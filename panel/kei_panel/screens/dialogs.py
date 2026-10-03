"""Small modals: confirm a step, pick an option, type a value, show a
task's result. Every routine screen is built from these."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, RichLog, SelectionList, Static, TextArea
from textual.widgets.option_list import Option

from ..i18n import t
from ..tasks import TaskResult


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "no", t("No")), Binding("y", "yes", t("Yes"))]

    def __init__(self, title: str, question: str, danger: bool = False, preview: str = "",
                 preview_title: str = ""):
        super().__init__()
        self._title, self._question, self._danger = title, question, danger
        self._preview, self._preview_title = preview, preview_title

    def compose(self) -> ComposeResult:
        classes = "dialog -error" if self._danger else "dialog"
        with Vertical(classes=classes + (" -wide" if self._preview else "")):
            yield Label(self._title, classes="dialog-title")
            if self._preview:
                if self._preview_title:
                    yield Label(self._preview_title, classes="dialog-prompt")
                with VerticalScroll(classes="dialog-scroll dialog-preview"):
                    yield Static(self._preview.strip("\n"), markup=False)
            yield Static(self._question, classes="dialog-body", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Yes"), id="yes", variant="error" if self._danger else "primary")
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


class ChoiceScreen(ModalScreen[str | None]):
    """One of a few options (the whiptail --menu of a routine)."""

    BINDINGS = [Binding("escape", "back", t("Back"))]

    def __init__(self, title: str, prompt: str, options: list[tuple[str, str]], note: str = "",
                 default: str = ""):
        super().__init__()
        self._title, self._prompt, self._options, self._note = title, prompt, options, note
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._prompt, classes="dialog-body", markup=False)
            yield OptionList(*[Option(label, id=key) for key, label in self._options], classes="dialog-options")
            if self._note:
                yield Static(self._note, classes="dialog-note", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Back"), id="back")

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        keys = [key for key, _ in self._options]
        if self._default in keys:
            options.highlighted = keys.index(self._default)
        options.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option.id)

    @on(Button.Pressed, "#back")
    def action_back(self) -> None:
        self.dismiss(None)


class InputScreen(ModalScreen[str | None]):
    """Instructions and one value to type or paste (a token, a name)."""

    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, title: str, instructions: str, prompt: str, validate=None, password: bool = False,
                 value: str = ""):
        super().__init__()
        self._title, self._instructions, self._prompt = title, instructions, prompt
        self._validate, self._password, self._value = validate, password, value

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide"):
            yield Label(self._title, classes="dialog-title")
            if self._instructions:
                with VerticalScroll(classes="dialog-scroll"):
                    yield Static(self._instructions, classes="dialog-body", markup=False)
            yield Label(self._prompt, classes="dialog-prompt")
            yield Input(self._value, password=self._password, id="value")
            yield Label("", id="input-error", classes="dialog-error")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")
                yield Button(t("Cancel"), id="cancel")

    def on_mount(self) -> None:
        self.query_one("#value", Input).focus()

    @on(Input.Submitted, "#value")
    @on(Button.Pressed, "#ok")
    def _accept(self) -> None:
        value = self.query_one("#value", Input).value.strip()
        error = self._validate(value) if self._validate else ("" if value else t("Cannot be empty."))
        if error:
            self.query_one("#input-error", Label).update(error)
            return
        self.dismiss(value)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class MessageScreen(ModalScreen[None]):
    """The end of a routine: what happened, its numbers, a command to copy
    and, when it went wrong, the last lines of its output."""

    BINDINGS = [Binding("escape", "close", t("OK"))]

    def __init__(self, title: str, body: str, kind: str = "ok", details: list[tuple[str, str]] | None = None,
                 command: str = "", command_help: str = "", command_notes: str = "",
                 log: list[str] | None = None):
        super().__init__()
        self._title, self._body, self._kind = title, body, kind
        self._details, self._command, self._command_help = details or [], command, command_help
        self._command_notes = command_notes
        self._log = log or []

    def compose(self) -> ComposeResult:
        classes = {"error": "dialog -wide -error", "info": "dialog -wide -info"}.get(self._kind, "dialog -wide -ok")
        with Vertical(classes=classes):
            yield Label(self._title, classes="dialog-title")
            with VerticalScroll(classes="dialog-scroll"):
                if self._body:
                    yield Static(self._body, classes="dialog-body", markup=False)
                for label, value in self._details:
                    with Horizontal(classes="dialog-detail"):
                        yield Label(label, classes="detail-label")
                        yield Static(value, classes="detail-value", markup=False)
                if self._command:
                    if self._command_help:
                        yield Static(self._command_help, classes="dialog-body", markup=False)
                    yield Static(self._command, classes="dialog-command", markup=False)
                    if self._command_notes:
                        yield Static(self._command_notes, classes="dialog-note", markup=False)
            if self._log:
                log = RichLog(classes="dialog-log", wrap=True, markup=False)
                yield log
            with Horizontal(classes="dialog-buttons"):
                if self._command:
                    yield Button(t("Copy"), id="copy")
                yield Button(t("OK"), id="ok", variant="primary")

    def on_mount(self) -> None:
        if self._log:
            log = self.query_one(RichLog)
            for line in self._log[-40:]:
                log.write(line)
        self.query_one("#ok").focus()

    @on(Button.Pressed, "#copy")
    def _copy(self) -> None:
        self.app.copy_to_clipboard(self._command)
        self.notify(t("Copied."), timeout=3)

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


class CredentialsScreen(ModalScreen[None]):
    """Addresses and passwords, grouped, each value on its own line with a
    Copy button (no border or label glued to what is copied)."""

    BINDINGS = [Binding("escape", "close", t("OK"))]

    def __init__(self, title: str, body: str, groups: list[tuple[str, list[tuple[str, str]]]],
                 kind: str = "ok", note: str = "", copy: bool = True):
        super().__init__()
        self._title, self._body, self._groups, self._kind, self._note = title, body, groups, kind, note
        self._copy = copy
        self._values: list[str] = []

    def compose(self) -> ComposeResult:
        classes = {"error": "dialog -wide -error", "info": "dialog -wide -info"}.get(self._kind, "dialog -wide -ok")
        with Vertical(classes=classes):
            yield Label(self._title, classes="dialog-title")
            with VerticalScroll(classes="dialog-scroll"):
                if self._body:
                    yield Static(self._body, classes="dialog-body", markup=False)
                for heading, rows in self._groups:
                    yield Label(heading, classes="dialog-prompt")
                    for label, value in rows:
                        self._values.append(value)
                        with Horizontal(classes="dialog-detail"):
                            yield Label(label, classes="detail-label")
                            yield Static(value, classes="detail-value", markup=False)
                            if self._copy:
                                yield Button(t("Copy"), id=f"copy-{len(self._values) - 1}", classes="detail-copy")
                if self._note:
                    yield Static(self._note, classes="dialog-note", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#ok").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("copy-"):
            event.stop()
            self.app.copy_to_clipboard(self._values[int(bid[5:])])
            self.notify(t("Copied."), timeout=3)

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


class TextScreen(ModalScreen[None]):
    """A long text to read (a report), scrollable, with an OK button."""

    BINDINGS = [Binding("escape", "close", t("OK"))]

    def __init__(self, title: str, text: str, kind: str = "info", body: str = ""):
        super().__init__()
        self._title, self._text, self._kind, self._body = title, text, kind, body

    def compose(self) -> ComposeResult:
        classes = {"error": "dialog -wide -error", "ok": "dialog -wide -ok"}.get(self._kind, "dialog -wide -info")
        with Vertical(classes=classes):
            yield Label(self._title, classes="dialog-title")
            if self._body:
                yield Static(self._body, classes="dialog-body", markup=False)
            with VerticalScroll(classes="dialog-scroll dialog-preview"):
                yield Static(self._text.strip("\n"), markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#ok").focus()

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


class ChecklistScreen(ModalScreen[list[str] | None]):
    """Several options to tick (the whiptail --checklist of a routine)."""

    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, title: str, prompt: str, options: list[tuple[str, str, bool]]):
        super().__init__()
        self._title, self._prompt, self._options = title, prompt, options

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide"):
            yield Label(self._title, classes="dialog-title")
            if self._prompt:
                yield Static(self._prompt, classes="dialog-body", markup=False)
            yield SelectionList[str](*[(label, key, on) for key, label, on in self._options],
                                     classes="dialog-options")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")
                yield Button(t("Cancel"), id="cancel")

    def on_mount(self) -> None:
        self.query_one(SelectionList).focus()

    @on(Button.Pressed, "#ok")
    def _accept(self) -> None:
        self.dismiss(list(self.query_one(SelectionList).selected))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class EditScreen(ModalScreen[bool]):
    """A text file to change by hand (the classic panel opens nano): Save
    writes it back, Cancel leaves it as it was."""

    BINDINGS = [Binding("escape", "cancel", t("Cancel")), Binding("ctrl+s", "save", t("Save"))]

    def __init__(self, title: str, path: str, note: str = ""):
        super().__init__()
        self._title, self._path, self._note = title, path, note

    def compose(self) -> ComposeResult:
        try:
            with open(self._path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            text = ""
        with Vertical(classes="dialog -wide -log"):
            yield Label(self._title, classes="dialog-title")
            if self._note:
                yield Static(self._note, classes="dialog-note", markup=False)
            yield TextArea(text, id="editor", classes="dialog-editor", show_line_numbers=True)
            yield Label("", id="edit-error", classes="dialog-error")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Save"), id="save", variant="primary")
                yield Button(t("Cancel"), id="cancel")

    def on_mount(self) -> None:
        self.query_one("#editor").focus()

    @on(Button.Pressed, "#save")
    def action_save(self) -> None:
        text = self.query_one("#editor", TextArea).text
        if text and not text.endswith("\n"):
            text += "\n"
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            self.query_one("#edit-error", Label).update(f"{self._path}: {exc.strerror}")
            return
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)
