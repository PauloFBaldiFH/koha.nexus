"""What to ask a server for one record (plan section 4.1): a short list of
searches, tried in order until one finds records.

    isbn          every ISBN of 020 $a (13 and 10 forms, at most 3 ISBNs), OR'ed
    issn          022 $a
    lccn          010 $a
    title-author  245 $a AND the main author's surname
    title-year    245 $a AND the year (when there is no author)

Each step has a fallback form for a server that refuses the first one
(Bib-1 diagnostic "unsupported attribute"...): ISBN and ISSN as
identifier-standard (use 1007), title AND author as title alone.
A typed query (ISBN, or title and author) gives the same steps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nexus_enrich import normalize
from nexus_enrich.marc import Record
from nexus_gateway.z3950 import Op, Term, and_

USE_TITLE, USE_AUTHOR, USE_DATE = 4, 1003, 31
USE_ISBN, USE_ISSN, USE_LCCN, USE_IDENTIFIER = 7, 8, 9, 1007
MAX_ISBNS = 3
TITLE_WORDS = 8
BROAD_STEPS = ("title-author", "title-year", "title")     # too many hits: not worth fetching


@dataclass(frozen=True)
class Step:
    name: str
    query: Term | Op
    fallback: Term | Op | None = None

    @property
    def qkey(self) -> str:
        """A stable key for the answer cache and for joining identical searches."""
        return f"{self.name}:{render(self.query)}"


def render(query: Term | Op) -> str:
    if isinstance(query, Term):
        return f"{query.use}={query.value}"
    return f"({render(query.left)} {query.op} {render(query.right)})"


def _or(terms: list[Term]) -> Term | Op:
    out: Term | Op = terms[0]
    for t in terms[1:]:
        out = Op("or", out, t)
    return out


def _title(rec: Record) -> str:
    """245 $a as catalogued (diacritics kept), without the non-filing
    article and the ISBD punctuation, at most TITLE_WORDS words."""
    f = rec.first("245")
    if f is None:
        return ""
    text = f.get("a") or ""
    skip = int(f.ind2) if f.ind2.isdigit() else 0
    text = text[skip:]
    text = re.sub(r"[\s/:;,.=\[\]]+$", "", text.strip())
    text = re.sub(r"[\"“”]", "", text)
    return " ".join(text.split()[:TITLE_WORDS])


def _surname(name: str) -> str:
    name = name.strip().strip(",.")
    if "," in name:
        return name.split(",", 1)[0].strip()
    words = name.split()
    return words[-1] if words else ""


def isbn_step(isbns: list[str]) -> Step | None:
    forms: list[str] = []
    for isbn in isbns[:MAX_ISBNS]:
        for form in normalize.isbn_forms(isbn):
            if form not in forms:
                forms.append(form)
    if not forms:
        return None
    return Step("isbn", _or([Term(f, USE_ISBN) for f in forms]),
                _or([Term(f, USE_IDENTIFIER) for f in forms]))


def title_steps(title: str, author: str, year: int | None) -> list[Step]:
    if not title:
        return []
    surname = _surname(author)
    if surname:
        return [Step("title-author", and_(Term(title, USE_TITLE), Term(surname, USE_AUTHOR)),
                     Term(title, USE_TITLE))]
    if year:
        return [Step("title-year", and_(Term(title, USE_TITLE), Term(str(year), USE_DATE)),
                     Term(title, USE_TITLE))]
    return [Step("title", Term(title, USE_TITLE))]


def for_record(rec: Record) -> list[Step]:
    steps: list[Step] = []
    s = isbn_step(normalize.isbns13(rec) or [v for f in rec.get_fields("020") for v in f.get_all("a")])
    if s:
        steps.append(s)
    issns = normalize.issns(rec)
    if issns:
        steps.append(Step("issn", _or([Term(i, USE_ISSN) for i in issns[:2]]),
                          _or([Term(i, USE_IDENTIFIER) for i in issns[:2]])))
    f010 = rec.first("010")
    lccn = re.sub(r"\s+", "", f010.get("a")) if f010 is not None and f010.get("a") else ""
    if lccn:
        steps.append(Step("lccn", Term(lccn, USE_LCCN)))
    year, _ = normalize.year(rec)
    steps += title_steps(_title(rec), normalize.main_author(rec), year)
    return steps


def for_query(isbn: str = "", title: str = "", author: str = "", year: int | None = None) -> list[Step]:
    """Steps for a typed query (no local record)."""
    steps: list[Step] = []
    s = isbn_step([isbn]) if isbn else None
    if s:
        steps.append(s)
    title = " ".join(title.split()[:TITLE_WORDS])
    steps += title_steps(title, author, year)
    return steps
