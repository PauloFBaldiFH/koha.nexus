"""Streaming readers for the harvest dumps: every file is read one record at
a time, so memory stays flat whatever the file size.

Formats (by extension after any .zst/.gz/.xz/.bz2, else by the first
bytes):
    jsonl     .jsonl .ndjson .json   one JSON object per line
    marcxml   .xml .marcxml          <collection> / <record>
    iso2709   .mrc .marc .iso .dat   binary MARC
    pool      .db .sqlite            catalog-network's pool (nexus_catalog)

A JSON line may carry the record as MARCXML ("marcxml", "marc_xml",
"xml", "record", "marc"), as ISO 2709 text ("iso2709", "mrc", "raw"), or
as MARC-in-JSON ({"leader", "fields"}, also under "marc" / "record").
Its id comes from "remote_id", "id", "_id", "control_number", "recid" or
"source_id", else from 001. Lines that hold none of these are counted as
errors with their keys, so an unknown dump layout shows up in the report
instead of silently loading nothing.
"""

from __future__ import annotations

import bz2
import gzip
import io
import json
import lzma
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator

from nexus_enrich import marc

_COMPRESSED = {".zst": "zstd", ".zstd": "zstd", ".gz": "gzip", ".xz": "xz", ".bz2": "bz2"}
_FORMATS = {".jsonl": "jsonl", ".ndjson": "jsonl", ".json": "jsonl", ".xml": "marcxml", ".marcxml": "marcxml",
            ".mrc": "iso2709", ".marc": "iso2709", ".iso": "iso2709", ".dat": "iso2709",
            ".db": "pool", ".sqlite": "pool", ".sqlite3": "pool"}
_XML_KEYS = ("marcxml", "marc_xml", "xml", "record", "marc")
_ISO_KEYS = ("iso2709", "mrc", "raw")
_ID_KEYS = ("remote_id", "id", "_id", "control_number", "recid", "source_id")


@dataclass
class Item:
    """One record read from a dump, or the error that replaced it."""
    record: marc.Record | None
    remote_id: str = ""
    source: str = ""          # from the line itself (config "source_field"), else ""
    error: str = ""


def open_stream(path: Path) -> IO[bytes]:
    """A binary file object, decompressing on the fly."""
    kind = _COMPRESSED.get(path.suffix.lower())
    if kind == "zstd":
        import zstandard
        fh = open(path, "rb")
        return zstandard.ZstdDecompressor().stream_reader(fh, closefd=True)
    if kind == "gzip":
        return gzip.open(path, "rb")
    if kind == "xz":
        return lzma.open(path, "rb")
    if kind == "bz2":
        return bz2.open(path, "rb")
    return open(path, "rb")


def detect(path: Path) -> str:
    name = path
    if name.suffix.lower() in _COMPRESSED:
        name = name.with_suffix("")
    fmt = _FORMATS.get(name.suffix.lower())
    if fmt:
        return fmt
    with open_stream(path) as fh:
        head = fh.read(64).lstrip()
    if head.startswith(b"SQLite format 3"):
        return "pool"
    if head.startswith(b"<"):
        return "marcxml"
    if head.startswith(b"{"):
        return "jsonl"
    if head[:5].isdigit():
        return "iso2709"
    raise ValueError(f"{path}: cannot tell the format from the name or the first bytes")


def _id_of(rec: marc.Record) -> str:
    return rec.control("001").strip()


def _from_json(obj: dict) -> marc.Record:
    for key in _XML_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and value.lstrip().startswith("<"):
            records = marc.parse_xml(value)
            if not records:
                raise marc.RecordError(f'"{key}" holds no MARCXML record')
            return records[0]
        if isinstance(value, dict) and "leader" in value:
            return marc.from_json(value)
    for key in _ISO_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and "\x1e" in value:
            return marc.from_iso2709(value.encode("utf-8"))
    if "leader" in obj and "fields" in obj:
        return marc.from_json(obj)
    raise marc.RecordError("no record in keys: " + ", ".join(sorted(obj)[:12]))


def read_jsonl(stream: IO[bytes], source_field: str = "") -> Iterator[Item]:
    text = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")
    for n, line in enumerate(text, 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            rec = _from_json(obj)
        except (ValueError, marc.RecordError) as exc:
            yield Item(None, error=f"line {n}: {exc}")
            continue
        remote = next((str(obj[k]) for k in _ID_KEYS if obj.get(k) not in (None, "")), "") or _id_of(rec)
        source = str(obj.get(source_field, "")) if source_field else ""
        yield Item(rec, remote, source)


def read_marcxml(stream: IO[bytes]) -> Iterator[Item]:
    try:
        for rec in marc.iter_xml(stream):
            yield Item(rec, _id_of(rec))
    except Exception as exc:     # a truncated or broken file: report it, keep what was read
        yield Item(None, error=f"XML stopped: {exc}")


def read_iso2709(stream: IO[bytes]) -> Iterator[Item]:
    for n, raw in enumerate(marc.iter_iso2709(stream), 1):
        try:
            rec = marc.from_iso2709(raw)
        except (ValueError, marc.RecordError) as exc:
            yield Item(None, error=f"record {n}: {exc}")
            continue
        yield Item(rec, _id_of(rec))


def read_pool(path: Path, source_field: str = "") -> Iterator[Item]:
    """catalog-network's pool: SELECT id, source, marcxml FROM records."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        for rid, source, xml in conn.execute("SELECT id, source, marcxml FROM records ORDER BY id"):
            try:
                rec = marc.parse_xml(xml)[0]
            except (IndexError, marc.RecordError) as exc:
                yield Item(None, error=f"pool row {rid}: {exc}")
                continue
            yield Item(rec, _id_of(rec) or f"pool:{rid}", source if source_field else "")
    finally:
        conn.close()


def read(path: Path, fmt: str = "auto", source_field: str = "") -> Iterator[Item]:
    fmt = detect(path) if fmt == "auto" else fmt
    if fmt == "pool":
        yield from read_pool(path, source_field)
        return
    with open_stream(path) as fh:
        if fmt == "jsonl":
            yield from read_jsonl(fh, source_field)
        elif fmt == "marcxml":
            yield from read_marcxml(fh)
        elif fmt == "iso2709":
            yield from read_iso2709(fh)
        else:
            raise ValueError(f"unknown format {fmt!r}")
