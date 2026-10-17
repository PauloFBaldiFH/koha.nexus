"""nexus_gateway's authority search (database _union-aut): Koha's
authority search indexes, the BN > Brazilian > LoC order, no LCSH
subjects, MARC21 authority records, over HTTP, and its Koha row."""

import json
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from conftest import bib
from test_authority import auth_rec, name, write

from enrich_build.build import Builder, SourceConfig
from nexus_enrich import marc
from nexus_enrich.marc import Field
from nexus_gateway import cql, koha_sql
from nexus_gateway.authorities import ALL_KINDS, kinds_of
from nexus_gateway.config import Settings
from nexus_gateway.engine import Engine, Static
from nexus_gateway.learned import Learned
from nexus_gateway.server import make_server
from nexus_gateway.targets import load

TARGETS = Path(__file__).resolve().parents[1] / "nexus_gateway" / "targets.json"
ZS = "{http://www.loc.gov/zing/srw/}"


@pytest.fixture(scope="module")
def static_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("gwauth")
    write(d / "bn.xml", [
        bib("Ensaio sobre a cegueira", None, rid="BN1", extra=[name("100", "Saramago, José", "1922-2010")]),
    ])
    write(d / "ufpr.xml", [
        bib("Livro", None, rid="U1", subjects=["Cegueira"],
            extra=[name("100", "Silva, José", "1900-1980"),
                   Field("710", "2", " ", [("a", "Universidade Federal do Paraná")])]),
    ])
    write(d / "loc.xml", [
        auth_rec("100", [("a", "Saramago, José,"), ("d", "1922-2010")], ["Saramago, José de Sousa"], "oca1",
                 "n 79063737"),
        auth_rec("100", [("a", "Assis, Machado de,"), ("d", "1839-1908")], ["Machado de Assis"], "oca2", "n 80000001"),
        auth_rec("150", [("a", "Blindness")], (), "sh1"),
    ])
    sources = [SourceConfig.from_dict({"id": "bn", "name": "Biblioteca Nacional", "paths": ["bn.xml"],
                                       "brazilian": True}),
               SourceConfig.from_dict({"id": "ufpr", "name": "UFPR", "paths": ["ufpr.xml"], "brazilian": True}),
               SourceConfig.from_dict({"id": "loc", "name": "Library of Congress", "paths": ["loc.xml"]})]
    out = d / "static.db"
    assert Builder(out, sources, d).build().error_count == 0
    return out


@pytest.fixture
def engine(static_db, tmp_path):
    return Engine(Static(static_db), Learned(tmp_path / "learned.db"), load(TARGETS))


def run(engine, query, start=1, maximum=10):
    return engine.search("_union-aut", cql.parse(query), start, maximum)


def heading(rec):
    f = next(f for f in rec.fields if f.tag[0] == "1" and not f.is_control)
    return f.tag, [(c, v) for c, v in f.subfields]


def sub(rec, tag, code):
    return [v for f in rec.fields if f.tag == tag and not f.is_control for c, v in f.subfields if c == code]


def test_indexes_name_the_kinds():
    assert kinds_of(cql.parse("bath.personalName=x")) == ("personal",)
    assert kinds_of(cql.parse("dc.subject=x")) == ("topical", "geographic", "genre")
    assert kinds_of(cql.parse("bath.name=x")) == ("personal", "corporate", "meeting")
    assert kinds_of(cql.parse("x")) == ALL_KINDS and kinds_of(cql.parse("cql.serverChoice=x")) == ALL_KINDS
    assert cql.parse("bath.personalName=x") == cql.Clause("author", "=", "x")     # index kept, not compared


def test_personal_name_bn_first_as_authority_records(engine):
    r = run(engine, 'bath.personalName="saramago"')
    assert r.origin == "static" and r.total == 2
    bn, loc = r.records
    assert bn.leader[6] == "z" and heading(bn) == ("100", [("a", "Saramago, José,"), ("d", "1922-2010")])
    assert sub(bn, "670", "a")[0].startswith("Biblioteca Nacional")
    assert bn.control("008")[33] == "d" and sub(bn, "667", "a")       # gathered from records: preliminary
    assert sub(loc, "670", "a")[0].startswith("Library of Congress") and sub(loc, "010", "a") == ["n79063737"]
    assert sub(loc, "400", "a") == ["Saramago, José de Sousa"] and loc.control("008")[33] == "c"


def test_variants_any_kind_and_paging(engine):
    r = run(engine, '"machado de assis"')
    assert [heading(x)[1][0][1] for x in r.records] == ["Assis, Machado de,"]
    assert run(engine, "bath.corporateName=machado").total == 0
    r = run(engine, "bath.name=jose", start=2, maximum=1)
    assert r.total == 3 and len(r.records) == 1


def test_subjects_never_lcsh(engine):
    assert run(engine, "dc.subject=blindness").total == 0
    r = run(engine, "dc.subject=cegueira")
    assert r.total == 1 and heading(r.records[0]) == ("150", [("a", "Cegueira")])


def test_corporate_and_boolean(engine):
    r = run(engine, 'bath.corporateName="federal parana"')
    assert r.total == 1 and heading(r.records[0])[0] == "110"
    assert run(engine, "bath.personalName=jose not bath.personalName=silva").total == 2
    assert run(engine, "bath.personalName=jose and dc.subject=cegueira").total == 0


def test_without_static_db(tmp_path):
    eng = Engine(Static(tmp_path / "missing.db"), None, load(TARGETS))
    assert eng.search("_union-aut", cql.parse("x"), 1, 10).origin == "none"


@pytest.fixture
def http(static_db, tmp_path):
    settings = Settings(port=0, static_db=static_db, learned_db=tmp_path / "l.db", live=False)
    srv = make_server(Engine(Static(static_db), Learned(settings.learned_db), load(TARGETS)), settings)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_http_koha_authority_query(http):
    # What Koha sends for the "Personal name" box through the row's SRU fields.
    q = urllib.parse.quote('bath.personalName="Saramago, José"')
    with urllib.request.urlopen(f"{http}/sru/_union-aut?version=1.1&operation=searchRetrieve&query={q}"
                                "&recordSchema=marcxml&maximumRecords=20", timeout=5) as resp:
        root = ET.fromstring(resp.read())
    assert root.find(f"{ZS}numberOfRecords").text == "2"
    records = marc.parse_xml(ET.tostring(root))
    assert [r.leader[6] for r in records] == ["z", "z"]
    with urllib.request.urlopen(f"{http}/sru/_union-aut?operation=explain", timeout=5) as resp:
        assert "autoridades" in resp.read().decode()


def test_koha_row_and_panel_list():
    sql = koha_sql.render(load(TARGETS))
    six = sql.split("-- 6.")[1]
    assert "'sru/_union-aut', 'KOHA.NEXUS (AUTORIDADES)', 1, 0" in six and "'authority'" in six
    assert "authorpersonal=bath.personalName" in six and "subject=dc.subject" in six
    assert "SET checked" not in six                                  # the librarian's tick is kept
    data = json.loads(koha_sql.PANEL_LIST.read_text(encoding="utf-8"))
    auth = [t for t in data["targets"] if t.get("recordtype") == "authority"]
    assert auth[0]["db"] == "sru/_union-aut" and auth[0]["sru_fields"] == koha_sql.AUTH_SRU_FIELDS
