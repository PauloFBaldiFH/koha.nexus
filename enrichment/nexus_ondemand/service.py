"""The on-demand service (plan section 2): the koha-nexus-ondemand unit.

It takes the on-demand jobs of jobs.db (origin "ondemand"; the batch
worker never takes them, nor this service a batch job), any number of
records (the whole catalogue too: it takes hours, record after record,
read from export.xml as it goes), or one typed query, and for each record:

1. asks the direct servers (dispatch.py) unless this round was already
   asked: a job is asked again only by "Search more servers" (a new
   round, the servers already asked passed over) and never by a change
   of donor;
2. keeps every record found under jobs/ID/candidates/SEQ/ (index.json
   says where each came from), and what each server did in od_attempts;
3. merges (nexus_enrich.merge, unchanged rules) the best record of each
   server, with the donors the librarian chose (od_choices) first for
   their field groups, into the job's item row, as the batch worker does.

Then the job is "ready" with the same report, chunks, Apply and Revert as
a batch job. A typed query (no local record) keeps its records as
candidates to import as new; nothing is merged.

A job stopped half way (the machine shut down) goes on from its last
record when the service starts again. Progress goes to
ondemand-status.json after every server event. The unit
needs no port: requests come in through jobs.db. It exits after IDLE
seconds with nothing to do (the installer starts it for each request).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from nexus_enrich import marc
from nexus_enrich.marc import Field
from nexus_enrich.merge import Candidate, Policy, enrich, rank
from nexus_gateway.learned import Learned
from nexus_jobs import report
from nexus_jobs.apply import record_xml
from nexus_jobs.store import Job, Store
from nexus_jobs.worker import biblionumber, count_records, item_row, title

from . import plan, targets
from .config import Settings as Config
from .dispatch import Dispatcher, Result, static_candidates
from .health import Health
from .limits import Limiter

log = logging.getLogger("nexus_ondemand.service")

IDLE = 300.0
POLL = 2.0


class JobError(Exception):
    """The job cannot run (its records are missing or unreadable)."""


@dataclass
class Settings:
    state: Path
    static_db: Path
    learned_db: Path | None = None
    idle: float = IDLE
    poll: float = POLL
    pause_poll: float = 10.0
    chunk: int = 500

    @property
    def jobs_db(self) -> Path:
        return self.state / "jobs.db"

    @property
    def status_file(self) -> Path:
        return self.state / "ondemand-status.json"

    def job_dir(self, job_id: int) -> Path:
        return self.state / "jobs" / str(job_id)

    @classmethod
    def from_env(cls, env=os.environ) -> "Settings":
        state = Path(env.get("NEXUS_JOBS_STATE") or "/var/lib/koha-nexus-enrich")
        learned = env.get("NEXUS_GATEWAY_LEARNED_DB")
        return cls(state, Path(env.get("NEXUS_GATEWAY_STATIC_DB") or state / "static.db"),
                   Path(learned) if learned else state / "learned.db")


# ----------------------------------------------------------------------
# Status file
# ----------------------------------------------------------------------

class Status:
    """ondemand-status.json: the job, the record being searched, and each
    server's state for it (waiting, searching, n record(s), no record,
    down / skipped: why)."""

    def __init__(self, path: Path, catalog: targets.Catalog):
        self.path, self.catalog = path, catalog
        self.data: dict = {"state": "idle"}

    def write(self) -> None:
        self.data["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = self.path.with_suffix(".part")
        try:
            tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:                      # progress is a convenience: never stop a search on it
            log.warning("status not written: %s", exc)

    def job(self, job: Job, total: int, done: int, state: str = "matching") -> None:
        self.data = {"job": job.id, "state": state, "round": job.rounds, "total": total, "done": done,
                     "record": None, "servers": {}, "found": 0, "network": []}
        self.write()

    def record(self, seq: int, rec: marc.Record | None, label: str) -> None:
        self.data.update(record={"seq": seq, "biblionumber": biblionumber(rec) if rec is not None else None,
                                 "title": title(rec) if rec is not None else label},
                         servers={}, found=0)
        self.write()

    def _server(self, tid: str) -> dict:
        servers = self.data.setdefault("servers", {})
        if tid not in servers:
            t = self.catalog.targets.get(tid)
            servers[tid] = {"name": t.name if t else tid, "country": t.country if t else "", "state": "waiting",
                            "ms": 0, "hits": 0}
        return servers[tid]

    def event(self, ev: dict) -> None:
        kind = ev.get("type")
        if kind == "wave":
            for tid in ev["targets"]:
                self._server(tid)["state"] = "searching"
        elif kind == "attempt":
            s = self._server(ev["target"])
            outcome = ev["outcome"]
            s.update(ms=ev["ms"], hits=ev["hits"], address=ev["address"])
            if outcome in ("found", "cached") and ev["records"]:
                s["state"] = f"{ev['records']} record(s)"
                self.data["found"] = self.data.get("found", 0) + ev["records"]
            elif outcome in ("found", "none", "cached"):
                s["state"] = "no record"
            elif s["state"] in ("waiting", "searching") or outcome == "error":
                s["state"] = f"{'down' if outcome == 'error' else 'skipped'}: {ev['detail']}"[:200]
        elif kind == "static":
            self.data["found"] = self.data.get("found", 0) + ev["found"]
        elif kind == "done":
            self.data["network"] = sorted(set(self.data.get("network", [])) | set(ev.get("network") or []))
        self.write()


# ----------------------------------------------------------------------
# Candidates kept on disk
# ----------------------------------------------------------------------

def _cand_dir(settings: Settings, job_id: int, seq: int) -> Path:
    return settings.job_dir(job_id) / "candidates" / str(seq)


def save_found(settings: Settings, job_id: int, seq: int, rnd: int, res: Result) -> None:
    folder = _cand_dir(settings, job_id, seq)
    folder.mkdir(parents=True, exist_ok=True)
    index_file = folder / "index.json"
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.is_file() else []
    for f in res.found:
        name = f"{len(index) + 1}.mrc"
        (folder / name).write_bytes(marc.to_iso2709(f.record))
        index.append({"file": name, "source": f.source, "weight": f.weight, "step": f.step, "round": rnd,
                      "remote_id": f.remote_id or f.record.control("001"), "brazilian": f.brazilian})
    tmp = index_file.with_suffix(".part")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, index_file)


def load_found(settings: Settings, job_id: int, seq: int) -> list[Candidate]:
    folder = _cand_dir(settings, job_id, seq)
    index_file = folder / "index.json"
    if not index_file.is_file():
        return []
    out = []
    for entry in json.loads(index_file.read_text(encoding="utf-8")):
        try:
            rec = marc.from_iso2709((folder / entry["file"]).read_bytes())
        except (OSError, marc.RecordError, ValueError):
            continue
        out.append(Candidate(rec, entry["source"], entry.get("remote_id", ""), entry.get("weight", 0.5),
                             entry.get("brazilian", False)))
    return out


def best_per_source(local: marc.Record, cands: list[Candidate]) -> list[Candidate]:
    """Plan 8.2: each server's best record only, so one server cannot
    outvote the others with its duplicates."""
    seen, out = set(), []
    for s in rank(local, cands):
        if s.candidate.source not in seen:
            seen.add(s.candidate.source)
            out.append(s.candidate)
    return out


LOCAL_TAGS = re.compile(r"^9")          # 9XX: the donor's own local data (Koha's 942/952/999...)


def import_file(settings: Settings, store: Store, job_id: int, seq: int, n: int, out: Path) -> dict:
    """The Nth record found for a typed query (as `show` lists them, from
    1) as MARCXML for Koha's staged import, as a new record: the donor's
    local 9XX fields left out, an 883 saying where it came from."""
    job = store.job(job_id)
    if job.origin != "ondemand" or not job.query:
        raise JobError(f"job {job_id} is not an on-demand query")
    cands = load_found(settings, job_id, seq)
    if not 1 <= n <= len(cands):
        raise JobError(f"job {job_id} has no record {n} for query {seq}")
    c = cands[n - 1]
    rec = c.record.copy()
    rec.fields = [f for f in rec.fields if not LOCAL_TAGS.match(f.tag)]
    prov = [("a", "koha.nexus on-demand"), ("d", time.strftime("%Y%m%d")), ("q", c.source)]
    if c.remote_id:
        prov.append(("w", c.remote_id))
    rec.add_field(Field("883", "0", " ", prov))
    out.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<collection xmlns="http://www.loc.gov/MARC21/slim">\n'
                   + record_xml(rec) + "</collection>\n", encoding="utf-8")
    return {"file": str(out), "source": c.source, "remote_id": c.remote_id, "title": title(rec)}


# ----------------------------------------------------------------------
# One job
# ----------------------------------------------------------------------

def _count(settings: Settings, job: Job) -> int:
    """How many records the job has (1 for a typed query)."""
    if job.query:
        try:
            json.loads(job.query)
        except ValueError as exc:
            raise JobError(f"the typed query is not readable: {exc}") from exc
        return 1
    export = settings.job_dir(job.id) / "export.xml"
    if not export.is_file():
        raise JobError("export.xml is missing")
    return count_records(export)


def _records(settings: Settings, job: Job):
    """(record, typed query) one at a time: the exported records, read as
    they are searched (a whole catalogue never sits in memory), or the
    typed query."""
    if job.query:
        yield None, json.loads(job.query)
        return
    with open(settings.job_dir(job.id) / "export.xml", "rb") as fh:
        for rec in marc.iter_xml(fh):
            yield rec, {}


def _steps(rec: marc.Record | None, query: dict) -> list[plan.Step]:
    if rec is not None:
        return plan.for_record(rec)
    year = query.get("year")
    return plan.for_query(isbn=str(query.get("isbn") or ""), title=str(query.get("title") or ""),
                          author=str(query.get("author") or ""),
                          year=int(year) if str(year or "").isdigit() else None)


def _query_row(query: dict, cands: list[Candidate]) -> dict:
    """A typed query's item: its records, to import as new (no merge)."""
    label = " / ".join(str(query.get(k)) for k in ("isbn", "title", "author") if query.get(k))
    found = [{"source": c.source, "remote_id": c.remote_id, "title": title(c.record),
              "isbn": next((v for f in c.record.get_fields("020") for v in f.get_all("a")), "")}
             for c in cands]
    return {"biblionumber": None, "f005": "", "title": label[:200], "status": "found" if cands else "no-match",
            "m0": 0, "m1": 0, "w": 0, "r": 0, "pointers": 0, "before": None, "after": None, "other": None,
            "detail": json.dumps({"query": query, "found": found}, ensure_ascii=False)}


async def process(store: Store, job: Job, settings: Settings, dispatcher: Dispatcher, status: Status) -> str:
    """Search, keep and merge every record of JOB; returns its state when
    it stopped. A job found "matching" (the service stopped half way) goes
    on after its last finished record; one "exported" (new, Search more
    servers or a new donor) goes through all of them, asking the servers
    only for records not asked in this round."""
    job = store.job(job.id)
    try:
        total = _count(settings, job)
    except (JobError, OSError, marc.RecordError, ValueError) as exc:
        store.set(job.id, state="failed", error=str(exc)[:500])
        return "failed"
    start = job.done if job.state == "matching" else 0
    store.set(job.id, state="matching", total=total, done=start)
    job = store.job(job.id)
    status.job(job, total, start)
    for seq, (rec, query) in enumerate(_records(settings, job), 1):
        if seq <= start:
            continue
        while (settings.state / "pause").exists() and store.job(job.id).state == "matching":
            status.data["paused"] = True             # the tray's or the panel's Pause: wait between records
            status.write()
            await asyncio.sleep(settings.pause_poll)
        status.data["paused"] = False
        if store.job(job.id).state != "matching":
            return store.job(job.id).state           # cancelled from the panel
        status.record(seq, rec, query.get("title") or query.get("isbn") or "")
        try:
            if not store.attempts(job.id, seq, job.rounds):
                res = await dispatcher.run(rec, _steps(rec, query), exclude=store.asked(job.id, seq))
                store.add_attempts(job.id, seq, job.rounds, res.attempts)
                save_found(settings, job.id, seq, job.rounds, res)
            cands = load_found(settings, job.id, seq)
            if rec is None:
                row = _query_row(query, cands)
            else:
                bib = biblionumber(rec)
                donors = store.choices(job.id, bib) if bib is not None else {}
                row = item_row(rec, enrich(rec, best_per_source(rec, cands), Policy(donors=donors)))
        except Exception as exc:                     # one bad record never stops the job
            log.exception("job %s record %s", job.id, seq)
            row = {"biblionumber": biblionumber(rec) if rec is not None else None,
                   "f005": rec.control("005") if rec is not None else "", "title": title(rec) if rec else "",
                   "status": "error", "m0": 0, "m1": 0, "w": 0, "r": 0, "pointers": 0,
                   "detail": json.dumps({"error": f"{type(exc).__name__}: {exc}"[:300]}), "before": None,
                   "after": None, "other": None}
        row.update(job_id=job.id, seq=seq)
        store.put_items([row])
        store.set(job.id, done=seq)
        status.data["done"] = seq
        status.write()
    store.make_chunks(job.id, settings.chunk)
    report.write(store, job.id, settings.job_dir(job.id))
    store.set(job.id, state="ready", total=total, done=total)
    status.data.update(state="ready", record=None)
    status.write()
    return "ready"


# ----------------------------------------------------------------------
# The unit
# ----------------------------------------------------------------------

def build(settings: Settings, config: Config, catalog: targets.Catalog | None = None, on_event=None,
          opener=None) -> tuple[Dispatcher, Health]:
    catalog = catalog or targets.load(config.direct_list)
    health = Health(config.health_db)
    health.check_list(catalog.sha256)
    learned = None
    if settings.learned_db is not None and settings.learned_db.parent.is_dir():
        learned = Learned(settings.learned_db)
    static = static_candidates(settings.static_db) if config.static else None
    kw = {"opener": opener} if opener is not None else {}
    d = Dispatcher(catalog, health, Limiter(store=health), learned=learned, static=static, on_event=on_event, **kw)
    d.settings.static = config.static
    return d, health


async def serve(settings: Settings, config: Config, *, once: int | None = None, catalog=None, opener=None,
                clock=time.monotonic) -> int:
    """Run every waiting on-demand job (only job ONCE when given); wait for
    more until IDLE seconds pass with none. Returns how many ran."""
    catalog = catalog or targets.load(config.direct_list)
    status = Status(settings.status_file, catalog)
    dispatcher, health = build(settings, config, catalog, status.event, opener)
    store = Store(settings.jobs_db)
    n = 0
    try:
        idle_since = clock()
        while True:
            if once is not None:
                job = store.job(once)
                if job.origin != "ondemand" or job.state not in ("exported", "matching"):
                    break
            else:
                job = store.next_job("ondemand")
            if job is not None:
                try:
                    await process(store, job, settings, dispatcher, status)
                except Exception as exc:
                    log.exception("job %s", job.id)
                    store.set(job.id, state="failed", error=f"{type(exc).__name__}: {exc}"[:500])
                n += 1
                idle_since = clock()
                if once is not None:
                    break
                continue
            if clock() - idle_since >= settings.idle:
                break
            await asyncio.sleep(settings.poll)
    finally:
        store.close()
        health.close()
        status.data = {"state": "idle"}
        status.write()
    return n
