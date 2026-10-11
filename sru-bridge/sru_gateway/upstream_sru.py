"""Searching a remote SRU server and handing its MARCXML records on."""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET

import httpx
import pymarc

from zeus_sru import marc
from zeus_sru.cql import AUTHOR, ISBN, TITLE, ZeusQuery
from zeus_sru.sru import SourceUnavailable

from .targets import Target

log = logging.getLogger(__name__)
KIND = {ISBN: "isbn", TITLE: "title", AUTHOR: "author"}


class UpstreamError(SourceUnavailable):
    def __init__(self, message: str):
        super().__init__(message)
        self.sru_message = message


def cql_for(target: Target, query: ZeusQuery) -> str:
    """The query rebuilt with the remote server's own index names."""
    term = query.term.replace("\\", "\\\\").replace('"', '\\"')
    return f'{target.index(KIND.get(query.search_type, "any"))}="{term}"'


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_response(text: str | bytes) -> tuple[int, list[pymarc.Record], str]:
    """(numberOfRecords, records, first diagnostic message) of a
    searchRetrieveResponse, whatever its namespace prefixes and packing."""
    root = ET.fromstring(text)
    total, records, diag = 0, [], ""
    for node in root.iter():
        name = _local(node.tag)
        if name == "numberOfRecords" and node.text:
            total = int(node.text.strip() or 0)
        elif name == "recordData":
            record = _record_in(node)
            if record is not None:
                records.append(record)
        elif name == "diagnostic" and not diag:
            parts = {_local(c.tag): (c.text or "").strip() for c in node}
            diag = parts.get("message") or parts.get("details") or parts.get("uri", "")
    return total, records, diag


def _record_in(data: ET.Element) -> pymarc.Record | None:
    found = next((n for n in data.iter() if _local(n.tag) == "record" and n is not data), None)
    if found is None and data.text and "<" in data.text:
        # recordPacking string: the record is escaped text.
        return marc.parse_marcxml(data.text.strip())
    if found is None:
        return None
    return marc.parse_marcxml(_strip_ns(found))


def _strip_ns(node: ET.Element) -> str:
    """The record re-serialized in the MARC21/slim namespace, whatever prefix
    or namespace the server used."""
    copy = ET.fromstring(ET.tostring(node))
    for n in copy.iter():
        n.tag = _local(n.tag)
    text = ET.tostring(copy, encoding="unicode")
    return text.replace("<record", f'<record xmlns="{marc._SLIM}"', 1)


async def search(client: httpx.AsyncClient, target: Target, query: ZeusQuery, start: int,
                 maximum: int) -> tuple[int, list[pymarc.Record]]:
    params = {"version": target.version, "operation": "searchRetrieve",
              "query": cql_for(target, query), "startRecord": str(start),
              "maximumRecords": str(maximum), "recordSchema": target.schema,
              "recordPacking": "xml"}
    auth = (target.user, target.password) if target.user else None
    try:
        resp = await client.get(target.url, params=params, auth=auth)
        resp.raise_for_status()
        total, records, diag = parse_response(resp.content)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"{target.name} did not answer: {type(exc).__name__}") from exc
    except ET.ParseError as exc:
        raise UpstreamError(f"{target.name} answered something that is not SRU XML") from exc
    if diag and not records and not total:
        raise UpstreamError(f"{target.name}: {diag}")
    return total, records


