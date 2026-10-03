"""LoadingScreen: the modal that every heavy task runs behind.

Pushed by tasks.run_with_loader. It starts the job in a worker on mount,
animates Pac-Man while the worker runs, and dismisses itself with a
TaskResult. Esc or the Cancel button cancels the worker (an installer
subprocess is terminated, a thread job sees reporter.cancelled), unless
the task must not be stopped halfway (a restore): cancellable=False.
"""

from __future__ import annotations

import time

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog, Static
from textual.worker import Worker, WorkerState

from ..i18n import t
from ..tasks import Job, Reporter, TaskFailed, TaskResult, is_async_job
from ..widgets.pacman import PacmanLoader

# A task shorter than this still shows the loader this long: no flash.
MIN_SECONDS = 0.6


class LoadingScreen(ModalScreen[TaskResult]):
    BINDINGS = [
        Binding("escape", "cancel", t("Cancel")),
        Binding("l", "toggle_log", "Log"),
    ]

    def __init__(self, title: str, job: Job, cancellable: bool = True):
        super().__init__()
        self.title_text = title
        self.job = job
        self.cancellable = cancellable
        self.reporter = Reporter(self)
        self.started = 0.0
        self.worker: Worker | None = None

    def compose(self) -> ComposeResult:
        plain = getattr(self.app, "env", None) and self.app.env.plain
        colors = not (getattr(self.app, "env", None) and self.app.env.no_color)
        with Vertical(id="loader-box"):
            yield Label(self.title_text, id="loader-title")
            yield PacmanLoader(plain=bool(plain), colors=colors, id="pacman")
            yield Static("", id="loader-notice")
            with Horizontal(id="loader-meta"):
                yield Label("", id="loader-status")
                yield Label("", id="loader-clock")
            yield RichLog(id="loader-log", max_lines=500, wrap=False, markup=False)
            with Horizontal(id="loader-buttons"):
                yield Button("Log", id="toggle-log", variant="default")
                yield Button(t("Cancel"), id="cancel", variant="error")

    def on_mount(self) -> None:
        self.started = time.monotonic()
        self.query_one("#loader-log").display = False
        self.query_one("#loader-notice").display = False
        if not self.cancellable:
            self.query_one("#cancel").display = False
        self.set_interval(0.5, self._update_clock)
        if is_async_job(self.job):
            self.worker = self.run_worker(self._run_async(), name="task", exit_on_error=False)
        else:
            self.worker = self.run_worker(self._run_thread, name="task", thread=True, exit_on_error=False)

    async def _run_async(self):
        return await self.job(self.reporter)

    def _run_thread(self):
        return self.job(self.reporter)

    # ------------------------------------------------------------------
    # Called by the Reporter (always on the app's thread)
    # ------------------------------------------------------------------
    def add_log(self, line: str) -> None:
        self.query_one("#loader-log", RichLog).write(line)
        if not self.query_one("#loader-status", Label).content:
            self.query_one("#loader-status", Label).update(line[:60])

    def set_status(self, text: str) -> None:
        self.query_one("#loader-status", Label).update(text)

    def set_notice(self, text: str) -> None:
        notice = self.query_one("#loader-notice", Static)
        notice.update(text)
        notice.display = bool(text)

    def set_progress(self, fraction: float | None) -> None:
        self.query_one(PacmanLoader).progress = fraction
        self._update_clock()

    def _update_clock(self) -> None:
        secs = int(time.monotonic() - self.started)
        fraction = self.query_one(PacmanLoader).progress
        pct = f"{round(fraction * 100):3d}%  " if fraction is not None else ""
        self.query_one("#loader-clock", Label).update(f"{pct}{secs // 60:02d}:{secs % 60:02d}")

    # ------------------------------------------------------------------
    # End of the worker
    # ------------------------------------------------------------------
    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker is not self.worker:
            return
        worker = event.worker
        seconds = time.monotonic() - self.started
        log = list(self.reporter.lines)
        if event.state == WorkerState.SUCCESS:
            result = TaskResult(ok=True, value=worker.result, log=log, seconds=seconds)
        elif event.state == WorkerState.ERROR:
            err = worker.error
            msg = str(err) if isinstance(err, TaskFailed) else f"{type(err).__name__}: {err}"
            result = TaskResult(ok=False, error=msg, log=log, seconds=seconds)
        elif event.state == WorkerState.CANCELLED:
            result = TaskResult(ok=False, cancelled=True, log=log, seconds=seconds)
        else:
            return
        self.query_one(PacmanLoader).pause()
        wait = max(0.0, MIN_SECONDS - seconds)
        self.set_timer(wait or 0.01, lambda: self._finish(result))

    def _finish(self, result: TaskResult) -> None:
        self.dismiss(result)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_cancel(self) -> None:
        if not self.cancellable:
            self.notify(t("Do not interrupt: CTRL+C is disabled until the restore finishes."), severity="warning")
            return
        if self.worker and self.worker.is_running:
            self.reporter._request_cancel()
            self.worker.cancel()
            self.set_status(t("Cancelling..."))

    def action_toggle_log(self) -> None:
        log = self.query_one("#loader-log")
        log.display = not log.display

    @on(Button.Pressed, "#cancel")
    def _cancel_pressed(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#toggle-log")
    def _log_pressed(self) -> None:
        self.action_toggle_log()
