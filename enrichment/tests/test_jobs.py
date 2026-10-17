"""nexus_jobs: scopes, the worker (batches, checkpoint and resume, pause,
cancel), the staged report and the Apply/Revert bookkeeping."""

import json
from pathlib import Path

import pytest
from conftest import bib

from enrich_build.build import Builder, SourceConfig
from nexus_enrich import marc
from nexus_enrich.marc import Field
from nexus_jobs import __main__ as cli
from nexus_jobs import apply, report, scope
from nexus_jobs.store import Store
from nexus_jobs.worker import Settings, process, run

ISBN = "9788535902778"


@pytest.fixture(scope="module")
def static_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("static")
    rich = bib("Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, rid="U1",
               subjects=["Cegueira", "Romance português"], extra=[Field("082", "0", "4", [("a", "869.3")])])
    rows = [{"fonte": "Universidade Federal do Paraná (UFPR)", "marcxml": marc.to_xml(rich)},
            {"fonte": "Universidade de Brasília (UnB)",
             "marcxml": marc.to_xml(bib("Vidas secas", "Ramos, Graciliano", year=1938, rid="B2",
                                        subjects=["Seca"]))}]
    (d / "dump.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    src = SourceConfig.from_dict({"id": "zeus", "paths": ["dump.jsonl"], "mode": "full", "brazilian": True,
                                  "source_field": "fonte"})
    out = d / "static.db"
    assert Builder(out, [src], d).build().error_count == 0
    return out


def local(bn, title, author=None, isbn=None, year=None, f005="20260101120000.0", **kw):
    rec = bib(title, author, isbn=isbn, year=year, **kw)
    rec.fields.insert(0, Field("005", data=f005))
    rec.add_field(Field("942", " ", " ", [("c", "BK")]))
    rec.add_field(Field("999", " ", " ", [("c", str(bn)), ("d", str(bn))]))
    return rec


def export(path: Path, records) -> None:
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<collection xmlns="http://www.loc.gov/MARC21/slim">'
                    + "".join(marc.to_xml(r) for r in records) + "</collection>", encoding="utf-8")


RECORDS = [
    local(101, "Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995),
    local(102, "Um livro que ninguém tem", "Ninguém, Fulano", year=2010),
    local(103, "Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, f005="20260202120000.0",
          subjects=["Cegueira"]),
    local(104, "Vidas secas", "Ramos, Graciliano", isbn="9788501061201", year=1998, ed="80. ed."),
    local(105, "Ensaio sobre a cegueira", "Saramago, José", isbn=ISBN, year=1995, f005="20260303120000.0"),
]


@pytest.fixture
def setup(static_db, tmp_path):
    settings = Settings(tmp_path / "state", static_db, batch=2, pause=0)
    settings.state.mkdir()
    store = Store(settings.jobs_db)
    job = store.add("all")
    settings.job_dir(job.id).mkdir(parents=True)
    export(settings.job_dir(job.id) / "export.xml", RECORDS)
    store.set(job.id, state="exported")
    yield settings, store, job
    store.close()


def test_scope():
    assert scope.parse("all") is None and scope.parse("") is None
    assert scope.parse("101, 102 500-550;103") == [(101, 103), (500, 550)]
    assert scope.text(scope.parse("5-7,1")) == "1, 5-7"
    assert list(scope.ids([(1, 3)])) == [1, 2, 3]
    for bad in ("abc", "5-3", "0"):
        with pytest.raises(scope.ScopeError):
            scope.parse(bad)
    with pytest.raises(scope.ScopeError):
        scope.parse(f"1-{scope.MAX_IDS + 1}")


def test_worker_matches_reports_and_chunks(setup):
    settings, store, job = setup
    settings.chunk = 1
    assert process(store, job, settings, sleep=lambda s: None) == "ready"
    job = store.job(job.id)
    assert (job.state, job.total, job.done) == ("ready", 5, 5)
    by_bn = {r["biblionumber"]: r for r in store.items(job.id)}
    assert by_bn[101]["status"] == "enriched" and by_bn[101]["m0"] > 0
    assert by_bn[102]["status"] == "no-match"
    added = [a["tag"] for a in json.loads(by_bn[101]["detail"])["additions"]]
    assert "650" in added and "082" in added
    # 103 already has subjects: only the Dewey number is added.
    assert [a["tag"] for a in json.loads(by_bn[103]["detail"])["additions"]] == ["082"]
    # One Koha batch per enriched record with chunk size 1.
    enriched = [bn for bn, r in by_bn.items() if r["status"] == "enriched"]
    assert len(store.chunks(job.id)) == len(enriched)
    d = settings.job_dir(job.id)
    summary = json.loads((d / "report.json").read_text(encoding="utf-8"))
    assert summary["records"] == 5 and summary["enriched"] == len(enriched) and summary["no_match"] >= 1
    assert summary["records_with"]["M0"] >= 3 and summary["fields_by_class"]["M0"] >= 3
    page = (d / "report.html").read_text(encoding="utf-8")
    assert 'class="add">+ 650 _4 $8 ' in page and "Ensaio sobre a cegueira" in page
    assert "101\tenriched" in (d / "report.tsv").read_text(encoding="utf-8")
    diff = report.text_diff(store, job.id, 101)
    assert "+ 082 04 $8 " in diff and "  245 10 $a Ensaio sobre a cegueira" in diff
    assert not [line for line in diff.splitlines() if line.startswith("- ")]
    status = json.loads(settings.status_file.read_text(encoding="utf-8"))
    assert status["state"] == "ready" and status["done"] == 5


def test_worker_resumes_from_its_checkpoint(setup):
    settings, store, job = setup

    class Stop(Exception):
        pass

    def stop(_):
        raise Stop
    with pytest.raises(Stop):
        process(store, job, settings, sleep=stop)          # stopped after the first batch of 2
    assert store.job(job.id).done == 2 and store.job(job.id).state == "matching"
    assert run(settings, sleep=lambda s: None) == 1
    job = store.job(job.id)
    assert job.state == "ready" and job.done == 5
    assert store.conn.execute("SELECT COUNT(*) FROM items WHERE job_id = ?", (job.id,)).fetchone()[0] == 5
    assert json.loads(settings.status_file.read_text(encoding="utf-8"))["state"] == "idle"


def test_pause_file_and_cancel(setup):
    settings, store, job = setup
    settings.pause_file.touch()
    calls = []

    def sleeper(seconds):
        calls.append(seconds)
        status = json.loads(settings.status_file.read_text(encoding="utf-8"))
        if seconds == 10:
            assert status["paused"] and status["why"] == "pause file"
            settings.pause_file.unlink()
        elif len(calls) > 1:
            store.set(job.id, state="cancelled")
    assert process(store, job, settings, sleep=sleeper) == "cancelled"
    assert calls[0] == 10
    assert store.job(job.id).done == 4


def test_missing_static_db_fails_the_job(setup, tmp_path):
    settings, store, job = setup
    settings.static_db = tmp_path / "none.db"
    run(settings)
    assert store.job(job.id).state == "failed" and "static.db" in store.job(job.id).error


def test_apply_and_revert_bookkeeping(setup, tmp_path):
    settings, store, job = setup
    process(store, job, settings, sleep=lambda s: None)
    assert apply.pending_chunks(store, job.id) == [1]
    ids = apply.chunk_ids(store, job.id, 1)
    enriched = sorted(ids)
    assert 101 in enriched and 105 in enriched
    # 105 was edited in Koha after the report: left out of the batch.
    current = {bn: RECORDS[bn - 101].control("005") for bn in ids}
    current[105] = "20261017090000.0"
    out = tmp_path / "chunk.xml"
    manifest = apply.chunk_file(store, job.id, 1, current, out)
    assert 105 not in manifest and manifest == [bn for bn in ids if bn != 105]
    assert store.job(job.id).state == "applying"
    text = out.read_text(encoding="utf-8")
    assert "<marc:" not in text and '<collection xmlns="http://www.loc.gov/MARC21/slim">' in text
    staged = marc.parse_xml(text)
    assert [int(r.first("999").get("c")) for r in staged] == manifest
    assert all(r.first("942") is not None for r in staged)
    assert any(f.tag == "883" for f in staged[0].fields)
    # Koha matched the second record to another biblionumber: not committed.
    rows = "\n".join(f"{i}\t{1000 + i}\t{bn if i != 2 else 999}\tauto_match" for i, bn in enumerate(manifest, 1))
    (tmp_path / "staged.tsv").write_text(rows, encoding="utf-8")
    bad = apply.check_matches(store, job.id, 1, 77, rows)
    assert bad == [1002]
    after = {bn: "20261017100000.0" for bn in manifest}
    res = apply.committed(store, job.id, 1, after)
    assert res == {"applied": len(manifest) - 1, "skipped_changed": 1, "skipped_deleted": 0, "skipped_match": 1}
    assert store.job(job.id).state == "applied"
    assert sorted(apply.applied_ids(store, job.id)) == sorted(bn for i, bn in enumerate(manifest, 1) if i != 2)
    # A librarian edited one applied record afterwards: Revert keeps it.
    edited = apply.applied_ids(store, job.id)[0]
    now = dict(after)
    now[edited] = "20261018080000.0"
    assert apply.revert_plan(store, job.id, now) == [(1, 77, [edited])]
    assert store.job(job.id).state == "reverting"
    assert apply.revert_plan(store, job.id, now, everything=True) == [(1, 77, [])]
    apply.reverted(store, job.id, 1, [edited])
    assert store.job(job.id).state == "reverted"
    states = {r["biblionumber"]: r["state"] for r in store.applied(job.id, 1)}
    assert states[edited] == "kept" and states[105] == "skipped-changed"


def test_cli(static_db, tmp_path, capsys, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("NEXUS_GATEWAY_STATIC_DB", str(static_db))
    base = ["--state", str(state)]
    assert cli.main(base + ["add", "--scope", "103, 101-102"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["scope"] == "101-103"
    assert Path(out["ids"]).read_text().split() == ["101", "102", "103"]
    export(Path(out["dir"]) / "export.xml", RECORDS[:3])
    assert cli.main(base + ["exported", str(out["job"])]) == 0
    assert cli.main(base + ["exported", str(out["job"])]) == 1
    capsys.readouterr()
    assert cli.main(base + ["chunks", str(out["job"])]) == 1          # not matched yet
    assert cli.main(base + ["worker", "--pause", "0"]) == 0
    capsys.readouterr()
    assert cli.main(base + ["show", str(out["job"])]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["state"] == "ready" and shown["report"]["records"] == 3 and shown["report_html"].endswith(".html")
    # The panel's list: enriched records first, each with its classes and fields added.
    changed = {c["biblionumber"]: c for c in shown["changes"]}
    assert shown["changes"][0]["status"] == "enriched" and changed[101]["added"] >= 1
    assert set(changed[101]) == {"biblionumber", "status", "title", "m0", "m1", "w", "r", "added"}
    assert cli.main(base + ["diff", str(out["job"]), "101"]) == 0
    assert "+ 650" in capsys.readouterr().out
    assert cli.main(base + ["pause", "on"]) == 0 and (state / "pause").exists()
    assert cli.main(base + ["status"]) == 0
    assert json.loads(capsys.readouterr().out)["pause_file"] is True
    assert cli.main(base + ["pause", "off"]) == 0 and not (state / "pause").exists()
    assert cli.main(base + ["list"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["id"] == out["job"]
    assert cli.main(base + ["add", "--scope", "x-y"]) == 1
    assert cli.main(base + ["show", "99"]) == 1
