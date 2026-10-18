"""nexus_ondemand.dispatch on a scripted fake network: waves and early
stop, alternates, diagnostics (114 -> the fallback form, 13 -> a smaller
Present), timeouts, dead names, a network that blocks DNS or port 1921,
the answer cache, joined searches, the provider limits and static.db."""

from __future__ import annotations

import asyncio
import socket

import pytest

from conftest import bib
from nexus_enrich.marc import Field, to_iso2709
from nexus_enrich.merge import Candidate
from nexus_gateway import z3950
from nexus_gateway.learned import Learned
from nexus_gateway.z3950 import Diagnostic, PresentResult, SearchResult, Term, Z3950Error
from nexus_ondemand.connect import open_session
from nexus_ondemand import plan
from nexus_ondemand.dispatch import Dispatcher, Settings
from nexus_ondemand.health import Health
from nexus_ondemand.limits import Limiter, Limits
from nexus_ondemand.policy import Policy
from nexus_ondemand.targets import Address, Catalog, Target

ISBN = "9780306406157"
T0 = 1_760_000_000.0


def local():
    return bib("O cortiço", "Azevedo, Aluísio", isbn=ISBN, year=1890, publisher="Garnier")


def donor(rich=True, dewey="869.3"):
    """The same book as local(), catalogued fully (completeness 6+) or minimally."""
    extra = [Field("082", "0", "4", [("a", dewey)])] if dewey else []
    subjects = [Field("650", " ", "0", [("a", "Brazilian fiction")])] if rich else []
    return bib("O cortiço", "Azevedo, Aluísio", isbn=ISBN, year=1890, publisher="Garnier",
               level=" " if rich else "3", subjects=subjects, extra=extra)


def other_book():
    return bib("Memórias póstumas", "Assis, Machado de", isbn="9788535902778", year=1881)


def uses(q) -> set[int]:
    return {q.use} if isinstance(q, Term) else uses(q.left) | uses(q.right)


class Server:
    """What one fake host does. connect: a Z3950Error kind raised when
    connecting; refuse: Bib-1 uses answered with diagnostic 114; search_diag:
    a diagnostic for every search; max_present: Present over it gets
    diagnostic 13; delay: seconds before the session opens."""

    def __init__(self, records=(), *, connect="", refuse=(), search_diag=None, max_present=None, delay=0.0,
                 total=None):
        self.records = list(records)
        self.connect, self.refuse, self.search_diag = connect, set(refuse), search_diag
        self.max_present, self.delay, self.total = max_present, delay, total


class FakeSession:
    def __init__(self, net, addr):
        self.net, self.addr = net, addr
        self.server = net.servers[addr.host]

    @property
    def label(self):
        return self.addr.host_key

    async def search(self, db, query):
        self.net.searches.append((self.addr.host, sorted(uses(query))))
        if self.server.search_diag is not None:
            return SearchResult(0, False, [Diagnostic(self.server.search_diag)])
        if uses(query) & self.server.refuse:
            return SearchResult(0, False, [Diagnostic(114, "7")])
        n = self.server.total if self.server.total is not None else len(self.server.records)
        return SearchResult(n)

    async def present(self, start, count, *, syntax=z3950.OID_USMARC):
        self.net.presents.append((self.addr.host, count))
        if self.server.max_present is not None and count > self.server.max_present:
            return PresentResult([], [Diagnostic(13)])
        return PresentResult([to_iso2709(r) for r in self.server.records[start - 1:start - 1 + count]])

    async def close(self):
        self.net.open_now[self.addr.provider] -= 1
        self.net.closed.append(self.addr.host)


class FakeNet:
    """The opener the dispatcher uses in place of connect.open_session."""

    def __init__(self, **servers: Server):
        self.servers = {host.replace("_", "."): s for host, s in servers.items()}
        self.opened: list[tuple[str, float]] = []
        self.searches, self.presents, self.closed = [], [], []
        self.open_now: dict[str, int] = {}
        self.peak: dict[str, int] = {}

    async def __call__(self, target, addr, policy, timeouts):
        server = self.servers[addr.host]
        self.opened.append((addr.host, timeouts.total))
        if server.delay:
            await asyncio.sleep(server.delay)
        if server.connect:
            raise Z3950Error(f"{addr.host}: {server.connect}", phase="connect", kind=server.connect)
        self.open_now[addr.provider] = self.open_now.get(addr.provider, 0) + 1
        self.peak[addr.provider] = max(self.peak.get(addr.provider, 0), self.open_now[addr.provider])
        return FakeSession(self, addr)

    def hosts(self) -> list[str]:
        return [h for h, _ in self.opened]


def tgt(tid, host=None, port=210, country="BR", category="brazil", alternates=(), **kw) -> Target:
    return Target(tid, kw.pop("name", tid.upper()), Address(host or f"{tid}.example.org", port, "b"),
                  country=country, category=category, alternates=tuple(alternates), **kw)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds
        await asyncio.sleep(0)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def health(tmp_path, clock):
    h = Health(tmp_path / "health.db", clock=clock)
    yield h
    h.close()


def dispatcher(targets, net, health, clock, learned=None, static=None, static_on=True, **settings) -> Dispatcher:
    catalog = Catalog({t.id: t for t in targets}, [], "sha")
    settings.setdefault("wave_budget", 1.0)
    settings["static"] = static_on
    return Dispatcher(catalog, health, Limiter(Limits(), store=health, clock=clock, sleep=clock.sleep),
                      learned=learned, static=static, settings=Settings(**settings), opener=net)


def run(d, rec=None, steps=None, **kw):
    rec = local() if rec is None else rec
    return asyncio.run(d.run(rec, plan.for_record(rec) if steps is None else steps, **kw))


# ----------------------------------------------------------------------
# Waves, early stop, typed queries
# ----------------------------------------------------------------------

def test_a_good_donor_in_the_first_wave_stops_the_search(health, clock):
    targets = [tgt(f"s{i}") for i in range(10)]
    net = FakeNet(**{f"s{i}_example_org": Server([donor()] if i == 0 else []) for i in range(10)})
    res = run(dispatcher(targets, net, health, clock))
    assert res.stopped_early and res.servers == 6
    assert sorted(net.hosts()) == sorted(f"s{i}.example.org" for i in range(6))
    (f,) = res.found
    assert f.source == "z3950:s0" and f.cls == "M0" and f.completeness >= 6 and f.step == "isbn"
    assert {a.outcome for a in res.attempts} == {"found", "none"}
    assert sorted(net.closed) == sorted(net.hosts())                 # every session closed
    (c,) = res.candidates()
    assert isinstance(c, Candidate) and c.brazilian and c.source == "z3950:s0"


def test_a_poor_donor_does_not_stop_the_search_two_agreeing_on_082_do(health, clock):
    targets = [tgt(f"s{i}") for i in range(12)]
    net = FakeNet(**{f"s{i}_example_org": Server([donor(rich=False)] if i in (0, 7) else []) for i in range(12)})
    res = run(dispatcher(targets, net, health, clock))
    assert res.stopped_early and res.servers == 12 and len(res.found) == 2


def test_max_servers_and_search_more(health, clock):
    targets = [tgt(f"s{i}") for i in range(30)]
    net = FakeNet(**{f"s{i}_example_org": Server() for i in range(30)})
    d = dispatcher(targets, net, health, clock)
    first = run(d)
    assert first.servers == 20 and not first.stopped_early and len(net.opened) == 20
    asked = set(net.hosts())
    net.opened.clear()
    more = run(d, exclude=first.asked)
    assert more.servers == 10 and not asked & set(net.hosts()) and len(set(net.hosts())) == 10


def test_a_typed_query_stops_at_the_first_wave_with_records(health, clock):
    targets = [tgt(f"s{i}") for i in range(12)]
    net = FakeNet(**{f"s{i}_example_org": Server([other_book()] if i == 3 else []) for i in range(12)})
    d = dispatcher(targets, net, health, clock)
    res = asyncio.run(d.run(None, plan.for_query(isbn="9788535902778")))
    assert res.stopped_early and res.servers == 6 and res.found[0].cls is None


def test_a_slow_server_does_not_hold_the_next_wave(health, clock):
    targets = [tgt("aslow"), *(tgt(f"s{i}") for i in range(6))]
    servers = {f"s{i}_example_org": Server() for i in range(6)}
    net = FakeNet(aslow_example_org=Server([donor()], delay=0.3), **servers)
    res = run(dispatcher(targets, net, health, clock, wave=1, wave_budget=0.02, max_servers=7))
    # every wave started before the slow server answered; its answer still counts
    assert net.hosts()[:2] == ["aslow.example.org", "s0.example.org"] and len(net.opened) == 7
    assert [f.source for f in res.found] == ["z3950:aslow"]


# ----------------------------------------------------------------------
# Search forms and Present
# ----------------------------------------------------------------------

def test_diagnostic_114_falls_back_to_the_identifier_form_and_is_remembered(health, clock):
    net = FakeNet(s_example_org=Server([donor()], refuse={7}))
    d = dispatcher([tgt("s")], net, health, clock)
    res = run(d)
    assert net.searches == [("s.example.org", [7]), ("s.example.org", [1007])]
    assert res.found and health.capability("s.example.org:210/b", "isbn") is False
    net.searches.clear()
    run(d)
    assert net.searches == [("s.example.org", [1007])]                # straight to the form it takes


def test_a_refused_form_moves_to_the_next_step(health, clock):
    net = FakeNet(s_example_org=Server([donor()], refuse={7, 1007}))
    res = run(dispatcher([tgt("s")], net, health, clock))
    assert [u for _, u in net.searches] == [[7], [1007], [4, 1003]]
    assert res.found[0].step == "title-author" and health.state("s.example.org:210/b") == "ok"


def test_present_is_capped_at_ten(health, clock):
    net = FakeNet(s_example_org=Server([other_book()] * 3, total=37))
    run(dispatcher([tgt("s")], net, health, clock))
    assert net.presents == [("s.example.org", 10)]


def test_loc_diagnostic_13_retries_with_half(health, clock):
    loc = tgt("loc", "lx2.loc.gov", country="US", category="north_america", name="Library of Congress")
    net = FakeNet(lx2_loc_gov=Server([donor()] * 10, max_present=5))
    res = run(dispatcher([loc], net, health, clock))
    assert net.presents == [("lx2.loc.gov", 10), ("lx2.loc.gov", 5)] and len(res.found) == 5


def test_broad_title_searches_are_not_fetched(health, clock):
    net = FakeNet(s_example_org=Server([other_book()], total=500))
    rec = bib("Poemas", "Silva, José")
    res = run(dispatcher([tgt("s")], net, health, clock), rec)
    assert net.presents == [] and res.found == [] and res.attempts[0].hits == 0


def test_a_config_diagnostic_is_an_error_for_that_server(health, clock):
    net = FakeNet(s_example_org=Server(search_diag=109))
    res = run(dispatcher([tgt("s")], net, health, clock))
    (a,) = res.attempts
    assert a.outcome == "error" and a.category == "misconfigured"
    assert health.state("s.example.org:210/b") == "misconfigured"


def test_session_timeouts_loc_12s_others_15s(health, clock):
    loc = tgt("loc", "lx2.loc.gov", country="US", category="north_america")
    alma = tgt("jhu", "na01.alma.exlibrisgroup.com", 1921, country="US", category="north_america")
    net = FakeNet(lx2_loc_gov=Server(), na01_alma_exlibrisgroup_com=Server(), s_example_org=Server())
    run(dispatcher([loc, alma, tgt("s")], net, health, clock))
    assert dict(net.opened) == {"lx2.loc.gov": 12, "na01.alma.exlibrisgroup.com": 15, "s.example.org": 15}


# ----------------------------------------------------------------------
# Failures, alternates, health
# ----------------------------------------------------------------------

def test_a_refused_primary_moves_to_the_alternate_and_remembers_it(health, clock):
    alt = Address("z2.example.org", 210, "b")
    net = FakeNet(s_example_org=Server(connect="refused"), z2_example_org=Server([donor()]))
    d = dispatcher([tgt("s", alternates=[alt])], net, health, clock)
    res = run(d)
    assert net.hosts() == ["s.example.org", "z2.example.org"] and res.found
    assert [a.outcome for a in res.attempts] == ["error", "found"]
    assert health.preferred("s") == alt.key
    net.opened.clear()
    run(d)
    assert net.hosts() == ["z2.example.org"]


def test_a_dead_name_fails_fast_for_a_day(health, clock):
    """redes.ufsm.br and the unifei hosts: the name lookup says the name
    does not exist; one attempt, then no request waits on it for 24 h."""
    net = FakeNet(redes_ufsm_br=Server(connect="dns-missing"), s_example_org=Server())
    d = dispatcher([tgt("ufsm", "redes.ufsm.br"), tgt("s")], net, health, clock)
    run(d)
    assert health.state("redes.ufsm.br:210/b") == "down"
    net.opened.clear()
    res = run(d)
    assert net.hosts() == ["s.example.org"] and ("ufsm", "down") in res.skipped
    clock.now += 23 * 3600
    assert health.state("redes.ufsm.br:210/b") == "down"
    clock.now += 2 * 3600
    assert health.state("redes.ufsm.br:210/b") == "half-open"


def test_the_real_policy_turns_a_missing_name_into_gone(health, clock):
    async def lookup(host, port):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    d = dispatcher([tgt("unifei", "thor.unifei.edu.br")], FakeNet(), health, clock)
    d.opener = open_session
    d.policy = Policy(resolver=lookup)
    res = asyncio.run(d.run(local(), plan.for_record(local())))
    assert res.attempts[0].category == "gone" and health.state("thor.unifei.edu.br:210/b") == "down"


def test_the_real_policy_never_connects_to_a_refused_address(health, clock, monkeypatch):
    async def no_connection(*a, **k):
        raise AssertionError("a refused address was contacted")

    async def cloudflare(host, port):
        return ["104.16.132.229"]

    monkeypatch.setattr(asyncio, "open_connection", no_connection)
    d = dispatcher([tgt("s")], FakeNet(), health, clock)
    d.opener = open_session
    d.policy = Policy(resolver=cloudflare)
    res = asyncio.run(d.run(local(), plan.for_record(local())))
    assert res.attempts[0].category == "policy" and res.found == []


def test_three_timeouts_open_the_breaker(health, clock):
    net = FakeNet(s_example_org=Server(connect="timeout"))
    d = dispatcher([tgt("s")], net, health, clock)
    for _ in range(3):
        run(d)
    assert health.state("s.example.org:210/b") == "down"
    net.opened.clear()
    run(d)
    assert net.opened == []


def test_a_network_without_dns_is_not_held_against_the_servers(health, clock):
    targets = [tgt(f"s{i}") for i in range(6)]
    net = FakeNet(**{f"s{i}_example_org": Server(connect="dns") for i in range(6)})
    res = run(dispatcher(targets, net, health, clock))
    assert res.network == ["dns"]
    assert all(health.state(t.address.key) == "ok" and health.summary(t.address.key)["fail_7d"] == 0
               for t in targets)


def test_a_few_dns_failures_among_answers_are_the_servers(health, clock):
    targets = [tgt(f"s{i}") for i in range(6)]
    net = FakeNet(**{f"s{i}_example_org": Server(connect="dns-missing" if i < 5 else "") for i in range(6)})
    res = run(dispatcher(targets, net, health, clock))
    assert res.network == [] and health.state("s0.example.org:210/b") == "down"


def test_a_network_that_blocks_port_1921(health, clock):
    """Alma answers on 1921; when every 1921 connection times out and the
    port-210 servers answer, the outbound port is blocked here."""
    alma = [tgt(f"a{i}", f"a{i}.alma.exlibrisgroup.com", 1921) for i in range(6)]
    others = [tgt(f"s{i}") for i in range(4)]
    net = FakeNet(**{f"a{i}_alma_exlibrisgroup_com": Server(connect="timeout") for i in range(6)},
                  **{f"s{i}_example_org": Server() for i in range(4)})
    res = run(dispatcher(alma + others, net, health, clock))
    assert res.network == ["port 1921"]
    assert all(health.summary(t.address.key)["fail_7d"] == 0 for t in alma)


# ----------------------------------------------------------------------
# Limits: Ex Libris Alma
# ----------------------------------------------------------------------

def test_alma_sessions_stay_bounded(health, clock):
    alma = [tgt(f"a{i}", f"a{i}.alma.exlibrisgroup.com", 1921, country="GB", category="europe") for i in range(12)]
    net = FakeNet(**{f"a{i}_alma_exlibrisgroup_com": Server(delay=0.05) for i in range(12)})
    res = run(dispatcher(alma, net, health, clock, wave_budget=0.01, max_servers=12))
    assert res.servers == 12 and len(net.opened) == 12
    assert net.peak["exlibris-alma"] <= 4
    assert health.daily("exlibris-alma") == 12


# ----------------------------------------------------------------------
# Answer cache, joined searches
# ----------------------------------------------------------------------

def test_cached_answers_open_no_session(health, clock, tmp_path):
    learned = Learned(tmp_path / "learned.db")
    net = FakeNet(s_example_org=Server([donor()]), t_example_org=Server())
    d = dispatcher([tgt("s"), tgt("t")], net, health, clock, learned=learned)
    first = run(d)
    net.opened.clear()
    again = run(d)
    assert net.opened == [] and len(again.found) == len(first.found) == 1
    assert sorted(a.outcome for a in again.attempts) == ["cached", "cached"]


def test_identical_searches_in_flight_are_joined(health, clock):
    net = FakeNet(s_example_org=Server([donor()], delay=0.05))
    d = dispatcher([tgt("s")], net, health, clock)

    async def both():
        steps = plan.for_record(local())
        return await asyncio.gather(d.run(local(), steps), d.run(local(), steps))

    a, b = asyncio.run(both())
    assert len(net.opened) == 1 and len(a.found) == len(b.found) == 1


# ----------------------------------------------------------------------
# static.db after the servers
# ----------------------------------------------------------------------

def test_static_is_asked_only_when_no_server_found_the_same_book(health, clock):
    asked = []

    def static(rec):
        asked.append(rec)
        return [Candidate(donor(), "bn", "123", 0.9)]

    net = FakeNet(s_example_org=Server())
    res = run(dispatcher([tgt("s")], net, health, clock, static=static))
    assert res.static_used and [f.source for f in res.found] == ["static:bn"] and res.found[0].cls == "M0"

    net = FakeNet(s_example_org=Server([donor()]))
    res = run(dispatcher([tgt("s")], net, health, clock, static=static))
    assert not res.static_used and len(asked) == 1

    net = FakeNet(s_example_org=Server())
    res = run(dispatcher([tgt("s")], net, health, clock, static=static, static_on=False))
    assert not res.static_used and len(asked) == 1


def test_a_broken_static_lookup_never_fails_the_request(health, clock):
    def static(rec):
        raise OSError("disk")

    res = run(dispatcher([tgt("s")], FakeNet(s_example_org=Server()), health, clock, static=static))
    assert res.found == [] and not res.static_used


def test_events_are_reported(health, clock):
    events = []
    net = FakeNet(s_example_org=Server([donor()]))
    d = dispatcher([tgt("s")], net, health, clock)
    d.on_event = events.append
    run(d)
    assert [e["type"] for e in events] == ["skipped", "wave", "attempt", "done"]


def test_no_steps_no_network(health, clock):
    net = FakeNet(s_example_org=Server())
    res = asyncio.run(dispatcher([tgt("s")], net, health, clock).run(local(), []))
    assert net.opened == [] and res.servers == 0



# ----------------------------------------------------------------------
# Many records at once: spreading, adaptive timeouts, pace
# ----------------------------------------------------------------------

def test_a_busy_server_moves_back_behind_idle_ones(health, clock):
    targets = [tgt(f"s{i}") for i in range(8)]
    d = dispatcher(targets, FakeNet(), health, clock)
    busy = {"s0.example.org": 1.0, "s1.example.org": 3.0}
    d.limiter.load = lambda a: busy.get(a.host, 0.0)
    order = [t.id for t in d._spread(targets)]
    assert order == ["s2", "s3", "s4", "s5", "s6", "s7", "s0", "s1"]    # a wave back per session ahead
    d.settings.spread = False
    assert d._spread(targets) == targets


def test_two_records_at_once_ask_different_servers_first(health, clock):
    targets = [tgt(f"s{i}") for i in range(4)]
    net = FakeNet(**{f"s{i}_example_org": Server([donor()], delay=0.05) for i in range(4)})
    d = dispatcher(targets, net, health, clock, wave=2, per_wave_provider=2)

    async def both():
        first = asyncio.ensure_future(d.run(local(), plan.for_record(local()), tag=1))
        await asyncio.sleep(0.01)                                   # the first record's sessions are open
        second = await d.run(local(), plan.for_record(local()), tag=2)
        return await first, second
    a, b = asyncio.run(both())
    assert a.asked == ["s0", "s1"] and b.asked == ["s2", "s3"]
    assert a.stopped_early and b.stopped_early


def test_a_server_that_answers_fast_is_not_waited_on_long(health, clock):
    for _ in range(5):
        health.record_success("s0.example.org:210/b", 500)
    for _ in range(4):
        health.record_success("s1.example.org:210/b", 500)          # not often enough yet
    health.record_success("s2.example.org:210/b", 9000)
    for _ in range(4):
        health.record_success("s2.example.org:210/b", 9000)
    net = FakeNet(s0_example_org=Server(), s1_example_org=Server(), s2_example_org=Server())
    run(dispatcher([tgt("s0"), tgt("s1"), tgt("s2")], net, health, clock))
    totals = dict(net.opened)
    assert totals["s0.example.org"] == 6.0                          # 4 x 0.5 s, at least 6 s
    assert totals["s1.example.org"] == 15 and totals["s2.example.org"] == 15   # the default: 4 x 9 s is more


def test_answers_and_timeouts_set_each_hosts_pace(health, clock):
    net = FakeNet(s0_example_org=Server([donor(rich=False)]), s1_example_org=Server(connect="timeout"),
                  s2_example_org=Server(connect="refused"))
    d = dispatcher([tgt("s0"), tgt("s1"), tgt("s2")], net, health, clock)
    run(d)
    pace = d.limiter.pacer
    assert pace.factor("s0.example.org:210") == 1.0 and "s0.example.org:210" in pace.usual
    assert pace.factor("s1.example.org:210") == 0.5                 # a timeout: slower
    assert pace.factor("s2.example.org:210") == 1.0                 # a refused connection is the breaker's


def test_every_event_carries_the_records_number(health, clock):
    events = []
    d = dispatcher([tgt("s0")], FakeNet(s0_example_org=Server([donor()])), health, clock)
    d.on_event = events.append
    run(d, tag=7)
    assert events and {e["seq"] for e in events} == {7}



def test_quota_waits_only_when_the_records_own_servers_are_all_over_their_cap(health, clock):
    from nexus_ondemand.dispatch import next_midnight
    br1, br2, us = tgt("br1"), tgt("br2"), tgt("us", country="US", category="north_america")
    d = dispatcher([br1, br2, us], FakeNet(), health, clock)
    rec = local()
    rec.fields = [f for f in rec.fields if f.tag != "008"]
    rec.add_field(Field("008", data="201017s1890    bl            000 0 por d"))
    assert d.quota_until(rec) is None
    for _ in range(500):
        health.add_daily(br1.address.host_key)
    assert d.quota_until(rec) is None                                # br2 still has searches today
    for _ in range(500):
        health.add_daily(br2.address.host_key)
    assert d.quota_until(rec, now=1_000.0) == next_midnight(1_000.0)  # the Brazilian ones are used up
    assert d.quota_until(None) is None                               # no language: the US server is left


def test_skipped_servers_are_reported(health, clock):
    events = []
    br1, br2 = tgt("br1"), tgt("br2")
    d = dispatcher([br1, br2], FakeNet(br1_example_org=Server(), br2_example_org=Server()), health, clock)
    d.on_event = events.append
    for _ in range(500):
        health.add_daily(br1.address.host_key)
    run(d)
    skipped = next(e for e in events if e["type"] == "skipped")
    assert [tid for tid, _ in skipped["targets"]] == ["br1"] and "daily limit" in skipped["targets"][0][1]
