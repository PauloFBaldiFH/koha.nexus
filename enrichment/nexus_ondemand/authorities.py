"""On-demand authority enrichment ("Enrich & standardize authorities").

The heading matcher is the batch worker's (nexus_enrich.authority through
nexus_jobs.worker.AuthMatcher): each name and subject heading of a record
is matched with the library's own Koha authorities, then static.db's
headings when the library has the file. What is still unmatched is asked
of the direct authority servers of z3950_direct.json (recordtype
"authority"; the UNIMARC ones are passed over, as for records), through
the same dispatcher as the bibliographic records: limiter slots, each
host's pace, breakers, the idle servers first, records several at once,
the hold while the network is down.

One heading, one search: its form (without dates) as a personal,
corporate or meeting name or a subject (Bib-1 use 1, 2, 3, 21), any word
(use 1016) for a server that refuses that. A search stops at the first
wave that found the heading itself. The records found are matched as
static.db's headings are (FoundHeadings), with these rules:
- a Brazilian server first, then the others in the list's order;
- subjects only from Brazilian servers (a Portuguese catalogue keeps
  Portuguese subjects; design decision 9);
- the new authority cites the server (670) and keeps the record's
  variants (4XX), LCCN and URI.

Every heading's answer is kept for the job (and in learned.db), so the
same author in thousands of records is asked once.
"""

from __future__ import annotations

import asyncio
import re

from nexus_enrich import marc
from nexus_enrich.authority import (NAME_KINDS, SUBJECT_KINDS, Match, StaticHeading, _strip_dates, dates_fit,
                                    kind_of)
from nexus_enrich.headings import Heading, from_field, of_authority
from nexus_enrich.normalize import fold, similarity
from nexus_gateway.z3950 import Term

from .dispatch import Dispatcher, Result
from .plan import Step
from .targets import Catalog, Target

USE_ANY = 1016
USE = {"personal": 1, "corporate": 2, "meeting": 3, "topical": 21, "geographic": 21, "genre": 21}
SEARCHED = NAME_KINDS + SUBJECT_KINDS
MAX_SERVERS = 6
LOC_HOSTS = ("loc.gov",)


def step_for(h: Heading) -> Step:
    """The search of heading H: its form, without dates."""
    text = h.heading.replace(h.dates, "") if h.dates else h.heading
    text = re.sub(r"[\"“”]", "", text).strip(" ,.") or h.heading
    return Step(f"auth-{h.kind}", Term(text, USE[h.kind]), Term(text, USE_ANY))


def tier_of(t: Target | None) -> int:
    """Brazilian 1, Library of Congress 2, others 3 (as static.db's tiers;
    no direct server is the Biblioteca Nacional's, tier 0)."""
    if t is None:
        return 3
    if t.country == "BR":
        return 1
    return 2 if any(t.address.host.endswith(h) for h in LOC_HOSTS) else 3


def rows_of(res: Result, catalog: Catalog) -> list[StaticHeading]:
    """The authority records RES found, as headings (StaticHeading rows)."""
    out = []
    for n, f in enumerate(res.found, 1):
        entry = of_authority(f.record)
        if entry is None:
            continue
        tid = f.source.split(":", 1)[1] if ":" in f.source else f.source
        t = catalog.targets.get(tid)
        status = f.record.control("008")[33:34]
        h = entry.heading
        out.append(StaticHeading(n, h.kind, h.heading, h.key, h.dates, h.thesaurus, entry.variants, f.source,
                                 entry.source_id or f.record.control("001"), entry.lccn, entry.uri, 0,
                                 int(status in ("b", "d")), tier_of(t)))
    return out


class FoundHeadings:
    """The headings found on the servers for one heading, with
    StaticHeadings' methods (exact, variant, fuzzy) so the batch matcher
    takes them as it takes static.db's."""

    def __init__(self, rows: list[StaticHeading], catalog: Catalog):
        self.rows = rows
        self.sources = {r.source: {"name": _name(catalog, r.source)} for r in rows}

    def _usable(self, rows: list[StaticHeading], kind: str) -> list[StaticHeading]:
        rows = [r for r in rows if r.kind == kind]
        if kind in SUBJECT_KINDS:
            rows = [r for r in rows if r.tier <= 1]
        return sorted(rows, key=lambda r: (r.tier, r.preliminary, r.id))

    def exact(self, kind: str, key: str) -> list[StaticHeading]:
        return self._usable([r for r in self.rows if r.key == key], kind)

    def variant(self, h: Heading) -> list[StaticHeading]:
        if not h.key:
            return []
        wanted = {h.key, fold(h.heading)}
        return self._usable([r for r in self.rows
                             if any(fold(v) in wanted or _strip_dates(fold(v)) == h.key for v in r.variants)], h.kind)

    def fuzzy(self, h: Heading, minimum: float):
        out = [(similarity(h.key, r.key), r) for r in self._usable(self.rows, h.kind)
               if r.key != h.key and dates_fit(h.dates, r.dates)]
        return sorted([x for x in out if x[0] >= minimum], key=lambda x: (-x[0], x[1].tier))


def _name(catalog: Catalog, source: str) -> str:
    tid = source.split(":", 1)[1] if ":" in source else source
    t = catalog.targets.get(tid)
    return t.name if t is not None else source


class Searcher:
    """Live searches of headings for one job: each (kind, key, dates) asked
    once, the searches of records in flight joined."""

    def __init__(self, dispatcher: Dispatcher, catalog: Catalog):
        self.dispatcher, self.catalog = dispatcher, catalog
        self.done: dict[tuple, list[StaticHeading]] = {}
        self._flight: dict[tuple, asyncio.Future] = {}
        self.brazil = [t.id for t in catalog.targets.values() if t.recordtype == "authority" and t.country == "BR"]

    async def search(self, h: Heading, context: marc.Record, seq: int | None = None) -> tuple[list, bool, Result | None]:
        """(rows, down, the search's Result). DOWN: this machine's network
        was down, so the empty answer means nothing (not kept). The Result
        is None when the answer came from this job's earlier searches."""
        key = (h.kind, h.key, fold(h.dates))
        if key in self.done:
            return self.done[key], False, None
        fut = self._flight.get(key)
        if fut is not None:
            rows, down = await asyncio.shield(fut)
            return rows, down, None
        fut = asyncio.get_running_loop().create_future()
        self._flight[key] = fut
        try:
            res = await self.dispatcher.run(
                None, [step_for(h)], tag=seq, recordtype="authority", context=context,
                only=self.brazil if h.kind in SUBJECT_KINDS else None, max_servers=MAX_SERVERS,
                accept=lambda found: any((e := of_authority(f.record)) is not None and e.heading.key == h.key
                                         for f in found))
            rows, down = rows_of(res, self.catalog), res.down
        except BaseException as exc:
            fut.set_exception(exc)
            fut.exception()
            raise
        finally:
            self._flight.pop(key, None)
        if not down:
            self.done[key] = rows
        fut.set_result((rows, down))
        return rows, down, res


def searchable(f: marc.Field, m: Match) -> bool:
    """A heading nothing matched that a server can be asked for."""
    k = kind_of(f)
    return m.action == "none" and m.heading is not None and k is not None and k[0] in SEARCHED


def heading(f: marc.Field) -> Heading | None:
    k = kind_of(f)
    return from_field(f, k[1], k[0]) if k else None


# ----------------------------------------------------------------------
# One job
# ----------------------------------------------------------------------

def matcher_class():
    """AuthMatcher (nexus_jobs.worker) that also names a server's headings."""
    from nexus_jobs.worker import AuthMatcher

    class OnDemandAuthMatcher(AuthMatcher):
        catalog: Catalog | None = None

        def source_name(self, source: str) -> str:
            if source.startswith("z3950:") and self.catalog is not None:
                return _name(self.catalog, source)
            return super().source_name(source)
    return OnDemandAuthMatcher


class AuthJob:
    """What an authority job needs while it runs: Koha's authorities (the
    job's authorities.xml), static.db's headings (when on and present),
    the matcher and the live searcher."""

    def __init__(self, store, job, job_dir, static_db, use_static: bool, dispatcher: Dispatcher, catalog: Catalog):
        import json

        from nexus_enrich.authority import KohaIndex, StaticHeadings
        from nexus_enrich.static import StaticDB

        self.db = None
        static = None
        if use_static and static_db.is_file():
            try:
                self.db = StaticDB(static_db)
                static = StaticHeadings(self.db.conn)
            except Exception:                       # a fallback only: the servers still answer
                self.close()
                static = None
        release = job.release
        if not release:
            rel = static_db.parent / "static.release"
            try:
                release = json.loads(rel.read_text(encoding="utf-8")).get("name", "") if rel.is_file() else ""
            except (OSError, ValueError):
                release = ""
            if release:
                store.set(job.id, release=release)    # the new authorities' 667, as the batch worker's
        self.matcher = matcher_class()(store, job, static, KohaIndex.from_file(job_dir / "authorities.xml"), release)
        self.matcher.catalog = catalog
        self.searcher = Searcher(dispatcher, catalog)
        self.catalog = catalog

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None

    async def row(self, rec: marc.Record, seq: int, gate, still) -> tuple[dict | None, list]:
        """(REC's item row, the servers' attempts): its headings matched
        with Koha and static.db, the rest asked of the authority servers.
        The row is None when the job stopped while it waited for the network."""
        from nexus_enrich.authority import match_field

        m = self.matcher
        matches = {i: m.match(f) for i, f in enumerate(rec.fields) if kind_of(f) is not None}
        todo = [i for i, x in matches.items() if searchable(rec.fields[i], x)]
        attempts: list = []
        while todo:
            if not await gate.passed(still):
                return None, []
            got = await asyncio.gather(*(self.searcher.search(matches[i].heading, rec, seq) for i in todo))
            if any(down for _, down, _ in got):
                gate.hold()                          # not "nothing found": asked again when it is back
                continue
            if any(res is not None for _, _, res in got):
                gate.open()
            for i, (rows, _, _) in zip(todo, got):
                if rows:
                    found = match_field(rec.fields[i], m.koha, FoundHeadings(rows, self.catalog), m.mode)
                    if found.action != "none":
                        matches[i] = found
            attempts = [a for _, _, res in got if res is not None for a in res.attempts]
            break
        return m.row(rec, matches), attempts
