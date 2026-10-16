"""The save step of a manual backup: the folder rules, WSL2 detection, the copy
target and the scp command (kei_panel.save_backup), and the screen that uses
them (screens/save_backup.py) in demo mode."""

import asyncio
import time
from pathlib import Path

from conftest import INSTALLER

from kei_panel import env as env_mod
from kei_panel import save_backup, transfer
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv
from kei_panel.screens.save_backup import SaveBackupScreen


# --- folder rules -------------------------------------------------------
def test_default_folder_is_backups_in_the_home():
    assert save_backup.default_folder("/home/ana") == Path("/home/ana/backups")
    assert save_backup.default_folder("") == Path("/root/backups")


def test_empty_box_means_the_default(tmp_path):
    default = tmp_path / "backups"
    assert save_backup.folder_problem("  ", default) == (default, "")


def test_relative_path_is_refused(tmp_path):
    assert save_backup.folder_problem("backups/x", tmp_path) == (None, "Use the full path, starting with /.")


def test_a_file_is_not_a_folder(tmp_path):
    f = tmp_path / "a.sql.gz"
    f.write_bytes(b"x")
    assert save_backup.folder_problem(str(f), tmp_path) == (None, "That is a file, not a folder.")


def test_existing_folder_is_taken_as_it_is(tmp_path):
    assert save_backup.folder_problem(str(tmp_path), tmp_path / "x") == (tmp_path, "")


def test_missing_folder_is_not_created_here(tmp_path):
    target = tmp_path / "new" / "deeper"
    assert save_backup.folder_problem(str(target), tmp_path) == (target, "")
    assert not target.exists()          # the save creates it


def test_folder_under_a_file_cannot_be_created(tmp_path):
    f = tmp_path / "plain"
    f.write_bytes(b"x")
    path, problem = save_backup.folder_problem(str(f / "backups"), tmp_path)
    assert path is None and problem == "That folder cannot be created here."


def test_pasted_windows_path_is_read_like_the_other_boxes(tmp_path):
    # A quoted, pasted path with a backslash escape is cleaned the same way.
    text = "'" + str(tmp_path) + "'"
    assert save_backup.folder_problem(text, tmp_path / "x") == (tmp_path, "")


# --- WSL2 ---------------------------------------------------------------
def _fake_proc_version(monkeypatch, tmp_path, text):
    fake = tmp_path / "version"
    if text is not None:
        fake.write_text(text)
    monkeypatch.setattr(env_mod, "Path", lambda _p: fake)


def test_wsl2_is_told_by_proc_version(monkeypatch, tmp_path):
    _fake_proc_version(monkeypatch, tmp_path,
                       "Linux version 5.15.167.4-microsoft-standard-WSL2 (root@1cf) (gcc) #1 SMP")
    assert save_backup.is_wsl() is True


def test_a_plain_linux_is_not_wsl(monkeypatch, tmp_path):
    _fake_proc_version(monkeypatch, tmp_path, "Linux version 6.1.0-18-amd64 (debian-kernel@lists.debian.org)")
    assert save_backup.is_wsl() is False


def test_no_proc_version_is_not_wsl(monkeypatch, tmp_path):
    _fake_proc_version(monkeypatch, tmp_path, None)
    assert save_backup.is_wsl() is False


# --- the Windows side ---------------------------------------------------
def test_picked_folder_needs_a_folder_that_exists(tmp_path):
    assert save_backup.picked_folder("") is None           # the person cancelled
    assert save_backup.picked_folder("\n") is None
    assert save_backup.picked_folder(str(tmp_path) + "\n") == tmp_path
    assert save_backup.picked_folder("C:\\Users\\nobody-here\\Downloads") is None


def test_windows_path_becomes_the_wsl_mount():
    assert transfer.dropped_path("C:\\Users\\Ana\\Downloads") == "/mnt/c/Users/Ana/Downloads"


def test_copy_target_never_overwrites(tmp_path):
    (tmp_path / "koha_manual.sql.gz").write_bytes(b"1")
    target = transfer.free_target(tmp_path, "koha_manual.sql.gz")
    assert target.name == "koha_manual (2).sql.gz"
    (tmp_path / target.name).write_bytes(b"2")
    assert transfer.free_target(tmp_path, "koha_manual.sql.gz").name == "koha_manual (3).sql.gz"


# --- scp ----------------------------------------------------------------
def test_scp_command_quotes_the_remote_path():
    cmd = save_backup.scp_command("ana", "192.0.2.10", "/home/ana/backups/koha manual.sql.gz")
    assert cmd == 'scp ana@192.0.2.10:"/home/ana/backups/koha manual.sql.gz" .'


def test_scp_host_is_the_server_address_or_this_host(monkeypatch):
    assert save_backup.scp_host("192.0.2.10") == "192.0.2.10"
    monkeypatch.setattr(save_backup.socket, "gethostname", lambda: "koha-box")
    assert save_backup.scp_host("") == "koha-box"
    assert save_backup.scp_host(None) == "koha-box"


# --- the screen ---------------------------------------------------------
INFO = {"real_home": "/root", "real_user": "root", "server_ip": "192.0.2.10"}


def _demo_app():
    return KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))


async def _until(pilot, cond, wait=10.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    return cond()


def test_windows_buttons_are_hidden_outside_wsl(monkeypatch, tmp_path):
    monkeypatch.setattr(save_backup, "is_wsl", lambda: False)

    async def main():
        app = _demo_app()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(SaveBackupScreen(INFO))
            await pilot.pause(0.2)
            screen = app.screen
            assert not screen.query("#win-downloads") and not screen.query("#win-pick")
            assert screen.query("#save") and screen.query("#done")
    asyncio.run(main())


def test_windows_buttons_are_shown_under_wsl(monkeypatch):
    monkeypatch.setattr(save_backup, "is_wsl", lambda: True)

    async def main():
        app = _demo_app()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(SaveBackupScreen(INFO))
            await pilot.pause(0.2)
            assert app.screen.query("#win-downloads") and app.screen.query("#win-pick")
    asyncio.run(main())


def test_a_bad_folder_is_said_and_nothing_starts(tmp_path):
    async def main():
        app = _demo_app()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(SaveBackupScreen(INFO))
            await pilot.pause(0.2)
            screen = app.screen
            screen.query_one("#sb-folder").value = "relative/dir"
            screen.query_one("#save").press()
            await pilot.pause(0.2)
            assert "starting with /" in str(screen.query_one("#sb-problem").render())
            assert screen._busy is False and screen._file is None
    asyncio.run(main())


def test_save_shows_the_scp_command_and_done_keeps_the_file(tmp_path):
    folder = tmp_path / "backups"

    async def main():
        app = _demo_app()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(SaveBackupScreen(INFO))
            await pilot.pause(0.2)
            screen = app.screen
            screen.query_one("#sb-folder").value = str(folder)
            screen.query_one("#save").press()
            assert await _until(pilot, lambda: screen._file is not None)
            await pilot.pause(0.2)
            assert screen.query_one("#sb-done").display
            assert not screen.query_one("#sb-buttons-save").display
            assert "scp " in str(screen.query_one("#sb-scp").render())
            screen.query_one("#done").press()
            await pilot.pause(0.2)
            assert not isinstance(app.screen, SaveBackupScreen)
    asyncio.run(main())
    assert folder.is_dir()
