#!/usr/bin/env bats
# Library tools 13: the CDD lookup. KohaEasy::CDD (the reader of the CDD
# and the searches) on a small made-up sample in the layout of the text of
# a CDD PDF (the real DDC is copyrighted and never enters the repository),
# cataloguing/cdd_lookup.pl run as a CGI with the Koha doubles of
# tests/mocks/perl5 (the items of the collection in $KS/items.tsv), and the
# panel: the index built from a file, the page and its buttons installed
# and removed.

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
    CDD=/var/lib/koha/library/kei-cdd
    rm -rf "$CDD" "$PM/KohaEasy/CDD.pm" "$KS"
    mkdir -p "$KS" "$W/lib/KohaEasy"
    "$KEI_SH" "$PANEL" cdd_pm > "$W/lib/KohaEasy/CDD.pm"
    perl -MDBD::SQLite -e 1 2>/dev/null || skip "DBD::SQLite (libdbd-sqlite3-perl) not installed"
}

teardown() { kei_kill_daemons; }

pre_backups() { find /var/backups/koha_sql -maxdepth 1 -name "PRE-${1:-}*" 2>/dev/null | wc -l; }
extra()       { printf '%s\n' "$@" > "$W/extra.sh"; export KEI_EXTRA="$W/extra.sh"; }
userjs()      { mysql -N -B --raw -e "SELECT value FROM systempreferences WHERE variable = 'IntranetUserJS';" "$DB"; }
# cdd 'PERL' [args]: Perl with KohaEasy::CDD and the sample index in $W/cdd.sqlite.
cdd()         { run perl -CSA -I "$W/lib" -MKohaEasy::CDD -e "my \$dbh = KohaEasy::CDD::connect_db('$W/cdd.sqlite'); $1" "${@:2}"; }

# A made-up CDD in the layout of the text of the PDF: table of contents,
# main classes, the alphabetical list of subjects (a caption wrapped on the
# next line, one written the other way round), Tables 1 to 3 and the
# schedules with a summary, numbers from the point on, a bracketed range,
# a page number and the running head of the next page. With FULL, a
# hundred more entries of class 900 (the panel refuses fewer than 100).
cdd_sample() {
    cat <<'TXT'
1
CLASSIFICAÇÃO DE TESTE (AMOSTRA INVENTADA)
23 Edição
SUMARIO
Tabela 1. Subdivisões Padrão..................................................
CDD – Classificação de teste - Classe 600.......................................
CDD 23 – Resumo das Classes Básicas
000 Generalidades de teste
600 Técnicas de teste
800 Letras de teste
CDD-Classificação Decimal de Dewey: Tabela Resumida
641.5 - COZINHA DE TESTE
641.5981 - COZINHA BRASILEIRA DE TESTE
ALIMENTOS INVENTADOS - 641.3
869.1 - VERSOS BRASILEIROS DE TESTE E POEMAS
COMPLETOS

2
Tabela 1. Subdivisões Padrão
A notação a seguir é um exemplo inventado.
—01 Filosofia e teoria. Ver também —072.
—03 Dicionários, enciclopédias
—(016) Bibliografias (Número opcional)
—072 Pesquisa
—09 História, tratamento geográfico
—093–099 Continentes, países
Tabela 2. Áreas Geográficas e Biografia
—8 América do Sul
—81 Brasil, incluindo Amazônia.
Tabela 3. Subdivisões para Obras Literárias
—1 Versos
CDD – CLASSIFICATION DECIMAL DE DEWEY
CLASSE 600
600 Técnicas de teste. Obras gerais de teste.
640 Casa de teste
641 Comida de teste. Classificar aqui alimentação
em geral; para nutrição, ver 613.2 e T1—03.
RESUMO
641.01 Filosofia
.3 Comidas
.5 Cozinha
.3 Comidas de teste, incluindo alimentos naturais.
[.301–.309] Subdivisões padrão. Não use; classe em 641.01.
.5 Cozinha de teste. Preparação de alimentos
com e sem calor.

37
641 Comida de teste 641
.59 Cozinha regional
.593–.599 Cozinha de continentes. Adicione ao número base 641.59 notação 3–9 da Tabela 2.
642 Refeições de teste
CLASSE 800
800 Letras de teste
869 Letras de língua portuguesa
TXT
    if [ "${1:-}" = "FULL" ]; then
        printf 'CLASSE 900\n'
        for i in $(seq 900 999); do printf '%s Assunto inventado %s. Nota de teste.\n' "$i" "$i"; done
    fi
}

# The collection of the Koha doubles: biblionumber, call number, title, author.
cdd_items() {
    printf '%s\n' $'1\t641.5 C837r\tReceitas da vovó\tSilva, Ana' $'1\t641.5 C837r ex.2\tReceitas da vovó\tSilva, Ana' \
        $'2\t641.5981 M611\tCozinha mineira\tLopes, Rui' $'3\tR 869.1 B214p\tPoemas <b>escolhidos</b>\tBandeira, Manuel' > "$KS/items.tsv"
}

build_sample() {
    cdd_sample "$@" > "$W/cdd.txt"
    perl -I "$W/lib" -MKohaEasy::CDD -e 'KohaEasy::CDD::build_cli(@ARGV)' "$W/cdd.txt" "$W/cdd.sqlite" "cdd.txt"
}

# --- KohaEasy::CDD ---------------------------------------------------------------

@test "D01 reader: schedules, summary, numbers from the point on, brackets, running heads, tables and the list of subjects" {
    run build_sample
    assert '[ "$(tr "\n" " " <<< "$output")" = "entries=22 schedule=13 tables=9 terms=4 edition=23 " ]' "$output"
    cdd 'for (@ARGV) { my $x = KohaEasy::CDD::entry($dbh, $_); print join("|", $_, map { $_ // "" } @$x{qw(heading notes status parent range_end)}), "\n" }' \
        000 641 641.3 641.301-641.309 641.5 641.593-641.599 T1-016 T2-81 T1-093-099 642
    assert '[ "${lines[0]}" = "000|Generalidades de teste||||" ]' "main class from the summary of the classes: ${lines[0]}"
    assert '[ "${lines[1]}" = "641|Comida de teste|Classificar aqui alimentação em geral; para nutrição, ver 613.2 e T1—03.||640|" ]' "wrapped notes, running head ignored: ${lines[1]}"
    assert '[ "${lines[2]}" = "641.3|Comidas de teste|incluindo alimentos naturais.||641|" ]' "the entry wins over its summary line: ${lines[2]}"
    assert '[ "${lines[3]}" = "641.301-641.309|Subdivisões padrão|Não use; classe em 641.01.|bracket|641.3|641.309" ]' "${lines[3]}"
    assert '[ "${lines[4]}" = "641.5|Cozinha de teste|Preparação de alimentos com e sem calor.||641|" ]' "text after a page number: ${lines[4]}"
    assert '[ "${lines[5]}" = "641.593-641.599|Cozinha de continentes|Adicione ao número base 641.59 notação 3–9 da Tabela 2.||641.59|641.599" ]' "${lines[5]}"
    assert '[ "${lines[6]}" = "T1-016|Bibliografias (Número opcional)||option|T1-01|" ] && [ "${lines[7]}" = "T2-81|Brasil|incluindo Amazônia.||T2-8|" ]' "${lines[6]} / ${lines[7]}"
    assert '[ "${lines[8]}" = "T1-093-099|Continentes, países|||T1-09|T1-099" ] && [ "${lines[9]}" = "642|Refeições de teste|||640|" ]' "${lines[8]} / ${lines[9]}"
    cdd 'print map { "$_->{num}|$_->{term}\n" } @{ $dbh->selectall_arrayref("SELECT num, term FROM terms ORDER BY num", { Slice => {} }) }; my $m = KohaEasy::CDD::meta($dbh); print "$m->{t1}|$m->{t3}|$m->{name}\n"'
    assert '[ "$(tr "\n" "#" <<< "$output")" = "641.3|ALIMENTOS INVENTADOS#641.5|COZINHA DE TESTE#641.5981|COZINHA BRASILEIRA DE TESTE#869.1|VERSOS BRASILEIROS DE TESTE E POEMAS COMPLETOS#Subdivisões Padrão|Subdivisões para Obras Literárias|cdd.txt#" ]' "$output"
    cdd 'print map { "$_->[0]|$_->[1]\n" } @{ $dbh->selectall_arrayref("SELECT num, heading FROM entries WHERE heading LIKE ? OR heading LIKE ? OR num LIKE ?", undef, "%Classe 600%", "%CLASSIFICATION%", "T3%") }'
    assert '[ "$output" = "T3-1|Versos" ]' "table of contents and page headings left out: $output"
}

@test "D02 searches: words without accents or endings, numbers as typed, hierarchy, ranges and how a built number was made" {
    build_sample >/dev/null
    cdd 'print join(" ", map { $_->{num} } @{ KohaEasy::CDD::search($dbh, $_, 5) }), "\n" for @ARGV' "COZINHAS" "alimentacao" "versos brasileiros" "brasil" "zzz"
    assert '[ "${lines[0]}" = "641.5 641.59 641.593-641.599 641.5981" ]' "plural, upper case: ${lines[0]}"
    assert '[ "${lines[1]}" = "641" ] && [ "${lines[2]}" = "869.1" ] && [ "${lines[3]}" = "T2-81 641.5981 869.1" ] && [ "${#lines[@]}" = "4" ]' "$output"
    cdd 'print join(" ", map { KohaEasy::CDD::clean_number($_) // "-" } @ARGV), "\n"' " 641,5 " "t1-09" "T2—81" "8" "64" "641." "abc" "6415"
    assert '[ "$output" = "641.5 T1-09 T2-81 800 640 641 - -" ]' "$output"
    cdd 'print join(" ", map { $_->{num} } @{ KohaEasy::CDD::ancestors($dbh, "641.5981") }), "|", join(" ", map { $_->{num} } @{ KohaEasy::CDD::children($dbh, "641") }), "|", join(" ", map { $_->{num} } @{ KohaEasy::CDD::ranges_with($dbh, $_) }), "\n" for "641.5972", "T1-0981"'
    assert '[ "${lines[0]}" = "600 640 641 641.5 641.59|641.01 641.3 641.5|641.593-641.599" ] && [ "${lines[1]}" = "600 640 641 641.5 641.59|641.01 641.3 641.5|T1-093-099" ]' "$output"
    cdd 'print join(" + ", map { "$_->{num}($_->{add})" } @{ KohaEasy::CDD::analyse($dbh, $_) }), "\n" for @ARGV' 641.50981 641.587 869.1 642.03 603
    assert '[ "${lines[0]}" = "641.5() + T1-09(09) + T2-81(81)" ] && [ "${lines[1]}" = "641.5() + T2-8(8) + (7)" ]' "Table 1 then Table 2; a digit left: $output"
    assert '[ "${lines[2]}" = "869() + T3-1(1)" ] && [ "${lines[3]}" = "642() + T1-03(03)" ] && [ "${lines[4]}" = "600() + T1-03(03)" ]' "literature, terminal zero dropped (6 + 03): $output"
}

# --- cdd_lookup.pl ------------------------------------------------------------------

page() {
    "$KEI_SH" "$PANEL" cdd_page_script > "$W/cdd_lookup.pl"
    mkdir -p "$CDD"
    build_sample >/dev/null && cp "$W/cdd.sqlite" "$CDD/cdd.sqlite"
    cdd_items
}
cgi() { run env PERL5LIB="$KEI_REPO/tests/mocks/perl5:$W/lib" "$KEI_REPO/tests/lib/cgi-run" "$W/cdd_lookup.pl" GET "$@"; }

@test "D03 page: staff login, search with the uses in the collection, number page with hierarchy, subdivisions and titles, escaped text" {
    page
    cgi "q=cozinha" target=tag_082_subfield_a_123
    assert 'grep -qx "checkauth intranet catalogue=1" "$KS/calls.log" && grep -q "Content-Type: text/html; charset=utf-8" <<< "$output"' "$(cat "$KS/calls.log")"
    assert 'grep -q "href=\"cdd_lookup.pl?n=641.5&amp;target=tag_082_subfield_a_123\">641.5</a>" <<< "$output"' "links keep the field of the form"
    assert 'grep -q "<b>1</b> titles <span class=\"sub\">+1 in subdivisions" <<< "$output"' "641.5: 1 title, 1 more in 641.5981"
    assert 'grep -q "class=\"apply\" data-num=\"641.5\"" <<< "$output" && ! grep -q "class=\"apply\" data-num=\"641.593" <<< "$output"' "a range is never applied"
    assert 'grep -q "\"edition\":\"23\"" <<< "$output" && grep -q "\"target\":\"tag_082_subfield_a_123\"" <<< "$output"'
    cgi "n=641"
    assert 'grep -q "Comida de teste" <<< "$output" && grep -q ">640</a>" <<< "$output" && grep -q "cdd_lookup.pl?n=613.2\">613.2</a>" <<< "$output" && grep -q "n=T1-03\">T1—03</a>" <<< "$output"' "breadcrumb and numbers of the notes as links"
    assert 'grep -q "Subdivisions" <<< "$output" && ! grep -q "class=\"apply\"" <<< "$output"' "no Use button without a field to fill"
    assert 'grep -q "Not used" <<< "$(cgi n=641.3 target=t1; printf "%s" "$output")" && ! grep -q "data-num=\"641.301" <<< "$output"' "a bracketed number is shown, never used"
    assert 'grep -q "Poemas &lt;b&gt;escolhidos" <<< "$(cgi n=869.1; printf "%s" "$output")" && ! grep -q "Poemas <b>" <<< "$output"' "titles of the library escaped"
    assert 'grep -q "detail.pl?biblionumber=1\"" <<< "$(cgi n=641; printf "%s" "$output")" && grep -q "<b>0</b> titles, 0 items <span class=\"sub\">(2 titles, 3 items including subdivisions)" <<< "$output"' "641.5 and 641.5981 under 641: $output"
    cgi "n=641.50981"
    assert 'grep -q "probably a built number" <<< "$output" && grep -q "n=T1-09\">T1—09</a> (09)" <<< "$output" && grep -q "n=T2-81\">T2—81</a> (81) Brasil" <<< "$output"'
    cgi "q=<script>alert(1)</script>" "target=x\"><script>"
    assert '! grep -q "<script>alert" <<< "$output" && grep -q "&lt;script&gt;alert(1)" <<< "$output" && grep -q "\"target\":\"\"" <<< "$output"' "search and target escaped or refused"
    cgi "hint=Cozinha mineira ; Receitas" target=tag_082_subfield_a_1
    assert 'grep -q "Suggestions for the record being catalogued" <<< "$output" && grep -q "data-num=\"641.5\"" <<< "$output"' "$output"
    rm -f "$CDD/cdd.sqlite"
    cgi "q=cozinha"
    assert 'grep -q "The CDD index has not been built yet" <<< "$output"' "$output"
}

# --- panel ---------------------------------------------------------------------------

@test "D04 panel: the index is built from the library's file, readable by Koha only, and a file that is not the CDD keeps the old one" {
    cdd_sample FULL > "$W/minha-cdd.txt"
    export KEI_SELECT_FILE="$W/minha-cdd.txt"
    answer no
    panel lt_cdd_build
    assert '[ -s "$CDD/cdd.sqlite" ] && [ "$(stat -c "%a %U" "$CDD/cdd.sqlite")" = "640 root" ] && [ "$(stat -c %a "$CDD")" = "750" ]' "$(ls -la "$CDD" 2>&1) $(dialogs | tail -3)"
    assert 'dialogs | grep -q "CDD index built: 113 entries of the schedules, 9 of the tables and 4 subjects of the alphabetical list (edition 23)"' "$(dialogs | tail -3)"
    assert 'grep -qx "name=minha-cdd.txt" "$CDD/cdd.info" && dialogs | grep -q "PROMPT \[CDD lookup\] Install the CDD lookup page"' "$(cat "$CDD/cdd.info")"
    assert 'grep -q "koha-shell library -c \"/usr/bin/perl\" \"-I\" \".*\" \".*cdd_build.pl\" \".*cdd.txt\"" "$KEI_S/calls.log"' "built with Koha's Perl, as the instance user: $(calls)"
    local sum; sum=$(md5sum < "$CDD/cdd.sqlite")
    printf 'Uma lista qualquer\n100 - UM ASSUNTO\n' > "$W/outro.txt"
    export KEI_SELECT_FILE="$W/outro.txt"
    panel lt_cdd_build
    assert 'dialogs | grep -q "Only 0 entries of the schedules were found: this file does not look like the CDD. The previous index was kept." && [ "$(md5sum < "$CDD/cdd.sqlite")" = "$sum" ]' "$(dialogs | tail -2)"
    assert '[ -z "$(ls /tmp/koha_tools.* 2>/dev/null)" ]' "the text of the CDD is not left in the work folder"
}

@test "D05 panel: the page is compiled, installed with its module and buttons, updated in place and removed cleanly" {
    export KOHA_INTRA_CGI="$W/cgi"
    mkdir -p "$W/cgi/cataloguing"
    local js_before; js_before=$(userjs | md5sum)
    answer yes
    panel lt_cdd_install
    local page="$W/cgi/cataloguing/cdd_lookup.pl"
    assert '[ "$(stat -c "%a %U" "$page")" = "755 root" ] && [ "$(stat -c "%a %U" "$PM/KohaEasy/CDD.pm")" = "644 root" ]' "$(ls -l "$page" 2>&1) $(dialogs | tail -2)"
    assert 'grep -q "koha-shell library -c \"/usr/bin/perl\" \"-I\" \".*\" \"-c\" \".*cdd_lookup.pl\"" "$KEI_S/calls.log"' "compiled as the instance user first: $(calls)"
    assert 'grep -q "our \$INDEX = '"'"'/var/lib/koha/library/kei-cdd/cdd.sqlite'"'"'" "$page" && dialogs | grep -q "The page asks for the index until it is built"' "$(dialogs | tail -1)"
    local js; js=$(userjs)
    assert '[[ "$js" == "/* the library'"'"'s own code */"* ]] && [ "$(pre_backups CDD)" = "1" ]' "the library code is kept: $js"
    assert 'grep -qF "input[id^='"'"'tag_082_subfield_a'"'"']" <<< "$js" && grep -qF "cataloguing\/(addbiblio|additem)\.pl" <<< "$js" && grep -q "fa fa-sitemap" <<< "$js" && grep -q "CDD lookup" <<< "$js"' "$js"
    answer yes
    panel lt_cdd_install
    js=$(userjs)
    assert '[ "$(grep -c "cdd begin" <<< "$js")" = "1" ] && grep -q "^koha-plack --restart library" "$KEI_S/calls.log" && [ "$(pre_backups CDD)" = "1" ]' "the same block is not written again"
    # The block of Replace a MARC record lives next to it, untouched.
    mysql -e "UPDATE systempreferences SET value = CONCAT(value, '\n/* koha-easy-installer marc_replace begin */\nmr();\n/* koha-easy-installer marc_replace end */') WHERE variable = 'IntranetUserJS';" "$DB"
    answer yes
    panel lt_cdd_remove
    js=$(userjs)
    assert '[ ! -e "$page" ] && [ ! -e "$PM/KohaEasy/CDD.pm" ] && ! grep -q "cdd begin" <<< "$js" && grep -q "^mr();$" <<< "$js"' "$js"
}

@test "D06 panel: a page that does not compile is never installed; a PDF is read with pdftotext" {
    export KOHA_INTRA_CGI="$W/cgi"
    mkdir -p "$W/cgi/cataloguing"
    extra 'cdd_page_script() { printf "use strict;\nthis is not perl(\n"; }'
    answer no
    panel lt_cdd_install
    assert 'dialogs | grep -q "does not compile" && [ ! -e "$W/cgi/cataloguing/cdd_lookup.pl" ] && [ "$(pre_backups)" = "0" ]' "$(dialogs | tail -2)"
    # pdftotext double: the text of the sample.
    mkdir -p "$W/bin"
    cdd_sample FULL > "$W/texto.txt"
    printf '#!/bin/sh\necho "pdftotext $*" >> %s/pdftotext.log\ncp %s "$4"\n' "$W" "$W/texto.txt" > "$W/bin/pdftotext"
    chmod 755 "$W/bin/pdftotext"
    printf '%%PDF-1.4\n%%fake\n' > "$W/CDD 23.pdf"
    export KEI_SELECT_FILE="$W/CDD 23.pdf"
    extra "PATH=\"$W/bin:\$PATH\""
    answer no
    panel lt_cdd_build
    assert 'grep -q "^pdftotext -enc UTF-8 .*CDD 23.pdf" "$W/pdftotext.log" && grep -qx "name=CDD 23.pdf" "$CDD/cdd.info"' "$(dialogs | tail -2)"
}
