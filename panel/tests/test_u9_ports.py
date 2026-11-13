"""U9 acceptance (study 16.2): the port of a new site, shown, editable and
checked.

- One field for every installer: the default port, its state as it is
  typed (free, this system's own, in use by whom), a suggestion with "Use",
  and the address that will be used. Continue only for a free port.
- Who uses a port is said in words; a system by its visible name (U6).
- Tainacan (local network) proposes the address the installer would use and
  asks its port; DSpace asks a port when it answers on this server's address
  (or localhost under WSL) instead of a whole address.
- The installer checks the port (port-check, only reads) and the Tainacan
  plan refuses a port someone else uses (tests/ports.bats).
- Every new text has Portuguese.
"""
import asyncio
import re
from pathlib import Path

import pytest

from kei_panel.bridge import TaskOutcome
from kei_panel.i18n import Translator, install
from kei_panel.screens import port_field
from kei_panel.screens.port_field import PortScreen, PortState

ROOT = Path(__file__).resolve().parents[2]


def outcome(**results):
    out = TaskOutcome()
    for k, v in results.items():
        out.feed(f'@@result {k}={v}')
    return out


def test_valid_and_parse():
    assert [port_field.valid(v) for v in ('8090', ' 80 ', '0', '65536', 'x', '', '123456')] == [8090, 80, 0, 0, 0, 0, 0]
    st = port_field.parse(8090, outcome(state='used', owner='other:nginx', suggest='8091', lan='192.168.0.10'))
    assert st == PortState(8090, 'used', 'other:nginx', 8091, '192.168.0.10')
    assert port_field.parse(8090, outcome(state='great', lan='x;rm')).state == '' and \
        port_field.parse(8090, outcome(state='free', lan='x;rm')).lan == ''
    assert port_field.parse(8090, outcome(state='free', owner='koha')).owner == ''


def test_owner_and_state_in_words():
    assert port_field.owner_text('tainacan', {'tainacan': 'Museu Municipal'}) == 'in use by Museu Municipal · Tainacan'
    assert port_field.owner_text('koha', {}) == 'in use by Koha'
    assert port_field.owner_text('other:nginx') == 'in use by another program (nginx)'
    assert port_field.owner_text('other:') == 'in use by another program'
    assert port_field.owner_text('reserved').startswith('reserved')
    assert port_field.status_text(PortState(8100, 'free')) == ('✓ free', 'ok')
    assert port_field.status_text(PortState(8090, 'used', 'other:nginx', 8091)) == \
        ('✗ in use by another program (nginx) · suggestion 8091', 'bad')
    assert port_field.status_text(PortState(0))[1] == 'bad'
    assert port_field.status_text(PortState(8090))[0] == 'Checking…'
    assert port_field.address(PortState(8091, 'free', lan='192.168.0.10')) == 'http://192.168.0.10:8091'
    assert port_field.address(PortState(8100, 'free'), host='localhost') == 'http://localhost:8100'
    assert port_field.address(PortState(8100, 'free')) == ''


def test_the_field_suggests_and_continues_only_when_free(monkeypatch):
    for name in ('KOHA', 'TAINACAN', 'DSPACE'):
        monkeypatch.setenv('KEI_PANEL_DEMO_' + name, '1')
    from textual.widgets import Button, Input, Label

    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang='en', plain=False, demo=True))
        calls, got = [], []
        real = app.bridge.task

        async def task(name, *args, **kwargs):
            calls.append((name, *args))
            return await real(name, *args, **kwargs)
        app.bridge.task = task
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(.3)
            app.push_screen(PortScreen('Install Tainacan', '', 'tainacan', 8090), got.append)

            async def until(done):
                for _ in range(100):
                    if done():
                        return
                    await pilot.pause(.05)
            screen = app.screen
            await until(lambda: screen.state.state)
            first = (str(screen.query_one('#port-state', Label).render()), screen.query_one('#ok', Button).disabled,
                     bool(screen.query_one('#port-use').display), str(screen.query_one('#port-address', Label).render()))
            screen.query_one('#port-use', Button).press()
            await until(lambda: screen.state.port == 8091 and screen.state.state)
            second = (str(screen.query_one('#port-state', Label).render()), screen.query_one('#ok', Button).disabled)
            screen.query_one('#port', Input).value = '0'
            await pilot.pause(.2)
            bad = screen.query_one('#ok', Button).disabled
            screen.query_one('#port', Input).value = '8100'
            await until(lambda: screen.state.port == 8100 and screen.state.state)
            screen.query_one('#ok', Button).press()
            await pilot.pause(.2)
            return first, second, bad, got, calls

    first, second, bad, got, calls = asyncio.run(main())
    assert first == ('✗ in use by another program (nginx) · suggestion 8091', True, True,
                     'Address: http://192.168.0.10:8090')
    assert second == ('✓ free', False)
    assert bad
    assert got == [PortState(8100, 'free', '', 0, '192.168.0.10')]
    # Only reads: the field's checks (the dashboard reads in the background).
    assert ('port-check', '8091', 'tainacan') in calls and ('port-check', '8100', 'tainacan') in calls
    assert not [c for c in calls if c[0] != 'port-check' and not c[0].endswith('status')]


def test_dspace_asks_a_port_instead_of_an_address(monkeypatch):
    from test_dspace_panel import App, mock_calls
    from types import SimpleNamespace

    from kei_panel.routines import dspace
    from kei_panel.screens.dialogs import ChoiceScreen
    calls = mock_calls(monkeypatch, {'availability': {'available': True},
                                     'dspace-prerequisites': {'apache_missing': False},
                                     'status': {'status': 'absent'}, 'plan': {'url': 'http://192.168.0.10:8101'}})
    chosen = PortState(8101, 'free', lan='192.168.0.10')
    app = App([True, 'port', chosen, False])
    app.check_platforms = lambda: None

    async def status():
        return {'docker': {'installed': True}}
    app.bridge = SimpleNamespace(status=status)
    asyncio.run(dspace.install(app))
    asked = [s for s in app.screens if isinstance(s, (ChoiceScreen, PortScreen))]
    assert isinstance(asked[-1], PortScreen) and asked[-1]._system == 'dspace' and asked[-1]._first == 8100
    plans = [args for name, args, kw in calls if name == 'dspace-panel' and args[0] == 'plan']
    assert plans and plans[0][1:3] == ('--url', 'http://192.168.0.10:8101')


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_new_texts_have_portuguese(pt):
    source = (ROOT / 'panel' / 'kei_panel' / 'screens' / 'port_field.py').read_text(encoding='utf-8')
    texts = set(re.findall(r'(?<![\w.])t\("([^"]+)"', source)) | {port_field.REACH}
    texts |= {"The collection answers on this server's address, on a port of its own. The suggested port is free; "
              "you can type another.",
              'DSpace answers on a port of its own. Keep the suggested port or type another.',
              'How will people open DSpace?', "This server's address, on a port of its own",
              'A name (domain) already pointing to this server'}
    assert sorted(s for s in texts if pt(s) == s) == []
