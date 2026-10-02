package C4::Biblio;
# Test double: ModBiblio writes the record to the state folder (fails with
# "modbiblio.fail"); the framework comes from "biblio/<n>.fw". AddBiblio
# writes a new biblio/<n>.xml after the highest number (fails with
# "addbiblio.fail").
use strict;
use warnings;
use Exporter 'import';
use Encode qw( encode );
use KeiKohaState;
our @EXPORT_OK = qw( AddBiblio ModBiblio GetFrameworkCode GetMarcFromKohaField );
sub GetMarcFromKohaField { return $_[0] eq 'items.itemnumber' ? ( '952', '9' ) : () }
sub GetFrameworkCode { my $fw = KeiKohaState::slurp( KeiKohaState::path("biblio/$_[0].fw") ) // ''; chomp $fw; return $fw }
sub ModBiblio {
    my ( $record, $biblionumber, $frameworkcode ) = @_;
    KeiKohaState::note( 'ModBiblio', $biblionumber, "fw=$frameworkcode", 'tags=' . join( ',', map { $_->tag } $record->fields ) );
    return 0 if -e KeiKohaState::path('modbiblio.fail');
    open( my $fh, '>:raw', KeiKohaState::path("biblio/$biblionumber.xml") ) or die $!;
    print {$fh} encode( 'UTF-8', $record->as_xml_record('MARC21') );
    close $fh;
    return 1;
}
sub AddBiblio {
    my ( $record, $frameworkcode ) = @_;
    my ($n) = sort { $b <=> $a } map { m{/(\d+)\.xml$} ? $1 : () } glob( KeiKohaState::path('biblio/*.xml') );
    $n = ( $n // 0 ) + 1;
    KeiKohaState::note( 'AddBiblio', $n, "fw=$frameworkcode", 'tags=' . join( ',', map { $_->tag } $record->fields ) );
    return if -e KeiKohaState::path('addbiblio.fail');
    open( my $fh, '>:raw', KeiKohaState::path("biblio/$n.xml") ) or die $!;
    print {$fh} encode( 'UTF-8', $record->as_xml_record('MARC21') );
    close $fh;
    open( $fh, '>', KeiKohaState::path("biblio/$n.fw") ) or die $!;
    print {$fh} $frameworkcode;
    close $fh;
    return ( $n, $n );
}
1;
