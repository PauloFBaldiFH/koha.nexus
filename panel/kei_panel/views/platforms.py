"""PlatformsView: the platforms this panel knows, one card each.

Read only. Each card keeps the four facts apart (platforms.py): supported
by this panel, installation detected, services, functional health (not
verified yet). Koha keeps its own "Install Koha server" entry, the other
platforms are planned. Docker, which they will need, can be installed from
here: the installer's plan is shown first and nothing happens without a Yes.
"""

from __future__ import annotations

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

    def on_mount(self) -> None:
        self.query_one("#platforms-docker-install").display = False
        self.query_one("#platforms-docker-remove").display = False
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
            self.query_one(f"#platform-{state.id}", StatusCard).set(*platforms.describe(state))


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
