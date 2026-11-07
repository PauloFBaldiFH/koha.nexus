#!/usr/bin/env bats
# Koha is optional: the "platforms" field of --status-json, the guard that
# refuses Koha actions and tasks on a server without Koha, and the first
# run that installs "sudo config.sh" before any Koha installation. The
# installer is loaded as a library; nothing here needs Koha, MariaDB or
# systemd.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    export KEI_PANEL_COMMAND="$W/bin/config.sh"
    mkdir -p "$W/bin"
}

# lib CODE: runs CODE with the installer loaded; Koha present when $W/koha exists.
lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
is_koha_installed() { [ -e '$W/koha' ]; }
msg_error() { printf 'ERROR %s\n' \"\$2\"; }
$1"
}

valid_json() { printf '%s' "$1" | python3 -c 'import json,sys; json.load(sys.stdin)'; }

@test "without Koha: koha not detected, services none, DSpace optional and AtoM planned" {
    run lib 'kei_platforms_json apache2=active mariadb=active'
    [ "$status" -eq 0 ]
    valid_json "$output"
    run python3 -c 'import json,sys; p=json.loads(sys.argv[1]); print(" ".join("%s:%s:%s:%s:%s" % (x["id"], x["supported"], x["detected"], x["services"], x["health"]) for x in p))' "$output"
    [ "$output" = "koha:True:False:none:unknown tainacan:True:False:none:unknown dspace:True:False:none:unknown atom:False:None:none:unknown" ]
}

@test "with Koha: services summarised, health never claimed" {
    touch "$W/koha"
    run lib 'kei_platforms_json apache2=active mariadb=active memcached=active koha-common=active cron=inactive'
    valid_json "$output"
    [[ "$output" == *'"id":"koha","supported":true,"detected":true,"services":"active"'* ]]
    [[ "$output" == *'"health":"unknown"'* ]]
    [[ "$output" != *'"cron"'* ]]
    run lib 'kei_platforms_json apache2=active mariadb=failed'
    [[ "$output" == *'"services":"partial"'* ]]
    [[ "$output" == *'"memcached":"unknown"'* ]]
    run lib 'kei_services_summary inactive failed; echo; kei_services_summary unknown unknown; echo; kei_services_summary'
    [ "${lines[0]}" = "inactive" ] && [ "${lines[1]}" = "unknown" ] && [ "${lines[2]}" = "none" ]
}

@test "--status-json keeps its fields and adds platforms" {
    run lib 'systemctl() { echo inactive; }; kei_http_code() { echo 000; }; plack_running() { false; }
kei_status_json'
    [ "$status" -eq 0 ]
    valid_json "$output"
    run python3 -c 'import json,sys; d=json.loads(sys.argv[1])
for k in ("schema","generated_at","panel_version","platform","state","koha_installed","services","plack","http","backup","recovery","disk","memory","platforms"):
    assert k in d, k
assert d["schema"] == 1 and d["koha_installed"] is False
print(d["state"], [p["id"] for p in d["platforms"]])' "$output"
    [ "$status" -eq 0 ]
    [ "$output" = "not_installed ['koha', 'tainacan', 'dspace', 'atom']" ]
}

@test "Koha actions and tasks are refused without Koha, shared ones are not" {
    run lib 'kei_action_needs_koha backup-manual && echo yes; kei_action_needs_koha languages || echo no; kei_action_needs_koha update-panel || echo no'
    [ "$output" = "$(printf 'yes\nno\nno')" ]
    run lib 'for t in backup-manual restore z3950-sync opac-theme-apply health; do kei_task_needs_koha $t || echo "free $t"; done
for t in info install timezones status clock ufw vpn-status run tool-install validation-report; do kei_task_needs_koha $t && echo "koha $t"; done; true'
    [ -z "$output" ]
}

@test "config.sh --task stops a Koha routine on a server without Koha" {
    [ ! -e /etc/koha/sites/library/koha-conf.xml ] || skip "Koha is installed here"
    run bash "$REPO/installer" --task backup-manual "$W/backup.sql.gz"
    [ "$status" -eq 1 ]
    [[ "$output" == *"@@msg error"* ]]
    [ ! -e "$W/backup.sql.gz" ]
    run bash "$REPO/installer" --task run backup-manual
    [ "$status" -eq 1 ]
    [[ "$output" == *"@@msg error"* ]]
    # A shared routine is not refused.
    run bash "$REPO/installer" --task run about </dev/null
    [ "$status" -eq 0 ]
    [[ "$output" != *"@@msg error"* ]]
}

@test "first run installs config.sh without Koha, once" {
    run lib "_SCRIPT_PATH='$REPO/installer'; _SCRIPT_DIR='$W/none'; install_linux_launcher() { :; }
kei_first_run_panel_copy && echo copied; kei_first_run_panel_copy || echo kept"
    [ "$output" = "$(printf 'copied\nkept')" ]
    cmp -s "$REPO/installer" "$KEI_PANEL_COMMAND"
    [ -x "$KEI_PANEL_COMMAND" ]
}

@test "a run from a pipe has nothing to copy" {
    run lib "_SCRIPT_PATH='/dev/fd/63'; kei_first_run_panel_copy || echo none"
    [ "$output" = "none" ]
    [ ! -e "$KEI_PANEL_COMMAND" ]
}
