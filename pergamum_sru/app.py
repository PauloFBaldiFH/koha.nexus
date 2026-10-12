"""FastAPI app: the SRU 1.1 endpoint Koha talks to, on 127.0.0.1:5006.

The endpoint itself (GET, form and SOAP requests, diagnostics, explain) is
the Zeus bridge's; only the catalogue behind it differs."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from fastapi import FastAPI

from zeus_sru.app import sru_app
from zeus_sru.cql import ZeusQuery

from . import __version__
from .config import Settings
from .marc import text_to_marcxml
from .pergamum import PergamumClient


class PergamumBackend:
    """Koha first asks with maximumRecords=0 (the count only), then for a
    page: the result list is fetched once and cached, and only the records
    of the page asked for are fetched, one request each."""

    def __init__(self, client: PergamumClient):
        self.client = client

    async def search(self, query: ZeusQuery, start: int,
                     maximum: int) -> tuple[int, list[ET.Element]]:
        ids = await self.client.ids(query)
        # The count is what can be served: the ids of Pergamum's first page.
        page = ids[start - 1:start - 1 + maximum] if maximum else []
        blocks = await self.client.records(page)
        return len(ids), [text_to_marcxml(b) for b in blocks]

    async def aclose(self) -> None:
        await self.client.aclose()


def create_app(settings: Settings | None = None, client: PergamumClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    return sru_app(
        title="Pergamum SRU bridge", version=__version__, source="Rede Pergamum",
        max_records=settings.max_records, record_schema=settings.record_schema,
        open_backend=lambda: PergamumBackend(client or PergamumClient(settings)),
        health={"base_url": settings.base_url},
        explain={"title": "Catálogo Rede Pergamum (CRP) via SRU",
                 "description": "Rede Pergamum's shared catalogue (PUCPR, site CRP).",
                 "indexes": (("ISBN", "dc", "isbn"), ("Title", "dc", "title"),
                             ("Author", "dc", "author"), ("Any", "cql", "serverChoice"))})


app = create_app()
