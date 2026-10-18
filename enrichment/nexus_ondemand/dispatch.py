"""The on-demand dispatcher (plan sections 4.3, 5 and 6): asks the ranked
direct servers for one record, in waves, and collects what they answer.

One record:
- the plan's steps (plan.py) are tried in order on each server, in one
  session per server (Init once); a cached answer (learned.db, key
  "direct:<id>") is used before any connection;
- servers are asked in waves of WAVE (select.py); the next wave starts
  when the wave is done or after the wave budget; the search stops after
  a wave that found a good same-manifestation donor (M0 with completeness
  >= GOOD, or two M0 agreeing on 082), or at MAX_SERVERS;
- each server: its preferred address, then the others in the list's
  order, skipping those whose breaker or daily cap says no;
- every session holds a limiter slot (limits.py) and goes through
  connect.open_session (the policy's checked address only);
- Present asks for at most PRESENT_MAX records (LoC answers diagnostic 13
  to more); a diagnostic 13 is retried once with half as many;
- after the servers, when no M0 was found, the local static.db (a file
  read, no network) when the library has it on.

Failures go to health.db (health.py), except those that say more about
this machine's network than about the servers: when 5 or more servers of
one request fail the same way (no name lookup works, or every port-1921
connection times out) and none of that kind succeeds, they are not held
against the servers and the result says what the network blocks.

The koha.nexus endpoints are not reachable from here: they are not in the
list and the policy refuses them.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field

from nexus_enrich import classify as cl
from nexus_enrich import marc
from nexus_enrich.merge import Candidate
from nexus_gateway.z3950 import OID_USMARC, Session, Timeouts, Z3950Error

from . import select
from .connect import open_session
from .health import Outcome, classify
from .limits import LimitReached
from .plan import BROAD_STEPS, Step
from .policy import Policy
from .targets import Address, Catalog, Target

log = logging.getLogger("nexus_ondemand.dispatch")

WAVE = 6
MAX_SERVERS = 20
WAVE_BUDGET = 12.0
PRESENT_MAX = 10              # LoC refuses more in one Present (diagnostic 13)
TOO_BROAD = 50
GOOD = 6                      # completeness of an M0 donor that ends the search
NETWORK_WIDE = 5              # failures of one kind in one request that point at our own network
DEFAULT_TIMEOUTS = Timeouts(connect=4, init=6, search=10, present=12, close=2, total=15)
PROVIDER_TIMEOUTS = {"loc": Timeouts(connect=4, init=6, search=10, present=12, close=2, total=12)}


@dataclass
class Settings:
    wave: int = WAVE
    max_servers: int = MAX_SERVERS
    wave_budget: float = WAVE_BUDGET
    present_max: int = PRESENT_MAX
    per_wave_provider: int = select.PER_WAVE_PROVIDER
    timeouts: Timeouts = DEFAULT_TIMEOUTS
    provider_timeouts: dict = field(default_factory=lambda: dict(PROVIDER_TIMEOUTS))
    static: bool = True

    def timeouts_for(self, address: Address) -> Timeouts:
        return self.provider_timeouts.get(address.provider, self.timeouts)


@dataclass
class Attempt:
    target: str
    address: str
    outcome: str                  # found, none, error, skipped, cached
    detail: str = ""
    category: str = ""            # health category of an error
    step: str = ""
    hits: int = 0
    records: int = 0
    ms: int = 0
    wave: int = 0


@dataclass
class Found:
    source: str                   # z3950:<id>, or static:<source>
    record: marc.Record
    step: str = ""
    cls: str | None = None        # M0 / M1 / W / R against the local record
    completeness: int = 0
    weight: float = 0.5
    brazilian: bool = False       # a Brazilian source (merge's subject rule)
    remote_id: str = ""           # the record's id there (001 when it has one)


@dataclass
class Result:
    attempts: list[Attempt] = field(default_factory=list)
    found: list[Found] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    servers: int = 0              # servers asked (not skipped)
    asked: list[str] = field(default_factory=list)      # their ids, for "Search more servers"
    stopped_early: bool = False
    static_used: bool = False
    network: list[str] = field(default_factory=list)    # "dns", "port 1921": what this machine's network blocks

    def candidates(self) -> list[Candidate]:
        """For nexus_enrich.merge: one Candidate per record found."""
        return [Candidate(f.record, f.source, f.remote_id or f.record.control("001"), f.weight, f.brazilian)
                for f in self.found]


def _weight(t: Target) -> float:
    return 0.9 if select.is_national(t) else 0.7 if t.preselect else 0.5


def static_candidates(path):
    """A static lookup for Dispatcher(static=...): static.db's candidates
    for a record, or [] when the file is missing."""
    from pathlib import Path

    from nexus_enrich.static import StaticDB

    def lookup(rec: marc.Record) -> list[Candidate]:
        if rec is None or not Path(path).is_file():
            return []
        db = StaticDB(path)
        try:
            return db.candidates_for(rec)[0]
        finally:
            db.close()
    return lookup


class _Request:
    """One record's bookkeeping."""

    def __init__(self, local: marc.Record | None):
        self.local = local
        self.keys = cl.Keys.of(local) if local is not None else None
        self.result = Result()
        self.deferred: list[tuple[str, Outcome, Address, str]] = []   # held back: maybe our own network
        self.dns_ok = False
        self.port1921_ok = False


class Dispatcher:
    def __init__(self, catalog: Catalog, health, limiter, policy: Policy | None = None, learned=None,
                 static=None, settings: Settings | None = None, opener=open_session, clock=time.monotonic,
                 on_event=None):
        self.catalog = catalog
        self.health = health
        self.limiter = limiter
        self.policy = policy or Policy()
        self.learned = learned
        self.static = static
        self.settings = settings or Settings()
        self.opener = opener
        self.clock = clock
        self.on_event = on_event
        self._inflight: dict[tuple, asyncio.Future] = {}

    def _emit(self, **event) -> None:
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception:                         # a broken listener never stops a search
                log.exception("on_event failed")

    # one record ---------------------------------------------------------

    async def run(self, local: marc.Record | None, steps: list[Step], *, only=None,
                  max_servers: int | None = None, exclude=()) -> Result:
        """Ask the servers for LOCAL (None: a typed query) with STEPS. The
        targets in EXCLUDE (an earlier run's Result.asked) are passed over:
        "Search more servers" asks the next ones."""
        req = _Request(local)
        res = req.result
        if not steps:
            return res
        ranked, res.skipped = select.rank(self.catalog.targets.values(), local, only=only, health=self.health,
                                          limiter=self.limiter)
        exclude = set(exclude)
        queue = [t for t in ranked if t.id not in exclude][:max_servers or self.settings.max_servers]
        pending: set[asyncio.Task] = set()
        for n, wave in enumerate(select.waves(queue, self.settings.wave, self.settings.per_wave_provider), 1):
            self._emit(type="wave", wave=n, targets=[t.id for t in wave])
            tasks = {asyncio.ensure_future(self._target(req, t, steps, n)) for t in wave}
            res.servers += len(wave)
            res.asked += [t.id for t in wave]
            done, late = await asyncio.wait(tasks, timeout=self.settings.wave_budget)
            pending |= late
            if self._good_enough(req):
                res.stopped_early = True
                break
        if pending:
            grace = max(t.total for t in [self.settings.timeouts, *self.settings.provider_timeouts.values()])
            _, still = await asyncio.wait(pending, timeout=grace + 1)
            for task in still:
                task.cancel()
            if still:
                await asyncio.gather(*still, return_exceptions=True)
        self._settle(req)
        if self.settings.static and self.static is not None and not self._has(req, cl.M0):
            self._static(req)
        self._emit(type="done", found=len(res.found), servers=res.servers, stopped_early=res.stopped_early,
                   network=res.network)
        return res

    def _has(self, req: _Request, cls: str) -> bool:
        return any(f.cls == cls for f in req.result.found)

    def _good_enough(self, req: _Request) -> bool:
        found = req.result.found
        if req.local is None:
            return bool(found)                       # a typed query: the first wave with records
        m0 = [f for f in found if f.cls == cl.M0]
        if any(f.completeness >= GOOD for f in m0):
            return True
        dewey = [f.record.first("082").get("a").strip() for f in m0 if f.record.first("082") is not None]
        return any(dewey.count(d) >= 2 for d in dewey if d)

    def _static(self, req: _Request) -> None:
        try:
            cands = self.static(req.local)
        except Exception as exc:                     # static.db is a fallback: never fail the request on it
            log.warning("static lookup failed: %s", exc)
            return
        for c in cands:
            self._add(req, Found(f"static:{c.source}", c.record, "static", weight=c.weight, brazilian=c.brazilian,
                                 remote_id=c.remote_id))
        req.result.static_used = True
        self._emit(type="static", found=len(cands))

    def _add(self, req: _Request, f: Found) -> None:
        if req.keys is not None:
            f.cls = cl.classify(req.keys, cl.Keys.of(f.record)).cls
        f.completeness = cl.completeness(f.record)
        req.result.found.append(f)

    # one server ---------------------------------------------------------

    async def _target(self, req: _Request, t: Target, steps: list[Step], wave: int) -> None:
        preferred = self.health.preferred(t.id) if self.health is not None else ""
        addresses = sorted(t.addresses, key=lambda a: a.key != preferred)
        for addr in addresses:
            attempt = Attempt(t.id, addr.key, "skipped", wave=wave)
            why = self.health.allow(addr.key) if self.health is not None else ""
            if not why:
                why = self.limiter.capped(addr) if self.limiter is not None else ""
                if why and self.health is not None:
                    self.health.release(addr.key)
            if why:
                attempt.detail = why
                self._record(req, attempt)
                continue
            started = self.clock()
            try:
                records, step, hits, cached = await self._shared(t, addr, steps)
            except LimitReached as exc:
                if self.health is not None:
                    self.health.release(addr.key)
                attempt.detail = str(exc)
                self._record(req, attempt)
                continue
            except Z3950Error as exc:
                outcome = classify(exc)
                attempt.outcome, attempt.category, attempt.detail = "error", outcome.category, str(exc)
                attempt.ms = int((self.clock() - started) * 1000)
                self._failure(req, addr, outcome, exc)
                self._record(req, attempt)
                continue                              # the same catalogue at its next address
            except asyncio.CancelledError:
                if self.health is not None:
                    self.health.release(addr.key)
                raise
            attempt.ms = int((self.clock() - started) * 1000)
            attempt.step, attempt.hits, attempt.records = step, hits, len(records)
            attempt.outcome = "cached" if cached else ("found" if records else "none")
            if not cached:
                req.dns_ok = True
                req.port1921_ok |= addr.port == 1921
                if self.health is not None:
                    self.health.record_success(addr.key, attempt.ms)
                    if addr is not t.address:
                        self.health.set_preferred(t.id, addr.key)
            elif self.health is not None:
                self.health.release(addr.key)
            for rec in records:
                self._add(req, Found(f"z3950:{t.id}", rec, step, weight=_weight(t), brazilian=t.country == "BR"))
            self._record(req, attempt)
            return

    def _record(self, req: _Request, a: Attempt) -> None:
        req.result.attempts.append(a)
        self._emit(type="attempt", target=a.target, address=a.address, outcome=a.outcome, detail=a.detail,
                   step=a.step, hits=a.hits, records=a.records, ms=a.ms, wave=a.wave)

    def _failure(self, req: _Request, addr: Address, outcome: Outcome, exc: Z3950Error) -> None:
        if exc.phase != "connect" or exc.kind not in ("dns", "dns-missing"):
            req.dns_ok = True                         # the name was found
        network_wide = (exc.kind in ("dns", "dns-missing")
                        or (addr.port == 1921 and exc.phase == "connect" and exc.kind == "timeout"))
        if network_wide:
            req.deferred.append((addr.key, outcome, addr, exc.kind))
            if self.health is not None:
                self.health.release(addr.key)
            return
        if self.health is not None:
            self.health.record_failure(addr.key, outcome, host_key=addr.host_key, provider=addr.provider)

    def _settle(self, req: _Request) -> None:
        """Record the held-back failures, unless they point at this machine's network."""
        dns = [d for d in req.deferred if d[3] in ("dns", "dns-missing")]
        port = [d for d in req.deferred if d[3] == "timeout"]
        drop = set()
        if len(dns) >= NETWORK_WIDE and not req.dns_ok:
            req.result.network.append("dns")
            drop |= {id(d) for d in dns}
        if len(port) >= NETWORK_WIDE and not req.port1921_ok:
            req.result.network.append("port 1921")
            drop |= {id(d) for d in port}
        if self.health is None:
            return
        for d in req.deferred:
            if id(d) not in drop:
                key, outcome, addr, _ = d
                self.health.record_failure(key, outcome, host_key=addr.host_key, provider=addr.provider)

    async def _shared(self, t: Target, addr: Address, steps: list[Step]):
        """_ask, with identical searches in flight joined."""
        key = (addr.key, tuple(s.qkey for s in steps))
        fut = self._inflight.get(key)
        if fut is not None:
            records, step, hits, _ = await asyncio.shield(fut)
            return records, step, hits, True
        fut = asyncio.get_running_loop().create_future()
        self._inflight[key] = fut
        try:
            out = await self._ask(t, addr, steps)
        except BaseException as exc:
            if not fut.done():
                fut.set_exception(exc)
                fut.exception()                      # retrieved: no "never retrieved" warning
            raise
        else:
            fut.set_result(out)
            return out
        finally:
            self._inflight.pop(key, None)

    async def _ask(self, t: Target, addr: Address, steps: list[Step]):
        """(records, step name, hits, cached) from ADDR: the first step with
        records, from learned.db when fresh, else from one session."""
        cache_id = f"direct:{t.id}"
        async with contextlib.AsyncExitStack() as stack:
            session: Session | None = None
            for step in steps:
                if self.learned is not None:
                    got = self.learned.get(cache_id, step.qkey)
                    if got is not None and not got[2]:
                        total, records, _ = got
                        if records:
                            return records, step.name, total, session is None
                        continue
                if session is None:
                    await stack.enter_async_context(self.limiter.slot(addr))
                    session = await self.opener(t, addr, self.policy, self.settings.timeouts_for(addr))
                    stack.push_async_callback(session.close)
                records, total = await self._step(session, t, addr, step)
                if self.learned is not None:
                    self.learned.put(cache_id, step.qkey, total, records)
                if records:
                    return records, step.name, total, False
            return [], "", 0, session is None

    async def _step(self, session: Session, t: Target, addr: Address, step: Step) -> tuple[list, int]:
        cap = self.health.capability(addr.key, step.name) if self.health is not None else None
        query = step.fallback if (cap is False and step.fallback is not None) else step.query
        found = await session.search(addr.db, query)
        if not found.ok:
            diag = found.diagnostic
            if diag is not None and diag.category == "query" and query is step.query and step.fallback is not None:
                if self.health is not None:
                    self.health.note_capability(addr.key, step.name, False)
                found = await session.search(addr.db, step.fallback)
                diag = found.diagnostic if not found.ok else None
            if not found.ok:
                if diag is not None and diag.category in ("config", "temporary"):
                    raise Z3950Error(f"{session.label}: {diag}", phase="search", kind="diagnostic", diagnostic=diag)
                return [], 0                          # this form is refused: the next step
        elif query is step.query and cap is None and self.health is not None:
            self.health.note_capability(addr.key, step.name, True)
        if not found.total:
            return [], 0
        if step.name in BROAD_STEPS and found.total > TOO_BROAD:
            return [], found.total                    # too broad to be worth fetching
        count = min(found.total, self.settings.present_max)
        page = await session.present(1, count, syntax=OID_USMARC)
        if not page.records and count > 1 and any(d.code == 13 for d in page.diagnostics):
            page = await session.present(1, max(1, count // 2), syntax=OID_USMARC)
        if not page.records:
            config = next((d for d in page.diagnostics if d.category == "config"), None)
            if config is not None:
                raise Z3950Error(f"{session.label}: {config}", phase="present", kind="diagnostic",
                                 diagnostic=config)
        records = []
        for raw in page.records:
            try:
                rec = marc.from_iso2709(raw)
            except (marc.RecordError, ValueError):
                continue
            if rec.marc8_fallback:                    # bad diacritics must never reach the catalogue
                continue
            records.append(rec)
        return records, found.total
