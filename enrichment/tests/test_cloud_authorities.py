"""Synthetic harvest, ranking and migration contracts, without public requests."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import koha_nexus_harvest as harvest
import setup_z3950_authorities as setup
from nexus_enrich.static import SCHEMA, create_empty
from nexus_gateway.authorities import AuthoritySearch
from nexus_gateway import cql


def binding(label='Example, Person'):
    return {'person': {'value': 'http://www.wikidata.org/entity/Q123'},
            'personLabel': {'value': label}, 'identifier': {'value': 'n123'}}


def test_harvest_idempotence_and_fts():
    conn = sqlite3.connect(':memory:')
    conn.executescript(SCHEMA)
    with conn:
        assert harvest.apply(conn, 'loc', [binding()]) == 1
        assert harvest.apply(conn, 'loc', [binding()]) == 0
    assert conn.execute('SELECT preliminary, source, lccn FROM auth_headings').fetchone() == (1, 'wikidata-loc', 'n123')
    assert conn.execute("SELECT COUNT(*) FROM auth_fts WHERE auth_fts MATCH 'Example'").fetchone()[0] == 1


def test_partitioned_bounded_query():
    assert 'wdt:P27 wd:Q155' in harvest.query('loc', 'Q155')
    assert 'wdt:P244' in harvest.query('loc', 'Q155')
    assert 'wdt:P4619' in harvest.query('bn', 'Q155')
    assert harvest.query('bn', 'Q155').endswith('LIMIT 3000')
    with pytest.raises(ValueError):
        harvest.query('loc', 'Q0')


def test_fetch_failure_leaves_database_unchanged(tmp_path, monkeypatch):
    path = tmp_path / 'static.db'
    create_empty(path)
    def fail(*args):
        raise OSError('synthetic network failure')
    monkeypatch.setattr(harvest, 'fetch', fail)
    assert harvest.main(['--source', 'all', '--db', str(path), '--no-reload']) == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM auth_headings').fetchone()[0] == 0


def test_invalid_batch_rolls_back_and_no_service_on_rerun(tmp_path, monkeypatch):
    path = tmp_path / 'static.db'
    create_empty(path)
    monkeypatch.setattr(harvest, 'fetch', lambda *args: [binding(), binding('Q456')])
    calls = []
    monkeypatch.setattr(harvest.subprocess, 'run', lambda *a, **kw: calls.append(a))
    argv = ['--source', 'loc', '--db', str(path)]
    assert harvest.main(argv) == 0
    assert harvest.main(argv) == 0
    assert len(calls) == 1
    assert calls[0][0] == ['systemctl', 'reload-or-restart', 'koha-nexus-sru.service']
    invalid = binding(); invalid['person']['value'] = 'not-an-entity'
    monkeypatch.setattr(harvest, 'fetch', lambda *a: [binding('New Name'), invalid])
    assert harvest.main(argv) == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM auth_headings').fetchone()[0] == 1


def test_inverted_heading_ranks_before_long_homonym():
    conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    harvest.apply(conn, 'loc', [binding('Hugo, Victor Another'), binding('Hugo, Victor')])
    total, records = AuthoritySearch(conn).search(cql.parse('"Victor Hugo"'), 1, 10)
    assert total == 2
    assert records[0].get_fields('100')[0].text('a') == 'Hugo, Victor'


def test_explicit_migration_keeps_biblio_and_disables_legacy_only():
    sql = setup.render(True)
    assert "`rank` = 1, servername = 'Nexus Autoridades (Cloud)'" in sql
    assert "attributes = '1=1016'" in sql
    assert "AND servertype = 'sru'" in sql
    assert 'DELETE FROM' not in sql
    assert 'START TRANSACTION' not in setup.render(False)
