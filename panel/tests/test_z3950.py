import asyncio
import json

import pytest

from kei_panel import z3950 as z
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
    assert bnf.syntax == "UNIMARC" and bnf.login and bnf.user == "Z3950"
    assert all(t.kind in ("zed", "sru") for t in targets)


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
            "('z3950.bnf.fr', 2211, 'TOUT-ANA1-UTF8', 'Z3950', 'Z3950_BNF', 'BnF l\\'officielle', 'UNIMARC');")
    loc, bnf = z.parse_koha_sql(dump)
    assert (loc.name, loc.db) == ("LIBRARY OF CONGRESS", "LCDB")
    assert (bnf.name, bnf.user, bnf.password, bnf.syntax) == ("BnF l'officielle", "Z3950", "Z3950_BNF", "UNIMARC")


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
