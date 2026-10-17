"""Publishing a release asset: GitHub Releases, plus the mirror's latest.txt.

    GITHUB_TOKEN=... python -m enrich_build publish nexus-enrich-2026.10.db.zst

Creates (or reuses) the release tagged enrich-YYYY.MM and uploads the asset
and its .sha256, replacing files of the same name. The token needs
"contents: write" on the repository. Clients find the newest release with
both files (nexus_gateway.update).

It also writes latest.txt beside the asset: copied to the mirror together
with the asset and its .sha256 (rclone, or any S3 tool for Cloudflare R2),
it is what clients read there when GitHub does not answer.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "PauloFBaldiFH/koha.nexus"
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
ASSET = re.compile(r"^nexus-enrich-(\d{4}\.\d{2})\.db\.zst$")


class PublishError(Exception):
    pass


class GitHub:
    def __init__(self, token: str, repo: str = REPO, api: str = API, uploads: str = UPLOADS):
        if not token:
            raise PublishError("GITHUB_TOKEN is not set")
        self.token, self.repo, self.api, self.uploads = token, repo, api.rstrip("/"), uploads.rstrip("/")

    def call(self, method: str, url: str, body: bytes | None = None, ctype: str = "application/json"):
        req = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "koha.nexus-enrich-build",
            **({"Content-Type": ctype} if body is not None else {})})
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise PublishError(f"{method} {url}: HTTP {exc.code} {exc.read()[:300]!r}") from exc
        return json.loads(data) if data else {}

    def release(self, tag: str, month: str) -> dict:
        rel = self.call("GET", f"{self.api}/repos/{self.repo}/releases/tags/{tag}")
        if rel is None:
            body = {"tag_name": tag, "name": f"Enrichment database {month}",
                    "body": (f"static.db of {month} for the koha.nexus local gateway: nexus-enrich-{month}.db.zst "
                             "and its SHA-256. Installed by the koha-nexus-enrich-update timer."),
                    "draft": False, "prerelease": False, "make_latest": "false"}
            rel = self.call("POST", f"{self.api}/repos/{self.repo}/releases", json.dumps(body).encode())
        return rel

    def upload(self, rel: dict, path: Path, ctype: str) -> dict:
        for a in rel.get("assets") or []:
            if a.get("name") == path.name:
                self.call("DELETE", f"{self.api}/repos/{self.repo}/releases/assets/{a['id']}")
        url = (f"{self.uploads}/repos/{self.repo}/releases/{rel['id']}/assets?"
               + urllib.parse.urlencode({"name": path.name}))
        return self.call("POST", url, path.read_bytes(), ctype)


def publish(asset: Path, gh: GitHub) -> dict:
    m = ASSET.match(asset.name)
    if not m:
        raise PublishError(f"{asset.name}: not a nexus-enrich-YYYY.MM.db.zst")
    sums = asset.with_name(asset.name + ".sha256")
    if not sums.exists():
        raise PublishError(f"{sums.name} is missing: make the asset with python -m enrich_build release")
    from .release import read_sha256, sha256_file
    if sha256_file(asset) != read_sha256(sums):
        raise PublishError(f"{asset.name} does not match {sums.name}")
    month = m.group(1)
    rel = gh.release(f"enrich-{month}", month)
    gh.upload(rel, asset, "application/zstd")
    gh.upload(rel, sums, "text/plain")
    latest = asset.with_name("latest.txt")
    latest.write_text(asset.name + "\n", encoding="ascii")
    return {"release": rel.get("html_url", ""), "tag": f"enrich-{month}", "latest": str(latest)}
