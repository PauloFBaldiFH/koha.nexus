"""nexus_ondemand.limits: one session per host, provider limits for Ex
Libris Alma and LoC, token buckets, daily caps and the rate factor. A fake
clock whose sleep advances it keeps the tests instant."""

from __future__ import annotations

import asyncio

import pytest

from nexus_ondemand.health import Health, Outcome
from nexus_ondemand.limits import Bucket, Limit, LimitReached, Limiter, Limits
from nexus_ondemand.targets import Address

ALMA_A = Address("usp.alma.exlibrisgroup.com", 1921, "55USP_INST")
ALMA_B = Address("na01.alma.exlibrisgroup.com", 1921, "01X")
LOC = Address("lx2.loc.gov", 210, "LCDB")
DNB = Address("z3950.dnb.de", 210, "dnb")
DNB2 = Address("z3950.dnb.de", 210, "zdb")
OTHER = Address("z3950.example.org", 210, "b")


class FakeTime:
    """clock() and an async sleep() that only moves the clock."""

    def __init__(self, now=1_760_000_000.0):
        self.now = now
        self.slept = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)


def limiter(t: FakeTime, store=None, **over) -> Limiter:
    return Limiter(Limits(**over), store=store, clock=t, sleep=t.sleep)


def test_bucket_refills_at_its_rate():
    b = Bucket(0.5, 2, 0.0)
    assert b.wait(0.0) == 0
    b.take(0.0)
    b.take(0.0)
    assert b.wait(0.0) == pytest.approx(2.0)
    assert b.wait(1.0) == pytest.approx(1.0)
    assert b.wait(2.0) == 0
    assert b.wait(2.0, factor=0.5) == 0                  # already full enough
    b.take(2.0)
    assert b.wait(2.0, factor=0.5) == pytest.approx(4.0)  # half the rate: twice the wait


def test_levels_name_host_and_provider():
    lim = limiter(FakeTime())
    assert [k for k, _ in lim.levels(ALMA_A)] == ["usp.alma.exlibrisgroup.com:1921", "exlibris-alma"]
    assert [k for k, _ in lim.levels(LOC)] == ["lx2.loc.gov:210", "loc"]
    assert [k for k, _ in lim.levels(DNB)] == ["z3950.dnb.de:210"]
    assert lim.levels(DNB)[0][0] == lim.levels(DNB2)[0][0]       # one host, two databases: one limit


def run_sessions(lim, t, addresses, hold=1.0):
    """Start one session per address at once; each holds its slot for
    HOLD seconds. Returns [(address, start, end)] and the peak concurrency
    per limit key."""
    active, peak, log = {}, {}, []

    async def one(a):
        async with lim.slot(a):
            keys = [k for k, _ in lim.levels(a)] + ["service"]
            for k in keys:
                active[k] = active.get(k, 0) + 1
                peak[k] = max(peak.get(k, 0), active[k])
            start = t()
            await t.sleep(hold)
            log.append((a, start, t()))
            for k in keys:
                active[k] -= 1

    async def main():
        await asyncio.gather(*(one(a) for a in addresses))

    asyncio.run(main())
    return log, peak


def test_one_session_at_a_time_per_host():
    t = FakeTime()
    lim = limiter(t)
    log, peak = run_sessions(lim, t, [DNB, DNB2, DNB])
    assert peak["z3950.dnb.de:210"] == 1
    starts = sorted(s for _, s, _ in log)
    assert starts[1] - starts[0] >= 1.0               # waited for the first to end


def test_the_host_rate_spaces_sessions_after_the_burst():
    t = FakeTime()
    lim = limiter(t)
    log, _ = run_sessions(lim, t, [OTHER] * 4, hold=0.0)
    starts = sorted(s for _, s, _ in log)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert gaps[0] == pytest.approx(0) and all(g == pytest.approx(2.0) for g in gaps[1:])   # burst 2, then 0.5/s


def test_alma_hosts_share_the_provider_limit():
    t = FakeTime()
    lim = limiter(t, providers={"exlibris-alma": Limit(2, 100.0, 100, 1000)})
    hosts = [Address(f"inst{i}.alma.exlibrisgroup.com", 1921, "X") for i in range(6)]
    _, peak = run_sessions(lim, t, hosts)
    assert peak["exlibris-alma"] == 2
    assert all(peak[h.host_key] == 1 for h in hosts)


def test_loc_gets_one_session_every_six_seconds():
    t = FakeTime()
    lim = limiter(t)
    log, peak = run_sessions(lim, t, [LOC, Address("z3950.loc.gov", 7090, "voyager"), LOC], hold=0.0)
    starts = sorted(s for _, s, _ in log)
    assert peak["loc"] == 1
    assert all(b - a >= 6.0 - 1e-6 for a, b in zip(starts, starts[1:]))


def test_the_service_limit_caps_everything():
    t = FakeTime()
    lim = limiter(t, service=3)
    hosts = [Address(f"z{i}.example.org", 210, "b") for i in range(7)]
    _, peak = run_sessions(lim, t, hosts)
    assert peak["service"] == 3


def test_waiting_on_a_busy_host_does_not_hold_a_service_slot():
    t = FakeTime()
    lim = limiter(t, service=1)
    log, _ = run_sessions(lim, t, [DNB, DNB, OTHER], hold=1.0)
    order = [a for a, _, _ in sorted(log, key=lambda r: r[1])]
    assert order[:2] == [DNB, OTHER]                  # OTHER ran while the second DNB waited


def test_daily_cap_refuses_at_once(tmp_path):
    t = FakeTime()
    store = Health(tmp_path / "h.db", clock=t)
    lim = limiter(t, store=store, host=Limit(1, 100.0, 100, 2))
    run_sessions(lim, t, [OTHER, OTHER], hold=0.0)
    assert lim.capped(OTHER).startswith("daily limit reached")

    async def again():
        async with lim.slot(OTHER):
            pass

    with pytest.raises(LimitReached):
        asyncio.run(again())
    assert store.daily(OTHER.host_key) == 2
    t.now += 86400
    assert lim.capped(OTHER) == ""
    store.close()


def test_provider_daily_cap(tmp_path):
    t = FakeTime()
    lim = limiter(t, providers={"exlibris-alma": Limit(4, 100.0, 100, 2)})
    run_sessions(lim, t, [ALMA_A, ALMA_B], hold=0.0)
    assert "exlibris-alma" in lim.capped(Address("other.alma.exlibrisgroup.com", 1921, "Y"))


def test_a_ban_halves_the_rate_used_by_the_limiter(tmp_path):
    t = FakeTime()
    store = Health(tmp_path / "h.db", clock=t)
    store.record_failure(OTHER.key, Outcome("ban", "closed", "search", "resources"), host_key=OTHER.host_key)
    lim = limiter(t, store=store)
    log, _ = run_sessions(lim, t, [OTHER] * 3, hold=0.0)
    starts = sorted(s for _, s, _ in log)
    assert starts[2] - starts[1] == pytest.approx(4.0)  # 0.25/s instead of 0.5/s
    store.close()
