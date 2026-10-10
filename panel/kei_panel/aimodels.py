"""Model discovery for the AI providers: the live list from each provider's
own models endpoint (read with the key typed or saved), sorted into two
groups, and a built-in list when the live one cannot be read.

  Free / Accessible   free tier or lowest price: Gemini Flash and Flash-Lite,
                      Gemma, OpenAI mini/nano, Claude Haiku, anything local
  Advanced            needs a paid key or active billing: Gemini Pro, the
                      full OpenAI and Claude models

The split is a label to guide the choice, not a statement about the bill:
OpenAI and Anthropic charge every request (BILLING_NOTE), and each company
changes its free tier on its own.

Like aiclient, discover() BLOCKS: call it from a thread job of
run_with_loader. It never raises; a failure ends up in Discovery.reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import aiclient, aiconf

FREE, PAID = "free", "paid"

# Shown when the live list cannot be read (no key yet, offline, refused
# key). Each provider's newest "latest" aliases where it has them, so the
# list does not go stale with every release.
FALLBACK = {
    "gemini": ("gemini-flash-latest", "gemini-flash-lite-latest", "gemini-pro-latest"),
    "openai": ("gpt-5-mini", "gpt-5-nano", "gpt-5"),
    "anthropic": ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"),
    "ollama": tuple(m for m, _label, _use in aiconf.OLLAMA_PRESETS),
    "compatible": (),
}

# Not chat models: embeddings, speech, images, video, moderation...
_NOT_CHAT = re.compile(
    r"embed|tts|whisper|dall-?e|davinci|babbage|moderation|transcri|audio|realtime|image|imagen|veo|"
    r"aqa|lyria|robotics|search|codex|computer-use|deep-research|sora|learnlm|attribution", re.I)

# Advanced (paid) models of each cloud provider; everything else is free /
# accessible. Local providers (Ollama, OpenAI-compatible servers) are free.
_ADVANCED = {
    "gemini": re.compile(r"\bpro\b|-pro|ultra|deep-?think", re.I),
    "openai": re.compile(r"^(?!.*(mini|nano)).*$", re.I),
    "anthropic": re.compile(r"^(?!.*haiku).*$", re.I),
}

BILLING_NOTE = {
    "gemini": "Google AI Studio has a free tier for the Flash models (with daily limits); "
              "Pro models need billing turned on for the key's project.",
    "openai": "OpenAI bills every request: even the accessible models need credits on the account.",
    "anthropic": "Anthropic bills every request: even the accessible models need credits on the account.",
    "ollama": "Runs on this server: every model is free.",
    "compatible": "Models of your own server: no provider billing.",
}
PAID_BADGE = "💳"
PAID_WARNING = ("Advanced model: needs an active subscription or credits on ${provider}'s platform, "
                "otherwise every request is refused.")
FREE_HEADER = "Free / Accessible Models"
PAID_HEADER = "Advanced Models (Requires Paid API Key / Active Billing)"


@dataclass
class Model:
    id: str
    tier: str            # FREE | PAID


@dataclass
class Discovery:
    provider: str
    models: list[Model] = field(default_factory=list)
    live: bool = False   # read from the provider now; False: the built-in list
    reason: str = ""     # why the built-in list is shown

    def group(self, tier: str) -> list[Model]:
        return [m for m in self.models if m.tier == tier]


def tier(provider: str, model_id: str) -> str:
    rule = _ADVANCED.get(provider)
    return PAID if rule and rule.search(model_id) else FREE


def is_chat_model(model_id: str) -> bool:
    return bool(model_id) and not _NOT_CHAT.search(model_id)


def _version_key(model_id: str) -> tuple:
    """Newest first: the numbers in the name compared as numbers."""
    parts = re.split(r"(\d+)", model_id.lower())
    return tuple((0, -int(p)) if p.isdigit() else (1, p) for p in parts if p)


def sort_models(provider: str, ids: list[str]) -> list[Model]:
    """Chat models only, without repeats; free ones first, newest first."""
    seen = dict.fromkeys(i for i in ids if is_chat_model(i))
    models = [Model(i, tier(provider, i)) for i in seen]
    # "latest" aliases go before the dated versions of each group.
    return sorted(models, key=lambda m: (m.tier != FREE, "latest" not in m.id, _version_key(m.id)))


def fallback(provider: str, reason: str = "") -> Discovery:
    return Discovery(provider, sort_models(provider, list(FALLBACK.get(provider, ()))), False, reason)


def discover(c: dict[str, str], timeout: float = 15) -> Discovery:
    """The models the key in c can use; the built-in list (with the reason)
    when the provider cannot be asked."""
    provider = c.get("provider", "")
    problem = aiconf.endpoint_problem(c)
    if problem == "NO_TOKEN":
        return fallback(provider, "no API key yet")
    if problem:
        return fallback(provider, aiconf.PROBLEMS[problem])
    try:
        ids = aiclient.check_connection(c, timeout).models
    except RuntimeError as e:
        return fallback(provider, str(e))
    found = sort_models(provider, ids)
    if not found:
        return fallback(provider, "the provider listed no chat model")
    return Discovery(provider, found, True)


def from_ids(provider: str, ids: list[str]) -> Discovery:
    """A live list already read (Test connection) as a Discovery."""
    found = sort_models(provider, ids)
    return Discovery(provider, found, True) if found else fallback(provider, "the provider listed no chat model")
