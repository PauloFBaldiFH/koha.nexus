"""Settings of the AI cataloguing tabs (vision.conf), shared with the web UI.

Same file and rules as KohaEasy::Cataloguing::Vision in the installer:
key=value lines, unknown keys ignored, provider defaults filled in, written
atomically with mode 0600. The owner of an existing file is kept, so the
staff interface (Plack, the instance user) can still read it after the
panel (root) saves it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULTS = {
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini"),
    "anthropic": ("https://api.anthropic.com", "claude-sonnet-5"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "ollama": ("http://localhost:11434", "qwen2.5vl:7b"),
    "compatible": ("http://localhost:1234/v1", ""),
}
PROVIDERS = tuple(DEFAULTS)
CONF_KEYS = ("provider", "url", "model", "token", "timeout", "max_px", "lang", "org_code",
             "table", "ddc_edition", "country")


def conf_path(instance: str) -> Path:
    return Path(f"/var/lib/koha/{instance}/kei-marc-replace/vision.conf")


def with_defaults(c: dict[str, str]) -> dict[str, str]:
    c = dict(c)
    if c.get("provider") not in PROVIDERS:
        c["provider"] = "openai"
    url, model = DEFAULTS[c["provider"]]
    c["url"] = c.get("url") or url
    c["model"] = c.get("model") or model
    for k in CONF_KEYS:
        c.setdefault(k, "")
    return c


def load(path: Path) -> dict[str, str]:
    c: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k in CONF_KEYS:
                c[k] = v
    except OSError:
        pass
    return with_defaults(c)


def save(path: Path, c: dict[str, str]) -> None:
    owner = None
    if path.exists():
        st = path.stat()
        owner = (st.st_uid, st.st_gid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("# koha-easy-installer: AI cataloguing settings (marc_replace.pl / Library tools)\n")
        for k in CONF_KEYS:
            v = str(c.get(k, "")).replace("\r", "").replace("\n", "")
            fh.write(f"{k}={v}\n")
    if owner and hasattr(os, "chown"):
        try:
            os.chown(tmp, *owner)
        except PermissionError:
            pass
    os.replace(tmp, path)


def list_models(c: dict[str, str], timeout: float = 15) -> list[str]:
    """Blocking: the models the provider offers (proves URL + token work).
    Run it in a thread worker, never on the event loop."""
    provider, url, token = c["provider"], c["url"].rstrip("/"), c.get("token", "")
    headers = {"User-Agent": "koha-easy-installer"}
    if provider == "anthropic":
        endpoint = url.removesuffix("/v1") + "/v1/models"
        headers |= {"x-api-key": token, "anthropic-version": "2023-06-01"}
    elif provider == "ollama":
        endpoint = url + "/api/tags"
    else:
        endpoint = url + "/models"
        if token:
            headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from {endpoint}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"{endpoint}: {getattr(e, 'reason', e)}") from None
    items = data.get("models") or data.get("data") or []
    return [m.get("id") or m.get("name") or "?" for m in items if isinstance(m, dict)]
