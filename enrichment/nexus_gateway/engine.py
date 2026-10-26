"""One SRU search: static.db first, then live targets through learned.db.

    database "_union"   every source in static.db; live: every native target
    database "_union-aut"
                        the authority headings of static.db (authorities.py),
                        MARC21 authority records; never live
    database "<id>"     a target of targets.json: its static.db sources
                        (the target's "static" ids); live: that target, if
                        it is native
                        or a static.db source id with no target: static only

The order of the answer:
 1. static.db records matching the whole CQL query (and, or, not; title,
    author, ISBN/ISSN and keyword clauses), most complete first;
 2. only when static.db has no catalogue record (none at all, or only
    repository ones: see catalogue_record): for each live target, its answer
    in learned.db when fresh, else a live search (one clause of the query:
    the ISBN, else the title, author or keywords) within the reply budget.
    The live records come first, then static.db's repository records.

Records go out without 9XX fields and $9 subfields: those are the source
Koha's own items and authority ids, wrong in any other catalogue.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from nexus_enrich import marc, normalize
from nexus_enrich.static import StaticDB

from . import cql
from .authorities import AuthoritySearch
from .learned import Learned
from .targets import AUTH_UNION, UNION, Target

# A catalogue record has at least one of these. The institutional
# repository records harvested for UNESP, UFPR, UNIFESP, UnB and UFU are
# Dublin Core turned into MARC (024, 042, 245, 260, 520, 653, 720): no
# author heading, ISBN, extent, controlled subject or class number.
CATALOGUE_TAGS = ("020", "022", "082", "080", "100", "110", "111", "300",
                  "600", "610", "611", "630", "650", "651")
LEAF_CAP = 5000          # versions one clause may match before the rest are ignored
CHUNK = 900              # SQLite's bound-parameter budget, with room to spare
_ORDER = {"isbn": 0, "title": 1, "author": 2, "keywords": 3}


class UnknownDatabase(LookupError):
    """No target and no static.db source by that name (SRU diagnostic 235)."""


@dataclass
class Result:
    total: int
    records: list[marc.Record]
    origin: str = "static"                          # static | learned | live | none
    errors: dict[str, str] = field(default_factory=dict)


def clean(rec: marc.Record) -> marc.Record:
    out = marc.Record(rec.leader, [], rec.marc8_fallback)
    for f in rec.fields:
        if f.tag.startswith("9"):
            continue
        if f.is_control:
            out.fields.append(f)
        else:
            out.fields.append(marc.Field(f.tag, f.ind1, f.ind2, [(c, v) for c, v in f.subfields if c != "9"]))
    return out


def catalogue_record(rec: marc.Record) -> bool:
    """A library catalogue record, not a Dublin Core repository record."""
    return rec.has(*CATALOGUE_TAGS)


# ----------------------------------------------------------------------
# static.db
# ----------------------------------------------------------------------
def _words(text: str) -> list[str]:
    return re.findall(r"\w+", normalize.fold(text))


def _fts(column: str | None, words: list[str], any_word: bool) -> str:
    prefix = f"{column} : " if column else ""
    return (" OR " if any_word else " AND ").join(f'{prefix}"{w}"' for w in words)


def _idents(term: str) -> list[str]:
    out = [f for f in normalize.isbn_forms(term) if len(f) == 13]
    m = re.fullmatch(r"\s*(\d{4})-?(\d{3}[\dXx])\s*", term)
    if m:
        out.append((m.group(1) + m.group(2)).upper())
    digits = re.sub(r"[^\dXx]", "", term).upper()
    if digits and digits not in out:
        out.append(digits)
    return out


class Static:
    """static.db, reopened when the file is replaced (the monthly update
    swaps it in place). One connection per thread."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._local = threading.local()

    def _stamp(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        return st.st_ino, st.st_mtime_ns, st.st_size

    def db(self) -> StaticDB | None:
        stamp = self._stamp()
        held = getattr(self._local, "held", None)
        if held and held[0] == stamp:
            return held[1]
        if held:
            held[1].close()
            self._local.held = None
        if stamp is None:
            return None
        try:
            db = StaticDB(self.path)
        except sqlite3.Error:
            return None
        self._local.held = (stamp, db)
        return db

    # -- search ----------------------------------------------------------
    def _leaf(self, conn: sqlite3.Connection, c: cql.Clause) -> set[int]:
        any_word = c.relation == "any"
        if c.field == "all":
            return {r[0] for r in conn.execute("SELECT id FROM versions WHERE body IS NOT NULL ORDER BY id LIMIT ?",
                                               (LEAF_CAP,))}
        if c.field == "isbn":
            idents = _idents(c.term)
            if not idents:
                return set()
            return {r[0] for r in conn.execute(
                f"SELECT version_id FROM idents WHERE ident IN ({', '.join('?' * len(idents))}) LIMIT ?",
                (*idents, LEAF_CAP))}
        words = _words(c.term)
        if not words:
            return set()
        column = {"title": "title", "author": "author"}.get(c.field)
        try:
            return {r[0] for r in conn.execute("SELECT rowid FROM versions_fts WHERE versions_fts MATCH ? LIMIT ?",
                                               (_fts(column, words, any_word), LEAF_CAP))}
        except sqlite3.OperationalError:
            return set()

    def _ids(self, conn: sqlite3.Connection, node: cql.Node) -> set[int]:
        if isinstance(node, cql.Clause):
            return self._leaf(conn, node)
        left = self._ids(conn, node.left)
        if node.op == "and" and not left:
            return set()
        right = self._ids(conn, node.right)
        if node.op == "and":
            return left & right
        if node.op == "or":
            return left | right
        return left - right

    def search(self, node: cql.Node, sources: set[str] | None, start: int, maximum: int
               ) -> tuple[int, list[marc.Record]]:
        db = self.db()
        if db is None:
            return 0, []
        conn = db.conn
        ids = sorted(self._ids(conn, node))
        rows = []
        for i in range(0, len(ids), CHUNK):
            part = ids[i:i + CHUNK]
            rows += conn.execute(f"SELECT id, source, completeness, author != '' OR isbns != '' AS cat FROM versions "
                                 f"WHERE body IS NOT NULL AND id IN ({', '.join('?' * len(part))})", part).fetchall()
        if sources is not None:
            rows = [r for r in rows if r["source"] in sources]
        # Catalogue records (an author heading or an ISBN) before repository
        # ones, whose Dublin Core author is a 720 that main_author never reads.
        rows.sort(key=lambda r: (-r["cat"], -r["completeness"], r["id"]))
        page = [r["id"] for r in rows[start - 1:start - 1 + maximum]]
        records = []
        if page:
            bodies = {r["id"]: r["body"] for r in conn.execute(
                f"SELECT id, body FROM versions WHERE id IN ({', '.join('?' * len(page))})", page)}
            for vid in page:
                try:
                    records.append(marc.from_iso2709(db._decompress(bodies[vid])))
                except Exception:
                    continue
        return len(rows), records

    def authorities(self, node: cql.Node, start: int, maximum: int) -> tuple[int, list[marc.Record]]:
        db = self.db()
        if db is None:
            return 0, []
        return AuthoritySearch(db.conn, self.release(db)).search(node, start, maximum)

    def release(self, db: StaticDB) -> str:
        """The release static.db came from (static.release, written by the
        update next to it), else the day it was built."""
        try:
            name = json.loads((self.path.parent / "static.release").read_text(encoding="utf-8")).get("name", "")
        except (OSError, ValueError, AttributeError):
            name = ""
        if name:
            return name
        built = db.meta("built")
        return (built.decode() if isinstance(built, bytes) else (built or ""))[:10]

    def has_source(self, sid: str) -> bool:
        db = self.db()
        return db is not None and sid in db.sources

    def info(self) -> dict:
        db = self.db()
        if db is None:
            return {"present": False}
        built = db.meta("built")
        return {"present": True, "built": built.decode() if isinstance(built, bytes) else built,
                "sources": len(db.sources),
                "records": sum(r["records"] for r in db.sources.values())}


# ----------------------------------------------------------------------
# the live part
# ----------------------------------------------------------------------
def live_clause(node: cql.Node) -> cql.Clause | None:
    """The one clause a live target is asked: the ISBN when the query has
    one, else the title, author, keywords. OR and NOT keep their left side,
    since the target sees one term only."""
    found: list[cql.Clause] = []

    def walk(n: cql.Node) -> None:
        if isinstance(n, cql.Clause):
            if n.field != "all" and n.term:
                found.append(n)
        elif n.op == "and":
            walk(n.left)
            walk(n.right)
        else:
            walk(n.left)

    walk(node)
    return min(found, key=lambda c: _ORDER.get(c.field, 9)) if found else None


def query_key(clause: cql.Clause) -> str:
    if clause.field == "isbn":
        idents = _idents(clause.term)
        return "isbn:" + (idents[0] if idents else clause.term.strip())
    return f"{clause.field}:" + " ".join(_words(clause.term))


class Engine:
    def __init__(self, static: Static, learned: Learned | None, targets: dict[str, Target], runner=None):
        self.static = static
        self.learned = learned
        self.targets = targets
        self.runner = runner

    def is_live(self, t: Target) -> bool:
        """Searched live when static.db has nothing: z3950 and sru targets,
        zeus ones when the runner has a Zeus address and the pergamum one
        when it has a Pergamum address."""
        if t.live:
            return True
        hub = {"zeus": "zeus", "pergamum": "pergamum"}.get(t.kind)
        return hub is not None and t.status != "broken" and getattr(self.runner, hub, None) is not None

    def resolve(self, database: str) -> tuple[set[str] | None, list[Target]]:
        """(static sources or None for all, live targets) for a database name.
        _union never asks Zeus or Pergamum: one union search would send Zeus
        a dozen, and Pergamum a page of record fetches."""
        database = database.strip("/").lower()
        if database in ("", UNION):
            return None, [t for t in self.targets.values() if t.live]
        if database == AUTH_UNION:
            return None, []
        t = self.targets.get(database)
        if t is not None:
            return set(t.static), [t] if self.is_live(t) else []
        if self.static.has_source(database):
            return {database}, []
        raise UnknownDatabase(database)

    def search(self, database: str, node: cql.Node, start: int, maximum: int) -> Result:
        sources, live = self.resolve(database)
        if database.strip("/").lower() == AUTH_UNION:
            total, records = self.static.authorities(node, start, maximum)
            return Result(total, [clean(r) for r in records], "static" if total else "none")
        total, records = self.static.search(node, sources, start, maximum)
        if total:
            # The first page is sorted most complete first: a catalogue
            # record anywhere in the hits shows on it.
            first = records if start == 1 else self.static.search(node, sources, 1, maximum)[1]
            if any(catalogue_record(r) for r in first):
                return Result(total, [clean(r) for r in records], "static")
        clause = live_clause(node)
        if not live or clause is None or self.learned is None:
            return Result(total, [clean(r) for r in records], "static" if total else "none")
        unique, errors, origin = self._live(live, clause)
        if not unique:
            return Result(total, [clean(r) for r in records], "static" if total else "none", errors)
        # live records first, then static.db's repository records
        page = unique[start - 1:start - 1 + maximum]
        if len(page) < maximum and total:
            skip = max(0, start - 1 - len(unique))
            page += self.static.search(node, sources, skip + 1, maximum - len(page))[1]
        return Result(len(unique) + total, [clean(r) for r in page], origin, errors)

    def _live(self, live: list[Target], clause: cql.Clause) -> tuple[list[marc.Record], dict[str, str], str]:
        """The live targets' records for one clause, without repeats: from
        learned.db when fresh, else searched within the reply budget."""
        qkey = query_key(clause)
        pooled: list[marc.Record] = []
        errors: dict[str, str] = {}
        origin = "learned"
        ask = []
        for t in live:
            got = self.learned.get(t.id, qkey)
            if got is None:
                ask.append(t)
                continue
            _total, recs, error = got
            if error:
                errors[t.id] = error
            pooled += recs
        if ask and self.runner is not None:
            origin = "live"
            for answer in self.runner.search(ask, clause.field, clause.term, qkey):
                if answer.error:
                    errors[answer.target] = answer.error
                pooled += answer.records
        seen, unique = set(), []
        for r in pooled:
            key = (r.control("001").strip(), normalize.title_full(r))
            if key[0] and key in seen:
                continue
            seen.add(key)
            unique.append(r)
        return unique, errors, origin
