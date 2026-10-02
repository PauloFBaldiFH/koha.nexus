"""One chat round trip with the configured provider (Module 1's settings).

Same endpoints, bodies and answer parsing as KohaEasy::Cataloguing::Vision
(_request_body, _endpoint, _reply_text), text only and JSON mode on, so a
provider that passes Module 1's connection test answers here too.

chat() BLOCKS: call it from a thread job of run_with_loader. Errors are
RuntimeError with the address and HTTP status only, never the key.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .. import aiclient

Messages = list[dict[str, str]]     # {"role": "system"|"user"|"assistant", "content": str}


def endpoint(c: dict[str, str]) -> str:
    b = aiclient.base(c)
    if c["provider"] == "anthropic":
        return b + "/v1/messages"
    if c["provider"] == "ollama":
        return b + "/api/chat"
    return b + "/chat/completions"


def _merged(messages: Messages) -> Messages:
    """Anthropic wants user/assistant turns alternating: join repeats."""
    out: Messages = []
    for m in messages:
        if out and out[-1]["role"] == m["role"]:
            out[-1] = {"role": m["role"], "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append(dict(m))
    return out


def request_body(c: dict[str, str], messages: Messages) -> dict:
    p = c["provider"]
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [m for m in messages if m["role"] != "system"]
    if p == "anthropic":
        return {"model": c["model"], "max_tokens": 2000, "system": system, "messages": _merged(turns)}
    msgs = [{"role": "system", "content": system}] + turns
    if p == "ollama":
        return {"model": c["model"], "stream": False, "format": "json", "options": {"temperature": 0},
                "messages": msgs}
    body: dict = {"model": c["model"], "messages": msgs}
    if p == "openai":
        body |= {"response_format": {"type": "json_object"}, "max_completion_tokens": 4000}
    elif p == "gemini":
        body |= {"response_format": {"type": "json_object"}, "temperature": 0, "max_tokens": 8192}
    else:
        body |= {"temperature": 0, "max_tokens": 2000}
    return body


def headers(c: dict[str, str]) -> dict[str, str]:
    h = {"User-Agent": aiclient.UA, "Content-Type": "application/json"}
    token = c.get("token", "")
    if c["provider"] == "anthropic":
        return h | {"x-api-key": token, "anthropic-version": "2023-06-01"}
    if token and c["provider"] != "ollama":
        h["Authorization"] = f"Bearer {token}"
    return h


def reply_text(provider: str, data) -> str:
    if not isinstance(data, dict):
        return ""
    if provider == "anthropic":
        return "".join(b.get("text", "") for b in data.get("content") or []
                       if isinstance(b, dict) and b.get("type") == "text")
    if provider == "ollama":
        m = data.get("message")
        return m.get("content", "") if isinstance(m, dict) else ""
    choices = data.get("choices") or []
    m = choices[0].get("message") if choices and isinstance(choices[0], dict) else None
    if not isinstance(m, dict):
        return ""
    content = m.get("content")
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def chat(c: dict[str, str], messages: Messages, timeout: float | None = None) -> str:
    from .. import aiconf

    problem = aiconf.endpoint_problem(c)
    if problem:
        raise RuntimeError(aiconf.PROBLEMS[problem])
    url = endpoint(c)
    seconds = timeout or float(c.get("timeout") or 0) or 120
    req = urllib.request.Request(url, data=json.dumps(request_body(c, messages)).encode(),
                                 headers=headers(c), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=seconds) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        hint = {400: "invalid request or model", 401: "key refused", 403: "key refused",
                404: "wrong address or model", 429: "rate limit: wait a moment"}.get(e.code, "")
        raise RuntimeError(f"HTTP {e.code} from {url}" + (f" ({hint})" if hint else "")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"{url}: {getattr(e, 'reason', e)}") from None
    except ValueError:
        raise RuntimeError(f"{url}: the answer is not JSON") from None
    return reply_text(c["provider"], data)
