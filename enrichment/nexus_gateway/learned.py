"""learned.db: what live targets answered, kept so the same search is
answered locally next time (and an answer that came after the reply was
sent is not lost). Local to this machine, never shipped.

    answers   one row per (target, query key): when, how many hits the
              target reported, or the error it gave
    records   the first page of records of that answer, as UTF-8 ISO 2709

An answer is used for LEARNED_DAYS; an error, or an answer with no
records, only for ERROR_SECONDS, so a target that is down is not asked on
every search but is tried again soon, and a "nothing found" from a broken
route does not stick for a month once the route is fixed.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from nexus_enrich import marc

ERROR_SECONDS = 600

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS answers (
    target TEXT NOT NULL, qkey TEXT NOT NULL, fetched_at INTEGER NOT NULL,
    total INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (target, qkey)
);
CREATE TABLE IF NOT EXISTS records (
    target TEXT NOT NULL, qkey TEXT NOT NULL, pos INTEGER NOT NULL, body BLOB NOT NULL,
    PRIMARY KEY (target, qkey, pos)
);
"""


class Learned:
    """Safe to use from several threads: each thread gets its own connection."""

    def __init__(self, path: Path | str, days: int = 30):
        self.path = Path(path)
        self.max_age = days * 86400
        self._local = threading.local()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn().executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=5)
            self._local.conn = conn
        return conn

    def get(self, target: str, qkey: str, now: float | None = None) -> tuple[int, list[marc.Record], str] | None:
        """(total, records, error) of a fresh answer, else None."""
        now = time.time() if now is None else now
        conn = self._conn()
        row = conn.execute("SELECT fetched_at, total, error FROM answers WHERE target = ? AND qkey = ?",
                           (target, qkey)).fetchone()
        if row is None:
            return None
        fetched, total, error = row
        if now - fetched > (ERROR_SECONDS if error or not total else self.max_age):
            return None
        records = []
        for (body,) in conn.execute("SELECT body FROM records WHERE target = ? AND qkey = ? ORDER BY pos",
                                    (target, qkey)):
            try:
                records.append(marc.from_iso2709(body))
            except marc.RecordError:
                continue
        return total, records, error

    def put(self, target: str, qkey: str, total: int, records: list[marc.Record], error: str = "",
            now: float | None = None) -> None:
        now = time.time() if now is None else now
        conn = self._conn()
        with conn:
            conn.execute("DELETE FROM records WHERE target = ? AND qkey = ?", (target, qkey))
            conn.execute("INSERT OR REPLACE INTO answers (target, qkey, fetched_at, total, error) VALUES (?,?,?,?,?)",
                         (target, qkey, int(now), total, error))
            conn.executemany("INSERT INTO records (target, qkey, pos, body) VALUES (?,?,?,?)",
                             [(target, qkey, i, marc.to_iso2709(r)) for i, r in enumerate(records)])

    def prune(self, now: float | None = None) -> int:
        """Remove answers past their age; returns how many."""
        now = time.time() if now is None else now
        conn = self._conn()
        with conn:
            old = conn.execute("SELECT target, qkey FROM answers WHERE fetched_at < ?",
                               (int(now - self.max_age),)).fetchall()
            for target, qkey in old:
                conn.execute("DELETE FROM records WHERE target = ? AND qkey = ?", (target, qkey))
                conn.execute("DELETE FROM answers WHERE target = ? AND qkey = ?", (target, qkey))
        return len(old)
