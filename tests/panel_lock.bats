#!/usr/bin/env bats
# The panel lock (section 4.5 of the installer): a lock left by a dropped
# SSH session or a dead panel must not keep "sudo config.sh" out.
# Runs the lock helpers alone; needs only flock, fuser and /proc.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    export KEI_PANEL_LOCK_FILE="$W/panel.lock"
    export BACKUP_LOCK_FILE="$W/backup.lock"
    sed -n '/^PANEL_LOCK_FILE=/,/^# end of panel lock helpers/p' "$REPO/installer" > "$W/lock.sh"
    HOLDER=""
}

teardown() {
    [ -n "$HOLDER" ] && kill "$HOLDER" 2>/dev/null
    return 0
}

# hold NAME: a process called NAME holding the panel lock, with no terminal.
hold() {
    ( exec 9>>"$KEI_PANEL_LOCK_FILE"; flock -n 9 || exit 1; exec -a "$1" sleep 300 ) </dev/null >/dev/null 2>&1 3>&- &
    HOLDER=$!
    for _ in $(seq 50); do
        [ -n "$(fuser "$KEI_PANEL_LOCK_FILE" 2>/dev/null)" ] && break
        sleep 0.1
    done
    printf '%s\n' "$HOLDER" > "$KEI_PANEL_LOCK_FILE"
}

take() { bash -c "source '$W/lock.sh'; $1; panel_lock_take; rc=\$?; echo \"rc=\$rc holder=\$PANEL_LOCK_HOLDER cleared=\$PANEL_LOCK_CLEARED\"; [ \$rc = 0 ] && cat \"\$PANEL_LOCK_FILE\" | sed 's/^/pid=/'; exit 0"; }

@test "a lock file of a panel that died is taken over" {
    printf '999999\n' > "$KEI_PANEL_LOCK_FILE"
    run take :
    [[ "$output" == *"rc=0"* ]]
    [[ "$output" == *"pid="[0-9]* ]]
    [[ "$output" != *"pid=999999"* ]]
}

@test "a lock held by another program (inherited descriptor) is replaced, the program kept" {
    hold some-daemon
    run take :
    [[ "$output" == *"rc=0"* ]]
    [[ "$output" == *"cleared=$HOLDER"* ]]
    kill -0 "$HOLDER"
}

@test "a live panel keeps the lock" {
    hold config.sh
    run take :
    [[ "$output" == *"rc=1 holder=$HOLDER"* ]]
    kill -0 "$HOLDER"
}

@test "a panel whose terminal is gone is ended and the lock taken" {
    hold config.sh
    run take 'panel_lock_pid_orphaned() { return 0; }'
    [[ "$output" == *"rc=0"* ]]
    sleep 0.3
    ! kill -0 "$HOLDER" 2>/dev/null
}

@test "a dropped session that is restoring keeps the lock" {
    hold config.sh
    ( exec 8>>"$BACKUP_LOCK_FILE"; flock -n 8; sleep 300 ) </dev/null >/dev/null 2>&1 3>&- &
    local backup=$!
    sleep 0.3
    run take 'panel_lock_pid_orphaned() { return 0; }'
    kill "$backup" 2>/dev/null
    [[ "$output" == *"rc=1"* ]]
    kill -0 "$HOLDER"
}

@test "panel_lock_release removes the lock file only for the panel that took the lock" {
    run bash -c "source '$W/lock.sh'; panel_lock_take; panel_lock_release; [ -e \"\$PANEL_LOCK_FILE\" ] && echo kept || echo gone"
    [ "$output" = "gone" ]
    printf '4242\n' > "$KEI_PANEL_LOCK_FILE"
    run bash -c "source '$W/lock.sh'; panel_lock_release; cat \"\$PANEL_LOCK_FILE\""
    [ "$output" = "4242" ]
}

# hold_panel: a panel as on Paulo's server: bash named config.sh that
# traps TERM and waits for a child (the Textual panel), lock on fd 9.
hold_panel() {
    ( exec 9>>"$KEI_PANEL_LOCK_FILE"; flock -n 9 || exit 1
      exec -a config.sh bash -c 'trap "exit 143" TERM; sleep 300; :' ) </dev/null >/dev/null 2>&1 3>&- &
    HOLDER=$!
    for _ in $(seq 50); do
        [ -n "$(pgrep -P "$HOLDER" sleep)" ] && break
        sleep 0.1
    done
    printf '%s\n' "$HOLDER" > "$KEI_PANEL_LOCK_FILE"
}

@test "a plain kill leaves such a panel running; --unlock (takeover) ends it and its child" {
    hold_panel
    local child
    child=$(pgrep -P "$HOLDER" sleep)
    [ -n "$child" ]
    kill "$HOLDER"
    sleep 0.5
    kill -0 "$HOLDER"            # bash waits for its child before running the trap
    run take :
    [[ "$output" == *"rc=1 holder=$HOLDER"* ]]
    run bash -c "source '$W/lock.sh'; panel_lock_take; PANEL_LOCK_HOLDER=$HOLDER; panel_lock_takeover; echo \"rc=\$? closed=\$PANEL_LOCK_CLOSED\"; cat \"\$PANEL_LOCK_FILE\" | sed 's/^/pid=/'"
    [[ "$output" == *"rc=0 closed=$HOLDER"* ]]
    [[ "$output" == *"pid="[0-9]* ]] && [[ "$output" != *"pid=$HOLDER"* ]]
    ! kill -0 "$HOLDER" 2>/dev/null
    ! kill -0 "$child" 2>/dev/null
}

@test "a recycled PID (alive, not this panel) in the file does not block" {
    sleep 300 </dev/null >/dev/null 2>&1 3>&- &
    HOLDER=$!
    printf '%s\n' "$HOLDER" > "$KEI_PANEL_LOCK_FILE"
    run take :
    [[ "$output" == *"rc=0"* ]]
    kill -0 "$HOLDER"
}

@test "a running backup is named instead of a dead PID" {
    printf '999999\n' > "$KEI_PANEL_LOCK_FILE"
    ( exec 9>>"$KEI_PANEL_LOCK_FILE"; flock -n 9; exec 8>>"$BACKUP_LOCK_FILE"; flock -n 8; exec -a backup_sql.sh sleep 300 ) </dev/null >/dev/null 2>&1 3>&- &
    HOLDER=$!
    sleep 0.4
    run bash -c "source '$W/lock.sh'; panel_lock_take; echo \"rc=\$? holder=\$PANEL_LOCK_HOLDER busy=\$PANEL_LOCK_BUSY\""
    [[ "$output" == *"rc=1 holder= busy=$HOLDER backup_sql.sh"* ]]
}

@test "a lock file removed by a closing panel is opened again, never two panels" {
    run bash -c "source '$W/lock.sh'
        exec 9>> \"\$PANEL_LOCK_FILE\"; rm -f \"\$PANEL_LOCK_FILE\"; exec 9>&-
        exec 7>> \"\$PANEL_LOCK_FILE\"; rm -f \"\$PANEL_LOCK_FILE\"   # the old file, then gone
        panel_lock_open; echo rc=\$?
        [ \"\$(stat -L -c %i /proc/\$\$/fd/9)\" = \"\$(stat -c %i \"\$PANEL_LOCK_FILE\")\" ] && echo same"
    [[ "$output" == *"rc=0"* ]] && [[ "$output" == *"same"* ]]
}

@test "a closed terminal (dropped SSH session) is seen as gone" {
    command -v script >/dev/null || skip "script (util-linux) not installed"
    ( script -qfc "bash -c 'trap \"\" HUP; exec -a kei-orphan-check sleep 300'" /dev/null ) </dev/null >/dev/null 2>&1 3>&- &
    local pid="" s
    for _ in $(seq 50); do pid=$(pgrep -f '^kei-orphan-check') && break; sleep 0.1; done
    HOLDER="$pid"
    run bash -c "source '$W/lock.sh'; panel_lock_pid_orphaned $pid && echo orphan || echo attached"
    [ "$output" = "attached" ]
    s=$(pgrep -x script | head -n1)
    kill -9 "$s"
    sleep 0.5
    run bash -c "source '$W/lock.sh'; panel_lock_pid_orphaned $pid && echo orphan || echo attached"
    [ "$output" = "orphan" ]
}
