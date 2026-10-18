#!/usr/bin/env bats
# On-demand enrichment (installer section "On-demand enrichment"): a few
# records or a typed query, exported as for a batch job, searched by the
# koha-nexus-ondemand service (here: the real service on a scripted fake
# network, tests/test_ondemand_dispatch.py, since no Z39.50 server is
# reachable from the test machine), then the batch Apply and Revert with a
# copy of the records in place of a full backup. Same MariaDB tables and
# Koha stand-ins as tests/enrichment_jobs.bats.

setup_file() {
    load lib/common
    kei_start_mariadb
    mysql -e "CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4;"
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
    ln -s "$KEI_REPO/enrichment/nexus_ondemand" "$W/enrich/nexus_ondemand"
    cp "$KEI_REPO/panel/kei_panel/data/z3950_direct.json" "$W/enrich/z3950_direct.json"
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
enrich_od_ready() { echo "enrich_od_ready" >> "$W/calls"; }
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


# The service, once, on a fake network: one Brazilian server whose answer
# is the same book with subjects and Dewey, one that has nothing.
od_service() {
    PYTHONPATH="$KEI_REPO/enrichment:$KEI_REPO/enrichment/tests" python3 - "$W/state" <<'PY'
import asyncio, sys
from pathlib import Path
from nexus_enrich.marc import Field, Record
from nexus_ondemand import service
from nexus_ondemand.config import Settings as Config
from nexus_ondemand.targets import Catalog
from test_ondemand_dispatch import FakeNet, Server, tgt
state = Path(sys.argv[1])
donor = Record("00000nam a2200000 a 4500", [
    Field("001", data="D1"), Field("008", data="201017s1995    bl            000 0 por d"),
    Field("020", " ", " ", [("a", "9788535902778")]), Field("082", "0", "4", [("a", "869.3")]),
    Field("100", "1", " ", [("a", "Saramago, José")]), Field("245", "1", "0", [("a", "Ensaio sobre a cegueira")]),
    Field("260", " ", " ", [("a", "São Paulo :"), ("b", "Companhia das Letras,"), ("c", "1995")]),
    Field("300", " ", " ", [("a", "310 p.")]), Field("650", " ", "0", [("a", "Cegueira")])])
net = FakeNet(ufpr_example_org=Server([donor]), usp_example_org=Server())
cat = Catalog({t.id: t for t in (tgt("ufpr"), tgt("usp"))}, [], "sha")
settings = service.Settings(state, state / "static.db", state / "learned.db", idle=0, poll=0.01)
config = Config(health_db=state / "health.db", static=False)
print(asyncio.run(service.serve(settings, config, catalog=cat, opener=net)))
PY
}
jshow() { "$W/enrich/.venv/bin/python" -m nexus_jobs --state "$W/state" show "$1"; }

@test "on demand: a few records exported, searched, applied with a copy of the records, reverted" {
    p enrich_od_add "1-2"
    [ "$status" -eq 0 ]
    grep -q "^job=1$" "$W/results" && grep -q "^records=2$" "$W/results"
    grep -q "^export_records.pl \[throttled\] --record-type=bibs --format=xml --dont_export_items --id_list_file=" "$W/calls"
    grep -q "systemctl start --no-block koha-nexus-ondemand$" "$W/calls"
    ! grep -q "systemctl start --no-block koha-nexus-enrich$" "$W/calls"
    # the batch worker leaves it alone; the service takes it
    worker
    [[ "$(jshow 1)" == *'"state": "exported"'* ]]
    od_service
    show=$(jshow 1)
    echo "$show"
    [[ "$show" == *'"state": "ready"'* ]] && [[ "$show" == *'"origin": "ondemand"'* ]]
    [[ "$show" == *'"enriched": 1'* ]]
    [[ "$show" == *'"target": "ufpr"'* ]] && [[ "$show" == *'"outcome": "found"'* ]]
    [ "$(has650 1)" = "0" ]                              # nothing in Koha before Apply
    : > "$W/results"
    p enrich_job_apply 1
    [ "$status" -eq 0 ]
    ! grep -q "^backup ENRICH$" "$W/calls"               # no full backup for on demand
    snap=$(ls "$W/state/jobs/1"/snapshot-apply-*.xml)
    grep -q "^backup=$snap$" "$W/results"
    [ "$(grep -c '<record' "$snap")" = 1 ] && grep -q '<subfield code="c">1</subfield>' "$snap"
    [ "$(has650 1)" = "1" ]
    zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = 1" | grep -q 'z3950:ufpr'
    grep -q "^applied=1$" "$W/results" && grep -q "^apply=done$" "$W/results"
    : > "$W/results"
    p enrich_job_revert 1
    [ "$status" -eq 0 ]
    ! grep -q "^backup UNDO-ENRICH$" "$W/calls"
    ls "$W/state/jobs/1"/snapshot-revert-*.xml
    [ "$(has650 1)" = "0" ] && [ ! -e "$W/state/jobs/1/applied.txt" ]
}

@test "on demand: a typed query needs no export; bad requests change nothing" {
    p enrich_od_add --isbn 9788535902778 --title "Ensaio sobre a cegueira"
    [ "$status" -eq 0 ]
    grep -q "^job=1$" "$W/results"
    ! grep -q "export_records" "$W/calls"
    od_service
    show=$(jshow 1)
    echo "$show"
    [[ "$show" == *'"scope": "query"'* ]] && [[ "$show" == *'"source": "z3950:ufpr"'* ]]
    for bad in "all" "1-60" "abc"; do
        : > "$W/results"
        p enrich_od_add "$bad"
        [ "$status" -ne 0 ]
        grep -q "^job=invalid-scope$" "$W/results"
    done
    p enrich_od_add --author "Saramago"
    [ "$status" -ne 0 ]
    p enrich_od_add --isbn
    [ "$status" -eq 2 ]
    p enrich_od_add
    [ "$status" -eq 2 ]
}

@test "on demand: a typed query's record imported as new, never over a record Koha has, undone as a MARC import" {
    p enrich_od_add --isbn 9788535902778
    od_service
    : > "$W/results"
    p enrich_od_import 1 1 1                              # Koha has this ISBN: ignored, nothing added
    [ "$status" -eq 0 ]
    grep -q "^import=exists$" "$W/results" && grep -q "^biblionumber=1$" "$W/results"
    grep -q -- "^stage_file.pl \[\] --file .* --format MARCXML --encoding UTF-8 --match 1 --no-replace --comment koha.nexus on-demand job 1: new record$" "$W/calls"
    [ "$(zsql "SELECT COUNT(*) FROM biblio_metadata")" = 5 ] && [ ! -e "$W/state/jobs/1/imported-1-1" ]
    zsql "DELETE FROM biblio_metadata"
    : > "$W/results"
    p enrich_od_import 1 1 1
    [ "$status" -eq 0 ]
    grep -q "^import=done$" "$W/results" && grep -q "^biblionumber=1$" "$W/results"
    ! grep -q "^backup " "$W/calls"
    new=$(zsql "SELECT metadata FROM biblio_metadata WHERE biblionumber = 1")
    [[ "$new" == *'tag="883"'* ]] && [[ "$new" == *'z3950:ufpr'* ]] && [[ "$new" == *'Cegueira'* ]]
    [ "$(cat "$W/state/jobs/1/imported-1-1")" = 1 ]
    [[ "$(jshow 1)" == *'"imported": 1'* ]]
    : > "$W/results"
    p enrich_od_import 1 1 1                              # twice: refused, still one record
    grep -q "^import=already$" "$W/results"
    [ "$(zsql "SELECT COUNT(*) FROM biblio_metadata WHERE biblionumber = 1")" = 1 ]
    p enrich_od_import 1 1 9
    [ "$status" -ne 0 ]
    grep -q "^import=not-found$" "$W/results"
    p enrich_od_import 1 x 1
    [ "$status" -eq 2 ]
    batch=$(zsql "SELECT MAX(import_batch_id) FROM import_batches")
    p _lt_marc_undo_run "$batch"
    [ "$(zsql "SELECT COUNT(*) FROM biblio_metadata WHERE biblionumber = 1")" = 0 ]
}

@test "on demand: Search more servers, a chosen donor, server health" {
    p enrich_od_add "1"
    od_service
    : > "$W/results"; : > "$W/calls"
    p enrich_od_again 1 more
    [ "$status" -eq 0 ]
    grep -q "^round=2$" "$W/results"
    grep -q "systemctl start --no-block koha-nexus-ondemand$" "$W/calls"
    od_service
    p enrich_od_again 1 donor 1 subjects z3950:ufpr
    [ "$status" -eq 0 ]
    grep -q "^round=2$" "$W/results"
    p enrich_od_again 1 donor 1 "bad group" x
    [ "$status" -eq 2 ]
    p enrich_od_again 1 donor 1 subjects 'x;rm'
    [ "$status" -eq 2 ]
    p enrich_od_again 1 sideways
    [ "$status" -eq 2 ]
    p enrich_job_apply 1
    : > "$W/results"
    p enrich_od_again 1 more                              # applied: no more searching
    [ "$status" -ne 0 ]
    grep -q "^job=not-ready$" "$W/results"
    : > "$W/results"
    p z3950_health
    [ "$status" -eq 0 ]
    grep -q '^health=\[' "$W/results"
    p z3950_health reset --all
    grep -q "^reset=[0-9]*$" "$W/results"
    p z3950_health reset 'a b'
    [ "$status" -eq 2 ]
    p enrich_od_status 1
    grep -q '^status={"state": "idle"' "$W/results"
    grep -q '^job={"id": 1' "$W/results"
}

@test "on demand: the unit is throttled, sandboxed and networked; the list ships; the tasks exist" {
    unit=$(awk '/\$\{ENRICH_ONDEMAND_UNIT\}.service" <<UNIT/,/^UNIT$/' "$KEI_REPO/installer")
    for d in 'ExecStart=${ENRICH_DIR}/.venv/bin/python -m nexus_ondemand serve' "CPUQuota=25%" "MemoryMax=160M" \
             "Nice=10" "IOSchedulingClass=idle" "ProtectSystem=strict" "NoNewPrivileges=yes" \
             'Environment=NEXUS_ONDEMAND_DIRECT_LIST=${ENRICH_DIR}/${ENRICH_DIRECT_LIST}' \
             "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX"; do
        printf '%s\n' "$unit" | grep -qxF "$d"
    done
    ! printf '%s\n' "$unit" | grep -q "PrivateNetwork=yes"
    grep -q 'cp -f "$src/../panel/kei_panel/data/${ENRICH_DIRECT_LIST}" "$ENRICH_DIR/${ENRICH_DIRECT_LIST}"' "$KEI_REPO/installer"
    grep -q "\"\*/panel/kei_panel/data/\${ENRICH_DIRECT_LIST}\"" "$KEI_REPO/installer"
    for task in enrich-od-add enrich-od-status enrich-od-more enrich-od-donor enrich-od-import z3950-health z3950-health-reset; do
        grep -q "^        ${task})" "$KEI_REPO/installer"
    done
    # An install from before on-demand: enrich_od_ready installs what is missing.
    grep -v '^enrich_od_ready()' "$W/extra.sh" > "$W/extra-ready.sh"
    echo "enrich_install() { echo enrich_install >> \"$W/calls\"; }" >> "$W/extra-ready.sh"
    run env KEI_EXTRA="$W/extra-ready.sh" bash "$PANEL" enrich_od_ready
    grep -q "^enrich_install$" "$W/calls"
}
