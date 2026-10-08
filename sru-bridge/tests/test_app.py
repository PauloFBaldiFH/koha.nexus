import asyncio
from xml.etree import ElementTree as ET

import httpx
import pytest
from fastapi.testclient import TestClient

from zeus_sru.app import create_app
from zeus_sru.config import Settings
from zeus_sru.zeus import ZeusClient

NS = {"zs": "http://www.loc.gov/zing/srw/", "marc": "http://www.loc.gov/MARC21/slim",
      "diag": "http://www.loc.gov/zing/srw/diagnostic/"}
EMPTY = "<html><body>Nenhum registro encontrado</body></html>"


class FakeZeus:
    """Answers like Zeus: the Tabamex record only from the chunk holding target 6."""

    def __init__(self, page, fail_all=False, delay=0.05):
        self.page, self.fail_all, self.delay = page, fail_all, delay
        self.requests = []
        self.in_flight = self.peak = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        await asyncio.sleep(self.delay)
        self.in_flight -= 1
        if self.fail_all:
            return httpx.Response(503, text="down")
        targets = [k for k in request.url.params if k.startswith("targets[")]
        body = self.page if "targets[6]" in targets else EMPTY
        return httpx.Response(200, text=body)


def make(page, **kw):
    fake = FakeZeus(page, **kw)
    settings = Settings(cache_ttl=600)
    zeus = ZeusClient(settings, httpx.AsyncClient(transport=httpx.MockTransport(fake)))
    return TestClient(create_app(settings, zeus)), fake


def sru(client, **params):
    params.setdefault("version", "1.1")
    params.setdefault("operation", "searchRetrieve")
    r = client.get("/sru", params=params)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/xml")
    return ET.fromstring(r.content)


def test_isbn_search_returns_marcxml(results_page):
    client, fake = make(results_page)
    with client:
        root = sru(client, query="dc.isbn=9684291426", maximumRecords="10")
    assert root.tag == "{http://www.loc.gov/zing/srw/}searchRetrieveResponse"
    assert root.findtext("zs:version", namespaces=NS) == "1.1"
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "1"
    rec = root.find("zs:records/zs:record", NS)
    assert rec.findtext("zs:recordSchema", namespaces=NS) == "marcxml"
    assert rec.findtext("zs:recordPosition", namespaces=NS) == "1"
    marc = rec.find("zs:recordData/marc:record", NS)
    title = marc.find("marc:datafield[@tag='245']/marc:subfield[@code='a']", NS).text
    assert title.startswith("Tabamex")
    assert marc.findtext("marc:leader", namespaces=NS)[9] == "a"

    # 16 targets -> 2 requests of at most 15, sent concurrently
    assert len(fake.requests) == 2
    assert fake.peak == 2
    for req in fake.requests:
        assert req.url.params["searchType"] == "7"
        assert req.url.params["searchString"] == "9684291426"
        assert req.url.params["operator"] == "and"
        assert sum(k.startswith("targets[") for k in req.url.params) <= 15


def test_title_search_and_cache(results_page):
    client, fake = make(results_page)
    with client:
        sru(client, query='dc.title="tabamex"')
        root = sru(client, query='dc.title="tabamex"', startRecord="1")
    assert fake.requests[0].url.params["searchType"] == "4"
    assert len(fake.requests) == 2   # second SRU call came from the cache
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "1"


def test_no_hits(results_page):
    client, _ = make(EMPTY)
    with client:
        root = sru(client, query="dc.title=nothing")
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "0"
    assert root.find("zs:records", NS) is None


def test_string_packing(results_page):
    client, _ = make(results_page)
    with client:
        root = sru(client, query="dc.isbn=9684291426", recordPacking="string")
    data = root.findtext("zs:records/zs:record/zs:recordData", namespaces=NS)
    assert data.startswith("<marc:record") and "Tabamex" in data


@pytest.mark.parametrize("params,code", [
    ({"query": ""}, "7"),
    ({"query": "dc.title=x", "recordSchema": "dc"}, "66"),
    ({"query": "dc.title=x", "version": "2.0"}, "5"),
    ({"query": "dc.title=x", "operation": "scan"}, "4"),
    ({"query": "dc.title=x", "startRecord": "0"}, "6"),
])
def test_diagnostics(results_page, params, code):
    client, _ = make(results_page)
    with client:
        root = sru(client, **params)
    uri = root.findtext(".//diag:diagnostic/diag:uri", namespaces=NS)
    assert uri == f"info:srw/diagnostic/1/{code}"


def test_zeus_down(results_page):
    client, _ = make(results_page, fail_all=True)
    with client:
        root = sru(client, query="dc.isbn=9684291426")
    assert root.findtext(".//diag:uri", namespaces=NS) == "info:srw/diagnostic/1/1"


def test_explain(results_page):
    client, _ = make(results_page)
    with client:
        r = client.get("/sru")
    root = ET.fromstring(r.content)
    assert root.tag == "{http://www.loc.gov/zing/srw/}explainResponse"
    assert b"marcxml-v1.1" in r.content


def test_health(results_page):
    client, _ = make(results_page)
    with client:
        assert client.get("/health").json()["status"] == "ok"


SOAP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <zs:searchRetrieveRequest xmlns:zs="http://www.loc.gov/zing/srw/">
      <zs:version>1.1</zs:version>
      <zs:query>dc.isbn=9684291426</zs:query>
      <zs:startRecord>1</zs:startRecord>
      <zs:maximumRecords>10</zs:maximumRecords>
      <zs:recordSchema>info:srw/schema/1/marcxml-v1.1</zs:recordSchema>
    </zs:searchRetrieveRequest>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""


def _one_record(root):
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "1"
    rec = root.find("zs:records/zs:record", NS)
    assert rec.findtext("zs:recordSchema", namespaces=NS) == "marcxml"
    title = rec.find("zs:recordData/marc:record/marc:datafield[@tag='245']/marc:subfield[@code='a']", NS)
    assert title.text.startswith("Tabamex")


def test_get_search(results_page):
    client, _ = make(results_page)
    with client:
        r = client.get("/sru", params={"version": "1.1", "operation": "searchRetrieve",
                                       "query": "dc.isbn=9684291426"})
    _one_record(ET.fromstring(r.content))


def test_form_post_search(results_page):
    client, fake = make(results_page)
    with client:
        r = client.post("/sru", data={"version": "1.1", "operation": "searchRetrieve",
                                      "query": "dc.isbn=9684291426", "maximumRecords": "10"})
    assert r.status_code == 200
    _one_record(ET.fromstring(r.content))
    assert fake.requests[0].url.params["searchType"] == "7"


def test_form_post_without_operation_searches(results_page):
    client, _ = make(results_page)
    with client:
        r = client.post("/sru", content="query=dc.title%3Dtabamex&version=1.1",
                        headers={"content-type": "application/x-www-form-urlencoded"})
    _one_record(ET.fromstring(r.content))


def test_soap_post_search_answers_in_soap(results_page):
    client, _ = make(results_page)
    with client:
        r = client.post("/sru", content=SOAP_REQUEST.encode(),
                        headers={"content-type": "text/xml; charset=utf-8", "SOAPAction": ""})
    assert r.status_code == 200
    env = ET.fromstring(r.content)
    assert env.tag == "{http://schemas.xmlsoap.org/soap/envelope/}Envelope"
    root = env.find("{http://schemas.xmlsoap.org/soap/envelope/}Body/zs:searchRetrieveResponse", NS)
    _one_record(root)


def test_plain_xml_post_search(results_page):
    body = SOAP_REQUEST.split("<SOAP-ENV:Body>")[1].split("</SOAP-ENV:Body>")[0].strip()
    client, _ = make(results_page)
    with client:
        r = client.post("/sru/sru", content=body.encode(), headers={"content-type": "text/xml"})
    _one_record(ET.fromstring(r.content))


def test_empty_post_is_explain(results_page):
    client, _ = make(results_page)
    with client:
        r = client.post("/sru")
    assert ET.fromstring(r.content).tag == "{http://www.loc.gov/zing/srw/}explainResponse"


def test_broken_xml_post_is_a_diagnostic_not_a_crash(results_page):
    client, _ = make(results_page)
    with client:
        r = client.post("/sru?operation=searchRetrieve", content=b"<searchRetrieveRequest><query>",
                        headers={"content-type": "text/xml"})
    assert r.status_code == 200
    assert ET.fromstring(r.content).findtext(".//diag:uri", namespaces=NS) == "info:srw/diagnostic/1/7"
