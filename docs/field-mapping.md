# Edit & Map Fields (Magic Import)

An optional step of the Magic Import Tool: before anything goes to Koha's
`stage_file.pl`, the librarian can see which fields and columns the file
holds, with sample values, and send each one to another MARC 21 destination
or leave it out. Skipping the step is the direct import, unchanged.

Status (1.5.82): engine (`kei_import/fieldmap.py`, the `fields` command and
`build --fieldmap`) and panel screen (`panel/kei_panel/screens/fieldmap.py`)
are built and tested. The classic whiptail panel imports as before (no
mapping step there).

## Where it sits in the import

```
analyse ── questions (as today) ── build ── preview ─┬─ review gate ── commit (stage_file.pl ...)
                                                    │
                                    [Edit field mapping]   (optional)
                                                    │
                       fields ── mapping screen ── build --fieldmap ── preview again
```

1. `analyse` and its questions run as today (what each table holds, the
   character set, legacy item fields...).
2. `build` makes the direct import's files: MARCXML or ISO 2709 for
   `stage_file.pl`, listed in `out/manifest.tsv` (and copied to
   `out/manifest-direct.tsv`).
3. New and optional: `fields` reads the first records of each of those
   streams (10 by default, `--sample N`) and the columns of each table, and
   writes `work/fields.json`.
4. The panel shows the mapping screen, writes the librarian's mapping to
   `work/fieldmap.json` and runs `build --fieldmap work/fieldmap.json` again.
5. The preview, review gate and commit go on as today, with the mapped files.

Nothing in these steps writes to Koha's database.

## The mapping (`fieldmap.json`)

```json
{"version": 1,
 "mappings": [
   {"from": "500$a",  "to": "100$a"},
   {"from": "090$a",  "to": "082$a"},
   {"from": "949",    "to": "952"},
   {"from": "949$a",  "to": "952$p"},
   {"from": "Tombo",  "to": "952$p", "kind": "column"},
   {"from": "Obs",    "to": "ignore", "kind": "column"},
   {"from": "999",    "to": "ignore"}
 ]}
```

| `from` | `to` | Effect |
|---|---|---|
| `TAG$c` | `TAG$c` | Every value of that subfield moves to the destination subfield. |
| `TAG` | `TAG` | The whole field changes tag, indicators and subfields kept (`949` → `952`). |
| `001`-`009` | `TAG` or `TAG$c` | A control field's value goes to another control field, or into a subfield (`001` → `035$a`). |
| column header | `TAG$c` | A spreadsheet column goes to that subfield (see "Spreadsheets"). |
| any | `ignore` | Left out of the import. |

- `version` is optional (1). `kind: "column"` marks a column header that
  could pass for a tag (a column called `100`); any `from` that is not
  `TAG` or `TAG$c` is a column anyway.
- Fields and columns no rule names pass through as they are. A rule to the
  same place (`245$a` → `245$a`) changes nothing. So no mapping, an empty
  one, or one the panel wrote without changes is the direct import.
- A whole-field rule and subfield rules can be combined: subfield rules name
  the source tag (`949$a` above still means the 949's `$a`).
- Mistakes stop the build before anything is made (exit code 2, "The field
  mapping cannot be used: ..."): a tag that is not three characters, a
  subfield of a control field, a whole field sent to a subfield or the
  reverse, a column without a subfield, an unknown version.

### How values land

- Subfields moved out of the same field occurrence stay together: two 949s
  with `$a` → `952$p` and `$b` → `952$y` make two 952s, each with its `$p`
  and `$y`.
- Fields a record has once (100, 110, 111, 130, 240, 245, 250, 260, 300, 942)
  take the moved subfield into the field already there: `246$a` → `245$b`
  adds `$b` to the existing 245.
- When the destination subfield is already set, nothing is overwritten and
  nothing is lost: the value stays in its original field and the preview
  counts it ("kept in place, destination already set") with examples.
- New fields get the usual indicators: 082 `04`, 100 `1#`, 245 `10`,
  264 `#1`, 650 `#4`, 700 `1#`; others blank.
- A 952 the mapping makes gets the library (`$a`, `$b`) and item type (`$y`)
  chosen for the import when the mapping did not give them, as Koha needs.
- A field left with no subfields after the moves is removed.

### Spreadsheets

A column mapped to a subfield the engine already builds takes that role,
with all the engine's rules (inverted names, 245 `$c`, 008, one record per
work, one 952 per copy, recasing):

| Subfield | Role | Subfield | Role |
|---|---|---|---|
| 020$a | ISBN | 490$a | series |
| 022$a | ISSN | 500$a | notes |
| 080$a | UDC class | 650$a | subjects |
| 082$a | Dewey class | 700$a | other authors |
| 100$a | author | 952$d | acquisition date |
| 245$a | title | 952$g | price |
| 245$b | subtitle | 952$h | volume |
| 250$a | edition | 952$i | accession number (tombo) |
| 260$a | place | 952$o | call number |
| 260$b | publisher | 952$p | barcode |
| 260$c | year | 952$t | copy number |
| 300$a | pages | 952$y | item type |

Any other subfield (`590$a`, `264$b`, `952$z`...) is carried as it is: 952
subfields go into each copy made from that row, the others make one field
per row (the same field from two rows of one work once). The mapping is for
this import only; the saved column profiles never remember it.

The columns' rules apply when the records are built, the `TAG$c` rules to
the records afterwards, so a table can use both.

### Streams and memory

Each stream is read and written one record at a time (ISO 2709 or MARCXML
in, MARCXML UTF-8 out, `out/mapped-N.xml`), so a large file costs no more
memory than a record. MARC-8 files are converted to UTF-8 with yaz first.

## `fields.json` (what the panel reads)

```json
{"version": 1, "sample": 10,
 "targets": [{"to": "100$a", "label": "Personal name (author)"}, "..."],
 "streams": [{"name": "isis.iso", "kind": "marc", "format": "ISO2709", "encoding": "UTF-8",
              "records_total": 11488,
              "fields": [{"from": "500$a", "kind": "marc", "count": 9,
                          "samples": ["AUSTEN, JANE", "ASSIS, MACHADO DE"], "to": "500$a"}],
              "records": [{"leader": "...", "fields": [["001", "7"], ["245", "10", [["a", "Emma"]]]]}]}],
 "columns": [{"table": "acervo.csv", "from": "Tombo", "kind": "column", "role": "tombo",
              "samples": ["T-1", "T-2"], "to": "952$i"}],
 "tables": [{"name": "acervo.csv", "kind": "table", "headers": ["Titulo", "Tombo"], "rows_total": 3200,
             "rows": [["Dom Casmurro", "T-1"], ["Iracema", "T-2"]]}],
 "mapping": {"version": 1, "mappings": []}}
```

- `fields`: each `TAG$c` (`TAG` for control fields) of the sample, in how
  many sample records it appears, up to three different values, and `to`,
  the proposal (the field itself).
- `columns`: each column of a table holding books, with the subfield of the
  role the engine gave it (`""` for a role no single subfield stands for,
  such as quantity), the mapped subfield, or `ignore`.
- `tables`: the first rows (up to `sample`, blank rows skipped) of each
  table holding books, every row as long as the headers and each value cut
  at 200 characters: the rows of the panel's grid. An engine older than
  1.5.83 sends no `tables`; the panel then builds a three-row grid from the
  columns' samples.
- `records`: the sample records, for the grid and the live preview: the panel imports
  `kei_import/fieldmap.py` (standard library only) and runs
  `FieldMap.apply` on them at every change, without calling the engine.
- `mapping`: the mapping of the last build, so a second look starts from it.
  The streams are always those of the direct import.

## Panel screen

`FieldMapScreen`, opened from the magic import task through the
`@@fieldmap TITLE<TAB>FIELDS<TAB>OUT<TAB>ENGINE` prompt (the engine's
`fields.json`, the `fieldmap.json` to write, the engine folder for the live
preview); it answers "ok" once a mapping with changes is written, "cancel"
when the librarian skips or changed nothing.

Laid out like MarcEdit's data snapshot (1.5.83): a grid of the sample, one
row per record and one column per field or spreadsheet column.

```
┌ Edit field mapping ──────────────────────────────────────────────────────────────────┐
│ isis.iso · 11,488 record(s) · sample of 10        [Show: all ▾]   ◀ Example 3 of 10 ▶ │
│ ╭ Sample data ─────────────────────────────────────────────────────────────────────╮ │
│ │ #  │ 090$a    │ 245$a          │ 260$b          │ 500$a                         │ │
│ │    │ = 090$a  │ = 245$a        │ → 264$b        │ ✕ left out                    │ │
│ │ 1  │ 869.3    │ Livro 1        │ Ã‰dition Edi… │ AUTOR 1 DA SILVA              │ │
│ │ 3  │ 869.3    │ Livro 3        │ Editora        │ ·                             │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────╯ │
│ ╭ Mapping of 260$b ───────────────────╮  ╭ Koha preview · example 3 of 10 ─────────╮ │
│ │ [ 264$b  Publisher (264)         ▾ ] │  │ 245 10 $a Livro 3                       │ │
│ ╰──────────────────────────────────────╯  │ ▸ 264    $b Editora                     │ │
│ ╭ Selected value · 260$b · example 3 ─╮  │                                         │ │
│ │ Editora                              │  │ [As in the file]                        │ │
│ │ 7 character(s)                       │  ╰─────────────────────────────────────────╯ │
│ ╰──────────────────────────────────────╯                                             │
│ 1 change(s) · 1 left out · 5 warning(s)          [Reset] [Skip: import as it is] [Apply] │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- When it opens: after the build's preview, the magic import asks one
  question, "Edit the field mapping before importing?", default **No**;
  No (or Esc) is today's import, untouched.
- Grid (`DataTable`, cell cursor, record number column frozen): each column
  is 16 characters wide; its two-line header is the source and its
  destination (`= kept` dim, `→ changed` bold, `✕ left out` red). Empty cells
  show `·`, repeated fields `×N`, values that look dirty are yellow.
- The cursor's row is the example everywhere ("Example N of 10", `[` and
  `]` or ◀ ▶); its column is the field the mapping card edits. Enter on a
  cell moves to its destination.
- Show: all / changed / with problems (missing in a sample record, or a
  warning) hides the columns you don't need.
- Mapping card: a `Select` with "Keep as it is" first, Paulo's list (100$a,
  245$a, 245$b, 260$b, 264$b, 260$c, 264$c, 082$a, 650$a, 952$p, 952$y),
  "Other: type TAG$subfield..." (an `Input`, checked with the engine's own
  rules on Enter) and "[Do not import this field]".
- Cell inspector: the selected value in full, every occurrence, its length
  and warnings (spaces at the start or end, all in capitals, broken accents,
  looks like an ISBN outside 020/022, control characters), and in how many
  sample records the field appears. Plain Python checks, no engine call.
- Koha preview: the example after the mapping, redrawn at every change
  (in-process `FieldMap.apply`, no engine call), changed lines marked with
  ▸; "As in the file" toggles the record before the mapping. A spreadsheet
  row shows each value and where it goes (the engine builds that record
  with its own rules). Without the engine module (an old engine) the screen
  still maps, without the MARC preview.
- Layout: from 140 columns the mapping card and inspector sit left of the
  preview; on a narrower terminal (an 80x24 console) the bottom half is two
  tabs, Mapping and Preview, switched with `p`.
- Several streams or tables: a selector at the top; one mapping holds all.
- Apply writes only the columns that differ from the proposal, then the task
  rebuilds and shows the new preview; Reset goes back to the proposal.
- Next (step 3): indicators, split on `;` and fixed fields.
- New strings are in `lang/pt.cache` (pt: "Editar Campos", "[Não importar
  este campo]", ...); the other languages show English for now.
- Demo mode (`--demo`) walks through the screen with a sample ISIS file.
