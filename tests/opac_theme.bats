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
    mysql "$DB" -e "DROP TABLE IF EXISTS additional_contents_localizations; DROP TABLE IF EXISTS additional_contents;"
    mysql "$DB" -e "DROP TABLE IF EXISTS systempreferences;
CREATE TABLE systempreferences (variable varchar(50) NOT NULL PRIMARY KEY, value mediumtext, options longtext,
  explanation mediumtext, type varchar(20)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO systempreferences (variable, value) VALUES
  ('OpacUserCSS', '#mine { color: red; }'), ('OpacUserJS', 'console.log(\"mine\");'),
  ('OPACAmazonCoverImages', '0'), ('AmazonAssocTag', ''), ('OpacFavicon', ''), ('OpacNav', 'keep'),
  ('IntranetUserCSS', '#staff { color: navy; }'), ('IntranetFavicon', ''),
  ('IntranetUserJS', '/* koha-easy-installer cdd begin */\nvar cdd = 1;\n/* koha-easy-installer cdd end */');"
    mkdir -p "$W/custom" "$W/work"
    cat > "$W/extra.sh" <<SH
SYS_LANG=en
kei_result() { printf 'RESULT %s=%s\n' "\$1" "\$2" >> "$W/results"; }
require_database() { return 0; }
is_koha_installed() { return 0; }
tools_locked() { TOOLS_WORK="$W/work"; "\$@"; }
tools_safety_backup() { TOOLS_PRE="$W/PRE-\$1.sql.gz"; echo "\$1" >> "$W/backups"; }
memcached_flush() { return 0; }
opac_theme_restart() { echo restart >> "$W/restarts"; }
OPAC_RETIRED="$W/etc/theme-retired.tsv"
TOOLS_LOG_DIR="$W/logs"
OPAC_CUSTOM_DIR="$W/custom"
STAFF_CUSTOM_DIR="$W/staff-custom"
OPAC_NA_BIN="$W/koha-kei-new-arrivals"
CRON_OPAC="$W/cron"
CRON_TASKS="$W/koha_tasks"
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
    touch "$W/cron" "$W/koha-kei-new-arrivals" "$W/custom/kei-new-arrivals.json" "$W/custom/kei-list-7.json" "$W/custom/library.png"
    task opac_theme_remove
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS)" = "#mine { color: red; }" ]
    [ "$(pref OpacUserJS)" = 'console.log("mine");' ]
    [ "$(pref OpacFavicon)" = "" ]
    [ ! -e "$W/custom/kei-favicon.png" ] && [ ! -e "$W/custom/kei-background.jpg" ]
    [ ! -e "$W/cron" ] && [ ! -e "$W/koha-kei-new-arrivals" ] && [ ! -e "$W/custom/kei-new-arrivals.json" ]
    [ ! -e "$W/custom/kei-list-7.json" ]
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

@test "theme-settings.json: saved by apply, gone with remove" {
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
    task opac_theme_remove
    [ ! -e "$W/etc/theme-settings.json" ]
    [ "$(pref IntranetUserCSS)" = "#staff { color: navy; }" ]
}

# restored LOOK: the database as a backup brings it back. "other": another
# look of the panel (metal) in OpacUserCSS / IntranetUserJS; "none": only the
# library's own CSS and JS.
restored() {
    local begin="/* koha-easy-installer opac-theme begin */" end="/* koha-easy-installer opac-theme end */"
    if [ "$1" = "other" ]; then
        mysql "$DB" -e "UPDATE systempreferences SET value = $(printf "'%s\n%s\n%s\n%s'" '#old { }' "$begin" \
            '/* KEI-THEME-DATA: {\"texture\": \"metal\"} */' "$end") WHERE variable = 'OpacUserCSS';
UPDATE systempreferences SET value = $(printf "'%s\n%s\n%s'" "$begin" '    var C = {\"links\": {\"items\": []}};' "$end") WHERE variable = 'OpacUserJS';
UPDATE systempreferences SET value = '' WHERE variable IN ('IntranetUserCSS', 'AmazonAssocTag');"
    else
        mysql "$DB" -e "UPDATE systempreferences SET value = '#old { }' WHERE variable = 'OpacUserCSS';
UPDATE systempreferences SET value = '' WHERE variable IN ('OpacUserJS', 'IntranetUserCSS', 'AmazonAssocTag');"
    fi
}

@test "restore: the restored database decides the look, theme-settings.json is read again from it" {
    printf '%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" ".navbar { background: #123456; }" \
        "/* koha-easy-installer opac-theme end */" > "$W/apply/staff.css"
    task opac_theme_apply "$W/apply"
    restored other
    rm -f "$W/results"
    task theme_state_refresh
    [ "$status" -eq 0 ]
    # Nothing of the panel's saved copy went back into Koha.
    [ "$(pref OpacUserCSS | grep -c 'KEI-THEME-DATA')" = "1" ]
    pref OpacUserCSS | grep -qF '"texture": "metal"'
    ! pref OpacUserCSS | grep -qxF "a { color: blue; }"
    [ "$(pref IntranetUserCSS)" = "" ]
    [ "$(pref AmazonAssocTag)" = "" ]
    grep -qxF "RESULT theme_state=restored" "$W/results"
    python3 - "$W/etc/theme-settings.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert s["settings"] == {"texture": "metal"}, s
assert set(s["blocks"]) == {"OpacUserCSS", "OpacUserJS"}, s
assert "#old" not in s["blocks"]["OpacUserCSS"] and "KEI-THEME-DATA" in s["blocks"]["OpacUserCSS"], s
assert s["from"] == "restore" and s["prefs"] == [], s
PY
    # The panel's Sync reads the restored look, not the one of the last apply.
    rm -f "$W/results"
    task opac_theme_sync
    grep -qF 'RESULT data=/* KEI-THEME-DATA: {"texture": "metal"} */' "$W/results"
    grep -qxF 'RESULT state={"texture": "metal"}' "$W/results"
    grep -qxF 'RESULT block_IntranetUserCSS=no' "$W/results"
}

@test "restore: none of the panel's look in the restored database, its saved copy goes" {
    task opac_theme_apply "$W/apply"
    [ -s "$W/etc/theme-settings.json" ]
    restored none
    rm -f "$W/results"
    task theme_state_refresh
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS)" = "#old { }" ]
    [ "$(pref OpacUserJS)" = "" ]
    [ ! -e "$W/etc/theme-settings.json" ]
    grep -qxF "RESULT theme_state=none" "$W/results"
    # Nothing saved before: still nothing, Koha untouched.
    task theme_state_refresh
    [ "$status" -eq 0 ]
    [ "$(pref OpacUserCSS)" = "#old { }" ]
}

@test "restore database: the saved look is read again from Koha, never written back" {
    ! grep -q 'theme_state_reapply' "$KEI_REPO/installer"
    refresh=$(grep -n 'tui_run .*theme_state_refresh' "$KEI_REPO/installer" | head -n1 | cut -d: -f1)
    resume=$(awk -v n="$refresh" 'NR > n && /tui_run .*resume_koha_services/ { print NR; exit }' "$KEI_REPO/installer")
    [ -n "$refresh" ] && [ -n "$resume" ] && [ $((resume - refresh)) -lt 5 ]
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

# na COUNT: the job against the SQLite catalogue and the local cover server
# (Amazon at /, OpenLibrary at /ol/).
na() {
    local base="http://127.0.0.1:$(cat "$BATS_FILE_TMPDIR/port")/"
    run env KEI_NA_DSN="dbi:SQLite:dbname=$W/c.db" KEI_NA_OUT="$W/feed.json" \
        KEI_NA_COVER_BASE="$base" KEI_NA_OL_BASE="${base}ol/" perl "$W/na.pl" "$1"
}

@test "new arrivals: only titles with a copy, newest first; a missing cover is an empty one" {
    catalog
    task opac_na_script
    printf '%s\n' "$output" > "$W/na.pl"
    perl -c "$W/na.pl"
    na 4
    echo "$output"
    [ "$status" -eq 0 ]
    [ "$output" = "2 of 3 new titles have a cover; 0 public lists" ]
    [ "$(stat -c %a "$W/feed.json")" = "644" ]
    python3 - "$W/feed.json" <<'PY'
import json, sys
items = json.load(open(sys.argv[1]))["items"]
# 2 has no cover: cover "" (the carousel leaves it out or draws one).
assert [i["biblionumber"] for i in items] == [2, 1, 5], items
assert items[0]["cover"] == "" and items[0]["title"] == "C language", items[0]
a, b = items[1:]
assert a["title"] == "Signals" and a["author"] == "Ana Souza", a
assert a["callnumber"] == "621.3 S578" and a["available"] == 0 and a["total"] == 1, a
assert a["cover"].endswith("/0306406152.01.LZZZZZZZ.jpg"), a
assert b["title"] == "Dom Casmurro" and b["available"] == 1 and b["total"] == 1, b
PY
}

@test "lists: one feed per public list in its order, uploaded covers first, then OpenLibrary" {
    catalog
    perl -MDBI -e '
my $d = DBI->connect("dbi:SQLite:dbname=$ARGV[0]", "", "", { RaiseError => 1 });
$d->do($_) for
  "CREATE TABLE systempreferences (variable TEXT PRIMARY KEY, value TEXT)",
  "INSERT INTO systempreferences VALUES (\"OPACLocalCoverImages\", \"1\")",
  "CREATE TABLE cover_images (imagenumber INTEGER PRIMARY KEY, biblionumber INTEGER)",
  # 4 has no ISBN but an uploaded cover: it joins the new arrivals too.
  "INSERT INTO cover_images VALUES (1, 4)",
  "CREATE TABLE virtualshelves (shelfnumber INTEGER PRIMARY KEY, shelfname TEXT, public INTEGER, sortfield TEXT)",
  "INSERT INTO virtualshelves VALUES (7, \"Reading club\", 1, \"title\"), (8, \"Private\", 0, \"title\")",
  "CREATE TABLE virtualshelfcontents (shelfnumber INTEGER, biblionumber INTEGER, dateadded TEXT)",
  # 3: only a lost copy, kept in a list (no badge); 2: no cover anywhere.
  "INSERT INTO virtualshelfcontents VALUES (7, 5, \"2026-10-01\"), (7, 4, \"2026-10-02\"), (7, 2, \"2026-10-03\"),
     (7, 3, \"2026-10-04\"), (8, 1, \"2026-10-01\")";
' "$W/c.db"
    mkdir -p "$BATS_FILE_TMPDIR/covers/ol"
    head -c 4000 /dev/urandom > "$BATS_FILE_TMPDIR/covers/ol/0306406152-L.jpg"
    echo old > "$W/kei-list-99.json"
    task opac_na_script
    printf '%s\n' "$output" > "$W/na.pl"
    na 4
    echo "$output"
    rm -rf "$BATS_FILE_TMPDIR/covers/ol"
    [ "$status" -eq 0 ]
    [ "$output" = "3 of 4 new titles have a cover; 1 public lists" ]
    [ ! -e "$W/kei-list-8.json" ] && [ ! -e "$W/kei-list-99.json" ]
    [ "$(stat -c %a "$W/kei-list-7.json")" = "644" ]
    python3 - "$W/kei-list-7.json" "$W/feed.json" <<'PY'
import json, sys
items = json.load(open(sys.argv[1]))["items"]
# By title: C language (no cover: ""), Dom Casmurro, Lost, No ISBN.
assert [i["biblionumber"] for i in items] == [2, 5, 3, 4], items
assert items[0]["cover"] == "", items[0]
assert items[1]["cover"].endswith("/8535902775.01.LZZZZZZZ.jpg"), items[1]
assert items[2]["cover"].endswith("/ol/0306406152-L.jpg?default=false") and items[2]["total"] == 0, items[2]
assert items[3]["cover"] == "/cgi-bin/koha/opac-image.pl?thumbnail=1&biblionumber=4", items[3]
feed = json.load(open(sys.argv[2]))["items"]
assert [i["biblionumber"] for i in feed] == [4, 2, 1, 5], feed
assert feed[2]["cover"].endswith("/ol/0306406152-L.jpg?default=false"), feed
PY
}

@test "new arrivals: turning the carousel on installs the job and its schedule" {
    apply_dir "$W/on" "a { }" "on 8"
    cat >> "$W/extra.sh" <<SH
opac_na_script() { printf '#!/bin/sh\necho "3 of 5 new titles have a cover; 0 public lists"\necho "\$1" > "$W/ran"\n'; }
SH
    task opac_theme_apply "$W/on"
    [ "$status" -eq 0 ]
    [ -x "$W/koha-kei-new-arrivals" ]
    # The schedule is a line of koha_tasks (Schedules & cron tasks), with
    # no file of its own; the number of covers is in the job.
    grep -qx "40 5 \* \* \* root $W/koha-kei-new-arrivals >/dev/null 2>&1" "$W/koha_tasks"
    [ ! -e "$W/cron" ]
    [ "$(cat "$W/ran")" = "8" ]
    grep -q "RESULT feed=3 of 5" "$W/results"
    rm -f "$W/results"
    task opac_theme_get
    grep -q "RESULT carousel=on" "$W/results"
    rm -f "$KEI_S/dialogs.log"
    task opac_carousel_refresh
    [ "$status" -eq 0 ]
    grep -q "OK The New arrivals feed was rebuilt." "$KEI_S/dialogs.log"
    # A time the library chose in Schedules & cron tasks stays on the next apply.
    sed -i "s|^40 5 \* \* \* root $W/koha-kei-new-arrivals|0 */6 * * * root $W/koha-kei-new-arrivals|" "$W/koha_tasks"
    task opac_theme_apply "$W/on"
    [ "$(grep -c koha-kei-new-arrivals "$W/koha_tasks")" = "1" ]
    grep -q "^0 \*/6 \* \* \* root $W/koha-kei-new-arrivals" "$W/koha_tasks"
    # Off again: the job and its line go, the other lines stay.
    printf '0 5 * * * root /usr/sbin/koha-plack --restart library\n' >> "$W/koha_tasks"
    task opac_theme_apply "$W/apply"
    [ ! -e "$W/koha-kei-new-arrivals" ]
    ! grep -q "koha-kei-new-arrivals\|OPAC carousel" "$W/koha_tasks"
    grep -qx "0 5 \* \* \* root /usr/sbin/koha-plack --restart library" "$W/koha_tasks"
    task opac_carousel_refresh
    [ "$status" -eq 1 ]
    grep -q "ERROR .*carousel is not on" "$KEI_S/dialogs.log"
}

@test "new arrivals: an older panel's schedule file moves into koha_tasks" {
    printf 'PATH=/bin\n\n0 5 * * * root /usr/sbin/koha-plack --restart library\n' > "$W/koha_tasks"
    printf '# koha.nexus: OPAC "New arrivals" carousel\n40 5 * * * root %s 8 >/dev/null 2>&1\n' "$W/koha-kei-new-arrivals" > "$W/cron"
    printf 'systemctl() { :; }\n' >> "$W/extra.sh"
    task upgrade_cron_tasks
    [ "$status" -eq 0 ]
    [ ! -e "$W/cron" ]
    grep -qx "40 5 \* \* \* root $W/koha-kei-new-arrivals 8 >/dev/null 2>&1" "$W/koha_tasks"
    grep -qx "0 5 \* \* \* root /usr/sbin/koha-plack --restart library" "$W/koha_tasks"
    # Run again: nothing doubled.
    task upgrade_cron_tasks
    [ "$(grep -c koha-kei-new-arrivals "$W/koha_tasks")" = "1" ]
}

@test "opac-theme: the panel knows the tasks" {
    grep -q '^        opac-theme-get) ' "$KEI_REPO/installer"
    grep -q '^        opac-theme-apply) ' "$KEI_REPO/installer"
    grep -q '^        opac-theme-remove) ' "$KEI_REPO/installer"
    grep -q '^        opac-carousel-refresh) ' "$KEI_REPO/installer"
    grep -q '^        opac-theme-sync) ' "$KEI_REPO/installer"
}

@test "opac-theme-apply: staff.js goes in IntranetUserJS next to the other tools' blocks, and out again" {
    printf '%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" "(function () { var staff = 1; })();" \
        "/* koha-easy-installer opac-theme end */" > "$W/apply/staff.js"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    pref IntranetUserJS | grep -qxF "var cdd = 1;"
    pref IntranetUserJS | grep -qF "var staff = 1;"
    python3 - "$W/etc/theme-settings.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert "var staff = 1;" in s["blocks"]["IntranetUserJS"], s
PY
    # A restore brings the backup's IntranetUserJS: it stays as restored.
    mysql "$DB" -e "UPDATE systempreferences SET value = 'var old = 1;' WHERE variable = 'IntranetUserJS';"
    task theme_state_refresh
    [ "$(pref IntranetUserJS)" = "var old = 1;" ]
    python3 - "$W/etc/theme-settings.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert "IntranetUserJS" not in s["blocks"], s
PY
    # Without staff.js our block goes, the other one stays.
    mysql "$DB" -e "UPDATE systempreferences SET value = CONCAT('var cdd = 1;', CHAR(10), value) WHERE variable = 'IntranetUserJS';"
    rm "$W/apply/staff.js"
    task opac_theme_apply "$W/apply"
    [ -z "$(pref IntranetUserJS | grep -F "var staff = 1;")" ]
    pref IntranetUserJS | grep -qxF "var cdd = 1;"
    # A damaged staff.js changes nothing.
    printf 'var staff = 2;\n' > "$W/apply/staff.js"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 1 ]
    [ -z "$(pref IntranetUserJS | grep -F "var staff = 2;")" ]
    rm "$W/apply/staff.js"
    printf '%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" "var staff = 3;" \
        "/* koha-easy-installer opac-theme end */" > "$W/apply/staff.js"
    task opac_theme_apply "$W/apply"
    task opac_theme_remove
    [ -z "$(pref IntranetUserJS | grep -F "var staff = 3;")" ]
    pref IntranetUserJS | grep -qxF "var cdd = 1;"
}

@test "opac-theme-sync: what is live in Koha, for the panel's Sync button" {
    mysql "$DB" -e "DROP TABLE IF EXISTS additional_contents_localizations; DROP TABLE IF EXISTS additional_contents;
CREATE TABLE additional_contents (id int PRIMARY KEY, location varchar(255));
CREATE TABLE additional_contents_localizations (id int PRIMARY KEY, additional_content_id int, content mediumtext);
INSERT INTO additional_contents VALUES (1, 'OpacMainUserBlock'), (2, 'opac_news');
INSERT INTO additional_contents_localizations VALUES
  (1, 1, '<p>Hi</p>[kei-button url=\\\"/a\\\"]A[/kei-button] [kei-button url=\\\"/b\\\"]B[/kei-button]'),
  (2, 2, '[kei-button url=\\\"/c\\\"]C[/kei-button]');"
    printf '%s\n%s\n%s\n' "/* koha-easy-installer opac-theme begin */" '    var C = {"links": {"items": []}};' \
        "/* koha-easy-installer opac-theme end */" > "$W/apply/user.js"
    task opac_theme_apply "$W/apply"
    rm -f "$W/results"
    task opac_theme_sync
    [ "$status" -eq 0 ]
    grep -qF 'RESULT data=/* KEI-THEME-DATA: {"texture": "frosted", "version": 1} */' "$W/results"
    grep -qxF 'RESULT block_OpacUserCSS=yes' "$W/results"
    grep -qxF 'RESULT block_IntranetUserJS=no' "$W/results"
    grep -qxF 'RESULT own_OpacUserCSS=1' "$W/results"
    grep -qxF 'RESULT own_IntranetUserJS=3' "$W/results"
    grep -qxF 'RESULT config_OpacUserJS={"links": {"items": []}}' "$W/results"
    grep -qxF 'RESULT state={"texture": "frosted", "version": 1}' "$W/results"
    grep -qxF 'RESULT mainblock=yes' "$W/results"
    grep -qxF 'RESULT mainblock_buttons=2' "$W/results"
    # The settings line moved out of our block by hand: still found.
    mysql "$DB" -e "UPDATE systempreferences SET value = '/* KEI-THEME-DATA: {\\\"texture\\\": \\\"metal\\\"} */' WHERE variable = 'OpacUserCSS';
DROP TABLE additional_contents_localizations; DROP TABLE additional_contents;"
    rm -f "$W/results" "$W/etc/theme-settings.json"
    task opac_theme_sync
    [ "$status" -eq 0 ]
    grep -qF 'RESULT data=/* KEI-THEME-DATA: {"texture": "metal"} */' "$W/results"
    grep -qxF 'RESULT block_OpacUserCSS=no' "$W/results"
    [ -z "$(grep 'RESULT state=' "$W/results")" ]
    grep -qxF 'RESULT mainblock=no' "$W/results"
}

@test "opac-theme-sync: the stylesheet in Koha is handed over, CRLF lines from Koha's editor included" {
    task opac_theme_apply "$W/apply"
    # Saved again from Koha's own editor: the browser sends CRLF lines.
    mysql "$DB" -e "UPDATE systempreferences SET value = REPLACE(REPLACE(value, '\\r', ''), '\\n', '\\r\\n')
        WHERE variable = 'OpacUserCSS';"
    pref OpacUserCSS | grep -q $'\r'
    rm -f "$W/results"
    task opac_theme_sync
    [ "$status" -eq 0 ]
    grep -qxF 'RESULT block_OpacUserCSS=yes' "$W/results"
    grep -qF 'RESULT data=/* KEI-THEME-DATA: {"texture": "frosted", "version": 1} */' "$W/results"
    line=$(grep '^RESULT css_OpacUserCSS=' "$W/results")
    printf '%s' "${line#RESULT css_OpacUserCSS=}" | base64 -d | grep -qF 'KEI-THEME-DATA'
    ! printf '%s' "${line#RESULT css_OpacUserCSS=}" | base64 -d | grep -q $'\r'
}

# --- login instructions and footer credits (HTML customizations) --------

# Koha 23.11+ tables, and the library's own entries: credits (id 1, shown),
# login instructions (id 2, shown until a date) and an old expired one (id 3).
contents_tables() {
    mysql "$DB" -e "CREATE TABLE additional_contents (id int unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY,
  category varchar(20) NOT NULL, code varchar(100) NOT NULL, location varchar(255) NOT NULL,
  branchcode varchar(10) DEFAULT NULL, published_on date DEFAULT NULL,
  updated_on timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  expirationdate date DEFAULT NULL, number int DEFAULT NULL, borrowernumber int DEFAULT NULL,
  UNIQUE KEY additional_contents_uniq (category, code, branchcode)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE additional_contents_localizations (id int unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY,
  additional_content_id int unsigned NOT NULL, title varchar(250) NOT NULL DEFAULT '', content mediumtext NOT NULL,
  lang varchar(50) NOT NULL DEFAULT '', UNIQUE KEY (additional_content_id, lang),
  CONSTRAINT fk_ac FOREIGN KEY (additional_content_id) REFERENCES additional_contents (id) ON DELETE CASCADE)
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO additional_contents (id, category, code, location, published_on, expirationdate) VALUES
  (1, 'html_customizations', 'opaccredits_1', 'opaccredits', '2025-01-01', NULL),
  (2, 'html_customizations', 'OpacLoginInstructions_2', 'OpacLoginInstructions', '2025-01-01', '2099-12-31'),
  (3, 'html_customizations', 'opaccredits_3', 'opaccredits', '2020-01-01', '2021-01-01');
INSERT INTO additional_contents_localizations (additional_content_id, content, lang) VALUES
  (1, '<p>Old credits</p>', 'default'), (2, '<p>Old login</p>', 'default'), (3, '<p>Older</p>', 'default');"
}

# contents DIR LOC=on|off...: the panel's contents.list and files.
contents() {
    local dir="$1" a loc
    shift
    mkdir -p "$dir/contents"
    : > "$dir/contents.list"
    for a in "$@"; do
        loc="${a%%=*}"
        printf '%s\t%s\n' "$loc" "${a#*=}" >> "$dir/contents.list"
        [ "${a#*=}" = "on" ] && printf '<div class="kei-credits">\n<p>%s – ours</p>\n</div>\n' "$loc" > "$dir/contents/$loc.html"
    done
    printf '{"credits": {"enabled": true, "name": "Biblioteca"}}' > "$dir/contents.json"
}

ac() { mysql --default-character-set=utf8mb4 -N --raw "$DB" -e "$1"; }

@test "contents: ours goes in, the library's own entry expires and comes back with off and remove" {
    contents_tables
    contents "$W/apply" opaccredits=on OpacLoginInstructions=on StaffLoginInstructions=off
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ "$(ac "SELECT l.content FROM additional_contents c JOIN additional_contents_localizations l ON l.additional_content_id = c.id
             WHERE c.code = 'kei-opaccredits' AND c.location = 'opaccredits' AND c.branchcode IS NULL AND l.lang = 'default'
             AND c.published_on <= CURDATE() AND c.expirationdate IS NULL")" = $'<div class="kei-credits">\n<p>opaccredits – ours</p>\n</div>' ]
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code LIKE 'kei-%'")" = "2" ]
    # Koha would show both: the library's own shown entries are expired, the old one untouched.
    [ "$(ac "SELECT id FROM additional_contents WHERE code NOT LIKE 'kei-%' AND expirationdate < CURDATE() ORDER BY id" | tr '\n' ' ')" = "1 2 3 " ]
    [ "$(ac "SELECT expirationdate FROM additional_contents WHERE id = 3")" = "2021-01-01" ]
    [ "$(cat "$W/etc/theme-retired.tsv")" = $'opaccredits\t1\t\nOpacLoginInstructions\t2\t2099-12-31' ]
    grep -qx restart "$W/restarts"
    # A second apply: still one entry of ours per place, nothing listed twice.
    task opac_theme_apply "$W/apply"
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code = 'kei-opaccredits'")" = "1" ]
    [ "$(ac "SELECT COUNT(*) FROM additional_contents_localizations")" = "5" ]
    [ "$(wc -l < "$W/etc/theme-retired.tsv")" = "2" ]
    # The credits turned off: ours goes, the library's credits come back.
    contents "$W/apply" opaccredits=off OpacLoginInstructions=on StaffLoginInstructions=off
    task opac_theme_apply "$W/apply"
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code = 'kei-opaccredits'")" = "0" ]
    [ "$(ac "SELECT IFNULL(expirationdate, 'none') FROM additional_contents WHERE id = 1")" = "none" ]
    [ "$(cat "$W/etc/theme-retired.tsv")" = $'OpacLoginInstructions\t2\t2099-12-31' ]
    # Remove: none of ours left, the login instructions get their own date back.
    task opac_theme_remove
    [ "$status" -eq 0 ]
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code LIKE 'kei-%'")" = "0" ]
    [ "$(ac "SELECT expirationdate FROM additional_contents WHERE id = 2")" = "2099-12-31" ]
    [ ! -e "$W/etc/theme-retired.tsv" ]
}

@test "news: the panel's news item of each side goes in with its title, the library's news stay" {
    contents_tables
    ac "INSERT INTO additional_contents (id, category, code, location, published_on) VALUES (10, 'news', 'News_10', 'staff_and_opac', '2025-01-01');
INSERT INTO additional_contents_localizations (additional_content_id, title, content, lang) VALUES (10, 'Ours too', '<p>Library news</p>', 'default');"
    contents "$W/apply" news-opac=on news-staff=off
    printf '<!-- kei-news-title: Férias de julho -->\n<div class="kei-news">\n<p>Fechado</p>\n</div>\n' > "$W/apply/contents/news-opac.html"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ "$(ac "SELECT CONCAT(c.category, '|', c.location, '|', l.title) FROM additional_contents c
             JOIN additional_contents_localizations l ON l.additional_content_id = c.id WHERE c.code = 'kei-news-opac'")" = "news|opac_only|Férias de julho" ]
    [ "$(ac "SELECT l.content FROM additional_contents c JOIN additional_contents_localizations l ON l.additional_content_id = c.id
             WHERE c.code = 'kei-news-opac'")" = $'<div class="kei-news">\n<p>Fechado</p>\n</div>' ]
    [ "$(ac "SELECT IFNULL(expirationdate, 'none') FROM additional_contents WHERE id = 10")" = "none" ]
    # Applied twice, then moved to the staff side: one of ours, on the right side.
    task opac_theme_apply "$W/apply"
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code = 'kei-news-opac'")" = "1" ]
    contents "$W/apply" news-opac=off news-staff=on
    printf '<!-- kei-news-title: Equipe -->\n<p>Reunião</p>\n' > "$W/apply/contents/news-staff.html"
    task opac_theme_apply "$W/apply"
    [ "$(ac "SELECT GROUP_CONCAT(CONCAT(code, ':', location)) FROM additional_contents WHERE code LIKE 'kei-news-%'")" = "kei-news-staff:staff_only" ]
    task opac_theme_remove
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code LIKE 'kei-%'")" = "0" ]
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE id = 10")" = "1" ]
}

@test "staff news: the koha.nexus item goes in once, as the library's own news, and never comes back" {
    contents_tables
    printf 'STAFF_WELCOME_MARK="%s"\n' "$W/etc/staff-welcome-news.done" >> "$W/extra.sh"
    task staff_welcome_news
    [ "$status" -eq 0 ]
    [ "$(ac "SELECT CONCAT(c.category, '|', c.location, '|', IFNULL(c.branchcode, 'all'), '|', l.lang, '|', l.title)
             FROM additional_contents c JOIN additional_contents_localizations l ON l.additional_content_id = c.id
             WHERE c.code = 'koha-nexus-welcome'")" = "news|staff_only|all|default|Welcome to koha.nexus" ]
    ac "SELECT l.content FROM additional_contents c JOIN additional_contents_localizations l ON l.additional_content_id = c.id
        WHERE c.code = 'koha-nexus-welcome'" > "$W/welcome.html"
    grep -qF '<a href="https://koha.nexus" target="_blank" rel="noopener">koha.nexus</a>' "$W/welcome.html"
    grep -qF '<a href="https://github.com/PauloFBaldiFH/koha.nexus" target="_blank" rel="noopener">' "$W/welcome.html"
    grep -qF 'without budget or technical support' "$W/welcome.html"
    grep -qF '<li>Pix: <code>076.650.449.21</code></li>' "$W/welcome.html"
    grep -qF '<li>Bitcoin (BTC): <code>bc1qw0kvacdkzul0panuppxcv90y08ah443m2z89tx</code></li>' "$W/welcome.html"
    [ -f "$W/etc/staff-welcome-news.done" ]
    # Not one of the panel's own (kei-*): the panel's staff news box shows it
    # as the library's news item and Apply edits it in place.
    task opac_contents_ours
    printf '%s' "$output" | grep -v '^ERROR\|^OK' | head -n1 | base64 -d | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["news-staff"]["own"] and d["news-staff"]["title"] == "Welcome to koha.nexus", d'
    # Deleted by the library: the next start leaves it out.
    ac "DELETE FROM additional_contents WHERE code = 'koha-nexus-welcome'"
    task staff_welcome_news
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code = 'koha-nexus-welcome'")" = "0" ]
    # A database that already has it (restored elsewhere) gets no second one.
    rm -f "$W/etc/staff-welcome-news.done"
    ac "INSERT INTO additional_contents (category, code, location, published_on) VALUES ('news', 'koha-nexus-welcome', 'staff_only', CURDATE())"
    task staff_welcome_news
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code = 'koha-nexus-welcome'")" = "1" ]
    [ -f "$W/etc/staff-welcome-news.done" ]
}

@test "staff news: the koha.nexus item is put in only by a new install, never when the panel opens" {
    # Called by the install of a new instance...
    sed -n '/^install_koha_flow\|^    tui_step 7 /,/install_task_cleanup/p' "$BATS_TEST_DIRNAME/../installer" | grep -q '^    staff_welcome_news$'
    # ...and by nothing that runs on every start of the panel.
    [ "$(grep -c '^[^#]*staff_welcome_news$' "$BATS_TEST_DIRNAME/../installer")" = "1" ]
    ! grep -q 'is_koha_installed && staff_welcome_news' "$BATS_TEST_DIRNAME/../installer"
}

@test "contents: scripts, handlers, unknown places or a missing file change nothing" {
    contents_tables
    contents "$W/apply" opaccredits=on
    printf '<p onclick="alert(1)">x</p>\n' > "$W/apply/contents/opaccredits.html"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 1 ]
    grep -q "ERROR .*missing or damaged" "$KEI_S/dialogs.log"
    printf '<p>x</p><SCRIPT>alert(1)</SCRIPT>\n' > "$W/apply/contents/opaccredits.html"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 1 ]
    printf '<a href="javascript:alert(1)">x</a>\n' > "$W/apply/contents/opaccredits.html"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 1 ]
    contents "$W/apply" OpacNav=on
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 1 ]
    contents "$W/apply" opaccredits=on
    rm -f "$W/apply/contents/opaccredits.html"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 1 ]
    [ ! -e "$W/backups" ]
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code LIKE 'kei-%'")" = "0" ]
}

@test "contents: the login banners go to each side's folder" {
    printf '\x89PNG\r\n\x1a\nfake' > "$W/apply/assets/kei-login.png"
    printf '\x89PNG\r\n\x1a\nfake' > "$W/apply/assets/kei-staff-login.png"
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    [ -f "$W/custom/kei-login.png" ] && [ -f "$W/staff-custom/kei-staff-login.png" ]
    task opac_theme_remove
    [ ! -e "$W/custom/kei-login.png" ] && [ ! -e "$W/staff-custom/kei-staff-login.png" ]
}

@test "contents: a Koha without the localizations table skips them, the look still goes in" {
    contents "$W/apply" opaccredits=on
    task opac_theme_apply "$W/apply"
    [ "$status" -eq 0 ]
    grep -q "RESULT contents=unsupported" "$W/results"
    pref OpacUserCSS | grep -qxF "a { color: blue; }"
}

@test "contents: what Koha holds decides, after a restore too; opac-theme-get hands it to the panel" {
    contents_tables
    contents "$W/apply" opaccredits=on OpacLoginInstructions=off StaffLoginInstructions=off news-opac=on
    printf '<!-- kei-news-title: Férias -->\n<div class="kei-news">\n<p>Fechado</p>\n<p class="kei-news-cta"><a class="btn btn-primary kei-news-button" href="/a">Ver</a></p>\n</div>\n' \
        > "$W/apply/contents/news-opac.html"
    task opac_theme_apply "$W/apply"
    python3 - "$W/etc/theme-settings.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert "ours" in s["contents"]["opaccredits"] and s["contents"]["OpacLoginInstructions"] == "", s
assert s["contents_settings"]["credits"]["name"] == "Biblioteca", s
PY
    rm -f "$W/results"
    task opac_theme_get
    python3 - "$W/results" <<'PY'
import base64, json, sys
line = [l for l in open(sys.argv[1], encoding="utf-8") if l.startswith("RESULT live_contents=")][0]
live = json.loads(base64.b64decode(line.split("=", 1)[1]).decode("utf-8"))
assert set(live) == {"opaccredits", "news-opac"}, live
assert live["news-opac"]["title"] == "Férias" and "\n" in live["news-opac"]["content"], live
assert 'href="/a">Ver</a>' in live["news-opac"]["content"], live
PY
    # The restored database: the library's own credits back, none of ours,
    # and its own version of our news item (another button).
    ac "DELETE FROM additional_contents WHERE code = 'kei-opaccredits'; UPDATE additional_contents SET expirationdate = NULL WHERE id = 1;
UPDATE additional_contents_localizations l JOIN additional_contents c ON c.id = l.additional_content_id
  SET l.title = 'Julho', l.content = '<div class=\"kei-news\">\n<p>Aberto</p>\n<p class=\"kei-news-cta\"><a class=\"btn btn-primary kei-news-button\" href=\"/b\">Agenda</a></p>\n</div>'
  WHERE c.code = 'kei-news-opac';"
    rm -f "$W/results"
    task theme_state_refresh
    [ "$status" -eq 0 ]
    # Koha untouched: no credits of ours written back, the library's shown.
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code = 'kei-opaccredits'")" = "0" ]
    [ "$(ac "SELECT IFNULL(expirationdate, 'none') FROM additional_contents WHERE id = 1")" = "none" ]
    [ "$(ac "SELECT l.title FROM additional_contents c JOIN additional_contents_localizations l ON l.additional_content_id = c.id WHERE c.code = 'kei-news-opac'")" = "Julho" ]
    # The expired list keeps only what is still expired in the restored database.
    [ ! -e "$W/etc/theme-retired.tsv" ]
    python3 - "$W/etc/theme-settings.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert "opaccredits" not in s["contents"], s
assert "Agenda" in s["contents"]["news-opac"], s
PY
    rm -f "$W/results"
    task opac_theme_get
    live=$(grep -F 'RESULT live_contents=' "$W/results" | cut -d= -f2- | base64 -d)
    grep -qF 'Agenda' <<< "$live"
    ! grep -qF 'opaccredits' <<< "$live"
    # The panel's Sync: the restored news with its button, no credits of ours.
    PYTHONPATH="$KEI_REPO/panel" python3 - "$W/results" <<'PY'
import sys
from kei_panel import opac_theme as ot
found = dict(l.rstrip("\n")[len("RESULT "):].split("=", 1) for l in open(sys.argv[1], encoding="utf-8")
             if l.startswith("RESULT ") and "=" in l)
cfg, notes, in_koha = ot.sync_settings(found)
news = cfg["news"]["opac"]
assert in_koha and news["title"] == "Julho" and news["html"] == "<p>Aberto</p>", news
assert news["buttons"] == [{"text": "Agenda", "url": "/b"}], news
assert not ot.credits_on(cfg["credits"]), cfg["credits"]
PY
}


@test "news: the library's own news item comes into the panel with its buttons and is updated in place" {
    contents_tables
    # Koha's news item 9 as Paulo has it: an inline style and .btn-acesso links, no text.
    ac "INSERT INTO additional_contents (id, category, code, location, published_on) VALUES (9, 'news', 'News_9', 'opac_only', '2025-01-01');
INSERT INTO additional_contents_localizations (additional_content_id, title, content, lang) VALUES (9, 'Bem-vindo(a) à biblioteca',
'<style>\n.btn-acesso { display: block; }\n</style>\n<a href=\"/cgi-bin/koha/opac-page.pl?page_id=5\" class=\"btn-acesso\">📖 Sobre</a> <a href=\"https://wa.me/550000000000\" rel=\"noopener\" class=\"btn-acesso\" target=\"_blank\">💬 WhatsApp</a> <a href=\"mailto:contato@biblioteca.gov.br\" class=\"btn-acesso\">📧 E-mail</a>', 'default');"
    rm -f "$W/results"
    task opac_theme_get
    [ "$status" -eq 0 ]
    PYTHONPATH="$KEI_REPO/panel" python3 - "$W/results" "$W/apply2" <<'PY'
import shutil, sys
from pathlib import Path
from kei_panel import opac_theme as ot
found = dict(l.rstrip("\n")[len("RESULT "):].split("=", 1) for l in open(sys.argv[1], encoding="utf-8")
             if l.startswith("RESULT ") and "=" in l)
cfg, notes, in_koha = ot.sync_settings(found)
news = cfg["news"]["opac"]
assert in_koha and news["enabled"] and news["koha_id"] == 9, news
assert news["title"] == "Bem-vindo(a) à biblioteca" and news["html"] == "", news
assert [b["text"] for b in news["buttons"]] == ["📖 Sobre", "💬 WhatsApp", "📧 E-mail"], news
assert not cfg["news"]["staff"]["enabled"]
# Seven buttons now (no limit), then Apply.
news["buttons"] += [{"text": f"Extra {i}", "url": f"/x{i}"} for i in range(4)]
work = ot.write_apply_dir(cfg, {})
shutil.copytree(work, sys.argv[2])
shutil.rmtree(work)
PY
    task opac_theme_apply "$W/apply2"
    [ "$status" -eq 0 ]
    # Item 9 itself changed; no news item of the panel next to it.
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE code LIKE 'kei-news-%'")" = "0" ]
    [ "$(ac "SELECT COUNT(*) FROM additional_contents WHERE category = 'news'")" = "1" ]
    [ "$(ac "SELECT title FROM additional_contents_localizations WHERE additional_content_id = 9")" = "Bem-vindo(a) à biblioteca" ]
    [ "$(ac "SELECT content FROM additional_contents_localizations WHERE additional_content_id = 9" | grep -c 'kei-news-button')" = "7" ]
    ! ac "SELECT content FROM additional_contents_localizations WHERE additional_content_id = 9" | grep -q 'kei-news-id'
}

@test "apply then sync: the panel reads back every field it wrote (colours, material, pictures, staff)" {
    dir=$(cd "$KEI_REPO/panel" && python3 -c '
from kei_panel import opac_theme as ot
cfg = ot.normalize({"texture": "metal", "opacity": 63, "blur": 9, "accent": "#260859", "accent2": "#f4f4f6",
  "surface": "#e8e8e8", "page": "#f3f4f6", "radius_block": 22,
  "logo": {"source": "url", "url": "https://i.postimg.cc/a/logo.png"},
  "background": {"source": "url", "url": "https://i.postimg.cc/a/wall.jpg"},
  "favicon": {"source": "url", "url": "https://i.postimg.cc/a/fav.png"},
  "links": {"enabled": True, "items": [{"text": "Acervo", "url": "https://x.org/a"}]},
  "staff": {"enabled": True, "accent": "#112233", "texture": "wood", "opacity": 70}})
print(ot.write_apply_dir(cfg, {}))')
    task opac_theme_apply "$dir"
    [ "$status" -eq 0 ]
    rm -f "$W/results" "$W/etc/theme-settings.json"
    task opac_theme_sync
    [ "$status" -eq 0 ]
    grep -q '^RESULT database=koha_' "$W/results"
    grep -q '^RESULT installer_version=[0-9]' "$W/results"
    grep -q '^RESULT chars_OpacUserCSS=[1-9]' "$W/results"
    cd "$KEI_REPO/panel" && python3 -c '
import sys
from kei_panel import opac_theme as ot
found = {}
for line in open(sys.argv[1], encoding="utf-8"):
    if line.startswith("RESULT "):
        k, _, v = line[7:].rstrip("\n").partition("=")
        found[k] = v
cfg, notes, in_koha = ot.sync_settings(found)
assert in_koha
assert (cfg["texture"], cfg["opacity"], cfg["blur"], cfg["radius_block"]) == ("metal", 63, 9, 22), cfg
assert (cfg["accent"], cfg["accent2"], cfg["surface"], cfg["page"]) == ("#260859", "#f4f4f6", "#e8e8e8", "#f3f4f6")
assert cfg["logo"]["url"] == "https://i.postimg.cc/a/logo.png" and cfg["background"]["url"] == "https://i.postimg.cc/a/wall.jpg"
assert cfg["favicon"]["url"] == "https://i.postimg.cc/a/fav.png" and cfg["links"]["items"][0]["text"] == "Acervo"
assert (cfg["staff"]["enabled"], cfg["staff"]["accent"], cfg["staff"]["texture"], cfg["staff"]["opacity"]) == (True, "#112233", "wood", 70)
' "$W/results"
}
