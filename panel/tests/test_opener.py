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


# Paulo, 2026-10-15: "Abrir link" did nothing on Windows; the bottom bar
# carried the Backup center instead of a way to the terminal.

def test_links_open_through_explorer_under_wsl_even_with_wslview():
    from kei_panel.opener import opener_command
    which = {"wslview": "/usr/bin/wslview", "explorer.exe": None}.get
    url = "https://postimages.org/"
    cmd = opener_command(url, wsl=True, ssh=False, which=which, environ={})
    assert cmd in (["/mnt/c/Windows/explorer.exe", url], ["wslview", url])
    which = {"wslview": "/usr/bin/wslview", "explorer.exe": "/mnt/c/Windows/explorer.exe"}.get
    assert opener_command(url, wsl=True, ssh=False, which=which, environ={}) == ["/mnt/c/Windows/explorer.exe", url]


def test_the_wsl_interop_handler_is_put_back_when_systemd_lost_it(tmp_path, monkeypatch):
    import os
    from kei_panel import opener
    register = tmp_path / "register"
    register.write_text("")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    written = []
    real_write = type(register).write_text

    def fake_write(self, text, *a, **k):
        if self.name == "register":
            written.append(text)
            (tmp_path / "WSLInterop").write_text("enabled")
        return real_write(self, text, *a, **k)

    monkeypatch.setattr(type(register), "write_text", fake_write)
    assert opener._interop_ready(tmp_path)
    assert written == [":WSLInterop:M::MZ::/init:PF"]
    # Already there: nothing is written again.
    written.clear()
    assert opener._interop_ready(tmp_path) and written == []
    # Not root and missing: Windows programs cannot run.
    (tmp_path / "WSLInterop").unlink()
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    assert not opener._interop_ready(tmp_path)


def test_a_windows_program_starts_in_c_windows_after_the_interop_check(monkeypatch, tmp_path):
    from kei_panel import opener
    calls = []
    monkeypatch.setattr(opener, "_interop_ready", lambda: True)
    monkeypatch.setattr(opener, "_WINDOWS_DIR", tmp_path)
    monkeypatch.setattr(opener.subprocess, "Popen", lambda argv, **kw: calls.append((argv, kw.get("cwd"))))
    assert opener._start(["/mnt/c/Windows/explorer.exe", "https://koha.nexus"])
    assert calls == [(["/mnt/c/Windows/explorer.exe", "https://koha.nexus"], str(tmp_path))]
    monkeypatch.setattr(opener, "_interop_ready", lambda: False)
    assert not opener._start(["/mnt/c/Windows/explorer.exe", "https://koha.nexus"])
    calls.clear()
    assert opener._start(["xdg-open", "https://koha.nexus"]) and calls == [(["xdg-open", "https://koha.nexus"], None)]


def test_the_shell_is_the_debian_users_with_the_way_back_printed_first():
    from kei_panel.routines.tools import shell_command
    assert shell_command("ana", "Type exit.")[-4:] == ["Type exit.", "runuser", "-l", "ana"]
    assert shell_command("root", "Type exit.")[-3:] == ["Type exit.", "bash", "-l"]
    assert "terminal" in [e.action for e in section("tools").entries]
    assert "terminal" in PANEL_ONLY and routines.has("terminal")


def test_the_bottom_bar_has_the_terminal_not_the_backup_center(monkeypatch):
    import asyncio
    from conftest import INSTALLER
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.screens.main import MainScreen

    shown = {b.key: b.description for b in MainScreen.BINDINGS if b.show}
    assert "b" not in shown and shown.get("c") == "Open the terminal" and "d" in shown
    assert any(b.key == "b" for b in MainScreen.BINDINGS)      # the key still works

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        ran = []
        monkeypatch.setattr(app.bridge, "run_command_interactive", lambda a, argv: ran.append(argv) or 0)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("c")
            for _ in range(40):
                if ran:
                    break
                await pilot.pause(0.05)
        assert ran and ran[0][:2] == ["sh", "-c"] and "Type exit to go back to the panel." in ran[0]

    asyncio.run(main())


def test_open_link_copies_the_address_too(monkeypatch):
    from conftest import INSTALLER
    from kei_panel import opener
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
    copied, notes = [], []
    monkeypatch.setattr(opener, "open_url", lambda url: True)
    monkeypatch.setattr(app, "copy_to_clipboard", lambda text, quiet=False: copied.append(text))
    monkeypatch.setattr(app, "notify", lambda msg, **kw: notes.append(msg))
    app.open_url("https://postimages.org/")
    assert copied == ["https://postimages.org/"] and "address copied" in notes[0]
