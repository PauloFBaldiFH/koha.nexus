"""The batch worker: reads a job's exported records 20 at a time, matches
each against static.db, records the result, sleeps, and checkpoints.

It runs as the koha-nexus-enrich unit (CPUQuota=25%, MemoryMax=256M, idle
I/O, no access to Koha's database) and backs off on its own:
- a `pause` file in the state folder (the tray or the panel writes it)
  stops it between batches until the file is gone;
- while the load average is above the number of CPUs it waits;
- a job cancelled from the panel stops at the next batch.

Progress goes to status.json after every batch, for the panel and the tray.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from nexus_enrich import authority, marc
from nexus_enrich.merge import Policy, enrich
from nexus_enrich.static import StaticDB

from . import report
from .store import Job, Store, pack


@dataclass
class Settings:
    state: Path
    static_db: Path
    batch: int = 20
    pause: float = 1.5                 # seconds between batches
    chunk: int = 500                   # records per Koha batch at Apply
    max_load: float = 0.0              # 0: the number of CPUs
    policy: Policy = field(default_factory=Policy)

    @property
    def jobs_db(self) -> Path:
        return self.state / "jobs.db"

    @property
    def pause_file(self) -> Path:
        return self.state / "pause"

    @property
    def status_file(self) -> Path:
        return self.state / "status.json"

    def job_dir(self, job_id: int) -> Path:
        return self.state / "jobs" / str(job_id)


def biblionumber(rec: marc.Record) -> int | None:
    """Koha's biblionumber: 999 $c (MARC21), else 001 when it is a number."""
    for f in rec.get_fields("999"):
        v = f.get("c").strip()
        if v.isdigit():
            return int(v)
    v = rec.control("001").strip()
    return int(v) if v.isdigit() else None


def title(rec: marc.Record) -> str:
    f = rec.first("245")
    return (f.text("abnp") if f is not None else "")[:200]


def write_status(settings: Settings, **values) -> None:
    values.setdefault("time", time.strftime("%Y-%m-%d %H:%M:%S"))
    tmp = settings.status_file.with_suffix(".part")
    tmp.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, settings.status_file)


def _busy(settings: Settings) -> bool:
    try:
        load = os.getloadavg()[0]
    except OSError:
        return False
    limit = settings.max_load or float(os.cpu_count() or 1)
    return load > limit


def match_one(db: StaticDB, rec: marc.Record, policy: Policy) -> dict:
    """The item row of one record (without job_id and seq)."""
    cands, pointers = db.candidates_for(rec)
    return item_row(rec, enrich(rec, cands, policy), pointers)


def item_row(rec: marc.Record, res, pointers=()) -> dict:
    """The item row of one record and its merge result (without job_id and seq)."""
    row = {"biblionumber": biblionumber(rec), "f005": rec.control("005"), "title": title(rec),
           "m0": 0, "m1": 0, "w": 0, "r": 0, "pointers": len(pointers), "before": None, "after": None,
           "other": None}
    counts = res.counts
    row.update(status=res.status, m0=counts["M0"], m1=counts["M1"], w=counts["W"],
               r=sum(1 for s in res.candidates if s.match.cls == "R"))
    info = {
        "additions": [{"group": a.group, "tag": a.field.tag, "text": report.field_text(a.field),
                       "source": a.source, "remote_id": a.remote_id, "cls": a.cls, "score": round(a.score, 3)}
                      for a in res.additions],
        "review": res.review,
        "candidates": [{"source": s.candidate.source, "remote_id": s.candidate.remote_id, "cls": s.match.cls,
                        "score": round(s.match.score, 3), "reasons": list(s.match.reasons)}
                       for s in res.candidates[:5]],
        "pointers": [{"source": p.source, "remote_id": p.remote_id, "title": p.title} for p in pointers[:5]],
    }
    if res.replacement is not None:
        info["replacement"] = {"source": res.replacement.candidate.source,
                               "remote_id": res.replacement.candidate.remote_id}
    row["detail"] = json.dumps(info, ensure_ascii=False)
    if res.status == "enriched":
        row["before"], row["after"] = pack(rec), pack(res.record)
    elif res.status == "review":
        row["before"] = pack(rec)
        other = res.replacement or next((s for s in res.candidates), None)
        if other is not None:
            row["other"] = pack(other.candidate.record)
    return row


class AuthMatcher:
    """The headings of one record against Koha's authorities (exported with
    the job) and static.db's headings. Item columns for an authority job:
    m0 links to Koha authorities, m1 links to new authorities, w headings
    put in the authorised form, r headings sent to review."""

    def __init__(self, store: Store, job: Job, db: StaticDB, koha: authority.KohaIndex, release: str):
        self.store, self.job, self.koha, self.release = store, job, koha, release
        self.static = authority.StaticHeadings(db.conn)
        self.mode = job.mode or "exact"

    def _new(self, m: authority.Match) -> int:
        kind, key, dates = authority.new_key(m)
        row = m.static
        preliminary = bool(m.fuzzy) or row is None or bool(row.preliminary)
        src = self.static.sources.get(row.source) if row is not None else None
        rec = authority.authority_record(kind, m.form, row, preliminary, self.release,
                                         src["name"] if src is not None else "")
        main = rec.first(authority.AUTH_TAG[kind])
        return self.store.new_authority(self.job.id, kind, key, dates, main.text(), row.source if row else "",
                                        preliminary, m.fuzzy, pack(rec))

    def __call__(self, rec: marc.Record) -> dict:
        row = {"biblionumber": biblionumber(rec), "f005": rec.control("005"), "title": title(rec),
               "m0": 0, "m1": 0, "w": 0, "r": 0, "pointers": 0, "before": None, "after": None, "other": None}
        after = rec.copy()
        found, review = [], []
        for i, f in enumerate(after.fields):
            if authority.kind_of(f) is None:
                continue
            m = authority.match_field(f, self.koha, self.static, self.mode)
            entry = {"tag": f.tag, "before": report.field_text(f), "action": m.action, "reason": m.reason}
            if m.static is not None:
                entry["source"] = m.static.source
            if m.fuzzy:
                entry["fuzzy"] = round(m.fuzzy, 3)
            if m.action == "koha":
                after.fields[i] = authority.rewrite(f, m, str(m.authid))
                entry["authid"] = m.authid
                row["m0"] += 1
            elif m.action == "new":
                nid = self._new(m)
                after.fields[i] = authority.rewrite(f, m, f"{authority.NEW_PREFIX}{nid}")
                entry["new"] = nid
                row["m1"] += 1
            elif m.action == "review":
                row["r"] += 1
                review.append(f"{f.tag} {m.heading.heading if m.heading else ''}: {m.reason}")
            if m.action in ("koha", "new"):
                entry["after"] = report.field_text(after.fields[i])
                if m.standardized:
                    row["w"] += 1
                    entry["standardized"] = True
            found.append(entry)
        changed = row["m0"] + row["m1"]
        row["status"] = "enriched" if changed else "review" if review else "unchanged"
        row["detail"] = json.dumps({"headings": found, "review": review}, ensure_ascii=False)
        if changed:
            row["before"], row["after"] = pack(rec), pack(after)
        elif review:
            row["before"] = pack(rec)
        return row


def count_records(path: Path) -> int:
    n = 0
    with open(path, "rb") as fh:
        for _ in marc.iter_xml(fh):
            n += 1
    return n


def process(store: Store, job: Job, settings: Settings, sleep=time.sleep) -> str:
    """Match one job from its checkpoint to the end (or to a pause or a
    cancel). Returns the job's state when it stopped."""
    job = store.job(job.id)
    export = settings.job_dir(job.id) / "export.xml"
    if not export.is_file():
        store.set(job.id, state="failed", error="export.xml is missing")
        return "failed"
    db = StaticDB(settings.static_db)
    try:
        release = ""
        rel_file = settings.state / "static.release"
        if rel_file.is_file():
            try:
                release = json.loads(rel_file.read_text(encoding="utf-8")).get("name", "")
            except ValueError:
                pass
        if job.state == "exported":
            store.set(job.id, state="matching", total=count_records(export), release=release)
        job = store.job(job.id)
        if job.kind == "auth":
            koha = authority.KohaIndex.from_file(settings.job_dir(job.id) / "authorities.xml")
            matcher = AuthMatcher(store, job, db, koha, job.release)
        else:
            def matcher(rec):
                return match_one(db, rec, settings.policy)
        done = job.done
        pending: list[dict] = []
        status = dict(job=job.id, state="matching", total=job.total)

        def checkpoint(seq_done: int) -> str | None:
            store.put_items(pending)
            pending.clear()
            store.set(job.id, done=seq_done)
            write_status(settings, **status, done=seq_done, paused=False)
            while True:
                state = store.job(job.id).state
                if state != "matching":
                    return state                       # cancelled from the panel
                if settings.pause_file.exists():
                    write_status(settings, **status, done=seq_done, paused=True, why="pause file")
                    sleep(10)
                    continue
                if _busy(settings):
                    write_status(settings, **status, done=seq_done, paused=True, why="machine busy")
                    sleep(30)
                    continue
                break
            sleep(settings.pause)
            return None

        with open(export, "rb") as fh:
            seq = 0
            records = marc.iter_xml(fh)
            while True:
                try:
                    rec = next(records)
                except StopIteration:
                    break
                except Exception as exc:          # a broken record ends the readable part of the file
                    store.set(job.id, state="failed", error=f"export.xml unreadable after record {seq}: {exc}")
                    return "failed"
                seq += 1
                if seq <= done:
                    continue
                try:
                    row = matcher(rec)
                except Exception as exc:          # one bad record never stops the job
                    row = {"biblionumber": biblionumber(rec), "f005": rec.control("005"), "title": title(rec),
                           "status": "error", "m0": 0, "m1": 0, "w": 0, "r": 0, "pointers": 0,
                           "detail": json.dumps({"error": str(exc)[:300]}), "before": None, "after": None,
                           "other": None}
                row.update(job_id=job.id, seq=seq)
                pending.append(row)
                if len(pending) >= settings.batch:
                    stopped = checkpoint(seq)
                    if stopped:
                        return stopped
            if pending or seq > done:
                store.put_items(pending)
                pending.clear()
                store.set(job.id, done=seq)
        store.make_chunks(job.id, settings.chunk)
        report.write(store, job.id, settings.job_dir(job.id))
        store.set(job.id, state="ready", total=seq)
        write_status(settings, job=job.id, state="ready", total=seq, done=seq, paused=False)
        return "ready"
    finally:
        db.close()


def run(settings: Settings, once: bool = False, sleep=time.sleep) -> int:
    """Every job waiting for the worker, oldest first; then exit (the unit is
    started again when a job is queued)."""
    store = Store(settings.jobs_db)
    n = 0
    try:
        while True:
            job = store.next_job()
            if job is None:
                break
            if not settings.static_db.is_file():
                store.set(job.id, state="failed", error="static.db is not installed yet (enrich-update)")
                continue
            try:
                process(store, job, settings, sleep=sleep)
            except Exception as exc:
                store.set(job.id, state="failed", error=f"{type(exc).__name__}: {exc}"[:500])
            n += 1
            if once:
                break
    finally:
        store.close()
    write_status(settings, state="idle", paused=settings.pause_file.exists())
    return n
