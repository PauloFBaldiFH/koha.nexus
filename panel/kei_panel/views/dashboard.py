"""DashboardView: Koha's state at a glance, read from --status-json, the
addresses Koha answers on (Open / Copy) and two quick actions: restart Koha
and export diagnostics.

The status is loaded in a worker with a one-line Pac-Man inside the view
(the same PacmanLoader as the modal, compact): a quick read does not need
to cover the screen, but it still never blocks it.
"""

from __future__ import annotations

import time

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.widgets import Button, Label

from ..i18n import t
from ..widgets.cards import LinkCard, StatusCard
from ..widgets.pacman import PacmanLoader
from .base import SectionView


def human_bytes(n: int | None) -> str:
    if not n:
        return "-"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return str(n)


def age(epoch: int | None) -> str:
    if not epoch:
        return "-"
    secs = max(0, int(time.time()) - int(epoch))
    if secs < 3600:
        return f"{secs // 60} min"
    if secs < 86400:
        return f"{secs // 3600} h"
    return f"{secs // 86400} d"


# The components the Koha window on Windows lists, in the order Koha needs
# them (KohaServices in windows/KohaEasy.Core.psm1), then the staff page.
COMPONENTS = (
    ("mariadb", "MariaDB"),
    ("apache2", "Apache"),
    ("rabbitmq-server", "RabbitMQ"),
    ("memcached", "Memcached"),
    ("koha-common", "Koha (koha-common)"),
)

# kei_overall_state in the installer: ok | degraded | stopped | not_installed.
OVERALL = {
    "ok": ("Running", "ok"),
    "running": ("Running", "ok"),
    "degraded": ("Attention", "warn"),
    "stopped": ("Stopped", "bad"),
    "not_installed": ("not installed", "warn"),
}


def unit_state(active: str | None) -> tuple[str, str]:
    """systemctl is-active as the Koha window shows it: text and card state."""
    if active == "active":
        return "Running", "ok"
    if active in ("activating", "reloading"):
        return "Starting", "warn"
    if active == "failed":
        return "Failed", "bad"
    if active in ("inactive", "deactivating"):
        return "Stopped", "bad"
    return "Unknown", "warn"


# The address cards: (where, page). Columns are where the browser is, rows
# the catalog then the staff interface.
WHERES = ("local", "lan", "public")
PAGES = ("opac", "staff")
LINK_TITLES = {
    ("local", "opac"): "Catalog (this computer)", ("lan", "opac"): "Catalog (local network)",
    ("public", "opac"): "Catalog (Internet)", ("local", "staff"): "Staff (this computer)",
    ("lan", "staff"): "Staff (local network)", ("public", "staff"): "Staff (Internet)",
}


def http_url(host: str, port: int) -> str:
    return f"http://{host}" if port == 80 else f"http://{host}:{port}"


def access_links(s: dict) -> dict[tuple[str, str], tuple[str, str, str]]:
    """--status-json's "access" (and "services") as (where, page) ->
    (url, note, card state). An empty url means none, the note says why."""
    a = s.get("access") or {}
    ports = {"opac": int(a.get("opac_port") or 80), "staff": int(a.get("staff_port") or 8080)}
    links: dict[tuple[str, str], tuple[str, str, str]] = {}
    for page in PAGES:
        links[("local", page)] = (http_url("localhost", ports[page]), t("On the server itself"), "")
        ip = a.get("lan_ip") or ""
        if a.get("lan_reachable") and ip:
            links[("lan", page)] = (http_url(ip, ports[page]), t("Other computers on the network"), "")
        elif s.get("platform", "").startswith("wsl"):
            links[("lan", page)] = ("", t("Not reachable from other computers (WSL NAT networking)"), "")
        else:
            links[("lan", page)] = ("", t("No local network address"), "")
    online = (s.get("services") or {}).get("cloudflared") == "active"
    mode = a.get("tunnel_mode") or ""
    where = t("Free koha.nexus address") if mode == "free" else t("Cloudflare Tunnel")
    for page in PAGES:
        host = a.get(f"public_{page}") or ""
        if host:
            links[("public", page)] = (f"https://{host}", f"{where} · {t('online') if online else t('offline')}",
                                       "ok" if online else "bad")
        elif mode == "free" and page == "staff":
            links[("public", page)] = ("", t("Remote staff access is off"), "")
        elif a.get("public_ip"):
            # A cloud server on a private address (10.0.0.60): the address
            # the Internet sees, which works once the cloud firewall lets
            # ports 80 and 8080 in.
            links[("public", page)] = (http_url(a["public_ip"], ports[page]),
                                       t("Public IP: open ports 80 and 8080 in the cloud firewall, or use a "
                                         "Cloudflare Tunnel"), "")
        else:
            links[("public", page)] = ("", t("Not published on the Internet"), "")
    return links


class DashboardView(SectionView):
    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            icon = "" if self.app.env.plain else f"{self.section.icon} "
            yield Label(icon + t("Control Dashboard"), classes="view-title")
            yield Button(t("Refresh"), id="refresh", classes="small")
        with Horizontal(classes="quick-actions"):
            yield Button(t("Restart Koha"), id="restart-koha", classes="small")
            yield Button(t("Export diagnostics"), id="export-diagnostics", classes="small")
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="status-loader")
        with Grid(classes="status-grid"):
            yield StatusCard(t("Koha"), id="card-state")
            yield StatusCard(t("Last backup"), id="card-backup")
            yield StatusCard(t("Disk free"), id="card-disk")
        yield Label(t("Addresses"), classes="view-prompt")
        with Grid(classes="status-grid", id="addresses"):
            for page in PAGES:
                for where in WHERES:
                    yield LinkCard(t(LINK_TITLES[where, page]), id=f"link-{where}-{page}")
        yield Label(t("Components"), classes="view-prompt")
        with Grid(classes="status-grid", id="components"):
            for unit, name in COMPONENTS:
                yield StatusCard(t(name), id=f"card-{unit}")
            yield StatusCard(t("HTTP response"), id="card-http")

    def on_mount(self) -> None:
        # An installer older than the panel has no such task: the button stays off.
        for action in ("restart-koha", "export-diagnostics"):
            task = "repair-services" if action == "restart-koha" else action
            ok = self.app.env.demo or (self.app.bridge.supports_tasks() and self.app.bridge.has_task(task))
            self.query_one(f"#{action}", Button).disabled = not ok
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "refresh":
            self.refresh_data()
        elif bid in ("restart-koha", "export-diagnostics"):
            self.app.run_native(bid, after=self.refresh_data if bid == "restart-koha" else None)

    @on(LinkCard.Pressed)
    def _link(self, event: LinkCard.Pressed) -> None:
        if event.copy:
            self.app.copy_to_clipboard(event.url)
        else:
            self.app.open_url(event.url)

    def refresh_data(self) -> None:
        self.query_one("#status-loader").display = True
        self.run_worker(self._load(), exclusive=True, group="status", exit_on_error=False)

    async def _load(self) -> None:
        try:
            status = await self.app.bridge.status()
        except Exception as e:  # shown in the card, never a crash
            self.query_one("#card-state", StatusCard).set(t("Unknown"), str(e)[:60], "bad")
            status = None
        finally:
            self.query_one("#status-loader").display = False
        if status:
            self.show(status)

    def show(self, s: dict) -> None:
        text, state = OVERALL.get(s.get("state", ""), ("Unknown", "bad"))
        m = s.get("memory", {})
        self.query_one("#card-state", StatusCard).set(
            t(text), f"v{s.get('panel_version', '?')} · {s.get('platform', '')}"
            f" · {t('Memory available')} {human_bytes(m.get('available'))}", state)
        b = s.get("backup", {})
        self.query_one("#card-backup", StatusCard).set(
            age(b.get("last_epoch")), b.get("last_file") or "-",
            "ok" if b.get("last_result") == "ok" else "warn")
        d = s.get("disk", {})
        free, total = d.get("free") or 0, d.get("total") or 0
        self.query_one("#card-disk", StatusCard).set(
            human_bytes(free), f"/ {human_bytes(total)}",
            "bad" if total and free / total < 0.1 else "ok")
        svcs = s.get("services", {})
        for unit, _name in COMPONENTS:
            text, state = unit_state(svcs.get(unit))
            self.query_one(f"#card-{unit}", StatusCard).set(t(text), unit, state)
        http = s.get("http", {})
        staff, opac = http.get("staff"), http.get("opac")
        answers = isinstance(staff, int) and 0 < staff < 500
        self.query_one("#card-http", StatusCard).set(
            t("Answers (HTTP ${code})", code=staff) if answers else t("Does not answer"),
            f"{t('Staff / OPAC')}: {staff or '-'} / {opac or '-'}", "ok" if answers else "bad")
        for (where, page), (url, note, state) in access_links(s).items():
            self.query_one(f"#link-{where}-{page}", LinkCard).set_url(url, note, state)
