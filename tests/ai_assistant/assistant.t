#!/usr/bin/perl
# KohaEasy::Assistant (the module of the AI assistant, made by the panel's
# aia_pm) against the sample Koha database of koha.sql in SQLite:
#   KEI_AIA_LIB=<folder with KohaEasy/Assistant.pm> perl assistant.t
use strict;
use warnings;
use utf8;
use FindBin;
use lib $ENV{KEI_AIA_LIB} // die "KEI_AIA_LIB is not set\n";
use Test::More;
use DBI;
use JSON::PP;
use KohaEasy::Assistant;
binmode STDOUT, ':utf8';

my $dbh = DBI->connect( 'dbi:SQLite:dbname=:memory:', '', '', { RaiseError => 1, sqlite_unicode => 1 } );
$dbh->sqlite_create_function( 'NOW', 0, sub { '2026-10-02 12:00:00' } );
open my $fh, '<:utf8', "$FindBin::Bin/koha.sql" or die;
my $sql = do { local $/; <$fh> };
$dbh->do($_) for grep { /\S/ } split /;\n/, $sql;
my %ALL = map { $_ => 1 } qw( patrons reports prefs holds edit_patrons edit_catalogue writeoff );
my $ctx = { dbh => $dbh, refs => {}, proposals => [], can => {%ALL} };
sub fresh { return { dbh => $dbh, refs => {}, proposals => [], can => {%ALL}, @_ } }
sub tool { my ( $c, $name, $args ) = @_; return JSON::PP->new->decode( KohaEasy::Assistant::call_tool( $c, $name, $args ) ) }

# The fuzzy question: the candidates of the model, both editions found.
my $r = KohaEasy::Assistant::t_search_catalogue( $ctx, { terms => [ 'It', 'A coisa', 'Stephen King', 'Pennywise' ] } );
is_deeply( [ sort map { $_->{biblionumber} } @{ $r->{matches} }[ 0, 1 ] ], [ 1, 2 ], 'clown: both editions of It' );
is( scalar( grep { $_->{biblionumber} == 5 } @{ $r->{matches} } ), 0, 'It does not match Smith' );
is( $r->{engine}, 'database', 'no search engine: the catalogue tables' );
# The question with several variables.
$r = KohaEasy::Assistant::t_find_patrons( $ctx, { overdues_min => 4, overdues_max => 4, fines_min => 144, fines_max => 144, limit => 1 } );
is( $r->{patrons}[0]{firstname}, 'Ana', 'patron with 4 overdue and 144' );
is( $r->{patrons}[0]{fines}, '144.00' );
is( scalar @{ KohaEasy::Assistant::t_find_patrons( $ctx, { overdues_min => 4, overdues_max => 4 } )->{patrons} }, 2 );
ok( $ctx->{refs}{'patron:101'}{url} =~ m{moremember\.pl\?borrowernumber=101$}, 'patron url' );
my $t = KohaEasy::Assistant::call_tool( $ctx, 'search_catalogue', { terms => [ "x' OR '1'='1", "\\'; DROP TABLE biblio; --" ] } );
like( $t, qr/"matches":\[\]/ );
is( $dbh->selectrow_array('SELECT COUNT(*) FROM biblio'), 7, 'still 7' );

# No SQL from the model: there is no such tool.
like( KohaEasy::Assistant::call_tool( $ctx, 'run_select', { sql => 'SELECT password FROM borrowers' } ), qr/unknown tool run_select/, 'no free SQL' );
unlike( KohaEasy::Assistant::system_prompt( $ctx, 'en' ), qr/run_select|MariaDB|"sql"/, 'the prompt offers no SQL' );

# Koha's search engine first, its order kept; the tables when it fails.
my @asked;
my $engine = fresh( search => sub { push @asked, [ @{ $_[0] } ]; return { engine => 'Elasticsearch', ids => [ 7, 3, 999 ] } } );
$r = KohaEasy::Assistant::t_search_catalogue( $engine, { terms => [ 'Machado de Assis', 'thorn' ] } );
is( $r->{engine}, 'Elasticsearch', 'the search engine answers' );
is_deeply( [ map { $_->{biblionumber} } @{ $r->{matches} } ], [ 7, 3 ], 'in its ranking, unknown ids left out' );
is_deeply( $asked[0], [ 'Machado de Assis', 'thorn' ], 'with the terms of the model' );
is_deeply( $r->{matches}[1]{subjects}, ['Literatura brasileira -- Romance'], 'with the subjects' );
$r = KohaEasy::Assistant::t_search_catalogue( fresh( search => sub { die "down\n" } ), { terms => ['Dom Casmurro'] } );
is_deeply( [ $r->{engine}, $r->{matches}[0]{biblionumber} ], [ 'database', 3 ], 'engine down: the tables' );

# Nothing found: said in so many words, for the model not to invent.
like( KohaEasy::Assistant::call_tool( $ctx, 'search_catalogue', { terms => ['quantum gravity'] } ), qr/"note":"NO MATCHES: nothing in this library matched/ );
unlike( KohaEasy::Assistant::call_tool( $ctx, 'search_catalogue', { terms => ['Coraline'] } ), qr/NO MATCHES/ );
like( KohaEasy::Assistant::system_prompt( $ctx, 'en' ), qr/NEVER list titles, authors, patrons or ids from your own knowledge/ );

# Statistics and the libraries: fixed queries.
my $s = tool( $ctx, 'library_stats', { metric => 'catalogue' } );
is_deeply( [ @$s{qw( records items items_on_loan )} ], [ 7, 10, 9 ], 'catalogue size' );
$s = tool( $ctx, 'library_stats', { metric => 'circulation' } );
is_deeply( [ @$s{qw( checkouts overdue holds_waiting )} ], [ 9, 8, 1 ], 'circulation' );
$s = tool( $ctx, 'library_stats', { metric => 'most_borrowed', since => '2026-01-01' } );
is( $s->{titles}[0]{biblionumber}, 1, 'most borrowed: It' );
is( $s->{titles}[0]{loans}, 3 );
$s = tool( $ctx, 'library_stats', { metric => 'new_records', since => '2026-09-01' } );
is_deeply( [ $s->{records}, map { $_->{biblionumber} } @{ $s->{newest} } ], [ 3, 6, 4, 2 ], 'records added since a date' );
like( KohaEasy::Assistant::call_tool( $ctx, 'library_stats', { metric => 'DROP TABLE x' } ), qr/metric must be one of/ );
like( KohaEasy::Assistant::call_tool( $ctx, 'library_stats', { metric => 'new_records', since => "1' OR 1=1" } ), qr/since must be a date/ );
like( KohaEasy::Assistant::call_tool( fresh( can => {} ), 'library_stats', { metric => 'patrons' } ), qr/not allowed to see patrons/ );
my $i = tool( $ctx, 'library_info', { library => 'Centerville' } );
is( $i->{libraries}[0]{branchcode}, 'CPL' );
is_deeply( $i->{libraries}[0]{opening_hours}[0], { day => 'Monday', open => '08:00', close => '18:00' }, 'opening hours' );
is( scalar @{ $i->{libraries}[0]{opening_hours} }, 6, 'Sunday has no hours' );
is_deeply( $i->{libraries}[0]{closed_every}, ['Sunday'], 'closed every Sunday' );
like( tool( $ctx, 'library_info', { library => 'FPL' } )->{note}, qr/No opening hours are recorded/, 'no hours: said, not guessed' );

# Action proposals: recorded, never run; ids only from tool results.
my $c = fresh();
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'write_off', patron => 101, summary => 'x' } ), qr/look the patron up first/ );
KohaEasy::Assistant::t_find_patrons( $c, { name => 'Ana' } );
my $w = tool( $c, 'propose_action', { action => 'write_off', patron => 101, summary => 'Write off the fines of Ana' } );
is_deeply( $w->{diff}, [ { field => 'outstanding fines', from => '144.00', to => '0.00' } ], 'write-off: the balance before and after' );
like( $w->{status}, qr/NOT executed/ );
is_deeply( $c->{proposals}[0]{before}, { outstanding => '144.00' }, 'the values it was shown with' );
is( $dbh->selectrow_array('SELECT SUM(amountoutstanding) FROM accountlines WHERE borrowernumber = 101'), 144, 'nothing changed' );
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'write_off', patron => 101, amount => 500, summary => 'x' } ), qr/at most the 144.00 outstanding/ );
$w = tool( $c, 'propose_action', { action => 'write_off', patron => 101, amount => '44,5', summary => 'Part' } );
is( $w->{diff}[0]{to}, '99.50', 'a part of it' );
KohaEasy::Assistant::t_search_catalogue( $c, { terms => ['Dom Casmurro'] } );
KohaEasy::Assistant::t_find_patrons( $c, { name => 'Bruno' } );
my $h = tool( $c, 'propose_action', { action => 'place_hold', patron => 102, biblio => 3, summary => 'Hold' } );
is_deeply( [ map { $_->{to} } @{ $h->{diff} } ], [ 'Bruno Lima', 'Dom Casmurro, Assis, Machado de', 'Centerville Public Library' ], 'hold: patron, record, pickup' );
is( $c->{proposals}[-1]{args}{pickup}, 'CPL', "the patron's library by default" );
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'place_hold', patron => 102, biblio => 3, pickup => 'XYZ', summary => 'x' } ), qr/no library XYZ/ );
KohaEasy::Assistant::t_find_patrons( $c, { name => 'Carla' } );
KohaEasy::Assistant::t_search_catalogue( $c, { terms => ['Coraline'] } );
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'place_hold', patron => 103, biblio => 6, summary => 'x' } ), qr/already has a hold/ );
my $e = tool( $c, 'propose_action', { action => 'update_patron', patron => 103, changes => { email => 'carla@example.org', phone => '' }, summary => 'E-mail' } );
is_deeply( $e->{diff}, [ { field => 'email', from => '', to => 'carla@example.org' } ], 'only the fields that change' );
for my $bad ( { password => 'x' }, { flags => 1 }, { userid => 'root' }, { email => 'not-an-email' }, { dateexpiry => 'tomorrow' }, {} ) {
    unlike( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'update_patron', patron => 103, changes => $bad, summary => 'x' } ),
        qr/"proposal"/, 'refused: ' . join( ',', %$bad ) );
}
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'update_patron', patron => 103, changes => { password => 'x' }, summary => 'x' } ),
    qr/password is not a field the assistant can change/ );
KohaEasy::Assistant::t_get_record( $c, { kind => 'biblio', id => 5 } );
my $u = tool( $c, 'propose_action', { action => 'update_record', biblio => 5, changes => { title => 'Drop Dead Gorgeous', author => 'Smith, Jane' }, summary => 'Title' } );
is_deeply( $u->{diff}, [ { field => 'title', from => 'Drop dead gorgeous', to => 'Drop Dead Gorgeous' } ], 'record: the title only' );
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'update_record', biblio => 5, changes => { title => 'Drop dead gorgeous' }, summary => 'x' } ), qr/nothing would change/ );
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'update_record', biblio => 5, changes => { '952$p' => 'x' }, summary => 'x' } ), qr/not a field the assistant can change/ );
my $o = tool( $c, 'propose_action', { action => 'open_page', page => 'patron_account', id => 101, summary => 'Write off' } );
is( $c->{proposals}[-1]{url}, '/cgi-bin/koha/members/boraccount.pl?borrowernumber=101', 'a Koha page' );
is( tool( $c, 'propose_action', { kind => 'koha_page', page => 'batch_items', summary => 'Batch' } )->{action}, 'open_page', 'the old name still works' );
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'open_page', page => 'patron_account', id => 999, summary => 'x' } ), qr/look the patron up first/ );
like( KohaEasy::Assistant::call_tool( $c, 'propose_action', { action => 'drop_table', summary => 'x' } ), qr/action must be one of/ );

# The librarian's permissions decide which actions exist.
my $lim = fresh( can => { patrons => 1 } );
KohaEasy::Assistant::t_find_patrons( $lim, { name => 'Ana' } );
like( KohaEasy::Assistant::call_tool( $lim, 'propose_action', { action => 'write_off', patron => 101, summary => 'x' } ), qr/permissions do not allow write_off/ );
like( KohaEasy::Assistant::system_prompt( $lim, 'en' ), qr/"action":"open_page"/, 'only open_page offered' );
like( KohaEasy::Assistant::system_prompt( $ctx, 'en' ), qr/"action":"open_page\|place_hold\|update_patron\|update_record\|write_off"/ );

# Approve reads the values again: a change since the proposal is refused.
my $p = $c->{proposals}[0];
ok( KohaEasy::Assistant::same_snapshot( KohaEasy::Assistant::snapshot( $c, $p ), $p->{before} ), 'unchanged' );
$dbh->do("INSERT INTO accountlines VALUES (99, 101, 3, 3, 'OVERDUE', '')");
ok( !KohaEasy::Assistant::same_snapshot( KohaEasy::Assistant::snapshot( $c, $p ), $p->{before} ), 'a new fine: not the proposal any more' );
$dbh->do('DELETE FROM accountlines WHERE accountlines_id = 99');
is( KohaEasy::Assistant::diff_text( $c->{proposals}[3] ), 'email:  -> carla@example.org', 'the line of the log' );

# The router: small talk without tools; library questions with them.
for my $q ( 'hello', 'Hi!', 'good morning', 'who are you?', 'What can you do?', 'thanks!', 'Olá, bom dia!', 'Quem é você?', 'obrigado',
    'hola, ¿quién eres?', 'Bonjour', 'Danke', 'ciao' ) {
    is( KohaEasy::Assistant::route($q), 'chat', "small talk: $q" );
}
for my $q ( 'Do you have Stephen King books?', 'who is the last patron with 4 overdue books?', 'what are the opening hours?',
    'hello, do you have Dom Casmurro?', 'Bom dia, temos livros do Machado de Assis?', 'how many books do we have?', '', 'It' ) {
    is( KohaEasy::Assistant::route($q), 'tools', "tools: $q" );
}
my @seen;
my $hist = [];
my $res = KohaEasy::Assistant::ask( fresh(), sub { push @seen, [ @{ $_[0] } ]; '{"answer":"Olá! Sou o assistente do koha.nexus."}' }, $hist, 'Olá, bom dia!', 'pt' );
is( $res->{route}, 'chat' );
is_deeply( $res->{steps}, [], 'no tool for a greeting' );
like( $seen[0][0]{content}, qr/This message is small talk/, 'the conversational prompt' );
unlike( $seen[0][0]{content}, qr/search_catalogue|find_patrons/, 'without the tools' );
is( scalar @$hist, 2, 'kept in the conversation' );
@seen = ();
my @script = ( '{"tool":"search_catalogue","args":{"terms":["x"]}}', '{"tool":"find_page","args":{"query":"circulation"}}', '{"answer":"[[page:circulation|Circulation]]"}' );
$res = KohaEasy::Assistant::ask( fresh(), sub { push @seen, [ @{ $_[0] } ]; shift @script }, [], 'hello', 'en' );
is( $res->{route}, 'tools', 'a tool asked for during small talk: the full way' );
like( $seen[1][0]{content}, qr/# Searching well/ );

# The loop with a scripted model; made-up ids are not links.
@script = ( '{"tool":"find_patrons","args":{"overdues_min":4,"overdues_max":4,"fines_min":144,"fines_max":144,"limit":1}}',
            "Sure:\n```json\n{\"answer\":\"[[patron:101|Ana Souza]] has 4 overdue loans. See also [[biblio:999|Made up]].\"}\n```" );
$hist = [];
my $c2 = fresh();
$res = KohaEasy::Assistant::ask( $c2, sub { shift @script }, $hist, 'last patron with 4 overdue and 144?', 'pt' );
like( $res->{answer}, qr/^\[\[patron:101/ ); is_deeply( $res->{steps}, ['find_patrons'] ); is( scalar @$hist, 2 );
is_deeply( [ keys %{ KohaEasy::Assistant::answer_refs( $c2, $res->{answer} ) } ], ['patron:101'], 'made-up id is not a link' );

# The conversation buffer: the records of a turn travel to the next one.
$hist = [];
my $c3 = fresh();
@script = ( '{"tool":"search_catalogue","args":{"terms":["Stephen King"]}}', '{"answer":"Yes: [[biblio:1|It]] and [[biblio:2|A coisa]]."}' );
KohaEasy::Assistant::ask( $c3, sub { shift @script }, $hist, 'Do you have Stephen King books?', 'en' );
my $mem = JSON::PP->new->decode( $hist->[1]{content} );
is_deeply( $mem->{context}{tools}, [ { tool => 'search_catalogue', args => { terms => ['Stephen King'] } } ], 'the call is remembered' );
like( "@{ $mem->{context}{found} }", qr/biblio:1 It, King, Stephen/, 'and the records it found' );
@seen = ();
@script = ( '{"tool":"propose_action","args":{"action":"place_hold","patron":101,"biblio":1,"summary":"x"}}', '{"answer":"ok"}' );
KohaEasy::Assistant::ask( $c3, sub { push @seen, [ @{ $_[0] } ]; shift @script }, $hist, 'Which one is his clown book?', 'en' );
like( $seen[0][1]{content}, qr/Stephen King/, 'the next question sees the earlier one' );
like( $seen[0][2]{content}, qr/"found":\[[^\]]*"biblio:1 It, King, Stephen"/, 'and its results' );
like( $seen[0][0]{content}, qr/# Conversation memory/ );
like( $seen[1][-1]{content}, qr/look the patron up first/, 'a patron never looked up cannot be used' );

like( KohaEasy::Assistant::system_prompt( fresh( can => {} ), 'pt' ), qr/Brazilian Portuguese/ ); unlike( KohaEasy::Assistant::system_prompt( fresh( can => {} ), 'pt' ), qr/- find_patrons/ );
like( KohaEasy::Assistant::call_tool( fresh( can => {} ), 'find_patrons', {} ), qr/unknown tool/, 'no patron permission, no tool' );
my $body = KohaEasy::Assistant::request_body( { provider => 'anthropic', model => 'm' }, [ { role => 'system', content => 'S' }, { role => 'user', content => 'a' }, { role => 'user', content => 'b' } ] );
is( scalar @{ $body->{messages} }, 1 ); is( $body->{system}, 'S' );
is( KohaEasy::Assistant::endpoint( { provider => 'gemini', url => 'https://generativelanguage.googleapis.com/v1beta/openai' } ), 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions' );
is( KohaEasy::Assistant::endpoint( { provider => 'ollama', url => 'http://localhost:11434' } ), 'http://127.0.0.1:11434/api/chat' );
is( KohaEasy::Assistant::request_body( { provider => 'ollama', model => 'm' }, [ { role => 'system', content => 'S' }, { role => 'user', content => 'a' } ] )->{options}{num_ctx}, 16384, 'ollama: a window that holds the tools' );

# Authors as the librarian writes them; subjects of the MARC record.
$r = KohaEasy::Assistant::t_search_catalogue( $ctx, { terms => ['Machado de Assis'] } );
is( $r->{matches}[0]{biblionumber}, 3, 'Machado de Assis finds "Assis, Machado de"' );
is_deeply( $r->{matches}[0]{subjects}, ['Literatura brasileira -- Romance'], 'with its subjects' );
$r = KohaEasy::Assistant::t_search_catalogue( $ctx, { terms => [ 'Australian literature', 'Literatura australiana' ] } );
is( $r->{matches}[0]{biblionumber}, 7, 'a subject of the MARC record' );
like( $r->{matches}[0]{found_in}, qr/MARC/ );
is_deeply( $r->{matches}[0]{subjects}, [ 'Australian literature -- 20th century', 'Australia -- Fiction' ] );
like( KohaEasy::Assistant::call_tool( $ctx, 'get_record', { kind => 'biblio', id => 7 } ), qr/Australian literature/, 'get_record: subjects' );

# "I have no access to the database": reminded, then it searches.
@script = ( '{"answer":"Desculpe, não tenho acesso ao banco de dados da biblioteca."}',
            '{"tool":"search_catalogue","args":{"terms":["Machado de Assis"]}}',
            '{"answer":"[[biblio:3|Dom Casmurro]]"}' );
@seen = ();
$hist = [];
$res = KohaEasy::Assistant::ask( fresh(), sub { push @seen, [ @{ $_[0] } ]; shift @script }, $hist, 'Temos livros do Machado de Assis?', 'pt' );
is( $res->{answer}, '[[biblio:3|Dom Casmurro]]', 'refusal: reminded once, then the tool' );
like( $seen[1][-1]{content}, qr/DO have live read access/ );
is_deeply( $res->{steps}, ['search_catalogue'] );
@script = ( '{"answer":"I don\'t have access to your library database."}', '{"answer":"As an AI, I cannot access it."}', '{"answer":"[[biblio:7|The thorn birds]]"}' );
@seen = ();
$hist = [];
$res = KohaEasy::Assistant::ask( fresh(), sub { push @seen, [ @{ $_[0] } ]; shift @script }, $hist, 'Do we have any Australian literature?', 'en' );
is_deeply( $res->{steps}, ['search_catalogue'], 'refusing twice: the catalogue is searched for it' );
like( $seen[2][-2]{content}, qr/"terms":\["Australian","literature"\]/ );
like( $seen[2][-1]{content}, qr/thorn birds/ );
@script = ( '{"answer":"I do not have access to the database."}', '{"answer":"I do not have access to the database."}' );
$hist = [];
$res = KohaEasy::Assistant::ask( fresh(), sub { shift @script // '{"answer":"I do not have access."}' }, $hist, 'ok?', 'en' );
is( scalar @$hist, 0, 'a refusal is not kept in the history' );
is_deeply( KohaEasy::Assistant::question_terms('Temos livros do Machado de Assis sobre o Rio de Janeiro?'), [ 'Machado de Assis', 'Rio de Janeiro' ] );
done_testing;
