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
