"""Synthetic CLI contracts for the three Magic Import modes."""

import csv
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from conftest import INSTALLER


@pytest.fixture
def cli(tmp_path):
    root = tmp_path / "engine"
    for match in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n',
                             INSTALLER.read_text(encoding="utf-8"), re.S):
        target = root / match[1]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(match[2] + "\n", encoding="utf-8")
    return root


def build(cli, tmp_path, name, text, mode="auto"):
    source = tmp_path / name
    source.write_text(text, encoding="utf-8")
    work = tmp_path / "work"
    result = subprocess.run([
        sys.executable, str(cli / "kei_import_run.py"), "build", "--in", str(source),
        "--work", str(work), "--branch", "CA", "--itype", "BK", "--mode", mode,
    ], cwd=cli, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = [line.split("\t") for line in (work / "out/manifest.tsv").read_text().splitlines()]
    return work, manifest


def test_mrk_native_items_and_descriptive_852_do_not_duplicate(cli, tmp_path):
    text = ("=LDR  00000nam a2200000 a 4500\n=001  SYN-1\n=245  10$aSynthetic migration title\n"
            "=852  \\\\$aObras gerais\n=952  \\\\$aCA$bCA$pSYN-0001$yBK$d2024-01-02\n")
    _, manifest = build(cli, tmp_path, "catalogue (synthetic).mrk", text, "bibliographic")
    bib = [row for row in manifest if row[0] == "biblio"]
    assert len(bib) == 1 and int(bib[0][4]) == 1 and int(bib[0][5]) == 1
    records = ET.parse(bib[0][3]).getroot()
    assert len(records.findall(".//{*}datafield[@tag='952']")) == 1


def test_authority_text_has_its_own_manifest_stream(cli, tmp_path):
    text = ("000  00000nz  a2200000n  4500\n001  SYN-A1\n100 1_ |aSynthetic, Person\n"
            "400 1_ |aPerson, Synthetic\n670 __ |aSynthetic fixture\n\n"
            "000  00000nz  a2200000n  4500\n001  SYN-A2\n180 __ |xSynthetic subdivision\n")
    _, manifest = build(cli, tmp_path, "authorities.txt", text, "authorities")
    auth = [row for row in manifest if row[0] == "authorities"]
    assert len(auth) == 1 and int(auth[0][4]) == 2
    assert not any(row[0] == "biblio" for row in manifest)
    records = ET.parse(auth[0][3]).getroot()
    assert records.find(".//{*}datafield[@tag='180']/{*}subfield[@code='x']").text == "Synthetic subdivision"


def test_named_sql_patrons_preserve_wide_fields_without_importing_passwords(cli, tmp_path):
    sql = ("INSERT INTO borrowers (cardnumber,surname,firstname,address,city,state,zipcode,"
           "country,dateofbirth,dateenrolled,email,branchcode,categorycode,password) VALUES "
           "('SYN-C1','Example','Test','Rua Sintetica, 10','Cidade Exemplo','PR','80000-000',"
           "'BR','1990-01-02','2024-01-02','test@example.invalid','CA','PT','$2y$not-a-real-hash');")
    _, manifest = build(cli, tmp_path, "patrons (synthetic).sql", sql, "patrons")
    patrons = [row for row in manifest if row[0] == "patrons"]
    assert len(patrons) == 1 and int(patrons[0][4]) == 1
    rows = list(csv.DictReader(io.StringIO(Path(patrons[0][3]).read_text())))
    assert rows[0]["country"] == "BR" and rows[0]["dateenrolled"] == "2024-01-02"
    assert rows[0]["branchcode"] == "CA" and rows[0]["zipcode"] == "80000-000"
    assert not rows[0].get("password")


def test_sql_with_embedded_xml_is_not_misread_as_xml_document(cli, tmp_path):
    xml = ('<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader>'
           '<controlfield tag="001">SYN-XML1</controlfield><datafield tag="245" ind1="1" ind2="0">'
           '<subfield code="a">Synthetic embedded title</subfield></datafield></record>')
    sql = "INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',101);" % xml
    _, manifest = build(cli, tmp_path, "metadata.sql", sql, "bibliographic")
    assert sum(int(row[4]) for row in manifest if row[0] == "biblio") == 1


def test_quoted_csv_with_one_record_is_detected_and_preserves_the_author(cli, tmp_path):
    _, manifest = build(cli, tmp_path, "synthetic.csv",
                        'Title,Author,Barcode\nSynthetic title,"Example, Synthetic",SYN-001\n',
                        "bibliographic")
    bib = next(row for row in manifest if row[0] == "biblio")
    assert int(bib[4]) == 1 and int(bib[5]) == 1
    root = ET.parse(bib[3]).getroot()
    assert "Example" in root.find(".//{*}datafield[@tag='100']/{*}subfield[@code='a']").text


def test_bibliographic_table_fixed_values_and_prefix_use_the_shared_mapper(cli, tmp_path):
    source = tmp_path / "synthetic columns.csv"
    source.write_text('Title,Author,Barcode\nSynthetic title,Synthetic author,SYN-001\n')
    work = tmp_path / "work"
    argv = [sys.executable, str(cli / "kei_import_run.py"), "fields", "--draft",
            "--in", str(source), "--work", str(work), "--mode", "bibliographic"]
    result = subprocess.run(argv, cwd=cli, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    fields = json.loads((work / "fields.json").read_text())
    columns = {column['header']: column['id'] for column in fields['columns']}
    profile = tmp_path / "mapping.json"
    profile.write_text(json.dumps({'version': 2, 'mode': 'bibliographic', 'mappings': [
        {'source': columns['Title'], 'to': '245$a', 'value': 'Fixed synthetic title'},
        {'source': columns['Author'], 'to': '100$a'},
        {'source': columns['Barcode'], 'to': '952$p', 'transform': 'prefix', 'prefix': 'MIG-'},
    ]}))
    argv[2:4] = ['build']
    result = subprocess.run(argv + ['--branch', 'CA', '--itype', 'BK', '--fieldmap', str(profile)],
                            cwd=cli, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = [line.split('\t') for line in (work / 'out/manifest.tsv').read_text().splitlines()]
    bib = next(row for row in manifest if row[0] == 'biblio')
    root = ET.parse(bib[3]).getroot()
    title = root.find(".//{*}datafield[@tag='245']/{*}subfield[@code='a']").text
    barcode = root.find(".//{*}datafield[@tag='952']/{*}subfield[@code='p']").text
    assert title.rstrip(' ./') == 'Fixed synthetic title'
    assert barcode == 'MIG-SYN-001'
