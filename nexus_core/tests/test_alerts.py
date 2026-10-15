import json

import pytest

from nexus_core.tests.fixtures import status_json
from nexus_core.alerts import ERROR, INFO, WARNING, Alert, DiskHealth, decide_alerts, format_size
from nexus_core.state import KohaStatus
from nexus_core.status import parse_status

NOW = 1_800_000_000
DAY = 86400


def st(state="running", **overrides):
    """A KohaStatus whose --status-json has a backup logged long ago and no repair."""
    blocks = {"backup": {"last_file": "x.sql.gz", "last_epoch": NOW - 3600, "last_size": 1024 ** 3 * 3 // 2,
                         "last_kind": "nightly", "last_result": "ok", "log_epoch": NOW - 10 * DAY}}
    blocks.update(overrides)
    return KohaStatus(state=state, linux=parse_status(status_json(**blocks)))


def titles(decision):
    return [a.title for a in decision.alerts]


def decide(previous, status, saved=None, disk=None, t=str):
    saved = {"desired": "running", "lastBackupLogEpoch": NOW - 10 * DAY, "firstSeen": NOW - 30 * DAY,
             **(saved or {})}
    return decide_alerts(previous, status, disk, saved, now=NOW, t=t)


def test_nothing_changed_nothing_told():
    d = decide("running", st())
    assert d.alerts == []
    assert d.changes == {"lastState": "running"}


@pytest.mark.parametrize("previous, cur, expected", [
    ("running", "not_responding", (ERROR, "Koha is not responding")),
    ("starting", "not_responding", (ERROR, "Koha is not responding")),
    ("running", "stopped", (ERROR, "Koha stopped unexpectedly")),
    ("starting", "stopped", (ERROR, "Koha stopped unexpectedly")),
    ("not_responding", "running", (INFO, "Koha is working again")),
    ("stopped", "running", (INFO, "Koha is working again")),
])
def test_service_events(previous, cur, expected):
    d = decide(previous, st(cur))
    assert [(a.level, a.title) for a in d.alerts] == [expected]


@pytest.mark.parametrize("previous, cur, saved", [
    ("", "not_responding", {}),                       # first check after start: no "change"
    ("running", "not_responding", {"desired": "stopped"}),  # the librarian does not want it on
    ("stopped_by_user", "stopped", {}),
    ("starting", "running", {}),                      # a normal start is not news
    ("running", "starting", {}),
])
def test_no_service_event(previous, cur, saved):
    assert decide(previous, st(cur), saved).alerts == []


def test_backup_ok_told_only_when_asked_and_once():
    fresh = {"backup": {"last_epoch": NOW - 600, "last_size": 1024 ** 3 * 3 // 2, "last_result": "ok",
                        "log_epoch": NOW - 600}}
    d = decide("running", st(**fresh))
    assert d.alerts == [] and d.changes["lastBackupLogEpoch"] == NOW - 600
    d = decide("running", st(**fresh), {"notifyBackupOk": True})
    assert d.alerts == [Alert(INFO, "Backup completed", "The nightly backup of the catalog was saved (1.5 GB).")]
    assert decide("running", st(**fresh), {"notifyBackupOk": True, "lastBackupLogEpoch": NOW - 600}).alerts == []


def test_backup_failure_is_always_told():
    failed = {"backup": {"last_epoch": NOW - DAY, "last_result": "failed", "log_epoch": NOW - 600}}
    assert titles(decide("running", st(**failed))) == ["Backup FAILED"]


def test_an_old_log_line_seen_for_the_first_time_is_only_remembered():
    old = {"backup": {"last_epoch": NOW - 600, "last_result": "failed", "log_epoch": NOW - 2 * DAY}}
    d = decide("running", st(**old), {"lastBackupLogEpoch": 0})
    assert d.alerts == [] and d.changes["lastBackupLogEpoch"] == NOW - 2 * DAY


def test_no_recent_backup_warning():
    stale = {"backup": {"last_epoch": NOW - 40 * 3600, "last_result": "ok", "log_epoch": 0}}
    d = decide("running", st(**stale))
    assert [(a.level, a.title) for a in d.alerts] == [(WARNING, "No recent backup")]
    assert "keep Koha on at 23:00" in d.alerts[0].text
    assert d.changes["lastStaleBackupWarn"] == NOW
    manual = decide("running", st(**stale), {"autostart": "manual"})
    assert "only when you click Koha - Start" in manual.alerts[0].text
    # once a day, not on a new install, not without Koha
    assert decide("running", st(**stale), {"lastStaleBackupWarn": NOW - 3600}).alerts == []
    new = decide("running", st(**stale), {"firstSeen": 0})
    assert new.alerts == [] and new.changes["firstSeen"] == NOW
    assert decide("running", st(koha_installed=False, **stale)).alerts == []


def test_without_a_backup_block_nothing_about_backups():
    status = KohaStatus(state="running", linux=parse_status(json.dumps({"schema": 1, "state": "ok",
                                                                         "koha_installed": True})))
    d = decide("running", status, {"firstSeen": 0})
    assert d.alerts == [] and "firstSeen" not in d.changes


def rec(**kw):
    base = {"epoch": NOW - 600, "state": "running", "finished": 0, "db": "-", "backup": "-", "index": "-"}
    base.update(kw)
    return {"recovery": base}


def test_repair_started_told_once():
    d = decide("running", st(**rec()))
    assert titles(d) == ["Koha was not shut down properly"]
    assert d.changes["lastRecoveryNotice"] == NOW - 600
    assert decide("running", st(**rec()), {"lastRecoveryNotice": NOW - 600}).alerts == []


def test_repair_done_cleanly():
    d = decide("running", st(**rec(state="done", db="ok", backup="ok", index="ok")),
               {"lastRecoveryNotice": NOW - 600})
    assert titles(d) == ["Koha repaired itself"]
    assert d.changes["lastRecoveryEpoch"] == NOW - 600


def test_repair_done_with_problems_lists_them():
    d = decide("running", st(**rec(state="done", db="errors", backup="failed", index="failed")))
    assert [(a.level, a.title) for a in d.alerts] == [(ERROR, "Koha needs attention")]
    assert ("problems: the database check reported errors; the new backup failed; "
            "the search index could not be rebuilt.") in d.alerts[0].text
    unreachable = decide("running", st(**rec(state="done", db="unreachable")))
    assert "the database did not start" in unreachable.alerts[0].text


def test_a_repair_older_than_a_week_is_ignored():
    assert decide("running", st(**rec(epoch=NOW - 8 * DAY))).alerts == []


def test_disk_space():
    low = DiskHealth("low", "8 GB free")
    d = decide("running", st(), disk=low)
    assert d.alerts == [Alert(WARNING, "Disk space is low", "8 GB free")]
    assert d.changes["lastDiskLevel"] == "low" and d.changes["lastDiskWarn"] == NOW
    assert decide("running", st(), {"lastDiskLevel": "low"}, disk=low).alerts == []
    crit = DiskHealth("critical", "3 GB free")
    assert decide("running", st(), {"lastDiskLevel": "low"}, disk=crit).alerts[0].level == ERROR
    again = {"lastDiskLevel": "critical", "lastDiskWarn": NOW - 7 * 3600}
    assert titles(decide("running", st(), again, disk=crit)) == ["Disk space is critically low"]
    again["lastDiskWarn"] = NOW - 3600
    assert decide("running", st(), again, disk=crit).alerts == []
    ok = decide("running", st(), {"lastDiskLevel": "critical"}, disk=DiskHealth("ok"))
    assert ok.alerts == [] and ok.changes["lastDiskLevel"] == "ok"
    assert "lastDiskLevel" not in decide("running", st()).changes


def test_texts_go_through_the_translator():
    pt = {"Backup FAILED": "Backup FALHOU",
          "The nightly backup of the catalog was saved ({0}).": "O backup noturno foi salvo ({0})."}
    t = lambda s: pt.get(s, s)  # noqa: E731
    failed = {"backup": {"last_epoch": NOW, "last_result": "failed", "log_epoch": NOW - 1}}
    assert titles(decide("running", st(**failed), t=t)) == ["Backup FALHOU"]
    ok = {"backup": {"last_epoch": NOW, "last_size": 2048, "last_result": "ok", "log_epoch": NOW - 1}}
    assert decide("running", st(**ok), {"notifyBackupOk": True}, t=t).alerts[0].text == \
        "O backup noturno foi salvo (2 KB)."


@pytest.mark.parametrize("n, text", [
    (0, "0 KB"), (1536, "2 KB"), (1024 ** 2 - 1, "1,024 KB"), (1024 ** 2, "1.0 MB"),
    (52428800, "50.0 MB"), (1024 ** 3 * 3 // 2, "1.5 GB"), (1024 ** 4, "1,024.0 GB"),
])
def test_format_size(n, text):
    assert format_size(n) == text
