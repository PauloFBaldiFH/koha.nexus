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

# Koha's own addresses (OPACBaseURL, staffClientBaseURL) in a file database:
# PREF=VALUE lines; writes are logged.
prefs() {
    printf '%s\n' "is_database_ready() { return 0; }
DB_NAME=koha_library
run_sql() { sed -n \"s/^\$(sed -n \"s/.*variable='\\([A-Za-z]*\\)'.*/\\1/p\" <<< \"\$1\")=//p\" '$T/prefs'; }
_kei_koha_set_pref() { echo \"pref \$1=\$2\" >> '$T/calls'; grep -v \"^\$1=\" '$T/prefs' > '$T/prefs.new'; echo \"\$1=\$2\" >> '$T/prefs.new'; mv '$T/prefs.new' '$T/prefs'; }
plack_restart() { echo plack >> '$T/calls'; }
systemctl() { echo \"systemctl \$*\" >> '$T/calls'; }"
}

@test "Koha's addresses follow one port and come back with two" {
    printf 'OPACBaseURL=http://192.168.0.20\nstaffClientBaseURL=\n' > "$T/prefs"
    run lib "$(prefs)
kei_koha_access plan one biblioteca.org.br"
    grep -qx '@@result base=opac|http://192.168.0.20|http://biblioteca.org.br|change' <<< "$output"
    grep -qx '@@result base=staff||http://admin.biblioteca.org.br|change' <<< "$output"
    [ ! -f "$T/calls" ]
    run lib "$(prefs)
kei_koha_access apply one biblioteca.org.br confirm"
    [ "$status" -eq 0 ]
    grep -qx 'OPACBaseURL=http://biblioteca.org.br' "$T/prefs"
    grep -qx 'staffClientBaseURL=http://admin.biblioteca.org.br' "$T/prefs"
    grep -qx plack "$T/calls"
    grep -qx 'prev_opac=http://192.168.0.20' "$KEI_OWNED_DIR/koha-access"
    grep -qx 'set_staff=http://admin.biblioteca.org.br' "$KEI_OWNED_DIR/koha-access"
    # Another domain: what came before is still the IP.
    run lib "$(prefs)
kei_koha_access apply one acervo.example.org confirm"
    grep -qx 'OPACBaseURL=http://acervo.example.org' "$T/prefs"
    grep -qx 'prev_opac=http://192.168.0.20' "$KEI_OWNED_DIR/koha-access"
    run lib "$(prefs)
kei_koha_access plan two"
    grep -qx '@@result base=opac|http://acervo.example.org|http://192.168.0.20|restore' <<< "$output"
    run lib "$(prefs)
kei_koha_access apply two confirm"
    [ "$status" -eq 0 ]
    grep -qx 'OPACBaseURL=http://192.168.0.20' "$T/prefs"
    grep -qx 'staffClientBaseURL=' "$T/prefs"
    ! grep -q '^prev_\|^set_' "$KEI_OWNED_DIR/koha-access"
}

@test "Koha's addresses: a public name is kept; a value changed by hand is not put back" {
    printf 'OPACBaseURL=https://catalogo.koha.nexus\nstaffClientBaseURL=http://192.168.0.20:8080\n' > "$T/prefs"
    run lib "$(prefs)
kei_koha_access apply one biblioteca.org.br confirm"
    [ "$status" -eq 0 ]
    grep -qx '@@result base=opac|https://catalogo.koha.nexus|https://catalogo.koha.nexus|keep' <<< "$output"
    grep -qx 'OPACBaseURL=https://catalogo.koha.nexus' "$T/prefs"
    grep -qx 'staffClientBaseURL=http://admin.biblioteca.org.br' "$T/prefs"
    ! grep -q '^prev_opac' "$KEI_OWNED_DIR/koha-access"
    # Changed by hand while on one port: two ports leaves it as it is.
    sed -i 's|^staffClientBaseURL=.*|staffClientBaseURL=https://equipe.example.org|' "$T/prefs"
    rm -f "$T/calls"
    run lib "$(prefs)
kei_koha_access apply two confirm"
    grep -qx '@@result base=staff|https://equipe.example.org|https://equipe.example.org|same' <<< "$output"
    grep -qx 'staffClientBaseURL=https://equipe.example.org' "$T/prefs"
    ! grep -q '^pref ' "$T/calls" && ! grep -qx plack "$T/calls"
}

@test "Koha's addresses: a preference that cannot be written is said; the site stays" {
    printf 'OPACBaseURL=\nstaffClientBaseURL=\n' > "$T/prefs"
    run lib "$(prefs)
_kei_koha_set_pref() { return 1; }
kei_koha_access apply one biblioteca.org.br confirm"
    [ "$status" -eq 0 ]
    grep -qx '@@result base_failed=OPACBaseURL' <<< "$output"
    grep -qx 'mode=one' "$KEI_OWNED_DIR/koha-access"
    ! grep -q '^set_' "$KEI_OWNED_DIR/koha-access"
}

@test "a preference value goes into SQL with its quotes doubled" {
    printf '#!/bin/sh\nprintf "%%s\\n" "$2" > "%s/sql"\n' "$T" > "$T/bin/mysql"; chmod +x "$T/bin/mysql"
    run lib "DB_NAME=koha_library
_kei_koha_set_pref OPACBaseURL \"http://x.org/a'b\\\\c\""
    [ "$status" -eq 0 ]
    grep -qF "VALUES ('OPACBaseURL', 'http://x.org/a''b\\\\c', 'Free')" "$T/sql"
}
