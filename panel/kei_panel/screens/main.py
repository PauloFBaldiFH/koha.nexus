"""MainScreen: header, sidebar of sections, the chosen section's view.

  ┌ Header ───────────────────────────────────────────────┐
  │ Sidebar      │ View (ContentSwitcher)                 │
  │  Dashboard   │  title · question                      │
  │  Install     │  [status cards]                        │
  │  Backup      │  [action card] [action card] ...       │
  │  ...         │                                        │
  └ Footer: shortcuts ────────────────────────────────────┘
Views are mounted the first time they are shown; Tab moves between the
sidebar and the view.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import ContentSwitcher, Footer, Header, OptionList
from textual.widgets.option_list import Option

from ..glyphs import split_icon
from ..i18n import t
from ..menus import SECTIONS, section
from ..views import VIEWS


def sidebar_prompt(label: str, plain: bool, own_icon: str = "") -> str:
    icon, text = split_icon(t(label))
    icon = icon or own_icon
    if plain or not icon:
        return f"  {text}"
    return f"{icon} {text}"


class MainScreen(Screen):
    BINDINGS = [
        Binding(s.key, f"show('{s.id}')", split_icon(t(s.label))[1], show=s.key in "db")
        for s in SECTIONS if s.key
    ] + [Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False)]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield OptionList(
                *[Option(sidebar_prompt(s.label, self.app.env.plain, s.icon), id=s.id) for s in SECTIONS],
                id="sidebar")
            yield ContentSwitcher(id="views")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "koha.nexus"
        self.sub_title = t("Control Dashboard")
        self.action_show("dashboard")
        self.query_one("#sidebar").focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Enter or a click opens a section (as in whiptail); moving the
        # highlight alone does not, so arrowing past "Database tables"
        # does not start reading the database.
        if event.option.id:
            self.action_show(event.option.id, from_sidebar=True)

    def action_show(self, section_id: str, from_sidebar: bool = False) -> None:
        switcher = self.query_one("#views", ContentSwitcher)
        view_id = f"view-{section_id}"
        if not switcher.query(f"#{view_id}"):
            sec = section(section_id)
            switcher.mount(VIEWS[sec.view](sec))
        switcher.current = view_id
        sec = section(section_id)
        self.sub_title = split_icon(t(sec.label))[1]
        if not from_sidebar:
            sidebar = self.query_one("#sidebar", OptionList)
            sidebar.highlighted = sidebar.get_option_index(section_id)

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display
