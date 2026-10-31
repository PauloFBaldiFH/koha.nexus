"""The catalogues the gateway serves, one per /sru/{id}, read from targets.json
(the list the VPS gateway served, kept so the 72 Koha rows keep their ids).

Each entry has an id (the part after /sru/), a name, a group and a kind:

  z3950     a Z39.50 server: host, port, db, syntax (USMARC/MARC21), encoding
  sru       an SRU server: url, version, schema, indexes
  zeus      a catalogue searched through Catálogo Zeus (target_index): live
            only on the server gateway (NEXUS_GATEWAY_ZEUS_URL set, zeus.py),
            static.db only elsewhere
  pergamum  Rede Pergamum: live only on the server gateway
            (NEXUS_GATEWAY_PERGAMUM_URL set, pergamum.py), static.db only
            elsewhere (a library's own gateway never scrapes)
  missing   no address known: static.db only

"target_index" is the n of targets[n] on Catálogo Zeus's search form. A
z3950 or sru target may carry one too: the catalogue is then also one of
the Zeus catalogues /sru/_union asks on the server gateway (USP, the
Senado's RVBI), a second road when its own server is slow.

"zeus_priority" (1, 2, ...) orders the Zeus catalogues in that union
request: the stable ones first (USP answered every ISBN and title search in
Paulo's 2026-10-31 tests), unranked ones after them. "zeus_unstable": true
marks a catalogue whose node often times out inside Zeus (the BN, targets[0]):
it is asked on its own, after the others, so its timeout never costs the
records the stable catalogues found.

"static" lists the static.db source ids that belong to the target (default:
its own id), so a harvest whose "fonte" gave another id still lands on the
right row. "country" is the ISO 3166 code the panel shows as a flag. Only z3950 and sru targets whose status is not "broken" are
searched live.

"local_first" (1, 2, ...) marks the catalogues static.db holds nearly whole
(UNESP, UFPR, UNIFESP, UnB, UFU: 99% of its records, Paulo 2026-10-24):
their Koha rows come first, in that order, and are ticked; on-demand
enrichment searches their static.db records before any server; a library's
own row for the same institution (its host is one of "legacy_hosts" or a
subdomain of one) moves behind them, unticked, kept (koha_sql.py).

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
    country: str = ""
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
    local_first: int = 0
    legacy_hosts: tuple[str, ...] = ()
    target_index: int = -1          # zeus: the n of targets[n] on Zeus's search form
    zeus_priority: int = 0          # order in the Zeus union request (1 first; 0 = after the ranked ones)
    zeus_unstable: bool = False     # asked alone and last in the Zeus union request

    @property
    def on_zeus(self) -> bool:
        """One of the catalogues /sru/_union asks through Zeus: a zeus
        target, or a z3950/sru one that names its targets[n]."""
        return self.status != "broken" and (self.kind == "zeus" or self.target_index >= 0)

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
        country=str(raw.get("country", "")).strip().upper()[:2],
        host=str(raw.get("host", "")).strip(), port=int(raw.get("port") or 0),
        db=str(raw.get("db", "")).strip(), syntax=str(raw.get("syntax", "USMARC")).strip().upper(),
        encoding=str(raw.get("encoding", "utf8")).strip().lower(),
        url=str(raw.get("url", "")).strip(), version=str(raw.get("version", "1.1")).strip(),
        schema=str(raw.get("schema", "marcxml")).strip(), indexes=dict(raw.get("indexes") or {}),
        static=tuple(str(s).strip().lower() for s in static), user=user, password=password,
        status=str(raw.get("status") or ("missing" if kind == "missing" else "untested")).strip().lower(),
        note=str(raw.get("note", "")),
        local_first=int(raw.get("local_first") or 0),
        legacy_hosts=tuple(str(h).strip().lower() for h in raw.get("legacy_hosts") or ()),
        target_index=int(raw["target_index"]) if raw.get("target_index") is not None else -1,
        zeus_priority=int(raw.get("zeus_priority") or 0),
        zeus_unstable=bool(raw.get("zeus_unstable", False)),
    )
    if t.zeus_priority < 0:
        raise TargetError(f"{tid}: zeus_priority is a position, 1 or more")
    if (t.zeus_priority or t.zeus_unstable) and not (kind == "zeus" or t.target_index >= 0):
        raise TargetError(f"{tid}: zeus_priority/zeus_unstable need kind zeus or a target_index")
    if t.local_first < 0:
        raise TargetError(f"{tid}: local_first is a position, 1 or more")
    if any(not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", h) for h in t.legacy_hosts):
        raise TargetError(f"{tid}: legacy_hosts are host names (unesp.br)")
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
    firsts = [t.local_first for t in out.values() if t.local_first]
    if len(firsts) != len(set(firsts)):
        raise TargetError("two targets share a local_first position")
    return out


def local_first(table: dict[str, Target]) -> list[Target]:
    """The local-first catalogues, in their order."""
    return sorted((t for t in table.values() if t.local_first), key=lambda t: t.local_first)


def local_first_sources(table: dict[str, Target]) -> dict[str, str]:
    """{static.db source id: target id} of the local-first catalogues."""
    return {s: t.id for t in local_first(table) for s in t.static}
