#!/usr/bin/env bats
# Koha with one port or two (U10, study 16.1): kei_koha_access. Two ports
# stays the default; one port adds the staff by name on 80 through an
# Apache site of Koha.Nexus (kei_proxy_apply_site, stubbed here; the real
# Apache runs in tests/proxy_system.bats). Koha's own files never change.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned"
    mkdir -p "$T/bin" "$KEI_OWNED_DIR"
    for c in bash sh awk sed grep cat mkdir mktemp mv rm chmod cp tr head tail cut sort printf date env python3 flock; do
        p=$(command -v "$c" 2>/dev/null) && ln -sf "$p" "$T/bin/$c"
    done
    cat > "$T/bin/ip" <<'SH'
#!/bin/sh
case "$*" in
    *route*) echo "1.1.1.1 via 192.168.0.1 dev eth0 src 192.168.0.20 uid 0" ;;
    *) echo "2: eth0    inet 192.168.0.20/24 brd 192.168.0.255 scope global eth0" ;;
esac
SH
    # Names: biblioteca.org.br points here, admin.biblioteca.org.br elsewhere,
    # anything else does not resolve.
    cat > "$T/bin/getent" <<'SH'
#!/bin/sh
case "$2" in
    biblioteca.org.br) echo "192.168.0.20    STREAM biblioteca.org.br" ;;
    admin.biblioteca.org.br) echo "203.0.113.9    STREAM admin.biblioteca.org.br" ;;
    *) exit 2 ;;
esac
SH
    printf '#!/bin/sh\nexit 0\n' > "$T/bin/apache2ctl"
    chmod +x "$T/bin/ip" "$T/bin/getent" "$T/bin/apache2ctl"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
kei_result() { printf '@@result %s=%s\n' \"\$1\" \"\$2\"; }
msg_error() { printf 'ERROR %s\n' \"\$2\"; }
is_koha_installed() { INTRAPORT=8080; return 0; }
get_server_ip() { echo 198.51.100.7; }
kei_proxy_module_use() { echo \"use \$*\" >> '$T/calls'; }
kei_proxy_module_release() { echo \"release \$*\" >> '$T/calls'; }
kei_proxy_apply_site() { echo \"apply \$1 \$2\" >> '$T/calls'; cp \"\$3\" '$T/site.conf'; [ -f '$T/refuse' ] && return 5; kei_owned_add apache-site zz-koha-nexus-\$2.conf \$1 no x; }
kei_proxy_remove_site() { echo \"remove \$*\" >> '$T/calls'; kei_owned_del apache-site zz-koha-nexus-\$2.conf \$1; }
KEI_PLATFORM=linux
PATH='$T/bin'
$1" 3>&-
}

@test "status: two ports by default, the addresses by IP" {
    run lib 'kei_koha_access status'
    [ "$status" -eq 0 ]
    [ "$output" = $'@@result mode=two\n@@result opac=http://192.168.0.20\n@@result staff=http://192.168.0.20:8080' ]
}

@test "plan: a domain is required and checked; nothing is changed" {
    for d in '' 'http://biblioteca.org.br' 'biblioteca' 'Biblioteca.org.br' '192.168.0.20' 'admin.biblioteca.org.br' 'a b.org' 'biblioteca.org.br/opac'; do
        run lib "kei_koha_access plan one '$d'"
        [ "$status" -eq 2 ]
        grep -q "^ERROR Type the institution's domain" <<< "$output"
    done
    run lib 'kei_koha_access plan one biblioteca.org.br'
    [ "$status" -eq 0 ]
    grep -qx '@@result staff=http://admin.biblioteca.org.br' <<< "$output"
    grep -qx '@@result opac=http://biblioteca.org.br' <<< "$output"
    grep -qx '@@result recovery=http://127.0.0.1:8080' <<< "$output"
    grep -qx '@@result points=biblioteca.org.br|here' <<< "$output"
    grep -qx '@@result points=admin.biblioteca.org.br|elsewhere' <<< "$output"
    grep -qx '@@result staff_net=all' <<< "$output"
    run lib 'kei_koha_access plan one acervo.example.org'
    grep -qx '@@result points=acervo.example.org|none' <<< "$output"
    [ ! -f "$T/calls" ] && [ ! -f "$KEI_OWNED_DIR/koha-access" ]
}

@test "apply needs confirm; one port adds the staff site by name, Koha's files untouched" {
    run lib 'kei_koha_access apply one biblioteca.org.br'
    [ "$status" -eq 4 ] && [ ! -f "$T/calls" ]
    run lib 'kei_koha_access apply one biblioteca.org.br confirm'
    [ "$status" -eq 0 ]
    [ "$(cat "$T/calls")" = $'use koha proxy\nuse koha proxy_http\napply koha koha-staff' ]
    grep -q '^<VirtualHost \*:80>$' "$T/site.conf"
    grep -q '^    ServerName admin.biblioteca.org.br$' "$T/site.conf"
    grep -q '^    ProxyPass / http://127.0.0.1:8080/$' "$T/site.conf"
    grep -q 'Require all granted' "$T/site.conf"
    [ "$(cat "$KEI_OWNED_DIR/koha-access")" = $'mode=one\ndomain=biblioteca.org.br' ]
    run lib 'kei_koha_access status'
    grep -qx '@@result mode=one' <<< "$output" && grep -qx '@@result staff=http://admin.biblioteca.org.br' <<< "$output"
}

@test "staff firewall closed to the internet: the name is limited to the local networks too" {
    printf '#!/bin/sh\necho "8080/tcp                   DENY        Anywhere"\n' > "$T/bin/ufw"; chmod +x "$T/bin/ufw"
    run lib 'kei_koha_access apply one biblioteca.org.br confirm'
    [ "$status" -eq 0 ]
    grep -qx '@@result staff_net=local' <<< "$output"
    grep -q 'Require ip 127.0.0.1 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16' "$T/site.conf"
    ! grep -q 'Require all granted' "$T/site.conf"
}

@test "refused by Apache: the modules go back, the mode stays two" {
    touch "$T/refuse"
    run lib 'kei_koha_access apply one biblioteca.org.br confirm'
    [ "$status" -eq 5 ]
    grep -qx 'release koha proxy_http' "$T/calls" && grep -qx 'release koha proxy' "$T/calls"
    [ ! -f "$KEI_OWNED_DIR/koha-access" ]
    run lib 'kei_koha_access status'
    grep -qx '@@result mode=two' <<< "$output"
}

@test "back to two ports: the site of Koha.Nexus goes, only it" {
    run lib 'kei_koha_access apply one biblioteca.org.br confirm'
    rm -f "$T/calls"
    run lib 'kei_koha_access apply two'
    [ "$status" -eq 4 ] && [ ! -f "$T/calls" ]
    run lib 'kei_koha_access apply two confirm'
    [ "$status" -eq 0 ]
    [ "$(cat "$T/calls")" = $'remove koha koha-staff\nrelease koha proxy_http\nrelease koha proxy' ]
    [ "$(cat "$KEI_OWNED_DIR/koha-access")" = $'mode=two\ndomain=' ]
    # Two ports again with no site of ours: nothing to remove.
    rm -f "$T/calls"
    run lib 'kei_koha_access apply two confirm'
    [ "$status" -eq 0 ]
    ! grep -q remove "$T/calls"
}

@test "Koha missing or a bad action: refused" {
    run lib 'is_koha_installed() { return 1; }; kei_koha_access status'
    [ "$status" -eq 3 ]
    run lib 'kei_koha_access remove'
    [ "$status" -eq 2 ]
    run lib 'kei_koha_access plan three'
    [ "$status" -eq 2 ]
}

@test "addresses screen: with one port the staff by name is listed and tested" {
    printf 'mode=one\ndomain=biblioteca.org.br\n' > "$KEI_OWNED_DIR/koha-access"
    run lib 'is_database_ready() { return 1; }; kei_addresses koha'
    [ "$status" -eq 0 ]
    grep -qx '@@result alternative=staff|http://admin.biblioteca.org.br' <<< "$output"
    grep -qx '@@result alternative=staff|http://192.168.0.20:8080' <<< "$output"
    printf 'mode=two\ndomain=\n' > "$KEI_OWNED_DIR/koha-access"
    run lib 'is_database_ready() { return 1; }; kei_addresses koha'
    ! grep -q 'admin.biblioteca' <<< "$output"
}
