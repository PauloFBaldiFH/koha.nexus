"""U7 acceptance, first part (study 11): the "summary" of --status-json.

- Computed once on the Linux side (kei_panel/status_summary.py) from what
  --status-json already reads; only installed systems are listed, with
  their visible names (U6).
- A system stopped on purpose does not count while others run; the worst
  of the others is the overall state.
- --status-json only gains "summary", last; "null" when it cannot be
  computed, so the JSON stays valid and the tray falls back to before.
- Every new text of the tray has Portuguese.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from kei_panel import status_summary as S

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'installer'
NOW = 1_800_000_000


def status(**over):
    data = {"generated_at": NOW, "state": "ok", "services": {"apache2": "active", "mariadb": "active"},
            "http": {"staff": 200}, "backup": {"last_epoch": NOW - 3600, "last_result": "ok"},
            "platforms": [{"id": "koha", "detected": True},
                          {"id": "tainacan", "detected": False, "status": "absent"},
                          {"id": "dspace", "detected": False}],
            "docker": {"running": True}, "names": {}}
    data.update(over)
    return data


def rows(data):
    out = S.summary(data)
    return out["state"], [(s["id"], s["name"], s["state"], s["reason"]) for s in out["systems"]]


TAINACAN_OK = {"id": "tainacan", "detected": True, "status": "installed", "services": "active", "health": "healthy"}
DSPACE = {"id": "dspace", "detected": True, "services": "active", "detail": {"status": "installed"}}


def test_koha_alone_with_its_name():
    assert rows(status(names={"koha": "Biblioteca Central"})) == \
        ("ok", [("koha", "Biblioteca Central", "ok", "")])
    assert S.summary(status())["checked_at"] == NOW


@pytest.mark.parametrize("over, expected", [
    ({"state": "degraded", "services": {"apache2": "active", "mariadb": "inactive"}}, ("critical", "database_stopped")),
    ({"state": "degraded", "services": {"apache2": "inactive", "mariadb": "active"}}, ("critical", "web_server_stopped")),
    ({"state": "degraded", "http": {"staff": 0}}, ("critical", "not_responding")),
    ({"state": "degraded"}, ("attention", "services_partial")),
    ({"state": "stopped"}, ("stopped", "stopped")),
    ({"backup": {"last_epoch": NOW - 4 * 86400, "last_result": "ok"}}, ("attention", "backup_late")),
    ({"backup": {"last_epoch": NOW - 60, "last_result": "failed"}}, ("attention", "backup_failed")),
    ({"backup": {"last_epoch": 0, "last_result": "none"}}, ("ok", "")),
    ({"services": {"apache2": "failed", "mariadb": "active"}}, ("critical", "web_server_stopped")),
])
def test_koha_states(over, expected):
    _o, systems = rows(status(**over))
    assert systems[0][2:] == expected


def test_no_system_and_no_koha():
    assert rows(status(state="not_installed")) == ("none", [])
    data = status(state="not_installed", platforms=[TAINACAN_OK], names={"tainacan": "Museu Municipal"})
    assert rows(data) == ("ok", [("tainacan", "Museu Municipal", "ok", "")])


@pytest.mark.parametrize("row, docker, expected", [
    ({"status": "installing"}, True, ("attention", "installing")),
    ({"status": "failed"}, True, ("critical", "install_failed")),
    ({"services": "unknown"}, True, ("critical", "docker_stopped")),
    ({}, False, ("critical", "docker_stopped")),
    ({"services": "inactive"}, True, ("critical", "not_running")),
    ({"services": "partial"}, True, ("critical", "services_partial")),
    ({"health": "failing"}, True, ("critical", "not_responding")),
    ({"health": "unknown"}, True, ("attention", "not_checked")),
])
def test_tainacan_states(row, docker, expected):
    data = status(platforms=[{"id": "koha", "detected": True}, dict(TAINACAN_OK, **row)], docker={"running": docker})
    overall, systems = rows(data)
    assert systems[1][2:] == expected and overall == expected[0]


@pytest.mark.parametrize("detail, services, expected", [
    ({"status": "stopped"}, "inactive", ("stopped", "stopped")),
    ({"status": "installing"}, "partial", ("attention", "installing")),
    ({"status": "degraded"}, "partial", ("critical", "services_partial")),
    ({"status": "unavailable"}, "unknown", ("critical", "docker_stopped")),
    ({"status": "installed"}, "partial", ("critical", "services_partial")),
    ({"status": "weird"}, "active", ("attention", "unknown")),
])
def test_dspace_states(detail, services, expected):
    data = status(platforms=[{"id": "koha", "detected": True}, dict(DSPACE, detail=detail, services=services)])
    assert rows(data)[1][1][2:] == expected
    assert rows(status(platforms=[dict(DSPACE, detail={"status": "absent"})]))[1] == \
        [("koha", "Koha", "ok", "")]


def test_stopped_does_not_count_and_the_worst_wins():
    stopped = dict(DSPACE, services="inactive", detail={"status": "stopped"})
    assert rows(status(platforms=[{"id": "koha"}, stopped]))[0] == "ok"
    assert rows(status(state="not_installed", platforms=[stopped]))[0] == "stopped"
    bad = dict(TAINACAN_OK, health="failing")
    late = {"backup": {"last_epoch": NOW - 5 * 86400, "last_result": "ok"}}
    assert rows(status(platforms=[{"id": "koha"}, bad], **late))[0] == "critical"


def test_names_are_only_text():
    data = status(names={"koha": "  ", "dspace": 5})
    assert rows(data)[1][0][1] == "Koha"


def run(stdin):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'panel'), 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run([sys.executable, '-m', 'kei_panel.status_summary'], input=stdin, env=env,
                          capture_output=True, text=True, timeout=60).stdout.strip()


def test_the_command_always_prints_json():
    assert json.loads(run(json.dumps(status())))["state"] == "ok"
    for bad in ('', 'garbage', '[1]', '{"platforms": 5}'):
        out = run(bad)
        assert out == 'null' or isinstance(json.loads(out), dict), bad


def test_the_installer_wiring():
    text = INSTALLER.read_text(encoding='utf-8')
    body = re.search(r'^kei_status_json\(\) \{\n(.*?)^\}', text, re.S | re.M).group(1)
    assert body.rstrip().endswith('"$platforms" "$docker" "$names" | kei_status_summary)"')
    assert """printf '"summary":%s}\\n'""" in body
    helper = re.search(r'^kei_status_summary\(\) \{\n(.*?)^\}', text, re.S | re.M).group(1)
    assert "printf 'null'" in helper and 'cd /' in helper and '[ -n "$out" ] || out=null' in helper


def test_the_installer_helper_runs(tmp_path):
    script = tmp_path / 's.sh'
    fn = re.search(r'^kei_status_summary\(\) \{\n.*?^\}\n', INSTALLER.read_text(encoding='utf-8'), re.S | re.M).group(0)
    script.write_text(fn + 'KEI_PANEL_SRC="$1"; KEI_PANEL_VENV=/nonexistent\nprintf "%s" "$2" | kei_status_summary\n')
    ok = subprocess.run(['bash', str(script), str(ROOT / 'panel'), json.dumps(status())], capture_output=True, text=True)
    assert json.loads(ok.stdout)["systems"][0]["id"] == "koha"
    gone = subprocess.run(['bash', str(script), str(tmp_path / 'none'), '{}'], capture_output=True, text=True)
    assert gone.stdout == 'null'


@pytest.fixture
def pt(monkeypatch, tmp_path):
    import kei_panel.i18n as i18n
    from kei_panel.i18n import Translator, install
    monkeypatch.setattr(i18n, 'CONFIG_DIR', tmp_path)
    translator = Translator('pt', ROOT / 'installer', False)
    install(translator)
    yield translator
    install(Translator('en', None))


def test_the_tray_texts_have_portuguese(pt):
    sys.path.insert(0, str(ROOT))
    from nexus_core import indicator
    core = (ROOT / 'windows' / 'KohaEasy.Core.psm1').read_text(encoding='utf-8-sig')
    tray = (ROOT / 'windows' / 'KohaEasy.Tray.ps1').read_text(encoding='utf-8-sig')
    texts = list(indicator.REASONS.values()) + list(indicator.WORDS.values())
    start = core.index('function Resolve-KohaIndicator')
    texts += re.findall(r"\(T '([^']+)'\)", core[start:core.index('# Notifications', start)])
    texts += ['Start the systems', 'Stop the systems']
    assert 'Start the systems' in tray
    assert len(texts) > 25 and sorted(s for s in set(texts) if pt(s) == s) == []
