"""Module 1, the AI setup screen, driven headless in demo mode."""

import asyncio
import stat
import time

import pytest
from conftest import INSTALLER
from textual.widgets import Input, ProgressBar, Select

from kei_panel import aiconf, marcreplace
from kei_panel.bridge import Bridge, installer_actions
from kei_panel.env import PanelEnv
from kei_panel.screens.loading import LoadingScreen
from kei_panel.widgets.cards import StatusCard

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
            assert q("#ai-ollama").display                          # always there: needs only Ollama
            assert q("#ai-assistant") and q("#ai-marc")              # both tools on one screen
            assert q("#ai-marc").disabled                           # nothing set up yet

            await pilot.click("#ai-p-gemini")
            await pilot.pause(0.1)
            assert q("#ai-url").value == aiconf.DEFAULTS["gemini"][0]
            view.action_save()                                       # no key: refused
            assert not (demo_dir / "vision.conf").exists()

            q("#ai-token").value = KEY
            view.action_test()
            await pilot.pause(0.2)
            assert isinstance(app.screen, LoadingScreen)            # the loader in front
            bar = app.screen.query_one("#loader-bar", ProgressBar)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            assert bar.percentage == 1.0                             # the demo test reports its steps
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
            assert not q("#ai-token-row").display
            assert q("#ai-url").value == "http://127.0.0.1:11434"
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


def test_models_download_without_the_assistant_and_presets_fill_the_fields(demo_dir, monkeypatch):
    from kei_panel.app import KohaPanelApp

    monkeypatch.setattr(marcreplace, "assistant_installed", lambda demo=False: False)

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("a")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-ai")
            q = view.query_one
            assert view.provider == "openai" and not marcreplace.assistant_installed()
            assert view.ollama_url() == aiconf.OLLAMA_URL           # Ollama's own address, any provider

            options = dict((v, label) for label, v in view.preset_options())
            for model in ("llama3.2:1b", "llama3.2:3b", "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5vl:7b"):
                assert model in options
            assert "[High CPU / Slow on ARM]" in options["qwen2.5vl:7b"]

            # The fields' models need Ollama as the provider; a preset does not.
            assert view.models_to_pull() == []
            q("#ai-ollama-preset", Select).value = "qwen2.5:3b"
            assert view.models_to_pull() == ["qwen2.5:3b"]
            view.pull_model()
            await pilot.pause(0.2)
            assert isinstance(app.screen, LoadingScreen)             # downloading, no assistant needed
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen), 6)   # the check after it

            # A text model is refused for cataloguing, taken for the chat.
            q("#ai-ollama-preset", Select).value = "llama3.2:1b"
            view.use_preset("vision")
            assert q("#ai-model", Input).value != "llama3.2:1b"
            view.use_preset("chat")
            await pilot.pause(0.1)
            assert view.provider == "ollama"
            assert q("#ai-model", Input).value == "qwen2.5vl:7b"
            assert q("#ai-chat-model", Input).value == "llama3.2:1b"
            assert view.models_to_pull() == ["llama3.2:1b"]
            q("#ai-ollama-preset", Select).value = "@fields"
            assert view.models_to_pull() == ["qwen2.5vl:7b", "llama3.2:1b"]

            view.action_save()
            await pilot.pause(0.1)
            saved = aiconf.load(demo_dir / "vision.conf")
            assert saved["model"] == "qwen2.5vl:7b" and saved["chat_model"] == "llama3.2:1b"
            assert aiconf.chat_model(saved) == "llama3.2:1b"
            assert "llama3.2:1b" in str(q("#ai-aia-text").render())

    asyncio.run(main())


def test_model_list_free_and_paid_groups(demo_dir):
    from kei_panel.app import KohaPanelApp
    from kei_panel import aimodels

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("a")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-ai")
            q = view.query_one
            await pilot.click("#ai-p-gemini")
            await pilot.pause(0.1)
            options = [o[1] for o in view.model_options(view.discovery)]
            assert options[0] == "@free" and "@paid" in options
            assert options.index("gemini-pro-latest") > options.index("@paid") > options.index("gemini-flash-latest")
            note = str(q("#ai-models-note").render())
            assert "Built-in list" in note and "Load models" in note        # says it is not the live list

            q("#ai-model-list", Select).value = "@paid"                    # a header picks nothing
            view.use_listed("vision")
            assert q("#ai-model").value == aiconf.DEFAULTS["gemini"][1]

            q("#ai-model-list", Select).value = "gemini-pro-latest"
            await pilot.pause(0.1)
            assert aimodels.PAID_BADGE in str(q("#ai-models-note").render())  # the billing warning
            view.use_listed("chat")
            assert q("#ai-chat-model").value == "gemini-pro-latest"

            view.load_models()
            await pilot.pause(0.2)
            assert isinstance(app.screen, LoadingScreen)
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            assert "demo mode" in str(q("#ai-models-note").render())

    asyncio.run(main())
