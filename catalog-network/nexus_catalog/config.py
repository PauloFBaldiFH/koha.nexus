"""Settings, read once from the environment (NEXUS_CATALOG_*)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8088
    db_path: Path = Path("/var/lib/koha-nexus-catalog/catalog.db")
    # Sync tokens: "name:token,name2:token2" (or bare tokens), and/or a file
    # of "name token" lines, re-read when it changes (no restart to add a library).
    tokens: str = ""
    tokens_file: Path | None = None
    max_records: int = 50          # SRU maximumRecords ceiling
    max_body: int = 20_000_000     # bytes of one sync request
    max_sync_records: int = 1000   # records in one sync request
    max_record_bytes: int = 200_000
    database_title: str = "Rede koha.nexus (Catalogação Compartilhada)"

    @classmethod
    def from_env(cls) -> "Settings":
        tokens_file = os.environ.get("NEXUS_CATALOG_TOKENS_FILE", "").strip()
        return cls(
            host=os.environ.get("NEXUS_CATALOG_HOST", cls.host),
            port=_int("NEXUS_CATALOG_PORT", cls.port),
            db_path=Path(os.environ.get("NEXUS_CATALOG_DB", "").strip() or cls.db_path),
            tokens=os.environ.get("NEXUS_CATALOG_TOKENS", ""),
            tokens_file=Path(tokens_file) if tokens_file else None,
            max_records=_int("NEXUS_CATALOG_MAX_RECORDS", cls.max_records),
            max_body=_int("NEXUS_CATALOG_MAX_BODY", cls.max_body),
            max_sync_records=_int("NEXUS_CATALOG_MAX_SYNC_RECORDS", cls.max_sync_records),
            database_title=os.environ.get("NEXUS_CATALOG_TITLE", cls.database_title),
        )
