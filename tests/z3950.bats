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
# The local gateway: not running, and its install only noted.
gateway_listening() { return 1; }
enrich_install() { echo "called" >> "$W/bridge"; }
CATALOG_NETWORK_OFF="$W/catalog-network.off"
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

zsql() { mysql -N --default-character-set=utf8mb4 "$DB" -e "$1"; }

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
    # An SRU server on 443 speaks HTTPS: Koha needs https:// in the host for that.
    [ "$(zsql "SELECT servertype, port, db, sru_fields FROM z3950servers WHERE host = 'https://services.dnb.de'")" = "$(printf 'sru\t443\tsru/dnb\ttitle=dc.title')" ]
    # An SRU row gets its SRU fields; a Z39.50 server gets none. A row on the
    # local gateway (127.0.0.1:5000) asks for the gateway, whose install moves
    # Koha's rows to it (enrich_register, tested below).
    [ "$(zsql "SELECT servertype, port, db, sru_fields FROM z3950servers WHERE host = '127.0.0.1'")" = "$(printf 'sru\t5000\tsru\ttitle=dc.title,isbn=dc.isbn')" ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = '127.0.0.1'")" = "1" ]
    [ "$(zsql "SELECT servertype, IFNULL(sru_fields,'-'), IFNULL(sru_options,'-') FROM z3950servers WHERE host = 'z3950.ufsc.br'")" = "$(printf 'zed\t\t')" ]
    # The gateway's row asked for the gateway to be installed and started.
    [ "$(cat "$W/bridge")" = "called" ]
    # The invalid ones were refused, nothing of them reached the database.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE servername LIKE 'Bad%'")" = "0" ]
    grep -q "OK .*added to Koha: 4" "$KEI_S/dialogs.log"
    [ "$(cat "$W/results")" = "$(printf 'RESULT added=4\nRESULT existing=1\nRESULT updated=1\nRESULT invalid=2')" ]
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

@test "z3950-add: a target already in Koha is updated, keeping its tick, rank and login" {
    # The librarian unticked LoC and moved it down; its settings are old.
    zsql "UPDATE z3950servers SET checked = 0, \`rank\` = 9, timeout = 3, userid = 'mine', password = 'myPass'
          WHERE host = 'lx2.loc.gov' AND db = 'LCDB'"
    ( printf '%s\t' lx2.loc.gov 210 LCDB MARC21 utf8 'Library of Congress' 2 30 zed '' '' '' ''; printf '\n' ) > "$W/u.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/u.tsv"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'lx2.loc.gov' AND recordtype = 'biblio'")" = "1" ]
    [ "$(zsql "SELECT servername, checked, \`rank\`, syntax, timeout, userid, password FROM z3950servers WHERE host = 'lx2.loc.gov' AND db = 'LCDB'")" = \
      "$(printf 'LIBRARY OF CONGRESS\t0\t9\tMARC21\t30\tmine\tmyPass')" ]
    grep -q "added to Koha: 0" "$KEI_S/dialogs.log"
    # A new login replaces the old one.
    ( printf '%s\t' lx2.loc.gov 210 LCDB MARC21 utf8 'Library of Congress' 2 30 zed new 'n3w' '' ''; printf '\n' ) > "$W/u.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/u.tsv"
    [ "$(zsql "SELECT userid, password, checked FROM z3950servers WHERE host = 'lx2.loc.gov' AND db = 'LCDB'")" = "$(printf 'new\tn3w\t0')" ]
}

@test "z3950-add: a server that moved (same name) is updated in place, no stale row, re-runnable" {
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, timeout, servertype, recordtype, sru_fields, sru_options)
          VALUES ('old.example.org', 5000, 'sru/x', 'Catálogo X', 0, 6, 'USMARC', 'MARC-8', 5, 'zed', 'biblio', NULL, NULL)"
    ( printf '%s\t' sru.koha.nexus 443 sru/x MARC21 utf8 'Catálogo X' 1 15 sru '' '' 'title=dc.title' 'sru=get,sru_version=1.1'; printf '\n'
      printf '%s\t' other.example.org 210 Y USMARC utf8 'Catálogo X' 2 0 zed '' '' '' ''; printf '\n' ) > "$W/m.tsv"
    cp "$W/m.tsv" "$W/m2.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/m.tsv"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'old.example.org'")" = "0" ]
    [ "$(zsql "SELECT host, port, db, syntax, encoding, timeout, servertype, sru_fields, sru_options, checked, \`rank\` FROM z3950servers WHERE db = 'sru/x'")" = \
      "$(printf 'https://sru.koha.nexus\t443\tsru/x\tMARC21\tutf8\t15\tsru\ttitle=dc.title\tsru=get,sru_version=1.1\t0\t6')" ]
    # The second target of that name did not take the same row: it is a new one.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE servername = 'Catálogo X'")" = "2" ]
    [ "$(zsql "SELECT checked, \`rank\` FROM z3950servers WHERE host = 'other.example.org'")" = "$(printf '1\t2')" ]
    before="$(zsql "SELECT * FROM z3950servers ORDER BY id")"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/m2.tsv"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT * FROM z3950servers ORDER BY id")" = "$before" ]
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

@test "z3950-add: a koha.nexus gateway row (SRU, 443) is written https://sru.koha.nexus" {
    ( umask 077
      printf '%s\t' sru.koha.nexus 443 sru/bn MARC21 utf8 'Biblioteca Nacional' 1 1 sru '' '' 'title=dc.title' \
          'sru=get,sru_version=1.1'; printf '\n' ) > "$W/gw.tsv"
    cp "$W/gw.tsv" "$W/gw2.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/gw.tsv"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT host, port, db, servertype FROM z3950servers WHERE db = 'sru/bn'")" = "$(printf 'https://sru.koha.nexus\t443\tsru/bn\tsru')" ]
    # Again: already in Koha, under its https:// host.
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/gw2.tsv"
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE db = 'sru/bn'")" = "1" ]
}

@test "z3950-seed: the Library of Congress and BN authority targets, kept as the librarian left them, re-runnable" {
    # NAF is already there (setup), unticked, with its own name and rank.
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-seed bash "$PANEL" z3950_seed_authorities
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE recordtype = 'authority'")" = "3" ]
    [ "$(zsql "SELECT servername, checked, \`rank\`, syntax, encoding, timeout, servertype FROM z3950servers WHERE recordtype = 'authority' AND db = 'NAF'")" = \
      "$(printf 'LOC AUTHORITIES\t0\t0\tUSMARC\tutf8\t10\tzed')" ]
    [ "$(zsql "SELECT host, port, servername, checked, \`rank\`, syntax, encoding, timeout, servertype FROM z3950servers WHERE recordtype = 'authority' AND db = 'SAF'")" = \
      "$(printf 'lx2.loc.gov\t210\tBIBLIOTECA DOS ASSUNTOS DO CONGRESSO\t1\t2\tUSMARC\tutf8\t10\tzed')" ]
    # The BN authority database on the SRU gateway (authority records built from the BN catalogue).
    [ "$(zsql "SELECT host, port, servername, checked, \`rank\`, syntax, encoding, timeout, servertype, sru_options FROM z3950servers WHERE recordtype = 'authority' AND db = 'sru/bn-aut'")" = \
      "$(printf 'https://sru.koha.nexus\t443\tBIBLIOTECA NACIONAL (AUTORIDADES)\t1\t3\tMARC21\tutf8\t30\tsru\tsru=get,sru_version=1.1')" ]
    [ "$(zsql "SELECT sru_fields FROM z3950servers WHERE db = 'sru/bn-aut'")" = \
      "nameany=dc.creator,authorany=dc.creator,authorpersonal=bath.personalName,authorcorp=bath.corporateName,authormeetingcon=bath.conferenceName,srchany=cql.serverChoice" ]
    # The catalogue (biblio) rows are untouched.
    [ "$(zsql "SELECT COUNT(*), MAX(timeout) FROM z3950servers WHERE recordtype = 'biblio'")" = "$(printf '1\t0')" ]
    before="$(zsql "SELECT * FROM z3950servers ORDER BY id")"
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-seed bash "$PANEL" z3950_seed_authorities
    [ "$(zsql "SELECT * FROM z3950servers ORDER BY id")" = "$before" ]
    # On a Koha without them: all three inserted, ticked, NAF first.
    zsql "DELETE FROM z3950servers WHERE recordtype = 'authority'"
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-seed bash "$PANEL" z3950_seed_authorities
    [ "$(zsql "SELECT db, servername, checked, \`rank\` FROM z3950servers WHERE recordtype = 'authority' ORDER BY \`rank\`")" = \
      "$(printf 'NAF\tBIBLIOTECA DOS NOMES DO CONGRESSO\t1\t1\nSAF\tBIBLIOTECA DOS ASSUNTOS DO CONGRESSO\t1\t2\nsru/bn-aut\tBIBLIOTECA NACIONAL (AUTORIDADES)\t1\t3')" ]
}

@test "Catalog Network SQL: an older row is updated in place, keeping its tick and rank, re-runnable" {
    SQL="$BATS_TEST_DIRNAME/../catalog-network/deploy/koha-z3950servers.sql"
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, servertype, recordtype) VALUES
      ('http://10.0.0.5', 8088, 'old', 'Rede koha.nexus (Catalogação Compartilhada)', 0, 4, 'USMARC', 'utf8', 'zed', 'biblio')"
    mysql --default-character-set=utf8mb4 "$DB" < "$SQL"
    [ "$(zsql "SELECT host, port, db, syntax, servertype, timeout, checked, \`rank\` FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'")" = \
      "$(printf 'https://catalog.koha.nexus\t443\tsru\tMARC21\tsru\t15\t0\t4')" ]
    before="$(zsql "SELECT * FROM z3950servers ORDER BY id")"
    mysql --default-character-set=utf8mb4 "$DB" < "$SQL"
    [ "$(zsql "SELECT * FROM z3950servers ORDER BY id")" = "$before" ]
    # On a Koha without it: inserted, ticked.
    zsql "DELETE FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'"
    mysql --default-character-set=utf8mb4 "$DB" < "$SQL"
    [ "$(zsql "SELECT COUNT(*), MIN(checked) FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'")" = "$(printf '1\t1')" ]
}

@test "panel export SQL: loads into another Koha, updates what is there, re-runnable" {
    zsql "UPDATE z3950servers SET checked = 0, \`rank\` = 8, syntax = 'UNIMARC' WHERE host = 'lx2.loc.gov' AND recordtype = 'biblio'"
    PYTHONPATH="$BATS_TEST_DIRNAME/../panel" python3 -c '
from kei_panel.z3950 import Target, to_koha_sql
print(to_koha_sql([Target("LoC", "lx2.loc.gov", 210, "LCDB", syntax="MARC21"),
                   Target("DNB", "services.dnb.de", 443, "sru/dnb", kind="sru")]), end="")' > "$W/export.sql"
    mysql --default-character-set=utf8mb4 "$DB" < "$W/export.sql"
    [ "$(zsql "SELECT servername, syntax, checked, \`rank\` FROM z3950servers WHERE host = 'lx2.loc.gov' AND recordtype = 'biblio'")" = \
      "$(printf 'LIBRARY OF CONGRESS\tMARC21\t0\t8')" ]
    # An SRU server on 443 is written as config.sh writes it: https:// in the host.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'https://services.dnb.de'")" = "1" ]
    before="$(zsql "SELECT * FROM z3950servers ORDER BY id")"
    mysql --default-character-set=utf8mb4 "$DB" < "$W/export.sql"
    [ "$(zsql "SELECT * FROM z3950servers ORDER BY id")" = "$before" ]
}

@test "z3950-list: Koha's targets, the catalogue ones first, then the authority ones" {
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-list bash "$PANEL" z3950_rows
    [ "$status" -eq 0 ]
    [ "$output" = "$(printf 'lx2.loc.gov\t210\tLCDB\tLIBRARY OF CONGRESS\tbiblio\t1\nlx2.loc.gov\t210\tNAF\tLOC AUTHORITIES\tauthority\t0')" ]
}

@test "z3950-check: ticks and unticks rows Koha has for the search, https:// SRU rows too; adds and deletes nothing" {
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, servertype, recordtype)
          VALUES ('https://sru.koha.nexus', 443, 'sru/loc', 'LoC (gateway)', 0, 500, 'MARC21', 'utf8', 'sru', 'biblio')"
    before=$(zsql "SELECT COUNT(*) FROM z3950servers")
    ( umask 077
      printf '%s\t' lx2.loc.gov 210 LCDB biblio 0; printf '\n'
      printf '%s\t' lx2.loc.gov 210 NAF authority 1; printf '\n'
      printf '%s\t' sru.koha.nexus 443 sru/loc biblio 1; printf '\n'
      printf '%s\t' z3950.ufsc.br 210 Default biblio 1; printf '\n'
      printf '%s\t' "x'; DROP TABLE z3950servers; --" 210 x biblio 1; printf '\n'
      printf '%s\t' lx2.loc.gov 210 LCDB biblio 7; printf '\n'
    ) > "$W/check.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_check "$W/check.tsv"
    echo "$output"; cat "$KEI_S/dialogs.log"
    [ "$status" -eq 0 ]
    [ ! -e "$W/check.tsv" ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers")" = "$before" ]
    [ "$(zsql "SELECT checked FROM z3950servers WHERE db = 'LCDB'")" = "0" ]
    [ "$(zsql "SELECT checked FROM z3950servers WHERE db = 'NAF'")" = "1" ]
    [ "$(zsql "SELECT checked FROM z3950servers WHERE db = 'sru/loc'")" = "1" ]
    [ "$(cat "$W/results")" = "$(printf 'RESULT ticked=2\nRESULT unticked=1\nRESULT missing=1\nRESULT invalid=2')" ]
    grep -q "2 server(s) ticked, 1 unticked" "$KEI_S/dialogs.log"
    grep -q "^        z3950-check) " "$KEI_REPO/installer"
}

@test "z3950: the panel knows the tasks" {
    grep -q '^        z3950-list)' "$KEI_REPO/installer"
    grep -q '^        z3950-add) ' "$KEI_REPO/installer"
    grep -q '^        z3950-seed) ' "$KEI_REPO/installer"
    grep -q '^        z3950-sync) ' "$KEI_REPO/installer"
}

@test "z3950-seed: the Biblioteca Nacional's dead Z39.50 rows are unticked; one of the same name moves in place" {
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, timeout, servertype, recordtype)
          VALUES ('162.214.168.248', 210, 'BNAUT', 'BIBLIOTECA NACIONAL (AUTORIDADES)', 1, 5, 'USMARC', 'utf8', 30, 'zed', 'authority'),
                 ('200.20.12.18', 210, 'AUT', 'Biblioteca Nacional autoridades (antigo)', 1, 4, 'USMARC', 'utf8', 30, 'zed', 'authority')"
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-seed bash "$PANEL" z3950_seed_authorities
    [ "$status" -eq 0 ]
    # Same name and record type: moved to the gateway in place, keeping its tick and rank.
    [ "$(zsql "SELECT host, port, db, servertype, syntax, timeout, checked, \`rank\` FROM z3950servers WHERE servername = 'BIBLIOTECA NACIONAL (AUTORIDADES)'")" = \
      "$(printf 'https://sru.koha.nexus\t443\tsru/bn-aut\tsru\tMARC21\t30\t1\t5')" ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE db = 'sru/bn-aut'")" = "1" ]
    # Another name on a dead address: kept, unticked (no more 30 s waits).
    [ "$(zsql "SELECT checked, \`rank\` FROM z3950servers WHERE host = '200.20.12.18'")" = "$(printf '0\t4')" ]
}

# The panel's catalogue as "Update server settings" sends it (host ... sru_options recordtype).
catalogue_tsv() {
    PYTHONPATH="$BATS_TEST_DIRNAME/../panel" python3 -c '
from kei_panel import z3950
print(z3950.add_file_text(z3950.sync_targets(z3950.load_curated(), set()), {}), end="")'
}

@test "z3950-sync: refreshes every row Koha has, adds only the missing authority files, counts both" {
    # A gateway row with old settings, the librarian's tick and rank; a stale BN authority row with SRU fields missing.
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, timeout, servertype, recordtype, sru_fields, sru_options)
          VALUES ('http://137.131.205.31', 5000, 'sru/bn', 'Fundação Biblioteca Nacional (BN)', 0, 7, 'USMARC', 'MARC-8', 5, 'sru', 'biblio', 'title=dc.title', ''),
                 ('162.214.168.248', 210, 'BNAUT', 'BN antiga', 1, 9, 'USMARC', 'utf8', 30, 'zed', 'authority', NULL, NULL)"
    catalogue_tsv > "$W/all.tsv"
    [ "$(wc -l < "$W/all.tsv")" -ge 75 ]
    cp "$W/all.tsv" "$W/all2.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/all.tsv" sync
    echo "$output"; cat "$W/results"
    [ "$status" -eq 0 ]
    [ ! -e "$W/all.tsv" ]
    # Found by name, moved to the gateway on the Cloudflare tunnel, tick and rank kept.
    [ "$(zsql "SELECT host, port, syntax, encoding, timeout, sru_options, checked, \`rank\` FROM z3950servers WHERE db = 'sru/bn'")" = \
      "$(printf 'https://sru.koha.nexus\t443\tMARC21\tutf8\t15\tsru=get,sru_version=1.1\t0\t7')" ]
    [ "$(zsql "SELECT sru_fields FROM z3950servers WHERE db = 'sru/bn'")" = \
      "title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,srchany=cql.serverChoice" ]
    # No catalogue server Koha did not have was added: still 2 biblio rows (LoC LCDB and BN).
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE recordtype = 'biblio'")" = "2" ]
    # The authority files: NAF updated (tick and rank kept), SAF, BN and the gateway's headings added; the dead BN row unticked.
    [ "$(zsql "SELECT db, servername, checked, \`rank\`, timeout FROM z3950servers WHERE recordtype = 'authority' AND host <> '162.214.168.248' ORDER BY db")" = \
      "$(printf 'NAF\tLOC AUTHORITIES\t0\t0\t10\nSAF\tBIBLIOTECA DOS ASSUNTOS DO CONGRESSO\t1\t2\t10\nsru/bn-aut\tBIBLIOTECA NACIONAL (AUTORIDADES)\t1\t3\t30\nsru/_union-aut\tKOHA.NEXUS (AUTORIDADES)\t1\t0\t15')" ]
    [ "$(zsql "SELECT checked FROM z3950servers WHERE host = '162.214.168.248'")" = "0" ]
    # BN, NAF and LCDB (a direct server in the list) updated.
    [ "$(cat "$W/results")" = "$(printf 'RESULT added=3\nRESULT updated=3\nRESULT unchecked=1\nRESULT invalid=0')" ]
    grep -q "OK .*settings updated.*Added: 3.*Updated: 3" "$KEI_S/dialogs.log"
    # Again: nothing to add, nothing to change.
    rm -f "$W/results"
    before="$(zsql "SELECT * FROM z3950servers ORDER BY id")"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/all2.tsv" sync
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT * FROM z3950servers ORDER BY id")" = "$before" ]
    [ "$(cat "$W/results")" = "$(printf 'RESULT added=0\nRESULT updated=0\nRESULT unchecked=0\nRESULT invalid=0')" ]
    # No bridge was installed for it.
    [ ! -e "$W/bridge" ]
}

@test "z3950-add: an authority target matches only authority rows, by address or name, and gets its SRU fields" {
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, timeout, servertype, recordtype)
          VALUES ('162.214.168.248', 210, 'BNAUT', 'BIBLIOTECA NACIONAL (AUTORIDADES)', 0, 6, 'USMARC', 'utf8', 30, 'zed', 'authority'),
                 ('lx2.loc.gov', 210, 'SAF', 'BIBLIOTECA NACIONAL (AUTORIDADES)', 1, 1, 'USMARC', 'utf8', 0, 'zed', 'biblio')"
    ( printf '%s\t' sru.koha.nexus 443 sru/bn-aut MARC21 utf8 'BIBLIOTECA NACIONAL (AUTORIDADES)' 3 30 sru '' '' \
          'nameany=dc.creator,srchany=cql.serverChoice' 'sru=get,sru_version=1.1' authority; printf '\n' ) > "$W/a.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/a.tsv"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT host, port, db, servertype, syntax, sru_fields, sru_options, checked, \`rank\` FROM z3950servers WHERE recordtype = 'authority' AND servername LIKE 'BIBLIOTECA NACIONAL%'")" = \
      "$(printf 'https://sru.koha.nexus\t443\tsru/bn-aut\tsru\tMARC21\tnameany=dc.creator,srchany=cql.serverChoice\tsru=get,sru_version=1.1\t0\t6')" ]
    # The biblio row of the same name is not touched.
    [ "$(zsql "SELECT host, db FROM z3950servers WHERE recordtype = 'biblio' AND servername LIKE 'BIBLIOTECA NACIONAL%'")" = "$(printf 'lx2.loc.gov\tSAF')" ]
}

@test "z3950-add: no gateway install without a row on it" {
    ( printf '%s\t' z3950.ufsc.br 210 Default USMARC utf8 UFSC 1 0 zed '' '' '' ''; printf '\n' ) > "$W/u.tsv"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" z3950_add "$W/u.tsv"
    [ "$status" -eq 0 ]
    [ ! -e "$W/bridge" ]
}

@test "enrichment: the panel tasks exist, the units start on boot and the bridges are retired" {
    grep -q '^        enrich-install|sru-bridge|pergamum-bridge) enrich_install ;;' "$KEI_REPO/installer"
    grep -q '^        enrich-update)' "$KEI_REPO/installer"
    grep -q 'ExecStart=${ENRICH_DIR}/.venv/bin/python -m nexus_gateway serve' "$KEI_REPO/installer"
    grep -q 'ExecStart=${ENRICH_DIR}/.venv/bin/python -m nexus_gateway update' "$KEI_REPO/installer"
    grep -q '^CPUQuota=25%$' "$KEI_REPO/installer"
    grep -q '^RETIRED_BRIDGE_UNITS="koha-zeus-sru koha-pergamum-sru"$' "$KEI_REPO/installer"
    ! grep -q 'sru_bridge_install' "$KEI_REPO/installer"
}

@test "enrichment: Koha's rows go to sru.koha.nexus:443, sru/_union and sru/all ticked, the shared catalogue added, re-runnable" {
    # The gateway's real koha-sql, through a stand-in venv python.
    mkdir -p "$W/enrich/.venv/bin"
    printf '#!/bin/sh\nPYTHONPATH=%s exec python3 "$@"\n' "$KEI_REPO/enrichment" > "$W/enrich/.venv/bin/python"
    chmod +x "$W/enrich/.venv/bin/python"
    echo "ENRICH_DIR=$W/enrich" >> "$W/extra.sh"
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, servertype, recordtype)
          VALUES ('http://137.131.205.31', 5000, 'sru/bn', 'BN', 1, 1, 'MARC21', 'utf8', 'sru', 'biblio'),
                 ('127.0.0.1', 5000, 'sru/usp', 'USP', 1, 2, 'MARC21', 'utf8', 'sru', 'biblio'),
                 ('127.0.0.1', 5000, 'sru/_union-aut', 'KOHA.NEXUS (AUTORIDADES)', 1, 6, 'MARC21', 'utf8', 'sru', 'authority'),
                 ('127.0.0.1', 8088, 'sru', 'Rede koha.nexus', 1, 7, 'MARC21', 'utf8', 'sru', 'biblio'),
                 ('10.0.0.60', 5001, 'pergamum', 'Rede', 0, 3, 'MARC21', 'utf8', 'sru', 'biblio'),
                 ('127.0.0.1', 5000, 'sru', 'Catálogo Zeus (UFSC bridge, SRU)', 1, 4, 'MARC21', 'utf8', 'sru', 'biblio'),
                 ('127.0.0.1', 5006, 'sru', 'Catálogo Rede Pergamum (CRP bridge, SRU)', 1, 5, 'MARC21', 'utf8', 'sru', 'biblio'),
                 ('https://sru.koha.nexus', 443, 'sru/bn-aut', 'BN AUT', 1, 3, 'MARC21', 'utf8', 'sru', 'authority')"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" enrich_register
    echo "$output"; cat "$W/logs/"* 2>/dev/null || true
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE recordtype = 'biblio' AND host = 'https://sru.koha.nexus' AND port = 443 AND db LIKE 'sru/%'")" = "74" ]
    # sru/_union and Rede Pergamum (sru/all) are the gateway's ticked rows.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'https://sru.koha.nexus' AND recordtype = 'biblio' AND checked = 1")" = "2" ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'https://sru.koha.nexus' AND recordtype = 'biblio' AND checked = 1 AND db IN ('sru/_union', 'sru/all')")" = "2" ]
    # The local gateway's and the VPS IP's rows moved (keeping their rank), the bridges' rows are gone.
    [ "$(zsql "SELECT \`rank\` FROM z3950servers WHERE db = 'sru/bn'")" = "1" ]
    [ "$(zsql "SELECT host, port, \`rank\` FROM z3950servers WHERE db = 'sru/usp'")" = "$(printf 'https://sru.koha.nexus\t443\t2')" ]
    [ "$(zsql "SELECT host, port, \`rank\` FROM z3950servers WHERE db = 'sru/_union-aut'")" = "$(printf 'https://sru.koha.nexus\t443\t6')" ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE recordtype = 'biblio' AND (host IN ('10.0.0.60', 'http://137.131.205.31') OR (host = '127.0.0.1' AND port IN (5000, 5006)) OR db = 'sru') AND host <> 'https://catalog.koha.nexus'")" = "1" ]
    # The Catalog Network row (127.0.0.1:8088) is not the gateway's: left alone.
    [ "$(zsql "SELECT port FROM z3950servers WHERE servername = 'Rede koha.nexus'")" = "8088" ]
    # The shared catalogue's own row is added, ticked, as the panel's switch adds it.
    [ "$(zsql "SELECT host, port, db, checked FROM z3950servers WHERE servername = 'Rede koha.nexus (Catalogação Compartilhada)'")" = \
      "$(printf 'https://catalog.koha.nexus\t443\tsru\t1')" ]
    [ "$(zsql "SELECT db FROM z3950servers WHERE db = 'sru/all'")" = "sru/all" ]
    # The librarian's other servers and the authority rows are untouched.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE host = 'lx2.loc.gov'")" = "2" ]
    [ "$(zsql "SELECT host, checked FROM z3950servers WHERE db = 'sru/bn-aut'")" = "$(printf 'https://sru.koha.nexus\t1')" ]
    grep -q "koha-target=set" "$W/results"
    before="$(zsql "SELECT * FROM z3950servers ORDER BY id")"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" enrich_register
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT * FROM z3950servers ORDER BY id")" = "$before" ]
}

@test "enrich_register: the shared catalogue turned off in the panel is not added back" {
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=catalog-network bash "$PANEL" catalog_network on "https://catalog.koha.nexus/sru"
    [ "$status" -eq 0 ] && [ ! -e "$W/catalog-network.off" ]
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=catalog-network bash "$PANEL" catalog_network off
    [ "$status" -eq 0 ] && [ -e "$W/catalog-network.off" ]
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" catalog_network_auto
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'")" = "0" ]
    rm -f "$W/catalog-network.off"
    run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" catalog_network_auto
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT host, port, db, checked FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'")" = \
      "$(printf 'https://catalog.koha.nexus\t443\tsru\t1')" ]
}

# ---------------------------------------------------------------------
# The screen's top and middle: this Koha's own Z39.50/SRU server and the
# koha.nexus Catalog Network row.
# ---------------------------------------------------------------------
daemon_extra() {
    mkdir -p "$W/z3950"
    printf '<yazgfs>\n  <listen id="public">tcp:@:2111</listen>\n</yazgfs>\n' > "$W/z3950/config.xml"
    cat >> "$W/extra.sh" <<SH
require_koha() { return 0; }
KEI_Z3950_DIR="$W/z3950"
z3950_daemon_running() { [ -e "$W/running" ]; }
koha_ctl() {
    echo "\$*" >> "$W/calls"
    case "\$*" in
        *--start*) touch "$W/running" ;;
        *--stop*) rm -f "$W/running" ;;
        *--disable*) rm -rf "$W/z3950" ;;    # as if Koha took the settings away
    esac
}
ufw() { echo "ufw \$*" >> "$W/calls"; }
systemctl() { echo "systemctl \$*" >> "$W/calls"; return 1; }
SH
}

@test "z3950-daemon: on starts the responder and opens its port; off stops it, closes it, keeps its settings" {
    daemon_extra
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-daemon bash "$PANEL" z3950_daemon on
    echo "$output"; cat "$W/calls"
    [ "$status" -eq 0 ]
    grep -q -- "--enable" "$W/calls"
    grep -q -- "--start" "$W/calls"
    grep -q "ufw allow 2111/tcp" "$W/calls"
    grep -q "RESULT daemon=running" "$W/results"
    grep -q "RESULT port=2111" "$W/results"
    grep -q "OK .*port 2111" "$KEI_S/dialogs.log"

    : > "$W/results"
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-daemon bash "$PANEL" z3950_daemon off
    [ "$status" -eq 0 ]
    grep -q -- "--stop" "$W/calls"
    grep -q -- "--disable" "$W/calls"
    grep -q "ufw delete allow 2111/tcp" "$W/calls"
    grep -q "RESULT daemon=stopped" "$W/results"
    # Koha's --disable removed the settings: a copy waits for "on".
    [ ! -e "$W/z3950" ] && [ -f "$W/z3950.kei-off/config.xml" ]

    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-daemon bash "$PANEL" z3950_daemon on
    [ "$status" -eq 0 ]
    [ -f "$W/z3950/config.xml" ] && [ ! -e "$W/z3950.kei-off" ]
    [ "$(grep -c "ufw allow 2111/tcp" "$W/calls")" = 2 ]
}

@test "catalog-network: on adds the shared catalogue as SRU (HTTPS, MARC21, utf8), again updates it, off removes it" {
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=catalog-network bash "$PANEL" catalog_network on "https://catalog.koha.nexus/sru"
    echo "$output"; cat "$KEI_S/dialogs.log"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT host, port, db, syntax, encoding, servertype, checked, timeout, sru_options FROM z3950servers WHERE servername = 'Rede koha.nexus (Catalogação Compartilhada)'")" = \
      "$(printf 'https://catalog.koha.nexus\t443\tsru\tMARC21\tutf8\tsru\t1\t15\tsru=get,sru_version=1.1')" ]
    [ "$(zsql "SELECT sru_fields FROM z3950servers WHERE host = 'https://catalog.koha.nexus'")" = \
      "title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,srchany=cql.serverChoice" ]
    grep -q "RESULT network=on" "$W/results"
    grep -q "RESULT network_url=https://catalog.koha.nexus:443/sru" "$W/results"

    # Again at another address: the same row moves, keeping the librarian's
    # tick and rank.
    zsql "UPDATE z3950servers SET checked = 0, \`rank\` = 5 WHERE servername LIKE 'Rede koha.nexus%'"
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=catalog-network bash "$PANEL" catalog_network on "http://10.0.0.5:8088/"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'")" = "1" ]
    [ "$(zsql "SELECT host, port, db, checked, \`rank\` FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'")" = "$(printf 'http://10.0.0.5\t8088\tsru\t0\t5')" ]

    : > "$W/results"
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-server-status bash "$PANEL" z3950_server_status
    grep -q "RESULT network=on" "$W/results"
    grep -q "RESULT network_url=http://10.0.0.5:8088/sru" "$W/results"

    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=catalog-network bash "$PANEL" catalog_network off
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE servername LIKE 'Rede koha.nexus%'")" = "0" ]
    # The other targets are untouched.
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers")" = "2" ]
}

@test "catalog-network: an address that is not http(s) changes nothing" {
    for bad in "catalog.koha.nexus" "https://x.org/sru'; DROP TABLE z3950servers; --" "ftp://x.org/sru" "https://x.org:99999/sru"; do
        run env KEI_EXTRA="$W/extra.sh" KEI_TASK=catalog-network bash "$PANEL" catalog_network on "$bad"
        [ "$status" -eq 1 ]
    done
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers")" = "2" ]
    grep -q "ERROR .*not valid" "$KEI_S/dialogs.log"
}

@test "z3950-server-status: the responder's state, port and no network row" {
    daemon_extra
    touch "$W/running"
    run env KEI_EXTRA="$W/extra.sh" KEI_TASK=z3950-server-status bash "$PANEL" z3950_server_status
    [ "$status" -eq 0 ]
    [ "$(cat "$W/results")" = "$(printf 'RESULT daemon=running\nRESULT port=2111\nRESULT network=off')" ]
}

@test "z3950: the panel knows the server and network tasks" {
    grep -q '^        z3950-server-status)' "$KEI_REPO/installer"
    grep -q '^        z3950-daemon) ' "$KEI_REPO/installer"
    grep -q '^        catalog-network)' "$KEI_REPO/installer"
}

@test "docs/sql/koha-authority-servers.sql: what the installer seeds, loads in Koha, re-runnable" {
    SQL="$BATS_TEST_DIRNAME/../docs/sql/koha-authority-servers.sql"
    gen="$( { bash "$PANEL" z3950_auth_rows | bash "$PANEL" z3950_upsert_sql add; bash "$PANEL" z3950_dead_sql; } 2>/dev/null)"
    [ "$(grep -v -e '^--' -e '^SET NAMES' -e '^SELECT @kei_added' "$SQL")" = "$gen" ]
    zsql "INSERT INTO z3950servers (host, port, db, servername, checked, \`rank\`, syntax, encoding, timeout, servertype, recordtype)
          VALUES ('200.20.12.18', 210, 'AUT', 'BN velha', 1, 4, 'USMARC', 'utf8', 30, 'zed', 'authority')"
    mysql --default-character-set=utf8mb4 "$DB" < "$SQL" > /dev/null
    # Again: nothing added, changed or unticked.
    run bash -c "mysql -N --default-character-set=utf8mb4 '$DB' < '$SQL'"
    [ "$status" -eq 0 ]
    [ "$(zsql "SELECT COUNT(*) FROM z3950servers WHERE recordtype = 'authority' AND checked = 1")" = "2" ]
    [ "$(zsql "SELECT db FROM z3950servers WHERE recordtype = 'authority' AND checked = 1 ORDER BY db")" = "$(printf 'SAF\nsru/bn-aut')" ]
    [ "$(zsql "SELECT checked FROM z3950servers WHERE host = '200.20.12.18'")" = "0" ]
    [ "$output" = "$(printf '0\t0\t0')" ]
}
