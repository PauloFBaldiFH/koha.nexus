#!/usr/bin/env bats
# Events for Tainacan (installer: kei_tainacan_events_*, _kei_ev_*), the
# parts that need no Docker: the production package of Nexus Eventos (no
# bundled/, no development/, every file checked against the list the
# installer carries), the check of Events Manager against the checksums
# wordpress.org publishes, the plan's decisions (an Events Manager or a
# Nexus Eventos already in the site is preserved), when turning events off
# may turn Events Manager off, the restore note about pass links, and the
# redaction of pass keys and certificate codes in diagnostics. The real
# installation runs in tests/tainacan_events_system.bats.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    T="$BATS_TEST_TMPDIR"
    export KEI_OWNED_DIR="$T/owned" KEI_TAINACAN_DIR="$T/owned/platforms/tainacan" KEI_TAINACAN_BACKUPS="$T/backups"
    mkdir -p "$KEI_TAINACAN_DIR" "$T/bin"
    # No docker or curl on PATH: these tests never reach a real one.
    for c in bash sh awk sed grep cat mkdir mktemp mv rm chmod cp tr head tail cut sort uniq printf date stat \
             sha256sum python3 find wc id ls dirname basename env timeout flock diff; do
        p=$(command -v "$c" 2>/dev/null) && ln -sf "$p" "$T/bin/$c"
    done
}

lib() {
    bash -c "source '$REPO/installer' >/dev/null 2>&1
log() { :; }
SYS_LANG=en
PATH='$T/bin'
$1" 3>&-
}

nope() { ! "$@"; }

@test "package: the list in the installer is the one of the plugin, without bundled/ or development/" {
    run python3 -I "$REPO/tools/nexus-eventos-package.py" check "$REPO/installer"
    echo "$output"
    [ "$status" -eq 0 ]
    run lib '_kei_ev_package_files'
    [ "$status" -eq 0 ]
    [ "$(grep -c . <<< "$output")" -ge 10 ]
    nope grep -E '  (bundled|development)/' <<< "$output"
    grep -q '  nexus-eventos.php$' <<< "$output"
    grep -q '  includes/class-admin.php$' <<< "$output"
    grep -q '  assets/vendor/LICENSE.qrcode$' <<< "$output"
}

@test "package: built from a checkout, folder nexus-eventos/, only the listed files" {
    export KEI_EVENTS_SRC="$REPO/nexus-events-plugin"
    run lib "_kei_ev_build_package '$T/nx.zip'"
    echo "$output"
    [ "$status" -eq 0 ]
    run python3 -I -c 'import sys, zipfile; print("\n".join(zipfile.ZipFile(sys.argv[1]).namelist()))' "$T/nx.zip"
    [ "$status" -eq 0 ]
    nope grep -v '^nexus-eventos/' <<< "$output"
    nope grep -E 'bundled|development|VALIDACAO|ANALISE' <<< "$output"
    [ "$(grep -c . <<< "$output")" = "$(lib '_kei_ev_package_files' | grep -c .)" ]
    # The same package as the tool makes (same files, same bytes).
    python3 -I "$REPO/tools/nexus-eventos-package.py" zip "$T/tool.zip"
    python3 -I - "$T/nx.zip" "$T/tool.zip" <<'EOF'
import sys, zipfile
a, b = (zipfile.ZipFile(p) for p in sys.argv[1:3])
assert sorted(a.namelist()) == sorted(b.namelist())
for n in a.namelist():
    assert a.read(n) == b.read(n), n
EOF
}

@test "package: a changed or missing file is refused, nothing is written" {
    cp -r "$REPO/nexus-events-plugin" "$T/src"
    rm -rf "$T/src/bundled"
    printf '\n// changed\n' >> "$T/src/includes/class-core.php"
    export KEI_EVENTS_SRC="$T/src"
    run lib "_kei_ev_build_package '$T/nx.zip'"
    echo "$output"
    [ "$status" -eq 1 ]
    grep -q 'did not match the list' <<< "$output"
    grep -q 'includes/class-core.php' <<< "$output"
    [ ! -e "$T/nx.zip" ]
    cp "$REPO/nexus-events-plugin/includes/class-core.php" "$T/src/includes/class-core.php"
    rm "$T/src/assets/events.css"
    run lib "_kei_ev_build_package '$T/nx.zip'"
    [ "$status" -eq 1 ]
    grep -q 'assets/events.css' <<< "$output"
    [ ! -e "$T/nx.zip" ]
}

# mkem MODE: an Events Manager package and its checksums in the format
# wordpress.org publishes, the package changed per MODE.
mkem() {
    python3 -I - "$T" "$1" <<'EOF'
import hashlib, json, sys, zipfile
t, mode = sys.argv[1:3]
files = {"events-manager.php": b"<?php /* Plugin Name: Events Manager\nVersion: 7.4.13 */", "classes/em-event.php": b"<?php class EM_Event {}"}
sums = {k: {"md5": hashlib.md5(v).hexdigest(), "sha256": hashlib.sha256(v).hexdigest()} for k, v in files.items()}
z = zipfile.ZipFile(t + "/em.zip", "w")
for k, v in files.items():
    if mode == "changed" and k == "classes/em-event.php":
        v = b"<?php class EM_Event { function x() { eval($_GET['x']); } }"
    z.writestr("events-manager/" + k, v)
if mode == "extra":
    z.writestr("events-manager/shell.php", b"<?php system($_GET['c']);")
z.close()
json.dump({"plugin": "tainacan" if mode == "slug" else "events-manager", "version": "7.4.13", "files": sums}, open(t + "/em.json", "w"))
EOF
}

@test "Events Manager: accepted only when every file matches the checksums of wordpress.org" {
    mkem good
    run lib "kei_wp_verify_plugin events-manager '$T/em.zip' '$T/em.json' 7.4.13"
    [ "$status" -eq 0 ]
    [ "$output" = "ok 2 files" ]
    run lib "kei_wp_verify_plugin events-manager '$T/em.zip' '$T/em.json' 7.4.12"
    [ "$status" -eq 1 ]
    for mode in changed extra slug; do
        mkem "$mode"
        run lib "kei_wp_verify_plugin events-manager '$T/em.zip' '$T/em.json' 7.4.13"
        echo "$mode: $output"
        [ "$status" -eq 1 ]
    done
    # The Tainacan check is the same function.
    mkem good
    run lib "kei_tainacan_verify_plugin '$T/em.zip' '$T/em.json' 7.4.13"
    [ "$status" -eq 1 ]
}

# decide STATE SCAN_LINES...: the plan for a scan (lines with \t).
decide() {
    local state="$1"; shift
    printf '%s\n' "$state" | tr ' ' '\n' | grep . > "$KEI_TAINACAN_DIR/state" || : > "$KEI_TAINACAN_DIR/state"
    printf '%b\n' "$@" > "$T/scan"
    lib "_kei_ev_decide '$T/scan'"
}
D0='dir\tevents-manager\t0'; N0='dir\tnexus-eventos\t0'; D1='dir\tevents-manager\t1'; N1='dir\tnexus-eventos\t1'

@test "plan: a site without events gets both, Events Manager marked as installed by Koha.Nexus" {
    run decide "status=installed" "$D0" "$N0"
    echo "$output"
    [ "$status" -eq 0 ]
    grep -qx $'plan\tenable' <<< "$output"
    grep -qx $'em_action\tinstall' <<< "$output"
    grep -qx $'em_origin\tours' <<< "$output"
    grep -qx $'nx_action\tinstall' <<< "$output"
}

@test "plan: an Events Manager already in the site is kept, never replaced or downgraded" {
    run decide "status=installed" 'em\tevents-manager/events-manager.php\t7.4.13\tactive' "$D1" "$N0"
    [ "$status" -eq 0 ]
    grep -qx $'em_action\tkeep' <<< "$output"
    grep -qx $'em_origin\tpreexisting' <<< "$output"
    grep -q 'turning events off later does not turn it off' <<< "$output"
    run decide "status=installed" 'em\tevents-manager/events-manager.php\t7.5.2\tinactive' "$D1" "$N0"
    [ "$status" -eq 0 ]
    grep -qx $'em_action\tactivate' <<< "$output"
    grep -qx $'em_origin\tpreexisting' <<< "$output"
    # In another folder: that one is used.
    run decide "status=installed" 'em\tevents-manager-x/events-manager.php\t7.4.13\tinactive' "$D0" "$N0"
    [ "$status" -eq 0 ]
    grep -qx $'em_file\tevents-manager-x/events-manager.php' <<< "$output"
    # Older than needed: refused, not replaced.
    run decide "status=installed" 'em\tevents-manager/events-manager.php\t7.3.1\tactive' "$D1" "$N0"
    [ "$status" -eq 3 ]
    grep -qx $'plan\trefuse' <<< "$output"
    grep -q 'It was not replaced' <<< "$output"
    # A folder without a working plugin, and two copies: left as they are.
    run decide "status=installed" "$D1" "$N0"
    [ "$status" -eq 3 ]
    run decide "status=installed" 'em\tevents-manager/events-manager.php\t7.4.13\tactive' 'em\tem2/events-manager.php\t7.4.13\tinactive' "$D1" "$N0"
    [ "$status" -eq 3 ]
}

@test "plan: one Koha.Nexus installed stays its own across enable and disable" {
    run decide "status=installed events_em=ours events_plugin=0.1.1" 'em\tevents-manager/events-manager.php\t7.4.13\tinactive' \
        'nx\tnexus-eventos/nexus-eventos.php\t0.1.1\tinactive' "$D1" "$N1"
    [ "$status" -eq 0 ]
    grep -qx $'em_origin\tours' <<< "$output"
    grep -qx $'em_action\tactivate' <<< "$output"
    grep -qx $'nx_action\tkeep' <<< "$output"
    run decide "status=installed events_em=ours events_plugin=0.1.0" 'em\tevents-manager/events-manager.php\t7.4.13\tactive' \
        'nx\tnexus-eventos/nexus-eventos.php\t0.1.0\tactive' "$D1" "$N1"
    [ "$status" -eq 0 ]
    grep -qx $'nx_action\tupdate' <<< "$output"
}

@test "plan: a Nexus Eventos put in by hand is preserved" {
    # The repository folder copied as it is (the old instructions).
    run decide "status=installed" 'nx\tnexus-events-plugin/nexus-eventos.php\t0.1.0\tactive' "$D0" "$N0"
    [ "$status" -eq 3 ]
    grep -q 'folder nexus-events-plugin' <<< "$output"
    # In the right folder, but not installed by Koha.Nexus.
    run decide "status=installed" 'nx\tnexus-eventos/nexus-eventos.php\t0.1.1\tinactive' "$D0" "$N1"
    [ "$status" -eq 3 ]
    grep -q 'put in this WordPress by hand' <<< "$output"
    run decide "status=installed" "$D0" "$N1"
    [ "$status" -eq 3 ]
}

@test "disable: Events Manager is turned off only when Koha.Nexus installed it, or when asked explicitly" {
    run lib '_kei_ev_turn_off_em ours ""'; [ "$status" -eq 0 ]
    run lib '_kei_ev_turn_off_em ours keep-dependency'; [ "$status" -eq 1 ]
    run lib '_kei_ev_turn_off_em ours dependency'; [ "$status" -eq 0 ]
    run lib '_kei_ev_turn_off_em preexisting ""'; [ "$status" -eq 1 ]
    run lib '_kei_ev_turn_off_em preexisting keep-dependency'; [ "$status" -eq 1 ]
    run lib '_kei_ev_turn_off_em preexisting dependency'; [ "$status" -eq 0 ]
    run lib '_kei_ev_turn_off_em "" ""'; [ "$status" -eq 1 ]
    run lib 'kei_tainacan_events_disable whatever'
    [ "$status" -eq 2 ]
}

@test "enable: nothing changes without confirm" {
    printf 'status=installed\n' > "$KEI_TAINACAN_DIR/state"
    run lib 'kei_tainacan_events_enable'
    [ "$status" -eq 3 ]
    grep -q 'plan needs a yes' <<< "$output"
    [ "$(cat "$KEI_TAINACAN_DIR/state")" = "status=installed" ]
}

# backup DIR KEY=VALUE...: a manifest.json with these fields.
backup() {
    local d="$T/backups/$1"; shift
    mkdir -p "$d"
    { echo '{'; for kv in "$@"; do printf '  "%s": %s,\n' "${kv%%=*}" "${kv#*=}"; done; echo '  "format": 2'; echo '}'; } > "$d/manifest.json"
    printf '%s' "$d"
}

@test "restore note: pass links already sent, when the keys differ and there is no phrase" {
    printf 'KN_AUTH_KEY=aaaa\nKN_AUTH_SALT=bbbb\n' > "$KEI_TAINACAN_DIR/.env"
    fp=$(lib '_kei_ev_keys_fp')
    [[ "$fp" =~ ^[0-9a-f]{16}$ ]]
    nope grep -q 'aaaa' <<< "$fp"
    # Another key, another fingerprint.
    printf 'KN_AUTH_KEY=aaaa\nKN_AUTH_SALT=cccc\n' > "$T/other.env"; mkdir -p "$T/o"; mv "$T/other.env" "$T/o/.env"
    [ "$(lib "_kei_ev_keys_fp '$T/o'")" != "$fp" ]
    b=$(backup other count_passes=3 'pass_keys_fingerprint="0123456789abcdef"')
    run lib "kei_tainacan_restore_notes '$b' nophrase"
    echo "$output"
    [ "$status" -eq 0 ]
    grep -q 'the 3 event pass links already sent stop working' <<< "$output"
    run lib "kei_tainacan_restore_notes '$b' phrase"
    [ -z "$output" ]
    # Same keys (a backup of this installation): nothing is lost.
    b=$(backup same count_passes=3 "pass_keys_fingerprint=\"$fp\"")
    run lib "kei_tainacan_restore_notes '$b' nophrase"
    [ -z "$output" ]
    # No eligible booking, or a backup without event data: nothing to say.
    b=$(backup none count_passes=0 'pass_keys_fingerprint="0123456789abcdef"' count_attendance=0)
    run lib "kei_tainacan_restore_notes '$b' nophrase"
    [ -z "$output" ]
    b=$(backup old count_items=1)
    run lib "kei_tainacan_restore_notes '$b' nophrase"
    [ -z "$output" ]
    # Counted passes, no fingerprint (cannot tell): said.
    b=$(backup nofp count_passes=2)
    run lib "kei_tainacan_restore_notes '$b' nophrase"
    grep -q 'the 2 event pass links' <<< "$output"
}

@test "diagnostics: pass keys and certificate codes are redacted" {
    k=3f1c9a0b7d2e4f60a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718
    run lib "printf '%s\n' '172.18.0.1 - - \"GET /?nxev_pass=12&nxev_key=$k HTTP/1.1\" 200' '\"GET /?nxev_verify=$k\" 200' '{\"nxev_key\": \"$k\"}' 'GET /?q=%3Fnxev_key%3D$k' 'nothing secret here' | kei_redact"
    echo "$output"
    [ "$status" -eq 0 ]
    nope grep -q "$k" <<< "$output"
    [ "$(grep -c 'REDACTED' <<< "$output")" -ge 4 ]
    grep -qx 'nothing secret here' <<< "$output"
}

@test "tasks: tainacan-events and tainacan-restore-notes are known to the installer" {
    grep -q '^        tainacan-events)$' "$REPO/installer"
    grep -q '^        tainacan-restore-notes)$' "$REPO/installer"
}

@test "the copy in nexus-events-plugin/bundled (development only) is the Events Manager 7.4.13 of wordpress.org" {
    if ! curl -fsSL --max-time 30 -o "$T/em.json" "https://downloads.wordpress.org/plugin-checksums/events-manager/7.4.13.json" 2>/dev/null; then
        [ "${KEI_REQUIRE_REAL_EVENTS:-}" = 1 ] && { echo "wordpress.org unreachable and the check is required"; return 1; }
        skip "wordpress.org unreachable"
    fi
    run python3 -I - "$REPO/nexus-events-plugin/bundled/events-manager" "$T/em.json" <<'PYEOF'
import hashlib, json, os, sys
root, data = sys.argv[1], json.load(open(sys.argv[2]))
assert data.get("plugin") == "events-manager" and str(data.get("version")) == "7.4.13", data.get("version")
sums = data["files"]
have = {}
for dp, dn, fn in os.walk(root):
    for f in fn:
        p = os.path.join(dp, f)
        have[os.path.relpath(p, root).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
want = lambda v: v["sha256"] if isinstance(v["sha256"], list) else [v["sha256"]]
extra = sorted(set(have) - set(sums)); missing = sorted(set(sums) - set(have))
bad = sorted(k for k in set(have) & set(sums) if have[k] not in want(sums[k]))
print("files %d, published %d, extra %d, missing %d, different %d" % (len(have), len(sums), len(extra), len(missing), len(bad)))
for k in (extra + missing + bad)[:20]: print(" ", k)
sys.exit(1 if extra or missing or bad else 0)
PYEOF
    echo "$output" >&3
    [ "$status" -eq 0 ]
}
