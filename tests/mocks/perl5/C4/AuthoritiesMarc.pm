package C4::AuthoritiesMarc;
# Test double: the authorities of the test database (auth_header.marcxml),
# read and written with the mysql client. merge points the $9 of the
# records (biblio_metadata) from one authority to the other; DelAuthority
# deletes the row. Every call goes to /run/kei-mock/calls.log, with the
# number of PRE-* backups present ("[pre=N]"); /run/kei-mock/fail/merge-<authid>
# makes the merge of that authority fail.
use strict;
use warnings;
use Exporter 'import';
use Encode qw( decode encode );
use MARC::Record;
use MARC::File::XML ( BinaryEncoding => 'utf8', RecordFormat => 'MARC21' );
our @EXPORT_OK = qw( GetAuthority ModAuthority merge DelAuthority );

sub sql {
    open( my $p, '-|', 'mysql', '--default-character-set=utf8mb4', '-Nrse', $_[0], 'koha_library' ) or die "mysql: $!";
    local $/;
    my $out = <$p>;
    close $p;
    return decode( 'UTF-8', $out // '' );
}
sub note {
    my $pre = () = glob('/var/backups/koha_sql/PRE-*');
    open( my $fh, '>>', '/run/kei-mock/calls.log' ) or return;
    print {$fh} join( ' ', @_ ), " [pre=$pre]\n";
}
sub GetAuthority {
    my $xml = sql( 'SELECT marcxml FROM auth_header WHERE authid = ' . int( $_[0] ) );
    return unless $xml =~ /\S/;
    return MARC::Record->new_from_xml( encode( 'UTF-8', $xml ), 'UTF-8', 'MARC21' );
}
sub ModAuthority {
    my ( $authid, $record, $type ) = @_;
    note( 'ModAuthority', $authid, $type, 'tags=' . join( ',', map { $_->tag } $record->fields ) );
    my $hex = unpack( 'H*', encode( 'UTF-8', $record->as_xml_record('MARC21') ) );
    sql( "UPDATE auth_header SET marcxml = CONVERT(UNHEX('$hex') USING utf8mb4) WHERE authid = " . int($authid) );
    return $authid;
}
sub merge {
    my ($p) = @_;
    my ( $from, $to ) = ( int $p->{mergefrom}, int $p->{mergeto} );
    note( 'merge', $from, $to, ( $p->{override_limit} ? 'override_limit' : '' ) );
    die "simulated failure\n" if -e "/run/kei-mock/fail/merge-$from";
    sql(  "UPDATE biblio_metadata SET metadata = REPLACE(metadata, '<subfield code=\"9\">$from</subfield>', "
        . "'<subfield code=\"9\">$to</subfield>')" );
    return 1;
}
sub DelAuthority {
    my ($p) = @_;
    note( 'DelAuthority', int $p->{authid}, ( $p->{skip_merge} ? 'skip_merge' : '' ) );
    sql( 'DELETE FROM auth_header WHERE authid = ' . int( $p->{authid} ) );
    return;
}
1;
