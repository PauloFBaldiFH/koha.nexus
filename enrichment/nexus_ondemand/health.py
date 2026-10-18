"""health.db: what on-demand enrichment learned about each direct server.
Local to this machine, never shipped. No background probing: everything
here comes from real requests and from the panel's manual test.

Per address (Address.key, so an alternate has its own):
    breaker       closed, open (until a time) or misconfigured
    events        each success and failure of the last 7 days
    capabilities  which forms of query the server refused (diagnostic 114...)
Per target: the alternate that answered (for "unconfirmed" entries).
Per limit key (host:port or provider): sessions per day and the rate
factor after a ban-like signal (limits.py reads both).

Breaker rules (plan section 6.2):
- 3 consecutive failures (a "down" one counts twice), or 5 in 10 minutes,
  open it for 5 min x 2^level; it is half-open after that: one real
  request may try it, success closes it, failure reopens it a level up
  (at most 24 h).
- A ban-like signal (the server closed for resources, cost or security;
  two resets at Init in 10 minutes; a refused connection on a host that
  answered earlier the same day) opens it for 24 h and halves the rate
  of that host, and of its provider once 3 of its hosts did so in 24 h.
- A refused login, an unknown database or an unsupported record syntax
  marks it misconfigured: never retried until the list file changes,
  the panel's "Test again", or reset().
- A refused query form or one bad record means the server is up.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from nexus_gateway.z3950 import Diagnostic, Z3950Error

OPEN_BASE = 300.0
OPEN_MAX = 86400.0
MAX_LEVEL = 8
CONSECUTIVE = 3
WINDOW = 600.0
WINDOW_FAILURES = 5
BAN_SECONDS = 86400.0
PROVIDER_BANS = 3
KEEP_EVENTS = 7 * 86400
FACTOR_MIN = 0.125
FACTOR_RESTORE = 0.25                # per clean day
BAN_CLOSE_REASONS = (3, 4, 5)        # costLimit, resources, securityViolation

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS breaker (
    key TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'closed', level INTEGER NOT NULL DEFAULT 0,
    open_until REAL NOT NULL DEFAULT 0, consecutive INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '', last_error_at REAL NOT NULL DEFAULT 0,
    last_ok_at REAL NOT NULL DEFAULT 0, latency_ms REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    key TEXT NOT NULL, at REAL NOT NULL, ok INTEGER NOT NULL, category TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT '', phase TEXT NOT NULL DEFAULT '', provider TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS events_key_at ON events (key, at);
CREATE TABLE IF NOT EXISTS capabilities (
    key TEXT NOT NULL, capability TEXT NOT NULL, ok INTEGER NOT NULL, at REAL NOT NULL,
    PRIMARY KEY (key, capability)
);
CREATE TABLE IF NOT EXISTS preferred (target TEXT PRIMARY KEY, address TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS daily (key TEXT NOT NULL, day TEXT NOT NULL, count INTEGER NOT NULL,
                                  PRIMARY KEY (key, day));
CREATE TABLE IF NOT EXISTS aimd (key TEXT PRIMARY KEY, factor REAL NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@dataclass(frozen=True)
class Outcome:
    """What one failure means for the server.

    category: transient, down, misconfigured, capability, bad_data, policy or ban."""
    category: str
    kind: str = ""
    phase: str = ""
    detail: str = ""


def classify_diagnostic(diag: Diagnostic, phase: str = "search") -> Outcome:
    category = {"query": "capability", "config": "misconfigured", "record": "bad_data"}.get(diag.category, "transient")
    return Outcome(category, "diagnostic", phase, str(diag))


def classify(exc: BaseException) -> Outcome:
    """The Outcome of a Z3950Error (PolicyError included)."""
    kind = getattr(exc, "kind", "") if isinstance(exc, Z3950Error) else ""
    phase = getattr(exc, "phase", "") if isinstance(exc, Z3950Error) else ""
    detail = str(exc) or type(exc).__name__
    if kind == "policy":
        return Outcome("policy", kind, phase, detail)
    if kind in ("dns", "refused"):
        return Outcome("down", kind, phase, detail)
    if kind == "init-refused":
        return Outcome("misconfigured", kind, phase, detail)
    if kind == "closed":
        reason = getattr(exc, "close_reason", None)
        return Outcome("ban" if reason in BAN_CLOSE_REASONS else "transient", kind, phase, detail)
    diag = getattr(exc, "diagnostic", None)
    if kind == "diagnostic" and diag is not None:
        return classify_diagnostic(diag, phase)
    return Outcome("transient", kind, phase, detail)


def local_day(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


class Health:
    def __init__(self, path: Path | str, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=5)
        self.conn.executescript(SCHEMA)
        self._probing: set[str] = set()         # half-open keys with their one probe in flight

    def close(self) -> None:
        self.conn.close()

    # breaker ------------------------------------------------------------

    def _row(self, key: str) -> dict:
        cur = self.conn.execute("SELECT * FROM breaker WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return {"key": key, "state": "closed", "level": 0, "open_until": 0.0, "consecutive": 0,
                    "last_error": "", "last_error_at": 0.0, "last_ok_at": 0.0, "latency_ms": 0.0}
        return dict(zip([c[0] for c in cur.description], row))

    def _save(self, row: dict) -> None:
        cols = list(row)
        self.conn.execute(f"INSERT OR REPLACE INTO breaker ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                          [row[c] for c in cols])

    def state(self, key: str, now: float | None = None) -> str:
        """ok, down (open, waiting), half-open (may be tried once) or misconfigured."""
        now = self.clock() if now is None else now
        row = self._row(key)
        if row["state"] == "misconfigured":
            return "misconfigured"
        if row["state"] == "open":
            return "down" if now < row["open_until"] else "half-open"
        return "ok"

    def allow(self, key: str, now: float | None = None) -> str:
        """"" when a request may use KEY now (a half-open key: only as its
        one probe, which this call claims), else why not."""
        now = self.clock() if now is None else now
        row = self._row(key)
        state = self.state(key, now)
        if state == "ok":
            return ""
        if state == "misconfigured":
            return f"misconfigured: {row['last_error']}"
        if state == "down":
            return "down until " + time.strftime("%H:%M", time.localtime(row["open_until"]))
        if key in self._probing:
            return "being retried by another request"
        self._probing.add(key)
        return ""

    def _event(self, key: str, now: float, ok: bool, o: Outcome | None = None, provider: str = "") -> None:
        o = o or Outcome("ok")
        self.conn.execute("INSERT INTO events (key, at, ok, category, kind, phase, provider, detail) "
                          "VALUES (?,?,?,?,?,?,?,?)",
                          (key, now, int(ok), o.category, o.kind, o.phase, provider, o.detail[:300]))

    def record_success(self, key: str, latency_ms: float | None = None, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        with self.conn:
            row = self._row(key)
            row.update(state="closed", level=0, open_until=0.0, consecutive=0)
            row["last_ok_at"] = now
            if latency_ms is not None:
                row["latency_ms"] = latency_ms if not row["latency_ms"] else 0.7 * row["latency_ms"] + 0.3 * latency_ms
            self._save(row)
            self._event(key, now, True)
        self._probing.discard(key)

    def _ban_signal(self, key: str, o: Outcome, row: dict, now: float) -> bool:
        if o.category == "ban":
            return True
        if o.kind == "reset" and o.phase == "init":
            n = self.conn.execute("SELECT COUNT(*) FROM events WHERE key = ? AND at > ? AND kind = 'reset' "
                                  "AND phase = 'init' AND ok = 0", (key, now - WINDOW)).fetchone()[0]
            return n >= 1                                    # this one is the second
        if o.kind == "refused" and row["last_ok_at"] and local_day(row["last_ok_at"]) == local_day(now):
            return True
        return False

    def record_failure(self, key: str, outcome: Outcome, now: float | None = None, host_key: str = "",
                       provider: str = "") -> str:
        """Record a failure; returns the breaker state after it."""
        now = self.clock() if now is None else now
        if outcome.category in ("capability", "bad_data"):
            with self.conn:
                self._event(key, now, False, outcome, provider)
            self.record_success(key, None, now)              # it answered: it is up
            return self.state(key, now)
        with self.conn:
            row = self._row(key)
            was_half_open = self.state(key, now) == "half-open"
            ban = outcome.category != "policy" and self._ban_signal(key, outcome, row, now)
            self._event(key, now, False, Outcome("ban", outcome.kind, outcome.phase, outcome.detail)
                        if ban else outcome, provider)
            row.update(last_error=outcome.detail[:300], last_error_at=now)
            if outcome.category == "policy":
                pass
            elif outcome.category == "misconfigured":
                row["state"] = "misconfigured"
            elif ban:
                row.update(state="open", open_until=now + BAN_SECONDS, consecutive=0)
                if host_key:
                    self._penalize(host_key, now)
                if provider and self._provider_bans(provider, now) >= PROVIDER_BANS:
                    self._penalize(provider, now)
            else:
                row["consecutive"] += 2 if outcome.category == "down" else 1
                recent = self.conn.execute(
                    "SELECT COUNT(*) FROM events WHERE key = ? AND at > ? AND ok = 0 "
                    "AND category IN ('transient', 'down')", (key, now - WINDOW)).fetchone()[0]
                if was_half_open:
                    row["level"] = min(row["level"] + 1, MAX_LEVEL)
                    row.update(state="open", open_until=now + min(OPEN_BASE * 2 ** row["level"], OPEN_MAX))
                elif row["state"] != "misconfigured" and (row["consecutive"] >= CONSECUTIVE
                                                          or recent >= WINDOW_FAILURES):
                    row.update(state="open", open_until=now + min(OPEN_BASE * 2 ** row["level"], OPEN_MAX),
                               consecutive=0)
            self._save(row)
        self._probing.discard(key)
        return self.state(key, now)

    def _provider_bans(self, provider: str, now: float) -> int:
        return self.conn.execute("SELECT COUNT(DISTINCT key) FROM events WHERE provider = ? AND at > ? "
                                 "AND category = 'ban'", (provider, now - BAN_SECONDS)).fetchone()[0]

    def release(self, key: str) -> None:
        """A claimed half-open probe that never ran (the request ended first)."""
        self._probing.discard(key)

    def reset(self, key: str | None = None) -> int:
        """Forget the breaker of KEY (every key when None); returns how many."""
        with self.conn:
            if key is None:
                n = self.conn.execute("DELETE FROM breaker").rowcount
                self._probing.clear()
            else:
                n = self.conn.execute("DELETE FROM breaker WHERE key = ?", (key,)).rowcount
                self._probing.discard(key)
        return n

    def check_list(self, sha256: str) -> bool:
        """A new list file clears every misconfigured server; True when it changed."""
        old = self.conn.execute("SELECT value FROM meta WHERE name = 'list_sha256'").fetchone()
        if old and old[0] == sha256:
            return False
        with self.conn:
            if old:
                self.conn.execute("UPDATE breaker SET state = 'closed', consecutive = 0 "
                                  "WHERE state = 'misconfigured'")
            self.conn.execute("INSERT OR REPLACE INTO meta (name, value) VALUES ('list_sha256', ?)", (sha256,))
        return True

    # what servers can do ---------------------------------------------

    def note_capability(self, key: str, capability: str, ok: bool, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO capabilities (key, capability, ok, at) VALUES (?,?,?,?)",
                              (key, capability, int(ok), now))

    def capability(self, key: str, capability: str) -> bool | None:
        row = self.conn.execute("SELECT ok FROM capabilities WHERE key = ? AND capability = ?",
                                (key, capability)).fetchone()
        return None if row is None else bool(row[0])

    def set_preferred(self, target: str, address_key: str, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO preferred (target, address, at) VALUES (?,?,?)",
                              (target, address_key, now))

    def preferred(self, target: str) -> str:
        row = self.conn.execute("SELECT address FROM preferred WHERE target = ?", (target,)).fetchone()
        return row[0] if row else ""

    # limits' persistent state ------------------------------------------

    def daily(self, key: str, now: float | None = None) -> int:
        now = self.clock() if now is None else now
        row = self.conn.execute("SELECT count FROM daily WHERE key = ? AND day = ?", (key, local_day(now))).fetchone()
        return row[0] if row else 0

    def add_daily(self, key: str, now: float | None = None) -> int:
        now = self.clock() if now is None else now
        with self.conn:
            self.conn.execute("INSERT INTO daily (key, day, count) VALUES (?, ?, 1) "
                              "ON CONFLICT (key, day) DO UPDATE SET count = count + 1", (key, local_day(now)))
        return self.daily(key, now)

    def factor(self, key: str, now: float | None = None) -> float:
        """The rate factor of a limit key: 1, halved by each ban-like
        signal (at least FACTOR_MIN), back by FACTOR_RESTORE per clean day."""
        now = self.clock() if now is None else now
        row = self.conn.execute("SELECT factor, at FROM aimd WHERE key = ?", (key,)).fetchone()
        if row is None:
            return 1.0
        days = int(max(0.0, now - row[1]) // 86400)
        return min(1.0, row[0] + FACTOR_RESTORE * days)

    def _penalize(self, key: str, now: float) -> None:
        self.conn.execute("INSERT OR REPLACE INTO aimd (key, factor, at) VALUES (?, ?, ?)",
                          (key, max(FACTOR_MIN, self.factor(key, now) / 2), now))

    # reporting and upkeep ------------------------------------------------

    def summary(self, key: str, now: float | None = None) -> dict:
        now = self.clock() if now is None else now
        row = self._row(key)
        ok, fail = self.conn.execute("SELECT COALESCE(SUM(ok), 0), COALESCE(SUM(1 - ok), 0) FROM events "
                                     "WHERE key = ? AND at > ?", (key, now - KEEP_EVENTS)).fetchone()
        return {"key": key, "state": self.state(key, now), "level": row["level"], "open_until": row["open_until"],
                "last_error": row["last_error"], "last_error_at": row["last_error_at"],
                "last_ok_at": row["last_ok_at"], "latency_ms": round(row["latency_ms"]),
                "ok_7d": ok, "fail_7d": fail}

    def prune(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        with self.conn:
            self.conn.execute("DELETE FROM events WHERE at < ?", (now - KEEP_EVENTS,))
            self.conn.execute("DELETE FROM daily WHERE day < ?", (local_day(now - 3 * 86400),))
