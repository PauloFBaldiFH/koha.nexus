"""Synthetic contracts for the three-mode migration mapper.

The selectors identify source columns by opaque IDs. Saved profiles align
content and names; none of these tests rely on a column's ordinal position.
"""

import asyncio
import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.app import App
from textual.widgets import Checkbox, Input, Select

from conftest import INSTALLER
from kei_panel.screens.importmap import ImportMapScreen


pytestmark = pytest.mark.usefixtures("widget_event_loop")


@pytest.fixture(scope="module")
def mapping_engine(tmp_path_factory):
    root = tmp_path_factory.mktemp("importmap-engine")
    source = INSTALLER.read_text(encoding="utf-8")
    for match in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n', source, re.S):
        path = root / match.group(1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(match.group(2) + "\n", encoding="utf-8")
    return root


def document():
    return {
        "version": 2,
        "mode": "patrons",
        "targets_by_mode": {
            "bibliographic": [{"to": "245$a", "label": "Title"}, {"to": "952$p", "label": "Barcode"}],
            "patrons": [{"to": field, "label": field} for field in (
                "cardnumber", "surname", "email", "zipcode", "country", "preferred_name", "B_address",
                "dateenrolled", "branchcode", "categorycode", "password", "flags")],
            "authorities": [{"to": "100$a", "label": "Personal name"}, {"to": "942$a", "label": "Authority type"}],
        },
        "columns": [
            {"id": "opaque-email", "table_id": "readers", "table": "readers", "header": "E-mail",
             "mode": "patrons", "to": "email", "confidence": 0.98, "reasons": ["email format"],
             "values": ["one@example.invalid", "two@example.invalid", "three@example.invalid"]},
            {"id": "opaque-postcode", "table_id": "readers", "table": "readers", "header": "CEP",
             "mode": "patrons", "to": "zipcode", "confidence": 0.96, "reasons": ["postal code format"],
             "values": ["80000-000", "88000-000", "90000-000"]},
        ],
        "tables": [{"id": "readers", "name": "readers", "mode": "patrons", "headers": ["E-mail", "CEP"],
                    "columns": ["opaque-email", "opaque-postcode"], "rows": [
                        ["one@example.invalid", "80000-000"],
                        ["two@example.invalid", "88000-000"],
                        ["three@example.invalid", "90000-000"]]}],
        "streams": [],
        "mapping": {"version": 2, "mode": "patrons", "mappings": [
            {"source": "opaque-email", "to": "email", "mode": "patrons", "table": "readers"},
            {"source": "opaque-postcode", "to": "zipcode", "mode": "patrons", "table": "readers"}],
            "table_modes": {"readers": "patrons"}},
        "capabilities": {}, "relationships": [], "review": [], "context": {"options": {}},
    }


def screen_for(tmp_path, mapping_engine, data=None):
    path = tmp_path / "fields.json"
    path.write_text(json.dumps(data or document()), encoding="utf-8")
    return ImportMapScreen("Map migration fields", str(path), str(tmp_path / "mapping.json"), str(mapping_engine))


class Host(App):
    def __init__(self, screen):
        super().__init__()
        self.review_screen = screen
        self.result = None

    def on_mount(self):
        self.push_screen(self.review_screen, lambda result: setattr(self, "result", result))


def drive(screen, action):
    async def main():
        app = Host(screen)
        async with app.run_test(size=(150, 55)) as pilot:
            await pilot.pause()
            result = await action(screen, pilot)
            await pilot.pause()
            return app.result, result
    return asyncio.run(main())


def choices(screen, selector):
    return {value for _, value in screen.query_one(selector, Select)._options if isinstance(value, str)}


def test_mode_switcher_and_patron_destinations_use_schema_not_marc(tmp_path, mapping_engine):
    screen = screen_for(tmp_path, mapping_engine)

    async def check(screen, pilot):
        modes = choices(screen, "#im-mode")
        patrons = choices(screen, "#im-dest")
        screen.query_one("#im-mode", Select).value = "authorities"
        await pilot.pause()
        authorities = choices(screen, "#im-dest")
        screen.query_one("#im-mode", Select).value = "bibliographic"
        await pilot.pause()
        bibliography = choices(screen, "#im-dest")
        return modes, patrons, authorities, bibliography

    _, (modes, patrons, authorities, bibliography) = drive(screen, check)
    assert modes >= {"bibliographic", "patrons", "authorities"}
    assert patrons >= {"preferred_name", "B_address", "country", "dateenrolled"}
    assert not ({"password", "flags"} & patrons)
    assert "100$a" in authorities and "952$p" not in authorities
    assert "245$a" in bibliography


def test_mapping_writes_version_two_ids_defaults_and_remaps(tmp_path, mapping_engine):
    screen = screen_for(tmp_path, mapping_engine)

    async def change(screen, pilot):
        assert choices(screen, "#im-field") >= {"opaque-email", "opaque-postcode"}
        screen.query_one("#im-field", Select).value = "opaque-email"
        await pilot.pause()
        screen.query_one("#im-dest", Select).value = "email"
        screen.query_one("#im-branch", Input).value = "CA"
        screen.query_one("#im-category", Input).value = "PT"
        screen.query_one("#im-remaps", Input).value = json.dumps({"branchcode": {"MAIN": "CA"}})
        await pilot.pause()
        screen.query_one("#im-apply").press()

    result, _ = drive(screen, change)
    assert result is True
    saved = json.loads((tmp_path / "mapping.json").read_text())
    assert saved["version"] == 2
    assert {rule["source"] for rule in saved["mappings"]} >= {"opaque-email", "opaque-postcode"}
    assert saved["defaults"]["branchcode"] == "CA" and saved["defaults"]["categorycode"] == "PT"
    assert saved["remaps"] == {"branchcode": {"MAIN": "CA"}}


def test_preview_calls_shared_backend_with_current_mapping(tmp_path, mapping_engine):
    screen = screen_for(tmp_path, mapping_engine)
    calls = []

    def preview(doc, spec):
        calls.append((doc, spec.to_obj()))
        return {"groups": [{"id": "readers", "mode": "patrons", "records": [
            {"email": "[redacted]"}, {"email": "[redacted]"}, {"email": "[redacted]"}], "issues": []}], "issues": []}

    screen.backend = SimpleNamespace(preview_document=preview)

    async def check(screen, pilot):
        screen.query_one("#im-field", Select).value = "opaque-postcode"
        await pilot.pause()
        screen.query_one("#im-dest", Select).value = "country"
        await pilot.pause()
        return screen.preview()

    _, previewed = drive(screen, check)
    assert len(previewed["groups"][0]["records"]) == 3
    assert calls[-1][0]["version"] == 2
    assert next(rule for rule in calls[-1][1]["mappings"] if rule["source"] == "opaque-postcode")["to"] == "country"


def test_groups_keep_independent_modes_and_identical_headers_use_distinct_ids(tmp_path, mapping_engine):
    data = document()
    data["columns"].append({"id": "books-name", "table_id": "books", "table": "books", "header": "E-mail",
                            "values": ["Synthetic heading"], "mode": "bibliographic", "to": "245$a"})
    data["tables"].append({"id": "books", "name": "books", "mode": "bibliographic", "headers": ["E-mail"],
                            "columns": ["books-name"], "rows": [["Synthetic heading"]]})
    data["mapping"]["mappings"].append({"source": "books-name", "to": "245$a", "mode": "bibliographic", "table": "books"})
    data["mapping"]["table_modes"]["books"] = "bibliographic"
    screen = screen_for(tmp_path, mapping_engine, data)

    async def change(screen, pilot):
        screen.query_one("#im-group", Select).value = "books"
        await pilot.pause()
        assert choices(screen, "#im-field") >= {"books-name"}
        screen.query_one("#im-mode", Select).value = "authorities"
        await pilot.pause()
        screen.query_one("#im-dest", Select).value = "100$a"
        await pilot.pause()
        return screen.mapping()

    _, mapped = drive(screen, change)
    assert mapped["table_modes"]["books"] == "authorities"
    assert mapped["table_modes"]["readers"] == "patrons"
    assert {rule["source"]: rule["to"] for rule in mapped["mappings"]}["opaque-email"] == "email"


def test_saved_profile_follows_shuffled_names_and_content(tmp_path, mapping_engine):
    original = screen_for(tmp_path, mapping_engine)
    profile = tmp_path / "migration-profile.json"

    async def save(screen, pilot):
        screen.save_profile(str(profile))

    drive(original, save)
    serialized = profile.read_text()
    assert "one@example.invalid" not in serialized and "80000-000" not in serialized
    changed = document()
    changed["columns"] = list(reversed(changed["columns"]))
    changed["tables"][0]["columns"] = ["new-postcode", "new-email"]
    changed["tables"][0]["headers"] = ["CEP", "E-mail"]
    changed["tables"][0]["rows"] = [["90000-000", "new@example.invalid"]]
    changed["columns"][0].update(id="new-postcode", values=["90000-000", "91000-000"])
    changed["columns"][1].update(id="new-email", values=["new@example.invalid", "next@example.invalid"])
    changed["mapping"]["mappings"] = []
    current = screen_for(tmp_path, mapping_engine, changed)

    async def load(screen, pilot):
        aligned = screen.load_profile(str(profile))
        return aligned, screen.mapping()

    _, (aligned, mapped) = drive(current, load)
    assert aligned["bindings"] == {"opaque-email": "new-email", "opaque-postcode": "new-postcode"}
    assert {rule["source"]: rule["to"] for rule in mapped["mappings"]} == {"new-email": "email", "new-postcode": "zipcode"}


def test_profile_ambiguous_content_requires_review_instead_of_column_order(tmp_path, mapping_engine):
    source = document()
    source["columns"] = [{"id": "old-date", "table_id": "readers", "table": "readers", "header": "",
                          "values": ["2000-01-01", "2001-01-01"], "mode": "patrons", "to": "dateenrolled"}]
    source["tables"][0].update(headers=[""], columns=["old-date"], rows=[["2000-01-01"], ["2001-01-01"]])
    source["mapping"]["mappings"] = [{"source": "old-date", "to": "dateenrolled", "mode": "patrons"}]
    original = screen_for(tmp_path, mapping_engine, source)
    profile = tmp_path / "ambiguous-profile.json"

    async def save(screen, pilot):
        screen.save_profile(str(profile))

    drive(original, save)
    current = copy.deepcopy(source)
    current["columns"] = [dict(source["columns"][0], id="candidate-a"), dict(source["columns"][0], id="candidate-b")]
    current["tables"][0].update(headers=["", ""], columns=["candidate-a", "candidate-b"], rows=[["2000-01-01", "2000-01-01"]])
    current["mapping"]["mappings"] = []
    screen = screen_for(tmp_path, mapping_engine, current)

    async def load(screen, pilot):
        return screen.load_profile(str(profile))

    _, aligned = drive(screen, load)
    assert aligned["bindings"] == {} and aligned["ambiguous"] == ["old-date"]


def test_v2_fieldmap_protocol_dispatches_to_new_mapper(tmp_path, mapping_engine):
    from kei_panel.routines.common import asker
    from kei_panel.bridge import TaskOutcome

    path = tmp_path / "fields.json"
    path.write_text(json.dumps(document()))
    asked = []

    class App:
        async def push_screen_wait(self, screen):
            asked.append(screen)
            return False

    result = asyncio.run(asker(App())(TaskOutcome(0), "fieldmap", "Map", "",
                                     (str(path), str(tmp_path / "out.json"), str(mapping_engine))))
    assert result is False and isinstance(asked[0], ImportMapScreen)


def test_profile_rebinds_across_filenames_using_logical_table_key(tmp_path, mapping_engine):
    original_data = document()
    original_data['tables'][0].update(id='first-file:readers', name='first-export.sql:readers', table_key='readers')
    for column in original_data['columns']:
        column.update(table_id='first-file:readers', table='first-export.sql:readers', table_key='readers')
    original_data['mapping']['table_modes'] = {'first-file:readers': 'patrons'}
    original = screen_for(tmp_path, mapping_engine, original_data)
    profile = tmp_path / 'different-filename-profile.json'

    async def save(screen, pilot):
        screen.save_profile(str(profile))

    drive(original, save)
    current_data = document()
    current_data['tables'][0].update(id='second-file:readers', name='next-export.sql:readers',
        table_key='readers', columns=['fresh-email', 'fresh-postcode'])
    current_data['mapping']['mappings'] = []
    current_data['mapping']['table_modes'] = {'second-file:readers': 'patrons'}
    for column, new_id in zip(current_data['columns'], ['fresh-email', 'fresh-postcode']):
        column.update(id=new_id, table_id='second-file:readers', table='next-export.sql:readers', table_key='readers')
    current = screen_for(tmp_path, mapping_engine, current_data)

    async def load(screen, pilot):
        return screen.load_profile(str(profile))

    _, aligned = drive(current, load)
    assert aligned['bindings'] == {'opaque-email': 'fresh-email', 'opaque-postcode': 'fresh-postcode'}
    assert not aligned['ambiguous'] and not aligned['missing']


def test_mixed_marc_groups_share_override_by_base_source_id(tmp_path, mapping_engine):
    data = document()
    data.update(mode='bibliographic', columns=[], tables=[], streams=[
        {'id': 'base:bibliographic', 'source_id': 'base-source', 'name': 'Synthetic MARC bibliographic',
         'mode': 'bibliographic', 'fields': [{'id': 'opaque-title', 'ref': '245$a', 'to': '245$a', 'values': ['Synthetic title']}], 'records': []},
        {'id': 'base:authorities', 'source_id': 'base-source', 'name': 'Synthetic MARC authorities',
         'mode': 'authorities', 'fields': [{'id': 'opaque-heading', 'ref': '100$a', 'to': '100$a', 'values': ['Synthetic heading']}], 'records': []},
    ], mapping={'version': 2, 'mode': 'bibliographic', 'mappings': [], 'source_modes': {}})
    screen = screen_for(tmp_path, mapping_engine, data)

    async def change(screen, pilot):
        screen.query_one('#im-group', Select).value = 'base:bibliographic'
        await pilot.pause()
        screen.query_one('#im-mode', Select).value = 'authorities'
        await pilot.pause()
        return screen.mapping()

    _, mapped = drive(screen, change)
    assert mapped['source_modes'] == {'base-source': 'authorities'}
    assert {rule['mode'] for rule in mapped['mappings']} == {'authorities'}
    assert {rule['source_id'] for rule in mapped['mappings']} == {'base-source'}


def test_sensitive_fields_need_explicit_review_and_literals_cannot_be_saved(tmp_path, mapping_engine):
    screen = screen_for(tmp_path, mapping_engine)

    async def review(screen, pilot):
        assert 'password' not in choices(screen, '#im-dest')
        screen.query_one('#im-sensitive', Checkbox).value = True
        await pilot.pause()
        assert {'password', 'flags'} <= choices(screen, '#im-dest')
        screen.query_one('#im-dest', Select).value = 'password'
        await pilot.pause()
        explicit = screen.mapping()
        screen.query_one('#im-dest', Select).value = 'fixed'
        await pilot.pause()
        screen.query_one('#im-custom', Input).value = 'password'
        screen.query_one('#im-fixed', Input).value = 'synthetic-secret-not-real'
        await pilot.pause()
        with pytest.raises(ValueError, match='Sensitive'):
            screen.save_profile(str(tmp_path / 'sensitive-profile.json'))
        return explicit

    _, explicit = drive(screen, review)
    assert explicit['allow_restricted'] is True
    assert any(rule['to'] == 'password' for rule in explicit['mappings'])
    assert not (tmp_path / 'sensitive-profile.json').exists()


def test_mount_preserves_initial_name_transform(tmp_path, mapping_engine):
    data = document()
    data['mapping']['mappings'][0].update(to='surname', transform='split_name')
    screen = screen_for(tmp_path, mapping_engine, data)

    async def inspect(screen, pilot):
        await pilot.pause()
        before = screen.mapping()
        screen.query_one('#im-field', Select).value = 'opaque-postcode'
        await pilot.pause()
        screen.query_one('#im-field', Select).value = 'opaque-email'
        await pilot.pause()
        return before, screen.mapping()

    _, (before, after) = drive(screen, inspect)
    for mapped in (before, after):
        rule = next(rule for rule in mapped['mappings'] if rule['source'] == 'opaque-email')
        assert rule['to'] == 'surname' and rule['transform'] == 'split_name'
