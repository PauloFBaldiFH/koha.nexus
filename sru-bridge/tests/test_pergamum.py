from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import pytest
from fastapi.testclient import TestClient

from pergamum_sru import marc as pmarc
from pergamum_sru import pergamum
from pergamum_sru.app import create_app
from pergamum_sru.config import Settings
from pergamum_sru.pergamum import PergamumClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NS = {"zs": "http://www.loc.gov/zing/srw/", "marc": "http://www.loc.gov/MARC21/slim",
      "diag": "http://www.loc.gov/zing/srw/diagnostic/"}
RESULTS = (FIXTURES / "pergamum_results.html").read_text(encoding="utf-8")
MARC_PAGE = (FIXTURES / "pergamum_marc.html").read_text(encoding="utf-8")


class FakePergamum:
    def __init__(self, results=RESULTS, down=False, charset="utf-8"):
        self.results, self.down, self.charset = results, down, charset
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            return httpx.Response(503, text="down")
        rs = request.url.params["rs"]
        body = self.results if rs == "ajax_resultados" else MARC_PAGE
        headers = {"content-type": "text/html" + (f"; charset={self.charset}" if self.charset else "")}
        enc = self.charset or "iso-8859-1"
        return httpx.Response(200, content=body.encode(enc), headers=headers)


def make(**kw):
    fake = FakePergamum(**kw)
    settings = Settings()
    client = PergamumClient(settings, httpx.AsyncClient(transport=httpx.MockTransport(fake)))
    return TestClient(create_app(settings, client)), fake


def sru(client, **params):
    params.setdefault("version", "1.1")
    params.setdefault("operation", "searchRetrieve")
    r = client.get("/sru", params=params)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/xml")
    return ET.fromstring(r.content)


def calls(fake, rs):
    return [r for r in fake.requests if r.url.params["rs"] == rs]


# ---- MARC text ---------------------------------------------------------

def test_marc_text_to_marcxml():
    block = pergamum.extract_marc(MARC_PAGE)
    rec = pmarc.text_to_marcxml(block)
    tags = [f.get("tag") for f in rec if f.get("tag")]
    # Bare \r, escaped \r and \r\n all split lines; the first tag is 001, not "\r0".
    assert tags == ["001", "005", "020", "100", "245", "260", "650"]
    assert rec.findtext("marc:leader", namespaces=NS) == pmarc.DEFAULT_LEADER
    assert rec.findtext("marc:controlfield[@tag='001']", namespaces=NS) == "98765"
    f100 = rec.find("marc:datafield[@tag='100']", NS)
    assert (f100.get("ind1"), f100.get("ind2")) == ("1", " ")
    f245 = rec.find("marc:datafield[@tag='245']", NS)
    assert (f245.get("ind1"), f245.get("ind2")) == ("1", "0")
    sub = {s.get("code"): s.text for s in f245}
    # Accents kept, entities decoded, the record separator gone.
    assert sub["c"] == "Machado de Assis ; ilustrações de João & Cia."
    assert rec.findtext("marc:datafield[@tag='260']/marc:subfield[@code='a']", namespaces=NS) == "São Paulo :"
    assert rec.findtext("marc:datafield[@tag='650']/marc:subfield[@code='a']", namespaces=NS) == "Ficção brasileira."
    assert rec.find("marc:datafield[@tag='650']", NS).get("ind2") == "4"
    # Every datafield has a subfield (852 and 090 were empty and are gone).
    assert all(len(df) for df in rec.iterfind("marc:datafield", NS))
    assert "\x1e" not in ET.tostring(rec, encoding="unicode")


def test_leader_line_is_used():
    rec = pmarc.text_to_marcxml("LDR 01234nam a2200277 a 4500\r001 1\r")
    assert rec.findtext("marc:leader", namespaces=NS) == "01234nam a2200277 a 4500"
    assert [c.get("tag") for c in rec.iterfind("marc:controlfield", NS)] == ["001"]


def test_xml_invalid_controls_are_dropped():
    rec = pmarc.text_to_marcxml("245 10 $a Bad\x1fchar\x00s\r")
    ET.fromstring(ET.tostring(rec))   # parses back
    assert rec.findtext(".//marc:subfield", namespaces=NS) == "Bad char s"


def test_parse_results():
    count, ids = pergamum.parse_results(RESULTS)
    assert count == 2 and ids == ["98765", "11111"]
    assert pergamum.parse_results("N&uacute;mero de Registros Encontrados: <b>1.234</b>")[0] == 1234
    assert pergamum.parse_results("nada")[1] == []


def test_escaped_markers():
    assert pergamum.extract_marc("x&lt;inicio&gt;001 1&lt;fim&gt;y") == "001 1"


# ---- SRU endpoint ------------------------------------------------------

def test_count_then_records_like_koha():
    client, fake = make()
    with client:
        root = sru(client, query='dc.title="dom casmurro"', maximumRecords="0")
        assert root.findtext("zs:numberOfRecords", namespaces=NS) == "2"
        assert root.find("zs:records", NS) is None
        assert calls(fake, "ajax_conteudo_pastas") == []
        root = sru(client, query='dc.title="dom casmurro"', maximumRecords="20")
    # The result list came from the cache the second time.
    assert len(calls(fake, "ajax_resultados")) == 1
    search = calls(fake, "ajax_resultados")[0]
    assert search.url.params.get_list("rsargs[]") == [
        "0", "dom casmurro", "TITULO", "obra", "50", "", "", "", "-1"]
    assert [r.url.params["rsargs[]"] for r in calls(fake, "ajax_conteudo_pastas")] == ["98765", "11111"]
    recs = root.findall("zs:records/zs:record", NS)
    assert len(recs) == 2
    first = recs[0]
    assert first.findtext("zs:recordSchema", namespaces=NS) == "info:srw/schema/1/marcxml-v1.1"
    assert first.findtext("zs:recordPacking", namespaces=NS) == "xml"
    assert [r.findtext("zs:recordPosition", namespaces=NS) for r in recs] == ["1", "2"]
    assert first.find("zs:recordData/marc:record/marc:datafield[@tag='245']", NS) is not None


def test_paging_fetches_only_the_page():
    client, fake = make()
    with client:
        root = sru(client, query="dc.title=x", startRecord="2", maximumRecords="1")
    assert [r.url.params["rsargs[]"] for r in calls(fake, "ajax_conteudo_pastas")] == ["11111"]
    assert root.findtext("zs:records/zs:record/zs:recordPosition", namespaces=NS) == "2"


@pytest.mark.parametrize("query,kind,term", [
    ("dc.isbn=978-85-359-0277-8", "ISBN", "9788535902778"),
    ('dc.author="machado de assis"', "AUTOR", "machado de assis"),
    ("casmurro", "TITULO", "casmurro"),
])
def test_search_types(query, kind, term):
    client, fake = make()
    with client:
        sru(client, query=query, maximumRecords="0")
    args = calls(fake, "ajax_resultados")[0].url.params.get_list("rsargs[]")
    assert (args[1], args[2]) == (term, kind)


def test_no_hits():
    client, _ = make(results="<p>Nenhum registro</p>")
    with client:
        root = sru(client, query="dc.title=nothing")
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "0"


def test_latin1_page_without_charset():
    client, _ = make(charset="")
    with client:
        root = sru(client, query="dc.title=x", maximumRecords="1")
    assert "ilustrações" in ET.tostring(root, encoding="unicode")


def test_pergamum_down():
    client, _ = make(down=True)
    with client:
        root = sru(client, query="dc.title=x")
    assert root.findtext(".//diag:uri", namespaces=NS) == "info:srw/diagnostic/1/1"
    assert "Rede Pergamum" in root.findtext(".//diag:message", namespaces=NS)


def test_explain_and_health():
    client, _ = make()
    with client:
        r = client.get("/sru")
        assert b"Rede Pergamum" in r.content
        assert client.get("/health").json()["status"] == "ok"
