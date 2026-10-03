"""Following a log file live (the classic panel's `tail -f | grep`)."""

from __future__ import annotations

import re
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from ..i18n import t

_BAD = re.compile(r"error|fatal|denied|fail", re.I)
_WARN = re.compile(r"warn", re.I)


def style_line(line: str) -> Text:
    """Errors red, warnings yellow, the rest plain."""
    if _BAD.search(line):
        return Text(line, style="bold red")
    if _WARN.search(line):
        return Text(line, style="yellow")
    return Text(line)


class LogTailScreen(ModalScreen[None]):
    """The last lines of a file, then every new line as it is written."""

    BINDINGS = [Binding("escape", "close", t("Back")), Binding("p", "pause", t("Pause"))]

    def __init__(self, title: str, path: str, lines: int = 50, interval: float = 1.0):
        super().__init__()
        self._title, self._path, self._lines, self._interval = title, Path(path), lines, interval
        self._offset = 0
        self._paused = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide -log"):
            yield Label(self._title, classes="dialog-title")
            yield Label(str(self._path), classes="dialog-note")
            yield RichLog(classes="dialog-log -tall", wrap=True, markup=False, max_lines=2000)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Pause"), id="pause")
                yield Button(t("Back"), id="back", variant="primary")

    def on_mount(self) -> None:
        self._first_read()
        self.set_interval(self._interval, self._follow)
        self.query_one("#back").focus()

    def _write(self, lines: list[str]) -> None:
        log = self.query_one(RichLog)
        for line in lines:
            log.write(style_line(line))

    def _first_read(self) -> None:
        try:
            with self._path.open("rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 256 * 1024))
                data = fh.read()
                self._offset = fh.tell()
        except OSError as exc:
            self._write([f"{t('Log file not found: ${log_file}', log_file=str(self._path))} ({exc.strerror})"])
            return
        self._write(data.decode("utf-8", "replace").splitlines()[-self._lines:])

    def _follow(self) -> None:
        if self._paused:
            return
        try:
            with self._path.open("rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                if size < self._offset:      # rotated or truncated
                    self._offset = 0
                fh.seek(self._offset)
                data = fh.read()
                self._offset = fh.tell()
        except OSError:
            return
        if data:
            self._write(data.decode("utf-8", "replace").splitlines())

    @on(Button.Pressed, "#pause")
    def action_pause(self) -> None:
        self._paused = not self._paused
        self.query_one("#pause", Button).label = t("Continue") if self._paused else t("Pause")

    @on(Button.Pressed, "#back")
    def action_close(self) -> None:
        self.dismiss(None)
