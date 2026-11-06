"""The panel organized by platform, on four servers (demo mode, simulated
installer answers): no platform, Koha only, Tainacan only, both.

The sidebar: the dashboard, the groups Koha (library) and Tainacan
(collections and museums), then the Server area; the dashboard's tabs are
the only summary. A platform's home follows its state (absent: install;
installed: its tools; failing or incomplete: the problem and the
diagnosis first, never a restore). Opening a screen reads, never changes,
the server; the full diagnosis only runs when asked, and a failed one
keeps the one before with its time.
"""

import asyncio
import re

import pytest
from conftest import INSTALLER

from kei_panel import platforms
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv

TEXT = INSTALLER.read_text(encoding="utf-8")
SERVERS = {"none": ("0", "0"), "koha": ("1", "0"), "tainacan": ("0", "1"), "both": ("1", "1")}
# The tasks the section and the tab may call while they are drawn: reads
# (setup-status: whether the "Continue the setup" card is drawn).
READS = {"platform-backup-status", "setup-status"}


@pytest.fixture
def server(monkeypatch, request):
    koha, tainacan = SERVERS[request.param]
    monkeypatch.setenv("KEI_PANEL_DEMO_KOHA", koha)
    monkeypatch.setenv("KEI_PANEL_DEMO_TAINACAN", tainacan)
    return request.param


def make_app(ran=None, fail=None, status_patch=None):
    """The demo panel; ran collects (task, args); fail = {task: installer
    error}; status_patch changes the Tainacan entry of --status-json."""
    app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
    real_task, real_status = app.bridge.task, app.bridge.status

    async def task(name, *args, **kwargs):
        if ran is not None:
            ran.append((name, args))
        out = await real_task(name, *args, **kwargs)
        if fail and name in fail:
            out.messages.clear()
            out.results.clear()
            out.feed(f"@@msg error Error\t{fail[name]}")
            out.rc = 1
        return out

    async def status(*args, **kwargs):
        st = await real_status(*args, **kwargs)
        if status_patch:
            st = dict(st)
            st["platforms"] = [{**p, **status_patch} if p["id"] == "tainacan" else p for p in st["platforms"]]
        return st
    app.bridge.task, app.bridge.status = task, status
    return app


def sidebar_ids(app):
    from textual.widgets import OptionList
    sidebar = app.screen.query_one("#sidebar", OptionList)
    return [sidebar.get_option_at_index(i).id for i in range(sidebar.option_count)]


def card(widget, cid):
    from kei_panel.widgets.cards import StatusCard
    c = widget.query_one(f"#{cid}", StatusCard)
    return str(c.query_one(".card-value").render()), str(c.query_one(".card-note").render())


async def open_section(app, pilot, key):
    await pilot.pause(0.3)
    app.screen.query_one("#sidebar").blur()
    await pilot.press(key)
    await pilot.pause(2.0)


def current_view(app):
    from textual.widgets import ContentSwitcher
    switcher = app.screen.query_one("#views", ContentSwitcher)
    return switcher.query_one(f"#{switcher.current}")


def shown_cards(view) -> list[str]:
    from kei_panel.widgets.cards import ActionCard
    return [c.entry.action for c in view.query(ActionCard) if c.display]


def choose(view, action) -> None:
    from kei_panel.widgets.cards import ActionCard
    next(c for c in view.query(ActionCard) if c.entry.action == action).action_choose()


# ----------------------------------------------------------------------
# Four servers: the sidebar, the dashboard's tabs, the platform homes
# ----------------------------------------------------------------------
KOHA_SCREENS = ["import", "library", "z3950", "ai", "opac", "hub", "search", "settings",
                "diagnostics", "koha-security"]
TAINACAN_SCREENS = ["tainacan-maintenance", "tainacan-events"]
# The Backup center and the Schedules center are shared (main menu, Paulo
# 2026-11-06): a platform home has a card that opens them already filtered.
SERVER_SCREENS = ["backups", "schedules", "security", "infra", "server-diagnostics", "languages", "update", "tools", "about",
                  "reboot"]


@pytest.mark.parametrize("server", list(SERVERS), indirect=True)
def test_the_sidebar_and_the_tabs_follow_what_is_installed(server):
    from textual.widgets import TabbedContent

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test() as pilot:
            await pilot.pause(2.5)          # the demo status takes 1.2 s
            tabs = app.screen.query_one("#dash-tabs", TabbedContent)
            shown = {pane: tabs.get_tab(pane).display for pane in
                     ("dash-tab-general", "dash-tab-koha", "dash-tab-tainacan")}
            dash = app.screen.query_one("#view-dashboard")
            planned = [c for c in ("atom", "dspace") if dash.query(f"#dash-platform-{c}")]
            return sidebar_ids(app), shown, tabs.active, ran, planned

    ids, shown, active, ran, planned = asyncio.run(main())
    koha, tainacan = server in ("koha", "both"), server in ("tainacan", "both")
    expected = ["dashboard", "koha"] + (KOHA_SCREENS if koha else []) + ["tainacan"] + \
        (TAINACAN_SCREENS if tainacan else []) + ["sidebar-server"] + SERVER_SCREENS
    assert ids == expected
    assert "platforms" not in ids and "install" not in ids
    assert shown == {"dash-tab-general": True, "dash-tab-koha": koha, "dash-tab-tainacan": tainacan}
    assert active == "dash-tab-general"
    assert planned == []                        # AtoM and DSpace are not in the operational summary
    # The dashboard only reads: --status-json, and the backup engine's state with Tainacan.
    assert {name for name, _a in ran} <= READS
    assert bool(ran) is tainacan


@pytest.mark.parametrize("server", list(SERVERS), indirect=True)
def test_each_platform_home_follows_its_state(server):
    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            homes = {}
            for key in ("k", "g"):
                await open_section(app, pilot, key)
                view = current_view(app)
                problem = str(view.query_one("#platform-problem").render())
                homes[key] = (view.id, shown_cards(view), problem,
                              view.query_one("#home-dashboard").display)
            return homes, ran

    homes, ran = asyncio.run(main())
    koha, tainacan = server in ("koha", "both"), server in ("tainacan", "both")
    kid, kcards, kproblem, kdash = homes["k"]
    assert kid == "view-koha"
    if koha:
        # The Schedules center's card sits where the editor was, after indexing.
        cards = KOHA_SCREENS[:KOHA_SCREENS.index("search") + 1] + ["schedules"] + \
            KOHA_SCREENS[KOHA_SCREENS.index("search") + 1:]
        assert kcards == ["credentials", "admin-koha", "backups"] + cards and kproblem == "" and kdash
    else:
        assert kcards == ["install"] and "not installed" in kproblem and not kdash
    tid, tcards, tproblem, tdash = homes["g"]
    assert tid == "view-tainacan"
    if tainacan:
        assert tcards == ["admin-tainacan", "tainacan-address"] + TAINACAN_SCREENS + ["backups", "tainacan-uninstall"] \
            and tproblem == "" and tdash
    else:
        assert tcards == ["tainacan-install"] and "not installed" in tproblem and not tdash
    # Opening the homes only reads.
    assert {name for name, _a in ran} <= READS


@pytest.mark.parametrize("server", ["tainacan"], indirect=True)
@pytest.mark.parametrize("patch,docker,why", [
    ({"services": "inactive"}, None, "containers are not all running"),
    ({}, {"running": False}, "Docker is stopped"),
    ({"status": "failed"}, None, "stopped before the end"),
])
def test_a_stopped_or_incomplete_tainacan_shows_the_problem_and_the_diagnosis_never_a_restore(
        server, patch, docker, why):
    async def main():
        app = make_app(status_patch=patch)
        if docker:
            real = app.bridge.status

            async def status(*a, **k):
                st = dict(await real(*a, **k))
                st["docker"] = {**st["docker"], "installed": True, "running": False, "compose": "2.29"}
                return st
            app.bridge.status = status
        async with app.run_test(size=(160, 48)) as pilot:
            await open_section(app, pilot, "g")
            view = current_view(app)
            titles = [w.id for w in view.query(".zone-title") if w.display]
            return shown_cards(view), str(view.query_one("#platform-problem").render()), titles

    cards, problem, titles = asyncio.run(main())
    assert why in problem
    # Stopped: start it again (plan and Yes) first; incomplete: install again.
    assert cards[:3] in (["tainacan-start", "tainacan-status", "tainacan-logs"],
                         ["tainacan-install", "tainacan-status", "tainacan-logs"])
    assert ("tainacan-start" in cards) is ("stopped before the end" not in why)
    assert not {"tainacan-restore", "tainacan-restore-test", "tainacan-backup"} & set(cards)
    assert "zone-recovery-title" in titles and "zone-removal-title" in titles
    assert ("infra" in cards) is bool(docker)


@pytest.mark.parametrize("server", ["koha"], indirect=True)
def test_a_stopped_koha_puts_the_diagnosis_first(server):
    async def main():
        app = make_app()
        real = app.bridge.status

        async def status(*a, **k):
            st = dict(await real(*a, **k))
            st["state"] = "stopped"
            st["services"] = {**st.get("services", {}), "mariadb": "inactive", "apache2": "failed"}
            return st
        app.bridge.status = status
        async with app.run_test(size=(160, 48)) as pilot:
            await open_section(app, pilot, "k")
            view = current_view(app)
            return shown_cards(view), str(view.query_one("#platform-problem").render())

    cards, problem = asyncio.run(main())
    assert "MariaDB, Apache" in problem
    assert cards[:4] == ["status", "health", "repair-services", "apache-log"]
    assert "backups" in cards and "install" not in cards and "restore" not in cards


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_groups_expand_and_collapse_with_the_arrows_and_keys_keep_their_screens(server):
    from textual.widgets import ContentSwitcher, OptionList

    keys = {"d": "dashboard", "k": "koha", "b": "backups", "i": "import", "l": "library", "h": "enrich-auth",
            "n": "ondemand", "z": "z3950", "a": "ai", "o": "opac", "m": "hub", "s": "schedules", "t": "database",
            "g": "tainacan", "x": "security", "v": "vpn", "p": "infra"}

    async def main():
        app = make_app()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.5)
            sidebar = app.screen.query_one("#sidebar", OptionList)
            sidebar.focus()
            sidebar.highlighted = sidebar.get_option_index("tainacan")
            await pilot.press("left")
            collapsed = sidebar_ids(app)
            highlighted = sidebar.get_option_at_index(sidebar.highlighted).id
            await pilot.press("right")
            expanded = sidebar_ids(app)
            current = app.screen.query_one("#views", ContentSwitcher).current
            opened = {}
            sidebar.blur()
            for key, sec in keys.items():
                await pilot.press(key)
                await pilot.pause(0.3)
                for _ in range(50):          # the tables screen reads them behind its loader
                    if app.screen.query("#views"):
                        break
                    await pilot.pause(0.1)
                opened[key] = app.screen.query_one("#views", ContentSwitcher).current
                await pilot.press("escape")
            # A key of a screen of a collapsed group opens it and expands the group.
            app.screen.set_group("koha", False)
            await pilot.pause(0.1)
            await pilot.press("i")
            await pilot.pause(0.3)
            return collapsed, highlighted, expanded, current, opened, sidebar_ids(app), \
                sidebar.get_option_at_index(sidebar.highlighted).id

    collapsed, highlighted, expanded, current, opened, after_b, hl_b = asyncio.run(main())
    assert not set(TAINACAN_SCREENS) & set(collapsed) and highlighted == "tainacan"
    assert set(TAINACAN_SCREENS) <= set(expanded)
    assert current == "view-dashboard"                   # the arrows never change the screen
    assert opened == {k: f"view-{v}" for k, v in keys.items()}
    assert "import" in after_b and hl_b == "import"


@pytest.mark.parametrize("server", ["none", "koha"], indirect=True)
def test_without_tainacan_its_screens_show_the_reason_and_load_nothing(server):
    from textual.widgets import Label

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.action_show("tainacan-events")
            await pilot.pause(0.5)
            view = current_view(app)
            return view.id, str(view.query_one("#unavailable-reason", Label).render()), ran

    vid, reason, ran = asyncio.run(main())
    assert vid == "view-tainacan-events-off"
    assert "Tainacan is not installed" in reason and "Tainacan (collections and museums)" in reason
    assert ran == []


@pytest.mark.parametrize("server", ["tainacan", "both"], indirect=True)
def test_the_tainacan_screens_have_their_tools_and_no_second_summary(server):
    from kei_panel.widgets.cards import LinkCard

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            out = {}
            for sec in TAINACAN_SCREENS + ["tainacan"]:
                app.screen.action_show(sec)
                await pilot.pause(2.0)
                view = current_view(app)
                out[sec] = (shown_cards(view), len(view.query(LinkCard)))
            return out, ran

    out, ran = asyncio.run(main())
    # The demo home page is prepared, so maintenance offers to undo it.
    assert out["tainacan-maintenance"][0] == ["tainacan-status", "tainacan-logs", "tainacan-credentials",
                                              "tainacan-site-undo"]
    assert out["tainacan-events"][0] == ["events-on", "events-status"]         # off: no "turn off"
    assert all(links == 0 for _c, links in out.values())         # addresses: the dashboard only
    assert {name for name, _a in ran} <= READS


@pytest.mark.parametrize("server", ["tainacan"], indirect=True)
def test_the_diagnosis_runs_only_when_asked_and_says_when_it_was_read(server):
    from kei_panel.screens.dialogs import TextScreen

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.action_show("tainacan-maintenance")
            await pilot.pause(2.0)
            before = [name for name, _a in ran]
            choose(current_view(app), "tainacan-status")
            await pilot.pause(1.5)
            text = app.screen._text if isinstance(app.screen, TextScreen) else ""
            return before, text, [name for name, _a in ran]

    before, text, after = asyncio.run(main())
    assert "tainacan-status" not in before
    assert after.count("tainacan-status") == 1
    assert "Collections: 3" in text and f"Read at {platforms.when(1793872800)}." in text


@pytest.mark.parametrize("server", ["tainacan"], indirect=True)
def test_a_failed_diagnosis_keeps_the_one_before_marked_as_old(server):
    from textual.widgets import TabbedContent

    from kei_panel.screens.dialogs import MessageScreen

    reason = "The diagnosis could not read Tainacan. Docker is not running."
    old = {"checked": {"checked_at": "1793872800", "collections": "4", "items": "1250", "attachments": "3110",
                       "attachments_missing": "0", "failed_at": "1793880000"}}

    async def main():
        app = make_app(fail={"tainacan-status": reason}, status_patch=old)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.screen.action_show("tainacan-maintenance")
            await pilot.pause(2.0)
            choose(current_view(app), "tainacan-status")
            await pilot.pause(1.5)
            screen = app.screen
            said = isinstance(screen, MessageScreen) and screen._kind == "error" and reason in screen._body \
                and "keeps the diagnosis before" in screen._body
            await pilot.press("escape")
            await pilot.pause(0.3)
            app.screen.action_show("dashboard")
            app.screen.query_one("#dash-tabs", TabbedContent).active = "dash-tab-tainacan"
            await pilot.pause(2.5)
            return said, card(app.screen.query_one("#view-dashboard"), "dash-tn-content")

    said, (value, note) = asyncio.run(main())
    assert said
    assert value == "4 collections · 1250 items · 3110 attachments"
    assert f"read at {platforms.when(1793872800)}" in note
    assert f"The diagnosis at {platforms.when(1793880000)} failed" in note


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_the_tabs_lead_to_the_tools_and_the_homes_lead_back_to_the_tabs(server):
    from textual.widgets import ContentSwitcher, TabbedContent

    async def main():
        app = make_app()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(2.5)
            tabs = app.screen.query_one("#dash-tabs", TabbedContent)
            tabs.active = "dash-tab-tainacan"
            await pilot.pause(0.3)
            dash = app.screen.query_one("#view-dashboard")
            content = card(dash, "dash-tn-content")
            dash.query_one("#dash-open-tainacan").press()
            await pilot.pause(2.0)
            from_tab = app.screen.query_one("#views", ContentSwitcher).current
            current_view(app).query_one("#home-dashboard").press()
            await pilot.pause(0.5)
            back = app.screen.query_one("#views", ContentSwitcher).current, tabs.active
            tabs.active = "dash-tab-koha"
            await pilot.pause(0.3)
            dash.query_one("#dash-open-koha").press()
            await pilot.pause(0.5)
            return content, from_tab, back, app.screen.query_one("#views", ContentSwitcher).current

    content, from_tab, back, koha = asyncio.run(main())
    assert content[0] == "4 collections · 1250 items · 3110 attachments"
    assert from_tab == "view-tainacan"
    assert back == ("view-dashboard", "dash-tab-tainacan")
    assert koha == "view-koha"


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_the_koha_tab_holds_koha_and_general_holds_the_server(server):
    from textual.widgets import Button

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(2.5)
            dash = app.screen.query_one("#view-dashboard")
            general = [w.id for w in dash.query_one("#dash-tab-general").query(".status-card")]
            koha = [w.id for w in dash.query_one("#dash-tab-koha").query(".status-card")]
            return (dash.query_one("#restart-koha", Button).disabled, card(dash, "card-state")[0],
                    dash.query_one("#addresses").display, card(dash, "health-db")[0], general, koha)

    disabled, state, addresses, db, general, koha = asyncio.run(main())
    assert disabled is False and state == "Running" and addresses is True and db != "-"
    assert general == ["dash-platform-koha", "dash-platform-tainacan", "card-disk", "health-cpu", "health-memory",
                       "health-updates"]
    for koha_only in ("health-db", "health-backup-dir", "health-errors", "health-koha-updates", "health-tunnel",
                      "health-sru", "health-z3950"):
        assert koha_only in koha


# ----------------------------------------------------------------------
# What the panel reads, and what the installer keeps
# ----------------------------------------------------------------------
def test_tainacan_detection_is_a_file_test(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_TAINACAN_DIR", str(tmp_path))
    env = PanelEnv(installer=None, lang="en", plain=False)
    assert not platforms.tainacan_detected(env)
    state = tmp_path / "state"
    state.write_text("status=installing\n")
    assert not platforms.tainacan_detected(env)
    state.write_text("status=installing\nurl=http://x:8090\nstatus=installed\n")
    assert platforms.tainacan_detected(env)
    # The installer's own file and key.
    assert 'KEI_TAINACAN_DIR="${KEI_TAINACAN_DIR:-$KEI_OWNED_DIR/platforms/tainacan}"' in TEXT
    assert "_kei_tn_state_file() { printf '%s/state' \"$KEI_TAINACAN_DIR\"; }" in TEXT


def test_only_known_fields_of_the_last_diagnosis_are_shown():
    state = platforms.tainacan_from_status({"platforms": [{
        "id": "tainacan", "supported": True, "status": "installed", "url": "http://a:8090/",
        "admin_url": "javascript:alert(1)",
        "checked": {"checked_at": "1793872800", "collections": "4; rm -rf /", "items": "12",
                    "password": "secret", "disk_db": "84.2MB", "failed_at": "1"}}]})
    assert state.admin_url == ""
    assert dict(state.checked) == {"checked_at": "1793872800", "items": "12", "disk_db": "84.2MB", "failed_at": "1"}
    assert state.failed_at == 0                          # older than the good read: not a failure now


def test_summary_without_a_diagnosis_says_how_to_get_one():
    state = platforms.TainacanState(True, "installed", services="active")
    cards = platforms.tainacan_summary(state, platforms.DockerState(), platforms.BackupState())
    assert cards["content"][0] == "Not read yet" and "Diagnosis" in cards["content"][1]
    assert cards["events"][0] == "Turned off"


def test_the_installer_keeps_the_last_diagnosis_without_secrets():
    body = re.search(r"^kei_tainacan_check\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    assert 'chmod 600 "$tmp"' in body and 'chmod 700 "$KEI_TAINACAN_DIR"' in body
    keys = re.search(r"^KEI_TN_LAST_KEYS='([^']*)'", TEXT, re.M).group(1).split("|")
    assert not [k for k in keys if re.search(r"pass|key|token|secret|link|cred", k)]
    # A failed read keeps the good one and only adds when it failed.
    assert "grep -Ev '^(failed_at|failed_reason)='" in body
    # --status-json: the admin address and the kept diagnosis, only with Tainacan here.
    assert '"admin_url":%s' in TEXT and '"checked":{%s}' in TEXT
    assert 'if [ "$detected" = true ] && [ -f "$KEI_TAINACAN_DIR/last-status" ]' in TEXT
