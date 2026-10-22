"""Edit & Map Fields (Magic Import, docs/field-mapping.md), laid out after
the librarians' own sketch (exemplo ferramenta de importação.xlsx):

  - on top, the import mode of the file (Bibliographic, Patrons or
    Authorities: what was detected is marked, a click switches it) and a
    grid of the sample: one row per record, one column per field or
    spreadsheet column, headed "campo N · 245$a" over where it goes
    ("245$a (Title)", "city (City)"); a bar under it is dragged (or
    Ctrl+Up/Down) to make the grid taller;
  - below, "Selecionar campo" and "Função" (keep, a field from the list, a
    custom TAG$subfield typed by hand, a fixed text for every record, or
    leave out), and beside them "Mais opções": the Library of Congress
    link, join copies of the same book, recase capitals, safe spelling
    repair (tidy.py in the engine);
  - "Valores do Koha": the instance's own libraries, item types and patron
    categories in lists (defaults for the rows without one, and the
    from/to list of the codes the file has: MAIN -> CA), the missing
    barcode policy and the saved mapping profiles;
  - the record Koha will get opens from "Record preview", and "Check the
    whole file" runs the engine's real build without touching Koha.

The row under the cursor is the example ("Example N of 10") everywhere. The
preview runs the engine's own modules (kei_import/fieldmap.py and
mapping.py), imported from the engine folder the routine names, so the
screen and the import never disagree; without them the screen still maps.

fields.json comes in two versions: 1 (MARC streams and spreadsheet tables
with names as keys, the mapping {"version": 1}) and 2 (opaque source IDs,
one mode per stream or table, the mapping {"version": 2}); the screen
writes back the version it read."""

from __future__ import annotations

import asyncio
import copy
import importlib
import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select, Static

from .. import koha_fields, marc21
from ..i18n import t

KEEP, OTHER, FIXED, IGNORE = "keep", "other", "fixed", "ignore"
NEW_FIXED = "+fixed"
OPTIONS = ("group", "case", "clean")
MODES = ("bibliographic", "patrons", "authorities")
MODE_NAMES = {"bibliographic": "Bibliographic", "patrons": "Patrons", "authorities": "Authorities"}
_REF = re.compile(r"^[0-9A-Za-z]{3}(\$[0-9a-z])?$")
CELL = 26                       # width of a grid column
WIDE = 140                      # mapping and options side by side from this width
CODES_SHOWN = 12                # values of a code column in the from/to list
_MOJIBAKE = re.compile("[ÃÂ][\u0080-¿ŒœŠšŸŽžƒˆ˜–-™]|â€|�")
_ISBN = re.compile(r"^(97[89][- ]?)?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?[\dXx]$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})|^(\d{1,2})/(\d{1,2})/(\d{4})")
_TSV_ESCAPES = {"0": "\0", "n": "\n", "r": "\r", "t": "\t", "b": "\b", "Z": "\x1a", "\\": "\\"}
# Destinations each copy, patron or user has once in the whole file.
UNIQUE = {"952$p", "cardnumber", "userid"}
DATE_DESTS = {"dateofbirth", "dateenrolled", "dateexpiry", "date_renewed", "password_expiration_date",
              "debarred", "952$d"}
REQUIRED = {"patrons": ("surname",)}


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


def _engine_module(name: str):
    """A module of the engine load_engine found (kei_import.mapping...)."""
    if "kei_import" not in sys.modules:
        return None
    try:
        return importlib.import_module("kei_import." + name)
    except Exception:  # noqa: BLE001 - an engine before version 2
        return None


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


def isbn_ok(value: str) -> bool:
    digits = re.sub(r"[^0-9Xx]", "", value.split(" ")[0])
    if len(digits) == 10:
        total = sum((10 - i) * (10 if c in "Xx" else int(c)) for i, c in enumerate(digits))
        return total % 11 == 0
    if len(digits) == 13 and digits.isdigit():
        return sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(digits)) % 10 == 0
    return False


def cpf_ok(value: str) -> bool:
    d = re.sub(r"\D", "", value)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        check = sum(int(d[i]) * (n + 1 - i) for i in range(n)) * 10 % 11 % 10
        if check != int(d[n]):
            return False
    return True


def date_ok(value: str) -> bool:
    m = _DATE.match(value.strip())
    if not m:
        return False
    y, mo, d = (m[1], m[2], m[3]) if m[1] else (m[6], m[5], m[4])
    try:
        date(int(y), int(mo), int(d))
    except ValueError:
        return False
    return True


def problems(value: str, dest: str) -> list[str]:
    """What is wrong with a value for where it goes (a yellow cell)."""
    v = value.strip()
    if not v or dest in (IGNORE, KEEP, ""):
        return []
    out = []
    if dest == "020$a" and re.match(r"^[\dXx -]{10,17}", v) and not isbn_ok(v):
        out.append(t("invalid ISBN (check digit)"))
    if dest in ("email", "emailpro", "B_email") and not _EMAIL.match(v):
        out.append(t("not an email address"))
    if dest in DATE_DESTS and not date_ok(v):
        out.append(t("not a date"))
    if re.fullmatch(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", v) and not cpf_ok(v):
        out.append(t("invalid CPF (check digit)"))
    return out


def ref_label(ref: str) -> str:
    """"245$a (Title)" (translated), or the reference alone."""
    name = marc21.label(ref)
    return f"{ref} ({t(name)})" if name else ref


def dest_label(to: str, mode: str = "bibliographic") -> str:
    """Where a value goes, code and name: "245$a (Title)", "city (City)"."""
    if mode == "patrons":
        name = koha_fields.PATRON_LABELS.get(to)
        return f"{to} ({t(name)})" if name else to
    if mode == "authorities":
        name = koha_fields.AUTHORITY_LABELS.get(to)
        return f"{to} ({t(name)})" if name else ref_label(to)
    return ref_label(to)


def _plain(text: str) -> str:
    """Code or name compared without case, accents or spaces."""
    import unicodedata
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def read_codes(folder: Path, name: str) -> list[tuple[str, str]]:
    """The instance's codes the routine exported next to fields.json
    (branches.tsv: code TAB name, mysql -N escapes), [] when absent."""
    try:
        lines = (folder / f"{name}.tsv").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    out = []
    for line in lines:
        parts = [re.sub(r"\\(.)", lambda m: _TSV_ESCAPES.get(m[1], m[1]), p) for p in line.split("\t")]
        if parts and parts[0].strip():
            out.append((parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""))
    return out


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
        self.table = table              # the group (version 2) or table name (version 1)
        self.id = key[1]                # the engine's source ID (version 2)
        self.unsure = False             # the engine's best guess, to check
        self.proposals: dict[str, str] = {}
        self.codes: dict[str, int] = {}
        self.rule: dict = {}

    @property
    def changed(self) -> bool:
        return self.to != self.proposal or bool(self.text)


class Group:
    """One stream of records or one table: its columns and sample rows,
    each row a list of the values of every column (a list: a field can
    repeat in a record)."""

    def __init__(self, gid: str, label: str, keys: list[tuple[str, str]], cells: list[list[list[str]]],
                 records: list | None = None, kind: str = "marc", mode: str = "bibliographic",
                 source_id: str = "", codes: dict | None = None, name: str = ""):
        self.gid = gid
        self.label = label
        self.keys = keys
        self.cells = cells
        self.records = records or []    # engine Records (MARC streams, with the engine)
        self.kind = kind                # marc | table
        self.mode = mode
        self.detected = mode
        self.source_id = source_id
        self.codes = codes or {}        # MARC streams: {"952$a": {"MAIN": 18624}}
        self.name = name


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


class CheckReportScreen(ModalScreen[None]):
    """What the engine's real build of the whole file found (nothing is
    written to Koha): the errors to fix and the warnings to look at."""

    BINDINGS = [Binding("escape", "close", t("Close"))]

    def __init__(self, text: Text):
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog fieldmap-preview"):
            yield Label(t("Check of the whole file"), classes="dialog-title", markup=False)
            with VerticalScroll(id="fmp-scroll"):
                yield Static(self._text, id="fmc-report")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Close"), id="fmc-close", variant="primary")

    @on(Button.Pressed, "#fmc-close")
    def action_close(self) -> None:
        self.dismiss(None)


class FieldMapScreen(ModalScreen[bool]):
    """Answers True when it wrote a mapping to out_path; False when the
    librarian skipped (or, with a version 1 file, changed nothing): the
    import goes on as it is."""

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
        self.v2 = self.data.get("version", 1) >= 2
        self.fm = load_engine(engine_dir)
        self.mapper = _engine_module("mapping") if self.fm and self.v2 else None
        self.review = _engine_module("review") if self.fm and self.v2 else None
        self.base = copy.deepcopy(self.data.get("mapping") or {}) if self.v2 else {}
        self.rows: OrderedDict[tuple[str, str], Row] = OrderedDict()
        self.groups: list[Group] = []
        self.fixed: list[tuple[str, str]] = []      # keys of the fixed-text columns
        self.options = {k: False for k in OPTIONS}
        # The instance's codes, exported by the routine next to fields.json.
        folder = Path(fields_path).parent
        self.koha = {kind: read_codes(folder, kind) for kind in ("branches", "itemtypes", "categories", "locations")}
        context = (self.data.get("context") or {}).get("options") or {}
        saved = self.base.get("defaults", {})
        self.defaults = {
            "branches": str(saved.get("952$a", saved.get("branchcode", context.get("branch") or ""))),
            "itemtypes": str(saved.get("952$y", saved.get("942$c", context.get("itype") or ""))),
            "categories": str(saved.get("categorycode", context.get("category") or "")),
        }
        for kind, value in self.defaults.items():
            if not value and len(self.koha.get(kind, [])) == 1:
                self.defaults[kind] = self.koha[kind][0][0]
        self.remaps: dict[str, dict[str, str]] = {kind: {} for kind in ("branches", "itemtypes", "categories", "locations")}
        self.barcodes = self.base.get("barcode_policy", "review")
        self.sensitive = self.base.get("allow_restricted") is True
        self.profiles = Path(context["profiles"]) if context.get("profiles") else folder / "profiles"
        self._build()
        if self.v2:
            self._load_remaps(self.base.get("remaps") or {})
            self._apply_saved_v2()
            self._seed_remaps()
        else:
            self._apply_saved(self.data.get("mapping") or {})
        self.group = self.groups[0] if self.groups else Group("", "", [], [])
        self.record = 0
        self.field: tuple[str, str] | None = None
        self.before = False
        self.grid_height = 0            # set on mount, then by the splitter
        self._shown: list[tuple[str, str]] = []
        self._code_rows: list[tuple[str, str]] = []
        self._checking = False

    # ------------------------------------------------------------ data

    def _build(self) -> None:
        if self.v2:
            self._build_v2()
            return
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
            self.groups.append(Group(f"s{i}", label, keys, cells, records, name=s.get("name", "")))
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
            self.groups.append(Group(f"t{i}", label, keys, cells, kind="table", name=tb.get("name", "")))

    def _build_v2(self) -> None:
        """Version 2: every stream and table has its own mode and every
        field or column an opaque ID; the saved rules are keyed by it."""
        rules = {r.get("source"): r for r in self.base.get("mappings", []) if isinstance(r, dict)}
        source_modes = self.base.get("source_modes", {})
        table_modes = self.base.get("table_modes", {})
        for s in self.data.get("streams", []):
            recs = s.get("records", [])
            mode = source_modes.get(s.get("source_id"), "auto")
            mode = s.get("mode", "bibliographic") if mode in ("auto", None) else mode
            keys = []
            for f in s.get("fields", []):
                key = ("marc", f["id"])
                ref = f.get("ref", "")
                row = Row(key, ref, "marc", f.get("to") or ref, f.get("count", 0), len(recs), table=s["id"])
                row.proposals = {m: ref for m in MODES if m != "patrons"}
                row.rule = copy.deepcopy(rules.get(f["id"], {}))
                if row.rule.get("to"):
                    row.to = row.rule["to"]
                self.rows[key] = row
                keys.append(key)
            cells = [[marc_values(r, self.rows[k].source) for k in keys] for r in recs]
            label = t("${name} · ${n} record(s) · sample of ${k}", name=s.get("name", ""),
                      n=f"{s.get('records_total', 0):,}", k=len(recs))
            records = [self.fm.record_from_obj(r) for r in recs] if self.fm else []
            g = Group(s["id"], label, keys, cells, records, kind="marc", mode=mode if mode in MODES else "bibliographic",
                      source_id=s.get("source_id", s["id"]), codes=s.get("codes", {}), name=s.get("name", ""))
            g.detected = s.get("mode", g.mode) if s.get("mode") in MODES else g.mode
            self.groups.append(g)
        columns = {c["id"]: c for c in self.data.get("columns", [])}
        for tb in self.data.get("tables", []):
            ids = tb.get("columns", [])
            headers = tb.get("headers", [])
            mode = table_modes.get(tb["id"], "auto")
            mode = tb.get("mode", "bibliographic") if mode in ("auto", None) else mode
            mode = mode if mode in MODES else "bibliographic"
            keys = []
            for i, cid in enumerate(ids):
                c = columns.get(cid, {})
                key = ("column", cid)
                header = c.get("header") or (headers[i] if i < len(headers) else cid)
                row = Row(key, header, "column", c.get("to") or IGNORE, table=tb["id"])
                row.proposals = dict(c.get("proposals") or {mode: row.proposal})
                row.proposals.setdefault(mode, row.proposal)
                row.unsure = bool(c.get("unsure")) and row.proposal != IGNORE
                row.codes = dict(c.get("codes") or {})
                row.rule = copy.deepcopy(rules.get(cid, {}))
                if row.rule.get("to"):
                    row.to = row.rule["to"]
                    if row.to != row.proposal:
                        row.unsure = False
                self.rows[key] = row
                keys.append(key)
            cells = [[[r[i]] if i < len(r) and r[i] not in ("", None) else [] for i in range(len(ids))]
                     for r in tb.get("rows", [])]
            for n, k in enumerate(keys):
                self.rows[k].total = len(cells)
                self.rows[k].count = sum(1 for c in cells if c[n])
            label = t("${name} · ${n} row(s) · sample of ${k}", name=tb.get("name", ""),
                      n=f"{tb.get('rows_total', len(cells)):,}", k=len(cells))
            g = Group(tb["id"], label, keys, cells, kind="table", mode=mode, source_id=tb.get("source", ""),
                      name=tb.get("name", ""))
            g.detected = tb.get("mode", mode) if tb.get("mode") in MODES else mode
            self.groups.append(g)

    def _apply_saved_v2(self) -> None:
        """Fixed texts and options of a mapping being looked at again."""
        by_source = {g.source_id: g for g in self.groups if g.kind == "marc"}
        for m in self.base.get("mappings", []):
            src = m.get("source", "")
            if isinstance(src, str) and src.startswith("="):
                g = by_source.get(m.get("stream")) or next((x for x in self.groups if x.mode == m.get("mode")), None)
                self._new_fixed(src[1:].strip(), m.get("to", ""), g.gid if g else "")
        for k, v in (self.base.get("options") or {}).items():
            if k in self.options:
                self.options[k] = bool(v)

    def _load_remaps(self, remaps: dict) -> None:
        kinds = {"952$a": "branches", "952$b": "branches", "branchcode": "branches", "952$y": "itemtypes",
                 "942$c": "itemtypes", "952$c": "locations", "categorycode": "categories"}
        for target, table in remaps.items():
            kind = kinds.get(target)
            if kind and isinstance(table, dict):
                self.remaps[kind].update({str(k): str(v) for k, v in table.items()})

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

    def _new_fixed(self, text: str = "", to: str = "", gid: str | None = None) -> tuple[str, str]:
        n = max((int(k[1]) for k in self.fixed), default=0) + 1
        key = ("fixed", str(n))
        row = Row(key, t("fixed text ${n}", n=n), "fixed", IGNORE)
        row.to, row.text = to or IGNORE, text
        row.table = gid if gid is not None else (self.group.gid if hasattr(self, "group") else "")
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

    def group_of(self, row: Row) -> Group | None:
        return next((g for g in self.groups if g.gid == row.table), None)

    def mode_of(self, row: Row | None = None) -> str:
        if not self.v2:
            return "bibliographic"
        g = self.group_of(row) if row is not None else self.group
        return g.mode if g else "bibliographic"

    def mapping(self) -> dict:
        if self.v2:
            return self._mapping_v2()
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

    def _mapping_v2(self) -> dict:
        """The version 2 mapping the next build (and the preview) uses."""
        obj = copy.deepcopy(self.base)
        mappings, seen = [], set()
        table_modes = dict(obj.get("table_modes") or {})
        source_modes = dict(obj.get("source_modes") or {})
        for g in self.groups:
            if g.kind == "table":
                table_modes[g.gid] = g.mode
            else:
                source_modes[g.source_id] = g.mode
            for key in g.keys:
                row = self.rows[key]
                rule = copy.deepcopy(row.rule)
                rule.update(source=row.id, mode=g.mode, to=IGNORE if row.text else row.to)
                if g.kind == "table":
                    rule["table"] = g.gid
                else:
                    rule.update(ref=row.source, stream=g.source_id)
                if rule.get("transform") == "split_name" and (g.mode != "patrons" or rule["to"] != "surname"):
                    rule.pop("transform")
                if rule.get("transform") == "prefix" and rule["to"] == IGNORE:
                    rule.pop("transform")
                    rule.pop("prefix", None)
                rule.pop("value", None)
                mappings.append(rule)
                if row.text and row.to != IGNORE and ("=" + row.text, g.mode) not in seen:
                    seen.add(("=" + row.text, g.mode))
                    fixed = {"source": "=" + row.text, "to": row.to, "mode": g.mode}
                    if g.kind == "marc":
                        fixed["stream"] = g.source_id
                    mappings.append(fixed)
            for key in self.fixed:
                row = self.rows[key]
                if row.table != g.gid or not row.text or row.to == IGNORE or ("=" + row.text, g.mode) in seen:
                    continue
                seen.add(("=" + row.text, g.mode))
                fixed = {"source": "=" + row.text, "to": row.to, "mode": g.mode}
                if g.kind == "marc":
                    fixed["stream"] = g.source_id
                mappings.append(fixed)
        modes = {g.mode for g in self.groups} or {"bibliographic"}
        obj.update(version=2, mappings=mappings, table_modes=table_modes, source_modes=source_modes,
                   mode=self.groups[0].mode if self.groups else obj.get("mode", "bibliographic"))
        options = {k: v for k, v in (obj.get("options") or {}).items() if k not in OPTIONS}
        options.update({k: True for k, v in self.options.items() if v})
        obj["options"] = options
        defaults = {k: v for k, v in (obj.get("defaults") or {}).items()
                    if k not in ("branchcode", "categorycode", "952$a", "952$b", "952$y", "942$c")}
        remaps = {k: v for k, v in (obj.get("remaps") or {}).items()
                  if k not in ("branchcode", "categorycode", "952$a", "952$b", "952$c", "952$y", "942$c")}
        targets = []
        if "bibliographic" in modes:
            targets += [("branches", ("952$a", "952$b")), ("itemtypes", ("952$y", "942$c")), ("locations", ("952$c",))]
        if "patrons" in modes:
            targets += [("branches", ("branchcode",)), ("categories", ("categorycode",))]
        for kind, refs in targets:
            table = {k: v for k, v in self.remaps.get(kind, {}).items() if v and v != k}
            for ref in refs:
                if table:
                    remaps[ref] = dict(table)
                default = self.defaults.get(kind, "")
                if default and ref != "952$c":
                    defaults[ref] = default
        obj["defaults"], obj["remaps"] = defaults, remaps
        obj["barcode_policy"] = self.barcodes
        if self.sensitive:
            obj["allow_restricted"] = True
        else:
            obj.pop("allow_restricted", None)
        for key in ("defaults", "remaps", "options"):
            if not obj[key]:
                del obj[key]
        return obj

    def check(self, row: Row, to: str) -> str:
        """"" when row can go to `to`, else why not."""
        mode = self.mode_of(row)
        if to == IGNORE and not (row.kind == "fixed" or row.text):
            return ""
        if mode == "patrons":
            if to == IGNORE:
                return t("Pick the patron field the text goes to.")
            if to not in koha_fields.PATRON_LABELS:
                return t("${field} is not a Koha patron field.", field=to)
            if self.mapper and to in self.mapper.RESTRICTED_FIELDS and not self.sensitive:
                return t("${field} is a sensitive field: tick \"Show sensitive patron fields\" first.", field=to)
            return ""
        if to != IGNORE and not _REF.match(to):
            return t("Type a MARC destination as ${ref}, for example ${example}.", ref="TAG$subfield", example="590$a")
        if row.kind == "fixed" or row.text:
            if to == IGNORE:
                return t("Type the field the text goes to, for example ${example}.", example="942$c")
            if "$" not in to and to >= "010":
                return t("A fixed text needs a subfield: ${ref}.", ref="TAG$subfield")
            return self._mode_check(mode, to)
        if self.fm:
            try:
                self.fm.Rule(row.source if row.kind == "marc" else "000$a", to, "column" if row.kind == "column" else None)
            except self.fm.FieldMapError as e:
                return str(e)
        elif row.kind == "column" and "$" not in to:
            return t("A column needs a subfield: ${ref}.", ref="TAG$subfield")
        return self._mode_check(mode, to)

    def _mode_check(self, mode: str, to: str) -> str:
        if self.mapper and mode == "authorities":
            try:
                self.mapper.MappingSpec.from_obj({"version": 2, "mode": mode,
                                                  "mappings": [{"source": "check", "to": to}]})
            except ValueError as e:
                return str(e)
        return ""

    def keys(self) -> list[tuple[str, str]]:
        """The grid's columns: the group's fields, then its fixed texts."""
        return list(self.group.keys) + [k for k in self.fixed if self.rows[k].table in (self.group.gid, "")]

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
        return dest_label(row.to, self.mode_of(row))

    def dest_of(self, row: Row) -> str:
        """The destination a column's values end up in (its source for a
        MARC field kept as it is)."""
        if row.to == KEEP:
            return row.source if row.kind == "marc" else ""
        return row.to

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
            with Horizontal(id="fm-modes"):
                yield Label(t("Import as:"), id="fm-modes-q")
                for mode in MODES:
                    yield Button(t(MODE_NAMES[mode]), id=f"fm-mode-{mode}", classes="fm-mode")
                yield Label("", id="fm-mode-note", markup=False)
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
                            yield Input(placeholder="820$a", id="fm-custom", max_length=24)
                            yield Input(placeholder=t("text for every record"), id="fm-text")
                        yield Label("", id="fm-error", classes="dialog-error", markup=False)
                        with Vertical(id="fm-codes"):
                            yield Label("", id="fm-codes-title", classes="fm-section", markup=False)
                            yield Vertical(id="fm-codes-list")
                    with Vertical(id="fm-side"):
                        with Vertical(id="fm-more", classes="fm-card"):
                            yield Label(t("Want to know the fields better?"), id="fm-loc-q")
                            with Horizontal(id="fm-loc-bar"):
                                yield Button(t("MARC 21 (Library of Congress) ↗"), id="fm-loc", classes="fm-link")
                                yield Button("", id="fm-loc-tag", classes="fm-link")
                            with Vertical(id="fm-tidy"):
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
                            yield Checkbox(t("Show sensitive patron fields (password, permissions...)"), self.sensitive,
                                           id="fm-sensitive")
                        if self.v2:
                            with Vertical(id="fm-koha", classes="fm-card"):
                                yield Label(t("For the rows that do not have one, use:"), classes="fm-section")
                                with Horizontal(classes="fm-line", id="fm-def-branches-line"):
                                    yield Label(t("Library"), classes="fm-key")
                                    yield Select(self._code_options("branches"), id="fm-def-branches",
                                                 prompt=t("Choose a library"))
                                with Horizontal(classes="fm-line", id="fm-def-itemtypes-line"):
                                    yield Label(t("Item type"), classes="fm-key")
                                    yield Select(self._code_options("itemtypes"), id="fm-def-itemtypes",
                                                 prompt=t("Choose an item type"))
                                with Horizontal(classes="fm-line", id="fm-def-categories-line"):
                                    yield Label(t("Patron category"), classes="fm-key")
                                    yield Select(self._code_options("categories"), id="fm-def-categories",
                                                 prompt=t("Choose a category"))
                                with Horizontal(classes="fm-line", id="fm-barcodes-line"):
                                    yield Label(t("No barcode"), classes="fm-key")
                                    yield Select([(t("Stop and show me those copies"), "review"),
                                                  (t("Create a barcode for them"), "generate")],
                                                 value=self.barcodes if self.barcodes in ("review", "generate") else "review",
                                                 allow_blank=False, id="fm-barcodes")
                                yield Label(t("Mapping profiles (for the next files from the same system)"),
                                            classes="fm-section")
                                with Horizontal(classes="fm-line"):
                                    yield Input(placeholder=t("Profile name, e.g. Pergamum campus"), id="fm-prof-name")
                                    yield Button(t("Save"), id="fm-prof-save")
                                with Horizontal(classes="fm-line"):
                                    yield Select(self._profile_options(), id="fm-prof-list", prompt=t("Saved profiles"))
                                    yield Button(t("Use"), id="fm-prof-load")
                                yield Label("", id="fm-prof-note", markup=False)
            with Horizontal(classes="dialog-buttons", id="fm-foot"):
                yield Label("", id="fm-count", markup=False)
                yield Button(t("Record preview"), id="fm-show-preview")
                if self.v2:
                    yield Button(t("Check the whole file"), id="fm-check")
                yield Button(t("Reset"), id="fm-reset")
                yield Button(t("Skip: import as it is"), id="fm-skip")
                yield Button(t("Apply"), id="fm-apply", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#fm-map").border_title = t("Mapping")
        self.query_one("#fm-more").border_title = t("More options")
        if self.v2:
            self.query_one("#fm-koha").border_title = t("Values of this Koha")
            for kind in ("branches", "itemtypes", "categories"):
                sel = self.query_one(f"#fm-def-{kind}", Select)
                if self.defaults.get(kind) in {c for c, _ in self.koha.get(kind, [])}:
                    sel.value = self.defaults[kind]
        self._error("")
        self.grid_height = min(len(self.group.cells) + 5, max(self.app.size.height * 2 // 5, 7))
        self._layout()
        self._modes()
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
        most = max(self.app.size.height - 19, 6)   # title, header, modes, splitter, a card and the buttons stay
        self.grid_height = max(5, min(height, most, len(self.group.cells) + 5 if self.group.cells else 5))
        self.query_one("#fm-grid").styles.height = self.grid_height

    def action_grow(self, step: int) -> None:
        self.resize_grid(self.grid_height + step)

    def _error(self, text: str) -> None:
        box = self.query_one("#fm-error", Label)
        box.update(text)
        box.display = bool(text)

    def _code_options(self, kind: str) -> list[tuple[str, str]]:
        return [(f"{code} · {name}" if name and name != code else code, code) for code, name in self.koha.get(kind, [])]

    def _profile_options(self) -> list[tuple[str, str]]:
        try:
            files = sorted(self.profiles.glob("mapping-*.json"))
        except OSError:
            return []
        out = []
        for f in files:
            try:
                name = json.loads(f.read_text(encoding="utf-8")).get("name") or f.stem[8:]
            except (OSError, ValueError):
                continue
            out.append((name, str(f)))
        return out

    # ------------------------------------------------------------ modes

    def _modes(self) -> None:
        """The mode bar: the current group's mode marked, Patrons only for
        tables (a MARC file has records, not patrons); hidden in version 1."""
        bar = self.query_one("#fm-modes")
        bar.display = self.v2 and bool(self.groups)
        if not bar.display:
            self._mode_widgets()
            return
        for mode in MODES:
            b = self.query_one(f"#fm-mode-{mode}", Button)
            b.set_class(self.group.mode == mode, "-active")
            b.disabled = mode == "patrons" and self.group.kind == "marc"
        note = ""
        if self.group.mode != self.group.detected:
            note = t("(detected: ${mode})", mode=t(MODE_NAMES[self.group.detected]))
        else:
            note = t("(detected automatically)")
        self.query_one("#fm-mode-note", Label).update(note)
        self._mode_widgets()

    def _mode_widgets(self) -> None:
        mode = self.group.mode if self.v2 else "bibliographic"
        modes = {g.mode for g in self.groups} if self.v2 else {"bibliographic"}
        self.query_one("#fm-tidy").display = mode == "bibliographic"
        self.query_one("#fm-sensitive").display = mode == "patrons"
        self.query_one("#fm-loc-q").display = self.query_one("#fm-loc-bar").display = mode != "patrons"
        if self.v2:
            self.query_one("#fm-def-branches-line").display = bool(modes & {"bibliographic", "patrons"})
            self.query_one("#fm-def-itemtypes-line").display = "bibliographic" in modes
            self.query_one("#fm-def-categories-line").display = "patrons" in modes
            self.query_one("#fm-barcodes-line").display = "bibliographic" in modes

    def set_mode(self, mode: str) -> None:
        """Switch the current stream or table to another mode: the columns
        not changed by hand take that mode's proposal, the others stay when
        they still fit."""
        g = self.group
        if mode == g.mode or mode not in MODES or (mode == "patrons" and g.kind == "marc"):
            return
        g.mode = mode
        for key in g.keys:
            row = self.rows[key]
            was_untouched = row.to == row.proposal and not row.text
            row.proposal = row.proposals.get(mode, IGNORE) or IGNORE
            if was_untouched or self.check(row, row.to):
                row.to, row.text = row.proposal, ""
        for key in [k for k in self.fixed if self.rows[k].table == g.gid]:
            if self.check(self.rows[key], self.rows[key].to):
                self.fixed.remove(key)
                del self.rows[key]
        self.field = None
        self._modes()
        self._fill_grid()
        self._error("")

    # ------------------------------------------------------------ the grid

    def _header(self, key: tuple[str, str]) -> Text:
        row = self.rows[key]
        head = Text(self.campo(key), style="bold")
        if row.kind != "fixed":
            head.append(" · " + row.source[:CELL - 10], style="bold")
        head.append("\n")
        mode = self.mode_of(row)
        if row.text:
            head.append("✎ " + (row.to if row.to != IGNORE else "?"), style="bold reverse")
        elif row.to == IGNORE:
            head.append("✕ " + t("left out"), style="bold red")
        elif row.changed:
            head.append("→ " + dest_label(row.to, mode), style="bold reverse")
        elif row.unsure:
            head.append("? " + dest_label(row.to, mode), style="bold yellow")
        else:
            if row.to == KEEP or (row.kind == "marc" and row.to == row.source):
                head.append("= " + dest_label(row.source, mode) if row.kind == "marc" else "= " + self.dest_text(row),
                            style="dim")
            else:
                head.append("= " + dest_label(row.to, mode), style="dim")
        return head

    def _duplicates(self, key: tuple[str, str]) -> set[str]:
        """Values repeated in the sample of a column that must be unique."""
        row = self.rows[key]
        if self.dest_of(row) not in UNIQUE or key not in self.group.keys:
            return set()
        i = self.group.keys.index(key)
        seen = Counter(v.strip() for r in self.group.cells for v in r[i] if v.strip())
        return {v for v, n in seen.items() if n > 1}

    def cell_problems(self, key: tuple[str, str], record: int) -> tuple[list[str], list[str]]:
        """(errors, warnings) of one cell, for where its column goes."""
        row = self.rows[key]
        vals = self.values(key, record)
        dest = self.dest_of(row)
        errors, warns = [], []
        if row.kind != "fixed" and row.to != IGNORE:
            dup = self._duplicates(key)
            if any(v.strip() in dup for v in vals):
                errors.append(t("repeated in the sample: it must be unique"))
            if not vals and dest in REQUIRED.get(self.mode_of(row), ()):
                errors.append(t("required by Koha and empty"))
            for v in vals:
                warns.extend(problems(v, dest))
        if koha_fields.CODE_KINDS.get(dest) is None:     # MAIN, BK: codes are capitals
            for v in vals:
                warns.extend(warnings(v, row.source))
        return errors, warns

    def _cell(self, key: tuple[str, str], record: int) -> Text:
        row = self.rows[key]
        if row.text:
            return Text(row.text[:CELL - 1], style="italic")
        vals = self.values(key, record)
        errors, warns = self.cell_problems(key, record) if row.to != IGNORE else ([], [])
        if not vals:
            return Text("!" if errors else "·", style="bold red" if errors else "dim")
        first = vals[0].replace("\n", " ")
        more = f" ×{len(vals)}" if len(vals) > 1 else ""
        room = CELL - len(more)
        shown = first if len(first) <= room else first[:room - 1] + "…"
        dirty = bool(warns)
        style = "strike dim" if row.to == IGNORE else ("bold red" if errors else ("yellow" if dirty else ""))
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
            if row.kind == "fixed":
                name = t("fixed text")
            elif row.kind == "marc":
                name = dest_label(row.source, self.mode_of(row))
            else:
                name = row.source
            opts.append((f"{self.campo(k)} · {name}", "\t".join(k)))
        opts.append((t("+ New fixed text for every record"), NEW_FIXED))
        sel = self.query_one("#fm-field", Select)
        sel.set_options(opts)
        if self.field:
            sel.value = "\t".join(self.field)

    def _sync(self) -> None:
        """Everything that follows the cursor: the example, the cell line, the
        mapping card, the LoC link, the codes and the counts."""
        n = len(self.group.cells)
        self.query_one("#fm-example", Label).update(
            t("Example ${i} of ${n}", i=self.record + 1 if n else 0, n=n))
        field = self.query_one("#fm-field", Select)
        if self.field and field.value != "\t".join(self.field):
            field.value = "\t".join(self.field)
        self._sync_editor()
        self._cell_line()
        self._codes()
        self._refresh()

    def _targets(self, mode: str) -> list[tuple[str, str]]:
        """The destinations of a mode, "code (name)", in the order offered."""
        out: list[tuple[str, str]] = []
        seen: set[str] = set()

        def add(to: str, label: str) -> None:
            if to and to not in seen:
                out.append((label, to))
                seen.add(to)

        if mode == "patrons":
            supported = (self.data.get("capabilities") or {}).get("patron_fields")
            restricted = self.mapper.RESTRICTED_FIELDS if self.mapper else {k for k, _ in koha_fields.PATRON_GROUPS[-1][1]}
            for group, fields in koha_fields.PATRON_GROUPS:
                for field, name in fields:
                    if field in restricted and not self.sensitive:
                        continue
                    if supported is not None and field not in supported and field not in restricted:
                        continue
                    add(field, f"{t(group)}: {field} ({t(name)})")
            return out
        if mode == "authorities":
            listed = [x.get("to") for x in (self.data.get("targets_by_mode") or {}).get("authorities", [])]
            for to in listed or list(koha_fields.AUTHORITY_LABELS):
                add(to, dest_label(to, mode))
            return out
        for x in self.data.get("targets", []) + (self.data.get("targets_by_mode") or {}).get("bibliographic", []):
            add(x["to"], ref_label(x["to"]) if marc21.label(x["to"]) else f"{x['to']} ({t(x.get('label', ''))})")
        for ref in marc21.SUBFIELDS:
            add(ref, ref_label(ref))
        return out

    def _dest_options(self, row: Row) -> list[tuple[str, str]]:
        """Função for a column: keep it, a custom destination, a fixed text,
        leave it out, the mode's destinations, then the fields of the other
        columns."""
        mode = self.mode_of(row)
        custom = t("Custom field (type it, e.g. ${ref})", ref="820$a") if mode != "patrons" else \
            t("Another patron field (type its name)")
        if row.kind == "fixed":
            opts = [(custom, OTHER), (t("[Remove this fixed text]"), IGNORE)]
        else:
            if row.proposal in (KEEP, IGNORE) or not self.v2:
                what = self.dest_text(row) if row.proposal != KEEP else row.source
                if row.proposal == IGNORE:
                    what = t("left out")
                keep = f"{self.campo(row.key)} · {what}" + ("" if row.proposal == IGNORE else f" {t('(keep)')}")
            else:
                keep = t("Suggested: ${dest}", dest=dest_label(row.proposal, mode))
                if row.unsure:
                    keep += " " + t("(check)")
            opts = [(keep, KEEP), (custom, OTHER),
                    (t("Fixed text for every record"), FIXED), (t("[Do not import this field]"), IGNORE)]
        seen = {v for _, v in opts}
        for label, to in self._targets(mode):
            if to not in seen:
                opts.append((label, to))
                seen.add(to)
        if mode != "patrons":
            for k in self.group.keys:
                other = self.rows[k]
                to = other.proposal
                if k != row.key and to not in seen and _REF.match(to or ""):
                    opts.append((f"{self.campo(k)} · {dest_label(to, mode)}", to))
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
        patrons = self.mode_of(row) == "patrons" if row else False
        custom.placeholder = "city" if patrons else "820$a"
        if row is not None:
            dest.set_options(self._dest_options(row))
            value = self._dest_value(row)
            dest.value = value
            fixed = row.kind == "fixed" or value == FIXED
            custom.display = value == OTHER or fixed
            text.display = fixed
            known = row.to in koha_fields.PATRON_LABELS if patrons else bool(_REF.match(row.to or ""))
            custom.value = row.to if known and (value == OTHER or fixed) else ""
            if fixed and not custom.value and (_REF.match(row.proposal or "") or patrons and row.proposal != IGNORE):
                custom.value = row.proposal if row.proposal not in (KEEP, IGNORE) else ""
            text.value = row.text
        else:
            custom.display = text.display = False
        self.query_one("#fm-inputs").display = custom.display or text.display
        mode = self.mode_of(row) if row else "bibliographic"
        tag = ""
        if row and mode != "patrons":
            tag = row.to if _REF.match(row.to or "") else (row.source if row.kind == "marc" else "")
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
        errors, warns = self.cell_problems(self.field, self.record) if row.to != IGNORE else ([], [])
        if not vals:
            line = Text(head + ": " + t("This example does not have this field."), style="dim")
            if errors:
                line.append("  ✖ " + ", ".join(errors), style="bold red")
            box.update(line)
            return
        v = vals[0]
        line = Text(head + ": ", style="bold")
        line.append(v.replace("\n", " "))
        line.append("  · " + t("${n} character(s)", n=len(v)), style="dim")
        if len(vals) > 1:
            line.append(f"  · ×{len(vals)}", style="dim")
        if errors:
            line.append("  ✖ " + ", ".join(errors), style="bold red")
        found = list(dict.fromkeys(warns))
        if found:
            line.append("  ⚠ " + ", ".join(found), style="yellow")
        box.update(line)

    # ------------------------------------------------------------ codes

    def _code_source(self, row: Row | None) -> tuple[str, dict[str, int]]:
        """(kind, {value: rows}) when the field under the cursor holds codes
        of the instance (library, item type, location, category)."""
        if row is None or not self.v2 or row.to == IGNORE or row.text:
            return "", {}
        dest = self.dest_of(row)
        kind = koha_fields.CODE_KINDS.get(dest, "")
        if not kind or not self.koha.get(kind):
            return "", {}
        found = self.group.codes.get(row.source, {}) if row.kind == "marc" else row.codes
        return (kind, found) if found else ("", {})

    def _codes(self) -> None:
        """The from/to list: each code of the file, how many rows have it and
        the instance's code it becomes (preset when the instance has the
        same code; else the default, when there is one)."""
        if not self.v2:
            self.query_one("#fm-codes").display = False
            return
        row = self.rows.get(self.field) if self.field else None
        kind, found = self._code_source(row)
        box = self.query_one("#fm-codes")
        box.display = bool(found)
        if not found:
            self._code_rows = []
            return
        values = list(found.items())[:CODES_SHOWN]
        self.set_timer(0.1, self._fit_codes)        # once the list is laid out
        if [(kind, v) for v, _ in values] == self._code_rows:
            return
        self._code_rows = [(kind, v) for v, _ in values]
        names = {"branches": t("library"), "itemtypes": t("item type"), "locations": t("shelving location"),
                 "categories": t("patron category")}
        self.query_one("#fm-codes-title", Label).update(
            t("In the file → in this Koha (${what})", what=names.get(kind, kind)))
        holder = self.query_one("#fm-codes-list", Vertical)
        holder.remove_children()
        known = {c for c, _ in self.koha[kind]}
        lines = []
        for n, (value, count) in enumerate(values):
            chosen = self.remaps[kind].get(value) or (value if value in known else "")
            sel = Select(self._code_options(kind), id=f"fm-code-{n}", prompt=t("Choose..."),
                         value=chosen if chosen in known else Select.NULL)
            label = Label(t("${value} (${n} row(s))", value=value, n=f"{count:,}") +
                          ("" if value in known else "  " + t("not in this Koha")),
                          classes="fm-code-key" + ("" if value in known else " -unknown"), markup=False)
            lines.append(Horizontal(label, sel, classes="fm-line"))
        holder.mount_all(lines)

    def _fit_codes(self) -> None:
        """Make room for the from/to list under the grid: fewer example
        rows, still at least four (Ctrl+↓ gives them back)."""
        bottom = self.query_one("#fm-bottom")
        overflow = self.query_one("#fm-map").outer_size.height - bottom.size.height
        if overflow > 0 and bottom.size.height:
            self.resize_grid(max(9, self.grid_height - overflow))

    def _code_values(self):
        """(kind, value) of every code the mapped columns and fields carry."""
        for g in self.groups:
            for key in g.keys:
                row = self.rows[key]
                kind = koha_fields.CODE_KINDS.get(self.dest_of(row) if row.to != IGNORE else "", "")
                if kind and self.koha.get(kind):
                    for value in (g.codes.get(row.source, {}) if row.kind == "marc" else row.codes):
                        yield kind, value

    def _seed_remaps(self) -> None:
        """A code the instance does not have goes to the instance's code of
        the same name ("Livros" -> BK Livros), else to the default (MAIN ->
        CA), until the librarian picks another: nothing stops on it."""
        for kind, value in self._code_values():
            known = {c for c, _ in self.koha[kind]}
            if value in known or self.remaps[kind].get(value):
                continue
            named = {_plain(name): code for code, name in self.koha[kind] if name}
            named.update({_plain(code): code for code in known})
            match = named.get(_plain(value))
            if match:
                self.remaps[kind][value] = match
            elif self.defaults.get(kind) in known:
                self.remaps[kind][value] = self.defaults[kind]

    def unresolved(self) -> dict[str, list[str]]:
        """Codes this Koha does not have and nobody said where they go."""
        left: dict[str, list[str]] = {}
        for kind, value in self._code_values():
            if kind == "locations":     # an unknown shelving location is only a warning
                continue
            if value not in {c for c, _ in self.koha[kind]} and not self.remaps[kind].get(value):
                left.setdefault(kind, [])
                if value not in left[kind]:
                    left[kind].append(value)
        return left

    def _refresh(self) -> None:
        n = self.changed()
        dropped = sum(1 for r in n if r.to == IGNORE)
        dirty = errors = 0
        for k in self.group.keys:
            if self.rows[k].to == IGNORE:
                continue
            for r in range(len(self.group.cells)):
                e, w = self.cell_problems(k, r)
                errors += bool(e)
                dirty += bool(w)
        unsure = sum(1 for k in self.group.keys if self.rows[k].unsure and not self.rows[k].changed)
        text = t("${n} change(s) · ${k} left out · ${w} warning(s)", n=len(n) - dropped, k=dropped, w=dirty)
        if errors:
            text += " · " + t("${e} error(s)", e=errors)
        if unsure:
            text += " · " + t("${u} to check (?)", u=unsure)
        self.query_one("#fm-count", Label).update(text)
        self._option_note()

    def _fieldmap(self):
        """The engine's FieldMap the preview applies to a MARC sample."""
        if self.v2:
            return self._spec_for(self.group).legacy_fieldmap()
        return self.fm.FieldMap.from_obj(self.mapping())

    def _spec_for(self, g: Group):
        spec = self.mapper.MappingSpec.from_obj(self.mapping()).for_mode(g.mode)
        obj = spec.to_obj()
        obj["mappings"] = [r for r in obj["mappings"]
                           if (not r.get("stream") or r["stream"] == g.source_id)
                           and (r.get("ref") or r["source"].startswith("="))]
        return self.mapper.MappingSpec.from_obj(obj)

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
            fmap = self._fieldmap()
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
            if self.group.kind == "table" or self.group.gid.startswith("t"):
                return self._patron_preview() if self.mode_of() == "patrons" else self._table_preview()
            return Text(t("The preview needs the engine of this panel version; the mapping still works."))
        src = self.group.records[min(self.record, len(self.group.records) - 1)]
        old = src.formatted().splitlines()
        if self.before:
            return Text("\n".join(old))
        try:
            if self.v2 and self.mapper:
                defaults = {"branch": self.defaults.get("branches", ""), "itype": self.defaults.get("itemtypes", "")}
                after = self._spec_for(self.group).apply_record(src, defaults=defaults).formatted().splitlines()
            else:
                after = self.fm.FieldMap.from_obj(self.mapping()).apply(src).formatted().splitlines()
        except (ValueError, KeyError) as e:
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
            to = self.dest_text(row)
            text.append(f"{row.source[:20]:<20} → {to[:34]:<34} ", style="bold" if row.changed else "")
            text.append(vals[0][:60] + "\n", style="strike dim" if row.to == IGNORE else "")
        return text

    def _patron_preview(self) -> Text:
        """The patron as Koha will get the example: field, name and value."""
        out: OrderedDict[str, str] = OrderedDict()
        for k in self.keys():
            row = self.rows[k]
            if row.to in (IGNORE, KEEP):
                continue
            vals = self.values(k)
            if vals and vals[0].strip():
                out.setdefault(row.to, vals[0].strip())
        branch = out.get("branchcode")
        if branch in self.remaps["branches"]:
            out["branchcode"] = self.remaps["branches"][branch]
        category = out.get("categorycode")
        if category in self.remaps["categories"]:
            out["categorycode"] = self.remaps["categories"][category]
        for field, kind in (("branchcode", "branches"), ("categorycode", "categories")):
            if not out.get(field) and self.defaults.get(kind):
                out[field] = self.defaults[kind] + "  " + t("(default)")
        text = Text()
        for group, fields in koha_fields.PATRON_GROUPS:
            lines = [(f, n) for f, n in fields if f in out]
            if not lines:
                continue
            text.append(t(group) + "\n", style="bold")
            for field, name in lines:
                text.append(f"  {t(name)[:30]:<30} ", style="dim")
                text.append(out[field][:70] + "\n")
        missing = [f for f in REQUIRED["patrons"] if f not in out]
        if missing:
            text.append("\n" + t("Missing and required: ${fields}", fields=", ".join(missing)) + "\n", style="bold red")
        return text or Text(t("No column goes to a patron field yet."))

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
        if to != row.proposal:
            row.unsure = False
        self._seed_remaps()
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
        if not isinstance(event.value, str) or event.value == self.group.gid:
            return
        self.group = next(g for g in self.groups if g.gid == event.value)
        self.record, self.field = 0, None
        self._code_rows = []
        self.resize_grid(self.grid_height)
        self._modes()
        self._fill_grid()

    @on(Button.Pressed, ".fm-mode")
    def _mode_pressed(self, event: Button.Pressed) -> None:
        self.set_mode((event.button.id or "").removeprefix("fm-mode-"))

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
            if not custom.value and row.proposal not in (KEEP, IGNORE) and \
                    (_REF.match(row.proposal or "") or self.mode_of(row) == "patrons"):
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
        if event.checkbox.id == "fm-sensitive":
            self.sensitive = event.value
            if not event.value and self.mapper:
                for row in self.rows.values():
                    if row.to in self.mapper.RESTRICTED_FIELDS:
                        row.to = IGNORE
            self._fill_grid()
            return
        name = (event.checkbox.id or "").removeprefix("fm-opt-")
        if name in self.options:
            self.options[name] = event.value
            self._refresh()

    @on(Select.Changed, "#fm-koha Select")
    def _koha_value(self, event: Select.Changed) -> None:
        sid = event.select.id or ""
        value = event.value if isinstance(event.value, str) else ""
        if sid.startswith("fm-def-"):
            kind = sid.removeprefix("fm-def-")
            if self.defaults.get(kind, "") != value:
                self.defaults[kind] = value
                self._seed_remaps()
                self._code_rows = []
                self._codes()
        elif sid == "fm-barcodes" and value in ("review", "generate"):
            self.barcodes = value

    @on(Select.Changed, "#fm-codes-list Select")
    def _code_value(self, event: Select.Changed) -> None:
        n = int((event.select.id or "fm-code-0").rsplit("-", 1)[1])
        if n >= len(self._code_rows):
            return
        kind, value = self._code_rows[n]
        chosen = event.value if isinstance(event.value, str) else ""
        if chosen:
            self.remaps[kind][value] = chosen
        else:
            self.remaps[kind].pop(value, None)

    @on(Button.Pressed, "#fm-prof-save")
    def _save_profile(self) -> None:
        note = self.query_one("#fm-prof-note", Label)
        name = self.query_one("#fm-prof-name", Input).value.strip()
        if not name:
            note.update(t("Type a name for the profile."))
            return
        if not self.mapper:
            note.update(t("The import engine is unavailable."))
            return
        try:
            profile = self.mapper.make_profile(self.mapping(), self._profile_columns())
        except ValueError as e:
            note.update(str(e))
            return
        profile["name"] = name
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"
        try:
            self.profiles.mkdir(parents=True, exist_ok=True)
            path = self.profiles / f"mapping-{slug}.json"
            path.write_text(json.dumps(profile, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            path.chmod(0o600)
        except OSError as e:
            note.update(f"{e.strerror}")
            return
        self.query_one("#fm-prof-list", Select).set_options(self._profile_options())
        note.update(t("Profile \"${name}\" saved (no values of the file are kept in it).", name=name))

    def _profile_columns(self) -> list[dict]:
        columns = {c["id"]: c for c in self.data.get("columns", [])}
        out = []
        for g in self.groups:
            for key in g.keys:
                row = self.rows[key]
                if row.kind == "column":
                    c = dict(columns.get(row.id, {"id": row.id, "header": row.source}))
                    c["table"] = c.get("table_key", g.name)
                    out.append(c)
        return out

    @on(Button.Pressed, "#fm-prof-load")
    def _load_profile(self) -> None:
        note = self.query_one("#fm-prof-note", Label)
        path = self.query_one("#fm-prof-list", Select).value
        if not isinstance(path, str) or not self.mapper:
            note.update(t("Choose a saved profile first."))
            return
        try:
            profile = json.loads(Path(path).read_text(encoding="utf-8"))
            saved = self.mapper.MappingSpec.from_obj(profile["mapping"]).to_obj()
            bindings = self.mapper.align_profile(profile, self._profile_columns())
        except (OSError, ValueError, KeyError) as e:
            note.update(str(e))
            return
        by_id = {self.rows[k].id: self.rows[k] for g in self.groups for k in g.keys}
        used = 0
        for rule in saved.get("mappings", []):
            row = by_id.get(bindings["bindings"].get(rule.get("source")) or rule.get("source"))
            if row is None:
                continue
            g = self.group_of(row)
            if g and rule.get("mode") in MODES and rule["mode"] != g.mode and not (rule["mode"] == "patrons" and g.kind == "marc"):
                g.mode = rule["mode"]
            if not self.check(row, rule.get("to", IGNORE)):
                row.to, row.text, row.unsure = rule.get("to", IGNORE), "", False
                used += 1
        self._load_remaps(saved.get("remaps") or {})
        for k, v in (saved.get("options") or {}).items():
            if k in self.options:
                self.options[k] = bool(v)
                self.query_one(f"#fm-opt-{k}", Checkbox).value = bool(v)
        self._code_rows = []
        self._modes()
        self._fill_grid()
        note.update(t("Profile used: ${n} column(s) matched; ${m} to check by hand.", n=used,
                      m=len(bindings["ambiguous"]) + len(bindings["missing"])))

    @on(Button.Pressed, "#fm-check")
    async def _check_file(self) -> None:
        """The engine's real build of the whole file with this mapping, in a
        temporary folder: its validation report, in words."""
        if self._checking:
            return
        if not self.mapper or not self.review:
            self._error(t("The import engine is unavailable."))
            return
        self._checking = True
        button = self.query_one("#fm-check", Button)
        button.label = t("Checking...")
        try:
            spec = self.mapper.MappingSpec.from_obj(self.mapping())
            result = await asyncio.to_thread(self.review.preview_document, self.data, spec)
        except Exception as e:  # noqa: BLE001 - a mapping the engine refuses stays editable
            self._error(t("The file could not be checked: ${error}", error=str(e)))
            return
        finally:
            self._checking = False
            button.label = t("Check the whole file")
        if self.is_mounted:
            self.app.push_screen(CheckReportScreen(self.check_report(result)))

    def check_report(self, result: dict) -> Text:
        issues = result.get("issues", [])
        errors = Counter(t(i.get("message") or i.get("code") or "") for i in issues if i.get("severity") == "error")
        warns = Counter(t(i.get("message") or i.get("code") or "") for i in issues if i.get("severity") == "warning")
        text = Text()
        built = sum(len(g.get("records", [])) for g in result.get("groups", []))
        if not errors:
            text.append(t("No errors: the file can be imported with this mapping.") + "\n\n", style="bold green")
        else:
            text.append(t("${n} error(s) to fix before importing:", n=sum(errors.values())) + "\n", style="bold red")
            for msg, n in errors.most_common(20):
                text.append(f"  ✖ {msg}  (×{n})\n", style="red")
            text.append("\n")
        if warns:
            text.append(t("${n} warning(s) to look at:", n=sum(warns.values())) + "\n", style="bold yellow")
            for msg, n in warns.most_common(20):
                text.append(f"  ⚠ {msg}  (×{n})\n")
        if built:
            text.append("\n" + t("First records built: ${n}", n=built) + "\n", style="dim")
        return text

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
        for g in self.groups:
            if g.mode != g.detected:
                self.group, current = g, self.group
                self.set_mode(g.detected)
                self.group = current
        for r in self.rows.values():
            r.to, r.text = r.proposal, ""
        for k in self.options:
            self.options[k] = False
            self.query_one(f"#fm-opt-{k}", Checkbox).value = False
        self.field = None
        self._modes()
        self._fill_grid()

    @on(Button.Pressed, "#fm-skip")
    def action_skip(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#fm-apply")
    def action_apply(self) -> None:
        obj = self.mapping()
        if not self.v2 and not obj["mappings"] and not obj.get("options"):
            self.dismiss(False)
            return
        if self.v2:
            left = self.unresolved()
            if left:
                names = {"branches": t("library"), "itemtypes": t("item type"), "categories": t("patron category")}
                kind, values = next(iter(left.items()))
                self._error(t("These ${kind} codes are not in this Koha: ${codes}. Pick in \"In the file → in this "
                              "Koha\" what each one becomes, or choose a default on the right.",
                              kind=names[kind], codes=", ".join(values[:5])))
                return
        if self.v2 and self.mapper:
            try:
                obj = self.mapper.MappingSpec.from_obj(obj).to_obj()
            except ValueError as e:
                self._error(str(e))
                return
        try:
            with open(self._out, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False, indent=1)
                fh.write("\n")
        except OSError as exc:
            self._error(f"{self._out}: {exc.strerror}")
            return
        self.dismiss(True)
