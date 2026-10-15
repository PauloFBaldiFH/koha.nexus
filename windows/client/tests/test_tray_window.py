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


def test_tray_window_key_opens_the_app_window_and_stop_calls_back_once():
    t, a, _ = tray()
    opened, stopped = [], []
    t.open_window = lambda: opened.append(1)
    t.on_stop = lambda: stopped.append(1)
    t._run("window")
    assert opened == [1] and ("python_window",) not in a.calls
    t.stop()
    t.stop()
    assert stopped == [1]


SECTIONS = [
    {"id": "backup", "sidebar": True, "entries": [
        {"action": "status", "kind": "native"},
        {"action": "backup-now", "kind": "native"},
        {"action": "backup-download", "kind": "native"},
    ]},
]


class FakeEngine:
    def __init__(self):
        self.calls = []

    def start(self, name):
        self.calls.append(("start", name))
        return {"ok": True, "id": 7, "name": name, "total": None}

    def answer(self, run_id, value):
        self.calls.append(("answer", run_id, value))
        return True

    def cancel(self, run_id):
        self.calls.append(("cancel", run_id))
        return True


def section_api():
    a, e = FakeActions(), FakeEngine()
    api = Api(monitor=None, actions=a, t=str, debian_running=lambda: True, sections=SECTIONS,
              engine=e, panel_only=frozenset({"backup-download"}))
    return api, a, e


def test_sections_carry_the_menu_inline_tasks_and_labels():
    api, _, _ = section_api()
    data = api.sections()
    assert data["sections"] == SECTIONS
    assert "status" in data["inline"]
    assert data["labels"]["terminal_panel"] == "Advanced: terminal panel"


def test_open_entry_runs_inline_tasks_here_and_the_rest_in_the_terminal_panel():
    api, a, e = section_api()
    assert api.open_entry("status") == {"ok": True, "how": "inline", "id": 7, "name": "status", "total": None}
    assert e.calls == [("start", "status")]
    assert api.open_entry("backup-now") == {"ok": True, "how": "terminal"}
    assert api.open_entry("backup-download") == {"ok": True, "how": "terminal"}
    assert a.calls == [("Panel", "-Action", "backup-now"), ("Panel",)]
    assert api.open_entry("rm -rf") == {"ok": False}
    assert api.terminal_panel() and a.calls[-1] == ("Panel",)


def test_answer_and_cancel_reach_the_engine():
    api, _, e = section_api()
    assert api.answer("7", "ok") and api.cancel(7)
    assert e.calls == [("answer", 7, "ok"), ("cancel", 7)]
    bare = Api(monitor=None, actions=FakeActions(), t=str, debian_running=lambda: True)
    assert bare.answer(1, True) is False and bare.cancel(1) is False


def test_js_call_is_plain_json():
    from koha_nexus_win.app import js_call
    assert js_call("nexus.onEvents", [{"text": "</script>é"}]) == \
        'nexus.onEvents([{"text": "</script>\\u00e9"}])'


def test_tray_menu_items_satisfy_pystray(monkeypatch):
    """pystray.MenuItem raises ValueError for an action of more than two
    arguments (defaults included): the whole menu then fails to build."""
    import sys
    import types

    from koha_nexus_win import menu

    made = []

    class MenuItem:
        def __init__(self, text, action, checked=None, enabled=True, default=False):
            if action.__code__.co_argcount > 2:
                raise ValueError(action)
            made.append((text, action))

    fake = types.SimpleNamespace(MenuItem=MenuItem, Menu=types.SimpleNamespace(SEPARATOR="-"))
    monkeypatch.setitem(sys.modules, "pystray", fake)
    t, a, _ = tray()
    entries = [menu.Entry(key="start", text="Start"), menu.Entry(key="opac", text="OPAC")]
    monkeypatch.setattr(t, "_entries", lambda: entries)
    t._items()
    assert [m[0] for m in made] == ["Start", "OPAC"]
    made[1][1](None, None)
    assert a.calls[-1] == ("opac",)
