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
import re
import urllib.error
import urllib.parse
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
        # Ollama listens on 127.0.0.1 only; "localhost" may try IPv6 (::1)
        # first, which hangs instead of failing on some WSL2 set-ups.
        return re.sub(r"^(https?://)localhost(?=[:/]|$)", r"\g<1>127.0.0.1", u)
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


def _open(req: urllib.request.Request, timeout: float):
    """urlopen, but never through an HTTP proxy for this machine or the local
    network (a proxy set for apt would answer for Ollama instead)."""
    host = urllib.parse.urlsplit(req.full_url).hostname or ""
    if aiconf.is_local_host(host):
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _reason(e: Exception) -> str:
    reason = getattr(e, "reason", e)
    if isinstance(reason, ConnectionRefusedError) or "refused" in str(reason).lower():
        return "nothing is answering at this address (connection refused)"
    return str(reason)


def _get_json(url: str, headers: dict[str, str], timeout: float):
    req = urllib.request.Request(url, headers=headers)
    try:
        with _open(req, timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        hint = {400: "invalid request or key", 401: "key refused", 403: "key refused",
                404: "wrong address"}.get(e.code, "")
        raise RuntimeError(f"HTTP {e.code} from {url}" + (f" ({hint})" if hint else "")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # The reason first: the Connection card only has room for a line.
        raise RuntimeError(f"{_reason(e)} ({url})") from None
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
        with _open(req, timeout) as resp:
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
        raise RuntimeError(f"{_reason(e)} ({b}/api/pull)") from None


def same_model(a: str, b: str) -> bool:
    return a.removesuffix(":latest") == b.removesuffix(":latest")


def ollama_loaded(url: str, timeout: float = 5) -> list[str]:
    """The models Ollama holds in memory now (GET /api/ps), not the ones
    downloaded (/api/tags): each takes its RAM until it is unloaded."""
    b = base({"provider": "ollama", "url": url})
    data = _get_json(b + "/api/ps", {"User-Agent": UA}, timeout)
    items = data.get("models") if isinstance(data, dict) else None
    return [str(m.get("name") or m.get("model")) for m in items or []
            if isinstance(m, dict) and (m.get("name") or m.get("model"))]


def ollama_unload(url: str, model: str, timeout: float = 15) -> None:
    """Frees the memory of one model now (keep_alive 0); Ollama loads it
    again on demand, on the next request that names it."""
    b = base({"provider": "ollama", "url": url})
    body = json.dumps({"model": model, "keep_alive": 0}).encode()
    req = urllib.request.Request(b + "/api/generate", data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    try:
        with _open(req, timeout) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from {b}/api/generate") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"{_reason(e)} ({b}/api/generate)") from None


def ollama_keep_only(url: str, keep: list[str]) -> list[str]:
    """Unloads every model in memory that is not in keep (all of them when
    keep is empty); returns the ones unloaded. The AI assistant and MARC
    Replace do the same before each request, for their own model."""
    gone = []
    for model in ollama_loaded(url):
        if not any(same_model(model, k) for k in keep if k):
            ollama_unload(url, model)
            gone.append(model)
    return gone
