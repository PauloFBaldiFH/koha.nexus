"""The website's Interactive Preview (preview/) stays in step with the panel.

export_docs_preview.py reads the panel's code: when a screen changes, the
committed preview/data/preview.json must be regenerated, and every visible
item needs its English and pt-BR guide.
"""
import json
import subprocess
import sys

from conftest import REPO

SCRIPT = REPO / "export_docs_preview.py"


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=REPO,
                          capture_output=True, text=True)


def test_preview_json_is_up_to_date():
    r = _run("--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_feature_is_found_in_the_panel():
    data = json.loads((REPO / "preview/data/preview.json").read_text())
    pending = [i["id"] for i in data["items"].values() if i.get("status") == "pending"]
    assert pending == []


def test_english_and_portuguese_guides_cover_every_item():
    data = json.loads((REPO / "preview/data/preview.json").read_text())
    wanted = {i["id"] for i in data["items"].values() if i.get("status") != "hidden"}
    for lang in ("en", "pt-BR"):
        manual = json.loads((REPO / f"preview/manual/{lang}.json").read_text())
        assert wanted - set(manual["items"]) == set(), lang
