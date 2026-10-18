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

Big jobs (a whole catalogue) are what this is built for:
- PARALLEL records (default 4, KEI_ONDEMAND_PARALLEL 1-8) are searched at
  once; their rows are saved in the job's order, so "done" is always a
  run of finished records and a stop loses nothing. The limiter still
  holds every host to one session and its pace, and the dispatcher sends
  each record to the idle servers first, so more records at once means
  more servers busy, never one server asked harder;
- the merge runs in a thread, off the loop the searches wait on;
- when this machine's own network is down (no name lookup works and no
  server answered), the record is not saved as "nothing found": the job
  waits (30 s, doubling to 10 min) and asks again, so a night with the
  internet gone costs time, not thousands of empty results;
- ondemand-status.json is written at most once a second, with the records
  in flight, records per hour and the time left.

A job stopped half way (the machine shut down) goes on from its last
saved record when the service starts again. The unit
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

from . import authorities, plan, targets
from .config import Settings as Config
from .dispatch import Dispatcher, Result, static_candidates
from .health import Health
from .limits import Limiter, Limits

log = logging.getLogger("nexus_ondemand.service")

IDLE = 300.0
POLL = 2.0
PARALLEL = 4
PARALLEL_MAX = 8
OUTAGE_WAIT = 30.0
OUTAGE_MAX = 600.0
RATE_WINDOW = 50                  # records the speed (and time left) is measured over


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
    parallel: int = PARALLEL
    outage_wait: float = OUTAGE_WAIT
    outage_max: float = OUTAGE_MAX
    status_every: float = 1.0

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
                   Path(learned) if learned else state / "learned.db",
                   parallel=parallel_from(env.get("KEI_ONDEMAND_PARALLEL")))


def parallel_from(value) -> int:
    """KEI_ONDEMAND_PARALLEL: records at once, 1 to PARALLEL_MAX (PARALLEL
    when unset or unreadable)."""
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return PARALLEL
    return min(PARALLEL_MAX, max(1, n))


# ----------------------------------------------------------------------
# Status file
# ----------------------------------------------------------------------

class Status:
    """ondemand-status.json: the job, the records in flight, and for the
    oldest of them (the next to be saved) each server's state (waiting,
    searching, n record(s), no record, down / skipped: why); records per
    hour and the seconds left; "outage" while this machine's network is
    down. Written at most every EVERY seconds, except on a change of state."""

    def __init__(self, path: Path, catalog: targets.Catalog, every: float = 1.0, clock=time.monotonic):
        self.path, self.catalog, self.every, self.clock = path, catalog, every, clock
        self.data: dict = {"state": "idle"}
        self.flight: dict = {}                       # seq -> {"record", "servers", "found"}
        self.finished: list[float] = []              # when the last records were saved
        self._last = float("-inf")

    def write(self) -> None:
        self._last = self.clock()
        self.data["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = self.path.with_suffix(".part")
        try:
            tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:                      # progress is a convenience: never stop a search on it
            log.warning("status not written: %s", exc)

    def touch(self) -> None:
        """write(), unless the last one was under EVERY seconds ago."""
        if self.clock() - self._last >= self.every:
            self.write()

    def job(self, job: Job, total: int, done: int, state: str = "matching") -> None:
        self.flight, self.finished = {}, []
        self.data = {"job": job.id, "state": state, "round": job.rounds, "total": total, "done": done,
                     "record": None, "servers": {}, "found": 0, "network": [], "inflight": 0,
                     "per_hour": 0, "eta_s": None}
        self.write()

    def _show(self) -> None:
        """The oldest record in flight is the one on screen."""
        self.data["inflight"] = len(self.flight)
        if self.flight:
            shown = self.flight[min(self.flight)]
            self.data.update(record=shown["record"], servers=shown["servers"], found=shown["found"])

    def record(self, seq: int, rec: marc.Record | None, label: str) -> None:
        self.flight[seq] = {"record": {"seq": seq, "biblionumber": biblionumber(rec) if rec is not None else None,
                                       "title": title(rec) if rec is not None else label},
                            "servers": {}, "found": 0}
        self._show()
        self.touch()

    def forget(self, seq: int) -> None:
        """SEQ's search is over (saved, or to be asked again)."""
        self.flight.pop(seq, None)
        self._show()

    def saved(self, done: int, n: int = 1) -> None:
        """Records up to DONE are saved (N of them now)."""
        now = self.clock()
        self.finished = (self.finished + [now] * n)[-RATE_WINDOW:]
        self.data["done"] = done
        if len(self.finished) >= 2 and self.finished[-1] > self.finished[0]:
            per_s = (len(self.finished) - 1) / (self.finished[-1] - self.finished[0])
            self.data["per_hour"] = round(per_s * 3600)
            self.data["eta_s"] = round(max(0, int(self.data.get("total") or 0) - done) / per_s)
        self.touch()

    def outage(self, until: float | None) -> None:
        """This machine's network is down: the job waits until UNTIL (epoch
        seconds), or None again."""
        self.data["outage"] = time.strftime("%H:%M:%S", time.localtime(until)) if until else None
        self.write()

    def _server(self, rec: dict, tid: str) -> dict:
        servers = rec["servers"]
        if tid not in servers:
            t = self.catalog.targets.get(tid)
            servers[tid] = {"name": t.name if t else tid, "country": t.country if t else "", "state": "waiting",
                            "ms": 0, "hits": 0}
        return servers[tid]

    def event(self, ev: dict) -> None:
        kind = ev.get("type")
        if kind == "done":
            self.data["network"] = sorted(set(self.data.get("network", [])) | set(ev.get("network") or []))
        seq = ev.get("seq")
        rec = self.flight.get(seq) or (self.flight[min(self.flight)] if self.flight else None)
        if rec is None:
            self.touch()
            return
        if kind == "wave":
            for tid in ev["targets"]:
                self._server(rec, tid)["state"] = "searching"
        elif kind == "attempt":
            s = self._server(rec, ev["target"])
            outcome = ev["outcome"]
            s.update(ms=ev["ms"], hits=ev["hits"], address=ev["address"])
            if outcome in ("found", "cached") and ev["records"]:
                s["state"] = f"{ev['records']} record(s)"
                rec["found"] += ev["records"]
            elif outcome in ("found", "none", "cached"):
                s["state"] = "no record"
            elif s["state"] in ("waiting", "searching") or outcome == "error":
                s["state"] = f"{'down' if outcome == 'error' else 'skipped'}: {ev['detail']}"[:200]
        elif kind == "static":
            rec["found"] += ev["found"]
        self._show()
        self.touch()


class Gate:
    """Holds every record while this machine's network is down: hold()
    after a search that only shows that, open() after one that reached a
    server. The wait doubles from WAIT to MAX while it lasts."""

    def __init__(self, wait: float, most: float, status: Status, clock=time.time, sleep=asyncio.sleep):
        self.base, self.most, self.status = wait, most, status
        self.clock, self.sleep = clock, sleep
        self.wait_s, self.until = wait, 0.0

    @staticmethod
    def down(res: Result) -> bool:
        """RES says this machine's network is down: it blocked the lookups
        or port 1921 (dispatch's network-wide rule) and no server answered."""
        return res.down

    def hold(self) -> None:
        now = self.clock()
        if now >= self.until:                        # the first record to see it sets the wait
            self.until = now + self.wait_s
            self.wait_s = min(self.most, self.wait_s * 2)
            log.warning("the network looks down: waiting until %s", time.strftime("%H:%M:%S",
                                                                                  time.localtime(self.until)))
            self.status.outage(self.until)

    def open(self) -> None:
        if self.until or self.wait_s != self.base:
            self.wait_s, self.until = self.base, 0.0
            self.status.outage(None)

    async def passed(self, still) -> bool:
        """Wait while held; False when STILL() says the job stopped meanwhile."""
        while self.clock() < self.until:
            if not still():
                return False
            await self.sleep(min(5.0, self.until - self.clock()))
        return still()


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


def _error_row(rec: marc.Record | None, exc: BaseException) -> dict:
    return {"biblionumber": biblionumber(rec) if rec is not None else None,
            "f005": rec.control("005") if rec is not None else "", "title": title(rec) if rec else "",
            "status": "error", "m0": 0, "m1": 0, "w": 0, "r": 0, "pointers": 0,
            "detail": json.dumps({"error": f"{type(exc).__name__}: {exc}"[:300]}), "before": None,
            "after": None, "other": None}


def _merged_row(rec: marc.Record, cands: list[Candidate], donors: dict) -> dict:
    """The batch worker's item row for REC (CPU only: run in a thread)."""
    return item_row(rec, enrich(rec, best_per_source(rec, cands), Policy(donors=donors)))


async def _one(store: Store, job: Job, settings: Settings, dispatcher: Dispatcher, status: Status, gate: Gate,
               seq: int, rec: marc.Record | None, query: dict) -> tuple[int, dict | None]:
    """Search, keep and merge record SEQ; (SEQ, its row), or (SEQ, None)
    when the job stopped while it waited for the network."""
    status.record(seq, rec, query.get("title") or query.get("isbn") or "")
    try:
        asked = bool(store.attempts(job.id, seq, job.rounds))
        while not asked:                             # (a round with no server left to ask records nothing)
            if not await gate.passed(lambda: store.job(job.id).state == "matching"):
                return seq, None
            res = await dispatcher.run(rec, _steps(rec, query), exclude=store.asked(job.id, seq), tag=seq)
            if Gate.down(res):
                gate.hold()                          # not "nothing found": asked again when it is back
                continue
            gate.open()
            store.add_attempts(job.id, seq, job.rounds, res.attempts)
            save_found(settings, job.id, seq, job.rounds, res)
            asked = True
        cands = load_found(settings, job.id, seq)
        if rec is None:
            row = _query_row(query, cands)
        else:
            bib = biblionumber(rec)
            donors = store.choices(job.id, bib) if bib is not None else {}
            row = await asyncio.to_thread(_merged_row, rec, cands, donors)
    except asyncio.CancelledError:
        raise
    except Exception as exc:                         # one bad record never stops the job
        log.exception("job %s record %s", job.id, seq)
        row = _error_row(rec, exc)
    finally:
        status.forget(seq)
    row.update(job_id=job.id, seq=seq)
    return seq, row


async def _auth_one(store: Store, job: Job, aj, status: Status, gate: Gate, seq: int,
                    rec: marc.Record) -> tuple[int, dict | None]:
    """An authority job's record SEQ (authorities.AuthJob); as _one."""
    status.record(seq, rec, "")
    try:
        row, attempts = await aj.row(rec, seq, gate, lambda: store.job(job.id).state == "matching")
        if row is None:
            return seq, None
        if attempts:
            store.add_attempts(job.id, seq, job.rounds, attempts)
    except asyncio.CancelledError:
        raise
    except Exception as exc:                         # one bad record never stops the job
        log.exception("job %s record %s", job.id, seq)
        row = _error_row(rec, exc)
    finally:
        status.forget(seq)
    row.update(job_id=job.id, seq=seq)
    return seq, row


async def process(store: Store, job: Job, settings: Settings, dispatcher: Dispatcher, status: Status,
                  gate: Gate | None = None) -> str:
    """Search, keep and merge every record of JOB, PARALLEL at a time;
    returns its state when it stopped. A job found "matching" (the service
    stopped half way) goes on after its last saved record; one "exported"
    (new, Search more servers or a new donor) goes through all of them,
    asking the servers only for records not asked in this round. Rows are
    saved in order: "done" never passes a record still being searched."""
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
    gate = gate or Gate(settings.outage_wait, settings.outage_max, status)
    aj = None
    if job.kind == "auth":                           # names and subjects: authorities.py
        aj = authorities.AuthJob(store, job, settings.job_dir(job.id), settings.static_db, dispatcher.settings.static,
                                 dispatcher, dispatcher.catalog)
    try:
        return await _run(store, job, settings, dispatcher, status, gate, aj, total, start)
    finally:
        if aj is not None:
            aj.close()


async def _run(store: Store, job: Job, settings: Settings, dispatcher: Dispatcher, status: Status, gate: Gate, aj,
               total: int, start: int) -> str:
    lanes = max(1, settings.parallel)
    running: set[asyncio.Task] = set()
    rows: dict[int, dict] = {}
    saved = start
    held = False                                     # a record let go while it waited for the network

    def still() -> str:
        return store.job(job.id).state

    async def settle(timeout: float | None) -> None:
        """Wait for a record (at most TIMEOUT), then save the run of finished ones."""
        nonlocal running, saved, held
        if not running:
            return
        done, running = await asyncio.wait(running, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            seq, row = task.result()
            if row is None:
                held = True
            else:
                rows[seq] = row
        batch = []
        while saved + 1 in rows:
            saved += 1
            batch.append(rows.pop(saved))
        if batch:
            store.put_items(batch)
            store.set(job.id, done=saved)
            status.saved(saved, len(batch))

    async def stop() -> None:
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)
        status.write()

    for seq, (rec, query) in enumerate(_records(settings, job), 1):
        if seq <= start:
            continue
        while True:
            while len(running) >= lanes:
                await settle(settings.pause_poll)
                if still() != "matching":
                    break
            if still() != "matching":
                break
            if not (settings.state / "pause").exists():
                break
            status.data["paused"] = True             # the tray's or the panel's Pause: no new record starts
            status.write()
            if running:
                await settle(settings.pause_poll)
            else:
                await asyncio.sleep(settings.pause_poll)
        status.data["paused"] = False
        state = still()
        if state != "matching":
            await stop()
            return state                             # cancelled from the panel
        one = (_auth_one(store, job, aj, status, gate, seq, rec) if aj is not None
               else _one(store, job, settings, dispatcher, status, gate, seq, rec, query))
        running.add(asyncio.ensure_future(one))
    while running:
        await settle(settings.pause_poll)
        if still() != "matching":
            state = still()
            await stop()
            return state
    if held:                                         # the job stopped while a record waited for the network
        return still()
    store.make_chunks(job.id, settings.chunk)
    report.write(store, job.id, settings.job_dir(job.id))
    store.set(job.id, state="ready", total=total, done=total)
    status.data.update(state="ready", record=None, inflight=0, eta_s=0)
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
    limits = Limits(service=max(Limits().service, 3 * max(1, settings.parallel)))
    d = Dispatcher(catalog, health, Limiter(limits, store=health), learned=learned, static=static,
                   on_event=on_event, **kw)
    d.settings.static = config.static
    return d, health


async def serve(settings: Settings, config: Config, *, once: int | None = None, catalog=None, opener=None,
                clock=time.monotonic) -> int:
    """Run every waiting on-demand job (only job ONCE when given); wait for
    more until IDLE seconds pass with none. Returns how many ran."""
    catalog = catalog or targets.load(config.direct_list)
    status = Status(settings.status_file, catalog, settings.status_every)
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
