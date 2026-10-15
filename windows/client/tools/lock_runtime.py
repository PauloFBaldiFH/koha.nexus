"""Writes or checks windows/client/runtime.lock.json.

The lock names every file the Windows installer downloads for the Python
tray and window (KohaEasy.Python.psm1): the embeddable CPython from
python.org and one wheel per package from PyPI, each with its SHA-256. The
installer refuses a file whose hash differs, so the lock is the whole
supply chain and is reviewed like code.

    python windows/client/tools/lock_runtime.py --write   # after changing PINS
    python windows/client/tools/lock_runtime.py --check   # CI: lock == upstream

Wheel hashes come from PyPI's JSON API (the digests PyPI publishes); the
Python zip is downloaded and hashed, since python.org publishes no plain
SHA-256 list. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

LOCK = Path(__file__).resolve().parents[1] / "runtime.lock.json"

PYTHON_VERSION = "3.12.10"
PYTHON_TAG = "cp312"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"

# Every package the client imports, with its dependencies for Windows, pinned.
# (name, version, sdist package dir when PyPI has no wheel)
PINS = [
    ("pystray", "0.19.5", None),
    ("six", "1.17.0", None),
    ("pillow", "12.3.0", None),
    ("pywebview", "6.2.1", None),
    ("proxy-tools", "0.1.0", "proxy_tools"),
    ("bottle", "0.13.4", None),
    ("typing-extensions", "4.16.0", None),
    ("pythonnet", "3.2.1", None),
    ("clr-loader", "0.3.1", None),
    ("cffi", "2.1.1", None),
    ("pycparser", "3.11", None),
    ("windows-toasts", "1.3.1", None),
    ("winrt-runtime", "3.2.1", None),
    ("winrt-Windows.Data.Xml.Dom", "3.2.1", None),
    ("winrt-Windows.Foundation", "3.2.1", None),
    ("winrt-Windows.Foundation.Collections", "3.2.1", None),
    ("winrt-Windows.UI.Notifications", "3.2.1", None),
]


def wheel_fits(filename: str, tag: str = PYTHON_TAG) -> int:
    """0 when the wheel cannot run on 64-bit Windows CPython `tag`; else a
    preference (2 = built for it, 1 = pure Python)."""
    if not filename.endswith(".whl"):
        return 0
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return 0
    py, abi, plat = parts[-3].split("."), parts[-2], parts[-1].split(".")
    if "win_amd64" in plat and tag in py and abi in (tag, "abi3", "none"):
        return 2
    if "any" in plat and (tag in py or any(p in ("py3", "py2") for p in py)) and abi == "none":
        return 1
    return 0


def pick(release: List[Dict[str, Any]], sdist_dir: Optional[str]) -> Dict[str, Any]:
    """The file of one PyPI release the installer should use."""
    wheels = sorted((f for f in release if wheel_fits(f["filename"])), key=lambda f: -wheel_fits(f["filename"]))
    if wheels:
        f = wheels[0]
        return {"kind": "wheel", "file": f["filename"], "url": f["url"], "sha256": f["digests"]["sha256"]}
    if sdist_dir:
        for f in release:
            if f["packagetype"] == "sdist" and f["filename"].endswith(".tar.gz"):
                top = f["filename"][: -len(".tar.gz")]
                return {"kind": "sdist", "file": f["filename"], "url": f["url"], "sha256": f["digests"]["sha256"],
                        "copy": f"{top}/{sdist_dir}"}
    raise SystemExit("no usable file in this release: " + ", ".join(f["filename"] for f in release))


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "koha.nexus-lock"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def build(python_sha256: Optional[str] = None) -> Dict[str, Any]:
    packages = []
    for name, version, sdist_dir in PINS:
        data = json.loads(_get(f"https://pypi.org/pypi/{name}/{version}/json"))
        packages.append({"name": name, "version": version, **pick(data["urls"], sdist_dir)})
    sha = python_sha256 or hashlib.sha256(_get(PYTHON_URL)).hexdigest()
    return {
        "lock": 1,
        "python": {"version": PYTHON_VERSION, "url": PYTHON_URL, "sha256": sha},
        "packages": packages,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    ap.add_argument("--python-sha256", help="use this hash instead of downloading the Python zip")
    args = ap.parse_args(argv)
    lock = build(args.python_sha256)
    text = json.dumps(lock, indent=2) + "\n"
    if args.write:
        LOCK.write_text(text, encoding="utf-8")
        print(f"wrote {LOCK}")
        return 0
    current = LOCK.read_text(encoding="utf-8") if LOCK.exists() else ""
    if current == text:
        print("runtime.lock.json matches PyPI and python.org")
        return 0
    print("runtime.lock.json differs from upstream. Expected:\n" + text, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
