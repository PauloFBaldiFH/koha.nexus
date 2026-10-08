package C4::Context;
# Test double: Koha's own database handle is the SQLite file of
# KEI_AIA_DB (the same database the read-only DSN points at). SQLite has no
# NOW(): it is added to every connection, fixed to 2026-10-02 12:00. The
# search engine is "Elasticsearch" (the doubles of Koha::SearchEngine).
use strict;
use warnings;
use DBI;
{
    no warnings 'redefine';
    my $connect = \&DBI::connect;
    *DBI::connect = sub {
        $_[4] = { %{ $_[4] || {} }, sqlite_unicode => 1 } if ( $_[1] // "" ) =~ /^dbi:SQLite:/i;
        my $dbh = $connect->(@_);
        $dbh->sqlite_create_function( 'NOW', 0, sub { '2026-10-02 12:00:00' } ) if $dbh && ( $_[1] // '' ) =~ /^dbi:SQLite:/i;
        return $dbh;
    };
}
my $DBH;
sub dbh { return $DBH ||= DBI->connect( "dbi:SQLite:dbname=$ENV{KEI_AIA_DB}", '', '', { RaiseError => 1, PrintError => 0, AutoCommit => 1, sqlite_unicode => 1 } ) }
sub userenv { return { number => 1, branch => 'CPL' } }
sub preference { my ( $class, $name ) = @_; return $name eq 'SearchEngine' ? 'Elasticsearch' : '' }
1;
