"""Module 2, the AI assistant: SQL guard, tools, agent loop, links, widget."""

import asyncio
import json
import time

import pytest
from conftest import INSTALLER

from kei_panel.assistant import db as dbmod
from kei_panel.assistant import links, llm, sqlguard, tools
from kei_panel.assistant.agent import Agent, DemoModel, parse_envelope
from kei_panel.env import PanelEnv


# ----------------------------------------------------------------------
# sqlguard
# ----------------------------------------------------------------------
@pytest.mark.parametrize("sql", [
    "SELECT title FROM biblio WHERE title = 'Drop dead gorgeous'",       # keyword inside a string
    "select count(*) from issues where date_due < NOW();",
    "WITH x AS (SELECT 1 AS n) SELECT n FROM x",
    "SELECT REPLACE(title, 'a', 'b') FROM biblio",
])
def test_select_allowed(sql):
    out = sqlguard.check_select(sql)
    assert out.startswith("SELECT * FROM (") and out.endswith("LIMIT 50")


@pytest.mark.parametrize("sql, why", [
    ("DELETE FROM biblio", "only SELECT"),
    ("SELECT 1; DROP TABLE biblio", "one statement"),
    ("SELECT * FROM biblio -- x", "comments"),
    ("SELECT * FROM biblio /* x */", "comments"),
    ("SELECT * FROM biblio INTO OUTFILE '/tmp/x'", "INTO"),
    ("SELECT password FROM borrowers", "password"),
    ("SELECT * FROM sessions", "sessions"),
    ("SELECT * FROM mysql.user", "mysql"),
    ("SELECT SLEEP(10)", "sleep"),
    ("SELECT * FROM biblio FOR UPDATE", "UPDATE|locking"),
    ("SELECT 'unclosed", "unbalanced"),
    ("SELECT 1 UNION SELECT 1 FROM x WHERE 1 AND (UPDATE)", "UPDATE"),
])
def test_select_refused(sql, why):
    with pytest.raises(sqlguard.SQLRefused, match=f"(?i){why}"):
        sqlguard.check_select(sql)


def test_write_rules():
    w = sqlguard.check_write("UPDATE accountlines SET amountoutstanding = 0 WHERE borrowernumber = 101;")
    assert (w.verb, w.table, w.where) == ("update", "accountlines", "borrowernumber = 101")
    assert w.capped(2).endswith("LIMIT 2")
    assert w.count_sql() == "SELECT COUNT(*) AS n FROM accountlines WHERE borrowernumber = 101"
    for bad in ("DELETE FROM items", "DELETE FROM items WHERE 1=1", "UPDATE items SET x=1 WHERE TRUE",
                "DROP TABLE items", "TRUNCATE items", "UPDATE borrowers SET password='x' WHERE borrowernumber=1",
                "DELETE FROM items WHERE itemnumber IN (SELECT itemnumber FROM items)",
                "UPDATE items i JOIN biblio b ON 1 SET i.x=1 WHERE b.biblionumber=1",
                "ALTER TABLE items ADD x INT", "SELECT 1"):
        with pytest.raises(sqlguard.SQLRefused):
            sqlguard.check_write(bad)
    assert sqlguard.check_write("INSERT INTO saved_sql (report_name) VALUES ('x')").verb == "insert"


# ----------------------------------------------------------------------
# tools on the demo database
# ----------------------------------------------------------------------
@pytest.fixture
def ctx():
    return tools.Context(dbmod.DemoDB())


def test_fuzzy_catalogue_search(ctx):
    out = tools.search_catalogue(ctx, {"terms": ["It", "A coisa", "Stephen King", "Pennywise"]})
    top = [r["biblionumber"] for r in out["matches"][:2]]
    assert sorted(top) == ["1", "2"]                       # both editions of It first
    assert ctx.refs["biblio:1"].startswith("It")


def test_patron_with_exact_overdues_and_fines(ctx):
    out = tools.find_patrons(ctx, {"overdues_min": 4, "overdues_max": 4, "fines_min": 144, "fines_max": 144,
                                   "order": "recent_activity", "limit": 1})
    (p,) = out["patrons"]
    assert (p["firstname"], p["overdues"], p["fines"]) == ("Ana", "4", "144.00")
    # Diego also has 4 overdues, but 124.00 after a payment: not a match.
    assert len(tools.find_patrons(ctx, {"overdues_min": 4, "overdues_max": 4})["patrons"]) == 2


def test_quoting_keeps_strings_inert(ctx):
    out = tools.search_catalogue(ctx, {"terms": ["x' OR '1'='1", "\\'; DROP TABLE biblio; --"]})
    assert out["matches"] == []
    assert ctx.db.query("SELECT COUNT(*) AS n FROM biblio")[0]["n"] == "6"


def test_records_never_carry_passwords(ctx):
    rec = tools.get_record(ctx, {"kind": "patron", "id": "101"})
    assert "password" not in rec and rec["fines"] == "144.00" and len(rec["loans"]) == 4
    assert "error" in json.loads(tools.call(ctx, "run_select", {"sql": "SELECT password FROM borrowers"}))


def test_proposals_are_previewed_and_capped(ctx):
    res = json.loads(tools.call(ctx, "propose_change", {
        "kind": "sql", "summary": "Waive Ana's fines",
        "sql": "UPDATE accountlines SET amountoutstanding = 0 WHERE borrowernumber = 101"}))
    assert res["rows"] == 2 and "NOT executed" in res["status"]
    (p,) = ctx.proposals
    assert p.run_sql.endswith("LIMIT 2") and p.state == "pending"
    assert ctx.db.query("SELECT SUM(amountoutstanding) AS s FROM accountlines WHERE borrowernumber = 101")[0]["s"] \
        == "144.0"                                          # nothing ran
    for bad in ({"kind": "sql", "summary": "x", "sql": "DELETE FROM items WHERE itemnumber = 999"},
                {"kind": "panel_action", "summary": "x", "action": "reboot"},
                {"kind": "sql", "summary": "x", "sql": "TRUNCATE accountlines"}):
        assert "error" in json.loads(tools.call(ctx, "propose_change", bad))
    assert len(ctx.proposals) == 1


def test_proposable_actions_exist_in_the_installer():
    from kei_panel.bridge import installer_actions
    assert set(tools.proposable_entries()) <= installer_actions(INSTALLER)
    assert "reboot" not in tools.proposable_entries() and "search-repair" in tools.proposable_entries()


def test_provision_sql_grants_select_only():
    sql = dbmod.provision_sql("koha_library", ["biblio", "borrowers", "sessions", "api_keys"],
                              {"borrowers": ["borrowernumber", "surname", "password", "secret"]}, "p'w")
    assert "GRANT SELECT ON `koha_library`.`biblio`" in sql
    assert "GRANT SELECT (`borrowernumber`, `surname`) ON `koha_library`.`borrowers`" in sql
    assert "sessions" not in sql and "api_keys" not in sql and "password`" not in sql
    assert "p''w" in sql and "ALL PRIVILEGES ON" not in sql.replace("REVOKE ALL PRIVILEGES", "")


def test_mysql_xml_rows():
    xml = ('<?xml version="1.0"?><resultset statement="x" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
           '<row><field name="a">1\t2</field><field name="b" xsi:nil="true" /></row></resultset>')
    assert dbmod.parse_xml_rows(xml) == [{"a": "1\t2", "b": None}]
    assert dbmod.parse_xml_rows(xml + xml.replace(">1\t2<", ">3<")) == [{"a": "3", "b": None}]


# ----------------------------------------------------------------------
# agent, links, provider bodies
# ----------------------------------------------------------------------
def test_agent_loop_with_demo_model(ctx):
    agent = Agent(DemoModel(), ctx, lang="pt")
    turn = agent.ask("who is the last patron who has 4 overdue books and 144 reais in fines?")
    assert turn.steps == ["Looking up patrons"]
    assert "[[patron:101|Ana Souza]]" in turn.answer
    assert "Brazilian Portuguese" in agent.system and "propose_change" in agent.system


def test_agent_takes_plain_text_and_stops_looping(ctx):
    assert Agent(lambda m: "Just text.", ctx).ask("hi").answer == "Just text."
    looping = Agent(lambda m: '{"tool": "find_page", "args": {"query": "backup"}}', ctx, max_steps=2)
    turn = looping.ask("loop")
    assert len(turn.steps) == 2 and turn.answer


def test_envelope_inside_prose_and_fences():
    assert parse_envelope('Sure!\n```json\n{"answer": "a {b}"}\n```') == {"answer": "a {b}"}
    assert parse_envelope("no json") == {}


def test_only_verified_refs_become_links():
    text = "See [[biblio:1|It]] and [[biblio:99|Made up]] [x]"
    out = links.render(text, {"biblio:1": "It"})
    assert "@click=open_ref('biblio:1')" in out and "biblio:99" not in out
    assert "Made up" in out and "\\[x]" in out
    assert links.refs(text) == [("biblio:1", "It"), ("biblio:99", "Made up")]


def test_request_bodies_per_provider():
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "q"},
            {"role": "user", "content": "TOOL RESULT"}]
    a = llm.request_body({"provider": "anthropic", "model": "m"}, msgs)
    assert a["system"] == "S" and len(a["messages"]) == 1           # alternating turns
    g = llm.request_body({"provider": "gemini", "model": "m"}, msgs)
    assert g["response_format"] == {"type": "json_object"} and g["messages"][0]["role"] == "system"
    o = llm.request_body({"provider": "ollama", "model": "m"}, msgs)
    assert o["format"] == "json" and o["stream"] is False
    assert llm.endpoint({"provider": "ollama", "url": "http://localhost:11434"}) == "http://localhost:11434/api/chat"
    assert llm.reply_text("gemini", {"choices": [{"message": {"content": "{}"}}]}) == "{}"


# ----------------------------------------------------------------------
# the widget, headless
# ----------------------------------------------------------------------
async def _until(pilot, cond, wait=6.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_dashboard_assistant_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    from kei_panel.app import KohaPanelApp
    from kei_panel.screens.dialogs import ConfirmScreen
    from kei_panel.screens.loading import LoadingScreen
    from kei_panel.screens.record import RecordScreen
    from kei_panel.widgets.assistant import AssistantPanel, ChatMessage, ProposalCard, RefChip

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.3)
            panel = app.screen.query_one(AssistantPanel)
            assert not panel.query_one("#assistant-setup").display      # demo: ready
            box = panel.query_one("#assistant-input")

            box.value = "that book about the clown that was made into a movie"
            panel.send()
            await pilot.pause(0.1)
            assert isinstance(app.screen, LoadingScreen)                # Pac-Man in front
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen))
            await pilot.pause(0.1)
            answer = panel.query(ChatMessage).last()
            assert "-assistant" in answer.classes
            chips = list(answer.query(RefChip))
            assert {c.key for c in chips[:2]} == {"biblio:1", "biblio:2"}

            panel.action_first_link()
            await pilot.press("enter")
            await _until(pilot, lambda: isinstance(app.screen, RecordScreen))
            assert app.screen.kind == "biblio"
            await pilot.press("escape")
            await pilot.pause(0.1)

            box.value = "please waive Ana's fines"
            panel.send()
            await _until(pilot, lambda: len(panel.query(ProposalCard)) == 1)
            card = panel.query_one(ProposalCard)
            assert card.proposal.rows == 2 and card.proposal.state == "pending"
            assert panel.db.query("SELECT SUM(amountoutstanding) AS s FROM accountlines "
                                  "WHERE borrowernumber = 101")[0]["s"] == "144.0"
            card.query_one(".proposal-confirm").press()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.press("y")                                       # the last Yes
            await _until(pilot, lambda: card.proposal.state == "done")
            assert panel.db.query("SELECT SUM(amountoutstanding) AS s FROM accountlines "
                                  "WHERE borrowernumber = 101")[0]["s"] == "0.0"

    asyncio.run(main())


def test_cancel_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    from kei_panel.app import KohaPanelApp
    from kei_panel.widgets.assistant import AssistantPanel, ProposalCard

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=True, demo=True))
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause(0.3)
            panel = app.screen.query_one(AssistantPanel)
            panel.query_one("#assistant-input").value = "waive Ana's fines"
            panel.send()
            await _until(pilot, lambda: len(panel.query(ProposalCard)) == 1)
            card = panel.query_one(ProposalCard)
            card.query_one(".proposal-cancel").press()
            await _until(pilot, lambda: card.proposal.state == "cancelled")
            assert panel.db.query("SELECT SUM(amountoutstanding) AS s FROM accountlines "
                                  "WHERE borrowernumber = 101")[0]["s"] == "144.0"

    asyncio.run(main())
