from pathlib import Path

from sru_gateway import targets as tg
from sru_gateway.zeus_labels import compare, main, names_match, parse_target_labels

FORM = Path(__file__).resolve().parent / "fixtures" / "zeus_search_form.html"


def test_labels_of_every_checkbox_shape():
    labels = parse_target_labels(FORM.read_text(encoding="utf-8"))
    assert labels == {0: "Fundação Biblioteca Nacional", 2: "Senado Federal - RVBI",
                      4: "Universidade de São Paulo - USP",
                      11: "UFSC - Universidade Federal de Santa Catarina"}


def test_labels_from_a_select():
    page = '<select name="targets[]" multiple><option value="3">UNICAMP</option><option value="6">UFMG</option></select>'
    assert parse_target_labels(page) == {3: "UNICAMP", 6: "UFMG"}


def test_names_match():
    assert names_match("Universidade de São Paulo (USP)", "Universidade de Sao Paulo - USP")
    assert not names_match("Universidade de São Paulo (USP)", "Universidade Federal de Santa Catarina")
    assert not names_match("Universidade Federal de São Carlos (UFSCar)", "UFSC")
    assert names_match("Rede Virtual de Bibliotecas", "RVBI - Rede Virtual de Bibliotecas do Senado")
    # No acronym on the page: the words of the name are enough.
    assert names_match("Fundação Biblioteca Nacional (BN)", "Fundacao Biblioteca Nacional")
    assert not names_match("Universidade Federal de Santa Catarina (UFSC)", "Universidade Federal de Goiás")


def test_compare_flags_a_wrong_index():
    labels = parse_target_labels(FORM.read_text(encoding="utf-8"))
    table = {t.id: t for t in (
        tg.make_target({"id": "usp", "name": "Universidade de São Paulo (USP)", "kind": "zeus", "target_index": 4}),
        tg.make_target({"id": "ufsc", "name": "Universidade Federal de Santa Catarina (UFSC)", "kind": "zeus",
                        "target_index": 0}),
        tg.make_target({"id": "uff", "name": "Universidade Federal Fluminense (UFF)", "kind": "zeus",
                        "target_index": 17}),
    )}
    rows = {r[0]: r for r in compare(table, labels)}
    assert rows["usp"][4] is True
    assert rows["ufsc"][4] is False and rows["ufsc"][3] == "Fundação Biblioteca Nacional"
    assert rows["uff"][4] is False and rows["uff"][3] == ""


def test_main_exit_code(tmp_path, capsys):
    targets = tmp_path / "targets.json"
    targets.write_text('{"targets": [{"id": "usp", "name": "Universidade de São Paulo (USP)", '
                       '"kind": "zeus", "target_index": 4}]}', encoding="utf-8")
    assert main(["--page", str(FORM), "--targets", str(targets)]) == 0
    assert "targets[ 4] usp" in capsys.readouterr().out
    empty = tmp_path / "empty.html"
    empty.write_text("<html></html>")
    assert main(["--page", str(empty), "--targets", str(targets)]) == 2
