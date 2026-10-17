"""Edition statements (250) as data: "2. ed.", "2ª ed.", "2nd ed." and
"segunda edição" are all edition 2; "ed. rev. e ampl." is a revision;
"3. reimpr." is a reprint, which does not make a new edition.

compare() answers "same", "different" or "unknown". A record without a
250 is "unknown", never assumed to be the first edition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .marc import Record
from .normalize import fold

SAME, DIFFERENT, UNKNOWN = "same", "different", "unknown"

_ORDINAL_WORDS = {
    # Portuguese, Spanish, English, French, Italian, German
    "primeira": 1, "primera": 1, "first": 1, "premiere": 1, "prima": 1, "erste": 1,
    "segunda": 2, "second": 2, "deuxieme": 2, "seconda": 2, "zweite": 2,
    "terceira": 3, "tercera": 3, "third": 3, "troisieme": 3, "terza": 3, "dritte": 3,
    "quarta": 4, "cuarta": 4, "fourth": 4, "quatrieme": 4, "vierte": 4,
    "quinta": 5, "fifth": 5, "cinquieme": 5, "funfte": 5,
    "sexta": 6, "sixth": 6, "sixieme": 6, "sesta": 6,
    "setima": 7, "septima": 7, "seventh": 7, "settima": 7,
    "oitava": 8, "octava": 8, "eighth": 8, "ottava": 8,
    "nona": 9, "novena": 9, "ninth": 9,
    "decima": 10, "tenth": 10,
}
_REVISION = re.compile(r"\b(rev|revista|revisada|revisado|revised|revisee|riveduta|atual|atualizada|actualizada|"
                       r"ampl|ampliada|aum|aumentada|corr|corrigida|corregida|updated|enlarged|expanded|"
                       r"neubearb|uberarb)\w*")
_REPRINT = re.compile(r"\b(reimpr|reimpressao|reimpresion|reprint|tiragem|tirage|ristampa|nachdr)\w*")
# "2.", "2a", "2ª" (folded to "2a"), "2nd", "2e", "2o", "2"; followed by an edition word.
_NUMBERED = re.compile(r"\b(\d{1,3})\s*(?:a|o|nd|rd|st|th|e|eme|er|re)?\s+"
                       r"(?:ed|edicao|edicion|edition|edizione|auflage|aufl)\b")
_EDITION_WORD = re.compile(r"\b(ed|edicao|edicion|edition|edizione|auflage|aufl)\b")


@dataclass(frozen=True)
class Edition:
    number: int | None
    revised: bool
    reprint: bool
    other: str          # folded text when no number was found

    @property
    def empty(self) -> bool:
        return self.number is None and not self.revised and not self.other


def parse(text: str) -> Edition:
    raw = (text or "").replace("ª", "a").replace("º", "o")
    folded = fold(raw)
    # Reprint counts are numbers too ("2. ed., 3. reimpr."): drop them
    # before looking for the edition number.
    without_reprint = re.sub(r"\b\d{1,3}\s*(?:a|o)?\s+(?:reimpr\w*|reimpressao|reimpresion|reprint\w*|tiragem)\b",
                             " ", folded)
    number = None
    m = _NUMBERED.search(without_reprint)
    if m:
        number = int(m.group(1))
    if number is None:
        for word in without_reprint.split():
            if word in _ORDINAL_WORDS and _EDITION_WORD.search(without_reprint):
                number = _ORDINAL_WORDS[word]
                break
    revised = bool(_REVISION.search(folded))
    reprint = bool(_REPRINT.search(folded))
    other = "" if number is not None or revised else _REPRINT.sub(" ", without_reprint).strip()
    other = " ".join(other.split())
    return Edition(number, revised, reprint, other)


def of(rec: Record) -> Edition | None:
    """The record's edition, or None when it has no 250."""
    f = rec.first("250")
    if f is None:
        return None
    return parse(f.text("ab"))


def compare(a: Edition | None, b: Edition | None) -> str:
    if a is None or b is None or a.empty or b.empty:
        return UNKNOWN
    if a.number is not None and b.number is not None:
        if a.number != b.number or a.revised != b.revised:
            return DIFFERENT
        return SAME
    if a.number is None and b.number is None:
        if a.revised != b.revised:
            return DIFFERENT
        if a.other and a.other == b.other:
            return SAME
        if not a.other and not b.other:
            return SAME          # both only "revised"
    return UNKNOWN
