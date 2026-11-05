#!/usr/bin/env bats
# Docker with consent, on a real machine (installer: kei_docker_*). It
# installs Docker the way the panel does, creates two platform networks
# and checks the isolation tests of the study (6.3):
#   1. no new listening port outside 127.0.0.1;
#   2. from another machine, the published and internal ports are closed;
#   3. from a container, the host's services (3306, 11211, 9200, 5672,
#      11434) are refused;
#   4. one platform cannot reach another;
#   5. the VPN (WireGuard when the kernel has it, otherwise a link with
#      the same firewall rules) works before and after Docker;
#   6. Apache (a stand-in for Koha's site) answers as before.
# Then removal: only what is labelled and registered goes; what belongs to
# others stays; Docker is removed only when Koha.Nexus installed it and
# nothing is left in it.
#
# DESTRUCTIVE: installs and purges packages, changes the firewall. It only
# runs with KEI_DESTRUCTIVE_TESTS=1, as root, under systemd, in a throwaway
# machine: tests/system/container.sh (CI: .github/workflows/proxy.yml).
# The tests depend on each other and run in order.

IMG="${KEI_TEST_IMAGE:-mirror.gcr.io/library/busybox:1.36}"
LABELS_A=(--label com.koha-nexus.managed=true --label com.koha-nexus.platform=alpha)
LABELS_B=(--label com.koha-nexus.managed=true --label com.koha-nexus.platform=beta)
HOST_PORTS="3306 11211 9200 5672 11434"

setup_file() {
    [ "${KEI_DESTRUCTIVE_TESTS:-}" = 1 ] || skip "destructive: set KEI_DESTRUCTIVE_TESTS=1 in a throwaway machine"
    [ "$(id -u)" = 0 ] || skip "needs root"
    [ -d /run/systemd/system ] || skip "needs systemd"
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
    # The isolation unit runs the installed panel, as on a real server.
    install -m 755 "$REPO/installer" /usr/local/bin/config.sh
    command -v docker >/dev/null 2>&1 && echo yes > "$S/docker_before" || echo no > "$S/docker_before"
    koha_apache
    apache2ctl -S 2>/dev/null | sort > "$S/apache_before"
    # Services of the host that a container must not reach.
    for p in $HOST_PORTS; do
        setsid python3 -m http.server "$p" --bind 0.0.0.0 >/dev/null 2>&1 3>&- &
    done
    vpn_up
    lan_up
    # A route that uses the first candidate /24: the platforms must avoid it.
    ip link add kntest0 type dummy 2>/dev/null || ip link add kntest0 type veth peer name kntest1
    ip addr add 10.213.1.1/24 dev kntest0
    ip link set kntest0 up
    sleep 1
    ss -Hltn | awk '{ print $4 }' | sort -u > "$S/listen_before"
}

teardown_file() {
    pkill -f 'http.server' 2>/dev/null || true
    ip netns del knpeer 2>/dev/null || true
    ip netns del knlan 2>/dev/null || true
    rm -f /etc/wireguard/kn-test-s.key /etc/wireguard/kn-test-p.key
}

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
$1" 3>&-
}

koha_apache() {
    mkdir -p /var/www/kei-opac /var/www/kei-staff
    echo OPAC > /var/www/kei-opac/index.html
    echo STAFF > /var/www/kei-staff/index.html
    grep -qE '^Listen 8080$' /etc/apache2/ports.conf || echo 'Listen 8080' >> /etc/apache2/ports.conf
    cat > /etc/apache2/sites-available/library.conf <<'EOF'
<VirtualHost *:80>
    ServerName catalog.kei.test
    DocumentRoot /var/www/kei-opac
</VirtualHost>
<VirtualHost *:8080>
    ServerName staff.kei.test
    DocumentRoot /var/www/kei-staff
</VirtualHost>
<Directory /var/www/kei-opac>
    Require all granted
</Directory>
<Directory /var/www/kei-staff>
    Require all granted
</Directory>
EOF
    a2dissite -q 000-default >/dev/null 2>&1 || true
    a2ensite -q library >/dev/null
    systemctl reset-failed apache2 2>/dev/null || true
    systemctl restart apache2
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        [ "$(curl -s http://127.0.0.1/)" = OPAC ] && return 0
        sleep 1
    done
    return 1
}

koha_answers_as_before() {
    [ "$(curl -s http://127.0.0.1/)" = OPAC ]
    [ "$(curl -s http://127.0.0.1:8080/)" = STAFF ]
    diff <(apache2ctl -S 2>/dev/null | sort) "$S/apache_before"
}

# The VPN: the server is 10.66.0.1 on wg0, a device 10.66.0.2, with the
# installer's own rules (vpn_setup: FORWARD -i/-o wg0 ACCEPT).
vpn_up() {
    ip netns add knpeer
    ip link add knul0 type veth peer name knul1
    ip link set knul1 netns knpeer
    ip addr add 198.51.100.1/24 dev knul0; ip link set knul0 up
    ip -n knpeer addr add 198.51.100.2/24 dev knul1; ip -n knpeer link set knul1 up; ip -n knpeer link set lo up
    if ip link add wg0 type wireguard 2>/dev/null && wg_up 2>"$S/wg.err"; then
        echo wireguard > "$S/vpn"
    else
        # Where the kernel has WireGuard (CI sets KEI_REQUIRE_WIREGUARD=1
        # after modprobe), a failure here fails the test: no silent fallback.
        if [ "${KEI_REQUIRE_WIREGUARD:-}" = 1 ]; then
            echo "WireGuard required but not set up: $(cat "$S/wg.err" 2>/dev/null)" >&2
            return 1
        fi
        # No WireGuard in this kernel (or it could not be set up, said in
        # the test output): a plain link named wg0, with the same rules.
        [ -s "$S/wg.err" ] && echo "link without WireGuard ($(tr '\n' ' ' < "$S/wg.err"))" > "$S/vpn" \
            || echo "link without WireGuard" > "$S/vpn"
        ip link del wg0 2>/dev/null || true; ip -n knpeer link del wg1 2>/dev/null || true
        ip link add wg0 type veth peer name wg1
        ip link set wg1 netns knpeer
        ip addr add 10.66.0.1/24 dev wg0; ip link set wg0 up
        ip -n knpeer addr add 10.66.0.2/24 dev wg1; ip -n knpeer link set wg1 up
    fi
    sysctl -q -w net.ipv4.ip_forward=1
    iptables -A FORWARD -i wg0 -j ACCEPT
    iptables -A FORWARD -o wg0 -j ACCEPT
    ip netns exec knpeer setsid python3 -m http.server 8000 --bind 10.66.0.2 >/dev/null 2>&1 3>&- &
}

# Keys in /etc/wireguard, mode 600, where a real server keeps them. On the
# CI runner wg refused key files under /tmp ("fopen: Permission denied"),
# most likely the host's AppArmor profile for wg.
wg_up() {
    local d=/etc/wireguard sp pp
    ( umask 077; mkdir -p "$d" && wg genkey > "$d/kn-test-s.key" && wg genkey > "$d/kn-test-p.key" ) || return 1
    sp=$(wg pubkey < "$d/kn-test-s.key") && pp=$(wg pubkey < "$d/kn-test-p.key") || return 1
    wg set wg0 private-key "$d/kn-test-s.key" listen-port 51820 peer "$pp" allowed-ips 10.66.0.2/32 || return 1
    ip addr add 10.66.0.1/24 dev wg0 && ip link set wg0 up || return 1
    ip -n knpeer link add wg1 type wireguard || return 1
    ip netns exec knpeer wg set wg1 private-key "$d/kn-test-p.key" peer "$sp" \
        allowed-ips 10.66.0.0/24 endpoint 198.51.100.1:51820 persistent-keepalive 5 || return 1
    ip -n knpeer addr add 10.66.0.2/24 dev wg1 && ip -n knpeer link set wg1 up
}

vpn_works() {
    [ "$(ip netns exec knpeer curl -s --max-time 5 http://10.66.0.1/)" = OPAC ] \
        && curl -s -o /dev/null --max-time 5 http://10.66.0.2:8000/
}

# Another machine on the LAN: 192.0.2.2, the server being 192.0.2.1.
lan_up() {
    ip netns add knlan
    ip link add knlan0 type veth peer name knlan1
    ip link set knlan1 netns knlan
    ip addr add 192.0.2.1/24 dev knlan0; ip link set knlan0 up
    ip -n knlan addr add 192.0.2.2/24 dev knlan1; ip -n knlan link set knlan1 up; ip -n knlan link set lo up
    ip -n knlan route add default via 192.0.2.1
}

# nope CMD: fails when CMD succeeds. (A "! CMD" line that is not the last
# of a test is not checked by bats.)
nope() { ! "$@"; }

rules() { iptables -S "$1" 2>/dev/null; }

cip() { docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1"; }
cgw() { docker inspect -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}' "$1"; }
# reach CONTAINER URL: the container can open the URL.
reach() { docker exec "$1" wget -q -T 3 -O /dev/null "$2" 2>/dev/null; }

@test "the VPN and Apache work before Docker" {
    run vpn_works
    echo "VPN: $(cat "$S/vpn")" >&3
    [ "$status" -eq 0 ]
    koha_answers_as_before
}

@test "plan and consent: nothing is installed without confirm" {
    [ "$(cat "$S/docker_before")" = no ] || skip "Docker was already on this machine"
    run lib 'kei_docker_plan'
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "$(printf 'plan\tinstall')" ]
    run lib 'kei_docker_install'
    [ "$status" -eq 2 ]
    nope command -v docker
    [ ! -e /var/lib/koha-nexus/docker.state ]
}

@test "Docker is installed from the official repository; nothing else changes" {
    if [ "$(cat "$S/docker_before")" = yes ]; then
        run lib 'kei_docker_plan'
        [ "${lines[0]}" = "$(printf 'plan\tuse')" ]
        skip "Docker was already on this machine: used as it is"
    fi
    run lib 'kei_docker_install confirm'
    [ "$status" -eq 0 ]
    grep -qx 'installed_by=koha-nexus' /var/lib/koha-nexus/docker.state
    grep -q 'download.docker.com' /etc/apt/sources.list.d/docker.list
    systemctl is-active --quiet docker
    docker compose version >/dev/null
    [ ! -e /etc/docker/daemon.json ]
    [ -z "$(getent group docker | cut -d: -f4)" ]
    echo "Docker $(docker version --format '{{.Server.Version}}'), $(. /etc/os-release; echo "$PRETTY_NAME")" >&3
    docker pull -q "$IMG" >/dev/null
    # The VPN and Koha did not notice.
    run vpn_works
    [ "$status" -eq 0 ]
    koha_answers_as_before
}

@test "someone else's containers, networks and volumes (used later)" {
    docker network create someone-net >/dev/null
    docker volume create someone-data >/dev/null
    docker run -d --name someone --network someone-net -v someone-data:/data "$IMG" sleep 3600 >/dev/null
    # A network named like ours, without our labels.
    docker network create kn-gamma >/dev/null
    run lib 'kei_docker_network_create gamma'
    [ "$status" -eq 4 ]
    [ -z "$(docker network inspect -f '{{index .Labels "com.koha-nexus.managed"}}' kn-gamma)" ]
    run lib 'kei_owned_list docker-network'
    [ -z "$output" ]
    docker network rm kn-gamma >/dev/null
}

@test "each platform gets its own /24, away from routes, Docker networks and the VPN" {
    run lib 'kei_docker_network_create alpha'
    [ "$status" -eq 0 ]
    A="$output"
    run lib 'kei_docker_network_create beta'
    [ "$status" -eq 0 ]
    B="$output"
    [ "$A" != "$B" ]
    [ "$A" != 10.213.1.0/24 ]       # the dummy route
    [ "$A" != 10.66.0.0/24 ] && [ "$B" != 10.66.0.0/24 ]
    [ "$(docker network inspect -f '{{index .Labels "com.koha-nexus.managed"}} {{index .Labels "com.koha-nexus.platform"}}' kn-alpha)" = "true alpha" ]
    [ "$(docker network inspect -f '{{index .Labels "com.koha-nexus.managed"}} {{index .Labels "com.koha-nexus.platform"}}' kn-beta)" = "true beta" ]
    [ "$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}' kn-alpha)" = "$A" ]
    ip link show kn-alpha >/dev/null
    run lib 'kei_owned_list docker-network | cut -f1-3,6'
    [ "${lines[0]}" = "$(printf 'docker-network\tkn-alpha\talpha\t%s' "$A")" ]
    [ "${lines[1]}" = "$(printf 'docker-network\tkn-beta\tbeta\t%s' "$B")" ]
    systemctl is-enabled --quiet koha-nexus-docker-isolation
    # Twice is the same: nothing duplicated.
    run lib 'kei_docker_network_create alpha'
    [ "$output" = "$A" ]
    [ "$(iptables -S KN-INPUT | grep -c 'kn-alpha')" = 5 ]
    [ "$(iptables -S INPUT | grep -c 'KN-INPUT')" = 1 ]
    [ "$(iptables -S DOCKER-USER | grep -c 'KN-FORWARD')" = 1 ]
}

@test "the platforms' containers (as a platform will start them)" {
    docker run -d --name a1 --network kn-alpha "${LABELS_A[@]}" --security-opt no-new-privileges \
        -p 127.0.0.1:18080:8080 "$IMG" httpd -f -p 8080 -h /etc >/dev/null
    docker run -d --name a2 --network kn-alpha "${LABELS_A[@]}" --security-opt no-new-privileges "$IMG" sleep 3600 >/dev/null
    docker run -d --name b1 --network kn-beta "${LABELS_B[@]}" --security-opt no-new-privileges \
        -p 127.0.0.1:18081:8080 "$IMG" httpd -f -p 8080 -h /etc >/dev/null
    docker volume create "${LABELS_A[@]}" alpha-data >/dev/null
    sleep 1
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/passwd)" = 200 ]
    run lib 'kei_docker_audit alpha'
    [ "$status" -eq 0 ]
}

@test "isolation 1: no new listening port outside 127.0.0.1" {
    ss -Hltn | awk '{ print $4 }' | sort -u > "$S/listen_after"
    run comm -13 "$S/listen_before" "$S/listen_after"
    echo "new: $output" >&3
    [ -n "$output" ]
    run bash -c "comm -13 '$S/listen_before' '$S/listen_after' | grep -v '^127\.0\.0\.1:'"
    [ -z "$output" ]
}

@test "isolation 2: from another machine, published and internal ports are closed" {
    ip -n knlan route add 10.213.0.0/16 via 192.0.2.1 2>/dev/null || true
    # Control: the LAN machine reaches the server (Apache).
    [ "$(ip netns exec knlan curl -s --max-time 5 http://192.0.2.1/)" = OPAC ]
    run ip netns exec knlan curl -s --max-time 3 http://192.0.2.1:18080/passwd
    [ "$status" -ne 0 ]
    run ip netns exec knlan curl -s --max-time 3 "http://$(cip a1):8080/passwd"
    [ "$status" -ne 0 ]
}

@test "isolation 3: a container cannot reach the host's services" {
    local gw p
    gw=$(cgw a1)
    for p in $HOST_PORTS; do
        # Control: the service answers the host itself.
        curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$p/"
        if reach a1 "http://$gw:$p/"; then echo "open: $gw:$p" >&3; false; fi
        if reach a1 "http://192.0.2.1:$p/"; then echo "open: 192.0.2.1:$p" >&3; false; fi
    done
    # Control: a container outside the platform networks (Docker's default
    # bridge) does reach them: the block comes from the isolation rules.
    run docker run --rm "$IMG" sh -c "wget -q -T 3 -O /dev/null http://\$(ip route | awk '/default/ { print \$3 }'):3306/"
    [ "$status" -eq 0 ]
}

@test "isolation 4: a platform cannot reach another; inside a platform it works" {
    run reach a1 "http://$(cip b1):8080/passwd"
    [ "$status" -ne 0 ]
    run reach b1 "http://$(cip a1):8080/passwd"
    [ "$status" -ne 0 ]
    reach a2 "http://a1:8080/passwd"
}

@test "isolation 5: the VPN works with Docker; a container cannot reach its devices" {
    run vpn_works
    [ "$status" -eq 0 ]
    run reach a1 "http://10.66.0.2:8000/"
    [ "$status" -ne 0 ]
    # Control: without our chain the device answers (Docker lets it through).
    iptables -D DOCKER-USER -j KN-FORWARD
    run reach a1 "http://10.66.0.2:8000/"
    lib 'kei_docker_isolation_apply'
    [ "$status" -eq 0 ]
    nope reach a1 "http://10.66.0.2:8000/"
}

@test "isolation 6: Apache answers as before" {
    koha_answers_as_before
}

@test "audit: a container that breaks the rules is reported" {
    docker run -d --name a-bad --network kn-alpha "${LABELS_A[@]}" --privileged -p 18090:8080 \
        "$IMG" httpd -f -p 8080 -h /etc >/dev/null
    run lib 'kei_docker_audit alpha'
    docker rm -f a-bad >/dev/null
    [ "$status" -eq 1 ]
    [[ "$output" == *"a-bad	privileged"* ]]
    [[ "$output" == *"a-bad	no-new-privileges missing"* ]]
    [[ "$output" == *"a-bad	port 8080/tcp published on 0.0.0.0"* ]]
    [[ "$output" != *"a1	"* ]]
}

@test "Docker's nftables firewall backend: the same isolation holds" {
    mkdir -p /etc/docker
    echo '{"firewall-backend": "nftables"}' > /etc/docker/daemon.json
    systemctl restart docker
    for _ in $(seq 1 20); do docker info >/dev/null 2>&1 && break; sleep 1; done
    [ "$(docker info --format '{{.FirewallBackend.Driver}}')" = nftables ] || {
        rm -f /etc/docker/daemon.json; systemctl restart docker; skip "this Docker has no nftables backend"; }
    docker start a1 a2 b1 >/dev/null
    sleep 1
    [[ "$(rules FORWARD)" == *"-j KN-FORWARD"* ]]
    nope reach a1 "http://$(cgw a1):3306/"
    nope reach a1 "http://10.66.0.2:8000/"
    nope reach a1 "http://$(cip b1):8080/passwd"
    reach a2 "http://a1:8080/passwd"
    run vpn_works
    [ "$status" -eq 0 ]
    rm -f /etc/docker/daemon.json
    systemctl restart docker
    for _ in $(seq 1 20); do docker info >/dev/null 2>&1 && break; sleep 1; done
    [[ "$(rules DOCKER-USER)" == *"-j KN-FORWARD"* ]]
    [[ "$(rules FORWARD)" != *"-j KN-FORWARD"* ]]
}

@test "the rules come back when Docker restarts, and with UFW active" {
    iptables -F KN-INPUT; iptables -F KN-FORWARD
    systemctl restart docker
    for _ in $(seq 1 20); do docker info >/dev/null 2>&1 && break; sleep 1; done
    systemctl is-active --quiet koha-nexus-docker-isolation
    [ "$(iptables -S KN-INPUT | grep -c 'kn-alpha')" = 5 ]
    docker start a1 a2 b1 >/dev/null
    sleep 1
    nope reach a1 "http://$(cgw a1):3306/"
    # UFW on (and reloaded): the jump stays in front of its chains.
    ufw allow 22/tcp >/dev/null; ufw --force enable >/dev/null
    ufw reload >/dev/null
    echo "INPUT after ufw reload: $(rules INPUT | sed -n 2,3p | tr '\n' ' ')" >&3
    [[ "$(rules INPUT)" == *"-j KN-INPUT"* ]]
    nope reach a1 "http://$(cgw a1):3306/"
    ufw --force disable >/dev/null
}

@test "release: a network still in use stays and is reported" {
    run lib 'kei_platform_release beta'
    [ "$status" -eq 1 ]
    [[ "$output" == *"kept: docker-network kn-beta"* ]]
    docker network inspect kn-beta >/dev/null
    [[ "$(rules KN-INPUT)" == *kn-beta* ]]
}

@test "removal keeping data: containers and network go, volumes and others stay" {
    run lib 'kei_docker_platform_remove alpha keep'
    [ "$status" -eq 0 ]
    [ -z "$(docker ps -aq --filter label=com.koha-nexus.platform=alpha)" ]
    nope docker network inspect kn-alpha >/dev/null 2>&1
    docker volume inspect alpha-data >/dev/null
    [[ "$(rules KN-INPUT)" != *kn-alpha* ]]
    [[ "$(rules KN-INPUT)" == *kn-beta* ]]
    docker inspect someone >/dev/null && docker network inspect someone-net >/dev/null && docker volume inspect someone-data >/dev/null
}

@test "removal deleting data: only the labelled volumes go; no rule or unit left" {
    docker volume create --label com.koha-nexus.managed=true --label com.koha-nexus.platform=beta beta-data >/dev/null
    run lib 'kei_docker_platform_remove beta delete'
    [ "$status" -eq 0 ]
    nope docker volume inspect beta-data >/dev/null 2>&1
    docker volume inspect alpha-data >/dev/null          # another platform's: kept
    docker volume inspect someone-data >/dev/null
    [ -z "$(rules KN-INPUT)" ] && [ -z "$(rules KN-FORWARD)" ]
    [[ "$(rules INPUT)$(rules DOCKER-USER)" != *KN-* ]]
    [ ! -e /etc/systemd/system/koha-nexus-docker-isolation.service ]
    run lib 'kei_owned_list docker-network'
    [ -z "$output" ]
    docker volume rm alpha-data >/dev/null
}

@test "Docker stays while anything of anyone is in it; then it can be removed" {
    [ "$(cat "$S/docker_before")" = no ] || skip "Docker was already on this machine: never removed"
    run lib 'kei_docker_remove_engine confirm'
    [ "$status" -eq 4 ]
    systemctl is-active --quiet docker
    docker rm -f someone >/dev/null; docker network rm someone-net >/dev/null; docker volume rm someone-data >/dev/null
    run lib 'kei_docker_remove_engine confirm'
    [ "$status" -eq 0 ]
    [[ "$(dpkg-query -W -f='${Status}' docker-ce 2>/dev/null)" != *"ok installed"* ]]
    [ ! -e /etc/apt/sources.list.d/docker.list ]
    [ ! -e /var/lib/koha-nexus/docker.state ]
    run vpn_works
    [ "$status" -eq 0 ]
    koha_answers_as_before
}
