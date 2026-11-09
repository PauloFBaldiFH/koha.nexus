"""Instance identity changes never rename, remove or operate on application data."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from nexus_core.instances import (
    InstanceContext, LegacyCandidate, Registry, RegistryError, discover_legacy,
)


def installation(tmp_path, application='dspace', status='installed'):
    root = tmp_path / 'server/var/lib/koha-nexus/platforms' / application
    root.mkdir(parents=True)
    state = root / ('state.json' if application == 'dspace' else 'state')
    if application == 'dspace':
        state.write_text(json.dumps({'status': status, 'url': 'http://192.168.1.50:8100',
                                    'password': 'NEVER_COPY_ME'}))
    else:
        state.write_text('status=' + status + '\nurl=http://192.168.1.50:8090\npassword=NEVER_COPY_ME\n')
    (root / 'data').write_text('application payload')
    return next(x for x in discover_legacy(tmp_path / 'server') if x.application == application)


def test_discovery_and_empty_registry_have_no_write_side_effects(tmp_path):
    root = tmp_path / 'missing'
    assert discover_legacy(root) == []
    assert Registry(root / 'registry').list() == []
    assert not root.exists()


def test_discovery_keeps_native_koha_sites_and_only_safe_state_fields(tmp_path):
    first = installation(tmp_path)
    second = installation(tmp_path, 'tainacan', 'kept')
    for name in ('library', 'museum'):
        conf = tmp_path / 'server/etc/koha/sites' / name / 'koha-conf.xml'
        conf.parent.mkdir(parents=True)
        conf.write_text('<config><password>NEVER_READ_ME</password></config>')
    rows = discover_legacy(tmp_path / 'server')
    assert len(rows) == 4
    assert {x.source_key for x in rows if x.application == 'koha'} == {'koha-native:library', 'koha-native:museum'}
    assert second.observed_status == 'data-kept'
    assert first.endpoints == {'public': 'http://192.168.1.50:8100'}
    assert 'NEVER_' not in repr(rows)


def test_unreadable_state_remains_unknown_not_absent(tmp_path):
    candidate = installation(tmp_path)
    Path(candidate.paths['state']).write_text('{broken')
    row, = discover_legacy(tmp_path / 'server')
    assert row.observed_status == 'unknown' and row.problem
    assert row.endpoints == {}


def test_invalid_or_secret_url_is_not_exposed(tmp_path):
    candidate = installation(tmp_path)
    Path(candidate.paths['state']).write_text(json.dumps({'status': 'installed', 'url': 'https://user:secret@example.org'}))
    row, = discover_legacy(tmp_path / 'server')
    assert not row.endpoints


def test_adoption_idempotent_and_rename_preserves_application_resources(tmp_path):
    candidate = installation(tmp_path)
    original = {p: Path(p).read_bytes() for p in candidate.paths.values() if Path(p).is_file()}
    registry = Registry(tmp_path / 'registry')
    adopted = registry.adopt(candidate, name='Repositório Municipal')
    assert registry.adopt(candidate).id == adopted.id
    renamed = registry.rename(adopted.id, 'Produção científica')
    assert renamed.name == 'Produção científica'
    assert renamed.id == adopted.id and renamed.paths == adopted.paths and renamed.resources == adopted.resources
    assert registry.adopt(candidate).name == renamed.name
    assert original == {p: Path(p).read_bytes() for p in original}
    assert adopted.health == 'not-checked'
    assert registry.root.stat().st_mode & 0o777 == 0o700
    assert (registry.root / (adopted.id + '.json')).stat().st_mode & 0o777 == 0o600


def test_concurrent_adoption_does_not_duplicate_instance(tmp_path):
    candidate = installation(tmp_path)
    root = tmp_path / 'registry'
    def adopt(_):
        return Registry(root).adopt(candidate).id
    with ThreadPoolExecutor(max_workers=6) as executor:
        ids = list(executor.map(adopt, range(12)))
    assert len(set(ids)) == 1
    assert len(Registry(root).list()) == 1


@pytest.mark.parametrize('ident', ['', 'dspace', '../dspace', None, 'ALL'])
def test_resolution_never_picks_first_instance(tmp_path, ident):
    registry = Registry(tmp_path / 'registry')
    registry.adopt(installation(tmp_path))
    with pytest.raises(RegistryError):
        registry.resolve(ident)


def test_target_application_and_changed_legacy_references_refused(tmp_path):
    registry = Registry(tmp_path / 'registry')
    candidate = installation(tmp_path)
    adopted = registry.adopt(candidate)
    with pytest.raises(RegistryError, match='different application'):
        registry.resolve(adopted.id, application='koha')
    other = tmp_path / 'another-data'
    other.mkdir()
    with pytest.raises(RegistryError, match='different references'):
        registry.adopt(replace(candidate, paths={'root': str(other)}))
    assert registry.get(adopted.id).paths == candidate.paths


def test_marking_removal_only_records_driver_result_never_erases_files(tmp_path):
    registry = Registry(tmp_path / 'registry')
    candidate = installation(tmp_path)
    adopted = registry.adopt(candidate)
    kept = registry.mark_removed(adopted.id, keep_data=True)
    assert kept.lifecycle == 'data-kept'
    assert Path(kept.paths['root'], 'data').read_text() == 'application payload'
    registry.mark_removed(adopted.id, keep_data=False)
    with pytest.raises(RegistryError, match='removed'):
        registry.resolve(adopted.id)
    with pytest.raises(RegistryError, match='explicit recovery'):
        registry.mark_removed(adopted.id, keep_data=True)
    assert Path(kept.paths['root'], 'data').exists()


def test_private_registry_rejects_symlinks_and_group_writable_records(tmp_path):
    registry = Registry(tmp_path / 'registry')
    adopted = registry.adopt(installation(tmp_path))
    record = registry.root / (adopted.id + '.json')
    content = record.read_bytes()
    record.chmod(0o660)
    with pytest.raises(RegistryError, match='private regular'):
        registry.get(adopted.id)
    record.unlink()
    other = tmp_path / 'external.json'
    other.write_bytes(content)
    other.chmod(0o600)
    record.symlink_to(other)
    with pytest.raises(RegistryError, match='trusted'):
        registry.get(adopted.id)
    assert other.read_bytes() == content
    alias = tmp_path / 'alias'
    alias.symlink_to(registry.root, target_is_directory=True)
    with pytest.raises(RegistryError, match='symbolic'):
        Registry(alias).list()


def test_symlinked_application_state_cannot_be_adopted(tmp_path):
    candidate = installation(tmp_path)
    state = Path(candidate.paths['state'])
    external = tmp_path / 'state.json'
    state.rename(external)
    state.symlink_to(external)
    row, = discover_legacy(tmp_path / 'server')
    assert row.observed_status == 'unknown'
    with pytest.raises(RegistryError, match='symbolic'):
        Registry(tmp_path / 'registry').adopt(row)


def test_corrupt_and_mismatched_records_fail_instead_of_disappearing(tmp_path):
    registry = Registry(tmp_path / 'registry')
    first = registry.adopt(installation(tmp_path))
    path = registry.root / (first.id + '.json')
    data = first.as_dict()
    data['schema'] = 999
    path.write_text(json.dumps(data))
    with pytest.raises(RegistryError):
        registry.list()
    data['schema'] = 1
    from uuid import uuid4
    data['id'] = str(uuid4())
    path.write_text(json.dumps(data))
    with pytest.raises(RegistryError, match='filename'):
        registry.get(first.id)


def test_atom_or_docker_koha_cannot_be_claimed_as_supported_driver(tmp_path):
    candidate = installation(tmp_path)
    with pytest.raises(RegistryError, match='Unsupported application'):
        Registry(tmp_path / 'registry').adopt(replace(candidate, application='koha', driver='koha-docker'))
    assert not (tmp_path / 'registry').exists()


def test_registry_cannot_be_replaced_through_a_writable_parent(tmp_path):
    parent = tmp_path / 'shared'
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    with pytest.raises(RegistryError, match='parent'):
        Registry(parent / 'registry').adopt(installation(tmp_path))
    assert not (parent / 'registry').exists()
