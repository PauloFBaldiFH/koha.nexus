#!/usr/bin/env bats
# The common backup engine of the platforms (installer: kei_backup_*), on a
# real machine with a real Tainacan: the backup key and the recovery phrase,
# a crash inside the window without writes (WordPress started again, the
# capture done again whole), a crash after the capture (resume goes on from
# the next step), restic repositories (local and through rclone), a
# referenced package restored in isolation, an older backup restored by the
# monthly check, a restore with and without the phrase, the recovery kit on
# a server that lost its backup key, the copy to a cloud remote resumed, the
# schedule, and Koha's Apache (a stand-in) and someone else's Docker
# resources as they were.
#
# The cloud remote is a local rclone remote (type local): the same rclone
# copy and check, without an account.
#
# DESTRUCTIVE: installs packages, changes the firewall and Apache. It only
# runs with KEI_DESTRUCTIVE_TESTS=1, as root, under systemd, in a throwaway
# machine: tests/system/container.sh (CI: .github/workflows/proxy.yml).
# The tests depend on each other and run in order.

IMG="${KEI_TEST_IMAGE:-mirror.gcr.io/library/busybox:1.36}"
PHRASE="SYST-EMTE-STPH-RASE-2026-ABCD"

setup_file() {
    [ "${KEI_DESTRUCTIVE_TESTS:-}" = 1 ] || skip "destructive: set KEI_DESTRUCTIVE_TESTS=1 in a throwaway machine"
    [ "$(id -u)" = 0 ] || skip "needs root"
    [ -d /run/systemd/system ] || skip "needs systemd"
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
    install -m 755 "$REPO/installer" /usr/local/bin/config.sh
    export KEI_TAINACAN_REGISTRY="${KEI_TAINACAN_REGISTRY:-docker.io}"
    if curl -sfI --max-time 15 "https://downloads.wordpress.org/plugin-checksums/tainacan/1.4.1.json" >/dev/null 2>&1; then
        echo real > "$S/plugin"
    else
        [ "${KEI_REQUIRE_REAL_TAINACAN:-}" = 1 ] && { echo "wordpress.org unreachable and the real plugin is required" >&2; return 1; }
        "$REPO/tests/system/tainacan-stub/build.sh" "$S/stub"
        echo "test double (wordpress.org unreachable)" > "$S/plugin"
        export KEI_TAINACAN_PLUGIN_URL="file://$S/stub/tainacan.zip"
        export KEI_TAINACAN_CHECKSUMS_URL="file://$S/stub/checksums.json"
    fi
    # rclone comes with the panel's cloud connections; here, from the system.
    command -v rclone >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq rclone >/dev/null
    koha_apache
    lib 'kei_apache_vhost_map' > "$S/apache_before"
}

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
    TN=/var/lib/koha-nexus/platforms/tainacan
    BK=/var/lib/koha-nexus/backup
    # Many packages are made in one day here: keep them all (retention
    # itself is tested in tests/backup_engine.bats).
    export KEI_BK_KEEP_LAST=50
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
$1" 3>&-
}

nope() { ! "$@"; }

koha_apache() {
    mkdir -p /var/www/kei-opac /var/www/kei-staff
    echo OPAC > /var/www/kei-opac/index.html
    echo STAFF > /var/www/kei-staff/index.html
    grep -qE '^Listen 8080$' /etc/apache2/ports.conf || echo 'Listen 8080' >> /etc/apache2/ports.conf
    cat > /etc/apache2/sites-available/library.conf <<'EOF'
<VirtualHost *:80>
    ServerName catalog.kei.test
    DocumentRoot /var/www/kei-opac
</VirtualHost>
<VirtualHost *:8080>
    ServerName staff.kei.test
    DocumentRoot /var/www/kei-staff
</VirtualHost>
<Directory /var/www/kei-opac>
    Require all granted
</Directory>
<Directory /var/www/kei-staff>
    Require all granted
</Directory>
EOF
    a2dissite -q 000-default >/dev/null 2>&1 || true
    a2ensite -q library >/dev/null
    systemctl reset-failed apache2 2>/dev/null || true
    systemctl restart apache2
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        [ "$(curl -s http://127.0.0.1/)" = OPAC ] && return 0
        sleep 1
    done
    return 1
}

koha_answers_as_before() {
    [ "$(curl -s http://127.0.0.1/)" = OPAC ]
    [ "$(curl -s http://127.0.0.1:8080/)" = STAFF ]
    diff <(lib 'kei_apache_vhost_map' | grep -v 'zz-koha-nexus-tainacan') "$S/apache_before"
}

# seed_php NAME TITLE: a published collection and a published item, through
# the plugin's REST routes from inside WordPress (draft, then PATCH: see
# tests/tainacan_system.bats).
seed_php() {
    cat <<PHP
<?php
function kn_rest(\$m, \$path, \$body) {
    \$r = new WP_REST_Request(\$m, \$path);
    \$r->set_header("content-type", "application/json");
    \$r->set_body(json_encode(\$body));
    \$res = rest_do_request(\$r);
    if (\$res->get_status() >= 300) { fwrite(STDERR, \$m . " " . \$path . ": " . json_encode(\$res->get_data()) . "\n"); exit(1); }
    return \$res->get_data();
}
\$c = kn_rest("POST", "/tainacan/v2/collections", ["name" => "$1", "status" => "publish"]);
\$i = kn_rest("POST", "/tainacan/v2/collection/" . \$c["id"] . "/items", ["title" => "$2", "status" => "draft"]);
kn_rest("PATCH", "/tainacan/v2/items/" . \$i["id"], ["status" => "publish"]);
echo \$c["id"], " ", \$i["id"];
PHP
}

counts() { lib '_kei_tn_counts' | awk '{ print $1, $2, $3 }'; }
wp_cid() { docker ps -aq --filter label=com.docker.compose.project=kn-tainacan --filter label=com.docker.compose.service=wordpress; }
wp_running() { [ "$(docker inspect -f '{{.State.Running}}' "$(wp_cid)")" = true ]; }
wp_php() {
    printf '%s\n' "$1" > "$TN/work/t.php"
    chmod 644 "$TN/work/t.php"
    lib '_kei_tn_wp eval-file /work/t.php --user=knadmin'
}
steps() { grep -o '"step":"[a-z-]*"' "$1/journal.jsonl" | cut -d'"' -f4 | tr '\n' ' '; }
healthy() { for _ in $(seq 1 60); do lib 'kei_tainacan_health' >/dev/null 2>&1 && return 0; sleep 2; done; return 1; }

@test "before: Docker, Tainacan with real data, Koha's Apache and someone else's resources" {
    echo "Tainacan plugin: $(cat "$S/plugin")" >&3
    if ! command -v docker >/dev/null 2>&1; then
        run lib 'kei_docker_install confirm'
        [ "$status" -eq 0 ]
    fi
    docker network create someone-net >/dev/null
    docker volume create someone-data >/dev/null
    docker run -d --restart unless-stopped --name someone --network someone-net -v someone-data:/data "$IMG" sleep 3600 >/dev/null
    IP=$(lib 'get_server_ip')
    run lib "kei_tainacan_install confirm http://$IP:8090"
    [ "$status" -eq 0 ]
    python3 -c 'import base64,sys; open(sys.argv[1],"wb").write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))' "$TN/work/sample.png"
    chmod 644 "$TN/work/sample.png"
    run wp_php "$(seed_php "Acervo de teste" "Item 1")"
    [ "$status" -eq 0 ]
    read -r _ iid <<< "${lines[-1]}"
    run lib "_kei_tn_wp media import /work/sample.png --post_id=$iid --porcelain"
    [ "$status" -eq 0 ]
    [ "$(counts)" = "1 1 1" ]
    lib '_kei_tn_env KN_AUTH_SALT' > "$S/salt"
    [ -s "$S/salt" ]
    koha_answers_as_before
}

@test "setup: the key, restic installed, the phrase stored nowhere, the kit" {
    run lib 'kei_backup_setup'
    [ "$status" -eq 3 ]
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_setup confirm"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    command -v restic
    restic version >&3
    [ "$(stat -c %a "$BK")" = 700 ]
    [ "$(stat -c %a "$BK/recovery-kit.txt")" = 600 ]
    nope grep -rqF "$PHRASE" /var/lib/koha-nexus /etc /root /var/backups/koha-nexus /var/log
    run lib 'kei_backup_status tainacan'
    [[ "$output" == *"key="[0-9A-F]* ]]
}

@test "a crash inside the window without writes: WordPress started again and the capture done again whole" {
    run lib '_KEI_BK_CRASH_AFTER=db kei_tainacan_backup'
    [ "$status" -eq 137 ]
    B=$(ls -d /var/backups/koha-nexus/tainacan/knx-tainacan-* | tail -n 1)
    # The crash left the writers stopped, and the package is not offered.
    nope wp_running
    [ ! -f "$B/manifest.json" ]
    [ -z "$(lib 'kei_tainacan_backups')" ]
    run lib 'kei_backup_incomplete tainacan | cut -f2,3'
    [ "$output" = "$(printf 'db\tno')" ]
    run lib "kei_backup_resume '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    wp_running
    healthy
    [[ "$(steps "$B")" == "start capture writes-stopped db writes-resumed capture-restart capture writes-stopped db files writes-resumed capture-done resumed secrets manifest done " ]]
    grep -q '"step":"writes-resumed".*"reason":"recovered"' "$B/journal.jsonl"
    ( cd "$B" && sha256sum -c --quiet SHA256SUMS )
    [ -f "$B/secrets.tar.gpg" ] && [ ! -e "$B/secrets" ]
    [ "$(lib "_kei_tn_manifest_get '$B' count_items")" = 1 ]
    echo "$B" > "$S/pkg_self"
}

@test "a crash after the capture: resume goes on from the next step, the parts checked" {
    run lib '_KEI_BK_CRASH_AFTER=secrets kei_tainacan_backup'
    [ "$status" -eq 137 ]
    B=$(ls -d /var/backups/koha-nexus/tainacan/knx-tainacan-* | tail -n 1)
    [ "$B" != "$(cat "$S/pkg_self")" ]
    # The window was closed before the crash.
    wp_running
    sha=$(sha256sum "$B/db.sql.gz" | awk '{ print $1 }')
    run lib "kei_backup_resume '$B'"
    [ "$status" -eq 0 ]
    [[ "$(steps "$B")" == "start capture writes-stopped db files writes-resumed capture-done secrets resumed manifest done " ]]
    [ "$(sha256sum "$B/db.sql.gz" | awk '{ print $1 }')" = "$sha" ]
    ( cd "$B" && sha256sum -c --quiet SHA256SUMS )
    healthy
}

@test "restic, local repository: the package refers to a snapshot taken inside the window" {
    run lib 'kei_backup_repo tainacan local'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$BK/restic-tainacan.pass")" = 600 ]
    run lib 'kei_tainacan_backup'
    [ "$status" -eq 0 ]
    B="${lines[-1]}"
    [ -f "$B/files.ref.json" ] && [ ! -f "$B/files.tar.gz" ]
    [ "$(lib "_kei_bk_mget '$B' mode")" = ref ]
    [ "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["files"] > 0)' "$B/files.ref.json")" = True ]
    run lib 'kei_backup_list tainacan | head -n 1 | cut -f4'
    [ "$output" = ref ]
    # The snapshot was taken while WordPress was stopped.
    python3 - "$B/journal.jsonl" <<'PY'
import json, sys
steps = [json.loads(l)["step"] for l in open(sys.argv[1])]
assert steps.index("writes-stopped") < steps.index("files") < steps.index("writes-resumed"), steps
PY
    echo "$B" > "$S/pkg_ref"
    healthy
}

@test "the data changes after the backups" {
    run wp_php "$(seed_php "Segunda" "Item 2")"
    [ "$status" -eq 0 ]
    [ "$(counts)" = "2 2 1" ]
}

@test "the referenced package restored in isolation; a wrong phrase is refused" {
    B=$(cat "$S/pkg_ref")
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore_test '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    run lib "KEI_BACKUP_PHRASE=wrong-phrase-123 kei_tainacan_restore_test '$B'"
    [ "$status" -eq 7 ]
    # The staging area of restic is gone; the installation in use untouched.
    [ -z "$(ls -d "$BK"/stage.* 2>/dev/null)" ]
    [ "$(counts)" = "2 2 1" ]
}

@test "restore with the phrase: the data and the configuration of the backup come back" {
    lib "_kei_tn_env_set KN_AUTH_SALT changed-after-the-backup"
    B=$(cat "$S/pkg_ref")
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [[ "$output" == *"The configuration of the backup came back."* ]]
    [ "$(counts)" = "1 1 1" ]
    [ "$(lib '_kei_tn_env KN_AUTH_SALT')" = "$(cat "$S/salt")" ]
    [ "$(docker exec "$(wp_cid)" printenv WORDPRESS_AUTH_SALT)" = "$(cat "$S/salt")" ]
    [ ! -e "$TN/.env.before-restore" ]
    koha_answers_as_before
}

@test "restore without the phrase: the data comes back, this installation's configuration stays" {
    run wp_php "$(seed_php "Terceira" "Item 3")"
    [ "$(counts)" = "2 2 1" ]
    lib "_kei_tn_env_set KN_AUTH_SALT kept-from-this-installation"
    ( cd "$TN" && docker compose up -d wordpress >/dev/null 2>&1 )
    healthy
    B=$(cat "$S/pkg_self")
    run lib "kei_tainacan_restore '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [[ "$output" == *"Configuration kept from this installation"* ]]
    [ "$(counts)" = "1 1 1" ]
    [ "$(lib '_kei_tn_env KN_AUTH_SALT')" = kept-from-this-installation ]
    lib "_kei_tn_env_set KN_AUTH_SALT '$(cat "$S/salt")'"
    ( cd "$TN" && docker compose up -d wordpress >/dev/null 2>&1 )
    healthy
}

@test "restic through rclone: the snapshot in a remote, restored in isolation" {
    rclone config create loc local >/dev/null
    run lib 'kei_backup_repo tainacan rclone:loc:/srv/restic-tainacan'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    run lib 'kei_tainacan_backup'
    [ "$status" -eq 0 ]
    B="${lines[-1]}"
    grep -q '"repository": "rclone:loc:/srv/restic-tainacan"' "$B/files.ref.json"
    [ -f /srv/restic-tainacan/config ]
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore_test '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    echo "$B" > "$S/pkg_rclone"
}

@test "the monthly check: an older backup (its restic snapshot) restored in isolation" {
    # Thirty days from the moment of the local restic package: that one is
    # the newest one made at least thirty days before.
    old=$(cat "$S/pkg_ref")
    made=$(date -d "$(lib "_kei_bk_mget '$old' created")" +%s)
    run lib "_KEI_BK_NOW=$((made + 30 * 86400 + 5)) kei_backup_pick tainacan 30"
    [ "$output" = "$old" ]
    lib 'kei_backup_repo tainacan local' >/dev/null
    run lib "_KEI_BK_NOW=$((made + 30 * 86400 + 5)) kei_backup_verify tainacan 30"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    grep -q '"result": "ok"' "$old/verify.json"
    [[ "$(lib 'kei_backup_status tainacan')" == *"tainacan.verified="*"${old##*/} ok"* ]]
    run lib 'kei_backup_maintain tainacan'
    [ "$status" -eq 0 ]
    [ "$(counts)" = "1 1 1" ]
}

@test "a server without its backup key: the kit and the phrase read the packages again" {
    cp "$BK/recovery-kit.txt" "$S/kit.txt"
    nope grep -qF "$PHRASE" "$S/kit.txt"
    mv "$BK" "$S/lost-backup-dir"
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore_test '$(cat "$S/pkg_ref")'"
    [ "$status" -ne 0 ]
    run lib "KEI_BACKUP_PHRASE=wrong-phrase-123 kei_backup_kit_import '$S/kit.txt'"
    [ "$status" -eq 7 ]
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_kit_import '$S/kit.txt'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$BK/restic-tainacan.pass")" = 600 ]
    cmp "$BK/restic-tainacan.pass" "$S/lost-backup-dir/restic-tainacan.pass"
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore_test '$(cat "$S/pkg_ref")'"
    [ "$status" -eq 0 ]
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore_test '$(cat "$S/pkg_rclone")'"
    [ "$status" -eq 0 ]
    # The configuration of an encrypted package opens with the imported key.
    run lib "KEI_BACKUP_PHRASE='$PHRASE' _kei_bk_secrets_open '$(cat "$S/pkg_self")'"
    [ "$status" -eq 0 ]
    grep -q '^KN_AUTH_SALT=' "$output/.env"
    rm -rf "$output"
}

@test "the copy to a cloud remote: resumed after a crash, checked at the remote" {
    lib 'kei_backup_repo tainacan none' >/dev/null
    run lib 'kei_backup_copy tainacan loc:/srv/cloud'
    [ "$status" -eq 0 ]
    run lib '_KEI_BK_CRASH_AFTER=manifest kei_tainacan_backup'
    [ "$status" -eq 137 ]
    B=$(ls -d /var/backups/koha-nexus/tainacan/knx-tainacan-* | tail -n 1)
    wp_running
    [ ! -d "/srv/cloud/${B##*/}" ]
    run lib 'kei_backup_incomplete tainacan | cut -f2,3'
    [ "$output" = "$(printf 'manifest\tyes')" ]
    run lib "kei_backup_discard '$B'"
    [ "$status" -eq 3 ]
    run lib "kei_backup_resume '$B'"
    [ "$status" -eq 0 ]
    ( cd "/srv/cloud/${B##*/}" && sha256sum -c --quiet SHA256SUMS )
    [ -f "/srv/cloud/${B##*/}/secrets.tar.gpg" ] && [ ! -e "/srv/cloud/${B##*/}/secrets" ]
    nope grep -rq "$(lib '_kei_tn_env KN_DB_PASSWORD')" "/srv/cloud/${B##*/}"
    grep -q '"step":"copy"' "$B/journal.jsonl"
    lib 'kei_backup_copy tainacan none' >/dev/null
}

@test "schedule: one cron file, in the registry; the task runs a scheduled package" {
    run lib 'kei_backup_schedule tainacan 02:30'
    [ "$status" -eq 0 ]
    f=/etc/cron.d/koha-nexus-platform-backups
    [ "$(stat -c %a "$f")" = 644 ]
    grep -q '^30 2 \* \* \* root .* --task platform-backup-run tainacan scheduled' "$f"
    grep -q '^30 3 \* \* 0 root .* --task platform-backup-maintain tainacan' "$f"
    grep -q '^30 4 1 \* \* root .* --task platform-backup-verify tainacan 30' "$f"
    run lib 'kei_owned_list cron-file tainacan | cut -f2'
    [ "$output" = koha-nexus-platform-backups ]
    # What cron runs.
    run /usr/local/bin/config.sh --task platform-backup-run tainacan scheduled
    echo "$output" >&3
    [ "$status" -eq 0 ]
    run lib 'kei_backup_list tainacan | head -n 1 | cut -f3'
    [ "$output" = scheduled ]
    healthy
}

@test "uninstall deleting the data: the schedule goes, the backups stay; Koha and the others as before" {
    run lib 'kei_tainacan_uninstall delete'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ ! -e /etc/cron.d/koha-nexus-platform-backups ]
    run lib 'kei_owned_list "" tainacan'
    [ -z "$output" ]
    run lib 'kei_tainacan_backups | cut -f3'
    [[ "$output" == *final* ]]
    [ -f /var/backups/koha-nexus/restic/tainacan/config ]
    [ -f "$BK/recovery-kit.txt" ]
    [ "$(docker inspect -f '{{.State.Running}}' someone)" = true ]
    docker volume inspect someone-data >/dev/null
    docker network inspect someone-net >/dev/null
    systemctl is-active --quiet docker
    koha_answers_as_before
    docker rm -f someone >/dev/null; docker network rm someone-net >/dev/null; docker volume rm someone-data >/dev/null
}
