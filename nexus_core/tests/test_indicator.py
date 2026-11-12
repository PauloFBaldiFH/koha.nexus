"""The tray indicator (study 11, U7): the matrix of section 11.1."""

import pytest

from nexus_core import indicator as I
from nexus_core import state as S
from nexus_core.status import parse_status
from nexus_core.tests.fixtures import status_json

NOW = 1_800_000_000


def linux(summary, **overrides):
    return parse_status(status_json(summary=summary, **overrides))


def summary(*systems, state=None, checked_at=NOW - 30):
    rows = [{"id": i, "name": n, "state": st, "reason": r} for i, n, st, r in systems]
    if state is None:
        counted = [r["state"] for r in rows if r["state"] != "stopped"]
        order = ["ok", "attention", "critical"]
        state = "none" if not rows else "stopped" if not counted else max(counted, key=order.index)
    return {"state": state, "checked_at": checked_at, "systems": rows}


KOHA_OK = ("koha", "Biblioteca Central", "ok", "")
MUSEU_DOWN = ("tainacan", "Museu Municipal", "critical", "not_responding")
REPO_ADMIN = ("dspace", "Repositório Institucional", "attention", "installing")


def show(state, data, now=NOW):
    return I.indicator(state, data, now)


def test_everything_ok_is_green():
    one = show(S.RUNNING, linux(summary(KOHA_OK)))
    assert (one.colour, one.text) == (I.GREEN, "Biblioteca Central is running")
    many = show(S.RUNNING, linux(summary(KOHA_OK, ("dspace", "DSpace", "ok", ""))))
    assert (many.colour, many.text) == (I.GREEN, "All systems running")
    assert many.lines == ("Biblioteca Central (Koha): running", "DSpace: running")


def test_no_system_installed_is_gray():
    data = linux(summary(), state="not_installed", koha_installed=False)
    word = S.resolve_state(installed=True, running=True, linux=data, saved={}, now=NOW)
    shown = show(word, data)
    assert (shown.colour, shown.text) == (I.GRAY, "No system installed. Open the panel to install.")


def test_a_server_without_koha_is_not_not_installed():
    # Bug 2.7: the tray said "Koha is not installed" with Tainacan running.
    data = linux(summary(("tainacan", "Museu Municipal", "ok", "")), state="not_installed", koha_installed=False)
    word = S.resolve_state(installed=True, running=True, linux=data, saved={}, now=NOW)
    assert word == S.RUNNING
    assert show(word, data).text == "Museu Municipal is running"


def test_one_system_down_says_which_and_that_others_run():
    shown = show(S.RUNNING, linux(summary(KOHA_OK, MUSEU_DOWN)))
    assert shown.colour == I.RED
    assert shown.text == "Museu Municipal: not responding · others running"
    assert shown.lines[1] == "Museu Municipal (Tainacan): not responding"


def test_attention_is_yellow_and_the_worst_wins():
    assert show(S.RUNNING, linux(summary(KOHA_OK, REPO_ADMIN))).colour == I.YELLOW
    assert show(S.RUNNING, linux(summary(REPO_ADMIN, MUSEU_DOWN))).text == "Museu Municipal: not responding"


def test_a_shared_service_down():
    shown = show(S.NOT_RESPONDING, linux(summary(("koha", "Biblioteca Central", "critical", "web_server_stopped"))))
    assert (shown.colour, shown.text) == (I.RED, "Biblioteca Central: web server stopped")


def test_a_stopped_system_does_not_count_while_others_run():
    stopped = ("dspace", "Repositório", "stopped", "stopped")
    assert show(S.RUNNING, linux(summary(KOHA_OK, stopped))).colour == I.GREEN
    only = show(S.RUNNING, linux(summary(stopped)))
    assert (only.colour, only.text) == (I.GRAY, "Systems stopped")


def test_debian_stopped():
    assert show(S.STOPPED_BY_USER, None).colour == I.GRAY
    assert show(S.STOPPED, None).colour == I.RED
    assert show(S.STARTING, None).colour == I.YELLOW


def test_unreadable_or_old_check_is_yellow():
    assert (show(S.NOT_RESPONDING, None).colour, show(S.NOT_RESPONDING, None).text) == \
        (I.YELLOW, "Could not check the state")
    old = show(S.RUNNING, linux(summary(KOHA_OK, checked_at=NOW - 180 - 600)))
    assert (old.colour, old.text) == (I.YELLOW, "Could not check the state (13 min ago)")


def test_an_older_installer_keeps_the_old_tray():
    data = parse_status(status_json())
    assert data.summary is None
    assert (show(S.RUNNING, data).colour, show(S.RUNNING, data).text) == (I.GREEN, "Koha is running")
    assert show(S.NOT_RESPONDING, parse_status(status_json(state="degraded"))).colour == I.RED
    assert show(S.NOT_INSTALLED, None).colour == I.GRAY


@pytest.mark.parametrize("bad", [None, "x", {"state": "great"}, {"state": "ok", "systems": "x"}])
def test_a_bad_summary_reads_as_none(bad):
    assert linux(bad).summary is None or linux(bad).summary.systems == ()


def test_bad_rows_are_left_out():
    data = linux({"state": "ok", "checked_at": NOW, "systems": [
        {"id": "atom", "name": "A", "state": "ok"}, {"id": "koha", "name": " ", "state": "ok"},
        {"id": "koha", "name": "B", "state": "great"}, {"id": "dspace", "name": "D" * 200, "state": "ok"}]})
    assert [s.id for s in data.summary.systems] == ["dspace"] and len(data.summary.systems[0].name) == 120


def test_the_tooltip_fits_windows():
    long = ("tainacan", "Museu " + "M" * 80, "critical", "not_responding")
    shown = show(S.RUNNING, linux(summary(KOHA_OK, long)))
    assert len(shown.tooltip) <= 63 and shown.tooltip.endswith("…") and len(shown.text) > 63


def test_the_powershell_port_knows_the_same_reasons():
    from pathlib import Path
    core = (Path(__file__).resolve().parents[2] / "windows" / "KohaEasy.Core.psm1").read_text(encoding="utf-8")
    for key, text in I.REASONS.items():
        assert f"{key} = '{text}'" in core, key
