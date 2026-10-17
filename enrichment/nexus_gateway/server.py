"""The HTTP side: SRU 1.1 / 1.2 on /sru/{database}, and /health.

    GET|POST /sru/_union    every source (the one Koha row ticked by default)
    GET|POST /sru/_union-aut  authority headings, for Koha's authority search
    GET|POST /sru/<id>      one catalogue of targets.json, or one static.db source
    GET|POST /sru           the same as /sru/_union
    GET      /health        {"status": "ok", "static": {...}, ...}

Koha's rows (Administration > Z39.50/SRU servers): SRU, host 127.0.0.1,
port 5000, database sru/<id>, syntax MARC21, encoding utf8; sru/_union-aut
is a row of record type authority.

Standard library only (ThreadingHTTPServer): the service stays small on a
WSL machine, and it only ever listens on 127.0.0.1.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

from nexus_enrich import marc

from . import __version__, cql, sru
from .config import Settings
from .engine import Engine, UnknownDatabase
from .targets import AUTH_UNION

log = logging.getLogger("nexus_gateway")
XML = "text/xml; charset=utf-8"
MAX_FORM = 64_000
TITLE = "koha.nexus (static.db + catálogos Z39.50/SRU)"
AUTH_TITLE = "koha.nexus (autoridades: BN, catálogos brasileiros, LoC)"


def answer(engine: Engine, settings: Settings, database: str, p: dict[str, str]) -> bytes:
    """The SRU response body for one request's parameters."""
    operation = p.get("operation", "").strip() or ("searchRetrieve" if p.get("query", "").strip() else "explain")
    version = p.get("version", "").strip() or "1.1"

    def fail(code: int, details: str, message: str) -> bytes:
        return sru.diagnostic_response(sru.Diagnostic(code, details, message), operation, version)

    if version not in ("1.1", "1.2"):
        return fail(sru.UNSUPPORTED_VERSION, "1.2", f"unsupported version {version}")
    try:
        engine.resolve(database)
    except UnknownDatabase:
        return fail(sru.UNKNOWN_DATABASE, database, f"no catalogue named {database!r}")
    if operation == "explain":
        return sru.explain_response(settings.host, settings.port, f"sru/{database or '_union'}",
                                    settings.max_records,
                                    AUTH_TITLE if database.strip("/").lower() == AUTH_UNION else TITLE, version)
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
        tree = cql.parse(query)
    except cql.CQLError as exc:
        return fail(sru.QUERY_SYNTAX_ERROR, query, str(exc))

    result = engine.search(database, tree, start, maximum)
    echo = {k: p.get(k, "") for k in ("query", "startRecord", "maximumRecords", "recordPacking", "recordSchema")}
    echo["version"] = version
    diags = []
    if result.total and start > result.total:
        diags.append(sru.Diagnostic(sru.FIRST_RECORD_OUT_OF_RANGE, str(start), "first record position out of range"))
    log.info("%s %r: %d (%s)%s", database or "_union", query, result.total, result.origin,
             f" errors: {result.errors}" if result.errors else "")
    return sru.search_retrieve_response(total=result.total, records=[marc.to_element(r) for r in result.records],
                                        start=start, packing=packing, echo=echo, version=version,
                                        diagnostics=diags)


def make_handler(engine: Engine, settings: Settings):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"koha.nexus-gateway/{__version__}"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):          # requests are logged by answer()
            log.debug("%s " + fmt, self.address_string(), *args)

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _route(self, params: dict[str, str]) -> None:
            path = urlsplit(self.path).path.rstrip("/")
            if path == "/health":
                body = json.dumps({"status": "ok", "version": __version__, "static": engine.static.info(),
                                   "live": settings.live,
                                   "targets": sum(1 for t in engine.targets.values() if t.live)})
                return self._send(200, body.encode(), "application/json")
            if path != "/sru" and not path.startswith("/sru/"):
                return self._send(404, b"not found\n", "text/plain")
            database = path[len("/sru/"):] if path.startswith("/sru/") else ""
            try:
                body = answer(engine, settings, database, params)
            except Exception as exc:                 # an SRU client reads diagnostics, not 500s
                log.exception("search failed")
                body = sru.diagnostic_response(sru.Diagnostic(sru.GENERAL_ERROR, type(exc).__name__, str(exc)))
            self._send(200, body, XML)

        def do_GET(self):
            self._route(dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True)))

        do_HEAD = do_GET

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_FORM:
                return self._send(413, b"request too large\n", "text/plain")
            form = self.rfile.read(length).decode("utf-8", "replace")
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))
            params.update(parse_qsl(form, keep_blank_values=True))
            self._route(params)

    return Handler


def make_server(engine: Engine, settings: Settings) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((settings.host, settings.port), make_handler(engine, settings))
    server.daemon_threads = True
    return server
