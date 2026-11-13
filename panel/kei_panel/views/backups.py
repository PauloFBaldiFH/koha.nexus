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

import dataclasses
import time

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from rich.text import Text
from textual.widgets import Collapsible, Label, Select, Static

from .. import backup_center, cloud, cron, names, platforms
from ..backup_center import DSPACE_CODECS, TAINACAN_CODECS
from ..i18n import t
from ..menus import Entry
from ..widgets.cards import ActionCard, StatusCard
from .backup import CODEC_NOTE, CODECS, RESULTS
from .base import ZONE_ORDER, zone_id
from .dashboard import backup_card, human_bytes
from .platform import ENCRYPTION_NOTE, PlatformSectionView


READING = "Reading the backup state… The actions below can already be used; each one checks the server first."
READ_FAILED = ("Part of the backup state could not be read (${what}). The actions stay available: each one checks "
               "the server again before doing anything. Use Refresh to read again.")

# One place for the backup key and its recovery kit (study 7.5, U8): the key
# is shared by the encrypted backups of Tainacan, DSpace and the full Nexus
# backup, so the center shows it once instead of a card per system.
KEY_NOTE = "Shared by the encrypted backups of Tainacan, DSpace and the full Nexus backup."
KEY_ENTRIES = (Entry("🔐  Set up encrypted backups", "pbackup-setup", kind="native"),
               Entry("🧰  Recovery kit", "pbackup-kit", kind="native"))
# The cards of each system that did the same: inside the key box instead.
KEY_ACTIONS = frozenset({"dspace-backup-key", "pbackup-setup", "pbackup-kit", "nexus-backup-key", "nexus-backup-kit"})

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


def brings_back_text() -> Text:
    """The table of the full backup (study 7.6): each part and what a
    recovery does with it, a bold title over its wrapped text."""
    from ..routines.nexus_backup import BRINGS_BACK
    text = Text()
    for n, (title, what) in enumerate(BRINGS_BACK):
        if n:
            text.append("\n")
        text.append(t(title), style="bold")
        text.append("\n  " + t(what))
    return text


class BackupCenterView(PlatformSectionView):
    def __init__(self, section):
        super().__init__(section)
        self.scope = ""
        self.codec = ""
        self.dspace_codec = ""
        self.tainacan_codec = ""
        self.nexus_codec = ""
        self.facts = None
        self.plans: list[backup_center.PlanRow] = []

    # --- layout ---------------------------------------------------------------
    def compose(self) -> ComposeResult:
        # The actions come right after the platform choice (study 2.1): the
        # state, settings and automatic backups follow them, so reading them
        # never pushes a button down.
        yield from self.heading()
        yield from self.cards()
        yield from self.details()

    def heading(self) -> ComposeResult:
        yield from super().heading()
        # One compact choice instead of a button per combination (study 7.5).
        with Horizontal(id="bk-scopes", classes="form-row"):
            yield Label(t("Show:"), classes="form-label")
            offered = self.offered() or list(backup_center.SCOPES)
            first = backup_center.pick_scope(self.scope or getattr(self.app, "backup_scope", ""), offered)
            select = Select([(self.scope_label(s), s) for s in offered],
                            value=first if first in offered else offered[0], allow_blank=False, id="bk-scope")
            select.offered = offered
            yield select
        yield Static(t("No platform is installed yet: install Koha, Tainacan or DSpace to back it up. Cloud connections "
                       "can already be added."), id="bk-none", classes="view-prompt", markup=False)
        yield Static(t(READING), id="bk-wait", classes="view-prompt bk-wait", markup=False)

    def details(self) -> ComposeResult:
        yield Label(t("State and settings"), classes="view-prompt bk-section-title", id="bk-details-title")
        with Vertical(id="bk-koha"):
            with Grid(classes="status-grid"):
                yield StatusCard(t("Last backup"), id="bk-age")
                yield StatusCard(t("Size"), id="bk-size")
                yield StatusCard(t("Result"), id="bk-result")
            with Collapsible(title=t("Compression"), id="bk-codec-more", classes="bk-more"):
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
        with Vertical(id="bk-dspace"):
            with Grid(classes="status-grid"):
                yield StatusCard(t("Last backup"), id="bk-ds-age")
                yield StatusCard(t("Size"), id="bk-ds-size")
                yield StatusCard(t("Recovery packages"), id="bk-ds-count")
            with Collapsible(title=t("What these backups contain"), id="bk-ds-about", classes="bk-more"):
                yield Static(t("DSpace packages encrypt the database, private configuration, documents and all Solr cores. Schedules, cloud copies and explicit platform sets are managed here."), classes="view-prompt", markup=False)
                yield Static(t("Container images are not included in these individual packages. Keep the matching images available for recovery on another server."), classes="view-prompt", markup=False)
            with Collapsible(title=t("Compression"), id="bk-ds-codec-more", classes="bk-more"):
                with Vertical(classes="hub-box", id="bk-ds-codec-box"):
                    with Horizontal(classes="form-row"):
                        yield Label(t("Compression"), classes="form-label")
                        yield Select([(t(label), key) for key, label in DSPACE_CODECS.items()], value="gz",
                                     allow_blank=False, id="bk-ds-codec", disabled=True)
                    yield Label(t("Used for new manual, scheduled and safety backups of DSpace. Compression runs after services resume; every package remains encrypted. Existing packages keep their format."), classes="ai-note")
        with Vertical(id="bk-tainacan"):
            with Grid(classes="status-grid"):
                yield StatusCard(t("Last backup"), id="bk-tn-age")
                yield StatusCard(t("Size"), id="bk-tn-size")
                yield StatusCard(t("Recovery packages"), id="pstatus-backups")
            with Collapsible(title=t("Compression"), id="bk-tn-codec-more", classes="bk-more"):
                with Vertical(id="bk-tn-codec-box", classes="hub-box"):
                    with Horizontal(classes="form-row"):
                        yield Label(t("Compression"), classes="form-label")
                        yield Select([(t(label), key) for key, label in TAINACAN_CODECS.items()], value="gz",
                                     allow_blank=False, id="bk-tn-codec", disabled=True)
                    yield Label(t("Used for new Tainacan manual, scheduled and safety backups. Additional compression runs after WordPress resumes. Existing backups keep their format. Restic controls compression inside its own repository."), classes="ai-note")
        with Vertical(id="bk-nexus"):
            from ..routines.nexus_backup import SHORT_NOTE
            yield Static(t(SHORT_NOTE), classes="view-prompt", markup=False)
            with Grid(classes="status-grid"):
                yield StatusCard(t("Last full backup"), id="bk-nexus-age")
                yield StatusCard(t("Size"), id="bk-nexus-size")
                yield StatusCard(t("Recovery sessions"), id="bk-nexus-sessions")
            # What a recovery does with each part, open from the start (study 7.6).
            with Collapsible(title=t("What this backup brings back"), id="bk-nexus-back", collapsed=False,
                             classes="bk-more"):
                yield Static(brings_back_text(), id="bk-nexus-table", markup=False)
            with Collapsible(title=t("Compression"), id="bk-nexus-codec-more", classes="bk-more"):
                with Vertical(classes="hub-box"):
                    with Horizontal(classes="form-row"):
                        yield Label(t("Compression"), classes="form-label")
                        yield Select([(t(label), key) for key, label in DSPACE_CODECS.items()], value="gz",
                                     allow_blank=False, id="bk-nexus-codec", disabled=True)
        with Vertical(id="bk-key", classes="hub-box"):
            yield Label("", id="bk-key-state", markup=False)
            yield Static(t(KEY_NOTE), classes="view-prompt", markup=False)
            with Grid(classes="card-grid", id="bk-key-cards"):
                for entry in KEY_ENTRIES:
                    card = ActionCard(entry)
                    card.add_class("bk-key-card")
                    yield card
            with Collapsible(title=t("What is encrypted"), id="bk-key-more", classes="bk-more"):
                yield Static(t(ENCRYPTION_NOTE), classes="view-prompt", id="encryption-note", markup=False)
        yield Label(t("Automatic backups"), classes="view-prompt", id="bk-plans-title")
        # One block per automatic backup (it wraps on a small terminal,
        # where a six-column table would not fit).
        yield Vertical(id="bk-plans")

    def tag(self, entry) -> str:
        return ""        # the platform is chosen above: no "Koha" tag on each card

    def on_mount(self) -> None:
        self.query_one("#bk-key").border_title = t("Backup key and recovery kit")
        self.query_one("#bk-codec-box").border_title = t("Backup compression type")
        self.query_one("#bk-tn-codec-box").border_title = t("Backup compression type")
        self.query_one("#bk-ds-codec-box").border_title = t("Backup compression type")
        super().on_mount()        # hides the cards and titles, then refresh_data()
        # Drawn at once from what is already known; usable when the read ends.
        self.show(self.facts or self.known_facts())
        self._waiting(True)

    def known_facts(self) -> platforms.Facts:
        """What the panel knows before reading: installed platforms and tasks."""
        return platforms.Facts(status={}, koha=self.app.koha_installed, has_task=self.app.bridge.has_task)

    def _waiting(self, on: bool, failed: str = "") -> None:
        # The cards stay usable while reading: each routine checks the server
        # again before doing anything, so waiting here would only slow people.
        note = self.query_one("#bk-wait", Static)
        if on:
            note.update(t(READING))
        elif failed:
            note.update(t(READ_FAILED, what=failed))
        else:
            note.update(t("State read at ${time}.", time=time.strftime("%H:%M")))
        note.set_class(bool(failed) and not on, "-warn")

    def refresh_data(self) -> None:
        # What is installed may have changed since (a platform installed or
        # removed while the panel is open): the platform shown is chosen again.
        self.scope = backup_center.pick_scope(self.scope or getattr(self.app, "backup_scope", ""), self.offered())
        self._show_scope()
        if self.query("#bk-wait"):
            self._waiting(True)
        super().refresh_data()

    # --- the platform shown -------------------------------------------------------
    def offered(self) -> list[str]:
        offered = backup_center.scopes(self.app.platform_ready("koha"), self.app.platform_ready("tainacan"), self.app.platform_ready("dspace"))
        if self.app.bridge.has_task('nexus-full'):
            offered.append(backup_center.NEXUS)
        return offered

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
        select = self.query_one("#bk-scope", Select)
        if offered and getattr(select, "offered", None) != offered:
            select.offered = offered
            with select.prevent(Select.Changed):
                select.set_options([(self.scope_label(s), s) for s in offered])
        if self.scope in offered and select.value != self.scope:
            with select.prevent(Select.Changed):
                select.value = self.scope
        self.query_one("#bk-scopes").display = len(offered) > 1
        self.query_one("#bk-none").display = not offered
        self.query_one("#bk-koha").display = self.scope == backup_center.KOHA
        self.query_one("#bk-tainacan").display = self.scope == backup_center.TAINACAN
        self.query_one("#bk-dspace").display = self.scope == backup_center.DSPACE
        self.query_one("#bk-nexus").display = self.scope == backup_center.NEXUS
        self.query_one("#bk-key").display = self.needs_backups()
        self.query_one("#bk-both").display = len(backup_center.MEMBERS.get(self.scope, ())) > 1
        self.query_one("#bk-details-title").display = bool(self.scope)
        self.query_one("#bk-plans-title").display = bool(self.scope) and self.scope != backup_center.NEXUS
        self.query_one("#bk-plans").display = bool(self.scope) and self.scope != backup_center.NEXUS
        self.show(self.facts or self.known_facts())

    def choose_scope(self, scope: str) -> None:
        self.app.backup_scope = scope
        self.set_scope(scope)

    def needs_backups(self) -> bool:
        """The shared key's state is read where a system uses it."""
        members = backup_center.MEMBERS.get(self.scope, ())
        return self.scope == backup_center.NEXUS or "tainacan" in members or "dspace" in members

    # --- which cards ----------------------------------------------------------
    def card_shown(self, entry, facts: platforms.Facts) -> bool:
        # A platform's cards in its view; the set's in "both"; the assisted
        # restore wherever a platform is; the cloud connections always.
        # The key's cards are in the key box only.
        if entry.action in KEY_ACTIONS:
            return False
        if self.scope == backup_center.NEXUS:
            return entry.scope == 'nexus' or entry.action == 'cloud-connections'
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
            if card.has_class("bk-key-card"):
                continue
            card.display = self.card_shown(card.entry, facts)
            visible[card.entry.zone] = visible.get(card.entry.zone, False) or card.display
        self._show_key(facts.backups)
        zones = [z for z in ZONE_ORDER if visible.get(z)]
        for z in ZONE_ORDER:
            for title in self.query(f"#zone-{zone_id(z)}-title"):
                title.display = len(zones) > 1 and visible.get(z, False)
            for grid in self.query(f"#zone-{zone_id(z)}"):
                grid.display = visible.get(z, False)
        if self.scope == backup_center.TAINACAN:
            backup = facts.backups
            tested = backup.verified.split()
            note = t('last restore test passed') if tested[-1:] == ['ok'] else t('last restore test failed') if tested else t('no restore test yet')
            self.query_one("#pstatus-backups", StatusCard).set(str(backup.count) if backup.known else '-', note, 'ok' if tested[-1:] == ['ok'] else 'warn')

    def _show_key(self, backup: platforms.BackupState) -> None:
        """The key box: its state, then set it up (no key yet) or save the
        kit (a key exists). Unread: setting up is offered, it checks first."""
        value, detail, state = platforms.describe_vault(backup)
        line = self.query_one("#bk-key-state", Label)
        line.update(f"{t('Backup key')}: {value} · {detail}")
        line.set_class(state == "ok", "-ok")
        line.set_class(state == "warn", "-warn")
        boxed = self.needs_backups()
        for card in self.query(".bk-key-card"):
            card.display = boxed and (bool(backup.key) if card.entry.action == "pbackup-kit" else not backup.key)

    # --- loading ------------------------------------------------------------------
    async def _load(self) -> None:
        rows: list[backup_center.PlanRow] = []
        failed: list[str] = []
        facts = None

        async def part(name, read):
            try:
                return await read()
            except Exception:  # noqa: BLE001 - one read failing never hides the actions
                failed.append(t(name))
                return None

        try:
            facts = await part("server state", self.read_facts)
            if facts is not None:
                if self.scope == backup_center.KOHA:
                    rows = await part("Koha backups", self._load_koha) or []
                elif self.scope == backup_center.TAINACAN:
                    rows = await part("Tainacan backups", lambda: self._load_tainacan(facts)) or []
                elif self.scope == backup_center.BOTH:
                    for name, read in (("Koha backups", self._load_koha),
                                       ("Tainacan backups", lambda: self._load_tainacan(facts)),
                                       ("joint backup", self._load_set)):
                        rows += await part(name, read) or []
            if self.scope == backup_center.DSPACE:
                await part("DSpace backups", self._load_dspace)
            if self.scope == backup_center.NEXUS:
                await part("full backup", self._load_nexus)
            if 'dspace' in backup_center.MEMBERS.get(self.scope, ()) and self.app.bridge.has_task('dspace-panel'):
                from ..dspace import payload

                async def dspace_plans():
                    out = await self.app.bridge.task('dspace-panel', 'operations', 'plans')
                    return backup_center.operation_plans(payload(out), self.scope)
                rows += await part("DSpace backup plans", dspace_plans) or []
        finally:
            self.query_one("#platform-loader").display = False
            facts = facts or self.facts or self.known_facts()
            self.facts = facts
            self.show(facts)
            self._waiting(False, ", ".join(failed))
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
                codec = out.get("tainacan.compression", "")
                if codec in TAINACAN_CODECS and bridge.has_task('platform-backup-compression'):
                    self._show_tainacan_codec(codec)
                else:
                    self.tainacan_codec = ""
                    self.query_one('#bk-tn-codec', Select).disabled = True
                newest = out.get('tainacan.last', '').split('|')
                self.query_one('#bk-tn-age', StatusCard).set(newest[1] if len(newest) > 1 else t('None yet'), '')
                size = out.get('tainacan.last_bytes', '')
                self.query_one('#bk-tn-size', StatusCard).set(human_bytes(int(size)) if size.isdigit() else '-', t('Restic snapshot excluded') if facts.backups.repo else t('Package on this server'))
        except Exception:  # noqa: BLE001
            self.query_one('#bk-tn-codec', Select).disabled = True
            self.tainacan_codec = ""
            for key in ('age', 'size'):
                self.query_one('#bk-tn-' + key, StatusCard).set(t('Unavailable'), '', 'warn')
        _status, _plans, _history, remotes = await self._cloud()
        return backup_center.tainacan_plans(facts.backups, keep, remotes)

    async def _load_dspace(self) -> None:
        from ..dspace import payload
        try:
            out = await self.app.bridge.task('dspace-panel', 'backup-list')
            data = payload(out) if out.ok else {}
            if not data or data.get('compression') not in DSPACE_CODECS:
                raise ValueError('Backup inventory unavailable')
            details = data.get('details', [])
            if not isinstance(details, list) or any(not isinstance(v, dict) for v in details):
                raise ValueError('Invalid backup inventory')
            newest = details[0] if details else {}
            epoch = int(newest.get('modified_at') or 0)
            self.query_one('#bk-ds-age', StatusCard).set(
                time.strftime('%Y-%m-%d %H:%M', time.localtime(epoch)) if epoch else t('None yet'),
                t('Test recovery to verify the package.') if epoch else '', '')
            self.query_one('#bk-ds-size', StatusCard).set(human_bytes(newest.get('bytes')), t('Encrypted archive'), '')
            self.query_one('#bk-ds-count', StatusCard).set(str(len(details)), str(data.get('directory', '')), '')
            self._show_dspace_codec(data['compression'])
        except Exception:
            for key in ('age', 'size', 'count'):
                self.query_one('#bk-ds-' + key, StatusCard).set(t('Unavailable'), t('Refresh or check the DSpace diagnosis.'), 'warn')
            self.query_one('#bk-ds-codec', Select).disabled = True

    def scope_label(self, scope: str) -> str:
        """The choice of a system by its visible name (U6): "Biblioteca
        Central · Koha", "Biblioteca Central + Museu Municipal"."""
        fallback = t(backup_center.SCOPE_LABELS[scope])
        members = backup_center.MEMBERS.get(scope, ())
        known = names.of(self.app)
        if scope == backup_center.NEXUS or not members:
            return fallback
        if len(members) == 1:
            return names.label(known, members[0]) if names.custom(known, members[0]) else fallback
        return names.joined(known, members, fallback)

    def _named(self, rows: list[backup_center.PlanRow]) -> list[backup_center.PlanRow]:
        """The plans of one named system say whose they are."""
        members = backup_center.MEMBERS.get(self.scope, ())
        name = names.custom(names.of(self.app), members[0]) if len(members) == 1 else ""
        return [dataclasses.replace(row, name=f"{name} · {row.name}") for row in rows] if name else rows

    def names_changed(self) -> None:
        try:
            select = self.query_one("#bk-scope", Select)
        except Exception:  # noqa: BLE001 - not composed yet
            return
        select.offered = None             # the choices are written again
        self._show_scope()
        if getattr(self, "_raw_plans", None) is not None:
            self._draw_plans(self._raw_plans)

    def _draw_plans(self, rows: list[backup_center.PlanRow]) -> None:
        self._raw_plans = rows
        rows = self._named(rows)
        title = t("Automatic backups") + (f" ({len(rows)})" if rows else "")
        self.query_one("#bk-plans-title", Label).update(title)
        box = self.query_one("#bk-plans", Vertical)
        if rows == self.plans and box.children:
            return                    # nothing changed: nothing is rebuilt
        self.plans = rows
        box.remove_children()
        if not rows:
            box.mount(Static(t("No automatic backup is set up yet."), classes="bk-plan", markup=False))
            return
        box.mount_all(Static(plan_text(row), classes=f"bk-plan -{row.state or 'none'}") for row in rows)

    # --- Koha: the compression of new backups ------------------------------------
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == 'bk-scope':
            event.stop()
            if isinstance(event.value, str) and event.value != self.scope and event.value in self.offered():
                self.choose_scope(event.value)
            return
        if event.select.id == 'bk-nexus-codec':
            event.stop()
            value = event.value if isinstance(event.value, str) else ''
            if self.nexus_codec and value != self.nexus_codec and value in DSPACE_CODECS:
                self.run_worker(self._set_nexus_codec(value), exclusive=True, group='routine', exit_on_error=False)
            return
        if event.select.id == 'bk-tn-codec':
            event.stop()
            value = event.value if isinstance(event.value, str) else ''
            if self.tainacan_codec and value != self.tainacan_codec and value in TAINACAN_CODECS:
                self.run_worker(self._set_tainacan_codec(value), exclusive=True, group='routine', exit_on_error=False)
            return
        if event.select.id == 'bk-ds-codec':
            event.stop()
            value = event.value if isinstance(event.value, str) else ''
            if self.dspace_codec and value != self.dspace_codec and value in DSPACE_CODECS:
                self.run_worker(self._set_dspace_codec(value), exclusive=True, group='routine', exit_on_error=False)
            return
        if event.select.id != "bk-codec":
            return
        event.stop()
        value = event.value if isinstance(event.value, str) else ""
        if not self.codec or value == self.codec or value not in CODECS:
            return
        self.run_worker(self._set_codec(value), exclusive=True, group="routine", exit_on_error=False)

    async def _load_nexus(self) -> None:
        from ..dspace import payload
        try:
            out = await self.app.bridge.task('nexus-full', 'status')
            data = payload(out) if out.ok else {}
            if data.get('compression') not in DSPACE_CODECS:
                raise ValueError('Full backup status unavailable')
            epoch = data.get('created')
            stamp = time.strftime('%Y-%m-%d %H:%M', time.localtime(epoch)) if isinstance(epoch, (int, float)) else t('None yet')
            self.query_one('#bk-nexus-age', StatusCard).set(stamp, str(data.get('file') or ''))
            self.query_one('#bk-nexus-size', StatusCard).set(human_bytes(data.get('bytes')), t('Encrypted portable package'))
            self.query_one('#bk-nexus-sessions', StatusCard).set(str(len(data.get('sessions', []))), t('Private decrypted staging; review or resume explicitly'))
            self._show_nexus_codec(data['compression'])
        except Exception:
            self.nexus_codec = ''
            self.query_one('#bk-nexus-codec', Select).disabled = True
            for key in ('age', 'size', 'sessions'):
                self.query_one('#bk-nexus-' + key, StatusCard).set(t('Unavailable'), t('Refresh or check the task log.'), 'warn')

    def _codec_title(self, box: str, name: str) -> None:
        self.query_one(box, Collapsible).title = f"{t('Compression')}: {t(name).split(' · ')[0]}"

    def _show_nexus_codec(self, codec: str) -> None:
        self._codec_title("#bk-nexus-codec-more", DSPACE_CODECS[codec])
        self.nexus_codec = codec
        self.app.nexus_backup_codec = codec
        select = self.query_one('#bk-nexus-codec', Select)
        select.value = codec
        select.disabled = False

    async def _set_nexus_codec(self, codec: str) -> None:
        from ..routines.nexus_backup import call
        previous = self.nexus_codec
        self.query_one('#bk-nexus-codec', Select).disabled = True
        result = await call(self.app, 'settings', '--compression', codec, '--confirm')
        self._show_nexus_codec(codec if result and result.get('compression') == codec else previous)

    def _show_tainacan_codec(self, codec: str) -> None:
        self._codec_title("#bk-tn-codec-more", TAINACAN_CODECS[codec])
        self.tainacan_codec = codec
        select = self.query_one('#bk-tn-codec', Select)
        select.value = codec
        select.disabled = False

    async def _set_tainacan_codec(self, codec: str) -> None:
        from ..routines.common import failed, run_task, show_failure
        previous = self.tainacan_codec
        self.query_one('#bk-tn-codec', Select).disabled = True
        result = await run_task(self.app, t('Saving the backup settings'), 'platform-backup-compression', 'tainacan', codec)
        if failed(result) or result.get('compression', '') != codec:
            await show_failure(self.app, t('Compression'), result)
            self._show_tainacan_codec(previous)
            return
        self._show_tainacan_codec(codec)
        self.app.notify(t('New backups: ${name}', name=t(TAINACAN_CODECS[codec])))

    def _show_dspace_codec(self, codec: str) -> None:
        self._codec_title("#bk-ds-codec-more", DSPACE_CODECS[codec])
        self.dspace_codec = codec
        select = self.query_one('#bk-ds-codec', Select)
        select.value = codec
        select.disabled = False

    async def _set_dspace_codec(self, codec: str) -> None:
        from ..routines.dspace import call
        previous = self.dspace_codec
        self.query_one('#bk-ds-codec', Select).disabled = True
        result = await call(self.app, 'backup-settings', '--compression', codec, '--confirm')
        if result is not None and result.get('compression') == codec:
            self._show_dspace_codec(codec)
            self.app.notify(t('New backups: ${name}', name=t(DSPACE_CODECS[codec])))
        else:
            self._show_dspace_codec(previous)

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
        self._codec_title("#bk-codec-more", CODECS[self.codec])
        select = self.query_one("#bk-codec", Select)
        select.value = self.codec
        select.disabled = False
        note = t(CODEC_NOTE)
        if used and used != self.codec:
            note += "\n" + t("The program for this compression is missing: backups are made with gzip until "
                             "it is installed (choose the compression again to install it).")
        self.query_one("#bk-codec-note", Label).update(note)
