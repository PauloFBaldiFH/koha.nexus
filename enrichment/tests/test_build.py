"""enrich_build end to end, on small dumps written by the tests in every
format the builder reads."""

import gzip
import json
import sqlite3

import pytest
import zstandard
from conftest import bib

from enrich_build import readers
from enrich_build.__main__ import main as cli
from enrich_build.build import Builder, SourceConfig, load_config
from enrich_build.release import compress, verify
from nexus_enrich import Policy, enrich, marc
from nexus_enrich.marc import Field, Record
from nexus_enrich.static import StaticDB

ISBN = "9788571644953"


def authority(name, dates, variant, lccn, rid):
    rec = Record(leader="00000nz  a2200000n  4500")
    rec.fields.append(Field("001", data=rid))
    rec.fields.append(Field("010", " ", " ", [("a", lccn)]))
    rec.fields.append(Field("100", "1", " ", [("a", name + ","), ("d", dates)]))
    rec.fields.append(Field("400", "1", " ", [("a", variant)]))
    return rec


def write_zst_jsonl(path, lines):
    data = "\n".join(json.dumps(x, ensure_ascii=False) for x in lines).encode()
    path.write_bytes(zstandard.ZstdCompressor().compress(data))


@pytest.fixture
def dumps(tmp_path):
    rich = bib("Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, publisher="Companhia das Letras",
               rid="Z1", subjects=["Cegueira"], extra=[Field("082", "0", "4", [("a", "869.3")])])
    reuse = bib("Manual de redação", "Martins, Eduardo", isbn=ISBN, year=1997, rid="Z2")
    noisbn = bib("Memorial do convento", "Saramago, José", year=1982, rid="Z3")
    write_zst_jsonl(tmp_path / "zeus.jsonl.zst", [
        {"id": "Z1", "target": "ufsc", "marcxml": marc.to_xml(rich)},
        {"id": "Z2", "target": "usp", "marc": {"leader": reuse.leader, "fields": [
            {f.tag: f.data} if f.is_control else
            {f.tag: {"ind1": f.ind1, "ind2": f.ind2, "subfields": [{c: v} for c, v in f.subfields]}}
            for f in reuse.fields]}},
        {"id": "Z3", "target": "usp", "iso2709": marc.to_iso2709(noisbn).decode("utf-8")},
        {"id": "Z4", "title": "a line with no record"},
    ])
    loc_xml = ('<collection xmlns="http://www.loc.gov/MARC21/slim">'
               + marc.to_xml(authority("Saramago, José", "1922-2010", "Saramago, José de Sousa", "n  79063737",
                                       "oca00001"))
               + marc.to_xml(bib("Blindness", "Saramago, José", isbn="9780156007757", year=1999, lang="eng",
                                 rid="L1", subjects=[Field("650", " ", "0", [("a", "Blindness"), ("v", "Fiction")])]))
               + "</collection>")
    with gzip.open(tmp_path / "loc.xml.gz", "wt", encoding="utf-8") as fh:
        fh.write(loc_xml)
    (tmp_path / "bn.mrc").write_bytes(
        marc.to_iso2709(bib("Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, rid="BN1",
                            publisher="Cia. das Letras",
                            extra=[Field("520", " ", " ", [("a", "Romance sobre uma epidemia.")])])))
    pool = sqlite3.connect(tmp_path / "catalog.db")
    pool.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, source TEXT, marcxml TEXT)")
    pool.execute("INSERT INTO records VALUES (1, 'biblioteca-1', ?)",
                 (marc.to_xml(bib("Vidas secas", "Ramos, Graciliano", year=1938, rid="P1")),))
    pool.commit()
    pool.close()
    config = {"sources": [
        {"id": "zeus", "name": "Catálogo Zeus", "paths": ["zeus.jsonl.zst"], "mode": "pointer",
         "brazilian": True, "weight": 0.7, "source_field": "target"},
        {"id": "loc", "name": "Library of Congress", "paths": ["loc.xml.gz"], "weight": 1.0},
        {"id": "bn", "name": "Biblioteca Nacional", "paths": ["bn.mrc"], "brazilian": True, "weight": 1.0},
        {"id": "pool", "paths": ["catalog.db"], "brazilian": True, "headings": False},
    ]}
    (tmp_path / "sources.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


def build(dumps, sample=2000):
    out = dumps / "static.db"
    report = Builder(out, load_config(dumps / "sources.json"), dumps, sample).build()
    return out, report


def test_detect_formats(dumps):
    assert readers.detect(dumps / "zeus.jsonl.zst") == "jsonl"
    assert readers.detect(dumps / "loc.xml.gz") == "marcxml"
    assert readers.detect(dumps / "bn.mrc") == "iso2709"
    assert readers.detect(dumps / "catalog.db") == "pool"
    (dumps / "noext").write_bytes((dumps / "bn.mrc").read_bytes())
    assert readers.detect(dumps / "noext") == "iso2709"


def test_build_counts_sources_and_errors(dumps):
    db, report = build(dumps)
    assert report.versions == 6 and report.pointers == 3 and report.authorities == 1
    assert report.error_count == 1 and "no record in keys" in report.errors[0]
    conn = sqlite3.connect(db)
    sources = dict(conn.execute("SELECT id, records FROM sources"))
    # source_field splits the Zeus dump by target; each gets the config's mode.
    assert sources == {"zeus": 0, "ufsc": 1, "usp": 2, "loc": 1, "bn": 1, "pool": 1}
    assert conn.execute("SELECT mode, brazilian FROM sources WHERE id = 'usp'").fetchone() == ("pointer", 1)


def test_pointer_rows_have_no_body_and_full_rows_do(dumps):
    db, _ = build(dumps)
    conn = sqlite3.connect(db)
    bodies = dict(conn.execute("SELECT remote_id, body IS NOT NULL FROM versions"))
    assert bodies == {"Z1": 0, "Z2": 0, "Z3": 0, "L1": 1, "BN1": 1, "P1": 1}


def test_reused_isbn_makes_its_own_cluster(dumps):
    db, _ = build(dumps)
    conn = sqlite3.connect(db)
    clusters = dict(conn.execute("SELECT remote_id, cluster_id FROM versions"))
    assert clusters["Z1"] == clusters["BN1"]          # same book, two sources
    assert clusters["Z2"] != clusters["Z1"]           # same ISBN, another title


def test_authority_record_establishes_the_heading(dumps):
    db, _ = build(dumps)
    s = StaticDB(db)
    rows = s.headings("personal", "saramago jose")
    first = rows[0]
    assert first["source"] == "loc" and first["preliminary"] == 0
    assert first["dates"] == "1922-2010" and first["lccn"] == "n79063737"
    assert first["variants"] == "Saramago, José de Sousa"
    # The same name gathered from bibliographic records (without dates,
    # so LoC's own bib record gives a second, preliminary entry).
    gathered = {r["source"]: r["occurrences"] for r in rows if r["preliminary"]}
    assert gathered == {"ufsc": 1, "usp": 1, "bn": 1, "loc": 1}
    # The pool source says "headings": false.
    assert not s.headings("personal", "ramos graciliano")
    assert s.headings("topical", "blindness")[0]["thesaurus"] == "lcsh"


def test_static_lookup_and_enrich_end_to_end(dumps):
    db, _ = build(dumps)
    s = StaticDB(db)
    local = bib("Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, publisher="Companhia das Letras")
    cands, pointers = s.candidates_for(local)
    assert {(c.source, c.remote_id) for c in cands} == {("bn", "BN1")}
    assert {(p.source, p.remote_id) for p in pointers} == {("ufsc", "Z1"), ("usp", "Z2")}
    assert cands[0].brazilian and cands[0].weight == 1.0
    res = enrich(local, cands, Policy(today="20261017"))
    assert [a.group for a in res.additions] == ["520"]
    titles = {c.remote_id for c in s.search(title="cegueira")[0]}
    assert titles == {"BN1"}
    assert {c.remote_id for c in s.search(author="saramago")[0]} == {"BN1", "L1"}


def test_dictionary_is_trained_and_used(tmp_path):
    xml = ['<collection xmlns="http://www.loc.gov/MARC21/slim">']
    for i in range(300):
        xml.append(marc.to_xml(bib(f"Livro número {i}", f"Autor{i}, Fulano", year=1950 + i % 70, rid=f"R{i}",
                                   publisher="Editora Exemplo", subjects=["Literatura brasileira"])))
    xml.append("</collection>")
    (tmp_path / "many.xml").write_text("".join(xml), encoding="utf-8")
    (tmp_path / "sources.json").write_text(json.dumps({"sources": [{"id": "x", "paths": ["many.xml"]}]}))
    db = tmp_path / "static.db"
    report = Builder(db, load_config(tmp_path / "sources.json"), tmp_path, sample=300).build()
    assert report.dictionary and report.versions == 300
    s = StaticDB(db)
    assert s.meta("zstd_dict")
    cands, _ = s.by_work(s.conn.execute("SELECT work_key FROM versions WHERE remote_id = 'R7'").fetchone()[0])
    assert cands[0].record.first("245").get("a") == "Livro número 7"


def test_replaced_remote_id_keeps_the_last_version(tmp_path):
    a = bib("Título antigo", "X, Y", year=2000, rid="R1")
    b = bib("Título novo", "X, Y", year=2000, rid="R1")
    (tmp_path / "d.mrc").write_bytes(marc.to_iso2709(a) + marc.to_iso2709(b))
    (tmp_path / "sources.json").write_text(json.dumps({"sources": [{"id": "x", "paths": ["d.mrc"]}]}))
    db = tmp_path / "static.db"
    report = Builder(db, load_config(tmp_path / "sources.json"), tmp_path).build()
    assert report.versions == 1
    s = StaticDB(db)
    assert [c.remote_id for c in s.search(title="novo")[0]] == ["R1"]
    assert s.search(title="antigo")[0] == []


def test_release_compress_and_verify(dumps):
    db, _ = build(dumps)
    asset, sums = compress(db, dumps / "nexus-enrich-2026.10.db.zst")
    assert sums.read_text().endswith("  nexus-enrich-2026.10.db.zst\n")
    info = verify(asset)
    assert info["verified"] and info["integrity"] == "ok" and info["versions"] == 6
    # A frame decompressible within a small window (no --long).
    params = zstandard.get_frame_parameters(asset.read_bytes()[:18])
    assert params.window_size <= 8 << 20
    with pytest.raises(ValueError, match="does not match"):
        verify(asset, "0" * 64)


def test_cli(dumps, capsys):
    assert cli(["build", str(dumps / "sources.json"), "--out", str(dumps / "cli.db"),
                "--report", str(dumps / "report.json")]) == 0
    assert json.loads((dumps / "report.json").read_text())["versions"] == 6
    capsys.readouterr()
    assert cli(["inspect", str(dumps / "cli.db")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert {s["id"] for s in out["sources"]} >= {"loc", "bn"} and out["meta"]["schema"] == "1"
    assert cli(["release", str(dumps / "cli.db"), "--month", "2026.10"]) == 0
    assert cli(["verify", str(dumps / "nexus-enrich-2026.10.db.zst")]) == 0


def test_config_errors(tmp_path):
    with pytest.raises(ValueError, match="mode"):
        SourceConfig.from_dict({"id": "x", "paths": ["a"], "mode": "copy"})
    with pytest.raises(ValueError, match="no paths"):
        SourceConfig.from_dict({"id": "x"})
