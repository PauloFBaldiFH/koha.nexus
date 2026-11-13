"""U3 acceptance: one installation pattern for DSpace and Tainacan.

- Before any question, the whole list of requirements (initial diagnosis),
  read only; Continue is off while any item failed.
- The plan is a plain summary; the technical plan (JSON) is one button away,
  never in front.
- The loader's bar moves by stage ("@@stage [n/N]"), never with the clock,
  and a quiet stage says how long it has been running.
- After the installation, the final diagnosis as a report.
- Every new text has Portuguese.
"""
import asyncio
import base64
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from kei_panel import dspace as ds_labels
from kei_panel.bridge import TaskOutcome, stage_parts
from kei_panel.i18n import Translator, install
from kei_panel.routines import dspace, platforms as tn
from kei_panel.screens.dialogs import MessageScreen, TextScreen
from kei_panel.screens.port_field import PortState
from kei_panel.screens.install_flow import CheckReportScreen, CompletionScreen, PlanSummaryScreen
from kei_panel.tasks import TaskResult

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'platforms' / 'dspace'))


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


class Reporter:
    def __init__(self):
        self.calls = []

    def log(self, line): self.calls.append(('log', line))
    def status(self, text): self.calls.append(('status', text))
    def notice(self, text): self.calls.append(('notice', text))
    def progress(self, current, total): self.calls.append(('progress', current, total))


def test_a_numbered_stage_moves_the_bar_by_stages_done(pt):
    reporter = Reporter()
    out = TaskOutcome()
    out.feed('@@stage [6/7] Preparing the database\tCreates the tables of the repository. It can take up to 20 '
             'minutes without new lines; the work goes on.', reporter)
    assert ('progress', 5, 7) in reporter.calls
    notice = [c[1] for c in reporter.calls if c[0] == 'notice'][0]
    assert notice.startswith('[6/7] Preparando o banco de dados\nCria as tabelas')


def test_routines_with_their_own_steps_keep_their_bar():
    # Koha's installation counts @@step lines (total_steps); its stages only inform.
    reporter = Reporter()
    TaskOutcome(total_steps=18).feed('@@stage [3/7] Database and Koha\tnote', reporter)
    assert not [c for c in reporter.calls if c[0] == 'progress']
    reporter = Reporter()
    TaskOutcome().feed('@@stage Waiting for the authorization...\tOpen this address', reporter)
    assert not [c for c in reporter.calls if c[0] == 'progress']
    assert stage_parts('[9/7] x') == ('[9/7] x', 0, 0)


def test_every_runtime_stage_is_one_of_seven_in_order():
    import runtime
    numbers = [n for n, _l, _t in runtime.STAGES.values()]
    assert numbers == sorted(numbers) == list(range(1, 8))


def response(data):
    out = TaskOutcome()
    out.feed('@@result payload=' + base64.b64encode(json.dumps(data).encode()).decode())
    return TaskResult(ok=True, value=out)


PLAN = {'schema': 1, 'experimental': True, 'url': 'http://192.168.1.20:8100', 'language': 'pt_BR',
        'images': {'backend': 'sha256:' + '1' * 64}, 'release_sha256': '2' * 64, 'proxy': 'apache-nexus',
        'ports': {'ui': 18100, 'backend': 18101}, 'migration': 'not-started'}
CHECKS = {'ok': True, 'checks': [{'id': 'memory', 'state': 'ok', 'label': 'Free memory (4 GB needed)', 'detail': '6.1 GB'}]}
DIAGNOSIS = {'status': 'installed', 'url': 'http://192.168.1.20:8100', 'health': 'api-ui-dependencies',
             'public_access': 'verified-local-proxy',
             'services': {n: 'running' for n in ('postgres', 'solr', 'backend', 'ui')}}


class App:
    def __init__(self, answers):
        self.answers, self.screens = list(answers), []
        self.check_platforms = lambda: None

        async def status():
            return {'docker': {'installed': True}}
        self.bridge = SimpleNamespace(status=status)

    async def push_screen_wait(self, screen):
        self.screens.append(screen)
        if isinstance(screen, MessageScreen):
            return None
        if isinstance(screen, CheckReportScreen) and screen._final:
            return True
        if isinstance(screen, CompletionScreen):
            return None                       # U4: the end of the flow, "Do it later"
        return self.answers.pop(0)


def run_dspace(monkeypatch, answers, checks=CHECKS):
    calls = []
    table = {'availability': {'available': True}, 'dspace-prerequisites': {'proxy_mode': 'apache-nexus'},
             'preflight': checks, 'status': {'url': 'http://192.168.1.20:8100'}, 'plan': PLAN,
             'install': {'status': 'installed', 'url': 'http://192.168.1.20:8100'}, 'diagnose': DIAGNOSIS,
             'admin-status': {'state': 'own', 'admins': []}}

    async def run(app, title, name, *args, **kwargs):
        calls.append((name, args))
        return response(table[args[0] if name == 'dspace-panel' else name])
    monkeypatch.setattr(dspace, 'run_task', run)
    app = App(answers)
    asyncio.run(dspace.install(app))
    # The runtime's commands; the prerequisites plan shows as "prerequisites".
    return app, [c[1][0] if c[0] == 'dspace-panel' else 'prerequisites' for c in calls]


def test_dspace_installs_through_diagnosis_summary_stages_and_report(monkeypatch):
    app, commands = run_dspace(monkeypatch, [True, True])
    kinds = [type(s) for s in app.screens]
    assert kinds[:3] == [CheckReportScreen, PlanSummaryScreen, CompletionScreen]   # U4: the report sits in the completion
    assert commands.index('preflight') < commands.index('plan') < commands.index('install') < commands.index('diagnose')
    summary = app.screens[1]
    shown = ' '.join(f'{a} {b}' for a, b in summary._rows)
    assert '{' not in shown and 'sha256' not in shown and 'experimental' not in shown
    assert json.loads(summary._details) == PLAN                      # the plan itself, unchanged, behind a button
    assert 'http://192.168.1.20:8100' in shown
    final = app.screens[2]
    assert all(state == 'ok' for state, _l, _d in final._checks)


@pytest.mark.parametrize('answer', [False, None])
def test_closing_the_initial_diagnosis_changes_nothing(monkeypatch, answer):
    app, commands = run_dspace(monkeypatch, [answer])
    assert commands == ['availability', 'prerequisites', 'preflight']


def test_declining_the_summary_never_installs(monkeypatch):
    app, commands = run_dspace(monkeypatch, [True, False])
    assert 'install' not in commands and isinstance(app.screens[1], PlanSummaryScreen)


def test_rows_from_the_runtime():
    deps = {'apache_missing': True, 'docker_stopped': True}
    rows = ds_labels.preflight_rows(CHECKS, deps)
    assert ('warn', 'Web server (Apache)') in [r[:2] for r in rows]
    assert ('warn', 'Docker service started') in [r[:2] for r in rows]
    broken = dict(DIAGNOSIS, health='failed', public_access='failed', reason='API not ready',
                  services={'postgres': 'running', 'solr': 'exited'})
    states = {label: state for state, label, _d in ds_labels.diagnosis_rows(broken)}
    assert states['Search (Solr)'] == 'fail' and states['DSpace API'] == 'fail'
    assert states['API, interface and login page checked'] == 'fail'
    assert states['Address verified from this server'] == 'fail'
    assert ds_labels.where('http://localhost:8100') == 'this computer'
    assert ds_labels.where('http://192.168.1.20:8100') == "the institution's network"
    assert ds_labels.where('http://repositorio.exemplo.org') == 'a name (domain)'


@pytest.mark.parametrize('size', [(80, 24), (160, 48)])
def test_a_failed_requirement_keeps_continue_off_and_details_open_on_request(size):
    from textual.app import App as TApp
    from textual.widgets import Button

    rows = [('ok', 'amd64 processor', 'x86_64'), ('fail', 'Free memory (4 GB needed)', '2.0 GB'),
            ('warn', 'Web server (Apache)', 'not installed')]
    results = []

    class Box(TApp):
        CSS_PATH = str(ROOT / 'panel' / 'kei_panel' / 'panel.tcss')

        def on_mount(self):
            self.push_screen(CheckReportScreen('Before installing DSpace', rows, details='{"a": 1}'), results.append)

    async def run():
        app = Box()
        async with app.run_test(size=size) as pilot:
            await pilot.pause(.2)
            screen = app.screen
            assert screen.query_one('#continue', Button).disabled
            for i in range(len(rows)):
                assert screen.query_one(f'#check-{i}').region.bottom <= size[1]
            assert screen.query_one('#cancel', Button).region.bottom <= size[1]
            await pilot.click('#details')
            await pilot.pause(.2)
            assert isinstance(app.screen, TextScreen)
            app.screen.dismiss(None)
            await pilot.pause(.1)
            await pilot.click('#cancel')
            await pilot.pause(.1)
    asyncio.run(run())
    assert results == [False]


def test_a_quiet_stage_says_how_long_it_has_been_running(pt):
    from textual.app import App as TApp
    from kei_panel.screens.loading import LoadingScreen

    async def job(reporter):
        reporter.notice('[6/7] Preparando o banco de dados\nnote')
        reporter.progress(5, 7)
        await asyncio.sleep(30)

    class Box(TApp):
        def on_mount(self):
            self.push_screen(LoadingScreen('DSpace', job))

    async def run():
        app = Box()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(.3)
            screen = app.screen
            screen.stage_started -= 185
            screen.last_output -= 20
            screen._update_clock()
            text = str(screen.query_one('#loader-waiting').render())
            assert 'em andamento há 3 min' in text
            assert screen.query_one('#loader-bar').display
            screen.worker.cancel()
            await pilot.pause(.1)
    asyncio.run(run())


class TApp:
    """Tainacan's flow with the installer's answers."""

    def __init__(self, answers, checks):
        self.answers, self.screens, self.tasks = list(answers), [], []
        results = {'tainacan-plan': {'plan': 'install', 'address': 'http://192.168.0.10:8090',
                                     'images': 'WordPress 7.1.4', 'kept': 'Not changed: Koha'},
                   'tainacan-status': {'db': 'running', 'wordpress': 'running', 'health': 'healthy',
                                       'images_pinned': 'yes', 'audit': 'ok', 'apache_site': 'yes',
                                       'collections': '0'}}

        async def task(name, *args, **kwargs):
            self.tasks.append(name)
            out = TaskOutcome()
            if name == 'tainacan-preflight':
                for row in checks:
                    out.feed('@@result check=' + row)
            for key, value in results.get(name, {}).items():
                out.feed(f'@@result {key}={value}')
            return out

        async def status():
            return {'docker': {'installed': True, 'running': True}}
        self.bridge = SimpleNamespace(task=task, has_task=lambda name: name != 'setup-mark', status=status)

    async def push_screen_wait(self, screen):
        self.screens.append(screen)
        if isinstance(screen, (MessageScreen, CompletionScreen)) or (isinstance(screen, CheckReportScreen) and screen._final):
            return None
        return self.answers.pop(0)


def run_tainacan(monkeypatch, answers, checks):
    import kei_panel.routines.common as common
    ran = []

    async def run(app, title, name, *args, **kwargs):
        ran.append(name)
        return TaskResult(ok=True, value=TaskOutcome())
    monkeypatch.setattr(common, 'run_task', run)

    async def free(app):
        return None
    monkeypatch.setattr(tn, 'read_free', free)
    monkeypatch.setattr(tn.platforms, 'docker_from_status',
                        lambda status: SimpleNamespace(known=True, installed=True, running=True))
    app = TApp(answers, checks)
    asyncio.run(tn.tainacan_install(app))
    return app, ran


GOOD = ['ok|Docker running on this server|29.1.3', 'ok|Free memory (768 MB needed)|5934 MB',
        'warn|Web server (Apache)|not installed']


def test_tainacan_installs_through_diagnosis_summary_and_report(monkeypatch):
    # U9: the port field keeps the proposed port.
    app, ran = run_tainacan(monkeypatch, [True, 'local', PortState(8090, 'free', lan='192.168.0.10'), True], GOOD)
    kinds = [type(s).__name__ for s in app.screens]
    assert kinds[0] == 'CheckReportScreen' and 'PlanSummaryScreen' in kinds
    assert ran == ['tainacan-install']
    assert app.tasks.index('tainacan-preflight') < app.tasks.index('tainacan-plan') < app.tasks.index('tainacan-status')
    final = [s for s in app.screens if isinstance(s, CompletionScreen)][0]
    assert all(state == 'ok' for state, _l, _d in final._checks)
    summary = [s for s in app.screens if isinstance(s, PlanSummaryScreen)][0]
    assert ('Address', 'http://192.168.0.10:8090') in summary._rows


def test_tainacan_with_a_failed_requirement_asks_nothing_else(monkeypatch):
    app, ran = run_tainacan(monkeypatch, [False], GOOD + ['fail|Free disk (3072 MB needed)|900 MB'])
    assert ran == [] and app.tasks == ['tainacan-preflight'] and len(app.screens) == 1


def test_new_texts_have_portuguese(pt):
    import runtime
    texts = [x for _n, label, note in runtime.STAGES.values() for x in (label, note)]
    texts += [r['label'] for r in [
        {'label': 'amd64 processor'}, {'label': 'Debian or Ubuntu'}, {'label': 'Free memory (4 GB needed)'},
        {'label': 'Free disk (8 GB needed)'}, {'label': 'Docker running on this server'},
        {'label': 'Internal ports 18100 and 18101 free'}, {'label': 'Programs of DSpace ready'}]]
    source = (ROOT / 'platforms' / 'dspace' / 'runtime.py').read_text()
    preflight = source[source.index('def preflight'):source.index('def plan(')]
    texts += re.findall(r"add\('\w+', [^,]+, '([^']+)'", preflight)
    texts += [d for d in re.findall(r"'([a-z][^']+)'\)\n", preflight) if ' ' in d]
    installer = (ROOT / 'installer').read_text()
    body = installer[installer.index('kei_tainacan_preflight() {'):installer.index('# kei_tainacan_plan [URL]')]
    texts += re.findall(r"printf '(?:ok|warn|fail)\\t([A-Z][^\\%]+)\\t", body)
    texts += re.findall(r'_kei_tn_stage \d "([^"]+)" "([^"]+)"', installer)[0]
    texts += [x for pair in re.findall(r'_kei_tn_stage \d "([^"]+)" "([^"]+)"', installer) for x in pair]
    texts += [label for _k, label in tn.TAINACAN_PLAN_LABELS]
    texts += ['Before installing DSpace', 'DSpace diagnosis after the installation', 'Install DSpace · Review',
              'Before installing Tainacan', 'Tainacan diagnosis after the installation', 'Install Tainacan · Review',
              'Nothing was changed so far.', 'Technical details', 'Install', 'Initial language',
              'This stage has been running for ${minutes} min. It reports only when it finishes; the work goes on.']
    for rows in (ds_labels.diagnosis_rows(DIAGNOSIS), tn.tainacan_status_rows({})):
        texts += [label for _s, label, _d in rows]
    missing = sorted({s for s in texts if pt(s) == s and s not in ('Plugin', 'Web', 'Docker', 'WordPress', 'amd64')})
    assert missing == []
    # The summary is built in the person's language: every line differs from
    # English, except the address itself.
    shown_pt = ds_labels.plan_rows(PLAN)
    install(Translator('en', None))
    shown_en = ds_labels.plan_rows(PLAN)
    assert [i for i, (a, b) in enumerate(zip(shown_pt, shown_en)) if a[0] == b[0] or (a[1] == b[1] and i != 2)] == []
