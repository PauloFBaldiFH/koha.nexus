package Koha::SearchEngine::Search;
# Test double of Elasticsearch: a term matches a record when all its words
# are in the title, author or abstract; the records that match more terms
# come first, as MARC::Record objects (999 $c: the biblionumber).
use strict;
use warnings;
use C4::Context;
use MARC::Record;
use MARC::Field;
sub new { return bless {}, shift }
sub simple_search_compat {
    my ( $self, $query, $offset, $max ) = @_;
    my @terms = split / OR /, $query;
    my $rows = C4::Context->dbh->selectall_arrayref( 'SELECT biblionumber, title, author, abstract FROM biblio', { Slice => {} } );
    my %score;
    for my $r (@$rows) {
        my $hay = lc join ' ', map { $_ // '' } @$r{qw( title author abstract )};
        my @words = $hay =~ /(\w+)/g;
        my %has = map { $_ => 1 } @words;
        $score{ $r->{biblionumber} } += 1 for grep { my @w = lc($_) =~ /(\w+)/g; @w && !grep { !$has{$_} } @w } @terms;
    }
    my @ids = sort { $score{$b} <=> $score{$a} || $a <=> $b } grep { $score{$_} } keys %score;
    splice @ids, $max if @ids > $max;
    return ( undef, [ map { my $m = MARC::Record->new; $m->append_fields( MARC::Field->new( '999', ' ', ' ', c => $_ ) ); $m } @ids ], scalar @ids );
}
1;
