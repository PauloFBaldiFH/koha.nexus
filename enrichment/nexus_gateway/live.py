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
import logging
import threading
from dataclasses import dataclass

from nexus_enrich import marc

from . import upstream, z3950
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


async def ask(target: Target, kind: str, term: str, timeout: float) -> Answer:
    """One target, one search: its first page of records, or the error."""
    try:
        if target.kind == "z3950":
            total, raws = await z3950.search(target.host, target.port, target.db, kind, term, 1, PAGE,
                                             user=target.user, password=target.password, timeout=timeout)
            records = []
            for raw in raws:
                try:
                    records.append(marc.from_iso2709(raw))
                except (marc.RecordError, ValueError):
                    continue
        else:
            total, records = await asyncio.to_thread(upstream.search, target, kind, term, 1, PAGE, timeout)
        return Answer(target.id, total, records)
    except (z3950.Z3950Error, upstream.UpstreamError, OSError, ValueError) as exc:
        return Answer(target.id, 0, [], str(exc) or type(exc).__name__)


class Runner:
    """The background loop. Thread-safe: request threads call search()."""

    def __init__(self, learned: Learned, budget: float = 6.0, grace: float = 30.0, asker=ask):
        self.learned = learned
        self.budget = budget
        self.grace = grace
        self.asker = asker
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="nexus-gateway-live", daemon=True)
        self.thread.start()

    async def _one(self, target: Target, kind: str, term: str, qkey: str) -> Answer:
        try:
            answer = await asyncio.wait_for(self.asker(target, kind, term, self.grace), self.grace)
        except asyncio.TimeoutError:
            answer = Answer(target.id, 0, [], f"no answer in {self.grace:g}s")
        try:
            self.learned.put(target.id, qkey, answer.total, answer.records, answer.error)
        except Exception:                                   # the reply must not fail on a cache write
            log.exception("learned.db write for %s failed", target.id)
        if answer.error:
            log.info("%s: %s", target.id, answer.error)
        return answer

    def search(self, targets: list[Target], kind: str, term: str, qkey: str) -> list[Answer]:
        """The answers that came within the budget, in the targets' order."""
        futures = {asyncio.run_coroutine_threadsafe(self._one(t, kind, term, qkey), self.loop): t for t in targets}
        done, _late = concurrent.futures.wait(futures, timeout=self.budget)
        out = []
        for fut, t in futures.items():
            if fut in done and fut.exception() is None:
                out.append(fut.result())
        return out

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
