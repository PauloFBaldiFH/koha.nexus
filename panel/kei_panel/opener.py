"""Opening a web address in the person's browser, from a panel that runs as
root on the Koha server.

Python's webbrowser module is not used: on a server it may pick a text
browser (www-browser, lynx, w3m) that takes the terminal away from the
panel, and as root it would start a desktop browser as root. Instead:

  WSL       explorer.exe <url> through WSL interop: Windows opens the
            default browser (wslview only where no explorer.exe is found)
  Windows   os.startfile (the panel run by a Windows Python)
  desktop   xdg-open as the person who ran sudo, when a display is there
  SSH       nothing here: the browser is on the other computer (also
            under sudo, which drops SSH_CONNECTION: an sshd above the panel)
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

import base64
import os
import shutil
import subprocess
from pathlib import Path

from .env import _is_wsl

_EXPLORER = Path("/mnt/c/Windows/explorer.exe")
_POWERSHELL = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
_WINDOWS_DIR = Path("/mnt/c/Windows")
_BINFMT = Path("/proc/sys/fs/binfmt_misc")
_INTEROP_RULE = ":WSLInterop:M::MZ::/init:PF"


def over_ssh(environ: dict[str, str] | None = None, proc: Path = Path("/proc")) -> bool:
    """Whether the panel runs in an SSH session. sudo without -E (and su)
    drop SSH_CONNECTION and SSH_TTY, so the processes above the panel are
    looked at too: an sshd among them is an SSH session."""
    environ = os.environ if environ is None else environ
    if environ.get("SSH_CONNECTION") or environ.get("SSH_TTY"):
        return True
    return _sshd_above(os.getpid(), proc)


def _sshd_above(pid: int, proc: Path = Path("/proc")) -> bool:
    for _ in range(64):
        if pid <= 1:
            return False
        try:
            stat = (proc / str(pid) / "stat").read_text()
        except OSError:
            return False
        # pid (comm) state ppid ...: comm may hold blanks and parentheses.
        comm = stat[stat.find("(") + 1:stat.rfind(")")]
        if comm.startswith("sshd"):
            return True
        try:
            pid = int(stat[stat.rfind(")") + 1:].split()[1])
        except (IndexError, ValueError):
            return False
    return False


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


def debian_terminal_command(distro: str, home_shell: str = "", which=shutil.which) -> list[str] | None:
    """Under WSL, the command that opens a Debian terminal of distro in a
    window of its own, as Windows' "Open Debian terminal" does: Windows
    Terminal (wt.exe -w new) when it is installed, else wsl.exe in a
    console window. PowerShell picks between them on the Windows side
    (wt.exe is an app alias Linux cannot see)."""
    ps = which("powershell.exe") or (str(_POWERSHELL) if _POWERSHELL.exists() else None)
    if not ps or not distro:
        return None
    tail = f"-d {distro} --cd ~" + (f" -- {home_shell} --shell" if home_shell else "")
    script = ("$w = Get-Command wt.exe -ErrorAction SilentlyContinue; "
              f"if ($w) {{ Start-Process $w.Source -ArgumentList '-w new --title \"Koha - Debian\" wsl.exe {tail}' }} "
              f"else {{ Start-Process wsl.exe -ArgumentList '{tail}' }}")
    # -EncodedCommand (UTF-16LE, base64): no quote is lost between Linux,
    # WSL interop and Windows PowerShell 5.1's own command-line parsing.
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [ps, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", encoded]


def open_debian_terminal() -> bool:
    """A Debian terminal in its own window (WSL only). False elsewhere, or
    when Windows programs cannot be started from here."""
    if not _is_wsl() or over_ssh():
        return False
    distro = os.environ.get("WSL_DISTRO_NAME") or "koha"
    window = "/usr/local/bin/koha-window"
    argv = debian_terminal_command(distro, window if os.access(window, os.X_OK) else "")
    return bool(argv) and _start(argv)


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
