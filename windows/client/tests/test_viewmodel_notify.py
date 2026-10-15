import json

from nexus_core.state import KohaStatus
from nexus_core.status import parse_status
from nexus_core.tests.fixtures import status_json

from koha_nexus_win import viewmodel
from koha_nexus_win.notify import WindowsNotifier, log_line, toast_app_id
from koha_nexus_win import config


def fmt(epoch):
    return f"T{int(epoch)}"


def test_window_of_a_healthy_koha():
    st = KohaStatus("running", linux=parse_status(status_json()), checked_at=100)
    vm = viewmodel.build(st, True, fmt=fmt)
    assert vm["banner"] == {"level": "ok", "text": "All services are running", "broken": []}
    assert vm["checked"] == "Checked at T100"
    assert vm["backup"] == "Latest backup: T1792018800 (50.0 MB)"
    assert [l["enabled"] for l in vm["links"]] == [True, True]
    assert {a["key"]: a["enabled"] for a in vm["actions"]} == {
        "start": False, "panel": True, "restart": True, "terminal": True, "poweroff": True}
    assert len(vm["components"]) == 7
    json.dumps(vm)  # plain JSON for app.js


def test_window_with_debian_stopped():
    vm = viewmodel.build(KohaStatus("stopped"), False, fmt=fmt)
    assert vm["banner"]["level"] == "fault" and vm["banner"]["broken"] == ["wsl"]
    assert vm["backup"] == "Latest backup: none yet"
    assert vm["checked"] == ""
    assert [c["broken"] for c in vm["components"]] == [True] + [False] * 6
    assert {a["key"]: a["enabled"] for a in vm["actions"]}["start"] is True


def test_notifications_are_logged_and_fall_back_to_the_balloon(tmp_path):
    shown = []
    n = WindowsNotifier(tmp_path, lambda: "KohaEasy.Koha", balloon=lambda t, x: shown.append((t, x)))
    assert n.notify("Backup FAILED", "The nightly backup failed.", "error") == "balloon"  # no WinRT on Linux
    assert shown == [("Backup FAILED", "The nightly backup failed.")]
    assert WindowsNotifier(tmp_path, lambda: "x").notify("A", "B") == "log"
    lines = "".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("notifications-*.log")).splitlines()
    assert lines[0].endswith(" | [error] Backup FAILED: The nightly backup failed.")
    assert len(lines) == 2


def test_log_line_name_and_format(tmp_path):
    log_line(tmp_path, "info", "T", "x", now=0)
    f = next(tmp_path.glob("notifications-*.log"))
    assert f.name.startswith("notifications-19") or f.name.startswith("notifications-20")
    assert f.read_text(encoding="utf-8").rstrip().endswith("| [info] T: x")


def test_toast_app_id():
    assert toast_app_id(True) == config.APP_ID
    assert toast_app_id(False) == config.TOAST_APP_ID
