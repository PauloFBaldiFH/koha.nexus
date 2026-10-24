"""Settings, from the environment (the unit reads the panel's .env).

    NEXUS_ONDEMAND_DIRECT_LIST   the direct server list (default: the checkout's)
    NEXUS_ONDEMAND_HEALTH_DB     health.db (default: the enrichment state folder)
    KEI_ONDEMAND_KOHA_NEXUS      1: also query sru.koha.nexus / catalog.koha.nexus
                                 after the direct servers (default 0, off)
    KEI_ONDEMAND_STATIC          0: do not fall back on the local static.db
                                 (default 1, on; a file read, no network)
    KEI_ONDEMAND_STATIC_FIRST    0: do not search the local-first catalogues'
                                 static.db records before the servers
                                 (default 1, on; needs KEI_ONDEMAND_STATIC)
    NEXUS_GATEWAY_TARGETS        the gateway's targets.json, where the
                                 local-first catalogues are marked

The service's own (service.Settings.from_env):
    KEI_ONDEMAND_PARALLEL        records searched at once, 1 to 8 (default 4)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .targets import DEFAULT_LIST


def local_first_sources(env=os.environ) -> dict[str, str]:
    """{static.db source id: gateway target id} of the local-first
    catalogues (targets.json "local_first": UNESP, UFPR, UNIFESP, UnB, UFU),
    {} when the gateway's list cannot be read."""
    from nexus_gateway.config import PACKAGE_TARGETS
    from nexus_gateway.targets import TargetError, load, local_first_sources as sources

    try:
        return sources(load(Path(env.get("NEXUS_GATEWAY_TARGETS") or PACKAGE_TARGETS)))
    except (OSError, ValueError, TargetError):
        return {}

STATE = Path("/var/lib/koha-nexus-enrich")
_OFF = ("", "0", "no", "false", "off")


def _flag(env, name: str, default: bool) -> bool:
    value = env.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in _OFF


@dataclass
class Settings:
    direct_list: Path = DEFAULT_LIST
    health_db: Path = STATE / "health.db"
    koha_nexus: bool = False
    static: bool = True
    static_first: bool = True
    local_sources: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, env=os.environ) -> "Settings":
        return cls(direct_list=Path(env.get("NEXUS_ONDEMAND_DIRECT_LIST") or DEFAULT_LIST),
                   health_db=Path(env.get("NEXUS_ONDEMAND_HEALTH_DB") or STATE / "health.db"),
                   koha_nexus=_flag(env, "KEI_ONDEMAND_KOHA_NEXUS", False),
                   static=_flag(env, "KEI_ONDEMAND_STATIC", True),
                   static_first=_flag(env, "KEI_ONDEMAND_STATIC_FIRST", True),
                   local_sources=local_first_sources(env))
