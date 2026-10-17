#!/usr/bin/env bats
# windows/koha-graceful-shutdown.sh, the clean stop inside Debian that the
# Windows shutdown watcher runs before WSL is stopped. Every command it
# calls is a stand-in on PATH that writes one line to $LOG, so the order of
# the stop is checked without Koha, MariaDB or systemd.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    SCRIPT="$REPO/windows/koha-graceful-shutdown.sh"
    W="$BATS_TEST_TMPDIR"
    BIN="$W/bin"
    mkdir -p "$BIN"
    export LOG="$W/calls.log"
    : > "$LOG"
    # PID 1 is systemd unless a test says otherwise.
    export INIT=systemd
    # Units this Debian has (systemctl cat finds them).
    export UNITS="apache2 koha-common rabbitmq-server memcached mariadb"
    export STOP_FAILS=""
    stub ps 'echo "$INIT"'
    stub systemctl '
case "$1" in
  cat) for u in $UNITS; do [ "$2" = "$u.service" ] && exit 0; done; exit 1 ;;
  stop) shift; echo "systemctl stop $*" >> "$LOG"
        for f in $STOP_FAILS; do case " $* " in *" $f.service "*) exit 1 ;; esac; done; exit 0 ;;
esac'
    stub koha-list 'echo library'
    for t in koha-plack koha-worker koha-indexer koha-es-indexer koha-zebra; do
        stub "$t" "echo \"$t \$*\" >> \"\$LOG\""
    done
    stub sync 'echo sync >> "$LOG"'
    stub mariadb-admin 'echo "mariadb-admin $*" >> "$LOG"'
    export KOHA_STOP_GUARD="$BIN/koha-stop-guard"
    stub koha-stop-guard 'echo "guard $*" >> "$LOG"'
    export PATH="$BIN:/usr/bin:/bin"
}

# stub NAME BODY: a stand-in command NAME on PATH.
stub() {
    printf '#!/bin/sh\n%s\n' "$2" > "$BIN/$1"
    chmod +x "$BIN/$1"
}

# line N of the call log.
nth() { sed -n "$1p" "$LOG"; }

@test "services stop in order: web, Koha's daemons, queue and cache, MariaDB, then sync and the guard" {
    run sh "$SCRIPT"
    [ "$status" -eq 0 ]
    [ "$(nth 1)" = "systemctl stop apache2.service koha-common.service" ]
    [ "$(nth 2)" = "koha-plack --stop library" ]
    [ "$(nth 3)" = "koha-worker --stop library" ]
    [ "$(nth 4)" = "koha-indexer --stop library" ]
    [ "$(nth 5)" = "koha-es-indexer --stop library" ]
    [ "$(nth 6)" = "koha-zebra --stop library" ]
    [ "$(nth 7)" = "koha-worker --stop --queue long_tasks library" ]
    [ "$(nth 8)" = "systemctl stop rabbitmq-server.service memcached.service" ]
    [ "$(nth 9)" = "systemctl stop mariadb.service" ]
    [ "$(nth 10)" = "sync" ]
    [ "$(nth 11)" = "guard stop" ]
    [ "$(wc -l < "$LOG")" -eq 11 ]
}

@test "the steps are reported for the progress on Windows" {
    run sh "$SCRIPT"
    [ "$(printf '%s\n' "$output" | grep '^@step' | tr '\n' ' ')" = "@step 1 @step 2 @step 3 @step 4 " ]
}

@test "units this Debian does not have are skipped (no Elasticsearch)" {
    run sh "$SCRIPT"
    ! grep -q elasticsearch "$LOG"
}

@test "a unit that does not stop: the rest still stops, exit 1 says so" {
    export STOP_FAILS="mariadb"
    run sh "$SCRIPT"
    [ "$status" -eq 1 ]
    [[ "$output" == *"did not stop: mariadb.service"* ]]
    grep -qx sync "$LOG"
    grep -qx "guard stop" "$LOG"
}

@test "the guard does not record the stop: exit 1" {
    stub koha-stop-guard 'exit 1'
    run sh "$SCRIPT"
    [ "$status" -eq 1 ]
    [[ "$output" == *"not marked clean"* ]]
}

@test "no guard yet: still syncs, exit 0" {
    export KOHA_STOP_GUARD="$W/missing"
    run sh "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"no clean-stop guard"* ]]
    grep -qx sync "$LOG"
}

@test "no Koha instance: only the units stop" {
    stub koha-list 'exit 0'
    run sh "$SCRIPT"
    [ "$status" -eq 0 ]
    ! grep -q -- '--stop' "$LOG"
    grep -qx "systemctl stop mariadb.service" "$LOG"
}

@test "without systemd: MariaDB shuts itself down, then sync" {
    export INIT=init
    run sh "$SCRIPT"
    [ "$status" -eq 0 ]
    [ "$(nth 1)" = "mariadb-admin ping" ]
    [ "$(nth 2)" = "mariadb-admin shutdown" ]
    [ "$(nth 3)" = "sync" ]
    ! grep -q systemctl "$LOG"
}

@test "without systemd and no MariaDB running: only sync" {
    export INIT=init
    stub mariadb-admin 'echo "mariadb-admin $*" >> "$LOG"; [ "$1" != ping ]'
    run sh "$SCRIPT"
    [ "$status" -eq 0 ]
    ! grep -q "mariadb-admin shutdown" "$LOG"
    grep -qx sync "$LOG"
}

@test "finishes well inside the watcher's 20 s (here under 5 s)" {
    start=$(date +%s)
    run timeout 5 sh "$SCRIPT"
    [ "$status" -eq 0 ]
    [ $(( $(date +%s) - start )) -lt 5 ]
}

@test "runs the same when fed through stdin, as Stop and Restart do" {
    run sh -s < "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -qx "guard stop" "$LOG"
}

@test "POSIX sh only (dash parses it)" {
    if ! command -v dash >/dev/null; then skip "no dash"; fi
    dash -n "$SCRIPT"
}
