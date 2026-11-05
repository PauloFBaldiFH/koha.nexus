"""PlatformsView: the platforms this panel knows, one card each.

Read only. Each card keeps the four facts apart (platforms.py): supported
by this panel, installation detected, services, functional health (not
verified yet). Koha keeps its own "Install Koha server" entry. Docker and
Tainacan can be installed from here: the installer's plan is shown first
and nothing happens without a Yes. Tainacan's card also has its diagnosis,
backup, restore (tested first in an isolated copy) and uninstall; AtoM and
DSpace are planned.
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Label

from .. import platforms
from ..glyphs import split_icon
from ..i18n import t
from ..widgets.cards import StatusCard
from ..widgets.pacman import PacmanLoader
from .base import SectionView


class PlatformsView(SectionView):
    def compose(self) -> ComposeResult:
        _icon, title = split_icon(t(self.section.title or self.section.label))
        with Horizontal(classes="view-head"):
            yield Label(title, classes="view-title")
            yield Button(t("Refresh"), id="platforms-refresh", classes="small")
        yield Label(t(self.section.prompt), classes="view-prompt")
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="platforms-loader")
        with Grid(classes="status-grid", id="platform-cards"):
            for p in platforms.CATALOG:
                yield StatusCard(f"{p.name}: {t(p.role)}", id=f"platform-{p.id}")
            yield StatusCard(t("Web proxy"), id="platform-proxy")
            yield StatusCard("Docker", id="platform-docker")
        with Horizontal(classes="form-buttons"):
            yield Button(t("Install Docker"), id="platforms-docker-install", classes="small")
            yield Button(t("Remove Docker"), id="platforms-docker-remove", classes="small")
        with Horizontal(classes="form-buttons", id="platforms-tainacan-buttons"):
            for key, label in TAINACAN_BUTTONS:
                yield Button(t(label), id=f"tainacan-{key}", classes="small")

    def on_mount(self) -> None:
        self.query_one("#platforms-docker-install").display = False
        self.query_one("#platforms-docker-remove").display = False
        for key, _label in TAINACAN_BUTTONS:
            self.query_one(f"#tainacan-{key}").display = False
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "platforms-refresh":
            event.stop()
            self.refresh_data()
        elif event.button.id == "platforms-docker-install":
            event.stop()
            self.app.run_worker(self.install_docker(), group="routine", exclusive=True, exit_on_error=False)
        elif event.button.id == "platforms-docker-remove":
            event.stop()
            self.app.run_worker(self.remove_docker(), group="routine", exclusive=True, exit_on_error=False)
        elif event.button.id and event.button.id.startswith("tainacan-"):
            event.stop()
            action = getattr(self, "tainacan_" + event.button.id[len("tainacan-"):].replace("-", "_"))
            self.app.run_worker(action(), group="routine", exclusive=True, exit_on_error=False)

    def refresh_data(self) -> None:
        self.query_one("#platforms-loader").display = True
        self.run_worker(self._load(), exclusive=True, group="platforms", exit_on_error=False)

    async def _load(self) -> None:
        try:
            status = await self.app.bridge.status()
        except Exception:  # the cards then say "not checked"; never a crash
            status = {"koha_installed": self.app.koha_installed}
        finally:
            self.query_one("#platforms-loader").display = False
        self.show(platforms.from_status(status))
        self.query_one("#platform-proxy", StatusCard).set(
            *platforms.describe_proxy(platforms.proxy_from_status(status)))
        docker = platforms.docker_from_status(status)
        self.query_one("#platform-docker", StatusCard).set(*platforms.describe_docker(docker))
        self.query_one("#platforms-docker-install").display = (
            platforms.docker_can_install(docker) and self.app.bridge.has_task("docker-plan"))
        self.query_one("#platforms-docker-remove").display = (
            platforms.docker_can_remove(docker) and self.app.bridge.has_task("docker-remove"))
        tainacan = platforms.tainacan_from_status(status)
        self.query_one("#platform-tainacan", StatusCard).set(*platforms.describe_tainacan(tainacan, docker))
        has = self.app.bridge.has_task("tainacan-status")
        self.query_one("#tainacan-install").display = has and platforms.tainacan_can_install(tainacan, docker)
        for key, _label in TAINACAN_BUTTONS[1:]:
            self.query_one(f"#tainacan-{key}").display = has and platforms.tainacan_installed(tainacan)
        self.app.platforms_seen(status)

    async def install_docker(self) -> None:
        """The installer's plan, then the person's Yes, then the install."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen, MessageScreen

        title = t("Install Docker")
        plan = await self.app.bridge.task("docker-plan")
        kind, note = plan.get("plan"), plan.get("note")
        if kind == "use":
            self.app.notify(note or t("Docker is already installed."))
            self.refresh_data()
            return
        if kind != "install":
            await self.app.push_screen_wait(MessageScreen(title, note or t("Docker cannot be installed here."),
                                                          kind="error"))
            return
        labels = (("repository", t("Repository")), ("key", t("Key")), ("source", t("Package source")),
                  ("packages", t("Packages")), ("service", t("Service")), ("kept", ""), ("firewall", ""),
                  ("undo", ""))
        steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                          for key, label in labels if plan.get(key))
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Install Docker now? No platform is installed with it."), preview=steps,
                preview_title=t("What will change on this server"))):
            return
        result = await run_task(self.app, title, "docker-install", "confirm")
        await show_done(self.app, title, result, t("Docker is installed."))
        self.refresh_data()

    async def remove_docker(self) -> None:
        """Only a Docker Koha.Nexus installed; the installer refuses while
        anything of anyone is in it."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen

        title = t("Remove Docker")
        if not await self.app.push_screen_wait(ConfirmScreen(title, t(
                "Remove Docker, which Koha.Nexus installed? Nothing is left in it. "
                "Its images in /var/lib/docker are kept."), danger=True)):
            return
        result = await run_task(self.app, title, "docker-remove", "confirm")
        await show_done(self.app, title, result, t("Docker was removed."))
        self.refresh_data()

    def show(self, states: list[platforms.PlatformState]) -> None:
        for state in states:
            if state.id != "tainacan":     # its own card text (_load)
                self.query_one(f"#platform-{state.id}", StatusCard).set(*platforms.describe(state))

    # Tainacan: every action is a task of the installer, which checks
    # everything again (the buttons only follow --status-json).
    async def tainacan_install(self) -> None:
        """An address (or the server's own), the plan, a Yes, the install."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen, InputScreen, MessageScreen

        title = t("Install Tainacan")

        def check(value: str) -> str:
            if not value or re.fullmatch(r"https?://[a-z0-9.-]+(:[0-9]{1,5})?/?", value):
                return ""
            return t("Use http://name or https://name, with no path, or leave it empty.")

        address = await self.app.push_screen_wait(InputScreen(
            title, t("Leave it empty to reach Tainacan by this server's address on the local network "
                     "(a port of its own). Or type the name it will have, such as http://acervo.example.org: "
                     "the name must point to this server."), t("Address (optional)"), validate=check))
        if address is None:
            return
        address = address.rstrip("/")
        plan = await self.app.bridge.task("tainacan-plan", *([address] if address else []))
        if plan.get("plan") != "install":
            await self.app.push_screen_wait(MessageScreen(
                title, plan.get("note") or t("Tainacan cannot be installed here."), kind="error"))
            return
        labels = (("address", t("Address")), ("web", t("Web")), ("apache", ""), ("images", t("Images")),
                  ("plugin", t("Plugin")), ("network", t("Network")), ("data", t("Data")), ("reuse", ""),
                  ("updates", ""), ("kept", ""), ("undo", ""))
        steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                          for key, label in labels if plan.get(key))
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Install Tainacan now? It takes a few minutes."), preview=steps,
                preview_title=t("What will change on this server"))):
            return
        args = ["confirm"] + ([plan.get("address")] if plan.get("address") else [])
        result = await run_task(self.app, title, "tainacan-install", *args)
        await show_done(self.app, title, result, t("Tainacan is installed."))
        self.refresh_data()

    async def tainacan_status(self) -> None:
        """The installer's diagnosis, as a list."""
        from ..screens.dialogs import TextScreen

        out = await self.app.bridge.task("tainacan-status")
        labels = (("status", t("Status")), ("url", t("Address")), ("health", t("Health")), ("reason", t("Reason")),
                  ("db", t("Database")), ("wordpress", "WordPress"), ("wordpress_version", t("WordPress version")),
                  ("tainacan_version", t("Tainacan version")), ("images_pinned", t("Images as fixed")),
                  ("collections", t("Collections")), ("items", t("Items")), ("attachments", t("Attachments")),
                  ("attachments_missing", t("Attachments missing on disk")), ("audit", t("Isolation rules")),
                  ("apache_site", t("Apache site")), ("last_backup", t("Last backup")), ("backups", t("Backups")),
                  ("disk_db", t("Database size")), ("disk_wp", t("Files size")), ("docker", "Docker"))
        text = "\n".join(f"{label}: {out.get(key)}" for key, label in labels if out.get(key))
        await self.app.push_screen_wait(TextScreen(t("Tainacan diagnosis"), text or t("Not checked")))

    async def tainacan_logs(self) -> None:
        from ..routines.common import run_task, show_done

        result = await run_task(self.app, t("Tainacan logs"), "tainacan-logs", "200")
        await show_done(self.app, t("Tainacan logs"), result)

    async def tainacan_backup(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Back up Tainacan")
        result = await run_task(self.app, title, "tainacan-backup")
        await show_done(self.app, title, result, t("The backup is ready."))
        self.refresh_data()

    async def _pick_backup(self, title: str) -> str | None:
        from ..screens.dialogs import ChoiceScreen, MessageScreen

        found: list[tuple[str, str]] = []

        def collect(key: str, value: str) -> None:
            if key == "backup":
                name, _sep, rest = value.partition("|")
                created, _sep, label = rest.partition("|")
                found.append((name, f"{created}  {label}  ({name})"))

        await self.app.bridge.task("tainacan-backups", on_result=collect)
        if not found:
            await self.app.push_screen_wait(MessageScreen(title, t("There is no complete Tainacan backup yet."),
                                                          kind="info"))
            return None
        return await self.app.push_screen_wait(ChoiceScreen(title, t("Which backup?"), found))

    async def tainacan_restore_test(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Test a restore")
        name = await self._pick_backup(title)
        if not name:
            return
        result = await run_task(self.app, title, "tainacan-restore-test", name)
        await show_done(self.app, title, result)

    async def tainacan_restore(self) -> None:
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen

        title = t("Restore Tainacan")
        name = await self._pick_backup(title)
        if not name:
            return
        if not await self.app.push_screen_wait(ConfirmScreen(title, t(
                "Restore this backup over the Tainacan in use? It is first tested in an isolated copy, and "
                "what is there now is saved in a safety backup; if the check fails, it goes back."),
                danger=True)):
            return
        result = await run_task(self.app, title, "tainacan-restore", name)
        await show_done(self.app, title, result)
        self.refresh_data()

    async def tainacan_credentials(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Tainacan administrator")
        result = await run_task(self.app, title, "tainacan-credentials")
        await show_done(self.app, title, result)

    async def tainacan_uninstall(self) -> None:
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ChoiceScreen, ConfirmScreen

        title = t("Uninstall Tainacan")
        choice = await self.app.push_screen_wait(ChoiceScreen(title, t("What happens to its data?"), [
            ("keep", t("Keep the data (installing it again uses it)")),
            ("delete", t("Delete the data (a last backup is made first)"))]))
        if choice not in ("keep", "delete"):
            return
        text = t("Uninstall Tainacan and keep its data?") if choice == "keep" else \
            t("Uninstall Tainacan and DELETE its collections, items and files? A last backup is made first "
              "and kept; nothing is deleted if it fails.")
        if not await self.app.push_screen_wait(ConfirmScreen(title, text, danger=choice == "delete")):
            return
        result = await run_task(self.app, title, "tainacan-uninstall", choice)
        await show_done(self.app, title, result)
        self.refresh_data()


# The Tainacan buttons, in order; the first shows while it is not
# installed, the others once it is.
TAINACAN_BUTTONS = (
    ("install", "Install Tainacan"),
    ("status", "Diagnosis"),
    ("logs", "Logs"),
    ("backup", "Back up now"),
    ("restore-test", "Test a restore"),
    ("restore", "Restore"),
    ("credentials", "Administrator"),
    ("uninstall", "Uninstall Tainacan"),
)


class UnavailableView(SectionView):
    """Stands in for a section whose platform is not installed: a key or a
    link that leads there shows why, and nothing of it is loaded."""

    def __init__(self, section, reason: str):
        # Its own id ("view-<id>-off"): the real view keeps "view-<id>" for
        # when the platform is installed, so the two never collide.
        VerticalScroll.__init__(self, id=f"view-{section.id}-off", classes="view")
        self.section = section
        self.reason = reason

    def compose(self) -> ComposeResult:
        yield from self.heading()
        yield Label(self.reason, classes="view-prompt", id="unavailable-reason")
