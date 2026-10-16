"""FastAPI app: one SRU 1.1 endpoint, /sru/{id}, for every catalogue in
targets.json. Koha's row for a catalogue is host <this server>, port 5000,
database sru/{id}, SRU, MARC21, utf8 (see README.md)."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from xml.etree import ElementTree as ET

import httpx
import pymarc
from fastapi import FastAPI

from pergamum_sru.app import PergamumBackend
from pergamum_sru.config import Settings as PergamumSettings
from pergamum_sru.pergamum import PergamumClient
from zeus_sru import marc, sru
from zeus_sru.app import ZeusBackend, sru_app
from zeus_sru.config import Settings as ZeusSettings
from zeus_sru.cql import ZeusQuery
from zeus_sru.zeus import ZeusClient

from . import __version__, targets, upstream_sru, z3950
from .config import Settings
from .targets import Target

log = logging.getLogger("sru_gateway")


def parse_iso(data: bytes, utf8: bool) -> pymarc.Record | None:
    """An ISO 2709 record from a Z39.50 server. A server set to utf8 often
    leaves leader/09 blank; the record is then read as UTF-8, not MARC-8."""
    if utf8 and len(data) > 9 and data[9:10] == b" ":
        data = data[:9] + b"a" + data[10:]
    return marc.parse_record(data)


class Z3950Backend:
    def __init__(self, target: Target, timeout: float):
        self.target, self.timeout, self.name = target, timeout, target.name

    async def search(self, query: ZeusQuery, start: int, maximum: int) -> tuple[int, list[ET.Element]]:
        t = self.target
        total, blobs = await z3950.search(t.host, t.port, t.db, query, start, maximum,
                                          user=t.user, password=t.password, timeout=self.timeout)
        records = [parse_iso(b, t.encoding.replace("-", "") == "utf8") for b in blobs]
        return total, [marc.to_marcxml(r) for r in records if r is not None]

    async def aclose(self) -> None:
        pass


class SRUBackend:
    def __init__(self, target: Target, client: httpx.AsyncClient):
        self.target, self.client, self.name = target, client, target.name

    async def search(self, query: ZeusQuery, start: int, maximum: int) -> tuple[int, list[ET.Element]]:
        total, records = await upstream_sru.search(self.client, self.target, query, start, maximum)
        return total, [marc.to_marcxml(r) for r in records[:maximum]]

    async def aclose(self) -> None:
        pass


class Named:
    """A Zeus or Pergamum backend under the name of its targets.json entry."""

    def __init__(self, inner, name: str, record_schema: str | None = None):
        self.inner, self.name = inner, name
        if record_schema:
            self.record_schema = record_schema

    async def search(self, query, start, maximum):
        return await self.inner.search(query, start, maximum)

    async def aclose(self) -> None:
        await self.inner.aclose()


class Gateway:
    """Picks the backend of /sru/{id}; Zeus and Pergamum clients are opened
    only when targets.json uses them."""

    def __init__(self, table: dict[str, Target], settings: Settings,
                 http: httpx.AsyncClient | None = None, zeus_http: httpx.AsyncClient | None = None,
                 pergamum: PergamumClient | None = None):
        """zeus_http, when given, is the HTTP client every zeus entry uses
        (tests pass a mocked one); else the first zeus entry opens one with
        Zeus's own headers (Referer, user agent) and the others share it."""
        self.table = table
        self.http = http or httpx.AsyncClient(timeout=settings.timeout, follow_redirects=True,
                                              headers={"User-Agent": settings.user_agent})
        self.backends: dict[str, object] = {}
        zeus_base = ZeusSettings.from_env()
        for t in table.values():
            if t.kind == "zeus":
                # One Zeus client per entry, each asking only for its own targets[n].
                zeus = ZeusClient(replace(zeus_base, targets=(t.target_index,)), client=zeus_http)
                zeus_http = zeus_http or zeus.http
                self.backends[t.id] = Named(ZeusBackend(zeus), t.name)
            elif t.kind == "pergamum":
                ps = PergamumSettings.from_env()
                pergamum = pergamum or PergamumClient(ps)
                self.backends[t.id] = Named(PergamumBackend(pergamum), t.name, ps.record_schema)
            elif t.kind == "z3950":
                self.backends[t.id] = Z3950Backend(t, settings.timeout)
            elif t.kind == "sru":
                self.backends[t.id] = SRUBackend(t, self.http)
        self._closers = [c for c in (zeus_http, pergamum) if c is not None]

    def for_database(self, database: str):
        tid = database.strip("/").rsplit("/", 1)[-1].lower()
        t = self.table.get(tid)
        if t is None:
            return sru.Diagnostic(sru.DATABASE_NOT_FOUND, tid or "(none)",
                                  f"Target not found or not configured: no catalogue {tid!r} here,"
                                  " use database sru/<id>")
        if not t.configured:
            return sru.Diagnostic(sru.GENERAL_ERROR, tid,
                                  f"{t.name}: no catalogue address configured yet")
        return self.backends[tid]

    async def search(self, query, start, maximum):
        # Only reached for /sru with no id, which has no catalogue.
        raise sru.SourceUnavailable("no catalogue id in the address")

    async def aclose(self) -> None:
        await self.http.aclose()
        for c in self._closers:
            await c.aclose()


class CollapseSlashes:
    """'//sru/bn' -> '/sru/bn': Koha joins host:port/db itself, so a database
    written '/sru/bn' arrives with two slashes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and "//" in scope.get("path", ""):
            scope = dict(scope, path=re.sub(r"/{2,}", "/", scope["path"]))
            scope["raw_path"] = scope["path"].encode()
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None, table: dict[str, Target] | None = None,
               **clients) -> CollapseSlashes:
    settings = settings or Settings.from_env()
    table = table if table is not None else targets.load(settings.targets_file)
    ready = sorted(t.id for t in table.values() if t.configured)
    missing = sorted(t.id for t in table.values() if not t.configured)
    api: FastAPI = sru_app(
        title="koha.nexus SRU gateway", version=__version__, source="SRU gateway",
        max_records=settings.max_records, openapi_url="/openapi.json",
        open_backend=lambda: Gateway(table, settings, **clients),
        health={"targets": len(table), "configured": ready, "missing": missing},
        explain={"title": "koha.nexus SRU gateway",
                 "description": "One SRU database per catalogue: sru/<id>.",
                 "indexes": (("ISBN", "dc", "isbn"), ("Title", "dc", "title"),
                             ("Author", "dc", "author"), ("Any", "cql", "serverChoice"))})
    wrapped = CollapseSlashes(api)
    wrapped.api = api
    return wrapped


app = create_app()
