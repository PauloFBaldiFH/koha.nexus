import asyncio
import sys
import threading
from pathlib import Path

PANEL = Path(__file__).resolve().parents[1]
REPO = PANEL.parent
sys.path.insert(0, str(PANEL))
INSTALLER = REPO / "installer"

import pytest


@pytest.fixture
def widget_event_loop():
    """Give synchronous widget construction its own loop on Python 3.9.

    asyncio.Lock binds to the current loop at construction on 3.9, unlike
    newer Python versions. A preceding asyncio.run() clears the default loop,
    so screen tests must not depend on whichever test ran before them.
    """
    if sys.version_info >= (3, 10):
        yield
        return
    class WidgetLoopPolicy(asyncio.DefaultEventLoopPolicy):
        def __init__(self):
            super().__init__()
            self.loops = []

        def new_event_loop(self):
            loop = super().new_event_loop()
            self.loops.append(loop)
            return loop

        def get_event_loop(self):
            try:
                return super().get_event_loop()
            except RuntimeError:
                if threading.current_thread() is not threading.main_thread():
                    raise
                # Profile tests can construct another screen after their
                # first asyncio.run() has cleared the current loop too.
                loop = self.new_event_loop()
                self.set_event_loop(loop)
                return loop

    previous = asyncio.get_event_loop_policy()
    policy = WidgetLoopPolicy()
    asyncio.set_event_loop_policy(policy)
    try:
        yield
    finally:
        asyncio.set_event_loop_policy(previous)
        for loop in policy.loops:
            if not loop.is_closed():
                loop.close()


@pytest.fixture(autouse=True)
def _theme_file_of_the_test(tmp_path, monkeypatch):
    # The panel keeps the chosen theme in /etc/koha-easy-install: the tests
    # never touch the one of the machine they run on.
    monkeypatch.setenv("KEI_PANEL_THEME_FILE", str(tmp_path / "panel-theme.conf"))
    # Nor the machine's .env of logins (kei_panel.credentials).
    monkeypatch.setenv("KEI_ENV_FILE", str(tmp_path / "kei.env"))
