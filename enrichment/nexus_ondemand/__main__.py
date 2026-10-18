"""python -m nexus_ondemand targets | health | health-reset | check

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
import sys

from nexus_gateway.z3950 import Z3950Error

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
    args = ap.parse_args(argv)
    settings = Settings.from_env()

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
