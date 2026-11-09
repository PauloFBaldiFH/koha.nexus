#!/usr/bin/env bats
# Address validation and the real generated Apache virtual host in a disposable runner.
setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
}
lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
kei_ip_interface() { [ \"\$1\" = 192.168.100.56 ] && printf eth1; }
is_wsl() { [ \"\${TEST_WSL:-no}\" = yes ]; }
$1"
}
@test "DSpace rejects an example IP not assigned to the server" {
    run lib 'kei_dspace_address_check http://192.168.1.50:8100'
    [ "$status" -eq 4 ]
    [[ "$output" == *'IPv4 address was not found'* ]]
}
@test "DSpace accepts the actual local IPv4 and localhost" {
    run lib 'kei_dspace_address_check http://192.168.100.56:8100'
    [ "$status" -eq 0 ]
    run lib 'kei_dspace_address_check http://localhost:8100'
    [ "$status" -eq 0 ]
}
@test "WSL accepts the IPv4 reported by the Windows integration" {
    run lib 'TEST_WSL=yes; WIN_LAN_IP=192.168.100.77; kei_dspace_address_check http://192.168.100.77:8100'
    [ "$status" -eq 0 ]
}
@test "generated Apache redirects aliases to a fixed canonical host and preserves paths and queries" {
    command -v apache2 >/dev/null || skip 'Apache required for the disposable integration test'
    mkdir -p "$T/http" "$T/run"
    printf 'healthy fixture' > "$T/http/index.html"
    chmod 755 "$T" "$T/http" "$T/run"
    python3 -m http.server 28112 --bind 127.0.0.1 --directory "$T/http" > "$T/fixture.log" 2>&1 &
    fixture_pid=$!
    python3 - "$REPO" > "$T/vhost.conf" <<'PY'
import sys
sys.path.insert(0,sys.argv[1]+'/platforms/dspace')
from runtime import Runtime
r=Runtime('/tmp/unused-web-test/dspace',lab=True)
r.state=lambda:dict(url='http://127.0.0.1:28110',ports={'ui':28112,'backend':28112})
print(r.proxy_config())
PY
    a2enmod proxy proxy_http headers rewrite >/dev/null 2>&1
    cat > "$T/apache.conf" <<EOF
ServerRoot /etc/apache2
IncludeOptional mods-enabled/*.load
IncludeOptional mods-enabled/*.conf
ServerName 127.0.0.1
DefaultRuntimeDir "$T/run"
PidFile "$T/run/apache.pid"
ErrorLog "$T/apache.log"
User www-data
Group www-data
Include "$T/vhost.conf"
EOF
    apache2 -t -f "$T/apache.conf"
    apache2 -f "$T/apache.conf" -DFOREGROUND > "$T/server.log" 2>&1 &
    apache_pid=$!
    for i in {1..60}; do
        curl --noproxy '*' -fsS http://127.0.0.1:28110/ -o "$T/body" 2>/dev/null && break
        sleep 0.1
    done
    run curl --noproxy '*' -sS -D - -o /dev/null -H 'Host: localhost:28110' 'http://127.0.0.1:28110/login?next=a%20b'
    [ "$status" -eq 0 ]
    [[ "$output" == *'307 Temporary Redirect'* ]]
    [[ "$output" == *'Location: http://127.0.0.1:28110/login?next=a%20b'* ]]
    run curl --noproxy '*' -sS -D - -o /dev/null -H 'Host: attacker.example' http://127.0.0.1:28110/
    [[ "$output" == *'Location: http://127.0.0.1:28110/'* ]]
    [[ "$output" != *'Location: http://attacker'* ]]
    grep -q 'healthy fixture' "$T/body"
}
teardown() {
    [ -z "${apache_pid:-}" ] || kill "$apache_pid" 2>/dev/null || true
    [ -z "${fixture_pid:-}" ] || kill "$fixture_pid" 2>/dev/null || true
}
