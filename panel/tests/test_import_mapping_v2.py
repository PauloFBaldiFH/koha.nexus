"""Contracts for the three-mode import mapper; all data below is synthetic.

The engine is read from the installer just as production writes it. These
tests deliberately describe the new interface before its implementation.
No SQL dump or patron data supplied by the user belongs in these fixtures.
"""

import importlib
import json
import re
import sys

import pytest

from conftest import INSTALLER


@pytest.fixture(scope="module")
def mapping_engine(tmp_path_factory):
    root = tmp_path_factory.mktemp("mapping-v2-engine")
    source = INSTALLER.read_text(encoding="utf-8")
    for match in re.finditer(
        r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n',
        source,
        re.S,
    ):
        path = root / match.group(1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(match.group(2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(root))
    for name in list(sys.modules):
        if name == "kei_import" or name.startswith("kei_import."):
            del sys.modules[name]
    try:
        yield importlib.import_module("kei_import.mapping"), importlib.import_module("kei_import.marc")
    finally:
        sys.path.remove(str(root))


def spec_obj(mode="patrons", mappings=None, **extra):
    return {"version": 2, "mode": mode, "mappings": mappings or [], **extra}


def column(id_, header, values, table="readers"):
    return {"id": id_, "source": "synthetic.csv", "table": table,
            "header": header, "values": values}


@pytest.mark.parametrize("mode", ["bibliographic", "patrons", "authorities"])
def test_explicit_modes_round_trip(mapping_engine, mode):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(mode))
    assert spec.mode == mode
    assert mapping.MappingSpec.from_obj(spec.to_obj()).to_obj() == spec.to_obj()


@pytest.mark.parametrize("mode", ["automatic-but-unknown", "biblio", "", None])
def test_unknown_modes_are_not_silently_bibliographic(mapping_engine, mode):
    mapping, _ = mapping_engine
    with pytest.raises(mapping.MappingError):
        mapping.MappingSpec.from_obj(spec_obj(mode))


def test_legacy_marc_mapping_keeps_its_behavior(mapping_engine):
    mapping, marc = mapping_engine
    record = marc.Record()
    record.add("500", " ", " ", ("a", "Example author"))
    record.add("245", "1", "0", ("a", "Example title"))
    spec = mapping.MappingSpec.from_obj(
        {"version": 1, "mappings": [{"from": "500$a", "to": "100$a"}]}
    )
    result = spec.apply_record(record)
    assert spec.mode == "bibliographic"
    assert "Example author" in result.formatted()
    assert "100 " in result.formatted()
    assert "Example title" in result.formatted()
    assert "500 " in record.formatted()  # preview must not mutate the input


def test_defaults_fill_gaps_and_remaps_change_only_named_codes(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(
        mappings=[{"source": "branch", "to": "branchcode"},
                  {"source": "category", "to": "categorycode"}],
        defaults={"branchcode": "CA", "categorycode": "ADULT"},
        remaps={"branchcode": {"MAIN": "CA"}},
    ))
    assert spec.apply_row({"branch": "MAIN", "category": "CHILD"}) == {
        "branchcode": "CA", "categorycode": "CHILD"}
    assert spec.apply_row({"branch": "OTHER", "category": ""}) == {
        "branchcode": "OTHER", "categorycode": "ADULT"}
    assert spec.apply_row({"branch": "", "category": "ADULT"}) == {
        "branchcode": "CA", "categorycode": "ADULT"}


def test_same_headers_in_different_tables_have_distinct_column_ids(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {"source": "people:column-a", "to": "email"},
        {"source": "contacts:column-a", "to": "B_email"},
        {"source": "people:column-b", "to": "zipcode"},
    ]))
    assert spec.apply_row({"people:column-a": "reader@example.invalid",
                           "contacts:column-a": "contact@example.invalid",
                           "people:column-b": "80000-000"}) == {
        "email": "reader@example.invalid", "B_email": "contact@example.invalid",
        "zipcode": "80000-000"}


def test_mapping_source_id_cannot_be_redefined(mapping_engine):
    mapping, _ = mapping_engine
    with pytest.raises(mapping.MappingError):
        mapping.MappingSpec.from_obj(spec_obj(mappings=[
            {"source": "opaque-id", "to": "email"},
            {"source": "opaque-id", "to": "zipcode"},
        ]))


def test_generic_patron_mapping_preserves_extended_supported_fields(mapping_engine):
    mapping, _ = mapping_engine
    values = {
        "cardnumber": "SYNTHETIC-1", "surname": "Example", "firstname": "Reader",
        "preferred_name": "Rê", "middle_name": "Middle", "pronouns": "they/them",
        "streetnumber": "100", "streettype": "Rua", "address": "Rua Exemplo",
        "address2": "Bairro Exemplo", "city": "Curitiba", "state": "PR",
        "zipcode": "80000-000", "country": "BR", "email": "reader@example.invalid",
        "emailpro": "work@example.invalid", "phonepro": "+55 41 3000-0000",
        "B_address": "Rua Alternativa", "B_city": "Outra Cidade",
        "B_state": "SC", "B_zipcode": "88000-000", "B_country": "BR",
        "B_email": "other@example.invalid", "dateofbirth": "1990-02-20",
        "branchcode": "CA", "categorycode": "ADULT", "dateenrolled": "2026-01-10",
        "dateexpiry": "2027-01-10", "contactname": "Contact Example",
        "borrowernotes": "Synthetic migration fixture", "opacnote": "Welcome",
        "altcontactfirstname": "Another", "altcontactsurname": "Example",
        "altcontactcountry": "BR", "smsalertnumber": "+55 41 90000-0000",
        "primary_contact_method": "email", "patron_attributes": "RG:EXAMPLE-123",
        "guarantor_relationship": "parent", "guarantor_id": "source-parent-42",
    }
    rules = [{"source": "opaque-" + field, "to": field} for field in values]
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=rules))
    actual = spec.apply_row({"opaque-" + field: value for field, value in values.items()},
                            supported_fields=set(values))
    assert actual == values


def test_target_schema_capabilities_are_checked(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {"source": "name", "to": "preferred_name"},
    ]))
    with pytest.raises(mapping.MappingError, match="preferred_name"):
        spec.apply_row({"name": "Example"}, supported_fields={"surname", "firstname"})


@pytest.mark.parametrize("field", ["password", "secret", "flags", "overdrive_auth_token",
                                  "protected", "auth_method"])
def test_sensitive_patron_destinations_require_explicit_authorization(mapping_engine, field):
    mapping, _ = mapping_engine
    with pytest.raises(mapping.MappingError, match=field):
        mapping.MappingSpec.from_obj(spec_obj(mappings=[{"source": "opaque", "to": field}]))


def test_patron_mapper_rejects_non_schema_destination(mapping_engine):
    mapping, _ = mapping_engine
    with pytest.raises(mapping.MappingError):
        mapping.MappingSpec.from_obj(spec_obj(mappings=[{"source": "name", "to": "DROP TABLE borrowers"}]))


@pytest.mark.parametrize("target", ["001", "008", "100$a", "110$a", "111$a", "130$a",
                                   "150$a", "151$a", "400$a", "450$a", "500$a", "550$a",
                                   "667$a", "670$a", "942$a"])
def test_authority_mapper_offers_authority_destinations(mapping_engine, target):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj("authorities", mappings=[
        {"source": "opaque", "to": target},
    ]))
    assert spec.mode == "authorities"
    assert spec.to_obj()["mappings"][0]["to"] == target


@pytest.mark.parametrize("target", ["245$a", "952$p", "952$y", "942$c"])
def test_authority_mapper_does_not_offer_bibliographic_item_destinations(mapping_engine, target):
    mapping, _ = mapping_engine
    with pytest.raises(mapping.MappingError):
        mapping.MappingSpec.from_obj(spec_obj("authorities", mappings=[
            {"source": "opaque", "to": target},
        ]))


def test_loaded_profile_follows_shuffled_headers_not_positions(mapping_engine):
    mapping, _ = mapping_engine
    original = [column("old-email", "E-mail", ["one@example.invalid", "two@example.invalid"]),
                column("old-zip", "CEP", ["80000-000", "88000-000"])]
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {"source": "old-email", "to": "email"}, {"source": "old-zip", "to": "zipcode"},
    ]))
    profile = mapping.make_profile(spec, original)
    current = [column("new-zip", "CEP", ["90000-000", "91000-000"]),
               column("new-email", "E-mail", ["three@example.invalid", "four@example.invalid"])]
    result = mapping.align_profile(profile, current)
    assert result["bindings"] == {"old-email": "new-email", "old-zip": "new-zip"}
    assert result["ambiguous"] == [] and result["missing"] == []
    encoded = json.dumps(profile)
    assert "one@example.invalid" not in encoded and "80000-000" not in encoded


def test_headless_profile_uses_content_and_reports_ambiguous_dates(mapping_engine):
    mapping, _ = mapping_engine
    original = [column("old-mail", "", ["a@example.invalid", "b@example.invalid"]),
                column("old-date", "", ["2000-01-01", "2001-02-02"])]
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {"source": "old-mail", "to": "email"}, {"source": "old-date", "to": "dateofbirth"},
    ]))
    profile = mapping.make_profile(spec, original)
    current = [column("candidate-date-a", "", ["1999-01-01", "2000-02-02"]),
               column("candidate-date-b", "", ["1998-01-01", "1999-02-02"]),
               column("candidate-mail", "", ["c@example.invalid", "d@example.invalid"])]
    result = mapping.align_profile(profile, current)
    assert result["bindings"] == {"old-mail": "candidate-mail"}
    assert result["ambiguous"] == ["old-date"]
    assert "old-date" not in result["bindings"]


def test_preview_first_three_rows_uses_exact_build_transformation(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {"source": "card", "to": "cardnumber"}, {"source": "name", "to": "surname"},
        {"source": "branch", "to": "branchcode"},
    ], defaults={"branchcode": "CA"}, remaps={"branchcode": {"MAIN": "CA"}}))
    rows = [{"card": "SYNTHETIC-%d" % n, "name": "Example %d" % n,
             "branch": "MAIN" if n % 2 else ""} for n in range(1, 6)]
    before = [dict(row) for row in rows]
    assert spec.preview_rows(rows, limit=3) == [spec.apply_row(row) for row in rows[:3]]
    assert rows == before


def test_patron_adapter_retains_extended_fields_and_exposes_real_errors(mapping_engine, tmp_path):
    mapping, _ = mapping_engine
    patrons = importlib.import_module('kei_import.patrons')
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {'source': field, 'to': field} for field in ('cardnumber', 'surname', 'country', 'dateofbirth', 'branchcode', 'categorycode')
    ], defaults={'branchcode': 'CA', 'categorycode': 'PT'}))
    rows, issues = patrons.build_rows([
        {'cardnumber': 'SYN-A', 'surname': 'Example', 'country': 'BR', 'dateofbirth': '02/03/1990'},
        {'cardnumber': 'SYN-A', 'surname': 'Example', 'country': 'PT', 'dateofbirth': '31/02/1990'},
    ], spec, registry={'branch': {'ca': 'CA'}, 'category': {'pt': 'PT'}})
    assert rows[0]['dateofbirth'] == '1990-03-02'
    assert rows[1]['dateofbirth'] == '31/02/1990'  # bad value is visible for correction
    assert {issue['code'] for issue in issues} >= {'duplicate', 'invalid_date'}
    writer = patrons.Patrons()
    writer.rows = rows
    columns = writer.write(tmp_path / 'patrons.csv')
    assert 'country' in columns and 'BR' in (tmp_path / 'patrons.csv').read_text()


def test_source_password_hash_is_not_reused_even_after_sensitive_opt_in(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[{'source': 'opaque', 'to': 'password'}], allow_restricted=True))
    with pytest.raises(mapping.MappingError, match='hashes'):
        spec.apply_row({'opaque': '$2y$synthetic-not-a-real-password-hash'})


def test_guarantor_identity_is_resolved_instead_of_reusing_source_database_id(mapping_engine):
    mapping, _ = mapping_engine
    patrons = importlib.import_module('kei_import.patrons')
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[{'source': 'opaque-parent', 'to': 'guarantor_id'}]))
    rows, issues = patrons.build_rows([{'opaque-parent': 'source-42'}], spec, required_fields=())
    assert any(issue['code'] == 'unresolved_guarantor' for issue in issues)
    rows, issues = patrons.build_rows([{'opaque-parent': 'source-42'}], spec, required_fields=(), registry={'guarantor_ids': {'source-42': 'target-8'}})
    assert rows == [{'guarantor_id': 'target-8'}] and issues == []


def test_mixed_upload_rules_are_validated_and_filtered_by_effective_mode(mapping_engine):
    mapping, _ = mapping_engine
    obj = spec_obj('bibliographic', mappings=[
        {'source': 'books-title', 'to': '245$a'},
        {'source': 'readers-card', 'to': 'cardnumber', 'table': 'readers'},
        {'source': 'readers-country', 'to': 'country', 'source_table': 'readers'},
        {'source': 'auth-type', 'to': '942$a', 'mode': 'authorities'},
        {'source': 'readers-mail', 'to': 'email', 'mode': 'patrons'},
    ], table_modes={'readers': 'patrons'}, defaults={'branchcode': 'CA', '942$c': 'BK'},
        remaps={'branchcode': {'MAIN': 'CA'}})
    spec = mapping.MappingSpec.from_obj(obj)
    assert spec.to_obj()['mappings'][1]['table'] == 'readers'
    patrons = spec.for_mode('patrons', {'readers-card', 'readers-country'})
    assert {rule['source'] for rule in patrons.mappings} == {'readers-card', 'readers-country'}
    assert patrons.apply_row({'readers-card': 'SYN-1', 'readers-country': 'BR'}) == {
        'cardnumber': 'SYN-1', 'country': 'BR', 'branchcode': 'CA'}
    assert patrons.defaults == {'branchcode': 'CA'}
    assert spec.for_mode('bibliographic').defaults == {'942$c': 'BK'}
    assert spec.for_mode('authorities').mappings[0]['source'] == 'auth-type'


def test_mixed_upload_cannot_hide_restricted_fields_in_another_mode(mapping_engine):
    mapping, _ = mapping_engine
    with pytest.raises(mapping.MappingError, match='password'):
        mapping.MappingSpec.from_obj(spec_obj('bibliographic', mappings=[
            {'source': 'opaque', 'to': 'password', 'mode': 'patrons'},
        ]))


def test_profiles_never_store_literal_sensitive_field_values(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(allow_restricted=True, defaults={'password': 'synthetic-secret'}))
    with pytest.raises(mapping.MappingError, match='profiles'):
        mapping.make_profile(spec, [])


    spec = mapping.MappingSpec.from_obj(spec_obj(allow_restricted=True, defaults={'password': '$argon2synthetic'}))
    with pytest.raises(mapping.MappingError, match='hashes'):
        spec.apply_row({})
    spec = mapping.MappingSpec.from_obj(spec_obj(allow_restricted=True,
        mappings=[{'source': 'opaque', 'to': 'password'}],
        remaps={'password': {'temporary': '$2y$synthetic-only'}}))
    with pytest.raises(mapping.MappingError, match='hashes'):
        spec.apply_row({'opaque': 'temporary'})
    with pytest.raises(mapping.MappingError, match='profiles'):
        mapping.make_profile(spec, [])


@pytest.mark.parametrize('value', ['$2y$synthetic-hash', '$argon2synthetic-hash', '{SHA}synthetic-hash'])
def test_password_prefix_cannot_disguise_a_source_hash(mapping_engine, value):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(allow_restricted=True, mappings=[
        {'source': 'synthetic-password', 'to': 'password', 'transform': 'prefix', 'prefix': 'plain:'},
    ]))
    with pytest.raises(mapping.MappingError, match='hashes'):
        spec.apply_row({'synthetic-password': value})


def test_fixed_values_keep_opaque_source_ids_and_apply_without_source_data(mapping_engine):
    mapping, _ = mapping_engine
    rule = {'source': 'opaque-original-column', 'to': 'branchcode', 'value': 'CA'}
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[rule]))
    assert spec.apply_row({}) == {'branchcode': 'CA'}
    assert spec.apply_row({'opaque-original-column': 'MAIN'}) == {'branchcode': 'CA'}
    assert spec.to_obj()['mappings'] == [rule]


def test_split_name_transform_preserves_explicit_fields_and_never_mutates_source(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {'source': 'full', 'to': 'surname', 'transform': 'split_name'},
        {'source': 'first', 'to': 'firstname'},
    ]))
    original = {'full': 'Souza, Ana', 'first': 'Ana'}
    assert spec.apply_row(original) == {'firstname': 'Ana', 'surname': 'Souza'}
    assert original == {'full': 'Souza, Ana', 'first': 'Ana'}
    with pytest.raises(mapping.MappingError, match='firstname'):
        spec.apply_row({'full': 'Souza, Ana', 'first': 'Different'})


def test_prefix_transform_is_literal_and_shared_by_preview_and_build(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(mappings=[
        {'source': 'cpf-column', 'to': 'patron_attributes', 'transform': 'prefix', 'prefix': 'CPF:'},
    ]))
    assert spec.apply_row({'cpf-column': '00000000000'}) == {'patron_attributes': 'CPF:00000000000'}
    assert spec.preview_rows([{'cpf-column': '00000000000'}]) == [{'patron_attributes': 'CPF:00000000000'}]


@pytest.mark.parametrize('mode,rule', [
    ('patrons', {'source': 'opaque', 'to': 'surname', 'transform': '__import__'}),
    ('patrons', {'source': 'opaque', 'to': 'firstname', 'transform': 'split_name'}),
    ('bibliographic', {'source': 'opaque', 'to': '100$a', 'transform': 'split_name'}),
    ('patrons', {'source': 'opaque', 'to': 'patron_attributes', 'transform': 'prefix', 'prefix': {'eval': 'bad'}}),
    ('patrons', {'source': 'opaque', 'to': 'surname', 'value': ['not', 'literal']}),
])
def test_mapping_functions_reject_unapproved_operations(mapping_engine, mode, rule):
    mapping, _ = mapping_engine
    with pytest.raises(mapping.MappingError):
        mapping.MappingSpec.from_obj(spec_obj(mode, mappings=[rule]))


def test_fixed_marc_value_replaces_only_the_named_source_reference(mapping_engine):
    mapping, marc = mapping_engine
    record = marc.Record()
    record.add('942', ' ', ' ', ('c', 'OLD'), ('h', 'Retained'))
    record.add('245', '1', '0', ('a', 'Example title'))
    spec = mapping.MappingSpec.from_obj(spec_obj('bibliographic', mappings=[
        {'source': 'opaque-type', 'ref': '942$c', 'to': '942$c', 'value': 'BK'},
    ]))
    changed = spec.apply_record(record)
    assert next(field for field in changed.fields if field.tag == '942').get('c') == 'BK'
    assert 'Retained' in changed.formatted() and 'Example title' in changed.formatted()
    assert record.fields[0].get('c') == 'OLD'


def test_prefix_transform_on_marc_values_is_literal_and_does_not_mutate_input(mapping_engine):
    mapping, marc = mapping_engine
    record = marc.Record()
    record.add('500', ' ', ' ', ('a', 'Example note'))
    spec = mapping.MappingSpec.from_obj(spec_obj('bibliographic', mappings=[
        {'source': 'scoped-note', 'ref': '500$a', 'to': '500$a', 'transform': 'prefix', 'prefix': 'Source: '},
    ]))
    assert spec.apply_record(record).fields[0].get('a') == 'Source: Example note'
    assert record.fields[0].get('a') == 'Example note'


def test_fixed_sensitive_values_remain_subject_to_hash_and_profile_guards(mapping_engine):
    mapping, _ = mapping_engine
    spec = mapping.MappingSpec.from_obj(spec_obj(allow_restricted=True, mappings=[
        {'source': 'opaque', 'to': 'password', 'value': 'synthetic-secret'},
    ]))
    with pytest.raises(mapping.MappingError, match='profiles'):
        mapping.make_profile(spec, [])
    hash_spec = mapping.MappingSpec.from_obj(spec_obj(allow_restricted=True, mappings=[
        {'source': 'opaque', 'to': 'password', 'value': '$2y$synthetic-only'},
    ]))
    with pytest.raises(mapping.MappingError, match='hashes'):
        hash_spec.apply_row({})
