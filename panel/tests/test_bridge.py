from conftest import INSTALLER

from kei_panel.bridge import Bridge
from kei_panel.env import PanelEnv
from kei_panel.menus import Entry, section


def bridge():
    return Bridge(PanelEnv(installer=INSTALLER, lang="en", plain=False))


def test_verbs_are_read_from_the_installer():
    b = bridge()
    assert b.supports("--status-json")
    assert b.supports("--rebuild-search-index")
    assert not b.supports("--backup-now")      # not in the installer yet


def test_unsupported_verb_falls_back_to_the_routine():
    from kei_panel.app import KohaPanelApp
    app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False))
    backup = section("backup").entries[0]
    # No menu entry uses a verb now (search repair is a native routine).
    rebuild = Entry("🔨  Repair / rebuild indexing", "search-repair", verb=("--rebuild-search-index",))
    assert not app.runs_in_background(backup)
    assert app.runs_in_background(rebuild)


def test_lock_descriptor_is_handed_to_routines(monkeypatch, tmp_path):
    import os

    from kei_panel.env import inherited_lock_fd

    fd = os.open(tmp_path / "lock", os.O_WRONLY | os.O_CREAT)
    try:
        monkeypatch.setenv("KEI_PANEL_LOCK_FD", str(fd))
        assert inherited_lock_fd() == fd
        env = PanelEnv(installer=INSTALLER, lang="en", plain=False)
        assert env.child_env()["KEI_PANEL_LOCK_FD"] == str(fd)
    finally:
        os.close(fd)
    # Closed (or never given): not passed on.
    assert inherited_lock_fd() is None
    assert "KEI_PANEL_LOCK_FD" not in PanelEnv(installer=INSTALLER, lang="en", plain=False).child_env()


def test_long_output_without_newline_does_not_break_the_stream():
    """A routine that prints MARC21 records (0x1D separated, no newline) used
    to raise "Separator is not found, and chunk exceed the limit"."""
    import asyncio
    import sys

    code = ("import sys; w = sys.stdout.buffer.write; w(b'start\\n'); "
            "w((b'x' * 1500 + b'\\x1d') * 2000); w(b'z' * 1500000); "
            "w(b'\\n@@result file /tmp/marc.tar.gz\\n'); sys.stdout.flush()")
    lines: list[str] = []
    rc = asyncio.run(bridge().stream([sys.executable, "-c", code], None, on_line=lines.append))
    assert rc == 0
    assert lines[0] == "start"
    assert lines[-1] == "@@result file /tmp/marc.tar.gz"
    assert all(len(line) <= 2002 for line in lines)


def test_split_line_falls_back_to_record_separators():
    from kei_panel.bridge import _split_line

    buf = bytearray(b"aaa\x1dbbb\x1dcc")
    assert _split_line(buf, limit=8) == b"aaa\x1dbbb\x1d"
    assert buf == bytearray(b"cc")
    assert _split_line(buf, limit=8) is None
    buf = bytearray(b"0123456789")
    assert _split_line(buf, limit=4) == b"0123"
    buf = bytearray(b"one\ntwo")
    assert _split_line(buf) == b"one"
