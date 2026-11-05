"""Tainacan's own section and the dashboard's tabs (plan Q, PR 1).

The panel on four servers (demo mode): no platform, Koha only, Tainacan
only, both. The section and the tabs follow what is installed; opening
them reads, never changes, the server; the full diagnosis only runs when
asked, and a failed one keeps the one before with its time.
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
# The tasks the section and the tab may call while they are drawn: reads.
READS = {"platform-backup-status"}


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


# ----------------------------------------------------------------------
# Four servers: the sidebar and the dashboard's tabs
# ----------------------------------------------------------------------
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
            return sidebar_ids(app), shown, tabs.active, ran

    ids, shown, active, ran = asyncio.run(main())
    koha, tainacan = server in ("koha", "both"), server in ("tainacan", "both")
    assert ("tainacan" in ids) is tainacan
    assert ("backup" in ids) is koha                      # Koha's sections, as before
    assert "platforms" in ids and "dashboard" in ids
    assert shown == {"dash-tab-general": True, "dash-tab-koha": koha, "dash-tab-tainacan": tainacan}
    assert active == "dash-tab-general"
    # The dashboard only reads: --status-json, and the backup engine's state with Tainacan.
    assert {name for name, _a in ran} <= READS
    assert bool(ran) is tainacan


@pytest.mark.parametrize("server", ["none", "koha"], indirect=True)
def test_without_tainacan_its_key_shows_the_reason_and_loads_nothing(server):
    from textual.widgets import ContentSwitcher, Label

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test() as pilot:
            await open_section(app, pilot, "g")
            switcher = app.screen.query_one("#views", ContentSwitcher)
            current = switcher.current
            reason = str(app.screen.query_one(f"#{current} #unavailable-reason", Label).render())
            real = [w.id for w in switcher.children if w.id == "view-tainacan"]
            return current, reason, real, ran

    current, reason, real, ran = asyncio.run(main())
    assert current == "view-tainacan-off" and real == []
    assert "Tainacan is not installed" in reason and "Platforms" in reason
    assert ran == []


@pytest.mark.parametrize("server", ["tainacan", "both"], indirect=True)
def test_the_section_shows_the_summary_and_changes_nothing(server):
    from kei_panel.widgets.cards import LinkCard

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test() as pilot:
            await open_section(app, pilot, "g")
            view = app.screen.query_one("#view-tainacan")
            links = {k: view.query_one(f"#tn-link-{k}", LinkCard).url for k in ("site", "admin")}
            cards = {k: card(view, f"tn-{k}") for k in ("state", "events", "content", "versions", "backup",
                                                         "restore-test")}
            notes = " ".join(str(w.render()) for w in view.query(".view-prompt"))
            buttons = {b: view.query_one(f"#{b}").display for b in
                       ("tainacan-status", "tainacan-logs", "tainacan-credentials", "events-on", "events-off",
                        "events-status")}
            return links, cards, notes, buttons, ran

    links, cards, notes, buttons, ran = asyncio.run(main())
    assert links == {"site": "http://192.168.0.20:8090/", "admin": "http://192.168.0.20:8090/wp-admin/"}
    assert cards["state"][0] == "Installed"
    assert cards["events"][0] == "Turned off"
    assert cards["content"][0] == "4 collections · 1250 items · 3110 attachments"
    assert cards["content"][1] == f"read at {platforms.when(1793872800)}"
    assert "WordPress 6.8.3" in cards["versions"][0] and "84.2MB + 2.1GB" in cards["versions"][1]
    assert cards["backup"][0] == "2026-11-05 02:30:00"         # the demo engine's newest
    # Koha's accounts are never WordPress administrators.
    assert "superlibrarian" in notes and "not WordPress accounts" in notes
    assert buttons == {"tainacan-status": True, "tainacan-logs": True, "tainacan-credentials": True,
                       "events-on": True, "events-off": False, "events-status": True}
    assert {name for name, _a in ran} <= READS


@pytest.mark.parametrize("server", ["tainacan"], indirect=True)
def test_the_diagnosis_runs_only_when_asked_and_says_when_it_was_read(server):
    from kei_panel.screens.dialogs import TextScreen

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test() as pilot:
            await open_section(app, pilot, "g")
            before = [name for name, _a in ran]
            app.screen.query_one("#tainacan-status").press()
            await pilot.pause(1.5)
            text = app.screen._text if isinstance(app.screen, TextScreen) else ""
            return before, text, [name for name, _a in ran]

    before, text, after = asyncio.run(main())
    assert "tainacan-status" not in before
    assert after.count("tainacan-status") == 1
    assert "Collections: 3" in text and f"Read at {platforms.when(1793872800)}." in text


@pytest.mark.parametrize("server", ["tainacan"], indirect=True)
def test_a_failed_diagnosis_keeps_the_one_before_marked_as_old(server):
    from kei_panel.screens.dialogs import MessageScreen

    reason = "The diagnosis could not read Tainacan. Docker is not running."
    old = {"checked": {"checked_at": "1793872800", "collections": "4", "items": "1250", "attachments": "3110",
                       "attachments_missing": "0", "failed_at": "1793880000"}}

    async def main():
        app = make_app(fail={"tainacan-status": reason}, status_patch=old)
        async with app.run_test() as pilot:
            await open_section(app, pilot, "g")
            app.screen.query_one("#tainacan-status").press()
            await pilot.pause(1.5)
            screen = app.screen
            said = isinstance(screen, MessageScreen) and screen._kind == "error" and reason in screen._body \
                and "keeps the diagnosis before" in screen._body
            await pilot.press("escape")
            await pilot.pause(2.0)
            return said, card(app.screen.query_one("#view-tainacan"), "tn-content")

    said, (value, note) = asyncio.run(main())
    assert said
    assert value == "4 collections · 1250 items · 3110 attachments"
    assert f"read at {platforms.when(1793872800)}" in note
    assert f"The diagnosis at {platforms.when(1793880000)} failed" in note


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_the_tainacan_tab_and_the_platforms_card_open_the_section(server):
    from textual.widgets import ContentSwitcher, TabbedContent

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(2.5)
            tabs = app.screen.query_one("#dash-tabs", TabbedContent)
            tabs.active = "dash-tab-tainacan"
            await pilot.pause(0.3)
            dash = app.screen.query_one("#view-dashboard")
            content = card(dash, "dash-tn-content")
            dash.query_one("#dash-open-tainacan").press()
            await pilot.pause(0.5)
            from_tab = app.screen.query_one("#views", ContentSwitcher).current
            await open_section(app, pilot, "p")
            button = app.screen.query_one("#tainacan-section")
            shown = button.display
            button.press()
            await pilot.pause(0.5)
            return content, from_tab, shown, app.screen.query_one("#views", ContentSwitcher).current

    content, from_tab, shown, from_card = asyncio.run(main())
    assert content[0] == "4 collections · 1250 items · 3110 attachments"
    assert from_tab == "view-tainacan"
    assert shown and from_card == "view-tainacan"


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_the_koha_tab_keeps_the_dashboard_as_it_was(server):
    from textual.widgets import Button

    async def main():
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.pause(2.5)
            dash = app.screen.query_one("#view-dashboard")
            return (dash.query_one("#restart-koha", Button).disabled, card(dash, "card-state")[0],
                    dash.query_one("#addresses").display, card(dash, "health-db")[0])

    disabled, state, addresses, db = asyncio.run(main())
    assert disabled is False and state == "Running" and addresses is True and db != "-"


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
