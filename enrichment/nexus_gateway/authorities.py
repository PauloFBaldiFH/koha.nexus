"""Authority search for Koha's cataloguing screen: database _union-aut.

Koha's authority search (Cataloguing > a heading's Z39.50/SRU search)
sends its form fields through the row's "SRU search fields" mapping:

    bath.personalName="saramago"         a personal name
    bath.corporateName=... / bath.conferenceName=...
    bath.uniformTitle=...                a uniform title
    dc.subject="cegueira"                a topical, geographic or genre term
    dc.creator=... / bath.name=...       any name
    cql.serverChoice=... or a bare term  any heading

Each clause matches the words of a heading or of its variants (4XX) in
static.db's auth_headings, of the kinds its index names; and, or and not
combine them. The answer is ranked as the authority jobs rank a match
(nexus_enrich.authority): the Biblioteca Nacional first, then the
Brazilian catalogues, then the Library of Congress; established before
preliminary; then the most used. Subjects never come from LCSH.

Each heading goes out as a MARC21 authority record (1XX, 4XX variants,
010/024 identifiers, 670 source; 008/33 d and a 667 note when the heading
was only gathered from bibliographic records), ready for Koha's
authority editor. Koha's own authorities are searched by Koha itself.
"""

from __future__ import annotations

import re
import sqlite3

from nexus_enrich import marc, normalize
from nexus_enrich.authority import NAME_KINDS, SUBJECT_KINDS, StaticHeading, StaticHeadings, authority_record, \
    text_form

from . import cql

LEAF_CAP = 5000
CHUNK = 900
ALL_KINDS = (*NAME_KINDS, "uniform", *SUBJECT_KINDS)
# The last part of a CQL index, lowercased, to the kinds of heading it names.
KINDS = {
    "personalname": ("personal",), "authorpersonal": ("personal",),
    "corporatename": ("corporate",), "authorcorp": ("corporate",),
    "conferencename": ("meeting",), "meetingname": ("meeting",), "authormeetingcon": ("meeting",),
    "uniformtitle": ("uniform",), "title": ("uniform",),
    "subject": SUBJECT_KINDS, "subjectsubdiv": SUBJECT_KINDS, "topic": ("topical",), "topicalterm": ("topical",),
    "geographicname": ("geographic",), "geographic": ("geographic",), "genreform": ("genre",), "genre": ("genre",),
    **{k: NAME_KINDS for k in ("name", "creator", "author", "au", "nameany", "authorany", "contributor")},
}


def kinds_of(clause: cql.Clause) -> tuple[str, ...]:
    """The heading kinds a clause searches: by its index, any kind for a
    bare term or an index this list does not know."""
    return KINDS.get(clause.index.rsplit(".", 1)[-1].lower(), ALL_KINDS)


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", normalize.fold(text))


class AuthoritySearch:
    """Searches auth_headings on one static.db connection."""

    def __init__(self, conn: sqlite3.Connection, release: str = ""):
        self.conn = conn
        self.release = release
        self.heads = StaticHeadings(conn)

    def _leaf(self, c: cql.Clause) -> set[int]:
        kinds = kinds_of(c)
        marks = ", ".join("?" * len(kinds))
        if c.field == "all":
            return {r[0] for r in self.conn.execute(
                f"SELECT id FROM auth_headings WHERE kind IN ({marks}) ORDER BY id LIMIT ?", (*kinds, LEAF_CAP))}
        words = _words(c.term)
        if not words:
            return set()
        expr = (" OR " if c.relation == "any" else " AND ").join(f'"{w}"' for w in words)
        try:
            ids = [r[0] for r in self.conn.execute("SELECT rowid FROM auth_fts WHERE auth_fts MATCH ? ORDER BY rank LIMIT ?",
                                                   (expr, LEAF_CAP))]
        except sqlite3.OperationalError:
            return set()
        out: set[int] = set()
        for i in range(0, len(ids), CHUNK):
            part = ids[i:i + CHUNK]
            out |= {r[0] for r in self.conn.execute(
                f"SELECT id FROM auth_headings WHERE kind IN ({marks}) AND id IN ({', '.join('?' * len(part))})",
                (*kinds, *part))}
        return out

    def _ids(self, node: cql.Node) -> set[int]:
        if isinstance(node, cql.Clause):
            return self._leaf(node)
        left = self._ids(node.left)
        if node.op == "and" and not left:
            return set()
        right = self._ids(node.right)
        if node.op == "and":
            return left & right
        if node.op == "or":
            return left | right
        return left - right

    def _rows(self, ids: list[int]) -> list[StaticHeading]:
        rows: list[StaticHeading] = []
        for i in range(0, len(ids), CHUNK):
            part = ids[i:i + CHUNK]
            rows += self.heads._rows(f"SELECT * FROM auth_headings WHERE id IN ({', '.join('?' * len(part))})", part)
        return rows

    def search(self, node: cql.Node, start: int, maximum: int) -> tuple[int, list[marc.Record]]:
        try:
            ids = sorted(self._ids(node))
            rows = self._rows(ids)
        except sqlite3.OperationalError:             # a static.db from before the authority headings
            return 0, []
        exact = {normalize.fold(t) for t in _terms(node)}
        rows = [r for r in rows if r.kind not in SUBJECT_KINDS or (not r.thesaurus.startswith("lcsh") and r.tier != 2)]
        terms = [set(_words(t)) for t in _terms(node) if _words(t)]

        def relevance(r):
            key_tokens = set(_words(r.key))
            # Ignore punctuation and name inversion, but do not reward a
            # longer homonym as if it were the requested full name.
            token_match = any(key_tokens == term for term in terms)
            literal_match = bool({r.key, normalize.fold(r.heading)} & exact)
            return (not (literal_match or token_match), r.tier, r.preliminary,
                    not bool(r.dates), not bool(r.source_id or r.lccn),
                    len(key_tokens), -r.occurrences, r.id)

        rows.sort(key=relevance)
        page = rows[start - 1:start - 1 + maximum]
        return len(rows), [self.record(r) for r in page]

    def record(self, row: StaticHeading) -> marc.Record:
        form = text_form(row.kind, row.heading, row.dates) or [("a", row.heading)]
        src = self.heads.sources.get(row.source)
        return authority_record(row.kind, form, row, bool(row.preliminary), self.release,
                                src["name"] if src is not None else row.source)


def _terms(node: cql.Node) -> list[str]:
    if isinstance(node, cql.Clause):
        return [node.term] if node.field != "all" else []
    return _terms(node.left) + (_terms(node.right) if node.op != "not" else [])
