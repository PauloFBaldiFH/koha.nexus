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
