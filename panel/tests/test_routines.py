"""Ported routines (routines/): the @@ protocol and the flows, end to end in
demo mode (the installer's answers are simulated by demo.py)."""

import asyncio
import os
import subprocess

import pytest
from conftest import INSTALLER

from kei_panel.app import KohaPanelApp
from kei_panel.bridge import TaskOutcome
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import (ChoiceScreen, ConfirmScreen, CredentialsScreen, InputScreen,
                                      MessageScreen, TextScreen)
from kei_panel.screens.files import PathPickerScreen
from kei_panel.screens.loading import LoadingScreen


def test_protocol_lines_are_parsed():
    out = TaskOutcome(total_steps=2)
    for line in ["plain output", "@@step Importing the catalog", "@@done 0 Importing the catalog",
                 "@@note Checking...", "@@result file=/root/a b.sql.gz", "@@result remote=x",
                 "@@result remote=y", "@@msg error Erro\tLine 1\\nLine 2"]:
        out.feed(line)
    assert out.steps == [("Importing the catalog", 0)]
    assert out.get("file") == "/root/a b.sql.gz" and out.lists["remote"] == ["x", "y"]
    assert out.last("error") == ("error", "Erro", "Line 1\nLine 2")
    assert not out.ok


def test_ok_needs_exit_zero_and_no_error_box():
    out = TaskOutcome()
    out.feed("@@msg ok OK\tdone")
    assert out.ok
    out.rc = 1
    assert not out.ok


@pytest.mark.skipif(os.geteuid() != 0, reason="the installer runs as root")
def test_installer_answers_in_the_protocol():
    run = subprocess.run(["bash", str(INSTALLER), "--task", "info"], capture_output=True, text=True, timeout=60)
    out = TaskOutcome()
    for line in run.stdout.splitlines():
        out.feed(line)
    assert run.returncode == 0 and out.get("dir_sql") and out.get("server_ip")
    bad = subprocess.run(["bash", str(INSTALLER), "--task", "no-such-task"], capture_output=True, text=True,
                         timeout=60)
    assert bad.returncode == 2 and bad.stdout.startswith("@@msg error")


def _app():
    return KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))


async def _wait_for(pilot, screen_type, tries=60):
    for _ in range(tries):
        await pilot.pause(0.1)
        if isinstance(pilot.app.screen, screen_type):
            return pilot.app.screen
    raise AssertionError(f"{screen_type.__name__} never shown (on {type(pilot.app.screen).__name__})")


def test_manual_backup_flow(tmp_path):
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("backup-manual")
            picker = await _wait_for(pilot, PathPickerScreen)
            picker.query_one("#picker-path").value = str(tmp_path)
            picker.query_one("#choose").press()
            await _wait_for(pilot, LoadingScreen)
            done = await _wait_for(pilot, MessageScreen)
            return done
    done = asyncio.run(main())
    assert done._command.startswith("scp root@") and str(tmp_path) in done._command


def test_restore_flow_asks_before_replacing(tmp_path):
    backup = tmp_path / "koha.sql.gz"
    backup.write_bytes(b"x")

    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("restore")
            picker = await _wait_for(pilot, PathPickerScreen)
            assert "scp" in picker._help
            picker.query_one("#picker-path").value = str(backup)
            picker.query_one("#choose").press()
            confirm = await _wait_for(pilot, ConfirmScreen)
            assert "REPLACED" in confirm._question and confirm._danger
            confirm.query_one("#yes").press()
            loader = await _wait_for(pilot, LoadingScreen)
            assert not loader.cancellable
            return await _wait_for(pilot, MessageScreen, tries=100)
    done = asyncio.run(main())
    assert ("Search engine", "Zebra") in done._details


def test_cloud_token_is_checked_before_running(tmp_path):
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("backup-cloud")
            choice = await _wait_for(pilot, ChoiceScreen)
            choice.dismiss("token")
            form = await _wait_for(pilot, InputScreen)
            form.query_one("#value").value = '{"access_token":"a"}'
            form.query_one("#ok").press()
            await pilot.pause(0.2)
            error = str(form.query_one("#input-error").render())
            assert isinstance(app.screen, InputScreen)
            form.query_one("#value").value = '{"access_token":"a","refresh_token":"b","expiry":"c"}'
            form.query_one("#ok").press()
            done = await _wait_for(pilot, MessageScreen)
            return error, done
    error, done = asyncio.run(main())
    assert "corrupt" in error and done._kind == "ok"


def test_test_backup_offers_the_newest_file():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("backup-test")
            choice = await _wait_for(pilot, ChoiceScreen)
            assert "koha_library_2026-10-02_03h00.sql.gz" in choice._prompt
            choice.dismiss("newest")
            return await _wait_for(pilot, MessageScreen)
    done = asyncio.run(main())
    assert ("Tables", "312") in done._details


def test_deep_maintenance_previews_then_runs():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("db-maintenance")
            confirm = await _wait_for(pilot, ConfirmScreen)
            preview = confirm._question
            confirm.query_one("#yes").press()
            await _wait_for(pilot, LoadingScreen)
            return preview, await _wait_for(pilot, MessageScreen, tries=100)
    preview, done = asyncio.run(main())
    assert "Repair and optimize" in preview and done._kind == "ok"


def test_reports_pack_removal_is_a_danger_confirm():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("reports")
            choice = await _wait_for(pilot, ChoiceScreen)
            choice.dismiss("remove")
            confirm = await _wait_for(pilot, ConfirmScreen)
            danger = confirm._danger
            confirm.query_one("#no").press()
            await pilot.pause(0.3)
            return danger, type(app.screen).__name__
    danger, screen = asyncio.run(main())
    assert danger and screen not in ("ConfirmScreen", "LoadingScreen")


def test_install_asks_everything_before_erasing():
    async def main():
        app = _app()
        seen = {}
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("install")
            ports = await _wait_for(pilot, ConfirmScreen)
            seen["ports"] = ports._question
            ports.query_one("#yes").press()
            await pilot.pause(0.5)
            welcome = await _wait_for(pilot, ConfirmScreen)
            seen["preview"] = welcome._preview
            welcome.query_one("#yes").press()
            await pilot.pause(0.2)
            tz = await _wait_for(pilot, ConfirmScreen)
            seen["tz"] = tz._question
            tz.query_one("#no").press()
            region = await _wait_for(pilot, ChoiceScreen)
            region.dismiss("Europe")
            await pilot.pause(0.2)
            city = await _wait_for(pilot, ChoiceScreen)
            seen["cities"] = [key for key, _ in city._options]
            city.dismiss("Lisbon")
            await pilot.pause(0.2)
            erase = await _wait_for(pilot, ConfirmScreen)
            seen["danger"] = erase._danger and "koha_library" in erase._question
            erase.query_one("#yes").press()
            word = await _wait_for(pilot, InputScreen)
            word.query_one("#value").value = "reinstall"
            word.query_one("#ok").press()
            await pilot.pause(0.2)
            seen["wrong"] = isinstance(app.screen, InputScreen)
            word.query_one("#value").value = "REINSTALL"
            word.query_one("#ok").press()
            loader = await _wait_for(pilot, LoadingScreen)
            seen["cancellable"] = loader.cancellable
            ready = await _wait_for(pilot, CredentialsScreen, tries=200)
            seen["values"] = ready._values
            ready.query_one("#ok").press()
            diag = await _wait_for(pilot, ConfirmScreen)
            diag.query_one("#yes").press()
            report = await _wait_for(pilot, TextScreen)
            report.query_one("#ok").press()
            await pilot.pause(0.2)
            reboot = await _wait_for(pilot, ConfirmScreen)
            reboot.query_one("#no").press()
            later = await _wait_for(pilot, MessageScreen)
            seen["later"] = later._kind
        return seen
    seen = asyncio.run(main())
    assert "apache2" in seen["ports"] and "VALIDATION REPORT" in seen["preview"]
    assert "America/Sao_Paulo" in seen["tz"] and seen["cities"] == ["Lisbon"]
    assert seen["danger"] and seen["wrong"] and not seen["cancellable"]
    assert "demo-Pa55word" in seen["values"] and seen["later"] == "info"


def test_credentials_have_one_copy_button_per_value():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("credentials")
            screen = await _wait_for(pilot, CredentialsScreen)
            screen.query_one("#copy-6").press()
            await pilot.pause(0.1)
            return screen._values, len(screen.query(".detail-copy"))
    values, buttons = asyncio.run(main())
    assert buttons == len(values) == 8 and values[6] == "demo-Pa55word"


def test_status_is_a_native_table():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("status")
            screen = await _wait_for(pilot, CredentialsScreen)
            return [g for g, _ in screen._groups], len(screen.query(".detail-copy"))
    groups, copies = asyncio.run(main())
    assert groups == ["SERVICES", "SEARCH", "MACHINE", "BACKUP"] and copies == 0


def test_health_shows_summary_and_report():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("health")
            screen = await _wait_for(pilot, TextScreen)
            return screen
    screen = asyncio.run(main())
    assert "No critical failures" in screen._body and "VALIDATION REPORT" in screen._text


def test_log_follow_shows_new_lines(tmp_path):
    from kei_panel.screens.logtail import LogTailScreen
    log = tmp_path / "intranet-error.log"
    log.write_text("".join(f"old line {i}\n" for i in range(80)))

    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            screen = LogTailScreen("Apache", str(log), interval=0.1)
            app.push_screen(screen)
            await pilot.pause(0.3)
            with log.open("a") as fh:
                fh.write("[error] DBI connect failed\n")
            await pilot.pause(0.5)
            from textual.widgets import RichLog
            lines = [strip.text for strip in screen.query_one(RichLog).lines]
            return lines
    lines = asyncio.run(main())
    text = "\n".join(lines)
    assert "old line 29" not in text and "old line 79" in text and "DBI connect failed" in text
