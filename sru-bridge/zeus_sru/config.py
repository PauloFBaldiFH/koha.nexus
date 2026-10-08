"""Settings, read once from the environment (ZEUS_SRU_*)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# The Zeus targets[N] ids Paulo listed (Biblioteca Nacional, UNICAMP, UNESP,
# USP, UFRGS, UFSC...). Ids 2, 4 and 15 are left out on purpose.
DEFAULT_TARGETS = (0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18)


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else default


def _targets(name: str) -> tuple[int, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return DEFAULT_TARGETS
    return tuple(int(t) for t in raw.replace(";", ",").split(",") if t.strip())


@dataclass(frozen=True)
class Settings:
    base_url: str = "https://catalogo.bu.ufsc.br/zbib/"
    targets: tuple[int, ...] = DEFAULT_TARGETS
    chunk_size: int = 15          # Zeus refuses more than 15 targets a request
    timeout: float = 30.0         # seconds, per Zeus request
    cache_ttl: int = 600          # seconds a search result is reused (paging)
    cache_size: int = 256         # searches kept in memory
    max_records: int = 50         # SRU maximumRecords ceiling
    user_agent: str = "koha-zeus-sru-bridge/1.0"
    extra_params: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.environ.get("ZEUS_SRU_BASE_URL", cls.base_url),
            targets=_targets("ZEUS_SRU_TARGETS"),
            chunk_size=max(1, min(15, _int("ZEUS_SRU_CHUNK_SIZE", cls.chunk_size))),
            timeout=_float("ZEUS_SRU_TIMEOUT", cls.timeout),
            cache_ttl=_int("ZEUS_SRU_CACHE_TTL", cls.cache_ttl),
            cache_size=_int("ZEUS_SRU_CACHE_SIZE", cls.cache_size),
            max_records=_int("ZEUS_SRU_MAX_RECORDS", cls.max_records),
            user_agent=os.environ.get("ZEUS_SRU_USER_AGENT", cls.user_agent),
        )
