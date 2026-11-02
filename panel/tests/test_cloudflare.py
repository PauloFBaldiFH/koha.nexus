"""The Cloudflare Tunnel screen (screens/cloudflare.py) and its tasks."""

import asyncio
import re

from conftest import INSTALLER

from kei_panel.screens import cloudflare as cf

TEXT = INSTALLER.read_text(encoding="utf-8")


def _app():
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    return KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))


async def _wait_for(pilot, kind, tries=80):
    for _ in range(tries):
        await pilot.pause(0.1)
        if isinstance(pilot.app.screen, kind) and pilot.app.screen.query("Button"):
            await pilot.pause(0.1)
            return pilot.app.screen
    raise AssertionError(f"{kind.__name__} never shown (on {type(pilot.app.screen).__name__})")


# ----------------------------------------------------------------------
# Parsing the task answers
# ----------------------------------------------------------------------
def test_status_of_an_own_domain():
    s = cf.parse_status(
        {"mode": "domain", "opac": "catalog.lib.org", "staff": "admin.lib.org", "service": "inactive",
         "enabled": "disabled", "version": "2026.9.1", "package": "yes", "connections": "x",
         "opac_base": "https://catalog.lib.org/", "local_ip": "10.0.0.5"},
        {"ingress": ["catalog.lib.org\thttp://localhost:80", "admin.lib.org\thttp://localhost:8080",
                     "wiki.lib.org\thttp://localhost:3000"], "edge": ["gru02", "gru01"]})
    assert s.paused and not s.running and s.connections == 0 and s.edges == ["gru01", "gru02"]
    assert s.koha_ok                                    # a trailing slash is the same address
    assert s.koha_urls() == ("https://catalog.lib.org", "https://admin.lib.org")
    rows = cf.addresses(s)
    assert [(a.kind, a.url) for a in rows] == [("opac", "https://catalog.lib.org"),
                                               ("staff", "https://admin.lib.org"),
                                               ("other", "https://wiki.lib.org")]
    assert "Paused" in cf.pill(s).plain


def test_free_address_without_remote_staff():
    s = cf.parse_status({"mode": "broker", "opac": "bib.koha.nexus", "staff": "", "service": "active",
                         "enabled": "enabled", "staff_host": "bib-admin.koha.nexus", "local_ip": "192.168.0.10",
                         "opac_base": "http://192.168.0.10"}, {})
    assert s.running and not s.koha_ok
    assert s.koha_urls() == ("https://bib.koha.nexus", "http://192.168.0.10:8080")
    rows = cf.addresses(s)
    assert rows[0].url == "https://bib.koha.nexus" and rows[1].kind == "staff" and "local" in rows[1].url
    assert "Online" in cf.pill(s).plain and "bib.koha.nexus" in cf.pill(s).plain
    assert "Not published" in cf.pill(cf.TunnelState()).plain
    stopped = cf.parse_status({"mode": "broker", "opac": "x", "service": "failed", "enabled": "enabled"}, {})
    assert not stopped.paused and "stopped" in cf.pill(stopped).plain


def test_checks_parse_and_advise():
    checks = cf.parse_checks(["service\tok\t", "public-opac\tfail\tHTTP 530", "koha-url\twarn\thttp://x", ""])
    assert [(c.id, c.state, c.detail) for c in checks] == [("service", "ok", ""), ("public-opac", "fail", "HTTP 530"),
                                                           ("koha-url", "warn", "http://x")]
    assert checks[0].advice == "" and "Reconnect" in checks[1].advice and "OPACBaseURL" in checks[2].label


def test_every_check_and_task_is_known_to_both_sides():
    body = re.search(r"^cf_check\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    ids = set(re.findall(r"cf_check_row ([a-z-]+) ", body))
    assert ids == set(cf.CHECKS)
    from kei_panel.bridge import installer_tasks
    tasks = installer_tasks(INSTALLER)
    assert {"cf-status", "cf-check", "cf-service", "cf-urls", "cf-qr", "cf-update", "cf-run"} <= tasks
    run = re.search(r"^cf_run\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    names = set(re.findall(r"^        ([a-z]+)\)\s+fn=", run, re.M))
    assert {name for name, _ in cf.CloudflareScreen.WIZARDS.values()} == names
    for fn in re.findall(r"fn=([a-z_]+)", run):
        assert re.search(rf"^{fn}\(\) \{{", TEXT, re.M), fn


# ----------------------------------------------------------------------
# The screen, in demo mode
# ----------------------------------------------------------------------
def test_screen_shows_state_addresses_and_test():
    async def main():
        app = _app()
        async with app.run_test(size=(160, 48)) as pilot:
            app.run_native("cloudflare")
            screen = await _wait_for(pilot, cf.CloudflareScreen)
            for _ in range(40):
                await pilot.pause(0.1)
                if screen.checks:
                    break

            def text(sel):
                return str(screen.query_one(sel).render())
            return (text("#cf-pill"), text("#cf-s-service"), text("#cf-s-conn"), text("#cf-w-list"),
                    screen.query_one("#cf-addr").row_count, [c.id for c in screen.checks], text("#cf-check-sum"),
                    text("#cf-k-note"), screen.query_one("#cf-free-manage").display,
                    screen.query_one("#cf-run-domain").disabled, text("#cf-log"), str(screen.query_one("#cf-pause").label))
    (pill, service, conn, where, rows, checks, summary, koha, manage, domain_off, log, pause) = asyncio.run(main())
    assert "Online" in pill and "biblioteca.koha.nexus" in pill
    assert "running" in service and "4" in conn and "gru01" in conn
    assert "https://biblioteca.koha.nexus" in where and rows == 2
    assert checks[0] == "service" and "koha-url" in checks and "warning" in summary
    assert "does not use" in koha and manage and domain_off and "Registered" in log and "Pause" in pause


def test_qr_pause_and_koha_addresses():
    from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen

    async def main():
        app = _app()
        async with app.run_test(size=(160, 48)) as pilot:
            app.run_native("cloudflare")
            screen = await _wait_for(pilot, cf.CloudflareScreen)
            await pilot.pause(0.5)
            screen.query_one("#cf-qr").press()
            for _ in range(30):
                await pilot.pause(0.1)
                if screen.qr:
                    break
            qr = (screen.query_one("#cf-qr-card").display, screen.qr_png)
            screen.query_one("#cf-fix-urls").press()
            confirm = await _wait_for(pilot, ConfirmScreen)
            question = confirm._question
            confirm.dismiss(True)
            done = await _wait_for(pilot, MessageScreen)
            body = done._body
            done.dismiss(None)
            await _wait_for(pilot, cf.CloudflareScreen)
            screen.query_one("#cf-pause").press()
            pause = await _wait_for(pilot, ConfirmScreen)
            danger = pause._danger
            pause.dismiss(False)
            await pilot.pause(0.3)
            return qr, question, body, danger
    qr, question, body, danger = asyncio.run(main())
    assert qr == (True, "/home/biblioteca/koha-catalog-qr.png")
    assert "https://biblioteca.koha.nexus" in question and "http://192.168.0.10:8080" in question
    assert "OPACBaseURL" in body and danger
