#!/usr/bin/env bats
# OPAC appearance (section 40): the panel's screen writes a folder with the
# two marked blocks (user.css, user.js), a few preferences, the pictures and
# the carousel switch; `config.sh --task opac-theme-apply DIR` puts them in
# Koha on a real MariaDB, keeping the rest of OpacUserCSS / OpacUserJS. The
# "New arrivals" job runs for real against SQLite and a local cover server.
# The CSS/JS themselves are Python: panel/tests/test_opac_theme.py.

setup_file() {
    load lib/common
    kei_start_mariadb
    mysql -e "CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4;"
    # Covers: two real ones, and Amazon's 43-byte "no cover" picture.
    COVERS="$BATS_FILE_TMPDIR/covers"
    mkdir -p "$COVERS"
    head -c 4000 /dev/urandom > "$COVERS/0306406152.01.LZZZZZZZ.jpg"
    head -c 4000 /dev/urandom > "$COVERS/8535902775.01.LZZZZZZZ.jpg"
    head -c 43 /dev/urandom > "$COVERS/0131103628.01.LZZZZZZZ.jpg"
    PORT=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
    echo "$PORT" > "$BATS_FILE_TMPDIR/port"
    kei_detached python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$COVERS"
    local i
    for i in $(seq 1 50); do
        python3 -c "import socket; socket.create_connection(('127.0.0.1', $PORT), 1)" 2>/dev/null && break
        sleep 0.1
    done
}

teardown_file() {
    pkill -f "http.server $(cat "$BATS_FILE_TMPDIR/port") " 2>/dev/null || true
}

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    rm -f "$KEI_S/dialogs.log"
    mysql "$DB" -e "DROP TABLE IF EXISTS systempreferences;
CREATE TABLE systempreferences (variable varchar(50) NOT NULL PRIMARY KEY, value mediumtext, options longtext,
  explanation mediumtext, type varchar(20)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO systempreferences (variable, value) VALUES
  ('OpacUserCSS', '#mine { color: red; }'), ('OpacUserJS', 'console.log(\"mine\");'),
  ('OPACAmazonCoverImages', '0'), ('AmazonAssocTag', ''), ('OpacFavicon', ''), ('OpacNav', 'keep'),
  ('IntranetUserCSS', '#staff { color: navy; }'), ('IntranetFavicon', '');"
    mkdir -p "$W/custom" "$W/work"
    cat > "$W/extra.sh" <<SH
SYS_LANG=en
kei_result() { printf 'RESULT %s=%s\n' "\$1" "\$2" >> "$W/results"; }
require_database() { return 0; }
is_koha_installed() { return 0; }
tools_locked() { TOOLS_WORK="$W/work"; "\$@"; }
tools_safety_backup() { TOOLS_PRE="$W/PRE-\$1.sql.gz"; echo "\$1" >> "$W/backups"; }
memcached_flush() { return 0; }
TOOLS_LOG_DIR="$W/logs"
OPAC_CUSTOM_DIR="$W/custom"
STAFF_CUSTOM_DIR="$W/staff-custom"
OPAC_NA_BIN="$W/koha-kei-new-arrivals"
CRON_OPAC="$W/cron"
THEME_STATE="$W/etc/theme-settings.json"
LOG_DIR="$W/logs"
SH
    apply_dir "$W/apply" "a { color: blue; }" "off"
}

# apply_dir DIR CSS CAROUSEL: a folder as the panel writes it.
apply_dir() {
    mkdir -p "$1/assets"
    printf '%s\n%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" \
        '/* KEI-THEME-DATA: {"texture": "frosted", "version": 1} */' "$2" \
        "/* koha-easy-installer opac-theme end */" > "$1/user.css"
    printf '%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" "(function () { var x = 1; })();" \
        "/* koha-easy-installer opac-theme end */" > "$1/user.js"
    printf 'OPACAmazonCoverImages\t1\nAmazonAssocTag\tmytag-20\nOpacFavicon\t/images/custom/kei-favicon.png?v=abc\n' > "$1/prefs"
    printf '%s\n' "$3" > "$1/carousel"
    printf '\x89PNG\r\n\x1a\nfake' > "$1/assets/kei-favicon.png"
    printf '\xff\xd8\xff\xe0fake' > "$1/assets/kei-background.jpg"
}

pref() { mysql -N --raw "$DB" -e "SELECT value FROM systempreferences WHERE variable = '$1'"; }
task() { run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" "$@"; echo "$output"; cat "$KEI_S/dialogs.log" 2>/dev/null || true; }

@test "opac-theme-apply: both blocks go in after the library's own CSS and JS" {
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS | head -n1)" = "#mine { color: red; }" ]
    pref OpacUserCSS | grep -qxF "a { color: blue; }"
    pref OpacUserJS | grep -qF 'console.log("mine");'
    pref OpacUserJS | grep -qF "(function () { var x = 1; })();"
    [ "$(pref OPACAmazonCoverImages)" = "1" ]
    [ "$(pref AmazonAssocTag)" = "mytag-20" ]
    [ "$(pref OpacFavicon)" = "/images/custom/kei-favicon.png?v=abc" ]
    [ "$(pref OpacNav)" = "keep" ]
    [ -f "$W/custom/kei-favicon.png" ] && [ -f "$W/custom/kei-background.jpg" ]
    [ "$(stat -c %a "$W/custom/kei-favicon.png")" = "644" ]
    [ "$(cat "$W/backups")" = "OPAC-THEME" ]
    grep -q "OK .*new look is in the OPAC" "$KEI_S/dialogs.log"
    grep -q "RESULT applied=yes" "$W/results"
}

@test "opac-theme-apply: a second run replaces the block instead of adding one" {
    task opac_theme_apply "$W/apply"
    apply_dir "$W/apply2" "a { color: green; }" "off"
    printf '\xff\xd8\xff\xe0new' > "$W/apply2/assets/kei-favicon.jpg"
    rm -f "$W/apply2/assets/kei-favicon.png"
    task opac_theme_apply "$W/apply2"
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS | grep -c 'opac-theme begin')" = "1" ]
    ! pref OpacUserCSS | grep -q "color: blue"
    pref OpacUserCSS | grep -q "color: green"
    [ "$(pref OpacUserCSS | head -n1)" = "#mine { color: red; }" ]
    # The favicon changed format: the old file went, only the new one is there.
    [ ! -e "$W/custom/kei-favicon.png" ] && [ -f "$W/custom/kei-favicon.jpg" ]
}

@test "opac-theme-get: hands back the settings line for the panel" {
    task opac_theme_apply "$W/apply"
    rm -f "$W/results"
    task opac_theme_get
    [ "$status" -eq 0 ]
    grep -qF 'RESULT data=/* KEI-THEME-DATA: {"texture": "frosted", "version": 1} */' "$W/results"
    grep -q "RESULT amazon=1" "$W/results"
    ! grep -q "RESULT carousel=" "$W/results"
}

@test "opac-theme-apply: damaged or unsafe folders change nothing" {
    printf '/* koha-easy-installer opac-theme begin */\n</style><script>alert(1)</script>\n/* koha-easy-installer opac-theme end */\n' > "$W/apply/user.css"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 1 ]
    grep -q "ERROR .*missing or damaged" "$KEI_S/dialogs.log"
    [ "$(pref OpacUserCSS)" = "#mine { color: red; }" ]

    apply_dir "$W/b" "a { }" "off"
    printf '<svg onload=alert(1)>' > "$W/b/assets/kei-logo.svg"
    task opac_theme_apply "$W/b"
    [ "$status" -eq 1 ]
    apply_dir "$W/c" "a { }" "off"
    ln -s /etc/passwd "$W/c/assets/kei-logo.png"
    task opac_theme_apply "$W/c"
    [ "$status" -eq 1 ]
    [ ! -e "$W/custom/kei-logo.png" ]
    [ ! -e "$W/backups" ]
}

@test "opac-theme-apply: only the allowed preferences and values are written" {
    printf 'OPACAmazonCoverImages\t7\nAmazonAssocTag\tx'"'"'; DROP TABLE x\nOpacFavicon\tjavascript:alert(1)\nOpacNav\tchanged\n' > "$W/apply/prefs"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ "$(pref OPACAmazonCoverImages)" = "0" ]
    [ "$(pref AmazonAssocTag)" = "" ]
    [ "$(pref OpacFavicon)" = "" ]
    [ "$(pref OpacNav)" = "keep" ]
}

@test "opac-theme-remove: Koha's own look back, the library's CSS and JS kept" {
    task opac_theme_apply "$W/apply"
    touch "$W/cron" "$W/koha-kei-new-arrivals" "$W/custom/kei-new-arrivals.json" "$W/custom/library.png"
    task opac_theme_remove
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS)" = "#mine { color: red; }" ]
    [ "$(pref OpacUserJS)" = 'console.log("mine");' ]
    [ "$(pref OpacFavicon)" = "" ]
    [ ! -e "$W/custom/kei-favicon.png" ] && [ ! -e "$W/custom/kei-background.jpg" ]
    [ ! -e "$W/cron" ] && [ ! -e "$W/koha-kei-new-arrivals" ] && [ ! -e "$W/custom/kei-new-arrivals.json" ]
    # Pictures the panel did not put there stay.
    [ -f "$W/custom/library.png" ]
    grep -q "OK .*back to Koha's own look" "$KEI_S/dialogs.log"
}

@test "opac-theme-remove: a favicon the library chose itself is kept" {
    mysql "$DB" -e "UPDATE systempreferences SET value = 'https://example.org/f.ico' WHERE variable = 'OpacFavicon'"
    task opac_theme_remove
    [ "$status" -eq 0 ]
    [ "$(pref OpacFavicon)" = "https://example.org/f.ico" ]
}

@test "opac-theme-apply: the staff interface's own pictures go to its web root, and out with remove" {
    printf '\x89PNG\r\n\x1a\nfake' > "$W/apply/assets/kei-staff-logo.png"
    printf '\x00\x00\x01\x00fake' > "$W/apply/assets/kei-staff-favicon.ico"
    printf 'IntranetFavicon\t/intranet-tmpl/kei-custom/kei-staff-favicon.ico?v=1\n' >> "$W/apply/prefs"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ -f "$W/staff-custom/kei-staff-logo.png" ] && [ -f "$W/staff-custom/kei-staff-favicon.ico" ]
    [ ! -e "$W/custom/kei-staff-logo.png" ]
    [ "$(pref IntranetFavicon)" = "/intranet-tmpl/kei-custom/kei-staff-favicon.ico?v=1" ]
    task opac_theme_remove
    [ "$status" -eq 0 ]
    [ "$(pref IntranetFavicon)" = "" ]
    [ ! -e "$W/staff-custom/kei-staff-logo.png" ] && [ ! -e "$W/staff-custom/kei-staff-favicon.ico" ]
}

@test "opac-theme-apply: a staff favicon outside the staff folder or https is refused" {
    printf 'IntranetFavicon\tjavascript:alert(1)\nIntranetFavicon\t/images/custom/kei-favicon.png\n' >> "$W/apply/prefs"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ "$(pref IntranetFavicon)" = "" ]
}

@test "opac-theme-apply: staff.css goes in IntranetUserCSS, and out again without it" {
    printf '%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" ".navbar { background: #123456; }" \
        "/* koha-easy-installer opac-theme end */" > "$W/apply/staff.css"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ "$(pref IntranetUserCSS | head -n1)" = "#staff { color: navy; }" ]
    pref IntranetUserCSS | grep -qF ".navbar { background: #123456; }"
    rm "$W/apply/staff.css"
    task opac_theme_apply "$W/apply"
    [ "$(pref IntranetUserCSS)" = "#staff { color: navy; }" ]
}

@test "theme-settings.json: saved by apply, written back after a restore, gone with remove" {
    printf '%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" ".navbar { background: #123456; }" \
        "/* koha-easy-installer opac-theme end */" > "$W/apply/staff.css"
    task opac_theme_apply "$W/apply"
    [ -s "$W/etc/theme-settings.json" ]
    python3 - "$W/etc/theme-settings.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert s["settings"] == {"texture": "frosted", "version": 1}, s
assert set(s["blocks"]) == {"OpacUserCSS", "OpacUserJS", "IntranetUserCSS"}, s
assert ["AmazonAssocTag", "mytag-20"] in s["prefs"] and s["carousel"] == "off", s
PY
    # A restore brings back the backup's preferences: the look is gone.
    mysql "$DB" -e "UPDATE systempreferences SET value = '#old { }' WHERE variable = 'OpacUserCSS';
UPDATE systempreferences SET value = '' WHERE variable IN ('OpacUserJS', 'IntranetUserCSS', 'AmazonAssocTag');"
    rm -f "$W/results"
    task theme_state_reapply
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS | head -n1)" = "#old { }" ]
    pref OpacUserCSS | grep -qxF "a { color: blue; }"
    [ "$(pref OpacUserCSS | grep -c 'opac-theme begin')" = "1" ]
    pref OpacUserJS | grep -qF "(function () { var x = 1; })();"
    pref IntranetUserCSS | grep -qF ".navbar { background: #123456; }"
    [ "$(pref AmazonAssocTag)" = "mytag-20" ]
    grep -q "RESULT theme_reapplied=yes" "$W/results"
    # Twice is the same as once.
    task theme_state_reapply
    [ "$(pref OpacUserCSS | grep -c 'opac-theme begin')" = "1" ]
    task opac_theme_remove
    [ ! -e "$W/etc/theme-settings.json" ]
    [ "$(pref IntranetUserCSS)" = "" ]
}

@test "theme-settings.json: nothing saved or a damaged file changes nothing" {
    task theme_state_reapply
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS)" = "#mine { color: red; }" ]
    mkdir -p "$W/etc"
    printf '{"blocks": {"OpacUserCSS": "</style><script>alert(1)</script>", "OpacUserJS": "x"}}' > "$W/etc/theme-settings.json"
    task theme_state_reapply
    [ "$status" -eq 1 ]
    [ "$(pref OpacUserCSS)" = "#mine { color: red; }" ]
    printf 'not json' > "$W/etc/theme-settings.json"
    task theme_state_reapply
    [ "$status" -eq 1 ]
    [ "$(pref OpacUserCSS)" = "#mine { color: red; }" ]
}

@test "restore database: the saved look goes back in before Koha restarts" {
    reapply=$(grep -n 'tui_run .*theme_state_reapply' "$KEI_REPO/installer" | head -n1 | cut -d: -f1)
    resume=$(awk -v n="$reapply" 'NR > n && /tui_run .*resume_koha_services/ { print NR; exit }' "$KEI_REPO/installer")
    [ -n "$reapply" ] && [ -n "$resume" ] && [ $((resume - reapply)) -lt 5 ]
}

# --- the "New arrivals" job -------------------------------------------

catalog() {
    rm -f "$W/c.db"
    perl -MDBI -e '
my $d = DBI->connect("dbi:SQLite:dbname=$ARGV[0]", "", "", { RaiseError => 1 });
$d->do($_) for
  "CREATE TABLE biblio (biblionumber INTEGER PRIMARY KEY, title TEXT, author TEXT, datecreated TEXT)",
  "CREATE TABLE biblioitems (biblionumber INTEGER, isbn TEXT)",
  "CREATE TABLE items (biblionumber INTEGER, itemcallnumber TEXT, onloan TEXT, notforloan INTEGER, itemlost INTEGER, withdrawn INTEGER)",
  # 1: ISBN-13 of 0306406152, on loan; 2: no cover (43 bytes); 3: only a lost copy;
  # 4: no ISBN; 5: ISBN-10 with dashes, available; 6: the same book again (one card).
  "INSERT INTO biblio VALUES (1, \"Signals /\", \"Ana Souza,\", \"2026-10-01\"), (2, \"C language\", \"K&R\", \"2026-10-02\"),
     (3, \"Lost\", \"X\", \"2026-10-03\"), (4, \"No ISBN\", \"Y\", \"2026-10-04\"), (5, \"Dom Casmurro :\", \"Machado\", \"2026-09-01\"),
     (6, \"Dom Casmurro\", \"Machado\", \"2026-08-01\")",
  "INSERT INTO biblioitems VALUES (1, \"9780306406157 (pbk.)\"), (2, \"0131103628\"), (3, \"0306406152\"), (4, \"\"), (5, \"85-359-0277-5\"), (6, \"8535902775\")",
  "INSERT INTO items VALUES (1, \"621.3 S578\", \"2026-10-05\", 0, 0, 0), (2, \"005.13 K\", NULL, 0, 0, 0),
     (3, \"X1\", NULL, 0, 1, 0), (4, \"Y1\", NULL, 0, 0, 0), (5, \"869.3 A\", NULL, 0, 0, 0), (5, \"869.3 A c.2\", NULL, 0, 0, 1), (6, \"869.3 B\", NULL, 0, 0, 0)";
' "$W/c.db"
}

@test "new arrivals: only titles with a copy and a real Amazon cover, newest first" {
    catalog
    task opac_na_script
    printf '%s\n' "$output" > "$W/na.pl"
    perl -c "$W/na.pl"
    run env KEI_NA_DSN="dbi:SQLite:dbname=$W/c.db" KEI_NA_OUT="$W/feed.json" \
        KEI_NA_COVER_BASE="http://127.0.0.1:$(cat "$BATS_FILE_TMPDIR/port")/" perl "$W/na.pl" 4
    echo "$output"
    [ "$status" -eq 0 ]
    [ "$output" = "2 of 3 titles with an ISBN have an Amazon cover" ]
    [ "$(stat -c %a "$W/feed.json")" = "644" ]
    python3 - "$W/feed.json" <<'PY'
import json, sys
items = json.load(open(sys.argv[1]))["items"]
assert [i["biblionumber"] for i in items] == [1, 5], items
a, b = items
assert a["title"] == "Signals" and a["author"] == "Ana Souza", a
assert a["callnumber"] == "621.3 S578" and a["available"] == 0 and a["total"] == 1, a
assert a["cover"].endswith("/0306406152.01.LZZZZZZZ.jpg"), a
assert b["title"] == "Dom Casmurro" and b["available"] == 1 and b["total"] == 1, b
PY
}

@test "new arrivals: turning the carousel on installs the job and its schedule" {
    apply_dir "$W/on" "a { }" "on 8"
    cat >> "$W/extra.sh" <<SH
opac_na_script() { printf '#!/bin/sh\necho "3 of 5 titles with an ISBN have an Amazon cover"\necho "\$1" > "$W/ran"\n'; }
SH
    task opac_theme_apply "$W/on"
    [ "$status" -eq 0 ]
    [ -x "$W/koha-kei-new-arrivals" ]
    grep -q "^40 5 \* \* \* root $W/koha-kei-new-arrivals 8 " "$W/cron"
    grep -q "RESULT feed=3 of 5" "$W/results"
    rm -f "$W/results"
    task opac_theme_get
    grep -q "RESULT carousel=on" "$W/results"
    rm -f "$KEI_S/dialogs.log"
    task opac_carousel_refresh
    [ "$status" -eq 0 ]
    grep -q "OK The New arrivals feed was rebuilt." "$KEI_S/dialogs.log"
    # Off again: the job and its schedule go.
    task opac_theme_apply "$W/apply"
    [ ! -e "$W/cron" ] && [ ! -e "$W/koha-kei-new-arrivals" ]
    task opac_carousel_refresh
    [ "$status" -eq 1 ]
    grep -q "ERROR .*carousel is not on" "$KEI_S/dialogs.log"
}

@test "opac-theme: the panel knows the tasks" {
    grep -q '^        opac-theme-get) ' "$KEI_REPO/installer"
    grep -q '^        opac-theme-apply) ' "$KEI_REPO/installer"
    grep -q '^        opac-theme-remove) ' "$KEI_REPO/installer"
    grep -q '^        opac-carousel-refresh) ' "$KEI_REPO/installer"
}
