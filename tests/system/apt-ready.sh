#!/bin/bash
# apt-ready.sh: "apt-get update" for the throwaway CI containers that
# survives a package mirror that cannot be reached for a while.
#
# apt-get update only warns ("W: Failed to fetch ... Could not resolve")
# when a mirror is unreachable, and the failure surfaces later as
# "Unable to locate package". Here a warning is a failure: it waits and
# tries again, and on Ubuntu it moves to another official mirror (the
# Azure one GitHub runners use, then kernel.org) before giving up.
# It never installs anything; the caller does. The same script serves the
# containers and the GitHub runner itself (run it with sudo there).
set -u

APT_READY_ATTEMPTS="${APT_READY_ATTEMPTS:-5}"
APT_READY_SLEEP="${APT_READY_SLEEP:-15}"
ROOT="${APT_READY_ROOT:-}"      # tests only: a fake /etc
log="$(mktemp)"

update() {
    apt-get update -qq -o Acquire::Retries=3 >"$log" 2>&1
    local rc=$?
    cat "$log" >&2
    [ "$rc" -eq 0 ] && ! grep -qE '^(W|E): (Failed to fetch|Some index files failed)' "$log"
}

ubuntu_mirror() {
    # $1: host that replaces archive.ubuntu.com and security.ubuntu.com
    grep -qi '^ID=ubuntu' "$ROOT/etc/os-release" 2>/dev/null || return 0
    local f
    # apt-mirrors.txt: the mirror list GitHub's own Ubuntu runners read.
    for f in "$ROOT"/etc/apt/sources.list.d/*.sources "$ROOT"/etc/apt/sources.list "$ROOT"/etc/apt/apt-mirrors.txt; do
        [ -f "$f" ] || continue
        sed -i -E "s#(https?://)([a-z.]*archive\.ubuntu\.com|security\.ubuntu\.com|mirrors\.edge\.kernel\.org)/ubuntu#\1$1/ubuntu#g" "$f"
    done
    echo "apt-ready: using the Ubuntu mirror $1" >&2
}

for attempt in $(seq 1 "$APT_READY_ATTEMPTS"); do
    if update; then
        rm -f "$log"
        exit 0
    fi
    case "$attempt" in
        2) ubuntu_mirror azure.archive.ubuntu.com ;;
        4) ubuntu_mirror mirrors.edge.kernel.org ;;
    esac
    [ "$attempt" -lt "$APT_READY_ATTEMPTS" ] && sleep $((attempt * APT_READY_SLEEP))
done
rm -f "$log"
echo "apt-ready: the package indexes could not be downloaded after $APT_READY_ATTEMPTS attempts" >&2
exit 1
