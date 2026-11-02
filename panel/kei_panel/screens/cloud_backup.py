"""CloudBackupScreen: the automatic cloud backup, all of it in one screen,
laid out like the manual backup and MARC21 export screens: the work on the
left (in tabs), what is true now on the right.

  ╭ ☁ Automatic cloud backup ───────────────── ✅ On: 2 cloud backups ──╮
  │ [🔌 Connections] [☁ Cloud backups] [📂 In the cloud] [📜 History]      │
  │ ┌ cloud backups ──────────────────────────┐  ╭ Where the backups go ╮ │
  │ │ ✅ gdrive   gdrive:     SQL+MARC21 daily │  │ gdrive → gdrive:     │ │
  │ │ ✅ wasabi-w wasabi:koha SQL  Sun 02:00   │  │ wasabi-w → wasabi:.. │ │
  │ └─────────────────────────────────────────┘  ├ Status ──────────────┤ │
  │ [➕ New cloud backup] [✏ Edit] [▶ Run now]    │ last upload, result  │ │
  │ ╭ Backups on this server ─────────────────╮  ├ Space in the cloud ──┤ │
  │ │ SQL [■] daily 23:00   MARC21 [■] Sun 03 │  │ used / free ▓▓▓░░░   │ │
  │ │ days kept here, upload speed limit       │  ├ rclone ──────────────┤ │
  │ ╰─────────────────────────────────────────╯  ╰──────────────────────╯ │
  │                                                              [Close]  │
  ╰───────────────────────────────────────────────────────────────────────╯

A cloud backup is a connection, a folder in it, what it sends (SQL,
MARC21 or both), its own schedule and how long the copies stay in the
cloud; there can be several, each to another service or account. The
installer keeps them in cloud_plans.conf and runs each from its own cron
line (/root/cloud_plan.sh ID WHAT), which is also its row in Schedules &
cron tasks: either screen changes the same line.

Everything rclone does runs in the installer (`config.sh --task cloud-*`,
as root, with root's rclone.conf: the file the nightly scripts read), so
the screen works the same on WSL, on a Linux desktop and over SSH. Only
`rclone config providers` (the catalog of services, no rclone.conf) and
the browser sign-in (cloud.Authorizer) run here. The screen closes with
("restore", path) when a backup fetched from the cloud should be restored:
the routine (routines/backup.cloud_backup) then opens Restore database.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (Button, DataTable, Input, Label, ProgressBar, Select, Static, Switch, TabbedContent,
                             TabPane, Tree)

from .. import cloud, cron, transfer
from ..i18n import t
from ..widgets.copy import CopyButton
from .dialogs import ConfirmScreen, MessageScreen


class _Reporter:
    """bridge.task's reporter: the busy line of the screen."""

    cancelled = False

    def __init__(self, screen: "CloudBackupScreen"):
        self._screen = screen

    def log(self, line: str) -> None:
        self._screen.busy_text(line)

    status = notice = log

    def cancellable(self, on: bool) -> None:
        pass

    def progress(self, current: float, total: float) -> None:
        self._screen.query_one("#cb-bar", ProgressBar).update(total=total or None, progress=current)


def _when(job: cron.Job | None) -> str:
    if job is None:
        return t("Not scheduled")
    if not job.enabled:
        return t("Off")
    if job.freq == "daily":
        return t("Daily at ${time}", time=job.time())
    if job.freq == "weekly":
        return t("Weekly, ${day} at ${time}", day=t(cron.WEEKDAYS[job.day % 7]), time=job.time())
    if job.freq == "monthly":
        return t("Monthly, day ${day} at ${time}", day=job.day, time=job.time())
    return job.raw


class CloudBackupScreen(ModalScreen[tuple | None]):
    BINDINGS = [Binding("escape", "close", t("Close"))]

    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self.status: dict[str, str] = {}
        self.history: list[cloud.History] = []
        self.remotes: list[cloud.Remote] = []
        self.catalog: list[cloud.Backend] = []
        self.files: list[cloud.Entry] = []
        self.plans: list[cloud.Plan] = []
        self.cron = cron.defaults(self._instance())
        self._busy = False
        self._tree_for = ""

    def _instance(self) -> str:
        try:
            return self.app.env.instance
        except Exception:  # noqa: BLE001 - before the app is known (tests)
            return "library"

    # --- layout -----------------------------------------------------------
    @staticmethod
    def _row(key: str, value_id: str, value: str = "") -> Horizontal:
        return Horizontal(Label(key, classes="sb-key", markup=False),
                          Static(value, id=value_id, classes="sb-val", markup=False), classes="sb-row")

    @staticmethod
    def _card(title: str, card_id: str, *classes: str) -> Vertical:
        card = Vertical(classes=" ".join(("sb-card",) + classes), id=card_id)
        card.border_title = title
        return card

    def _schedule_rows(self, key: str) -> ComposeResult:
        with Horizontal(classes="cb-plan-row"):
            yield Switch(value=True, id=f"cb-{key}-on")
            yield Label(t("Scheduled"), classes="cb-switch-label", markup=False)
            yield Select([(t(cron.FREQS[f]), f) for f in ("daily", "weekly", "monthly")], value="daily",
                         allow_blank=False, id=f"cb-{key}-freq", classes="cb-freq")
            yield Select([(t(d), i) for i, d in enumerate(cron.WEEKDAYS)], value=0, allow_blank=False,
                         id=f"cb-{key}-day", classes="cb-day")
            yield Input("23:00", id=f"cb-{key}-time", classes="cb-time", max_length=5)

    def compose(self) -> ComposeResult:
        with Vertical(id="cb-box"):
            with Horizontal(id="sb-head"):
                yield Label(t("☁ Automatic cloud backup"), classes="dialog-title", id="cb-title", markup=False)
                yield Static("", id="cb-pill")
            with Horizontal(id="cb-body"):
                with TabbedContent(id="cb-tabs"):
                    with TabPane(t("🔌 Connections"), id="cb-tab-conn"):
                        yield Static(t("The clouds rclone can send to. ⭐ marks the ones a cloud backup "
                                       "sends to; any service rclone supports can be added."), classes="sb-hint",
                                     markup=False)
                        yield DataTable(id="cb-remotes", cursor_type="row", zebra_stripes=True)
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("➕ New connection"), id="cb-new", variant="success")
                            yield Button(t("✏ Edit"), id="cb-edit")
                            yield Button(t("🧪 Test"), id="cb-test")
                            yield Button(t("🗑 Remove"), id="cb-remove", variant="error")
                        yield Label(t("Folder in the cloud where the backup folders go (empty = the top):"),
                                    classes="sb-prompt", markup=False)
                        yield Input(id="cb-base", placeholder=t("for example: koha/my-library"))
                        yield Static("", id="cb-base-dest", classes="sb-hint", markup=False)
                        yield Tree(t("Choose a connection above"), id="cb-tree")
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("☁ Back up to this connection"), id="cb-use", variant="primary")
                            yield Button(t("🔄 Reload folders"), id="cb-tree-reload")
                    with TabPane(t("☁ Cloud backups"), id="cb-tab-plan"):
                        with VerticalScroll():
                            yield Static(t("Each cloud backup sends to one connection on its own schedule. Make "
                                           "as many as you want, to other services or accounts (3-2-1 rule). "
                                           "Each is also a row in Schedules & cron tasks."), classes="sb-hint",
                                         markup=False)
                            yield DataTable(id="cb-plans", cursor_type="row", zebra_stripes=True)
                            with Horizontal(classes="sb-card-buttons"):
                                yield Button(t("➕ New cloud backup"), id="cb-plan-new", variant="success")
                                yield Button(t("✏ Edit"), id="cb-plan-edit")
                                yield Button(t("▶ Run now"), id="cb-plan-run")
                                yield Button(t("🗑 Remove"), id="cb-plan-rm", variant="error")
                            with self._card(t("Backups on this server"), "cb-plan-local"):
                                yield Static(t("What the cloud backups send: made here first, checked, and kept "
                                               "here for some days."), classes="sb-hint", markup=False)
                                yield Label(t("Database backup (SQL)"), classes="cr-label", markup=False)
                                yield from self._schedule_rows("sql")
                                yield Label(t("MARC21 package"), classes="cr-label", markup=False)
                                yield from self._schedule_rows("marc")
                                with Horizontal(classes="cb-plan-row"):
                                    yield Label(t("Days kept on this server:"), classes="cb-plan-key", markup=False)
                                    yield Input("7", id="cb-keep-local", classes="cb-time", max_length=4)
                                with Horizontal(classes="cb-plan-row"):
                                    yield Label(t("Upload speed limit:"), classes="cb-plan-key", markup=False)
                                    yield Input("", id="cb-bw", placeholder=t("no limit"))
                                yield Static(t("Leave empty for no limit. 2M = 2 MB/s; 512k; or by the clock: "
                                               "08:00,1M 19:00,off (slow during the day, free at night)."),
                                             classes="sb-hint", markup=False)
                                with Horizontal(classes="sb-card-buttons"):
                                    yield Button(t("💾 Save"), id="cb-save-plan", variant="primary")
                    with TabPane(t("📂 In the cloud"), id="cb-tab-files"):
                        with Horizontal(classes="cb-plan-row"):
                            yield Select([], prompt=t("Cloud backup"), id="cb-files-plan", classes="cb-freq")
                            yield Select([(t("Database backups (SQL)"), "sql"), (t("MARC21 packages"), "marc")],
                                         value="sql", allow_blank=False, id="cb-which", classes="cb-freq")
                            yield Button(t("🔄 Refresh"), id="cb-files-reload")
                        yield DataTable(id="cb-files", cursor_type="row", zebra_stripes=True)
                        yield Static("", id="cb-files-sum", classes="sb-hint", markup=False)
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("📥 Download to this server"), id="cb-get")
                            yield Button(t("♻ Restore this backup"), id="cb-restore", variant="warning")
                            yield Button(t("🗑 Delete from the cloud"), id="cb-rm", variant="error")
                    with TabPane(t("📜 History"), id="cb-tab-hist"):
                        yield Static(t("What the last backups did, from the backup logs."), classes="sb-hint",
                                     markup=False)
                        yield DataTable(id="cb-history", cursor_type="row", zebra_stripes=True)
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("☁ Run every cloud backup now"), id="cb-send-now", variant="success")
                            yield Button(t("🔄 Refresh"), id="cb-hist-reload")
                with VerticalScroll(id="cb-side"):
                    with self._card(t("Where the backups go"), "cb-where", "-download"):
                        yield Static("", id="cb-w-list", markup=False)
                        with Horizontal(classes="sb-card-buttons"):
                            yield CopyButton(id="cb-copy-dest")
                    with self._card(t("Status"), "cb-state"):
                        yield self._row(t("Last upload"), "cb-s-last")
                        yield self._row(t("Result"), "cb-s-result")
                        yield self._row(t("Kept here"), "cb-s-keep")
                        yield self._row(t("Speed limit"), "cb-s-bw")
                    with self._card(t("Space in the cloud"), "cb-space"):
                        yield self._row(t("Used"), "cb-a-used")
                        yield self._row(t("Free"), "cb-a-free")
                        yield ProgressBar(total=100, show_eta=False, id="cb-a-bar")
                        yield Static("", id="cb-a-note", classes="sb-hint", markup=False)
                    with self._card("rclone", "cb-rclone"):
                        yield self._row(t("Version"), "cb-r-version")
                        yield self._row(t("Services"), "cb-r-backends")
                        yield Static("", id="cb-r-note", classes="sb-hint", markup=False)
                        with Horizontal(classes="sb-card-buttons", id="cb-r-buttons"):
                            yield Button(t("⬆ Install the official rclone"), id="cb-official")
                    with self._card(t("Good to know"), "cb-tips"):
                        yield Static(self._tips(), classes="sb-hint", markup=False)
            with Horizontal(id="cb-busy"):
                yield Label("", id="cb-busy-text", markup=False)
                yield ProgressBar(total=None, show_eta=False, id="cb-bar")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Close"), id="cb-close", variant="primary")

    def _tips(self) -> str:
        where = transfer.where()
        lines = [t("• Keep the 3-2-1 rule: 3 copies, on 2 kinds of storage, 1 away from the library. "
                   "This server and two cloud backups to different services do that."),
                 t("• The backups go up from this server at night, even with this panel closed."),
                 t("• Test the connection after changing a password or plan of the service.")]
        if where in ("ssh", "server"):
            lines.append(t("• Over SSH, a sign-in in the browser gives you a link to open on your own "
                           "computer; the address it ends on is pasted back here."))
        return "\n".join(lines)

    def on_mount(self) -> None:
        self.query_one("#cb-remotes", DataTable).add_columns(" ", t("Name"), t("Service"), t("Use"))
        self.query_one("#cb-files", DataTable).add_columns(t("File"), t("Size"), t("Date"))
        self.query_one("#cb-history", DataTable).add_columns(t("When"), t("Backup"), t("What happened"))
        self.query_one("#cb-plans", DataTable).add_columns(" ", t("Name"), t("Where"), t("Sends"), t("When"),
                                                           t("Kept in the cloud"))
        self.query_one("#cb-busy").display = False
        self.query_one("#cb-r-buttons").display = False
        self._load_cron()
        self._start()

    # --- running the installer's tasks ---------------------------------------
    def busy_text(self, text: str) -> None:
        self.query_one("#cb-busy-text", Label).update(text)

    def _set_busy(self, text: str | None) -> None:
        self._busy = text is not None
        self.query_one("#cb-busy").display = self._busy
        if text is not None:
            self.busy_text(text)
            self.query_one("#cb-bar", ProgressBar).update(total=None, progress=0)

    async def task(self, label: str, name: str, *args: str, quiet: bool = False):
        """One `--task cloud-*`; its error box (if any) is shown unless quiet."""
        self._set_busy(label)
        try:
            out = await self.app.bridge.task(name, *args, reporter=_Reporter(self))
        except Exception as e:  # noqa: BLE001 - shown, the screen stays usable
            self._set_busy(None)
            if not quiet:
                await self._say(t("Error"), f"{type(e).__name__}: {e}", "error")
            return None
        self._set_busy(None)
        if not out.ok and not quiet:
            msg = out.last("error")
            await self._say(msg[1] if msg and msg[1] else label, msg[2] if msg else f"exit {out.rc}", "error")
        return out

    async def _say(self, title: str, body: str, kind: str = "ok", details=None) -> None:
        await self.app.push_screen_wait(MessageScreen(title, body.replace("\\n", "\n"), kind=kind,
                                                      details=details))

    def _guard(self) -> bool:
        if self._busy:
            self.app.notify(t("Wait: the cloud is still answering."), severity="warning")
            return False
        return True

    # --- loading ---------------------------------------------------------------
    @work(exclusive=True, group="cb-load", exit_on_error=False)
    async def _start(self) -> None:
        if not self.app.env.demo and (self.info.get("rclone") or "no") != "yes":
            await self.task(t("Installing rclone"), "cloud-prepare")
        if self.app.env.demo:
            self.catalog = cloud.demo_catalog()
        else:
            self._set_busy(t("Reading the services rclone supports..."))
            self.catalog = await cloud.load_catalog() or cloud.demo_catalog()
            self._set_busy(None)
        await self.refresh_all()

    async def refresh_all(self) -> None:
        status = await self.task(t("Reading the cloud settings..."), "cloud-status", quiet=True)
        if status is not None:
            self.status = dict(status.results)
            self.history = cloud.parse_history(status.lists.get("history", []))
            self.plans = cloud.parse_plans(status.lists.get("plan", []))
        self._load_cron()
        listed = await self.task(t("Reading the connections..."), "cloud-list", quiet=True)
        if listed is not None:
            self.remotes = cloud.parse_remotes(listed.lists.get("remote", []))
        self._draw_remotes()
        self._draw_plans()
        self._draw_plan()
        self._draw_side()
        self._draw_history()
        self._draw_files_plans()
        if self.plans:
            self.query_one("#cb-base", Input).value = self.plans[0].base
            self._about(self.plans[0].remote)
            self._load_files()

    def _remote(self, name: str) -> cloud.Remote | None:
        return next((r for r in self.remotes if r.name == name), None)

    def _service(self, remote: cloud.Remote | None) -> str:
        if remote is None:
            return "—"
        if remote.encrypted:
            return t("🔒 encrypted layer")
        backend = cloud.find_backend(self.catalog, remote.kind)
        return t(backend.label) if backend else remote.kind

    def selected(self) -> cloud.Remote | None:
        table = self.query_one("#cb-remotes", DataTable)
        if not self.remotes or table.cursor_row is None or table.cursor_row >= len(self.remotes):
            return None
        return self.remotes[table.cursor_row]

    # --- drawing -----------------------------------------------------------------
    def _draw_remotes(self) -> None:
        table = self.query_one("#cb-remotes", DataTable)
        keep = table.cursor_row or 0
        table.clear()
        for r in self.remotes:
            uses = [p.id for p in self.plans if p.remote == r.name]
            service = self._service(r)
            table.add_row("⭐" if uses else "", r.name,
                          service if len(service) <= 36 else service[:35] + "…", ", ".join(uses))
        if not self.remotes:
            table.add_row("", t("(none yet)"), t("Press ➕ New connection"), "")
        if self.remotes:
            table.move_cursor(row=min(keep, len(self.remotes) - 1))
        for b in ("#cb-edit", "#cb-test", "#cb-remove", "#cb-use"):
            self.query_one(b, Button).disabled = not self.remotes
        self._show_tree()

    def _plan_job(self, plan: cloud.Plan) -> cron.Job | None:
        return self.cron.job(cron.CLOUD_PREFIX + plan.id)

    def _sends(self, job: cron.Job | None) -> str:
        return cron.WHAT_LABELS[cron.cloud_what(job)] if job else "—"

    def _draw_side(self) -> None:
        s = self.status
        on = [p for p in self.plans if (j := self._plan_job(p)) is not None and j.enabled]
        pill = self.query_one("#cb-pill", Static)
        if on:
            pill.update(Text(" " + t("✅ On: ${n} cloud backup(s)", n=len(on)) + " ", style="bold reverse green"))
        else:
            pill.update(Text(" " + t("⚠ Off: no cloud backup scheduled") + " ", style="bold reverse yellow"))
        lines = []
        for p in self.plans:
            job = self._plan_job(p)
            remote = self._remote(p.remote)
            lock = " 🔒" if remote and remote.encrypted else ""
            mark = "✅" if job and job.enabled else "⏸"
            lines.append(f"{mark} {p.id} → {p.where()}{lock}\n   {self._sends(job)} · {_when(job)}")
        self.query_one("#cb-w-list", Static).update("\n".join(lines) if lines else t(
            "No cloud backup yet: the backups stay only on this server. Make one in ☁ Cloud backups."))
        last = cloud.last_cloud(self.history)
        self.query_one("#cb-s-last", Static).update(last.when if last else t("never"))
        if last is None:
            result = t("No upload yet") if self.plans else "—"
        else:
            result = t("✅ Sent") if last.ok else "⚠ " + last.text[:120]
        if s.get("running") == "yes":
            result = t("⏳ A backup is running now")
        self.query_one("#cb-s-result", Static).update(result)
        self.query_one("#cb-s-keep", Static).update(t("${n} days", n=s.get("keep_days", "7")))
        self.query_one("#cb-s-bw", Static).update(s.get("bwlimit") or t("no limit"))
        version = s.get("rclone", "")
        self.query_one("#cb-r-version", Static).update(
            f"{version} ({t('Debian package') if s.get('rclone_source') == 'debian' else t('official')})"
            if version else t("not installed"))
        self.query_one("#cb-r-backends", Static).update(s.get("rclone_backends") or str(len(self.catalog)))
        debian = s.get("rclone_source") == "debian" or not version
        self.query_one("#cb-r-buttons").display = debian
        self.query_one("#cb-r-note", Static).update(
            t("Debian's rclone leaves some services out (MEGA, Proton Drive, Storj and others) and is older. "
              "The official build from rclone.org has all of them.") if debian
            else t("The official rclone: every service it supports is in the list."))

    def _draw_history(self) -> None:
        table = self.query_one("#cb-history", DataTable)
        table.clear()
        for h in sorted(self.history, key=lambda h: h.when, reverse=True):
            mark = "✅" if h.ok else "⚠"
            table.add_row(h.when, "SQL" if h.which == "sql" else "MARC21", f"{mark} {h.text}")
        if not self.history:
            table.add_row("—", "", t("No backup has run yet."))

    # --- the cloud folder tree ---------------------------------------------------
    def _show_tree(self) -> None:
        remote = self.selected()
        name = remote.name if remote else ""
        if name == self._tree_for:
            self._dest_hint()
            return
        self._tree_for = name
        tree = self.query_one("#cb-tree", Tree)
        tree.clear()
        tree.root.label = f"☁ {name}:" if name else t("Choose a connection above")
        tree.root.data = ""
        tree.root.allow_expand = bool(name)
        tree.root.collapse()
        self._dest_hint()

    def _dest_hint(self) -> None:
        remote = self.selected()
        base = self.query_one("#cb-base", Input).value
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
            text = t("The backups will go to ${sql}/ and ${marc}/", sql=f"{remote.name}:{sql}",
                     marc=f"{remote.name}:{marc}")
        self.query_one("#cb-base-dest", Static).update(text)

    @on(DataTable.RowHighlighted, "#cb-remotes")
    def _remote_moved(self) -> None:
        self._show_tree()

    @on(Input.Changed, "#cb-base")
    def _base_changed(self) -> None:
        self._dest_hint()

    @on(Tree.NodeExpanded, "#cb-tree")
    def _expand(self, event: Tree.NodeExpanded) -> None:
        node = event.node
        if self._tree_for and not getattr(node, "_kei_loaded", False):
            node._kei_loaded = True
            self._load_folder(node)

    @work(group="cb-tree", exit_on_error=False)
    async def _load_folder(self, node) -> None:
        path = node.data or ""
        out = await self.task(t("Listing ${where}...", where=f"{self._tree_for}:{path}"), "cloud-ls",
                              f"{self._tree_for}:{path}", "dirs")
        if out is None or not out.ok:
            node._kei_loaded = False
            return
        dirs = [e for e in cloud.parse_entries(out.lists.get("entry", [])) if e.is_dir]
        for e in sorted(dirs, key=lambda e: e.name.lower()):
            child = node.add(f"📁 {e.name}", data=f"{path}/{e.name}".strip("/"), allow_expand=True)
            child._kei_loaded = False
        if not dirs:
            node.add_leaf(t("(no folders)"), data=None)

    @on(Tree.NodeSelected, "#cb-tree")
    def _folder_picked(self, event: Tree.NodeSelected) -> None:
        if event.node.data is not None:
            base = event.node.data
            # Choosing a backup folder itself means the folder above it.
            for leaf in (cloud.SQL_DIR, cloud.MARC_DIR):
                if base == leaf or base.endswith("/" + leaf):
                    base = base[: -len(leaf)].rstrip("/")
            self.query_one("#cb-base", Input).value = base

    @on(Button.Pressed, "#cb-tree-reload")
    def _tree_reload(self) -> None:
        self._tree_for = ""
        self._show_tree()

    # --- connections -------------------------------------------------------------
    @on(Button.Pressed, "#cb-new")
    def _new(self) -> None:
        if self._guard():
            self._edit(None)

    @on(Button.Pressed, "#cb-edit")
    def _edit_pressed(self) -> None:
        remote = self.selected()
        if remote and self._guard():
            if remote.encrypted:
                self.app.notify(t("The encrypted layer has no settings of its own: edit the connection under it."),
                                severity="warning")
                return
            self._edit(remote)

    @work(exclusive=True, group="cb-edit", exit_on_error=False)
    async def _edit(self, remote: cloud.Remote | None) -> None:
        from .cloud_remote import RemoteFormScreen
        current, secrets = {}, set()
        if remote is not None:
            shown = await self.task(t("Reading the connection..."), "cloud-show", remote.name)
            if shown is None or not shown.ok:
                return
            for line in shown.lists.get("opt", []):
                key, _, value = line.partition("\t")
                if key and key != "type":
                    current[key] = value
            secrets = set(shown.lists.get("secret", []))
        names = [r.name for r in self.remotes]
        has_crypt = remote is not None and (remote.name + cloud.CRYPT_SUFFIX) in names
        answers = await self.app.push_screen_wait(RemoteFormScreen(
            self.catalog, names, remote=remote, current=current, secrets=secrets, has_crypt=has_crypt))
        if not answers:
            return
        try:
            path = cloud.save_file(answers["name"], answers["prefix"], answers["mode"], answers["values"],
                                   answers.get("crypt", ""), crypt_dir=answers.get("crypt_dir", ""))
        except ValueError:
            await self._say(t("☁ Automatic cloud backup"), t("An answer has a tab or a line break. Type it again."),
                            "error")
            return
        try:
            out = await self.task(t("Saving the connection in rclone..."), "cloud-save", str(path))
        finally:
            path.unlink(missing_ok=True)
        if out is None or not out.ok:
            return
        target = out.get("remote") or answers["name"]
        await self.refresh_all()
        self._select(target)
        tested = await self._test(target)
        if tested and not any(p.remote == target for p in self.plans):
            if await self.app.push_screen_wait(ConfirmScreen(
                    t("☁ Automatic cloud backup"),
                    t("The connection works. Make a cloud backup to ${name} now?", name=target))):
                base = self.query_one("#cb-base", Input).value
                await self._plan_edit_run(None, remote=target, base="" if cloud.base_problem(base) else base)

    def _select(self, name: str) -> None:
        for i, r in enumerate(self.remotes):
            if r.name == name:
                self.query_one("#cb-remotes", DataTable).move_cursor(row=i)

    @on(Button.Pressed, "#cb-test")
    def _test_pressed(self) -> None:
        remote = self.selected()
        if remote and self._guard():
            self.run_worker(self._test(remote.name), group="cb-test", exclusive=True, exit_on_error=False)

    async def _test(self, name: str, base: str | None = None) -> bool:
        if base is None:
            base = self.query_one("#cb-base", Input).value
        if cloud.base_problem(base):
            base = ""
        remote = self._remote(name)
        if remote and cloud.needs_bucket(remote.kind) and not cloud.clean_base(base):
            await self._say(t("🧪 Test of ${name}", name=name), t(
                "Type the name of the bucket in the folder box first."), "error")
            return False
        out = await self.task(t("Testing ${name}: sending a test file...", name=name), "cloud-test", name,
                              cloud.clean_base(base))
        if out is None or not out.ok:
            return False
        secs = out.get("seconds")
        msg = out.last("ok")
        await self._say(t("🧪 Test of ${name}", name=name), msg[2] if msg else t("✅ The cloud answered."),
                        "ok", details=[(t("Time"), f"{secs} s")] if secs else None)
        self._about(name)
        return True

    @on(Button.Pressed, "#cb-use")
    def _use_pressed(self) -> None:
        remote = self.selected()
        if remote is None or not self._guard():
            return
        base = self.query_one("#cb-base", Input).value
        if cloud.base_problem(base):
            base = ""
        self._plan_edit(None, remote=remote.name, base=base)

    @on(Button.Pressed, "#cb-remove")
    def _remove_pressed(self) -> None:
        remote = self.selected()
        if remote and self._guard():
            self.run_worker(self._remove(remote), group="cb-remove", exclusive=True, exit_on_error=False)

    async def _remove(self, remote: cloud.Remote) -> None:
        warn = ""
        uses = [p.id for p in self.plans if p.remote == remote.name]
        if uses:
            warn = "\n\n" + t("⚠ These cloud backups send to it and are removed with it: ${names}",
                              names=", ".join(uses))
        if not await self.app.push_screen_wait(ConfirmScreen(
                t("🗑 Remove"), t("Remove the connection ${name}? The files already in the cloud are kept.",
                                  name=remote.name) + warn, danger=True)):
            return
        out = await self.task(t("Removing ${name}...", name=remote.name), "cloud-delete", remote.name)
        if out is not None and out.ok:
            self.app.notify(t("Connection removed: ${name}", name=remote.name), timeout=5)
            self._tree_for = "?"
            await self.refresh_all()

    # --- space in the cloud --------------------------------------------------------
    @work(exclusive=True, group="cb-about", exit_on_error=False)
    async def _about(self, name: str) -> None:
        out = await self.app.bridge.task("cloud-about", name)
        used, free, total = (out.get(k) for k in ("used", "free", "total"))
        human = transfer.human_size
        self.query_one("#cb-space").border_title = t("Space in the cloud") + f" · {name}"
        if out.get("about") == "none" or not (used or free):
            self.query_one("#cb-a-used", Static).update("—")
            self.query_one("#cb-a-free", Static).update("—")
            self.query_one("#cb-a-bar").display = False
            self.query_one("#cb-a-note", Static).update(t("This service does not tell its free space."))
            return
        u, f = int(used or 0), int(free or 0)
        whole = int(total or 0) or (u + f)
        self.query_one("#cb-a-used", Static).update(human(u))
        self.query_one("#cb-a-free", Static).update(human(f) + (f" / {human(whole)}" if whole else ""))
        bar = self.query_one("#cb-a-bar", ProgressBar)
        bar.display = bool(whole)
        if whole:
            bar.update(total=100, progress=round(100 * u / whole))
        newest = self._newest_size()
        note = ""
        if newest and f:
            note = t("Room for about ${n} more backups of ${size}.", n=f // newest, size=human(newest))
            if f < newest * 3:
                note = t("⚠ Almost full: fewer than 3 backups fit. Keep fewer days or get more space.")
        self.query_one("#cb-a-note", Static).update(note)

    def _newest_size(self) -> int:
        sql = [e for e in self.files if not e.is_dir]
        return max(sql, key=lambda e: e.modified).size if sql else 0

    # --- the cloud backups ----------------------------------------------------------------
    def _load_cron(self) -> None:
        text = "" if self.app.env.demo else cron.read()
        self.cron = cron.parse(text, self._instance()) if text else cron.defaults(self._instance())
        if self.app.env.demo:
            # The demo has no cron file: its cloud backups get a schedule here.
            for i, p in enumerate(self.plans):
                if self.cron.job(cron.CLOUD_PREFIX + p.id) is None:
                    job = cron.cloud_job(p.id, "sql+marc" if i == 0 else "sql", hour=23 if i == 0 else 2,
                                         minute=30 if i == 0 else 0)
                    if i:
                        job.freq, job.day = "weekly", 0
                    self.cron.jobs.append(job)

    def _draw_plans(self) -> None:
        table = self.query_one("#cb-plans", DataTable)
        keep = table.cursor_row or 0
        table.clear()
        for p in self.plans:
            job = self._plan_job(p)
            mark = "✅" if job and job.enabled else "⏸"
            table.add_row(mark, p.id, p.where(), self._sends(job), _when(job),
                          t("${n} days", n=p.keep) if p.keep else t("everything"))
        if not self.plans:
            table.add_row("", t("(none yet)"), t("Press ➕ New cloud backup"), "", "", "")
        else:
            table.move_cursor(row=min(keep, len(self.plans) - 1))
        for b in ("#cb-plan-edit", "#cb-plan-run", "#cb-plan-rm"):
            self.query_one(b, Button).disabled = not self.plans

    def selected_plan(self) -> cloud.Plan | None:
        table = self.query_one("#cb-plans", DataTable)
        if not self.plans or table.cursor_row is None or table.cursor_row >= len(self.plans):
            return None
        return self.plans[table.cursor_row]

    @on(Button.Pressed, "#cb-plan-new")
    def _plan_new(self) -> None:
        if self._guard():
            remote = self.selected()
            self._plan_edit(None, remote=remote.name if remote else "")

    @on(Button.Pressed, "#cb-plan-edit")
    def _plan_edit_pressed(self) -> None:
        plan = self.selected_plan()
        if plan and self._guard():
            self._plan_edit(plan)

    @work(exclusive=True, group="cb-plan-edit", exit_on_error=False)
    async def _plan_edit(self, plan: cloud.Plan | None, remote: str = "", base: str = "") -> None:
        await self._plan_edit_run(plan, remote, base)

    async def _plan_edit_run(self, plan: cloud.Plan | None, remote: str = "", base: str = "") -> None:
        from .cloud_plan import PlanFormScreen
        if not self.remotes:
            self.app.notify(t("Make a connection first: 🔌 Connections, ➕ New connection."), severity="warning")
            return
        services = {r.name: self._service(r) for r in self.remotes}
        answers = await self.app.push_screen_wait(PlanFormScreen(
            self.remotes, [p.id for p in self.plans], plan=plan, job=self._plan_job(plan) if plan else None,
            remote=remote, base=base, default_time=cron.after_backup(self.cron), services=services))
        if not answers:
            return
        await self._plan_save(answers)

    async def _plan_save(self, a: dict) -> None:
        out = await self.task(t("Saving the cloud backup..."), "cloud-plan-save", a["id"], a["remote"], a["base"],
                              str(a["keep"]), *((a["old_id"],) if a["old_id"] else ()))
        if out is None or not out.ok:
            return
        # The task may have taken the renamed backup's line out: read again.
        self._load_cron()
        cf = cron.parse(cron.render(self.cron), self._instance())
        cron.put_cloud_job(cf, a["job"], old_id=a["old_id"])
        text = cron.render(cf)
        if text != cron.render(self.cron):
            if not await self._apply_cron(text):
                return
        self.app.notify(t("Cloud backup ${name} saved.", name=a["id"]), timeout=6)
        new = not a["old_id"]
        await self.refresh_all()
        self._select_plan(a["id"])
        if new:
            await self._test(a["remote"], a["base"])

    async def _apply_cron(self, text: str) -> bool:
        problem = cron.file_problem(text)
        if problem:
            await self._say(t("☁ Automatic cloud backup"), t(problem), "error")
            return False
        path = cron.write_temp(text)
        try:
            out = await self.task(t("Saving the schedule..."), "cron-apply", str(path))
        finally:
            path.unlink(missing_ok=True)
        if out is None or not out.ok:
            return False
        self.cron = cron.parse(text, self._instance())
        return True

    def _select_plan(self, plan_id: str) -> None:
        for i, p in enumerate(self.plans):
            if p.id == plan_id:
                self.query_one("#cb-plans", DataTable).move_cursor(row=i)

    @on(Button.Pressed, "#cb-plan-rm")
    def _plan_rm_pressed(self) -> None:
        plan = self.selected_plan()
        if plan and self._guard():
            self.run_worker(self._plan_rm(plan), group="cb-plan-rm", exclusive=True, exit_on_error=False)

    async def _plan_rm(self, plan: cloud.Plan) -> None:
        if not await self.app.push_screen_wait(ConfirmScreen(
                t("🗑 Remove"), t("Remove the cloud backup ${name}? Its schedule goes too; the files already in "
                                  "the cloud are kept.", name=plan.id), danger=True)):
            return
        out = await self.task(t("Removing ${name}...", name=plan.id), "cloud-plan-delete", plan.id)
        if out is not None and out.ok:
            self.app.notify(t("Cloud backup removed: ${name}", name=plan.id), timeout=5)
            await self.refresh_all()

    @on(Button.Pressed, "#cb-plan-run")
    def _plan_run_pressed(self) -> None:
        plan = self.selected_plan()
        if plan and self._guard():
            self.run_worker(self._send_now([plan]), group="cb-send", exclusive=True, exit_on_error=False)

    # --- backups on this server ----------------------------------------------------------
    def _draw_plan(self) -> None:
        for key, preset in (("sql", "backup_sql"), ("marc", "backup_marc")):
            job = self.cron.job(preset) or cron.preset_job(cron.BY_KEY[preset], self._instance())
            self.query_one(f"#cb-{key}-on", Switch).value = job.enabled
            freq = job.freq if job.freq in ("daily", "weekly", "monthly") else "daily"
            self.query_one(f"#cb-{key}-freq", Select).value = freq
            self._day_options(key, freq, job.day)
            self.query_one(f"#cb-{key}-time", Input).value = job.time()
        s = self.status
        self.query_one("#cb-keep-local", Input).value = s.get("keep_days", "7")
        self.query_one("#cb-bw", Input).value = s.get("bwlimit", "")

    def _day_options(self, key: str, freq: str, day: int) -> None:
        sel = self.query_one(f"#cb-{key}-day", Select)
        if freq == "monthly":
            sel.set_options([(t("Day ${n}", n=n), n) for n in range(1, 29)])
            sel.value = min(max(day, 1), 28)
        else:
            sel.set_options([(t(d), i) for i, d in enumerate(cron.WEEKDAYS)])
            sel.value = day % 7
        sel.display = freq != "daily"

    @on(Select.Changed, "#cb-sql-freq")
    @on(Select.Changed, "#cb-marc-freq")
    def _freq_changed(self, event: Select.Changed) -> None:
        key = "sql" if event.select.id == "cb-sql-freq" else "marc"
        day = self.query_one(f"#cb-{key}-day", Select).value
        self._day_options(key, str(event.value), day if isinstance(day, int) else 0)

    def plan(self) -> tuple[dict[str, str], str, str]:
        """(backup.conf settings, new cron file, problem) from the local card."""
        values: dict[str, str] = {}
        local = self.query_one("#cb-keep-local", Input).value.strip()
        if cloud.keep_problem(local, low=1):
            return {}, "", t("Days on this server: type a number of days (1 or more).")
        values["KEEP_DAYS"] = str(int(local))
        bw = self.query_one("#cb-bw", Input).value.strip()
        if cloud.bwlimit_problem(bw):
            return {}, "", t("Upload speed limit: ${why}", why=t(cloud.bwlimit_problem(bw)))
        values["RCLONE_BWLIMIT"] = bw
        cf = cron.parse(cron.render(self.cron), self._instance())
        for key, preset in (("sql", "backup_sql"), ("marc", "backup_marc")):
            job = cf.job(preset)
            if job is None:
                job = cron.preset_job(cron.BY_KEY[preset], self._instance())
                cf.jobs.append(job)
            hm = cron.parse_time(self.query_one(f"#cb-{key}-time", Input).value)
            if hm is None:
                return {}, "", t("Type the time as HH:MM, for example 23:00.")
            job.enabled = self.query_one(f"#cb-{key}-on", Switch).value
            job.freq = str(self.query_one(f"#cb-{key}-freq", Select).value)
            day = self.query_one(f"#cb-{key}-day", Select).value
            job.day = day if isinstance(day, int) else 0
            job.hour, job.minute = hm
        text = cron.render(cf)
        problem = cron.file_problem(text)
        return values, text, t(problem) if problem else ""

    @on(Button.Pressed, "#cb-save-plan")
    def _save_plan_pressed(self) -> None:
        if not self._guard():
            return
        values, text, problem = self.plan()
        if problem:
            self.app.notify(problem, severity="error", timeout=8)
            return
        self.run_worker(self._save_plan(values, text), group="cb-plan", exclusive=True, exit_on_error=False)

    async def _save_plan(self, values: dict[str, str], text: str) -> None:
        if not self.query_one("#cb-sql-on", Switch).value and self.plans:
            if not await self.app.push_screen_wait(ConfirmScreen(
                    t("☁ Cloud backups"),
                    t("The nightly database backup is off: the cloud backups will make one each time they run. "
                      "Save anyway?"))):
                return
        path = cloud.settings_file(values)
        try:
            out = await self.task(t("Saving the cloud settings..."), "cloud-settings", str(path))
        finally:
            path.unlink(missing_ok=True)
        if out is None or not out.ok:
            return
        if text != cron.render(self.cron) and not await self._apply_cron(text):
            return
        self.app.notify(t("Saved. It applies from the next backup."), timeout=6)
        await self.refresh_all()

    # --- in the cloud -------------------------------------------------------------------
    def _draw_files_plans(self) -> None:
        sel = self.query_one("#cb-files-plan", Select)
        value = sel.value
        sel.set_options([(p.id, p.id) for p in self.plans])
        ids = [p.id for p in self.plans]
        if ids:
            sel.value = value if value in ids else ids[0]

    def _files_plan(self) -> cloud.Plan | None:
        value = self.query_one("#cb-files-plan", Select).value
        return next((p for p in self.plans if p.id == value), self.plans[0] if self.plans else None)

    def _files_where(self) -> tuple[str, str]:
        """(connection, folder) of the list in In the cloud."""
        plan = self._files_plan()
        if plan is None:
            return "", ""
        sql, marc = plan.folders()
        return plan.remote, marc if self.query_one("#cb-which", Select).value == "marc" else sql

    @on(Select.Changed, "#cb-which")
    @on(Select.Changed, "#cb-files-plan")
    @on(Button.Pressed, "#cb-files-reload")
    def _files_reload(self) -> None:
        if self.plans:
            self._load_files()

    @on(TabbedContent.TabActivated, "#cb-tabs")
    def _tab(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id == "cb-tab-files" and self.plans and not self.files:
            self._load_files()

    @work(exclusive=True, group="cb-files", exit_on_error=False)
    async def _load_files(self) -> None:
        remote, folder = self._files_where()
        table = self.query_one("#cb-files", DataTable)
        if not remote:
            return
        out = await self.task(t("Listing ${where}...", where=f"{remote}:{folder}"), "cloud-ls",
                              f"{remote}:{folder}", quiet=True)
        table.clear()
        if out is None or not out.ok:
            msg = out.last("error") if out else None
            self.query_one("#cb-files-sum", Static).update(
                (msg[2] if msg else t("The cloud did not list the folder.")).replace("\\n", " "))
            self.files = []
            return
        entries = [e for e in cloud.parse_entries(out.lists.get("entry", [])) if not e.is_dir]
        self.files = sorted(entries, key=lambda e: e.modified, reverse=True)
        for e in self.files:
            table.add_row(e.name, transfer.human_size(e.size), e.when)
        total = sum(e.size for e in self.files)
        self.query_one("#cb-files-sum", Static).update(
            t("${n} file(s), ${size} in ${where}", n=len(self.files), size=transfer.human_size(total),
              where=f"{remote}:{folder}/") if self.files else t("No backup in ${where} yet.",
                                                              where=f"{remote}:{folder}/"))

    def _picked_file(self) -> cloud.Entry | None:
        table = self.query_one("#cb-files", DataTable)
        if not self.files or table.cursor_row is None or table.cursor_row >= len(self.files):
            self.app.notify(t("Choose a file in the list first."), severity="warning")
            return None
        return self.files[table.cursor_row]

    @on(Button.Pressed, "#cb-get")
    def _get_pressed(self) -> None:
        entry = self._picked_file()
        if entry and self._guard():
            self.run_worker(self._get(entry, restore=False), group="cb-get", exclusive=True, exit_on_error=False)

    @on(Button.Pressed, "#cb-restore")
    def _restore_pressed(self) -> None:
        entry = self._picked_file()
        if entry is None or not self._guard():
            return
        if not entry.name.lower().endswith((".sql", ".sql.gz", ".sql.zst", ".sql.xz", ".sql.bz2")):
            self.app.notify(t("Only a database backup (.sql.gz, .sql.zst, .sql.xz) can be restored. A MARC21 "
                              "package is imported in Koha (Stage records for import)."), severity="warning",
                            timeout=8)
            return
        self.run_worker(self._get(entry, restore=True), group="cb-get", exclusive=True, exit_on_error=False)

    async def _get(self, entry: cloud.Entry, restore: bool) -> None:
        remote, folder = self._files_where()
        out = await self.task(t("Downloading ${file}...", file=entry.name), "cloud-get",
                              f"{remote}:{folder}/{entry.name}")
        if out is None or not out.ok:
            return
        file = out.get("file")
        if restore and file:
            self.dismiss(("restore", file))
            return
        await self._say(t("📥 Downloaded from the cloud"), t("The backup is on this server now."), "ok",
                        details=[(t("File:"), file), (t("Size:"), out.get("size") or transfer.human_size(entry.size))])

    @on(Button.Pressed, "#cb-rm")
    def _rm_pressed(self) -> None:
        entry = self._picked_file()
        if entry and self._guard():
            self.run_worker(self._rm(entry), group="cb-rm", exclusive=True, exit_on_error=False)

    async def _rm(self, entry: cloud.Entry) -> None:
        if not await self.app.push_screen_wait(ConfirmScreen(
                t("🗑 Delete from the cloud"),
                t("Delete ${file} from the cloud? This copy cannot be brought back.", file=entry.name),
                danger=True)):
            return
        remote, folder = self._files_where()
        out = await self.task(t("Deleting ${file}...", file=entry.name), "cloud-rm",
                              f"{remote}:{folder}/{entry.name}")
        if out is not None and out.ok:
            self.app.notify(t("Deleted from the cloud: ${gone}", gone=entry.name), timeout=5)
            self._load_files()

    # --- history, send now, rclone -------------------------------------------------------
    @on(Button.Pressed, "#cb-hist-reload")
    def _hist_reload(self) -> None:
        if self._guard():
            self.run_worker(self.refresh_all(), group="cb-load", exclusive=True, exit_on_error=False)

    @on(Button.Pressed, "#cb-send-now")
    def _send_now_pressed(self) -> None:
        if not self._guard():
            return
        if not self.plans:
            self.app.notify(t("Make a cloud backup first: ☁ Cloud backups, ➕ New cloud backup."),
                            severity="warning")
            return
        self.run_worker(self._send_now(list(self.plans)), group="cb-send", exclusive=True, exit_on_error=False)

    async def _send_now(self, plans: list[cloud.Plan]) -> None:
        """Each cloud backup now; the first makes a fresh backup, the others send that one."""
        lines: list[str] = []
        ok = True
        last = ""
        for i, plan in enumerate(plans):
            what = cron.cloud_what(self._plan_job(plan)) if self._plan_job(plan) else "sql+marc"
            out = await self.task(t("Sending to the cloud: ${name}...", name=plan.id), "cloud-send-now", plan.id,
                                  what, *(("fresh",) if i == 0 else ()), quiet=True)
            if out is None:
                return
            lines += out.lists.get("line", [])
            msg = out.last("ok", "error")
            last = msg[2] if msg else last
            ok = ok and out.ok
        await self._say(t("☁ Send a backup now"), last + ("\n\n" + "\n".join(lines[-12:]) if lines else ""),
                        "ok" if ok else "error")
        await self.refresh_all()

    @on(Button.Pressed, "#cb-official")
    def _official_pressed(self) -> None:
        if self._guard():
            self.run_worker(self._official(), group="cb-official", exclusive=True, exit_on_error=False)

    async def _official(self) -> None:
        if not await self.app.push_screen_wait(ConfirmScreen(
                t("⬆ Install the official rclone"),
                t("Download rclone from rclone.org (checked against its SHA-256 list) and put it in place of "
                  "Debian's package? The connections already made are kept."))):
            return
        out = await self.task(t("Downloading the official rclone..."), "cloud-rclone-official")
        if out is None or not out.ok:
            return
        msg = out.last("ok")
        if not self.app.env.demo:
            self.catalog = await cloud.load_catalog() or self.catalog
        await self._say("rclone", msg[2] if msg else "", "ok")
        await self.refresh_all()

    @on(Button.Pressed, "#cb-copy-dest")
    def _copy_dest(self) -> None:
        plan = self.selected_plan() or (self.plans[0] if self.plans else None)
        if plan:
            self.app.copy_to_clipboard(f"{plan.remote}:{plan.folders()[0]}/")

    @on(Button.Pressed, "#cb-close")
    def action_close(self) -> None:
        if self._busy:
            self.app.notify(t("Wait: the cloud is still answering."), severity="warning")
            return
        self.dismiss(None)


def restore_path(result) -> str | None:
    """The file to restore when the screen closed with ("restore", path)."""
    if isinstance(result, tuple) and len(result) == 2 and result[0] == "restore" and result[1]:
        return str(Path(result[1]))
    return None
