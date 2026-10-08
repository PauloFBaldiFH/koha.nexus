"""The messaging & interoperability screen (views/hub.py), headless in demo mode."""

import asyncio
import time

from conftest import INSTALLER
from textual.widgets import DataTable, Input, Select, Switch, TabbedContent

from kei_panel import sip
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def _app(monkeypatch, opened):
    from kei_panel.app import KohaPanelApp
    app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
    monkeypatch.setattr(app, "open_url", lambda url, new_tab=True: opened.append(url))
    return app


def test_status_links_and_gmail_sheet(monkeypatch):
    opened: list[str] = []
    copied: list[str] = []

    async def main():
        app = _app(monkeypatch, opened)
        monkeypatch.setattr(app, "copy_to_clipboard", lambda text, quiet=False: copied.append(text))
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("m")
            view = app.screen.query_one("#view-hub")
            await _until(pilot, lambda: view.staff_url)
            state = str(view.query_one("#h-email-state").render())
            assert "E-mail: on" in state and "library@example.org" in state and "Gmail" in state
            assert view.query_one("#h-smtp", DataTable).row_count == 1
            assert view.query_one("#h-gmail-table", DataTable).row_count == 7
            assert "SIP2: stopped" in str(view.query_one("#h-sip-state").render())
            assert "Z39.50: running" in str(view.query_one("#h-z-state").render())
            assert "no driver" in str(view.query_one("#h-sms-state").render())

            for bid in ("h-l-smtp", "h-l-smtp-add", "h-l-admin-email", "h-apppass", "h-l-sms", "h-l-msgprefs-sms"):
                view.query_one(f"#{bid}").press()
                await pilot.pause(0.05)
            assert opened == [
                "http://192.0.2.10:8080/cgi-bin/koha/admin/smtp_servers.pl",
                "http://192.0.2.10:8080/cgi-bin/koha/admin/smtp_servers.pl?op=add_form",
                "http://192.0.2.10:8080/cgi-bin/koha/admin/preferences.pl?op=search&searchfield=KohaAdminEmailAddress",
                "https://myaccount.google.com/apppasswords",
                "http://192.0.2.10:8080/cgi-bin/koha/admin/preferences.pl?op=search&searchfield=SMSSendDriver",
                "http://192.0.2.10:8080/cgi-bin/koha/admin/preferences.pl?op=search"
                "&searchfield=EnhancedMessagingPreferences",
            ]
            view.query_one("#h-copy-host").press()
            await pilot.pause(0.05)
            assert copied == ["smtp.gmail.com"]

            # Z39.50 tab: its servers screen is one button away.
            view.query_one("#hub-tabs", TabbedContent).active = "hub-z3950"
            await pilot.pause(0.1)
            view.query_one("#h-z-servers").press()
            await _until(pilot, lambda: app.screen.query_one("#views").current == "view-z3950")

    asyncio.run(main())


def test_sip_wizard_writes_the_xml(tmp_path, monkeypatch):
    conf = tmp_path / "SIPconfig.xml"
    monkeypatch.setenv("KEI_SIP_CONF", str(conf))
    sent = {}
    real = sip.write_temp

    def spy(text):
        sent["text"] = text
        sent["path"] = real(text)
        sent["mode"] = sent["path"].stat().st_mode & 0o777
        return sent["path"]
    monkeypatch.setattr(sip, "write_temp", spy)
    opened: list[str] = []

    async def main():
        app = _app(monkeypatch, opened)
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("m")
            view = app.screen.query_one("#view-hub")
            await _until(pilot, lambda: view.branches)
            view.query_one("#hub-tabs", TabbedContent).active = "hub-sip"
            await pilot.pause(0.1)
            assert view.query_one("#h-sip-port", Input).value == "6001"
            assert view.query_one("#h-sip-examples", Switch).value is True

            # Koha's example login is refused, so is a short password.
            view.query_one("#h-sip-login", Input).value = "term1"
            assert "example" in view.sip_settings()[1]
            view.query_one("#h-sip-login", Input).value = "selfcheck"
            view.query_one("#h-sip-password", Input).value = "short"
            assert "8 characters" in view.sip_settings()[1]
            view.query_one("#h-sip-password", Input).value = "S3lf-Check-99"
            assert "library" in view.sip_settings()[1]
            view.query_one("#h-sip-branch", Select).value = "MPL"
            view.query_one("#h-sip-public", Select).value = "public"
            view.query_one("#h-sip-port", Input).value = "6010"
            view.query_one("#h-sip-renewal", Switch).value = False
            assert view.sip_settings()[1] == ""

            view.query_one("#h-l-sip-patron").press()
            await pilot.pause(0.05)
            assert opened == ["http://192.0.2.10:8080/cgi-bin/koha/members/memberentry.pl?op=add_form"]

            view.query_one("#h-sip-save").press()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            preview = app.screen._preview
            assert "0.0.0.0:6010" in preview and "selfcheck" in preview and "MPL" in preview
            assert "S3lf-Check-99" not in preview
            await pilot.pause(0.1)
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen) and app.screen.query("#ok"))
            assert "SIP2 is set up" in app.screen._body
            assert not sent["path"].exists() and sent["mode"] == 0o600
            text = sent["text"]
            assert 'port="0.0.0.0:6010/tcp"' in text
            assert [lg["id"] for lg in sip.logins(text)] == ["selfcheck"]
            assert 'password="S3lf-Check-99"' in text and 'institution="MPL"' in text
            assert 'renewal="false"' in text

    asyncio.run(main())
