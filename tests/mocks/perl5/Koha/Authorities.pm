package Koha::Authorities;
# Test double: find(authid)->authtypecode from the test database.
use strict;
use warnings;
use C4::AuthoritiesMarc;
sub find {
    my ( $class, $id ) = @_;
    my $type = C4::AuthoritiesMarc::sql( 'SELECT authtypecode FROM auth_header WHERE authid = ' . int($id) );
    chomp $type;
    return bless { authtypecode => $type }, 'Koha::Authority';
}
package Koha::Authority;
sub authtypecode { return $_[0]{authtypecode} }
1;
