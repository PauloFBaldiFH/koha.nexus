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
def test_catalog_knows_four_platforms_and_supports_koha_and_tainacan():
    assert [p.id for p in platforms.CATALOG] == ["koha", "tainacan", "atom", "dspace"]
    assert [p.id for p in platforms.CATALOG if p.supported] == ["koha", "tainacan"]


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


async def _open(app, pilot, section):
    """Open a screen as its sidebar row does; the cards follow the state read."""
    await pilot.pause(0.3)
    app.screen.query_one("#sidebar").blur()
    app.screen.action_show(section)
    await pilot.pause(2.0)
    from textual.widgets import ContentSwitcher
    switcher = app.screen.query_one("#views", ContentSwitcher)
    return switcher.query_one(f"#{switcher.current}")


def _shown(view) -> list[str]:
    from kei_panel.widgets.cards import ActionCard
    return [c.entry.action for c in view.query(ActionCard) if c.display]


def _choose(view, action) -> None:
    from kei_panel.widgets.cards import ActionCard
    next(c for c in view.query(ActionCard) if c.entry.action == action and c.display).action_choose()


def test_with_koha_the_sidebar_has_its_group_then_the_server():
    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            return sidebar_ids(app)

    # Tainacan's screens only come with Tainacan installed (not in this demo).
    koha = [s.id for s in menus.children("koha")]
    server = [s.id for s in menus.SECTIONS if s.sidebar and not s.group and s.id != "dashboard"]
    assert asyncio.run(main()) == ["dashboard", "koha", *koha, "tainacan", "sidebar-server", *server]
    assert "platforms" not in server and "infra" in server


def test_without_koha_the_panel_opens_with_the_shared_sections(no_koha):
    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            return app.koha_installed, sidebar_ids(app)

    installed, ids = asyncio.run(main())
    assert installed is False
    for gone in ("backup", "import", "ai", "z3950", "opac", "hub", "search", "library", "crons", "credentials",
                 "settings", "diagnostics", "koha-security"):
        assert gone not in ids
    # The group's own row stays: it is where Koha is installed.
    for kept in ("dashboard", "koha", "tainacan", "security", "infra", "server-diagnostics", "tools",
                 "languages", "update", "about", "reboot"):
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


def test_the_dashboard_shows_a_card_per_supported_platform_only(no_koha):
    from kei_panel.widgets.cards import StatusCard

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(2.5)
            view = app.screen.query_one("#view-dashboard")
            return {c.id: str(c.query_one(".card-value").render())
                    for c in view.query_one("#dash-platforms").query(StatusCard) if c.id.startswith("dash-platform-")}

    # AtoM and DSpace are planned: they are said in About, never as a card.
    assert asyncio.run(main()) == {"dash-platform-koha": "Not installed", "dash-platform-tainacan": "Not installed"}


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


def test_shared_infrastructure_shows_the_proxy_card(no_koha):
    from kei_panel.widgets.cards import StatusCard

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "infra")
            return str(view.query_one("#pstatus-proxy", StatusCard).query_one(".card-value").render())

    assert asyncio.run(main()) == "No web server"


# ----------------------------------------------------------------------
# Docker (installer: kei_docker_*, the "docker" of --status-json)
# ----------------------------------------------------------------------
def test_docker_status_is_read_and_unknown_values_are_not_trusted():
    d = platforms.docker_from_status({"docker": {
        "installed": True, "package": "docker-ce", "engine": "29.9.3", "compose": "5.7.0", "running": True,
        "installed_by": "koha-nexus", "others": {"containers": 2}, "platform_networks": 1}})
    assert (d.known, d.installed, d.running, d.installed_by_nexus, d.others, d.networks) == (
        True, True, True, True, 2, 1)
    assert platforms.docker_from_status({}).known is False                    # an older installer
    bad = platforms.docker_from_status({"docker": {"installed": "yes", "running": 1, "engine": 5,
                                                   "others": {"containers": -3}, "platform_networks": True}})
    assert (bad.installed, bad.running, bad.engine, bad.others, bad.networks) == (False, False, "", 0, 0)


def test_docker_card_and_install_button():
    absent = platforms.DockerState(known=True)
    assert platforms.describe_docker(absent)[0] == "Not installed"
    assert platforms.docker_can_install(absent)
    assert not platforms.docker_can_install(platforms.DockerState())          # not reported: no button
    found = platforms.DockerState(True, True, "docker.io", "24.0.7", "2.24.6", True, False, 3)
    value, note, card = platforms.describe_docker(found)
    assert (value, card) == ("Docker 24.0.7", "ok")
    assert "never changed" in note and "3 containers of other programs" in note
    assert not platforms.docker_can_install(found)
    assert not platforms.docker_can_remove(found)                              # found here: never removed
    ours = platforms.DockerState(True, True, "docker-ce", "29.9.3", "5.7.0", True, True)
    assert platforms.docker_can_remove(ours)
    assert not platforms.docker_can_remove(platforms.DockerState(True, True, "docker-ce", "29", "5", True, True, 1))
    assert not platforms.docker_can_remove(platforms.DockerState(True, True, "docker-ce", "29", "5", True, True, 0, 1))
    assert platforms.describe_docker(platforms.DockerState(True, True, "docker-ce", "29.9.3", "", True))[2] == "warn"
    assert platforms.describe_docker(platforms.DockerState(True, True, "docker-ce", "", "", False))[1] == \
        "Installed, but not running"


def test_docker_is_installed_only_after_the_plan_and_a_yes(no_koha):
    from kei_panel.screens.dialogs import ConfirmScreen
    from kei_panel.widgets.cards import StatusCard

    async def main(answer: str):
        app = make_app()
        ran: list[tuple[str, tuple[str, ...]]] = []
        real_task = app.bridge.task

        async def task(name, *args, **kwargs):
            ran.append((name, args))
            return await real_task(name, *args, **kwargs)
        app.bridge.task = task
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "infra")
            value = str(view.query_one("#pstatus-docker", StatusCard).query_one(".card-value").render())
            shown = _shown(view)
            _choose(view, "docker-install")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            dialog = app.screen
            preview = isinstance(dialog, ConfirmScreen) and "download.docker.com" in dialog._preview
            await pilot.click(f"#{answer}")
            await pilot.pause(2.0)
            return value, shown, preview, [name for name, _ in ran if name.startswith("docker-")], ran

    value, shown, preview, names, _ = asyncio.run(main("no"))
    assert (value, preview) == ("Not installed", True)
    # The demo has a backup key: its kit is offered; removing Docker is not (it is not here).
    assert shown == ["docker-install", "pbackup-kit"]
    assert names == ["docker-plan"]                                            # "No": nothing installed
    *_, names, ran = asyncio.run(main("yes"))
    assert names == ["docker-plan", "docker-install"]
    assert ("docker-install", ("confirm",)) in ran


# ----------------------------------------------------------------------
# Tainacan (installer: kei_tainacan_*; its entry of "platforms")
# ----------------------------------------------------------------------
def test_tainacan_status_is_read_and_unknown_values_are_not_trusted():
    st = platforms.tainacan_from_status({"platforms": [
        {"id": "tainacan", "supported": True, "detected": True, "services": "active", "health": "healthy",
         "status": "installed", "url": "http://acervo.example.org"}]})
    assert st == platforms.TainacanState(True, "installed", "http://acervo.example.org", "active", "healthy")
    odd = platforms.tainacan_from_status({"platforms": [
        {"id": "tainacan", "supported": True, "status": "rm -rf", "url": "javascript:x", "health": "great"}]})
    assert (odd.status, odd.url, odd.health) == ("absent", "", "unknown")
    # An installer that does not support it yet: planned.
    assert not platforms.tainacan_from_status({"platforms": [{"id": "tainacan", "supported": False}]}).known
    assert platforms.describe_tainacan(platforms.TainacanState(), platforms.DockerState())[0] == "Planned"


def test_tainacan_card_and_buttons_follow_the_installer():
    docker = platforms.DockerState(True, True, "docker-ce", "29.9.3", "2.40", True)
    absent = platforms.TainacanState(True)
    assert platforms.tainacan_can_install(absent, docker)
    assert not platforms.tainacan_can_install(absent, platforms.DockerState(True))     # no Docker yet
    assert platforms.describe_tainacan(absent, platforms.DockerState(True))[1] == \
        "Needs Docker: its installation prepares it first"
    up = platforms.TainacanState(True, "installed", "http://x.org", "active", "healthy")
    assert platforms.describe_tainacan(up, docker)[2] == "ok"
    assert "http://x.org" in platforms.describe_tainacan(up, docker)[1]
    # Running is not healthy: the API check decides.
    assert platforms.describe_tainacan(platforms.TainacanState(True, "installed", "", "active", "unknown"),
                                       docker)[2] == "warn"
    assert platforms.describe_tainacan(platforms.TainacanState(True, "installed", "", "active", "failing"),
                                       docker)[2] == "bad"
    assert platforms.tainacan_installed(up) and not platforms.tainacan_can_install(up, docker)
    kept = platforms.TainacanState(True, "kept")
    assert platforms.tainacan_can_install(kept, docker)
    assert "kept" in platforms.describe_tainacan(kept, docker)[1]


def _with_docker(status: dict) -> dict:
    status = dict(status)
    status["docker"] = {**status["docker"], "installed": True, "running": True, "engine": "29.9.3",
                        "compose": "2.40", "package": "docker-ce"}
    return status


def test_tainacan_is_installed_only_after_the_plan_and_a_yes(no_koha):
    from kei_panel.screens.dialogs import ConfirmScreen, InputScreen

    async def main(answer: str):
        app = make_app()
        ran: list[tuple[str, tuple[str, ...]]] = []
        real_task, real_status = app.bridge.task, app.bridge.status

        async def task(name, *args, **kwargs):
            ran.append((name, args))
            return await real_task(name, *args, **kwargs)

        async def status(*args, **kwargs):
            return _with_docker(await real_status(*args, **kwargs))
        app.bridge.task, app.bridge.status = task, status
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "tainacan")
            shown = _shown(view)
            _choose(view, "tainacan-install")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            asked = isinstance(app.screen, InputScreen)
            await pilot.click("#ok")              # empty: the server's own address
            await pilot.pause(1.0)
            preview = isinstance(app.screen, ConfirmScreen) and "wordpress.org" in app.screen._preview
            await pilot.click(f"#{answer}")
            await pilot.pause(2.0)
            return shown, asked, preview, [r for r in ran if r[0].startswith("tainacan-")]

    shown, asked, preview, ran = asyncio.run(main("no"))
    # Absent: its home offers the installation and nothing that needs it.
    assert (shown, asked, preview) == (["tainacan-install"], True, True)
    assert ran == [("tainacan-plan", ())]                                   # "No": nothing installed
    *_, ran = asyncio.run(main("yes"))
    assert ran == [("tainacan-plan", ()), ("tainacan-install", ("confirm", "http://192.168.0.10:8090"))]


def test_without_docker_the_tainacan_installation_prepares_it_first_and_goes_on(no_koha):
    from kei_panel.screens.dialogs import ConfirmScreen, InputScreen

    async def main(answers):
        app = make_app()
        ran: list[tuple[str, tuple[str, ...]]] = []
        real_task, real_status = app.bridge.task, app.bridge.status
        docker_in = []

        async def task(name, *args, **kwargs):
            ran.append((name, args))
            if name == "docker-install":
                docker_in.append(True)
            return await real_task(name, *args, **kwargs)

        async def status(*args, **kwargs):
            st = await real_status(*args, **kwargs)
            return _with_docker(st) if docker_in else st
        app.bridge.task, app.bridge.status = task, status
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "tainacan")
            _choose(view, "tainacan-install")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            screens = []
            for answer in answers:
                screen = app.screen
                screens.append(type(screen).__name__ + (":docker" if isinstance(screen, ConfirmScreen) and
                                                        "download.docker.com" in screen._preview else ""))
                await pilot.click(f"#{answer}")
                await pilot.pause(1.5)
            if isinstance(app.screen, InputScreen):
                screens.append("InputScreen")
            return screens, [r[0] for r in ran if r[0].startswith(("docker-", "tainacan-"))]

    # "No" at the explanation: nothing is asked of the installer.
    screens, ran = asyncio.run(main(["no"]))
    assert screens == ["ConfirmScreen"] and ran == []
    # "Yes", then Docker's own plan and "Yes": Docker goes in and Tainacan goes on.
    screens, ran = asyncio.run(main(["yes", "yes"]))
    assert screens == ["ConfirmScreen", "ConfirmScreen:docker", "InputScreen"]
    assert ran == ["docker-plan", "docker-install"]
    # "No" at Docker's plan: neither is installed.
    screens, ran = asyncio.run(main(["yes", "no"]))
    assert ran == ["docker-plan"]


def test_tainacan_uninstall_asks_what_happens_to_the_data(no_koha):
    from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen

    async def main():
        app = make_app()
        ran: list[tuple[str, tuple[str, ...]]] = []
        real_task, real_status = app.bridge.task, app.bridge.status

        async def task(name, *args, **kwargs):
            ran.append((name, args))
            return await real_task(name, *args, **kwargs)

        async def status(*args, **kwargs):
            return _tainacan_installed(await real_status(*args, **kwargs))
        app.bridge.task, app.bridge.status = task, status
        app.tainacan_installed = True
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "tainacan")
            shown = _shown(view)
            _choose(view, "tainacan-uninstall")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            choice = isinstance(app.screen, ChoiceScreen)
            app.screen.dismiss("delete")
            await pilot.pause(1.0)
            danger = isinstance(app.screen, ConfirmScreen) and app.screen._danger and "DELETE" in app.screen._question
            await pilot.click("#yes")
            await pilot.pause(2.0)
            return shown, choice, danger, [r for r in ran if r[0] == "tainacan-uninstall"]

    shown, choice, danger, ran = asyncio.run(main())
    assert "tainacan-install" not in shown and shown[-1] == "tainacan-uninstall"     # removal drawn last
    assert (choice, danger) == (True, True)
    assert ran == [("tainacan-uninstall", ("delete",))]


# ----------------------------------------------------------------------
# The "Platform backups" card (installer: kei_backup_*)
# ----------------------------------------------------------------------
def test_backup_status_is_read_and_unknown_values_are_not_trusted():
    st = platforms.backup_from_results({
        "key": "3F2A9C0E5B7D1A4C8E6F0B2D4A6C8E0F1A3B5C7D", "restic": "0.16.4", "tainacan.repo": "rclone:gd:x",
        "tainacan.copy": "gd:y", "tainacan.schedule": "02:30", "tainacan.count": "4", "tainacan.incomplete": "0",
        "tainacan.verified": "2026-11-01 04:30:12 knx-tainacan-20261002-023000 ok"})
    assert st.known and st.key.startswith("3F2A") and st.schedule == "02:30" and st.count == 4
    value, note, card = platforms.describe_backups(st)
    assert value == "Configuration encrypted" and card == "ok"
    assert "files in an encrypted restic repository" in note and "database not encrypted" in note
    assert "rclone" in note and "gd:y" in note and "02:30" in note and "passed" in note
    odd = platforms.backup_from_results({"key": "not-a-key; rm", "tainacan.schedule": "25:99",
                                         "tainacan.count": "lots", "tainacan.incomplete": "2"})
    assert (odd.key, odd.schedule, odd.count, odd.incomplete) == ("", "", 0, 2)
    value, note, card = platforms.describe_backups(odd)
    assert value == "Configuration not encrypted" and card == "warn" and "incomplete" in note
    assert platforms.describe_backups(platforms.BackupState(True, verified="x y z failed"))[2] == "bad"
    # An installer without the engine: nothing reported, nothing shown.
    assert not platforms.backup_from_results({}).known


def test_the_installer_knows_every_backup_task_the_panel_calls():
    import pathlib
    from kei_panel.bridge import installer_tasks
    view = pathlib.Path(platforms.__file__).with_name("routines").joinpath("platforms.py").read_text(encoding="utf-8")
    called = set(re.findall(r'"(platform-backup-[a-z-]+)"', view)) | {"platform-backup-resume",
                                                                    "platform-backup-discard"}
    assert called and called <= installer_tasks(INSTALLER)


def _tainacan_installed(st: dict) -> dict:
    st = _with_docker(st)
    st["platforms"] = [p if p["id"] != "tainacan" else
                       {**p, "detected": True, "status": "installed", "services": "active",
                        "health": "healthy", "url": "http://192.168.0.10:8090"} for p in st["platforms"]]
    return st


def _platforms_app(ran, results=None):
    app = make_app()
    real_task, real_status = app.bridge.task, app.bridge.status

    async def task(name, *args, **kwargs):
        ran.append((name, args, dict(kwargs.get("env") or {})))
        out = await real_task(name, *args, **kwargs)
        if results and name in results:
            out.results.clear()
            out.results.update(results[name])
        return out

    async def status(*args, **kwargs):
        return _tainacan_installed(await real_status(*args, **kwargs))
    app.bridge.task, app.bridge.status = task, status
    app.tainacan_installed = True        # as its state file would say
    return app


def test_restore_passes_the_recovery_phrase_in_the_environment_only(no_koha):
    from kei_panel.screens.dialogs import InputScreen
    from textual.widgets import Input

    async def main():
        ran: list = []
        app = _platforms_app(ran)
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "tainacan-backups")
            card = view.query_one("#pstatus-backups").display
            shown = _shown(view)
            _choose(view, "tainacan-restore")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            app.screen.dismiss("knx-tainacan-20261105-020000")       # the backup
            await pilot.pause(1.0)
            await pilot.click("#yes")                                 # restore over the one in use
            await pilot.pause(1.0)
            asked = isinstance(app.screen, InputScreen) and app.screen._password
            app.screen.query_one("#value", Input).value = "MY-SECRET-RECOVERY-PHRASE"
            await pilot.click("#ok")
            await pilot.pause(2.0)
            return card, shown, asked, [r for r in ran if r[0] == "tainacan-restore"]

    card, shown, asked, ran = asyncio.run(main())
    assert card and asked
    assert shown == ["tainacan-backup", "tainacan-restore-test", "tainacan-restore", "pbackup-schedule",
                     "pbackup-configure", "pbackup-verify", "pbackup-incomplete"]
    assert ran == [("tainacan-restore", ("knx-tainacan-20261105-020000",),
                    {"KEI_BACKUP_PHRASE": "MY-SECRET-RECOVERY-PHRASE"})]
    assert all("MY-SECRET" not in " ".join(r[1]) for r in ran)


def test_backup_setup_shows_the_plan_and_needs_a_yes(no_koha):
    from kei_panel.screens.dialogs import ConfirmScreen, InputScreen

    no_key = {"platform-backup-status": {"key": "", "restic": "", "tainacan.count": "0",
                                         "tainacan.incomplete": "0"}}

    async def main(answer: str):
        ran: list = []
        app = _platforms_app(ran, no_key)
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "infra")
            shown = _shown(view)
            _choose(view, "pbackup-setup")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            preview = isinstance(app.screen, ConfirmScreen) and "restic" in app.screen._preview
            await pilot.click(f"#{answer}")
            await pilot.pause(1.0)
            asked = isinstance(app.screen, InputScreen)
            if asked:
                await pilot.click("#ok")          # empty: a new phrase, shown once
                await pilot.pause(2.0)
            return shown, preview, [r[:2] for r in ran if r[0].startswith("platform-backup-") and
                                    r[0] != "platform-backup-status"]

    shown, preview, ran = asyncio.run(main("no"))
    assert "pbackup-setup" in shown and "pbackup-kit" not in shown and preview
    assert ran == [("platform-backup-plan", ())]
    *_, ran = asyncio.run(main("yes"))
    assert ran == [("platform-backup-plan", ()), ("platform-backup-setup", ("confirm",))]


def test_an_incomplete_backup_is_resumed_or_discarded(no_koha):
    from kei_panel.screens.dialogs import ChoiceScreen

    async def main():
        ran: list = []
        app = _platforms_app(ran)
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "tainacan-backups")
            _choose(view, "pbackup-incomplete")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            options = [k for k, _v in app.screen._options] if isinstance(app.screen, ChoiceScreen) else []
            app.screen.dismiss("resume")
            await pilot.pause(2.0)
            return options, [r[:2] for r in ran if r[0] in ("platform-backup-resume", "platform-backup-discard")]

    options, ran = asyncio.run(main())
    assert options == ["resume", "discard"]
    assert ran == [("platform-backup-resume", ("knx-tainacan-20261105-143000",))]


# ----------------------------------------------------------------------
# Events in Tainacan (installer: --task tainacan-events): optional, off by
# default, the plan before anything, a dependency that was there before
# kept, data kept when turned off.
# ----------------------------------------------------------------------
def test_events_state_is_read_and_unknown_values_are_not_trusted():
    def state(**kw):
        return platforms.tainacan_from_status({"platforms": [
            {"id": "tainacan", "supported": True, "status": "installed", **kw}]})

    assert (state().events, state().events_dependency) == ("off", "")        # an installer without events
    on = state(events="on", events_dependency="preexisting")
    assert (on.events, on.events_dependency) == ("on", "preexisting")
    odd = state(events="yes; rm -rf /", events_dependency="theirs")
    assert (odd.events, odd.events_dependency) == ("off", "")
    docker = platforms.DockerState(True, True, "29.9.3", "2.40", "docker-ce")
    assert "events on" in platforms.describe_tainacan(on, docker)[1]
    assert "events" not in platforms.describe_tainacan(state(), docker)[1]


def test_events_buttons_only_with_tainacan_installed_and_an_installer_that_has_them():
    installed = platforms.TainacanState(True, "installed")
    none = {"on": False, "off": False, "status": False}
    assert platforms.events_buttons(platforms.TainacanState(True), True) == none          # Tainacan absent
    assert platforms.events_buttons(platforms.TainacanState(True, "failed"), True) == none
    assert platforms.events_buttons(platforms.TainacanState(), True) == none              # older installer
    assert platforms.events_buttons(installed, False) == none                             # no events tasks
    assert platforms.events_buttons(installed, True) == {"on": True, "off": False, "status": True}
    on = platforms.TainacanState(True, "installed", events="on", events_dependency="ours")
    assert platforms.events_buttons(on, True) == {"on": False, "off": True, "status": True}


def test_turning_events_off_keeps_a_preexisting_events_manager_unless_asked():
    pre = platforms.events_off_choices(platforms.TainacanState(True, "installed", events="on",
                                                               events_dependency="preexisting"))
    assert [k for k, _v in pre] == ["default", "dependency"] and "Keep" in pre[0][1]
    # Not recorded (an older state file): treated as someone else's.
    assert [k for k, _v in platforms.events_off_choices(platforms.TainacanState(True, "installed", events="on"))] \
        == ["default", "dependency"]
    ours = platforms.events_off_choices(platforms.TainacanState(True, "installed", events="on",
                                                                events_dependency="ours"))
    assert [k for k, _v in ours] == ["default", "keep-dependency"] and "off too" in ours[0][1]


def test_the_installer_knows_the_events_tasks_and_arguments_the_panel_uses():
    import pathlib
    from kei_panel.bridge import installer_tasks
    tasks = installer_tasks(INSTALLER)
    assert {"tainacan-events", "tainacan-restore-notes"} <= tasks
    body = re.search(r"^        tainacan-events\)(.*?);;\n        tainacan-restore-notes", TEXT, re.S | re.M).group(1)
    for sub in ("plan)", "status)", "enable)", "disable)"):
        assert sub in body, sub
    view = pathlib.Path(platforms.__file__).with_name("routines").joinpath("platforms.py").read_text(encoding="utf-8")
    assert '"tainacan-events", "enable", "confirm"' in view
    # The default disable (no argument) and the two explicit ones are the installer's.
    assert re.search(r'case "\$how" in ""\|keep-dependency\|dependency\)', TEXT)
    # --status-json carries what the buttons follow.
    assert '"events":%s,"events_dependency":%s' in TEXT


def _events_app(ran, events="off", dependency="", tainacan="installed", fail=None, results=None):
    """The demo panel with Tainacan in the given state; fail = {(task,
    first argument): the installer's error}, which then fails as bash does."""
    app = make_app()
    real_task, real_status = app.bridge.task, app.bridge.status

    async def task(name, *args, **kwargs):
        ran.append((name, args, dict(kwargs.get("env") or {})))
        out = await real_task(name, *args, **kwargs)
        key = (name, args[0] if args else "")
        if fail and key in fail:
            out.messages.clear()
            out.results.clear()
            out.feed(f"@@msg error Error\t{fail[key]}")
            out.rc = 1
        if results and key in results:
            out.results.clear()
            out.results.update(results[key])
        return out

    async def status(*args, **kwargs):
        st = _with_docker(await real_status(*args, **kwargs))
        st["platforms"] = [p if p["id"] != "tainacan" else
                           {**p, "detected": tainacan == "installed", "status": tainacan, "services": "active",
                            "health": "healthy", "url": "http://192.168.0.10:8090", "events": events,
                            "events_dependency": dependency} for p in st["platforms"]]
        return st
    app.bridge.task, app.bridge.status = task, status
    app.tainacan_installed = tainacan == "installed"    # as its state file would say
    return app


async def _open_events(app, pilot):
    """Tainacan, Events: where the events cards are."""
    return await _open(app, pilot, "tainacan-events")


def _press(app, action):
    view = app.screen.query_one("#views").query_one(f"#{app.screen.query_one('#views').current}")
    _choose(view, action)


def _events_ran(ran):
    return [r[:2] for r in ran if r[0] == "tainacan-events"]


def test_events_are_off_by_default_and_their_buttons_follow_the_card(no_koha):
    async def main(**kw):
        ran: list = []
        app = _events_app(ran, **kw)
        async with app.run_test() as pilot:
            view = await _open_events(app, pilot)
            shown = _shown(view) if view.id == "view-tainacan-events" else []
            return {k: f"events-{k}" in shown for k in ("on", "off", "status")}, _events_ran(ran)

    # Nothing is asked of the installer while the cards are drawn.
    assert asyncio.run(main()) == ({"on": True, "off": False, "status": True}, [])
    assert asyncio.run(main(events="on", dependency="ours"))[0] == {"on": False, "off": True, "status": True}
    # Tainacan not installed: the screen says why, with no events card at all.
    assert asyncio.run(main(tainacan="absent"))[0] == {"on": False, "off": False, "status": False}


def test_events_are_turned_on_only_after_the_plan_and_a_yes(no_koha):
    from kei_panel.screens.dialogs import ConfirmScreen

    async def main(answer: str):
        ran: list = []
        app = _events_app(ran)
        async with app.run_test() as pilot:
            await _open_events(app, pilot)
            _press(app, "events-on")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            screen = app.screen
            preview = screen._preview if isinstance(screen, ConfirmScreen) else ""
            await pilot.click(f"#{answer}")
            await pilot.pause(2.5)
            return preview, _events_ran(ran)

    preview, ran = asyncio.run(main("no"))
    assert "wordpress.org" in preview and "Nexus Eventos 0.1.1" in preview and "keeps their data" in preview
    assert ran == [("tainacan-events", ("plan",))]                       # "No": nothing changed
    _preview, ran = asyncio.run(main("yes"))
    assert ran == [("tainacan-events", ("plan",)), ("tainacan-events", ("enable", "confirm"))]


def test_a_refused_plan_is_said_and_nothing_is_turned_on(no_koha):
    from kei_panel.screens.dialogs import MessageScreen

    refused = {("tainacan-events", "plan"): {
        "plan": "refuse", "note": "Events Manager 6.4.0 is installed; Nexus Eventos needs 7.4.13 or newer. It was "
                                  "not replaced: update it in WordPress (Plugins) after a backup.", "rc": "3"}}

    async def main():
        ran: list = []
        app = _events_app(ran, results=refused)
        async with app.run_test() as pilot:
            await _open_events(app, pilot)
            _press(app, "events-on")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            screen = app.screen
            said = isinstance(screen, MessageScreen) and screen._kind == "error" and "6.4.0" in screen._body
            return said, _events_ran(ran)

    said, ran = asyncio.run(main())
    assert said and ran == [("tainacan-events", ("plan",))]


def test_a_failed_enable_shows_the_installers_reason(no_koha):
    from kei_panel.screens.dialogs import MessageScreen

    reason = "Events Manager did not match the checksums published by wordpress.org: it was not installed."

    async def main():
        ran: list = []
        app = _events_app(ran, fail={("tainacan-events", "enable"): reason})
        async with app.run_test() as pilot:
            await _open_events(app, pilot)
            _press(app, "events-on")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            await pilot.click("#yes")
            await pilot.pause(2.5)
            screen = app.screen
            return isinstance(screen, MessageScreen) and screen._kind == "error" and screen._body == reason

    assert asyncio.run(main())


def test_cancelling_a_running_enable_says_how_to_finish(no_koha):
    from kei_panel.screens.dialogs import MessageScreen
    from kei_panel.screens.loading import LoadingScreen

    async def main():
        ran: list = []
        app = _events_app(ran)
        async with app.run_test() as pilot:
            await _open_events(app, pilot)
            _press(app, "events-on")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            await pilot.click("#yes")
            await pilot.pause(0.2)
            loading = isinstance(app.screen, LoadingScreen)
            await pilot.click("#cancel")
            await pilot.pause(1.5)
            screen = app.screen
            said = isinstance(screen, MessageScreen) and screen._kind == "info" and "stay off" in screen._body and "turn events on again" in screen._body
            return loading, said, _events_ran(ran)

    loading, said, ran = asyncio.run(main())
    assert loading and said
    assert ran == [("tainacan-events", ("plan",)), ("tainacan-events", ("enable", "confirm"))]


def test_turning_events_off_keeps_the_data_and_a_preexisting_dependency(no_koha):
    from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen

    async def main(dependency, choice, answer="yes"):
        ran: list = []
        app = _events_app(ran, events="on", dependency=dependency)
        async with app.run_test() as pilot:
            await _open_events(app, pilot)
            _press(app, "events-off")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            options = [k for k, _v in app.screen._options] if isinstance(app.screen, ChoiceScreen) else []
            prompt = app.screen._prompt if isinstance(app.screen, ChoiceScreen) else ""
            app.screen.dismiss(choice)
            await pilot.pause(1.0)
            confirm = app.screen if isinstance(app.screen, ConfirmScreen) else None
            danger = bool(confirm and confirm._danger)
            question = confirm._question if confirm else ""
            if confirm:
                await pilot.click(f"#{answer}")
                await pilot.pause(2.0)
            return options, prompt, danger, question, _events_ran(ran)

    options, prompt, danger, question, ran = asyncio.run(main("preexisting", "default"))
    assert options == ["default", "dependency"] and "kept" in prompt
    assert not danger and "No data is deleted" in question
    assert ran == [("tainacan-events", ("disable",))]                    # the installer keeps it on
    *_, danger, question, ran = asyncio.run(main("preexisting", "dependency"))
    assert danger and "was in this WordPress before" in question
    assert ran == [("tainacan-events", ("disable", "dependency"))]       # only with the explicit choice
    *_, ran = asyncio.run(main("preexisting", "dependency", answer="no"))
    assert ran == []                                                     # "No" at the warning
    *_, ran = asyncio.run(main("preexisting", None))
    assert ran == []                                                     # "Back" at the choice
    options, *_, ran = asyncio.run(main("ours", "keep-dependency"))
    assert options == ["default", "keep-dependency"]
    assert ran == [("tainacan-events", ("disable", "keep-dependency"))]


def test_a_failed_disable_shows_the_installers_reason(no_koha):
    from kei_panel.screens.dialogs import MessageScreen

    reason = "Another backup action of this platform is running. Try again when it ends."

    async def main():
        ran: list = []
        app = _events_app(ran, events="on", dependency="ours", fail={("tainacan-events", "disable"): reason})
        async with app.run_test() as pilot:
            await _open_events(app, pilot)
            _press(app, "events-off")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            app.screen.dismiss("default")
            await pilot.pause(1.0)
            await pilot.click("#yes")
            await pilot.pause(2.0)
            screen = app.screen
            return isinstance(screen, MessageScreen) and screen._kind == "error" and screen._body == reason

    assert asyncio.run(main())


def test_the_events_state_screen_lists_both_plugins_and_the_data(no_koha):
    from kei_panel.screens.dialogs import TextScreen

    async def main(fail=None):
        ran: list = []
        app = _events_app(ran, events="on", dependency="ours", fail=fail)
        async with app.run_test() as pilot:
            await _open_events(app, pilot)
            _press(app, "events-status")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            return app.screen._text if isinstance(app.screen, TextScreen) else ""

    text = asyncio.run(main())
    assert "Events are on." in text and "Events Manager: 7.4.13 (active), installed by Koha.Nexus" in text
    assert "Nexus Eventos: 0.1.1 (active)" in text and "Bookings with a pass: 9" in text and "Certificates: 5" in text
    failed = asyncio.run(main({("tainacan-events", "status"): "The Tainacan containers are not running."}))
    assert "The Tainacan containers are not running." in failed


def test_restore_without_the_phrase_warns_about_event_passes_first(no_koha):
    from kei_panel.screens.dialogs import ConfirmScreen

    async def main(backup: str, answer: str, phrase: str = ""):
        from textual.widgets import Input
        ran: list = []
        app = _events_app(ran, events="on")
        async with app.run_test() as pilot:
            view = await _open(app, pilot, "tainacan-backups")
            _choose(view, "tainacan-restore")
            await pilot.pause(2.0)          # the routine reads the state first (1.2 s in the demo)
            app.screen.dismiss(backup)
            await pilot.pause(1.0)
            await pilot.click("#yes")                                  # restore over the one in use
            await pilot.pause(1.0)
            app.screen.query_one("#value", Input).value = phrase
            await pilot.click("#ok")
            await pilot.pause(1.0)
            note = app.screen._question if isinstance(app.screen, ConfirmScreen) else ""
            if note:
                await pilot.click(f"#{answer}")
            await pilot.pause(2.0)
            return note, [r[:2] for r in ran if r[0] in ("tainacan-restore", "tainacan-restore-notes")]

    note, ran = asyncio.run(main("knx-tainacan-20261105-020000", "no"))
    assert "9 event pass links" in note
    assert ran == [("tainacan-restore-notes", ("knx-tainacan-20261105-020000", "nophrase"))]   # not restored
    _note, ran = asyncio.run(main("knx-tainacan-20261105-020000", "yes"))
    assert ran[-1] == ("tainacan-restore", ("knx-tainacan-20261105-020000",))
    # Nothing to lose (no passes, or the same keys): no question.
    note, ran = asyncio.run(main("knx-tainacan-20261104-020000", "yes"))
    assert note == "" and ran[-1] == ("tainacan-restore", ("knx-tainacan-20261104-020000",))
    # With the phrase the links keep working: not even asked.
    note, ran = asyncio.run(main("knx-tainacan-20261105-020000", "yes", phrase="MY-SECRET-RECOVERY-PHRASE"))
    assert note == "" and ran == [("tainacan-restore", ("knx-tainacan-20261105-020000",))]
