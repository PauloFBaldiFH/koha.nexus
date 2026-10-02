#!/usr/bin/env bats
# Incremental indexing: new or changed records must reach the search engine
# after installs, engine switches and restores (successful or not).

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_backup_fixtures
    rm -f "$KEI_S/es-up" /etc/cron.d/koha_zebra_queue /etc/cron.d/koha_es_watchdog
    unset KEI_SELECT_FILE KEI_EXTRA KEI_DEFAULT_ANSWER
}

teardown() { kei_kill_daemons; }

# The ES indexer runs: its daemon, or its systemd unit (which starts the
# daemon on a real server; the systemctl test double only records it).
es_indexer_up() { [ -e "$KEI_S/run/es-indexer" ] || [ -e "$KEI_S/svc/koha-es-indexer@library" ]; }

set_engine() { mysql -e "UPDATE ${DB}.systempreferences SET value='$1' WHERE variable='SearchEngine';"; }
es_server()  { set_engine Elasticsearch; touch "$KEI_S/pkgs/elasticsearch" "$KEI_S/pkgs/koha-elasticsearch" "$KEI_S/es-up" "$KEI_S/svc/elasticsearch"; }

# The command a cron line runs (6th field on), without redirections.
cron_command() { grep -vE '^[[:space:]]*(#|$|[A-Z_]+=)' "$1" | head -n1 | awk '{ for (i = 7; i <= NF; i++) if ($i !~ /^>|^2>/) printf "%s ", $i }'; }

zebra_watchdog() { run "$KEI_SH" "$(cron_command /etc/cron.d/koha_zebra_queue | awk '{print $1}')"; }
backlog() { mysql -e "INSERT INTO ${DB}.zebraqueue (biblio_auth_number, operation, server, done, time) VALUES (1,'specialUpdate','biblioserver',0, NOW() - INTERVAL ${1:-60} MINUTE);"; }

# --- Zebra -----------------------------------------------------------------

@test "I01 the Zebra indexing cron runs a program that exists (no zebraqueue_daemon.pl)" {
    panel write_cron_zebra
    assert '[ -f /etc/cron.d/koha_zebra_queue ]'
    assert '! grep -q zebraqueue_daemon /etc/cron.d/koha_zebra_queue' "zebraqueue_daemon.pl does not exist in Koha"
    local prog; prog=$(cron_command /etc/cron.d/koha_zebra_queue | awk '{print $1}')
    assert '[ -x "$prog" ]' "cron must run an existing executable (got '$prog')"
    assert '[ "$(stat -c %a /etc/cron.d/koha_zebra_queue)" = "644" ]'
    assert 'bash -n "$prog"'
}

@test "I02 watchdog starts the Zebra indexer daemon (koha-indexer) when it is down" {
    panel write_cron_zebra
    rm -f "$KEI_S/run/indexer"
    zebra_watchdog
    assert '[ -e "$KEI_S/run/indexer" ]' "koha-indexer must be started"
    assert 'grep -q "koha-indexer --start" "$KEI_S/calls.log"'
}

@test "I03 watchdog starts the Zebra server when it is down" {
    panel write_cron_zebra
    rm -f "$KEI_S/run/zebra"
    zebra_watchdog
    assert '[ -e "$KEI_S/run/zebra" ]'
}

@test "I04 watchdog restarts a stuck indexer (records waiting > 10 min)" {
    panel write_cron_zebra
    backlog 60
    zebra_watchdog
    assert 'grep -q "koha-indexer --restart" "$KEI_S/calls.log"'
}

@test "I05 watchdog leaves a healthy indexer alone" {
    panel write_cron_zebra
    backlog 1
    zebra_watchdog
    assert '[ "$status" -eq 0 ]'
    assert '! grep -q "koha-indexer" "$KEI_S/calls.log" 2>/dev/null'
}

@test "I06 watchdog stays away during panel maintenance, and clears a stale marker" {
    panel write_cron_zebra
    rm -f "$KEI_S/run/indexer"
    mkdir -p /run/koha-easy-install
    sleep 30 & local live=$!
    echo "$live" > /run/koha-easy-install/maintenance.in-progress
    zebra_watchdog
    assert '[ ! -e "$KEI_S/run/indexer" ]' "must not start the indexer during a restore"
    kill "$live"; wait "$live" 2>/dev/null || true
    zebra_watchdog
    assert '[ -e "$KEI_S/run/indexer" ]' "a stale marker must not block indexing forever"
    assert '[ ! -e /run/koha-easy-install/maintenance.in-progress ]'
}

@test "I07 watchdog does nothing on Elasticsearch or when MariaDB is down" {
    panel write_cron_zebra
    rm -f "$KEI_S/run/indexer"
    set_engine Elasticsearch
    zebra_watchdog
    assert '[ ! -e "$KEI_S/run/indexer" ]'
    set_engine Zebra
    kei_stop_mariadb
    zebra_watchdog
    kei_start_mariadb
    assert '[ "$status" -eq 0 ]'
    assert '[ ! -e "$KEI_S/run/indexer" ]'
}

@test "I08 USE_INDEXER_DAEMON=no: watchdog runs the incremental rebuild itself" {
    panel write_cron_zebra
    printf 'USE_INDEXER_DAEMON="no"\n' > /etc/default/koha-common
    zebra_watchdog
    assert 'grep -q "koha-rebuild-zebra -q library" "$KEI_S/calls.log"'
}

@test "I09 health check fails when the Zebra indexer daemon is down or stuck" {
    panel write_cron_zebra
    rm -f "$KEI_S/run/indexer"
    panel eval 'v_reset test; validate_zebra Zebra; echo "FAIL=$V_FAIL"'
    assert 'echo "$output" | grep -q "FAIL=[1-9]"' "a dead indexer must be a failure"
    touch "$KEI_S/run/indexer"
    backlog 60
    panel eval 'v_reset test; validate_zebra Zebra; echo "FAIL=$V_FAIL"'
    assert 'echo "$output" | grep -q "FAIL=[1-9]"' "a stuck queue must be a failure"
    mysql -e "DELETE FROM ${DB}.zebraqueue;"
    panel eval 'v_reset test; validate_zebra Zebra; echo "FAIL=$V_FAIL"'
    assert 'echo "$output" | grep -q "FAIL=0"'
}

@test "I10 successful restore on Zebra: indexer daemon running and watchdog scheduled" {
    rm -f "$KEI_S/run/indexer"
    export KEI_SELECT_FILE="$FIX/new.sql.gz"
    panel function_restore_database
    assert '[ "$(live_marker)" = "NEW" ]'
    assert 'grep -q "koha-rebuild-zebra -f" "$KEI_S/calls.log"' "full Zebra rebuild expected"
    assert '[ -e "$KEI_S/run/indexer" ]' "koha-indexer must be running"
    assert '[ -x "$(cron_command /etc/cron.d/koha_zebra_queue | awk "{print \$1}")" ]'
}

# --- Elasticsearch -------------------------------------------------------------

@test "I11 Zebra server: indexer setup does not install the Elasticsearch watchdog" {
    panel manage_koha_indexers start
    assert '[ ! -e /etc/cron.d/koha_es_watchdog ]' "the stock <elasticsearch> block is not an engine switch"
    assert '! grep -q "koha-es-indexer --start" "$KEI_S/calls.log" 2>/dev/null'
}

@test "I12 Elasticsearch watchdog follows SearchEngine, not the koha-conf.xml block" {
    es_server
    panel install_koha_indexer_service
    set_engine Zebra                    # switched in Koha's staff interface
    rm -f "$KEI_S/run/es-indexer"; : > "$KEI_S/calls.log"
    run "$KEI_SH" /usr/local/bin/koha-es-watchdog.sh
    assert '! grep -q "koha-es-indexer" "$KEI_S/calls.log"' "must not start an ES indexer on a Zebra catalog"
    set_engine Elasticsearch
    run "$KEI_SH" /usr/local/bin/koha-es-watchdog.sh
    assert 'grep -q "koha-es-indexer@library\|koha-es-indexer --restart" "$KEI_S/calls.log"' "must recover the ES indexer"
}

@test "I13 successful restore on Elasticsearch: engine kept, indexer and watchdog running" {
    es_server
    export KEI_SELECT_FILE="$FIX/new.sql.gz"
    panel function_restore_database
    assert '[ "$(live_marker)" = "NEW" ]'
    assert '[ "$(live_engine)" = "Elasticsearch" ]'
    assert '[ -f /etc/cron.d/koha_es_watchdog ]'
    assert 'es_indexer_up'
    assert 'grep -q "koha-elasticsearch --rebuild" "$KEI_S/calls.log"'
}

@test "I14 failed restore on Elasticsearch: after the rollback the indexer is not left dormant" {
    es_server
    cat > "$BATS_TEST_TMPDIR/extra.sh" <<'EOF'
eval "kei_orig_$(declare -f import_sql_file)"
import_sql_file() {
    if [ "$2" = "koha_library" ] && [ ! -e /run/kei-mock/injected ]; then
        touch /run/kei-mock/injected; echo "ERROR (injected)" >> "$3"; return 1
    fi
    kei_orig_import_sql_file "$@"
}
EOF
    rm -f "$KEI_S/injected" "$KEI_S/run/es-indexer" "$KEI_S/svc/koha-es-indexer@library"
    export KEI_EXTRA="$BATS_TEST_TMPDIR/extra.sh" KEI_SELECT_FILE="$FIX/new.sql.gz"
    panel function_restore_database
    assert '[ "$(live_marker)" = "OLD" ]'
    assert '[ -f /etc/cron.d/koha_es_watchdog ]' "ES watchdog must be scheduled again"
    assert 'es_indexer_up' "ES indexer must be running again"
}

@test "I15 restore on a server whose Elasticsearch is gone falls back to Zebra with indexing" {
    set_engine Elasticsearch            # but nothing Elasticsearch is installed
    export KEI_SELECT_FILE="$FIX/new.sql.gz"
    panel function_restore_database
    assert '[ "$(live_engine)" = "Zebra" ]'
    assert '[ -e "$KEI_S/run/indexer" ]'
    assert '[ -f /etc/cron.d/koha_zebra_queue ]'
}

@test "I16 switch Elasticsearch -> Zebra: indexer daemon running, watchdog valid, ES watchdog gone" {
    es_server
    panel install_koha_indexer_service
    rm -f "$KEI_S/run/indexer"
    panel function_toggle_search_engine
    assert '[ "$(live_engine)" = "Zebra" ]'
    assert '[ ! -e /etc/cron.d/koha_es_watchdog ]'
    assert '! grep -q zebraqueue_daemon /etc/cron.d/koha_zebra_queue'
    assert '[ -e "$KEI_S/run/indexer" ]' "koha-indexer must be running after the switch"
    assert 'xmllint --noout /etc/koha/sites/library/koha-conf.xml'
}

@test "I17 <elasticsearch> is added to the main <config>, never inside Zebra's <server>" {
    cp "$KEI_REPO/tests/mocks/koha-conf.xml" "$BATS_TEST_TMPDIR/conf.xml"
    # Remove the stock block, as older panel versions did when going to Zebra.
    sed -i '/<!-- Elasticsearch Configuration/,/<\/elasticsearch>/d' /etc/koha/sites/library/koha-conf.xml
    panel set_xml_elasticsearch inserir
    local conf=/etc/koha/sites/library/koha-conf.xml
    assert '[ "$(xmllint --xpath "count(/yazgfs/config/elasticsearch)" $conf)" = "1" ]'
    assert '[ "$(xmllint --xpath "count(/yazgfs/server/config/elasticsearch)" $conf)" = "0" ]' "Zebra's <server><config> must stay a plain path"
    assert '[ "$(xmllint --xpath "string(/yazgfs/server/config)" $conf)" = "/etc/koha/sites/library/zebra-biblios-dom.cfg" ]'
    # Idempotent: a second call must not duplicate the block.
    panel set_xml_elasticsearch inserir
    assert '[ "$(xmllint --xpath "count(//elasticsearch)" $conf)" = "1" ]'
}

@test "I18 damage left by v1.0.1 (ES block inside Zebra's <config>) is repaired" {
    local conf=/etc/koha/sites/library/koha-conf.xml
    sed -i 's|<config>/etc/koha/sites/library/zebra-biblios-dom.cfg</config>|<config>/etc/koha/sites/library/zebra-biblios-dom.cfg  <elasticsearch>\n    <server>127.0.0.1:9200</server>\n    <index_name>koha_library</index_name>\n  </elasticsearch></config>|' "$conf"
    assert '[ "$(xmllint --xpath "count(/yazgfs/server/config/elasticsearch)" $conf)" = "1" ]' "fixture must reproduce the damage"
    panel repair_koha_conf_xml
    assert '[ "$(xmllint --xpath "string(/yazgfs/server/config)" $conf)" = "/etc/koha/sites/library/zebra-biblios-dom.cfg" ]'
    assert 'cmp -s "$conf" "$KEI_REPO/tests/mocks/koha-conf.xml"' "repair must give back the original file"
}

@test "I19 the search engine switch shows one line per task; the commands' output goes to search-engine.log" {
    es_server
    rm -f /var/log/koha-easy-install/search-engine.log
    panel function_toggle_search_engine
    assert '[ "$(live_engine)" = "Zebra" ]'
    assert 'echo "$output" | grep -q "Switching the search engine to Zebra"' "$output"
    assert 'echo "$output" | grep -q "Stopping Elasticsearch.*Done!"' "$output"
    assert 'echo "$output" | grep -q "Reindexing the catalog.*Done!"' "$output"
    assert '[ -s /var/log/koha-easy-install/search-engine.log ]'
    assert 'grep -q "=====.*se_task_es_off" /var/log/koha-easy-install/search-engine.log' "$(cat /var/log/koha-easy-install/search-engine.log)"
}
