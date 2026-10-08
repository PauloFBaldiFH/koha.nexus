package Koha::SearchEngine::QueryBuilder;
# Test double: the operands joined with OR (KEI_AIA_ENGINE=down: an error).
use strict;
use warnings;
sub new { return bless {}, shift }
sub build_query_compat {
    my ( $self, $ops, $operands ) = @_;
    return ('the search engine is not answering') if ( $ENV{KEI_AIA_ENGINE} // '' ) eq 'down';
    return ( undef, join ' OR ', @$operands );
}
1;
