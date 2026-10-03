from conftest import INSTALLER

from kei_panel.bridge import Bridge
from kei_panel.env import PanelEnv
from kei_panel.menus import section


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
    rebuild = section("search").entries[1]
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
