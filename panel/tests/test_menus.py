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
    # The Library tools menu of bash is the panel's section of its tools.
    assert installer_actions() - all_actions() == {"library-tools"}


def test_every_entry_is_native():
    # The full port: no entry opens a whiptail routine any more.
    from kei_panel import routines
    left = [e.action for s in SECTIONS for e in s.entries
            if e.kind != "view" and (e.kind != "native" or not routines.has(e.action))]
    assert not left, f"not ported: {left}"


def test_existing_labels_are_installer_texts():
    # New screens (database, ai) bring new texts; everything else must be
    # the installer's own English key, or its translations are lost.
    new = {"database", "ai", "dashboard", "z3950", "opac", "hub", "vpn"}
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


def test_magic_import_is_on_the_main_menu():
    # Right under the backups (Paulo, 2026-10-09), and only there.
    ids = [s.id for s in SECTIONS]
    assert ids.index("import") == ids.index("backup") + 1
    places = [s.id for s in SECTIONS for e in s.entries if e.action == "magic-import"]
    assert places == ["import"]


def test_security_and_access_hub():
    # VPN, Cloudflare Tunnel, firewall, HTTPS and Fail2ban in one place.
    from kei_panel.menus import section
    hub = section("security")
    actions = [e.action for e in hub.entries]
    for a in ("vpn", "cloudflare", "ufw", "staff-firewall", "ssl", "fail2ban"):
        assert a in actions
    assert [e.kind for e in hub.entries if e.action == "vpn"] == ["view"]
    ids = [s.id for s in SECTIONS]
    assert "publish" not in ids
    vpn = section("vpn")
    assert not vpn.sidebar and vpn.parent == "security" and vpn.key == "v"
    # Every view entry opens a section that exists.
    for s in SECTIONS:
        for e in s.entries:
            if e.kind == "view":
                assert section(e.action)


def test_the_bash_main_menu_matches():
    # The classic menu has the same order: Magic Import under the backups,
    # one Security & access hub.
    body = TEXT[TEXT.index("# MAIN MENU (17 OPTIONS)"):]
    assert body.index("m4=$(t '💾  Backup center')") < body.index("m5=$(t '🪄  Magic Import Tool')")
    assert "m7=$(t '🔒  Security & access hub')" in body
    assert "🌐  Publish system to internet')" not in body


def test_the_terminal_web_browser_is_gone():
    from kei_panel import routines
    assert "links" not in all_actions() and "links" not in routines.ROUTINES


def test_the_vpn_card_opens_the_vpn_screen():
    import asyncio

    from textual.widgets import ContentSwitcher, OptionList

    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.widgets.cards import ActionCard

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.3)
            sidebar = app.screen.query_one("#sidebar", OptionList)
            in_sidebar = [sidebar.get_option_at_index(i).id for i in range(sidebar.option_count)]
            app.screen.action_show("security")
            await pilot.pause(0.3)
            card = next(c for c in app.screen.query(ActionCard) if c.entry.action == "vpn")
            card.action_choose()
            await pilot.pause(0.5)
            shown = app.screen.query_one("#views", ContentSwitcher).current
            return in_sidebar, shown, sidebar.get_option_at_index(sidebar.highlighted).id

    in_sidebar, shown, highlighted = asyncio.run(main())
    assert "vpn" not in in_sidebar and "security" in in_sidebar and "publish" not in in_sidebar
    assert shown == "view-vpn" and highlighted == "security"
