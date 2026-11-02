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
RCLONE_RATE_WAITS="0 0"
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
    if [ "$FAKE_MODE" = rate ] && [ "$(cat "$W/rate_left" 2>/dev/null || echo 0)" -gt 0 ]; then
        echo $(( $(cat "$W/rate_left") - 1 )) > "$W/rate_left"
        cat >&2 <<'JSON'
ERROR : Attempt 1/1 failed with 1 errors and: googleapi: Error 403: Quota exceeded for quota metric 'Queries' and limit 'Queries per minute' of service 'drive.googleapis.com' for consumer 'project_number:202264815644'.
Details:
[
  {
    "@type": "type.googleapis.com/google.rpc.Help",
    "links": [
      {
        "description": "Request a higher quota limit.",
        "url": "https://cloud.google.com/docs/quotas/help/request_increase"
      }
    ]
  }
]
, rateLimitExceeded
JSON
        exit 7
    fi
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

@test "C09 Google's rate limit is waited out and the test goes on" {
    fake_rclone
    export FAKE_MODE=rate FAKE_STEP=mkdir
    echo 2 > "$W/rate_left"
    run_fn validate_and_register_rclone gdrive
    [ "$status" -eq 0 ]
    [ "$(grep -c '^--contimeout.* mkdir gdrive:Backup_SQL_Koha$' "$W/rclone.log")" -eq 3 ]
    grep -qx 'RCLONE_REMOTE="gdrive"' "$W/backup.conf"
}

@test "C10 a rate limit that does not pass is explained, without Google's JSON" {
    fake_rclone
    export FAKE_MODE=rate FAKE_STEP=mkdir
    echo 9 > "$W/rate_left"
    run_fn validate_and_register_rclone gdrive
    [ "$status" -eq 1 ]
    [ "$(grep -c '^--contimeout.* mkdir gdrive:Backup_SQL_Koha$' "$W/rclone.log")" -eq 3 ]
    grep -q "ERROR .*write test failed.*too many requests (rateLimitExceeded).*shared by every rclone user.*own Google client id.*project_number:202264815644" "$KEI_S/dialogs.log"
    ! grep -q "google.rpc.Help" "$KEI_S/dialogs.log"
    [ ! -e "$W/backup.conf" ]
}

@test "C11 the nightly uploads try again with a pause, and old scripts are rewritten" {
    [ "$(grep -c 'copy --retries 4 --retries-sleep 60s' "$KEI_REPO/installer")" -eq 2 ]
    grep -q 'cloud_send "\\$FILE" "\\$RCLONE_SQL_FOLDER"' "$KEI_REPO/installer"
    grep -q 'cloud_send "\\$PACKAGE" "\\$RCLONE_MARC_FOLDER"' "$KEI_REPO/installer"
    [ "$(grep -c -- "grep -q -- '--retries-sleep' /root/backup_" "$KEI_REPO/installer")" -eq 2 ]
}

# rclone.conf as a list of "name type" lines ($W/remotes): enough of rclone
# for the tasks of the cloud backup screen.
conf_rclone() {
    cat > "$W/bin/rclone" <<'SH'
#!/bin/bash
printf '%s\n' "$*" >> "$W/rclone.log"
touch "$W/remotes"
case "$1 $2" in
    "listremotes --long") awk '{ printf "%s: %s\n", $1, $2 }' "$W/remotes"; exit 0 ;;
    "help backend") [ "$3" = nope ] && exit 1; exit 0 ;;
    "config create") grep -q "^$3 " "$W/remotes" && exit 1; echo "$3 $4" >> "$W/remotes"; exit 0 ;;
    "config update") grep -q "^$3 " "$W/remotes"; exit $? ;;
    "config delete") sed -i "/^$3 /d" "$W/remotes"; exit 0 ;;
esac
case "$1" in
    listremotes) awk '{ print $1 ":" }' "$W/remotes" ;;
    lsf) [ -e "$W/uploaded" ] && echo "kei-upload-test.txt" ;;
    copyto) touch "$W/uploaded" ;;
esac
for a in "$@"; do
    case "$a" in
        listremotes) awk '{ print $1 ":" }' "$W/remotes" ;;
        lsf) [ -e "$W/uploaded" ] && echo "kei-upload-test.txt" ;;
        copyto) touch "$W/uploaded" ;;
    esac
done
exit 0
SH
    chmod +x "$W/bin/rclone"
}

answers() { printf '%b' "$1" > "$W/answers.tsv"; chmod 600 "$W/answers.tsv"; }

@test "C12 cloud-save: any service from the panel's form, secrets obscured, the file deleted" {
    conf_rclone
    answers 'name\tlib\ntype\twebdav\nmode\tcreate\nopt\turl\thttps://cloud.example.org/remote.php/dav/files/koha\nopt\tvendor\tnextcloud\nopt\tpass\tS3cr3t pass\n'
    run_fn cloud_save "$W/answers.tsv"
    [ "$status" -eq 0 ]
    grep -qx 'config create lib webdav url https://cloud.example.org/remote.php/dav/files/koha vendor nextcloud pass S3cr3t pass --obscure --non-interactive' "$W/rclone.log"
    [ ! -e "$W/answers.tsv" ]
    ! grep -q 'S3cr3t' "$W/run.log" 2>/dev/null
}

@test "C13 cloud-save refuses a bad key, an unknown service and a name already taken" {
    conf_rclone
    answers 'name\tlib\ntype\twebdav\nmode\tcreate\nopt\tbad key\tx\n'
    run_fn cloud_save "$W/answers.tsv"
    [ "$status" -eq 1 ] && [ ! -e "$W/answers.tsv" ]
    answers 'name\tlib\ntype\tnope\nmode\tcreate\n'
    run_fn cloud_save "$W/answers.tsv"
    [ "$status" -eq 1 ]
    grep -q "does not know the service 'nope'" "$KEI_S/dialogs.log"
    echo "lib webdav" > "$W/remotes"
    answers 'name\tlib\ntype\twebdav\nmode\tcreate\n'
    run_fn cloud_save "$W/answers.tsv"
    [ "$status" -eq 1 ]
    grep -q "already a connection called 'lib'" "$KEI_S/dialogs.log"
    ! grep -q 'config create' "$W/rclone.log"
}

@test "C14 cloud-save update changes only what was sent; encryption adds NAME-crypt inside the bucket" {
    conf_rclone
    echo "box s3" > "$W/remotes"
    answers 'name\tbox\ntype\ts3\nmode\tupdate\nopt\tregion\tsa-east-1\ncrypt\tlong password!\ncryptdir\tmy-bucket\n'
    run_fn cloud_save "$W/answers.tsv"
    [ "$status" -eq 0 ]
    grep -qx 'config update box region sa-east-1 --obscure --non-interactive' "$W/rclone.log"
    grep -q '^config create box-crypt crypt remote box:my-bucket/KohaNexus_encrypted password long password! ' "$W/rclone.log"
}

@test "C15 a chosen folder: the test and the destination use BASE/Backup_SQL_Koha" {
    conf_rclone
    echo "gdrive drive" > "$W/remotes"
    run_fn validate_and_register_rclone gdrive "/koha/my library/"
    [ "$status" -eq 0 ]
    grep -q 'mkdir gdrive:koha/my library/Backup_SQL_Koha' "$W/rclone.log"
    grep -qx 'RCLONE_SQL_FOLDER="koha/my library/Backup_SQL_Koha"' "$W/backup.conf"
    grep -qx 'RCLONE_MARC_FOLDER="koha/my library/Backup_MARC_Koha"' "$W/backup.conf"
    run_fn validate_and_register_rclone gdrive "a/../b"
    [ "$status" -eq 1 ]
}

@test "C16 cloud-settings: checked values written, anything else refuses the whole file" {
    conf_rclone
    echo "wasabi s3" > "$W/remotes"
    printf 'RCLONE_REMOTE="gdrive"\n' > "$W/backup.conf"
    printf 'CLOUD_KEEP_DAYS\t30\nKEEP_DAYS\t10\nRCLONE_REMOTE2\twasabi\nRCLONE_BWLIMIT\t08:00,1M 19:00,off\nCLOUD_MARC\tno\n' > "$W/s.tsv"
    run_fn cloud_settings "$W/s.tsv"
    [ "$status" -eq 0 ]
    grep -qx 'CLOUD_KEEP_DAYS="30"' "$W/backup.conf"
    grep -qx 'KEEP_DAYS="10"' "$W/backup.conf"
    grep -qx 'RCLONE_REMOTE2="wasabi"' "$W/backup.conf"
    grep -qx 'RCLONE_BWLIMIT="08:00,1M 19:00,off"' "$W/backup.conf"
    grep -qx 'RCLONE_REMOTE="gdrive"' "$W/backup.conf"
    [ ! -e "$W/s.tsv" ]
    cp "$W/backup.conf" "$W/before.conf"
    for bad in 'CLOUD_KEEP_DAYS\tx' 'RCLONE_REMOTE2\tghost' 'RCLONE_BWLIMIT\t$(reboot)' 'EVIL\t1' 'KEEP_DAYS\t0'; do
        printf "${bad}\n" > "$W/s.tsv"
        run_fn cloud_settings "$W/s.tsv"
        [ "$status" -eq 1 ]
        cmp "$W/backup.conf" "$W/before.conf"
    done
}

@test "C17 cloud-delete removes the connection and clears it as destination or second copy" {
    conf_rclone
    printf 'gdrive drive\nwasabi s3\n' > "$W/remotes"
    printf 'RCLONE_REMOTE="gdrive"\nRCLONE_REMOTE2="wasabi"\n' > "$W/backup.conf"
    run_fn cloud_delete wasabi
    [ "$status" -eq 0 ]
    grep -qx 'RCLONE_REMOTE2=""' "$W/backup.conf"
    grep -qx 'RCLONE_REMOTE="gdrive"' "$W/backup.conf"
    ! grep -q '^wasabi' "$W/remotes"
}

@test "C18 cloud-get and cloud-rm take only Koha backups, inside a known connection" {
    conf_rclone
    echo "gdrive drive" > "$W/remotes"
    run_fn cloud_rm "gdrive:Backup_SQL_Koha/notes.txt"
    [ "$status" -eq 1 ]
    run_fn cloud_rm "ghost:Backup_SQL_Koha/koha_library_2026-11-02_23h00.sql.gz"
    [ "$status" -eq 1 ]
    run_fn cloud_rm "gdrive:../Backup_SQL_Koha/koha_library_2026-11-02_23h00.sql.gz"
    [ "$status" -eq 1 ]
    ! grep -q deletefile "$W/rclone.log"
    run_fn cloud_rm "gdrive:Backup_SQL_Koha/koha_library_2026-11-02_23h00.sql.gz"
    [ "$status" -eq 0 ]
    grep -q 'deletefile gdrive:Backup_SQL_Koha/koha_library_2026-11-02_23h00.sql.gz' "$W/rclone.log"
}
