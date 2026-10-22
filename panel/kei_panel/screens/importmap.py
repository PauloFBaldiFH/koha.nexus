"""Three-domain import review over the engine's version 2 draft document.

Source IDs are opaque and scoped to their table or MARC stream. All preview
and profile transformations use the extracted import engine; this screen
does not implement a second importer or infer fields from their positions.
"""
from __future__ import annotations

import asyncio
import copy
import importlib
import json
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select, Static

from ..i18n import t
from .fieldmap import load_engine, read_fields

MODES = ('bibliographic', 'patrons', 'authorities')
MODE_LABELS = {'auto': 'Automatic detection', 'bibliographic': 'Bibliographic',
               'patrons': 'Patrons', 'authorities': 'Authorities'}
CUSTOM, FIXED, IGNORE = 'custom', 'fixed', 'ignore'


class ImportMapScreen(ModalScreen[bool]):
    BINDINGS = [Binding('escape', 'skip', t('Skip: import as it is')),
                Binding('ctrl+s', 'apply', t('Apply'))]

    def __init__(self, title: str, fields_path: str, out_path: str, engine_dir: str = ''):
        super().__init__()
        self._title, self._out = title, out_path
        self.data = read_fields(fields_path)
        self.mapper = self.backend = None
        if load_engine(engine_dir) is not None:
            try:
                self.mapper = importlib.import_module('kei_import.mapping')
                self.backend = importlib.import_module('kei_import.review')
            except ImportError:
                pass
        self.base = copy.deepcopy(self.data.get('mapping') or {})
        self.allow_restricted = self.base.get('allow_restricted') is True
        self.rows, self.groups, self.modes = {}, {}, {}
        self._syncing = False
        self._preview_serial = 0
        self._preview_timer = None
        self._preview_lock = asyncio.Lock()
        self._build()
        self.group_id = next(iter(self.groups), '')
        self.field_id = next(iter(self.groups.get(self.group_id, {}).get('columns', [])), '')
        defaults = self.base.get('defaults', {})
        self.branch = str(defaults.get('branchcode', defaults.get('952$a', '')))
        self.category = str(defaults.get('categorycode', ''))
        self.itype = str(defaults.get('952$y', defaults.get('942$c', '')))
        self.remaps = copy.deepcopy(self.base.get('remaps', {}))

    def _build(self):
        by_id = {column['id']: column for column in self.data.get('columns', [])}
        for kind in ('tables', 'streams'):
            for group in self.data.get(kind, []):
                gid = group['id']
                mode = group.get('mode', self.data.get('mode', 'bibliographic'))
                if mode not in MODES:
                    mode = 'bibliographic'
                ids = []
                if kind == 'tables':
                    fields = [by_id[key] for key in group.get('columns', []) if key in by_id]
                    # A draft can carry column objects directly as well.
                    if not fields:
                        fields = [column for column in by_id.values() if column.get('table_id') == gid]
                else:
                    fields = group.get('fields', [])
                for source in fields:
                    sid = source['id']
                    ids.append(sid)
                    row = copy.deepcopy(source)
                    row.update({'id': sid, 'group': gid, 'kind': kind,
                                'table_key': ('marc:' + mode) if kind == 'streams' else
                                             source.get('table_key', group.get('table_key', group.get('name', ''))),
                                'header': source.get('header', source.get('ref', sid)),
                                'ref': source.get('ref', source.get('from', '')),
                                'to': source.get('to') or (source.get('ref') if kind == 'streams' else IGNORE),
                                'function': 'field', 'fixed': ''})
                    self.rows[sid] = row
                self.groups[gid] = {'id': gid, 'name': group.get('name', gid),
                                    'source_id': group.get('source_id', gid),
                                    'mode': mode, 'kind': kind, 'columns': ids}
                overrides = self.base.get('table_modes' if kind == 'tables' else 'source_modes', {})
                self.modes[gid] = overrides.get(group.get('source_id', gid) if kind == 'streams' else gid, 'auto')
        for rule in self.base.get('mappings', []):
            sid = rule.get('source', rule.get('from'))
            if sid in self.rows:
                self.rows[sid]['to'] = rule.get('to') or IGNORE
                self.rows[sid]['rule'] = copy.deepcopy(rule)
                if 'value' in rule:
                    self.rows[sid].update(function=FIXED, fixed=str(rule['value']))

    def effective_mode(self, gid=None):
        gid = self.group_id if gid is None else gid
        selected = self.modes.get(gid, 'auto')
        return self.groups.get(gid, {}).get('mode', 'bibliographic') if selected == 'auto' else selected

    def targets(self, mode=None):
        mode = mode or self.effective_mode()
        offered = self.data.get('targets_by_mode', {}).get(mode, [])
        if mode == 'patrons' and self.mapper:
            supported = self.data.get('capabilities', {}).get('patron_fields')
            offered = [{'to': key, 'label': key} for key in self.mapper.PATRON_FIELDS
                       if supported is None or key in supported]
        elif mode == 'authorities' and not offered and self.mapper:
            offered = [{'to': key, 'label': key} for key in self.mapper.AUTHORITY_TARGETS]
        restricted = self.mapper.RESTRICTED_FIELDS if self.mapper else set()
        result = []
        for item in offered:
            key = item.get('to', item.get('value')) if isinstance(item, dict) else item
            label = item.get('label', key) if isinstance(item, dict) else key
            if key and not (mode == 'patrons' and key in restricted and not self.allow_restricted):
                result.append((f'{key} · {t(label)}' if label != key else key, key))
        return result

    def _valid_target(self, target, mode):
        if target == IGNORE:
            return True
        if self.mapper:
            try:
                self.mapper.MappingSpec.from_obj({'version': 2, 'mode': mode,
                    'allow_restricted': self.allow_restricted,
                    'mappings': [{'source': 'validation', 'to': target}]})
                supported = self.data.get('capabilities', {}).get('patron_fields')
                return mode != 'patrons' or supported is None or target in supported
            except ValueError:
                return False
        return target in {value for _, value in self.targets(mode)}

    def mapping(self):
        """The exact version 2 spec used for preview and the next build."""
        obj = copy.deepcopy(self.base)
        obj.update({'version': 2, 'mode': self.base.get('mode', self.data.get('mode', 'bibliographic')),
                    'mappings': [], 'table_modes': {}, 'source_modes': {}})
        if obj['mode'] not in MODES:
            obj['mode'] = 'bibliographic'
        if self.allow_restricted:
            obj['allow_restricted'] = True
        else:
            obj.pop('allow_restricted', None)
        for gid, group in self.groups.items():
            mode = self.effective_mode(gid)
            mode_key = gid if group['kind'] == 'tables' else group['source_id']
            obj['table_modes' if group['kind'] == 'tables' else 'source_modes'][mode_key] = self.modes[gid]
            for sid in group['columns']:
                row = self.rows[sid]
                rule = copy.deepcopy(row.get('rule', {}))
                rule.update(source=sid, to=row['to'], mode=mode, table=gid)
                if row['kind'] == 'streams':
                    rule.update(ref=row['ref'], source_id=group['source_id'])
                if row['function'] == FIXED:
                    rule['value'] = row['fixed']
                else:
                    rule.pop('value', None)
                obj['mappings'].append(rule)
        defaults = copy.deepcopy(self.base.get('defaults', {}))
        modes = {self.effective_mode(gid) for gid in self.groups}
        for target in ('branchcode', 'categorycode', '952$a', '952$b', '952$y', '942$c'):
            defaults.pop(target, None)
        if 'patrons' in modes:
            if self.branch:
                defaults['branchcode'] = self.branch
            if self.category:
                defaults['categorycode'] = self.category
        if 'bibliographic' in modes:
            if self.branch:
                defaults.update({'952$a': self.branch, '952$b': self.branch})
            if self.itype:
                defaults.update({'952$y': self.itype, '942$c': self.itype})
        obj.update(defaults=defaults, remaps=copy.deepcopy(self.remaps))
        for key in ('options', 'relationships', 'capabilities', 'barcode_policy', 'migration_id'):
            if key in self.base:
                obj[key] = copy.deepcopy(self.base[key])
        return obj

    def _profile_columns(self):
        return [dict(row, table=row.get('table_key', '')) for row in self.rows.values()]

    def save_profile(self, path):
        if not self.mapper:
            raise ValueError(t('The import engine is unavailable.'))
        profile = self.mapper.make_profile(self.mapping(), self._profile_columns())
        Path(path).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return profile

    def load_profile(self, path):
        if not self.mapper:
            raise ValueError(t('The import engine is unavailable.'))
        profile = json.loads(Path(path).read_text(encoding='utf-8'))
        alignment = self.mapper.align_profile(profile, self._profile_columns())
        saved = self.mapper.MappingSpec.from_obj(profile['mapping']).to_obj()
        for rule in saved['mappings']:
            old = rule.get('source', rule.get('from'))
            sid = alignment['bindings'].get(old)
            if sid is None:
                continue
            row = self.rows[sid]
            mode = rule.get('mode', saved['mode'])
            if mode in MODES:
                self.modes[row['group']] = mode
            row['rule'] = copy.deepcopy(rule)
            row['to'] = rule['to']
            row['function'] = FIXED if 'value' in rule else 'field'
            row['fixed'] = str(rule.get('value', ''))
        self.base.update({key: copy.deepcopy(saved[key]) for key in
                          ('defaults', 'remaps', 'options', 'barcode_policy') if key in saved})
        defaults = saved.get('defaults', {})
        self.branch = str(defaults.get('branchcode', defaults.get('952$a', '')))
        self.category = str(defaults.get('categorycode', ''))
        self.itype = str(defaults.get('952$y', defaults.get('942$c', '')))
        self.remaps = copy.deepcopy(saved.get('remaps', {}))
        if self.is_mounted:
            self._syncing = True
            for key, value in (('branch', self.branch), ('category', self.category), ('itype', self.itype)):
                self.query_one(f'#im-{key}', Input).value = value
            self.query_one('#im-remaps', Input).value = json.dumps(self.remaps, ensure_ascii=False)
            self._syncing = False
            self._refresh_group()
            self._status(t('Profile loaded. Ambiguous: ${a}; missing: ${m}. Review these fields before applying.',
                           a=len(alignment['ambiguous']), m=len(alignment['missing'])))
            self._schedule_preview()
        return alignment

    def preview(self):
        if not self.mapper or not self.backend:
            raise ValueError(t('The import engine is unavailable.'))
        spec = self.mapper.MappingSpec.from_obj(self.mapping())
        return self.backend.preview_document(self.data, spec)

    def compose(self) -> ComposeResult:
        with Vertical(classes='dialog importmap'):
            yield Label(self._title, classes='dialog-title', markup=False)
            with Horizontal(classes='im-line'):
                yield Select([(group['name'] + ' · ' + t(MODE_LABELS[group['mode']]), gid)
                              for gid, group in self.groups.items()],
                             value=self.group_id or Select.NULL, allow_blank=not bool(self.groups), id='im-group')
                yield Label(t('Import mode'), classes='im-key')
                yield Select([(t(label), mode) for mode, label in MODE_LABELS.items()],
                             value=self.modes.get(self.group_id, 'auto'), allow_blank=False, id='im-mode')
            with VerticalScroll(id='im-scroll'):
                yield DataTable(id='im-grid', cursor_type='row', zebra_stripes=True)
                yield Static('', id='im-reasons', markup=False)
                with Horizontal(classes='im-line'):
                    yield Label(t('Select field'), classes='im-key')
                    yield Select([], id='im-field')
                    yield Label(t('Function'), classes='im-key')
                    yield Select([(t('Leave out'), IGNORE)], value=IGNORE, allow_blank=False, id='im-dest')
                with Horizontal(classes='im-line'):
                    yield Input(placeholder=t('Destination field or TAG$subfield'), id='im-custom')
                    yield Input(placeholder=t('Fixed text for this field'), id='im-fixed')
                with Horizontal(classes='im-line'):
                    yield Label(t('Transform'), classes='im-key')
                    yield Select([(t('Keep the value'), 'none'), (t('Split full name'), 'split_name'),
                                  (t('Add a prefix'), 'prefix')], value='none', allow_blank=False, id='im-transform')
                    yield Input(placeholder=t('Prefix, for example CPF:'), id='im-prefix')
                yield Static(t('Sensitive fields require explicit review. Source password hashes cannot be imported as passwords.'),
                             id='im-restricted', markup=False)
                yield Checkbox(t('Review sensitive patron fields'), value=self.allow_restricted, id='im-sensitive')
                yield Label(t('Fill missing values for this migration'), classes='im-section')
                with Horizontal(classes='im-line'):
                    yield Input(self.branch, placeholder=t('Default branch'), id='im-branch')
                    yield Input(self.category, placeholder=t('Default patron category'), id='im-category')
                    yield Input(self.itype, placeholder=t('Default item type'), id='im-itype')
                yield Input(json.dumps(self.remaps, ensure_ascii=False),
                            placeholder=t('Code remaps as JSON, for example {"branchcode":{"MAIN":"CA"}}'), id='im-remaps')
                yield Label(t('Relationships between bibliographic records and items'), classes='im-section')
                yield Static(t('Review the proposals, then enter only confirmed relationships below. No proposal is selected automatically.'),
                             markup=False)
                yield Static(json.dumps(self.data.get('relationships', []), ensure_ascii=False, indent=2),
                             id='im-relationship-proposals', markup=False)
                yield Input(json.dumps(self.base.get('relationships', []), ensure_ascii=False),
                            placeholder=t('Confirmed relationships as a JSON list'), id='im-relationships')
                with Horizontal(classes='im-line'):
                    yield Label(t('Missing barcodes'), classes='im-key')
                    yield Select([(t('Review before importing'), 'review'),
                                  (t('Generate stable migration barcodes'), 'generate')],
                                 value=self.base.get('barcode_policy', 'review'), allow_blank=False, id='im-barcodes')
                yield Label(t('Reusable mapping profile'), classes='im-section')
                with Horizontal(classes='im-line'):
                    yield Input(placeholder=t('Mapping profile file path'), id='im-profile')
                    yield Button(t('Save profile'), id='im-save-profile')
                    yield Button(t('Load profile'), id='im-load-profile')
                yield Label(t('Live preview · first 3 mapped records'), classes='im-section')
                yield Static('', id='im-sample', markup=False)
                yield Static('', id='im-status', markup=False)
            with Horizontal(classes='dialog-buttons'):
                yield Button(t('Refresh preview'), id='im-preview')
                yield Button(t('Skip: import as it is'), id='im-skip')
                yield Button(t('Apply mapping'), variant='primary', id='im-apply')

    def on_mount(self):
        self.query_one('#im-grid', DataTable).add_columns(t('Source field'), t('Destination'),
                                                        t('Confidence'), t('Sample values'))
        self._refresh_group()
        self._schedule_preview()

    def _status(self, message):
        self.query_one('#im-status', Static).update(message)

    def _refresh_group(self):
        self._syncing = True
        group = self.groups.get(self.group_id, {'columns': []})
        self.query_one('#im-mode', Select).value = self.modes.get(self.group_id, 'auto')
        fields = [(self.rows[sid]['header'] or t('Unnamed field'), sid) for sid in group['columns']]
        selector = self.query_one('#im-field', Select)
        selector.set_options(fields)
        if self.field_id not in group['columns']:
            self.field_id = next(iter(group['columns']), '')
        selector.value = self.field_id or Select.NULL
        grid = self.query_one('#im-grid', DataTable)
        grid.clear()
        for sid in group['columns']:
            row = self.rows[sid]
            values = row.get('values', row.get('samples', []))[:3]
            confidence = row.get('confidence', row.get('score', 0))
            try:
                confidence = f'{float(confidence):.0%}'
            except (ValueError, TypeError):
                confidence = str(confidence)
            grid.add_row(row['header'] or t('Unnamed field'), row['to'], confidence,
                         ' | '.join(str(value)[:50] for value in values), key=sid)
        self._syncing = False
        self._refresh_field()

    def _refresh_field(self):
        self._syncing = True
        row = self.rows.get(self.field_id)
        options = [(t('Leave out'), IGNORE)] + self.targets() + [(t('Custom destination'), CUSTOM),
                                                               (t('Fixed text'), FIXED)]
        selector = self.query_one('#im-dest', Select)
        selector.set_options(options)
        if row:
            listed = {value for _, value in options}
            selector.value = FIXED if row['function'] == FIXED else row['to'] if row['to'] in listed else CUSTOM
            self.query_one('#im-custom', Input).value = row['to'] if row['to'] != IGNORE else ''
            self.query_one('#im-fixed', Input).value = row['fixed']
            with self.prevent(Select.Changed, Input.Changed):
                transform = row.get('rule', {}).get('transform', 'none')
                self.query_one('#im-transform', Select).value = transform
                self.query_one('#im-prefix', Input).value = row.get('rule', {}).get('prefix', '')
            self.query_one('#im-prefix', Input).display = transform == 'prefix'
            reasons = row.get('reasons', [])
            flags = row.get('flags', [])
            if isinstance(reasons, str):
                reasons = [reasons]
            if isinstance(flags, str):
                flags = [flags]
            self.query_one('#im-reasons', Static).update('\n'.join(str(value) for value in reasons + flags))
        self.query_one('#im-custom', Input).display = bool(row and selector.value in (CUSTOM, FIXED))
        self.query_one('#im-fixed', Input).display = bool(row and selector.value == FIXED)
        self._syncing = False

    @on(Select.Changed, '#im-group')
    def _group_changed(self, event):
        if not self._syncing and event.value == event.select.value and event.value in self.groups:
            self.group_id = event.value
            self._refresh_group()

    @on(Select.Changed, '#im-mode')
    def _mode_changed(self, event):
        if self._syncing or event.value != event.select.value or event.value not in MODE_LABELS:
            return
        if self.modes.get(self.group_id) == event.value:
            return
        self.modes[self.group_id] = event.value
        selected = self.groups[self.group_id]
        affected = [self.group_id]
        if selected['kind'] == 'streams':
            affected = [gid for gid, group in self.groups.items() if group['kind'] == 'streams'
                        and group['source_id'] == selected['source_id']]
        for gid in affected:
            self.modes[gid] = event.value
            mode = self.effective_mode(gid)
            for sid in self.groups[gid]['columns']:
                row = self.rows[sid]
                if not self._valid_target(row['to'], mode):
                    row['to'], row['function'] = IGNORE, 'field'
                if row.get('rule', {}).get('transform') == 'split_name' and mode != 'patrons':
                    row['rule'].pop('transform', None)
        self._refresh_group()
        self._status(t('Mode changed. Review the proposed destinations before applying.'))
        self._schedule_preview()

    @on(Select.Changed, '#im-field')
    def _field_changed(self, event):
        group_ids = self.groups.get(self.group_id, {}).get('columns', [])
        if not self._syncing and event.value == event.select.value and event.value in group_ids and event.value != self.field_id:
            self.field_id = event.value
            self._refresh_field()

    @on(DataTable.RowHighlighted, '#im-grid')
    def _row_highlighted(self, event):
        sid = event.row_key.value
        if not self._syncing and sid in self.groups.get(self.group_id, {}).get('columns', []) and sid != self.field_id:
            self.field_id = sid
            self.query_one('#im-field', Select).value = sid
            self._refresh_field()

    @on(Select.Changed, '#im-dest')
    def _destination_changed(self, event):
        if self._syncing or event.value != event.select.value or self.field_id not in self.rows:
            return
        row = self.rows[self.field_id]
        if (event.value in (CUSTOM, FIXED) and row['function'] == event.value) or \
                (event.value == row['to'] and row['function'] == 'field'):
            return
        if event.value in (CUSTOM, FIXED):
            row['function'] = event.value
        elif isinstance(event.value, str):
            changed = row['to'] != event.value
            row['to'], row['function'] = event.value, 'field'
            if changed:
                row.get('rule', {}).pop('transform', None)
        self._refresh_field()
        self._schedule_preview()

    @on(Input.Changed)
    def _input_changed(self, event):
        if self._syncing or event.value != event.input.value:
            return
        key = event.input.id
        row = self.rows.get(self.field_id)
        if key == 'im-custom' and row:
            changed = row['to'] != (event.value or IGNORE)
            row['to'] = event.value or IGNORE
            if changed:
                row.get('rule', {}).pop('transform', None)
        elif key == 'im-fixed' and row:
            row['fixed'] = event.value
        elif key == 'im-prefix' and row:
            row.setdefault('rule', {})['prefix'] = event.value
        elif key in ('im-branch', 'im-category', 'im-itype'):
            setattr(self, key[3:], event.value.strip())
        elif key == 'im-remaps':
            try:
                parsed = json.loads(event.value or '{}')
                if not isinstance(parsed, dict):
                    raise ValueError()
                self.remaps = parsed
            except ValueError:
                self._status(t('Code remaps must be a JSON object.'))
                return
        elif key == 'im-relationships':
            try:
                parsed = json.loads(event.value or '[]')
                if not isinstance(parsed, list) or any(not isinstance(item, dict) for item in parsed):
                    raise ValueError()
                self.base['relationships'] = parsed
            except ValueError:
                self._status(t('Confirmed relationships must be a JSON list.'))
                return
        else:
            return
        self._schedule_preview()

    @on(Select.Changed, '#im-barcodes')
    def _barcodes_changed(self, event):
        if not self._syncing and event.value == event.select.value and event.value in ('review', 'generate'):
            self.base['barcode_policy'] = event.value
            self._schedule_preview()

    @on(Select.Changed, '#im-transform')
    def _transform_changed(self, event):
        if self._syncing or event.value != event.select.value or self.field_id not in self.rows:
            return
        rule = self.rows[self.field_id].setdefault('rule', {})
        if event.value == 'none':
            rule.pop('transform', None)
            rule.pop('prefix', None)
        elif event.value in ('split_name', 'prefix'):
            rule['transform'] = event.value
        self.query_one('#im-prefix', Input).display = event.value == 'prefix'
        self._schedule_preview()

    @on(Checkbox.Changed, '#im-sensitive')
    def _sensitive_changed(self, event):
        if self._syncing:
            return
        self.allow_restricted = event.value
        if not event.value and self.mapper:
            for row in self.rows.values():
                if row['to'] in self.mapper.RESTRICTED_FIELDS:
                    row['to'], row['function'] = IGNORE, 'field'
        self._refresh_field()
        self._schedule_preview()

    def _schedule_preview(self):
        self._preview_serial += 1
        if self._preview_timer:
            self._preview_timer.stop()
        self._preview_timer = self.set_timer(.25, self._show_preview)

    async def _show_preview(self):
        self._preview_serial += 1
        serial = self._preview_serial
        try:
            async with self._preview_lock:
                if serial != self._preview_serial or not self.is_mounted:
                    return
                if not self.mapper or not self.backend:
                    raise ValueError(t('The import engine is unavailable.'))
                # Capture choices on the UI thread; one full-file preview
                # worker prevents rapid edits from piling up large builds.
                spec = self.mapper.MappingSpec.from_obj(self.mapping())
                result = await asyncio.to_thread(self.backend.preview_document, self.data, spec)
            if serial != self._preview_serial or not self.is_mounted:
                return
            lines = []
            issues = list(result.get('issues', []))
            for group in result.get('groups', []):
                lines.append(str(group.get('name', group.get('id', ''))))
                for record in group.get('records', [])[:3]:
                    lines.append(json.dumps(record, ensure_ascii=False, indent=2) if isinstance(record, dict) else str(record))
                issues.extend(group.get('issues', []))
            if issues:
                lines.append(t('Validation flags'))
                lines.extend(t('Row ${row}: ${message}', row=issue.get('row', ''),
                               message=t(issue.get('message', issue.get('code', '')))) for issue in issues)
            self.query_one('#im-sample', Static).update('\n\n'.join(lines) or t('No preview records.'))
        except Exception as error:  # noqa: BLE001 - a draft must remain editable
            if self.is_mounted and serial == self._preview_serial:
                self._status(t('Preview could not be prepared: ${error}', error=str(error)))

    @on(Button.Pressed, '#im-preview')
    async def _preview_pressed(self):
        await self._show_preview()

    @on(Button.Pressed, '#im-save-profile')
    def _save_pressed(self):
        try:
            self.save_profile(self.query_one('#im-profile', Input).value)
            self._status(t('Mapping profile saved. Source values were not stored.'))
        except Exception as error:  # noqa: BLE001 - keep the mapping editable
            self._status(str(error))

    @on(Button.Pressed, '#im-load-profile')
    def _load_pressed(self):
        try:
            self.load_profile(self.query_one('#im-profile', Input).value)
        except Exception as error:  # noqa: BLE001 - invalid files change no mapping
            self._status(str(error))

    @on(Button.Pressed, '#im-apply')
    def action_apply(self):
        try:
            if not self.mapper:
                raise ValueError(t('The import engine is unavailable.'))
            remaps = json.loads(self.query_one('#im-remaps', Input).value or '{}')
            if not isinstance(remaps, dict):
                raise ValueError(t('Code remaps must be a JSON object.'))
            self.remaps = remaps
            relationships = json.loads(self.query_one('#im-relationships', Input).value or '[]')
            if not isinstance(relationships, list):
                raise ValueError(t('Confirmed relationships must be a JSON list.'))
            self.base['relationships'] = relationships
            for row in self.rows.values():
                if row['function'] == FIXED and (not row['fixed'] or row['to'] == IGNORE):
                    raise ValueError(t('Fixed text needs a value and a destination field.'))
            obj = self.mapper.MappingSpec.from_obj(self.mapping()).to_obj()
            Path(self._out).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as error:  # noqa: BLE001 - rejected mappings never leave screen
            self._status(str(error))
            return
        self.dismiss(True)

    @on(Button.Pressed, '#im-skip')
    def action_skip(self):
        self.dismiss(False)
