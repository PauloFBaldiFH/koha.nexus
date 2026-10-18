"""Edit & Map Fields in the panel (screens/fieldmap.py): the data grid over
the engine's real fields.json (rows = sample records, columns = fields), the
cell inspector, the live preview of the row under the cursor, the layouts,
the mapping it writes, the @@fieldmap prompt and the demo's magic import
walking through it."""

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
from kei_panel.screens.fieldmap import IGNORE, KEEP, OTHER, FieldMapScreen, warnings
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
        if i != 4:
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


def drive(screen, steps, size=(160, 50)):
    async def main():
        app = Host(screen)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            out = await steps(screen, pilot)
            await pilot.pause()
            return app.result, out
    return asyncio.run(main())


def preview(screen):
    return str(screen.query_one("#fm-preview", Static).render())


def inspect(screen):
    return str(screen.query_one("#fm-inspect", Static).render())


async def goto(screen, pilot, source, record=None):
    """The grid cursor on the cell of `source` (column) in `record` (row)."""
    grid = screen.query_one("#fm-grid")
    row = screen.record if record is None else record
    grid.move_cursor(row=row, column=[k[1] for k in screen._shown].index(source) + 1)
    await pilot.pause()


async def pick(screen, pilot, source, value):
    await goto(screen, pilot, source)
    screen.query_one("#fm-dest", Select).value = value
    await pilot.pause()


def test_grid_cells_inspector_and_skip(fields, tmp_path):
    d, path = fields
    target = tmp_path / "fieldmap.json"
    screen = FieldMapScreen("Edit field mapping", str(path), str(target), str(d))

    async def steps(screen, pilot):
        grid = screen.query_one("#fm-grid")
        size = (grid.row_count, len(grid.columns))
        await goto(screen, pilot, "500$a", 3)
        missing = inspect(screen), screen.record
        await goto(screen, pilot, "500$a", 1)
        cell = inspect(screen), str(screen.query_one("#fm-example", Label).render())
        shown = preview(screen)
        screen.query_one("#fm-skip").press()
        return size, missing, cell, shown
    result, (size, missing, cell, shown) = drive(screen, steps)
    assert result is False and not target.exists()
    assert size == (5, 4)                       # 5 records; # + 090$a 245$a 500$a
    assert screen.rows[("marc", "500$a")].proposal == "500$a" and screen.rows[("marc", "500$a")].count == 4
    assert "does not have this field" in missing[0] and missing[1] == 3
    assert "AUTOR 2" in cell[0] and "all in capitals" in cell[0] and "In 4 of 5" in cell[0]
    assert cell[1] == "Example 2 of 5"
    assert "500    $a AUTOR 2" in shown


def test_warnings():
    assert warnings(" x") and warnings("Ã©dition") and warnings("CASA GRANDE")
    assert warnings("978-85-359-0277-5") and not warnings("978-85-359-0277-5", "020$a")
    assert warnings("Casa grande") == [] and warnings("São Paulo") == [] and warnings("SÃO PAULO") == ["all in capitals"]


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
        header = str(screen.query_one("#fm-grid").columns[next(iter(
            k for k in screen.query_one("#fm-grid").columns if k.value == "marc\t500$a"))].label)
        screen.query_one("#fm-before").press()
        await pilot.pause()
        before = preview(screen)
        screen.query_one("#fm-apply").press()
        return after, count, second, before, header
    result, (after, count, second, before, header) = drive(screen, steps)
    assert result is True
    assert json.loads(target.read_text()) == {"version": 1, "mappings": [
        {"from": "090$a", "to": "082$a"}, {"from": "500$a", "to": "100$a"}]}
    assert "▸ 100 1  $a AUTOR 1" in after and "▸ 082 04 $a 869.3" in after and "500    $a" not in after
    assert count.startswith("2 ") and "AUTOR 2" in second and "→ 100$a" in header
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


def test_stepper_filter_and_problems(fields, tmp_path):
    d, path = fields
    screen = FieldMapScreen("Edit field mapping", str(path), str(tmp_path / "m.json"), str(d))

    async def steps(screen, pilot):
        await goto(screen, pilot, "245$a", 0)
        await pilot.press("right_square_bracket", "right_square_bracket")
        stepped = screen.record, screen.query_one("#fm-grid").cursor_coordinate.row, preview(screen)
        await pilot.press("left_square_bracket", "left_square_bracket", "left_square_bracket")
        wrapped = screen.record
        await pick(screen, pilot, "090$a", "082$a")
        screen.query_one("#fm-show", Select).value = "changed"
        await pilot.pause()
        changed = [k[1] for k in screen._shown]
        screen.query_one("#fm-show", Select).value = "problems"
        await pilot.pause()
        problems = [k[1] for k in screen._shown]
        return stepped, wrapped, changed, problems
    _, (stepped, wrapped, changed, problems) = drive(screen, steps)
    assert stepped[:2] == (2, 2) and "Livro 3" in stepped[2] and wrapped == 4
    assert changed == ["090$a"]
    assert problems == ["500$a"]                # in capitals, and missing in record 4


def test_narrow_terminal_uses_tabs(fields, tmp_path):
    d, path = fields
    screen = FieldMapScreen("Edit field mapping", str(path), str(tmp_path / "m.json"), str(d))

    async def steps(screen, pilot):
        dialog = screen.query_one(".fieldmap")
        first = (dialog.has_class("-stacked"), screen.query_one("#fm-left").display,
                 screen.query_one("#fm-preview-card").display)
        await pilot.press("p")
        second = (screen.query_one("#fm-left").display, screen.query_one("#fm-preview-card").display)
        await goto(screen, pilot, "500$a")
        await pilot.press("enter")              # Enter on a cell: on to its destination
        third = screen.pane, isinstance(screen.focused, Select)
        fits = screen.query_one("#fm-foot").region.bottom <= screen.size.height
        return first, second, third, fits
    _, (first, second, third, fits) = drive(screen, steps, size=(80, 24))
    assert first == (True, True, False) and second == (False, True)
    assert third == ("map", True) and fits


def test_wide_terminal_side_by_side(fields, tmp_path):
    d, path = fields
    screen = FieldMapScreen("Edit field mapping", str(path), str(tmp_path / "m.json"), str(d))

    async def steps(screen, pilot):
        return (screen.query_one(".fieldmap").has_class("-stacked"), screen.query_one("#fm-tabs").display,
                screen.query_one("#fm-left").region.y == screen.query_one("#fm-preview-card").region.y)
    _, out = drive(screen, steps)
    assert out == (False, False, True)


def test_spreadsheet_grid(tmp_path):
    """A table: ten rows under its headers, and a mapping of a column."""
    data = {"version": 1, "sample": 10, "targets": [{"to": "100$a", "label": "Author"}], "streams": [],
            "columns": [{"table": "acervo.csv", "from": "Autor", "to": "100$a", "samples": ["A"]},
                        {"table": "acervo.csv", "from": "Obs", "to": "", "samples": []}],
            "tables": [{"name": "acervo.csv", "kind": "table", "headers": ["Autor", "Obs"], "rows_total": 40,
                        "rows": [["Autor %d" % i, "" if i % 2 else "nota"] for i in range(10)]}]}
    src, target = tmp_path / "fields.json", tmp_path / "m.json"
    src.write_text(json.dumps(data))
    screen = FieldMapScreen("Edit field mapping", str(src), str(target), "")

    async def steps(screen, pilot):
        grid = screen.query_one("#fm-grid")
        size = grid.row_count, len(grid.columns)
        label = str(screen.query_one("#fm-group-label", Label).render())
        await goto(screen, pilot, "Obs", 2)
        shown = preview(screen)
        await pick(screen, pilot, "Obs", OTHER)
        custom = screen.query_one("#fm-custom", Input)
        custom.value = "500$a"
        await custom.action_submit()
        await pilot.pause()
        screen.query_one("#fm-apply").press()
        return size, label, shown
    result, (size, label, shown) = drive(screen, steps)
    assert size == (10, 3) and "40" in label and "sample of 10" in label
    assert "Autor 2" in shown and "nota" in shown
    assert result is True
    assert json.loads(target.read_text())["mappings"] == [{"from": "Obs", "to": "500$a", "kind": "column"}]
