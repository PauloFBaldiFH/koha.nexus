#!/usr/bin/env bats
# The port of a new site (U9, study 16.2): kei_port_owner / kei_port_check
# say who uses a port and suggest the next free one. Read only.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_APACHE_DIR="$T/apache"
    mkdir -p "$T/bin" "$KEI_APACHE_DIR/sites-enabled" "$KEI_OWNED_DIR"
    for c in bash sh awk sed grep cat mkdir mktemp mv rm chmod cp tr head tail cut sort printf date env python3 seq; do
        p=$(command -v "$c" 2>/dev/null) && ln -sf "$p" "$T/bin/$c"
    done
    # Listeners: nginx on 8091, docker on 9000, Apache on 80; every call logged.
    cat > "$T/bin/ss" <<SH
#!/bin/sh
echo "\$*" >> "$T/ss.log"
echo 'LISTEN 0 511 0.0.0.0:8091 0.0.0.0:* users:(("nginx",pid=10,fd=6))'
echo 'LISTEN 0 4096 0.0.0.0:9000 0.0.0.0:* users:(("docker-proxy",pid=11,fd=4))'
echo 'LISTEN 0 511 *:80 *:* users:(("apache2",pid=12,fd=4))'
SH
    cat > "$T/bin/ip" <<'SH'
#!/bin/sh
case "$*" in
    *route*) echo "1.1.1.1 via 192.168.0.1 dev eth0 src 192.168.0.20 uid 0" ;;
    *) echo "2: eth0    inet 192.168.0.20/24 brd 192.168.0.255 scope global eth0" ;;
esac
SH
    chmod +x "$T/bin/ss" "$T/bin/ip"
    printf 'Listen 80\nListen 8095\n' > "$KEI_APACHE_DIR/ports.conf"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
kei_result() { printf '@@result %s=%s\n' \"\$1\" \"\$2\"; }
msg_error() { printf 'ERROR %s\n' \"\$2\"; }
is_koha_installed() { return 1; }
kei_dspace_runtime() { echo '{\"url\": \"http://192.168.0.20:8100\"}'; }
_kei_tn_get() { case \"\$1\" in status) echo installed ;; lan_port) echo 8090 ;; esac; }
KEI_PLATFORM=linux
PATH='$T/bin'
$1" 3>&-
}

@test "who uses a port: the systems, reserved ports, programs and Apache" {
    run lib 'for p in 8090 8100 18100 18091 8091 9000 8095 8092; do printf "%s=%s\n" "$p" "$(kei_port_owner $p)"; done'
    [ "$status" -eq 0 ]
    [ "$output" = $'8090=tainacan\n8100=dspace\n18100=reserved\n18091=reserved\n8091=other:nginx\n9000=docker\n8095=apache\n8092=' ]
}

@test "Koha's ports when Koha is installed" {
    run lib 'is_koha_installed() { return 0; }; kei_port_owner 80; kei_port_owner 8080'
    [ "$output" = $'koha\nkoha' ]
    run lib 'kei_port_owner 80'
    [ "$output" = apache ]
}

@test "check: free, the system's own, used with a suggestion, invalid" {
    run lib 'kei_port_check 8092'
    grep -qx '@@result state=free' <<< "$output"
    grep -qx '@@result lan=192.168.0.20' <<< "$output"
    run lib 'kei_port_check 8090 tainacan'
    grep -qx '@@result state=mine' <<< "$output"
    run lib 'kei_port_check 8090 dspace'
    grep -qx '@@result state=used' <<< "$output"
    grep -qx '@@result owner=tainacan' <<< "$output"
    grep -qx '@@result suggest=8092' <<< "$output"
    for bad in 0 70000 abc ""; do
        run lib "kei_port_check '$bad'"
        [ "$status" -eq 2 ]
        grep -q 'Invalid port' <<< "$output"
    done
    # Only reads: ss lists, nothing else is called.
    ! grep -vq -- '-Hltnp' "$T/ss.log"
}

@test "the Tainacan plan refuses a port someone else uses" {
    run lib 'command() { [ "$2" = docker ] && return 0; builtin command "$@"; }
_kei_docker_running() { return 0; }; _kei_docker() { return 0; }; _kei_tn_mem_mb() { echo 99999; }; _kei_tn_disk_mb() { echo 99999; }
_kei_tn_get() { case "$1" in status) echo absent ;; esac; }
kei_proxy_detect() { echo "apache -"; }
kei_tainacan_plan http://192.168.0.20:8091'
    [ "$status" -eq 3 ]
    grep -q $'^plan\trefuse' <<< "$output"
    grep -q 'Port 8091 is already in use (other:nginx)' <<< "$output"
}

@test "web ports: the installed systems' ports, for Windows (U9 part 2)" {
    run lib 'is_koha_installed() { OPACPORT=80 INTRAPORT=8080; return 0; }; kei_web_ports'
    [ "$status" -eq 0 ]
    [ "$output" = $'@@result port=80\n@@result port=8080\n@@result port=8090\n@@result port=8100' ]
    # Koha absent, Tainacan without a local-network port, DSpace on an https name: nothing.
    run lib '_kei_tn_get() { :; }; kei_dspace_runtime() { echo "{\"url\": \"https://repo.example.org\"}"; }; kei_web_ports'
    [ "$status" -eq 0 ] && [ -z "$output" ]
    # Own ports, a broken DSpace answer and duplicates.
    run lib 'is_koha_installed() { OPACPORT=8000 INTRAPORT=8001; return 0; }; _kei_tn_get() { [ "$1" = lan_port ] && echo 8001; }; kei_dspace_runtime() { echo "{not json"; }; kei_web_ports'
    [ "$output" = $'@@result port=8000\n@@result port=8001' ]
    # The DSpace port still names its owner.
    run lib 'kei_port_owner 8100'
    [ "$output" = dspace ]
}
