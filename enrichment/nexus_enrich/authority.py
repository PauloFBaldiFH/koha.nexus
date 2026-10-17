"""Authority matching for "Enrich & standardize authorities" jobs.

Each name or subject heading of a bibliographic record is matched, in this
order, against:
1. the library's own Koha authorities (exported with the job): the
   authorised heading, then its 4XX variants;
2. the headings of static.db (auth_headings): Biblioteca Nacional first,
   then the other Brazilian sources, then the Library of Congress, then the
   rest; authority records before headings gathered from bibliographic
   records, then by how often a heading occurs;
3. with mode "fuzzy", headings at least FUZZY_MIN alike (one typo): applied
   and the new authority marked preliminary; with mode "exact" they are only
   proposed for review.

What a match does to the bibliographic field:
    linked     the field already has $9: left alone
    koha       an authority in Koha: $9 is added; the form becomes Koha's
               authorised form when it differs (a variant, missing dates)
    new        a heading of static.db and none in Koha: a new authority is
               created at Apply (one per heading for the whole job) and
               linked; the form is standardised the same way
    review     several people or authorities fit, or only a close form:
               nothing is changed, the report lists it
    none       nothing fits
    skipped    a name/title entry ($t) or a subject with subdivisions
               ($v $x $y $z): Koha links those to their own authorities

Subjects (650, 651, 655) never take LCSH or LoC forms: LCSH is English, and
a Portuguese catalogue keeps Portuguese subjects (design, decision 9).
Corporate, meeting and uniform-title forms are only taken from Koha or from
the record's own field: static.db keeps headings as text, without their
subfields, so a form that differs is sent to review instead of guessed.
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import headings, marc
from .headings import Heading
from .normalize import fold, similarity

FUZZY_MIN = 0.92
NAME_KINDS = ("personal", "corporate", "meeting")
SUBJECT_KINDS = ("topical", "geographic", "genre")
LINK_TAGS = ("100", "110", "111", "130", "600", "610", "611", "630", "650", "651", "655",
             "700", "710", "711", "730")
AUTH_TAG = {"personal": "100", "corporate": "110", "meeting": "111", "uniform": "130",
            "topical": "150", "geographic": "151", "genre": "155"}
# Subfields that turn a name into a name/title entry.
_TITLE_CODES = "fklmnoprst"
_SUBDIVISIONS = "vxyz"
# Placeholder $9 for an authority created at Apply; chunk_file() puts the
# real authid in its place.
NEW_PREFIX = "nexus-new:"
BN_IDS = ("bn", "fbn", "biblioteca-nacional", "bnb")
LOC_IDS = ("loc", "lc", "lcnaf", "lcsh", "naf", "library-of-congress")


def kind_of(f: marc.Field) -> tuple[str, str] | None:
    """(kind, heading subfields) of a bibliographic heading field."""
    return headings._BIB_KINDS.get(f.tag[1:]) if f.tag in LINK_TAGS else None


def heading_of(f: marc.Field) -> Heading | None:
    k = kind_of(f)
    return headings.from_field(f, k[1], k[0]) if k else None


def _fdates(d: str) -> str:
    return fold(d)


def dates_fit(a: str, b: str) -> bool:
    """Dates that may be the same person: one missing, equal, or one open
    ("1922-") and the other closed ("1922-2010")."""
    fa, fb = _fdates(a), _fdates(b)
    return not fa or not fb or fa.startswith(fb) or fb.startswith(fa)


def date_groups(dates: list[str]) -> int:
    """How many different people the dates describe (fitting dates are one)."""
    groups: list[str] = []
    for d in sorted({_fdates(x) for x in dates if _fdates(x)}, key=len, reverse=True):
        if not any(g.startswith(d) or d.startswith(g) for g in groups):
            groups.append(d)
    return len(groups)


# ----------------------------------------------------------------------
# The library's own authorities
# ----------------------------------------------------------------------
@dataclass
class KohaAuthority:
    authid: int
    heading: Heading
    variants: tuple[str, ...]
    field: marc.Field


class KohaIndex:
    """Koha's authorities as exported (001 = authid)."""

    def __init__(self, records=()):
        self.items: list[KohaAuthority] = []
        self._key: dict[tuple[str, str], list[int]] = {}
        self._variant: dict[tuple[str, str], list[int]] = {}
        self._tokens: dict[tuple[str, str], set[int]] = {}
        for rec in records:
            self.add(rec)

    @classmethod
    def from_file(cls, path: Path | str) -> "KohaIndex":
        index = cls()
        p = Path(path)
        if p.is_file() and p.stat().st_size:
            with open(p, "rb") as fh:
                for rec in marc.iter_xml(fh):
                    index.add(rec)
        return index

    def add(self, rec: marc.Record) -> None:
        authid = rec.control("001").strip()
        entry = headings.of_authority(rec)
        if entry is None or not authid.isdigit():
            return
        main = next(f for f in rec.fields if f.tag in headings.AUTH_TAGS)
        i = len(self.items)
        h = entry.heading
        self.items.append(KohaAuthority(int(authid), h, entry.variants, main))
        self._key.setdefault((h.kind, h.key), []).append(i)
        for v in entry.variants:
            self._variant.setdefault((h.kind, fold(v)), []).append(i)
            self._variant.setdefault((h.kind, _strip_dates(fold(v))), []).append(i)
        for tok in set(h.key.split()):
            if len(tok) >= 3:
                self._tokens.setdefault((h.kind, tok), set()).add(i)

    def __len__(self) -> int:
        return len(self.items)

    def exact(self, kind: str, key: str, dates: str) -> list[KohaAuthority]:
        return [self.items[i] for i in self._key.get((kind, key), []) if dates_fit(dates, self.items[i].heading.dates)]

    def variant(self, h: Heading) -> list[KohaAuthority]:
        seen, out = set(), []
        for k in {fold(h.heading), h.key}:
            for i in self._variant.get((h.kind, k), []):
                if i not in seen:
                    seen.add(i)
                    out.append(self.items[i])
        return out

    def fuzzy(self, h: Heading, minimum: float) -> list[tuple[float, KohaAuthority]]:
        count: dict[int, int] = {}
        for tok in set(h.key.split()):
            for i in self._tokens.get((h.kind, tok), ()):
                count[i] = count.get(i, 0) + 1
        best = sorted(count, key=lambda i: -count[i])[:200]
        out = []
        for i in best:
            a = self.items[i]
            s = similarity(h.key, a.heading.key)
            if s >= minimum and a.heading.key != h.key and dates_fit(h.dates, a.heading.dates):
                out.append((s, a))
        return sorted(out, key=lambda x: -x[0])


def _strip_dates(folded: str) -> str:
    return re.sub(r"(\s+\d[\d ]*)+$", "", folded).strip()


# ----------------------------------------------------------------------
# static.db headings
# ----------------------------------------------------------------------
@dataclass
class StaticHeading:
    id: int
    kind: str
    heading: str
    key: str
    dates: str
    thesaurus: str
    variants: tuple[str, ...]
    source: str
    source_id: str
    lccn: str
    uri: str
    occurrences: int
    preliminary: int
    tier: int

    @property
    def label(self) -> str:
        return self.heading


def is_bn(source: str, name: str = "") -> bool:
    return source in BN_IDS or ("biblioteca nacional" in fold(name) and "portugal" not in fold(name))


def is_loc(source: str, name: str = "") -> bool:
    return source in LOC_IDS or "library of congress" in fold(name)


class StaticHeadings:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.sources: dict[str, sqlite3.Row] = {}
        for r in conn.execute("SELECT * FROM sources"):
            self.sources[r["id"]] = r

    def tier(self, source: str) -> int:
        s = self.sources.get(source)
        name = s["name"] if s is not None else ""
        if is_bn(source, name):
            return 0
        if s is not None and s["brazilian"]:
            return 1
        if is_loc(source, name):
            return 2
        return 3

    def _rows(self, sql: str, args) -> list[StaticHeading]:
        out = []
        for r in self.conn.execute(sql, args):
            out.append(StaticHeading(
                r["id"], r["kind"], r["heading"], r["key"], r["dates"], r["thesaurus"],
                tuple(v for v in (r["variants"] or "").split("\n") if v), r["source"], r["source_id"], r["lccn"],
                r["uri"], r["occurrences"], r["preliminary"], self.tier(r["source"])))
        return out

    def _usable(self, rows: list[StaticHeading], kind: str) -> list[StaticHeading]:
        if kind in SUBJECT_KINDS:
            rows = [r for r in rows if not r.thesaurus.startswith("lcsh") and r.tier != 2]
        return sorted(rows, key=lambda r: (r.tier, r.preliminary, -r.occurrences, r.id))

    def exact(self, kind: str, key: str) -> list[StaticHeading]:
        return self._usable(self._rows("SELECT * FROM auth_headings WHERE kind = ? AND key = ? LIMIT 100",
                                       (kind, key)), kind)

    def _fts(self, column: str, expr: str, kind: str, limit: int) -> list[StaticHeading]:
        try:
            ids = [r[0] for r in self.conn.execute(
                "SELECT rowid FROM auth_fts WHERE auth_fts MATCH ? ORDER BY rank LIMIT ?",
                (f"{column} : {expr}", limit * 4))]
        except sqlite3.OperationalError:
            return []
        if not ids:
            return []
        rows = self._rows(f"SELECT * FROM auth_headings WHERE kind = ? AND id IN ({', '.join('?' * len(ids))})",
                          (kind, *ids))
        return rows[:limit]

    def variant(self, h: Heading) -> list[StaticHeading]:
        if not h.key:
            return []
        wanted = {h.key, fold(h.heading)}
        rows = [r for r in self._fts("variants", f'"{h.key}"', h.kind, 50)
                if any(fold(v) in wanted or _strip_dates(fold(v)) == h.key for v in r.variants)]
        return self._usable(rows, h.kind)

    def fuzzy(self, h: Heading, minimum: float) -> list[tuple[float, StaticHeading]]:
        toks = [t for t in h.key.split() if len(t) >= 3]
        if not toks:
            return []
        rows = self._fts("heading", "(" + " OR ".join(f'"{t}"' for t in toks) + ")", h.kind, 100)
        out = [(similarity(h.key, r.key), r) for r in self._usable(rows, h.kind)
               if r.key != h.key and dates_fit(h.dates, r.dates)]
        return sorted([x for x in out if x[0] >= minimum], key=lambda x: (-x[0], x[1].tier))


# ----------------------------------------------------------------------
# Matching one field
# ----------------------------------------------------------------------
@dataclass
class Match:
    action: str                                    # linked, koha, new, review, none, skipped
    heading: Heading | None = None
    form: list[tuple[str, str]] = field(default_factory=list)   # the authorised heading subfields
    authid: int | None = None
    static: StaticHeading | None = None
    fuzzy: float = 0.0
    reason: str = ""

    @property
    def standardized(self) -> bool:
        return bool(self.form) and self.heading is not None and fold(" ".join(v for _, v in self.form)) != fold(
            self.heading.heading)


def _own_form(f: marc.Field, codes: str) -> list[tuple[str, str]]:
    return [(c, v) for c, v in f.subfields if c in codes and v.strip()]


def _with_dates(form: list[tuple[str, str]], dates: str) -> list[tuple[str, str]]:
    """The field's own name with the dates of the authority added."""
    if not dates or any(c == "d" for c, _ in form):
        return form
    out = list(form)
    pos = max(i for i, (c, _) in enumerate(out) if c in "abcq") + 1
    c, v = out[pos - 1]
    if not v.rstrip().endswith((",", "-")):
        out[pos - 1] = (c, v.rstrip().rstrip(".") + ",")
    out.insert(pos, ("d", dates))
    return out


def text_form(kind: str, heading: str, dates: str) -> list[tuple[str, str]] | None:
    """Subfields of a heading known only as text, where that is safe: a
    personal name ($a, $d split off) or a one-part subject ($a). None for
    corporate, meeting and uniform-title forms."""
    if kind == "personal":
        name = heading
        if dates and name.endswith(dates):
            name = name[: -len(dates)].rstrip(" ,")
        return [("a", name + ","), ("d", dates)] if dates else [("a", name)]
    if kind in SUBJECT_KINDS:
        return [("a", heading)]
    return None


def _koha_form(a: KohaAuthority, codes: str) -> list[tuple[str, str]]:
    return [(c, v) for c, v in a.field.subfields if c in codes and v.strip()]


def match_field(f: marc.Field, koha: KohaIndex, static: StaticHeadings | None, mode: str = "exact") -> Match:
    k = kind_of(f)
    if k is None:
        return Match("skipped", reason="not a heading")
    kind, codes = k
    if any(c == "9" and v.strip() for c, v in f.subfields):
        return Match("linked", heading_of(f), reason="already linked")
    if kind in NAME_KINDS and any(c in _TITLE_CODES for c, _ in f.subfields):
        return Match("skipped", heading_of(f), reason="name/title entry")
    if f.tag.startswith("6") and any(c in _SUBDIVISIONS for c, _ in f.subfields):
        return Match("skipped", heading_of(f), reason="subject with subdivisions")
    h = headings.from_field(f, codes, kind)
    if h is None or not h.key:
        return Match("skipped", reason="no $a")
    own = _own_form(f, codes)

    # 1. Koha's own authorities: the heading, then the variants.
    local = koha.exact(kind, h.key, h.dates)
    if len({a.authid for a in local}) > 1:
        return Match("review", h, reason=f"{len(local)} Koha authorities fit: "
                     + "; ".join(f"{a.authid} {a.heading.heading}" for a in local[:4]))
    if not local:
        local = koha.variant(h)
        if len({a.authid for a in local}) > 1:
            return Match("review", h, reason="a variant of several Koha authorities: "
                         + "; ".join(f"{a.authid} {a.heading.heading}" for a in local[:4]))
    if local:
        return Match("koha", h, _koha_form(local[0], codes), authid=local[0].authid)

    # 2. static.db: the heading (with the people that share the name), then
    #    the variants.
    if static is not None:
        rows = [r for r in static.exact(kind, h.key) if dates_fit(h.dates, r.dates)]
        if rows:
            if not h.dates and kind == "personal" and date_groups([r.dates for r in rows]) > 1:
                return Match("review", h, reason="several people with this name: "
                             + "; ".join(sorted({r.heading for r in rows})[:4]))
            best = rows[0]
            return _from_static(h, best, _with_dates(own, best.dates) if kind == "personal" else own, koha, codes)
        rows = static.variant(h)
        if rows:
            best = rows[0]
            if len({r.key for r in rows if r.tier == best.tier}) > 1:
                return Match("review", h, reason="a variant of several headings: "
                             + "; ".join(sorted({r.heading for r in rows})[:4]))
            form = text_form(kind, best.heading, best.dates)
            if form is None:
                return Match("review", h, static=best, reason=f"variant of {best.heading} ({best.source})")
            return _from_static(h, best, form, koha, codes)

    # 3. Close forms (a typo): applied in fuzzy mode, proposed otherwise.
    close = koha.fuzzy(h, FUZZY_MIN)
    if close:
        s, a = close[0]
        if mode != "fuzzy":
            return Match("review", h, reason=f"close to Koha authority {a.authid} {a.heading.heading} ({s:.2f})")
        return Match("koha", h, _koha_form(a, codes), authid=a.authid, fuzzy=s)
    if static is not None:
        near = static.fuzzy(h, FUZZY_MIN)
        if near:
            s, r = near[0]
            form = text_form(kind, r.heading, r.dates)
            if mode != "fuzzy" or form is None:
                return Match("review", h, static=r, reason=f"close to {r.heading} ({r.source}, {s:.2f})")
            m = _from_static(h, r, form, koha, codes)
            m.fuzzy = s
            return m
    return Match("none", h)


def _from_static(h: Heading, row: StaticHeading, form: list[tuple[str, str]], koha: KohaIndex, codes: str) -> Match:
    """A static.db heading: linked to Koha's authority when Koha already
    has that form, else a new authority."""
    local = koha.exact(row.kind, row.key, row.dates or h.dates)
    if len({a.authid for a in local}) == 1:
        return Match("koha", h, _koha_form(local[0], codes), authid=local[0].authid, static=row)
    return Match("new", h, form, static=row)


def new_key(m: Match) -> tuple[str, str, str]:
    """One new authority per (kind, key, dates) in a job."""
    form = m.form
    dates = next((v for c, v in form if c == "d"), "") if m.heading.kind == "personal" else ""
    key = fold(" ".join(v for c, v in form if not (c == "d" and m.heading.kind == "personal")))
    return m.heading.kind, key, fold(dates)


def rewrite(f: marc.Field, m: Match, link: str) -> marc.Field:
    """The field with its heading in the authorised form and $9 LINK; the
    other subfields ($e, $4…) kept after it."""
    codes = kind_of(f)[1]
    rest = [(c, v) for c, v in f.subfields if c not in codes and c != "9"]
    subs = list(m.form) if m.form else _own_form(f, codes)
    if rest and subs and rest[0][0] == "e" and not subs[-1][1].endswith((",", "-")):
        subs[-1] = (subs[-1][0], subs[-1][1].rstrip(".") + ",")
    ind1 = f.ind1
    if f.tag[1:] == "00" and subs and subs[0][0] == "a":
        ind1 = "1" if "," in subs[0][1] else "0"
    return marc.Field(f.tag, ind1, f.ind2, subs + rest + [("9", link)])


# ----------------------------------------------------------------------
# A new authority record
# ----------------------------------------------------------------------
def authority_record(kind: str, form: list[tuple[str, str]], row: StaticHeading | None, preliminary: bool,
                     release: str = "", source_name: str = "") -> marc.Record:
    """MARC21 authority for Koha: 1XX from FORM, 4XX from the source's
    variants, 010/024 identifiers, 670 the source; a preliminary record
    (008/33 d) also carries a 667 note asking for review."""
    f008 = list(" " * 40)
    f008[0:6] = time.strftime("%y%m%d")
    # 06 no geographic subdivision, 09 established, 10/11 other rules and
    # system, 12/13 not a series, 14-16 main/subject/series use, 29 evaluated.
    for pos, value in zip(range(6, 18), "n||azznn" + ("ba" if kind in SUBJECT_KINDS else "aa") + "bn"):
        f008[pos] = value
    f008[29] = "a"
    f008[31] = "a"
    f008[32] = "a" if kind == "personal" else "n"
    f008[33] = "d" if preliminary else "c"
    f008[39] = "d"
    rec = marc.Record(leader="00000nz  a2200000n  4500")
    rec.fields.append(marc.Field("008", data="".join(f008)))
    if row is not None and row.lccn:
        rec.fields.append(marc.Field("010", " ", " ", [("a", row.lccn)]))
    if row is not None and row.uri:
        rec.fields.append(marc.Field("024", "7", " ", [("a", row.uri), ("2", "uri")]))
    rec.fields.append(marc.Field("040", " ", " ", [("b", "por"), ("c", "koha.nexus")]))
    tag = AUTH_TAG[kind]
    ind1 = {"personal": "1" if form and "," in form[0][1] else "0", "corporate": "2", "meeting": "2"}.get(kind, " ")
    main = [(c, v.rstrip(",").rstrip() if i == len(form) - 1 else v) for i, (c, v) in enumerate(form)]
    rec.fields.append(marc.Field(tag, ind1, " ", main))
    names = {fold(" ".join(v for _, v in main))}
    for v in (row.variants if row is not None else ()):
        sub = text_form(kind, v, "") or [("a", v)]
        if fold(v) not in names:
            names.add(fold(v))
            rec.fields.append(marc.Field("4" + tag[1:], ind1, " ", sub))
    if preliminary:
        rec.fields.append(marc.Field("667", " ", " ", [("a", "Preliminary record created by koha.nexus from "
                                                            "enrichment data: review the heading.")]))
    if row is not None:
        src = source_name or row.source
        cite = f"{src}, {row.source_id}" if row.source_id else src
        rec.fields.append(marc.Field("670", " ", " ", [("a", cite), ("b", "heading: " + row.heading)]))
    if release:
        rec.fields.append(marc.Field("670", " ", " ", [("a", f"koha.nexus enrichment database {release}")]))
    return rec
