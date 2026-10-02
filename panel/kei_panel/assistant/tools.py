"""The tools the model may call, and the links they make possible.

Every tool runs fixed SQL through the read-only account (db.py) with its
arguments checked and quoted here; run_select is the only free query and
goes through sqlguard.check_select. Each row a tool returns carries a
ready-made "link" ([[kind:id|label]]) and its id is remembered in
Context.refs: the widget turns into a blue link only an id a tool really
returned, so a model that invents a biblionumber gets plain text.

propose_change runs nothing: it validates the change and records a
Proposal the widget shows with Confirm / Cancel (actions.py runs it).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import menus
from . import sqlguard
from .db import Database, DBError

MAX_RESULT_CHARS = 6000
MAX_PROPOSAL_ROWS = 1000

# Panel routines the assistant may propose: everything in the menus except
# what the panel cannot undo, and what only makes sense typed by a person.
NOT_PROPOSABLE = {"install", "restore", "reboot", "rotate-db-password", "credentials", "superlibrarian",
                  "update-system", "update-panel", "staff-firewall", "cloudflare", "ssl", "monitor",
                  "links", "mc", "search-toggle"}

# Staff interface pages: (id, name, path, keywords).
STAFF_PAGES = (
    ("staff-circulation", "Circulation", "/cgi-bin/koha/circ/circulation-home.pl", "checkout checkin loans emprestimo"),
    ("staff-patrons", "Patrons", "/cgi-bin/koha/members/members-home.pl", "patrons readers leitores usuarios"),
    ("staff-catalogue", "Advanced search", "/cgi-bin/koha/catalogue/advsearch.pl", "catalogue search books acervo"),
    ("staff-cataloguing", "Cataloguing", "/cgi-bin/koha/cataloguing/cataloging-home.pl", "marc record add catalogacao"),
    ("staff-reports", "Reports", "/cgi-bin/koha/reports/reports-home.pl", "reports sql relatorios"),
    ("staff-overdues", "Overdues", "/cgi-bin/koha/circ/overdue.pl", "overdue late atrasos"),
    ("staff-sysprefs", "System preferences", "/cgi-bin/koha/admin/preferences.pl", "preferences settings parametros"),
    ("staff-admin", "Administration", "/cgi-bin/koha/admin/admin-home.pl", "administration branches categories"),
    ("staff-acquisitions", "Acquisitions", "/cgi-bin/koha/acqui/acqui-home.pl", "acquisitions orders vendors aquisicao"),
    ("staff-tools", "Tools", "/cgi-bin/koha/tools/tools-home.pl", "tools batch notices ferramentas"),
    ("staff-about", "About Koha", "/cgi-bin/koha/about.pl", "about version sobre"),
)

STAFF_PATHS = {
    "biblio": "/cgi-bin/koha/catalogue/detail.pl?biblionumber={id}",
    "patron": "/cgi-bin/koha/members/moremember.pl?borrowernumber={id}",
    "report": "/cgi-bin/koha/reports/guided_reports.pl?reports={id}&phase=Show%20SQL",
    "syspref": "/cgi-bin/koha/admin/preferences.pl?op=search&searchfield={id}",
}

KINDS = ("biblio", "patron", "report", "syspref", "page")


class ToolError(RuntimeError):
    """A tool refused its arguments: the message goes back to the model."""


@dataclass
class Proposal:
    kind: str                 # sql | panel_action
    summary: str
    sql: str = ""             # as proposed
    run_sql: str = ""         # what Confirm runs (LIMIT = rows)
    rows: int = 0
    action: str = ""          # panel routine (--run action)
    label: str = ""           # its menu label
    state: str = "pending"    # pending | done | cancelled | failed


@dataclass
class Context:
    db: Database
    refs: dict[str, str] = field(default_factory=dict)     # "biblio:1" -> label
    proposals: list[Proposal] = field(default_factory=list)

    def ref(self, kind: str, rid: object, label: str) -> str:
        key = f"{kind}:{rid}"
        label = re.sub(r"[\[\]|]", "", label or key).strip() or key
        self.refs[key] = label
        return f"[[{key}|{label}]]"


@dataclass
class Tool:
    name: str
    description: str
    args: dict[str, str]
    fn: Callable[[Context, dict], Any]

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "args": self.args}


# ----------------------------------------------------------------------
# Quoting (the only way a model string reaches SQL in the fixed tools)
# ----------------------------------------------------------------------
def lit(s: object, max_len: int = 80) -> str:
    """A string literal valid in MariaDB and SQLite: no backslashes, '' quoted."""
    text = re.sub(r"[\\\x00-\x1f%]", "", str(s))[:max_len]
    return "'" + text.replace("'", "''") + "'"


def like(s: object) -> str:
    """'%s%' for LIKE, quoted as lit() does."""
    return "'%" + lit(s)[1:-1] + "%'"


def num(v: object, name: str) -> float:
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        raise ToolError(f"{name} must be a number") from None


def _q(ctx: Context, sql: str) -> list[dict]:
    try:
        return ctx.db.query(sql)
    except DBError as e:
        raise ToolError(f"database: {e}") from None


# ----------------------------------------------------------------------
# The tools
# ----------------------------------------------------------------------
def search_catalogue(ctx: Context, a: dict) -> dict:
    terms = a.get("terms") or a.get("query") or []
    if isinstance(terms, str):
        terms = [terms]
    terms = [str(t).strip() for t in terms if len(str(t).strip()) >= 2][:8]
    # Koha stores authors as "King, Stephen": "Stephen King" finds it too.
    terms += [f"{w[1]}, {w[0]}" for w in (t.split() for t in terms if "," not in t) if len(w) == 2]
    if not terms:
        raise ToolError("give at least one search term of 2+ characters")
    cols = {"b.title": 3, "b.author": 2, "b.subtitle": 1, "b.seriestitle": 1, "b.abstract": 1, "bi.isbn": 2}
    conds, score = [], []
    for t in terms:
        if len(t) <= 3:
            # "It": a whole word of the title, or "Smith" and "little" match too.
            hit = (f"(b.title = {lit(t)} OR b.title LIKE {lit(t + ' %')} OR b.title LIKE {lit('% ' + t)} "
                   f"OR b.title LIKE {lit('% ' + t + ' %')})")
            conds.append(hit)
            score.append(f"CASE WHEN b.title = {lit(t)} THEN 8 WHEN {hit} THEN 3 ELSE 0 END")
            continue
        conds.append("(" + " OR ".join(f"{c} LIKE {like(t)}" for c in cols) + ")")
        score.append(f"CASE WHEN b.title = {lit(t)} THEN 5 ELSE 0 END")
        score += [f"CASE WHEN {c} LIKE {like(t)} THEN {w} ELSE 0 END" for c, w in cols.items()]
    sql = ("SELECT b.biblionumber, b.title, b.subtitle, b.author, b.copyrightdate, bi.isbn, "
           f"({' + '.join(score)}) AS score FROM biblio b "
           "LEFT JOIN biblioitems bi ON bi.biblionumber = b.biblionumber "
           f"WHERE {' OR '.join(conds)} ORDER BY score DESC, b.biblionumber DESC LIMIT 10")
    rows = _q(ctx, sql)
    for r in rows:
        r["link"] = ctx.ref("biblio", r["biblionumber"], _title(r))
    return {"terms": terms, "matches": rows}


def _title(r: dict) -> str:
    t = (r.get("title") or "").strip(" /:")
    return f"{t}, {r['author']}" if r.get("author") else t


PATRON_ORDER = {"recent_activity": "p.lastseen DESC", "recent_enrolment": "p.dateenrolled DESC",
                "most_fines": "p.fines DESC", "most_overdues": "p.overdues DESC", "name": "p.surname, p.firstname"}


def find_patrons(ctx: Context, a: dict) -> dict:
    where = []
    if a.get("name"):
        for word in str(a["name"]).split()[:3]:
            where.append(f"(b.firstname LIKE {like(word)} OR b.surname LIKE {like(word)})")
    if a.get("cardnumber"):
        where.append(f"b.cardnumber = {lit(a['cardnumber'])}")
    if a.get("category"):
        where.append(f"b.categorycode = {lit(str(a['category']).upper(), 10)}")
    outer = []
    for key, col, op in (("overdues_min", "overdues", ">="), ("overdues_max", "overdues", "<="),
                         ("fines_min", "fines", ">="), ("fines_max", "fines", "<=")):
        if a.get(key) not in (None, ""):
            v = num(a[key], key)
            if col == "fines":
                v = v - 0.005 if op == ">=" else v + 0.005
                outer.append(f"p.fines {op} {v:.3f}")
            else:
                outer.append(f"p.overdues {op} {int(v)}")
    order = PATRON_ORDER.get(str(a.get("order") or "recent_activity"), PATRON_ORDER["recent_activity"])
    limit = max(1, min(20, int(num(a.get("limit") or 5, "limit"))))
    inner = ("SELECT b.borrowernumber, b.cardnumber, b.firstname, b.surname, b.categorycode, "
             "b.lastseen, b.dateenrolled, "
             "(SELECT COUNT(*) FROM issues i WHERE i.borrowernumber = b.borrowernumber "
             "AND i.date_due < NOW()) AS overdues, "
             "(SELECT COALESCE(SUM(a.amountoutstanding), 0) FROM accountlines a "
             "WHERE a.borrowernumber = b.borrowernumber) AS fines FROM borrowers b"
             + (" WHERE " + " AND ".join(where) if where else ""))
    sql = (f"SELECT * FROM ({inner}) p" + (" WHERE " + " AND ".join(outer) if outer else "")
           + f" ORDER BY {order} LIMIT {limit}")
    rows = _q(ctx, sql)
    for r in rows:
        r["fines"] = f"{float(r.get('fines') or 0):.2f}"
        r["link"] = ctx.ref("patron", r["borrowernumber"], f"{r.get('firstname') or ''} {r.get('surname') or ''}")
    return {"order": order.split()[0].removeprefix("p."), "patrons": rows}


def get_record(ctx: Context, a: dict) -> dict:
    kind, rid = str(a.get("kind", "")), str(a.get("id", "")).strip()
    if kind == "biblio" or kind == "patron" or kind == "report":
        if not rid.isdigit():
            raise ToolError("id must be a number")
    if kind == "biblio":
        rows = _q(ctx, "SELECT b.biblionumber, b.title, b.subtitle, b.author, b.seriestitle, b.copyrightdate, "
                       "b.abstract, b.notes, bi.isbn, bi.publishercode FROM biblio b LEFT JOIN biblioitems bi "
                       f"ON bi.biblionumber = b.biblionumber WHERE b.biblionumber = {rid}")
        if not rows:
            raise ToolError(f"no biblio {rid}")
        rec = rows[0]
        rec["items"] = _q(ctx, "SELECT barcode, homebranch, itemcallnumber, onloan FROM items "
                               f"WHERE biblionumber = {rid} LIMIT 20")
        rec["link"] = ctx.ref("biblio", rid, _title(rec))
        return rec
    if kind == "patron":
        rows = _q(ctx, "SELECT borrowernumber, cardnumber, firstname, surname, categorycode, branchcode, email, "
                       f"phone, dateenrolled, dateexpiry, lastseen FROM borrowers WHERE borrowernumber = {rid}")
        if not rows:
            raise ToolError(f"no patron {rid}")
        rec = rows[0]
        rec["loans"] = _q(ctx, "SELECT b.biblionumber, b.title, i.date_due, "
                               "CASE WHEN i.date_due < NOW() THEN 1 ELSE 0 END AS overdue FROM issues i "
                               "JOIN items it ON it.itemnumber = i.itemnumber "
                               "JOIN biblio b ON b.biblionumber = it.biblionumber "
                               f"WHERE i.borrowernumber = {rid} ORDER BY i.date_due LIMIT 30")
        for loan in rec["loans"]:
            loan["link"] = ctx.ref("biblio", loan["biblionumber"], loan.get("title") or "")
        fines = _q(ctx, "SELECT COALESCE(SUM(amountoutstanding), 0) AS fines FROM accountlines "
                        f"WHERE borrowernumber = {rid}")
        rec["fines"] = f"{float(fines[0]['fines'] or 0):.2f}" if fines else "0.00"
        rec["link"] = ctx.ref("patron", rid, f"{rec.get('firstname') or ''} {rec.get('surname') or ''}")
        return rec
    if kind == "report":
        rows = _q(ctx, f"SELECT id, report_name, notes, savedsql FROM saved_sql WHERE id = {rid}")
        if not rows:
            raise ToolError(f"no report {rid}")
        rows[0]["link"] = ctx.ref("report", rid, rows[0].get("report_name") or "")
        return rows[0]
    if kind == "syspref":
        rows = _q(ctx, "SELECT variable, value, explanation, type FROM systempreferences "
                       f"WHERE variable = {lit(rid)}")
        if not rows:
            raise ToolError(f"no system preference {rid}")
        rows[0]["link"] = ctx.ref("syspref", rows[0]["variable"], rows[0]["variable"])
        return rows[0]
    if kind == "page":
        page = PAGES.get(rid)
        if not page:
            raise ToolError(f"no page {rid}")
        return {"id": rid, "name": page[0], "where": page[1], "link": ctx.ref("page", rid, page[0])}
    raise ToolError(f"kind must be one of {', '.join(KINDS)}")


def search_reports(ctx: Context, a: dict) -> dict:
    q = str(a.get("query", "")).strip()
    cond = f"WHERE report_name LIKE {like(q)} OR notes LIKE {like(q)} OR savedsql LIKE {like(q)}" if q else ""
    rows = _q(ctx, f"SELECT id, report_name, notes FROM saved_sql {cond} ORDER BY id DESC LIMIT 15")
    for r in rows:
        r["link"] = ctx.ref("report", r["id"], r.get("report_name") or "")
    return {"reports": rows}


def get_syspref(ctx: Context, a: dict) -> dict:
    q = str(a.get("query", "")).strip()
    if not q:
        raise ToolError("give a preference name or a keyword")
    rows = _q(ctx, "SELECT variable, value, explanation FROM systempreferences "
                   f"WHERE variable LIKE {like(q)} OR explanation LIKE {like(q)} ORDER BY variable LIMIT 15")
    for r in rows:
        r["link"] = ctx.ref("syspref", r["variable"], r["variable"])
    return {"preferences": rows}


def _pages() -> dict[str, tuple[str, str, str]]:
    """page id -> (name, where, keywords): panel sections and staff pages."""
    from ..glyphs import split_icon
    pages = {}
    for s in menus.SECTIONS:
        words = " ".join(split_icon(e.label)[1] for e in s.entries)
        pages[s.id] = (split_icon(s.label)[1], "panel", words)
    for pid, name, path, words in STAFF_PAGES:
        pages[pid] = (name, path, words)
    return pages


PAGES = _pages()


def find_page(ctx: Context, a: dict) -> dict:
    words = [w for w in re.findall(r"\w+", str(a.get("query", "")).lower()) if len(w) > 2]
    scored = []
    for pid, (name, where, kw) in PAGES.items():
        hay = f"{pid} {name} {kw}".lower()
        hits = sum(w in hay for w in words)
        if hits:
            scored.append((hits, pid, name, where))
    scored.sort(key=lambda s: -s[0])
    return {"pages": [{"id": pid, "name": name, "where": "panel screen" if where == "panel" else f"staff {where}",
                       "link": ctx.ref("page", pid, name)} for _h, pid, name, where in scored[:6]]}


def run_select(ctx: Context, a: dict) -> dict:
    try:
        sql = sqlguard.check_select(str(a.get("sql", "")))
    except sqlguard.SQLRefused as e:
        raise ToolError(f"refused: {e}") from None
    return {"rows": _q(ctx, sql)}


def propose_change(ctx: Context, a: dict) -> dict:
    kind = str(a.get("kind", ""))
    summary = str(a.get("summary", "")).strip()[:300]
    if not summary:
        raise ToolError("summary is required: one sentence saying what the change does")
    if kind == "panel_action":
        action = str(a.get("action", ""))
        entry = proposable_entries().get(action)
        if not entry:
            raise ToolError("unknown or not proposable action; available: " + ", ".join(sorted(proposable_entries())))
        p = Proposal("panel_action", summary, action=action, label=entry.label)
    elif kind == "sql":
        try:
            w = sqlguard.check_write(str(a.get("sql", "")))
        except sqlguard.SQLRefused as e:
            raise ToolError(f"refused: {e}") from None
        rows = 1
        if w.verb != "insert":
            try:
                counted = ctx.db.query(sqlguard.check_select(w.count_sql()))
            except (sqlguard.SQLRefused, DBError) as e:
                raise ToolError(f"could not preview the change: {e}") from None
            rows = int(float(counted[0].get("n") or 0)) if counted else 0
            if rows == 0:
                raise ToolError("the WHERE clause matches no rows: nothing would change")
            if rows > MAX_PROPOSAL_ROWS:
                raise ToolError(f"it would touch {rows} rows (limit {MAX_PROPOSAL_ROWS}); narrow the WHERE "
                                "or use a Koha batch tool")
        p = Proposal("sql", summary, sql=w.sql, run_sql=w.capped(rows), rows=rows)
    else:
        raise ToolError('kind must be "panel_action" or "sql"')
    ctx.proposals.append(p)
    return {"proposal": len(ctx.proposals), "rows": p.rows, "status":
            "shown to the person with Confirm / Cancel; NOT executed. Tell them it waits for their confirmation."}


def proposable_entries() -> dict[str, menus.Entry]:
    return {e.action: e for s in menus.SECTIONS for e in s.entries if e.action not in NOT_PROPOSABLE}


TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("search_catalogue", "Find books in the catalogue. OR of all terms over title, author, subtitle, "
         "series, abstract and ISBN, best matches first.", {"terms": "list of up to 8 strings"}, search_catalogue),
    Tool("find_patrons", "Find patrons (readers) by name, card, category, number of overdue loans and "
         "outstanding fines balance.",
         {"name": "optional", "cardnumber": "optional", "category": "optional",
          "overdues_min": "optional int", "overdues_max": "optional int", "fines_min": "optional number",
          "fines_max": "optional number", "order": "|".join(PATRON_ORDER), "limit": "1-20, default 5"},
         find_patrons),
    Tool("get_record", "One record in full: a biblio (with items), a patron (with loans and fines), a saved "
         "report (with its SQL), a system preference or a page.",
         {"kind": "|".join(KINDS), "id": "biblionumber, borrowernumber, report id, preference name or page id"},
         get_record),
    Tool("search_reports", "Saved SQL reports by name, notes or SQL text.", {"query": "string"}, search_reports),
    Tool("get_syspref", "System preferences by name or keyword in their explanation.", {"query": "string"},
         get_syspref),
    Tool("find_page", "Panel screens and staff interface pages that match a topic.", {"query": "string"},
         find_page),
    Tool("run_select", "Last resort: ONE read-only SELECT on Koha's MariaDB schema, max 50 rows.",
         {"sql": "string"}, run_select),
    Tool("propose_change", "Prepare a change for the person to review and confirm. Runs nothing.",
         {"kind": "panel_action|sql", "summary": "one sentence", "action": "panel routine id (panel_action)",
          "sql": "one single-table UPDATE/INSERT/DELETE with WHERE (sql)"}, propose_change),
)}


def call(ctx: Context, name: str, args: dict) -> str:
    """Runs a tool; the JSON text the model gets back (errors included)."""
    tool = TOOLS.get(name)
    if not tool:
        out: dict = {"error": f"unknown tool {name}; tools: {', '.join(TOOLS)}"}
    else:
        try:
            out = tool.fn(ctx, args if isinstance(args, dict) else {})
        except ToolError as e:
            out = {"error": str(e)}
    text = json.dumps(out, ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + ' ... (truncated: ask for fewer rows)"'
    return text
