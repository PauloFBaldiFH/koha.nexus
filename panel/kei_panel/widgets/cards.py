"""Cards: the building blocks of every view."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, Static

from ..glyphs import split_icon
from ..i18n import t
from ..menus import Entry


class StatusCard(Vertical):
    """A small read-only fact: title, big value, one quiet line."""

    def __init__(self, title: str, value: str = "…", note: str = "", *, id: str | None = None):
        super().__init__(id=id, classes="status-card")
        self._title, self._value, self._note = title, value, note

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="card-title")
        yield Label(self._value, classes="card-value")
        yield Label(self._note, classes="card-note")

    def set(self, value: str, note: str = "", state: str = "") -> None:
        self.query_one(".card-value", Label).update(value)
        self.query_one(".card-note", Label).update(note)
        for s in ("ok", "warn", "bad"):
            self.set_class(s == state, f"-{s}")


class LinkCard(StatusCard):
    """A web address with Open and Copy buttons (disabled while there is
    none; the note then says why)."""

    class Pressed(Message):
        def __init__(self, url: str, copy: bool):
            super().__init__()
            self.url, self.copy = url, copy

    def __init__(self, title: str, *, id: str | None = None):
        super().__init__(title, "-", id=id)
        self.add_class("link-card")
        self.url = ""

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Horizontal(classes="link-buttons"):
            yield Button(t("Open"), classes="link-open", compact=True, disabled=True)
            yield Button(t("Copy"), classes="link-copy", compact=True, disabled=True)

    def set_url(self, url: str, note: str = "", state: str = "") -> None:
        self.url = url
        self.set(url or "-", note, state)
        for b in self.query(Button):
            b.disabled = not url

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self.url:
            self.post_message(self.Pressed(self.url, event.button.has_class("link-copy")))


class ActionCard(Static, can_focus=True):
    """One routine: clickable, focusable, Enter/Space or a click runs it."""

    class Chosen(Message):
        def __init__(self, entry: Entry):
            super().__init__()
            self.entry = entry

    BINDINGS = [("enter", "choose", "Open"), ("space", "choose", "Open")]

    def __init__(self, entry: Entry, background: bool = False, native: bool = False):
        super().__init__(classes="action-card")
        self.entry = entry
        self.background = background
        self.native = native

    def compose(self) -> ComposeResult:
        icon, text = split_icon(t(self.entry.label))
        yield Label(icon or ">", classes="action-icon")
        yield Label(text, classes="action-text")
        if self.native:
            hint = t("Step by step, in this panel")
        elif self.background:
            hint = t("Runs in the background")
        else:
            hint = t("Opens the classic screens")
        yield Label(hint, classes="action-hint")

    def on_click(self) -> None:
        self.action_choose()

    def action_choose(self) -> None:
        self.post_message(self.Chosen(self.entry))
