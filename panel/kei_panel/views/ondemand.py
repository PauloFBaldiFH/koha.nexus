"""OnDemandView: "On-demand enrichment", the panel side of the
koha-nexus-ondemand service (enrichment/nexus_ondemand, installer section
"On-demand enrichment").

The jobs screen of the retired batch "Enrich bibliographic catalog"
(views/enrich.py, no longer opened from the menus), for on-demand jobs only, searched now over direct Z39.50 servers (never the
koha.nexus gateways):
- all the records, or any biblionumbers (`enrich-od-add SCOPE`: a large
  job runs for hours in the background, record after record, and goes on
  after a restart), or a book typed by ISBN,
  title, author and year (`enrich-od-add --isbn X --title T ...`);
- while the service searches, each server it asks for the current record,
  with its state and time (`enrich-od-status`), refreshed every few seconds,
  how many records it searches at once, its speed and the time left, and
  a note while it waits for the internet to come back;
- the staged report, changes, diff, Apply and Revert of the batch screen
  (Apply saves a copy of those records instead of a full backup);
- "Search more servers" (`enrich-od-more`: a new round, the servers already
  asked passed over) and "Choose donor" (`enrich-od-donor`: the server
  whose record gives a group of fields, merged again without the network);
- for a typed book, the records found, and "Import as new record"
  (`enrich-od-import JOB SEQ N`: Koha's staged import, never over a record
  Koha already has; Library tools > Undo a MARC import takes it out).
"""

from __future__ import annotations

import json
import re

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Label, ProgressBar, Static

from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen
from .enrich import EnrichView, summary_text, valid_scope

YEAR = re.compile(r"^\d{4}$")
# The field groups a donor can be chosen for (nexus_enrich.merge.GROUPS).
SNAPSHOT_MAX = 50       # up to this many records, a copy of them instead of a full backup
GROUPS = ("subjects", "082", "080", "505", "520", "300", "024")


def group_label(group: str) -> str:
    return {
        "subjects": t("Subjects (6XX)"),
        "082": t("Dewey classification (082)"),
        "080": t("UDC classification (080)"),
        "505": t("Contents note (505)"),
        "520": t("Summary (520)"),
        "300": t("Physical description (300)"),
        "024": t("Other identifiers (024)"),
    }.get(group, group)


def eta_text(seconds) -> str:
    """Seconds left, for the person: "3 h 20 min", "12 min"."""
    s = int(seconds or 0)
    h, m = s // 3600, (s % 3600) // 60
    return t("${h} h ${m} min", h=h, m=m) if h else t("${m} min", m=max(1, m))


def speed_text(w: dict) -> str:
    """Records at once, per hour and time left, from the service's status."""
    parts = []
    if int(w.get("inflight") or 0) > 1:
        parts.append(t("${n} records at once", n=int(w["inflight"])))
    if w.get("per_hour"):
        parts.append(t("${n} per hour", n=int(w["per_hour"])))
    if w.get("eta_s"):
        parts.append(t("about ${time} left", time=eta_text(w["eta_s"])))
    return " · ".join(parts)


def server_state(state: str) -> str:
    """A server's state in ondemand-status.json, for the person."""
    m = re.match(r"^(\d+) record\(s\)$", state)
    if m:
        return t("${n} record(s)", n=m.group(1))
    head, _, why = state.partition(": ")
    if head == "down":
        return t("Down: ${why}", why=why)
    if head == "skipped":
        return t("Skipped: ${why}", why=why)
    return {"waiting": t("Waiting"), "searching": t("Searching…"), "no record": t("No record")}.get(state, state)


def query_label(job: dict) -> str:
    try:
        q = json.loads(job.get("query") or "{}")
    except ValueError:
        q = {}
    return " / ".join(str(q[k]) for k in ("isbn", "title", "author", "year") if q.get(k))


def attempts_text(job: dict) -> str:
    att = job.get("attempts") or []
    if not att:
        return ""
    asked = {a["target"] for a in att}
    found = {a["target"] for a in att if a.get("outcome") in ("found", "cached") and a.get("records")}
    trouble = {a["target"] for a in att if a.get("outcome") not in ("found", "cached", "none")} - found
    return t("Round ${r} · servers asked ${n} · with records ${f} · down or skipped ${d}",
             r=job.get("rounds", 1), n=len(asked), f=len(found), d=len(trouble))


class OnDemandView(EnrichView):
    ORIGIN = "ondemand"
    DEFAULT_SCOPE = "all"

    def __init__(self, section):
        super().__init__(section)
        self.picked_bn: str = ""
        self.servers_seen: tuple = ()

    def intro(self) -> str:
        return t("Searches public catalogues over direct Z39.50 connections only, for your records (all of them, or "
                 "the ones you list) or for a book you type. A large job runs for hours in the background and goes "
                 "on after a restart. Nothing reaches the catalogue until you read the report and choose Apply or "
                 "Import as new record.")

    def compose_new(self) -> ComposeResult:
        yield Static(t("Your records: all, or biblionumbers such as 101, 102, 500-510."),
                     classes="ai-note", markup=False)
        with Horizontal(classes="quick-actions"):
            yield Input(placeholder="all", id="e-scope")
            yield Button(t("Search"), id="e-start", classes="small", variant="primary")
        yield Static(t("Or a book to find and import as a new record: its ISBN, or its title (the author and the "
                       "year help)."), classes="ai-note", markup=False)
        with Horizontal(classes="quick-actions"):
            yield Input(placeholder="ISBN", id="od-isbn")
            yield Input(placeholder=t("Title"), id="od-title")
            yield Input(placeholder=t("Author"), id="od-author")
            yield Input(placeholder=t("Year"), id="od-year")
            yield Button(t("Find"), id="od-find", classes="small", variant="primary")

    def compose_worker(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="e-worker-state")
        yield ProgressBar(total=None, show_eta=False, id="e-progress")
        table = DataTable(id="od-servers", zebra_stripes=True, cursor_type="row", classes="hub-table")
        table.add_column(t("Server"), key="name")
        table.add_column(t("Country"), key="country")
        table.add_column(t("State"), key="state")
        table.add_column("ms", key="ms")
        yield table
        with Horizontal(classes="quick-actions"):
            yield Button(t("Pause"), id="e-pause", classes="small")
            yield Button(t("Resume"), id="e-resume", classes="small")

    def compose_report_buttons(self) -> ComposeResult:
        yield Button(t("Search more servers"), id="od-more", classes="small", disabled=True)
        yield Button(t("Choose donor"), id="od-donor", classes="small", disabled=True)

    def compose_report_extra(self) -> ComposeResult:
        yield Static("", id="od-found-note", classes="ai-note", markup=False)
        found = DataTable(id="od-found", zebra_stripes=True, cursor_type="row", classes="hub-table")
        found.add_column(t("Source"), key="source")
        found.add_column(t("Title"), key="title")
        found.add_column("ISBN", key="isbn")
        found.add_column(t("In the catalogue"), key="imported")
        yield found
        with Horizontal(classes="quick-actions"):
            yield Button(t("Import as new record"), id="od-import", classes="small", variant="success",
                         disabled=True)

    def on_mount(self) -> None:
        super().on_mount()
        self.query_one("#e-new").border_title = t("New search")
        self.query_one("#e-worker").border_title = t("Servers (direct Z39.50, a quarter of one CPU)")

    # -- what differs from the batch screen ---------------------------------
    def scope_problem(self, scope: str) -> str:
        if valid_scope(scope):
            return ""
        return t("Not a valid request: all, biblionumbers (such as 101, 102, 500-510), an ISBN, or a title.")

    def start_task(self, scope: str) -> tuple[str, list[str]]:
        return "enrich-od-add", [scope]

    def start_title(self) -> str:
        return t("Enrich from world catalogues")

    def scope_label(self, job: dict) -> str:
        return query_label(job) if job.get("query") else job.get("scope", "")

    def summary(self, job: dict) -> str:
        if job.get("query"):
            found = sum(len(q.get("found", [])) for q in job.get("found", []))
            if job.get("state") == "failed":
                text = summary_text(job)
            elif job.get("state") in ("ready",):
                text = t("Records found: ${n}. Pick one and choose Import as new record.", n=found) if found else \
                    t("No server had this book. Search more servers asks the ones not asked yet.")
            else:
                text = t("The records found appear here when the search ends.")
        else:
            text = summary_text(job)
        more = attempts_text(job)
        return text + ("\n" + more if more else "")

    def small(self) -> bool:
        """A small job saves a copy of its records instead of a full backup
        (the installer's enrich_od_small)."""
        return 0 < int((self.job.get("report") or {}).get("enriched", 0)) <= SNAPSHOT_MAX

    def apply_question(self, rep: dict, job_id: int) -> str:
        if not self.small():
            return super().apply_question(rep, job_id)
        return t("Write the ${n} enriched record(s) of job ${id} into the catalogue? A copy of these records is "
                 "saved first (not a full backup), then Koha's staged import adds the fields. Records edited after "
                 "the report are left as they are. Revert undoes it.", n=rep.get("enriched", 0), id=job_id)

    def revert_question(self, job_id: int) -> str:
        if not self.small():
            return super().revert_question(job_id)
        return t("Undo job ${id}? A copy of the records as they are now is saved first, then the records get their "
                 "previous version back. Records edited in Koha after Apply are kept.", id=job_id)

    async def fetch_worker(self, worker: dict) -> dict:
        """The service's state, with the shared pause file (the batch worker's status says it)."""
        out = await self._call("enrich-od-status")
        status: dict = {"state": "idle"}
        if out is not None and out.ok:
            try:
                status = json.loads(out.get("status") or "{}", strict=False) or status
            except ValueError:
                pass
        status["pause_file"] = bool(worker.get("pause_file"))
        return status

    # -- drawing -------------------------------------------------------------
    def draw_worker(self) -> None:
        w = self.worker
        label = self.query_one("#e-worker-state", Label)
        bar = self.query_one("#e-progress", ProgressBar)
        self.query_one("#e-pause", Button).disabled = bool(w.get("pause_file"))
        self.query_one("#e-resume", Button).disabled = not w.get("pause_file")
        if w.get("state") == "matching" and w.get("paused"):
            label.update(t("◐ Paused at record ${n} of ${total}: Resume goes on.", n=int(w.get("done") or 0),
                           total=w.get("total", 0)))
        elif w.get("state") == "matching" and w.get("outage"):
            label.update(t("◌ No internet connection: the job waits and asks again at ${time}.", time=w["outage"]))
        elif w.get("state") == "matching" and w.get("quota"):
            label.update(t("◌ The servers for these records have used today's searches: the job waits and goes "
                           "on at ${time}.", time=w["quota"]))
        elif w.get("state") == "matching":
            rec = w.get("record") or {}
            line = t("● Job ${job}, round ${round}: record ${n} of ${total}: ${title}", job=w.get("job", "?"),
                     round=w.get("round", 1), n=min(int(w.get("done") or 0) + 1, int(w.get("total") or 1)),
                     total=w.get("total", 0), title=rec.get("title", ""))
            speed = speed_text(w)
            label.update(f"{line} · {speed}" if speed else line)
            bar.update(total=max(int(w.get("total") or 0), 1), progress=int(w.get("done") or 0))
        else:
            label.update(t("○ Idle: the service starts when you search and stops after 5 idle minutes."))
            bar.update(total=1, progress=1 if self.jobs else 0)
        servers = w.get("servers") or {}
        seen = (servers, w.get("capped"), w.get("cooling"))
        if not servers or seen == self.servers_seen:
            return                       # idle: the last search's servers stay on screen
        self.servers_seen = seen
        table = self.query_one("#od-servers", DataTable)
        table.clear()
        for tid, s in servers.items():
            ms = int(s.get("ms") or 0)
            table.add_row(s.get("name", tid), s.get("country", ""), server_state(s.get("state", "")),
                          str(ms) if ms else "–", key=tid)
        # The servers passed over for this record are not in the list: say how many and why.
        if w.get("capped"):
            table.add_row(t("${n} other server(s)", n=w["capped"]), "", t("today's limit reached"), "–",
                          key="_capped")
        if w.get("cooling"):
            table.add_row(t("${n} other server(s)", n=w["cooling"]), "", t("cooling down after errors"), "–",
                          key="_cooling")

    def draw_job(self, redraw_changes: bool = True) -> None:
        super().draw_job(redraw_changes)
        job = self.job
        state = job.get("state", "")
        self.query_one("#od-more", Button).disabled = state not in ("ready", "failed")
        self.query_one("#od-donor", Button).disabled = not (state == "ready" and any(job.get("donors", {}).values()))
        if not redraw_changes:
            return
        table = self.query_one("#od-found", DataTable)
        table.clear()
        rows = 0
        for q in job.get("found", []):
            for i, f in enumerate(q.get("found", []), 1):
                bn = f.get("imported")
                table.add_row(f.get("source", ""), f.get("title", ""), f.get("isbn", ""),
                              t("Yes (biblionumber ${bn})", bn=bn) if bn else "", key=f"{q.get('seq', 1)}:{i}")
                rows += 1
        self.query_one("#od-found-note", Static).update(
            t("Records found for this book (the best of each server):") if rows else "")
        self.query_one("#od-import", Button).disabled = rows == 0 or state != "ready"

    # -- events --------------------------------------------------------------
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "e-changes" and event.row_key is not None:
            self.picked_bn = (event.row_key.value or "").split(":")[0]
            return
        super().on_data_table_row_highlighted(event)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        work = {"od-find": self._find, "od-more": self._more, "od-donor": self._donor, "od-import": self._import}
        if bid in work:
            event.stop()
            self.app.run_worker(work[bid](), group="routine", exclusive=True, exit_on_error=False)
            return
        super().on_button_pressed(event)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("od-isbn", "od-title", "od-author", "od-year"):
            event.stop()
            self.app.run_worker(self._find(), group="routine", exclusive=True, exit_on_error=False)
            return
        super().on_input_submitted(event)

    # -- actions -------------------------------------------------------------
    def query_args(self) -> list[str] | str:
        """The typed book as enrich-od-add arguments, or why it cannot be searched."""
        values = {k: self.query_one(f"#od-{k}", Input).value.strip() for k in ("isbn", "title", "author", "year")}
        if not values["isbn"] and not values["title"]:
            return t("Type an ISBN or a title.")
        if values["year"] and not YEAR.match(values["year"]):
            return t("The year has four digits, such as 1995.")
        args: list[str] = []
        for k, v in values.items():
            if v:
                args += [f"--{k}", v]
        return args

    async def _queued(self, title: str, task: str, *args: str) -> None:
        from ..routines.common import failed, run_task, show_failure
        result = await run_task(self.app, title, task, *args)
        if failed(result):
            await show_failure(self.app, title, result)
            return
        job = result.value.get("job", "")
        if job.isdigit():
            self.job_id, self.job = int(job), {}
            self.app.notify(t("Job ${id}: the servers are being asked now.", id=job), timeout=5)
        self.reload()

    async def _start(self) -> None:
        scope = self.query_one("#e-scope", Input).value.strip() or self.DEFAULT_SCOPE
        problem = self.scope_problem(scope)
        if problem:
            self.app.notify(problem, severity="warning", timeout=6)
            return
        await self._queued(self.start_title(), "enrich-od-add", scope)

    async def _find(self) -> None:
        args = self.query_args()
        if isinstance(args, str):
            self.app.notify(args, severity="warning", timeout=6)
            return
        await self._queued(self.start_title(), "enrich-od-add", *args)

    async def _more(self) -> None:
        if self.job_id is None:
            return
        await self._queued(t("Search more servers"), "enrich-od-more", str(self.job_id))

    async def _donor(self) -> None:
        from ..routines.common import failed, run_task, show_failure
        job_id, donors = self.job_id, self.job.get("donors") or {}
        bn = self.picked_bn if self.picked_bn in donors else next((b for b, c in donors.items() if c), "")
        if job_id is None or not bn:
            return
        title = t("Choose donor")
        chosen = (self.job.get("choices") or {}).get(bn, {})
        group = await self.app.push_screen_wait(ChoiceScreen(
            title, t("Record ${bn}: which fields should come from a server you choose?", bn=bn),
            [(g, group_label(g) + (f"  ← {chosen[g]}" if g in chosen else "")) for g in GROUPS]))
        if not group:
            return
        options = [("auto", t("Automatic (the best match first)"))] + [
            (c["source"], f"{c['source']}  ·  {c.get('cls', '')} {c.get('score', '')}") for c in donors[bn]]
        source = await self.app.push_screen_wait(ChoiceScreen(
            title, t("${group}: from which server?", group=group_label(group)), options,
            default=chosen.get(group, "auto")))
        if not source:
            return
        args = [str(job_id), bn, group] + ([] if source == "auto" else [source])
        result = await run_task(self.app, title, "enrich-od-donor", *args)
        if failed(result):
            await show_failure(self.app, title, result)
            return
        self.app.notify(t("Record ${bn} is being merged again with that choice (no server is asked).", bn=bn),
                        timeout=5)
        self.job = {}
        self.reload()

    async def _import(self) -> None:
        from ..routines.common import run_task, show_done
        table = self.query_one("#od-found", DataTable)
        if self.job_id is None or not table.row_count:
            return
        key = table.coordinate_to_cell_key((max(table.cursor_row, 0), 0)).row_key.value or ""
        seq, _, n = key.partition(":")
        row = table.get_row(key)
        title = t("Import as new record")
        if not await self.app.push_screen_wait(ConfirmScreen(title, t(
                "Add \"${title}\" (from ${source}) to the catalogue as a new record? If Koha already has a record "
                "with this ISBN, nothing is added. Library tools > Undo a MARC import takes it out again.",
                title=row[1], source=row[0]))):
            return
        result = await run_task(self.app, title, "enrich-od-import", str(self.job_id), seq, n, cancellable=False)
        await show_done(self.app, title, result)
        self.job = {}
        self.reload()
