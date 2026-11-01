"""Live searches of the native targets, on one background event loop.

A search asks every target at once and waits at most the reply budget
(6 s by default, below Koha's own row timeout). A target that answers
later is not cancelled: it may run on for the grace period, and its answer
is written to learned.db, so the next identical search is answered locally.
Every answer, late or not, and every error is written there.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import logging
import threading
from dataclasses import dataclass

from nexus_enrich import marc

from . import upstream, z3950
from . import pergamum as pergamum_mod
from . import zeus as zeus_mod
from .learned import Learned
from .targets import Target

log = logging.getLogger("nexus_gateway.live")
PAGE = 20                    # records asked of each target (the first page Koha shows)


@dataclass
class Answer:
    target: str
    total: int
    records: list[marc.Record]
    error: str = ""


async def _direct(target: Target, kind: str, term: str, timeout: float) -> tuple[int, list[marc.Record]]:
    """A z3950 or sru target at its own address."""
    if target.kind == "z3950":
        total, raws = await z3950.search(target.host, target.port, target.db, kind, term, 1, PAGE,
                                         user=target.user, password=target.password, timeout=timeout)
        records = []
        for raw in raws:
            try:
                records.append(marc.from_iso2709(raw))
            except (marc.RecordError, ValueError):
                continue
        return total, records
    if target.kind == "sru":
        return await asyncio.to_thread(upstream.search, target, kind, term, 1, PAGE, timeout)
    raise upstream.UpstreamError(f"{target.id} has no address of its own (kind {target.kind})")


async def _answer(target: Target, coro) -> Answer:
    try:
        total, records = await coro
        return Answer(target.id, total, records[:PAGE])
    except (z3950.Z3950Error, upstream.UpstreamError, zeus_mod.ZeusError, pergamum_mod.PergamumError,
            OSError, ValueError) as exc:
        return Answer(target.id, 0, [], str(exc) or type(exc).__name__)


async def _first_with_records(target: Target, tasks: list[asyncio.Task]) -> Answer:
    """The first of `tasks` that brings records; else the first one's answer
    (the direct route), with every route's error when none answered."""
    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            if d.result().records:
                for p in pending:
                    p.cancel()
                return d.result()
    answers = [t.result() for t in tasks]
    if all(a.error for a in answers):
        return Answer(target.id, 0, [], "; ".join(a.error for a in answers))
    return next(a for a in answers if not a.error)


async def ask(target: Target, kind: str, term: str, timeout: float,
              zeus: "zeus_mod.Zeus | None" = None, pergamum: "pergamum_mod.Pergamum | None" = None,
              via_zeus: bool = True) -> Answer:
    """One target, one search: its first page of records, or the error.

    With a Zeus address, a z3950/sru target whose name is on Zeus's search
    form is also asked through Zeus at the same time, and a target with no
    address (missing) only through Zeus: the first route that brings
    records answers. So a catalogue whose own port is closed to this
    machine (Alma's 1921 asks for a registered IP) still answers when
    Zeus reaches it. via_zeus=False (/sru/_union, which asks Zeus once for
    its members) leaves that out."""
    if target.kind == "zeus":
        if zeus is None:
            return Answer(target.id, 0, [], "no Zeus address (NEXUS_GATEWAY_ZEUS_URL)")
        if target.id == zeus_mod.UNION_ID:
            return await _answer(target, asyncio.to_thread(zeus.search_many, zeus.members, kind, term, timeout))
        return await _answer(target, asyncio.to_thread(zeus.search, target, kind, term, timeout))
    if target.kind == "pergamum":
        if pergamum is None:
            return Answer(target.id, 0, [], "no Pergamum address (NEXUS_GATEWAY_PERGAMUM_URL)")
        return await _answer(target, asyncio.to_thread(pergamum.search, kind, term, PAGE, timeout))
    tasks = []
    if target.kind in ("z3950", "sru"):
        tasks.append(asyncio.ensure_future(_answer(target, _direct(target, kind, term, timeout))))
    if zeus is not None and via_zeus and target.status != "broken":
        on_form = await asyncio.to_thread(zeus.has, target, min(timeout, 20.0))
        if on_form:
            tasks.append(asyncio.ensure_future(_answer(target, asyncio.to_thread(zeus.search, target, kind,
                                                                                  term, timeout))))
        elif not tasks:
            return Answer(target.id, 0, [], f"{target.name} has no address and is not on Zeus's search form")
    if not tasks:
        return Answer(target.id, 0, [], f"{target.id} has no address of its own (kind {target.kind})")
    return await _first_with_records(target, tasks)


class Runner:
    """The background loop. Thread-safe: request threads call search()."""

    def __init__(self, learned: Learned, budget: float = 6.0, grace: float = 30.0, asker=ask,
                 zeus: "zeus_mod.Zeus | None" = None, pergamum: "pergamum_mod.Pergamum | None" = None):
        self.learned = learned
        self.budget = budget
        self.grace = grace
        self.zeus = zeus                # set: kind zeus targets are searched live too
        self.pergamum = pergamum        # set: the kind pergamum target too
        self.asker = functools.partial(ask, zeus=zeus, pergamum=pergamum) if asker is ask else asker
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="nexus-gateway-live", daemon=True)
        self.thread.start()

    async def _one(self, target: Target, kind: str, term: str, qkey: str, via_zeus: bool = True) -> Answer:
        extra = {} if via_zeus else {"via_zeus": False}
        try:
            answer = await asyncio.wait_for(self.asker(target, kind, term, self.grace, **extra), self.grace)
        except asyncio.TimeoutError:
            answer = Answer(target.id, 0, [], f"no answer in {self.grace:g}s")
        try:
            self.learned.put(target.id, qkey, answer.total, answer.records, answer.error)
        except Exception:                                   # the reply must not fail on a cache write
            log.exception("learned.db write for %s failed", target.id)
        if answer.error:
            log.info("%s: %s", target.id, answer.error)
        return answer

    def search(self, targets: list[Target], kind: str, term: str, qkey: str, via_zeus: bool = True
               ) -> list[Answer]:
        """The answers that came within the budget, in the targets' order."""
        futures = {asyncio.run_coroutine_threadsafe(self._one(t, kind, term, qkey, via_zeus), self.loop): t
                   for t in targets}
        done, _late = concurrent.futures.wait(futures, timeout=self.budget)
        out = []
        for fut, t in futures.items():
            if fut in done and fut.exception() is None:
                out.append(fut.result())
        return out

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
