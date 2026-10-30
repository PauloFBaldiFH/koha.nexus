"""The Z39.50 / SRU screen, driven headless in demo mode."""

import asyncio
import json
import time

from conftest import INSTALLER
from textual.widgets import DataTable

from kei_panel import z3950
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ConfirmScreen, InputScreen, MessageScreen
from kei_panel.screens.loading import LoadingScreen


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_show_servers_backups_ticks_and_save_to_koha(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp
    from kei_panel.views import z3950 as zview

    curated = z3950.load_curated()
    ufsc = next(t for t in curated if t.key == "z3950.ufsc.br:210/Default")
    ufsc_backup = next(t for t in curated if t.db == "sru/ufsc")
    loc = next(t for t in curated if t.key == "lx2.loc.gov:210/LCDB")
    loc_backup = next(t for t in curated if t.db == "sru/loc")
    utfpr = next(t for t in curated if t.db == "biblioteca")
    catalog = next(t for t in curated if t.host == "catalog.koha.nexus")
    assert ufsc_backup.backup and ufsc_backup.backup_for == ufsc.key and loc_backup.backup_for == loc.key
    real_scan = zview._demo_scan
    tested = []

    async def scan_ufsc_empty(targets, each):
        """The demo scan, but UFSC answers without a record."""
        def mine(tg, res):
            if tg.key == ufsc.key:
                res.status = "empty"
            each(tg, res)
        tested.extend(tg.key for tg in targets)
        out = await real_scan(targets, mine)
        for res in out:
            if res.key == ufsc.key:
                res.status = "empty"
        return out
    monkeypatch.setattr(zview, "_demo_scan", scan_ufsc_empty)

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            table = view.query_one("#z-table", DataTable)
            rows = lambda: [k.value for k in table.rows if not k.value.startswith("region:")]  # noqa: E731

            # Before any test: only the servers Koha searches (its checked rows), ticked.
            await _until(pilot, lambda: view.ticks_from_koha)
            assert view.selected == {catalog.key, loc.key}
            assert set(rows()) == {catalog.key, loc.key}
            assert str(view.query_one("#z-scan").label) == "Show servers"
            assert "press the blue Show servers" in str(view.query_one("#z-summary").render())
            assert view.query_one("#z-summary").has_class("-todo")
            assert "at most 20" in str(view.query_one("#z-limit").render())
            assert "In Koha" in table.get_row(loc.key)[2]

            # Show servers: every server is tested, then the backups of the ones without a record.
            view.scan()
            await pilot.pause(0.1)
            assert isinstance(app.screen, LoadingScreen)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen), wait=30)
            assert str(view.query_one("#z-scan").label) == "Update"
            history = json.loads((tmp_path / z3950.HISTORY_FILE).read_text())
            assert history[z3950.TESTED_KEY] > 0
            # UFSC returned no record: its backup was tested and stands in; LoC's backup was not needed.
            assert ufsc_backup.key in tested and loc_backup.key not in tested
            shown = set(rows())
            assert ufsc.key not in shown and ufsc_backup.key in shown and loc_backup.key not in shown
            assert utfpr.key in shown and "Working" in table.get_row(utfpr.key)[2]
            # A server that needs a login it does not have answers without a record: hidden.
            assert not [t for t in curated if t.login and t.key in shown]
            # "Show all" brings back everything, "Only working" the test's list.
            view.toggle_hidden()
            assert len(rows()) == len(curated)
            view.toggle_hidden()
            assert set(rows()) == shown

            # More than 20 ticked: advised against in the warning colour, never refused.
            limit = view.query_one("#z-limit")
            view.toggle("region:europe")
            assert z3950.most_ticked(view.targets, view.selected) > 20 and limit.has_class("-over")
            assert "Now " in str(limit.render())
            view.toggle("region:europe")
            assert not limit.has_class("-over")

            # Select / Unselect for search: the server under the cursor, or a whole region.
            table.move_cursor(row=table.get_row_index("region:brazil"))
            await _click(pilot, view, "z-tick")
            brazil = {t.key for t in view.visible() if t.region == "brazil"}
            assert brazil <= view.selected
            await _click(pilot, view, "z-untick")
            assert not brazil & view.selected
            table.move_cursor(row=table.get_row_index(catalog.key))
            await _click(pilot, view, "z-untick")
            assert catalog.key not in view.selected
            await _click(pilot, view, "z-tick")
            assert catalog.key in view.selected
            await _click(pilot, view, "z-untick-all")
            assert view.selected == set()
            view.selected = {catalog.key, loc.key}

            # Save to Koha: add UTFPR, tick UFSC (in Koha, unticked), untick LoC.
            view.set_ticks(True, utfpr.key)
            view.set_ticks(True, ufsc.key)
            view.set_ticks(False, loc.key)
            assert ufsc.key in rows() and loc.key in rows()      # ticked or in Koha: still listed to untick
            seen, tasks = {}, []
            real_add, real_check = z3950.write_add_file, z3950.write_check_file

            def spy_add(targets, ranks):
                path = real_add(targets, ranks)
                seen["add"] = path.read_text()
                return path

            def spy_check(changes):
                path = real_check(changes)
                seen["check"] = path.read_text()
                return path
            monkeypatch.setattr(z3950, "write_add_file", spy_add)
            monkeypatch.setattr(z3950, "write_check_file", spy_check)
            task = app.bridge.task

            async def spy_task(name, *args, **kw):
                tasks.append(name)
                return await task(name, *args, **kw)
            monkeypatch.setattr(app.bridge, "task", spy_task)
            view.add()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            preview = app.screen._preview
            assert "+ " in preview and "☑ UFSC" in preview and "☐ " in preview
            assert "Add 1 new server(s)" in app.screen._question
            await _press(pilot, app, "yes")
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert tasks[:2] == ["z3950-add", "z3950-check"]
            assert seen["add"].startswith("z3950.utfpr.edu.br\t210\tbiblioteca\t")
            assert sorted(seen["check"].splitlines()) == sorted(["z3950.ufsc.br\t210\tDefault\tbiblio\t1",
                                                                  "lx2.loc.gov\t210\tLCDB\tbiblio\t0"])
            assert "1 server(s) ticked, 1 unticked" in app.screen._body
            await _press(pilot, app, "ok")

            # Hide one by hand: gone from the list and the ticks, not tested again.
            await _until(pilot, lambda: not isinstance(app.screen, MessageScreen))
            table.move_cursor(row=table.get_row_index(utfpr.key))
            view.hide()
            assert utfpr.key not in rows() and utfpr.key not in view.selected

            # A login: typed in the panel, kept privately, never shown.
            table.move_cursor(row=table.get_row_index(catalog.key))
            view.login()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen))
            app.screen.query_one("#value").value = "librarian"
            await _press(pilot, app, "ok")
            await _until(pilot, lambda: isinstance(app.screen, InputScreen) and app.screen._password)
            app.screen.query_one("#value").value = "s3cret-pw"
            await _press(pilot, app, "ok")
            await _until(pilot, lambda: (tmp_path / z3950.LOCAL_FILE).exists())
            saved = (tmp_path / z3950.LOCAL_FILE)
            assert saved.stat().st_mode & 0o777 == 0o600 and "s3cret-pw" in saved.read_text()
            assert all("s3cret-pw" not in str(c) for k in table.rows for c in table.get_row(k))

    asyncio.run(main())


def test_a_cancelled_test_keeps_what_it_found(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp
    from kei_panel.views import z3950 as zview
    real_scan = zview._demo_scan

    async def slow_after_ten(targets, each):
        out = []
        for i, tg in enumerate(targets):
            if i == 10:
                await asyncio.sleep(60)          # the person gives up and cancels here
            out += await real_scan([tg], each)
        return out
    monkeypatch.setattr(zview, "_demo_scan", slow_after_ten)

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        notes = []
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            monkeypatch.setattr(app, "notify", lambda msg, **kw: notes.append(str(msg)))
            view.scan()
            await _until(pilot, lambda: isinstance(app.screen, LoadingScreen))
            await pilot.pause(1.5)
            app.screen.action_cancel()
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            await _until(pilot, lambda: any("Test stopped after 10 servers" in n for n in notes))
            assert view.history.tested and str(view.query_one("#z-scan").label) == "Update"
            assert sum(view.history.works(t.key) for t in view.targets) >= 8
            assert not view.query_one("#z-summary").has_class("-todo")

    asyncio.run(main())


def test_add_server_by_hand_is_tested_and_ticked(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            view.new_server()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen))
            app.screen.query_one("#value").value = "not an address"
            await _press(pilot, app, "ok")
            assert isinstance(app.screen, InputScreen)            # refused, still asking
            app.screen.query_one("#value").value = "z.minha.example.br:2100/acervo"
            await _press(pilot, app, "ok")
            await _until(pilot, lambda: isinstance(app.screen, InputScreen) and
                         app.screen.query_one("#value").value == "z.minha.example.br")
            app.screen.query_one("#value").value = "Minha rede"
            await _press(pilot, app, "ok")
            key = "z.minha.example.br:2100/acervo"
            await _until(pilot, lambda: view.history.get(key).get("status") == "dead")
            # Ticked, so listed even without a record (to be unticked), and kept privately.
            assert key in view.selected and key in [k.value for k in view.query_one("#z-table").rows]
            assert "Minha rede" in (tmp_path / z3950.LOCAL_FILE).read_text()

    asyncio.run(main())


def test_import_and_export(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    src = tmp_path / "mine.csv"
    src.write_text("name,host,port,db\nMy consortium,z.consortium.example.br,2100,acervo\n")
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            table = view.query_one("#z-table", DataTable)
            view.import_list()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen))
            app.screen.query_one("#value").value = str(src)
            await _press(pilot, app, "ok")
            key = "z.consortium.example.br:2100/acervo"
            # Tested at once: no record (demo mode), so it is listed only with "Show all".
            await _until(pilot, lambda: view.history.get(key).get("status") == "dead")
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            assert key not in [k.value for k in table.rows]
            view.toggle_hidden()
            assert table.get_row(key)[1] == "My consortium *"
            assert "z.consortium.example.br" in (tmp_path / z3950.LOCAL_FILE).read_text()

            view.selected.clear()
            view.toggle(key)
            view.export()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen))
            out = tmp_path / "out.sql"
            app.screen.query_one("#value").value = str(out)
            await _press(pilot, app, "ok")
            await _until(pilot, out.exists)
            assert "z.consortium.example.br" in out.read_text() and "lx2.loc.gov" not in out.read_text()

            view.sync()
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            assert key in [k.value for k in table.rows]           # the community list keeps mine

    asyncio.run(main())


async def _click(pilot, view, button_id):
    """Press a button of the screen (it may be scrolled out of sight)."""
    view.query_one(f"#{button_id}").press()
    await pilot.pause(0.1)


async def _press(pilot, app, button_id):
    """Press a dialog button once the dialog has drawn it."""
    await _until(pilot, lambda: bool(app.screen.query(f"#{button_id}")))
    app.screen.query_one(f"#{button_id}").press()
    await pilot.pause(0.05)


def test_inbound_server_and_community_network(tmp_path, monkeypatch):
    """Top and middle of the screen: the switches show the state the status
    task reads, ask before acting, and run the task with the network's address."""
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    (tmp_path / "kei.env").write_text("KEI_CATALOG_NETWORK_URL=https://catalogo.example.org/sru\n")
    monkeypatch.setenv("KEI_ENV_FILE", str(tmp_path / "kei.env"))
    from kei_panel.app import KohaPanelApp
    from textual.widgets import Switch

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        calls = []
        real_task = app.bridge.task

        async def spy(name, *args, **kwargs):
            calls.append((name, *args))
            return await real_task(name, *args, **kwargs)
        monkeypatch.setattr(app.bridge, "task", spy)
        async with app.run_test(size=(150, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            view = app.screen.query_one("#view-z3950")
            daemon = view.query_one("#z-daemon", Switch)
            net = view.query_one("#z-net", Switch)
            await _until(pilot, lambda: not daemon.disabled, wait=20)
            assert daemon.value is True and net.value is False
            assert "Running · port 2100" in str(view.query_one("#z-daemon-state").render())
            assert "Not in Koha" in str(view.query_one("#z-net-state").render())
            assert "https://catalogo.example.org/sru" in str(view.query_one("#z-net-note").render())
            assert view.query_one("#z-inbound").border_title.startswith("This catalogue")

            # The network: asked first, then the task gets the address.
            net.value = True
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "https://catalogo.example.org/sru" in app.screen._question
            await _press(pilot, app, "yes")
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert ("catalog-network", "on", "https://catalogo.example.org/sru") in calls
            await _press(pilot, app, "ok")

            # The daemon: "no" puts the switch back and runs nothing.
            await _until(pilot, lambda: not isinstance(app.screen, MessageScreen))
            await _until(pilot, lambda: not [w for w in app.workers if w.group in ("routine", "z3950-server")
                                             and w.is_running], wait=20)
            daemon.value = False
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await _press(pilot, app, "no")
            await _until(pilot, lambda: daemon.value is True)
            assert not [c for c in calls if c[0] == "z3950-daemon"]
            daemon.value = False
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await _press(pilot, app, "yes")
            await _until(pilot, lambda: ("z3950-daemon", "off") in calls)

    asyncio.run(main())


def test_network_address_falls_back_to_the_default(monkeypatch, tmp_path):
    monkeypatch.setenv("KEI_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.delenv("KEI_CATALOG_NETWORK_URL", raising=False)
    assert z3950.network_url() == z3950.NETWORK_URL
    monkeypatch.setenv("KEI_CATALOG_NETWORK_URL", "https://x.example.org:8443/sru")
    assert z3950.network_url() == "https://x.example.org:8443/sru"
    monkeypatch.setenv("KEI_CATALOG_NETWORK_URL", "javascript:alert(1)")
    assert z3950.network_url() == z3950.NETWORK_URL


def test_one_blue_button_shows_then_updates(tmp_path, monkeypatch):
    """One button (Paulo 2026-10-30): the first press only tests the list
    (Show servers); once tested it reads Update, which refreshes Koha's own
    rows (z3950-sync, the old yellow "Update server settings") and then
    tests the whole list again."""
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            # The yellow button is gone.
            assert not view.query("#z-update")
            seen, tasks, notes = {}, [], []
            real = z3950.write_add_file

            def spy(targets, ranks):
                path = real(targets, ranks)
                seen["text"] = path.read_text()
                return path
            monkeypatch.setattr(z3950, "write_add_file", spy)
            task = app.bridge.task

            async def spy_task(name, *args, **kw):
                tasks.append(name)
                return await task(name, *args, **kw)
            monkeypatch.setattr(app.bridge, "task", spy_task)
            monkeypatch.setattr(app, "notify", lambda msg, **kw: notes.append(str(msg)))
            button = view.query_one("#z-scan")

            # First press, Show servers: the test only, Koha is not touched.
            assert str(button.label) == "Show servers"
            button.scroll_visible(animate=False)
            await pilot.pause(0.1)
            await pilot.click("#z-scan")
            await _until(pilot, lambda: isinstance(app.screen, LoadingScreen))
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen), wait=30)
            assert "z3950-sync" not in tasks
            assert view.history.tested and str(button.label) == "Update"
            assert any("returned a valid MARC record" in n for n in notes)

            # Second press, Update: no question, Koha's rows first, then the test.
            notes.clear()
            view.selected.clear()      # nothing ticked: the whole list is still sent
            await pilot.click("#z-scan")
            await _until(pilot, lambda: "z3950-sync" in tasks, wait=30)
            assert not isinstance(app.screen, ConfirmScreen)
            lines = seen["text"].splitlines()
            # The direct authority files Koha lacks are left out: only Add puts them in Koha.
            assert len(lines) == len(z3950.sync_targets(z3950.load_curated(), set())) == len(z3950.load_curated()) - 17
            assert any(line.startswith("sru.koha.nexus\t443\tsru/bn-aut\t") and line.endswith("\tauthority")
                       for line in lines)
            # The counts are a notice, not a box to close; then the test starts.
            await _until(pilot, lambda: "Servers added: 3 · updated: 5" in notes, wait=30)
            await _until(pilot, lambda: isinstance(app.screen, LoadingScreen))
            assert not any(isinstance(s, MessageScreen) for s in app.screen_stack)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen), wait=30)
            assert str(button.label) == "Update"
            assert any("returned a valid MARC record" in n for n in notes)

    asyncio.run(main())


def test_ticking_a_server_keeps_the_list_where_it_is(tmp_path, monkeypatch):
    """A tick redraws the list: the list's scroll, the page and the cursor
    stay put (Paulo 2026-10-27: the long list jumped to the top on a tick)."""
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 40)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            table = view.query_one("#z-table", DataTable)
            await _until(pilot, lambda: view.ticks_from_koha)
            view.toggle_hidden()                     # the whole list: far longer than the screen
            await pilot.pause(0.2)
            table.scroll_visible(animate=False)
            await pilot.pause(0.1)
            table.scroll_to(y=60, animate=False)
            await pilot.pause(0.2)
            where = lambda: (view.scroll_y, table.scroll_y)  # noqa: E731
            spot = where()
            assert spot[1] == 60

            # A mouse tick: the first click moves the cursor, the second ticks.
            await pilot.click(table, offset=(5, 10))
            await pilot.pause(0.2)
            key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value
            assert not key.startswith("region:") and key not in view.selected
            await pilot.click(table, offset=(5, 10))
            await pilot.pause(0.2)
            assert key in view.selected and where() == spot
            assert table.cursor_row == table.get_row_index(key)
            # Space and Enter untick and tick again, the list still in place.
            await pilot.press("space")
            await pilot.pause(0.2)
            assert key not in view.selected and where() == spot
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert key in view.selected and where() == spot

            # A whole region from its heading.
            heading = f"region:{view.by_key(key).region}"
            table.move_cursor(row=table.get_row_index(heading), scroll=False)
            await pilot.pause(0.1)
            spot = where()
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert where() == spot and table.cursor_row == table.get_row_index(heading)

            # Back to the tested list: an untick that drops a row refills the
            # table, and its scroll comes back too.
            view.selected = {tg.key for tg in view.targets}  # ticked: listed even untested
            view.toggle_hidden()
            await pilot.pause(0.2)
            assert table.max_scroll_y > 20
            table.scroll_to(y=20, animate=False)
            await pilot.pause(0.2)
            spot = where()
            gone = table.coordinate_to_cell_key((table.row_count - 1, 0)).row_key.value
            view.toggle(gone)
            await pilot.pause(0.2)
            assert gone not in [k.value for k in table.rows]
            assert where() == spot

    asyncio.run(main())
