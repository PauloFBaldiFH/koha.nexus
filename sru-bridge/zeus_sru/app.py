"""FastAPI app: the SRU 1.1 endpoint Koha talks to.

Register it in Koha (Administration > Z39.50/SRU servers > New SRU server):
host 127.0.0.1, port 5000, database "sru", record syntax MARC21/USMARC,
encoding UTF-8. See README.md for the SRU search field mapping.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from . import __version__, cql, marc, sru
from .config import Settings
from .zeus import ZeusClient, ZeusUnavailable

log = logging.getLogger("zeus_sru")
XML = "text/xml; charset=utf-8"


def create_app(settings: Settings | None = None, client: ZeusClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.zeus = client or ZeusClient(settings)
        try:
            yield
        finally:
            await app.state.zeus.aclose()

    app = FastAPI(title="Zeus SRU bridge", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings

    def xml(body: bytes) -> Response:
        return Response(content=body, media_type=XML)

    def fail(code: int, details: str, message: str, operation: str = "searchRetrieve") -> Response:
        return xml(sru.diagnostic_response(sru.Diagnostic(code, details, message), operation))

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__,
                             "targets": list(settings.targets), "chunk_size": settings.chunk_size})

    @app.get("/sru")
    @app.get("/sru/{database:path}")
    async def sru_endpoint(request: Request, database: str = "") -> Response:
        # SRU parameter names are case-sensitive; Koha sends them as spelled here.
        p = request.query_params
        operation = p.get("operation", "explain" if "query" not in p else "searchRetrieve")
        version = p.get("version", "1.1")

        if version not in ("1.1", "1.2"):
            return fail(sru.UNSUPPORTED_VERSION, "1.1", f"unsupported version {version}", operation)

        if operation == "explain":
            url = request.url
            return xml(sru.explain_response(url.hostname or "127.0.0.1", url.port or 80,
                                            url.path.lstrip("/") or "sru", settings.max_records))
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
        maximum = max(0, min(maximum, settings.max_records))

        try:
            zq = cql.parse(query)
        except cql.CQLError as exc:
            return fail(sru.QUERY_SYNTAX_ERROR, query, str(exc))

        try:
            records = await request.app.state.zeus.search(zq)
        except ZeusUnavailable as exc:
            log.error("Zeus unreachable: %s", exc)
            return fail(sru.GENERAL_ERROR, "Catálogo Zeus", "Catálogo Zeus did not answer")

        total = len(records)
        echo = {k: p.get(k, "") for k in ("version", "query", "startRecord", "maximumRecords",
                                          "recordPacking", "recordSchema")}
        echo["version"] = "1.1"
        if total and start > total:
            return xml(sru.search_retrieve_response(
                total=total, records=[], start=start, echo=echo,
                diagnostics=[sru.Diagnostic(sru.FIRST_RECORD_OUT_OF_RANGE, str(start),
                                            "first record position out of range")]))
        page = records[start - 1:start - 1 + maximum]
        body = sru.search_retrieve_response(
            total=total, records=[marc.to_marcxml(r) for r in page], start=start,
            packing=packing, echo=echo)
        return xml(body)

    return app


app = create_app()
