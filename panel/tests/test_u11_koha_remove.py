"""U11 acceptance (study 17.3): Koha removed as its own step.

- The plan is shown before anything: what goes (instance, database, site,
  scheduled tasks), what stays (packages, firewall, tunnel, backups, files,
  the other systems), where the safety package goes and how Koha comes back.
- Nothing runs without the review's button and the Yes; the apply is
  "keep confirm", never cancellable half way.
- No backup key: the person chooses the key first (nothing removed) or a
  package without Koha's secrets (said, never silent).
- Remove instance offers Koha when the installer has the step; an older
  installer keeps saying it is not available.
- The installer side (kei_koha_remove) runs in tests/koha_remove.bats and,
  with a real Koha and Tainacan, in tests/koha_set_system.bats.
- Every new text has Portuguese.
"""
import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kei_panel.bridge import TaskOutcome
from kei_panel.i18n import Translator, install
from kei_panel.routines import koha_remove as kr
from kei_panel.tasks import TaskResult

ROOT = Path(__file__).resolve().parents[2]

PLAN = ['@@result instance=library', '@@result database=koha_library', '@@result version=24.05.06',
        '@@result go=instance|/etc/koha/sites/library', '@@result go=database|koha_library',
        '@@result go=apache-site|/etc/apache2/sites-available/library.conf',
        '@@result go=cron|/etc/cron.d/koha_tasks',
        *[f'@@result keep={k}' for k in ('packages', 'firewall', 'tunnel', 'backups', 'files')],
        '@@result others=tainacan', '@@result dest=/var/backups/koha-nexus']


def outcome(lines, rc=0):
    out = TaskOutcome(rc=rc)
    for line in lines:
        out.feed(line)
    return out


class Bridge:
    def __init__(self, secrets='with', rc=0, tasks=('koha-remove',)):
        self.secrets, self.rc, self.calls, self.tasks = secrets, rc, [], tasks

    async def task(self, name, *args, **kwargs):
        self.calls.append((name, *args))
        return outcome(PLAN + [f'@@result secrets={self.secrets}'], self.rc)

    def has_task(self, name):
        return name in self.tasks


class App:
    def __init__(self, answers, **bridge):
        self.answers, self.screens, self.checked = list(answers), [], 0
        self.bridge = Bridge(**bridge)

    async def push_screen_wait(self, screen):
        self.screens.append(screen)
        return self.answers.pop(0) if self.answers else None

    def platform_ready(self, p):
        return p in ('koha', 'tainacan')

    def check_platforms(self):
        self.checked += 1


@pytest.fixture
def ran(monkeypatch):
    import kei_panel.routines.common as common
    calls = []

    async def run_task(app, title, name, *args, **kwargs):
        calls.append((name, *args, kwargs.get('cancellable', True)))
        return TaskResult(ok=True, value=outcome(['@@result package=/var/backups/koha-nexus/set.tar',
                                                 '@@result removed=yes']))

    async def show_done(app, title, result, default=''):
        calls.append(('done', default))
    monkeypatch.setattr(common, 'run_task', run_task)
    monkeypatch.setattr(common, 'show_done', show_done)
    return calls


def test_plan_then_yes_then_remove_keeping_the_data(ran):
    from kei_panel.screens.dialogs import ConfirmScreen
    from kei_panel.screens.install_flow import PlanSummaryScreen
    app = App([True, True])
    asyncio.run(kr.koha_remove(app))
    assert [type(s) for s in app.screens] == [PlanSummaryScreen, ConfirmScreen]
    plan = app.screens[0]
    assert plan._danger and app.screens[1]._danger
    rows = plan._rows
    goes = [v.rpartition(': ')[2] for k, v in rows if k.startswith('✗')]
    assert goes == ['/etc/koha/sites/library', 'koha_library', '/etc/apache2/sites-available/library.conf',
                    '/etc/cron.d/koha_tasks']
    stays = ' '.join(v for k, v in rows if k.startswith('✓'))
    for word in ('koha-common', 'firewall', 'tunnel', 'backups already made', '/var/lib/koha', 'tainacan'):
        assert word in stays, word
    assert dict(rows)['Safety package'] == '/var/backups/koha-nexus'
    assert 'Nothing was changed so far' in plan._body and '"library"' in plan._body
    assert '24.05' in plan._note and 'Assisted restore' in plan._note
    assert app.bridge.calls == [('koha-remove', 'plan')]
    assert ran[0] == ('koha-remove', 'apply', 'keep', 'confirm', False)
    assert '/var/backups/koha-nexus/set.tar' in ran[1][1] and app.checked == 1


def test_nothing_runs_without_both_yeses(ran):
    for answers in ([None], [False], [True, False], [True, None]):
        app = App(answers)
        asyncio.run(kr.koha_remove(app))
        assert not ran and app.checked == 0
        assert app.bridge.calls == [('koha-remove', 'plan')]


def test_no_backup_key_key_first_or_package_without_secrets(ran, monkeypatch):
    from kei_panel.routines import ROUTINES
    from kei_panel.screens.dialogs import ChoiceScreen, MessageScreen
    opened = []

    async def setup(app):
        opened.append('pbackup-setup')
    monkeypatch.setitem(ROUTINES, 'pbackup-setup', setup)
    app = App(['key'], secrets='needs-choice')
    asyncio.run(kr.koha_remove(app))
    assert isinstance(app.screens[0], ChoiceScreen) and isinstance(app.screens[-1], MessageScreen)
    assert opened == ['pbackup-setup'] and not ran
    app = App([None], secrets='needs-choice')
    asyncio.run(kr.koha_remove(app))
    assert not ran
    app = App(['data', True, True], secrets='needs-choice')
    asyncio.run(kr.koha_remove(app))
    assert ran[0] == ('koha-remove', 'apply', 'keep', 'confirm', 'no-secrets', False)


def test_plan_failure_is_shown_and_nothing_runs(ran, monkeypatch):
    shown = []

    async def show_failure(app, title, result):
        shown.append(result.value.rc)
    monkeypatch.setattr('kei_panel.routines.common.show_failure', show_failure)
    app = App([True, True], rc=3)
    asyncio.run(kr.koha_remove(app))
    assert shown == [3] and not ran and not app.screens


def test_remove_instance_offers_koha_only_with_the_step(monkeypatch):
    from kei_panel.routines import ROUTINES, instances
    from kei_panel.screens.dialogs import ChoiceScreen
    chosen = []

    async def run(app):
        chosen.append('koha-remove')
    monkeypatch.setitem(ROUTINES, 'koha-remove', run)
    seen = []

    async def pick(screen):
        seen.append(screen)
        return 'koha' if isinstance(screen, ChoiceScreen) else None
    app = SimpleNamespace(platform_ready=lambda p: p == 'koha', push_screen_wait=pick,
                          bridge=SimpleNamespace(has_task=lambda n: n == 'koha-remove'))
    asyncio.run(instances.remove(app))
    assert chosen == ['koha-remove']
    assert 'koha' in [k for k, _v in seen[0]._options]
    seen.clear()
    old = SimpleNamespace(platform_ready=lambda p: p == 'koha', push_screen_wait=pick,
                          bridge=SimpleNamespace(has_task=lambda n: False))
    asyncio.run(instances.remove(old))
    assert chosen == ['koha-remove'] and instances.KOHA_REMOVAL.split(':')[0] in seen[0]._body


def test_in_the_panel(monkeypatch):
    for name in ('KOHA', 'TAINACAN', 'DSPACE'):
        monkeypatch.setenv('KEI_PANEL_DEMO_' + name, '1')
    from kei_panel import menus
    from kei_panel.routines import ROUTINES
    assert 'koha-remove' in ROUTINES and menus.PLATFORM_TASKS['koha-remove'] == 'koha-remove'
    assert menus.requires_of('koha-remove') == 'koha' and menus.DESCRIPTIONS['koha-remove']
    entry = next(e for e in menus.section('koha').entries if e.action == 'koha-remove')
    assert entry.zone == 'removal'
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang='en', plain=False, demo=True))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(.3)
            out = await app.bridge.task('koha-remove', 'plan')
            return kr.plan_rows(kr.results(out))
    rows = asyncio.run(main())
    assert ('✗ Goes', 'The instance (koha-remove): /etc/koha/sites/library') in rows


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_new_texts_have_portuguese(pt):
    from kei_panel import menus
    source = (ROOT / 'panel' / 'kei_panel' / 'routines' / 'koha_remove.py').read_text(encoding='utf-8')
    texts = set(re.findall(r'(?<![\w.])t\("([^"]+)"\s*[,)]', source))
    for m in re.finditer(r'(?<![\w.])t\(\s*((?:"(?:[^"\\]|\\.)*"\s*)+)', source):
        texts.add(''.join(s.replace('\\"', '"') for s in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))))
    texts |= {kr.TITLE, *kr.GO.values(), *kr.KEEP.values(), '🗑  Remove Koha', menus.DESCRIPTIONS['koha-remove']}
    installer = (ROOT / 'installer').read_text()
    body = installer[installer.index('kei_koha_remove() {'):]
    body = body[:body.index('\n}\n')]
    texts |= set(re.findall(r'\$\(t "([^"]+)"\)', body))
    assert sorted(s for s in texts if pt(s) == s) == []
