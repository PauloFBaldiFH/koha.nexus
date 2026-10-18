"""EnrichView: "Enrich bibliographic catalog", the panel side of the
enrichment jobs (enrichment/nexus_jobs, installer section "Enrichment jobs").

Retired from the menus in 1.5.94: On-demand enrichment (views/ondemand.py,
a subclass of this view) is the one bibliographic enrichment screen. This
view stays registered (VIEWS["enrich"]) and its tasks stay in the
installer, but no key, card or sidebar row opens it.

Top, a new job: the scope ("all", or biblionumbers such as 101, 102,
500-550) goes to `config.sh --task enrich-job-add`, which exports the
records at low priority and starts the worker. Then the worker's state
(progress, paused, busy machine) with Pause / Resume (`enrich-pause`), and
the jobs (`enrich-jobs`), refreshed every few seconds while one is running.

Bottom, the chosen job (`enrich-job-show`): the staged report's counts
(enriched, review, M0/M1/W/R), the changed records and, for the one picked,
its before/after diff (`enrich-job-diff`: added lines in green). "Open
report" copies report.html to the Downloads folder and opens it in the
browser. Apply (`enrich-job-apply`: safety backup, then Koha's staged
import) and Revert (`enrich-job-revert`) ask first and cannot be cancelled
half way.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, ProgressBar, RadioButton, RadioSet, Static

from ..i18n import t
from ..screens.dialogs import ConfirmScreen
from .base import SectionView

SCOPE = re.compile(r"^\s*(all|\*|\d+(\s*-\s*\d+)?([\s,;]+\d+(\s*-\s*\d+)?)*)\s*$", re.I)
# Job states while something still moves: the list refreshes itself.
ACTIVE = ("queued", "exported", "matching", "applying", "reverting")
REFRESH_SECONDS = 4.0


def state_text(state: str) -> str:
    return {
        "queued": t("Exporting"),
        "exported": t("Waiting for the worker"),
        "matching": t("Comparing"),
        "ready": t("Report ready"),
        "applying": t("Applying"),
        "partly-applied": t("Partly applied"),
        "applied": t("Applied"),
        "reverting": t("Reverting"),
        "reverted": t("Reverted"),
        "failed": t("Failed"),
        "cancelled": t("Cancelled"),
    }.get(state, state)


def valid_scope(text: str) -> bool:
    return bool(SCOPE.match(text or ""))


def summary_text(job: dict) -> str:
    rep = job.get("report") or {}
    if not rep:
        if job.get("state") == "failed":
            return t("Failed: ${error}", error=job.get("error", ""))
        return t("The report appears here when the comparison ends.")
    w = rep.get("records_with", {})
    lines = [
        t("Records read ${n} · Enriched ${e} · Unchanged ${u} · Review ${r} · No match ${m} · Errors ${x}",
          n=rep.get("records", 0), e=rep.get("enriched", 0), u=rep.get("unchanged", 0), r=rep.get("review", 0),
          m=rep.get("no_match", 0), x=rep.get("errors", 0)),
        t("Records with M0 ${m0} · M1 ${m1} · W ${w} · R ${r} · Fields to add ${f} · Koha batches ${b}",
          m0=w.get("M0", 0), m1=w.get("M1", 0), w=w.get("W", 0), r=w.get("R", 0), f=rep.get("fields_added", 0),
          b=rep.get("koha_batches", 0)),
    ]
    sources = rep.get("fields_by_source") or {}
    if sources:
        lines.append(t("Sources: ${list}", list=", ".join(f"{k} {v}" for k, v in list(sources.items())[:8])))
    if rep.get("release"):
        lines.append(t("Enrichment database: ${name}", name=rep["release"]))
    return "\n".join(lines)


def auth_summary_text(job: dict) -> str:
    rep = job.get("report") or {}
    if not rep:
        return summary_text(job)
    h = rep.get("headings", {})
    lines = [
        t("Records read ${n} · Changed ${c} · Unchanged ${u} · Review ${r} · Errors ${x}",
          n=rep.get("records", 0), c=rep.get("changed", 0), u=rep.get("unchanged", 0), r=rep.get("review", 0),
          x=rep.get("errors", 0)),
        t("Headings ${n}: linked to Koha ${k} · to new authorities ${new} · forms standardised ${s} · "
          "review ${r} · no match ${m} · already linked ${l}",
          n=h.get("read", 0), k=h.get("koha", 0), new=h.get("new", 0), s=h.get("standardized", 0),
          r=h.get("review", 0), m=h.get("no_match", 0), l=h.get("linked_before", 0)),
        t("New authority records ${n} (preliminary ${p}) · Koha batches ${b}", n=rep.get("new_authorities", 0),
          p=rep.get("preliminary", 0), b=rep.get("koha_batches", 0)),
    ]
    sources = rep.get("new_by_source") or {}
    if sources:
        lines.append(t("Sources: ${list}", list=", ".join(f"{k} {v}" for k, v in list(sources.items())[:8])))
    if rep.get("release"):
        lines.append(t("Enrichment database: ${name}", name=rep["release"]))
    return "\n".join(lines)


def diff_text(lines: list[str]) -> Text:
    out = Text()
    for line in lines:
        if line.startswith("+ "):
            out.append(line + "\n", style="bold green")
        elif line.startswith("- "):
            out.append(line + "\n", style="bold red")
        elif line.startswith("#"):
            out.append(line + "\n", style="dim")
        else:
            out.append(line + "\n")
    return out


def classes(row: dict) -> str:
    return " ".join(c for c in ("M0", "M1", "W", "R") if row.get(c.lower()))


class EnrichView(SectionView):
    loaded = False
    KIND = "bib"            # the jobs this screen lists (nexus_jobs' job kind)
    ORIGIN = "batch"        # and their origin (batch, or ondemand: views/ondemand.py)
    DEFAULT_SCOPE = "all"   # an empty scope box

    # -- what differs between the bibliographic and the authority screen --
    def intro(self) -> str:
        return t("Adds what your records lack (subjects, classification, notes, extent) from the "
                 "koha.nexus enrichment database. Nothing reaches the catalogue until you read the "
                 "report and choose Apply; Apply makes a safety backup first and can be reverted.")

    def compose_options(self) -> ComposeResult:
        yield from ()

    def start_task(self, scope: str) -> tuple[str, list[str]]:
        return "enrich-job-add", [scope]

    def start_title(self) -> str:
        return t("Enrich bibliographic data")

    def summary(self, job: dict) -> str:
        return summary_text(job)

    def apply_question(self, rep: dict, job_id: int) -> str:
        return t("Write the ${n} enriched record(s) of job ${id} into the catalogue? A verified safety backup "
                 "is made first, then Koha's staged import adds the fields, at most 500 records at a time. "
                 "Records edited after the report are left as they are. Revert undoes it.",
                 n=rep.get("enriched", 0), id=job_id)

    def revert_question(self, job_id: int) -> str:
        return t("Undo job ${id}? A verified safety backup is made first, then each Koha batch is reverted: "
                 "the records get their previous version back. Records edited in Koha after Apply are kept.",
                 id=job_id)

    def change_columns(self) -> tuple[str, str]:
        return t("Class"), t("Fields")

    def scope_problem(self, scope: str) -> str:
        """Why SCOPE cannot start a job ("" when it can)."""
        if valid_scope(scope):
            return ""
        return t("Not a valid scope: use all, or biblionumbers such as 101, 102, 500-550.")

    def scope_label(self, job: dict) -> str:
        return job.get("scope", "")

    def change_cells(self, c: dict) -> tuple[str, str]:
        return classes(c), str(c.get("added", 0))

    def __init__(self, section):
        super().__init__(section)
        self.jobs: list[dict] = []
        self.worker: dict = {}
        self.job: dict = {}             # the chosen job, as enrich-job-show gave it
        self.job_id: int | None = None
        self._timer = None

    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield from self.heading()
            yield Button(t("Reload"), id="e-reload", classes="small")
        yield Static(self.intro(), classes="view-prompt", markup=False)
        with Vertical(id="e-new", classes="hub-box"):
            yield from self.compose_new()
        with Vertical(id="e-worker", classes="hub-box"):
            yield from self.compose_worker()
        with Vertical(id="e-jobs", classes="hub-box z-wide"):
            table = DataTable(id="e-table", zebra_stripes=True, cursor_type="row", classes="hub-table")
            table.add_column(t("Job"), key="id")
            table.add_column(t("Created"), key="created")
            table.add_column(t("Scope"), key="scope")
            table.add_column(t("State"), key="state")
            table.add_column(t("Progress"), key="progress")
            yield table
        with Vertical(id="e-report", classes="hub-box z-wide"):
            yield Static(t("Choose a job in the list."), id="e-summary", markup=False)
            with Horizontal(classes="quick-actions"):
                yield Button(t("Open report"), id="e-open", classes="small", disabled=True)
                yield Button(t("Apply"), id="e-apply", classes="small", variant="success", disabled=True)
                yield Button(t("Revert"), id="e-revert", classes="small", variant="warning", disabled=True)
                yield Button(t("Cancel job"), id="e-cancel", classes="small", disabled=True)
                yield from self.compose_report_buttons()
            changes = DataTable(id="e-changes", zebra_stripes=True, cursor_type="row", classes="hub-table")
            changes.add_column(t("Biblionumber"), key="bn")
            changes.add_column(t("Result"), key="status")
            col_cls, col_added = self.change_columns()
            changes.add_column(col_cls, key="cls")
            changes.add_column(col_added, key="added")
            changes.add_column(t("Title"), key="title")
            yield changes
            yield Static("", id="e-diff", classes="e-diff")
            yield from self.compose_report_extra()

    def compose_new(self) -> ComposeResult:
        yield Static(t("Which records: all, or biblionumbers such as 101, 102, 500-550."),
                     classes="ai-note", markup=False)
        with Horizontal(classes="quick-actions"):
            yield Input(placeholder="all", id="e-scope")
            yield Button(t("Start"), id="e-start", classes="small", variant="primary")
        yield from self.compose_options()

    def compose_worker(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="e-worker-state")
        yield ProgressBar(total=None, show_eta=False, id="e-progress")
        with Horizontal(classes="quick-actions"):
            yield Button(t("Pause"), id="e-pause", classes="small")
            yield Button(t("Resume"), id="e-resume", classes="small")

    def compose_report_buttons(self) -> ComposeResult:
        yield from ()

    def compose_report_extra(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.query_one("#e-new").border_title = t("New job")
        self.query_one("#e-worker").border_title = t("Worker (a quarter of one CPU, in the background)")
        self.query_one("#e-jobs").border_title = t("Jobs")
        self.query_one("#e-report").border_title = t("Staged report")

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            self._timer = self.set_interval(REFRESH_SECONDS, self._tick)
        self.reload()

    def refresh_data(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.run_worker(self._load(), exclusive=True, group="enrich-load", exit_on_error=False)

    def _tick(self) -> None:
        if not self.display or not self.is_on_screen:
            return
        moving = any(j.get("state") in ACTIVE for j in self.jobs) or self.worker.get("state") == "matching"
        if moving:
            self.reload()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    async def _call(self, name: str, *args: str):
        try:
            return await self.app.bridge.task(name, *args)
        except Exception:     # noqa: BLE001 (no installer: the screen says nothing was read)
            return None

    async def _load(self) -> None:
        out = await self._call("enrich-jobs")
        if out is None or not out.ok:
            self.query_one("#e-worker-state", Label).update(t("The enrichment service is not installed yet."))
            return
        try:
            self.jobs = [j for j in json.loads(out.get("jobs") or "[]", strict=False)
                         if (j.get("kind") or "bib") == self.KIND and (j.get("origin") or "batch") == self.ORIGIN]
            self.worker = json.loads(out.get("worker") or "{}", strict=False)
        except ValueError:
            self.jobs, self.worker = [], {}
        self.worker = await self.fetch_worker(self.worker)
        self.draw_worker()
        self.draw_jobs()
        if self.job_id is None and self.jobs:
            self.job_id = self.jobs[0]["id"]
        current = next((j for j in self.jobs if j["id"] == self.job_id), None)
        if current and (current.get("state") != self.job.get("state") or current.get("done") != self.job.get("done")
                        or self.job.get("id") != self.job_id):
            await self._load_job(self.job_id)

    async def _load_job(self, job_id: int) -> None:
        out = await self._call("enrich-job-show", str(job_id))
        if out is None or not out.ok:
            return
        try:
            job = json.loads(out.get("job") or "{}", strict=False)
        except ValueError:
            return
        if job.get("id") != job_id:
            return
        changed = job.get("state") != self.job.get("state") or job.get("id") != self.job.get("id")
        self.job = job
        self.draw_job(redraw_changes=changed or not self.query_one("#e-changes", DataTable).row_count)

    async def fetch_worker(self, worker: dict) -> dict:
        """The background state this screen shows (the batch worker's)."""
        return worker

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw_worker(self) -> None:
        w = self.worker
        label = self.query_one("#e-worker-state", Label)
        bar = self.query_one("#e-progress", ProgressBar)
        state = w.get("state", "idle")
        if state == "matching":
            text = t("● Comparing job ${job}: ${done} of ${total} records", job=w.get("job", "?"),
                     done=w.get("done", 0), total=w.get("total", 0))
            if w.get("paused"):
                why = t("pause button") if w.get("why") == "pause file" else t("the machine is busy")
                text = t("◐ Paused (${why}) at ${done} of ${total} records", why=why, done=w.get("done", 0),
                         total=w.get("total", 0))
            bar.update(total=max(int(w.get("total") or 0), 1), progress=int(w.get("done") or 0))
        else:
            text = t("○ Idle: no job is being compared.")
            if w.get("pause_file"):
                text += " " + t("(paused: new jobs wait until you resume)")
            bar.update(total=1, progress=1 if self.jobs else 0)
        label.update(text)
        for bid, off in (("#e-pause", bool(w.get("pause_file"))), ("#e-resume", not w.get("pause_file"))):
            for b in self.query(bid):
                b.disabled = off

    def draw_jobs(self) -> None:
        table = self.query_one("#e-table", DataTable)
        row = table.cursor_row
        table.clear()
        for j in self.jobs:
            total, done = int(j.get("total") or 0), int(j.get("done") or 0)
            progress = f"{done}/{total}" if total else "–"
            table.add_row(str(j["id"]), j.get("created", "")[:16], self.scope_label(j), state_text(j.get("state", "")),
                          progress, key=str(j["id"]))
        if self.jobs:
            table.move_cursor(row=min(max(row, 0), len(self.jobs) - 1))

    def draw_job(self, redraw_changes: bool = True) -> None:
        job = self.job
        state = job.get("state", "")
        head = t("Job ${id} · ${scope} · ${state}", id=job.get("id", "?"), scope=self.scope_label(job),
                 state=state_text(state))
        self.query_one("#e-summary", Static).update(head + "\n" + self.summary(job))
        rep = job.get("report") or {}
        enriched = int(rep.get("enriched", rep.get("changed", 0)))
        self.query_one("#e-open", Button).disabled = not job.get("report_html")
        self.query_one("#e-apply", Button).disabled = not (state in ("ready", "applying", "partly-applied")
                                                           and enriched > 0)
        self.query_one("#e-revert", Button).disabled = state not in ("applied", "partly-applied", "reverting")
        self.query_one("#e-cancel", Button).disabled = state not in ("queued", "exported", "matching", "ready")
        if not redraw_changes:
            return
        changes = self.query_one("#e-changes", DataTable)
        changes.clear()
        for c in job.get("changes", []):
            changes.add_row(str(c.get("biblionumber") or ""),
                            t("Changed") if c.get("status") == "enriched" and self.KIND == "auth" else
                            t("Enriched") if c.get("status") == "enriched" else t("Review"),
                            *self.change_cells(c), c.get("title", ""),
                            key=f"{c.get('biblionumber')}:{c.get('status')}")
        self.query_one("#e-diff", Static).update("")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "e-table" and event.row_key is not None and event.row_key.value:
            job_id = int(event.row_key.value)
            if job_id != self.job_id:
                self.job_id = job_id
                self.run_worker(self._load_job(job_id), exclusive=True, group="enrich-job", exit_on_error=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        if event.data_table.id == "e-changes" and event.row_key is not None and self.job_id is not None:
            bn = (event.row_key.value or "").split(":")[0]
            if bn.isdigit():
                self.run_worker(self._show_diff(self.job_id, bn), exclusive=True, group="enrich-diff",
                                exit_on_error=False)

    async def _show_diff(self, job_id: int, bn: str) -> None:
        out = await self._call("enrich-job-diff", str(job_id), bn)
        lines = out.lists.get("line", []) if out else []
        self.query_one("#e-diff", Static).update(diff_text(lines) if lines else t("No difference to show."))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "e-reload":
            self.reload()
        elif bid == "e-start":
            self.app.run_worker(self._start(), group="routine", exclusive=True, exit_on_error=False)
        elif bid in ("e-pause", "e-resume"):
            self.run_worker(self._pause(bid == "e-pause"), exit_on_error=False)
        elif bid == "e-open":
            self.app.run_worker(self._open_report(), group="routine", exclusive=True, exit_on_error=False)
        elif bid == "e-apply":
            self.app.run_worker(self._apply(), group="routine", exclusive=True, exit_on_error=False)
        elif bid == "e-revert":
            self.app.run_worker(self._revert(), group="routine", exclusive=True, exit_on_error=False)
        elif bid == "e-cancel":
            self.app.run_worker(self._cancel(), group="routine", exclusive=True, exit_on_error=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "e-scope":
            event.stop()
            self.app.run_worker(self._start(), group="routine", exclusive=True, exit_on_error=False)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    async def _start(self) -> None:
        from ..routines.common import failed, run_task, show_done
        scope = self.query_one("#e-scope", Input).value.strip() or self.DEFAULT_SCOPE
        problem = self.scope_problem(scope)
        if problem:
            self.app.notify(problem, severity="warning", timeout=6)
            return
        title = self.start_title()
        task, args = self.start_task(scope)
        result = await run_task(self.app, title, task, *args)
        if not failed(result) and result.value.get("job", "").isdigit():
            self.job_id = int(result.value.get("job"))
            self.job = {}
        await show_done(self.app, title, result)
        self.reload()

    async def _pause(self, on: bool) -> None:
        await self._call("enrich-pause", "on" if on else "off")
        self.app.notify(t("The worker stops after its current batch.") if on else t("The worker goes on."),
                        timeout=4)
        await self._load()

    async def _cancel(self) -> None:
        if self.job_id is None:
            return
        title = t("Cancel job")
        if not await self.app.push_screen_wait(ConfirmScreen(title, t(
                "Cancel job ${id}? Nothing was written to the catalogue; its report is kept.", id=self.job_id))):
            return
        await self._call("enrich-job-cancel", str(self.job_id))
        self.job = {}
        await self._load()

    async def _apply(self) -> None:
        from ..routines.common import run_task, show_done
        job_id = self.job_id
        rep = self.job.get("report") or {}
        if job_id is None:
            return
        title = t("Apply")
        question = self.apply_question(rep, job_id)
        if not await self.app.push_screen_wait(ConfirmScreen(title, question, danger=True)):
            return
        result = await run_task(self.app, title, "enrich-job-apply", str(job_id), cancellable=False)
        await show_done(self.app, title, result)
        self.job = {}
        await self._load()

    async def _revert(self) -> None:
        from ..routines.common import run_task, show_done
        job_id = self.job_id
        if job_id is None:
            return
        title = t("Revert")
        question = self.revert_question(job_id)
        if not await self.app.push_screen_wait(ConfirmScreen(title, question, danger=True)):
            return
        result = await run_task(self.app, title, "enrich-job-revert", str(job_id), cancellable=False)
        await show_done(self.app, title, result)
        self.job = {}
        await self._load()

    async def _open_report(self) -> None:
        """report.html copied to the Downloads folder (Windows' under WSL) and
        opened in the browser; where there is none, its path is copied."""
        src = Path(self.job.get("report_html") or "")
        name = f"koha-nexus-enrichment-job-{self.job.get('id', 0)}.html"
        if self.app.env.demo:
            self.app.notify(t("Report: ${file}", file=name), timeout=5)
            return
        from ..opener import _windows_path, open_url
        from ..transfer import downloads_folder

        def copy() -> Path | None:
            folder = downloads_folder()
            if folder is None or not src.is_file():
                return None
            target = folder / name
            shutil.copyfile(src, target)
            return target
        try:
            target = await asyncio.to_thread(copy)
        except OSError:
            target = None
        if target is None:
            self.app.copy_to_clipboard(str(src), quiet=True)
            self.app.notify(t("The report is at ${file} (path copied).", file=str(src)), timeout=8)
            return
        where = _windows_path(str(target)) or str(target)
        if not open_url(where):
            self.app.copy_to_clipboard(where, quiet=True)
        self.app.notify(t("Report saved in Downloads: ${file}", file=target.name), timeout=6)


class AuthEnrichView(EnrichView):
    """"Enrich & standardize authorities": the same jobs screen for
    authority jobs (`enrich-auth-add SCOPE MODE`). Each name and subject
    heading is matched with Koha's own authorities, then the enrichment
    database (Biblioteca Nacional first, then the other Brazilian sources,
    then the Library of Congress); Apply creates the new authorities, then
    links the records ($9) and puts their headings in the authorised form."""

    KIND = "auth"

    def intro(self) -> str:
        return t("Links the names and subjects of your records to authority records: your own Koha authorities "
                 "first, then the koha.nexus enrichment database (Biblioteca Nacional first, then Brazilian "
                 "catalogues, then the Library of Congress). Headings get the authorised form; missing "
                 "authorities are created. Nothing reaches the catalogue until you read the report and choose "
                 "Apply; Apply makes a safety backup first and can be reverted.")

    def compose_options(self) -> ComposeResult:
        with RadioSet(id="e-mode"):
            yield RadioButton(t("Exact forms only"), value=True, id="e-mode-exact")
            yield RadioButton(t("Also close forms (a typo; new authorities marked preliminary)"), id="e-mode-fuzzy")

    def mode(self) -> str:
        return "fuzzy" if self.query_one("#e-mode-fuzzy", RadioButton).value else "exact"

    def start_task(self, scope: str) -> tuple[str, list[str]]:
        return "enrich-auth-add", [scope, self.mode()]

    def start_title(self) -> str:
        return t("Enrich & standardize authorities")

    def summary(self, job: dict) -> str:
        return auth_summary_text(job)

    def change_columns(self) -> tuple[str, str]:
        return t("Standardised"), t("Linked")

    def change_cells(self, c: dict) -> tuple[str, str]:
        return str(c.get("w", 0)), str(c.get("added", 0))

    def apply_question(self, rep: dict, job_id: int) -> str:
        return t("Apply job ${id}? A verified safety backup is made first. Then ${a} new authority record(s) are "
                 "created and ${n} record(s) are linked to their authorities through Koha's staged import, at most "
                 "500 at a time. Records edited after the report are left as they are. Revert undoes it.",
                 id=job_id, a=rep.get("new_authorities", 0), n=rep.get("changed", 0))

    def revert_question(self, job_id: int) -> str:
        return t("Undo job ${id}? A verified safety backup is made first. The records get their previous version "
                 "back, then the authority records the job created are removed, except those a record still "
                 "links to. Records edited in Koha after Apply are kept.", id=job_id)
