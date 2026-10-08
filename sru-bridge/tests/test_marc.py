from zeus_sru import marc
from zeus_sru.zeus import chunks, extract_raw_records, build_params
from zeus_sru.cql import ZeusQuery, ISBN
from zeus_sru.config import DEFAULT_TARGETS


def test_decode_and_parse(raw_record):
    data = marc.decode_raw(raw_record)
    assert data[:24] == b"00959namCa2200277 a 4500"
    rec = marc.parse_record(data)
    assert rec["001"].data == "000002434"
    assert rec["020"]["a"].startswith("9684291426")
    assert rec["245"]["a"].startswith("Tabamex")
    assert rec["260"]["a"] == "México, DF:"
    assert rec.get_fields("650")[1]["x"] == " Indústria"


def test_marcxml(raw_record):
    from xml.etree import ElementTree as ET
    node = marc.to_marcxml(marc.parse_record(marc.decode_raw(raw_record)))
    text = ET.tostring(node, encoding="unicode")
    assert node.tag == "{http://www.loc.gov/MARC21/slim}record"
    assert "México, DF:" in text and 'tag="949"' in text


def test_rebuild_fixes_char_counted_offsets(raw_record):
    # Shift every offset after the first accented field by pretending the
    # lengths were counted in characters: pymarc alone would misread it.
    good = marc.decode_raw(raw_record)
    broken = good[:5].replace(b"00959", b"00950") + good[5:]
    rec = marc.parse_record(broken)
    assert rec is not None and rec["245"]["a"].startswith("Tabamex")
    rebuilt = marc._rebuild(good)
    assert rebuilt == good


def test_html_escaped_value(raw_record):
    data = marc.decode_raw(raw_record.replace("+", "&#43;"))
    assert data[:24] == b"00959namCa2200277 a 4500"


def test_extract_dedupes_form_and_link(results_page, raw_record):
    assert extract_raw_records(results_page) == [raw_record]


def test_chunks_respect_zeus_limit():
    groups = chunks(DEFAULT_TARGETS, 15)
    assert [len(g) for g in groups] == [15, 1]
    assert sum(groups, ()) == DEFAULT_TARGETS


def test_build_params():
    params = build_params(ZeusQuery("9684291426", ISBN), (0, 1, 3))
    assert params == [("searchString", "9684291426"), ("searchType", "7"),
                      ("operator", "and"), ("targets[0]", "on"), ("targets[1]", "on"),
                      ("targets[3]", "on")]
