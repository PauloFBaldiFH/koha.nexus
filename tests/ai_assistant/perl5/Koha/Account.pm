package Koha::Account;
# Test double: pay() pays the debits of the patron, oldest first, and
# records the credit (WRITEOFF, PAYMENT...) in accountlines.
use strict;
use warnings;
use C4::Context;
sub new { my ( $class, $p ) = @_; return bless {%$p}, $class }
sub pay {
    my ( $self, $p ) = @_;
    my $dbh  = C4::Context->dbh;
    my $left = $p->{amount};
    my $debits = $dbh->selectall_arrayref( 'SELECT accountlines_id, amountoutstanding FROM accountlines WHERE borrowernumber = ? AND amountoutstanding > 0 ORDER BY accountlines_id',
        { Slice => {} }, $self->{patron_id} );
    for my $d (@$debits) {
        last if $left <= 0;
        my $pay = $left < $d->{amountoutstanding} ? $left : $d->{amountoutstanding};
        $dbh->do( 'UPDATE accountlines SET amountoutstanding = amountoutstanding - ? WHERE accountlines_id = ?', undef, $pay, $d->{accountlines_id} );
        $left -= $pay;
    }
    $dbh->do( 'INSERT INTO accountlines (borrowernumber, amount, amountoutstanding, debit_type_code, description) VALUES (?, ?, 0, NULL, ?)',
        undef, $self->{patron_id}, -$p->{amount}, $p->{type} );
    return { payment_id => $dbh->last_insert_id( undef, undef, 'accountlines', 'accountlines_id' ) };
}
1;
