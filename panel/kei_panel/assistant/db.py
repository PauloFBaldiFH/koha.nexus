"""The assistant's only way into the Koha database: a read-only account.

    kei_ai_ro@localhost   SELECT on every Koha table except the sensitive
                          ones (sqlguard.SENSITIVE_TABLES), and on borrowers
                          / deletedborrowers without their password columns.

Its password lives in /etc/koha-easy-install/ai-readonly.cnf (0600, a
MySQL option file), so it never shows up on a command line. Every query
runs as

    SET SESSION TRANSACTION READ ONLY; SET SESSION max_statement_time=10; <query>

through the mysql client in XML mode (NULLs and tabs survive). The account
is created once, by the panel as root (provision_sql), behind the loader.

DemoDB answers the same queries from an in-memory SQLite copy of a few
Koha tables, so the assistant runs in --demo mode and in the tests.

Every function here BLOCKS: call it from a thread job of run_with_loader.
"""

from __future__ import annotations

import os
import re
import secrets
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from . import sqlguard

RO_USER = "kei_ai_ro"
RO_CNF = Path("/etc/koha-easy-install/ai-readonly.cnf")
STATEMENT_SECONDS = 10
NOT_SET_UP = "The assistant's read-only database access is not set up yet."


class DBError(RuntimeError):
    pass


class Database(Protocol):
    def query(self, sql: str) -> list[dict]: ...


# ----------------------------------------------------------------------
# Real Koha (MariaDB)
# ----------------------------------------------------------------------
def koha_conf_value(conf: Path, tag: str) -> str:
    """<config><tag> of koha-conf.xml (koha_conf_value in the installer)."""
    try:
        root = ET.parse(conf).getroot()
    except (OSError, ET.ParseError):
        return ""
    node = root.find(f"config/{tag}")
    return (node.text or "").strip() if node is not None else ""


def koha_conf(instance: str) -> Path:
    return Path(f"/etc/koha/sites/{instance}/koha-conf.xml")


def parse_xml_rows(text: str) -> list[dict]:
    """Output of mysql --xml: <resultset><row><field name=.. [xsi:nil]>."""
    if not text.strip():
        return []
    # One <resultset> document per statement that returns rows: wrap them.
    body = re.sub(r"<\?xml[^>]*\?>", "", text)
    try:
        root = ET.fromstring(f"<all>{body}</all>")
    except ET.ParseError as e:
        raise DBError(f"unreadable answer from mysql: {e}") from None
    nil = "{http://www.w3.org/2001/XMLSchema-instance}nil"
    rows = []
    for rs in root.iter("resultset"):
        rows = []                        # the last result set is the query's
        for row in rs.iter("row"):
            rows.append({f.get("name"): (None if f.get(nil) == "true" else (f.text or ""))
                         for f in row.iter("field")})
    return rows


class MariaDBReadOnly:
    def __init__(self, cnf: Path = RO_CNF, timeout: float = STATEMENT_SECONDS + 5):
        self.cnf = cnf
        self.timeout = timeout

    def ready(self) -> bool:
        return self.cnf.is_file()

    def query(self, sql: str) -> list[dict]:
        if not self.ready():
            raise DBError(NOT_SET_UP)
        script = (f"SET SESSION TRANSACTION READ ONLY; "
                  f"SET SESSION max_statement_time={STATEMENT_SECONDS}; {sql};")
        try:
            p = subprocess.run(["mysql", f"--defaults-file={self.cnf}", "--xml", "--batch"],
                               input=script, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise DBError("the query took too long and was stopped") from None
        except OSError as e:
            raise DBError(f"mysql client: {e}") from None
        if p.returncode != 0:
            raise DBError(_first_line(p.stderr) or f"mysql exit {p.returncode}")
        return parse_xml_rows(p.stdout)


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:300]
    return ""


# ----------------------------------------------------------------------
# Creating the account (root, once)
# ----------------------------------------------------------------------
def provision_sql(db: str, tables: list[str], borrower_cols: dict[str, list[str]],
                  password: str, host: str = "localhost") -> str:
    """CREATE USER + per-table SELECT grants. Idempotent (REVOKE first)."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", db):
        raise DBError(f"unexpected database name {db!r}")
    pw = password.replace("\\", "\\\\").replace("'", "''")
    acct = f"'{RO_USER}'@'{host}'"
    out = [f"CREATE USER IF NOT EXISTS {acct} IDENTIFIED BY '{pw}';",
           f"ALTER USER {acct} IDENTIFIED BY '{pw}' WITH MAX_USER_CONNECTIONS 4;",
           f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM {acct};"]
    for t in sorted(tables):
        if not re.fullmatch(r"[A-Za-z0-9_]+", t) or t in sqlguard.SENSITIVE_TABLES:
            continue
        if t in borrower_cols:
            cols = [c for c in borrower_cols[t] if re.fullmatch(r"[A-Za-z0-9_]+", c)
                    and c not in sqlguard.SENSITIVE_COLUMNS and not c.endswith("_password")]
            out.append(f"GRANT SELECT ({', '.join(f'`{c}`' for c in cols)}) ON `{db}`.`{t}` TO {acct};")
        else:
            out.append(f"GRANT SELECT ON `{db}`.`{t}` TO {acct};")
    out.append("FLUSH PRIVILEGES;")
    return "\n".join(out)


def option_file(db: str, password: str, host: str = "localhost", port: str = "") -> str:
    lines = ["[client]", f"user={RO_USER}", f"password={password}", f"database={db}"]
    if host and host != "localhost":
        lines += [f"host={host}", f"port={port or 3306}", "protocol=TCP"]
    return "\n".join(lines) + "\n"


def provision(instance: str, cnf: Path = RO_CNF) -> str:
    """Creates kei_ai_ro and its option file (the panel runs as root)."""
    conf = koha_conf(instance)
    db = koha_conf_value(conf, "database") or f"koha_{instance}"
    host = koha_conf_value(conf, "hostname") or "localhost"
    port = koha_conf_value(conf, "port")

    def root_sql(sql: str) -> str:
        p = subprocess.run(["mysql", "--batch", "--skip-column-names"], input=sql,
                           capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            raise DBError(_first_line(p.stderr) or "mysql (root) failed")
        return p.stdout

    tables = root_sql(f"SELECT table_name FROM information_schema.tables "
                      f"WHERE table_schema='{db}' AND table_type='BASE TABLE';").split()
    cols: dict[str, list[str]] = {}
    for t in ("borrowers", "deletedborrowers"):
        if t in tables:
            cols[t] = root_sql(f"SELECT column_name FROM information_schema.columns "
                               f"WHERE table_schema='{db}' AND table_name='{t}';").split()
    password = secrets.token_urlsafe(24)
    grant_host = "127.0.0.1" if host in ("127.0.0.1", "::1") else "localhost"
    root_sql(provision_sql(db, tables, cols, password, grant_host))
    cnf.parent.mkdir(parents=True, exist_ok=True)
    tmp = cnf.with_name(cnf.name + ".tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(option_file(db, password, host, port))
    os.replace(tmp, cnf)
    return db


# ----------------------------------------------------------------------
# Demo: a few Koha tables in SQLite
# ----------------------------------------------------------------------
_DEMO_SCHEMA = """
CREATE TABLE biblio (biblionumber INTEGER PRIMARY KEY, title TEXT, subtitle TEXT, author TEXT,
    seriestitle TEXT, copyrightdate INTEGER, abstract TEXT, notes TEXT);
CREATE TABLE biblioitems (biblioitemnumber INTEGER PRIMARY KEY, biblionumber INTEGER, isbn TEXT,
    publishercode TEXT);
CREATE TABLE items (itemnumber INTEGER PRIMARY KEY, biblionumber INTEGER, barcode TEXT,
    homebranch TEXT, itemcallnumber TEXT, onloan TEXT);
CREATE TABLE borrowers (borrowernumber INTEGER PRIMARY KEY, cardnumber TEXT, firstname TEXT,
    surname TEXT, categorycode TEXT, branchcode TEXT, email TEXT, phone TEXT, dateenrolled TEXT,
    dateexpiry TEXT, lastseen TEXT, password TEXT);
CREATE TABLE issues (issue_id INTEGER PRIMARY KEY, borrowernumber INTEGER, itemnumber INTEGER,
    issuedate TEXT, date_due TEXT);
CREATE TABLE accountlines (accountlines_id INTEGER PRIMARY KEY, borrowernumber INTEGER,
    amount REAL, amountoutstanding REAL, debit_type_code TEXT, description TEXT);
CREATE TABLE saved_sql (id INTEGER PRIMARY KEY, report_name TEXT, notes TEXT, savedsql TEXT,
    date_created TEXT);
CREATE TABLE systempreferences (variable TEXT PRIMARY KEY, value TEXT, explanation TEXT,
    type TEXT);
"""


def _demo_rows(today: date) -> dict[str, list[tuple]]:
    d = lambda n: (today + timedelta(days=n)).isoformat() + " 23:59:00"   # noqa: E731
    return {
        "biblio": [
            (1, "It", "a novel", "King, Stephen", None, 1986,
             "Seven friends face a shape-shifting evil that takes the form of Pennywise the clown.", None),
            (2, "A coisa", None, "King, Stephen", None, 2014,
             "Edição brasileira de It: o palhaço Pennywise aterroriza Derry.", "Tradução de Regiane Winarski"),
            (3, "Dom Casmurro", None, "Assis, Machado de", None, 1899, None, None),
            (4, "O pequeno príncipe", None, "Saint-Exupéry, Antoine de", None, 1943, None, None),
            (5, "Drop dead gorgeous", "a mystery", "Smith, Jane", None, 2001, None, None),
            (6, "Coraline", None, "Gaiman, Neil", None, 2002, "Adaptado para o cinema em 2009.", None),
        ],
        "biblioitems": [(1, 1, "9781501142970", "Scribner"), (2, 2, "9788556510785", "Suma"),
                        (3, 3, "9788594318602", "Penguin"), (4, 4, "9788595081512", "HarperCollins"),
                        (5, 5, "", ""), (6, 6, "9788551001189", "Intrínseca")],
        "items": [(10, 1, "0001", "CPL", "813 K52i", None), (11, 2, "0002", "CPL", "813 K52c", d(-20)),
                  (12, 2, "0003", "CPL", "813 K52c", d(-15)), (13, 3, "0004", "CPL", "869.3 A848d", d(-9)),
                  (14, 4, "0005", "CPL", "843 S135p", d(-30)), (15, 6, "0006", "CPL", "823 G142c", d(-3)),
                  (16, 3, "0007", "CPL", "869.3 A848d", d(-4)), (17, 4, "0008", "CPL", "843 S135p", d(3)),
                  (18, 5, "0009", "CPL", "813 S642d", d(-5)), (19, 6, "0010", "CPL", "823 G142c", d(-6))],
        "borrowers": [
            (101, "C0101", "Ana", "Souza", "ADULT", "CPL", "ana@example.org", "", "2024-03-01", "2027-03-01",
             d(-1), "$2a$08$x"),
            (102, "C0102", "Bruno", "Lima", "ADULT", "CPL", "", "", "2023-05-10", "2026-12-31",
             d(-5), "$2a$08$y"),
            (103, "C0103", "Carla", "Mendes", "STUDENT", "CPL", "", "", "2025-02-11", "2027-02-11",
             d(-40), "$2a$08$z"),
            (104, "C0104", "Diego", "Rocha", "ADULT", "CPL", "", "", "2022-08-20", "2026-11-20",
             d(-2), "$2a$08$w"),
        ],
        "issues": [  # Ana: 4 overdue; Diego: 4 overdue; Bruno: 1 not overdue
            (1, 101, 11, d(-40), d(-20)), (2, 101, 12, d(-35), d(-15)), (3, 101, 13, d(-30), d(-9)),
            (4, 101, 14, d(-50), d(-30)), (5, 102, 17, d(-11), d(3)),
            (6, 104, 15, d(-20), d(-3)), (7, 104, 16, d(-21), d(-4)), (8, 104, 18, d(-22), d(-5)),
            (9, 104, 19, d(-23), d(-6)),
        ],
        "accountlines": [(1, 101, 100.0, 100.0, "OVERDUE", "It"), (2, 101, 44.0, 44.0, "OVERDUE", "Dom Casmurro"),
                         (3, 104, 144.0, 144.0, "LOST", "Coraline"), (4, 104, 20.0, -20.0, None, "Payment"),
                         (5, 102, 5.0, 0.0, "OVERDUE", "")],
        "saved_sql": [(1, "Overdues by branch", "Circulation", "SELECT branchcode, COUNT(*) FROM issues "
                       "WHERE date_due < NOW() GROUP BY branchcode", "2025-01-10"),
                      (2, "Patrons with fines over 50", "Accounts", "SELECT borrowernumber, SUM(amountoutstanding) "
                       "FROM accountlines GROUP BY borrowernumber HAVING SUM(amountoutstanding) > 50", "2025-04-02")],
        "systempreferences": [
            ("OverdueNoticeCalendar", "0", "Use the calendar when calculating overdue notices", "YesNo"),
            ("finesMode", "production", "Calculate fines (production) or only test them", "Choice"),
            ("SearchEngine", "Zebra", "Search engine used by the catalogue", "Choice"),
        ],
    }


class DemoDB:
    """Same SQL as MariaDB for what the tools use (NOW() and CURDATE() added)."""

    def __init__(self, today: date | None = None):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.create_function("NOW", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.conn.create_function("CURDATE", 0, lambda: date.today().isoformat())
        self.conn.executescript(_DEMO_SCHEMA)
        for table, rows in _demo_rows(today or date.today()).items():
            marks = ",".join("?" * len(rows[0]))
            self.conn.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
        self.conn.commit()

    def ready(self) -> bool:
        return True

    def query(self, sql: str) -> list[dict]:
        try:
            cur = self.conn.execute(sql)
        except sqlite3.Error as e:
            raise DBError(str(e)) from None
        return [{k: (None if r[k] is None else str(r[k])) for k in r.keys()} for r in cur.fetchall()]

    def execute(self, sql: str) -> int:
        """Demo only: runs a confirmed change. sqlite has no UPDATE ... LIMIT."""
        sql = re.sub(r"\s+LIMIT\s+\d+\s*$", "", sql, flags=re.I)
        cur = self.conn.execute(sql)
        self.conn.commit()
        return cur.rowcount
