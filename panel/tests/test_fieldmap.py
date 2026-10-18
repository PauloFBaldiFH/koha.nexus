"""Edit & Map Fields (docs/field-mapping.md): the operator's field mapping in
the Magic Import engine (kei_import/fieldmap.py, written out of the
installer's heredocs), on its own and through the engine's build and fields
commands, without Koha. No mapping must leave the direct import as it is."""

import importlib
import json
import re
import subprocess
import sys
from collections import Counter
from xml.etree import ElementTree as ET

import pytest
from conftest import INSTALLER

SLIM = "{http://www.loc.gov/MARC21/slim}"


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    d = tmp_path_factory.mktemp("kei")
    text = INSTALLER.read_text(encoding="utf-8")
    for m in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n', text, re.S):
        f = d / m.group(1)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(m.group(2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(d))
    for name in [n for n in sys.modules if n == "kei_import" or n.startswith("kei_import.")]:
        del sys.modules[name]
    yield d, importlib.import_module("kei_import.fieldmap"), importlib.import_module("kei_import.marc")
    sys.path.remove(str(d))


def record(marc, *fields):
    r = marc.Record()
    for f in fields:
        if len(f) == 2:
            r.control(*f)
        else:
            r.add(f[0], f[1][0], f[1][1], *f[2])
    return r


def lines(rec):
    return rec.formatted().splitlines()[1:]


# ---------------------------------------------------------------- the spec

def test_no_mapping_is_the_record_itself(engine):
    _, F, marc = engine
    r = record(marc, ("245", "10", [("a", "Emma")]), ("500", "  ", [("a", "x")]))
    for fm in (F.FieldMap(), F.FieldMap.from_obj({"mappings": []}),
               F.FieldMap.from_obj({"mappings": [{"from": "245$a", "to": "245$a"}, {"from": "500", "to": "500"}]})):
        assert not fm.marc_rules
        assert fm.apply(r) is r


@pytest.mark.parametrize("bad", [
    {"mappings": [{"from": "", "to": "245$a"}]},
    {"mappings": [{"from": "500$a", "to": "24$a"}]},
    {"mappings": [{"from": "500$a", "to": "245"}]},        # subfield to a whole field
    {"mappings": [{"from": "949", "to": "952$p"}]},        # whole field to a subfield
    {"mappings": [{"from": "Tombo", "to": "952"}]},        # a column needs a subfield
    {"mappings": [{"from": "001$a", "to": "035$a"}]},      # control fields have no subfields: a column, then no subfield
    {"version": 2, "mappings": []},
    {"mappings": "500$a=100$a"},
])
def test_bad_mappings_are_refused(engine, bad):
    _, F, _ = engine
    with pytest.raises(F.FieldMapError):
        F.FieldMap.from_obj(bad)


def test_round_trip_and_kinds(engine):
    _, F, _ = engine
    obj = {"version": 1, "mappings": [{"from": "090$a", "to": "082$a"}, {"from": "Tombo", "to": "952$p", "kind": "column"},
                                      {"from": "Autor", "to": "100$a"}, {"from": "500$a", "to": "ignore"}]}
    fm = F.FieldMap.from_obj(obj)
    assert [r.kind for r in fm.rules] == ["marc", "column", "column", "marc"]
    assert F.FieldMap.from_obj(fm.to_obj()).to_obj() == fm.to_obj()
    # A header that looks like a tag stays a column when the panel says so.
    assert F.FieldMap.from_obj({"mappings": [{"from": "100", "to": "245$a", "kind": "column"}]}).columns == {"100": ("245", "a")}


# ---------------------------------------------------------------- records

def test_paulos_targets(engine):
    _, F, marc = engine
    r = record(marc, ("001", "ISIS-7"),
               ("245", "10", [("a", "Orgulho e preconceito")]),
               ("500", "  ", [("a", "AUSTEN, JANE")]),
               ("090", "  ", [("a", "823.91"), ("b", "A933o")]),
               ("595", "  ", [("a", "T-0042"), ("b", "LIV")]),
               ("690", "  ", [("a", "Romance inglês")]),
               ("710", "  ", [("a", "Martin Claret"), ("d", "2010")]))
    fm = F.FieldMap.from_obj({"mappings": [
        {"from": "500$a", "to": "100$a"}, {"from": "090$a", "to": "082$a"}, {"from": "595$a", "to": "952$p"},
        {"from": "595$b", "to": "952$y"}, {"from": "690$a", "to": "650$a"}, {"from": "710$a", "to": "264$b"},
        {"from": "710$d", "to": "264$c"}, {"from": "001", "to": "035$a"}]})
    st = Counter()
    out = fm.apply(r, st, {"branch": "CPL", "itype": "BK"})
    assert lines(out) == [
        "035    $a ISIS-7",
        "082 04 $a 823.91",
        "090    $b A933o",
        "100 1  $a AUSTEN, JANE",
        "245 10 $a Orgulho e preconceito",
        "264  1 $b Martin Claret $c 2010",
        "650  4 $a Romance inglês",
        "952    $p T-0042 $y LIV $a CPL $b CPL",
    ]
    assert st["moved"] == 8 and st["dropped"] == 0 and st["conflicts"] == 0
    assert lines(r)[0] == "001    ISIS-7"        # the source record is not changed


def test_ignore_whole_fields_and_recoding(engine):
    _, F, marc = engine
    r = record(marc, ("245", "10", [("a", "Emma"), ("h", "[texto]")]),
               ("949", "  ", [("a", "B1"), ("c", "x")]), ("949", "  ", [("a", "B2")]),
               ("999", "  ", [("c", "1")]))
    fm = F.FieldMap.from_obj({"mappings": [{"from": "245$h", "to": "ignore"}, {"from": "999", "to": "ignore"},
                                           {"from": "949", "to": "952"}, {"from": "949$a", "to": "952$p"},
                                           {"from": "949$c", "to": "ignore"}]})
    st = Counter()
    out = fm.apply(r, st, {"branch": "CPL", "itype": "BK"})
    assert lines(out) == ["245 10 $a Emma", "952    $p B1 $a CPL $b CPL $y BK", "952    $p B2 $a CPL $b CPL $y BK"]
    assert st["dropped"] == 3


def test_single_fields_take_the_subfield_in_and_conflicts_lose_nothing(engine):
    _, F, marc = engine
    r = record(marc, ("245", "10", [("a", "Emma")]), ("246", "  ", [("a", "um romance")]),
               ("100", "1 ", [("a", "Austen, Jane")]), ("500", "  ", [("a", "AUSTEN, J.")]))
    fm = F.FieldMap.from_obj({"mappings": [{"from": "246$a", "to": "245$b"}, {"from": "500$a", "to": "100$a"}]})
    st = Counter()
    out = fm.apply(r, st)
    assert lines(out) == ["100 1  $a Austen, Jane", "245 10 $a Emma $b um romance", "500    $a AUSTEN, J."]
    assert st["conflicts"] == 1 and "100$a already set" in st["examples"][0]


def test_record_json_round_trip(engine):
    _, F, marc = engine
    r = record(marc, ("001", "7"), ("245", "10", [("a", "Emma"), ("b", "x")]))
    assert F.record_from_obj(json.loads(json.dumps(F.record_obj(r)))).formatted() == r.formatted()


# ---------------------------------------------------------------- the engine

def marcxml(path, marc, records):
    marc.write_marcxml(records, str(path))


def run(d, *args):
    return subprocess.run([sys.executable, str(d / "kei_import_run.py"), *args], capture_output=True, text=True, cwd=d)


def read_out(path):
    out = []
    for r in ET.parse(path).getroot().iter(SLIM + "record"):
        out.append([(f.get("tag"), f.text if f.tag == SLIM + "controlfield" else [(s.get("code"), s.text) for s in f])
                    for f in r if f.tag != SLIM + "leader"])
    return out


def manifest(work, name="manifest.tsv"):
    return [l.split("\t") for l in (work / "out" / name).read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def legacy_marc(engine, tmp_path):
    _, _, marc = engine
    recs = [record(marc, ("245", "10", [("a", "Livro %d" % i)]), ("500", "  ", [("a", "AUTOR %d" % i)]),
                   ("090", "  ", [("a", "869.3")])) for i in range(1, 13)]
    src = tmp_path / "isis.xml"
    marcxml(src, marc, recs)
    return src


def test_build_without_mapping_is_the_direct_import(engine, tmp_path, legacy_marc):
    d, _, _ = engine
    work = tmp_path / "work"
    work.mkdir()
    p = run(d, "build", "--in", str(legacy_marc), "--work", str(work), "--branch", "CPL", "--itype", "BK")
    assert p.returncode == 0, p.stdout + p.stderr
    assert manifest(work) == manifest(work, "manifest-direct.tsv")
    assert "Edit & Map Fields" not in (work / "out" / "preview.txt").read_text(encoding="utf-8")


def test_fields_then_build_with_mapping(engine, tmp_path, legacy_marc):
    d, _, _ = engine
    work = tmp_path / "work"
    work.mkdir()
    base = ["--in", str(legacy_marc), "--work", str(work), "--branch", "CPL", "--itype", "BK"]
    assert run(d, "fields", *base).returncode == 2          # build first
    assert run(d, "build", *base).returncode == 0
    p = run(d, "fields", *base, "--sample", "5")
    assert p.returncode == 0, p.stdout + p.stderr
    fields = json.loads((work / "fields.json").read_text(encoding="utf-8"))
    (s,) = fields["streams"]
    assert s["records_total"] == 12 and len(s["records"]) == 5
    by = {f["from"]: f for f in s["fields"]}
    assert by["500$a"]["count"] == 5 and by["500$a"]["samples"] == ["AUTOR 1", "AUTOR 2", "AUTOR 3"]
    assert by["500$a"]["to"] == "500$a"
    assert [t["to"] for t in fields["targets"]][:3] == ["100$a", "245$a", "245$b"]

    fm = tmp_path / "map.json"
    fm.write_text(json.dumps({"mappings": [{"from": "500$a", "to": "100$a"}, {"from": "090$a", "to": "082$a"}]}))
    p = run(d, "build", *base, "--fieldmap", str(fm))
    assert p.returncode == 0, p.stdout + p.stderr
    (row,) = manifest(work)
    assert row[:3] == ["biblio", "MARCXML", "UTF-8"] and row[3].endswith("mapped-1.xml") and row[4] == "12"
    recs = read_out(row[3])
    assert len(recs) == 12
    assert recs[0] == [("082", [("a", "869.3")]), ("100", [("a", "AUTOR 1")]), ("245", [("a", "Livro 1")])]
    preview = (work / "out" / "preview.txt").read_text(encoding="utf-8")
    assert "Your field mapping" in preview and "values moved: 24" in preview
    # The fields of a second look are still those of the direct import.
    assert run(d, "fields", *base, "--fieldmap", str(fm)).returncode == 0
    again = json.loads((work / "fields.json").read_text(encoding="utf-8"))
    assert "500$a" in {f["from"] for f in again["streams"][0]["fields"]}
    assert again["mapping"]["mappings"][0] == {"from": "500$a", "to": "100$a"}


def test_bad_mapping_file_stops_the_build(engine, tmp_path, legacy_marc):
    d, _, _ = engine
    work = tmp_path / "work"
    work.mkdir()
    fm = tmp_path / "map.json"
    fm.write_text(json.dumps({"mappings": [{"from": "500$a", "to": "1$a"}]}))
    p = run(d, "build", "--in", str(legacy_marc), "--work", str(work), "--fieldmap", str(fm))
    assert p.returncode == 2 and "field mapping cannot be used" in p.stdout


def test_spreadsheet_columns(engine, tmp_path):
    d, _, _ = engine
    src = tmp_path / "acervo.csv"
    src.write_text("Titulo;Observacao;Registro;Estante;Lixo\n"
                   "Dom Casmurro;ASSIS, MACHADO DE;T-1;E3;zz\n"
                   "Dom Casmurro;ASSIS, MACHADO DE;T-2;E3;zz\n"
                   "Iracema;ALENCAR, JOSE DE;T-3;E4;zz\n", encoding="utf-8")
    fm = tmp_path / "map.json"
    fm.write_text(json.dumps({"mappings": [
        {"from": "Titulo", "to": "245$a"}, {"from": "Observacao", "to": "100$a"}, {"from": "Registro", "to": "952$p"},
        {"from": "Estante", "to": "952$z"}, {"from": "Lixo", "to": "ignore"}]}))
    work = tmp_path / "work"
    work.mkdir()
    # The questions come first, as in the panel: this table is the collection.
    answers = tmp_path / "answers.tsv"
    answers.write_text("")
    assert run(d, "analyse", "--in", str(src), "--work", str(work), "--answers", str(answers)).returncode == 0
    qid = (work / "questions.tsv").read_text(encoding="utf-8").split("\t")[0]
    answers.write_text("%s\tbiblio\n" % qid)
    p = run(d, "build", "--in", str(src), "--work", str(work), "--answers", str(answers), "--branch", "CPL", "--itype", "BK",
            "--today", "2026-10-17", "--fieldmap", str(fm))
    assert p.returncode == 0, p.stdout + p.stderr
    preview = (work / "out" / "preview.txt").read_text(encoding="utf-8")
    assert "your mapping" in preview
    recs = {dict(r)["245"][0][1].rstrip(" /"): r for r in read_out(work / "out" / "records.xml")}
    dom = recs["Dom Casmurro"]
    assert ("100", [("a", "Assis, Machado de")]) in dom
    items = [dict(f[1]) for f in dom if f[0] == "952"]
    assert sorted(i["p"] for i in items) == ["T-1", "T-2"] and all(i["z"] == "E3" for i in items)
    assert "zz" not in (work / "out" / "records.xml").read_text(encoding="utf-8")
    # The mapping is for this import only: no saved profile remembers it.
    for f in (work / "profiles-new").glob("*.tsv") if (work / "profiles-new").exists() else []:
        assert "Lixo" not in f.read_text(encoding="utf-8")
    p = run(d, "fields", "--in", str(src), "--work", str(work), "--answers", str(answers), "--fieldmap", str(fm))
    assert p.returncode == 0, p.stdout + p.stderr
    obj = json.loads((work / "fields.json").read_text(encoding="utf-8"))
    cols = {c["from"]: c for c in obj["columns"]}
    assert cols["Estante"]["to"] == "952$z" and cols["Lixo"]["to"] == "ignore" and cols["Observacao"]["to"] == "100$a"
    assert cols["Registro"]["samples"][:2] == ["T-1", "T-2"]
    # The panel's grid: the table's first rows, cell by cell under its headers.
    table = obj["tables"][0]
    assert table["name"] == "acervo.csv" and table["headers"] == ["Titulo", "Observacao", "Registro", "Estante", "Lixo"]
    assert table["rows_total"] == 3 and table["rows"][2] == ["Iracema", "ALENCAR, JOSE DE", "T-3", "E4", "zz"]


def test_table_entry_sample(engine):
    """At most `sample` rows, blank rows skipped, short rows padded, long values cut."""
    _, fieldmap, _ = engine
    data = [["", ""], ["a"]] + [["x%d" % i, "y" * 300] for i in range(20)]
    out = fieldmap.table_entry("t.csv", ["A", "B"], data, 10)
    assert out["rows_total"] == 22 and len(out["rows"]) == 10
    assert out["rows"][0] == ["a", ""] and len(out["rows"][1][1]) == 200
