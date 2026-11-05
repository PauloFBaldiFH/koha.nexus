#!/usr/bin/env bats
# uninstall.sh and the ownership registry: with resources of another
# platform registered, Apache, cloudflared, the tunnel and the panel stay
# and only Koha's parts go. DESTRUCTIVE: it runs the real uninstall.sh
# (purges packages), so it only runs in a throwaway container with
# KEI_DESTRUCTIVE_TESTS=1 (CI: .github/workflows/proxy.yml).

setup() {
    [ "${KEI_DESTRUCTIVE_TESTS:-}" = 1 ] || skip "destructive: set KEI_DESTRUCTIVE_TESTS=1 in a throwaway container"
    [ "$(id -u)" = 0 ] || skip "needs root"
    command -v apache2ctl >/dev/null 2>&1 || skip "needs Apache"
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
}

# A server with Koha's site, a site and a tunnel address of "tainacan".
fake_server() {
    mkdir -p /var/www/kei-new /etc/cloudflared /var/lib/koha-nexus
    echo NEW > /var/www/kei-new/index.html
    printf '<VirtualHost *:80>\n    ServerName catalog.kei.test\n</VirtualHost>\n' > /etc/apache2/sites-available/library.conf
    {
        echo '# Managed by Koha.Nexus: tainacan/acervo. Do not edit.'
        printf '<VirtualHost *:80>\n    ServerName acervo.kei.test\n    DocumentRoot /var/www/kei-new\n</VirtualHost>\n'
    } > /etc/apache2/sites-available/zz-koha-nexus-acervo.conf
    a2ensite -q library zz-koha-nexus-acervo >/dev/null
    cat > /etc/cloudflared/config.yml <<'EOF'
tunnel: abc
credentials-file: /root/.cloudflared/abc.json

ingress:
  - hostname: catalog.example.org
    service: http://localhost:80
  - hostname: admin.example.org
    service: http://localhost:8080
  - hostname: acervo.example.org
    service: http://localhost:8091
  - hostname: wiki.example.org
    service: http://localhost:80
  - service: http_status:404
EOF
    printf '#!/bin/bash\n' > /usr/local/bin/config.sh
    chmod 755 /usr/local/bin/config.sh
}

@test "with another platform registered, its Apache site, tunnel and the panel stay" {
    fake_server
    printf 'apache-site\tzz-koha-nexus-acervo.conf\ttainacan\tno\t-\t-\ningress\tacervo.example.org\ttainacan\tno\t-\thttp://localhost:8091\n' \
        > /var/lib/koha-nexus/owned.tsv
    printf 'ingress\tcatalog.example.org\tkoha\tno\t-\thttp://localhost:80\ningress\tadmin.example.org\tkoha\tno\t-\thttp://localhost:8080\n' \
        >> /var/lib/koha-nexus/owned.tsv
    run bash "$REPO/uninstall.sh" --full --yes
    [[ "$output" == *"Apache e cloudflared mantidos"* ]]
    dpkg-query -W -f='${Status}' apache2 | grep -q 'ok installed'
    [ -L /etc/apache2/sites-enabled/zz-koha-nexus-acervo.conf ]
    [ ! -e /etc/apache2/sites-enabled/library.conf ]
    [ -x /usr/local/bin/config.sh ]
    run cat /etc/cloudflared/config.yml
    [[ "$output" == *"acervo.example.org"* ]]
    [[ "$output" != *"catalog.example.org"* ]] && [[ "$output" != *"localhost:8080"* ]]
    [[ "$output" == *"http_status:404"* ]]
    # An entry added by hand stays, even on Koha's port.
    [[ "$output" == *"wiki.example.org"* ]]
    grep -q '^ingress	acervo.example.org	tainacan' /var/lib/koha-nexus/owned.tsv
    run grep -c '	koha	' /var/lib/koha-nexus/owned.tsv
    [ "$output" = 0 ]
}

@test "with no other platform, --full removes Apache as before" {
    fake_server
    rm -f /var/lib/koha-nexus/owned.tsv
    run bash "$REPO/uninstall.sh" --full --yes
    [[ "$output" != *"mantidos"* ]]
    run dpkg-query -W -f='${Status}' apache2
    [[ "$output" != *"ok installed"* ]]
    [ ! -e /usr/local/bin/config.sh ]
    [ ! -e /etc/cloudflared ]
    [ ! -e /var/lib/koha-nexus ]
}

@test "Docker is never removed; the record of an install made here stays" {
    fake_server
    rm -f /var/lib/koha-nexus/owned.tsv
    printf 'installed_by=koha-nexus\nstatus=installed\n' > /var/lib/koha-nexus/docker.state
    run bash "$REPO/uninstall.sh" --yes
    [[ "$output" == *"Docker mantido"* ]]
    grep -qx 'installed_by=koha-nexus' /var/lib/koha-nexus/docker.state
    [ "$(ls -A /var/lib/koha-nexus)" = docker.state ]
    rm -rf /var/lib/koha-nexus
}
