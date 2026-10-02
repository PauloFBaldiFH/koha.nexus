"""The AI providers over HTTP: connection test and the local Ollama.

Every function here BLOCKS (urllib): call it from a thread job of
run_with_loader, never from an event handler. Errors are raised as
RuntimeError with the address and the HTTP status only: a key never ends
up in a message, a log line or the loader's log.

Same endpoints and rules as check_connection in KohaEasy::Cataloguing::Vision,
so a test passed here is a test the staff interface passes too.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from . import aiconf

UA = "koha-easy-installer"


@dataclass
class Check:
    endpoint: str
    models: list[str]
    found: bool       # the configured model is among them


def base(c: dict[str, str]) -> str:
    """_base in Vision.pm: trailing slashes and an optional /v1 handled once."""
    u = c["url"].rstrip("/")
    p = c["provider"]
    host_only = u.count("/") == 2           # scheme://host[:port]
    if p == "anthropic":
        return u.removesuffix("/v1")
    if p == "ollama":
        for suffix in ("/api", "/v1"):
            u = u.removesuffix(suffix)
        return u
    if p == "gemini":
        if host_only:
            return u + "/v1beta/openai"
        if u.endswith(("/v1", "/v1beta")):
            return u + "/openai"
        return u
    return u + "/v1" if host_only else u


def models_endpoint(c: dict[str, str]) -> tuple[str, dict[str, str]]:
    b, p, token = base(c), c["provider"], c.get("token", "")
    headers = {"User-Agent": UA}
    if p == "anthropic":
        return b + "/v1/models", headers | {"x-api-key": token, "anthropic-version": "2023-06-01"}
    if p == "ollama":
        return b + "/api/tags", headers
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return b + "/models", headers


def _get_json(url: str, headers: dict[str, str], timeout: float):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        hint = {400: "invalid request or key", 401: "key refused", 403: "key refused",
                404: "wrong address"}.get(e.code, "")
        raise RuntimeError(f"HTTP {e.code} from {url}" + (f" ({hint})" if hint else "")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"{url}: {getattr(e, 'reason', e)}") from None
    except ValueError:
        raise RuntimeError(f"{url}: the answer is not JSON (is this the right address?)") from None


def model_ids(provider: str, data) -> list[str]:
    if not isinstance(data, dict):
        return []
    items = data.get("models") if provider == "ollama" else data.get("data")
    ids = []
    for m in items or []:
        if isinstance(m, dict):
            name = (m.get("name") if provider == "ollama" else m.get("id")) or ""
            ids.append(name.removeprefix("models/"))     # Gemini lists "models/gemini-..."
    return ids


def model_found(provider: str, model: str, ids: list[str]) -> bool:
    if model in ids:
        return True
    return provider == "ollama" and ":" not in model and f"{model}:latest" in ids


def check_connection(c: dict[str, str], timeout: float = 15) -> Check:
    """Lists the provider's models: proves the address and the key work."""
    problem = aiconf.endpoint_problem(c)
    if problem:
        raise RuntimeError(aiconf.PROBLEMS[problem])
    url, headers = models_endpoint(c)
    ids = model_ids(c["provider"], _get_json(url, headers, timeout))
    return Check(url, ids, model_found(c["provider"], c["model"], ids))


# ----------------------------------------------------------------------
# Local Ollama
# ----------------------------------------------------------------------
OLLAMA_INSTALL = "curl -fsSL https://ollama.com/install.sh | sh"


def ollama_version(url: str, timeout: float = 5) -> str:
    """The running Ollama's version; RuntimeError when nothing answers."""
    b = base({"provider": "ollama", "url": url})
    data = _get_json(b + "/api/version", {"User-Agent": UA}, timeout)
    return str(data.get("version", "?")) if isinstance(data, dict) else "?"


def ollama_pull(url: str, model: str, on_progress: Callable[[str, int, int], None],
                cancelled: Callable[[], bool], timeout: float = 30) -> None:
    """Downloads a model into Ollama (POST /api/pull, streamed JSON lines).

    on_progress(status, completed, total) for every line; total is 0 while
    Ollama does not know the size. Stops when cancelled() turns true."""
    if not model:
        raise RuntimeError("no model name")
    b = base({"provider": "ollama", "url": url})
    body = json.dumps({"model": model, "stream": True}).encode()
    req = urllib.request.Request(b + "/api/pull", data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                if cancelled():
                    return
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get("error"):
                    raise RuntimeError(f"Ollama: {msg['error']}")
                on_progress(str(msg.get("status", "")), int(msg.get("completed") or 0),
                            int(msg.get("total") or 0))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from {b}/api/pull") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"{b}/api/pull: {getattr(e, 'reason', e)}") from None
