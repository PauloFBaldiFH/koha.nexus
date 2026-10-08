"""The Magic Import engine (installer section 36), written out of the
installer's heredocs and run as the panel runs it, without Koha: ROADMAP
subject 2 (casing, names, 008 / 245 $c, JSON and XML, DOS text, fuzzy
joining of rows without ISBN, the summary of the review gate)."""

import importlib
import json
import re
import subprocess
import sys
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
    yield d, importlib.import_module("kei_import.rules")
    sys.path.remove(str(d))


def build(engine, tmp_path, name, data):
    d, _ = engine
    src = tmp_path / name
    src.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir()
    p = subprocess.run([sys.executable, str(d / "kei_import_run.py"), "build", "--in", str(src), "--work", str(work),
                        "--branch", "CPL", "--itype", "BK", "--today", "2026-10-08"],
                       capture_output=True, text=True, cwd=d)
    preview = (work / "out" / "preview.txt").read_text(encoding="utf-8") if (work / "out" / "preview.txt").exists() else ""
    assert p.returncode == 0, p.stdout + p.stderr + preview
    records = []
    if (work / "out" / "records.xml").exists():
        for r in ET.parse(work / "out" / "records.xml").getroot().iter(SLIM + "record"):
            fields = {}
            for f in r:
                tag = f.get("tag")
                if f.tag == SLIM + "controlfield":
                    fields.setdefault(tag, []).append(f.text)
                elif f.tag == SLIM + "datafield":
                    fields.setdefault(tag, []).append({s.get("code"): s.text for s in f})
            records.append(fields)
    patrons = (work / "out" / "patrons.csv").read_text(encoding="utf-8") if (work / "out" / "patrons.csv").exists() else ""
    return records, preview, p.stdout, patrons


# ---------------------------------------------------------------- rules

@pytest.mark.parametrize("text, mode, expected", [
    ("MEMORIAS POSTUMAS DE BRAS CUBAS", "title", "Memorias Postumas de Bras Cubas"),
    ("A HORA DA ESTRELA", "title", "A Hora da Estrela"),
    ("ABNT NBR 6023: INFORMACAO E DOCUMENTACAO", "title", "ABNT NBR 6023: Informacao e Documentacao"),
    ("UNIVERSIDADE FEDERAL DO PARANA (UFPR)", "title", "Universidade Federal do Parana (UFPR)"),
    ("HISTORIA DO BRASIL - SECULO XIV", "sentence", "Historia do Brasil - Seculo XIV"),
    ("LITERATURA BRASILEIRA; ROMANCE", "sentence", "Literatura brasileira; Romance"),
    ("ESTADOS UNIDOS (EUA) E UNESCO", "title", "Estados Unidos (EUA) e UNESCO"),
    ("SALVADOR, BA", "title", "Salvador, BA"),
    ("JOANA D'ARC", "title", "Joana d'Arc"),
    ("D'AVILA, MARIA", "title", "D'Avila, Maria"),
    ("J. R. R. TOLKIEN", "title", "J. R. R. Tolkien"),
    ("LUDWIG VON MISES", "title", "Ludwig von Mises"),
    ("Dom Casmurro", "title", "Dom Casmurro"),           # not in capitals: as it is
    ("UFPR", "title", "UFPR"),
])
def test_smart_case(engine, text, mode, expected):
    _, R = engine
    assert R.smart_case(text, mode) == expected


@pytest.mark.parametrize("name, entry, first, surname", [
    ("João Pedro Santos", "Santos, João Pedro", "João Pedro", "Santos"),
    ("Carlos Eduardo da Silva Filho", "Silva Filho, Carlos Eduardo da", "Carlos Eduardo da", "Silva Filho"),
    ("Maria de Lourdes dos Santos", "Santos, Maria de Lourdes dos", "Maria de Lourdes dos", "Santos"),
    ("Paulo Fernando Baldi Júnior", "Baldi Júnior, Paulo Fernando", "Paulo Fernando", "Baldi Júnior"),
])
def test_names(engine, name, entry, first, surname):
    _, R = engine
    assert R.invert_name(name) == entry
    assert R.split_patron_name(name) == (first, surname)
    assert R.natural_name(entry) == name
    assert R.split_patron_name(entry) == (first, surname)


def test_natural_name_drops_the_dates(engine):
    _, R = engine
    assert R.natural_name("Assis, Machado de, 1839-1908") == "Machado de Assis"
    assert R.natural_name("Universidade Federal do Paraná") == "Universidade Federal do Paraná"


def test_language_place_and_similarity(engine):
    _, R = engine
    assert R.guess_language("The lord of the rings") == "eng"
    assert R.guess_language("Historia de la literatura y del arte") == "spa"
    assert R.guess_language("Dom Casmurro") == ""
    assert R.place_code("Lisboa") == "po " and R.place_code("Palotina") == "bl " and R.place_code("S.l.") == "xx "
    assert R.similar("dom casmurro", "dom casmuro") > 0.9 > R.similar("casa", "caso")


def test_dos_text_is_read_as_ibm850(engine):
    _, R = engine
    text = "AÇÃO; CONCEIÇÃO; coração; São Paulo"
    assert R.decode_text(text.encode("cp850")) == (text, "IBM850 (MS-DOS)")
    assert R.decode_text(text.encode("cp1252")) == (text, "Windows-1252")
    assert R.decode_text(text.encode("utf-8")) == (text, "UTF-8")


# ---------------------------------------------------------------- build

BOOKS = ("Título;Autor;Editora;Local;Ano;Tombo\n"
         "MEMORIAS POSTUMAS DE BRAS CUBAS;MACHADO DE ASSIS;EDITORA ATICA;SAO PAULO;1997;101\n"
         "Dom Casmurro;Machado de Assis;Ática;São Paulo;1998;102\n"
         "Dom Casmuro;Machado de Assis;Ática;São Paulo;1998;103\n"
         "Matemática 5;Luiz Roberto Dante;Ática;São Paulo;2010;104\n"
         "Matemática 6;Luiz Roberto Dante;Ática;São Paulo;2010;105\n"
         "The lord of the rings;J. R. R. Tolkien;HarperCollins;London;2005;106\n")


def by_title(records):
    return {r["245"][0]["a"].rstrip(" /:"): r for r in records}


def test_spreadsheet_build(engine, tmp_path):
    records, preview, log, _ = build(engine, tmp_path, "livros.csv", BOOKS)
    recs = by_title(records)
    # Typo without ISBN: one record, two copies. Different numbers: two records.
    assert set(recs) == {"Memorias Postumas de Bras Cubas", "Dom Casmurro", "Matemática 5", "Matemática 6",
                         "The lord of the rings"}
    assert [i["p"] for i in recs["Dom Casmurro"]["952"]] == ["102", "103"]
    # Capitals recased; 245 $c from the authors, in direct order.
    m = recs["Memorias Postumas de Bras Cubas"]
    assert m["100"][0]["a"] == "Assis, Machado de"
    assert m["245"][0] == {"a": "Memorias Postumas de Bras Cubas /", "c": "Machado de Assis"}
    assert m["260"][0]["b"].startswith("Editora Atica")
    # 008: 40 positions, s + Date 1, place, language from the title.
    f008 = recs["The lord of the rings"]["008"][0]
    assert len(f008) == 40 and f008[:6] == "261008" and f008[6:11] == "s2005"
    assert f008[15:18] == "enk" and f008[35:38] == "eng" and f008[39] == "d"
    assert recs["Dom Casmurro"]["008"][0][35:38] == "por"
    assert "041" not in recs["The lord of the rings"]          # a guess is not a language note
    assert recs["The lord of the rings"]["245"][0]["c"] == "J. R. R. Tolkien"
    # The review gate: the summary comes first, and the counters reach the panel.
    head = preview.split("\n\n")[1]
    assert head.startswith("== Summary") and "Books: 5 record(s), 6 item(s)" in head
    assert "Casing fixed (text typed in capitals): 4" in head
    assert "Rows without ISBN joined by a similar title (same author, publisher and year): 1" in preview
    assert re.search(r"^Casing fixes: 4$", log, re.M) and re.search(r"^Rows read: 6$", log, re.M)
    assert re.search(r"^Anomalies: 0$", log, re.M)


def test_json_export(engine, tmp_path):
    data = {"acervo": [
        {"titulo": "O CORTIÇO", "autor": {"nome": "ALUÍSIO AZEVEDO"}, "ano": 1890, "tombo": "1"},
        {"titulo": "Iracema", "autor": {"nome": "José de Alencar"}, "ano": 1865, "tombo": "2"},
    ]}
    records, preview, _, _ = build(engine, tmp_path, "export.json", json.dumps(data, ensure_ascii=False))
    recs = by_title(records)
    assert set(recs) == {"O Cortiço", "Iracema"}
    assert recs["O Cortiço"]["100"][0]["a"] == "Azevedo, Aluísio"
    assert recs["O Cortiço"]["245"][0]["c"] == "Aluísio Azevedo"
    assert "export.json: acervo  (JSON" in preview


def test_xml_export(engine, tmp_path):
    xml = ("<?xml version='1.0' encoding='UTF-8'?><biblioteca><livros>"
           "<livro tombo='10'><titulo>Vidas secas</titulo><autor>Graciliano Ramos</autor><ano>1938</ano></livro>"
           "<livro tombo='11'><titulo>Capitães da areia</titulo><autor>Jorge Amado</autor><ano>1937</ano></livro>"
           "<livro tombo='12'><titulo>Sagarana</titulo><autor>Guimarães Rosa</autor><editora>José Olympio</editora>"
           "<ano>1946</ano></livro>"
           "</livros></biblioteca>")
    records, preview, _, _ = build(engine, tmp_path, "export.xml", xml)
    assert set(by_title(records)) == {"Vidas secas", "Capitães da areia", "Sagarana"}
    assert "export.xml: livro  (XML" in preview
    assert sorted(r["952"][0]["p"] for r in records) == ["10", "11", "12"]     # tombo from the attribute


def test_dos_csv_and_patron_names(engine, tmp_path):
    data = ("Nome;CPF;E-mail\n"
            "CARLOS EDUARDO DA CONCEIÇÃO FILHO;529.982.247-25;c@x.br\n"
            "Maria de Lourdes dos Santos;111.444.777-35;m@x.br\n").encode("cp850")
    _, preview, log, patrons = build(engine, tmp_path, "leitores.csv", data)
    rows = [line.split('","') for line in patrons.splitlines()]
    head = [c.strip('"') for c in rows[0]]
    people = {(r[head.index("firstname")].strip('"'), r[head.index("surname")].strip('"')) for r in rows[1:]}
    assert people == {("Carlos Eduardo da", "Conceição Filho"), ("Maria de Lourdes dos", "Santos")}
    assert "encoding IBM850 (MS-DOS)" in preview
    assert "Encoding fixed: 1 file(s) converted to UTF-8 (IBM850: 1)" in preview
    assert re.search(r"^Casing fixes: 1$", log, re.M)
