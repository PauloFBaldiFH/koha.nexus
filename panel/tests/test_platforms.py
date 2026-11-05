"""Koha is optional: the platform registry and a panel without Koha."""

import asyncio
import re

import pytest
from conftest import INSTALLER

from kei_panel import health, menus, platforms
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv

TEXT = INSTALLER.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# The registry: four facts, never one "operational" flag
# ----------------------------------------------------------------------
def test_catalog_knows_four_platforms_and_supports_only_koha():
    assert [p.id for p in platforms.CATALOG] == ["koha", "tainacan", "atom", "dspace"]
    assert [p.id for p in platforms.CATALOG if p.supported] == ["koha"]


def test_status_json_platforms_are_read():
    status = {"platforms": [
        {"id": "koha", "supported": True, "detected": True, "services": "partial",
         "units": {"apache2": "active", "mariadb": "inactive"}, "health": "unknown"},
        {"id": "tainacan", "supported": False, "detected": None, "services": "none", "health": "unknown"},
        {"id": "something-else", "detected": True},
    ]}
    states = {s.id: s for s in platforms.from_status(status)}
    assert set(states) == {"koha", "tainacan", "atom", "dspace"}
    koha = states["koha"]
    assert koha.detected is True and koha.services == "partial" and koha.health == "unknown"
    assert dict(koha.units) == {"apache2": "active", "mariadb": "inactive"}
    assert states["tainacan"].detected is None and states["atom"].detected is None


def test_an_older_installer_without_platforms_still_says_koha_installed():
    states = {s.id: s for s in platforms.from_status({"koha_installed": False})}
    assert states["koha"].detected is False
    assert {s.id: s.detected for s in platforms.from_status({})}["koha"] is None


def test_unknown_values_are_not_trusted():
    s = platforms.from_status({"platforms": [{"id": "koha", "detected": "yes", "services": "great",
                                              "health": "operational"}]})[0]
    assert s.detected is None and s.health == "unknown"


def test_installed_and_running_is_not_called_healthy():
    state = platforms.from_status({"platforms": [{"id": "koha", "detected": True, "services": "active",
                                                  "health": "unknown"}]})[0]
    value, note, card = platforms.describe(state)
    assert value == "Installed" and "health not verified" in note and card == "ok"
    failing = platforms.from_status({"platforms": [{"id": "koha", "detected": True, "services": "active",
                                                    "health": "failing"}]})[0]
    assert platforms.describe(failing)[2] == "bad"


def test_planned_and_not_installed_cards():
    states = {s.id: s for s in platforms.from_status({"koha_installed": False})}
    assert platforms.describe(states["koha"])[0] == "Not installed"
    assert platforms.describe(states["dspace"])[0] == "Planned"


def test_koha_detection_is_a_file_test(tmp_path, monkeypatch):
    conf = tmp_path / "koha-conf.xml"
    monkeypatch.setenv("KEI_KOHA_CONF", str(conf))
    env = PanelEnv(installer=None, lang="en", plain=False)
    assert not platforms.koha_detected(env)
    conf.write_text("<yazgfs/>")
    assert platforms.koha_detected(env)


def test_default_koha_conf_path_is_the_installers():
    assert 'KOHA_CONF="/etc/koha/sites/${INSTANCE}/koha-conf.xml"' in TEXT
    assert 'is_koha_installed() { [ -f "$KOHA_CONF" ]' in TEXT


# ----------------------------------------------------------------------
# Which actions need Koha: the panel and the installer agree
# ----------------------------------------------------------------------
def installer_koha_actions() -> set[str]:
    m = re.search(r'^KEI_KOHA_ACTIONS="(.*?)"', TEXT, re.S | re.M)
    return set(m.group(1).split())


def test_installer_and_panel_agree_on_koha_actions():
    assert menus.platform_actions("koha") == installer_koha_actions() & menus.all_actions()
    assert "library-tools" in installer_koha_actions()


def test_shared_actions_stay_available_without_koha():
    shared = menus.all_actions() - menus.platform_actions("koha")
    # Install Koha, change the panel's language, update the panel, the
    # server's own tools: none of them needs Koha.
    assert {"install", "languages", "update-panel", "update-system", "about", "reboot", "clock", "ufw",
            "fail2ban", "status", "validation-report", "monitor", "mc"} <= shared


def test_view_entries_and_buttons_carry_their_requirement():
    assert menus.requires_of("database") == "koha"        # a view entry under Diagnostics
    assert menus.requires_of("restart-koha") == "koha"    # the dashboard's button
    assert menus.requires_of("backup-download") == "koha"
    assert menus.requires_of("vpn") == ""
    assert menus.requires_of("terminal") == ""


def test_koha_task_guard_names_real_tasks():
    body = re.search(r"^kei_task_needs_koha\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    names = [n for n in re.findall(r"[a-z][a-z0-9*-]+", body.split("case", 1)[1].split(")", 1)[0])
             if n != "in"]
    from kei_panel.bridge import installer_tasks
    tasks = installer_tasks(INSTALLER)
    for name in names:
        if name.endswith("*"):
            assert any(t.startswith(name[:-1]) for t in tasks), name
        else:
            assert name in tasks, name
    # Tasks a server without Koha still needs are never refused.
    for free in ("info", "install", "install-check", "timezones", "validation-report", "status",
                 "export-diagnostics", "clock", "ufw", "fail2ban", "vpn-status", "run", "tool-install"):
        assert not re.search(rf"(^|[|\s]){re.escape(free)}([|)]|$)", body.split(")", 1)[0]), free


# ----------------------------------------------------------------------
# Health: nothing of Koha is read without it
# ----------------------------------------------------------------------
def test_health_without_koha_never_calls_koha_mysql(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("Koha was read")

    for name in ("read_db_size", "read_z3950", "read_koha_versions"):
        monkeypatch.setattr(health, name, boom)
    monkeypatch.setattr(health, "koha_logs", boom)
    monkeypatch.setattr(health, "latest_panel_version", lambda *_: None)
    monkeypatch.setattr(health, "read_cpu", lambda: None)
    h = asyncio.run(health.collect({}, "library", None, koha=False))
    assert h.db_size is None and h.koha is None and h.z3950 is None


# ----------------------------------------------------------------------
# The panel on a server without Koha (demo mode, KEI_PANEL_DEMO_KOHA=0)
# ----------------------------------------------------------------------
def sidebar_ids(app) -> list[str]:
    from textual.widgets import OptionList
    sidebar = app.screen.query_one("#sidebar", OptionList)
    return [sidebar.get_option_at_index(i).id for i in range(sidebar.option_count)]


@pytest.fixture
def no_koha(monkeypatch):
    monkeypatch.setenv("KEI_PANEL_DEMO_KOHA", "0")


def make_app():
    return KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))


def test_with_koha_the_sidebar_is_the_same_plus_platforms():
    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            return sidebar_ids(app)

    expected = [s.id for s in menus.SECTIONS if s.sidebar]
    assert asyncio.run(main()) == expected
    assert "platforms" in expected and expected.index("platforms") > expected.index("update")


def test_without_koha_the_panel_opens_with_the_shared_sections(no_koha):
    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            return app.koha_installed, sidebar_ids(app)

    installed, ids = asyncio.run(main())
    assert installed is False
    for gone in ("backup", "import", "ai", "z3950", "opac", "hub", "search", "library", "crons", "credentials"):
        assert gone not in ids
    for kept in ("dashboard", "install", "security", "diagnostics", "settings", "tools", "languages",
                 "update", "platforms", "about", "reboot"):
        assert kept in ids


def test_without_koha_a_key_shows_the_reason_and_loads_nothing(no_koha):
    from textual.widgets import ContentSwitcher, Label

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            await pilot.press("b")          # Backup center
            await pilot.pause(0.2)
            switcher = app.screen.query_one("#views", ContentSwitcher)
            current = switcher.current
            reason = str(app.screen.query_one(f"#{current} #unavailable-reason", Label).render())
            await pilot.press("t")          # Database tables (it would read Koha's database)
            await pilot.pause(0.2)
            real_views = [w.id for w in switcher.children if w.id in ("view-backup", "view-database")]
            return current, reason, switcher.current, real_views

    current, reason, after, real_views = asyncio.run(main())
    assert current == "view-backup-off"
    assert "Koha is not installed" in reason
    assert after == "view-database-off" and real_views == []


def test_without_koha_routines_are_refused_with_a_reason(no_koha, tmp_path):
    dropped = tmp_path / "library-backup.sql.gz"
    dropped.write_bytes(b"backup")

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            notes = []
            app.notify = lambda msg, **kw: notes.append(msg)
            backup = next(e for s in menus.SECTIONS for e in s.entries if e.action == "backup-manual")
            app.run_entry(backup)
            app.run_native("restart-koha")
            app.drop_file(str(dropped))
            await pilot.pause(0.1)
            workers = [w for w in app.workers if w.group == "routine"]
            return notes, workers

    notes, workers = asyncio.run(main())
    assert len(notes) == 3 and all("Koha is not installed" in n for n in notes)
    assert workers == []


def test_without_koha_shared_routines_still_run(no_koha):
    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            return [a for a in ("languages", "update-panel", "install", "clock", "terminal")
                    if app.refuse_missing(a)]

    assert asyncio.run(main()) == []


def test_without_koha_the_dashboard_says_so(no_koha):
    from textual.widgets import Button

    from kei_panel.widgets.cards import StatusCard

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(2.5)          # the demo status takes 1.2 s
            dash = app.screen.query_one("#view-dashboard")
            restart = dash.query_one("#restart-koha", Button)
            koha_card = dash.query_one("#dash-platform-koha", StatusCard)
            db_card = dash.query_one("#health-db", StatusCard)
            addresses = dash.query_one("#addresses")
            return (restart.disabled, str(koha_card.query_one(".card-value").render()),
                    str(db_card.query_one(".card-note").render()), addresses.display)

    disabled, koha_value, db_note, addresses_shown = asyncio.run(main())
    assert disabled is True
    assert koha_value == "Not installed"
    assert db_note == "Koha is not installed"
    assert addresses_shown is False


def test_installing_koha_brings_its_sections_back(no_koha, monkeypatch):
    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            await pilot.press("b")
            await pilot.pause(0.2)
            before = sidebar_ids(app)
            monkeypatch.setenv("KEI_PANEL_DEMO_KOHA", "1")   # as if the installation just ended
            app.check_platforms()
            await pilot.pause(0.3)
            return before, sidebar_ids(app), app.screen.query_one("#views").current

    before, after, current = asyncio.run(main())
    assert "backup" not in before and "backup" in after
    assert current == "view-backup"


def test_platforms_screen_shows_a_card_per_platform(no_koha):
    from kei_panel.widgets.cards import StatusCard

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            await pilot.press("p")
            await pilot.pause(2.0)
            view = app.screen.query_one("#view-platforms")
            return {p.id: str(view.query_one(f"#platform-{p.id}", StatusCard).query_one(".card-value").render())
                    for p in platforms.CATALOG}

    assert asyncio.run(main()) == {"koha": "Not installed", "tainacan": "Planned", "atom": "Planned",
                                   "dspace": "Planned"}


# ----------------------------------------------------------------------
# The web proxy (installer: kei_proxy_detect, the "proxy" of --status-json)
# ----------------------------------------------------------------------
def test_proxy_status_is_read_and_unknown_values_are_not_trusted():
    p = platforms.proxy_from_status({"proxy": {"mode": "external", "server": "nginx", "sites": 2}})
    assert (p.mode, p.server, p.sites) == ("external", "nginx", 2)
    assert platforms.proxy_from_status({}).mode is None                       # an older installer
    bad = platforms.proxy_from_status({"proxy": {"mode": "operational", "server": 3, "sites": -1}})
    assert (bad.mode, bad.server, bad.sites) == (None, "", 0)


def test_proxy_card_never_promises_a_change():
    assert platforms.describe_proxy(platforms.ProxyState())[0] == "Unknown"
    assert platforms.describe_proxy(platforms.ProxyState("none"))[0] == "No web server"
    assert platforms.describe_proxy(platforms.ProxyState("apache-nexus", "apache2", 1))[2] == "ok"
    shared = platforms.describe_proxy(platforms.ProxyState("apache-shared", "apache2"))
    assert shared[2] == "warn" and "never changed" in shared[1]
    external = platforms.describe_proxy(platforms.ProxyState("external", "caddy"))
    assert external[0] == "caddy" and external[2] == "warn"


def test_platforms_screen_shows_the_proxy_card(no_koha):
    from kei_panel.widgets.cards import StatusCard

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            await pilot.press("p")
            await pilot.pause(2.0)
            card = app.screen.query_one("#view-platforms #platform-proxy", StatusCard)
            return str(card.query_one(".card-value").render())

    assert asyncio.run(main()) == "No web server"
