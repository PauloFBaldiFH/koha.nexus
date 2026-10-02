"""Module 1, the AI setup screen, driven headless in demo mode."""

import asyncio
import stat
import time

import pytest
from conftest import INSTALLER

from kei_panel import aiconf, marcreplace
from kei_panel.bridge import Bridge, installer_actions
from kei_panel.env import PanelEnv
from kei_panel.screens.loading import LoadingScreen
from kei_panel.widgets.cards import StatusCard
from kei_panel.widgets.pacman import PacmanLoader

KEY = "AIzaSyD-test-key-0123456789wxyz"


@pytest.fixture
def demo_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    return tmp_path / "kei-demo-ai"


async def _until(pilot, cond, wait=5.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_gemini_key_test_save_and_marc_hook(demo_dir):
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("a")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-ai")
            q = view.query_one
            assert not q("#ai-ollama").display                      # openai by default
            assert q("#ai-marc").disabled                           # nothing set up yet

            await pilot.click("#ai-p-gemini")
            await pilot.pause(0.1)
            assert q("#ai-url").value == aiconf.DEFAULTS["gemini"][0]
            view.action_save()                                       # no key: refused
            assert not (demo_dir / "vision.conf").exists()

            q("#ai-token").value = KEY
            view.action_test()
            await pilot.pause(0.2)
            assert isinstance(app.screen, LoadingScreen)            # Pac-Man in front
            pac = app.screen.query_one(PacmanLoader)
            frame = pac.frame
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            assert pac.frame > frame                                 # it moved while the test ran
            card = q("#card-ai-connection", StatusCard)
            assert "-ok" in card.classes

            view.action_save()
            await pilot.pause(0.1)
            conf, keys = demo_dir / "vision.conf", demo_dir / "ai-keys.conf"
            assert stat.S_IMODE(conf.stat().st_mode) == 0o600 == stat.S_IMODE(keys.stat().st_mode)
            assert aiconf.load(conf)["token"] == KEY
            assert q("#ai-token").value == ""                       # never put back in a widget
            assert KEY not in q("#ai-token").placeholder and "wxyz" in q("#ai-token").placeholder
            assert not q("#ai-marc").disabled                       # the MARC Replace hook opens

            await pilot.click("#ai-p-ollama")
            await pilot.pause(0.1)
            assert q("#ai-ollama").display and not q("#ai-token").display
            assert q("#ai-url").value == "http://localhost:11434"
            await pilot.click("#ai-p-gemini")                       # back: saved settings return
            await pilot.pause(0.1)
            assert view.values()["token"] == KEY

    asyncio.run(main())


def test_ollama_check_runs_behind_the_loader(demo_dir):
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=True, demo=True))
        async with app.run_test(size=(100, 40)) as pilot:             # 100 cols: narrow layout
            await pilot.pause(0.2)
            await pilot.press("a")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-ai")
            await pilot.click("#ai-p-ollama")
            view.check_ollama()
            await pilot.pause(0.2)
            assert isinstance(app.screen, LoadingScreen)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            state = str(view.query_one("#ai-ollama-state").render())
            assert "Ollama 0.12-demo" in state and "not downloaded yet" in state

    asyncio.run(main())


def test_marc_replace_action_falls_back_on_older_installers(tmp_path):
    assert marcreplace.ACTION in installer_actions(INSTALLER)
    old = tmp_path / "installer"
    old.write_text("panel_action_function() {\n    case \"$1\" in\n"
                   "        library-tools)      echo function_library_tools ;;\n    esac\n}\n")
    bridge = Bridge(PanelEnv(installer=old, lang="en", plain=False))
    assert marcreplace.action(bridge) == marcreplace.FALLBACK_ACTION
    bridge = Bridge(PanelEnv(installer=INSTALLER, lang="en", plain=False))
    assert marcreplace.action(bridge) == marcreplace.ACTION
