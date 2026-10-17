"""Records for the tests, written by hand: bib() builds a MARC21
bibliographic record from a few keywords, so each test shows exactly
which fields differ between the local record and a candidate."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nexus_enrich.marc import Field, Record  # noqa: E402


def bib(title: str, author: str | None = None, isbn: str | None = None, year: int | None = None,
        ed: str | None = None, publisher: str | None = None, lang: str = "por", subjects=(), extra=(),
        level: str = " ", rid: str | None = None, nonfiling: int = 0, extent: str | None = "200 p.") -> Record:
    f008 = list(" " * 40)
    f008[0:6] = "201017"
    f008[6] = "s"
    f008[7:11] = f"{year:04d}" if year else "    "
    f008[15:18] = "bl "
    f008[35:38] = lang
    f008[39] = "d"
    f008 = "".join(f008)
    rec = Record(leader="00000nam a2200000" + level + "a 4500")
    if rid:
        rec.fields.append(Field("001", data=rid))
    rec.fields.append(Field("008", data=f008))
    if isbn:
        rec.fields.append(Field("020", " ", " ", [("a", isbn)]))
    if author:
        rec.fields.append(Field("100", "1", " ", [("a", author)]))
    rec.fields.append(Field("245", "1" if author else "0", str(nonfiling), [("a", title)]))
    if ed:
        rec.fields.append(Field("250", " ", " ", [("a", ed)]))
    if publisher or year:
        subs = [("a", "São Paulo :")]
        if publisher:
            subs.append(("b", publisher + ","))
        if year:
            subs.append(("c", str(year)))
        rec.fields.append(Field("260", " ", " ", subs))
    if extent:
        rec.fields.append(Field("300", " ", " ", [("a", extent)]))
    for s in subjects:
        rec.fields.append(s if isinstance(s, Field) else Field("650", " ", "4", [("a", s)]))
    for f in extra:
        rec.add_field(f)
    return rec
