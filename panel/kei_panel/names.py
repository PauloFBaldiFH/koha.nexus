"""The visible name of each installation, as the panel shows it (U6).

The names come from --status-json ("names", added in 1.5.202): only the
installations named in the registry. Without a name a system is called by
its own name ("Koha"), as before. Where a name is shown, it is "name ·
system", so that "Biblioteca Central · Koha" says both.

Six places show it: the sidebar, the dashboard tabs, Add system, the Backup
center, the Schedule center and the confirmations of a removal.
"""

from __future__ import annotations

SYSTEMS = {"koha": "Koha", "tainacan": "Tainacan", "dspace": "DSpace"}
MAX = 120


def valid(value: object) -> str:
    """A name of 1 to 120 printable characters (the registry's rule), else ""."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or len(value) > MAX or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value):
        return ""
    return value


def from_status(status: object) -> dict[str, str]:
    raw = status.get("names") if isinstance(status, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {key: name for key in SYSTEMS if (name := valid(raw.get(key)))}


def custom(names: dict[str, str], key: str) -> str:
    """The name given to it, "" when it has none (or just the system's)."""
    name = names.get(key, "")
    return "" if not name or name == SYSTEMS.get(key) else name


def short(names: dict[str, str], key: str) -> str:
    """The name alone ("Biblioteca Central"), or the system's ("Koha")."""
    return custom(names, key) or SYSTEMS.get(key, key)


def label(names: dict[str, str], key: str) -> str:
    """"Biblioteca Central · Koha", or "Koha" without a name."""
    name = custom(names, key)
    system = SYSTEMS.get(key, key)
    return f"{name} · {system}" if name else system


def joined(names: dict[str, str], keys, fallback: str) -> str:
    """Several systems ("Biblioteca Central + Museu Municipal"), or the
    translated fallback when none of them has a name."""
    if not any(custom(names, k) for k in keys):
        return fallback
    return " + ".join(short(names, k) for k in keys)


def of(app) -> dict[str, str]:
    return getattr(app, "instance_names", None) or {}
