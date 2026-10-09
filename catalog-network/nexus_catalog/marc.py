"""MARCXML in and out: read what a koha.nexus instance sends, keep what the
shared pool needs, and pull out the search keys (ISBN, title, author).

Standard library only (ElementTree). A record sent to the pool loses its
local 9XX fields (Koha's 942 item type, 952 items, 999 biblionumber): they
describe one library's copies, not the work.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

MARC = "http://www.loc.gov/MARC21/slim"
ET.register_namespace("marc", MARC)
_M = f"{{{MARC}}}"


class RecordError(ValueError):
    """A record the pool cannot take (the message says why)."""


@dataclass
class Record:
    element: ET.Element
    isbns: list[str] = field(default_factory=list)   # ISBN-13 first, then ISBN-10 forms
    issns: list[str] = field(default_factory=list)
    title: str = ""
    author: str = ""               # main entry (1XX), else the first 7XX
    authors: str = ""              # every name, for the author search
    year: str = ""
    keywords: str = ""

    @property
    def idents(self) -> list[str]:
        return list(dict.fromkeys(self.isbns + self.issns))

    @property
    def key(self) -> str:
        """What makes two records the same work when they share no ISBN."""
        thirteen = [i for i in self.isbns if len(i) == 13]
        if thirteen:
            return "isbn:" + min(thirteen)
        if self.issns:
            return "issn:" + min(self.issns)
        basis = "|".join((fold(self.title), fold(self.author), self.year))
        return "t:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()

    def xml(self) -> str:
        return ET.tostring(self.element, encoding="unicode")


# ----------------------------------------------------------------------
# ISBN / ISSN
# ----------------------------------------------------------------------
def _isbn10_check(nine: str) -> str:
    s = sum((10 - i) * int(d) for i, d in enumerate(nine)) % 11
    c = (11 - s) % 11
    return "X" if c == 10 else str(c)


def _isbn13_check(twelve: str) -> str:
    s = sum((3 if i % 2 else 1) * int(d) for i, d in enumerate(twelve))
    return str((10 - s % 10) % 10)


def isbn_forms(raw: str) -> list[str]:
    """Both forms of an ISBN found in RAW ("978-85-359-0277-8 (broch.)"),
    ISBN-13 first; [] when there is none. A wrong check digit is kept as
    typed (catalogues have them) but gets no converted form."""
    m = re.search(r"97[89][\d\-\s]{10,16}|\d[\d\-\s]{8,12}[\dXx]", raw or "")
    if not m:
        return []
    digits = re.sub(r"[\s\-]", "", m.group(0)).upper()
    if len(digits) == 13 and digits.isdigit():
        out = [digits]
        if digits.startswith("978") and _isbn13_check(digits[:12]) == digits[12]:
            out.append(digits[3:12] + _isbn10_check(digits[3:12]))
        return out
    if len(digits) == 10 and digits[:9].isdigit() and (digits[9].isdigit() or digits[9] == "X"):
        if _isbn10_check(digits[:9]) != digits[9]:
            return [digits]
        thirteen = "978" + digits[:9]
        return [thirteen + _isbn13_check(thirteen), digits]
    return []


def issn_form(raw: str) -> str:
    m = re.search(r"\d{4}-?\d{3}[\dXx]", raw or "")
    return m.group(0).replace("-", "").upper() if m else ""


def fold(text: str) -> str:
    """Lower case, no accents, single spaces: for keys and comparisons."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"\w+", text))


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _renamespace(el: ET.Element) -> ET.Element:
    """A copy in the MARC21 slim namespace (some exports carry none)."""
    out = ET.Element(_M + _local(el.tag), dict(el.attrib))
    out.text = el.text
    out.tail = None
    for child in el:
        node = _renamespace(child)
        node.tail = None
        out.append(node)
    return out


def split_records(xml: str | bytes) -> list[ET.Element]:
    """The <record> elements of a <collection>, a lone <record> or an SRU
    response. Raises RecordError when it is not XML at all."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise RecordError(f"not XML: {exc}") from None
    return [el for el in root.iter() if _local(el.tag) == "record"
            and any(_local(c.tag) == "leader" for c in el)]


def subfields(df: ET.Element, codes: str) -> list[str]:
    return [(sf.text or "").strip() for sf in df
            if _local(sf.tag) == "subfield" and sf.get("code", "") in codes and (sf.text or "").strip()]


def _clean(text: str) -> str:
    """Trailing ISBD punctuation off: "Dom Casmurro /" -> "Dom Casmurro"."""
    return re.sub(r"[\s/:;,.=]+$", "", " ".join(text.split()))


def read(el: ET.Element, max_bytes: int = 200_000) -> Record:
    """One MARCXML record, checked and cleaned, with its search keys."""
    rec = _renamespace(el)
    leader = rec.find(f"{_M}leader")
    if leader is None or len((leader.text or "").strip()) < 20:
        raise RecordError("no leader")
    for df in list(rec):
        tag = df.get("tag", "")
        if _local(df.tag) in ("datafield", "controlfield") and tag[:1] == "9":
            rec.remove(df)
    fields = [df for df in rec if _local(df.tag) == "datafield"]
    controls = {cf.get("tag"): (cf.text or "") for cf in rec if _local(cf.tag) == "controlfield"}

    def first(tags: str, codes: str) -> str:
        for df in fields:
            if df.get("tag") in tags.split():
                parts = subfields(df, codes)
                if parts:
                    return _clean(" ".join(parts))
        return ""

    title = first("245", "abnp")
    if not title:
        raise RecordError("no title (245)")
    r = Record(element=rec, title=title, author=first("100 110 111", "abcdq"))
    for df in fields:
        tag = df.get("tag")
        if tag == "020":
            for v in subfields(df, "a"):
                r.isbns.extend(isbn_forms(v))
        elif tag == "022":
            for v in subfields(df, "a"):
                issn = issn_form(v)
                if issn:
                    r.issns.append(issn)
    r.isbns = list(dict.fromkeys(sorted(r.isbns, key=len, reverse=True)))
    r.issns = list(dict.fromkeys(r.issns))
    date = controls.get("008", "")[7:11]
    if not date.isdigit():
        m = re.search(r"\d{4}", first("264 260", "c"))
        date = m.group(0) if m else ""
    r.year = date
    added = [_clean(" ".join(subfields(df, "abcdq"))) for df in fields if df.get("tag") in ("700", "710", "711")]
    subjects = [" ".join(subfields(df, "abcdvxyz")) for df in fields if df.get("tag", "")[:1] == "6"]
    other = [" ".join(subfields(df, "ab")) for df in fields if df.get("tag") in ("246", "250", "260", "264", "490",
                                                                              "500", "520")]
    r.author = r.author or (added[0] if added else "")
    r.authors = " ".join(dict.fromkeys([r.author, *added]))
    r.keywords = " ".join([r.title, r.authors, *subjects, *other, r.year, *r.idents])
    data = r.xml().encode("utf-8")
    if len(data) > max_bytes:
        raise RecordError(f"record too large ({len(data)} bytes)")
    return r


def checksum(xml: str) -> str:
    return hashlib.sha1(xml.encode("utf-8")).hexdigest()
