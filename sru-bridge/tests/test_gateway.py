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
from zeus_sru.config import Settings as ZeusSettings
from zeus_sru.cql import parse
from zeus_sru.zeus import ZeusClient

NS = {"zs": "http://www.loc.gov/zing/srw/", "marc": "http://www.loc.gov/MARC21/slim",
      "diag": "http://www.loc.gov/zing/srw/diagnostic/"}
TARGETS_JSON = Path(__file__).resolve().parents[1] / "sru_gateway" / "targets.json"
IDS = ("bn ufsc unicamp usp uerj ufg ufmg ufpe ufscar ufu ufrgs uff senado nlm harvard uw_madison mit psu "
       "upenn tufts fsu ubc trent sfu utoronto bl oxford bne bcl bizkaia aladi sbn_it abes_fr swb_de "
       "uhamburg bn_polonia slsp nkc rsl bashkir bna biblored pucp upc_peru christchurch juac_julac "
       "monash_sa pergamum").split()


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

def test_targets_json_has_the_48_ids_in_order():
    data = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))
    assert [t["id"] for t in data["targets"]] == IDS
    table = tg.load(TARGETS_JSON)
    assert len(table) == 48
    kinds = {t.id: t.kind for t in table.values()}
    assert kinds["ufsc"] == "zeus" and kinds["pergamum"] == "pergamum"
    assert {k for k, v in kinds.items() if v == "z3950"} == {"bl", "sbn_it", "swb_de"}
    assert not any({"user", "password"} & set(t) for t in data["targets"])


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
    with gateway(table, zeus=ZeusClient(ZeusSettings(), httpx.AsyncClient())) as client:
        r = client.get("/sru/bn")
        assert b"explainResponse" in r.content
        h = client.get("/health").json()
    assert h["targets"] == 48 and "ufsc" in h["configured"] and "bn" in h["missing"]


def test_ufsc_goes_to_zeus(marcxml_page):
    seen = []

    def answer(request):
        seen.append(request)
        return httpx.Response(200, text=marcxml_page)
    zeus = ZeusClient(ZeusSettings(), httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    table = {"ufsc": tg.make_target({"id": "ufsc", "name": "UFSC", "kind": "zeus"})}
    with gateway(table, zeus=zeus) as client:
        root = search(client, "/sru/ufsc", query="dc.isbn=9684291426", maximumRecords="5")
    assert seen and int(root.findtext("zs:numberOfRecords", namespaces=NS)) >= 1
    assert titles(root)


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
