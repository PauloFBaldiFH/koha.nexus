import pytest

from nexus_catalog import cql
from nexus_catalog.cql import Bool, Clause
from nexus_catalog.db import fts_expr, to_sql


@pytest.mark.parametrize("query, expected", [
    ("isbn=8535902775", Clause("isbn", "=", "8535902775")),
    ("dc.isbn = 978-85-359-0277-8", Clause("isbn", "=", "978-85-359-0277-8")),
    ('dc.title="dom casmurro"', Clause("title", "=", "dom casmurro")),
    ("dc.creator=machado", Clause("author", "=", "machado")),
    ("author any \"machado assis\"", Clause("author", "any", "machado assis")),
    ("bath.isbn=/cql.word 123", Clause("isbn", "=", "123")),
    ("casmurro", Clause("keywords", "=", "casmurro")),
    ("cql.serverChoice=casmurro", Clause("keywords", "=", "casmurro")),
    ("cql.allRecords=1", Clause("all", "=", "1")),
])
def test_clauses(query, expected):
    assert cql.parse(query) == expected


def test_booleans_left_to_right_and_parentheses():
    tree = cql.parse('dc.title="dom casmurro" and dc.creator="machado" or isbn=1')
    assert tree == Bool("or", Bool("and", Clause("title", "=", "dom casmurro"),
                                   Clause("author", "=", "machado")), Clause("isbn", "=", "1"))
    tree = cql.parse("(title=memorias or title=memórias) not author=bras")
    assert tree == Bool("not", Bool("or", Clause("title", "=", "memorias"), Clause("title", "=", "memórias")),
                        Clause("author", "=", "bras"))
    assert cql.parse("a prox/unit=word b") == Bool("and", Clause("keywords", "=", "a"), Clause("keywords", "=", "b"))


@pytest.mark.parametrize("query", ["", "  ", "title=", "(title=a", "title=a)", "title=a and"])
def test_unreadable(query):
    with pytest.raises(cql.CQLError):
        cql.parse(query)


def test_fts_text():
    assert fts_expr("title", "Dom Casmurro", "=") == '(title : "Dom" AND title : "Casmurro")'
    assert fts_expr("title", "dom casmurro", "any") == '(title : "dom" OR title : "casmurro")'
    assert fts_expr("title", "dom casmurro", "==") == 'title : "dom casmurro"'
    assert fts_expr("title", "casm*", "=") == '(title : "casm"*)'
    assert fts_expr("title", '" ; --', "=") == ""


def test_sql_takes_values_as_parameters():
    params = []
    where = to_sql(cql.parse("title=\"x' OR 1=1 --\" and isbn=0140449094"), params)
    assert "'" not in where and "OR 1" not in where
    assert params == ['(title : "x" AND title : "OR" AND title : "1" AND title : "1")', "9780140449099", "0140449094"]


def test_too_many_clauses():
    with pytest.raises(cql.CQLError):
        to_sql(cql.parse(" or ".join(f"title=t{i}" for i in range(25))), [])
