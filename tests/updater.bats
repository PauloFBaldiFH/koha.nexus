#!/usr/bin/env bats
# "Update this panel via GitHub" (section 26 of the installer): the installer
# and installer.sha256 must come from the same commit, so that GitHub's raw
# cache (up to 5 minutes per file) can't pair a new script with an old hash.
# Runs update_resolve/update_fetch alone with a fake curl; no network needed.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    sed -n '/^update_resolve() {/,/^function_autoupdate() {/p' "$REPO/installer" | sed '$d' > "$W/update.sh"
    SHA=0123456789abcdef0123456789abcdef01234567
    # Fake GitHub: $W/web/<url without https://> is the body of that URL.
    mkdir -p "$W/web/api.github.com/repos/Owner/repo/commits"
    printf '%s' "$SHA" > "$W/web/api.github.com/repos/Owner/repo/commits/main"
    publish "$W/web/raw.githubusercontent.com/Owner/repo/$SHA" 'PANEL_VERSION=" 9.9.9"'
    # The branch copy is a stale mix: new script, hash of the old one.
    publish "$W/web/raw.githubusercontent.com/Owner/repo/refs/heads/main" 'PANEL_VERSION=" 9.9.9"'
    printf 'old\n' | sha256sum | sed 's/-$/installer/' > "$W/web/raw.githubusercontent.com/Owner/repo/refs/heads/main/installer.sha256"
}

publish() {
    mkdir -p "$1"
    printf '%s\n' "$2" > "$1/installer"
    (cd "$1" && sha256sum installer > installer.sha256)
}

# run_update URL CODE: sources the helpers with a fake curl serving $W/web
# and prints UPDATE_COMMIT, UPDATE_BASE and update_fetch's return code.
run_update() {
    bash -c "
        W='$W'
        log() { echo \"log: \$*\" >> \"\$W/log\"; }
        curl() {
            local out='' url='' a
            while [ \$# -gt 0 ]; do
                case \"\$1\" in
                    -o) out=\"\$2\"; shift ;;
                    -H|--retry|--retry-delay|--connect-timeout|--max-time) shift ;;
                    http*) url=\"\$1\" ;;
                esac
                shift
            done
            echo \"\$url\" >> \"\$W/calls\"
            local f=\"\$W/web/\${url#https://}\"
            [ -f \"\$f\" ] || return 22
            if [ -e \"\$W/truncate-once\" ] && [[ \"\$url\" == */installer ]]; then
                rm -f \"\$W/truncate-once\"; head -c 5 \"\$f\" > \"\$out\"; return 0
            fi
            if [ -n \"\$out\" ]; then cp \"\$f\" \"\$out\"; else cat \"\$f\"; fi
        }
        source '$W/update.sh'
        UPDATE_URL='$1'
        update_resolve
        rc=0; update_fetch \"\$W/script\" \"\$W/sum\" || rc=\$?
        echo \"commit=\$UPDATE_COMMIT\"
        echo \"base=\$UPDATE_BASE\"
        echo \"rc=\$rc\"
    "
}

BRANCH_URL=https://raw.githubusercontent.com/Owner/repo/refs/heads/main/installer

@test "the script and its hash come from the commit main points to" {
    run run_update "$BRANCH_URL"
    [[ "$output" == *"commit=$SHA"* ]]
    [[ "$output" == *"base=https://raw.githubusercontent.com/Owner/repo/$SHA/"* ]]
    [[ "$output" == *"rc=0"* ]]
    ! grep -q refs/heads "$W/calls"
    grep -q '9.9.9' "$W/script"
}

@test "a tampered script at the pinned commit is refused" {
    printf 'evil\n' > "$W/web/raw.githubusercontent.com/Owner/repo/$SHA/installer"
    run run_update "$BRANCH_URL"
    [[ "$output" == *"commit=$SHA"* ]]
    [[ "$output" == *"rc=2"* ]]
    [ "$(grep -c "$SHA/installer\$" "$W/calls")" = 2 ]
}

@test "a download cut short is fetched again before it counts as a mismatch" {
    touch "$W/truncate-once"
    run run_update "$BRANCH_URL"
    [[ "$output" == *"rc=0"* ]]
    grep -q '9.9.9' "$W/script"
    grep -q 'attempt 1' "$W/log"
}

@test "without GitHub's API the branch is used, and a stale pair still fails" {
    rm "$W/web/api.github.com/repos/Owner/repo/commits/main"
    run run_update "$BRANCH_URL"
    [[ "$output" == *"commit="$'\n'* ]]
    [[ "$output" == *"base=https://raw.githubusercontent.com/Owner/repo/refs/heads/main/"* ]]
    [[ "$output" == *"rc=2"* ]]
}

@test "an update URL outside GitHub is used as it is" {
    mkdir -p "$W/web/mirror.example/koha"
    publish "$W/web/mirror.example/koha" 'PANEL_VERSION=" 9.9.9"'
    run run_update https://mirror.example/koha/installer
    [[ "$output" == *"base=https://mirror.example/koha/"* ]]
    [[ "$output" == *"rc=0"* ]]
    ! grep -q api.github.com "$W/calls"
}

@test "a missing hash file is a download failure, not a pass" {
    rm "$W/web/raw.githubusercontent.com/Owner/repo/$SHA/installer.sha256"
    run run_update "$BRANCH_URL"
    [[ "$output" == *"rc=1"* ]]
}
