#!/usr/bin/env bats
# Administrative access and the steps after a new installation (installer:
# kei_koha_admin_*, kei_tainacan_admin_*, kei_setup_*). No Koha, no Docker:
# Koha's superlibrarians are a text file behind run_sql and a stand-in
# koha-shell; WordPress is a text file behind _kei_tn_wp. Covered: the
# password only travels on standard input (never in a command line, a log,
# the output or the result lines), it is read once and cleared from the
# environment; short ones and line breaks are refused before anything; an
# existing account is never recreated and only the chosen one changes; the
# site's keys stay; the setup file holds only states, is created only by a
# new installation and follows the real state.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export T PW='Correct-Horse-9'
    export KEI_SETUP_DIR="$T/setup" KEI_TAINACAN_DIR="$T/tainacan" KEI_KOHA_SHELL="$T/koha-shell"
    mkdir -p "$KEI_TAINACAN_DIR"
    # Koha: userid|flags (1 = superlibrarian)
    printf 'admin|1\nmaria|0\n' > "$T/koha_users"
    # WordPress: login|role|password|email
    printf 'kn_ab12|administrator|gen-Pass-123456|admin@x.invalid\njoao|editor|joao-pass-00|joao@x.org\n' > "$T/wp_users"
    printf 'KN_ADMIN_USER=kn_ab12\nKN_ADMIN_PASSWORD=gen-Pass-123456\nKN_AUTH_KEY=salt-keep-me\nKN_PORT=8090\n' \
        > "$KEI_TAINACAN_DIR/.env"
    chmod 600 "$KEI_TAINACAN_DIR/.env"
    cat > "$KEI_KOHA_SHELL" <<'SH'
#!/bin/bash
# koha-shell INSTANCE -c "perl SCRIPT USER": the password on stdin.
printf '%s\n' "$*" >> "$T/argv"
user=${3##* }
IFS= read -r pw
line=$(grep "^$user|" "$T/koha_users") || { echo nouser; exit 3; }
[ "${line#*|}" = 1 ] || { echo notsuper; exit 4; }
case "$pw" in *weak*) echo policy; exit 6 ;; esac
printf '%s|%s\n' "$user" "$pw" >> "$T/koha_passwords"
echo ok
SH
    chmod +x "$KEI_KOHA_SHELL"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { printf '%s\n' \"\$*\" >> '$T/log'; }
SYS_LANG=en
DB_NAME=koha_library
INSTANCE=library
CLOUD_PLANS_FILE='$T/cloud_plans.conf'
is_koha_installed() { return 0; }
is_database_ready() { return 0; }
run_sql() { awk -F'|' '\$2 == 1 { print \$1 }' '$T/koha_users'; }
tunnel_mode_is() { return 1; }
_kei_bk_get() { [ \"\$1\" = schedule_tainacan ] && cat '$T/schedule' 2>/dev/null; return 0; }
_kei_tn_get() { case \"\$1\" in status) echo installed ;; url) cat '$T/url' 2>/dev/null || echo http://192.168.0.5:8090 ;; esac; return 0; }
_kei_tn_wp() {
    printf '%s\n' \"\$*\" >> '$T/argv'
    if [ \"\$1 \$2\" = 'user list' ]; then awk -F'|' '\$2 == \"administrator\" { print \$1 }' '$T/wp_users'; return 0; fi
    # As wp-cli: eval takes no arguments for the code (\$args is only
    # given by eval-file, whose file is in the work folder, /work).
    [ \"\$1\" = eval-file ] || return 1
    local code pw; code=\$(cat \"\$KEI_TAINACAN_DIR/work/\${2#/work/}\") || return 1; shift 2
    IFS= read -r pw
    if [[ \"\$code\" == *wp_check_password* ]]; then
        grep -q \"^\$1|[^|]*|\$pw|\" '$T/wp_users' && echo yes || echo no
    elif [[ \"\$code\" == *wp_set_password* ]]; then
        local line; line=\$(grep \"^\$1|\" '$T/wp_users') || { echo nouser; return 0; }
        [ \"\$(cut -d'|' -f2 <<<\"\$line\")\" = administrator ] || { echo notadmin; return 0; }
        awk -F'|' -v OFS='|' -v u=\"\$1\" -v p=\"\$pw\" '\$1 == u { \$3 = p } 1' '$T/wp_users' > '$T/wp_users.new' && mv '$T/wp_users.new' '$T/wp_users'
        echo ok
    elif [[ \"\$code\" == *wp_insert_user* ]]; then
        grep -q -e \"^\$1|\" -e \"|\$2\\\$\" '$T/wp_users' && { echo exists; return 0; }
        printf '%s|administrator|%s|%s\n' \"\$1\" \"\$pw\" \"\$2\" >> '$T/wp_users'
        echo ok
    fi
}
$1" 3>&-
}

# never CMD...: fails when CMD succeeds (a bare "! cmd" does not fail a
# bats test).
never() { if "$@"; then return 1; fi; return 0; }

no_password_anywhere() {
    # Never in a command line, a log line or what the task printed.
    never grep -qF -- "$1" "$T/argv" 2>/dev/null
    never grep -qF -- "$1" "$T/log" 2>/dev/null
    [[ "$output" != *"$1"* ]]
}

@test "A01 Koha: the web installer is unfinished while no superlibrarian exists" {
    printf 'maria|0\n' > "$T/koha_users"
    run lib "kei_koha_admin_status"
    [ "$status" -eq 0 ]
    [[ "$output" == *state=web-installer* ]] && [[ "$output" != *admin=* ]]
    printf 'admin|1\nmaria|0\n' > "$T/koha_users"
    run lib "kei_koha_admin_status"
    [[ "$output" == *state=ready* ]] && [[ "$output" == *admin=admin* ]] && [[ "$output" != *admin=maria* ]]
}

@test "A02 Koha: a superlibrarian's password goes on stdin only and the environment loses it" {
    run lib "export KEI_ADMIN_PASSWORD='$PW'; kei_koha_admin_password admin; echo \"left=\${KEI_ADMIN_PASSWORD:-}\"; echo \"kept=\${_KEI_PW:-}\""
    [ "$status" -eq 0 ]
    grep -qxF "admin|$PW" "$T/koha_passwords"
    [[ "$output" == *"left="* ]] && [[ "$output" == *$'left=\nkept='* ]]
    [[ "$output" == *"encryption key"* ]]
    no_password_anywhere "$PW"
    # The perl script is gone.
    [ -z "$(ls /tmp/koha_admin.* 2>/dev/null)" ]
}

@test "A03 Koha: only superlibrarians, only existing accounts; Koha's own rules refuse a weak password" {
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_koha_admin_password maria"
    [ "$status" -eq 4 ] && [[ "$output" == *"not a superlibrarian"* ]]
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_koha_admin_password nobody"
    [ "$status" -eq 3 ]
    run lib "KEI_ADMIN_PASSWORD='weak-but-long' kei_koha_admin_password admin"
    [ "$status" -eq 6 ] && [[ "$output" == *"Nothing was changed"* ]]
    [ ! -e "$T/koha_passwords" ]
}

@test "A04 a short password, a line break or a bad user name is refused before anything runs" {
    run lib "KEI_ADMIN_PASSWORD=short kei_koha_admin_password admin"
    [ "$status" -eq 2 ] && [[ "$output" == *"at least 10"* ]]
    run lib "KEI_ADMIN_PASSWORD=\$'line-one-long\nline-two' kei_tainacan_admin_password kn_ab12"
    [ "$status" -eq 2 ] && [[ "$output" == *"line breaks"* ]]
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_password 'x;rm -rf /'"
    [ "$status" -eq 2 ]
    [ ! -e "$T/argv" ]
}

@test "A05 Tainacan: the initial account is reported until its own password is set; the salts stay" {
    run lib "kei_tainacan_admin_status"
    [ "$status" -eq 0 ]
    [[ "$output" == *state=initial* ]] && [[ "$output" == *initial=kn_ab12* ]] && [[ "$output" == *admin=kn_ab12* ]]
    [[ "$output" != *admin=joao* ]]
    no_password_anywhere gen-Pass-123456
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_password kn_ab12"
    [ "$status" -eq 0 ]
    grep -qxF "kn_ab12|administrator|$PW|admin@x.invalid" "$T/wp_users"
    never grep -q KN_ADMIN_PASSWORD "$KEI_TAINACAN_DIR/.env"
    grep -qx 'KN_AUTH_KEY=salt-keep-me' "$KEI_TAINACAN_DIR/.env" && grep -qx 'KN_ADMIN_USER=kn_ab12' "$KEI_TAINACAN_DIR/.env"
    [ "$(stat -c %a "$KEI_TAINACAN_DIR/.env")" = 600 ]
    no_password_anywhere "$PW"
    run lib "kei_tainacan_admin_status"
    [[ "$output" == *state=own* ]]
    # The other account did not change.
    grep -qxF 'joao|editor|joao-pass-00|joao@x.org' "$T/wp_users"
}

@test "A06 Tainacan: a password only for an administrator that exists" {
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_password joao"
    [ "$status" -eq 4 ] && [[ "$output" == *"not an administrator"* ]]
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_password ghost"
    [ "$status" -eq 3 ]
    grep -qxF 'joao|editor|joao-pass-00|joao@x.org' "$T/wp_users"
    grep -q KN_ADMIN_PASSWORD "$KEI_TAINACAN_DIR/.env"
}

@test "A07 Tainacan: another administrator, never over an existing name or e-mail" {
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_create joao new@x.org"
    [ "$status" -eq 5 ] && [[ "$output" == *"nothing was created or changed"* ]]
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_create ana joao@x.org"
    [ "$status" -eq 5 ]
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_create ana 'not-an-email'"
    [ "$status" -eq 2 ]
    [ "$(wc -l < "$T/wp_users")" -eq 2 ]
    run lib "KEI_ADMIN_PASSWORD='$PW' kei_tainacan_admin_create ana ana@x.org"
    [ "$status" -eq 0 ]
    grep -qxF "ana|administrator|$PW|ana@x.org" "$T/wp_users"
    no_password_anywhere "$PW"
    # The code files given to wp eval-file are removed after each call.
    [ -z "$(ls -A "$KEI_TAINACAN_DIR/work" 2>/dev/null)" ]
}

@test "A08 setup: only states in a private file; begin never resets; the real state marks steps done" {
    run lib "kei_setup_status tainacan"
    [ "$output" = setup=none ]
    run lib "kei_setup_begin tainacan && kei_setup_mark tainacan public later && kei_setup_begin tainacan"
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$KEI_SETUP_DIR")" = 700 ] && [ "$(stat -c %a "$KEI_SETUP_DIR/tainacan.state")" = 600 ]
    [ "$(cat "$KEI_SETUP_DIR/tainacan.state" | sort)" = "$(printf 'admin=pending\nbackup=pending\npublic=later')" ]
    run lib "kei_setup_status tainacan quick"
    [[ "$output" == *setup=open* ]] && [[ "$output" == *"step=public|later|"* ]] && [[ "$output" == *pending=3* ]]
    # Configured elsewhere (the menus): counted as done by the real state.
    echo 02:30 > "$T/schedule"
    echo https://acervo.example.org > "$T/url"
    run lib "kei_setup_status tainacan"
    [[ "$output" == *"step=backup|done|daily backup at 02:30"* ]]
    [[ "$output" == *"step=public|done|https://acervo.example.org"* ]]
    [[ "$output" == *"step=admin|pending|"* ]] && [[ "$output" == *pending=1* ]]
    grep -qx backup=done "$KEI_SETUP_DIR/tainacan.state"
    # Never a setting, a password or an address in the file.
    never grep -vqE '^(admin|public|backup)=(done|later|pending)$' "$KEI_SETUP_DIR/tainacan.state"
    run lib "kei_setup_mark tainacan admin maybe"
    [ "$status" -eq 2 ]
    run lib "kei_setup_close tainacan"
    [ ! -e "$KEI_SETUP_DIR/tainacan.state" ]
    run lib "kei_setup_mark koha admin later"
    [ "$status" -eq 3 ] && [ ! -e "$KEI_SETUP_DIR/koha.state" ]
}

@test "A09 setup: Koha's admin step is done when a superlibrarian exists; a local address is not public" {
    run lib "kei_setup_begin koha && kei_setup_status koha"
    [[ "$output" == *"step=admin|done|superlibrarian: admin"* ]]
    [[ "$output" == *"step=public|pending|"* ]] && [[ "$output" == *"step=backup|pending|"* ]]
    echo 'daily|gdrive|Koha|30' > "$T/cloud_plans.conf"
    run lib "kei_setup_status koha"
    [[ "$output" == *"step=backup|done|1 cloud backup(s)"* ]]
    run lib "kei_setup_begin tainacan && kei_setup_status tainacan"
    [[ "$output" == *"step=public|pending|"* ]]
}

@test "A10 only a new installation starts the setup; an update or the status never does" {
    calls=$(grep -n 'kei_setup_begin ' "$REPO/installer" | grep -v '^[0-9]*:[[:space:]]*#' | grep -v 'kei_setup_begin()' )
    [ "$(wc -l <<<"$calls")" -eq 2 ]
    grep -q 'kei_setup_begin koha' <<<"$calls" && grep -q 'kei_setup_begin tainacan' <<<"$calls"
}
