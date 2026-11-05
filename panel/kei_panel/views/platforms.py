"""PlatformsView: the platforms this panel knows, one card each.

Read only. Each card keeps the four facts apart (platforms.py): supported
by this panel, installation detected, services, functional health (not
verified yet). Nothing is installed from here in this version: Koha keeps
its own "Install Koha server" entry, the other platforms are planned.
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

    def on_mount(self) -> None:
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "platforms-refresh":
            event.stop()
            self.refresh_data()

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
        self.app.platforms_seen(status)

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
