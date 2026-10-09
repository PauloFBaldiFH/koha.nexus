import asyncio
import json
import re

import pytest

from kei_panel import z3950 as z
from dataclasses import replace

from kei_panel.z3950 import CTX, UNIVERSAL, Target, ber_decode, tlv


@pytest.fixture(autouse=True)
def _own_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_Z3950_DIR", str(tmp_path))


def marc(title="Don Quixote", tag=b"245"):
    """A small, valid ISO 2709 record: 001 and a title field."""
    fields = [(b"001", b"12345\x1e"), (tag, b"10\x1fa" + title.encode() + b" /\x1fcCervantes.\x1e")]
    directory, data, pos = b"", b"", 0
    for t, body in fields:
        directory += t + b"%04d%05d" % (len(body), pos)
        data += body
        pos += len(body)
    base = 24 + len(directory) + 1
    length = base + len(data) + 1
    leader = b"%05dnam a22%05d   4500" % (length, base)
    return leader + directory + b"\x1e" + data + b"\x1d"


# ----------------------------------------------------------------------
# Curated list
# ----------------------------------------------------------------------
def test_curated_list_loads_and_covers_every_region():
    targets = z.load_curated()
    assert len(targets) >= 15
    assert {t.region for t in targets} == set(z.REGIONS)
    keys = [t.key for t in targets]
    assert len(keys) == len(set(keys))
    loc = next(t for t in targets if t.host == "lx2.loc.gov")
    assert (loc.port, loc.db, loc.syntax, loc.verified) == (210, "LCDB", "USMARC", True)
    bnf = next(t for t in targets if t.host == "z3950.bnf.fr")
    assert bnf.syntax == "UNIMARC" and bnf.login and bnf.login_env == "KEI_Z3950_BNF"
    assert all(t.kind in ("zed", "sru") for t in targets)


def test_curated_file_carries_no_login():
    data = json.loads(z.DATA_FILE.read_text(encoding="utf-8"))
    assert not [t["name"] for t in data["targets"] if t.get("user") or t.get("password")]


def test_login_comes_from_the_environment_or_the_env_file(tmp_path, monkeypatch):
    raw = {"host": "z.example.org", "db": "X", "login": True, "login_env": "KEI_Z3950_DEMO"}
    assert (z.make_target(raw).user, z.make_target(raw).password) == ("", "")
    (tmp_path / "kei.env").write_text("# logins\nexport KEI_Z3950_DEMO_USER=reader\n"
                                      "KEI_Z3950_DEMO_PASSWORD='from file'\n")
    t = z.make_target(raw)
    assert (t.user, t.password, t.login) == ("reader", "from file", True)
    monkeypatch.setenv("KEI_Z3950_DEMO_PASSWORD", "from env")
    assert z.make_target(raw).password == "from env"
    # A login typed in the list wins; one from .env is not copied into it.
    assert z.make_target(dict(raw, user="typed", password="pw")).password == "pw"
    z.save_local([replace(t, origin="curated")])
    assert z.load_local() == []
    # Only KEI_Z3950_* names: an imported list cannot read anything else.
    monkeypatch.setenv("HOME_PASSWORD", "nope")
    t = z.make_target(dict(raw, login_env="HOME"))
    assert (t.login_env, t.password) == ("", "")


def test_curated_file_is_plain_json_with_sources():
    data = json.loads(z.DATA_FILE.read_text(encoding="utf-8"))
    assert all(t.get("source") for t in data["targets"])
    assert all(t["region"] in z.REGIONS for t in data["targets"])


# ----------------------------------------------------------------------
# Readers and writers
# ----------------------------------------------------------------------
def test_make_target_aliases_and_urls():
    t = z.make_target({"Server Name": "Lib", "Hostname": "z.example.org:2100/books", "Format": "unimarc"})
    assert (t.name, t.host, t.port, t.db, t.syntax, t.kind) == ("Lib", "z.example.org", 2100, "books",
                                                                 "UNIMARC", "zed")
    s = z.make_target({"host": "https://sru.example.de/opac-1", "name": "SRU"})
    assert (s.kind, s.port, s.db, s.region) == ("sru", 443, "opac-1", "europe")
    assert z.make_target({"name": "no host"}) is None
    assert z.make_target({"host": "localhost"}) is None
    assert z.make_target({"host": "a.example.org", "port": "99999"}) is None


def test_csv_with_semicolons_and_header_aliases():
    text = "Nome;Servidor;Porta;Base;Formato\nBiblioteca X;z3950.x.br;210;acervo;MARC21\n;;;;\n"
    [t] = z.parse_csv(text)
    assert (t.name, t.host, t.port, t.db, t.syntax, t.region) == ("Biblioteca X", "z3950.x.br", 210, "acervo",
                                                                   "USMARC", "latam")


def test_csv_without_header():
    [t] = z.parse_csv("Some Library,z.example.edu,7090,Voyager\n")
    assert (t.name, t.host, t.port, t.db, t.region) == ("Some Library", "z.example.edu", 7090, "Voyager",
                                                         "north_america")


def test_yaml_registry():
    text = "targets:\n  - name: \"Test\"\n    host: z.example.jp\n    port: 210\n    database: OPAC\n" \
           "  - name: Other\n    host: sru.example.org\n    port: 80\n    type: sru\n    db: sru\n"
    a, b = z.parse_yaml(text)
    assert (a.name, a.host, a.db, a.region) == ("Test", "z.example.jp", "OPAC", "asia_pacific")
    assert b.kind == "sru"


def test_koha_sql_dump_with_and_without_columns():
    dump = ("INSERT INTO `z3950servers` VALUES (1,'lx2.loc.gov',210,'LCDB','','','LIBRARY OF CONGRESS',1,1,"
            "'USMARC',0,'zed','utf8','biblio',NULL,NULL,NULL,NULL),(2,'lx2.loc.gov',210,'NAF','','',"
            "'LOC AUTH',0,0,'USMARC',0,'zed','utf8','authority',NULL,NULL,NULL,NULL);\n"
            "INSERT INTO z3950servers (host, port, db, userid, password, servername, syntax) VALUES "
            "('z3950.bnf.fr', 2211, 'TOUT-ANA1-UTF8', 'reader', 'example', 'BnF l\\'officielle', 'UNIMARC');")
    loc, bnf = z.parse_koha_sql(dump)
    assert (loc.name, loc.db) == ("LIBRARY OF CONGRESS", "LCDB")
    assert (bnf.name, bnf.user, bnf.password, bnf.syntax) == ("BnF l'officielle", "reader", "example", "UNIMARC")


def test_scraper_reads_pages_tables_and_labels():
    page = """<html><body>
    <p>Connect to <b>catalog.example.edu:7090/Voyager</b> (MARC21).</p>
    <table><tr><td>National Library of Somewhere</td><td>z.nls.example.org</td><td>210</td><td>NLS</td>
    <td>UNIMARC</td></tr></table>
    <pre>Host: z3950.example.fr
Port: 2211
Database: CAT
Syntax: UNIMARC

Host: other.example.it
Port: 3950
Database: nopac</pre>
    <a href="https://sru.example.de/opac-de-1?version=1.1&operation=searchRetrieve&query=x">SRU</a>
    </body></html>"""
    found = {t.host: t for t in z.scrape(page)}
    assert found["catalog.example.edu"].db == "Voyager" and found["catalog.example.edu"].port == 7090
    nls = found["z.nls.example.org"]
    assert (nls.name, nls.port, nls.db, nls.syntax) == ("National Library of Somewhere", 210, "NLS", "UNIMARC")
    assert (found["z3950.example.fr"].port, found["z3950.example.fr"].db) == (2211, "CAT")
    assert found["other.example.it"].db == "nopac"
    sru = found["sru.example.de"]
    assert (sru.kind, sru.port, sru.db) == ("sru", 443, "opac-de-1")


def test_read_any_picks_the_reader():
    assert z.read_any('{"targets":[{"host":"a.example.org"}]}')[0].host == "a.example.org"
    assert z.read_any("host,port\nb.example.org,210\n", "list.csv")[0].host == "b.example.org"
    assert z.read_any("- host: c.example.org\n  port: 210\n", "x.yml")[0].host == "c.example.org"
    assert z.read_any("see d.example.org:210/x")[0].db == "x"


def test_export_round_trips_and_hides_passwords():
    t = Target("BnF", "z3950.bnf.fr", 2211, "TOUT", syntax="UNIMARC", region="europe", user="u", password="s3cret")
    for text in (z.to_json([t]), z.to_csv([t]), z.to_koha_sql([t])):
        assert "s3cret" not in text
    assert "s3cret" in z.to_json([t], passwords=True)
    back = z.parse_json(z.to_json([t], passwords=True))[0]
    assert (back.host, back.port, back.db, back.syntax, back.user, back.password) == \
           ("z3950.bnf.fr", 2211, "TOUT", "UNIMARC", "u", "s3cret")
    assert z.parse_csv(z.to_csv([t]))[0].key == t.key
    assert z.parse_koha_sql(z.to_koha_sql([t]))[0].key == t.key
    assert "WHERE NOT EXISTS" in z.to_koha_sql([t])


def test_password_never_in_repr_or_describe():
    t = Target("X", "x.example.org", user="me", password="hunter2")
    assert "hunter2" not in repr(t) and "hunter2" not in t.describe()
    assert "user=me" in t.describe()


def test_add_file_is_private_and_tab_safe():
    t = Target("A\tB\nC", "a.example.org", 210, "db", user="u", password="p")
    path = z.write_add_file([t], {t.key: 3})
    try:
        assert path.stat().st_mode & 0o777 == 0o600
        [line] = path.read_text().splitlines()
        cells = line.split("\t")
        assert len(cells) == len(z.ADD_FIELDS)
        row = dict(zip(z.ADD_FIELDS, cells))
        assert (row["name"], row["rank"], row["user"], row["password"], row["kind"]) == ("A B C", "3", "u", "p", "zed")
    finally:
        path.unlink()


def test_local_list_keeps_logins_privately(tmp_path):
    curated = z.load_curated()
    bl = Target("British Library", "z3950cat.bl.uk", 9909, "BLAC", user="me", password="pw", origin="curated")
    mine = Target("Mine", "mine.example.org", 210, "x", origin="imported")
    z.save_local([bl, mine] + curated[:2])
    assert (tmp_path / z.LOCAL_FILE).stat().st_mode & 0o777 == 0o600
    saved = {t.key: t for t in z.load_local()}
    assert set(saved) == {bl.key, mine.key}       # plain curated ones are not copied
    merged = {t.key: t for t in z.load_all()}
    assert merged[bl.key].password == "pw" and merged[mine.key].origin == "imported"


def test_merge_keeps_a_typed_login():
    a = Target("A", "a.example.org", user="me", password="pw")
    b = Target("A (new)", "a.example.org")
    [m] = z.merge([a], [b])
    assert (m.name, m.user, m.password) == ("A (new)", "me", "pw")


def test_community_sync(monkeypatch):
    class Resp:
        def __init__(self, body): self.body = body
        def read(self, n): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False
    body = json.dumps({"targets": [{"name": "New", "host": "new.example.org", "port": 210, "db": "x"}]}).encode()
    seen = {}

    def fake(req, timeout):
        seen["url"] = req.full_url
        return Resp(body)
    monkeypatch.setattr(z.urllib.request, "urlopen", fake)
    [t] = z.community_sync()
    assert t.origin == "community" and seen["url"] == z.COMMUNITY_URL
    monkeypatch.setattr(z.urllib.request, "urlopen", lambda req, timeout: Resp(b'{"targets": []}'))
    with pytest.raises(ValueError):
        z.community_sync()


# ----------------------------------------------------------------------
# BER and MARC
# ----------------------------------------------------------------------
def test_ber_lengths_tags_and_oids():
    assert z.ber_len(5) == b"\x05" and z.ber_len(200) == b"\x81\xc8" and z.ber_len(300) == b"\x82\x01\x2c"
    assert z.ber_tag(CTX, True, 20) == b"\xb4"
    assert z.ber_tag(CTX, False, 110) == b"\x9f\x6e"
    assert z.ber_tag(CTX, True, 102) == b"\xbf\x66"
    assert z.ber_oid(z.OID_BIB1) == bytes.fromhex("2a8648ce130301")
    assert z.ber_oid(z.OID_USMARC) == bytes.fromhex("2a8648ce13050a")
    assert z.ber_int(1_048_576) == b"\x10\x00\x00" and z.ber_int(128) == b"\x00\x80"


def test_requests_have_the_z3950_shape():
    init = ber_decode(z.init_request("me", "pw"))[0]
    assert init[:3] == (CTX, 20, True)
    assert z.ber_find(init[3], 1) == b"me" and z.ber_find(init[3], 2) == b"pw"
    assert z.ber_find(init[3], 111) == b"koha.nexus"
    assert z.ber_find(ber_decode(z.init_request())[0][3], 7) is None
    search = ber_decode(z.search_request("LCDB", "quixote"))[0]
    assert search[:3] == (CTX, 22, True)
    assert z.ber_find(search[3], 105) == b"LCDB" and z.ber_find(search[3], 45) == b"quixote"
    assert z.ber_find(search[3], 121) == b"\x04"
    assert z.ber_find(search[3], 6, UNIVERSAL) == z.ber_oid(z.OID_BIB1)
    present = ber_decode(z.present_request("UNIMARC"))[0]
    assert z.ber_find(present[3], 104) == z.ber_oid(z.OID_UNIMARC)


def test_marc_frame_validator():
    rec = marc()
    assert z.marc_frame_ok(rec)
    assert z.marc_title(rec) == "Don Quixote"
    assert z.marc_title(marc("Le Petit Prince", b"200"), unimarc=True) == "Le Petit Prince"
    assert not z.marc_frame_ok(rec[:-1])                       # no record terminator
    assert not z.marc_frame_ok(b"x" + rec[1:])                 # length not digits
    assert not z.marc_frame_ok(rec[:-1] + b"\x1d\x1d")         # length disagrees
    assert not z.marc_frame_ok(b"<html>error</html>" * 3)
    broken = bytearray(rec)
    broken[24] = ord("X")                                      # directory not digits
    assert not z.marc_frame_ok(bytes(broken))


def test_marcxml_check():
    assert z.marcxml_ok('<record><leader>00000nam a2200000 a 4500</leader><controlfield tag="001">1'
                        '</controlfield></record>')
    assert not z.marcxml_ok("<dc:title>x</dc:title>")


# ----------------------------------------------------------------------
# The scan, against a small Z39.50 server of the test
# ----------------------------------------------------------------------
class FakeZ3950:
    """Answers Init, Search and Present like a real target would."""

    def __init__(self, accept=True, hits=1, record=None, want_user=""):
        self.accept, self.hits, self.want_user = accept, hits, want_user
        self.record = marc() if record is None else record
        self.terms, self.users = [], []

    async def handle(self, reader, writer):
        try:
            while True:
                pdu = ber_decode(await z.read_pdu(reader))[0]
                if pdu[1] == 20:
                    user = z.ber_find(pdu[3], 1)
                    self.users.append(user)
                    ok = self.accept and (not self.want_user or user == self.want_user.encode())
                    writer.write(tlv(21, tlv(3, b"\x00\xe0") + tlv(12, b"\xff" if ok else b"\x00"), True))
                elif pdu[1] == 22:
                    term = z.ber_find(pdu[3], 45).decode()
                    self.terms.append(term)
                    n = self.hits if term == "prince" or self.hits and term == "quixote" else 0
                    writer.write(tlv(23, tlv(23, z.ber_int(n)) + tlv(24, z.ber_int(0)) + tlv(22, b"\xff"), True))
                elif pdu[1] == 24:
                    external = tlv(8, tlv(6, z.ber_oid(z.OID_USMARC), cls=UNIVERSAL) + tlv(1, self.record), True,
                                   UNIVERSAL)
                    npr = tlv(16, tlv(0, b"db") + tlv(1, tlv(1, external[2:], True), True), True, UNIVERSAL)
                    writer.write(tlv(25, tlv(24, z.ber_int(1)) + tlv(27, z.ber_int(0)) + tlv(28, npr, True), True))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


async def _serve(fake):
    server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


def test_probe_finds_a_valid_record():
    async def go():
        fake = FakeZ3950()
        server, port = await _serve(fake)
        async with server:
            t = Target("Fake", "127.0.0.1", port, "db")
            return fake, await z.scan_one(t)
    fake, res = asyncio.run(go())
    assert res.status == "ok" and res.title == "Don Quixote" and res.hits == 1
    assert res.connect_ms is not None and res.query_ms is not None
    assert fake.terms == ["quixote"]


def test_probe_tries_the_next_word_then_reports_empty():
    async def go(hits):
        fake = FakeZ3950(hits=hits)
        server, port = await _serve(fake)
        async with server:
            return fake, await z.scan_one(Target("Fake", "127.0.0.1", port, "db"))
    fake, res = asyncio.run(go(0))
    assert res.status == "empty" and fake.terms == list(z.PROBE_TERMS)


def test_probe_rejects_corrupt_records_and_refused_logins():
    async def go(**kw):
        fake = FakeZ3950(**kw)
        server, port = await _serve(fake)
        async with server:
            return fake, await z.scan_one(Target("Fake", "127.0.0.1", port, "db", user=kw.get("want_user", "")))
    _f, res = asyncio.run(go(record=b"<html>500 Internal Server Error</html>"))
    assert res.status == "no_marc"
    _f, res = asyncio.run(go(accept=False))
    assert res.status == "login"
    fake, res = asyncio.run(go(want_user="librarian"))
    assert res.status == "ok" and fake.users == [b"librarian"]


def test_probe_of_a_port_that_speaks_something_else():
    async def chatter(reader, writer):
        writer.write(b"HTTP/1.0 400 Bad Request\r\n\r\n")
        await writer.drain()
        writer.close()

    async def go():
        server = await asyncio.start_server(chatter, "127.0.0.1", 0)
        async with server:
            return await z.scan_one(Target("Web", "127.0.0.1", server.sockets[0].getsockname()[1], "db"))
    assert asyncio.run(go()).status == "tcp"


def test_dead_host_and_alternate_ports(monkeypatch):
    monkeypatch.setattr(z, "CONNECT_TIMEOUT", 0.5)
    tried = []
    real = z._connect

    async def fake_connect(host, port, timeout):
        tried.append(port)
        if port == 2100 and host == "moved.example.org":
            return await real("127.0.0.1", live, timeout)
        raise ConnectionRefusedError

    async def go():
        nonlocal live
        fake = FakeZ3950()
        server, live = await _serve(fake)
        async with server:
            dead = await z.scan_one(Target("Dead", "127.0.0.1", 9, "db"))
            tried.clear()
            moved = await z.scan_one(Target("Moved", "moved.example.org", 210, "db"))
        return dead, moved
    live = 0
    monkeypatch.setattr(z, "_connect", fake_connect)
    dead, moved = asyncio.run(go())
    assert dead.status == "dead"
    assert moved.status == "ok" and moved.port == 2100 and "port 2100" in moved.detail
    assert set(tried) >= {210, 2100, 2210}


def test_scan_runs_everything_and_reports_each():
    async def go():
        fake = FakeZ3950()
        server, port = await _serve(fake)
        async with server:
            targets = [Target(f"T{i}", "127.0.0.1", port, f"db{i}") for i in range(5)]
            seen = []
            results = await z.scan(targets, on_result=lambda t, r: seen.append(t.name), concurrency=2)
            return results, seen
    results, seen = asyncio.run(go())
    assert [r.status for r in results] == ["ok"] * 5 and sorted(seen) == [f"T{i}" for i in range(5)]


def test_sru_probe():
    xml = ('<searchRetrieveResponse><numberOfRecords>12</numberOfRecords><records><record><recordData>'
           '<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000cam a2200000 i 4500</leader>'
           '<controlfield tag="001">1</controlfield><datafield tag="245" ind1="1" ind2="0">'
           '<subfield code="a">El ingenioso hidalgo don Quijote /</subfield></datafield></record>'
           '</recordData></record></records></searchRetrieveResponse>')
    urls = []

    def get(url, timeout):
        urls.append(url)
        return xml
    t = Target("DNB", "services.dnb.de", 443, "sru/dnb", kind="sru", schema="MARC21-xml")
    res = asyncio.run(z.probe_sru(t, 443, get=get))
    assert res.status == "ok" and res.title == "El ingenioso hidalgo don Quijote" and res.hits == 12
    assert urls[0].startswith("https://services.dnb.de/sru/dnb?") and "recordSchema=MARC21-xml" in urls[0]
    assert "maximumRecords=1" in urls[0]
    res = asyncio.run(z.probe_sru(t, 443, get=lambda u, timeout: "<numberOfRecords>0</numberOfRecords>"))
    assert res.status == "empty"
    res = asyncio.run(z.probe_sru(t, 443, get=lambda u, timeout: "<numberOfRecords>3</numberOfRecords><dc/>"))
    assert res.status == "no_marc"
    res = asyncio.run(z.probe_sru(t, 443, get=lambda u, timeout: "<html>hello</html>"))
    assert res.status == "tcp"
    assert z.sru_url(Target("x", "h.example.org", 8080, "/a/b", kind="sru"), "q").startswith(
        "http://h.example.org:8080/a/b?")


# ----------------------------------------------------------------------
# Ranking and blacklist
# ----------------------------------------------------------------------
def test_ranking():
    rs = [z.ScanResult("a", "dead"), z.ScanResult("b", "ok", query_ms=900), z.ScanResult("c", "ok", query_ms=80),
          z.ScanResult("d", "empty", query_ms=10), z.ScanResult("e", "login")]
    assert [r.key for r in z.rank(rs)] == ["c", "b", "d", "e", "a"]


def test_history_blacklists_after_three_failures(tmp_path):
    h = z.History()
    for _ in range(2):
        h.record(z.ScanResult("k", "dead"))
    assert not h.blacklisted("k")
    h.record(z.ScanResult("k", "tcp"))
    assert h.blacklisted("k")
    h.save()
    again = z.History()
    assert again.blacklisted("k") and again.get("k")["fails"] == 3
    again.record(z.ScanResult("k", "ok", query_ms=50))
    assert not again.blacklisted("k")
    again.set_manual("k", True)
    assert again.blacklisted("k")
    again.set_manual("k", False)
    assert not again.blacklisted("k")
    assert (tmp_path / z.HISTORY_FILE).stat().st_mode & 0o777 == 0o600


def test_koha_ranks_follow_latency():
    a, b, c = (Target(n, f"{n}.example.org") for n in "abc")
    h = z.History()
    h.record(z.ScanResult(a.key, "ok", query_ms=700))
    h.record(z.ScanResult(b.key, "ok", query_ms=90))
    assert z.koha_ranks([a, b, c], h) == {b.key: 1, a.key: 2, c.key: 3}


def test_curated_brazil_list_and_zeus_bridge():
    latam = [t for t in z.load_curated() if t.region == "latam"]
    assert [t.host for t in latam] == ["127.0.0.1", "z3950.ufsc.br", "z3950.utfpr.edu.br", "z3950.unifesp.br"]
    zeus = latam[0]
    assert (zeus.kind, zeus.port, zeus.db, zeus.preselect) == ("sru", 5000, "sru", True)
    assert all((t.kind, t.port, t.db, t.preselect) == ("zed", 210, "Default", False) for t in latam[1:])
    hosts = {t.host for t in z.load_curated()}
    assert not hosts & {"162.214.168.248", "unesp.alma.exlibrisgroup.com"}


def test_add_file_and_sql_carry_the_sru_settings():
    zeus = next(t for t in z.load_curated() if t.preselect)
    ufsc = next(t for t in z.load_curated() if t.host == "z3950.ufsc.br")
    dnb = next(t for t in z.load_curated() if t.host == "services.dnb.de")
    rows = [dict(zip(z.ADD_FIELDS, line.split("\t"))) for line in
            z.add_file_text([zeus, ufsc, dnb], {}).splitlines()]
    assert (rows[0]["kind"], rows[0]["sru_fields"], rows[0]["sru_options"]) == (
        "sru", "title=dc.title,isbn=dc.isbn,srchany=cql.serverChoice", "sru_version=1.1,schema=marcxml")
    assert (rows[1]["kind"], rows[1]["sru_fields"], rows[1]["sru_options"]) == ("zed", "", "")
    assert rows[2]["sru_fields"] == z.DEFAULT_SRU_FIELDS
    sql = z.to_koha_sql([zeus])
    assert "'sru_version=1.1,schema=marcxml'" in sql and "sru_options" in sql
    # A Z39.50 target never carries SRU settings, whatever its source says.
    t = z.make_target({"host": "z.example.org", "sru_fields": "title=x"})
    assert t.kind == "zed" and t.sru_fields == ""


# ----------------------------------------------------------------------
# What counts as working (no false failures)
# ----------------------------------------------------------------------
class PickyZ3950(FakeZ3950):
    """Real-world replies the older scan took for failures."""

    def __init__(self, mode, **kw):
        super().__init__(**kw)
        self.mode = mode

    async def handle(self, reader, writer):
        try:
            while True:
                pdu = ber_decode(await z.read_pdu(reader))[0]
                if pdu[1] == 20:
                    if self.mode == "indefinite":
                        # InitResponse with an indefinite length, its result last.
                        writer.write(b"\xb5\x80" + tlv(3, b"\x00\xe0") + tlv(12, b"\x01") + b"\x00\x00")
                    elif self.mode == "no_result":
                        writer.write(tlv(21, tlv(3, b"\x00\xe0") + tlv(110, b"x"), True))
                    elif self.mode == "nested_false":
                        user_info = tlv(11, tlv(12, b"\x00"), True)
                        writer.write(tlv(21, tlv(3, b"\x00\xe0") + user_info + tlv(12, b"\xff"), True))
                    else:
                        writer.write(tlv(21, tlv(3, b"\x00\xe0") + tlv(12, b"\xff"), True))
                elif pdu[1] == 22:
                    if self.mode == "slow_search":
                        await asyncio.sleep(5)
                    writer.write(tlv(23, tlv(23, z.ber_int(42)) + tlv(24, z.ber_int(0)) + tlv(22, b"\xff"), True))
                elif pdu[1] == 24:
                    # Present out of range: a nonSurrogateDiagnostic, no record.
                    diag = tlv(130, tlv(16, tlv(6, z.ber_oid(z.OID_BIB1), cls=UNIVERSAL)
                                        + tlv(2, z.ber_int(13), cls=UNIVERSAL), True, UNIVERSAL), True)
                    writer.write(tlv(25, tlv(24, z.ber_int(0)) + tlv(27, z.ber_int(1)) + diag, True))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


def _scan_picky(mode, **kw):
    async def go():
        fake = PickyZ3950(mode, **kw)
        server, port = await _serve(fake)
        async with server:
            return await z.scan_one(Target("Picky", "127.0.0.1", port, "Default"))
    return asyncio.run(go())


def test_indefinite_length_init_is_read():
    res = _scan_picky("indefinite")
    assert res.alive and res.answered and res.hits == 42


def test_init_without_or_with_a_nested_result_is_accepted():
    assert _scan_picky("no_result").status == "empty"
    assert _scan_picky("nested_false").status == "empty"


def test_present_out_of_range_is_working_not_bad_marc():
    res = _scan_picky("plain")
    assert res.status == "empty" and res.alive and "Present" in res.detail


def test_slow_search_after_init_is_working(monkeypatch):
    monkeypatch.setattr(z, "QUERY_TIMEOUT", 0.3)

    async def go():
        fake = PickyZ3950("slow_search")
        server, port = await _serve(fake)
        async with server:
            t = Target("Slow", "127.0.0.1", port, "LCDB")
            return await z.probe_z3950(t, port, timeout=0.3), await z.scan([t])
    res, [scanned] = asyncio.run(go())
    assert res.status == "empty" and res.alive and "TimeoutError" in res.detail
    assert scanned.alive


def test_whole_scan_timeout_keeps_what_the_probe_learnt(monkeypatch):
    monkeypatch.setattr(z, "QUERY_TIMEOUT", 0.1)
    monkeypatch.setattr(z, "CONNECT_TIMEOUT", 0.1)

    async def slow_probe(target, port, res=None, **kw):
        res.status, res.answered = "tcp", True
        await asyncio.sleep(5)
    monkeypatch.setattr(z, "probe_z3950", slow_probe)

    async def fake_port(host, port, timeout=0):
        return port, 3
    monkeypatch.setattr(z, "find_port", fake_port)
    [r] = asyncio.run(z.scan([Target("T", "t.example.org", 210, "db")]))
    assert r.status == "empty" and "took too long" in r.detail


def test_sru_diagnostic_or_zero_hits_is_working():
    t = Target("Zeus", "127.0.0.1", 5000, "sru", kind="sru")
    diag = ('<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/"><zs:diagnostics>'
            '<diag:diagnostic xmlns:diag="x"><diag:uri>info:srw/diagnostic/1/1</diag:uri>'
            '<diag:message>Catálogo Zeus did not answer</diag:message></diag:diagnostic></zs:diagnostics>'
            '</zs:searchRetrieveResponse>')
    res = asyncio.run(z.probe_sru(t, 5000, get=lambda u, timeout: diag))
    assert res.status == "empty" and res.alive and "Zeus did not answer" in res.detail


def test_history_from_the_older_scan_is_shown_again(tmp_path):
    old = {"a.example.org:210/x": {"status": "tcp", "fails": 4, "auto": True},
           "b.example.org:210/y": {"status": "dead", "fails": 1, "manual": True}}
    (tmp_path / z.HISTORY_FILE).write_text(json.dumps(old))
    h = z.History()
    assert not h.blacklisted("a.example.org:210/x") and h.get("a.example.org:210/x")["fails"] == 0
    assert h.blacklisted("b.example.org:210/y")          # hidden by hand: stays hidden
    h.record(z.ScanResult("a.example.org:210/x", "dead"))
    h.save()
    again = z.History()
    assert again.get("a.example.org:210/x")["fails"] == 1  # no second reset


def test_curated_list_without_the_confirmed_dead_servers():
    targets = z.load_curated()
    hosts = {t.host for t in targets}
    assert not hosts & {"z3950.bnportugal.gov.pt", "eu00.alma.exlibrisgroup.com"}
    assert not any(t.host == "z3950.loc.gov" for t in targets)
    assert not any(re.fullmatch(r"[\d.]+", t.host) and t.host != "127.0.0.1" for t in targets)
    keys = {t.key for t in targets}
    assert {"lx2.loc.gov:210/LCDB", "services.dnb.de:443/sru/dnb", "z3950.libris.kb.se:210/libr"} <= keys
    libris = next(t for t in targets if t.host == "z3950.libris.kb.se")
    assert libris.encoding == "MARC-8"
