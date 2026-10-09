"""The shared pool: one SQLite file with a full-text index (FTS5).

    records      one row per work: search keys for display, the MARCXML, a
                 checksum (an unchanged record is not rewritten), who sent it
    idents       every ISBN-13, ISBN-10 and ISSN of a record (exact lookup)
    records_fts  title, author (all names) and keywords (title, names,
                 subjects, edition, publisher, series, notes, year), accents
                 folded, so "memorias" finds "Memórias"

A record sent by a library replaces the one in the pool that shares one of
its ISBNs/ISSNs, else the one with the same title, main author and year:
the latest version of a work wins, from whichever library it comes.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import cql
from .marc import Record, checksum, isbn_forms, issn_form

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY,
    record_key  TEXT NOT NULL UNIQUE,
    isbn        TEXT NOT NULL DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    author      TEXT NOT NULL DEFAULT '',
    year        TEXT NOT NULL DEFAULT '',
    marcxml     TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS records_title ON records(title);
CREATE INDEX IF NOT EXISTS records_author ON records(author);
CREATE INDEX IF NOT EXISTS records_updated ON records(updated_at);
CREATE TABLE IF NOT EXISTS idents (
    ident      TEXT NOT NULL,
    record_id  INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    PRIMARY KEY (ident, record_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idents_record ON idents(record_id);
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    title, author, keywords, tokenize = 'unicode61 remove_diacritics 2'
);
"""
MAX_CLAUSES = 20
COLUMNS = {"title": "title", "author": "author", "keywords": "keywords"}


class NoFTS5(RuntimeError):
    """This Python's SQLite was built without FTS5."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------
# CQL -> SQL
# ----------------------------------------------------------------------
def _fts_token(tok: str) -> str:
    prefix = tok.endswith("*")
    word = tok.rstrip("*")
    return '"' + word.replace('"', '""') + '"' + ("*" if prefix else "")


def fts_expr(column: str, term: str, relation: str) -> str:
    """The FTS5 MATCH text of one clause; "" when the term has no word.
    = and all: every word; any: one of them; ==, adj, exact: the phrase.
    A trailing * is a prefix search ("casm*")."""
    words = re.findall(r"\w+\*?", term)
    if not words:
        return ""
    if relation in ("==", "adj", "exact") and len(words) > 1 and not any(w.endswith("*") for w in words):
        phrase = " ".join(words).replace('"', '""')
        return f'{column} : "{phrase}"'
    parts = [f"{column} : {_fts_token(w)}" for w in words]
    if relation == "any":
        return "(" + " OR ".join(parts) + ")"
    return "(" + " AND ".join(parts) + ")"


def ident_forms(term: str) -> list[str]:
    forms = isbn_forms(term)
    if not forms:
        issn = issn_form(term)
        forms = [issn] if issn else []
    return forms or [re.sub(r"[\s\-]", "", term).upper()]


def to_sql(node: cql.Node, params: list, budget: list[int] | None = None) -> str:
    """A WHERE condition on records r for a CQL tree; values go to params."""
    budget = budget if budget is not None else [MAX_CLAUSES]
    if isinstance(node, cql.Bool):
        left = to_sql(node.left, params, budget)
        right = to_sql(node.right, params, budget)
        if node.op == "or":
            return f"({left} OR {right})"
        if node.op == "not":
            return f"({left} AND NOT {right})"
        return f"({left} AND {right})"
    budget[0] -= 1
    if budget[0] < 0:
        raise cql.CQLError(f"more than {MAX_CLAUSES} search clauses")
    if node.field == "all":
        return "1"
    if node.field == "isbn":
        forms = ident_forms(node.term)
        params.extend(forms)
        cond = f"r.id IN (SELECT record_id FROM idents WHERE ident IN ({', '.join('?' * len(forms))}))"
    else:
        expr = fts_expr(COLUMNS[node.field], node.term, node.relation)
        if not expr:
            return "1" if node.term.strip() == "*" else "0"
        params.append(expr)
        cond = "r.id IN (SELECT rowid FROM records_fts WHERE records_fts MATCH ?)"
    return f"NOT {cond}" if node.relation == "<>" else cond


# ----------------------------------------------------------------------
# The catalogue
# ----------------------------------------------------------------------
class Catalog:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write = threading.Lock()
        self._shared = None
        if self.path == ":memory:":     # tests: one connection shared by every thread
            self._shared = self._open()
        conn = self.conn()
        try:
            conn.executescript(SCHEMA)
        except sqlite3.OperationalError as exc:
            if "fts5" in str(exc).lower():
                raise NoFTS5(f"SQLite {sqlite3.sqlite_version} has no FTS5: {exc}") from None
            raise

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def conn(self) -> sqlite3.Connection:
        if self._shared is not None:
            return self._shared
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._local.conn = self._open()
        return conn

    # -- reading --------------------------------------------------------
    def count(self) -> int:
        return self.conn().execute("SELECT COUNT(*) FROM records").fetchone()[0]

    def search(self, node: cql.Node, start: int = 1, maximum: int = 10) -> tuple[int, list[str]]:
        """(number of hits, the MARCXML of hits start..start+maximum-1),
        newest first. start is 1-based, as in SRU."""
        params: list = []
        where = to_sql(node, params)
        conn = self.conn()
        total = conn.execute(f"SELECT COUNT(*) FROM records r WHERE {where}", params).fetchone()[0]
        if not total or maximum <= 0 or start > total:
            return total, []
        rows = conn.execute(
            f"SELECT r.marcxml FROM records r WHERE {where} ORDER BY r.updated_at DESC, r.id DESC LIMIT ? OFFSET ?",
            [*params, maximum, start - 1]).fetchall()
        return total, [row[0] for row in rows]

    # -- writing --------------------------------------------------------
    def _find(self, conn: sqlite3.Connection, rec: Record):
        idents = rec.idents
        if idents:
            row = conn.execute(
                f"SELECT r.id, r.checksum FROM records r JOIN idents i ON i.record_id = r.id "
                f"WHERE i.ident IN ({', '.join('?' * len(idents))}) ORDER BY r.id LIMIT 1", idents).fetchone()
            if row:
                return row
        return conn.execute("SELECT id, checksum FROM records WHERE record_key = ?", (rec.key,)).fetchone()

    def _put(self, conn: sqlite3.Connection, rec: Record, source: str, stamp: str) -> str:
        xml = rec.xml()
        digest = checksum(xml)
        row = self._find(conn, rec)
        values = (rec.isbns[0] if rec.isbns else (rec.issns[0] if rec.issns else ""),
                  rec.title, rec.author, rec.year, xml, digest, source, stamp)
        if row is not None and row["checksum"] == digest:
            return "unchanged"
        if row is not None:
            rid = row["id"]
            conn.execute("UPDATE records SET isbn = ?, title = ?, author = ?, year = ?, marcxml = ?, checksum = ?, "
                         "source = ?, updated_at = ? WHERE id = ?", (*values, rid))
            conn.execute("DELETE FROM idents WHERE record_id = ?", (rid,))
            conn.execute("DELETE FROM records_fts WHERE rowid = ?", (rid,))
            outcome = "updated"
        else:
            rid = conn.execute("INSERT INTO records (isbn, title, author, year, marcxml, checksum, source, "
                               "updated_at, record_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (*values, rec.key, stamp)).lastrowid
            outcome = "inserted"
        conn.executemany("INSERT OR IGNORE INTO idents (ident, record_id) VALUES (?, ?)",
                         [(i, rid) for i in rec.idents])
        conn.execute("INSERT INTO records_fts (rowid, title, author, keywords) VALUES (?, ?, ?, ?)",
                     (rid, rec.title, rec.authors, rec.keywords))
        return outcome

    def put_many(self, records: list[Record], source: str) -> dict[str, int]:
        """Insert or update records in one transaction; counts by outcome."""
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        stamp = now()
        with self._write:
            conn = self.conn()
            conn.execute("BEGIN IMMEDIATE")
            try:
                for rec in records:
                    counts[self._put(conn, rec, source, stamp)] += 1
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        return counts

    def close(self) -> None:
        conn = self._shared or getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()

