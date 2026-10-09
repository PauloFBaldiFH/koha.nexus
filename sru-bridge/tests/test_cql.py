import pytest

from zeus_sru import cql


@pytest.mark.parametrize("query,term,kind", [
    ("dc.isbn=9684291426", "9684291426", "isbn"),
    ('bath.isbn = "978-85-359-0277-7"', "9788535902777", "isbn"),
    ("isbn=968-429-142-6", "9684291426", "isbn"),
    ('dc.title="tabamex"', "tabamex", "title"),
    ('dc.title="um caso" and dc.author="jauregui"', "um caso", "title"),
    ('dc.title="x" and dc.isbn=9684291426', "9684291426", "isbn"),
    ("tabamex", "tabamex", "any"),
    ("9684291426", "9684291426", "isbn"),
    ('cql.serverChoice all "dom quixote"', "dom quixote", "any"),
    ('dc.author="machado de assis"', "machado de assis", "author"),
    ('dc.title="dom casmurro" and dc.author="machado"', "dom casmurro", "title"),
])
def test_parse(query, term, kind):
    q = cql.parse(query)
    assert (q.term, q.kind) == (term, kind)


@pytest.mark.parametrize("query", ["", "   ", "and"])
def test_parse_rejects_empty(query):
    with pytest.raises(cql.CQLError):
        cql.parse(query)
