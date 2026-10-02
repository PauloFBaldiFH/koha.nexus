# ISIS catalogue: PostgreSQL export format

How the panel reads the catalogue of a library that ran CDS/ISIS (Library
tools > Magic Import Tool, which recognises the export and calls this reader).
Written from one real export; nothing below comes from a vendor. Anything the
importer does not recognise is counted in the preview before a change is made.

## 1. The file

The "ISIS backup" is not an ISIS master file (`.mst`/`.xrf`): the ISIS
database was loaded into PostgreSQL and the file is a `pg_dump` of it.

- **Layout**: plain SQL text (`pg_dump -Fp`), UTF-8 declared by
  `SET client_encoding = 'UTF8'`, Windows line ends (CRLF), data in
  `COPY ... FROM stdin;` blocks ended by `\.`. No compression.
- **Also accepted**: the same dump compressed with gzip, bzip2, zlib or zip
  (detected by content, not by extension); `INSERT INTO` statements instead of
  `COPY` (`pg_dump --inserts`, with or without a column list, text on several
  lines, `E'...'` escapes); `LATIN1`/`WIN1252` dumps; UTF-8 with a byte order
  mark or UTF-16. A custom-format dump (`pg_dump -Fc`, starts with `PGDMP`) is
  turned back into SQL by `pg_restore` when it is installed, otherwise the
  panel asks for a plain export.
- **Noise**: bytes before the dump's first SQL line and after
  `-- PostgreSQL database dump complete` are left out and counted. Lines that
  are not valid UTF-8 in a UTF-8 dump are read as Windows-1252. A dump cut in
  the middle of a table keeps the complete rows and says so in the preview.

COPY text format: tab-separated, `\N` is NULL, and `\\`, `\t`, `\n`, `\r`,
octal and `\x` escapes are decoded. A row with the wrong number of columns is
skipped and counted.

## 2. Tables

| Table | Rows (example) | Use |
|---|---|---|
| `acervo` | one per ISIS record (MFN), including emptied records with no title | Catalogue: one MARC 21 record per row |
| `ocorrencias` | a handful | Remarks on a copy (`cod_livro` = tombo): note on the item; `extraviado = t` marks it lost |
| sequences `acervo_mfn_seq`, `cad_geral` | | Not used |

The catalogue table is found by its `titulo` column (the largest table with
one), not by name. There are no patron, loan or hold tables in this export;
any other table is listed in the preview as not migrated.

## 3. Columns of `acervo` and MARC 21

Columns are matched by name with accents, case and punctuation ignored, so a
renamed or reordered export still maps. The preview prints this table.

| Column | MARC 21 |
|---|---|
| `mfn` | 035 `(ISIS)<mfn>`, 952 $x |
| `tipo` (M/m monograph, n, s serial; typos such as `mp`) | Leader/07 (`s` = serial, anything else `m`) |
| `idioma` (POR, por, ING, esp, FRE, ALE...) | 008/35-37 and 041 (ING→eng, ESP→spa, ALE→ger, FRA→fre...) |
| `n_chamada` (`869.3 A994c`) | 082 $a (class), 090 $a $b (class, Cutter), 952 $o |
| `registro` (tombos) | one 952 per tombo: $p barcode, $h volume (section 4) |
| `aut_pes` / `aut_ent` / `aut_ev` | 100 / 110 / 111 (the first one found is the main entry; `<FREI>` becomes $c) |
| `aut_sec_pes` / `_ent` / `_ev` (split on `;`) | 700 / 710 / 711 |
| `titulo` (`<O> CORTIÇO`) | 245, nonfiling characters from the `<article>` mark; `<XII=DOZE>` keeps `XII` |
| `edicao` | 250 |
| `local_editor` (`Sao Paulo Atica`, `RIO DE JANEIRO: SEXTANTE, 2007`) | 260 $a place, $b publisher, $c year |
| `_data` | a year: 260 $c and 008; a full date (`22/05/2013`, `2022-09-13`, the date the copy was registered): 952 $d |
| `colacao_mon_e_an_mon` (`459 p`) | 300 |
| `colacao_an_per` | 362 |
| `serie` | 490 |
| `notas_gerais`, `nota_de_publ_c` | 500 |
| `nota_de_tese` / `nota_de_cont` / `nota_de_convenio` | 502 / 505 / 536 |
| `aut_*_todo`, `titulo_todo` (the host work) | 773 $a, $t |
| `assunto` (`<A><B>` or `A; B`; `/` and ` - ` are subdivisions) | 650 _4 $a $x |
| `centro_cooperante` | 500 |

The place in `local_editor` is split off at `:`, `,` or `.`, at `Place-UF`,
or by matching a known place name at the start (a built-in list plus the
places the same export writes with a separator). When no place is found the
whole text goes to 260 $b and is counted.

## 4. The `registro` field (tombos)

One field holds the accession numbers (tombos) of every copy of the title,
typed by hand over the years. Patterns seen, and how they are read:

| Written | Copies (952 $p, $h) |
|---|---|
| `-1001` | 1001 (the leading `-` is the old ISIS repeat mark) |
| `-1655 v1 - 1656 v2`, `-2201 v1-2202 v2` | 1655 v. 1, 1656 v. 2 (hyphens separate copies) |
| `-2134 I^f2135 II^f2136 III` | 2134 v. I, 2135 v. II, 2136 v. III: `^f` is the ISIS subfield delimiter left in the text, a copy separator |
| `-3404^3462`, `-22^23`, `-5722 v11^5721 v12` | a bare caret between two tombos is a separator too |
| `^3100`, `-3200^`, `d^3300`, `-3400 v9^ -` | a caret at either end, or glued to a stray letter, is noise |
| `-4101, 4102 v1` | two copies of v. 1 (commas separate tombos of one volume) |
| `-669 a 672`, `-7670 v1 a 7673 v4` | ranges ("a" = to), expanded when they span at most 100 tombos and the volumes line up |
| `-4779 v54495 v6` | volume glued to the next tombo: v. 5 on 4779, then 4495 v. 6 (split by the length of the tombo before it) |
| `-1111,1112 1ª serie - 1113 2ª serie` | volume "1ª série", "2ª série" |
| `-2717$ - 2718` | `$` dropped, noted on the item |
| `-5130(Baixa)`, `516 (atrasado)` | baixa = withdrawn (952 $0); other words in brackets go to the note |
| `h5705`, `-e5706`, `~d5707`, `5708h5709` | stray letters dropped; between two numbers they separate copies |
| `-6001 - 863 M42 - 6002` | a call number typed in the field is not a tombo |
| `-`, `Informação não encontrada`, `-Sobrenome, Nome` | no tombo: one item with barcode `ISIS<mfn>` |

A tombo already used by an earlier copy (in the same record or another) keeps
its first owner; the later copy gets `ISIS<mfn>-<n>` and a note naming the
tombo and the MFN that has it. Every item keeps the original field in its
internal note (952 $x `ISIS MFN <mfn>; registro: <as typed>`).

## 5. Text cleaning (all fields)

- `Informação não encontrada` (with any trailing spaces), blank strings and a
  literal `\N` are empty.
- Control characters (for example `\x02` inside a call number) and escape
  leftovers typed as text (`\t`, `\\`) are removed; spaces are collapsed.
- `Ẃ` and `ẃ` are `ª` and `º`: the old text was Latin-1 read as ISO-8859-14
  (`8Ẃ ed` = `8ª ed`, `1Ẃ serie`). All the letters that code page moves are
  put back.
- Capital words with small accented letters (`INTRODUçãO`, from an
  upper-casing that skipped accents) are upper-cased.
- A caret inside a title becomes the 245 $a/$b split; in the imprint it
  separates place and publisher; elsewhere it becomes a space. These records
  are listed by MFN in the preview, because an ISIS subfield letter may be
  glued to the next word (`...^CINTRODUCAO`).
- Rows without a title are not imported; the ones that still carry a tombo
  are listed by MFN.
