"""A small MARC21 record model with MARCXML and ISO 2709 in and out.

Standard library only. The model keeps field order and repeated
subfields exactly as read, so a record written back out differs from the
one read only by the fields the engine added.

ISO 2709 records whose leader/09 is not "a" (MARC-8) are decoded with
pymarc's MARC-8 converter when pymarc is installed; without it they are
read as Latin-1 and flagged (Record.marc8_fallback) so the caller can
report them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator
from xml.etree import ElementTree as ET

MARC = "http://www.loc.gov/MARC21/slim"
ET.register_namespace("marc", MARC)
_M = f"{{{MARC}}}"

FT = b"\x1e"   # field terminator
RT = b"\x1d"   # record terminator
SD = b"\x1f"   # subfield delimiter


class RecordError(ValueError):
    """A record that cannot be read (the message says why)."""


@dataclass
class Field:
    tag: str
    ind1: str = " "
    ind2: str = " "
    subfields: list[tuple[str, str]] = field(default_factory=list)
    data: str | None = None          # control fields (00X) only

    @property
    def is_control(self) -> bool:
        return self.data is not None

    def get(self, code: str) -> str:
        for c, v in self.subfields:
            if c == code:
                return v
        return ""

    def get_all(self, codes: str) -> list[str]:
        return [v for c, v in self.subfields if c in codes]

    def text(self, codes: str = "abcdefghijklmnopqrstuvwxyz") -> str:
        return " ".join(v for c, v in self.subfields if c in codes and v)


@dataclass
class Record:
    leader: str = " " * 24
    fields: list[Field] = field(default_factory=list)
    marc8_fallback: bool = False

    # -- reading ---------------------------------------------------------
    def get_fields(self, *tags: str) -> list[Field]:
        return [f for f in self.fields if f.tag in tags]

    def first(self, *tags: str) -> Field | None:
        for f in self.fields:
            if f.tag in tags:
                return f
        return None

    def control(self, tag: str) -> str:
        f = self.first(tag)
        return (f.data or "") if f is not None and f.is_control else ""

    def has(self, *tags: str) -> bool:
        return any(f.tag in tags for f in self.fields)

    @property
    def is_authority(self) -> bool:
        return len(self.leader) > 6 and self.leader[6] == "z"

    # -- writing ---------------------------------------------------------
    def add_field(self, new: Field) -> None:
        """Insert in tag order: after the last field with a tag <= new.tag
        (so an added 650 lands after the existing 6XX, before the 7XX)."""
        pos = len(self.fields)
        for i, f in enumerate(self.fields):
            if f.tag > new.tag:
                pos = i
                break
        self.fields.insert(pos, new)

    def copy(self) -> "Record":
        return Record(self.leader, [Field(f.tag, f.ind1, f.ind2, list(f.subfields), f.data) for f in self.fields],
                      self.marc8_fallback)


# ----------------------------------------------------------------------
# MARCXML
# ----------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def from_element(el: ET.Element) -> Record:
    """One MARCXML <record> element (any namespace, or none)."""
    rec = Record()
    seen_leader = False
    for child in el:
        name = _local(child.tag)
        if name == "leader":
            rec.leader = (child.text or "").ljust(24)[:24]
            seen_leader = True
        elif name == "controlfield":
            rec.fields.append(Field(child.get("tag", ""), data=child.text or ""))
        elif name == "datafield":
            subs = [(sf.get("code", ""), sf.text or "") for sf in child if _local(sf.tag) == "subfield"]
            rec.fields.append(Field(child.get("tag", ""), (child.get("ind1") or " ")[:1],
                                    (child.get("ind2") or " ")[:1], subs))
    if not seen_leader:
        raise RecordError("no leader")
    return rec


def to_element(rec: Record) -> ET.Element:
    el = ET.Element(_M + "record")
    ET.SubElement(el, _M + "leader").text = rec.leader
    for f in rec.fields:
        if f.is_control:
            ET.SubElement(el, _M + "controlfield", tag=f.tag).text = f.data
        else:
            df = ET.SubElement(el, _M + "datafield", tag=f.tag, ind1=f.ind1 or " ", ind2=f.ind2 or " ")
            for code, value in f.subfields:
                ET.SubElement(df, _M + "subfield", code=code).text = value
    return el


def to_xml(rec: Record) -> str:
    return ET.tostring(to_element(rec), encoding="unicode")


def parse_xml(text: str | bytes) -> list[Record]:
    """Every <record> with a leader in a document (a <collection>, a lone
    <record>, an SRU response)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise RecordError(f"not XML: {exc}") from None
    out = []
    for el in root.iter():
        if _local(el.tag) == "record" and any(_local(c.tag) == "leader" for c in el):
            out.append(from_element(el))
    return out


def iter_xml(stream) -> Iterator[Record]:
    """Stream the records of a MARCXML file object: memory stays at one
    record whatever the file size."""
    depth = 0
    for event, el in ET.iterparse(stream, events=("start", "end")):
        if _local(el.tag) != "record":
            continue
        if event == "start":
            depth += 1
            continue
        depth -= 1
        if depth == 0:
            if any(_local(c.tag) == "leader" for c in el):
                yield from_element(el)
            el.clear()


# ----------------------------------------------------------------------
# ISO 2709
# ----------------------------------------------------------------------
def _marc8(data: bytes) -> str | None:
    try:
        from pymarc.marc8 import marc8_to_unicode
    except ImportError:
        return None
    return marc8_to_unicode(data)


def from_iso2709(raw: bytes) -> Record:
    if len(raw) < 25:
        raise RecordError("record shorter than a leader")
    leader = raw[:24].decode("ascii", "replace")
    try:
        base = int(leader[12:17])
    except ValueError:
        raise RecordError(f"bad base address in leader {leader!r}") from None
    utf8 = leader[9] == "a"
    rec = Record(leader=leader)

    def decode(b: bytes) -> str:
        if utf8:
            return b.decode("utf-8", "replace")
        text = _marc8(b)
        if text is None:
            rec.marc8_fallback = True
            return b.decode("latin-1")
        return text

    directory = raw[24:base - 1]
    if len(directory) % 12:
        raise RecordError("directory length is not a multiple of 12")
    for i in range(0, len(directory), 12):
        entry = directory[i:i + 12].decode("ascii", "replace")
        tag, length, start = entry[:3], int(entry[3:7]), int(entry[7:12])
        chunk = raw[base + start: base + start + length].rstrip(FT)
        if tag < "010" and tag.isdigit():
            rec.fields.append(Field(tag, data=decode(chunk)))
            continue
        ind = decode(chunk[:2]).ljust(2)
        subs = []
        for part in chunk[2:].split(SD)[1:]:
            if part:
                subs.append((decode(part[:1]), decode(part[1:])))
        rec.fields.append(Field(tag, ind[0], ind[1], subs))
    return rec


def iter_iso2709(stream) -> Iterator[bytes]:
    """The raw records of an ISO 2709 file object, one at a time."""
    buf = b""
    while True:
        chunk = stream.read(1 << 16)
        if not chunk:
            break
        buf += chunk
        while True:
            end = buf.find(RT)
            if end < 0:
                break
            raw, buf = buf[:end + 1], buf[end + 1:]
            raw = raw.lstrip(b"\r\n \x00")
            if len(raw) > 24:
                yield raw
    if buf.strip(b"\r\n \x00"):
        yield buf.strip(b"\r\n \x00")


def to_iso2709(rec: Record) -> bytes:
    """UTF-8 ISO 2709 (leader/09 set to "a")."""
    directory = b""
    data = b""
    for f in rec.fields:
        if f.is_control:
            body = (f.data or "").encode("utf-8") + FT
        else:
            body = ((f.ind1 or " ")[:1] + (f.ind2 or " ")[:1]).encode("utf-8")
            for code, value in f.subfields:
                body += SD + code.encode("utf-8") + value.encode("utf-8")
            body += FT
        directory += f"{f.tag[:3]:0>3}{len(body):04d}{len(data):05d}".encode("ascii")
        data += body
    base = 24 + len(directory) + 1
    total = base + len(data) + 1
    leader = rec.leader.ljust(24)[:24]
    leader = f"{total:05d}" + leader[5:9] + "a" + leader[10:12] + f"{base:05d}" + leader[17:]
    return leader.encode("ascii", "replace") + directory + FT + data + RT


# ----------------------------------------------------------------------
# MARC-in-JSON (the LoC / pymarc JSON form)
# ----------------------------------------------------------------------
def from_json(obj: dict) -> Record:
    """{"leader": "...", "fields": [{"001": "x"}, {"245": {"ind1": "1",
    "ind2": "0", "subfields": [{"a": "..."}]}}]}"""
    if not isinstance(obj, dict) or "leader" not in obj or "fields" not in obj:
        raise RecordError("not MARC-in-JSON")
    rec = Record(leader=str(obj["leader"]).ljust(24)[:24])
    for item in obj["fields"]:
        for tag, value in item.items():
            if isinstance(value, str):
                rec.fields.append(Field(tag, data=value))
            else:
                subs = [(c, v) for sf in value.get("subfields", []) for c, v in sf.items()]
                rec.fields.append(Field(tag, (value.get("ind1") or " ")[:1], (value.get("ind2") or " ")[:1], subs))
    return rec
