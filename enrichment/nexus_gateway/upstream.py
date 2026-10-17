"""Searching a remote SRU server (standard library HTTP, no scraping)."""

from __future__ import annotations

import base64
import urllib.error
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET

from nexus_enrich import marc

from .targets import Target

USER_AGENT = "koha.nexus-gateway"
MAX_BYTES = 20_000_000


class UpstreamError(Exception):
    """The server did not answer, or answered something that is not SRU."""


def cql_for(target: Target, kind: str, term: str) -> str:
    """The query in the remote server's own index names."""
    term = term.replace("\\", "\\\\").replace('"', '\\"')
    return f'{target.index(kind)}="{term}"'


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_response(text: bytes | str) -> tuple[int, list[marc.Record], str]:
    """(numberOfRecords, records, first diagnostic message) of a
    searchRetrieveResponse, whatever its prefixes and record packing."""
    root = ET.fromstring(text)
    total, records, diag = 0, [], ""
    for node in root.iter():
        name = _local(node.tag)
        if name == "numberOfRecords" and node.text and node.text.strip().isdigit():
            total = int(node.text.strip())
        elif name == "recordData":
            if len(node):
                found = [marc.from_element(n) for n in node.iter()
                         if _local(n.tag) == "record" and any(_local(c.tag) == "leader" for c in n)]
                records.extend(found[:1])
            elif node.text and "<" in node.text:       # recordPacking string
                records.extend(marc.parse_xml(node.text.strip())[:1])
        elif name == "diagnostic" and not diag:
            parts = {_local(c.tag): (c.text or "").strip() for c in node}
            diag = parts.get("message") or parts.get("details") or parts.get("uri", "")
    return total, records, diag


def search(target: Target, kind: str, term: str, start: int, maximum: int,
           timeout: float = 25.0) -> tuple[int, list[marc.Record]]:
    params = {"version": target.version, "operation": "searchRetrieve", "query": cql_for(target, kind, term),
              "startRecord": str(start), "maximumRecords": str(maximum), "recordSchema": target.schema,
              "recordPacking": "xml"}
    url = target.url + ("&" if "?" in target.url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml, text/xml"})
    if target.user:
        token = base64.b64encode(f"{target.user}:{target.password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpstreamError(f"{target.id} did not answer: {type(exc).__name__}: {exc}") from exc
    if len(body) > MAX_BYTES:
        raise UpstreamError(f"{target.id} answered more than {MAX_BYTES} bytes")
    try:
        total, records, diag = parse_response(body)
    except (ET.ParseError, marc.RecordError) as exc:
        raise UpstreamError(f"{target.id} answered something that is not SRU XML") from exc
    if diag and not records and not total:
        raise UpstreamError(f"{target.id}: {diag}")
    return total, records
