#!/usr/bin/env bats
# Library tools 15: the Cutter Calculator. The library's Cutter-Sanborn table
# read in the layout of the three-figure table ("  127     Abbot, J.", a
# made-up sample: the real tables are copyrighted and never enter the
# repository), cutter_calculator.pl run as a CGI with the Koha doubles of
# tests/mocks/perl5 (the items of the collection in $KS/items.tsv, the
# records in $KS/biblio), and the panel: the calculator, the table loaded
# from the menu, the page and its buttons installed and removed.

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_tools_catalog
    kei_modules_catalog
    unset KEI_SELECT_FILE KEI_DEFAULT_ANSWER KEI_EXTRA KOHA_INTRA_CGI
    W="$BATS_TEST_TMPDIR"
    PM=/usr/local/lib/site_perl
    KS=/run/kei-mock/koha
    TABLE=/etc/koha-easy-install/tables/cutter.tsv
    rm -rf "$KS" "$PM/KohaEasy/Cataloguing" /etc/koha-easy-install/tables
    mkdir -p "$KS/biblio" "$W/lib/KohaEasy/Cataloguing"
    "$KEI_SH" "$PANEL" mr_pm_rules > "$W/lib/KohaEasy/Cataloguing/Rules.pm"
}

teardown() { kei_kill_daemons; }

pre_backups() { find /var/backups/koha_sql -maxdepth 1 -name "PRE-${1:-}*" 2>/dev/null | wc -l; }
extra()       { printf '%s\n' "$@" > "$W/extra.sh"; export KEI_EXTRA="$W/extra.sh"; }
userjs()      { mysql -N -B --raw -e "SELECT value FROM systempreferences WHERE variable = 'IntranetUserJS';" "$DB"; }

# A made-up table in the layout of the three-figure table: number, spaces,
# entry; the leading spaces vary, Windows line ends, initials after a comma.
cutter_rows() {
    printf '%s\r\n' "111     Aa" "  112     Ab" "  127     Abbot, J." "  128     Abbot, M" "  131     Abbott" \
        "  847     Ass" "  848     Assi" "  849     Ast" \
        "18     Ea" "  19     Ec" "  21     Ed" \
        "111     La" "  588     Lem" "  589     Lent" "  591     Leo" \
        "1     Qa" "  2     Qe" "  3     Qu"
}

load_table() {
    mkdir -p /etc/koha-easy-install/tables
    cutter_rows > "$W/cutter.txt"
    "$KEI_SH" "$PANEL" cat_table_import cutter "$W/cutter.txt" "$TABLE" > /dev/null
}

page() {
    "$KEI_SH" "$PANEL" cutter_page_script > "$W/cutter_calculator.pl"
    printf '%s\n' $'1\t869.3 A848d\tDom Casmurro\tAssis, Machado de' $'2\t869.3 A848m ex.2\tMemórias <b>póstumas</b>\tAlves, Outro' \
        $'3\tR 869.3 A847a\tAlguma coisa\tAstro, Ana' $'4\t869.3 A8481\tOutro livro\tAssim, Rui' > "$KS/items.tsv"
    cat > "$KS/biblio/7.xml" <<'XML'
<record><datafield tag="082" ind1="0" ind2="4"><subfield code="a">869.3</subfield></datafield><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Eco, Umberto,</subfield></datafield><datafield tag="245" ind1="1" ind2="2"><subfield code="a">O nome da rosa &amp; outros /</subfield></datafield></record>
XML
}
cgi() { run env PERL5LIB="$KEI_REPO/tests/mocks/perl5:$W/lib" "$KEI_REPO/tests/lib/cgi-run" "$W/cutter_calculator.pl" GET "$@"; }
json() { cgi format=json "$@"; output=$(sed -n '/^{/,$p' <<< "$output"); }
jget() { perl -MJSON::PP -0 -e 'my $j = decode_json(<STDIN>); for my $k (split /\./, $ARGV[0]) { $j = ref $j eq "ARRAY" ? $j->[$k] : $j->{$k} } print ref $j eq "JSON::PP::Boolean" ? 0 + $j : ref $j ? "" : $j // ""' "$1" <<< "$output"; }

# --- the table and the notation -------------------------------------------------------

@test "K01 the three-figure table is read as printed: varying spaces, CRLF, initials after a comma" {
    mkdir -p /etc/koha-easy-install/tables
    cutter_rows > "$W/cutter.txt"
    panel cat_table_import cutter "$W/cutter.txt" "$TABLE"
    assert 'grep -q "^Entries: 18$" <<< "$output" && grep -q "^Lines not understood: 0$" <<< "$output" && grep -q "@@problems 0" <<< "$output"' "$output"
    assert 'grep -qP "^a\tabbot j\t127\tAbbot, J\.$" "$TABLE" && grep -qP "^a\tabbot m\t128\tAbbot, M$" "$TABLE" && grep -qP "^a\tabbott\t131\tAbbott$" "$TABLE"' "$(cat "$TABLE")"
    # The comma still separates the entry from the number when it is next to it.
    printf 'Sampaio M.,184\nRau,183\n' > "$W/pha.txt"
    panel cat_table_import pha "$W/pha.txt" "$W/pha.tsv"
    assert 'grep -qP "^s\tsampaio m\t184\tSampaio M\.$" "$W/pha.tsv" && grep -qP "^r\trau\t183\tRau$" "$W/pha.tsv"' "$(cat "$W/pha.tsv")"
    local c
    while IFS='|' read -r name title want; do
        panel cat_notation cutter "$name" "$title"
        assert '[ "$(cut -f1 <<< "$output")" = "$want" ]' "$name / $title: got $(cut -f1 <<< "$output"), want $want"
    done <<'EOF'
Assis, Machado de|Dom Casmurro|A848d
Abbot, John|The life|A127L
Abbot, Mary|Poems|A128p
Abbott, Ann|Poems|A131p
Eco, Umberto|O nome da rosa|E19n
Queiroz, Rachel de|O quinze|Q3q
Lentino, Noêmia|Classificação|L589c
EOF
}

# --- cutter_calculator.pl ------------------------------------------------------------

@test "K02 page: staff login, the notation as JSON, a name read as Surname, Forename, numbers used in the class" {
    load_table
    page
    json name="Machado de Assis" title="Dom Casmurro" class=869.3
    assert 'grep -qx "checkauth intranet catalogue=1" "$KS/calls.log"' "$(cat "$KS/calls.log")"
    assert '[ "$(jget notation)" = "A848d" ] && [ "$(jget read_as)" = "Assis, Machado de" ] && [ "$(jget entry)" = "Assi" ] && [ "$(jget call_number)" = "869.3 A848d" ]' "$output"
    assert '[ "$(jget used.0.call_number)" = "869.3 A848d" ] && [ "$(jget used.1.call_number)" = "869.3 A848m ex.2" ] && [ -z "$(jget used.2.call_number)" ]' "A8481 is another number: $output"
    assert '[ "$(jget alternatives.0.number)" = "A847" ] && [ "$(jget alternatives.0.free)" = "0" ] && [ "$(jget alternatives.1.number)" = "A849" ] && [ "$(jget alternatives.1.free)" = "1" ]' "R 869.3 A847a uses A847 in the class: $output"
    json name="Alves, Rui" title="Memórias" class=869.3 bn=2
    assert '[ "$(jget notation)" = "A131m" ] && [ -z "$(jget read_as)" ] && [ -z "$(jget alternatives)" ]' "$output"
    json name="Assis, M" title=Dom class=869.3 bn=2
    assert '[ "$(jget used.0.call_number)" = "869.3 A848d" ] && [ -z "$(jget used.1.call_number)" ]' "the record being edited is not a collision: $output"
    json name="Instituto Brasileiro" title="Anuário" mode=corporate
    assert '[ "$(jget error)" = "no_entry" ] && [ -z "$(jget notation)" ]' "no entry for the letter I in the sample: $output"
    json title="Quinze dias" mode=title
    assert '[ "$(jget notation)" = "Q3" ]' "anonymous work: first word of the title, no mark: $output"
    json name="123 Editora"
    assert '[ "$(jget error)" = "no_letter" ]' "$output"
}

@test "K03 page: the item editor reads the record, the form and the result are escaped, the field is kept" {
    load_table
    page
    json bn=7
    assert '[ "$(jget notation)" = "E19n" ] && [ "$(jget title)" = "O nome da rosa & outros" ] && [ "$(jget ind2)" = "2" ] && [ "$(jget class)" = "869.3" ]' "100, 245 with ind2 and 082 of the record: $output"
    cgi name="Assis, M" title=Dom class=869.3 target=tag_090_subfield_b_123
    assert 'grep -q "<div class=\"big\">A848d</div>" <<< "$output" && grep -q "class=\"apply\" data-n=\"A848d\" data-c=\"869.3\"" <<< "$output" && grep -q "\"target\":\"tag_090_subfield_b_123\"" <<< "$output"' "$output"
    assert 'grep -q "Memórias &lt;b&gt;póstumas&lt;/b&gt;" <<< "$output" && ! grep -q "<b>póstumas" <<< "$output"' "titles of the catalogue escaped"
    cgi "name=<script>alert(1)</script>" "title=\"><i>" "target=x\"><script>" format=part
    assert '! grep -q "<script>alert" <<< "$output" && ! grep -q "class=\"apply\"" <<< "$output"' "a bad target gives no Use button: $output"
    cgi "name=<script>alert(1)</script>" "title=\"><i>"
    assert 'grep -q "value=\"&lt;script&gt;alert(1)&lt;/script&gt;\"" <<< "$output" && grep -q "value=\"&quot;&gt;&lt;i&gt;\"" <<< "$output" && grep -q "Table of the library: 18 entries" <<< "$output"' "$output"
    rm -f "$TABLE"
    cgi name="Assis, M"
    assert 'grep -q "No author table has been loaded yet" <<< "$output"' "$output"
}

# --- panel -------------------------------------------------------------------------

@test "K04 panel: the table is loaded from the menu and the calculator shows the numbers used in the class" {
    cutter_rows > "$W/minha-tabela.txt"
    export KEI_SELECT_FILE="$W/minha-tabela.txt"
    answer yes
    panel lt_cat_load cutter
    assert '[ "$(wc -l < "$TABLE")" = "18" ] && dialogs | grep -q "^OK .*18 entries"' "no menu of tables: $(dialogs | tail -3)"
    inputs "Lentino, Noêmia" "Classificação" "025.4"
    panel lt_cutter_calc
    local r="$KEI_S/textbox.last"
    assert 'grep -q "Cutter-Sanborn: L589c" "$r" && grep -q "025.4 L589o .*Lent, Carlos" "$r"' "$(cat "$r")"
    assert 'grep -q "L588  (free to use)" "$r"' "$(cat "$r")"
    rm -f "$TABLE"
    panel lt_cutter_calc
    assert 'dialogs | grep -q "Load the Cutter-Sanborn or the PHA table of your library first"' "$(dialogs | tail -1)"
}

@test "K05 panel: the page is compiled, installed with the rules module and its buttons, updated in place and removed cleanly" {
    export KOHA_INTRA_CGI="$W/cgi"
    mkdir -p "$W/cgi/cataloguing" "$W/cgi/tools"
    answer yes
    panel lt_cutter_install
    local page="$W/cgi/cataloguing/cutter_calculator.pl"
    assert '[ "$(stat -c "%a %U" "$page")" = "755 root" ] && [ "$(stat -c "%a %U" "$PM/KohaEasy/Cataloguing/Rules.pm")" = "644 root" ]' "$(ls -l "$page" 2>&1) $(dialogs | tail -2)"
    assert 'grep -q "koha-shell library -c \"/usr/bin/perl\" \"-I\" \".*\" \"-c\" \".*cutter_calculator.pl\"" "$KEI_S/calls.log"' "compiled as the instance user first: $(calls)"
    assert 'grep -q "our %TABLES = ( cutter => '"'"'/etc/koha-easy-install/tables/cutter.tsv'"'"', pha => '"'"'/etc/koha-easy-install/tables/pha.tsv'"'"' );" "$page" && dialogs | grep -q "The page asks for a table until one is loaded"' "$(dialogs | tail -1)"
    local js; js=$(userjs)
    assert '[[ "$js" == "/* the library'"'"'s own code */"* ]] && [ "$(pre_backups CUTTER)" = "1" ]' "the library code is kept: $js"
    assert 'grep -qF "input[id^='"'"'tag_090_subfield_b'"'"']" <<< "$js" && grep -qF "input[id^='"'"'tag_952_subfield_o'"'"']" <<< "$js" && grep -q "fa fa-calculator" <<< "$js" && grep -q "nextAll(\".kei-cdd\")" <<< "$js"' "$js"
    assert 'grep -qF "input[id^='"'"'tag_090_subfield_a'"'"']" <<< "$js" && grep -q "\"kei-callno\", \"Call number\"" <<< "$js" && grep -qF "tag_080_subfield_a" <<< "$js" && grep -qF "tag_650_subfield_a" <<< "$js"' "the Call number button next to the class and the item call number: $js"
    answer yes
    panel lt_cutter_install
    js=$(userjs)
    assert '[ "$(grep -c "cutter begin" <<< "$js")" = "1" ] && grep -q "^koha-plack --restart library" "$KEI_S/calls.log" && [ "$(pre_backups CUTTER)" = "1" ]' "the same block is not written again"
    # Replace a MARC record shares the rules module: it stays while that page is installed.
    touch "$W/cgi/tools/marc_replace.pl"
    answer yes
    panel lt_cutter_remove
    js=$(userjs)
    assert '[ ! -e "$page" ] && ! grep -q "cutter begin" <<< "$js" && [ -e "$PM/KohaEasy/Cataloguing/Rules.pm" ]' "$js"
    rm -f "$W/cgi/tools/marc_replace.pl"
    answer no
    panel lt_cutter_install
    answer yes
    panel lt_cutter_remove
    assert '[ ! -e "$page" ] && [ ! -e "$PM/KohaEasy/Cataloguing/Rules.pm" ]' "$(ls -R "$PM/KohaEasy" 2>&1)"
}

@test "K06 panel: a page that does not compile is never installed; the menu is Library tools 15" {
    export KOHA_INTRA_CGI="$W/cgi"
    mkdir -p "$W/cgi/cataloguing"
    extra 'cutter_page_script() { printf "use strict;\nthis is not perl(\n"; }'
    answer yes
    panel lt_cutter_install
    assert 'dialogs | grep -q "does not compile" && [ ! -e "$W/cgi/cataloguing/cutter_calculator.pl" ] && [ "$(pre_backups)" = "0" ]' "$(dialogs | tail -2)"
    local item='"15" "$(t "🧮  Cutter Calculator")"'
    assert 'grep -qF "$item" "$KEI_REPO/installer" && grep -qF "15) function_cutter ;;" "$KEI_REPO/installer"'
}

# --- PHA and the options of the author number ---------------------------------------

# A made-up PHA table in the "Entry;number" form the panel reads.
load_pha() {
    mkdir -p /etc/koha-easy-install/tables
    printf '%s\n' "Aa;11" "Assi;861" "Ast;862" "Ea;12" "Ec;19" "Qa;4" "Qu;43" > "$W/pha.txt"
    "$KEI_SH" "$PANEL" cat_table_import pha "$W/pha.txt" /etc/koha-easy-install/tables/pha.tsv > /dev/null
}

@test "K07 page: the table is chosen (PHA when loaded), the letter of the title can be left out, edition and copy are added" {
    load_table
    page
    json name="Assis, Machado de" title="Dom Casmurro"
    assert '[ "$(jget code)" = "A848d" ] && [ "$(jget table)" = "cutter" ]' "only the Cutter table loaded: $output"
    load_pha
    json name="Assis, Machado de" title="Dom Casmurro"
    assert '[ "$(jget code)" = "A861d" ] && [ "$(jget table)" = "pha" ]' "PHA first when both are loaded: $output"
    json name="Assis, Machado de" title="Dom Casmurro" table=cutter
    assert '[ "$(jget code)" = "A848d" ]' "$output"
    json name="Assis, Machado de" title="Dom Casmurro" noletter=1 class=869.3
    assert '[ "$(jget code)" = "A861" ] && [ "$(jget call_number)" = "869.3 A861" ]' "$output"
    json name="Assis, Machado de" title="Dom Casmurro" edition=2 copy=3
    assert '[ "$(jget code)" = "A861d 2. ed. ex. 3" ] && [ "$(jget notation)" = "A861d" ]' "$output"
    json name="Assis, Machado de" title="Dom Casmurro" edition=1 copy=abc
    assert '[ "$(jget code)" = "A861d" ]' "the first edition and a copy that is not a number add nothing: $output"
    json title="O quinze" ind2=2
    assert '[ "$(jget code)" = "Q43" ] && [ "$(jget mode)" = "title" ]' "no author: the title without its article: $output"
    json name="Assis, Machado de" title="Dom Casmurro" table=other
    assert '[ "$(jget table)" = "pha" ]' "an unknown table falls back to a loaded one: $output"
    cat > "$KS/biblio/8.xml" <<'XML'
<record><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Assis, Machado de,</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Dom Casmurro /</subfield></datafield><datafield tag="250" ind1=" " ind2=" "><subfield code="a">3. ed.</subfield></datafield></record>
XML
    json bn=8
    assert '[ "$(jget code)" = "A861d 3. ed." ]' "the edition of the record (250): $output"
    cgi name="Assis, Machado de"
    assert 'grep -q "<option value=\"pha\" selected>PHA table" <<< "$output" && grep -q "<option value=\"cutter\">Cutter-Sanborn" <<< "$output" && grep -q "name=\"noletter\"" <<< "$output"' "$output"
}

# OCR-like text of a page spread of the PHA book (letters D and F): rows of
# "Entry number Entry" groups in the decimal order of the book, made up.
pha_spread() {
    python3 - "$@" <<'PY'
import sys
nums = sorted({str(n) for n in range(11, 1000) if "0" not in str(n)})[:64]
abc = "abcdefghijklmnopqrstuvwxyz"
names = [abc[i // 26] + abc[i % 26] for i in range(64)]
nums[5] = "113"          # 115 misread as 113 by the OCR
lines = []
for i in range(0, 64, 2):
    a, b = i, i + 1
    lines.append(f"| D{names[a]} {nums[a]} F{names[a]}   D{names[b]} {nums[b]} F{names[b]} :")
print("Explicação\nA tabela dá o número 12 de cada nome, e o 3 depois.\n\f" + "\n".join(lines))
PY
}

@test "K08 the PHA reader puts the rows of the book in order and corrects a misread number by that order" {
    "$KEI_SH" "$PANEL" cat_pha_rows_py > "$W/pha_rows.py"
    pha_spread > "$W/ocr.txt"
    run python3 "$W/pha_rows.py" "$W/ocr.txt" "$W/rows.tsv"
    assert '[ "$status" = 0 ] && grep -qx "rows=64" <<< "$output" && grep -qx "fixed=1" <<< "$output" && grep -qx "fix=Daf 113 -> 115" <<< "$output"' "$output"
    assert '[ "$(head -1 "$W/rows.tsv")" = "$(printf "Daa\t11\tFaa")" ] && grep -qxP "Daf\t115\tFaf" "$W/rows.tsv" && ! grep -q "Explica\|[|:]" "$W/rows.tsv"' "$(head -8 "$W/rows.tsv")"
    run python3 "$W/pha_rows.py" "$W/ocr.txt"
    assert '[ "$status" != 0 ] && grep -q usage <<< "$output"' "$output"
}

@test "K09 panel: the PHA table is loaded from the PDF of a scanned book with OCR; menu of 5 options" {
    mkdir -p "$W/bin" /etc/koha-easy-install/tables
    pha_spread > "$W/ocr.txt"
    # Doubles: a PDF without text, two pages, each page read by the OCR.
    printf '#!/bin/sh\necho "pdftotext $*" >> %s/tools.log\n: > "$5"\n' "$W" > "$W/bin/pdftotext"
    printf '#!/bin/sh\necho "Pages:          2"\n' > "$W/bin/pdfinfo"
    printf '#!/bin/sh\necho "pdftoppm $*" >> %s/tools.log\nfor a; do p="$a"; done\n: > "$p-1.png"\n' "$W" > "$W/bin/pdftoppm"
    cat > "$W/bin/tesseract" <<SH
#!/bin/sh
[ "\$1" = --list-langs ] && { echo por; exit 0; }
echo "tesseract \$*" >> $W/tools.log
n=\$(cat $W/n 2>/dev/null || echo 0); n=\$((n + 1)); echo \$n > $W/n
[ \$n = 1 ] && sed -n '1,2p' $W/ocr.txt || sed -n '3,\$p' $W/ocr.txt | tr -d '\f'
SH
    chmod 755 "$W"/bin/*
    printf '%%PDF-1.4\n%%fake\n' > "$W/PHA.pdf"
    export KEI_SELECT_FILE="$W/PHA.pdf"
    extra "PATH=\"$W/bin:\$PATH\""
    answer yes
    panel lt_cat_load pha
    local r="$KEI_S/textbox.last" pha=/etc/koha-easy-install/tables/pha.tsv
    assert 'grep -q "^pdftoppm -r 300 -gray -png -f 2 -l 2 .*PHA.pdf" "$W/tools.log" && grep -q "^tesseract .* -l por --psm 6" "$W/tools.log"' "$(cat "$W/tools.log" 2>&1) $(dialogs | tail -3)"
    assert 'grep -q "Rows read from the PDF: 64" "$r" && grep -q "check them against the book): 1" "$r" && grep -q "Daf 113 -> 115" "$r"' "$(cat "$r")"
    assert '[ "$(wc -l < "$pha")" = "128" ] && grep -qP "^d\tdaf\t115\tDaf$" "$pha" && grep -qP "^f\tfaf\t115\tFaf$" "$pha" && dialogs | grep -q "^OK .*128 entries"' "$(dialogs | tail -3)"
    # A PDF is only read for the PHA table.
    export KEI_SELECT_FILE="$W/PHA.pdf"
    panel lt_cat_load cutter
    assert 'dialogs | tail -1 | grep -q "could not be read from this PDF"' "$(dialogs | tail -1)"
    local n
    for n in 1 2 3 4 5; do assert 'grep -qF "            \"$n\" \"\$(t \"" <<< "$(sed -n "/^function_cutter()/,/^}/p" "$KEI_REPO/installer")"' "menu item $n"; done
}

# --- the class of the call number ----------------------------------------------------

# A made-up catalogue: CDD call numbers with subjects (fifth column), one
# CDU call number, and a location prefix.
catalogue() {
    printf '%s\n' $'1\t869.3 A848d\tDom Casmurro\tAssis, Machado de\tLiteratura brasileira ; Romance' \
        $'2\t869.3 A848m\tMemórias póstumas de Brás Cubas\tAssis, Machado de,\tLiteratura brasileira' \
        $'3\t981 E19h\tHistória do Brasil\tEco, Outro\tBrasil - História' \
        $'4\tR 981 Q3h\tHistória geral do Brasil\tQuaresma, Rui\tBrasil - História' \
        $'5\t869.1 L589p\tPoemas escolhidos\tLent, Ana\tPoesia brasileira' \
        $'6\t821.134.3(81)-1 Q3q\tO quinze\tQueiroz, Rachel de\tRomance brasileiro' > "$KS/items.tsv"
}

@test "K10 page: the classification is told from the settings, the class, the record or the catalogue; a class is suggested when there is none" {
    load_table
    page
    catalogue
    json name="Assis, Machado de" title="Quincas Borba"
    assert '[ "$(jget scheme)" = "cdd" ] && [ "$(jget scheme_why)" = "collection" ] && [ "$(jget scheme_count.0)" = "5" ] && [ "$(jget scheme_count.1)" = "6" ]' "$output"
    assert '[ "$(jget suggestions.0.class)" = "869.3" ] && [ "$(jget suggestions.0.why.0.kind)" = "author" ] && [ "$(jget suggestions.0.why.0.n)" = "2" ] && [ "$(jget suggested_call_number)" = "869.3 A848q" ] && [ -z "$(jget call_number | grep 869)" ]' "two titles of the same author: $output"
    json title="Nova história do Brasil" subjects="Brasil - História" mode=title
    assert '[ "$(jget suggestions.0.class)" = "981" ] && [ "$(jget suggestions.0.why.0.kind)" = "subject" ] && [ "$(jget suggestions.0.why.0.n)" = "2" ]' "the subject, R 981 read as 981: $output"
    json name="Assis, Machado de" title="Quincas Borba" c082="869.3 22"
    assert '[ "$(jget class)" = "869.3" ] && [ "$(jget class_from)" = "082" ] && [ "$(jget scheme_why)" = "record" ] && [ -z "$(jget suggestions)" ] && [ "$(jget call_number)" = "869.3 A848q" ]' "$output"
    json name="Assis, Machado de" title="Quincas Borba" class=869
    assert '[ "$(jget suggestions.0.class)" = "869.3" ] && [ -z "$(jget suggested_class)" ] && [ "$(jget call_number)" = "869 A848q" ]' "a class without its decimals gets suggestions: $output"
    json name="Assis, Machado de" title="Quincas Borba" class=LIT
    assert '[ "$(jget scheme)" = "local" ] && [ "$(jget scheme_why)" = "class" ] && [ "$(jget call_number)" = "LIT A848q" ]' "$output"
    # CDU: from 080, from the settings, and the numbers used in a CDU class.
    json name="Queiroz, Rachel de" title="Dôra, Doralina" c080="821.134.3(81)-31"
    assert '[ "$(jget scheme)" = "cdu" ] && [ "$(jget scheme_why)" = "record" ] && [ "$(jget call_number)" = "821.134.3(81)-31 Q3d" ]' "$output"
    json name="Queiroz, Rachel de" title="Dôra, Doralina" scheme=cdu
    assert '[ "$(jget scheme_why)" = "setting" ] && [ "$(jget suggestions.0.class)" = "821.134.3(81)-1" ] && [ "$(jget suggested_call_number)" = "821.134.3(81)-1 Q3d" ]' "$output"
    json name="Queiroz, Rachel de" title="Dôra, Doralina" class="821.134.3(81)-1"
    assert '[ "$(jget used.0.call_number)" = "821.134.3(81)-1 Q3q" ]' "a CDU class with brackets in the search of the numbers used: $output"
    json name="Eco, Umberto" title="Obra" scheme=cdu
    assert '[ -z "$(jget suggestions.0.class)" ] && [ -n "$(jget scheme)" ]' "no CDU call number of this author: $output"
    cgi name="Eco, Umberto" title="Obra" scheme=cdu
    assert 'grep -q "The panel has no CDU table" <<< "$output" && grep -q "No suggestion" <<< "$output"' "$output"
    # The page: the suggestions, the suggested call number, the class put into 090 \$a.
    cgi name="Assis, Machado de" title="Quincas Borba" target=tag_090_subfield_a_1
    assert 'grep -q "class=\"use\" data-class=\"869.3\"" <<< "$output" && grep -q "Suggested call number: <b>869.3 A848q</b>" <<< "$output" && grep -q "class=\"apply\" data-n=\"A848q\" data-c=\"869.3\"" <<< "$output"' "$output"
    assert 'grep -q "2 title(s) of the same author" <<< "$output" && grep -q "Classification: <b>CDD (Dewey)</b>" <<< "$output"' "$output"
    # The gear: the settings of this browser.
    assert 'grep -q "id=\"kei-gear\"" <<< "$output" && grep -q "id=\"kei-s-letter\"" <<< "$output" && grep -q "id=\"kei-s-edition\"" <<< "$output" && grep -q "id=\"kei-s-copy\"" <<< "$output" && grep -q "kei_callno_settings" <<< "$output" && grep -q "<select id=\"kei-scheme\" name=\"scheme\">" <<< "$output"' "$output"
}

@test "K11 page: the item editor reads 080, 082 and the subjects of the record; the CDD index of the library suggests classes" {
    perl -MDBD::SQLite -e 1 2>/dev/null || skip "DBD::SQLite (libdbd-sqlite3-perl) not installed"
    load_table
    page
    catalogue
    cat > "$KS/biblio/9.xml" <<'XML'
<record><datafield tag="080" ind1=" " ind2=" "><subfield code="a">82-31</subfield></datafield><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Lent, Rui,</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Versos /</subfield></datafield><datafield tag="650" ind1=" " ind2="4"><subfield code="a">Poesia brasileira.</subfield></datafield></record>
XML
    json bn=9
    assert '[ "$(jget scheme)" = "cdu" ] && [ "$(jget class)" = "82-31" ] && [ "$(jget class_from)" = "080" ] && [ "$(jget subjects)" = "Poesia brasileira" ]' "$output"
    json bn=9 scheme=cdd
    assert '[ "$(jget suggestions.0.class)" = "869.1" ] && [ "$(jget suggestions.0.why.0.kind)" = "subject" ]' "$output"
    # The CDD index (CDD lookup) built from a made-up list of subjects.
    "$KEI_SH" "$PANEL" cdd_pm > "$W/lib/KohaEasy/CDD.pm"
    printf '%s\n' "CDD-Classificação Decimal de Dewey: Tabela Resumida" "869.1 - POESIA BRASILEIRA DE TESTE" "981 - HISTORIA DE TESTE DO BRASIL" > "$W/cdd.txt"
    mkdir -p /var/lib/koha/library/kei-cdd
    perl -I "$W/lib" -MKohaEasy::CDD -e 'KohaEasy::CDD::build_cli(@ARGV)' "$W/cdd.txt" /var/lib/koha/library/kei-cdd/cdd.sqlite cdd.txt > /dev/null
    json name="Nobody, Some" title="Versos" subjects="Poesia brasileira" scheme=cdd
    assert '[ "$(jget suggestions.0.class)" = "869.1" ] && grep -q "\"kind\":\"cdd\",\"label\":\"POESIA BRASILEIRA DE TESTE\"" <<< "$output"' "$output"
    rm -rf /var/lib/koha/library/kei-cdd
}
