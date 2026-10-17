from conftest import bib

from nexus_enrich import classify
from nexus_enrich.classify import M0, M1, R, W, Keys
from nexus_enrich.marc import Field

ISBN = "9788571644953"
OTHER_ISBN = "9788535902778"


def cls(local, cand):
    return classify.classify(Keys.of(local), Keys.of(cand))


def base(**kw):
    args = dict(title="Ensaio sobre a cegueira", author="Saramago, José", isbn=ISBN, year=1995,
                publisher="Companhia das Letras")
    args.update(kw)
    return bib(**args)


def test_m0_same_isbn_year_and_no_250_on_either_side():
    m = cls(base(), base(author="José Saramago"))
    assert m.cls == M0 and m.isbn_shared and m.year_gap == 0


def test_m0_same_edition_statement():
    assert cls(base(ed="2. ed."), base(ed="2ª ed.")).cls == M0


def test_m1_reprint_one_year_same_edition_and_publisher():
    assert cls(base(ed="2. ed."), base(ed="2. ed., 3. reimpr.", year=1996, publisher="Cia. das Letras")).cls == M1


def test_one_year_gap_with_another_publisher_goes_to_review():
    m = cls(base(), base(year=1996, publisher="Editorial Caminho"))
    assert m.cls == R and "publisher" in m.reasons[0]


def test_shared_isbn_with_another_title_is_isbn_reuse():
    m = cls(base(), base(title="Manual de redação"))
    assert m.cls == R and "ISBN reused" in m.reasons[0]


def test_shared_isbn_with_another_edition_is_a_conflict():
    assert cls(base(ed="2. ed."), base(ed="3. ed.")).cls == R


def test_missing_year_where_m0_needs_one():
    assert cls(base(year=None, publisher="Companhia das Letras"), base()).cls == R


def test_two_year_gap_with_shared_isbn_is_review():
    assert cls(base(), base(year=1997)).cls == R


def test_two_year_gap_same_edition_without_isbn_is_review():
    assert cls(base(isbn=None, ed="2. ed."), base(isbn=OTHER_ISBN, year=1997, ed="2. ed.")).cls == R


def test_work_level_other_year_or_edition():
    assert cls(base(), base(isbn=OTHER_ISBN, year=2008)).cls == W
    assert cls(base(ed="1. ed."), base(isbn=OTHER_ISBN, ed="5. ed.")).cls == W
    assert cls(base(isbn=None), base(isbn=None, year=2010)).cls == W
    # A shared ISBN 10 years apart: the work is the same, the manifestation is not vouched for.
    assert cls(base(), base(year=2005)).cls == W


def test_not_the_same_work_has_no_class():
    assert cls(base(isbn=None), base(isbn=None, title="Memorial do convento")).cls is None
    assert cls(base(isbn=None), base(isbn=None, author="Lispector, Clarice")).cls is None


def test_author_missing_on_one_side_needs_a_shared_isbn():
    assert cls(base(author=None), base()).cls == M0
    assert cls(base(author=None, isbn=None), base(isbn=None)).cls is None


def test_completeness_and_stub():
    plain = base(level="7")
    rich = base(subjects=["Cegueira"], extra=[Field("082", "0", "4", [("a", "869.3")]),
                                              Field("520", " ", " ", [("a", "Romance.")]),
                                              Field("040", " ", " ", [("a", "BR-RjBN")])])
    assert classify.completeness(plain) == 0
    assert classify.completeness(rich) == 3 + 3 + 2 + 1 + 1
    assert classify.is_stub(plain)
    assert classify.is_stub(base(publisher=None, year=None, extent=None))
    assert not classify.is_stub(rich)
