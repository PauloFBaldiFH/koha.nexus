"""SectionView: a heading, the bash sub-menu's question, a grid of cards."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, VerticalScroll
from textual.widgets import Label

from ..glyphs import split_icon
from ..i18n import t
from ..menus import Section
from ..widgets.cards import ActionCard


class SectionView(VerticalScroll):
    """Default view of a section; specialised views extend it."""

    def __init__(self, section: Section):
        super().__init__(id=f"view-{section.id}", classes="view")
        self.section = section

    @property
    def panel(self):
        return self.app

    def heading(self) -> ComposeResult:
        _icon, title = split_icon(t(self.section.title or self.section.label))
        yield Label(title, classes="view-title")
        if self.section.prompt:
            yield Label(t(self.section.prompt), classes="view-prompt")

    def cards(self) -> ComposeResult:
        entries = [e for e in self.section.entries if not e.hidden]
        if not entries:
            return
        with Grid(classes="card-grid"):
            for entry in entries:
                yield ActionCard(entry)

    def compose(self) -> ComposeResult:
        yield from self.heading()
        yield from self.cards()

    @on(ActionCard.Chosen)
    def _chosen(self, event: ActionCard.Chosen) -> None:
        event.stop()
        if event.entry.kind == "view":
            self.screen.action_show(event.entry.action)
            return
        self.panel.run_entry(event.entry, after=self.refresh_data)

    def refresh_data(self) -> None:
        """Called after a routine ends; views with live data override it."""
