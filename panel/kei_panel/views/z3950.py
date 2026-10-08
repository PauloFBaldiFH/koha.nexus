"""Z3950View: public catalogues for copy cataloguing, scanned and ranked.

The list (z3950.py) is grouped by region; the librarian ticks servers
(space, or a click on a region to tick all of it), scans them behind the
Pac-Man loader (a real search that must return a MARC record, latency in
ms) and adds the chosen ones to Koha's z3950servers with
`config.sh --task z3950-add`, ranked by speed. Logins typed here stay in
the panel's private config file and the temporary list the task deletes.
"""

from __future__ import annotations

import asyncio
import os
import random
import tempfile
import urllib.request
from dataclasses import replace
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Label, Static

from .. import z3950
from ..i18n import t
from ..screens.dialogs import ConfirmScreen, InputScreen
from ..tasks import Reporter, TaskFailed, TaskResult, run_with_loader
from .base import SectionView

STATUS_MARK = {"ok": "●", "empty": "◐", "no_marc": "◐", "login": "🔒", "tcp": "○", "dead": "✕"}


class Z3950View(SectionView):
    BINDINGS = [Binding("space", "toggle", t("Select"), show=False)]

    loaded = False

    def __init__(self, section):
        super().__init__(section)
        self.targets: list[z3950.Target] = []
        self.history = z3950.History()
        self.selected: set[str] = set()
        self.in_koha: set[str] = set()
        self.show_hidden = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield from self.heading()
        yield Static(t("Public catalogues to copy records from. Tick servers with the space bar (or a region "
                      "to tick it all), scan them, then add the working ones to Koha. * an address from an "
                      "older list: the scan tells if it still works."), classes="view-prompt", markup=False)
        with Horizontal(classes="quick-actions"):
            yield Button(t("Scan"), id="z-scan", classes="small", variant="primary")
            yield Button(t("Add to Koha"), id="z-add", classes="small", variant="success")
            yield Button(t("Login"), id="z-login", classes="small")
            yield Button(t("Hide"), id="z-hide", classes="small")
        with Horizontal(classes="quick-actions"):
            yield Button(t("Community list"), id="z-sync", classes="small")
            yield Button(t("Import"), id="z-import", classes="small")
            yield Button(t("Export"), id="z-export", classes="small")
            yield Button(t("Show hidden"), id="z-hidden", classes="small")
        yield Label("", id="z-summary", classes="view-prompt")
        table = DataTable(id="z-table", zebra_stripes=True, cursor_type="row")
        table.add_column(" ", key="tick")
        table.add_column(t("Server"), key="name")
        table.add_column(t("Status"), key="status")
        table.add_column("ms", key="ms")
        table.add_column(t("Format"), key="format")
        table.add_column(t("Address"), key="address")
        yield table

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            if self.app.env.demo:
                z3950.use_dir(demo_dir())
            self.reload()
            self.run_worker(self._load_koha(), exclusive=True, group="z3950-koha", exit_on_error=False)

    # ------------------------------------------------------------------
    # The list
    # ------------------------------------------------------------------
    def reload(self) -> None:
        self.targets = z3950.load_all()
        self.history = z3950.History()
        self.draw()

    async def _load_koha(self) -> None:
        """The servers Koha already has (marked "in Koha"); quiet on failure."""
        try:
            out = await self.app.bridge.task("z3950-list")
        except Exception:     # noqa: BLE001 (no installer, no database: the list still works)
            return
        keys = set()
        for row in out.lists.get("row", []):
            parts = row.split("\t")
            if len(parts) >= 3 and parts[1].isdigit():
                keys.add(f"{parts[0].lower()}:{parts[1]}/{parts[2]}")
        self.in_koha = keys
        self.draw()

    def visible(self) -> list[z3950.Target]:
        return [tg for tg in self.targets if self.show_hidden or not self.history.blacklisted(tg.key)]

    def by_key(self, key: str) -> z3950.Target | None:
        return next((tg for tg in self.targets if tg.key == key), None)

    def draw(self) -> None:
        table = self.query_one("#z-table", DataTable)
        row = table.cursor_row
        table.clear()
        shown = self.visible()
        for region, label in z3950.REGIONS.items():
            group = [tg for tg in shown if tg.region == region]
            if not group:
                continue
            ticked = sum(tg.key in self.selected for tg in group)
            mark = "☑" if ticked == len(group) else ("◩" if ticked else "☐")
            table.add_row(mark, f"[b]{t(label)}[/b]", f"{len(group)} {t('servers')}", "", "", "",
                          key=f"region:{region}")
            for tg in sorted(group, key=self._order):
                table.add_row(*self._cells(tg), key=tg.key)
        if shown:
            table.move_cursor(row=min(row, table.row_count - 1))
        hidden = len(self.targets) - len(shown)
        scanned = [self.history.get(tg.key) for tg in shown if self.history.get(tg.key).get("status")]
        working = sum(h.get("status") == "ok" for h in scanned)
        text = (f"{len(shown)} {t('servers')} · {len(self.selected)} {t('selected')} · "
                f"{working}/{len(scanned)} {t('working in the last scan')}")
        if hidden:
            text += f" · {hidden} {t('hidden')}"
        self.query_one("#z-summary", Label).update(text)
        self.query_one("#z-hidden", Button).label = t("Hide hidden") if self.show_hidden else t("Show hidden")

    def _order(self, tg: z3950.Target):
        h = self.history.get(tg.key)
        status = h.get("status", "")
        rank = z3950.STATUS_ORDER.index(status) if status in z3950.STATUS_ORDER else 1.5
        return (rank, h.get("query_ms") or 10**9, tg.name.lower())

    def _cells(self, tg: z3950.Target) -> tuple:
        h = self.history.get(tg.key)
        status = h.get("status", "")
        if self.history.blacklisted(tg.key):
            text = t("Hidden (keeps failing)") if h.get("auto") else t("Hidden")
        elif status:
            text = f"{STATUS_MARK[status]} {t(z3950.STATUS_SHORT[status])}"
        else:
            text = t("Not scanned yet")
        if tg.key in self.in_koha:
            text = f"{t('In Koha')} · {text}"
        name = tg.name + (" 🔒" if tg.login and not tg.user else "") + ("" if tg.verified else " *")
        kind = "SRU" if tg.kind == "sru" else "Z39.50"
        ms = h.get("query_ms") if status in ("ok", "empty") else h.get("connect_ms")
        return ("☑" if tg.key in self.selected else "☐", name, text, "" if ms is None else str(ms),
                f"{kind} {tg.syntax}", f"{tg.host}:{tg.port}/{tg.db}")

    def cursor_key(self) -> str:
        table = self.query_one("#z-table", DataTable)
        if not table.row_count:
            return ""
        return table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value or ""

    def toggle(self, key: str) -> None:
        if key.startswith("region:"):
            group = [tg.key for tg in self.visible() if tg.region == key[7:]]
            if all(k in self.selected for k in group):
                self.selected.difference_update(group)
            else:
                self.selected.update(group)
        elif key:
            self.selected.symmetric_difference_update({key})
        self.draw()

    def action_toggle(self) -> None:
        self.toggle(self.cursor_key())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        self.toggle(event.row_key.value or "")

    def chosen(self) -> list[z3950.Target]:
        """The ticked servers, else every one shown."""
        shown = self.visible()
        picked = [tg for tg in shown if tg.key in self.selected]
        return picked or shown

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {"z-scan": self.scan, "z-add": self.add, "z-login": self.login, "z-hide": self.hide,
                   "z-sync": self.sync, "z-import": self.import_list, "z-export": self.export,
                   "z-hidden": self.toggle_hidden}
        if event.button.id in actions:
            event.stop()
            actions[event.button.id]()

    def toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        self.draw()

    # ------------------------------------------------------------------
    # The scan
    # ------------------------------------------------------------------
    def scan(self) -> None:
        targets = self.chosen()
        if not targets:
            return
        demo = self.app.env.demo

        async def job(reporter: Reporter) -> list[z3950.ScanResult]:
            done = [0]

            def each(tg: z3950.Target, res: z3950.ScanResult) -> None:
                done[0] += 1
                reporter.progress(done[0], len(targets))
                reporter.status(f"{tg.name}: {t(z3950.STATUS_TEXT[res.status])}")
                ms = f" {res.query_ms} ms" if res.query_ms is not None else ""
                reporter.log(f"{res.status:8} {tg.host}:{res.port or tg.port}/{tg.db}{ms} {res.title or res.detail}")
            reporter.status(t("Scanning ${n} servers", n=len(targets)))
            if demo:
                return await _demo_scan(targets, each)
            return await z3950.scan(targets, on_result=each)

        run_with_loader(self.app, t("Scanning Z39.50/SRU servers"), job, on_done=self._scanned)

    def _scanned(self, result: TaskResult) -> None:
        if not result.ok:
            self.app.task_failed(t("Scanning Z39.50/SRU servers"), result)
            return
        for res in result.value:
            self.history.record(res)
        self.history.save()
        ranked = z3950.rank(result.value)
        working = [r for r in ranked if r.status == "ok"]
        self.draw()
        best = self.by_key(working[0].key) if working else None
        msg = t("${ok} of ${n} servers returned a valid MARC record.", ok=len(working), n=len(ranked))
        if best:
            msg += " " + t("Fastest: ${name} (${ms} ms).", name=best.name, ms=working[0].query_ms)
        self.app.notify(msg, severity="information" if working else "warning", timeout=8)

    # ------------------------------------------------------------------
    # Into Koha
    # ------------------------------------------------------------------
    def add(self) -> None:
        picked = [tg for tg in self.visible() if tg.key in self.selected]
        if not picked:
            self.app.notify(t("Tick the servers to add first (space bar)."), severity="warning")
            return
        self.app.run_worker(self._add(picked), group="routine", exclusive=True, exit_on_error=False)

    async def _add(self, picked: list[z3950.Target]) -> None:
        from ..routines.common import run_task, show_done
        title = t("Add Z39.50/SRU servers to Koha")
        ranks = z3950.koha_ranks(picked, self.history)
        lines = [f"{ranks[tg.key]:>2}. {tg.describe()}" for tg in sorted(picked, key=lambda x: ranks[x.key])]
        missing = [tg.name for tg in picked if tg.login and not tg.user]
        question = t("Add these ${n} servers to Koha's Z39.50/SRU servers, checked for the cataloguing "
                     "searches? Servers Koha already has are kept as they are.", n=len(picked))
        if missing:
            question += "\n\n" + t("These need a login you have not typed yet: ${names}", names=", ".join(missing))
        if not await self.app.push_screen_wait(ConfirmScreen(title, question, preview="\n".join(lines),
                                                             preview_title=t("Rank by speed in the last scan"))):
            return
        path = z3950.write_add_file(picked, ranks)
        try:
            result = await run_task(self.app, title, "z3950-add", str(path))
        finally:
            path.unlink(missing_ok=True)
        await show_done(self.app, title, result)
        await self._load_koha()

    # ------------------------------------------------------------------
    # Login, hide
    # ------------------------------------------------------------------
    def login(self) -> None:
        tg = self.by_key(self.cursor_key())
        if not tg:
            self.app.notify(t("Move the cursor to a server first."), severity="warning")
            return
        self.app.run_worker(self._login(tg), group="z3950-login", exclusive=True, exit_on_error=False)

    async def _login(self, tg: z3950.Target) -> None:
        title = t("Login for ${name}", name=tg.name)
        user = await self.app.push_screen_wait(InputScreen(
            title, t("For subscription servers (OCLC and others). Leave empty to remove the login. The password "
                     "is kept only in the panel's private file and in Koha, never in a log."),
            t("User"), validate=lambda v: "", value=tg.user))
        if user is None:
            return
        password = ""
        if user:
            password = await self.app.push_screen_wait(InputScreen(title, "", t("Password"), password=True,
                                                                   validate=lambda v: ""))
            if password is None:
                return
        tg.user, tg.password, tg.login = user, password, tg.login or bool(user)
        self._save()
        self.app.notify(t("Login saved for ${name}.", name=tg.name) if user else t("Login removed."))

    def hide(self) -> None:
        key = self.cursor_key()
        if not self.by_key(key):
            return
        self.history.set_manual(key, not self.history.blacklisted(key))
        self.history.save()
        self.selected.discard(key)
        self.draw()

    def _save(self) -> None:
        try:
            z3950.save_local(self.targets)
        except OSError as e:
            self.app.notify(str(e), severity="error")
        self.draw()

    # ------------------------------------------------------------------
    # Community list, import, export
    # ------------------------------------------------------------------
    def sync(self) -> None:
        demo = self.app.env.demo

        def job(reporter: Reporter) -> list[z3950.Target]:
            reporter.status(z3950.COMMUNITY_URL)
            if demo:
                return [replace(tg, origin="community") for tg in z3950.load_curated()]
            try:
                return z3950.community_sync()
            except (OSError, ValueError) as e:
                raise TaskFailed(str(e)) from None

        run_with_loader(self.app, t("Downloading the community list"), job, on_done=self._synced)

    def _synced(self, result: TaskResult) -> None:
        if not result.ok:
            self.app.task_failed(t("Downloading the community list"), result)
            return
        self._merge(result.value)

    def _merge(self, new: list[z3950.Target]) -> None:
        before = {tg.key for tg in self.targets}
        self.targets = z3950.merge(self.targets, new)
        added = sum(tg.key not in before for tg in new)
        self._save()
        self.app.notify(t("${n} servers read, ${added} new.", n=len(new), added=added))

    def import_list(self) -> None:
        self.app.run_worker(self._import(), group="z3950-import", exclusive=True, exit_on_error=False)

    async def _import(self) -> None:
        title = t("Import Z39.50/SRU servers")
        source = await self.app.push_screen_wait(InputScreen(
            title, t("A file on this server (JSON, YAML, CSV or a Koha SQL dump of z3950servers), or the address "
                     "of a page that lists servers (host:port/database, tables, SRU addresses)."),
            t("File or address"), validate=_source_problem))
        if not source:
            return

        def job(reporter: Reporter) -> list[z3950.Target]:
            reporter.status(source)
            try:
                if source.startswith(("http://", "https://")):
                    req = urllib.request.Request(source, headers={"User-Agent": "koha.nexus-panel"})
                    with urllib.request.urlopen(req, timeout=20) as resp:   # noqa: S310 (typed by the librarian)
                        text = resp.read(5_000_000).decode("utf-8", "replace")
                else:
                    text = Path(source).expanduser().read_text(encoding="utf-8", errors="replace")
                found = z3950.read_any(text, source)
            except (OSError, ValueError) as e:
                raise TaskFailed(str(e)) from None
            if not found:
                raise TaskFailed(t("No Z39.50/SRU server was found in it."))
            return found

        run_with_loader(self.app, title, job, on_done=self._imported)

    def _imported(self, result: TaskResult) -> None:
        if not result.ok:
            self.app.task_failed(t("Import Z39.50/SRU servers"), result)
            return
        self._merge(result.value)

    def export(self) -> None:
        self.app.run_worker(self._export(), group="z3950-export", exclusive=True, exit_on_error=False)

    async def _export(self) -> None:
        targets = self.chosen()
        default = str(Path(os.path.expanduser("~")) / "z3950-servers.json")
        path = await self.app.push_screen_wait(InputScreen(
            t("Export Z39.50/SRU servers"),
            t("${n} servers (the ticked ones, else all shown). The file type follows the name: .json, .csv or "
              ".sql (for another Koha). Passwords are not exported.", n=len(targets)),
            t("File"), value=default))
        if not path:
            return
        try:
            z3950.write_export(Path(path).expanduser(), targets)
        except OSError as e:
            self.app.notify(str(e), severity="error")
            return
        self.app.notify(t("Saved: ${file}", file=path))


def _source_problem(value: str) -> str:
    if not value:
        return t("Cannot be empty.")
    if value.startswith(("http://", "https://")) or Path(value).expanduser().is_file():
        return ""
    return t("File not found.")


async def _demo_scan(targets, each) -> list[z3950.ScanResult]:
    """Demo mode: no network; the verified servers answer."""
    out = []
    rnd = random.Random(42)
    for tg in targets:
        await asyncio.sleep(0.08)
        if tg.verified and not tg.login:
            res = z3950.ScanResult(tg.key, "ok", tg.port, rnd.randint(20, 200), rnd.randint(120, 1500), 1,
                                   "Don Quixote")
        elif tg.login:
            res = z3950.ScanResult(tg.key, "login", tg.port, rnd.randint(20, 200))
        else:
            res = z3950.ScanResult(tg.key, "dead")
        each(tg, res)
        out.append(res)
    return out


def demo_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "kei-demo-z3950"
    path.mkdir(parents=True, exist_ok=True)
    return path
