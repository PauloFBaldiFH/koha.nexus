"""Backup center: the compression of new backups, saved by the installer."""

import asyncio
import time

from conftest import INSTALLER
from textual.widgets import Select

from kei_panel.env import PanelEnv
from kei_panel.screens.loading import LoadingScreen


async def _until(pilot, cond, wait=5.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_compression_choice_runs_the_task():
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        calls = []
        real = app.bridge.task

        async def spy(name, *args, **kw):
            calls.append((name, args))
            return await real(name, *args, **kw)
        app.bridge.task = spy
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("b")
            view = app.screen.query_one("#view-backup")
            select = view.query_one("#bk-codec", Select)
            await _until(pilot, lambda: not select.disabled)          # the installer said: gz
            assert select.value == "gz" and view.codec == "gz"
            assert not [c for c in calls if c[0] == "backup-compression"]   # loading saves nothing
            select.value = "zst"
            await pilot.pause(0.3)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen) and view.codec == "zst")
            assert ("backup-compression", ("zst",)) in calls
            assert ".sql.zst" in str(view.query_one("#bk-codec-note").render())

    asyncio.run(main())
