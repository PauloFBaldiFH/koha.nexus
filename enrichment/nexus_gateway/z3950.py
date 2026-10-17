"""A small Z39.50 client (Init, Search, Present) over asyncio.

The BER code is the koha.nexus panel's scanner (panel/kei_panel/z3950.py),
with Present asking for a page of records instead of one test record; this
copy is the VPS gateway's (branch backup/sru-bridge), without its Zeus types.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

CTX = 0x80
UNIVERSAL = 0x00
OID_BIB1 = "1.2.840.10003.3.1"
OID_USMARC = "1.2.840.10003.5.10"
MAX_APDU = 8_000_000

# Bib-1 use attributes for the kinds of search Koha's CQL turns into.
USE = {"isbn": 7, "title": 4, "author": 1003}
USE_ANY = 1016


class Z3950Error(Exception):
    """The server refused, broke off or answered something unreadable."""


def ber_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def ber_tag(cls: int, constructed: bool, number: int) -> bytes:
    first = cls | (0x20 if constructed else 0)
    if number < 31:
        return bytes([first | number])
    out = [number & 0x7F]
    number >>= 7
    while number:
        out.insert(0, 0x80 | (number & 0x7F))
        number >>= 7
    return bytes([first | 0x1F] + out)


def tlv(number: int, value: bytes, constructed: bool = False, cls: int = CTX) -> bytes:
    return ber_tag(cls, constructed, number) + ber_len(len(value)) + value


def ber_int(n: int) -> bytes:
    return n.to_bytes(max(1, (n.bit_length() + 8) // 8), "big", signed=True)


def ber_oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.split(".")]
    out = bytearray([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.insert(0, 0x80 | (p & 0x7F))
            p >>= 7
        out += bytes(chunk)
    return bytes(out)


def _ber_node(data: bytes, pos: int, end: int) -> tuple[tuple, int]:
    first = data[pos]
    pos += 1
    cls, constructed, number = first & 0xC0, bool(first & 0x20), first & 0x1F
    if number == 0x1F:
        number = 0
        while True:
            b = data[pos]
            pos += 1
            number = (number << 7) | (b & 0x7F)
            if not b & 0x80:
                break
    length = data[pos]
    pos += 1
    if length == 0x80:
        if not constructed:
            raise ValueError("indefinite length on a primitive BER value")
        kids = []
        while True:
            if pos + 2 > end:
                raise ValueError("truncated BER")
            if data[pos] == 0 and data[pos + 1] == 0:
                return (cls, number, True, kids), pos + 2
            node, pos = _ber_node(data, pos, end)
            kids.append(node)
    if length & 0x80:
        k = length & 0x7F
        length = int.from_bytes(data[pos:pos + k], "big")
        pos += k
    if pos + length > end:
        raise ValueError("truncated BER")
    value = data[pos:pos + length]
    return (cls, number, constructed, ber_decode(data, pos, pos + length) if constructed else value), pos + length


def ber_decode(data: bytes, pos: int = 0, end: int | None = None) -> list[tuple]:
    """[(class, number, constructed, value)], constructed values decoded too."""
    end = len(data) if end is None else end
    out = []
    while pos < end:
        node, pos = _ber_node(data, pos, end)
        out.append(node)
    return out


def ber_top(nodes, number: int, cls: int = CTX):
    return next((v for c, n, _k, v in nodes if c == cls and n == number), None)


def _primitives(nodes) -> list[bytes]:
    out = []
    for _c, _n, constructed, value in nodes:
        out += _primitives(value) if constructed else [value]
    return out


def _int(v) -> int:
    return int.from_bytes(v, "big", signed=True) if isinstance(v, bytes) and v else 0


async def _read_tlv(reader: asyncio.StreamReader, budget: list[int], head: bytes = b"") -> bytes:
    head = head or await reader.readexactly(1)
    if head[0] & 0x1F == 0x1F:
        while True:
            b = await reader.readexactly(1)
            head += b
            if not b[0] & 0x80:
                break
    lb = await reader.readexactly(1)
    head += lb
    length = lb[0]
    if length == 0x80:
        while True:
            tag = await reader.readexactly(1)
            if tag == b"\x00":
                end = await reader.readexactly(1)
                if end != b"\x00":
                    raise ValueError("bad BER end-of-contents")
                return head + tag + end
            head += await _read_tlv(reader, budget, tag)
    if length & 0x80:
        extra = await reader.readexactly(length & 0x7F)
        head += extra
        length = int.from_bytes(extra, "big")
    budget[0] -= length
    if length > MAX_APDU or budget[0] < 0:
        raise ValueError("APDU too large")
    return head + await reader.readexactly(length)


async def read_pdu(reader: asyncio.StreamReader) -> bytes:
    return await _read_tlv(reader, [MAX_APDU])


def init_request(user: str = "", password: str = "") -> bytes:
    body = (tlv(3, b"\x00\xe0")                    # protocolVersion 1, 2, 3
            + tlv(4, b"\x00\xe0")                  # options: search, present, delSet
            + tlv(5, ber_int(1_048_576)) + tlv(6, ber_int(MAX_APDU)))
    if user:
        body += tlv(7, tlv(16, tlv(1, user.encode()) + tlv(2, password.encode()), True, UNIVERSAL), True)
    body += tlv(110, b"KNX") + tlv(111, b"koha.nexus gateway") + tlv(112, b"1")
    return tlv(20, body, True)


def search_request(db: str, term: str, use: int) -> bytes:
    attr = tlv(16, tlv(120, ber_int(1)) + tlv(121, ber_int(use)), True, UNIVERSAL)
    apt = tlv(102, tlv(44, attr, True) + tlv(45, term.encode("utf-8")), True)
    rpn = tlv(6, ber_oid(OID_BIB1), cls=UNIVERSAL) + tlv(0, apt, True)
    body = (tlv(13, ber_int(0)) + tlv(14, ber_int(1)) + tlv(15, ber_int(0)) + tlv(16, b"\xff")
            + tlv(17, b"default") + tlv(18, tlv(105, db.encode()), True) + tlv(21, tlv(1, rpn, True), True))
    return tlv(22, body, True)


def present_request(start: int, count: int) -> bytes:
    body = (tlv(31, b"default") + tlv(30, ber_int(start)) + tlv(29, ber_int(count))
            + tlv(19, tlv(0, b"F"), True) + tlv(104, ber_oid(OID_USMARC)))
    return tlv(24, body, True)


def present_records(resp_body: list) -> list[bytes]:
    """The ISO 2709 records of a PresentResponse, in order: in each
    NamePlusRecord the longest octet string is the record (the rest are the
    database name and the syntax OID). Surrogate diagnostics are skipped."""
    box = ber_top(resp_body, 28)
    if not isinstance(box, list):
        return []
    out = []
    for _c, _n, constructed, npr in box:
        if not constructed:
            continue
        record = ber_top(npr, 1)
        if not isinstance(record, list) or ber_top(record, 2) is not None:
            continue
        blobs = sorted(_primitives(record), key=len, reverse=True)
        if blobs and blobs[0][:5].isdigit():
            out.append(blobs[0])
    return out


async def search(host: str, port: int, db: str, kind: str, term: str, start: int, count: int, *,
                 user: str = "", password: str = "", timeout: float = 25.0) -> tuple[int, list[bytes]]:
    """(hit count, ISO 2709 records start..start+count-1) from one Z39.50
    session. KIND is isbn, title, author or keywords."""
    try:
        return await asyncio.wait_for(
            _search(host, port, db, kind, term, start, count, user, password), timeout)
    except asyncio.TimeoutError as exc:
        raise Z3950Error(f"{host}:{port} did not answer in {timeout:g}s") from exc
    except (OSError, asyncio.IncompleteReadError, ValueError, IndexError) as exc:
        raise Z3950Error(f"{host}:{port}: {type(exc).__name__}: {exc}") from exc


async def _search(host, port, db, kind, term, start, count, user, password):
    reader, writer = await asyncio.open_connection(host, port)
    try:
        async def ask(pdu: bytes, want: int) -> list:
            writer.write(pdu)
            await writer.drain()
            resp = ber_decode(await read_pdu(reader))
            if not resp or resp[0][1] != want or not resp[0][2]:
                raise Z3950Error(f"{host}:{port}: unexpected answer (APDU {resp[0][1] if resp else '-'})")
            return resp[0][3]

        init = await ask(init_request(user, password), 21)
        if ber_top(init, 12) == b"\x00":
            raise Z3950Error(f"{host}:{port} refused the connection (login needed?)")
        use = USE.get(kind, USE_ANY)
        found = await ask(search_request(db, term, use), 23)
        total = _int(ber_top(found, 23))
        if ber_top(found, 22) == b"\x00":
            # searchStatus false: the server sent a diagnostic (an index it
            # does not support...). Koha sees no hits rather than an error.
            log.warning("%s:%s refused the search %r (use %d)", host, port, term, use)
        if not total or count <= 0 or start > total:
            return total, []
        page = await ask(present_request(start, min(count, total - start + 1)), 25)
        return total, present_records(page)
    finally:
        writer.close()
