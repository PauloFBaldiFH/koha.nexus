"""U5 acceptance, third part (study 17.4): Addresses and access.

- Each system's "Addresses and access" separates the configured address
  (the only one with "use this", Open and Copy), the other names of the
  server with the effect to expect, and the internet.
- Nothing is called working without a test; each test says where it was
  made from. Under WSL the screen says it was not checked from Windows.
- Opening the screen only reads; "Test access" only reads too.
- Changing the address is the system's own routine; the cards stay.
- Every new text has Portuguese.
"""
import asyncio
from pathlib import Path

import pytest

from kei_panel import addresses
from kei_panel.bridge import TaskOutcome
from kei_panel.i18n import Translator, install
from kei_panel.menus import section

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'installer'


def outcome(*lines):
    out = TaskOutcome()
    for line in lines:
        out.feed('@@result ' + line)
    return out


def test_the_screens_and_their_cards():
    for sid, cards in (('koha-addresses', {'cloudflare', 'ssl', 'staff-firewall'}),
                       ('tainacan-addresses', {'tainacan-address'}),
                       ('dspace-addresses', {'dspace-address', 'dspace-repair-web'})):
        sec = section(sid)
        assert sec.view == 'addresses' and {e.action for e in sec.entries} == cards


def test_parse_keeps_only_web_addresses():
    a = addresses.parse('tainacan', outcome(
        'platform=wsl', 'configured=site|http://192.168.0.20:8090', 'configured=site|javascript:alert(1)',
        'alternative=site|http://localhost:8090', 'alternative=bad|http://x', 'unset=site',
        'check=http://localhost:8090|302|http://192.168.0.20:8090/|1790000000', 'check=nonsense'))
    assert a.host_platform == 'wsl'
    assert a.configured == [('site', 'http://192.168.0.20:8090')]
    assert a.alternatives == [('site', 'http://localhost:8090')]
    assert a.unset == []
    assert a.checks['http://localhost:8090'].redirect == 'http://192.168.0.20:8090/'


def test_nothing_is_working_without_a_test():
    line, state = addresses.check_text(None)
    assert line.startswith('?') and state == ''
    assert addresses.check_text(addresses.Check('200', '', 1000), now=1030)[1] == 'ok'
    assert addresses.check_text(addresses.Check('500', '', 1000), now=1030)[1] == 'bad'
    assert addresses.check_text(addresses.Check('000', '', 1000), now=1030)[0].startswith('✖ no answer')
    conf = [('site', 'http://192.168.1.20:8100')]
    # Before a test: the effect to expect, by system.
    assert addresses.alternative_text('dspace', 'http://localhost:8100', conf, None).startswith('May fail')
    assert 'login works only there' in addresses.alternative_text('tainacan', 'http://localhost:8090', conf, None)
    redirect = addresses.Check('302', 'http://192.168.1.20:8100/', 1)
    assert addresses.alternative_text('dspace', 'http://localhost:8100', conf, redirect) == \
        'Leads to the configured address'
    assert addresses.alternative_text('dspace', 'x', conf, addresses.Check('500')) == 'Error (HTTP 500)'


def test_internet():
    a = addresses.Addresses('tainacan', configured=[('site', 'http://192.168.0.20:8090')])
    assert addresses.internet_text('tainacan', a, []) == 'Not published'
    a.configured = [('site', 'https://acervo.example.org')]
    assert addresses.internet_text('tainacan', a, []) == 'https://acervo.example.org'
    assert addresses.is_local('http://localhost:8100') and addresses.is_local('http://10.0.0.5')
    assert not addresses.is_local('https://biblioteca.koha.nexus')


def run_screen(monkeypatch, sid, test=False):
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA', '1')
    monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN', '1')
    monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE', '1')
    from textual.widgets import Button, Label

    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang='en', plain=False, demo=True))
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.5)
            calls = []
            real = app.bridge.task

            async def task(name, *args, **kwargs):
                calls.append((name, *args))
                return await real(name, *args, **kwargs)
            app.bridge.task = task
            app.screen.action_show(sid, from_sidebar=True)
            await pilot.pause(2.5)
            view = app.screen.query_one(f'#view-{sid}')
            if test:
                view.query_one('#addr-test', Button).press()
                await pilot.pause(3)
            texts = [str(lb.render()) for lb in view.query(Label) if lb.display]
            buttons = {b.id for b in view.query(Button) if b.id}
            return texts, buttons, calls

    return asyncio.run(main())


def test_dspace_screen_before_and_after_the_test(monkeypatch):
    texts, buttons, calls = run_screen(monkeypatch, 'dspace-addresses')
    assert 'http://192.168.1.20:8100' in texts
    assert '? not checked yet: press Test access' in texts
    assert not any(t.startswith('✓') for t in texts)
    assert any(t.startswith('? not checked from Windows') for t in texts)
    assert 'http://localhost:8100   May fail: DSpace answers fully only at the configured address' in texts
    assert {'addr-change', 'addr-test'} <= buttons and 'addr-publish' not in buttons
    assert set(calls) <= {('addresses', 'dspace'), ('platform-backup-status', 'tainacan')}, calls
    texts, _b, calls = run_screen(monkeypatch, 'dspace-addresses', test=True)
    assert any(t.startswith('✓ answered from this server (HTTP 200') for t in texts)
    assert 'http://localhost:8100   Error (HTTP 500)' in texts
    assert ('addresses', 'dspace', 'test') in calls
    assert all(c[0] in ('addresses', 'platform-backup-status') for c in calls)


def test_koha_screen_publishes_through_the_tunnel(monkeypatch):
    texts, buttons, _calls = run_screen(monkeypatch, 'koha-addresses')
    assert 'http://192.168.0.20' in texts and 'http://192.168.0.20:8080' in texts
    assert 'https://biblioteca.koha.nexus' in texts
    assert 'addr-publish' in buttons and 'addr-change' not in buttons


def test_the_installer_task_only_reads():
    import re
    text = INSTALLER.read_text(encoding='utf-8')
    body = re.search(r'^kei_addresses\(\) \{\n(.*?)^\}', text, re.S | re.M).group(1)
    for word in ('run_sql "INSERT', 'UPDATE ', '_kei_tn_set', 'kei_proxy', 'systemctl', '-X ', '--data'):
        assert word not in body, word
    assert '--max-time' in body


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_new_texts_have_portuguese(pt):
    texts = [v for k, v in addresses.KIND_NAMES.items() if k != 'opac'] + list(addresses.EXPECTED.values())
    texts += ['just now', '${n} min ago', '${n} h ago', '? not checked yet: press Test access',
              '✓ answered from this server (HTTP ${code}, ${when})', '✖ error from this server (HTTP ${code}, ${when})',
              '✖ no answer from this server (${when})', 'Leads to the configured address',
              'No answer from this server', 'Error (HTTP ${code})', 'Not published',
              'Configured address (use this)', 'Other names of this server (may redirect or fail at login)',
              'On the internet', 'Publish…', 'Change or publish the address…', 'Test access',
              'The addresses could not be read. Update this panel and try again.', 'configured', 'Not set',
              '${pref} is empty: Koha builds its links from the address the browser used.',
              '? not checked from Windows: a test from inside WSL does not prove access from Windows or from the '
              'network.', 'None found.']
    same = {'Site'}
    assert sorted(s for s in texts if pt(s) == s and s not in same) == []
