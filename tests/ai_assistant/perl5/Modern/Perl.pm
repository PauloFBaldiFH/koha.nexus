package Modern::Perl;
# Test double (Koha depends on the real one): strict, warnings, say.
use strict;
use warnings;
use feature ();
sub import { strict->import; warnings->import; feature->import(':5.10'); return }
1;
