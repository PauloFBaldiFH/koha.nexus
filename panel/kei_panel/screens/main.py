"""MainScreen: header, sidebar of sections, the chosen section's view.

  ┌ Header ───────────────────────────────────────────────┐
  │ Sidebar         │ View (ContentSwitcher)              │
  │  Dashboard      │  title · question                   │
  │ ▾ Koha          │  [status cards]                     │
  │     Backups     │  [action card] [action card] ...    │
  │     ...         │                                     │
  │ ▸ Tainacan      │                                     │
  │ ── Server ──    │                                     │
  │  Security ...   │                                     │
  └ Footer: Dashboard, Open Debian terminal, Exit ────────┘
The platforms are groups (menus.GROUPS): the group's row opens the
platform's home and expands it; → expands and ← collapses a group without
changing the screen. A group's screens are listed only while it is
expanded and the platform is installed. Views are mounted the first time
they are shown; Tab moves between the sidebar and the view.
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
from ..menus import GROUPS, SECTIONS, group_of, section
from ..transfer import looks_like_path
from ..views import VIEWS, UnavailableView


def sidebar_prompt(label: str, plain: bool, own_icon: str = "") -> str:
    icon, text = split_icon(t(label))
    icon = icon or own_icon
    if plain or not icon:
        return f"  {text}"
    return f"{icon} {text}"


class Sidebar(OptionList):
    """The sidebar: arrows right and left expand and collapse a group."""

    BINDINGS = [Binding("right", "expand", show=False), Binding("left", "collapse", show=False)]

    def _current_id(self) -> str:
        if self.highlighted is None:
            return ""
        return self.get_option_at_index(self.highlighted).id or ""

    def action_expand(self) -> None:
        self.screen.set_group(self._current_id(), True)

    def action_collapse(self) -> None:
        self.screen.set_group(self._current_id(), False)


class MainScreen(Screen):
    # The bar at the bottom: the dashboard and a shell. Every section keeps
    # its letter (b still opens the Backup center), out of the bar.
    BINDINGS = [
        Binding(s.key, f"show('{s.id}')", split_icon(t(s.label))[1], show=s.key == "d")
        for s in SECTIONS if s.key
    ] + [Binding("c", "terminal", t("Open Debian terminal")),
         Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False)]

    def compose(self) -> ComposeResult:
        # The groups of the installed platforms start expanded.
        self.expanded: set[str] = {g for g in GROUPS if self.app.platform_ready(g)}
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield Sidebar(*self.sidebar_options(), id="sidebar")
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
        # does not start reading the database. A group's row also expands it.
        if event.option.id:
            self.action_show(event.option.id, from_sidebar=True)

    def sidebar_options(self) -> list[Option]:
        """Sections of the sidebar: the dashboard, each platform group (its
        screens only while expanded, and only with the platform installed:
        a key of a missing platform's screen still answers, with the reason),
        then the Server area."""
        plain = self.app.env.plain
        options: list[Option] = []
        server = False
        for s in SECTIONS:
            if not s.sidebar:
                continue
            if s.id in GROUPS:
                open_ = s.id in self.expanded
                arrow = ("-" if open_ else "+") if plain else ("▾" if open_ else "▸")
                if not self.app.platform_ready(s.id):
                    arrow = " "             # not installed: nothing under it to open
                options.append(Option(f"{arrow} {sidebar_prompt(s.label, plain, s.icon).lstrip()}", id=s.id))
            elif s.group:
                if s.group in self.expanded and self.app.platform_ready(s.requires):
                    options.append(Option("   " + sidebar_prompt(s.label, plain, s.icon), id=s.id))
            else:
                if not server and s.id not in ("dashboard", "instances"):
                    server = True
                    rule = "--" if plain else "──"
                    options.append(Option(f"{rule} {t('Server')} {rule}", id="sidebar-server", disabled=True))
                options.append(Option(sidebar_prompt(s.label, plain, s.icon), id=s.id))
        return options

    def redraw_sidebar(self, highlight: str = "") -> None:
        sidebar = self.query_one("#sidebar", OptionList)
        if not highlight and sidebar.highlighted is not None:
            highlight = sidebar.get_option_at_index(sidebar.highlighted).id or ""
        sidebar.clear_options()
        sidebar.add_options(self.sidebar_options())
        self.highlight(highlight)

    def highlight(self, section_id: str) -> None:
        sidebar = self.query_one("#sidebar", OptionList)
        for candidate in (section_id, group_of(section_id) if section_id in {s.id for s in SECTIONS} else ""):
            if not candidate:
                continue
            try:
                sidebar.highlighted = sidebar.get_option_index(candidate)
                return
            except Exception:  # noqa: BLE001 - not on the sidebar now
                continue
        sidebar.highlighted = None

    def set_group(self, option_id: str, expand: bool) -> None:
        """→ / ←: expand or collapse the group of the highlighted row (the
        group's own row, or one of its screens). The screen does not change."""
        if not option_id or option_id == "sidebar-server":
            return
        group = option_id if option_id in GROUPS else group_of(option_id)
        if not group or (group in self.expanded) == expand:
            return
        if expand:
            self.expanded.add(group)
        else:
            self.expanded.discard(group)
        self.redraw_sidebar(highlight=option_id if expand else group)

    def action_show(self, section_id: str, from_sidebar: bool = False, scope: str = "") -> None:
        switcher = self.query_one("#views", ContentSwitcher)
        sec = section(section_id)
        # A card can open a shared screen already filtered (the Backup
        # center from a platform group: menus.Entry.scope).
        if scope and section_id == "backups":
            self.app.backup_scope = scope
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
        if scope:
            view = switcher.query_one(f"#{view_id}")
            if hasattr(view, "set_scope"):
                view.set_scope(scope)
        self.sub_title = split_icon(t(sec.label))[1]
        # The group of the screen shown is expanded (a key, a card or its row).
        group = group_of(section_id)
        if group and group not in self.expanded:
            self.expanded.add(group)
            self.redraw_sidebar(highlight=sec.parent or section_id)
        elif not from_sidebar:
            self.highlight(sec.parent or section_id)

    def platforms_changed(self) -> None:
        """Koha was installed (or removed) while the panel was open: the
        sidebar is drawn again, the screen on show is opened again the
        right way, and the other screens of a platform start over the next
        time they are shown."""
        # A platform just installed: its group opens.
        self.expanded |= {g for g in GROUPS if self.app.platform_ready(g)}
        self.redraw_sidebar()
        switcher = self.query_one("#views", ContentSwitcher)
        current = switcher.current or ""
        # The screens that depend on what is installed: a platform's, a
        # platform group's, and a shared one with cards of a platform.
        changing = [s for s in SECTIONS if s.requires or s.view in ("platform-home", "platform-section")
                    or any(e.requires for e in s.entries)]
        gated = {f"view-{s.id}" for s in changing} | {f"view-{s.id}-off" for s in changing}
        for view in list(switcher.children):
            if view.id in gated and view.id != current:
                view.remove()
        if current in gated:
            self.action_show(current.removeprefix("view-").removesuffix("-off"), from_sidebar=True)
            view = switcher.query_one(f"#{switcher.current}")
            if hasattr(view, "refresh_data") and current == switcher.current:
                view.refresh_data()

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
