"""jobs.db: the jobs, one row per record read, and the Koha batches of the
Apply step. Every write commits at once, so a stop at any point resumes
from the last checkpoint."""

from __future__ import annotations

import json
import sqlite3
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

from nexus_enrich import marc

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    scope TEXT NOT NULL,
    state TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    release TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);
-- One row per exported record. before/after/other: zlib MARCXML, kept only
-- for records with something to show (enriched, review).
CREATE TABLE IF NOT EXISTS items (
    job_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    biblionumber INTEGER,
    status TEXT NOT NULL,
    f005 TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    m0 INTEGER NOT NULL DEFAULT 0,
    m1 INTEGER NOT NULL DEFAULT 0,
    w INTEGER NOT NULL DEFAULT 0,
    r INTEGER NOT NULL DEFAULT 0,
    pointers INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT '{}',
    before BLOB,
    after BLOB,
    other BLOB,
    chunk INTEGER,
    PRIMARY KEY (job_id, seq)
);
CREATE INDEX IF NOT EXISTS items_chunk ON items (job_id, chunk);
CREATE INDEX IF NOT EXISTS items_bib ON items (job_id, biblionumber);
-- One row per Koha import batch of the Apply step.
CREATE TABLE IF NOT EXISTS chunks (
    job_id INTEGER NOT NULL,
    chunk INTEGER NOT NULL,
    records INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',   -- pending, applied, failed, reverted
    batch INTEGER,
    staged INTEGER NOT NULL DEFAULT 0,       -- records in the batch file
    applied TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (job_id, chunk)
);
-- Per record of an applied chunk: what happened, and its 005 right after
-- the commit (a later edit by a librarian is kept by Revert).
CREATE TABLE IF NOT EXISTS applied (
    job_id INTEGER NOT NULL,
    chunk INTEGER NOT NULL,
    biblionumber INTEGER NOT NULL,
    state TEXT NOT NULL,                     -- staged, skipped-changed, skipped-deleted, skipped-match, applied, kept
    f005 TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (job_id, chunk, biblionumber)
);
-- Authority jobs: one row per authority to create at Apply (one per
-- heading for the whole job). The bibliographic records link to it by a
-- placeholder $9 nexus-new:ID until Koha gives it an authid.
CREATE TABLE IF NOT EXISTS auth_new (
    job_id INTEGER NOT NULL,
    id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    dates TEXT NOT NULL DEFAULT '',
    heading TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    preliminary INTEGER NOT NULL DEFAULT 1,
    fuzzy REAL NOT NULL DEFAULT 0,
    record BLOB,
    chunk INTEGER,
    state TEXT NOT NULL DEFAULT 'pending',   -- pending, exists, staged, created, failed, kept, reverted
    authid INTEGER,
    PRIMARY KEY (job_id, id)
);
CREATE UNIQUE INDEX IF NOT EXISTS auth_new_key ON auth_new (job_id, kind, key, dates);
"""

# Columns added after the first release of jobs.db.
_ADDED = (("jobs", "kind", "TEXT NOT NULL DEFAULT 'bib'"), ("jobs", "mode", "TEXT NOT NULL DEFAULT ''"),
          ("chunks", "kind", "TEXT NOT NULL DEFAULT 'bib'"))

OPEN_STATES = ("queued", "exported", "matching")


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def pack(rec: marc.Record | None) -> bytes | None:
    return None if rec is None else zlib.compress(marc.to_xml(rec).encode("utf-8"), 6)


def unpack(blob: bytes | None) -> marc.Record | None:
    if not blob:
        return None
    return marc.parse_xml(zlib.decompress(blob))[0]


@dataclass
class Job:
    id: int
    created: str
    updated: str
    scope: str
    state: str
    total: int
    done: int
    release: str
    error: str
    kind: str = "bib"          # bib: enrich bibliographic records; auth: authorities
    mode: str = ""             # auth: exact or fuzzy

    def as_dict(self) -> dict:
        return dict(self.__dict__)


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA cache_size = -8000")
        self.conn.executescript(SCHEMA)
        for table, column, decl in _ADDED:
            if column not in {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def close(self) -> None:
        self.conn.close()

    # -- jobs ------------------------------------------------------------
    def add(self, scope: str, kind: str = "bib", mode: str = "") -> Job:
        t = now()
        cur = self.conn.execute("INSERT INTO jobs (created, updated, scope, state, kind, mode) "
                                "VALUES (?, ?, ?, 'queued', ?, ?)", (t, t, scope, kind, mode))
        return self.job(cur.lastrowid)

    def job(self, job_id: int) -> Job:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"no job {job_id}")
        return Job(**dict(row))

    def jobs(self) -> list[Job]:
        return [Job(**dict(r)) for r in self.conn.execute("SELECT * FROM jobs ORDER BY id DESC")]

    def next_job(self) -> Job | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE state IN ('exported', 'matching') ORDER BY id LIMIT 1"
                                ).fetchone()
        return Job(**dict(row)) if row else None

    def set(self, job_id: int, **values) -> None:
        values["updated"] = now()
        cols = ", ".join(f"{k} = ?" for k in values)
        self.conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", (*values.values(), job_id))

    # -- items -----------------------------------------------------------
    def put_items(self, rows: list[dict]) -> None:
        self.conn.execute("BEGIN")
        try:
            self.conn.executemany(
                "INSERT OR REPLACE INTO items (job_id, seq, biblionumber, status, f005, title, m0, m1, w, r, "
                "pointers, detail, before, after, other) VALUES (:job_id, :seq, :biblionumber, :status, :f005, "
                ":title, :m0, :m1, :w, :r, :pointers, :detail, :before, :after, :other)", rows)
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def counts(self, job_id: int) -> dict:
        out = {"enriched": 0, "unchanged": 0, "review": 0, "no-match": 0, "error": 0}
        for status, n in self.conn.execute("SELECT status, COUNT(*) FROM items WHERE job_id = ? GROUP BY status",
                                           (job_id,)):
            out[status] = n
        row = self.conn.execute(
            "SELECT COALESCE(SUM(m0 > 0), 0), COALESCE(SUM(m1 > 0), 0), COALESCE(SUM(w > 0), 0), "
            "COALESCE(SUM(r > 0), 0), COALESCE(SUM(m0 + m1 + w), 0), COALESCE(SUM(pointers > 0), 0) "
            "FROM items WHERE job_id = ?", (job_id,)).fetchone()
        out["records_with"] = {"M0": row[0], "M1": row[1], "W": row[2], "R": row[3]}
        out["fields_added"] = row[4]
        out["pointer_only"] = row[5]
        return out

    def item(self, job_id: int, biblionumber: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM items WHERE job_id = ? AND biblionumber = ? ORDER BY seq LIMIT 1",
                                 (job_id, biblionumber)).fetchone()

    def items(self, job_id: int, *statuses: str, limit: int | None = None):
        sql = "SELECT * FROM items WHERE job_id = ?"
        args: list = [job_id]
        if statuses:
            sql += f" AND status IN ({', '.join('?' * len(statuses))})"
            args += statuses
        sql += " ORDER BY seq"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        return self.conn.execute(sql, args)

    # -- chunks ----------------------------------------------------------
    def make_chunks(self, job_id: int, size: int = 500) -> int:
        """Enriched records in groups of at most SIZE (one Koha batch each);
        for an authority job, the new authorities first, in their own
        batches (the records link to them)."""
        self.conn.execute("BEGIN")
        try:
            self.conn.execute("DELETE FROM chunks WHERE job_id = ?", (job_id,))
            n = 0
            ids = [r[0] for r in self.conn.execute("SELECT id FROM auth_new WHERE job_id = ? ORDER BY id", (job_id,))]
            for i in range(0, len(ids), size):
                n += 1
                part = ids[i:i + size]
                self.conn.executemany("UPDATE auth_new SET chunk = ? WHERE job_id = ? AND id = ?",
                                      [(n, job_id, a) for a in part])
                self.conn.execute("INSERT INTO chunks (job_id, chunk, records, kind) VALUES (?, ?, ?, 'auth')",
                                  (job_id, n, len(part)))
            seqs = [r[0] for r in self.conn.execute(
                "SELECT seq FROM items WHERE job_id = ? AND status = 'enriched' ORDER BY seq", (job_id,))]
            for i in range(0, len(seqs), size):
                n += 1
                part = seqs[i:i + size]
                self.conn.executemany("UPDATE items SET chunk = ? WHERE job_id = ? AND seq = ?",
                                      [(n, job_id, s) for s in part])
                self.conn.execute("INSERT INTO chunks (job_id, chunk, records) VALUES (?, ?, ?)",
                                  (job_id, n, len(part)))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        return n

    def chunks(self, job_id: int) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM chunks WHERE job_id = ? ORDER BY chunk", (job_id,)).fetchall()

    def chunk(self, job_id: int, chunk: int) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM chunks WHERE job_id = ? AND chunk = ?", (job_id, chunk)).fetchone()
        if row is None:
            raise KeyError(f"no chunk {chunk} in job {job_id}")
        return row

    def set_chunk(self, job_id: int, chunk: int, **values) -> None:
        cols = ", ".join(f"{k} = ?" for k in values)
        self.conn.execute(f"UPDATE chunks SET {cols} WHERE job_id = ? AND chunk = ?",
                          (*values.values(), job_id, chunk))

    def set_applied(self, job_id: int, chunk: int, rows: list[tuple[int, str, str]]) -> None:
        """rows: (biblionumber, state, f005)."""
        self.conn.executemany("INSERT OR REPLACE INTO applied (job_id, chunk, biblionumber, state, f005) "
                              "VALUES (?, ?, ?, ?, ?)", [(job_id, chunk, b, s, f) for b, s, f in rows])

    def applied(self, job_id: int, chunk: int | None = None) -> list[sqlite3.Row]:
        if chunk is None:
            return self.conn.execute("SELECT * FROM applied WHERE job_id = ? ORDER BY chunk, biblionumber",
                                     (job_id,)).fetchall()
        return self.conn.execute("SELECT * FROM applied WHERE job_id = ? AND chunk = ? ORDER BY biblionumber",
                                 (job_id, chunk)).fetchall()


    # -- new authorities (authority jobs) ---------------------------------
    def new_authority(self, job_id: int, kind: str, key: str, dates: str, heading: str, source: str,
                      preliminary: bool, fuzzy: float, record: bytes | None) -> int:
        """The id of the job's new authority for this heading, created on
        first use (a record matched again after a restart gets the same id)."""
        row = self.conn.execute("SELECT id FROM auth_new WHERE job_id = ? AND kind = ? AND key = ? AND dates = ?",
                                (job_id, kind, key, dates)).fetchone()
        if row is not None:
            return row[0]
        nid = self.conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM auth_new WHERE job_id = ?",
                                (job_id,)).fetchone()[0]
        self.conn.execute("INSERT INTO auth_new (job_id, id, kind, key, dates, heading, source, preliminary, fuzzy, "
                          "record) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (job_id, nid, kind, key, dates, heading, source, int(preliminary), fuzzy, record))
        return nid

    def new_authorities(self, job_id: int, chunk: int | None = None) -> list[sqlite3.Row]:
        if chunk is None:
            return self.conn.execute("SELECT * FROM auth_new WHERE job_id = ? ORDER BY id", (job_id,)).fetchall()
        return self.conn.execute("SELECT * FROM auth_new WHERE job_id = ? AND chunk = ? ORDER BY id",
                                 (job_id, chunk)).fetchall()

    def set_new_authority(self, job_id: int, nid: int, **values) -> None:
        cols = ", ".join(f"{k} = ?" for k in values)
        self.conn.execute(f"UPDATE auth_new SET {cols} WHERE job_id = ? AND id = ?", (*values.values(), job_id, nid))


def detail(item: sqlite3.Row) -> dict:
    return json.loads(item["detail"] or "{}")
