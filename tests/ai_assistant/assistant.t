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
my $ctx = { dbh => $dbh, refs => {}, proposals => [], can => { patrons => 1, reports => 1, prefs => 1, sql => 1, write => 1 } };

# The fuzzy question: the candidates of the model, both editions found.
my $r = KohaEasy::Assistant::t_search_catalogue( $ctx, { terms => [ 'It', 'A coisa', 'Stephen King', 'Pennywise' ] } );
is_deeply( [ sort map { $_->{biblionumber} } @{ $r->{matches} }[ 0, 1 ] ], [ 1, 2 ], 'clown: both editions of It' );
is( scalar( grep { $_->{biblionumber} == 5 } @{ $r->{matches} } ), 0, 'It does not match Smith' );
# The question with several variables.
$r = KohaEasy::Assistant::t_find_patrons( $ctx, { overdues_min => 4, overdues_max => 4, fines_min => 144, fines_max => 144, limit => 1 } );
is( $r->{patrons}[0]{firstname}, 'Ana', 'patron with 4 overdue and 144' );
is( $r->{patrons}[0]{fines}, '144.00' );
is( scalar @{ KohaEasy::Assistant::t_find_patrons( $ctx, { overdues_min => 4, overdues_max => 4 } )->{patrons} }, 2 );
ok( $ctx->{refs}{'patron:101'}{url} =~ m{moremember\.pl\?borrowernumber=101$}, 'patron url' );
my $t = KohaEasy::Assistant::call_tool($ctx,'run_select',{sql=>'SELECT password FROM borrowers'}); like($t, qr/refused/);
$t = KohaEasy::Assistant::call_tool($ctx,'search_catalogue',{terms=>["x' OR '1'='1", "\\'; DROP TABLE biblio; --"]}); like($t, qr/"matches":\[\]/);
is($dbh->selectrow_array('SELECT COUNT(*) FROM biblio'), 7, 'still 7');
$t = KohaEasy::Assistant::call_tool($ctx,'propose_change',{kind=>'sql',summary=>'Waive',sql=>'UPDATE accountlines SET amountoutstanding = 0 WHERE borrowernumber = 101'});
like($t, qr/"rows":2/); is($ctx->{proposals}[0]{run_sql}, 'UPDATE accountlines SET amountoutstanding = 0 WHERE borrowernumber = 101 LIMIT 2');
for my $bad ('DELETE FROM items','DELETE FROM items WHERE 1=1','DROP TABLE items','UPDATE borrowers SET password=1 WHERE borrowernumber=1','TRUNCATE items','DELETE FROM items WHERE itemnumber IN (SELECT 1)') {
  ok(!eval{KohaEasy::Assistant::check_write($bad);1}, "refused: $bad");
}
for my $bad ('DELETE FROM biblio','SELECT 1; DROP TABLE x','SELECT * FROM biblio -- c','SELECT * FROM sessions','SELECT SLEEP(5)','SELECT * FROM mysql.user','SELECT a INTO OUTFILE \'/x\' FROM b','SELECT * FROM biblio FOR UPDATE') {
  ok(!eval{KohaEasy::Assistant::check_select($bad);1}, "refused select: $bad");
}
ok(eval{KohaEasy::Assistant::check_select("SELECT title FROM biblio WHERE title='Drop dead'")}, 'keyword inside a string');
$t = KohaEasy::Assistant::call_tool($ctx,'propose_change',{kind=>'koha_page',summary=>'Write off',page=>'patron_account',id=>101});
like($t, qr/"proposal":2/); is($ctx->{proposals}[1]{url}, '/cgi-bin/koha/members/boraccount.pl?borrowernumber=101');
like(KohaEasy::Assistant::call_tool($ctx,'propose_change',{kind=>'koha_page',summary=>'x',page=>'patron_account',id=>999}), qr/look the patron up first/);
# the loop with a scripted model
my @script = ('{"tool":"find_patrons","args":{"overdues_min":4,"overdues_max":4,"fines_min":144,"fines_max":144,"limit":1}}',
              "Sure:\n```json\n{\"answer\":\"[[patron:101|Ana Souza]] has 4 overdue loans. See also [[biblio:999|Made up]].\"}\n```");
my $hist = [];
my $res = KohaEasy::Assistant::ask({%$ctx, refs=>{}, proposals=>[]}, sub { shift @script }, $hist, 'last patron with 4 overdue and 144?', 'pt');
like($res->{answer}, qr/^\[\[patron:101/); is_deeply($res->{steps}, ['find_patrons']); is(scalar @$hist, 2);
my $c2 = {%$ctx, refs=>{}}; KohaEasy::Assistant::t_find_patrons($c2,{name=>'Ana'});
my $refs = KohaEasy::Assistant::answer_refs($c2, $res->{answer}); is_deeply([keys %$refs], ['patron:101'], 'made-up id is not a link');
my $lim = {%$ctx, can=>{}}; like(KohaEasy::Assistant::call_tool($lim,'find_patrons',{}), qr/unknown tool/, 'no patron permission, no tool');
like(KohaEasy::Assistant::system_prompt($lim,'pt'), qr/Brazilian Portuguese/); unlike(KohaEasy::Assistant::system_prompt($lim,'pt'), qr/- find_patrons/);
my $body = KohaEasy::Assistant::request_body({provider=>'anthropic',model=>'m'}, [{role=>'system',content=>'S'},{role=>'user',content=>'a'},{role=>'user',content=>'b'}]);
is(scalar @{$body->{messages}}, 1); is($body->{system}, 'S');
is(KohaEasy::Assistant::endpoint({provider=>'gemini',url=>'https://generativelanguage.googleapis.com/v1beta/openai'}), 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions');
is(KohaEasy::Assistant::endpoint({provider=>'ollama',url=>'http://localhost:11434'}), 'http://127.0.0.1:11434/api/chat');
is(KohaEasy::Assistant::request_body({provider=>'ollama',model=>'m'}, [{role=>'system',content=>'S'},{role=>'user',content=>'a'}])->{options}{num_ctx}, 16384, 'ollama: a window that holds the tools');

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
my @seen;
$hist = [];
$res = KohaEasy::Assistant::ask( { %$ctx, refs => {}, proposals => [] }, sub { push @seen, [ @{ $_[0] } ]; shift @script }, $hist, 'Temos livros do Machado de Assis?', 'pt' );
is( $res->{answer}, '[[biblio:3|Dom Casmurro]]', 'refusal: reminded once, then the tool' );
like( $seen[1][-1]{content}, qr/DO have live read access/ );
is_deeply( $res->{steps}, ['search_catalogue'] );
@script = ( '{"answer":"I don\'t have access to your library database."}', '{"answer":"As an AI, I cannot access it."}', '{"answer":"[[biblio:7|The thorn birds]]"}' );
@seen = ();
$hist = [];
$res = KohaEasy::Assistant::ask( { %$ctx, refs => {}, proposals => [] }, sub { push @seen, [ @{ $_[0] } ]; shift @script }, $hist, 'Do we have any Australian literature?', 'en' );
is_deeply( $res->{steps}, ['search_catalogue'], 'refusing twice: the catalogue is searched for it' );
like( $seen[2][-2]{content}, qr/"terms":\["Australian","literature"\]/ );
like( $seen[2][-1]{content}, qr/thorn birds/ );
@script = ( '{"answer":"I do not have access to the database."}', '{"answer":"I do not have access to the database."}' );
$hist = [];
$res = KohaEasy::Assistant::ask( { %$ctx, refs => {}, proposals => [] }, sub { shift @script // '{"answer":"I do not have access."}' }, $hist, 'ok?', 'en' );
is( scalar @$hist, 0, 'a refusal is not kept in the history' );
@script = ('{"answer":"Olá! Como posso ajudar?"}');
$res = KohaEasy::Assistant::ask( { %$ctx, refs => {}, proposals => [] }, sub { shift @script }, $hist, 'oi', 'pt' );
is( $res->{answer}, 'Olá! Como posso ajudar?', 'a greeting is not a refusal' );
is_deeply( KohaEasy::Assistant::question_terms('Temos livros do Machado de Assis sobre o Rio de Janeiro?'), [ 'Machado de Assis', 'Rio de Janeiro' ] );

# Never readable, whatever the account allows.
for my $bad ( 'SELECT * FROM identity_providers', 'SELECT * FROM message_queue', 'SELECT secret FROM borrowers',
    'SELECT client_secret FROM api_keys', 'SELECT b.access_token FROM x b' ) {
    ok( !eval { KohaEasy::Assistant::check_select($bad); 1 }, "refused select: $bad" );
}
done_testing;
