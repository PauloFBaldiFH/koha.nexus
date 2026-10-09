"""CQL, as Koha and other SRU clients send it, read into a small tree.

Koha builds the query from the target's "SRU search fields" mapping, so
what arrives looks like:

    dc.isbn=8535902775
    dc.title="dom casmurro" and dc.creator="machado"
    isbn=978-85-359-0277-8
    (title=memorias or title=memórias) not author=bras
    casmurro                         (a bare term: cql.serverChoice)

Booleans (and, or, not; prox is read as and) bind left to right with equal
precedence, as CQL says; parentheses group. Relation modifiers (=/cql.word)
are read and ignored. Each clause names one of four fields: isbn (ISBN and
ISSN numbers), title, author, or keywords (anything else, and bare terms).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

ISBN_INDEXES = {"isbn", "issn", "identifier", "number", "standardidentifier", "stdid", "isn"}
TITLE_INDEXES = {"title", "titles", "ti", "maintitle"}
AUTHOR_INDEXES = {"author", "creator", "au", "name", "contributor", "personalname", "corporatename"}
ALL_INDEXES = {"allrecords"}
RELATION_WORDS = {"any", "all", "adj", "exact", "within", "encloses"}
SYMBOLS = ("==", "<>", "<=", ">=", "=", "<", ">")
BOOLEANS = {"and", "or", "not", "prox"}

_TOKEN = re.compile(r'\s*(?:(?P<paren>[()])|(?P<quoted>"(?:[^"\\]|\\.)*")|(?P<sym>==|<>|<=|>=|=|<|>)'
                    r'|(?P<slash>/)|(?P<word>[^\s()"=<>/]+))')


class CQLError(ValueError):
    """A query this server cannot read (SRU diagnostic 10)."""


@dataclass(frozen=True)
class Clause:
    field: str          # isbn | title | author | keywords | all
    relation: str       # = == any all adj exact <> ...
    term: str


@dataclass(frozen=True)
class Bool:
    op: str             # and | or | not
    left: "Node"
    right: "Node"


Node = Union[Clause, Bool]


def field_of(index: str | None) -> str:
    if not index:
        return "keywords"
    short = index.rsplit(".", 1)[-1].lower()
    if short in ISBN_INDEXES:
        return "isbn"
    if short in TITLE_INDEXES:
        return "title"
    if short in AUTHOR_INDEXES:
        return "author"
    if short in ALL_INDEXES:
        return "all"
    return "keywords"


def _tokens(query: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    query = query.strip()
    while pos < len(query):
        m = _TOKEN.match(query, pos)
        if not m or m.end() == pos:
            raise CQLError(f"cannot read {query[pos:]!r}")
        pos = m.end()
        kind = m.lastgroup
        value = m.group(kind)
        if kind == "quoted":
            value = re.sub(r"\\(.)", r"\1", value[1:-1])
        out.append((kind, value))
    return out


class _Parser:
    def __init__(self, query: str):
        self.toks = _tokens(query)
        self.i = 0

    def peek(self, offset: int = 0) -> tuple[str, str]:
        j = self.i + offset
        return self.toks[j] if j < len(self.toks) else ("end", "")

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        self.i += 1
        return tok

    def modifiers(self) -> None:
        # /modifier[relation value] after a relation or a boolean: read, ignored.
        while self.peek()[0] == "slash":
            self.take()
            if self.peek()[0] != "word":
                raise CQLError("a modifier name must follow /")
            self.take()
            if self.peek()[0] == "sym" and self.peek(1)[0] in ("word", "quoted"):
                self.take()
                self.take()

    def query(self) -> Node:
        node = self.subquery()
        while self.peek()[0] == "word" and self.peek()[1].lower() in BOOLEANS:
            op = self.take()[1].lower()
            self.modifiers()
            right = self.subquery()
            node = Bool("and" if op == "prox" else op, node, right)
        return node

    def subquery(self) -> Node:
        kind, value = self.peek()
        if kind == "paren" and value == "(":
            self.take()
            node = self.query()
            if self.take() != ("paren", ")"):
                raise CQLError("missing )")
            return node
        if kind not in ("word", "quoted"):
            raise CQLError(f"a search term was expected, not {value or 'the end'!r}")
        nxt_kind, nxt = self.peek(1)
        is_relation = nxt_kind == "sym" or (
            nxt_kind == "word" and nxt.lower() in RELATION_WORDS and self.peek(2)[0] in ("word", "quoted", "slash"))
        if kind == "word" and is_relation:
            index = self.take()[1]
            relation = self.take()[1].lower()
            self.modifiers()
            term_kind, term = self.take()
            if term_kind not in ("word", "quoted"):
                raise CQLError(f"a search term was expected after {index}{relation}")
            return Clause(field_of(index), relation, term.strip())
        self.take()
        return Clause("keywords", "=", value.strip())


def parse(query: str) -> Node:
    if not query or not query.strip():
        raise CQLError("empty query")
    p = _Parser(query)
    node = p.query()
    if p.peek()[0] != "end":
        raise CQLError(f"unexpected {p.peek()[1]!r}")
    return node
