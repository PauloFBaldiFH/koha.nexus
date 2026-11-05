#!/usr/bin/env bats
# The checks PR 2 (proxy and ownership) left for a real machine: Apache
# reloaded by systemd, UFW active, and cloudflared's own validation of the
# tunnel file. DESTRUCTIVE (changes Apache, UFW and /etc/cloudflared): only
# with KEI_DESTRUCTIVE_TESTS=1, as root, under systemd, in a throwaway
# machine (tests/system/container.sh; CI: .github/workflows/proxy.yml).

setup() {
    [ "${KEI_DESTRUCTIVE_TESTS:-}" = 1 ] || skip "destructive: set KEI_DESTRUCTIVE_TESTS=1 in a throwaway machine"
    [ "$(id -u)" = 0 ] || skip "needs root"
    [ -d /run/systemd/system ] || skip "needs systemd"
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$W/owned"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
$1" 3>&-
}

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
    systemctl reset-failed apache2 2>/dev/null || true
    systemctl restart apache2
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        [ "$(curl -s http://127.0.0.1/)" = OPAC ] && return 0
        sleep 1
    done
    return 1
}

@test "systemd: a site is applied with systemctl reload; Koha keeps answering" {
    koha_apache
    pid=$(systemctl show -p MainPID --value apache2)
    printf '<VirtualHost *:80>\n    ServerName acervo.kei.test\n    DocumentRoot /var/www/kei-new\n</VirtualHost>\n' > "$W/site.conf"
    run lib "kei_owned_add apache-site zz-koha-nexus-acervo.conf tainacan no
kei_proxy_apply_site tainacan acervo '$W/site.conf'"
    [ "$status" -eq 0 ]
    # A reload, not a restart: the main process is the same.
    [ "$(systemctl show -p MainPID --value apache2)" = "$pid" ]
    journalctl -u apache2 --no-pager | grep -q 'Reload'
    [ "$(curl -s --resolve acervo.kei.test:80:127.0.0.1 http://acervo.kei.test/)" = NEW ]
    [ "$(curl -s http://127.0.0.1/)" = OPAC ]
    [ "$(curl -s http://127.0.0.1:8080/)" = STAFF ]
    run lib 'kei_proxy_remove_site tainacan acervo'
    [ "$status" -eq 0 ]
    [ "$(systemctl show -p MainPID --value apache2)" = "$pid" ]
    [ "$(curl -s --resolve acervo.kei.test:80:127.0.0.1 http://acervo.kei.test/)" = OPAC ]
}

@test "UFW active: a port opened for a platform closes again; one that existed stays" {
    command -v ufw >/dev/null || skip "needs ufw"
    ufw --force reset >/dev/null
    ufw allow 22/tcp >/dev/null
    ufw allow 80/tcp >/dev/null
    ufw --force enable >/dev/null
    run lib 'kei_proxy_port_open tainacan 80; kei_proxy_port_open tainacan 8091; kei_proxy_port_open atom 8091
kei_owned_list ufw-port | cut -f2,3,4 | sort | tr "\t\n" " |"'
    [ "$output" = "80 tainacan yes|8091 atom no|8091 tainacan no|" ]
    ufw status | grep -qE '^8091/tcp +ALLOW'
    run lib 'kei_proxy_port_release tainacan 8091'
    ufw status | grep -qE '^8091/tcp +ALLOW'          # atom still uses it
    run lib 'kei_proxy_port_release atom 8091; kei_proxy_port_release tainacan 80'
    run ufw status
    [[ "$output" != *8091* ]]
    [[ "$output" == *"80/tcp"* ]] && [[ "$output" == *"22/tcp"* ]]
    ufw --force disable >/dev/null
}

@test "cloudflared: the tunnel file passes its validation; an invalid one is refused" {
    command -v cloudflared >/dev/null || skip "needs cloudflared"
    export KEI_TUNNEL_CONFIG="$W/config.yml"
    printf '{"AccountTag":"x","TunnelSecret":"eA==","TunnelID":"abc"}\n' > "$W/abc.json"
    run lib "kei_tunnel_config abc '$W/abc.json' catalog.example.org admin.example.org > '$KEI_TUNNEL_CONFIG'
cloudflared tunnel --config '$KEI_TUNNEL_CONFIG' ingress validate"
    [ "$status" -eq 0 ]
    run lib 'kei_tunnel_ingress_add tainacan acervo.example.org http://localhost:8091'
    [ "$status" -eq 0 ]
    grep -q 'acervo.example.org' "$KEI_TUNNEL_CONFIG"
    cloudflared tunnel --config "$KEI_TUNNEL_CONFIG" ingress validate
    cp "$KEI_TUNNEL_CONFIG" "$W/good"
    # A file without the catch-all rule: cloudflared refuses it, the old one stays.
    printf 'tunnel: abc\ningress:\n  - hostname: x.example.org\n    service: http://localhost:80\n' > "$W/bad"
    run lib "kei_tunnel_write '$W/bad'"
    [ "$status" -eq 5 ]
    cmp "$KEI_TUNNEL_CONFIG" "$W/good"
}
