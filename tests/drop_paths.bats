#!/usr/bin/env bats
# A file dropped on the terminal (Windows Terminal pastes 'C:\...' or
# "C:\..." with backslashes) becomes a path of this machine (clean_path),
# and keys left waiting in the terminal never answer the next prompt
# (flush_tty_input). Runs the two helpers alone.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    {
        sed -n '/^clean_path() {/,/^}/p' "$REPO/installer"
        sed -n '/^flush_tty_input() {/,/^}/p' "$REPO/installer"
    } > "$W/drop.sh"
    mkdir -p "$W/bin"
    # Only the tools a test asks for: no wslpath unless a stub is written.
    export PATH="$W/bin:/usr/bin:/bin"
}

clean() { bash -c "source '$W/drop.sh'; clean_path \"\$1\"" _ "$1"; }

@test "quotes, backslashes and a Windows line break are removed; drives go to /mnt" {
    run clean "'C:\\Users\\Ana\\Downloads\\BKP_BIBLIOTECA (2).backup'"$'\r\n'
    [ "$output" = "/mnt/c/Users/Ana/Downloads/BKP_BIBLIOTECA (2).backup" ]
    run clean '"D:\backups\koha.sql.gz"'
    [ "$output" = "/mnt/d/backups/koha.sql.gz" ]
    run clean "& 'C:\\Koha\\Importar\\acervo.mrc'"
    [ "$output" = "/mnt/c/Koha/Importar/acervo.mrc" ]
    run clean '  \\wsl.localhost\koha\root\b.sql  '
    [ "$output" = "/root/b.sql" ]
}

@test "under WSL wslpath converts the drive path; its failure falls back to /mnt" {
    cat > "$W/bin/wslpath" <<'SH'
#!/bin/bash
[ "$1" = "-u" ] || exit 2
[ -n "${KEI_WSLPATH_FAIL:-}" ] && exit 1
printf '/c/%s\n' "$(printf '%s' "${2#?:\\}" | tr '\\' '/')"
SH
    chmod +x "$W/bin/wslpath"
    run clean '"C:\Users\Ana\My Backup.sql"'
    [ "$output" = "/c/Users/Ana/My Backup.sql" ]
    KEI_WSLPATH_FAIL=1 run clean '"C:\Users\Ana\My Backup.sql"'
    [ "$output" = "/mnt/c/Users/Ana/My Backup.sql" ]
}

@test "keys waiting on a terminal are thrown away; a pipe keeps its input" {
    run bash -c "source '$W/drop.sh'; printf 'kept\n' | { flush_tty_input; read -r l; echo \"\$l\"; }"
    [ "$output" = "kept" ]
    command -v script >/dev/null || skip "script (util-linux) is not installed"
    # Typed ahead on a real terminal: the Enter and the Esc never reach read.
    printf 'source %q; sleep 0.3; flush_tty_input; read -r -t 1 l; echo "got[$l]"\n' "$W/drop.sh" > "$W/t.sh"
    run bash -c "printf 'x\n\033\n' | script -qec 'bash $W/t.sh' /dev/null"
    [[ "$output" == *"got[]"* ]]
}
