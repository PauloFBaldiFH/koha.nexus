"""Authority databases built from a catalogue's bibliographic records.

Koha's authority search (z3950servers rows with recordtype "authority")
needs MARC21 authority records (leader/06 "z"). A catalogue such as the
Biblioteca Nacional's only gives bibliographic ones, so /sru/<authority id>
searches its catalogue by author and turns the main entry of every record
found (100 personal name, 110 corporate name) into one authority record:

    leader  00000nz  a2200000n  4500
    040     $a BR-RjBN $b por
    100/110 the heading: $a and $d ($b too for a 110), indicators kept
    670     $a Acervo Fundação Biblioteca Nacional (Pergamum)

Nothing else of the bibliographic record is kept (no 245, 260, 300, 020).
The same heading on several records gives one authority record, and only
headings holding every word of the search term are answered. When the
catalogue finds records but none has a 100 or 110, the answer is an SRU
diagnostic, never an empty authority record.
"""

from __future__ import annotations

import re
import unicodedata
from xml.etree import ElementTree as ET

from zeus_sru import sru
from zeus_sru.cql import AUTHOR, ZeusQuery

MARC = "http://www.loc.gov/MARC21/slim"
LEADER = "00000nz  a2200000n  4500"
CATALOGUING_SOURCE = (("a", "BR-RjBN"), ("b", "por"))
SOURCE_NOTE = "Acervo Fundação Biblioteca Nacional (Pergamum)"
# Subfields kept from the bibliographic heading.
KEEP = {"100": ("a", "d"), "110": ("a", "b", "d")}
# Bibliographic records read for one search: one page of the catalogue is
# enough to gather the distinct headings of a name.
SCAN = 50


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", _norm(text))


def _tidy(value: str, last: bool) -> str:
    """Bibliographic punctuation off: the trailing comma before $d, and the
    full stop that ends a heading (an initial such as "J." keeps its own)."""
    value = value.strip().rstrip(",;:/").strip()
    if last and value.endswith(".") and not re.search(r"(?:^|\W)\w\.$", value):
        value = value[:-1].rstrip()
    return value


def headings(record: ET.Element) -> list[tuple[str, str, str, list[tuple[str, str]]]]:
    """(tag, ind1, ind2, subfields) of the record's 100 and 110."""
    out = []
    for df in record.iter(f"{{{MARC}}}datafield"):
        tag = df.get("tag", "")
        if tag not in KEEP:
            continue
        subs = [(sf.get("code", ""), (sf.text or "").strip()) for sf in df.iter(f"{{{MARC}}}subfield")]
        subs = [(c, v) for c, v in subs if c in KEEP[tag] and v]
        if not any(c == "a" for c, _ in subs):
            continue
        subs = [(c, _tidy(v, i == len(subs) - 1)) for i, (c, v) in enumerate(subs)]
        out.append((tag, df.get("ind1", " "), df.get("ind2", " "), [(c, v) for c, v in subs if v]))
    return out


def authority_record(tag: str, ind1: str, subfields: list[tuple[str, str]]) -> ET.Element:
    rec = ET.Element(f"{{{MARC}}}record")
    ET.SubElement(rec, f"{{{MARC}}}leader").text = LEADER

    def field(t: str, i1: str, i2: str, subs) -> None:
        df = ET.SubElement(rec, f"{{{MARC}}}datafield", tag=t, ind1=i1, ind2=i2)
        for code, value in subs:
            ET.SubElement(df, f"{{{MARC}}}subfield", code=code).text = value

    field("040", " ", " ", CATALOGUING_SOURCE)
    # In an authority record the second indicator of a 1XX is undefined.
    field(tag, ind1 or " ", " ", subfields)
    field("670", " ", " ", (("a", SOURCE_NOTE),))
    return rec


def matches(term: str, subfields: list[tuple[str, str]]) -> bool:
    """Every word of the term begins a word of the heading ($a, $b)."""
    have = _words(" ".join(v for c, v in subfields if c in "ab"))
    want = [w for w in _words(term) if len(w) > 1 or w.isdigit()]
    return bool(want) and all(any(h.startswith(w) for h in have) for w in want)


def build(term: str, records: list[ET.Element]) -> list[ET.Element]:
    """The distinct matching headings of records, as authority records, in
    the order the catalogue found them. Raises sru.DiagnosticError when
    records came back but not one of them has a 100 or 110."""
    seen, out, any_heading = set(), [], False
    for record in records:
        for tag, ind1, _ind2, subs in headings(record):
            any_heading = True
            key = (tag, tuple((c, _norm(v)) for c, v in subs))
            if key in seen or not matches(term, subs):
                continue
            seen.add(key)
            out.append(authority_record(tag, ind1, subs))
    if records and not any_heading:
        raise sru.DiagnosticError(sru.Diagnostic(
            sru.GENERAL_ERROR, term,
            f"the catalogue found {len(records)} record(s) for {term!r} but none has a 100 or 110 "
            "heading to make an authority record from"))
    return out


class AuthorityBackend:
    """/sru/<authority id>: the catalogue backend of its "from" id, searched
    by author, answering authority records."""

    record_schema = sru.MARCXML_SCHEMA

    def __init__(self, inner, name: str):
        self.inner, self.name = inner, name

    async def search(self, query: ZeusQuery, start: int, maximum: int) -> tuple[int, list[ET.Element]]:
        # Koha sends the name under whichever index the row maps it to
        # (dc.creator, bath.personalName, a bare term): it is a name here.
        _total, records = await self.inner.search(ZeusQuery(query.term, AUTHOR), 1, SCAN)
        found = build(query.term, records)
        return len(found), found[start - 1:start - 1 + maximum]

    async def aclose(self) -> None:
        pass
