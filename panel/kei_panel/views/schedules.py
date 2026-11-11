"""Unified schedules with explicit per-row save and existing backend writers.

Known Koha jobs support recurrence editing. Tainacan's backup group and
explicit DSpace/set plans expose their supported daily schedule. Manual,
package and linked maintenance rows remain read-only. Filtering preserves
unsaved drafts; opening the screen never writes a schedule.
"""

from __future__ import annotations

import datetime as dt
import asyncio

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, Static, Switch

from .. import cloud, cron, platforms, schedules
from ..schedule_controls import controls, EditError
from ..screens.dialogs import ConfirmScreen
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
    text.append(f"\n  {t('Original editor')}: ", style="dim")
    text.append(row.editor)
    for other in row.also:
        text.append("\n  ⚠ " + t("Also scheduled in ${where}: it runs twice", where=other), style="yellow")
    return text



def day_options(freq, current=0):
    """Day choices for a frequency: weekday names, days of the month, or the
    unchanged hidden value for daily and custom schedules."""
    if freq == 'weekly':
        return [(t(name), n) for n, name in enumerate(cron.WEEKDAYS)]
    if freq == 'monthly':
        return [(t("Day ${n}", n=n), n) for n in range(1, 32)]
    return [(str(current), current)]


def day_value(freq, current):
    """Keep the chosen day when it fits the frequency; otherwise its first day."""
    if freq not in ('weekly', 'monthly'):
        return current if isinstance(current, int) else 0
    allowed = range(0, 7) if freq == 'weekly' else range(1, 32)
    return current if isinstance(current, int) and current in allowed else allowed[0]


class SchedulesView(SectionView):
    def __init__(self, section):
        super().__init__(section)
        self.platform = ""
        self.kind = ""
        self.rows: list[schedules.Row] = []
        self.loaded = False
        self.controls = {}
        self.drafts = {}
        self.tainacan_settings = None
        self.joint_settings = None
        self.operation_plans = []
        self.saving = False
        self.loading = False
        self._render_lock = None
        self.ready = False          # the rows were read at least once

    def compose(self) -> ComposeResult:
        yield from self.heading()
        yield Static(t("Turn managed jobs on or off, choose their frequency and time, then Save. "
                       "Changes are reviewed before applying. Manual and package jobs are read-only."), classes="view-prompt", markup=False)
        with Horizontal(id="sc-filters"):
            yield Label(t("Platform:"), classes="form-label")
            yield Select([(t("All"), "")], value="", allow_blank=False, id="sc-platform")
            yield Label(t("Type:"), classes="form-label")
            yield Select([(t("All"), "")] + [(t(v), k) for k, v in schedules.KIND_LABELS.items()], value="",
                         allow_blank=False, id="sc-kind")
            yield Button(t("Refresh"), id="sc-refresh", classes="small")
        yield Static("", id="sc-tz", classes="view-prompt", markup=False)
        yield Label(t("Scheduled jobs"), classes="view-prompt zone-title")
        yield Vertical(id="sc-rows")
        yield Label(t("Other editors"), classes="view-prompt zone-title")
        yield from self.cards()

    def on_mount(self) -> None:
        self._platform_choices()

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            self.refresh_data()

    def refresh_data(self) -> None:
        self._remember()
        self._platform_choices()
        self.run_worker(self._load, exclusive=False, group="schedules", exit_on_error=False)

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
        if event.select.id and event.select.id.startswith("sc-freq-"):
            event.stop()
            self._fields(int(event.select.id.removeprefix("sc-freq-")))
        elif event.select.id == "sc-platform":
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
        bid = event.button.id or ""
        if bid.startswith("sc-save-"):
            event.stop()
            self.app.run_worker(self._save(int(bid.removeprefix("sc-save-")), getattr(event.button, "schedule_control", None)), group="routine", exclusive=True, exit_on_error=False)
        elif bid == "sc-refresh":
            event.stop()
            self.refresh_data()

    # --- loading ----------------------------------------------------------
    async def _load(self) -> None:
        if self.loading: return
        self.loading = True
        self.ready = False
        try:
            await self._load_data()
        finally:
            self.loading = False

    async def _load_data(self) -> None:
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
        self.controls = controls(rows, files, self.app.env.instance, tainacan=self.tainacan_settings,
                                 joint=self.joint_settings, plans=self.operation_plans)
        schedules.fill_times(rows, dt.datetime.now(), last)
        self.rows = rows
        self.query_one("#sc-tz", Static).update(t("Times in ${zone} (the server's time zone).", zone=zone))
        await self._render_rows()
        self.ready = True

    async def _last_runs(self, koha: bool, tainacan: bool) -> dict[str, tuple[str, str]]:
        """Only what a record says: the backup logs, the newest package."""
        bridge = self.app.bridge
        backup: dict = {}
        plans: list = []
        history: list = []
        tn = None
        joint = ""
        self.tainacan_settings = None
        self.joint_settings = None
        self.operation_plans = []
        if koha and tainacan and bridge.has_task("set-schedule-status"):
            try:
                out = await bridge.task("set-schedule-status")
                self.joint_settings = dict(out.results) if out.ok else None
                joint = out.results.get("last", "")
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
                    if out.ok:
                        self.tainacan_settings = dict(schedule=tn.schedule, key=tn.key, known=tn.known)
                    else:
                        self.tainacan_settings = {"known": False}
            except Exception:  # noqa: BLE001
                pass
        last = schedules.last_runs(backup, plans, history, tn, joint)
        if self.app.platform_ready("dspace") and bridge.has_task("dspace-panel"):
            try:
                from ..dspace import payload
                out = await bridge.task("dspace-panel", "operations", "plans")
                if out.ok:
                    data = payload(out)
                    self.operation_plans = data.get('plans', [])
                    last.update(schedules.operation_last_runs(data))
            except Exception:  # noqa: BLE001 - the rows then say "No run recorded"
                pass
        return last

    def _values(self, i):
        return dict(enabled=self.query_one(f"#sc-on-{i}", Switch).value,
                    freq=self.query_one(f"#sc-freq-{i}", Select).value,
                    day=int(self.query_one(f"#sc-day-{i}", Select).value),
                    time=self.query_one(f"#sc-time-{i}", Input).value,
                    raw=self.query_one(f"#sc-raw-{i}", Input).value)

    def _remember(self):
        if not self.ready: return
        for i, row in enumerate(self.rows):
            if id(row) in self.controls and self.query(f"#sc-on-{i}"):
                key = (row.source, row.key)
                values = self._values(i)
                if values != self.controls[id(row)].values():
                    self.drafts[key] = values
                else:
                    self.drafts.pop(key, None)

    def _draw(self) -> None:
        self._remember()
        self.run_worker(self._render_rows(), group="schedule-render", exclusive=False, exit_on_error=False)

    async def _render_rows(self):
        # Never cancel an in-flight remove_children: cancellation can also
        # cancel widget message pumps and leave a terminal filter hanging.
        if self._render_lock is None:
            self._render_lock = asyncio.Lock()
        async with self._render_lock:
            await self._render_rows_unlocked()

    async def _render_rows_unlocked(self):
        box = self.query_one("#sc-rows", Vertical)
        await box.remove_children()
        shown = schedules.shown(self.rows, self.platform, self.kind)
        if not shown:
            await box.mount(Static(t("Nothing is scheduled here.") if not self.rows else
                                   t("Nothing scheduled matches this filter."), classes="sc-row sc-description", markup=False))
            return
        for i, row in enumerate(self.rows):
            if row not in shown: continue
            control = self.controls.get(id(row))
            block = Vertical(classes=f"sc-row -{row.state}")
            await box.mount(block)
            await block.mount(Static(row_text(row), classes="sc-description"))
            if control is None:
                reason = ("Linked schedule: change the platform backup schedule above." if row.key in ('tainacan:maintain', 'tainacan:verify')
                          else "Read-only: managed by its original tool or package.")
                await block.mount(Label(t(reason), classes="sc-note"))
                continue
            values = self.drafts.get((row.source, row.key), control.values())
            toolbar = Horizontal(classes="sc-controls")
            await block.mount(toolbar)
            await toolbar.mount(Label(t("Active"), classes="sc-switch-label"),
                Switch(values['enabled'], id=f"sc-on-{i}", disabled=not control.available),
                Select([(t(cron.FREQS[f]), f) for f in control.frequencies], value=values['freq'], allow_blank=False, id=f"sc-freq-{i}"),
                Select(day_options(values['freq'], day_value(values['freq'], values['day'])), value=day_value(values['freq'], values['day']), allow_blank=False, id=f"sc-day-{i}"),
                Input(values['time'], id=f"sc-time-{i}", placeholder="HH:MM", max_length=5),
                Input(values['raw'], id=f"sc-raw-{i}", placeholder=t("Cron expression")),
                Button(t("Save"), id=f"sc-save-{i}", disabled=not control.available))
            button = toolbar.query_one(f"#sc-save-{i}", Button)
            button.schedule_control = control
            toolbar.query_one(f"#sc-day-{i}", Select).day_kind = values['freq']
            button.tooltip = t("Review and save this schedule")
            self.query_one(f"#sc-on-{i}").tooltip = t("Enabled after saving")
            self.query_one(f"#sc-freq-{i}").tooltip = t("Frequency")
            self.query_one(f"#sc-time-{i}").tooltip = t("Server time (HH:MM)")
            if control.note:
                await block.mount(Label(t(control.note), classes="sc-note"))
            if not control.available:
                await block.mount(Label(t("Read-only: the schedule contains manual changes or its settings could not be read. Use its original editor."), classes="sc-note"))
            self._fields(i)

    def on_switch_changed(self, event: Switch.Changed):
        if event.switch.id and event.switch.id.startswith('sc-on-'):
            event.stop()
            self._fields(int(event.switch.id.removeprefix('sc-on-')))

    def _fields(self, i):
        # Initial Select events may arrive before its siblings finish mounting.
        if not all(self.query(f"#{key}-{i}") for key in ('sc-freq','sc-day','sc-time','sc-raw','sc-on')): return
        freq = self.query_one(f"#sc-freq-{i}", Select).value
        enabled = self.query_one(f"#sc-on-{i}", Switch).value and self.controls[id(self.rows[i])].available
        for key in ('sc-freq','sc-day','sc-time','sc-raw'):
            self.query_one(f"#{key}-{i}").disabled = not enabled
        day = self.query_one(f"#sc-day-{i}", Select)
        if freq in ('weekly', 'monthly') and getattr(day, 'day_kind', None) != freq:
            target = day_value(freq, day.value)
            day.set_options(day_options(freq))
            day.day_kind = freq
            # set_options already picked the first day; when that equals the
            # target, Select keeps the old label (e.g. "1" instead of Monday).
            day.set_reactive(Select.value, Select.BLANK)
            day.value = target
        day.display = freq in ('weekly','monthly')
        self.query_one(f"#sc-time-{i}").display = freq != 'custom'
        self.query_one(f"#sc-raw-{i}").display = freq == 'custom'

    async def _save(self, i, expected=None):
        if self.loading or self.saving or not 0 <= i < len(self.rows): return
        row = self.rows[i]
        control = self.controls.get(id(row))
        if control is None or not control.available or (expected is not None and expected is not control): return
        try:
            values = control.edited(self._values(i))
            if control.driver == 'koha': control.koha_text(values)
        except EditError as error:
            self.app.notify(t(str(error)), severity='warning')
            return
        if values == control.values() and not control.out_of_sync:
            self.app.notify(t("Nothing changed."))
            return
        if values['enabled'] and control.driver == 'tainacan' and not self.tainacan_settings.get('key'):
            self.app.notify(t("Configure the backup key in the Backup center first."), severity='warning')
            return
        self._remember()
        self.saving = True
        try:
            summary = cron.Job('', '', '', freq=values['freq'], day=values['day'], raw=values['raw'])
            if values['freq'] != 'custom': summary.hour, summary.minute = cron.parse_time(values['time'])
            description = t("Switched off") if not values['enabled'] else schedules.describe(summary.schedule())
            if not await self.app.push_screen_wait(ConfirmScreen(t("Schedules"),
                    t(schedules.PLATFORM_LABELS.get(row.platform, row.platform)) + ' · ' + row.name + '\n' + description + '\n\n' + t(control.note or "Only this task is changed. Other schedules are kept."))):
                return
            from ..routines.schedules import apply
            if await apply(self.app, control, values):
                self.drafts.pop((row.source,row.key), None)
                await self._load()
        finally:
            self.saving = False
