import asyncio

from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv, log_error


def test_first_screen_signals_the_watchdog(tmp_path, monkeypatch):
    ready = tmp_path / "panel-started"
    monkeypatch.setenv("KEI_PANEL_READY_FILE", str(ready))

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            return ready.exists()

    assert asyncio.run(main())


def test_errors_go_to_the_error_log(tmp_path, monkeypatch):
    log = tmp_path / "new-panel.log"
    monkeypatch.setenv("KEI_PANEL_ERRLOG", str(log))
    log_error("Traceback: boom\n")
    assert "kei_panel" in log.read_text() and "boom" in log.read_text()


def test_no_error_log_configured_is_fine(monkeypatch):
    monkeypatch.delenv("KEI_PANEL_ERRLOG", raising=False)
    log_error("ignored")


def test_screenshot_and_maximize_are_not_offered():
    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.focus_next()
            return {c.title for c in app.get_system_commands(app.screen)}

    titles = asyncio.run(main())
    assert "Quit" in titles
    assert not titles & {"Screenshot", "Maximize", "Minimize"}


def test_dashboard_title_has_its_icon():
    from textual.widgets import Label

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            return str(app.screen.query_one("#view-dashboard .view-title", Label).render())

    assert asyncio.run(main()) == "📊 Control Dashboard"
