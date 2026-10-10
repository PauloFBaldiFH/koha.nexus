#!/usr/bin/env bats
# Library tools: undo of a MARC import, SQL reports pack, school-year
# turnover, data-quality check, LGPD housekeeping (the imports themselves:
# tests/magic_import.bats). The Koha
# scripts are test doubles (tests/mocks/koha-script) acting on a real
# MariaDB; the panel's own steps (lock, dry run, confirmation, PRE-* backup,
# koha-shell quoting) run for real.

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_tools_catalog
    unset KEI_SELECT_FILE KEI_DEFAULT_ANSWER
    W="$BATS_TEST_TMPDIR"
}

teardown() {
    [ -n "${HOLD:-}" ] && kill "$HOLD" 2>/dev/null
    kei_kill_daemons
}

pre_backups() { find /var/backups/koha_sql -maxdepth 1 -name "PRE-${1:-}*" 2>/dev/null | wc -l; }
# ISO 2709 file with N minimal records (leader position 09 = "a": Unicode).
marc_file()   { local i; for ((i = 0; i < $2; i++)); do printf '00026nam a2200025 a 4500\036\035'; done > "$1"; }
bibs()        { tools_sql "SELECT COUNT(*) FROM biblio;"; }

# --- MARC undo (batches staged by the Magic Import Tool, tests/magic_import.bats) ---

@test "L04 MARC undo: counts first, PRE-UNDO-IMPORT backup, then commit_file.pl --revert" {
    marc_file "$W/books.mrc" 4
    export KEI_SELECT_FILE="$W/books.mrc"
    inputs "new"; answer yes yes
    panel lt_magic_import
    assert '[ "$(bibs)" = "204" ]'
    : > "$KEI_S/calls.log"
    inputs "1"; answer yes
    panel lt_marc_undo
    assert 'dialogs | grep -q "PROMPT \[Undo a MARC import\] Batch 1: 4 record(s) and 4 item(s)"' "$(dialogs)"
    assert 'grep -q "^commit_file.pl --revert --batch-number 1 \[pre=2\]" "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(pre_backups UNDO-IMPORT)" = "1" ]'
    assert '[ "$(bibs)" = "200" ]'
    assert '[ "$(tools_sql "SELECT import_status FROM import_batches WHERE import_batch_id = 1;")" = "reverted" ]'
}

@test "L05 write tools are refused while a backup or restore holds the lock" {
    marc_file "$W/books.mrc" 2
    export KEI_SELECT_FILE="$W/books.mrc"
    flock -o /var/lock/koha_backup.lock sleep 30 3>&- &
    HOLD=$!; sleep 0.5
    panel lt_magic_import
    inputs "1"
    panel lt_reports
    inputs "ST" "FM" "all" "*"
    panel lt_patron_category
    assert '! grep -qE "stage_file|update_patrons" "$KEI_S/calls.log" 2>/dev/null' "$(calls)"
    assert '[ "$(dialogs | grep -c "already running")" = "3" ]' "$(dialogs)"
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql;")" = "1" ]'
}

@test "L06 no write happens when the safety backup cannot be made" {
    marc_file "$W/books.mrc" 2
    export KEI_SELECT_FILE="$W/books.mrc"
    rm -rf /var/backups/koha_sql; mkdir -p /var/backups; : > /var/backups/koha_sql   # a file where the folder should be
    inputs "keep"; answer yes yes
    panel lt_magic_import
    rm -f /var/backups/koha_sql
    assert 'grep -q "^stage_file.pl" "$KEI_S/calls.log"' "the preview still runs"
    assert '! grep -q "^commit_file.pl" "$KEI_S/calls.log"' "nothing may be imported without the backup"
    assert 'dialogs | grep -q "Safety backup failed"'
    assert '[ "$(bibs)" = "200" ]'
}

@test "L07 koha_tool passes every argument intact through koha-shell and refuses single quotes" {
    printf '#!/bin/bash\nprintf "<%%s>\\n" "$@"\n' > /usr/share/koha/bin/kei_echo.pl
    chmod 755 /usr/share/koha/bin/kei_echo.pl
    panel eval 'tools_workdir; l=$(tools_log echo); koha_tool "$l" kei_echo.pl "a b" "\$HOME" "\`id\`" "q\"uote" "back\\slash" "a;b|c&d"; cat "$l"'
    rm -f /usr/share/koha/bin/kei_echo.pl
    assert 'echo "$output" | grep -qxF "<a b>"' "$output"
    assert 'echo "$output" | grep -qxF "<\$HOME>" && echo "$output" | grep -qxF "<\`id\`>"' "$output"
    assert 'echo "$output" | grep -qxF "<q\"uote>" && echo "$output" | grep -qxF "<back\\slash>" && echo "$output" | grep -qxF "<a;b|c&d>"' "$output"
    panel eval 'tools_workdir; l=$(tools_log echo); koha_tool "$l" stage_file.pl "it'"'"'s"; echo "rc=$?"'
    assert 'echo "$output" | grep -q "rc=2"' "$output"
    assert '! grep -q "^stage_file.pl" "$KEI_S/calls.log" 2>/dev/null'
}

# --- SQL reports pack ------------------------------------------------------

# The other Koha columns and tables the reports read (same names and types
# as kohastructure.sql), with a row for each report to find.
reports_catalog() {
    tools_sql "
ALTER TABLE borrowers ADD COLUMN IF NOT EXISTS address2 mediumtext, ADD COLUMN IF NOT EXISTS city longtext;
ALTER TABLE items ADD COLUMN IF NOT EXISTS itype varchar(10), ADD COLUMN IF NOT EXISTS ccode varchar(80),
  ADD COLUMN IF NOT EXISTS booksellerid longtext, ADD COLUMN IF NOT EXISTS itemnotes_nonpublic longtext,
  ADD COLUMN IF NOT EXISTS price decimal(8,2), ADD COLUMN IF NOT EXISTS replacementprice decimal(8,2),
  ADD COLUMN IF NOT EXISTS withdrawn tinyint(1) NOT NULL DEFAULT 0, ADD COLUMN IF NOT EXISTS withdrawn_on datetime,
  ADD COLUMN IF NOT EXISTS damaged tinyint(1) NOT NULL DEFAULT 0, ADD COLUMN IF NOT EXISTS damaged_on datetime,
  ADD COLUMN IF NOT EXISTS datelastborrowed date;
ALTER TABLE statistics ADD COLUMN IF NOT EXISTS itemtype varchar(10);
CREATE TABLE IF NOT EXISTS itemtypes (itemtype varchar(10) NOT NULL PRIMARY KEY, description longtext) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE accountlines (accountlines_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, borrowernumber int(11), amountoutstanding decimal(28,6));
CREATE TABLE borrower_debarments (borrower_debarment_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, borrowernumber int(11) NOT NULL,
  expiration date, type varchar(50) NOT NULL DEFAULT 'MANUAL', comment mediumtext);
CREATE TABLE reserves (reserve_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, borrowernumber int(11) NOT NULL, biblionumber int(11) NOT NULL,
  itemnumber int(11), branchcode varchar(10), found varchar(1), waitingdate date);
CREATE TABLE auth_header (authid bigint(20) unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY, authtypecode varchar(10) NOT NULL DEFAULT '',
  datecreated date, marcxml longtext NOT NULL) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO itemtypes VALUES ('LIVRO', 'Livro') ON DUPLICATE KEY UPDATE description = VALUES(description);
UPDATE items SET itype = 'LIVRO', itemcallnumber = '869.3 A1', booksellerid = 'Doação da prefeitura', dateaccessioned = CURDATE() WHERE itemnumber = 20;
UPDATE items SET withdrawn = 1, withdrawn_on = '2025-05-01' WHERE itemnumber = 30;
UPDATE biblio SET datecreated = CURDATE() WHERE biblionumber = 20;
UPDATE biblio_metadata SET metadata = REPLACE(metadata, '</record>', '<controlfield tag=\"008\">250101s2025    bl     j      000 1 por d</controlfield><datafield tag=\"650\" ind1=\" \" ind2=\"4\"><subfield code=\"a\">Contos</subfield><subfield code=\"9\">1</subfield></datafield></record>') WHERE biblionumber = 20;
UPDATE borrowers SET city = 'Curitiba', address2 = 'Centro' WHERE cardnumber IN ('S1', 'S2');
UPDATE borrowers SET dateenrolled = CURDATE() WHERE cardnumber = 'S2';
INSERT INTO statistics (datetime, branch, type, itemnumber, borrowernumber, itemtype)
  SELECT NOW(), 'CPL', 'issue', 20, borrowernumber, 'LIVRO' FROM borrowers WHERE cardnumber = 'S1';
INSERT INTO accountlines (borrowernumber, amountoutstanding) SELECT borrowernumber, 2.5 FROM borrowers WHERE cardnumber = 'S2';
INSERT INTO borrower_debarments (borrowernumber, expiration, comment) SELECT borrowernumber, NULL, 'Overdue' FROM borrowers WHERE cardnumber = 'S3';
INSERT INTO reserves (borrowernumber, biblionumber, itemnumber, branchcode, found, waitingdate)
  SELECT borrowernumber, 5, 5, 'CPL', 'W', CURDATE() FROM borrowers WHERE cardnumber = 'S1';
INSERT INTO auth_header (authid, authtypecode, datecreated, marcxml) VALUES
  (1, 'TOPIC_TERM', '2025-01-01', '<record><datafield tag=\"150\" ind1=\" \" ind2=\" \"><subfield code=\"a\">Contos</subfield></datafield></record>'),
  (2, 'PERSO_NAME', '2025-01-01', '<record><datafield tag=\"100\" ind1=\"1\" ind2=\" \"><subfield code=\"a\">Ninguém, Fulano</subfield></datafield></record>');"
}
# report_run KEY: the saved report of the pack, run as Koha would (dates asked at run time: 2000-01-01..2099-12-31).
report_run() {
    local q
    q=$(tools_sql "SELECT savedsql FROM saved_sql WHERE notes LIKE '%[koha-easy-installer:$1]%';")
    [ -n "$q" ] || return 1
    q=$(sed -E -e "s/<<From[^<>]*>>/'2000-01-01'/g" -e "s/<<[^<>]*>>/'2099-12-31'/g" <<< "$q")
    tools_sql "$q"
}

@test "L08 reports pack: tagged read-only reports, idempotent, removal keeps other reports" {
    reports_catalog
    inputs "1"; answer yes
    panel lt_reports
    assert '[ "$status" -eq 0 ]' "$output"
    local n ids
    n=$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '%[koha-easy-installer:%';")
    assert '[ "$n" = "22" ]' "22 reports expected, got $n: $(dialogs) $(cat "$KEI_S/textbox.last")"
    # C4::Reports::Guided refuses these words anywhere in a saved report.
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '"'"'%[koha-easy-installer:%'"'"' AND savedsql REGEXP '"'"'[[:<:]](UPDATE|DELETE|DROP|INSERT|SHOW|CREATE)[[:>:]]'"'"';")" = "0" ]' "a report has a word Koha refuses"
    # Each new report finds the row made for it.
    assert 'report_run acquisitions | grep -q "Donation"' "$(report_run acquisitions)"
    assert 'report_run zero-loans | grep -q .'
    assert 'report_run ddc-classes | grep -qP "^800\tLiterature\t1\t1$"' "$(report_run ddc-classes)"
    assert 'report_run patrons-district | grep -qP "^Curitiba\tCentro\t2\t2$"' "$(report_run patrons-district)"
    assert 'report_run patrons-new | grep -qP "\tST\tCPL\t1$"' "$(report_run patrons-new)"
    assert 'report_run inventory-out | grep -q "Withdrawn: 1"' "$(report_run inventory-out)"
    assert 'report_run inventory-out | grep -q "Lost: Lost"' "$(report_run inventory-out)"
    assert 'report_run loans-type | grep -qP "^Livro\t1\t0\t0$"' "$(report_run loans-type)"
    assert 'report_run children-new | grep -q "869.3 A1"' "$(report_run children-new)"
    assert '[ "$(report_run fines-debarred | wc -l)" = "2" ]' "$(report_run fines-debarred)"
    assert '[ "$(report_run orphan-authorities | cut -f1)" = "2" ]' "$(report_run orphan-authorities)"
    assert 'report_run active-patrons | grep -qP "^ST\tStudent\t1\t1$"' "$(report_run active-patrons)"
    assert '[ "$(report_run holds-waiting | wc -l)" = "1" ]'
    assert 'report_run collection-type | grep -qP "^CPL\tLivro\t1\t1\t0$"' "$(report_run collection-type)"
    assert 'report_run circ-daily | grep -q .'

    assert '[ "$(pre_backups REPORTS)" = "1" ]'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql WHERE notes LIKE '"'"'%[koha-easy-installer:%'"'"' AND savedsql NOT LIKE '"'"'SELECT %'"'"';")" = "0" ]' "only SELECT statements"
    assert '[ "$(tools_sql "SELECT DISTINCT borrowernumber FROM saved_sql WHERE report_group IS NOT NULL;")" = "$(tools_sql "SELECT borrowernumber FROM borrowers WHERE cardnumber = '"'"'E4'"'"';")" ]' "owner = the superlibrarian"
    # Every saved query runs on the catalog.
    local q
    while IFS= read -r q; do
        q=$(sed -E "s/<<[^<>]*>>/'2000-01-01'/g" <<< "$q")      # the dates Koha asks for
        assert 'mysql koha_library -e "$q" >/dev/null' "report does not run: $q"
    done < <(tools_sql "SELECT savedsql FROM saved_sql WHERE notes LIKE '%[koha-easy-installer:%';")
    ids=$(tools_sql "SELECT GROUP_CONCAT(id ORDER BY id) FROM saved_sql;")
    inputs "1"; answer yes
    panel lt_reports
    assert '[ "$(tools_sql "SELECT GROUP_CONCAT(id ORDER BY id) FROM saved_sql;")" = "$ids" ]' "installing again must update the same reports"
    assert 'grep -q "update" "$KEI_S/textbox.last"'
    inputs "2"; answer yes
    panel lt_reports
    assert '[ "$(tools_sql "SELECT report_name FROM saved_sql;")" = "My own report" ]' "only the pack may be removed"
}

@test "L09 reports pack declined after the preview: nothing saved, no backup" {
    inputs "1"; answer no
    panel lt_reports
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM saved_sql;")" = "1" ] && [ "$(pre_backups)" = "0" ]'
    assert 'grep -q "Most borrowed titles" "$KEI_S/textbox.last"' "the preview lists the reports"
}

# --- patrons ------------------------------------------------------------------

@test "L12 school-year turnover: dry run lists the patrons, --confirm only after the backup" {
    inputs "ST" "FM" "age" "*"
    answer yes
    panel lt_patron_category
    assert 'grep -q "^update_patrons_category.pl --from ST --to FM -v --too_old \[pre=0\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^update_patrons_category.pl --from ST --to FM -v --too_old --confirm \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "WOULD HAVE Updated Bia Souza" "$KEI_S/textbox.last"'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM borrowers WHERE categorycode = '"'"'FM'"'"';")" = "2" ]' "only the two adults move"
    assert 'dialogs | grep -q "Patrons moved from ST to FM: 2"'
}

@test "L13 school-year turnover: same category, bad date and empty selection change nothing" {
    inputs "ST" "ST"
    panel lt_patron_category
    inputs "ST" "FM" "date" "2024-13-45"
    panel lt_patron_category
    inputs "ST" "FM" "date" "2000-01-01" "*"
    panel lt_patron_category
    assert '[ "$(grep -c "^update_patrons_category.pl" "$KEI_S/calls.log")" = "1" ]' "only the valid request reaches Koha: $(calls)"
    assert 'grep -q -- "--regbefore 2000-01-01 \[pre=0\]" "$KEI_S/calls.log"'
    assert 'dialogs | grep -q "No patron matches"'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM borrowers WHERE categorycode = '"'"'ST'"'"';")" = "3" ] && [ "$(pre_backups)" = "0" ]'
}

# --- data quality ---------------------------------------------------------------

@test "L14 data-quality check is read-only and its report goes to a log" {
    panel lt_data_quality
    assert 'dialogs | grep -q "No inconsistencies found"' "$(dialogs)"
    tools_sql "UPDATE items SET homebranch = NULL WHERE itemnumber = 7;"
    panel lt_data_quality
    assert 'grep -q "itemnumber=7" "$KEI_S/textbox.last"'
    assert '[ "$(ls /var/log/koha-easy-install/tools/data-quality-*.log | wc -l)" -ge 1 ]'
    assert '[ "$(pre_backups)" = "0" ]' "a read-only check makes no backup"
}

# --- privacy (LGPD) -------------------------------------------------------------

@test "L15 anonymise: counts like Koha, then PRE-PRIVACY backup, then batch_anonymise.pl" {
    inputs "365"
    answer yes
    panel lt_privacy_anonymise
    assert 'dialogs | grep -q "Loans: 3"' "3 old loans (the patron who keeps his history and the recent loan are left out): $(dialogs)"
    assert 'dialogs | grep -q "Holds: 2"'
    assert 'grep -q "^batch_anonymise.pl --days 365 -v \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM old_issues WHERE borrowernumber IS NULL;")" = "3" ]'
    assert 'dialogs | grep -q "Anonymised: 3 loan(s) and 2 hold(s)"'
}

@test "L16 anonymise: too few days is refused, declining changes nothing" {
    inputs "7"
    panel lt_privacy_anonymise
    inputs "365"; answer no
    panel lt_privacy_anonymise
    assert '! grep -q "batch_anonymise" "$KEI_S/calls.log" 2>/dev/null'
    assert '[ "$(tools_sql "SELECT COUNT(*) FROM old_issues WHERE borrowernumber IS NULL;")" = "0" ] && [ "$(pre_backups)" = "0" ]'
}

@test "L17 delete old patrons: dry run, typed count confirmation, PRE-PRIVACY backup" {
    inputs "2020-01-01" "*" "5"      # wrong number typed
    panel lt_privacy_delete
    assert '! grep -q "delete_patrons.pl.*--confirm" "$KEI_S/calls.log"' "$(calls)"
    assert 'dialogs | grep -q "did not match"'
    inputs "2020-01-01" "*" "2"
    panel lt_privacy_delete
    assert 'grep -q "^delete_patrons.pl --expired_before 2020-01-01 --not_borrowed_since 2020-01-01 -v \[pre=0\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^delete_patrons.pl .* -v --confirm \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(tools_sql "SELECT GROUP_CONCAT(cardnumber ORDER BY cardnumber) FROM borrowers WHERE dateexpiry < '"'"'2020-01-01'"'"';")" = "E3,E4" ]' "the patron with a loan and the staff member stay"
    assert 'dialogs | grep -q "Patrons deleted: 2"'
}

@test "L18 tool logs are private and listed newest first" {
    inputs "ST" "FM" "all" "*"; answer no
    panel lt_patron_category
    assert '[ "$(stat -c %a /var/log/koha-easy-install/tools)" = "700" ]'
    assert '[ "$(stat -c %a /var/log/koha-easy-install/tools/patron-category-*.log)" = "600" ]'
    panel lt_view_logs
    assert 'grep -q "WOULD HAVE Updated" "$KEI_S/textbox.last"'
}
