"""The catalogues the gateway serves, one per /sru/{id}, read from targets.json
(the list the VPS gateway served, kept so the 72 Koha rows keep their ids).

Each entry has an id (the part after /sru/), a name, a group and a kind:

  z3950     a Z39.50 server: host, port, db, syntax (USMARC/MARC21), encoding
  sru       an SRU server: url, version, schema, indexes
  zeus      Catálogo Zeus instances, and
  pergamum  Rede Pergamum: harvested on the build server, so here they answer
            from static.db only (a client never scrapes)
  missing   no address known: static.db only

"static" lists the static.db source ids that belong to the target (default:
its own id), so a harvest whose "fonte" gave another id still lands on the
right row. Only z3950 and sru targets whose status is not "broken" are
searched live.

A login never goes in the file: NEXUS_GATEWAY_LOGIN_<ID>=user:password (id
in capitals, "-" as "_") supplies one from the environment.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("zeus", "pergamum", "z3950", "sru", "missing")
STATUSES = ("verified", "untested", "broken", "missing")
GROUPS = {
    "national": "Bibliotecas Nacionais e Órgãos Oficiais",
    "br_universities": "Universidades Brasileiras (Rede Federal e Estaduais)",
    "intl_universities": "Universidades Internacionais",
    "specialized": "Especializados e Catálogos Coletivos",
}
MARC21_SYNTAXES = ("USMARC", "MARC21")
DEFAULT_INDEXES = {"isbn": "bath.isbn", "title": "dc.title", "author": "dc.creator",
                   "keywords": "cql.serverChoice"}
UNION = "_union"
AUTH_UNION = "_union-aut"       # the authority headings, for Koha's authority search
_ID = re.compile(r"[a-z0-9][a-z0-9_\-]*")


class TargetError(ValueError):
    """targets.json holds an entry the gateway cannot serve."""


@dataclass(frozen=True)
class Target:
    id: str
    name: str
    kind: str
    group: str = "specialized"
    host: str = ""
    port: int = 0
    db: str = ""
    syntax: str = "USMARC"
    encoding: str = "utf8"
    url: str = ""
    version: str = "1.1"
    schema: str = "marcxml"
    indexes: dict = field(default_factory=dict)
    static: tuple[str, ...] = ()
    user: str = ""
    password: str = ""
    status: str = "untested"
    note: str = ""

    @property
    def live(self) -> bool:
        return self.kind in ("z3950", "sru") and self.status != "broken"

    def index(self, kind: str) -> str:
        return {**DEFAULT_INDEXES, **self.indexes}.get(kind, DEFAULT_INDEXES["keywords"])


def _login(tid: str) -> tuple[str, str]:
    raw = os.environ.get(f"NEXUS_GATEWAY_LOGIN_{tid.upper().replace('-', '_')}", "")
    user, _, password = raw.partition(":")
    return user, password


def make_target(raw: dict) -> Target:
    tid = str(raw.get("id", "")).strip().lower()
    if not _ID.fullmatch(tid):
        raise TargetError(f"bad target id {raw.get('id')!r}")
    kind = str(raw.get("kind", "missing")).strip().lower()
    if kind not in KINDS:
        raise TargetError(f"{tid}: unknown kind {kind!r}")
    static = raw.get("static") or [tid]
    if isinstance(static, str):
        static = [static]
    user, password = _login(tid)
    t = Target(
        id=tid, name=str(raw.get("name") or tid), kind=kind,
        group=str(raw.get("group") or "specialized").strip().lower(),
        host=str(raw.get("host", "")).strip(), port=int(raw.get("port") or 0),
        db=str(raw.get("db", "")).strip(), syntax=str(raw.get("syntax", "USMARC")).strip().upper(),
        encoding=str(raw.get("encoding", "utf8")).strip().lower(),
        url=str(raw.get("url", "")).strip(), version=str(raw.get("version", "1.1")).strip(),
        schema=str(raw.get("schema", "marcxml")).strip(), indexes=dict(raw.get("indexes") or {}),
        static=tuple(str(s).strip().lower() for s in static), user=user, password=password,
        status=str(raw.get("status") or ("missing" if kind == "missing" else "untested")).strip().lower(),
        note=str(raw.get("note", "")),
    )
    if t.group not in GROUPS:
        raise TargetError(f"{tid}: unknown group {t.group!r}")
    if t.status not in STATUSES:
        raise TargetError(f"{tid}: unknown status {t.status!r}")
    if (t.status == "missing") != (kind == "missing"):
        raise TargetError(f"{tid}: status missing goes with kind missing, and only with it")
    if kind == "z3950":
        if not (t.host and t.port and t.db):
            raise TargetError(f"{tid}: a z3950 target needs host, port and db")
        if t.syntax not in MARC21_SYNTAXES:
            raise TargetError(f"{tid}: syntax {t.syntax} is not served, only USMARC/MARC21")
    if kind == "sru" and not re.match(r"https?://", t.url):
        raise TargetError(f"{tid}: an sru target needs an http(s) url")
    return t


def load(path: Path) -> dict[str, Target]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Target] = {}
    for raw in data.get("targets", []):
        t = make_target(raw)
        if t.id in out or t.id == UNION:
            raise TargetError(f"{t.id}: listed twice or reserved")
        out[t.id] = t
    return out
