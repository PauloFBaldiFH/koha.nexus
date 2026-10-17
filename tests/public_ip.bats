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

# ip and hostname stand-ins: KEI_IP_ROUTE is what "ip -4 route get" prints,
# KEI_IP_ADDR the "ip -4 -o addr" lines, KEI_HOSTNAME_I what hostname -I says.
fake_net() {
    cat > "$W/bin/ip" <<'SH'
#!/bin/bash
case "$*" in
    *"route get"*) printf '%s\n' "${KEI_IP_ROUTE:-}" ;;
    *addr*) printf '%s\n' "${KEI_IP_ADDR:-}" ;;
esac
SH
    cat > "$W/bin/hostname" <<'SH'
#!/bin/bash
[ "$1" = "-I" ] && printf '%s\n' "${KEI_HOSTNAME_I:-}"
SH
    chmod +x "$W/bin/ip" "$W/bin/hostname"
}

@test "the server address is the word after src, whatever the route line holds" {
    fake_net
    KEI_IP_ROUTE="1.1.1.1 via 192.168.0.1 dev eth0 src 192.168.0.42 uid 0" run run_net "get_server_ip"
    [ "$output" = "192.168.0.42" ]
    # WSL2 mirrored networking: no gateway, the 7th word is the uid "0".
    KEI_IP_ROUTE="1.1.1.1 dev eth0 src 192.168.1.77 uid 0" run run_net "get_server_ip"
    [ "$output" = "192.168.1.77" ]
    KEI_IP_ROUTE="1.1.1.1 via 10.0.0.1 dev eth1 table 127 src 10.0.0.9 uid 1000" run run_net "get_server_ip"
    [ "$output" = "10.0.0.9" ]
}

@test "no usable route address: Windows' address, then hostname -I, then ip addr" {
    fake_net
    KEI_IP_ROUTE="1.1.1.1 dev loopback0 src 0 uid 0" WIN_LAN_IP=192.168.5.20 KEI_HOSTNAME_I="172.20.1.2" \
        run run_net "get_server_ip"
    [ "$output" = "192.168.5.20" ]
    KEI_IP_ROUTE="" KEI_HOSTNAME_I="127.0.0.1 169.254.3.4 192.168.5.21 fe80::1" run run_net "get_server_ip"
    [ "$output" = "192.168.5.21" ]
    KEI_IP_ROUTE="" KEI_HOSTNAME_I="" KEI_IP_ADDR="2: eth0    inet 10.1.2.3/24 brd 10.1.2.255 scope global eth0" \
        run run_net "get_server_ip"
    [ "$output" = "10.1.2.3" ]
    KEI_IP_ROUTE="" KEI_HOSTNAME_I="0" KEI_IP_ADDR="" run run_net "get_server_ip"
    [ "$output" = "127.0.0.1" ]
}

@test "only dotted IPv4 addresses another machine can use count" {
    for ip in 192.168.0.1 10.0.0.60 172.20.1.2 203.0.113.7; do
        run run_net "lan_ip_usable $ip"; [ "$status" -eq 0 ]
    done
    for ip in 0 0.0.0.0 127.0.0.1 169.254.9.9 224.0.0.1 255.255.255.255 192.168.0.256 1.2.3 abc ""; do
        run run_net "lan_ip_usable '$ip'"; [ "$status" -ne 0 ]
    done
}
