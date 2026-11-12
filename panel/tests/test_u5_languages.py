"""U5 acceptance, second part (study 17.2): the Language center.

- "Languages" stays in the server's sidebar (not under Diagnosis) and opens
  the Language center: one row for the panel and one for each system, each
  read from the setting the application itself uses.
- A system that is not installed shows "Not installed" and no button.
- Opening the center only reads: no routine that changes anything runs.
- "Panel language only" writes the panel's setting and nothing else.
- The new Tainacan card changes WordPress's language only after a Yes.
- Every new text has Portuguese.
"""
import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kei_panel import languages
from kei_panel.bridge import TaskOutcome, installer_tasks
from kei_panel.i18n import Translator, install
from kei_panel.menus import SECTIONS, section

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'installer'
# What may run while the center is open: reads only (the backup status is the
# dashboard's, read when the panel starts).
READS = {'koha-languages', ('dspace-panel', 'operations', 'languages'), ('platform-backup-status', 'tainacan')}


def test_languages_stays_in_the_sidebar_as_the_center():
    sec = section('languages')
    assert sec.label == '🌍  Languages' and sec.sidebar and not sec.group
    assert sec.view == 'languages' and sec.title == '🌍 Language center'
    actions = [e.action for e in sec.entries]
    # The cards of before are all kept, with the panel's and Tainacan's.
    assert {'languages', 'lang-download', 'lang-activate', 'lang-list', 'dspace-languages'} <= set(actions)
    assert actions[0] == 'panel-language' and 'tainacan-language' in actions
    assert next(e for e in sec.entries if e.action == 'tainacan-language').requires == 'tainacan'
    assert not any(e.action.startswith('lang') for s in SECTIONS if s.id.endswith(('diagnostics', 'maintenance'))
                   for e in s.entries)


def run_center(monkeypatch, size=(160, 48), koha='1', tainacan='1', dspace='1', path=None):
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA', koha)
    monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN', tainacan)
    monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE', dspace)
    from textual.widgets import Button, Label

    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang='en', plain=False, demo=True))
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.5)
            calls = []
            real = app.bridge.task

            async def task(name, *args, **kwargs):
                calls.append((name, *args) if args else name)
                return await real(name, *args, **kwargs)
            app.bridge.task = task
            app.screen.action_show('languages', from_sidebar=True)
            await pilot.pause(0.5)
            view = app.screen.query_one('#view-languages')
            # The rows are read in the background: wait until each one is filled
            # (a slow machine takes longer), never a fixed time.
            for _ in range(300):
                if all(str(v.render()) != '…' for v in view.query('.lang-value')):
                    break
                await pilot.pause(0.1)
            rows = {}
            for row in view.query('.lang-row'):
                labels = [str(lb.render()) for lb in row.query(Label)]
                rows[row.id.removeprefix('lang-')] = (labels, row.query_one(Button).display)
            if path:
                app.save_screenshot(path)
            return rows, calls

    return asyncio.run(main())


def test_one_row_per_panel_and_system(monkeypatch):
    rows, calls = run_center(monkeypatch)
    assert list(rows) == ['panel', 'koha', 'tainacan', 'dspace']
    assert rows['koha'][0][1] == 'OPAC: pt-BR, en · Staff: pt-BR'
    assert rows['koha'][0][2] == 'Installed: en, pt-BR, es-ES'
    assert rows['tainacan'][0][1] == 'WordPress: Português (Brasil) (pt_BR)'
    assert rows['dspace'][0][1:] == ['Interface: pt-BR, en', 'Default: pt-BR']
    assert all(shown for _labels, shown in rows.values())
    # Reading only.
    assert set(calls) <= READS, calls


def test_a_missing_system_has_no_button(monkeypatch):
    rows, calls = run_center(monkeypatch, koha='0', tainacan='0', dspace='0')
    for key in ('koha', 'tainacan', 'dspace'):
        assert rows[key][0][1] == 'Not installed' and rows[key][1] is False
    assert rows['panel'][1] is True
    assert calls == []


def test_rows_from_what_each_application_keeps(tmp_path):
    conf = tmp_path / 'translation.conf'
    conf.write_text('OTHER=1\nKOHA_PANEL_LANG_FULL="pt-BR"\nKOHA_PANEL_LANG="pt"\n')
    assert languages.panel_code(conf) == 'pt-BR'
    assert languages.panel_code(tmp_path / 'none', 'en') == 'en'
    out = TaskOutcome()
    for line in ('@@result koha=installed', '@@result installed=en', '@@result opac=', '@@result staff='):
        out.feed(line)
    assert languages.koha_row(out).value == 'Database not ready yet'
    absent = TaskOutcome()
    absent.feed('@@result koha=absent')
    assert languages.koha_row(absent).button is False
    assert languages.koha_row(None).value == 'Not read'
    assert languages.tainacan_row('pt_BR; rm -rf /').value == 'Not recorded'
    assert languages.dspace_row({'active': 'bad'}).value == 'Not read'


def test_panel_language_only_writes_the_panel_setting(monkeypatch, tmp_path):
    import kei_panel.env as env
    from kei_panel.routines import tools
    conf = tmp_path / 'translation.conf'
    conf.write_text('KEEP=1\nKOHA_PANEL_LANG_FULL="pt-BR"\nKOHA_PANEL_LANG="pt"\n')
    monkeypatch.setattr(env, 'TRANSLATION_CONFIG', conf)
    answers = iter(['es-ES', True])
    exits = []

    async def push(screen):
        return next(answers)

    def no_task(*a, **k):
        raise AssertionError('no installer routine runs')
    app = SimpleNamespace(env=SimpleNamespace(installer=INSTALLER, lang='pt', demo=False), push_screen_wait=push,
                          exit=lambda return_code=None: exits.append(return_code),
                          bridge=SimpleNamespace(task=no_task))
    asyncio.run(tools.panel_language(app))
    assert exits == [tools.RESTART_CODE]
    assert conf.read_text() == 'KEEP=1\nKOHA_PANEL_LANG_FULL="es-ES"\nKOHA_PANEL_LANG="es"\n'
    # Back on the confirmation: nothing written, the panel stays.
    answers = iter(['en-GB', False])
    asyncio.run(tools.panel_language(app))
    assert exits == [tools.RESTART_CODE] and 'es-ES' in conf.read_text()


@pytest.mark.parametrize('confirm', [True, False])
def test_tainacan_language_only_after_yes(monkeypatch, confirm):
    from kei_panel.routines import common, platforms as rp
    ran = []

    async def run_task(app, title, name, *args, **kwargs):
        ran.append((name, *args))
        return SimpleNamespace(ok=True, cancelled=False, value=None)

    async def show_done(*a, **k):
        return None

    async def status():
        return {'platforms': [{'id': 'tainacan', 'supported': True, 'status': 'installed', 'lang': 'pt_BR'}]}
    monkeypatch.setattr(common, 'run_task', run_task)
    monkeypatch.setattr(common, 'show_done', show_done)
    answers = iter(['es_ES', confirm])

    async def push(screen):
        return next(answers)
    app = SimpleNamespace(push_screen_wait=push, bridge=SimpleNamespace(status=status), check_platforms=lambda: None)
    asyncio.run(rp.tainacan_language(app))
    assert ran == ([('tainacan-language', 'es_ES')] if confirm else [])


def test_the_installer_reads_and_validates():
    text = INSTALLER.read_text(encoding='utf-8')
    assert {'koha-languages', 'tainacan-language'} <= installer_tasks(INSTALLER)
    body = re.search(r'^        koha-languages\)\n(.*?);;', text, re.S | re.M).group(1)
    assert 'lang_pref_set' not in body and 'lang_activate' not in body and 'lang_download' not in body
    assert '"lang":%s' in text
    # The code chosen in the panel is checked again by the installer.
    assert all(languages.WP_LOCALE.match(code) for code, _name in languages.TAINACAN_LOCALES)
    assert "[[ \"$lang\" =~ ^[a-z]{2,3}(_[A-Z]{2})?$ ]]" in text


def test_the_tainacan_status_carries_its_language():
    from kei_panel import platforms
    raw = {'platforms': [{'id': 'tainacan', 'supported': True, 'status': 'installed', 'lang': 'es_ES'}]}
    assert platforms.tainacan_from_status(raw).lang == 'es_ES'
    raw['platforms'][0]['lang'] = '$(reboot)'
    assert platforms.tainacan_from_status(raw).lang == ''


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_new_texts_have_portuguese(pt):
    from kei_panel.menus import DESCRIPTIONS
    texts = [title for _k, title, _p in languages.ROWS] + list(languages.BUTTONS.values())
    texts += [section('languages').title, section('languages').prompt, DESCRIPTIONS['panel-language'],
              DESCRIPTIONS['tainacan-language'], 'Koha languages', 'Not recorded', 'Database not ready yet',
              'Installed: ${codes}', 'Default: ${code}', 'WordPress and the Tainacan plugin.',
              'Changing it here does not change Koha, Tainacan or DSpace.',
              'The language of this panel. Koha, Tainacan and DSpace keep theirs.',
              'Show this panel in ${name}? It closes and opens again in it; nothing else changes.',
              'The language of WordPress and of the Tainacan plugin, for visitors and administrators.']
    texts += [e.label for e in section('languages').entries]
    assert sorted(s for s in texts if pt(s) == s) == []
