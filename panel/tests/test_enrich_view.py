"""The "Enrich bibliographic catalog" screen, driven headless in demo mode."""

import time

from conftest import INSTALLER
from textual.widgets import Button, DataTable, Input, Label, Static

from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen
from kei_panel.views.enrich import classes, diff_text, state_text, summary_text, valid_scope


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_helpers():
    for good in ("all", "ALL", "101", "101, 102 500-550", "1-5;9"):
        assert valid_scope(good), good
    for bad in ("", "abc", "1-", "x-y", "101,abc"):
        assert not valid_scope(bad), bad
    assert state_text("ready") == "Report ready" and state_text("odd") == "odd"
    assert classes({"m0": 2, "w": 1}) == "M0 W"
    text = summary_text({"report": {"records": 5, "enriched": 4, "review": 1,
                                    "records_with": {"M0": 4, "R": 1}, "fields_added": 16,
                                    "fields_by_source": {"ufpr": 16}, "koha_batches": 1}})
    assert "Records read 5 · Enriched 4" in text and "M0 4 · M1 0 · W 0 · R 1" in text and "ufpr 16" in text
    assert "report appears" in summary_text({"state": "matching"})
    assert "boom" in summary_text({"state": "failed", "error": "boom"})
    styled = diff_text(["# head", "  245 10 $a X", "+ 650 _4 $a Y"])
    assert styled.plain.splitlines() == ["# head", "  245 10 $a X", "+ 650 _4 $a Y"]
    assert any("green" in str(span.style) for span in styled.spans)


def test_jobs_report_diff_apply_and_revert():
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("e")
            view = app.screen.query_one("#view-enrich")
            jobs = view.query_one("#e-table", DataTable)
            await _until(pilot, lambda: jobs.row_count == 2)
            assert jobs.get_row("2")[3] == "Comparing" and jobs.get_row("2")[4] == "20/51"
            assert jobs.get_row("1")[3] == "Report ready"
            state = view.query_one("#e-worker-state", Label)
            assert "Comparing job 2: 20 of 51 records" in str(state.render())
            assert view.query_one("#e-pause", Button).disabled is False
            assert view.query_one("#e-resume", Button).disabled is True

            # The second job: its staged report, changes and buttons.
            view.query_one("#e-table", DataTable).move_cursor(row=1)
            summary = view.query_one("#e-summary", Static)
            await _until(pilot, lambda: "Job 1 ·" in str(summary.render()))
            text = str(summary.render())
            assert "Job 1 · all · Report ready" in text and "M0 356 · M1 41 · W 77 · R 37" in text
            assert "unesp 540" in text
            assert view.query_one("#e-apply", Button).disabled is False
            assert view.query_one("#e-revert", Button).disabled is True
            assert view.query_one("#e-open", Button).disabled is False
            changes = view.query_one("#e-changes", DataTable)
            assert changes.row_count == 3
            assert changes.get_row("230:review")[1] == "Review"

            # One record's before/after: the added lines in green.
            await view._show_diff(1, "101")
            diff = str(view.query_one("#e-diff", Static).render())
            assert "+ 650 _4 $8 1\\p $a Cegueira" in diff and "  245 10 $a Ensaio" in diff

            # Apply asks first, then runs and reports.
            view.query_one("#e-apply", Button).press()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen) and app.screen.query("#yes"))
            app.screen.query_one("#yes", Button).press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen) and app.screen.query("#ok"))
            assert "412 record(s) enriched" in app.screen._body
            app.screen.query_one("#ok", Button).press()
            await _until(pilot, lambda: not isinstance(app.screen, MessageScreen))

            # A bad scope is refused before anything runs.
            view.query_one("#e-scope", Input).value = "abc"
            await pilot.click("#e-start")
            await pilot.pause(0.3)
            assert not isinstance(app.screen, ConfirmScreen)

    import asyncio
    asyncio.run(main())
