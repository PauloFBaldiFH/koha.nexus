"""python -m nexus_ondemand serve | once JOB | status | targets | health | health-reset | check

    serve          the koha-nexus-ondemand unit: every on-demand job of
                   jobs.db, then exit after 5 idle minutes
    once           JOB: that job only, now (for a test from a terminal)
    status         ondemand-status.json: the job being searched, each
                   server's state
    import-file    JOB SEQ N --out FILE: record N found for a typed query, as
                   MARCXML for Koha's staged import (a new record)

    targets        the direct servers on-demand may ask, and those skipped
                   or unusable, with the reason (--json)
    health         each server's breaker state, last error, 7-day counts (--json)
    health-reset   forget the breaker of one server id (or --all)
    check          HOST PORT [DB]: would the policy let on-demand contact it?
                   (looks the name up; contacts nothing)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from nexus_gateway.z3950 import Z3950Error
from nexus_jobs.store import Store

from . import service
from . import targets as targets_mod
from .config import Settings
from .health import Health
from .policy import Policy


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nexus_ondemand")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("targets", "health"):
        sub.add_parser(name).add_argument("--json", action="store_true")
    hr = sub.add_parser("health-reset")
    hr.add_argument("id", nargs="?")
    hr.add_argument("--all", action="store_true")
    ck = sub.add_parser("check")
    ck.add_argument("host")
    ck.add_argument("port", type=int)
    ck.add_argument("db", nargs="?", default="")
    sv = sub.add_parser("serve")
    sv.add_argument("--idle", type=float, default=service.IDLE)
    sub.add_parser("once").add_argument("job", type=int)
    sub.add_parser("status")
    imp = sub.add_parser("import-file")
    imp.add_argument("job", type=int)
    imp.add_argument("seq", type=int)
    imp.add_argument("n", type=int)
    imp.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    settings = Settings.from_env()

    if args.cmd in ("serve", "once"):
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        svc = service.Settings.from_env()
        if args.cmd == "serve":
            svc.idle = args.idle
        n = asyncio.run(service.serve(svc, settings, once=args.job if args.cmd == "once" else None))
        print(json.dumps({"jobs": n}))
        return 0
    if args.cmd == "import-file":
        svc = service.Settings.from_env()
        store = Store(svc.jobs_db)
        try:
            print(json.dumps(service.import_file(svc, store, args.job, args.seq, args.n, args.out), ensure_ascii=False))
        except (KeyError, service.JobError) as exc:
            print(str(exc).strip("'\""), file=sys.stderr)
            return 1
        finally:
            store.close()
        return 0
    if args.cmd == "status":
        try:
            status = json.loads(service.Settings.from_env().status_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            status = {"state": "idle"}
        print(json.dumps(status, ensure_ascii=False))
        return 0

    if args.cmd == "check":
        try:
            ip = asyncio.run(Policy().resolve(args.host, args.port, args.db))
        except Z3950Error as exc:
            print(json.dumps({"allowed": False, "kind": exc.kind, "reason": str(exc)}))
            return 1
        print(json.dumps({"allowed": True, "address": ip}))
        return 0

    catalog = targets_mod.load(settings.direct_list)
    if args.cmd == "targets":
        rows = [{"id": t.id, "name": t.name, "address": t.address.key, "provider": t.address.provider,
                 "recordtype": t.recordtype, "alternates": [a.key for a in t.alternates],
                 "unusable": t.unusable} for t in catalog.targets.values()]
        if args.json:
            print(json.dumps({"targets": rows, "skipped": catalog.skipped}, ensure_ascii=False, indent=1))
        else:
            usable = sum(1 for r in rows if not r["unusable"])
            print(f"{len(rows)} loaded, {usable} usable now, {len(catalog.skipped)} skipped")
            for r in rows:
                if r["unusable"]:
                    print(f"  unusable  {r['id']}: {r['unusable']}")
            for sid, why in catalog.skipped:
                print(f"  skipped   {sid}: {why}")
        return 0

    health = Health(settings.health_db)
    try:
        if args.cmd == "health-reset":
            if args.all:
                n = health.reset()
            elif args.id and args.id.lower() in catalog.targets:
                n = sum(health.reset(a.key) for a in catalog.targets[args.id.lower()].addresses)
            else:
                print("health-reset: name a server id, or --all", file=sys.stderr)
                return 2
            print(json.dumps({"reset": n}))
            return 0
        health.check_list(catalog.sha256)
        rows = [{"id": t.id, **health.summary(a.key)} for t in catalog.targets.values() for a in t.addresses]
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        else:
            for r in rows:
                if r["state"] != "ok" or r["fail_7d"]:
                    print(f"{r['id']:<20} {r['state']:<14} ok {r['ok_7d']:>4}  fail {r['fail_7d']:>4}  {r['last_error']}")
        return 0
    finally:
        health.close()


if __name__ == "__main__":
    sys.exit(main())
