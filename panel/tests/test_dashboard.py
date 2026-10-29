from kei_panel.views.dashboard import COMPONENTS, OVERALL, unit_state


def test_overall_ok_is_green():
    # --status-json says "ok" (kei_overall_state), never "running".
    assert OVERALL["ok"] == ("Running", "ok")
    assert OVERALL["degraded"][1] == "warn" and OVERALL["stopped"][1] == "bad"


def test_components_match_the_windows_window():
    assert [u for u, _ in COMPONENTS] == ["mariadb", "apache2", "rabbitmq-server", "memcached", "koha-common"]
    assert unit_state("active") == ("Running", "ok")
    assert unit_state("failed")[1] == unit_state("inactive")[1] == "bad"
    assert unit_state(None)[1] == "warn"


from kei_panel.opener import opener_command
from kei_panel.views.dashboard import access_links

_BASE = {"platform": "linux", "services": {"cloudflared": "active"},
         "access": {"opac_port": 80, "staff_port": 8080, "lan_ip": "192.168.0.20", "lan_reachable": True,
                    "tunnel_mode": "own", "public_opac": "catalogo.example.org", "public_staff": "staff.example.org"}}


def test_addresses_from_status_json():
    links = access_links(_BASE)
    assert links["local", "opac"][0] == "http://localhost"
    assert links["local", "staff"][0] == "http://localhost:8080"
    assert links["lan", "staff"][0] == "http://192.168.0.20:8080"
    assert links["public", "opac"][:1] == ("https://catalogo.example.org",) and links["public", "opac"][2] == "ok"


def test_addresses_that_cannot_be_used_have_no_link():
    s = dict(_BASE, platform="wsl2", services={"cloudflared": "inactive"},
             access=dict(_BASE["access"], lan_reachable=False, lan_ip="", tunnel_mode="free", public_staff=""))
    links = access_links(s)
    assert links["lan", "opac"][0] == "" and "WSL" in links["lan", "opac"][1]
    assert links["public", "opac"][2] == "bad"           # tunnel down
    assert links["public", "staff"][0] == ""             # remote staff access off
    # An installer older than the panel: no "access" block, still no crash.
    assert access_links({"platform": "linux"})["public", "opac"][0] == ""


def test_browser_is_never_opened_over_ssh_or_without_a_desktop():
    which = {"wslview": None, "explorer.exe": "/mnt/c/Windows/explorer.exe", "xdg-open": "/usr/bin/xdg-open",
             "runuser": "/usr/sbin/runuser"}.get
    url = "http://localhost"
    assert opener_command(url, wsl=True, ssh=True, which=which, environ={}) is None
    assert opener_command(url, wsl=True, ssh=False, which=which, environ={}) == ["/mnt/c/Windows/explorer.exe", url]
    assert opener_command(url, wsl=False, ssh=False, which=which, environ={}) is None
    cmd = opener_command(url, wsl=False, ssh=False, which=which, environ={"DISPLAY": ":0", "SUDO_USER": "ana"})
    assert cmd[-2:] == ["xdg-open", url]


def test_cloud_server_on_a_private_address_shows_its_public_ip():
    s = dict(_BASE, services={"cloudflared": "inactive"},
             access=dict(_BASE["access"], lan_ip="10.0.0.60", tunnel_mode="", public_opac="", public_staff="",
                         public_ip="203.0.113.7"))
    links = access_links(s)
    assert links["lan", "opac"][0] == "http://10.0.0.60"
    assert links["public", "opac"][0] == "http://203.0.113.7"
    assert links["public", "staff"][0] == "http://203.0.113.7:8080"
    assert "Cloudflare Tunnel" in links["public", "staff"][1]


def test_last_backup_card_shows_when_how_long_ago_and_which_file():
    import time as _time

    from kei_panel.views.dashboard import backup_card
    now = 1_791_640_000
    b = {"last_file": "koha_library_2026-10-09_23h00.sql.gz", "last_epoch": now - 3 * 3600, "last_result": "ok"}
    value, note, state = backup_card(b, now=now)
    assert value == _time.strftime("%Y-%m-%d %H:%M", _time.localtime(now - 3 * 3600))
    assert note == "3 h ago · koha_library_2026-10-09_23h00.sql.gz" and state == "ok"
    # No nightly run yet (a manual or safety copy is the newest): still green.
    assert backup_card(dict(b, last_result="none"), now=now)[2] == "ok"
    # Old, or the last nightly run failed: amber.
    assert backup_card(dict(b, last_epoch=now - 3 * 86400), now=now)[2] == "warn"
    assert backup_card(dict(b, last_result="failed"), now=now)[2] == "warn"
    # No backup at all, or an installer that sent nothing.
    for empty in ({"last_epoch": 0, "last_file": ""}, {}, None, {"last_epoch": "x"}):
        assert backup_card(empty, now=now) == ("None yet", "No backup on this server yet", "warn")


def test_backup_over_a_day_old_warns():
    from kei_panel.views.dashboard import backup_card
    now = 1_791_640_000
    b = {"last_file": "koha_library.sql.xz", "last_epoch": now - 22 * 3600, "last_result": "ok"}
    assert backup_card(b, now=now)[2] == "ok"
    value, note, state = backup_card(dict(b, last_epoch=now - 25 * 3600), now=now)
    assert state == "warn" and note == "No backup for 1 d · koha_library.sql.xz"


# ---- Server health ---------------------------------------------------
from kei_panel import health
from kei_panel.views import dashboard as dash


def test_cpu_busy_from_two_proc_stat_reads():
    a = "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 1 1 1 1\n"
    b = "cpu  150 0 150 900 0 0 0 0 0 0\n"
    assert round(health.cpu_busy(a, b)) == 50
    assert health.cpu_busy(b, a) is None
    assert dash.cpu_card({"cores": 4, "busy": 50.0, "load": 1.5}) == ("50% in use", "4 cores · load 1.50", "ok")
    assert dash.cpu_card({"cores": 4, "busy": 95.0, "load": 6})[2] == "warn"
    assert dash.cpu_card(None)[0] == "-"


def test_memory_card_shows_used_and_total():
    value, note, state = dash.memory_card({"total": 16 * 1024**3, "available": 4 * 1024**3})
    assert value == "12.0 GB / 16.0 GB" and note == "75% used · 4.0 GB free" and state == "ok"
    assert dash.memory_card({"total": 100, "available": 3})[2] == "bad"
    assert dash.memory_card({})[0] == "-"


def test_backup_folder_warns_when_the_next_backups_do_not_fit():
    disk = {"total": 100 * 1024**3, "free": 50 * 1024**3}
    ok = dash.backup_dir_card({"bytes": 3 * 1024**3, "files": 12}, disk, last_size=200 * 1024**2)
    assert ok == ("3.0 GB", "12 files", "ok")
    small = dict(disk, free=300 * 1024**2)
    assert dash.backup_dir_card({"bytes": 1, "files": 1}, small, last_size=200 * 1024**2)[2] == "bad"
    assert dash.backup_dir_card(None, disk)[0] == "-"


def test_error_lines_from_apache_and_koha_logs(tmp_path):
    from datetime import datetime
    now = datetime(2026, 10, 29, 20, 0, 0).timestamp()
    apache = tmp_path / "error.log"
    apache.write_text(
        "[Thu Oct 29 19:00:00.123456 2026] [cgi:error] [pid 7] AH01215: DBI connect failed: /usr/share/koha\n"
        "[Thu Oct 29 19:01:00.123456 2026] [mpm_prefork:notice] [pid 1] resuming normal operations\n"
        "[Thu Oct 29 19:02:00.123456 2026] [cgi:error] [pid 7] AH01215: Use of uninitialized value $x\n"
        "[Mon Oct 26 10:00:00.000000 2026] [core:error] [pid 3] too old\n"
        "a line with no time\n")
    plack = tmp_path / "plack-error.log"
    plack.write_text("[2026/10/29 18:30:00] [ERROR] Search timed out\n[2026/10/29 18:31:00] [WARN] slow\n")
    found = health.count_errors([str(apache), str(plack), str(tmp_path / "missing.log")], now=now)
    assert found["count"] == 2 and "DBI connect failed" in found["last"]
    assert health.short_error(found["last"]).startswith("DBI connect failed")
    assert health.count_errors([str(tmp_path / "missing.log")], now=now) is None
    a = health.count_errors([str(apache)], now=now)
    k = health.count_errors([str(plack)], now=now)
    value, note, state = dash.errors_card(a, k, now=now)
    assert value == "2 errors" and note.startswith("Apache 1 · Koha 1 · 1 h ago: DBI connect") and state == "warn"
    assert dash.errors_card({"count": 0}, {"count": 0})[:1] == ("No errors",)


def test_tunnel_and_sru_cards():
    s = {"services": {"cloudflared": "active"}, "access": {"public_opac": "biblioteca.koha.nexus"}}
    assert dash.tunnel_card({"code": 200, "ms": 300}, s)[2] == "ok"
    assert dash.tunnel_card({"code": 530, "ms": 300}, s) == ("Does not answer", "biblioteca.koha.nexus · HTTP 530",
                                                             "bad")
    stopped = dict(s, services={"cloudflared": "inactive"})
    assert "cloudflared is stopped" in dash.tunnel_card({"code": 0, "ms": 8000}, stopped)[1]
    assert dash.tunnel_card(None, {"access": {}})[0] == "Not used"
    assert dash.sru_card({"code": 200, "ms": 420}) == ("Answers (HTTP 200)", "420 ms", "ok")
    assert dash.sru_card({"code": 0, "ms": 8000})[2] == "warn"


def test_z3950_card_reads_the_last_test(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))
    assert health.read_z3950() == {"ok": 0, "tested": 0, "when": 0}
    (tmp_path / "z3950-history.json").write_text(json.dumps({
        "_rules": 2, "_tested": 1_791_600_000,
        "a:210/x": {"status": "ok", "when": 1}, "b:210/y": {"status": "tcp", "when": 1},
        "c:210/z": {"status": "ok", "when": 1}, "d:210/w": {"hidden": True}}))
    z = health.read_z3950()
    assert z == {"ok": 2, "tested": 3, "when": 1_791_600_000}
    assert dash.z3950_card(z, now=1_791_600_000 + 7200) == ("2 working", "of 3 tested · 2 h ago", "ok")
    assert dash.z3950_card({"ok": 0, "tested": 0, "when": 0})[2] == "warn"


def test_updates_card():
    text = 'shield\nPANEL_VERSION=" 1.5.126"\nUPDATE_URL="https://x"\n'
    assert health.parse_panel_version(text) == "1.5.126"
    pol = "koha-common:\n  Installed: 24.11.05-1\n  Candidate: 24.11.06-1\n  Version table:\n"
    assert health.parse_apt_policy(pol) == ("24.11.05-1", "24.11.06-1")
    assert health.parse_apt_policy("koha-common:\n  Installed: (none)\n  Candidate: 1\n") is None
    value, note, state = dash.updates_card("1.5.125", "1.5.126", ("24.11.05-1", "24.11.05-1"))
    assert (value, state) == ("Update available", "warn") and note == "Panel 1.5.125 → 1.5.126 · Koha 24.11.05-1"
    assert dash.updates_card("1.5.126", "1.5.126", ("24.11.05-1", "24.11.06-1"))[1].endswith("24.11.06-1")
    assert dash.updates_card("1.5.126", "1.5.10", None) == ("Up to date", "Panel 1.5.126", "ok")
    assert dash.updates_card("1.5.126", None, None)[0] == "-"


def test_update_url_follows_the_installer(tmp_path):
    f = tmp_path / "config.sh"
    f.write_text('PANEL_VERSION=" 1.0"\nUPDATE_URL="https://example.org/fork/installer"\n')
    assert health.update_url(f) == "https://example.org/fork/installer"
    assert health.update_url(None) == health.UPDATE_URL
