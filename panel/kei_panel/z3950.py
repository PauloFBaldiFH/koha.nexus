"""Z39.50 / SRU targets: the list, the health scan and the files around it.

The screen (views/z3950.py) shows Koha's copy-cataloguing sources grouped
by region and adds the chosen ones to Koha's z3950servers table through
`config.sh --task z3950-add`. Everything else lives here, with no Textual:

  * the list: a curated baseline (data/z3950_targets.json, shipped with the
    panel), the community copy of that file on GitHub (community_sync), and
    the person's own imports, kept in the panel's config folder;
  * readers for what people share: JSON, a small YAML subset, CSV, a Koha
    SQL dump of z3950servers, and a scraper for registry pages and
    bulletins (host:port/db, labelled fields, SRU addresses);
  * writers: JSON, CSV and Koha SQL (passwords left out unless asked);
  * the scan: each server's port is tried with a 3 s timeout (the listed
    one, then 210, 2100 and 2210), then a real search for a book every
    library has (Don Quixote, The Little Prince) asking for one record:
    Z39.50 with a small BER client of its own (Init, Search, Present), SRU
    with a searchRetrieve. A server counts as working only when the record
    is a valid MARC frame (ISO 2709) or MARCXML. Latency is kept in ms;
  * a history of the scans: a host that fails 3 scans in a row, or that the
    person blacklists, is hidden from the list.

A target's password is never printed, logged or exported by default:
Target.password is left out of repr(), describe() and the SQL/CSV/JSON
writers unless the caller asks for it.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from .env import CONFIG_DIR

DATA_FILE = Path(__file__).with_name("data") / "z3950_targets.json"
COMMUNITY_URL = ("https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/"
                 "panel/kei_panel/data/z3950_targets.json")
LOCAL_FILE = "z3950-targets.json"     # the person's imports and logins
HISTORY_FILE = "z3950-history.json"   # scan results and the blacklist

REGIONS = {
    "latam": "Brazil / Latin America",
    "north_america": "North America",
    "europe": "Europe",
    "asia_pacific": "Asia-Pacific",
    "academia": "Specialized / Academia",
}
SYNTAXES = ("USMARC", "MARC21", "UNIMARC", "NORMARC", "DANMARC")
ENCODINGS = ("utf8", "MARC-8", "ISO_5426", "ISO_6937", "ISO_8859-1", "EUC-KR")
ALT_PORTS = (210, 2100, 2210)
CONNECT_TIMEOUT = 3.0
QUERY_TIMEOUT = 8.0
FAILS_TO_BLACKLIST = 3
HISTORY_RULES = 2                     # bumped when the scan's idea of "working" changes
RULES_KEY = "_rules"
# Words of titles every catalogue has: Don Quixote and The Little Prince.
PROBE_TERMS = ("quixote", "quijote", "prince", "principe")


_DIR: Path | None = None


def use_dir(path: Path | None) -> None:
    """Another folder for the list and the history (demo mode)."""
    global _DIR
    _DIR = path


def config_dir() -> Path:
    """Where the panel keeps the list and the history (KEI_Z3950_DIR in the
    tests)."""
    return Path(os.environ.get("KEI_Z3950_DIR") or _DIR or CONFIG_DIR)


# ----------------------------------------------------------------------
# The target
# ----------------------------------------------------------------------
@dataclass
class Target:
    name: str
    host: str
    port: int = 210
    db: str = ""
    kind: str = "zed"            # zed (Z39.50) or sru, Koha's servertype
    syntax: str = "USMARC"
    encoding: str = "utf8"
    region: str = "academia"
    country: str = ""
    login: bool = False          # the server needs a user and password
    user: str = ""
    password: str = field(default="", repr=False)
    schema: str = ""             # SRU recordSchema (marcxml...)
    sru_fields: str = ""         # Koha's SRU search field mapping (title=dc.title,...)
    sru_options: str = ""        # Koha's extra SRU options (sru_version=1.1,...)
    preselect: bool = False      # ticked when the screen opens
    source: str = ""
    notes: str = ""
    verified: bool = False       # taken from the library's own published page
    origin: str = "curated"      # curated, community, imported, custom

    @property
    def key(self) -> str:
        return f"{self.host.lower()}:{self.port}/{self.db}"

    @property
    def host_key(self) -> str:
        return self.host.lower()

    def describe(self) -> str:
        """One line for screens and logs, never with the password."""
        login = f" user={self.user}" if self.user else (" (login needed)" if self.login else "")
        return f"{self.name} [{self.kind}] {self.host}:{self.port}/{self.db} {self.syntax}{login}"

    def to_dict(self, passwords: bool = False) -> dict:
        d = {k: v for k, v in asdict(self).items() if v not in ("", False) or k in ("name", "host", "port")}
        d.pop("origin", None)
        if not passwords:
            d.pop("password", None)
        return d


_BOOL = {"1", "true", "yes", "y", "sim", "x"}
_ALIASES = {
    "name": ("name", "servername", "server_name", "server", "title", "library", "label", "nome", "biblioteca"),
    "host": ("host", "hostname", "address", "server_address", "url", "endereco", "servidor"),
    "port": ("port", "porta", "puerto"),
    "db": ("db", "database", "databasename", "dbname", "base", "base_de_dados", "basededatos"),
    "kind": ("kind", "servertype", "type", "protocol", "tipo"),
    "syntax": ("syntax", "recordsyntax", "format", "marc", "formato"),
    "encoding": ("encoding", "charset", "codificacao"),
    "region": ("region", "regiao", "group"),
    "country": ("country", "pais"),
    "user": ("user", "userid", "username", "login_user", "usuario"),
    "password": ("password", "pass", "senha"),
    "schema": ("schema", "recordschema"),
    "sru_fields": ("sru_fields", "srufields"),
    "sru_options": ("sru_options", "sruoptions"),
    "preselect": ("preselect",),
    "source": ("source", "fonte"),
    "notes": ("notes", "note", "comment", "obs"),
    "login": ("login", "needs_login", "auth"),
    "verified": ("verified",),
}
_FIELD_OF = {alias: f for f, aliases in _ALIASES.items() for alias in aliases}


def _norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(k).strip().lower().replace(" ", "_").replace("-", "_"))


def normalize_syntax(s: str) -> str:
    s = (s or "").strip().upper().replace(" ", "")
    if s in ("", "MARC", "MARC21", "USMARC", "MARC-21"):
        return "USMARC"
    return s if s in SYNTAXES else s or "USMARC"


def normalize_kind(s: str) -> str:
    s = (s or "").strip().lower()
    return "sru" if s in ("sru", "srw", "http", "https") else "zed"


def guess_region(country: str, host: str) -> str:
    c = (country or "").upper()
    tld = host.rsplit(".", 1)[-1].lower() if "." in host else ""
    if c in ("BR", "AR", "MX", "CL", "CO", "PE", "UY", "PY", "BO", "VE", "EC", "CU") or tld in (
            "br", "ar", "mx", "cl", "co", "pe", "uy", "py", "bo", "ve", "ec", "cu"):
        return "latam"
    if c in ("US", "CA") or tld in ("gov", "edu", "us", "ca"):
        return "north_america"
    if c in ("AU", "NZ", "JP", "CN", "KR", "IN", "SG", "TW", "HK") or tld in (
            "au", "nz", "jp", "cn", "kr", "in", "sg", "tw", "hk"):
        return "asia_pacific"
    if c and len(c) == 2 or tld in ("fr", "de", "es", "pt", "it", "uk", "se", "no", "dk", "fi", "nl", "be",
                                    "ch", "at", "pl", "cz", "ie", "eu"):
        return "europe"
    return "academia"


def make_target(raw: dict, origin: str = "imported") -> Target | None:
    """A Target from a dict with any of the usual column names, or None when
    there is no host. A URL in host (sru://, http://host:port/db) is split."""
    d: dict = {}
    for k, v in raw.items():
        f = _FIELD_OF.get(_norm_key(k))
        if f and v not in (None, "") and f not in d:
            d[f] = v.strip() if isinstance(v, str) else v
    host = str(d.get("host", "")).strip()
    if not host:
        return None
    port, db = d.get("port"), str(d.get("db", "")).strip()
    kind = normalize_kind(str(d.get("kind", "")))
    m = re.match(r"^(?:(z3950|zed|sru|https?)://)?([A-Za-z0-9.-]+)(?::(\d+))?(?:/(\S*))?$", host)
    if not m:
        return None
    scheme, host = m.group(1), m.group(2)
    if m.group(3) and not port:
        port = m.group(3)
    if m.group(4) and not db:
        db = m.group(4).split("?", 1)[0]
    if scheme in ("sru", "http", "https"):
        kind = "sru"
    try:
        port = int(str(port).strip()) if port not in (None, "") else (443 if scheme == "https" else
                                                                      80 if kind == "sru" else 210)
    except ValueError:
        return None
    if not 0 < port < 65536 or "." not in host:
        return None
    country = str(d.get("country", "")).upper()[:2]
    region = str(d.get("region", "")).strip().lower()
    if region not in REGIONS:
        region = next((k for k, v in REGIONS.items() if v.lower() == region), "") or guess_region(country, host)
    return Target(
        name=str(d.get("name") or host)[:100], host=host, port=port, db=db, kind=kind,
        syntax=normalize_syntax(str(d.get("syntax", ""))),
        encoding=str(d.get("encoding") or "utf8"), region=region, country=country,
        login=_truthy(d.get("login")) or bool(d.get("user")), user=str(d.get("user", "")),
        password=str(d.get("password", "")), schema=str(d.get("schema", "")),
        sru_fields=str(d.get("sru_fields", "")) if kind == "sru" else "",
        sru_options=str(d.get("sru_options", "")) if kind == "sru" else "",
        preselect=_truthy(d.get("preselect")),
        source=str(d.get("source", "")), notes=str(d.get("notes", "")),
        verified=_truthy(d.get("verified")), origin=origin)


def _truthy(v) -> bool:
    return v is True or str(v).strip().lower() in _BOOL


def merge(*lists: list[Target]) -> list[Target]:
    """One target per host:port/db; a later list wins, but a login the
    person typed is kept."""
    out: dict[str, Target] = {}
    for targets in lists:
        for t in targets:
            old = out.get(t.key)
            if old and old.user and not t.user:
                t = replace(t, user=old.user, password=old.password, login=True)
            out[t.key] = t
    return list(out.values())


# ----------------------------------------------------------------------
# Readers
# ----------------------------------------------------------------------
def parse_json(text: str, origin: str = "imported") -> list[Target]:
    data = json.loads(text)
    items = data.get("targets", data.get("servers", [])) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("no list of targets in this JSON")
    return [t for t in (make_target(i, origin) for i in items if isinstance(i, dict)) if t]


def parse_yaml(text: str, origin: str = "imported") -> list[Target]:
    """The YAML of simple registries: a list of flat mappings, at the top or
    under one key ("targets:"). No anchors, no nesting beyond that."""
    items: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s*-\s+(.*)$", line)
        if m:
            cur = {}
            items.append(cur)
            line = m.group(1)
        kv = re.match(r"^\s*([A-Za-z_][\w -]*):\s*(.*?)\s*$", line)
        if kv and cur is not None:
            value = kv.group(2)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            cur[kv.group(1)] = value
    return [t for t in (make_target(i, origin) for i in items) if t]


def parse_csv(text: str, origin: str = "imported") -> list[Target]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return []
    head = [_norm_key(h) for h in rows[0]]
    if "host" not in {_FIELD_OF.get(h) for h in head}:
        # No header: name, host, port, db[, syntax] or host, port, db.
        head = ["name", "host", "port", "db", "syntax"] if len(rows[0]) >= 4 and not rows[0][1].isdigit() \
            else ["host", "port", "db", "syntax"]
        body = rows
    else:
        body = rows[1:]
    return [t for t in (make_target(dict(zip(head, r)), origin) for r in body if any(c.strip() for c in r)) if t]


# Koha's z3950servers columns, in order (an INSERT with no column list).
KOHA_COLUMNS = ("id", "host", "port", "db", "userid", "password", "servername", "checked", "rank", "syntax",
                "timeout", "servertype", "encoding", "recordtype", "sru_options", "sru_fields", "add_xslt",
                "attributes")


def _sql_values(s: str) -> list[list]:
    """The tuples of a VALUES (...), (...) list: quoted strings (backslash
    and doubled quotes), numbers and NULL."""
    rows, row, i, n = [], None, 0, len(s)
    while i < n:
        c = s[i]
        if c == "(" and row is None:
            row = []
        elif c == ")" and row is not None:
            rows.append(row)
            row = None
        elif row is not None and c in "'\"":
            q, j, buf = c, i + 1, []
            while j < n:
                if s[j] == "\\" and j + 1 < n:
                    buf.append({"n": "\n", "t": "\t", "0": "\0"}.get(s[j + 1], s[j + 1]))
                    j += 2
                    continue
                if s[j] == q:
                    if j + 1 < n and s[j + 1] == q:
                        buf.append(q)
                        j += 2
                        continue
                    break
                buf.append(s[j])
                j += 1
            row.append("".join(buf))
            i = j
        elif row is not None and (c.isalnum() or c in "-."):
            m = re.match(r"[-\w.]+", s[i:])
            word = m.group(0)
            row.append(None if word.upper() == "NULL" else word)
            i += len(word) - 1
        elif c == ";" and row is None:
            break
        i += 1
    return rows


def parse_koha_sql(text: str, origin: str = "imported") -> list[Target]:
    """INSERT INTO z3950servers ... statements of a mysqldump or of Koha's
    own sample SQL (with or without a column list). Authority targets are
    skipped."""
    out: list[Target] = []
    pat = re.compile(r"INSERT\s+(?:IGNORE\s+)?INTO\s+`?z3950servers`?\s*(\(([^)]*)\))?\s*(VALUES|SELECT)\s*",
                     re.I)
    for m in pat.finditer(text):
        cols = [c.strip(" `") for c in m.group(2).split(",")] if m.group(2) else list(KOHA_COLUMNS)
        rest = text[m.end():]
        if m.group(3).upper() == "SELECT":
            # Our own export: INSERT ... SELECT 'host', 210, ... FROM DUAL WHERE NOT EXISTS (...)
            end = re.search(r"\sFROM\s+DUAL\b", rest, re.I)
            rest = "(" + rest[:end.start() if end else len(rest)] + ")"
        for values in _sql_values(rest):
            row = dict(zip(cols, values))
            if str(row.get("recordtype") or "biblio").lower() == "authority":
                continue
            t = make_target({
                "name": row.get("servername"), "host": row.get("host"), "port": row.get("port"),
                "db": row.get("db"), "syntax": row.get("syntax"), "encoding": row.get("encoding"),
                "kind": row.get("servertype"), "user": row.get("userid"),
                "password": row.get("password")}, origin)
            if t:
                out.append(t)
    return out


_HOSTPORT = re.compile(r"(?<![\w.@/-])((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}|\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})"
                       r"(?:/([A-Za-z0-9_.:-]+))?")
_HOST = re.compile(r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}|\d{1,3}(?:\.\d{1,3}){3}")
_SRU_URL = re.compile(r"https?://([A-Za-z0-9.-]+)(?::(\d+))?/([^\s\"'<>?]*)\?[^\s\"'<>]*"
                      r"operation=(?:searchRetrieve|explain)", re.I)
_LABEL = re.compile(r"^\s*(host(?:name)?|server|address|port|database|db|base|syntax|record syntax|"
                    r"format|name|servidor|porta|puerto|base de dados|base de datos|endereço)\s*[:=]\s*(.+?)\s*$",
                    re.I)


def scrape(text: str, origin: str = "imported") -> list[Target]:
    """Endpoints in a page or bulletin someone pasted or saved: HTML tags are
    dropped, then three shapes are read: host:port/database, blocks of
    labelled lines (Host: / Port: / Database:), table rows with a host and a
    port cell, and SRU addresses (…?operation=searchRetrieve)."""
    found: list[Target] = []
    for m in _SRU_URL.finditer(text):
        port = int(m.group(2) or (443 if m.group(0).lower().startswith("https") else 80))
        found.append(Target(name=m.group(1), host=m.group(1), port=port, db=m.group(3).strip("/"),
                            kind="sru", region=guess_region("", m.group(1)), origin=origin))
    plain = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    if re.search(r"<(html|body|table|p|div)\b", plain, re.I):
        # In HTML a new line in the source means nothing (outside <pre>).
        parts = re.split(r"(<pre\b.*?</pre>)", plain, flags=re.S | re.I)
        plain = "".join(p if p[:4].lower() == "<pre" else re.sub(r"\s+", " ", p) for p in parts)
    plain = re.sub(r"</(td|th)>", "\t", plain, flags=re.I)
    plain = re.sub(r"<br\s*/?>|</(tr|p|div|li|h\d)>", "\n", plain, flags=re.I)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = plain.replace("&nbsp;", " ").replace("&amp;", "&")
    sru_hosts = {t.host for t in found}
    for line in plain.splitlines():
        cells = [c.strip() for c in line.split("\t") if c.strip()]
        for m in _HOSTPORT.finditer(line):
            host = m.group(1)
            if host in sru_hosts or not 0 < int(m.group(2)) < 65536:
                continue
            name = next((c for c in cells if m.group(0) not in c and not c.isdigit()), host)
            found.append(Target(name=name[:100], host=host, port=int(m.group(2)), db=m.group(3) or "",
                                syntax=_syntax_in(line), region=guess_region("", host), origin=origin))
        if len(cells) >= 3 and not _HOSTPORT.search(line):
            host = next((c for c in cells if _HOST.fullmatch(c)), "")
            port = next((c for c in cells if re.fullmatch(r"\d{2,5}", c)), "")
            if host and port:
                rest = [c for c in cells if c not in (host, port)]
                db = next((c for c in rest if re.fullmatch(r"[A-Za-z0-9_.-]{2,40}", c)
                           and c.upper() not in SYNTAXES), "")
                name = next((c for c in rest if c != db and " " in c), host)
                found.append(Target(name=name[:100], host=host, port=int(port), db=db, syntax=_syntax_in(line),
                                    region=guess_region("", host), origin=origin))
    # Labelled blocks: a new block starts at each name or host line.
    block: dict = {}

    def flush() -> None:
        if block.get("host"):
            t = make_target(dict(block), origin)
            if t:
                found.append(t)
        block.clear()
    for line in plain.splitlines():
        m = _LABEL.match(line)
        if not m:
            if not line.strip():
                flush()
            continue
        label = m.group(1).lower()
        f = ("host" if label in ("host", "hostname", "server", "address", "servidor", "endereço") else
             "port" if label in ("port", "porta", "puerto") else
             "syntax" if label in ("syntax", "record syntax", "format") else
             "name" if label == "name" else "db")
        if f in block and f in ("host", "name"):
            flush()
        block[f] = m.group(2) if f == "name" else m.group(2).split()[0]
    flush()
    return merge(found)


def _syntax_in(text: str) -> str:
    m = re.search(r"\b(UNIMARC|USMARC|MARC21|MARC 21|NORMARC|DANMARC)\b", text, re.I)
    return normalize_syntax(m.group(1)) if m else "USMARC"


def read_any(text: str, name: str = "", origin: str = "imported") -> list[Target]:
    """The reader that fits the file name, else the content."""
    low, head = name.lower(), text.lstrip()[:200]
    if low.endswith(".json") or head.startswith(("{", "[")):
        return parse_json(text, origin)
    if re.search(r"INSERT\s+(IGNORE\s+)?INTO\s+`?z3950servers", text, re.I):
        return parse_koha_sql(text, origin)
    if low.endswith((".yml", ".yaml")) or re.match(r"^(\w+:\s*\n)?\s*-\s+\w+:", head):
        return parse_yaml(text, origin)
    if low.endswith((".csv", ".tsv")):
        return parse_csv(text, origin)
    return scrape(text, origin)


# ----------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------
def to_json(targets: list[Target], passwords: bool = False) -> str:
    return json.dumps({"schema": 1, "targets": [t.to_dict(passwords) for t in targets]},
                      ensure_ascii=False, indent=1) + "\n"


CSV_COLUMNS = ("name", "host", "port", "db", "kind", "syntax", "encoding", "region", "country", "user",
               "schema", "source", "notes")


def to_csv(targets: list[Target], passwords: bool = False) -> str:
    cols = CSV_COLUMNS + (("password",) if passwords else ())
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for t in targets:
        w.writerow([getattr(t, c) for c in cols])
    return buf.getvalue()


def _q(v) -> str:
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def to_koha_sql(targets: list[Target], ranks: dict[str, int] | None = None, passwords: bool = False) -> str:
    """INSERT statements another Koha can load (a target already there, same
    host, port and database, is skipped)."""
    lines = ["-- Z39.50/SRU targets exported by koha.nexus"]
    for i, t in enumerate(targets, 1):
        rank = (ranks or {}).get(t.key, i)
        pw = t.password if passwords else ""
        lines.append(
            "INSERT INTO z3950servers (host, port, db, userid, password, servername, checked, `rank`, syntax, "
            "timeout, servertype, encoding, recordtype, sru_fields, sru_options) SELECT "
            f"{_q(t.host)}, {int(t.port)}, {_q(t.db)}, {_q(t.user)}, {_q(pw)}, {_q(t.name)}, 1, {int(rank)}, "
            f"{_q(t.syntax)}, 0, {_q(t.kind)}, {_q(t.encoding)}, 'biblio', {_q(sru_fields(t))}, "
            f"{_q(t.sru_options if t.kind == 'sru' else '')} FROM DUAL WHERE NOT EXISTS "
            f"(SELECT 1 FROM z3950servers WHERE host = {_q(t.host)} AND port = {int(t.port)} "
            f"AND db = {_q(t.db)} AND recordtype = 'biblio');")
    return "\n".join(lines) + "\n"


def write_export(path: Path, targets: list[Target], passwords: bool = False) -> None:
    low = path.name.lower()
    text = (to_csv(targets, passwords) if low.endswith(".csv") else
            to_koha_sql(targets, passwords=passwords) if low.endswith(".sql") else to_json(targets, passwords))
    path.write_text(text, encoding="utf-8")


# The file config.sh --task z3950-add reads: one line per target.
ADD_FIELDS = ("host", "port", "db", "syntax", "encoding", "name", "rank", "timeout", "kind", "user", "password",
              "sru_fields", "sru_options")
DEFAULT_SRU_FIELDS = "title=dc.title,isbn=bath.isbn,author=dc.creator"


def sru_fields(t: Target) -> str:
    """Koha's SRU search field mapping: the target's own, else the usual one."""
    if t.kind != "sru":
        return ""
    return t.sru_fields or DEFAULT_SRU_FIELDS


def _cell(v) -> str:
    return re.sub(r"[\t\r\n]+", " ", str(v)).strip()


def add_file_text(targets: list[Target], ranks: dict[str, int]) -> str:
    lines = []
    for t in targets:
        row = {"host": t.host, "port": t.port, "db": t.db, "syntax": t.syntax, "encoding": t.encoding,
               "name": t.name, "rank": ranks.get(t.key, 0), "timeout": 0, "kind": t.kind, "user": t.user,
               "password": t.password, "sru_fields": sru_fields(t),
               "sru_options": t.sru_options if t.kind == "sru" else ""}
        lines.append("\t".join(_cell(row[f]) for f in ADD_FIELDS))
    return "\n".join(lines) + "\n"


def write_add_file(targets: list[Target], ranks: dict[str, int]) -> Path:
    """A private (0600) temporary file for z3950-add; it holds the logins,
    so config.sh deletes it as soon as it has read it."""
    fd, name = tempfile.mkstemp(prefix="kei-z3950-", suffix=".tsv")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(add_file_text(targets, ranks))
    os.chmod(name, 0o600)
    return Path(name)


# ----------------------------------------------------------------------
# The list on disk
# ----------------------------------------------------------------------
def load_curated(path: Path = DATA_FILE) -> list[Target]:
    try:
        return parse_json(path.read_text(encoding="utf-8"), "curated")
    except (OSError, ValueError):
        return []


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def load_local() -> list[Target]:
    try:
        data = json.loads((config_dir() / LOCAL_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for item in data.get("targets", []):
        t = make_target(item, item.get("origin", "imported"))
        if t:
            out.append(t)
    return out


def save_local(targets: list[Target]) -> None:
    """The person's own targets and logins (root only, 0600): the curated
    ones are saved only when they carry a login."""
    keep = [t for t in targets if t.origin != "curated" or t.user]
    items = [dict(t.to_dict(passwords=True), origin=t.origin) for t in keep]
    _write_private(config_dir() / LOCAL_FILE, json.dumps({"schema": 1, "targets": items}, ensure_ascii=False,
                                                         indent=1) + "\n")


def load_all() -> list[Target]:
    return merge(load_curated(), load_local())


def community_sync(url: str = COMMUNITY_URL, timeout: float = 15.0) -> list[Target]:
    """The community copy of the list (GitHub): new and corrected targets
    without a new panel. Raises OSError/ValueError when it cannot be read."""
    req = urllib.request.Request(url, headers={"User-Agent": "koha.nexus-panel"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # noqa: S310 (fixed https URL)
        text = resp.read(2_000_000).decode("utf-8", "replace")
    targets = read_any(text, url, "community")
    if not targets:
        raise ValueError("the community list has no targets")
    return targets


# ----------------------------------------------------------------------
# History and blacklist
# ----------------------------------------------------------------------
class History:
    """Per host:port/db: the last scan, consecutive failures, a blacklist mark."""

    def __init__(self, path: Path | None = None):
        self.path = path or config_dir() / HISTORY_FILE
        try:
            self.data: dict = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        if self.data.get(RULES_KEY) != HISTORY_RULES:
            # Hidden by the older, stricter scan (a slow search, 0 hits or an
            # indefinite-length reply counted as a failure): shown again, and
            # the next scans decide. A hide by hand stays.
            for h in self.data.values():
                if isinstance(h, dict):
                    h.pop("auto", None)
                    h["fails"] = 0
            self.data[RULES_KEY] = HISTORY_RULES

    def get(self, key: str) -> dict:
        return self.data.get(key, {})

    def record(self, result: "ScanResult") -> None:
        h = self.data.setdefault(result.key, {})
        h.update(status=result.status, when=int(time.time()), connect_ms=result.connect_ms,
                 query_ms=result.query_ms, port=result.port)
        if result.alive:
            h["fails"] = 0
            h.pop("auto", None)
        else:
            h["fails"] = int(h.get("fails", 0)) + 1
            if h["fails"] >= FAILS_TO_BLACKLIST:
                h["auto"] = True

    def blacklisted(self, key: str) -> bool:
        h = self.get(key)
        return bool(h.get("manual") or h.get("auto"))

    def set_manual(self, key: str, on: bool) -> None:
        h = self.data.setdefault(key, {})
        if on:
            h["manual"] = True
        else:
            h.pop("manual", None)
            h.pop("auto", None)
            h["fails"] = 0

    def save(self) -> None:
        try:
            _write_private(self.path, json.dumps(self.data, indent=1, sort_keys=True) + "\n")
        except OSError:
            pass


# ----------------------------------------------------------------------
# BER (the subset Z39.50 needs)
# ----------------------------------------------------------------------
def ber_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def ber_tag(cls: int, constructed: bool, number: int) -> bytes:
    first = cls | (0x20 if constructed else 0)
    if number < 31:
        return bytes([first | number])
    out = [number & 0x7F]
    number >>= 7
    while number:
        out.insert(0, 0x80 | (number & 0x7F))
        number >>= 7
    return bytes([first | 0x1F] + out)


CTX = 0x80
UNIVERSAL = 0x00


def tlv(number: int, value: bytes, constructed: bool = False, cls: int = CTX) -> bytes:
    return ber_tag(cls, constructed, number) + ber_len(len(value)) + value


def ber_int(n: int) -> bytes:
    return n.to_bytes(max(1, (n.bit_length() + 8) // 8), "big", signed=True)


def ber_oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.split(".")]
    out = bytearray([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.insert(0, 0x80 | (p & 0x7F))
            p >>= 7
        out += bytes(chunk)
    return bytes(out)


def _ber_node(data: bytes, pos: int, end: int) -> tuple[tuple, int]:
    """One TLV at pos: ((class, number, constructed, value), next pos).
    Definite and indefinite (constructed, ended by 00 00) lengths."""
    first = data[pos]
    pos += 1
    cls, constructed, number = first & 0xC0, bool(first & 0x20), first & 0x1F
    if number == 0x1F:
        number = 0
        while True:
            b = data[pos]
            pos += 1
            number = (number << 7) | (b & 0x7F)
            if not b & 0x80:
                break
    length = data[pos]
    pos += 1
    if length == 0x80:
        # Indefinite length (some Z39.50 servers send it): children up to 00 00.
        if not constructed:
            raise ValueError("indefinite length on a primitive BER value")
        kids = []
        while True:
            if pos + 2 > end:
                raise ValueError("truncated BER")
            if data[pos] == 0 and data[pos + 1] == 0:
                return (cls, number, True, kids), pos + 2
            node, pos = _ber_node(data, pos, end)
            kids.append(node)
    if length & 0x80:
        k = length & 0x7F
        length = int.from_bytes(data[pos:pos + k], "big")
        pos += k
    if pos + length > end:
        raise ValueError("truncated BER")
    value = data[pos:pos + length]
    return (cls, number, constructed, ber_decode(data, pos, pos + length) if constructed else value), pos + length


def ber_decode(data: bytes, pos: int = 0, end: int | None = None) -> list[tuple[int, int, bool, bytes | list]]:
    """[(class, number, constructed, value)], constructed values decoded too."""
    end = len(data) if end is None else end
    out = []
    while pos < end:
        node, pos = _ber_node(data, pos, end)
        out.append(node)
    return out


def ber_top(nodes, number: int, cls: int = CTX):
    """The value of a direct child with this tag (not one nested deeper)."""
    return next((v for c, n, _k, v in nodes if c == cls and n == number), None)


def ber_find(nodes, number: int, cls: int = CTX):
    """First node with this tag anywhere in the tree."""
    for c, n, constructed, value in nodes:
        if c == cls and n == number:
            return value
        if constructed:
            hit = ber_find(value, number, cls)
            if hit is not None:
                return hit
    return None


def ber_octets(nodes) -> list[bytes]:
    """Every primitive value of the tree, longest first (records hide in
    EXTERNALs nested a few levels down)."""
    out = []
    for _c, _n, constructed, value in nodes:
        if constructed:
            out += ber_octets(value)
        else:
            out.append(value)
    return sorted(out, key=len, reverse=True)


async def _read_tlv(reader: asyncio.StreamReader, budget: list[int], head: bytes = b"") -> bytes:
    head = head or await reader.readexactly(1)
    if head[0] & 0x1F == 0x1F:
        while True:
            b = await reader.readexactly(1)
            head += b
            if not b[0] & 0x80:
                break
    lb = await reader.readexactly(1)
    head += lb
    length = lb[0]
    if length == 0x80:
        # Indefinite length: read the children up to the 00 00 end mark.
        while True:
            tag = await reader.readexactly(1)
            if tag == b"\x00":
                end = await reader.readexactly(1)
                if end != b"\x00":
                    raise ValueError("bad BER end-of-contents")
                return head + tag + end
            head += await _read_tlv(reader, budget, tag)
    if length & 0x80:
        extra = await reader.readexactly(length & 0x7F)
        head += extra
        length = int.from_bytes(extra, "big")
    budget[0] -= length
    if length > 8_000_000 or budget[0] < 0:
        raise ValueError("APDU too large")
    return head + await reader.readexactly(length)


async def read_pdu(reader: asyncio.StreamReader) -> bytes:
    """One whole APDU from the socket (definite or indefinite length)."""
    return await _read_tlv(reader, [8_000_000])


OID_BIB1 = "1.2.840.10003.3.1"
OID_USMARC = "1.2.840.10003.5.10"
OID_UNIMARC = "1.2.840.10003.5.1"
SYNTAX_OID = {"USMARC": OID_USMARC, "MARC21": OID_USMARC, "UNIMARC": OID_UNIMARC,
              "NORMARC": "1.2.840.10003.5.12", "DANMARC": "1.2.840.10003.5.14"}


def init_request(user: str = "", password: str = "") -> bytes:
    body = (tlv(3, b"\x00\xe0")                    # protocolVersion 1, 2, 3
            + tlv(4, b"\x00\xe0")                  # options: search, present, delSet
            + tlv(5, ber_int(1_048_576)) + tlv(6, ber_int(1_048_576)))
    if user:
        body += tlv(7, tlv(16, tlv(1, user.encode()) + tlv(2, password.encode()), True, UNIVERSAL), True)
    body += tlv(110, b"KEI") + tlv(111, b"koha.nexus") + tlv(112, b"1")
    return tlv(20, body, True)


def search_request(db: str, term: str, use: int = 4) -> bytes:
    attr = tlv(16, tlv(120, ber_int(1)) + tlv(121, ber_int(use)), True, UNIVERSAL)
    apt = tlv(102, tlv(44, attr, True) + tlv(45, term.encode()), True)
    rpn = tlv(6, ber_oid(OID_BIB1), cls=UNIVERSAL) + tlv(0, apt, True)
    body = (tlv(13, ber_int(0)) + tlv(14, ber_int(1)) + tlv(15, ber_int(0)) + tlv(16, b"\xff")
            + tlv(17, b"default") + tlv(18, tlv(105, db.encode()), True) + tlv(21, tlv(1, rpn, True), True))
    return tlv(22, body, True)


def present_request(syntax: str = "USMARC") -> bytes:
    body = (tlv(31, b"default") + tlv(30, ber_int(1)) + tlv(29, ber_int(1))
            + tlv(19, tlv(0, b"F"), True)
            + tlv(104, ber_oid(SYNTAX_OID.get(syntax.upper(), OID_USMARC))))
    return tlv(24, body, True)


def _int(v) -> int:
    return int.from_bytes(v, "big", signed=True) if isinstance(v, bytes) and v else 0


# ----------------------------------------------------------------------
# MARC
# ----------------------------------------------------------------------
def marc_frame_ok(rec: bytes) -> bool:
    """An ISO 2709 record: the length and base address in the leader are
    digits and match, the directory is whole 12-digit entries ending in a
    field terminator, and the record ends in a record terminator."""
    if len(rec) < 26 or not rec[:5].isdigit() or not rec[12:17].isdigit():
        return False
    if int(rec[:5]) != len(rec) or rec[-1] != 0x1D:
        return False
    base = int(rec[12:17])
    if base < 37 or base >= len(rec) or rec[base - 1] != 0x1E or (base - 25) % 12:
        return False
    directory = rec[24:base - 1]
    for i in range(0, len(directory), 12):
        entry = directory[i:i + 12]
        if not entry.isdigit():
            return False
        size, start = int(entry[3:7]), int(entry[7:12])
        if base + start + size > len(rec) - 1 or rec[base + start + size - 1] != 0x1E:
            return False
    return True


def marc_title(rec: bytes, unimarc: bool = False) -> str:
    """$a of 245 (200 in UNIMARC), for the scan's report."""
    try:
        base = int(rec[12:17])
        directory = rec[24:base - 1]
        for i in range(0, len(directory), 12):
            entry = directory[i:i + 12]
            if entry[:3] in (b"245", b"200") and (entry[:3] == b"200") == unimarc:
                size, start = int(entry[3:7]), int(entry[7:12])
                data = rec[base + start:base + start + size - 1]
                for sub in data.split(b"\x1f")[1:]:
                    if sub[:1] == b"a":
                        return sub[1:].decode("utf-8", "replace").strip(" /:;,.")
    except (ValueError, IndexError):
        pass
    return ""


def marcxml_ok(text: str) -> bool:
    return bool(re.search(r"<(\w+:)?leader>[^<]{20,}</(\w+:)?leader>", text)
                and re.search(r"<(\w+:)?(controlfield|datafield)\b", text))


# ----------------------------------------------------------------------
# The scan
# ----------------------------------------------------------------------
STATUS_ORDER = ("ok", "empty", "no_marc", "login", "tcp", "dead")
STATUS_TEXT = {
    "ok": "Working: returned a valid MARC record",
    "empty": "Answers, but found no test record",
    "no_marc": "Answers, but the record is not valid MARC",
    "login": "Refused the connection (login needed?)",
    "tcp": "The port is open but the server does not speak the protocol",
    "dead": "No answer on any port",
}

STATUS_SHORT = {"ok": "Working", "empty": "No test record", "no_marc": "Not MARC", "login": "Login?",
                "tcp": "Wrong protocol", "dead": "No answer"}


@dataclass
class ScanResult:
    key: str
    status: str = "dead"
    port: int = 0                # the port that answered
    connect_ms: int | None = None
    query_ms: int | None = None
    hits: int = 0
    title: str = ""
    detail: str = ""
    answered: bool = False       # the server spoke the protocol (Init or an SRU response)

    @property
    def alive(self) -> bool:
        return self.status in ("ok", "empty", "no_marc", "login")

    def settle(self, why: str) -> "ScanResult":
        """A probe cut short: a server that already answered the protocol is
        working (it may just be slow, or have nothing for the test words);
        one that never did is not."""
        if self.answered and not self.alive:
            self.status = "empty"
        if why:
            self.detail = (self.detail + "; " if self.detail else "") + why
        return self


async def _connect(host: str, port: int, timeout: float):
    t0 = time.monotonic()
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    return reader, writer, int((time.monotonic() - t0) * 1000)


async def find_port(host: str, port: int, timeout: float = CONNECT_TIMEOUT) -> tuple[int, int] | None:
    """(port, connect ms) of the listed port, else the first of 210, 2100
    and 2210 that accepts a connection; all tried at once."""
    ports = [port] + [p for p in ALT_PORTS if p != port]

    async def one(p: int):
        try:
            _r, w, ms = await _connect(host, p, timeout)
        except (OSError, asyncio.TimeoutError):
            return None
        w.close()
        return ms
    found = await asyncio.gather(*(one(p) for p in ports))
    for p, ms in zip(ports, found):
        if ms is not None:
            return p, ms
    return None


async def probe_z3950(target: Target, port: int, timeout: float = QUERY_TIMEOUT,
                      res: ScanResult | None = None) -> ScanResult:
    """Init, then a title search for each probe word until one has hits, then
    Present of the first record in the target's syntax.

    A server that accepts the Init is working, whatever comes after: 0 hits,
    a slow or failed search, or a Present refused (record out of range...)
    only change what the scan reports, never hide it."""
    res = res or ScanResult(target.key)
    res.status, res.port = "tcp", port
    try:
        reader, writer, res.connect_ms = await _connect(target.host, port, CONNECT_TIMEOUT)
    except (OSError, asyncio.TimeoutError):
        res.status = "dead"
        return res
    t0 = time.monotonic()

    async def ask(pdu: bytes):
        writer.write(pdu)
        await writer.drain()
        return ber_decode(await asyncio.wait_for(read_pdu(reader), timeout))
    try:
        resp = await ask(init_request(target.user, target.password))
        if not resp or resp[0][1] != 21 or not resp[0][2]:
            res.detail = "no Init response"
            return res
        res.answered = True
        # result [12] is a direct child of the InitResponse; only an explicit
        # false refuses (a nested [12] or a missing one is not a refusal).
        if ber_top(resp[0][3], 12) == b"\x00":
            res.status, res.detail = "login", "Init refused"
            return res
        res.status = "empty"
        for term in PROBE_TERMS:
            resp = await ask(search_request(target.db, term))
            if not resp or resp[0][1] != 23 or not resp[0][2]:
                res.detail = "no Search response"
                return res
            res.hits = _int(ber_top(resp[0][3], 23))
            if res.hits:
                break
        res.query_ms = int((time.monotonic() - t0) * 1000)
        if not res.hits:
            return res
        resp = await ask(present_request(target.syntax))
        res.query_ms = int((time.monotonic() - t0) * 1000)
        if not resp or resp[0][1] != 25 or not resp[0][2]:
            res.detail = "no Present response"
            return res
        for blob in ber_octets(resp[0][3]):
            if marc_frame_ok(blob):
                res.status = "ok"
                res.title = marc_title(blob, target.syntax.upper() == "UNIMARC")
                return res
        if ber_top(resp[0][3], 28) is None or ber_find(resp[0][3], 130) is not None:
            # No records, or a diagnostic (present out of range...): the
            # server answered, it just did not hand over the test record.
            res.detail = "Present returned no record"
            return res
        res.status, res.detail = "no_marc", "the record is not an ISO 2709 frame"
        return res
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError, OSError, ValueError,
            IndexError) as e:
        return res.settle(type(e).__name__)
    finally:
        writer.close()


def sru_url(target: Target, query: str) -> str:
    scheme = "https" if target.port == 443 else "http"
    port = "" if target.port in (80, 443) else f":{target.port}"
    params = {"version": "1.1", "operation": "searchRetrieve", "query": query, "maximumRecords": "1",
              "recordSchema": target.schema or "marcxml"}
    return f"{scheme}://{target.host}{port}/{target.db.strip('/')}?{urllib.parse.urlencode(params)}"


def _sru_get(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "koha.nexus-panel"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # noqa: S310 (http/https only)
        return resp.read(2_000_000).decode("utf-8", "replace")


async def probe_sru(target: Target, port: int, timeout: float = QUERY_TIMEOUT, get=_sru_get,
                    res: ScanResult | None = None) -> ScanResult:
    """A searchRetrieve for each probe word until one has hits. Any SRU
    response counts as working, a diagnostic or 0 hits included."""
    res = res or ScanResult(target.key)
    res.status, res.port = "tcp", port
    t0 = time.monotonic()
    probe = replace(target, port=port)
    for term in PROBE_TERMS:
        try:
            text = await asyncio.wait_for(asyncio.to_thread(get, sru_url(probe, term), timeout), timeout + 1)
        except (OSError, asyncio.TimeoutError, ValueError) as e:
            code = getattr(e, "code", 0)
            if code in (401, 403):
                res.status = "login"
            res.detail = f"HTTP {code}" if code else type(e).__name__
            return res.settle("") if res.answered and not code else res
        m = re.search(r"<(?:\w+:)?numberOfRecords>\s*(\d+)", text)
        if not m:
            if re.search(r"<(?:\w+:)?(searchRetrieveResponse|explainResponse|diagnostic)\b", text):
                res.answered, res.status = True, "empty"
                res.query_ms = int((time.monotonic() - t0) * 1000)
                d = re.search(r"<(?:\w+:)?message>([^<]+)<", text)
                res.detail = f"SRU diagnostic: {d.group(1).strip()}" if d else "SRU diagnostic"
            else:
                res.detail = "not an SRU response"
            return res
        res.answered = True
        res.hits = int(m.group(1))
        if res.hits:
            break
    res.query_ms = int((time.monotonic() - t0) * 1000)
    if not res.hits:
        res.status = "empty"
    elif marcxml_ok(text):
        res.status = "ok"
        m = re.search(r'tag="(245|200)"[^>]*>.*?code="a"[^>]*>([^<]+)<', text, re.S)
        res.title = m.group(2).strip(" /:;,.") if m else ""
    else:
        res.status, res.detail = "no_marc", "the record is not MARCXML"
    return res


async def scan_one(target: Target, res: ScanResult | None = None) -> ScanResult:
    """res, when given, is filled in as the probe goes, so a caller that
    times the probe out still knows how far it got."""
    res = res or ScanResult(target.key)
    found = await find_port(target.host, target.port)
    if not found:
        res.status, res.detail = "dead", "no port answered"
        return res
    port, ms = found
    probe = probe_sru if target.kind == "sru" else probe_z3950
    res = await probe(target, port, res=res)
    res.connect_ms = res.connect_ms or ms
    if port != target.port:
        res.detail = (res.detail + "; " if res.detail else "") + f"answers on port {port}"
    return res


async def scan(targets: list[Target], on_result=None, concurrency: int = 16) -> list[ScanResult]:
    """Every target at once (at most `concurrency` connections); on_result is
    called as each one ends."""
    sem = asyncio.Semaphore(concurrency)

    async def one(t: Target) -> ScanResult:
        async with sem:
            r = ScanResult(t.key)
            try:
                r = await asyncio.wait_for(scan_one(t, r), CONNECT_TIMEOUT + 3 * QUERY_TIMEOUT)
            except asyncio.TimeoutError:
                if r.status == "dead" and not r.answered:
                    r.status = "tcp"
                r.settle("the probe took too long")
        if on_result:
            on_result(t, r)
        return r
    return list(await asyncio.gather(*(one(t) for t in targets)))


def rank(results: list[ScanResult]) -> list[ScanResult]:
    """Best first: working servers by query time, then the others by how
    close they came."""
    def score(r: ScanResult):
        return (STATUS_ORDER.index(r.status), r.query_ms if r.query_ms is not None else 10**9,
                r.connect_ms if r.connect_ms is not None else 10**9)
    return sorted(results, key=score)


def koha_ranks(targets: list[Target], history: History) -> dict[str, int]:
    """Koha's display rank (1 = first) for targets about to be added: the
    fastest working one first, never-scanned ones after them."""
    def score(t: Target):
        h = history.get(t.key)
        status = h.get("status", "")
        known = STATUS_ORDER.index(status) if status in STATUS_ORDER else len(STATUS_ORDER)
        return (known, h.get("query_ms") or 10**9, t.name.lower())
    return {t.key: i for i, t in enumerate(sorted(targets, key=score), 1)}
