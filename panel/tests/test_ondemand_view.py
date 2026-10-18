"""The "On-demand enrichment" screen and the Z39.50 screen's direct-server
health box, driven headless in demo mode."""

import asyncio
import time

from conftest import INSTALLER
from textual.widgets import Button, DataTable, Input, Label, Static

from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen, MessageScreen
from kei_panel.views.ondemand import attempts_text, count_scope, query_label, server_state
from kei_panel.views.z3950 import health_state


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_helpers():
    assert count_scope("101, 102 500-510") == 13 and count_scope("1 - 50") == 50 and count_scope("7") == 1
    assert server_state("3 record(s)") == "3 record(s)" and server_state("no record") == "No record"
    assert server_state("down: timeout: no answer") == "Down: timeout: no answer"
    assert server_state("skipped: limit") == "Skipped: limit" and server_state("searching") == "Searching…"
    assert query_label({"query": '{"isbn": "978", "title": "X", "year": 1995}'}) == "978 / X / 1995"
    text = attempts_text({"rounds": 2, "attempts": [
        {"target": "a", "outcome": "found", "records": 1}, {"target": "b", "outcome": "none", "records": 0},
        {"target": "c", "outcome": "error", "records": 0}]})
    assert text == "Round 2 · servers asked 3 · with records 1 · down or skipped 1"
    assert health_state("down") == "Paused after failures" and health_state("odd") == "odd"


def test_on_demand_screen():
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(170, 70)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("n")
            view = app.screen.query_one("#view-ondemand")
            jobs = view.query_one("#e-table", DataTable)
            await _until(pilot, lambda: jobs.row_count == 2)          # on-demand jobs only
            assert jobs.get_row("6")[2] == "9788535911664 / O evangelho segundo Jesus Cristo"
            # The live servers of the record being searched.
            servers = view.query_one("#od-servers", DataTable)
            await _until(pilot, lambda: servers.row_count == 4)
            assert servers.get_row("ufpr")[2:] == ["1 record(s)", "412"]
            assert servers.get_row("bne")[2] == "Down: timeout: no answer in 15 s"
            assert "record 2 of 2: Vidas secas" in str(view.query_one("#e-worker-state", Label).render())

            # The typed book: the records found, one already imported.
            summary = view.query_one("#e-summary", Static)
            await _until(pilot, lambda: "Job 6 ·" in str(summary.render()))
            assert "Records found: 2" in str(summary.render())
            assert "servers asked 3 · with records 1 · down or skipped 1" in str(summary.render())
            found = view.query_one("#od-found", DataTable)
            assert found.row_count == 2 and found.get_row("1:2")[3] == "Yes (biblionumber 1302)"
            assert view.query_one("#e-apply", Button).disabled and not view.query_one("#od-import", Button).disabled
            view.query_one("#od-import", Button).press()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen) and app.screen.query("#yes"))
            app.screen.query_one("#yes", Button).press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen) and app.screen.query("#ok"))
            assert "biblionumber 1303" in app.screen._body
            app.screen.query_one("#ok", Button).press()
            await _until(pilot, lambda: not isinstance(app.screen, MessageScreen))

            # The records' job: report, Search more, Choose donor.
            jobs.move_cursor(row=1)
            await _until(pilot, lambda: "Job 5 ·" in str(summary.render()))
            assert "Enriched 2" in str(summary.render())
            assert not view.query_one("#od-more", Button).disabled and not view.query_one("#od-donor", Button).disabled
            view.query_one("#od-donor", Button).press()
            await _until(pilot, lambda: isinstance(app.screen, ChoiceScreen))
            assert "Record 101" in app.screen._prompt
            app.screen.dismiss("subjects")
            await _until(pilot, lambda: isinstance(app.screen, ChoiceScreen) and "Subjects" in app.screen._prompt)
            assert [k for k, _ in app.screen._options] == ["auto", "z3950:ufpr", "z3950:unb"]
            assert app.screen._default == "z3950:ufpr"
            app.screen.dismiss("z3950:unb")
            await _until(pilot, lambda: not isinstance(app.screen, ChoiceScreen))

            # Requests the service would refuse are refused here first.
            for scope in ("all", "1-60", "abc"):
                assert view.scope_problem(scope)
            assert view.scope_problem("101, 117") == ""
            view.query_one("#od-year", Input).value = "95"
            view.query_one("#od-title", Input).value = "Vidas secas"
            assert view.query_args() == "The year has four digits, such as 1995."
            view.query_one("#od-year", Input).value = "1938"
            assert view.query_args() == ["--title", "Vidas secas", "--year", "1938"]

    asyncio.run(main())


def test_batch_screen_leaves_on_demand_jobs_out():
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("e")
            jobs = app.screen.query_one("#view-enrich").query_one("#e-table", DataTable)
            await _until(pilot, lambda: jobs.row_count == 2)
            assert {jobs.get_row_at(i)[0] for i in range(2)} == {"1", "2"}

    asyncio.run(main())


def test_z3950_health_box(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            view = app.screen.query_one("#view-z3950")
            table = view.query_one("#z-health-table", DataTable)
            await _until(pilot, lambda: table.row_count == 2)             # the working one is left out
            assert table.get_row_at(0)[:4] == ["bne", "Paused after failures", "0", "4"]
            assert "2 of 3 direct server address(es)" in str(view.query_one("#z-health-state", Label).render())
            assert not view.query_one("#z-health-reset", Button).disabled
            view.reset_all_health()
            await pilot.pause(0.3)

    asyncio.run(main())
