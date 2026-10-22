"""installer.sha256 is the hash of the installer as committed, with LF.

windows/install.ps1, the Inno Setup preflight and the MSIX build all refuse
an installer that does not match it, and Git for Windows rewrites it with
CRLF unless .gitattributes pins LF (the MSIX then stopped with "The
installer file is damaged").
"""

import hashlib

from conftest import INSTALLER, REPO


def test_installer_sha256_matches_installer():
    expected, name = (REPO / "installer.sha256").read_text(encoding="ascii").split()
    assert name == "installer"
    assert hashlib.sha256(INSTALLER.read_bytes()).hexdigest() == expected


def test_installer_has_no_crlf():
    assert b"\r" not in INSTALLER.read_bytes()
    assert b"\r" not in (REPO / "installer.sha256").read_bytes()


def test_gitattributes_keeps_debian_files_lf():
    rules = {}
    for line in (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and not parts[0].startswith("#"):
            rules[parts[0]] = parts[1:]
    for pattern in ("installer", "installer.sha256", "lang/**", "panel/**"):
        assert "eol=lf" in rules.get(pattern, []), pattern
