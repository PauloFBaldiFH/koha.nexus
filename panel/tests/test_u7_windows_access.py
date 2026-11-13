"""U7 acceptance, second part (study 17.4/17.5): the access test made from Windows.

- Under WSL the tray opens each configured address from Windows (every 10
  minutes, only reads) and the installer records the answer; the
  "Addresses and access" screen shows it, with where it came from and when.
- Without a record, or under Linux, nothing is claimed for Windows.
- An old record is not shown as working.
- The installer accepts only configured addresses, an HTTP code and an
  http(s) redirect from Windows.
- Every new text has Portuguese.
"""
import re
from pathlib import Path

import pytest

from kei_panel import addresses
from kei_panel.i18n import Translator, install

from test_u5_addresses import outcome, run_screen

ROOT = Path(__file__).resolve().parents[2]
NOW = 1_800_000_000


def wsl(*rows):
    return addresses.parse('tainacan', outcome('platform=wsl', 'configured=site|http://192.168.0.20:8090', *rows))


def test_parse_reads_the_windows_answers_apart():
    a = wsl(f'check=http://192.168.0.20:8090|200||{NOW}', f'wincheck=http://192.168.0.20:8090|000||{NOW - 60}',
            'wincheck=javascript:x|200||1', f'wincheck=http://192.168.0.20:8090x|2000|ftp://a|{NOW}')
    assert a.checks['http://192.168.0.20:8090'].code == '200'
    assert a.win_checks['http://192.168.0.20:8090'] == addresses.Check('000', '', NOW - 60)
    assert 'javascript:x' not in a.win_checks
    assert a.win_checks['http://192.168.0.20:8090x'] == addresses.Check('000', '', NOW)


def test_windows_line():
    line, state = addresses.windows_text(wsl(), NOW)
    assert line.startswith('? not checked from Windows') and state == ''
    line, state = addresses.windows_text(wsl(f'wincheck=http://192.168.0.20:8090|302|http://x/|{NOW - 240}'), NOW)
    assert (line, state) == ('✓ http://192.168.0.20:8090 answered from Windows (HTTP 302, 4 min ago)', 'ok')
    line, state = addresses.windows_text(wsl(f'wincheck=http://192.168.0.20:8090|000||{NOW - 30}'), NOW)
    assert (line, state) == ('✖ http://192.168.0.20:8090: no answer from Windows (just now)', 'bad')
    line, state = addresses.windows_text(wsl(f'wincheck=http://192.168.0.20:8090|503||{NOW - 30}'), NOW)
    assert state == 'bad' and 'HTTP 503' in line
    # A record older than an hour: the tray stopped testing, nothing is claimed.
    line, state = addresses.windows_text(wsl(f'wincheck=http://192.168.0.20:8090|200||{NOW - 7200}'), NOW)
    assert line.startswith('? ') and state == ''


def test_koha_with_one_address_checked():
    a = addresses.parse('koha', outcome('platform=wsl', 'configured=opac|http://192.168.0.20',
                                        'configured=staff|http://192.168.0.20:8080',
                                        f'wincheck=http://192.168.0.20|200||{NOW}'))
    line, state = addresses.windows_text(a, NOW)
    assert line.splitlines() == ['✓ http://192.168.0.20 answered from Windows (HTTP 200, just now)',
                                 '? the other addresses were not checked from Windows yet']
    assert state == ''


def test_the_screen_shows_the_windows_answer(monkeypatch):
    texts, _b, calls = run_screen(monkeypatch, 'tainacan-addresses')
    assert any(t.startswith('✓ http://192.168.0.20:8090 answered from Windows (HTTP 200') for t in texts)
    assert not any(t.startswith('? not checked from Windows') for t in texts)
    assert ('addresses', 'tainacan') in calls
    # DSpace was never tested from Windows: the screen says so.
    texts, _b, _c = run_screen(monkeypatch, 'dspace-addresses')
    assert any(t.startswith('? not checked from Windows') for t in texts)


def test_the_installer_records_only_answers():
    text = (ROOT / 'installer').read_text(encoding='utf-8')
    body = re.search(r'^kei_windows_check\(\) \{\n(.*?)^\}', text, re.S | re.M).group(1)
    assert 'grep -qxF -- "$url"' in body and '^[0-9]{3}$' in body and '^https?://' in body
    assert 'mv -f "$tmp" "$KEI_WINDOWS_CHECKS"' in body
    assert re.search(r'windows-check\)\s+kei_windows_check "\$@"', text)
    assert re.search(r'windows-addresses\)\s+kei_windows_addresses', text)


def test_the_tray_tests_from_windows_and_only_reads():
    core = (ROOT / 'windows' / 'KohaEasy.Core.psm1').read_text(encoding='utf-8-sig')
    body = re.search(r'function Test-KohaWindowsAccess \{(.*?)\n\}', core, re.S).group(1)
    assert "'windows-addresses'" in body and "'windows-check', '-') -InputText" in body
    probe = re.search(r'function Invoke-KohaHttpProbe \{(.*?)\n\}', core, re.S).group(1)
    assert "$req.Method = 'GET'" in probe and '$req.AllowAutoRedirect = $false' in probe
    assert 'Credentials' not in probe and 'GetRequestStream' not in probe
    tray = (ROOT / 'windows' / 'KohaEasy.Tray.ps1').read_text(encoding='utf-8-sig')
    assert 'Test-KohaWindowsAccess' in tray


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_new_texts_have_portuguese(pt):
    for text in ('? ${url}: last answer from Windows ${when}, the tray has not tested it since',
                 '✓ ${url} answered from Windows (HTTP ${code}, ${when})',
                 '✖ ${url}: error from Windows (HTTP ${code}, ${when})',
                 '✖ ${url}: no answer from Windows (${when})',
                 '? the other addresses were not checked from Windows yet'):
        assert pt(text) != text, text
