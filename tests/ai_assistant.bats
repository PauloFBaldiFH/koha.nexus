#!/usr/bin/env bats
# Library tools 16: the AI assistant on the staff home page. The module
# (KohaEasy::Assistant) against the sample Koha database of
# tests/ai_assistant/koha.sql in SQLite; the page run as a CGI behind
# tests/ai_assistant/staff-mock (a staff home page, the Koha doubles of
# tests/ai_assistant/perl5 and a scripted model); the GRANTs of the
# read-only account; the IntranetUserJS block; and, where Playwright is
# installed, the widget in a real browser. Needs no Koha: perl with DBI,
# DBD::SQLite and CGI, python3 and curl.

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    PORT=$((20000 + RANDOM % 20000))
    bash "$KEI_REPO/tests/ai_assistant/make-state" "$W" "$PORT"
    URL="http://127.0.0.1:${PORT}/cgi-bin/koha/tools/ai_assistant.pl"
}

teardown() { [ -n "${MOCK_PID:-}" ] && kill "$MOCK_PID" 2>/dev/null || true; }

start_mock() {
    python3 "$KEI_REPO/tests/ai_assistant/staff-mock" "$PORT" "$W" &
    MOCK_PID=$!
    local i
    for i in $(seq 50); do curl -s -o /dev/null "http://127.0.0.1:${PORT}/" && return 0; sleep 0.1; done
    return 1
}
ask()  { curl -s -X POST --data-urlencode op=cud-ask --data-urlencode csrf_token=tok-SESS1 --data-urlencode "question=$1" "$URL"; }
post() { curl -s -X POST --data-urlencode csrf_token=tok-SESS1 "$@" "$URL"; }
fines() { perl -MDBI -e 'my $d = DBI->connect("dbi:SQLite:dbname=$ARGV[0]"); printf "%g", $d->selectrow_array("SELECT SUM(amountoutstanding) FROM accountlines WHERE borrowernumber = 101")' "$W/koha.db"; }

@test "ai assistant: the module answers, links and refuses (Perl tests)" {
    run env KEI_AIA_LIB="$W/lib" perl "$KEI_REPO/tests/ai_assistant/assistant.t"
    echo "$output"
    [ "$status" -eq 0 ]
    [[ "$output" != *"not ok"* ]]
}

@test "ai assistant: the page and the module compile" {
    run env PERL5LIB="$KEI_REPO/tests/ai_assistant/perl5:$W/lib" perl -wc "$W/ai_assistant.pl"
    [ "$status" -eq 0 ]
    grep -q "^our \$DIR = '$W/kei-ai';" "$W/ai_assistant.pl"
    grep -q 'title => _d(q{' "$W/ai_assistant.pl"
}

@test "ai assistant: fuzzy and multi-variable questions come back with verified links" {
    start_mock
    run curl -s "$URL?op=state"
    [[ "$output" == *'"csrf_token":"tok-SESS1"'* && "$output" == *'"setup":""'* ]]
    run ask "that book about the clown that was made into a movie..."
    [[ "$output" == *'"biblio:1":{"label":"It, King, Stephen","url":"/cgi-bin/koha/catalogue/detail.pl?biblionumber=1"}'* ]]
    [[ "$output" == *'[[biblio:2|A coisa, King, Stephen]]'* ]]
    run ask "who is the last patron who has 4 overdue books and 144 reais in fines?"
    [[ "$output" == *'[[patron:101|Ana Souza]]'* && "$output" == *'144.00'* ]]
    [[ "$output" == *'/cgi-bin/koha/members/moremember.pl?borrowernumber=101'* ]]
    # The model got the tools and the rules, and the librarian's question.
    grep -q 'READ-ONLY' "$W/model.log"
    grep -q 'find_patrons' "$W/model.log"
}

@test "ai assistant: nothing changes without the token or without Confirm" {
    start_mock
    run curl -s -X POST -d op=cud-ask -d csrf_token=bad -d question=hi "$URL"
    [[ "$output" == *'"error":"Invalid or expired security token'* ]]
    run ask "waive Ana's fines"
    [[ "$output" == *'"kind":"sql"'* && "$output" == *'"rows":2'* && "$output" == *'"state":"pending"'* ]]
    [ "$(fines)" = "144" ]
    run curl -s -X POST -d op=cud-confirm -d proposal=1 -d csrf_token=bad "$URL"
    [[ "$output" == *'"error":"Invalid or expired security token'* ]]
    [ "$(fines)" = "144" ]
    run post -d op=cud-confirm -d proposal=1
    [[ "$output" == *'"state":"done"'* && "$output" == *'"result":2'* ]]
    [ "$(fines)" = "0" ]
    # The rows before the change and the log of who ran it.
    grep -q '"amountoutstanding":100' "$W"/kei-ai/undo/*.json
    grep -q $'\tlibrarian\t2\tUPDATE accountlines SET amountoutstanding = 0 WHERE borrowernumber = 101 AND amountoutstanding > 0 LIMIT 2' "$W/kei-ai/changes.log"
    run post -d op=cud-confirm -d proposal=1
    [[ "$output" == *'"error":"This proposal was already decided."'* ]]
}

@test "ai assistant: a change runs only on the rows of the preview" {
    start_mock
    ask "waive Ana's fines" > /dev/null
    perl -MDBI -e 'DBI->connect("dbi:SQLite:dbname=$ARGV[0]")->do("INSERT INTO accountlines VALUES (9, 101, 3, 3, \"OVERDUE\", \"\")")' "$W/koha.db"
    run post -d op=cud-confirm -d proposal=1
    [[ "$output" == *'"error":"The data changed after the preview'* ]]
    [ "$(fines)" = "147" ]
}

@test "ai assistant: SQL changes only for a superlibrarian; Koha pages for everyone" {
    KEI_AIA_PERMS="patrons reports prefs sql" start_mock
    run ask "waive Ana's fines"
    [[ "$output" == *'not allowed to change data through the assistant'* && "$output" == *'"proposals":[]'* ]]
    ask "who is the last patron who has 4 overdue books and 144 reais in fines?" > /dev/null
    run ask "write off Ana's fines"
    [[ "$output" == *'"kind":"koha_page"'* && "$output" == *'"url":"/cgi-bin/koha/members/boraccount.pl?borrowernumber=101"'* ]]
    run post -d op=cud-confirm -d proposal=1
    [[ "$output" == *'"go":"/cgi-bin/koha/members/boraccount.pl?borrowernumber=101"'* ]]
    [ "$(fines)" = "144" ]
}

@test "ai assistant: no patron permission, no patron tool" {
    KEI_AIA_PERMS="reports" start_mock
    run ask "who is the last patron who has 4 overdue books and 144 reais in fines?"
    [[ "$output" == *'unknown tool find_patrons'* ]]
    ! grep -q '"find_patrons' <(head -n1 "$W/model.log" | grep -o '"content": "You are[^"]*')
}

@test "ai assistant: passwords and secrets are never read" {
    start_mock
    run ask "show me the password of Ana"
    [[ "$output" == *'refused: the column password is not available to the assistant'* ]]
    [[ "$output" != *'$2a$'* ]]
}

@test "ai assistant: the setup problems are told on the page" {
    rm "$W/kei-ai/readonly.cnf"
    start_mock
    run curl -s "$URL?op=state"
    [[ "$output" == *'"setup":"The read-only database account of the assistant is missing.'* ]]
    run ask "hi"
    [[ "$output" == *'"error":"The read-only database account'* ]]
}

@test "ai assistant: the read-only account gets SELECT only, without secrets" {
    printf '%s\t%s\n' biblio biblionumber biblio title borrowers borrowernumber borrowers password borrowers secret \
        borrowers surname sessions id sessions a_session api_keys secret z3950servers host z3950servers password > "$W/cols.tsv"
    run bash -c 'source "$1"; source "$2"; aia_grants localhost < "$3"' _ "$KEI_REPO/installer" "$KEI_REPO/tests/lib/overrides.sh" "$W/cols.tsv"
    echo "$output"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GRANT SELECT ON \`koha_library\`.\`biblio\` TO 'kei_ai_ro_library'@'localhost';"* ]]
    [[ "$output" == *"GRANT SELECT (\`borrowernumber\`, \`surname\`) ON \`koha_library\`.\`borrowers\` TO 'kei_ai_ro_library'@'localhost';"* ]]
    [[ "$output" == *"GRANT SELECT (\`host\`) ON \`koha_library\`.\`z3950servers\`"* ]]
    [[ "$output" != *sessions* && "$output" != *api_keys* && "$output" != *password* && "$output" != *secret* ]]
    [ "$(grep -c '^GRANT SELECT ' <<< "$output")" = "3" ]
    [[ "$output" != *"ALL"* && "$output" != *"UPDATE"* && "$output" != *"INSERT"* ]]
}

@test "ai assistant: the lists of secrets of the panel and of the module agree" {
    tables=$(bash -c 'source "$1"; source "$2"; printf "%s" "$AIA_SENSITIVE_TABLES"' _ "$KEI_REPO/installer" "$KEI_REPO/tests/lib/overrides.sh")
    run perl -I"$W/lib" -MKohaEasy::Assistant -e 'print "@KohaEasy::Assistant::SENSITIVE_TABLES"'
    [ "$output" = "$tables" ]
}

@test "ai assistant: the IntranetUserJS block goes in and out, other blocks stay" {
    printf '%s\n' 'mr_js_current() { printf "%s\n" "/* other */" "var a = 1;"; [ -f "$AIA_OLD" ] && cat "$AIA_OLD"; }' > "$W/js.sh"
    run env KEI_EXTRA="$W/js.sh" bash "$PANEL" aia_js_sql add "$W/add.sql"
    grep -qF "UPDATE systempreferences SET value = '/* other */" "$W/add.sql"
    grep -qF '/* koha-easy-installer ai-assistant begin */' "$W/add.sql"
    grep -qF 'news.replaceWith(box)' "$W/add.sql"
    grep -qF '/cgi-bin/koha/tools/ai_assistant.pl?v=' "$W/add.sql"
    env KEI_EXTRA="$W/js.sh" bash "$PANEL" aia_js_block > "$W/old.js"
    run env KEI_EXTRA="$W/js.sh" AIA_OLD="$W/old.js" bash "$PANEL" aia_js_sql remove "$W/rm.sql"
    grep -qxF "UPDATE systempreferences SET value = '/* other */" "$W/rm.sql"
    grep -qxF "var a = 1;' WHERE variable = 'IntranetUserJS';" "$W/rm.sql"
    ! grep -q 'ai-assistant' "$W/rm.sql"
    run env KEI_EXTRA="$W/js.sh" AIA_OLD="$W/old.js" bash "$PANEL" aia_js_latest
    [ "$status" -eq 0 ]
}

@test "ai assistant: in the panel menus" {
    # The action of the Textual panel (config.sh --run ai-assistant).
    grep -qE '^ +ai-assistant\) +echo function_ai_assistant ;;$' "$KEI_REPO/installer"
    grep -qF '"16" "$(t "💬  AI assistant on the staff home page")"' "$KEI_REPO/installer"
}

@test "ai assistant: the widget in a browser replaces the news block" {
    command -v node >/dev/null && NODE_PATH="$(npm root -g 2>/dev/null)" node -e 'require("playwright")' 2>/dev/null \
        && [ -r /usr/share/javascript/jquery/jquery.min.js ] || skip "Playwright or jQuery (libjs-jquery) not installed"
    start_mock
    run env NODE_PATH="$(npm root -g)" node "$KEI_REPO/tests/ai_assistant/widget-check.js" "http://127.0.0.1:${PORT}"
    echo "$output"
    [ "$status" -eq 0 ]
}

@test "ai assistant: the account is made from nothing, its login only in readonly.cnf" {
    printf '%s\t%s\n' biblio title borrowers surname borrowers password > "$W/cols.tsv"
    cat > "$W/prov.sh" <<SH
AIA_DIR="$W/prov"; AIA_CNF="$W/prov/readonly.cnf"; TOOLS_WORK="$W/work"
koha_conf_value() { case "\$1" in hostname) echo 127.0.0.1 ;; port) echo 3307 ;; esac; }
run_sql() { cat "$W/cols.tsv"; }
mysql() { cat > "$W/account.sql"; }
install() { cp "\${@: -2:1}" "\${@: -1}"; }
SH
    mkdir -p "$W/prov" "$W/work"
    run env KEI_EXTRA="$W/prov.sh" bash "$PANEL" aia_ro_provision "$W/log"
    [ "$status" -eq 0 ]
    pass=$(sed -n 's/^password=//p' "$W/prov/readonly.cnf")
    [[ "$pass" =~ ^[A-Za-z0-9]{40}$ ]]
    grep -qx 'dsn=dbi:mysql:database=koha_library;host=127.0.0.1;port=3307' "$W/prov/readonly.cnf"
    grep -qx 'user=kei_ai_ro_library' "$W/prov/readonly.cnf"
    [ "$(head -n2 "$W/account.sql")" = "DROP USER IF EXISTS 'kei_ai_ro_library'@'127.0.0.1';
CREATE USER 'kei_ai_ro_library'@'127.0.0.1' IDENTIFIED BY '$pass';" ]
    grep -qx "GRANT SELECT (\`surname\`) ON \`koha_library\`.\`borrowers\` TO 'kei_ai_ro_library'@'127.0.0.1';" "$W/account.sql"
    # The password is neither in the log nor left in the work folder.
    ! grep -q "$pass" "$W/log"
    [ -z "$(ls "$W/work")" ]
    # Kept on the next run; a database on another server is refused.
    run env KEI_EXTRA="$W/prov.sh" bash "$PANEL" aia_ro_provision "$W/log"
    grep -qx "password=$pass" "$W/prov/readonly.cnf"
    printf 'koha_conf_value() { echo db.example.org; }\n' >> "$W/prov.sh"
    run env KEI_EXTRA="$W/prov.sh" bash "$PANEL" aia_ro_provision "$W/log"
    [ "$status" -eq 3 ]
}
