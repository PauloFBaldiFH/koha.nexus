"""WebTransferScreen: a backup sent from, or saved to, the person's computer
through their browser when the panel runs over SSH (webtransfer.py).

It starts the page on mount (in a thread: openssl takes a moment), shows
its addresses with Copy buttons, the certificate's fingerprint and the
ssh -L tunnel for a port the provider's firewall keeps closed, then follows
the transfer. An upload closes the screen with the received file; a
download stays until the person closes it. Closing stops the page.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from .. import transfer
from ..i18n import t
from ..webtransfer import PAGE_TEXTS, TransferError, TransferServer, addresses
from .dialogs import CopyValues, FitsScreen


RECEIVED = "received"   # ~/backups/received: the files sent through the browser


def page_texts() -> dict[str, str]:
    return {key: t(text) for key, text in PAGE_TEXTS.items()}


def browser_server(info: dict, mode: str, file: Path | None = None) -> TransferServer:
    """The page that moves a backup through the person's browser, for the
    addresses of this server their computer may use."""
    hosts = addresses(os.environ.get("SSH_CONNECTION"), info.get("server_ip"))
    folder = Path(info.get("real_home") or "/root") / "backups" / RECEIVED
    return TransferServer(mode, folder=folder, file=file, hosts=hosts, texts=page_texts())


class WebTransferScreen(FitsScreen, CopyValues, ModalScreen[Optional[Path]]):
    BINDINGS = [Binding("escape", "close", t("Close")), Binding("c", "copy", t("Copy"), show=False)]

    def __init__(self, title: str, server: TransferServer, user: str = "root"):
        super().__init__()
        self._title, self.server, self._user = title, server, user
        self._values: list[str] = []
        # Not self._closed: Textual's MessagePump has its own, and setting
        # it stops the screen from ever being removed.
        self._finished = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide -info"):
            yield Label(self._title, classes="dialog-title", markup=False)
            with VerticalScroll(classes="dialog-scroll", id="web-body"):
                yield Static(t("Starting the transfer page..."), classes="dialog-body", markup=False)
            yield Label("", id="web-status", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Close"), id="close", variant="primary")

    def on_mount(self) -> None:
        super().on_mount()
        self.run_worker(self._start, thread=True, exit_on_error=False, group="web-start")

    def _start(self) -> None:
        try:
            self.server.start()
        except (TransferError, OSError) as e:
            self.app.call_from_thread(self._failed, str(e))
            return
        if self._finished:      # closed while openssl was still working
            self.server.stop()
            return
        self.app.call_from_thread(self._show)

    def _failed(self, error: str) -> None:
        body = self.query_one("#web-body", VerticalScroll)
        body.remove_children()
        body.mount(Static(t("The transfer page could not be started: ${error}", error=error),
                          classes="dialog-body dialog-error", markup=False))

    def _show(self) -> None:
        server = self.server
        body = self.query_one("#web-body", VerticalScroll)
        body.remove_children()
        if server.mode == "upload":
            intro = t("This panel runs on another computer (SSH), so a file dragged onto the terminal does not "
                      "reach it. Open this address in the browser of your computer and drop the backup on the "
                      "page: it is sent here and checked (size and SHA-256).")
        else:
            intro = t("This panel runs on another computer (SSH). Open this address in the browser of your "
                      "computer: the backup is saved in your Downloads folder.")
        widgets = [Static(intro, classes="dialog-body", markup=False)]
        for url in server.urls():
            self._values.append(url)
            widgets.append(self._row(url, len(self._values) - 1))
        if server.cert_fingerprint:
            widgets.append(Static(t("The browser warns that the certificate is not trusted: it was made by this "
                                    "server just now. Continue to the page (Advanced > Proceed). Its SHA-256 "
                                    "fingerprint is:") + f"\n{server.cert_fingerprint}",
                                  classes="dialog-note", markup=False))
        host = (server.hosts or ["SERVER"])[0]
        tunnel = f"ssh -L {server.port}:127.0.0.1:{server.port} {self._user}@{host}"
        widgets.append(Static(t("If the page does not open, the firewall of the server's provider may keep port "
                                "${port} closed. Then run this on your computer and open the address below it:",
                                port=server.port), classes="dialog-note", markup=False))
        for value in (tunnel, server.tunnel_url()):
            self._values.append(value)
            widgets.append(self._row(value, len(self._values) - 1))
        if server.mode == "upload":
            widgets.append(Static(t("Received files go to ${folder}.", folder=str(server.folder)),
                                  classes="dialog-note", markup=False))
        else:
            widgets.append(Static(t("File:") + f" {server.file.name}", classes="dialog-note", markup=False))
        body.mount_all(widgets)
        self.query_one("#web-status", Label).update(t("Waiting for the browser..."))
        self.set_interval(0.5, self._poll)
        self.call_after_refresh(self._fit)

    def _row(self, value: str, index: int) -> Horizontal:
        from ..widgets.copy import CopyButton
        return Horizontal(Static(value, classes="detail-value", markup=False),
                          CopyButton(id=f"copy-{index}", classes="detail-copy"), classes="dialog-detail")

    def _poll(self) -> None:
        if self._finished:
            return
        state = self.server.state()
        status = self.query_one("#web-status", Label)
        if self.server.mode == "upload":
            if state["received"] is not None:
                self.app.notify(t("Backup received and checked: ${name}", name=state["received"].name), timeout=6)
                self._close(state["received"])
                return
            if state["error"]:
                status.update(t("The file arrived damaged (${error}): send it again.", error=state["error"]))
            elif state["total"]:
                status.update(f"{state['name']}: {transfer.human_size(state['done'])} / "
                              f"{transfer.human_size(state['total'])} "
                              f"({100 * state['done'] // state['total']}%)")
            return
        size = self.server.file.stat().st_size if self.server.file else 0
        line = t("Downloads finished: ${n}", n=state["downloads"])
        if state["sent"] and state["sent"] < size:
            line += f" · {transfer.human_size(state['sent'])} / {transfer.human_size(size)}"
        if state["sha256"]:
            line += f" · SHA-256 {state['sha256']}"
        status.update(line)

    def _close(self, result: Path | None) -> None:
        if self._finished:
            return
        self._finished = True
        self.server.stop()
        self.dismiss(result)

    def on_unmount(self) -> None:
        self._finished = True
        self.server.stop()

    @on(Button.Pressed, "#close")
    def action_close(self) -> None:
        self._close(None)
