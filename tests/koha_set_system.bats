#!/usr/bin/env bats
# The joint package with a REAL Koha (koha-common from the official
# repository) and a REAL Tainacan, on a machine with systemd (document V,
# section 5): what Koha encrypted with its key (a staff two-factor secret)
# is readable again on a recreated instance only after the encryption key
# comes back from the package, and nothing else of the target's
# koha-conf.xml changes; an uploaded file and a plugin come back; Koha is
# restored alone from the set, Tainacan on its own.
#
# The recreated instance is a new installation of the same library: a new
# koha-conf.xml with another encryption key and another database password
# (koha-remove, koha-create), as on a new server.
#
# DESTRUCTIVE: installs Koha, MariaDB, Docker and Tainacan. It only runs
# with KEI_DESTRUCTIVE_TESTS=1, as root, under systemd, in a throwaway
# machine: tests/system/container.sh (CI: .github/workflows/proxy.yml, job
# koha-set). KEI_REQUIRE_REAL_KOHA=1 (CI) fails instead of skipping when
# the Koha repository cannot be reached. The tests depend on each other
# and run in order.

PHRASE="KOHA-SETS-YSTE-MPHR-2026-ABCD"
TOTP="JBSWY3DPEHPK3PXP"          # a two-factor secret (the RFC's sample, not a real one)
INST=library

setup_file() {
    [ "${KEI_DESTRUCTIVE_TESTS:-}" = 1 ] || skip "destructive: set KEI_DESTRUCTIVE_TESTS=1 in a throwaway machine"
    [ "$(id -u)" = 0 ] || skip "needs root"
    [ -d /run/systemd/system ] || skip "needs systemd"
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
    install -m 755 "$REPO/installer" /usr/local/bin/config.sh
    export KEI_TAINACAN_REGISTRY="${KEI_TAINACAN_REGISTRY:-docker.io}"
    if ! curl -sfI --max-time 20 https://debian.koha-community.org/koha/dists/stable/Release >/dev/null 2>&1; then
        [ "${KEI_REQUIRE_REAL_KOHA:-}" = 1 ] && { echo "debian.koha-community.org unreachable and a real Koha is required" >&2; return 1; }
        skip "debian.koha-community.org unreachable: a real Koha cannot be installed here"
    fi
    if curl -sfI --max-time 15 "https://downloads.wordpress.org/plugin-checksums/tainacan/1.4.1.json" >/dev/null 2>&1; then
        echo real > "$S/plugin"
    else
        [ "${KEI_REQUIRE_REAL_TAINACAN:-}" = 1 ] && { echo "wordpress.org unreachable and the real plugin is required" >&2; return 1; }
        "$REPO/tests/system/tainacan-stub/build.sh" "$S/stub"
        echo "test double (wordpress.org unreachable)" > "$S/plugin"
        export KEI_TAINACAN_PLUGIN_URL="file://$S/stub/tainacan.zip"
        export KEI_TAINACAN_CHECKSUMS_URL="file://$S/stub/checksums.json"
    fi
}

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    S="$BATS_FILE_TMPDIR"
    CONF=/etc/koha/sites/$INST/koha-conf.xml
    TN=/var/lib/koha-nexus/platforms/tainacan
    export KEI_BK_KEEP_LAST=50
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
$1" 3>&-
}
never() { ! "$@"; }
conf() { lib "_kei_koha_conf_value '$CONF' '$1'"; }
sql() { koha-mysql "$INST" -N -e "$1"; }
# Koha's own code, as root with the instance's configuration; errors stay
# visible in the test output.
koha_perl() { env PERL5LIB=/usr/share/koha/lib KOHA_CONF="$CONF" perl -MKoha::Encryption -e "$1" "${2:-}"; }
decrypt() { koha_perl 'print Koha::Encryption->new->decrypt_hex(shift)' "$(sql "SELECT secret FROM borrowers WHERE userid = 'kn-staff'")"; }
field() { sed -n "s/^$1=//p" <<<"$2" | tail -n 1; }

# koha_instance: koha-create, with an encryption key of its own. What
# koha-create wrote about the key is reported (never its value); when the
# instance has no usable key, one is set the way koha-create would.
koha_instance() {
    local key state
    # koha-create right after koha-remove failed once in CI with its output
    # hidden: it is shown now, and tried once more after the services settle.
    if ! koha-create --create-db "$INST" > "$S/koha-create.log" 2>&1 3>&- && [ ! -f "$CONF" ]; then
        sed 's/^/  koha-create: /' "$S/koha-create.log" | tail -n 20 >&3
        koha-remove "$INST" >/dev/null 2>&1 3>&- || true      # what the failed attempt left
        sleep 10
        koha-create --create-db "$INST" > "$S/koha-create.log" 2>&1 3>&- || [ -f "$CONF" ] \
            || { sed 's/^/  koha-create (2): /' "$S/koha-create.log" | tail -n 20 >&3; return 1; }
    fi
    case "$(conf encryption_key)" in
        "") state=none ;; __ENCRYPTION_KEY__) state=placeholder ;; *) state=set ;;
    esac
    echo "koha-create: $(grep -c '<encryption_key>' "$CONF") <encryption_key> line(s) in koha-conf.xml, key $state" >&3
    grep -n -B1 -A1 '<encryption_key>' "$CONF" | sed -E 's/(<encryption_key>)[^<]+/\1(value hidden)/; s/^/  /' >&3
    key=$(head -c 24 /dev/urandom | base64 | tr -d '/+=')
    case "$state" in
        placeholder)
            sed -i "s|<encryption_key>__ENCRYPTION_KEY__</encryption_key>|<encryption_key>$key</encryption_key>|" "$CONF" ;;
        none)
            if grep -qE '<encryption_key>[[:space:]]*</encryption_key>' "$CONF"; then
                sed -i -E "s|<encryption_key>[[:space:]]*</encryption_key>|<encryption_key>$key</encryption_key>|" "$CONF"
            else
                perl -0pi -e "s|(.*)</config>|\$1 <encryption_key>$key</encryption_key>\n</config>|s" "$CONF"   # the LAST </config>: the main section
            fi ;;
    esac
    case "$(conf encryption_key)" in ""|__ENCRYPTION_KEY__) return 1 ;; esac
}

# koha_schema: the tables (the web installer's kohastructure.sql) and the
# Version preference the web installer records, which the panel's restore
# requires of a Koha database.
koha_schema() {
    local v
    koha-mysql "$INST" < /usr/share/koha/intranet/cgi-bin/installer/data/mysql/kohastructure.sql || return 1
    if [ -f /usr/share/koha/intranet/cgi-bin/kohaversion.pl ]; then
        v=$(PERL5LIB=/usr/share/koha/lib perl -e 'require "/usr/share/koha/intranet/cgi-bin/kohaversion.pl"; my @v = split /\./, kohaversion(); print "$v[0]." . join("", @v[1 .. $#v])')
    else
        v=$(dpkg-query -W -f '${Version}' koha-common | sed 's/-.*//' | awk -F. '{ printf "%s.%s%s000", $1, $2, $3 }')
    fi
    [ -n "$v" ] || return 1
    sql "INSERT INTO systempreferences (variable, value) VALUES ('Version', '$v')"
    echo "Koha schema: Version $v" >&3
}

wp_php() {
    printf '%s\n' "$1" > "$TN/work/t.php"
    chmod 644 "$TN/work/t.php"
    lib '_kei_tn_wp eval-file /work/t.php --user=knadmin'
}
counts() { lib '_kei_tn_counts' | awk '{ print $1, $2, $3 }'; }
seed_php() {
    cat <<PHP
<?php
\$r = new WP_REST_Request("POST", "/tainacan/v2/collections");
\$r->set_header("content-type", "application/json");
\$r->set_body(json_encode(["name" => "$1", "status" => "publish"]));
\$res = rest_do_request(\$r);
if (\$res->get_status() >= 300) { fwrite(STDERR, json_encode(\$res->get_data())); exit(1); }
echo "ok\n";
PHP
}

@test "a real Koha: koha-common from the official repository, an instance, its schema" {
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl gnupg ca-certificates apache2 mariadb-server >/dev/null
    systemctl enable --now mariadb >/dev/null 2>&1
    curl -fsSL --retry 5 https://debian.koha-community.org/koha/gpg.asc | gpg --dearmor > /usr/share/keyrings/koha-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/koha-keyring.gpg] https://debian.koha-community.org/koha ${KEI_KOHA_SUITE:-stable} main" \
        > /etc/apt/sources.list.d/koha.list
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq koha-common >/dev/null
    grep -qE '^Listen 8080$' /etc/apache2/ports.conf || echo 'Listen 8080' >> /etc/apache2/ports.conf
    a2enmod rewrite cgi headers proxy_http >/dev/null 2>&1 || true
    koha_instance
    koha_schema
    echo "Koha: $(dpkg-query -W -f '${Version}' koha-common)" >&3
    # Where this Koha uses its encryption key (document V: "a conferir").
    grep -rl 'Koha::Encryption' /usr/share/koha/lib /usr/share/koha/intranet/cgi-bin /usr/share/koha/opac/cgi-bin 2>/dev/null \
        | sed 's|^/usr/share/koha/||' | sort | sed 's/^/  uses Koha::Encryption: /' >&3
    [ -n "$(conf encryption_key)" ]
}

@test "data that depends on the key and data outside the database" {
    sql "INSERT INTO branches (branchcode, branchname) VALUES ('MAIN', 'Main')"
    sql "INSERT INTO categories (categorycode, description, category_type) VALUES ('S', 'Staff', 'S')"
    cipher=$(koha_perl 'print Koha::Encryption->new->encrypt_hex(shift)' "$TOTP")
    [ -n "$cipher" ] && [ "$cipher" != "$TOTP" ]
    sql "INSERT INTO borrowers (cardnumber, surname, branchcode, categorycode, userid, flags, secret) VALUES ('kn1', 'Teste', 'MAIN', 'S', 'kn-staff', 1, '$cipher')"
    [ "$(decrypt)" = "$TOTP" ]
    # An uploaded file (Upload tool): the database keeps its name and hash only.
    up=$(conf upload_path || true); up=${up:-/var/lib/koha/$INST/uploads}
    mkdir -p "$up/kn" && printf 'scanned page\n' > "$up/kn/sample.pdf"
    chown -R "$INST-koha:$INST-koha" "$up"
    sql "INSERT INTO uploaded_files (hashvalue, filename, dir, filesize, uploadcategorycode, public, permanent) VALUES ('$(sha1sum < "$up/kn/sample.pdf" | cut -c1-40)', 'sample.pdf', 'kn', 13, 'kn', 1, 1)"
    printf '%s\n' "$up" > "$S/upload_path"
    # A plugin (its code is not in the database).
    pl=$(conf pluginsdir || true); pl=${pl:-/var/lib/koha/$INST/plugins}
    mkdir -p "$pl/Koha/Plugin" && printf 'package Koha::Plugin::KnTest;\n1;\n' > "$pl/Koha/Plugin/KnTest.pm"
    printf '%s\n' "$pl" > "$S/plugins"
    # SIP2 logins of this library.
    printf '<acsconfig><accounts><login id="kn-sip" password="sip-secret-1" institution="MAIN"/></accounts></acsconfig>\n' \
        > "/etc/koha/sites/$INST/SIPconfig.xml"
    chmod 600 "/etc/koha/sites/$INST/SIPconfig.xml"
}

@test "a real Tainacan with a collection, and the backup key" {
    echo "Tainacan plugin: $(cat "$S/plugin")" >&3
    command -v docker >/dev/null 2>&1 || { run lib 'kei_docker_install confirm'; [ "$status" -eq 0 ]; }
    IP=$(lib 'get_server_ip')
    run lib "kei_tainacan_install confirm http://$IP:8090"
    [ "$status" -eq 0 ]
    run wp_php "$(seed_php "Acervo do conjunto")"
    [ "$status" -eq 0 ]
    counts > "$S/tn_counts"
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_backup_setup confirm"
    [ "$status" -eq 0 ]
    run lib 'kei_backup_kit'
    [ "$status" -eq 0 ]
    cp /var/lib/koha-nexus/backup/recovery-kit.txt "$S/kit.txt"
}

@test "the joint package: full, Koha's files in it, its secrets only encrypted" {
    mkdir -p "$S/sets"
    run config.sh --task set-backup "$S/sets" </dev/null 3>&-
    echo "$output" | grep '@@result' >&3
    [ "$status" -eq 0 ]
    [[ "$output" == *"recoverability=full"* ]]
    SET=$(ls "$S"/sets/knx-set-*.tar)
    tar -tf "$SET" | grep -qx 'koha/files.tar.gz'
    tar -tf "$SET" | grep -qx 'koha/secrets.tar.gpg'
    files=$(tar -xOf "$SET" koha/files.tar.gz | tar -tzf -)
    grep -qx './uploads/kn/sample.pdf' <<<"$files" && grep -qx './plugins/Koha/Plugin/KnTest.pm' <<<"$files"
    # No value of a secret readable in the set, nor in its files.
    key=$(conf encryption_key); pass=$(conf pass)
    printf '%s\n' "$key" > "$S/old_key"; printf '%s\n' "$pass" > "$S/old_pass"
    all=$(tar -xOf "$SET"; tar -xOf "$SET" koha/files.tar.gz | tar -xzOf -)
    never grep -aqF -e "$key" -e "$pass" -e sip-secret-1 <<<"$all"
}

@test "a new installation of the library: another key, another database password" {
    koha-remove "$INST" >/dev/null 2>&1 3>&- || true
    [ ! -f "$CONF" ]
    # koha-remove keeps the instance's files under /var/lib/koha: a new
    # server has none.
    rm -rf "$(cat "$S/upload_path")" "$(cat "$S/plugins")"
    koha_instance
    [ "$(conf encryption_key)" != "$(cat "$S/old_key")" ]
    [ "$(conf pass)" != "$(cat "$S/old_pass")" ]
    conf pass > "$S/new_pass"; { conf upload_path || true; } > "$S/new_upload_conf"
    cp -p "$CONF" "$S/new-koha-conf.xml"
    [ ! -e "$(cat "$S/upload_path")/kn/sample.pdf" ]
}

@test "Koha alone restored from the set: the data is back, the two-factor secret does not open yet" {
    SET=$(ls "$S"/sets/knx-set-*.tar)
    run lib "kei_set_unpack '$SET'"
    [ "$status" -eq 0 ]
    field stage "$output" > "$S/stage"
    KOHA_FILE=$(field koha "$output")
    run config.sh --task restore "$KOHA_FILE" </dev/null 3>&-
    echo "$output" | grep -E '@@(msg|result)' | tail -n 5 >&3
    [ "$status" -eq 0 ]
    [ "$(sql "SELECT COUNT(*) FROM borrowers WHERE userid = 'kn-staff'")" = 1 ]
    [ "$(sql "SELECT filename FROM uploaded_files WHERE dir = 'kn'")" = sample.pdf ]
    # The ciphertext came back with the database, but this key does not open it.
    [ "$(decrypt)" != "$TOTP" ]
    [ ! -e "$(cat "$S/upload_path")/kn/sample.pdf" ]
}

@test "Koha's files and secrets: a plan without values, then only the key changes in koha-conf.xml" {
    STAGE=$(cat "$S/stage")
    run env KEI_BACKUP_PHRASE="$PHRASE" config.sh --task set-koha-extras plan "$STAGE" </dev/null 3>&-
    [ "$status" -eq 0 ]
    echo "$output" | grep '@@result' >&3
    [[ "$output" == *"secrets=open"* ]]
    [[ "$output" == *"item=encryption_key"$'\t'"apply"* ]]
    [[ "$output" == *"item=uploads"$'\t'"restore"* ]]
    never grep -qF -e "$(cat "$S/old_key")" -e "$(cat "$S/old_pass")" -e "$(cat "$S/new_pass")" -e sip-secret-1 -e "$PHRASE" <<<"$output"
    cmp -s "$CONF" "$S/new-koha-conf.xml"                              # the plan changed nothing
    run env KEI_BACKUP_PHRASE="$PHRASE" config.sh --task set-koha-extras apply "$STAGE" confirm </dev/null 3>&-
    [ "$status" -eq 0 ]
    never grep -qF -e "$(cat "$S/old_key")" -e sip-secret-1 -e "$PHRASE" <<<"$output"
    # Only <encryption_key> changed: the database password and the paths are the new installation's.
    [ "$(conf encryption_key)" = "$(cat "$S/old_key")" ]
    [ "$(conf pass)" = "$(cat "$S/new_pass")" ]
    diff <(grep -v '<encryption_key>' "$CONF") <(grep -v '<encryption_key>' "$S/new-koha-conf.xml")
    ls /etc/koha/sites/$INST/koha-conf.xml.kei-before-secrets-* >/dev/null
    # What depended on the key opens again; the files are back.
    [ "$(decrypt)" = "$TOTP" ]
    [ "$(cat "$(cat "$S/upload_path")/kn/sample.pdf")" = "scanned page" ]
    [ -f "$(cat "$S/plugins")/Koha/Plugin/KnTest.pm" ]
    # SIP2: added when the new installation had none, else kept beside.
    sip=/etc/koha/sites/$INST/SIPconfig.xml
    grep -q sip-secret-1 "$sip" || grep -q sip-secret-1 "$sip.from-backup"
    # Koha answers with its database.
    [ "$(env PERL5LIB=/usr/share/koha/lib KOHA_CONF="$CONF" perl -MC4::Context -e 'print C4::Context->dbh->selectrow_array(q{SELECT COUNT(*) FROM borrowers})')" = 1 ]
}

@test "Tainacan restored on its own from the set" {
    STAGE=$(cat "$S/stage")
    P=$(ls -d "$STAGE"/tainacan/knx-tainacan-*)
    run wp_php "$(seed_php "Depois do conjunto")"
    [ "$status" -eq 0 ]
    [ "$(counts)" != "$(cat "$S/tn_counts")" ]
    run lib "KEI_BACKUP_PHRASE='$PHRASE' kei_tainacan_restore '$P'"
    [ "$status" -eq 0 ]
    [ "$(counts)" = "$(cat "$S/tn_counts")" ]
    # Koha was not touched by Tainacan's restore.
    [ "$(decrypt)" = "$TOTP" ]
    lib "kei_set_cleanup '$STAGE'"
}
