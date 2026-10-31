"""Discover new servers (Z39 Atlas) on the Z39.50 screen, headless in demo mode."""

import asyncio
import os
import time

from conftest import INSTALLER, REPO

from kei_panel import z3950, z39atlas
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ChecklistScreen, ConfirmScreen, MessageScreen

TOOL = REPO / "tools" / "harvesters" / "z39-atlas-2.0" / "z39-atlas" / "z39atlas.py"


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


async def _press(pilot, app, button_id):
    app.screen.query_one(f"#{button_id}").press()
    await pilot.pause(0.1)


def test_panel_copy_is_the_tool():
    """The panel ships z39atlas.py; tools/harvesters keeps the standalone copy."""
    assert (z3950.Path(z39atlas.__file__).read_bytes() == TOOL.read_bytes()), \
        "panel/kei_panel/z39atlas.py and tools/.../z39atlas.py differ: copy one over the other"


def test_summary_lines():
    from kei_panel.views.z3950 import atlas_summary
    assert atlas_summary({"status": "idle"}) == "No discovery run yet."
    line = atlas_summary({"status": "running", "phase": "probe", "percent": 60, "targets_done": 5,
                          "targets_total": 10, "approved": 2})
    assert "60%" in line and "5/10" in line and "2" in line
    line = atlas_summary({"status": "interrupted", "approved": 1, "confirmed_total": 4})
    assert "Interrupted" in line and "continues" in line


def test_discover_check_and_add_new_servers(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp
    from kei_panel.views import z3950 as zview
    launched = []
    real_launch = zview.launch_atlas
    monkeypatch.setattr(zview, "launch_atlas", lambda args, demo=False: (launched.append(args),
                                                                         real_launch(args, demo)))

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            await _until(pilot, lambda: view.ticks_from_koha)
            assert "No discovery run yet" in str(view.query_one("#z-atlas-state").render())

            # Start: a confirmation, then the run goes to the background.
            view.atlas_start()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "background" in app.screen._question
            await _press(pilot, app, "yes")
            await _until(pilot, lambda: bool(launched))
            args = launched[0]
            assert args[0] == "--published" and args.count("--known") == 2
            known = (tmp_path / "z39-atlas" / "known.txt").read_text()
            assert "catalog.koha.nexus:443/sru" in known and "z3950.ufsc.br:210/default" in known
            await _until(pilot, lambda: "Finished" in str(view.query_one("#z-atlas-state").render()))

            # Check scan status: the numbers of the run.
            view.atlas_status()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            details = dict(app.screen._details)
            assert details["State"] == "Finished" and details["Returned a MARC record"] == "2"
            assert "New servers ready to add: 2" in app.screen._body
            await _press(pilot, app, "ok")
            await _until(pilot, lambda: not isinstance(app.screen, MessageScreen))

            # New servers found: checkboxes, nothing ticked; then Save to Koha's confirmation.
            tasks, seen = [], {}
            task = app.bridge.task

            async def spy_task(name, *a, **kw):
                tasks.append(name)
                if name == "z3950-add":
                    seen["add"] = open(a[0], encoding="utf-8").read()
                return await task(name, *a, **kw)
            monkeypatch.setattr(app.bridge, "task", spy_task)
            view.atlas_new()
            await _until(pilot, lambda: isinstance(app.screen, ChecklistScreen))
            opts = app.screen._options
            assert {k for k, _l, _on in opts} == {"z3950.demo-library.org:210/BIBLIO",
                                                   "catalog.demo-univ.edu:2100/MAIN"}
            assert not any(on for _k, _l, on in opts)
            from textual.widgets import SelectionList
            app.screen.query_one(SelectionList).select("z3950.demo-library.org:210/BIBLIO")
            await _press(pilot, app, "ok")
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "Add 1 new server(s)" in app.screen._question
            assert not tasks                         # nothing reached Koha before this confirmation
            await _press(pilot, app, "yes")
            await _until(pilot, lambda: "z3950-add" in tasks)
            assert seen["add"].startswith("z3950.demo-library.org\t210\tBIBLIO\t")
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            await _press(pilot, app, "ok")
            assert view.by_key("z3950.demo-library.org:210/BIBLIO") is not None
            # Now in the list: only the other one is still new.
            assert [r["host"] for r in view._atlas_new_rows()] == ["catalog.demo-univ.edu"]

    asyncio.run(main())


def test_missing_yaz_starts_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp
    from kei_panel.views import z3950 as zview
    monkeypatch.setattr(zview, "yaz_available", lambda demo=False: False)
    monkeypatch.setattr(zview, "launch_atlas", lambda *a, **k: (_ for _ in ()).throw(AssertionError("started")))

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            view.atlas_start()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert "not installed" in app.screen._body and app.screen._command == "sudo apt install -y yaz"
            assert not (tmp_path / "z39-atlas" / "atlas.sqlite3").exists()

    asyncio.run(main())


def test_running_state_and_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp
    from kei_panel.views import z3950 as zview
    db = zview.atlas_db()
    con = z39atlas.init_db(db)
    z39atlas.set_state(con, status="running", phase="probe", pid=os.getpid(), pages_done=5, pages_total=5,
                       targets_done=3, targets_total=12, approved=1)
    con.close()
    stops = []
    monkeypatch.setattr(z39atlas, "stop_run", lambda path: stops.append(path) or True)

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        notes = []
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            monkeypatch.setattr(app, "notify", lambda msg, **kw: notes.append(str(msg)))
            await _until(pilot, lambda: "3/12" in str(view.query_one("#z-atlas-state").render()))
            assert not view.query_one("#z-atlas-stop").disabled
            # A second start while one runs only says how far it is.
            view.atlas_start()
            await _until(pilot, lambda: any("3/12" in n for n in notes))
            assert not isinstance(app.screen, ConfirmScreen)
            view.atlas_stop()
            assert stops == [db]

    asyncio.run(main())
