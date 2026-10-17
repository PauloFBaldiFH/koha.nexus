import io

import pytest
from conftest import bib

from nexus_enrich import edition, marc, normalize
from nexus_enrich.marc import Field


# -- marc ------------------------------------------------------------------
def test_xml_roundtrip_keeps_order_and_repeats():
    rec = bib("Dom Casmurro", "Assis, Machado de", isbn="8508046540", year=1899,
              extra=[Field("650", " ", "4", [("a", "Romance"), ("x", "Crítica"), ("x", "História")])])
    again = marc.parse_xml(marc.to_xml(rec))[0]
    assert again == rec


def test_iso2709_roundtrip_utf8_and_stream():
    a = bib("Memórias póstumas de Brás Cubas", "Assis, Machado de", year=1881)
    b = bib("São Bernardo", "Ramos, Graciliano", year=1934)
    data = marc.to_iso2709(a) + b"\n" + marc.to_iso2709(b)
    raws = list(marc.iter_iso2709(io.BytesIO(data)))
    back = [marc.from_iso2709(r) for r in raws]
    assert [r.fields for r in back] == [a.fields, b.fields]
    # Length and base address are filled in; the rest of the leader is kept.
    assert back[0].leader[5:12] == a.leader[5:12] and back[0].leader[17:] == a.leader[17:]
    assert int(back[0].leader[:5]) == len(marc.to_iso2709(a))


def test_iter_xml_streams_collection_with_and_without_namespace():
    xml = ('<collection xmlns="http://www.loc.gov/MARC21/slim">' + marc.to_xml(bib("A", year=2000))
           + "</collection>")
    bare = '<collection><record><leader>00000nam a2200000 a 4500</leader>' \
           '<datafield tag="245" ind1="0" ind2="0"><subfield code="a">B</subfield></datafield></record></collection>'
    assert [r.first("245").get("a") for r in marc.iter_xml(io.BytesIO(xml.encode()))] == ["A"]
    assert [r.first("245").get("a") for r in marc.iter_xml(io.BytesIO(bare.encode()))] == ["B"]


def test_marc_in_json():
    rec = marc.from_json({"leader": "00000nam a2200000 a 4500",
                          "fields": [{"001": "x1"}, {"245": {"ind1": "1", "ind2": "0", "subfields": [{"a": "T"}]}}]})
    assert rec.control("001") == "x1" and rec.first("245").get("a") == "T"
    with pytest.raises(marc.RecordError):
        marc.from_json({"title": "no record"})


def test_add_field_lands_in_tag_order():
    rec = bib("T", subjects=["Existente"], extra=[Field("700", "1", " ", [("a", "Outro")])])
    rec.add_field(Field("650", " ", "4", [("a", "Novo")]))
    tags = [f.tag for f in rec.fields]
    assert tags.index("650") < tags.index("700")
    assert [f.get("a") for f in rec.get_fields("650")] == ["Existente", "Novo"]


# -- normalize -------------------------------------------------------------
def test_isbn_forms_and_cancelled_isbns_are_not_identity():
    assert normalize.isbn_forms("85-359-0277-5 (broch.)") == ["9788535902778", "8535902775"]
    rec = bib("T", isbn="978-85-359-0277-8", extra=[Field("020", " ", " ", [("z", "9780000000002")])])
    assert normalize.isbns13(rec) == ["9788535902778"]


def test_title_drops_nonfiling_and_folds():
    rec = bib("O Alienista :", nonfiling=2)
    assert normalize.title_main(rec) == "alienista"


def test_name_key_matches_inverted_names_and_ignores_dates():
    assert normalize.name_key("Saramago, José, 1922-2010") == normalize.name_key("José Saramago")


@pytest.mark.parametrize("text,expected", [("c1998", (1998, False)), ("[1998?]", (1998, True)),
                                           ("199-", (1990, True))])
def test_year_from_imprint(text, expected):
    rec = bib("T", extra=[Field("260", " ", " ", [("c", text)])])
    rec.fields = [f for f in rec.fields if f.tag != "008"]
    assert normalize.year(rec) == expected


def test_similarity():
    assert normalize.similarity("Ensaio sobre a cegueira", "ENSAIO SOBRE A CEGUEIRA.") == 1.0
    assert normalize.similarity("Silva, José", "José Silva") == 1.0
    assert normalize.similarity("Dom Casmurro", "Grande sertão: veredas") < 0.5
    assert normalize.similarity("", "") == 0.0


def test_publisher_key_ignores_corporate_noise():
    a = bib("T", publisher="Companhia das Letras", year=2000)
    b = bib("T", publisher="Cia. das Letras", year=2000)
    assert normalize.publisher(a) == normalize.publisher(b) == "letras"


# -- edition ---------------------------------------------------------------
@pytest.mark.parametrize("text,number,revised,reprint", [
    ("2. ed.", 2, False, False), ("2ª ed.", 2, False, False), ("2nd ed.", 2, False, False),
    ("Segunda edição", 2, False, False), ("5a. ed.", 5, False, False), ("3rd edition", 3, False, False),
    ("2. Aufl.", 2, False, False), ("Ed. rev. e ampl.", None, True, False),
    ("3. ed. rev. e atual.", 3, True, False), ("2. ed., 3. reimpr.", 2, False, True),
    ("Reimpressão", None, False, True),
])
def test_edition_parse(text, number, revised, reprint):
    e = edition.parse(text)
    assert (e.number, e.revised, e.reprint) == (number, revised, reprint)


def test_edition_compare():
    p = edition.parse
    assert edition.compare(p("2. ed."), p("2ª edição")) == edition.SAME
    assert edition.compare(p("2. ed."), p("3. ed.")) == edition.DIFFERENT
    assert edition.compare(p("2. ed."), p("2. ed. rev.")) == edition.DIFFERENT
    assert edition.compare(p("2. ed."), p("2. ed., 4. reimpr.")) == edition.SAME
    assert edition.compare(None, p("1. ed.")) == edition.UNKNOWN          # no 250 is not "first edition"
    assert edition.compare(p("Ed. rev."), p("2. ed.")) == edition.UNKNOWN
    assert edition.compare(p("Edição de bolso"), p("Edição de bolso")) == edition.SAME
    assert edition.compare(p("Reimpressão"), p("2. ed.")) == edition.UNKNOWN


def test_marc8_iso2709_is_decoded_with_pymarc():
    pytest.importorskip("pymarc")
    rec = bib("Cafxe", year=2000)
    raw = bytearray(marc.to_iso2709(rec))
    raw[9:10] = b" "                                   # MARC-8
    i = raw.index(b"Cafxe")
    raw[i + 3:i + 4] = b"\xe2"                          # MARC-8 combining acute, before its base letter
    back = marc.from_iso2709(bytes(raw))
    assert back.first("245").get("a") == "Café" and not back.marc8_fallback
    assert [f.tag for f in back.fields] == [f.tag for f in rec.fields]
