package C4::Search;
# Test double: the Zebra records are never raw here (see Koha::SearchEngine::Search).
use strict;
use warnings;
sub new_record_from_zebra { return }
1;
