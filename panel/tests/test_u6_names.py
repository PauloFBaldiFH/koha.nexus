"""U6 acceptance (study 12 and 13): the visible name of each installation.

- The name lives only in the instance registry: naming adopts the existing
  installation (its references, nothing moved) and renaming changes the
  name only. Databases, files, volumes and addresses stay as they are.
- Opening a screen never writes: "instance-names" only reads; a name is
  written by "instance-name" after OK.
- --status-json only gains "names"; an older status keeps the panel as it was.
- The name appears in the six places: sidebar, dashboard tabs, Add system,
  Backup center, Schedule center and the confirmations of a removal.
- Every new text has Portuguese.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from kei_panel import demo, names
from kei_panel.bridge import TaskOutcome, installer_tasks
from kei_panel.i18n import Translator, install

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'installer'
PANEL = ROOT / 'panel'


def test_the_registry_is_the_same_code_as_nexus_core():
    # One registry: the panel's copy is nexus_core's, byte for byte.
    assert (PANEL / 'kei_panel/instance_registry.py').read_bytes() == (ROOT / 'nexus_core/instances.py').read_bytes()


# --- the installer's helper (kei_panel/instance_names.py) ---------------------
@pytest.fixture
def server(tmp_path):
    """A disposable server: Koha site "library" and a Tainacan state."""
    root = tmp_path / 'root'
    conf = root / 'etc/koha/sites/library/koha-conf.xml'
    conf.parent.mkdir(parents=True)
    conf.write_text('<yazgfs><config><database>koha_library</database></config></yazgfs>\n')
    state = root / 'var/lib/koha-nexus/platforms/tainacan/state'
    state.parent.mkdir(parents=True)
    state.write_text('status=installed\nurl=http://192.168.0.20:8090\n')
    registry = tmp_path / 'registry'
    return root, registry


def cli(server, *args):
    root, registry = server
    env = {**os.environ, 'PYTHONPATH': str(PANEL), 'KEI_INSTANCES_SYSTEM_ROOT': str(root),
           'KEI_INSTANCES_REGISTRY': str(registry), 'PYTHONDONTWRITEBYTECODE': '1'}
    proc = subprocess.run([sys.executable, '-m', 'kei_panel.instance_names', *args], env=env,
                          capture_output=True, text=True, timeout=60)
    out = TaskOutcome()
    for line in proc.stderr.splitlines():
        out.feed(line)
    out.rc = proc.returncode
    return out, proc.stdout


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}


def test_reading_proposes_names_and_writes_nothing(server):
    root, registry = server
    before = snapshot(root)
    out, _ = cli(server, 'read', 'library')
    assert out.ok and out.lists['system'] == ['koha|proposed|library', 'tainacan|proposed|Tainacan']
    assert not registry.exists() and snapshot(root) == before
    _o, text = cli(server, 'json', 'library')
    assert json.loads(text) == {} and not registry.exists()


def test_naming_adopts_then_renames_only_the_name(server):
    root, registry = server
    before = snapshot(root)
    out, _ = cli(server, 'set', 'koha', 'library', '  Biblioteca Central ')
    assert out.ok and out.get('system') == 'koha|named|Biblioteca Central'
    records = list(registry.glob('*.json'))
    assert len(records) == 1
    first = json.loads(records[0].read_text())
    assert first['source_key'] == 'koha-native:library' and first['resources'] == {'native_site': 'library'}
    out, _ = cli(server, 'set', 'koha', 'library', 'Biblioteca Palotina')
    second = json.loads(records[0].read_text())
    assert out.ok and second['id'] == first['id'] and second['name'] == 'Biblioteca Palotina'
    assert {k: v for k, v in second.items() if k not in ('name', 'updated_at')} == \
        {k: v for k, v in first.items() if k not in ('name', 'updated_at')}
    # The installation itself is untouched.
    assert snapshot(root) == before
    out, _ = cli(server, 'read', 'library')
    assert out.lists['system'] == ['koha|named|Biblioteca Palotina', 'tainacan|proposed|Tainacan']
    _o, text = cli(server, 'json', 'library')
    assert json.loads(text) == {'koha': 'Biblioteca Palotina'}


def test_a_bad_name_or_a_missing_system_changes_nothing(server):
    _root, registry = server
    for args in (('set', 'koha', 'library', 'a\nb'), ('set', 'koha', 'library', 'x' * 121),
                 ('set', 'dspace', 'library', 'Repositório'), ('set', 'atom', 'library', 'Arquivo'),
                 ('set', 'koha', 'other', 'Outra')):
        out, _ = cli(server, *args)
        assert not out.ok and out.last('error'), args
    assert not list(registry.glob('*.json')) if registry.exists() else True


def test_an_unreadable_registry_keeps_status_valid(server):
    _root, registry = server
    registry.mkdir(mode=0o755)          # not private: refused, never trusted
    out, _ = cli(server, 'read', 'library')
    assert out.ok and out.get('registry') and 'koha|proposed|library' in out.lists['system']
    _o, text = cli(server, 'json', 'library')
    assert json.loads(text) == {}


def test_the_installer_wiring():
    text = INSTALLER.read_text(encoding='utf-8')
    assert {'instance-names', 'instance-name'} <= installer_tasks(INSTALLER)
    assert re.search(r'^        instance-names\)\s+kei_instance_names read ;;$', text, re.M)
    body = re.search(r'^kei_instance_names\(\) \{\n(.*?)^\}', text, re.S | re.M).group(1)
    assert 'cd /' in body and '"$INSTANCE"' in body
    # Only added to --status-json, last, and always valid JSON.
    status = re.search(r'^kei_status_json\(\) \{\n(.*?)^\}', text, re.S | re.M).group(1)
    assert status.rstrip().endswith("""printf '"names":%s}\\n' "$(kei_instance_names json 2>/dev/null || printf '{}')\"""")


# --- what the panel shows -------------------------------------------------------
def test_names_from_status():
    assert names.from_status({}) == {} and names.from_status({'names': []}) == {}
    raw = {'names': {'koha': ' Biblioteca Central ', 'dspace': 'a\x1bb', 'atom': 'X', 'tainacan': ''}}
    known = names.from_status(raw)
    assert known == {'koha': 'Biblioteca Central'}
    assert names.label(known, 'koha') == 'Biblioteca Central · Koha' and names.label(known, 'dspace') == 'DSpace'
    assert names.short(known, 'tainacan') == 'Tainacan'
    assert names.joined(known, ('koha', 'tainacan'), 'Koha and Tainacan') == 'Biblioteca Central + Tainacan'
    assert names.joined({}, ('koha', 'tainacan'), 'Koha and Tainacan') == 'Koha and Tainacan'
    # The system's own name is no name.
    assert names.label({'koha': 'Koha'}, 'koha') == 'Koha'


@pytest.fixture
def demo_names(monkeypatch):
    monkeypatch.setattr(demo, 'DEMO_NAMES', {})
    yield demo.DEMO_NAMES


def run_panel(monkeypatch, named='1', show=None, path=None):
    for key in ('KOHA', 'TAINACAN', 'DSPACE'):
        monkeypatch.setenv(f'KEI_PANEL_DEMO_{key}', '1')
    monkeypatch.setenv('KEI_PANEL_DEMO_NAMES', named)
    from textual.widgets import OptionList, Select, Static, TabbedContent

    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.routines import instances

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang='en', plain=False, demo=True))
        async with app.run_test(size=(160, 48)) as pilot:
            # The dashboard reads the status in the background: wait for it.
            for _ in range(300):
                tabs = app.screen.query('#dash-tabs')
                if tabs and app.screen.query_one('#dash-platform-koha').query_one('.card-title').render() \
                        and (app.instance_names or named != '1') and not app.screen.query('#status-loader').first().display:
                    break
                await pilot.pause(0.1)
            await pilot.pause(0.3)
            sidebar = app.screen.query_one('#sidebar', OptionList)
            seen = {'sidebar': [str(sidebar.get_option_at_index(i).prompt) for i in range(sidebar.option_count)]}
            tabs = app.screen.query_one('#dash-tabs', TabbedContent)
            seen['tabs'] = [str(tabs.get_tab(f'dash-tab-{k}').label) for k in ('koha', 'tainacan', 'dspace')]
            seen['cards'] = [str(app.screen.query_one(f'#dash-platform-{k}').query_one('.card-title').render())
                             for k in ('koha', 'tainacan', 'dspace')]
            seen['add'] = [text for _k, text in instances.add_options(app)]
            if show == 'backups':
                app.screen.action_show('koha-backups', from_sidebar=True)
                await pilot.pause(0.5)
                view = app.screen.query_one('#view-backups')
                for _ in range(300):
                    if view.query('#bk-plans Static') and view.plans:
                        break
                    await pilot.pause(0.1)
                select = view.query_one('#bk-scope', Select)
                seen['scopes'] = [str(o[0]) for o in select._options]
                seen['plans'] = [row.name for row in view.plans]
            if show == 'schedules':
                app.screen.action_show('schedules', from_sidebar=True)
                await pilot.pause(0.5)
                view = app.screen.query_one('#view-schedules')
                for _ in range(300):
                    if view.query('#sc-rows .sc-description'):
                        break
                    await pilot.pause(0.1)
                await pilot.pause(0.3)
                seen['rows'] = [str(s.render()) for s in view.query('#sc-rows .sc-description')]
                seen['filter'] = [str(o[0]) for o in view.query_one('#sc-platform', Select)._options]
            if path:
                app.save_screenshot(path)
            return seen

    return asyncio.run(main())


def test_the_names_in_the_sidebar_tabs_and_add_system(monkeypatch, demo_names):
    seen = run_panel(monkeypatch)
    assert '▾ 📚 Biblioteca Central · Koha' in seen['sidebar']
    assert any(p.endswith('Museu Municipal · Tainacan') for p in seen['sidebar'])
    assert any(p.endswith('Repositório Institucional · DSpace') for p in seen['sidebar'])
    assert seen['tabs'] == ['Biblioteca Central', 'Museu Municipal', 'Repositório Institucional']
    assert seen['cards'] == ['Biblioteca Central · Koha', 'Museu Municipal · Tainacan',
                             'Repositório Institucional · DSpace']
    assert any('Installed: Biblioteca Central · open' in text for text in seen['add'])


def test_without_names_nothing_changes(monkeypatch, demo_names):
    seen = run_panel(monkeypatch, named='0')
    assert any(p.endswith('📚 Koha (library)') for p in seen['sidebar'])
    assert seen['tabs'] == ['Koha', 'Tainacan', 'DSpace'] and seen['cards'] == ['Koha', 'Tainacan', 'DSpace']
    assert all('Installed · open' in text for text in seen['add'])


def test_the_names_in_backups(monkeypatch, demo_names):
    seen = run_panel(monkeypatch, show='backups')
    assert 'Biblioteca Central · Koha' in seen['scopes'] and 'Full Nexus' in seen['scopes']
    assert 'Biblioteca Central + Museu Municipal' in seen['scopes']
    assert seen['plans'] and all(name.startswith('Biblioteca Central · ') for name in seen['plans'])


def test_the_names_in_schedules(monkeypatch, demo_names):
    seen = run_panel(monkeypatch, show='schedules')
    assert any(row.split('\n')[0].startswith('● Biblioteca Central · ') for row in seen['rows'])
    assert 'Biblioteca Central · Koha' in seen['filter']


# --- naming: reads first, writes after OK ---------------------------------------
def fake_app(answers, systems, installed=('koha', 'tainacan', 'dspace')):
    calls, ran, shown = [], [], {}

    async def task(name, *args, **kwargs):
        calls.append((name, *args))
        out = TaskOutcome()
        for row in systems:
            out.feed('@@result system=' + row)
        return out

    async def push(screen):
        shown.setdefault('screens', []).append(type(screen).__name__)
        if type(screen).__name__ == 'InputScreen':
            shown.setdefault('values', []).append(screen._value)
        return next(answers)

    app = SimpleNamespace(bridge=SimpleNamespace(task=task, has_task=lambda n: True), push_screen_wait=push,
                          platform_ready=lambda k: k in installed, instance_names={},
                          notify=lambda *a, **k: shown.setdefault('notes', []).append(a[0]))
    app.names_seen = lambda status: setattr(app, 'instance_names', names.from_status(status))
    return app, calls, ran, shown


@pytest.fixture
def no_run(monkeypatch):
    from kei_panel.routines import common
    ran = []

    async def run_task(app, title, name, *args, **kwargs):
        ran.append((name, *args))
        out = TaskOutcome()
        out.feed(f'@@result system={args[0]}|named|{args[1]}')
        return SimpleNamespace(ok=True, cancelled=False, value=out)
    monkeypatch.setattr(common, 'run_task', run_task)
    return ran


def test_naming_reads_then_writes_after_ok(no_run):
    from kei_panel.routines import instances
    systems = ['koha|proposed|library', 'tainacan|named|Museu Municipal']
    # Back on the choice: only read.
    app, calls, _r, _s = fake_app(iter([None]), systems)
    asyncio.run(instances.name_instances(app))
    assert calls == [('instance-names',)] and no_run == []
    # Cancel on the name: only read.
    app, calls, _r, _s = fake_app(iter(['koha', None]), systems)
    asyncio.run(instances.name_instances(app))
    assert no_run == []
    # The same name again: nothing written.
    app, calls, _r, _s = fake_app(iter(['tainacan', 'Museu Municipal']), systems)
    asyncio.run(instances.name_instances(app))
    assert no_run == []
    # A name: written once, shown at once.
    app, calls, _r, shown = fake_app(iter(['koha', ' Biblioteca Central ']), systems)
    asyncio.run(instances.name_instances(app))
    assert no_run == [('instance-name', 'koha', 'Biblioteca Central')]
    assert app.instance_names == {'koha': 'Biblioteca Central'}
    assert shown['notes'] == ['Name saved: Biblioteca Central · Koha']
    # Not named yet: "Koha" is proposed, never the site's "library".
    assert shown['values'] == ['Koha']


def test_naming_offers_only_installed_systems(no_run):
    from kei_panel.routines import instances
    # One system installed: no choice, straight to its name.
    app, _c, _r, shown = fake_app(iter(['Repositório']), ['koha|proposed|library', 'dspace|proposed|DSpace'],
                                  installed=('dspace',))
    asyncio.run(instances.name_instances(app))
    assert shown['screens'] == ['InputScreen'] and no_run == [('instance-name', 'dspace', 'Repositório')]
    assert instances.check_name('a\tb') and not instances.check_name('Biblioteca Central')


def test_the_demo_names_and_status(monkeypatch, demo_names):
    from kei_panel.bridge import Bridge
    from kei_panel.env import PanelEnv
    monkeypatch.setenv('KEI_PANEL_DEMO_NAMES', '0')
    bridge = Bridge(PanelEnv(installer=INSTALLER, lang='en', plain=False, demo=True))
    assert asyncio.run(bridge.status())['names'] == {}
    out = asyncio.run(bridge.task('instance-name', 'koha', 'Biblioteca Central'))
    assert out.lists.get('system', [out.get('system')]) == ['koha|named|Biblioteca Central']
    assert asyncio.run(bridge.status())['names'] == {'koha': 'Biblioteca Central'}


# --- removals confirm by name ---------------------------------------------------
def removal_app(answers, named):
    async def push(screen):
        pushed.append((type(screen).__name__, getattr(screen, '_title', '')))
        return next(answers)
    pushed = []
    app = SimpleNamespace(push_screen_wait=push, instance_names=named)
    return app, pushed


def test_dspace_removal_types_the_name(monkeypatch):
    from kei_panel.routines import dspace
    sent = []

    async def operation(app, name, request, *a):
        sent.append((name, request))
    monkeypatch.setattr(dspace, 'operation', operation)
    named = {'dspace': 'Repositório Institucional'}
    app, pushed = removal_app(iter(['purge', 'DSpace']), named)
    asyncio.run(dspace.remove(app))
    assert sent == [] and pushed[0][1] == 'Remove “Repositório Institucional” (DSpace)'
    app, _p = removal_app(iter(['purge', 'Repositório Institucional']), named)
    asyncio.run(dspace.remove(app))
    # The installer's confirmation word stays the same.
    assert sent == [('remove', {'purge': True, 'erase': 'DSpace'})]
    sent.clear()
    app, _p = removal_app(iter(['purge', 'DSpace']), {})
    asyncio.run(dspace.remove(app))
    assert sent == [('remove', {'purge': True, 'erase': 'DSpace'})]


def test_tainacan_removal_types_the_name(monkeypatch):
    from kei_panel.routines import common
    ran = []

    async def run_task(app, title, name, *args, **kwargs):
        ran.append((title, name, *args))
        return SimpleNamespace(ok=True, cancelled=False, value=TaskOutcome())

    async def show_done(*a, **k):
        return None
    monkeypatch.setattr(common, 'run_task', run_task)
    monkeypatch.setattr(common, 'show_done', show_done)
    from kei_panel.routines import platforms as rp
    named = {'tainacan': 'Museu Municipal'}
    app, _p = removal_app(iter(['delete', True, 'Museu']), named)
    asyncio.run(rp.tainacan_uninstall(app))
    assert ran == []
    app, _p = removal_app(iter(['delete', True, 'Museu Municipal']), named)
    asyncio.run(rp.tainacan_uninstall(app))
    assert ran == [('Uninstall “Museu Municipal” (Tainacan)', 'tainacan-uninstall', 'delete')]
    # Keeping the data asks no name.
    ran.clear()
    app, _p = removal_app(iter(['keep', True]), named)
    asyncio.run(rp.tainacan_uninstall(app))
    assert ran == [('Uninstall “Museu Municipal” (Tainacan)', 'tainacan-uninstall', 'keep')]


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
    texts = ['🔖  Name the installations', 'Name the installations', DESCRIPTIONS['instance-names'],
             'Installed: ${name} · open', 'no name yet', 'Name:', 'Name saved: ${name}',
             'Use 1 to 120 letters, numbers or signs, without line breaks.',
             "This server's installer is older than the panel: update it (Update panel) to name the installations.",
             'No installed system was found to name.', 'The names could not be read.',
             'The name is shown in this panel: in the sidebar, the tabs, backups, schedules and confirmations. '
             'Only the name changes: databases, files, services and addresses stay as they are.',
             "A name for this ${system}, such as the institution's or the collection's. Only the name changes: "
             "its database, files, services and addresses stay as they are.",
             'Uninstall “${name}” (Tainacan)', 'Type the name “${name}” to confirm deleting its data.',
             'Remove “${name}” (DSpace)', 'Type the name “${name}” to confirm permanent removal of its data.',
             'The panel is not installed here; the names cannot be read.']
    assert sorted(s for s in texts if pt(s) == s) == []
