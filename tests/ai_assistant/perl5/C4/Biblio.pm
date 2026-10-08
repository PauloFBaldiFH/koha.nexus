package C4::Biblio;
# Test double: the MARC mapping of the default framework for a few fields,
# and ModBiblio writing the record back to the biblio tables.
use strict;
use warnings;
use C4::Context;
our %MAP = ( 'biblio.biblionumber' => [ '999', 'c' ], 'biblio.title' => [ '245', 'a' ], 'biblio.subtitle' => [ '245', 'b' ],
    'biblio.author' => [ '100', 'a' ], 'biblio.seriestitle' => [ '490', 'a' ], 'biblio.notes' => [ '500', 'a' ],
    'biblio.abstract' => [ '520', 'a' ], 'biblioitems.isbn' => [ '020', 'a' ], 'biblioitems.publishercode' => [ '260', 'b' ] );
sub GetMarcFromKohaField { my ($f) = @_; return @{ $MAP{$f} || [] } }
sub ModBiblio {
    my ( $record, $id ) = @_;
    my $sub = sub { my ( $t, $c ) = @{ $MAP{ $_[0] } }; my $f = $record->field($t); my $v = $f ? $f->subfield($c) : undef; $v =~ s/\s*[\/:;=,.]+$// if defined $v; $v };
    my $dbh = C4::Context->dbh;
    $dbh->do( 'UPDATE biblio SET title = ?, subtitle = ?, author = ?, seriestitle = ?, notes = ?, abstract = ? WHERE biblionumber = ?', undef,
        map( { $sub->("biblio.$_") } qw( title subtitle author seriestitle notes abstract ) ), $id );
    $dbh->do( 'UPDATE biblioitems SET isbn = ?, publishercode = ? WHERE biblionumber = ?', undef, $sub->('biblioitems.isbn'), $sub->('biblioitems.publishercode'), $id );
    if ( open( my $log, ">>", "$ENV{KEI_AIA_DB}.marc" ) ) { print {$log} $record->as_formatted, "\n"; close $log }
    return 1;
}
1;
