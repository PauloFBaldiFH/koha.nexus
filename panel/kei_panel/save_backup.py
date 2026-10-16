"""The rules of the save step of a manual backup (screens/save_backup.py),
kept apart from the screen so they are tested without one.

  folder      where the file goes on this server: ~/backups by default,
              created when the save starts; a path typed, pasted or dropped
              is read like the other path boxes (transfer.dropped_path)
  WSL2        told by /proc/version (env._is_wsl). Only there the Windows
              side is reachable: the Downloads folder (transfer) and a
              folder picked in a Windows window (powershell.exe, run in a
              thread by the screen). Elsewhere those buttons are not shown.
  SCP         the command the person runs on their own computer to fetch the
              file; the host is the server's address the installer knows,
              else this machine's host name.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

from . import transfer
from .env import _is_wsl

SUBDIR = "backups"
POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"

# The Windows folder picker. It needs a single-threaded apartment (-STA);
# the chosen folder is printed, nothing is printed when the person cancels.
PICK_FOLDER_SCRIPT = (
    "Add-Type -AssemblyName System.Windows.Forms; "
    "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
    "$d.Description = 'Save the backup in'; $d.ShowNewFolderButton = $true; "
    "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
)


def is_wsl() -> bool:
    """WSL2: the Windows disk is mounted here (env._is_wsl, /proc/version)."""
    return _is_wsl()


def default_folder(home: str) -> Path:
    """~/backups of the person who runs the panel (created when saving)."""
    return Path(home or "/root") / SUBDIR


def folder_problem(text: str, default: Path) -> tuple[Path | None, str]:
    """The folder typed in the box, or the reason it cannot be used (a
    message key). Empty means the default folder. Nothing is created here:
    the folder that does not exist yet must have an existing parent that
    can take it."""
    raw = (text or "").strip()
    if not raw:
        return default, ""
    path = Path(transfer.dropped_path(raw))
    if not path.is_absolute():
        return None, "Use the full path, starting with /."
    if path.exists():
        if not path.is_dir():
            return None, "That is a file, not a folder."
        if not os.access(path, os.W_OK):
            return None, "That folder cannot be written."
        return path, ""
    parent = next(p for p in path.parents if p.exists())
    if not parent.is_dir() or not os.access(parent, os.W_OK):
        return None, "That folder cannot be created here."
    return path, ""


def scp_host(server_ip: str | None) -> str:
    """The address a computer outside this server uses: the server's address
    the installer knows, else this machine's host name."""
    return server_ip or socket.gethostname()


def scp_command(user: str, host: str, remote_path: str) -> str:
    """The command run on the person's computer; the quotes keep blanks in
    the path, and the dot is the current folder there."""
    return f'scp {user}@{host}:"{remote_path}" .'


def windows_folder_dialog() -> str:
    """The Windows folder picker, through powershell.exe. It waits for the
    person's answer, so it runs in a thread. "" when nothing was chosen."""
    ps = shutil.which("powershell.exe") or POWERSHELL
    try:
        done = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-STA", "-Command", PICK_FOLDER_SCRIPT],
                              capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout


def picked_folder(output: str) -> Path | None:
    """The folder the Windows picker printed (a Windows path, C:\\...), as a
    path of this WSL2 system (/mnt/c/...); None when nothing was chosen or
    the folder is not there."""
    text = (output or "").strip()
    if not text:
        return None
    path = Path(transfer.dropped_path(text))
    return path if path.is_dir() else None
