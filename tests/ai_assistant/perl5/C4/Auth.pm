package C4::Auth;
# Test double of the AI assistant tests: always logged in as "librarian".
# KEI_AIA_PERMS="patrons reports prefs holds edit_patrons edit_catalogue
# writeoff": the permissions held (default: all of them).
use strict;
use warnings;
use Exporter 'import';
our @EXPORT_OK = qw( checkauth haspermission );
sub checkauth { return ( 'librarian', undef, 'SESS1' ) }
sub haspermission {
    my ( $user, $flags ) = @_;
    my %held = map { $_ => 1 } split ' ', $ENV{KEI_AIA_PERMS} // 'patrons reports prefs holds edit_patrons edit_catalogue writeoff';
    my %flag = ( borrowers => 'patrons', reports => 'reports', parameters => 'prefs' );
    my %sub  = ( place_holds => 'holds', edit_borrowers => 'edit_patrons', edit_catalogue => 'edit_catalogue', writeoff => 'writeoff' );
    my ($name) = keys %$flags;
    my $want = $sub{ $flags->{$name} } // $flag{$name};
    return $want && $held{$want} ? 1 : 0;
}
1;
