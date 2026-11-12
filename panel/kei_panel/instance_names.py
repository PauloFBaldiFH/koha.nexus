"""The visible names of the installations, for the installer (study 12, U6).

The name lives only in the instance registry (instance_registry.py, the same
code as nexus_core/instances.py). Naming an installation never reinstalls,
moves or renames anything: databases, volumes, directories, ports and
addresses stay as they are.

    python -m kei_panel.instance_names read SITE
        what each installed system is called: one "@@result
        system=APP|named|NAME" (in the registry) or "system=APP|proposed|NAME"
        (found, not named yet) per system, on stderr like every task value.
        Reads only.
    python -m kei_panel.instance_names json SITE
        {"koha": "Biblioteca Central", ...}: the registered names only, for
        --status-json. Reads only; "{}" when the registry cannot be read.
    python -m kei_panel.instance_names set APP SITE NAME
        the only writer: adopts the installation in the registry with NAME
        the first time (its references, nothing moved), renames it after.

SITE is the Koha instance the panel manages (config.sh's INSTANCE).
Standard library only: config.sh runs it without the panel's packages.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from .instance_registry import DEFAULT_REGISTRY, Registry, RegistryError, discover_legacy

APPS = ("koha", "tainacan", "dspace")
SITE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")


def source_of(app: str, site: str) -> str:
    return f"koha-native:{site}" if app == "koha" else f"{app}-docker:legacy"


def _paths() -> tuple[Registry, Path]:
    # Overridable for the tests only (a disposable root); the installer never sets them.
    root = Path(os.environ.get("KEI_INSTANCES_SYSTEM_ROOT") or "/")
    registry = Path(os.environ.get("KEI_INSTANCES_REGISTRY") or DEFAULT_REGISTRY)
    return Registry(registry), root


def found(site: str, root: Path) -> dict:
    """The installations on this server, by system (Koha: the panel's instance)."""
    rows = {}
    for candidate in discover_legacy(root):
        if candidate.source_key == source_of(candidate.application, site):
            rows[candidate.application] = candidate
    return rows


def registered(registry: Registry) -> dict:
    return {row.source_key: row for row in registry.list() if row.lifecycle != "removed"}


def emit(key: str, value: str) -> None:
    value = value.replace("\r", "").replace("\n", " ")
    print(f"@@result {key}={value}", file=sys.stderr)


def error(text: str) -> int:
    print(f"@@msg error Names\t{text}", file=sys.stderr)
    return 1


def read(site: str) -> int:
    registry, root = _paths()
    candidates = found(site, root)
    try:
        names = registered(registry)
    except RegistryError as problem:
        # Still said: the systems found, with the reason no name is shown.
        names = {}
        emit("registry", str(problem))
    for app in APPS:
        record = names.get(source_of(app, site))
        if record is not None:
            emit("system", f"{app}|named|{record.name}")
        elif app in candidates:
            emit("system", f"{app}|proposed|{candidates[app].name}")
    return 0


def as_json(site: str) -> int:
    registry, _root = _paths()
    try:
        names = registered(registry)
    except Exception:  # noqa: BLE001 - --status-json must stay valid JSON
        names = {}
    out = {app: names[source_of(app, site)].name for app in APPS if source_of(app, site) in names}
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return 0


def set_name(app: str, site: str, name: str) -> int:
    if app not in APPS:
        return error("Unknown system.")
    registry, root = _paths()
    try:
        record = registered(registry).get(source_of(app, site))
        if record is not None:
            record = registry.rename(record.id, name)
        else:
            candidate = found(site, root).get(app)
            if candidate is None:
                return error("This system was not found on this server; nothing was changed.")
            record = registry.adopt(candidate, name=name)
            if record.name != name.strip():
                # Adopted before under another name (two panels at once).
                record = registry.rename(record.id, name)
    except RegistryError as problem:
        return error(f"{problem} Nothing was changed.")
    emit("system", f"{app}|named|{record.name}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] in ("read", "json") and SITE.match(argv[1]):
        return read(argv[1]) if argv[0] == "read" else as_json(argv[1])
    if len(argv) == 4 and argv[0] == "set" and SITE.match(argv[2]):
        return set_name(argv[1], argv[2], argv[3])
    print("usage: instance_names read|json SITE | set APP SITE NAME", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
