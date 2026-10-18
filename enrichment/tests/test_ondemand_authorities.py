"""nexus_ondemand.authorities: an authority job on the on-demand service.
Headings Koha and static.db leave unmatched are asked of the direct
authority servers (a scripted fake network): a found heading becomes a
new authority citing its server, subjects come only from Brazilian
servers, the same heading in many records is asked once, and the job
waits for the network instead of finding nothing."""

from __future__ import annotations

import asyncio
import json

from nexus_enrich.marc import Field
from nexus_jobs.store import Store, unpack
from nexus_ondemand import authorities, service
from test_authority import auth_rec, local, name, write
from test_ondemand_dispatch import FakeNet, Server, tgt
from test_ondemand_service import catalog, env, item, job_of  # noqa: F401 (env: a fixture)

SARAMAGO = auth_rec("100", [("a", "Saramago, José,"), ("d", "1922-2010")], variants=["Saramago, J."], rid="br-1")
CEGUEIRA = auth_rec("150", [("a", "Cegueira")], rid="br-2")
BLINDNESS = auth_rec("150", [("a", "Ninguém")], rid="de-1")


def aut(tid, country="BR"):
    return tgt(tid, country=country, category="authorities", recordtype="authority")


def auth_job(settings, records, koha=()):
    store = Store(settings.jobs_db)
    try:
        job = store.add("all", "auth", "exact", origin="ondemand")
        d = settings.job_dir(job.id)
        d.mkdir(parents=True, exist_ok=True)
        write(d / "export.xml", records)
        write(d / "authorities.xml", list(koha))
        store.set(job.id, state="exported")
        return job.id
    finally:
        store.close()


def headings(settings, job_id, seq):
    return {h["before"].split("$a ", 1)[1]: h for h in json.loads(item(settings, job_id, seq)["detail"])["headings"]}


def test_unmatched_headings_are_found_on_the_authority_servers(env):
    settings, config = env
    net = FakeNet(br_example_org=Server([SARAMAGO, CEGUEIRA]), de_example_org=Server([BLINDNESS]))
    cat = catalog(aut("br"), aut("de", country="DE"), tgt("bib"))
    rec = local(301, [name("100", "Saramago, José"), Field("650", " ", "4", [("a", "Cegueira")]),
                      Field("650", " ", "4", [("a", "Ninguém")])])
    job_id = auth_job(settings, [rec])
    assert asyncio.run(service.serve(settings, config, catalog=cat, opener=net)) == 1
    assert job_of(settings, job_id).state == "ready"
    row = item(settings, job_id, 1)
    assert row["status"] == "enriched" and row["m1"] == 2
    got = headings(settings, job_id, 1)
    saramago = next(h for b, h in got.items() if b.startswith("Saramago"))
    assert saramago["action"] == "new" and saramago["source"] == "z3950:br"
    assert got["Cegueira"]["action"] == "new"                        # from the Brazilian server
    assert got["Ninguém"]["action"] == "none"                        # only the foreign server has it
    assert not any(h == "de.example.org" and 21 in u for h, u in net.searches)   # subjects: Brazil only
    assert not any(h == "bib.example.org" for h, _ in net.searches)  # authority servers only
    store = Store(settings.jobs_db)
    try:
        new = [unpack(r[0]) for r in store.conn.execute(
            "SELECT record FROM auth_new WHERE job_id = ? ORDER BY id", (job_id,))]
        assert store.attempts(job_id)                                # the servers asked, for the report
    finally:
        store.close()
    assert any("BR" in f.text() for r in new for f in r.get_fields("670"))      # cites the server
    assert any("Saramago, J." in f.text() for r in new for f in r.get_fields("400"))


def test_a_heading_in_many_records_is_asked_once(env):
    settings, config = env
    settings.parallel = 4
    net = FakeNet(br_example_org=Server([SARAMAGO]))
    recs = [local(400 + n, [name("100", "Saramago, José")]) for n in range(6)]
    job_id = auth_job(settings, recs)
    asyncio.run(service.serve(settings, config, catalog=catalog(aut("br")), opener=net))
    assert job_of(settings, job_id).state == "ready"
    assert all(item(settings, job_id, n)["m1"] == 1 for n in range(1, 7))
    assert len([s for s in net.searches if s[0] == "br.example.org"]) == 1
    store = Store(settings.jobs_db)
    try:
        assert store.conn.execute("SELECT COUNT(*) FROM auth_new WHERE job_id = ?", (job_id,)).fetchone()[0] == 1
    finally:
        store.close()


def test_koha_authorities_are_never_asked_of_the_servers(env):
    settings, config = env
    koha = auth_rec("100", [("a", "Saramago, José,"), ("d", "1922-2010")], rid="77")
    net = FakeNet(br_example_org=Server([SARAMAGO]))
    job_id = auth_job(settings, [local(501, [name("100", "Saramago, José")])], koha=[koha])
    asyncio.run(service.serve(settings, config, catalog=catalog(aut("br")), opener=net))
    assert item(settings, job_id, 1)["m0"] == 1 and net.searches == []


def test_the_auth_job_waits_for_the_network(env):
    settings, config = env
    settings.outage_wait = 0.05
    servers = {f"s{i}_example_org": Server([SARAMAGO], connect="dns") for i in range(5)}
    net = FakeNet(**servers)
    cat = catalog(*[aut(f"s{i}") for i in range(5)])
    job_id = auth_job(settings, [local(601, [name("100", "Saramago, José")])])
    outages = []

    async def run():
        task = asyncio.ensure_future(service.serve(settings, config, catalog=cat, opener=net))
        while not outages:
            await asyncio.sleep(0.01)
            if settings.status_file.is_file() and json.loads(settings.status_file.read_text()).get("outage"):
                outages.append(1)
        assert job_of(settings, job_id).done == 0
        for s in net.servers.values():
            s.connect = ""
        await task
    asyncio.run(run())
    assert item(settings, job_id, 1)["m1"] == 1


def test_found_headings_rules():
    rows = [authorities.StaticHeading(1, "topical", "Blindness", "blindness", "", "", (), "z3950:de", "x", "", "", 0, 0, 3),
            authorities.StaticHeading(2, "personal", "Saramago, José", "saramago jose", "1922-2010", "", ("Saramago, J.",),
                                      "z3950:br", "y", "", "", 0, 1, 1)]
    found = authorities.FoundHeadings(rows, catalog(aut("br"), aut("de", country="DE")))
    assert found.exact("topical", "blindness") == []                 # no foreign subject
    assert [r.id for r in found.exact("personal", "saramago jose")] == [2]
    assert found.sources["z3950:br"]["name"] == "BR"
