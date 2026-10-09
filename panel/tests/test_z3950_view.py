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


def test_scan_rank_hide_login_and_add(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("z")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-z3950")
            table = view.query_one("#z-table", DataTable)
            curated = z3950.load_curated()
            assert table.row_count == len(curated) + len(z3950.REGIONS)
            assert table.get_row("region:latam")[1] == "[b]Brazil / Latin America[/b]"
            # Koha's own list was read: the LoC target is marked.
            loc = next(t for t in curated if t.host == "lx2.loc.gov")
            await _until(pilot, lambda: "In Koha" in table.get_row(loc.key)[2])

            # The Zeus bridge comes ticked; untick it before the regions.
            zeus = next(t for t in curated if t.preselect)
            assert view.selected == {zeus.key}
            view.toggle(zeus.key)
            assert view.selected == set()

            # A region ticks all of it; space on a server unticks one.
            view.toggle("region:europe")
            europe = [t for t in curated if t.region == "europe"]
            assert view.selected == {t.key for t in europe}
            view.toggle(europe[0].key)
            assert len(view.selected) == len(europe) - 1
            view.toggle("region:europe")
            assert len(view.selected) == len(europe)

            view.scan()
            await pilot.pause(0.1)
            assert isinstance(app.screen, LoadingScreen)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            history = json.loads((tmp_path / z3950.HISTORY_FILE).read_text())
            assert set(history) - {z3950.RULES_KEY} == {t.key for t in europe}
            bnp = next(t for t in europe if t.host == "z3950.libris.kb.se")
            assert history[bnp.key]["status"] == "ok"
            assert "Working" in table.get_row(bnp.key)[2] and table.get_row(bnp.key)[3]

            # Hide one by hand: gone from the list, back with "Show hidden".
            table.move_cursor(row=table.get_row_index(bnp.key))
            view.hide()
            assert bnp.key not in [k.value for k in table.rows]
            assert bnp.key not in view.selected
            view.toggle_hidden()
            assert "Hidden" in table.get_row(bnp.key)[2]
            view.toggle_hidden()

            # A login: typed in the panel, kept privately, never shown.
            bl = next(t for t in europe if t.host == "z3950cat.bl.uk")
            table.move_cursor(row=table.get_row_index(bl.key))
            view.login()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen))
            app.screen.query_one("#value").value = "librarian"
            await pilot.click("#ok")
            await _until(pilot, lambda: isinstance(app.screen, InputScreen) and app.screen._password)
            app.screen.query_one("#value").value = "s3cret-pw"
            await pilot.click("#ok")
            await _until(pilot, lambda: (tmp_path / z3950.LOCAL_FILE).exists())
            saved = (tmp_path / z3950.LOCAL_FILE)
            assert saved.stat().st_mode & 0o777 == 0o600 and "s3cret-pw" in saved.read_text()
            assert all("s3cret-pw" not in str(c) for k in table.rows for c in table.get_row(k))

            # Into Koha: the confirmation lists the servers by rank.
            seen = {}
            real = z3950.write_add_file

            def spy(targets, ranks):
                path = real(targets, ranks)
                seen["path"], seen["text"] = path, path.read_text()
                return path
            monkeypatch.setattr(z3950, "write_add_file", spy)
            view.add()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            preview = app.screen._preview
            assert preview.splitlines()[0].startswith(" 1. ") and "s3cret-pw" not in preview
            await pilot.click("#yes")
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert "added to Koha: 2" in app.screen._body
            assert not seen["path"].exists()                     # the list with the login is gone
            assert "librarian\ts3cret-pw" in seen["text"]

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
            await pilot.click("#ok")
            key = "z.consortium.example.br:2100/acervo"
            await _until(pilot, lambda: key in [k.value for k in table.rows])
            assert table.get_row(key)[1] == "My consortium *"
            assert "z.consortium.example.br" in (tmp_path / z3950.LOCAL_FILE).read_text()

            view.toggle(key)
            view.export()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen))
            out = tmp_path / "out.sql"
            app.screen.query_one("#value").value = str(out)
            await pilot.click("#ok")
            await _until(pilot, out.exists)
            assert "z.consortium.example.br" in out.read_text() and "lx2.loc.gov" not in out.read_text()

            view.sync()
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            assert key in [k.value for k in table.rows]           # the community list keeps mine

    asyncio.run(main())


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
