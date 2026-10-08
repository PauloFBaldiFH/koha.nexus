#!/usr/bin/env bats
# WireGuard VPN (section 42): the server's wg0.conf, the devices' profiles
# (split tunnel 10.66.0.0/24, MTU 1360, keepalive 25, no DNS), revoking and
# the state read by the panel. The real `wg` makes the keys; a stand-in
# records the rest (no interface is created).

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    rm -f "$KEI_S/dialogs.log"
    mkdir -p "$W/bin" "$W/etc"
    REAL_WG=$(command -v wg)
    cat > "$W/bin/wg" <<SH
#!/bin/sh
case "\$1" in
    genkey|pubkey|genpsk) exec "$REAL_WG" "\$@" ;;
    show) [ -f "$W/dump" ] && [ "\$3" = dump ] && cat "$W/dump"; [ -e "$W/up" ] ;;
    *) echo "wg \$*" >> "$W/calls" ;;
esac
SH
    printf '#!/bin/sh\necho "wg-quick $*" >> "%s/calls"\n' "$W" > "$W/bin/wg-quick"
    printf '#!/bin/sh\necho "ufw $*" >> "%s/calls"\n' "$W" > "$W/bin/ufw"
    printf '#!/bin/sh\necho "sysctl $*" >> "%s/calls"\n' "$W" > "$W/bin/sysctl"
    printf '#!/bin/sh\nexit 1\n' > "$W/bin/curl"
    chmod +x "$W/bin/"*
    cat > "$W/extra.sh" <<SH
SYS_LANG=en
kei_result() { printf 'RESULT %s=%s\n' "\$1" "\$2" >> "$W/results"; }
host_can() { [ "\$1" != lan_direct ] || [ ! -e "$W/wsl" ]; }
apt_install() { echo "apt_install \$*" >> "$W/calls"; }
systemctl() { echo "systemctl \$*" >> "$W/calls"; case "\$*" in *restart*) touch "$W/up" ;; *disable*) rm -f "$W/up" ;; esac; }
sshd() { printf 'port 2222\n'; }
TOOLS_LOG_DIR="$W/logs"
RUN_LOG="$W/run.log"
CONFIG_DIR="$W/etc"
WG_DIR="$W/wireguard"
WG_CONF="$W/wireguard/wg0.conf"
WG_KEY="$W/wireguard/kei-server.key"
WG_PEERS="$W/wireguard/kei-peers"
WG_STATE="$W/etc/wireguard.conf"
WG_SYSCTL="$W/99-kei-wireguard.conf"
PATH="$W/bin:\$PATH"
SH
}

task() { run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" "$@"; echo "$output"; cat "$KEI_S/dialogs.log" 2>/dev/null || true; }

@test "vpn-setup: wg0.conf with NAT, ip_forward, MTU, the UDP port and the service" {
    task vpn_setup vpn.example.org 51820
    [ "$status" -eq 0 ]
    grep -q "OK ✅ The VPN is on: this server is 10.66.0.1 inside it, UDP port 51820" "$KEI_S/dialogs.log"
    conf="$W/wireguard/wg0.conf"
    [ "$(stat -c %a "$conf")" = "600" ] && [ "$(stat -c %a "$W/wireguard/kei-server.key")" = "600" ]
    grep -qx "Address = 10.66.0.1/24" "$conf"
    grep -qx "ListenPort = 51820" "$conf"
    grep -qx "MTU = 1360" "$conf"
    grep -qx "PrivateKey = $(cat "$W/wireguard/kei-server.key")" "$conf"
    grep -q "^PostUp = .*iptables -t nat -A POSTROUTING -s 10.66.0.0/24 -o [^ ]* -j MASQUERADE" "$conf"
    grep -q "^PostDown = .*iptables -t nat -D POSTROUTING -s 10.66.0.0/24" "$conf"
    grep -qx "net.ipv4.ip_forward = 1" "$W/99-kei-wireguard.conf"
    grep -q "ufw allow 51820/udp" "$W/calls"
    grep -q "ufw allow in on wg0 to any port 8080 proto tcp" "$W/calls"
    grep -q "ufw allow in on wg0 to any port 2222 proto tcp" "$W/calls"
    grep -q "systemctl enable wg-quick@wg0" "$W/calls"
    printf 'ENDPOINT=vpn.example.org\nPORT=51820\n' | cmp - "$W/etc/wireguard.conf"
    # Run again: the same key.
    key=$(cat "$W/wireguard/kei-server.key")
    task vpn_setup vpn.example.org 51821
    [ "$(cat "$W/wireguard/kei-server.key")" = "$key" ]
}

@test "vpn-setup: bad answers, WSL without mirrored networking, a VPN that does not start" {
    for args in "bad_name! 51820" "vpn.example.org 80" "vpn.example.org port"; do
        task vpn_setup $args
        [ "$status" -eq 1 ]
    done
    [ ! -e "$W/wireguard/wg0.conf" ]
    touch "$W/wsl"
    task vpn_setup vpn.example.org 51820
    [ "$status" -eq 1 ]
    grep -q "ERROR .*mirrored networking" "$KEI_S/dialogs.log"
    rm -f "$W/wsl"
    printf 'systemctl() { echo "systemctl \\$*" >> "%s/calls"; }\n' "$W" >> "$W/extra.sh"
    task vpn_setup vpn.example.org 51820
    [ "$status" -eq 1 ]
    grep -q "ERROR .*the VPN did not start" "$KEI_S/dialogs.log"
}

@test "vpn-peer-add: a split-tunnel profile, no DNS, its own address and key" {
    task vpn_setup 203.0.113.7 51820
    task vpn_peer_add laptop
    [ "$status" -eq 0 ]
    grep -q "OK ✅ Device laptop added with the address 10.66.0.2" "$KEI_S/dialogs.log"
    conf="$W/wireguard/kei-peers/laptop.conf"
    [ "$(stat -c %a "$conf")" = "600" ] && [ "$(stat -c %a "$W/wireguard/kei-peers/laptop.peer")" = "600" ]
    grep -qx "Address = 10.66.0.2/32" "$conf"
    grep -qx "AllowedIPs = 10.66.0.0/24" "$conf"
    grep -qx "MTU = 1360" "$conf"
    grep -qx "PersistentKeepalive = 25" "$conf"
    grep -qx "Endpoint = 203.0.113.7:51820" "$conf"
    ! grep -q "0.0.0.0/0" "$conf"
    ! grep -qi "^DNS" "$conf"
    grep -qx "PublicKey = $(wg pubkey < "$W/wireguard/kei-server.key")" "$conf"
    # The server knows the device's public key, never its private one.
    priv=$(sed -n 's/^PrivateKey = //p' "$conf")
    grep -qx "PublicKey = $(printf '%s\n' "$priv" | wg pubkey)" "$W/wireguard/wg0.conf"
    grep -qx "AllowedIPs = 10.66.0.2/32" "$W/wireguard/wg0.conf"
    ! grep -q "$priv" "$W/wireguard/wg0.conf"
    # The PSK is the same on both sides.
    [ "$(sed -n 's/^PresharedKey = //p' "$conf")" = "$(sed -n 's/^PresharedKey = //p' "$W/wireguard/kei-peers/laptop.peer")" ]
    grep -q "wg syncconf wg0" "$W/calls"
    grep -q "RESULT conf=$conf" "$W/results"
    # The next device takes the next address; a taken name is refused.
    task vpn_peer_add phone
    grep -qx "Address = 10.66.0.3/32" "$W/wireguard/kei-peers/phone.conf"
    task vpn_peer_add laptop
    [ "$status" -eq 1 ]
    task vpn_peer_add "../x"
    [ "$status" -eq 1 ]
}

@test "vpn-peer-add: refused before setup; a freed address is used again" {
    task vpn_peer_add laptop
    [ "$status" -eq 1 ]
    grep -q "ERROR .*Set up the VPN first" "$KEI_S/dialogs.log"
    task vpn_setup vpn.example.org 51820
    task vpn_peer_add a
    task vpn_peer_add b
    task vpn_peer_revoke a
    task vpn_peer_add c
    grep -qx "Address = 10.66.0.2/32" "$W/wireguard/kei-peers/c.conf"
}

@test "vpn-peer-revoke: the device is gone from wg0.conf and its profile deleted" {
    task vpn_setup vpn.example.org 51820
    task vpn_peer_add laptop
    pub=$(sed -n 's/^PublicKey = //p' "$W/wireguard/kei-peers/laptop.peer")
    task vpn_peer_revoke laptop
    [ "$status" -eq 0 ]
    [ ! -e "$W/wireguard/kei-peers/laptop.conf" ] && [ ! -e "$W/wireguard/kei-peers/laptop.peer" ]
    ! grep -q "$pub" "$W/wireguard/wg0.conf"
    grep -q "OK Device laptop revoked" "$KEI_S/dialogs.log"
    task vpn_peer_revoke laptop
    [ "$status" -eq 1 ]
}

@test "vpn-setup: a new endpoint goes into the devices' profiles" {
    task vpn_setup old.example.org 51820
    task vpn_peer_add laptop
    task vpn_setup new.example.org 51999
    grep -qx "Endpoint = new.example.org:51999" "$W/wireguard/kei-peers/laptop.conf"
    grep -q "import their profiles again" "$KEI_S/dialogs.log"
    grep -q "AllowedIPs = 10.66.0.2/32" "$W/wireguard/wg0.conf"
}

@test "vpn-status: state and each device's traffic" {
    task vpn_status
    grep -q "RESULT configured=no" "$W/results"
    rm -f "$W/results"
    task vpn_setup vpn.example.org 51820
    task vpn_peer_add laptop
    pub=$(sed -n 's/^PublicKey = //p' "$W/wireguard/kei-peers/laptop.peer")
    printf 'PRIV\tPUB\t51820\toff\n%s\t(none)\t198.51.100.4:40000\t10.66.0.2/32\t1760000000\t1234\t5678\t25\n' "$pub" > "$W/dump"
    rm -f "$W/results"
    task vpn_status
    [ "$status" -eq 0 ]
    grep -q "RESULT configured=yes" "$W/results"
    grep -q "RESULT running=yes" "$W/results"
    grep -q "RESULT endpoint=vpn.example.org" "$W/results"
    grep -q "RESULT port=51820" "$W/results"
    grep -q "RESULT ssh_port=2222" "$W/results"
    grep -q "$(printf 'RESULT peer=laptop\t10.66.0.2\t1760000000\t1234\t5678')" "$W/results"
    ! grep -qi "private\|$(cat "$W/wireguard/kei-server.key")" "$W/results"
}

@test "vpn-stop: the service is stopped, the keys and devices kept" {
    task vpn_setup vpn.example.org 51820
    task vpn_peer_add laptop
    task vpn_stop
    [ "$status" -eq 0 ]
    grep -q "systemctl disable --now wg-quick@wg0" "$W/calls"
    [ -s "$W/wireguard/kei-server.key" ] && [ -e "$W/wireguard/kei-peers/laptop.conf" ]
}

@test "vpn: the panel knows the tasks" {
    for task in vpn-status vpn-setup vpn-peer-add vpn-peer-revoke vpn-stop; do
        grep -q "^        ${task}) " "$KEI_REPO/installer"
    done
}
