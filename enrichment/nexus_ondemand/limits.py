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
factor in health.db, which a ban-like signal halves. Daily counts live in
health.db too, so a restart does not reset them; the buckets start full
again after a restart, which allows at most one burst more.
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
        async with self._sem(*levels[0]):
            async with (self._sem(*levels[1]) if len(levels) > 1 else _nothing()):
                while True:
                    now = self.clock()
                    factors = [self.store.factor(key, now) for key, _ in levels]
                    wait = max(self._bucket(key, limit).wait(now, f) for (key, limit), f in zip(levels, factors))
                    if wait <= 0:
                        break
                    await self.sleep(wait)
                self._check_daily(levels)               # another request may have used the last one meanwhile
                for (key, limit), f in zip(levels, factors):
                    self._bucket(key, limit).take(now, f)
                    self.store.add_daily(key, now)
                async with self._service:
                    yield


@asynccontextmanager
async def _nothing():
    yield
