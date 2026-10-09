#!/usr/bin/env bats
# Cloud backup set-up: the "Testing the real cloud upload..." step. Every
# rclone call is bounded (rclone's own limits and timeout(1)), a failure
# shows rclone's own words and saves nothing, and the pasted Google Drive
# token is cleaned before it reaches rclone.conf. A stand-in rclone plays
# the cloud (it can answer, fail or stall); the token tests use the real
# rclone when it is installed.

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    rm -f "$KEI_S/dialogs.log"
    mkdir -p "$W/bin"
    cat > "$W/extra.sh" <<SH
SYS_LANG=en
require_database() { return 0; }
rclone_prepare() { return 0; }
BACKUP_CONF="$W/backup.conf"
LOG_DIR="$W"
RUN_LOG="$W/run.log"
TUI_LOG="$W/tui.log"
write_backup_config() { touch "\$BACKUP_CONF"; }
kei_first_cloud_backup() { echo "FIRST BACKUP" >> "$W/calls"; }
RCLONE_TEST_SECS=2
PATH="$W/bin:\$PATH"
SH
    export FAKE_MODE=ok FAKE_STEP=none W
}

run_fn() { run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" "$@"; }

# FAKE_STEP (mkdir, copyto, lsf) fails (FAKE_MODE=fail) or stalls (hang).
fake_rclone() {
    cat > "$W/bin/rclone" <<'SH'
#!/bin/bash
printf '%s\n' "$*" >> "$W/rclone.log"
args=("$@")
for a in "${args[@]}"; do
    case "$a" in -*|[0-9]*s|1) ;; *) cmd=$a; break ;; esac
done
if [ "$cmd" = "${FAKE_STEP:-}" ]; then
    [ "$FAKE_MODE" = hang ] && exec sleep 600
    [ "$FAKE_MODE" = fail ] && { echo "ERROR : Backup_SQL_Koha: googleapi: Error 403: The user's Drive storage quota has been exceeded." >&2; exit 7; }
fi
case "$cmd" in
    listremotes) echo "gdrive:" ;;
    lsf) touch "$W/listed"; [ -e "$W/uploaded" ] && echo "kei-upload-test.txt" ;;
    copyto) touch "$W/uploaded" ;;
esac
exit 0
SH
    chmod +x "$W/bin/rclone"
}

@test "C01 a stalled cloud stops the test within the limit, says so, and saves nothing" {
    fake_rclone
    export FAKE_MODE=hang FAKE_STEP=copyto
    SECONDS=0
    run_fn validate_and_register_rclone gdrive
    [ "$status" -eq 1 ]
    [ "$SECONDS" -lt 15 ]
    grep -q "ERROR .*test upload to gdrive:Backup_SQL_Koha failed.*did not answer within 2 seconds" "$KEI_S/dialogs.log"
    [ ! -e "$W/backup.conf" ]
    [ ! -e "$W/calls" ]
    ! pgrep -f "sleep 600" >/dev/null
}

@test "C02 every rclone call of the test carries the strict limits" {
    fake_rclone
    run_fn validate_and_register_rclone gdrive
    [ "$status" -eq 0 ]
    for cmd in "mkdir gdrive:Backup_SQL_Koha" "copyto " "lsf gdrive:Backup_SQL_Koha" "deletefile "; do
        grep -F -- "--contimeout 15s --timeout 20s --retries 1 --low-level-retries 1 $cmd" "$W/rclone.log"
    done
}

@test "C03 a refused write shows rclone's own error and saves nothing" {
    fake_rclone
    export FAKE_MODE=fail FAKE_STEP=mkdir
    run_fn validate_and_register_rclone gdrive
    [ "$status" -eq 1 ]
    grep -q "ERROR .*write test failed.*storage quota has been exceeded" "$KEI_S/dialogs.log"
    [ ! -e "$W/uploaded" ]
    [ ! -e "$W/backup.conf" ]
}

@test "C04 a stalled mkdir is stopped too" {
    fake_rclone
    export FAKE_MODE=hang FAKE_STEP=mkdir
    SECONDS=0
    run_fn validate_and_register_rclone gdrive
    [ "$status" -eq 1 ]
    [ "$SECONDS" -lt 15 ]
    grep -q "ERROR .*write test failed.*did not answer within 2 seconds" "$KEI_S/dialogs.log"
}

@test "C05 success: a test file is sent, read back and removed, then the remote is saved" {
    fake_rclone
    run_fn validate_and_register_rclone gdrive
    [ "$status" -eq 0 ]
    [ -e "$W/uploaded" ] && [ -e "$W/listed" ]
    grep -q "deletefile gdrive:Backup_SQL_Koha/kei-upload-test.txt" "$W/rclone.log"
    grep -qx 'RCLONE_REMOTE="gdrive"' "$W/backup.conf"
    grep -qx "FIRST BACKUP" "$W/calls"
    grep -q "^OK Cloud enabled and tested successfully" "$KEI_S/dialogs.log"
    [ -z "$(ls /tmp/kei-cloud-test.* 2>/dev/null)" ]
}

TOKEN='{"access_token":"ya29.A","token_type":"Bearer","refresh_token":"1//R","expiry":"2026-09-28T15:00:00.1-03:00"}'

@test "C06 the pasted token is cleaned: line breaks, BOM, quotes and PowerShell escaping" {
    local bom=$'\xef\xbb\xbf' messy
    for messy in \
        "$TOKEN"$'\r\n' \
        "  ${TOKEN:0:40}"$'\n'"${TOKEN:40}  " \
        "${bom}${TOKEN}" \
        "'${TOKEN}'" \
        "${TOKEN//\"/\\\"}" \
        "${TOKEN//\"access_token\"/“access_token”}"; do
        run env KEI_EXTRA="$W/extra.sh" PASTE="$messy" bash "$PANEL" eval 'rclone_token_clean "$PASTE"; echo "rc=$? $REPLY"' 
        [ "${lines[-1]}" = "rc=0 $TOKEN" ]
    done
    run env KEI_EXTRA="$W/extra.sh" PASTE="${TOKEN:0:60}}" bash "$PANEL" eval 'rclone_token_clean "$PASTE"; echo "rc=$?"' 
    [ "${lines[-1]}" = "rc=1" ]
}

@test "C07 rclone.conf gets the token on one line and it reads back as JSON" {
    [ -x /usr/bin/rclone ] || skip "rclone is not installed"
    printf 'RCLONE_CONFIG="%s/rclone.conf"\nexport RCLONE_CONFIG\nPATH=/usr/bin:$PATH\n' "$W" >> "$W/extra.sh"
    run env KEI_EXTRA="$W/extra.sh" PASTE="  ${TOKEN//\"/\\\"}"$'\r\n' bash "$PANEL" eval 'rclone_create_gdrive "$PASTE"; echo "rc=$?"' 
    [ "${lines[-1]}" = "rc=0" ]
    grep -qxF "token = $TOKEN" "$W/rclone.conf"
    [ "$(grep -c '^token = ' "$W/rclone.conf")" -eq 1 ]
}

@test "C08 a token that rclone cannot use is refused before rclone.conf is touched" {
    [ -x /usr/bin/rclone ] || skip "rclone is not installed"
    printf 'RCLONE_CONFIG="%s/rclone.conf"\nexport RCLONE_CONFIG\nPATH=/usr/bin:$PATH\n' "$W" >> "$W/extra.sh"
    run env KEI_EXTRA="$W/extra.sh" PASTE='{"access_token":"a" "refresh_token":"r","expiry":"x"}' bash "$PANEL" eval 'rclone_create_gdrive "$PASTE"; echo "rc=$?"' 
    [ "${lines[-1]}" = "rc=1" ]
    [ ! -s "$W/rclone.conf" ] || ! grep -q '^\[gdrive\]' "$W/rclone.conf"
}
