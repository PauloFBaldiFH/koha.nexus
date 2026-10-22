"""Synthetic contracts for the pre-build, three-mode review document."""
import importlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import INSTALLER


@pytest.fixture
def api(tmp_path):
    root = tmp_path / 'engine'
    for match in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n',
                             INSTALLER.read_text(), re.S):
        path = root / match[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(match[2] + '\n')
    for name in list(sys.modules):
        if name == 'kei_import' or name.startswith('kei_import.'):
            del sys.modules[name]
    sys.path.insert(0, str(root))
    yield importlib.import_module('kei_import.review'), root
    sys.path.remove(str(root))


def options(tmp_path, name, content, mode='auto'):
    source = tmp_path / name
    source.write_text(content)
    work = tmp_path / 'work'
    work.mkdir(exist_ok=True)
    return SimpleNamespace(src=str(source), work=str(work), mode=mode, branch='CA', itype='BK',
        answers=None, profiles=None, readers='', branches=None, itypes=None, locations=None,
        categories=None, cpf_attr=False, today='2026-01-01', yaz='yaz-marcdump',
        capabilities=None, existing_barcodes=None, fieldmap=None, sample=3)


def test_draft_is_available_before_build_and_before_questions_are_answered(api, tmp_path):
    review, _ = api
    opts = options(tmp_path, 'unknown.csv', 'Column A,Column B\nalpha,beta\ngamma,delta\n')
    document, status = review.draft(opts)
    assert status == 0
    assert document['questions']
    assert not (Path(opts.work) / 'out/manifest.tsv').exists()
    assert len(document['columns']) == 2
    assert document['tables'][0]['columns'] == [column['id'] for column in document['columns']]
    assert all(column['to'] == 'ignore' for column in document['columns'])
    assert json.loads((Path(opts.work) / 'fields.json').read_text())['version'] == 2


def test_patron_draft_offers_supported_wide_fields_and_masks_credentials(api, tmp_path):
    review, _ = api
    sql = ("INSERT INTO borrowers (surname,cardnumber,country,preferred_name,dateenrolled,password) VALUES "
           "('Synthetic','SYN-C1','BR','Reader','2024-01-02','$2y$not-a-real-hash');")
    opts = options(tmp_path, 'people.sql', sql, 'patrons')
    document, status = review.draft(opts)
    assert status == 0
    by_header = {column['header']: column for column in document['columns']}
    assert by_header['country']['to'] == 'country'
    assert by_header['preferred_name']['to'] == 'preferred_name'
    assert by_header['dateenrolled']['to'] == 'dateenrolled'
    assert by_header['password']['to'] == 'ignore'
    assert by_header['password']['values'] == ['[redacted]']
    assert '$2y$' not in json.dumps(document)
    offered = {field['to'] for field in document['targets_by_mode']['patrons']}
    assert 'preferred_name' in offered and 'password' not in offered


def test_draft_proposals_follow_shuffled_headers_and_not_ordinal_positions(api, tmp_path):
    review, _ = api
    first, _ = review.draft(options(tmp_path, 'first.sql',
        "INSERT INTO borrowers (surname,cardnumber,zipcode) VALUES ('Synthetic','SYN-C1','80000-000');", 'patrons'))
    second, _ = review.draft(options(tmp_path, 'second.sql',
        "INSERT INTO borrowers (zipcode,surname,cardnumber) VALUES ('80000-000','Synthetic','SYN-C1');", 'patrons'))
    left = {column['header']: column['to'] for column in first['columns']}
    right = {column['header']: column['to'] for column in second['columns']}
    assert left == right == {'surname': 'surname', 'cardnumber': 'cardnumber', 'zipcode': 'zipcode'}
    assert first['tables'][0]['table_key'] == second['tables'][0]['table_key'] == 'borrowers'


def test_headless_dates_remain_review_choices(api, tmp_path):
    review, _ = api
    opts = options(tmp_path, 'headless.sql',
        "INSERT INTO borrowers VALUES ('2000-01-02','2024-01-01','reader@example.invalid','80000-000'),"
        "('2001-02-03','2025-01-01','other@example.invalid','88000-000');", 'patrons')
    document, _ = review.draft(opts)
    dates = [column for column in document['columns'] if column['values'][0] in ('2000-01-02', '2024-01-01')]
    assert len(dates) == 2
    assert all(column['to'] == 'ignore' for column in dates)
    assert any(column['to'] == 'email' for column in document['columns'])


def test_patron_preview_uses_the_final_build_dates_defaults_and_remaps(api, tmp_path):
    review, root = api
    opts = options(tmp_path, 'patrons.sql',
        "INSERT INTO borrowers (cardnumber,surname,dateofbirth,branchcode) VALUES "
        "('SYN-C1','Synthetic','02/01/1990','MAIN'),('SYN-C2','Example','1991-02-03','');", 'patrons')
    document, _ = review.draft(opts)
    spec = document['mapping']
    spec['defaults'] = {'branchcode': 'CA', 'categorycode': 'PT'}
    spec['remaps'] = {'branchcode': {'MAIN': 'CA'}}
    output = review.preview_document(document, spec)
    assert output['status'] == 0
    records = output['groups'][0]['records']
    assert records[0]['dateofbirth'] == '1990-01-02'
    assert all(record['branchcode'] == 'CA' and record['categorycode'] == 'PT' for record in records)
    assert not list(Path(opts.work).glob('mapping-preview-*'))


def test_authority_preview_preserves_repeated_tracings_and_type_mapping(api, tmp_path):
    review, _ = api
    text = ('000  00000nz  a2200000n  4500\n001  SYN-A1\n100 1_ |aExample, Synthetic\n'
            '400 1_ |aSynthetic, Example\n400 1_ |aAnother variant\n670 __ |aSynthetic source\n')
    opts = options(tmp_path, 'authorities.txt', text)
    document, status = review.draft(opts)
    assert status == 0 and document['streams'][0]['mode'] == 'authorities'
    output = review.preview_document(document, document['mapping'])
    assert output['status'] == 0
    record = output['groups'][0]['records'][0]
    assert record.count('400 ') == 2 and 'Another variant' in record


def test_bibliographic_preview_uses_item_normalization(api, tmp_path):
    review, _ = api
    text = ('=LDR  00000nam a2200000 a 4500\n=001  SYN-B1\n=245  10$aSynthetic title\n'
            '=952  \\\\$aMAIN$bMAIN$pSYN-001$yBK$d2024-01-02\n')
    opts = options(tmp_path, 'catalogue (synthetic).mrk', text)
    document, status = review.draft(opts)
    assert status == 0
    spec = document['mapping']
    spec['remaps'] = {'952$a': {'MAIN': 'CA'}, '952$b': {'MAIN': 'CA'}}
    output = review.preview_document(document, spec)
    assert output['status'] == 0
    record = output['groups'][0]['records'][0]
    assert '$a CA' in record and '$b CA' in record and '$p SYN-001' in record
    assert '$d 2024-01-02' in record


def test_draft_does_not_approve_relational_key_candidates(api, tmp_path, monkeypatch):
    review, _ = api
    opts = options(tmp_path, 'catalogue.csv', 'Title,ISBN\nSynthetic title,9788535914849\n')
    original = review.engine.analyse
    def with_candidates(options):
        analysis = original(options)
        analysis.relationships = [{'table': 'items', 'child_key': 1, 'parent_key': 2}]
        return analysis
    monkeypatch.setattr(review.engine, 'analyse', with_candidates)
    document, _ = review.draft(opts)
    assert document['relationships']
    assert document['mapping']['relationships'] == []


def test_preview_limits_records_to_three_and_reports_full_file_duplicates(api, tmp_path):
    review, _ = api
    values = ["('SYN-C%d','Synthetic')" % index for index in range(1, 5)]
    values.append("('SYN-C1','Duplicate')")
    opts = options(tmp_path, 'people.sql',
        'INSERT INTO borrowers (cardnumber,surname) VALUES ' + ','.join(values) + ';', 'patrons')
    document, _ = review.draft(opts)
    output = review.preview_document(document, document['mapping'])
    assert len(output['groups'][0]['records']) == 3
    assert any(issue.get('code') == 'duplicate' for issue in output['issues'])
