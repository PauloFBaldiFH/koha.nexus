"""Where Koha is on this PC and what it is called ($Cfg of KohaEasy.Core.psm1)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

DISTRO = "koha"
PANEL_PATH = "/usr/local/bin/koha-panel"
STAFF_URL = "http://localhost:8080/"
OPAC_URL = "http://localhost/"
APP_ID = "KohaEasy.Koha"
# Windows PowerShell's own AppUserModelID: toasts use it until the Koha
# shortcut carrying APP_ID exists (state.json appIdShortcut).
TOAST_APP_ID = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
TRAY_MUTEX = "Local\\KohaEasyTray"
WINDOW_MUTEX = "Local\\KohaEasyWindow"
STATUS_EVERY_S = 60
DISK_EVERY_S = 1800
WINDOW_REFRESH_S = 30

NEW_ROOT = "C:\\Koha"
OLD_ROOT = "C:\\KohaEasy"


def _is_install(root: Path) -> bool:
    return (root / "state.json").exists() or (root / "bin" / "KohaEasy.ps1").exists()


def resolve_root(env: Optional[Mapping[str, str]] = None, here: Optional[Path] = None,
                 new_root: str = NEW_ROOT, old_root: str = OLD_ROOT) -> Path:
    """Resolve-KohaRoot: KOHAEASY_ROOT; else the folder this package was
    installed in (<root>\\bin\\client\\koha_nexus_win); else C:\\Koha, or
    C:\\KohaEasy when only an install from before the rename is there."""
    env = os.environ if env is None else env
    if env.get("KOHAEASY_ROOT"):
        return Path(env["KOHAEASY_ROOT"])
    here = Path(__file__).resolve() if here is None else here
    pkg = here.parent
    bin_dir = pkg.parent.parent
    if bin_dir.name.lower() == "bin" and (bin_dir / "KohaEasy.ps1").exists():
        return bin_dir.parent
    new, old = Path(new_root), Path(old_root)
    if not _is_install(new) and _is_install(old):
        return old
    return new


@dataclass(frozen=True)
class KohaPaths:
    root: Path

    @property
    def bin(self) -> Path:
        return self.root / "bin"

    @property
    def state(self) -> Path:
        return self.root / "state.json"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def backups(self) -> Path:
        return self.root / "Backups"

    @property
    def lang(self) -> Path:
        return self.bin / "lang"

    @property
    def icon(self) -> Path:
        return self.bin / "koha.ico"

    @property
    def launcher(self) -> Path:
        return self.bin / "koha.nexus.exe"

    @property
    def script(self) -> Path:
        return self.bin / "KohaEasy.ps1"


def paths(env: Optional[Mapping[str, str]] = None) -> KohaPaths:
    return KohaPaths(resolve_root(env))
