"""Z3950View: everything Z39.50 / SRU on one screen, in three parts.

Top, this catalogue's own server: the switch turns koha-z3950-responder
on or off (`config.sh --task z3950-daemon on|off`), with its state and port.
Middle, the koha.nexus Catalog Network: the switch puts the shared
catalogue's SRU address in Koha's z3950servers or takes it out
(`--task catalog-network on URL|off`). Both read `--task z3950-server-status`.

Then the direct servers on-demand enrichment asks (`--task z3950-health`):
the ones whose breaker is open, or that failed in the last 7 days, with the
last error; Reset forgets a server's breaker (`--task z3950-health-reset
ID`, or --all) so the next search asks it again.

Bottom, public catalogues for copy cataloguing. "Show servers" tests the
whole list (z3950.py) behind the Pac-Man loader, a real search that must
return a MARC record, the backups (koha.nexus gateway rows) only for the
servers that returned none; then it becomes "Update", to test again. The
list, grouped by region, shows the servers that returned a record, a backup
only when its main server did not, and the ticked ones. The tick is
"selected for the cataloguing search" in Koha (Koha's checked): "Save to
Koha" adds the ticked servers Koha lacks (`config.sh --task z3950-add`,
ranked by speed) and ticks or unticks the ones it has
(`--task z3950-check`); nothing is deleted. More than SEARCH_LIMIT (20)
ticked is advised against, never refused. "Update server settings" sends
the whole list to `config.sh --task z3950-sync`: every row Koha has is
refreshed, the authority files are added when missing. Logins typed here
stay in the panel's private config file and the temporary list the task
deletes.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import tempfile
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static, Switch

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
        # The servers Koha has ticked for the cataloguing search (checked = 1).
        self.koha_checked: set[str] = set()
        # The ticks follow Koha's once its list has been read (the first time).
        self.ticks_from_koha = False
        self.show_hidden = False
        # This Koha's server and the network, as the last status said: the
        # switches are set from them, and a change that matches is no request.
        self.server: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield from self.heading()
            yield Button(t("Reload"), id="z-reload", classes="small")
        with Vertical(id="z-inbound", classes="hub-box"):
            with Horizontal(classes="z-switch-row"):
                yield Switch(False, id="z-daemon", disabled=True)
                yield Label(t("Z39.50/SRU server (koha-z3950-daemon)"), classes="z-switch-name")
                yield Label(t("Not checked yet."), id="z-daemon-state", classes="z-switch-state")
            yield Static(t("Lets other libraries search this catalogue by Z39.50 and SRU (koha-z3950-daemon). "
                           "Turning it on opens its port in the firewall; off closes it, also after a restart."),
                         classes="ai-note", markup=False)
        with Vertical(id="z-network", classes="hub-box"):
            with Horizontal(classes="z-switch-row"):
                yield Switch(False, id="z-net", disabled=True)
                yield Label(z3950.NETWORK_NAME, classes="z-switch-name")
                yield Label(t("Not checked yet."), id="z-net-state", classes="z-switch-state")
            yield Static("", id="z-net-note", classes="ai-note", markup=False)
        with Vertical(id="z-health", classes="hub-box z-wide"):
            yield Label(t("Not checked yet."), id="z-health-state")
            health = DataTable(id="z-health-table", zebra_stripes=True, cursor_type="row", classes="hub-table")
            health.add_column(t("Server"), key="id")
            health.add_column(t("State"), key="state")
            health.add_column(t("OK (7 days)"), key="ok")
            health.add_column(t("Failed (7 days)"), key="fail")
            health.add_column(t("Last error"), key="error")
            yield health
            with Horizontal(classes="quick-actions"):
                yield Button(t("Reset"), id="z-health-reset", classes="small", disabled=True)
                yield Button(t("Reset all"), id="z-health-reset-all", classes="small", disabled=True)
        with Vertical(id="z-outbound", classes="hub-box z-wide"):
            yield from self.compose_outbound()

    def compose_outbound(self) -> ComposeResult:
        yield Static(t("Public catalogues to copy records from. \"Show servers\" tests every server with a real "
                      "search and lists the ones that return a record; a backup server appears only when its "
                      "main server returns none. Tick (space bar, or a region to tick it all) the servers for "
                      "Koha's cataloguing search, then Save to Koha. * an address from an older list."),
                     classes="view-prompt", markup=False)
        with Horizontal(classes="quick-actions"):
            yield Button(t("Show servers"), id="z-scan", classes="small", variant="primary")
            yield Button(t("Save to Koha"), id="z-add", classes="small", variant="success")
            yield Button(t("Add server"), id="z-new", classes="small")
            yield Button(t("Login"), id="z-login", classes="small")
            yield Button(t("Hide"), id="z-hide", classes="small")
        with Horizontal(classes="quick-actions"):
            yield Button(t("Community list"), id="z-sync", classes="small")
            yield Button(t("Import"), id="z-import", classes="small")
            yield Button(t("Export"), id="z-export", classes="small")
            yield Button(t("Show all"), id="z-hidden", classes="small")
        with Horizontal(classes="quick-actions"):
            yield Button(t("Update server settings"), id="z-update", classes="small", variant="warning")
        yield Static("", id="z-limit", classes="ai-note", markup=False)
        yield Label("", id="z-summary", classes="view-prompt")
        table = DataTable(id="z-table", zebra_stripes=True, cursor_type="row")
        table.add_column(" ", key="tick")
        table.add_column(t("Server"), key="name")
        table.add_column(t("Status"), key="status")
        table.add_column("ms", key="ms")
        table.add_column(t("Format"), key="format")
        table.add_column(t("Address"), key="address")
        yield table

    def on_mount(self) -> None:
        self.query_one("#z-inbound").border_title = t("This catalogue's Z39.50 / SRU server (inbound)")
        self.query_one("#z-network").border_title = t("Community network")
        self.query_one("#z-outbound").border_title = t("Catalogues to copy records from (outbound)")
        self.query_one("#z-health").border_title = t("Direct servers for on-demand enrichment")
        self.query_one("#z-net-note", Static).update(
            t("The shared catalogue of the koha.nexus libraries. Turning it on adds it to Koha's Z39.50/SRU "
              "servers, checked for the cataloguing searches; off takes it out.")
            + "\n" + t("Address: ${url}", url=z3950.network_url()))

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            if self.app.env.demo:
                z3950.use_dir(demo_dir())
            self.reload()
            self.selected.update(tg.key for tg in self.targets if tg.preselect
                                 and not self.history.get(tg.key).get("manual"))
            self.draw()
            self.run_worker(self._load_koha(), exclusive=True, group="z3950-koha", exit_on_error=False)
            self.load_server()
            self.load_health()

    def refresh_data(self) -> None:
        self.load_server()
        self.load_health()
        self.run_worker(self._load_koha(), exclusive=True, group="z3950-koha", exit_on_error=False)

    # ------------------------------------------------------------------
    # Inbound server and community network
    # ------------------------------------------------------------------
    def load_server(self) -> None:
        self.run_worker(self._load_server(), exclusive=True, group="z3950-server", exit_on_error=False)

    async def _load_server(self) -> None:
        try:
            out = await self.app.bridge.task("z3950-server-status")
        except Exception:     # noqa: BLE001 (no installer: the switches stay off and say so)
            self.show_server()
            return
        if out.ok:
            self.server = dict(out.results)
        self.show_server()

    def show_server(self) -> None:
        s = self.server
        daemon = self.query_one("#z-daemon", Switch)
        net = self.query_one("#z-net", Switch)
        daemon.disabled = "daemon" not in s
        net.disabled = "network" not in s
        daemon.value = s.get("daemon") == "running"
        net.value = s.get("network") == "on"
        if "daemon" not in s:
            state = t("Not checked")
        elif s["daemon"] == "running":
            state = t("● Running · port ${port}", port=s.get("port", "2100"))
        else:
            state = t("○ Stopped · port ${port}", port=s.get("port", "2100"))
        self.query_one("#z-daemon-state", Label).update(state)
        if "network" not in s:
            state = t("Not checked")
        elif s["network"] == "on":
            state = t("● In Koha: ${url}", url=s.get("network_url", ""))
        else:
            state = t("○ Not in Koha")
        self.query_one("#z-net-state", Label).update(state)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        event.stop()
        if event.switch.id == "z-daemon" and event.value != (self.server.get("daemon") == "running"):
            self.app.run_worker(self._toggle_daemon(event.value), group="routine", exclusive=True,
                                exit_on_error=False)
        elif event.switch.id == "z-net" and event.value != (self.server.get("network") == "on"):
            self.app.run_worker(self._toggle_network(event.value), group="routine", exclusive=True,
                                exit_on_error=False)

    async def _toggle_daemon(self, on: bool) -> None:
        from ..routines.common import failed, run_task, show_done
        title = t("This catalogue's Z39.50 / SRU server")
        port = self.server.get("port", "2100")
        question = (t("Turn on this catalogue's Z39.50/SRU server? Other libraries will be able to search it on "
                      "port ${port}, and the port is opened in the firewall.", port=port) if on else
                    t("Turn off this catalogue's Z39.50/SRU server? Other libraries will no longer search it, and "
                      "port ${port} is closed in the firewall.", port=port))
        if not await self.app.push_screen_wait(ConfirmScreen(title, question)):
            self.show_server()
            return
        result = await run_task(self.app, title, "z3950-daemon", "on" if on else "off")
        if not failed(result):
            out = result.value
            self.server["daemon"] = out.get("daemon") or ("running" if on else "stopped")
            self.server["port"] = out.get("port") or port
        self.show_server()
        await show_done(self.app, title, result)
        self.load_server()

    async def _toggle_network(self, on: bool) -> None:
        from ..routines.common import failed, run_task, show_done
        title = z3950.NETWORK_NAME
        url = z3950.network_url()
        question = (t("Add the koha.nexus network (${url}) to Koha's Z39.50/SRU servers, checked for the "
                      "cataloguing searches?", url=url) if on else
                    t("Take the koha.nexus network out of Koha's Z39.50/SRU servers?"))
        if not await self.app.push_screen_wait(ConfirmScreen(title, question)):
            self.show_server()
            return
        args = ("on", url) if on else ("off",)
        result = await run_task(self.app, title, "catalog-network", *args)
        if not failed(result):
            out = result.value
            self.server["network"] = out.get("network") or ("on" if on else "off")
            self.server["network_url"] = out.get("network_url") or url
        self.show_server()
        await show_done(self.app, title, result)
        self.load_server()
        await self._load_koha()

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
        keys, checked = set(), set()
        for row in out.lists.get("row", []):
            parts = row.split("\t")
            if len(parts) >= 3 and parts[1].isdigit():
                # An HTTPS SRU row's host carries https:// in Koha, not in the list.
                host = re.sub(r"^https?://", "", parts[0].lower())
                keys.add(f"{host}:{parts[1]}/{parts[2]}")
                if len(parts) >= 6 and parts[5].strip() not in ("", "0"):
                    checked.add(f"{host}:{parts[1]}/{parts[2]}")
        self.in_koha, self.koha_checked = keys, checked
        known = {tg.key for tg in self.targets}
        if keys & known and not self.ticks_from_koha:
            # The ticks say what Koha searches: its checked rows of the list.
            self.ticks_from_koha = True
            self.selected = checked & known
        self.draw()

    def visible(self) -> list[z3950.Target]:
        if self.show_hidden:
            return list(self.targets)
        return z3950.shown(self.targets, self.history, self.selected)

    def by_key(self, key: str) -> z3950.Target | None:
        return next((tg for tg in self.targets if tg.key == key), None)

    def draw(self) -> None:
        table = self.query_one("#z-table", DataTable)
        row = table.cursor_row
        table.clear()
        shown = self.visible()
        for n, (region, label) in enumerate(z3950.REGIONS.items(), 1):
            group = [tg for tg in shown if tg.region == region]
            if not group:
                continue
            ticked = sum(tg.key in self.selected for tg in group)
            mark = "☑" if ticked == len(group) else ("◩" if ticked else "☐")
            # "\[" keeps the heading's number from being read as Rich markup.
            table.add_row(mark, f"[b]\\[{n}] {t(label)}[/b]", f"{len(group)} {t('servers')}", "", "", "",
                          key=f"region:{region}")
            for tg in sorted(group, key=self._order):
                table.add_row(*self._cells(tg), key=tg.key)
        if shown:
            table.move_cursor(row=min(row, table.row_count - 1))
        hidden = len(self.targets) - len(shown)
        if not self.history.tested and not self.show_hidden:
            text = t("Press Show servers to test the ${n} servers of the list and show the ones that work.",
                     n=len(self.targets))
            if shown:
                text += " " + t("Ticked for the search: ${n}.", n=len(shown))
        else:
            working = sum(self.history.works(tg.key) for tg in self.targets)
            text = t("${shown} servers shown · ${selected} ticked for the search · ${working} returned a record "
                     "in the last test (${when})", shown=len(shown), selected=len(self.selected), working=working,
                     when=_when(self.history.tested))
            if hidden:
                text += " · " + t("${n} hidden (no record, backup not needed, or hidden by hand)", n=hidden)
        self.query_one("#z-summary", Label).update(text)
        self.query_one("#z-hidden", Button).label = t("Only working") if self.show_hidden else t("Show all")
        self.query_one("#z-scan", Button).label = t("Update") if self.history.tested else t("Show servers")
        self.draw_limit()

    def draw_limit(self) -> None:
        """The recommendation of at most SEARCH_LIMIT servers, in the theme's
        warning colour once it is passed (never a block)."""
        n = z3950.most_ticked(self.targets, self.selected)
        note = self.query_one("#z-limit", Static)
        text = t("Recommendation: tick at most ${limit} servers for the search at once. More than that can make "
                 "Koha's search unstable (slow, or some servers left without an answer).", limit=z3950.SEARCH_LIMIT)
        if n > z3950.SEARCH_LIMIT:
            text += " " + t("Now ${n} are ticked: it works, but untick some if the search becomes unstable.", n=n)
        note.update(text)
        note.set_class(n > z3950.SEARCH_LIMIT, "-over")

    def _order(self, tg: z3950.Target):
        h = self.history.get(tg.key)
        status = h.get("status", "")
        rank = z3950.STATUS_ORDER.index(status) if status in z3950.STATUS_ORDER else 1.5
        return (rank, h.get("query_ms") or 10**9, tg.name.lower())

    def _cells(self, tg: z3950.Target) -> tuple:
        h = self.history.get(tg.key)
        status = h.get("status", "")
        if h.get("manual"):
            text = t("Hidden")
        elif status:
            text = f"{STATUS_MARK[status]} {t(z3950.STATUS_SHORT[status])}"
        else:
            text = t("Not scanned yet")
        if tg.key in self.in_koha:
            text = f"{t('In Koha')} · {text}"
        badge = z3950.badge(tg)
        name = ((badge + " ") if badge else "") + tg.name + (" 🔒" if tg.login and not tg.user else "") \
            + ("" if tg.verified else " *")
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
        actions = {"z-scan": self.scan, "z-add": self.add, "z-new": self.new_server, "z-login": self.login,
                   "z-hide": self.hide,
                   "z-sync": self.sync, "z-import": self.import_list, "z-export": self.export,
                   "z-hidden": self.toggle_hidden, "z-reload": self.refresh_data,
                   "z-update": self.update_servers, "z-health-reset": self.reset_health,
                   "z-health-reset-all": self.reset_all_health}
        if event.button.id in actions:
            event.stop()
            actions[event.button.id]()

    # ------------------------------------------------------------------
    # Direct servers' health (on-demand enrichment)
    # ------------------------------------------------------------------
    def load_health(self) -> None:
        self.run_worker(self._load_health(), exclusive=True, group="z3950-health", exit_on_error=False)

    async def _load_health(self) -> None:
        import json
        try:
            out = await self.app.bridge.task("z3950-health")
            rows = json.loads(out.get("health") or "[]", strict=False) if out.ok else []
        except Exception:     # noqa: BLE001 (no installer, or not installed yet: an empty list)
            rows = []
        self.draw_health(rows if isinstance(rows, list) else [])

    def draw_health(self, rows: list[dict]) -> None:
        table = self.query_one("#z-health-table", DataTable)
        table.clear()
        trouble = [r for r in rows if r.get("state") != "ok" or r.get("fail_7d")]
        for r in trouble:
            table.add_row(r.get("id", ""), health_state(r.get("state", "")), str(r.get("ok_7d", 0)),
                          str(r.get("fail_7d", 0)), (r.get("last_error") or "")[:80], key=r.get("id", "") + "|" + r.get("key", ""))
        if not rows:
            text = t("On-demand enrichment is not installed yet, or has not asked any server.")
        elif not trouble:
            text = t("All ${n} direct server address(es) answered or were not asked yet.", n=len(rows))
        else:
            text = t("${n} of ${total} direct server address(es) failed lately or are paused:", n=len(trouble),
                     total=len(rows))
        self.query_one("#z-health-state", Label).update(text)
        self.query_one("#z-health-reset", Button).disabled = not trouble
        self.query_one("#z-health-reset-all", Button).disabled = not trouble

    def reset_health(self) -> None:
        table = self.query_one("#z-health-table", DataTable)
        if not table.row_count:
            return
        key = table.coordinate_to_cell_key((max(table.cursor_row, 0), 0)).row_key.value or ""
        self.run_worker(self._reset_health(key.split("|")[0]), exclusive=True, group="z3950-health",
                        exit_on_error=False)

    def reset_all_health(self) -> None:
        self.run_worker(self._reset_health("--all"), exclusive=True, group="z3950-health", exit_on_error=False)

    async def _reset_health(self, server: str) -> None:
        if not server:
            return
        try:
            out = await self.app.bridge.task("z3950-health-reset", server)
            n = out.get("reset") or "0"
        except Exception:     # noqa: BLE001
            n = "0"
        self.app.notify(t("${n} server address(es) will be asked again on the next search.", n=n), timeout=5)
        await self._load_health()

    def toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        self.draw()

    # ------------------------------------------------------------------
    # The scan
    # ------------------------------------------------------------------
    def scan(self) -> None:
        """Show servers / Update: every server of the list (but the ones
        hidden by hand) is tested; then the backups of the servers that
        returned no record."""
        targets = [tg for tg in self.targets if not self.history.get(tg.key).get("manual")]
        if not targets:
            return
        self._test(targets, whole=True)

    def _test(self, targets: list[z3950.Target], whole: bool = False) -> None:
        demo = self.app.env.demo
        main, backups = z3950.test_phases(targets)
        # A backup's main server that is not tested now keeps its last result.
        last = {tg.key: self.history.works(tg.key) for tg in self.targets}

        async def job(reporter: Reporter) -> list[z3950.ScanResult]:
            done, total = [0], [len(main)]

            def each(tg: z3950.Target, res: z3950.ScanResult) -> None:
                done[0] += 1
                reporter.progress(done[0], total[0])
                reporter.status(f"{tg.name}: {t(z3950.STATUS_TEXT[res.status])}")
                ms = f" {res.query_ms} ms" if res.query_ms is not None else ""
                reporter.log(f"{res.status:8} {tg.host}:{res.port or tg.port}/{tg.db}{ms} {res.title or res.detail}")

            async def run(group: list[z3950.Target]) -> list[z3950.ScanResult]:
                if demo:
                    return await _demo_scan(group, each)
                return await z3950.scan(group, on_result=each)
            reporter.status(t("Testing ${n} servers", n=len(main)))
            results = await run(main)
            works = dict(last, **{r.key: r.status == "ok" for r in results})
            needed = [tg for tg in backups if z3950.backup_needed(tg, lambda k: works.get(k, False))]
            if needed:
                total[0] += len(needed)
                reporter.status(t("Testing ${n} backup servers", n=len(needed)))
                results += await run(needed)
            return results

        run_with_loader(self.app, t("Testing Z39.50/SRU servers"), job,
                        on_done=lambda result: self._scanned(result, whole))

    def _scanned(self, result: TaskResult, whole: bool = False) -> None:
        if not result.ok:
            self.app.task_failed(t("Testing Z39.50/SRU servers"), result)
            return
        for res in result.value:
            self.history.record(res)
        if whole:
            self.history.mark_tested()
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
        """Save to Koha: the ticked servers Koha lacks are added (ticked for
        the search), the ones it has are ticked or unticked to match."""
        picked = [tg for tg in self.targets if tg.key in self.selected and tg.key not in self.in_koha]
        changes = [(tg, tg.key in self.selected) for tg in self.targets if tg.key in self.in_koha
                   and (tg.key in self.selected) != (tg.key in self.koha_checked)]
        if not picked and not changes:
            self.app.notify(t("Koha already searches exactly the ticked servers: nothing to save. Tick or untick "
                              "servers with the space bar first."), severity="warning")
            return
        self.app.run_worker(self._add(picked, changes), group="routine", exclusive=True, exit_on_error=False)

    async def _add(self, picked: list[z3950.Target], changes: list[tuple[z3950.Target, bool]]) -> None:
        from ..routines.common import failed, run_task, show_done
        title = t("Save to Koha")
        ranks = z3950.koha_ranks(picked, self.history)
        lines = [f"+ {ranks[tg.key]:>2}. {tg.describe()}" for tg in sorted(picked, key=lambda x: ranks[x.key])]
        lines += [("☑ " if on else "☐ ") + tg.describe() for tg, on in changes]
        question = t("Koha's cataloguing search will ask the ticked servers. Add ${add} new server(s) (+) and "
                     "tick ${on} / untick ${off} of the ones Koha has (☑ / ☐)? Unticked servers stay in Koha, "
                     "only out of the search.", add=len(picked), on=sum(on for _tg, on in changes),
                     off=sum(not on for _tg, on in changes))
        missing = [tg.name for tg in picked if tg.login and not tg.user]
        if missing:
            question += "\n\n" + t("These need a login you have not typed yet: ${names}", names=", ".join(missing))
        n = z3950.most_ticked(self.targets, self.selected)
        if n > z3950.SEARCH_LIMIT:
            question += "\n\n" + t("${n} servers are ticked. We recommend at most ${limit} at once: the search "
                                    "may become unstable. Save anyway?", n=n, limit=z3950.SEARCH_LIMIT)
        if not await self.app.push_screen_wait(ConfirmScreen(title, question, preview="\n".join(lines),
                                                             preview_title=t("Rank by speed in the last test"))):
            return
        result = None
        if picked:
            path = z3950.write_add_file(picked, ranks)
            try:
                result = await run_task(self.app, title, "z3950-add", str(path))
            finally:
                path.unlink(missing_ok=True)
        if changes and (result is None or not failed(result)):
            path = z3950.write_check_file(changes)
            try:
                result = await run_task(self.app, title, "z3950-check", str(path))
            finally:
                path.unlink(missing_ok=True)
        await show_done(self.app, title, result)
        await self._load_koha()

    # ------------------------------------------------------------------
    # A server typed by hand
    # ------------------------------------------------------------------
    def new_server(self) -> None:
        self.app.run_worker(self._new_server(), group="z3950-new", exclusive=True, exit_on_error=False)

    async def _new_server(self) -> None:
        title = t("Add server")
        address = await self.app.push_screen_wait(InputScreen(
            title, t("The server's address as host:port/database (Z39.50), or its SRU address "
                     "(https://host/path). It is tested now and comes ticked for the search."),
            t("Address"), validate=_address_problem))
        if not address:
            return
        name = await self.app.push_screen_wait(InputScreen(title, "", t("Name"), validate=lambda v: "",
                                                           value=_address_target(address).host))
        if name is None:
            return
        tg = replace(_address_target(address), name=name.strip()[:100] or _address_target(address).host)
        self.targets = z3950.merge(self.targets, [tg])
        self.history.set_manual(tg.key, False)
        self.selected.add(tg.key)
        self._save()
        self._test([tg])

    def update_servers(self) -> None:
        self.app.run_worker(self._update_servers(), group="routine", exclusive=True, exit_on_error=False)

    async def _update_servers(self) -> None:
        """Every server Koha has gets the list's settings (host, port,
        database, format, timeout, SRU fields), keeping its tick and rank;
        the authority files are added when missing."""
        from ..routines.common import failed, run_task, show_done
        title = t("Update server settings")
        question = t("Update the settings of the Z39.50/SRU servers Koha already has (address, port, database, "
                     "format, timeout, SRU fields) from this list? Their tick and rank are kept. The authority "
                     "files (Library of Congress names and subjects, Biblioteca Nacional) are added when "
                     "missing, and the Biblioteca Nacional's old Z39.50 addresses are unticked.")
        if not await self.app.push_screen_wait(ConfirmScreen(title, question)):
            return
        path = z3950.write_add_file(z3950.sync_targets(self.targets, self.in_koha), {})
        try:
            result = await run_task(self.app, title, "z3950-sync", str(path))
        finally:
            path.unlink(missing_ok=True)
        if not failed(result):
            out = result.value
            self.app.notify(t("Servers added: ${added} · updated: ${updated}", added=out.get("added", "0"),
                              updated=out.get("updated", "0")), timeout=10)
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
        # Tested at once: the list shows only the ones that return a record.
        self._test([tg for tg in self.targets if tg.key in {n.key for n in result.value}])

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


def health_state(state: str) -> str:
    """A direct server's breaker state (nexus_ondemand.health), for the person."""
    return {"ok": t("Working"), "down": t("Paused after failures"), "half-open": t("Asked again on the next search"),
            "misconfigured": t("Wrong settings (not asked)")}.get(state, state)


def _address_target(value: str) -> z3950.Target | None:
    """A server typed as host:port/database or an SRU address, or None."""
    return z3950.make_target({"host": value.strip(), "name": ""}, "custom")


def _address_problem(value: str) -> str:
    if not value.strip():
        return t("Cannot be empty.")
    return "" if _address_target(value) else t("Not a server address (host:port/database).")


def _when(stamp: int) -> str:
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(stamp)) if stamp else "-"


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
