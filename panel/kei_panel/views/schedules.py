"""SchedulesView: every scheduled job of this server in one list (Paulo,
2026-11-06), in the main menu (key s).

  ⏰ Schedules                                         [Refresh]
  Platform: [All ▾]   Type: [All ▾]
  Times in America/Sao_Paulo (the server's time zone).
  [✏ Koha's scheduled jobs]  [⏰ Schedule backups (Tainacan)]   the editors
  ● Koha · Database backup (compressed SQL)
    Daily at 23:00 · next 2026-11-06 23:00
    Last run: 2026-11-05 23:00 · OK
    Changed in: Schedules & cron tasks
  ...
  ℹ Tainacan · WP-Cron (WordPress's own scheduler)
    Runs when the site gets visits: it is not a server schedule

It only reads (schedules.py). Each row says where it is changed: the
editor of koha_tasks (views/crons.py), "Schedule backups" for the
platforms, or the screen of the job the installer keeps in its own file.
The Koha group opens it already filtered on Koha (menus.Entry.scope).
"""

from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Select, Static

from .. import cloud, platforms, schedules
from ..i18n import t
from .base import SectionView

STATES = {"on": ("●", "green"), "off": ("○", "dim"), "internal": ("ℹ", "cyan")}
LAST = {"ok": "green", "bad": "red", "warn": "yellow", "": "dim"}


def row_text(row: schedules.Row) -> Text:
    mark, colour = STATES.get(row.state, STATES["off"])
    text = Text()
    text.append(f"{mark} ", style=colour)
    text.append(t(schedules.PLATFORM_LABELS.get(row.platform, row.platform)) + " · ", style="dim")
    text.append(row.name, style="bold" if row.state != "off" else "dim")
    if row.state == "internal":
        text.append("\n  " + row.when)
    else:
        text.append("\n  " + row.when)
        text.append(" · " + (t("next ${when}", when=row.next) if row.state == "on" else t("Switched off")), style="dim")
        text.append(f"\n  {t('Last run')}: ", style="dim")
        text.append(row.last, style=LAST.get(row.last_state, "dim"))
    text.append(f"\n  {t('Changed in')}: ", style="dim")
    text.append(row.editor)
    for other in row.also:
        text.append("\n  ⚠ " + t("Also scheduled in ${where}: it runs twice", where=other), style="yellow")
    return text


class SchedulesView(SectionView):
    def __init__(self, section):
        super().__init__(section)
        self.platform = ""
        self.kind = ""
        self.rows: list[schedules.Row] = []
        self.loaded = False
        self.ready = False          # the rows were read at least once

    def compose(self) -> ComposeResult:
        yield from self.heading()
        yield Static(t("Everything this server runs by itself, from every file that holds a schedule. Nothing "
                       "is changed here: each row says where it is changed."), classes="view-prompt", markup=False)
        with Horizontal(id="sc-filters"):
            yield Label(t("Platform:"), classes="form-label")
            yield Select([(t("All"), "")], value="", allow_blank=False, id="sc-platform")
            yield Label(t("Type:"), classes="form-label")
            yield Select([(t("All"), "")] + [(t(v), k) for k, v in schedules.KIND_LABELS.items()], value="",
                         allow_blank=False, id="sc-kind")
            yield Button(t("Refresh"), id="sc-refresh", classes="small")
        yield Static("", id="sc-tz", classes="view-prompt", markup=False)
        yield from self.cards()
        yield Label(t("Scheduled jobs"), classes="view-prompt zone-title")
        yield Vertical(id="sc-rows")

    def on_mount(self) -> None:
        self._platform_choices()

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            self.refresh_data()

    def refresh_data(self) -> None:
        self._platform_choices()
        self.run_worker(self._load, exclusive=True, group="schedules", exit_on_error=False)

    # --- filters ----------------------------------------------------------
    def _platform_choices(self) -> None:
        offered = schedules.platforms_offered(self.app.platform_ready("koha"), self.app.platform_ready("tainacan"), self.app.platform_ready("dspace"))
        if self.platform not in offered:
            self.platform = ""
        select = self.query_one("#sc-platform", Select)
        select.set_options([(t("All"), "")] + [(t(schedules.PLATFORM_LABELS[p]), p) for p in offered])
        select.value = self.platform

    def set_scope(self, scope: str) -> None:
        """A platform group opens the center already filtered on it."""
        self.platform = scope if scope in schedules.PLATFORM_LABELS else ""
        if self.is_mounted:
            self._platform_choices()
            self._draw()

    def on_select_changed(self, event: Select.Changed) -> None:
        value = event.value if isinstance(event.value, str) else ""
        if event.select.id == "sc-platform":
            event.stop()
            if value != self.platform:
                self.platform = value
                self._draw()
        elif event.select.id == "sc-kind":
            event.stop()
            if value != self.kind:
                self.kind = value
                self._draw()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sc-refresh":
            event.stop()
            self.refresh_data()

    # --- loading ----------------------------------------------------------
    async def _load(self) -> None:
        koha, tainacan = self.app.platform_ready("koha"), self.app.platform_ready("tainacan")
        if self.app.env.demo:
            from ..demo import demo_cron_files
            files = demo_cron_files(koha, tainacan)
            zone = "America/Sao_Paulo"
        else:
            files = schedules.read_files()
            zone = schedules.server_timezone()
        rows = schedules.collect(files, self.app.env.instance, tainacan)
        last = await self._last_runs(koha, tainacan)
        schedules.fill_times(rows, dt.datetime.now(), last)
        self.rows = rows
        self.query_one("#sc-tz", Static).update(t("Times in ${zone} (the server's time zone).", zone=zone))
        self._draw()
        self.ready = True

    async def _last_runs(self, koha: bool, tainacan: bool) -> dict[str, tuple[str, str]]:
        """Only what a record says: the backup logs, the newest package."""
        bridge = self.app.bridge
        backup: dict = {}
        plans: list = []
        history: list = []
        tn = None
        joint = ""
        if koha and tainacan and bridge.has_task("set-schedule-status"):
            try:
                joint = (await bridge.task("set-schedule-status")).results.get("last", "")
            except Exception:  # noqa: BLE001
                pass
        if koha:
            try:
                backup = (await bridge.status()).get("backup", {}) or {}
            except Exception:  # noqa: BLE001 - the rows then say "No run recorded"
                pass
            try:
                if bridge.has_task("cloud-status"):
                    out = await bridge.task("cloud-status")
                    plans = cloud.parse_plans(out.lists.get("plan", []))
                    history = cloud.parse_history(out.lists.get("history", []))
            except Exception:  # noqa: BLE001
                pass
        if tainacan:
            try:
                if bridge.has_task("platform-backup-status"):
                    out = await bridge.task("platform-backup-status", "tainacan")
                    tn = platforms.backup_from_results(out.results)
            except Exception:  # noqa: BLE001
                pass
        last = schedules.last_runs(backup, plans, history, tn, joint)
        if self.app.platform_ready("dspace") and bridge.has_task("dspace-panel"):
            try:
                from ..dspace import payload
                last.update(schedules.operation_last_runs(payload(await bridge.task("dspace-panel", "operations", "plans"))))
            except Exception:  # noqa: BLE001 - the rows then say "No run recorded"
                pass
        return last

    def _draw(self) -> None:
        box = self.query_one("#sc-rows", Vertical)
        box.remove_children()
        rows = schedules.shown(self.rows, self.platform, self.kind)
        if not rows:
            box.mount(Static(t("Nothing is scheduled here.") if not self.rows else
                             t("Nothing scheduled matches this filter."), classes="sc-row", markup=False))
            return
        box.mount_all(Static(row_text(r), classes=f"sc-row -{r.state}") for r in rows)
