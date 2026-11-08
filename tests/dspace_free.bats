#!/usr/bin/env bats
# Installer client decisions with explicit broker/runtime/service doubles.
# Actual signatures and server transitions are tested in broker/test/e2e/dspace.mjs.
setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    export T="$BATS_TEST_TMPDIR" KEI_OWNED_DIR="$BATS_TEST_TMPDIR/owned"
    mkdir -p "$T/dspace"
    printf '{}' > "$T/dspace/state.json"
    printf 'TUNNEL_MODE=broker\nOPAC_HOST=library.example.org\nTAINACAN_HOST=collection.example.org\n' > "$T/tunnel.conf"
    printf '{"services":"koha,tainacan"}' > "$T/reply"
}
lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
SYS_LANG=en
KEI_DSPACE_DIR='$T/dspace'
TUNNEL_CONF='$T/tunnel.conf'
BROKER_ENV='$T/broker.env'
BROKER_KEY='$T/broker.key'
CRON_BROKER='$T/cron'
CLOUDFLARED_UNIT='$T/cloudflared.service'
BROKER_BODY='$T/body'
kei_proxy_detect() { if [ -f '$T/external' ]; then echo external nginx 1; else echo apache-shared apache 2; fi; }
broker_resolves() { return 0; }
broker_cleanup() { :; }
broker_request() {
    printf '%s %s %s %s\n' \"\$1\" \"\$2\" \"\$3\" \"\${4:-}\" >> '$T/requests'
    case \"\$1\" in
      GET) [ ! -f '$T/unavailable' ] || return 1
        printf '{\"services\":[\"koha\",\"tainacan\",\"dspace\"],\"repository_suffix\":\"-repositorio\",\"repository_origin_port\":18102}' > \"\$BROKER_BODY\" ;;
      PUT) printf '{\"hostnames\":{\"repository\":\"repository.example.org\"}}' > \"\$BROKER_BODY\" ;;
      DELETE) if [ -f '$T/status' ]; then BROKER_STATUS=\$(cat '$T/status');return 1;fi
        cp '$T/reply' \"\$BROKER_BODY\" ;;
    esac
}
prompt_yes_no() { [ ! -f '$T/decline' ]; }
ui_input() { printf 'test-only recovery phrase'; }
msg_error() { printf '%s\n' \"\$*\" >> '$T/dialogs'; }
msg_info() { :; }
kei_lan_address() { printf '192.0.2.7 eth0\n'; }
kei_dspace_runtime() {
    printf '%s\n' \"\$*\" >> '$T/runtime-args'
    printf '%s\n' \"\$KEI_DSPACE_OPERATIONS_DATA\" >> '$T/address-data'
    [ ! -f '$T/fail-runtime' ]
}
systemctl() { printf '%s\n' \"\$*\" >> '$T/systemctl'; }
$1" 3>&-
}
absent() { if "$@"; then return 1; fi; return 0; }

@test "DF01 external proxy is refused before any broker mutation" {
    touch "$T/external"
    run lib 'kei_dspace_free on'
    [ "$status" -eq 3 ]
    [ ! -e "$T/requests" ] && [ ! -e "$T/runtime-args" ]
}
@test "DF02 unavailable capability and declined publication never reserve a name" {
    touch "$T/unavailable"
    run lib 'kei_dspace_free on'
    [ "$status" -eq 3 ]
    absent grep -q '^PUT ' "$T/requests"
    rm "$T/unavailable"; touch "$T/decline"
    run lib 'kei_dspace_free on'
    [ "$status" -eq 0 ]
    absent grep -q '^PUT ' "$T/requests"
    [ ! -e "$T/runtime-args" ]
}
@test "DF03 shared attachment changes only repository address and keeps phrase out of arguments" {
    run lib 'kei_dspace_free on'
    [ "$status" -eq 0 ]
    grep -qx 'PUT /v1/services yes {"dspace":true}' "$T/requests"
    grep -qx 'OPAC_HOST=library.example.org' "$T/tunnel.conf"
    grep -qx 'TAINACAN_HOST=collection.example.org' "$T/tunnel.conf"
    grep -qx 'DSPACE_HOST=repository.example.org' "$T/tunnel.conf"
    grep -q '"mode":"tunnel","origin_port":18102' "$T/address-data"
    absent grep -q 'recovery phrase' "$T/runtime-args"
}
@test "DF04 failed address validation keeps shared identity for an explicit retry" {
    touch "$T/fail-runtime"
    run lib 'kei_dspace_free on'
    [ "$status" -eq 1 ]
    grep -qx 'DSPACE_HOST=repository.example.org' "$T/tunnel.conf"
    absent grep -q '^DELETE ' "$T/requests"
    [ ! -e "$T/systemctl" ]
}
@test "DF05 shared release uses the dedicated repository endpoint and preserves the tunnel" {
    printf 'DSPACE_HOST=repository.example.org\n' >> "$T/tunnel.conf"
    run lib 'kei_dspace_free off'
    [ "$status" -eq 0 ]
    grep -qx 'DELETE /v1/services/dspace yes ' "$T/requests"
    grep -qx 'OPAC_HOST=library.example.org' "$T/tunnel.conf"
    grep -qx 'TAINACAN_HOST=collection.example.org' "$T/tunnel.conf"
    grep -qx 'DSPACE_HOST=' "$T/tunnel.conf"
    [ ! -e "$T/systemctl" ]
}
@test "DF06 a shared authentication failure preserves identity and all other services" {
    printf 'DSPACE_HOST=repository.example.org\n' >> "$T/tunnel.conf"
    printf 401 > "$T/status"
    run lib 'kei_dspace_free off'
    [ "$status" -eq 1 ]
    grep -qx 'DSPACE_HOST=repository.example.org' "$T/tunnel.conf"
    [ ! -e "$T/systemctl" ]
}
@test "DF07 retry after standalone deletion removes only the broker unit we generated" {
    printf 'TUNNEL_MODE=broker\nDSPACE_HOST=repository.example.org\n' > "$T/tunnel.conf"
    printf 'EnvironmentFile=%s/broker.env\n' "$T" > "$T/cloudflared.service"
    touch "$T/broker.env" "$T/broker.key" "$T/cron"
    printf 401 > "$T/status"
    run lib 'kei_dspace_free off'
    [ "$status" -eq 0 ]
    [ ! -e "$T/tunnel.conf" ] && [ ! -e "$T/cloudflared.service" ]
    [ ! -e "$T/broker.env" ] && [ ! -e "$T/broker.key" ]
    grep -qx 'disable --now cloudflared' "$T/systemctl"
}
