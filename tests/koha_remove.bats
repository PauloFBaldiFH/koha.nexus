#!/usr/bin/env bats
# Removing Koha (U11, study 17.3): kei_koha_remove. The plan only reads;
# nothing goes without a complete package that passed its check; the
# scheduled tasks are moved aside, not deleted; packages, firewall, tunnel
# and the other systems are not touched. The package, the check and the
# removal are stubbed here; tests/koha_set_system.bats runs it with a real
# Koha and a real Tainacan.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_BK_ROOT="$T/backups"
    mkdir -p "$T/bin" "$KEI_OWNED_DIR" "$T/cron"
    for c in bash sh awk sed grep cat mkdir mktemp mv rm chmod cp tr head tail cut sort printf date env python3 flock ls touch; do
        p=$(command -v "$c" 2>/dev/null) && ln -sf "$p" "$T/bin/$c"
    done
    printf '#!/bin/sh\necho 24.05.06-1\n' > "$T/bin/dpkg-query"; chmod +x "$T/bin/dpkg-query"
    for f in koha_tasks koha_zebra_queue koha_es_watchdog koha_sitemap; do echo "# $f" > "$T/cron/$f"; done
    echo "<config></config>" > "$T/koha-conf.xml"
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
kei_result() { printf '@@result %s=%s\n' \"\$1\" \"\$2\"; }
msg_error() { printf 'ERROR %s\n' \"\$2\"; }
is_koha_installed() { [ ! -f '$T/gone' ]; }
INSTANCE=library DB_NAME=koha_library KEI_APACHE_DIR=/etc/apache2 KOHA_CONF='$T/koha-conf.xml'
CRON_TASKS='$T/cron/koha_tasks' CRON_ZEBRA='$T/cron/koha_zebra_queue' CRON_ES='$T/cron/koha_es_watchdog'
CRON_BROKER='$T/cron/koha_broker' CRON_SITEMAP='$T/cron/koha_sitemap' CRON_MSG='$T/cron/koha_messaging' CRON_OPAC='$T/cron/koha_kei_opac'
kei_set_platforms() { echo 'koha tainacan'; }
_kei_dspace_port() { :; }
_kei_bk_has_key() { [ ! -f '$T/nokey' ]; }
kei_set_backup() {
    echo \"set \$*\" >> '$T/calls'
    [ -f '$T/nokey' ] && [ \"\$3\" != no-secrets ] && { echo needs=key; return 7; }
    [ -f '$T/badset' ] && { echo 'platform=koha	failed'; echo 'MariaDB said no' >&2; return 9; }
    : > \"\$1/knx-set-1.tar\"; printf 'size=1M\ncomplete=yes\nrecoverability=full\nfile=%s\n' \"\$1/knx-set-1.tar\"
}
kei_set_inspect() {
    echo \"inspect \$1\" >> '$T/calls'
    if [ -f '$T/badcheck' ]; then echo integrity=failed; else printf 'kind=koha-nexus-set\ncomplete=yes\nintegrity=ok\nplatforms=koha\n'; fi
}
backup_lock_acquire() { echo lock >> '$T/calls'; }
backup_lock_release() { echo unlock >> '$T/calls'; }
install_task_remove_previous() { echo remove >> '$T/calls'; [ -f '$T/rmfail' ] && return 3; touch '$T/gone'; }
KEI_PLATFORM=linux
PATH='$T/bin'
$1" 3>&-
}

@test "plan: what goes and what stays; it only reads" {
    run lib 'kei_koha_remove plan'
    [ "$status" -eq 0 ]
    grep -qx '@@result instance=library' <<< "$output"
    grep -qx '@@result version=24.05.06' <<< "$output"
    grep -qx '@@result go=instance|/etc/koha/sites/library' <<< "$output"
    grep -qx '@@result go=database|koha_library' <<< "$output"
    grep -qx "@@result go=cron|$T/cron/koha_tasks" <<< "$output"
    [ "$(grep -c '^@@result go=cron|' <<< "$output")" = 4 ]
    for k in packages firewall tunnel backups files; do grep -qx "@@result keep=$k" <<< "$output"; done
    grep -qx '@@result others=tainacan' <<< "$output"
    grep -qx '@@result secrets=with' <<< "$output"
    [ ! -f "$T/calls" ] && [ -f "$T/cron/koha_tasks" ]
}

@test "apply needs keep and confirm; Koha missing or bad words: refused" {
    run lib 'kei_koha_remove apply keep'
    [ "$status" -eq 4 ] && [ ! -f "$T/calls" ]
    run lib 'kei_koha_remove apply delete confirm'
    [ "$status" -eq 2 ]
    run lib 'kei_koha_remove apply keep confirm everything'
    [ "$status" -eq 2 ]
    run lib 'kei_koha_remove wipe'
    [ "$status" -eq 2 ]
    touch "$T/gone"
    run lib 'kei_koha_remove plan'
    [ "$status" -eq 3 ]
    [ ! -f "$T/calls" ]
}

@test "remove keeping the data: package, check, then removal; tasks moved aside" {
    run lib 'kei_koha_remove apply keep confirm'
    [ "$status" -eq 0 ]
    [ "$(cat "$T/calls")" = "set $KEI_BK_ROOT koha "$'\n'"inspect $KEI_BK_ROOT/knx-set-1.tar"$'\n'"lock"$'\n'"remove"$'\n'"unlock" ]
    grep -qx "@@result package=$KEI_BK_ROOT/knx-set-1.tar" <<< "$output"
    grep -qx '@@result removed=yes' <<< "$output"
    aside=$(sed -n 's/^@@result aside=//p' <<< "$output")
    [ -f "$aside/cron/koha_tasks" ] && [ -f "$aside/cron/koha_sitemap" ] && [ ! -e "$T/cron/koha_tasks" ]
    grep -qx "package=$KEI_BK_ROOT/knx-set-1.tar" "$aside/removed"
    grep -qx 'version=24.05.06' "$aside/removed"
}

@test "no package, or a package that fails its check: nothing removed" {
    touch "$T/badset"
    run lib 'kei_koha_remove apply keep confirm'
    [ "$status" -eq 6 ]
    grep -q 'Nothing was removed' <<< "$output"
    ! grep -qx remove "$T/calls" && [ -f "$T/cron/koha_tasks" ]
    rm -f "$T/badset" "$T/calls"
    touch "$T/badcheck"
    run lib 'kei_koha_remove apply keep confirm'
    [ "$status" -eq 6 ]
    grep -q 'did not pass its check' <<< "$output"
    ! grep -qx remove "$T/calls" && ! grep -qx lock "$T/calls" && [ -f "$T/cron/koha_tasks" ]
    ! grep -q '@@result package=' <<< "$output"
}

@test "no backup key: stops before anything; a package without the secrets when chosen" {
    touch "$T/nokey"
    run lib 'kei_koha_remove plan'
    grep -qx '@@result secrets=needs-choice' <<< "$output"
    run lib 'kei_koha_remove apply keep confirm'
    [ "$status" -eq 7 ]
    ! grep -qx remove "$T/calls"
    rm -f "$T/calls"
    run lib 'kei_koha_remove apply keep confirm no-secrets'
    [ "$status" -eq 0 ]
    grep -qx "set $KEI_BK_ROOT koha no-secrets" "$T/calls"
}

@test "the removal stops part way: said, the package is kept" {
    touch "$T/rmfail"
    run lib 'kei_koha_remove apply keep confirm'
    [ "$status" -eq 8 ]
    grep -q 'could not be removed completely. The package is kept.' <<< "$output"
    grep -qx "@@result package=$KEI_BK_ROOT/knx-set-1.tar" <<< "$output"
    [ -f "$KEI_BK_ROOT/knx-set-1.tar" ]
    grep -qx unlock "$T/calls"
}

@test "the staff site by name (U10) goes with Koha" {
    printf 'mode=one\ndomain=biblioteca.org.br\n' > "$KEI_OWNED_DIR/koha-access"
    run lib '_kei_koha_staff_ours() { [ ! -f "'"$T"'/site-gone" ]; }
kei_koha_access() { echo "access $*" >> "'"$T"'/calls"; touch "'"$T"'/site-gone"; }
kei_koha_remove plan'
    grep -q '^@@result go=apache-site|/etc/apache2/sites-available/zz-koha-nexus-koha-staff.conf$' <<< "$output"
    run lib '_kei_koha_staff_ours() { [ ! -f "'"$T"'/site-gone" ]; }
kei_koha_access() { echo "access $*" >> "'"$T"'/calls"; touch "'"$T"'/site-gone"; }
kei_koha_remove apply keep confirm'
    [ "$status" -eq 0 ]
    grep -qx 'access apply two confirm' "$T/calls"
    [ ! -f "$KEI_OWNED_DIR/koha-access" ]
}
