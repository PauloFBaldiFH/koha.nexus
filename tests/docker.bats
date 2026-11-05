#!/usr/bin/env bats
# Docker, optional (installer: kei_docker_*). These tests need nothing
# installed: dpkg-query, docker and the system files are stand-ins. The
# tests with a real Docker, a real firewall and the VPN are in
# tests/docker_isolation.bats (destructive, throwaway machine only).

# A PATH without docker and snap: the machine running the tests may have
# them; the stand-ins below decide what each test sees.
setup_file() {
    local f
    mkdir -p "$BATS_FILE_TMPDIR/sys"
    for f in /usr/local/bin/* /usr/bin/* /bin/* /usr/sbin/* /sbin/*; do
        case "${f##*/}" in docker|dockerd|snap|containerd*) continue ;; esac
        [ -e "$BATS_FILE_TMPDIR/sys/${f##*/}" ] || ln -s "$f" "$BATS_FILE_TMPDIR/sys/${f##*/}"
    done
}

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$W/owned"
    export KEI_OS_RELEASE="$W/os-release"
    export KEI_DOCKER_APT_SOURCE="$W/docker.list"
    export KEI_DOCKER_KEYRING="$W/docker.asc"
    export KEI_DOCKER_DAEMON_JSON="$W/daemon.json"
    printf 'ID=debian\nVERSION_CODENAME=bookworm\n' > "$KEI_OS_RELEASE"
    mkdir -p "$W/bin"
}

# lib CODE: runs CODE with the installer loaded. $W/pkgs lists the
# packages the dpkg-query stand-in reports as installed.
lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
dpkg-query() { grep -qx \"\${@: -1}\" '$W/pkgs' 2>/dev/null && printf 'install ok installed'; }
dpkg() { echo amd64; }
PATH='$W/bin':'$BATS_FILE_TMPDIR/sys'
$1" 3>&-
}

# A docker stand-in: "docker compose version" works only with $W/compose.
fake_docker() {
    cat > "$W/bin/docker" <<EOF
#!/bin/bash
case "\$1 \$2" in
    "compose version") [ -f "$W/compose" ] && echo 2.30.0 || exit 1 ;;
    "version "*) echo 27.3.1 ;;
    "info "*|"info") exit 0 ;;
    "ps -aq") cat "$W/containers" 2>/dev/null ;;
    "volume ls") cat "$W/volumes" 2>/dev/null ;;
    "network ls") printf 'bridge\nhost\nnone\n'; cat "$W/networks" 2>/dev/null ;;
    *) exit 0 ;;
esac
EOF
    chmod +x "$W/bin/docker"
}

@test "subnets: overlap is computed on the prefix" {
    run lib '_kei_cidr_overlap 10.213.1.0/24 10.213.1.77 && echo a
_kei_cidr_overlap 10.213.1.0/24 10.0.0.0/8 && echo b
_kei_cidr_overlap 10.213.1.0/24 10.213.2.0/24 || echo c
_kei_cidr_overlap 192.168.0.0/16 192.168.213.0/24 && echo d
_kei_cidr_overlap 172.30.4.0/24 172.17.0.0/16 || echo e'
    [ "$output" = "$(printf 'a\nb\nc\nd\ne')" ]
}

@test "subnets: the first /24 that no route, address, network or the VPN uses" {
    run lib 'kei_docker_used_nets() { printf "10.213.1.0/24\n10.213.2.5\n10.66.0.0/24\n"; }; kei_docker_pick_subnet'
    [ "$output" = "10.213.3.0/24" ]
    # A route covering all of 10.0.0.0/8 (a company VPN): the next pool.
    run lib 'kei_docker_used_nets() { printf "10.0.0.0/8\n172.16.0.0/12\n"; }; kei_docker_pick_subnet'
    [ "$output" = "192.168.1.0/24" ]
    run lib 'kei_docker_used_nets() { printf "0.0.0.0/0\n"; }; kei_docker_pick_subnet'
    [ "$status" -ne 0 ]
}

@test "daemon.json is only read: its top-level keys" {
    printf '{\n  "data-root": "/srv/docker",\n  "default-address-pools": [{"base": "10.10.0.0/16", "size": 24}],\n  "log-opts": {"max-size": "10m"}\n}\n' > "$KEI_DOCKER_DAEMON_JSON"
    cp "$KEI_DOCKER_DAEMON_JSON" "$W/before"
    run lib '_kei_docker_daemon_keys'
    [ "$output" = "data-root,default-address-pools,log-opts" ]
    cmp "$KEI_DOCKER_DAEMON_JSON" "$W/before"
}

@test "plan: without Docker, the official repository; nothing written" {
    run lib 'kei_docker_plan'
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "$(printf 'plan\tinstall')" ]
    [[ "$output" == *"https://download.docker.com/linux/debian bookworm stable (amd64)"* ]]
    [[ "$output" == *"docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"* ]]
    [[ "$output" == *"daemon.json"* ]]
    [ ! -e "$KEI_DOCKER_APT_SOURCE" ] && [ ! -e "$KEI_DOCKER_KEYRING" ] && [ ! -e "$KEI_OWNED_DIR/docker.state" ]
}

@test "plan: an existing key or source is kept and said so" {
    echo key > "$KEI_DOCKER_KEYRING"
    run lib 'kei_docker_plan'
    [[ "$output" == *"docker.asc (already there, kept)"* ]]
    [[ "$output" == *"docker.list (new)"* ]]
}

@test "plan: a Docker with Compose v2 is used as it is" {
    fake_docker; touch "$W/compose"; echo docker.io > "$W/pkgs"
    run lib 'kei_docker_plan'
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "$(printf 'plan\tuse')" ]
    [[ "$output" == *"docker.io"* ]]
    # And installing does nothing.
    run lib 'apt-get() { echo APT "$@"; }; curl() { echo CURL; }; kei_docker_install confirm'
    [ "$status" -eq 0 ]
    [[ "$output" != *APT* ]] && [[ "$output" != *CURL* ]]
    [ ! -e "$KEI_OWNED_DIR/docker.state" ]
}

@test "plan: never installs on top of docker.io without Compose, nor next to conflicting packages" {
    fake_docker; echo docker.io > "$W/pkgs"
    run lib 'kei_docker_plan'
    [ "$status" -eq 3 ]
    [ "${lines[0]}" = "$(printf 'plan\trefuse')" ]
    rm -f "$W/bin/docker"; printf 'containerd\nrunc\n' > "$W/pkgs"
    run lib 'kei_docker_plan'
    [ "$status" -eq 3 ]
    [[ "$output" == *"containerd runc"* ]]
    run lib 'apt-get() { echo APT; }; kei_docker_install confirm'
    [ "$status" -eq 3 ]
    [[ "$output" != *APT* ]]
}

@test "plan: only Debian and Ubuntu" {
    printf 'ID=fedora\nVERSION_CODENAME=\n' > "$KEI_OS_RELEASE"
    run lib 'kei_docker_plan'
    [ "$status" -eq 3 ]
    [[ "$output" == *fedora* ]]
}

@test "install: nothing happens without the word confirm" {
    run lib 'apt-get() { echo APT; }; curl() { echo CURL; }; kei_docker_install; echo rc=$?; kei_docker_install yes; echo rc=$?'
    [[ "$output" != *APT* ]] && [[ "$output" != *CURL* ]]
    [[ "$output" == *"rc=2"*"rc=2"* ]]
    [ ! -e "$KEI_OWNED_DIR/docker.state" ]
}

@test "install: the state says Koha.Nexus installed it, and what it created" {
    run lib 'curl() { local o; while [ $# -gt 0 ]; do [ "$1" = -o ] && o=$2; shift; done; echo KEY > "$o"; }
apt-get() { case "$1" in install) printf "#!/bin/bash\nexit 0\n" > '"$W"'/bin/docker; chmod +x '"$W"'/bin/docker ;; esac; }
iptables() { echo "-P FORWARD ACCEPT"; }
kei_docker_install confirm'
    [ "$status" -eq 0 ]
    grep -qx 'installed_by=koha-nexus' "$KEI_OWNED_DIR/docker.state"
    grep -qx 'status=installed' "$KEI_OWNED_DIR/docker.state"
    grep -qx 'keyring_created=yes' "$KEI_OWNED_DIR/docker.state"
    grep -qx 'source_created=yes' "$KEI_OWNED_DIR/docker.state"
    grep -qx 'forward_policy_before=ACCEPT' "$KEI_OWNED_DIR/docker.state"
    [ "$(cat "$KEI_DOCKER_APT_SOURCE")" = "deb [arch=amd64 signed-by=$KEI_DOCKER_KEYRING] https://download.docker.com/linux/debian bookworm stable" ]
}

@test "install: a failed apt run is recorded, so it can be undone" {
    run lib 'curl() { local o; while [ $# -gt 0 ]; do [ "$1" = -o ] && o=$2; shift; done; echo KEY > "$o"; }
apt-get() { [ "$1" = install ] && return 100; return 0; }
iptables() { :; }
kei_docker_install confirm'
    [ "$status" -eq 1 ]
    grep -qx 'status=failed' "$KEI_OWNED_DIR/docker.state"
    grep -qx 'installed_by=koha-nexus' "$KEI_OWNED_DIR/docker.state"
}

@test "remove: a Docker found on the server is never removed" {
    fake_docker; echo docker-ce > "$W/pkgs"
    run lib 'apt-get() { echo APT "$@"; }; kei_docker_remove_engine confirm'
    [ "$status" -eq 4 ]
    [[ "$output" != *APT* ]]
}

@test "remove: only while no container, volume, network or platform network is left" {
    fake_docker; echo docker-ce > "$W/pkgs"
    mkdir -p "$KEI_OWNED_DIR"; printf 'installed_by=koha-nexus\nsource_created=yes\n' > "$KEI_OWNED_DIR/docker.state"
    echo src > "$KEI_DOCKER_APT_SOURCE"; echo key > "$KEI_DOCKER_KEYRING"
    echo c1 > "$W/containers"
    run lib 'apt-get() { echo APT; }; kei_docker_remove_engine confirm'
    [ "$status" -eq 4 ] && [[ "$output" != *APT* ]]
    rm "$W/containers"; echo v1 > "$W/volumes"
    run lib 'apt-get() { echo APT; }; kei_docker_remove_engine confirm'
    [ "$status" -eq 4 ] && [[ "$output" != *APT* ]]
    rm "$W/volumes"; echo someones-net > "$W/networks"
    run lib 'apt-get() { echo APT; }; kei_docker_remove_engine confirm'
    [ "$status" -eq 4 ] && [[ "$output" != *APT* ]]
    rm "$W/networks"
    run lib 'kei_owned_add docker-network kn-tainacan tainacan no "" 10.213.1.0/24
apt-get() { echo APT; }; kei_docker_remove_engine confirm'
    [ "$status" -eq 4 ] && [[ "$output" != *APT* ]]
    run lib 'kei_owned_del docker-network kn-tainacan tainacan
apt-get() { echo APT "$@" >> '"$W"'/apt; }; kei_docker_remove_engine confirm'
    [ "$status" -eq 0 ]
    [[ "$(cat "$W/apt")" == *"APT purge -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"* ]]
    # It created the source, not the key: only the source goes.
    [ ! -e "$KEI_DOCKER_APT_SOURCE" ] && [ -e "$KEI_DOCKER_KEYRING" ]
    [ ! -e "$KEI_OWNED_DIR/docker.state" ]
}

@test "networks: Koha and names too long for a bridge are refused" {
    run lib 'kei_docker_valid_platform tainacan && echo ok1
kei_docker_valid_platform koha || echo no1
kei_docker_valid_platform abcdefghijklm || echo no2
kei_docker_valid_platform "a b" || echo no3'
    [ "$output" = "$(printf 'ok1\nno1\nno2\nno3')" ]
}

@test "--status-json gains docker and keeps the other fields" {
    run lib 'systemctl() { echo inactive; }; kei_http_code() { echo 000; }; plack_running() { false; }
kei_web_listeners() { :; }; KEI_APACHE_DIR=/nonexistent; iptables() { return 1; }
kei_status_json'
    [ "$status" -eq 0 ]
    run python3 -c 'import json,sys; d=json.loads(sys.argv[1])
for k in ("schema","state","platforms","proxy","docker"): assert k in d, k
print(d["schema"], d["docker"]["installed"], d["docker"]["running"], d["docker"]["others"], d["docker"]["platform_networks"])' "$output"
    [ "$output" = "1 False False {'containers': 0, 'networks': 0, 'volumes': 0} 0" ]
}

@test "release: a platform network is part of kei_platform_release" {
    run lib 'kei_docker_network_remove() { echo "network $1"; return 4; }
kei_owned_add docker-network kn-tainacan tainacan no "" 10.213.1.0/24
kei_platform_release tainacan; echo rc=$?'
    [[ "$output" == *"network tainacan"* ]]
    [[ "$output" == *"kept: docker-network kn-tainacan"* ]]
    [[ "$output" == *"rc=1"* ]]
}
