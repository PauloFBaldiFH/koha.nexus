import asyncio
import json
import threading
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import pymarc
import pytest
from fastapi.testclient import TestClient

from sru_gateway import targets as tg
from sru_gateway import z3950
from sru_gateway.app import create_app
from sru_gateway.config import Settings
from sru_gateway.upstream_sru import cql_for, parse_response
from zeus_sru.cql import parse

NS = {"zs": "http://www.loc.gov/zing/srw/", "marc": "http://www.loc.gov/MARC21/slim",
      "diag": "http://www.loc.gov/zing/srw/diagnostic/"}
TARGETS_JSON = Path(__file__).resolve().parents[1] / "sru_gateway" / "targets.json"
# Paulo's list of 2026-10-15, in his order and under his four headings.
GROUPS = {
    "national": "bn fundacentro senado senado-folio bn-portugal porbase bne bl loc argentina colombia polonia "
                "suica suecia tchequia grecia russia-state bashkir-russia africa-do-sul taiwan nysl",
    "br_universities": "usp unicamp unesp uerj ufg ufmg ufpe ufsc ufscar unifesp ufu ufpr ufrgs uff utfpr",
    "intl_universities": "harvard yale mit wisconsin pennstate upenn tufts fsu suno ubc toronto sfu trent memorial "
                         "oxford coimbra porto barcelona gent-belgica tuhh-alemanha macau buap-mexico pucp-peru upc-peru",
    "specialized": "all nlm art-chicago nga castilla-leon bizkaia italia abes-franca kobv-alemanha swb-alemanha "
                   "christchurch hong-kong",
}
IDS = [i for ids in GROUPS.values() for i in ids.split()]


def marc_record(title: str, isbn: str = "9788535902778") -> bytes:
    r = pymarc.Record(force_utf8=True)
    r.add_field(pymarc.Field(tag="020", indicators=[" ", " "], subfields=[pymarc.Subfield("a", isbn)]))
    r.add_field(pymarc.Field(tag="245", indicators=["1", "0"], subfields=[pymarc.Subfield("a", title)]))
    data = r.as_marc()
    return data[:9] + b" " + data[10:]   # leader/09 blank, as many utf8 servers send


def search(client, path="/sru/bn", **params):
    params.setdefault("version", "1.1")
    params.setdefault("operation", "searchRetrieve")
    r = client.get(path, params=params)
    assert r.status_code == 200
    return ET.fromstring(r.content)


def titles(root):
    return [d.text for d in root.findall(".//marc:datafield[@tag='245']/marc:subfield[@code='a']", NS)]


def diag(root):
    return (root.findtext(".//diag:uri", namespaces=NS), root.findtext(".//diag:message", namespaces=NS))


# --- targets.json -------------------------------------------------------

def test_targets_json_has_the_72_ids_in_order():
    data = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))
    assert [t["id"] for t in data["targets"]] == IDS
    table = tg.load(TARGETS_JSON)
    assert len(table) == 72
    assert {g: " ".join(t.id for t in table.values() if t.group == g) for g in tg.GROUPS} == GROUPS
    kinds = {t.id: t.kind for t in table.values()}
    assert kinds["ufsc"] == "zeus" and kinds["all"] == "pergamum"
    assert {k for k, v in kinds.items() if v == "z3950"} == {"nlm", "bl", "loc", "italia", "swb-alemanha",
                                                                  "utfpr", "unifesp", "suecia"}
    assert not any({"user", "password"} & set(t) for t in data["targets"])
    # Every entry says what is known about it (the old STATUS_ALVOS.md).
    assert all("status" in t for t in data["targets"])
    status = {t.id: t.status for t in table.values()}
    assert status["bl"] == status["nlm"] == "broken" and status["italia"] == "untested"
    assert {i for i, s in status.items() if s == "missing"} == {i for i, k in kinds.items() if k == "missing"}


def test_zeus_target_indexes_are_distinct():
    table = tg.load(TARGETS_JSON)
    indexes = [t.target_index for t in table.values() if t.kind == "zeus"]
    assert len(indexes) == len(set(indexes)) == 13


def test_status_is_checked():
    assert tg.make_target({"id": "x", "kind": "missing"}).status == "missing"
    assert tg.make_target({"id": "x", "kind": "sru", "url": "https://h/sru"}).status == "untested"
    with pytest.raises(tg.TargetError):
        tg.make_target({"id": "x", "kind": "sru", "url": "https://h/sru", "status": "fine"})
    with pytest.raises(tg.TargetError):
        tg.make_target({"id": "x", "kind": "sru", "url": "https://h/sru", "status": "missing"})


def test_make_target_rejects_what_it_cannot_serve():
    with pytest.raises(tg.TargetError):
        tg.make_target({"id": "x", "kind": "z3950", "host": "h", "port": 210, "db": "d", "syntax": "UNIMARC"})
    with pytest.raises(tg.TargetError):
        tg.make_target({"id": "x", "kind": "z3950", "host": "h"})
    with pytest.raises(tg.TargetError):
        tg.make_target({"id": "Bad Id", "kind": "missing"})
    with pytest.raises(tg.TargetError):
        tg.make_target({"id": "x", "kind": "sru", "url": "ftp://h"})


def test_login_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("SRU_GATEWAY_LOGIN_BL", "me:secret")
    t = tg.make_target({"id": "bl", "kind": "z3950", "host": "h", "port": 1, "db": "d"})
    assert (t.user, t.password) == ("me", "secret")


# --- routing ------------------------------------------------------------

def gateway(table, **clients):
    return TestClient(create_app(Settings(timeout=5), table, **clients))


def test_unknown_id_is_database_not_found():
    with gateway({}) as client:
        uri, msg = diag(search(client, "/sru/nowhere", query="dc.title=x"))
    assert uri == "info:srw/diagnostic/1/235" and "nowhere" in msg


def test_missing_address_says_so_and_both_slash_forms_route():
    table = {"bn": tg.make_target({"id": "bn", "name": "Biblioteca Nacional", "kind": "missing"})}
    with gateway(table) as client:
        # Koha joins host:port/db, so a database written /sru/bn asks for //sru/bn.
        for path in ("/sru/bn", "http://testserver//sru/bn"):
            uri, msg = diag(search(client, path, query="dc.title=x"))
            assert uri == "info:srw/diagnostic/1/1"
            assert "Biblioteca Nacional" in msg and "no catalogue address" in msg


def test_explain_and_health():
    table = tg.load(TARGETS_JSON)
    with gateway(table, zeus_http=httpx.AsyncClient()) as client:
        r = client.get("/sru/bn")
        assert b"explainResponse" in r.content
        h = client.get("/health").json()
    assert h["targets"] == 72 and "ufsc" in h["configured"] and "bne" in h["missing"]


def test_ufsc_goes_to_zeus(marcxml_page):
    seen = []

    def answer(request):
        seen.append(request)
        return httpx.Response(200, text=marcxml_page)
    http = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    table = {"ufsc": tg.make_target({"id": "ufsc", "name": "UFSC", "kind": "zeus", "target_index": 11}),
             "usp": tg.make_target({"id": "usp", "name": "USP", "kind": "zeus", "target_index": 4})}
    with gateway(table, zeus_http=http) as client:
        root = search(client, "/sru/ufsc", query="dc.isbn=9684291426", maximumRecords="5")
        assert seen and int(root.findtext("zs:numberOfRecords", namespaces=NS)) >= 1
        assert titles(root)
        search(client, "/sru/usp", query="dc.isbn=9684291426", maximumRecords="5")
    # Each id asks Zeus for its own target only.
    asked = [[k for k in r.url.params if k.startswith("targets[")] for r in seen]
    assert asked == [["targets[11]"], ["targets[4]"]]


# --- upstream SRU -------------------------------------------------------

SRU_ANSWER = """<?xml version="1.0"?>
<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">
 <srw:version>1.1</srw:version><srw:numberOfRecords>7</srw:numberOfRecords>
 <srw:records>
  <srw:record><srw:recordSchema>marcxml</srw:recordSchema><srw:recordPacking>xml</srw:recordPacking>
   <srw:recordData><mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
    <mx:leader>00000nam a2200000 a 4500</mx:leader>
    <mx:datafield tag="245" ind1="1" ind2="0"><mx:subfield code="a">Dom Casmurro</mx:subfield></mx:datafield>
   </mx:record></srw:recordData></srw:record>
  <srw:record><srw:recordSchema>marcxml</srw:recordSchema><srw:recordPacking>string</srw:recordPacking>
   <srw:recordData>&lt;record&gt;&lt;leader&gt;00000nam a2200000 a 4500&lt;/leader&gt;&lt;datafield tag="245" ind1="0" ind2="0"&gt;&lt;subfield code="a"&gt;Memórias póstumas&lt;/subfield&gt;&lt;/datafield&gt;&lt;/record&gt;</srw:recordData></srw:record>
 </srw:records>
</srw:searchRetrieveResponse>"""


def test_parse_response_reads_prefixed_and_string_packed_records():
    total, records, d = parse_response(SRU_ANSWER.encode())
    assert total == 7 and not d
    assert [r["245"]["a"] for r in records] == ["Dom Casmurro", "Memórias póstumas"]


def test_cql_uses_the_targets_index_names():
    t = tg.make_target({"id": "x", "kind": "sru", "url": "https://h/sru", "indexes": {"isbn": "dc.identifier"}})
    assert cql_for(t, parse("dc.isbn=85-359-0277-5")) == 'dc.identifier="8535902775"'
    assert cql_for(t, parse('dc.title="dom casmurro"')) == 'dc.title="dom casmurro"'


def test_sru_target_through_the_gateway():
    asked = []

    def answer(request):
        asked.append(request)
        return httpx.Response(200, content=SRU_ANSWER.encode())
    http = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    table = {"nlm": tg.make_target({"id": "nlm", "name": "NLM", "kind": "sru", "url": "https://example.org/sru"})}
    with gateway(table, http=http) as client:
        root = search(client, "/sru/nlm", query="dc.title=casmurro", maximumRecords="2")
    assert asked[0].url.params["query"] == 'dc.title="casmurro"'
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "7"
    assert titles(root) == ["Dom Casmurro", "Memórias póstumas"]


def test_sru_target_diagnostic_is_passed_on():
    body = ('<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><numberOfRecords>0</numberOfRecords>'
            '<diagnostics><diagnostic xmlns="http://www.loc.gov/zing/srw/diagnostic/">'
            '<uri>info:srw/diagnostic/1/16</uri><message>Unsupported index</message></diagnostic></diagnostics>'
            '</searchRetrieveResponse>')
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=body)))
    table = {"nlm": tg.make_target({"id": "nlm", "name": "NLM", "kind": "sru", "url": "https://example.org/sru"})}
    with gateway(table, http=http) as client:
        uri, msg = diag(search(client, "/sru/nlm", query="dc.title=x"))
    assert uri == "info:srw/diagnostic/1/1" and "Unsupported index" in msg


# --- Z39.50 -------------------------------------------------------------

class FakeZ3950:
    """Answers Init, Search and Present like a Z39.50 server holding RECORDS."""

    RECORDS = [marc_record("Grande sertão: veredas"), marc_record("Vidas secas"), marc_record("Macunaíma")]

    def __init__(self):
        self.searches = []
        self.presents = []
        self.port = 0
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self.ready.wait(5)

    def _run(self):
        asyncio.set_event_loop(self.loop)
        server = self.loop.run_until_complete(asyncio.start_server(self._client, "127.0.0.1", 0))
        self.port = server.sockets[0].getsockname()[1]
        self.ready.set()
        self.loop.run_forever()

    async def _client(self, reader, writer):
        T = z3950.tlv
        try:
            while True:
                pdu = z3950.ber_decode(await z3950.read_pdu(reader))[0]
                body = pdu[3]
                if pdu[1] == 20:
                    out = T(21, T(12, b"\xff"), True)
                elif pdu[1] == 22:
                    rpn = z3950.ber_top(body, 21)
                    self.searches.append(rpn)
                    n = len(self.RECORDS)
                    out = T(23, T(23, z3950.ber_int(n)) + T(24, z3950.ber_int(0))
                            + T(25, z3950.ber_int(1)) + T(22, b"\xff"), True)
                else:
                    start = z3950._int(z3950.ber_top(body, 30))
                    count = z3950._int(z3950.ber_top(body, 29))
                    self.presents.append((start, count))
                    nprs = b""
                    for rec in self.RECORDS[start - 1:start - 1 + count]:
                        ext = T(8, T(6, z3950.ber_oid(z3950.OID_USMARC), cls=z3950.UNIVERSAL) + T(1, rec),
                                True, z3950.UNIVERSAL)
                        nprs += T(16, T(0, b"db") + T(1, T(1, ext, True), True), True, z3950.UNIVERSAL)
                    out = T(25, T(24, z3950.ber_int(count)) + T(25, z3950.ber_int(start + count))
                            + T(27, z3950.ber_int(0)) + T(28, nprs, True), True)
                writer.write(out)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            writer.close()


@pytest.fixture(scope="module")
def fake_z3950():
    return FakeZ3950()


def z_table(port):
    return {"bl": tg.make_target({"id": "bl", "name": "British Library", "kind": "z3950",
                                  "host": "127.0.0.1", "port": port, "db": "BLAC"})}


def test_z3950_count_then_page(fake_z3950):
    with gateway(z_table(fake_z3950.port)) as client:
        count = search(client, "/sru/bl", query="dc.title=sertao", maximumRecords="0")
        page = search(client, "/sru/bl", query="dc.title=sertao", startRecord="2", maximumRecords="5")
    assert count.findtext("zs:numberOfRecords", namespaces=NS) == "3" and not titles(count)
    assert titles(page) == ["Vidas secas", "Macunaíma"]
    assert fake_z3950.presents[-1] == (2, 2)


def test_z3950_isbn_uses_bib1_use_7(fake_z3950):
    with gateway(z_table(fake_z3950.port)) as client:
        search(client, "/sru/bl", query="dc.isbn=85-359-0277-5", maximumRecords="1")
    last = fake_z3950.searches[-1]
    octets = z3950._primitives(last)
    assert b"8535902775" in octets and z3950.ber_int(7) in octets


def test_z3950_down_is_diagnostic_1():
    with gateway(z_table(1)) as client:
        uri, msg = diag(search(client, "/sru/bl", query="dc.title=x"))
    assert uri == "info:srw/diagnostic/1/1" and "127.0.0.1:1" in msg


def test_readme_table_matches_targets_json():
    from sru_gateway import status_table
    text = status_table.README.read_text(encoding="utf-8")
    assert status_table.readme_block(text) == status_table.block(tg.load(TARGETS_JSON)), \
        "README.md is behind targets.json: run python -m sru_gateway.status_table --write"


def test_koha_sql_and_panel_list_match_targets_json():
    from sru_gateway import koha_sql
    table = tg.load(TARGETS_JSON)
    assert koha_sql.OUT.read_text(encoding="utf-8") == koha_sql.render(table), \
        "deploy/koha-z3950servers.sql is behind targets.json: run python -m sru_gateway.koha_sql --write"
    panel = json.loads(koha_sql.PANEL_LIST.read_text(encoding="utf-8"))
    updated = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))["updated"]
    assert koha_sql.PANEL_LIST.read_text(encoding="utf-8") == koha_sql.panel_list(table, updated)
    assert [r["db"] for r in panel["targets"]] == [f"sru/{i}" for i in IDS]
    assert {(r["host"], r["port"], r["syntax"]) for r in panel["targets"]} == {("sru.koha.nexus", 443, "MARC21")}
    # Renames only point at ids that exist, and never from one that still does.
    assert set(koha_sql.RENAMED.values()) <= set(table) and not set(koha_sql.RENAMED) & set(table)


# --- every slug routes, and nothing answers JSON ------------------------

def assert_sru_xml(r):
    """What YAZ needs: HTTP 200, an XML content type and an SRU root, never
    FastAPI's JSON {"detail": "Not Found"} (Koha reports that as "wrong protocol")."""
    assert r.status_code == 200, (r.request.url, r.status_code, r.text[:200])
    assert "xml" in r.headers["content-type"] and "json" not in r.headers["content-type"]
    assert b'"detail"' not in r.content
    root = ET.fromstring(r.content)
    assert root.tag.startswith("{http://www.loc.gov/zing/srw/}")
    return root


def test_every_slug_answers_explain_with_and_without_trailing_slash():
    table = tg.load(TARGETS_JSON)
    with gateway(table, zeus_http=httpx.AsyncClient()) as client:
        for tid in IDS:
            for path in (f"/sru/{tid}", f"/sru/{tid}/", f"http://testserver//sru/{tid}"):
                root = assert_sru_xml(client.get(path, params={"operation": "explain", "version": "1.1"}))
                assert root.tag.endswith("}explainResponse"), path
                if table[tid].configured:
                    assert root.findtext(".//{http://explain.z3950.org/dtd/2.0/}database") == f"sru/{tid}"
                    assert table[tid].name in root.findtext(".//{http://explain.z3950.org/dtd/2.0/}title")
                    assert diag(root) == (None, None)
                else:
                    # No upstream address in targets.json yet: said in SRU, not as a 404.
                    uri, msg = diag(root)
                    assert uri == "info:srw/diagnostic/1/1" and "no catalogue address" in msg


def test_every_slug_answers_search_retrieve_in_sru(monkeypatch):
    table = tg.load(TARGETS_JSON)

    async def down(*args, **kwargs):
        from zeus_sru import sru
        raise sru.SourceUnavailable("offline in tests")
    for mod, attr in ((z3950, "search"), (__import__("sru_gateway.upstream_sru").upstream_sru, "search")):
        monkeypatch.setattr(mod, attr, down)
    offline = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with gateway(table, http=offline, zeus_http=offline) as client:
        for tid in IDS:
            for path in (f"/sru/{tid}", f"/sru/{tid}/"):
                r = client.get(path, params={"operation": "searchRetrieve", "version": "1.1",
                                             "query": "dc.title=x", "maximumRecords": "1"})
                root = assert_sru_xml(r)
                assert root.tag.endswith("}searchRetrieveResponse"), path
                assert root.findtext("zs:numberOfRecords", namespaces=NS) is not None


def test_unknown_slug_is_diagnostic_235_under_explain_and_search():
    table = tg.load(TARGETS_JSON)
    with gateway(table, zeus_http=httpx.AsyncClient()) as client:
        for path in ("/sru/nowhere", "/sru/nowhere/", "/sru/NoWhere"):
            root = assert_sru_xml(client.get(path, params={"operation": "explain"}))
            assert root.tag.endswith("}explainResponse")
            assert diag(root)[0] == "info:srw/diagnostic/1/235"
            assert root.findtext(".//diag:details", namespaces=NS) == "nowhere"
            assert "Target not found or not configured" in diag(root)[1]
            root = assert_sru_xml(client.get(path, params={"operation": "searchRetrieve",
                                                           "query": "dc.title=x"}))
            assert root.tag.endswith("}searchRetrieveResponse")
            assert diag(root)[0] == "info:srw/diagnostic/1/235"


def test_no_route_ever_answers_json_404():
    with gateway(tg.load(TARGETS_JSON), zeus_http=httpx.AsyncClient()) as client:
        for path in ("/", "/sr", "/nothing/here", "/srubn", "/sru/bn/x/y"):
            root = assert_sru_xml(client.get(path, params={"operation": "explain"}))
            assert root.tag.endswith("}explainResponse")
            assert diag(root)[0] in ("info:srw/diagnostic/1/235", "info:srw/diagnostic/1/1")
        root = assert_sru_xml(client.delete("/sru/bn"))
        assert diag(root)[0] == "info:srw/diagnostic/1/4"
        root = assert_sru_xml(client.get("/nothing"))
        assert diag(root)[0] == "info:srw/diagnostic/1/235"


def test_openapi_lists_the_dynamic_route():
    # So a look at https://sru.koha.nexus/openapi.json shows whether this
    # gateway is the one deployed: one /sru/{database} route, not /sru/ufsc.
    with gateway({}) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "/sru/{database}" in paths and "/health" in paths
    assert not any(p.startswith("/sru/") and "{" not in p for p in paths)
