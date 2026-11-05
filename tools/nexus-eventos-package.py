#!/usr/bin/env python3
"""The production package of the Nexus Eventos plugin (nexus-events-plugin/).

Only the plugin goes into it: never bundled/ (the copy of Events Manager
kept for the analysis) nor development/ (tests that create users and
bookings). Events Manager is a separate plugin, installed from wordpress.org.

  nexus-eventos-package.py list            "sha256  path" of every file
  nexus-eventos-package.py zip OUT.zip     the package, folder nexus-eventos/
  nexus-eventos-package.py check INSTALLER the list inside the installer
                                           (_kei_ev_package_files) is this one

The installer carries the list and checks every file against it before
WordPress sees the plugin, so the list there must be updated (and this check
passes) whenever a file of the plugin changes.
"""
import hashlib
import os
import re
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nexus-events-plugin")
FOLDER = "nexus-eventos"
TOP = ["nexus-eventos.php", "uninstall.php", "readme.txt", "LICENSE", "LEIA-ME.md", "THIRD-PARTY-NOTICES.md"]
DIRS = ["includes", "assets", "languages"]
NEVER = ("bundled/", "development/")


def files(root=ROOT):
    out = []
    for name in TOP:
        out.append(name)
    for d in DIRS:
        base = os.path.join(root, d)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            for f in sorted(filenames):
                rel = os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")
                if f.startswith(".") or f.endswith((".pyc",)) or "__pycache__" in rel:
                    continue
                out.append(rel)
    for rel in out:
        path = os.path.join(root, rel)
        if rel.startswith(NEVER):
            raise SystemExit("not for production: " + rel)
        if os.path.islink(path) or not os.path.isfile(path):
            raise SystemExit("not a regular file: " + rel)
    return sorted(out)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def listing(root=ROOT):
    return ["%s  %s" % (sha256(os.path.join(root, rel)), rel) for rel in files(root)]


def make_zip(out, root=ROOT):
    # Fixed dates and modes: the same files give the same zip.
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files(root):
            info = zipfile.ZipInfo(FOLDER + "/" + rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(root, rel), "rb") as fh:
                z.writestr(info, fh.read())


def installer_list(path):
    text = open(path, encoding="utf-8").read()
    m = re.search(r"^_kei_ev_package_files\(\) \{\n    cat <<'EOF'\n(.*?)\nEOF\n\}", text, re.S | re.M)
    if not m:
        raise SystemExit("_kei_ev_package_files not found in " + path)
    return m.group(1).splitlines()


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    cmd = argv[1]
    if cmd == "list":
        print("\n".join(listing()))
        return 0
    if cmd == "zip" and len(argv) == 3:
        make_zip(argv[2])
        return 0
    if cmd == "check" and len(argv) == 3:
        want, have = listing(), installer_list(argv[2])
        if want == have:
            print("ok %d files" % len(want))
            return 0
        for line in sorted(set(want) ^ set(have)):
            print(("installer has: " if line in have else "plugin has:    ") + line)
        print("update _kei_ev_package_files in the installer with: tools/nexus-eventos-package.py list")
        return 1
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
