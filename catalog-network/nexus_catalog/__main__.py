"""python -m nexus_catalog [serve | import FILE... | push URL FILE...]

    serve (default)  listen on NEXUS_CATALOG_HOST:NEXUS_CATALOG_PORT
                     (127.0.0.1:8088), behind the Cloudflare Tunnel
    import FILE...   load MARCXML files straight into the pool (on the
                     server, to seed it; the source is the file name, or
                     --source NAME)
    push URL FILE... send MARCXML files to a pool's /api/records/sync, in
                     batches (from a koha.nexus library; the token comes
                     from NEXUS_CATALOG_TOKEN, never the command line)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path


def serve() -> None:
    import uvicorn
    logging.basicConfig(level=os.environ.get("NEXUS_CATALOG_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run("nexus_catalog.app:app",
                host=os.environ.get("NEXUS_CATALOG_HOST", "127.0.0.1"),
                port=int(os.environ.get("NEXUS_CATALOG_PORT", "8088")),
                workers=int(os.environ.get("NEXUS_CATALOG_WORKERS", "1")),
                proxy_headers=True, forwarded_allow_ips="127.0.0.1", access_log=False)


def _elements(files: list[str]):
    from . import marc
    for name in files:
        data = Path(name).read_bytes()
        yield name, marc.split_records(data)


def import_files(files: list[str], source: str = "") -> int:
    from . import marc
    from .config import Settings
    from .db import Catalog
    settings = Settings.from_env()
    catalog = Catalog(settings.db_path)
    bad = 0
    for name, elements in _elements(files):
        records = []
        for el in elements:
            try:
                records.append(marc.read(el, settings.max_record_bytes))
            except marc.RecordError as exc:
                bad += 1
                print(f"{name}: skipped: {exc}", file=sys.stderr)
        for i in range(0, len(records), 1000):
            counts = catalog.put_many(records[i:i + 1000], source or Path(name).name)
            print(f"{name}: {json.dumps(counts)}")
    print(f"{catalog.count()} records in {settings.db_path}")
    return 1 if bad and not catalog.count() else 0


def push(url: str, files: list[str], batch: int = 500) -> int:
    from xml.etree import ElementTree as ET
    token = os.environ.get("NEXUS_CATALOG_TOKEN", "").strip()
    if not token:
        print("NEXUS_CATALOG_TOKEN is not set", file=sys.stderr)
        return 2
    endpoint = url.rstrip("/")
    if not endpoint.endswith("/api/records/sync"):
        endpoint += "/api/records/sync"
    rc = 0
    for name, elements in _elements(files):
        for i in range(0, len(elements), batch):
            body = ('<collection xmlns="http://www.loc.gov/MARC21/slim">'
                    + "".join(ET.tostring(el, encoding="unicode") for el in elements[i:i + batch])
                    + "</collection>").encode("utf-8")
            req = urllib.request.Request(endpoint, data=body, method="POST", headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/marcxml+xml",
                "User-Agent": "koha.nexus-catalog-push"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:   # noqa: S310 (the pool's address)
                    print(f"{name} [{i + 1}-{i + len(elements[i:i + batch])}]: {resp.read().decode()}")
            except OSError as exc:
                print(f"{name}: {exc}", file=sys.stderr)
                rc = 1
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nexus_catalog", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("serve")
    imp = sub.add_parser("import")
    imp.add_argument("files", nargs="+")
    imp.add_argument("--source", default="")
    psh = sub.add_parser("push")
    psh.add_argument("url")
    psh.add_argument("files", nargs="+")
    psh.add_argument("--batch", type=int, default=500)
    args = ap.parse_args(argv)
    if args.cmd == "import":
        return import_files(args.files, args.source)
    if args.cmd == "push":
        return push(args.url, args.files, max(1, min(args.batch, 1000)))
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
