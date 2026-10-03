"""The one pattern every heavy task uses: worker + Pac-Man loader.

    run_with_loader(app, t("Saving a safety backup"), job, on_done=callback)

`job` is either
  * an async function  `async def job(reporter) -> value`, run as an async
    worker on the event loop (subprocesses, network: bridge.stream), or
  * a plain function   `def job(reporter) -> value`, run in a thread worker
    (CPU-bound Python: parsing a MARC file, building a report).
Either way the LoadingScreen is pushed first, so Pac-Man is on screen
before the work starts, keeps moving because the work never blocks the
event loop, and the screen dismisses itself with a TaskResult when the
worker ends (success, error or cancel). `on_done` receives that result.

The Reporter is the job's only handle on the screen. Its methods are safe
from both kinds of worker: from a thread they hop to the app's thread
with call_from_thread.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Union

if TYPE_CHECKING:
    from textual.app import App

    from .screens.loading import LoadingScreen

Job = Union[Callable[["Reporter"], Awaitable[Any]], Callable[["Reporter"], Any]]


class TaskFailed(RuntimeError):
    """Raised by a job to end as a failure with a readable message."""

    def __init__(self, message: str, rc: int | None = None):
        super().__init__(message)
        self.rc = rc


@dataclass
class TaskResult:
    ok: bool
    value: Any = None
    error: str = ""
    cancelled: bool = False
    log: list[str] = field(default_factory=list)
    seconds: float = 0.0


class Reporter:
    """What a running job may tell the loader."""

    def __init__(self, screen: "LoadingScreen"):
        self._screen = screen
        self._app_thread = threading.get_ident()
        self.lines: deque[str] = deque(maxlen=500)
        self._cancel = threading.Event()

    def _call(self, fn: Callable, *args: Any) -> None:
        if threading.get_ident() == self._app_thread:
            fn(*args)
        else:
            self._screen.app.call_from_thread(fn, *args)

    def log(self, line: str) -> None:
        self.lines.append(line)
        self._call(self._screen.add_log, line)

    def status(self, text: str) -> None:
        self._call(self._screen.set_status, text)

    def notice(self, text: str) -> None:
        """A text the person must read while the task runs (a link to open)."""
        self._call(self._screen.set_notice, text)

    def progress(self, current: float, total: float) -> None:
        """Switches Pac-Man to determinate mode (current of total)."""
        self._call(self._screen.set_progress, current / total if total else None)

    @property
    def cancelled(self) -> bool:
        """Thread jobs poll this; async jobs get CancelledError instead."""
        return self._cancel.is_set()

    def _request_cancel(self) -> None:
        self._cancel.set()


def is_async_job(job: Job) -> bool:
    return inspect.iscoroutinefunction(job) or inspect.iscoroutinefunction(getattr(job, "__call__", None))


def run_with_loader(app: "App", title: str, job: Job,
                    on_done: Callable[[TaskResult], Any] | None = None) -> None:
    """Show the Pac-Man loader and run job in a worker behind it."""
    from .screens.loading import LoadingScreen

    app.push_screen(LoadingScreen(title, job), callback=on_done)


def verb_job(bridge, verb: tuple[str, ...]) -> Callable[["Reporter"], Awaitable[int]]:
    """An installer verb as a job: a non-zero exit ends as a failure."""
    async def job(reporter: Reporter) -> int:
        rc = await bridge.run_verb(verb, reporter)
        if rc != 0:
            tail = " / ".join(list(reporter.lines)[-3:])
            raise TaskFailed(f"exit {rc}" + (f": {tail}" if tail else ""), rc)
        return rc
    return job


def task_job(bridge, name: str, *args: str, env: dict[str, str] | None = None, total_steps: int = 0,
             on_result: Callable[["Reporter", str, str], None] | None = None, ask=None
             ) -> Callable[["Reporter"], Awaitable[Any]]:
    """A ported routine (`config.sh --task`) as a job. It returns the
    TaskOutcome whatever happened: the routine's own boxes say what went
    wrong, and the screen that follows shows them."""
    async def job(reporter: Reporter):
        cb = (lambda k, v: on_result(reporter, k, v)) if on_result else None
        return await bridge.task(name, *args, reporter=reporter, env=env,
                                 total_steps=total_steps, on_result=cb, ask=ask)
    return job


async def sleep_job(reporter: Reporter, seconds: float = 3.0) -> str:
    """Example async job, used by the demo and the tests."""
    steps = 20
    for i in range(steps):
        reporter.progress(i + 1, steps)
        await asyncio.sleep(seconds / steps)
    return "done"
