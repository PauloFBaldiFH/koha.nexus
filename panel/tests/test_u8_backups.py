"""U8 acceptance (study 7.5, 7.6): the full backup says what comes back;
the Backup center keeps fixed texts and settings in collapsible sections and
shows the shared backup key in one place.

- The full backup shows one short line and, open from the start, "What this
  backup brings back": comes back automatically, loaded during recovery,
  kept for review, must be ready on the destination, not included.
- The table is true to the recovery code: what is applied, loaded and only
  kept for review.
- Compression and fixed texts are collapsed, with the current compression
  in the title.
- The key and its kit are one box, for Tainacan, DSpace, sets and the full
  backup; no system has its own key card in the center; Koha alone has none.
- Opening the center still only reads.
- Every new text has Portuguese.
"""
import asyncio
import re
from pathlib import Path

import pytest

from kei_panel.i18n import Translator, install
from kei_panel.routines import nexus_backup
from kei_panel.views import backups
from kei_panel.widgets.cards import ActionCard

from test_u2_backups import demo, make_app, open_center, read_done  # noqa: F401 - fixtures

ROOT = Path(__file__).resolve().parents[2]
READS = {'platform-backup-status', 'info', 'cloud-status', 'cloud-list', 'set-schedule-status', 'nexus-full',
         'dspace-panel'}


def test_the_table_has_the_five_rows_of_the_study():
    assert [title for title, _ in nexus_backup.BRINGS_BACK] == [
        'Comes back automatically', 'Loaded during recovery', 'Kept for review, not turned on',
        'Must be ready on the destination', 'Not included']
    text = backups.brings_back_text().plain
    assert text.startswith('Comes back automatically\n  the data of Koha, Tainacan and DSpace')


def test_the_table_is_true_to_the_recovery_code():
    code = (ROOT / 'platforms' / 'nexus' / 'recovery.py').read_text(encoding='utf-8')
    rows = dict(nexus_backup.BRINGS_BACK)
    # Applied: theme, panel language, backup plans with no time; the key imported; images loaded.
    assert "role=='panel-settings'" in code and "role=='panel-language'" in code
    assert "data['time']=''" in code and "'import-key'" in code and 'self._load_images(session)' in code
    assert 'backup plans, turned off' in rows['Comes back automatically']
    # Everything else is only a reference, never written to the destination.
    assert "else:references.append(role)" in code
    installer = (ROOT / 'installer').read_text(encoding='utf-8')
    for role in ("'instance-registry'", "'cloud-connections'", "'cloudflare-files'", "'docker-settings'", "'panel-code'"):
        assert role in installer, role
    assert "'addresses_preserved':True" in code
    for word in ('schedules', 'cloud connections', 'Cloudflare', 'Docker', 'addresses'):
        assert word in rows['Kept for review, not turned on'], word
    for field in ("'package_version'", "'release_sha256'", "'url'", "'images'"):
        assert field in code
    assert "manifest['system']!=current['system']" in code


def state(view):
    return {
        'cards': [c.entry.action for c in view.query(ActionCard) if c.display and not c.has_class('bk-key-card')],
        'key': bool(view.query_one('#bk-key').display),
        'key_cards': [c.entry.action for c in view.query('.bk-key-card') if c.display],
        'key_line': str(view.query_one('#bk-key-state').render()),
    }


@pytest.mark.parametrize('scope', ['koha', 'tainacan', 'dspace', 'both', 'nexus'])
def test_one_key_box(demo, scope):
    async def run():
        app = make_app()
        calls = []
        real = app.bridge.task

        async def task(name, *args, **kwargs):
            calls.append(name)
            return await real(name, *args, **kwargs)
        app.bridge.task = task
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(.5)
            view = await open_center(app, pilot, scope)
            await read_done(pilot, view)
            await pilot.pause(.3)
            return state(view), set(calls)

    st, calls = asyncio.run(run())
    assert not set(st['cards']) & backups.KEY_ACTIONS
    if scope == 'koha':
        assert not st['key']
    else:
        assert st['key'] and st['key_line'].startswith('Backup key: ')
        assert len(st['key_cards']) == 1 and st['key_cards'][0] in ('pbackup-setup', 'pbackup-kit')
    assert calls <= READS, calls


def test_full_backup_screen(demo):
    async def run():
        app = make_app()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(.5)
            view = await open_center(app, pilot, 'nexus')
            await read_done(pilot, view)
            await pilot.pause(.3)
            from textual.widgets import Collapsible
            back = view.query_one('#bk-nexus-back', Collapsible)
            codec = view.query_one('#bk-nexus-codec-more', Collapsible)
            table = str(view.query_one('#bk-nexus-table').render())
            texts = [str(s.render()) for s in view.query('#bk-nexus Static') if s.display]
            # Before U8 the full backup's state cards had no height: never seen.
            heights = [view.query_one(f'#bk-nexus-{k}').region.height for k in ('age', 'size', 'sessions')]
            return back.collapsed, codec.collapsed, codec.title, table, texts, heights

    back, codec, title, table, texts, heights = asyncio.run(run())
    assert min(heights) >= 3
    assert not back and codec
    assert title.startswith('Compression: ')
    assert 'Not included' in table and 'Must be ready on the destination' in table
    assert texts[0] == nexus_backup.SHORT_NOTE
    assert not any(nexus_backup.NOTE in text for text in texts)


def test_compression_is_collapsed_with_its_value(demo):
    async def run():
        app = make_app()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(.5)
            view = await open_center(app, pilot, 'koha')
            for _ in range(100):
                if not view.query_one('#bk-codec').disabled:
                    break
                await pilot.pause(.1)
            from textual.widgets import Collapsible
            box = view.query_one('#bk-codec-more', Collapsible)
            return box.collapsed, box.title

    collapsed, title = asyncio.run(run())
    assert collapsed and title == 'Compression: Gzip (.sql.gz)'


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_new_texts_have_portuguese(pt):
    texts = [nexus_backup.SHORT_NOTE, backups.KEY_NOTE, 'What this backup brings back', 'Backup key and recovery kit',
             'What these backups contain', 'What is encrypted', 'Compression', 'Backup key']
    texts += [v for row in nexus_backup.BRINGS_BACK for v in row]
    assert [s for s in texts if pt(s) == s] == []
    assert not re.search(r'\$\{', pt(backups.KEY_NOTE))
