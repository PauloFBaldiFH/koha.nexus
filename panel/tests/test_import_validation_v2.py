"""Full-file safety boundary, with synthetic records and no live database."""
import csv
import importlib
import json
import re
import sys
from types import SimpleNamespace

import pytest
from conftest import INSTALLER


@pytest.fixture
def api(tmp_path):
    root = tmp_path / 'engine'
    for match in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n', INSTALLER.read_text(), re.S):
        path = root / match[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(match[2] + '\n')
    for name in list(sys.modules):
        if name == 'kei_import' or name.startswith('kei_import.'):
            del sys.modules[name]
    sys.path.insert(0, str(root))
    yield importlib.import_module('kei_import.validation'), importlib.import_module('kei_import.marc')
    sys.path.remove(str(root))


def analysis(**extra):
    return SimpleNamespace(review=[], unsupported=[], capabilities={}, spec=None,
                           koha={'branch': {'ca': 'CA'}, 'itemtype': {'bk': 'BK'}}, **extra)


def record(marc, barcode='SYN-C1', **codes):
    output = marc.Record()
    output.add('245', '1', '0', ('a', 'Synthetic catalogue title'))
    output.add('952', ' ', ' ', *[(key, value) for key, value in
               {'a': 'CA', 'b': 'CA', 'y': 'BK', 'p': barcode, **codes}.items()])
    return output


def stream(tmp_path, marc, records, name='catalogue', kind='biblio'):
    path = tmp_path / (name + '.xml')
    marc.write_marcxml(records, str(path))
    return (kind, 'MARCXML', 'UTF-8', str(path), len(records),
            sum(item.count('952') for item in records), '-', name)


def test_duplicate_after_preview_and_across_streams_is_blocked(api, tmp_path):
    validation, marc = api
    first = stream(tmp_path, marc, [record(marc, 'SYN-%d' % i) for i in range(5)])
    second = stream(tmp_path, marc, [record(marc, 'SYN-4')], 'other')
    report = validation.validate([first, second], analysis(), SimpleNamespace(existing_barcodes=None))
    assert report['blocked'] and any(issue['code'] == 'duplicate-barcode' for issue in report['issues'])
    assert 'SYN-4' not in json.dumps(report)


@pytest.mark.parametrize('code,value', [('a', 'UNKNOWN'), ('b', ''), ('y', 'UNKNOWN'), ('p', '')])
def test_invalid_and_missing_native_item_fields_block(api, tmp_path, code, value):
    validation, marc = api
    row = stream(tmp_path, marc, [record(marc, **{code: value})])
    report = validation.validate([row], analysis(), SimpleNamespace(existing_barcodes=None))
    assert report['blocked']
    assert any(issue.get('field') == '952$' + code for issue in report['issues'])


def test_target_barcode_comparison_preserves_literal_spaces(api, tmp_path):
    validation, marc = api
    target = tmp_path / 'barcodes.txt'
    target.write_text('  SYN-SPACE  \n')
    row = stream(tmp_path, marc, [record(marc, '  SYN-SPACE  ')])
    report = validation.validate([row], analysis(), SimpleNamespace(existing_barcodes=str(target)))
    assert any(issue['code'] == 'target-barcode' for issue in report['issues'])


def test_isbn_warning_keeps_a_valid_build_available_for_review(api, tmp_path):
    validation, marc = api
    item = record(marc)
    item.add('020', ' ', ' ', ('a', '9788508000013'))
    report = validation.validate([stream(tmp_path, marc, [item])], analysis(), SimpleNamespace(existing_barcodes=None))
    assert not report['blocked'] and report['warnings'] == 1


def test_private_normalization_audit_is_excluded_from_validation(api):
    validation, _ = api
    a = analysis()
    a.review = [{'kind': 'holdings', 'source': 'synthetic', 'record': 2,
                 'source_ids': ['PRIVATE-SOURCE-ID'], 'barcode_map': ['PRIVATE-CODE'],
                 'issues': [{'reason': 'Missing barcode', 'value': 'PRIVATE-VALUE'}]}]
    report = validation.validate([], a, SimpleNamespace(existing_barcodes=None))
    assert report['errors'] == 1
    assert 'PRIVATE' not in json.dumps(report)


def test_failed_reader_blocks_other_valid_streams(api, tmp_path):
    validation, marc = api
    report = validation.validate([stream(tmp_path, marc, [record(marc)])], analysis(build_failures=1),
                                 SimpleNamespace(existing_barcodes=None))
    assert report['blocked'] and any(issue['code'] == 'reader-failed' for issue in report['issues'])


def test_patron_target_updates_require_explicit_policy(api, tmp_path):
    validation, _ = api
    path = tmp_path / 'patrons.csv'
    path.write_text('cardnumber,surname,branchcode,categorycode\nSYN-C1,Synthetic,CA,PT\n')
    a = analysis()
    a.capabilities = {'cardnumbers': ['SYN-C1'], 'category': {'pt': 'PT'}}
    manifest = [('patrons', 'CSV', 'UTF-8', str(path), 1, 0, 'cardnumber', 'synthetic')]
    report = validation.validate(manifest, a, SimpleNamespace(existing_barcodes=None, update_patrons=False))
    assert report['blocked']
    assert not validation.validate(manifest, a, SimpleNamespace(existing_barcodes=None, update_patrons=True))['blocked']


def test_manifest_count_mismatch_is_not_reported_as_zero_success(api, tmp_path):
    validation, marc = api
    row = list(stream(tmp_path, marc, [record(marc)]))
    row[4] = 2
    report = validation.validate([row], analysis(), SimpleNamespace(existing_barcodes=None))
    assert any(issue['code'] == 'record-count' for issue in report['issues'])


def test_empty_authoritative_branch_registry_rejects_every_item_branch(api, tmp_path):
    validation, marc = api
    a = analysis()
    a.koha['branch'] = {}
    a.capabilities = {'branch': {}}
    report = validation.validate([stream(tmp_path, marc, [record(marc)])], a,
                                 SimpleNamespace(existing_barcodes=None))
    assert report['blocked']
    assert any(issue['code'] == 'invalid-item-code' and issue['field'] == '952$a' for issue in report['issues'])


def test_empty_authoritative_category_registry_rejects_unknown_patron_category(api, tmp_path):
    validation, _ = api
    path = tmp_path / 'patrons.csv'
    path.write_text('cardnumber,surname,categorycode\nSYN-C1,Synthetic,UNKNOWN\n')
    a = analysis()
    a.capabilities = {'category': {}}
    manifest = [('patrons', 'CSV', 'UTF-8', str(path), 1, 0, 'cardnumber', 'synthetic')]
    report = validation.validate(manifest, a, SimpleNamespace(existing_barcodes=None))
    assert report['blocked']
    assert any(issue['code'] == 'invalid-patron-code' for issue in report['issues'])


def test_standalone_category_tsv_is_authoritative_even_without_capabilities(api, tmp_path):
    validation, _ = api
    path = tmp_path / 'patrons.csv'
    path.write_text('cardnumber,surname,categorycode\nSYN-C1,Synthetic,PT\n')
    categories = tmp_path / 'categories.tsv'
    categories.write_text('PT\tSynthetic category\n')
    manifest = [('patrons', 'CSV', 'UTF-8', str(path), 1, 0, 'cardnumber', 'synthetic')]
    opts = SimpleNamespace(existing_barcodes=None, categories=str(categories))
    assert not validation.validate(manifest, analysis(), opts)['blocked']
    categories.write_text('')
    assert validation.validate(manifest, analysis(), opts)['blocked']


def test_branch_display_alias_is_not_a_destination_code(api, tmp_path):
    validation, marc = api
    a = analysis()
    a.koha['branch'] = {'ca': 'CA', 'synthetic branch': 'CA'}
    report = validation.validate([stream(tmp_path, marc, [record(marc, a='synthetic branch')])], a,
                                 SimpleNamespace(existing_barcodes=None))
    assert report['blocked']
    assert any(issue['code'] == 'invalid-item-code' for issue in report['issues'])


@pytest.mark.parametrize('collation,blocked', [('utf8mb4_unicode_ci', True), ('utf8mb4_bin', False)])
def test_barcode_case_comparison_matches_the_captured_target_collation(api, tmp_path, collation, blocked):
    validation, marc = api
    a = analysis()
    a.capabilities = {'identifier_collations': {'barcode': collation}}
    rows = [record(marc, 'SYN-CASE'), record(marc, 'syn-case')]
    report = validation.validate([stream(tmp_path, marc, rows)], a, SimpleNamespace(existing_barcodes=None))
    assert report['blocked'] is blocked
    assert 'syn-case' not in json.dumps(report)


def test_pad_space_target_barcode_collision_is_not_silently_missed(api, tmp_path):
    validation, marc = api
    a = analysis()
    a.capabilities = {'identifier_collations': {'barcode': 'utf8mb4_unicode_ci'}}
    target = tmp_path / 'target-barcodes.tsv'
    target.write_text('SYN-PAD\n')
    report = validation.validate([stream(tmp_path, marc, [record(marc, 'syn-pad  ')])], a,
                                 SimpleNamespace(existing_barcodes=str(target)))
    assert report['blocked']
    assert any(issue['code'] == 'target-barcode' for issue in report['issues'])


def test_patron_collisions_apply_case_accent_and_padding_rules_without_rewriting(api, tmp_path):
    validation, _ = api
    path = tmp_path / 'patrons.csv'
    path.write_text('cardnumber,surname,userid\nSYN-C1,Synthetic,Éxample \nsyn-c1,Other,example\n')
    before = path.read_text()
    a = analysis()
    a.capabilities = {'identifier_collations': {'cardnumber': 'utf8mb4_unicode_ci', 'userid': 'utf8mb4_unicode_ci'}}
    manifest = [('patrons', 'CSV', 'UTF-8', str(path), 2, 0, 'cardnumber', 'synthetic')]
    report = validation.validate(manifest, a, SimpleNamespace(existing_barcodes=None))
    assert report['blocked']
    assert {issue.get('field') for issue in report['issues'] if issue['code'] == 'duplicate-patron-id'} == {'cardnumber', 'userid'}
    assert path.read_text() == before
    assert 'Éxample' not in json.dumps(report)


def test_binary_and_nopad_identifier_comparison_preserves_distinct_values(api, tmp_path):
    validation, marc = api
    a = analysis()
    a.capabilities = {'identifier_collations': {'barcode': 'utf8mb4_0900_as_cs'}}
    report = validation.validate([stream(tmp_path, marc, [record(marc, 'SYN-CASE'), record(marc, 'syn-case ')])],
                                 a, SimpleNamespace(existing_barcodes=None))
    assert not report['blocked']
