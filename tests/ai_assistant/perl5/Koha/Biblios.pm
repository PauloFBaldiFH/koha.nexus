package Koha::Biblios;
# Test double: a record of the sample database as a MARC::Record (built
# from its biblio row).
use strict;
use warnings;
use C4::Context;
use MARC::Record;
use MARC::Field;
sub find {
    my ( $class, $id ) = @_;
    my $r = C4::Context->dbh->selectrow_hashref( 'SELECT b.*, bi.isbn, bi.publishercode FROM biblio b LEFT JOIN biblioitems bi ON bi.biblionumber = b.biblionumber WHERE b.biblionumber = ?', undef, $id );
    return $r ? bless( $r, 'Koha::Biblio' ) : undef;
}
package Koha::Biblio;
sub biblionumber  { return $_[0]{biblionumber} }
sub frameworkcode { return '' }
sub metadata      { return bless { b => $_[0] }, 'Koha::Biblio::Metadata' }
package Koha::Biblio::Metadata;
sub record {
    my $b = $_[0]{b};
    my $r = MARC::Record->new;
    $r->append_fields( MARC::Field->new( '020', ' ', ' ', a => $b->{isbn} ) ) if $b->{isbn};
    $r->append_fields( MARC::Field->new( '100', '1', ' ', a => $b->{author} ) ) if $b->{author};
    $r->append_fields( MARC::Field->new( '245', '1', '0', a => $b->{title} . ( $b->{author} ? ' /' : '' ), $b->{subtitle} ? ( b => $b->{subtitle} ) : () ) );
    $r->append_fields( MARC::Field->new( '999', ' ', ' ', c => $b->{biblionumber} ) );
    return $r;
}
1;
