import json
from pathlib import Path

from koha_nexus_win import config
from koha_nexus_win.store import DEFAULTS, JsonStateStore


def test_root_from_the_environment():
    assert config.resolve_root({"KOHAEASY_ROOT": "D:\\Koha"}) == Path("D:\\Koha")


def test_root_from_where_the_package_is_installed(tmp_path):
    pkg = tmp_path / "Koha" / "bin" / "client" / "koha_nexus_win"
    pkg.mkdir(parents=True)
    (tmp_path / "Koha" / "bin" / "KohaEasy.ps1").write_text("")
    assert config.resolve_root({}, here=pkg / "config.py") == tmp_path / "Koha"


def test_root_falls_back_to_an_old_install_only_when_the_new_one_is_missing(tmp_path):
    new, old = tmp_path / "Koha", tmp_path / "KohaEasy"
    here = tmp_path / "src" / "pkg" / "config.py"
    assert config.resolve_root({}, here, str(new), str(old)) == new
    old.mkdir()
    (old / "state.json").write_text("{}")
    assert config.resolve_root({}, here, str(new), str(old)) == old
    new.mkdir()
    (new / "state.json").write_text("{}")
    assert config.resolve_root({}, here, str(new), str(old)) == new


def test_paths():
    p = config.KohaPaths(Path("C:/Koha"))
    assert p.state == Path("C:/Koha/state.json")
    assert p.launcher == Path("C:/Koha/bin/koha.nexus.exe")
    assert p.lang == Path("C:/Koha/bin/lang")


def test_store_defaults_and_normalisation(tmp_path):
    s = JsonStateStore(tmp_path / "state.json")
    assert s.load() == DEFAULTS
    (tmp_path / "state.json").write_text('{"desired": "maybe", "autostart": "manual", "phase": "done"}')
    st = s.load()
    assert st["desired"] == "running" and st["autostart"] == "manual" and st["phase"] == "done"


def test_store_reads_a_bom_and_survives_damage(tmp_path):
    f = tmp_path / "state.json"
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps({"lastState": "running"}).encode())
    assert JsonStateStore(f).load()["lastState"] == "running"
    f.write_text("{half a file")
    assert JsonStateStore(f).load() == DEFAULTS


def test_store_save_merges_and_keeps_unknown_keys(tmp_path):
    f = tmp_path / "state.json"
    f.write_text(json.dumps({"phase": "done", "launcher": "ok", "lastState": "stopped"}))
    JsonStateStore(f).save({"lastState": "running", "firstSeen": 5})
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["phase"] == "done" and data["launcher"] == "ok"
    assert data["lastState"] == "running" and data["firstSeen"] == 5
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]
