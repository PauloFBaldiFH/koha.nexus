"""vpn.py and the WireGuard VPN screen (demo mode)."""

import asyncio
import shutil
import time

import pytest
from conftest import INSTALLER
from textual.widgets import DataTable, Input

from kei_panel import vpn
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen
from kei_panel.screens.vpn import ProfileScreen


def test_answers():
    assert vpn.name_problem("maria-laptop") == "" and vpn.name_problem("Desk_2") == ""
    for bad in ("", "-x", "a b", "../etc", "x" * 33):
        assert vpn.name_problem(bad), bad
    assert vpn.endpoint_problem("vpn.library.org") == "" and vpn.endpoint_problem("203.0.113.7") == ""
    assert vpn.endpoint_problem("http://x") and vpn.endpoint_problem("a b") and vpn.endpoint_problem("")
    assert vpn.port_problem("51820") == "" and vpn.port_problem("80") and vpn.port_problem("x")


def test_profile_problem_enforces_split_tunnel():
    good = vpn.DEMO_PROFILE
    assert vpn.profile_problem(good) == ""
    assert "10.66.0.0/24" in vpn.profile_problem(good.replace("AllowedIPs = 10.66.0.0/24", "AllowedIPs = 0.0.0.0/0"))
    assert "10.66.0.0/24" in vpn.profile_problem(good.replace("10.66.0.0/24\n", "10.66.0.0/24, 0.0.0.0/0\n"))
    assert "DNS" in vpn.profile_problem(good.replace("MTU = 1360", "MTU = 1360\nDNS = 1.1.1.1"))
    assert "MTU" in vpn.profile_problem(good.replace("MTU = 1360", "MTU = 1420"))
    assert "MTU" in vpn.profile_problem(good.replace("PersistentKeepalive = 25", ""))
    assert vpn.profile_problem(good.replace("Endpoint", "# Endpoint"))


def test_peer_rows_sizes_and_ages():
    p = vpn.parse_peer("laptop\t10.66.0.2\t1760000000\t1048576\t42")
    assert p == {"name": "laptop", "address": "10.66.0.2", "handshake": 1760000000, "rx": 1048576, "tx": 42}
    assert vpn.parse_peer("x")["rx"] == 0
    assert vpn.size(42) == "42 B" and vpn.size(1048576) == "1.0 MB" and vpn.size(3 * 1024 ** 3) == "3.0 GB"
    now = time.time()
    assert vpn.ago(0) == ("never", 0)
    assert vpn.ago(int(now) - 30, now) == ("seconds", 30)
    assert vpn.ago(int(now) - 600, now) == ("minutes", 10)
    assert vpn.ago(int(now) - 3 * 86400, now) == ("days", 3)


@pytest.mark.skipif(not shutil.which("qrencode"), reason="qrencode not installed")
def test_qr_code():
    code = vpn.qr(vpn.DEMO_PROFILE)
    assert "▀" in code or "▄" in code or "█" in code
    assert vpn.qr("x", qrencode="no-such-qrencode") == ""


def test_read_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_WG_PEERS", str(tmp_path))
    (tmp_path / "laptop.conf").write_text(vpn.DEMO_PROFILE)
    assert vpn.read_profile("laptop") == vpn.DEMO_PROFILE


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_vpn_screen(monkeypatch):
    from kei_panel.app import KohaPanelApp
    copied: list[str] = []
    ran: list[tuple] = []
    from kei_panel.routines import common
    real = common.run_task

    async def spy(app, title, name, *args, **kw):
        ran.append((name, *args))
        return await real(app, title, name, *args, **kw)
    monkeypatch.setattr(common, "run_task", spy)

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        monkeypatch.setattr(app, "copy_to_clipboard", lambda text, quiet=False: copied.append(text))
        async with app.run_test(size=(160, 70)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("v")
            view = app.screen.query_one("#view-vpn")
            await _until(pilot, lambda: view.peers)
            assert "VPN on: vpn.example.org, UDP port 51820. Devices: 2." in str(view.query_one("#v-state").render())
            assert view.query_one("#v-endpoint", Input).value == "vpn.example.org"
            assert view.query_one("#v-peers", DataTable).row_count == 2
            assert "http://10.66.0.1:8080" in str(view.query_one("#v-howto").render())

            # Set up: what will happen is shown first.
            view.query_one("#v-port", Input).value = "80"
            view.setup()
            await pilot.pause(0.1)
            assert not isinstance(app.screen, ConfirmScreen)
            view.query_one("#v-port", Input).value = "51820"
            view.setup()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "MASQUERADE" in app.screen._preview and "vpn.example.org:51820" in app.screen._preview
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen) and app.screen.query("#ok"))
            assert "The VPN is on" in app.screen._body
            await pilot.press("escape")
            assert ("vpn-setup", "vpn.example.org", "51820") in ran

            # A device: added, then its QR code and profile.
            view.query_one("#v-name", Input).value = "front-desk"
            view.add()
            await pilot.pause(0.1)
            assert not ran[-1][0] == "vpn-peer-add"           # the name is taken
            view.query_one("#v-name", Input).value = "joao-laptop"
            view.add()
            await _until(pilot, lambda: isinstance(app.screen, ProfileScreen))
            assert ("vpn-peer-add", "joao-laptop") in ran
            screen = app.screen
            assert "VPN: joao-laptop" in screen.profile
            if shutil.which("qrencode"):
                assert screen.code
            screen.query_one("#vpn-copy").press()
            await pilot.pause(0.05)
            assert copied and "AllowedIPs = 10.66.0.0/24" in copied[0] and "0.0.0.0/0" not in copied[0]
            screen.query_one("#close").press()
            await _until(pilot, lambda: not isinstance(app.screen, ProfileScreen))

            # Revoke the selected device, after a warning.
            table = view.query_one("#v-peers", DataTable)
            table.move_cursor(row=1)
            assert view.selected() == "maria-phone"
            view.revoke()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert app.screen._danger and "maria-phone" in app.screen._question
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen) and app.screen.query("#ok"))
            assert ("vpn-peer-revoke", "maria-phone") in ran

    asyncio.run(main())


def test_unsafe_profile_is_not_shown(monkeypatch):
    from kei_panel.app import KohaPanelApp
    monkeypatch.setattr(vpn, "DEMO_PROFILE", vpn.DEMO_PROFILE.replace("10.66.0.0/24\n", "0.0.0.0/0\n"))

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("v")
            view = app.screen.query_one("#view-vpn")
            await _until(pilot, lambda: view.peers)
            view.show_selected()
            await pilot.pause(0.3)
            assert not isinstance(app.screen, ProfileScreen)

    asyncio.run(main())
