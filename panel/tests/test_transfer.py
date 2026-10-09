"""Subject 1, steps 3 and 4: Copy buttons, dropped backup files and the
latest backup copied to Downloads (kei_panel.transfer)."""

import asyncio
import shutil
from collections import namedtuple
from pathlib import Path

import pytest
from conftest import INSTALLER
from textual import events

from kei_panel import transfer
from kei_panel.app import KohaPanelApp, clean_copy
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import MessageScreen, TextScreen, copyable
from kei_panel.screens.files import PathPickerScreen
from kei_panel.tasks import TaskFailed
from kei_panel.widgets.copy import CopyButton


class FakeReporter:
    def __init__(self, cancel_after=None):
        self.points, self.lines, self.cancel_after = [], [], cancel_after

    def progress(self, done, total):
        self.points.append((done, total))

    def status(self, text):
        self.lines.append(text)

    @property
    def cancelled(self):
        return self.cancel_after is not None and len(self.points) > self.cancel_after


@pytest.mark.parametrize("text, path", [
    ("/root/b.sql.gz", "/root/b.sql.gz"),
    ("'/home/ana/my backup.sql'", "/home/ana/my backup.sql"),
    ("/home/ana/my\\ backup.sql\n", "/home/ana/my backup.sql"),
    ('"C:\\Users\\Ana\\Downloads\\koha 1.sql.gz"', "/mnt/c/Users/Ana/Downloads/koha 1.sql.gz"),
    ("D:\\backups\\k.sql", "/mnt/d/backups/k.sql"),
    ("\\\\wsl.localhost\\Debian\\root\\k.sql", "/root/k.sql"),
    ("file:///home/ana/k%20b.sql", "/home/ana/k b.sql"),
    ("file:///C:/Users/Ana/k.sql", "/mnt/c/Users/Ana/k.sql"),
    # Escaped or doubled quotes and a Windows line break (drag and drop).
    ('\\"/home/ana/acervo.mrc\\"', "/home/ana/acervo.mrc"),
    ("\\'/home/ana/my file.xml\\'\r\n", "/home/ana/my file.xml"),
    ("\"'/mnt/c/Users/Ana/livros.xlsx'\"", "/mnt/c/Users/Ana/livros.xlsx"),
    ("'C:\\Koha\\Importar\\dump.sql.zst'\r\n", "/mnt/c/Koha/Importar/dump.sql.zst"),
    # Names with blanks and parentheses; PowerShell's "& '...'"; forward
    # slashes; a WSL file dropped from Windows Explorer; one quote left.
    ("& 'C:\\Users\\Ana\\BKP_BIBLIOTECA (2).backup'", "/mnt/c/Users/Ana/BKP_BIBLIOTECA (2).backup"),
    ("/root/BKP_BIBLIOTECA\\ \\(2\\).backup", "/root/BKP_BIBLIOTECA (2).backup"),
    ("  \"/root/BKP_BIBLIOTECA (2).backup\"  ", "/root/BKP_BIBLIOTECA (2).backup"),
    ("C:/Users/Ana/acervo.dump", "/mnt/c/Users/Ana/acervo.dump"),
    ("file://wsl.localhost/Debian/root/a%20(2).bkp", "/root/a (2).bkp"),
    ("'/root/importar/x.tar", "/root/importar/x.tar"),
    ("/root//importar/", "/root/importar"),
])
def test_dropped_paths(text, path):
    assert transfer.dropped_path(text) == path


def test_copy_reports_progress_and_speed(tmp_path):
    src = tmp_path / "b.sql.gz"
    src.write_bytes(b"x" * (3 * transfer.CHUNK + 10))
    rep = FakeReporter()
    out = transfer.copy_file(src, tmp_path / "out.sql.gz", rep)
    assert out.read_bytes() == src.read_bytes()
    assert rep.points[-1] == (src.stat().st_size, src.stat().st_size) and len(rep.points) == 5
    assert " / " in rep.lines[-1] and "/s · " in rep.lines[-1]
    assert not (tmp_path / "out.sql.gz.part").exists()


def test_cancelled_copy_leaves_nothing(tmp_path):
    src = tmp_path / "b.sql"
    src.write_bytes(b"x" * (4 * transfer.CHUNK))
    with pytest.raises(InterruptedError):
        transfer.copy_file(src, tmp_path / "out.sql", FakeReporter(cancel_after=2))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["b.sql"]


def test_no_room_is_said_before_copying(tmp_path, monkeypatch):
    src = tmp_path / "b.sql"
    src.write_bytes(b"x" * 2048)
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: Usage(10, 10, 100))
    with pytest.raises(TaskFailed, match="free"):
        transfer.copy_file(src, tmp_path / "out.sql", FakeReporter())
    assert not (tmp_path / "out.sql.part").exists()


def test_a_taken_name_gets_a_number(tmp_path):
    (tmp_path / "k.sql.gz").write_text("1")
    (tmp_path / "k (2).sql.gz").write_text("2")
    assert transfer.free_target(tmp_path, "k.sql.gz").name == "k (3).sql.gz"
    assert transfer.free_target(tmp_path, "new.sql").name == "new.sql"


def test_windows_disk_and_backup_names():
    assert transfer.on_windows_disk("/mnt/c/Users/a/k.sql") and not transfer.on_windows_disk("/mnt/backup/k.sql")
    assert transfer.is_backup_name("K.SQL.GZ") and not transfer.is_backup_name("k.gz")


def test_about_keys_are_copyable():
    about = ("Support this open-source initiative:\n  * Pix (Brazil)  : 076.650.449.21\n"
             "  * Bitcoin (BTC) : bc1qw0kvacdkzul0panuppxcv90y08ah443m2z89tx\n\n"
             "Official Repository:\n  https://github.com/PauloFBaldiFH/koha.nexus\n")
    assert copyable(about) == ["076.650.449.21", "bc1qw0kvacdkzul0panuppxcv90y08ah443m2z89tx",
                               "https://github.com/PauloFBaldiFH/koha.nexus"]
    assert copyable("Invalid CPF: 123.456.789-00") == []     # only a Pix line gives a key


def test_copied_text_has_no_terminal_codes():
    assert clean_copy("\x1b[1;33mscp root@1.2.3.4:/x Downloads/\x1b[0m\n") == "scp root@1.2.3.4:/x Downloads/"


def app():
    return KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))


def test_copy_button_says_copied_then_comes_back(monkeypatch):
    monkeypatch.setattr("kei_panel.widgets.copy.FEEDBACK_SECONDS", 0.3)
    copied = []

    async def main():
        a = app()
        async with a.run_test() as pilot:
            monkeypatch.setattr(a, "copy_to_clipboard", lambda text, quiet=False: copied.append(text))
            a.push_screen(MessageScreen("Done", "", command="scp a b"))
            await pilot.pause(0.2)
            button = a.screen.query_one("#copy", CopyButton)
            first = str(button.label)
            await pilot.click("#copy")
            await pilot.pause(0.05)
            during = str(button.label)
            await pilot.pause(0.5)
            return first, during, str(button.label)
    first, during, after = asyncio.run(main())
    assert (first, during, after) == ("📋 Copy command", "✓ Copied!", "📋 Copy command")
    assert copied == ["scp a b"]


def test_about_text_gets_copy_buttons():
    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            a.push_screen(TextScreen("About", "Pix (Brazil) : 076.650.449.21\nBitcoin (BTC) : bc1qw0kvacdkzul0panuppxcv90y08ah443m2z89tx"))
            await pilot.pause(0.2)
            return [str(b.label) for b in a.screen.query(CopyButton)]
    assert asyncio.run(main()) == ["📋 Copy", "📋 Copy"]


def pick(start, drop, send=None):
    async def main():
        a = app()
        result = []
        async with a.run_test(size=(120, 40)) as pilot:
            a.push_screen(PathPickerScreen("Restore", start, mode="file", send_command=send), callback=result.append)
            await pilot.pause(0.2)
            a.screen.query_one("#picker-tree").post_message(events.Paste(drop))
            await pilot.pause(0.3)
            return result, a.screen
    return asyncio.run(main())


def test_a_dropped_backup_is_chosen(tmp_path):
    f = tmp_path / "my backup.sql.gz"
    f.write_bytes(b"x")
    result, _ = pick(tmp_path, f"'{f}'")
    assert result == [f]


def test_a_dropped_backup_with_parentheses_is_chosen(tmp_path):
    f = tmp_path / "BKP_BIBLIOTECA (2).backup"
    f.write_bytes(b"x")
    result, _ = pick(tmp_path, f'"{f}"')
    assert result == [f]


def test_any_file_is_taken_when_the_picker_is_for_any_file(tmp_path):
    """The Magic Import Tool asks for any file (no suffixes): a dropped
    .tar or .dump is chosen, and a typed path in quotes is cleaned first."""
    f = tmp_path / "acervo antigo (2).tar"
    f.write_bytes(b"x")

    async def main(how):
        a = app()
        result = []
        async with a.run_test(size=(120, 40)) as pilot:
            a.push_screen(PathPickerScreen("Import", tmp_path, mode="file", suffixes=None), callback=result.append)
            await pilot.pause(0.2)
            if how == "drop":
                a.screen.query_one("#picker-tree").post_message(events.Paste(f"'{f}'"))
            else:
                box = a.screen.query_one("#picker-path")
                box.value = f'  "{f}"  '
                box.focus()
                await pilot.press("enter")
            await pilot.pause(0.3)
            return result
    assert asyncio.run(main("drop")) == [f]
    assert asyncio.run(main("type")) == [f]


def test_an_unreadable_path_is_said_not_raised(tmp_path):
    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            a.push_screen(PathPickerScreen("Import", tmp_path, mode="file", suffixes=None))
            await pilot.pause(0.2)
            box = a.screen.query_one("#picker-path")
            box.value = "/root/" + "x" * 5000
            box.focus()
            await pilot.press("enter")
            await pilot.pause(0.2)
            return type(a.screen).__name__, str(a.screen.query_one("#picker-error").render())
    name, error = asyncio.run(main())
    assert name == "PathPickerScreen" and "does not exist" in error


def test_texts_with_brackets_never_close_the_panel():
    """A title, option or status with "[/...]" (a path) is shown as it is,
    not read as Rich markup (a MarkupError would end the whole panel)."""
    from kei_panel.screens.dialogs import ChoiceScreen
    text = "Saved in [/root/importar] (2)"

    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            a.push_screen(ChoiceScreen(text, text, [("1", text)]))
            await pilot.pause(0.3)
            a.push_screen(MessageScreen(text, text, kind="error"))
            await pilot.pause(0.3)
            return type(a.screen).__name__
    assert asyncio.run(main()) == "MessageScreen"


def test_a_dropped_file_from_another_computer_gets_the_scp_command(tmp_path):
    result, screen = pick(tmp_path, '"C:\\Users\\Ana\\k.sql"', send=lambda p: f'scp "{p}" root@192.0.2.10:/root/')
    assert result == []
    assert isinstance(screen, MessageScreen) and screen._command == 'scp "C:\\Users\\Ana\\k.sql" root@192.0.2.10:/root/'


def test_download_latest_saves_in_downloads(tmp_path, monkeypatch):
    from kei_panel.routines import backup
    src = tmp_path / "server" / "koha_daily.sql.gz"
    src.parent.mkdir()
    src.write_bytes(b"y" * 5000)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    async def facts(_app):
        return {"newest": str(src), "dir_sql": str(src.parent), "real_user": "root", "server_ip": "192.0.2.10"}

    monkeypatch.setattr(backup, "facts", facts)
    monkeypatch.setattr(transfer, "where", lambda: "wsl")
    monkeypatch.setattr(transfer, "downloads_folder", lambda place=None: downloads)
    notes = []

    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(a, "notify", lambda msg, **kw: notes.append(msg))
            a.run_native("backup-download")
            for _ in range(40):
                await pilot.pause(0.1)
                if isinstance(a.screen, MessageScreen):
                    break
            return type(a.screen).__name__
    assert asyncio.run(main()) == "MessageScreen"
    assert (downloads / "koha_daily.sql.gz").read_bytes() == src.read_bytes()
    assert any("koha_daily.sql.gz" in n for n in notes)


def test_download_over_ssh_shows_the_scp_command(tmp_path, monkeypatch):
    from kei_panel.routines import backup
    src = tmp_path / "koha_daily.sql.gz"
    src.write_bytes(b"y")

    async def facts(_app):
        return {"newest": str(src), "real_user": "ana", "server_ip": "192.0.2.10"}

    monkeypatch.setattr(backup, "facts", facts)
    monkeypatch.setattr(transfer, "where", lambda: "ssh")

    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            a.run_native("backup-download")
            for _ in range(40):
                await pilot.pause(0.1)
                if isinstance(a.screen, MessageScreen):
                    break
            return a.screen._command
    assert asyncio.run(main()) == f"scp ana@192.0.2.10:{src} Downloads/"


def test_compressed_backups_are_backup_names(tmp_path):
    for name in ("k.sql", "k.sql.gz", "k.sql.bz2", "k.sql.xz", "k.sql.zst"):
        assert transfer.is_backup_name(name)
    (tmp_path / "k.sql.zst").write_text("x")
    assert transfer.free_target(tmp_path, "k.sql.zst").name == "k (2).sql.zst"
