#!/usr/bin/env bats
# Synthetic failure boundaries. Run inside the disposable harness described
# in tests/README.md; these tests never use an installed library database.

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_tools_catalog
    kei_br_catalog
    unset KEI_EXTRA KEI_SELECT_FILE KEI_DEFAULT_ANSWER KEI_TASK KEI_TASK_INTERACTIVE KEI_DRAFT_CANCEL_REVIEW
    W="$BATS_TEST_TMPDIR"
    export KEI_DRAFT_FILE="$W/synthetic (7).xml"
    cat > "$KEI_DRAFT_FILE" <<'XML'
<collection xmlns="http://www.loc.gov/MARC21/slim"><record><leader>00000nam a2200000 a 4500</leader><controlfield tag="001">SYN-BIB-1</controlfield><datafield tag="245" ind1="0" ind2="0"><subfield code="a">Synthetic title</subfield></datafield></record></collection>
XML
}

teardown() {
    kei_kill_daemons
}

extra() { printf '%s\n' "$@" > "$W/extra.sh"; export KEI_EXTRA="$W/extra.sh"; }
append_extra() { printf '%s\n' "$@" >> "$KEI_EXTRA"; }
tool_logs() { cat /var/log/koha-easy-install/tools/*.log 2>/dev/null; }

# The backup double records whether a backup was requested. Backup creation and
# verification have their own real-MariaDB battery in tests/backup.bats.
tool_double() {
    export KEI_DRAFT_TOOL_MODE="$1"
    extra 'tools_safety_backup() {
    printf "backup %s\n" "$1" >> "$KEI_S/calls.log"
    TOOLS_PRE=/synthetic/PRE-IMPORT.sql.gz
    return 0
}
koha_tool() {
    local logfile="$1" script="$2" kind=biblio argument
    shift 2
    printf "%s\n" "$script" >> "$KEI_S/calls.log"
    printf "$ %s\n" "$script" >> "$logfile"
    case "$script" in
        stage_file.pl)
            printf "%s\0" "$@" > "$KEI_S/draft-stage-argv.bin"
            if [ "$KEI_DRAFT_TOOL_MODE" = stage-failure ]; then
                # A convincing partial report must never override exit 29.
                printf "Batch number assigned: 1\nNumber of valid records: 1\nSYN-STAGE-29: record decoding aborted\n" >> "$logfile"
                return 29
            fi
            for argument in "$@"; do [ "$argument" = --authorities ] && kind=auth; done
            run_sql "INSERT INTO ${DB_NAME}.import_batches (import_batch_id,num_records,import_status,record_type) VALUES (1,1,\"staged\",\"$kind\"); INSERT INTO ${DB_NAME}.import_records (import_batch_id,record_sequence,status) VALUES (1,1,\"staged\");" >/dev/null || return 2
            if [ "$KEI_DRAFT_TOOL_MODE" = commit-item-error ]; then
                run_sql "INSERT INTO ${DB_NAME}.import_items (import_record_id,status) SELECT import_record_id,\"staged\" FROM ${DB_NAME}.import_records WHERE import_batch_id=1;" >/dev/null || return 2
            fi
            printf "Batch number assigned: 1\nNumber of valid records: 1\n" >> "$logfile"
            return 0
            ;;
        commit_file.pl|kei_commit_authorities.pl)
            if [ "$KEI_DRAFT_TOOL_MODE" = commit-error ]; then
                # Koha/process wrappers can return 0 despite a per-record error.
                # The concrete diagnostic exists ONLY in the database. The
                # importer must fetch it rather than rely on a CLI report.
                run_sql "UPDATE ${DB_NAME}.import_batches SET import_status=\"imported\" WHERE import_batch_id=1; UPDATE ${DB_NAME}.import_records SET status=\"error\",import_error=\"SYN-COMMIT-952: invalid target branch SYN-NOT-A-BRANCH\" WHERE import_batch_id=1;" >/dev/null || return 2
                printf "Number of new records added: 0\nNumber of records replaced: 0\nNumber of items added: 0\n" >> "$logfile"
                return 0
            fi
            if [ "$KEI_DRAFT_TOOL_MODE" = commit-item-error ]; then
                run_sql "UPDATE ${DB_NAME}.import_batches SET import_status=\"imported\" WHERE import_batch_id=1; UPDATE ${DB_NAME}.import_records SET status=\"imported\" WHERE import_batch_id=1; UPDATE ${DB_NAME}.import_items ii JOIN ${DB_NAME}.import_records ir USING (import_record_id) SET ii.status=\"error\",ii.import_error=\"SYN-ITEM-952: barcode SYN-DUPLICATE already exists\" WHERE ir.import_batch_id=1;" >/dev/null || return 2
                printf "Number of new records added: 1\nNumber of records replaced: 0\nNumber of items added: 0\nNumber of items ignored: 1\n" >> "$logfile"
                return 0
            fi
            run_sql "UPDATE ${DB_NAME}.import_batches SET import_status=\"imported\" WHERE import_batch_id=1; UPDATE ${DB_NAME}.import_records SET status=\"imported\" WHERE import_batch_id=1;" >/dev/null || return 2
            printf "Number of new records added: 1\nNumber of records replaced: 0\nNumber of items added: 0\n" >> "$logfile"
            return 0
            ;;
        *) printf "Unexpected synthetic tool: %s\n" "$script" >> "$logfile"; return 127 ;;
    esac
}'
}

# Drive the real orchestration with a documented engine result, independently
# of heuristic choices. The engine itself is covered by the Python fixtures.
engine_double() {
    export KEI_DRAFT_KIND="$1" KEI_DRAFT_SEVERITY="${2:-none}"
    append_extra 'kei_import_write() { mkdir -p "$1"; }
magic_target_snapshot() { return 0; }
magic_can_map() { return 1; }
magic_engine() {
    local logfile="$1" operation="$2" errors=0 warnings=0 records=1 authorities=0 blocked=false
    printf "$ kei_import %s\n" "$operation" >> "$logfile"
    case "$operation" in
        analyse)
            if [ "${KEI_DRAFT_CANCEL_REVIEW:-}" = 1 ] && [ ! -f "$MAGIC_WORK/review-answered" ]; then
                printf "Importable: 1\nQuestions: 1\nSettings:\n" >> "$logfile"
            else
                printf "Importable: 1\nQuestions: 0\nSettings:\n" >> "$logfile"
            fi
            return 0 ;;
        fields)
            printf "{\"version\":2}\n" > "$MAGIC_WORK/fields.json"
            printf "Fields: 1\nReview issues: 1\n" >> "$logfile"
            return 0 ;;
        build)
            mkdir -p "$MAGIC_WORK/out" || return 2
            cp "$KEI_DRAFT_FILE" "$MAGIC_WORK/out/prepared.xml" || return 2
            [ "$KEI_DRAFT_KIND" = authorities ] && { records=0; authorities=1; }
            printf "%s\tMARCXML\tUTF-8\t%s\t1\t0\t\tsynthetic (7).xml\n" "$KEI_DRAFT_KIND" "$MAGIC_WORK/out/prepared.xml" > "$MAGIC_WORK/out/manifest.tsv"
            printf "Synthetic dry-run preview\n" > "$MAGIC_WORK/out/preview.txt"
            case "$KEI_DRAFT_SEVERITY" in
                error) errors=1; blocked=true ;;
                warning) warnings=1 ;;
            esac
            if [ "$KEI_DRAFT_SEVERITY" = none ]; then
                printf "{\"version\":1,\"issues\":[],\"errors\":0,\"warnings\":0,\"blocked\":false}\n" > "$MAGIC_WORK/out/validation.json"
            else
                printf "{\"version\":1,\"issues\":[{\"severity\":\"%s\",\"code\":\"synthetic-review\",\"message\":\"SYN-REVIEW: source field needs attention\"}],\"errors\":%s,\"warnings\":%s,\"blocked\":%s}\n" "$KEI_DRAFT_SEVERITY" "$errors" "$warnings" "$blocked" > "$MAGIC_WORK/out/validation.json"
            fi
            printf "Total records: %s\nTotal authorities: %s\nTotal items: 0\nTotal patrons: 0\nTotal loans: 0\nTotal holds: 0\nCasing fixes: 0\nEncoding fixes: 0\nAnomalies: 0\n" "$records" "$authorities" >> "$logfile"
            return 0 ;;
        *) printf "Unexpected synthetic engine operation: %s\n" "$operation" >> "$logfile"; return 2 ;;
    esac
}'
}

@test "R01 nonzero staging status overrides a partial success report: no backup or commit" {
    tool_double stage-failure
    answer yes
    panel eval 'tools_workdir && _lt_marc_import_run "$KEI_DRAFT_FILE" MARCXML UTF-8 new'
    assert '[ "$status" -ne 0 ]' "staging exit 29 must propagate as an import failure: $output"
    assert 'grep -qx stage_file.pl "$KEI_S/calls.log"' "staging must actually be attempted"
    assert '! grep -qE "^(backup |commit_file.pl$)" "$KEI_S/calls.log"' "a failed stage must not reach backup/commit: $(calls)"
    assert 'tool_logs | grep -qF "SYN-STAGE-29: record decoding aborted"' "the exact stage diagnostic must remain in the import log"
    assert '! dialogs | grep -q "^OK "' "no success message after staging fails"
}

@test "R02 zero process status with an error import record fails and retains the exact diagnostic" {
    tool_double commit-error
    answer yes
    panel eval 'tools_workdir && _lt_marc_import_run "$KEI_DRAFT_FILE" MARCXML UTF-8 new'
    assert '[ "$status" -ne 0 ]' "DB record status error must override commit exit 0: $output"
    assert 'grep -qx "backup IMPORT" "$KEI_S/calls.log" && grep -qx commit_file.pl "$KEI_S/calls.log"' "this fixture must reach the protected commit"
    assert '[ "$(tools_sql "SELECT status FROM import_records WHERE import_batch_id=1;")" = error ]' "the simulated Koha error must be present in the DB"
    assert '[ "$(tools_sql "SELECT import_error FROM import_records WHERE import_batch_id=1;")" = "SYN-COMMIT-952: invalid target branch SYN-NOT-A-BRANCH" ]'
    assert 'tool_logs | grep -qF "SYN-COMMIT-952: invalid target branch SYN-NOT-A-BRANCH"' "the concrete import error must be available to the operator"
    assert '! dialogs | grep -q "^OK "' "a zero-record failed batch must never be announced as imported"
}

@test "R03 koha_exec preserves filenames with spaces and parentheses as complete argv values" {
    cat > "$W/argv.sh" <<'SH'
#!/bin/bash
printf '%s\0' "$@" > /run/kei-mock/draft-exec-argv.bin
SH
    export KEI_DRAFT_ECHO="$W/argv.sh" KEI_DRAFT_OUT="$W/out (1).xml"
    panel eval 'tools_workdir; logfile=$(tools_log argv); koha_exec "$logfile" synthetic-argv /bin/bash "$KEI_DRAFT_ECHO" --in "$KEI_DRAFT_FILE" --out "$KEI_DRAFT_OUT"'
    assert '[ "$status" -eq 0 ]' "$output"
    run python3 - "$KEI_S/draft-exec-argv.bin" "$KEI_DRAFT_FILE" "$KEI_DRAFT_OUT" <<'PY'
from pathlib import Path
import sys
actual = Path(sys.argv[1]).read_bytes().split(b'\0')[:-1]
assert actual == [b'--in', sys.argv[2].encode(), b'--out', sys.argv[3].encode()], actual
PY
    assert '[ "$status" -eq 0 ]' "$output"
}

@test "R04 authority-only manifest dispatches to staging with --authorities and without --add-items" {
    tool_double success
    engine_double authorities
    cat > "$KEI_DRAFT_FILE" <<'XML'
<collection xmlns="http://www.loc.gov/MARC21/slim"><record><leader>00000nz  a2200000n  4500</leader><controlfield tag="001">SYN-AUTH-1</controlfield><controlfield tag="008">260101n| azannaabn          |a aaa      c</controlfield><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Synthetic, Example</subfield></datafield><datafield tag="152" ind1=" " ind2=" "><subfield code="b">PERSO_NAME</subfield></datafield></record></collection>
XML
    answer yes yes
    panel eval 'tools_workdir && _lt_magic_run "$KEI_DRAFT_FILE"'
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'grep -qx stage_file.pl "$KEI_S/calls.log" && grep -qx kei_commit_authorities.pl "$KEI_S/calls.log"' "an authority stream must not silently disappear: $(calls)"
    run python3 - "$KEI_S/draft-stage-argv.bin" <<'PY'
from pathlib import Path
import sys
args = Path(sys.argv[1]).read_bytes().split(b'\0')[:-1]
assert b'--authorities' in args, args
assert b'--add-items' not in args, args
PY
    assert '[ "$status" -eq 0 ]' "$output"
    assert '[ "$(tools_sql "SELECT record_type FROM import_batches WHERE import_batch_id=1;")" = auth ]'
}

@test "R12 reviewed authority commits and undo select the batch API adapter, not the stock type guesser" {
    extra 'koha_exec() {
    local logfile="$1" label="$2"
    shift 2
    printf "%s\0" "$@" > "$KEI_S/${label}-argv.bin"
    cp -p -- "$2" "$KEI_S/${label}-helper.pl"
    return 0
}'
    panel eval 'tools_workdir; logfile=$(tools_log batch-adapter); koha_tool "$logfile" kei_commit_authorities.pl --batch-number 7; koha_tool "$logfile" commit_file.pl --revert --batch-number 8'
    assert '[ "$status" -eq 0 ]' "$output"
    run python3 - "$KEI_S" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for name, tail in [('kei_commit_authorities.pl', [b'--batch-number', b'7']),
                   ('commit_file.pl', [b'--revert', b'--batch-number', b'8'])]:
    argv = (root / (name + '-argv.bin')).read_bytes().split(b'\0')[:-1]
    assert argv[0] == b'perl' and argv[2:] == tail, argv
    helper = root / (name + '-helper.pl')
    text = helper.read_text()
    assert 'BatchCommitRecords' in text and 'BatchRevertRecords' in text
    assert 'local *C4::ImportBatch::GuessAuthTypeCode' in text
    assert helper.stat().st_mode & 0o777 == 0o600
PY
    assert '[ "$status" -eq 0 ]' "$output"
}

@test "R05 a blocking review result prevents all Koha staging and backup steps" {
    tool_double success
    engine_double biblio error
    answer yes yes
    panel eval 'tools_workdir && _lt_magic_run "$KEI_DRAFT_FILE"'
    assert '! grep -qE "^(stage_file.pl$|commit_file.pl$|backup )" "$KEI_S/calls.log" 2>/dev/null' "blocked source data must be corrected before any Koha import: $(calls)"
    assert 'dialogs | grep -qiE "review|validation|mapping"' "the operator must be told why this nonempty build was blocked"
    assert '! dialogs | grep -q "^OK "' "blocking errors must not produce a success message"
}

@test "R06 warning-only review remains visible while allowing the confirmed import" {
    tool_double success
    engine_double biblio warning
    inputs new
    answer yes yes
    panel eval 'tools_workdir && _lt_magic_run "$KEI_DRAFT_FILE"'
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'grep -qx stage_file.pl "$KEI_S/calls.log" && grep -qx commit_file.pl "$KEI_S/calls.log"' "warnings must not be silently promoted to blocking errors: $(calls)"
    assert '{ tool_logs; cat "$KEI_S/textboxes.log"; } | grep -qF "SYN-REVIEW: source field needs attention"' "the warning must remain visible or logged"
}

@test "R07 a committed record with an error item fails and logs the database-only item diagnostic" {
    tool_double commit-item-error
    answer yes
    panel eval 'tools_workdir && _lt_marc_import_run "$KEI_DRAFT_FILE" MARCXML UTF-8 new'
    assert '[ "$status" -ne 0 ]' "an item error must fail even when the biblio imported and commit exited 0: $output"
    assert 'grep -qx "backup IMPORT" "$KEI_S/calls.log" && grep -qx commit_file.pl "$KEI_S/calls.log"'
    assert '[ "$(tools_sql "SELECT status FROM import_records WHERE import_batch_id=1;")" = imported ]' "this must test an item error independently of a record error"
    assert '[ "$(tools_sql "SELECT ii.status FROM import_items ii JOIN import_records ir USING (import_record_id) WHERE ir.import_batch_id=1;")" = error ]'
    assert '[ "$(tools_sql "SELECT ii.import_error FROM import_items ii JOIN import_records ir USING (import_record_id) WHERE ir.import_batch_id=1;")" = "SYN-ITEM-952: barcode SYN-DUPLICATE already exists" ]'
    assert 'tool_logs | grep -qF "SYN-ITEM-952: barcode SYN-DUPLICATE already exists"' "item diagnostics stored only in the DB must reach the log"
    assert '! dialogs | grep -q "^OK "' "a partial bibliographic success must not hide a failed item"
}

@test "R08 target snapshot reads the live schema and registry without exposing patron identities" {
    tools_sql "UPDATE borrowers SET userid='SYN-PRIVATE-USER' WHERE cardnumber='C1';"
    panel eval 'tools_workdir; MAGIC_ENGINE="$TOOLS_WORK/kei"; MAGIC_WORK="$TOOLS_WORK/magic"; mkdir -p "$MAGIC_WORK"; kei_import_write "$MAGIC_ENGINE"; logfile=$(tools_log snapshot); magic_target_snapshot "$logfile"; rc=$?; cp "$MAGIC_WORK/capabilities.json" /run/kei-mock/snapshot.json; stat -c %a "$MAGIC_WORK/capabilities.json"; exit "$rc"'
    assert '[ "$status" -eq 0 ]' "$output"
    run python3 - "$KEI_S/snapshot.json" <<'PY'
import json
import sys
with open(sys.argv[1]) as source:
    report = json.load(source)
assert {'cardnumber','surname','branchcode','categorycode','dateofbirth'} <= set(report['patron_fields'])
assert 'borrowernumber' not in report['patron_fields']
assert report['branch']['cpl'] == 'CPL'
assert report['authoritytypes'] == [{'code':'PERSO_NAME','tag':'100'}]
assert report['authority_type_field'] == '152$b'
assert 'SYN-PRIVATE-USER' in report['userids']
PY
    assert '[ "$status" -eq 0 ]' "$output"
    assert '! tool_logs | grep -qF SYN-PRIVATE-USER' 'Snapshot contents must stay in private files'
}

@test "R09 an unreadable target registry aborts preparation before any import" {
    tools_sql 'DROP TABLE auth_types;'
    panel eval 'tools_workdir; MAGIC_ENGINE="$TOOLS_WORK/kei"; MAGIC_WORK="$TOOLS_WORK/magic"; mkdir -p "$MAGIC_WORK"; kei_import_write "$MAGIC_ENGINE"; logfile=$(tools_log snapshot); magic_target_snapshot "$logfile"'
    assert '[ "$status" -ne 0 ]' 'A failed SQL probe must not become an empty, permissive registry'
    assert 'tool_logs | grep -qF "Target snapshot failed: authority-types"'
    assert '! calls | grep -qE "stage_file.pl|commit_file.pl"'
}

@test "R10 logs from the same second have distinct paths and retain both diagnostics" {
    panel eval 'date() { printf "20261022-000000\n"; }; first=$(tools_log synthetic); printf "first diagnostic\n" >> "$first"; second=$(tools_log synthetic); printf "second diagnostic\n" >> "$second"; test "$first" != "$second" && grep -qx "first diagnostic" "$first" && grep -qx "second diagnostic" "$second"'
    assert '[ "$status" -eq 0 ]' "$output"
}

@test "R11 cancelling the mapper reruns analysis and preserves unresolved questions" {
    tool_double success
    engine_double biblio
    export KEI_DRAFT_CANCEL_REVIEW=1
    append_extra 'magic_can_map() { return 0; }
ui_fieldmap() { printf "mapper-cancelled\n" >> "$KEI_S/calls.log"; return 1; }
magic_ask() { printf "question-asked\n" >> "$KEI_S/calls.log"; touch "$MAGIC_WORK/review-answered"; return 0; }'
    answer no
    panel eval 'tools_workdir && _lt_magic_run "$KEI_DRAFT_FILE"'
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'grep -qx mapper-cancelled "$KEI_S/calls.log" && grep -qx question-asked "$KEI_S/calls.log"' 'Cancelling the mapper must not discard analysis questions'
    assert '! calls | grep -qx stage_file.pl' 'The overall preview was declined'
}
