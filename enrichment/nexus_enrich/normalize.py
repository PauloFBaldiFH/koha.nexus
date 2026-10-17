"""Search and match keys: folding, ISBNs, titles, names, years, publishers,
language, and the similarity measure the match classes use.

The ISBN code is catalog-network's (nexus_catalog/marc.py), copied rather
than imported so this package has no dependency on that service.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

from .marc import Record


def fold(text: str) -> str:
    """Lower case, no accents, punctuation to spaces, single spaces."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"\w+", text))


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
    """Both forms of the ISBN in RAW, ISBN-13 first; [] when there is none.
    A wrong check digit is kept as typed but gets no converted form."""
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


def isbn13_valid(isbn: str) -> bool:
    return len(isbn) == 13 and isbn.isdigit() and _isbn13_check(isbn[:12]) == isbn[12]


def isbns13(rec: Record) -> list[str]:
    """The valid ISBN-13s of a record's 020 $a (a 10-digit ISBN is
    converted). Cancelled ISBNs ($z) are not identity: they are left out."""
    out: list[str] = []
    for f in rec.get_fields("020"):
        for value in f.get_all("a"):
            for form in isbn_forms(value):
                if isbn13_valid(form) and form not in out:
                    out.append(form)
    return out


def issns(rec: Record) -> list[str]:
    out = []
    for f in rec.get_fields("022"):
        for value in f.get_all("a"):
            m = re.search(r"\d{4}-?\d{3}[\dXx]", value)
            if m:
                out.append(m.group(0).replace("-", "").upper())
    return list(dict.fromkeys(out))


# ----------------------------------------------------------------------
# Title, names, year, publisher, language
# ----------------------------------------------------------------------
def _nonfiling(f) -> int:
    return int(f.ind2) if f.ind2.isdigit() else 0


def title_main(rec: Record) -> str:
    """245 $a with the non-filing characters (ind2) dropped, folded."""
    f = rec.first("245")
    if f is None:
        return ""
    a = f.get("a")
    return fold(a[_nonfiling(f):] if a else "")


def title_full(rec: Record) -> str:
    """245 $a $b $n $p, non-filing characters dropped, folded."""
    f = rec.first("245")
    if f is None:
        return ""
    parts = [v for c, v in f.subfields if c in "abnp"]
    if parts and f.subfields and f.subfields[0][0] == "a":
        parts[0] = parts[0][_nonfiling(f):]
    return fold(" ".join(parts))


def name_key(name: str) -> str:
    """A name as a sorted token set without dates, so "Saramago, José,
    1922-2010" and "José Saramago" give the same key."""
    name = re.sub(r"\d{3,4}\??-?(\d{3,4})?", " ", name or "")
    return " ".join(sorted(set(fold(name).split())))


def main_author(rec: Record) -> str:
    f = rec.first("100", "110", "111")
    if f is not None:
        return f.text("abcq")
    f = rec.first("700", "710", "711")
    return f.text("abcq") if f is not None else ""


def author_surname(rec: Record) -> str:
    name = main_author(rec)
    if "," in name:
        return fold(name.split(",", 1)[0])
    words = fold(name).split()
    return words[-1] if words else ""


def year(rec: Record) -> tuple[int | None, bool]:
    """(year, approximate). 008/07-10 first, then 264 #1 $c, then 260 $c.
    "c1998" -> 1998; "[1998?]" -> 1998 approximate; "199-" -> 1990
    approximate."""
    raw = rec.control("008")[7:11]
    if raw.isdigit() and raw != "0000":
        return int(raw), False
    if re.fullmatch(r"\d{3}[u\-]", raw or ""):
        return int(raw[:3] + "0"), True
    texts = [f.get("c") for f in rec.get_fields("264") if f.ind2 == "1"]
    texts += [f.get("c") for f in rec.get_fields("260")]
    for text in texts:
        m = re.search(r"(\d{4})", text or "")
        if m:
            return int(m.group(1)), ("?" in text or "[" in text)
        m = re.search(r"(\d{3})-", text or "")
        if m:
            return int(m.group(1) + "0"), True
    return None, False


_PUB_NOISE = {"editora", "ed", "edicoes", "edicao", "livraria", "ltda", "sa", "s", "a", "inc", "publishers",
              "publisher", "publishing", "press", "co", "the", "grupo", "cia", "companhia", "das", "de", "do",
              "da", "e"}


def publisher(rec: Record) -> str:
    for f in rec.get_fields("264"):
        if f.ind2 == "1" and f.get("b"):
            return _pub_key(f.get("b"))
    f = rec.first("260")
    return _pub_key(f.get("b")) if f is not None else ""


def _pub_key(text: str) -> str:
    words = [w for w in fold(text).split() if w not in _PUB_NOISE]
    return " ".join(words)


def language(rec: Record) -> str:
    """008/35-37, else the first 041 $a; "" when unknown."""
    code = rec.control("008")[35:38].strip().lower()
    if len(code) == 3 and code.isalpha() and code not in ("und", "zxx", "mul"):
        return code
    f = rec.first("041")
    if f is not None and f.get("a"):
        return f.get("a")[:3].lower()
    return ""


def work_key(rec: Record) -> str:
    basis = title_main(rec) + "|" + author_surname(rec)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:20]


# ----------------------------------------------------------------------
# Similarity
# ----------------------------------------------------------------------
def similarity(a: str, b: str) -> float:
    """0..1 on folded text: the better of the character ratio and the
    sorted-token ratio, so word order ("Silva, José" / "José Silva") and
    small typos both count as close. Two empty strings score 0."""
    a, b = fold(a), fold(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    direct = SequenceMatcher(None, a, b, autojunk=False).ratio()
    sa, sb = " ".join(sorted(a.split())), " ".join(sorted(b.split()))
    tokens = SequenceMatcher(None, sa, sb, autojunk=False).ratio()
    return max(direct, tokens)


def name_similarity(a: str, b: str) -> float:
    return similarity(name_key(a), name_key(b))
