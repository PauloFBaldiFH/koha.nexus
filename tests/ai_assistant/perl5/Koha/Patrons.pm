package Koha::Patrons;
# Test double: find / set / store on the borrowers table.
use strict;
use warnings;
use C4::Context;
sub find {
    my ( $class, $id ) = @_;
    my ($n) = C4::Context->dbh->selectrow_array( 'SELECT COUNT(*) FROM borrowers WHERE borrowernumber = ?', undef, $id );
    return $n ? bless( { id => $id, set => {} }, 'Koha::Patron' ) : undef;
}
package Koha::Patron;
sub set { my ( $self, $h ) = @_; $self->{set} = { %{ $self->{set} }, %$h }; return $self }
sub store {
    my ($self) = @_;
    my @cols = sort keys %{ $self->{set} };
    C4::Context->dbh->do( 'UPDATE borrowers SET ' . join( ', ', map {"$_ = ?"} @cols ) . ' WHERE borrowernumber = ?', undef,
        @{ $self->{set} }{@cols}, $self->{id} ) if @cols;
    return $self;
}
1;
