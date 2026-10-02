import re

from conftest import INSTALLER

from kei_panel.menus import SECTIONS, all_actions

TEXT = INSTALLER.read_text(encoding="utf-8")


def installer_actions():
    body = re.search(r"^panel_action_function\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    return set(re.findall(r"^\s+([a-z][a-z0-9-]*)\)\s+echo", body, re.M))


def test_every_action_exists_in_the_installer():
    missing = all_actions() - installer_actions()
    assert not missing, f"not in panel_action_function: {missing}"


def test_every_bash_action_has_a_menu_entry():
    assert installer_actions() - all_actions() == set()


def test_existing_labels_are_installer_texts():
    # New screens (database, ai) bring new texts; everything else must be
    # the installer's own English key, or its translations are lost.
    new = {"database", "ai", "dashboard"}
    for s in SECTIONS:
        if s.id in new:
            continue
        for text in [s.label, s.title, s.prompt] + [e.label for e in s.entries]:
            if text:
                assert text in TEXT, f"{s.id}: {text!r} is not an installer text"


def test_unique_ids_and_keys():
    ids = [s.id for s in SECTIONS]
    keys = [s.key for s in SECTIONS if s.key]
    assert len(ids) == len(set(ids)) and len(keys) == len(set(keys))
