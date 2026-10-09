import pytest

from nexus_catalog import marc


def test_isbn_forms():
    assert marc.isbn_forms("8535902775 (broch.)") == ["9788535902778", "8535902775"]
    assert marc.isbn_forms("978-0-14-044909-9") == ["9780140449099", "0140449094"]
    assert marc.isbn_forms("85-359-0277-0") == ["8535902770"]     # wrong check digit: kept as typed
    assert marc.isbn_forms("no number") == []
    assert marc.issn_form("ISSN 0028-0836") == "00280836"


def test_read_keeps_the_work_and_drops_local_fields(collection):
    first, second, third = (marc.read(el) for el in marc.split_records(collection))
    assert first.title == "Dom Casmurro"
    assert first.author == "Machado de Assis, 1839-1908"
    assert first.year == "1899"
    assert first.isbns == ["9788535902778", "8535902775"]
    assert first.key == "isbn:9788535902778"
    xml = first.xml()
    assert 'tag="952"' not in xml and 'tag="999"' not in xml and 'tag="942"' not in xml
    assert 'tag="650"' in xml and "Romance brasileiro" in first.keywords
    assert xml.startswith("<marc:record") or xml.startswith("<record")
    assert second.title == "Memórias póstumas de Brás Cubas"
    assert "Scott-Buccleuch" in second.authors
    assert third.isbns == [] and third.year == "2026"
    assert third.key.startswith("t:") and third.author == "Biblioteca Comunitária Exemplo"


def test_records_without_namespace_or_title():
    el, = marc.split_records('<record><leader>00000nam a2200000 a 4500</leader>'
                             '<datafield tag="245" ind1="0" ind2="0"><subfield code="a">Sem nome</subfield>'
                             '</datafield></record>')
    assert marc.read(el).element.tag == "{http://www.loc.gov/MARC21/slim}record"
    bad, = marc.split_records('<record><leader>00000nam a2200000 a 4500</leader></record>')
    with pytest.raises(marc.RecordError, match="245"):
        marc.read(bad)
    with pytest.raises(marc.RecordError):
        marc.split_records(b"not xml")
