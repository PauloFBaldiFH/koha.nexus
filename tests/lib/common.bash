# Shared helpers for the bats test battery (see tests/README.md).
# shellcheck shell=bash
KEI_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KEI_S=/run/kei-mock
PANEL="$KEI_REPO/tests/lib/panel.sh"
# The battery describes a Linux server, even when it runs inside WSL;
# tests/wsl_mode.bats sets the platform per test.
export KEI_PLATFORM_OVERRIDE="${KEI_PLATFORM_OVERRIDE:-linux}"
# Shell used for the panel and the generated scripts: KEI_BASH=/path/to/bash
# runs the battery with another Bash release (e.g. 5.1 of Debian 11 / Ubuntu 22.04).
KEI_SH="${KEI_BASH:-bash}"
DB=koha_library
FIX="${BATS_FILE_TMPDIR:-/tmp}/fixtures"

# ---------------------------------------------------------------------
# Synthetic Koha catalog: the core tables the panel checks, the zebraqueue
# and background_jobs queues, and fillers up to 60 tables (a real Koha has
# ~300). Random text keeps the dumps from compressing to nothing.
# ---------------------------------------------------------------------
kei_schema_sql() {
    cat <<'SQL'
CREATE TABLE branches (branchcode varchar(10) NOT NULL PRIMARY KEY, branchname longtext NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE categories (categorycode varchar(10) NOT NULL PRIMARY KEY, description longtext, category_type varchar(1) NOT NULL DEFAULT 'A') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE borrowers (borrowernumber int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, cardnumber varchar(32) UNIQUE, surname longtext, firstname mediumtext, branchcode varchar(10) NOT NULL, categorycode varchar(10) NOT NULL, userid varchar(75) UNIQUE, password varchar(60), flags bigint(11)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE biblio (biblionumber int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, title longtext, author longtext, datecreated date NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE biblio_metadata (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, biblionumber int(11) NOT NULL, format varchar(16) NOT NULL, `schema` varchar(16) NOT NULL, metadata longtext NOT NULL, CONSTRAINT bm_fk FOREIGN KEY (biblionumber) REFERENCES biblio (biblionumber) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE items (itemnumber int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, biblionumber int(11) NOT NULL, barcode varchar(20) UNIQUE, homebranch varchar(10), CONSTRAINT it_fk FOREIGN KEY (biblionumber) REFERENCES biblio (biblionumber) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE systempreferences (variable varchar(50) NOT NULL PRIMARY KEY, value mediumtext, options longtext, explanation mediumtext, type varchar(20)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE zebraqueue (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, biblio_auth_number bigint(20) unsigned NOT NULL DEFAULT 0, operation char(20) NOT NULL DEFAULT '', server char(20) NOT NULL DEFAULT '', done int(11) NOT NULL DEFAULT 0, time timestamp NOT NULL DEFAULT current_timestamp()) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE background_jobs (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, status varchar(32), type varchar(64), queue varchar(191) NOT NULL DEFAULT 'default', enqueued_on datetime, data longtext) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE sessions (id varchar(32) NOT NULL PRIMARY KEY, a_session longblob NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
SQL
    local i
    for i in $(seq -w 1 50); do
        printf 'CREATE TABLE kei_filler_%s (id int(11) NOT NULL PRIMARY KEY, note varchar(100)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n' "$i"
    done
}

# kei_data_sql LABEL NBIB ENGINE: catalog content; every title starts with LABEL.
kei_data_sql() {
    local label="$1" n="${2:-200}" engine="${3:-Zebra}"
    cat <<SQL
INSERT INTO branches VALUES ('CPL','Castro Alves');
INSERT INTO categories VALUES ('S','Staff','S'),('PT','Patron','A');
INSERT INTO systempreferences (variable,value,type) VALUES ('Version','24.0500000','Free'),('SearchEngine','${engine}','Choice'),('marker','${label}','Free');
INSERT INTO borrowers (cardnumber,surname,firstname,branchcode,categorycode,userid) VALUES ('C1','${label}','Ana','CPL','PT','ana');
SQL
    awk -v n="$n" -v label="$label" 'BEGIN {
        srand(42 + length(label));
        for (i = 1; i <= n; i++) {
            s = ""; for (j = 0; j < 40; j++) s = s sprintf("%c", 97 + int(rand() * 26));
            printf "INSERT INTO biblio VALUES (%d,\"%s title %d %s\",\"author %d\",\"2024-01-01\");\n", i, label, i, s, i;
            printf "INSERT INTO biblio_metadata (biblionumber,format,`schema`,metadata) VALUES (%d,\"marcxml\",\"MARC21\",\"<record>%s %s</record>\");\n", i, label, s s s;
            printf "INSERT INTO items (biblionumber,barcode,homebranch) VALUES (%d,\"%s-%d\",\"CPL\");\n", i, substr(label, 1, 3), i;
        }
        for (i = 1; i <= 300; i++) {
            s = ""; for (j = 0; j < 30; j++) s = s sprintf("%c", 65 + int(rand() * 26));
            printf "INSERT INTO systempreferences (variable,value,type) VALUES (\"pref%d\",\"%s\",\"Free\");\n", i, s;
        }
    }'
}

# kei_make_catalog DB LABEL [NBIB] [ENGINE]
kei_make_catalog() {
    local db="$1"
    mysql -e "DROP DATABASE IF EXISTS \`$db\`; CREATE DATABASE \`$db\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    { echo "SET FOREIGN_KEY_CHECKS=0;"; kei_schema_sql; kei_data_sql "$2" "${3:-200}" "${4:-Zebra}"; } | mysql "$db"
}

# The live catalog: "OLD" data, as found on the server before a restore.
kei_reset_live_catalog() { kei_make_catalog "$DB" "${1:-OLD}" "${2:-200}" "${3:-Zebra}"; }

# kei_dump DB FILE [extra mysqldump options]: .sql or .sql.gz by extension.
kei_dump() {
    local db="$1" out="$2"; shift 2
    if [[ "$out" == *.gz ]]; then
        mysqldump --single-transaction --routines --triggers "$@" "$db" | gzip > "$out"
    else
        mysqldump --single-transaction --routines --triggers "$@" "$db" > "$out"
    fi
}

# A valid backup of a "NEW" catalog, in both formats (cached per test file).
kei_backup_fixtures() {
    mkdir -p "$FIX"
    [ -s "$FIX/new.sql.gz" ] && return 0
    kei_make_catalog kei_src NEW 300
    kei_dump kei_src "$FIX/new.sql.gz"
    kei_dump kei_src "$FIX/new.sql"
    mysql -e "DROP DATABASE IF EXISTS kei_src;"
}

# Label of the live catalog ("OLD", "NEW"...), or "" when it is gone.
live_marker()  { mysql -Nse "SELECT value FROM ${DB}.systempreferences WHERE variable='marker';" 2>/dev/null; }
live_biblios() { mysql -Nse "SELECT COUNT(*) FROM ${DB}.biblio;" 2>/dev/null; }
live_engine()  { mysql -Nse "SELECT value FROM ${DB}.systempreferences WHERE variable='SearchEngine';" 2>/dev/null; }

# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------
# Starts a background service without any of the test runner's descriptors:
# bats waits until every copy of its pipes is closed, so a server that kept
# one would hang the run.
kei_detached() {
    (
        for fd in /proc/self/fd/*; do
            fd="${fd##*/}"
            [ "$fd" -gt 2 ] 2>/dev/null && eval "exec $fd>&-" 2>/dev/null
        done
        exec setsid "$@" </dev/null >>/tmp/kei-services.log 2>&1
    ) &
}

kei_mariadb_up() { mysqladmin ping >/dev/null 2>&1; }
kei_start_mariadb() {   # [extra mariadbd options, e.g. --skip-name-resolve]
    kei_mariadb_up && return 0
    mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld
    kei_detached mariadbd --user=mysql --socket=/run/mysqld/mysqld.sock \
        --pid-file=/run/mysqld/mysqld.pid "$@"
    local i
    for i in $(seq 1 60); do kei_mariadb_up && return 0; sleep 0.5; done
    return 1
}
kei_stop_mariadb() {
    mysqladmin shutdown >/dev/null 2>&1
    local i
    for i in $(seq 1 60); do kei_mariadb_up || return 0; sleep 0.5; done
    return 1
}
# memcached needs a moment to exit on SIGTERM: wait for real state changes.
kei_memcached_up() { (exec 3<>/dev/tcp/127.0.0.1/11211) 2>/dev/null; }
kei_stop_memcached() {
    pkill -x memcached || true
    local i
    for i in $(seq 1 40); do pgrep -x memcached >/dev/null || return 0; sleep 0.25; done
    return 1
}
kei_start_memcached() {
    kei_memcached_up && return 0
    kei_stop_memcached
    kei_detached memcached -u memcache -l 127.0.0.1 -p 11211 -m 16
    local i
    for i in $(seq 1 40); do kei_memcached_up && return 0; sleep 0.25; done
    return 1
}

# Kills the fake daemons started by the koha-* test doubles.
kei_kill_daemons() {
    local p
    [ -f "$KEI_S/daemons.pids" ] || return 0
    while read -r p; do [ -n "$p" ] && { kill "$p" 2>/dev/null || true; }; done < "$KEI_S/daemons.pids"
    rm -f "$KEI_S/daemons.pids"
}

# Fresh state for every test: logs, mock services, locks, backups, cron.
kei_reset_env() {
    kei_kill_daemons
    rm -rf "$KEI_S/calls.log" "$KEI_S/dialogs.log" "$KEI_S/answers" "$KEI_S/syslog" \
           "$KEI_S/run" "$KEI_S/svc" "$KEI_S/svc-fail" "$KEI_S/fail" "$KEI_S/pkgs" \
           "$KEI_S/inputs" "$KEI_S/cache-module-broken" "$KEI_S/textbox.last" "$KEI_S/textboxes.log" "$KEI_S/last-staged.mrc" "$KEI_S"/batch-*.biblios
    rm -rf /var/log/koha-easy-install/tools /var/lib/koha/library/email.enabled /root/koha_patrons_template.csv
    # Magic Import Tool: drop folder, remembered column answers, backups on their way to Restore database.
    rm -rf /root/importar /etc/koha-easy-install/import-profiles /var/tmp/kei-restore.*
    mkdir -p "$KEI_S/run" "$KEI_S/svc" "$KEI_S/svc-fail" "$KEI_S/fail" "$KEI_S/pkgs"
    touch "$KEI_S/svc/mariadb" "$KEI_S/svc/memcached" "$KEI_S/svc/apache2" "$KEI_S/svc/cron"
    touch "$KEI_S/run/zebra" "$KEI_S/run/indexer" "$KEI_S/run/plack" "$KEI_S/run/worker"
    rm -f /root/.my.cnf
    rm -rf /var/backups/koha_sql /var/backups/koha_marc /run/koha-easy-install /var/lib/koha-easy-install/last-manual-backup
    rm -f /etc/cron.d/koha_* /var/lock/koha_backup.lock /var/run/koha_backup.pid
    rm -f /usr/local/bin/koha-zebra-watchdog.sh /usr/local/bin/koha-es-watchdog.sh /usr/local/bin/koha-wait-services.sh
    # Modules of Library tools 11-13 (messaging, cataloguing tables, marc_replace.pl).
    rm -rf /usr/local/lib/site_perl/KohaEasy /usr/local/lib/site_perl/SMS/Send/KohaEasy /usr/local/lib/koha-easy-installer \
           /etc/koha/sites/library/kei-messaging.conf /var/lib/koha/library/kei-messaging /var/lib/koha/library/kei-marc-replace \
           /etc/koha-easy-install/messaging.state /etc/koha-easy-install/marc_replace.state /etc/koha-easy-install/tables \
           "$KEI_S/koha" "$KEI_S/http.log" "$KEI_S/http-fail" "$KEI_S/tg-updates.json" "$KEI_S/vision-reply.txt" "$KEI_S/vision-fail"
    rm -f /etc/systemd/system/koha-common.service.d/koha-easy-install.conf /etc/systemd/system/apache2.service.d/koha-easy-install.conf
    cp -f "$KEI_REPO/tests/mocks/koha-conf.xml" /etc/koha/sites/library/koha-conf.xml
    printf 'USE_INDEXER_DAEMON="yes"\n' > /etc/default/koha-common
    kei_start_mariadb
    kei_start_memcached
    mysql -e "DROP DATABASE IF EXISTS koha_restore_check; DROP DATABASE IF EXISTS koha_teste_restauracao;" 2>/dev/null || true
}

# Runs one installer function through the driver (bats "run" semantics).
panel() { run "$KEI_SH" "$PANEL" "$@"; }

dialogs() { cat "$KEI_S/dialogs.log" 2>/dev/null; }
calls()   { cat "$KEI_S/calls.log" 2>/dev/null; }
answer()  { printf '%s\n' "$@" >> "$KEI_S/answers"; }
inputs()  { printf '%s\n' "$@" >> "$KEI_S/inputs"; }

# Fails the test with context when a condition is false.
assert() {
    if ! eval "$1"; then
        printf 'ASSERTION FAILED: %s\n' "${2:-$1}" >&2
        printf -- '--- output ---\n%s\n--- dialogs ---\n%s\n' "${output:-}" "$(dialogs | tail -n 15)" >&2
        return 1
    fi
}

# The catalog was not modified: still the OLD data, Koha still serving.
assert_catalog_untouched() {
    assert '[ "$(live_marker)" = "OLD" ]' "live catalog must still be the OLD one (got '$(live_marker)')"
    assert '[ "$(live_biblios)" = "200" ]' "OLD catalog must keep its 200 records (got '$(live_biblios)')"
    assert '! grep -q "koha-plack --stop" "$KEI_S/calls.log" 2>/dev/null' "Koha services must not have been stopped"
}

# ---------------------------------------------------------------------
# Library tools: the tables and columns they read or write (same names and
# types as Koha's kohastructure.sql), added to the live catalog.
#   patrons: C1 Ana (PT), 3 students (ST: two adults, one child), 2 expired
#   patrons without loans, 1 expired with a loan, 1 expired staff member,
#   1 patron who keeps his history (privacy 0)
#   history: 3 old loans + 2 old holds anonymisable, 1 recent loan
# ---------------------------------------------------------------------
kei_tools_catalog() {
    mysql "$DB" <<'SQL'
ALTER TABLE borrowers ADD COLUMN email mediumtext, ADD COLUMN phone mediumtext, ADD COLUMN dateofbirth date,
  ADD COLUMN dateenrolled date, ADD COLUMN dateexpiry date, ADD COLUMN privacy int(11) NOT NULL DEFAULT 1;
ALTER TABLE items ADD COLUMN itemcallnumber varchar(255), ADD COLUMN dateaccessioned date, ADD COLUMN issues smallint(6),
  ADD COLUMN itemlost tinyint(1) NOT NULL DEFAULT 0, ADD COLUMN itemlost_on datetime;
ALTER TABLE items MODIFY homebranch varchar(10) NULL;
CREATE TABLE import_batches (import_batch_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, matcher_id int(11), num_records int(11) NOT NULL DEFAULT 0,
  num_items int(11) NOT NULL DEFAULT 0, upload_timestamp timestamp NOT NULL DEFAULT current_timestamp(),
  import_status enum('staging','staged','importing','imported','reverting','reverted','cleaned') NOT NULL DEFAULT 'staging',
  batch_type enum('batch','z3950','webservice') NOT NULL DEFAULT 'batch', record_type enum('biblio','auth','holdings') NOT NULL DEFAULT 'biblio',
  file_name varchar(100), comments longtext);
CREATE TABLE import_records (import_record_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, import_batch_id int(11) NOT NULL,
  status enum('error','staged','imported','reverted','items_reverted','ignored') NOT NULL DEFAULT 'staged');
CREATE TABLE import_items (import_items_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, import_record_id int(11) NOT NULL,
  itemnumber int(11), status enum('error','staged','imported','reverted','ignored') NOT NULL DEFAULT 'staged');
CREATE TABLE marc_matchers (matcher_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, code varchar(10) NOT NULL DEFAULT '',
  description varchar(255) NOT NULL DEFAULT '', record_type varchar(10) NOT NULL DEFAULT 'biblio', threshold int(11) NOT NULL DEFAULT 0);
CREATE TABLE saved_sql (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, borrowernumber int(11), date_created datetime, last_modified datetime,
  savedsql mediumtext, last_run datetime, report_name varchar(255) NOT NULL DEFAULT '', type varchar(255), notes mediumtext,
  cache_expiry int(11) NOT NULL DEFAULT 300, public tinyint(1) NOT NULL DEFAULT 0, report_area varchar(6), report_group varchar(80),
  report_subgroup varchar(80), mana_id int(11)) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE issues (issue_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, borrowernumber int(11), itemnumber int(11),
  date_due datetime, branchcode varchar(10), issuedate datetime);
CREATE TABLE old_issues (issue_id int(11) NOT NULL PRIMARY KEY, borrowernumber int(11), itemnumber int(11), date_due datetime,
  branchcode varchar(10), returndate datetime, issuedate datetime);
CREATE TABLE old_reserves (reserve_id int(11) NOT NULL PRIMARY KEY, borrowernumber int(11), biblionumber int(11),
  timestamp timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp());
CREATE TABLE statistics (datetime datetime, branch varchar(10), type varchar(16), itemnumber int(11), borrowernumber int(11));
CREATE TABLE authorised_values (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, category varchar(32) NOT NULL DEFAULT '',
  authorised_value varchar(80) NOT NULL DEFAULT '', lib varchar(200));

INSERT INTO marc_matchers (code, description) VALUES ('ISBN', 'ISBN');
INSERT INTO authorised_values (category, authorised_value, lib) VALUES ('LOST', '1', 'Lost');
INSERT INTO branches VALUES ('MPL', 'Midway');
INSERT INTO categories VALUES ('ST', 'Student', 'C'), ('FM', 'Former student', 'A');
UPDATE borrowers SET dateexpiry = '2099-01-01', dateenrolled = '2020-01-01' WHERE cardnumber = 'C1';
INSERT INTO borrowers (cardnumber, surname, firstname, branchcode, categorycode, flags, dateofbirth, dateenrolled, dateexpiry, privacy) VALUES
  ('S1', 'Souza', 'Bia', 'CPL', 'ST', 0, '2000-03-01', '2019-02-01', '2099-01-01', 1),
  ('S2', 'Lima', 'Caio', 'CPL', 'ST', 0, '2001-05-01', '2024-02-01', '2099-01-01', 1),
  ('S3', 'Rocha', 'Duda', 'MPL', 'ST', 0, '2016-07-01', '2024-02-01', '2099-01-01', 1),
  ('E1', 'Old', 'Eva', 'CPL', 'PT', 0, NULL, '2010-01-01', '2019-01-01', 1),
  ('E2', 'Old', 'Fabio', 'CPL', 'PT', 0, NULL, '2010-01-01', '2019-06-01', 1),
  ('E3', 'Old', 'Gil', 'CPL', 'PT', 0, NULL, '2010-01-01', '2019-06-01', 1),
  ('E4', 'Staff', 'Hugo', 'CPL', 'S', 1, NULL, '2010-01-01', '2019-06-01', 1),
  ('K1', 'Keep', 'Iris', 'CPL', 'PT', 0, NULL, '2010-01-01', '2099-01-01', 0);
UPDATE items SET itemcallnumber = CONCAT('000.', itemnumber), dateaccessioned = '2020-01-01', issues = 0;
UPDATE items SET itemlost = 1, itemlost_on = NOW() WHERE itemnumber = 1;
INSERT INTO issues (borrowernumber, itemnumber, date_due, branchcode, issuedate)
  SELECT borrowernumber, 2, DATE_SUB(NOW(), INTERVAL 3 DAY), 'CPL', DATE_SUB(NOW(), INTERVAL 20 DAY) FROM borrowers WHERE cardnumber = 'E3';
INSERT INTO old_issues (issue_id, borrowernumber, itemnumber, returndate, issuedate)
  SELECT 1, borrowernumber, 3, '2019-03-01', '2019-02-01' FROM borrowers WHERE cardnumber = 'C1' UNION ALL
  SELECT 2, borrowernumber, 4, '2019-03-01', '2019-02-01' FROM borrowers WHERE cardnumber = 'S1' UNION ALL
  SELECT 3, borrowernumber, 5, '2019-03-01', '2019-02-01' FROM borrowers WHERE cardnumber = 'E1' UNION ALL
  SELECT 4, borrowernumber, 6, '2019-03-01', '2019-02-01' FROM borrowers WHERE cardnumber = 'K1' UNION ALL
  SELECT 5, borrowernumber, 7, NOW(), DATE_SUB(NOW(), INTERVAL 5 DAY) FROM borrowers WHERE cardnumber = 'C1';
INSERT INTO old_reserves (reserve_id, borrowernumber, biblionumber, timestamp)
  SELECT 1, borrowernumber, 1, '2020-03-01' FROM borrowers WHERE cardnumber = 'C1' UNION ALL
  SELECT 2, borrowernumber, 2, '2020-03-01' FROM borrowers WHERE cardnumber = 'S2';
INSERT INTO statistics (datetime, branch, type, itemnumber, borrowernumber) VALUES
  (NOW(), 'CPL', 'issue', 3, 1), (NOW(), 'CPL', 'issue', 3, 1), (NOW(), 'MPL', 'return', 3, 1);
INSERT INTO saved_sql (borrowernumber, date_created, savedsql, report_name, type, notes)
  VALUES (NULL, NOW(), 'SELECT 1', 'My own report', '1', 'written by the library');
SQL
}
tools_sql() { mysql --default-character-set=utf8mb4 -Nse "$1" "$DB"; }

# ---------------------------------------------------------------------
# Brazil tools: item types, label creator, calendar, patron attributes and
# the detail-view preferences (same columns as Koha 26.05). On top of
# kei_tools_catalog: one template, one layout and one closed day that were
# not made by the panel, and CPFs in sort1 for the CPF report.
# ---------------------------------------------------------------------
kei_br_catalog() {
    mysql "$DB" <<'SQL'
CREATE TABLE itemtypes (itemtype varchar(10) NOT NULL PRIMARY KEY, description longtext) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO itemtypes VALUES ('LIVRO', 'Livro'), ('REV', 'Revista');
CREATE TABLE creator_templates (template_id int(4) NOT NULL AUTO_INCREMENT PRIMARY KEY, profile_id int(4) DEFAULT NULL,
  template_code char(100) NOT NULL DEFAULT 'DEFAULT TEMPLATE', template_desc char(100) NOT NULL DEFAULT 'Default description',
  page_width float NOT NULL DEFAULT 0, page_height float NOT NULL DEFAULT 0, label_width float NOT NULL DEFAULT 0, label_height float NOT NULL DEFAULT 0,
  top_text_margin float NOT NULL DEFAULT 0, left_text_margin float NOT NULL DEFAULT 0, top_margin float NOT NULL DEFAULT 0, left_margin float NOT NULL DEFAULT 0,
  cols int(2) NOT NULL DEFAULT 0, `rows` int(2) NOT NULL DEFAULT 0, col_gap float NOT NULL DEFAULT 0, row_gap float NOT NULL DEFAULT 0,
  units char(20) NOT NULL DEFAULT 'POINT', creator char(15) NOT NULL DEFAULT 'Labels') DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE creator_layouts (layout_id int(4) NOT NULL AUTO_INCREMENT PRIMARY KEY, barcode_type char(100) NOT NULL DEFAULT 'CODE39',
  start_label int(2) NOT NULL DEFAULT 1, printing_type char(32) NOT NULL DEFAULT 'BAR', layout_name char(25) NOT NULL DEFAULT 'DEFAULT',
  guidebox int(1) DEFAULT 0, oblique_title int(1) DEFAULT 1, font char(10) NOT NULL DEFAULT 'TR', font_size int(4) NOT NULL DEFAULT 10,
  scale_width decimal(28,6) NOT NULL DEFAULT 0.800000, scale_height decimal(28,6) NOT NULL DEFAULT 0.010000, units char(20) NOT NULL DEFAULT 'POINT',
  callnum_split int(1) DEFAULT 0, text_justify char(1) NOT NULL DEFAULT 'L', format_string varchar(210) NOT NULL DEFAULT 'barcode',
  layout_xml mediumtext NOT NULL, creator char(15) NOT NULL DEFAULT 'Labels') DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO creator_templates (template_code, template_desc, units) VALUES ('MINHA', 'Modelo da biblioteca', 'MM');
INSERT INTO creator_layouts (layout_name, layout_xml) VALUES ('Meu layout', '');
CREATE TABLE special_holidays (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, branchcode varchar(10) NOT NULL, day smallint(6) NOT NULL DEFAULT 0,
  month smallint(6) NOT NULL DEFAULT 0, year smallint(6) NOT NULL DEFAULT 0, isexception smallint(1) NOT NULL DEFAULT 1,
  title varchar(50) NOT NULL DEFAULT '', description mediumtext NOT NULL) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO special_holidays (branchcode, day, month, year, isexception, title, description) VALUES ('CPL', 25, 12, 2025, 0, 'Natal', 'dia de fechar');
CREATE TABLE borrower_attribute_types (code varchar(64) NOT NULL PRIMARY KEY, description varchar(255) NOT NULL);
CREATE TABLE borrower_attributes (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, borrowernumber int(11) NOT NULL, code varchar(64) NOT NULL, attribute varchar(255));
ALTER TABLE borrowers ADD COLUMN sort1 varchar(80);
UPDATE borrowers SET sort1 = '529.982.247-25' WHERE cardnumber = 'S1';
UPDATE borrowers SET sort1 = '52998224725' WHERE cardnumber = 'S2';
UPDATE borrowers SET sort1 = '123.456.789-00' WHERE cardnumber = 'S3';
UPDATE borrowers SET sort1 = '5299822472' WHERE cardnumber = 'E1';
UPDATE borrowers SET sort1 = 'turma 3B' WHERE cardnumber = 'E2';
INSERT INTO systempreferences (variable, value, type) VALUES ('OPACXSLTDetailsDisplay', 'default', 'Free'), ('XSLTDetailsDisplay', '', 'Free');
SQL
}

# kei_marc FILE ENCODING MARCXML: ISO 2709 file written by yaz-marcdump
# (leader/09 blank, like the exports of older systems).
kei_marc() { yaz-marcdump -i marcxml -o marc -f UTF-8 -t "$2" -l 9=32 "$3" > "$1"; }

# ---------------------------------------------------------------------
# Library tools 11-13 (messaging, cataloguing aids, marc_replace.pl), on
# top of kei_tools_catalog and kei_br_catalog: notices (with Koha's SMS
# versions of CHECKOUT and HOLD only), messaging preferences, SMS numbers
# in several shapes, a real MARCXML record (biblionumber 201) and call
# numbers already using L589 in class 025.4.
# ---------------------------------------------------------------------
kei_modules_catalog() {
    mysql "$DB" <<'SQL'
CREATE TABLE letter (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, module varchar(20) NOT NULL DEFAULT '', code varchar(20) NOT NULL DEFAULT '',
  branchcode varchar(10) NOT NULL DEFAULT '', name varchar(100) NOT NULL DEFAULT '', is_html tinyint(1) DEFAULT 0, title varchar(200) NOT NULL DEFAULT '',
  content mediumtext, message_transport_type varchar(20) NOT NULL DEFAULT 'email', lang varchar(25) NOT NULL DEFAULT 'default',
  UNIQUE KEY letter_uniq_1 (module, code, branchcode, message_transport_type, lang)) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO letter (module, code, name, title, content, message_transport_type) VALUES
  ('circulation', 'CHECKOUT', 'Item check-out (digest)', 'Checkouts', 'email text', 'email'),
  ('circulation', 'CHECKOUT', 'Item check-out (digest)', 'Checkouts', 'The following items have been checked out: [% biblio.title %]', 'sms'),
  ('circulation', 'ODUE', 'Overdue notice', 'Item overdue', 'email text', 'email'),
  ('reserves', 'HOLD', 'Hold available for pickup', 'Hold', 'Your hold [% biblio.title %] is waiting', 'sms');
CREATE TABLE overduerules_transport_types (id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, letternumber int(1) NOT NULL DEFAULT 1,
  message_transport_type varchar(20) NOT NULL DEFAULT 'email', overduerules_id int(11) NOT NULL);
INSERT INTO overduerules_transport_types (message_transport_type, overduerules_id) VALUES ('email', 1), ('sms', 1);
CREATE TABLE borrower_message_preferences (borrower_message_preference_id int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
  borrowernumber int(11), categorycode varchar(10), message_attribute_id int(11) DEFAULT 0, days_in_advance int(11), wants_digest tinyint(1) NOT NULL DEFAULT 0);
CREATE TABLE borrower_message_transport_preferences (borrower_message_preference_id int(11) NOT NULL, message_transport_type varchar(20) NOT NULL);
INSERT INTO borrower_message_preferences (borrowernumber, message_attribute_id) SELECT borrowernumber, 6 FROM borrowers WHERE cardnumber IN ('S1', 'S2');
INSERT INTO borrower_message_transport_preferences SELECT borrower_message_preference_id, 'sms' FROM borrower_message_preferences;
ALTER TABLE borrowers ADD COLUMN smsalertnumber varchar(50), ADD COLUMN mobile varchar(50);
UPDATE borrowers SET smsalertnumber = '(44) 9876-5432' WHERE cardnumber = 'S1';
UPDATE borrowers SET smsalertnumber = '+5544998765432' WHERE cardnumber = 'S2';
UPDATE borrowers SET smsalertnumber = '(10) 1234-5678' WHERE cardnumber = 'S3';
UPDATE borrowers SET smsalertnumber = '0 15 44 3524-1234' WHERE cardnumber = 'E1';
INSERT INTO systempreferences (variable, value, type) VALUES ('SMSSendDriver', 'Email', 'Free'), ('EnhancedMessagingPreferences', '1', 'YesNo'),
  ('IntranetUserJS', '/* the library''s own code */\n$(document).ready(function () { var re = /a\\b/; });', 'Textarea');
INSERT INTO biblio VALUES (201, 'Classificação decimal', 'Lentino, Noêmia', '2024-01-01'), (202, 'Outra obra', 'Lent, Carlos', '2024-01-01');
INSERT INTO biblio_metadata (biblionumber, format, `schema`, metadata) VALUES (201, 'marcxml', 'MARC21',
  '<?xml version="1.0" encoding="UTF-8"?>\n<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00300nam a2200100 a 4500</leader><datafield tag="082" ind1="0" ind2="4"><subfield code="a">025.4</subfield></datafield><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Lentino, Noêmia,</subfield></datafield><datafield tag="245" ind1="1" ind2="2"><subfield code="a">A classificação decimal /</subfield></datafield></record>');
INSERT INTO items (biblionumber, barcode, homebranch, itemcallnumber) VALUES (202, 'LENT-1', 'CPL', '025.4 L589o'), (201, 'LENTINO-1', 'CPL', '025.4 L589c'),
  (202, 'OTHER-1', 'CPL', '025.4 L5891a'), (202, 'OTHER-2', 'CPL', '869.3 L589x');
SQL
}

# The WhatsApp / Telegram / vision model test double on 127.0.0.1:PORT
# (default 18080).
kei_http_mock_start() {
    local port="${1:-18080}" i
    kei_detached /usr/local/lib/kei-mock/http-mock "$port" "$KEI_S"
    for i in $(seq 1 40); do
        (exec 5<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && { pgrep -f "http-mock $port" >> "$KEI_S/daemons.pids"; return 0; }
        sleep 0.25
    done
    return 1
}
http_log() { cat "$KEI_S/http.log" 2>/dev/null; }
