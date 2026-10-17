"""Paulo's real dump layout (catalogo_zeus_enriquecimento.jsonl.zst): each
line holds "fonte", "id_hash", "resumo", "marc" (the {"LDR", tag:
[{"ind", "subcampos"}]} dict) and, on some lines, "raw_iso2709"."""

import copy
import io
import json
import sqlite3
from pathlib import Path

import pytest
import zstandard

from enrich_build import readers
from enrich_build.build import Builder, SourceConfig, slug
from nexus_enrich import marc, normalize
from nexus_enrich.static import StaticDB

LINE = json.loads((Path(__file__).parent / "fixtures" / "zeus_line.json").read_text(encoding="utf-8"))


def read_one(obj, source_field=""):
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode()
    items = list(readers.read_jsonl(io.BytesIO(data), source_field))
    assert len(items) == 1
    return items[0]


def with_raw(obj):
    """The line plus "raw_iso2709" as the harvester writes it: ISO 2709 text."""
    rec = marc.from_campos(obj["marc"])
    out = copy.deepcopy(obj)
    out["raw_iso2709"] = marc.to_iso2709(rec).decode("utf-8")
    return out


def test_marc_dict_is_read():
    item = read_one(LINE)
    assert not item.error
    rec = item.record
    assert rec.leader.startswith("04657nmm")
    assert rec.first("245").ind1 == "1" and rec.first("245").ind2 == "0"
    assert rec.first("264").ind1 == "3" and rec.first("264").ind2 == "1"
    first_650 = rec.get_fields("650")[0]
    assert first_650.get_all("x") == ["Motocicletas", "Condições de trabalho."]
    assert [c for c, _ in first_650.subfields] == ["a", "x", "x", "2"]
    assert rec.first("082").get("a") == "629.227561362"
    assert rec.first("520").get("a").startswith("A organização")


def test_remote_id_is_001_not_the_hash():
    assert read_one(LINE).remote_id == "99571403509501"
    no001 = copy.deepcopy(LINE)
    del no001["marc"]["001"]
    assert read_one(no001).remote_id == LINE["id_hash"]


def test_malformed_008_does_not_fake_year_or_language():
    rec = read_one(LINE).record
    assert normalize.year(rec) == (2026, False)        # from 264 _1 $c
    assert normalize.language(rec) == "por"            # from 041
    assert normalize.isbns13(rec) == ["9786588344217"]


def test_raw_iso2709_is_read_first_and_matches_the_dict():
    line = with_raw(LINE)
    line["marc"] = {"LDR": "x"}        # would give an empty record if it were used
    rec = read_one(line).record
    want = marc.from_campos(LINE["marc"])
    assert [(f.tag, f.ind1, f.ind2, f.subfields, f.data) for f in rec.fields] == \
           [(f.tag, f.ind1, f.ind2, f.subfields, f.data) for f in want.fields]


def test_broken_raw_iso2709_falls_back_to_the_dict():
    line = copy.deepcopy(LINE)
    line["raw_iso2709"] = "00100nam  2200049 a 4500" + "2450010000\x1e10\x1faX\x1e"   # 10-character directory
    item = read_one(line)
    assert not item.error
    assert item.record.first("245").get("a").startswith("Organização")


def test_line_without_any_record_is_an_error_naming_its_keys():
    item = read_one({"fonte": "X", "id_hash": "h", "resumo": {}})
    assert item.record is None
    assert "fonte" in item.error and "resumo" in item.error


def test_slug():
    assert slug(LINE["fonte"]) == "fundacentro"
    assert slug("Universidade de São Paulo") == "universidade-de-sao-paulo"
    assert slug("") == "unknown"


def test_source_field_settings_and_overrides():
    src = SourceConfig.from_dict({"id": "zeus", "paths": ["x"], "mode": "pointer", "brazilian": True,
                                  "source_field": "fonte", "source_map": {"Universidade de São Paulo": "usp"},
                                  "overrides": {"fundacentro": {"mode": "full", "weight": 0.8}}})
    st = src.settings(LINE["fonte"])
    assert (st.id, st.name, st.mode, st.brazilian, st.weight) == ("fundacentro", LINE["fonte"], "full", True, 0.8)
    usp = src.settings("Universidade de São Paulo")
    assert (usp.id, usp.mode) == ("usp", "pointer")
    with pytest.raises(ValueError, match="unknown keys"):
        SourceConfig.from_dict({"id": "z", "paths": ["x"], "overrides": {"a": {"mod": "full"}}})
    with pytest.raises(ValueError, match="mode"):
        SourceConfig.from_dict({"id": "z", "paths": ["x"], "overrides": {"a": {"mode": "copy"}}})


def test_build_from_the_zeus_layout(tmp_path):
    lines = []
    for i in range(3):
        a = copy.deepcopy(LINE)
        a["marc"]["001"] = f"F{i}"
        a["marc"]["245"][0]["subcampos"]["$a"] = f"Título número {i} /"
        a["marc"]["020"][0]["subcampos"]["$a"] = ""
        lines.append(with_raw(a) if i % 2 else a)
    other = copy.deepcopy(LINE)
    other["fonte"] = "Biblioteca Restrita"
    other["marc"]["001"] = "R1"
    lines.append(other)
    path = tmp_path / "zeus.jsonl.zst"
    path.write_bytes(zstandard.ZstdCompressor().compress(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in lines).encode()))
    src = SourceConfig.from_dict({"id": "zeus", "paths": [path.name], "mode": "pointer", "brazilian": True,
                                  "source_field": "fonte", "overrides": {"fundacentro": {"mode": "full"}}})
    report = Builder(tmp_path / "s.db", [src], tmp_path).build()
    assert report.error_count == 0, report.errors
    conn = sqlite3.connect(tmp_path / "s.db")
    sources = dict(conn.execute("SELECT id, mode FROM sources"))
    assert sources == {"fundacentro": "full", "biblioteca-restrita": "pointer"}
    counts = dict(conn.execute("SELECT source, count(*) FROM versions GROUP BY source"))
    assert counts == {"fundacentro": 3, "biblioteca-restrita": 1}
    conn.close()
    db = StaticDB(tmp_path / "s.db")
    cands, pointers = db.by_isbn(["9786588344217"])
    assert cands == []                                      # the Fundacentro copies had no ISBN
    assert [(p.source, p.remote_id) for p in pointers] == [("biblioteca-restrita", "R1")]
    cands, _ = db.search(title="Título número 1")
    assert [(c.source, c.remote_id) for c in cands][:1] == [("fundacentro", "F1")]
    assert cands[0].brazilian and cands[0].record.first("082").get("a") == "629.227561362"
    db.close()
