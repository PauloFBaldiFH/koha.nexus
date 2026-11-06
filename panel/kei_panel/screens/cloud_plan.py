"""PlanFormScreen: one cloud backup of Automatic cloud backup, created or
changed. A cloud backup is a connection and a folder in it, what it sends
(the database, the MARC21 package or both), when it runs and how long the
copies stay in the cloud. There can be as many as the library wants, each
to another service or account, each on its own schedule.

  ╭ ☁ New cloud backup ────────────────────────────────────────────╮
  │ Name [gdrive-daily]            Connection [gdrive · Google Drive]│
  │ Folder in the cloud [koha/library]                               │
  │   → gdrive:koha/library/Backup_SQL_Koha/ and .../Backup_MARC_Koha/│
  │ Sends [SQL + MARC21]                                             │
  │ [■] Scheduled  [Daily] [Sunday] [23:30]                          │
  │ Kept in the cloud [30 days] [  ]                                 │
  │                                          [Cancel] [💾 Save]      │
  ╰──────────────────────────────────────────────────────────────────╯

The schedule is the cloud backup's own line in /etc/cron.d/koha_tasks, so
Schedules & cron tasks shows the same row. The screen closes with a dict
(id, remote, base, keep, job) or None.
"""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch

from .. import cloud, cron
from ..i18n import t

KEEP_CHOICES = (0, 7, 14, 30, 60, 90, 180, 365)
CUSTOM = -1
WHATS = (("SQL + MARC21", "sql+marc"), ("Database only (SQL)", "sql"), ("MARC21 only", "marc"))


class PlanFormScreen(ModalScreen[Optional[dict]]):
    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, remotes: list[cloud.Remote], taken: list[str], plan: cloud.Plan | None = None,
                 job: cron.Job | None = None, remote: str = "", base: str = "",
                 default_time: tuple[int, int] = (23, 30), services: dict[str, str] | None = None):
        super().__init__()
        self.remotes = remotes
        self.services = services or {}
        self.plan = plan
        self.taken = [n for n in taken if not plan or n != plan.id]
        start_remote = plan.remote if plan else (remote or (remotes[0].name if remotes else ""))
        self.job = job or cron.cloud_job(plan.id if plan else "new", hour=default_time[0], minute=default_time[1])
        self.start = {
            "id": plan.id if plan else cloud.free_plan_id(start_remote or "cloud", taken),
            "remote": start_remote,
            "base": plan.base if plan else cloud.clean_base(base),
            "keep": plan.keep if plan else 30,
        }

    def compose(self) -> ComposeResult:
        title = t("✏ Edit cloud backup") if self.plan else t("☁ New cloud backup")
        with Vertical(id="cp-box"):
            yield Label(title, classes="dialog-title", markup=False)
            with VerticalScroll(id="cp-form"):
                yield Label(t("Name (it names the row in Schedules & cron tasks too):"), classes="cr-label",
                            markup=False)
                yield Input(self.start["id"], id="cp-name", max_length=32)
                yield Label(t("Connection:"), classes="cr-label", markup=False)
                yield Select([(f"{r.name} · {self.services.get(r.name, r.kind)}", r.name) for r in self.remotes],
                             value=self.start["remote"] if self.start["remote"] in {r.name for r in self.remotes}
                             else Select.NULL, allow_blank=not self.remotes, id="cp-remote")
                yield Label(t("Folder in the cloud where the backup folders go (empty = the top):"),
                            classes="cr-label", markup=False)
                yield Input(self.start["base"], id="cp-base", placeholder=t("for example: koha/my-library"))
                yield Static("", id="cp-dest", classes="sb-hint", markup=False)
                yield Label(t("What it sends:"), classes="cr-label", markup=False)
                yield Select([(t(label), value) for label, value in WHATS], value=cron.cloud_what(self.job),
                             allow_blank=False, id="cp-what")
                yield Static(t("It sends the newest backup of this server; when there is none from the last day "
                               "(MARC21: the last week), it makes one first."), classes="sb-hint", markup=False)
                yield Label(t("When:"), classes="cr-label", markup=False)
                with Horizontal(classes="cb-plan-row"):
                    yield Switch(value=self.job.enabled, id="cp-on")
                    yield Label(t("Scheduled"), classes="cb-switch-label", markup=False)
                    freq = self.job.freq if self.job.freq in ("daily", "weekly", "monthly") else "daily"
                    yield Select([(t(cron.FREQS[f]), f) for f in ("daily", "weekly", "monthly")], value=freq,
                                 allow_blank=False, id="cp-freq", classes="cb-freq")
                    yield Select([(t(d), i) for i, d in enumerate(cron.WEEKDAYS)], value=0, allow_blank=False,
                                 id="cp-day", classes="cb-day")
                    yield Input(self.job.time(), id="cp-time", classes="cb-time", max_length=5)
                if self.job.freq == "custom":
                    yield Static(t("Its schedule was written by hand (${raw}): saving here makes it one of the "
                                   "above.", raw=self.job.raw), classes="sb-hint", markup=False)
                yield Label(t("Kept in the cloud:"), classes="cr-label", markup=False)
                with Horizontal(classes="cb-plan-row"):
                    keep = self.start["keep"]
                    yield Select([(t("Keep everything"), 0)] + [(t("${n} days", n=n), n) for n in KEEP_CHOICES[1:]]
                                 + [(t("Another number of days"), CUSTOM)],
                                 value=keep if keep in KEEP_CHOICES else CUSTOM, allow_blank=False, id="cp-keep",
                                 classes="cb-freq")
                    yield Input("" if keep in KEEP_CHOICES else str(keep), id="cp-keep-n", classes="cb-time",
                                max_length=4)
                yield Static(t("Copies older than this are deleted from its folders in the cloud after each "
                               "upload that worked; a failed upload never deletes anything."), classes="sb-hint",
                             markup=False)
                yield Static("", id="cp-problem", classes="dialog-error", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Cancel"), id="cp-cancel")
                yield Button(t("💾 Save"), id="cp-save", variant="success")

    def on_mount(self) -> None:
        self._days(str(self.query_one("#cp-freq", Select).value), self.job.day)
        self.query_one("#cp-keep-n").display = self.query_one("#cp-keep", Select).value == CUSTOM
        self._dest()

    # --- the fields -----------------------------------------------------------
    def _days(self, freq: str, day: int) -> None:
        sel = self.query_one("#cp-day", Select)
        if freq == "monthly":
            sel.set_options([(t("Day ${n}", n=n), n) for n in range(1, 29)])
            sel.value = min(max(day, 1), 28)
        else:
            sel.set_options([(t(d), i) for i, d in enumerate(cron.WEEKDAYS)])
            sel.value = day % 7
        sel.display = freq != "daily"

    @on(Select.Changed, "#cp-freq")
    def _freq(self, event: Select.Changed) -> None:
        day = self.query_one("#cp-day", Select).value
        self._days(str(event.value), day if isinstance(day, int) else 0)

    @on(Select.Changed, "#cp-keep")
    def _keep(self, event: Select.Changed) -> None:
        self.query_one("#cp-keep-n").display = event.value == CUSTOM

    @on(Select.Changed, "#cp-remote")
    @on(Select.Changed, "#cp-what")
    @on(Input.Changed, "#cp-base")
    def _dest(self) -> None:
        base = self.query_one("#cp-base", Input).value
        remote = self._remote()
        what = self.query_one("#cp-what", Select).value
        problem = cloud.base_problem(base)
        if problem:
            text = t(problem)
        elif remote is None:
            text = ""
        elif cloud.needs_bucket(remote.kind) and not cloud.clean_base(base):
            text = t("⚠ On this service the first folder is a bucket: type its name (for example "
                     "my-library-backups); it is created when it does not exist.")
        else:
            sql, marc = cloud.folders(base)
            dests = [f"{remote.name}:{sql}/"] if what != "marc" else []
            dests += [f"{remote.name}:{marc}/"] if what != "sql" else []
            text = "→ " + "  ·  ".join(dests)
        self.query_one("#cp-dest", Static).update(text)

    def _remote(self) -> cloud.Remote | None:
        value = self.query_one("#cp-remote", Select).value
        return next((r for r in self.remotes if r.name == value), None)

    # --- answers -------------------------------------------------------------------
    def collect(self) -> tuple[dict | None, str]:
        """(the answers, "") or (None, what to fix)."""
        plan_id = self.query_one("#cp-name", Input).value.strip()
        problem = cloud.plan_problem(plan_id, self.taken)
        if problem:
            return None, t("Name: ${why}", why=t(problem))
        remote = self._remote()
        if remote is None:
            return None, t("Choose a connection. A new one is made in Connections (➕ New connection).")
        base = self.query_one("#cp-base", Input).value
        problem = cloud.base_problem(base)
        if problem:
            return None, t(problem)
        if cloud.needs_bucket(remote.kind) and not cloud.clean_base(base):
            return None, t("Type the name of the bucket in the folder box first.")
        keep = self.query_one("#cp-keep", Select).value
        if keep == CUSTOM:
            n = self.query_one("#cp-keep-n", Input).value.strip()
            if cloud.keep_problem(n, low=1):
                return None, t("Days in the cloud: type a number of days (1 or more).")
            keep = int(n)
        hm = cron.parse_time(self.query_one("#cp-time", Input).value)
        if hm is None:
            return None, t("Type the time as HH:MM, for example 23:00.")
        what = str(self.query_one("#cp-what", Select).value)
        freq = str(self.query_one("#cp-freq", Select).value)
        day = self.query_one("#cp-day", Select).value
        job = cron.cloud_job(plan_id, what, hour=hm[0], minute=hm[1])
        job.enabled = self.query_one("#cp-on", Switch).value
        job.freq = freq
        job.day = day if isinstance(day, int) and freq != "daily" else 0
        job.user = self.job.user
        return {"id": plan_id, "remote": remote.name, "base": cloud.clean_base(base), "keep": int(keep or 0),
                "job": job, "old_id": self.plan.id if self.plan else ""}, ""

    @on(Button.Pressed, "#cp-save")
    def _save(self) -> None:
        answers, problem = self.collect()
        self.query_one("#cp-problem", Static).update(problem)
        if answers:
            self.dismiss(answers)

    @on(Button.Pressed, "#cp-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
