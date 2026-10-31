"""nexus_gateway: static search, the live path through learned.db, the
Z39.50 and SRU clients against local fake servers, the HTTP server and the
Koha SQL."""

import asyncio
import json
import re
import shutil
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from conftest import bib

from enrich_build.build import Builder, SourceConfig
from nexus_enrich import marc
from nexus_enrich.marc import Field
from nexus_gateway import cql, koha_sql, live, upstream, z3950
from nexus_gateway.config import Settings
from nexus_gateway.engine import Engine, Static, UnknownDatabase, live_clause, query_key
from nexus_gateway.learned import Learned
from nexus_gateway.server import make_server
from nexus_gateway.targets import TargetError, load, local_first, make_target

ISBN = "9788535902778"
TARGETS = Path(__file__).resolve().parents[1] / "nexus_gateway" / "targets.json"
ZS = "{http://www.loc.gov/zing/srw/}"


def jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


@pytest.fixture(scope="module")
def static_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("static")
    rich = bib("Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, rid="U1",
               subjects=[Field("650", " ", "4", [("a", "Cegueira"), ("9", "123")])],
               extra=[Field("082", "0", "4", [("a", "869.3")]), Field("952", " ", " ", [("a", "BIB")])])
    plain = bib("Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, rid="F1")
    jsonl(d / "dump.jsonl", [
        {"fonte": "Universidade Federal do Paraná (UFPR)", "marcxml": marc.to_xml(rich)},
        {"fonte": "Fundação Jorge Duprat Figueiredo (Fundacentro)", "marcxml": marc.to_xml(plain)},
        {"fonte": "Universidade de Brasília (UnB)",
         "marcxml": marc.to_xml(bib("Memorial do convento", "Saramago, José", year=1982, rid="B1"))},
        {"fonte": "Universidade de Brasília (UnB)",
         "marcxml": marc.to_xml(bib("Vidas secas", "Ramos, Graciliano", year=1938, rid="B2"))},
        {"fonte": "Biblioteca X (bx)",
         "marcxml": marc.to_xml(bib("Somente aqui", "Autor, Único", year=2001, rid="X1"))},
    ])
    src = SourceConfig.from_dict({"id": "zeus", "paths": ["dump.jsonl"], "mode": "full", "brazilian": True,
                                  "source_field": "fonte"})
    out = d / "static.db"
    report = Builder(out, [src], d).build()
    assert report.error_count == 0
    return out


def run(engine, query, database="_union", start=1, maximum=10):
    return engine.search(database, cql.parse(query), start, maximum)


def ids(result):
    return [r.control("001") for r in result.records]


@pytest.fixture
def engine(static_db, tmp_path):
    return Engine(Static(static_db), Learned(tmp_path / "learned.db"), load(TARGETS))


# ----------------------------------------------------------------------
# static.db
# ----------------------------------------------------------------------
def test_union_isbn_title_author_and_boolean(engine):
    r = run(engine, f"dc.isbn={ISBN}")
    assert r.origin == "static" and ids(r) == ["U1", "F1"]      # most complete first
    assert ids(run(engine, "isbn=978-85-359-0277-8")) == ["U1", "F1"]
    assert ids(run(engine, "isbn=8535902775")) == ["U1", "F1"]
    assert sorted(ids(run(engine, 'dc.creator="saramago" and dc.title=memorial'))) == ["B1"]
    assert sorted(ids(run(engine, "dc.title=memorial or dc.title=vidas"))) == ["B1", "B2"]
    assert sorted(ids(run(engine, "dc.creator=saramago not dc.title=cegueira"))) == ["B1"]
    assert sorted(ids(run(engine, "secas"))) == ["B2"]
    assert run(engine, "dc.title=inexistente").total == 0


def test_paging(engine):
    r = run(engine, "saramago", start=2, maximum=1)
    assert r.total == 3 and len(r.records) == 1


def test_target_and_source_databases(engine):
    assert ids(run(engine, f"isbn={ISBN}", "ufpr")) == ["U1"]
    assert ids(run(engine, f"isbn={ISBN}", "fundacentro")) == ["F1"]
    assert sorted(ids(run(engine, "saramago or ramos", "unb"))) == ["B1", "B2"]
    assert ids(run(engine, "somente", "bx")) == ["X1"]            # a static.db source with no target
    assert run(engine, "somente", "ufpr").total == 0
    with pytest.raises(UnknownDatabase):
        engine.resolve("nowhere")


def test_records_go_out_without_9xx_and_dollar_9(engine):
    rec = run(engine, f"isbn={ISBN}", "ufpr").records[0]
    assert not rec.get_fields("952")
    assert rec.first("650").subfields == [("a", "Cegueira")]
    assert rec.first("082").get("a") == "869.3"


def test_static_db_replaced_in_place_is_reopened(static_db, tmp_path):
    path = tmp_path / "static.db"
    shutil.copy(static_db, path)
    static = Static(path)
    eng = Engine(static, None, load(TARGETS))
    assert run(eng, "secas").total == 1
    path.unlink()
    assert run(eng, "secas").total == 0 and static.info() == {"present": False}
    shutil.copy(static_db, tmp_path / "new.db")
    (tmp_path / "new.db").replace(path)
    assert run(eng, "secas").total == 1


# ----------------------------------------------------------------------
# live path
# ----------------------------------------------------------------------
def test_live_clause_and_key():
    assert live_clause(cql.parse('dc.title=x and dc.isbn=978-85-359-0277-8')).field == "isbn"
    assert live_clause(cql.parse('dc.creator=a and dc.title=b')).field == "title"
    assert live_clause(cql.parse('(dc.title=a or dc.title=b) not dc.creator=c')).term == "a"
    assert live_clause(cql.parse("cql.allRecords=1")) is None
    assert query_key(live_clause(cql.parse("isbn=8535902775"))) == "isbn:" + ISBN
    assert query_key(live_clause(cql.parse('title="Dom  Casmurro!"'))) == "title:dom casmurro"


class FakeAsker:
    def __init__(self, delay=0.0, error=""):
        self.delay, self.error, self.calls = delay, error, []

    async def __call__(self, target, kind, term, timeout):
        self.calls.append((target.id, kind, term))
        await asyncio.sleep(self.delay)
        if self.error:
            return live.Answer(target.id, 0, [], self.error)
        rec = bib(f"Livro de {target.id}", "Autor", year=2020, rid=f"{target.id}-1",
                  extra=[Field("999", " ", " ", [("c", "1")])])
        return live.Answer(target.id, 1, [rec])


def live_engine(static_db, tmp_path, asker, budget=2.0):
    learned = Learned(tmp_path / "learned.db")
    targets = {t.id: t for t in (
        make_target({"id": "loc", "name": "LoC", "group": "national", "kind": "z3950", "host": "h", "port": 210,
                     "db": "LCDB", "status": "verified"}),
        make_target({"id": "yale", "name": "Yale", "group": "intl_universities", "kind": "sru",
                     "url": "https://x/sru", "status": "verified"}),
        make_target({"id": "dead", "name": "Dead", "group": "national", "kind": "z3950", "host": "h", "port": 1,
                     "db": "d", "status": "broken"}),
        make_target({"id": "ufpr", "name": "UFPR", "group": "br_universities", "kind": "missing",
                     "status": "missing"}),
    )}
    runner = live.Runner(learned, budget=budget, grace=5.0, asker=asker)
    return Engine(Static(static_db), learned, targets, runner)


def test_static_hit_never_goes_live(static_db, tmp_path):
    asker = FakeAsker()
    eng = live_engine(static_db, tmp_path, asker)
    assert run(eng, f"isbn={ISBN}").origin == "static" and asker.calls == []
    eng.runner.close()


def test_miss_goes_live_then_learned(static_db, tmp_path):
    asker = FakeAsker()
    eng = live_engine(static_db, tmp_path, asker)
    r = run(eng, 'dc.title="nada aqui"')
    assert r.origin == "live" and ids(r) == ["loc-1", "yale-1"]   # broken and static-only targets not asked
    assert not r.records[0].get_fields("999")
    assert sorted(c[0] for c in asker.calls) == ["loc", "yale"]
    r2 = run(eng, 'title="Nada  aqui"')                            # same key: from learned.db
    assert r2.origin == "learned" and ids(r2) == ["loc-1", "yale-1"] and len(asker.calls) == 2
    assert ids(run(eng, 'dc.title="nada aqui"', "yale")) == ["yale-1"]
    assert run(eng, 'dc.title="nada aqui"', "ufpr").origin == "none"   # static-only target
    eng.runner.close()


def test_late_answer_lands_in_learned(static_db, tmp_path):
    asker = FakeAsker(delay=0.6)
    eng = live_engine(static_db, tmp_path, asker, budget=0.1)
    started = time.monotonic()
    r = run(eng, "dc.title=tarde")
    assert r.total == 0 and time.monotonic() - started < 0.5
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and eng.learned.get("yale", "title:tarde") is None:
        time.sleep(0.05)
    assert ids(run(eng, "dc.title=tarde")) == ["loc-1", "yale-1"]
    eng.runner.close()


def test_errors_are_kept_briefly(static_db, tmp_path):
    asker = FakeAsker(error="refused")
    eng = live_engine(static_db, tmp_path, asker)
    r = run(eng, "dc.title=erro")
    assert r.total == 0 and r.errors == {"loc": "refused", "yale": "refused"}
    run(eng, "dc.title=erro")
    assert len(asker.calls) == 2                                    # not asked again at once
    assert eng.learned.get("loc", "title:erro", now=time.time() + 601) is None
    eng.runner.close()


# ----------------------------------------------------------------------
# Z39.50 and SRU clients
# ----------------------------------------------------------------------
T = z3950.tlv
U = z3950.UNIVERSAL


def test_z3950_client_against_a_fake_server():
    raw = marc.to_iso2709(bib("Dom Casmurro", "Assis, Machado de", year=1899, rid="Z1"))
    seen = {}

    async def handle(reader, writer):
        while True:
            try:
                pdu = await z3950.read_pdu(reader)
            except asyncio.IncompleteReadError:
                break
            tag = z3950.ber_decode(pdu)[0][1]
            if tag == 20:
                resp = T(21, T(12, b"\xff"), True)
            elif tag == 22:
                seen["search"] = pdu
                resp = T(23, T(23, z3950.ber_int(1)) + T(22, b"\xff"), True)
            else:
                npr = T(16, T(0, b"Default") + T(1, T(16, T(6, z3950.ber_oid(z3950.OID_USMARC), cls=U)
                                                      + T(1, raw), True, U), True), True, U)
                resp = T(25, T(28, npr, True), True)
            writer.write(resp)
            await writer.drain()
        writer.close()

    async def main():
        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            return await z3950.search("127.0.0.1", port, "Default", "isbn", "8535902775", 1, 20, timeout=5)

    total, records = asyncio.run(main())
    assert total == 1 and marc.from_iso2709(records[0]).first("245").get("a") == "Dom Casmurro"
    assert b"8535902775" in seen["search"]


def test_z3950_unreachable_is_an_error():
    with pytest.raises(z3950.Z3950Error):
        asyncio.run(z3950.search("127.0.0.1", 1, "d", "title", "x", 1, 5, timeout=2))


def sru_body(records, packing="xml"):
    datas = []
    for i, r in enumerate(records, 1):
        xml = marc.to_xml(r)
        if packing == "string":
            xml = xml.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        datas.append(f"<zs:record><zs:recordSchema>marcxml</zs:recordSchema><zs:recordPacking>{packing}"
                     f"</zs:recordPacking><zs:recordData>{xml}</zs:recordData>"
                     f"<zs:recordPosition>{i}</zs:recordPosition></zs:record>")
    return ('<?xml version="1.0"?><zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">'
            f"<zs:version>1.1</zs:version><zs:numberOfRecords>{len(records)}</zs:numberOfRecords>"
            f"<zs:records>{''.join(datas)}</zs:records></zs:searchRetrieveResponse>").encode()


def test_sru_parse_both_packings():
    recs = [bib("Iracema", "Alencar, José de", year=1865, rid="S1")]
    for packing in ("xml", "string"):
        total, got, diag = upstream.parse_response(sru_body(recs, packing))
        assert total == 1 and got[0].first("245").get("a") == "Iracema" and diag == ""


def test_sru_client_against_a_fake_server():
    asked = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            asked["path"] = self.path
            body = sru_body([bib("Iracema", "Alencar, José de", year=1865, rid="S1")])
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        t = make_target({"id": "yale", "name": "Yale", "group": "intl_universities", "kind": "sru",
                         "url": f"http://127.0.0.1:{srv.server_address[1]}/view/sru/X",
                         "indexes": {"title": "alma.title"}})
        total, records = upstream.search(t, "title", 'Ira"cema', 1, 20, timeout=5)
    finally:
        srv.shutdown()
    assert total == 1 and records[0].control("001") == "S1"
    assert "alma.title%3D%22Ira%5C%22cema%22" in asked["path"]


# ----------------------------------------------------------------------
# HTTP server
# ----------------------------------------------------------------------
@pytest.fixture
def http(static_db, tmp_path):
    settings = Settings(port=0, static_db=static_db, learned_db=tmp_path / "l.db", live=False)
    eng = Engine(Static(static_db), Learned(settings.learned_db), load(TARGETS))
    srv = make_server(eng, settings)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read()


def test_http_search_explain_health(http):
    root = ET.fromstring(get(f"{http}/sru/_union?version=1.1&operation=searchRetrieve&query=dc.isbn%3D{ISBN}"
                             "&recordSchema=marcxml&maximumRecords=5"))
    assert root.find(f"{ZS}numberOfRecords").text == "2"
    assert len(marc.parse_xml(ET.tostring(root))) == 2
    root = ET.fromstring(get(f"{http}/sru/ufpr?operation=explain"))
    assert root.tag == f"{ZS}explainResponse"
    root = ET.fromstring(get(f"{http}/sru/nowhere?query=x"))
    assert "235" in ET.tostring(root, encoding="unicode")
    root = ET.fromstring(get(f"{http}/sru/_union?query=dc.title%3D%28"))
    assert "diagnostic/1/10" in ET.tostring(root, encoding="unicode")
    health = json.loads(get(f"{http}/health"))
    assert health["status"] == "ok" and health["static"]["present"] and health["static"]["records"] == 5


def test_http_post_form(http):
    req = urllib.request.Request(f"{http}/sru/unb", data=b"operation=searchRetrieve&query=vidas", method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        root = ET.fromstring(resp.read())
    assert root.find(f"{ZS}numberOfRecords").text == "1"


def test_http_post_bad_length_is_refused(http):
    host, port = http.rsplit("/", 1)[1].split(":")
    for bad in ("-1", "abc"):
        with socket.create_connection((host, int(port)), timeout=5) as s:
            s.sendall(f"POST /sru/unb HTTP/1.1\r\nHost: x\r\nContent-Length: {bad}\r\n\r\nquery=vidas".encode())
            got = s.recv(64)
            assert got.split(b" ")[1] == b"400", (bad, got)


# ----------------------------------------------------------------------
# targets and Koha SQL
# ----------------------------------------------------------------------
def test_targets_file():
    table = load(TARGETS)
    assert len(table) == 73 and "unb" in table and "_union" not in table
    assert {t.kind for t in table.values() if t.live} == {"z3950", "sru"}
    assert not table["bl"].live and table["loc"].live                # broken is never asked
    assert table["nga"].static == ("nga", "national-gallery")


def test_koha_sql():
    table = load(TARGETS)
    sql = koha_sql.render(table)
    assert sql.count("INSERT INTO z3950servers") == len(table) + 2       # sru/_union and sru/_union-aut
    assert "'sru/_union', 'KOHA.NEXUS (TODOS OS CATÁLOGOS)', 1, 0" in sql
    assert "SET checked = IF(db IN ('sru/_union', 'sru/all'), 1, 0)" in sql      # Rede Pergamum ticked too
    # Koha's rows are on the Cloudflare tunnel; after step 1 nothing points at the local gateway.
    assert "host = 'https://sru.koha.nexus' AND port = 443" in sql
    assert "host = '127.0.0.1'" not in sql.split("-- 2.")[1].split("-- 6.")[0]
    assert "UPDATE z3950servers SET host = 'https://sru.koha.nexus', port = 443 WHERE recordtype = 'authority'" in sql
    assert sql.strip().endswith("COMMIT;")
    assert koha_sql.q("O'Brien") == "'O''Brien'"


def test_koha_sql_local_first():
    table = load(TARGETS)
    assert [t.id for t in local_first(table)] == ["unesp", "ufpr", "unifesp", "unb", "ufu"]
    sql = koha_sql.render(table)
    seven = sql.split("-- 7.")[1].split("-- 8.")[0]
    for rank, tid in enumerate(["unesp", "ufpr", "unifesp", "unb", "ufu"], 1):
        assert f"SET checked = 1, `rank` = {rank} WHERE" in seven and f"db = 'sru/{tid}'" in seven
    assert seven.count("NOT EXISTS (SELECT 1 FROM koha_nexus_legacy_z3950 WHERE id = 0)") == 5
    eight = sql.split("-- 8.")[1]
    assert eight.count("INSERT IGNORE INTO koha_nexus_legacy_z3950") == 5
    assert "SET z.checked = 0, z.`rank` = GREATEST(IFNULL(z.`rank`, 0), 900), b.state = 'demoted'" in eight
    # The table is created before the transaction (DDL would commit it).
    assert sql.index("CREATE TABLE IF NOT EXISTS koha_nexus_legacy_z3950") < sql.index("START TRANSACTION")
    undo = koha_sql.render_undo(table)
    assert "z.`rank` = b.rank_before, z.checked = b.checked_before, b.state = 'restored'" in undo
    assert "VALUES (0, '_off', 'off')" in undo and undo.count("SET checked = 0") == 5
    redo = koha_sql.render_redo(table)
    assert redo.index("DELETE FROM koha_nexus_legacy_z3950;") < redo.index("-- 7.")


def test_legacy_hosts_match_the_institution_only():
    unesp, unb = load(TARGETS)["unesp"], load(TARGETS)["unb"]
    pattern = koha_sql.legacy_match(unesp)
    assert "host REGEXP '(^|[/.])unesp[.]alma[.]exlibrisgroup[.]com([:/]|$)'" in pattern
    res = [re.compile(r) for r in re.findall(r"REGEXP '([^']+)'", koha_sql.legacy_match(unb))]
    hit = [h for h in ("unb.br", "bce.unb.br", "https://z3950.bce.unb.br/sru", "fundunb.br", "unb.br.example.com",
                       "sru.koha.nexus") if any(r.search(h) for r in res)]
    assert hit == ["unb.br", "bce.unb.br", "https://z3950.bce.unb.br/sru"]


def test_local_first_entries_are_checked(tmp_path):
    base = {"name": "X", "group": "br_universities", "kind": "missing"}
    with pytest.raises(TargetError, match="legacy_hosts"):
        make_target({**base, "id": "x", "legacy_hosts": ["not a host"]})
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"targets": [{**base, "id": "a", "local_first": 1},
                                            {**base, "id": "b", "local_first": 1}]}))
    with pytest.raises(TargetError, match="local_first"):
        load(path)


def test_koha_sql_removes_the_retired_bridges():
    sql = koha_sql.render(load(TARGETS))
    zero = sql.split("-- 0.")[1].split("-- 1.")[0]
    assert "port = 5000 AND IFNULL(db, '') IN ('', 'sru', '/sru')" in zero
    assert "port = 5006" in zero and "recordtype = 'biblio'" in zero


def test_panel_list_is_generated_from_targets_json():
    # The panel's curated list must be python -m nexus_gateway panel-list's output.
    current = koha_sql.PANEL_LIST.read_text(encoding="utf-8")
    assert koha_sql.panel_list(load(TARGETS)) == current
    data = json.loads(current)
    rows = data["targets"]
    # First the koha.nexus servers: the shared catalogue and Rede Pergamum on the gateway, preselected.
    assert [(t["host"], t["db"], t["region"], t["rank"], t["preselect"]) for t in rows[:2]] == [
        ("catalog.koha.nexus", "sru", "koha_nexus", 1, True), ("sru.koha.nexus", "sru/all", "koha_nexus", 2, True)]
    assert rows[0]["name"] == "Rede koha.nexus (Catalogação Compartilhada)"
    # Then the local-first catalogues (static.db holds them nearly whole), preselected, ranked 1 to 5.
    assert [(t["db"], t["rank"], t["preselect"], t["priority"]) for t in rows[2:7]] == [
        ("sru/unesp", 1, True, "primary"), ("sru/ufpr", 2, True, "primary"), ("sru/unifesp", 3, True, "primary"),
        ("sru/unb", 4, True, "primary"), ("sru/ufu", 5, True, "primary")]
    assert "direct Z39.50 row UNIFESP" in rows[4]["notes"] and "backup_for" not in rows[4]
    rows = rows[7:]
    # Then the direct Z39.50 servers (the primary targets), straight to the libraries; a local-first
    # library's own server is its gateway row's backup.
    direct = [t for t in rows if t["source"] == koha_sql.DIRECT_SOURCE]
    direct_biblio = [t for t in direct if t.get("recordtype") != "authority"]
    assert rows[:len(direct_biblio)] == direct_biblio and len(direct) - len(direct_biblio) == 16
    assert {t["kind"] for t in direct} == {"zed"}
    backups = {t["host"]: t["backup_for"] for t in direct if t["priority"] == "fallback"}
    assert backups == {"z3950.unifesp.br": ["sru.koha.nexus:443/sru/unifesp"],
                       "unesp.alma.exlibrisgroup.com": ["sru.koha.nexus:443/sru/unesp"]}
    assert not any(t["preselect"] for t in direct if t["priority"] == "fallback")
    assert rows[0]["db"] == "biblioteca" and rows[0]["host"] == "z3950.utfpr.edu.br"
    # Then the authority files, then the gateway rows: the fallback, never ticked, ranked after the direct servers.
    assert [t["db"] for t in rows if t.get("recordtype") == "authority" and t["source"] != koha_sql.DIRECT_SOURCE] \
        == ["NAF", "SAF", "sru/bn-aut", "sru/_union-aut"]
    fallback = [t for t in rows if t.get("priority") == "fallback" and t["source"] != koha_sql.DIRECT_SOURCE]
    assert fallback[0]["db"] == "sru/_union" and rows[-len(fallback):] == fallback
    assert not {"sru/unesp", "sru/ufpr", "sru/unifesp", "sru/unb", "sru/ufu"} & {t["db"] for t in fallback}
    assert {(t["host"], t["port"]) for t in fallback} == {("sru.koha.nexus", 443)}
    assert not any(t["preselect"] for t in fallback)
    assert [t["rank"] for t in fallback] == list(range(koha_sql.FALLBACK_RANK, koha_sql.FALLBACK_RANK + len(fallback)))
    assert [t["db"] for t in rows if t.get("preselect")] == ["biblioteca", "Default"]
    # A gateway row a direct server covers says so; the flags come from the countries.
    utfpr = next(t for t in fallback if t["db"] == "sru/utfpr")
    assert "direct Z39.50 row UTFPR" in utfpr["notes"] and utfpr["flag"] == "🇧🇷"
    assert fallback[0]["flag"] == "🌐" and koha_sql.flag("gb") == "🇬🇧"


# ----------------------------------------------------------------------
# repository (Dublin Core) records do not stop the live search
# ----------------------------------------------------------------------
def dc_record(title, rid):
    """A repository record as the UNESP/UFPR harvests hold them: Dublin Core
    turned into MARC."""
    rec = marc.Record(leader="00000nam a2200000 a 4500")
    rec.fields += [Field("001", data=rid),
                   Field("024", "8", " ", [("a", f"http://hdl.handle.net/11449/{rid}")]),
                   Field("042", " ", " ", [("a", "dc")]),
                   Field("245", "0", "0", [("a", title)]),
                   Field("260", " ", " ", [("c", "2019")]),
                   Field("520", " ", " ", [("a", "Resumo.")]),
                   Field("653", " ", " ", [("a", "Cervantes")]),
                   Field("720", " ", " ", [("a", "Silva, Ana"), ("e", "author")])]
    return rec


@pytest.fixture(scope="module")
def repo_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("repo")
    jsonl(d / "dump.jsonl", [
        {"fonte": "unesp", "marcxml": marc.to_xml(dc_record("O Quixote na sala de aula", "R1"))},
        {"fonte": "unesp", "marcxml": marc.to_xml(dc_record("Leituras do Quixote", "R2"))},
        {"fonte": "unesp", "marcxml": marc.to_xml(bib("Grande sertão", "Rosa, João Guimarães", rid="C1"))},
        {"fonte": "unesp", "marcxml": marc.to_xml(dc_record("Grande sertão em teses", "R3"))},
    ])
    src = SourceConfig.from_dict({"id": "zeus", "paths": ["dump.jsonl"], "mode": "full", "source_field": "fonte"})
    out = d / "static.db"
    assert Builder(out, [src], d).build().error_count == 0
    return out


def test_catalogue_record():
    from nexus_gateway.engine import catalogue_record
    assert not catalogue_record(dc_record("x", "R"))
    assert catalogue_record(bib("x", "Autor"))
    assert catalogue_record(bib("x", extent=None, isbn=ISBN))


def test_repository_hits_still_go_live_and_come_after(repo_db, tmp_path):
    asker = FakeAsker()
    eng = live_engine(repo_db, tmp_path, asker)
    r = run(eng, "dc.title=quixote")
    assert r.origin == "live" and r.total == 4
    assert ids(r) == ["loc-1", "yale-1", "R1", "R2"]
    # pages run on from the live records into the repository ones
    assert len(ids(run(eng, "dc.title=quixote", start=2, maximum=2))) == 2
    assert ids(run(eng, "dc.title=quixote", start=3, maximum=2)) == ["R1", "R2"]
    assert ids(run(eng, "dc.title=quixote", start=4, maximum=2)) == ["R2"]
    eng.runner.close()


def test_a_catalogue_hit_never_goes_live(repo_db, tmp_path):
    asker = FakeAsker()
    eng = live_engine(repo_db, tmp_path, asker)
    r = run(eng, 'dc.title="grande sertão"')
    assert r.origin == "static" and ids(r)[0] == "C1" and asker.calls == []
    eng.runner.close()


def test_repository_hits_stay_when_nothing_live(repo_db, tmp_path):
    eng = Engine(Static(repo_db), Learned(tmp_path / "l.db"), load(TARGETS))      # no runner
    r = run(eng, "dc.title=quixote", database="unesp")
    assert r.origin == "static" and sorted(ids(r)) == ["R1", "R2"]
    asker = FakeAsker(error="refused")
    eng = live_engine(repo_db, tmp_path, asker)
    r = run(eng, "dc.title=quixote")
    assert r.origin == "static" and ids(r) == ["R1", "R2"] and r.errors
    eng.runner.close()
