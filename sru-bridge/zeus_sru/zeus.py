"""Searching Catálogo Zeus and pulling the MARC records out of its HTML."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import OrderedDict

import httpx
import pymarc

from . import marc
from .sru import SourceUnavailable
from .config import Settings
from .cql import ZeusQuery

log = logging.getLogger(__name__)

# rawRecord shows up as a hidden input or inside a URL / form body.
_INPUT_RE = re.compile(
    r"""<input\b[^>]*\bname\s*=\s*["']?rawRecord["']?[^>]*>""", re.I)
_VALUE_RE = re.compile(r"""\bvalue\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_PARAM_RE = re.compile(r"""rawRecord(?:=|%3D)([^"'&\s<>]+)""", re.I)


def extract_raw_records(page: str) -> list[str]:
    """Every rawRecord value in a Zeus result page, in page order, deduplicated."""
    found: list[tuple[int, str]] = []
    for m in _INPUT_RE.finditer(page):
        v = _VALUE_RE.search(m.group(0))
        if v:
            found.append((m.start(), v.group(1) if v.group(1) is not None else v.group(2)))
    for m in _PARAM_RE.finditer(page):
        found.append((m.start(), m.group(1)))
    seen, out = set(), []
    for _, value in sorted(found):
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


# Zeus /zeus/ embeds each result as MARCXML: <record>...</record> blocks
# holding a leader (prefixed or not, with or without the slim namespace).
_MARCXML_RE = re.compile(r"<(?:marc:)?record\b[^>]*>.*?</(?:marc:)?record>", re.S | re.I)


def extract_marcxml_records(page: str) -> list[str]:
    """Every MARCXML record block in a Zeus page, deduplicated, in order."""
    seen, out = set(), []
    for m in _MARCXML_RE.finditer(page):
        block = m.group(0)
        if "leader>" in block and block not in seen:
            seen.add(block)
            out.append(block)
    return out


def chunks(items: tuple[int, ...], size: int) -> list[tuple[int, ...]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_params(query: ZeusQuery, targets: tuple[int, ...]) -> list[tuple[str, str]]:
    params = [
        ("searchString", query.term),
        ("searchType", str(query.search_type)),
        ("operator", "and"),
    ]
    params += [(f"targets[{t}]", "on") for t in targets]
    return params


class ZeusClient:
    """Runs one Zeus search across every target, 15 at a time, concurrently."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=settings.timeout,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent,
                     "Referer": settings.base_url.split("/zeus")[0].split("/zbib")[0] + "/"},
        )
        self._cache: OrderedDict[ZeusQuery, tuple[float, list[pymarc.Record]]] = OrderedDict()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _fetch_chunk(self, query: ZeusQuery, targets: tuple[int, ...]) -> str:
        resp = await self._client.get(self.settings.base_url, params=build_params(query, targets))
        resp.raise_for_status()
        return resp.text

    async def search(self, query: ZeusQuery) -> list[pymarc.Record]:
        cached = self._cache_get(query)
        if cached is not None:
            return cached

        groups = chunks(self.settings.targets, self.settings.chunk_size)
        started = time.monotonic()
        pages = await asyncio.gather(
            *(self._fetch_chunk(query, g) for g in groups), return_exceptions=True)

        failures = [p for p in pages if isinstance(p, BaseException)]
        for group, page in zip(groups, pages):
            if isinstance(page, BaseException):
                log.warning("Zeus chunk %s failed: %r", list(group), page)
        if failures and len(failures) == len(pages):
            raise ZeusUnavailable(str(failures[0])) from failures[0]

        records, keys = [], set()
        for page in pages:
            if isinstance(page, BaseException):
                continue
            found = [marc.parse_marcxml(b) for b in extract_marcxml_records(page)]
            found += [marc.parse_record(marc.decode_raw(r)) for r in extract_raw_records(page)]
            for record in found:
                if record is None:
                    continue
                key = marc.record_key(record)
                if key not in keys:
                    keys.add(key)
                    records.append(record)

        log.info("Zeus %s %r: %d records from %d chunks (%d failed) in %.2fs",
                 query.kind, query.term, len(records), len(groups), len(failures),
                 time.monotonic() - started)
        # A partial failure is not cached, so the next page retries it.
        if not failures:
            self._cache_put(query, records)
        return records

    def _cache_get(self, query: ZeusQuery) -> list[pymarc.Record] | None:
        hit = self._cache.get(query)
        if hit is None:
            return None
        stamp, records = hit
        if time.monotonic() - stamp > self.settings.cache_ttl:
            self._cache.pop(query, None)
            return None
        self._cache.move_to_end(query)
        return records

    def _cache_put(self, query: ZeusQuery, records: list[pymarc.Record]) -> None:
        if self.settings.cache_ttl <= 0 or self.settings.cache_size <= 0:
            return
        self._cache[query] = (time.monotonic(), records)
        self._cache.move_to_end(query)
        while len(self._cache) > self.settings.cache_size:
            self._cache.popitem(last=False)


class ZeusUnavailable(SourceUnavailable):
    """Every chunk failed: Zeus is down or unreachable (SRU diagnostic 1)."""
