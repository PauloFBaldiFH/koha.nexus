"""Synthetic authority import framework tests, separate from name merging."""
import importlib
import re
import sys

import pytest
from conftest import INSTALLER


@pytest.fixture
def api(tmp_path):
    for match in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n',
                             INSTALLER.read_text(), re.S):
        path = tmp_path / match[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(match[2] + '\n')
    for name in list(sys.modules):
        if name == 'kei_import' or name.startswith('kei_import.'):
            del sys.modules[name]
    sys.path.insert(0, str(tmp_path))
    yield importlib.import_module('kei_import.marc'), importlib.import_module('kei_import.authority_import')
    sys.path.remove(str(tmp_path))


def authority(marc, tag='100', code='a'):
    rec = marc.Record('00000nz  a2200000n  4500')
    rec.control('001', 'SYN-A1')
    rec.add(tag, ' ', ' ', (code, 'Synthetic heading'))
    rec.add('670', ' ', ' ', ('a', 'Synthetic source'))
    return rec


@pytest.mark.parametrize('tag,code', [('100', 'a'), ('155', 'a'), ('180', 'x')])
def test_heading_types_and_tracings_are_preserved(api, tag, code):
    marc, adapter = api
    rec = authority(marc, tag, code)
    rec.add('450', ' ', ' ', ('a', 'A variant'), ('x', 'Subdivision'), ('x', 'Other subdivision'))
    before = rec.formatted()
    output, issues = adapter.prepare(rec)
    assert not [issue for issue in issues if issue['severity'] == 'error']
    assert output.formatted() == before == rec.formatted()


def test_authtype_is_selected_from_target_framework_not_fixed_code(api):
    marc, adapter = api
    caps = {'authoritytypes': [{'code': 'LOCAL_PERSON', 'tag': '100'}], 'authority_type_field': '942$a'}
    output, issues = adapter.prepare(authority(marc), caps)
    assert not issues
    assert next(field for field in output.fields if field.tag == '942').get('a') == 'LOCAL_PERSON'


def test_invalid_type_and_wrong_mode_are_not_silently_repaired(api):
    marc, adapter = api
    rec = authority(marc)
    rec.leader = marc.Record().leader
    output, issues = adapter.prepare(rec, {'authoritytypes': [{'code': 'PERSON', 'tag': '100'}]}, 'UNKNOWN')
    assert {'authority-leader', 'authority-type'} <= {issue['code'] for issue in issues}
    assert output.leader == rec.leader


def test_multiple_headings_require_review(api):
    marc, adapter = api
    rec = authority(marc)
    rec.add('150', ' ', ' ', ('a', 'Another heading'))
    _, issues = adapter.prepare(rec)
    assert any(issue['code'] == 'authority-heading' for issue in issues)


def test_table_authorities_require_explicit_heading_mapping(api):
    _, adapter = api
    records, issues = adapter.rows_to_records(
        [{'col:title': 'Synthetic bibliographic title'}],
        {'version': 2, 'mode': 'authorities', 'mappings': []},
    )
    assert records == []
    assert issues[0]['code'] == 'authority-unmapped'
    assert 'Synthetic bibliographic title' not in str(issues)


def test_table_authority_mapping_uses_ids_and_target_framework(api):
    _, adapter = api
    records, issues = adapter.rows_to_records(
        [{'source:date': '1900-1980', 'source:name': 'Example, Synthetic',
          'source:id': 'SYN-A21', 'source:source': 'Synthetic reference'}],
        {'version': 2, 'mode': 'authorities', 'mappings': [
            {'source': 'source:name', 'to': '100$a'},
            {'source': 'source:date', 'to': '100$d'},
            {'source': 'source:id', 'to': '001'},
            {'source': 'source:source', 'to': '670$a'},
        ]},
        {'authoritytypes': [{'code': 'LOCAL_PERSON', 'tag': '100'}]},
    )
    assert not issues
    assert len(records) == 1
    heading = next(field for field in records[0].fields if field.tag == '100')
    assert heading.get('a') == 'Example, Synthetic' and heading.get('d') == '1900-1980'
    assert next(field for field in records[0].fields if field.tag == '152').get('b') == 'LOCAL_PERSON'
    assert records[0].leader[6] == 'z'


def test_repeatable_authority_tracings_are_preserved_without_positional_join(api):
    _, adapter = api
    records, issues = adapter.rows_to_records(
        [{'id:heading': 'Synthetic topic', 'id:variants': ['Synthetic variant one', 'Synthetic variant two'],
          'id:other': 'Synthetic variant three'}],
        {'version': 2, 'mode': 'authorities', 'mappings': [
            {'source': 'id:heading', 'to': '150$a'},
            {'source': 'id:variants', 'to': '450$a'},
            {'source': 'id:other', 'to': '450$a'},
        ]},
    )
    assert not issues
    variants = [field.get('a') for field in records[0].fields if field.tag == '450']
    assert variants == ['Synthetic variant one', 'Synthetic variant two', 'Synthetic variant three']


def test_authority_table_defaults_and_remaps_match_shared_mapping(api):
    _, adapter = api
    records, issues = adapter.rows_to_records(
        [{'id:heading': 'Synthetic heading', 'id:type': 'PERSON_SOURCE'}],
        {'version': 2, 'mode': 'authorities', 'mappings': [
            {'source': 'id:heading', 'to': '100$a'},
            {'source': 'id:type', 'to': '942$a'},
        ], 'defaults': {'670$a': 'Synthetic default source'},
            'remaps': {'942$a': {'PERSON_SOURCE': 'PERSON_TARGET'}}},
        {'authoritytypes': [{'code': 'PERSON_TARGET', 'tag': '100'}], 'authority_type_field': '942$a'},
    )
    assert not issues
    assert next(field for field in records[0].fields if field.tag == '942').get('a') == 'PERSON_TARGET'
    assert next(field for field in records[0].fields if field.tag == '670').get('a') == 'Synthetic default source'


def test_authority_table_scope_excludes_other_tables_and_patron_rules(api):
    _, adapter = api
    records, issues = adapter.rows_to_records(
        [{'auth:name': 'Synthetic authority'}],
        {'version': 2, 'mode': 'patrons', 'mappings': [
            {'source': 'auth:name', 'to': '100$a', 'mode': 'authorities'},
            {'source': 'other:name', 'to': '150$a', 'mode': 'authorities'},
            {'source': 'pat:name', 'to': 'surname', 'mode': 'patrons'},
        ]},
    )
    assert not issues
    assert len(records) == 1 and records[0].count('100') == 1 and records[0].count('150') == 0


def test_authority_table_ambiguous_repeats_and_control_conflicts_require_review(api):
    _, adapter = api
    records, issues = adapter.rows_to_records(
        [{'id:heading': 'Synthetic heading', 'id:control': ['SYN-1', 'SYN-2'],
          'id:variants': ['Variant one', 'Variant two'], 'id:subdivision': 'Synthetic subdivision'}],
        {'version': 2, 'mode': 'authorities', 'mappings': [
            {'source': 'id:heading', 'to': '150$a'},
            {'source': 'id:control', 'to': '001'},
            {'source': 'id:variants', 'to': '450$a'},
            {'source': 'id:subdivision', 'to': '450$x'},
        ]},
    )
    assert {'authority-control-conflict', 'authority-occurrence-review'} <= {entry['code'] for entry in issues}
    variant = next(field for field in records[0].fields if field.tag == '450')
    assert variant.subfields == [('a', 'Variant one'), ('a', 'Variant two'), ('x', 'Synthetic subdivision')]
    assert all(entry['row'] == 1 for entry in issues)
    assert 'Variant one' not in str(issues)


def test_existing_explicit_type_wins_when_target_has_two_types_for_one_heading(api):
    marc, adapter = api
    record = authority(marc)
    record.add('152', ' ', ' ', ('b', 'LOCAL_PERSON'))
    caps = {'authoritytypes': [{'code': 'LOCAL_PERSON', 'tag': '100'},
                               {'code': 'PERSO_NAME', 'tag': '100'}]}
    output, issues = adapter.prepare(record, caps)
    assert not issues
    assert next(field for field in output.fields if field.tag == '152').get('b') == 'LOCAL_PERSON'
    assert record.formatted() == output.formatted()


def test_existing_unknown_type_cannot_be_replaced_by_an_inferred_type(api):
    marc, adapter = api
    record = authority(marc)
    record.add('152', ' ', ' ', ('b', 'UNKNOWN'))
    output, issues = adapter.prepare(record, {'authoritytypes': [{'code': 'PERSON', 'tag': '100'}]})
    assert any(issue['code'] == 'authority-type' for issue in issues)
    assert next(field for field in output.fields if field.tag == '152').get('b') == 'UNKNOWN'


def test_known_existing_type_must_match_the_authority_heading(api):
    marc, adapter = api
    record = authority(marc)
    record.add('152', ' ', ' ', ('b', 'TOPIC'))
    _, issues = adapter.prepare(record, {'authoritytypes': [{'code': 'TOPIC', 'tag': '150'}]})
    assert any(issue['code'] == 'authority-type-heading' for issue in issues)


def test_conflicting_existing_authority_types_remain_for_review(api):
    marc, adapter = api
    record = authority(marc)
    record.add('152', ' ', ' ', ('b', 'PERSON'), ('b', 'LOCAL_PERSON'))
    _, issues = adapter.prepare(record, {'authoritytypes': [{'code': 'PERSON', 'tag': '100'},
                                                          {'code': 'LOCAL_PERSON', 'tag': '100'}]})
    assert any(issue['code'] == 'authority-type-conflict' for issue in issues)
