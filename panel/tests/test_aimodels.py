"""Model discovery: live list from the provider, free/paid groups, built-in
list when the provider cannot be asked (no internet: a local fake server)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from kei_panel import aiconf, aimodels

SECRET = "sk-very-secret-key-1111"


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/v1/models" and self.headers.get("Authorization") == f"Bearer {SECRET}":
            data = {"data": [{"id": i} for i in (
                "gpt-5", "gpt-5-mini", "gpt-5-nano", "text-embedding-3-large", "whisper-1", "dall-e-3",
                "gpt-4o-mini-tts", "omni-moderation-latest", "gpt-5-mini")]}
            code = 200
        else:
            data, code = {"error": "bad key"}, 401
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_tiers_per_provider():
    assert aimodels.tier("gemini", "gemini-flash-latest") == aimodels.FREE
    assert aimodels.tier("gemini", "gemini-3-flash-preview") == aimodels.FREE
    assert aimodels.tier("gemini", "gemma-3-27b-it") == aimodels.FREE
    assert aimodels.tier("gemini", "gemini-pro-latest") == aimodels.PAID
    assert aimodels.tier("gemini", "gemini-3-pro-preview") == aimodels.PAID
    assert aimodels.tier("openai", "gpt-5-mini") == aimodels.FREE
    assert aimodels.tier("openai", "o4-mini") == aimodels.FREE
    assert aimodels.tier("openai", "gpt-5") == aimodels.PAID
    assert aimodels.tier("anthropic", "claude-haiku-5-5") == aimodels.FREE
    assert aimodels.tier("anthropic", "claude-opus-5-5") == aimodels.PAID
    assert aimodels.tier("ollama", "llama3.2:3b") == aimodels.FREE
    assert aimodels.tier("compatible", "anything-pro") == aimodels.FREE


def test_only_chat_models_free_first_newest_first():
    ids = ["gemini-2.0-flash", "gemini-3-pro-preview", "text-embedding-004", "imagen-4.0-generate-001",
           "gemini-3-flash-preview", "gemini-flash-latest", "veo-3.0-generate-001", "gemini-pro-latest"]
    got = [(m.id, m.tier) for m in aimodels.sort_models("gemini", ids)]
    assert got == [("gemini-flash-latest", "free"), ("gemini-3-flash-preview", "free"),
                   ("gemini-2.0-flash", "free"), ("gemini-pro-latest", "paid"), ("gemini-3-pro-preview", "paid")]


def test_live_list_with_the_key(server):
    found = aimodels.discover({"provider": "openai", "url": server, "model": "gpt-5-mini", "token": SECRET})
    assert found.live and not found.reason
    assert [m.id for m in found.group(aimodels.FREE)] == ["gpt-5-mini", "gpt-5-nano"]
    assert [m.id for m in found.group(aimodels.PAID)] == ["gpt-5"]


def test_built_in_list_without_key_or_with_a_refused_one(server):
    found = aimodels.discover({"provider": "gemini", "url": aiconf.DEFAULTS["gemini"][0], "model": "", "token": ""})
    assert not found.live and found.reason == "no API key yet"
    assert [m.id for m in found.models] == ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-pro-latest"]
    assert found.group(aimodels.PAID)[0].id == "gemini-pro-latest"
    refused = aimodels.discover({"provider": "openai", "url": server, "model": "", "token": "sk-wrong-key-000000"})
    assert not refused.live and "401" in refused.reason and "wrong" not in refused.reason
    assert {m.id for m in refused.models} == set(aimodels.FALLBACK["openai"])


def test_no_outdated_default_model():
    assert "2.5" not in aiconf.DEFAULTS["gemini"][1]
    for provider in ("gemini", "openai", "anthropic"):
        assert aiconf.DEFAULTS[provider][1] in aimodels.FALLBACK[provider]
