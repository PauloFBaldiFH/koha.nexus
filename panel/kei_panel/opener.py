"""Opening a web address in the person's browser, from a panel that runs as
root on the Koha server.

Python's webbrowser module is not used: on a server it may pick a text
browser (www-browser, lynx, w3m) that takes the terminal away from the
panel, and as root it would start a desktop browser as root. Instead:

  WSL       the Windows browser (wslview, else explorer.exe through interop)
  desktop   xdg-open as the person who ran sudo, when a display is there
  SSH       nothing here: the browser is on the other computer
Anything that cannot open a browser returns False and the caller copies the
address instead (OSC 52 lands on the person's own clipboard, also over SSH).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .env import _is_wsl

_EXPLORER = Path("/mnt/c/Windows/explorer.exe")


def over_ssh() -> bool:
    return bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"))


def opener_command(url: str, wsl: bool | None = None, ssh: bool | None = None,
                   which=shutil.which, environ: dict[str, str] | None = None) -> list[str] | None:
    """The command that opens url here, or None when this machine has no
    browser for the person (SSH, a server without a desktop)."""
    environ = os.environ if environ is None else environ
    wsl = _is_wsl() if wsl is None else wsl
    ssh = over_ssh() if ssh is None else ssh
    if ssh:
        return None
    if wsl:
        if which("wslview"):
            return ["wslview", url]
        explorer = which("explorer.exe") or (str(_EXPLORER) if _EXPLORER.exists() else None)
        return [explorer, url] if explorer else None
    if not (environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY")) or not which("xdg-open"):
        return None
    user = environ.get("SUDO_USER")
    if os.geteuid() == 0 and user and user != "root" and which("runuser"):
        return ["runuser", "-u", user, "--", "xdg-open", url]
    return ["xdg-open", url]


def open_url(url: str) -> bool:
    """Starts the browser on url, detached and silent (nothing it prints may
    reach the panel's terminal). False when there is no browser here."""
    argv = opener_command(url)
    if not argv:
        return False
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    return True


def open_folder(path: str) -> bool:
    """A folder in Windows Explorer (WSL only): \\\\wsl.localhost\\... path."""
    if not _is_wsl() or over_ssh():
        return False
    explorer = shutil.which("explorer.exe") or (str(_EXPLORER) if _EXPLORER.exists() else None)
    if not explorer or not shutil.which("wslpath"):
        return False
    try:
        win = subprocess.run(["wslpath", "-w", path], capture_output=True, text=True, timeout=5).stdout.strip()
        if not win:
            return False
        subprocess.Popen([explorer, win], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return True
