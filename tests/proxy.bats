#!/usr/bin/env bats
# Resource ownership and the web proxy (installer: kei_owned_*, kei_proxy_*,
# kei_tunnel_config). The registry, detection, external-proxy and tunnel
# tests need nothing installed. The Apache tests need root and a real
# Apache (apache2ctl); they set up a stand-in for Koha's site (library.conf
# on 80 and 8080) and check that it answers as before whatever happens.
# CI: .github/workflows/proxy.yml.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$W/owned"
}

# lib CODE: runs CODE with the installer loaded.
lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
$1" 3>&-
}

need_apache() {
    [ "$(id -u)" = 0 ] || skip "needs root"
    command -v apache2ctl >/dev/null 2>&1 || skip "needs Apache (apache2ctl)"
    command -v curl >/dev/null 2>&1 || skip "needs curl"
}

# ----------------------------------------------------------------------
# A stand-in for Koha's Apache: library.conf, OPAC on 80, staff on 8080.
# ----------------------------------------------------------------------
koha_apache() {
    mkdir -p /var/www/kei-opac /var/www/kei-staff /var/www/kei-new
    echo OPAC > /var/www/kei-opac/index.html
    echo STAFF > /var/www/kei-staff/index.html
    echo NEW > /var/www/kei-new/index.html
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
<Directory /var/www/kei-new>
    Require all granted
</Directory>
EOF
    a2dissite -q 000-default >/dev/null 2>&1 || true
    a2ensite -q library >/dev/null
    rm -f /etc/apache2/sites-*/zz-koha-nexus-*
    a2dismod -q -f info >/dev/null 2>&1 || true
    # 3>&-: a daemon that keeps bats' descriptor 3 open makes bats wait for ever.
    if [ -d /run/systemd/system ]; then systemctl restart apache2; else apache2ctl restart 3>&-; fi
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        [ "$(curl -s http://127.0.0.1/)" = OPAC ] && return 0
        sleep 1
    done
    return 1
}

koha_answers_as_before() {
    [ "$(curl -s http://127.0.0.1/)" = OPAC ]
    [ "$(curl -s --resolve catalog.kei.test:80:127.0.0.1 http://catalog.kei.test/)" = OPAC ]
    [ "$(curl -s http://127.0.0.1:8080/)" = STAFF ]
}

site_conf() {
    cat > "$W/site.conf" <<EOF
<VirtualHost *:80>
    ServerName ${1:-acervo.kei.test}
    DocumentRoot /var/www/kei-new
</VirtualHost>
EOF
}

# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
@test "registry: one line per resource and platform, counted by users" {
    run lib 'kei_owned_add apache-module proxy tainacan no
kei_owned_add apache-module proxy atom no
kei_owned_add apache-module proxy tainacan no
kei_owned_add ufw-port 80 tainacan yes
kei_owned_users apache-module proxy | tr "\n" " "; echo
kei_owned_list apache-module | wc -l
kei_owned_was_preexisting ufw-port 80 && echo pre80
kei_owned_was_preexisting apache-module proxy || echo notpre
kei_owned_del apache-module proxy tainacan
kei_owned_users apache-module proxy
kei_owned_platforms | tr "\n" " "'
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "atom tainacan " ]
    [ "${lines[1]}" = "2" ]
    [ "${lines[2]}" = "pre80" ] && [ "${lines[3]}" = "notpre" ]
    [ "${lines[4]}" = "atom" ]
    [ "${lines[5]}" = "atom tainacan " ]
}

@test "registry: bad entries are refused and tabs cannot split a column" {
    run lib 'kei_owned_add apache-site "" koha no; echo "rc=$?"
kei_owned_add apache-site x koha maybe; echo "rc=$?"
kei_owned_add ingress "a	b" tainacan no "" "http://localhost:1"; echo "rc=$?"
awk -F"\t" "{ print NF }" "$KEI_OWNED_DIR/owned.tsv"'
    [ "${lines[0]}" = "rc=2" ] && [ "${lines[1]}" = "rc=2" ] && [ "${lines[2]}" = "rc=0" ]
    [ "${lines[3]}" = "6" ]
}

# ----------------------------------------------------------------------
# Detection: the four cases (listeners and Apache faked)
# ----------------------------------------------------------------------
@test "detection: none, apache-nexus, apache-shared and external" {
    mkdir -p "$W/apache/sites-enabled" "$W/koha/library"
    run lib "KEI_APACHE_DIR='$W/nothing'; KEI_KOHA_SITES_DIR='$W/koha'
kei_web_listeners() { :; }; command() { [ \"\$2\" != apache2ctl ] && builtin command \"\$@\"; }
kei_proxy_detect
kei_web_listeners() { echo '80 nginx'; }; kei_proxy_detect
KEI_APACHE_DIR='$W/apache'; touch '$W/apache/apache2.conf'
kei_web_listeners() { echo '80 apache2'; }
touch '$W/apache/sites-enabled/library.conf' '$W/apache/sites-enabled/zz-koha-nexus-acervo.conf'; kei_proxy_detect
touch '$W/apache/sites-enabled/loja.conf'; kei_proxy_detect
kei_web_listeners() { printf '80 apache2\n443 caddy\n'; }; kei_proxy_detect"
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "none -" ]
    [ "${lines[1]}" = "external nginx" ]
    [ "${lines[2]}" = "apache-nexus apache2" ]
    [ "${lines[3]}" = "apache-shared apache2" ]
    [ "${lines[4]}" = "external caddy" ]
}

@test "--status-json gains proxy and keeps the other fields" {
    run lib 'systemctl() { echo inactive; }; kei_http_code() { echo 000; }; plack_running() { false; }
kei_web_listeners() { :; }; KEI_APACHE_DIR=/nonexistent; command() { [ "$2" != apache2ctl ] && builtin command "$@"; }
kei_status_json'
    [ "$status" -eq 0 ]
    run python3 -c 'import json,sys; d=json.loads(sys.argv[1])
for k in ("schema","state","koha_installed","services","backup","platforms","proxy"): assert k in d, k
print(d["schema"], d["proxy"])' "$output"
    [ "$output" = "1 {'mode': 'none', 'server': '', 'sites': 0}" ]
}

# ----------------------------------------------------------------------
# External proxy and tunnel
# ----------------------------------------------------------------------
@test "external proxy: nginx and caddy blocks, bad names refused" {
    run lib 'kei_proxy_external_snippet nginx acervo.example.org 8091'
    [[ "$output" == *"server_name acervo.example.org;"* ]]
    [[ "$output" == *"proxy_pass http://127.0.0.1:8091;"* ]]
    [[ "$output" == *'proxy_set_header Host $host;'* ]]
    run lib 'kei_proxy_external_snippet caddy acervo.example.org 8091'
    [[ "$output" == *"reverse_proxy 127.0.0.1:8091"* ]]
    run lib 'kei_proxy_external_snippet nginx "x; evil" 80'
    [ "$status" -eq 2 ]
    run lib 'kei_proxy_external_snippet apache acervo.example.org 80'
    [ "$status" -eq 2 ]
}

@test "tunnel: without other platforms config.yml is the same as before" {
    run lib 'kei_tunnel_config abc-123 /root/.cloudflared/abc-123.json catalog.example.org admin.example.org'
    expected="tunnel: abc-123
credentials-file: /root/.cloudflared/abc-123.json

ingress:
  - hostname: catalog.example.org
    service: http://localhost:80
  - hostname: admin.example.org
    service: http://localhost:8080
  - service: http_status:404"
    [ "$output" = "$expected" ]
}

@test "tunnel: other platforms' addresses are kept, before the 404" {
    run lib 'kei_tunnel_ingress_add tainacan acervo.example.org http://localhost:8091 || echo bad
kei_tunnel_ingress_add koha x.example.org http://localhost:1 && echo bad
kei_tunnel_ingress_add atom arq.example.org "http://evil.example.org:80" && echo bad
kei_tunnel_config id cred catalog.example.org admin.example.org'
    [[ "$output" != *bad* ]]
    [[ "$output" == *"  - hostname: admin.example.org
    service: http://localhost:8080
  - hostname: acervo.example.org
    service: http://localhost:8091
  - service: http_status:404"* ]]
    run lib 'kei_tunnel_ingress_del tainacan acervo.example.org; kei_tunnel_config id cred c.example.org a.example.org'
    [[ "$output" != *acervo* ]]
}

# ----------------------------------------------------------------------
# Apache (real)
# ----------------------------------------------------------------------
@test "apache: a site is applied, Koha stays the default server" {
    need_apache
    koha_apache
    site_conf
    run lib "kei_proxy_apply_site tainacan acervo '$W/site.conf'"
    [ "$status" -eq 0 ]
    head -n1 /etc/apache2/sites-available/zz-koha-nexus-acervo.conf | grep -qF '# Managed by Koha.Nexus: tainacan/acervo.'
    [ -L /etc/apache2/sites-enabled/zz-koha-nexus-acervo.conf ]
    [ "$(curl -s --resolve acervo.kei.test:80:127.0.0.1 http://acervo.kei.test/)" = NEW ]
    koha_answers_as_before
    apache2ctl -S 2>/dev/null | grep -E 'default server' | grep -q 'library.conf'
    run lib 'kei_owned_list apache-site'
    [[ "$output" == "apache-site	zz-koha-nexus-acervo.conf	tainacan	no	"* ]]
}

@test "apache: a syntax error is refused by configtest, nothing reloads" {
    need_apache
    koha_apache
    printf '<VirtualHost *:80>\n    ServerName broken.kei.test\n    NoSuchDirective on\n</VirtualHost>\n' > "$W/bad.conf"
    run lib "kei_proxy_apply_site tainacan broken '$W/bad.conf'"
    [ "$status" -eq 5 ]
    [ ! -e /etc/apache2/sites-available/zz-koha-nexus-broken.conf ]
    [ ! -e /etc/apache2/sites-enabled/zz-koha-nexus-broken.conf ]
    apache2ctl configtest
    koha_answers_as_before
    run lib 'kei_owned_list apache-site'
    [ -z "$output" ]
}

@test "apache: a broken update puts the previous version back" {
    need_apache
    koha_apache
    site_conf
    run lib "kei_proxy_apply_site tainacan acervo '$W/site.conf'"
    [ "$status" -eq 0 ]
    cp /etc/apache2/sites-available/zz-koha-nexus-acervo.conf "$W/before.conf"
    printf '<VirtualHost *:80>\n    ServerName acervo.kei.test\n    Bogus x\n</VirtualHost>\n' > "$W/bad.conf"
    run lib "kei_proxy_apply_site tainacan acervo '$W/bad.conf'"
    [ "$status" -eq 5 ]
    cmp /etc/apache2/sites-available/zz-koha-nexus-acervo.conf "$W/before.conf"
    [ "$(curl -s --resolve acervo.kei.test:80:127.0.0.1 http://acervo.kei.test/)" = NEW ]
    koha_answers_as_before
}

@test "apache: a valid site that changes Koha's answers is rolled back" {
    need_apache
    koha_apache
    # Valid syntax, but outside its <VirtualHost>: every site would answer 403.
    printf '<Location />\n    Require all denied\n</Location>\n<VirtualHost *:80>\n    ServerName greedy.kei.test\n    DocumentRoot /var/www/kei-new\n</VirtualHost>\n' > "$W/greedy.conf"
    run lib "kei_proxy_apply_site tainacan greedy '$W/greedy.conf'"
    [ "$status" -eq 6 ]
    [ ! -e /etc/apache2/sites-available/zz-koha-nexus-greedy.conf ]
    sleep 1
    koha_answers_as_before
    run lib 'kei_owned_list apache-site'
    [ -z "$output" ]
}

@test "apache: a file that is not Koha.Nexus's, or another platform's, is left alone" {
    need_apache
    koha_apache
    site_conf
    echo '# hand made' > /etc/apache2/sites-available/zz-koha-nexus-mine.conf
    run lib "kei_proxy_apply_site tainacan mine '$W/site.conf'"
    [ "$status" -eq 4 ]
    [ "$(cat /etc/apache2/sites-available/zz-koha-nexus-mine.conf)" = "# hand made" ]
    rm -f /etc/apache2/sites-available/zz-koha-nexus-mine.conf
    run lib "kei_proxy_apply_site tainacan acervo '$W/site.conf'"
    [ "$status" -eq 0 ]
    run lib "kei_proxy_apply_site atom acervo '$W/site.conf'"
    [ "$status" -eq 4 ]
    run lib "kei_proxy_remove_site atom acervo"
    [ "$status" -eq 4 ]
    run lib "kei_proxy_apply_site tainacan '../etc' '$W/site.conf'"
    [ "$status" -eq 2 ]
}

@test "apache: removing a site leaves Koha answering" {
    need_apache
    koha_apache
    site_conf
    run lib "kei_proxy_apply_site tainacan acervo '$W/site.conf'"
    [ "$status" -eq 0 ]
    run lib "kei_proxy_remove_site tainacan acervo"
    [ "$status" -eq 0 ]
    [ ! -e /etc/apache2/sites-available/zz-koha-nexus-acervo.conf ]
    [ ! -e /etc/apache2/sites-enabled/zz-koha-nexus-acervo.conf ]
    koha_answers_as_before
    run lib 'kei_owned_list apache-site'
    [ -z "$output" ]
}

@test "apache: modules are counted; one enabled before is never disabled" {
    need_apache
    koha_apache
    a2enmod -q alias >/dev/null
    run lib 'kei_proxy_module_use tainacan info && kei_proxy_module_use atom info && kei_proxy_module_use tainacan alias
kei_proxy_module_release tainacan info; [ -e "$KEI_APACHE_DIR/mods-enabled/info.load" ] && echo info-kept
kei_proxy_module_release atom info; [ -e "$KEI_APACHE_DIR/mods-enabled/info.load" ] || echo info-off
kei_proxy_module_release tainacan alias; [ -e "$KEI_APACHE_DIR/mods-enabled/alias.load" ] && echo alias-kept'
    [ "$status" -eq 0 ]
    [ "$output" = "$(printf 'info-kept\ninfo-off\nalias-kept')" ]
    koha_answers_as_before
}

@test "apache: detection on the real server" {
    need_apache
    koha_apache
    run lib "KEI_KOHA_SITES_DIR='$W/koha'; mkdir -p '$W/koha/library'; kei_proxy_detect"
    [ "$output" = "apache-nexus apache2" ]
    a2ensite -q 000-default >/dev/null
    run lib "KEI_KOHA_SITES_DIR='$W/koha'; mkdir -p '$W/koha/library'; kei_proxy_detect"
    a2dissite -q 000-default >/dev/null
    [ "$output" = "apache-shared apache2" ]
}
