"""Authority jobs: headings matched against Koha's own authorities, then
static.db (BN first, then the Brazilian sources, then LoC), the staged
report, and the Apply/Revert bookkeeping of the new authorities."""

import json

import pytest
from conftest import bib

from enrich_build.build import Builder, SourceConfig
from nexus_enrich import authority, marc
from nexus_enrich.authority import KohaIndex, StaticHeadings, match_field
from nexus_enrich.marc import Field, Record
from nexus_enrich.static import StaticDB
from nexus_jobs import __main__ as cli
from nexus_jobs import apply
from nexus_jobs.store import Store, unpack
from nexus_jobs.worker import Settings, process


def auth_rec(tag, subs, variants=(), rid="", lccn=""):
    rec = Record(leader="00000nz  a2200000n  4500")
    if rid:
        rec.fields.append(Field("001", data=rid))
    if lccn:
        rec.fields.append(Field("010", " ", " ", [("a", lccn)]))
    rec.fields.append(Field(tag, "1", " ", subs))
    for v in variants:
        rec.fields.append(Field("4" + tag[1:], "1", " ", [("a", v)]))
    return rec


def name(tag, a, d=None, ind1="1", more=()):
    subs = [("a", a + ("," if d else ""))] + ([("d", d)] if d else []) + list(more)
    return Field(tag, ind1, " ", subs)


def write(path, records):
    path.write_text('<collection xmlns="http://www.loc.gov/MARC21/slim">' + "".join(marc.to_xml(r) for r in records)
                    + "</collection>", encoding="utf-8")


@pytest.fixture(scope="module")
def static_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("authstatic")
    write(d / "bn.xml", [
        bib("Ensaio sobre a cegueira", None, rid="BN1", extra=[name("100", "Saramago, José", "1922-2010")]),
        bib("Perto do coração selvagem", None, rid="BN2", extra=[name("100", "Silva, José", "1950-")]),
    ])
    write(d / "ufpr.xml", [
        bib("Livro", None, rid="U1", subjects=["Cegueira"], extra=[name("100", "Silva, José", "1900-1980"),
                                                              Field("710", "2", " ", [("a", "Universidade Federal do Paraná")])]),
    ])
    write(d / "loc.xml", [
        auth_rec("100", [("a", "Saramago, José,"), ("d", "1922-2010")], ["Saramago, José de Sousa"], "oca1", "n 79063737"),
        auth_rec("100", [("a", "Assis, Machado de,"), ("d", "1839-1908")], ["Machado de Assis"], "oca2", "n 80000001"),
        auth_rec("150", [("a", "Blindness")], (), "sh1"),
    ])
    sources = [SourceConfig.from_dict({"id": "bn", "name": "Biblioteca Nacional", "paths": ["bn.xml"],
                                       "brazilian": True}),
               SourceConfig.from_dict({"id": "ufpr", "name": "UFPR", "paths": ["ufpr.xml"], "brazilian": True}),
               SourceConfig.from_dict({"id": "loc", "name": "Library of Congress", "paths": ["loc.xml"]})]
    out = d / "static.db"
    assert Builder(out, sources, d).build().error_count == 0
    return out


KOHA = [
    auth_rec("100", [("a", "Ramos, Graciliano,"), ("d", "1892-1953")], ["Ramos, G."], "7"),
    auth_rec("100", [("a", "Souza, Maria,"), ("d", "1900-1950")], (), "8"),
    auth_rec("100", [("a", "Souza, Maria,"), ("d", "1960-")], (), "9"),
]


@pytest.fixture(scope="module")
def heads(static_db):
    db = StaticDB(static_db)
    yield KohaIndex(KOHA), StaticHeadings(db.conn)
    db.close()


def test_rules(heads):
    koha, static = heads
    # Koha first: dates added from Koha's form; a variant leads to the authorised form.
    m = match_field(name("100", "Ramos, Graciliano"), koha, static)
    assert m.action == "koha" and m.authid == 7 and m.standardized
    assert m.form == [("a", "Ramos, Graciliano,"), ("d", "1892-1953")]
    m = match_field(name("700", "Ramos, G."), koha, static)
    assert m.action == "koha" and m.authid == 7
    assert match_field(name("100", "Souza, Maria"), koha, static).action == "review"     # two in Koha
    # static.db: BN before LoC, the record's own form with the dates.
    m = match_field(name("100", "Saramago, José"), koha, static)
    assert m.action == "new" and m.static.source == "bn" and m.form == [("a", "Saramago, José,"), ("d", "1922-2010")]
    m = match_field(name("700", "Machado de Assis"), koha, static)
    assert m.action == "new" and m.static.source == "loc" and m.form == [("a", "Assis, Machado de,"),
                                                                           ("d", "1839-1908")]
    assert match_field(name("100", "Silva, José"), koha, static).action == "review"       # 1900-1980 / 1950-
    assert match_field(name("100", "Silva, José", "1950-"), koha, static).static.source == "bn"
    # Subjects: Brazilian forms yes, LCSH never.
    assert match_field(Field("650", " ", "4", [("a", "Cegueira")]), koha, static).action == "new"
    assert match_field(Field("650", " ", "0", [("a", "Blindness")]), koha, static).action == "none"
    assert match_field(Field("650", " ", "4", [("a", "Cegueira"), ("x", "Ficção")]), koha, static).action == "skipped"
    assert match_field(name("700", "Saramago, José", more=[("t", "Ensaio")]), koha, static).action == "skipped"
    assert match_field(name("700", "Saramago, José", more=[("9", "12")]), koha, static).action == "linked"
    # A typo: proposed in exact mode, applied (preliminary) in fuzzy mode.
    assert match_field(name("100", "Saramagu, José"), koha, static).action == "review"
    m = match_field(name("100", "Saramagu, José"), koha, static, "fuzzy")
    assert m.action == "new" and m.fuzzy >= authority.FUZZY_MIN and m.form[0] == ("a", "Saramago, José,")
    assert match_field(name("100", "Ninguém, Fulano"), koha, static).action == "none"


def test_new_authority_record(heads):
    koha, static = heads
    m = match_field(name("700", "Machado de Assis"), koha, static)
    rec = authority.authority_record("personal", m.form, m.static, preliminary=False, release="nexus-enrich-2026.10")
    assert rec.is_authority and rec.first("100").subfields == [("a", "Assis, Machado de,"), ("d", "1839-1908")]
    assert rec.first("400").get("a") == "Machado de Assis" and rec.first("010").get("a") == "n80000001"
    assert rec.control("008")[33] == "c" and rec.first("667") is None
    pre = authority.authority_record("topical", [("a", "Cegueira")], None, preliminary=True)
    assert pre.control("008")[33] == "d" and pre.first("150").get("a") == "Cegueira" and pre.first("667")
    f = authority.rewrite(name("700", "Machado de Assis", more=[("e", "autor")]), m, "nexus-new:3")
    assert f.subfields == [("a", "Assis, Machado de,"), ("d", "1839-1908,"), ("e", "autor"), ("9", "nexus-new:3")]


def local(bn, fields, f005="20260101120000.0"):
    rec = bib(f"Livro {bn}", None)
    rec.fields.insert(0, Field("005", data=f005))
    for f in fields:
        rec.add_field(f)
    rec.add_field(Field("999", " ", " ", [("c", str(bn)), ("d", str(bn))]))
    return rec


RECORDS = [
    local(201, [name("100", "Saramago, José"), Field("650", " ", "4", [("a", "Cegueira")]),
                name("700", "Machado de Assis")]),
    local(202, [name("100", "Ramos, Graciliano"), name("700", "Ramos, G.")]),
    local(203, [name("100", "Silva, José"), name("700", "Lispector, Clarice", more=[("9", "44")])]),
    local(204, [name("100", "Saramagu, José")]),
    local(205, [name("100", "Ninguém, Fulano")]),
]


def run_job(static_db, tmp_path, mode):
    settings = Settings(tmp_path / "state", static_db, batch=2, pause=0)
    settings.state.mkdir()
    store = Store(settings.jobs_db)
    job = store.add("all", "auth", mode)
    d = settings.job_dir(job.id)
    d.mkdir(parents=True)
    write(d / "export.xml", RECORDS)
    write(d / "authorities.xml", KOHA)
    store.set(job.id, state="exported")
    assert process(store, store.job(job.id), settings, sleep=lambda s: None) == "ready"
    return settings, store, job


def test_job_report_apply_and_revert(static_db, tmp_path, capsys):
    settings, store, job = run_job(static_db, tmp_path, "exact")
    items = {r["biblionumber"]: r for r in store.items(job.id)}
    assert items[201]["status"] == "enriched" and items[201]["m1"] == 3 and items[201]["w"] == 2
    assert items[202]["status"] == "enriched" and items[202]["m0"] == 2
    assert items[203]["status"] == "review" and items[204]["status"] == "review"
    assert items[205]["status"] == "unchanged"
    new = store.new_authorities(job.id)
    assert [(a["kind"], a["heading"], a["source"]) for a in new] == [
        ("personal", "Saramago, José, 1922-2010", "bn"), ("topical", "Cegueira", "ufpr"),
        ("personal", "Assis, Machado de, 1839-1908", "loc")]
    assert [a["preliminary"] for a in new] == [1, 1, 0]
    after = unpack(items[201]["after"])
    assert after.first("100").subfields == [("a", "Saramago, José,"), ("d", "1922-2010"), ("9", "nexus-new:1")]
    assert unpack(items[202]["after"]).first("100").get("9") == "7"

    rep = json.loads((settings.job_dir(job.id) / "report.json").read_text())
    assert rep["kind"] == "auth" and rep["changed"] == 2 and rep["new_authorities"] == 3
    assert rep["headings"]["koha"] == 2 and rep["headings"]["new"] == 3 and rep["headings"]["review"] == 2
    assert rep["headings"]["linked_before"] == 1 and rep["headings"]["standardized"] == 4
    html = (settings.job_dir(job.id) / "report.html").read_text()
    assert "Saramago, José, 1922-2010" in html and "preliminary" in html
    assert "- 100 1_ $a Saramago, José" in html.replace("&#x27;", "'")
    assert [c["kind"] for c in store.chunks(job.id)] == ["auth", "bib"]

    # Apply: Koha gained Saramago since the report; the other two are created.
    koha_now = KohaIndex(KOHA + [auth_rec("100", [("a", "Saramago, José,"), ("d", "1922-2010")], (), "50")])
    assert apply.resolve_new(store, job.id, koha_now) == 1
    assert apply.pending_chunks(store, job.id, "auth") == [1]
    out = tmp_path / "auth.xml"
    assert apply.auth_file(store, job.id, 1, out) == 2
    staged = marc.parse_xml(out.read_text())
    assert [r.first("100", "150").get("a") for r in staged] == ["Cegueira", "Assis, Machado de,"]
    res = apply.auth_committed(store, job.id, 1, 900, "1\t61\timported\n2\t62\timported\n")
    assert res == {"created": 2, "failed": 0, "existing": 1}
    current = {201: "20260101120000.0", 202: "20260101120000.0"}
    bibfile = tmp_path / "bib.xml"
    assert apply.chunk_file(store, job.id, 2, current, bibfile) == [201, 202]
    rec = marc.parse_xml(bibfile.read_text())[0]
    assert [f.get("9") for f in rec.get_fields("100", "650", "700")] == ["50", "61", "62"]
    apply.check_matches(store, job.id, 2, 901, "1\t1\t201\tauto_match\n2\t2\t202\tauto_match\n")
    apply.committed(store, job.id, 2, {201: "x1", 202: "x2"})
    assert store.job(job.id).state == "applied"

    # Revert: the records first, then the authorities (one still in use is kept).
    assert apply.auth_revert_plan(store, job.id) == []
    plan = apply.revert_plan(store, job.id, {201: "x1", 202: "x2"})
    assert plan == [(2, 901, [])]
    apply.reverted(store, job.id, 2, [])
    assert store.job(job.id).state == "partly-applied"
    assert apply.auth_revert_plan(store, job.id) == [(1, 900, [61, 62])]
    apply.auth_reverted(store, job.id, 1, [62])
    assert store.job(job.id).state == "reverted"
    assert [a["state"] for a in store.new_authorities(job.id)] == ["exists", "reverted", "kept"]

    assert cli.main(["--state", str(settings.state), "show", str(job.id)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["kind"] == "auth" and shown["mode"] == "exact" and len(shown["new_authorities"]) == 3
    assert shown["changes"][0]["added"] == 3
    store.close()


def test_fuzzy_mode_links_the_typo(static_db, tmp_path):
    settings, store, job = run_job(static_db, tmp_path, "fuzzy")
    item = store.item(job.id, 204)
    assert item["status"] == "enriched"
    # The typo links to the same new authority as the right form (one per heading).
    assert unpack(item["after"]).first("100").get("9") == "nexus-new:1"
    assert len(store.new_authorities(job.id)) == 3
    store.close()


def test_cli_add_kind(tmp_path, capsys):
    base = ["--state", str(tmp_path)]
    assert cli.main(base + ["add", "--scope", "1-3", "--kind", "auth", "--mode", "fuzzy"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert cli.main(base + ["kind", str(out["job"])]) == 0
    assert capsys.readouterr().out.strip() == "auth"
