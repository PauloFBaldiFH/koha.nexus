"""A small Z39.50 client (Init, Search, Present, Close) over asyncio.

The BER code is the koha.nexus panel's scanner (panel/kei_panel/z3950.py),
with Present asking for a page of records instead of one test record; this
copy is the VPS gateway's (branch backup/sru-bridge), without its Zeus types.

Session keeps one association open for several searches (one Init, then
Search and Present as often as needed, then Close), with a timeout per
phase and a hard limit for the whole session. Queries are Type-1 (RPN):
a Term, or Term and Term (and_). A refused search or present comes back
as a Diagnostic (Bib-1 code, addinfo, category) instead of being lost.
Every failure is a Z3950Error naming the phase and what went wrong, so
the caller can tell a server that is down from one that only refused an
index. search() is the one-shot form the gateway uses.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

CTX = 0x80
UNIVERSAL = 0x00
OID_BIB1 = "1.2.840.10003.3.1"
OID_BIB1_DIAG = "1.2.840.10003.4.1"
OID_USMARC = "1.2.840.10003.5.10"
OID_UNIMARC = "1.2.840.10003.5.1"
MAX_APDU = 8_000_000

# Bib-1 use attributes for the kinds of search Koha's CQL turns into.
USE = {"isbn": 7, "title": 4, "author": 1003}
USE_ANY = 1016

# Bib-1 attribute types.
ATTR_USE, ATTR_RELATION, ATTR_POSITION, ATTR_STRUCTURE, ATTR_TRUNCATION, ATTR_COMPLETENESS = 1, 2, 3, 4, 5, 6

# Bib-1 diagnostic codes by what the caller should do about them:
#   query    the server cannot run this form of query; another form may work
#   config   the database, login or record syntax is wrong for this server
#   temporary  try again later
#   record   one record could not be sent; the others are fine
DIAG_CATEGORY = {
    **{c: "query" for c in (3, 4, 5, 6, 7, 8, 9, 11, 107, 108, 110)},
    **{c: "query" for c in range(113, 127)},
    **{c: "config" for c in (101, 102, 106, 109, 111, 235, 236, 238, 239)},
    **{c: "temporary" for c in (2, 28, 112)},
    **{c: "record" for c in (14, 17, 18, 19)},
}

# closeReason values of a Close the server sends.
CLOSE_REASONS = {0: "finished", 1: "shutdown", 2: "systemProblem", 3: "costLimit", 4: "resources",
                 5: "securityViolation", 6: "protocolError", 7: "lackOfActivity", 8: "peerAbort",
                 9: "unspecified"}


@dataclass(frozen=True)
class Diagnostic:
    """A diagnostic the server sent (DefaultDiagFormat)."""
    code: int
    addinfo: str = ""
    diagset: str = OID_BIB1_DIAG

    @property
    def category(self) -> str:
        if self.diagset != OID_BIB1_DIAG:
            return "other"
        return DIAG_CATEGORY.get(self.code, "other")

    def __str__(self) -> str:
        return f"diagnostic {self.code}" + (f" ({self.addinfo})" if self.addinfo else "")


class Z3950Error(Exception):
    """The server refused, broke off or answered something unreadable.

    phase: connect, init, search, present or close (where it happened);
    kind:  dns, refused, unreachable, timeout, reset, init-refused,
           closed (the server sent Close; close_reason says why),
           protocol (an answer that is not the expected APDU or not BER)
           or diagnostic (diagnostic says which).
    """

    def __init__(self, message: str, *, phase: str = "", kind: str = "",
                 diagnostic: Diagnostic | None = None, close_reason: int | None = None):
        super().__init__(message)
        self.phase = phase
        self.kind = kind
        self.diagnostic = diagnostic
        self.close_reason = close_reason


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


def ber_oid_text(value: bytes) -> str:
    """The dotted form of a BER object identifier."""
    if not value:
        return ""
    head = min(value[0] // 40, 2)
    parts, n = [str(head), str(value[0] - 40 * head)], 0
    for b in value[1:]:
        n = (n << 7) | (b & 0x7F)
        if not b & 0x80:
            parts.append(str(n))
            n = 0
    return ".".join(parts)


def _text(value) -> str:
    return value.decode("utf-8", "replace").strip() if isinstance(value, bytes) else ""


# ----------------------------------------------------------------------
# Type-1 (RPN) queries
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Term:
    """One search term with its Bib-1 attributes (only use is required)."""
    value: str
    use: int = USE_ANY
    relation: int | None = None
    position: int | None = None
    structure: int | None = None
    truncation: int | None = None
    completeness: int | None = None

    def attributes(self) -> list[tuple[int, int]]:
        out = [(ATTR_USE, self.use)]
        for kind, value in ((ATTR_RELATION, self.relation), (ATTR_POSITION, self.position),
                            (ATTR_STRUCTURE, self.structure), (ATTR_TRUNCATION, self.truncation),
                            (ATTR_COMPLETENESS, self.completeness)):
            if value is not None:
                out.append((kind, value))
        return out


OPERATORS = {"and": 0, "or": 1, "and-not": 2}


@dataclass(frozen=True)
class Op:
    """Two queries joined by and, or or and-not."""
    op: str
    left: "Term | Op"
    right: "Term | Op"


def and_(*parts: "Term | Op") -> "Term | Op":
    """The parts joined by AND, left to right; one part is itself."""
    if not parts:
        raise ValueError("and_() needs at least one query")
    query = parts[0]
    for part in parts[1:]:
        query = Op("and", query, part)
    return query


def term_for(kind: str, term: str) -> Term:
    """The Term for one of the gateway's kinds of search (isbn, title, author, keywords)."""
    return Term(term, USE.get(kind, USE_ANY))


def rpn_structure(query: "Term | Op") -> bytes:
    """RPNStructure: op [0] AttributesPlusTerm, or rpnRpnOp [1] (left, right, operator)."""
    if isinstance(query, Term):
        attrs = b"".join(tlv(16, tlv(120, ber_int(kind)) + tlv(121, ber_int(value)), True, UNIVERSAL)
                         for kind, value in query.attributes())
        apt = tlv(102, tlv(44, attrs, True) + tlv(45, query.value.encode("utf-8")), True)
        return tlv(0, apt, True)
    if isinstance(query, Op):
        if query.op not in OPERATORS:
            raise ValueError(f"unknown operator {query.op!r}")
        operator = tlv(46, tlv(OPERATORS[query.op], b""), True)
        return tlv(1, rpn_structure(query.left) + rpn_structure(query.right) + operator, True)
    raise TypeError(f"not a query: {query!r}")


# ----------------------------------------------------------------------
# Requests
# ----------------------------------------------------------------------

def init_request(user: str = "", password: str = "", name: str = "koha.nexus gateway",
                 version: str = "1") -> bytes:
    body = (tlv(3, b"\x00\xe0")                    # protocolVersion 1, 2, 3
            + tlv(4, b"\x00\xe0")                  # options: search, present, delSet
            + tlv(5, ber_int(1_048_576)) + tlv(6, ber_int(MAX_APDU)))
    if user:
        body += tlv(7, tlv(16, tlv(1, user.encode()) + tlv(2, password.encode()), True, UNIVERSAL), True)
    body += tlv(110, b"KNX") + tlv(111, name.encode()) + tlv(112, version.encode())
    return tlv(20, body, True)


def search_request(db: str, query: "Term | Op | str", use: int | None = None, *,
                   set_name: str = "default") -> bytes:
    """A SearchRequest on DB. QUERY is a Term or Op; a plain string is
    searched with USE (any word when USE is not given)."""
    if isinstance(query, str):
        query = Term(query, USE_ANY if use is None else use)
    rpn = tlv(6, ber_oid(OID_BIB1), cls=UNIVERSAL) + rpn_structure(query)
    body = (tlv(13, ber_int(0)) + tlv(14, ber_int(1)) + tlv(15, ber_int(0)) + tlv(16, b"\xff")
            + tlv(17, set_name.encode()) + tlv(18, tlv(105, db.encode()), True) + tlv(21, tlv(1, rpn, True), True))
    return tlv(22, body, True)


def present_request(start: int, count: int, syntax: str = OID_USMARC, *, set_name: str = "default",
                    element_set: str = "F") -> bytes:
    body = (tlv(31, set_name.encode()) + tlv(30, ber_int(start)) + tlv(29, ber_int(count))
            + tlv(19, tlv(0, element_set.encode()), True) + tlv(104, ber_oid(syntax)))
    return tlv(24, body, True)


def close_request(reason: int = 0) -> bytes:
    """Close with closeReason (0: finished)."""
    return tlv(48, tlv(211, ber_int(reason)), True)


# ----------------------------------------------------------------------
# Responses
# ----------------------------------------------------------------------

def _diagnostic(nodes: list) -> Diagnostic:
    """DefaultDiagFormat's contents: diagnosticSetId, condition, addinfo."""
    diagset, code, addinfo = OID_BIB1_DIAG, 0, ""
    for cls, number, constructed, value in nodes:
        if cls != UNIVERSAL or constructed:
            continue
        if number == 6:
            diagset = ber_oid_text(value) or diagset
        elif number == 2:
            code = _int(value)
        elif number in (12, 19, 22, 26, 27) and not addinfo:   # UTF8, Printable, IA5, Visible, General
            addinfo = _text(value)
    return Diagnostic(code, addinfo, diagset)


def diagnostics(nodes) -> list[Diagnostic]:
    """Every DefaultDiagFormat in NODES, however deeply wrapped (a non-
    surrogate diagnostic, a SEQUENCE OF DiagRec, a surrogate in a record)."""
    if not isinstance(nodes, list):
        return []
    if any(c == UNIVERSAL and n == 2 and not k for c, n, k, _v in nodes):
        return [_diagnostic(nodes)]
    out = []
    for _c, _n, constructed, value in nodes:
        if constructed:
            out += diagnostics(value)
    return out


def _records_diagnostics(body: list) -> list[Diagnostic]:
    """nonSurrogateDiagnostic [130] or multipleNonSurDiagnostics [205]."""
    return diagnostics(ber_top(body, 130)) + diagnostics(ber_top(body, 205))


@dataclass
class SearchResult:
    total: int
    ok: bool = True                                   # searchStatus
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def diagnostic(self) -> Diagnostic | None:
        return self.diagnostics[0] if self.diagnostics else None


@dataclass
class PresentResult:
    records: list[bytes] = field(default_factory=list)            # ISO 2709, in order
    diagnostics: list[Diagnostic] = field(default_factory=list)   # surrogate and non-surrogate
    status: int = 0                                               # presentStatus (0 success)


def parse_search(body: list) -> SearchResult:
    return SearchResult(_int(ber_top(body, 23)), ber_top(body, 22) != b"\x00", _records_diagnostics(body))


def parse_present(body: list) -> PresentResult:
    """The ISO 2709 records of a PresentResponse, in order: in each
    NamePlusRecord the longest octet string is the record (the rest are the
    database name and the syntax OID). A surrogate diagnostic in place of a
    record goes to diagnostics."""
    out = PresentResult(status=_int(ber_top(body, 27)), diagnostics=_records_diagnostics(body))
    box = ber_top(body, 28)
    if not isinstance(box, list):
        return out
    for _c, _n, constructed, npr in box:
        if not constructed:
            continue
        record = ber_top(npr, 1)
        if not isinstance(record, list):
            continue
        surrogate = ber_top(record, 2)
        if surrogate is not None:
            out.diagnostics += diagnostics(surrogate)
            continue
        blobs = sorted(_primitives(record), key=len, reverse=True)
        if blobs and blobs[0][:5].isdigit():
            out.records.append(blobs[0])
    return out


def present_records(resp_body: list) -> list[bytes]:
    """The records of a PresentResponse (surrogate diagnostics skipped)."""
    return parse_present(resp_body).records


# ----------------------------------------------------------------------
# Session
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Timeouts:
    """Seconds per phase, and for the whole session from open() on.
    close is how long Close waits for the server's own Close (0: not at all)."""
    connect: float = 4.0
    init: float = 6.0
    search: float = 8.0
    present: float = 10.0
    close: float = 2.0
    total: float = 25.0

    @classmethod
    def single(cls, seconds: float) -> "Timeouts":
        """One limit for everything, without waiting on Close (the gateway's form)."""
        return cls(seconds, seconds, seconds, seconds, 0.0, seconds)


class Session:
    """One Z39.50 association: open() (connect + Init), then search() and
    present() as often as needed, then close(). Also an async context manager.

    ADDRESS, when given, is where to connect (an IP the caller already
    resolved and checked); HOST is still the name used in messages.
    A timeout, a reset or an unexpected answer drops the connection: the
    session cannot be used after that error."""

    def __init__(self, host: str, port: int, *, user: str = "", password: str = "",
                 timeouts: Timeouts | None = None, address: str | None = None,
                 name: str = "koha.nexus gateway", version: str = "1", clock=time.monotonic):
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.timeouts = timeouts or Timeouts()
        self.address = address
        self.name, self.version = name, version
        self.clock = clock
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.deadline = 0.0
        self.server: dict[str, str] = {}             # implementationId / Name / Version of the Init answer

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def is_open(self) -> bool:
        return self.writer is not None

    async def __aenter__(self) -> "Session":
        await self.open()
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    def _limit(self, phase: str, seconds: float) -> float:
        left = self.deadline - self.clock()
        if left <= 0:
            self._drop()
            raise Z3950Error(f"{self.label}: session limit of {self.timeouts.total:g}s reached",
                             phase=phase, kind="timeout")
        return min(seconds, left)

    def _drop(self) -> None:
        if self.writer is not None:
            self.writer.close()
        self.reader = self.writer = None

    async def open(self) -> None:
        """Connect and Init. Raises Z3950Error (phase connect or init)."""
        self.deadline = self.clock() + self.timeouts.total
        limit = self._limit("connect", self.timeouts.connect)
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.address or self.host, self.port), limit)
        except asyncio.TimeoutError as exc:
            raise Z3950Error(f"{self.label} did not accept a connection in {limit:g}s",
                             phase="connect", kind="timeout") from exc
        except socket.gaierror as exc:
            raise Z3950Error(f"{self.label}: name not found ({exc})", phase="connect", kind="dns") from exc
        except ConnectionRefusedError as exc:
            raise Z3950Error(f"{self.label} refused the connection", phase="connect", kind="refused") from exc
        except OSError as exc:
            raise Z3950Error(f"{self.label}: {type(exc).__name__}: {exc}", phase="connect",
                             kind="unreachable") from exc
        init = await self._ask("init", init_request(self.user, self.password, self.name, self.version), 21,
                               self.timeouts.init)
        self.server = {key: _text(ber_top(init, tag)) for key, tag in (("id", 110), ("name", 111), ("version", 112))
                       if isinstance(ber_top(init, tag), bytes)}
        if ber_top(init, 12) == b"\x00":
            diag = diagnostics(ber_top(init, 11))
            self._drop()
            raise Z3950Error(f"{self.label} refused the connection (login needed?)", phase="init",
                             kind="init-refused", diagnostic=diag[0] if diag else None)

    async def _roundtrip(self, pdu: bytes) -> list:
        self.writer.write(pdu)
        await self.writer.drain()
        return ber_decode(await read_pdu(self.reader))

    async def _ask(self, phase: str, pdu: bytes, want: int, seconds: float) -> list:
        """Send PDU, return the body of the answer, which must be APDU WANT."""
        if self.writer is None:
            raise Z3950Error(f"{self.label}: the session is not open", phase=phase, kind="protocol")
        limit = self._limit(phase, seconds)
        try:
            resp = await asyncio.wait_for(self._roundtrip(pdu), limit)
        except asyncio.TimeoutError as exc:
            self._drop()
            raise Z3950Error(f"{self.label} did not answer in {limit:g}s", phase=phase, kind="timeout") from exc
        except (asyncio.IncompleteReadError, ConnectionError) as exc:
            self._drop()
            raise Z3950Error(f"{self.label} closed the connection", phase=phase, kind="reset") from exc
        except OSError as exc:
            self._drop()
            raise Z3950Error(f"{self.label}: {type(exc).__name__}: {exc}", phase=phase, kind="reset") from exc
        except (ValueError, IndexError) as exc:
            self._drop()
            raise Z3950Error(f"{self.label}: unreadable answer ({exc})", phase=phase, kind="protocol") from exc
        if not resp:
            self._drop()
            raise Z3950Error(f"{self.label}: empty answer", phase=phase, kind="protocol")
        _cls, number, constructed, body = resp[0]
        if number == 48 and constructed:
            reason = _int(ber_top(body, 211))
            self._drop()
            raise Z3950Error(f"{self.label} closed the session ({CLOSE_REASONS.get(reason, reason)})",
                             phase=phase, kind="closed", close_reason=reason)
        if number != want or not constructed:
            self._drop()
            raise Z3950Error(f"{self.label}: unexpected answer (APDU {number})", phase=phase, kind="protocol")
        return body

    async def search(self, db: str, query: "Term | Op", *, set_name: str = "default") -> SearchResult:
        """Run QUERY on DB. A refused search is a SearchResult with ok False
        and its diagnostics, not an error: the session stays usable."""
        return parse_search(await self._ask("search", search_request(db, query, set_name=set_name), 23,
                                            self.timeouts.search))

    async def present(self, start: int, count: int, *, syntax: str = OID_USMARC, set_name: str = "default",
                      element_set: str = "F") -> PresentResult:
        """Records START..START+COUNT-1 of the last search."""
        body = await self._ask("present", present_request(start, count, syntax, set_name=set_name,
                                                          element_set=element_set), 25, self.timeouts.present)
        return parse_present(body)

    async def close(self) -> None:
        """Send Close (finished), wait up to timeouts.close for the server's
        Close, and drop the connection. Never raises."""
        if self.writer is None:
            return
        try:
            self.writer.write(close_request(0))
            await self.writer.drain()
            if self.timeouts.close > 0:
                await asyncio.wait_for(read_pdu(self.reader), self.timeouts.close)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, OSError, ValueError, IndexError):
            pass
        finally:
            self._drop()


async def search(host: str, port: int, db: str, kind: str, term: str, start: int, count: int, *,
                 user: str = "", password: str = "", timeout: float = 25.0) -> tuple[int, list[bytes]]:
    """(hit count, ISO 2709 records start..start+count-1) from one Z39.50
    session. KIND is isbn, title, author or keywords."""
    session = Session(host, port, user=user, password=password, timeouts=Timeouts.single(timeout))
    try:
        await session.open()
        query = term_for(kind, term)
        found = await session.search(db, query)
        if not found.ok:
            # searchStatus false: the server sent a diagnostic (an index it
            # does not support...). Koha sees no hits rather than an error.
            log.warning("%s:%s refused the search %r (use %d, %s)", host, port, term, query.use,
                        found.diagnostic or "no diagnostic")
        total = found.total
        if not total or count <= 0 or start > total:
            return total, []
        page = await session.present(start, min(count, total - start + 1))
        return total, page.records
    finally:
        await session.close()
