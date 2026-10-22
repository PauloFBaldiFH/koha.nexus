"""Synthetic regression contracts for Magic Import's new intake/classification.

No uploaded catalogue or patron data is committed here. Readers only parse
input; they must never execute SQL, commands, or the document being inspected.
"""

import importlib
import os
import re
import sqlite3
import subprocess
import sys
import zipfile

import pytest

from conftest import INSTALLER


@pytest.fixture(scope="module")
def engine_v2(tmp_path_factory):
    destination = tmp_path_factory.mktemp("import-v2")
    text = INSTALLER.read_text(encoding="utf-8")
    for match in re.finditer(
        r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n',
        text,
        re.S,
    ):
        output = destination / match.group(1)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(match.group(2) + "\n", encoding="utf-8")
    previous = {
        name: module
        for name, module in sys.modules.items()
        if name == "kei_import" or name.startswith("kei_import.")
    }
    for name in previous:
        del sys.modules[name]
    sys.path.insert(0, str(destination))
    yield lambda name: importlib.import_module("kei_import." + name)
    sys.path.remove(str(destination))
    for name in list(sys.modules):
        if name == "kei_import" or name.startswith("kei_import."):
            del sys.modules[name]
    sys.modules.update(previous)


def fields(record, tag):
    return [field for field in record.fields if field.tag == tag]


def control(record, tag):
    return fields(record, tag)[0].value


def marcxml(identifier="B-17", title="Catálogo de teste"):
    return (
        '<record xmlns="http://www.loc.gov/MARC21/slim">'
        '<leader>00000nam a2200000 a 4500</leader>'
        '<controlfield tag="001">' + identifier + '</controlfield>'
        '<datafield tag="245" ind1="1" ind2="0">'
        '<subfield code="a">' + title + '</subfield></datafield></record>'
    )


def test_mrk_preserves_unicode_indicators_repeated_fields_and_subfields(engine_v2):
    readers = engine_v2("readers")
    text = (
        "=LDR  00000nam a2200000 a 4500\n"
        "=001  B-17\n"
        "=245  10$aCatálogo de teste :$bmemória e ação\n"
        "=650  \\4$aBibliotecas$xAdministração$xHistória\n"
        "=952  \\\\$aMAIN$bMAIN$pTEST-001$d2024-03-12$yBK\n"
        "=952  \\\\$aMAIN$bMAIN$pTEST-002$yBK\n"
    )
    records = readers.read_marc_text(text)
    assert len(records) == 1
    assert control(records[0], "001") == "B-17"
    title = fields(records[0], "245")[0]
    assert (title.ind1, title.ind2) == ("1", "0")
    assert title.get("a") == "Catálogo de teste :"
    subject = fields(records[0], "650")[0]
    assert (subject.ind1, subject.ind2) == (" ", "4")
    assert subject.subfields == [
        ("a", "Bibliotecas"), ("x", "Administração"), ("x", "História")
    ]
    assert [item.get("p") for item in fields(records[0], "952")] == ["TEST-001", "TEST-002"]


def test_mrk_record_boundaries_follow_leaders_without_required_blank_line(engine_v2):
    readers = engine_v2("readers")
    text = (
        "=LDR  00000nam a2200000 a 4500\n=001  B-1\n=245  10$aOne\n"
        "=LDR  00000nam a2200000 a 4500\n=001  B-2\n=245  10$aTwo\n"
    )
    assert [control(rec, "001") for rec in readers.read_marc_text(text)] == ["B-1", "B-2"]


def test_bare_authority_text_retains_heading_and_tracings(engine_v2):
    readers = engine_v2("readers")
    records = readers.read_marc_text(
        "LDR 00000nz  a2200000n  4500\n"
        "001 AUTH-1\n008 260101n| azannaabn          |a aaa      \n"
        "100 1  $aSilva, Autora de Teste$d1900-1980\n"
        "400 1  $aAutora de Teste Silva\n"
        "500 1  $aOutra pessoa\n942   $aPERSO_NAME\n\n"
        "LDR 00000nz  a2200000n  4500\n001 AUTH-2\n"
        "150   $aBibliotecas escolares\n450   $aBibliotecas de escolas\n"
    )
    assert len(records) == 2
    assert records[0].leader[6] == "z"
    assert control(records[0], "008").endswith("aaa      ")
    assert fields(records[0], "100")[0].get("a") == "Silva, Autora de Teste"
    assert fields(records[0], "400")[0].get("a") == "Autora de Teste Silva"
    assert fields(records[0], "942")[0].get("a") == "PERSO_NAME"
    assert fields(records[1], "150")[0].get("a") == "Bibliotecas escolares"
    assert not fields(records[0], "245")


def test_sql_parser_handles_escaped_quotes_null_and_multiline_values(engine_v2):
    readers = engine_v2("readers")
    tables = readers.read_sql(
        "INSERT INTO `source_books` (`notes`,`external_id`,`title`,`other`) VALUES\n"
        "('Line one\nLine two; (not a tuple)', '000017', 'D''Ávila, ação', NULL),\n"
        "('A \\'quoted\\' word', '000018', 'NULL', '');\n"
    )
    assert len(tables) == 1
    table = tables[0]
    assert table.name == "source_books"
    assert table.headers == ["notes", "external_id", "title", "other"]
    first, second = [dict(zip(table.headers, row)) for row in table.rows]
    assert first == {
        "notes": "Line one\nLine two; (not a tuple)",
        "external_id": "000017", "title": "D'Ávila, ação", "other": None,
    }
    assert second["notes"] == "A 'quoted' word"
    assert second["title"] == "NULL" and second["other"] == ""


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1), (1, 2, 0)])
def test_named_sql_column_order_does_not_change_meaning(engine_v2, order):
    readers = engine_v2("readers")
    columns = ["title", "barcode", "branchcode"]
    values = ["Synthetic title", "COPY-017", "CA"]
    text = "INSERT INTO books (%s) VALUES (%s);" % (
        ",".join(columns[i] for i in order),
        ",".join("'%s'" % values[i] for i in order),
    )
    table = readers.read_sql(text)[0]
    assert dict(zip(table.headers, table.rows[0])) == dict(zip(columns, values))


def test_sql_schema_names_are_used_only_when_present(engine_v2):
    readers = engine_v2("readers")
    tables = readers.read_sql(
        "CREATE TABLE `books` (\n"
        " `external_id` int NOT NULL,\n `title` varchar(255),\n"
        " PRIMARY KEY (`external_id`)\n);\n"
        "INSERT INTO `books` VALUES (17,'A book');"
    )
    assert tables[0].headers == ["external_id", "title"]
    assert tables[0].rows == [["17", "A book"]]


def test_headless_sql_retains_all_columns_without_inventing_schema(engine_v2):
    readers = engine_v2("readers")
    table = readers.read_sql(
        "INSERT INTO borrowers VALUES "
        "('reader@example.invalid',NULL,'00071','2001-01-01'),"
        "('other@example.invalid','a note','00072','2002-02-02');"
    )[0]
    assert table.name == "borrowers"
    assert table.headers is None
    assert table.rows[0] == ["reader@example.invalid", None, "00071", "2001-01-01"]
    assert len(table.rows) == 2


def test_anonymous_sql_fragment_splits_schema_runs_without_guessing_columns(engine_v2):
    readers = engine_v2("readers")
    tables = readers.read_sql(
        "(17,'A title'),\n(18,'Another title');\n"
        "(17,'marcxml','<record></record>'),\n"
        "(18,'marcxml','<record></record>');\n"
        "INSERT INTO items VALUES ('COPY-17',17),('COPY-18',18);"
    )
    assert len(tables) == 3
    assert tables[0].name.startswith("anonymous") and tables[0].headers is None
    assert tables[1].name.startswith("anonymous") and tables[1].headers is None
    assert [len(table.rows) for table in tables] == [2, 2, 2]
    assert [len(table.rows[0]) for table in tables] == [2, 3, 2]
    assert tables[2].name == "items"


def test_sql_is_parsed_as_data_without_executing_statements(engine_v2, monkeypatch):
    readers = engine_v2("readers")
    def forbidden(*args, **kwargs):
        raise AssertionError("Reader attempted execution")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    tables = readers.read_sql(
        "DROP TABLE borrowers;\n"
        "SET @example='must not execute';\n"
        "INSERT INTO source (note) VALUES ('DROP TABLE source; $(touch /tmp/not-executed)');"
    )
    populated = [table for table in tables if table.rows]
    assert len(populated) == 1
    assert populated[0].rows == [["DROP TABLE source; $(touch /tmp/not-executed)"]]


def test_sql_embedded_marcxml_is_not_mistaken_for_whole_file_xml(engine_v2):
    readers = engine_v2("readers")
    xml = marcxml().replace("'", "''")
    table = readers.read_sql(
        "INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',17);" % xml
    )[0]
    assert table.headers == ["metadata", "biblionumber"]
    assert table.rows == [[marcxml(), "17"]]


def test_report_extracts_xml_and_labeled_holdings_without_losing_unicode(engine_v2):
    readers = engine_v2("readers")
    escaped = marcxml().replace("\n", "\\n")
    text = (
        "17   Catálogo de teste   Autora Sintética   " + escaped +
        " [barcode:COPY-17 | homebranch:MAIN | holdingbranch:MAIN | itype:BK | "
        "callnumber:025 S617 | location:GEN | ccode: | dateaccessioned:2024-03-12]\n"
    )
    record = readers.read_report(text)[0]
    assert fields(record, "245")[0].get("a") == "Catálogo de teste"
    item = fields(record, "952")[0]
    assert {code: item.get(code) for code in ("p", "a", "b", "y", "o", "c", "d")} == {
        "p": "COPY-17", "a": "MAIN", "b": "MAIN", "y": "BK",
        "o": "025 S617", "c": "GEN", "d": "2024-03-12",
    }


def test_report_repeated_item_summaries_remain_separate_copies(engine_v2):
    readers = engine_v2("readers")
    record = readers.read_report(
        "17 " + marcxml() +
        " [barcode:COPY-17 | homebranch:CA | itype:BK]"
        " [barcode:COPY-18 | homebranch:CA | itype:BK]\n"
    )[0]
    assert [field.get("p") for field in fields(record, "952")] == ["COPY-17", "COPY-18"]


def test_headless_xlsx_keeps_first_row_and_text_identifiers(engine_v2, tmp_path):
    tables = engine_v2("tables")
    path = tmp_path / "headless.xlsx"
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        '</Relationships>'
    )
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="1"><c r="A1" t="inlineStr"><is><t>00017</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Catálogo de teste</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>00018</t></is></c>'
        '<c r="B2" t="inlineStr"><is><t>Outro título</t></is></c></row>'
        '</sheetData></worksheet>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    table = tables.read_xlsx(str(path), path.name)[0]
    classify = engine_v2("classify")
    tables.set_header(table, lambda value: bool(classify.header_match(value)))
    assert not table.header_row
    assert table.data() == [["00017", "Catálogo de teste"], ["00018", "Outro título"]]


def test_headless_heuristics_recognize_content_without_header_penalty(engine_v2):
    heuristics = engine_v2("heuristics")
    rows = [
        ["reader-a@example.invalid", "80010-100", "Rua das Letras, 17", "PR"],
        ["reader-b@example.invalid", "80020-200", "Avenida dos Livros, 28", "SC"],
        ["reader-c@example.invalid", "80030-300", "Travessa da Leitura, 39", "RS"],
    ]
    inferred = heuristics.infer_columns(rows, mode="patrons")
    for column, expected in zip(inferred, ("email", "zipcode", "address", "state")):
        candidate = next(item for item in column.candidates if item.role == expected)
        assert candidate.score > 0.6
        assert candidate.reasons


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1), (1, 2, 0)])
def test_content_classification_is_invariant_under_column_permutation(engine_v2, order):
    heuristics = engine_v2("heuristics")
    columns = [
        ["a@example.invalid", "b@example.invalid", "c@example.invalid"],
        ["80010-100", "80020-200", "80030-300"],
        ["PR", "SC", "RS"],
    ]
    rows = [list(row) for row in zip(*(columns[index] for index in order))]
    inferred = heuristics.infer_columns(rows, mode="patrons")
    for column, original in zip(inferred, order):
        assert column.role == ("email", "zipcode", "state")[original]


def test_headless_date_semantics_require_review_instead_of_positional_guess(engine_v2):
    heuristics = engine_v2("heuristics")
    inferred = heuristics.infer_columns(
        [["2001-01-02", "2001-01-02"], ["2002-02-03", "2002-02-03"], ["2003-03-04", "2003-03-04"]],
        mode="patrons",
    )
    for column in inferred:
        assert column.role is None
        roles = {candidate.role for candidate in column.candidates}
        assert {"dateofbirth", "dateenrolled", "dateexpiry"} <= roles


def test_empty_columns_remain_visible_without_semantic_invention(engine_v2):
    heuristics = engine_v2("heuristics")
    inferred = heuristics.infer_columns([[None, ""], [None, ""]], mode="patrons")
    assert len(inferred) == 2
    assert all(column.role is None for column in inferred)
