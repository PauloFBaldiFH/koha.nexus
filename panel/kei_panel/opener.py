"""Opening a web address in the person's browser, from a panel that runs as
root on the Koha server.

Python's webbrowser module is not used: on a server it may pick a text
browser (www-browser, lynx, w3m) that takes the terminal away from the
panel, and as root it would start a desktop browser as root. Instead:

  WSL       explorer.exe <url> through WSL interop: Windows opens the
            default browser (wslview only where no explorer.exe is found)
  Windows   os.startfile (the panel run by a Windows Python)
  desktop   xdg-open as the person who ran sudo, when a display is there
  SSH       nothing here: the browser is on the other computer
Anything that cannot open a browser returns False and the caller copies the
address instead (OSC 52 lands on the person's own clipboard, also over SSH).

Windows programs run from WSL through the WSLInterop handler of
binfmt_misc. With systemd as PID 1 it can be lost (systemd-binfmt
re-registers its own list), and then explorer.exe cannot start at all:
_interop_ready() puts the handler back before a Windows program is run.
Windows programs start in C:\\Windows, not in a Linux folder (which Windows
would see as \\\\wsl.localhost\\...).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .env import _is_wsl

_EXPLORER = Path("/mnt/c/Windows/explorer.exe")
_WINDOWS_DIR = Path("/mnt/c/Windows")
_BINFMT = Path("/proc/sys/fs/binfmt_misc")
_INTEROP_RULE = ":WSLInterop:M::MZ::/init:PF"


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
        explorer = which("explorer.exe") or (str(_EXPLORER) if _EXPLORER.exists() else None)
        if explorer:
            return [explorer, url]
        return ["wslview", url] if which("wslview") else None
    if not (environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY")) or not which("xdg-open"):
        return None
    user = environ.get("SUDO_USER")
    if os.geteuid() == 0 and user and user != "root" and which("runuser"):
        return ["runuser", "-u", user, "--", "xdg-open", url]
    return ["xdg-open", url]


def _interop_ready(binfmt: Path = _BINFMT) -> bool:
    """Whether WSL can start Windows programs; when its binfmt_misc handler
    is missing and the panel runs as root, it is registered again (WSL's own
    rule). False when Windows programs cannot run from here."""
    try:
        if any(binfmt.glob("WSLInterop*")):
            return True
        if os.geteuid() != 0 or not (binfmt / "register").exists():
            return False
        (binfmt / "register").write_text(_INTEROP_RULE)
        return any(binfmt.glob("WSLInterop*"))
    except OSError:
        return False


def open_url(url: str) -> bool:
    """Starts the browser on url, detached and silent (nothing it prints may
    reach the panel's terminal). False when there is no browser here."""
    if os.name == "nt":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
        except OSError:
            return False
        return True
    argv = opener_command(url)
    return bool(argv) and _start(argv)


def open_folder(path: str) -> bool:
    """A folder in Windows Explorer (WSL only): \\\\wsl.localhost\\... path."""
    if not _is_wsl() or over_ssh():
        return False
    argv = folder_command(path, wsl=True, ssh=False)
    return bool(argv) and _start(argv)


def _windows_path(path: str) -> str:
    """path as Windows sees it (C:\\... or \\\\wsl.localhost\\...), "" when wslpath fails."""
    if not shutil.which("wslpath"):
        return ""
    try:
        return subprocess.run(["wslpath", "-w", path], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _start(argv: list[str]) -> bool:
    """Runs argv detached and silent. A Windows program (WSL) gets the
    interop handler checked first and C:\\Windows as its folder."""
    cwd = None
    if argv[0].lower().endswith(".exe"):
        if not _interop_ready():
            return False
        cwd = str(_WINDOWS_DIR) if _WINDOWS_DIR.is_dir() else None
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, cwd=cwd)
    except OSError:
        return False
    return True


def folder_command(path: str, wsl: bool | None = None, ssh: bool | None = None, which=shutil.which,
                   environ: dict[str, str] | None = None, winpath=_windows_path) -> list[str] | None:
    """The command that shows the folder path to the person: under WSL
    explorer.exe "$(wslpath -w PATH)"; on a Linux desktop xdg-open PATH (as
    the person who ran sudo); None over SSH or on a server with no screen."""
    environ = os.environ if environ is None else environ
    wsl = _is_wsl() if wsl is None else wsl
    ssh = over_ssh() if ssh is None else ssh
    if ssh:
        return None
    if wsl:
        explorer = which("explorer.exe") or (str(_EXPLORER) if _EXPLORER.exists() else None)
        win = winpath(path) if explorer else ""
        return [explorer, win] if explorer and win else None
    if not (environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY")) or not which("xdg-open"):
        return None
    user = environ.get("SUDO_USER")
    if os.geteuid() == 0 and user and user != "root" and which("runuser"):
        return ["runuser", "-u", user, "--", "xdg-open", path]
    return ["xdg-open", path]


def reveal_command(path: str, wsl: bool | None = None, ssh: bool | None = None, which=shutil.which,
                   environ: dict[str, str] | None = None, winpath=_windows_path) -> list[str] | None:
    """The command that shows a file selected in its folder: under WSL
    explorer.exe /select,"C:\\..." ; on a Linux desktop the folder that
    holds it (xdg-open cannot select); None where nothing can be shown."""
    wsl = _is_wsl() if wsl is None else wsl
    if wsl and not (over_ssh() if ssh is None else ssh):
        explorer = which("explorer.exe") or (str(_EXPLORER) if _EXPLORER.exists() else None)
        win = winpath(path) if explorer else ""
        # "/select," and the path as two words: Explorer reads them so, and a
        # path with spaces gets its quotes from WSL.
        return [explorer, "/select,", win] if explorer and win else None
    return folder_command(str(Path(path).parent), wsl=wsl, ssh=ssh, which=which, environ=environ, winpath=winpath)


def open_user_folder(path: str) -> bool:
    """The user's home folder in Windows Explorer (WSL) or the desktop's
    file manager. False when it cannot be shown here (SSH, no screen)."""
    argv = folder_command(path)
    return bool(argv) and _start(argv)


def reveal_file(path: str) -> bool:
    """A file shown selected in Windows Explorer (WSL), or its folder on a
    Linux desktop. False when nothing can show it here."""
    argv = reveal_command(path)
    return bool(argv) and _start(argv)
