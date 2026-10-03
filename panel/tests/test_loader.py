"""The worker + Pac-Man pattern, end to end in a headless app."""

import asyncio
import time

from conftest import INSTALLER
from textual.app import App

from kei_panel.env import PanelEnv
from kei_panel.screens.loading import LoadingScreen
from kei_panel.tasks import TaskFailed, run_with_loader
from kei_panel.widgets.pacman import PacmanLoader


class Host(App):
    def __init__(self):
        super().__init__()
        self.env = PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True)
        self.results = []


def run(job, *, cancel_after=None, wait=3.0):
    async def main():
        app = Host()
        async with app.run_test(size=(100, 30)) as pilot:
            run_with_loader(app, "Working", job, on_done=app.results.append)
            await pilot.pause(0.1)
            assert isinstance(app.screen, LoadingScreen)
            pac = app.screen.query_one(PacmanLoader)
            first = pac.frame
            if cancel_after is not None:
                await pilot.pause(cancel_after)
                await pilot.press("escape")
            deadline = time.monotonic() + wait
            while not app.results and time.monotonic() < deadline:
                await pilot.pause(0.05)
            return app.results[0], pac.frame - first, type(app.screen).__name__
    return asyncio.run(main())


def test_async_job_animates_while_it_runs():
    async def job(reporter):
        for i in range(10):
            reporter.progress(i + 1, 10)
            await asyncio.sleep(0.08)
        return 42
    result, frames, screen = run(job)
    assert result.ok and result.value == 42
    assert frames >= 6           # ~10 fps over ~0.8 s: the loop was never blocked
    assert screen != "LoadingScreen"


def test_thread_job_does_not_block_the_animation():
    def job(reporter):
        time.sleep(0.8)          # blocking work, in a thread
        reporter.log("finished")
        return "ok"
    result, frames, _ = run(job)
    assert result.ok and result.log == ["finished"]
    assert frames >= 6


def test_failure_is_reported():
    async def job(reporter):
        reporter.log("step 1")
        raise TaskFailed("exit 3")
    result, _, _ = run(job)
    assert not result.ok and result.error == "exit 3" and result.log == ["step 1"]


def test_escape_cancels():
    async def job(reporter):
        await asyncio.sleep(10)
    result, _, _ = run(job, cancel_after=0.3)
    assert result.cancelled and not result.ok
