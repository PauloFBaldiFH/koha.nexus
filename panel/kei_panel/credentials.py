"""Logins the panel needs but the repository must never carry.

A value comes from the environment first, then from a .env file of
KEY=value lines: KEI_ENV_FILE, else /etc/koha-easy-install/.env (root
only, 0600). .env.example at the top of the repository lists the names.
"""

from __future__ import annotations

import os
from pathlib import Path

from .env import CONFIG_DIR

ENV_FILE = CONFIG_DIR / ".env"


def env_file() -> Path:
    return Path(os.environ.get("KEI_ENV_FILE") or ENV_FILE)


def read_env_file(path: Path) -> dict[str, str]:
    """KEY=value lines; blank lines, # comments and a leading "export" are
    allowed, and one pair of matching quotes around the value is removed.
    A missing or unreadable file is an empty one."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def get(name: str, default: str = "") -> str:
    """The value of NAME: the environment wins over the .env file."""
    value = os.environ.get(name)
    if value:
        return value
    return read_env_file(env_file()).get(name, default)
