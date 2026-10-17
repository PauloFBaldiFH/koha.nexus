from conftest import bib

from nexus_enrich import M0, M1, W, Candidate, Policy, enrich
from nexus_enrich.marc import Field

ISBN = "9788571644953"
OTHER_ISBN = "9788535902778"
POLICY = Policy(today="20261017")


def base(**kw):
    args = dict(title="Ensaio sobre a cegueira", author="Saramago, José", isbn=ISBN, year=1995,
                publisher="Companhia das Letras")
    args.update(kw)
    return bib(**args)


def f(tag, *subs, ind1=" ", ind2=" "):
    return Field(tag, ind1, ind2, list(subs))


def local_record():
    return base(rid="local-1", extra=[f("942", ("c", "LIVRO")), f("952", ("a", "BIB"), ("p", "000123")),
                                      f("999", ("c", "77"), ("d", "77"))])


def donor(**kw):
    extra = kw.pop("extra", [f("082", ("a", "869.3"), ("2", "23"), ind1="0", ind2="4"),
                             f("520", ("a", "Uma epidemia de cegueira branca."))])
    return base(subjects=kw.pop("subjects", [f("650", ("a", "Cegueira"), ("x", "Ficção"), ("9", "4411"), ind2="4")]),
                extra=extra, **kw)


def tags(rec):
    return [x.tag for x in rec.fields]


def test_m0_adds_missing_fields_with_provenance_and_keeps_local_data():
    local = local_record()
    res = enrich(local, [Candidate(donor(extent="352 p."), "bn", "BN-1", weight=1.0, brazilian=True)], POLICY)
    assert res.status == "enriched"
    out = res.record
    assert {a.group for a in res.additions} == {"subjects", "082", "520"}
    assert res.counts == {M0: 3, M1: 0, W: 0}
    # The local 300 exists, so the donor's is not added; nothing local changed.
    assert [x.get("a") for x in out.get_fields("300")] == ["200 p."]
    for tag in ("008", "020", "100", "245", "260", "942", "952", "999"):
        assert out.get_fields(tag) == local.get_fields(tag)
    # $9 (the donor's own authority id) is dropped; $8 links to an 883.
    subject = out.first("650")
    assert ("9", "4411") not in subject.subfields
    link = subject.get("8")
    assert link.endswith("\\p")
    prov = [p for p in out.get_fields("883") if p.get("8") == link][0]
    assert prov.get("a") == "nexus_enrich M0" and prov.get("q") == "bn" and prov.get("w") == "BN-1"
    assert prov.get("d") == "20261017" and prov.ind1 == "0"
    # One link number per group.
    assert len({x.get("8") for x in out.get_fields("883")}) == 3
    # The input record is not modified.
    assert not local.has("883")


def test_300_only_from_m0():
    no_extent = base(extent=None)
    m1 = donor(year=1996, publisher="Cia. das Letras", extent="352 p.")
    res = enrich(no_extent, [Candidate(m1, "usp", "U1", brazilian=True)], POLICY)
    assert res.additions and all(a.cls == M1 for a in res.additions)
    assert not res.record.has("300")
    res = enrich(no_extent, [Candidate(donor(extent="352 p."), "usp", "U1", brazilian=True)], POLICY)
    assert [x.get("a") for x in res.record.get_fields("300")] == ["352 p."]


def test_work_level_gives_only_subjects_classification_and_notes():
    no_extent = base(extent=None)
    w = donor(isbn=OTHER_ISBN, year=2008, extent="400 p.",
              extra=[f("082", ("a", "869.3"), ind1="0", ind2="4"), f("024", ("a", "X1"), ind1="3")])
    res = enrich(no_extent, [Candidate(w, "usp", "U2", brazilian=True)], POLICY)
    assert {a.group for a in res.additions} == {"subjects", "082"}
    assert all(a.cls == W for a in res.additions)
    assert not res.record.has("300") and not res.record.has("024")


def test_work_level_notes_and_subjects_need_the_same_language():
    eng = donor(isbn=OTHER_ISBN, year=1997 + 2, lang="eng")
    res = enrich(base(), [Candidate(eng, "loc", "L1", weight=1.0)], POLICY)
    assert {a.group for a in res.additions} == {"082"}


def test_portuguese_record_takes_subjects_only_from_portuguese_or_brazilian_donors():
    lcsh = [f("650", ("a", "Blindness"), ("v", "Fiction"), ind2="0")]
    english_m0 = donor(lang="eng", subjects=lcsh)
    res = enrich(base(), [Candidate(english_m0, "loc", "L1", weight=1.0)], POLICY)
    assert "subjects" not in {a.group for a in res.additions}
    # A Brazilian source counts even when its 008 says another language.
    res = enrich(base(), [Candidate(english_m0, "usp", "U1", brazilian=True)], POLICY)
    assert "subjects" in {a.group for a in res.additions}


def test_foreign_thesaurus_in_2_is_never_added_to_a_portuguese_record():
    rameau = [f("650", ("a", "Cécité"), ("2", "rameau"), ind2="7"),
              f("650", ("a", "Cegueira"), ("2", "larpcal"), ind2="7")]
    res = enrich(base(), [Candidate(donor(subjects=rameau), "usp", "U1", brazilian=True)], POLICY)
    assert [x.get("a") for x in res.record.get_fields("650")] == ["Cegueira"]


def test_fill_empty_and_union_with_duplicate_headings():
    local = base(subjects=[f("650", ("a", "Cegueira"), ind2="4")])
    subjects = [f("650", ("a", "Cegueira."), ind2="4"), f("650", ("a", "Epidemias"), ind2="4"),
                f("600", ("a", "Saramago, José"), ind1="1", ind2="4")]
    cand = Candidate(donor(subjects=subjects), "bn", "B1", brazilian=True)
    res = enrich(local, [cand], POLICY)
    assert "subjects" not in {a.group for a in res.additions}       # fill-empty: the record has a 6XX
    res = enrich(local, [cand], Policy(subjects="union", today="20261017"))
    added = [(a.field.tag, a.field.get("a")) for a in res.additions if a.group == "subjects"]
    assert added == [("650", "Epidemias"), ("600", "Saramago, José")]


def test_class_beats_completeness_one_donor_per_group():
    plain_m0 = donor(subjects=[], extra=[f("082", ("a", "869.3"), ind1="0", ind2="4")])
    rich_w = donor(isbn=OTHER_ISBN, year=2010, level=" ",
                   extra=[f("082", ("a", "000"), ind1="0", ind2="4"), f("520", ("a", "Resumo W."))])
    res = enrich(base(), [Candidate(rich_w, "usp", "U9", weight=1.0, brazilian=True),
                          Candidate(plain_m0, "ufrgs", "R1", weight=0.3, brazilian=True)], POLICY)
    by_group = {a.group: (a.source, a.cls) for a in res.additions}
    assert by_group["082"] == ("ufrgs", M0)          # the right manifestation wins
    assert by_group["subjects"] == ("usp", W)        # the M0 has none: the next donor gives them
    assert by_group["520"] == ("usp", W)
    assert [x.get("a") for x in res.record.get_fields("082")] == ["869.3"]


def test_only_review_candidates_change_nothing():
    reuse = donor(title="Manual de redação e estilo")
    res = enrich(base(), [Candidate(reuse, "usp", "U1", brazilian=True)], POLICY)
    assert res.status == "review" and not res.additions and "ISBN reused" in res.review[0]
    assert res.record.fields == base().fields


def test_review_candidate_next_to_a_good_one_is_reported_not_used():
    reuse = donor(title="Manual de redação e estilo")
    res = enrich(base(), [Candidate(reuse, "usp", "U1", brazilian=True),
                          Candidate(donor(), "bn", "B1", brazilian=True)], POLICY)
    assert res.status == "enriched" and {a.source for a in res.additions} == {"bn"}
    assert res.review and "U1" in res.review[0]


def test_other_manifestations_of_one_work_are_not_a_tie():
    a = base(isbn=None, ed="1. ed.")
    b1 = donor(isbn=OTHER_ISBN, year=2001, ed="3. ed.")
    b2 = donor(isbn="9788535914849", year=2002, ed="4. ed.")
    res = enrich(a, [Candidate(b1, "usp", "U1"), Candidate(b2, "bn", "B1")], POLICY)
    assert res.status == "enriched"


def test_two_people_with_one_name_tied_go_to_review():
    def silva(dates, isbn):
        rec = bib("Poemas", "Silva, José", isbn=isbn, year=1990, subjects=["Poesia brasileira"])
        rec.first("100").subfields.append(("d", dates))
        return rec
    local = bib("Poemas", "Silva, José", year=1980)
    res = enrich(local, [Candidate(silva("1900-1970", OTHER_ISBN), "usp", "U1"),
                         Candidate(silva("1950-", "9788535914849"), "bn", "B1")], POLICY)
    assert res.status == "review" and not res.additions and "two candidates" in res.review[0]


def test_stub_gets_a_replacement_proposal_but_only_additions_apply():
    stub = base(level="5", extent=None)
    full = donor(extent="352 p.")
    res = enrich(stub, [Candidate(full, "bn", "B1", brazilian=True)], POLICY)
    assert res.replacement is not None and res.replacement.candidate.remote_id == "B1"
    assert any("stub record" in r for r in res.review)
    assert res.record.first("245").subfields == stub.first("245").subfields
    assert res.record.leader == stub.leader


def test_no_candidates():
    res = enrich(base(), [], POLICY)
    assert res.status == "no-match" and not res.additions


def test_link_numbers_do_not_clash_with_existing_8():
    local = base(extra=[f("880", ("6", "245-01"), ("8", "1\\c"), ("a", "x"))])
    res = enrich(local, [Candidate(donor(), "bn", "B1", brazilian=True)], POLICY)
    links = {x.get("8") for x in res.record.get_fields("883")}
    assert "1\\p" not in links and "2\\p" in links


def test_protected_tags_never_added():
    rich = donor(extra=[f("082", ("a", "869.3"), ind1="0", ind2="4"), f("250", ("a", "2. ed.")),
                        f("100", ("a", "Outro")), f("952", ("a", "X"))])
    res = enrich(base(extent=None), [Candidate(rich, "bn", "B1", brazilian=True)], POLICY)
    added = {a.field.tag for a in res.additions}
    assert not added & {"100", "245", "250", "260", "264", "008", "020", "952"}
