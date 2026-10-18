"""The Z39.50 Session (nexus_gateway.z3950): RPN queries, one association
for several searches, per-phase timeouts, diagnostics, and what each
failure is called. A scripted fake server on 127.0.0.1 answers with BER
written by hand below, so each test shows the exact bytes a server sends."""

from __future__ import annotations

import asyncio
import socket
import time

import pytest
from conftest import bib

from nexus_enrich import marc
from nexus_gateway import z3950
from nexus_gateway.z3950 import Op, Session, Term, Timeouts, Z3950Error

T = z3950.tlv
U = z3950.UNIVERSAL
HANG = object()          # the fake server reads the request and never answers
DROP = object()          # the fake server closes the connection instead of answering


# ----------------------------------------------------------------------
# BER fixtures: what a server sends
# ----------------------------------------------------------------------

def diag_format(code: int, addinfo: bytes = b"", diagset: str = z3950.OID_BIB1_DIAG) -> bytes:
    """The contents of a DefaultDiagFormat: diagnosticSetId, condition, addinfo."""
    return T(6, z3950.ber_oid(diagset), cls=U) + T(2, z3950.ber_int(code), cls=U) + T(26, addinfo, cls=U)


def init_response(ok: bool = True) -> bytes:
    return T(21, T(12, b"\xff" if ok else b"\x00") + T(110, b"81") + T(111, b"Fake Alma") + T(112, b"9.9"), True)


def search_response(total: int, ok: bool = True, records: bytes = b"") -> bytes:
    return T(23, T(23, z3950.ber_int(total)) + T(22, b"\xff" if ok else b"\x00") + records, True)


def non_surrogate(code: int, addinfo: bytes = b"") -> bytes:
    return T(130, diag_format(code, addinfo), True)


def npr_record(raw: bytes) -> bytes:
    return T(16, T(0, b"Default") + T(1, T(1, T(8, T(6, z3950.ber_oid(z3950.OID_USMARC), cls=U)
                                                  + T(1, raw), True, U), True), True), True, U)


def npr_surrogate(code: int, addinfo: bytes = b"") -> bytes:
    return T(16, T(0, b"Default") + T(1, T(2, T(16, diag_format(code, addinfo), True, U), True), True), True, U)


def present_response(*nprs: bytes, status: int = 0, records: bytes | None = None) -> bytes:
    box = T(28, b"".join(nprs), True) if records is None else records
    return T(25, T(24, z3950.ber_int(len(nprs))) + T(27, z3950.ber_int(status)) + box, True)


def close_pdu(reason: int) -> bytes:
    return T(48, T(211, z3950.ber_int(reason)), True)


def iso(title: str, rid: str) -> bytes:
    return marc.to_iso2709(bib(title, "Assis, Machado de", year=1899, rid=rid))


class FakeServer:
    """Answers each APDU from SCRIPT: {apdu tag: bytes | HANG | DROP | list
    of those, one per request}. Every request is kept in .seen as (tag, body)."""

    def __init__(self, script: dict, delay: float = 0.0):
        self.script = {k: (v if isinstance(v, list) else [v]) for k, v in script.items()}
        self.delay = delay
        self.seen: list[tuple[int, list]] = []
        self.port = 0

    def answer(self, tag: int):
        queue = self.script.get(tag, [DROP])
        return queue.pop(0) if len(queue) > 1 else queue[0]

    async def handle(self, reader, writer):
        try:
            while True:
                try:
                    pdu = await z3950.read_pdu(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    break
                _c, tag, _k, body = z3950.ber_decode(pdu)[0]
                self.seen.append((tag, body))
                resp = self.answer(tag)
                if resp is HANG:                     # silent until the client goes away
                    await reader.read()
                    break
                if resp is DROP:
                    break
                if self.delay:
                    await asyncio.sleep(self.delay)
                writer.write(resp)
                await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    @property
    def tags(self) -> list[int]:
        return [tag for tag, _ in self.seen]


def run(server: FakeServer, scenario):
    """Start SERVER, run scenario(port) and return its result."""
    async def main():
        srv = await asyncio.start_server(server.handle, "127.0.0.1", 0)
        server.port = srv.sockets[0].getsockname()[1]
        async with srv:
            return await scenario(server.port)
    return asyncio.run(main())


def fast(**over) -> Timeouts:
    values = dict(connect=1.0, init=1.0, search=1.0, present=1.0, close=0.5, total=5.0)
    values.update(over)
    return Timeouts(**values)


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------

def _apt(node):
    """(attributes [(type, value)], term) of an operand [0] -> [102]."""
    _c, n, _k, value = node
    assert n == 0
    apt = z3950.ber_top(value, 102)
    attrs = [(z3950._int(z3950.ber_top(el, 120)), z3950._int(z3950.ber_top(el, 121)))
             for _c2, _n2, _k2, el in z3950.ber_top(apt, 44)]
    return attrs, z3950.ber_top(apt, 45).decode()


def _rpn(pdu: bytes):
    """The RPNStructure node of a SearchRequest, and its attribute set OID."""
    body = z3950.ber_decode(pdu)[0][3]
    rpn = z3950.ber_top(z3950.ber_top(body, 21), 1)
    oid = z3950.ber_oid_text(z3950.ber_top(rpn, 6, U))
    return [n for n in rpn if not (n[0] == U and n[1] == 6)][0], oid


def test_a_term_carries_only_the_attributes_it_sets():
    assert Term("x", 7).attributes() == [(1, 7)]
    assert Term("x", 4, relation=3, structure=1, truncation=100).attributes() == [(1, 4), (2, 3), (4, 1), (5, 100)]
    assert z3950.term_for("isbn", "85").use == 7 and z3950.term_for("nonsense", "x").use == z3950.USE_ANY


def test_and_query_is_an_rpn_rpn_op():
    query = z3950.and_(Term("Dom Casmurro", 4, structure=1), Term("Assis", 1003))
    assert query == Op("and", Term("Dom Casmurro", 4, structure=1), Term("Assis", 1003))
    node, oid = _rpn(z3950.search_request("Default", query))
    assert oid == z3950.OID_BIB1
    _c, n, constructed, value = node
    assert n == 1 and constructed                                  # rpnRpnOp
    assert _apt(value[0]) == ([(1, 4), (4, 1)], "Dom Casmurro")
    assert _apt(value[1]) == ([(1, 1003)], "Assis")
    operator = value[2]
    assert operator[1] == 46 and operator[3] == [(z3950.CTX, 0, False, b"")]   # and [0] NULL


def test_three_parts_nest_to_the_left_and_or_operators_encode():
    q = z3950.and_(Term("a", 4), Term("b", 1003), Term("1899", 31))
    assert q == Op("and", Op("and", Term("a", 4), Term("b", 1003)), Term("1899", 31))
    assert z3950.and_(Term("a")) == Term("a")
    node, _ = _rpn(z3950.search_request("d", Op("and-not", Term("a"), Term("b"))))
    assert node[3][2][3][0][1] == 2
    with pytest.raises(ValueError):
        z3950.rpn_structure(Op("xor", Term("a"), Term("b")))
    with pytest.raises(ValueError):
        z3950.and_()


def test_the_old_string_form_of_search_request_is_unchanged():
    # The bytes the gateway sent before Session existed.
    attr = T(16, T(120, z3950.ber_int(1)) + T(121, z3950.ber_int(7)), True, U)
    apt = T(102, T(44, attr, True) + T(45, "8535902775".encode()), True)
    rpn = T(6, z3950.ber_oid(z3950.OID_BIB1), cls=U) + T(0, apt, True)
    old = T(22, T(13, z3950.ber_int(0)) + T(14, z3950.ber_int(1)) + T(15, z3950.ber_int(0)) + T(16, b"\xff")
            + T(17, b"default") + T(18, T(105, b"Default"), True) + T(21, T(1, rpn, True), True), True)
    assert z3950.search_request("Default", "8535902775", 7) == old
    assert z3950.search_request("Default", Term("8535902775", 7)) == old


def test_present_request_names_the_syntax():
    body = z3950.ber_decode(z3950.present_request(1, 10, z3950.OID_UNIMARC))[0][3]
    assert z3950.ber_oid_text(z3950.ber_top(body, 104)) == z3950.OID_UNIMARC
    assert z3950._int(z3950.ber_top(body, 29)) == 10


def test_oid_text_round_trips():
    for oid in (z3950.OID_BIB1, z3950.OID_USMARC, z3950.OID_BIB1_DIAG, "1.3.6.1.4.200000"):
        assert z3950.ber_oid_text(z3950.ber_oid(oid)) == oid


# ----------------------------------------------------------------------
# Diagnostics
# ----------------------------------------------------------------------

def test_diagnostic_categories():
    assert z3950.Diagnostic(114).category == "query"
    assert z3950.Diagnostic(123).category == "query"
    assert z3950.Diagnostic(235).category == "config"
    assert z3950.Diagnostic(109).category == "config"
    assert z3950.Diagnostic(2).category == "temporary"
    assert z3950.Diagnostic(17).category == "record"
    assert z3950.Diagnostic(1).category == "other"
    assert z3950.Diagnostic(114, diagset="1.2.3").category == "other"
    assert str(z3950.Diagnostic(114, "1003")) == "diagnostic 114 (1003)"


def test_parse_search_reads_a_non_surrogate_diagnostic():
    body = z3950.ber_decode(search_response(0, ok=False, records=non_surrogate(114, b"1003")))[0][3]
    got = z3950.parse_search(body)
    assert not got.ok and got.total == 0
    assert got.diagnostic == z3950.Diagnostic(114, "1003", z3950.OID_BIB1_DIAG)


def test_parse_search_reads_multiple_diagnostics():
    many = T(205, T(16, diag_format(114, b"7"), True, U) + T(16, diag_format(2), True, U), True)
    got = z3950.parse_search(z3950.ber_decode(search_response(0, ok=False, records=many))[0][3])
    assert [d.code for d in got.diagnostics] == [114, 2]


def test_parse_present_keeps_records_and_surrogates_in_order():
    body = z3950.ber_decode(present_response(npr_record(iso("A", "1")), npr_surrogate(17, b"rec 2"),
                                             npr_record(iso("B", "3")), status=1))[0][3]
    got = z3950.parse_present(body)
    assert [marc.from_iso2709(r).first("001").data for r in got.records] == ["1", "3"]
    assert got.diagnostics == [z3950.Diagnostic(17, "rec 2")] and got.diagnostics[0].category == "record"
    assert got.status == 1
    assert z3950.present_records(body) == got.records


# ----------------------------------------------------------------------
# A session against the fake server
# ----------------------------------------------------------------------

def test_one_init_for_several_searches_then_close():
    server = FakeServer({20: init_response(), 22: [search_response(2), search_response(0)],
                         24: present_response(npr_record(iso("Dom Casmurro", "Z1")), npr_record(iso("Iaiá", "Z2"))),
                         48: close_pdu(0)})

    async def scenario(port):
        async with Session("127.0.0.1", port, timeouts=fast()) as s:
            first = await s.search("Default", Term("8535902775", 7))
            page = await s.present(1, first.total)
            second = await s.search("Default", z3950.and_(Term("Dom Casmurro", 4), Term("Assis", 1003)))
            return s.server, first, page, second, s

    info, first, page, second, s = run(server, scenario)
    assert server.tags == [20, 22, 24, 22, 48]
    assert info == {"id": "81", "name": "Fake Alma", "version": "9.9"}
    assert first.ok and first.total == 2 and second.total == 0
    assert [marc.from_iso2709(r).first("001").data for r in page.records] == ["Z1", "Z2"]
    assert z3950._int(z3950.ber_top(server.seen[-1][1], 211)) == 0          # closeReason finished
    assert not s.is_open


def test_init_sends_the_implementation_name_and_login():
    server = FakeServer({20: init_response(), 48: close_pdu(0)})

    async def scenario(port):
        async with Session("127.0.0.1", port, user="me", password="pw", name="koha.nexus on-demand",
                           version="1.5", timeouts=fast()):
            pass

    run(server, scenario)
    init = server.seen[0][1]
    assert z3950.ber_top(init, 111) == b"koha.nexus on-demand" and z3950.ber_top(init, 112) == b"1.5"
    assert z3950.ber_top(init, 7) is not None


def test_a_refused_search_keeps_the_session_usable():
    server = FakeServer({20: init_response(),
                         22: [search_response(0, ok=False, records=non_surrogate(114, b"7")), search_response(1)],
                         48: close_pdu(0)})

    async def scenario(port):
        async with Session("127.0.0.1", port, timeouts=fast()) as s:
            refused = await s.search("Default", Term("8535902775", 7))
            retry = await s.search("Default", Term("8535902775", 1007))
            return refused, retry

    refused, retry = run(server, scenario)
    assert not refused.ok and refused.diagnostic.code == 114 and refused.diagnostic.category == "query"
    assert retry.ok and retry.total == 1


def test_present_non_surrogate_diagnostic_is_config():
    server = FakeServer({20: init_response(), 22: search_response(1),
                         24: present_response(status=5, records=non_surrogate(239, b"1.2.840.10003.5.10")),
                         48: close_pdu(0)})

    async def scenario(port):
        async with Session("127.0.0.1", port, timeouts=fast()) as s:
            await s.search("d", Term("x"))
            return await s.present(1, 1)

    page = run(server, scenario)
    assert page.records == [] and page.status == 5
    assert page.diagnostics[0].code == 239 and page.diagnostics[0].category == "config"


# ----------------------------------------------------------------------
# Failures: phase and kind
# ----------------------------------------------------------------------

def failure(server: FakeServer, steps, timeouts: Timeouts | None = None) -> tuple[Z3950Error, float, Session]:
    """Run STEPS(session) on a fresh session; the Z3950Error it raised,
    the seconds it took and the session."""
    async def scenario(port):
        s = Session("127.0.0.1", port, timeouts=timeouts or fast())
        start = time.monotonic()
        try:
            await steps(s)
        except Z3950Error as exc:
            return exc, time.monotonic() - start, s
        finally:
            await s.close()
        raise AssertionError("no Z3950Error")
    return run(server, scenario)


async def open_and_search(s: Session):
    await s.open()
    await s.search("d", Term("x"))


def test_init_refused():
    server = FakeServer({20: T(21, T(12, b"\x00") + T(11, T(16, diag_format(101), True, U), True), True)})
    exc, _, s = failure(server, Session.open)
    assert (exc.phase, exc.kind) == ("init", "init-refused")
    assert exc.diagnostic.code == 101 and exc.diagnostic.category == "config"
    assert "login" in str(exc) and not s.is_open


def test_search_timeout_drops_the_session():
    server = FakeServer({20: init_response(), 22: HANG})
    exc, took, s = failure(server, open_and_search, fast(search=0.3))
    assert (exc.phase, exc.kind) == ("search", "timeout")
    assert 0.25 < took < 1.5 and not s.is_open
    assert "did not answer in 0.3s" in str(exc)


def test_present_timeout_is_its_own_phase():
    server = FakeServer({20: init_response(), 22: search_response(1), 24: HANG})

    async def steps(s):
        await open_and_search(s)
        await s.present(1, 1)

    exc, _, _ = failure(server, steps, fast(present=0.3))
    assert (exc.phase, exc.kind) == ("present", "timeout")


def test_the_session_limit_caps_every_phase():
    server = FakeServer({20: init_response(), 22: search_response(0)}, delay=0.3)

    async def steps(s):
        await s.open()
        for _ in range(10):
            await s.search("d", Term("x"))

    exc, took, _ = failure(server, steps, fast(search=5.0, total=0.8))
    assert exc.kind == "timeout" and took < 1.5


def test_connection_closed_mid_session_is_reset():
    server = FakeServer({20: init_response(), 22: DROP})
    exc, _, s = failure(server, open_and_search)
    assert (exc.phase, exc.kind) == ("search", "reset") and not s.is_open


def test_server_close_carries_its_reason():
    server = FakeServer({20: init_response(), 22: close_pdu(4)})
    exc, _, _ = failure(server, open_and_search)
    assert (exc.phase, exc.kind, exc.close_reason) == ("search", "closed", 4)
    assert "resources" in str(exc)


def test_unexpected_apdu_is_protocol():
    server = FakeServer({20: init_response(), 22: present_response()})
    exc, _, _ = failure(server, open_and_search)
    assert (exc.phase, exc.kind) == ("search", "protocol")


def test_unreadable_ber_is_protocol():
    server = FakeServer({20: b"\x75\x02\x8c\x05"})     # [21] whole, but its [12] claims 5 bytes it lacks
    exc, _, _ = failure(server, Session.open)
    assert (exc.phase, exc.kind) == ("init", "protocol")


def test_search_before_open_is_an_error():
    async def main():
        with pytest.raises(Z3950Error) as info:
            await Session("127.0.0.1", 1).search("d", Term("x"))
        return info.value
    exc = asyncio.run(main())
    assert exc.kind == "protocol"


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_connection_refused():
    async def main():
        with pytest.raises(Z3950Error) as info:
            await Session("127.0.0.1", _closed_port(), timeouts=fast()).open()
        return info.value
    exc = asyncio.run(main())
    assert (exc.phase, exc.kind) == ("connect", "refused")


def test_dns_failure_and_connect_timeout(monkeypatch):
    async def no_name(host, port):
        raise socket.gaierror(-2, "Name or service not known")

    async def slow(host, port):
        await asyncio.sleep(10)

    async def attempt():
        with pytest.raises(Z3950Error) as info:
            await Session("nowhere.invalid", 210, timeouts=fast(connect=0.2)).open()
        return info.value

    monkeypatch.setattr(asyncio, "open_connection", no_name)
    exc = asyncio.run(attempt())
    assert (exc.phase, exc.kind) == ("connect", "dns")
    monkeypatch.setattr(asyncio, "open_connection", slow)
    exc = asyncio.run(attempt())
    assert (exc.phase, exc.kind) == ("connect", "timeout")


def test_address_is_where_it_connects_and_host_names_it():
    server = FakeServer({20: init_response(), 22: HANG})

    async def scenario(port):
        s = Session("catalogue.example.org", port, address="127.0.0.1", timeouts=fast(search=0.2))
        await s.open()
        with pytest.raises(Z3950Error) as info:
            await s.search("d", Term("x"))
        return info.value

    exc = run(server, scenario)
    assert str(exc).startswith("catalogue.example.org:")


def test_close_waits_at_most_its_timeout_and_never_raises():
    server = FakeServer({20: init_response(), 48: HANG})

    async def scenario(port):
        s = Session("127.0.0.1", port, timeouts=fast(close=0.3))
        await s.open()
        start = time.monotonic()
        await s.close()
        await s.close()                                  # twice is fine
        return time.monotonic() - start

    took = run(server, scenario)
    assert took < 1.0 and server.tags == [20, 48]


# ----------------------------------------------------------------------
# The gateway's one-shot search()
# ----------------------------------------------------------------------

def test_one_shot_search_returns_no_hits_on_a_refused_search():
    server = FakeServer({20: init_response(), 22: search_response(0, ok=False, records=non_surrogate(114))})

    async def scenario(port):
        return await z3950.search("127.0.0.1", port, "d", "isbn", "85", 1, 20, timeout=2)

    assert run(server, scenario) == (0, [])
    assert server.tags[:2] == [20, 22]           # its Close is not waited for, so the server may not have read it yet


def test_one_shot_search_does_not_wait_on_close():
    server = FakeServer({20: init_response(), 22: search_response(1),
                         24: present_response(npr_record(iso("A", "1"))), 48: HANG})

    async def scenario(port):
        start = time.monotonic()
        got = await z3950.search("127.0.0.1", port, "d", "title", "A", 1, 20, timeout=5)
        return got, time.monotonic() - start

    (total, records), took = run(server, scenario)
    assert total == 1 and len(records) == 1 and took < 1.0
