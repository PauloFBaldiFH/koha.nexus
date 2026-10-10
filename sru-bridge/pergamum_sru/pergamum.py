"""Searching Rede Pergamum through its Sajax calls and reading the MARC text.

A search is two kinds of GET on pesquisa.php:
  rs=ajax_resultados        the result list; each hit links mostrar_marc(<acervo id>)
  rs=ajax_conteudo_pastas   one record's tabs; the MARC text sits between
                            <inicio> and <fim>
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import OrderedDict
from typing import Hashable

import httpx

from zeus_sru.cql import AUTHOR, ISBN, ZeusQuery
from zeus_sru.sru import SourceUnavailable

from .config import Settings

log = logging.getLogger(__name__)

_COUNT_RE = re.compile(r"N\S{0,8}?mero de Registros Encontrados\s*:?\s*(?:<[^>]*>\s*)*(\d[\d.]*)", re.I)
_ID_RE = re.compile(r"mostrar_marc\((\d+)\)")
_MARC_RE = re.compile(r"(?:<|&lt;)inicio(?:>|&gt;)(.*?)(?:<|&lt;)fim(?:>|&gt;)", re.S)


def search_type(query: ZeusQuery) -> str:
    """Pergamum's search type: ISBN, AUTOR, else TITULO (also for "any")."""
    return {ISBN: "ISBN", AUTHOR: "AUTOR"}.get(query.search_type, "TITULO")


def search_params(term: str, kind: str, page_size: int) -> list[tuple[str, str]]:
    args = ["0", term, kind, "obra", str(page_size), "", "", "", "-1"]
    return [("rs", "ajax_resultados"), ("rst", ""), ("rsrnd", "1234567890")] + \
        [("rsargs[]", a) for a in args]


def record_params(acervo_id: str) -> list[tuple[str, str]]:
    return [("rs", "ajax_conteudo_pastas"), ("rst", ""), ("rsrnd", "1234567890"),
            ("rsargs[]", acervo_id)]


def parse_results(page: str) -> tuple[int, list[str]]:
    """The count Pergamum reports (0 when absent) and the acervo ids, in order."""
    m = _COUNT_RE.search(page)
    count = int(m.group(1).replace(".", "")) if m else 0
    return count, list(dict.fromkeys(_ID_RE.findall(page)))


def extract_marc(page: str) -> str | None:
    m = _MARC_RE.search(page)
    return m.group(1) if m else None


def decode(resp: httpx.Response) -> str:
    """The page as text: the declared charset, else UTF-8, else Latin-1
    (what requests, which the first version of this bridge used, falls back to)."""
    if resp.charset_encoding:
        return resp.text
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError:
        return resp.content.decode("iso-8859-1")


class _TTLCache:
    def __init__(self, ttl: int, size: int):
        self.ttl, self.size = ttl, size
        self._data: OrderedDict[Hashable, tuple[float, object]] = OrderedDict()

    def get(self, key: Hashable):
        hit = self._data.get(key)
        if hit is None or time.monotonic() - hit[0] > self.ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return hit[1]

    def put(self, key: Hashable, value: object) -> None:
        if self.ttl <= 0 or self.size <= 0:
            return
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self.size:
            self._data.popitem(last=False)


class PergamumClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=settings.timeout, follow_redirects=True,
            headers={"User-Agent": settings.user_agent, "Referer": settings.base_url})
        self._searches = _TTLCache(settings.cache_ttl, settings.cache_size)
        self._records = _TTLCache(settings.cache_ttl, settings.cache_size)
        self._gate = asyncio.Semaphore(settings.concurrency)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, params: list[tuple[str, str]]) -> str:
        resp = await self._client.get(self.settings.base_url, params=params)
        resp.raise_for_status()
        return decode(resp)

    async def ids(self, query: ZeusQuery) -> list[str]:
        """The acervo ids of a search, first page only (page_size of them)."""
        kind = search_type(query)
        key = (kind, query.term)
        cached = self._searches.get(key)
        if cached is not None:
            return cached
        started = time.monotonic()
        try:
            page = await self._get(search_params(query.term, kind, self.settings.page_size))
        except httpx.HTTPError as exc:
            raise PergamumUnavailable(repr(exc)) from exc
        count, ids = parse_results(page)
        log.info("Pergamum %s %r: %d reported, %d ids in %.2fs",
                 kind, query.term, count, len(ids), time.monotonic() - started)
        self._searches.put(key, ids)
        return ids

    async def marc_text(self, acervo_id: str) -> str | None:
        cached = self._records.get(acervo_id)
        if cached is not None:
            return cached
        async with self._gate:
            try:
                page = await self._get(record_params(acervo_id))
            except httpx.HTTPError as exc:
                log.warning("Pergamum record %s failed: %r", acervo_id, exc)
                return None
        block = extract_marc(page)
        if block is None:
            log.warning("Pergamum record %s: no <inicio>...<fim> block", acervo_id)
            return None
        self._records.put(acervo_id, block)
        return block

    async def records(self, ids: list[str]) -> list[str]:
        """The MARC text of each id, in order; the ones that fail are left out."""
        blocks = await asyncio.gather(*(self.marc_text(i) for i in ids))
        return [b for b in blocks if b]


class PergamumUnavailable(SourceUnavailable):
    """The result list did not come back (SRU diagnostic 1)."""
