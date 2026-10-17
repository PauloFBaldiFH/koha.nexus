# Edit & Map Fields (Magic Import)

An optional step of the Magic Import Tool: before anything goes to Koha's
`stage_file.pl`, the librarian can see which fields and columns the file
holds, with sample values, and send each one to another MARC 21 destination
or leave it out. Skipping the step is the direct import, unchanged.

Status (1.5.82): the engine side is done and tested (`kei_import/fieldmap.py`,
the `fields` command and `build --fieldmap`). The panel screen below is a
proposal, not built yet.

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
 "mapping": {"version": 1, "mappings": []}}
```

- `fields`: each `TAG$c` (`TAG` for control fields) of the sample, in how
  many sample records it appears, up to three different values, and `to`,
  the proposal (the field itself).
- `columns`: each column of a table holding books, with the subfield of the
  role the engine gave it (`""` for a role no single subfield stands for,
  such as quantity), the mapped subfield, or `ignore`.
- `records`: the sample records, for the live preview: the panel imports
  `kei_import/fieldmap.py` (standard library only) and runs
  `FieldMap.apply` on them at every change, without calling the engine.
- `mapping`: the mapping of the last build, so a second look starts from it.
  The streams are always those of the direct import.

## Panel screen (proposal)

A new native screen, `MagicFieldMapScreen`, opened from the magic import
task through a new `@@fieldmap PATH` prompt (PATH = `fields.json`); it
answers with the path of the saved `fieldmap.json`, or nothing when the
librarian skips.

```
┌ 🪄 Magic Import Tool · Edit field mapping ─────────────────────────────┐
│ isis.iso · 11,488 records · sample of 10                    [stream ▾] │
├──────────────┬──────────────────────────┬──────────────────────────────┤
│ Source       │ Sample value             │ Koha destination             │
│ 090$a   10/10│ 823.91                   │ 082$a DDC classification   ▾ │
│ 500$a    9/10│ AUSTEN, JANE             │ 100$a Personal name        ▾ │
│ 595$a   10/10│ T-0042                   │ 952$p Barcode / accession  ▾ │
│ 999$c   10/10│ 1                        │ [Do not import this field] ▾ │
├──────────────┴──────────────────────────┴──────────────────────────────┤
│ Record preview  ◀ 1 / 3 ▶                                              │
│ 082 04 $a 823.91                                                       │
│ 100 1  $a AUSTEN, JANE                                                 │
│ 245 10 $a Orgulho e preconceito                                        │
│ 952    $p T-0042 $a CPL $b CPL $y BK                                   │
├────────────────────────────────────────────────────────────────────────┤
│ 3 changes · 1 left out          [Reset] [Skip: import as it is] [Apply]│
└────────────────────────────────────────────────────────────────────────┘
```

- When it opens: after the build's preview, the magic import asks one
  question, "Edit the field mapping before importing?", default **No**;
  No (or Esc) is today's import, untouched.
- Table: one row per source field or column (`DataTable`, the panel's
  existing styling): source with how many sample records have it, the first
  sample value (all three on hover or in the row's detail line), and the
  destination.
- Destination picker: a `Select` with "Keep as it is" first, Paulo's list
  (100$a, 245$a, 245$b, 260$b, 264$b, 260$c, 264$c, 082$a, 650$a, 952$p,
  952$y), "Other: type TAG$subfield..." (an `Input` validated as you type)
  and "[Do not import this field]".
- Record preview: the first 1-3 sample records after the mapping, redrawn
  at every change (in-process `FieldMap.apply`, no engine call), changed
  lines highlighted; a "before" toggle shows the record as in the file.
- Several streams or tables: a selector at the top; one mapping holds all.
- Apply writes only the rows that differ from the proposal, then the task
  rebuilds and shows the new preview; Reset goes back to the proposal.
- New strings go to the 22 lang caches by hand (pt: "Editar Campos",
  "Não importar este campo", ...), as with every panel string.
