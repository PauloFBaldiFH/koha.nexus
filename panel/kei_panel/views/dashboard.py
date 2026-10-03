"""DashboardView: Koha's state at a glance, read from --status-json.

The status is loaded in a worker with a one-line Pac-Man inside the view
(the same PacmanLoader as the modal, compact): a quick read does not need
to cover the screen, but it still never blocks it.
"""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.widgets import Button, Label

from ..i18n import t
from ..widgets.cards import StatusCard
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


class DashboardView(SectionView):
    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield Label(t("Control Dashboard"), classes="view-title")
            yield Button(t("Refresh"), id="refresh", classes="small")
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="status-loader")
        with Grid(classes="status-grid"):
            yield StatusCard(t("Koha"), id="card-state")
            yield StatusCard(t("Last backup"), id="card-backup")
            yield StatusCard(t("Disk free"), id="card-disk")
        yield Label(t("Components"), classes="view-prompt")
        with Grid(classes="status-grid", id="components"):
            for unit, name in COMPONENTS:
                yield StatusCard(t(name), id=f"card-{unit}")
            yield StatusCard(t("HTTP response"), id="card-http")

    def on_mount(self) -> None:
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh":
            self.refresh_data()

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
