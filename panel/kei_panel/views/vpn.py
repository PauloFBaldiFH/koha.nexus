"""VpnView: the WireGuard VPN for the staff interface and SSH.

Set up writes the server side (`config.sh --task vpn-setup ENDPOINT PORT`);
each staff computer or phone is a device with its own key and address
(vpn-peer-add / vpn-peer-revoke). A device's profile opens as a QR code
for the WireGuard app and a Copy button for a computer (screens/vpn.py).
Split tunnel only: 10.66.0.0/24 goes through the VPN, the rest of the
device's traffic and its DNS do not (vpn.py).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Static

from .. import vpn
from ..i18n import t
from ..screens.dialogs import ConfirmScreen
from ..screens.vpn import ProfileScreen
from .base import SectionView

AGO = {"never": "never", "seconds": "${n} s ago", "minutes": "${n} min ago", "hours": "${n} h ago",
       "days": "${n} days ago"}


class VpnView(SectionView):
    loaded = False

    def __init__(self, section):
        super().__init__(section)
        self.status: dict[str, str] = {}
        self.peers: list[dict[str, object]] = []

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield from self.heading()
            yield Button(t("Reload"), id="v-reload", classes="small")
        yield Static(t("A private network for the staff: from home or another branch, a computer or phone with "
                       "WireGuard reaches the staff interface and SSH of this server as if it were on the library's "
                       "network. Only the library's addresses (10.66.0.x) go through it; the device's internet, "
                       "DNS and the book covers stay on its own connection."), classes="view-prompt", markup=False)
        yield Label(t("Not checked yet."), id="v-state", classes="hub-state")
        with Vertical(id="v-server", classes="hub-box"):
            with Horizontal(classes="form-row"):
                yield Label(t("Address"), classes="form-label")
                yield Input("", id="v-endpoint", placeholder=t("public IP or name, e.g. vpn.library.org"))
            with Horizontal(classes="form-row"):
                yield Label(t("UDP port"), classes="form-label")
                yield Input(str(vpn.DEFAULT_PORT), id="v-port", max_length=5, type="integer")
            with Horizontal(classes="form-buttons"):
                yield Button(t("Set up the VPN"), id="v-setup", variant="success")
                yield Button(t("Turn off"), id="v-stop", variant="error")
        with Vertical(id="v-devices", classes="hub-box"):
            yield DataTable(id="v-peers", cursor_type="row", classes="hub-table")
            with Horizontal(classes="form-row"):
                yield Label(t("New device"), classes="form-label")
                yield Input("", id="v-name", max_length=32, placeholder=t("e.g. maria-laptop"))
            with Horizontal(classes="form-buttons"):
                yield Button(t("Add device"), id="v-add", variant="primary")
                yield Button(t("QR code & profile"), id="v-show")
                yield Button(t("Revoke"), id="v-revoke", variant="error")
        yield Static("", id="v-howto", classes="ai-note", markup=False)

    def on_mount(self) -> None:
        self.query_one("#v-server").border_title = t("Server")
        self.query_one("#v-devices").border_title = t("Devices")
        self.query_one("#v-peers", DataTable).add_columns(
            t("Device"), t("Address"), t("Last seen"), t("Received"), t("Sent"))
        self.show_howto()

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            self.reload()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def reload(self) -> None:
        self.run_worker(self._reload(), exclusive=True, group="vpn-load", exit_on_error=False)

    async def _reload(self) -> None:
        try:
            out = await self.app.bridge.task("vpn-status")
        except Exception:     # noqa: BLE001 (no installer: the screen stays as it is)
            return
        self.status = dict(out.results)
        self.peers = [vpn.parse_peer(row) for row in out.lists.get("peer", [])]
        self.show_status()

    def show_status(self) -> None:
        s = self.status
        if s.get("supported") == "no":
            state = t("This server is not reachable directly (WSL without mirrored networking): the VPN is off.")
        elif s.get("configured") != "yes":
            state = t("VPN not set up yet.")
        elif s.get("running") == "yes":
            state = t("VPN on: ${endpoint}, UDP port ${port}. Devices: ${n}.",
                      endpoint=s.get("endpoint", ""), port=s.get("port", ""), n=len(self.peers))
        else:
            state = t("VPN set up but off. Set up the VPN turns it on again.")
        self.query_one("#v-state", Label).update(state)
        endpoint = self.query_one("#v-endpoint", Input)
        if not endpoint.value:
            endpoint.value = s.get("endpoint") or s.get("public_ip") or ""
        if s.get("port"):
            self.query_one("#v-port", Input).value = s["port"]
        table = self.query_one("#v-peers", DataTable)
        table.clear()
        for p in self.peers:
            unit, n = vpn.ago(int(p["handshake"]))
            table.add_row(p["name"], p["address"], t(AGO[unit], n=n), vpn.size(int(p["rx"])),
                          vpn.size(int(p["tx"])), key=str(p["name"]))
        table.display = bool(self.peers)
        self.show_howto()

    def show_howto(self) -> None:
        ssh = self.status.get("ssh_port", "22")
        ssh_cmd = f"ssh -p {ssh} USER@{vpn.SERVER}" if ssh != "22" else f"ssh USER@{vpn.SERVER}"
        self.query_one("#v-howto", Static).update(
            t("Connected to the VPN: staff interface http://${ip}:8080 · SSH: ${ssh}", ip=vpn.SERVER, ssh=ssh_cmd))

    def selected(self) -> str:
        table = self.query_one("#v-peers", DataTable)
        if not table.row_count:
            return ""
        return str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {"v-reload": self.reload, "v-setup": self.setup, "v-stop": self.stop, "v-add": self.add,
                   "v-show": self.show_selected, "v-revoke": self.revoke}
        if event.button.id in actions:
            event.stop()
            actions[event.button.id]()

    def _run(self, flow) -> None:
        self.app.run_worker(flow, group="routine", exclusive=True, exit_on_error=False)

    def setup(self) -> None:
        endpoint = self.query_one("#v-endpoint", Input).value.strip()
        port = self.query_one("#v-port", Input).value.strip()
        problem = vpn.endpoint_problem(endpoint) or vpn.port_problem(port)
        if problem:
            self.app.notify(t(problem), severity="warning")
            return
        self._run(self._setup(endpoint, port))

    async def _setup(self, endpoint: str, port: str) -> None:
        from ..routines.common import run_task, show_done
        title = t("🔐  WireGuard VPN")
        steps = "\n".join([
            t("Installs WireGuard and writes /etc/wireguard/wg0.conf (this server: ${ip}).", ip=vpn.SERVER),
            t("Turns on IP forwarding and the NAT (iptables MASQUERADE) for 10.66.0.0/24."),
            t("Opens UDP port ${port} in the firewall; the staff interface and SSH answer on the VPN.", port=port),
            t("Devices connect to ${endpoint}:${port}. On a router, forward that UDP port to this server.",
              endpoint=endpoint, port=port),
        ])
        if not await self.app.push_screen_wait(ConfirmScreen(title, t("Set up the VPN now?"), preview=steps)):
            return
        await show_done(self.app, title, await run_task(self.app, title, "vpn-setup", endpoint, port))
        self.reload()

    def stop(self) -> None:
        self._run(self._stop())

    async def _stop(self) -> None:
        from ..routines.common import run_task, show_done
        title = t("🔐  WireGuard VPN")
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Turn the VPN off? Connected devices are dropped; their profiles are kept."))):
            return
        await show_done(self.app, title, await run_task(self.app, title, "vpn-stop"))
        self.reload()

    def add(self) -> None:
        name = self.query_one("#v-name", Input).value.strip()
        problem = vpn.name_problem(name)
        if not problem and any(p["name"] == name for p in self.peers):
            problem = "There is already a device called ${name}."
        if problem:
            self.app.notify(t(problem, name=name), severity="warning")
            return
        self._run(self._add(name))

    async def _add(self, name: str) -> None:
        from ..routines.common import failed, run_task, show_failure
        title = t("🔐  WireGuard VPN")
        result = await run_task(self.app, title, "vpn-peer-add", name)
        if failed(result):
            await show_failure(self.app, title, result)
            return
        self.query_one("#v-name", Input).value = ""
        self.reload()
        await self._profile(name)

    def show_selected(self) -> None:
        name = self.selected()
        if not name:
            self.app.notify(t("Add a device first."), severity="warning")
            return
        self._run(self._profile(name))

    async def _profile(self, name: str) -> None:
        if self.app.env.demo:
            profile = vpn.DEMO_PROFILE.replace("VPN: demo", f"VPN: {name}")
        else:
            try:
                profile = vpn.read_profile(name)
            except OSError as e:
                self.app.notify(t("The profile of ${name} could not be read: ${error}", name=name, error=str(e)),
                                severity="error")
                return
        problem = vpn.profile_problem(profile)
        if problem:
            self.app.notify(t(problem), severity="error")
            return
        await self.app.push_screen_wait(ProfileScreen(name, profile, vpn.qr(profile)))

    def revoke(self) -> None:
        name = self.selected()
        if not name:
            self.app.notify(t("Add a device first."), severity="warning")
            return
        self._run(self._revoke(name))

    async def _revoke(self, name: str) -> None:
        from ..routines.common import run_task, show_done
        title = t("🔐  WireGuard VPN")
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Revoke ${name}? It can no longer connect; a new profile is needed to come back.",
                         name=name), danger=True)):
            return
        await show_done(self.app, title, await run_task(self.app, title, "vpn-peer-revoke", name))
        self.reload()

    def refresh_data(self) -> None:
        self.reload()
