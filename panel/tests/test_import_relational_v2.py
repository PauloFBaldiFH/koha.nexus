"""SQL relationships must survive reordering and expose ambiguous headless keys."""
import importlib
import json
import re
import sys

import pytest
from conftest import INSTALLER


@pytest.fixture
def modules(tmp_path):
    for match in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n',
                             INSTALLER.read_text(), re.S):
        path = tmp_path / match[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(match[2] + "\n")
    for name in list(sys.modules):
        if name == "kei_import" or name.startswith("kei_import."):
            del sys.modules[name]
    sys.path.insert(0, str(tmp_path))
    yield importlib.import_module("kei_import.readers"), importlib.import_module("kei_import.relational")
    sys.path.remove(str(tmp_path))


XML = ('<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader>'
       '<controlfield tag="001">CAT-10</controlfield><datafield tag="245" ind1="1" ind2="0">'
       '<subfield code="a">Synthetic title</subfield></datafield></record>')


@pytest.mark.parametrize("reverse", [False, True])
def test_declared_join_is_independent_of_column_position(modules, reverse):
    readers, relational = modules
    metadata = "INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',10);" % XML
    if reverse:
        items = "INSERT INTO items (itype,barcode,biblionumber,homebranch) VALUES ('BK','SYN-C1',10,'CA');"
    else:
        items = "INSERT INTO items (homebranch,biblionumber,barcode,itype) VALUES ('CA',10,'SYN-C1','BK');"
    records, remaining, review, _ = relational.extract(readers.read_sql(metadata + items))
    copies = [f for f in records[0].fields if f.tag == '952']
    assert len(copies) == 1
    assert {code: copies[0].get(code) for code in ('a','p','y')} == {'a':'CA','p':'SYN-C1','y':'BK'}
    assert not remaining and not review


def test_equal_key_overlap_does_not_pick_first_column(modules):
    readers, relational = modules
    metadata = "INSERT INTO meta VALUES (10,'%s');" % XML
    items = "INSERT INTO items VALUES (10,10,'SYN-C1','CA','BK');"
    records, remaining, review, candidates = relational.extract(readers.read_sql(metadata + items))
    assert not any(f.tag == '952' for f in records[0].fields)
    assert remaining and review
    assert len([p for p in candidates if p['coverage'] == 1]) >= 2


def test_reviewed_item_mapping_joins_anonymous_rows_without_schema_positions(modules):
    readers, relational = modules
    engine = importlib.import_module('kei_import.engine')
    mapping = importlib.import_module('kei_import.mapping')
    intake = importlib.import_module('kei_import.intake')
    member = intake.Member('/tmp/synthetic.sql', 'synthetic.sql')
    sql = ("INSERT INTO meta VALUES ('%s',10);" % XML
           + "INSERT INTO items VALUES ('CA','SYN-C1','BK',10);")
    identities = {code: 'col:' + engine.qid(member.display, 'synthetic.sql: items', index)
                  for index, code in enumerate(('a', 'p', 'y'))}
    spec = mapping.MappingSpec.from_obj({'version': 2, 'mode': 'bibliographic', 'mappings': [
        {'source': identities[code], 'to': '952$' + code} for code in ('a', 'p', 'y')
    ]})
    parsed = engine._mapped_sql_items(readers.read_sql(sql), member, spec)
    records, remaining, review, _ = relational.extract(parsed, [{
        'parent_table': 'meta', 'parent_column': 1, 'child_table': 'items', 'child_column': 3,
    }])
    item = next(field for field in records[0].fields if field.tag == '952')
    assert item.get('p') == 'SYN-C1' and item.get('a') == 'CA' and item.get('y') == 'BK'
    assert not remaining and not review


def test_orphan_item_is_reported_instead_of_attached_to_any_record(modules):
    readers, relational = modules
    sql = ("INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',10);" % XML
           + "INSERT INTO items (biblionumber,barcode,homebranch) VALUES (99,'SYN-C1','CA');")
    records, _, review, _ = relational.extract(readers.read_sql(sql))
    assert not any(f.tag == '952' for f in records[0].fields)
    assert any(entry['kind'] == 'orphan_item' for entry in review)


def test_metadata_insert_chunks_are_joined_as_one_source_table(modules):
    readers, relational = modules
    sql = ("INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',10);" % XML
           + "INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',20);" % XML.replace('CAT-10', 'CAT-20')
           + "INSERT INTO items (biblionumber,barcode,homebranch) VALUES (20,'SYN-C2','CA');")
    records, _, review, _ = relational.extract(readers.read_sql(sql))
    assert [len([f for f in record.fields if f.tag == '952']) for record in records] == [0, 1]
    assert not review


def test_insert_chunks_align_values_by_declared_names_when_header_order_changes(modules):
    readers, relational = modules
    sql = ("INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',10);" % XML
           + "INSERT INTO biblio_metadata (biblionumber,metadata) VALUES (20,'%s');" % XML.replace('CAT-10', 'CAT-20')
           + "INSERT INTO items (barcode,biblionumber,homebranch) VALUES ('SYN-C1',10,'CA');"
           + "INSERT INTO items (homebranch,biblionumber,barcode) VALUES ('CA',20,'SYN-C2');")
    records, remaining, review, _ = relational.extract(readers.read_sql(sql))
    linked = {}
    for record in records:
        identity = next(field.value for field in record.fields if field.tag == '001')
        linked[identity] = [field.get('p') for field in record.fields if field.tag == '952']
    assert linked == {'CAT-10': ['SYN-C1'], 'CAT-20': ['SYN-C2']}
    assert not remaining and not review


def test_qualified_source_names_do_not_collapse(modules):
    readers, _ = modules
    tables = readers.read_sql("INSERT INTO one.items VALUES (1); INSERT INTO two.items VALUES (2);")
    assert [table.name for table in tables] == ['one.items', 'two.items']


@pytest.mark.parametrize('bad_index', [-1, True, 100])
def test_reviewed_relationship_requires_valid_column_addresses(modules, bad_index):
    readers, relational = modules
    sql = ("INSERT INTO meta VALUES (10,'%s');" % XML
           + "INSERT INTO items VALUES (10,'SYN-C1');")
    with pytest.raises(ValueError):
        relational.extract(readers.read_sql(sql), [
            {'parent_table': 'meta', 'child_table': 'items', 'parent_column': bad_index, 'child_column': 0}])


def test_sql_decoding_does_not_unescape_literal_backslashes_twice(modules):
    readers, relational = modules
    xml = XML.replace('Synthetic title', r'Synthetic title C:\new\read')
    sql = "INSERT INTO meta (metadata,biblionumber) VALUES ('%s',10);" % xml.replace('\\', '\\\\')
    records, _, _, _ = relational.extract(readers.read_sql(sql))
    title = next(f for f in records[0].fields if f.tag == '245')
    assert title.get('a') == r'Synthetic title C:\new\read'


def _xml_with_native_item():
    return XML.replace('</record>', '<datafield tag="952" ind1=" " ind2=" ">'
                       '<subfield code="a">CA</subfield><subfield code="p">SYN-NATIVE-ONLY</subfield>'
                       '</datafield></record>')


def _bibliographic_selection(parent_column, child_column, child_table='biblio'):
    return {'kind': 'bibliographic', 'parent_table': 'biblio_metadata',
            'parent_column': parent_column, 'child_table': child_table, 'child_column': child_column}


def _assert_no_source_values_in_relationships(review, proposals):
    public = json.dumps({'review': review, 'relationships': proposals}, ensure_ascii=False)
    for private_marker in ('SYN-PRIVATE-TITLE', 'SYN-PRIVATE-AUTHOR', 'SYN-PRIVATE-CARD',
                           'SYN-ANONYMOUS-COPY', '<record', 'Synthetic title'):
        assert private_marker not in public


@pytest.mark.parametrize('reverse', [False, True])
def test_declared_biblio_rows_with_extra_columns_are_consumed_by_id_without_marc_changes(modules, reverse):
    readers, relational = modules
    xml = _xml_with_native_item()
    metadata = "INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % xml
    if reverse:
        bibliographic = ("INSERT INTO biblio (author,timestamp,biblionumber,title,abstract) "
                         "VALUES ('SYN-PRIVATE-AUTHOR','2026-01-01',9010042,'SYN-PRIVATE-TITLE','Extra scalar text');")
    else:
        bibliographic = ("INSERT INTO biblio (title,biblionumber,author,abstract,timestamp) "
                         "VALUES ('SYN-PRIVATE-TITLE',9010042,'SYN-PRIVATE-AUTHOR','Extra scalar text','2026-01-01');")
    expected = readers.read_report(xml)[0].formatted()
    records, remaining, review, proposals = relational.extract(readers.read_sql(metadata + bibliographic))
    assert len(records) == 1 and not remaining and not review
    # The source ID establishes redundancy. Different scalar title/author values
    # must not replace MARC fields or accidentally create a physical exemplar.
    assert records[0].formatted() == expected
    assert [field.get('p') for field in records[0].fields if field.tag == '952'] == ['SYN-NATIVE-ONLY']
    _assert_no_source_values_in_relationships(review, proposals)


@pytest.mark.parametrize('key_index', [0, 2])
def test_headless_named_biblio_requires_reviewed_bibliographic_relationship(modules, key_index):
    readers, relational = modules
    xml = _xml_with_native_item()
    row = ['SYN-PRIVATE-TITLE', 'SYN-PRIVATE-AUTHOR']
    row.insert(key_index, 9010042)
    values = ','.join(str(value) if isinstance(value, int) else "'%s'" % value for value in row)
    sql = ("INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % xml
           + 'INSERT INTO biblio VALUES (%s);' % values)
    parsed = readers.read_sql(sql)
    expected = readers.read_report(xml)[0].formatted()
    records, remaining, review, proposals = relational.extract(parsed)
    assert len(records) == 1 and records[0].formatted() == expected
    assert len(remaining) == 1 and remaining[0].name == 'biblio'
    assert remaining[0].rows == [[str(value) for value in row]]
    assert review and any(issue.get('severity', 'error') == 'error' for issue in review)
    assert any(proposal['parent_table'] == 'biblio_metadata' and proposal['parent_column'] == 1
               and proposal['child_table'] == 'biblio' and proposal['child_column'] == key_index
               for proposal in proposals)
    _assert_no_source_values_in_relationships(review, proposals)
    reviewed, remaining, review, proposals = relational.extract(
        parsed, [_bibliographic_selection(1, key_index)])
    assert len(reviewed) == 1 and reviewed[0].formatted() == expected
    assert not remaining and not review
    _assert_no_source_values_in_relationships(review, proposals)


@pytest.mark.parametrize('failure', ['orphan', 'duplicate-parent', 'duplicate-child'])
def test_bibliographic_keys_with_no_unique_match_remain_unconsumed_for_review(modules, failure):
    readers, relational = modules
    xml = _xml_with_native_item()
    metadata = "INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % xml
    expected = [readers.read_report(xml)[0].formatted()]
    if failure == 'duplicate-parent':
        second = xml.replace('CAT-10', 'CAT-20').replace('SYN-NATIVE-ONLY', 'SYN-NATIVE-SECOND')
        metadata += "INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % second
        expected.append(readers.read_report(second)[0].formatted())
    child_key = 9010099 if failure == 'orphan' else 9010042
    # The orphan deliberately has exactly the same title as the MARC record:
    # title equality cannot substitute for a verified source-key relationship.
    bibliographic = ("INSERT INTO biblio (biblionumber,title,author) VALUES "
                     "(%s,'Synthetic title','SYN-PRIVATE-AUTHOR');" % child_key)
    if failure == 'duplicate-child':
        bibliographic += ("INSERT INTO biblio (biblionumber,title,author) VALUES "
                          "(9010042,'SYN-PRIVATE-TITLE','Second synthetic author');")
    records, remaining, review, proposals = relational.extract(readers.read_sql(metadata + bibliographic))
    assert [record.formatted() for record in records] == expected
    assert len(remaining) == 1 and remaining[0].name == 'biblio'
    assert len(remaining[0].rows) == (2 if failure == 'duplicate-child' else 1)
    assert review and any(issue.get('severity', 'error') == 'error' for issue in review)
    _assert_no_source_values_in_relationships(review, proposals)


@pytest.mark.parametrize('columns', [('a', 'p', 'y', 'key'), ('key', 'y', 'a', 'p')])
def test_anonymous_tuple_items_need_both_field_mapping_and_reviewed_relationship(modules, columns):
    readers, relational = modules
    engine = importlib.import_module('kei_import.engine')
    mapping = importlib.import_module('kei_import.mapping')
    intake = importlib.import_module('kei_import.intake')
    member = intake.Member('/tmp/synthetic.sql', 'synthetic.sql')
    tuples = []
    for barcode in ('SYN-ANONYMOUS-COPY-1', 'SYN-ANONYMOUS-COPY-2'):
        values = {'a': 'CA', 'p': barcode, 'y': 'BK', 'key': 9010042}
        tuples.append('(' + ','.join(str(values[code]) if code == 'key' else "'%s'" % values[code]
                                     for code in columns) + ')')
    sql = ("INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % XML
           + ','.join(tuples) + ';')
    parsed = readers.read_sql(sql)
    anonymous = next(table for table in parsed if table.name.startswith('anonymous-'))
    selected = {'parent_table': 'biblio_metadata', 'parent_column': 1,
                'child_table': anonymous.name, 'child_column': columns.index('key')}
    records, remaining, review, proposals = relational.extract(parsed)
    assert len(records) == 1 and records[0].count('952') == 0
    assert [table.name for table in remaining] == [anonymous.name]
    assert review and any(proposal['child_table'] == anonymous.name for proposal in proposals)
    _assert_no_source_values_in_relationships(review, proposals)
    # Reviewing the key alone supplies no meaning for the remaining cells.
    records, remaining, review, _ = relational.extract(parsed, [selected])
    assert records[0].count('952') == 0 and remaining and review
    spec = mapping.MappingSpec.from_obj({'version': 2, 'mode': 'bibliographic', 'mappings': [
        {'source': 'col:' + engine.qid(member.display, member.display + ': ' + anonymous.name, index),
         'to': '952$' + code}
        for index, code in enumerate(columns) if code != 'key'
    ]})
    mapped = engine._mapped_sql_items(parsed, member, spec)
    assert anonymous.headers is None
    records, remaining, review, _ = relational.extract(mapped)
    assert records[0].count('952') == 0 and remaining and review
    records, remaining, review, proposals = relational.extract(mapped, [selected])
    copies = [field for field in records[0].fields if field.tag == '952']
    assert len(copies) == 2
    assert {field.get('p') for field in copies} == {'SYN-ANONYMOUS-COPY-1', 'SYN-ANONYMOUS-COPY-2'}
    assert all(field.get('a') == 'CA' and field.get('y') == 'BK' for field in copies)
    assert not remaining and not review
    _assert_no_source_values_in_relationships(review, proposals)


@pytest.mark.parametrize('table_name', ['borrowers', 'legacy_catalogue'])
def test_overlapping_non_biblio_table_is_not_consumed_without_explicit_bibliographic_kind(modules, table_name):
    readers, relational = modules
    xml = _xml_with_native_item()
    sql = ("INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % xml
           + "INSERT INTO %s (biblionumber,title,surname,cardnumber) VALUES " % table_name
           + "(9010042,'Synthetic title','SYN-PRIVATE-AUTHOR','SYN-PRIVATE-CARD');")
    parsed = readers.read_sql(sql)
    expected = readers.read_report(xml)[0].formatted()
    records, remaining, review, proposals = relational.extract(parsed)
    assert len(records) == 1 and records[0].formatted() == expected
    assert [table.name for table in remaining] == [table_name]
    assert not any(proposal.get('child_table') == table_name for proposal in proposals)
    assert not review
    reviewed, remaining, review, proposals = relational.extract(
        parsed, [_bibliographic_selection(1, 0, table_name)])
    assert len(reviewed) == 1 and reviewed[0].formatted() == expected
    assert not remaining and not review
    _assert_no_source_values_in_relationships(review, proposals)


def test_multiple_metadata_parents_need_a_reviewed_bibliographic_parent_selection(modules):
    readers, relational = modules
    second = XML.replace('CAT-10', 'CAT-20')
    sql = ("INSERT INTO first_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % XML
           + "INSERT INTO second_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % second
           + "INSERT INTO biblio (biblionumber,title,author) VALUES (9010042,'SYN-PRIVATE-TITLE','SYN-PRIVATE-AUTHOR');")
    parsed = readers.read_sql(sql)
    expected = [readers.read_report(xml)[0].formatted() for xml in (XML, second)]
    records, remaining, review, proposals = relational.extract(parsed)
    assert [record.formatted() for record in records] == expected
    assert [table.name for table in remaining] == ['biblio'] and review
    selected = dict(_bibliographic_selection(1, 0), parent_table='second_metadata')
    records, remaining, review, proposals = relational.extract(parsed, [selected])
    assert [record.formatted() for record in records] == expected
    assert not remaining and not review
    _assert_no_source_values_in_relationships(review, proposals)


def test_named_biblio_title_alone_never_consumes_a_metadata_record(modules):
    readers, relational = modules
    sql = ("INSERT INTO biblio_metadata (metadata,biblionumber) VALUES ('%s',9010042);" % XML
           + "INSERT INTO biblio (title,author) VALUES ('Synthetic title','SYN-PRIVATE-AUTHOR');")
    records, remaining, review, proposals = relational.extract(readers.read_sql(sql))
    assert len(records) == 1 and records[0].count('952') == 0
    assert [table.name for table in remaining] == ['biblio'] and review
    _assert_no_source_values_in_relationships(review, proposals)
