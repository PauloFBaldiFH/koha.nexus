#!/usr/bin/env bats
# Cloud servers (Oracle Cloud, AWS, DigitalOcean) bind a private address
# (10.0.0.60): the banners and the dashboard add the public one. Runs the
# address helpers alone, with curl replaced by a stub.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    sed -n '/^get_server_ip() {/,/^get_database_password() {/p' "$REPO/installer" | sed '$d' > "$W/net.sh"
    export KEI_PUBLIC_IP_CACHE="$W/cache/public-ip"
    mkdir -p "$W/bin"
    cat > "$W/bin/curl" <<'SH'
#!/bin/bash
echo "$*" >> "$KEI_CURL_LOG"
case "$*" in *ipify*) printf '%s' "${KEI_CURL_IPIFY:-}" ;; *ifconfig.me*) printf '%s' "${KEI_CURL_IFCONFIG:-}" ;; esac
SH
    chmod +x "$W/bin/curl"
    export PATH="$W/bin:$PATH" KEI_CURL_LOG="$W/curl.log"
}

run_net() { bash -c "host_can() { [ \"\${KEI_LAN:-yes}\" = yes ]; }; source '$W/net.sh'; $1"; }

@test "private, CGNAT and loopback addresses are private; others are not" {
    for ip in 10.0.0.60 172.16.4.1 172.31.255.1 192.168.1.10 100.64.0.1 100.127.9.9 127.0.0.1 169.254.1.1; do
        run run_net "ip_is_private $ip"; [ "$status" -eq 0 ]
    done
    for ip in 8.8.8.8 172.15.0.1 172.32.0.1 100.63.0.1 100.128.0.1 203.0.113.7 11.0.0.1; do
        run run_net "ip_is_private $ip"; [ "$status" -ne 0 ]
    done
}

@test "the public address is asked once, then read from the cache" {
    export KEI_CURL_IPIFY="203.0.113.7"
    run run_net "server_public_ip 10.0.0.60"
    [ "$output" = "203.0.113.7" ]
    export KEI_CURL_IPIFY="198.51.100.1"
    run run_net "server_public_ip 10.0.0.60"
    [ "$output" = "203.0.113.7" ]
    [ "$(grep -c ipify "$KEI_CURL_LOG")" = "1" ]
    grep -q -- "--max-time" "$KEI_CURL_LOG"
}

@test "the second service answers when the first one does not; junk is ignored" {
    export KEI_CURL_IPIFY="<html>blocked</html>" KEI_CURL_IFCONFIG="198.51.100.20"
    run run_net "get_public_ip"
    [ "$output" = "198.51.100.20" ]
}

@test "no question when the address is already public, or under WSL" {
    run run_net "server_public_ip 203.0.113.7"
    [ -z "$output" ]
    KEI_LAN=no run run_net "server_public_ip 10.0.0.60"
    [ -z "$output" ]
    [ ! -s "$KEI_CURL_LOG" ]
}
