"""Settings of the AI cataloguing tabs (vision.conf), shared with the web UI.

Same file and rules as KohaEasy::Cataloguing::Vision in the installer:
key=value lines, unknown keys ignored, provider defaults filled in, written
atomically with mode 0600. The owner of an existing file is kept, so the
staff interface (Plack, the instance user) can still read it after the
panel (root) saves it.

Keys of the other providers live next to it, in ai-keys.conf (same
rules, owner root): switching provider in the panel brings back the key
typed for it before, and vision.conf only ever holds the active one, as the
staff interface expects. A key is never shown again once saved: mask()
gives the panel (and anything diagnostic) its last four characters only.

The HTTP side (connection test, Ollama) is in aiclient.py.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULTS = {
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini"),
    "anthropic": ("https://api.anthropic.com", "claude-sonnet-5"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "ollama": ("http://localhost:11434", "qwen2.5vl:7b"),
    "compatible": ("http://localhost:1234/v1", ""),
}
PROVIDERS = tuple(DEFAULTS)
# Shown in the provider selector, local first.
LABELS = {
    "ollama": "Local Ollama",
    "gemini": "Google Gemini",
    "openai": "OpenAI",
    "anthropic": "Anthropic Claude",
    "compatible": "Other (OpenAI-compatible)",
}
SELECTOR_ORDER = ("ollama", "gemini", "openai", "anthropic", "compatible")
# Where each company hands out its keys (shown under the key field).
KEY_HELP = {
    "gemini": "https://aistudio.google.com/apikey",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "compatible": "LM Studio, vLLM, llama.cpp, OpenRouter...",
    "ollama": "",
}
CONF_KEYS = ("provider", "url", "model", "token", "timeout", "max_px", "lang", "org_code",
             "table", "ddc_edition", "country")


def conf_path(instance: str) -> Path:
    return Path(f"/var/lib/koha/{instance}/kei-marc-replace/vision.conf")


def keys_path(conf: Path) -> Path:
    return conf.with_name("ai-keys.conf")


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
    lines = [f"{k}={_clean(c.get(k, ''))}" for k in CONF_KEYS]
    _write_private(path, "# koha-easy-installer: AI cataloguing settings (marc_replace.pl / Library tools)", lines)


def _clean(v: object) -> str:
    return str(v).replace("\r", "").replace("\n", "")


def _write_private(path: Path, header: str, lines: list[str]) -> None:
    """Atomic write, mode 0600, keeping the owner of an existing file."""
    owner = None
    if path.exists():
        st = path.stat()
        owner = (st.st_uid, st.st_gid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(header + "\n")
        for line in lines:
            fh.write(line + "\n")
    if owner and hasattr(os, "chown"):
        try:
            os.chown(tmp, *owner)
        except PermissionError:
            pass
    os.replace(tmp, path)


# ----------------------------------------------------------------------
# Keys of every provider (ai-keys.conf)
# ----------------------------------------------------------------------
def load_keys(path: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.partition("=")
            if sep and k.endswith("_token") and k[:-6] in PROVIDERS and v:
                keys[k[:-6]] = v
    except OSError:
        pass
    return keys


def save_keys(path: Path, keys: dict[str, str]) -> None:
    lines = [f"{p}_token={_clean(keys[p])}" for p in PROVIDERS if keys.get(p)]
    _write_private(path, "# koha-easy-installer: API keys of the AI providers (panel only)", lines)


def save_all(path: Path, c: dict[str, str]) -> None:
    """vision.conf with the active provider, and its key in ai-keys.conf."""
    kpath = keys_path(path)
    keys = load_keys(kpath)
    if c.get("token"):
        keys[c["provider"]] = c["token"]
    elif c["provider"] in keys:
        del keys[c["provider"]]
    save(path, c)
    if keys or kpath.exists():
        save_keys(kpath, keys)


def key_for(path: Path, provider: str) -> str:
    """The key saved for provider: vision.conf's when it is the active one."""
    c = load(path)
    if c["provider"] == provider and c["token"]:
        return c["token"]
    return load_keys(keys_path(path)).get(provider, "")


def mask(token: str) -> str:
    """What the panel shows of a saved key: never more than its last 4."""
    if not token:
        return ""
    return "••••" + (token[-4:] if len(token) >= 12 else "")


# ----------------------------------------------------------------------
# Checks before saving (endpoint_problem in KohaEasy::Cataloguing::Vision)
# ----------------------------------------------------------------------
_URL = re.compile(r"^(https?)://([A-Za-z0-9.-]+)(?::\d{1,5})?(?:/\S*)?$")
_LAN = re.compile(r"^(localhost|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+"
                  r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$")


def is_local_host(host: str) -> bool:
    host = host.lower()
    return bool(_LAN.match(host)) or bool(re.search(r"\.(local|lan|internal|home\.arpa)$", host)) \
        or "." not in host


def needs_token(provider: str, host: str = "") -> bool:
    return provider in ("anthropic", "gemini") or (provider == "openai" and not is_local_host(host))


def endpoint_problem(c: dict[str, str]) -> str:
    """'' when usable, else URL / TOKEN_PLAIN / NO_TOKEN (same codes as Perl)."""
    m = _URL.match(c.get("url", ""))
    if not m:
        return "URL"
    scheme, host = m.group(1).lower(), m.group(2).lower()
    token = c.get("token", "")
    if scheme == "http" and token and not is_local_host(host):
        return "TOKEN_PLAIN"
    if not token and needs_token(c.get("provider", ""), host):
        return "NO_TOKEN"
    return ""


PROBLEMS = {
    "URL": "The server address must start with http:// or https://.",
    "TOKEN_PLAIN": "The key would travel unencrypted: use https:// for a server outside the local network.",
    "NO_TOKEN": "This provider needs an API key.",
}
