"""Settings, from the environment (the unit reads the panel's .env).

    NEXUS_ONDEMAND_DIRECT_LIST   the direct server list (default: the checkout's)
    NEXUS_ONDEMAND_HEALTH_DB     health.db (default: the enrichment state folder)
    KEI_ONDEMAND_KOHA_NEXUS      1: also query sru.koha.nexus / catalog.koha.nexus
                                 after the direct servers (default 0, off)
    KEI_ONDEMAND_STATIC          0: do not fall back on the local static.db
                                 (default 1, on; a file read, no network)

The service's own (service.Settings.from_env):
    KEI_ONDEMAND_PARALLEL        records searched at once, 1 to 8 (default 4)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .targets import DEFAULT_LIST

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

    @classmethod
    def from_env(cls, env=os.environ) -> "Settings":
        return cls(direct_list=Path(env.get("NEXUS_ONDEMAND_DIRECT_LIST") or DEFAULT_LIST),
                   health_db=Path(env.get("NEXUS_ONDEMAND_HEALTH_DB") or STATE / "health.db"),
                   koha_nexus=_flag(env, "KEI_ONDEMAND_KOHA_NEXUS", False),
                   static=_flag(env, "KEI_ONDEMAND_STATIC", True))
