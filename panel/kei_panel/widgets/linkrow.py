"""LinkRow: an outside web address with a short note, an Open button and a
Copy button. Used where the panel sends the person to another site for
something it cannot do itself: an image host (OPAC and Staff Appearance),
the page that makes an AI API key (AI), the WhatsApp gateway (Messaging).

Open goes through app.open_url (opener.py: copies the address when no
browser can be opened from here); Copy through app.copy_to_clipboard.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from ..i18n import t
from .copy import CopyButton


class LinkRow(Vertical):
    DEFAULT_CSS = """
    LinkRow {
        height: auto;
        margin: 0 0 1 0;
    }
    LinkRow .link-row-line {
        height: auto;
    }
    LinkRow .link-row-url {
        width: 1fr;
        padding: 1 1 0 1;
        color: $accent;
        text-style: underline;
    }
    LinkRow Button {
        margin-left: 1;
    }
    """

    def __init__(self, url: str, note: str = "", name: str = "", **kwargs):
        super().__init__(**kwargs)
        self.url, self.note, self.title = url, note, name
        self.add_class("link-helper")

    def compose(self) -> ComposeResult:
        if self.note:
            yield Static(self.note, classes="ai-note", markup=False)
        with Horizontal(classes="link-row-line"):
            yield Label((f"{self.title}: " if self.title else "") + self.url, classes="link-row-url", markup=False)
            yield Button(t("🔗 Open link"), classes="small link-row-open", tooltip=self.url)
            yield CopyButton(classes="small link-row-copy", tooltip=t("Copy the address"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.has_class("link-row-open"):
            event.stop()
            self.app.open_url(self.url)
        elif event.button.has_class("link-row-copy"):
            event.stop()           # CopyButton has flashed already
            self.app.copy_to_clipboard(self.url)
