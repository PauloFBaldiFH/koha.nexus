"""Settings, from NEXUS_GATEWAY_* environment variables (the systemd unit
sets them)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_TARGETS = Path(__file__).with_name("targets.json")
# The repository's GitHub Releases; NEXUS_GATEWAY_RELEASES_API overrides it.
RELEASES_API = "https://api.github.com/repos/PauloFBaldiFH/koha.nexus/releases?per_page=30"
STATE = Path("/var/lib/koha-nexus-enrich")


def _env(name: str, default: str) -> str:
    return os.environ.get(f"NEXUS_GATEWAY_{name}", "").strip() or default


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 5000
    static_db: Path = STATE / "static.db"
    learned_db: Path = STATE / "learned.db"
    targets: Path = PACKAGE_TARGETS
    live: bool = True                 # search native targets when the local data has nothing
    live_timeout: float = 6.0         # the reply waits this long; slower answers go to learned.db
    live_grace: float = 30.0          # how long a late answer may still arrive
    learned_days: int = 30            # a learned answer older than this is searched again
    max_records: int = 50
    releases_api: str = RELEASES_API
    mirror: str = ""                  # e.g. the R2 bucket's public URL

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(host=_env("HOST", "127.0.0.1"), port=int(_env("PORT", "5000")),
                   static_db=Path(_env("STATIC_DB", str(STATE / "static.db"))),
                   learned_db=Path(_env("LEARNED_DB", str(STATE / "learned.db"))),
                   targets=Path(_env("TARGETS", str(PACKAGE_TARGETS))),
                   live=_env("LIVE", "1") not in ("0", "no", "false", "off"),
                   live_timeout=float(_env("LIVE_TIMEOUT", "6")), live_grace=float(_env("LIVE_GRACE", "30")),
                   learned_days=int(_env("LEARNED_DAYS", "30")), max_records=int(_env("MAX_RECORDS", "50")),
                   releases_api=_env("RELEASES_API", RELEASES_API), mirror=_env("MIRROR", ""))
