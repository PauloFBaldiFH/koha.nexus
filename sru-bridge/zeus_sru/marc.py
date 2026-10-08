"""rawRecord strings from Zeus -> pymarc Records -> MARCXML elements."""

from __future__ import annotations

import html
import io
import logging
from urllib.parse import unquote_to_bytes
from xml.etree import ElementTree as ET

import pymarc

log = logging.getLogger(__name__)

FT = b"\x1e"   # field terminator
RT = b"\x1d"   # record terminator


def decode_raw(raw: str) -> bytes:
    """A rawRecord value (form-urlencoded, maybe HTML-escaped) -> ISO 2709 bytes."""
    raw = html.unescape(raw.strip())
    return unquote_to_bytes(raw.replace("+", " "))


def _rebuild(data: bytes) -> bytes:
    """Recompute leader length, base address and directory from the fields.

    Some catalogues count characters instead of bytes, so a record with
    accents can carry offsets that no longer match. The field order in the
    directory is kept; only lengths and offsets are recalculated.
    """
    data = data.rstrip(RT)
    leader = data[:24]
    base = int(leader[12:17])
    directory = data[24:base].rstrip(FT)
    tags = [directory[i:i + 3] for i in range(0, len(directory) - len(directory) % 12, 12)]
    fields = data[base:].split(FT)
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) != len(tags):
        raise ValueError(f"{len(tags)} directory entries but {len(fields)} fields")

    entries, body, offset = [], [], 0
    for tag, value in zip(tags, fields):
        chunk = value + FT
        entries.append(tag + b"%04d%05d" % (len(chunk), offset))
        body.append(chunk)
        offset += len(chunk)
    new_dir = b"".join(entries) + FT
    new_base = 24 + len(new_dir)
    total = new_base + offset + 1
    new_leader = b"%05d" % total + leader[5:12] + b"%05d" % new_base + leader[17:24]
    return new_leader + new_dir + b"".join(body) + RT


def _read(data: bytes) -> pymarc.Record | None:
    reader = pymarc.MARCReader(io.BytesIO(data), to_unicode=True, force_utf8=False,
                               utf8_handling="replace", permissive=True)
    return next(iter(reader), None)


def parse_record(data: bytes) -> pymarc.Record | None:
    if len(data) < 25:
        return None
    if not data.endswith(RT):
        data += RT
    record = None
    try:
        record = _read(data)
    except Exception as exc:  # pymarc raises a family of RecordXxx errors
        log.debug("pymarc rejected record as-is: %s", exc)
    if record is None:
        try:
            record = _read(_rebuild(data))
        except Exception as exc:
            log.warning("unreadable MARC record skipped: %s", exc)
            return None
    if record is not None and record.leader is not None:
        # The record is UTF-8 from here on (pymarc decoded MARC-8 if needed).
        leader = str(record.leader)
        record.leader = pymarc.Leader(leader[:9] + "a" + leader[10:])
    return record


def to_marcxml(record: pymarc.Record) -> ET.Element:
    # Round-trip through bytes so the tags carry the MARC21/slim namespace
    # (record_to_xml_node only writes an xmlns attribute).
    return ET.fromstring(pymarc.record_to_xml(record, namespace=True))


def record_key(record: pymarc.Record) -> str:
    """Identity used to drop the same record arriving from two chunks."""
    return pymarc.record_to_xml(record).decode("utf-8", "replace")
