"""CronView: Koha's scheduled tasks, on or off, how often and when.

One row per job of /etc/cron.d/koha_tasks (cron.py): a switch, how often
(daily, weekly, monthly, or a schedule written by hand), the day and the
time. The presets the panel knows are always there (a full index rebuild,
fines, authority linking...), off until switched on; lines written by hand
keep their own schedule. Save shows what changes and hands the whole file
to `config.sh --task cron-apply`, which checks it and keeps a copy of the
old one. No text editor.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, Static, Switch

from .. import cron
from ..i18n import t
from ..screens.dialogs import ConfirmScreen, TextScreen
from .base import SectionView


class CronView(SectionView):
    loaded = False
    drawn = False

    def __init__(self, section):
        super().__init__(section)
        self.cf = cron.defaults(self._instance())

    def _instance(self) -> str:
        try:
            return self.app.env.instance
        except Exception:     # noqa: BLE001 (before the app is there)
            return "library"

    def compose(self) -> ComposeResult:
        yield from self.heading()
        yield Static(t("The jobs this server runs by itself. Switch a job on or off, choose how often and at what "
                       "time, then Save: the old schedule is kept as koha_tasks.bak. Lines you wrote by hand are "
                       "kept as they are."), classes="view-prompt", markup=False)
        with Horizontal(classes="quick-actions"):
            yield Button(t("Save"), id="cr-save", classes="small", variant="success")
            yield Button(t("Preview"), id="cr-preview", classes="small")
            yield Button(t("Reload"), id="cr-reload", classes="small")
            yield Button(t("Defaults"), id="cr-defaults", classes="small")
        yield Vertical(id="cr-rows")

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            self.reload()

    # ------------------------------------------------------------------
    # Rows
    # ------------------------------------------------------------------
    def reload(self) -> None:
        self.cf = cron.parse(cron.read(), self.app.env.instance)
        self.draw()

    def draw(self) -> None:
        self.drawn = False
        self.run_worker(self._draw(), exclusive=True, group="cron-draw", exit_on_error=False)

    async def _draw(self) -> None:
        box = self.query_one("#cr-rows", Vertical)
        await box.remove_children()
        rows = []
        for i, job in enumerate(self.cf.jobs):
            preset = cron.BY_KEY.get(job.key)
            freqs = preset.freqs if preset else tuple(cron.FREQS)
            if job.freq not in freqs:
                freqs = (*freqs, job.freq)
            label = t(job.label) if job.key else _own_label(job)
            row = Horizontal(classes="cron-row", id=f"cr-row-{i}")
            widgets = [
                Switch(job.enabled, id=f"cr-on-{i}"),
                Vertical(Label(label, classes="cron-name"),
                         Label(t(preset.help) if preset and preset.help else "", classes="cron-help"),
                         classes="cron-text"),
                Select([(t(cron.FREQS[f]), f) for f in freqs], value=job.freq, allow_blank=False,
                       id=f"cr-freq-{i}", classes="cron-freq"),
                Select(_day_options(job.freq), value=_day_value(job), allow_blank=False, id=f"cr-day-{i}",
                       classes="cron-day"),
                Input(job.time(), id=f"cr-time-{i}", classes="cron-time", max_length=5),
                Input(job.raw or job.schedule(), id=f"cr-raw-{i}", classes="cron-raw"),
            ]
            rows.append((row, widgets, job.freq))
        for row, widgets, _freq in rows:
            await box.mount(row)
            await row.mount(*widgets)
        for i, (_row, _widgets, freq) in enumerate(rows):
            self._show_fields(i, freq)
        self.drawn = True

    def _show_fields(self, i: int, freq: str) -> None:
        self.query_one(f"#cr-day-{i}").display = freq in ("weekly", "monthly")
        self.query_one(f"#cr-time-{i}").display = freq != "custom"
        self.query_one(f"#cr-raw-{i}").display = freq == "custom"

    def on_select_changed(self, event: Select.Changed) -> None:
        wid = event.select.id or ""
        if not wid.startswith("cr-freq-"):
            return
        i = int(wid.rsplit("-", 1)[1])
        freq = str(event.value)
        day = self.query_one(f"#cr-day-{i}", Select)
        job = cron.with_freq(self.cf.jobs[i], freq)
        day.set_options(_day_options(freq))
        day.value = _day_value(job)
        self._show_fields(i, freq)

    def collect(self) -> tuple[list[cron.Job], str]:
        """The jobs as set on the screen, or the first thing to fix."""
        jobs = []
        for i, old in enumerate(self.cf.jobs):
            freq = str(self.query_one(f"#cr-freq-{i}", Select).value)
            job = cron.Job(old.key, old.label, old.command, self.query_one(f"#cr-on-{i}", Switch).value,
                           freq, user=old.user, note=list(old.note))
            name = t(old.label) if old.key else _own_label(old)
            if freq == "custom":
                raw = " ".join(self.query_one(f"#cr-raw-{i}", Input).value.split())
                problem = cron.schedule_problem(raw)
                if problem:
                    return [], f"{name}: {t(problem)}"
                job.raw = raw
            else:
                hm = cron.parse_time(self.query_one(f"#cr-time-{i}", Input).value)
                if hm is None:
                    return [], f"{name}: {t('type the time as HH:MM, for example 23:00')}"
                job.hour, job.minute = hm
                day = self.query_one(f"#cr-day-{i}", Select).value
                job.day = int(day) if freq in ("weekly", "monthly") and day is not Select.BLANK else 0
            jobs.append(job)
        return jobs, ""

    def new_text(self) -> tuple[str, str]:
        jobs, problem = self.collect()
        if problem:
            return "", problem
        text = cron.render(cron.CronFile(jobs, self.cf.env, self.cf.blocks))
        problem = cron.file_problem(text)
        return text, t(problem) if problem else ""

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {"cr-save": self.save, "cr-preview": self.preview, "cr-reload": self.reload,
                   "cr-defaults": self.defaults}
        if event.button.id in actions:
            event.stop()
            actions[event.button.id]()

    def defaults(self) -> None:
        self.cf = cron.defaults(self.app.env.instance)
        keep = cron.parse(cron.read(), self.app.env.instance)
        self.cf.jobs += [j for j in keep.jobs if not j.key]    # lines written by hand stay
        self.cf.env, self.cf.blocks = keep.env, keep.blocks
        self.draw()
        self.app.notify(t("Default schedules on the screen: Save to keep them."))

    def preview(self) -> None:
        text, problem = self.new_text()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        self.app.push_screen(TextScreen(t("Active Tasks in /etc/cron.d/koha_tasks"), text))

    def save(self) -> None:
        text, problem = self.new_text()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        self.app.run_worker(self._save(text), group="routine", exclusive=True, exit_on_error=False)

    async def _save(self, text: str) -> None:
        from ..routines.common import run_task, show_done
        title = t("⏰  Schedules & cron tasks")
        jobs, _ = self.collect()
        changes = []
        for old, new in zip(self.cf.jobs, jobs):
            name = t(old.label) if old.key else _own_label(old)
            if old.enabled != new.enabled:
                changes.append(f"{name}: {t('on') if new.enabled else t('off')}")
            elif new.enabled and old.schedule() != new.schedule():
                changes.append(f"{name}: {_when(new)}")
        if not changes:
            self.app.notify(t("Nothing changed."))
            return
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Save these changes to the schedules?"), preview="\n".join(changes))):
            return
        path = cron.write_temp(text)
        try:
            result = await run_task(self.app, title, "cron-apply", str(path))
        finally:
            path.unlink(missing_ok=True)
        await show_done(self.app, title, result)
        self.reload()


def _own_label(job: cron.Job) -> str:
    for line in job.note:
        text = line.lstrip("#").strip()
        if text and not text.startswith("="):
            return text[:70]
    return job.command[:70]


def _day_options(freq: str) -> list[tuple[str, int]]:
    if freq == "monthly":
        return [(t("Day ${n}", n=d), d) for d in range(1, 29)]
    return [(t(name), i) for i, name in enumerate(cron.WEEKDAYS)]


def _day_value(job: cron.Job) -> int:
    if job.freq == "monthly":
        return min(max(job.day, 1), 28)
    return job.day % 7


def _when(job: cron.Job) -> str:
    if job.freq == "daily":
        return t("Daily at ${time}", time=job.time())
    if job.freq == "weekly":
        return t("Weekly, ${day} at ${time}", day=t(cron.WEEKDAYS[job.day % 7]), time=job.time())
    if job.freq == "monthly":
        return t("Monthly, day ${n} at ${time}", n=job.day, time=job.time())
    return job.raw
