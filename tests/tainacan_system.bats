#!/usr/bin/env bats
# Tainacan in containers, on a real machine (installer: kei_tainacan_*):
# installation the way the panel does it, real data (a collection, an item,
# an attachment), the isolation of its containers, persistence across a
# Docker restart and recreated containers, a backup, a restore tested in an
# isolated copy (internal network, no port, e-mail intercepted, WP-Cron
# off) and then applied, a change of address, and uninstalling keeping and
# deleting the data. Koha's Apache (a stand-in), the host's services and
# someone else's Docker resources must stay as they were.
#
# The plugin is the real one from wordpress.org. Where wordpress.org cannot
# be reached (the cloud test machine), a test double of the plugin
# (tests/system/tainacan-stub) with the same REST routes is used instead,
# and the first test says so; CI sets KEI_REQUIRE_REAL_TAINACAN=1, so there
# the real plugin is mandatory.
#
# DESTRUCTIVE: installs packages, changes the firewall and Apache. It only
# runs with KEI_DESTRUCTIVE_TESTS=1, as root, under systemd, in a throwaway
# machine: tests/system/container.sh (CI: .github/workflows/proxy.yml).
# The tests depend on each other and run in order.

HOST_PORTS="3306 11211 9200"
IMG="${KEI_TEST_IMAGE:-mirror.gcr.io/library/busybox:1.36}"

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
    koha_apache
    lib 'kei_apache_vhost_map' > "$S/apache_before"
    for p in $HOST_PORTS; do
        setsid python3 -m http.server "$p" --bind 0.0.0.0 >/dev/null 2>&1 3>&- &
    done
    sleep 1
}

teardown_file() {
    pkill -f 'http.server' 2>/dev/null || true
}

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
    TN=/var/lib/koha-nexus/platforms/tainacan
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

# Koha's sites answer as before, and Apache's map of ports, names and
# default servers (kei_apache_vhost_map, the view the proxy code trusts)
# is the same once Tainacan's own site is left out. The raw apache2ctl -S
# text is not compared: Apache prints a port with one site and a port with
# several names in different shapes, with the same meaning.
koha_answers_as_before() {
    [ "$(curl -s http://127.0.0.1/)" = OPAC ]
    [ "$(curl -s http://127.0.0.1:8080/)" = STAFF ]
    diff <(lib 'kei_apache_vhost_map' | grep -v 'zz-koha-nexus-tainacan') "$S/apache_before"
}

# seed_php NAME TITLE: PHP that creates a published collection and a
# published item through the plugin's REST routes, called from inside
# WordPress (rest_do_request), the way Tainacan's own admin does it: the item
# is created as a draft and then published with PATCH (Tainacan 1.4.1
# refuses a POST that publishes an item directly: "Entities must be
# validated before you can save them"). A refused call stops with its
# answer on stderr. Prints "COLLECTION_ID ITEM_ID".
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

tn() { lib "$1"; }
counts() { lib '_kei_tn_counts' | awk '{ print $1, $2, $3 }'; }
wp_cid() { docker ps -q --filter label=com.docker.compose.project=kn-tainacan --filter label=com.docker.compose.service=wordpress; }
db_cid() { docker ps -q --filter label=com.docker.compose.project=kn-tainacan --filter label=com.docker.compose.service=db; }
# api URL HOSTHEADER: the collections API through Apache.
api() { curl -s --max-time 20 -H "Host: $2" "$1/?rest_route=/tainacan/v2/collections"; }
json_len() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d, list) else -1)'; }

# PHP run inside WordPress as the administrator (the real REST routes of
# the plugin, called from inside: rest_do_request).
wp_php() {
    printf '%s\n' "$1" > "$TN/work/t.php"
    chmod 644 "$TN/work/t.php"
    lib '_kei_tn_wp eval-file /work/t.php --user=knadmin'
}

@test "before: Koha's Apache, the host's services and someone else's Docker resources" {
    echo "Tainacan plugin: $(cat "$S/plugin")" >&3
    if ! command -v docker >/dev/null 2>&1; then
        run lib 'kei_docker_install confirm'
        [ "$status" -eq 0 ]
    fi
    docker network create someone-net >/dev/null
    docker volume create someone-data >/dev/null
    docker run -d --restart unless-stopped --name someone --network someone-net -v someone-data:/data "$IMG" sleep 3600 >/dev/null
    koha_answers_as_before
    # A server with Koha only: nothing of Tainacan shows, no address or
    # diagnosis made up.
    run config.sh --status-json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | grep '^{' | tail -n 1 | python3 -c 'import json,sys
d = json.load(sys.stdin)
t = [p for p in d["platforms"] if p["id"] == "tainacan"][0]
assert t["detected"] is False and t["status"] == "absent" and t["admin_url"] == "" and t["checked"] == {}, t'
    [ ! -e /var/lib/koha-nexus/platforms/tainacan/last-status ]
}

@test "plan, and nothing without confirm" {
    run lib 'kei_tainacan_plan'
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "$(printf 'plan\tinstall')" ]
    [[ "$output" == *"address"*":8090"* ]]
    run lib 'kei_tainacan_install'
    [ "$status" -eq 3 ]
    [ -z "$(docker ps -aq --filter label=com.koha-nexus.platform=tainacan)" ]
    [ ! -e "$TN/state" ]
}

@test "install, reached by address on the local network through Apache's own port" {
    IP=$(lib 'get_server_ip')
    run lib "kei_tainacan_install confirm http://$IP:8090"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(lib '_kei_tn_get status')" = installed ]
    [ "$(stat -c %a "$TN")" = 700 ]
    [ "$(stat -c %a "$TN/.env")" = 600 ]
    # No secret in compose.yml; images by digest; port only on 127.0.0.1.
    pw=$(lib '_kei_tn_env KN_DB_PASSWORD')
    nope grep -q "$pw" "$TN/compose.yml"
    [ "$(grep -c '@sha256:' "$TN/compose.yml")" = 3 ]
    [[ "$(docker port "$(wp_cid)")" == "80/tcp -> 127.0.0.1:"* ]]
    [ -z "$(docker port "$(db_cid)")" ]
    run lib 'kei_docker_audit tainacan'
    [ "$status" -eq 0 ]
    # Apache: the site on its own port; Koha's sites as before.
    [ -L /etc/apache2/sites-enabled/zz-koha-nexus-tainacan.conf ]
    koha_answers_as_before
    [ "$(api "http://$IP:8090" "$IP:8090" | json_len)" = 0 ]
    run lib 'kei_owned_list "" tainacan | cut -f1,2'
    [[ "$output" == *"apache-site"*"zz-koha-nexus-tainacan.conf"* ]]
    [[ "$output" == *"ufw-port"*"8090"* ]]
    [[ "$output" == *"docker-network"*"kn-tainacan"* ]]
    # Automatic updates off.
    [ "$(lib "_kei_tn_wp eval 'echo AUTOMATIC_UPDATER_DISABLED ? \"off\" : \"on\";'")" = off ]
}

@test "real data: a collection, an item and an attachment, seen by the API" {
    python3 -c 'import base64,sys; open(sys.argv[1],"wb").write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))' "$TN/work/sample.png"
    chmod 644 "$TN/work/sample.png"
    run wp_php "$(seed_php "Acervo de teste" "Item 1")"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    read -r cid iid <<< "${lines[-1]}"
    [ -n "$iid" ] && [ "$iid" -gt 0 ]
    run lib "_kei_tn_wp media import /work/sample.png --post_id=$iid --porcelain"
    [ "$status" -eq 0 ]
    [ "$(counts)" = "1 1 1" ]
    IP=$(lib 'get_server_ip')
    [ "$(api "http://$IP:8090" "$IP:8090" | json_len)" = 1 ]
    run lib 'kei_tainacan_health'
    [ "$status" -eq 0 ]
    run lib 'kei_tainacan_status'
    [[ "$output" == *"health=healthy"* ]]
    [[ "$output" == *"attachments_missing=0"* ]]
}

@test "the diagnosis kept for the panel matches the database, with no secret, and --status-json shows it" {
    run lib 'kei_tainacan_check'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [[ "$output" == *"result=ok"* ]]
    f="$TN/last-status"
    [ "$(stat -c '%a %U' "$f")" = "600 root" ]
    read -r c i a <<< "$(counts)"
    grep -qx "collections=$c" "$f"
    grep -qx "items=$i" "$f"
    grep -qx "attachments=$a" "$f"
    grep -Eqx 'checked_at=[0-9]+' "$f"
    # None of the passwords of .env, nor anything named like a secret.
    while IFS= read -r pw; do
        [ -n "$pw" ] || continue
        run grep -cF "$pw" "$f"
        [ "$output" = 0 ]
    done < <(awk -F= '/^KN_.*(PASSWORD|KEY|SALT)=/ { print substr($0, index($0, "=") + 1) }' "$TN/.env")
    run grep -Eci '^[a-z_]*(pass|key|token|secret|link)' "$f"
    [ "$output" = 0 ]
    run config.sh --status-json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | grep '^{' | tail -n 1 | C="$c" I="$i" python3 -c 'import json,os,sys
d = json.load(sys.stdin)
t = [p for p in d["platforms"] if p["id"] == "tainacan"][0]
assert t["admin_url"].endswith("/wp-admin/") and t["admin_url"].startswith(t["url"].rstrip("/")), t
assert t["checked"]["collections"] == os.environ["C"] and t["checked"]["items"] == os.environ["I"], t
assert t["checked"]["checked_at"].isdigit() and t["checked"]["failed_at"] == "", t'
}

@test "isolation: Tainacan's containers cannot reach the host's services" {
    gw=$(docker network inspect -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}' kn-tainacan)
    for p in $HOST_PORTS; do
        run docker exec "$(wp_cid)" curl -s -o /dev/null --max-time 3 "http://$gw:$p/"
        [ "$status" -ne 0 ]
    done
    # Control: the services are there (the host reaches them).
    curl -s -o /dev/null --max-time 3 "http://$gw:3306/"
    # Its database is published nowhere.
    [ -z "$(docker port "$(db_cid)")" ]
}

@test "persistence: the data survives a Docker restart and recreated containers" {
    systemctl restart docker
    for _ in $(seq 1 90); do lib 'kei_tainacan_health' >/dev/null 2>&1 && break; sleep 2; done
    [ "$(counts)" = "1 1 1" ]
    iptables -S KN-INPUT | grep -q kn-tainacan
    ( cd "$TN" && docker compose up -d --force-recreate db wordpress >/dev/null 2>&1 )
    for _ in $(seq 1 90); do lib 'kei_tainacan_health' >/dev/null 2>&1 && break; sleep 2; done
    [ "$(counts)" = "1 1 1" ]
    run lib 'kei_tainacan_health'
    [ "$status" -eq 0 ]
}

@test "backup: every writer stopped, manifest, checksums, permissions" {
    run lib 'kei_tainacan_backup'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    B="${lines[-1]}"
    echo "$B" > "$S/backup1"
    [ -f "$B/manifest.json" ] && [ -f "$B/db.sql.gz" ] && [ -f "$B/files.tar.gz" ]
    ( cd "$B" && sha256sum -c --quiet SHA256SUMS )
    [ "$(stat -c %a "$B")" = 700 ]
    [ "$(stat -c %a "$B/secrets/.env")" = 600 ]
    [ "$(lib "_kei_tn_manifest_get '$B' count_collections")" = 1 ]
    [ "$(lib "_kei_tn_manifest_get '$B' count_items")" = 1 ]
    [ "$(lib "_kei_tn_manifest_get '$B' count_attachments")" = 1 ]
    [ "$(lib "_kei_tn_manifest_get '$B' attachments_missing")" = 0 ]
    echo "window without writes: $(lib "_kei_tn_manifest_get '$B' window_seconds") s" >&3
    # The journal: writes stopped before the dump, resumed after the files.
    [ "$(grep -o '"step":"[a-z-]*"' "$B/journal.jsonl" | cut -d'"' -f4 | tr '\n' ' ')" = 'start capture writes-stopped db files writes-resumed capture-done secrets manifest done ' ]
    run lib 'kei_tainacan_health'
    [ "$status" -eq 0 ]
    # A directory without manifest.json is never offered.
    mkdir -p /var/backups/koha-nexus/tainacan/knx-tainacan-99999999-000000
    run lib 'kei_tainacan_backups'
    [ "${#lines[@]}" -eq 1 ]
    rmdir /var/backups/koha-nexus/tainacan/knx-tainacan-99999999-000000
}

@test "the data changes after the backup" {
    run wp_php "$(seed_php "Segunda" "Item 2")"
    [ "$status" -eq 0 ]
    [ "$(counts)" = "2 2 1" ]
}

@test "restore test: an isolated copy, with no way out, and the installation in use untouched" {
    B=$(cat "$S/backup1")
    run lib "KEI_TAINACAN_KEEP_RT=1 kei_tainacan_restore_test '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    # While it is kept: an internal network, no published port, WP-Cron off.
    [ "$(docker network inspect -f '{{.Internal}}' kn-tainacan-rt)" = true ]
    for c in $(docker ps -q --filter label=com.docker.compose.project=kn-tainacan-rt); do
        [ -z "$(docker port "$c")" ]
    done
    [ "$(lib "_kei_tn_wp rt eval 'echo (defined(\"DISABLE_WP_CRON\") && DISABLE_WP_CRON) ? \"off\" : \"on\";'")" = off ]
    [ "$(lib "_kei_tn_wp rt eval 'echo has_filter(\"pre_wp_mail\") && !wp_mail(\"x@example.invalid\", \"t\", \"t\") ? \"blocked\" : \"sent\";'")" = blocked ]
    rtc=$(docker ps -q --filter label=com.docker.compose.project=kn-tainacan-rt --filter label=com.docker.compose.service=wordpress)
    run docker exec "$rtc" curl -s -o /dev/null --max-time 5 https://wordpress.org/
    [ "$status" -ne 0 ]
    # The copy cannot reach the platform in use either.
    run docker exec "$rtc" curl -s -o /dev/null --max-time 3 "http://$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$(wp_cid)")/"
    [ "$status" -ne 0 ]
    # The installation in use did not notice.
    [ "$(counts)" = "2 2 1" ]
    lib '_kei_tn_rt_down'
    [ -z "$(docker ps -aq --filter label=com.docker.compose.project=kn-tainacan-rt)" ]
    nope docker network inspect kn-tainacan-rt
    nope docker volume inspect kn-tainacan-rt-db
    run lib 'kei_owned_list docker-network | cut -f2'
    [ "$output" = kn-tainacan ]
}

@test "restore: back to the backup, after a safety backup" {
    B=$(cat "$S/backup1")
    run lib "kei_tainacan_restore '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(counts)" = "1 1 1" ]
    run lib 'kei_tainacan_health'
    [ "$status" -eq 0 ]
    run lib 'kei_tainacan_backups | cut -f3'
    [[ "$output" == *pre-restore* ]]
    safety=$(lib 'kei_tainacan_backups' | awk -F'\t' '$3 == "pre-restore" { print $1; exit }')
    [ "$(lib "_kei_tn_manifest_get '$safety' count_collections")" = 2 ]
    koha_answers_as_before
}

@test "a new address, with a name of its own" {
    run lib 'kei_tainacan_address http://tainacan.kei.test'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(curl -s --max-time 20 --resolve tainacan.kei.test:80:127.0.0.1 'http://tainacan.kei.test/?rest_route=/tainacan/v2/collections' | json_len)" = 1 ]
    [ "$(lib "_kei_tn_wp option get home")" = http://tainacan.kei.test ]
    nope grep -q 'Listen 8090' /etc/apache2/sites-available/zz-koha-nexus-tainacan.conf
    run lib 'kei_owned_list ufw-port tainacan | cut -f2'
    [ "$output" = 80 ]
    koha_answers_as_before
}

@test "administrative access: your own password on stdin only, another administrator, the keys unchanged" {
    # A new installation started the steps after it.
    [ -f /var/lib/koha-nexus/setup/tainacan.state ]
    [ "$(stat -c %a /var/lib/koha-nexus/setup/tainacan.state)" = 600 ]
    run lib 'kei_tainacan_admin_status'
    [ "$status" -eq 0 ]
    [[ "$output" == *state=initial* ]]
    user=$(lib '_kei_tn_env KN_ADMIN_USER')
    keys=$(lib "_kei_tn_wp eval 'echo md5(AUTH_KEY . SECURE_AUTH_KEY . LOGGED_IN_SALT . NONCE_SALT);'")
    PW='Sys-Test-Pass-2026'
    printf '%s\n' "$PW" > "$S/pw"
    # While it runs, no process may carry the password on its command line.
    ( for _ in $(seq 1 600); do grep -a -l -F -f "$S/pw" /proc/[0-9]*/cmdline 2>/dev/null; sleep 0.05; done ) > "$S/seen" &
    watch=$!
    export KEI_ADMIN_PASSWORD="$PW"
    run lib "kei_tainacan_admin_password '$user'"
    unset KEI_ADMIN_PASSWORD
    kill "$watch" 2>/dev/null || true; wait "$watch" 2>/dev/null || true
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ ! -s "$S/seen" ] || { cat "$S/seen" >&3; false; }
    [[ "$output" != *"$PW"* ]]
    nope grep -rqF -f "$S/pw" /var/log/koha-easy-install "$TN/.env" 2>/dev/null
    nope grep -q KN_ADMIN_PASSWORD "$TN/.env"
    [ "$(printf '%s\n' "$PW" | lib "_kei_tn_wp eval '\$pw = rtrim((string) fgets(STDIN), \"\\n\"); \$u = get_user_by(\"login\", \$args[0]); echo wp_check_password(\$pw, \$u->user_pass, \$u->ID) ? \"yes\" : \"no\";' '$user'")" = yes ]
    [ "$(lib "_kei_tn_wp eval 'echo md5(AUTH_KEY . SECURE_AUTH_KEY . LOGGED_IN_SALT . NONCE_SALT);'")" = "$keys" ]
    run lib 'kei_tainacan_admin_status'
    [[ "$output" == *state=own* ]]
    run lib 'kei_setup_status tainacan'
    [[ "$output" == *"step=admin|done|"* ]]
    # Another administrator; never over an existing name.
    export KEI_ADMIN_PASSWORD="$PW"
    run lib "kei_tainacan_admin_create ana ana@kei.test"
    [ "$status" -eq 0 ]
    run lib "kei_tainacan_admin_create '$user' other@kei.test"
    unset KEI_ADMIN_PASSWORD
    [ "$status" -eq 5 ]
    [ "$(lib "_kei_tn_wp user get ana --field=roles")" = administrator ]
    run lib 'kei_setup_close tainacan'
    [ ! -e /var/lib/koha-nexus/setup/tainacan.state ]
}

@test "uninstall keeping the data, then install again with the same data" {
    pw=$(lib '_kei_tn_env KN_ADMIN_PASSWORD')
    run lib 'kei_tainacan_uninstall keep'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ -z "$(docker ps -aq --filter label=com.koha-nexus.platform=tainacan)" ]
    docker volume inspect kn-tainacan-db kn-tainacan-wp >/dev/null
    [ ! -e /etc/apache2/sites-enabled/zz-koha-nexus-tainacan.conf ]
    nope docker network inspect kn-tainacan
    koha_answers_as_before
    run lib 'kei_tainacan_install confirm http://tainacan.kei.test'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(counts)" = "1 1 1" ]
    [ "$(lib '_kei_tn_env KN_ADMIN_PASSWORD')" = "$pw" ]
    # An existing WordPress is not a new installation: no steps after it.
    [ ! -e /var/lib/koha-nexus/setup/tainacan.state ]
}

@test "uninstall deleting the data: a last backup first; Koha and the others stay" {
    run lib 'kei_tainacan_uninstall delete'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    nope docker volume inspect kn-tainacan-db
    nope docker volume inspect kn-tainacan-wp
    [ ! -e "$TN" ]
    run lib 'kei_owned_list "" tainacan'
    [ -z "$output" ]
    # The backups stay, the last one included.
    run lib 'kei_tainacan_backups | cut -f3'
    [[ "$output" == *final* ]]
    # No platform network left: the isolation chains go with it.
    nope iptables -S KN-INPUT
    # Someone else's resources, Docker, Apache and Koha: as they were.
    [ "$(docker inspect -f '{{.State.Running}}' someone)" = true ]
    docker volume inspect someone-data >/dev/null
    docker network inspect someone-net >/dev/null
    systemctl is-active --quiet docker
    koha_answers_as_before
    docker rm -f someone >/dev/null; docker network rm someone-net >/dev/null; docker volume rm someone-data >/dev/null
}
