"""The restore screen (PathPickerScreen, file mode) takes a dropped file
however the terminal delivers it, and opens the host's file manager
(Paulo, 2026-10-16: drops on the restore screen did nothing)."""

import asyncio
import time
from pathlib import Path

from textual import events
from textual.app import App
from textual.widgets import Button, Input, Label

from kei_panel.screens import files
from kei_panel.screens.files import PathPickerScreen, inserted_text


class PickerApp(App):
    def __init__(self, start, mode="file"):
        super().__init__()
        self.start, self.mode, self.result = start, mode, "open"

    def on_mount(self):
        self.push_screen(PathPickerScreen("Restore", self.start, mode=self.mode),
                         callback=lambda r: setattr(self, "result", r))


def _type(widget, text, gap=0.0):
    """Keys posted as a terminal would type them; gap = seconds between keys."""
    t0 = time.monotonic()
    for i, ch in enumerate(text):
        key = events.Key(ch, ch)
        key.time = t0 + i * gap
        widget.post_message(key)


def _run(start, steps, mode="file"):
    app = PickerApp(start, mode)

    async def main():
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            await steps(app, pilot)
    asyncio.run(main())
    return app


def test_inserted_text():
    assert inserted_text("/root", "/root/mnt/c/b.sql") == "/mnt/c/b.sql"
    assert inserted_text("/root", "'/mnt/c/b.sql'") == "'/mnt/c/b.sql'"
    assert inserted_text("", "abc") == "abc"


def test_the_path_box_has_the_focus_in_file_mode_the_tree_in_folder_mode(tmp_path):
    seen = {}

    async def steps(app, pilot):
        seen["id"] = app.focused.id if app.focused else None
    _run(tmp_path, steps)
    assert seen["id"] == "picker-path"
    _run(tmp_path, steps, mode="dir")
    assert seen["id"] == "picker-tree"


def test_a_drop_typed_as_keys_picks_the_backup_every_codec(tmp_path):
    for name in ("koha.sql", "koha.sql.gz", "koha.sql.xz", "koha.sql.zst", "koha library (2).sql.xz"):
        f = tmp_path / name
        f.write_bytes(b"-- MariaDB dump\n")

        async def steps(app, pilot, f=f):
            _type(app.focused, f'"{f}"')
            await pilot.pause(0.4)
        app = _run(tmp_path, steps)
        assert app.result == f, name


def test_typing_by_hand_is_never_taken_for_a_drop(tmp_path):
    (tmp_path / "koha.sql").write_bytes(b"x")
    seen = {}

    async def steps(app, pilot):
        box = app.screen.query_one("#picker-path", Input)
        box.value = ""
        _type(box, f"{tmp_path}/koha.sql", gap=0.12)
        await pilot.pause(0.5)
        seen["value"], seen["screen"] = box.value, type(app.screen).__name__
    app = _run(tmp_path, steps)
    assert app.result == "open" and seen["screen"] == "PathPickerScreen"
    assert seen["value"] == f"{tmp_path}/koha.sql"


def test_a_held_slash_key_is_not_a_drop(tmp_path):
    seen = {}

    async def steps(app, pilot):
        box = app.screen.query_one("#picker-path", Input)
        box.value = ""
        _type(box, "////////", gap=0.02)
        await pilot.pause(0.4)
        seen["value"] = box.value
    _run(tmp_path, steps)
    assert seen["value"] == "////////"


def test_a_bad_drop_is_said_under_the_box_and_the_screen_stays(tmp_path):
    (tmp_path / "catalog.mrc").write_bytes(b"x")
    seen = {}

    async def steps(app, pilot):
        box = app.screen.query_one("#picker-path", Input)
        _type(box, r"C:\Users\Ana Lima\Downloads\gone.sql.xz")
        await pilot.pause(0.4)
        seen["missing"] = (str(app.screen.query_one("#picker-error", Label).render()), box.value,
                           app.focused is box)
        _type(box, f"'{tmp_path}/catalog.mrc'")
        await pilot.pause(0.4)
        seen["kind"] = str(app.screen.query_one("#picker-error", Label).render())
    app = _run(tmp_path, steps)
    assert app.result == "open"
    error, value, focused = seen["missing"]
    assert "does not exist" in error and value == "/mnt/c/Users/Ana Lima/Downloads/gone.sql.xz" and focused
    assert ".sql.xz" in seen["kind"]


def test_enter_right_after_a_typed_drop_takes_the_drop(tmp_path):
    f = tmp_path / "koha.sql.zst"
    f.write_bytes(b"x")

    async def steps(app, pilot):
        _type(app.focused, f"file://{f}")
        await pilot.pause(0.01)
        await pilot.press("enter")
        await pilot.pause(0.3)
    assert _run(tmp_path, steps).result == f


def test_a_pasted_drop_still_works(tmp_path):
    f = tmp_path / "koha.sql.gz"
    f.write_bytes(b"x")

    async def steps(app, pilot):
        app.focused.post_message(events.Paste(f"'{f}'"))
        await pilot.pause(0.3)
    assert _run(tmp_path, steps).result == f


def test_open_file_manager_runs_off_the_screen_and_once_per_burst_of_clicks(tmp_path, monkeypatch):
    from kei_panel import opener
    monkeypatch.setattr(files, "where", lambda: "wsl")
    calls = []

    def slow_open(path):
        calls.append(path)
        time.sleep(0.3)        # wslpath / interop: must not freeze the screen
        return True
    monkeypatch.setattr(opener, "open_user_folder", slow_open)
    seen = {}

    async def steps(app, pilot):
        button = app.screen.query_one("#open-folder", Button)
        start = time.monotonic()
        for _ in range(3):
            button.press()
            await pilot.pause(0.02)
        seen["responsive"] = time.monotonic() - start < 0.25
        await pilot.pause(0.5)
    _run(tmp_path, steps)
    assert calls == [str(tmp_path)] and seen["responsive"]


def test_no_file_manager_button_over_ssh_or_on_a_server(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "where", lambda: "ssh")
    seen = {}

    async def steps(app, pilot):
        seen["n"] = len(app.screen.query("#open-folder"))
    _run(tmp_path, steps)
    assert seen["n"] == 0


def test_an_elevated_window_says_to_paste_the_path(tmp_path, monkeypatch):
    """Windows refuses drags from Explorer into a window run as administrator
    (the panel the Windows installer opens): the hint says what works."""
    monkeypatch.setattr(files, "drops_blocked", lambda: True)
    seen = {}

    async def steps(app, pilot):
        seen["text"] = str(app.screen.query_one("#picker-drop").render())
    _run(tmp_path, steps)
    assert "administrator" in seen["text"] and "Copy as path" in seen["text"]
