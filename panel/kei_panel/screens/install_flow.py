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

from typing import Iterable, Optional

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
                 note: str = "", action: str = "", danger: bool = False):
        super().__init__()
        self._title, self._rows, self._body, self._details = title, rows, body, details
        self._note, self._action, self._danger = note, action or t("Install"), danger

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide -error" if self._danger else "dialog -wide", id="plan-summary"):
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
                yield Button(self._action, id="install", variant="error" if self._danger else "primary")
                yield Button(t("Back"), id="back")

    def on_mount(self) -> None:
        super().on_mount()
        # A step that replaces data starts on Back, like ConfirmScreen's No.
        _focus_first(self, "#back" if self._danger else "#install")

    @on(Button.Pressed, "#details")
    def _show_details(self) -> None:
        self.app.push_screen(TextScreen(t("Technical details"), self._details))

    @on(Button.Pressed, "#install")
    def _install(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#back")
    def action_back(self) -> None:
        self.dismiss(False)


class CompletionScreen(FitsScreen, ModalScreen[Optional[str]]):
    """The end of an installation, the same for every system (study 8.3).

    A system that still needs a step (DSpace without an administrator) is
    "installed, one step left" in yellow, never "ready". The checks come
    from the final diagnosis, summed up, with the report one button away.
    Returns "action" when its next step was chosen, else None: "Do it
    later" only closes; nothing else opens from here."""

    BINDINGS = [Binding("escape", "later", t("Do it later"))]

    def __init__(self, name: str, checks: list[Check], links: list[tuple[str, str]],
                 facts: list[Check] | None = None, next_step: str = "", action: str = "",
                 note: str = "", reminder: str = "", report_title: str = "", details: str = ""):
        super().__init__()
        self._system, self._checks, self._links = name, checks, links
        self._facts, self._next, self._action = facts or [], next_step, action
        self._note, self._reminder = note, reminder
        self._report_title, self._details = report_title, details

    @property
    def pending(self) -> bool:
        return worst(list(self._checks) + list(self._facts)) != OK

    def compose(self) -> ComposeResult:
        failed = worst(self._checks) == FAIL
        title = (t("${name} is installed, with checks to review", name=self._system) if failed
                 else t("${name} is installed; one step is left", name=self._system) if self.pending
                 else t("${name} is ready", name=self._system))
        kind = "-error" if failed else "-info" if self.pending else "-ok"
        mark = MARKS[FAIL] if failed else MARKS[WARN] if self.pending else MARKS[OK]
        with Vertical(classes=f"dialog -wide {kind}", id="completion"):
            yield Label(f"{mark} {title}", classes="dialog-title", markup=False, id="completion-title")
            with VerticalScroll(classes="dialog-scroll"):
                if self._checks:
                    passed = sum(1 for state, _l, _d in self._checks if state == OK)
                    with Horizontal(classes="dialog-detail completion-row"):
                        yield Label(t("Checks"), classes="detail-label", markup=False)
                        yield Static(f"{MARKS[worst(self._checks)]} " + t("${n} of ${total} passed", n=passed,
                                                                           total=len(self._checks)),
                                     classes="detail-value", markup=False, id="completion-checks")
                        yield Button(t("See the report"), id="report", classes="detail-copy")
                for i, (label, url) in enumerate(self._links):
                    with Horizontal(classes="dialog-detail completion-row"):
                        yield Label(label, classes="detail-label", markup=False)
                        yield Static(url, classes="detail-value", markup=False)
                        yield Button(t("Open"), id=f"open-{i}", classes="detail-copy")
                        yield Button(t("Copy"), id=f"copy-{i}", classes="detail-copy")
                for state, label, value in self._facts:
                    with Horizontal(classes=f"dialog-detail completion-row check-row -{state}"):
                        yield Label(label, classes="detail-label", markup=False)
                        yield Static(f"{MARKS.get(state, '?')} {value}", classes="detail-value check-detail-strong",
                                     markup=False)
                if self._note:
                    yield Static(self._note, classes="dialog-body", markup=False, id="completion-note")
                if self._next:
                    yield Static(self._next, classes="dialog-body completion-next", markup=False,
                                 id="completion-next")
            if self._reminder:
                yield Static(self._reminder, classes="dialog-note completion-reminder", markup=False)
            with Horizontal(classes="dialog-buttons"):
                if self._action:
                    yield Button(self._action, id="action", variant="primary")
                yield Button(t("Do it later") if self._action else t("OK"), id="later",
                             variant="default" if self._action else "primary")

    def on_mount(self) -> None:
        super().on_mount()
        _focus_first(self, "#action" if self._action else "#later")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("open-"):
            event.stop()
            self.app.open_url(self._links[int(bid[5:])][1])
        elif bid.startswith("copy-"):
            event.stop()
            self.app.copy_to_clipboard(self._links[int(bid[5:])][1])
            self.notify(t("Copied."), timeout=2)
        elif bid == "report":
            event.stop()
            self.app.push_screen(CheckReportScreen(self._report_title or t("Checks"), self._checks, final=True,
                                                   details=self._details))
        elif bid == "action":
            event.stop()
            self.dismiss("action")
        elif bid == "later":
            event.stop()
            self.action_later()

    def action_later(self) -> None:
        self.dismiss(None)
