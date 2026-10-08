"""Small modals: confirm a step, pick an option, type a value, show a
task's result. Every routine screen is built from these."""

from __future__ import annotations

import re

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, RichLog, SelectionList, Static, TextArea
from textual.widgets.option_list import Option

from ..i18n import t
from ..tasks import TaskResult
from ..widgets.copy import CopyButton


class FitsScreen:
    """Keeps a dialog's buttons whole on a short terminal: its scrolling part
    (long text, log, list of options) gets only the rows left over by the
    title, the texts and the buttons, so it scrolls instead of pushing the
    buttons off the dialog (a blank or cut "OK")."""

    def on_mount(self) -> None:
        self.call_after_refresh(self._fit)

    def on_resize(self) -> None:
        self.call_after_refresh(self._fit)

    def _fit(self) -> None:
        dialogs = list(self.query(".dialog"))
        parts = list(self.query(".dialog-scroll, .dialog-options"))
        if not dialogs or not parts or parts[0].parent is not dialogs[0]:
            return
        dialog, part = dialogs[0], parts[0]
        others = sum(w.outer_size.height for w in dialog.children if w is not part and w.display)
        room = int(self.size.height * 0.9) - dialog.styles.gutter.height - others \
            - part.styles.gutter.height - part.styles.margin.height
        cap = 24 if "dialog-scroll" in part.classes else 12
        part.styles.max_height = max(3, min(cap, room)) + part.styles.gutter.height


# What a person may want to paste elsewhere: addresses, recovery codes, a
# Bitcoin address, and the key on a "Pix" line (only there: a CPF in a
# report is not something to copy).
_PIX = re.compile(r"\bPix\b[^:\n]*:\s*(\S+)", re.I)
_OTHER = re.compile(r"https?://[^\s\"'<>]+|\b[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}\b|\bbc1[02-9ac-hj-np-z]{11,71}\b")


def copyable(text: str) -> list[str]:
    """The addresses, codes and Pix/Bitcoin keys in a dialog's text, in
    order, once each."""
    text = text or ""
    hits = [(m.start(1), m.group(1)) for m in _PIX.finditer(text)]
    hits += [(m.start(), m.group(0)) for m in _OTHER.finditer(text)]
    found: list[str] = []
    for _, value in sorted(hits):
        value = value.rstrip(".,;:)!?") if value.startswith("http") else value
        if value not in found:
            found.append(value)
    return found


class CopyValues:
    """Copy buttons (id "copy-N") for a dialog's values, and the "c" key,
    which copies the value whose button has the focus, else the first one.
    The app puts the text on the clipboard (OSC 52, so over SSH it lands on
    the person's own computer) and says "Copied."."""

    _values: list[str]

    def copy_rows(self, values: list[str], command: bool = False):
        for value in values:
            self._values.append(value)
            with Horizontal(classes="dialog-detail"):
                yield Static(value, classes="detail-value", markup=False)
                yield CopyButton(command=command, id=f"copy-{len(self._values) - 1}", classes="detail-copy")

    def action_copy(self) -> None:
        if not self._values:
            return
        bid = getattr(self.focused, "id", None) or ""
        index = int(bid[5:]) if bid.startswith("copy-") else 0
        self.app.copy_to_clipboard(self._values[index])
        for button in self.query(f"#copy-{index}, #copy").results(CopyButton):
            button.flash()
            break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("copy-"):
            event.stop()
            self.app.copy_to_clipboard(self._values[int(bid[5:])])


class ConfirmScreen(FitsScreen, CopyValues, ModalScreen[bool]):
    BINDINGS = [Binding("escape", "no", t("No")), Binding("y", "yes", t("Yes")),
                Binding("c", "copy", t("Copy"), show=False)]

    def __init__(self, title: str, question: str, danger: bool = False, preview: str = "",
                 preview_title: str = ""):
        super().__init__()
        self._title, self._question, self._danger = title, question, danger
        self._preview, self._preview_title = preview, preview_title
        self._values: list[str] = []

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
            yield from self.copy_rows(copyable(self._question))
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


class ResultScreen(FitsScreen, ModalScreen[None]):
    """A failed task: what failed and the last lines of its output."""

    BINDINGS = [Binding("escape,enter", "close", t("OK"))]

    def __init__(self, title: str, result: TaskResult):
        super().__init__()
        self._title, self._result = title, result

    def compose(self) -> ComposeResult:
        r = self._result
        with Vertical(classes="dialog -error"):
            yield Label(self._title, classes="dialog-title")
            # Text and log scroll together: on a short terminal they give
            # way, never the OK button below them.
            with VerticalScroll(classes="dialog-scroll"):
                yield Label(r.error or t("Cancelled"), classes="dialog-body")
                yield RichLog(classes="dialog-log -inner", wrap=True, markup=False)
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


class ChoiceScreen(FitsScreen, CopyValues, ModalScreen[str | None]):
    """One of a few options (the whiptail --menu of a routine)."""

    BINDINGS = [Binding("escape", "back", t("Back")), Binding("c", "copy", t("Copy"), show=False)]

    def __init__(self, title: str, prompt: str, options: list[tuple[str, str]], note: str = "",
                 default: str = ""):
        super().__init__()
        self._title, self._prompt, self._options, self._note = title, prompt, options, note
        self._default = default
        self._values: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._prompt, classes="dialog-body", markup=False)
            yield from self.copy_rows(copyable(self._prompt))
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


class InputScreen(FitsScreen, CopyValues, ModalScreen[str | None]):
    """Instructions and one value to type or paste (a token, a name)."""

    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, title: str, instructions: str, prompt: str, validate=None, password: bool = False,
                 value: str = "", commands: list[str] | None = None):
        super().__init__()
        self._title, self._instructions, self._prompt = title, instructions, prompt
        self._validate, self._password, self._value = validate, password, value
        self._commands = commands or []
        self._values: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide"):
            yield Label(self._title, classes="dialog-title")
            if self._instructions:
                with VerticalScroll(classes="dialog-scroll"):
                    yield Static(self._instructions, classes="dialog-body", markup=False)
                    yield from self.copy_rows(self._commands, command=True)
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


class MessageScreen(FitsScreen, CopyValues, ModalScreen[str | None]):
    """The end of a routine: what happened, its numbers, a command to copy
    (else the addresses and codes in its text) and, when it went wrong, the
    last lines of its output."""

    BINDINGS = [Binding("escape", "close", t("OK")), Binding("c", "copy", t("Copy"), show=False)]

    def __init__(self, title: str, body: str, kind: str = "ok", details: list[tuple[str, str]] | None = None,
                 command: str = "", command_help: str = "", command_notes: str = "",
                 log: list[str] | None = None, is_command: bool = True, extra: str = ""):
        super().__init__()
        # extra: the label of one more button; pressing it closes the
        # dialog with "extra" (else None).
        self._extra = extra
        # "command" is shown to copy: a command (📋 Copy command), or a path
        # or a password (is_command=False: 📋 Copy).
        self._command_is_command = is_command
        self._title, self._body, self._kind = title, body, kind
        self._details, self._command, self._command_help = details or [], command, command_help
        self._command_notes = command_notes
        self._log = log or []
        self._values: list[str] = [command] if command else []

    def compose(self) -> ComposeResult:
        classes = {"error": "dialog -wide -error", "info": "dialog -wide -info"}.get(self._kind, "dialog -wide -ok")
        with Vertical(classes=classes):
            yield Label(self._title, classes="dialog-title")
            with VerticalScroll(classes="dialog-scroll"):
                if self._body:
                    yield Static(self._body, classes="dialog-body", markup=False)
                if not self._command:
                    yield from self.copy_rows(copyable(self._body))
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
                    yield CopyButton(command=self._command_is_command, id="copy")
                if self._extra:
                    yield Button(self._extra, id="extra", variant="success")
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

    @on(Button.Pressed, "#extra")
    def _extra_pressed(self) -> None:
        self.dismiss("extra")

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


class CredentialsScreen(FitsScreen, CopyValues, ModalScreen[None]):
    """Addresses and passwords, grouped, each value on its own line with a
    Copy button (no border or label glued to what is copied)."""

    BINDINGS = [Binding("escape", "close", t("OK")), Binding("c", "copy", t("Copy"), show=False)]

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
                        with Horizontal(classes="dialog-detail"):
                            yield Label(label, classes="detail-label")
                            yield Static(value, classes="detail-value", markup=False)
                            if self._copy:
                                self._values.append(value)
                                yield CopyButton(id=f"copy-{len(self._values) - 1}", classes="detail-copy")
                if self._note:
                    yield Static(self._note, classes="dialog-note", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#ok").focus()

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


class TextScreen(FitsScreen, CopyValues, ModalScreen[None]):
    """A long text to read (a report), scrollable, with an OK button, and
    Copy buttons for the first addresses and keys in it (About: the Pix
    key, the Bitcoin address, the repository)."""

    BINDINGS = [Binding("escape", "close", t("OK")), Binding("c", "copy", t("Copy"), show=False)]
    MAX_COPY = 6

    def __init__(self, title: str, text: str, kind: str = "info", body: str = ""):
        super().__init__()
        self._title, self._text, self._kind, self._body = title, text, kind, body
        self._values: list[str] = []

    def compose(self) -> ComposeResult:
        classes = {"error": "dialog -wide -error", "ok": "dialog -wide -ok"}.get(self._kind, "dialog -wide -info")
        with Vertical(classes=classes):
            yield Label(self._title, classes="dialog-title")
            if self._body:
                yield Static(self._body, classes="dialog-body", markup=False)
            with VerticalScroll(classes="dialog-scroll dialog-preview"):
                yield Static(self._text.strip("\n"), markup=False)
            yield from self.copy_rows(copyable(self._text)[:self.MAX_COPY])
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#ok").focus()

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


class ChecklistScreen(FitsScreen, ModalScreen[list[str] | None]):
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
