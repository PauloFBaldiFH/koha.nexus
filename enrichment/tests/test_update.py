"""nexus_gateway.update: the newest release from a fake GitHub API and a
fake mirror, the SHA-256 check, the atomic swap, and the gateway picking
up the new file."""

import json
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import bib

from enrich_build.build import Builder, SourceConfig
from enrich_build.release import compress
from nexus_enrich import marc
from nexus_gateway import cql, update
from nexus_gateway.engine import Engine, Static
from nexus_gateway.targets import load


def build_db(d, title, n=1):
    d.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"fonte": "UFPR (ufpr)", "marcxml": marc.to_xml(bib(f"{title} {i}", "Autor, Um", rid=f"R{i}"))},
                        ensure_ascii=False) for i in range(n)]
    (d / "dump.jsonl").write_text("\n".join(lines), encoding="utf-8")
    src = SourceConfig.from_dict({"id": "zeus", "paths": ["dump.jsonl"], "source_field": "fonte"})
    Builder(d / "static.db", [src], d).build()
    return d / "static.db"


class Site:
    """A tiny web server: path -> bytes."""

    def __init__(self):
        self.files, self.hits = {}, []
        site = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                site.hits.append(self.path)
                body = site.files.get(self.path.split("?")[0])
                if body is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def publish(self, asset, sums, month, tag=None, extra=()):
        """A GitHub-like releases list at /releases with one release per call."""
        name = asset.name
        self.files[f"/dl/{month}/{name}"] = asset.read_bytes()
        self.files[f"/dl/{month}/{name}.sha256"] = sums.read_bytes()
        rel = {"tag_name": tag or f"enrich-{month}", "draft": False, "prerelease": False, "assets": [
            {"name": name, "size": asset.stat().st_size, "browser_download_url": f"{self.base}/dl/{month}/{name}"},
            {"name": name + ".sha256", "size": sums.stat().st_size,
             "browser_download_url": f"{self.base}/dl/{month}/{name}.sha256"}, *extra]}
        current = json.loads(self.files.get("/releases", b"[]"))
        self.files["/releases"] = json.dumps([rel] + current).encode()

    def close(self):
        self.srv.shutdown()


@pytest.fixture
def site():
    s = Site()
    yield s
    s.close()


@pytest.fixture
def assets(tmp_path):
    out = {}
    for month, title in (("2026.10", "Outubro"), ("2026.11", "Novembro")):
        db = build_db(tmp_path / month, title, 2)
        out[month] = compress(db, tmp_path / month / f"nexus-enrich-{month}.db.zst")
    return out


def titles(path):
    eng = Engine(Static(path), None, load(Path(__file__).resolve().parents[1] / "nexus_gateway" / "targets.json"))
    return sorted(r.first("245").get("a") for r in eng.search("_union", cql.parse("autor"), 1, 10).records)


def test_installs_then_is_current_then_takes_the_next_month(site, assets, tmp_path):
    api = site.base + "/releases"
    site.publish(*assets["2026.10"], "2026.10")
    target = tmp_path / "state" / "static.db"
    got = update.update(target, api=api)
    assert got["status"] == "updated" and got["release"] == "nexus-enrich-2026.10.db.zst" and got["versions"] == 2
    assert titles(target) == ["Outubro 0", "Outubro 1"]
    assert json.loads((tmp_path / "state" / "static.release").read_text())["name"] == "nexus-enrich-2026.10.db.zst"
    assert sorted(p.name for p in target.parent.iterdir()) == ["static.db", "static.release"]   # no leftovers

    hits = len(site.hits)
    assert update.update(target, api=api)["status"] == "current"
    assert len(site.hits) == hits + 1                                  # only the list was read

    # A running gateway keeps answering, then sees the new month.
    static = Static(target)
    eng = Engine(static, None, {})
    assert eng.search("_union", cql.parse("outubro"), 1, 5).total == 2
    site.publish(*assets["2026.11"], "2026.11")
    assert update.update(target, api=api, check=True)["status"] == "available"
    assert update.update(target, api=api)["status"] == "updated"
    assert eng.search("_union", cql.parse("novembro"), 1, 5).total == 2
    assert eng.search("_union", cql.parse("outubro"), 1, 5).total == 0


def test_bad_hash_leaves_static_db_alone(site, assets, tmp_path):
    asset, sums = assets["2026.10"]
    site.publish(asset, sums, "2026.10")
    target = tmp_path / "s" / "static.db"
    target.parent.mkdir()
    target.write_bytes(b"old")
    site.files["/dl/2026.10/" + sums.name] = b"0" * 64 + b"  " + asset.name.encode() + b"\n"
    with pytest.raises(update.UpdateError, match="does not match"):
        update.update(target, api=site.base + "/releases")
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in target.parent.iterdir()) == ["static.db"]


def test_corrupt_or_foreign_database_is_refused(tmp_path):
    import zstandard
    junk = tmp_path / "x.db.zst"
    junk.write_bytes(zstandard.ZstdCompressor().compress(b"not sqlite at all" * 100))
    target = tmp_path / "static.db"
    with pytest.raises(update.UpdateError, match="not a static.db|quick_check"):
        update.swap_in(junk, target)
    assert not target.exists() and not (tmp_path / "static.db.part").exists()
    junk.write_bytes(b"not zstd")
    with pytest.raises(update.UpdateError, match="cannot unpack"):
        update.swap_in(junk, target)


def test_mirror_is_used_when_github_fails_and_newest_wins(site, assets, tmp_path):
    asset, sums = assets["2026.11"]
    site.files["/r2/latest.txt"] = asset.name.encode() + b"\n"
    site.files["/r2/" + asset.name] = asset.read_bytes()
    site.files["/r2/" + sums.name] = sums.read_bytes()
    target = tmp_path / "m" / "static.db"
    got = update.update(target, api=site.base + "/nothing-here", mirror=site.base + "/r2")
    assert got["status"] == "updated" and got["origin"] == "mirror"
    rel, errors = update.find(site.base + "/nothing-here", site.base + "/r2")
    assert rel.origin == "mirror" and errors and errors[0].startswith("github:")
    site.publish(*assets["2026.10"], "2026.10")
    rel, _ = update.find(site.base + "/releases", site.base + "/r2")
    assert rel.origin == "mirror"                                     # 2026.11 beats 2026.10


def test_release_listing_rules(site, assets):
    asset, sums = assets["2026.10"]
    site.publish(asset, sums, "2026.10", extra=[{"name": "KohaNexus-Setup.exe", "size": 1,
                                                              "browser_download_url": "x"}])
    rels = json.loads(site.files["/releases"])
    rels.insert(0, {"tag_name": "enrich-2026.12", "draft": True, "assets": rels[0]["assets"]})
    rels.insert(0, {"tag_name": "v1.5.70", "assets": [{"name": "nexus-enrich-2027.01.db.zst", "size": 1,
                                                       "browser_download_url": "y"}]})   # no .sha256
    site.files["/releases"] = json.dumps(rels).encode()
    rel = update.latest_github(site.base + "/releases")
    assert rel.name == "nexus-enrich-2026.10.db.zst" and rel.size == asset.stat().st_size


def test_nothing_found_is_an_error(site, tmp_path):
    site.files["/releases"] = b"[]"
    with pytest.raises(update.UpdateError, match="no release found"):
        update.update(tmp_path / "static.db", api=site.base + "/releases")


def test_cli_update(site, assets, tmp_path, monkeypatch, capsys):
    from nexus_gateway.__main__ import main
    site.publish(*assets["2026.10"], "2026.10")
    monkeypatch.setenv("NEXUS_GATEWAY_STATIC_DB", str(tmp_path / "c" / "static.db"))
    monkeypatch.setenv("NEXUS_GATEWAY_RELEASES_API", site.base + "/releases")
    assert main(["update"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "updated"
    monkeypatch.setenv("NEXUS_GATEWAY_RELEASES_API", site.base + "/gone")
    assert main(["update", "--check"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_nothing_found_says_where_it_looked(site, tmp_path):
    site.files["/releases"] = json.dumps([{"tag_name": "", "draft": True, "assets": []}]).encode()
    with pytest.raises(update.UpdateError, match="drafts and pre-releases are not read"):
        update.update(tmp_path / "static.db", api=site.base + "/releases")
    from nexus_gateway.config import RELEASES_API, Settings
    assert Settings().releases_api == Settings.from_env().releases_api == RELEASES_API == update.API
    assert "/repos/PauloFBaldiFH/koha.nexus/releases" in RELEASES_API


def test_the_empty_static_db_then_the_first_download(site, assets, tmp_path, monkeypatch, capsys):
    from nexus_enrich.static import create_empty, record_count
    from nexus_gateway.__main__ import main
    target = tmp_path / "fresh" / "static.db"
    monkeypatch.setenv("NEXUS_GATEWAY_STATIC_DB", str(target))
    assert main(["init-db"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "created", "records": 0}
    assert (target.stat().st_mode & 0o777) == 0o644 and record_count(target) == 0
    assert main(["init-db"]) == 0 and json.loads(capsys.readouterr().out)["status"] == "present"
    assert not create_empty(target)
    # The gateway answers from it (nothing), authority search too.
    eng = Engine(Static(target), None, {})
    assert eng.search("_union", cql.parse("autor"), 1, 5).total == 0
    assert eng.search("_union-aut", cql.parse("autor"), 1, 5).total == 0
    # It is no release: the first update replaces it, readable by everyone.
    site.publish(*assets["2026.10"], "2026.10")
    assert update.update(target, api=site.base + "/releases")["status"] == "updated"
    assert record_count(target) == 2 and (target.stat().st_mode & 0o777) == 0o644
    assert (target.with_name("static.release").stat().st_mode & 0o777) == 0o644
    assert record_count(tmp_path / "missing.db") == -1
