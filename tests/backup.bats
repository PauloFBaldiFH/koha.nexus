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
    assert '[ -z "$(ls /var/backups/koha_sql/*.sql.gz 2>/dev/null)" ]' "partial file must be removed"
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
