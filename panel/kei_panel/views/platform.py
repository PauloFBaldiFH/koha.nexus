"""The screens of the platform groups and of Shared infrastructure.

PlatformHomeView is the screen a platform group's own row opens (Koha,
Tainacan): one screen whose cards follow the platform's state on this
server (platforms.home_mode):

  absent      installing it (Tainacan: Docker first when it is missing,
              after its own plan and Yes, then Tainacan goes on)
  installed   its tools; removing kept apart, at the end
  failing     the problem in one line, then diagnosis and recovery, then
              the tools. A stopped container never leads to a restore:
              restoring lives in the platform's backups only.
  incomplete  an installation that stopped: install again, the diagnosis,
              the logs, removing

State, addresses and indicators are not repeated here: they live in the
Control Dashboard, in the platform's tab ("State and addresses" leads
there).

PlatformSectionView draws the other screens of the Tainacan group (its
diagnosis and maintenance, events, backups) and Shared infrastructure
(Docker, the web proxy, the backup vault): the same cards, shown or not by
platforms.entry_shown, plus the read-only status cards a screen needs.
Every card runs a routine of routines/platforms.py; the installer checks
everything again.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.widgets import Button, Label, Static, TabbedContent

from .. import platforms
from ..glyphs import split_icon
from ..i18n import t
from ..widgets.cards import ActionCard, StatusCard
from ..widgets.pacman import PacmanLoader
from .base import ZONE_ORDER, SectionView, zone_id

# The read-only cards some screens show above their actions: (id, title).
STATUS_CARDS = {
    "infra": (("proxy", "Web proxy"), ("docker", "Docker"), ("vault", "Backup key")),
    "tainacan-backups": (("backups", "Tainacan backups"),),
}

# What is encrypted in the platform backups, said where the key is made.
ENCRYPTION_NOTE = (
    "What the platform backups encrypt: the configuration (passwords and keys of the platform) with this "
    "server's key, which the recovery phrase opens. The files are encrypted only when they go to a restic "
    "repository, with restic's own password (kept on this server and in the recovery kit). The database is "
    "not encrypted, in the package nor in its cloud copy: keep the backup folder and the cloud account "
    "protected.")


class PlatformSectionView(SectionView):
    def heading(self) -> ComposeResult:
        _icon, title = split_icon(t(self.section.title or self.section.label))
        with Horizontal(classes="view-head"):
            yield Label(title, classes="view-title")
            if self.section.view == "platform-home":
                yield Button(t("State and addresses"), id="home-dashboard", classes="small")
            yield Button(t("Refresh"), id="platform-refresh", classes="small")
        if self.section.prompt:
            yield Label(t(self.section.prompt), classes="view-prompt")
        yield Static("", id="platform-problem", classes="view-prompt platform-problem", markup=False)
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="platform-loader")
        cards = STATUS_CARDS.get(self.section.id, ())
        if cards:
            with Grid(classes="status-grid", id="platform-status"):
                for key, title in cards:
                    yield StatusCard(t(title), id=f"pstatus-{key}")
        if self.section.id == "infra":
            yield Static(t(ENCRYPTION_NOTE), classes="view-prompt", id="encryption-note", markup=False)

    def on_mount(self) -> None:
        # Nothing is offered before the state is read: no card that would
        # only answer "not possible here".
        for card in self.query(ActionCard):
            card.display = False
        for title in self.query(".zone-title"):
            title.display = False
        self.query_one("#platform-problem").display = False
        if self.query("#home-dashboard"):
            self.query_one("#home-dashboard").display = False
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "platform-refresh":
            event.stop()
            self.refresh_data()
        elif event.button.id == "home-dashboard":
            event.stop()
            self.screen.action_show("dashboard")
            try:
                tabs = self.screen.query_one("#dash-tabs", TabbedContent)
                tabs.active = f"dash-tab-{self.section.group}"
            except Exception:  # noqa: BLE001 - the tab is hidden (platform just removed)
                pass

    def refresh_data(self) -> None:
        self.query_one("#platform-loader").display = True
        self.run_worker(self._load(), exclusive=True, group=f"platform-{self.section.id}", exit_on_error=False)

    def needs_backups(self) -> bool:
        return self.section.id in ("infra", "tainacan-backups", "tainacan")

    async def read_facts(self) -> platforms.Facts:
        app = self.app
        try:
            status = await app.bridge.status()
        except Exception:  # the cards then say "not checked"; never a crash
            status = {}
        status = status if isinstance(status, dict) else {}
        app.platforms_seen(status)
        backups = platforms.BackupState()
        if self.needs_backups() and app.bridge.has_task("platform-backup-status"):
            try:
                out = await app.bridge.task("platform-backup-status", "tainacan")
                backups = platforms.backup_from_results(out.results)
            except Exception:  # "not checked"
                backups = platforms.BackupState()
        return platforms.Facts(status=status, koha=app.koha_installed,
                               tainacan=platforms.tainacan_from_status(status),
                               docker=platforms.docker_from_status(status), backups=backups,
                               has_task=app.bridge.has_task)

    def mode(self, facts: platforms.Facts) -> str:
        return "installed"

    def problem(self, facts: platforms.Facts, mode: str) -> str:
        return ""

    async def _load(self) -> None:
        try:
            facts = await self.read_facts()
        finally:
            self.query_one("#platform-loader").display = False
        self.facts = facts
        self.show(facts)

    def show(self, facts: platforms.Facts) -> None:
        mode = self.mode(facts)
        self.shown_mode = mode
        problem = self.problem(facts, mode)
        label = self.query_one("#platform-problem", Static)
        label.update(problem)
        label.display = bool(problem)
        label.set_class(mode in ("failing", "incomplete"), "-warn")
        if self.query("#home-dashboard"):
            self.query_one("#home-dashboard").display = mode in ("installed", "failing")
        visible: dict[str, bool] = {}
        for card in self.query(ActionCard):
            e = card.entry
            card.display = platforms.entry_shown(e.action, e.zone, mode, facts)
            visible[e.zone] = visible.get(e.zone, False) or card.display
        zones = [z for z in ZONE_ORDER if visible.get(z)]
        for z in ZONE_ORDER:
            for title in self.query(f"#zone-{zone_id(z)}-title"):
                title.display = len(zones) > 1 and visible.get(z, False)
            for grid in self.query(f"#zone-{zone_id(z)}"):
                grid.display = visible.get(z, False)
        self.show_status(facts)

    def show_status(self, facts: platforms.Facts) -> None:
        if self.section.id == "infra":
            self.query_one("#pstatus-proxy", StatusCard).set(
                *platforms.describe_proxy(platforms.proxy_from_status(facts.status)))
            self.query_one("#pstatus-docker", StatusCard).set(*platforms.describe_docker(facts.docker))
            self.query_one("#pstatus-vault", StatusCard).set(*platforms.describe_vault(facts.backups))
        elif self.section.id == "tainacan-backups":
            self.query_one("#pstatus-backups", StatusCard).set(*platforms.describe_backups(facts.backups))


class PlatformHomeView(PlatformSectionView):
    """A platform's home: the group's own row in the sidebar."""

    def mode(self, facts: platforms.Facts) -> str:
        return platforms.home_mode(self.section.group, facts)

    def problem(self, facts: platforms.Facts, mode: str) -> str:
        if self.section.group == platforms.KOHA:
            return platforms.koha_problem(facts)
        return platforms.tainacan_problem(facts)
