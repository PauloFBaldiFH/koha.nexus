"""Moving backup files between this server and the person's computer,
without SCP or SFTP: the panel runs on the Koha server itself, so

  WSL       the Windows disk is here (/mnt/c): a file dropped on the panel
            is copied in, and a backup is copied out to the Windows
            Downloads folder, directly
  desktop   Linux with a screen: the Downloads folder of the person who ran
            sudo (the copy is then theirs)
  SSH       the person's computer is elsewhere: what was dropped is a path
            on that computer, so the panel shows the scp command instead

Copies run as thread jobs (tasks.run_with_loader) with the progress bar,
the size, the speed and the time left; a cancelled or failed copy leaves no
half file behind.
"""

from __future__ import annotations

import os
import pwd
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from .env import _is_wsl
from .i18n import t
from .opener import over_ssh
from .tasks import TaskFailed

BACKUP_SUFFIXES = (".sql", ".sql.gz")
CHUNK = 1024 * 1024
_WINDOWS_PATH = re.compile(r"^([A-Za-z]):[\\/](.*)$")
_WSL_SHARE = re.compile(r"^[\\/]{2}wsl(?:\.localhost|\$)[\\/][^\\/]+[\\/](.*)$", re.I)


def is_backup_name(name: str) -> bool:
    return name.lower().endswith(BACKUP_SUFFIXES)


def where() -> str:
    """"ssh", "wsl", "desktop" or "server" (no way to reach the person's disk)."""
    if over_ssh():
        return "ssh"
    if _is_wsl():
        return "wsl"
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return "desktop"
    return "server"


def dropped_path(text: str) -> str:
    """The path a terminal pastes when a file is dropped on it, as a path of
    this machine: quotes and backslash escapes removed, file:// URIs read,
    C:\\... and \\\\wsl.localhost\\Distro\\... turned into /mnt/c/... and /...."""
    line = (text or "").strip().splitlines()[0].strip() if (text or "").strip() else ""
    if len(line) >= 2 and line[0] == line[-1] and line[0] in "'\"":
        line = line[1:-1]
    if line.lower().startswith("file://"):
        line = unquote(urlparse(line).path)
        if re.match(r"^/[A-Za-z]:/", line):
            line = line[1:]
    m = _WSL_SHARE.match(line)
    if m:
        return "/" + m.group(1).replace("\\", "/")
    m = _WINDOWS_PATH.match(line)
    if m:
        return f"/mnt/{m.group(1).lower()}/" + m.group(2).replace("\\", "/")
    # Linux terminals escape spaces and quotes with a backslash.
    return re.sub(r"\\(.)", r"\1", line)


def on_windows_disk(path: str | Path) -> bool:
    return bool(re.match(r"^/mnt/[a-z]/", str(path)))


def _windows_downloads() -> Path | None:
    """The Downloads folder of the Windows user (it may have been moved)."""
    ps = shutil.which("powershell.exe") or "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    script = "(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path"
    try:
        win = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        if win:
            path = subprocess.run(["wslpath", "-u", win], capture_output=True, text=True,
                                  timeout=5).stdout.strip()
            if path and Path(path).is_dir():
                return Path(path)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        user = subprocess.run(["cmd.exe", "/c", "echo %USERNAME%"], capture_output=True, text=True,
                              timeout=10, cwd="/mnt/c").stdout.strip()
    except (OSError, subprocess.SubprocessError):
        user = ""
    guess = Path("/mnt/c/Users") / user / "Downloads" if user and "%" not in user else None
    return guess if guess and guess.is_dir() else None


def _desktop_user() -> pwd.struct_passwd | None:
    name = os.environ.get("SUDO_USER")
    if not name or name == "root":
        return None
    try:
        return pwd.getpwnam(name)
    except KeyError:
        return None


def _desktop_downloads() -> Path | None:
    user = _desktop_user()
    home = Path(user.pw_dir) if user else Path.home()
    try:
        argv = ["xdg-user-dir", "DOWNLOAD"]
        if user and os.geteuid() == 0 and shutil.which("runuser"):
            argv = ["runuser", "-u", user.pw_name, "--"] + argv
        found = subprocess.run(argv, capture_output=True, text=True, timeout=5).stdout.strip()
        if found and Path(found).is_dir() and Path(found) != home:
            return Path(found)
    except (OSError, subprocess.SubprocessError):
        pass
    guess = home / "Downloads"
    return guess if guess.is_dir() else None


def downloads_folder(place: str | None = None) -> Path | None:
    """Where "Download latest backup" saves, or None (SSH, a bare server)."""
    place = place or where()
    if place == "wsl":
        return _windows_downloads()
    if place == "desktop":
        return _desktop_downloads()
    return None


def free_target(folder: Path, name: str) -> Path:
    """name in folder, or name (2), name (3)... when it is taken."""
    target = folder / name
    stem, suffix = (name[:-7], ".sql.gz") if name.lower().endswith(".sql.gz") else (Path(name).stem, Path(name).suffix)
    n = 2
    while target.exists():
        target = folder / f"{stem} ({n}){suffix}"
        n += 1
    return target


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def stats_line(done: int, total: int, seconds: float) -> str:
    speed = done / seconds if seconds > 0 else 0.0
    left = (total - done) / speed if speed > 0 else None
    eta = f"{int(left) // 60:02d}:{int(left) % 60:02d}" if left is not None else "--:--"
    return f"{human_size(done)} / {human_size(total)} · {human_size(speed)}/s · {eta}"


def copy_file(src: Path, dst: Path, reporter, owner: pwd.struct_passwd | None = None) -> Path:
    """src to dst through dst.part, with progress; nothing is left at dst
    when the copy is cancelled or fails."""
    total = src.stat().st_size
    free = shutil.disk_usage(dst.parent).free
    if total > free:
        raise TaskFailed(t("Not enough free space: ${need} needed, ${free} free.", need=human_size(total),
                           free=human_size(free)))
    part = dst.with_name(dst.name + ".part")
    started, done = time.monotonic(), 0
    reporter.progress(0, total or 1)
    try:
        with open(src, "rb") as fin, open(part, "wb") as fout:
            while True:
                if reporter.cancelled:
                    raise InterruptedError("cancelled")
                chunk = fin.read(CHUNK)
                if not chunk:
                    break
                fout.write(chunk)
                done += len(chunk)
                reporter.progress(done, total or 1)
                reporter.status(stats_line(done, total, time.monotonic() - started))
        if owner is not None:
            os.chown(part, owner.pw_uid, owner.pw_gid)
        os.replace(part, dst)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise
    return dst


def desktop_owner(place: str) -> pwd.struct_passwd | None:
    """Who should own a file saved in a Linux Downloads folder."""
    return _desktop_user() if place == "desktop" and os.geteuid() == 0 else None
