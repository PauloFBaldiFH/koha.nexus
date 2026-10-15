"""The catalogues the gateway serves, one per /sru/{id}, read from targets.json.

Each entry has an id (the part after /sru/), a name and a kind:

  zeus      Catálogo Zeus, BU/UFSC (the zeus_sru client, ZEUS_SRU_* settings)
  pergamum  Rede Pergamum, CRP (the pergamum_sru client, PERGAMUM_SRU_* settings)
  z3950     a Z39.50 server: host, port, db, syntax (USMARC/MARC21), encoding
  sru       an SRU server: url, version, schema, indexes
  missing   no address known yet: searches answer an SRU diagnostic saying so

Each entry also has a status, what is known about it today:

  verified  searched live and returned MARC records
  untested  has an address that nobody has searched through the gateway yet
  broken    has an address that does not answer (kept until a new one is found)
  missing   no address known yet (kind "missing")

A login never goes in the file: SRU_GATEWAY_LOGIN_<ID>=user:password (id in
capitals) supplies one from the environment.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("zeus", "pergamum", "z3950", "sru", "missing")
STATUSES = ("verified", "untested", "broken", "missing")
MARC21_SYNTAXES = ("USMARC", "MARC21")
DEFAULT_INDEXES = {"isbn": "bath.isbn", "title": "dc.title", "author": "dc.creator",
                   "any": "cql.serverChoice"}
_ID = re.compile(r"[a-z0-9][a-z0-9_\-]*")


class TargetError(ValueError):
    """targets.json holds an entry the gateway cannot serve."""


@dataclass(frozen=True)
class Target:
    id: str
    name: str
    kind: str
    host: str = ""
    port: int = 0
    db: str = ""
    syntax: str = "USMARC"
    encoding: str = "utf8"
    url: str = ""
    version: str = "1.1"
    schema: str = "marcxml"
    indexes: dict = field(default_factory=dict)
    user: str = ""
    password: str = ""
    status: str = "untested"
    note: str = ""
    source: str = ""
    target_index: int = 0

    @property
    def configured(self) -> bool:
        return self.kind != "missing"

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    def index(self, kind: str) -> str:
        return {**DEFAULT_INDEXES, **self.indexes}.get(kind, DEFAULT_INDEXES["any"])


def _login(tid: str) -> tuple[str, str]:
    raw = os.environ.get(f"SRU_GATEWAY_LOGIN_{tid.upper().replace('-', '_')}", "")
    user, _, password = raw.partition(":")
    return user, password


def make_target(raw: dict) -> Target:
    tid = str(raw.get("id", "")).strip().lower()
    if not _ID.fullmatch(tid):
        raise TargetError(f"bad target id {raw.get('id')!r}")
    kind = str(raw.get("kind", "missing")).strip().lower()
    if kind not in KINDS:
        raise TargetError(f"{tid}: unknown kind {kind!r}")
    t = Target(
        id=tid, name=str(raw.get("name") or tid), kind=kind,
        host=str(raw.get("host", "")).strip(), port=int(raw.get("port") or 0),
        db=str(raw.get("db", "")).strip(), syntax=str(raw.get("syntax", "USMARC")).strip().upper(),
        encoding=str(raw.get("encoding", "utf8")).strip().lower(),
        url=str(raw.get("url", "")).strip(), version=str(raw.get("version", "1.1")).strip(),
        schema=str(raw.get("schema", "marcxml")).strip(), indexes=dict(raw.get("indexes") or {}),
        status=str(raw.get("status") or ("missing" if kind == "missing" else "untested")).strip().lower(),
        note=str(raw.get("note", "")), source=str(raw.get("source", "")),
        target_index=int(raw.get("target_index") or 0),
        **dict(zip(("user", "password"), _login(tid))),
    )
    if t.status not in STATUSES:
        raise TargetError(f"{tid}: unknown status {t.status!r}")
    if (t.status == "missing") != (kind == "missing"):
        raise TargetError(f"{tid}: status missing goes with kind missing, and only with it")
    if kind == "z3950":
        if not (t.host and t.port and t.db):
            raise TargetError(f"{tid}: a z3950 target needs host, port and db")
        if t.syntax not in MARC21_SYNTAXES:
            # Koha's rows say MARC21; UNIMARC would need a conversion this gateway lacks.
            raise TargetError(f"{tid}: syntax {t.syntax} is not served, only USMARC/MARC21")
    if kind == "sru" and not re.match(r"https?://", t.url):
        raise TargetError(f"{tid}: an sru target needs an http(s) url")
    return t


def load(path: Path) -> dict[str, Target]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Target] = {}
    for raw in data.get("targets", []):
        t = make_target(raw)
        if t.id in out:
            raise TargetError(f"{t.id}: listed twice")
        out[t.id] = t
    return out
