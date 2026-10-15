"""Every other routine of the menu, as panel screens.

  generic(action)  `config.sh --task run ACTION`: the routine of the classic
                   panel (publishing, library tools, schedules, updates,
                   about, reboot...) runs as it is, and each box it opens
                   (menus, text to type, files to pick, yes/no, messages,
                   long texts, a file to edit) is one of the panel's own
                   screens, asked over the Pac-Man loader while it waits.
  languages, language_activate
                   the same, then the panel starts again in the new language
  update_panel     the same; a new version closes the panel (open it again)
  user_folder      the user's home folder in Windows Explorer (WSL) or the
                   desktop's file manager; elsewhere its path, to copy
  terminal         Open Debian terminal: under WSL a Debian terminal in a
                   window of its own (Windows Terminal, else wsl.exe), as
                   the tray's; elsewhere (or when Windows cannot start it) a
                   shell in this window; exit comes back to the panel
  monitor, mc
                   full-screen programs of their own: the choice and the
                   installation are panel screens, then the program gets the
                   terminal until it is closed (q / F10).
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from ..env import normalize_panel_language
from ..i18n import t
from ..opener import open_debian_terminal, open_user_folder
from ..screens.dialogs import ChoiceScreen, MessageScreen
from .common import facts, failed, run_interactive, run_task, show_failure, tx

RESTART_CODE = 3   # config.sh starts the panel again (screens/language.py)


def generic(action: str, title: str):
    """The routine of a menu entry, its boxes asked in the panel."""
    async def routine(app) -> None:
        await run_interactive(app, t(title), "run", action)
    routine.__name__ = f"run_{action.replace('-', '_')}"
    return routine


async def _language_change(app, title: str, action: str) -> None:
    result = await run_interactive(app, t(title), "run", action)
    out = result.value if result else None
    lang = out.get("panel_lang") if out is not None and hasattr(out, "get") else ""
    if lang and normalize_panel_language(lang) != app.env.lang:
        app.exit(return_code=RESTART_CODE)


async def languages(app) -> None:
    await _language_change(app, "Koha & Panel Languages", "languages")


async def language_activate(app) -> None:
    await _language_change(app, "✅  Set an installed language as active", "lang-activate")


async def update_panel(app) -> None:
    result = await run_interactive(app, t("🆕  Update this panel via GitHub"), "run", "update-panel")
    out = result.value if result else None
    if out is not None and hasattr(out, "get") and out.get("updated") == "yes":
        app.exit()


async def user_folder(app) -> None:
    """The home folder of the person behind the panel (the installer's
    REAL_HOME: the Debian user under WSL, the sudo user on a Linux desktop)."""
    info = await facts(app)
    home = info.get("real_home") or "/root"
    if not app.env.demo and open_user_folder(home):
        app.notify(tx("Opened ${folder}", folder=home), timeout=5)
        return
    await app.push_screen_wait(MessageScreen(
        t("📂  Open user folder"), "", kind="info", command=home,
        command_help=t("This computer has no file manager for the panel to open. The folder is:"),
        is_command=False))


def shell_command(user: str, hint: str) -> list[str]:
    """The in-window shell of "Open Debian terminal": a login shell of user (the person
    behind the panel, sudo for root), root's own when there is none. The
    hint is printed first, so the way back is on the screen."""
    if user and user != "root":
        login = ["runuser", "-l", user]
    else:
        login = ["bash", "-l"]
    return ["sh", "-c", 'printf "%s\\n\\n" "$1"; shift; exec "$@"', "sh", hint, *login]


async def terminal(app) -> None:
    if not app.env.demo and open_debian_terminal():
        app.notify(t("Opening the Debian terminal in a new window."), timeout=5)
        return
    info = await facts(app)
    user = (info.get("real_user") if info else "") or "root"
    rc = app.bridge.run_command_interactive(
        app, shell_command(user, t("Type exit to go back to the panel.")))
    if rc not in (0, None, 130):
        app.notify(f"{t('Open Debian terminal')}: exit {rc}", severity="warning")


async def _terminal_tool(app, title: str, tool: str, argv: list[str] | None = None) -> None:
    """Installs the program if needed (behind Pac-Man), then hands it the terminal."""
    result = await run_task(app, title, "tool-install", tool)
    if failed(result):
        await show_failure(app, title, result)
        return
    if argv is None:
        return
    rc = app.bridge.run_command_interactive(app, argv)
    if rc not in (0, None):
        app.notify(f"{title}: exit {rc}", severity="warning")


async def monitor(app) -> None:
    title = t("Resource Monitoring")
    choice = await app.push_screen_wait(ChoiceScreen(
        title, tx("Choose the real-time tool:\n\n(Press 'F10' or 'Q' to exit the screen and return to the panel)"),
        [("1", t("Htop (CPU, RAM and Active Processes usage)")),
         ("2", t("Nethogs (Network Bandwidth usage by Process)"))]))
    if not choice:
        return
    result = await run_task(app, t("Installing htop and nethogs"), "tool-install", "htop")
    if failed(result):
        await show_failure(app, title, result)
        return
    argv = ["htop"] if choice == "1" else ["nethogs", *filter(None, [result.value.get("iface")])]
    rc = app.bridge.run_command_interactive(app, argv)
    if rc not in (0, None):
        app.notify(f"{title}: exit {rc}", severity="warning")


async def mc(app) -> None:
    await _terminal_tool(app, t("Installing Midnight Commander"), "mc", ["mc"])
