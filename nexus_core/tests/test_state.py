import json

import pytest

from nexus_core.tests.fixtures import status_json
from nexus_core import state as S
from nexus_core.status import parse_status

NOW = 1_800_000_000
OK = parse_status(status_json())
DEGRADED = parse_status(status_json(state="degraded"))
NO_KOHA = parse_status(status_json(state="not_installed", koha_installed=False))


def resolve(installed=True, running=True, linux=OK, saved=None, grace_until=0):
    return S.resolve_state(installed=installed, running=running, linux=linux,
                           saved=saved or {}, now=NOW, grace_until=grace_until)


def test_no_distro_is_not_installed():
    assert resolve(installed=False, running=True) == S.NOT_INSTALLED


@pytest.mark.parametrize("saved, grace_until, expected", [
    ({"desired": "stopped"}, 0, S.STOPPED_BY_USER),
    ({"desired": "stopped"}, NOW + 30, S.STOPPED_BY_USER),       # the librarian's stop wins over grace
    ({"desired": "running"}, 0, S.STOPPED),
    ({"desired": "running"}, NOW + 30, S.STARTING),              # just booted
    ({"desired": "running", "autostart": "manual"}, NOW + 30, S.STOPPED),  # manual start: no grace
    ({}, NOW, S.STOPPED),                                        # grace ends at grace_until itself
])
def test_distro_down(saved, grace_until, expected):
    assert resolve(running=False, linux=None, saved=saved, grace_until=grace_until) == expected


def test_up_and_ok_is_running_even_in_grace():
    assert resolve(saved={"desired": "running"}, grace_until=NOW + 30) == S.RUNNING


def test_up_without_koha_is_not_installed():
    assert resolve(linux=NO_KOHA) == S.NOT_INSTALLED


@pytest.mark.parametrize("linux", [DEGRADED, None])
def test_up_not_ok_is_starting_right_after_start(linux):
    assert resolve(linux=linux, saved={"startedAt": NOW - 60}) == S.STARTING
    assert resolve(linux=linux, saved={"startedAt": str(NOW - 60)}) == S.STARTING


@pytest.mark.parametrize("saved", [{}, {"startedAt": NOW - 181}, {"startedAt": None}, {"startedAt": "x"}])
def test_up_not_ok_for_a_while_is_not_responding(saved):
    assert resolve(linux=DEGRADED, saved=saved) == S.NOT_RESPONDING


def test_up_not_ok_in_boot_grace_is_starting():
    assert resolve(linux=DEGRADED, grace_until=NOW + 1) == S.STARTING


def test_boot_grace_until():
    assert S.boot_grace_until(10_000, NOW) == NOW - 10 + S.BOOT_GRACE_S
    assert S.boot_grace_until(10_999, NOW, boot_grace_s=0) == NOW - 10


def test_boot_grace_unwraps_a_32_bit_tick_count():
    # [Environment]::TickCount after 25 days is negative.
    wrapped = 25 * 86400 * 1000 - 4294967296
    assert S.boot_grace_until(wrapped, NOW) == NOW - 25 * 86400 + S.BOOT_GRACE_S


def test_state_texts_are_the_lang_cache_keys():
    assert S.state_text(S.RUNNING) == "Koha is running"
    assert S.state_text("something new") == "Koha is not installed"
    pt = {"Koha is running": "O Koha está em execução"}
    assert S.state_text(S.RUNNING, lambda s: pt.get(s, s)) == pt["Koha is running"]
    assert set(S.STATE_TEXTS) == set(S.STATES)


def test_on_states_are_the_ones_the_tray_can_stop():
    assert set(S.ON_STATES) == {S.RUNNING, S.STARTING, S.NOT_RESPONDING}
