#!/usr/bin/env bats
# Restore database and the Magic Import Tool read a dump compressed with
# gzip, bzip2, xz or zstd, recognised from its first bytes (not its name).
# Runs the dump helpers alone; needs gzip, bzip2, xz and zstd.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    sed -n '/^dump_codec() {/,/^# Streams a .sql backup/p' "$REPO/installer" > "$W/dump.sh"
    printf -- '-- MariaDB dump 10.19\nCREATE TABLE `biblio` (x int);\n-- Dump completed on 2026-10-09\n' > "$W/k.sql"
}

@test "each compression is recognised from its bytes and read back" {
    command -v zstd >/dev/null || skip "zstd not installed"
    gzip -c "$W/k.sql" > "$W/a.sql.gz"
    bzip2 -c "$W/k.sql" > "$W/b.sql.bz2"
    xz -c "$W/k.sql" > "$W/c.sql.xz"
    zstd -q -c "$W/k.sql" > "$W/d.sql.zst"
    cp "$W/d.sql.zst" "$W/renamed.sql"
    for f in k.sql a.sql.gz b.sql.bz2 c.sql.xz d.sql.zst renamed.sql; do
        run bash -c "source '$W/dump.sh'; dump_codec '$W/$f'; dump_test '$W/$f' && echo intact; dump_cat '$W/$f' | md5sum"
        [ "${lines[1]}" = "intact" ]
        [ "${lines[2]}" = "$(md5sum < "$W/k.sql")" ]
    done
    run bash -c "source '$W/dump.sh'; for f in k.sql a.sql.gz b.sql.bz2 c.sql.xz d.sql.zst renamed.sql; do dump_codec '$W/'\$f; done | tr '\n' ' '"
    [ "$output" = "plain gz bz2 xz zst zst " ]
}

@test "a damaged compressed dump fails its test" {
    command -v zstd >/dev/null || skip "zstd not installed"
    zstd -q -c "$W/k.sql" | head -c 20 > "$W/cut.sql.zst"
    run bash -c "source '$W/dump.sh'; dump_test '$W/cut.sql.zst'"
    [ "$status" -ne 0 ]
    bzip2 -c "$W/k.sql" | head -c 20 > "$W/cut.sql.bz2"
    run bash -c "source '$W/dump.sh'; dump_test '$W/cut.sql.bz2'"
    [ "$status" -ne 0 ]
}
