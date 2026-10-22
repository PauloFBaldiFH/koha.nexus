"""Synthetic holdings contract for Magic Import v2 (no library exports).

The normalizer returns (new_record, report), preserves its input, and uses
content plus declared profiles rather than subfield occurrence positions.
Registry keys follow the engine's existing Koha lookup snapshots.  Tests
exercise the engine extracted from the installer's actual shipped heredocs.
"""

import importlib
import re
import sys

import pytest
from conftest import INSTALLER


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    root = tmp_path_factory.mktemp("kei-holdings")
    text = INSTALLER.read_text(encoding="utf-8")
    for match in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n', text, re.S):
        path = root / match.group(1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(match.group(2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(root))
    for name in list(sys.modules):
        if name == "kei_import" or name.startswith("kei_import."):
            del sys.modules[name]
    yield importlib.import_module("kei_import.marc"), importlib.import_module("kei_import.normalizer")
    sys.path.remove(str(root))


@pytest.fixture
def registry():
    return {
        "branch": {"main": "MAIN", "ca": "CA"},
        "itemtype": {"bk": "BK", "dvd": "DVD"},
        "location": {"gen": "GEN"},
        "barcodes": set(),
    }


def rec(marc, identity="SOURCE-1"):
    record = marc.Record()
    record.control("001", identity)
    record.control("003", "BR-RjBN")
    record.add("245", "1", "0", ("a", "A synthetic title"))
    record.add("090", " ", " ", ("a", "123.4"), ("b", "S123"))
    return record


def native(marc, identity="SOURCE-1", barcode="TEST-001"):
    record = rec(marc, identity)
    record.add("952", " ", " ",
               ("a", "MAIN"), ("b", "MAIN"), ("y", "BK"),
               ("c", "GEN"), ("d", "2025-03-24"), ("o", "123.4 S123"),
               ("p", barcode), ("9", "99881"), ("0", "0"), ("1", "0"),
               ("4", "0"), ("7", "0"), ("x", "Internal note"),
               ("z", "Public note one"), ("z", "Public note two"))
    return record


def fields(record, tag):
    return [field for field in record.fields if field.tag == tag]


def options(**overrides):
    return {"branch": "CA", "itype": "BK", "barcode_policy": "review",
            "migration_id": "synthetic-fixture-v1", **overrides}


def test_native_952_all_values_and_input_are_preserved(api, registry):
    marc, normalize = api
    source = native(marc)
    original = source.formatted()
    result, report = normalize.normalize(source, options(), registry)
    assert result.formatted() == original
    assert source.formatted() == original
    assert result is not source
    assert report["items_existing"] == 1
    assert report["items_created"] == report["items_normalized"] == 0
    assert report["review"] == []


def test_explicit_branch_and_type_maps_change_only_requested_values(api, registry):
    marc, normalize = api
    source = native(marc)
    before = list(fields(source, "952")[0].subfields)
    result, report = normalize.normalize(source, options(branch_map={"MAIN": "CA"}, itype_map={"BK": "DVD"}), registry)
    expected = [(code, {"a": "CA", "b": "CA", "y": "DVD"}.get(code, value)) for code, value in before]
    assert fields(result, "952")[0].subfields == expected
    assert fields(source, "952")[0].subfields == before
    assert report["items_normalized"] == 1


def test_home_and_holding_branch_differences_are_preserved(api, registry):
    marc, normalize = api
    source = native(marc)
    item = fields(source, "952")[0]
    item.subfields = [(code, "CA" if code == "b" else value) for code, value in item.subfields]
    result, _ = normalize.normalize(source, options(), registry)
    assert fields(result, "952")[0].get("a") == "MAIN"
    assert fields(result, "952")[0].get("b") == "CA"


def test_invalid_explicit_target_is_blocked_and_original_retained(api, registry):
    marc, normalize = api
    source = native(marc)
    result, report = normalize.normalize(source, options(branch_map={"MAIN": "NOT-A-BRANCH"}), registry)
    assert fields(result, "952")[0].get("a") == "MAIN"
    assert report["review"]
    assert "NOT-A-BRANCH" in str(report["review"])


def test_unknown_native_branch_requires_review_or_explicit_remap(api, registry):
    marc, normalize = api
    source = native(marc)
    item = fields(source, "952")[0]
    item.subfields = [(code, "OLD" if code in ("a", "b") else value) for code, value in item.subfields]
    result, report = normalize.normalize(source, options(), registry)
    assert fields(result, "952")[0].get("a") == "OLD"
    assert report["review"]
    mapped, mapped_report = normalize.normalize(source, options(branch_map={"OLD": "CA"}), registry)
    assert fields(mapped, "952")[0].get("a") == fields(mapped, "952")[0].get("b") == "CA"
    assert not mapped_report["review"]


def test_native_items_and_descriptive_852_do_not_make_extra_items(api, registry):
    marc, normalize = api
    source = native(marc)
    source.add("852", " ", " ", ("a", "Obras Gerais"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") == 1
    assert result.count("852") == 1
    assert report["items_created"] == 0


def test_bn_legal_deposit_is_metadata_not_an_item(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("949", " ", " ", ("a", "1.395.407 DL 06/08/2013"))
    result, report = normalize.normalize(source, options(barcode_policy="generate"), registry)
    assert result.count("952") == 0
    assert fields(result, "949")[0].get("a") == "1.395.407 DL 06/08/2013"
    assert report["excluded_holdings"] == 1
    assert report["generated_barcodes"] == 0


def test_each_949_occurrence_judged_even_beside_existing_952(api, registry):
    marc, normalize = api
    source = native(marc)
    source.add("949", " ", " ", ("a", "1.395.407 DL 06/08/2013"))
    source.add("949", " ", " ", ("a", "Bib.2024.150"), ("y", "2025-03-25"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") == 2
    assert {field.get("p") for field in fields(result, "952")} == {"TEST-001", "Bib.2024.150"}
    assert report["items_existing"] == report["items_created"] == report["excluded_holdings"] == 1


def test_biblivre_date_and_donation_are_not_type_or_status(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("949", " ", " ", ("a", "SYN-150"), ("y", "2025-03-25"), ("c", "DOAÇÃO"))
    result, report = normalize.normalize(source, options(), registry)
    item = fields(result, "952")[0]
    assert item.get("p") == "SYN-150"
    assert item.get("d") == "2025-03-25"
    assert item.get("y") == "BK"
    assert item.get("a") == item.get("b") == "CA"
    assert not any(item.get(code) for code in ("0", "1", "4", "7"))
    assert "DOAÇÃO" in " ".join(value for _, value in item.subfields) or "DOAÇÃO" in str(report)


def test_mixed_949_and_real_852_are_both_normalized(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("949", " ", " ", ("a", "SYN-149"), ("y", "2025-03-24"))
    source.add("852", " ", " ", ("a", "CA"), ("p", "SYN-852"), ("h", "500"), ("i", "X99"))
    result, report = normalize.normalize(source, options(), registry)
    items = fields(result, "952")
    assert {item.get("p") for item in items} == {"SYN-149", "SYN-852"}
    assert next(item for item in items if item.get("p") == "SYN-852").get("o") == "500 X99"
    assert report["items_created"] == 2


def test_ambiguous_090_copy_numbers_are_not_zipped_by_occurrence(api, registry):
    marc, normalize = api
    source = rec(marc)
    fields(source, "090")[0].subfields.append(("d", "1"))
    source.add("090", " ", " ", ("a", "123.4"), ("b", "S123"), ("d", "2"))
    source.add("949", " ", " ", ("a", "SYN-B"), ("y", "2025-03-24"))
    source.add("949", " ", " ", ("a", "SYN-A"), ("y", "2025-03-24"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") == 2
    assert all(not item.get("t") for item in fields(result, "952"))
    assert report["review"]


def test_missing_barcode_defaults_to_review_without_fake_holdings(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("852", " ", " ", ("a", "CA"), ("t", "ex. 1"), ("h", "500"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") == 0
    assert report["review"]
    assert report["generated_barcodes"] == 0


def test_opt_in_barcode_generation_is_stable_and_does_not_mutate_registry(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("852", " ", " ", ("a", "CA"), ("t", "ex. 1"), ("h", "500"))
    opts = options(barcode_policy="generate")
    one, first = normalize.normalize(source, opts, registry)
    two, second = normalize.normalize(source, opts, registry)
    assert one.count("952") == two.count("952") == 1
    assert fields(one, "952")[0].get("p") == fields(two, "952")[0].get("p")
    assert first["generated_barcodes"] == second["generated_barcodes"] == 1
    assert registry["barcodes"] == set()


def test_barcode_collision_requires_review_not_silent_renumbering(api, registry):
    marc, normalize = api
    registry["barcodes"].add("SYN-DUP")
    source = rec(marc)
    source.add("949", " ", " ", ("a", "SYN-DUP"), ("y", "2025-03-24"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") == 0
    assert report["review"]
    assert "SYN-DUP" in str(report["review"])


def test_duplicate_legacy_barcodes_are_reported_within_record(api, registry):
    marc, normalize = api
    source = rec(marc)
    for _ in range(2):
        source.add("949", " ", " ", ("a", "SYN-DUP"), ("y", "2025-03-24"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") <= 1
    assert report["review"]


def test_ten_biblios_eighteen_items_synthetic_native_and_legacy(api, registry):
    marc, normalize = api
    counts = (1, 1, 1, 1, 2, 2, 2, 2, 2, 4)
    for mode in ("native", "legacy"):
        output = []
        for number, copies in enumerate(counts, 1):
            source = rec(marc, "SYN-%02d" % number)
            for copy in range(copies):
                barcode = "SYN-%02d-%02d" % (number, copy)
                if mode == "native":
                    source.add("952", " ", " ", ("a", "MAIN"), ("b", "MAIN"), ("y", "BK"), ("p", barcode))
                else:
                    source.add("949", " ", " ", ("a", barcode), ("y", "2025-03-24"))
            converted, _ = normalize.normalize(source, options(), registry)
            output.append(converted)
        assert len(output) == 10
        assert sum(record.count("952") for record in output) == 18


def test_pergamum_bibliographic_only_fixture_does_not_invent_items(api, registry):
    marc, normalize = api
    for number in range(10):
        result, report = normalize.normalize(rec(marc, "PERG-SYN-%02d" % number), options(barcode_policy="generate"), registry)
        assert result.count("952") == 0
        assert report["items_created"] == report["generated_barcodes"] == 0


def test_holding_branch_can_be_remapped_separately(api, registry):
    marc, normalize = api
    result, _ = normalize.normalize(native(marc), options(holding_branch_map={"MAIN": "CA"}), registry)
    item = fields(result, "952")[0]
    assert item.get("a") == "MAIN"
    assert item.get("b") == "CA"


def test_invalid_date_is_reviewed_not_used_as_barcode(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("949", " ", " ", ("a", "SYN-150"), ("y", "2025-02-30"))
    result, report = normalize.normalize(source, options(), registry)
    assert fields(result, "952")[0].get("p") == "SYN-150"
    assert not fields(result, "952")[0].get("d")
    assert any("date" in item["reason"].lower() for item in report["review"])
    assert fields(result, "949")[0].get("y") == "2025-02-30"


def test_cross_record_duplicates_use_source_registry_not_target_snapshot(api, registry):
    marc, normalize = api
    registry["source_seen"] = set()
    first, _ = normalize.normalize(native(marc, "FIRST", "SYN-SHARED"), options(), registry)
    source = rec(marc, "SECOND")
    source.add("949", " ", " ", ("a", "SYN-SHARED"), ("y", "2025-03-24"))
    second, report = normalize.normalize(source, options(), registry)
    assert first.count("952") == 1
    assert second.count("952") == 0
    assert "SYN-SHARED" in str(report["review"])
    assert registry["barcodes"] == set()


def test_source_internal_ids_are_removed_only_by_explicit_target_policy(api, registry):
    marc, normalize = api
    source = native(marc)
    source.add("999", " ", " ", ("c", "555"), ("d", "556"))
    ordinary, _ = normalize.normalize(source, options(), registry)
    assert fields(ordinary, "952")[0].get("9") == "99881"
    target, report = normalize.normalize(source, options(new_target_ids=True), registry)
    assert not fields(target, "952")[0].get("9")
    assert not fields(target, "999")
    assert fields(target, "001")[0].value == "SOURCE-1"
    assert {entry["value"] for entry in report["source_ids"]} == {"99881", "555", "556"}
    assert fields(source, "952")[0].get("9") == "99881"


def test_generated_barcode_target_collision_blocks_the_item(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("852", " ", " ", ("a", "CA"), ("t", "ex. 1"), ("h", "500"))
    opts = options(barcode_policy="generate")
    initial, _ = normalize.normalize(source, opts, registry)
    registry["barcodes"].add(fields(initial, "952")[0].get("p"))
    result, report = normalize.normalize(source, opts, registry)
    assert result.count("952") == 0
    assert report["generated_barcodes"] == 0
    assert report["review"]


def test_duplicate_native_and_legacy_values_with_conflicts_are_reviewed(api, registry):
    marc, normalize = api
    source = native(marc, barcode="SYN-SHARED")
    source.add("949", " ", " ", ("a", "SYN-SHARED"), ("y", "2025-03-25"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") == 1
    assert report["review"]


def test_real_local_inventory_is_not_discarded_because_a_note_mentions_deposit(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("949", " ", " ", ("p", "LOCAL-123"), ("b", "CA"), ("t", "BK"), ("z", "Depósito legal"))
    result, report = normalize.normalize(source, options(), registry)
    assert result.count("952") == 1
    assert fields(result, "952")[0].get("p") == "LOCAL-123"
    assert report["excluded_holdings"] == 0


@pytest.mark.parametrize("branch,mapping", [("CA", {}), ("LEGACY1", {"LEGACY1": "CA"})])
@pytest.mark.parametrize("copy_fields", [(), (("e", "1"), ("h", "456"))])
def test_local_949_a_barcode_survives_an_unrelated_deposit_note(api, registry, branch, mapping, copy_fields):
    marc, normalize = api
    source = rec(marc)
    source.add("949", " ", " ", ("a", "SYN-LOCAL-123"), ("b", branch),
               ("t", "BK"), ("z", "Depósito legal"), *copy_fields)
    original = source.formatted()
    result, report = normalize.normalize(source, options(branch_map=mapping), registry)
    assert result.count("952") == 1
    item = fields(result, "952")[0]
    assert item.get("p") == "SYN-LOCAL-123"
    assert item.get("a") == item.get("b") == "CA"
    assert report["excluded_holdings"] == 0
    assert not report["review"]
    assert source.formatted() == original


def test_native_callnumber_needs_no_selection_from_unrelated_bibliographic_numbers(api, registry):
    marc, normalize = api
    source = native(marc)
    source.add("090", " ", " ", ("a", "987.6"), ("b", "Z987"))
    original = source.formatted()
    result, report = normalize.normalize(source, options(), registry)
    assert result.formatted() == original
    assert not report["review"]


def test_legacy_explicit_callnumber_needs_no_bibliographic_selection(api, registry):
    marc, normalize = api
    source = rec(marc)
    source.add("090", " ", " ", ("a", "987.6"), ("b", "Z987"))
    source.add("949", " ", " ", ("a", "SYN-CALL-1"), ("h", "456.7 C456"))
    result, report = normalize.normalize(source, options(), registry)
    assert fields(result, "952")[0].get("o") == "456.7 C456"
    assert not report["review"]


def test_generator_distinguishes_records_in_one_source_file(api, registry):
    marc, normalize = api
    barcodes = []
    for control_id in ("BIB-1", "BIB-2"):
        source = rec(marc, control_id)
        source.add("852", " ", " ", ("a", "CA"), ("t", "ex. 1"), ("h", "500"))
        result, _ = normalize.normalize(source, options(barcode_policy="generate", source_id="one-export.mrc"), registry)
        barcodes.append(fields(result, "952")[0].get("p"))
    assert len(set(barcodes)) == 2
