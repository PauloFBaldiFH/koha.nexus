package C4::Reports::Guided;
# Test double: save_report writes the new report to saved_sql of the
# SQLite database (KEI_AIA_DB) and gives its id, as Koha's does.
use strict;
use warnings;
use C4::Context;
sub save_report {
    my ($f) = @_;
    my $dbh = C4::Context->dbh;
    $dbh->do( 'INSERT INTO saved_sql (report_name, notes, savedsql, borrowernumber, report_group, public) VALUES (?, ?, ?, ?, ?, ?)', undef,
        @$f{qw( name notes sql borrowernumber group public )} );
    return $dbh->last_insert_id( undef, undef, 'saved_sql', 'id' );
}
1;
