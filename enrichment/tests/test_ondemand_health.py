"""nexus_ondemand.health: failure classes, the circuit breaker, ban-like
signals, misconfigured servers, capabilities and the rate factor. A fake
clock drives every test."""

from __future__ import annotations

import pytest

from nexus_gateway.z3950 import Diagnostic, Z3950Error
from nexus_ondemand.health import (BAN_SECONDS, OPEN_BASE, OPEN_MAX, Health, Outcome, classify,
                                   classify_diagnostic)
from nexus_ondemand.policy import PolicyError

K = "z.example.org:210/b"
T0 = 1_760_000_000.0          # a fixed start


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def health(tmp_path, clock):
    h = Health(tmp_path / "health.db", clock=clock)
    yield h
    h.close()


def err(kind, phase="search", **kw):
    return Z3950Error(f"{kind} at {phase}", phase=phase, kind=kind, **kw)


TRANSIENT = Outcome("transient", "timeout", "search", "no answer")
DOWN = Outcome("down", "refused", "connect", "refused")


# ----------------------------------------------------------------------
# Classes
# ----------------------------------------------------------------------

@pytest.mark.parametrize("exc, category", [
    (err("dns", "connect"), "down"),
    (err("refused", "connect"), "down"),
    (err("timeout", "connect"), "transient"),
    (err("timeout", "present"), "transient"),
    (err("reset", "init"), "transient"),
    (err("unreachable", "connect"), "transient"),
    (err("protocol", "init"), "transient"),
    (err("init-refused", "init"), "misconfigured"),
    (err("closed", close_reason=4), "ban"),
    (err("closed", close_reason=5), "ban"),
    (err("closed", close_reason=7), "transient"),
    (err("diagnostic", diagnostic=Diagnostic(114)), "capability"),
    (err("diagnostic", diagnostic=Diagnostic(235)), "misconfigured"),
    (err("diagnostic", diagnostic=Diagnostic(2)), "transient"),
    (err("diagnostic", diagnostic=Diagnostic(17)), "bad_data"),
    (PolicyError("no"), "policy"),
])
def test_classify(exc, category):
    o = classify(exc)
    assert o.category == category and o.kind == exc.kind


def test_classify_diagnostic_keeps_the_phase():
    assert classify_diagnostic(Diagnostic(239), "present") == Outcome("misconfigured", "diagnostic", "present",
                                                                     "diagnostic 239")


# ----------------------------------------------------------------------
# Breaker
# ----------------------------------------------------------------------

def test_three_consecutive_failures_open_it(health, clock):
    for _ in range(2):
        assert health.record_failure(K, TRANSIENT) == "ok"
    assert health.allow(K) == ""
    assert health.record_failure(K, TRANSIENT) == "down"
    assert health.allow(K).startswith("down until")
    clock.advance(OPEN_BASE - 1)
    assert health.state(K) == "down"
    clock.advance(2)
    assert health.state(K) == "half-open"


def test_a_down_failure_counts_twice(health):
    health.record_failure(K, DOWN)
    assert health.state(K) == "ok"
    assert health.record_failure(K, TRANSIENT) == "down"


def test_a_success_resets_the_count(health):
    health.record_failure(K, TRANSIENT)
    health.record_failure(K, TRANSIENT)
    health.record_success(K, 120)
    health.record_failure(K, TRANSIENT)
    assert health.state(K) == "ok"


def test_five_failures_in_ten_minutes_open_it(health, clock):
    for _ in range(4):
        health.record_failure(K, TRANSIENT)
        if health.state(K) == "down":
            break
        health.record_success(K)          # interleaved successes keep "consecutive" low
        clock.advance(60)
    # 4 failures so far within the window, none 3 in a row
    assert health.state(K) == "ok"
    assert health.record_failure(K, TRANSIENT) == "down"


def test_old_failures_leave_the_window(health, clock):
    for _ in range(4):
        health.record_failure(K, TRANSIENT)
        health.record_success(K)
        clock.advance(200)
    assert health.record_failure(K, TRANSIENT) == "ok"


def test_half_open_allows_one_probe_and_backs_off_exponentially(health, clock):
    for _ in range(3):
        health.record_failure(K, TRANSIENT)
    waits = []
    for _ in range(4):
        row = health.summary(K)
        waits.append(round(row["open_until"] - clock()))
        clock.advance(row["open_until"] - clock() + 1)
        assert health.allow(K) == ""                     # the probe
        assert health.allow(K) == "being retried by another request"
        health.record_failure(K, TRANSIENT)
    assert waits == [OPEN_BASE, 2 * OPEN_BASE, 4 * OPEN_BASE, 8 * OPEN_BASE]
    clock.advance(health.summary(K)["open_until"] - clock() + 1)
    assert health.allow(K) == ""
    health.record_success(K, 300)
    assert health.state(K) == "ok" and health.summary(K)["level"] == 0


def test_the_wait_is_capped(health, clock):
    for _ in range(3):
        health.record_failure(K, TRANSIENT)
    for _ in range(12):
        clock.advance(health.summary(K)["open_until"] - clock() + 1)
        health.allow(K)
        health.record_failure(K, TRANSIENT)
    assert health.summary(K)["open_until"] - clock() <= OPEN_MAX


def test_release_frees_an_unused_probe(health, clock):
    for _ in range(3):
        health.record_failure(K, TRANSIENT)
    clock.advance(OPEN_BASE + 1)
    assert health.allow(K) == ""
    health.release(K)
    assert health.allow(K) == ""


def test_capability_and_bad_data_mean_the_server_is_up(health):
    health.record_failure(K, TRANSIENT)
    health.record_failure(K, TRANSIENT)
    assert health.record_failure(K, Outcome("capability", "diagnostic", "search", "diagnostic 114")) == "ok"
    health.record_failure(K, TRANSIENT)
    assert health.state(K) == "ok"
    assert health.record_failure(K, Outcome("bad_data")) == "ok"


def test_policy_refusals_do_not_touch_the_breaker(health):
    for _ in range(5):
        health.record_failure(K, Outcome("policy", "policy", "connect", "refused by policy"))
    assert health.state(K) == "ok"


# ----------------------------------------------------------------------
# Misconfigured
# ----------------------------------------------------------------------

def test_misconfigured_waits_for_a_list_change_or_reset(health, clock):
    assert health.check_list("sha-1") is True
    health.record_failure(K, classify(err("init-refused", "init")))
    assert health.state(K) == "misconfigured"
    clock.advance(10 * 86400)
    assert health.allow(K).startswith("misconfigured")
    assert health.check_list("sha-1") is False and health.state(K) == "misconfigured"
    assert health.check_list("sha-2") is True and health.state(K) == "ok"
    health.record_failure(K, classify(err("diagnostic", diagnostic=Diagnostic(235))))
    assert health.state(K) == "misconfigured"
    assert health.reset(K) == 1 and health.state(K) == "ok"


def test_a_successful_manual_test_clears_misconfigured(health):
    health.record_failure(K, classify(err("init-refused", "init")))
    health.record_success(K, 200)
    assert health.state(K) == "ok"


# ----------------------------------------------------------------------
# Ban-like signals and the rate factor
# ----------------------------------------------------------------------

def test_server_close_for_resources_opens_for_a_day_and_halves_the_rate(health, clock):
    health.record_failure(K, classify(err("closed", close_reason=4)), host_key="z.example.org:210")
    assert health.state(K) == "down"
    assert health.summary(K)["open_until"] - clock() == BAN_SECONDS
    assert health.factor("z.example.org:210") == 0.5
    clock.advance(86400)
    assert health.factor("z.example.org:210") == 0.75
    clock.advance(2 * 86400)
    assert health.factor("z.example.org:210") == 1.0


def test_repeated_penalties_have_a_floor(health, clock):
    for _ in range(6):
        health.record_failure(K, classify(err("closed", close_reason=4)), host_key="h:210")
    assert health.factor("h:210") == 0.125


def test_two_resets_at_init_in_ten_minutes_are_a_ban(health, clock):
    reset = classify(err("reset", "init"))
    assert health.record_failure(K, reset, host_key="h:210") == "ok"
    clock.advance(300)
    assert health.record_failure(K, reset, host_key="h:210") == "down"
    assert health.summary(K)["open_until"] - clock() == BAN_SECONDS


def test_resets_far_apart_are_not(health, clock):
    reset = classify(err("reset", "init"))
    health.record_failure(K, reset)
    clock.advance(900)
    health.record_success(K)
    assert health.record_failure(K, reset) == "ok"


def test_refused_after_answering_the_same_day_is_a_ban(health, clock):
    health.record_success(K, 100)
    clock.advance(60)
    health.record_failure(K, classify(err("refused", "connect")), host_key="h:210")
    assert health.summary(K)["open_until"] - clock() == BAN_SECONDS
    assert health.factor("h:210") == 0.5


def test_three_banned_hosts_penalize_their_provider(health):
    for i in range(3):
        key = f"inst{i}.alma.exlibrisgroup.com:1921/X"
        health.record_failure(key, classify(err("closed", close_reason=4)), host_key=key.split("/")[0],
                              provider="exlibris-alma")
        assert health.factor("exlibris-alma") == (1.0 if i < 2 else 0.5)


# ----------------------------------------------------------------------
# The rest of the store
# ----------------------------------------------------------------------

def test_capabilities_preferred_and_daily(health, clock):
    assert health.capability(K, "use7") is None
    health.note_capability(K, "use7", False)
    assert health.capability(K, "use7") is False
    health.set_preferred("usp", "dedalus.usp.br:9991/USP01")
    assert health.preferred("usp") == "dedalus.usp.br:9991/USP01" and health.preferred("x") == ""
    assert [health.add_daily("h:210") for _ in range(3)] == [1, 2, 3]
    clock.advance(86400)
    assert health.daily("h:210") == 0


def test_summary_and_prune(health, clock):
    health.record_success(K, 100)
    health.record_success(K, 200)
    health.record_failure(K, TRANSIENT)
    s = health.summary(K)
    assert (s["ok_7d"], s["fail_7d"], s["state"]) == (2, 1, "ok") and s["latency_ms"] == 130
    clock.advance(8 * 86400)
    health.prune()
    assert health.summary(K)["ok_7d"] == 0


def test_state_survives_a_restart(tmp_path, clock):
    h = Health(tmp_path / "h.db", clock=clock)
    for _ in range(3):
        h.record_failure(K, TRANSIENT)
    h.add_daily("h:210")
    h.close()
    h2 = Health(tmp_path / "h.db", clock=clock)
    assert h2.state(K) == "down" and h2.daily("h:210") == 1
    h2.close()
