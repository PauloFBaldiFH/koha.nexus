"""Edit & Map Fields (Magic Import, docs/field-mapping.md): the fields and
columns the engine found in the first records, with sample values, and where
each one goes in Koha. The record preview is redrawn at every change with the
engine's own kei_import/fieldmap.py, imported from the engine folder the
routine names, so the screen and the import never disagree."""

from __future__ import annotations

import importlib
import json
import re
import sys
from collections import OrderedDict

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from ..i18n import t

KEEP, OTHER, IGNORE = "keep", "other", "ignore"
COLUMNS = "\0columns"           # the stream selector's entry for the tables
_REF = re.compile(r"^[0-9A-Za-z]{3}(\$[0-9a-z])?$")
PREVIEW = 3


def load_engine(engine_dir: str):
    """kei_import.fieldmap of the engine folder, or None (no preview then)."""
    if not engine_dir:
        return None
    for name in [n for n in sys.modules if n == "kei_import" or n.startswith("kei_import.")]:
        del sys.modules[name]
    sys.path.insert(0, engine_dir)
    try:
        return importlib.import_module("kei_import.fieldmap")
    except Exception:  # noqa: BLE001 - an old or missing engine: the screen still maps
        return None
    finally:
        if engine_dir in sys.path:
            sys.path.remove(engine_dir)


class Row:
    """One source field (TAG$c, or TAG for a control field) or column."""

    def __init__(self, key: tuple[str, str], source: str, kind: str, samples: list[str], proposal: str,
                 count: int = 0, total: int = 0, table: str = ""):
        self.key = key
        self.source = source
        self.kind = kind                # marc | column
        self.samples = samples
        self.proposal = proposal        # where it goes with no mapping
        self.to = proposal
        self.count = count
        self.total = total
        self.table = table


def read_fields(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class FieldMapScreen(ModalScreen[bool]):
    """Answers True when it wrote a mapping with changes to out_path; False
    when the librarian skipped (or changed nothing): the import goes on as
    it is."""

    BINDINGS = [Binding("escape", "skip", t("Skip: import as it is")), Binding("ctrl+s", "apply", t("Apply"))]

    def __init__(self, title: str, fields_path: str, out_path: str, engine_dir: str = ""):
        super().__init__()
        self._title, self._out = title, out_path
        self.data = read_fields(fields_path)
        self.fm = load_engine(engine_dir)
        self.rows: OrderedDict[tuple[str, str], Row] = OrderedDict()
        self.groups: list[tuple[str, str, list[tuple[str, str]]]] = []   # (id, label, row keys)
        self._records: dict[str, list] = {}
        self._build_rows()
        self._apply_saved(self.data.get("mapping") or {})
        self.group = self.groups[0][0] if self.groups else ""
        self.record = 0
        self.before = False
        self._shown: list[tuple[str, str]] = []
        self._syncing = False

    # ------------------------------------------------------------ data

    def _build_rows(self) -> None:
        for i, s in enumerate(self.data.get("streams", [])):
            keys = []
            for f in s.get("fields", []):
                key = ("marc", f["from"])
                if key not in keys:
                    keys.append(key)
                if key not in self.rows:
                    self.rows[key] = Row(key, f["from"], "marc", f.get("samples", []), f["from"],
                                         f.get("count", 0), len(s.get("records", [])))
            gid = f"s{i}"
            label = t("${name} · ${n} record(s) · sample of ${k}", name=s.get("name", ""),
                       n=f"{s.get('records_total', 0):,}", k=len(s.get("records", [])))
            self.groups.append((gid, label, keys))
            if self.fm:
                self._records[gid] = [self.fm.record_from_obj(r) for r in s.get("records", [])]
        keys = []
        for c in self.data.get("columns", []):
            key = ("column", c["from"])
            if key not in keys:
                keys.append(key)
            if key not in self.rows:
                self.rows[key] = Row(key, c["from"], "column", c.get("samples", []), c.get("to") or KEEP,
                                     table=c.get("table", ""))
        if keys:
            self.groups.append((COLUMNS, t("Spreadsheet columns"), keys))

    def _apply_saved(self, mapping: dict) -> None:
        """The mapping of the last build: a second look starts from it."""
        for m in mapping.get("mappings", []):
            key = ("column" if m.get("kind") == "column" else "marc", m.get("from", ""))
            if key not in self.rows and key[0] == "marc" and ("column", key[1]) in self.rows:
                key = ("column", key[1])
            if key in self.rows:
                self.rows[key].to = m.get("to", "") or IGNORE

    def changed(self) -> list[Row]:
        return [r for r in self.rows.values() if r.to != r.proposal]

    def mapping(self) -> dict:
        out = []
        for r in self.changed():
            m = {"from": r.source, "to": r.to}
            if r.kind == "column":
                m["kind"] = "column"
            out.append(m)
        return {"version": 1, "mappings": out}

    def check(self, row: Row, to: str) -> str:
        """"" when row can go to `to`, else why not."""
        if to == IGNORE:
            return ""
        if not _REF.match(to):
            return t("Type a MARC destination as ${ref}, for example ${example}.", ref="TAG$subfield", example="590$a")
        if self.fm:
            try:
                self.fm.Rule(row.source, to, "column" if row.kind == "column" else None)
            except self.fm.FieldMapError as e:
                return str(e)
        elif row.kind == "column" and "$" not in to:
            return t("A column needs a subfield: ${ref}.", ref="TAG$subfield")
        return ""

    # ------------------------------------------------------------ screen

    def _targets(self) -> list[tuple[str, str]]:
        opts = [(t("Keep as it is"), KEEP)]
        for x in self.data.get("targets", []):
            opts.append((f"{x['to']}  {t(x['label'])}", x["to"]))
        opts.append((t("Other: type ${ref}...", ref="TAG$subfield"), OTHER))
        opts.append((t("[Do not import this field]"), IGNORE))
        return opts

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide -log fieldmap"):
            yield Label(self._title, classes="dialog-title", markup=False)
            yield Static(t("Choose where each field or column goes in Koha. What you leave as it is is "
                           "imported as before."), classes="dialog-note", markup=False)
            if len(self.groups) > 1:
                yield Select([(label, gid) for gid, label, _ in self.groups], value=self.group,
                             allow_blank=False, id="fm-group")
            else:
                yield Label(self.groups[0][1] if self.groups else "", id="fm-group-label", markup=False)
            table = DataTable(id="fm-table", cursor_type="row", zebra_stripes=True)
            table.add_columns(t("Source field"), t("Sample value"), t("Koha destination"))
            yield table
            with Horizontal(id="fm-edit"):
                yield Select(self._targets(), value=KEEP, allow_blank=False, id="fm-dest")
                yield Input(placeholder="590$a", id="fm-custom", max_length=6)
            yield Label("", id="fm-error", classes="dialog-error", markup=False)
            with Horizontal(id="fm-preview-bar"):
                yield Label("", id="fm-preview-title", markup=False)
                yield Button("◀", id="fm-prev", classes="-small")
                yield Button("▶", id="fm-next", classes="-small")
                yield Button(t("As in the file"), id="fm-before", classes="-small")
            yield Static("", id="fm-preview", classes="dialog-preview")
            with Horizontal(classes="dialog-buttons"):
                yield Label("", id="fm-count", markup=False)
                yield Button(t("Reset"), id="fm-reset")
                yield Button(t("Skip: import as it is"), id="fm-skip")
                yield Button(t("Apply"), id="fm-apply", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#fm-custom", Input).display = False
        self._fill_table()
        self.query_one("#fm-table", DataTable).focus()

    def _group_keys(self) -> list[tuple[str, str]]:
        for gid, _, keys in self.groups:
            if gid == self.group:
                return keys
        return []

    def _dest_text(self, row: Row) -> str:
        if row.to == IGNORE:
            return t("[Do not import this field]")
        if row.to == row.proposal:
            return row.to if row.kind == "marc" or row.to != KEEP else t("as the engine reads it")
        return f"→ {row.to}"

    def _source_text(self, row: Row) -> str:
        if row.kind == "column":
            return row.source
        return f"{row.source}  {row.count}/{row.total}" if row.total else row.source

    def _fill_table(self) -> None:
        table = self.query_one("#fm-table", DataTable)
        at = table.cursor_row
        table.clear()
        self._shown = self._group_keys()
        for key in self._shown:
            row = self.rows[key]
            sample = row.samples[0] if row.samples else ""
            table.add_row(Text(self._source_text(row)), Text(sample[:60]), Text(self._dest_text(row)), key="\t".join(key))
        if self._shown:
            table.move_cursor(row=min(max(at, 0), len(self._shown) - 1))
        self._sync_editor()
        self._refresh()

    def _current(self) -> Row | None:
        table = self.query_one("#fm-table", DataTable)
        if not self._shown or table.cursor_row < 0 or table.cursor_row >= len(self._shown):
            return None
        return self.rows[self._shown[table.cursor_row]]

    def _sync_editor(self) -> None:
        """The destination picker shows the row under the cursor."""
        row = self._current()
        dest, custom = self.query_one("#fm-dest", Select), self.query_one("#fm-custom", Input)
        self._syncing = True
        try:
            values = {v for _, v in self._targets()}
            if row is None or row.to == row.proposal:
                dest.value, custom.display = KEEP, False
            elif row.to in values:
                dest.value, custom.display = row.to, False
            else:
                dest.value, custom.display, custom.value = OTHER, True, row.to
        finally:
            self._syncing = False
        self.query_one("#fm-error", Label).update("")

    def _set(self, to: str) -> None:
        row = self._current()
        if row is None:
            return
        why = self.check(row, to) if to != row.proposal else ""
        self.query_one("#fm-error", Label).update(why)
        if why:
            return
        row.to = to
        table = self.query_one("#fm-table", DataTable)
        table.update_cell("\t".join(row.key), table.ordered_columns[2].key, Text(self._dest_text(row)))
        self._refresh()

    def _refresh(self) -> None:
        n = self.changed()
        dropped = sum(1 for r in n if r.to == IGNORE)
        self.query_one("#fm-count", Label).update(
            t("${n} change(s) · ${k} left out", n=len(n) - dropped, k=dropped))
        self._draw_preview()

    def _draw_preview(self) -> None:
        title = self.query_one("#fm-preview-title", Label)
        box = self.query_one("#fm-preview", Static)
        for b in ("#fm-prev", "#fm-next", "#fm-before"):
            self.query_one(b, Button).display = self.group != COLUMNS
        if self.group == COLUMNS:
            title.update(t("Columns and where they go"))
            text = Text()
            for key in self._shown:
                row = self.rows[key]
                to = t("left out") if row.to == IGNORE else (t("as the engine reads it") if row.to == KEEP else row.to)
                text.append(f"{row.source[:24]:<24} → {to:<10} ", style="bold" if row.to != row.proposal else "")
                text.append((row.samples[0] if row.samples else "")[:40] + "\n")
            box.update(text)
            return
        records = self._records.get(self.group, [])
        if not self.fm or not records:
            title.update(t("Record preview"))
            box.update(t("The preview needs the engine of this panel version; the mapping still works."))
            return
        shown = min(PREVIEW, len(records))
        self.record %= shown
        title.update(t("Record preview ${i} / ${n}", i=self.record + 1, n=shown)
                     + ("  ·  " + t("as in the file") if self.before else ""))
        src = records[self.record]
        before = src.formatted().splitlines()
        if self.before:
            box.update(Text("\n".join(before)))
            return
        try:
            after = self.fm.FieldMap.from_obj(self.mapping()).apply(src).formatted().splitlines()
        except self.fm.FieldMapError as e:
            box.update(Text(str(e)))
            return
        old = set(before)
        text = Text()
        for line in after:
            text.append(("▸ " if line not in old else "  ") + line + "\n", style="bold" if line not in old else "")
        box.update(text)

    # ------------------------------------------------------------ events

    @on(DataTable.RowHighlighted, "#fm-table")
    def _row_moved(self) -> None:
        self._sync_editor()

    @on(Select.Changed, "#fm-group")
    def _group_changed(self, event: Select.Changed) -> None:
        self.group, self.record = str(event.value), 0
        self.query_one("#fm-table", DataTable).move_cursor(row=0)
        self._fill_table()

    @on(Select.Changed, "#fm-dest")
    def _dest_changed(self, event: Select.Changed) -> None:
        if self._syncing:
            return
        row = self._current()
        custom = self.query_one("#fm-custom", Input)
        if event.value == OTHER:
            custom.display = True
            custom.focus()
            return
        custom.display = False
        if row is not None:
            self._set(row.proposal if event.value == KEEP else str(event.value))

    @on(Input.Submitted, "#fm-custom")
    def _custom_typed(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self._set(value)
            self.query_one("#fm-table", DataTable).focus()

    @on(Button.Pressed, "#fm-prev")
    def _prev(self) -> None:
        self.action_record(-1)

    @on(Button.Pressed, "#fm-next")
    def _next(self) -> None:
        self.action_record(1)

    def action_record(self, step: int) -> None:
        self.record += step
        self._draw_preview()

    @on(Button.Pressed, "#fm-before")
    def _toggle_before(self) -> None:
        self.before = not self.before
        self._draw_preview()

    @on(Button.Pressed, "#fm-reset")
    def _reset(self) -> None:
        for r in self.rows.values():
            r.to = r.proposal
        self._fill_table()

    @on(Button.Pressed, "#fm-skip")
    def action_skip(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#fm-apply")
    def action_apply(self) -> None:
        if not self.changed():
            self.dismiss(False)
            return
        try:
            with open(self._out, "w", encoding="utf-8") as fh:
                json.dump(self.mapping(), fh, ensure_ascii=False, indent=1)
                fh.write("\n")
        except OSError as exc:
            self.query_one("#fm-error", Label).update(f"{self._out}: {exc.strerror}")
            return
        self.dismiss(True)
