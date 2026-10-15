import os
from pathlib import Path

import pytest

from koha_nexus_win import menu
from koha_nexus_win.actions import Actions, hidden_launch
from koha_nexus_win.config import KohaPaths

P = KohaPaths(Path("C:/Koha"))
ENV = {"SystemRoot": "C:/Windows"}


def everything(path):
    return True


def test_launcher_first_when_it_works():
    argv = hidden_launch("Start", {"launcher": "ok"}, P, ENV, everything)
    assert argv == [str(P.launcher), "Start", "-Hidden"]


def test_wscript_then_conhost_then_powershell():
    st = {"launcher": "refused", "hiddenLaunch": "conhost"}
    assert hidden_launch("Stop -Force", st, P, ENV, everything)[:3] == [os.path.join("C:/Windows", "System32", "wscript.exe"), "//B", "//Nologo"]
    assert hidden_launch("Stop -Force", st, P, ENV, everything)[-3:] == ["Stop", "-Force", "-Hidden"]
    st["hiddenLaunch"] = "nowscript"
    argv = hidden_launch("Stop", st, P, ENV, everything)
    assert argv[0].endswith("conhost.exe") and argv[1] == "--headless"
    st["hiddenLaunch"] = "powershell"
    argv = hidden_launch("Stop", st, P, ENV, everything)
    assert argv[0].endswith("powershell.exe")
    assert argv[1:8] == ["-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", str(P.script)]


def test_a_missing_launcher_is_skipped():
    argv = hidden_launch("Start", {"launcher": "ok"}, P, ENV, lambda p: not p.endswith("koha.nexus.exe"))
    assert argv[0].endswith("wscript.exe")


def test_actions_start_only_known_verbs():
    calls = []
    a = Actions(P, lambda: {"launcher": "ok"}, popen=lambda argv, **kw: calls.append(argv))
    a.verb("RestartServices")
    assert calls[-1][-2:] == ["RestartServices", "-Hidden"]
    with pytest.raises(ValueError):
        a.verb("Uninstall")


def keys(entries):
    return {e.key: e for e in entries if e.key not in ("", "-")}


def test_menu_when_running():
    m = keys(menu.entries("running", {"autostart": "logon", "notifyBackupOk": True}))
    assert m["staff"].enabled and m["opac"].enabled
    assert not m["start"].enabled and m["stop"].enabled and m["reindex"].enabled
    assert m["autostart"].checked is True and m["notify_backup"].checked is True
    assert m["window"].default
    assert m["reindex"].confirm.startswith("Rebuild the search index from scratch?")


@pytest.mark.parametrize("state, start, stop", [("stopped", True, False), ("stopped_by_user", True, False),
                                                ("not_installed", False, False), ("starting", False, True),
                                                ("not_responding", False, True)])
def test_menu_start_stop(state, start, stop):
    m = keys(menu.entries(state, {}))
    assert (m["start"].enabled, m["stop"].enabled, m["staff"].enabled) == (start, stop, False)


def test_menu_header_is_the_translated_state():
    pt = {"Koha is running": "O Koha est\u00e1 em execu\u00e7\u00e3o"}
    e = menu.entries("running", {}, lambda s: pt.get(s, s))
    assert e[0].text == pt["Koha is running"] and not e[0].enabled


def test_every_verb_of_the_menu_is_allowed():
    from koha_nexus_win.actions import VERBS
    for verb in menu.VERB_OF.values():
        assert verb[0] in VERBS
