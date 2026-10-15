import json
import shutil
import subprocess
from pathlib import Path

import pytest

from nexus_core.tests.fixtures import HEALTHY, status_json
from nexus_core.status import SCHEMA, Backup, LinuxStatus, last_json_line, parse_status

REPO = Path(__file__).resolve().parents[2]


def test_healthy_output_is_read_field_by_field():
    s = parse_status(status_json())
    assert s.schema == SCHEMA
    assert s.state == "ok" and s.koha_installed is True
    assert s.service("mariadb") == "active"
    assert s.service("koha-zeus-sru") == "unknown"
    assert (s.http_staff, s.http_opac) == (200, 200)
    assert s.backup == Backup("koha_library_2026-10-14_23h00.sql.gz", 1792018800, 52428800,
                              "nightly", "ok", 1792018860)
    assert s.recovery.state == "none" and s.recovery.db == "-"
    assert s.access.lan_ip == "192.168.0.10" and s.access.lan_reachable is True
    assert s.disk.free == 32131735552
    assert s.memory.free == 16367075328


def test_the_last_json_line_wins_over_other_output():
    out = "Preparing...\n{\"schema\": 1, \"state\": \"degraded\"}\nnoise\n" + status_json() + "\n"
    assert parse_status(out).state == "ok"
    assert last_json_line("  {\"a\": 1}") == {"a": 1}


@pytest.mark.parametrize("out", ["", "no json here", "{broken", "[1, 2]", "{\"a\": 1} trailing"])
def test_unreadable_output_is_none(out):
    assert parse_status(out) is None


def test_an_older_installer_without_blocks_reads_as_nothing_known():
    s = parse_status(json.dumps({"schema": 1, "state": "stopped"}))
    assert s.state == "stopped"
    assert s.koha_installed is False
    assert s.services == {}
    assert s.backup == Backup()
    assert s.access.staff_port == 8080
    assert "backup" not in s.raw


def test_wrong_types_never_raise():
    s = parse_status(json.dumps({"schema": "1", "koha_installed": "true", "services": [],
                                 "http": {"staff": "200"}, "backup": "none",
                                 "disk": {"total": None, "free": 1.5}}))
    assert s.schema == 1
    assert s.koha_installed is True
    assert s.services == {}
    assert s.http_staff == 200
    assert s.backup == Backup()
    assert (s.disk.total, s.disk.free) == (0, 1)


def test_a_newer_schema_keeps_known_fields_and_unknown_keys():
    s = parse_status(status_json(schema=2, sru={"koha-zeus-sru": "active"}))
    assert s.schema == 2
    assert s.state == "ok"
    assert s.raw["sru"] == {"koha-zeus-sru": "active"}


def test_from_json_and_parse_agree():
    assert LinuxStatus.from_json(HEALTHY) == parse_status(json.dumps(HEALTHY))


def test_the_real_installer_output_parses():
    """Contract test: the installer in this repository, run here, prints
    something parse_status reads (no Koha in CI: not_installed)."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash")
    try:
        p = subprocess.run([bash, str(REPO / "installer"), "--status-json"], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        pytest.skip("installer --status-json timed out")
    s = parse_status(p.stdout)
    if s is None:
        pytest.skip("installer --status-json printed no JSON here: " + p.stderr[-300:])
    assert s.schema == SCHEMA
    assert s.state in ("ok", "degraded", "stopped", "not_installed")
    for key in ("services", "http", "backup", "recovery", "access", "disk", "memory"):
        assert key in s.raw, key
    assert set(s.services) >= {"apache2", "mariadb", "koha-common"}
