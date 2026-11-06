#!/usr/bin/env bats
# The joint package (installer: kei_set_*): Koha + Tainacan in one
# transportable file, and the inspection of any backup before a restore.
# No Docker and no MariaDB: Koha's dump is a stand-in for create_safety_backup
# and Tainacan is the real backup engine over a stand-in platform (a text
# file as the database, a directory as the files), as in backup_engine.bats.
# Covered: the set holds the data (not references) with each capture's own
# times; a partial failure is never "done" and keeps the valid part; lack
# of space; the file is recognised by its content, not its name; tampered
# and malicious archives are refused before anything is extracted; nothing
# the manifest says is ever run.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_BK_ROOT="$T/backups" KEI_TAINACAN_BACKUPS="$T/backups/tainacan"
    export KEI_BK_CRON="$T/cron.d/koha-nexus-platform-backups" KEI_BK_NEED_CRON=0 RCLONE_CONFIG="$T/rclone.conf"
    export DEMO="$T/demo" OUT="$T/out" FAKE_KOHA=yes FAKE_TN=yes
    mkdir -p "$DEMO/data/sub" "$T/cron.d" "$OUT"
    printf 'CREATE TABLE t (x int);\nINSERT INTO t VALUES (1);\n' > "$DEMO/db.sql"
    printf 'one\n' > "$DEMO/data/a.txt"; printf 'two\n' > "$DEMO/data/sub/b.txt"
    printf 'KN_SECRET=s3cr3t\n' > "$DEMO/.env"; chmod 600 "$DEMO/.env"
    printf '<yazgfs><config><pass>koha-db-pass</pass></config></yazgfs>\n' > "$T/koha-conf.xml"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
DB_NAME=koha_library
KOHA_CONF='$T/koha-conf.xml'
KEI_BK_PLATFORMS=tainacan
is_koha_installed() { [ \"\$FAKE_KOHA\" = yes ]; }
_kei_tn_get() { [ \"\$1\" = status ] && [ \"\$FAKE_TN\" = yes ] && echo installed; [ \"\$1\" = url ] && echo http://acervo.local; return 0; }
backup_lock_acquire() { return 0; }
backup_lock_release() { return 0; }
create_safety_backup() {
    [ \"\$FAKE_KOHA_DUMP\" = fail ] && { SAFETY_BACKUP_ERROR='The disk is full (free in x: 0)'; return 1; }
    printf -- '-- MariaDB dump 10.19\nCREATE TABLE biblio (id int);\n' | gzip > \"\$1\"
}
_kei_bk_tainacan_preflight() { [ \"\$FAKE_TN_DUMP\" = fail ] && { echo 'The Tainacan database is not running.' >&2; return 3; }; [ -d \"\$DEMO/data\" ]; }
_kei_bk_tainacan_size() { echo 1; }
_kei_bk_tainacan_stop() { :; }
_kei_bk_tainacan_start() { :; }
_kei_bk_tainacan_meta() { printf 'url\t\"http://acervo.local\"\n'; }
_kei_bk_tainacan_dump() { cat \"\$DEMO/db.sql\"; }
_kei_bk_tainacan_tar() { tar -C \"\$DEMO/data\" -cf - .; }
_kei_bk_tainacan_path() { printf '%s' \"\$DEMO/data\"; }
_kei_bk_tainacan_after() { :; }
_kei_bk_tainacan_secrets() { printf '%s\n' \"\$DEMO/.env\"; }
$1" 3>&-
}

field() { sed -n "s/^$1=//p" <<<"$2" | head -n 1; }
manifest() { tar -xOf "$1" manifest.json; }

@test "S01 the set holds both platforms' data, each with its own capture times, and says per-platform" {
    run lib "kei_set_backup '$OUT'"
    [ "$status" -eq 0 ]
    SET=$(field file "$output")
    [[ "$output" == *$'platform=koha\tok\t'* ]] && [[ "$output" == *$'platform=tainacan\tok\t'* ]]
    [[ "$SET" == "$OUT"/knx-set-*.tar ]] && [[ "$SET" != *partial* ]]
    m=$(manifest "$SET")
    python3 -I - "$m" <<'PY'
import json, sys
m = json.loads(sys.argv[1])
assert m["kind"] == "koha-nexus-set" and m["format"] == 1 and m["complete"] is True
assert m["consistency"] == "per-platform"
koha, tn = m["platforms"]
assert koha["id"] == "koha" and koha["result"] == "ok" and koha["path"].startswith("koha/koha_library_set_")
assert tn["id"] == "tainacan" and tn["path"].startswith("tainacan/knx-tainacan-")
for p in (koha, tn):
    assert p["started"] and p["finished"] and p["started"] <= p["finished"] and len(p["sha256"]) == 64
PY
    # The data itself, never a reference to a restic repository.
    tar -tf "$SET" | grep -q 'tainacan/knx-tainacan-.*/files.tar.gz$'
    ! tar -tf "$SET" | grep -q 'files.ref.json'
    tar -xOf "$SET" "$(tar -tf "$SET" | grep '^koha/.*\.sql\.gz$')" | gzip -dc | grep -q 'CREATE TABLE biblio'
    # Only the files of a set, and their checksums.
    ! tar -tf "$SET" | grep -vE '^(manifest\.json|SHA256SUMS|koha/.*|tainacan/.*)$'
    [ ! -e "$OUT"/.knx-set.* ]
}

@test "S02 a platform that fails leaves a partial set, never 'done', with the valid part in it" {
    FAKE_TN_DUMP=fail run lib "kei_set_backup '$OUT'"
    [ "$status" -eq 9 ]
    [ "$(field complete "$output")" = no ]
    [[ "$output" == *$'platform=tainacan\tfailed\t'*"not running"* ]]
    SET=$(ls "$OUT"/knx-set-*-partial.tar)
    m=$(manifest "$SET")
    [[ "$m" == *'"complete": false'* ]]
    run lib "kei_set_inspect '$SET'"
    [ "$(field kind "$output")" = koha-nexus-set ]
    [ "$(field complete "$output")" = no ] && [ "$(field integrity "$output")" = ok ]
    [ "$(field platforms "$output")" = koha ]
    [[ "$output" == *$'part=tainacan\tfailed'*"not running"* ]]
}

@test "S03 nothing backed up: no set; not enough space: no set and nothing left behind" {
    FAKE_TN_DUMP=fail FAKE_KOHA_DUMP=fail run lib "kei_set_backup '$OUT'"
    [ "$status" -eq 9 ]
    [ -z "$(ls -A "$OUT")" ]
    run lib "df() { printf 'Filesystem 1B-blocks Used Available Use%% Mounted\nx 1 1 10 99%% /\n'; }; kei_set_backup '$OUT' koha"
    [ "$status" -eq 5 ]
    [[ "$output" == *"Not enough free disk"* ]]
    [ -z "$(ls -A "$OUT")" ]
}

@test "S04 a backup is recognised by its content, not by its name" {
    lib "kei_set_backup '$OUT'" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    cp "$SET" "$T/backup.sql.gz"
    printf -- '-- MariaDB dump 10.19\nCREATE TABLE x (y int);\n' | gzip > "$T/photo.jpg"
    head -c 4096 /dev/urandom > "$T/archive.tar"
    tar -C "$DEMO" -czf "$T/koha_marc_2026.tar.gz" data
    run lib "kei_set_inspect '$T/backup.sql.gz'"; [ "$(field kind "$output")" = koha-nexus-set ]
    run lib "kei_set_inspect '$T/photo.jpg'";     [ "$(field kind "$output")" = koha-sql ]
    run lib "kei_set_inspect '$T/archive.tar'";   [ "$(field kind "$output")" = unknown ]
    run lib "kei_set_inspect '$T/koha_marc_2026.tar.gz'"; [ "$(field kind "$output")" = unknown ]
    # A Tainacan package, as a folder or as an archive of it.
    PKG=$(ls -d "$KEI_TAINACAN_BACKUPS"/knx-tainacan-* | head -n 1)
    run lib "kei_set_inspect '$PKG'"
    [ "$(field kind "$output")" = tainacan-package ] && [ "$(field integrity "$output")" = ok ]
    tar -C "${PKG%/*}" -cf "$T/pkg.tar" "${PKG##*/}"
    run lib "kei_set_inspect '$T/pkg.tar'"; [ "$(field kind "$output")" = tainacan-archive ]
}

@test "S05 unpack: checked and verified in a private staging folder; a selective part is usable alone" {
    lib "kei_set_backup '$OUT'" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    run lib "kei_set_unpack '$SET'"
    [ "$status" -eq 0 ]
    STAGE=$(field stage "$output")
    [[ "$STAGE" == "$KEI_BK_ROOT"/.set-restore.* ]] && [ "$(stat -c %a "$STAGE")" = 700 ]
    [[ "$(field koha "$output")" == "$STAGE/koha/koha_library_set_"* ]]
    [[ "$(field tainacan "$output")" == "$STAGE/tainacan/knx-tainacan-"* ]]
    TN=$(ls -d "$STAGE"/tainacan/knx-tainacan-*)
    run lib "kei_backup_check '$TN' tainacan"
    [ "$status" -eq 0 ]
    run lib "kei_set_cleanup '$STAGE'"
    [ ! -e "$STAGE" ]
    run lib "kei_set_cleanup '$T'"            # only its own staging folders
    [ "$status" -eq 2 ] && [ -d "$T" ]
}

@test "S06 a tampered set is refused before anything is extracted" {
    lib "kei_set_backup '$OUT'" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    mkdir "$T/x" && tar -C "$T/x" -xf "$SET"
    printf -- '-- MariaDB dump\nDROP DATABASE koha_library;\n' | gzip > "$(ls "$T"/x/koha/*.sql.gz)"
    tar -C "$T/x" -cf "$T/tampered.tar" manifest.json SHA256SUMS koha tainacan
    run lib "kei_set_inspect '$T/tampered.tar'"
    [ "$(field integrity "$output")" = failed ]
    run lib "kei_set_unpack '$T/tampered.tar'"
    [ "$status" -eq 4 ]
    [ -z "$(ls -A "$KEI_BK_ROOT" | grep set-restore)" ]
}

@test "S07 malicious archives: paths out, links, unknown members, a forged manifest; its commands never run" {
    mkdir -p "$T/m/koha"
    printf -- '-- MariaDB dump\n' | gzip > "$T/m/koha/k.sql.gz"
    good='{"kind":"koha-nexus-set","format":1,"complete":true,"platforms":[{"id":"koha","result":"ok","path":"koha/k.sql.gz"}]}'
    mk() {   # NAME MANIFEST [extra tar args...]
        local name="$1" man="$2"; shift 2
        printf '%s' "$man" > "$T/m/manifest.json"
        ( cd "$T/m" && sha256sum manifest.json koha/k.sql.gz > SHA256SUMS && tar -cf "$T/$name" manifest.json SHA256SUMS koha "$@" )
    }
    ln -sf /etc/passwd "$T/m/koha/link"
    mk link.tar "$good"
    rm -f "$T/m/koha/link"
    printf 'echo pwned\n' > "$T/m/run.sh"; mk extra.tar "$good" run.sh; rm -f "$T/m/run.sh"
    mk path.tar '{"kind":"koha-nexus-set","format":1,"complete":true,"platforms":[{"id":"koha","result":"ok","path":"../../etc/cron.d/x"}]}'
    mk kind.tar '{"kind":"something-else","format":1,"complete":true,"platforms":[]}'
    mk cmd.tar '{"kind":"koha-nexus-set","format":1,"complete":true,"command":"touch '"$T"'/pwned","platforms":[{"id":"koha","result":"ok","path":"koha/k.sql.gz","error":"$(touch '"$T"'/pwned2)"}]}'
    python3 -I - "$T/dots.tar" <<'PY'
import io, sys, tarfile
with tarfile.open(sys.argv[1], "w") as tf:
    for name in ("manifest.json", "../escape.txt"):
        data = b"x"; info = tarfile.TarInfo(name); info.size = 1; tf.addfile(info, io.BytesIO(data))
PY
    for f in link.tar extra.tar path.tar kind.tar dots.tar; do
        run lib "kei_set_inspect '$T/$f'"
        [ "$(field kind "$output")" = unsafe ] || { echo "$f: $output"; false; }
        run lib "kei_set_unpack '$T/$f'"
        [ "$status" -eq 4 ]
    done
    # Extra keys are only data: read, never run.
    run lib "kei_set_unpack '$T/cmd.tar'"
    [ "$status" -eq 0 ]
    run lib "kei_set_inspect '$T/cmd.tar'"
    [[ "$output" == *'$(touch'* ]]
    [ ! -e "$T/pwned" ] && [ ! -e "$T/pwned2" ] && [ ! -e "$T/../escape.txt" ] && [ ! -e "$T/escape.txt" ]
}

@test "S08 the Koha configuration goes into the set only encrypted, with the backup key" {
    lib "kei_set_backup '$OUT' koha" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    ! tar -tf "$SET" | grep -q koha-conf
    ! tar -xOf "$SET" | grep -aq koha-db-pass
    lib "KEI_BACKUP_PHRASE=TEST-PHRA-SE12-3456-7890-ABCD kei_backup_setup confirm" >/dev/null
    rm -f "$OUT"/*.tar
    lib "kei_set_backup '$OUT' koha" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    tar -tf "$SET" | grep -qx 'koha/koha-conf.xml.gpg'
    ! tar -xOf "$SET" | grep -aq koha-db-pass
    [[ "$(manifest "$SET")" == *'"secrets": "gpg"'* ]]
}

@test "S09 the conflicts with this server are said before a restore" {
    lib "kei_set_backup '$OUT'" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    run lib "kei_set_inspect '$SET'"
    [[ "$output" == *$'conflict=koha\tThe Koha in use (database koha_library) is replaced'* ]]
    [[ "$output" == *$'conflict=tainacan\tThe Tainacan in use (http://acervo.local) is replaced'* ]]
    FAKE_KOHA=no FAKE_TN=no run lib "kei_set_inspect '$SET'"
    [[ "$output" == *$'conflict=koha\tKoha is not installed here'* ]]
    [[ "$output" == *$'conflict=tainacan\tTainacan is not installed here'* ]]
}

@test "S10 the set tasks are not Koha tasks and are in the dispatcher" {
    for task in set-backup set-inspect set-unpack set-cleanup; do
        run lib "kei_task_needs_koha $task"
        [ "$status" -eq 1 ]
        grep -E "^        [a-z|-]+\)" "$REPO/installer" | grep -q -- "$task"
    done
}
