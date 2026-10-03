package Koha::Token;
# Test double: the CSRF token of session SESS1 is "tok-SESS1".
use strict;
use warnings;
sub new { return bless {}, shift }
sub generate_csrf { my ( $self, $a ) = @_; return 'tok-' . ( $a->{session_id} // '' ) }
sub check_csrf { my ( $self, $a ) = @_; return ( $a->{token} // '' ) eq 'tok-' . ( $a->{session_id} // '' ) ? 1 : 0 }
1;
