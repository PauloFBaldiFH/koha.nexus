"""Build static.db from the harvest dumps.

    sources.json ─▶ readers (streaming) ─▶ keys + cluster ─▶ static.db
                                         └▶ headings ───────▶ auth_headings

Two passes over the sources: the first reads up to `sample` records to
train a zstd dictionary (MARC records share most of their bytes, so a
dictionary makes each compressed body several times smaller); the second
loads everything. Bibliographic records become `versions` (body NULL for
a source in "pointer" mode); authority records (leader/06 z) become
`auth_headings`; the headings of bibliographic records are gathered into
`auth_headings` too (preliminary, with an occurrence count) unless the
source says "headings": false.

Clustering: a version joins a cluster that shares one of its ISBN-13s
only when the folded main titles are at least 0.60 alike, so a reused
ISBN starts a second cluster; a version without ISBN joins the cluster of
its work key. The same record twice in one source (same remote id) keeps
the last one read; an identical record from a mirror source in the same
cluster is still stored (it is another source's version) but counted.
"""

from __future__ import annotations

import glob
import hashlib
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from nexus_enrich import classify, edition, headings, marc, normalize
from nexus_enrich.static import SCHEMA, SCHEMA_VERSION

from . import readers

ISBN_TITLE_GATE = 0.60
DICT_SIZE = 112_640          # zstd's usual dictionary size
LEVEL = 19                   # no --long / --ultra: decompression stays small


@dataclass
class SourceConfig:
    id: str
    paths: list[str]
    name: str = ""
    format: str = "auto"
    mode: str = "full"                  # "full" or "pointer"
    brazilian: bool = False
    weight: float = 0.5
    headings: bool = True
    source_field: str = ""              # JSON key naming the source per line

    @classmethod
    def from_dict(cls, d: dict) -> "SourceConfig":
        if not d.get("id"):
            raise ValueError("every source needs an id")
        paths = d.get("paths") or ([d["path"]] if d.get("path") else [])
        if not paths:
            raise ValueError(f"source {d['id']}: no paths")
        mode = d.get("mode", "full")
        if mode not in ("full", "pointer"):
            raise ValueError(f"source {d['id']}: mode must be full or pointer, not {mode!r}")
        return cls(id=d["id"], paths=list(paths), name=d.get("name", ""), format=d.get("format", "auto"),
                   mode=mode, brazilian=bool(d.get("brazilian", False)), weight=float(d.get("weight", 0.5)),
                   headings=bool(d.get("headings", True)), source_field=d.get("source_field", ""))

    def files(self, base: Path) -> list[Path]:
        out: list[Path] = []
        for pattern in self.paths:
            p = Path(pattern)
            if not p.is_absolute():
                p = base / p
            matches = sorted(glob.glob(str(p)))
            out.extend(Path(m) for m in matches)
        return out


def load_config(path: Path) -> list[SourceConfig]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = [SourceConfig.from_dict(d) for d in data.get("sources", [])]
    ids = [s.id for s in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("source ids must be unique")
    return sources


@dataclass
class Report:
    started: str = ""
    finished: str = ""
    sources: dict = field(default_factory=dict)
    versions: int = 0
    clusters: int = 0
    pointers: int = 0
    authorities: int = 0
    headings: int = 0
    duplicates: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)       # first 200
    error_count: int = 0
    marc8_fallback: int = 0
    dictionary: bool = False

    def error(self, where: str, msg: str) -> None:
        self.error_count += 1
        if len(self.errors) < 200:
            self.errors.append(f"{where}: {msg}")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class Builder:
    def __init__(self, out: Path, sources: list[SourceConfig], base: Path, sample: int = 2000):
        self.out = out
        self.sources = sources
        self.base = base
        self.sample = sample
        self.report = Report()
        self._cctx = None

    # -- pass 1 ------------------------------------------------------------
    def _train(self) -> bytes:
        samples: list[bytes] = []
        for src in self.sources:
            if src.mode != "full":
                continue
            for path in src.files(self.base):
                for item in readers.read(path, src.format, src.source_field):
                    if item.record is not None and not item.record.is_authority:
                        samples.append(marc.to_iso2709(item.record))
                    if len(samples) >= self.sample:
                        break
                if len(samples) >= self.sample:
                    break
        if len(samples) < 200:
            return b""
        import zstandard
        try:
            return zstandard.train_dictionary(DICT_SIZE, samples).as_bytes()
        except zstandard.ZstdError:
            return b""

    # -- pass 2 ------------------------------------------------------------
    def build(self) -> Report:
        import zstandard
        self.report.started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if self.out.exists():
            self.out.unlink()
        dict_bytes = self._train()
        self.report.dictionary = bool(dict_bytes)
        cdict = zstandard.ZstdCompressionDict(dict_bytes) if dict_bytes else None
        self._cctx = zstandard.ZstdCompressor(level=LEVEL, dict_data=cdict)

        conn = sqlite3.connect(self.out, isolation_level=None)
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.executescript(SCHEMA)
        conn.execute("BEGIN")
        for key, value in (("schema", SCHEMA_VERSION), ("zstd_dict", dict_bytes)):
            conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        n = 0
        t0 = time.monotonic()
        for src in self.sources:
            stats = self.report.sources.setdefault(src.id, {"files": 0, "records": 0, "pointers": 0,
                                                            "authorities": 0, "errors": 0})
            self._ensure_source(conn, src, src.id)
            files = src.files(self.base)
            if not files:
                self.report.error(src.id, "no file matches " + ", ".join(src.paths))
            for path in files:
                stats["files"] += 1
                for item in readers.read(path, src.format, src.source_field):
                    if item.record is None:
                        stats["errors"] += 1
                        self.report.error(f"{src.id} {path.name}", item.error)
                        continue
                    source_id = item.source or src.id
                    if source_id != src.id:
                        self._ensure_source(conn, src, source_id)
                    self._add(conn, src, source_id, item, stats)
                    n += 1
                    if n % 50_000 == 0:
                        conn.execute("COMMIT")
                        conn.execute("BEGIN")
                        _log(f"{n} records, {n / max(time.monotonic() - t0, 0.001):.0f}/s")
        self._finish(conn)
        conn.execute("COMMIT")
        conn.execute("VACUUM")
        conn.close()
        self.report.finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self.report

    def _ensure_source(self, conn, src: SourceConfig, source_id: str) -> None:
        conn.execute("INSERT OR IGNORE INTO sources (id, name, mode, brazilian, weight) VALUES (?, ?, ?, ?, ?)",
                     (source_id, src.name if source_id == src.id else source_id, src.mode, int(src.brazilian),
                      src.weight))

    def _add(self, conn, src: SourceConfig, source_id: str, item: readers.Item, stats: dict) -> None:
        rec = item.record
        if rec.marc8_fallback:
            self.report.marc8_fallback += 1
        if rec.is_authority:
            entry = headings.of_authority(rec)
            if entry is None:
                self.report.skipped += 1
                return
            self._put_heading(conn, entry.heading, source_id, preliminary=0, variants=entry.variants,
                              lccn=entry.lccn, uri=entry.uri, source_id=entry.source_id or item.remote_id)
            stats["authorities"] += 1
            self.report.authorities += 1
            return
        title = normalize.title_main(rec)
        if not title:
            self.report.skipped += 1
            self.report.error(source_id, f"{item.remote_id or '?'}: no title (245)")
            return
        remote = item.remote_id or hashlib.sha1(marc.to_iso2709(rec)).hexdigest()[:16]
        iso = marc.to_iso2709(rec)
        checksum = hashlib.sha1(iso).hexdigest()
        isbns = normalize.isbns13(rec)
        wkey = normalize.work_key(rec)
        cluster = self._cluster(conn, isbns, wkey, title)
        y, _ = normalize.year(rec)
        ed = edition.of(rec)
        body = None if src.mode == "pointer" else self._cctx.compress(iso)
        old = conn.execute("SELECT id, cluster_id, checksum FROM versions WHERE source = ? AND remote_id = ?",
                           (source_id, remote)).fetchone()
        if old is not None:
            conn.execute("DELETE FROM idents WHERE version_id = ?", (old[0],))
            conn.execute("DELETE FROM versions WHERE id = ?", (old[0],))
            self.report.versions -= 1
            if src.mode == "pointer":
                self.report.pointers -= 1
        dup = conn.execute("SELECT 1 FROM versions WHERE cluster_id = ? AND checksum = ? LIMIT 1",
                           (cluster, checksum)).fetchone()
        if dup:
            self.report.duplicates += 1
        vid = conn.execute(
            "INSERT INTO versions (cluster_id, source, remote_id, isbns, work_key, title, author, year, edition, "
            "publisher, lang, completeness, checksum, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cluster, source_id, remote, " ".join(isbns), wkey, normalize.title_full(rec),
             normalize.fold(normalize.main_author(rec)), y,
             "" if ed is None else json.dumps([ed.number, ed.revised, ed.other]),
             normalize.publisher(rec), normalize.language(rec), classify.completeness(rec), checksum,
             body)).lastrowid
        idents = isbns + normalize.issns(rec)
        conn.executemany("INSERT OR IGNORE INTO idents VALUES (?, ?)", [(i, vid) for i in idents])
        subjects = " ".join(f.text("abcdvxyz") for f in rec.get_fields(*headings.BIB_TAGS) if f.tag.startswith("6"))
        names = " ".join(f.text("abcdq") for f in rec.get_fields("100", "110", "111", "700", "710", "711"))
        # Contentless FTS keeps only the index. A replaced version's old
        # entry is left behind: every search joins versions by id, so it
        # matches nothing.
        conn.execute("INSERT INTO versions_fts (rowid, title, author, subjects) VALUES (?, ?, ?, ?)",
                     (vid, normalize.title_full(rec), normalize.fold(normalize.main_author(rec)) + " " +
                      normalize.fold(names), normalize.fold(subjects)))
        self.report.versions += 1
        stats["records"] += 1
        if src.mode == "pointer":
            self.report.pointers += 1
            stats["pointers"] += 1
        if src.headings:
            for h in headings.of_bib(rec):
                self._put_heading(conn, h, source_id, preliminary=1)

    def _cluster(self, conn, isbns: list[str], wkey: str, title: str) -> int:
        for isbn in isbns:
            for cid, ctitle in conn.execute("SELECT id, title FROM clusters WHERE isbn13 = ?", (isbn,)):
                if normalize.similarity(title, ctitle) >= ISBN_TITLE_GATE:
                    return cid
        if not isbns:
            row = conn.execute("SELECT id FROM clusters WHERE work_key = ? AND isbn13 IS NULL", (wkey,)).fetchone()
            if row:
                return row[0]
        self.report.clusters += 1
        return conn.execute("INSERT INTO clusters (isbn13, work_key, title) VALUES (?, ?, ?)",
                            (isbns[0] if isbns else None, wkey, title)).lastrowid

    def _put_heading(self, conn, h: headings.Heading, source: str, preliminary: int, variants=(), lccn="",
                     uri="", source_id="") -> None:
        if not h.key:
            return
        row = conn.execute("SELECT id, preliminary FROM auth_headings WHERE kind = ? AND key = ? AND dates = ? "
                           "AND thesaurus = ? AND source = ?", (h.kind, h.key, h.dates, h.thesaurus, source)).fetchone()
        if row is not None:
            if preliminary and row[1]:
                conn.execute("UPDATE auth_headings SET occurrences = occurrences + 1 WHERE id = ?", (row[0],))
                return
            if preliminary:
                return          # an authority record already established it
            # An authority record replaces the heading gathered from bibs.
            conn.execute("DELETE FROM auth_headings WHERE id = ?", (row[0],))
            self.report.headings -= 1
        hid = conn.execute(
            "INSERT INTO auth_headings (kind, heading, key, dates, thesaurus, variants, source, source_id, lccn, uri, "
            "preliminary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (h.kind, h.heading, h.key, h.dates, h.thesaurus, "\n".join(variants), source, source_id, lccn, uri,
             preliminary)).lastrowid
        conn.execute("INSERT INTO auth_fts (rowid, heading, variants) VALUES (?, ?, ?)",
                     (hid, h.heading, "\n".join(variants)))
        self.report.headings += 1

    def _finish(self, conn) -> None:
        for sid, in conn.execute("SELECT id FROM sources").fetchall():
            conn.execute("UPDATE sources SET records = (SELECT COUNT(*) FROM versions WHERE source = ?), "
                         "headings = (SELECT COUNT(*) FROM auth_headings WHERE source = ?) WHERE id = ?",
                         (sid, sid, sid))
        self.report.clusters = conn.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)",
                     (datetime.now(timezone.utc).isoformat(timespec="seconds"),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('counts', ?)", (json.dumps({
            "versions": self.report.versions, "pointers": self.report.pointers, "clusters": self.report.clusters,
            "headings": self.report.headings, "authorities": self.report.authorities}),))
        conn.execute("INSERT INTO versions_fts (versions_fts) VALUES ('optimize')")
        conn.execute("INSERT INTO auth_fts (auth_fts) VALUES ('optimize')")
