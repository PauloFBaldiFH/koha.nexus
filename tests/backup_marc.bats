#!/usr/bin/env bats
# The MARC21 backup (/root/backup_marc.sh) and its cloud upload, and the
# catch-up of a missed scheduled run by the nightly SQL backup.
#
# Needs no database: mysqldump, koha-shell and rclone are doubles. The
# scripts live at fixed paths (/root, /usr/sbin/koha-shell, /usr/bin/rclone),
# so, like the rest of the battery, run it as root in a throwaway container
# (tests/run.sh tests/backup_marc.bats). Whatever was at those paths is put
# back afterwards.

KEI_REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"

setup() {
    [ "$(id -u)" = 0 ] || skip "needs root (fixed script paths)"
    W="$BATS_TEST_TMPDIR"
    mkdir -p "$W/bin" "$W/keep" "$W/log" /root/.config/rclone /usr/share/koha/bin /var/lock
    for f in /root/backup_sql.sh /root/backup_marc.sh /usr/sbin/koha-shell /usr/bin/rclone \
             /root/.config/rclone/rclone.conf /usr/share/koha/bin/export_records.pl; do
        [ -e "$f" ] && cp -p "$f" "$W/keep/$(echo "$f" | tr / _)"
    done
    : > /usr/share/koha/bin/export_records.pl
    # koha-shell: one tiny ISO 2709 record per export (bibs and auths).
    cat > /usr/sbin/koha-shell <<'EOF'
#!/bin/bash
printf '00026nam a2200025 a 4500\036\035'
EOF
    cat > /usr/bin/rclone <<EOF
#!/bin/bash
echo "\$*" >> "$W/rclone.calls"
case "\$1" in listremotes) echo "gdrive:" ;; esac
exit 0
EOF
    # mysqldump: a complete dump, big enough for the 10 KB check.
    cat > "$W/bin/mysqldump" <<'EOF'
#!/bin/bash
head -c 30000 /dev/urandom | base64
echo "-- Dump completed on 2026-10-31"
EOF
    chmod +x /usr/sbin/koha-shell /usr/bin/rclone "$W/bin/mysqldump"
    printf '[gdrive]\ntype = drive\n' > /root/.config/rclone/rclone.conf
    export PATH="$W/bin:$PATH"
    cron_line "0 3 * * 0 root /bin/bash /root/backup_marc.sh >/dev/null 2>&1"
    write_scripts
}

teardown() {
    [ -n "${W:-}" ] || return 0
    for f in /root/backup_sql.sh /root/backup_marc.sh /usr/sbin/koha-shell /usr/bin/rclone \
             /root/.config/rclone/rclone.conf /usr/share/koha/bin/export_records.pl; do
        k="$W/keep/$(echo "$f" | tr / _)"
        if [ -e "$k" ]; then cp -p "$k" "$f"; else rm -f "$f"; fi
    done
    rm -f /var/lock/koha_backup.lock
}

cron_line() {
    printf 'PATH=/usr/sbin:/usr/bin:/sbin:/bin\n0 23 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1\n%s\n' "$1" > "$W/koha_tasks"
}

# The installer's own write_backup_scripts, pointed at this test's folders.
write_scripts() {
    run bash -c '
        source "$1/installer" >/dev/null 2>&1
        BACKUP_CONF="$2/backup.conf" DIR_SQL="$2/sql" DIR_MARC="$2/marc" LOG_DIR="$2/log" CRON_TASKS="$2/koha_tasks"
        write_backup_scripts' _ "$KEI_REPO" "$W"
    [ "$status" -eq 0 ]
    sed -i 's/^RCLONE_REMOTE=.*/RCLONE_REMOTE="gdrive"/' "$W/backup.conf"
}

marc_packages() { find "$W/marc" -maxdepth 1 -name 'koha_marc_*.tar.gz' 2>/dev/null | wc -l; }
marc_uploads() { cat "$W/rclone.calls" 2>/dev/null | grep -c 'Backup_MARC_Koha/' || true; }
old_package() {   # a package made $1 days ago
    mkdir -p "$W/marc"
    : > "$W/marc/koha_marc_2020-01-01_0300.tar.gz"
    touch -d "$1 days ago" "$W/marc/koha_marc_2020-01-01_0300.tar.gz"
}

@test "M01 MARC21 backup: package made and sent to the MARC cloud folder" {
    run bash /root/backup_marc.sh
    [ "$status" -eq 0 ]
    [ "$(marc_packages)" -eq 1 ]
    [ "$(marc_uploads)" -eq 1 ]
    grep -q '| Cloud OK: gdrive:Backup_MARC_Koha/' "$W/log/backup_marc.log"
}

@test "M02 MARC21 backup works when the log folder is missing" {
    rm -rf "$W/log"
    run bash /root/backup_marc.sh
    [ "$status" -eq 0 ]
    grep -q '| OK: ' "$W/log/backup_marc.log"
}

@test "M03 --if-due: weekly schedule and no package yet -> runs and uploads" {
    run bash /root/backup_marc.sh --if-due
    [ "$status" -eq 0 ]
    [ "$(marc_uploads)" -eq 1 ]
    grep -q 'INFO: catching up the scheduled MARC backup (none in the last 7 days)' "$W/log/backup_marc.log"
}

@test "M04 --if-due: weekly schedule, package from 3 days ago -> nothing" {
    old_package 3
    run bash /root/backup_marc.sh --if-due
    [ "$status" -eq 0 ]
    [ "$(marc_uploads)" -eq 0 ]
    [ ! -s "$W/log/backup_marc.log" ]
}

@test "M05 --if-due: weekly schedule, package from 8 days ago -> runs" {
    old_package 8
    run bash /root/backup_marc.sh --if-due
    [ "$(marc_uploads)" -eq 1 ]
}

@test "M06 --if-due: a schedule switched off in the panel never runs" {
    cron_line "#off# 0 3 * * 0 root /bin/bash /root/backup_marc.sh >/dev/null 2>&1"
    run bash /root/backup_marc.sh --if-due
    [ "$status" -eq 0 ]
    [ "$(marc_uploads)" -eq 0 ]
}

@test "M07 --if-due: the period follows the schedule (daily 1 day, monthly 31 days)" {
    old_package 2
    cron_line "0 3 * * * root /bin/bash /root/backup_marc.sh >/dev/null 2>&1"
    run bash /root/backup_marc.sh --if-due
    [ "$(marc_uploads)" -eq 1 ]

    rm -f "$W/rclone.calls" "$W"/marc/*
    old_package 10
    cron_line "0 3 5 * * root /bin/bash /root/backup_marc.sh >/dev/null 2>&1"
    run bash /root/backup_marc.sh --if-due
    [ "$(marc_uploads)" -eq 0 ]
}

@test "M08 nightly SQL backup uploads its dump, then catches up the missed MARC21 run" {
    old_package 9
    run bash /root/backup_sql.sh
    [ "$status" -eq 0 ]
    grep -q 'Backup_SQL_Koha/' "$W/rclone.calls"
    [ "$(marc_uploads)" -eq 1 ]
    ! grep -q 'skipped because another backup' "$W/log/backup_marc.log"
}

@test "M09 nightly SQL backup leaves MARC21 alone when it ran this week or with KEI_NO_MARC_CATCHUP" {
    old_package 2
    run bash /root/backup_sql.sh
    [ "$(marc_uploads)" -eq 0 ]

    rm -f "$W"/marc/*
    KEI_NO_MARC_CATCHUP=1 run bash /root/backup_sql.sh
    [ "$status" -eq 0 ]
    grep -q 'Backup_SQL_Koha/' "$W/rclone.calls"
    [ "$(marc_uploads)" -eq 0 ]
}
