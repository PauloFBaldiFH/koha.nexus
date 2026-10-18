"""How hard on-demand enrichment may use the direct servers (plan section 5).

Every session takes a slot: the host's (host:port), its provider's when it
has one (all *.alma.exlibrisgroup.com hosts share Ex Libris' clusters; LoC
asks bulk users to download instead), then one of the service's. Each
level has a concurrency limit, a token bucket (sessions per second and a
burst) and a daily cap. A daily cap that is reached refuses at once
(LimitReached); a busy host or an empty bucket only waits.

Slots are taken narrowest first (host, provider, rate wait, then the
service's), so a request waiting on a busy host does not hold one of the
service's slots. The rate of a host or provider is multiplied by its
factor in health.db, which a ban-like signal halves, and by its pace
(Pacer, in memory): a host that answers much slower than it usually does,
or times out, is asked more slowly at once and gets its speed back a step
at a time while it answers well (AIMD). Daily counts live in health.db
too, so a restart does not reset them; the buckets start full again
after a restart, which allows at most one burst more.

load() says how busy a host is now (sessions open, requests queued for
it, seconds until its bucket lets one more in), so a request with other
good servers to ask can ask those first instead of queueing (dispatch.py).
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from .targets import Address


@dataclass(frozen=True)
class Limit:
    sessions: int                # at the same time
    rate: float                  # new sessions per second
    burst: float                 # sessions allowed back to back
    daily: int                   # sessions per local day


@dataclass(frozen=True)
class Limits:
    service: int = 8                                       # sessions at once for the whole service
    host: Limit = Limit(1, 0.5, 2, 500)
    providers: dict = field(default_factory=lambda: {
        "exlibris-alma": Limit(4, 2.0, 4, 3000),
        "loc": Limit(1, 1 / 6, 1, 300),
    })


class LimitReached(Exception):
    """A daily cap is reached: skip this server today."""

    def __init__(self, key: str, cap: int):
        super().__init__(f"daily limit reached ({key}: {cap} sessions)")
        self.key, self.cap = key, cap


class Bucket:
    def __init__(self, rate: float, burst: float, now: float):
        self.rate, self.burst = rate, burst
        self.tokens, self.stamp = burst, now

    def _fill(self, now: float, factor: float) -> None:
        if now > self.stamp:
            self.tokens = min(self.burst, self.tokens + (now - self.stamp) * self.rate * factor)
        self.stamp = max(self.stamp, now)

    def wait(self, now: float, factor: float = 1.0) -> float:
        """Seconds until a token is there (0: now)."""
        self._fill(now, factor)
        return 0.0 if self.tokens >= 1 else (1 - self.tokens) / (self.rate * factor)

    def take(self, now: float, factor: float = 1.0) -> None:
        self._fill(now, factor)
        self.tokens -= 1


class Pacer:
    """The pace of each host, from its answers (AIMD): x DECREASE after a
    timeout or an answer SLOW times slower than its usual one (and over
    SLOW_FLOOR_MS), + INCREASE after each answer at its usual speed, between
    FLOOR and 1. Usual = the latency average of its normal answers."""

    DECREASE = 0.5
    INCREASE = 0.1
    FLOOR = 0.125
    SLOW = 2.5
    SLOW_FLOOR_MS = 2000.0
    ALPHA = 0.2

    def __init__(self):
        self.pace: dict[str, float] = {}
        self.usual: dict[str, float] = {}

    def factor(self, key: str) -> float:
        return self.pace.get(key, 1.0)

    def observe(self, key: str, ms: float | None, ok: bool) -> float:
        """Record one session of KEY (ms: how long it took; ok False: it
        timed out or broke). Returns the new pace."""
        pace = self.pace.get(key, 1.0)
        usual = self.usual.get(key)
        if not ok:
            pace *= self.DECREASE
        elif ms is not None and usual and ms > max(self.SLOW * usual, self.SLOW_FLOOR_MS):
            pace *= self.DECREASE                    # slow for this host: give it room
        else:
            pace += self.INCREASE
            if ms is not None:
                self.usual[key] = ms if usual is None else (1 - self.ALPHA) * usual + self.ALPHA * ms
        if ok and ms is not None and usual is None:
            self.usual[key] = ms
        self.pace[key] = min(1.0, max(self.FLOOR, pace))
        return self.pace[key]


class _NoStore:
    """Daily counts and factors in memory (tests, or no health.db)."""

    def __init__(self):
        self.counts: dict[str, int] = {}

    def daily(self, key, now=None):
        return self.counts.get(key, 0)

    def add_daily(self, key, now=None):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def factor(self, key, now=None):
        return 1.0


class Limiter:
    """One per service process (one asyncio loop). STORE is a Health (or
    anything with daily, add_daily and factor)."""

    def __init__(self, limits: Limits | None = None, store=None, clock=time.time, sleep=asyncio.sleep):
        self.limits = limits or Limits()
        self.store = store or _NoStore()
        self.clock, self.sleep = clock, sleep
        self._service = asyncio.Semaphore(self.limits.service)
        self._sems: dict[str, asyncio.Semaphore] = {}
        self._buckets: dict[str, Bucket] = {}
        self.pacer = Pacer()
        self._open: dict[str, int] = {}
        self._queued: dict[str, int] = {}

    def _sem(self, key: str, limit: Limit) -> asyncio.Semaphore:
        if key not in self._sems:
            self._sems[key] = asyncio.Semaphore(limit.sessions)
        return self._sems[key]

    def _bucket(self, key: str, limit: Limit) -> Bucket:
        if key not in self._buckets:
            self._buckets[key] = Bucket(limit.rate, limit.burst, self.clock())
        return self._buckets[key]

    def levels(self, address: Address) -> list[tuple[str, Limit]]:
        out = [(address.host_key, self.limits.host)]
        if address.provider in self.limits.providers:
            out.append((address.provider, self.limits.providers[address.provider]))
        return out

    def observe(self, address: Address, ms: float | None, ok: bool) -> None:
        """One session's outcome, for the host's pace (see Pacer)."""
        self.pacer.observe(address.host_key, ms, ok)

    def _factor(self, key: str, now: float) -> float:
        return self.store.factor(key, now) * self.pacer.factor(key)

    def load(self, address: Address) -> float:
        """How long a new session for ADDRESS would wait, in sessions ahead
        of it: the ones open and queued past the host's limit, plus its
        bucket's wait in seconds over its pace (0: it can go now)."""
        now = self.clock()
        out = 0.0
        for key, limit in self.levels(address):
            ahead = self._open.get(key, 0) + self._queued.get(key, 0)
            out = max(out, ahead / limit.sessions if ahead >= limit.sessions else 0.0)
            if key in self._buckets:
                wait = self._buckets[key].wait(now, self._factor(key, now))
                out = max(out, wait * limit.rate)
        return out

    def capped(self, address: Address) -> str:
        """Why ADDRESS is over a daily cap today, or ""."""
        now = self.clock()
        for key, limit in self.levels(address):
            if self.store.daily(key, now) >= limit.daily:
                return str(LimitReached(key, limit.daily))
        return ""

    def _check_daily(self, levels) -> None:
        now = self.clock()
        for key, limit in levels:
            if self.store.daily(key, now) >= limit.daily:
                raise LimitReached(key, limit.daily)

    @asynccontextmanager
    async def slot(self, address: Address):
        """Hold a session slot for ADDRESS. Raises LimitReached."""
        levels = self.levels(address)
        self._check_daily(levels)
        keys = [key for key, _ in levels]
        _count(self._queued, keys, 1)
        queued = True
        try:
            async with self._sem(*levels[0]):
                async with (self._sem(*levels[1]) if len(levels) > 1 else _nothing()):
                    while True:
                        now = self.clock()
                        factors = [self._factor(key, now) for key in keys]
                        wait = max(self._bucket(key, limit).wait(now, f) for (key, limit), f in zip(levels, factors))
                        if wait <= 0:
                            break
                        await self.sleep(wait)
                    self._check_daily(levels)               # another request may have used the last one meanwhile
                    for (key, limit), f in zip(levels, factors):
                        self._bucket(key, limit).take(now, f)
                        self.store.add_daily(key, now)
                    _count(self._queued, keys, -1)
                    queued = False
                    _count(self._open, keys, 1)
                    try:
                        async with self._service:
                            yield
                    finally:
                        _count(self._open, keys, -1)
        finally:
            if queued:
                _count(self._queued, keys, -1)


def _count(counts: dict, keys, n: int) -> None:
    for key in keys:
        counts[key] = counts.get(key, 0) + n


@asynccontextmanager
async def _nothing():
    yield
