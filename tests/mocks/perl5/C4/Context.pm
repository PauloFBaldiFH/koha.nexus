package C4::Context;
# Test double: preferences and a database handle that reads the records
# of the state folder (SELECT ... FOR UPDATE is noted in calls.log).
use strict;
use warnings;
use Encode qw( decode );
use KeiKohaState;
sub preference { my ( $class, $name ) = @_; return $name eq 'marcflavour' ? 'MARC21' : undef }
sub dbh { return bless {}, 'KeiFakeDBH' }
package KeiFakeDBH;
sub selectrow_array {
    my ( $self, $sql, $attr, @bind ) = @_;
    if ( $sql =~ /^SELECT (GET_LOCK|RELEASE_LOCK)/ ) {
        KeiKohaState::note( lc($1) =~ tr/_/-/r, $bind[0] );
        return -e KeiKohaState::path('lock.busy') && $1 eq 'GET_LOCK' ? (0) : (1);
    }
    return () unless $sql =~ /FROM biblio_metadata/;
    KeiKohaState::note( 'select-metadata', $bind[0], ( $sql =~ /FOR UPDATE/ ? 'FOR-UPDATE' : '' ) );
    my $xml = KeiKohaState::slurp( KeiKohaState::path("biblio/$bind[0].xml") );
    return defined $xml ? ( Encode::decode( "UTF-8", $xml ) ) : ();
}
# Records whose 020 holds the ISBN of the LIKE pattern: [ biblionumber, title ].
# The queries of cdd_lookup.pl (marked /* kei-cdd:... */) read the items of
# $S/items.tsv: biblionumber<TAB>call number<TAB>title<TAB>author.
sub selectall_arrayref {
    my ( $self, $sql, $attr, @bind ) = @_;
    return cdd_query( $1, @bind ) if $sql =~ m{/\* kei-cdd:(\w+) \*/};
    return cutter_used(@bind) if $sql =~ m{/\* kei-cutter:used \*/};
    return cutter_near( $1, @bind ) if $sql =~ m{/\* kei-cutter:(author|subject|words|sample) \*/};
    return [] unless $sql =~ /FROM biblioitems/;
    ( my $isbn = $bind[0] ) =~ s/%//g;
    KeiKohaState::note( 'select-isbn', $isbn );
    my @rows;
    for my $f ( sort glob( KeiKohaState::path('biblio/*.xml') ) ) {
        my ($n) = $f =~ m{/(\d+)\.xml$} or next;
        my $xml = Encode::decode( 'UTF-8', KeiKohaState::slurp($f) );
        my @isbns = $xml =~ m{<datafield tag="020"[^>]*>\s*<subfield code="[az]">([^<]*)<}g;
        next unless grep { ( my $x = $_ ) =~ s/-//g; index( $x, $isbn ) >= 0 } @isbns;
        my ($title) = $xml =~ m{<datafield tag="245"[^>]*>\s*<subfield code="a">([^<]*)<};
        push @rows, [ $n, $title ];
    }
    return \@rows;
}
# The call numbers of cutter_calculator.pl (/* kei-cutter:used */): the items
# of $S/items.tsv whose call number matches the REGEXP, other records than
# the second parameter: [ call number, author, title ].
sub cutter_used {
    my ( $re, $bn ) = @_;
    KeiKohaState::note( 'cutter-used', $re, $bn );
    my @rows;
    for ( split /\n/, Encode::decode( 'UTF-8', KeiKohaState::slurp( KeiKohaState::path('items.tsv') ) // '' ) ) {
        my ( $b, $cn, $title, $author ) = split /\t/;
        push @rows, [ $cn, $author // '', $title // '' ] if $cn =~ /$re/ && $b ne $bn;
    }
    return [ sort { $a->[0] cmp $b->[0] } @rows ];
}
# The catalogue near a record for cutter_calculator.pl (/* kei-cutter:author
# | subject | words | sample */), from $S/items.tsv (a fifth column holds the
# subjects): [ call number, biblionumber ] of other records than the last
# parameter; sample gives every call number.
sub cutter_near {
    my ( $kind, @bind ) = @_;
    KeiKohaState::note( 'cutter-near', $kind, @bind );
    my $bn = pop @bind;
    my @like = map { lc s/^%|%$//gr } @bind;
    my @rows;
    for ( split /\n/, Encode::decode( 'UTF-8', KeiKohaState::slurp( KeiKohaState::path('items.tsv') ) // '' ) ) {
        my ( $b, $cn, $title, $author, $subjects ) = map { $_ // '' } split /\t/;
        if ( $kind eq 'sample' ) { push @rows, [$cn] if $cn ne ''; next }
        next if $b eq ( $bn // '' ) || $cn eq '';
        my $hay = lc( $kind eq 'author' ? $author : $kind eq 'subject' ? $subjects : $title );
        next if grep { $kind eq 'author' ? index( $hay, $_ ) != 0 : index( $hay, $_ ) < 0 } @like;
        push @rows, [ $cn, $b ];
    }
    return \@rows;
}
sub cdd_query {
    my ( $kind, @bind ) = @_;
    KeiKohaState::note( 'cdd', $kind, @bind );
    my @items;
    for ( split /\n/, Encode::decode( 'UTF-8', KeiKohaState::slurp( KeiKohaState::path('items.tsv') ) // '' ) ) {
        my ( $bn, $cn, $title, $author ) = split /\t/;
        my ($c) = ( $cn // '' ) =~ /([0-9]{3}(?:[.][0-9]+)?)/ or next;
        push @items, { bn => $bn, cn => $cn, c => $c, title => $title // '', author => $author // '' };
    }
    my %g;
    if ( $kind eq 'classes' ) {
        for (@items) { $g{ $_->{c} }{b}{ $_->{bn} } = 1; $g{ $_->{c} }{n}++ }
        return [ map { [ $_, scalar keys %{ $g{$_}{b} }, $g{$_}{n} ] } sort keys %g ];
    }
    if ( $kind eq 'titles' ) {
        ( my $p = $bind[0] ) =~ s/%$//;
        for ( grep { index( $_->{c}, $p ) == 0 } @items ) {
            my $x = $g{ $_->{bn} } //= [ $_->{bn}, $_->{title}, $_->{author}, $_->{cn} ];
            $x->[3] = $_->{cn} if $_->{cn} lt $x->[3];
        }
        my @r = sort { $a->[3] cmp $b->[3] || $a->[1] cmp $b->[1] } values %g;
        return [ grep {defined} @r[ 0 .. ( $#r < 14 ? $#r : 14 ) ] ];
    }
    if ( $kind eq 'words' ) {
        my @w = map { lc s/%//gr } @bind[ grep { $_ % 2 == 0 } 0 .. $#bind ];
        for my $i (@items) {
            next if grep { index( lc $i->{title}, $_ ) < 0 && index( lc $i->{author}, $_ ) < 0 } @w;
            $g{ $i->{c} }{ $i->{bn} } = 1;
        }
        my @r = sort { $b->[1] <=> $a->[1] || $a->[0] cmp $b->[0] } map { [ $_, scalar keys %{ $g{$_} } ] } keys %g;
        return [ @r[ 0 .. ( $#r < 7 ? $#r : 7 ) ] ];
    }
    return [];
}
1;
