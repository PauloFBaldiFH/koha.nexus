package C4::Reserves;
# Test double: holds in the reserves table of the sample database.
# KEI_AIA_HOLD=<status> makes CanBookBeReserved refuse with it.
use strict;
use warnings;
use C4::Context;
sub CanBookBeReserved { return { status => $ENV{KEI_AIA_HOLD} // 'OK' } }
sub CalculatePriority {
    my ($biblio) = @_;
    return 1 + C4::Context->dbh->selectrow_array( 'SELECT COUNT(*) FROM reserves WHERE biblionumber = ? AND found IS NULL', undef, $biblio );
}
sub AddReserve {
    my ($p) = @_;
    my $dbh = C4::Context->dbh;
    $dbh->do( 'INSERT INTO reserves (borrowernumber, biblionumber, branchcode, priority, found, reservedate) VALUES (?, ?, ?, ?, NULL, ?)',
        undef, @$p{qw( borrowernumber biblionumber branchcode priority )}, '2026-10-02' );
    return $dbh->last_insert_id( undef, undef, 'reserves', 'reserve_id' );
}
1;
