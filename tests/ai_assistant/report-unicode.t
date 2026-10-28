#!/usr/bin/perl
# Exercise real MySQL driver metadata, not SQLite's different Unicode handling.
use strict;
use warnings;
use utf8;
use lib $ENV{KEI_AIA_LIB} // die "KEI_AIA_LIB is not set\n";
use Test::More;
use File::Temp qw(tempfile);
use JSON::PP;
use KohaEasy::Assistant;
binmode STDOUT, ':utf8';
plan skip_all => 'Disposable MySQL DSN not supplied' unless $ENV{KEI_AIA_MYSQL_DSN};
my ($fh, $path) = tempfile(UNLINK => 1);
print {$fh} "dsn=$ENV{KEI_AIA_MYSQL_DSN}\nuser=root\npassword=\n";
close $fh;
my $dbh = KohaEasy::Assistant::connect_ro($path);
my $preview = KohaEasy::Assistant::test_report({dbh => $dbh},
    "SELECT 'João, ação e devolução' AS `Número do cartão`, '📚' AS `Título do livro`, 42 AS `Total`" );
is_deeply($preview->{columns}, ['Número do cartão', 'Título do livro', 'Total'], 'report column aliases stay Unicode');
is_deeply($preview->{rows}, [['João, ação e devolução', '📚', '42']], 'report values retain accents and supplementary characters');
my $decoded = JSON::PP->new->utf8->decode(JSON::PP->new->utf8->encode($preview));
is_deeply($decoded, $preview, 'preview survives the UTF-8 JSON response');
my $plain = KohaEasy::Assistant::test_report({dbh => $dbh}, 'SELECT 1 AS Count');
is_deeply($plain->{columns}, ['Count'], 'ASCII aliases remain unchanged');
my $rejected = eval { KohaEasy::Assistant::test_report({dbh => $dbh}, "SELECT 1 AS password"); 1 };
ok(!$rejected, 'sensitive-column guard remains active');
$dbh->disconnect;
done_testing;
