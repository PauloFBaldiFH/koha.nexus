package C4::Auth;
# Test double of the AI assistant tests: always logged in as "librarian".
# KEI_AIA_PERMS="patrons reports prefs sql write": the permissions held
# (default: all of them; "write" is the superlibrarian flag).
use strict;
use warnings;
use Exporter 'import';
our @EXPORT_OK = qw( checkauth haspermission );
sub checkauth { return ( 'librarian', undef, 'SESS1' ) }
sub haspermission {
    my ( $user, $flags ) = @_;
    my %held = map { $_ => 1 } split ' ', $ENV{KEI_AIA_PERMS} // 'patrons reports prefs sql write';
    my %need = ( borrowers => 'patrons', reports => 'reports', parameters => 'prefs', superlibrarian => 'write' );
    my ($flag) = keys %$flags;
    my $want = $flag eq 'reports' && $flags->{reports} eq 'create_reports' ? 'sql' : $need{$flag};
    return $want && $held{$want} ? 1 : 0;
}
1;
