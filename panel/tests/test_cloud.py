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
    assert "already" in cloud.name_problem("GDrive", ["gdrive"])
    assert "-crypt" in cloud.name_problem("box-crypt")
    assert cloud.base_problem("") == "" and cloud.base_problem("/koha/my library/") == ""
    assert cloud.base_problem("a/../b") and cloud.base_problem("x$y") and cloud.base_problem("a//b")
    assert cloud.folders(" /koha/ ") == ("koha/Backup_SQL_Koha", "koha/Backup_MARC_Koha")
    assert cloud.folders("") == ("Backup_SQL_Koha", "Backup_MARC_Koha")
    assert cloud.base_of("koha/Backup_SQL_Koha") == "koha" and cloud.base_of("Backup_SQL_Koha") == ""
    for ok in ("", "2M", "512k", "1.5M", "08:00,1M 19:00,off", "Mon-08:00,512k Fri-23:59,off", "10M:1M"):
        assert cloud.bwlimit_problem(ok) == "", ok
    for bad in ("fast", "2 M", "08:00 1M", "1M;rm"):
        assert cloud.bwlimit_problem(bad), bad
    assert cloud.keep_problem("30") == "" and cloud.keep_problem("0") == "" and cloud.keep_problem("0", low=1)
    assert cloud.password_problem("short", "short") and cloud.password_problem("long enough!", "other")
    assert cloud.password_problem("long enough!", "long enough!") == ""
    assert cloud.token_problem(TOKEN) == ""
    assert cloud.token_problem('{"access_token":"a"}') and cloud.token_problem("nope")


def test_clean_token_matches_the_installer():
    token = '{"access_token":"a","refresh_token":"b","expiry":"c"}'
    for messy in (token + "\r\n", "  " + token[:20] + "\n" + token[20:], "\ufeff" + token, f"'{token}'",
                  token.replace('"', '\\"'), token.replace('"access_token"', "\u201caccess_token\u201d")):
        assert cloud.clean_token(messy) == token and cloud.token_problem(messy) == ""
    assert cloud.token_problem(token[:30] + "}")


def test_classify_what_was_pasted():
    assert cloud.classify("  " + TOKEN + "\n").kind == "token"
    assert cloud.classify('{"access_token":"a"}').problem
    url = "http://localhost:53682/?code=M.C123&state=xyz"
    assert cloud.classify(url) == cloud.Pasted("redirect", url)
    assert cloud.classify("http://127.0.0.1:53682/?error=access_denied&state=x").kind == "redirect"
    for bad in ("https://login.microsoftonline.com/?code=1&state=2", "http://localhost:53682/?code=1",
                "http://evil.example/?code=1&state=2", "hello"):
        assert cloud.classify(bad).kind == "", bad


def test_save_file_is_private_and_refuses_new_lines():
    path = cloud.save_file("od", "onedrive", "create", {"token": TOKEN, "region": "global"}, crypt="pw pw pw pw")
    try:
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.read_text() == (f"name\tod\ntype\tonedrive\nmode\tcreate\nopt\ttoken\t{TOKEN}\n"
                                    "opt\tregion\tglobal\ncrypt\tpw pw pw pw\n")
    finally:
        path.unlink()
    for bad in ({"pass": "a\tb"}, {"pass": "a\nb"}, {"Bad-Key": "x"}):
        with pytest.raises(ValueError):
            cloud.save_file("m", "mega", "create", bad)


# ----------------------------------------------------------------------
# The catalog of services (rclone config providers)
# ----------------------------------------------------------------------
def test_catalog_popular_first_and_wrappers_left_out():
    catalog = cloud.demo_catalog()
    prefixes = [b.prefix for b in catalog]
    assert prefixes[:4] == ["drive", "onedrive", "dropbox", "mega"]
    assert "crypt" not in prefixes and "alias" not in prefixes
    assert cloud.find_backend(catalog, "drive").oauth and not cloud.find_backend(catalog, "sftp").oauth
    assert cloud.find_backend(catalog, "S3").prefix == "s3"
    assert [b.prefix for b in cloud.search(catalog, "nextcloud")] == ["webdav"]
    assert {b.prefix for b in cloud.search(catalog, "")} == set(prefixes)


def test_s3_rows_follow_the_provider():
    s3 = cloud.find_backend(cloud.demo_catalog(), "s3")
    aws = [o.name for o in cloud.form_options(s3, {"provider": "AWS"})]
    wasabi = [o.name for o in cloud.form_options(s3, {"provider": "Wasabi"})]
    assert aws[0] == "provider" and "storage_class" in aws and "storage_class" not in wasabi
    assert len(aws) == len(set(aws))      # region has one row per provider rule: one is shown
    region = next(o for o in cloud.form_options(s3, {"provider": "AWS"}) if o.name == "region")
    assert any(v == "sa-east-1" for v, _ in region.examples)
    assert not any(o.advanced for o in cloud.form_options(s3, {"provider": "AWS"}))
    assert any(o.advanced for o in cloud.form_options(s3, {"provider": "AWS"}, advanced=True))
    assert cloud.provider_matches("!AWS,Minio", "Wasabi") and not cloud.provider_matches("!AWS,Minio", "AWS")
    assert cloud.provider_matches("", "x") and not cloud.provider_matches("AWS", "")


def test_answers_skip_defaults_and_missing_lists_required():
    sftp = cloud.find_backend(cloud.demo_catalog(), "sftp")
    assert [o.name for o in cloud.missing(sftp, {})] == ["host"]
    values = {"host": " nas.local ", "user": "koha", "port": "22", "pass": "secret"}
    assert cloud.answers(sftp, values) == {"host": "nas.local", "user": "koha", "pass": "secret"}
    assert cloud.missing(sftp, values) == []
    drive = cloud.find_backend(cloud.demo_catalog(), "drive")
    assert cloud.answers(drive, {"token": TOKEN})["token"] == TOKEN
    assert all(o.name not in cloud.SKIP_OPTIONS for o in cloud.form_options(drive, {}, advanced=True))


def test_parsers_of_the_task_answers():
    entries = cloud.parse_entries(["D\tBackup_SQL_Koha\t0\t2026-10-01T10:00:00",
                                   "F\tk_2026.sql.gz\t4821\t2026-11-02T23:01:20", "junk"])
    assert [(e.is_dir, e.name, e.size) for e in entries] == [(True, "Backup_SQL_Koha", 0), (False, "k_2026.sql.gz", 4821)]
    assert entries[1].when == "2026-11-02 23:01"
    remotes = cloud.parse_remotes(["gdrive\tdrive", "box-crypt\tcrypt", ""])
    assert [r.name for r in remotes] == ["gdrive", "box-crypt"] and remotes[1].encrypted
    hist = cloud.parse_history(["sql\t2026-11-01 23:01:12 | WARN: cloud upload failed on gdrive (local copy preserved)",
                                "sql\t2026-11-02 23:01:20 | Cloud OK: gdrive:Backup_SQL_Koha/ (x.sql.gz)",
                                "sql\t2026-11-02 23:01:21 | Cloud cleanup: copies older than 30 days removed"])
    assert [h.ok for h in hist] == [False, True, True]
    assert cloud.last_cloud(hist).when == "2026-11-02 23:01:20"
    assert cloud.is_backup_name("koha_library_2026-11-02_23h00.sql.gz")
    assert cloud.is_backup_name("koha_marc_2026-11-01_0300.tar.gz") and not cloud.is_backup_name("notes.txt")
    assert cloud.needs_bucket("s3") and cloud.needs_bucket("google cloud storage") and not cloud.needs_bucket("drive")


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
# The screens, in demo mode
# ----------------------------------------------------------------------
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


def test_cloud_screen_shows_destination_status_and_files():
    from kei_panel.screens.cloud_backup import CloudBackupScreen

    async def main():
        app = _app()
        async with app.run_test(size=(160, 48)) as pilot:
            app.run_native("backup-cloud")
            screen = await _wait_for(pilot, CloudBackupScreen)
            for _ in range(30):
                await pilot.pause(0.1)
                if screen.remotes and screen.files:
                    break
            def text(sel):
                return str(screen.query_one(sel).render())
            return (text("#cb-w-sql"), text("#cb-s-result"), text("#cb-s-keep"), text("#cb-a-used"),
                    [r.name for r in screen.remotes], [f.name for f in screen.files],
                    screen.query_one("#cb-r-buttons").display, screen.query_one("#cb-history").row_count)
    sql, result, keep, used, remotes, files, official, history = asyncio.run(main())
    assert sql == "gdrive:Backup_SQL_Koha/" and "Sent" in result and "30 days" in keep and "GB" in used
    assert remotes == ["gdrive", "wasabi", "nas"]
    assert files[0] == "koha_library_2026-11-02_23h00.sql.gz"     # newest first
    assert official                                              # Debian's rclone: the button is offered
    assert history == 5


def test_new_connection_form_saves_tests_and_offers_the_destination(monkeypatch):
    from kei_panel.screens.cloud_backup import CloudBackupScreen
    from kei_panel.screens.cloud_remote import RemoteFormScreen
    from kei_panel.screens.dialogs import MessageScreen
    from kei_panel.screens.oauth import OAuthScreen
    seen = {}
    real = cloud.save_file

    def spy(*args, **kwargs):
        seen["args"], seen["kwargs"] = args, kwargs
        seen["path"] = real(*args, **kwargs)
        return seen["path"]
    monkeypatch.setattr(cloud, "save_file", spy)

    async def main():
        app = _app()
        async with app.run_test(size=(160, 48)) as pilot:
            app.run_native("backup-cloud")
            screen = await _wait_for(pilot, CloudBackupScreen)
            await pilot.pause(0.5)
            screen.query_one("#cb-new").press()
            form = await _wait_for(pilot, RemoteFormScreen)
            assert form.backend.prefix == "drive"          # the first service, already open
            form.query_one("#cr-name").value = "gdrive"
            form.query_one("#cr-save").press()
            await pilot.pause(0.2)
            taken = str(form.query_one("#cr-problem").render())
            form.query_one("#cr-name").value = "library"
            form.query_one("#cr-save").press()
            await pilot.pause(0.2)
            unsigned = str(form.query_one("#cr-problem").render())
            form.query_one("#cr-signin-go").press()
            oauth = await _wait_for(pilot, OAuthScreen)
            oauth.query_one("#oauth-paste").value = TOKEN
            oauth.query_one("#ok").press()
            await _wait_for(pilot, RemoteFormScreen)
            signed = str(form.query_one("#cr-signin-state").render())
            form.query_one("#cr-encrypt").value = True
            form.query_one("#cr-pass").value = "a long password"
            form.query_one("#cr-pass2").value = "a long password"
            form.query_one("#cr-save").press()
            done = await _wait_for(pilot, MessageScreen, tries=100)     # the upload test
            return taken, unsigned, signed, done._kind, done._title
    taken, unsigned, signed, kind, title = asyncio.run(main())
    assert "already" in taken and "Sign in first" in unsigned and "Signed in" in signed
    assert kind == "ok" and "Test" in title
    name, prefix, mode, values = seen["args"][:4]
    assert (name, prefix, mode) == ("library", "drive", "create")
    assert json.loads(values["token"])["access_token"] == "a" and seen["args"][4] == "a long password"
    assert not seen["path"].exists()


def test_schedule_tab_builds_cron_and_settings():
    from kei_panel import cron
    from kei_panel.screens.cloud_backup import CUSTOM, CloudBackupScreen

    async def main():
        app = _app()
        async with app.run_test(size=(160, 48)) as pilot:
            app.run_native("backup-cloud")
            screen = await _wait_for(pilot, CloudBackupScreen)
            for _ in range(20):
                await pilot.pause(0.1)
                if screen.remotes:
                    break
            screen.query_one("#cb-tabs").active = "cb-tab-plan"
            await pilot.pause(0.3)
            screen.query_one("#cb-sql-time").value = "21:30"
            screen.query_one("#cb-marc-freq").value = "monthly"
            await pilot.pause(0.2)
            screen.query_one("#cb-marc-day").value = 5
            screen.query_one("#cb-keep-cloud").value = CUSTOM
            screen.query_one("#cb-keep-cloud-n").value = "45"
            screen.query_one("#cb-remote2").value = "wasabi"
            screen.query_one("#cb-bw").value = "08:00,1M 19:00,off"
            good = screen.plan()
            screen.query_one("#cb-bw").value = "fast"
            bad = screen.plan()
            return good, bad
    (values, text, problem), bad = asyncio.run(main())
    assert problem == "" and bad[2]
    assert values == {"KEEP_DAYS": "7", "CLOUD_KEEP_DAYS": "45", "CLOUD_MARC": "yes", "RCLONE_REMOTE2": "wasabi",
                      "RCLONE_BWLIMIT": "08:00,1M 19:00,off"}
    cf = cron.parse(text, "library")
    assert cf.job("backup_sql").schedule() == "30 21 * * *"
    assert cf.job("backup_marc").schedule() == "0 3 5 * *"
    assert cron.file_problem(text) == ""
