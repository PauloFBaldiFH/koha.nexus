"""Just enough CQL to turn Koha's SRU queries into one Zeus search.

Koha builds CQL from the target's "SRU search fields" mapping, so what
arrives looks like:

    dc.isbn=9684291426
    dc.title="tabamex" and dc.author="jauregui"
    bath.isbn = "978-85-..."
    tabamex                      (a bare term: cql.serverChoice)

Zeus takes a single searchString plus a searchType (7 = ISBN, 4 = Title,
1003 = Author, 1016 = any field), so an ISBN clause wins when there is one,
then a title, then an author clause; anything else is searched in any field. A bare term that
looks like an ISBN is searched as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ISBN = 7
TITLE = 4
AUTHOR = 1003
ANY = 1016

ISBN_INDEXES = {"isbn", "identifier", "issn", "number", "standardidentifier"}
TITLE_INDEXES = {"title", "titles", "ti"}
AUTHOR_INDEXES = {"author", "creator", "au", "name"}
ANY_INDEXES = {"anywhere", "serverchoice", "keyword", "any", "all", "text"}

_RELATIONS = r"==|<>|<=|>=|=|<|>|\b(?:exact|any|all|adj|within|encloses)\b"
_CLAUSE = re.compile(
    r"""(?:(?P<index>[A-Za-z][\w.\-]*)\s*(?P<rel>%s)(?:/[\w.\-]+)*\s*)?
        (?P<term>"(?:[^"\\]|\\.)*"|[^\s()"]+)""" % _RELATIONS,
    re.X | re.I,
)
_BOOLEANS = {"and", "or", "not", "prox"}


class CQLError(ValueError):
    """Raised for a query this bridge cannot read (SRU diagnostic 10)."""


@dataclass(frozen=True)
class ZeusQuery:
    term: str
    search_type: int

    @property
    def kind(self) -> str:
        return {ISBN: "isbn", TITLE: "title", AUTHOR: "author"}.get(self.search_type, "any")


def looks_like_isbn(term: str) -> bool:
    digits = re.sub(r"[\s\-]", "", term)
    return bool(re.fullmatch(r"\d{9}[\dXx]|97[89]\d{10}", digits))


def clean_isbn(term: str) -> str:
    m = re.search(r"97[89][\d\-\s]{10,17}|\d[\d\-\s]{8,12}[\dXx]", term)
    raw = m.group(0) if m else term
    return re.sub(r"[\s\-]", "", raw).upper()


def _unquote(term: str) -> str:
    if len(term) >= 2 and term[0] == term[-1] == '"':
        term = re.sub(r"\\(.)", r"\1", term[1:-1])
    return term.strip()


def _short_index(index: str | None) -> str:
    if not index:
        return "serverchoice"
    return index.rsplit(".", 1)[-1].lower()


def parse(query: str) -> ZeusQuery:
    if not query or not query.strip():
        raise CQLError("empty query")

    isbn: list[str] = []
    title: list[str] = []
    author: list[str] = []
    other: list[str] = []
    for m in _CLAUSE.finditer(query):
        index, term = m.group("index"), _unquote(m.group("term"))
        if not index and term.lower() in _BOOLEANS:
            continue
        if not term or term == "*":
            continue
        short = _short_index(index)
        if short in ISBN_INDEXES:
            isbn.append(term)
        elif short in TITLE_INDEXES:
            title.append(term)
        elif short in AUTHOR_INDEXES:
            author.append(term)
        else:
            other.append(term)

    if isbn:
        return ZeusQuery(clean_isbn(isbn[0]), ISBN)
    if title:
        return ZeusQuery(" ".join(title), TITLE)
    if author:
        return ZeusQuery(" ".join(author), AUTHOR)
    if not other:
        raise CQLError(f"no search term in {query!r}")
    joined = " ".join(other)
    if len(other) == 1 and looks_like_isbn(joined):
        return ZeusQuery(clean_isbn(joined), ISBN)
    return ZeusQuery(joined, ANY)
