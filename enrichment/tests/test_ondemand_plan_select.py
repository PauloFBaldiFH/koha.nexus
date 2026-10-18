"""nexus_ondemand.plan and nexus_ondemand.select: what is asked of a server
for one record, and in what order the servers are asked."""

from __future__ import annotations

from conftest import bib
from nexus_enrich.marc import Field
from nexus_gateway.z3950 import Op, Term
from nexus_ondemand import plan, select
from nexus_ondemand.health import Health, Outcome
from nexus_ondemand.targets import Address, Target

ISBN = "9780306406157"


def uses(q) -> list[int]:
    return [q.use] if isinstance(q, Term) else uses(q.left) + uses(q.right)


def values(q) -> list[str]:
    return [q.value] if isinstance(q, Term) else values(q.left) + values(q.right)


# ----------------------------------------------------------------------
# plan
# ----------------------------------------------------------------------

def test_a_record_with_isbn_and_author():
    steps = plan.for_record(bib("O cortiço :", "Azevedo, Aluísio,", isbn=ISBN, year=1890))
    assert [s.name for s in steps] == ["isbn", "title-author"]
    isbn, ta = steps
    assert values(isbn.query) == ["9780306406157", "0306406152"] and set(uses(isbn.query)) == {7}
    assert set(uses(isbn.fallback)) == {1007} and values(isbn.fallback) == values(isbn.query)
    assert isinstance(ta.query, Op) and ta.query.op == "and"
    assert values(ta.query) == ["O cortiço", "Azevedo"] and uses(ta.query) == [4, 1003]
    assert ta.fallback == Term("O cortiço", 4)


def test_issn_lccn_and_title_year():
    rec = bib("Revista de teste", year=1999, nonfiling=0,
              extra=[Field("022", " ", " ", [("a", "0317-8471")]), Field("010", " ", " ", [("a", " 99012345 ")])])
    steps = plan.for_record(rec)
    assert [s.name for s in steps] == ["issn", "lccn", "title-year"]
    assert uses(steps[0].query) == [8] and uses(steps[0].fallback) == [1007]
    assert steps[1].query == Term("99012345", 9) and steps[1].fallback is None
    assert values(steps[2].query) == ["Revista de teste", "1999"]


def test_the_non_filing_article_and_long_titles():
    rec = bib("The very long title of a book that goes on and on forever /", nonfiling=4)
    (step,) = plan.for_record(rec)
    assert step.name == "title" and step.query.value == "very long title of a book that goes"


def test_a_typed_query_and_qkeys():
    steps = plan.for_query(isbn=ISBN, title="Dom Casmurro", author="Machado de Assis")
    assert [s.name for s in steps] == ["isbn", "title-author"]
    assert values(steps[1].query) == ["Dom Casmurro", "Assis"]
    assert steps[0].qkey == "isbn:(7=9780306406157 or 7=0306406152)"
    assert plan.for_query() == [] and plan.for_query(isbn="no isbn here") == []


def test_at_most_three_isbns():
    rec = bib("X", extra=[Field("020", " ", " ", [("a", i)])
                          for i in ("9780306406157", "9788535902778", "9788571646858", "9780140449136")])
    assert len(values(plan.for_record(rec)[0].query)) == 6


# ----------------------------------------------------------------------
# select
# ----------------------------------------------------------------------

def target(tid, host=None, country="", category="", **kw) -> Target:
    return Target(tid, kw.pop("name", tid.upper()), Address(host or f"{tid}.example.org", 210, "b"),
                  country=country, category=category, **kw)


SERVERS = [
    target("dnb", country="DE", category="europe", name="Deutsche Nationalbibliothek"),
    target("ufsc", country="BR", category="brazil", preselect=True),
    target("unicamp", country="BR", category="brazil"),
    target("bn", country="BR", category="brazil", name="Biblioteca Nacional"),
    target("loc", "lx2.loc.gov", country="US", category="north_america", name="Library of Congress"),
    target("harvard", country="US", category="north_america"),
    target("bnf", country="FR", category="europe", syntax="UNIMARC"),
    target("lcauth", country="US", category="north_america", recordtype="authority"),
]


def ids(ordered) -> list[str]:
    return [t.id for t in ordered]


def test_portuguese_records_ask_brazil_first_national_first():
    ordered, skipped = select.rank(SERVERS, bib("Livro", lang="por"))
    assert ids(ordered) == ["bn", "ufsc", "unicamp", "dnb", "loc", "harvard"]
    assert skipped == [("bnf", "UNIMARC, not merged in v1")]


def test_english_records_ask_the_us_first():
    rec = bib("Book", lang="eng")
    assert ids(select.rank(SERVERS, rec)[0])[:2] == ["loc", "harvard"]
    assert ids(select.rank(SERVERS, None)[0])[:2] == ["loc", "harvard"]       # a typed query: default order


def test_only_a_subset():
    ordered, _ = select.rank(SERVERS, None, only=["brazil", "LOC"])
    assert set(ids(ordered)) == {"bn", "ufsc", "unicamp", "loc"}


def test_health_orders_within_a_tier_and_down_servers_are_skipped(tmp_path):
    health = Health(tmp_path / "h.db", clock=lambda: 1_760_000_000.0)
    try:
        health.record_success("unicamp.example.org:210/b", 100)
        health.record_failure("ufsc.example.org:210/b", Outcome("gone", "dns-missing", "connect", "gone"))
        ordered, skipped = select.rank(SERVERS, bib("Livro"), health=health)
        assert ids(ordered)[:2] == ["bn", "unicamp"]
        assert ("ufsc", "down") in skipped
    finally:
        health.close()


def test_waves_keep_two_sessions_of_a_provider_each():
    alma = [target(f"a{i}", f"a{i}.alma.exlibrisgroup.com", country="GB", category="europe") for i in range(8)]
    others = [target(f"o{i}", country="GB", category="europe") for i in range(4)]
    waves = select.waves(alma + others, wave=6, per_provider=2)
    assert [ids(w) for w in waves] == [["a0", "a1", "o0", "o1", "o2", "o3"], ["a2", "a3"], ["a4", "a5"],
                                       ["a6", "a7"]]
    assert [len(w) for w in select.waves(others + others[:0], wave=3)] == [3, 1]
    assert select.waves([]) == []
