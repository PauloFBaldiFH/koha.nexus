#!/usr/bin/env bats
# Server sizing: the six RAM profiles, the recommended one, the cap of two
# Plack workers per CPU core and the RAM a profile needs. Runs the helpers
# alone, without a Koha server.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    {
        sed -n '/^ES_HEAP_CAP_FILE=/,/^adjust_elasticsearch_heap() {/p' "$REPO/installer" | sed '$d'
        sed -n '/^sizing_profile() {/,/^function_size_server() {/p' "$REPO/installer" | sed '$d'
    } > "$W/sizing.sh"
    sed -i "s|^ES_HEAP_CAP_FILE=.*|ES_HEAP_CAP_FILE='$W/es-heap-cap'|" "$W/sizing.sh"
}

run_sz() { bash -c "source '$W/sizing.sh'; $1"; }

@test "S01 every RAM size gets its profile" {
    for pair in 1:1 3:1 4:2 7:2 8:3 15:3 16:4 23:4 24:5 27:5 31:5 47:5 48:6 63:6 128:6; do
        run run_sz "sizing_recommended ${pair%%:*}"
        [ "$output" = "${pair##*:}" ]
    done
}

@test "S02 the profiles keep their values and the large ones grow" {
    run run_sz "sizing_profile 1"; [ "$output" = "2 64 512M 100 - 4" ]
    run run_sz "sizing_profile 4"; [ "$output" = "6 256 2G 100 - 4" ]
    run run_sz "sizing_profile 5"; [ "$output" = "8 512 4G 500 1G 6" ]
    run run_sz "sizing_profile 6"; [ "$output" = "12 1024 8G 500 2G 8" ]
    run run_sz "sizing_profile 7"; [ "$status" -ne 0 ]
}

@test "S03 the menu offers every profile the helper knows" {
    for n in 1 2 3 4 5 6; do
        grep -qE "^        \"$n\" \"[^\"]+ - [0-9]+ Plack" "$REPO/installer"
    done
    grep -q '"5" "24-48 GB - 8 Plack, 512MB cache, 4G InnoDB, ES 6G"' "$REPO/installer"
    grep -q '"6" "48 GB+   - 12 Plack, 1GB cache, 8G InnoDB, ES 8G"' "$REPO/installer"
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
    # Lowest RAM of each band, one site, Elasticsearch at the profile's cap.
    for pair in 24:5 48:6; do
        g=${pair%%:*} p=${pair##*:}
        read -r wk mem db _ _ cap <<< "$(run_sz "sizing_profile $p")"
        es=$(run_sz "es_heap_gb $(( g * 1024 )) $cap")
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

@test "S08 Elasticsearch: half the RAM up to the cap; the saved cap survives a reinstall" {
    run run_sz "es_heap_gb 28057 4";  [ "$output" = "4" ]
    run run_sz "es_heap_gb 28057 6";  [ "$output" = "6" ]
    run run_sz "es_heap_gb 65536 8";  [ "$output" = "8" ]
    run run_sz "es_heap_gb 8192 8";   [ "$output" = "4" ]
    run run_sz "es_heap_gb 1024 4";   [ "$output" = "1" ]
    run run_sz "es_heap_cap"; [ "$output" = "4" ]
    echo 8 > "$W/es-heap-cap";  run run_sz "es_heap_cap"; [ "$output" = "8" ]
    echo 99 > "$W/es-heap-cap"; run run_sz "es_heap_cap"; [ "$output" = "4" ]
    echo junk > "$W/es-heap-cap"; run run_sz "es_heap_cap"; [ "$output" = "4" ]
    grep -q 'es_heap_gb "$(awk' "$REPO/installer"
}

@test "S09 the large profiles write the redo log and recycle workers less; the small ones do not" {
    sed -n '/^function_size_server() {/,/^}/p' "$REPO/installer" > "$W/fn.sh"
    grep -q 'PLACK_MAX_REQUESTS=$maxreq' "$W/fn.sh"
    grep -q "innodb_log_file_size = %s" "$W/fn.sh"
    grep -q 'if \[ "$redo" != "-" \]' "$W/fn.sh"
    grep -q 'rm -f "$ES_HEAP_CAP_FILE"' "$W/fn.sh"
    for n in 1 2 3 4; do run run_sz "sizing_profile $n"; [[ "$output" == *" 100 - 4" ]]; done
}
