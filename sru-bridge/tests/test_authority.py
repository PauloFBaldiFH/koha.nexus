"""/sru/bn-aut: MARC21 authority records built from /sru/bn's bibliographic
ones. Zeus is a stand-in page here (the cloud cannot reach the catalogue)."""

from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import pytest
from fastapi.testclient import TestClient

from sru_gateway import authority, koha_sql
from sru_gateway import targets as tg
from sru_gateway.app import create_app
from sru_gateway.config import Settings

NS = {"zs": "http://www.loc.gov/zing/srw/", "marc": "http://www.loc.gov/MARC21/slim",
      "diag": "http://www.loc.gov/zing/srw/diagnostic/"}
TARGETS_JSON = Path(__file__).resolve().parents[1] / "sru_gateway" / "targets.json"


def bib(*fields: str) -> str:
    """One bibliographic MARCXML block as Zeus embeds it in its page."""
    return ("<record><leader>00959nam a2200277 a 4500</leader>"
            "<controlfield tag=\"001\">000001</controlfield>"
            "<datafield tag=\"020\" ind1=\" \" ind2=\" \"><subfield code=\"a\">9788535902778</subfield></datafield>"
            + "".join(fields) +
            "<datafield tag=\"245\" ind1=\"1\" ind2=\"0\"><subfield code=\"a\">Dom Casmurro /</subfield></datafield>"
            "<datafield tag=\"260\" ind1=\" \" ind2=\" \"><subfield code=\"a\">Rio de Janeiro :</subfield></datafield>"
            "<datafield tag=\"300\" ind1=\" \" ind2=\" \"><subfield code=\"a\">256 p.</subfield></datafield>"
            "</record>")


def df(tag: str, ind1: str, **subs: str) -> str:
    inner = "".join(f"<subfield code=\"{c}\">{v}</subfield>" for c, v in subs.items())
    return f"<datafield tag=\"{tag}\" ind1=\"{ind1}\" ind2=\" \">{inner}</datafield>"


ASSIS = df("100", "1", a="Assis, Machado de,", d="1839-1908.", e="autor")
ASSIS_AGAIN = df("100", "1", a="Assis, Machado de,", d="1839-1908")
BN = df("110", "2", a="Biblioteca Nacional (Brasil).", b="Divisão de Música.")


def page(*records: str) -> str:
    return "<html><body>" + "".join(f"<div class=\"result\">{r}</div>" for r in records) + "</body></html>"


def gateway(answer_page: str, seen: list | None = None):
    def answer(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, text=answer_page)
    http = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    table = {"bn": tg.make_target({"id": "bn", "name": "Fundação Biblioteca Nacional (BN)", "kind": "zeus",
                                   "status": "verified", "group": "national", "target_index": 0})}
    auths = {"bn-aut": tg.Authority("bn-aut", "BIBLIOTECA NACIONAL (AUTORIDADES)", "bn")}
    return TestClient(create_app(Settings(timeout=5), table, auths, zeus_http=http))


def search(client, query, path="/sru/bn-aut", **params):
    r = client.get(path, params={"version": "1.1", "operation": "searchRetrieve", "query": query, **params})
    assert r.status_code == 200 and "xml" in r.headers["content-type"]
    return ET.fromstring(r.content)


def fields(rec):
    return {d.get("tag"): [(s.get("code"), s.text) for s in d.findall("marc:subfield", NS)]
            for d in rec.findall("marc:datafield", NS)}


def test_heading_becomes_one_authority_record():
    seen = []
    with gateway(page(bib(ASSIS), bib(ASSIS_AGAIN), bib(BN)), seen) as client:
        root = search(client, 'bath.personalName="Machado de Assis"')
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "1"
    recs = root.findall(".//marc:record", NS)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.findtext("marc:leader", namespaces=NS) == "00000nz  a2200000n  4500"
    f = fields(rec)
    assert list(f) == ["040", "100", "670"]
    assert f["040"] == [("a", "BR-RjBN"), ("b", "por")]
    assert f["100"] == [("a", "Assis, Machado de"), ("d", "1839-1908")]
    assert f["670"] == [("a", "Acervo Fundação Biblioteca Nacional (Pergamum)")]
    assert rec.find("marc:datafield[@tag='100']", NS).get("ind1") == "1"
    assert not rec.findall("marc:controlfield", NS)
    # Zeus was asked an author search (searchType 1003), whatever index Koha used.
    assert seen and all("1003" in str(r.url) or r.method == "POST" for r in seen)


def test_corporate_heading_and_accents():
    with gateway(page(bib(BN), bib(ASSIS))) as client:
        root = search(client, "dc.creator=biblioteca nacional musica")
    f = fields(root.find(".//marc:record", NS))
    # The full stop before $b stays: it is part of the heading.
    assert f["110"] == [("a", "Biblioteca Nacional (Brasil)."), ("b", "Divisão de Música")]
    assert "245" not in f and "260" not in f and "300" not in f and "020" not in f


def test_records_without_a_heading_answer_a_diagnostic():
    with gateway(page(bib(), bib())) as client:
        root = search(client, "dc.creator=ninguem")
    assert root.findtext(".//diag:uri", namespaces=NS) == "info:srw/diagnostic/1/1"
    assert "100 or 110" in root.findtext(".//diag:message", namespaces=NS)
    assert not root.findall(".//marc:record", NS)


def test_nothing_found_is_zero_records_and_paging_slices():
    with gateway(page()) as client:
        root = search(client, "dc.creator=ninguem")
        assert root.findtext("zs:numberOfRecords", namespaces=NS) == "0"
        assert root.find(".//diag:uri", NS) is None
    other = df("100", "1", a="Assis, Machado de,", d="1839-1908 (pseud.)")
    with gateway(page(bib(ASSIS), bib(other))) as client:
        root = search(client, "assis", startRecord="2", maximumRecords="1")
    assert root.findtext("zs:numberOfRecords", namespaces=NS) == "2"
    assert fields(root.find(".//marc:record", NS))["100"][1] == ("d", "1839-1908 (pseud.)")


def test_bibliographic_route_is_unchanged():
    with gateway(page(bib(ASSIS))) as client:
        root = search(client, "dc.creator=assis", path="/sru/bn")
    rec = root.find(".//marc:record", NS)
    assert rec.findtext("marc:leader", namespaces=NS).startswith("00") and "245" in fields(rec)


def test_tidy_keeps_initials():
    assert authority._tidy("Silva, J.", last=True) == "Silva, J."
    assert authority._tidy("1839-1908.", last=True) == "1839-1908"
    assert authority._tidy("Assis, Machado de,", last=False) == "Assis, Machado de"


def test_targets_json_authorities():
    table = tg.load(TARGETS_JSON)
    auths = tg.load_authorities(TARGETS_JSON, table)
    assert auths == {"bn-aut": tg.Authority("bn-aut", "BIBLIOTECA NACIONAL (AUTORIDADES)", "bn")}
    with TestClient(create_app(Settings(timeout=5), zeus_http=httpx.AsyncClient())) as client:
        assert client.get("/health").json()["authorities"] == ["bn-aut"]
        assert b"explainResponse" in client.get("/sru/bn-aut").content


def test_authority_must_read_a_configured_catalogue(tmp_path):
    for src in ("nowhere", "bne"):
        p = tmp_path / "t.json"
        p.write_text('{"targets": [{"id": "bne", "kind": "missing"}], '
                     '"authorities": [{"id": "x-aut", "from": "%s"}]}' % src)
        with pytest.raises(tg.TargetError):
            tg.load_authorities(p, tg.load(p))


def test_koha_sql_has_the_authority_row():
    table = tg.load(TARGETS_JSON)
    sql = koha_sql.render(table, tg.load_authorities(TARGETS_JSON, table))
    row = next(line for line in sql.splitlines() if line.startswith("INSERT") and "'sru/bn-aut'" in line)
    for part in ("'https://sru.koha.nexus', 443, 'sru/bn-aut', 'BIBLIOTECA NACIONAL (AUTORIDADES)'",
                 "'MARC21', 'utf8'", "'sru', 'authority'"):
        assert part in row
