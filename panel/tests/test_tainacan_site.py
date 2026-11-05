"""Tainacan's public home page, its address and starting it again
(installer: kei_tainacan_site_*, kei_lan_address, kei_tainacan_start).

The real WordPress and Tainacan run in tests/e2e (CI): here, what can be
checked without them: the address never comes from a VPN, the tasks the
panel calls exist, the page script removes nothing by its title.
"""

import re
import shutil
import subprocess

import pytest
from conftest import INSTALLER

TEXT = INSTALLER.read_text(encoding="utf-8")


def bash(body: str) -> str:
    """Runs BODY with the installer's functions (sourced, nothing runs)."""
    script = f'source "{INSTALLER}" >/dev/null 2>&1\n{body}\n'
    return subprocess.run(["bash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=60).stdout


FAKE_IP = '''
ip() {
    case "$*" in
        "-4 route get 1.1.1.1") echo "1.1.1.1 via $GW dev $DEV src $SRC uid 0" ;;
        "-4 -o addr show scope global"|"-4 -o addr show")
            echo "2: eth0    inet 192.168.0.20/24 brd 192.168.0.255 scope global eth0"
            echo "3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0"
            echo "5: tun0    inet 10.8.0.3/24 scope global tun0" ;;
    esac
}
'''


def test_the_address_skips_a_default_route_through_a_vpn():
    out = bash(FAKE_IP + 'GW=10.8.0.1 DEV=tun0 SRC=10.8.0.3 kei_lan_address')
    assert out.strip() == "192.168.0.20 eth0"


def test_the_address_is_the_route_to_the_internet_when_it_is_a_real_interface():
    out = bash(FAKE_IP + 'GW=192.168.0.1 DEV=eth0 SRC=192.168.0.20 kei_lan_address')
    assert out.strip() == "192.168.0.20 eth0"


def test_the_plan_says_where_an_address_comes_from():
    vpn = bash(FAKE_IP + 'GW=10.8.0.1 DEV=tun0 SRC=10.8.0.3 _kei_tn_address_origin http://10.8.0.3:8090')
    assert "from\tInterface tun0: a VPN, tunnel or virtual network" in vpn
    lan = bash(FAKE_IP + 'GW=10.8.0.1 DEV=tun0 SRC=10.8.0.3 _kei_tn_address_origin http://192.168.0.20:8090')
    assert "from\tInterface eth0 (local network)." in lan
    assert "route\tThe route to the internet goes through tun0" in lan
    # A name: nothing to say about interfaces.
    assert bash(FAKE_IP + 'GW=x DEV=eth0 SRC=1 _kei_tn_address_origin https://acervo.example.org').strip() == ""


def test_an_installation_keeps_its_address():
    # Only a new installation gets the default address; the plan and the
    # install take the one in the state file first.
    plan = re.search(r"^kei_tainacan_plan\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    assert plan.index('url=$(_kei_tn_get url)') < plan.index("url=$(kei_tainacan_default_url)")


def test_the_panel_tasks_exist():
    from kei_panel.bridge import installer_tasks
    assert {"tainacan-site", "tainacan-start"} <= installer_tasks(INSTALLER)
    body = re.search(r"^        tainacan-site\)(.*?);;\n        tainacan-start", TEXT, re.S | re.M).group(1)
    for sub in ("plan)", "status)", "apply)", "undo)"):
        assert sub in body


def site_php() -> str:
    m = re.search(r"^_kei_tn_site_php\(\) \{\n    cat <<'PHP'\n(.*?)^PHP$", TEXT, re.S | re.M)
    return m.group(1)


def test_the_home_page_script_removes_nothing_by_its_title():
    php = site_php()
    assert "wp_delete_post" not in php                       # the trash only, undo puts it back
    for title in ("Hello world", "Olá, mundo", "Sample Page", "Página de exemplo"):
        assert title not in php
    # The sample post and page are taken by the ids kept at install time,
    # never edited, and only on a new installation.
    assert "$kind === 'fresh'" in php and "kn_untouched($p)" in php
    assert "post_list" not in php
    assert "site_samples" in TEXT and "--post_type=post,page --post_status=publish --format=ids" in TEXT


def test_only_supported_settings_and_blocks_are_used():
    php = site_php()
    # Tainacan's own settings (Settings, Theme default templates) and its
    # [tainacan-search] shortcode; WordPress's core blocks; no theme change.
    for opt in ("override_collection_items_archive_template", "override_taxonomy_term_items_archive_template",
                "override_repository_items_archive_template"):
        assert f"tainacan_option_{opt}" in php
    assert "[tainacan-search]" in php
    assert "switch_theme" not in php and "theme mod" not in php.lower()


@pytest.mark.skipif(not shutil.which("php"), reason="php is not installed")
def test_the_home_page_script_is_valid_php(tmp_path):
    f = tmp_path / "kn-site.php"
    f.write_text(site_php(), encoding="utf-8")
    proc = subprocess.run(["php", "-l", str(f)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.returncode == 0, proc.stdout


def test_an_existing_installation_needs_a_yes():
    apply = re.search(r"^kei_tainacan_site_apply\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    assert "confirm|fresh) ;;" in apply and "the plan needs a yes (confirm)" in apply
    undo = re.search(r"^kei_tainacan_site_undo\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    assert '[ "${1:-}" = confirm ]' in undo
    start = re.search(r"^kei_tainacan_start\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    assert '[ "${1:-}" = confirm ]' in start and "restore" not in start


def test_the_install_prepares_the_home_page_of_a_new_wordpress_only():
    install = re.search(r"^kei_tainacan_install\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    # site_fresh is set only right after WordPress's own install.
    assert install.index("core install") < install.index("site_fresh 1") < install.index("kei_tainacan_site_apply fresh")
    plan = re.search(r"^kei_tainacan_plan\(\) \{(.*?)^\}", TEXT, re.S | re.M).group(1)
    assert "printf 'site\\t%s\\n'" in plan
    assert "Platforms, Install Docker" not in TEXT
