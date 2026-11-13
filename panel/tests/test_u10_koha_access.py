"""U10 acceptance (study 16.1): Koha with one port or two, chosen in
Addresses and access.

- Two ports stays the default and needs nothing; one port asks the
  institution's domain (checked before anything runs).
- The plan is shown before any change: catalog and staff addresses, the
  staff on this server (8080 kept), who may open the staff by name, and
  whether each name already points here (a warning, never a block).
- Nothing changes without the Yes: apply runs only with confirm; choosing
  what is already set changes nothing.
- The installer side (kei_koha_access) runs in tests/koha_access.bats and,
  with a real Apache, in tests/proxy_system.bats.
- Every new text has Portuguese.
"""
import asyncio
import re
from pathlib import Path

import pytest

from kei_panel.bridge import TaskOutcome
from kei_panel.i18n import Translator, install
from kei_panel.routines import koha_access as ka
from kei_panel.tasks import TaskResult

ROOT = Path(__file__).resolve().parents[2]

TWO = ['@@result mode=two', '@@result opac=http://192.168.0.20', '@@result staff=http://192.168.0.20:8080']
ONE = ['@@result mode=one', '@@result domain=biblioteca.org.br', '@@result opac=http://biblioteca.org.br',
       '@@result staff=http://admin.biblioteca.org.br', '@@result recovery=http://127.0.0.1:8080',
       '@@result staff_net=local', '@@result points=biblioteca.org.br|here',
       '@@result points=admin.biblioteca.org.br|none']


def outcome(lines, rc=0):
    out = TaskOutcome(rc=rc)
    for line in lines:
        out.feed(line)
    return out


class Bridge:
    def __init__(self, status):
        self.status_lines, self.calls = status, []

    async def task(self, name, *args, **kwargs):
        self.calls.append((name, *args))
        if args[0] == 'status':
            return outcome(self.status_lines)
        return outcome(ONE if args[1] == 'one' else TWO)


class App:
    def __init__(self, answers, status=TWO):
        self.answers, self.screens = list(answers), []
        self.bridge = Bridge(status)

    async def push_screen_wait(self, screen):
        self.screens.append(screen)
        return self.answers.pop(0) if self.answers else None


@pytest.fixture
def ran(monkeypatch):
    import kei_panel.routines.common as common
    calls = []

    async def run_task(app, title, name, *args, **kwargs):
        calls.append((name, *args))
        return TaskResult(ok=True, value=outcome(['@@msg ok OK\tDone.']))

    async def show_done(app, title, result, default=''):
        calls.append(('done',))
    monkeypatch.setattr(common, 'run_task', run_task)
    monkeypatch.setattr(common, 'show_done', show_done)
    return calls


def test_domain_check():
    assert ka.domain_error('biblioteca.org.br') == '' and ka.domain_error(' Biblioteca.ORG.br ') == ''
    for bad in ('', 'biblioteca', 'http://biblioteca.org.br', '192.168.0.20', 'admin.biblioteca.org.br',
                'biblioteca.org.br/opac', 'a b.org', 'x' * 64 + '.org'):
        assert ka.domain_error(bad), bad


def test_one_port_shows_the_plan_then_applies_with_confirm(ran):
    from kei_panel.screens.dialogs import ChoiceScreen, InputScreen
    from kei_panel.screens.install_flow import PlanSummaryScreen
    app = App(['one', 'biblioteca.org.br', True])
    asyncio.run(ka.koha_access(app))
    kinds = [type(s) for s in app.screens]
    assert kinds == [ChoiceScreen, InputScreen, PlanSummaryScreen]
    assert app.screens[0]._default == 'two'
    plan = app.screens[-1]
    rows = dict(plan._rows)
    assert rows['Catalog'] == 'http://biblioteca.org.br' and rows['Staff'] == 'http://admin.biblioteca.org.br'
    assert rows['Staff on this server'] == 'http://127.0.0.1:8080'
    assert rows['Who may open the staff by name'].startswith('Only the local networks')
    assert rows['biblioteca.org.br'].startswith('✓') and rows['admin.biblioteca.org.br'].startswith('⚠')
    assert 'Not every name points here yet' in plan._note       # a warning, the button stays
    assert app.bridge.calls == [('koha-access', 'status'), ('koha-access', 'plan', 'one', 'biblioteca.org.br')]
    assert ran == [('koha-access', 'apply', 'one', 'biblioteca.org.br', 'confirm'), ('done',)]


def test_nothing_changes_without_the_yes(ran):
    for answers in ([None], ['one', None], ['one', 'biblioteca.org.br', False]):
        app = App(answers)
        asyncio.run(ka.koha_access(app))
        assert not ran
        assert all(c[1] in ('status', 'plan') for c in app.bridge.calls)


def test_the_choice_already_set_changes_nothing(ran):
    from kei_panel.screens.dialogs import MessageScreen
    app = App(['two'])
    asyncio.run(ka.koha_access(app))
    assert isinstance(app.screens[-1], MessageScreen) and not ran
    app = App(['one', 'biblioteca.org.br'], status=ONE)
    asyncio.run(ka.koha_access(app))
    assert app.screens[0]._default == 'one' and app.screens[1]._value == 'biblioteca.org.br'
    assert isinstance(app.screens[-1], MessageScreen) and not ran


def test_back_to_two_ports(ran):
    app = App(['two', True], status=ONE)
    asyncio.run(ka.koha_access(app))
    assert ('koha-access', 'plan', 'two') in app.bridge.calls
    assert ran == [('koha-access', 'apply', 'two', 'confirm'), ('done',)]
    assert dict(app.screens[-1]._rows) == {'Catalog': 'http://192.168.0.20', 'Staff': 'http://192.168.0.20:8080'}


def test_in_the_panel_addresses_of_koha(monkeypatch):
    """The routine is on Koha's Addresses and access (button and card) and
    in the demo."""
    for name in ('KOHA', 'TAINACAN', 'DSPACE'):
        monkeypatch.setenv('KEI_PANEL_DEMO_' + name, '1')
    from kei_panel import menus
    from kei_panel.routines import ROUTINES
    from kei_panel.views.addresses import CHANGE
    # (another test may wrap ROUTINES for tracing: the name is what counts)
    assert 'koha-access' in ROUTINES and CHANGE['koha'] == 'koha-access'
    assert menus.requires_of('koha-access') == 'koha' and menus.PLATFORM_TASKS['koha-access'] == 'koha-access'
    section = next(s for s in menus.SECTIONS if s.id == 'koha-addresses')
    assert 'koha-access' in [e.action for e in section.entries]
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang='en', plain=False, demo=True))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(.3)
            out = await app.bridge.task('koha-access', 'plan', 'one', 'biblioteca.org.br')
            return ka.plan_rows(ka.results(out))
    rows = dict(asyncio.run(main()))
    assert rows['Staff'] == 'http://admin.biblioteca.org.br'


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_new_texts_have_portuguese(pt):
    source = (ROOT / 'panel' / 'kei_panel' / 'routines' / 'koha_access.py').read_text(encoding='utf-8')
    texts = set(re.findall(r'(?<![\w.])t\("([^"]+)"\s*[,)]', source))
    texts |= {ka.TITLE, *ka.POINTS.values(), *ka.NETS.values(), 'One port or two…',
              'Catalog and staff on two ports by IP, or on one port with names (admin.your-domain)'}
    # Texts split over lines: joined as the source has them.
    for m in re.finditer(r'(?<![\w.])t\(\s*((?:"[^"]*"\s*)+)', source):
        texts.add(''.join(re.findall(r'"([^"]*)"', m.group(1))))
    installer = (ROOT / 'installer').read_text()
    body = installer[installer.index('kei_koha_access() {'):]
    body = body[:body.index('\n}\n')]
    texts |= set(re.findall(r'\$\(t "([^"]+)"\)', body))
    assert sorted(s for s in texts if pt(s) == s) == []
