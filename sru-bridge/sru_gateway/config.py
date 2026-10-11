"""Settings, read once from the environment (SRU_GATEWAY_*)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from zeus_sru.config import _float, _int

TARGETS_FILE = Path(__file__).with_name("targets.json")


@dataclass(frozen=True)
class Settings:
    targets_file: Path = TARGETS_FILE
    timeout: float = 25.0         # seconds per remote catalogue (Koha's rows wait 30)
    max_records: int = 50         # SRU maximumRecords ceiling
    user_agent: str = "koha.nexus-sru-gateway/1.0"

    @classmethod
    def from_env(cls) -> "Settings":
        path = os.environ.get("SRU_GATEWAY_TARGETS", "").strip()
        return cls(
            targets_file=Path(path) if path else cls.targets_file,
            timeout=_float("SRU_GATEWAY_TIMEOUT", cls.timeout),
            max_records=_int("SRU_GATEWAY_MAX_RECORDS", cls.max_records),
            user_agent=os.environ.get("SRU_GATEWAY_USER_AGENT", cls.user_agent),
        )
