"""static.db: the prebuilt enrichment database every client downloads.

Written by enrich_build, read here (read-only). One SQLite file:

    meta          schema version, build date, the zstd dictionary
    sources       one row per source: mode "full" or "pointer", weight,
                  whether it is Brazilian
    clusters      one row per manifestation group: an ISBN-13 (with a
                  title check, so a reused ISBN makes a second cluster)
                  or, without ISBN, a work key
    versions      every version of a record from every source, with its
                  match keys; body = the record as UTF-8 ISO 2709,
                  zstd-compressed with the shared dictionary, or NULL for
                  a pointer (the record stays at its source; remote_id
                  says where)
    idents        ISBN-13 / ISSN -> version (exact lookup)
    versions_fts  title, author and subject words (contentless FTS5,
                  rowid = versions.id)
    auth_headings authority headings: from authority records (LoC, BN…)
                  or gathered from the bibliographic records of the dumps
                  (marked preliminary)
    auth_fts      heading and variant words (contentless, rowid = id)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import marc
from .merge import Candidate

SCHEMA_VERSION = "1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value BLOB);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL,
    brazilian INTEGER NOT NULL DEFAULT 0, weight REAL NOT NULL DEFAULT 0.5,
    records INTEGER NOT NULL DEFAULT 0, headings INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY, isbn13 TEXT, work_key TEXT NOT NULL, title TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS clusters_isbn ON clusters(isbn13) WHERE isbn13 IS NOT NULL;
CREATE INDEX IF NOT EXISTS clusters_work ON clusters(work_key) WHERE isbn13 IS NULL;
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,   -- never reused: a replaced version's FTS entry stays dead
    cluster_id INTEGER NOT NULL REFERENCES clusters(id),
    source TEXT NOT NULL, remote_id TEXT NOT NULL,
    isbns TEXT NOT NULL DEFAULT '', work_key TEXT NOT NULL,
    title TEXT NOT NULL, author TEXT NOT NULL DEFAULT '', year INTEGER,
    edition TEXT NOT NULL DEFAULT '', publisher TEXT NOT NULL DEFAULT '',
    lang TEXT NOT NULL DEFAULT '', completeness INTEGER NOT NULL DEFAULT 0,
    checksum TEXT NOT NULL, body BLOB
);
CREATE UNIQUE INDEX IF NOT EXISTS versions_remote ON versions(source, remote_id);
CREATE INDEX IF NOT EXISTS versions_cluster ON versions(cluster_id);
CREATE INDEX IF NOT EXISTS versions_work ON versions(work_key);
CREATE TABLE IF NOT EXISTS idents (
    ident TEXT NOT NULL, version_id INTEGER NOT NULL,
    PRIMARY KEY (ident, version_id)
) WITHOUT ROWID;
CREATE VIRTUAL TABLE IF NOT EXISTS versions_fts USING fts5(
    title, author, subjects, content = '', tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS auth_headings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,              -- personal, corporate, meeting, uniform, topical, geographic, genre
    heading TEXT NOT NULL,           -- the heading as written ($a$b$c$d$q…), punctuation trimmed
    key TEXT NOT NULL,               -- folded heading without dates
    dates TEXT NOT NULL DEFAULT '',
    thesaurus TEXT NOT NULL DEFAULT '',
    variants TEXT NOT NULL DEFAULT '',   -- 4XX, one per line
    source TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    lccn TEXT NOT NULL DEFAULT '',
    uri TEXT NOT NULL DEFAULT '',
    occurrences INTEGER NOT NULL DEFAULT 1,
    preliminary INTEGER NOT NULL DEFAULT 1   -- 1: gathered from bibliographic records
);
CREATE UNIQUE INDEX IF NOT EXISTS auth_key ON auth_headings(kind, key, dates, thesaurus, source);
CREATE VIRTUAL TABLE IF NOT EXISTS auth_fts USING fts5(
    heading, variants, content = '', tokenize = 'unicode61 remove_diacritics 2'
);
"""


@dataclass
class Pointer:
    """A version whose record stays at its source (restricted licence)."""
    source: str
    remote_id: str
    title: str
    year: int | None


class StaticDB:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.execute("PRAGMA cache_size = -16000")     # 16 MB, the worker's memory cap is 256 MB
        self.conn.execute("PRAGMA mmap_size = 0")
        self.conn.row_factory = sqlite3.Row
        row = self.conn.execute("SELECT value FROM meta WHERE key = 'zstd_dict'").fetchone()
        self._dict = row[0] if row and row[0] else None
        self._dctx = None
        self.sources = {r["id"]: r for r in self.conn.execute("SELECT * FROM sources")}

    def close(self) -> None:
        self.conn.close()

    def meta(self, key: str):
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _decompress(self, body: bytes) -> bytes:
        if self._dctx is None:
            import zstandard
            d = zstandard.ZstdCompressionDict(self._dict) if self._dict else None
            self._dctx = zstandard.ZstdDecompressor(dict_data=d)
        return self._dctx.decompress(body)

    def _rows_to_candidates(self, rows) -> tuple[list[Candidate], list[Pointer]]:
        cands, pointers = [], []
        for r in rows:
            src = self.sources.get(r["source"])
            if r["body"] is None:
                pointers.append(Pointer(r["source"], r["remote_id"], r["title"], r["year"]))
                continue
            rec = marc.from_iso2709(self._decompress(r["body"]))
            cands.append(Candidate(rec, r["source"], r["remote_id"],
                                   weight=src["weight"] if src else 0.5,
                                   brazilian=bool(src["brazilian"]) if src else False))
        return cands, pointers

    def by_isbn(self, isbns: list[str]) -> tuple[list[Candidate], list[Pointer]]:
        if not isbns:
            return [], []
        rows = self.conn.execute(
            f"SELECT v.* FROM versions v WHERE v.id IN (SELECT version_id FROM idents WHERE ident IN "
            f"({', '.join('?' * len(isbns))})) ORDER BY v.completeness DESC, v.id", isbns).fetchall()
        return self._rows_to_candidates(rows)

    def by_work(self, work_key: str, limit: int = 50) -> tuple[list[Candidate], list[Pointer]]:
        rows = self.conn.execute("SELECT * FROM versions WHERE work_key = ? ORDER BY completeness DESC, id LIMIT ?",
                                 (work_key, limit)).fetchall()
        return self._rows_to_candidates(rows)

    def search(self, title: str = "", author: str = "", limit: int = 50) -> tuple[list[Candidate], list[Pointer]]:
        """Title and/or author words (every word must match)."""
        import re
        parts = []
        for column, text in (("title", title), ("author", author)):
            words = re.findall(r"\w+", text or "")
            parts += [f'{column} : "{w}"' for w in words]
        if not parts:
            return [], []
        rows = self.conn.execute(
            "SELECT v.* FROM versions v WHERE v.id IN (SELECT rowid FROM versions_fts WHERE versions_fts MATCH ? "
            "LIMIT ?) ORDER BY v.completeness DESC, v.id", (" AND ".join(parts), limit)).fetchall()
        return self._rows_to_candidates(rows)

    def candidates_for(self, rec: marc.Record) -> tuple[list[Candidate], list[Pointer]]:
        """Everything worth classifying for a local record: its ISBNs, then
        its work key. Duplicates (same source and id) are removed."""
        from .normalize import isbns13, work_key
        seen: set[tuple[str, str]] = set()
        cands: list[Candidate] = []
        pointers: list[Pointer] = []
        for found_c, found_p in (self.by_isbn(isbns13(rec)), self.by_work(work_key(rec))):
            for c in found_c:
                if (c.source, c.remote_id) not in seen:
                    seen.add((c.source, c.remote_id))
                    cands.append(c)
            for p in found_p:
                if (p.source, p.remote_id) not in seen:
                    seen.add((p.source, p.remote_id))
                    pointers.append(p)
        return cands, pointers

    def headings(self, kind: str, key: str, limit: int = 20) -> list[sqlite3.Row]:
        """Authority headings of one kind with this folded key: authority
        records (preliminary 0) first, then by occurrences."""
        return self.conn.execute(
            "SELECT * FROM auth_headings WHERE kind = ? AND key = ? ORDER BY preliminary, occurrences DESC LIMIT ?",
            (kind, key, limit)).fetchall()
