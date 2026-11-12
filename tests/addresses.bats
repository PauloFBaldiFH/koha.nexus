#!/usr/bin/env bats
# The "Addresses and access" screen (installer: kei_addresses, study 17.4):
# the configured address, the other names of this server for the same
# port, and, only when asked, a test of each from this server. Read only.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_TAINACAN_DIR="$T/owned/platforms/tainacan"
    mkdir -p "$T/bin" "$KEI_TAINACAN_DIR"
    for c in bash sh awk sed grep cat mkdir mktemp mv rm chmod cp tr head tail cut sort printf date env python3; do
        p=$(command -v "$c" 2>/dev/null) && ln -sf "$p" "$T/bin/$c"
    done
    # Two interfaces: the local network and a VPN (never offered).
    cat > "$T/bin/ip" <<'SH'
#!/bin/sh
echo "2: eth0    inet 192.168.0.20/24 brd 192.168.0.255 scope global eth0"
echo "5: tun0    inet 10.8.0.2/24 scope global tun0"
SH
    # curl: answers 302 to the configured address for localhost, 200 else;
    # every call is logged (only reads: no -X, no -d).
    cat > "$T/bin/curl" <<SH
#!/bin/sh
echo "\$*" >> "$T/curl.log"
for a; do last=\$a; done
case "\$last" in *localhost*) printf '302|http://192.168.0.20:8090/' ;; *) printf '200|' ;; esac
SH
    chmod +x "$T/bin/ip" "$T/bin/curl"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
# kei_result is defined after the line that ends a sourced installer.
kei_result() { printf '@@result %s=%s\n' "\$1" "\$2"; }
KEI_PLATFORM=linux
PATH='$T/bin'
$1" 3>&-
}

@test "Tainacan: the configured address, localhost and the network address; the VPN is left out" {
    printf 'status=installed\nurl=http://192.168.0.20:8090/\n' > "$KEI_TAINACAN_DIR/state"
    run lib 'kei_addresses tainacan'
    [ "$status" -eq 0 ]
    grep -qx '@@result configured=site|http://192.168.0.20:8090' <<< "$output"
    grep -qx '@@result alternative=site|http://localhost:8090' <<< "$output"
    ! grep -q '10.8.0.2' <<< "$output"
    # The configured one is not repeated as an alternative; nothing tested.
    [ "$(grep -c '192.168.0.20:8090' <<< "$output")" = 1 ]
    ! grep -q 'check=' <<< "$output"
    [ ! -f "$T/curl.log" ]
}

@test "test: each address opened from this server, only reads" {
    printf 'status=installed\nurl=http://192.168.0.20:8090/\n' > "$KEI_TAINACAN_DIR/state"
    run lib 'kei_addresses tainacan test'
    [ "$status" -eq 0 ]
    grep -q '^@@result check=http://192.168.0.20:8090|200||[0-9]*$' <<< "$output"
    grep -q '^@@result check=http://localhost:8090|302|http://192.168.0.20:8090/|[0-9]*$' <<< "$output"
    ! grep -Eq -- '(^| )-(X|d|F|T)( |$)|--data|--request' "$T/curl.log"
}

@test "Koha: empty preferences are said, ports 80 and 8080 still listed" {
    run lib 'is_koha_installed() { return 0; }; is_database_ready() { return 0; }; run_sql() { :; }; kei_addresses koha'
    [ "$status" -eq 0 ]
    grep -qx '@@result unset=opac' <<< "$output"
    grep -qx '@@result unset=staff' <<< "$output"
    grep -qx '@@result alternative=opac|http://192.168.0.20' <<< "$output"
    grep -qx '@@result alternative=staff|http://192.168.0.20:8080' <<< "$output"
}

@test "Koha: OPACBaseURL is the configured address" {
    run lib "is_koha_installed() { return 0; }; is_database_ready() { return 0; }
run_sql() { case \"\$1\" in *OPACBaseURL*) echo 'https://catalog.example.org/' ;; esac; }; kei_addresses koha"
    grep -qx '@@result configured=opac|https://catalog.example.org' <<< "$output"
    grep -qx '@@result unset=staff' <<< "$output"
    grep -qx '@@result alternative=opac|https://localhost' <<< "$output"
}

@test "unknown platform or Koha missing: refused" {
    run lib 'kei_addresses atom'
    [ "$status" -eq 2 ]
    run lib 'is_koha_installed() { return 1; }; kei_addresses koha'
    [ "$status" -eq 3 ]
}
