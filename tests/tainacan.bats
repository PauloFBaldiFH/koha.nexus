#!/usr/bin/env bats
# Tainacan (installer: kei_tainacan_*), the parts that need no Docker: the
# generated files, the address, the plan's refusals, the check of the
# plugin package against the published checksums, the safety checks of a
# backup before a restore, and the platforms entry. The installation
# itself runs in tests/tainacan_system.bats.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_TAINACAN_DIR="$T/owned/platforms/tainacan" KEI_TAINACAN_BACKUPS="$T/backups"
    export KEI_APACHE_DIR="$T/apache"
    mkdir -p "$KEI_APACHE_DIR/sites-enabled" "$T/bin"
    # No docker on PATH: these tests never reach a real one.
    for c in bash sh awk sed grep cat mkdir mktemp mv rm chmod cp tr head tail cut sort uniq printf date stat \
             sha256sum gzip tar python3 ss ip find wc id ls dirname basename env timeout flock comm diff hostname df seq; do
        p=$(command -v "$c" 2>/dev/null) && ln -sf "$p" "$T/bin/$c"
    done
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
PATH='$T/bin'
$1" 3>&-
}

@test "compose.yml: images by digest, port only on 127.0.0.1, labels, no-new-privileges, no secret" {
    run lib 'kei_tainacan_write_files && cat "$KEI_TAINACAN_DIR/compose.yml"'
    [ "$status" -eq 0 ]
    [ "$(grep -c '@sha256:[0-9a-f]\{64\}' <<< "$output")" = 3 ]
    grep -q '"127.0.0.1:${KN_PORT}:80"' <<< "$output"
    [ "$(grep -c 'ports:' <<< "$output")" = 1 ]
    grep -q 'no-new-privileges:true' <<< "$output"
    grep -q 'com.koha-nexus.platform: "tainacan"' <<< "$output"
    grep -q 'AUTOMATIC_UPDATER_DISABLED' <<< "$output"
    nope() { ! "$@"; }
    # Secrets only in .env (600), referenced by name.
    pw=$(grep '^KN_DB_PASSWORD=' "$KEI_TAINACAN_DIR/.env" | cut -d= -f2)
    [ "${#pw}" = 32 ]
    run grep -c "$pw" "$KEI_TAINACAN_DIR/compose.yml"
    [ "$output" = 0 ]
    [ "$(stat -c %a "$KEI_TAINACAN_DIR/.env")" = 600 ]
    [ "$(stat -c %a "$KEI_TAINACAN_DIR")" = 700 ]
    # Written again, the passwords stay (a kept database knows them).
    lib 'kei_tainacan_write_files'
    [ "$(grep '^KN_DB_PASSWORD=' "$KEI_TAINACAN_DIR/.env" | cut -d= -f2)" = "$pw" ]
}

@test "the restore-test copy: no port, its own names, the e-mail interceptor, WP-Cron off" {
    run lib '_kei_tn_compose rt'
    [ "$status" -eq 0 ]
    [ "$(grep -c 'ports:' <<< "$output")" = 0 ]
    grep -q '^name: kn-tainacan-rt$' <<< "$output"
    grep -q 'name: kn-tainacan-rt-db' <<< "$output"
    [ "$(grep -c 'kn-restore-test.php:/var/www/html/wp-content/mu-plugins/' <<< "$output")" = 2 ]
    [ "$(grep -c 'KN_RESTORE_TEST: "1"' <<< "$output")" = 2 ]
    grep -q "DISABLE_WP_CRON" <<< "$output"
    run lib '_kei_tn_nomail_plugin'
    grep -q "pre_wp_mail" <<< "$output"
}

@test "addresses: name, LAN address with port, and what is refused" {
    run lib 'kei_tainacan_parse_url http://acervo.exemplo.org'
    [ "$output" = "http acervo.exemplo.org 80" ]
    run lib 'kei_tainacan_parse_url https://acervo.exemplo.org/'
    [ "$output" = "https acervo.exemplo.org 443" ]
    run lib 'kei_tainacan_parse_url http://192.168.0.10:8090'
    [ "$output" = "http 192.168.0.10 8090" ]
    run lib '_kei_tn_hostport http://192.168.0.10:8090'
    [ "$output" = "192.168.0.10:8090" ]
    for bad in ftp://x.org http://x.org/wp "http://x.org:99999" "http://x y.org" http://UPPER.org "javascript:x"; do
        run lib "kei_tainacan_parse_url '$bad'"
        [ "$status" -eq 2 ]
    done
}

@test "the Apache site: by name on 80, or on its own port with Listen; proxy to 127.0.0.1" {
    run lib '_kei_tn_apache_site http://acervo.exemplo.org host 18090'
    [[ "${lines[0]}" == "<VirtualHost *:80>" ]]
    grep -q 'ServerName acervo.exemplo.org' <<< "$output"
    grep -q 'ProxyPass / http://127.0.0.1:18090/' <<< "$output"
    run lib '_kei_tn_apache_site http://192.168.0.10:8090 lan 18090'
    [ "${lines[0]}" = "Listen 8090" ]
    [ "${lines[1]}" = "<VirtualHost *:8090>" ]
}

@test "Apache's view: a port only the platform's site uses is left out, any other is compared" {
    map=$(printf '%s\n' \
        'default 80 /etc/apache2/sites-enabled/library.conf' \
        'vhost 80 catalog.kei.test /etc/apache2/sites-enabled/library.conf' \
        'default 8090 /etc/apache2/sites-enabled/zz-koha-nexus-tainacan.conf')
    run lib "printf '%s\n' '$map' | _kei_proxy_view zz-koha-nexus-tainacan.conf"
    [ "${#lines[@]}" -eq 2 ]
    [[ "$output" != *8090* ]]
    # Becoming the default server of a port someone else uses is not hidden.
    map2=$(printf '%s\n' \
        'default 80 /etc/apache2/sites-enabled/zz-koha-nexus-tainacan.conf' \
        'vhost 80 catalog.kei.test /etc/apache2/sites-enabled/library.conf')
    run lib "printf '%s\n' '$map2' | _kei_proxy_view zz-koha-nexus-tainacan.conf"
    [ "${#lines[@]}" -eq 2 ]
}

@test "plan: refused without Docker, and nothing is installed without confirm" {
    run lib 'kei_tainacan_plan http://acervo.exemplo.org'
    [ "$status" -eq 3 ]
    [ "${lines[0]}" = "$(printf 'plan\trefuse')" ]
    [[ "$output" == *"Docker is not installed"* ]]
    run lib 'kei_tainacan_install'
    [ "$status" -eq 3 ]
    [ ! -e "$KEI_TAINACAN_DIR/state" ]
    run lib 'kei_tainacan_uninstall'
    [ "$status" -eq 2 ]
    run lib 'kei_tainacan_uninstall keep'
    [ "$status" -eq 3 ]
}

# A plugin package and its checksums, in the format wordpress.org uses.
mkplugin() {
    python3 -I - "$T" "$@" <<'EOF'
import hashlib, json, sys, zipfile
t, mode = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "good"
files = {"tainacan.php": b"<?php /* Version: 1.4.1 */", "assets/a.css": b"body{}"}
sums = {k: {"md5": hashlib.md5(v).hexdigest(), "sha256": hashlib.sha256(v).hexdigest()} for k, v in files.items()}
z = zipfile.ZipFile(t + "/p.zip", "w")
for k, v in files.items():
    if mode == "changed" and k == "assets/a.css":
        v = b"body{display:none}"
    z.writestr("tainacan/" + k, v)
if mode == "extra":
    z.writestr("tainacan/backdoor.php", b"<?php eval($_GET['x']);")
if mode == "outside":
    z.writestr("other/x.php", b"x")
if mode == "missing":
    z.close(); z = zipfile.ZipFile(t + "/p.zip", "w"); z.writestr("tainacan/tainacan.php", files["tainacan.php"])
z.close()
json.dump({"plugin": "tainacan", "version": "1.4.1", "files": sums}, open(t + "/p.json", "w"))
EOF
}

@test "plugin package: accepted only when every file matches the published checksums" {
    mkplugin good
    run lib "kei_tainacan_verify_plugin '$T/p.zip' '$T/p.json' 1.4.1"
    [ "$status" -eq 0 ]
    [ "$output" = "ok 2 files" ]
    run lib "kei_tainacan_verify_plugin '$T/p.zip' '$T/p.json' 1.4.2"
    [ "$status" -eq 1 ]
    for mode in changed extra outside missing; do
        mkplugin "$mode"
        run lib "kei_tainacan_verify_plugin '$T/p.zip' '$T/p.json' 1.4.1"
        echo "$mode: $output"
        [ "$status" -eq 1 ]
    done
    printf 'not json' > "$T/p.json"
    run lib "kei_tainacan_verify_plugin '$T/p.zip' '$T/p.json' 1.4.1"
    [ "$status" -eq 1 ]
}

# A backup directory as kei_tainacan_backup writes it.
mkbackup() {
    local d="$KEI_TAINACAN_BACKUPS/knx-tainacan-$1" wpv="${2:-7.1.4}" plv="${3:-1.4.1}"
    mkdir -p "$d/secrets" "$T/tree/wp-content/uploads"
    echo '<?php' > "$T/tree/index.php"
    tar -C "$T/tree" -czf "$d/files.tar.gz" .
    echo 'CREATE TABLE x (a int);' | gzip > "$d/db.sql.gz"
    echo 'KN_PORT=18090' > "$d/secrets/.env"; : > "$d/secrets/compose.yml"; : > "$d/secrets/state"
    cat > "$d/manifest.json.tmp" <<EOF
{
  "format": 1,
  "platform": "tainacan",
  "created": "2026-11-05 ${1:9:2}:${1:11:2}:00",
  "label": "manual",
  "url": "http://acervo.exemplo.org",
  "wordpress_version": "$wpv",
  "tainacan_version": "$plv",
  "count_collections": 3,
  "count_items": 10,
  "count_attachments": 4,
  "attachments_missing": 0,
  "complete": true
}
EOF
    mv "$d/manifest.json.tmp" "$d/manifest.json"
    ( cd "$d" && sha256sum db.sql.gz files.tar.gz secrets/.env secrets/compose.yml secrets/state manifest.json > SHA256SUMS )
    printf '%s' "$d"
}

@test "backups: only complete ones are listed, newest first; manifest values" {
    a=$(mkbackup 20261105-100000); b=$(mkbackup 20261105-110000)
    mkdir -p "$KEI_TAINACAN_BACKUPS/knx-tainacan-20261105-120000"     # no manifest
    run lib 'kei_tainacan_backups | cut -f1'
    [ "${#lines[@]}" -eq 2 ]
    [ "${lines[0]}" = "$b" ]
    [ "$(lib "_kei_tn_manifest_get '$a' count_items")" = 10 ]
    [ "$(lib "_kei_tn_manifest_get '$a' url")" = "http://acervo.exemplo.org" ]
    [ "$(lib "_kei_tn_manifest_get '$a' complete")" = true ]
    run lib "_kei_tn_resolve latest"
    [ "$output" = "$b" ]
    run lib "_kei_tn_resolve ../../etc"
    [ "$status" -ne 0 ]
}

@test "restore safety: checksums, unsafe archive entries, newer versions, incomplete backups" {
    d=$(mkbackup 20261105-100000)
    run lib "kei_tainacan_backup_check '$d'"
    [ "$status" -eq 0 ]
    # A changed file.
    echo x >> "$d/secrets/.env"
    run lib "kei_tainacan_backup_check '$d'"
    [ "$status" -eq 4 ]
    # An archive with a way out, even with matching checksums.
    d=$(mkbackup 20261105-110000)
    python3 -I - "$d/files.tar.gz" <<'EOF'
import io, sys, tarfile
with tarfile.open(sys.argv[1], "w:gz") as tf:
    for name, kind in (("./index.php", "f"), ("../evil.php", "f"), ("./link", "l")):
        ti = tarfile.TarInfo(name)
        if kind == "l":
            ti.type = tarfile.SYMTYPE; ti.linkname = "/etc/passwd"; tf.addfile(ti)
        else:
            ti.size = 1; tf.addfile(ti, io.BytesIO(b"x"))
EOF
    ( cd "$d" && sha256sum db.sql.gz files.tar.gz secrets/.env secrets/compose.yml secrets/state manifest.json > SHA256SUMS )
    run lib "kei_tainacan_backup_check '$d'"
    [ "$status" -eq 4 ]
    run lib "kei_tainacan_check_tar '$d/files.tar.gz'"
    [[ "$output" == *"unsafe path: ../evil.php"* ]]
    [[ "$output" == *"link outside: ./link"* ]]
    # A backup of a newer version.
    d=$(mkbackup 20261105-120000 7.2.0)
    run lib "kei_tainacan_backup_check '$d'"
    [ "$status" -eq 6 ]
    d=$(mkbackup 20261105-130000 7.1.4 1.10.0)
    run lib "kei_tainacan_backup_check '$d'"
    [ "$status" -eq 6 ]
    # An older one is fine.
    d=$(mkbackup 20261105-140000 7.0.1 1.4.0)
    run lib "kei_tainacan_backup_check '$d'"
    [ "$status" -eq 0 ]
    # No manifest: never.
    rm "$d/manifest.json"
    run lib "kei_tainacan_backup_check '$d'"
    [ "$status" -eq 4 ]
}

@test "--status-json: Tainacan supported, absent until installed" {
    run lib 'kei_tainacan_json'
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys
d = json.load(sys.stdin)
assert d["id"] == "tainacan" and d["supported"] is True and d["detected"] is False, d
assert d["status"] == "absent" and d["health"] == "unknown", d'
    mkdir -p "$KEI_TAINACAN_DIR"; echo 'status=kept' > "$KEI_TAINACAN_DIR/state"
    run lib 'kei_tainacan_json'
    printf '%s' "$output" | python3 -c 'import json,sys
d = json.load(sys.stdin)
assert d["detected"] is False and d["status"] == "kept", d'
}

@test "the Tainacan tasks are not Koha tasks" {
    run lib 'kei_task_needs_koha tainacan-install'
    [ "$status" -eq 1 ]
    run lib 'kei_task_needs_koha tainacan-backup'
    [ "$status" -eq 1 ]
}
