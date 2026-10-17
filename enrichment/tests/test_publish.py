"""enrich_build.publish against a fake GitHub API: the release is created
once, assets of the same name are replaced, a mismatched .sha256 stops it."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from enrich_build.publish import GitHub, PublishError, publish
from enrich_build.release import sha256_file


class FakeGitHub:
    def __init__(self):
        self.releases, self.calls, self.next_id = {}, [], 1
        gh = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None):
                body = json.dumps(obj).encode() if obj is not None else b""
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_GET(self):
                gh.calls.append(("GET", self.path, self.headers["Authorization"]))
                tag = self.path.rsplit("/", 1)[-1]
                rel = gh.releases.get(tag)
                self._send(200, rel) if rel else self._send(404, {"message": "Not Found"})

            def do_POST(self):
                body = self._body()
                gh.calls.append(("POST", self.path.split("?")[0], len(body)))
                if self.path.endswith("/releases"):
                    data = json.loads(body)
                    rel = {"id": gh.next_id, "tag_name": data["tag_name"], "assets": [], "html_url": "h"}
                    gh.next_id += 1
                    gh.releases[data["tag_name"]] = rel
                    return self._send(201, rel)
                name = self.path.split("name=")[1]
                rel = next(r for r in gh.releases.values() if f"/releases/{r['id']}/" in self.path)
                rel["assets"].append({"id": gh.next_id, "name": name, "size": len(body)})
                gh.next_id += 1
                self._send(201, rel["assets"][-1])

            def do_DELETE(self):
                aid = int(self.path.rsplit("/", 1)[-1])
                gh.calls.append(("DELETE", aid))
                for r in gh.releases.values():
                    r["assets"] = [a for a in r["assets"] if a["id"] != aid]
                self._send(204)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"


@pytest.fixture
def gh():
    fake = FakeGitHub()
    yield fake
    fake.srv.shutdown()


def asset(tmp_path, data=b"zstd bytes"):
    a = tmp_path / "nexus-enrich-2026.10.db.zst"
    a.write_bytes(data)
    (tmp_path / (a.name + ".sha256")).write_text(f"{sha256_file(a)}  {a.name}\n")
    return a


def test_publish_creates_then_replaces(gh, tmp_path):
    client = GitHub("tok", "o/r", gh.base, gh.base)
    a = asset(tmp_path)
    out = publish(a, client)
    assert out["tag"] == "enrich-2026.10" and (tmp_path / "latest.txt").read_text() == a.name + "\n"
    rel = gh.releases["enrich-2026.10"]
    assert sorted(x["name"] for x in rel["assets"]) == [a.name, a.name + ".sha256"]
    assert gh.calls[0][2] == "Bearer tok"
    a = asset(tmp_path, b"newer bytes!")
    publish(a, client)
    assert len(gh.releases) == 1 and sum(1 for c in gh.calls if c[0] == "DELETE") == 2
    assert sorted((x["name"], x["size"]) for x in rel["assets"]) == [(a.name, 12), (a.name + ".sha256", 64 + 2 + len(a.name) + 1)]


def test_publish_refuses(tmp_path, gh):
    client = GitHub("tok", "o/r", gh.base, gh.base)
    a = asset(tmp_path)
    (tmp_path / (a.name + ".sha256")).write_text("0" * 64 + "  " + a.name)
    with pytest.raises(PublishError, match="does not match"):
        publish(a, client)
    other = tmp_path / "static.db"
    other.write_bytes(b"x")
    with pytest.raises(PublishError, match="not a nexus-enrich"):
        publish(other, client)
    with pytest.raises(PublishError, match="GITHUB_TOKEN"):
        GitHub("")
    assert gh.calls == []
