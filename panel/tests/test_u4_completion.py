"""U4 acceptance: one completion screen, and DSpace's results in plain lines.

- The end of an installation is the same screen for every system: the
  checks summed up (the report one button away), the addresses with Open
  and Copy, the administrator, the next step.
- A DSpace without an administrator is "installed; one step is left", never
  "ready"; creating it is offered right there, and "Do it later" only closes.
- Backup, recovery test, restore and web repair show plain lines; the
  runtime's JSON is behind "Technical details", never in front.
- Every new text has Portuguese.
"""
import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kei_panel import dspace as ds_labels
from kei_panel.bridge import TaskOutcome
from kei_panel.i18n import Translator, install
from kei_panel.routines import dspace, platforms as tn
from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from kei_panel.screens.install_flow import CheckReportScreen, CompletionScreen, PlanSummaryScreen
from kei_panel.tasks import TaskResult

ROOT = Path(__file__).resolve().parents[2]
URL = 'http://192.168.1.20:8100'
OK_CHECKS = [('ok', 'Database (PostgreSQL)', 'Running'), ('ok', 'DSpace API', 'Running')]


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def response(data):
    out = TaskOutcome()
    out.feed('@@result payload=' + base64.b64encode(json.dumps(data).encode()).decode())
    return TaskResult(ok=True, value=out)


class App:
    """push_screen_wait answers from a list; reports and messages need none."""

    def __init__(self, answers=()):
        self.answers, self.screens = list(answers), []
        self.check_platforms = lambda: None

        async def status():
            return {'docker': {'installed': True}}
        self.bridge = SimpleNamespace(status=status)

    async def push_screen_wait(self, screen):
        self.screens.append(screen)
        if isinstance(screen, MessageScreen) or (isinstance(screen, CheckReportScreen) and screen._final):
            return None
        return self.answers.pop(0)


def runtime(monkeypatch, table):
    calls = []

    async def run(app, title, name, *args, **kwargs):
        calls.append((name, args))
        return response(table[args[0] if name == 'dspace-panel' else name])
    monkeypatch.setattr(dspace, 'run_task', run)
    return calls


DIAGNOSIS = {'status': 'installed', 'url': URL, 'health': 'api-ui-dependencies', 'public_access': 'verified-local-proxy',
             'services': {n: 'running' for n in ('postgres', 'solr', 'backend', 'ui')}}


# ---------------------------------------------------------------- completion
def completion(monkeypatch, admins, answer):
    calls = runtime(monkeypatch, {'diagnose': DIAGNOSIS, 'admin-status': admins})
    created = []

    async def admin(app, create=False):
        created.append(create)
    monkeypatch.setattr(dspace, 'admin', admin)
    app = App([answer])
    asyncio.run(dspace.completion(app, {'status': 'installed', 'url': URL}, URL))
    return app, created, [c[1][0] for c in calls]


def test_dspace_without_an_administrator_is_one_step_from_ready(monkeypatch):
    app, created, commands = completion(monkeypatch, {'admins': []}, 'action')
    screen = app.screens[0]
    assert isinstance(screen, CompletionScreen) and screen.pending
    assert commands == ['diagnose', 'admin-status']
    assert screen._facts == [('warn', 'Administrator account', 'not created yet')]
    assert screen._action == 'Create administrator now'
    assert screen._links == [('Public site', URL), ('Sign in', URL + '/login')]
    assert json.loads(screen._details) == DIAGNOSIS            # the diagnosis itself, behind the report's button
    assert created == [True]                                   # the create path, no second "create or change?" question


def test_do_it_later_only_closes(monkeypatch):
    app, created, _ = completion(monkeypatch, {'admins': []}, None)
    assert created == [] and len(app.screens) == 1


def test_dspace_with_an_administrator_is_ready(monkeypatch):
    app, created, _ = completion(monkeypatch, {'admins': ['ana@biblioteca.org']}, None)
    screen = app.screens[0]
    assert not screen.pending and not screen._action and not screen._next
    assert screen._facts == [('ok', 'Administrator account', 'ana@biblioteca.org')]


def test_unreadable_administrators_never_say_ready(monkeypatch):
    async def run(app, title, name, *args, **kwargs):
        if args[0] == 'admin-status':
            return TaskResult(ok=False, value=None)
        return response({'diagnose': DIAGNOSIS}[args[0]])
    monkeypatch.setattr(dspace, 'run_task', run)
    shown = []

    async def failure(app, title, result):
        shown.append(title)
    monkeypatch.setattr(dspace, 'show_failure', failure)
    app = App([None])
    asyncio.run(dspace.completion(app, {'url': URL}, URL))
    screen = app.screens[-1]
    assert screen.pending and screen._facts[0][0] == 'warn' and not screen._action
    assert shown == ['DSpace']


def test_admin_create_skips_the_create_or_change_question(monkeypatch):
    runtime(monkeypatch, {'admin-status': {'admins': ['ana@biblioteca.org'], 'languages': []}})
    app = App([None])                                          # closing the first box stops here
    asyncio.run(dspace.admin(app, create=True))
    assert isinstance(app.screens[0], InputScreen)
    app = App([None])
    asyncio.run(dspace.admin(app))
    assert isinstance(app.screens[0], ChoiceScreen)


def test_the_install_ends_on_the_completion_screen(monkeypatch):
    plan = {'url': URL, 'language': 'pt_BR', 'proxy': 'apache-nexus', 'migration': 'not-started'}
    calls = runtime(monkeypatch, {
        'availability': {'available': True}, 'dspace-prerequisites': {'proxy_mode': 'apache-nexus'},
        'preflight': {'ok': True, 'checks': []}, 'status': {'url': URL}, 'plan': plan,
        'install': {'status': 'installed', 'url': URL, 'note': 'Demo note.'}, 'diagnose': DIAGNOSIS,
        'admin-status': {'admins': []}})
    app = App([True, True, None])
    asyncio.run(dspace.install(app))
    kinds = [type(s) for s in app.screens]
    assert kinds == [CheckReportScreen, PlanSummaryScreen, CompletionScreen]   # no MessageScreen after the end
    assert app.screens[-1]._note == 'Demo note.'
    assert [c[1][0] for c in calls if c[0] == 'dspace-panel'][-2:] == ['diagnose', 'admin-status']


# --------------------------------------------------------------- operations
PACKAGE = '/var/backups/koha-nexus/dspace/knx-dspace-20261112-020000.tar.gz.gpg'
PLAN = {'platform': 'dspace', 'release_sha256': '4' * 64, 'compression': 'gz', 'source_url': URL,
        'destination_url': URL, 'files': 1284, 'uncompressed_bytes': 2147483648, 'safety_backup_required': True,
        'destination_database_must_be_readable': True, 'old_volumes_preserved': True, 'repository_will_pause': True,
        'isolated_verification_network': 'none; shared loopback only'}
RESTORED = {'restored': True, 'safety_backup': '/var/backups/koha-nexus/dspace/knx-dspace-safety.tar.gz.gpg',
            'old_volumes_preserved': True}
TESTED = {'verified': True, 'database': 'all logical records', 'files': 'all checksums', 'solr': 'all cold cores',
          'network': 'none; shared loopback only', 'public_ports': False}


def plain(rows):
    text = ' '.join(f'{a} {b}' for a, b in rows)
    assert '{' not in text and 'sha256' not in text and '_' not in text.replace('knx-dspace', '')
    return text


def test_restore_is_a_plain_summary_with_back_first(monkeypatch):
    calls = runtime(monkeypatch, {'backup-list': {'packages': [PACKAGE]}, 'backup-plan': PLAN,
                                  'backup-restore': RESTORED})
    app = App([PACKAGE, 'phrase words', True])
    asyncio.run(dspace.backup_restore(app))
    review = app.screens[2]
    assert isinstance(review, PlanSummaryScreen) and review._danger and review._action == 'Restore'
    text = plain(review._rows)
    assert 'knx-dspace-20261112-020000.tar.gz.gpg' in text and '2.0 GB' in text and '1284' in text
    assert json.loads(review._details) == PLAN
    done = app.screens[-1]
    assert isinstance(done, MessageScreen) and '{' not in done._body
    assert ('Safety backup', 'knx-dspace-safety.tar.gz.gpg') in done._details
    assert [c[1][0] for c in calls] == ['backup-list', 'backup-plan', 'backup-restore']


def test_declining_the_restore_summary_restores_nothing(monkeypatch):
    calls = runtime(monkeypatch, {'backup-list': {'packages': [PACKAGE]}, 'backup-plan': PLAN})
    asyncio.run(dspace.backup_restore(App([PACKAGE, 'phrase words', False])))
    assert 'backup-restore' not in [c[1][0] for c in calls]


def test_recovery_test_result_in_plain_lines(monkeypatch):
    runtime(monkeypatch, {'backup-list': {'packages': [PACKAGE]}, 'backup-test': TESTED})
    app = App([PACKAGE, 'phrase words', True])
    asyncio.run(dspace.backup_test(app))
    assert isinstance(app.screens[2], ConfirmScreen)
    done = app.screens[-1]
    assert '{' not in done._body and ('Recovery verified', 'Yes') in done._details
    plain(done._details)


def test_backup_result_in_plain_lines(monkeypatch):
    runtime(monkeypatch, {'backup-settings': {'compression': 'gz'},
                          'backup-create': {'package': PACKAGE, 'encrypted': True, 'compression': 'gz',
                                            'bytes': 734003200, 'window_seconds': 42}})
    app = App([True])
    asyncio.run(dspace.backup_create(app))
    rows = dict(app.screens[-1]._details)
    assert rows['File'] == 'knx-dspace-20261112-020000.tar.gz.gpg' and rows['Size'] == '700.0 MB'
    assert rows['Encrypted'] == 'Yes' and rows['Repository paused for'] == '42 s'


def test_web_repair_is_a_plain_summary(monkeypatch):
    plan = {'url': 'http://localhost:8100', 'previous_url': URL, 'local_only': True, 'changes': 'x',
            'data_volumes_preserved': True, 'database_migration': False,
            'note': 'localhost works only on this computer. Other computers require the network/address assistant.'}
    calls = runtime(monkeypatch, {'operations': plan})
    app = App(['local', False])
    asyncio.run(dspace.repair_web(app))
    review = app.screens[1]
    assert isinstance(review, PlanSummaryScreen) and json.loads(review._details) == plan
    assert 'http://localhost:8100 (this computer)' in plain(review._rows)
    assert len(calls) == 1                                     # declined: no --confirm run


def test_a_whole_set_restore_reports_at_its_own_end(monkeypatch):
    runtime(monkeypatch, {'backup-plan': PLAN, 'backup-restore': RESTORED})
    app = App(['phrase words', True])
    assert asyncio.run(dspace.restore_path(app, PACKAGE, show=False)) is True
    assert not [s for s in app.screens if isinstance(s, MessageScreen)]


# ----------------------------------------------------------------- Tainacan
class TApp:
    def __init__(self, admin_lines, answers):
        self.answers, self.screens = list(answers), []

        async def task(name, *args, **kwargs):
            out = TaskOutcome()
            lines = {'tainacan-status': ['@@result db=running', '@@result wordpress=running',
                                         '@@result health=healthy', '@@result images_pinned=yes',
                                         '@@result audit=ok', '@@result apache_site=yes',
                                         '@@result url=http://192.168.0.10:8090'],
                     'admin-status': admin_lines}[name]
            for line in lines:
                out.feed(line)
            return out
        self.bridge = SimpleNamespace(task=task)

    async def push_screen_wait(self, screen):
        self.screens.append(screen)
        return self.answers.pop(0)


def test_tainacan_with_its_generated_password_offers_to_set_one(monkeypatch):
    import kei_panel.routines.admin_access as access
    changed = []

    async def change(app, platform, user):
        changed.append((platform, user))
        return True
    monkeypatch.setattr(access, 'change_password', change)
    app = TApp(['@@result state=initial', '@@result initial=kn_7f3a', '@@result admin=kn_7f3a'], ['action'])
    asyncio.run(tn.tainacan_completion(app, TaskResult(ok=True, value=TaskOutcome())))
    screen = app.screens[0]
    assert screen.pending and screen._facts[0][0] == 'warn' and 'kn_7f3a' in screen._facts[0][2]
    assert screen._links[1] == ('Sign in', 'http://192.168.0.10:8090/wp-admin')
    assert changed == [('tainacan', 'kn_7f3a')]


def test_tainacan_with_its_own_password_is_ready():
    app = TApp(['@@result state=own', '@@result admin=bibliotecaria'], [None])
    asyncio.run(tn.tainacan_completion(app, TaskResult(ok=True, value=TaskOutcome())))
    screen = app.screens[0]
    assert not screen.pending and not screen._action


# ------------------------------------------------------------------- screen
@pytest.mark.parametrize('size', [(80, 24), (160, 48)])
def test_completion_fits_and_opens_the_report(size, pt):
    from textual.app import App as TextualApp
    from textual.widgets import Button, Label

    copied, results = [], []

    class Box(TextualApp):
        CSS_PATH = str(ROOT / 'panel' / 'kei_panel' / 'panel.tcss')

        def copy_to_clipboard(self, text):
            copied.append(text)

        def on_mount(self):
            self.push_screen(CompletionScreen(
                'DSpace', OK_CHECKS, [('Site público', URL), ('Login', URL + '/login')],
                facts=[('warn', 'Conta de administrador', 'ainda não criada')],
                next_step='Crie a conta de administrador para entrar no DSpace.', action='Criar administrador agora',
                reminder='Acesso administrativo, endereços e backups ficam sempre no menu do DSpace.'), results.append)

    async def run():
        app = Box()
        async with app.run_test(size=size) as pilot:
            await pilot.pause(.2)
            screen = app.screen
            title = str(screen.query_one('#completion-title', Label).render())
            assert 'falta um passo' in title and 'pronto' not in title
            assert screen.focused is screen.query_one('#action', Button)
            for bid in ('#action', '#later'):
                assert screen.query_one(bid, Button).region.bottom <= size[1]
            await pilot.click('#copy-1')
            assert copied == [URL + '/login']
            await pilot.click('#report')
            await pilot.pause(.2)
            assert isinstance(app.screen, CheckReportScreen) and app.screen._final
            app.screen.dismiss(True)
            await pilot.pause(.1)
            await pilot.press('escape')
            await pilot.pause(.1)
    asyncio.run(run())
    assert results == [None]


def test_titles_by_state():
    async def build():      # a Screen needs a running loop on Python 3.9
        return (CompletionScreen('DSpace', OK_CHECKS, []),
                CompletionScreen('DSpace', OK_CHECKS, [], facts=[('warn', 'Administrator account', 'not created yet')]),
                CompletionScreen('DSpace', OK_CHECKS + [('fail', 'Public interface', 'Stopped')], []))
    ready, pending, failed = asyncio.run(build())
    assert (ready.pending, pending.pending, failed.pending) == (False, True, True)


def test_new_texts_have_portuguese(pt):
    texts = ['${name} is ready', '${name} is installed; one step is left', '${name} is installed, with checks to review',
             'Checks', '${n} of ${total} passed', 'See the report', 'Open', 'Copy', 'Copied.', 'Do it later',
             'Create administrator now', 'Create the administrator account to sign in to DSpace.', 'Public site',
             'Sign in', 'Set my password now', 'Restore DSpace · Review', 'Repair web access · Review',
             'Encrypted DSpace backup created.', 'Recovery test passed. The backup can be restored.',
             'DSpace restored. Check the repository before sharing its address.',
             'Administrative access, addresses and backups are always in the DSpace menu.',
             'Administrative access, the address and backups are always in the Tainacan menu.',
             'Set your own password to sign in to WordPress; the generated one is not shown.',
             '${name}, with a generated password', 'not created yet', 'could not be read; see Administrative access']
    rows = (ds_labels.backup_rows({'package': PACKAGE, 'bytes': 1, 'compression': 'gz', 'encrypted': True,
                                   'window_seconds': 1})
            + ds_labels.restore_plan_rows(PLAN, PACKAGE) + ds_labels.test_rows(TESTED)
            + ds_labels.restore_rows(RESTORED)
            + ds_labels.repair_rows({'url': 'http://localhost:8100', 'previous_url': URL,
                                     'data_volumes_preserved': True, 'database_migration': False,
                                     'note': 'The configured public address is preserved.'}))
    # Built while Portuguese is active: no English label is left.
    english = {label for label, _v in rows} | {value for _l, value in rows}
    install(Translator('en', None))
    en_rows = (ds_labels.restore_plan_rows(PLAN, PACKAGE) + ds_labels.test_rows(TESTED)
               + ds_labels.restore_rows(RESTORED))
    install(pt)
    assert not ({label for label, _v in en_rows} - {'Backup'}) & english
    missing = sorted(s for s in texts if pt(s) == s and s not in ('OK',))
    assert missing == []
