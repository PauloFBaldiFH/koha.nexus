"""The kind pergamum target searched live through Rede Pergamum (nexus_gateway/pergamum.py)."""

from __future__ import annotations

import asyncio
import http.server
import threading
import urllib.parse
from pathlib import Path

import pytest

from nexus_gateway import live, pergamum
from nexus_gateway.engine import Engine, Static
from nexus_gateway.learned import Learned
from nexus_gateway.targets import load, make_target

FIX = Path(__file__).parent / "fixtures"
TARGETS = Path(__file__).resolve().parents[1] / "nexus_gateway" / "targets.json"
RESULTS = (FIX / "pergamum_results.html").read_text(encoding="utf-8")
MARC_PAGE = (FIX / "pergamum_marc.html").read_text(encoding="utf-8")
TOO_MANY = (FIX / "pergamum_too_many.html").read_text(encoding="utf-8")


def target():
    return make_target({"id": "all", "name": "Rede Pergamum", "group": "specialized", "kind": "pergamum",
                        "status": "verified"})


class FakeGet:
    def __init__(self, results=RESULTS, marc_page=MARC_PAGE):
        self.results, self.marc_page, self.calls = results, marc_page, []

    def __call__(self, params, timeout):
        self.calls.append(params)
        if dict(params)["rs"] == "ajax_resultados":
            return self.results
        return self.marc_page


def test_marc_text_to_record():
    rec = pergamum.text_to_record(pergamum.extract_marc(MARC_PAGE))
    assert [f.tag for f in rec.fields] == ["001", "005", "020", "100", "245", "260", "650"]
    assert rec.leader == pergamum.DEFAULT_LEADER
    assert rec.control("001") == "98765"
    f100 = rec.first("100")
    assert (f100.ind1, f100.ind2) == ("1", " ")
    f245 = rec.first("245")
    assert (f245.ind1, f245.ind2) == ("1", "0")
    assert f245.get("c") == "Machado de Assis ; ilustrações de João & Cia."
    assert rec.first("260").get("a") == "São Paulo :"
    assert rec.first("650").get("a") == "Ficção brasileira." and rec.first("650").ind2 == "4"
    # "852    $" and "090    $" carry no subfield: dropped, or Koha refuses the record
    assert all(f.subfields for f in rec.fields if not f.is_control)


def test_leader_line_is_used():
    rec = pergamum.text_to_record("LDR 01234nam a2200277 a 4500\r001 1\r")
    assert rec.leader == "01234nam a2200277 a 4500"
    assert [f.tag for f in rec.fields] == ["001"]


def test_xml_invalid_controls_are_dropped():
    rec = pergamum.text_to_record("245 10 $a Bad\x01char\x0bs")
    assert rec.first("245").get("a") == "Bad char s"


def test_parse_results():
    assert pergamum.parse_results(RESULTS) == (2, ["98765", "11111"])
    assert pergamum.parse_results("N&uacute;mero de Registros Encontrados: <b>1.234</b>")[0] == 1234
    assert pergamum.parse_results("nada") == (0, [])


def test_escaped_markers():
    assert pergamum.extract_marc("x&lt;inicio&gt;001 1&lt;fim&gt;y") == "001 1"


@pytest.mark.parametrize("kind,term,ptype,clean", [
    ("isbn", "978-85-359-0277-8", "ISBN", "9788535902778"),
    ("author", "Machado de Assis", "AUTOR", "Machado de Assis"),
    ("title", '"Dom Casmurro"', "TITULO", "Dom Casmurro"),
    ("keywords", "casmurro", "TITULO", "casmurro"),
])
def test_search_asks_the_right_type(kind, term, ptype, clean):
    get = FakeGet()
    total, recs = pergamum.Pergamum(get=get).search(kind, term, 20, 5)
    args = [v for k, v in get.calls[0] if k == "rsargs[]"]
    assert (args[1], args[2], args[4]) == (clean, ptype, "50")
    assert total == 2 and len(recs) == 2
    assert sorted(dict(p)["rsargs[]"] for p in get.calls[1:]) == ["11111", "98765"]


def test_search_fetches_only_the_limit():
    get = FakeGet()
    total, recs = pergamum.Pergamum(get=get).search("title", "x", 1, 5)
    assert total == 2 and len(recs) == 1
    assert [dict(p)["rsargs[]"] for p in get.calls[1:]] == ["98765"]


def test_no_hits():
    get = FakeGet(results="+:var res = 'Nenhum registro'; res;")
    assert pergamum.Pergamum(get=get).search("title", "zzz", 20, 5) == (0, [])
    assert len(get.calls) == 1


# ----------------------------------------------------------------------
# "Resultado maior que 500 linhas. Refine melhor a busca !"
# ----------------------------------------------------------------------
@pytest.mark.parametrize("page", [
    TOO_MANY,
    "Resultado maior que 500 linhas. Refine melhor a busca !",
    "+:var res = 'Resultado&nbsp;maior que 500 linhas.<br>Refine melhor a busca !'; res;",
    "<p>RESULTADO MAIOR QUE 500\n  LINHAS</p>",
])
def test_the_500_line_refusal_is_recognised(page):
    assert pergamum.too_many_results(page)
    with pytest.raises(pergamum.PergamumExcessiveResultsError) as exc:
        pergamum.parse_results(page, "TITULO", "Jesus")
    assert "more than 500" in str(exc.value) and "refine" in str(exc.value)
    assert (exc.value.ptype, exc.value.term) == ("TITULO", "Jesus")


def test_ordinary_pages_are_not_the_refusal():
    assert not pergamum.too_many_results(RESULTS)
    assert not pergamum.too_many_results("+:var res = 'Nenhum registro'; res;")
    # a record about the number 500 is not the refusal
    assert not pergamum.too_many_results("245 10 $a Os 500 anos do Brasil")


def test_refusal_is_a_pergamum_error():
    # live.ask and every caller that catches PergamumError still catch it
    assert issubclass(pergamum.PergamumExcessiveResultsError, pergamum.PergamumError)


def test_search_raises_on_the_refusal_and_fetches_no_record(caplog):
    get = FakeGet(results=TOO_MANY)
    with caplog.at_level("WARNING", logger="nexus_gateway.pergamum"):
        with pytest.raises(pergamum.PergamumExcessiveResultsError):
            pergamum.Pergamum(get=get).search("author", "Jesus", 20, 5)
    assert len(get.calls) == 1                      # no MARC page asked for
    assert "more than 500 hits" in caplog.text and "'Jesus'" in caplog.text


def test_ask_reports_the_refusal_as_the_answer_error():
    crp = pergamum.Pergamum(get=FakeGet(results=TOO_MANY))
    answer = asyncio.run(live.ask(target(), "title", "Jesus", 5, pergamum=crp))
    assert answer.records == [] and answer.total == 0
    assert "more than 500" in answer.error and "refine" in answer.error


def test_a_record_that_fails_is_left_out():
    class Flaky(FakeGet):
        def __call__(self, params, timeout):
            if dict(params).get("rsargs[]") == "11111":
                raise pergamum.PergamumError("down")
            return super().__call__(params, timeout)
    total, recs = pergamum.Pergamum(get=Flaky()).search("title", "x", 20, 5)
    assert total == 2 and [r.control("001") for r in recs] == ["98765"]


class _Handler(http.server.BaseHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        type(self).seen.append((q.get("rs", [""])[0], self.headers.get("Cookie", "")))
        rs = q.get("rs", [""])[0]
        if not rs:
            status, body, extra = 200, "<html>pesquisa</html>", [("Set-Cookie", "PHPSESSID=abc; Path=/")]
        elif rs == "ajax_resultados" and q["rsargs[]"][1] == "nada":
            status, body, extra = 500, "+:var res = ''; res;", []
        elif rs == "ajax_resultados" and q["rsargs[]"][1] == "Jesus":
            # the refusal comes in Pergamum's own Latin-1, under HTTP 500
            status, body, extra = 500, TOO_MANY, []
        elif rs == "ajax_resultados":
            status, body, extra = 200, RESULTS, []
        else:
            status, body, extra = 200, MARC_PAGE, []
        charset = "iso-8859-1" if body is TOO_MANY else "utf-8"
        data = body.encode(charset)
        self.send_response(status)
        self.send_header("Content-Type", f"text/html; charset={charset}")
        for k, v in extra:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def site():
    _Handler.seen = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/pesquisa.php"
    srv.shutdown()


def test_session_cookie_and_http_500_without_hits(site):
    crp = pergamum.Pergamum(site)
    total, recs = crp.search("isbn", "9788535902778", 20, 5)
    assert total == 2 and len(recs) == 2 and recs[0].first("245") is not None
    assert crp.search("title", "nada", 20, 5) == (0, [])
    opens = [s for s in _Handler.seen if s[0] == ""]
    assert len(opens) == 1 and _Handler.seen[0][0] == ""
    assert all("PHPSESSID=abc" in cookie for rs, cookie in _Handler.seen[1:])


def test_refusal_under_http_500_is_not_a_bare_http_error(site):
    with pytest.raises(pergamum.PergamumExcessiveResultsError):
        pergamum.Pergamum(site).search("title", "Jesus", 20, 5)
    assert [rs for rs, _ in _Handler.seen].count("ajax_conteudo_pastas") == 0


def test_without_an_address_the_target_answers_an_error():
    answer = asyncio.run(live.ask(target(), "title", "x", 5))
    assert answer.records == [] and "NEXUS_GATEWAY_PERGAMUM_URL" in answer.error


def test_ask_with_an_address_returns_records():
    crp = pergamum.Pergamum(get=FakeGet())
    answer = asyncio.run(live.ask(target(), "title", "casmurro", 5, pergamum=crp))
    assert not answer.error and answer.total == 2 and len(answer.records) == 2


def test_live_only_with_an_address_also_from_union(tmp_path):
    targets = load(TARGETS)
    assert targets["all"].kind == "pergamum"

    class Runner:
        zeus = None
        pergamum = None

    runner = Runner()
    engine = Engine(Static(tmp_path / "none.db"), Learned(tmp_path / "l.db"), targets, runner)
    assert engine.resolve("all")[1] == []
    runner.pergamum = pergamum.Pergamum(get=FakeGet())
    assert [t.id for t in engine.resolve("all")[1]] == ["all"]
    assert "all" in [t.id for t in engine.resolve("_union")[1]]
    runner.pergamum = None
    assert "all" not in [t.id for t in engine.resolve("_union")[1]]
