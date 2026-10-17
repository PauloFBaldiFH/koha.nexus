"""python -m nexus_gateway serve | koha-sql | check

    serve       run the SRU server (settings: NEXUS_GATEWAY_* variables)
    koha-sql    print the SQL that points Koha's rows at this gateway
    check       load targets.json and static.db, print what would be served
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import koha_sql
from .config import Settings
from .engine import Engine, Static
from .learned import Learned
from .live import Runner
from .server import make_server
from .targets import load


def build(settings: Settings, live: bool | None = None) -> Engine:
    learned = Learned(settings.learned_db, settings.learned_days)
    use_live = settings.live if live is None else live
    runner = Runner(learned, settings.live_timeout, settings.live_grace) if use_live else None
    return Engine(Static(settings.static_db), learned, load(settings.targets), runner)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nexus_gateway")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sql = sub.add_parser("koha-sql")
    sql.add_argument("--host", default="127.0.0.1")
    sql.add_argument("--port", type=int, default=5000)
    sub.add_parser("check")
    args = ap.parse_args(argv)
    settings = Settings.from_env()

    if args.cmd == "koha-sql":
        sys.stdout.write(koha_sql.render(load(settings.targets), args.host, args.port))
        return 0
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
