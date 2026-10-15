"""The Runner for Windows: wsl.exe into Koha's distro (Invoke-KohaLinux).

`wsl.exe --list` prints UTF-16 (little endian) unless WSL_UTF8=1 is set;
both are decoded. Every child process gets CREATE_NO_WINDOW so no console
ever flashes, and status checks never start the distro: a Koha the
librarian stopped stays stopped.
"""

from __future__ import annotations

import os
import subprocess
from typing import Callable, List, Optional, Sequence

from nexus_core.ports import RunResult

from . import config

CREATE_NO_WINDOW = 0x08000000


def wsl_exe(env=None) -> str:
    env = os.environ if env is None else env
    return os.path.join(env.get("SystemRoot") or "C:\\Windows", "System32", "wsl.exe")


def decode_wsl(raw: bytes) -> str:
    """wsl.exe output as text: UTF-16 LE when it looks like it (every other
    byte zero), else UTF-8; NUL characters dropped either way."""
    if not raw:
        return ""
    if raw.startswith(b"\xff\xfe") or (len(raw) >= 2 and raw[1:2] == b"\x00"):
        text = raw.decode("utf-16-le", "replace")
    else:
        text = raw.decode("utf-8", "replace")
    return text.replace("\ufeff", "").replace("\x00", "")


def distro_names(output: str) -> List[str]:
    """Names from `wsl.exe --list --quiet` output, one per line."""
    return [line.strip() for line in output.splitlines() if line.strip()]


Run = Callable[..., "subprocess.CompletedProcess[bytes]"]


class WslRunner:
    def __init__(self, distro: str = config.DISTRO, panel: str = config.PANEL_PATH,
                 run: Optional[Run] = None, exe: Optional[str] = None):
        self.distro = distro
        self.panel = panel
        self._run = run or subprocess.run
        self.exe = exe or wsl_exe()

    def _call(self, args: Sequence[str], timeout: float) -> RunResult:
        env = dict(os.environ, WSL_UTF8="1")
        try:
            p = self._run([self.exe, *args], capture_output=True, timeout=timeout, env=env,
                          stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired) as e:
            return RunResult(-1, str(e))
        return RunResult(p.returncode, decode_wsl(p.stdout))

    def _names(self, *flags: str) -> List[str]:
        r = self._call(["--list", *flags, "--quiet"], timeout=30)
        return distro_names(r.out) if r.code == 0 else []

    def installed(self) -> bool:
        return self.distro in self._names()

    def running(self) -> bool:
        return self.distro in self._names("--running")

    def verb(self, args: Sequence[str], timeout: float = 30) -> RunResult:
        return self._call(["-d", self.distro, "-u", "root", "--", self.panel, *args], timeout)
