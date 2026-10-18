"""Enrich, never replace: add to a local record the fields it lacks, taken
from the best candidate for each field group, and trace every addition.

    enrich(local, candidates, policy) -> Result

Rules (design.md section 2.6):
- Only fields the local record lacks are added. Nothing is overwritten or
  removed; 1XX, 245, 250, 260/264, 008, 020 and every 9XX are never
  touched, at any confidence.
- What a candidate may give depends on its class: M0 every group, M1 all
  but 300, W subjects, classification and 505/520 only, R nothing.
- Donors are ranked by class first (M0 > M1 > W), then completeness, then
  source weight, then score: a rich record of the wrong edition never beats
  a plainer one of the right edition.
- One donor per field group. Each added field gets $8 N\\p linking it to
  an 883 (machine-generated metadata provenance) naming class, score,
  date, source and the source's record id.
- Subjects on a Portuguese record come only from a Portuguese donor or a
  Brazilian source, and never with a foreign thesaurus in $2.
- Two different candidates of the same class within 0.02 of each other,
  or nothing but R candidates: no change, the record goes to review.
- A stub record (minimal level, or no imprint and no extent) never gets
  replaced automatically: the best M0 candidate is proposed for review.

The result is a plan for a staged batch; nothing here writes to Koha.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from . import classify
from .classify import M0, M1, W, R, CLASS_ORDER, Keys, Match, Thresholds
from .marc import Field, Record
from .normalize import fold

SUBJECT_TAGS = ("600", "610", "611", "630", "647", "648", "650", "651", "655")
PROTECTED = re.compile(r"^(1..|245|250|260|264|008|020|9..)$")
# Field groups: (name, tags, classes that may give them). A group is added
# only when the local record lacks it: no 6XX at all for subjects (or, with
# the "union" policy, headings it does not have yet), no field of the tag
# for the others, a 024 value it does not have yet.
GROUPS = (
    ("subjects", SUBJECT_TAGS, (M0, M1, W)),
    ("082", ("082",), (M0, M1, W)),
    ("080", ("080",), (M0, M1, W)),
    ("505", ("505",), (M0, M1, W)),
    ("520", ("520",), (M0, M1, W)),
    ("300", ("300",), (M0,)),
    ("024", ("024",), (M0,)),
)
# Subfields never copied from a donor: $9 is the donor's own Koha
# authority id, $5 its institution, $8 its own field links.
DROP_SUBFIELDS = ("9", "5", "8")
FOREIGN_THESAURI = frozenset({"lcsh", "lcgft", "fast", "bne", "embne", "rameau", "gnd", "mesh", "sears"})


@dataclass
class Candidate:
    record: Record
    source: str                    # source id, e.g. "bn", "usp", "loc"
    remote_id: str = ""            # the record's id in that source
    weight: float = 0.5            # 0..1, the source's authority
    brazilian: bool = False        # a Brazilian source (subject rule)


@dataclass
class Policy:
    thresholds: Thresholds = field(default_factory=Thresholds)
    subjects: str = "fill-empty"   # or "union": add headings not already present
    today: str = ""                # YYYYMMDD for 883 $d; default: today
    agency: str = "nexus_enrich"
    donors: dict = field(default_factory=dict)   # group -> source the librarian chose (on-demand)


@dataclass
class Scored:
    candidate: Candidate
    match: Match
    completeness: int


@dataclass
class Addition:
    group: str
    field: Field
    source: str
    remote_id: str
    cls: str
    score: float


@dataclass
class Result:
    status: str                    # "enriched", "unchanged", "review", "no-match"
    record: Record                 # the local record plus additions (a copy)
    additions: list[Addition] = field(default_factory=list)
    candidates: list[Scored] = field(default_factory=list)   # ranked, R last
    review: list[str] = field(default_factory=list)
    replacement: Scored | None = None                         # stub: proposed, never applied

    @property
    def counts(self) -> dict[str, int]:
        out = {M0: 0, M1: 0, W: 0}
        for a in self.additions:
            out[a.cls] += 1
        return out


def _rank_key(s: Scored):
    return (CLASS_ORDER[s.match.cls], -s.completeness, -s.candidate.weight, -s.match.score)


def rank(local: Record, candidates: list[Candidate], t: Thresholds | None = None) -> list[Scored]:
    """Classified candidates, best first; candidates of no class are left out."""
    keys = Keys.of(local)
    out = []
    for c in candidates:
        m = classify.classify(keys, Keys.of(c.record), t)
        if m.cls is not None:
            out.append(Scored(c, m, classify.completeness(c.record)))
    out.sort(key=_rank_key)
    return out


def _clean(f: Field, link: str) -> Field:
    subs = [(c, v) for c, v in f.subfields if c not in DROP_SUBFIELDS]
    return Field(f.tag, f.ind1, f.ind2, [("8", link)] + subs)


def _heading_key(f: Field) -> tuple[str, str]:
    return f.tag, fold(" ".join(v for c, v in f.subfields if c.isalpha()))


def _subject_allowed(f: Field, local_lang: str, donor: Scored) -> bool:
    thesaurus = f.get("2").strip().lower()
    if local_lang == "por":
        if thesaurus and thesaurus.split()[0] in FOREIGN_THESAURI:
            return False
        donor_lang = classify.Keys.of(donor.candidate.record).language
        return donor_lang == "por" or donor.candidate.brazilian
    return True


def _same_language_needed(group: str, cls: str) -> bool:
    return cls == W and group in ("subjects", "505", "520")


def _author_dates(rec: Record) -> str:
    f = rec.first("100", "110", "111")
    return fold(f.get("d")) if f is not None else ""


def _different_works(a: Record, b: Record) -> bool:
    """Two candidates that both pass as the local record's work but are not
    the same work as each other: other work keys, or main authors with
    different dates (two "Silva, José" who are different people). Other
    manifestations of one work are not ambiguous."""
    if Keys.of(a).work_key != Keys.of(b).work_key:
        return True
    da, db = _author_dates(a), _author_dates(b)
    return bool(da and db and da != db)


def _next_link(rec: Record) -> int:
    used = [0]
    for f in rec.fields:
        for code, value in f.subfields:
            if code == "8":
                m = re.match(r"(\d+)", value)
                if m:
                    used.append(int(m.group(1)))
    return max(used) + 1


def _fields_for(group: str, tags: tuple[str, ...], local: Record, donor: Scored, policy: Policy,
                local_lang: str) -> list[Field]:
    rec = donor.candidate.record
    if group == "subjects":
        have = local.get_fields(*tags)
        if have and policy.subjects != "union":
            return []
        present = {_heading_key(f) for f in have}
        out, seen = [], set()
        for f in rec.get_fields(*tags):
            key = _heading_key(f)
            if key in present or key in seen or not _subject_allowed(f, local_lang, donor):
                continue
            seen.add(key)
            out.append(f)
        return out
    if group == "024":
        have = {fold(f.get("a")) for f in local.get_fields("024")}
        return [f for f in rec.get_fields("024") if f.get("a") and fold(f.get("a")) not in have]
    if local.has(*tags):
        return []
    return rec.get_fields(*tags)


def enrich(local: Record, candidates: list[Candidate], policy: Policy | None = None) -> Result:
    policy = policy or Policy()
    t = policy.thresholds
    ranked = rank(local, candidates, t)
    out = local.copy()
    result = Result("no-match", out, candidates=ranked)
    usable = [s for s in ranked if s.match.cls != R]
    for s in ranked:
        if s.match.cls == R:
            result.review.extend(f"{s.candidate.source}:{s.candidate.remote_id}: {r}" for r in s.match.reasons)

    if not usable:
        result.status = "review" if ranked else "no-match"
        return result

    # Ambiguity: the two best of the same class are different works or
    # manifestations and score within the tie margin.
    if len(usable) > 1:
        a, b = usable[0], usable[1]
        if a.match.cls == b.match.cls and abs(a.match.score - b.match.score) <= t.tie:
            if _different_works(a.candidate.record, b.candidate.record):
                result.status = "review"
                result.review.append(f"two candidates within {t.tie}: {a.candidate.source}:{a.candidate.remote_id}"
                                     f" and {b.candidate.source}:{b.candidate.remote_id}")
                return result

    if classify.is_stub(local):
        best_m0 = next((s for s in usable if s.match.cls == M0), None)
        if best_m0 is not None:
            result.replacement = best_m0
            result.review.append(f"stub record: full replacement by {best_m0.candidate.source}:"
                                 f"{best_m0.candidate.remote_id} proposed (never applied automatically)")

    local_lang = Keys.of(local).language
    stamp = policy.today or date.today().strftime("%Y%m%d")
    link = _next_link(out)
    for group, tags, classes in GROUPS:
        chosen = policy.donors.get(group)
        # A chosen donor goes first for its group; the class rules still apply to it.
        order = sorted(usable, key=lambda s: s.candidate.source != chosen) if chosen else usable
        for donor in order:
            cls = donor.match.cls
            if cls not in classes:
                continue
            if _same_language_needed(group, cls):
                donor_lang = Keys.of(donor.candidate.record).language
                if not local_lang or donor_lang != local_lang:
                    continue
            fields = _fields_for(group, tags, out, donor, policy, local_lang)
            if not fields:
                continue
            ref = f"{link}\\p"
            for f in fields:
                assert not PROTECTED.match(f.tag), f.tag
                added = _clean(f, ref)
                out.add_field(added)
                result.additions.append(Addition(group, added, donor.candidate.source, donor.candidate.remote_id,
                                                 cls, donor.match.score))
            prov = [("8", ref), ("a", f"{policy.agency} {cls}"), ("c", f"{donor.match.score:.2f}"),
                    ("d", stamp), ("q", donor.candidate.source)]
            if donor.candidate.remote_id:
                prov.append(("w", donor.candidate.remote_id))
            out.add_field(Field("883", "0", " ", prov))
            link += 1
            break           # one donor per group
    result.status = "enriched" if result.additions else ("review" if result.review else "unchanged")
    return result
