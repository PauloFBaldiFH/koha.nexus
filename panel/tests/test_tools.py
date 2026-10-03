"""Phases 8 and 9: every other routine through `--task run ACTION`, its
boxes asked in the panel (demo.py simulates the installer)."""

import asyncio
import os
import subprocess
from pathlib import Path

import pytest
from conftest import INSTALLER
from test_routines import _app, _wait_for

from kei_panel.bridge import TaskOutcome, answer_prompt
from kei_panel.screens.dialogs import ChecklistScreen, ChoiceScreen, EditScreen, MessageScreen, TextScreen
from kei_panel.screens.files import PathPickerScreen


def test_new_prompt_lines_are_answered():
    asked = []

    async def ask(out, kind, title, text, extra):
        asked.append((kind, title, extra))
        return {"check": ["a", "c"], "file": "/root/x.mrc", "edit": True}.get(kind, True)

    async def main():
        out = TaskOutcome()
        replies = []
        for line in ["@@check T\tPick:\ta\tA\tON\tb\tB\tOFF\tc\tC\tOFF",
                     "@@file file\tFiles\tPick one:\t/root\tmrc xml",
                     "@@edit Cron\t/etc/cron.d/koha_tasks\tOnly numbers",
                     "@@say ok OK\tDone!", "@@view About\tline 1\\nline 2"]:
            out.feed(line)
            replies.append(await answer_prompt(out, line, ask))
        return out, replies
    out, replies = asyncio.run(main())
    assert replies == ["ok a\tc", "ok /root/x.mrc", "ok", "ok", "ok"]
    assert asked[0] == ("check", "T", [("a", "A", True), ("b", "B", False), ("c", "C", False)])
    assert asked[1] == ("file", "Files", ("file", "/root", ["mrc", "xml"]))
    assert asked[2] == ("edit", "Cron", "/etc/cron.d/koha_tasks")
    assert out.already_said(out.last("ok")) and out.previews == [("About", "line 1\nline 2")]


def test_cloudflare_menu_loops_and_ends_quietly():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("cloudflare")
            menu = await _wait_for(pilot, ChoiceScreen)
            keys = [k for k, _ in menu._options]
            menu.dismiss("5")
            box = await _wait_for(pilot, MessageScreen)
            body = box._body
            box.query_one("#ok").press()
            again = await _wait_for(pilot, ChoiceScreen)
            again.dismiss(None)
            await pilot.pause(0.8)
            return keys, body, type(app.screen).__name__
    keys, body, last = asyncio.run(main())
    # The box was shown while the routine ran: not again at the end.
    assert keys == ["1", "5"] and "restarted" in body and last not in ("MessageScreen", "LoadingScreen")


def test_schedules_are_edited_in_the_panel():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("crons")
            (await _wait_for(pilot, ChoiceScreen)).dismiss("4")
            editor = await _wait_for(pilot, EditScreen)
            area = editor.query_one("#editor")
            area.text = area.text.replace("0 23", "30 22")
            editor.query_one("#save").press()
            done = await _wait_for(pilot, MessageScreen)
            return Path(editor._path).read_text(), done._kind
    text, kind = asyncio.run(main())
    assert "30 22 * * *" in text and kind == "ok"


def test_checklist_file_picker_and_long_text():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("brazil")
            check = await _wait_for(pilot, ChecklistScreen)
            selected = list(check.query_one("SelectionList").selected)
            check.query_one("#ok").press()
            (await _wait_for(pilot, MessageScreen)).query_one("#ok").press()
            await pilot.pause(0.5)
            app.run_native("magic-import")
            picker = await _wait_for(pilot, PathPickerScreen)
            mode = picker._mode
            picker.dismiss(None)
            await pilot.pause(0.5)
            app.run_native("about")
            about = await _wait_for(pilot, TextScreen)
            return selected, mode, about._text
    selected, mode, text = asyncio.run(main())
    assert selected == ["6180"] and mode == "file" and "Baldi" in text


def test_new_language_restarts_the_panel():
    async def main():
        app = _app()
        app.env.lang = "pt"
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("languages")
            menu = await _wait_for(pilot, ChoiceScreen)
            default = menu._default
            menu.dismiss("en")
            (await _wait_for(pilot, MessageScreen)).query_one("#ok").press()
            for _ in range(30):
                await pilot.pause(0.1)
                if app.return_code is not None:
                    break
            return default, app.return_code
    assert asyncio.run(main()) == ("pt-BR", 3)


def test_terminal_tools_get_the_terminal():
    async def main():
        app = _app()
        handed = []
        app.bridge.run_command_interactive = lambda _app, argv: handed.append(argv) or 0
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("monitor")
            (await _wait_for(pilot, ChoiceScreen)).dismiss("2")
            for _ in range(30):
                await pilot.pause(0.1)
                if handed:
                    break
            return handed
    assert asyncio.run(main()) == [["nethogs", "eth0"]]


@pytest.mark.skipif(os.geteuid() != 0, reason="the installer runs as root")
def test_installer_runs_a_classic_routine_as_a_task():
    """The real About routine: its text box comes as @@view and waits."""
    proc = subprocess.run(["bash", str(INSTALLER), "--task", "run", "about"], input="ok\n",
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60,
                          env={**os.environ, "KEI_TASK_INTERACTIVE": "1"})
    views = [ln for ln in proc.stdout.splitlines() if ln.startswith("@@view ")]
    assert proc.returncode == 0 and len(views) == 1 and "Baldi" in views[0]
    bad = subprocess.run(["bash", str(INSTALLER), "--task", "run", "no-such-action"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    assert bad.returncode == 2
