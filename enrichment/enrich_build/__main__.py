"""python -m enrich_build {build | release | publish | verify | inspect}

    build SOURCES.json [--out static.db] [--report report.json] [--sample N]
                      read every source's dumps and write static.db
    release static.db [--month YYYY.MM] [--dir DIR]
                      write nexus-enrich-YYYY.MM.db.zst and its .sha256
    publish ASSET.db.zst [--repo OWNER/NAME]
                      upload it and its .sha256 to the release enrich-YYYY.MM
                      (GITHUB_TOKEN), write latest.txt for the mirror
    verify ASSET.db.zst [--sha256 HASH]
                      check the hash, decompress, run SQLite's integrity check
    inspect static.db print the build date, counts and sources

Runs on the release machine (yours or CI), never on the production VPS
and never on a library's computer.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m enrich_build", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("sources", type=Path)
    b.add_argument("--out", type=Path, default=Path("static.db"))
    b.add_argument("--report", type=Path)
    b.add_argument("--sample", type=int, default=2000, help="records read to train the zstd dictionary")
    r = sub.add_parser("release")
    r.add_argument("db", type=Path)
    r.add_argument("--month", default=date.today().strftime("%Y.%m"))
    r.add_argument("--dir", type=Path)
    p = sub.add_parser("publish")
    p.add_argument("asset", type=Path)
    p.add_argument("--repo", default="PauloFBaldiFH/koha.nexus")
    v = sub.add_parser("verify")
    v.add_argument("asset", type=Path)
    v.add_argument("--sha256")
    i = sub.add_parser("inspect")
    i.add_argument("db", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "build":
        from .build import Builder, load_config
        sources = load_config(args.sources)
        report = Builder(args.out, sources, args.sources.resolve().parent, args.sample).build()
        text = json.dumps(report.__dict__, ensure_ascii=False, indent=2)
        if args.report:
            args.report.write_text(text, encoding="utf-8")
        print(text)
        return 0 if report.versions or report.headings else 1
    if args.cmd == "release":
        from .release import asset_name, compress
        out_dir = args.dir or args.db.resolve().parent
        asset, sums = compress(args.db, out_dir / asset_name(args.month))
        print(json.dumps({"asset": str(asset), "bytes": asset.stat().st_size, "sha256": str(sums)}))
        return 0
    if args.cmd == "publish":
        from .publish import GitHub, PublishError, publish
        try:
            print(json.dumps(publish(args.asset, GitHub(os.environ.get("GITHUB_TOKEN", ""), args.repo))))
        except PublishError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    if args.cmd == "verify":
        from .release import verify
        try:
            print(json.dumps(verify(args.asset, args.sha256)))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    meta = {k: (v if isinstance(v, str) else f"<{len(v)} bytes>") for k, v in conn.execute("SELECT * FROM meta")}
    sources = [dict(zip(("id", "name", "mode", "brazilian", "weight", "records", "headings"), row))
               for row in conn.execute("SELECT id, name, mode, brazilian, weight, records, headings FROM sources")]
    print(json.dumps({"meta": meta, "sources": sources}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
