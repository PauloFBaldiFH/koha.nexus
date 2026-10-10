#!/usr/bin/env bats
# Find duplicate authors (Library tools > 18): the kei_import engine groups
# the variant forms of one person's name in the authority file
# (tests/data/authorities_sample.xml, made up for the tests), the operator
# confirms each group, and the merge goes through Koha's own
# C4::AuthoritiesMarc (the test double of tests/mocks/perl5 on a real
# MariaDB) after a verified PRE-AUTHORITIES backup.

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    unset KEI_EXTRA
    W="$BATS_TEST_TMPDIR"
    SAMPLE="$KEI_REPO/tests/data/authorities_sample.xml"
    auth_catalog
}

teardown() {
    kei_kill_daemons
}

# The sample authorities in auth_header; records 1-3 use authorities 2, 3
# and 6 (MARCXML with its namespace, as Koha keeps it), and one item 952 $9
# that is not an authority.
auth_catalog() {
    python3 - "$SAMPLE" > "$W/auth.sql" <<'PY'
import sys
from xml.etree import ElementTree as ET
NS = "{http://www.loc.gov/MARC21/slim}"
ET.register_namespace("", NS[1:-1])
print("CREATE TABLE auth_header (authid bigint(20) unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY, authtypecode varchar(10) NOT NULL DEFAULT '', marcxml longtext NOT NULL) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;")
for rec in ET.parse(sys.argv[1]).getroot().iter(NS + "record"):
    xml = ET.tostring(rec, encoding="unicode").replace("'", "''")
    authid = rec.find(NS + "controlfield").text
    print("INSERT INTO auth_header VALUES (%s, 'PERSO_NAME', '%s');" % (authid, xml))
PY
    tools_sql "$(cat "$W/auth.sql")"
    tools_sql "UPDATE biblio_metadata SET metadata = CONCAT('<record xmlns=\"http://www.loc.gov/MARC21/slim\"><datafield tag=\"100\" ind1=\"1\" ind2=\" \"><subfield code=\"a\">x</subfield><subfield code=\"9\">',
                 ELT(biblionumber, 2, 3, 6), '</subfield></datafield><datafield tag=\"952\" ind1=\" \" ind2=\" \"><subfield code=\"9\">2</subfield></datafield></record>')
               WHERE biblionumber <= 3;"
}
authids()  { tools_sql "SELECT GROUP_CONCAT(authid ORDER BY authid) FROM auth_header;"; }
linked()   { tools_sql "SELECT ExtractValue(metadata, '//datafield[@tag<900]/subfield[@code=\"9\"]') FROM biblio_metadata WHERE biblionumber = $1;"; }
pre_auth() { find /var/backups/koha_sql -maxdepth 1 -name 'PRE-AUTHORITIES*' 2>/dev/null | wc -l; }
engine() {   # the engine alone, written out of the installer
    panel kei_import_write "$W/kei"
    mkdir -p "$W/work"
    run python3 -I -B "$W/kei/kei_import_run.py" authorities --in "$1" --work "$W/work" "${@:2}"
}

@test "M01 engine on the sample: inverted, abbreviated, typo, accents and sound-alike forms grouped; different people kept apart" {
    engine "$SAMPLE"
    assert '[ "$status" -eq 0 ]' "$output"
    g="$W/work/authority-groups.tsv"
    grp() { awk -F'\t' -v id="$1" '$2 == id { print $1 }' "$g"; }
    # Machado de Assis: the dated form is kept, the 1950- namesake stays out.
    assert '[ "$(awk -F"\t" "\$3 == \"keep\" && \$2 == 1" "$g" | wc -l)" = 1 ]' "$(cat "$g")"
    assert '[ "$(grp 2)" = "$(grp 1)" ] && [ "$(grp 3)" = "$(grp 1)" ] && [ "$(grp 4)" = "$(grp 1)" ]' "$(cat "$g")"
    assert '[ -z "$(grp 30)" ]' "$(cat "$g")"
    assert 'grep -q "also like: Assis, Machado de, 1950-" "$g"' "$(cat "$g")"
    # Drummond filed under either surname, initials, the fuller form (100 $q).
    assert '[ "$(grp 6)" = "$(grp 5)" ] && [ "$(grp 7)" = "$(grp 5)" ]' "$(cat "$g")"
    assert '[ "$(grp 20)" = "$(grp 19)" ] && [ "$(grp 21)" = "$(grp 19)" ]' "$(cat "$g")"
    # Accents and case, Queiroz / Queirós, Luiz / Luís, Sousa / Souza.
    assert '[ "$(grp 25)" = "$(grp 24)" ] && [ "$(grp 10)" = "$(grp 11)" ] && [ "$(grp 9)" = "$(grp 8)" ]' "$(cat "$g")"
    assert '[ "$(grp 23)" = "$(grp 22)" ] && [ "$(grp 27)" = "$(grp 26)" ]' "$(cat "$g")"
    # Never together: José / João, Filho / Neto, Maria / Mário, Lobato, Costa.
    assert '[ "$(grp 12)" != "$(grp 13)" ] || [ -z "$(grp 12)" ]' "$(cat "$g")"
    assert '[ -z "$(grp 15)$(grp 16)$(grp 17)$(grp 18)$(grp 28)$(grp 29)" ]' "$(cat "$g")"
    # Every score at or above the threshold, every variant with its reasons.
    assert '! awk -F"\t" "\$3 == \"variant\" && (\$4 < 0.85 || \$5 == \"-\")" "$g" | grep -q .' "$(cat "$g")"
    assert '[[ "$output" == *"Groups of variant forms: 9"* ]]' "$output"
}

@test "M02 engine: a stricter threshold finds fewer groups; nothing alike exits 3; a broken file exits 4" {
    engine "$SAMPLE" --threshold 0.96
    assert '[ "$status" -eq 0 ]' "$output"
    assert '! grep -q "Assis, M. de" "$W/work/authority-groups.tsv"' "$(cat "$W/work/authority-groups.tsv")"
    printf '1\tPERSO_NAME\tAssis, Machado de\t\t\n2\tPERSO_NAME\tLispector, Clarice\t\t\n' > "$W/two.tsv"
    engine "$W/two.tsv"
    assert '[ "$status" -eq 3 ]' "$output"
    printf '<collection><record>' > "$W/broken.xml"
    engine "$W/broken.xml"
    assert '[ "$status" -eq 4 ]' "$output"
}

@test "M03 confirmed groups merged by Koha after the PRE-AUTHORITIES backup; skipped groups untouched; variant kept as 400" {
    # Group 1 (Assis): the suggested form; group 2 (Drummond): not the same
    # person; the rest: the suggested form for all.
    inputs "1" "skip" "all"
    answer yes
    panel lt_authority_match
    assert '[ "$status" -eq 0 ]' "$output"
    assert '[ "$(pre_auth)" = 1 ]' "$(dialogs)"
    assert 'grep -q "^merge 2 1 override_limit \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^DelAuthority 3 skip_merge" "$KEI_S/calls.log"' "$(calls)"
    assert '! grep -Eq "^merge (6|7) " "$KEI_S/calls.log"' "$(calls)"
    assert '! grep -Eq "^merge 30 " "$KEI_S/calls.log"' "$(calls)"
    ids=",$(authids),"
    for gone in 2 3 4 10 20 21 25; do assert '[[ "$ids" != *",$gone,"* ]]' "$ids"; done
    for kept in 1 5 6 7 11 12 13 19 30; do assert '[[ "$ids" == *",$kept,"* ]]' "$ids"; done
    # The records that used 2 and 3 now use 1; Drummond's (6) and the item's 952 are untouched.
    assert '[ "$(linked 1)" = "1" ] && [ "$(linked 2)" = "1" ] && [ "$(linked 3)" = "6" ]' "$(linked 1) $(linked 2) $(linked 3)"
    # The variants are "see from" references (400) of the form kept.
    x=$(tools_sql "SELECT marcxml FROM auth_header WHERE authid = 1;")
    assert '[[ "$x" == *"<datafield tag=\"400\" ind1=\"0\" ind2=\" \">"*"Machado de Assis"* ]]' "$x"
    assert '[[ "$x" == *"Assis, M. de"* && "$x" == *"Asis, Machado de"* ]]' "$x"
    assert 'dialogs | grep -q "Authorities merged: 11"' "$(dialogs)"
}

@test "M04 another form chosen to stay: the others merge into it" {
    inputs "2" "CANCEL"
    panel lt_authority_match
    # Cancelled at the second group: nothing at all is merged.
    assert '[ "$(pre_auth)" = 0 ] && ! grep -q "^merge" "$KEI_S/calls.log"' "$(calls)"
    rm -f "$KEI_S/calls.log"
    inputs "2" "skip" "skip" "skip" "skip" "skip" "skip" "skip" "skip"
    answer yes
    panel lt_authority_match
    assert 'grep -q "^merge 1 2 " "$KEI_S/calls.log" && grep -q "^merge 4 2 " "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(grep -c "^merge" "$KEI_S/calls.log")" = 3 ]' "$(calls)"
    assert '[ "$(linked 1)" = "2" ]' "$(linked 1)"
}

@test "M05 declined after the review, or no authorities at all: nothing changed, no backup" {
    before=$(authids)
    answer no
    panel lt_authority_match
    assert '[ "$(pre_auth)" = 0 ] && [ "$(authids)" = "$before" ]' "$(dialogs)"
    assert '! grep -q "^merge" "$KEI_S/calls.log" 2>/dev/null'
    tools_sql "DELETE FROM auth_header;"
    panel lt_authority_match
    assert 'dialogs | grep -q "no authority records yet"' "$(dialogs)"
}

@test "M06 one merge failing does not stop the others, and is reported" {
    touch "$KEI_S/fail/merge-3"
    inputs "all"
    answer yes
    panel lt_authority_match
    assert 'grep -q "^merge 3 1 " "$KEI_S/calls.log" && grep -q "^merge 4 1 " "$KEI_S/calls.log"' "$(calls)"
    assert '[[ ",$(authids)," == *",3,"* ]]' "$(authids)"
    assert 'dialogs | grep -q "Not merged (see the log): 1"' "$(dialogs)"
    assert 'grep -q "Authority 3 not merged into 1: simulated failure" /var/log/koha-easy-install/tools/authority-match-*.log'
}
