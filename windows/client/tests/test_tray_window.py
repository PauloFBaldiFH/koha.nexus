"""tray.py and window.py without pystray or pywebview: the parts that decide."""

from koha_nexus_win.tray import Tray
from koha_nexus_win.window import Api


class FakeActions:
    def __init__(self):
        self.calls = []

    def verb(self, *a):
        self.calls.append(a)

    def staff(self):
        self.calls.append(("staff",))

    def opac(self):
        self.calls.append(("opac",))

    def backups(self):
        self.calls.append(("backups",))

    def python_window(self):
        self.calls.append(("python_window",))


def tray(saved=None):
    saved = dict(saved or {"autostart": "logon", "notifyBackupOk": True})
    a = FakeActions()
    t = Tray(monitor=None, actions=a, t=str, load_state=lambda: dict(saved), save_state=saved.update)
    return t, a, saved


def test_tray_menu_keys_run_their_verbs():
    t, a, _ = tray()
    for key in ("start", "stop", "restart", "reindex", "poweroff", "report", "diagnostics", "disk", "panel"):
        t._run(key)
    assert [c[0] for c in a.calls] == ["Start", "Stop", "RestartServices", "RebuildIndex", "SafeShutdown",
                                       "ExportReport", "ExportDiagnostics", "CheckDisk", "Panel"]
    t._run("window")
    assert a.calls[-1] == ("python_window",)


def test_tray_toggles():
    t, a, saved = tray()
    t._run("autostart")
    assert a.calls[-1] == ("SetAutostart", "-Mode", "manual")
    t._run("notify_backup")
    assert saved["notifyBackupOk"] is False


def test_tray_close_is_remembered():
    t, _, saved = tray()
    t._run("close")
    assert saved["trayClosed"] is True


def test_window_buttons():
    a = FakeActions()
    api = Api(monitor=None, actions=a, t=str, debian_running=lambda: True)
    assert api.act("staff") and api.act("start") and api.act("terminal")
    assert api.act("uninstall") is False
    assert a.calls == [("staff",), ("Start",), ("Terminal",)]


def test_window_status_errors_become_a_message():
    class Broken:
        def status(self):
            raise RuntimeError("wsl.exe missing")
    api = Api(monitor=Broken(), actions=FakeActions(), t=str, debian_running=lambda: False)
    assert api.status() == {"error": "wsl.exe missing"}
