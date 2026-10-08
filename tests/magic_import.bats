#!/usr/bin/env bats
# Magic Import Tool (Library tools > 1): the kei_import engine (Python, run
# as the instance user through koha-shell) on synthetic files of every kind
# it reads, the questions it asks, Koha backups sent to Restore database,
# and the commit through Koha's own tools (the test doubles of
# tests/mocks/koha-script on a real MariaDB). Real yaz-marcdump and
# MARC::Record. No real catalogue or patron data: every file is made here or
# by tests/lib (import_fixtures.py, bf_backup.py, isis_dump.py).

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_tools_catalog
    kei_br_catalog
    unset KEI_SELECT_FILE KEI_DEFAULT_ANSWER KEI_EXTRA MAGIC_DROP_DIRS
    W="$BATS_TEST_TMPDIR"
}

teardown() {
    kei_kill_daemons
}

pre_backups() { find /var/backups/koha_sql -maxdepth 1 -name "PRE-${1:-}*" 2>/dev/null | wc -l; }
extra()       { printf '%s\n' "$@" > "$W/extra.sh"; export KEI_EXTRA="$W/extra.sh"; }
marc_dump()   { yaz-marcdump "$1" 2>/dev/null; }
xml_dump()    { yaz-marcdump -i marcxml -o line "$1" 2>/dev/null; }
bibs()        { tools_sql "SELECT COUNT(*) FROM biblio;"; }
preview()     { cat "$KEI_S/textboxes.log" 2>/dev/null; }
fixtures()    { python3 "$KEI_REPO/tests/lib/import_fixtures.py" "$W/fx"; }
bf_backup()   { python3 "$KEI_REPO/tests/lib/bf_backup.py" "$@"; }
isis_dump()   { python3 "$KEI_REPO/tests/lib/isis_dump.py" "$@"; }
# Restore database is the subject of tests/restore.bats: here it only says
# which file it was handed, and that the file was there.
restore_double() { extra 'function_restore_database() { [ -s "$1" ] && echo "RESTORE $1" >> /run/kei-mock/calls.log; }'; }
# Menus also record their text (the item question lists the subfields).
menu_texts()  { extra 'ui_menu() { local title="$1" ans; printf "%s\n" "$2" >> "$KEI_S/menus.log"; shift 2; ans=$(_kei_next_input); [ -n "$ans" ] || ans="${1:-}"; _kei_dialog "MENU [$title] => $ans"; [ "$ans" = "CANCEL" ] && return 1; printf "%s" "$ans"; }'; }
engine_ran()  { grep -q "^koha-shell library -c \"/usr/bin/python3\" \"-I\" \"-B\" \"/tmp/koha_tools\.[^\"]*/kei/kei_import_run.py\" \"$1\"" "$KEI_S/calls.log"; }

# A Biblivre-like export: accession numbers (tombo) in 949 $a, call number
# in 090, leader/09 blank. Record 3 already has a 952.
biblivre_xml() {
    cat > "$W/biblivre.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record><leader>00000nam  2200000 a 4500</leader><controlfield tag="001">1</controlfield>
  <datafield tag="082" ind1="0" ind2="4"><subfield code="a">869.3</subfield></datafield>
  <datafield tag="090" ind1=" " ind2=" "><subfield code="a">869.3</subfield><subfield code="b">A848d</subfield></datafield>
  <datafield tag="100" ind1="1" ind2=" "><subfield code="a">Assis, Machado de,</subfield><subfield code="d">1839-1908.</subfield></datafield>
  <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Dom Casmurro /</subfield><subfield code="c">Machado de Assis.</subfield></datafield>
  <datafield tag="260" ind1=" " ind2=" "><subfield code="a">São Paulo :</subfield><subfield code="b">Ática,</subfield><subfield code="c">1997.</subfield></datafield>
  <datafield tag="949" ind1=" " ind2=" "><subfield code="a">000123</subfield></datafield>
  <datafield tag="949" ind1=" " ind2=" "><subfield code="a">000124</subfield></datafield>
</record>
<record><leader>00000nam  2200000 a 4500</leader><controlfield tag="001">2</controlfield>
  <datafield tag="245" ind1="0" ind2="0"><subfield code="a">Iracema :</subfield><subfield code="b">lenda do Ceará /</subfield><subfield code="c">José de Alencar.</subfield></datafield>
  <datafield tag="949" ind1=" " ind2=" "><subfield code="b">sem tombo</subfield></datafield>
</record>
<record><leader>00000nam  2200000 a 4500</leader><controlfield tag="001">3</controlfield>
  <datafield tag="245" ind1="0" ind2="0"><subfield code="a">Já catalogado no Koha</subfield></datafield>
  <datafield tag="952" ind1=" " ind2=" "><subfield code="a">X</subfield><subfield code="p">999</subfield></datafield>
</record>
</collection>
XML
}

# Three records already in Koha's layout (one with its item in 952), UTF-8.
koha_marc() {
    cat > "$W/books.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record><leader>00000nam a2200000 a 4500</leader><datafield tag="245" ind1="0" ind2="0"><subfield code="a">Um</subfield></datafield></record>
<record><leader>00000nam a2200000 a 4500</leader><datafield tag="245" ind1="0" ind2="0"><subfield code="a">Dois</subfield></datafield></record>
<record><leader>00000nam a2200000 a 4500</leader><datafield tag="245" ind1="0" ind2="0"><subfield code="a">Três</subfield></datafield>
  <datafield tag="952" ind1=" " ind2=" "><subfield code="a">CPL</subfield><subfield code="b">CPL</subfield><subfield code="p">999</subfield></datafield></record>
</collection>
XML
    yaz-marcdump -i marcxml -o marc -f UTF-8 -t UTF-8 -l 9=97 "$W/books.xml" > "$W/books.mrc"
}

# Windows-1252 patron spreadsheet with Portuguese headers, semicolons, quoted
# fields, formatted CPFs, one invalid and one repeated CPF, one line without a name.
# A CPF never refuses a patron: the invalid one is imported, the repeated one
# is refused only because, with no card number column, it is a repeated card.
legacy_csv() {
    printf 'Nome;CPF;E-mail;Data de Nascimento;Sexo;Cidade\r\n"Ana Maria Souza";529.982.247-25;ana@x.br;05/03/2001;Feminino;S\xe3o Paulo\r\nJo\xe3o Lima;111.444.777-35;;12/12/1999;M;"Palotina; PR"\r\nPedro Errado;123.456.789-00;;;;\r\nAna Dup;52998224725;;;;\r\n;390.533.447-05;;;;\r\n' > "$W/leitores.csv"
}

# A Biblioteca Fácil collection spreadsheet saved by Excel (Windows-1252).
biblioteca_facil_csv() {
    cat <<'EOF' | iconv -f UTF-8 -t WINDOWS-1252 > "$W/acervo.csv"
Tombo;Título;Subtítulo;Autor;Editora;Local;Ano;Edição;ISBN;CDD;Cutter;Assunto;Exemplar;Tipo;Data de aquisição;Valor;Observação da escola
0001;O cortiço;;Azevedo, Aluísio;Ática;São Paulo;1997;2;978-85-08-00001-3;869.3;A994c;"Romance brasileiro; Naturalismo";1;Livro;05/03/2020;R$ 25,90;x
0002;O cortiço;;Azevedo, Aluísio;Ática;São Paulo;1997;2;978-85-08-00001-3;869.3;A994c;"Romance brasileiro; Naturalismo";2;Livro;05/03/2020;;
0003;Revista Ciência Hoje;n. 300;;SBPC;Rio de Janeiro;2013;;;505;;Ciência;;revista;;;
0001;Duplicado;;Autor, Teste;;;;;;;;;;;;;
;;;Sem título;;;;;;;;;;;;;
EOF
}

# Columns and tables of Koha that the Biblioteca Fácil loans and holds are written to.
bf_circ_schema() {
    tools_sql "ALTER TABLE items ADD COLUMN itemnotes_nonpublic longtext, ADD COLUMN onloan date;
      CREATE TABLE reserves (reserve_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, borrowernumber int(11) NOT NULL, reservedate date,
        biblionumber int(11) NOT NULL, branchcode varchar(10), priority smallint(6) NOT NULL DEFAULT 1, expirationdate date)
        DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
}

# --- MARC files ----------------------------------------------------------------

@test "I01 MARC in Koha's layout: the engine as the instance user, Koha's staged preview, PRE-IMPORT backup, then the import" {
    koha_marc
    export KEI_SELECT_FILE="$W/books.mrc"
    inputs keep
    answer yes yes          # go on; import the staged batch
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'engine_ran analyse && engine_ran build' "the engine runs through koha-shell, isolated: $(calls)"
    assert 'grep -q "^stage_file.pl --file /tmp/koha_tools\.[^ ]*/books.mrc --format ISO2709 --encoding UTF-8 --add-items --comment koha-easy-installer [0-9-]* books.mrc --match 1 --no-replace \[pre=0\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^commit_file.pl --batch-number 1 \[pre=1\]" "$KEI_S/calls.log"' "the import comes after the safety backup: $(calls)"
    local pre; pre=$(ls /var/backups/koha_sql/PRE-IMPORT_*.sql.gz)
    assert 'gzip -t "$pre" && zcat "$pre" | tail -n1 | grep -q "Dump completed"' "PRE-IMPORT backup must be complete"
    assert 'preview | grep -q "^== books.mrc  (ISO 2709, 3 record(s), encoding UTF-8)" && preview | grep -q "^Items: 1 in 952, as Koha keeps them"' "$(preview)"
    assert '! dialogs | grep -q "MENU \[🪄  Magic Import Tool\]"' "no question, and no library or item type for records that bring their own items"
    assert 'dialogs | grep -q "Records: 3\\\\n  Items: 1\\\\n  Patrons: 0"' "$(dialogs)"
    assert 'dialogs | grep -q "^OK ✅ Successfully imported 3 bibliographic record(s), 3 item(s) and 0 patron(s) with zero manual mapping required"' "$(dialogs | tail -2)"
    assert '[ "$(bibs)" = "203" ]'
    assert '[ -z "$(ls -d /tmp/koha_tools.* 2>/dev/null)" ]' "the work folder must be removed on exit"
}

@test "I02 declined at the overall preview or at Koha's dry run: nothing imported, no backup" {
    koha_marc
    export KEI_SELECT_FILE="$W/books.mrc"
    answer no
    panel lt_magic_import
    assert '! grep -q "stage_file.pl" "$KEI_S/calls.log"' "$(calls)"
    assert 'dialogs | grep -q "^INFO .*Nothing was imported"'
    : > "$KEI_S/calls.log"
    inputs new
    answer yes no
    panel lt_magic_import
    assert 'grep -q "^stage_file.pl" "$KEI_S/calls.log" && ! grep -q "^stage_file.pl.*--match" "$KEI_S/calls.log"' "mode 'new' must not match records: $(calls)"
    assert '! grep -q "^commit_file.pl" "$KEI_S/calls.log"'
    assert '[ "$(pre_backups)" = "0" ] && [ "$(bibs)" = "200" ]'
    assert 'dialogs | grep -q "Nothing was added to the catalog"'
}

@test "I03 empty, unknown and custom-format files: refused or explained, never sent to Koha" {
    local f
    : > "$W/empty.mrc"
    echo "hello" > "$W/text.mrc"
    head -c 4000 /dev/urandom > "$W/estragado.bkp"
    printf 'PGDMP\001\016\000' > "$W/custom.backup"
    for f in empty.mrc text.mrc estragado.bkp custom.backup; do
        export KEI_SELECT_FILE="$W/$f"
        panel lt_magic_import
    done
    assert '! grep -q "stage_file.pl\|import_patrons.pl" "$KEI_S/calls.log" 2>/dev/null' "$(calls)"
    assert '[ "$(dialogs | grep -c "^ERROR.*empty or cannot be read")" = "1" ]' "$(dialogs)"
    assert '[ "$(dialogs | grep -c "^INFO .*Nothing in it can be imported")" = "3" ]' "$(dialogs)"
    assert 'preview | grep -q "estragado.bkp: format not recognised" && preview | grep -q "export it again as plain SQL (pg_dump -Fp)"' "$(preview)"
    assert '! preview | grep -q "^Settings:\|^Importable:"' "the operator sees the files, not the engine's bookkeeping"
    assert '[ "$(bibs)" = "200" ] && [ "$(pre_backups)" = "0" ]'
}

@test "I04 Koha backups go to Restore database: dropped as they are, or found in an archive" {
    fixtures
    restore_double
    export KEI_SELECT_FILE="$W/fx/koha-backup.sql"
    answer yes
    panel lt_magic_import
    assert 'grep -qx "RESTORE $W/fx/koha-backup.sql" "$KEI_S/calls.log"' "$(calls)"
    assert '! grep -q "kei_import" "$KEI_S/calls.log"' "a backup is never copied or read by the engine"
    # In an archive with other files: restore it, or import the other files.
    gzip -k "$W/fx/koha-backup.sql"
    (cd "$W/fx" && zip -q "$W/pacote.zip" koha-backup.sql.gz ACERVO.DBF ACERVO.DBT)
    : > "$KEI_S/calls.log"
    export KEI_SELECT_FILE="$W/pacote.zip"
    inputs restore
    panel lt_magic_import
    assert 'grep -q "^RESTORE /var/tmp/kei-restore\.[^/]*/koha-backup.sql.gz$" "$KEI_S/calls.log"' "$(calls)"
    assert '[ -z "$(ls -d /var/tmp/kei-restore.* 2>/dev/null)" ] && [ -z "$(ls -d /tmp/koha_tools.* 2>/dev/null)" ]' "the copies go once the restore is done"
    assert '! grep -q "stage_file.pl" "$KEI_S/calls.log"'
    : > "$KEI_S/calls.log"; rm -f "$KEI_S/textboxes.log"
    inputs import CPL LIVRO
    answer no
    panel lt_magic_import
    assert '! grep -q "^RESTORE" "$KEI_S/calls.log"' "$(calls)"
    assert 'preview | grep -q "Koha backup (goes to Restore database, not imported here): pacote.zip/koha-backup.sql.gz" && preview | grep -q "^Records: 2$"' "$(preview)"
    # Declined: nothing at all.
    : > "$KEI_S/calls.log"
    export KEI_SELECT_FILE="$W/fx/koha-backup.sql"
    answer no
    panel lt_magic_import
    assert '[ ! -s "$KEI_S/calls.log" ]' "$(calls)"
}

@test "I05 Biblivre: Latin-1 export recognised, 949 tombo moved to 952 by MARC::Record, then Koha's staged import" {
    biblivre_xml
    kei_marc "$W/acervo.mrc" ISO-8859-1 "$W/biblivre.xml"
    assert '! iconv -f UTF-8 -t UTF-8 "$W/acervo.mrc" >/dev/null 2>&1' "the fixture must be Latin-1"
    export KEI_SELECT_FILE="$W/acervo.mrc"
    inputs CPL LIVRO new
    answer yes yes
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    local f="$KEI_S/last-staged.mrc"
    assert 'preview | grep -q "^== acervo.mrc  (ISO 2709, 3 record(s), encoding ISO_8859-1)" && preview | grep -q "^Items: field 949 moved to 952, one item per field:"' "$(preview)"
    assert 'preview | grep -qx "  949 \$a -> 952 \$p, barcode: 000123, 000124" && preview | grep -qx "  949 \$b not used, values not recognised: sem tombo"' "the tombo is read as the barcode: $(preview)"
    assert '[ -s "$f" ] && iconv -f UTF-8 -t UTF-8 "$f" >/dev/null' "the staged file must be UTF-8"
    assert '[ "$(head -c 10 "$f" | tail -c 1)" = "a" ]' "leader/09 must say Unicode"
    assert 'marc_dump "$f" | grep -q "São Paulo : \$b Ática"' "accents kept: $(marc_dump "$f" | grep ^260)"
    assert 'marc_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$o 869.3 A848d \$p 000123"' "$(marc_dump "$f" | grep ^952)"
    assert 'marc_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$o 869.3 A848d \$p 000124"'
    assert '[ "$(marc_dump "$f" | grep -n "000123" | cut -d: -f1)" -lt "$(marc_dump "$f" | grep -n "000124" | cut -d: -f1)" ]' "items keep their order"
    assert '! marc_dump "$f" | grep -q "^949"' "legacy item fields removed once moved"
    assert 'marc_dump "$f" | grep -qx "952    \$a X \$p 999"' "an existing 952 is left alone"
    assert 'grep -q "Items without barcode: 1" "$KEI_S/textboxes.log"' "the preview reports items without barcode"
    assert 'grep -q "^stage_file.pl .*--format ISO2709 --encoding UTF-8 .*acervo.mrc \[pre=0\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^commit_file.pl --batch-number 1 \[pre=1\]" "$KEI_S/calls.log"' "import only after the PRE-IMPORT backup"
    assert '[ "$(bibs)" = "203" ]'
}

@test "I06 missing yaz-marcdump: offered install, and nothing happens without it" {
    biblivre_xml
    kei_marc "$W/acervo.mrc" UTF-8 "$W/biblivre.xml"
    export KEI_SELECT_FILE="$W/acervo.mrc"
    extra 'YAZ_MARCDUMP=/nonexistent/yaz-marcdump'
    answer yes
    panel lt_magic_import
    assert 'grep -q "^apt_install yaz" "$KEI_S/calls.log"' "the yaz package must be offered: $(calls)"
    assert 'dialogs | grep -q "could not be installed"'
    assert '! grep -q "remap952\|stage_file" "$KEI_S/calls.log"'
    : > "$KEI_S/calls.log"
    answer no
    panel lt_magic_import
    assert '! grep -q "apt_install\|remap952\|stage_file" "$KEI_S/calls.log" 2>/dev/null' "refusing the install stops here"
}

@test "I07 MARC questions: an unknown item field and a character set the bytes cannot settle" {
    python3 - "$W/local.mrc" <<'PY'
import sys
def rec(fields):
    dirs = data = b""
    for tag, body in fields:
        body += b"\x1e"
        dirs += tag + b"%04d%05d" % (len(body), len(data))
        data += body
    base = 24 + len(dirs) + 1
    return b"%05dnam  22%05d   4500" % (base + len(data) + 1, base) + dirs + b"\x1e" + data + b"\x1d"
with open(sys.argv[1], "wb") as fh:
    fh.write(rec([(b"245", b"10\x1faJos\xe9 de Alencar"), (b"500", b"  \x1faCear\xe2a"), (b"945", b"  \x1fbT-100\x1fcx")]))
    fh.write(rec([(b"245", b"10\x1faIracema"), (b"945", b"  \x1fbT-101\x1fcx")]))
PY
    export KEI_SELECT_FILE="$W/local.mrc"
    menu_texts
    inputs ISO_8859-1 items CPL LIVRO new
    answer yes yes
    panel lt_magic_import
    assert '[ "$(dialogs | grep -c "^MENU \[🪄  Magic Import Tool\] => \(ISO_8859-1\|items\)$")" = "2" ]' "$(dialogs)"
    assert 'grep -q "may keep their copies in field 945" "$KEI_S/menus.log" && grep -qF '\''hold:\n  $b: Barcode of the copy (952)\n  $c: (not used)\n\nSample: $b T-100 $c x | $b T-101 $c x'\'' "$KEI_S/menus.log"' "the question says how each subfield is read: $(cat "$KEI_S/menus.log")"
    local f="$KEI_S/last-staged.mrc"
    assert 'preview | grep -q "encoding ISO_8859-1, your answer" && preview | grep -q "^Items: field 945 moved to 952, one item per field:" && preview | grep -qx "  945 \$b -> 952 \$p, barcode: T-100, T-101"' "$(preview)"
    assert 'marc_dump "$f" | grep -qx "245 10 \$a José de Alencar" && marc_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$p T-101"' "$(marc_dump "$f")"
    assert 'dialogs | grep -q "^OK ✅ .*Questions answered: 2"' "$(dialogs | tail -1)"
}

@test "I20 an item field in another system's layout: every subfield read from its values, library and item type checked against Koha" {
    # 949 as many systems export it: call number in $a, barcode in $i,
    # library $b, location $l, item type $t, copy $c, date $d, price $p,
    # status $s. One library (XPL) and one item type (Gibi) Koha does not
    # have, one impossible date; Latin-1 like most Brazilian exports.
    tools_sql "INSERT INTO authorised_values (category, authorised_value, lib) VALUES ('LOC', 'REF', 'Referência'), ('LOC', 'GEN', 'Acervo geral');"
    local i949='<datafield tag="949" ind1=" " ind2=" ">'
    cat > "$W/vendor.xml" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record><leader>00000nam  2200000 a 4500</leader>
  <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Dom Casmurro</subfield></datafield>
  $i949<subfield code="a">869.3 A848d</subfield><subfield code="i">0000101</subfield><subfield code="b">CPL</subfield><subfield code="l">Referência</subfield><subfield code="t">Livro</subfield><subfield code="c">1</subfield><subfield code="d">15/03/2020</subfield><subfield code="p">R\$ 25,00</subfield><subfield code="s">Disponível</subfield></datafield>
  $i949<subfield code="a">869.3 A848d</subfield><subfield code="i">0000102</subfield><subfield code="b">Midway</subfield><subfield code="l">Acervo geral</subfield><subfield code="t">LIVRO</subfield><subfield code="c">2</subfield><subfield code="d">15/03/2020</subfield><subfield code="p">R\$ 25,00</subfield><subfield code="s">Extraviado</subfield></datafield>
</record>
<record><leader>00000nam  2200000 a 4500</leader>
  <datafield tag="245" ind1="0" ind2="0"><subfield code="a">Ciência Hoje</subfield></datafield>
  $i949<subfield code="a">505 C569</subfield><subfield code="i">0000103</subfield><subfield code="b">XPL</subfield><subfield code="l">REF</subfield><subfield code="t">Revista</subfield><subfield code="c">1</subfield><subfield code="d">2019-01-02</subfield><subfield code="p">R\$ 12,50</subfield><subfield code="s">Baixado</subfield></datafield>
</record>
<record><leader>00000nam  2200000 a 4500</leader>
  <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Iracema</subfield></datafield>
  $i949<subfield code="a">869.3 A368i</subfield><subfield code="i">0000104</subfield><subfield code="b">CPL</subfield><subfield code="l">GEN</subfield><subfield code="t">Livro</subfield><subfield code="c">1</subfield><subfield code="d">02/01/2019</subfield><subfield code="p">R\$ 30,00</subfield><subfield code="s">Disponível</subfield></datafield>
</record>
<record><leader>00000nam  2200000 a 4500</leader>
  <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Vidas secas</subfield></datafield>
  $i949<subfield code="a">869.3 R194v</subfield><subfield code="i">0000105</subfield><subfield code="b">CPL</subfield><subfield code="l">GEN</subfield><subfield code="t">Gibi</subfield><subfield code="c">1</subfield><subfield code="d">31/02/2020</subfield><subfield code="p">R\$ 25,00</subfield><subfield code="s">Disponível</subfield></datafield>
</record>
</collection>
XML
    kei_marc "$W/vendor.mrc" ISO-8859-1 "$W/vendor.xml"
    export KEI_SELECT_FILE="$W/vendor.mrc"
    inputs CPL LIVRO new
    answer yes yes
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    assert '! dialogs | grep -q "=> items$"' "a usual item field with a barcode is not asked about: $(dialogs)"
    local p
    for p in '949 $a -> 952 $o, call number: 869.3 A848d, 505 C569, 869.3 A368i' '949 $b -> 952 $a $b, library: CPL, Midway, XPL' \
             '949 $c -> 952 $t, copy number: 1, 2' '949 $d -> 952 $d, date acquired: 15/03/2020, 2019-01-02, 02/01/2019' \
             '949 $i -> 952 $p, barcode: 0000101, 0000102, 0000103' '949 $l -> 952 $c, shelving location: Referência, Acervo geral, REF' \
             '949 $p -> 952 $g, price: R$ 25,00, R$ 12,50, R$ 30,00' '949 $s -> 952 $0/$1/$4/$7, status: Disponível, Extraviado, Baixado' \
             '949 $t -> 952 $y, item type: Livro, LIVRO, Revista' 'library and item type when the field has none Koha knows: CPL, LIVRO' \
             'Items created: 5' 'Items with their library from the field: 4' 'Libraries Koha does not have (your choice used): 1' \
             'Items with their item type from the field: 4' 'Item types Koha does not have (your choice used): 1' \
             'Values left out (location, date, price or status Koha cannot take): 1'; do
        assert 'preview | grep -qxF "  $p" || preview | grep -qxF "$p"' "missing in the preview: $p
$(preview)"
    done
    local f="$KEI_S/last-staged.mrc"
    for p in '$a CPL $b CPL $y LIVRO $c REF $d 2020-03-15 $g 25.00 $o 869.3 A848d $p 0000101 $t 1' \
             '$a MPL $b MPL $y LIVRO $1 1 $c GEN $d 2020-03-15 $g 25.00 $o 869.3 A848d $p 0000102 $t 2' \
             '$a CPL $b CPL $y REV $0 1 $c REF $d 2019-01-02 $g 12.50 $o 505 C569 $p 0000103 $t 1' \
             '$a CPL $b CPL $y LIVRO $c GEN $d 2019-01-02 $g 30.00 $o 869.3 A368i $p 0000104 $t 1' \
             '$a CPL $b CPL $y LIVRO $c GEN $g 25.00 $o 869.3 R194v $p 0000105 $t 1'; do
        assert 'marc_dump "$f" | grep -qxF "952    $p"' "missing 952: $p
$(marc_dump "$f" | grep ^952)"
    done
    assert '! marc_dump "$f" | grep -q "^949"' "legacy item fields removed once moved"
}

@test "I21 MARCXML with MARC 21 holdings (852): library and location only when Koha has them; a 950 that holds no copies is passed over" {
    tools_sql "INSERT INTO authorised_values (category, authorised_value, lib) VALUES ('LOC', 'REF', 'Referência');"
    cat > "$W/holdings.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record><leader>00000nam a2200000 a 4500</leader>
  <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Grande sertão: veredas</subfield></datafield>
  <datafield tag="852" ind1="8" ind2=" "><subfield code="a">CPL</subfield><subfield code="b">Sala 2</subfield><subfield code="c">REF</subfield><subfield code="h">869.3</subfield><subfield code="i">R788g</subfield><subfield code="p">B-001</subfield><subfield code="t">1</subfield><subfield code="z">Só consulta local</subfield></datafield>
  <datafield tag="852" ind1="8" ind2=" "><subfield code="a">MPL</subfield><subfield code="b">Sala 2</subfield><subfield code="j">ARM 12</subfield><subfield code="p">B-002</subfield><subfield code="t">2</subfield><subfield code="x">Doação</subfield></datafield>
  <datafield tag="950" ind1=" " ind2=" "><subfield code="a">Literatura brasileira</subfield></datafield>
</record>
<record><leader>00000nam a2200000 a 4500</leader>
  <datafield tag="245" ind1="0" ind2="0"><subfield code="a">Sagarana</subfield></datafield>
  <datafield tag="852" ind1="8" ind2=" "><subfield code="a">CPL</subfield><subfield code="b">Sala 3</subfield><subfield code="c">REF</subfield><subfield code="h">869.3</subfield><subfield code="i">R788s</subfield><subfield code="p">B-003</subfield></datafield>
  <datafield tag="950" ind1=" " ind2=" "><subfield code="a">Contos</subfield></datafield>
</record>
</collection>
XML
    export KEI_SELECT_FILE="$W/holdings.xml"
    inputs MPL LIVRO new
    answer yes yes
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    assert '! dialogs | grep -q "=> items$"' "$(dialogs)"
    assert 'preview | grep -q "^== holdings.xml  (MARCXML, 2 record(s)" && preview | grep -q "^Items: field 852 moved to 952, one item per field:"' "$(preview)"
    assert 'preview | grep -qxF "  852 \$a -> 952 \$a \$b, library: CPL, MPL" && preview | grep -qxF "  852 \$b not used, not a library Koha has: Sala 2, Sala 3"' "$(preview)"
    local f="$KEI_S/last-staged.mrc"
    assert 'marc_dump "$f" | grep -qxF "952    \$a CPL \$b CPL \$y LIVRO \$c REF \$o 869.3 R788g \$p B-001 \$t 1 \$z Só consulta local"' "$(marc_dump "$f" | grep ^952)"
    assert 'marc_dump "$f" | grep -qxF "952    \$a MPL \$b MPL \$y LIVRO \$o ARM 12 \$p B-002 \$t 2 \$x Doação"' "the shelving number stands in for the call number: $(marc_dump "$f" | grep ^952)"
    assert 'marc_dump "$f" | grep -qxF "952    \$a CPL \$b CPL \$y LIVRO \$c REF \$o 869.3 R788s \$p B-003"'
    assert 'marc_dump "$f" | grep -qxF "950    \$a Contos" && ! marc_dump "$f" | grep -q "^852"' "the 950 stays, the 852 is moved: $(marc_dump "$f")"
}

# --- Spreadsheets ---------------------------------------------------------------

@test "I08 legacy patrons: Windows-1252 spreadsheet, CPFs not refused, the CPF as card number, then Koha's dry run" {
    legacy_csv
    export KEI_SELECT_FILE="$W/leitores.csv"
    inputs CPL PT
    answer yes no yes    # go on; do not update existing; import
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'preview | grep -q "^Patrons ready: 3$" && preview | grep -q "^Rejected: 2$"' "$(preview)"
    assert 'preview | grep -q "^Invalid CPF (imported, not kept as CPF): 1$" && ! preview | grep -q "invalid CPF 123"'
    assert 'preview | grep -q "leitores.csv line 5: duplicate card number (line 2)" && preview | grep -q "leitores.csv line 6: no name"'
    assert 'preview | grep -q "the CPF is used as the card number" && preview | grep -q "(CSV, encoding Windows-1252, separator \";\")"'
    assert '! dialogs | grep -q "MENU \[Records already in the catalog\]"' "no records, no record question"
    assert 'grep -q "^import_patrons.pl .*--matchpoint cardnumber --default branchcode=CPL --default categorycode=PT -v -v \[pre=0\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^import_patrons.pl .*--confirm \[pre=1\]" "$KEI_S/calls.log"'
    assert '[ "$(tools_sql "SELECT CONCAT(firstname, \"|\", surname) FROM borrowers WHERE cardnumber = \"52998224725\";")" = "Ana|Maria Souza" ]'
    assert '[ "$(tools_sql "SELECT surname FROM borrowers WHERE cardnumber = \"11144477735\";")" = "Lima" ]'
    assert '[ "$(tools_sql "SELECT surname FROM borrowers WHERE cardnumber = \"12345678900\";")" = "Errado" ]' "an invalid CPF does not refuse the patron"
    assert 'dialogs | grep -q "^OK ✅ Successfully imported 0 bibliographic record(s), 0 item(s) and 3 patron(s) with zero manual mapping required"'
}

@test "I09 patrons with a card number column: the CPF goes to the CPF attribute" {
    printf 'MATRÍCULA,Nome Completo,Endereço,Nº CPF,Validade\n2024001,Bia Rocha,"Rua A, 10",390.533.447-05,31/12/2026\n2024002,Caio Reis,,123.456.789-00,\n' > "$W/alunos.csv"
    tools_sql "INSERT INTO borrower_attribute_types VALUES ('CPF', 'CPF');"
    export KEI_SELECT_FILE="$W/alunos.csv"
    inputs CPL ST
    answer yes no yes
    panel lt_magic_import
    assert 'preview | grep -qE "MATRÍCULA +-> cardnumber" && preview | grep -qE "Nº CPF +-> cpf"' "$(preview)"
    assert 'preview | grep -q "^Patrons ready: 2$" && preview | grep -q "^Invalid CPF (imported, not kept as CPF): 1$"'
    assert 'preview | grep -q "^Columns for Koha: cardnumber, surname, firstname, address, dateexpiry, patron_attributes$" && ! preview | grep -q "not stored"' "the CPF goes to the CPF attribute"
    assert 'grep -q "^import_patrons.pl .*--confirm \[pre=1\]" "$KEI_S/calls.log"'
    assert '[ "$(tools_sql "SELECT surname FROM borrowers WHERE cardnumber = \"2024001\";")" = "Rocha" ]'
    assert '[ "$(tools_sql "SELECT surname FROM borrowers WHERE cardnumber = \"2024002\";")" = "Reis" ]' "the invalid CPF is imported without its CPF"
}

@test "I10 Biblioteca Fácil spreadsheet: one record per work, one 952 per copy, repeated tombos renumbered, the unclear column asked" {
    biblioteca_facil_csv
    export KEI_SELECT_FILE="$W/acervo.csv"
    inputs ignore CPL LIVRO new
    answer yes yes
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    local f="$KEI_S/last-staged.mrc"
    assert 'dialogs | grep -q "^MENU \[🪄  Magic Import Tool\] => ignore$"' "the school's own column is asked: $(dialogs)"
    assert 'preview | grep -qE "Título +-> title \(1.00\)" && preview | grep -qE "Tombo +-> tombo" && preview | grep -qE "Observação da escola +-> - \(left out\)"' "$(preview)"
    assert 'preview | grep -q "^Records: 3$" && preview | grep -q "^Items created: 4$" && preview | grep -q "^Rows without title (left out): 1$"'
    assert 'preview | grep -q "^Repeated tombos or barcodes renumbered (<code>-<n>, noted in 952 \$x): 1$" && preview | grep -q "^ISBNs with a wrong check digit (kept in 020 \$z): 1$"'
    assert 'grep -q "^stage_file.pl .*records.xml --format MARCXML --encoding UTF-8 .*acervo.csv" "$KEI_S/calls.log"' "MARCXML for the staged import: $(calls)"
    assert '[ "$(xml_dump "$f" | grep -c "^245")" = "3" ]' "$(xml_dump "$f")"
    assert 'xml_dump "$f" | grep -qx "245 12 \$a O cortiço" && xml_dump "$f" | grep -qx "100 1  \$a Azevedo, Aluísio"' "nonfiling article"
    assert 'xml_dump "$f" | grep -qx "260    \$a São Paulo : \$b Ática, \$c 1997" && xml_dump "$f" | grep -qx "250    \$a 2. ed."'
    assert 'xml_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$o 869.3 A994c \$p 0001 \$i 0001 \$t 1 \$d 2020-03-05 \$g 25.90"' "$(xml_dump "$f" | grep ^952)"
    assert 'xml_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$o 869.3 A994c \$p 0002 \$i 0002 \$t 2 \$d 2020-03-05"'
    assert 'xml_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y REV \$o 505 \$p 0003 \$i 0003" && xml_dump "$f" | grep -qx "942    \$c REV"' "item type from its description"
    assert 'xml_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$p 0001-2 \$i 0001 \$x tombo 0001 repetido (acervo.csv, linha 5)"' "repeated tombo renumbered and noted"
    assert 'xml_dump "$f" | grep -qx "020    \$z 9788508000013" && xml_dump "$f" | grep -qx "090    \$a 869.3 \$b A994c" && xml_dump "$f" | grep -qx "650  4 \$a Naturalismo"'
    assert 'grep -q "^commit_file.pl --batch-number 1 \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
}

@test "I11 a spreadsheet without a title column builds nothing" {
    printf 'Tombo;Autor;Editora\n1;Fulano;Ática\n2;Beltrano;Rocco\n' > "$W/semtitulo.csv"
    export KEI_SELECT_FILE="$W/semtitulo.csv"
    inputs CPL LIVRO
    panel lt_magic_import
    assert 'preview | grep -q "No title column: no record can be built from this table."' "$(preview)"
    assert 'dialogs | grep -q "^INFO .*Nothing could be built from it"' "$(dialogs | tail -2)"
    assert '! grep -q "^stage_file.pl" "$KEI_S/calls.log" 2>/dev/null && [ "$(pre_backups)" = "0" ]'
}

@test "I12 XLSX workbook: books and patrons in one sheet kept apart by asking, patron sheet, loans left out; answers remembered for the ODS" {
    fixtures
    export KEI_SELECT_FILE="$W/fx/biblioteca.xlsx"
    inputs author fullname CPL LIVRO new ST
    answer yes no yes yes
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    assert '[ "$(dialogs | grep -c "^MENU \[🪄  Magic Import Tool\] => \(author\|fullname\)$")" = "2" ]' "Autor and Leitor are asked: $(dialogs)"
    assert 'preview | grep -q "^== biblioteca.xlsx: Livros  (XLSX, encoding UTF-8)" && preview | grep -q "^Holds: books and copies, with patrons in the same rows"' "$(preview)"
    assert 'preview | grep -qE "Leitor +-> fullname \(your answer\)" && preview | grep -qE "Autor +-> author \(your answer\)"'
    assert 'preview | grep -q "^Holds: loans or holds (not imported by this version)"' "the loans sheet is recognised and left out"
    assert 'preview | grep -q "^Records: 3$" && preview | grep -q "^Items created: 4$" && preview | grep -q "^Patrons ready: 5$" && preview | grep -q "biblioteca.xlsx: Livros line 5: invalid CPF 123.456.789-00"'
    local f="$KEI_S/last-staged.mrc"
    assert 'xml_dump "$f" | grep -qx "100 1  \$a Assis, Machado de" && ! xml_dump "$f" | grep -q "Ana Maria Souza\|Lima, João"' "patrons never become authors: $(xml_dump "$f")"
    assert 'xml_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$p 5001 \$i 5001 \$d 2023-03-15"' "Excel dates read: $(xml_dump "$f" | grep ^952)"
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM borrowers WHERE cardnumber IN (\"52998224725\", \"11144477735\", \"A1\", \"A2\", \"A3\");")" = "5" ]' "$(tools_sql "SELECT cardnumber, surname FROM borrowers;")"
    assert '[ -n "$(ls /etc/koha-easy-install/import-profiles/*.tsv)" ] && [ "$(stat -c %a /etc/koha-easy-install/import-profiles)" = "700" ]'
    assert 'dialogs | grep -q "^OK ✅ Successfully imported 3 bibliographic record(s), 3 item(s) and 5 patron(s). Questions answered: 2"' "$(dialogs | tail -1)"
    # The same columns in an ODS: no question this time.
    rm -f "$KEI_S/dialogs.log" "$KEI_S/textboxes.log"
    export KEI_SELECT_FILE="$W/fx/biblioteca.ods"
    inputs CPL LIVRO
    answer no
    panel lt_magic_import
    assert '! dialogs | grep -q "=> \(author\|fullname\)$"' "$(dialogs)"
    assert 'preview | grep -qE "Leitor +-> fullname \(saved answer\)" && preview | grep -q "^Patrons ready: 5$" && preview | grep -q "^Items created: 4$"' "$(preview)"
}

@test "I13 XLS and dBase: old Excel and Clipper tables, memo text, deleted rows left out" {
    fixtures
    # The XLS part needs python3-xlwt (to write the fixture) and python3-xlrd.
    if [ -f "$W/fx/biblioteca.xls" ] && python3 -c "import xlrd" 2>/dev/null; then
        export KEI_SELECT_FILE="$W/fx/biblioteca.xls"
        inputs author fullname CPL LIVRO
        answer no
        panel lt_magic_import
        assert 'preview | grep -q "^== biblioteca.xls: Livros  (XLS" && preview | grep -q "^Records: 3$" && preview | grep -q "^Patrons ready: 5$"' "$(preview)"
        rm -f "$KEI_S/textboxes.log"
    fi
    export KEI_SELECT_FILE="$W/fx/ACERVO.DBF"
    inputs CPL LIVRO new
    answer yes yes
    panel lt_magic_import
    local f="$KEI_S/last-staged.mrc"
    assert 'preview | grep -q "^== ACERVO.DBF  (DBF, encoding cp850 (dBase))" && preview | grep -q "^Deleted rows in the table (left out): 1$"' "$(preview)"
    assert 'preview | grep -q "^Records: 2$" && preview | grep -q "^Items created: 3$"' "the two copies of one work make one record: $(preview)"
    assert 'xml_dump "$f" | grep -qx "245 10 \$a Memórias póstumas de Brás Cubas" && xml_dump "$f" | grep -q "Exemplar com dedicatória do autor"' "accents from cp850 and the memo text: $(xml_dump "$f")"
    assert '! xml_dump "$f" | grep -q "Apagado"'
}

@test "I14 a spreadsheet without a header row: what the table holds and its unclear columns are asked" {
    fixtures
    export KEI_SELECT_FILE="$W/fx/sem-cabecalho.csv"
    inputs biblio title author tombo CPL LIVRO new
    answer yes yes
    panel lt_magic_import
    assert 'dialogs | grep -q "^MENU \[🪄  Magic Import Tool\] => biblio$"' "$(dialogs)"
    local f="$KEI_S/last-staged.mrc"
    assert 'preview | grep -q "^Holds: books and copies \[your answer\]" && preview | grep -q "^Records: 2$" && preview | grep -q "^Items created: 3$"' "$(preview)"
    assert 'xml_dump "$f" | grep -qx "245 12 \$a A hora da estrela" && xml_dump "$f" | grep -qx "100 1  \$a Lispector, Clarice"' "$(xml_dump "$f")"
    assert 'xml_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$p 8002 \$i 8002"'
}

# --- Biblioteca Fácil and ISIS backups -------------------------------------------

@test "I15 Biblioteca Fácil backup: records, patrons and circulation in three steps, never the operators' passwords" {
    bf_backup "$W/biblioteca.bkp"
    bf_circ_schema
    tools_sql "INSERT INTO borrower_attribute_types VALUES ('CPF', 'CPF');"
    export KEI_SELECT_FILE="$W/biblioteca.bkp"
    inputs CPL LIVRO new PT
    answer yes no yes yes    # go on; keep registered patrons; import records; import patrons
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    local f="$KEI_S/last-staged.mrc"
    assert 'preview | grep -q "Tables read: 15 of 15" && preview | grep -q "Backup: Backup do dia 30/09/2026 08:15:18 (2026-09-30 08:15)"' "$(preview)"
    assert 'preview | grep -q "^Records: 103$" && preview | grep -q "^Items created: 104$" && preview | grep -q "^Patrons ready: 3$" && preview | grep -q "^Holds still valid: 2$"'
    assert 'dialogs | grep -q "Records: 103\\\\n  Items: 104\\\\n  Patrons: 3\\\\n  Loans: 2\\\\n  Holds: 2"' "$(dialogs)"
    assert '! grep -rq "segredo123" "$KEI_S/textboxes.log" /var/log/koha-easy-install 2>/dev/null' "the operators' passwords never reach a screen or a log"
    assert '[ "$(marc_dump "$f" | grep -c "^245")" = "103" ] && marc_dump "$f" | grep -qx "245 12 \$a O cortiço"'
    assert 'marc_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$o 869.3 A994c \$p 1001 \$t 1 \$c EST1 \$d 2020-03-05 \$x Biblioteca Fácil: acervo 1"' "$(marc_dump "$f" | grep ^952 | head -3)"
    assert 'grep -q "^stage_file.pl .*bf-1-koha.mrc --format ISO2709 --encoding UTF-8 .*biblioteca.bkp \[pre=0\]" "$KEI_S/calls.log" && grep -q "^commit_file.pl --batch-number 1 \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^import_patrons.pl .*--matchpoint cardnumber .*--confirm \[pre=2\]" "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(tools_sql "SELECT GROUP_CONCAT(cardnumber ORDER BY cardnumber) FROM borrowers WHERE categorycode = \"PT\" AND cardnumber IN (\"1\",\"2\",\"4\",\"3\",\"5\");")" = "1,2,4" ]'
    assert 'dialogs | grep -q "No loan or hold to add"' "the mock import has no Biblioteca Fácil items: $(dialogs | tail -3)"
    assert '[ "$(pre_backups CIRCULATION)" = "0" ] && [ -z "$(ls -A /tmp/koha_tools.* 2>/dev/null)" ]' "no circulation change; the work copies (patron data) are gone"
}

@test "I16 Biblioteca Fácil data folder read like the backup; a cut backup builds nothing" {
    bf_backup --folder "$W/Dados"
    export KEI_SELECT_FILE="$W/Dados/T09_ACER.dat"
    inputs CPL LIVRO
    answer no
    panel lt_magic_import
    assert 'preview | grep -q "Dados/T09_ACER.dat: Biblioteca Fácil data folder" && preview | grep -q "^Records: 103$" && preview | grep -q "^Patrons ready: 3$"' "$(preview)"
    bf_backup "$W/biblioteca.bkp"
    head -c 6000 "$W/biblioteca.bkp" > "$W/cortado.bkp"
    rm -f "$KEI_S/textboxes.log"
    export KEI_SELECT_FILE="$W/cortado.bkp"
    inputs CPL LIVRO
    panel lt_magic_import
    assert 'preview | grep -q "Not imported: not a Biblioteca Fácil backup or data folder the panel can read."' "$(preview)"
    assert 'dialogs | grep -q "^INFO .*Nothing could be built from it"'
    assert '! grep -q "^stage_file.pl\|^import_patrons.pl" "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(pre_backups)" = "0" ] && [ "$(bibs)" = "200" ]'
}

@test "I17 ISIS: the PostgreSQL export becomes MARC 21 with one item per tombo, the reader's report in the preview" {
    isis_dump "$W/Backup_ISIS.backup"
    export KEI_SELECT_FILE="$W/Backup_ISIS.backup"
    inputs CPL LIVRO new
    answer yes yes
    panel lt_magic_import
    assert '[ "$status" -eq 0 ]' "$output"
    local f="$KEI_S/last-staged.mrc"
    assert 'preview | grep -q "Noise left out: 25 byte(s) before the dump, 19 byte(s) after it" && preview | grep -q "^Records: 8$" && preview | grep -q "^Items created: 26$"' "$(preview)"
    assert 'preview | grep -q "Patrons, loans and holds: not in this backup"'
    assert '[ "$(marc_dump "$f" | grep -c "^245")" = "8" ] && [ "$(marc_dump "$f" | grep -c "^952")" = "26" ]' "$(marc_dump "$f" | head -40)"
    assert 'marc_dump "$f" | grep -qx "952    \$a CPL \$b CPL \$y LIVRO \$o 823 A95 \$p 2135 \$h v. II \$d 2022-09-13 \$x ISIS MFN 2; registro: -2134 I^f2135 II^f2136 III"' "$(marc_dump "$f" | grep ^952)"
    assert 'grep -q "^commit_file.pl --batch-number 1 \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
}

@test "I18 one zip with an ISIS and a Biblioteca Fácil backup: every stream from one drop" {
    bf_backup "$W/biblioteca.bkp"
    isis_dump "$W/Backup_ISIS.backup"
    (cd "$W" && zip -q "$W/tudo.zip" biblioteca.bkp Backup_ISIS.backup)
    export KEI_SELECT_FILE="$W/tudo.zip"
    inputs CPL LIVRO
    answer no
    panel lt_magic_import
    assert 'preview | grep -q "^tudo.zip/biblioteca.bkp: Biblioteca Fácil backup$" && preview | grep -q "^tudo.zip/Backup_ISIS.backup: ISIS catalogue (PostgreSQL export)$"' "$(preview)"
    assert 'dialogs | grep -q "Records: 111\\\\n  Items: 130\\\\n  Patrons: 3\\\\n  Loans: 2\\\\n  Holds: 2"' "$(dialogs)"
    assert '! grep -q "^stage_file.pl" "$KEI_S/calls.log"'
}

# --- Drop folders ------------------------------------------------------------------

@test "I19 drop folders: what waits there is offered first, Windows folders shown as Windows names" {
    biblioteca_facil_csv
    mkdir -p "$W/importar" "$W/c/KohaEasy/Importar/Dados"
    cp "$W/acervo.csv" "$W/importar/"
    export MAGIC_DROP_DIRS="$W/importar $W/c/KohaEasy/Importar"
    inputs 1 ignore CPL LIVRO
    answer no
    panel lt_magic_import
    assert 'dialogs | grep -q "^MENU \[🪄  Magic Import Tool\] => 1$" && preview | grep -q "^== acervo.csv  (CSV"' "$(dialogs)"
    panel magic_shown_path /mnt/c/KohaEasy/Importar
    assert '[ "$output" = "C:\\KohaEasy\\Importar" ]' "$output"
    # Nothing waiting: straight to the file explorer.
    rm -f "$W/importar/acervo.csv"; rmdir "$W/c/KohaEasy/Importar/Dados"
    export KEI_SELECT_FILE="$W/acervo.csv"
    rm -f "$KEI_S/dialogs.log"
    inputs ignore CPL LIVRO
    answer no
    panel lt_magic_import
    assert '! dialogs | grep -q "=> 1$" && dialogs | grep -q "Records: 3"' "$(dialogs)"
    unset MAGIC_DROP_DIRS
    panel magic_drop_dirs
    assert '[ -d /root/importar ] && echo "$output" | grep -qx /root/importar' "the drop folder is created in the panel user's home: $output"
    # Windows: C:\KohaEasy\Importar is created next to bin and logs; never a C:\KohaEasy on Linux.
    rm -rf "$W/c"; mkdir -p "$W/c/KohaEasy"
    export MAGIC_DROP_DIRS="$W/importar $W/c/KohaEasy/Importar $W/d/KohaEasy/Importar"
    panel magic_drop_dirs
    assert '[ -d "$W/c/KohaEasy/Importar" ] && echo "$output" | grep -qx "$W/c/KohaEasy/Importar" && [ ! -e "$W/d" ]' "$output"
    unset MAGIC_DROP_DIRS
}
