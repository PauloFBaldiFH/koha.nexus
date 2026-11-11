"""U1 acceptance: the normal screens speak the person's language.

- DSpace is no longer called experimental on its normal screens; the build
  note uses the approved requirement text.
- DSpace phases and states are shown as translated labels, never as the raw
  protocol word ("ready", "running").
- Every fixed text on the DSpace, Backup center, dashboard and schedule
  screens has a Portuguese translation.
- A weekly schedule shows the weekday name, never "0", and the switch says
  what it means.
"""
import ast
import asyncio
from pathlib import Path

import pytest

from kei_panel import dspace, platforms, schedules
from kei_panel.i18n import Translator, install

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / 'panel' / 'kei_panel'
SCREENS = ['dspace.py', 'routines/dspace.py', 'views/backups.py', 'views/dashboard.py', 'views/schedules.py']
# Same word in both languages, on purpose.
SAME = {'Koha', 'online', 'offline'}


@pytest.fixture
def pt():
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def literal_t_calls(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if (isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 't' and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            yield node.args[0].value


def label_texts():
    tables = (dspace.STATE_LABELS, dspace.PHASE_LABELS, dspace.SERVICE_LABELS)
    return [v for table in tables for v in table.values()] + [dspace.BUILD_NOTE]


def test_every_fixed_text_on_these_screens_has_a_portuguese_translation(pt):
    missing = sorted({(name, s) for name in SCREENS for s in literal_t_calls(PANEL / name)
                      if s not in SAME and pt(s) == s})
    missing += [('labels', s) for s in label_texts() if pt(s) == s]
    assert not missing


@pytest.mark.parametrize('mode', ['absent', 'incomplete', 'failing', 'unknown', 'installed'])
def test_dspace_home_line_is_translated_and_not_experimental(pt, mode, monkeypatch):
    monkeypatch.setattr(platforms, 'dspace_mode', lambda facts: mode)
    line = platforms.dspace_problem({})
    assert 'xperimental' not in line
    install(Translator('en', None))
    assert pt(platforms.dspace_problem({})) != platforms.dspace_problem({})


def test_no_normal_dspace_text_says_experimental():
    for name in SCREENS + ['platforms.py']:
        texts = [s for s in literal_t_calls(PANEL / name)]
        assert not [s for s in texts if 'xperimental' in s], name
    assert 'xperimental' not in dspace.BUILD_NOTE


def test_approved_build_note_in_portuguese(pt):
    assert pt(dspace.BUILD_NOTE) == 'Imagens compiladas neste servidor a partir de uma receita fixada e verificada; processador amd64'


@pytest.mark.parametrize('table,raw', [(dspace.PHASE_LABELS, 'ready'), (dspace.SERVICE_LABELS, 'running'),
                                       (dspace.STATE_LABELS, 'installed'), (dspace.STATE_LABELS, 'degraded')])
def test_runtime_words_become_labels(pt, table, raw):
    shown = dspace.label(table, raw)
    assert shown != raw and shown == pt(table[raw])


def test_unknown_runtime_word_is_marked_unknown_not_hidden(pt):
    assert dspace.label(dspace.PHASE_LABELS, 'something-new') == 'Desconhecido (something-new)'
    assert dspace.label(dspace.PHASE_LABELS, None) == 'Desconhecido'


def test_dspace_summary_shows_labels_and_no_experimental_note(pt):
    from textual.app import App
    from kei_panel.widgets.cards import StatusCard

    data = {'status': 'installed', 'phase': 'ready', 'url': 'http://192.168.1.20:8100',
            'services': {'postgres': 'running', 'solr': 'running', 'backend': 'exited', 'ui': 'running'}}

    class Box(App):
        def compose(self):
            yield dspace.DSpaceSummary()

    async def run():
        app = Box()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one(dspace.DSpaceSummary).show(data)
            await pilot.pause()
            text = '\n'.join(str(card.render()) + ' ' + ' '.join(str(w.render()) for w in card.query('*'))
                             for card in app.query(StatusCard))
            text += ' '.join(str(w.render()) for w in app.query('LinkCard *'))
            return text

    text = asyncio.run(run())
    assert 'Instalação concluída' in text and 'Instalado e em execução' in text
    assert 'Funcionando' in text and 'Parado' in text
    assert 'xperimental' not in text and 'ready' not in text


WEEKLY = (schedules.cron.CRON_PATH + '\n0 23 * * 0 root /bin/bash /root/backup_sql.sh >/dev/null 2>&1\n')


def select_label(select):
    from textual.widgets import Static
    return str(select.query_one('SelectCurrent Static#label', Static).render())


@pytest.mark.parametrize('size', [(80, 24), (160, 48)])
def test_weekly_schedule_shows_the_weekday_and_the_switch_says_active(monkeypatch, size, pt):
    from kei_panel import demo
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from textual.widgets import Label, Select

    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA', '1')
    monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN', '0')
    monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE', '0')
    monkeypatch.setattr(demo, 'demo_cron_files', lambda *args: {schedules.TASKS_FILE: WEEKLY})

    async def until(pilot, condition):
        for _ in range(80):
            if condition():
                return
            await pilot.pause(.1)
        raise AssertionError('Schedules did not load')

    async def run():
        app = KohaPanelApp(PanelEnv(installer=ROOT / 'installer', lang='pt', plain=False, demo=True))
        async with app.run_test(size=size) as pilot:
            await pilot.pause(.3)
            app.screen.action_show('schedules')
            view = app.screen.query_one('#view-schedules')
            await until(pilot, lambda: view.ready and view.query('.sc-controls'))
            i = next(i for i, r in enumerate(view.rows) if r.key == 'koha:backup_sql')
            day = view.query_one(f'#sc-day-{i}', Select)
            assert day.display and day.value == 0
            assert select_label(day) == pt('Sunday')
            assert pt('Active') in [str(w.render()) for w in view.query('.sc-switch-label').results(Label)]
            # Monday, then monthly (day 1 is the first option) and back.
            day.value = 1
            await pilot.pause(.1)
            assert select_label(day) == pt('Monday')
            freq = view.query_one(f'#sc-freq-{i}', Select)
            freq.value = 'monthly'
            await pilot.pause(.2)
            assert day.value == 1 and select_label(day) == pt('Day ${n}', n=1)
            freq.value = 'weekly'
            await pilot.pause(.2)
            assert day.value == 1 and select_label(day) == pt('Monday')
    asyncio.run(run())
