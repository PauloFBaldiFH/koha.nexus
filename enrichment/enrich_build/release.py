"""The release asset: static.db -> nexus-enrich-YYYY.MM.db.zst + .sha256.

Compressed at level 19 without --long or --ultra, so a client decompresses
it with a window of a few MB, well inside the worker's 256 MB cap. The
.sha256 file is the line `sha256sum` prints ("HASH  NAME"), so
`sha256sum -c` checks it as well as verify() does.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path

LEVEL = 19
CHUNK = 1 << 20


def asset_name(month: str) -> str:
    """nexus-enrich-YYYY.MM.db.zst"""
    return f"nexus-enrich-{month}.db.zst"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def compress(db: Path, out: Path, level: int = LEVEL) -> tuple[Path, Path]:
    import zstandard
    cctx = zstandard.ZstdCompressor(level=level, write_checksum=True, threads=-1)
    tmp = out.with_name(out.name + ".part")
    with open(db, "rb") as src, open(tmp, "wb") as dst:
        cctx.copy_stream(src, dst, size=db.stat().st_size)
    os.replace(tmp, out)
    sums = out.with_name(out.name + ".sha256")
    sums.write_text(f"{sha256_file(out)}  {out.name}\n", encoding="ascii")
    return out, sums


def read_sha256(path: Path) -> str:
    return path.read_text(encoding="ascii").split()[0].strip().lower()


def verify(asset: Path, expected: str | None = None, check_db: bool = True) -> dict:
    """Hash check, then (optionally) decompress to a temporary file and run
    SQLite's integrity check and a count. Raises ValueError on a mismatch."""
    actual = sha256_file(asset)
    if expected is None:
        sums = asset.with_name(asset.name + ".sha256")
        expected = read_sha256(sums) if sums.exists() else None
    if expected is not None and actual != expected.lower():
        raise ValueError(f"{asset.name}: SHA-256 {actual} does not match {expected}")
    out = {"sha256": actual, "verified": expected is not None}
    if not check_db:
        return out
    import zstandard
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "static.db"
        with open(asset, "rb") as src, open(db, "wb") as dst:
            zstandard.ZstdDecompressor().copy_stream(src, dst)
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            out["integrity"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
            out["versions"] = conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
            out["headings"] = conn.execute("SELECT COUNT(*) FROM auth_headings").fetchone()[0]
            out["schema"] = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()[0]
        finally:
            conn.close()
        out["db_bytes"] = db.stat().st_size
    if out["integrity"] != "ok":
        raise ValueError(f"{asset.name}: integrity check says {out['integrity']}")
    return out
