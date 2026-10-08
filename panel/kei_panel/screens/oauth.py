"""The sign-in of a cloud service that needs a browser (OneDrive), from a
panel that may be on a server with none.

The screen shows the service's sign-in address with 📋 Copy link and Open
buttons, and a box for what comes back: the address the browser ended on
(http://localhost:53682/?code=...), handed to rclone on this server, or a
token made with rclone on another computer. When rclone has the token the
screen closes with it (cloud.Authorizer does the rclone part).
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from .. import cloud
from ..i18n import t
from .dialogs import FitsScreen


class OAuthScreen(FitsScreen, ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, title: str, service: str, authorizer: cloud.Authorizer):
        super().__init__()
        self._title, self._service, self.authorizer = title, service, authorizer
        self.url = ""
        self._done = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide", id="oauth"):
            yield Label(self._title, classes="dialog-title")
            with VerticalScroll(classes="dialog-scroll"):
                yield Static("\n".join([
                    t("1. Copy the link below and open it in a browser, on any computer."),
                    t("2. Sign in to ${service} with the library's account and allow access.", service=self._service),
                    t("3. The browser then goes to a page that does not open (localhost:53682). That is expected: "
                      "copy the whole address from the address bar and paste it below."),
                ]), classes="dialog-body", markup=False)
                yield Static(t("Starting the sign-in..."), id="oauth-link", classes="dialog-body", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("📋 Copy link"), id="oauth-copy", variant="primary")
                yield Button(t("Open in the browser"), id="oauth-open")
            yield Label(t("The address the browser ended on, or a token made with rclone:"), classes="dialog-prompt")
            yield Input(id="oauth-paste", placeholder="http://localhost:53682/?code=...")
            yield Label("", id="oauth-status", classes="dialog-error")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("OK"), id="ok", variant="primary")
                yield Button(t("Cancel"), id="cancel")

    def on_mount(self) -> None:
        super().on_mount()
        self.query_one("#oauth-copy").disabled = True
        self.query_one("#oauth-open").disabled = True
        self.run_worker(self._sign_in(), group="oauth", exit_on_error=False)

    async def _sign_in(self) -> None:
        try:
            self.url = await self.authorizer.start()
        except (RuntimeError, OSError) as e:
            self._status(str(e))
            return
        self.query_one("#oauth-link", Static).update(self.url)
        self.query_one("#oauth-copy").disabled = False
        self.query_one("#oauth-open").disabled = False
        self.query_one("#oauth-paste", Input).focus()
        try:
            token = await self.authorizer.token()
        except (RuntimeError, OSError) as e:
            if not self._done:
                self._status(str(e))
            return
        self._finish(token)

    def _status(self, text: str) -> None:
        self.query_one("#oauth-status", Label).update(text)

    def _finish(self, token: str | None) -> None:
        if not self._done:
            self._done = True
            self.dismiss(token)

    @on(Button.Pressed, "#oauth-copy")
    def _copy(self, event: Button.Pressed) -> None:
        if self.url:
            self.app.copy_to_clipboard(self.url)

    @on(Button.Pressed, "#oauth-open")
    def _open(self) -> None:
        if self.url:
            self.app.open_url(self.url)

    @on(Input.Submitted, "#oauth-paste")
    @on(Button.Pressed, "#ok")
    def _accept(self) -> None:
        pasted = cloud.classify(self.query_one("#oauth-paste", Input).value)
        if pasted.kind == "token":
            self.run_worker(self._stop_then(pasted.value), group="oauth-stop", exit_on_error=False)
        elif pasted.kind == "redirect":
            self._status(t("Finishing the sign-in on this server..."))
            self.run_worker(self.authorizer.answer(pasted.value), group="oauth-answer", exit_on_error=False)
        else:
            self._status(t(pasted.problem))

    async def _stop_then(self, token: str) -> None:
        self._done = True
        await self.authorizer.stop()
        self.dismiss(token)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.run_worker(self._cancel(), group="oauth-stop", exit_on_error=False)

    async def _cancel(self) -> None:
        self._done = True
        await self.authorizer.stop()
        self.dismiss(None)
