"""SectionView: a heading, the bash sub-menu's question, a grid of cards.

A section's cards can be in zones (menus.Entry.zone): "setup",
"recovery" (diagnosis and recovery, drawn first), "" (the day-to-day
tools) and "removal" (removing, kept apart and drawn last). A section with
one zone looks as it always did: one grid, no zone title.

UnavailableView stands in for a section whose platform is not installed.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, VerticalScroll
from textual.widgets import Label

from ..glyphs import split_icon
from ..i18n import t
from ..menus import Entry, Section
from ..widgets.cards import ActionCard

# Zones in the order they are drawn, with their titles.
ZONE_ORDER = ("setup", "recovery", "", "removal")
ZONE_TITLES = {"setup": "", "recovery": "Diagnosis and recovery", "": "Tools", "removal": "Removal"}
PLATFORM_NAMES = {"koha": "Koha", "tainacan": "Tainacan"}


def zone_id(zone: str) -> str:
    return zone or "tools"


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

    def entries(self) -> list[Entry]:
        """The cards of the section. In a section every platform shares
        (the Server area), a card of a platform that is not installed here
        is left out: nothing is offered that cannot run."""
        return [e for e in self.section.entries if not e.hidden
                and (self.section.view == "platform-home" or self.section.requires
                     or self.app.platform_ready(e.requires))]

    def tag(self, entry: Entry) -> str:
        """"Koha" on a card of a shared section that only serves Koha."""
        if entry.requires and not self.section.requires and self.section.view != "platform-home":
            return PLATFORM_NAMES.get(entry.requires, entry.requires)
        return ""

    def cards(self) -> ComposeResult:
        entries = self.entries()
        if not entries:
            return
        zones = [z for z in ZONE_ORDER if any(e.zone == z for e in entries)]
        for zone in zones:
            title = ZONE_TITLES[zone]
            if len(zones) > 1 and title:
                yield Label(t(title), classes="view-prompt zone-title", id=f"zone-{zone_id(zone)}-title")
            classes = "card-grid" + (" zone-removal" if zone == "removal" else "")
            with Grid(classes=classes, id=f"zone-{zone_id(zone)}" if len(zones) > 1 else None):
                for entry in entries:
                    if entry.zone == zone:
                        yield ActionCard(entry, tag=self.tag(entry))

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
