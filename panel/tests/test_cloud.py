"""cloud.py and the OneDrive / MEGA / S3 flows of the backup center."""

import asyncio
import json
import os
import socket
import sys
import textwrap

import pytest

from kei_panel import cloud

TOKEN = '{"access_token":"a","token_type":"Bearer","refresh_token":"r","expiry":"2030-01-01T00:00:00Z"}'


def test_validators():
    assert cloud.name_problem("onedrive") == "" and cloud.name_problem("Lib_backup-2") == ""
    assert cloud.name_problem("2drive") and cloud.name_problem("a b") and cloud.name_problem("")
    assert "gdrive" in cloud.name_problem("GDrive")
    assert cloud.bucket_problem("koha-backups") == "" and cloud.bucket_problem("my.bucket.1") == ""
    assert cloud.bucket_problem("Backup_SQL") and cloud.bucket_problem("ab") and cloud.bucket_problem("a..b")
    assert cloud.endpoint_problem("https://s3.wasabisys.com") == ""
    assert cloud.endpoint_problem("http://minio.local:9000/") == ""
    assert cloud.endpoint_problem("s3.wasabisys.com") and cloud.endpoint_problem("https://x/y?z")
    assert cloud.token_problem(TOKEN) == ""
    assert cloud.token_problem('{"access_token":"a"}') and cloud.token_problem("nope")


def test_classify_what_was_pasted():
    assert cloud.classify("  " + TOKEN + "\n").kind == "token"
    assert cloud.classify('{"access_token":"a"}').problem
    url = "http://localhost:53682/?code=M.C123&state=xyz"
    assert cloud.classify(url) == cloud.Pasted("redirect", url)
    assert cloud.classify("http://127.0.0.1:53682/?error=access_denied&state=x").kind == "redirect"
    for bad in ("https://login.microsoftonline.com/?code=1&state=2", "http://localhost:53682/?code=1",
                "http://evil.example/?code=1&state=2", "hello"):
        assert cloud.classify(bad).kind == "", bad


def test_settings_file_is_private_and_refuses_new_lines():
    path = cloud.settings_file("od", "onedrive", {"token": TOKEN})
    try:
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.read_text() == f"name\tod\ntype\tonedrive\ntoken\t{TOKEN}\n"
    finally:
        path.unlink()
    with pytest.raises(ValueError):
        cloud.settings_file("m", "mega", {"pass": "a\tb"})


# ----------------------------------------------------------------------
# A stand-in for `rclone authorize onedrive --auth-no-open-browser`: it
# listens on a port, sends /auth to the provider's page and prints the
# token once the browser's answer (?code=) reaches it.
# ----------------------------------------------------------------------
FAKE_RCLONE = textwrap.dedent('''
    import http.server, sys
    port = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 0
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass
        def do_GET(self):
            if self.path.startswith("/auth"):
                self.send_response(307)
                self.send_header("Location", "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?state=s1")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Success")
            if "code=good" in self.path:
                print("Paste the following into your remote machine --->")
                print(%r)
                print("<---End paste", flush=True)
            else:
                print("Error: access denied", flush=True)
            self.server.done = True
    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    srv.done = False
    print("If your browser doesn't open automatically go to the following link: "
          "http://127.0.0.1:%%d/auth?state=s1" %% srv.server_port, flush=True)
    print("Log in and authorize rclone for access", flush=True)
    print("Waiting for code...", flush=True)
    while not srv.done:
        srv.handle_request()
''') % TOKEN


@pytest.fixture
def fake_rclone(tmp_path):
    script = tmp_path / "rclone_fake.py"
    script.write_text(FAKE_RCLONE)
    exe = tmp_path / "rclone"
    exe.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
    exe.chmod(0o755)
    return str(exe)


def test_authorizer_follows_redirect_and_gets_the_token(fake_rclone):
    async def main():
        auth = cloud.Authorizer("onedrive", rclone=fake_rclone)
        url = await auth.start(wait=10)
        assert url.startswith("https://login.microsoftonline.com/") and auth.port > 0
        waiting = asyncio.create_task(auth.token())
        await auth.answer("http://localhost:53682/?code=good&state=s1")
        return await asyncio.wait_for(waiting, 10)
    assert json.loads(asyncio.run(main()))["access_token"] == "a"


def test_authorizer_reports_a_refusal(fake_rclone):
    async def main():
        auth = cloud.Authorizer("onedrive", rclone=fake_rclone)
        await auth.start(wait=10)
        waiting = asyncio.create_task(auth.token())
        await auth.answer("http://localhost:53682/?error=access_denied&state=s1")
        with pytest.raises(RuntimeError, match="access denied"):
            await asyncio.wait_for(waiting, 10)
    asyncio.run(main())


def test_authorizer_without_a_link_stops(tmp_path):
    exe = tmp_path / "rclone"
    exe.write_text("#!/bin/sh\necho 'Failed to start auth webserver'\n")
    exe.chmod(0o755)

    async def main():
        auth = cloud.Authorizer("onedrive", rclone=str(exe))
        with pytest.raises(RuntimeError, match="authorization link"):
            await auth.start(wait=5)
    asyncio.run(main())


def test_provider_url_falls_back_to_the_local_address():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    local = f"http://127.0.0.1:{port}/auth?state=x"
    assert cloud.provider_url(local, timeout=2) == local


# ----------------------------------------------------------------------
# The flows, in demo mode
# ----------------------------------------------------------------------
def _flow(steps, monkeypatch, *, provider):
    from conftest import INSTALLER  # noqa: F401  (conftest puts the panel on the path)
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.screens.dialogs import ChoiceScreen, InputScreen, MessageScreen
    from kei_panel.screens.oauth import OAuthScreen
    seen = {}
    real = cloud.settings_file

    def spy(name, prov, values):
        seen.update(name=name, provider=prov, values=dict(values))
        seen["path"] = real(name, prov, values)
        return seen["path"]
    monkeypatch.setattr(cloud, "settings_file", spy)

    async def wait_for(pilot, kind):
        for _ in range(80):
            await pilot.pause(0.1)
            if isinstance(pilot.app.screen, kind) and pilot.app.screen.query("Button"):
                await pilot.pause(0.05)
                return pilot.app.screen
        raise AssertionError(f"{kind.__name__} never shown (on {type(pilot.app.screen).__name__})")

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 45)) as pilot:
            app.run_native("backup-cloud")
            (await wait_for(pilot, ChoiceScreen)).dismiss("providers")
            (await wait_for(pilot, ChoiceScreen)).dismiss(provider)
            form = await wait_for(pilot, InputScreen)
            form.query_one("#value").value = "gdrive"
            form.query_one("#ok").press()
            await pilot.pause(0.2)
            assert "Google Drive" in str(form.query_one("#input-error").render())
            form.query_one("#value").value = "lib" + provider
            form.query_one("#ok").press()
            kinds = {"input": InputScreen, "choice": ChoiceScreen, "oauth": OAuthScreen}
            for kind, value in steps:
                screen = await wait_for(pilot, kinds[kind])
                if kind == "choice":
                    screen.dismiss(value)
                elif kind == "input":
                    screen.query_one("#value").value = value
                    screen.query_one("#ok").press()
                else:
                    await value(pilot, screen)
            return await wait_for(pilot, MessageScreen)
    done = asyncio.run(main())
    return done, seen


def test_onedrive_flow_with_copy_link_and_pasted_address(monkeypatch):
    copied = []

    async def sign_in(pilot, screen):
        for _ in range(40):
            await pilot.pause(0.05)
            if screen.url:
                break
        assert screen.url.startswith("https://login.microsoftonline.com/")
        monkeypatch.setattr(pilot.app, "copy_to_clipboard", lambda text, quiet=False: copied.append(text))
        screen.query_one("#oauth-copy").press()
        await pilot.pause(0.05)
        screen.query_one("#oauth-paste").value = "https://example.org/nope"
        screen.query_one("#ok").press()
        await pilot.pause(0.1)
        assert "localhost:53682" in str(screen.query_one("#oauth-status").render())
        screen.query_one("#oauth-paste").value = "http://localhost:53682/?code=M.123&state=demo"
        screen.query_one("#ok").press()

    done, seen = _flow([("oauth", sign_in)], monkeypatch, provider="onedrive")
    assert copied and copied[0].startswith("https://login.microsoftonline.com/")
    assert done._kind == "ok"
    assert seen["name"] == "libonedrive" and seen["provider"] == "onedrive"
    assert json.loads(seen["values"]["token"])["access_token"] == "demo"
    assert not seen["path"].exists()


def test_onedrive_accepts_a_pasted_token(monkeypatch):
    async def paste(pilot, screen):
        screen.query_one("#oauth-paste").value = TOKEN
        screen.query_one("#ok").press()

    done, seen = _flow([("oauth", paste)], monkeypatch, provider="onedrive")
    assert done._kind == "ok" and seen["values"] == {"token": TOKEN}


def test_mega_flow(monkeypatch):
    done, seen = _flow([("input", "library@example.org"), ("input", "M3ga-pass")], monkeypatch, provider="mega")
    assert done._kind == "ok"
    assert seen["values"] == {"user": "library@example.org", "pass": "M3ga-pass"}
    assert not seen["path"].exists()


def test_s3_flow_wasabi(monkeypatch):
    steps = [("choice", "Wasabi"), ("input", "AKIA123"), ("input", "s3cr3t"),
             ("input", "https://s3.wasabisys.com"), ("input", "koha-backups")]
    done, seen = _flow(steps, monkeypatch, provider="s3")
    assert done._kind == "ok"
    assert seen["values"] == {"provider": "Wasabi", "access_key_id": "AKIA123", "secret_access_key": "s3cr3t",
                              "endpoint": "https://s3.wasabisys.com", "bucket": "koha-backups"}


def test_s3_flow_aws_asks_the_region(monkeypatch):
    steps = [("choice", "AWS"), ("input", "AKIA123"), ("input", "s3cr3t"), ("input", "sa-east-1"),
             ("input", "koha-backups")]
    done, seen = _flow(steps, monkeypatch, provider="s3")
    assert seen["values"]["region"] == "sa-east-1" and "endpoint" not in seen["values"]
