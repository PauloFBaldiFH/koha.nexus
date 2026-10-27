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


SECRET_HEADERS = ("authorization", "x-api-key", "x-goog-api-key", "api-key")


def _origin(url: str) -> tuple[str, str, int | None]:
    u = urllib.parse.urlsplit(url)
    port = u.port or {"http": 80, "https": 443}.get(u.scheme.lower())
    return u.scheme.lower(), (u.hostname or "").lower(), port


class _KeepKeysHome(urllib.request.HTTPRedirectHandler):
    """Follows redirects as urllib does, but a key header is only sent again
    to the same scheme, host and port: never to another server, never from
    HTTPS down to HTTP."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and _origin(newurl) != _origin(req.full_url):
            for name in list(new.headers):
                if name.lower() in SECRET_HEADERS:
                    del new.headers[name]
        return new


def _open(req: urllib.request.Request, timeout: float):
    """urlopen, but never through an HTTP proxy for this machine or the local
    network (a proxy set for apt would answer for Ollama instead), and never
    with a key sent on to another server by a redirect."""
    host = urllib.parse.urlsplit(req.full_url).hostname or ""
    if aiconf.is_local_host(host):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), _KeepKeysHome()).open(req, timeout=timeout)
    return urllib.request.build_opener(_KeepKeysHome()).open(req, timeout=timeout)


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


# ----------------------------------------------------------------------
# One chat turn (the server helper): JSON answers, as the AI assistant
# ----------------------------------------------------------------------
OLLAMA_CTX = 16384


def chat_endpoint(c: dict[str, str]) -> str:
    """endpoint in KohaEasy::Assistant."""
    b = base(c)
    if c["provider"] == "anthropic":
        return b + "/v1/messages"
    if c["provider"] == "ollama":
        return b + "/api/chat"
    return b + "/chat/completions"


def chat_body(c: dict[str, str], messages: list[dict[str, str]]) -> dict:
    """request_body in KohaEasy::Assistant: the model is asked for one JSON
    object (json mode where the provider has one)."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [dict(m) for m in messages if m["role"] != "system"]
    p, model = c["provider"], aiconf.chat_model(c)
    if p == "anthropic":
        alt: list[dict[str, str]] = []        # user / assistant turns must alternate
        for m in turns:
            if alt and alt[-1]["role"] == m["role"]:
                alt[-1]["content"] += "\n\n" + m["content"]
            else:
                alt.append(m)
        return {"model": model, "max_tokens": 2000, "system": system, "messages": alt}
    msgs = [{"role": "system", "content": system}] + turns
    if p == "ollama":
        return {"model": model, "stream": False, "format": "json",
                "options": {"temperature": 0, "num_ctx": OLLAMA_CTX}, "messages": msgs}
    body: dict = {"model": model, "messages": msgs}
    if p == "openai":
        body |= {"response_format": {"type": "json_object"}, "max_completion_tokens": 4000}
    elif p == "gemini":
        body |= {"response_format": {"type": "json_object"}, "temperature": 0, "max_tokens": 8192}
    else:
        body |= {"temperature": 0, "max_tokens": 2000}
    return body


def reply_text(provider: str, d) -> str:
    """reply_text in KohaEasy::Assistant."""
    if not isinstance(d, dict):
        return ""
    if provider == "anthropic":
        return "".join(b.get("text") or "" for b in d.get("content") or []
                       if isinstance(b, dict) and b.get("type") == "text")
    if provider == "ollama":
        m = d.get("message")
        return (m.get("content") or "") if isinstance(m, dict) else ""
    choices = d.get("choices")
    m = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    if not isinstance(m, dict):
        return ""
    content = m.get("content")
    if isinstance(content, list):
        return "".join(x.get("text") or "" for x in content if isinstance(x, dict))
    return content or ""


def chat(c: dict[str, str], messages: list[dict[str, str]], timeout: float = 120) -> str:
    """Sends the conversation, returns the model's text. BLOCKS."""
    problem = aiconf.endpoint_problem(c)
    if problem:
        raise RuntimeError(aiconf.PROBLEMS[problem])
    p, token = c["provider"], c.get("token", "")
    if p == "ollama":
        try:
            ollama_keep_only(c["url"], [aiconf.chat_model(c)])
        except RuntimeError:
            pass
    headers = {"User-Agent": UA, "Content-Type": "application/json"}
    if p == "anthropic":
        headers |= {"x-api-key": token, "anthropic-version": "2023-06-01"}
    elif token and p != "ollama":
        headers["Authorization"] = f"Bearer {token}"
    url = chat_endpoint(c)
    req = urllib.request.Request(url, data=json.dumps(chat_body(c, messages)).encode(), method="POST",
                                 headers=headers)
    try:
        with _open(req, timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from {url}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"{_reason(e)} ({url})") from None
    except ValueError:
        raise RuntimeError(f"{url}: the answer is not JSON") from None
    return reply_text(p, data)
