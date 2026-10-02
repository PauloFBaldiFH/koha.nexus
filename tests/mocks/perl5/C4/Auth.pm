package C4::Auth;
# Test double: records the permission asked for; "noauth" in the state
# folder answers like the login page.
use strict;
use warnings;
use Exporter 'import';
use KeiKohaState;
our @EXPORT_OK = qw( checkauth haspermission );
sub checkauth {
    my ( $query, $noauth, $flags, $type ) = @_;
    KeiKohaState::note( 'checkauth', $type, map { "$_=$flags->{$_}" } sort keys %$flags );
    if ( -e KeiKohaState::path('noauth') ) { print "Status: 403 Forbidden\r\nContent-Type: text/plain\r\n\r\nlogin required\n"; exit 0 }
    return ( 'librarian', undef, 'SESSID1' );
}
# "noconfig" in the state folder: the librarian may not change the system
# preferences.
sub haspermission {
    my ( $userid, $flags ) = @_;
    KeiKohaState::note( 'haspermission', $userid, map { "$_=$flags->{$_}" } sort keys %$flags );
    return -e KeiKohaState::path('noconfig') ? 0 : { superlibrarian => 0, parameters => 1 };
}
1;
