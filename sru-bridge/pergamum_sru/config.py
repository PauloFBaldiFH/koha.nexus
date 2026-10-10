"""Settings, read once from the environment (PERGAMUM_SRU_*)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from zeus_sru.config import _float, _int
from zeus_sru.sru import MARCXML_URI

BASE_URL = "https://www.pergamum.pucpr.br/redepergamum/consultas/site_CRP/pesquisa.php"
# Pergamum answers a browser; the default python/httpx agent is not what the
# working script sent.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


@dataclass(frozen=True)
class Settings:
    base_url: str = BASE_URL
    timeout: float = 12.0         # seconds per Pergamum request (Koha waits 15)
    page_size: int = 50           # ids Pergamum lists per search (its "50" argument)
    concurrency: int = 5          # MARC records fetched at once
    cache_ttl: int = 600          # seconds a search or a record is reused
    cache_size: int = 512         # searches and records kept in memory
    max_records: int = 50         # SRU maximumRecords ceiling
    user_agent: str = USER_AGENT
    # The full URI, as in the spec tested against Koha with this bridge.
    # The Zeus bridge sends "marcxml"; set "marcxml" here if Koha shows hits
    # but no records.
    record_schema: str = MARCXML_URI

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.environ.get("PERGAMUM_SRU_BASE_URL", cls.base_url),
            timeout=_float("PERGAMUM_SRU_TIMEOUT", cls.timeout),
            page_size=max(1, _int("PERGAMUM_SRU_PAGE_SIZE", cls.page_size)),
            concurrency=max(1, _int("PERGAMUM_SRU_CONCURRENCY", cls.concurrency)),
            cache_ttl=_int("PERGAMUM_SRU_CACHE_TTL", cls.cache_ttl),
            cache_size=_int("PERGAMUM_SRU_CACHE_SIZE", cls.cache_size),
            max_records=_int("PERGAMUM_SRU_MAX_RECORDS", cls.max_records),
            user_agent=os.environ.get("PERGAMUM_SRU_USER_AGENT", cls.user_agent),
            record_schema=os.environ.get("PERGAMUM_SRU_RECORD_SCHEMA", cls.record_schema),
        )
