"""python -m nexus_gateway serve | update | init-db | koha-sql | panel-list | check | zeus-labels

    serve       run the SRU server (settings: NEXUS_GATEWAY_* variables)
    update      download the newest static.db release and swap it in
                (--check: only say whether one is available; --force: again)
    init-db     create an empty static.db where there is none (before the
                first download), print its record count
    koha-sql    print the SQL that points Koha's rows at this gateway
                (--undo-local-first / --redo-local-first: the local-first
                catalogues' steps, see koha_sql.py)
    panel-list  print the koha.nexus panel's list of these rows
    check       load targets.json and static.db, print what would be served
    zeus-labels fetch Catálogo Zeus's search form (NEXUS_GATEWAY_ZEUS_URL or
                --url) and print which targets[n] each zeus target is searched as
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys

from nexus_enrich.static import create_empty, record_count

from . import koha_sql, update, zeus
from .config import Settings
from .engine import Engine, Static
from .learned import Learned
from .live import Runner
from .server import make_server
from .targets import load


def build(settings: Settings, live: bool | None = None) -> Engine:
    learned = Learned(settings.learned_db, settings.learned_days)
    use_live = settings.live if live is None else live
    hub = zeus.Zeus(settings.zeus_url) if settings.zeus_url else None
    runner = Runner(learned, settings.live_timeout, settings.live_grace, zeus=hub) if use_live else None
    return Engine(Static(settings.static_db), learned, load(settings.targets), runner)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nexus_gateway")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sql = sub.add_parser("koha-sql")
    sql.add_argument("--host", default=koha_sql.KOHA_HOST)
    sql.add_argument("--port", type=int, default=koha_sql.GATEWAY_PORT)
    how = sql.add_mutually_exclusive_group()
    how.add_argument("--undo-local-first", action="store_true",
                     help="give the library's own UNESP/UFPR/UNIFESP/UnB/UFU rows their rank and tick back")
    how.add_argument("--redo-local-first", action="store_true", help="the local-first steps again, after an undo")
    sub.add_parser("check")
    sub.add_parser("init-db")
    up = sub.add_parser("update")
    up.add_argument("--force", action="store_true")
    up.add_argument("--check", action="store_true")
    pl = sub.add_parser("panel-list")
    pl.add_argument("--authorities", help="the panel list whose authority rows to keep")
    zl = sub.add_parser("zeus-labels")
    zl.add_argument("--url", help="Catálogo Zeus's address (default NEXUS_GATEWAY_ZEUS_URL)")
    args = ap.parse_args(argv)
    settings = Settings.from_env()

    if args.cmd == "update":
        try:
            result = update.update(settings.static_db, api=settings.releases_api, mirror=settings.mirror,
                                   force=args.force, check=args.check)
        except (update.UpdateError, OSError) as exc:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
            return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.cmd == "init-db":
        try:
            created = create_empty(settings.static_db)
        except (OSError, sqlite3.Error) as exc:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
            return 1
        print(json.dumps({"status": "created" if created else "present",
                          "records": max(record_count(settings.static_db), 0)}))
        return 0
    if args.cmd == "panel-list":
        sys.stdout.write(koha_sql.panel_list(load(settings.targets), args.authorities))
        return 0

    if args.cmd == "koha-sql":
        render = (koha_sql.render_undo if args.undo_local_first
                  else koha_sql.render_redo if args.redo_local_first else koha_sql.render)
        sys.stdout.write(render(load(settings.targets), args.host, args.port))
        return 0
    if args.cmd == "zeus-labels":
        url = args.url or settings.zeus_url
        if not url:
            print("No Zeus address: give --url or set NEXUS_GATEWAY_ZEUS_URL.", file=sys.stderr)
            return 2
        try:
            labels = zeus.parse_labels(zeus._get(url, 20.0))
        except zeus.ZeusError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        rows = zeus.compare([t for t in load(settings.targets).values() if t.kind == "zeus"], labels)
        for r in rows:
            where = f"targets[{r['found']}] {r['label']}" if r["found"] is not None else "not on the page"
            print(f"{'ok ' if r['found'] is not None else 'NO '} {r['id']:<8} {r['name']}  ->  {where}")
        print(f"\n{len(labels)} targets on the page:", ", ".join(f"{n}={labels[n]}" for n in sorted(labels)))
        return 0 if labels and all(r["found"] is not None for r in rows) else 1
    if args.cmd == "check":
        targets = load(settings.targets)
        engine = Engine(Static(settings.static_db), None, targets)
        print(json.dumps({"static": engine.static.info(), "targets": len(targets),
                          "live": sorted(t.id for t in targets.values() if t.live)}, indent=1))
        return 0

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    engine = build(settings)
    if engine.learned is not None:
        engine.learned.prune()
    server = make_server(engine, settings)
    logging.getLogger("nexus_gateway").info("listening on %s:%d, static.db %s", settings.host, settings.port,
                                            engine.static.info())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if engine.runner is not None:
            engine.runner.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
