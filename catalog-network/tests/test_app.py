import json
import os
from xml.etree import ElementTree as ET

from conftest import TOKEN

ZS = "{http://www.loc.gov/zing/srw/}"
MARC = "{http://www.loc.gov/MARC21/slim}"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def sru(client, query, **extra):
    params = {"version": "1.1", "operation": "searchRetrieve", "query": query, **extra}
    r = client.get("/sru", params=params)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/xml")
    return ET.fromstring(r.content)


def titles(root):
    return [df.find(f"{MARC}subfield[@code='a']").text
            for df in root.iter(f"{MARC}datafield") if df.get("tag") == "245"]


def total(root):
    return int(root.find(f"{ZS}numberOfRecords").text)


def test_health(loaded):
    body = loaded.get("/health").json()
    assert body["status"] == "ok" and body["records"] == 3 and body["sync"] is True


def test_isbn_both_forms_and_hyphens(loaded):
    for q in ("isbn=8535902775", "dc.isbn=9788535902778", 'bath.isbn="978-85-359-0277-8"', "8535902775"):
        root = sru(loaded, q)
        assert total(root) == 1, q
        assert titles(root) == ["Dom Casmurro /"]


def test_what_koha_reads(loaded):
    """The record shape the Zeus bridge proved on a live Koha: schema
    "marcxml", packing xml, a MARC21 slim <record> inside recordData."""
    root = sru(loaded, "isbn=0140449094")
    rec = root.find(f"{ZS}records/{ZS}record")
    assert rec.find(f"{ZS}recordSchema").text == "marcxml"
    assert rec.find(f"{ZS}recordPacking").text == "xml"
    assert rec.find(f"{ZS}recordData/{MARC}record/{MARC}leader") is not None
    assert rec.find(f"{ZS}recordPosition").text == "1"
    # Local fields of the library that sent it never leave the pool.
    root = sru(loaded, "isbn=8535902775")
    assert not [df for df in root.iter(f"{MARC}datafield") if df.get("tag")[:1] == "9"]


def test_title_author_accents_and_booleans(loaded):
    assert titles(sru(loaded, 'dc.title="memorias postumas"')) == ["Memórias póstumas de Brás Cubas /"]
    assert total(sru(loaded, "dc.creator=machado")) == 2
    assert total(sru(loaded, "author=scott-buccleuch")) == 1
    assert total(sru(loaded, 'dc.title="dom casmurro" and dc.creator="machado"')) == 1
    assert total(sru(loaded, "title=casmurro or title=relatorio")) == 2
    assert total(sru(loaded, "author=machado not title=casmurro")) == 1
    assert total(sru(loaded, "title=casm*")) == 1
    assert total(sru(loaded, "romance")) == 1                       # subject, bare term
    assert total(sru(loaded, "cql.allRecords=1")) == 3
    assert total(sru(loaded, "title=nada")) == 0


def test_paging(loaded):
    root = sru(loaded, "cql.allRecords=1", maximumRecords="2")
    assert total(root) == 3 and len(root.findall(f"{ZS}records/{ZS}record")) == 2
    assert root.find(f"{ZS}nextRecordPosition").text == "3"
    root = sru(loaded, "cql.allRecords=1", startRecord="3")
    assert len(root.findall(f"{ZS}records/{ZS}record")) == 1
    root = sru(loaded, "cql.allRecords=1", startRecord="9")
    assert "61" in root.find(".//{http://www.loc.gov/zing/srw/diagnostic/}uri").text


def test_version_12_string_packing_and_diagnostics(loaded):
    root = sru(loaded, "isbn=8535902775", version="1.2", recordPacking="string")
    assert root.find(f"{ZS}version").text == "1.2"
    data = root.find(f"{ZS}records/{ZS}record/{ZS}recordData").text
    assert "Dom Casmurro" in data
    diag = "{http://www.loc.gov/zing/srw/diagnostic/}uri"
    assert sru(loaded, "title=(").find(f".//{diag}").text.endswith("/10")
    assert sru(loaded, "isbn=1", recordSchema="dc").find(f".//{diag}").text.endswith("/66")
    assert sru(loaded, "isbn=1", version="2.0").find(f".//{diag}").text.endswith("/5")


def test_explain_and_soap(loaded):
    root = ET.fromstring(loaded.get("/sru").content)
    assert root.tag == f"{ZS}explainResponse"
    assert "koha.nexus" in loaded.get("/sru").text
    soap = ('<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>'
            '<SRW:searchRetrieveRequest xmlns:SRW="http://www.loc.gov/zing/srw/"><SRW:version>1.1</SRW:version>'
            '<SRW:query>isbn=8535902775</SRW:query></SRW:searchRetrieveRequest></SOAP-ENV:Body></SOAP-ENV:Envelope>')
    root = ET.fromstring(loaded.post("/sru", content=soap, headers={"Content-Type": "text/xml"}).content)
    assert root.tag.endswith("Envelope") and total(root.find(f".//{ZS}searchRetrieveResponse")) == 1
    r = loaded.post("/sru", content="query=isbn%3D8535902775&version=1.1",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert total(ET.fromstring(r.content)) == 1


def test_sync_needs_a_token(client, collection):
    assert client.post("/api/records/sync", content=collection).status_code == 401
    r = client.post("/api/records/sync", content=collection, headers={"Authorization": "Bearer wrong-token-000000000000"})
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert client.get("/health").json()["records"] == 0


def test_sync_counts_and_dedupes(loaded, collection):
    body = loaded.post("/api/records/sync", content=collection, headers=AUTH).json()
    assert body == {"library": "biblioteca-a", "received": 3, "inserted": 0, "updated": 0, "unchanged": 3,
                    "rejected": []}
    # The same work from another catalogue (ISBN-10 only, other title words): replaces it.
    newer = ('<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader>'
             '<datafield tag="020" ind1=" " ind2=" "><subfield code="a">978-85-359-0277-8</subfield></datafield>'
             '<datafield tag="245" ind1="1" ind2="0"><subfield code="a">Dom Casmurro :</subfield>'
             '<subfield code="b">romance /</subfield></datafield></record>')
    bad = '<record><leader>00000nam a2200000 a 4500</leader></record>'
    r = loaded.post("/api/records/sync", content=json.dumps({"records": [newer, bad]}),
                    headers={**AUTH, "Content-Type": "application/json"})
    assert r.json() == {"library": "biblioteca-a", "received": 2, "inserted": 0, "updated": 1, "unchanged": 0,
                        "rejected": [{"index": 1, "error": "no title (245)"}]}
    assert titles(sru(loaded, "isbn=8535902775")) == ["Dom Casmurro :"]
    assert total(sru(loaded, "title=romance")) == 1
    assert loaded.get("/health").json()["records"] == 3


def test_sync_refuses_garbage_and_floods(client):
    assert client.post("/api/records/sync", content=b"<<<", headers=AUTH).status_code == 400
    assert client.post("/api/records/sync", content=b"<collection/>", headers=AUTH).status_code == 400
    assert client.post("/api/records/sync", content=b'{"records": 3}',
                       headers={**AUTH, "Content-Type": "application/json"}).status_code == 400
    many = "<collection>" + "<record><leader>00000nam a2200000 a 4500</leader></record>" * 1001 + "</collection>"
    assert client.post("/api/records/sync", content=many, headers=AUTH).status_code == 413


def test_tokens_file_is_read_again(tmp_path, catalog):
    from fastapi.testclient import TestClient
    from nexus_catalog.app import create_app
    from nexus_catalog.config import Settings
    path = tmp_path / "tokens"
    settings = Settings(db_path=tmp_path / "catalog.db", tokens_file=path)
    with TestClient(create_app(settings, catalog)) as c:
        assert c.post("/api/records/sync", content=b"<x/>", headers=AUTH).status_code == 503
        path.write_text("# library  token\nbiblioteca-b " + TOKEN + "\ncurta abc\n")
        os.utime(path, ns=(1, 1))
        r = c.post("/api/records/sync", content=b"<collection/>", headers=AUTH)
        assert r.status_code == 400          # past the token check
