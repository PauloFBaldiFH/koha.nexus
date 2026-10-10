#!/usr/bin/env bats
# Sync & link authorities (Library tools > 17): Koha's
# link_bibs_to_authorities.pl (the test double of tests/mocks/koha-script on
# a real MariaDB) in simulation (--test) or apply mode, with the linker
# picked in the panel handed to that run through OVERRIDE_SYSPREF_LinkerModule.
# Double's catalogue: Default links the even record numbers, FirstMatch /
# LastMatch also the odd ones (fuzzily); record 7 fails with a warning.

setup() {
    load lib/common
    kei_reset_env
    kei_reset_live_catalog
    kei_tools_catalog
    tools_sql "CREATE TABLE auth_header (authid bigint(20) unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY, authtypecode varchar(10) NOT NULL DEFAULT '', marcxml longtext NOT NULL);
               INSERT INTO auth_header (authtypecode, marcxml) VALUES ('PERSO_NAME', '<record/>');
               INSERT INTO systempreferences (variable, value) VALUES ('LinkerModule', 'LastMatch');"
    unset KEI_SELECT_FILE KEI_DEFAULT_ANSWER
}

teardown() {
    kei_kill_daemons
}

pre_backups() { find /var/backups/koha_sql -maxdepth 1 -name "PRE-${1:-}*" 2>/dev/null | wc -l; }
linked_bibs() { tools_sql "SELECT COUNT(*) FROM biblio_metadata WHERE metadata LIKE '%<kei-linked/>%';"; }
tool_files()  { ls /var/log/koha-easy-install/tools/ 2>/dev/null; }

@test "A01 simulation: --test with the chosen linker, counts from the -v lines, nothing written" {
    inputs "all" "Default" "preview"
    answer no
    panel lt_authority_sync
    assert 'grep -q "^link_bibs_to_authorities.pl --test -v --link-report \[pre=0\]" "$KEI_S/calls.log"' "$(calls)"
    assert '! grep -q -- "--linker" "$KEI_S/calls.log"' "the script has no --linker option"
    assert '[ "$(cat "$KEI_S/last-linker")" = "Default 1" ]' "Default overrides the saved LastMatch for this run: $(cat "$KEI_S/last-linker")"
    assert 'dialogs | grep -q "PROMPT \[Simulation (dry run)\] Nothing was written (simulation).*Records that would be updated: 100\\\\nHeadings that would be linked: 100 (fuzzily: 0).*Records with errors: 1.*=> no"' "$(dialogs)"
    assert '! dialogs | grep -q "nothing to change"'
    assert '[ "$(linked_bibs)" = "0" ] && [ "$(pre_backups)" = "0" ]'
    assert '[ "$(tools_sql "SELECT value FROM systempreferences WHERE variable = '"'"'LinkerModule'"'"';")" = "LastMatch" ]' "the saved preference is left alone"
    # Warnings in the log, the clean report in its own file.
    log=$(ls /var/log/koha-easy-install/tools/authority-sync-*.log)
    assert 'grep -q "Error while searching for authorities for biblionumber 7" "$log"' "$(cat "$log")"
    assert '! grep -q "Error while searching" /var/log/koha-easy-install/tools/authority-sync-*-simulation.txt'
    assert 'grep -q "Number of bibs checked: *200" /var/log/koha-easy-install/tools/authority-sync-*-simulation.txt'
    assert '! grep -qE "^Bib +[0-9]" "$KEI_S/textbox.last" && grep -q "heading linking report" "$KEI_S/textbox.last"'
}

@test "A02 fuzzy: recommendation shown, simulation then apply after a PRE-AUTHORITIES backup and a background reindex" {
    inputs "all" "FirstMatch" "preview"
    answer yes
    panel lt_authority_sync
    assert 'grep -q "Recommended: run the simulation first" "$KEI_S/menus.log"' "$(cat "$KEI_S/menus.log")"
    assert 'grep -q "^link_bibs_to_authorities.pl --test -v --link-report \[pre=0\]" "$KEI_S/calls.log"' "$(calls)"
    assert 'grep -q "^link_bibs_to_authorities.pl -v --link-report \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
    assert '[ "$(cat "$KEI_S/last-linker")" = "FirstMatch 0" ]'
    assert '[ "$(pre_backups AUTHORITIES)" = "1" ] && [ "$(linked_bibs)" = "199" ]'
    assert 'dialogs | grep -q "OK ✅ Changes saved permanently.*Records updated: 199.*fuzzily: 99.*rebuilt in the background"' "$(dialogs)"
    for _ in $(seq 50); do grep -q "^koha-rebuild-zebra -v -b library" "$KEI_S/calls.log" && break; sleep 0.1; done
    assert 'grep -q "^koha-rebuild-zebra -v -b library" "$KEI_S/calls.log"' "$(calls)"
    assert 'tool_files | grep -q "authority-sync-.*-reindex.log"' "$(tool_files)"
}

@test "A03 apply directly, then a new simulation: already linked headings are not 'nothing matched'" {
    inputs "range" "1" "20" "Default" "apply"
    answer yes
    panel lt_authority_sync
    assert 'grep -q "^link_bibs_to_authorities.pl -v --link-report --bib-limit biblionumber BETWEEN 1 AND 20 \[pre=1\]" "$KEI_S/calls.log"' "$(calls)"
    assert '! grep -q -- "--test" "$KEI_S/calls.log"' "apply runs only once, without --test"
    assert '[ "$(linked_bibs)" = "10" ]'
    inputs "range" "1" "20" "Default" "preview"
    panel lt_authority_sync
    assert 'dialogs | grep -q "INFO \[Simulation (dry run)\].*Headings that match an authority: 10, all already linked: nothing to change"' "$(dialogs)"
}

@test "A04 nothing is written when the apply is declined or nothing matches" {
    inputs "all" "LastMatch" "apply"
    answer no
    panel lt_authority_sync
    assert '! grep -q "^link_bibs_to_authorities.pl" "$KEI_S/calls.log" 2>/dev/null' "$(calls)"
    tools_sql "DELETE FROM biblio WHERE MOD(biblionumber, 2) = 0;"
    inputs "all" "Default" "preview"
    panel lt_authority_sync
    assert 'dialogs | grep -q "No heading matches an authority: nothing to change"' "$(dialogs)"
    assert '[ "$(pre_backups)" = "0" ] && [ "$(linked_bibs)" = "0" ]'
}
