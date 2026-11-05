#!/usr/bin/env bats
# Events for Tainacan on a real machine, with the versions the installer
# uses (WordPress 7.1.4, PHP 8.3, MariaDB 11.8.9, Tainacan 1.4.1, Events
# Manager 7.4.13, Nexus Eventos from this repository): off until asked; an
# Events Manager already in the site kept and never turned off without an
# explicit "dependency"; the event edit screen drawn whole with Tainacan
# active (the "Nexus" box with its collections); passes, attendance and a
# certificate; pass keys redacted in the logs; a backup with events off
# that counts their data and a restore check that compares it; a restore
# without the recovery phrase that says pass links stop working (and they
# do), and with the phrase they keep working; a deleted booking takes its
# history with it; Events Manager installed from wordpress.org with every
# file matching the published checksums.
#
# Tainacan and Events Manager are the real ones from wordpress.org. Where
# wordpress.org cannot be reached (the cloud test machine), the Tainacan
# test double (tests/system/tainacan-stub) and the Events Manager 7.4.13
# files kept in nexus-events-plugin/bundled/ (with checksums made from
# them) are used instead, and the first test says so; CI sets
# KEI_REQUIRE_REAL_TAINACAN=1 and KEI_REQUIRE_REAL_EVENTS=1, so there the
# real packages and the published checksums are mandatory.
#
# Nexus Eventos comes from this checkout (KEI_EVENTS_SRC), checked file by
# file against the list in the installer, like the download from GitHub.
#
# DESTRUCTIVE: installs packages, changes the firewall and Apache. It only
# runs with KEI_DESTRUCTIVE_TESTS=1, as root, under systemd, in a throwaway
# machine: tests/system/container.sh (CI: .github/workflows/proxy.yml).
# The tests depend on each other and run in order.

IMG="${KEI_TEST_IMAGE:-mirror.gcr.io/library/busybox:1.36}"
PHRASE="EVEN-TSTE-STPH-RASE-2026-WXYZ"

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
    if curl -sfI --max-time 15 "https://downloads.wordpress.org/plugin-checksums/events-manager/7.4.13.json" >/dev/null 2>&1; then
        echo "real, from wordpress.org" > "$S/em"
    else
        [ "${KEI_REQUIRE_REAL_EVENTS:-}" = 1 ] && { echo "wordpress.org unreachable and the real Events Manager is required" >&2; return 1; }
        em_substitute "$S/em-sub"
        echo "files of nexus-events-plugin/bundled (wordpress.org unreachable)" > "$S/em"
        export KEI_EVENTS_EM_URL="file://$S/em-sub/events-manager.zip"
        export KEI_EVENTS_EM_CHECKSUMS_URL="file://$S/em-sub/checksums.json"
    fi
    export KEI_EVENTS_SRC="$REPO/nexus-events-plugin"
    koha_apache
    lib 'kei_apache_vhost_map' > "$S/apache_before"
}

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
    TN=/var/lib/koha-nexus/platforms/tainacan
    export KEI_BK_KEEP_LAST=50
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
$1" 3>&-
}

nope() { ! "$@"; }

# em_substitute OUT: the Events Manager files of bundled/ as a package plus
# checksums in the format wordpress.org publishes.
em_substitute() {
    mkdir -p "$1"
    python3 -I - "$REPO/nexus-events-plugin/bundled/events-manager" "$1" <<'EOF'
import hashlib, json, os, sys, zipfile
src, out = sys.argv[1:3]
files = {}
with zipfile.ZipFile(os.path.join(out, "events-manager.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for dp, dn, fn in os.walk(src):
        for f in fn:
            p = os.path.join(dp, f); rel = os.path.relpath(p, src).replace(os.sep, "/")
            data = open(p, "rb").read()
            z.writestr("events-manager/" + rel, data)
            files[rel] = {"md5": hashlib.md5(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest()}
json.dump({"plugin": "events-manager", "version": "7.4.13", "files": files}, open(os.path.join(out, "checksums.json"), "w"))
EOF
}

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

wp() { lib "_kei_tn_wp $*"; }
fixture() {
    install -m 644 "$REPO/tests/system/events-fixture.php" "$TN/work/events-fixture.php"
    lib "_kei_tn_wp eval-file /work/events-fixture.php $* --user=knadmin"
}
fx() { python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$S/fixture.json" "$1"; }
plugin_state() { wp "plugin get $1 --field=status" 2>/dev/null; }
ev_count() { lib '_kei_ev_counts' | awk -F'\t' -v k="count_$1" '$1 == k { print $2 }'; }
http_code() { curl -s -o "$S/page.html" -w '%{http_code}' "$1"; }
healthy() { for _ in $(seq 1 60); do lib 'kei_tainacan_health' >/dev/null 2>&1 && return 0; sleep 2; done; return 1; }
wp_volume() { docker volume inspect -f '{{.Mountpoint}}' kn-tainacan-wp; }

@test "before: Tainacan with a collection; events off until asked" {
    echo "Tainacan plugin: $(cat "$S/plugin"); Events Manager: $(cat "$S/em")" >&3
    if ! command -v docker >/dev/null 2>&1; then
        run lib 'kei_docker_install confirm'
        [ "$status" -eq 0 ]
    fi
    docker network create someone-net >/dev/null
    docker run -d --restart unless-stopped --name someone --network someone-net "$IMG" sleep 3600 >/dev/null
    IP=$(lib 'get_server_ip')
    run lib "kei_tainacan_install confirm http://$IP:8090"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    # Nothing of events comes with Tainacan.
    run lib 'kei_tainacan_events_status'
    echo "$output" >&3
    grep -qx 'events=' <<< "$output"
    grep -qx 'dependency=absent' <<< "$output"
    grep -qx 'plugin=absent' <<< "$output"
    [ -z "$(lib '_kei_ev_counts')" ]
    [ ! -e "$(wp_volume)/wp-content/plugins/events-manager" ]
    run lib 'kei_tainacan_events_plan'
    [ "$status" -eq 0 ]
    grep -qx $'em_action\tinstall' <<< "$output"
    koha_answers_as_before
}

@test "an Events Manager already in the site is kept as it is when events are turned on" {
    # Someone installed and activated Events Manager before (here, the same
    # checked package, by hand) and keeps a file of theirs in its folder.
    run lib '_kei_ev_fetch_em'
    [ "$status" -eq 0 ]
    run wp "plugin install /work/events-manager.7.4.13.zip --activate"
    [ "$status" -eq 0 ]
    echo mine > "$(wp_volume)/wp-content/plugins/events-manager/kn-someone-elses-file.txt"
    before=$(stat -c %Y "$(wp_volume)/wp-content/plugins/events-manager/events-manager.php")
    run lib 'kei_tainacan_events_plan'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    grep -qx $'em_origin\tpreexisting' <<< "$output"
    grep -qx $'em_action\tkeep' <<< "$output"
    run lib 'kei_tainacan_events_enable confirm'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(cat "$(wp_volume)/wp-content/plugins/events-manager/kn-someone-elses-file.txt")" = mine ]
    [ "$(stat -c %Y "$(wp_volume)/wp-content/plugins/events-manager/events-manager.php")" = "$before" ]
    [ "$(lib '_kei_tn_get events_em')" = preexisting ]
    [ "$(lib '_kei_tn_get events')" = on ]
    [ "$(plugin_state events-manager)" = active ]
    [ "$(plugin_state nexus-eventos)" = active ]
    [ "$(wp 'plugin get nexus-eventos --field=version')" = 0.1.1 ]
    # The production package only: no copy of Events Manager, no tests.
    nx="$(wp_volume)/wp-content/plugins/nexus-eventos"
    [ -f "$nx/nexus-eventos.php" ]
    [ ! -e "$nx/bundled" ] && [ ! -e "$nx/development" ]
    [ "$(find "$nx" -type f | wc -l)" = "$(lib '_kei_ev_package_files' | wc -l)" ]
    healthy
}

@test "the event edit screen is drawn whole with Tainacan active: the Nexus box lists the collections" {
    run fixture seed
    echo "$output" >&3
    [ "$status" -eq 0 ]
    printf '%s\n' "${lines[-1]}" > "$S/fixture.json"
    pid=$(fx event_post)
    # The box alone, as WordPress calls it.
    run fixture render "$pid"
    [ "$status" -eq 0 ]
    grep -q 'name="nxev_meta_nonce"' <<< "$output"
    grep -q 'name="nxev_collections_present"' <<< "$output"
    grep -qE "<option value=\"$(fx collection)\" +selected='selected'>Acervo da oficina</option>" <<< "$output"
    grep -q 'name="nxev_certificate" value="1"  checked' <<< "$output" || grep -q "name=\"nxev_certificate\" value=\"1\" checked='checked'" <<< "$output"
    # The whole edit screen, through Apache, logged in as the administrator.
    U=$(lib '_kei_tn_get url'); PW=$(lib '_kei_tn_env KN_ADMIN_PASSWORD')
    curl -s -c "$S/jar" -b "$S/jar" -o /dev/null "$U/wp-login.php"
    code=$(curl -s -c "$S/jar" -b "$S/jar" -o /dev/null -w '%{http_code}' --data-urlencode log=knadmin --data-urlencode "pwd=$PW" \
        --data-urlencode testcookie=1 --data-urlencode "redirect_to=$U/wp-admin/" "$U/wp-login.php")
    [ "$code" = 302 ]
    code=$(curl -s -b "$S/jar" -o "$S/edit.html" -w '%{http_code}' "$U/wp-admin/post.php?post=$pid&action=edit")
    echo "edit screen: HTTP $code, $(wc -c < "$S/edit.html") bytes" >&3
    [ "$code" = 200 ]
    nope grep -qiE 'critical error|Fatal error|Uncaught' "$S/edit.html"
    grep -q 'id="nxev-integration"' "$S/edit.html"
    grep -q 'name="nxev_collections\[\]"' "$S/edit.html"
    grep -q '>Acervo da oficina</option>' "$S/edit.html"
    grep -q 'name="nxev_hours"' "$S/edit.html"
    # The new-event screen too.
    code=$(curl -s -b "$S/jar" -o "$S/new.html" -w '%{http_code}' "$U/wp-admin/post-new.php?post_type=event")
    [ "$code" = 200 ]
    grep -q 'id="nxev-integration"' "$S/new.html"
    nope grep -qiE 'critical error|Fatal error' "$S/new.html"
}

@test "passes, attendance and a certificate; counted whether events are on or off" {
    [ "$(ev_count events)" = 2 ]
    [ "$(ev_count bookings)" = 3 ]
    # Approved one-person bookings of published events: the past and the future one, not the pending one.
    [ "$(ev_count passes)" = 2 ]
    [ "$(ev_count attendance)" = 1 ]
    [ "$(ev_count certificates)" = 1 ]
    [ "$(http_code "$(fx pass)")" = 200 ]
    grep -q 'Oficina de memória' "$S/page.html"
    grep -q 'Érica da Conceição' "$S/page.html"
    [ "$(http_code "$(fx pass | sed 's/nxev_key=[0-9a-f]*/nxev_key=0000000000000000000000000000000000000000000000000000000000000000/')")" = 404 ]
    # The public check says valid and does not publish who took part.
    [ "$(http_code "$(fx verify)")" = 200 ]
    grep -q 'Comprovante válido' "$S/page.html"
    nope grep -q 'Érica da Conceição' "$S/page.html"
    # The certificate itself, from the pass.
    [ "$(http_code "$(fx pass)&nxev_document=1")" = 200 ]
    grep -q 'Érica da Conceição' "$S/page.html"
}

@test "logs: pass keys and certificate codes are redacted" {
    run lib 'kei_tainacan_logs 500'
    [ "$status" -eq 0 ]
    grep -q 'nxev_key=' <<< "$output"
    nope grep -qF "$(fx pass_key)" <<< "$output"
    nope grep -qF "$(fx code)" <<< "$output"
    grep -q 'nxev_key=\[REDACTED\]' <<< "$output"
}

@test "backup with events on, then events off: Events Manager that was there before stays on, the data stays" {
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_setup confirm"
    [ "$status" -eq 0 ]
    run lib 'kei_tainacan_backup'
    [ "$status" -eq 0 ]
    printf '%s\n' "${lines[-1]}" > "$S/b_on"
    run lib 'kei_tainacan_events_disable'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    grep -q 'it was in this WordPress before' <<< "$output"
    [ "$(plugin_state nexus-eventos)" = inactive ]
    [ "$(plugin_state events-manager)" = active ]
    [ "$(lib '_kei_tn_get events')" = off ]
    [ "$(ev_count passes)" = 2 ] && [ "$(ev_count certificates)" = 1 ]
    healthy
}

@test "a backup with events off counts their data, and the restore check compares it" {
    run lib 'kei_tainacan_backup'
    [ "$status" -eq 0 ]
    B="${lines[-1]}"; echo "$B" > "$S/b_off"
    for k in events=2 bookings=3 passes=2 attendance=1 certificates=1; do
        [ "$(lib "_kei_tn_manifest_get '$B' count_${k%=*}")" = "${k#*=}" ]
    done
    [[ "$(lib "_kei_tn_manifest_get '$B' pass_keys_fingerprint")" =~ ^[0-9a-f]{16}$ ]]
    nope grep -qF "$(lib '_kei_tn_env KN_AUTH_SALT')" "$B/manifest.json"
    run lib "kei_tainacan_restore_test '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    # A package whose event data does not match is refused by the check.
    cp -a "$B" "$B-bad"
    sed -i 's/^  "count_attendance": 1,/  "count_attendance": 7,/' "$B-bad/manifest.json"
    ( cd "$B-bad" && sha256sum $(awk '{ print $2 }' SHA256SUMS) > SHA256SUMS.new && mv SHA256SUMS.new SHA256SUMS )
    run lib "kei_tainacan_restore_test '$B-bad'"
    echo "$output" >&3
    [ "$status" -ne 0 ]
    grep -q 'event data differs from the backup (attendance 1/7)' <<< "$output"
    rm -rf "$B-bad"
}

@test "restore without the phrase, other keys: the note says pass links stop working, and they do; with the phrase they work" {
    B=$(cat "$S/b_on")
    # This installation gets other keys (as a new server would).
    sed -i "s/^KN_AUTH_SALT=.*/KN_AUTH_SALT=$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 64)/" "$TN/.env"
    lib '_kei_tn_dc up -d wordpress' >/dev/null 2>&1
    healthy
    run lib "kei_tainacan_restore_notes '$B' nophrase"
    grep -q 'the 2 event pass links already sent stop working' <<< "$output"
    run lib "kei_tainacan_restore '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    grep -q 'the 2 event pass links already sent stop working' <<< "$output"
    healthy
    [ "$(plugin_state nexus-eventos)" = active ]
    [ "$(ev_count passes)" = 2 ] && [ "$(ev_count attendance)" = 1 ]
    [ "$(http_code "$(fx pass)")" = 404 ]
    # With the phrase: the keys of the backup come back, no note, the link works.
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore '$B'"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    nope grep -q 'pass links' <<< "$output"
    healthy
    [ "$(http_code "$(fx pass)")" = 200 ]
    grep -q 'Oficina de memória' "$S/page.html"
}

@test "events off with dependency turns Events Manager off on request; on again keeps it as someone else's" {
    run lib 'kei_tainacan_events_disable dependency'
    [ "$status" -eq 0 ]
    grep -q 'Events Manager was turned off too' <<< "$output"
    [ "$(plugin_state events-manager)" = inactive ]
    [ "$(plugin_state nexus-eventos)" = inactive ]
    run lib 'kei_tainacan_events_enable confirm'
    [ "$status" -eq 0 ]
    [ "$(plugin_state events-manager)" = active ]
    [ "$(lib '_kei_tn_get events_em')" = preexisting ]
    [ "$(cat "$(wp_volume)/wp-content/plugins/events-manager/kn-someone-elses-file.txt")" = mine ]
}

@test "a deleted booking takes its history with it; its certificate stays revoked and anonymous" {
    run fixture delete "$(fx b1)"
    echo "$output" >&3
    [ "$status" -eq 0 ]
    python3 -I - "${lines[-1]}" <<'EOF'
import json, sys
d = json.loads(sys.argv[1])
assert d["attendance"] == 0, d
assert d["log"] == 0, d
assert d["certificate"] == {"participant": "", "email": "", "revoked": True}, d
EOF
    [ "$(http_code "$(fx verify)")" = 200 ]
    grep -q 'Comprovante não encontrado ou inválido' "$S/page.html"
    [ "$(ev_count attendance)" = 0 ]
    [ "$(ev_count passes)" = 1 ]
}

@test "a site without Events Manager: installed from wordpress.org, every file as published, also after a cut run; off with events" {
    wp 'plugin deactivate nexus-eventos events-manager' >/dev/null
    wp 'plugin delete nexus-eventos events-manager' >/dev/null
    sed -i '/^events=/d; /^events_em=/d; /^events_em_file=/d; /^events_plugin=/d' "$TN/state"
    run lib 'kei_tainacan_events_plan'
    grep -qx $'em_action\tinstall' <<< "$output"
    # Cut right after Events Manager was put in (the panel's Cancel, a
    # reboot), with its folder left half written: events stay off, the
    # state already says whose it is, and the next run installs over it.
    run lib '_KEI_EV_CUT_AFTER=em kei_tainacan_events_enable confirm'
    [ "$status" -ne 0 ]
    [ "$(lib '_kei_tn_get events')" != on ]
    [ "$(lib '_kei_tn_get events_em')" = ours ]
    [ -z "$(plugin_state nexus-eventos)" ]
    rm -f "$(wp_volume)/wp-content/plugins/events-manager/events-manager.php"
    run lib 'kei_tainacan_events_plan'
    echo "$output" >&3
    grep -qx $'em_action\trepair' <<< "$output"
    # Cut again, after Nexus Eventos was put in, before it was turned on.
    run lib '_KEI_EV_CUT_AFTER=nx kei_tainacan_events_enable confirm'
    [ "$status" -ne 0 ]
    [ "$(lib '_kei_tn_get events')" != on ]
    run lib 'kei_tainacan_events_plan'
    grep -qx $'nx_action\tkeep' <<< "$output"
    run lib 'kei_tainacan_events_enable confirm'
    echo "$output" >&3
    [ "$status" -eq 0 ]
    [ "$(lib '_kei_tn_get events')" = on ]
    [ "$(lib '_kei_tn_get events_em')" = ours ]
    [ "$(wp 'plugin get events-manager --field=version')" = 7.4.13 ]
    # What WordPress has is exactly what wordpress.org publishes.
    python3 -I - "$(wp_volume)/wp-content/plugins/events-manager" "$TN/work/events-manager.7.4.13.checksums.json" <<'EOF'
import hashlib, json, os, sys
root, sums = sys.argv[1], json.load(open(sys.argv[2]))["files"]
have = {}
for dp, dn, fn in os.walk(root):
    for f in fn:
        p = os.path.join(dp, f)
        have[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
assert set(have) == set(sums), sorted(set(have) ^ set(sums))[:10]
want = lambda v: v["sha256"] if isinstance(v["sha256"], list) else [v["sha256"]]
bad = [k for k, v in sums.items() if have[k] not in want(v)]
assert not bad, bad[:10]
print("ok", len(have))
EOF
    [ "$(ev_count events)" = 2 ]
    run lib 'kei_tainacan_events_disable'
    [ "$status" -eq 0 ]
    grep -q 'Events Manager was turned off too' <<< "$output"
    [ "$(plugin_state events-manager)" = inactive ]
    [ "$(plugin_state nexus-eventos)" = inactive ]
    healthy
}

@test "after: Tainacan healthy, Koha's Apache and someone else's container as they were" {
    healthy
    koha_answers_as_before
    [ "$(docker inspect -f '{{.State.Running}}' someone)" = true ]
    run lib 'kei_docker_audit tainacan'
    [ "$status" -eq 0 ]
}
