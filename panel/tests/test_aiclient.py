"""Connection test and Ollama against a local fake server (no internet)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from kei_panel import aiclient

SECRET = "sk-very-secret-key-0000"


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/version":
            return self._json(200, {"version": "0.12.3"})
        if self.path == "/api/tags":
            return self._json(200, {"models": [{"name": "qwen2.5vl:7b"}, {"name": "llama3:latest"}]})
        if self.path == "/v1/models":
            if self.headers.get("Authorization") != f"Bearer {SECRET}":
                return self._json(401, {"error": "bad key"})
            return self._json(200, {"data": [{"id": "models/gemini-2.5-flash"}, {"id": "gpt-x"}]})
        self._json(404, {})

    def do_POST(self):
        if self.path == "/api/pull":
            self.send_response(200)
            self.end_headers()
            for line in ({"status": "pulling manifest"},
                         {"status": "downloading", "completed": 50, "total": 100},
                         {"status": "downloading", "completed": 100, "total": 100},
                         {"status": "success"}):
                self.wfile.write(json.dumps(line).encode() + b"\n")
            return
        self._json(404, {})


@pytest.fixture(scope="module")
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_base_matches_the_perl_side():
    assert aiclient.base({"provider": "openai", "url": "http://h:1/"}) == "http://h:1/v1"
    assert aiclient.base({"provider": "anthropic", "url": "https://api.anthropic.com/v1"}) == \
        "https://api.anthropic.com"
    assert aiclient.base({"provider": "gemini", "url": "https://g.example.com/v1beta"}) == \
        "https://g.example.com/v1beta/openai"
    assert aiclient.base({"provider": "ollama", "url": "http://localhost:11434/api"}) == \
        "http://127.0.0.1:11434"


def test_ollama_models_and_latest_tag(server):
    check = aiclient.check_connection({"provider": "ollama", "url": server, "model": "llama3", "token": ""})
    assert check.models == ["qwen2.5vl:7b", "llama3:latest"] and check.found
    assert aiclient.ollama_version(server) == "0.12.3"


def test_key_checked_and_gemini_prefix_removed(server):
    conf = {"provider": "compatible", "url": server, "model": "gemini-2.5-flash", "token": SECRET}
    check = aiclient.check_connection(conf)
    assert check.found and "gemini-2.5-flash" in check.models


def test_refused_key_is_never_in_the_error(server):
    conf = {"provider": "compatible", "url": server, "model": "m", "token": "sk-wrong-key-1111"}
    with pytest.raises(RuntimeError) as e:
        aiclient.check_connection(conf)
    assert "401" in str(e.value) and "sk-wrong" not in str(e.value)


def test_unreachable_server_is_a_readable_error():
    with pytest.raises(RuntimeError):
        aiclient.ollama_version("http://127.0.0.1:9", timeout=2)


def test_ollama_pull_reports_progress(server):
    seen = []
    aiclient.ollama_pull(server, "qwen2.5vl:7b", lambda s, d, t: seen.append((s, d, t)), lambda: False)
    assert ("downloading", 100, 100) in seen and seen[-1][0] == "success"
