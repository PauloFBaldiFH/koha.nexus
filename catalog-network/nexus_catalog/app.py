"""FastAPI app: the shared catalogue's SRU endpoint and its sync API.

    GET  /sru                 SRU 1.1 / 1.2 searchRetrieve and explain (what
                              Koha's Z39.50/SRU search talks to); POST forms
                              and SRW SOAP too, as YAZ may send them
    POST /api/records/sync    a koha.nexus library sends MARCXML records
                              (Authorization: Bearer TOKEN)
    GET  /health              {"status": "ok", "records": N, ...}

Koha's row (Administration > Z39.50/SRU servers): SRU, host
https://HOSTNAME, port 443, database "sru", syntax MARC21, encoding utf8.
"""

from __future__ import annotations

import hmac
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl
from xml.etree import ElementTree as ET

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import __version__, cql, marc, sru
from .config import Settings
from .db import Catalog

log = logging.getLogger("nexus_catalog")
XML = "text/xml; charset=utf-8"
SRU_PARAMS = ("operation", "version", "query", "startRecord", "maximumRecords", "recordPacking",
              "recordSchema", "sortKeys", "stylesheet", "resultSetTTL")
MIN_TOKEN = 24


class Tokens:
    """Who may sync: name -> token, from the settings' string and file.
    The file ("name token" or "name:token" lines, # comments) is read again
    whenever it changes, so a new library needs no restart."""

    def __init__(self, inline: str = "", path: Path | None = None):
        self.inline = self._parse(inline.replace(",", "\n"))
        self.path = path
        self._stamp: tuple | None = None
        self._from_file: dict[str, str] = {}

    @staticmethod
    def _parse(text: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for n, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, token = line.replace(":", " ", 1).partition(" ")
            name, token = (name, token.strip()) if sep else (f"library-{n}", name)
            if len(token) < MIN_TOKEN:
                log.warning("sync token of %s ignored: shorter than %d characters", name, MIN_TOKEN)
                continue
            out[name] = token
        return out

    def all(self) -> dict[str, str]:
        if self.path is not None:
            try:
                st = self.path.stat()
                stamp = (st.st_mtime_ns, st.st_size)
                if stamp != self._stamp:
                    self._from_file = self._parse(self.path.read_text(encoding="utf-8"))
                    self._stamp = stamp
            except OSError as exc:
                if self._stamp is not None:
                    log.warning("tokens file unreadable: %s", exc)
                self._from_file, self._stamp = {}, None
        return {**self.inline, **self._from_file}

    def who(self, header: str) -> str | None:
        """The library a bearer token belongs to; None when it is not one."""
        scheme, _, token = (header or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            return None
        found = None
        for name, known in self.all().items():
            if hmac.compare_digest(known.encode(), token.encode()):
                found = name
        return found


async def read_params(request: Request) -> tuple[dict[str, str], bool]:
    """The SRU parameters of a GET, a form POST or a SOAP (SRW) POST, and
    whether the request came as SOAP (the answer then goes back as SOAP).
    Body values win over the query string."""
    p: dict[str, str] = dict(request.query_params)
    if request.method != "POST":
        return p, False
    body = (await request.body())[:200_000].decode("utf-8", "replace").strip()
    if not body:
        return p, False
    if not body.startswith("<"):
        p.update(parse_qsl(body, keep_blank_values=True))
        return p, False
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        log.warning("unreadable XML body: %s", exc)
        return p, False
    soap = root.tag.endswith("}Envelope") or root.tag == "Envelope"
    for node in root.iter():
        name = node.tag.rsplit("}", 1)[-1]
        if name in ("searchRetrieveRequest", "explainRequest", "scanRequest"):
            p["operation"] = name[:-len("Request")]
            for child in node:
                key = child.tag.rsplit("}", 1)[-1]
                if key in SRU_PARAMS and child.text and child.text.strip():
                    p[key] = child.text.strip()
            break
    return p, soap


def create_app(settings: Settings | None = None, catalog: Catalog | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.catalog = catalog or Catalog(settings.db_path)
        log.info("catalog %s: %d records", settings.db_path, app.state.catalog.count())
        if not app.state.tokens.all():
            log.warning("no sync token set: POST /api/records/sync is closed")
        try:
            yield
        finally:
            if catalog is None:
                app.state.catalog.close()

    app = FastAPI(title="koha.nexus Catalog Network", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.tokens = Tokens(settings.tokens, settings.tokens_file)

    def xml(body: bytes) -> Response:
        return Response(content=body, media_type=XML)

    def fail(code: int, details: str, message: str, operation: str = "searchRetrieve",
             version: str = "1.1") -> Response:
        return xml(sru.diagnostic_response(sru.Diagnostic(code, details, message), operation, version))

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        count = await run_in_threadpool(request.app.state.catalog.count)
        return JSONResponse({"status": "ok", "version": __version__, "records": count,
                             "sync": bool(request.app.state.tokens.all())})

    @app.api_route("/sru", methods=["GET", "POST"])
    @app.api_route("/sru/{database:path}", methods=["GET", "POST"])
    async def sru_endpoint(request: Request) -> Response:
        p, soap = await read_params(request)
        resp = await handle(request, p)
        if soap:
            resp = xml(sru.soap_wrap(resp.body))
        return resp

    async def handle(request: Request, p: dict[str, str]) -> Response:
        operation = p.get("operation", "").strip() or ("searchRetrieve" if p.get("query", "").strip()
                                                       else "explain")
        version = p.get("version", "").strip() or "1.1"
        if version not in ("1.1", "1.2"):
            return fail(sru.UNSUPPORTED_VERSION, "1.2", f"unsupported version {version}", operation)

        if operation == "explain":
            url = request.url
            return xml(sru.explain_response(url.hostname or settings.host, url.port or 443,
                                            url.path.lstrip("/") or "sru", settings.max_records,
                                            settings.database_title, version))
        if operation != "searchRetrieve":
            return fail(sru.UNSUPPORTED_OPERATION, operation, f"unsupported operation {operation}",
                        version=version)

        query = p.get("query", "")
        if not query.strip():
            return fail(sru.MANDATORY_PARAMETER_MISSING, "query", "query is required", version=version)
        schema = p.get("recordSchema", "").strip()
        if schema.lower() not in sru.MARCXML_NAMES:
            return fail(sru.UNKNOWN_SCHEMA, schema, "only MARCXML records are served", version=version)
        packing = p.get("recordPacking", "xml").strip().lower() or "xml"
        if packing not in ("xml", "string"):
            return fail(sru.UNSUPPORTED_PACKING, packing, "recordPacking must be xml or string", version=version)
        try:
            start = int(p.get("startRecord", "1") or 1)
            maximum = int(p.get("maximumRecords", "10") or 10)
        except ValueError as exc:
            return fail(sru.UNSUPPORTED_PARAMETER_VALUE, "startRecord/maximumRecords", str(exc), version=version)
        if start < 1:
            return fail(sru.UNSUPPORTED_PARAMETER_VALUE, "startRecord", "startRecord must be >= 1", version=version)
        maximum = max(0, min(maximum, settings.max_records))

        try:
            tree = cql.parse(query)
            total, rows = await run_in_threadpool(request.app.state.catalog.search, tree, start, maximum)
        except cql.CQLError as exc:
            return fail(sru.QUERY_SYNTAX_ERROR, query, str(exc), version=version)

        echo = {k: p.get(k, "") for k in ("query", "startRecord", "maximumRecords", "recordPacking",
                                          "recordSchema")}
        echo["version"] = version
        if total and start > total:
            return xml(sru.search_retrieve_response(
                total=total, records=[], start=start, echo=echo, version=version,
                diagnostics=[sru.Diagnostic(sru.FIRST_RECORD_OUT_OF_RANGE, str(start),
                                            "first record position out of range")]))
        return xml(sru.search_retrieve_response(
            total=total, records=[ET.fromstring(r) for r in rows], start=start,
            packing=packing, echo=echo, version=version))

    @app.post("/api/records/sync")
    async def sync(request: Request) -> JSONResponse:
        tokens: Tokens = request.app.state.tokens
        if not tokens.all():
            return JSONResponse({"error": "sync is not enabled on this server"}, status_code=503)
        library = tokens.who(request.headers.get("authorization", ""))
        if library is None:
            return JSONResponse({"error": "a valid bearer token is required"}, status_code=401,
                                headers={"WWW-Authenticate": "Bearer"})
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > settings.max_body:
            return JSONResponse({"error": f"body larger than {settings.max_body} bytes"}, status_code=413)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > settings.max_body:
                return JSONResponse({"error": f"body larger than {settings.max_body} bytes"}, status_code=413)
        if not body.strip():
            return JSONResponse({"error": "no records sent"}, status_code=400)

        elements: list[ET.Element] = []
        rejected: list[dict] = []
        try:
            if "json" in request.headers.get("content-type", "").lower():
                data = json.loads(body)
                items = data.get("records") if isinstance(data, dict) else data
                if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
                    raise marc.RecordError('JSON must be {"records": ["<record>...</record>", ...]}')
                for item in items:
                    elements.extend(marc.split_records(item))
            else:
                elements = marc.split_records(bytes(body))
        except (ValueError, marc.RecordError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if not elements:
            return JSONResponse({"error": "no MARCXML <record> with a <leader> found"}, status_code=400)
        if len(elements) > settings.max_sync_records:
            return JSONResponse({"error": f"more than {settings.max_sync_records} records in one request"},
                                status_code=413)

        records = []
        for i, el in enumerate(elements):
            try:
                records.append(marc.read(el, settings.max_record_bytes))
            except marc.RecordError as exc:
                rejected.append({"index": i, "error": str(exc)})
        counts = await run_in_threadpool(request.app.state.catalog.put_many, records, library)
        log.info("sync from %s: %d received, %s, %d rejected", library, len(elements), counts, len(rejected))
        return JSONResponse({"library": library, "received": len(elements), **counts,
                             "rejected": rejected})

    return app


app = create_app()
