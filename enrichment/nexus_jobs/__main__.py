"""python -m nexus_jobs [--state DIR] COMMAND

Jobs (the panel's tasks call these through the installer):
    add --scope "all" | "101, 102, 500-550" [--kind auth --mode exact|fuzzy]
                                    new job; prints its id and folder
    add --origin ondemand --scope "101, 102" | --isbn X | --title T [--author A] [--year Y]
                                    an on-demand job: "all" or any biblionumbers, or
                                    a typed query (its records are imported as new)
    more ID                         on-demand: ask the next servers (a new round)
    donor ID BIBLIONUMBER GROUP [SOURCE]
                                    on-demand: the donor of a field group (none: the best)
    exported ID                     Koha's records are in jobs/ID/export.xml
    fail ID --error TEXT
    cancel ID
    list | show ID | status | diff ID BIBLIONUMBER
    pause on|off                    stop or resume the worker between batches
    worker [--once]                 match every job waiting (the unit runs this)

Apply and Revert bookkeeping (installer only):
    chunks ID | chunk-ids ID N
    chunk-file ID N --current TSV --out FILE
    check-matches ID N --batch B --staged FILE
    committed ID N --after TSV | chunk-failed ID N --note TEXT
    applied-ids ID | revert-plan ID --current TSV [--all] | reverted ID N [--kept LIST]
    kind ID | chunks ID --kind auth|bib
    auth-resolve ID --koha XML | auth-file ID N --out FILE
    auth-committed ID N [--batch B] --staged TSV
    auth-revert-plan ID | auth-reverted ID N [--kept LIST]

State folder: --state, else NEXUS_JOBS_STATE, else /var/lib/koha-nexus-enrich.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from nexus_enrich.authority import KohaIndex
from nexus_enrich.merge import GROUPS

from . import apply, report, scope
from .store import Store
from .worker import Settings, run

SHOW_CHANGES = 200
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nexus_jobs", description=__doc__.split("\n")[0])
    ap.add_argument("--state", type=Path,
                    default=Path(os.environ.get("NEXUS_JOBS_STATE", "/var/lib/koha-nexus-enrich")))
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--scope", default="all")
    a.add_argument("--kind", choices=("bib", "auth"), default="bib")
    a.add_argument("--mode", choices=("exact", "fuzzy"), default="exact")
    a.add_argument("--origin", choices=("batch", "ondemand"), default="batch")
    for name in ("isbn", "title", "author", "year"):
        a.add_argument(f"--{name}", default="")
    for name in ("exported", "cancel", "show", "applied-ids", "kind", "auth-revert-plan", "more", "origin"):
        sub.add_parser(name).add_argument("job", type=int)
    ch = sub.add_parser("chunks")
    ch.add_argument("job", type=int)
    ch.add_argument("--kind", choices=("bib", "auth"), default="")
    ar = sub.add_parser("auth-resolve")
    ar.add_argument("job", type=int)
    ar.add_argument("--koha", type=Path, required=True)
    f = sub.add_parser("fail")
    f.add_argument("job", type=int)
    f.add_argument("--error", default="")
    sub.add_parser("list")
    sub.add_parser("status")
    p = sub.add_parser("pause")
    p.add_argument("value", choices=("on", "off"))
    d = sub.add_parser("diff")
    d.add_argument("job", type=int)
    d.add_argument("biblionumber", type=int)
    w = sub.add_parser("worker")
    w.add_argument("--once", action="store_true")
    w.add_argument("--pause", type=float, default=float(os.environ.get("NEXUS_JOBS_PAUSE", "0")))
    for name in ("chunk-ids", "chunk-file", "check-matches", "committed", "chunk-failed", "reverted",
                 "auth-file", "auth-committed", "auth-reverted"):
        c = sub.add_parser(name)
        c.add_argument("job", type=int)
        c.add_argument("chunk", type=int)
        if name == "chunk-file":
            c.add_argument("--current", required=True)
            c.add_argument("--out", type=Path, required=True)
        elif name == "auth-file":
            c.add_argument("--out", type=Path, required=True)
        elif name == "auth-committed":
            c.add_argument("--batch", type=int, default=0)
            c.add_argument("--staged", type=Path, required=True)
        elif name == "check-matches":
            c.add_argument("--batch", type=int, required=True)
            c.add_argument("--staged", type=Path, required=True)
        elif name == "committed":
            c.add_argument("--after", required=True)
        elif name == "chunk-failed":
            c.add_argument("--note", default="")
        elif name in ("reverted", "auth-reverted"):
            c.add_argument("--kept", default="")
    dn = sub.add_parser("donor")
    dn.add_argument("job", type=int)
    dn.add_argument("biblionumber", type=int)
    dn.add_argument("group", choices=[g[0] for g in GROUPS])
    dn.add_argument("source", nargs="?", default="")
    r = sub.add_parser("revert-plan")
    r.add_argument("job", type=int)
    r.add_argument("--current", required=True)
    r.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)

    static = Path(os.environ.get("NEXUS_GATEWAY_STATIC_DB", str(args.state / "static.db")))
    settings = Settings(args.state, static)
    if args.cmd == "worker":
        settings.pause = args.pause
        run(settings, once=args.once)
        return 0
    if args.cmd == "pause":
        if args.value == "on":
            settings.pause_file.touch()
        else:
            settings.pause_file.unlink(missing_ok=True)
        return 0
    if args.cmd == "status":
        try:
            status = json.loads(settings.status_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            status = {"state": "idle"}
        status["pause_file"] = settings.pause_file.exists()
        print(json.dumps(status, ensure_ascii=False))
        return 0

    store = Store(settings.jobs_db)
    try:
        return _jobs(args, store, settings)
    except (KeyError, scope.ScopeError) as exc:
        print(str(exc).strip("'\""), file=sys.stderr)
        return 1
    finally:
        store.close()


def _ondemand_scope(args) -> tuple:
    """(ranges, typed query JSON) of an on-demand job: biblionumbers (any
    number; None for "all"), or a typed query."""
    q = {k: " ".join(getattr(args, k).split())[:300] for k in ("isbn", "title", "author", "year")}
    if any(q.values()):
        if not (q["isbn"] or q["title"]):
            raise scope.ScopeError("an on-demand query needs an ISBN or a title")
        return None, json.dumps({k: v for k, v in q.items() if v}, ensure_ascii=False)
    return scope.parse(args.scope), ""


def _jobs(args, store: Store, settings: Settings) -> int:
    cmd = args.cmd
    if cmd == "add":
        query = ""
        if args.origin == "ondemand":
            ranges, query = _ondemand_scope(args)
        else:
            ranges = scope.parse(args.scope)
        job = store.add(scope.text(ranges) if not query else "query", args.kind,
                        args.mode if args.kind == "auth" else "", args.origin, query)
        folder = settings.job_dir(job.id)
        folder.mkdir(parents=True, exist_ok=True)
        ids = ""
        if ranges is not None:
            ids = str(folder / "ids.txt")
            with open(ids, "w", encoding="ascii") as fh:
                for n in scope.ids(ranges):
                    fh.write(f"{n}\n")
        print(json.dumps({"job": job.id, "dir": str(folder), "scope": job.scope, "ids": ids}))
        return 0
    if cmd == "list":
        print(json.dumps([j.as_dict() for j in store.jobs()], ensure_ascii=False))
        return 0
    job = store.job(args.job)
    if cmd == "exported":
        if job.state != "queued":
            print(f"job {job.id} is {job.state}", file=sys.stderr)
            return 1
        store.set(job.id, state="exported")
        return 0
    if cmd == "fail":
        store.set(job.id, state="failed", error=args.error[:500])
        return 0
    if cmd == "cancel":
        if job.state not in ("queued", "exported", "matching", "ready"):
            print(f"job {job.id} is {job.state}: only a job not yet applied can be cancelled", file=sys.stderr)
            return 1
        store.set(job.id, state="cancelled")
        return 0
    if cmd == "show":
        out = job.as_dict()
        out["dir"] = str(settings.job_dir(job.id))
        rep = settings.job_dir(job.id) / "report.json"
        if rep.is_file():
            out["report"] = json.loads(rep.read_text(encoding="utf-8"))
            out["report_html"] = str(rep.with_suffix(".html"))
        out["chunks"] = [dict(c) for c in store.chunks(job.id)]
        if job.origin == "ondemand":
            # What each server did, every round; a typed query's records.
            out["attempts"] = [{k: a[k] for k in ("seq", "round", "wave", "target", "address", "outcome",
                                                  "category", "detail", "step", "hits", "records", "ms")}
                               for a in store.attempts(job.id)]
            out["found"] = [{"seq": r["seq"], **json.loads(r["detail"] or "{}")}
                            for r in store.items(job.id, "found", "no-match") if r["biblionumber"] is None]
            # Records already imported as new (the installer leaves imported-SEQ-N with the biblionumber).
            for q in out["found"]:
                for i, f in enumerate(q.get("found", []), 1):
                    mark = settings.job_dir(job.id) / f"imported-{q['seq']}-{i}"
                    if mark.is_file():
                        v = mark.read_text(encoding="utf-8").strip()
                        f["imported"] = int(v) if v.isdigit() else 0
            # Each record's donors (for "Choose donor"): every server's best record, best first.
            out["donors"] = {str(r["biblionumber"]): json.loads(r["detail"] or "{}").get("candidates", [])
                             for r in store.items(job.id) if r["biblionumber"] is not None}
            out["choices"] = {}
            for b, grp, src in store.conn.execute(
                    "SELECT biblionumber, grp, source FROM od_choices WHERE job_id = ?", (job.id,)):
                out["choices"].setdefault(str(b), {})[grp] = src
        # The records a person reviews first (the panel's list): changed
        # ones, then the review list, at most SHOW_CHANGES.
        auth = job.kind == "auth"
        out["changes"] = [
            {"biblionumber": r["biblionumber"], "status": r["status"], "title": r["title"], "m0": r["m0"],
             "m1": r["m1"], "w": r["w"], "r": r["r"],
             "added": r["m0"] + r["m1"] if auth else len(json.loads(r["detail"] or "{}").get("additions", []))}
            for status in ("enriched", "review") for r in store.items(job.id, status, limit=SHOW_CHANGES)]
        if auth:
            out["new_authorities"] = [{"id": a["id"], "heading": a["heading"], "source": a["source"],
                                       "preliminary": a["preliminary"], "state": a["state"], "authid": a["authid"]}
                                      for a in store.new_authorities(job.id)[:SHOW_CHANGES]]
        print(json.dumps(out, ensure_ascii=False))
        return 0
    if cmd == "diff":
        sys.stdout.write(report.text_diff(store, job.id, args.biblionumber))
        return 0
    if cmd == "chunks":
        if job.state not in ("ready", "applying", "partly-applied"):
            print(f"job {job.id} is {job.state}: nothing to apply", file=sys.stderr)
            return 1
        print("\n".join(str(n) for n in apply.pending_chunks(store, job.id, args.kind)))
        return 0
    if cmd == "kind":
        print(job.kind)
        return 0
    if cmd == "origin":
        print(job.origin)
        return 0
    if cmd in ("more", "donor"):
        if job.origin != "ondemand" or job.state not in ("ready", "failed"):
            print(f"job {job.id} is {job.state}: only an on-demand report not yet applied can search again",
                  file=sys.stderr)
            return 1
        if cmd == "more":
            store.set(job.id, state="exported", rounds=job.rounds + 1, error="")
        else:
            store.set_choice(job.id, args.biblionumber, args.group, args.source)
            store.set(job.id, state="exported", error="")     # merged again, no network
        print(json.dumps({"job": job.id, "round": store.job(job.id).rounds}))
        return 0
    if cmd == "auth-resolve":
        print(apply.resolve_new(store, job.id, KohaIndex.from_file(args.koha)))
        return 0
    if cmd == "auth-file":
        print(apply.auth_file(store, job.id, args.chunk, args.out))
        return 0
    if cmd == "auth-committed":
        text = args.staged.read_text(encoding="utf-8", errors="replace") if args.staged.is_file() else ""
        print(json.dumps(apply.auth_committed(store, job.id, args.chunk, args.batch or None, text)))
        return 0
    if cmd == "auth-revert-plan":
        for chunk, batch, ids in apply.auth_revert_plan(store, job.id):
            print(f"{chunk}\t{batch}\t{','.join(str(n) for n in ids)}")
        return 0
    if cmd == "auth-reverted":
        apply.auth_reverted(store, job.id, args.chunk, [int(x) for x in args.kept.split(",") if x.strip().isdigit()])
        return 0
    if cmd == "chunk-ids":
        print("\n".join(str(n) for n in apply.chunk_ids(store, job.id, args.chunk)))
        return 0
    if cmd == "chunk-file":
        manifest = apply.chunk_file(store, job.id, args.chunk, apply.read_tsv(args.current), args.out)
        print(len(manifest))
        return 0
    if cmd == "check-matches":
        bad = apply.check_matches(store, job.id, args.chunk, args.batch,
                                  args.staged.read_text(encoding="utf-8", errors="replace"))
        print("\n".join(str(n) for n in bad))
        return 0
    if cmd == "committed":
        print(json.dumps(apply.committed(store, job.id, args.chunk, apply.read_tsv(args.after))))
        return 0
    if cmd == "chunk-failed":
        apply.failed(store, job.id, args.chunk, args.note)
        return 0
    if cmd == "applied-ids":
        print("\n".join(str(n) for n in apply.applied_ids(store, job.id)))
        return 0
    if cmd == "revert-plan":
        for chunk, batch, keep in apply.revert_plan(store, job.id, apply.read_tsv(args.current), args.all):
            print(f"{chunk}\t{batch}\t{','.join(str(n) for n in keep)}")
        return 0
    if cmd == "reverted":
        kept = [int(x) for x in args.kept.split(",") if x.strip().isdigit()]
        apply.reverted(store, job.id, args.chunk, kept)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
