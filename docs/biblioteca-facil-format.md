# Biblioteca Fácil: database and backup format

How the panel reads Biblioteca Fácil (Library tools > Magic Import Tool, which
recognises the backup or data folder and calls this reader). Reverse engineered from a
backup of the program's version 7 with its empty template database
(`BibFacil7\Vazio`) plus a few test entries; nothing below comes from the
vendor. The layout is checked by the importer on every run (record checksums,
declared sizes, record counts) and anything unexpected is shown in the
preview before a change is made. The loan and patron tables were empty in that
backup, so their contents were checked only with the synthetic backup of
`tests/lib/bf_backup.py`.

## 1. Backup container (.bkp)

Little-endian throughout.

| Offset | Size | Meaning |
|---|---|---|
| 0 | 16 | Engine signature (the same 16 bytes appear at offset 9 of every table file) |
| 16 | 8 | int64, unknown (43100 here; not a file or sum of sizes) |
| 24 | 8 | double, Delphi TDateTime of the backup (46295.3439 = 2026-09-30 08:15:18) |
| 32 | 1+n | ShortString (length byte + text): description |
| .. | 4 | int32: number of tables (15), then one ShortString per table name |

Then one entry per file (`T01_USUA.dat`, `T01_USUA.idx`, ... `T15_RESE.idx`):

| Size | Meaning |
|---|---|
| 1+n | ShortString file name |
| 0 or 4 | `.dat` entries carry 4 extra zero bytes here (`.idx` do not) |
| 8 | int64 uncompressed size |
| 16 | constant block (same in every entry; probably a password hash or GUID) |
| 1 | compression level (6) |
| then | chunks until the size is reached: int32 compressed length + zlib stream; each chunk inflates to at most 65,536 bytes |

The importer locates the first zlib header after the name and checks that the
chunks add up to the declared size, so the 4-byte difference does not matter.

## 2. Table files (.dat): DBISAM 4

The tables are **DBISAM** (Elevate Software, Delphi): `.dat` data, `.idx`
B-tree indexes, `.blb` blobs (none in this schema). The `.idx` files are not
needed for a migration.

Header (512 bytes):

| Offset | Size | Meaning |
|---|---|---|
| 0 | 8 | int64 last autoinc value |
| 8 | 1 | 0x06 |
| 9 | 16 | engine signature |
| 25 | 4 | deleted records |
| 29 | 4 | next row id |
| 41 | 4 | active records (checked against the rows actually read) |
| 45 | 2 | record size in bytes |
| 47 | 2 | number of fields |
| 72 | 1+n | ShortString table description ("Cadastro de Leitores") |

Field descriptors: 768 bytes each, starting at 512.

| Offset | Size | Meaning |
|---|---|---|
| 0 | 2 | field number (1..n) |
| 2 | 1+n | ShortString field name |
| 164 | 1 | type: 1 string, 2 date, 4 boolean, 5 smallint, 6 integer (7 float, 11 datetime, 3 blob exist in DBISAM but not in this schema) |
| 165 | 1 | subtype (29 = autoinc) |
| 166 | 2 | declared string size |
| 169 | 2 | stored length |
| 172 | 2 | offset in the record |

Records start at `512 + fields*768`, `record size` bytes each:

| Offset | Size | Meaning |
|---|---|---|
| 0 | 1 | status: 0 active, 1 deleted |
| 1 | 4 | chain pointer |
| 5 | 4 | row id |
| 9 | 16 | MD5 of bytes 25..end (checked: every record in the backup matches) |
| field offset | 1 | 1 = has a value, 0 = NULL |
| +1 | len | value |

Values: strings are fixed-size, NUL-terminated, **Windows-1252**; dates are
int32 days where 1 = 0001-01-01; booleans and smallints int16; integers int32.

On top of DBISAM's own deleted flag, most tables have an `*_EXCLUSAO` date:
the program's soft delete. Rows with that date are treated as deleted.

## 3. Tables and relationships

| Table | Content | Key | Links |
|---|---|---|---|
| T01_USUA | program operators (login, **plain-text password**, level, rights) | NUMUSUARIO | T02 |
| T02_ACES | operator permissions | NUMACESSO | NUMUSUARIO → T01 |
| T03_CONF | settings, one row (loan days DIAS, items per loan LIMITEITENSEMPR, receipt options) | | |
| T04_LEIT | patrons: LEITOR (name), SEXO/SEXO2, IDENTIDADE (RG), CPF, NOMEPAI, NOMEMAE, ENDERECO, BAIRRO, CIDADE, ESTADO, CEP, PONTOREFER, INTERNET (e-mail), OBS1-2, ESCOLARIDADE, NATURALIDADE, TELEFONE1-2, FONECONTATO, NOMECONTATO, DATACADASTRO, DATANASC, EXCLUSAO, DESATIVADO, MATRICULA, TURMA, TURNO/TURNO2, FOTO | NUMLEITOR | |
| T05_AUTO | authors (name in direct order, e.g. "MONTEIRO LOBATO") | NUMAUTOR | |
| T06_EDIT | publishers + LOCALIZACAO (city) | NUMEDITORA | |
| T07_CLAS | "classificação literária" (genre, sometimes a number: "BIOGRAFIA", "920.71") | NUMCLASSIFIC | |
| T08_TIPO | item types + QTDDIAS (loan days) | NUMTIPOITEM | |
| T09_ACER | **one row per copy**: TITULO, SUBTITULO, EDICAO, ANOEDICAO/ANOEDICAO2, VOLUME, EXEMPLAR, TOMBO (accession no.), ISBN, CDD, CDU, CUTTER, PAGINAS, PALAVRAS1-5, OBS1-2, LOCAL, AQUISICAO, BAIXA (withdrawn), NAOEMPRESTAR, EMPRESTADO, RESERVADO, FOTO | NUMACERVO | NUMEDITORA → T06, NUMTIPOITEM → T08, NUMCLASSIFIC → T07, NUMIDIOMA → T14 |
| T10_AUAC | authors of each copy, in order | SEQUENCIA | NUMACERVO → T09, NUMAUTOR → T05 |
| T11_MOVI | loan lines: PREVISAO (due), DEVOLUCAO (returned), EXCLUSAO, EXCLUIDOPOR | NUMMOVIMENTO | NUMACERVO → T09, NUMEMPRESTIMO → T13 |
| T12_INDC | table of contents lines (INDICE, PAGINA) | SEQUENCIAL | NUMACERVO → T09 |
| T13_MOVM | loan header: patron and date | NUMEMPRESTIMO | NUMLEITOR → T04 |
| T14_IDIO | languages ("PORTUGUES") | NUMIDIOMA | |
| T15_RESE | holds: DATA, VALIDADE1-2, UTILIZOU | NUMRESERVA | NUMLEITOR → T04, NUMACERVO → T09 |

## 4. Mapping to Koha (as built in the importer)

- **Catalogue** (MARC 21 through the normal staged MARC import): copies with the
  same title, subtitle, edition, year, publisher, ISBN and authors become one
  record. 020 ISBN, 041/008 language, 080 CDU, 082 CDD, 090 CDD/CDU + Cutter,
  100/700 authors from T10 in order (ind1 0, since names are in direct order),
  245 title/subtitle, 250 edition, 260 place/publisher/year, 300 pages,
  500 notes, 505 contents (T12), 650 keywords (PALAVRAS1-5), 655 literary
  classification (T07), 942 item type. Each copy is a 952 item: TOMBO as barcode
  (a missing or repeated tombo gets `BF<NUMACERVO>`), EXEMPLAR copy number,
  VOLUME enumchron, LOCAL shelving location, AQUISICAO accession date, BAIXA
  withdrawn, NAOEMPRESTAR not for loan, and a non-public note
  "Biblioteca Fácil: acervo N" that links loans and holds to the right item.
- **Patrons** (import_patrons.pl): card number = NUMLEITOR; name split into
  first name and surname; CPF checked (modulo 11) and stored as the CPF patron
  attribute when that type exists; TURMA → sort1, TURNO → sort2; RG, parents,
  reference point, schooling, birthplace, notes → borrower notes;
  NOMECONTATO/FONECONTATO → alternate contact; DESATIVADO → restriction.
- **Circulation** (one SQL transaction after a PRE-CIRCULATION backup): open
  loans → issues (and items.onloan), returned loans → old_issues, holds still
  valid → reserves. Rows whose patron or item did not reach Koha are counted and
  skipped.
- **Not migrated**: operators and permissions (T01/T02; plain-text passwords),
  photos (Windows paths). T03's loan days and item limit are shown as a
  suggestion for Koha's circulation rules.
