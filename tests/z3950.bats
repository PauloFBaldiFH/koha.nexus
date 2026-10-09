#!/usr/bin/env bats
# Z39.50 / SRU servers (section 39): the panel's screen writes a private
# list of the chosen targets and `config.sh --task z3950-add FILE` puts
# them in Koha's z3950servers table, on a real MariaDB (the table as in
# Koha's kohastructure.sql). The scan itself is Python: panel/tests/test_z3950.py.

setup_file() {
    load lib/common
    kei_start_mariadb
    mysql -e "CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4;"
}

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    rm -f "$KEI_S/dialogs.log"
    mysql "$DB" -e "DROP TABLE IF EXISTS z3950servers;
CREATE TABLE z3950servers (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, host varchar(255) DEFAULT NULL,
  port int(11) DEFAULT NULL, db varchar(255) DEFAULT NULL, userid varchar(255) DEFAULT NULL,
  password varchar(255) DEFAULT NULL, servername longtext NOT NULL, checked smallint(6) DEFAULT NULL,
  \`rank\` int(11) DEFAULT NULL, syntax varchar(80) DEFAULT NULL, timeout int(11) NOT NULL DEFAULT 0,
  servertype enum('zed','sru') NOT NULL DEFAULT 'zed', encoding text DEFAULT NULL,
  recordtype enum('authority','biblio') NOT NULL DEFAULT 'biblio', sru_options varchar(255) DEFAULT NULL,
  sru_fields longtext DEFAULT NULL, add_xslt longtext DEFAULT NULL, attributes varchar(255) DEFAULT NULL)
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, recordtype)
  VALUES ('lx2.loc.gov', 210, 'LCDB', 'LIBRARY OF CONGRESS', 1, 1, 'USMARC', 'utf8', 'biblio'),
         ('lx2.loc.gov', 210, 'NAF', 'LOC AUTHORITIES', 0, 0, 'USMARC', 'utf8', 'authority');"
    cat > "$W/extra.sh" <<SH
SYS_LANG=en
kei_result() { printf 'RESULT %s=%s\n' "\$1" "\$2" >> "$W/results"; }
require_database() { return 0; }
is_koha_installed() { return 0; }
TOOLS_LOG_DIR="$W/logs"
# The Zeus bridge: not running, and its install only noted.
sru_bridge_listening() { return 1; }
sru_bridge_install() { echo called >> "$W/bridge"; }
SH
    ( umask 077
      printf '%s\t' lx2.loc.gov 210 LCDB USMARC utf8 'Library of Congress' 3 0 zed '' '' ''; printf '\n'
      printf '%s\t' z3950.bnf.fr 2211 TOUT-ANA1-UTF8 UNIMARC utf8 "BnF l'officielle" 1 0 zed Z3950 'Pa\ss'"'"'w0rd' ''; printf '\n'
      printf '%s\t' services.dnb.de 443 sru/dnb USMARC utf8 'DNB (SRU)' 2 0 sru '' '' 'title=dc.title'; printf '\n'
      printf '%s\t' 127.0.0.1 5000 sru USMARC utf8 'Catálogo Zeus' 0 0 sru '' '' \
          'title=dc.title,isbn=dc.isbn' 'sru_version=1.1,schema=marcxml'; printf '\n'
      printf '%s\t' z3950.ufsc.br 210 Default USMARC utf8 'UFSC' 4 0 zed '' '' 'title=x' 'sru_version=1.1'; printf '\n'
      printf '%s\t' 'bad host;drop' 210 x USMARC utf8 'Bad' 4 0 zed '' '' ''; printf '\n'
      printf '%s\t' ok.example.org 210 x WEIRDMARC utf8 'Bad syntax' 5 0 zed '' '' ''; printf '\n'
    ) > "$W/add.tsv"
}

zsql() { mysql -N "$DB" -e "$1"; }

@test "z3950-add: valid targets go in once, checked, ranked; the list file is deleted" {
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/add.tsv"
    echo "$output"; cat "$KEI_S/dialogs.log"
    [ "$status" -eq 0 ]
    [ ! -e "$W/add.tsv" ]
    # LoC was already there (same host, port and database): not added twice.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE recordtype = 'biblio'")" = "5" ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'lx2.loc.gov' AND db = 'LCDB'")" = "1" ]
    [ "$(mysql -N --raw "$DB" -e "SELECT password FROM z3950servers WHERE host = 'z3950.bnf.fr'")" = 'Pa\ss'"'"'w0rd' ]
    [ "$(zsql "SELECT servername, checked, \`rank\` FROM z3950servers WHERE host = 'z3950.bnf.fr'")" = "$(printf "BnF l'officielle\t1\t1")" ]
    [ "$(zsql "SELECT servertype, port, db, sru_fields FROM z3950servers WHERE host = 'services.dnb.de'")" = "$(printf 'sru\t443\tsru/dnb\ttitle=dc.title')" ]
    # The Zeus bridge gets its SRU fields and options; a Z39.50 server gets none.
    # ...and then the bridge's own row replaced it: MARC21, GET, 15 s.
    [ "$(zsql "SELECT servertype, port, db, syntax, timeout, sru_fields, sru_options FROM z3950servers WHERE host = '127.0.0.1'")" = "$(printf 'sru\t5000\tsru\tMARC21\t15\ttitle=dc.title,isbn=dc.isbn,srchany=cql.serverChoice\tsru=get,sru_version=1.1')" ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = '127.0.0.1'")" = "1" ]
    # The UFSC Z39.50 server does not answer: kept, but unticked.
    [ "$(zsql "SELECT servertype, IFNULL(sru_fields,'-'), IFNULL(sru_options,'-'), checked FROM z3950servers WHERE host = 'z3950.ufsc.br'")" = "$(printf 'zed\t\t\t0')" ]
    # The Zeus row asked for its bridge to be installed and started.
    [ "$(cat "$W/bridge")" = called ]
    # The invalid ones were refused, nothing of them reached the database.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE servername LIKE 'Bad%'")" = "0" ]
    grep -q "OK .*added to Koha: 4" "$KEI_S/dialogs.log"
    [ "$(cat "$W/results")" = "$(printf 'RESULT koha-target=set\nRESULT added=4\nRESULT existing=1\nRESULT invalid=2')" ]
    grep -q "Already in Koha: 1" "$KEI_S/dialogs.log"
    # The password is in no log, and no SQL file is left behind.
    ! grep -rq "w0rd" "$W/logs" /var/log/koha-easy-install 2>/dev/null
    ! grep -q "w0rd" "$KEI_S/dialogs.log"
    [ -z "$(find /tmp -maxdepth 2 -name 'z3950-add.sql' 2>/dev/null)" ]
}

@test "z3950-add: a second run adds nothing" {
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/add.tsv"
    [ "$status" -eq 0 ]
    ( umask 077
      printf '%s\t' z3950.bnf.fr 2211 TOUT-ANA1-UTF8 UNIMARC utf8 BnF 1 0 zed '' '' ''; printf '\n' ) > "$W/again.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/again.tsv"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'z3950.bnf.fr'")" = "1" ]
    grep -q "added to Koha: 0" "$KEI_S/dialogs.log"
}

@test "z3950-add: a list with nothing valid changes nothing and says why" {
    printf 'not a host\t99999\n' > "$W/bad.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/bad.tsv"
    [ "$status" -eq 1 ]
    [ ! -e "$W/bad.tsv" ]
    grep -q "ERROR .*valid address" "$KEI_S/dialogs.log"
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers")" = "2" ]
}

@test "z3950-add: a database error is logged with the passwords masked" {
    zsql "ALTER TABLE z3950servers DROP COLUMN sru_fields"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' z.example.org 210 x USMARC utf8 X 1 0 zed me 'S3cr3tPass' '' > "$W/e.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/e.tsv"
    [ "$status" -eq 1 ]
    grep -q "ERROR .*did not take the servers" "$KEI_S/dialogs.log"
    grep -rq "sru_fields" "$W/logs"
    ! grep -rq "S3cr3tPass" "$W/logs" "$KEI_S/dialogs.log"
}

@test "z3950-list: Koha's catalogue targets, no authority ones" {
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-list bash "$PANEL" z3950_rows
    [ "$status" -eq 0 ]
    [ "$output" = "$(printf 'lx2.loc.gov\t210\tLCDB\tLIBRARY OF CONGRESS')" ]
}

@test "z3950: the panel knows the tasks" {
    grep -q '^        z3950-list)' "$KEI_REPO/installer"
    grep -q '^        z3950-add) ' "$KEI_REPO/installer"
}

@test "z3950-add: no bridge install without a Zeus row" {
    ( printf '%s\t' z3950.ufsc.br 210 Default USMARC utf8 UFSC 1 0 zed '' '' '' ''; printf '\n' ) > "$W/u.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/u.tsv"
    [ "$status" -eq 0 ]
    [ ! -e "$W/bridge" ]
}

@test "sru-bridge: the panel task exists and the unit starts the bridge on boot" {
    grep -q '^        sru-bridge)' "$KEI_REPO/installer"
    grep -q 'WantedBy=multi-user.target' "$KEI_REPO/installer"
    grep -q 'ExecStart=${SRU_BRIDGE_DIR}/.venv/bin/python -m zeus_sru' "$KEI_REPO/installer"
}
