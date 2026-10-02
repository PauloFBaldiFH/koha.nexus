"""Small modals: confirm a step, show a task's result."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from ..i18n import t
from ..tasks import TaskResult


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "no", t("No")), Binding("y", "yes", t("Yes"))]

    def __init__(self, title: str, question: str):
        super().__init__()
        self._title, self._question = title, question

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Label(self._question, classes="dialog-body")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Yes"), id="yes", variant="primary")
                yield Button(t("No"), id="no")

    def on_mount(self) -> None:
        self.query_one("#no").focus()

    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)


class ResultScreen(ModalScreen[None]):
    """A failed task: what failed and the last lines of its output."""

    BINDINGS = [Binding("escape,enter", "close", t("OK"))]

    def __init__(self, title: str, result: TaskResult):
        super().__init__()
        self._title, self._result = title, result

    def compose(self) -> ComposeResult:
        r = self._result
        with Vertical(classes="dialog -error"):
            yield Label(self._title, classes="dialog-title")
            yield Label(r.error or t("Cancelled"), classes="dialog-body")
            log = RichLog(classes="dialog-log", wrap=True, markup=False)
            yield log
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        for line in self._result.log[-40:]:
            log.write(line)
        self.query_one("#ok").focus()

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)
