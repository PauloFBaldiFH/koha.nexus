"""Status failures do not erase local health or disable recovery tools."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import time

import pytest
from textual.widgets import Label

from kei_panel.app import KohaPanelApp
from kei_panel.bridge import Bridge, BridgeError, decode_status_output
from kei_panel.env import PanelEnv
from kei_panel import health, platforms
from kei_panel.views.dashboard import DashboardView
from kei_panel.widgets.cards import StatusCard

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('response', [
    '{"schema":1,"state":"ok"}',
    '\n  {"schema":1,\n"state":"ok"}\n',
    'Preparing...\n{"schema":1,"state":"stopped"}\nLegacy notice\n{\n"schema":1,\n"state":"ok"\n}\n',
])
def test_decoder_accepts_complete_status_with_legacy_preamble(response):
    assert decode_status_output(response)['state'] == 'ok'


@pytest.mark.parametrize('response', ['', 'not JSON', '{"schema":1} trailing',
                                           '{"schema":1,\n"platforms": [\n{"id":"dspace"}',
                                           '{"schema":1, "state":', '[{"schema":1}]'])
def test_decoder_rejects_truncated_status_instead_of_using_nested_fragment(response):
    with pytest.raises(BridgeError):
        decode_status_output(response)


def test_real_dspace_serializer_roundtrips_into_panel(tmp_path):
    """Exercise the actual Bash producers and async panel reader together.

    Only service discovery is doubled: the real serializer used to add an
    interior newline exactly when state.json existed, breaking Bridge.status.
    """
    source = (REPO / 'installer').read_text()
    def function(name):
        start = source.index(name + '() {\n')
        return source[start:source.index('\n}\n', start) + 3]
    state = tmp_path / 'dspace'
    script = tmp_path / 'status.sh'
    script.write_text('''#!/bin/bash
KEI_PLATFORMS_PLANNED=atom
KEI_DSPACE_DIR="'''+str(state)+'''"
json_str() { printf '"%s"' "$1"; }
is_koha_installed() { return 1; }
kei_tainacan_json() { printf '{"id":"tainacan","supported":true,"detected":false}'; }
kei_dspace_runtime() { printf '{"status":"installed","phase":"ready","services":{"ui":"running"}}'; }
'''+function('kei_dspace_json')+function('kei_platforms_json')+'''
printf '{"schema":1,"platforms":%s}\n' "$(kei_platforms_json)"
''')
    bridge = Bridge(PanelEnv(installer=script, lang='en', plain=True))
    for present in (False, True):
        if present:
            state.mkdir(); (state / 'state.json').write_text('{}')
        raw = subprocess.check_output(['bash', str(script)], text=True)
        assert len(raw.splitlines()) == 1, 'machine status must remain compact for older clients'
        result = asyncio.run(bridge.status())
        assert result == json.loads(raw)
        dspace = next(x for x in result['platforms'] if x['id'] == 'dspace')
        assert dspace['detected'] is present
        if present:
            assert dspace['detail']['status'] == 'installed'


def test_status_timeout_kills_its_process_group_and_retry_works(tmp_path, monkeypatch):
    from kei_panel import bridge as module
    monkeypatch.setattr(module, 'STATUS_TIMEOUT', 0.4)
    pids = tmp_path / 'pids'
    script = tmp_path / 'slow.sh'
    script.write_text('sleep 60 &\nprintf "%s %s" "$$" "$!" > "'+str(pids)+'"\nwait\n')
    bridge = Bridge(PanelEnv(installer=script, lang='en', plain=True))
    started = time.monotonic()
    with pytest.raises(BridgeError, match='timed out'):
        asyncio.run(bridge.status())
    assert time.monotonic() - started < 4
    for pid in pids.read_text().split():
        stat = Path('/proc') / pid / 'stat'
        assert not stat.exists() or stat.read_text().split()[2] == 'Z'
    script.write_text('printf \'{"schema":1,"state":"ok"}\\n\'\n')
    assert asyncio.run(bridge.status())['state'] == 'ok'


def test_status_cancellation_reaps_children(tmp_path):
    pids = tmp_path / 'cancel-pids'
    script = tmp_path / 'slow.sh'
    script.write_text('sleep 60 &\nprintf "%s %s" "$$" "$!" > "'+str(pids)+'"\nwait\n')
    async def exercise():
        bridge = Bridge(PanelEnv(installer=script, lang='en', plain=True))
        task = asyncio.create_task(bridge.status())
        for _ in range(100):
            if pids.exists(): break
            await asyncio.sleep(.01)
        assert pids.exists()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(exercise())
    for pid in pids.read_text().split():
        stat = Path('/proc') / pid / 'stat'
        assert not stat.exists() or stat.read_text().split()[2] == 'Z'


def test_unknown_state_preserves_diagnosis_without_offering_reinstall():
    facts = platforms.Facts(status={}, has_task=lambda task: True)
    for action in ('dspace-diagnose', 'dspace-logs', 'dspace-remove',
                   'tainacan-status', 'tainacan-logs', 'tainacan-uninstall'):
        assert platforms.entry_shown(action, 'recovery', 'unknown', facts)
    for action in ('dspace-install', 'dspace-start', 'tainacan-install'):
        assert not platforms.entry_shown(action, 'setup', 'unknown', facts)


def test_dashboard_recovers_status_and_keeps_local_health_when_collector_fails(monkeypatch):
    monkeypatch.setattr(PanelEnv, 'language_chosen', lambda self: True)
    monkeypatch.setattr(health, 'read_cpu', lambda: {'busy': 17, 'cores': 4, 'load': .2})
    async def no_network(*args, **kwargs):
        return health.Health(cpu={'busy':17, 'cores':4, 'load':.2})
    monkeypatch.setattr(health, 'collect', no_network)
    async def exercise():
        app = KohaPanelApp(PanelEnv(installer=None, lang='en', plain=True))
        good = False
        async def status():
            if not good: raise BridgeError('broken collector')
            return {'schema':1, 'state':'not_installed', 'koha_installed':False,
                    'disk': {'total': 100, 'free': 50},
                    'memory': {'total': 1000, 'available':500}}
        app.bridge.status = status
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause(.7)
            view = app.screen.query_one(DashboardView)
            assert view.query_one('#status-error').display
            assert not view.query_one('#status-loader').display
            def value(key):
                return str(view.query_one('#'+key, StatusCard).query_one('.card-value', Label).render())
            assert '17%' in value('health-cpu')
            assert value('card-disk') not in ('…', 'Unknown')
            assert 'Unknown' in value('dash-platform-dspace')
            good = True
            view.refresh_data(); await pilot.pause(.5)
            assert not view.query_one('#status-error').display
            assert view._last_status_at > 0
            last = value('dash-platform-dspace')
            good = False
            view.refresh_data(); await pilot.pause(.5)
            assert view.query_one('#status-error').display
            assert value('dash-platform-dspace') == last
    asyncio.run(exercise())
