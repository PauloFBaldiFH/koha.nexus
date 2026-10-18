"""Edit & Map Fields (Magic Import, docs/field-mapping.md), laid out after
the librarians' own sketch (exemplo ferramenta de importação.xlsx):

  - on top, a grid of the sample: one row per record, one column per field
    or spreadsheet column, headed "campo N · 245$a" over where it goes; a
    bar under it is dragged (or Ctrl+Up/Down) to make the grid taller;
  - below, "Selecionar campo" and "Função" (keep, a field from the list, a
    custom TAG$subfield typed by hand, a fixed text for every record, or
    leave out), and beside them the Library of Congress link and "Mais
    opções": join copies of the same book, recase capitals, safe spelling
    repair (tidy.py in the engine);
  - the record Koha will get opens from "Record preview".

The row under the cursor is the example ("Example N of 10") everywhere. The
preview runs the engine's own kei_import/fieldmap.py, imported from the
engine folder the routine names, so the screen and the import never
disagree; without it the screen still maps."""

from __future__ import annotations

import importlib
import json
import re
import sys
from collections import Counter, OrderedDict

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select, Static

from .. import marc21
from ..i18n import t

KEEP, OTHER, FIXED, IGNORE = "keep", "other", "fixed", "ignore"
NEW_FIXED = "+fixed"
OPTIONS = ("group", "case", "clean")
_REF = re.compile(r"^[0-9A-Za-z]{3}(\$[0-9a-z])?$")
CELL = 20                       # width of a grid column
WIDE = 140                      # mapping and options side by side from this width
_MOJIBAKE = re.compile("[ÃÂ][\u0080-¿ŒœŠšŸŽžƒˆ˜–-™]|â€|�")
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
    """What looks dirty in one value (the cell line and the grid tint)."""
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


def ref_label(ref: str) -> str:
    """"245$a - Title" (translated), or the reference alone."""
    name = marc21.label(ref)
    return f"{ref} - {t(name)}" if name else ref


class Row:
    """One source field (TAG$c, or TAG for a control field), spreadsheet
    column or fixed text: a grid column. `to` is where it goes (its
    proposal when unchanged); `text` a fixed text written in every record
    in place of its values."""

    def __init__(self, key: tuple[str, str], source: str, kind: str, proposal: str,
                 count: int = 0, total: int = 0, table: str = ""):
        self.key = key
        self.source = source
        self.kind = kind                # marc | column | fixed
        self.proposal = proposal        # where it goes with no mapping
        self.to = proposal
        self.text = ""
        self.count = count
        self.total = total
        self.table = table

    @property
    def changed(self) -> bool:
        return self.to != self.proposal or bool(self.text)


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


class Splitter(Static):
    """The bar under the grid: dragged up or down, it makes the grid
    shorter or taller (the sketch's "barra para deslizar")."""

    def __init__(self, **kw):
        super().__init__(t("━━━  ↕ drag to resize the grid (Ctrl+↑ / Ctrl+↓)  ━━━"), **kw)
        self._start: tuple[int, int] | None = None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._start = (event.screen_y, self.screen.grid_height)
        self.capture_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._start is not None:
            y, h = self._start
            self.screen.resize_grid(h + event.screen_y - y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._start = None
        self.release_mouse()


class RecordPreviewScreen(ModalScreen[None]):
    """The record Koha will get from the example under the grid's cursor,
    after the mapping and the chosen cleanings ("As in the file" toggles
    the record before them)."""

    BINDINGS = [Binding("escape", "close", t("Close")),
                Binding("left_square_bracket", "example(-1)", t("Previous example")),
                Binding("right_square_bracket", "example(1)", t("Next example"))]

    def __init__(self, owner: "FieldMapScreen"):
        super().__init__()
        self.owner = owner

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog fieldmap-preview"):
            yield Label("", id="fmp-title", classes="dialog-title", markup=False)
            with VerticalScroll(id="fmp-scroll"):
                yield Static("", id="fmp-record")
            with Horizontal(classes="dialog-buttons"):
                yield Button("◀", id="fmp-prev", classes="fm-step")
                yield Button("▶", id="fmp-next", classes="fm-step")
                yield Button(t("As in the file"), id="fmp-before")
                yield Button(t("Close"), id="fmp-close", variant="primary")

    def on_mount(self) -> None:
        self._draw()

    def _draw(self) -> None:
        o = self.owner
        n = len(o.group.cells)
        title = t("Koha preview · example ${i} of ${n}", i=o.record + 1 if n else 0, n=n)
        if o.before:
            title += "  ·  " + t("as in the file")
        self.query_one("#fmp-title", Label).update(title)
        self.query_one("#fmp-record", Static).update(o.preview_text())
        self.query_one("#fmp-before").display = bool(o.group.records)

    def action_example(self, step: int) -> None:
        self.owner.action_example(step)
        self._draw()

    @on(Button.Pressed, "#fmp-prev")
    def _prev(self) -> None:
        self.action_example(-1)

    @on(Button.Pressed, "#fmp-next")
    def _next(self) -> None:
        self.action_example(1)

    @on(Button.Pressed, "#fmp-before")
    def _before(self) -> None:
        self.owner.before = not self.owner.before
        self._draw()

    @on(Button.Pressed, "#fmp-close")
    def action_close(self) -> None:
        self.owner.before = False
        self.dismiss(None)


class FieldMapScreen(ModalScreen[bool]):
    """Answers True when it wrote a mapping with changes to out_path; False
    when the librarian skipped (or changed nothing): the import goes on as
    it is."""

    BINDINGS = [Binding("escape", "skip", t("Skip: import as it is")), Binding("ctrl+s", "apply", t("Apply")),
                Binding("left_square_bracket", "example(-1)", t("Previous example")),
                Binding("right_square_bracket", "example(1)", t("Next example")),
                Binding("ctrl+up", "grow(-2)", t("Smaller grid"), show=False),
                Binding("ctrl+down", "grow(2)", t("Taller grid"), show=False),
                Binding("p", "preview", t("Record preview"), show=False)]

    def __init__(self, title: str, fields_path: str, out_path: str, engine_dir: str = ""):
        super().__init__()
        self._title, self._out = title, out_path
        self.data = read_fields(fields_path)
        self.fm = load_engine(engine_dir)
        self.rows: OrderedDict[tuple[str, str], Row] = OrderedDict()
        self.groups: list[Group] = []
        self.fixed: list[tuple[str, str]] = []      # keys of the fixed-text columns
        self.options = {k: False for k in OPTIONS}
        self._build()
        self._apply_saved(self.data.get("mapping") or {})
        self.group = self.groups[0] if self.groups else Group("", "", [], [])
        self.record = 0
        self.field: tuple[str, str] | None = None
        self.before = False
        self.grid_height = 0            # set on mount, then by the splitter
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
            src = m.get("from", "")
            if src.startswith("=") and m.get("kind") != "column":
                self._new_fixed(src[1:].strip(), m.get("to", ""))
                continue
            key = ("column" if m.get("kind") == "column" else "marc", src)
            if key not in self.rows and key[0] == "marc" and ("column", key[1]) in self.rows:
                key = ("column", key[1])
            if key in self.rows:
                self.rows[key].to = m.get("to", "") or IGNORE
        for k, v in (mapping.get("options") or {}).items():
            if k in self.options:
                self.options[k] = bool(v)

    def _new_fixed(self, text: str = "", to: str = "") -> tuple[str, str]:
        n = max((int(k[1]) for k in self.fixed), default=0) + 1
        key = ("fixed", str(n))
        row = Row(key, t("fixed text ${n}", n=n), "fixed", IGNORE)
        row.to, row.text = to or IGNORE, text
        self.rows[key] = row
        self.fixed.append(key)
        return key

    def _remove_fixed(self, key: tuple[str, str]) -> None:
        self.fixed.remove(key)
        del self.rows[key]
        self.field = None
        self._fill_grid()

    def changed(self) -> list[Row]:
        return [r for r in self.rows.values() if r.changed and (r.kind != "fixed" or (r.text and r.to != IGNORE))]

    def mapping(self) -> dict:
        out = []
        for r in self.changed():
            kind = {"kind": "column"} if r.kind == "column" else {}
            if r.kind == "fixed":
                out.append({"from": "=" + r.text, "to": r.to})
            elif r.text:
                out.append(dict({"from": r.source, "to": IGNORE}, **kind))
                out.append({"from": "=" + r.text, "to": r.to})
            else:
                out.append(dict({"from": r.source, "to": r.to}, **kind))
        obj = {"version": 1, "mappings": out}
        on_ = {k: True for k, v in self.options.items() if v}
        if on_:
            obj["options"] = on_
        return obj

    def check(self, row: Row, to: str) -> str:
        """"" when row can go to `to`, else why not."""
        if to == IGNORE and not (row.kind == "fixed" or row.text):
            return ""
        if to != IGNORE and not _REF.match(to):
            return t("Type a MARC destination as ${ref}, for example ${example}.", ref="TAG$subfield", example="590$a")
        if row.kind == "fixed" or row.text:
            if to == IGNORE:
                return t("Type the field the text goes to, for example ${example}.", example="942$c")
            if "$" not in to and to >= "010":
                return t("A fixed text needs a subfield: ${ref}.", ref="TAG$subfield")
            return ""
        if self.fm:
            try:
                self.fm.Rule(row.source, to, "column" if row.kind == "column" else None)
            except self.fm.FieldMapError as e:
                return str(e)
        elif row.kind == "column" and "$" not in to:
            return t("A column needs a subfield: ${ref}.", ref="TAG$subfield")
        return ""

    def keys(self) -> list[tuple[str, str]]:
        """The grid's columns: the group's fields, then the fixed texts."""
        return list(self.group.keys) + self.fixed

    def number(self, key: tuple[str, str]) -> int:
        """The column's place in the grid, from 1."""
        return self.keys().index(key) + 1

    def campo(self, key: tuple[str, str]) -> str:
        """"campo 2": how the sketch names a column."""
        return t("field ${n}", n=self.number(key))

    def values(self, key: tuple[str, str], record: int | None = None) -> list[str]:
        row = self.rows[key]
        if row.kind == "fixed":
            return [row.text] if row.text else []
        g = self.group
        r = self.record if record is None else record
        return g.cells[r][g.keys.index(key)] if r < len(g.cells) else []

    def dest_text(self, row: Row) -> str:
        """Where a column goes, in words."""
        if row.to == IGNORE:
            return t("left out")
        if row.to == KEEP:
            return t("as the engine reads it")
        return ref_label(row.to)

    # ------------------------------------------------------------ screen

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog fieldmap"):
            yield Label(self._title, classes="dialog-title", markup=False)
            with Horizontal(id="fm-head"):
                if len(self.groups) > 1:
                    yield Select([(g.label, g.gid) for g in self.groups], value=self.group.gid,
                                 allow_blank=False, id="fm-group")
                else:
                    yield Label(self.group.label, id="fm-group-label", markup=False)
                yield Button("◀", id="fm-prev", classes="fm-step")
                yield Label("", id="fm-example", markup=False)
                yield Button("▶", id="fm-next", classes="fm-step")
            yield DataTable(id="fm-grid", cursor_type="cell", fixed_columns=1, header_height=2, zebra_stripes=True)
            yield Splitter(id="fm-split")
            yield Label("", id="fm-cell", markup=False)
            with VerticalScroll(id="fm-bottom"):
                with Horizontal(id="fm-cards"):
                    with Vertical(id="fm-map", classes="fm-card"):
                        with Horizontal(classes="fm-line"):
                            yield Label(t("Select field"), classes="fm-key")
                            yield Select([], allow_blank=True, id="fm-field")
                        with Horizontal(classes="fm-line"):
                            yield Label(t("Function"), classes="fm-key")
                            yield Select([], allow_blank=True, id="fm-dest")
                        with Horizontal(classes="fm-line", id="fm-inputs"):
                            yield Label("", classes="fm-key")
                            yield Input(placeholder="820$a", id="fm-custom", max_length=6)
                            yield Input(placeholder=t("text for every record"), id="fm-text")
                        yield Label("", id="fm-error", classes="dialog-error", markup=False)
                    with Vertical(id="fm-more", classes="fm-card"):
                        yield Label(t("Want to know the fields better?"), id="fm-loc-q")
                        with Horizontal(id="fm-loc-bar"):
                            yield Button(t("MARC 21 (Library of Congress) ↗"), id="fm-loc", classes="fm-link")
                            yield Button("", id="fm-loc-tag", classes="fm-link")
                        yield Checkbox(t("Join copies of the same book"), self.options["group"], id="fm-opt-group")
                        yield Label(t("Author + title + publisher/year, tolerant of typos; ISBN when there is one."),
                                    classes="fm-hint")
                        yield Checkbox(t("Fix capitals and small letters"), self.options["case"], id="fm-opt-case")
                        yield Label(t("Only text typed all in capitals; names and acronyms stay right."),
                                    classes="fm-hint")
                        yield Checkbox(t("Safe spelling repair"), self.options["clean"], id="fm-opt-clean")
                        yield Label(t("Broken accents, extra spaces, OCR slips; no word is guessed."),
                                    classes="fm-hint")
                        yield Static("", id="fm-opt-note")
            with Horizontal(classes="dialog-buttons", id="fm-foot"):
                yield Label("", id="fm-count", markup=False)
                yield Button(t("Record preview"), id="fm-show-preview")
                yield Button(t("Reset"), id="fm-reset")
                yield Button(t("Skip: import as it is"), id="fm-skip")
                yield Button(t("Apply"), id="fm-apply", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#fm-map").border_title = t("Mapping")
        self.query_one("#fm-more").border_title = t("More options")
        self._error("")
        self.grid_height = min(len(self.group.cells) + 5, max(self.app.size.height * 2 // 5, 7))
        self._layout()
        self._fill_grid()
        self.query_one("#fm-grid", DataTable).focus()

    def on_resize(self) -> None:
        self._layout()

    def _layout(self) -> None:
        """Mapping and options side by side on a wide terminal, one under the
        other below WIDE; the grid as tall as the splitter left it."""
        self.query_one(".fieldmap").set_class(self.app.size.width < WIDE, "-stacked")
        self.resize_grid(self.grid_height)

    def resize_grid(self, height: int) -> None:
        most = max(self.app.size.height - 16, 6)   # title, header, splitter, a card and the buttons stay
        self.grid_height = max(5, min(height, most, len(self.group.cells) + 5 if self.group.cells else 5))
        self.query_one("#fm-grid").styles.height = self.grid_height

    def action_grow(self, step: int) -> None:
        self.resize_grid(self.grid_height + step)

    def _error(self, text: str) -> None:
        box = self.query_one("#fm-error", Label)
        box.update(text)
        box.display = bool(text)

    # ------------------------------------------------------------ the grid

    def _header(self, key: tuple[str, str]) -> Text:
        row = self.rows[key]
        head = Text(self.campo(key), style="bold")
        if row.kind != "fixed":
            head.append(" · " + row.source[:CELL - 10], style="bold")
        head.append("\n")
        if row.text:
            head.append("✎ " + (row.to if row.to != IGNORE else "?"), style="bold reverse")
        elif row.to == IGNORE:
            head.append("✕ " + t("left out"), style="bold red")
        elif row.changed:
            head.append(f"→ {row.to}", style="bold reverse")
        else:
            name = marc21.label(row.to) if row.to != KEEP else ""
            head.append("= " + (t(name) if name else self.dest_text(row)), style="dim")
        return head

    def _cell(self, key: tuple[str, str], record: int) -> Text:
        row = self.rows[key]
        if row.text:
            return Text(row.text[:CELL - 1], style="italic")
        vals = self.values(key, record)
        if not vals:
            return Text("·", style="dim")
        first = vals[0].replace("\n", " ")
        more = f" ×{len(vals)}" if len(vals) > 1 else ""
        room = CELL - len(more)
        shown = first if len(first) <= room else first[:room - 1] + "…"
        dirty = any(warnings(v, row.source) for v in vals)
        style = "strike dim" if row.to == IGNORE else ("yellow" if dirty else "")
        cell = Text(shown, style=style)
        if more:
            cell.append(more, style="dim")
        return cell

    def _fill_grid(self) -> None:
        grid = self.query_one("#fm-grid", DataTable)
        col = grid.cursor_column
        grid.clear(columns=True)
        self._shown = self.keys()
        grid.add_column(Text("#\n", style="bold"), width=3, key="#")
        for k in self._shown:
            grid.add_column(self._header(k), width=CELL, key="\t".join(k))
        for r in range(len(self.group.cells)):
            grid.add_row(Text(str(r + 1), style="bold"), *[self._cell(k, r) for k in self._shown], key=str(r))
        if self.field in self._shown:
            col = self._shown.index(self.field) + 1
        if self._shown and self.group.cells:
            grid.move_cursor(row=min(self.record, len(self.group.cells) - 1),
                             column=min(max(col, 1), len(self._shown)))
        if self.field not in self._shown:
            self.field = self._shown[0] if self._shown else None
        self._field_options()
        self._sync()

    def _field_options(self) -> None:
        """Selecionar campo: every column of the grid, then a new fixed text."""
        opts = []
        for k in self._shown:
            row = self.rows[k]
            name = row.source if row.kind != "fixed" else t("fixed text")
            opts.append((f"{self.campo(k)} ({name})", "\t".join(k)))
        opts.append((t("+ New fixed text for every record"), NEW_FIXED))
        sel = self.query_one("#fm-field", Select)
        sel.set_options(opts)
        if self.field:
            sel.value = "\t".join(self.field)

    def _sync(self) -> None:
        """Everything that follows the cursor: the example, the cell line, the
        mapping card, the LoC link and the counts."""
        n = len(self.group.cells)
        self.query_one("#fm-example", Label).update(
            t("Example ${i} of ${n}", i=self.record + 1 if n else 0, n=n))
        field = self.query_one("#fm-field", Select)
        if self.field and field.value != "\t".join(self.field):
            field.value = "\t".join(self.field)
        self._sync_editor()
        self._cell_line()
        self._refresh()

    def _dest_options(self, row: Row) -> list[tuple[str, str]]:
        """Função for a column: keep it, a custom TAG$subfield, a fixed text,
        leave it out, Paulo's list, then the fields of the other columns."""
        if row.kind == "fixed":
            opts = [(t("Custom field (type it, e.g. ${ref})", ref="820$a"), OTHER),
                    (t("[Remove this fixed text]"), IGNORE)]
        else:
            what = self.dest_text(row) if row.proposal != KEEP else row.source
            keep = f"{self.campo(row.key)} ({what}) {t('(keep)')}"
            opts = [(keep, KEEP), (t("Custom field (type it, e.g. ${ref})", ref="820$a"), OTHER),
                    (t("Fixed text for every record"), FIXED), (t("[Do not import this field]"), IGNORE)]
        seen = {v for _, v in opts}
        for x in self.data.get("targets", []):
            if x["to"] not in seen:
                opts.append((f"{x['to']} - {t(x['label'])}", x["to"]))
                seen.add(x["to"])
        for k in self.group.keys:
            other = self.rows[k]
            to = other.proposal
            if k != row.key and to not in seen and _REF.match(to or ""):
                opts.append((f"{self.campo(k)} ({ref_label(to)})", to))
                seen.add(to)
        return opts

    def _dest_value(self, row: Row | None) -> str:
        """The Função picker's value for a column."""
        if row is None:
            return KEEP
        if row.kind == "fixed":
            return row.to if row.to in {v for _, v in self._dest_options(row)} else OTHER
        if row.text:
            return FIXED
        if row.to == row.proposal:
            return KEEP
        return row.to if row.to in {v for _, v in self._dest_options(row)} else OTHER

    def _sync_editor(self) -> None:
        row = self.rows.get(self.field) if self.field else None
        card = self.query_one("#fm-map")
        card.border_title = t("Mapping of ${field}", field=self.campo(row.key)) if row else t("Mapping")
        dest = self.query_one("#fm-dest", Select)
        custom, text = self.query_one("#fm-custom", Input), self.query_one("#fm-text", Input)
        dest.disabled = row is None
        if row is not None:
            dest.set_options(self._dest_options(row))
            value = self._dest_value(row)
            dest.value = value
            fixed = row.kind == "fixed" or value == FIXED
            custom.display = value == OTHER or fixed
            text.display = fixed
            custom.value = row.to if _REF.match(row.to or "") and (value == OTHER or fixed) else ""
            if fixed and not custom.value and _REF.match(row.proposal or ""):
                custom.value = row.proposal
            text.value = row.text
        else:
            custom.display = text.display = False
        self.query_one("#fm-inputs").display = custom.display or text.display
        tag = row.to if row and _REF.match(row.to or "") else (row.source if row and row.kind == "marc" else "")
        link = self.query_one("#fm-loc-tag", Button)
        link.display = bool(tag) and marc21.loc_url(tag) != marc21.LOC
        link.label = t("Field ${tag} ↗", tag=tag.partition("$")[0])
        self._error("")

    def _cell_line(self) -> None:
        box = self.query_one("#fm-cell", Label)
        if not self.field:
            box.update(t("Pick a cell of the grid."))
            return
        row = self.rows[self.field]
        vals = self.values(self.field)
        head = t("${field} · example ${i}", field=self.campo(self.field), i=self.record + 1)
        if not vals:
            box.update(Text(head + ": " + t("This example does not have this field."), style="dim"))
            return
        v = vals[0]
        line = Text(head + ": ", style="bold")
        line.append(v.replace("\n", " "))
        line.append("  · " + t("${n} character(s)", n=len(v)), style="dim")
        if len(vals) > 1:
            line.append(f"  · ×{len(vals)}", style="dim")
        found = warnings(v, row.source)
        if found:
            line.append("  ⚠ " + ", ".join(found), style="yellow")
        box.update(line)

    def _refresh(self) -> None:
        n = self.changed()
        dropped = sum(1 for r in n if r.to == IGNORE)
        dirty = sum(1 for row in self.group.cells for vals in row for v in vals if warnings(v))
        self.query_one("#fm-count", Label).update(
            t("${n} change(s) · ${k} left out · ${w} warning(s)", n=len(n) - dropped, k=dropped, w=dirty))
        self._option_note()

    def _option_note(self) -> None:
        """What the chosen options do to the sample."""
        box = self.query_one("#fm-opt-note", Static)
        if not any(self.options.values()):
            box.update("")
            return
        if not self.group.records:
            box.update(Text(t("Applied to the records built from this file when importing."), style="dim"))
            return
        parts = []
        try:
            fmap = self.fm.FieldMap.from_obj(self.mapping())
            stats = Counter()
            done = [fmap.apply(r, stats) for r in self.group.records]
            if self.options["clean"]:
                parts.append(t("${n} value(s) repaired", n=stats["cleaned"]))
            if self.options["case"]:
                parts.append(t("${n} value(s) recased", n=stats["recased"]))
            if self.options["group"]:
                pairs = sys.modules["kei_import.tidy"].group_sample(done) if "kei_import.tidy" in sys.modules else []
                parts.append(t("${n} record(s) join another", n=len(pairs)) if pairs else
                             t("no copies to join in the sample"))
        except Exception:  # noqa: BLE001 - an engine without the options
            box.update(Text(t("The preview needs the engine of this panel version; the mapping still works."),
                            style="dim"))
            return
        box.update(Text(t("In the sample: ${what}.", what=" · ".join(parts)), style="dim"))

    def preview_text(self) -> Text:
        """The example as Koha will get it (▸ marks what changed)."""
        if not self.group.records:
            if self.group.gid.startswith("t"):
                return self._table_preview()
            return Text(t("The preview needs the engine of this panel version; the mapping still works."))
        src = self.group.records[min(self.record, len(self.group.records) - 1)]
        old = src.formatted().splitlines()
        if self.before:
            return Text("\n".join(old))
        try:
            after = self.fm.FieldMap.from_obj(self.mapping()).apply(src).formatted().splitlines()
        except self.fm.FieldMapError as e:
            return Text(str(e))
        seen = set(old)
        text = Text()
        for line in after:
            text.append(("▸ " if line not in seen else "  ") + line + "\n", style="bold" if line not in seen else "")
        return text

    def _table_preview(self) -> Text:
        """A spreadsheet row and where each value goes (the engine builds the
        record itself, with its own rules)."""
        text = Text()
        for k in self.keys():
            row = self.rows[k]
            vals = self.values(k)
            if not vals:
                continue
            to = self.dest_text(row).split(" - ")[0]
            text.append(f"{row.source[:20]:<20} → {to:<10} ", style="bold" if row.changed else "")
            text.append(vals[0][:60] + "\n", style="strike dim" if row.to == IGNORE else "")
        return text

    # ------------------------------------------------------------ changes

    def _set(self, to: str, text: str | None = None) -> None:
        row = self.rows.get(self.field) if self.field else None
        if row is None:
            return
        fixed = text is not None
        why = self.check(row, to) if (to != row.proposal or fixed) else ""
        if fixed and not text.strip() and row.kind != "fixed":
            why = t("Type the text to write in every record.")
        self._error(why)
        if why:
            return
        row.to = to
        if fixed:
            row.text = text.strip()
        elif row.kind != "fixed":
            row.text = ""
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
        """Enter on a cell: on to its function."""
        if self.field:
            self.query_one("#fm-dest", Select).focus()

    @on(Select.Changed, "#fm-group")
    def _group_changed(self, event: Select.Changed) -> None:
        self.group = next(g for g in self.groups if g.gid == event.value)
        self.record, self.field = 0, None
        self.resize_grid(self.grid_height)
        self._fill_grid()

    @on(Select.Changed, "#fm-field")
    def _field_changed(self, event: Select.Changed) -> None:
        value = event.value
        if not isinstance(value, str) or (self.field and value == "\t".join(self.field)):
            return                      # the picker following the cursor
        if value == NEW_FIXED:
            self.field = self._new_fixed()
            self._fill_grid()
            self.query_one("#fm-custom", Input).focus()
            return
        key = tuple(str(value).split("\t", 1))
        if key in self._shown:
            self.field = key
            self.query_one("#fm-grid", DataTable).move_cursor(column=self._shown.index(key) + 1)
            self._sync()

    @on(Select.Changed, "#fm-dest")
    def _dest_changed(self, event: Select.Changed) -> None:
        row = self.rows.get(self.field) if self.field else None
        if row is None or not isinstance(event.value, str) or event.value == self._dest_value(row):
            return                      # the picker following the cursor, not a choice
        custom, text = self.query_one("#fm-custom", Input), self.query_one("#fm-text", Input)
        if event.value in (OTHER, FIXED):
            custom.display = True
            text.display = event.value == FIXED or row.kind == "fixed"
            self.query_one("#fm-inputs").display = True
            if not custom.value and _REF.match(row.proposal or ""):
                custom.value = row.proposal
            (text if event.value == FIXED and custom.value else custom).focus()
            return
        if row.kind == "fixed":
            if event.value == IGNORE:
                self._remove_fixed(row.key)
            else:
                self._set(str(event.value), row.text)
            return
        self._set(row.proposal if event.value == KEEP else str(event.value))

    @on(Input.Submitted, "#fm-custom")
    @on(Input.Submitted, "#fm-text")
    def _typed(self, event: Input.Submitted) -> None:
        row = self.rows.get(self.field) if self.field else None
        if row is None:
            return
        custom = self.query_one("#fm-custom", Input).value.strip()
        text = self.query_one("#fm-text", Input)
        if text.display:
            if event.input.id == "fm-custom" and not text.value.strip():
                text.focus()
                return
            self._set(custom or IGNORE, text.value)
        elif custom:
            self._set(custom)
        if not self.query_one("#fm-error", Label).display:
            self.query_one("#fm-grid", DataTable).focus()

    @on(Checkbox.Changed)
    def _option(self, event: Checkbox.Changed) -> None:
        name = (event.checkbox.id or "").removeprefix("fm-opt-")
        if name in self.options:
            self.options[name] = event.value
            self._refresh()

    @on(Button.Pressed, "#fm-loc")
    def _loc(self) -> None:
        self.app.open_url(marc21.LOC)

    @on(Button.Pressed, "#fm-loc-tag")
    def _loc_tag(self) -> None:
        row = self.rows.get(self.field) if self.field else None
        if row:
            tag = row.to if _REF.match(row.to or "") else row.source
            self.app.open_url(marc21.loc_url(tag))

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

    @on(Button.Pressed, "#fm-show-preview")
    def action_preview(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.app.push_screen(RecordPreviewScreen(self))

    @on(Button.Pressed, "#fm-reset")
    def _reset(self) -> None:
        for k in self.fixed:
            del self.rows[k]
        self.fixed = []
        for r in self.rows.values():
            r.to, r.text = r.proposal, ""
        for k in self.options:
            self.options[k] = False
            self.query_one(f"#fm-opt-{k}", Checkbox).value = False
        self.field = None
        self._fill_grid()

    @on(Button.Pressed, "#fm-skip")
    def action_skip(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#fm-apply")
    def action_apply(self) -> None:
        obj = self.mapping()
        if not obj["mappings"] and not obj.get("options"):
            self.dismiss(False)
            return
        try:
            with open(self._out, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False, indent=1)
                fh.write("\n")
        except OSError as exc:
            self._error(f"{self._out}: {exc.strerror}")
            return
        self.dismiss(True)
