"""The port of a new site (U9, study 16.2): one field for every installer.

    Port of the site: [8100]  ✓ free
    Port of the site: [8090]  ✗ in use by Museu Municipal (Tainacan) · suggestion 8091 [Use]
    Port of the site: [  80]  ✗ in use by another program (nginx) · suggestion 8081 [Use]

The default port is shown and can be changed. Each value is checked on the
server (`--task port-check PORT SYSTEM`, only reads); the installer checks
it again right before applying. A free port is not yet a reachable one:
the screen says other computers also depend on the firewall and router.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from .. import names
from ..i18n import t
from .dialogs import FitsScreen

SYSTEMS = {"koha": "Koha", "tainacan": "Tainacan", "dspace": "DSpace"}
DEFAULTS = {"tainacan": 8090, "dspace": 8100}
REACH = "Other computers also depend on the firewall and the router."


@dataclass
class PortState:
    port: int
    state: str = ""            # free | mine | used | "" (not checked)
    owner: str = ""
    suggest: int = 0
    lan: str = ""


def valid(text: str) -> int:
    """The port typed, or 0."""
    text = (text or "").strip()
    if not text.isdigit() or len(text) > 5:
        return 0
    port = int(text)
    return port if 1 <= port <= 65535 else 0


def parse(port: int, out) -> PortState:
    """From `--task port-check` (a TaskOutcome)."""
    st = PortState(port)
    if out is None:
        return st
    state = out.get("state") or ""
    st.state = state if state in ("free", "mine", "used") else ""
    owner = out.get("owner") or ""
    st.owner = owner[:60] if st.state == "used" else ""
    suggest = out.get("suggest") or ""
    st.suggest = valid(suggest)
    lan = out.get("lan") or ""
    st.lan = lan if all(p.isdigit() for p in lan.split(".")) and lan.count(".") == 3 else ""
    return st


def owner_text(owner: str, known: dict | None = None) -> str:
    """Who uses the port, in words: a system by its visible name (U6)."""
    if owner in SYSTEMS:
        name = names.label(known or {}, owner) if names.custom(known or {}, owner) else SYSTEMS[owner]
        return t("in use by ${who}", who=name)
    if owner == "reserved":
        return t("reserved for the internal use of Tainacan or DSpace")
    if owner == "apache":
        return t("in use by another site of the web server (Apache)")
    if owner == "docker":
        return t("in use by a Docker container")
    program = owner.partition(":")[2]
    return t("in use by another program (${name})", name=program) if program else t("in use by another program")


def status_text(st: PortState, known: dict | None = None) -> tuple[str, str]:
    """(line, state) under the field."""
    if not st.port:
        return t("Use a number from 1 to 65535."), "bad"
    if st.state == "free":
        return t("✓ free"), "ok"
    if st.state == "mine":
        return t("✓ already this system's port"), "ok"
    if st.state == "used":
        line = "✗ " + owner_text(st.owner, known)
        if st.suggest:
            line += " · " + t("suggestion ${port}", port=st.suggest)
        return line, "bad"
    return t("Checking…"), ""


def address(st: PortState, scheme: str = "http", host: str = "") -> str:
    """The address of the new site on that port, "" without a host."""
    host = host or st.lan
    return f"{scheme}://{host}:{st.port}" if host and st.port else ""


class PortScreen(FitsScreen, ModalScreen[Optional[PortState]]):
    """One port, checked as it is typed; OK only for a free one. Gives the
    PortState (its port and this server's address), or None."""

    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, title: str, body: str, system: str, port: int = 0, scheme: str = "http",
                 host: str = ""):
        super().__init__()
        self._title, self._body, self._system = title, body, system
        self._first = port or DEFAULTS.get(system, 8080)
        self._scheme, self._host = scheme, host
        self.state = PortState(self._first)

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide"):
            yield Label(self._title, classes="dialog-title", markup=False)
            if self._body:
                yield Static(self._body, classes="dialog-body", markup=False)
            with Horizontal(classes="form-row port-row"):
                yield Label(t("Port of the site:"), classes="form-label")
                yield Input(str(self._first), id="port", max_length=5, restrict=r"[0-9]*")
                yield Button(t("Use"), id="port-use", classes="small")
            yield Label("", id="port-state", classes="port-state", markup=False)
            yield Label("", id="port-address", classes="dialog-body", markup=False)
            yield Static(t(REACH), classes="ai-note", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Continue"), id="ok", variant="primary", disabled=True)
                yield Button(t("Cancel"), id="cancel")

    def on_mount(self) -> None:
        self.query_one("#port-use").display = False
        self.query_one("#port", Input).focus()
        self.check(self._first)

    @on(Input.Changed, "#port")
    def _typed(self, event: Input.Changed) -> None:
        self.check(valid(event.value))

    @work(exclusive=True, group="port-check", exit_on_error=False)
    async def check(self, port: int) -> None:
        self.state = PortState(port)
        self._draw()
        if not port:
            return
        try:
            out = await self.app.bridge.task("port-check", str(port), self._system)
        except Exception:  # noqa: BLE001 - not checked: OK stays off
            out = None
        try:
            if valid(self.query_one("#port", Input).value) != port:
                return                   # typed again meanwhile
        except Exception:  # noqa: BLE001 - the dialog was closed meanwhile
            return
        self.state = parse(port, out)
        self._draw()

    def _draw(self) -> None:
        st = self.state
        line, state = status_text(st, names.of(self.app))
        label = self.query_one("#port-state", Label)
        label.update(line)
        label.set_class(state == "ok", "-ok")
        label.set_class(state == "bad", "-bad")
        use = self.query_one("#port-use", Button)
        use.display = bool(st.state == "used" and st.suggest)
        use.label = t("Use ${port}", port=st.suggest) if st.suggest else t("Use")
        url = address(st, self._scheme, self._host)
        self.query_one("#port-address", Label).update(t("Address: ${url}", url=url) if url else "")
        self.query_one("#ok", Button).disabled = st.state not in ("free", "mine")

    @on(Button.Pressed, "#port-use")
    def _use(self) -> None:
        if self.state.suggest:
            self.query_one("#port", Input).value = str(self.state.suggest)

    @on(Input.Submitted, "#port")
    @on(Button.Pressed, "#ok")
    def _accept(self) -> None:
        if self.state.state in ("free", "mine") and self.state.port:
            self.dismiss(self.state)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
