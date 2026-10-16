"""FastAPI app: the SRU 1.1 endpoint Koha talks to.

Register it in Koha (Administration > Z39.50/SRU servers > New SRU server):
host 127.0.0.1, port 5000, database "sru", record syntax MARC21/USMARC,
encoding UTF-8. See README.md for the SRU search field mapping.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Callable, Protocol
from urllib.parse import parse_qsl
from xml.etree import ElementTree as ET

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from . import __version__, cql, marc, sru
from .config import Settings
from .zeus import ZeusClient

log = logging.getLogger("zeus_sru")
XML = "text/xml; charset=utf-8"
SRU_PARAMS = ("operation", "version", "query", "startRecord", "maximumRecords", "recordPacking",
              "recordSchema", "sortKeys", "stylesheet", "resultSetTTL")


class Backend(Protocol):
    async def search(self, query: cql.ZeusQuery, start: int,
                     maximum: int) -> tuple[int, list[ET.Element]]: ...

    async def aclose(self) -> None: ...


async def read_params(request: Request) -> tuple[dict[str, str], bool]:
    """The SRU parameters of a GET, a form POST or a SOAP (SRW) POST, and
    whether the request came as SOAP (the answer then goes back as SOAP).

    YAZ, which Koha uses through ZOOM, may send any of the three. Body
    values win over the query string."""
    p: dict[str, str] = dict(request.query_params)
    if request.method != "POST":
        return p, False
    body = (await request.body()).decode("utf-8", "replace").strip()
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


class ZeusBackend:
    """Zeus answers a search with every record at once; pages are sliced here."""

    def __init__(self, client: ZeusClient):
        self.client = client

    async def search(self, query: cql.ZeusQuery, start: int,
                     maximum: int) -> tuple[int, list[ET.Element]]:
        records = await self.client.search(query)
        page = records[start - 1:start - 1 + maximum]
        return len(records), [marc.to_marcxml(r) for r in page]

    async def aclose(self) -> None:
        await self.client.aclose()


def create_app(settings: Settings | None = None, client: ZeusClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    return sru_app(
        title="Zeus SRU bridge", version=__version__, source="Catálogo Zeus",
        max_records=settings.max_records,
        open_backend=lambda: ZeusBackend(client or ZeusClient(settings)),
        health={"targets": list(settings.targets), "chunk_size": settings.chunk_size})


def sru_app(*, title: str, version: str, source: str, max_records: int,
            open_backend: Callable[[], Backend], health: dict | None = None,
            explain: dict | None = None, record_schema: str = sru.MARCXML_SCHEMA,
            openapi_url: str | None = None) -> FastAPI:
    """The SRU 1.1 endpoint shared by the bridges in this directory.

    open_backend() is called once at startup; its search(query, start,
    maximum) returns the hit count and the MARCXML records of that page, and
    raises sru.SourceUnavailable when the catalogue behind it is down.

    Every answer is SRU XML, errors included: YAZ (Koha's ZOOM client) reads
    FastAPI's JSON 404 as "wrong protocol", so an unknown path or method gets
    an explainResponse diagnostic with HTTP 200 instead."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.backend = open_backend()
        try:
            yield
        finally:
            await app.state.backend.aclose()

    app = FastAPI(title=title, version=version, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=openapi_url)

    def xml(body: bytes) -> Response:
        return Response(content=body, media_type=XML)

    def fail(code: int, details: str, message: str, operation: str = "searchRetrieve") -> Response:
        return xml(sru.diagnostic_response(sru.Diagnostic(code, details, message), operation))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        if exc.status_code == 404:
            return fail(sru.DATABASE_NOT_FOUND, request.url.path,
                        "Target not found or not configured: use /sru/<id>", "explain")
        if exc.status_code == 405:
            return fail(sru.UNSUPPORTED_OPERATION, request.method,
                        f"method {request.method} not supported: use GET or POST", "explain")
        return fail(sru.GENERAL_ERROR, request.url.path, str(exc.detail), "explain")

    @app.exception_handler(RequestValidationError)
    async def bad_request(request: Request, exc: RequestValidationError) -> Response:
        return fail(sru.UNSUPPORTED_PARAMETER_VALUE, request.url.path, "malformed request", "explain")

    @app.get("/health")
    async def health_endpoint() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": version, **(health or {})})

    # One route per method keeps the operation ids of /openapi.json distinct.
    @app.get("/sru")
    @app.post("/sru")
    @app.get("/sru/{database:path}")
    @app.post("/sru/{database:path}")
    async def sru_endpoint(request: Request, database: str = "") -> Response:
        p, soap = await read_params(request)
        resp = await handle(request, p, database.strip("/"))
        if soap:
            resp = xml(sru.soap_wrap(resp.body))
        return resp

    async def handle(request: Request, p: dict[str, str], database: str = "") -> Response:
        # SRU parameter names are case-sensitive; Koha sends them as spelled here.
        operation = p.get("operation", "").strip() or ("searchRetrieve" if p.get("query", "").strip()
                                                       else "explain")
        version = p.get("version", "1.1")

        if version not in ("1.1", "1.2"):
            return fail(sru.UNSUPPORTED_VERSION, "1.1", f"unsupported version {version}", operation)

        # A backend with for_database() serves several catalogues, one per
        # /sru/{database}; it answers a Diagnostic for a database it cannot
        # serve, under explain as well as under searchRetrieve.
        backend, name, schema_out = request.app.state.backend, source, record_schema
        pick = getattr(backend, "for_database", None)
        if pick is not None and (database or operation != "explain"):
            backend = pick(database)
            if isinstance(backend, sru.Diagnostic):
                return xml(sru.diagnostic_response(
                    backend, "explain" if operation == "explain" else "searchRetrieve"))
            name = getattr(backend, "name", name)
            schema_out = getattr(backend, "record_schema", schema_out)

        if operation == "explain":
            url = request.url
            info = dict(explain or {})
            if pick is not None and database:
                info["title"] = f"{name} (koha.nexus SRU gateway)"
            return xml(sru.explain_response(url.hostname or "127.0.0.1", url.port or 80,
                                            url.path.strip("/") or "sru", max_records, **info))
        if operation != "searchRetrieve":
            return fail(sru.UNSUPPORTED_OPERATION, operation, f"unsupported operation {operation}")

        query = p.get("query", "")
        if not query.strip():
            return fail(sru.MANDATORY_PARAMETER_MISSING, "query", "query is required")

        schema = p.get("recordSchema", "").strip()
        if schema.lower() not in sru.MARCXML_NAMES:
            return fail(sru.UNKNOWN_SCHEMA, schema, "only MARCXML records are served")
        packing = p.get("recordPacking", "xml").strip().lower() or "xml"
        if packing not in ("xml", "string"):
            return fail(sru.UNSUPPORTED_PACKING, packing, "recordPacking must be xml or string")

        try:
            start = int(p.get("startRecord", "1") or 1)
            maximum = int(p.get("maximumRecords", "10") or 10)
        except ValueError as exc:
            return fail(sru.UNSUPPORTED_PARAMETER_VALUE, "startRecord/maximumRecords", str(exc))
        if start < 1:
            return fail(sru.UNSUPPORTED_PARAMETER_VALUE, "startRecord", "startRecord must be >= 1")
        maximum = max(0, min(maximum, max_records))

        try:
            q = cql.parse(query)
        except cql.CQLError as exc:
            return fail(sru.QUERY_SYNTAX_ERROR, query, str(exc))

        try:
            total, records = await backend.search(q, start, maximum)
        except sru.DiagnosticError as exc:
            return xml(sru.diagnostic_response(exc.diagnostic))
        except sru.SourceUnavailable as exc:
            log.error("%s unreachable: %s", name, exc)
            return fail(sru.GENERAL_ERROR, name, getattr(exc, "sru_message", "") or f"{name} did not answer")

        echo = {k: p.get(k, "") for k in ("version", "query", "startRecord", "maximumRecords",
                                          "recordPacking", "recordSchema")}
        echo["version"] = "1.1"
        if total and start > total:
            return xml(sru.search_retrieve_response(
                total=total, records=[], start=start, echo=echo, schema=schema_out,
                diagnostics=[sru.Diagnostic(sru.FIRST_RECORD_OUT_OF_RANGE, str(start),
                                            "first record position out of range")]))
        body = sru.search_retrieve_response(
            total=total, records=records, start=start,
            packing=packing, echo=echo, schema=schema_out)
        return xml(body)

    return app


app = create_app()
