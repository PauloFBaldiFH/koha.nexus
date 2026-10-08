"""A VPN device's profile: its QR code for the WireGuard app on a phone,
and a Copy button for a computer (the .conf text goes to the clipboard of
the computer the person is at, also over SSH)."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ..i18n import t
from .dialogs import FitsScreen


class ProfileScreen(FitsScreen, ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", t("Close"))]

    def __init__(self, name: str, profile: str, code: str):
        super().__init__()
        self._name, self.profile, self.code = name, profile, code

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide -info", id="vpn-profile"):
            yield Label(t("VPN profile: ${name}", name=self._name), classes="dialog-title")
            yield Static(t("Phone: open the WireGuard app, tap + and scan the code. Computer: install WireGuard, "
                           "Copy profile, then in WireGuard choose Import tunnel from file or Add empty tunnel and "
                           "paste it. Only the library's addresses (10.66.0.x) go through the VPN."),
                         classes="dialog-body", markup=False)
            with VerticalScroll(classes="dialog-scroll", id="vpn-qr-box"):
                if self.code:
                    yield Static(Text.from_ansi(self.code), id="vpn-qr")
                else:
                    yield Static(t("qrencode is not installed: use Copy profile."), id="vpn-qr", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("📋 Copy profile (.conf)"), id="vpn-copy", variant="primary")
                yield Button(t("Close"), id="close")

    def _fit(self) -> None:
        # The code is read whole by a camera: it gets every row the
        # terminal has left, not the usual 24 of a dialog's text.
        dialog = self.query_one("#vpn-profile")
        box = self.query_one("#vpn-qr-box")
        others = sum(w.outer_size.height for w in dialog.children if w is not box and w.display)
        room = int(self.size.height * 0.95) - dialog.styles.gutter.height - others
        box.styles.max_height = max(3, room)

    @on(Button.Pressed, "#vpn-copy")
    def _copy(self) -> None:
        self.app.copy_to_clipboard(self.profile)

    @on(Button.Pressed, "#close")
    def action_close(self) -> None:
        self.dismiss(None)
