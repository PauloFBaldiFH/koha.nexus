"""U2 acceptance: the Backup center shows its actions first.

- The action cards are drawn as the center opens, right after the platform
  choice, usable while the state is read, and the first one is on screen
  without scrolling at 80x24 and 160x48.
- Reading never moves them: the first card stays where it was.
- A read that fails keeps every action and says what could not be read.
- The automatic backups are not rebuilt when nothing changed.
- Removing an instance says that Koha removal is not available yet.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from kei_panel import backup_center
from kei_panel.routines import instances
from kei_panel.widgets.cards import ActionCard

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def demo(monkeypatch):
    for name in ('KOHA', 'TAINACAN', 'DSPACE'):
        monkeypatch.setenv('KEI_PANEL_DEMO_' + name, '1')


def make_app():
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    return KohaPanelApp(PanelEnv(installer=None, lang='en', plain=False, demo=True))


async def open_center(app, pilot, scope):
    from kei_panel.views.backups import BackupCenterView
    app.backup_scope = scope
    app.screen.action_show('backups')
    await pilot.pause(.05)
    view = app.screen.query_one(BackupCenterView)
    view.set_scope(scope)
    return view


def shown(view):
    return [c for c in view.query(ActionCard) if c.display]


async def read_done(pilot, view):
    for _ in range(150):
        if not view.query_one('#platform-loader').display:
            return
        await pilot.pause(.1)
    raise AssertionError('the backup state was never read')


@pytest.mark.parametrize('size', [(80, 24), (160, 48)])
@pytest.mark.parametrize('scope', ['koha', 'dspace', 'both'])
def test_actions_are_drawn_first_and_do_not_move_while_reading(demo, monkeypatch, size, scope):
    from kei_panel.views.backups import BackupCenterView
    original = BackupCenterView.read_facts
    gates = []           # made inside the loop: Python 3.9 binds an Event to it

    async def slow(self):
        await gates[0].wait()
        return await original(self)
    monkeypatch.setattr(BackupCenterView, 'read_facts', slow)

    async def run():
        gates.append(asyncio.Event())
        gate = gates[0]
        app = make_app()
        async with app.run_test(size=size) as pilot:
            await pilot.pause(.5)
            view = await open_center(app, pilot, scope)
            await pilot.pause(.3)
            cards = shown(view)
            assert cards and not any(c.disabled for c in cards)
            assert view.query_one('#bk-wait').display
            first = cards[0]
            top = first.region.y
            assert view.region.y <= top < view.region.bottom - 2      # visible without scrolling
            gate.set()
            await read_done(pilot, view)
            await pilot.pause(.3)
            after = shown(view)
            assert after[0] is first and first.region.y == top          # not moved by the read
            assert not any(c.disabled for c in after)
            assert 'State read at' in str(view.query_one('#bk-wait').render())
    asyncio.run(run())


def test_a_failed_read_keeps_the_actions_and_says_what_failed(demo, monkeypatch):
    # Before U2 an exception in any read skipped show(): every card stayed
    # hidden until Refresh (study 2.1, cause 3).
    from kei_panel.views.backups import BackupCenterView

    async def broken(self):
        raise RuntimeError('installer did not answer')
    monkeypatch.setattr(BackupCenterView, '_load_koha', broken)

    async def run():
        app = make_app()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(.5)
            view = await open_center(app, pilot, 'koha')
            await read_done(pilot, view)
            await pilot.pause(.3)
            cards = shown(view)
            assert cards and not any(c.disabled for c in cards)
            wait = view.query_one('#bk-wait')
            assert wait.display and wait.has_class('-warn')
            assert 'Koha backups' in str(wait.render())
    asyncio.run(run())


def test_unchanged_automatic_backups_are_not_rebuilt(demo):
    row = backup_center.PlanRow('Nightly', 'this server', 'Daily at 23:00', '7', 'no', 'No run recorded')

    async def run():
        app = make_app()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(.5)
            view = await open_center(app, pilot, 'koha')
            await read_done(pilot, view)
            view._draw_plans([row])
            await pilot.pause(.1)
            before = list(view.query_one('#bk-plans').children)
            view._draw_plans([row])
            await pilot.pause(.1)
            assert list(view.query_one('#bk-plans').children) == before
            assert '(1)' in str(view.query_one('#bk-plans-title').render())
    asyncio.run(run())


@pytest.mark.parametrize('containers', [True, False])
def test_removing_an_instance_says_koha_removal_is_not_available_yet(containers):
    seen = []

    async def screen(s):
        seen.append(s)
        return None
    ready = {'koha': True, 'tainacan': containers, 'dspace': False}
    app = SimpleNamespace(platform_ready=lambda p: ready.get(p, False), push_screen_wait=screen)
    asyncio.run(instances.remove(app))
    text = ' '.join(str(v) for v in vars(seen[0]).values() if isinstance(v, str))
    assert 'Koha: removal is not available in the panel yet' in text


def test_new_texts_have_portuguese(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    from kei_panel.views.backups import READ_FAILED, READING
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    pt = i18n.Translator('pt', ROOT / 'installer', False)
    texts = [READING, READ_FAILED, instances.KOHA_REMOVAL, 'State and settings', 'Show:', 'State read at ${time}.',
             'server state', 'Koha backups', 'Tainacan backups', 'joint backup', 'DSpace backups', 'full backup',
             'DSpace backup plans']
    assert [s for s in texts if pt(s) == s] == []
