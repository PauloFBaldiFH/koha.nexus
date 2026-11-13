"""U5 acceptance (study 17.1 and 7.2): one navigation pattern for every system.

- Each platform group starts with the same standard items, in the same
  order: Administrative access, Addresses and access, Backups and schedules,
  Diagnosis and maintenance; its own tools come after a "tools" divider.
- Every section of before keeps its name, shortcut and place; Appearance and
  AI stay two entries; there is no "More Koha tools" drawer.
- "Backups and schedules" opens the Backup center filtered by that system.
- "Add system" lists every system, the installed ones too: an installed one
  opens its page, a missing one shows what it is and needs before Install…
- Opening these screens changes nothing on the server.
- Every new text has Portuguese.
"""
import asyncio
from pathlib import Path

import pytest

from kei_panel import menus
from kei_panel.i18n import Translator, install, load_cache
from kei_panel.menus import SECTIONS, children, section

ROOT = Path(__file__).resolve().parents[2]
STANDARD = ['🔐  Administrative access', '🌐  Addresses and access', '💾  Backups and schedules']
KOHA_TOOLS = ['import', 'library', 'z3950', 'ai', 'opac', 'hub', 'search', 'settings', 'koha-security']
# The shortcuts of before (study 6 and 17.1): none moves or disappears.
KEYS = {'d': 'dashboard', 'k': 'koha', 'i': 'import', 'l': 'library', 'z': 'z3950', 'a': 'ai', 'o': 'opac',
        'm': 'hub', 'g': 'tainacan', 'j': 'dspace', 'b': 'backups', 's': 'schedules', 'x': 'security',
        'v': 'vpn', 'p': 'infra', 'h': 'enrich-auth', 'n': 'ondemand', 't': 'database'}


@pytest.mark.parametrize('group, maintenance', [('koha', 'diagnostics'), ('tainacan', 'tainacan-maintenance'),
                                                ('dspace', 'dspace-maintenance')])
def test_every_group_starts_with_the_standard_items(group, maintenance):
    rows = children(group)
    assert [s.label for s in rows[:3]] == STANDARD
    assert rows[3].id == maintenance
    assert not any(s.tool for s in rows[:4])
    # Its own tools only after the standard items.
    first_tool = next((i for i, s in enumerate(rows) if s.tool), len(rows))
    assert all(s.tool for s in rows[first_tool:])


def test_koha_tools_keep_their_names_and_keys():
    rows = [s.id for s in children('koha') if s.tool]
    assert rows == KOHA_TOOLS                                   # AI and Appearance stay two entries
    assert 'koha-more' not in {s.id for s in SECTIONS}
    assert section('opac').label == '🎨  OPAC and Staff Appearance' and section('ai').label == '🤖  AI'
    assert {s.key: s.id for s in SECTIONS if s.key} == KEYS


def test_backups_and_schedules_opens_the_center_for_its_system():
    for group in menus.GROUPS:
        row = section(group + '-backups')
        assert row.opens == 'backups' and row.group == group and not row.entries


def test_the_standard_items_gather_existing_cards_only():
    # Shortcuts to routines that already exist: no new routine, nothing moved out.
    # Later PRs of the plan add their own routine here, named below.
    from kei_panel import routines
    added_later = {'koha-access': 'U10, One port or two (study 16.1)'}
    for sid in ('koha-admin', 'koha-addresses', 'tainacan-admin', 'tainacan-addresses', 'dspace-admin-access',
                'dspace-addresses'):
        for entry in section(sid).entries:
            assert routines.has(entry.action), entry.action
            if entry.action in added_later:
                continue
            others = [s.id for s in SECTIONS if s.id != sid and entry.action in {e.action for e in s.entries}]
            assert others, f'{entry.action} lives only in {sid}'


def test_the_sidebar_draws_the_tree_and_opens_the_filtered_center(monkeypatch):
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA', '1')
    monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN', '1')
    from textual.widgets import ContentSwitcher, OptionList

    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang='en', plain=False, demo=True))
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.5)
            sidebar = app.screen.query_one('#sidebar', OptionList)
            ids = [sidebar.get_option_at_index(i).id for i in range(sidebar.option_count)]
            calls = []
            real = app.bridge.task

            async def task(name, *args, **kwargs):
                calls.append(name)
                return await real(name, *args, **kwargs)
            app.bridge.task = task
            for sid in ('koha-admin', 'koha-addresses', 'tainacan-admin', 'tainacan-addresses'):
                app.screen.action_show(sid, from_sidebar=True)
                await pilot.pause(0.3)
                assert app.screen.query_one('#views', ContentSwitcher).current == f'view-{sid}'
            app.screen.action_show('tainacan-backups', from_sidebar=True)
            await pilot.pause(0.6)
            shown = app.screen.query_one('#views', ContentSwitcher).current
            scope = app.screen.query_one('#view-backups').scope
            highlighted = sidebar.get_option_at_index(sidebar.highlighted).id
            return ids, shown, scope, highlighted, calls

    ids, shown, scope, highlighted, calls = asyncio.run(main())
    koha = ids[ids.index('koha') + 1:ids.index('tainacan')]
    assert koha[:4] == ['koha-admin', 'koha-addresses', 'koha-backups', 'diagnostics']
    assert koha[4] == 'sidebar-tools-koha' and koha[5:] == KOHA_TOOLS
    assert ids[1] == 'instances'
    assert (shown, scope, highlighted) == ('view-backups', 'tainacan', 'tainacan-backups')
    # Reading only: no routine that changes the server ran.
    changing = {'tainacan-install', 'tainacan-uninstall', 'tainacan-address', 'admin-password', 'admin-create'}
    assert not changing & set(calls)


def test_the_tools_divider_cannot_be_chosen():
    from types import SimpleNamespace
    from kei_panel.screens.main import MainScreen
    screen = SimpleNamespace(expanded={'koha'})
    # set_group ignores the dividers (no group named "sidebar-tools-koha").
    MainScreen.set_group(screen, 'sidebar-tools-koha', False)
    assert screen.expanded == {'koha'}


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_add_system_lists_every_system(pt):
    from types import SimpleNamespace
    from kei_panel.routines import instances
    rows = instances.add_options(SimpleNamespace(platform_ready=lambda p: p == 'koha'))
    assert [k for k, _l in rows] == ['koha', 'tainacan', 'dspace']
    assert rows[0][1].endswith('Instalado · abrir') and rows[2][1].endswith('Não instalado')


def test_new_texts_have_portuguese(pt):
    from kei_panel.routines import instances
    texts = STANDARD + ['➕  Add system', 'tools', 'Add system', 'Installed · open', 'Not installed',
                        'What it is', 'When installing', 'Requirements', 'Install…',
                        'Each system can be installed once on this server. Choose one to see what it does and what '
                        'it needs.',
                        'Nothing is changed here. Install… starts the installation, which shows its own checks and '
                        'questions first.']
    texts += [x for _i, *rest in instances.ABOUT.values() for x in rest]
    assert sorted(s for s in texts if pt(s) == s) == []
    cache = load_cache(ROOT / 'lang' / 'pt.cache')
    assert all(cache.get(s.label) for s in SECTIONS if s.id.endswith(('-admin', '-addresses', '-backups')))
