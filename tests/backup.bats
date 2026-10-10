#!/usr/bin/env bats
# Backups: the nightly cron script, the manual backup and the "test the
# latest backup" routine (which must never touch production).

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_backup_fixtures
    unset KEI_SELECT_DIR KEI_EXTRA KEI_DEFAULT_ANSWER
    panel write_backup_scripts
}

teardown() {
    mountpoint -q /var/backups/koha_sql 2>/dev/null && umount /var/backups/koha_sql
    kei_start_mariadb
}

old_backup() {   # an older, valid backup that must survive failed runs
    mkdir -p /var/backups/koha_sql
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/koha_library_2020-01-01_23h00.sql.gz
    touch -d '3 days ago' /var/backups/koha_sql/koha_library_2020-01-01_23h00.sql.gz
}

@test "B01 'test latest backup' never writes into production (dump made with --databases)" {
    kei_make_catalog koha_library ANCIENT 50
    mkdir -p /var/backups/koha_sql
    kei_dump koha_library /var/backups/koha_sql/koha_library_2026-01-01_23h00.sql.gz --databases
    kei_reset_live_catalog
    panel function_test_backup
    assert_catalog_untouched
    assert '! mysql -e "USE koha_teste_restauracao" 2>/dev/null' "test database must be dropped"
}

@test "B02 'test latest backup' reports a truncated backup without touching production" {
    mkdir -p /var/backups/koha_sql
    head -c 4000 "$FIX/new.sql.gz" > /var/backups/koha_sql/koha_library_2026-01-01_23h00.sql.gz
    panel function_test_backup
    assert '[ "$status" -ne 0 ]'
    assert_catalog_untouched
    assert 'dialogs | grep -q "^ERROR"'
}

@test "B03 nightly backup: valid gzip, complete mysqldump, restorable" {
    run "$KEI_SH" /root/backup_sql.sh
    assert '[ "$status" -eq 0 ]'
    local f; f=$(ls /var/backups/koha_sql/koha_library_*.sql.gz | head -n1)
    assert 'gzip -t "$f"'
    assert 'zcat "$f" | tail -n1 | grep -q "^-- Dump completed"'
    assert 'grep -q "OK:" /var/log/koha-easy-install/backup_sql.log'
}

@test "B04 nightly backup with MariaDB down: fails, leaves no file, keeps older backups" {
    old_backup
    kei_stop_mariadb
    run "$KEI_SH" /root/backup_sql.sh
    kei_start_mariadb
    assert '[ "$status" -ne 0 ]'
    assert '[ "$(ls /var/backups/koha_sql | wc -l)" = "1" ]' "only the older backup may remain"
}

@test "B05 nightly backup on a full disk: fails, leaves no partial file" {
    mkdir -p /var/backups/koha_sql
    mount -t tmpfs -o size=8k tmpfs /var/backups/koha_sql
    run "$KEI_SH" /root/backup_sql.sh
    assert '[ "$status" -ne 0 ]'
    assert '[ -z "$(ls -A /var/backups/koha_sql 2>/dev/null)" ]' "partial file (.part included) must be removed"
}

@test "B06 nightly backup keeps older backups when the new one fails the size check" {
    old_backup
    mysql -e "DROP DATABASE koha_library; CREATE DATABASE koha_library;"
    run "$KEI_SH" /root/backup_sql.sh
    assert '[ "$status" -ne 0 ]'
    assert '[ -f /var/backups/koha_sql/koha_library_2020-01-01_23h00.sql.gz ]'
}

@test "B07 manual backup: complete dump in the chosen folder" {
    export KEI_SELECT_DIR="$BATS_TEST_TMPDIR"
    panel function_manual_backup
    local f; f=$(ls "$BATS_TEST_TMPDIR"/koha_library_manual_*.sql.gz | head -n1)
    assert '[ -n "$f" ] && gzip -t "$f"'
    assert 'zcat "$f" | tail -n1 | grep -q "^-- Dump completed"'
    assert 'flock -n /var/lock/koha_backup.lock true'
}

@test "B08 manual backup into an unwritable destination: error and no partial file" {
    : > "$BATS_TEST_TMPDIR/not-a-dir"
    export KEI_SELECT_DIR="$BATS_TEST_TMPDIR/not-a-dir"
    panel function_manual_backup
    assert 'dialogs | grep -q "^ERROR"'
    assert 'flock -n /var/lock/koha_backup.lock true'
}

# --- The newest backup (latest_sql_backup): one answer for the dashboard,
# Download latest backup, Test the latest backup and the validation report.

newest_name() { panel latest_sql_backup; local f; f=$(printf '%s' "$output" | cut -d' ' -f4-); printf '%s' "${f##*/}"; }

@test "B09 the newest backup is read from the date in its name, not from a copy's mtime" {
    mkdir -p /var/backups/koha_sql
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/koha_library_2026-10-09_23h00.sql.gz
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/koha_library_2026-10-01_23h00.sql.gz   # copied back today
    touch -d '2 days ago' /var/backups/koha_sql/koha_library_2026-10-09_23h00.sql.gz
    assert '[ "$(newest_name)" = "koha_library_2026-10-09_23h00.sql.gz" ]'
    panel latest_sql_backup
    assert '[ "${output%% *}" = "$(date -d "2026-10-09 23:00" +%s)" ]' "epoch from the name"
    # Safety copies count too, seconds included in their name.
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/pre_restore_safety_backup_2026-10-10_09h15m30.sql.gz
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/PRE-UPDATE_2026-10-10_09h1500.sql.gz
    assert '[ "$(newest_name)" = "pre_restore_safety_backup_2026-10-10_09h15m30.sql.gz" ]'
    panel newest_sql_backup
    assert '[ "$output" = /var/backups/koha_sql/pre_restore_safety_backup_2026-10-10_09h15m30.sql.gz ]'
}

@test "B10 a dump in progress, an empty file and subfolders never count as the newest backup" {
    mkdir -p /var/backups/koha_sql/old
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/koha_library_2026-10-01_23h00.sql.gz
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/koha_library_2026-10-09_23h00.sql.gz.part
    : > /var/backups/koha_sql/koha_library_2026-10-08_23h00.sql.gz
    cp "$FIX/new.sql.gz" /var/backups/koha_sql/old/koha_library_2026-10-07_23h00.sql.gz
    assert '[ "$(newest_name)" = "koha_library_2026-10-01_23h00.sql.gz" ]'
    # A name without a date: its mtime decides.
    cp "$FIX/new.sql.gz" "/var/backups/koha_sql/my copy.sql.gz"
    assert '[ "$(newest_name)" = "my copy.sql.gz" ]'
    rm -rf /var/backups/koha_sql/*
    panel latest_sql_backup
    assert '[ "$status" -eq 0 ] && [ -z "$output" ]'
}

@test "B11 status json: newest backup, its kind and nothing when there is none" {
    rm -f /var/log/koha-easy-install/backup_sql.log
    panel kei_backup_summary
    assert '[ "$output" = "0 0 none none " ]' "got '$output'"
    run "$KEI_SH" /root/backup_sql.sh
    panel kei_backup_summary
    read -r epoch size result kind file <<< "$output"
    assert '[ "$result" = ok ] && [ "$kind" = nightly ] && [ "$size" -gt 10240 ]' "got '$output'"
    assert '[ $(( $(date +%s) - epoch )) -lt 120 ]'
    assert '[ -z "$(ls /var/backups/koha_sql/*.part 2>/dev/null)" ]' "the .part is renamed"
}

@test "B12 a manual backup saved elsewhere counts as the newest while its file is there" {
    old_backup
    export KEI_SELECT_DIR="$BATS_TEST_TMPDIR"
    panel function_manual_backup
    local f; f=$(ls "$BATS_TEST_TMPDIR"/koha_library_manual_*.sql.gz | head -n1)
    panel newest_sql_backup
    assert '[ "$output" = "$f" ]' "got '$output'"
    panel kei_backup_summary
    assert 'echo "$output" | grep -q " manual "'
    rm -f "$f"
    assert '[ "$(newest_name)" = "koha_library_2020-01-01_23h00.sql.gz" ]'
}

# --- Restore: the safety copy of the current database comes first.

@test "B13 restore: pre_restore_safety_backup of the current database before it is replaced" {
    export KEI_SELECT_FILE="$FIX/new.sql.gz"
    panel function_restore_database
    assert '[ "$(live_marker)" = "NEW" ]'
    local f; f=$(ls /var/backups/koha_sql/pre_restore_safety_backup_*.sql.gz | head -n1)
    assert '[[ "${f##*/}" =~ ^pre_restore_safety_backup_[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}h[0-9]{2}m[0-9]{2}\.sql\.gz$ ]]' "got '$f'"
    assert 'zcat "$f" | grep -q "OLD"' "the safety copy holds the catalog from before the restore"
    assert 'grep -q "pre-restore safety backup: $f" /var/log/koha-easy-install/*.log'
}

@test "B14 restore: when the safety backup fails, nothing is restored" {
    cat > "$BATS_TEST_TMPDIR/extra.sh" <<'EOF'
create_safety_backup() { : > "$1.part"; rm -f "$1.part"; return 1; }
EOF
    export KEI_EXTRA="$BATS_TEST_TMPDIR/extra.sh" KEI_SELECT_FILE="$FIX/new.sql.gz"
    panel function_restore_database
    assert '[ "$status" -ne 0 ]'
    assert_catalog_untouched
    assert 'dialogs | grep -q "Safety backup failed"'
    assert 'grep -q "restore aborted: the pre-restore safety backup failed" /var/log/koha-easy-install/*.log'
    assert 'flock -n /var/lock/koha_backup.lock true'
}
