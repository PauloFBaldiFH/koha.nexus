"""MainScreen: header, sidebar of sections, the chosen section's view.

  ┌ Header ───────────────────────────────────────────────┐
  │ Sidebar      │ View (ContentSwitcher)                 │
  │  Dashboard   │  title · question                      │
  │  Install     │  [status cards]                        │
  │  Backup      │  [action card] [action card] ...       │
  │  ...         │                                        │
  └ Footer: Dashboard, Open Debian terminal, Exit ────────┘
Views are mounted the first time they are shown; Tab moves between the
sidebar and the view.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import ContentSwitcher, Footer, Header, OptionList
from textual.widgets.option_list import Option

from .. import platforms
from ..glyphs import split_icon
from ..i18n import t
from ..menus import SECTIONS, section
from ..transfer import looks_like_path
from ..views import VIEWS, UnavailableView


def sidebar_prompt(label: str, plain: bool, own_icon: str = "") -> str:
    icon, text = split_icon(t(label))
    icon = icon or own_icon
    if plain or not icon:
        return f"  {text}"
    return f"{icon} {text}"


class MainScreen(Screen):
    # The bar at the bottom: the dashboard and a shell. Every section keeps
    # its letter (b still opens the Backup center), out of the bar.
    BINDINGS = [
        Binding(s.key, f"show('{s.id}')", split_icon(t(s.label))[1], show=s.key == "d")
        for s in SECTIONS if s.key
    ] + [Binding("c", "terminal", t("Open Debian terminal")),
         Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False)]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield OptionList(*self.sidebar_options(), id="sidebar")
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

    def sidebar_options(self) -> list[Option]:
        """Sections of the sidebar. A section of a platform that is not
        installed here (Koha on a server without it) is left out; its key
        still answers, with the reason (action_show)."""
        return [Option(sidebar_prompt(s.label, self.app.env.plain, s.icon), id=s.id) for s in SECTIONS
                if s.sidebar and self.app.platform_ready(s.requires)]

    def action_show(self, section_id: str, from_sidebar: bool = False) -> None:
        switcher = self.query_one("#views", ContentSwitcher)
        sec = section(section_id)
        ready = self.app.platform_ready(sec.requires)
        # A section whose platform is not installed gets its own stand-in
        # ("-off"): nothing of the section is loaded (its view may read
        # Koha's database as soon as it is shown), the reason is shown.
        view_id = f"view-{section_id}" if ready else f"view-{section_id}-off"
        if not switcher.query(f"#{view_id}"):
            if ready:
                switcher.mount(VIEWS[sec.view](sec))
            else:
                view = UnavailableView(sec, platforms.missing_reason(sec.requires))
                switcher.mount(view)
        switcher.current = view_id
        self.sub_title = split_icon(t(sec.label))[1]
        if not from_sidebar:
            sidebar = self.query_one("#sidebar", OptionList)
            try:
                sidebar.highlighted = sidebar.get_option_index(sec.parent or section_id)
            except Exception:  # noqa: BLE001 - a section that is not on the sidebar now
                sidebar.highlighted = None

    def platforms_changed(self) -> None:
        """Koha was installed (or removed) while the panel was open: the
        sidebar is drawn again, the screen on show is opened again the
        right way, and the other screens of a platform start over the next
        time they are shown."""
        sidebar = self.query_one("#sidebar", OptionList)
        sidebar.clear_options()
        sidebar.add_options(self.sidebar_options())
        switcher = self.query_one("#views", ContentSwitcher)
        current = switcher.current or ""
        gated = {f"view-{s.id}" for s in SECTIONS if s.requires} | {f"view-{s.id}-off" for s in SECTIONS if s.requires}
        for view in list(switcher.children):
            if view.id in gated and view.id != current:
                view.remove()
        if current in gated:
            self.action_show(current.removeprefix("view-").removesuffix("-off"), from_sidebar=True)

    # A file dropped on the window: the terminal pastes its path (Windows
    # Terminal C:\..., a Linux terminal /home/...). A backup goes straight
    # to Restore database; anything else is said, never ignored. Boxes that
    # take text (Input) keep what is pasted into them.
    def on_paste(self, event: events.Paste) -> None:
        if looks_like_path(event.text):
            event.stop()
            self.app.drop_file(event.text)

    def action_terminal(self) -> None:
        self.app.run_native("terminal")

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display
