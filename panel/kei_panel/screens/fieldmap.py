"""Edit & Map Fields (Magic Import, docs/field-mapping.md), laid out like
MarcEdit's data snapshot: a grid of the sample records (one row per record,
one column per field or spreadsheet column) with each column's destination
in its header, the mapping of the selected column, the selected cell in
full with its warnings, and the record Koha will get from the selected row.
The row under the cursor is the example ("Exemplo N de 10") everywhere.

The preview runs the engine's own kei_import/fieldmap.py, imported from the
engine folder the routine names, so the screen and the import never
disagree; without it the screen still maps."""

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
SHOW_ALL, SHOW_CHANGED, SHOW_PROBLEMS = "all", "changed", "problems"
_REF = re.compile(r"^[0-9A-Za-z]{3}(\$[0-9a-z])?$")
CELL = 16                       # width of a grid column
WIDE = 140                      # side by side from this width; stacked below
_MOJIBAKE = re.compile("[ÃÂ][\u0080-¿\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013-\u2122]|â€|�")
_ISBN = re.compile(r"^(97[89][- ]?)?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?[\dXx]$")


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


def warnings(value: str, source: str = "") -> list[str]:
    """What looks dirty in one value (the cell inspector and the grid tint)."""
    out = []
    if value != value.strip():
        out.append(t("spaces at the start or end"))
    letters = [c for c in value if c.isalpha()]
    if len(letters) > 3 and value.upper() == value and any(c.lower() != c for c in letters):
        out.append(t("all in capitals"))
    if _MOJIBAKE.search(value):
        out.append(t("broken accents (wrong character set?)"))
    if not source.startswith(("020", "022")) and _ISBN.match(value.strip()) and \
            len(re.sub(r"\D", "", value)) in (10, 13):
        out.append(t("looks like an ISBN"))
    if any(ord(c) < 32 for c in value):
        out.append(t("control characters"))
    return out


class Row:
    """One source field (TAG$c, or TAG for a control field) or column; a
    grid column. The name stays from the mapping's point of view."""

    def __init__(self, key: tuple[str, str], source: str, kind: str, proposal: str,
                 count: int = 0, total: int = 0, table: str = ""):
        self.key = key
        self.source = source
        self.kind = kind                # marc | column
        self.proposal = proposal        # where it goes with no mapping
        self.to = proposal
        self.count = count
        self.total = total
        self.table = table


class Group:
    """One stream of records or one table: its columns and sample rows,
    each row a list of the values of every column (a list: a field can
    repeat in a record)."""

    def __init__(self, gid: str, label: str, keys: list[tuple[str, str]], cells: list[list[list[str]]],
                 records: list | None = None):
        self.gid = gid
        self.label = label
        self.keys = keys
        self.cells = cells
        self.records = records or []    # engine Records (MARC streams, with the engine)


def marc_values(obj: dict, key: str) -> list[str]:
    """The values of TAG$c (or of the control field TAG) in one record of
    fields.json."""
    tag, _, code = key.partition("$")
    out = []
    for f in obj.get("fields", []):
        if f[0] != tag:
            continue
        if len(f) == 2 and not code:
            out.append(f[1])
        elif len(f) == 3 and code:
            out.extend(v for c, v in f[2] if c == code)
    return out


def read_fields(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class FieldMapScreen(ModalScreen[bool]):
    """Answers True when it wrote a mapping with changes to out_path; False
    when the librarian skipped (or changed nothing): the import goes on as
    it is."""

    BINDINGS = [Binding("escape", "skip", t("Skip: import as it is")), Binding("ctrl+s", "apply", t("Apply")),
                Binding("left_square_bracket", "example(-1)", t("Previous example")),
                Binding("right_square_bracket", "example(1)", t("Next example")),
                Binding("p", "pane", t("Mapping / Preview"), show=False)]

    def __init__(self, title: str, fields_path: str, out_path: str, engine_dir: str = ""):
        super().__init__()
        self._title, self._out = title, out_path
        self.data = read_fields(fields_path)
        self.fm = load_engine(engine_dir)
        self.rows: OrderedDict[tuple[str, str], Row] = OrderedDict()
        self.groups: list[Group] = []
        self._build()
        self._apply_saved(self.data.get("mapping") or {})
        self.group = self.groups[0] if self.groups else Group("", "", [], [])
        self.show = SHOW_ALL
        self.record = 0
        self.field: tuple[str, str] | None = None
        self.before = False
        self.pane = "map"               # stacked layout: map | preview
        self._shown: list[tuple[str, str]] = []

    # ------------------------------------------------------------ data

    def _build(self) -> None:
        for i, s in enumerate(self.data.get("streams", [])):
            recs = s.get("records", [])
            keys = []
            for f in s.get("fields", []):
                key = ("marc", f["from"])
                if key not in keys:
                    keys.append(key)
                if key not in self.rows:
                    self.rows[key] = Row(key, f["from"], "marc", f["from"], f.get("count", 0), len(recs))
            cells = [[marc_values(r, k[1]) for k in keys] for r in recs]
            label = t("${name} · ${n} record(s) · sample of ${k}", name=s.get("name", ""),
                      n=f"{s.get('records_total', 0):,}", k=len(recs))
            records = [self.fm.record_from_obj(r) for r in recs] if self.fm else []
            self.groups.append(Group(f"s{i}", label, keys, cells, records))
        proposals = {(c.get("table", ""), c["from"]): c.get("to") or KEEP for c in self.data.get("columns", [])}
        tables = self.data.get("tables")
        if tables is None:
            tables = self._tables_from_columns()
        for i, tb in enumerate(tables):
            headers = tb.get("headers", [])
            keys = []
            for h in headers:
                key = ("column", h)
                if key in keys:
                    continue
                keys.append(key)
                if key not in self.rows:
                    self.rows[key] = Row(key, h, "column", proposals.get((tb.get("name", ""), h), KEEP),
                                         table=tb.get("name", ""))
            index = {h: n for n, h in reversed(list(enumerate(headers)))}
            cells = [[[r[index[k[1]]]] if index[k[1]] < len(r) and r[index[k[1]]] else [] for k in keys]
                     for r in tb.get("rows", [])]
            for k in keys:
                row = self.rows[k]
                row.total = len(cells)
                row.count = sum(1 for c in cells if c[keys.index(k)])
            label = t("${name} · ${n} row(s) · sample of ${k}", name=tb.get("name", ""),
                      n=f"{tb.get('rows_total', len(cells)):,}", k=len(cells))
            self.groups.append(Group(f"t{i}", label, keys, cells))

    def _tables_from_columns(self) -> list[dict]:
        """An engine before the grid sent only three values per column: they
        become three rows."""
        tables: OrderedDict[str, dict] = OrderedDict()
        for c in self.data.get("columns", []):
            tb = tables.setdefault(c.get("table", ""), {"name": c.get("table", ""), "headers": [], "cols": []})
            tb["headers"].append(c["from"])
            tb["cols"].append(c.get("samples", []))
        out = []
        for tb in tables.values():
            n = max((len(s) for s in tb["cols"]), default=0)
            rows = [[s[i] if i < len(s) else "" for s in tb["cols"]] for i in range(n)]
            out.append({"name": tb["name"], "headers": tb["headers"], "rows": rows, "rows_total": n})
        return out

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

    def values(self, key: tuple[str, str], record: int | None = None) -> list[str]:
        g = self.group
        i = g.keys.index(key)
        r = self.record if record is None else record
        return g.cells[r][i] if r < len(g.cells) else []

    def problems(self, key: tuple[str, str]) -> int:
        """Sample values of a column that are missing or look dirty."""
        i = self.group.keys.index(key)
        return sum(1 for row in self.group.cells
                   if not row[i] or any(warnings(v, key[1]) for v in row[i]))

    # ------------------------------------------------------------ screen

    def _targets(self) -> list[tuple[str, str]]:
        opts = [(t("Keep as it is"), KEEP)]
        for x in self.data.get("targets", []):
            opts.append((f"{x['to']}  {t(x['label'])}", x["to"]))
        opts.append((t("Other: type ${ref}...", ref="TAG$subfield"), OTHER))
        opts.append((t("[Do not import this field]"), IGNORE))
        return opts

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog fieldmap"):
            yield Label(self._title, classes="dialog-title", markup=False)
            with Horizontal(id="fm-head"):
                if len(self.groups) > 1:
                    yield Select([(g.label, g.gid) for g in self.groups], value=self.group.gid,
                                 allow_blank=False, id="fm-group")
                else:
                    yield Label(self.group.label, id="fm-group-label", markup=False)
                yield Select([(t("Show: all"), SHOW_ALL), (t("Show: changed"), SHOW_CHANGED),
                              (t("Show: with problems"), SHOW_PROBLEMS)],
                             value=SHOW_ALL, allow_blank=False, id="fm-show")
                yield Button("◀", id="fm-prev", classes="fm-step")
                yield Label("", id="fm-example", markup=False)
                yield Button("▶", id="fm-next", classes="fm-step")
            grid = DataTable(id="fm-grid", cursor_type="cell", fixed_columns=1, header_height=2,
                             zebra_stripes=True)
            grid.border_title = t("Sample data")
            yield grid
            with Horizontal(id="fm-tabs"):
                yield Button(t("Mapping"), id="fm-tab-map", classes="fm-tab -active")
                yield Button(t("Preview"), id="fm-tab-preview", classes="fm-tab")
            with Horizontal(id="fm-bottom"):
                with Vertical(id="fm-left"):
                    with Vertical(id="fm-map", classes="fm-card"):
                        with Horizontal(id="fm-edit"):
                            yield Select(self._targets(), value=KEEP, allow_blank=False, id="fm-dest")
                            yield Input(placeholder="590$a", id="fm-custom", max_length=6)
                        yield Label("", id="fm-error", classes="dialog-error", markup=False)
                    with Vertical(id="fm-cell", classes="fm-card"):
                        yield Static("", id="fm-inspect")
                with Vertical(id="fm-preview-card", classes="fm-card"):
                    yield Static("", id="fm-preview")
                    yield Button(t("As in the file"), id="fm-before", classes="fm-step")
            with Horizontal(classes="dialog-buttons", id="fm-foot"):
                yield Label("", id="fm-count", markup=False)
                yield Button(t("Reset"), id="fm-reset")
                yield Button(t("Skip: import as it is"), id="fm-skip")
                yield Button(t("Apply"), id="fm-apply", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#fm-custom", Input).display = False
        self._error("")
        self._layout()
        self._fill_grid()
        self.query_one("#fm-grid", DataTable).focus()

    def on_resize(self) -> None:
        self._layout()

    def _layout(self) -> None:
        """Side by side on a wide terminal; below WIDE the bottom half is
        two tabs (Mapping, Preview), switched with p."""
        stacked = self.app.size.width < WIDE
        self.query_one(".fieldmap").set_class(stacked, "-stacked")
        grid, bottom = self.query_one("#fm-grid"), self.query_one("#fm-bottom")
        if stacked:                     # fr heights overflow a full-screen dialog here: share the rows by hand
            room = max(self.app.size.height - 13, 10)   # borders, title, header, tabs, buttons
            grid.styles.height = min((room + 1) // 2, len(self.group.cells) + 4)
            bottom.styles.height = room - grid.styles.height.value
        else:
            grid.styles.height = bottom.styles.height = None
        self.query_one("#fm-tabs").display = stacked
        self.query_one("#fm-left").display = not stacked or self.pane == "map"
        self.query_one("#fm-preview-card").display = not stacked or self.pane == "preview"
        self.query_one("#fm-tab-map").set_class(self.pane == "map", "-active")
        self.query_one("#fm-tab-preview").set_class(self.pane == "preview", "-active")

    # ------------------------------------------------------------ the grid

    def _header(self, row: Row) -> Text:
        head = Text(row.source[:CELL], style="bold")
        head.append("\n")
        if row.to == IGNORE:
            head.append("✕ " + t("left out"), style="bold red")
        elif row.to != row.proposal:
            head.append(f"→ {row.to}", style="bold reverse")
        elif row.kind == "column" and row.to == KEEP:
            head.append("= " + t("as the engine reads it"), style="dim")
        else:
            head.append(f"= {row.to}", style="dim")
        return head

    @staticmethod
    def _cell(vals: list[str], source: str) -> Text:
        if not vals:
            return Text("·", style="dim")
        first = vals[0].replace("\n", " ")
        more = f" ×{len(vals)}" if len(vals) > 1 else ""
        room = CELL - len(more)
        shown = first if len(first) <= room else first[:room - 1] + "…"
        dirty = any(warnings(v, source) for v in vals)
        cell = Text(shown, style="yellow" if dirty else "")
        if more:
            cell.append(more, style="dim")
        return cell

    def _visible(self) -> list[tuple[str, str]]:
        keys = self.group.keys
        if self.show == SHOW_CHANGED:
            return [k for k in keys if self.rows[k].to != self.rows[k].proposal]
        if self.show == SHOW_PROBLEMS:
            return [k for k in keys if self.problems(k)]
        return list(keys)

    def _fill_grid(self) -> None:
        grid = self.query_one("#fm-grid", DataTable)
        col = grid.cursor_column
        grid.clear(columns=True)
        self._shown = self._visible()
        grid.add_column(Text("#\n", style="bold"), width=3, key="#")
        for k in self._shown:
            grid.add_column(self._header(self.rows[k]), width=CELL, key="\t".join(k))
        for r, row in enumerate(self.group.cells):
            values = dict(zip(self.group.keys, row))
            grid.add_row(Text(str(r + 1), style="bold"), *[self._cell(values[k], k[1]) for k in self._shown],
                         key=str(r))
        if self.field in self._shown:
            col = self._shown.index(self.field) + 1
        if self._shown and self.group.cells:
            grid.move_cursor(row=min(self.record, len(self.group.cells) - 1),
                             column=min(max(col, 1), len(self._shown)))
        else:
            self.field = None
        self._sync()

    def _sync(self) -> None:
        """Everything that follows the cursor: the example, the mapping card,
        the inspector, the preview and the counts."""
        n = len(self.group.cells)
        self.query_one("#fm-example", Label).update(
            t("Example ${i} of ${n}", i=self.record + 1 if n else 0, n=n))
        self._sync_editor()
        self._inspect()
        self._refresh()

    def _sync_editor(self) -> None:
        row = self.rows.get(self.field) if self.field else None
        card = self.query_one("#fm-map")
        card.border_title = t("Mapping of ${field}", field=row.source) if row else t("Mapping")
        dest, custom = self.query_one("#fm-dest", Select), self.query_one("#fm-custom", Input)
        dest.disabled = row is None
        value = self._dest_value(row)
        dest.value, custom.display = value, value == OTHER
        if value == OTHER:
            custom.value = row.to
        self._error("")

    def _error(self, text: str) -> None:
        box = self.query_one("#fm-error", Label)
        box.update(text)
        box.display = bool(text)

    def _dest_value(self, row: Row | None) -> str:
        """The picker's value for a column's destination."""
        if row is None or row.to == row.proposal:
            return KEEP
        return row.to if row.to in {v for _, v in self._targets()} else OTHER

    def _inspect(self) -> None:
        card, box = self.query_one("#fm-cell"), self.query_one("#fm-inspect", Static)
        if not self.field:
            card.border_title = t("Selected value")
            box.update(t("Pick a cell of the grid."))
            return
        row = self.rows[self.field]
        card.border_title = t("Selected value · ${field} · example ${i}", field=row.source, i=self.record + 1)
        vals = self.values(self.field)
        text = Text()
        if not vals:
            text.append(t("This example does not have this field."), style="dim")
        for v in vals:
            text.append(v + "\n")
            found = warnings(v, row.source)
            facts = t("${n} character(s)", n=len(v))
            text.append(facts, style="dim")
            if found:
                text.append("  ⚠ " + ", ".join(found), style="yellow")
            text.append("\n")
        if row.total:
            text.append(t("In ${n} of ${k} sample records.", n=row.count, k=row.total), style="dim")
        box.update(text)

    def _refresh(self) -> None:
        n = self.changed()
        dropped = sum(1 for r in n if r.to == IGNORE)
        dirty = sum(1 for row in self.group.cells for vals in row for v in vals if warnings(v))
        self.query_one("#fm-count", Label).update(
            t("${n} change(s) · ${k} left out · ${w} warning(s)", n=len(n) - dropped, k=dropped, w=dirty))
        self._draw_preview()

    def _draw_preview(self) -> None:
        card, box = self.query_one("#fm-preview-card"), self.query_one("#fm-preview", Static)
        n = len(self.group.cells)
        card.border_title = t("Koha preview · example ${i} of ${n}", i=self.record + 1 if n else 0, n=n)
        before = self.query_one("#fm-before", Button)
        before.display = bool(self.group.records)
        if not self.group.records:
            if self.group.gid.startswith("t"):
                box.update(self._table_preview())
            else:
                box.update(t("The preview needs the engine of this panel version; the mapping still works."))
            return
        src = self.group.records[min(self.record, len(self.group.records) - 1)]
        old = src.formatted().splitlines()
        if self.before:
            card.border_title += "  ·  " + t("as in the file")
            box.update(Text("\n".join(old)))
            return
        try:
            after = self.fm.FieldMap.from_obj(self.mapping()).apply(src).formatted().splitlines()
        except self.fm.FieldMapError as e:
            box.update(Text(str(e)))
            return
        seen = set(old)
        text = Text()
        for line in after:
            text.append(("▸ " if line not in seen else "  ") + line + "\n", style="bold" if line not in seen else "")
        box.update(text)

    def _table_preview(self) -> Text:
        """A spreadsheet row and where each value goes (the engine builds the
        record itself, with its own rules)."""
        text = Text()
        for k in self.group.keys:
            row = self.rows[k]
            vals = self.values(k)
            if not vals:
                continue
            to = t("left out") if row.to == IGNORE else (t("as the engine reads it") if row.to == KEEP else row.to)
            text.append(f"{row.source[:20]:<20} → {to:<10} ", style="bold" if row.to != row.proposal else "")
            text.append(vals[0][:60] + "\n", style="strike dim" if row.to == IGNORE else "")
        return text

    # ------------------------------------------------------------ changes

    def _set(self, to: str) -> None:
        row = self.rows.get(self.field) if self.field else None
        if row is None:
            return
        why = self.check(row, to) if to != row.proposal else ""
        self._error(why)
        if why:
            return
        row.to = to
        self._fill_grid()

    # ------------------------------------------------------------ events

    @on(DataTable.CellHighlighted, "#fm-grid")
    def _moved(self, event: DataTable.CellHighlighted) -> None:
        self.record = event.coordinate.row
        col = event.coordinate.column
        if 1 <= col <= len(self._shown):
            self.field = self._shown[col - 1]
        self._sync()

    @on(DataTable.CellSelected, "#fm-grid")
    def _chosen(self) -> None:
        """Enter on a cell: on to its destination."""
        if self.field:
            self.pane = "map"
            self._layout()
            self.query_one("#fm-dest", Select).focus()

    @on(Select.Changed, "#fm-group")
    def _group_changed(self, event: Select.Changed) -> None:
        self.group = next(g for g in self.groups if g.gid == event.value)
        self.record, self.field = 0, None
        self._fill_grid()

    @on(Select.Changed, "#fm-show")
    def _show_changed(self, event: Select.Changed) -> None:
        self.show = str(event.value)
        self._fill_grid()

    @on(Select.Changed, "#fm-dest")
    def _dest_changed(self, event: Select.Changed) -> None:
        row = self.rows.get(self.field) if self.field else None
        if event.value == self._dest_value(row):
            return                      # the picker following the cursor, not a choice
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
            if not str(self.query_one("#fm-error", Label).render()):
                self.query_one("#fm-grid", DataTable).focus()

    @on(Button.Pressed, "#fm-prev")
    def _prev(self) -> None:
        self.action_example(-1)

    @on(Button.Pressed, "#fm-next")
    def _next(self) -> None:
        self.action_example(1)

    def action_example(self, step: int) -> None:
        n = len(self.group.cells)
        if not n:
            return
        self.record = (self.record + step) % n
        grid = self.query_one("#fm-grid", DataTable)
        grid.move_cursor(row=self.record, column=max(grid.cursor_column, 1 if self._shown else 0))
        self._sync()

    @on(Button.Pressed, "#fm-tab-map")
    def _tab_map(self) -> None:
        self.pane = "map"
        self._layout()

    @on(Button.Pressed, "#fm-tab-preview")
    def _tab_preview(self) -> None:
        self.pane = "preview"
        self._layout()

    def action_pane(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.pane = "preview" if self.pane == "map" else "map"
        self._layout()

    @on(Button.Pressed, "#fm-before")
    def _toggle_before(self) -> None:
        self.before = not self.before
        self._draw_preview()

    @on(Button.Pressed, "#fm-reset")
    def _reset(self) -> None:
        for r in self.rows.values():
            r.to = r.proposal
        self._fill_grid()

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
            self._error(f"{self._out}: {exc.strerror}")
            return
        self.dismiss(True)
