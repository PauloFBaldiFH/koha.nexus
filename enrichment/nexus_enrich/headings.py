"""Authority headings: what a bibliographic or authority record names, as
(kind, heading, key, dates, thesaurus) ready to match or store.

Relator terms ($e, $4), links ($0, $9, $8), sources ($2, $5) and, for
subjects, subdivisions ($v $x $y $z) are not part of the heading. Dates
($d) are kept apart from the key, so "Saramago, José, 1922-2010" and
"Saramago, José" share the key and differ only in dates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .marc import Field, Record
from .normalize import fold

# tag (last two digits) -> (kind, subfields of the heading)
_BIB_KINDS = {
    "00": ("personal", "abcdq"),
    "10": ("corporate", "abcdn"),
    "11": ("meeting", "acdenq"),
    "30": ("uniform", "adfklmnoprs"),
    "50": ("topical", "ab"),
    "51": ("geographic", "a"),
    "55": ("genre", "a"),
}
BIB_TAGS = ("100", "110", "111", "130", "600", "610", "611", "630", "650", "651", "655",
            "700", "710", "711", "730")
AUTH_TAGS = {"100": "personal", "110": "corporate", "111": "meeting", "130": "uniform",
             "150": "topical", "151": "geographic", "155": "genre"}
_THESAURI = {"0": "lcsh", "1": "lcshac", "2": "mesh", "3": "nal", "5": "cash", "6": "rvm"}


@dataclass(frozen=True)
class Heading:
    kind: str
    heading: str
    key: str
    dates: str
    thesaurus: str


def _trim(value: str) -> str:
    value = value.strip().rstrip(",;:/").strip()
    if value.endswith(".") and not re.search(r"(?:^|\W)\w\.$", value):
        value = value[:-1].rstrip()
    return value


def from_field(f: Field, codes: str, kind: str) -> Heading | None:
    parts = [(c, _trim(v)) for c, v in f.subfields if c in codes and v.strip()]
    if not any(c == "a" for c, _ in parts):
        return None
    dates = " ".join(v for c, v in parts if c == "d") if kind == "personal" else ""
    text = " ".join(v for _, v in parts)
    key = fold(" ".join(v for c, v in parts if not (c == "d" and kind == "personal")))
    thesaurus = ""
    if f.tag.startswith("6"):
        thesaurus = f.get("2").strip().lower() if f.ind2 == "7" else _THESAURI.get(f.ind2, "")
    return Heading(kind, text, key, dates, thesaurus)


def of_bib(rec: Record) -> list[Heading]:
    out = []
    for f in rec.get_fields(*BIB_TAGS):
        kind, codes = _BIB_KINDS[f.tag[1:]]
        h = from_field(f, codes, kind)
        if h is not None and h not in out:
            out.append(h)
    return out


@dataclass(frozen=True)
class AuthorityEntry:
    heading: Heading
    variants: tuple[str, ...]
    lccn: str
    uri: str
    source_id: str


def of_authority(rec: Record) -> AuthorityEntry | None:
    """The established heading of an authority record (leader/06 z), its
    4XX variants, LCCN (010 $a) and an identifier URI (024 $a with $2 uri,
    else the first http $0 or 1XX $1)."""
    main = next((f for f in rec.fields if f.tag in AUTH_TAGS), None)
    if main is None:
        return None
    kind = AUTH_TAGS[main.tag]
    codes = {"personal": "abcdq", "corporate": "abcdn", "meeting": "acdenq", "uniform": "adfklmnoprs"}.get(kind, "a")
    h = from_field(main, codes, kind)
    if h is None:
        return None
    if kind in ("topical", "geographic", "genre"):
        system = {"a": "lcsh", "b": "lcshac", "c": "mesh", "d": "nal", "k": "cash"}.get(rec.control("008")[11:12], "")
        f040 = rec.first("040")
        h = replace(h, thesaurus=system or (f040.get("f").strip().lower() if f040 is not None else ""))
    variants = []
    for f in rec.fields:
        if f.tag.startswith("4") and f.tag[1:] == main.tag[1:]:
            v = from_field(f, codes, kind)
            if v is not None and v.heading not in variants:
                variants.append(v.heading)
    f010 = rec.first("010")
    lccn = re.sub(r"\s+", "", f010.get("a")) if f010 is not None else ""
    uri = ""
    for f in rec.get_fields("024"):
        if f.get("2").lower() == "uri" and f.get("a"):
            uri = f.get("a")
            break
    if not uri:
        for v in main.get_all("10"):
            if v.startswith("http"):
                uri = v
                break
    return AuthorityEntry(h, tuple(variants), lccn, uri, rec.control("001").strip())
