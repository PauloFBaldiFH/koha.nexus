# Edit & Map Fields (Magic Import)

An optional step of the Magic Import Tool: before anything goes to Koha's
`stage_file.pl`, the librarian can see which fields and columns the file
holds, with sample values, and send each one to another MARC 21 destination
or leave it out. Skipping the step is the direct import, unchanged.

Status (1.5.84): engine (`kei_import/fieldmap.py`, the `fields` command and
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
   {"from": "999",    "to": "ignore"},
   {"from": "=BK",    "to": "942$c"}
 ],
 "options": {"group": true, "case": true, "clean": true}}
```

| `from` | `to` | Effect |
|---|---|---|
| `TAG$c` | `TAG$c` | Every value of that subfield moves to the destination subfield. |
| `TAG` | `TAG` | The whole field changes tag, indicators and subfields kept (`949` → `952`). |
| `001`-`009` | `TAG` or `TAG$c` | A control field's value goes to another control field, or into a subfield (`001` → `035$a`). |
| column header | `TAG$c` | A spreadsheet column goes to that subfield (see "Spreadsheets"). |
| any | `ignore` | Left out of the import. |
| `=text` | `TAG$c` | Fixed text written in every record (see "Fixed texts"). |

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

### Fixed texts

`{"from": "=BK", "to": "942$c"}` writes "BK" in every record: into the
field the record already has (into every copy, for 952), or into a new
field with the usual indicators. A fixed text fills, it never overwrites: a
record that already holds that subfield keeps its own value. A 952 fixed
text never makes a copy where there is none. The panel's "Fixed text for
every record" on a column writes `{"from": column, "to": "ignore"}` plus the
fixed text to the column's field, so the column's values are replaced.

### Mais opções (`options`, kei_import/tidy.py)

All off by default, rule-based, the same code in the preview and the import:

| Option | What it does |
|---|---|
| `clean` | Safe spelling repair: double-encoded accents (`JosÃ©` → `José`), control characters, repeated and edge spaces (ISBD spacing such as ` :` stays), and one OCR slip inside a word: a `0` or `1` between two letters on each side, in a word with no other digit (`Hist0ria`, `Sa1vador`). Coded fields (0XX, 856, 942, 952, 999) get only the spaces and control characters. No dictionary, so no word is guessed. |
| `case` | Text typed all in capitals (90% of at least four letters) written as a catalogue writes it, with the engine's `rules.smart_case`: names (1XX, 600-611, 7XX, 800), places and publishers (260/264), series in title case with lowercase particles; titles (245 `$a$b$n$p`), editions, notes and subjects in sentence case, keeping acronyms, Roman numerals, known places and the words of the record's own names ("MEMORIAS DE MACHADO DE ASSIS" → "Memorias de Machado de Assis" when 100 is Assis, Machado de). Accents missing from the file are not restored. |
| `group` | Records of the same book joined into one, their copies (952) and extra ISBNs kept: same first author's surname, title similarity ≥ 0.9 (Levenshtein), publisher similarity ≥ 0.8 when both have one ("Editora Ática" = "Ática"), same year when both have one, same edition and volume numbers, and no two different valid ISBNs. The stream is read three times, one record at a time. |

Spreadsheets already get recasing and grouping when the engine builds
their records; the options also run on those records afterwards.

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
preview); it answers "ok" once a mapping with changes (or options) is
written, "cancel" when the librarian skips or changed nothing.

Laid out after the librarians' sketch `exemplo ferramenta de importação.xlsx`
(1.5.84):

```
┌ Editar mapeamento de campos ─────────────────────────────────────────────────────────┐
│ acervo.iso · 11.488 registro(s) · amostra de 10                  ◀ Exemplo 4 de 10 ▶ │
│ ╭──────────────────────────────────────────────────────────────────────────────────╮ │
│ │ #  campo 1 · 001     campo 2 · 020$a    campo 5 · 245$a       campo 6 · 260$a    │ │
│ │    = Número de contr = ISBN             = Título              = Local de publ…   │ │
│ │ 1  8898              9788576658085 (b…  O colecionador de l…  São Paulo:         │ │
│ │ 4  10812             8585517085         VOCE E A CONSTITUIC…  SAO PAULO :        │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────╯ │
│ ━━━  ↕ arraste para aumentar ou diminuir a tabela (Ctrl+↑ / Ctrl+↓)  ━━━              │
│ campo 5 · exemplo 4: VOCE E A CONSTITUICAO :  · 23 caractere(s)  ⚠ tudo em maiúsculas │
│ ╭ Mapeamento de campo 5 ──────────────────╮ ╭ Mais opções ──────────────────────────╮ │
│ │ Selecionar campo [campo 5 (245$a)     ▾]│ │ Deseja conhecer melhor os campos?     │ │
│ │ Função [campo 5 (245$a - Título) (manter)▾]│ MARC 21 (Library of Congress) ↗  Campo 245 ↗ │
│ │          [820$a] [texto p/ todos]       │ │ [X] Junção inteligente de exemplares  │ │
│ ╰─────────────────────────────────────────╯ │ [X] Correção de maiúsculas/minúsculas │ │
│                                             │ [ ] Correção ortográfica inteligente  │ │
│                                             │ Na amostra: 3 valor(es) ... · 1 juntado │
│                                             ╰───────────────────────────────────────╯ │
│ 0 mudança(s) · 0 de fora · 6 aviso(s)   [Prévia do registro] [Restaurar] [Pular] [Aplicar] │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- Grid (`DataTable`, cell cursor, record number frozen, 20 characters per
  column): headers "campo N · source" over the destination (`= name` dim,
  `→ TAG$c` changed, `✕` left out, `✎` fixed text). Empty cells `·`,
  repeated fields `×N`, dirty values yellow, left-out values struck through.
- Splitter under the grid: drag it with the mouse, or Ctrl+Up / Ctrl+Down.
- The cursor row is the example ("Exemplo N de 10", `[` `]`, ◀ ▶); one line
  under the grid shows the selected value in full with its length and
  warnings (edge spaces, all capitals, broken accents, ISBN-like values,
  control characters).
- Selecionar campo: every column ("campo N (source)"), then "+ Novo texto
  fixo para todos os registros" (a column of its own for a field the file
  doesn't have, such as `942$c = BK`). It follows the grid's cursor and
  moves it.
- Função: "campo N (... ) (manter)", "Campo personalizado" (any TAG$subfield
  typed by hand, checked with the engine's rules), "Texto fixo para todos
  os registros" (field + text), "[Não importar este campo]", Paulo's list
  with names, then the fields of the other columns. Enter on a grid cell
  jumps here.
- Mais opções: the LoC MARC 21 page and the page of the selected tag
  (`bd245.html`; 9XX and Koha's fields open the index) through the panel's
  browser opener (the address is also copied), and the three options with
  what they do to the sample.
- Record preview (button or `p`): the example after the mapping and the
  options, ▸ on changed lines, "Como no arquivo" for the record before,
  ◀ ▶ to step. A spreadsheet row shows each value and where it goes.
- Below 140 columns the two cards stack and scroll; the grid keeps the
  height the splitter gave it.
- New strings are in `lang/pt.cache`; field names in `kei_panel/marc21.py`.
- Demo mode (`--demo`) walks through the screen with a sample ISIS file.
