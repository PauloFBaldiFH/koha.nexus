# shellcheck shell=bash disable=SC2034  # variables here are read by the installer
# Test doubles loaded by tests/lib/panel.sh AFTER the installer: dialogs are
# recorded instead of drawn, answers come from a queue, and a few system
# probes can be steered from the tests. Everything else (mysql, mysqldump,
# gzip, flock, the restore logic itself) is the real thing.
KEI_S=/run/kei-mock
mkdir -p "$KEI_S"

# ---- dialogs ---------------------------------------------------------
_kei_dialog() { printf '%s\n' "$*" >> "$KEI_S/dialogs.log"; }
whiptail()       { _kei_dialog "whiptail $*"; return 0; }
msg_info()       { _kei_dialog "INFO [$1] $2"; }
msg_ok()         { _kei_dialog "OK $1"; }
msg_error()      { _kei_dialog "ERROR [$1] $2"; }
clear()          { :; }
pause_terminal() { :; }
show_validation_report()     { :; }
show_restore_transfer_help() { :; }
validate_complete_system()   { _kei_dialog "VALIDATE $*"; V_FAIL=0; V_WARN=0; V_OK=1; return 0; }

# Yes/no answers are read from $KEI_S/answers, one per line ("yes"/"no");
# when the queue is empty the answer is ${KEI_DEFAULT_ANSWER:-yes}.
prompt_yes_no() {
    local ans=""
    if [ -s "$KEI_S/answers" ]; then
        ans=$(head -n1 "$KEI_S/answers")
        sed -i '1d' "$KEI_S/answers"
    fi
    ans="${ans:-${KEI_DEFAULT_ANSWER:-yes}}"
    _kei_dialog "PROMPT [$1] $2 => $ans"
    [ "$ans" = "yes" ]
}
select_file()      { printf '%s' "${KEI_SELECT_FILE:-}"; [ -n "${KEI_SELECT_FILE:-}" ]; }

# Menus and input boxes of the library tools: answers from $KEI_S/inputs,
# one per line. With an empty queue a menu takes its first tag and an input
# box its default value; "CANCEL" cancels the dialog. Menu texts go to
# $KEI_S/menus.log. Text boxes are
# recorded (the last one shown is kept in $KEI_S/textbox.last).
_kei_next_input() {
    local ans=""
    if [ -s "$KEI_S/inputs" ]; then
        ans=$(head -n1 "$KEI_S/inputs")
        sed -i '1d' "$KEI_S/inputs"
    fi
    printf '%s' "$ans"
}
ui_menu() {
    local title="$1" ans
    printf '[%s] %s\n' "$1" "$2" >> "$KEI_S/menus.log"
    shift 2
    ans=$(_kei_next_input); [ -n "$ans" ] || ans="${1:-}"
    _kei_dialog "MENU [$title] => $ans"
    [ "$ans" = "CANCEL" ] && return 1
    printf '%s' "$ans"
}
ui_input() {
    local ans
    ans=$(_kei_next_input); [ -n "$ans" ] || ans="${3:-}"
    _kei_dialog "INPUT [$1] $2 => $ans"
    [ "$ans" = "CANCEL" ] && return 1
    printf '%s' "$ans"
}
ui_textbox() {
    _kei_dialog "TEXTBOX [$1] $2"
    cp -f "$2" "$KEI_S/textbox.last" 2>/dev/null
    { printf '=== %s\n' "$1"; cat "$2" 2>/dev/null; } >> "$KEI_S/textboxes.log"
    return 0
}
# Checklist: one input line with the chosen tags (space separated); an
# empty queue keeps the items that start ON. "CANCEL" cancels.
ui_checklist() {
    local title="$1" ans tags=()
    shift 2
    while [ $# -ge 3 ]; do [ "$3" = "ON" ] && tags+=("$1"); shift 3; done
    ans=$(_kei_next_input); [ -n "$ans" ] || ans="${tags[*]}"
    _kei_dialog "CHECKLIST [$title] => $ans"
    [ "$ans" = "CANCEL" ] && return 1
    printf '%s\n' $ans
}
select_directory() { printf '%s' "${KEI_SELECT_DIR:-}";  [ -n "${KEI_SELECT_DIR:-}" ]; }

# ---- packages and platform --------------------------------------------
apt_install()        { printf 'apt_install %s\n' "$*" >> "$KEI_S/calls.log"; return 0; }
apt_update_indices() { return 0; }
wait_for_apt_locks() { return 0; }

# "dpkg -s PKG" succeeds when $KEI_S/pkgs/PKG exists; the architecture comes
# from $KEI_ARCH. Everything else goes to the real dpkg.
dpkg() {
    case "${1:-}" in
        -s) [ -e "$KEI_S/pkgs/${2:-}" ] ;;
        --print-architecture) printf '%s\n' "${KEI_ARCH:-amd64}" ;;
        *) command dpkg "$@" ;;
    esac
}
uname() {
    if [ "${1:-}" = "-m" ] && [ -n "${KEI_MACHINE:-}" ]; then printf '%s\n' "$KEI_MACHINE"; else command uname "$@"; fi
}

# Shorter waits keep the "MariaDB is down" scenarios fast.
DB_WAIT_SECONDS="${KEI_DB_WAIT_SECONDS:-2}"
