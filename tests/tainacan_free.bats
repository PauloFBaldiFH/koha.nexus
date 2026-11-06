#!/usr/bin/env bats
# The free koha.nexus address of the collection (installer:
# kei_tainacan_free_*, and the broker client it shares with the catalog's
# free address). The address service is tests/lib/fake_broker.py (the real
# one, broker/, is tested there); Tainacan's address change is a stand-in
# that records it. Covered: a service without collection addresses, one
# that is not online and Koha without a free address change nothing; with
# Koha on a free address the collection's name is added after a yes, in the
# same tunnel, and taken out again without touching the catalog; giving up
# the catalog's address brings the collection back to the local network; a
# server without Koha asks for an address of the collection only (never
# Koha's names, never the public list), the token kept out of sight, and
# gives it up again.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export T
    mkdir -p "$T/conf" "$T/bin" "$T/broker"
    printf '#!/bin/sh\necho "cloudflared $*" >> "%s/calls"\n' "$T" > "$T/bin/cloudflared"
    chmod +x "$T/bin/cloudflared"
    : > "$T/answers"
    touch "$T/koha" "$T/resolves"
}

teardown() {
    [ -f "$T/broker/pid" ] && kill "$(cat "$T/broker/pid")" 2>/dev/null
    rm -f /root/koha-address-t-*.key
    return 0
}

# broker [seed]: starts the stand-in service ("slug services" = a library
# this server already has).
broker() {
    [ -n "${1:-}" ] && printf '%s\n' "$1" > "$T/broker/seed"
    python3 "$REPO/tests/lib/fake_broker.py" "$T/broker" 3>&- &
    echo $! > "$T/broker/pid"
    local i
    for i in $(seq 1 50); do [ -s "$T/broker/port" ] && break; sleep 0.1; done
    PORT=$(cat "$T/broker/port")
}

answer() { printf '%s\n' "$@" >> "$T/answers"; }

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
SYS_LANG=en
PATH='$T/bin':\$PATH
CONF_DIR='$T/conf'
TUNNEL_CONF='$T/conf/tunnel.conf'
BROKER_KEY='$T/conf/broker.key'
BROKER_ENROLL='$T/conf/broker-enroll.conf'
BROKER_ENV='$T/broker.env'
CLOUDFLARED_UNIT='$T/cloudflared.service'
CRON_BROKER='$T/cron_broker'
KEI_BROKER_URL='http://127.0.0.1:${PORT:-9}'
REAL_HOME='$T'
log() { printf '%s\n' \"\$*\" >> '$T/log'; }
broker_resolves() { [ -f '$T/resolves' ]; }
is_koha_installed() { [ -f '$T/koha' ]; }
require_systemd() { return 0; }
cloudflared_install() { return 0; }
tunnel_check_url() { return 0; }
systemctl() { echo \"systemctl \$*\" >> '$T/calls'; }
set_koha_public_urls() { echo \"koha-urls \$*\" >> '$T/calls'; }
function_share_catalog_link() { echo share >> '$T/calls'; }
get_server_ip() { echo 192.168.0.5; }
clear() { :; }
display_explanation() { :; }
_kei_tn_get() { case \"\$1\" in status) echo installed ;; url) cat '$T/url' 2>/dev/null || echo http://192.168.0.5:8090 ;; esac; return 0; }
kei_tainacan_address() {
    local u=\"\$1\"
    echo \"\$u\" >> '$T/address.log'
    [ \"\$u\" = local ] && u=http://192.168.0.5:8090
    echo \"\$u\" > '$T/url'
    echo \"Tainacan now answers at \$u.\"
}
_next() { local a; a=\$(head -n1 '$T/answers'); sed -i '1d' '$T/answers'; printf '%s' \"\$a\"; }
ui_input() { printf 'INPUT %s\n' \"\$2\" >> '$T/dialogs'; _next; }
ui_menu() { printf 'MENU %s\n' \"\$2\" >> '$T/dialogs'; local a; a=\$(_next); [ -n \"\$a\" ] && [ \"\$a\" != CANCEL ] && printf '%s' \"\$a\"; }
prompt_yes_no() { local a; a=\$(_next); printf 'PROMPT %s => %s\n' \"\$2\" \"\$a\" >> '$T/dialogs'; [ \"\$a\" = yes ]; }
msg_error() { printf 'ERROR %s\n' \"\$*\" >> '$T/dialogs'; }
msg_info() { printf 'INFO %s\n' \"\$*\" >> '$T/dialogs'; }
msg_ok() { printf 'OK %s\n' \"\$*\" >> '$T/dialogs'; }
$1" 3>&-
}

dialogs() { cat "$T/dialogs" 2>/dev/null; }
calls() { cat "$T/calls" 2>/dev/null; }
requests() { cat "$T/broker/broker.log" 2>/dev/null; }
conf() { grep -x "$1=.*" "$T/conf/tunnel.conf" 2>/dev/null | cut -d= -f2-; }

# never CMD...: fails when CMD succeeds (a bare "! cmd" does not fail a
# bats test).
never() { if "$@"; then return 1; fi; return 0; }

# A server whose Koha already has the free address t-palotina.example.org.
koha_on_free_address() {
    broker "palotina koha"
    printf 'TUNNEL_MODE=broker\nBROKER_URL=http://127.0.0.1:%s\nLIBRARY_ID=lib-1\nOPAC_HOST=t-palotina.example.org\nSTAFF_HOST=t-palotina-admin.example.org\nSTAFF_REMOTE=no\n' \
        "$PORT" > "$T/conf/tunnel.conf"
    lib 'broker_ensure_key'
}

@test "F01 a service without collection addresses changes nothing" {
    rm -f "$T/koha"
    touch "$T/broker/old"
    broker
    run lib 'kei_tainacan_free_status'
    [ "$status" -eq 0 ]
    echo "$output" | grep -qx "available=no"
    echo "$output" | grep -q "^reason=.*does not offer addresses for collections yet"
    echo "$output" | grep -qx "library=none"
    run lib 'kei_tainacan_free on'
    dialogs | grep -q "ERROR .*does not offer addresses for collections yet"
    [ "$(requests | grep -vc '^GET /v1/capabilities ')" -eq 0 ]
    [ ! -e "$T/conf/tunnel.conf" ] && [ ! -e "$T/address.log" ] && [ ! -e "$T/conf/broker.key" ]
}

@test "F02 a service that is not online, and Koha without a free address, ask nothing of it" {
    rm -f "$T/koha" "$T/resolves"
    broker
    run lib 'kei_tainacan_free_status'
    echo "$output" | grep -q "^reason=The free address service is not online yet"
    touch "$T/resolves" "$T/koha"
    run lib 'kei_tainacan_free_status'
    echo "$output" | grep -q "^reason=Koha on this server has no free address yet. Get the catalog's free address first"
    run lib 'kei_tainacan_free on'
    dialogs | grep -q "ERROR .*Koha on this server has no free address yet"
    [ -z "$(requests)" ]
    [ ! -e "$T/address.log" ]
}

@test "F03 Koha on a free address: the collection's name is added after a yes, in the same tunnel" {
    koha_on_free_address
    run lib 'kei_tainacan_free_status'
    echo "$output" | grep -qx "available=yes"
    echo "$output" | grep -qx "library=koha"
    echo "$output" | grep -qx "preview=t-palotina-acervo.example.org"

    # No: nothing is asked of the service, nothing changes.
    answer no
    run lib 'kei_tainacan_free on'
    dialogs | grep -q "PROMPT The collection gets the address https://t-palotina-acervo.example.org, in the same tunnel as the catalog (https://t-palotina.example.org).* => no"
    never grep -q "^PUT " "$T/broker/broker.log"
    [ ! -e "$T/address.log" ] && [ -z "$(conf TAINACAN_HOST)" ]

    answer yes
    run lib 'kei_tainacan_free on'
    [ "$status" -eq 0 ]
    requests | grep -qx 'PUT /v1/services signed {"tainacan":true}'
    [ "$(conf TAINACAN_HOST)" = t-palotina-acervo.example.org ]
    [ "$(cat "$T/address.log")" = https://t-palotina-acervo.example.org ]
    dialogs | grep -q "OK Your collection is online:.*https://t-palotina-acervo.example.org"
    # The catalog and its tunnel are not touched.
    [ "$(conf OPAC_HOST)" = t-palotina.example.org ] && [ "$(conf STAFF_REMOTE)" = no ]
    never grep -q "tunnel-token" "$T/broker/broker.log"
    never grep -q "koha-urls" "$T/calls"

    run lib 'kei_tainacan_free_status'
    echo "$output" | grep -qx "host=t-palotina-acervo.example.org"
    echo "$output" | grep -qx "available=yes"

    # Asked again: the address is applied again, the service is not asked.
    local before
    before=$(requests | wc -l)
    run lib 'kei_tainacan_free on'
    [ "$(requests | wc -l)" -eq "$before" ]
}

@test "F04 the collection leaves the free address; the catalog keeps its own" {
    koha_on_free_address
    answer yes
    lib 'kei_tainacan_free on'
    : > "$T/address.log"

    answer no
    run lib 'kei_tainacan_free off'
    [ "$(conf TAINACAN_HOST)" = t-palotina-acervo.example.org ]
    never grep -q "tainacan\":false" "$T/broker/broker.log"

    answer yes
    run lib 'kei_tainacan_free off'
    [ "$status" -eq 0 ]
    requests | grep -qx 'PUT /v1/services signed {"tainacan":false}'
    never grep -q "^DELETE " "$T/broker/broker.log"
    [ -z "$(conf TAINACAN_HOST)" ] && [ "$(conf OPAC_HOST)" = t-palotina.example.org ]
    [ "$(cat "$T/address.log")" = local ]
    dialogs | grep -q "OK The free address was released."
}

@test "F05 giving up the catalog's free address brings the collection back to the local network" {
    koha_on_free_address
    answer yes
    lib 'kei_tainacan_free on'
    : > "$T/address.log"
    answer yes
    run lib 'function_broker_leave'
    [ "$status" -eq 0 ]
    dialogs | grep -q "PROMPT .*The collection's address (https://t-palotina-acervo.example.org) is released too"
    requests | grep -q "^DELETE /v1/library signed"
    [ "$(cat "$T/address.log")" = local ]
    [ ! -e "$T/conf/tunnel.conf" ] && [ ! -e "$T/conf/broker.key" ]
}

@test "F06 a server without Koha gets an address of the collection only, the token out of sight" {
    rm -f "$T/koha"
    broker
    answer new "Museu Municipal" "museu@example.org" "museu" no
    run lib 'kei_tainacan_free on'
    [ "$status" -eq 0 ]
    requests | grep -q '^POST /v1/device/start unsigned .*"requested_name":"museu","services":\["tainacan"\]}$'
    [ "$(conf TUNNEL_MODE)" = broker ] && [ -z "$(conf OPAC_HOST)" ] && [ -z "$(conf STAFF_HOST)" ]
    [ "$(conf TAINACAN_HOST)" = t-museu-acervo.example.org ]
    [ "$(cat "$T/address.log")" = https://t-museu-acervo.example.org ]
    dialogs | grep -q "OK Your collection is online:.*https://t-museu-acervo.example.org"
    # The tunnel: token in a 0600 file, never on a command line or a screen.
    [ "$(stat -c %a "$T/broker.env")" = 600 ] && grep -q "^TUNNEL_TOKEN=tunnel-token-" "$T/broker.env"
    grep -q "EnvironmentFile=$T/broker.env" "$T/cloudflared.service"
    never grep -q "tunnel-token" "$T/cloudflared.service"
    never grep -q "tunnel-token" "$T/dialogs"
    never grep -q "tunnel-token" "$T/log"
    calls | grep -q "systemctl restart cloudflared"
    # Nothing of Koha: no Koha addresses, no sharing of the catalog, no public list.
    never grep -q "koha-urls\|share" "$T/calls"
    never grep -q "/v1/listing" "$T/broker/broker.log"
    never grep -qi "public list" "$T/dialogs"
    [ ! -e "$T/conf/broker-enroll.conf" ]

    run lib 'kei_tainacan_free_status'
    echo "$output" | grep -qx "library=tainacan"
    echo "$output" | grep -qx "host=t-museu-acervo.example.org"
}

@test "F07 the recovery file of a collection-only address carries its name" {
    rm -f "$T/koha"
    broker
    answer new "Museu Municipal" "museu@example.org" "museu" yes
    run lib 'kei_tainacan_free on'
    [ "$status" -eq 0 ]
    local file="$T/koha-address-t-museu-acervo.key"
    [ "$(stat -c %a "$file")" = 600 ]
    grep -qx "LIBRARY_ID=lib-1" "$file" && grep -q "BEGIN PRIVATE KEY" "$file"
}

@test "F08 the collection-only address is given up after a yes" {
    rm -f "$T/koha"
    broker
    answer new "Museu Municipal" "museu@example.org" "museu" no
    lib 'kei_tainacan_free on'
    : > "$T/address.log"
    answer no
    run lib 'kei_tainacan_free off'
    [ -s "$T/conf/tunnel.conf" ]
    never grep -q "^DELETE " "$T/broker/broker.log"

    answer yes
    run lib 'kei_tainacan_free off'
    [ "$status" -eq 0 ]
    requests | grep -q "^DELETE /v1/library signed"
    [ ! -e "$T/conf/tunnel.conf" ] && [ ! -e "$T/conf/broker.key" ] && [ ! -e "$T/broker.env" ] && [ ! -e "$T/cron_broker" ]
    calls | grep -q "systemctl disable --now cloudflared"
    [ "$(cat "$T/address.log")" = local ]
}

@test "F09 only on and off are tasks" {
    run lib 'kei_tainacan_free bogus'
    [ "$status" -eq 2 ]
    run lib 'kei_tainacan_free_off'
    dialogs | grep -q "INFO .*The collection does not use a free address."
}
