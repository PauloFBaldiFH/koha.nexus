"""Manifestation affinity: how close a candidate record is to the local one.

Every candidate falls in one class before anything is scored
(design.md section 2.6):

    M0  same manifestation   shared valid ISBN, title >= 0.85, same year,
                             compatible edition
    M1  reprint              as M0 but the year differs by 1, same edition
                             statement and same publisher
    W   work level           same work (title >= 0.85, author >= 0.80) but
                             another year or edition, or no shared ISBN
    R   review               anything ambiguous: a shared ISBN with another
                             title (ISBN reuse), a shared ISBN with another
                             edition, a 2-year gap with the same edition,
                             a missing year where M0/M1 needs one

A candidate that is not even the same work gets no class (None) and is
dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import edition, normalize
from .marc import Record

M0, M1, W, R = "M0", "M1", "W", "R"
CLASS_ORDER = {M0: 0, M1: 1, W: 2, R: 3}


@dataclass
class Thresholds:
    title: float = 0.85           # title similarity for the same work
    author: float = 0.80          # main-author similarity for the same work
    title_alone: float = 0.95     # title similarity when neither side has an author
    publisher: float = 0.80       # publisher similarity for M1
    reprint_years: int = 1        # year gap a reprint may have (M1)
    tie: float = 0.02             # two different candidates this close: review


@dataclass
class Keys:
    """What the classes compare, read once per record."""
    isbns: list[str]
    title_main: str
    title_full: str
    author: str
    year: int | None
    year_approx: bool
    edition: edition.Edition | None
    publisher: str
    language: str
    work_key: str

    @classmethod
    def of(cls, rec: Record) -> "Keys":
        y, approx = normalize.year(rec)
        return cls(isbns=normalize.isbns13(rec), title_main=normalize.title_main(rec),
                   title_full=normalize.title_full(rec), author=normalize.main_author(rec), year=y,
                   year_approx=approx, edition=edition.of(rec), publisher=normalize.publisher(rec),
                   language=normalize.language(rec), work_key=normalize.work_key(rec))


@dataclass
class Match:
    cls: str | None
    title: float
    author: float | None          # None: neither record has an author
    score: float                  # 0.6 title + 0.4 author (title twice when no author)
    isbn_shared: bool
    year_gap: int | None
    edition: str                  # edition.SAME / DIFFERENT / UNKNOWN
    reasons: list[str] = field(default_factory=list)


def _title_sim(a: Keys, b: Keys) -> float:
    return max(normalize.similarity(a.title_full, b.title_full),
               normalize.similarity(a.title_main, b.title_main))


def _publisher_same(a: Keys, b: Keys, t: Thresholds) -> bool:
    return bool(a.publisher and b.publisher) and normalize.similarity(a.publisher, b.publisher) >= t.publisher


def classify(local: Keys, cand: Keys, t: Thresholds | None = None) -> Match:
    t = t or Thresholds()
    title = _title_sim(local, cand)
    if local.author and cand.author:
        author: float | None = normalize.name_similarity(local.author, cand.author)
    elif not local.author and not cand.author:
        author = None
    else:
        author = 0.0
    score = round(0.6 * title + 0.4 * (title if author is None else author), 4)
    shared = bool(set(local.isbns) & set(cand.isbns))
    gap = abs(local.year - cand.year) if local.year is not None and cand.year is not None else None
    ed = edition.compare(local.edition, cand.edition)
    m = Match(None, round(title, 4), None if author is None else round(author, 4), score, shared, gap, ed)

    if shared and title < t.title:
        m.cls = R
        m.reasons.append(f"shared ISBN but different title ({title:.2f}): ISBN reused?")
        return m
    if author is None:
        same_work = title >= t.title_alone
    elif author == 0.0 and not (local.author and cand.author):
        # One side has no author: only a shared ISBN can vouch for the work.
        same_work = shared and title >= t.title
        if same_work:
            m.reasons.append("main author missing on one side")
    else:
        same_work = title >= t.title and author >= t.author
    if not same_work:
        if shared:
            m.cls = R
            m.reasons.append(f"shared ISBN but author differs ({author:.2f})" if author is not None
                             else "shared ISBN but title below the no-author threshold")
        return m

    if shared:
        if ed == edition.DIFFERENT:
            m.cls = R
            m.reasons.append("shared ISBN but different edition statements")
        elif gap is None:
            m.cls = R
            m.reasons.append("year missing on one side")
        elif gap == 0:
            both_without_250 = local.edition is None and cand.edition is None
            if ed == edition.SAME or both_without_250 or _publisher_same(local, cand, t):
                m.cls = M0
            else:
                m.cls = R
                m.reasons.append("same ISBN and year but edition unknown and publisher differs")
        elif gap <= t.reprint_years:
            both_without_250 = local.edition is None and cand.edition is None
            if (ed == edition.SAME or both_without_250) and _publisher_same(local, cand, t):
                m.cls = M1
            else:
                m.cls = R
                m.reasons.append(f"{gap}-year gap without the same edition and publisher")
        elif gap == t.reprint_years + 1:
            m.cls = R
            m.reasons.append(f"{gap}-year gap with a shared ISBN")
        else:
            m.cls = W
        return m

    if gap == t.reprint_years + 1 and ed == edition.SAME:
        m.cls = R
        m.reasons.append(f"{gap}-year gap with the same edition statement")
        return m
    m.cls = W
    return m


# ----------------------------------------------------------------------
# Completeness and ranking
# ----------------------------------------------------------------------
# MARC organization codes (040 $a, compared upper case) of national agencies.
NATIONAL_AGENCIES = frozenset({"DLC", "BR-RJBN", "SPMABN", "FRPBN", "DE-101", "UK", "POLIBN", "CAOONL"})


def completeness(rec: Record) -> int:
    """Encoding level (leader/17: full " " or 1 -> 3, core 4 -> 2, less than
    full 2 or prepublication 8 -> 1, minimal 3, 5, 7 -> 0) + controlled
    subjects 3 + 082/080 2 + 520/505 1 + a national agency in 040 $a 1."""
    level = rec.leader[17:18] if len(rec.leader) > 17 else " "
    score = {" ": 3, "1": 3, "4": 2, "2": 1, "8": 1}.get(level, 0)
    controlled = any(f.ind2 in "0123456" or (f.ind2 == "7" and f.get("2"))
                     for f in rec.get_fields("600", "610", "611", "630", "650", "651", "655"))
    score += 3 if controlled else 0
    score += 2 if rec.has("082", "080") else 0
    score += 1 if rec.has("520", "505") else 0
    f040 = rec.first("040")
    if f040 is not None and f040.get("a").strip().upper() in NATIONAL_AGENCIES:
        score += 1
    return score


def is_stub(rec: Record) -> bool:
    """Abbreviated or minimal (leader/17 3, 5, 7), or neither 260/264 nor 300."""
    level = rec.leader[17:18] if len(rec.leader) > 17 else ""
    return level in ("3", "5", "7") or (not rec.has("260", "264") and not rec.has("300"))
