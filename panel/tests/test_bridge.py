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
