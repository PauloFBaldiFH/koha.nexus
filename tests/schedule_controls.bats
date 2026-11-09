#!/usr/bin/env bats
# Real existing writers on disposable files; no services or application databases.
setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_BK_CRON="$T/platform-cron" KEI_SET_CRON="$T/set-cron" KEI_BK_NEED_CRON=0
    mkdir -p "$T/config" "$T/destination"
    printf 'PATH=/usr/local/bin:/usr/bin:/bin\n0 23 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1\n# custom\n3 4 * * * root echo preserved\n' > "$T/cron"
    cp "$T/cron" "$T/new"
    sed -i 's/0 23 /15 8 /' "$T/new"
}
lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
CRON_TASKS='$T/cron'
KEI_PANEL_COMMAND=/usr/local/bin/config.sh
KEI_BK_PLATFORMS=tainacan
require_koha() { return 0; }
log() { :; }
systemctl() { :; }
msg_ok() { :; }
msg_error() { :; }
kei_owned_add() { :; }
kei_owned_del() { :; }
_kei_bk_set() { printf '%s' \"\$2\" > '$T/config/'\"\$1\"; }
_kei_bk_get() { cat '$T/config/'\"\$1\" 2>/dev/null; }
$1"
}
@test "Koha schedule applies through existing writer and preserves manual task" {
    sha=$(sha256sum "$T/cron" | cut -d' ' -f1)
    run lib "cron_apply '$T/new' '$sha'"
    [ "$status" -eq 0 ]
    grep -q '^15 8 ' "$T/cron"
    grep -q '^3 4 .*echo preserved$' "$T/cron"
    grep -q '^0 23 ' "$T/cron.bak"
}
@test "stale Koha source rejects before replacing file or taking its backup" {
    sha=$(sha256sum "$T/cron" | cut -d' ' -f1)
    printf '# another editor\n' >> "$T/cron"
    cp "$T/cron" "$T/before"
    run lib "cron_apply '$T/new' '$sha'"
    [ "$status" -eq 4 ]
    cmp "$T/cron" "$T/before"
    [ ! -e "$T/cron.bak" ]
}
@test "Tainacan daily group updates all three linked tasks and disabling keeps configuration" {
    run lib "kei_backup_schedule tainacan 02:30"
    [ "$status" -eq 0 ]
    sha=$(sha256sum "$KEI_BK_CRON" | cut -d' ' -f1)
    run lib "kei_backup_schedule tainacan 08:15 '$sha'"
    [ "$status" -eq 0 ]
    grep -q '^15 8 .*platform-backup-run' "$KEI_BK_CRON"
    grep -q '^15 9 .*platform-backup-maintain' "$KEI_BK_CRON"
    grep -q '^15 10 .*platform-backup-verify' "$KEI_BK_CRON"
    printf keep > "$T/config/repository"
    sha=$(sha256sum "$KEI_BK_CRON" | cut -d' ' -f1)
    run lib "kei_backup_schedule tainacan off '$sha'"
    [ "$status" -eq 0 ]
    [ ! -e "$KEI_BK_CRON" ]
    [ "$(cat "$T/config/repository")" = keep ]
    [ ! -s "$T/config/schedule_tainacan" ]
}
@test "stale group change does not change its settings" {
    run lib "kei_backup_schedule tainacan 02:30"
    [ "$status" -eq 0 ]
    sha=$(sha256sum "$KEI_BK_CRON" | cut -d' ' -f1)
    printf '# changed\n' >> "$KEI_BK_CRON"
    run lib "kei_backup_schedule tainacan off '$sha'"
    [ "$status" -eq 4 ]
    [ "$(cat "$T/config/schedule_tainacan")" = 02:30 ]
    [ -f "$KEI_BK_CRON" ]
}
@test "joint schedule preserves destination and retention, then disables without a key" {
    printf '%s' "$T/destination" > "$T/config/set_dest"
    printf 13 > "$T/config/set_keep"
    printf no > "$T/config/set_secrets"
    run lib 'kei_set_schedule time=02:30'
    [ "$status" -eq 0 ]
    sha=$(sha256sum "$KEI_SET_CRON" | cut -d' ' -f1)
    run lib "kei_set_schedule time=09:45 expected=$sha"
    [ "$status" -eq 0 ]
    grep -q '^45 9 ' "$KEI_SET_CRON"
    [ "$(cat "$T/config/set_dest")" = "$T/destination" ]
    [ "$(cat "$T/config/set_keep")" = 13 ]
    sha=$(sha256sum "$KEI_SET_CRON" | cut -d' ' -f1)
    run lib "kei_set_schedule time=off expected=$sha"
    [ "$status" -eq 0 ]
    [ ! -e "$KEI_SET_CRON" ]
    [ "$(cat "$T/config/set_keep")" = 13 ]
}
@test "symlink cron and lock are refused" {
    ln -s "$T/elsewhere" "$T/cron.lock"
    run lib "cron_apply '$T/new'"
    [ "$status" -eq 4 ]
    [ ! -e "$T/elsewhere" ]
}
@test "grouped center refuses to overwrite a manual job even with the current revision" {
    run lib "kei_backup_schedule tainacan 02:30"
    [ "$status" -eq 0 ]
    printf '0 1 * * * root echo manual-job\n' >> "$KEI_BK_CRON"
    sha=$(sha256sum "$KEI_BK_CRON" | cut -d' ' -f1)
    run lib "kei_backup_schedule tainacan off '$sha'"
    [ "$status" -eq 4 ]
    grep -q 'echo manual-job' "$KEI_BK_CRON"
    [ "$(cat "$T/config/schedule_tainacan")" = 02:30 ]
}
