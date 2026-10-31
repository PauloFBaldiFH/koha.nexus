#!/usr/bin/env bats
# The backup/restore lock (section 5 of the installer). Paulo, 2026-10-31:
# after changing the backup compression, applying the OPAC look said
# "Another backup or restore is already running. Nothing was changed." with
# nothing of his running. A panel task cancelled during its safety backup
# had left its dump and compressor running on their own, holding the lock
# they inherited; a program started under the lock can keep it for good.
# Runs the lock helpers alone; needs only flock, fuser and /proc.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    export KEI_BACKUP_LOCK_FILE="$W/backup.lock"
    export DIR_SQL="$W/sql"
    mkdir -p "$DIR_SQL" "$W/bin"
    {
        printf 'log() { printf "%%s\\n" "$*" >> "%s/log"; }\n' "$W"
        printf 't() { printf "%%s" "$1"; }\n'
        printf 'display_explanation() { printf "waiting: %%s\\n" "$1"; }\n'
        sed -n '/^BACKUP_LOCK_FILE=/,/^# end of backup lock helpers/p' "$REPO/installer"
    } > "$W/lock.sh"
    PIDS=()
}

teardown() {
    local p
    for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done
    return 0
}

# wait_held: until the lock file is open somewhere.
wait_held() {
    for _ in $(seq 50); do
        [ -n "$(fuser "$KEI_BACKUP_LOCK_FILE" 2>/dev/null)" ] && return 0
        sleep 0.1
    done
    return 1
}

# hold PROGRAM ARGS...: PROGRAM holding the lock (as an inherited descriptor).
hold() {
    ( exec 8>>"$KEI_BACKUP_LOCK_FILE"; flock -n 8 || exit 1; exec "$@" ) </dev/null >/dev/null 2>&1 3>&- &
    PIDS+=($!)
    wait_held
}

take() {
    bash -c "source '$W/lock.sh'; $1
        backup_lock_acquire; rc=\$?
        echo \"rc=\$rc\"
        echo \"busy=\$BACKUP_LOCK_BUSY\"
        echo \"cleared=\$BACKUP_LOCK_CLEARED\"
        [ \$rc = 0 ] && echo \"file=\$(cat \"\$BACKUP_LOCK_FILE\") me=\$\$\"
        echo \"text=\$(backup_lock_busy_text)\"
        exit 0"
}

@test "a free lock is taken and carries the PID of the installer that took it" {
    run take :
    [[ "$output" == *"rc=0"* ]]
    [[ "$output" =~ file=([0-9]+)\ me=([0-9]+) ]]
    [ "${BASH_REMATCH[1]}" = "${BASH_REMATCH[2]}" ]
}

@test "a lock kept by a program that merely inherited it is replaced, the program kept" {
    hold sleep 300
    run take :
    [[ "$output" == *"rc=0"* ]]
    [[ "$output" == *"cleared=${PIDS[0]} sleep 300"* ]]
    kill -0 "${PIDS[0]}"
    grep -q "cleared a stale lock" "$W/log"
}

@test "Paulo 2026-10-31: a safety backup left by a cancelled task is stopped and its unfinished file removed" {
    ln -s "$(command -v sleep)" "$W/bin/xz"
    ( exec 8>>"$KEI_BACKUP_LOCK_FILE"; flock -n 8 || exit 1; exec "$W/bin/xz" 300 ) \
        </dev/null >"$DIR_SQL/PRE-OPAC-THEME_2026-10-31_20h30.sql.xz" 2>&1 3>&- &
    PIDS+=($!)
    wait_held
    run take :
    [[ "$output" == *"rc=0"* ]]
    sleep 0.2
    ! kill -0 "${PIDS[0]}" 2>/dev/null || [ "$(awk '/^State:/{print $2}' /proc/${PIDS[0]}/status)" = Z ]
    [ ! -e "$DIR_SQL/PRE-OPAC-THEME_2026-10-31_20h30.sql.xz" ]
}

@test "a nightly backup that is running is waited for, then the lock is taken" {
    cat > "$W/backup_sql.sh" <<EOF
exec 9>"$KEI_BACKUP_LOCK_FILE"
flock -n 9 || exit 1
sleep 1.5
EOF
    bash "$W/backup_sql.sh" </dev/null >/dev/null 2>&1 3>&- &
    PIDS+=($!)
    wait_held
    run take 'BACKUP_LOCK_WAIT=20'
    [[ "$output" == *"waiting: A backup is running now"* ]]
    [[ "$output" == *"rc=0"* ]]
}

@test "a nightly backup longer than the wait refuses, naming it" {
    cat > "$W/backup_sql.sh" <<EOF
exec 9>"$KEI_BACKUP_LOCK_FILE"
flock -n 9 || exit 1
sleep 300
EOF
    bash "$W/backup_sql.sh" </dev/null >/dev/null 2>&1 3>&- &
    PIDS+=($!)
    wait_held
    run take 'BACKUP_LOCK_WAIT=1'
    [[ "$output" == *"rc=1"* ]]
    [[ "$output" == *"busy=${PIDS[0]} bash $W/backup_sql.sh"* ]]
    [[ "$output" == *"Holding it now:"$'\n'"${PIDS[0]} bash $W/backup_sql.sh"* ]]
    kill -0 "${PIDS[0]}"
}

@test "a panel task holding the lock is a real overlap: refused at once, left alone" {
    ( exec 8>>"$KEI_BACKUP_LOCK_FILE"; flock -n 8 || exit 1; exec bash -c 'sleep 300; :' config.sh --task opac-theme-apply ) \
        </dev/null >/dev/null 2>&1 3>&- &
    PIDS+=($!)
    wait_held
    run take 'BACKUP_LOCK_WAIT=30'
    [[ "$output" == *"rc=1"* ]]
    [[ "$output" == *"busy=${PIDS[0]} "* ]]
    [[ "$output" != *"waiting:"* ]]
    kill -0 "${PIDS[0]}"
}

@test "the installer that wrote its PID in the lock file keeps it" {
    bash -c "source '$W/lock.sh'; backup_lock_acquire && exec sleep 300" </dev/null >/dev/null 2>&1 3>&- &
    PIDS+=($!)
    wait_held
    sleep 0.2
    [ "$(cat "$KEI_BACKUP_LOCK_FILE")" = "${PIDS[0]}" ]
    run take :
    [[ "$output" == *"rc=1"* ]]
    kill -0 "${PIDS[0]}"
}

@test "a database import (mysql) keeps the lock" {
    ln -s "$(command -v sleep)" "$W/bin/mysql"
    hold "$W/bin/mysql" 300
    run take :
    [[ "$output" == *"rc=1"* ]]
    kill -0 "${PIDS[0]}"
}

@test "the lock taken after a clear is exclusive again" {
    hold sleep 300
    bash -c "source '$W/lock.sh'; backup_lock_acquire && exec sleep 300" </dev/null >/dev/null 2>&1 3>&- &
    PIDS+=($!)
    sleep 0.5
    run take :
    [[ "$output" == *"rc=1"* ]]
}
