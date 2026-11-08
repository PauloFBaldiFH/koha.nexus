"""BackupCenterView: every backup of this server in one screen (Paulo,
2026-11-06), in the main menu.

  💾 Backup center                               [Refresh]
  Platform: [ Koha ] [ Tainacan ]        only the installed ones
  ┌ what is true now for that platform ┐
  │ Koha: last backup, size, result, compression of new backups
  │ Tainacan: its packages, the backup key, what is encrypted
  └────────────────────────────────────┘
  Automatic backups: one row each, with its own destination, frequency,
  retention, what is encrypted and its last run ("No run recorded" without one)
  the cards of that platform, then the Cloud connections (any platform)

The platform groups open it already filtered (menus.Entry.scope). Every
card runs the routine it ran before (routines/backup.py for Koha,
routines/platforms.py for Tainacan); nothing is scheduled by opening it.
"""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, HorizontalScroll, Vertical
from rich.text import Text
from textual.widgets import Button, Label, Select, Static

from .. import backup_center, cloud, cron, platforms
from ..i18n import t
from ..widgets.cards import ActionCard, StatusCard
from .backup import CODEC_NOTE, CODECS, RESULTS
from .base import ZONE_ORDER, zone_id
from .dashboard import backup_card, human_bytes
from .platform import ENCRYPTION_NOTE, PlatformSectionView


MARKS = {"ok": ("✅", "green"), "warn": ("⚠", "yellow"), "bad": ("⚠", "red"), "": ("·", "")}


def plan_text(row: backup_center.PlanRow) -> Text:
    """One automatic backup: its name and result, then what decides it."""
    mark, colour = MARKS.get(row.state, MARKS[""])
    text = Text()
    text.append(f"{mark} ", style=colour)
    text.append(row.name, style="bold")
    for key, value in ((t("Destination"), row.destination), (t("When"), row.when), (t("Kept"), row.keep),
                       (t("Encryption"), row.encrypted), (t("Last run"), row.last)):
        text.append(f"\n  {key}: ", style="dim")
        text.append(value, style=colour if key == t("Last run") else "")
    return text


class BackupCenterView(PlatformSectionView):
    def __init__(self, section):
        super().__init__(section)
        self.scope = ""
        self.codec = ""
        self.facts = None
        self.plans: list[backup_center.PlanRow] = []

    # --- layout ---------------------------------------------------------------
    def heading(self) -> ComposeResult:
        yield from super().heading()
        with HorizontalScroll(id="bk-scopes", classes="sb-card-buttons"):
            yield Label(t("Platform:"), classes="form-label")
            for scope in backup_center.SCOPES:
                yield Button(t(backup_center.SCOPE_LABELS[scope]), id=f"scope-{scope}", classes="small")
        yield Static(t("No platform is installed yet: install Koha, Tainacan or DSpace to back it up. Cloud connections "
                       "can already be added."), id="bk-none", classes="view-prompt", markup=False)
        with Vertical(id="bk-koha"):
            with Grid(classes="status-grid"):
                yield StatusCard(t("Last backup"), id="bk-age")
                yield StatusCard(t("Size"), id="bk-size")
                yield StatusCard(t("Result"), id="bk-result")
            with Vertical(id="bk-codec-box", classes="hub-box"):
                with Horizontal(classes="form-row"):
                    yield Label(t("Compression"), classes="form-label")
                    yield Select([(t(v), k) for k, v in CODECS.items()], value="gz", allow_blank=False,
                                 id="bk-codec", disabled=True)
                yield Label(t(CODEC_NOTE), id="bk-codec-note", classes="ai-note")
        yield Static(t("The selected platforms as a set: the joint backup makes one file with their data, each "
                       "captured in turn with its own consistent copy (not at the same instant), and the assisted "
                       "restore brings back one or several of them. The automatic backups of each are below."),
                     id="bk-both", classes="view-prompt", markup=False)
        yield Static(t("DSpace packages encrypt the database, private configuration, documents and all Solr cores. Schedules, cloud copies and explicit platform sets are managed here."), id="bk-dspace", classes="view-prompt", markup=False)
        with Vertical(id="bk-tainacan"):
            with Grid(classes="status-grid"):
                yield StatusCard(t("Tainacan backups"), id="pstatus-backups")
                yield StatusCard(t("Backup key"), id="pstatus-vault")
            yield Static(t(ENCRYPTION_NOTE), classes="view-prompt", id="encryption-note", markup=False)
        yield Label(t("Automatic backups"), classes="view-prompt", id="bk-plans-title")
        # One block per automatic backup (it wraps on a small terminal,
        # where a six-column table would not fit).
        yield Vertical(id="bk-plans")

    def tag(self, entry) -> str:
        return ""        # the platform is chosen above: no "Koha" tag on each card

    def on_mount(self) -> None:
        self.query_one("#bk-codec-box").border_title = t("Backup compression type")
        super().on_mount()        # hides the cards and titles, then refresh_data()

    def refresh_data(self) -> None:
        # What is installed may have changed since (a platform installed or
        # removed while the panel is open): the platform shown is chosen again.
        self.scope = backup_center.pick_scope(self.scope or getattr(self.app, "backup_scope", ""), self.offered())
        self._show_scope()
        super().refresh_data()

    # --- the platform shown -------------------------------------------------------
    def offered(self) -> list[str]:
        return backup_center.scopes(self.app.platform_ready("koha"), self.app.platform_ready("tainacan"), self.app.platform_ready("dspace"))

    def set_scope(self, scope: str) -> None:
        """Called when a platform group opens the center already filtered."""
        scope = backup_center.pick_scope(scope, self.offered())
        if not self.query("#bk-scopes"):     # just mounted: on_mount shows it
            self.scope = scope
            return
        if scope == self.scope:
            return
        self.scope = scope
        self._show_scope()
        self.refresh_data()

    def _show_scope(self) -> None:
        offered = self.offered()
        for scope in backup_center.SCOPES:
            button = self.query_one(f"#scope-{scope}", Button)
            button.display = scope in offered and len(offered) > 1
            button.variant = "primary" if scope == self.scope else "default"
        self.query_one("#bk-scopes").display = len(offered) > 1
        self.query_one("#bk-none").display = not offered
        self.query_one("#bk-koha").display = self.scope == backup_center.KOHA
        self.query_one("#bk-tainacan").display = self.scope == backup_center.TAINACAN
        self.query_one("#bk-dspace").display = self.scope == backup_center.DSPACE
        self.query_one("#bk-both").display = len(backup_center.MEMBERS.get(self.scope, ())) > 1
        self.query_one("#bk-plans-title").display = bool(self.scope)
        self.query_one("#bk-plans").display = bool(self.scope)
        if self.facts is not None:
            self.show(self.facts)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("scope-"):
            event.stop()
            self.app.backup_scope = bid.removeprefix("scope-")
            self.set_scope(self.app.backup_scope)
            return
        super().on_button_pressed(event)

    def needs_backups(self) -> bool:
        return self.scope in (backup_center.TAINACAN, backup_center.BOTH)

    # --- which cards ----------------------------------------------------------
    def card_shown(self, entry, facts: platforms.Facts) -> bool:
        # A platform's cards in its view; the set's in "both"; the assisted
        # restore wherever a platform is; the cloud connections always.
        if entry.action in ('dspace-plan','dspace-plan-run'):
            return 'dspace' in backup_center.MEMBERS.get(self.scope, ())
        if entry.action == 'set-backup' and len(backup_center.MEMBERS.get(self.scope, ())) > 1:
            return True
        if entry.requires and entry.requires != self.scope:
            return False
        if entry.scope and entry.scope != self.scope:
            return False
        if entry.action == "restore-assisted" and (not self.scope or self.scope == backup_center.DSPACE):
            return False
        return platforms.entry_shown(entry.action, entry.zone, "installed", facts)

    def show(self, facts: platforms.Facts) -> None:
        self.shown_mode = "installed"
        self.query_one("#platform-problem").display = False
        visible: dict[str, bool] = {}
        for card in self.query(ActionCard):
            card.display = self.card_shown(card.entry, facts)
            visible[card.entry.zone] = visible.get(card.entry.zone, False) or card.display
        zones = [z for z in ZONE_ORDER if visible.get(z)]
        for z in ZONE_ORDER:
            for title in self.query(f"#zone-{zone_id(z)}-title"):
                title.display = len(zones) > 1 and visible.get(z, False)
            for grid in self.query(f"#zone-{zone_id(z)}"):
                grid.display = visible.get(z, False)
        if self.scope == backup_center.TAINACAN:
            self.query_one("#pstatus-backups", StatusCard).set(*platforms.describe_backups(facts.backups))
            self.query_one("#pstatus-vault", StatusCard).set(*platforms.describe_vault(facts.backups))

    # --- loading ------------------------------------------------------------------
    async def _load(self) -> None:
        rows: list[backup_center.PlanRow] = []
        try:
            facts = await self.read_facts()
            if self.scope == backup_center.KOHA:
                rows = await self._load_koha()
            elif self.scope == backup_center.TAINACAN:
                rows = await self._load_tainacan(facts)
            elif self.scope == backup_center.BOTH:
                rows = await self._load_koha() + await self._load_tainacan(facts) + await self._load_set()
            if 'dspace' in backup_center.MEMBERS.get(self.scope, ()) and self.app.bridge.has_task('dspace-panel'):
                from ..dspace import payload
                rows += backup_center.operation_plans(payload(await self.app.bridge.task('dspace-panel','operations','plans')),self.scope)
        finally:
            self.query_one("#platform-loader").display = False
        self.facts = facts
        self.show(facts)
        self._draw_plans(rows)

    async def _cloud(self) -> tuple[dict, list[cloud.Plan], list[cloud.History], list[cloud.Remote]]:
        status: dict = {}
        plans: list[cloud.Plan] = []
        history: list[cloud.History] = []
        remotes: list[cloud.Remote] = []
        bridge = self.app.bridge
        try:
            if bridge.has_task("cloud-status"):
                out = await bridge.task("cloud-status")
                status = dict(out.results)
                plans = cloud.parse_plans(out.lists.get("plan", []))
                history = cloud.parse_history(out.lists.get("history", []))
            if bridge.has_task("cloud-list"):
                listed = await bridge.task("cloud-list")
                remotes = cloud.parse_remotes(listed.lists.get("remote", []))
        except Exception:  # noqa: BLE001 - the rows then say what they can
            pass
        return status, plans, history, remotes

    async def _load_koha(self) -> list[backup_center.PlanRow]:
        bridge = self.app.bridge
        try:
            info = await bridge.task("info")
            self._show_codec(info.get("compression", "gz"), info.get("compression_used", ""))
        except Exception:  # noqa: BLE001
            pass
        b: dict = {}
        try:
            b = (await bridge.status()).get("backup", {}) or {}
            self.query_one("#bk-age", StatusCard).set(*backup_card(b))
            self.query_one("#bk-size", StatusCard).set(human_bytes(b.get("last_size")))
            text, state = RESULTS.get(b.get("last_result") or "none", RESULTS["none"])
            note = t("Last nightly backup")
            if b.get("log_epoch"):
                note += " · " + time.strftime("%Y-%m-%d %H:%M", time.localtime(int(b["log_epoch"])))
            self.query_one("#bk-result", StatusCard).set(t(text), note, state)
        except Exception as e:  # noqa: BLE001
            self.query_one("#bk-age", StatusCard).set("-", str(e)[:60], "bad")
        status, plans, history, remotes = await self._cloud()
        if self.app.env.demo:
            cron_file = cron.demo_cloud_jobs(cron.defaults(self.app.env.instance), [p.id for p in plans])
        else:
            # No cron file: nothing is scheduled (never the presets' defaults).
            text = cron.read()
            cron_file = cron.parse(text, self.app.env.instance) if text.strip() else None
        return backup_center.koha_plans(cron_file, status, plans, remotes, history, b)

    async def _load_set(self) -> list[backup_center.PlanRow]:
        bridge = self.app.bridge
        try:
            if bridge.has_task("set-schedule-status"):
                return backup_center.set_plans(dict((await bridge.task("set-schedule-status")).results))
        except Exception:  # noqa: BLE001 - no row rather than a wrong one
            pass
        return []

    async def _load_tainacan(self, facts: platforms.Facts) -> list[backup_center.PlanRow]:
        keep = ""
        bridge = self.app.bridge
        try:
            if bridge.has_task("platform-backup-status"):
                out = await bridge.task("platform-backup-status", "tainacan")
                keep = out.results.get("tainacan.keep", "") if isinstance(out.results, dict) else ""
        except Exception:  # noqa: BLE001
            pass
        _status, _plans, _history, remotes = await self._cloud()
        return backup_center.tainacan_plans(facts.backups, keep, remotes)

    def _draw_plans(self, rows: list[backup_center.PlanRow]) -> None:
        self.plans = rows
        box = self.query_one("#bk-plans", Vertical)
        box.remove_children()
        if not rows:
            box.mount(Static(t("No automatic backup is set up yet."), classes="bk-plan", markup=False))
            return
        box.mount_all(Static(plan_text(row), classes=f"bk-plan -{row.state or 'none'}") for row in rows)

    # --- Koha: the compression of new backups ------------------------------------
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "bk-codec":
            return
        event.stop()
        value = event.value if isinstance(event.value, str) else ""
        if not self.codec or value == self.codec or value not in CODECS:
            return
        self.run_worker(self._set_codec(value), exclusive=True, group="routine", exit_on_error=False)

    async def _set_codec(self, codec: str) -> None:
        from ..routines.common import failed, run_task, show_failure
        title = t("Compression")
        result = await run_task(self.app, t("Saving the backup settings"), "backup-compression", codec)
        if failed(result):
            await show_failure(self.app, title, result)
            self._show_codec(self.codec)
            return
        self._show_codec(codec)
        self.app.notify(t("New backups: ${name}", name=t(CODECS[codec]).split(" · ")[0]))

    def _show_codec(self, codec: str, used: str = "") -> None:
        self.codec = codec if codec in CODECS else "gz"
        select = self.query_one("#bk-codec", Select)
        select.value = self.codec
        select.disabled = False
        note = t(CODEC_NOTE)
        if used and used != self.codec:
            note += "\n" + t("The program for this compression is missing: backups are made with gzip until "
                             "it is installed (choose the compression again to install it).")
        self.query_one("#bk-codec-note", Label).update(note)
