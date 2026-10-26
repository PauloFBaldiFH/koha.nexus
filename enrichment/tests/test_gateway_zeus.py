"""Kind zeus targets searched live through Catálogo Zeus (nexus_gateway/zeus.py)."""

from __future__ import annotations

import asyncio
import urllib.parse
from pathlib import Path

from nexus_gateway import live, zeus
from nexus_gateway.engine import Engine, Static
from nexus_gateway.learned import Learned
from nexus_gateway.targets import load, make_target

FIX = Path(__file__).parent / "fixtures"
TARGETS = Path(__file__).resolve().parents[1] / "nexus_gateway" / "targets.json"
FORM = (FIX / "zeus_search_form.html").read_text(encoding="utf-8")
RESULTS = (FIX / "zeus_marcxml.html").read_text(encoding="utf-8")


def target(tid, name, n):
    return make_target({"id": tid, "name": name, "group": "national", "kind": "zeus", "status": "verified",
                        "target_index": n})


class FakeGet:
    def __init__(self, form=FORM, results=RESULTS):
        self.form, self.results, self.urls = form, results, []

    def __call__(self, url, timeout):
        self.urls.append(url)
        if "searchString" in url:
            return self.results
        if self.form is None:
            raise zeus.ZeusError("down")
        return self.form


def test_labels_are_read_from_the_search_form():
    labels = zeus.parse_labels(FORM)
    assert labels[0] == "Fundação Biblioteca Nacional"
    assert labels[2] == "Senado Federal - RVBI"
    assert "USP" in labels[4] and "UFSC" in labels[11]


def test_index_comes_from_the_label_not_a_wrong_target_index():
    labels = zeus.parse_labels(FORM)
    assert zeus.index_for(target("bn", "Fundação Biblioteca Nacional (BN)", 0), labels) == 0
    # a target_index that names another library is corrected from the labels
    assert zeus.index_for(target("ufsc", "Universidade Federal de Santa Catarina (UFSC)", 0), labels) == 11
    assert zeus.index_for(target("uff", "Universidade Federal Fluminense (UFF)", 17), labels) is None


def test_result_page_records():
    recs = zeus.parse_results(RESULTS)
    assert recs and recs[0].control("001") == "000002434"
    assert any(f.tag == "245" for f in recs[0].fields)


def test_search_asks_only_the_matching_target():
    get = FakeGet()
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=get)
    total, recs = hub.search(target("ufsc", "Universidade Federal de Santa Catarina (UFSC)", 3), "isbn",
                             "9684291426", 5)
    assert total == len(recs) >= 1
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(get.urls[-1]).query)
    assert query["targets[11]"] == ["on"] and query["searchType"] == ["7"]
    assert not any(k.startswith("targets[") and k != "targets[11]" for k in query)
    # the form is read once, not before every search
    hub.search(target("bn", "Fundação Biblioteca Nacional (BN)", 0), "title", "x", 5)
    assert sum("searchString" not in u for u in get.urls) == 1


def test_target_not_on_the_form_is_an_error_not_a_guess():
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=FakeGet())
    answer = asyncio.run(live.ask(target("uff", "Universidade Federal Fluminense (UFF)", 17), "title", "x", 5,
                                  zeus=hub))
    assert answer.records == [] and "not among the targets" in answer.error


def test_unreadable_form_is_an_error():
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=FakeGet(form=None))
    answer = asyncio.run(live.ask(target("bn", "Fundação Biblioteca Nacional (BN)", 0), "title", "x", 5,
                                  zeus=hub))
    assert answer.records == [] and "could not be read" in answer.error


def test_without_a_zeus_address_zeus_targets_stay_static(tmp_path):
    static = Static(tmp_path / "missing.db")
    learned = Learned(tmp_path / "learned.db")
    table = load(TARGETS)
    plain = Engine(static, learned, table, live.Runner(learned))
    assert plain.resolve("bn")[1] == []
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=FakeGet())
    served = Engine(static, learned, table, live.Runner(learned, zeus=hub))
    assert [t.id for t in served.resolve("bn")[1]] == ["bn"]
    # _union never sends Zeus a search per zeus target
    assert not any(t.kind == "zeus" for t in served.resolve("_union")[1])
    plain.runner.close()
    served.runner.close()


def test_direct_list_addresses_replace_missing_and_zeus_where_marc21():
    table = load(TARGETS)
    assert (table["ufsc"].kind, table["ufsc"].host, table["ufsc"].db) == ("z3950", "z3950.ufsc.br", "Default")
    assert (table["usp"].kind, table["usp"].port, table["usp"].db) == ("z3950", 1921, "55USP_INST")
    assert (table["bne"].kind, table["bne"].db) == ("z3950", "34BNE_INST")
    assert table["bn"].kind == "zeus" and table["bn"].target_index == 0
    # UNIMARC catalogues are not served (MARC21 only), so they stay without an address
    assert table["bn-portugal"].kind == table["porbase"].kind == "missing"
