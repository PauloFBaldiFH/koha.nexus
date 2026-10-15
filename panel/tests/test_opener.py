"""Opening the user's folder and showing a file in Windows Explorer
(opener.folder_command, opener.reveal_command), and the card that opens
the user folder (Paulo, 2026-10-15: Windows users never type Linux paths)."""

from kei_panel import routines
from kei_panel.menus import PANEL_ONLY, section
from kei_panel.opener import folder_command, reveal_command

WHICH = {"explorer.exe": "/mnt/c/Windows/explorer.exe", "xdg-open": "/usr/bin/xdg-open",
         "runuser": "/usr/sbin/runuser"}.get


def winpath(path):
    return {"/home/ana": r"\\wsl.localhost\koha\home\ana",
            "/mnt/c/Users/Ana Lima/Downloads/koha_library_manual.sql.gz":
                r"C:\Users\Ana Lima\Downloads\koha_library_manual.sql.gz"}.get(path, "")


def test_user_folder_opens_in_windows_explorer_under_wsl():
    assert folder_command("/home/ana", wsl=True, ssh=False, which=WHICH, environ={}, winpath=winpath) == \
        ["/mnt/c/Windows/explorer.exe", r"\\wsl.localhost\koha\home\ana"]


def test_user_folder_uses_xdg_open_on_a_linux_desktop_as_the_sudo_user():
    cmd = folder_command("/home/ana", wsl=False, ssh=False, which=WHICH,
                         environ={"DISPLAY": ":0", "SUDO_USER": "ana"}, winpath=winpath)
    assert cmd[-2:] == ["xdg-open", "/home/ana"]


def test_nothing_is_opened_over_ssh_without_a_desktop_or_without_a_windows_path():
    assert folder_command("/home/ana", wsl=True, ssh=True, which=WHICH, environ={}, winpath=winpath) is None
    assert folder_command("/home/ana", wsl=False, ssh=False, which=WHICH, environ={}, winpath=winpath) is None
    assert folder_command("/nowhere", wsl=True, ssh=False, which=WHICH, environ={}, winpath=winpath) is None


def test_a_backup_is_shown_selected_in_explorer():
    path = "/mnt/c/Users/Ana Lima/Downloads/koha_library_manual.sql.gz"
    assert reveal_command(path, wsl=True, ssh=False, which=WHICH, environ={}, winpath=winpath) == \
        ["/mnt/c/Windows/explorer.exe", "/select,", r"C:\Users\Ana Lima\Downloads\koha_library_manual.sql.gz"]
    # A Linux desktop cannot select a file: its folder opens.
    cmd = reveal_command("/home/ana/Downloads/b.sql.gz", wsl=False, ssh=False, which=WHICH,
                         environ={"DISPLAY": ":0"}, winpath=winpath)
    assert cmd[-2:] == ["xdg-open", "/home/ana/Downloads"]


def test_the_user_folder_card_is_a_panel_routine():
    assert "user-folder" in [e.action for e in section("tools").entries]
    assert "user-folder" in PANEL_ONLY and routines.has("user-folder")
