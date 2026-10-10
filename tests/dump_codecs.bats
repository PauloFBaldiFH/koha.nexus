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

@test "the kind of a backup is read from its content, whatever its name" {
    mkdir "$W/pg" && echo x > "$W/pg/toc.dat" && tar cf "$W/pg (3).bkp" -C "$W/pg" toc.dat
    printf 'PGDMP\001\016\000' > "$W/BKP_BIBLIOTECA (2).backup"
    printf -- '--\n-- PostgreSQL database dump\n--\nCOPY public.livros (id) FROM stdin;\n1\n\\.\n' > "$W/pg (2).dump"
    gzip -c "$W/k.sql" > "$W/koha (2).backup"
    tar czf "$W/arch (2).tar" -C "$W" k.sql
    printf 'SQLite format 3\000x' > "$W/s.bkp"
    : > "$W/empty.dump"
    run bash -c "source '$W/dump.sh'; for f in 'koha (2).backup' 'BKP_BIBLIOTECA (2).backup' 'pg (3).bkp' 'pg (2).dump' 'arch (2).tar' s.bkp empty.dump; do dump_kind \"$W/\$f\"; done | tr '\n' ' '"
    [ "$output" = "mysql pg_custom pg_tar pg_plain tar sqlite empty " ]
}

@test "Restore database refuses a PostgreSQL backup and an archive, and says why" {
    printf -- '--\n-- PostgreSQL database dump\n--\nCREATE TABLE public.livros (id integer);\n' > "$W/pg (2).backup"
    tar cf "$W/k.tar" -C "$W" k.sql
    for f in "pg (2).backup" k.tar k.sql; do
        run bash -c "t() { printf '%s' \"\$1\"; }; source '$W/dump.sh'; sed -n '/^check_dump_file() {/,/^}/p' '$REPO/installer' > '$W/check.sh'; source '$W/check.sh'; dump_is_complete() { return 0; }; check_dump_file \"$W/$f\"; echo \"rc=\$? \$DUMP_ERROR\""
        case "$f" in
            pg*)   [[ "$output" == "rc=1 This is a PostgreSQL backup, not a MariaDB/MySQL one."* ]] ;;
            k.tar) [[ "$output" == "rc=1 This is an archive (tar or zip)"* ]] ;;
            *)     [ "$output" = "rc=0 " ] ;;
        esac
    done
}

@test "a Koha backup in a tar.gz or zip is unpacked for Restore database; a PostgreSQL one is refused" {
    mkdir -p "$W/in"
    cp "$W/k.sql" "$W/in/BKP_BIBLIOTECA (2).sql"
    printf 'x' > "$W/in/readme.txt"
    tar czf "$W/BKP (2).tar.gz" -C "$W/in" .
    (cd "$W/in" && zip -q "$W/BKP (3).zip" "BKP_BIBLIOTECA (2).sql")
    mkdir "$W/pg" && echo x > "$W/pg/toc.dat" && tar cf "$W/pg.tar" -C "$W/pg" toc.dat
    sed -n '/^restore_unpack() {/,/^}/p' "$REPO/installer" > "$W/unpack.sh"
    for f in "BKP (2).tar.gz:tar" "BKP (3).zip:zip" "pg.tar:tar"; do
        run bash -c "set -o pipefail; t() { printf '%s' \"\$1\"; }; log() { :; }; get_free_space_mb() { echo 99999; }; source '$W/dump.sh'; source '$W/unpack.sh'; restore_unpack \"$W/${f%:*}\" ${f#*:}; echo \"rc=\$? \$RESTORE_UNPACK_FILE|\$RESTORE_UNPACK_ERROR\"; rm -rf \"\$RESTORE_UNPACK_DIR\""
        case "$f" in
            pg*) [[ "$output" == "rc=1 |This is a PostgreSQL backup"* ]] ;;
            *)   [[ "$output" == "rc=0 /var/tmp/kei-unpack."*"/BKP_BIBLIOTECA (2).sql|" ]] ;;
        esac
    done
}

@test "a compressed Koha backup is recognised as one (no SIGPIPE under pipefail)" {
    { cat "$W/k.sql"; for t in biblio_metadata items borrowers systempreferences; do printf 'CREATE TABLE `%s` (x int);\n' "$t"; done; seq 1 200000 | sed 's/^/INSERT INTO `x` VALUES (/; s/$/);/'; } | gzip > "$W/BKP_BIBLIOTECA (2).backup"
    sed -n '/^magic_is_koha_dump() {/,/^}/p' "$REPO/installer" > "$W/koha.sh"
    run bash -c "set -o pipefail; source '$W/dump.sh'; source '$W/koha.sh'; magic_is_koha_dump \"$W/BKP_BIBLIOTECA (2).backup\""
    [ "$status" -eq 0 ]
}
