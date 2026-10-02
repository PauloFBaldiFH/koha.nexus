"""SQL checks of the assistant: what may be read, what may be proposed.

These checks sit ON TOP of the database account (db.py), which is
SELECT-only: a statement that slipped past them would still be refused by
MariaDB. They exist so the model gets a clear error it can correct, and so
the person never sees a proposal the panel would not run.

check_select(sql)  -> the SELECT to run (with a LIMIT), or SQLRefused
check_write(sql)   -> a Write (single-table UPDATE/INSERT/DELETE), or SQLRefused
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_ROWS = 50


class SQLRefused(ValueError):
    pass


# Never readable or writable through the assistant, whatever the account allows.
SENSITIVE_TABLES = ("sessions", "api_keys", "borrower_password_recovery", "oauth_access_tokens",
                    "two_factor_auth", "user_secrets")
SENSITIVE_COLUMNS = ("password", "secret", "token", "api_key")
SYSTEM_SCHEMAS = ("mysql", "performance_schema", "sys", "information_schema")

_WRITE_WORDS = ("insert", "update", "delete", "replace", "drop", "truncate", "alter", "create",
                "rename", "grant", "revoke", "lock", "unlock", "call", "handler", "load", "set",
                "do", "prepare", "execute", "deallocate", "flush", "kill", "shutdown", "install",
                "uninstall", "optimize", "repair", "analyze", "purge", "reset", "commit", "rollback",
                "savepoint", "start", "begin", "xa", "use")
_DDL_WORDS = ("drop", "truncate", "alter", "create", "rename", "grant", "revoke")
_BAD_FUNCTIONS = ("sleep", "benchmark", "load_file", "get_lock", "release_lock", "is_free_lock",
                  "master_pos_wait", "sys_exec", "sys_eval")


# ----------------------------------------------------------------------
# Tokenising: strings and comments out, so a keyword inside a title
# ("Drop Dead Gorgeous") is not mistaken for a statement.
# ----------------------------------------------------------------------
_TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<comment>--[^\n]*|\#[^\n]*|/\*.*?\*/)
  | (?P<str>'(?:[^'\\]|\\.|'')*'|"(?:[^"\\]|\\.|"")*")
  | (?P<ident>`(?:[^`]|``)*`)
  | (?P<word>[A-Za-z_][A-Za-z0-9_$]*)
  | (?P<num>\d+(?:\.\d+)?)
  | (?P<op>[^\sA-Za-z0-9_'"`])
""", re.S | re.X)


@dataclass
class Token:
    kind: str
    text: str

    @property
    def low(self) -> str:
        return self.text.lower()


def tokens(sql: str) -> list[Token]:
    out, pos = [], 0
    while pos < len(sql):
        m = _TOKEN.match(sql, pos)
        if not m:
            raise SQLRefused("could not read the SQL (unbalanced quote?)")
        pos = m.end()
        kind = m.lastgroup or ""
        if kind == "comment":
            raise SQLRefused("comments are not allowed in the SQL")
        if kind != "ws":
            out.append(Token(kind, m.group()))
    return out


def _single_statement(toks: list[Token]) -> list[Token]:
    while toks and toks[-1].text == ";":
        toks = toks[:-1]
    if any(t.text == ";" for t in toks):
        raise SQLRefused("only one statement is allowed")
    if not toks:
        raise SQLRefused("empty SQL")
    return toks


def _names(toks: list[Token]) -> list[str]:
    return [t.low.strip("`") for t in toks if t.kind in ("word", "ident")]


def _check_names(toks: list[Token]) -> None:
    names = _names(toks)
    for i, n in enumerate(names):
        if n in SENSITIVE_TABLES:
            raise SQLRefused(f"the table {n} is not available to the assistant")
        if n in SENSITIVE_COLUMNS or n.endswith("_password"):
            raise SQLRefused(f"the column {n} is not available to the assistant")
        if n in SYSTEM_SCHEMAS:
            raise SQLRefused(f"the {n} schema is not available to the assistant")
    for i, t in enumerate(toks):
        if t.kind == "word" and t.low in _BAD_FUNCTIONS and i + 1 < len(toks) and toks[i + 1].text == "(":
            raise SQLRefused(f"{t.low}() is not allowed")


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------
def check_select(sql: str, max_rows: int = MAX_ROWS) -> str:
    """The SELECT to run, wrapped with a LIMIT; SQLRefused otherwise."""
    toks = _single_statement(tokens(sql))
    first = toks[0].low
    if first not in ("select", "with") and toks[0].text != "(":
        raise SQLRefused("only SELECT queries can be run; propose a change instead")
    words = {t.low for t in toks if t.kind == "word"}
    bad = words & set(_WRITE_WORDS)
    # "set" is a write word but also part of nothing legitimate in a SELECT;
    # "replace" is also a string function: allowed when called as replace(.
    if "replace" in bad and all(toks[i + 1].text == "("
                                for i, t in enumerate(toks[:-1]) if t.low == "replace"):
        bad.discard("replace")
    if bad:
        raise SQLRefused(f"'{sorted(bad)[0].upper()}' is not allowed in a read-only query")
    if "into" in words:
        raise SQLRefused("SELECT ... INTO is not allowed")
    low = " ".join(t.low for t in toks)
    if "for update" in low or "lock in share mode" in low:
        raise SQLRefused("locking reads are not allowed")
    _check_names(toks)
    body = sql.strip().rstrip(";").strip()
    return f"SELECT * FROM ({body}) AS kei_q LIMIT {int(max_rows)}"


# ----------------------------------------------------------------------
# Proposals
# ----------------------------------------------------------------------
@dataclass
class Write:
    verb: str          # update | insert | delete
    table: str
    where: str         # "" for INSERT
    sql: str           # as proposed, without trailing ;

    def count_sql(self) -> str:
        """How many rows it would touch (run with the read-only account)."""
        return f"SELECT COUNT(*) AS n FROM {self.table} WHERE {self.where}"

    def capped(self, rows: int) -> str:
        """The statement that really runs: never more rows than the preview."""
        if self.verb == "insert":
            return self.sql
        return f"{self.sql} LIMIT {int(rows)}"


_TRIVIAL_WHERE = re.compile(r"^\(?\s*(1|true|1\s*=\s*1|'1'\s*=\s*'1'|\d+\s*=\s*\d+|1\s*<>\s*0)\s*\)?$", re.I)
_IDENT = r"`?([A-Za-z_][A-Za-z0-9_]*)`?"


def check_write(sql: str) -> Write:
    toks = _single_statement(tokens(sql))
    words = [t.low for t in toks if t.kind == "word"]
    verb = toks[0].low
    if verb not in ("update", "insert", "delete"):
        raise SQLRefused("a change must be one UPDATE, INSERT or DELETE")
    if set(words) & set(_DDL_WORDS):
        raise SQLRefused("structural commands (DROP, TRUNCATE, ALTER...) are never allowed")
    if "limit" in words or "join" in words or "select" in words and verb != "insert":
        raise SQLRefused("only simple single-table changes can be proposed (no JOIN, sub-select or LIMIT)")
    _check_names(toks)
    body = sql.strip().rstrip(";").strip()
    if verb == "insert":
        m = re.match(rf"insert\s+into\s+{_IDENT}\s*\(", body, re.I)
        if not m or "select" in words:
            raise SQLRefused("INSERT must be INSERT INTO table (columns) VALUES (...)")
        return Write("insert", m.group(1), "", body)
    if verb == "update":
        m = re.match(rf"update\s+{_IDENT}\s+set\s+.+?\s+where\s+(.+)$", body, re.I | re.S)
    else:
        m = re.match(rf"delete\s+from\s+{_IDENT}\s+where\s+(.+)$", body, re.I | re.S)
    if not m:
        raise SQLRefused(f"{verb.upper()} must name one table and have a WHERE clause")
    table, where = m.group(1), m.group(2).strip()
    if "," in table or _TRIVIAL_WHERE.match(where):
        raise SQLRefused("the WHERE clause must select specific rows")
    return Write(verb, table, where, body)
