#!/usr/bin/env bats
# Server sizing: the six RAM profiles, the recommended one, the cap of two
# Plack workers per CPU core and the RAM a profile needs. Runs the helpers
# alone, without a Koha server.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    sed -n '/^sizing_profile() {/,/^function_size_server() {/p' "$REPO/installer" | sed '$d' > "$W/sizing.sh"
}

run_sz() { bash -c "source '$W/sizing.sh'; $1"; }

@test "S01 every RAM size gets its profile" {
    for pair in 1:1 3:1 4:2 7:2 8:3 15:3 16:4 23:4 24:5 27:5 31:5 47:5 48:6 63:6 128:6; do
        run run_sz "sizing_recommended ${pair%%:*}"
        [ "$output" = "${pair##*:}" ]
    done
}

@test "S02 the profiles keep their values and the large ones grow" {
    run run_sz "sizing_profile 1"; [ "$output" = "2 64 512M" ]
    run run_sz "sizing_profile 4"; [ "$output" = "6 256 2G" ]
    run run_sz "sizing_profile 5"; [ "$output" = "8 512 4G" ]
    run run_sz "sizing_profile 6"; [ "$output" = "12 1024 8G" ]
    run run_sz "sizing_profile 7"; [ "$status" -ne 0 ]
}

@test "S03 the menu offers every profile the helper knows" {
    for n in 1 2 3 4 5 6; do
        grep -qE "^        \"$n\" \"[^\"]+ - [0-9]+ Plack" "$REPO/installer"
    done
    grep -q '"5" "24-48 GB - 8 Plack, 512MB cache, 4G InnoDB"' "$REPO/installer"
    grep -q '"6" "48 GB+   - 12 Plack, 1GB cache, 8G InnoDB"' "$REPO/installer"
}

@test "S04 Plack workers stop at two per CPU core, never under 2" {
    run run_sz "sizing_cap_workers 12 4";  [ "$output" = "8" ]
    run run_sz "sizing_cap_workers 12 16"; [ "$output" = "12" ]
    run run_sz "sizing_cap_workers 6 1";   [ "$output" = "2" ]
    run run_sz "sizing_cap_workers 2 1";   [ "$output" = "2" ]
    run run_sz "sizing_cap_workers 8 junk"; [ "$output" = "2" ]
}

@test "S05 the RAM a profile needs counts every site's workers and Elasticsearch" {
    run run_sz "sizing_need_mb 8 1 512 4G 0";  [ "$output" = "7808" ]
    run run_sz "sizing_need_mb 8 2 512 4G 4";  [ "$output" = "15104" ]
    run run_sz "sizing_need_mb 2 1 64 512M 0"; [ "$output" = "1376" ]
    run run_sz "sizing_need_mb 2 0 64 512M 0"; [ "$output" = "1376" ]
}

@test "S06 the large profiles fit in 80% of the RAM they are meant for" {
    # Lowest RAM of each band, one site, Elasticsearch at its 4 GB cap.
    for pair in 24:5 48:6; do
        g=${pair%%:*} p=${pair##*:} es=4
        read -r wk mem db <<< "$(run_sz "sizing_profile $p")"
        need=$(run_sz "sizing_need_mb $wk 1 $mem $db $es")
        [ "$need" -le $(( g * 1024 * 8 / 10 )) ]
    done
}

@test "S07 a larger profile than recommended, or a large one, is checked before applying" {
    sed -n '/^function_size_server() {/,/^}/p' "$REPO/installer" > "$W/fn.sh"
    grep -q 'profile" -gt "\$recommended"' "$W/fn.sh"
    grep -q 'profile" -ge 5' "$W/fn.sh"
    grep -q 'ram_mb \* 8 / 10' "$W/fn.sh"
    grep -q 'defaultno || return 0' "$W/fn.sh"
}
