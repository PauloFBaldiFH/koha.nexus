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


def test_too_many_records_or_no_export_fail_the_job(env):
    settings, config = env
    many = ondemand_job(settings, [mine(n) for n in range(1, 52)])
    missing = ondemand_job(settings)
    serve(settings, config, FakeNet(), catalog(tgt("s")))
    assert job_of(settings, many).state == "failed" and "more than 50" in job_of(settings, many).error
    assert job_of(settings, missing).state == "failed" and "export.xml" in job_of(settings, missing).error


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
    assert cli.main(base + ["add", "--origin", "ondemand", "--scope", "all"]) == 1
    assert cli.main(base + ["add", "--origin", "ondemand", "--scope", "1-51"]) == 1
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
