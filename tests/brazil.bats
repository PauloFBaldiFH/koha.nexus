#!/usr/bin/env bats
# Brazil: localization (Library tools > 9). Real yaz-marcdump,
# MARC::Record, xsltproc, MariaDB and Memcached; the Koha scripts are the
# test doubles of tests/mocks/koha-script and koha-mysql / koha-preferences
# of tests/mocks/koha-mock.

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_tools_catalog
    kei_br_catalog
    unset KEI_SELECT_FILE KEI_DEFAULT_ANSWER KEI_EXTRA
    W="$BATS_TEST_TMPDIR"
    rm -f /etc/koha-easy-install/ficha.state
}

teardown() {
    [ -n "${HOLD:-}" ] && kill "$HOLD" 2>/dev/null
    kei_kill_daemons
}

pre_backups() { find /var/backups/koha_sql -maxdepth 1 -name "PRE-${1:-}*" 2>/dev/null | wc -l; }
extra()       { printf '%s\n' "$@" > "$W/extra.sh"; export KEI_EXTRA="$W/extra.sh"; }
marc_dump()   { yaz-marcdump "$1" 2>/dev/null; }

# --- 3. CPF and calendar (pure functions) ----------------------------------

@test "BR01 CPF modulo-11 validator: official check digits, formatting, identical digits" {
    local v
    for v in 529.982.247-25 52998224725 111.444.777-35 123.456.789-09 000.000.001-91 390.533.447-05; do
        panel cpf_valid "$v"
        assert '[ "$status" -eq 0 ]' "$v must be valid"
    done
    for v in 000.000.000-00 111.111.111-11 222.222.222-22 999.999.999-99 \
             529.982.247-24 529.982.247-15 123.456.789-00 \
             5299822472 529982247250 12345678 a29.982.247-25 "529 982 247 25" ""; do
        panel cpf_valid "$v"
        assert '[ "$status" -ne 0 ]' "'$v' must be refused"
    done
}

@test "BR02 movable holidays from Easter (Meeus/Jones/Butcher): Carnival, Good Friday, Corpus Christi" {
    local y
    for y in "2000 2000-04-23" "2008 2008-03-23" "2011 2011-04-24" "2019 2019-04-21" "2024 2024-03-31" "2025 2025-04-20" "2026 2026-04-05" "2038 2038-04-25"; do
        panel br_easter "${y% *}"
        assert '[ "$output" = "${y#* }" ]' "Easter ${y% *}: got $output"
    done
    panel br_holidays 2025
    assert 'echo "$output" | grep -qx "2025-03-03|Carnaval (segunda-feira)|P"' "$output"
    assert 'echo "$output" | grep -qx "2025-03-04|Carnaval (terça-feira)|P"'
    assert 'echo "$output" | grep -qx "2025-04-18|Sexta-feira Santa|N"'
    assert 'echo "$output" | grep -qx "2025-06-19|Corpus Christi|P"'
    assert '[ "$(echo "$output" | grep -c "|N$")" = "10" ] && [ "$(echo "$output" | wc -l)" = "13" ]' "10 national + 3 optional in 2025"
    assert '[ "$(echo "$output" | cut -d"|" -f1)" = "$(echo "$output" | cut -d"|" -f1 | sort)" ]' "sorted by date"
    panel br_holidays 2024
    assert 'echo "$output" | grep -q "^2024-02-13|Carnaval (terça-feira)" && echo "$output" | grep -q "^2024-03-29|Sexta-feira Santa" && echo "$output" | grep -q "^2024-05-30|Corpus Christi"' "$output"
    panel br_holidays 2023
    assert '! echo "$output" | grep -q "Consciência Negra"' "national only from 2024 (Lei 14.759/2023)"
}

# --- 1. Readers of the old systems (their imports: tests/magic_import.bats) --------

@test "BR05 the item reader moves SophiA, Pergamum and custom item fields to 952, with the values the engine checked" {
    cat > "$W/vendors.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record><leader>00000nam  2200000 a 4500</leader>
  <datafield tag="245" ind1="0" ind2="0"><subfield code="a">Vidas secas</subfield></datafield>
  <datafield tag="852" ind1=" " ind2=" "><subfield code="h">869.3</subfield><subfield code="i">R194v</subfield><subfield code="p">P-001</subfield><subfield code="t">2</subfield></datafield>
  <datafield tag="990" ind1=" " ind2=" "><subfield code="a">S-001</subfield><subfield code="b">B869.3 R194</subfield></datafield>
  <datafield tag="949" ind1=" " ind2=" "><subfield code="c">C-001</subfield><subfield code="d">869.3</subfield><subfield code="e">R194v</subfield></datafield>
</record>
</collection>
XML
    kei_marc "$W/v.mrc" UTF-8 "$W/vendors.xml"
    local p
    "$KEI_SH" "$PANEL" br_write_remapper "$W/r.pl"
    # The layouts the Magic Import Tool recognises (Pergamum, SophiA) and a custom map.
    for p in "852 p=p,o=h+i,t=t,z=z,x=x|\$o 869.3 R194v \$p P-001 \$t 2" "990 p=a,o=b|\$o B869.3 R194 \$p S-001" "949 p=c,o=d+e|\$o 869.3 R194v \$p C-001"; do
        local spec="${p%%|*}"
        run perl "$W/r.pl" --in "$W/v.mrc" --out "$W/o.mrc" --item-tag "${spec%% *}" --map "${spec#* }" --callnumber "090:ab|082:a" --branch MPL --itype REV
        assert '[ "$status" -eq 0 ]' "$spec: $output"
        run yaz-marcdump "$W/o.mrc"
        assert 'echo "$output" | grep -qF "952    \$a MPL \$b MPL \$y REV ${p#*|}"' "$spec: $output"
    done
    # Values the engine checked (--values): library and item type become
    # Koha's codes, unknown ones the defaults; status, date and price as Koha
    # takes them; "h+k|j" takes $j when $h and $k are empty.
    cat > "$W/items.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record><leader>00000nam  2200000 a 4500</leader>
  <datafield tag="245" ind1="0" ind2="0"><subfield code="a">Um</subfield></datafield>
  <datafield tag="949" ind1=" " ind2=" "><subfield code="b">CPL</subfield><subfield code="t">Livro</subfield><subfield code="s">Extraviado</subfield><subfield code="d">15/03/2020</subfield><subfield code="p">R$ 25,00</subfield><subfield code="i">I-1</subfield><subfield code="j">ARM 1</subfield></datafield>
  <datafield tag="949" ind1=" " ind2=" "><subfield code="b">XPL</subfield><subfield code="t">Gibi</subfield><subfield code="s">Disponível</subfield><subfield code="i">I-2</subfield><subfield code="h">869.3</subfield><subfield code="k">R194v</subfield></datafield>
</record>
</collection>
XML
    kei_marc "$W/i.mrc" UTF-8 "$W/items.xml"
    printf 'a\tCPL\tCPL\na\tXPL\t\ny\tLivro\tLIVRO\ny\tGibi\t\nS\tExtraviado\t1\nS\tDisponível\t-\nd\t15/03/2020\t2020-03-15\ng\tR$ 25,00\t25.00\n' > "$W/v.tsv"
    run perl "$W/r.pl" --in "$W/i.mrc" --out "$W/o.mrc" --item-tag 949 --map "a=b,y=t,S=s,d=d,g=p,p=i,o=h+k|j" --callnumber "090:ab|082:a" \
        --branch MPL --itype REV --values "$W/v.tsv"
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'echo "$output" | grep -qx "Items with their library from the field: 1" && echo "$output" | grep -qx "Libraries Koha does not have (your choice used): 1"' "$output"
    assert 'echo "$output" | grep -qx "Item types Koha does not have (your choice used): 1" && echo "$output" | grep -qx "Values left out (location, date, price or status Koha cannot take): 0"' "$output"
    run yaz-marcdump "$W/o.mrc"
    assert 'echo "$output" | grep -qxF "952    \$a CPL \$b CPL \$y LIVRO \$1 1 \$d 2020-03-15 \$g 25.00 \$o ARM 1 \$p I-1"' "$output"
    assert 'echo "$output" | grep -qxF "952    \$a MPL \$b MPL \$y REV \$o 869.3 R194v \$p I-2"' "$output"
}

@test "BR09 CPF report is read-only: invalid, shared and non-CPF values" {
    inputs "sort1"
    panel lt_br_cpf_audit
    local r="$KEI_S/textbox.last"
    assert 'grep -q "Invalid CPF: 123.456.789-00" "$r" && grep -q "Invalid CPF: 5299822472" "$r"' "$(cat "$r")"
    assert 'grep -q "CPF shared by two patrons: 52998224725" "$r"'
    assert 'grep -q "Checked: 4   valid: 2   invalid: 2   shared: 1   other values (not a CPF): 1" "$r"' "$(cat "$r")"
    assert '[ "$(pre_backups)" = "0" ] && ! grep -q "koha-mysql" "$KEI_S/calls.log" 2>/dev/null' "read-only"
}

# --- 2. Printing and cataloguing --------------------------------------------------

@test "BR10 Pimaco templates: chosen sheets and layouts through koha-mysql, idempotent, removable" {
    inputs "1" "6180 6287"
    answer yes
    panel lt_br_labels
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'grep -q "^koha-mysql library" "$KEI_S/calls.log"' "SQL runs with Koha's account: $(calls)"
    assert '[ "$(pre_backups LABELS)" = "1" ]'
    assert '[ "$(tools_sql "SELECT CONCAT_WS(\"|\", label_width, label_height, cols, \`rows\`, units, page_width) FROM creator_templates WHERE template_code = \"KEI-PIMACO-6180\";")" = "66.68|25.4|3|10|MM|215.9" ]' "$(tools_sql "SELECT * FROM creator_templates")"
    assert '[ "$(tools_sql "SELECT CONCAT_WS(\"|\", label_width, label_height, cols, \`rows\`) FROM creator_templates WHERE template_code = \"KEI-PIMACO-6287\";")" = "44.45|12.7|4|20" ]'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM creator_templates WHERE template_code LIKE \"KEI-PIMACO-%\";")" = "2" ]' "only the chosen sheets"
    assert '[ "$(tools_sql "SELECT GROUP_CONCAT(layout_name ORDER BY layout_name) FROM creator_layouts WHERE layout_name LIKE \"KEI %\";")" = "KEI Codigo de barras,KEI Lombada,KEI Titulo e codigo" ]'
    inputs "1" "6180 6287 A4256"
    answer yes
    panel lt_br_labels
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM creator_templates WHERE template_code LIKE \"KEI-PIMACO-%\";")" = "3" ] && [ "$(tools_sql "SELECT COUNT(*) FROM creator_layouts WHERE layout_name LIKE \"KEI %\";")" = "3" ]' "no duplicates on a second run"
    inputs "2"; answer yes
    panel lt_br_labels
    assert '[ "$(tools_sql "SELECT GROUP_CONCAT(template_code) FROM creator_templates;")" = "MINHA" ] && [ "$(tools_sql "SELECT GROUP_CONCAT(layout_name) FROM creator_layouts;")" = "Meu layout" ]' "only the panel's templates are removed"
}

@test "BR11 label templates are refused while a backup holds the lock, and need the safety backup" {
    flock -o /var/lock/koha_backup.lock sleep 30 3>&- &
    HOLD=$!; sleep 0.5
    inputs "1" "6180"
    panel lt_br_labels
    kill "$HOLD"; HOLD=""; sleep 0.3
    assert 'dialogs | grep -q "already running" && ! grep -q "koha-mysql" "$KEI_S/calls.log" 2>/dev/null'
    rm -rf /var/backups/koha_sql; mkdir -p /var/backups; : > /var/backups/koha_sql
    inputs "1" "6180"; answer yes
    panel lt_br_labels
    rm -f /var/backups/koha_sql
    assert 'dialogs | grep -q "Safety backup failed" && ! grep -q "koha-mysql" "$KEI_S/calls.log"'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM creator_templates;")" = "1" ]'
}

# Stub default detail stylesheets (Koha's real ones are checked with
# xsltproc when the card changes; see tests/README.md).
ficha_env() {
    local d
    for d in opac/en opac/pt-BR intra/en; do mkdir -p "$W/tmpl/$d/xslt"; done
    for d in opac/en opac/pt-BR; do
        printf '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:marc="http://www.loc.gov/MARC21/slim"><xsl:output method="html"/><xsl:template match="/"><xsl:apply-templates/></xsl:template><xsl:template match="marc:record"><div id="default-%s">DEFAULT VIEW</div></xsl:template></xsl:stylesheet>\n' "${d##*/}" > "$W/tmpl/$d/xslt/MARC21slim2OPACDetail.xsl"
    done
    cp "$W/tmpl/opac/en/xslt/MARC21slim2OPACDetail.xsl" "$W/tmpl/intra/en/xslt/MARC21slim2intranetDetail.xsl"
    extra "KOHA_OPAC_TMPL='$W/tmpl/opac'" "KOHA_INTRA_TMPL='$W/tmpl/intra'" "FICHA_DIR='$W/ficha'"
}

@test "BR12 catalogue card: stylesheets per language, preferences set through koha-preferences, then restored" {
    ficha_env
    inputs "on"; answer yes
    panel lt_br_ficha
    assert '[ "$status" -eq 0 ]' "$output"
    assert '[ -f "$W/ficha/en/opac-detail.xsl" ] && [ -f "$W/ficha/pt-BR/opac-detail.xsl" ] && [ -f "$W/ficha/pt-BR/staff-detail.xsl" ]' "$(ls -R "$W/ficha" 2>&1)"
    assert 'grep -q "href=\"$W/tmpl/opac/pt-BR/xslt/MARC21slim2OPACDetail.xsl\"" "$W/ficha/pt-BR/opac-detail.xsl"' "the OPAC card imports the view of its own language"
    assert 'grep -q "href=\"$W/tmpl/intra/en/xslt/MARC21slim2intranetDetail.xsl\"" "$W/ficha/pt-BR/staff-detail.xsl"' "a language missing on one side falls back to English"
    assert 'grep -q "^koha-preferences set OPACXSLTDetailsDisplay $W/ficha/{langcode}/opac-detail.xsl" "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(tools_sql "SELECT value FROM systempreferences WHERE variable = \"XSLTDetailsDisplay\";")" = "$W/ficha/{langcode}/staff-detail.xsl" ]'
    assert 'grep -qx "OPACXSLTDetailsDisplay=default" /etc/koha-easy-install/ficha.state && grep -qx "XSLTDetailsDisplay=default" /etc/koha-easy-install/ficha.state'
    assert '[ "$(pre_backups FICHA)" = "1" ]'
    # The card itself (AACR2 layout) below the default view.
    biblio_xml='<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader>
      <datafield tag="020" ind1=" " ind2=" "><subfield code="a">8508040350</subfield></datafield>
      <datafield tag="082" ind1="0" ind2="4"><subfield code="a">869.3</subfield></datafield>
      <datafield tag="090" ind1=" " ind2=" "><subfield code="a">869.3</subfield><subfield code="b">A848d</subfield></datafield>
      <datafield tag="100" ind1="1" ind2=" "><subfield code="a">Assis, Machado de,</subfield><subfield code="d">1839-1908</subfield></datafield>
      <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Dom Casmurro /</subfield><subfield code="c">Machado de Assis.</subfield></datafield>
      <datafield tag="250" ind1=" " ind2=" "><subfield code="a">3. ed.</subfield></datafield>
      <datafield tag="260" ind1=" " ind2=" "><subfield code="a">São Paulo :</subfield><subfield code="b">Ática,</subfield><subfield code="c">1997.</subfield></datafield>
      <datafield tag="300" ind1=" " ind2=" "><subfield code="a">208 p. ;</subfield><subfield code="c">21 cm.</subfield></datafield>
      <datafield tag="490" ind1="0" ind2=" "><subfield code="a">Bom livro ;</subfield><subfield code="v">12</subfield></datafield>
      <datafield tag="650" ind1=" " ind2="4"><subfield code="a">Romance brasileiro</subfield><subfield code="y">Século XIX.</subfield></datafield>
      <datafield tag="700" ind1="1" ind2=" "><subfield code="a">Silva, João,</subfield><subfield code="e">org.</subfield></datafield>
    </record>'
    printf '%s\n' "$biblio_xml" > "$W/rec.xml"
    run xsltproc "$W/ficha/pt-BR/opac-detail.xsl" "$W/rec.xml"
    assert '[ "$status" -eq 0 ] && echo "$output" | grep -q "default-pt-BR"' "Koha's view comes first: $output"
    local card
    card=$(echo "$output" | sed -n '/class="kei-ficha"/,/kei-ficha-print/p' | sed 's/<[^>]*>/\n/g; s/^ *//' | grep -v '^$')
    assert 'echo "$card" | grep -qx "869.3" && echo "$card" | grep -qx "A848d"' "call number column: $card"
    assert 'echo "$card" | grep -qx "Assis, Machado de, 1839-1908."' "$card"
    assert 'echo "$card" | grep -qx "Dom Casmurro / Machado de Assis. – 3. ed. – São Paulo : Ática, 1997."' "$card"
    assert 'echo "$card" | grep -qx "208 p. ; 21 cm. – (Bom livro ; 12)"' "$card"
    assert 'echo "$card" | grep -qx "ISBN 8508040350"'
    assert 'echo "$card" | grep -qx "1. Romance brasileiro – Século XIX. I. Silva, João. II. Título."' "$card"
    assert 'echo "$card" | grep -qx "CDD 869.3"'
    assert 'echo "$output" | grep -q "class=\"kei-entrada\"" && echo "$output" | grep -q "text-indent: -2.2em"' "hanging indentation"
    assert 'echo "$output" | grep -q "<details class=\"kei-ficha-box\" id=\"kei-ficha\">" && echo "$output" | grep -q "<summary class=\"kei-ficha-show\">Show the AACR2 catalogue card</summary>" && ! echo "$output" | grep -q "<details[^>]* open"' "the card starts collapsed behind its button"
    # The ABNT reference under the card (the organizer with $e is not a co-author).
    local ref
    ref=$(echo "$output" | sed -n '/id="kei-abnt"/,/<\/p>/p' | sed 's/.*id="kei-abnt"/<div id="kei-abnt"/' | tr '\n' ' ' | sed 's/<h3[^>]*>[^<]*<\/h3>//; s/<[^>]*>//g; s/  */ /g; s/^ //; s/ $//')
    assert '[ "$ref" = "ASSIS, Machado de. Dom Casmurro. 3. ed. São Paulo: Ática, 1997." ]' "ABNT reference: $ref"
    assert 'echo "$output" | grep -q "<strong>Dom Casmurro</strong>"' "the title is in bold"
    printf '%s\n' '<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><controlfield tag="008">090101s2009    bl            000 0 por d</controlfield>
      <datafield tag="245" ind1="0" ind2="2"><subfield code="a">O pequeno príncipe /</subfield></datafield></record>' > "$W/rec2.xml"
    run xsltproc "$W/ficha/pt-BR/opac-detail.xsl" "$W/rec2.xml"
    ref=$(echo "$output" | sed -n '/id="kei-abnt"/,/<\/p>/p' | sed 's/.*id="kei-abnt"/<div id="kei-abnt"/' | tr '\n' ' ' | sed 's/<h3[^>]*>[^<]*<\/h3>//; s/<[^>]*>//g; s/  */ /g; s/^ //; s/ $//')
    assert '[ "$ref" = "O PEQUENO príncipe. [S. l.: s. n.], 2009." ]' "entry by title, date of the 008: $ref"
    # Off: the previous values come back.
    inputs "off"; answer yes
    panel lt_br_ficha
    assert '[ "$(tools_sql "SELECT value FROM systempreferences WHERE variable = \"OPACXSLTDetailsDisplay\";")" = "default" ]'
    assert '[ ! -e /etc/koha-easy-install/ficha.state ]'
}

@test "BR13 catalogue card refresh: new languages get a stylesheet, nothing when the card is off" {
    ficha_env
    panel ficha_refresh
    assert '[ ! -e "$W/ficha" ]' "ficha_refresh must not do anything while the card is off"
    printf 'OPACXSLTDetailsDisplay=default\nXSLTDetailsDisplay=default\n' > /etc/koha-easy-install/ficha.state
    mkdir -p "$W/tmpl/opac/es-ES/xslt" && cp "$W/tmpl/opac/en/xslt/MARC21slim2OPACDetail.xsl" "$W/tmpl/opac/es-ES/xslt/"
    panel ficha_refresh
    rm -f /etc/koha-easy-install/ficha.state
    assert '[ -f "$W/ficha/es-ES/opac-detail.xsl" ] && [ -f "$W/ficha/es-ES/staff-detail.xsl" ]' "$(ls -R "$W/ficha" 2>&1)"
}

# --- 4. Government census reports -----------------------------------------------

# Koha columns used by the census reports, and a year (2025) with known
# figures: 3 volumes added, 1 lost, 1 withdrawn, 1 damaged, 1 deleted,
# 2 loans, 1 renewal, 1 in-library use, 2 active readers.
census_data() {
    tools_sql "
ALTER TABLE items ADD COLUMN itype varchar(10), ADD COLUMN notforloan tinyint(1) NOT NULL DEFAULT 0, ADD COLUMN withdrawn tinyint(1) NOT NULL DEFAULT 0,
  ADD COLUMN withdrawn_on datetime, ADD COLUMN damaged tinyint(1) NOT NULL DEFAULT 0, ADD COLUMN damaged_on datetime,
  ADD COLUMN replacementprice decimal(8,2), ADD COLUMN datelastborrowed date;
ALTER TABLE biblio ADD COLUMN copyrightdate smallint(6);
ALTER TABLE borrowers ADD COLUMN sex varchar(1);
ALTER TABLE statistics ADD COLUMN itemtype varchar(10);
CREATE TABLE biblioitems (biblioitemnumber int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, biblionumber int(11) NOT NULL, itemtype varchar(10));
CREATE TABLE deleteditems (itemnumber int(11) NOT NULL PRIMARY KEY, biblionumber int(11) NOT NULL, itype varchar(10), replacementprice decimal(8,2),
  withdrawn tinyint(1) NOT NULL DEFAULT 0, timestamp timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp());
CREATE TABLE virtualshelves (shelfnumber int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, shelfname varchar(255)) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE virtualshelfcontents (shelfnumber int(11) NOT NULL, biblionumber int(11) NOT NULL);
INSERT INTO biblioitems (biblionumber, itemtype) SELECT biblionumber, 'LIVRO' FROM biblio;
UPDATE items SET itype = 'REV' WHERE itemnumber IN (10, 11);
UPDATE biblio SET copyrightdate = IF(biblionumber <= 50, 2023, IF(biblionumber <= 100, 2010, NULL));
UPDATE items SET itemcallnumber = '869.3 A1' WHERE itemnumber BETWEEN 20 AND 29;
UPDATE items SET dateaccessioned = '2025-03-10' WHERE itemnumber IN (20, 21, 22);
UPDATE items SET itemlost_on = '2025-02-02', replacementprice = 30 WHERE itemnumber = 1;
UPDATE items SET withdrawn = 1, withdrawn_on = '2025-05-01' WHERE itemnumber = 30;
UPDATE items SET damaged = 1, damaged_on = '2025-06-01', replacementprice = 45.5 WHERE itemnumber = 31;
INSERT INTO deleteditems (itemnumber, biblionumber, itype, replacementprice, timestamp) VALUES (9001, 1, 'LIVRO', 10, '2025-08-01'), (9002, 1, 'LIVRO', 10, '2024-08-01');
UPDATE borrowers SET sex = 'F' WHERE cardnumber = 'S1';
UPDATE borrowers SET sex = 'M' WHERE cardnumber = 'S2';
INSERT INTO statistics (datetime, branch, type, itemnumber, borrowernumber, itemtype)
  SELECT '2025-03-15 10:00', 'CPL', 'issue', 20, borrowernumber, 'LIVRO' FROM borrowers WHERE cardnumber = 'S1' UNION ALL
  SELECT '2025-03-20 10:00', 'CPL', 'renew', 20, borrowernumber, 'LIVRO' FROM borrowers WHERE cardnumber = 'S1' UNION ALL
  SELECT '2025-04-02 10:00', 'CPL', 'issue', 10, borrowernumber, 'REV' FROM borrowers WHERE cardnumber = 'S2' UNION ALL
  SELECT '2025-04-05 10:00', 'CPL', 'return', 10, borrowernumber, 'REV' FROM borrowers WHERE cardnumber = 'S2' UNION ALL
  SELECT '2025-04-06 10:00', 'CPL', 'localuse', 11, NULL, 'REV' UNION ALL
  SELECT '2024-12-31 23:00', 'CPL', 'issue', 21, borrowernumber, 'LIVRO' FROM borrowers WHERE cardnumber = 'S3';"
}
# census_run KEY: the saved report run for 2025, as Koha would after asking for the year.
census_run() {
    local q
    q=$(tools_sql "SELECT savedsql FROM saved_sql WHERE notes LIKE '%[koha-easy-installer-censo:censo-$1]%';")
    [ -n "$q" ] || return 1
    tools_sql "$(sed -E "s/<<[^<>]*>>/'2025'/g" <<< "$q")"
}

@test "BR17 census reports: tagged read-only reports with the year asked by Koha, figures of the year, own pack" {
    census_data
    inputs "1"; answer yes
    panel lt_br_census
    assert '[ "$status" -eq 0 ]' "$output"
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '"'"'%[koha-easy-installer-censo:%'"'"';")" = "10" ]' "10 reports expected: $(cat "$KEI_S/textbox.last")"
    assert '[ "$(pre_backups CENSO)" = "1" ]'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '"'"'%[koha-easy-installer-censo:%'"'"' AND savedsql NOT LIKE '"'"'SELECT %'"'"';")" = "0" ]' "only SELECT statements"
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE savedsql LIKE '"'"'%<<Census year (YYYY)>>%'"'"';")" = "6" ]' "reports of a year ask for it (once per query)"
    local key
    for key in summary collection-type collection-area acquisitions circulation loans-type readers losses age weeding; do
        assert 'census_run "$key" >/dev/null' "report $key does not run"
    done
    assert '[ "$(census_run summary)" = "$(printf "2025\t198\t198\t3\t1\t1\t1\t5\t0\t2\t2\t1\t1")" ]' "summary of 2025: $(census_run summary)"
    assert 'census_run collection-area | grep -qx "800 Literature	10	10"' "$(census_run collection-area)"
    assert 'census_run collection-area | grep -qx "000 Computer science, information and general works	188	188"'
    assert 'census_run collection-type | grep -qx "Revista	CPL	2	2	2	0"' "$(census_run collection-type)"
    assert 'census_run acquisitions | grep -qx "Livro	800 Literature	3	3"' "$(census_run acquisitions)"
    assert 'census_run circulation | grep -qx "2025-03	1	1	0	0	1"' "$(census_run circulation)"
    assert 'census_run circulation | grep -qx "2025-04	1	0	1	1	1"'
    assert 'census_run loans-type | grep -qx "Revista	Student	1	0	0"' "$(census_run loans-type)"
    assert 'census_run loans-type | grep -qx "Revista	Not informed	0	0	1"' "anonymous in-library use"
    assert 'census_run readers | grep -qx "Student	Female	18-29	1	1"' "$(census_run readers)"
    assert 'census_run readers | grep -qx "Student	Not informed	00-11	1	0"' "S3 (born 2016) read nothing in 2025"
    assert 'census_run losses | grep -qx "Damaged	Livro	1	45.50"' "$(census_run losses)"
    assert 'census_run losses | grep -qx "Deleted from the catalog (discarded)	Livro	1	10.00"'
    assert '[ "$(census_run losses | wc -l)" = "4" ]' "lost, withdrawn, damaged, deleted"
    assert 'census_run age | grep -qx "800 Literature	10	10	0	0	0	0.0"' "$(census_run age)"
    assert '[ "$(census_run weeding | wc -l)" = "50" ]' "records 51-100 (2010, never borrowed): $(census_run weeding | wc -l)"
    # The essential pack and the census pack are removed separately.
    inputs "1"; answer yes
    panel lt_reports
    local essential
    essential=$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '%[koha-easy-installer:%';")
    inputs "2"; answer yes
    panel lt_br_census
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '"'"'%[koha-easy-installer-censo:%'"'"';")" = "0" ]'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '"'"'%[koha-easy-installer:%'"'"';")" = "$essential" ] && [ "$essential" -gt 0 ]' "the essential pack stays"
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE report_name = '"'"'My own report'"'"';")" = "1" ]'
}

@test "BR18 census reports declined after the preview, or on a Koha without the columns: nothing saved" {
    inputs "1"; answer no
    panel lt_br_census
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql;")" = "1" ] && [ "$(pre_backups)" = "0" ]'
    assert 'grep -q "not compatible with this Koha version" "$KEI_S/textbox.last"' "without biblioitems/withdrawn the dry run skips the reports: $(cat "$KEI_S/textbox.last")"
}

@test "BR22 census reports in every panel language: the translated labels keep the SQL valid and acceptable to Koha" {
    census_data
    local l q n
    for l in pt es fr de it nl ru pl uk cs sv tr ar ja zh hi bn id tl fa vi ko; do
        extra "SYS_LANG=$l" "load_panel_translations" 'census_dump() { census_reports_define; printf "%s\n" "${RP_SQL[@]}"; }'
        panel census_dump
        assert '[ "$status" -eq 0 ] && [ "$(printf "%s\n" "$output" | grep -c "^SELECT ")" = "10" ]' "$l: $output"
        [ "$l" = "pt" ] && assert 'grep -q "<<Ano do censo (AAAA)>>" <<< "$output" && grep -q "AS \`Leitores ativos no ano\`" <<< "$output"' "pt-BR labels: $output"
        n=0
        while IFS= read -r q; do
            [[ "$q" == SELECT* ]] || continue
            n=$((n + 1))
            # C4::Reports::Guided refuses these words anywhere in a saved report.
            assert '! grep -qiE "(^|[^[:alnum:]_])(UPDATE|DELETE|DROP|INSERT|SHOW|CREATE)([^[:alnum:]_]|$)" <<< "$q"' "$l: report $n has a word Koha refuses"
            assert 'tools_sql "$(sed -E "s/<<[^<>]*>>/'"'"'2025'"'"'/g" <<< "$q")" >/dev/null' "$l: report $n does not run: $q"
        done <<< "$output"
    done
}

# --- 5. ABNT references -----------------------------------------------------------

abnt_records() {
    cat > "$W/abnt.tsv" <<'EOF_TSV'
1	869.3 A848d	2	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><controlfield tag="008">970101s1997    bl            000 0 por d</controlfield><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Assis, Machado de,</subfield><subfield code="d">1839-1908.</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Dom Casmurro /</subfield><subfield code="c">Machado de Assis.</subfield></datafield><datafield tag="250" ind1=" " ind2=" "><subfield code="a">2nd ed. rev.</subfield></datafield><datafield tag="260" ind1=" " ind2=" "><subfield code="a">São Paulo :</subfield><subfield code="b">Ática,</subfield><subfield code="c">1997.</subfield></datafield><datafield tag="300" ind1=" " ind2=" "><subfield code="a">xii, 208 p. :</subfield><subfield code="b">il.</subfield></datafield><datafield tag="490" ind1="0" ind2=" "><subfield code="a">Bom livro ;</subfield><subfield code="v">12</subfield></datafield><datafield tag="856" ind1="4" ind2="2"><subfield code="u">http://capa.example/x.jpg</subfield></datafield></record>
2		0	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><datafield tag="245" ind1="0" ind2="2"><subfield code="a">O pequeno príncipe /</subfield><subfield code="c">tradução de Dom Marcos Barbosa.</subfield></datafield><datafield tag="260" ind1=" " ind2=" "><subfield code="a">Rio de Janeiro :</subfield><subfield code="b">Agir Editora Ltda.,</subfield><subfield code="c">c2009.</subfield></datafield><datafield tag="700" ind1="1" ind2=" "><subfield code="a">Barbosa, Marcos,</subfield><subfield code="e">tradutor.</subfield></datafield></record>
3	370 E24	1	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><datafield tag="245" ind1="0" ind2="0"><subfield code="a">Educação e sociedade :</subfield><subfield code="b">ensaios /</subfield><subfield code="c">organização de Ana Souza.</subfield></datafield><datafield tag="260" ind1=" " ind2=" "><subfield code="a">[S.l.] :</subfield><subfield code="b">[s.n.],</subfield></datafield><datafield tag="700" ind1="1" ind2=" "><subfield code="a">Souza, Ana,</subfield><subfield code="e">org.</subfield></datafield></record>
4	610 M532	1	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Lima, João</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Medicina :</subfield><subfield code="b">manual /</subfield></datafield><datafield tag="264" ind1=" " ind2="1"><subfield code="a">Curitiba :</subfield><subfield code="b">UFPR,</subfield><subfield code="c">2020.</subfield></datafield><datafield tag="700" ind1="1" ind2=" "><subfield code="a">Costa, Maria.</subfield></datafield><datafield tag="700" ind1="1" ind2=" "><subfield code="a">Pereira, Rui.</subfield></datafield><datafield tag="700" ind1="1" ind2=" "><subfield code="a">Alves, Eva.</subfield></datafield></record>
5		0	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><datafield tag="110" ind1="1" ind2=" "><subfield code="a">Brasil.</subfield><subfield code="b">Ministério da Educação.</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Base nacional comum curricular.</subfield></datafield><datafield tag="264" ind1=" " ind2="1"><subfield code="a">Brasília, DF :</subfield><subfield code="b">MEC,</subfield><subfield code="c">2018.</subfield></datafield><datafield tag="856" ind1="4" ind2="0"><subfield code="u">http://basenacionalcomum.mec.gov.br/</subfield></datafield></record>
6		0	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Oliveira, Paula.</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Leitura na escola /</subfield></datafield><datafield tag="300" ind1=" " ind2=" "><subfield code="a">150 p.</subfield></datafield><datafield tag="502" ind1=" " ind2=" "><subfield code="b">Dissertação (Mestrado em Educação)</subfield><subfield code="c">Universidade Federal do Paraná</subfield><subfield code="d">2015.</subfield></datafield></record>
7		0	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000naa a2200000 a 4500</leader><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Santos, Luís.</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Bibliotecas escolares no Brasil.</subfield></datafield><datafield tag="773" ind1="0" ind2=" "><subfield code="t">Revista Brasileira de Biblioteconomia</subfield><subfield code="g">v. 10, n. 2 (2019), p. 33-50</subfield></datafield></record>
8		0	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000naa a2200000 a 4500</leader><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Rocha, Ivo.</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">A leitura.</subfield></datafield><datafield tag="773" ind1="0" ind2=" "><subfield code="a">Souza, Ana (org.)</subfield><subfield code="t">Educação e sociedade</subfield><subfield code="d">São Paulo : Cortez, 2012</subfield><subfield code="g">p. 10-25</subfield></datafield></record>
9		0	not a record
10		0	<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><datafield tag="110" ind1="2" ind2=" "><subfield code="a">Universidade Federal do Paraná.</subfield><subfield code="b">Sistema de Bibliotecas.</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Normas para apresentação de documentos científicos</subfield><subfield code="n">2</subfield><subfield code="p">Teses.</subfield></datafield><datafield tag="250" ind1=" " ind2=" "><subfield code="a">1ª edição</subfield></datafield><datafield tag="260" ind1=" " ind2=" "><subfield code="a">Curitiba :</subfield><subfield code="b">Ed. UFPR,</subfield><subfield code="c">[2007?]</subfield></datafield></record>
EOF_TSV
}

@test "BR19 ABNT NBR 6023 formatter: books, entries by title and organizer, et al., corporate, thesis, article, chapter, online" {
    abnt_records
    panel abnt_write_formatter "$W/abnt.pl"
    run perl "$W/abnt.pl" --in "$W/abnt.tsv" --html "$W/out.html" --text "$W/out.txt" --caption "Teste" --access "5 mar. 2026"
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'echo "$output" | grep -qx "References: 9" && echo "$output" | grep -qx "Records not read: 1" && echo "$output" | grep -qx "Without date: 1"' "$output"
    cat > "$W/expected.txt" <<'EOF_REFS'
Teste

REFERÊNCIAS

ASSIS, Machado de. Dom Casmurro. 2. ed. rev. São Paulo: Ática, 1997. 208 p. (Bom livro, 12).

BRASIL. Ministério da Educação. Base nacional comum curricular. Brasília, DF: MEC, 2018. Disponível em: http://basenacionalcomum.mec.gov.br/. Acesso em: 5 mar. 2026.

LIMA, João et al. Medicina: manual. Curitiba: UFPR, 2020.

O PEQUENO príncipe. Tradução: Marcos Barbosa. Rio de Janeiro: Agir Editora, 2009.

OLIVEIRA, Paula. Leitura na escola. 2015. 150 f. Dissertação (Mestrado em Educação) – Universidade Federal do Paraná, 2015.

ROCHA, Ivo. A leitura. In: SOUZA, Ana (org.). Educação e sociedade. São Paulo: Cortez, 2012. p. 10-25.

SANTOS, Luís. Bibliotecas escolares no Brasil. Revista Brasileira de Biblioteconomia, v. 10, n. 2, p. 33-50, 2019.

SOUZA, Ana (org.). Educação e sociedade: ensaios. [S. l.: s. n.], [s. d.].

UNIVERSIDADE FEDERAL DO PARANÁ. Sistema de Bibliotecas. Normas para apresentação de documentos científicos 2 Teses. Curitiba: Ed. UFPR, [2007?].

EOF_REFS
    assert 'diff "$W/expected.txt" "$W/out.txt"' "$(diff "$W/expected.txt" "$W/out.txt")"
    assert 'grep -q "<p class=\"ref\">ASSIS, Machado de. <strong>Dom Casmurro</strong>. 2. ed. rev." "$W/out.html"' "bold title"
    assert 'grep -q "In: SOUZA, Ana (org.). <strong>Educação e sociedade</strong>. São Paulo" "$W/out.html"' "bold host of the chapter"
    assert 'grep -q "<strong>Revista Brasileira de Biblioteconomia</strong>, v. 10" "$W/out.html"' "bold journal"
    assert 'grep -q "<p class=\"ref\">O PEQUENO príncipe. Tradução" "$W/out.html"' "no bold with an entry by title"
    assert 'grep -q "@page { size: A4; margin: 3cm 2cm 2cm 3cm; }" "$W/out.html" && grep -q "<h1>Referências</h1>" "$W/out.html"' "NBR 14724 presentation"
    # Collection listing: call numbers and copies, duplicates kept.
    run perl "$W/abnt.pl" --in "$W/abnt.tsv" --html "$W/out.html" --text "$W/out.txt" --listing
    assert 'grep -qx "    Localização: 869.3 A848d (2 ex.)." "$W/out.txt" && grep -qx "    Sem exemplares no acervo." "$W/out.txt"' "$(cat "$W/out.txt")"
}

abnt_catalog() {
    census_data
    abnt_records
    local bn xml line
    while IFS= read -r line; do
        bn=${line%%$'\t'*}; xml=$(cut -f4- <<< "$line")
        [ "$bn" -le 2 ] || continue
        tools_sql "INSERT INTO biblio (biblionumber, title, datecreated) VALUES ($((300 + bn)), 'abnt $bn', '2025-01-01');
            INSERT INTO biblio_metadata (biblionumber, format, \`schema\`, metadata) VALUES ($((300 + bn)), 'marcxml', 'MARC21', '${xml//\'/\'\'}');"
    done < "$W/abnt.tsv"
    tools_sql "INSERT INTO items (biblionumber, barcode, homebranch, itemcallnumber, dateaccessioned) VALUES
        (301, 'AB1', 'CPL', '869.3 A848d', '2025-02-01'), (301, 'AB2', 'MPL', '869.3 A848d', '2025-02-01'), (302, 'AB3', 'CPL', '843 S129p', '2019-01-01');
        INSERT INTO virtualshelves (shelfname) VALUES ('Bibliografia básica de Letras d''Água');
        INSERT INTO virtualshelfcontents VALUES (1, 301), (1, 302);"
    mkdir -p "$W/out"
    export KEI_SELECT_DIR="$W/out"
}

@test "BR20 ABNT references from the catalog: typed records, a Koha list as a collection listing, files in the chosen folder" {
    abnt_catalog
    inputs "numbers" "301, 302;9999"; answer no
    panel lt_br_abnt
    assert '[ "$status" -eq 0 ]' "$output"
    local txt html
    txt=$(ls "$W"/out/referencias-abnt-*.txt 2>/dev/null); html=$(ls "$W"/out/referencias-abnt-*.html 2>/dev/null)
    assert '[ -f "$txt" ] && [ -f "$html" ]' "$(ls -l "$W/out") $(dialogs | tail -n 5)"
    assert 'grep -qx "ASSIS, Machado de. Dom Casmurro. 2. ed. rev. São Paulo: Ática, 1997. 208 p. (Bom livro, 12)." "$txt"' "$(cat "$txt")"
    assert 'grep -qx "O PEQUENO príncipe. Tradução: Marcos Barbosa. Rio de Janeiro: Agir Editora, 2009." "$txt"'
    assert '! grep -q "Localização" "$txt"' "a plain bibliography"
    assert 'grep -q "ASSIS, Machado de" "$KEI_S/textbox.last"' "preview of the references"
    assert 'dialogs | grep -q "OK .*References: 2"' "$(dialogs | tail -n 3)"
    assert '[ -z "$(ls /tmp/koha_tools.* 2>/dev/null | grep abnt)" ]' "work files removed"
    rm -f "$W"/out/*
    inputs "list" "1"; answer yes
    panel lt_br_abnt
    txt=$(ls "$W"/out/referencias-abnt-*.txt 2>/dev/null)
    assert 'head -n 1 "$txt" | grep -qx "Bibliografia básica de Letras d’Água"' "the list name is the caption (koha-shell cannot pass a quote): $(cat "$txt")"
    assert 'grep -qx "    Localização: 869.3 A848d (2 ex.)." "$txt" && grep -qx "    Localização: 843 S129p (1 ex.)." "$txt"' "$(cat "$txt")"
    rm -f "$W"/out/*
    inputs "new" "2025-01-01" "2025-12-31"; answer no
    panel lt_br_abnt
    txt=$(ls "$W"/out/referencias-abnt-*.txt 2>/dev/null)
    assert 'grep -q "^ASSIS" "$txt" && ! grep -q "PEQUENO" "$txt"' "only items added in 2025: $(cat "$txt")"
    assert 'head -n 1 "$txt" | grep -qx "New acquisitions from 2025-01-01 to 2025-12-31"'
}

@test "BR21 ABNT references: bad input and empty selections write nothing" {
    abnt_catalog
    inputs "numbers" "301; DROP TABLE biblio"
    panel lt_br_abnt
    assert 'dialogs | grep -q "ERROR.*Use only record numbers"' "$(dialogs | tail -n 3)"
    inputs "class" "8'%"
    panel lt_br_abnt
    assert 'dialogs | grep -q "ERROR.*Use only digits"'
    inputs "new" "2025-13-01" "2025-12-31"
    panel lt_br_abnt
    assert 'dialogs | grep -q "ERROR.*Invalid date"'
    inputs "class" "7"
    panel lt_br_abnt
    assert 'dialogs | grep -q "INFO .*No record found"' "$(dialogs | tail -n 3)"
    assert '[ -z "$(ls "$W/out")" ] && [ "$(tools_sql "SELECT COUNT(*) FROM biblio WHERE biblionumber = 301;")" = "1" ]' "$(ls "$W/out")"
}

# --- 3. Calendar ----------------------------------------------------------------

# Probes Memcached in a subshell (fd 3 belongs to bats).
memcached_set() { ( exec 5<>/dev/tcp/127.0.0.1/11211; printf 'set kei_probe 0 0 1\r\nx\r\n' >&5; read -r -t 2 _ <&5 ); }
memcached_has() { ( exec 5<>/dev/tcp/127.0.0.1/11211; printf 'get kei_probe\r\n' >&5; read -r -t 2 r <&5; [[ "$r" == VALUE* ]] ); }

@test "BR14 holidays: national, movable and local days for every library, no duplicates" {
    memcached_set
    assert 'memcached_has'
    inputs "add" "2025" "*" "20/01 São Sebastião"
    answer yes
    panel lt_br_holidays
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'grep -q "^koha-mysql library" "$KEI_S/calls.log" && [ "$(pre_backups CALENDAR)" = "1" ]' "$(calls)"
    local q="SELECT COUNT(*) FROM special_holidays WHERE year = 2025 AND isexception = 0"
    assert '[ "$(tools_sql "$q AND branchcode = \"MPL\";")" = "14" ]' "13 national/optional days + 1 local"
    assert '[ "$(tools_sql "$q AND branchcode = \"CPL\";")" = "14" ]' "CPL already had Natal: $(tools_sql "SELECT day, month, title FROM special_holidays WHERE branchcode = 'CPL'")"
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM special_holidays WHERE branchcode = \"CPL\" AND day = 25 AND month = 12;")" = "1" ]' "a day already in the calendar is not added twice"
    assert '[ "$(tools_sql "SELECT title FROM special_holidays WHERE branchcode = \"MPL\" AND day = 4 AND month = 3;")" = "Carnaval (terça-feira)" ]'
    assert '[ "$(tools_sql "SELECT title FROM special_holidays WHERE branchcode = \"MPL\" AND day = 19 AND month = 6;")" = "Corpus Christi" ]'
    assert '[ "$(tools_sql "SELECT title FROM special_holidays WHERE branchcode = \"MPL\" AND day = 20 AND month = 1;")" = "São Sebastião" ]'
    assert '! memcached_has' "Koha's cached calendar must be dropped"
    inputs "add" "2025" "*" ""
    answer yes
    panel lt_br_holidays
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM special_holidays;")" = "28" ]' "a second run adds nothing"
    inputs "remove" "2025" "MPL"
    answer yes
    panel lt_br_holidays
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM special_holidays WHERE branchcode = \"MPL\";")" = "0" ] && [ "$(tools_sql "SELECT COUNT(*) FROM special_holidays WHERE branchcode = \"CPL\";")" = "14" ]'
    inputs "remove" "2025" "CPL"; answer yes
    panel lt_br_holidays
    assert '[ "$(tools_sql "SELECT title FROM special_holidays;")" = "Natal" ]' "days added by hand stay"
}

@test "BR15 holidays: bad input is refused, and Koha's newer calendar table is used when present" {
    inputs "add" "25"
    panel lt_br_holidays
    inputs "add" "2025" "CPL" "32/13 Nada"
    panel lt_br_holidays
    assert '[ "$(dialogs | grep -c "^ERROR")" = "2" ] && ! grep -q "koha-mysql" "$KEI_S/calls.log" 2>/dev/null' "$(dialogs)"
    tools_sql "DROP TABLE special_holidays; CREATE TABLE library_single_closures (library_single_closure_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, library_id varchar(10) NOT NULL, date date NOT NULL, title varchar(50) NOT NULL DEFAULT '', description mediumtext NOT NULL, UNIQUE KEY library_id_date (library_id, date));"
    inputs "add" "2026" "CPL" ""; answer yes
    panel lt_br_holidays
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM library_single_closures WHERE library_id = \"CPL\";")" = "13" ]' "$output"
    assert '[ "$(tools_sql "SELECT title FROM library_single_closures WHERE date = \"2026-02-17\";")" = "Carnaval (terça-feira)" ]'
}

@test "BR16 opt-in only: the installation and the panel start never apply a Brazilian preset" {
    local body
    body=$(sed -n '/^function_install_koha() {/,/^}/p' "$KEI_REPO/installer")
    assert '[ -n "$body" ] && ! echo "$body" | grep -qE "lt_br_|br_|ficha_|cpf_|function_brazil"' "the installation must not call the Brazil tools"
    assert '! sed -n "/^(return 0 2>\/dev\/null) \&\& return 0/,\$p" "$KEI_REPO/installer" | grep -qE "lt_br_|br_holidays|br_patrons|_lt_br"' "the startup only refreshes an already enabled card"
    assert 'grep -qE "^ +9\) function_brazil_tools ;;" "$KEI_REPO/installer"' "reachable only from Library tools > 9"
}
