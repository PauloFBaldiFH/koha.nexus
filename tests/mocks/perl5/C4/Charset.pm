package C4::Charset;
# Test double of Koha's MarcToUTF8Record: leader/09 "a" is UTF-8,
# anything else is read as ISO-8859-1 (enough for the tests).
use strict;
use warnings;
use Exporter 'import';
use Encode qw( decode );
use MARC::Record;
use MARC::Field;
use KeiKohaState;
our @EXPORT_OK = qw( MarcToUTF8Record );
sub MarcToUTF8Record {
    my ( $raw, $flavour ) = @_;
    KeiKohaState::note( 'MarcToUTF8Record', $flavour );
    my $r = MARC::Record->new_from_usmarc($raw);
    my $utf8 = substr( $r->leader, 9, 1 ) eq 'a';
    my $enc  = $utf8 ? 'UTF-8' : 'ISO-8859-1';
    my $out  = MARC::Record->new;
    my $leader = $r->leader; substr( $leader, 9, 1 ) = 'a'; $out->leader($leader);
    for my $f ( $r->fields ) {
        if ( $f->is_control_field ) { $out->append_fields( MARC::Field->new( $f->tag, decode( $enc, $f->data ) ) ); next }
        $out->append_fields( MARC::Field->new( $f->tag, $f->indicator(1), $f->indicator(2), map { ( $_->[0], decode( $enc, $_->[1] ) ) } $f->subfields ) );
    }
    return ( $out, $enc, [] );
}
1;
