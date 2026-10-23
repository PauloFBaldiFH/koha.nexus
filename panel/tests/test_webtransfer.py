"""Backups through the person's browser over SSH (kei_panel.webtransfer and
screens/web_transfer): upload in pieces checked by size and SHA-256,
download of one file, TLS with a certificate of this run, the token, ufw."""

import asyncio
import hashlib
import json
import shutil
import ssl
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import INSTALLER

from kei_panel import opener, transfer, webtransfer
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ChoiceScreen
from kei_panel.screens.web_transfer import WebTransferScreen
from kei_panel.webtransfer import TransferServer


def server(tmp_path, mode="upload", file=None, tls=False):
    s = TransferServer(mode, folder=tmp_path / "received", file=file, hosts=["127.0.0.1"], port=0,
                       bind="127.0.0.1", tls=tls, firewall=False)
    s.start()
    return s


def request(s, method, route, params="", body=None, token=None):
    scheme = "https" if s.tls else "http"
    url = f"{scheme}://127.0.0.1:{s.port}/t/{token or s.token}/{route}{'?' + params if params else ''}"
    ctx = ssl._create_unverified_context() if s.tls else None    # the test trusts its own certificate
    req = urllib.request.Request(url, data=body, method=method)
    handlers = [urllib.request.ProxyHandler({})]      # 127.0.0.1, never through a proxy
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    try:
        with urllib.request.build_opener(*handlers).open(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def send(s, name, data, chunk=5, sha=None):
    q = f"name={name}&size={len(data)}"
    code, body = request(s, "GET", "status", q)
    assert code == 200, body
    offset = json.loads(body)["offset"]
    while offset < len(data):
        code, body = request(s, "PUT", "chunk", f"{q}&offset={offset}", data[offset:offset + chunk])
        assert code == 200, body
        offset = json.loads(body)["offset"]
    return request(s, "POST", "finish", f"{q}&sha256={sha or hashlib.sha256(data).hexdigest()}", b"")


def test_addresses_take_the_ssh_one_first_without_repeats():
    assert webtransfer.addresses("203.0.113.5 50000 198.51.100.7 22", "198.51.100.7") == ["198.51.100.7"]
    assert webtransfer.addresses("203.0.113.5 50000 10.0.0.4 22", "198.51.100.7") == ["10.0.0.4", "198.51.100.7"]
    assert webtransfer.addresses("2001:db8::1 5 2001:db8::2 22", None) == ["[2001:db8::2]"]
    assert webtransfer.addresses(None, "") == []


def test_upload_is_written_only_when_size_and_sha256_match(tmp_path):
    s = server(tmp_path)
    try:
        data = bytes(range(256)) * 41
        code, body = send(s, "koha_2026.sql.gz", data, chunk=1000)
        assert code == 200 and json.loads(body)["name"] == "koha_2026.sql.gz"
        got = tmp_path / "received" / "koha_2026.sql.gz"
        assert got.read_bytes() == data
        assert s.state()["received"] == got
        assert not list((tmp_path / "received").glob(".*.part"))
        # Once a file came in, the page takes no other.
        code, _ = request(s, "GET", "status", "name=b.sql&size=3")
        assert code == 403
    finally:
        s.stop()


def test_a_damaged_upload_is_thrown_away(tmp_path):
    s = server(tmp_path)
    try:
        code, body = send(s, "k.sql", b"select 1;\n" * 20, sha="0" * 64)
        assert code == 409 and "SHA-256" in json.loads(body)["error"]
        assert not list((tmp_path / "received").iterdir())
        assert s.state()["received"] is None and s.state()["error"]
    finally:
        s.stop()


def test_a_piece_sent_twice_is_not_written_twice(tmp_path):
    s = server(tmp_path)
    try:
        data = b"0123456789"
        q = "name=k.sql&size=10"
        request(s, "GET", "status", q)
        assert json.loads(request(s, "PUT", "chunk", q + "&offset=0", data[:4])[1])["offset"] == 4
        # The answer was lost: the page sends the same piece again.
        assert json.loads(request(s, "PUT", "chunk", q + "&offset=0", data[:4])[1])["offset"] == 4
        # A reloaded page asks where to go on from.
        assert json.loads(request(s, "GET", "status", q)[1])["offset"] == 4
        request(s, "PUT", "chunk", q + "&offset=4", data[4:])
        code, _ = request(s, "POST", "finish", q + f"&sha256={hashlib.sha256(data).hexdigest()}", b"")
        assert code == 200 and (tmp_path / "received" / "k.sql").read_bytes() == data
    finally:
        s.stop()


def test_only_backups_and_only_the_token(tmp_path):
    s = server(tmp_path)
    try:
        assert request(s, "GET", "status", "name=notes.txt&size=3")[0] == 403
        assert request(s, "GET", "status", "name=../../etc/k.sql&size=3")[0] == 200
        assert (tmp_path / "received" / ".k.sql.part").exists()     # the folders were dropped
        assert request(s, "GET", "", token="wrong")[0] == 404
        code, page = request(s, "GET", "")
        assert code == 200 and b"Sha256" in page and s.token.encode() not in page
    finally:
        s.stop()
    assert not (tmp_path / "received" / ".k.sql.part").exists()    # stop() leaves no half file


def test_download_over_tls_with_its_own_certificate(tmp_path):
    if not shutil.which("openssl"):
        pytest.skip("openssl")
    src = tmp_path / "koha_daily.sql.gz"
    src.write_bytes(b"backup" * 1000)
    s = server(tmp_path, mode="download", file=src, tls=True)
    try:
        assert s.urls()[0].startswith("https://127.0.0.1:") and len(s.cert_fingerprint) == 95
        code, body = request(s, "GET", "file")
        assert code == 200 and body == src.read_bytes()
        for _ in range(50):
            if s.state()["sha256"]:
                break
            asyncio.run(asyncio.sleep(0.05))
        assert s.state()["sha256"] == hashlib.sha256(src.read_bytes()).hexdigest()
        assert s.state()["downloads"] == 1
        assert request(s, "PUT", "chunk", "name=k.sql&size=1&offset=0", b"x")[0] == 404
    finally:
        s.stop()


def test_ufw_port_opened_only_when_needed(monkeypatch):
    monkeypatch.setattr(webtransfer.shutil, "which", lambda name: "/usr/sbin/" + name)
    calls = []

    def run(status):
        def fake(argv, **_):
            calls.append(argv)
            return SimpleNamespace(stdout=status, returncode=0)
        return fake

    assert webtransfer.ufw_open(8765, run("Status: active\n\n22/tcp  ALLOW  Anywhere\n"))
    assert calls[-1] == ["ufw", "allow", "8765/tcp"]
    calls.clear()
    assert not webtransfer.ufw_open(8765, run("Status: active\n\n8765/tcp  ALLOW  Anywhere\n"))
    assert not webtransfer.ufw_open(8765, run("Status: inactive\n"))
    assert all(argv == ["ufw", "status"] for argv in calls)


def test_ssh_seen_through_sudo_by_the_sshd_above(tmp_path):
    for pid, comm, ppid in ((40, "python3", 30), (30, "sudo", 20), (20, "bash", 10), (10, "sshd", 1)):
        (tmp_path / str(pid)).mkdir()
        (tmp_path / str(pid) / "stat").write_text(f"{pid} ({comm}) S {ppid} 1 1 0")
    assert opener._sshd_above(40, tmp_path)
    (tmp_path / "10" / "stat").write_text("10 (systemd) S 1 1 1 0")
    assert not opener._sshd_above(40, tmp_path)
    assert opener.over_ssh({"SSH_CONNECTION": "a 1 b 22"}, tmp_path)


# ----------------------------------------------------------------------
# The panel: drop over SSH, restore over SSH, download over SSH
# ----------------------------------------------------------------------
def app():
    return KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))


@pytest.fixture
def local_page(monkeypatch, tmp_path):
    """browser_server without TLS, ufw or a public port."""
    from kei_panel.routines import backup
    made = []

    def browser_server(info, mode, file=None):
        s = TransferServer(mode, folder=tmp_path / "received", file=file, hosts=["127.0.0.1"], port=0,
                           bind="127.0.0.1", tls=False, firewall=False)
        made.append(s)
        return s

    async def facts(_app):
        return {"real_user": "ana", "server_ip": "192.0.2.10", "real_home": str(tmp_path),
                "dir_sql": str(tmp_path), "newest": str(tmp_path / "koha_daily.sql.gz")}

    monkeypatch.setattr(backup, "browser_server", browser_server)
    monkeypatch.setattr(backup, "facts", facts)
    monkeypatch.setattr("kei_panel.routines.common.facts", facts)
    monkeypatch.setattr(transfer, "where", lambda: "ssh")
    return made


async def _wait(pilot, test, tries=60):
    for _ in range(tries):
        await pilot.pause(0.1)
        if test():
            return True
    return False


def test_drop_over_ssh_receives_the_file_then_restores_it(local_page, monkeypatch):
    from kei_panel.routines import backup
    restored = []

    async def restore(_app, file=None):
        restored.append(file)

    monkeypatch.setattr(backup, "restore", restore)
    data = b"-- MySQL dump\nselect 1;\n-- Dump completed\n"

    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            a.drop_file("'C:\\Users\\Ana\\koha.sql'")
            ok = await _wait(pilot, lambda: isinstance(a.screen, WebTransferScreen) and a.screen._values)
            assert ok
            urls = list(a.screen._values)
            s = local_page[0]
            threading.Thread(target=send, args=(s, "koha.sql", data), daemon=True).start()
            assert await _wait(pilot, lambda: restored)
            return urls, s
    urls, s = asyncio.run(main())
    assert urls[0] == f"http://127.0.0.1:{s.port}/t/{s.token}/"
    assert any(v.startswith("ssh -L ") and "ana@127.0.0.1" in v for v in urls)
    assert Path(restored[0]).read_bytes() == data
    assert s._httpd is None                       # the page stopped with the screen


def test_restore_over_ssh_asks_where_the_file_is(local_page):
    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            a.run_native("restore")
            assert await _wait(pilot, lambda: isinstance(a.screen, ChoiceScreen))
            a.screen.dismiss("browser")
            assert await _wait(pilot, lambda: isinstance(a.screen, WebTransferScreen))
            return a.screen.server.mode
    assert asyncio.run(main()) == "upload"


def test_download_over_ssh_offers_the_file_in_the_browser(local_page, tmp_path):
    src = tmp_path / "koha_daily.sql.gz"
    src.write_bytes(b"y" * 10)

    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            a.run_native("backup-download")
            assert await _wait(pilot, lambda: isinstance(a.screen, WebTransferScreen) and a.screen._values)
            s = a.screen.server
            got = []
            threading.Thread(target=lambda: got.append(request(s, "GET", "file")[1]), daemon=True).start()
            assert await _wait(pilot, lambda: got)
            body = got[0]
            a.screen.query_one("#close").press()
            await pilot.pause(0.2)
            return s, body
    s, body = asyncio.run(main())
    assert s.mode == "download" and s.file == src and body == src.read_bytes()
    assert s._httpd is None


def test_manual_backup_over_ssh_has_a_browser_download(local_page, monkeypatch, tmp_path):
    from kei_panel.routines import backup
    from kei_panel.screens.save_backup import SaveBackupScreen
    monkeypatch.setattr("kei_panel.screens.web_transfer.browser_server", backup.browser_server)
    monkeypatch.setattr("kei_panel.save_backup.is_wsl", lambda: False)
    done = tmp_path / "koha_manual.sql.gz"
    done.write_bytes(b"z")

    async def main():
        a = app()
        async with a.run_test(size=(120, 40)) as pilot:
            screen = SaveBackupScreen({"real_user": "ana", "real_home": str(tmp_path)})
            a.push_screen(screen)
            await pilot.pause(0.2)
            screen._file = done
            screen._show_done("1 B")
            await pilot.pause(0.1)
            screen.query_one("#web-download").press()
            assert await _wait(pilot, lambda: isinstance(a.screen, WebTransferScreen))
            return a.screen.server
    s = asyncio.run(main())
    assert s.mode == "download" and s.file == done
