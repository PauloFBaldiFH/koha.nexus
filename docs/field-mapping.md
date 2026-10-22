# Edit & Map Fields (Magic Import)

The Textual panel reviews bibliographic records, patrons and authorities
before building the files that Koha will import. The mapper opens before
unresolved column questions and before the record-count check, so a
misclassified or patron-only file can still be corrected.

For formats, holdings rules, validation and recovery, see
[Magic Import: operator and architecture guide](magic-import.md).

## Operator workflow

1. Open **Library tools > Magic Import Tool** and choose the source.
2. Select a table or MARC stream. Check its **Import mode**:
   **Automatic detection**, **Bibliographic**, **Patrons** or **Authorities**.
   An override for a mixed MARC file applies to its source file; automatic
   detection keeps its bibliographic and authority groups separate.
3. Review each source field, proposed destination, confidence and reasons.
   Field and function selectors use light blue; warnings remain separate.
   **Leave out** excludes a field. **Custom destination** accepts a valid
   destination name or MARC reference. **Fixed text** replaces that source
   field's contribution with an entered literal value.
4. Choose a transform when needed: **Split full name** maps a patron's full
   name to `firstname` and `surname`; **Add a prefix** prepends literal text,
   for example `CPF:` for `patron_attributes`. These are named functions,
   never executable expressions.
5. Fill missing branch, patron category or item type values. Enter explicit
   code remaps when existing source codes must change. Defaults fill gaps;
   they do not replace valid codes already present.
6. For headless SQL, review proposed relationships and enter only confirmed
   relationships. No candidate is selected automatically. Choose **Review
   before importing** for missing barcodes, or explicitly request stable
   migration barcodes.
7. Inspect **Live preview · first 3 mapped records** and its validation flags.
   Edits schedule a background preview using the same backend build as the
   import. The preview displays three records; validation scans the complete
   output, including duplicates beyond that sample.
8. Apply the mapping. The tool analyses again, asks remaining questions,
   then builds and validates every output stream. Koha's staging or patron
   dry run, confirmation and verified backup still precede each write.

An invalid selected mapping stops the operation; it does not silently switch
to an unmapped import. Skipping the mapper continues through the usual
analysis and validation gates. The classic whiptail interface retains its
existing questions and does not provide the new graphical mapper.

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

Enter a profile path and use **Save profile** or **Load profile**. Profiles
contain mappings, logical table namespaces and statistical column signatures,
not raw source samples. A different source filename or shuffled column order
can therefore reuse a profile. Matching uses names and content distributions;
it never copies the first column into the first saved destination.

Loading reports ambiguous and missing fields. Ambiguous dates, competing
identifiers or indistinguishable columns require review; they receive no
guessed profile binding. Destination validation still runs after a profile
is applied. Literal credentials and other restricted values are refused
when saving a profile, including fixed assignments, defaults and remap
tables. Keep library-specific profiles in a private location.

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

The dispatch in `panel/kei_panel/routines/common.py` opens `ImportMapScreen`
for document version 2 or later, and the existing `FieldMapScreen` for v1.
Apply writes the mapping and answers the existing prompt; cancel/skip does
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
