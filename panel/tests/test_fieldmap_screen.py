"""Edit & Map Fields in the panel (screens/fieldmap.py): the mapping screen
over the engine's real fields.json, its live preview, the mapping it writes,
the @@fieldmap prompt and the demo's magic import walking through it."""

import asyncio
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import INSTALLER
from test_routines import _app, _wait_for
from textual.app import App
from textual.widgets import Input, Label, Select, Static

from kei_panel.bridge import TaskOutcome, answer_prompt
from kei_panel.screens.dialogs import ConfirmScreen
from kei_panel.screens.fieldmap import IGNORE, KEEP, OTHER, FieldMapScreen
from kei_panel.screens.files import PathPickerScreen


@pytest.fixture(scope="module")
def fields(tmp_path_factory):
    """The engine (written out of the installer), a legacy MARCXML file, its
    direct build and the fields.json the screen reads."""
    d = tmp_path_factory.mktemp("kei")
    text = INSTALLER.read_text(encoding="utf-8")
    for m in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n', text, re.S):
        f = d / m.group(1)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(m.group(2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(d))
    for name in [n for n in sys.modules if n == "kei_import" or n.startswith("kei_import.")]:
        del sys.modules[name]
    marc = importlib.import_module("kei_import.marc")
    sys.path.remove(str(d))
    recs = []
    for i in range(1, 6):
        r = marc.Record()
        r.add("245", "1", "0", ("a", "Livro %d" % i))
        r.add("500", " ", " ", ("a", "AUTOR %d" % i))
        r.add("090", " ", " ", ("a", "869.3"))
        recs.append(r)
    src = d / "isis.xml"
    marc.write_marcxml(recs, str(src))
    work = d / "work"
    work.mkdir()
    base = [sys.executable, str(d / "kei_import_run.py")]
    opts = ["--in", str(src), "--work", str(work), "--branch", "CPL", "--itype", "BK"]
    for cmd in ("build", "fields"):
        p = subprocess.run(base + [cmd] + opts, capture_output=True, text=True, cwd=d)
        assert p.returncode == 0, p.stdout + p.stderr
    return d, work / "fields.json"


class Host(App):
    def __init__(self, screen):
        super().__init__()
        self.screen_ = screen
        self.result = "unset"

    def on_mount(self) -> None:
        self.push_screen(self.screen_, lambda r: setattr(self, "result", r))


def drive(screen, steps):
    async def main():
        app = Host(screen)
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            out = await steps(screen, pilot)
            await pilot.pause()
            return app.result, out
    return asyncio.run(main())


def preview(screen):
    return str(screen.query_one("#fm-preview", Static).render())


async def pick(screen, pilot, source, value):
    table = screen.query_one("#fm-table")
    table.move_cursor(row=[k[1] for k in screen._shown].index(source))
    await pilot.pause()
    screen.query_one("#fm-dest", Select).value = value
    await pilot.pause()


def test_rows_samples_and_skip(fields, tmp_path):
    d, path = fields
    target = tmp_path / "fieldmap.json"
    screen = FieldMapScreen("Edit field mapping", str(path), str(target), str(d))

    async def steps(screen, pilot):
        rows = {k[1]: r for k, r in screen.rows.items()}
        shown = preview(screen)
        screen.query_one("#fm-skip").press()
        return rows, shown
    result, (rows, shown) = drive(screen, steps)
    assert result is False and not target.exists()
    assert rows["500$a"].samples[:2] == ["AUTOR 1", "AUTOR 2"] and rows["500$a"].proposal == "500$a"
    assert "500    $a AUTOR 1" in shown


def test_mapping_preview_and_apply(fields, tmp_path):
    d, path = fields
    target = tmp_path / "fieldmap.json"
    screen = FieldMapScreen("Edit field mapping", str(path), str(target), str(d))

    async def steps(screen, pilot):
        await pick(screen, pilot, "500$a", "100$a")
        await pick(screen, pilot, "090$a", "082$a")
        after = preview(screen)
        count = str(screen.query_one("#fm-count", Label).render())
        screen.query_one("#fm-next").press()
        await pilot.pause()
        second = preview(screen)
        screen.query_one("#fm-before").press()
        await pilot.pause()
        before = preview(screen)
        screen.query_one("#fm-apply").press()
        return after, count, second, before
    result, (after, count, second, before) = drive(screen, steps)
    assert result is True
    assert json.loads(target.read_text()) == {"version": 1, "mappings": [
        {"from": "090$a", "to": "082$a"}, {"from": "500$a", "to": "100$a"}]}
    assert "▸ 100 1  $a AUTOR 1" in after and "▸ 082 04 $a 869.3" in after and "500    $a" not in after
    assert count.startswith("2 ") and "AUTOR 2" in second
    assert "500    $a AUTOR" in before


def test_custom_and_ignore(fields, tmp_path):
    d, path = fields
    target = tmp_path / "fieldmap.json"
    screen = FieldMapScreen("Edit field mapping", str(path), str(target), str(d))

    async def steps(screen, pilot):
        await pick(screen, pilot, "500$a", OTHER)
        custom = screen.query_one("#fm-custom", Input)
        shown = custom.display
        custom.value = "59$a"
        await custom.action_submit()
        await pilot.pause()
        bad = str(screen.query_one("#fm-error", Label).render())
        custom.value = "590$a"
        await custom.action_submit()
        await pilot.pause()
        await pick(screen, pilot, "090$a", IGNORE)
        screen.query_one("#fm-apply").press()
        return shown, bad
    result, (shown, bad) = drive(screen, steps)
    assert result is True and shown and "TAG$subfield" in bad
    assert json.loads(target.read_text())["mappings"] == [{"from": "090$a", "to": "ignore"}, {"from": "500$a", "to": "590$a"}]


def test_keep_and_reset_mean_no_mapping(fields, tmp_path):
    d, path = fields
    target = tmp_path / "fieldmap.json"
    screen = FieldMapScreen("Edit field mapping", str(path), str(target), str(d))

    async def steps(screen, pilot):
        await pick(screen, pilot, "500$a", "100$a")
        await pick(screen, pilot, "500$a", KEEP)
        await pick(screen, pilot, "090$a", "082$a")
        screen.query_one("#fm-reset").press()
        await pilot.pause()
        screen.query_one("#fm-apply").press()
    result, _ = drive(screen, steps)
    assert result is False and not target.exists()


def test_without_the_engine_it_still_maps(fields, tmp_path):
    _, path = fields
    target = tmp_path / "fieldmap.json"
    screen = FieldMapScreen("Edit field mapping", str(path), str(target), "")

    async def steps(screen, pilot):
        await pick(screen, pilot, "500$a", "100$a")
        shown = preview(screen)
        screen.query_one("#fm-apply").press()
        return shown
    result, shown = drive(screen, steps)
    assert result is True and "engine" in shown
    assert json.loads(target.read_text())["mappings"] == [{"from": "500$a", "to": "100$a"}]


def test_the_prompt_line_is_answered():
    asked = []

    async def ask(out, kind, title, text, extra):
        asked.append((kind, title, extra))
        return len(asked) == 1

    async def main():
        out = TaskOutcome()
        line = "@@fieldmap Edit field mapping\t/w/fields.json\t/w/fieldmap.json\t/w/kei"
        out.feed(line)
        return [await answer_prompt(out, line, ask), await answer_prompt(out, line, ask)]
    assert asyncio.run(main()) == ["ok", "cancel"]
    assert asked[0] == ("fieldmap", "Edit field mapping", ("/w/fields.json", "/w/fieldmap.json", "/w/kei"))


def test_demo_magic_import_offers_the_mapping():
    async def main():
        app = _app()
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("magic-import")
            (await _wait_for(pilot, PathPickerScreen)).dismiss(Path("/root/acervo.iso"))
            for _ in range(300):
                await pilot.pause(0.1)
                if isinstance(app.screen, ConfirmScreen) and app.screen.is_mounted and app.screen.query("Button"):
                    break
            question = app.screen._question if isinstance(app.screen, ConfirmScreen) else ""
            app.screen.dismiss(True)
            screen = await _wait_for(pilot, FieldMapScreen)
            rows = [k[1] for k in screen._shown]
            screen.query_one("#fm-skip").press()
            gate = await _wait_for(pilot, ConfirmScreen)
            text = gate._question
            gate.dismiss(False)
            await pilot.pause(0.5)
            return question, rows, text
    question, rows, gate = asyncio.run(main())
    assert "field mapping" in question and "500$a" in rows and "Ready to import" in gate
