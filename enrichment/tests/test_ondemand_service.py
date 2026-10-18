"""nexus_ondemand.service and the on-demand side of nexus_jobs: a job of
at most 50 records (or a typed query) goes through the direct servers
(a scripted fake network), keeps what they found, merges it into the
same report as a batch job; "Search more servers" asks only new servers,
a chosen donor re-merges without the network, and the batch worker and
this service never take each other's jobs."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from conftest import bib
from nexus_enrich.marc import Field
from nexus_jobs import __main__ as cli
from nexus_jobs.store import Store, unpack
from nexus_ondemand import service
from nexus_ondemand.config import Settings as Config
from nexus_ondemand.targets import Catalog
from test_jobs import export, local
from test_ondemand_dispatch import FakeNet, Server, tgt

ISBN = "9780306406157"


def donor(subject: str, dewey: str = "869.3"):
    return bib("O cortiço", "Azevedo, Aluísio", isbn=ISBN, year=1890, publisher="Garnier",
               subjects=[Field("650", " ", "0", [("a", subject)])],
               extra=[Field("082", "0", "4", [("a", dewey)])])


def mine(bn=7):
    return local(bn, "O cortiço", "Azevedo, Aluísio", isbn=ISBN, year=1890, publisher="Garnier")


@pytest.fixture
def env(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    settings = service.Settings(state, tmp_path / "no-static.db", state / "learned.db", idle=0, poll=0.01)
    config = Config(health_db=state / "health.db", static=False)
    return settings, config


def catalog(*targets):
    return Catalog({t.id: t for t in targets}, [], "sha")


def ondemand_job(settings, records=None, query=None):
    store = Store(settings.jobs_db)
    try:
        job = store.add("query" if query else "7", origin="ondemand", query=json.dumps(query) if query else "")
        settings.job_dir(job.id).mkdir(parents=True, exist_ok=True)
        if records is not None:
            export(settings.job_dir(job.id) / "export.xml", records)
        store.set(job.id, state="exported")
        return job.id
    finally:
        store.close()


def serve(settings, config, net, cat, **kw):
    return asyncio.run(service.serve(settings, config, catalog=cat, opener=net, **kw))


def item(settings, job_id, seq=1):
    store = Store(settings.jobs_db)
    try:
        return dict(store.conn.execute("SELECT * FROM items WHERE job_id = ? AND seq = ?", (job_id, seq)).fetchone())
    finally:
        store.close()


def job_of(settings, job_id):
    store = Store(settings.jobs_db)
    try:
        return store.job(job_id)
    finally:
        store.close()


def test_a_record_is_enriched_from_a_direct_server(env):
    settings, config = env
    net = FakeNet(s_example_org=Server([donor("Brazilian fiction")]), t_example_org=Server())
    job_id = ondemand_job(settings, [mine()])
    assert serve(settings, config, net, catalog(tgt("s"), tgt("t"))) == 1
    assert job_of(settings, job_id).state == "ready"
    row = item(settings, job_id)
    assert row["status"] == "enriched" and row["biblionumber"] == 7
    after = unpack(row["after"])
    assert [f.get("a") for f in after.get_fields("650")] == ["Brazilian fiction"]
    assert any(f.get("q") == "z3950:s" for f in after.get_fields("883"))
    # what each server did, and every record kept on disk for later re-merges
    store = Store(settings.jobs_db)
    attempts = {a["target"]: a["outcome"] for a in store.attempts(job_id)}
    store.close()
    assert attempts == {"s": "found", "t": "none"}
    index = json.loads((settings.job_dir(job_id) / "candidates" / "1" / "index.json").read_text())
    assert [(e["source"], e["round"], e["brazilian"]) for e in index] == [("z3950:s", 1, True)]
    assert (settings.job_dir(job_id) / "report.json").is_file()
    assert json.loads(settings.status_file.read_text())["state"] == "idle"


def test_status_file_shows_each_server(env):
    settings, config = env
    seen = []
    net = FakeNet(s_example_org=Server([donor("X")]), t_example_org=Server(connect="refused"))
    cat = catalog(tgt("s"), tgt("t"))
    status = service.Status(settings.status_file, cat)
    original = status.write

    def spy():
        original()
        seen.append(json.loads(settings.status_file.read_text()))
    status.write = spy
    dispatcher, health = service.build(settings, config, cat, status.event, net)
    store = Store(settings.jobs_db)
    job_id = ondemand_job(settings, [mine()])
    try:
        assert asyncio.run(service.process(store, store.job(job_id), settings, dispatcher, status)) == "ready"
    finally:
        store.close()
        health.close()
    servers = [s["servers"] for s in seen if s.get("servers")][-1]
    assert servers["s"]["state"] == "1 record(s)" and servers["t"]["state"].startswith("down:")
    assert seen[-1]["state"] == "ready" and seen[-1]["done"] == 1


def test_search_more_servers_asks_only_new_ones(env):
    settings, config = env
    targets = [tgt(f"s{i:02d}") for i in range(25)]          # ranked by id: s24 is in the second round
    net = FakeNet(**{f"s{i:02d}_example_org": Server([donor("Late")] if i == 24 else []) for i in range(25)})
    cat = catalog(*targets)
    job_id = ondemand_job(settings, [mine()])
    serve(settings, config, net, cat)
    first = set(net.hosts())
    assert len(first) == 20 and item(settings, job_id)["status"] == "no-match"
    assert cli.main(["--state", str(settings.state), "more", str(job_id)]) == 0
    assert job_of(settings, job_id).rounds == 2
    net.opened.clear()
    serve(settings, config, net, cat)
    assert set(net.hosts()) and not set(net.hosts()) & first and len(net.hosts()) == 5
    assert item(settings, job_id)["status"] == "enriched"
    store = Store(settings.jobs_db)
    assert {a["round"] for a in store.attempts(job_id)} == {1, 2}
    store.close()


def test_a_chosen_donor_remerges_without_the_network(env):
    settings, config = env
    net = FakeNet(a_example_org=Server([donor("Assunto A")]), b_example_org=Server([donor("Assunto B")]))
    cat = catalog(tgt("a"), tgt("b"))
    job_id = ondemand_job(settings, [mine()])
    serve(settings, config, net, cat)
    first = unpack(item(settings, job_id)["after"]).get_fields("650")[0].get("a")
    other = "b" if first == "Assunto A" else "a"
    assert cli.main(["--state", str(settings.state), "donor", str(job_id), "7", "subjects", f"z3950:{other}"]) == 0
    net.opened.clear()
    serve(settings, config, net, cat)
    assert net.opened == []                               # no server asked again
    assert unpack(item(settings, job_id)["after"]).get_fields("650")[0].get("a") == f"Assunto {other.upper()}"
    assert job_of(settings, job_id).rounds == 1


def test_a_typed_query_keeps_its_records_to_import(env):
    settings, config = env
    net = FakeNet(s_example_org=Server([donor("X")]))
    job_id = ondemand_job(settings, query={"isbn": ISBN})
    serve(settings, config, net, catalog(tgt("s")))
    row = item(settings, job_id)
    assert row["status"] == "found" and row["biblionumber"] is None and row["after"] is None
    found = json.loads(row["detail"])["found"]
    assert found[0]["source"] == "z3950:s" and found[0]["isbn"] == ISBN


def test_any_number_of_records_runs_and_a_missing_export_fails(env):
    settings, config = env
    net = FakeNet(s_example_org=Server([donor("Muitos")]))
    many = ondemand_job(settings, [mine(n) for n in range(1, 121)])      # no cap: the whole catalogue may come
    missing = ondemand_job(settings)
    serve(settings, config, net, catalog(tgt("s")))
    job = job_of(settings, many)
    assert job.state == "ready" and job.total == job.done == 120
    assert item(settings, many, 120)["status"] == "enriched" and item(settings, many, 120)["biblionumber"] == 120
    assert job_of(settings, missing).state == "failed" and "export.xml" in job_of(settings, missing).error


def test_a_job_stopped_half_way_goes_on_from_its_last_record(env):
    settings, config = env
    net = FakeNet(s_example_org=Server([donor("Retomado")]))
    job_id = ondemand_job(settings, [mine(n) for n in range(1, 11)])
    store = Store(settings.jobs_db)
    store.set(job_id, state="matching", total=10, done=6)              # the machine shut down after record 6
    store.close()
    serve(settings, config, net, catalog(tgt("s")))
    assert job_of(settings, job_id).state == "ready"
    store = Store(settings.jobs_db)
    asked = sorted({a["seq"] for a in store.attempts(job_id)})
    store.close()
    assert asked == [7, 8, 9, 10]


def test_the_pause_file_holds_the_job_between_records(env):
    settings, config = env
    settings.pause_poll = 0.01
    net = FakeNet(s_example_org=Server([donor("X")]))
    job_id = ondemand_job(settings, [mine(1), mine(2)])
    (settings.state / "pause").write_text("")

    async def run():
        task = asyncio.ensure_future(service.serve(settings, config, catalog=catalog(tgt("s")), opener=net))
        await asyncio.sleep(0.3)
        held = job_of(settings, job_id).done
        (settings.state / "pause").unlink()
        await task
        return held
    assert asyncio.run(run()) == 0 and job_of(settings, job_id).state == "ready"


def test_the_worker_and_the_service_never_take_each_others_jobs(env):
    settings, _ = env
    store = Store(settings.jobs_db)
    try:
        batch = store.add("all")
        od = store.add("7", origin="ondemand")
        for j in (batch, od):
            store.set(j.id, state="exported")
        assert store.next_job().id == batch.id and store.next_job("ondemand").id == od.id
        assert store.job(od.id).origin == "ondemand" and store.job(batch.id).origin == "batch"
    finally:
        store.close()


def test_idle_exit_with_no_job(env):
    settings, config = env
    assert serve(settings, config, FakeNet(), catalog(tgt("s"))) == 0


def test_jobs_cli_on_demand(env, capsys):
    settings, _ = env
    base = ["--state", str(settings.state)]
    assert cli.main(base + ["add", "--origin", "ondemand", "--scope", "101, 102"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert Path(out["ids"]).read_text().split() == ["101", "102"]
    assert cli.main(base + ["origin", str(out["job"])]) == 0 and capsys.readouterr().out.strip() == "ondemand"
    assert cli.main(base + ["add", "--origin", "ondemand", "--scope", "all"]) == 0
    assert json.loads(capsys.readouterr().out)["ids"] == ""                    # all: the whole catalogue
    assert cli.main(base + ["add", "--origin", "ondemand", "--scope", "1-5000"]) == 0
    capsys.readouterr()
    assert cli.main(base + ["add", "--origin", "ondemand", "--scope", "abc"]) == 1
    assert cli.main(base + ["add", "--origin", "ondemand", "--author", "x"]) == 1
    assert cli.main(base + ["add", "--origin", "ondemand", "--isbn", " 978 ", "--title", ""]) == 0
    q = json.loads(capsys.readouterr().out)
    assert q["scope"] == "query" and q["ids"] == ""
    store = Store(settings.jobs_db)
    assert json.loads(store.job(q["job"]).query) == {"isbn": "978"}
    store.close()
    # more / donor only on a ready on-demand report
    assert cli.main(base + ["more", str(out["job"])]) == 1
    assert cli.main(base + ["add", "--scope", "1"]) == 0
    batch = json.loads(capsys.readouterr().out)["job"]
    assert cli.main(base + ["donor", str(batch), "1", "subjects", "z3950:x"]) == 1


def test_a_typed_querys_record_as_a_new_record(env, tmp_path, capsys):
    settings, config = env
    rec = donor("X")
    rec.add_field(Field("952", " ", " ", [("a", "LOCAL")]))
    rec.add_field(Field("999", " ", " ", [("c", "55")]))
    net = FakeNet(s_example_org=Server([rec]))
    job_id = ondemand_job(settings, query={"isbn": ISBN})
    serve(settings, config, net, catalog(tgt("s")))
    out = tmp_path / "new.xml"
    store = Store(settings.jobs_db)
    try:
        info = service.import_file(settings, store, job_id, 1, 1, out)
        with pytest.raises(service.JobError):
            service.import_file(settings, store, job_id, 1, 2, out)
        batch = store.add("1", origin="ondemand")
        with pytest.raises(service.JobError):
            service.import_file(settings, store, batch.id, 1, 1, out)
    finally:
        store.close()
    assert info["source"] == "z3950:s" and info["title"].startswith("O cortiço")
    from nexus_enrich import marc
    with open(out, "rb") as fh:
        (new,) = list(marc.iter_xml(fh))
    assert not [f for f in new.fields if f.tag.startswith("9")]       # the donor's local fields stay out
    prov = new.first("883")
    assert prov.get("a") == "koha.nexus on-demand" and prov.get("q") == "z3950:s"
    assert [f.get("a") for f in new.get_fields("650")] == ["X"]
    # show: an imported record is marked with its biblionumber
    (settings.job_dir(job_id) / "imported-1-1").write_text("42\n")
    assert cli.main(["--state", str(settings.state), "show", str(job_id)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["found"][0]["found"][0]["imported"] == 42 and shown["donors"] == {}


def test_show_lists_each_records_donors_and_choices(env, capsys):
    settings, config = env
    net = FakeNet(a_example_org=Server([donor("A")]), b_example_org=Server([donor("B")]))
    job_id = ondemand_job(settings, [mine()])
    serve(settings, config, net, catalog(tgt("a"), tgt("b")))
    assert cli.main(["--state", str(settings.state), "donor", str(job_id), "7", "subjects", "z3950:b"]) == 0
    capsys.readouterr()
    assert cli.main(["--state", str(settings.state), "show", str(job_id)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert {c["source"] for c in shown["donors"]["7"]} == {"z3950:a", "z3950:b"}
    assert shown["choices"] == {"7": {"subjects": "z3950:b"}}
    assert shown["found"] == []


# ----------------------------------------------------------------------
# Big jobs: records at once, saved in order, the network going away
# ----------------------------------------------------------------------

def test_records_are_searched_at_once_and_saved_in_order(env):
    settings, config = env
    settings.parallel = 4
    # Twelve servers, each slow: several records are in flight, each on idle servers.
    net = FakeNet(**{f"s{i:02d}_example_org": Server([donor("Junto")], delay=0.05) for i in range(12)})
    cat = catalog(*[tgt(f"s{i:02d}") for i in range(12)])
    job_id = ondemand_job(settings, [mine(n) for n in range(1, 9)])
    status = service.Status(settings.status_file, cat, every=0)
    widest, done_seen = [], []
    original = status.saved

    def saved(done, n=1):
        done_seen.append(done)
        original(done, n)
    status.saved = saved
    orig_record = status.record

    def record(seq, rec, label):
        orig_record(seq, rec, label)
        widest.append(len(status.flight))
    status.record = record
    dispatcher, health = service.build(settings, config, cat, status.event, net)
    store = Store(settings.jobs_db)
    try:
        assert asyncio.run(service.process(store, store.job(job_id), settings, dispatcher, status)) == "ready"
        rows = store.conn.execute("SELECT seq, biblionumber, status FROM items WHERE job_id = ? ORDER BY rowid",
                                  (job_id,)).fetchall()
    finally:
        store.close()
        health.close()
    assert max(widest) == 4                                          # four records in flight at once
    assert [tuple(r) for r in rows] == [(n, n, "enriched") for n in range(1, 9)]   # saved in the job's order
    assert done_seen == sorted(done_seen) and done_seen[-1] == 8
    assert json.loads(settings.status_file.read_text())["per_hour"] > 0


def test_the_job_waits_for_the_network_instead_of_finding_nothing(env):
    settings, config = env
    settings.parallel = 2
    settings.outage_wait = 0.05
    servers = {f"s{i}_example_org": Server([donor("Volta")] if i == 0 else [], connect="dns") for i in range(6)}
    net = FakeNet(**servers)
    cat = catalog(*[tgt(f"s{i}") for i in range(6)])
    job_id = ondemand_job(settings, [mine(1), mine(2)])
    outages = []

    async def run():
        task = asyncio.ensure_future(service.serve(settings, config, catalog=cat, opener=net))
        while not outages:
            await asyncio.sleep(0.01)
            if settings.status_file.is_file():
                data = json.loads(settings.status_file.read_text())
                if data.get("outage"):
                    outages.append(data["outage"])
        assert job_of(settings, job_id).done == 0                    # nothing saved as "not found"
        for s in net.servers.values():
            s.connect = ""                                           # the internet is back
        await task
    asyncio.run(run())
    assert job_of(settings, job_id).state == "ready"
    assert item(settings, job_id, 1)["status"] == "enriched" and item(settings, job_id, 2)["status"] == "enriched"
    store = Store(settings.jobs_db)
    try:
        kept = {a["outcome"] for a in store.attempts(job_id)}
    finally:
        store.close()
    assert "error" not in kept                                       # the failed tries were not kept


def test_parallel_setting_from_the_environment():
    assert service.parallel_from(None) == service.PARALLEL and service.parallel_from("x") == service.PARALLEL
    assert service.parallel_from("1") == 1 and service.parallel_from(" 6 ") == 6
    assert service.parallel_from("0") == 1 and service.parallel_from("99") == service.PARALLEL_MAX
    assert service.Settings.from_env({"KEI_ONDEMAND_PARALLEL": "2"}).parallel == 2


def test_a_round_with_no_server_left_finishes(env):
    settings, config = env
    net = FakeNet(s_example_org=Server([]))
    job_id = ondemand_job(settings, [mine()])
    serve(settings, config, net, catalog(tgt("s")))
    store = Store(settings.jobs_db)
    store.set(job_id, state="exported", rounds=2)                    # Search more servers: none left
    store.close()
    assert serve(settings, config, net, catalog(tgt("s"))) == 1
    assert job_of(settings, job_id).state == "ready"
