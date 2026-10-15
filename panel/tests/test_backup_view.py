"""Backup center: the compression of new backups, saved by the installer."""

import asyncio
import time

from conftest import INSTALLER
from textual.widgets import Select

from kei_panel.env import PanelEnv
from kei_panel.screens.loading import LoadingScreen


async def _until(pilot, cond, wait=5.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_compression_choice_runs_the_task():
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        calls = []
        real = app.bridge.task

        async def spy(name, *args, **kw):
            calls.append((name, args))
            return await real(name, *args, **kw)
        app.bridge.task = spy
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("b")
            view = app.screen.query_one("#view-backup")
            select = view.query_one("#bk-codec", Select)
            await _until(pilot, lambda: not select.disabled)          # the installer said: gz
            assert select.value == "gz" and view.codec == "gz"
            assert not [c for c in calls if c[0] == "backup-compression"]   # loading saves nothing
            select.value = "zst"
            await pilot.pause(0.3)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen) and view.codec == "zst")
            assert ("backup-compression", ("zst",)) in calls
            assert ".sql.zst" in str(view.query_one("#bk-codec-note").render())

    asyncio.run(main())


def test_the_cards_are_the_only_backup_actions(tmp_path, monkeypatch):
    """Paulo, 2026-10-15: no buttons above the status cards; the cards hold
    Download latest backup, manual backup, MARC21, restore and cloud. The
    MARC21 result offers Download to computer where Downloads is reachable."""
    from kei_panel import transfer
    from kei_panel.app import KohaPanelApp
    from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen
    from kei_panel.widgets.cards import ActionCard

    monkeypatch.setattr(transfer, "where", lambda: "wsl")

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        ran = []
        run_native = app.run_native
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("b")
            view = app.screen.query_one("#view-backup")
            assert not view.query(".quick-actions") and not view.query("#backup-restore")
            cards = {c.entry.action: c for c in view.query(ActionCard)}
            assert list(cards)[:5] == ["backup-download", "backup-manual", "backup-marc", "restore", "backup-cloud"]
            assert view.query_one("#bk-codec-box").border_title == "Backup compression type"
            app.run_native = lambda action, after=None: ran.append(action)
            cards["restore"].action_choose()
            await pilot.pause(0.1)
            assert ran == ["restore"]
            app.run_native = run_native
            cards["backup-marc"].action_choose()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            app.screen.dismiss(True)
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert "koha_marc_" in str(app.screen._details)
            await _until(pilot, lambda: bool(app.screen.query("#extra")))
            assert str(app.screen.query_one("#extra").label) == "📥 Download to computer"

    asyncio.run(main())


def test_marc_package_download_to_computer(tmp_path, monkeypatch):
    from kei_panel import transfer
    from kei_panel.app import KohaPanelApp
    from kei_panel.routines import backup
    from kei_panel.screens.dialogs import MessageScreen

    src = tmp_path / "koha_marc_2026-10-15.tar.gz"
    src.write_bytes(b"marc")
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / src.name).write_bytes(b"old")
    monkeypatch.setattr(transfer, "where", lambda: "wsl")
    monkeypatch.setattr(transfer, "downloads_folder", lambda place=None: downloads)

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            app.run_worker(backup.download_file(app, src, "📥 Download to computer", {}))
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            return app.screen._details

    details = asyncio.run(main())
    saved = downloads / "koha_marc_2026-10-15 (2).tar.gz"
    assert saved.read_bytes() == b"marc" and saved.name in str(details)
