#!/usr/bin/env bats
# Free address (Cloudflare Tunnel through the Koha broker): the panel talks
# to the real broker code (broker/, run in local workerd by Miniflare with a
# fake Cloudflare API). Covers the request and its approval, the signed
# calls, the tunnel token kept out of sight, the cloudflared service,
# remote staff access, sharing the link, the heartbeat and giving the
# address up. Also the own-domain setup never replacing a DNS record
# without asking.
#
# Needs Node.js and `npm install` in broker/; skipped otherwise. The tests
# run in order: B01 creates the library the next ones use.

setup_file() {
    if ! command -v node >/dev/null 2>&1 || [ ! -d "$KEI_REPO_DIR/broker/node_modules/miniflare4" ]; then
        return 0
    fi
    export BROKER_STATE="$BATS_FILE_TMPDIR/broker"
    ( cd "$KEI_REPO_DIR/broker" && npm run --silent build:local >/dev/null 2>&1 )
    node "$KEI_REPO_DIR/broker/test/e2e/serve.mjs" "$BROKER_STATE" > "$BATS_FILE_TMPDIR/broker.log" 2>&1 3>&- &
    echo $! > "$BATS_FILE_TMPDIR/broker.pid"
    local i
    for i in $(seq 1 60); do [ -s "$BROKER_STATE/ready" ] && break; sleep 0.5; done
    rm -f /etc/koha-easy-install/tunnel.conf /etc/koha-easy-install/broker.key /etc/koha-easy-install/broker-enroll.conf
}

teardown_file() {
    [ -f "$BATS_FILE_TMPDIR/broker.pid" ] && kill "$(cat "$BATS_FILE_TMPDIR/broker.pid")" 2>/dev/null
    rm -f /etc/koha-easy-install/tunnel.conf /etc/koha-easy-install/broker.key /etc/koha-easy-install/broker-enroll.conf \
          /root/koha-catalog-qr.png
    return 0
}

# A menu loop that never ends fails the test instead of hanging the battery.
BATS_TEST_TIMEOUT=${BATS_TEST_TIMEOUT:-180}
KEI_REPO_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
ADMIN="Authorization: Bearer aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CONF=/etc/koha-easy-install

setup() {
    load lib/common
    [ -s "${BROKER_STATE:-/nonexistent}/ready" ] || skip "broker not available (Node.js and npm install in broker/)"
    kei_reset_env
    kei_reset_live_catalog
    BROKER=$(sed -n 1p "$BROKER_STATE/ready")
    INSPECT=$(sed -n 2p "$BROKER_STATE/ready")
    BIN="$BATS_TEST_TMPDIR/bin"
    mkdir -p "$BIN"
    UNIT="$BATS_FILE_TMPDIR/cloudflared.service"
    ENVF="$BATS_FILE_TMPDIR/koha-broker.env"
    cat > "$BATS_TEST_TMPDIR/extra.sh" <<EOF
PATH="$BIN:\$PATH"
KEI_BROKER_URL="$BROKER"
KEI_BROKER_POLL=1
KEI_TUNNEL_CHECK_DELAY=0
KEI_TUNNEL_CHECKS=2
BROKER_ENV="$ENVF"
CLOUDFLARED_UNIT="$UNIT"
get_server_ip() { echo 192.168.0.10; }
# Password boxes answer from \$KEI_S/passwords, one per line.
whiptail() {
    _kei_dialog "whiptail \$*"
    case " \$* " in *" --passwordbox "*) head -n1 "\$KEI_S/passwords" >&2; sed -i '1d' "\$KEI_S/passwords" ;; esac
    return 0
}
EOF
    export KEI_EXTRA="$BATS_TEST_TMPDIR/extra.sh"
    # cloudflared is "installed"; the public address answers 200.
    fake cloudflared 'echo "cloudflared $*" >> '"$KEI_S"'/calls.log'
    fake curl 'for a in "$@"; do case "$a" in https://t-*.example.org*) printf 200; exit 0 ;; esac; done; exec /usr/bin/curl "$@"'
    fake qrencode 'printf "%s\n" "$@" > '"$KEI_S"'/qrencode.args; o=""; while [ $# -gt 0 ]; do [ "$1" = "-o" ] && o="$2"; shift; done; [ -n "$o" ] && echo PNG > "$o"; echo "██ QR ██"'
    rm -f "$KEI_S/passwords"
}

teardown() {
    rm -f /root/.kei-broker-*
    kei_kill_daemons
}

fake() {
    printf '#!/bin/bash\n%s\n' "$2" > "$BIN/$1"
    chmod 755 "$BIN/$1"
}

state() { /usr/bin/curl -s "$INSPECT"; }
pref() { mysql -Nse "SELECT value FROM ${DB}.systempreferences WHERE variable='$1';"; }

@test "B01 free address: approved on the spot, tunnel installed with the token out of sight" {
    inputs "Biblioteca Pública Municipal de Palotina" "biblioteca@palotina.pr.gov.br" "Palotina PR" CANCEL
    panel function_cloudflare_free_address
    assert '[ "$status" -eq 0 ]' "$output"

    assert 'grep -qx "TUNNEL_MODE=broker" $CONF/tunnel.conf' "$(cat $CONF/tunnel.conf)"
    assert 'grep -qx "OPAC_HOST=t-palotina-pr.example.org" $CONF/tunnel.conf'
    assert 'grep -qx "STAFF_HOST=t-palotina-pr-admin.example.org" $CONF/tunnel.conf'
    assert 'grep -qx "STAFF_REMOTE=no" $CONF/tunnel.conf'
    assert '[ ! -e $CONF/broker-enroll.conf ]' "the request file is removed"
    assert '[ "$(stat -c %a $CONF/broker.key)" = 600 ]'

    local s
    s=$(state)
    assert 'echo "$s" | grep -q "\"name\":\"kei-lib-"' "$s"
    assert '[ "$(echo "$s" | grep -o "\"type\":\"CNAME\"" | wc -l)" -eq 2 ]' "$s"

    assert '[ "$(stat -c %a $ENVF)" = 600 ]'
    assert 'grep -q "^TUNNEL_TOKEN=tunnel-token-for-" $ENVF'
    assert 'grep -qx "EnvironmentFile=$ENVF" $UNIT' "$(cat $UNIT)"
    assert 'grep -q "tunnel run$" $UNIT && ! grep -q "tunnel-token" $UNIT' "token never on the command line"
    assert '! echo "$output" | grep -q "tunnel-token-for" && ! dialogs | grep -q "tunnel-token-for"' "token never shown"
    assert 'calls | grep -q "systemctl enable cloudflared" && calls | grep -q "systemctl restart cloudflared"' "$(calls)"
    assert 'grep -q -- "--broker-heartbeat" /etc/cron.d/koha_broker'
    assert '[ "$(pref OPACBaseURL)" = "https://t-palotina-pr.example.org" ]' "$(pref OPACBaseURL)"
    assert 'dialogs | grep -q "OK .*Your catalog is online"' "$(dialogs)"
    assert '! echo "$output" | grep -qF "/join?c=" && ! dialogs | grep -q "MENU \[Authorization\]"' "no link to open, no wait: $output"
    assert '[ -z "$(ls /root/.kei-broker-* 2>/dev/null)" ]' "temporary files removed"
}

@test "B02 status, credentials and banner read the free address" {
    panel eval 'tunnel_public_hosts'
    assert '[ "$output" = "t-palotina-pr.example.org -" ]' "staff stays local while remote access is off: $output"
    panel function_view_credentials
    assert 'echo "$output" | grep -qx "https://t-palotina-pr.example.org"' "value alone on its line: $output"
}

@test "B03 remote staff access: edge password on, then off; password never shown" {
    printf '%s\n' "uma senha bem longa" "uma senha bem longa" > "$KEI_S/passwords"
    inputs on biblioteca ""
    panel function_broker_staff_access
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'grep -qx "STAFF_REMOTE=yes" $CONF/tunnel.conf'
    assert '[ "$(pref staffClientBaseURL)" = "https://t-palotina-pr-admin.example.org" ]'
    assert '! dialogs | grep -q "uma senha bem longa" && ! echo "$output" | grep -q "uma senha bem longa"'

    local code
    code=$(/usr/bin/curl -s -o /dev/null -w '%{http_code}' -H 'Host: t-palotina-pr-admin.example.org' "$BROKER/")
    assert '[ "$code" = 401 ]' "no password: $code"
    code=$(/usr/bin/curl -s -o /dev/null -w '%{http_code}' -u biblioteca:errada -H 'Host: t-palotina-pr-admin.example.org' "$BROKER/")
    assert '[ "$code" = 401 ]' "wrong password: $code"
    local body
    body=$(/usr/bin/curl -s -u 'biblioteca:uma senha bem longa' -H 'Host: t-palotina-pr-admin.example.org' "$BROKER/cgi-bin/koha/mainpage.pl")
    assert 'echo "$body" | grep -q "\"koha\":true" && echo "$body" | grep -q "\"authorization\":null"' "reaches Koha without the gate password: $body"

    panel eval 'tunnel_public_hosts'
    assert '[ "$output" = "t-palotina-pr.example.org t-palotina-pr-admin.example.org" ]' "$output"

    printf '%s\n' "curta" "curta" > "$KEI_S/passwords"
    inputs on biblioteca
    panel function_broker_staff_access
    assert 'dialogs | grep -q "at least 12 characters"' "short password refused locally: $(dialogs)"

    inputs off
    panel function_broker_staff_access
    assert 'grep -qx "STAFF_REMOTE=no" $CONF/tunnel.conf'
    assert '[ "$(pref staffClientBaseURL)" = "http://192.168.0.10:8080" ]'
    code=$(/usr/bin/curl -s -o /dev/null -w '%{http_code}' -u 'biblioteca:uma senha bem longa' -H 'Host: t-palotina-pr-admin.example.org' "$BROKER/")
    assert '[ "$code" = 403 ]' "closed again: $code"
}

@test "B04 heartbeat and token renewal are signed calls" {
    panel broker_heartbeat
    assert '[ "$status" -eq 0 ]' "$output"
    assert '/usr/bin/curl -s -H "$ADMIN" "$BROKER/admin/libraries" | grep -q "\"installer_version\":\"[0-9][0-9.]*\""'

    local before
    before=$(cat "$ENVF")
    inputs 3 CANCEL
    panel function_broker_manage
    assert '[ "$(state | grep -o "\"rotations\":{[^}]*}")" != "\"rotations\":{}" ]' "$(state)"
    assert '[ "$(cat $ENVF)" != "$before" ]' "the new token replaces the old one"

    # A foreign key cannot sign for this library.
    cp $CONF/broker.key "$BATS_TEST_TMPDIR/key.bak"
    openssl genpkey -algorithm ed25519 -out $CONF/broker.key 2>/dev/null
    panel eval 'broker_request GET /v1/library yes; echo "status=$BROKER_STATUS"'
    cp "$BATS_TEST_TMPDIR/key.bak" $CONF/broker.key
    assert 'echo "$output" | grep -qx "status=401"' "$output"
}

@test "B05 share the catalog link: QR code, image to print, link to copy" {
    inputs qr png link CANCEL
    panel function_share_catalog_link
    assert 'echo "$output" | grep -q "██ QR ██"' "$output"
    assert '[ "$(tail -n1 $KEI_S/qrencode.args)" = "https://t-palotina-pr.example.org" ]' "$(cat $KEI_S/qrencode.args)"
    assert '[ -s /root/koha-catalog-qr.png ]'
    assert 'echo "$output" | grep -q "https://t-palotina-pr.example.org"'
}

@test "B06 own-domain setup is refused while the free address is in use" {
    panel function_cloudflare_setup
    assert 'dialogs | grep -q "ERROR.*uses a free address"' "$(dialogs)"
    assert '! calls | grep -q "cloudflared tunnel login"'
}

@test "B07 KEY=value files are never executed and odd values are refused" {
    cp $CONF/tunnel.conf "$BATS_TEST_TMPDIR/t.bak"
    printf 'OPAC_HOST=$(touch /tmp/kei-pwned)\n' >> $CONF/tunnel.conf
    panel eval 'tunnel_conf_get OPAC_HOST; echo "rc=$?"'
    cp "$BATS_TEST_TMPDIR/t.bak" $CONF/tunnel.conf
    assert 'echo "$output" | grep -qx "rc=1"' "$output"
    assert '[ ! -e /tmp/kei-pwned ]'
    panel eval 'kv_write "$BATS_TEST_TMPDIR/x.conf" 600 A "b;rm" && echo written'
    assert '! echo "$output" | grep -q written'
}

@test "B08 giving up the address removes tunnel, records, token and key" {
    answer yes
    panel function_broker_leave
    assert '[ "$status" -eq 0 ]' "$output"
    local s
    s=$(state)
    assert 'echo "$s" | grep -q "\"tunnels\":\[\]"' "$s"
    assert '! echo "$s" | grep -q "t-palotina-pr"' "$s"
    assert '[ ! -e $CONF/tunnel.conf ] && [ ! -e $CONF/broker.key ] && [ ! -e "$ENVF" ] && [ ! -e /etc/cron.d/koha_broker ]'
    assert 'calls | grep -q "systemctl disable --now cloudflared"'
    assert '[ "$(pref OPACBaseURL)" = "http://192.168.0.10" ]'
}

@test "B09 a name that is taken gets a close variant, still without review" {
    # B08 gave palotina-pr up; the broker holds a released name for a while.
    inputs "Biblioteca Pública Municipal de Palotina" "biblioteca@palotina.pr.gov.br" "Palotina PR" CANCEL
    panel function_cloudflare_free_address
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'grep -qx "OPAC_HOST=t-palotina-pr-2.example.org" $CONF/tunnel.conf' "$(cat $CONF/tunnel.conf 2>/dev/null)"
    assert 'dialogs | grep -q "OK .*https://t-palotina-pr-2.example.org"' "$(dialogs)"
}

@test "B10 own domain: an existing DNS record is replaced only when the person agrees" {
    fake cloudflared 'echo "cloudflared $*" >> '"$KEI_S"'/calls.log; case " $* " in *" -f "*) exit 0 ;; *" route dns "*) echo "record already exists" >&2; exit 1 ;; esac'
    answer no
    panel cloudflare_route_dns koha-library catalog.example.org
    assert '! calls | grep -q "route dns -f"' "$(calls)"
    assert 'dialogs | grep -q "PROMPT .*already exists.* => no"' "$(dialogs)"
    answer yes
    panel cloudflare_route_dns koha-library catalog.example.org
    assert 'calls | grep -q "cloudflared tunnel route dns -f koha-library catalog.example.org"' "$(calls)"
}
