"""Kind zeus targets searched live through Catálogo Zeus (nexus_gateway/zeus.py)."""

from __future__ import annotations

import asyncio
import time
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
    # _union never sends Zeus a search per zeus target: no members, no Zeus at all
    assert not any(t.kind == "zeus" for t in served.resolve("_union")[1])
    assert not any(t.kind == "zeus" for t in plain.resolve("_union")[1])
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


def test_union_asks_zeus_once_for_all_its_catalogues(tmp_path):
    static = Static(tmp_path / "missing.db")
    learned = Learned(tmp_path / "learned.db")
    table = load(TARGETS)
    members = [t for t in table.values() if t.kind == "zeus"]
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=FakeGet(), members=members)
    served = Engine(static, learned, table, live.Runner(learned, zeus=hub))
    union = served.resolve("_union")[1]
    assert union[0].id == zeus.UNION_ID and sum(t.kind == "zeus" for t in union) == 1
    served.runner.close()


def test_search_many_ticks_every_catalogue_on_the_form_in_one_request():
    get = FakeGet()
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=get)
    members = [target("bn", "Fundação Biblioteca Nacional (BN)", 0),
               target("ufsc", "Universidade Federal de Santa Catarina (UFSC)", 3),
               target("uff", "Universidade Federal Fluminense (UFF)", 17)]          # not on the form
    total, recs = hub.search_many(members, "title", "quixote", 5)
    assert total == len(recs) >= 1
    searches = [u for u in get.urls if "searchString" in u]
    assert len(searches) == 1
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(searches[0]).query)
    assert sorted(k for k in query if k.startswith("targets[")) == ["targets[0]", "targets[11]"]


def test_search_many_splits_into_chunks_of_15():
    get = FakeGet()
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=get)
    hub._labels = {n: f"Biblioteca Numero {n} (B{n})" for n in range(20)}
    hub._labels_at = time.monotonic()
    members = [target(f"b{n}", f"Biblioteca Numero {n} (B{n})", n) for n in range(20)]
    hub.search_many(members, "title", "x", 5)
    sizes = [sum(k.startswith("targets[") for k in urllib.parse.parse_qs(urllib.parse.urlsplit(u).query))
             for u in get.urls if "searchString" in u]
    assert sizes == [15, 5]


def test_union_answer_through_live_ask():
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=FakeGet(),
                    members=[target("ufsc", "Universidade Federal de Santa Catarina (UFSC)", 11)])
    answer = asyncio.run(live.ask(zeus.union_target(), "title", "x", 5, zeus=hub))
    assert not answer.error and answer.records and answer.target == zeus.UNION_ID


# ----------------------------------------------------------------------
# stable catalogues first, timeout-prone ones alone and last
# ----------------------------------------------------------------------
def ranked(tid, name, n, priority=0, unstable=False, kind="zeus"):
    raw = {"id": tid, "name": name, "group": "national", "kind": kind, "status": "verified",
           "target_index": n, "zeus_priority": priority, "zeus_unstable": unstable}
    if kind == "z3950":
        raw.update(host="z.example", port=210, db="X")
    return make_target(raw)


def search_targets(urls):
    return [sorted((k for k in urllib.parse.parse_qs(urllib.parse.urlsplit(u).query) if k.startswith("targets[")),
                   key=lambda k: int(k[8:-1]))
            for u in urls if "searchString" in u]


BN = ("bn", "Fundação Biblioteca Nacional (BN)", 0)
USP = ("usp", "Universidade de São Paulo (USP)", 4)
RVBI = ("senado", "Rede Virtual de Bibliotecas (RVBI), Senado Federal", 2)
UFSC = ("ufsc", "Universidade Federal de Santa Catarina (UFSC)", 11)


def test_targets_json_puts_usp_and_rvbi_first_and_bn_last():
    table = load(TARGETS)
    assert table["bn"].zeus_unstable and table["bn"].on_zeus
    assert (table["usp"].kind, table["usp"].target_index, table["usp"].zeus_priority) == ("z3950", 4, 1)
    assert (table["senado"].target_index, table["senado"].zeus_priority) == (2, 2)
    members = zeus.order_members(t for t in table.values() if t.on_zeus)
    assert [t.id for t in members[:2]] == ["usp", "senado"]
    assert members[-1].id == "bn"
    # the direct z3950 rows are untouched: still searched live on their own
    assert table["usp"].live and table["usp"].host == "na01.alma.exlibrisgroup.com"


def test_zeus_priority_needs_a_zeus_catalogue():
    import pytest
    from nexus_gateway.targets import TargetError
    with pytest.raises(TargetError):
        make_target({"id": "x", "name": "X", "kind": "z3950", "host": "h.example", "port": 210, "db": "d",
                     "zeus_priority": 1})
    with pytest.raises(TargetError):
        ranked("y", "Y (Y)", 3, priority=-1)


def test_stable_first_and_the_unstable_one_alone_after_them():
    get = FakeGet()
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=get)
    members = [ranked(*BN, unstable=True), ranked(*UFSC), ranked(*RVBI, priority=2),
               ranked(*USP, priority=1, kind="z3950")]
    hub.search_many(members, "isbn", "9788535902778", 30)
    assert search_targets(get.urls) == [["targets[2]", "targets[4]", "targets[11]"], ["targets[0]"]]


def test_a_timed_out_unstable_node_keeps_the_stable_records():
    class SlowBN(FakeGet):
        def __call__(self, url, timeout):
            if "targets%5B0%5D" in url:
                self.urls.append(url)
                raise zeus.ZeusError("Zeus did not answer: TimeoutError")
            return super().__call__(url, timeout)
    get = SlowBN()
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=get)
    total, recs = hub.search_many([ranked(*BN, unstable=True), ranked(*USP, priority=1)], "title", "x", 30)
    assert total == len(recs) >= 1
    assert search_targets(get.urls) == [["targets[4]"], ["targets[0]"]]


def test_the_unstable_request_gets_only_the_time_left():
    waits = []

    class Timed(FakeGet):
        def __call__(self, url, timeout):
            if "searchString" in url:
                waits.append(timeout)
            return super().__call__(url, timeout)
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=Timed())
    hub.search_many([ranked(*BN, unstable=True), ranked(*USP, priority=1)], "title", "x", 30)
    assert waits[0] == 30 and waits[1] <= zeus.UNSTABLE_TIMEOUT


def test_no_time_left_skips_the_unstable_node(monkeypatch):
    get = FakeGet()
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=get)
    hub.labels()
    clock = iter([0.0, 100.0])
    monkeypatch.setattr(zeus.time, "monotonic", lambda: next(clock, 100.0))
    total, recs = hub.search_many([ranked(*BN, unstable=True), ranked(*USP, priority=1)], "title", "x", 30)
    assert recs and search_targets(get.urls) == [["targets[4]"]]


def test_only_an_unstable_node_that_fails_is_an_error():
    import pytest

    class Down(FakeGet):
        def __call__(self, url, timeout):
            if "searchString" in url:
                raise zeus.ZeusError("Zeus did not answer: TimeoutError")
            return super().__call__(url, timeout)
    hub = zeus.Zeus("https://catalogo.example/zeus/", get=Down())
    with pytest.raises(zeus.ZeusError):
        hub.search_many([ranked(*BN, unstable=True)], "title", "x", 30)
