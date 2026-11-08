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
    export KEI_BK_CRON="$T/cron.d/koha-nexus-platform-backups" KEI_SET_CRON="$T/cron.d/koha-nexus-backup-sets" KEI_BK_NEED_CRON=0 RCLONE_CONFIG="$T/rclone.conf"
    export DEMO="$T/demo" OUT="$T/out" FAKE_KOHA=yes FAKE_TN=yes
    mkdir -p "$DEMO/data/sub" "$T/cron.d" "$OUT"
    printf 'CREATE TABLE t (x int);\nINSERT INTO t VALUES (1);\n' > "$DEMO/db.sql"
    printf 'one\n' > "$DEMO/data/a.txt"; printf 'two\n' > "$DEMO/data/sub/b.txt"
    printf 'KN_SECRET=s3cr3t\n' > "$DEMO/.env"; chmod 600 "$DEMO/.env"
    # A Koha installation's files and secrets, under T (paths as the installer names them).
    K="$T/koha"; mkdir -p "$K/etc" "$K/uploads/ab" "$K/plugins/Koha/Plugin" "$K/opac-custom" "$K/staff-custom" "$K/mr" "$K/conf/import-profiles"
    # As in a real koha-conf.xml, Zebra's <server> sections come first and
    # have <config> elements of their own (a path, never the main section).
    cat > "$T/koha-conf.xml" <<XML
<yazgfs>
<server id="biblioserver" listenref="biblioserver">
 <!-- <encryption_key>commented-key</encryption_key> -->
 <config>/etc/koha/zebradb/zebra-biblios-dom.cfg</config>
</server>
<config>
 <pass>koha-db-pass</pass>
 <upload_path>$K/uploads</upload_path>
 <pluginsdir>$K/plugins</pluginsdir>
 <encryption_key>OLD-key-0123456789abcdef</encryption_key>
</config></yazgfs>
XML
    printf 'scan\n' > "$K/uploads/ab/scan.pdf"; printf 'package X;\n' > "$K/plugins/Koha/Plugin/X.pm"
    printf 'logo\n' > "$K/opac-custom/logo.png"; printf 'rule\n' > "$K/mr/rules.tsv"
    printf 'VISION_KEY=vision-secret\n' > "$K/mr/vision.conf"; chmod 600 "$K/mr/vision.conf"
    printf '<sip><login id="m1" password="sip-secret"/></sip>\n' > "$K/etc/SIPconfig.xml"
    printf 'KEI_Z3950_LOGIN=z-secret\n' > "$K/conf/.env"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
DB_NAME=koha_library
INSTANCE=library
KOHA_CONF='$T/koha-conf.xml'
K='$T/koha'
SIP_CONF=\$K/etc/SIPconfig.xml MSG_CONF=\$K/etc/kei-messaging.conf MR_DIR=\$K/mr CONF_DIR=\$K/conf
OPAC_CUSTOM_DIR=\$K/opac-custom STAFF_CUSTOM_DIR=\$K/staff-custom THEME_STATE=\$K/conf/theme-settings.json
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

never() { ! "$@"; }
field() { sed -n "s/^$1=//p" <<<"$2" | head -n 1; }
manifest() { tar -xOf "$1" manifest.json; }

@test "S01 the set holds both platforms' data, each with its own capture times, and says per-platform" {
    run lib "kei_set_backup '$OUT' '' no-secrets"
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
    [ -z "$(tar -tf "$SET" | grep 'files.ref.json')" ]
    tar -xOf "$SET" "$(tar -tf "$SET" | grep '^koha/.*\.sql\.gz$')" | gzip -dc | grep -q 'CREATE TABLE biblio'
    # Only the files of a set, and their checksums.
    [ -z "$(tar -tf "$SET" | grep -vE '^(manifest\.json|SHA256SUMS|koha/.*|tainacan/.*)$')" ]
    [ ! -e "$OUT"/.knx-set.* ]
}

@test "S02 a platform that fails leaves a partial set, never 'done', with the valid part in it" {
    FAKE_TN_DUMP=fail run lib "kei_set_backup '$OUT' '' no-secrets"
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
    FAKE_TN_DUMP=fail FAKE_KOHA_DUMP=fail run lib "kei_set_backup '$OUT' '' no-secrets"
    [ "$status" -eq 9 ]
    [ -z "$(ls -A "$OUT")" ]
    run lib "df() { printf 'Filesystem 1B-blocks Used Available Use%% Mounted\nx 1 1 10 99%% /\n'; }; kei_set_backup '$OUT' koha no-secrets"
    [ "$status" -eq 5 ]
    [[ "$output" == *"Not enough free disk"* ]]
    [ -z "$(ls -A "$OUT")" ]
}

@test "S04 a backup is recognised by its content, not by its name" {
    lib "kei_set_backup '$OUT' '' no-secrets" >/dev/null
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
    lib "kei_set_backup '$OUT' '' no-secrets" >/dev/null
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
    lib "kei_set_backup '$OUT' '' no-secrets" >/dev/null
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

@test "S08 Koha's secrets never in clear: without a key the person chooses first; data-only is never 'full'" {
    clear_secrets() {   # SET: no secret value readable anywhere in it, nor in its files archive
        local all; all=$(tar -xOf "$1"; tar -xOf "$1" koha/files.tar.gz 2>/dev/null | tar -xzOf - 2>/dev/null)
        never grep -aqE 'koha-db-pass|sip-secret|vision-secret|z-secret|OLD-key' <<<"$all"
    }
    # No key: nothing is captured, the reason is said, and a choice is asked for.
    run lib "kei_set_backup '$OUT'"
    [ "$status" -eq 7 ] && [ "$(field needs "$output")" = key ]
    [[ "$output" == *"Set up the backup key first, or make the package without the secrets"* ]]
    [ -z "$(ls -A "$OUT")" ]
    # The person chose a package without the secrets: the data files go, marked data-only.
    run lib "kei_set_backup '$OUT' koha no-secrets"
    [ "$status" -eq 0 ] && [ "$(field recoverability "$output")" = partial ]
    [[ "$output" == *$'platform=koha\tok\t'*$'\tdata-only'* ]]
    SET=$(ls "$OUT"/knx-set-*.tar)
    tar -tf "$SET" | grep -qx 'koha/files.tar.gz'
    [ -z "$(tar -tf "$SET" | grep 'secrets\|koha-conf')" ]
    files=$(tar -xOf "$SET" koha/files.tar.gz | tar -tzf -)
    for f in ./uploads/ab/scan.pdf ./plugins/Koha/Plugin/X.pm ./opac-custom/logo.png ./marc-replace/rules.tsv; do
        grep -qx "$f" <<<"$files" || { echo "missing $f"; false; }
    done
    never grep -q vision.conf <<<"$files"
    clear_secrets "$SET"
    m=$(manifest "$SET")
    python3 -I - "$m" <<'PY'
import json, sys
m = json.loads(sys.argv[1])
assert m["recoverability"] == "partial" and "koha-common package" in m["external"]
k = m["platforms"][0]
assert k["id"] == "koha" and k["secrets"] == "none" and k["recoverability"] == "data-only"
PY
    run lib "kei_set_inspect '$SET'"
    [ "$(field recoverability "$output")" = partial ] && [ "$(field koha_files "$output")" = yes ]
    # With the backup key: the secrets go, encrypted only, and the package is full.
    lib "KEI_BACKUP_PHRASE=TEST-PHRA-SE12-3456-7890-ABCD kei_backup_setup confirm" >/dev/null
    rm -f "$OUT"/*.tar
    run lib "kei_set_backup '$OUT' koha"
    [ "$status" -eq 0 ] && [ "$(field recoverability "$output")" = full ]
    SET=$(ls "$OUT"/knx-set-*.tar)
    tar -tf "$SET" | grep -qx 'koha/secrets.tar.gpg'
    clear_secrets "$SET"
    [[ "$(manifest "$SET")" == *'"secrets": "gpg"'* ]]
}

@test "S09 the conflicts with this server are said before a restore" {
    lib "kei_set_backup '$OUT' '' no-secrets" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    run lib "kei_set_inspect '$SET'"
    [[ "$output" == *$'conflict=koha\tThe Koha in use (database koha_library) is replaced'* ]]
    [[ "$output" == *$'conflict=tainacan\tThe Tainacan in use (http://acervo.local) is replaced'* ]]
    FAKE_KOHA=no FAKE_TN=no run lib "kei_set_inspect '$SET'"
    [[ "$output" == *$'conflict=koha\tKoha is not installed here'* ]]
    [[ "$output" == *$'conflict=tainacan\tTainacan is not installed here'* ]]
}

@test "S10 the set tasks are not Koha tasks and are in the dispatcher" {
    for task in set-backup set-inspect set-unpack set-cleanup set-koha-extras set-schedule set-schedule-status set-run; do
        run lib "kei_task_needs_koha $task"
        [ "$status" -eq 1 ]
        grep -E "^        [a-z|-]+\)" "$REPO/installer" | grep -q -- "$task"
    done
}

@test "S11 Koha's secrets come back without overwriting the target blindly: only the encryption key, never a value shown" {
    PH=TEST-PHRA-SE12-3456-7890-ABCD
    lib "KEI_BACKUP_PHRASE=$PH kei_backup_setup confirm" >/dev/null
    lib "kei_set_backup '$OUT' koha" >/dev/null
    SET=$(ls "$OUT"/knx-set-*.tar)
    # The target: another installation (its own database password and key),
    # no uploads, its own SIP2 logins, no AI key.
    sed -i 's/koha-db-pass/NEW-db-pass/; s/OLD-key-0123456789abcdef/NEW-key-fedcba9876543210/' "$T/koha-conf.xml"
    chmod 640 "$T/koha-conf.xml"
    rm -rf "$K/uploads" "$K/mr/vision.conf"
    printf '<sip><login id="m9" password="target-sip"/></sip>\n' > "$K/etc/SIPconfig.xml"
    STAGE=$(field stage "$(lib "kei_set_unpack '$SET'")")
    shown() { never grep -qE 'koha-db-pass|NEW-db-pass|sip-secret|target-sip|vision-secret|z-secret|OLD-key|NEW-key' <<<"$1"; }
    # The plan: what would change, with no value in it; nothing changes.
    before=$(sha256sum "$T/koha-conf.xml" "$K/etc/SIPconfig.xml")
    run lib "KEI_BACKUP_PHRASE=$PH kei_set_koha_extras plan '$STAGE'"
    [ "$status" -eq 0 ] && shown "$output"
    [ "$(field secrets "$output")" = open ]
    [[ "$output" == *$'item=uploads\trestore\t'"$K/uploads"* ]]
    [[ "$output" == *$'item=encryption_key\tapply\t'"$T/koha-conf.xml"* ]]
    [[ "$output" == *$'item=SIPconfig.xml\tbeside\t'"$K/etc/SIPconfig.xml.from-backup"* ]]
    [[ "$output" == *$'item=vision.conf\tadd\t'"$K/mr/vision.conf"* ]]
    [[ "$output" == *$'item=panel.env\tsame\t'* ]]
    [ "$before" = "$(sha256sum "$T/koha-conf.xml" "$K/etc/SIPconfig.xml")" ] && [ ! -e "$K/uploads" ]
    # No phrase, a wrong phrase, no key here: the secrets are not opened.
    run lib "kei_set_koha_extras plan '$STAGE'"; [ "$(field secrets "$output")" = missing ]
    run lib "KEI_BACKUP_PHRASE=WRONG-PHRA-SE00 kei_set_koha_extras plan '$STAGE'"; [ "$(field secrets "$output")" = wrong ]
    never grep -q 'item=encryption_key' <<<"$output"
    run lib "_kei_bk_has_key() { return 1; }; KEI_BACKUP_PHRASE=$PH kei_set_koha_extras plan '$STAGE'"; [ "$(field secrets "$output")" = nokey ]
    # Apply needs a yes; then only <encryption_key> changes in koha-conf.xml.
    run lib "KEI_BACKUP_PHRASE=$PH kei_set_koha_extras apply '$STAGE'"
    [ "$status" -eq 3 ] && [ "$before" = "$(sha256sum "$T/koha-conf.xml" "$K/etc/SIPconfig.xml")" ]
    run lib "KEI_BACKUP_PHRASE=$PH kei_set_koha_extras apply '$STAGE' confirm"
    [ "$status" -eq 0 ] && shown "$output"
    grep -q '<encryption_key>OLD-key-0123456789abcdef</encryption_key>' "$T/koha-conf.xml"
    grep -q '<pass>NEW-db-pass</pass>' "$T/koha-conf.xml"
    grep -q "<upload_path>$K/uploads</upload_path>" "$T/koha-conf.xml"
    [ "$(stat -c %a "$T/koha-conf.xml")" = 640 ]
    old=$(ls "$T"/koha-conf.xml.kei-before-secrets-*)
    [ "$(stat -c %a "$old")" = 600 ] && grep -q NEW-key "$old"
    # The data files are back; the target's own secrets are kept, the packaged one beside.
    [ "$(cat "$K/uploads/ab/scan.pdf")" = scan ]
    grep -q target-sip "$K/etc/SIPconfig.xml"
    grep -q sip-secret "$K/etc/SIPconfig.xml.from-backup" && [ "$(stat -c %a "$K/etc/SIPconfig.xml.from-backup")" = 600 ]
    grep -q vision-secret "$K/mr/vision.conf" && [ "$(stat -c %a "$K/mr/vision.conf")" = 600 ]
    # What the files replaced was kept first.
    safety=$(field safety "$output")
    [[ "$safety" == "$KEI_BK_ROOT"/koha-before-files-*.tar.gz ]] && tar -tzf "$safety" | grep -q 'opac-custom/logo.png'
    # Only its own staging folders.
    run lib "kei_set_koha_extras plan '$T'"; [ "$status" -eq 2 ]
}

# ----------------------------------------------------------------------
# The scheduled joint package (U6)
# ----------------------------------------------------------------------
history() { cat "$KEI_BK_ROOT/sets-history.jsonl"; }
runs() { grep -c . "$KEI_BK_ROOT/sets-history.jsonl"; }

@test "S12 a schedule is written only when asked; without a key the person chooses; off keeps the sets" {
    # Loading the installer and reading the status write nothing.
    run lib "kei_set_schedule_status"
    [ "$(field cron "$output")" = no ] && [ ! -e "$KEI_SET_CRON" ]
    # No key and Koha here: not scheduled until the person chooses.
    run lib "kei_set_schedule time=02:15 dest='$OUT' keep=3"
    [ "$status" -eq 7 ] && [ "$(field needs "$output")" = key ] && [ ! -e "$KEI_SET_CRON" ]
    for bad in "time=25:00 dest='$OUT'" "time=02:15 dest=relative" "time=02:15 dest='$T/none'" "time=02:15 dest='$OUT' keep=0" "time=02:15 dest='$OUT' secrets=no copy=nope:x"; do
        run lib "kei_set_schedule $bad"
        [ "$status" -ne 0 ] && [ ! -e "$KEI_SET_CRON" ] || { echo "$bad: $status"; false; }
    done
    # A cloud copy needs the backup key: never in clear.
    printf '[loc]\ntype = local\n' > "$RCLONE_CONFIG"
    run lib "kei_set_schedule time=02:15 dest='$OUT' secrets=no copy=loc:$T/cloud"
    [ "$status" -eq 6 ] && [ ! -e "$KEI_SET_CRON" ]
    run lib "kei_set_schedule time=02:15 dest='$OUT' keep=3 secrets=no"
    [ "$status" -eq 0 ]
    [ "$(grep -c -- '--task set-run scheduled' "$KEI_SET_CRON")" = 1 ]
    [ "$(grep -vc '^#\|^[A-Z]*=\|^$' "$KEI_SET_CRON")" = 1 ]
    grep -q '^15 2 \* \* \* root ' "$KEI_SET_CRON"
    [ "$(grep -c "koha-nexus-backup-sets" "$KEI_OWNED_DIR/owned.tsv")" = 2 ]
    # Asked again: still one line (never a second schedule).
    lib "kei_set_schedule time=03:00 secrets=no" >/dev/null
    [ "$(grep -c -- '--task set-run' "$KEI_SET_CRON")" = 1 ] && grep -q '^0 3 ' "$KEI_SET_CRON"
    run lib "kei_set_schedule_status"
    [ "$(field schedule "$output")" = 03:00 ] && [ "$(field dest "$output")" = "$OUT" ] && [ "$(field keep "$output")" = 3 ]
    [ "$(field secrets "$output")" = no ]
    lib "kei_set_run scheduled" >/dev/null
    run lib "kei_set_schedule time=off"
    [ "$status" -eq 0 ] && [ ! -e "$KEI_SET_CRON" ]
    [ -z "$(grep koha-nexus-backup-sets "$KEI_OWNED_DIR/owned.tsv")" ]
    [ -n "$(ls "$OUT"/knx-set-*.tar)" ]
}

@test "S13 scheduled runs: the same joint package, a history line each, retention only of its own sets" {
    lib "kei_set_backup '$OUT' '' no-secrets" >/dev/null           # a set made by hand
    manual=$(ls "$OUT"/knx-set-*.tar)
    lib "kei_set_schedule time=02:15 dest='$OUT' keep=2 secrets=no" >/dev/null
    for i in 1 2 3; do
        sleep 1
        run lib "kei_set_run scheduled"
        [ "$status" -eq 0 ] || { echo "$output"; false; }
    done
    [ "$(runs)" = 3 ]
    [ -f "$manual" ]                                                   # never removed
    [ "$(ls "$OUT"/knx-set-*.tar | grep -vc "$manual")" = 2 ]
    python3 -I - "$(history)" <<'PY'
import json, os, sys
runs = [json.loads(l) for l in sys.argv[1].splitlines()]
assert [r["result"] for r in runs] == ["ok", "ok", "ok"], runs
assert [r["removed"] for r in runs] == [0, 0, 1], runs
assert not os.path.exists(runs[0]["file"]) and all(os.path.exists(r["file"]) for r in runs[1:])
for r in runs:
    assert r["trigger"] == "scheduled" and r["recoverability"] == "partial" and r["copy"] == "none"
    assert [p["id"] for p in r["platforms"]] == ["koha", "tainacan"] and all(p["result"] == "ok" for p in r["platforms"])
PY
    run lib "kei_set_schedule_status"
    [[ "$(field last "$output")" == *"|ok|partial|none|" ]] && [ "$(field runs "$output")" = 3 ]
}

@test "S14 a platform that fails: partial, said per platform, nothing removed; busy: skipped and recorded" {
    lib "kei_set_schedule time=02:15 dest='$OUT' keep=1 secrets=no" >/dev/null
    lib "kei_set_run scheduled" >/dev/null
    sleep 1
    FAKE_TN_DUMP=fail run lib "kei_set_run scheduled"
    [ "$status" -eq 9 ]
    [ "$(ls "$OUT"/knx-set-*.tar | wc -l)" = 2 ]                       # retention waits for a complete set
    run lib "kei_set_schedule_status"
    [[ "$(field last "$output")" == *"|partial|"*"tainacan: The Tainacan database is not running."* ]]
    FAKE_TN_DUMP=fail FAKE_KOHA_DUMP=fail run lib "kei_set_run scheduled"
    [ "$status" -eq 9 ]
    [[ "$(history | tail -n 1)" == *'"result": "failed"'* ]]
    # Another run holds the lock: this one is skipped, recorded, and makes nothing.
    n=$(ls "$OUT" | wc -l)
    ( exec 8>"$KEI_BK_ROOT/.sets.lock"; flock 8; sleep 5 ) &
    sleep 1
    run lib "kei_set_run scheduled"
    [ "$status" -eq 9 ] && [[ "$output" == *"Another joint backup is running"* ]]
    [[ "$(history | tail -n 1)" == *'"result": "busy"'* ]] && [ "$(ls "$OUT" | wc -l)" = "$n" ]
    wait
}

@test "S15 the cloud copy is the whole set encrypted with the backup key, never in clear" {
    printf '[loc]\ntype = local\n' > "$RCLONE_CONFIG"
    mkdir -p "$T/cloud"
    lib "KEI_BACKUP_PHRASE=TEST-PHRA-SE12-3456-7890-ABCD kei_backup_setup confirm" >/dev/null
    run lib "kei_set_schedule time=02:15 dest='$OUT' keep=2 copy=loc:$T/cloud"
    [ "$status" -eq 0 ]
    run lib "kei_set_run scheduled"
    [ "$status" -eq 0 ] && [ "$(field copy "$output")" = ok ]
    up=$(ls "$T"/cloud/knx-set-*.tar.gpg)
    [ -z "$(ls "$T/cloud" | grep -v '\.tar\.gpg$')" ]
    never tar -tf "$up"
    never grep -aqE 'koha-db-pass|sip-secret|vision-secret|z-secret|OLD-key|CREATE TABLE|s3cr3t' "$up"
    [ -z "$(ls -A "$OUT" | grep '^\.')" ]                             # no clear or encrypted leftovers
    [[ "$(history | tail -n 1)" == *'"copy": "ok"'* ]] && [[ "$(history | tail -n 1)" == *'"recoverability": "full"'* ]]
    # The key is gone afterwards: the copy cannot be rescheduled without it,
    # and the scheduled run stops (Koha's secrets would be left out): failed,
    # never "done", and nothing goes to the cloud.
    rm -rf "$KEI_OWNED_DIR/backup/gnupg"
    run lib "kei_set_schedule time=02:15 secrets=no"
    [ "$status" -eq 6 ]
    sleep 1
    run lib "kei_set_run scheduled"
    [ "$status" -ne 0 ]
    [[ "$(history | tail -n 1)" == *'"result": "failed"'*"backup key"* ]]
    [ "$(ls "$T"/cloud/ | wc -l)" = 1 ]
}

@test "DS01 explicit DSpace capture uses format 2 and carries its encrypted package, legacy default stays two platforms" {
    run lib "
_kei_bk_has_key() { return 0; }
kei_dspace_runtime() {
    printf cipher > '$T/knx-dspace-20261108-000000-abcd1234.tar.gpg'
    printf '{\"package\":\"$T/knx-dspace-20261108-000000-abcd1234.tar.gpg\"}'
}
kei_set_backup '$OUT' dspace"
    [ "$status" -eq 0 ]
    SET=$(field file "$output")
    [[ "$output" == *$'platform=dspace\tok\t'* ]]
    tar -tf "$SET" | grep -q '^dspace/knx-dspace-.*\.tar\.gpg$'
    m=$(manifest "$SET")
    python3 -I - "$m" <<'PY'
import json,sys
x=json.loads(sys.argv[1]);assert x['format']==2 and x['complete'] is True
assert x['recoverability']=='full' and [r['id'] for r in x['platforms']]==['dspace']
PY
    run lib "kei_set_inspect '$SET'"
    [ "$status" -eq 0 ]
    [ "$(field integrity "$output")" = ok ]
    [ "$(field platforms "$output")" = dspace ]
    run lib "kei_set_unpack '$SET'"
    [ "$status" -eq 0 ]
    [ -f "$(field dspace "$output")" ]
    run lib "kei_set_platforms"
    [ "$output" = 'koha tainacan' ]
}

@test "DS02 missing DSpace encryption key refuses the whole set before any capture" {
    run lib "_kei_bk_has_key() { return 1; }; create_safety_backup() { touch '$T/should-not-exist'; }; kei_set_backup '$OUT' koha,dspace no-secrets"
    [ "$status" -eq 7 ]
    [ ! -e "$T/should-not-exist" ]
    [ "$(field needs "$output")" = key ]
}
