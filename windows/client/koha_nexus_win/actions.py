"""Buttons and menu items, run as the existing KohaEasy.ps1 verbs.

The Python tray and window do not reimplement Start, Stop, the safe
shutdown or the diagnostics: they start `KohaEasy.ps1 <Verb> -Hidden` the
same hidden way the PowerShell tray does (Get-KohaHiddenLaunch), so both
trays behave the same while they live side by side.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from typing import Any, Callable, Dict, List, Mapping, Optional

from . import config
from .config import KohaPaths

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

# The verbs the tray and the window may start (KohaEasy.ps1's ValidateSet).
VERBS = ("Window", "Start", "Stop", "RestartServices", "RebuildIndex", "SafeShutdown",
         "ExportReport", "ExportDiagnostics", "CheckDisk", "Panel", "Terminal", "SetAutostart")


def hidden_launch(arguments: str, state: Mapping[str, Any], paths: KohaPaths,
                  env: Optional[Mapping[str, str]] = None,
                  exists: Callable[[str], bool] = os.path.exists) -> List[str]:
    """Get-KohaHiddenLaunch as an argument list: koha.nexus.exe when the
    installer found it works (state.json launcher = ok), else wscript.exe
    with KohaEasy.Hidden.js, else conhost --headless, else PowerShell
    hidden. Every launch carries -Hidden, so KohaEasy.ps1 never relaunches."""
    env = os.environ if env is None else env
    root = env.get("SystemRoot") or "C:\\Windows"
    words = (arguments + " -Hidden").split()
    script = str(paths.script)
    ps = os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    ps_args = ["-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script, *words]
    hidden = state.get("hiddenLaunch", "conhost")
    launcher = str(paths.launcher)
    if state.get("launcher") == "ok" and exists(launcher):
        return [launcher, *words]
    js = str(paths.bin / "KohaEasy.Hidden.js")
    wscript = os.path.join(root, "System32", "wscript.exe")
    if hidden not in ("nowscript", "powershell") and exists(js) and exists(wscript):
        return [wscript, "//B", "//Nologo", js, *words]
    conhost = os.path.join(root, "System32", "conhost.exe")
    if hidden != "powershell" and exists(conhost):
        return [conhost, "--headless", ps, *ps_args]
    return [ps, *ps_args]


class Actions:
    def __init__(self, paths: KohaPaths, load_state: Callable[[], Dict[str, Any]],
                 popen: Callable[..., Any] = subprocess.Popen,
                 open_url: Callable[[str], Any] = webbrowser.open,
                 open_folder: Optional[Callable[[str], Any]] = None):
        self.paths = paths
        self.load_state = load_state
        self.popen = popen
        self.open_url = open_url
        self.open_folder = open_folder or (lambda p: os.startfile(p))  # type: ignore[attr-defined]

    def verb(self, name: str, *extra: str) -> List[str]:
        """Starts KohaEasy.ps1 <name> hidden and returns the command line."""
        if name not in VERBS:
            raise ValueError(f"not a tray verb: {name}")
        argv = hidden_launch(" ".join((name, *extra)), self.load_state(), self.paths)
        flags = CREATE_NO_WINDOW | DETACHED_PROCESS if os.name == "nt" else 0
        self.popen(argv, creationflags=flags, close_fds=True)
        return argv

    def python_window(self) -> List[str]:
        """The Python status window, in its own process (the tray stays responsive)."""
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            exe = exe[:-len("python.exe")] + "pythonw.exe"
        argv = [exe, "-m", "koha_nexus_win", "window"]
        self.popen(argv, creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0, close_fds=True)
        return argv

    def staff(self) -> None:
        self.open_url(config.STAFF_URL)

    def opac(self) -> None:
        self.open_url(config.OPAC_URL)

    def backups(self) -> None:
        self.paths.backups.mkdir(parents=True, exist_ok=True)
        self.open_folder(str(self.paths.backups))
