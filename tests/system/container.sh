#!/bin/bash
# A throwaway system test machine: a privileged container with systemd as
# PID 1, its own network namespace and firewall, Apache, UFW and WireGuard
# tools. Docker is NOT installed in it: tests/docker_isolation.bats
# installs it the way the panel does. Used by CI (.github/workflows/proxy.yml)
# and by hand:
#
#   tests/system/container.sh start IMAGE NAME   build and start
#   tests/system/container.sh run NAME CMD...    run a command in /src
#   tests/system/container.sh reboot NAME        restart the machine (systemd
#                                                stops and boots it again)
#   tests/system/container.sh stop NAME
#
# IMAGE: ubuntu:24.04, debian:12 or debian:13 (a registry prefix is kept).
# Behind an HTTPS proxy, set KEI_TEST_PROXY (URL reachable from the
# container) and KEI_TEST_CA (CA file): apt, curl and the inner Docker use them.
set -euo pipefail
cmd="${1:-}"; shift || true
repo="$(cd "$(dirname "$0")/../.." && pwd)"

packages="apache2 bats curl python3 iproute2 iptables ufw wireguard-tools systemd systemd-sysv dbus \
ca-certificates gnupg kmod procps iputils-ping netcat-openbsd dialog libxml2-utils unzip wget psmisc zstd"

case "$cmd" in
start)
    image="$1"; name="$2"
    tag="kei-system:$(printf '%s' "${image##*/}" | tr ':/' '--')"
    if ! docker image inspect "$tag" >/dev/null 2>&1; then
        prep='set -e
            export DEBIAN_FRONTEND=noninteractive
            if [ -n "${KEI_TEST_PROXY:-}" ]; then
                for f in /etc/apt/sources.list.d/*.sources /etc/apt/sources.list; do
                    [ -f "$f" ] && sed -i "s#http://#https://#g" "$f"
                done
                mkdir -p /usr/local/share/ca-certificates && cp /ca.crt /usr/local/share/ca-certificates/test-proxy.crt
                printf "Acquire::https::CAInfo \"/usr/local/share/ca-certificates/test-proxy.crt\";\nAcquire::https::Proxy \"%s\";\n" "$KEI_TEST_PROXY" > /etc/apt/apt.conf.d/99proxy
            fi
            apt-get update -qq
            apt-get install -y -qq --no-install-recommends '"$packages"' >/dev/null
            if [ -n "${KEI_TEST_PROXY:-}" ]; then
                update-ca-certificates >/dev/null 2>&1
                mkdir -p /etc/systemd/system/docker.service.d
                printf "[Service]\nEnvironment=HTTPS_PROXY=%s\n" "$KEI_TEST_PROXY" > /etc/systemd/system/docker.service.d/proxy.conf
                printf "HTTPS_PROXY=%s\nhttps_proxy=%s\n" "$KEI_TEST_PROXY" "$KEI_TEST_PROXY" >> /etc/environment
            fi'
        ca=(); [ -n "${KEI_TEST_CA:-}" ] && ca=(-v "$KEI_TEST_CA:/ca.crt:ro")
        docker rm -f "$name-build" >/dev/null 2>&1 || true
        docker run --name "$name-build" "${ca[@]}" -e KEI_TEST_PROXY="${KEI_TEST_PROXY:-}" "$image" bash -c "$prep"
        docker commit "$name-build" "$tag" >/dev/null
        docker rm "$name-build" >/dev/null
    fi
    docker rm -f "$name" >/dev/null 2>&1 || true
    # /var/lib/docker and /var/lib/containerd as volumes: overlay on overlay
    # does not mount.
    docker run -d --name "$name" --privileged --cgroupns=host \
        -v /sys/fs/cgroup:/sys/fs/cgroup:rw --tmpfs /run --tmpfs /run/lock \
        -v /var/lib/docker -v /var/lib/containerd -v /lib/modules:/lib/modules:ro \
        -e KEI_DESTRUCTIVE_TESTS=1 "$tag" /sbin/init >/dev/null
    for _ in $(seq 1 60); do
        st=$(docker exec "$name" systemctl is-system-running 2>/dev/null || true)
        case "$st" in running|degraded) break ;; esac
        sleep 1
    done
    docker exec "$name" mkdir -p /src
    tar -C "$repo" --exclude=.git -cf - . | docker exec -i "$name" tar -C /src -xf -
    echo "$name: systemd $st"
    ;;
run)
    name="$1"; shift
    docker exec -e KEI_DESTRUCTIVE_TESTS=1 -e KEI_REQUIRE_WIREGUARD="${KEI_REQUIRE_WIREGUARD:-}" \
        -e KEI_REQUIRE_REAL_TAINACAN="${KEI_REQUIRE_REAL_TAINACAN:-}" -e KEI_REQUIRE_REAL_EVENTS="${KEI_REQUIRE_REAL_EVENTS:-}" \
        -e KEI_REBOOT_PHASE="${KEI_REBOOT_PHASE:-}" \
        -e KEI_TAINACAN_REGISTRY="${KEI_TAINACAN_REGISTRY:-docker.io}" -w /src "$name" "$@"
    ;;
reboot)
    name="$1"
    # SIGRTMIN+3 asks systemd for an orderly halt; docker then starts the
    # same container (same disk, Docker's volumes kept) and systemd boots.
    docker restart -t 120 -s SIGRTMIN+3 "$name" >/dev/null
    st=""
    for _ in $(seq 1 120); do
        st=$(docker exec "$name" systemctl is-system-running 2>/dev/null || true)
        case "$st" in running|degraded) break ;; esac
        sleep 1
    done
    echo "$name: rebooted, systemd $st"
    ;;
stop)
    docker rm -f -v "$1" >/dev/null 2>&1 || true
    ;;
*)
    sed -n '2,18p' "$0"; exit 2 ;;
esac
