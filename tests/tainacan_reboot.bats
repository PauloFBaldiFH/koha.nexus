#!/usr/bin/env bats
# A real reboot of a machine with Tainacan (installer: kei_tainacan_*,
# kei_docker_isolation_*). Two phases, with the machine restarted between
# them (tests/system/container.sh reboot: systemd stops everything and
# boots again; Docker's data survives, /run does not):
#
#   KEI_REBOOT_PHASE=before  installs Tainacan by name, adds a collection
#                            and an item, writes down what it saw
#   KEI_REBOOT_PHASE=after   the isolation unit came up before Docker, its
#                            chains are back, the containers came back by
#                            themselves, the data is the same, Apache serves
#                            Tainacan by its name again
#
# DESTRUCTIVE: runs only with KEI_DESTRUCTIVE_TESTS=1, as root, under
# systemd, in a throwaway machine (CI: .github/workflows/proxy.yml).

NAME=tainacan.reboot.test
MARK=/root/kn-reboot

setup() {
    [ "${KEI_DESTRUCTIVE_TESTS:-}" = 1 ] || skip "destructive: set KEI_DESTRUCTIVE_TESTS=1 in a throwaway machine"
    [ "$(id -u)" = 0 ] || skip "needs root"
    [ -d /run/systemd/system ] || skip "needs systemd"
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    TN=/var/lib/koha-nexus/platforms/tainacan
    export KEI_TAINACAN_REGISTRY="${KEI_TAINACAN_REGISTRY:-docker.io}"
    if [ -f "$MARK/stub/tainacan.zip" ]; then
        export KEI_TAINACAN_PLUGIN_URL="file://$MARK/stub/tainacan.zip"
        export KEI_TAINACAN_CHECKSUMS_URL="file://$MARK/stub/checksums.json"
    fi
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
$1" 3>&-
}

counts() { lib '_kei_tn_counts' | awk '{ print $1, $2, $3 }'; }
api() { curl -s --max-time 20 --resolve "$NAME:80:127.0.0.1" "http://$NAME/?rest_route=/tainacan/v2/collections"; }
json_len() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d, list) else -1)'; }
mono() { systemctl show -p "$2" --value "$1"; }

@test "before the reboot: Tainacan by name, with data" {
    [ "${KEI_REBOOT_PHASE:-}" = before ] || skip "phase before"
    mkdir -p "$MARK"
    if ! curl -sfI --max-time 15 "https://downloads.wordpress.org/plugin-checksums/tainacan/1.4.1.json" >/dev/null 2>&1; then
        [ "${KEI_REQUIRE_REAL_TAINACAN:-}" = 1 ] && { echo "wordpress.org unreachable and the real plugin is required" >&2; return 1; }
        "$REPO/tests/system/tainacan-stub/build.sh" "$MARK/stub"
        export KEI_TAINACAN_PLUGIN_URL="file://$MARK/stub/tainacan.zip"
        export KEI_TAINACAN_CHECKSUMS_URL="file://$MARK/stub/checksums.json"
        echo "Tainacan plugin: test double (wordpress.org unreachable)" >&3
    fi
    command -v docker >/dev/null 2>&1 || lib 'kei_docker_install confirm'
    systemctl is-enabled --quiet docker
    run lib "kei_tainacan_install confirm http://$NAME"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    printf '%s\n' '<?php
$r = new WP_REST_Request("POST", "/tainacan/v2/collections");
$r->set_header("content-type", "application/json");
$r->set_body(json_encode(["name" => "Antes de reiniciar", "status" => "publish"]));
$c = rest_do_request($r)->get_data();
$r = new WP_REST_Request("POST", "/tainacan/v2/collection/" . $c["id"] . "/items");
$r->set_header("content-type", "application/json");
$r->set_body(json_encode(["title" => "Item", "status" => "publish"]));
rest_do_request($r);' > "$TN/work/r.php"
    chmod 644 "$TN/work/r.php"
    lib '_kei_tn_wp eval-file /work/r.php --user=knadmin'
    [ "$(api | json_len)" = 1 ]
    counts > "$MARK/counts"
    [ "$(cut -d' ' -f1,2 "$MARK/counts")" = "1 1" ]
    systemctl is-enabled --quiet koha-nexus-docker-isolation
    iptables -S KN-INPUT | grep -q kn-tainacan
}

@test "after the reboot: isolation first, then Docker, Tainacan and the same data" {
    [ "${KEI_REBOOT_PHASE:-}" = after ] || skip "phase after"
    [ -f "$MARK/counts" ]
    # The isolation unit was active before Docker began to start.
    systemctl is-active --quiet koha-nexus-docker-isolation
    systemctl is-active --quiet docker
    iso=$(mono koha-nexus-docker-isolation ActiveEnterTimestampMonotonic)
    dock=$(mono docker InactiveExitTimestampMonotonic)
    echo "isolation active at $iso us, Docker starting at $dock us" >&3
    [ "$iso" -gt 0 ] && [ "$dock" -gt 0 ] && [ "$iso" -le "$dock" ]
    iptables -S KN-INPUT | grep -q kn-tainacan
    # The containers came back by themselves (restart policy), healthy.
    for _ in $(seq 1 90); do lib 'kei_tainacan_health' >/dev/null 2>&1 && break; sleep 2; done
    run lib 'kei_tainacan_health'
    [ "$status" -eq 0 ]
    [ "$(counts)" = "$(cat "$MARK/counts")" ]
    # Apache serves it by its name again.
    [ "$(api | json_len)" = 1 ]
    run lib 'kei_docker_audit tainacan'
    [ "$status" -eq 0 ]
}
