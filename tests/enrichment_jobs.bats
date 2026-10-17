#!/usr/bin/env bats
# Enrichment jobs (installer section "Enrichment jobs"): export, the worker,
# the explicit Apply through Koha's staged import, and Revert, on a real
# MariaDB with the real nexus_jobs and a real static.db. export_records.pl,
# stage_file.pl and commit_file.pl are stand-ins (tests/data/koha_import_mock.py)
# that act on the tables the way Koha does: a replace overlay keeps the old
# record in marcxml_old, a revert puts it back and skips records whose status
# is error or reverted (C4::ImportBatch).

setup_file() {
    load lib/common
    kei_start_mariadb
    mysql -e "CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4;"
    STATIC="$BATS_FILE_TMPDIR/static.db"
    PYTHONPATH="$KEI_REPO/enrichment" python3 - "$STATIC" <<'PY'
import json, sys
from pathlib import Path
from enrich_build.build import Builder, SourceConfig
from nexus_enrich import marc
from nexus_enrich.marc import Field, Record
out = Path(sys.argv[1])
rec = Record("00000nam a2200000 a 4500", [
    Field("001", data="U1"), Field("008", data="201017s1995    bl            000 0 por d"),
    Field("020", " ", " ", [("a", "9788535902778")]), Field("100", "1", " ", [("a", "Saramago, José")]),
    Field("245", "1", "0", [("a", "Ensaio sobre a cegueira")]),
    Field("260", " ", " ", [("a", "São Paulo :"), ("b", "Companhia das Letras,"), ("c", "1995")]),
    Field("300", " ", " ", [("a", "310 p.")]), Field("082", "0", "4", [("a", "869.3")]),
    Field("650", " ", "4", [("a", "Cegueira")]), Field("650", " ", "4", [("a", "Romance português")])])
rec.fields.sort(key=lambda f: f.tag)
(out.parent / "dump.jsonl").write_text(json.dumps({"fonte": "Universidade Federal do Paraná (UFPR)",
                                                   "marcxml": marc.to_xml(rec)}, ensure_ascii=False))
src = SourceConfig.from_dict({"id": "zeus", "paths": ["dump.jsonl"], "mode": "full", "brazilian": True,
                              "source_field": "fonte"})
assert Builder(out, [src], out.parent).build().error_count == 0
PY
}

# One local record: a copy of the open catalogue's book without subjects and
# Dewey (biblionumbers 1, 3, 4, 5) or a book nobody else has (2).
bib_xml() {
    local bn="$1" f005="$2" title="${3:-Ensaio sobre a cegueira}" isbn="${4:-9788535902778}"
    printf '<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader>'
    printf '<controlfield tag="005">%s</controlfield>' "$f005"
    printf '<controlfield tag="008">201017s1995    bl            000 0 por d</controlfield>'
    [ -n "$isbn" ] && printf '<datafield tag="020" ind1=" " ind2=" "><subfield code="a">%s</subfield></datafield>' "$isbn"
    printf '<datafield tag="100" ind1="1" ind2=" "><subfield code="a">Saramago, José</subfield></datafield>'
    printf '<datafield tag="245" ind1="1" ind2="0"><subfield code="a">%s</subfield></datafield>' "$title"
    printf '<datafield tag="260" ind1=" " ind2=" "><subfield code="a">São Paulo :</subfield><subfield code="b">Companhia das Letras,</subfield><subfield code="c">1995</subfield></datafield>'
    printf '<datafield tag="942" ind1=" " ind2=" "><subfield code="c">BK</subfield></datafield>'
    printf '<datafield tag="999" ind1=" " ind2=" "><subfield code="c">%s</subfield><subfield code="d">%s</subfield></datafield></record>' "$bn" "$bn"
}

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    rm -f "$KEI_S/dialogs.log"
    mysql "$DB" <<'SQL'
DROP TABLE IF EXISTS biblio_metadata, import_batches, import_records, import_biblios, marc_matchers, matchpoints,
  matcher_matchpoints, matchpoint_components, matchpoint_component_norms, systempreferences, zebraqueue,
  auth_header, import_auths;
CREATE TABLE auth_header (authid bigint(20) unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY,
  authtypecode varchar(10) NOT NULL DEFAULT '', marcxml longtext NOT NULL) DEFAULT CHARSET=utf8mb4;
CREATE TABLE import_auths (import_record_id int(11) NOT NULL PRIMARY KEY, matched_authid int(11));
CREATE TABLE biblio_metadata (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, biblionumber int(11) NOT NULL,
  format varchar(16) NOT NULL, `schema` varchar(16) NOT NULL, metadata longtext NOT NULL) DEFAULT CHARSET=utf8mb4;
CREATE TABLE import_batches (import_batch_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, matcher_id int(11),
  num_records int(11) NOT NULL DEFAULT 0, import_status enum('staging','staged','importing','imported','reverting','reverted','cleaned')
  NOT NULL DEFAULT 'staging', record_type enum('biblio','auth','holdings') NOT NULL DEFAULT 'biblio', comments longtext);
CREATE TABLE import_records (import_record_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, import_batch_id int(11) NOT NULL,
  record_sequence int(11) NOT NULL DEFAULT 0, marcxml longtext NOT NULL, marcxml_old longtext,
  overlay_status enum('no_match','auto_match','manual_match','match_applied') NOT NULL DEFAULT 'no_match',
  status enum('error','staged','imported','reverted','items_reverted','ignored') NOT NULL DEFAULT 'staged') DEFAULT CHARSET=utf8mb4;
CREATE TABLE import_biblios (import_record_id int(11) NOT NULL PRIMARY KEY, matched_biblionumber int(11));
CREATE TABLE marc_matchers (matcher_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, code varchar(10) NOT NULL DEFAULT '',
  description varchar(255) NOT NULL DEFAULT '', record_type varchar(10) NOT NULL DEFAULT 'biblio', threshold int(11) NOT NULL DEFAULT 0);
CREATE TABLE matchpoints (matcher_id int(11) NOT NULL, matchpoint_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
  search_index varchar(30) NOT NULL DEFAULT '', score int(11) NOT NULL DEFAULT 0);
CREATE TABLE matcher_matchpoints (matcher_id int(11) NOT NULL, matchpoint_id int(11) NOT NULL);
CREATE TABLE matchpoint_components (matchpoint_id int(11) NOT NULL, matchpoint_component_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
  sequence int(11) NOT NULL DEFAULT 0, tag varchar(3) NOT NULL DEFAULT '', subfields varchar(40) NOT NULL DEFAULT '',
  `offset` int(4) NOT NULL DEFAULT 0, length int(4) NOT NULL DEFAULT 0);
CREATE TABLE matchpoint_component_norms (matchpoint_component_id int(11) NOT NULL, sequence int(11) NOT NULL DEFAULT 0,
  norm_routine varchar(50) NOT NULL DEFAULT '');
CREATE TABLE systempreferences (variable varchar(50) NOT NULL PRIMARY KEY, value mediumtext);
CREATE TABLE zebraqueue (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, done int(11) NOT NULL DEFAULT 0);
INSERT INTO systempreferences VALUES ('SearchEngine', 'Zebra');
INSERT INTO marc_matchers (code, description) VALUES ('ISBN', 'ISBN');
SQL
    local bn
    for bn in 1 2 3 4 5; do
        if [ "$bn" = 2 ]; then x=$(bib_xml 2 20260101000000.0 "Um livro que ninguém tem" ""); else x=$(bib_xml "$bn" 20260101000000.0); fi
        mysql --default-character-set=utf8mb4 "$DB" -e "INSERT INTO biblio_metadata (biblionumber, format, \`schema\`, metadata) VALUES ($bn, 'marcxml', 'MARC21', '$x');"
    done
    mkdir -p "$W/enrich/.venv/bin" "$W/state"
    printf '#!/bin/sh\nPYTHONPATH=%s exec python3 "$@"\n' "$KEI_REPO/enrichment" > "$W/enrich/.venv/bin/python"
    chmod +x "$W/enrich/.venv/bin/python"
    ln -s "$KEI_REPO/enrichment/nexus_jobs" "$W/enrich/nexus_jobs"
    cp "$BATS_FILE_TMPDIR/static.db" "$W/state/static.db"
    cat > "$W/extra.sh" <<SH
SYS_LANG=en
DB_NAME=$DB
kei_result() { printf '%s=%s\n' "\$1" "\$2" >> "$W/results"; }
require_database() { return 0; }
TOOLS_LOG_DIR="$W/logs"
ENRICH_DIR="$W/enrich"
ENRICH_STATE="$W/state"
ENRICH_RUNAS=""
ENRICH_INDEX_WAIT=0
systemctl() { echo "systemctl \$*" >> "$W/calls"; }
display_explanation() { :; }
ui_textbox() { :; }
tools_safety_backup() { TOOLS_PRE="$W/PRE-\$1.sql"; : > "\$TOOLS_PRE"; echo "backup \$1" >> "$W/calls"; }
# Koha's scripts: the stand-in, with the throttle prefix recorded.
koha_tool() {
    local log="\$1" name="\$2"; shift 2
    printf '\$ %s %s\n' "\$name" "\$*" >> "\$log"
    echo "\$name [\${KOHA_THROTTLE:+throttled}] \$*" >> "$W/calls"
    python3 "$KEI_REPO/tests/data/koha_import_mock.py" "$DB" "\$name" "\$@" >> "\${KOHA_EXEC_OUT:-\$log}" 2>> "\$log"
}
SH
}

zsql() { mysql -N --default-character-set=utf8mb4 "$DB" -e "$1"; }
p() { run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" "$@"; echo "$output"; cat "$W/logs/"* 2>/dev/null || true; }
f005() { zsql "SELECT ExtractValue(metadata, '//controlfield[@tag=\"005\"]') FROM biblio_metadata WHERE biblionumber = $1"; }
has650() { zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = $1" | grep -o 'tag="650"' | wc -l; }
worker() { "$W/enrich/.venv/bin/python" -m nexus_jobs --state "$W/state" worker --pause 0; }

@test "enrichment job: export, staged report, Apply in Koha batches, Revert keeps later edits" {
    p enrich_job_add "1-5"
    [ "$status" -eq 0 ]
    grep -q "^job=1$" "$W/results" && grep -q "^records=5$" "$W/results"
    grep -q "^export_records.pl \[throttled\] --record-type=bibs --format=xml --dont_export_items --id_list_file=" "$W/calls"
    grep -q "systemctl start --no-block koha-nexus-enrich" "$W/calls"
    [ "$(sort "$W/state/jobs/1/ids.txt" | tr '\n' ' ')" = "1 2 3 4 5 " ]
    # Nothing reaches Koha before Apply: the worker only writes the report.
    worker
    [ "$(has650 1)" = "0" ]
    show=$("$W/enrich/.venv/bin/python" -m nexus_jobs --state "$W/state" show 1)
    echo "$show"
    [[ "$show" == *'"state": "ready"'* ]]
    # 2 shares only the author: listed for review, never applied.
    [[ "$show" == *'"enriched": 4'* ]] && [[ "$show" == *'"review": 1'* ]]
    grep -q 'class="add">+ 650 _4' "$W/state/jobs/1/report.html"
    # 3 is edited in Koha after the report; Koha's search finds the wrong
    # record for 4: neither may be overwritten.
    zsql "UPDATE biblio_metadata SET metadata = REPLACE(metadata, '20260101000000.0', '20261017110000.0') WHERE biblionumber = 3"
    echo "4=99" > "$W/mismatch"
    : > "$W/results"
    MOCK_MISMATCH_FILE="$W/mismatch" p enrich_job_apply 1
    [ "$status" -eq 0 ]
    grep -q "^backup ENRICH$" "$W/calls"
    m=$(zsql "SELECT matcher_id FROM marc_matchers WHERE code = 'NEXUSBIB'")
    [ "$(zsql "SELECT search_index, score FROM matchpoints WHERE matcher_id = $m")" = "$(printf 'local-number\t1000')" ]
    [ "$(zsql "SELECT tag, subfields FROM matchpoint_components")" = "$(printf '999\tc')" ]
    grep -q "^stage_file.pl \[throttled\] --file .* --format MARCXML --encoding UTF-8 --match $m --no-create --item-action ignore --comment koha.nexus enrichment job 1 batch 1$" "$W/calls"
    grep -q "^commit_file.pl \[throttled\] --batch-number 1$" "$W/calls"
    # The staged file had 1, 4 and 5 (3 changed since the report); 4 was
    # marked error so the commit skipped it.
    [ "$(zsql "SELECT record_sequence, status FROM import_records ORDER BY record_sequence" | tr '\t\n' ': ')" = "1:imported 2:error 3:imported " ]
    [ "$(has650 1)" = "2" ] && [ "$(has650 5)" = "2" ]
    [ "$(has650 3)" = "0" ] && [ "$(has650 4)" = "0" ] && [ "$(has650 2)" = "0" ]
    zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = 1" | grep -q 'tag="883"'
    zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = 1" | grep -q '<subfield code="c">BK</subfield>'
    grep -q "^applied=2$" "$W/results" && grep -q "^apply=done$" "$W/results"
    grep -q "OK .*Job 1 applied: 2 record(s) enriched" "$KEI_S/dialogs.log"
    # Applying again finds nothing left.
    : > "$W/results"
    p enrich_job_apply 1
    grep -q "^apply=nothing$\|^apply=not-ready$" "$W/results"
    # A librarian edits 5 after Apply: Revert gives 1 its old version and keeps 5.
    zsql "UPDATE biblio_metadata SET metadata = REPLACE(metadata, '</record>', '<datafield tag=\"590\" ind1=\" \" ind2=\" \"><subfield code=\"a\">nota</subfield></datafield></record>') WHERE biblionumber = 5"
    zsql "UPDATE biblio_metadata SET metadata = REPLACE(metadata, '$(f005 5)', '20261018080000.0') WHERE biblionumber = 5"
    : > "$W/results"
    p enrich_job_revert 1
    [ "$status" -eq 0 ]
    grep -q "^backup UNDO-ENRICH$" "$W/calls"
    grep -q "^commit_file.pl \[throttled\] --revert --batch-number 1$" "$W/calls"
    [ "$(has650 1)" = "0" ] && [ "$(f005 1)" = "20260101000000.0" ]
    [ "$(has650 5)" = "2" ] && zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = 5" | grep -q nota
    grep -q "^reverted=1$" "$W/results" && grep -q "^kept=1$" "$W/results"
    show=$("$W/enrich/.venv/bin/python" -m nexus_jobs --state "$W/state" show 1)
    [[ "$show" == *'"state": "reverted"'* ]]
}

@test "enrichment job: a bad scope, an empty scope and a missing database change nothing" {
    p enrich_job_add "abc"
    [ "$status" -ne 0 ]
    grep -q "^job=invalid-scope$" "$W/results"
    p enrich_job_add "900-901"
    [ "$status" -ne 0 ]
    grep -q "^job=empty$" "$W/results"
    rm "$W/state/static.db"
    p enrich_job_add "all"
    [ "$status" -ne 0 ]
    grep -q "^job=no-static-db$" "$W/results"
    grep -q "systemctl start --no-block koha-nexus-enrich-update.service" "$W/calls"
    ! grep -q "stage_file\|commit_file" "$W/calls" 2>/dev/null
}

@test "enrichment: a fresh install gets an empty static.db; a job waits for the download" {
    rm "$W/state/static.db"
    p enrich_empty_db
    [ "$status" -eq 0 ]
    [ -s "$W/state/static.db" ]
    [ "$(PYTHONPATH="$KEI_REPO/enrichment" python3 -c 'import sys; from nexus_enrich.static import record_count; print(record_count(sys.argv[1]))' "$W/state/static.db")" = 0 ]
    p enrich_empty_db                                   # never over a database already there
    [ "$status" -eq 0 ]
    cp "$BATS_FILE_TMPDIR/static.db" "$W/state/static.db"
    p enrich_empty_db
    p enrich_records
    [ "${lines[0]}" = 1 ]
    rm "$W/state/static.db"
    p enrich_empty_db
    p enrich_job_add "all"
    [ "$status" -ne 0 ]
    grep -q "^job=no-static-db$" "$W/results"
    grep -q "has not been downloaded yet" "$KEI_S/dialogs.log"
}

@test "enrichment job: a failed commit stops Apply and leaves the rest for a second Apply" {
    p enrich_job_add "1"
    worker
    touch "$W/fail-commit"
    MOCK_FAIL_COMMIT="$W/fail-commit" p enrich_job_apply 1
    [ "$status" -ne 0 ]
    grep -q "^apply=failed$" "$W/results"
    [ "$(has650 1)" = "0" ]
    : > "$W/results"
    p enrich_job_apply 1
    [ "$status" -eq 0 ]
    grep -q "^applied=1$" "$W/results"
    [ "$(has650 1)" = "2" ]
    zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = 1" | grep -q "Saramago, José"
}

@test "enrichment: the worker unit is sandboxed and throttled; the panel tasks exist" {
    grep -q 'ExecStart=${ENRICH_DIR}/.venv/bin/python -m nexus_jobs worker' "$KEI_REPO/installer"
    for d in "CPUQuota=25%" "MemoryMax=256M" "PrivateNetwork=yes" "ProtectSystem=strict" "IOSchedulingClass=idle" "Nice=19"; do
        awk '/\$\{ENRICH_WORKER_UNIT\}.service" <<UNIT/,/^UNIT$/' "$KEI_REPO/installer" | grep -qx "$d"
    done
    for task in enrich-job-add enrich-auth-add enrich-jobs enrich-job-show enrich-job-diff enrich-job-apply enrich-job-revert enrich-job-cancel enrich-pause; do
        grep -q "^        ${task})" "$KEI_REPO/installer"
    done
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" throttle_cmd
    [[ "$output" == *"nice -n 19 ionice -c 3"* ]]
}

bib9() { zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = $1" | grep -o '<subfield code="9">[0-9]*</subfield>' | sed 's/.*">\([0-9]*\)<.*/\1/' | paste -sd, -; }

@test "authority job: new authorities created before the records, linked by \$9; Revert keeps one still in use" {
    p enrich_job_add "1-2" auth exact
    [ "$status" -eq 0 ]
    grep -q "^job=1$" "$W/results"
    grep -q "^export_records.pl \[throttled\] --record-type=auths --format=xml$" "$W/calls"
    [ -f "$W/state/jobs/1/authorities.xml" ]
    worker
    [ -z "$(bib9 1)" ]
    show=$("$W/enrich/.venv/bin/python" -m nexus_jobs --state "$W/state" show 1)
    echo "$show"
    [[ "$show" == *'"kind": "auth"'* ]] && [[ "$show" == *'"state": "ready"'* ]]
    [[ "$show" == *'"new_authorities": 1,'* ]] && [[ "$show" == *'"changed": 2'* ]]
    grep -q "Saramago, José" "$W/state/jobs/1/report.html"
    : > "$W/results"
    p enrich_job_apply 1
    [ "$status" -eq 0 ]
    grep -q "^backup ENRICH$" "$W/calls"
    grep -q "^stage_file.pl \[throttled\] --authorities --file .* --format MARCXML --encoding UTF-8 --comment koha.nexus authorities job 1 batch 1$" "$W/calls"
    [ "$(zsql "SELECT COUNT(*) FROM auth_header")" = 1 ]
    a=$(zsql "SELECT authid FROM auth_header")
    zsql "SELECT marcxml FROM auth_header" | grep -q 'tag="667"'
    zsql "SELECT marcxml FROM auth_header" | grep -q "<controlfield tag=\"001\">$a</controlfield>"
    [ "$(bib9 1)" = "$a" ] && [ "$(bib9 2)" = "$a" ]
    grep -q "^authorities=1$" "$W/results" && grep -q "^applied=2$" "$W/results"
    grep -q "OK .*Job 1 applied: 1 new authority record(s), 2 record(s) linked" "$KEI_S/dialogs.log"
    # 2 is edited after Apply: it keeps its link, so the authority stays too.
    zsql "UPDATE biblio_metadata SET metadata = REPLACE(metadata, '$(f005 2)', '20261018080000.0') WHERE biblionumber = 2"
    : > "$W/results"
    p enrich_job_revert 1
    [ "$status" -eq 0 ]
    [ -z "$(bib9 1)" ] && [ "$(bib9 2)" = "$a" ]
    [ "$(zsql "SELECT COUNT(*) FROM auth_header")" = 1 ]
    grep -q "^reverted=1$" "$W/results" && grep -q "^kept=2$" "$W/results" && grep -q "^authorities=0$" "$W/results"
    show=$("$W/enrich/.venv/bin/python" -m nexus_jobs --state "$W/state" show 1)
    [[ "$show" == *'"state": "reverted"'* ]]
}

@test "authority job: an authority Koha gained after the report is linked, not created; Revert removes what it made" {
    p enrich_job_add "1" auth exact
    worker
    zsql "INSERT INTO auth_header (authid, marcxml) VALUES (500, '<record xmlns=\"http://www.loc.gov/MARC21/slim\"><leader>00000nz  a2200000n  4500</leader><controlfield tag=\"001\">500</controlfield><datafield tag=\"100\" ind1=\"1\" ind2=\" \"><subfield code=\"a\">Saramago, José</subfield></datafield></record>')"
    : > "$W/results"
    p enrich_job_apply 1
    [ "$status" -eq 0 ]
    ! grep -q -- "--authorities" "$W/calls"
    [ "$(bib9 1)" = "500" ]
    grep -q "^authorities=0$" "$W/results"
    : > "$W/results"
    p enrich_job_revert 1
    [ "$status" -eq 0 ]
    [ -z "$(bib9 1)" ]
    [ "$(zsql "SELECT COUNT(*) FROM auth_header")" = 1 ]
    # A second job creates the authority itself; reverting it removes it.
    zsql "DELETE FROM auth_header"
    p enrich_job_add "1" auth exact
    worker
    p enrich_job_apply 2
    [ "$(zsql "SELECT COUNT(*) FROM auth_header")" = 1 ]
    : > "$W/results"
    p enrich_job_revert 2
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM auth_header")" = 0 ] && [ -z "$(bib9 1)" ]
    grep -q "^authorities=1$" "$W/results"
}
