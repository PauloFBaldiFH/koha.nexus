"""The monthly static.db: find the newest release, download it, check its
SHA-256, unpack it and swap it in, so the running gateway picks it up.

    python -m nexus_gateway update [--force] [--check]

Where it looks, in order:
  1. GitHub Releases of the repository: the newest release holding both
     nexus-enrich-YYYY.MM.db.zst and its .sha256;
  2. the mirror (NEXUS_GATEWAY_MIRROR, e.g. a Cloudflare R2 public bucket):
     MIRROR/latest.txt names the asset, MIRROR/<asset> and <asset>.sha256
     sit beside it.
The newer of the two wins; one that does not answer is skipped.

The swap is atomic: the new database is unpacked next to static.db
(static.db.part), checked (SQLite quick_check, schema version, at least
one record) and renamed over static.db. The gateway notices the new file on
its next search; searches already running finish on the old one. Nothing is
replaced when any step fails, and static.release records what is installed
so the same month is not downloaded twice.

Runs under koha-nexus-enrich-update.service (nice 19, idle I/O, 25 % CPU,
256 MB), started by its weekly timer and once after installation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from nexus_enrich.static import SCHEMA_VERSION

REPO = "PauloFBaldiFH/koha.nexus"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ASSET = re.compile(r"^nexus-enrich-(\d{4})\.(\d{2})\.db\.zst$")
CHUNK = 1 << 20
USER_AGENT = "koha.nexus-gateway"
MAX_ASSET = 4 << 30          # 4 GB: a larger file is not ours
MARGIN = 256 << 20           # free space left over after the swap


class UpdateError(Exception):
    """A step failed; static.db was not touched."""


@dataclass(frozen=True)
class Release:
    name: str                # nexus-enrich-YYYY.MM.db.zst
    url: str
    sha_url: str
    size: int = 0            # 0: unknown
    origin: str = "github"

    @property
    def month(self) -> tuple[int, int]:
        m = ASSET.match(self.name)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _get(url: str, timeout: float, accept: str = "*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    return urllib.request.urlopen(req, timeout=timeout)


def _read(url: str, timeout: float, limit: int = 4 << 20, accept: str = "*/*") -> bytes:
    with _get(url, timeout, accept) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise UpdateError(f"{url}: answer larger than {limit} bytes")
    return data


def latest_github(api: str = API, timeout: float = 30) -> Release | None:
    """The newest release with both files, or None when there is none."""
    releases = json.loads(_read(api, timeout, accept="application/vnd.github+json"))
    best = None
    for rel in releases if isinstance(releases, list) else []:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        assets = {a.get("name", ""): a for a in rel.get("assets") or []}
        for name, a in assets.items():
            sums = assets.get(name + ".sha256")
            if not ASSET.match(name) or sums is None:
                continue
            cand = Release(name, a["browser_download_url"], sums["browser_download_url"], int(a.get("size") or 0))
            if best is None or cand.month > best.month:
                best = cand
    return best


def latest_mirror(base: str, timeout: float = 30) -> Release | None:
    base = base.rstrip("/")
    name = _read(f"{base}/latest.txt", timeout, limit=4096).decode("utf-8", "replace").strip()
    if not ASSET.match(name):
        raise UpdateError(f"{base}/latest.txt does not name a release ({name[:60]!r})")
    return Release(name, f"{base}/{name}", f"{base}/{name}.sha256", origin="mirror")


def find(api: str = API, mirror: str = "", timeout: float = 30) -> tuple[Release | None, list[str]]:
    """(the newest release found, the errors of the places that failed)."""
    found, errors = [], []
    for origin, look in (("github", lambda: latest_github(api, timeout)),
                         ("mirror", lambda: latest_mirror(mirror, timeout) if mirror else None)):
        try:
            rel = look()
        except (urllib.error.URLError, OSError, ValueError, KeyError, UpdateError) as exc:
            errors.append(f"{origin}: {exc}")
            continue
        if rel is not None:
            found.append(rel)
    if not found:
        return None, errors
    # The newest month; on a tie GitHub (listed first) wins.
    return max(found, key=lambda r: r.month), errors


def expected_sha(rel: Release, timeout: float = 30) -> str:
    text = _read(rel.sha_url, timeout, limit=4096).decode("ascii", "replace").split()
    if not text or not re.fullmatch(r"[0-9a-fA-F]{64}", text[0]):
        raise UpdateError(f"{rel.sha_url}: no SHA-256 in it")
    if len(text) > 1 and text[1].lstrip("*") != rel.name:
        raise UpdateError(f"{rel.sha_url} names {text[1]}, not {rel.name}")
    return text[0].lower()


def download(rel: Release, dest: Path, timeout: float = 60) -> str:
    """The asset into DEST (written as DEST.part, renamed when complete);
    returns its SHA-256."""
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    size = 0
    try:
        with _get(rel.url, timeout) as resp, open(part, "wb") as out:
            for chunk in iter(lambda: resp.read(CHUNK), b""):
                size += len(chunk)
                if size > MAX_ASSET:
                    raise UpdateError(f"{rel.name}: larger than {MAX_ASSET} bytes")
                h.update(chunk)
                out.write(chunk)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    if rel.size and size != rel.size:
        part.unlink(missing_ok=True)
        raise UpdateError(f"{rel.name}: {size} bytes received, {rel.size} expected")
    os.replace(part, dest)
    return h.hexdigest()


def unpacked_size(asset: Path) -> int:
    """The database size the zstd frame header declares (0: not declared)."""
    import zstandard
    with open(asset, "rb") as fh:
        head = fh.read(18)
    try:
        size = zstandard.frame_content_size(head)
    except zstandard.ZstdError:
        return 0
    return size if size and size > 0 else 0


def check_db(path: Path) -> dict:
    """The checks a database passes before it replaces static.db."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        quick = conn.execute("PRAGMA quick_check").fetchone()[0]
        if quick != "ok":
            raise UpdateError(f"quick_check says {quick}")
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
        schema = row[0].decode() if row and isinstance(row[0], bytes) else (row[0] if row else None)
        if str(schema) != SCHEMA_VERSION:
            raise UpdateError(f"schema {schema}, this gateway reads {SCHEMA_VERSION}")
        versions = conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
        if not versions:
            raise UpdateError("no records in it")
        return {"versions": versions, "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]}
    except sqlite3.DatabaseError as exc:
        raise UpdateError(f"not a static.db: {exc}") from exc
    finally:
        conn.close()


def swap_in(asset: Path, target: Path) -> dict:
    """Unpack ASSET to TARGET.part, check it, rename it over TARGET."""
    import zstandard
    part = target.with_name(target.name + ".part")
    try:
        with open(asset, "rb") as src, open(part, "wb") as dst:
            zstandard.ZstdDecompressor().copy_stream(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        stats = check_db(part)
        os.replace(part, target)
    except zstandard.ZstdError as exc:
        part.unlink(missing_ok=True)
        raise UpdateError(f"{asset.name}: cannot unpack: {exc}") from exc
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    try:
        fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
    return stats


def installed(state: Path) -> dict:
    try:
        return json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update(static_db: Path, *, api: str = API, mirror: str = "", force: bool = False, check: bool = False,
           timeout: float = 60) -> dict:
    """One run. Returns {"status": "current" | "available" | "updated", ...};
    raises UpdateError when nothing could be installed."""
    static_db = Path(static_db)
    api = api or API
    state = static_db.with_name("static.release")
    rel, errors = find(api, mirror, timeout)
    if rel is None:
        raise UpdateError("no release found" + (f" ({'; '.join(errors)})" if errors else ""))
    have = installed(state)
    out = {"release": rel.name, "origin": rel.origin, "installed": have.get("name", "")}
    if have.get("name") == rel.name and static_db.exists() and not force:
        return {**out, "status": "current"}
    if check:
        return {**out, "status": "available"}
    static_db.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(static_db.parent).free
    if rel.size and free < rel.size + MARGIN:
        raise UpdateError(f"{free >> 20} MB free, the download needs {(rel.size + MARGIN) >> 20} MB")
    sha = expected_sha(rel, timeout)
    asset = static_db.with_name(rel.name)
    try:
        got = download(rel, asset, timeout)
        if got != sha:
            raise UpdateError(f"{rel.name}: SHA-256 {got} does not match {sha}")
        need = unpacked_size(asset)
        free = shutil.disk_usage(static_db.parent).free
        if need and free < need + MARGIN:
            raise UpdateError(f"{free >> 20} MB free, the database needs {(need + MARGIN) >> 20} MB")
        stats = swap_in(asset, static_db)
    finally:
        asset.unlink(missing_ok=True)
    record = {"name": rel.name, "sha256": sha, "origin": rel.origin,
              "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    tmp = state.with_name(state.name + ".part")
    tmp.write_text(json.dumps(record) + "\n", encoding="utf-8")
    os.replace(tmp, state)
    return {**out, **stats, "status": "updated", "installed": rel.name}
