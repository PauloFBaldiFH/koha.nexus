#!/usr/bin/env bats
# The platform backup engine (installer: kei_backup_*, _kei_bk_*), with no
# Docker: a stand-in platform "demo" (a text file as the database, a
# directory as the files) exercises the journal, a crash during and after
# the capture and the resume, the discard, the encrypted configuration,
# the recovery kit on a new server, restic (local and through rclone),
# the cloud copy, retention, the choice of an older backup, the schedule
# and the refusal of malicious packages. Tainacan itself runs in
# tests/backup_engine_system.bats. gpg is needed; restic and rclone tests
# are skipped without them (CI installs both).

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_BK_ROOT="$T/backups" KEI_BK_CRON="$T/cron.d/koha-nexus-platform-backups" KEI_BK_NEED_CRON=0
    export RCLONE_CONFIG="$T/rclone.conf" KEI_PANEL_COMMAND=/usr/local/bin/config.sh
    export DEMO="$T/demo"
    mkdir -p "$DEMO/data/sub" "$T/cron.d"
    printf 'CREATE TABLE t (x int);\nINSERT INTO t VALUES (1);\n' > "$DEMO/db.sql"
    printf 'one\n' > "$DEMO/data/a.txt"; printf 'two\n' > "$DEMO/data/sub/b.txt"
    ln -s a.txt "$DEMO/data/link"
    printf 'KN_SECRET=s3cr3t\n' > "$DEMO/.env"; chmod 600 "$DEMO/.env"
    echo running > "$DEMO/state"
}

PHRASE="TEST-PHRA-SE12-3456-7890-ABCD"

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
KEI_BK_PLATFORMS=demo
_kei_bk_demo_preflight() { [ -d \"\$DEMO/data\" ]; }
_kei_bk_demo_size() { echo 1; }
_kei_bk_demo_stop() { echo stopped > \"\$DEMO/state\"; }
_kei_bk_demo_start() { echo running > \"\$DEMO/state\"; }
_kei_bk_demo_meta() { printf 'count_files\t%s\n' \"\$(find \"\$DEMO/data\" -type f | wc -l)\"; }
_kei_bk_demo_dump() { cat \"\$DEMO/db.sql\"; }
_kei_bk_demo_tar() { tar -C \"\$DEMO/data\" -cf - .; }
_kei_bk_demo_path() { printf '%s' \"\$DEMO/data\"; }
_kei_bk_demo_after() { printf 'demo_after\t1\n'; }
_kei_bk_demo_secrets() { printf '%s\n' \"\$DEMO/.env\"; }
kei_demo_restore_test() { kei_backup_check \"\$1\" demo >/dev/null && echo restored; }
$1" 3>&-
}

steps() { sed -n 's/.*"step":"\([a-z-]*\)".*/\1/p' "$1/journal.jsonl" | tr '\n' ' '; }
nope() { ! "$@"; }

@test "a package without a key: journal in order, plain configuration (600), manifest last, checksums" {
    run lib 'kei_backup_run demo'
    [ "$status" -eq 0 ]
    B="${lines[-1]}"
    [ "$(steps "$B")" = "start capture writes-stopped db files writes-resumed capture-done secrets manifest done " ]
    [ "$(cat "$DEMO/state")" = running ]
    [ -f "$B/files.tar.gz" ] && [ -f "$B/secrets/.env" ]
    [ "$(stat -c %a "$B")" = 700 ] && [ "$(stat -c %a "$B/secrets/.env")" = 600 ]
    [ "$(lib "_kei_bk_mget '$B' format")" = 2 ]
    [ "$(lib "_kei_bk_mget '$B' secrets")" = plain ]
    [ "$(lib "_kei_bk_mget '$B' count_files")" = 2 ]
    [ "$(lib "_kei_bk_mget '$B' demo_after")" = 1 ]
    ( cd "$B" && sha256sum -c --quiet SHA256SUMS )
    run lib "kei_backup_check '$B' demo"
    [ "$status" -eq 0 ]
    [ ! -e "$B/.meta" ] && [ ! -e "$B/.files.list" ]
    run lib 'kei_backup_list demo | cut -f3,4'
    [ "$output" = "$(printf 'manual\tself')" ]
}

@test "encrypted configuration: the phrase is needed to open it; the kit has no phrase" {
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_setup confirm"
    [ "$status" -eq 0 ]
    [[ "$output" != *"$PHRASE"* ]]   # given, so not shown again
    K="$KEI_OWNED_DIR/backup/recovery-kit.txt"
    [ "$(stat -c %a "$K")" = 600 ]
    grep -q '^@@begin secret-key$' "$K"
    nope grep -q "$PHRASE" "$K"
    nope grep -rq "$PHRASE" "$KEI_OWNED_DIR"
    run lib 'kei_backup_run demo'
    [ "$status" -eq 0 ]
    B="${lines[-1]}"
    [ -f "$B/secrets.tar.gpg" ] && [ ! -e "$B/secrets" ]
    [ "$(lib "_kei_bk_mget '$B' secrets")" = gpg ]
    nope grep -q s3cr3t "$B/secrets.tar.gpg"
    run lib "_kei_bk_secrets_open '$B'"
    [ "$status" -eq 7 ]
    run lib "KEI_BACKUP_PHRASE=wrong-phrase-123 _kei_bk_secrets_open '$B'"
    [ "$status" -eq 7 ]
    run lib "d=\$(KEI_BACKUP_PHRASE='$PHRASE' _kei_bk_secrets_open '$B') && cat \"\$d/.env\" && rm -rf \"\$d\""
    [ "$status" -eq 0 ]
    [ "$output" = "KN_SECRET=s3cr3t" ]
    # Opened once, the agent did not keep the phrase.
    run lib "_kei_bk_secrets_open '$B'"
    [ "$status" -eq 7 ]
}

@test "a new phrase is made and shown once when none is given" {
    run lib 'kei_backup_setup confirm'
    [ "$status" -eq 0 ]
    ph=$(sed -n 's/.*not saved on this server): //p' <<< "$output")
    [[ "$ph" =~ ^[A-Z2-9]{4}(-[A-Z2-9]{4}){5}$ ]]
    nope grep -rq "$ph" "$KEI_OWNED_DIR"
    run lib 'kei_backup_setup confirm'
    [[ "$output" == *"already set up"* ]]
}

@test "crash during the capture: the platform is started again and the capture is done again whole" {
    run lib '_KEI_BK_CRASH_AFTER=db kei_backup_run demo'
    [ "$status" -eq 137 ]
    [ "$(cat "$DEMO/state")" = stopped ]
    B=$(ls -d "$KEI_BK_ROOT"/demo/knx-demo-*)
    [ ! -f "$B/manifest.json" ]
    run lib 'kei_backup_list demo'
    [ -z "$output" ]
    run lib 'kei_backup_incomplete demo | cut -f2,3'
    [ "$output" = "$(printf 'db\tno')" ]
    printf 'three\n' > "$DEMO/data/c.txt"
    run lib "kei_backup_resume '${B##*/}'"
    [ "$status" -eq 0 ]
    [ "$(cat "$DEMO/state")" = running ]
    s=$(steps "$B")
    [[ "$s" == *"db writes-resumed capture-restart capture writes-stopped db files writes-resumed capture-done secrets manifest resumed"* ]] || [[ "$s" == *"db writes-resumed capture-restart capture writes-stopped db files writes-resumed capture-done resumed secrets manifest done"* ]]
    grep -q '"reason":"recovered"' "$B/journal.jsonl"
    [ "$(lib "_kei_bk_mget '$B' count_files")" = 3 ]
    run lib "kei_backup_check '$B' demo"
    [ "$status" -eq 0 ]
    [ -z "$(lib 'kei_backup_incomplete demo')" ]
}

@test "crash after the capture: resume goes on from the next step, with the parts checked" {
    run lib '_KEI_BK_CRASH_AFTER=secrets kei_backup_run demo'
    [ "$status" -eq 137 ]
    [ "$(cat "$DEMO/state")" = running ]
    B=$(ls -d "$KEI_BK_ROOT"/demo/knx-demo-*)
    run lib "kei_backup_resume '$B'"
    [ "$status" -eq 0 ]
    [ "$(grep -c '"step":"capture-done"' "$B/journal.jsonl")" = 1 ]
    nope grep -q capture-restart "$B/journal.jsonl"
    [ "$(grep -c '"step":"secrets"' "$B/journal.jsonl")" = 1 ]
    run lib "kei_backup_check '$B' demo"
    [ "$status" -eq 0 ]
    run lib "kei_backup_resume '$B'"
    [[ "$output" == *"nothing to resume"* ]]
}

@test "resume refuses a part changed since; discard takes only incomplete packages" {
    run lib '_KEI_BK_CRASH_AFTER=capture-done kei_backup_run demo'
    [ "$status" -eq 137 ]
    B=$(ls -d "$KEI_BK_ROOT"/demo/knx-demo-*)
    printf 'tampered' | gzip > "$B/db.sql.gz"
    run lib "kei_backup_resume '$B'"
    [ "$status" -eq 4 ]
    run lib "kei_backup_discard '$B'"
    [ "$status" -eq 0 ]
    [ ! -e "$B" ]
    run lib 'kei_backup_run demo'
    C="${lines[-1]}"
    run lib "kei_backup_discard '$C'"
    [ "$status" -eq 3 ]
    [ -d "$C" ]
}

@test "malicious packages are refused before anything is restored" {
    run lib 'kei_backup_run demo'
    B="${lines[-1]}"
    resum() { ( cd "$1" && sha256sum db.sql.gz files.tar.gz secrets/.env > SHA256SUMS.new && grep manifest.json SHA256SUMS >> SHA256SUMS.new && mv SHA256SUMS.new SHA256SUMS ); }
    bad() { cp -a "$B" "$T/bad"; }
    # "..", absolute path, link out, device, hard link.
    for kind in dotdot abs link dev hard; do
        rm -rf "$T/bad" "$T/src"; bad; mkdir -p "$T/src"; echo x > "$T/src/f"
        case $kind in
            dotdot) tar -C "$T/src" -czf "$T/bad/files.tar.gz" --transform 's#^\./f#../evil#' ./f ;;
            abs) python3 -c 'import tarfile,io,sys; t=tarfile.open(sys.argv[1],"w:gz"); i=tarfile.TarInfo("/etc/evil"); i.size=1; t.addfile(i, io.BytesIO(b"x")); t.close()' "$T/bad/files.tar.gz" ;;
            link) ln -s /etc/passwd "$T/src/l"; tar -C "$T/src" -czf "$T/bad/files.tar.gz" . ;;
            dev) python3 -c 'import tarfile,sys; t=tarfile.open(sys.argv[1],"w:gz"); i=tarfile.TarInfo("d"); i.type=tarfile.CHRTYPE; i.devmajor=1; i.devminor=3; t.addfile(i); t.close()' "$T/bad/files.tar.gz" ;;
            hard) ln "$T/src/f" "$T/src/g"; tar -C "$T/src" -czf "$T/bad/files.tar.gz" . ;;
        esac
        resum "$T/bad"
        run lib "kei_backup_check '$T/bad' demo"
        [ "$status" -eq 4 ] || { echo "$kind accepted"; false; }
        [[ "$output" == *"unsafe entries"* ]]
    done
    # An expansion bomb: 80 MB of zeros in a tiny archive.
    rm -rf "$T/bad" "$T/src"; bad; mkdir -p "$T/src"; head -c $((80 << 20)) /dev/zero > "$T/src/z"
    tar -C "$T/src" -czf "$T/bad/files.tar.gz" .; resum "$T/bad"
    run lib "kei_backup_check '$T/bad' demo"
    [ "$status" -eq 4 ]
    [[ "$output" == *"expands too much"* ]]
    # The checksum list names a file outside the package.
    rm -rf "$T/bad"; bad; printf '%064d  ../../etc/passwd\n' 0 >> "$T/bad/SHA256SUMS"
    run lib "kei_backup_check '$T/bad' demo"
    [ "$status" -eq 4 ]
    [[ "$output" == *"outside the package"* ]]
    # A damaged manifest, and one of another platform.
    rm -rf "$T/bad"; bad; sed -i 's/"format": 2,/"format": 2,,/' "$T/bad/manifest.json"; resum "$T/bad"
    run lib "kei_backup_check '$T/bad' demo"
    [ "$status" -eq 4 ]
    run lib "kei_backup_check '$B' tainacan"
    [ "$status" -eq 4 ]
    # And the good one still passes.
    run lib "kei_backup_check '$B' demo"
    [ "$status" -eq 0 ]
}

@test "restic: the files go to a local repository as a snapshot; restored and checked in a staging area" {
    command -v restic >/dev/null || skip "restic not installed"
    run lib 'kei_backup_repo demo local'
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$KEI_OWNED_DIR/backup/restic-demo.pass")" = 600 ]
    run lib 'kei_backup_run demo'
    [ "$status" -eq 0 ]
    B="${lines[-1]}"
    [ -f "$B/files.ref.json" ] && [ ! -e "$B/files.tar.gz" ]
    [ "$(lib "_kei_bk_mget '$B' mode")" = ref ]
    grep -q '"files": 2' "$B/files.ref.json"
    run lib "kei_backup_check '$B' demo"
    [ "$status" -eq 0 ]
    run lib "kei_backup_list demo | cut -f4"
    [ "$output" = ref ]
    # The snapshot restored: same names, sizes and contents, the link kept.
    run lib "_kei_bk_stage_ref '$B' demo"
    [ "$status" -eq 0 ]
    IFS=$'\t' read -r stage tree <<< "$output"
    diff -r "$DEMO/data" "$tree"
    [ "$(readlink "$tree/link")" = a.txt ]
    rm -rf "$stage"
    # A damaged reference is refused.
    cp -a "$B" "$T/bad"; sed -i 's/"snapshot": "[0-9a-f]*"/"snapshot": "..\/x"/' "$T/bad/files.ref.json"
    ( cd "$T/bad" && sha256sum db.sql.gz files.ref.json secrets/.env > S && grep manifest.json SHA256SUMS >> S && mv S SHA256SUMS )
    run lib "kei_backup_check '$T/bad' demo"
    [ "$status" -eq 4 ]
}

@test "restic retention: snapshots no package names are forgotten" {
    command -v restic >/dev/null || skip "restic not installed"
    lib 'kei_backup_repo demo local' >/dev/null
    run lib 'kei_backup_run demo'
    B="${lines[-1]}"
    # An orphan: a snapshot whose package is gone.
    RESTIC_REPOSITORY="$KEI_BK_ROOT/restic/demo" RESTIC_PASSWORD_FILE="$KEI_OWNED_DIR/backup/restic-demo.pass" \
        restic backup -q --tag knx-demo --host koha-nexus "$DEMO/data" >/dev/null
    n() { RESTIC_REPOSITORY="$KEI_BK_ROOT/restic/demo" RESTIC_PASSWORD_FILE="$KEI_OWNED_DIR/backup/restic-demo.pass" restic snapshots --json --tag knx-demo | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'; }
    [ "$(n)" = 2 ]
    run lib 'kei_backup_retention demo'
    [ "$status" -eq 0 ]
    [ "$(n)" = 1 ]
    run lib "_kei_bk_stage_ref '$B' demo"
    [ "$status" -eq 0 ]
    rm -rf "${output%%$'\t'*}"
    run lib 'kei_backup_maintain demo'
    [ "$status" -eq 0 ]
}

@test "restic through rclone, and the copy of each package to a cloud remote, resumed after a crash" {
    command -v restic >/dev/null && command -v rclone >/dev/null || skip "restic or rclone not installed"
    rclone config create loc local >/dev/null
    run lib "kei_backup_repo demo rclone:loc:$T/rrepo"
    [ "$status" -eq 0 ]
    # Without the backup key the configuration would leave in clear: refused.
    run lib "kei_backup_copy demo loc:$T/cloud"
    [ "$status" -eq 6 ]
    lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_setup confirm" >/dev/null
    run lib "kei_backup_copy demo loc:$T/cloud"
    [ "$status" -eq 0 ]
    run lib 'kei_backup_copy demo nowhere:x'
    [ "$status" -eq 3 ]
    # Never inside the folders of a Koha cloud backup: each plan its own destination.
    run lib "kei_backup_copy demo loc:$T/Backup_SQL_Koha"
    [ "$status" -eq 2 ]
    run lib "kei_backup_copy demo loc:$T/k/Backup_MARC_Koha/x"
    [ "$status" -eq 2 ]
    run lib "kei_backup_copy demo loc:$T/cloud"
    [ "$status" -eq 0 ]
    run lib '_KEI_BK_CRASH_AFTER=manifest kei_backup_run demo'
    [ "$status" -eq 137 ]
    B=$(ls -d "$KEI_BK_ROOT"/demo/knx-demo-*)
    [ ! -d "$T/cloud/${B##*/}" ]
    run lib 'kei_backup_incomplete demo | cut -f2,3'
    [ "$output" = "$(printf 'manifest\tyes')" ]
    run lib "kei_backup_discard '$B'"
    [ "$status" -eq 3 ]
    run lib "kei_backup_resume '$B'"
    [ "$status" -eq 0 ]
    ( cd "$T/cloud/${B##*/}" && sha256sum -c --quiet SHA256SUMS )
    grep -q '"step":"copy"' "$B/journal.jsonl"
    grep -q "rclone:loc:$T/rrepo" "$B/files.ref.json"
    run lib "_kei_bk_stage_ref '$B' demo"
    [ "$status" -eq 0 ]
    rm -rf "${output%%$'\t'*}"
}

@test "a new server: the kit and the phrase open the packages and the restic repository" {
    command -v restic >/dev/null || skip "restic not installed"
    lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_setup confirm" >/dev/null
    lib 'kei_backup_repo demo local' >/dev/null
    run lib 'kei_backup_run demo'
    B="${lines[-1]}"
    cp "$KEI_OWNED_DIR/backup/recovery-kit.txt" "$T/kit.txt"
    grep -q '^@@begin restic-demo$' "$T/kit.txt"
    nope grep -q "$(cat "$KEI_OWNED_DIR/backup/restic-demo.pass")" "$T/kit.txt"
    # The old server is gone.
    rm -rf "$KEI_OWNED_DIR"
    export KEI_OWNED_DIR="$T/new"
    run lib "KEI_BACKUP_PHRASE=wrong-phrase-123 kei_backup_kit_import '$T/kit.txt'"
    [ "$status" -eq 7 ]
    run lib "kei_backup_kit_import '$T/kit.txt'"
    [ "$status" -eq 7 ]
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_kit_import '$T/kit.txt'"
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$KEI_OWNED_DIR/backup/restic-demo.pass")" = 600 ]
    run lib "d=\$(KEI_BACKUP_PHRASE='$PHRASE' _kei_bk_secrets_open '$B') && cat \"\$d/.env\" && rm -rf \"\$d\""
    [ "$output" = "KN_SECRET=s3cr3t" ]
    run lib "_kei_bk_stage_ref '$B' demo"
    [ "$status" -eq 0 ]
    IFS=$'\t' read -r stage tree <<< "$output"
    diff -r "$DEMO/data" "$tree"
    rm -rf "$stage"
    # Not a kit.
    echo hello > "$T/no.txt"
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_kit_import '$T/no.txt'"
    [ "$status" -eq 2 ]
}

@test "retention: newest N, one per day, week and month, final always, the verified one always" {
    mk() {  # mk NAME CREATED LABEL
        local d="$KEI_BK_ROOT/demo/$1"; mkdir -p "$d"
        printf '{\n  "format": 2,\n  "platform": "demo",\n  "created": "%s",\n  "label": "%s",\n  "complete": true\n}\n' "$2" "$3" > "$d/manifest.json"
    }
    mk knx-demo-20260101-010000 "2026-01-01 01:00:00" final
    mk knx-demo-20260301-010000 "2026-03-01 01:00:00" manual
    mk knx-demo-20260415-010000 "2026-04-15 01:00:00" manual
    mk knx-demo-20260501-010000 "2026-05-01 01:00:00" manual
    mk knx-demo-20260502-010000 "2026-05-02 01:00:00" manual
    mk knx-demo-20260502-020000 "2026-05-02 02:00:00" manual
    mk knx-demo-20260503-010000 "2026-05-03 01:00:00" manual
    printf '{\n  "result": "ok"\n}\n' > "$KEI_BK_ROOT/demo/knx-demo-20260301-010000/verify.json"
    run lib 'KEI_BK_KEEP_LAST=1 KEI_BK_KEEP_DAILY=2 KEI_BK_KEEP_WEEKLY=1 KEI_BK_KEEP_MONTHLY=2 kei_backup_retention demo; ls "$KEI_BK_ROOT/demo"'
    [ "$status" -eq 0 ]
    # last 1 + days 05-03, 05-02 (newest of the day) + week of 05-03 + months 05 and 04 + final + verified.
    [ "$(tr '\n' ' ' <<< "$output")" = "knx-demo-20260101-010000 knx-demo-20260301-010000 knx-demo-20260415-010000 knx-demo-20260502-020000 knx-demo-20260503-010000 " ]
}

@test "an older backup is picked for the monthly test; verify writes its result" {
    run lib 'kei_backup_run demo'
    A="${lines[-1]}"
    sleep 2
    printf 'four\n' > "$DEMO/data/d.txt"
    run lib 'kei_backup_run demo'
    B="${lines[-1]}"
    t=$(date -d "$(lib "_kei_bk_mget '$A' created")" +%s)
    run lib "_KEI_BK_NOW=$((t + 30 * 86400)) kei_backup_pick demo 30"
    [ "$output" = "$A" ]
    run lib 'kei_backup_pick demo 30'
    [ "$output" = "$A" ]   # none that old: the oldest
    run lib "_KEI_BK_NOW=$((t + 30 * 86400)) kei_backup_verify demo 30"
    [ "$status" -eq 0 ]
    grep -q '"result": "ok"' "$A/verify.json"
    [ ! -e "$B/verify.json" ]
    run lib 'kei_backup_status demo'
    [[ "$output" == *"demo.verified="*"${A##*/} ok"* ]]
    [[ "$output" == *"demo.count=2"* ]]
    [[ "$output" == *"demo.keep=7 7 4 6"* ]]
}

@test "schedule: daily package, weekly maintenance, monthly verification; off removes the file" {
    run lib 'kei_backup_schedule demo 25:00'
    [ "$status" -eq 2 ]
    run lib 'kei_backup_schedule demo 02:30'
    [ "$status" -eq 0 ]
    grep -qx '30 2 \* \* \* root /usr/local/bin/config.sh --task platform-backup-run demo scheduled >/dev/null 2>&1' "$KEI_BK_CRON"
    grep -qx '30 3 \* \* 0 root /usr/local/bin/config.sh --task platform-backup-maintain demo >/dev/null 2>&1' "$KEI_BK_CRON"
    grep -qx '30 4 1 \* \* root /usr/local/bin/config.sh --task platform-backup-verify demo 30 >/dev/null 2>&1' "$KEI_BK_CRON"
    [ "$(stat -c %a "$KEI_BK_CRON")" = 644 ]
    run lib 'kei_owned_list cron-file demo | cut -f1,2'
    [ "$output" = "$(printf 'cron-file\tkoha-nexus-platform-backups')" ]
    run lib 'kei_backup_schedule demo off'
    [ "$status" -eq 0 ]
    [ ! -e "$KEI_BK_CRON" ]
    [ -z "$(lib 'kei_owned_list cron-file demo')" ]
}

@test "one action at a time per platform" {
    exec 8>"$KEI_OWNED_DIR/backup/demo.lock" 2>/dev/null || { mkdir -p "$KEI_OWNED_DIR/backup"; exec 8>"$KEI_OWNED_DIR/backup/demo.lock"; }
    flock -n 8
    run lib 'kei_backup_run demo'
    [ "$status" -eq 9 ]
    exec 8>&-
    run lib 'kei_backup_run demo'
    [ "$status" -eq 0 ]
}

@test "the platform-backup tasks are not Koha tasks" {
    for t in platform-backup-run platform-backup-setup platform-backup-resume platform-backup-verify platform-backup-schedule; do
        run lib "kei_task_needs_koha $t"
        [ "$status" -ne 0 ]
    done
}
