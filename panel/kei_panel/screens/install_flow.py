"""The shared screens of an installation (study section 8 and 16.3).

Koha, Tainacan and DSpace follow one route:

    initial diagnosis -> name and address -> summary -> stages -> final
    diagnosis -> completion

- CheckReportScreen: a list of checks, each with its mark and the reason.
  Before installing it is read only ("Nothing was changed so far.") and its
  Continue is off while any check failed; after installing it is the final
  report.
- PlanSummaryScreen: what will be installed, in plain lines, with the
  engine's technical plan (JSON) one button away, never in front.

The progress in stages is the loader's (bridge.stage_parts reads the
"@@stage [n/N]" lines both engines write).
"""

from __future__ import annotations

from typing import Iterable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ..i18n import t
from .dialogs import FitsScreen, TextScreen, _focus_first

OK, WARN, FAIL = "ok", "warn", "fail"
MARKS = {OK: "✔", WARN: "⚠", FAIL: "✖"}

# A check row: (state, label, detail). The label is shown translated, the
# detail as it came (numbers, names, a reason already in the person's language).
Check = tuple[str, str, str]


def worst(rows: Iterable[Check]) -> str:
    states = {state for state, _l, _d in rows}
    return FAIL if FAIL in states else WARN if WARN in states else OK


class CheckReportScreen(FitsScreen, ModalScreen[bool]):
    """Checks before (final=False) or after (final=True) an installation."""

    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, title: str, rows: list[Check], body: str = "", final: bool = False,
                 details: str = "", details_title: str = ""):
        super().__init__()
        self._title, self._rows, self._body, self._final = title, rows, body, final
        self._details, self._details_title = details, details_title

    def compose(self) -> ComposeResult:
        state = worst(self._rows)
        kind = {FAIL: "-error", WARN: "-info"}.get(state, "-ok")
        with Vertical(classes=f"dialog -wide {kind}", id="check-report"):
            yield Label(self._title, classes="dialog-title", markup=False)
            if self._body:
                yield Static(self._body, classes="dialog-body", markup=False)
            with VerticalScroll(classes="dialog-scroll"):
                for i, (row_state, label, detail) in enumerate(self._rows):
                    with Horizontal(classes=f"check-row -{row_state}", id=f"check-{i}"):
                        yield Static(MARKS.get(row_state, "?"), classes="check-mark", markup=False)
                        yield Label(t(label), classes="check-label", markup=False)
                        yield Static(detail, classes="check-detail", markup=False)
            if not self._final:
                note = (t("Nothing was changed so far. Fix the items marked ✖ and open the installation again.")
                        if state == FAIL else t("Nothing was changed so far."))
                yield Static(note, classes="dialog-note", id="check-note", markup=False)
            with Horizontal(classes="dialog-buttons"):
                if self._details:
                    yield Button(t("Technical details"), id="details")
                if self._final:
                    yield Button(t("OK"), id="ok", variant="primary")
                else:
                    yield Button(t("Continue"), id="continue", variant="primary", disabled=state == FAIL)
                    yield Button(t("Cancel"), id="cancel")

    def on_mount(self) -> None:
        super().on_mount()
        _focus_first(self, "#ok" if self._final else "#cancel" if worst(self._rows) == FAIL else "#continue")

    @on(Button.Pressed, "#details")
    def _show_details(self) -> None:
        self.app.push_screen(TextScreen(self._details_title or t("Technical details"), self._details))

    @on(Button.Pressed, "#continue")
    def _continue(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(self._final)


class PlanSummaryScreen(FitsScreen, ModalScreen[bool]):
    """"Review and install": plain lines, the technical plan behind a button."""

    BINDINGS = [Binding("escape", "back", t("Back"))]

    def __init__(self, title: str, rows: list[tuple[str, str]], body: str = "", details: str = "",
                 note: str = "", action: str = ""):
        super().__init__()
        self._title, self._rows, self._body, self._details = title, rows, body, details
        self._note, self._action = note, action or t("Install")

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide", id="plan-summary"):
            yield Label(self._title, classes="dialog-title", markup=False)
            if self._body:
                yield Static(self._body, classes="dialog-body", markup=False)
            with VerticalScroll(classes="dialog-scroll"):
                for label, value in self._rows:
                    with Horizontal(classes="dialog-detail plan-row"):
                        yield Label(label, classes="detail-label", markup=False)
                        yield Static(value, classes="detail-value", markup=False)
            if self._note:
                yield Static(self._note, classes="dialog-note", markup=False)
            with Horizontal(classes="dialog-buttons"):
                if self._details:
                    yield Button(t("Technical details"), id="details")
                yield Button(self._action, id="install", variant="primary")
                yield Button(t("Back"), id="back")

    def on_mount(self) -> None:
        super().on_mount()
        _focus_first(self, "#install")

    @on(Button.Pressed, "#details")
    def _show_details(self) -> None:
        self.app.push_screen(TextScreen(t("Technical details"), self._details))

    @on(Button.Pressed, "#install")
    def _install(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#back")
    def action_back(self) -> None:
        self.dismiss(False)
