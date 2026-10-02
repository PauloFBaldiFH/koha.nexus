"""DashboardView: Koha's state at a glance, read from --status-json,
and under it the AI assistant (Module 2, widgets/assistant.py), where the
whiptail panel showed its static news.

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
from ..widgets.assistant import AssistantPanel
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


class DashboardView(SectionView):
    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield Label(t("Control Dashboard"), classes="view-title")
            yield Button(t("Refresh"), id="refresh", classes="small")
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="status-loader")
        with Grid(classes="status-grid"):
            yield StatusCard(t("Koha"), id="card-state")
            yield StatusCard(t("Staff / OPAC"), id="card-http")
            yield StatusCard(t("Last backup"), id="card-backup")
            yield StatusCard(t("Disk free"), id="card-disk")
            yield StatusCard(t("Memory available"), id="card-memory")
            yield StatusCard(t("Services"), id="card-services")
        yield AssistantPanel(id="assistant")

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
        state = s.get("state", "unknown")
        good = state == "running"
        self.query_one("#card-state", StatusCard).set(
            state.replace("_", " "), f"v{s.get('panel_version', '?')} · {s.get('platform', '')}",
            "ok" if good else "bad")
        http = s.get("http", {})
        ok_http = http.get("staff") == 200 and http.get("opac") == 200
        self.query_one("#card-http", StatusCard).set(
            f"{http.get('staff', '-')} / {http.get('opac', '-')}", "HTTP", "ok" if ok_http else "warn")
        b = s.get("backup", {})
        self.query_one("#card-backup", StatusCard).set(
            age(b.get("last_epoch")), b.get("last_file") or "-",
            "ok" if b.get("last_result") == "ok" else "warn")
        d = s.get("disk", {})
        free, total = d.get("free") or 0, d.get("total") or 0
        self.query_one("#card-disk", StatusCard).set(
            human_bytes(free), f"/ {human_bytes(total)}",
            "bad" if total and free / total < 0.1 else "ok")
        m = s.get("memory", {})
        self.query_one("#card-memory", StatusCard).set(
            human_bytes(m.get("available")), f"/ {human_bytes(m.get('total'))}")
        svcs = s.get("services", {})
        down = [k for k in ("apache2", "mariadb", "memcached", "koha-common") if svcs.get(k) != "active"]
        self.query_one("#card-services", StatusCard).set(
            f"{sum(v == 'active' for v in svcs.values())}/{len(svcs)}",
            ", ".join(down) if down else "apache2 · mariadb · memcached · koha", "bad" if down else "ok")
