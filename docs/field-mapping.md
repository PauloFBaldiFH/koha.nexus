# Edit & Map Fields (Magic Import)

The Textual panel reviews bibliographic records, patrons and authorities
before building the files that Koha will import. The mapper opens before
unresolved column questions and before the record-count check, so a
misclassified or patron-only file can still be corrected.

For formats, holdings rules, validation and recovery, see
[Magic Import: operator and architecture guide](magic-import.md).

## Operator workflow

1. Open **Library tools > Magic Import Tool** and choose the source.
2. The mapping screen opens in the MarcEdit-style layout: a horizontal grid
   with one row per sample record (or table row) and one column per source
   field. Each column header shows the source on the first line and its
   destination on the second, always as code and plain name, for example
   `245$a (Title)` or `surname (Surname)`. `=` means unchanged, `→` a new
   destination, `?` a guess the tool is not sure about (shown in the warning
   colour) and `✕` a field left out.
3. The mode bar above the grid switches the selected table or MARC stream
   between **Bibliographic**, **Patrons** and **Authorities**; the detected
   mode is marked. Switching shows that mode's own proposal for every column.
4. Click a column, then pick its destination in **Function**. The list is
   grouped (MARC fields with their names; patron fields grouped as Koha's
   patron form: identification, address, contact, library and category...).
   Any other field can be typed by hand (`590$a`, `sort1`). **Fixed text**
   adds a value every record or patron receives (`=BK` to `942$c`).
5. Code columns (library, item type, shelving location, patron category)
   open the **In the file → in this Koha** list: every distinct value found
   in the whole file, with a selector of this Koha's own codes. A value
   whose name matches a Koha code is paired automatically ("Livros" → `BK`);
   a value this Koha does not have is marked "not in this Koha". Apply stops
   with a clear message while such a value has no destination.
6. On the right, **Values of this Koha** sets the default library, item type
   and patron category (selectors filled from the instance) for rows that
   have none, and what to do with copies without a barcode. **More options**
   keeps the tidy tools: join copies of the same book in one record, fix
   text typed in capitals, and safe spelling repair.
7. Cells are checked as you go: red for errors (a repeated barcode or card
   number, a required field empty), yellow for warnings (invalid ISBN or CPF
   check digit, a value that is not a date). **Record preview** shows the
   MARC record (or the patron card) the import builds; **Check the whole
   file** runs the real build in the background and lists every error and
   warning for the complete file before anything is imported.
8. Apply the mapping. The tool analyses again, then builds and validates
   every output stream. Koha's staging or patron dry run, confirmation and
   verified backup still precede each write. **Skip** imports as detected.

An invalid mapping stops the operation; it does not silently switch to an
unmapped import. The classic whiptail interface keeps its own questions and
does not provide the graphical mapper.

## Patron and authority destinations

In **Patrons** mode, destinations use Koha importer/`borrowers` field names,
not MARC tags. The catalog includes names, alternate contacts, all `B_*`
address fields, contact details, enrollment/expiry dates, branch/category,
notes, preferences and supported importer fields such as `patron_attributes`
and guarantor relationships. The connected instance's schema filters what is
offered; an unavailable destination cannot silently disappear during export.
Automatic inference proposes only fields supported by the evidence. It
cannot distinguish every headless date, name or document number.

**Review sensitive patron fields** is off by default. Enabling it permits
intentional mapping to restricted fields such as `password`, `flags`,
`auth_method` and `protected`. Source password hashes are not portable:
recognized hashes are rejected, including hashes introduced by a fixed
value, default or remap. Saved profiles reject literal sensitive values.
Review access flags and authentication choices separately from ordinary
contact information.

In **Authorities** mode, destinations include control fields, established
headings (`100`, `110`, `111`, `130`, `150`, `151`...), 4XX/5XX tracings and
notes. Bibliographic `245`, item `952` and bibliographic `942$c` are rejected.
The destination framework determines the authority type code and its actual
field, commonly `152$b` or a locally configured `942$a`. One heading and a
compatible target type are required. Selecting a mode alone does not repair
an incompatible MARC leader or invent an authority heading.

## Mapping version 2

Source IDs address a particular source/table/field. They are opaque: neither
their spelling nor a column's position defines its bibliographic meaning.
Identical display headers in different tables have different IDs.

This synthetic example shows the shape; use IDs from the current draft:

```json
{
  "version": 2,
  "mode": "bibliographic",
  "table_modes": {"table:synthetic-readers": "patrons"},
  "source_modes": {"source:synthetic-marc": "auto"},
  "mappings": [
    {"source": "column:synthetic-card", "table": "table:synthetic-readers", "mode": "patrons", "to": "cardnumber"},
    {"source": "column:synthetic-name", "table": "table:synthetic-readers", "mode": "patrons", "to": "surname", "transform": "split_name"},
    {"source": "column:synthetic-country", "table": "table:synthetic-readers", "mode": "patrons", "to": "country", "value": "BR"},
    {"source": "marc:synthetic-title", "stream": "source:synthetic-marc", "mode": "bibliographic", "ref": "245$a", "to": "245$a"}
  ],
  "defaults": {"branchcode": "CA", "categorycode": "PT", "952$a": "CA", "952$b": "CA", "952$y": "BK"},
  "remaps": {"branchcode": {"MAIN": "CA"}, "952$a": {"MAIN": "CA"}, "952$b": {"MAIN": "CA"}},
  "relationships": [],
  "barcode_policy": "review"
}
```

| Key | Meaning |
|---|---|
| `mode` | Default domain: `bibliographic`, `patrons` or `authorities`. |
| `table_modes`, `source_modes` | Per-table or source-file overrides, including `auto`. |
| `mappings[].source` | Current opaque source-column or MARC-field ID. |
| `mappings[].table`, `stream`, `ref` | Scope and real MARC reference, where applicable. |
| `mappings[].mode` | Domain used to validate that rule's destination. |
| `mappings[].to` | Official patron field, MARC reference or `ignore`. |
| `mappings[].value` | Optional literal assignment, retaining the source ID. |
| `transform`, `prefix` | Whitelisted `split_name`, or `prefix` plus literal prefix text. |
| `defaults` | Values used only when the destination is missing. |
| `remaps` | Explicit source-code to destination-code translations. |
| `relationships` | Reviewed SQL joins, initially empty. |
| `barcode_policy` | `review` by default; `generate` needs stable migration/source identity. |
| `allow_restricted` | Explicit authorization to map restricted patron fields. |

An SQL relationship names `parent_table`, `child_table`, `parent_column`
and `child_column`, optionally its source and `kind`. The column integers are
reviewed source cell addresses from a proposal; they are not built-in schema
assumptions. `kind: "items"` joins physical copies to metadata.
`kind: "bibliographic"` associates a bibliographic/accounting table with
its metadata record, avoiding a second title for the same source record.
Only one parent relationship may be selected for a child table.

## Save and load profiles

Under **Mapping profiles**, type a name and press **Save**; pick a saved
profile and press **Use** to apply it to the next file from the same system.
Profiles are kept in the panel's `import-profiles` folder as
`mapping-<name>.json`, even when that import is not completed. They contain
mappings, logical table namespaces and statistical column signatures, not
raw source samples, so a different file name or shuffled column order can
reuse a profile. Matching uses names and content distributions; it never
copies the first column into the first saved destination.

Using a profile reports how many columns matched and how many are left to
check by hand. Literal credentials and other restricted values are refused
when saving a profile, including fixed assignments, defaults and remaps.

## Backend and panel protocol

The installer writes the `kei_import` package into the run's work directory.
The panel imports its `mapping` and `review` modules for validation, profiles
and previews. The protocol remains:

```text
@@fieldmap TITLE<TAB>FIELDS_JSON<TAB>OUT_JSON<TAB>ENGINE_DIR
```

`fields --draft` writes a version 2 document before a successful build is
required. It includes every table/stream field ID, first-three samples,
mode-specific destinations, capabilities, relationship proposals and the
current mapping. The preview calls `review.preview_document`, which builds
in an isolated work directory and reads `out/validation.json`.

`panel/kei_panel/routines/common.py` opens `FieldMapScreen` for every
document; it reads version 1 and version 2 files. Apply writes the mapping and answers the existing prompt; cancel/skip does
not write a new mapping. Samples and identity snapshots stay in the private
work directory; retained decision/audit reports have mode `0600`.

## Legacy mapping version 1

Existing v1 bibliographic mappings and the old screen remain supported:

```json
{
  "version": 1,
  "mappings": [
    {"from": "500$a", "to": "100$a"},
    {"from": "Tombo", "to": "952$p", "kind": "column"},
    {"from": "999", "to": "ignore"},
    {"from": "=BK", "to": "942$c"}
  ],
  "options": {"clean": true, "case": true, "group": true}
}
```

For v1, an omitted `version` means 1. Unnamed fields pass through; `ignore`
drops a named source; `kind: "column"` disambiguates a header that looks
like a MARC tag. Whole fields map to whole fields and subfields to subfields.
Fixed text fills an absent subfield without creating a physical copy.
Conflicting destination values are retained by the original field mapper.
The optional clean/case/group routines remain those of `fieldmap.py` and
`tidy.py`; neither mapping version evaluates arbitrary code.
