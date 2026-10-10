#!/usr/bin/env bats
# Koha languages (section 6): download a pack only, download and activate,
# activate an installed pack, list the installed ones. koha-translate is a
# stand-in that keeps its packs in a file; the preferences live in a real
# MariaDB (no Koha needed).

setup_file() {
    load lib/common
    kei_start_mariadb
    mysql -e "CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4;"
}

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    mkdir -p "$KEI_S"
    rm -f "$KEI_S/dialogs.log" "$KEI_S/inputs" "$KEI_S/textboxes.log"
    mysql "$DB" -e "DROP TABLE IF EXISTS systempreferences;
CREATE TABLE systempreferences (variable varchar(50) NOT NULL PRIMARY KEY, value mediumtext, options longtext,
  explanation mediumtext, type varchar(20)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO systempreferences (variable, value) VALUES
  ('OPACLanguages', 'en,pt-BR'), ('StaffInterfaceLanguages', 'en');"
    mkdir -p "$W/bin"
    printf 'pt-BR\n' > "$W/packs"
    cat > "$W/bin/koha-translate" <<SH
#!/bin/bash
echo "koha-translate \$*" >> "$W/calls"
case "\$1" in
    --list) cat "$W/packs" ;;
    --install) [ -e "$W/fail" ] && { echo "no such pack" >&2; exit 1; }; echo "\$2" >> "$W/packs" ;;
esac
exit 0
SH
    chmod +x "$W/bin/koha-translate"
    cat > "$W/extra.sh" <<SH
PATH="$W/bin:\$PATH"
SYS_LANG=en
KOHA_PANEL_LANG_FULL=en-GB
kei_result() { printf 'RESULT %s=%s\n' "\$1" "\$2" >> "$W/results"; }
set_panel_language() { printf 'PANEL %s\n' "\$1" >> "$W/results"; KOHA_PANEL_LANG_FULL="\$1"; }
is_koha_installed() { [ ! -e "$W/no-koha" ]; }
tui_run() { shift; "\$@" >> "$W/tui.log" 2>&1; }
tui_title() { :; }
lang_prepare_locale() { :; }
memcached_flush() { return 0; }
plack_restart() { return 0; }
systemctl() { return 0; }
LOG_DIR="$W/logs"
RUN_LOG="$W/run.log"
SH
}

pref() { mysql -N --raw "$DB" -e "SELECT value FROM systempreferences WHERE variable = '$1'"; }
lang() { run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" "$@"; echo "$output"; dialogs || true; }

@test "L1 download only: the pack is installed, preferences and panel unchanged" {
    inputs es-ES
    lang function_lang_download
    [ "$status" -eq 0 ]
    grep -Fxq "es-ES" "$W/packs"
    grep -q "koha-translate --install es-ES" "$W/calls"
    [ "$(pref OPACLanguages)" = "en,pt-BR" ]
    [ "$(pref StaffInterfaceLanguages)" = "en" ]
    [ ! -e "$W/results" ]
    dialogs | grep -q "Language pack 'es-ES' downloaded"
}

@test "L2 download only: a pack already there is not downloaded again" {
    inputs pt-BR
    lang function_lang_download
    ! grep -q -- "--install\|--update" "$W/calls"
    dialogs | grep -q "already installed. Nothing was downloaded"
}

@test "L3 download only: a failed download says so and changes nothing" {
    touch "$W/fail"
    inputs fr-FR
    lang function_lang_download
    dialogs | grep -q "Failed to process language 'fr-FR'"
    [ "$(pref OPACLanguages)" = "en,pt-BR" ]
}

@test "L4 activate: the installed language goes first, nothing is downloaded" {
    inputs pt-BR
    lang function_lang_activate
    [ "$(pref OPACLanguages)" = "pt-BR,en" ]
    [ "$(pref StaffInterfaceLanguages)" = "pt-BR,en" ]
    ! grep -q -- "--install\|--update" "$W/calls"
    grep -q "RESULT panel_lang=pt-BR" "$W/results"
    grep -q "PANEL pt-BR" "$W/results"
}

@test "L5 activate on an older Koha: the 'language' preference is the staff one" {
    mysql "$DB" -e "DELETE FROM systempreferences WHERE variable = 'StaffInterfaceLanguages';
                    INSERT INTO systempreferences (variable, value) VALUES ('language', 'en');"
    inputs pt-BR
    lang function_lang_activate
    [ "$(pref language)" = "pt-BR,en" ]
    [ -z "$(pref StaffInterfaceLanguages)" ]
}

@test "L6 activate before the Web Installer: a message, no change" {
    mysql "$DB" -e "DROP TABLE systempreferences;"
    inputs pt-BR
    lang function_lang_activate
    dialogs | grep -q "Finish the Web Installer first"
    [ ! -e "$W/results" ]
}

@test "L7 download and activate: pack, preferences and panel together" {
    inputs es-ES
    lang function_install_languages
    grep -Fxq "es-ES" "$W/packs"
    [ "$(pref OPACLanguages)" = "es-ES,en,pt-BR" ]
    [ "$(pref StaffInterfaceLanguages)" = "es-ES,en" ]
    grep -q "RESULT panel_lang=es-ES" "$W/results"
    dialogs | grep -q "Language 'es-ES' enabled successfully"
}

@test "L8 download and activate without Koha: only the panel language" {
    touch "$W/no-koha"
    inputs es-ES
    lang function_install_languages
    grep -q "PANEL es-ES" "$W/results"
    [ ! -e "$W/calls" ]
}

@test "L9 list: installed packs with the active and enabled ones" {
    mysql "$DB" -e "UPDATE systempreferences SET value = 'pt-BR,en' WHERE variable = 'OPACLanguages';"
    lang function_lang_list
    grep -E "^  pt-BR +Português \(Brasil\) +OPAC: ACTIVE +Staff: -" "$KEI_S/textboxes.log"
    grep -E "^  en +English +OPAC: enabled +Staff: ACTIVE" "$KEI_S/textboxes.log"
    grep -q "Active in the OPAC: pt-BR" "$KEI_S/textboxes.log"
    grep -q "Active in the staff interface: en" "$KEI_S/textboxes.log"
}

@test "L10 the first install still downloads the pack of the server's language" {
    # Koha's Web Installer then asks for the language and makes it active.
    run grep -A6 'auto_lang=$(detect_koha_locale)' "$KEI_REPO/installer"
    [[ "$output" == *'koha-translate --install "$auto_lang"'* ]]
}
