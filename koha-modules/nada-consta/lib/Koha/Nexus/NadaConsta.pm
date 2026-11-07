package Koha::Nexus::NadaConsta;

# Koha.Nexus - módulo "Nada Consta" (certidão negativa de débito).
#
# Este arquivo NÃO altera o núcleo do Koha. Ele fica em
# /usr/share/koha/lib/Koha/Nexus/NadaConsta.pm e é usado pelos dois CGIs.
#
# As funções puras (código verificador, leitura da configuração) não
# carregam C4::Context, por isso o módulo pode ser testado sem um Koha
# instalado. As funções que consultam o banco carregam C4::Context só
# quando são chamadas.

use strict;
use warnings;
use Exporter 'import';
use Digest::SHA qw(hmac_sha256);

our $VERSION   = '0.1.0';
our @EXPORT_OK = qw(
    read_config
    make_code
    verify_code
    certificate_expiry
    pendencies
    patron_row
    cpf_of
    enrolment_of
    qr_data_uri
);

# Alfabeto RFC 4648 (A-Z, 2-7), sem padding: 10 bytes viram 16 caracteres.
my @B32 = ( 'A' .. 'Z', '2' .. '7' );

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

# Lê /etc/koha/nadaconsta.conf (formato CHAVE=valor, linhas com # são ignoradas).
sub read_config {
    my ($path) = @_;
    open my $fh, '<', $path or die "Não consigo ler a configuração ($path).\n";
    my %c;
    while ( my $line = <$fh> ) {
        $line =~ s/\r?\n\z//;
        next if $line =~ /^\s*(?:#|$)/;
        my ( $k, $v ) = $line =~ /^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/ or next;
        $c{$k} = $v;
    }
    close $fh;

    die "HMAC_KEY ausente ou com menos de 32 caracteres.\n"
        unless defined $c{HMAC_KEY} && length $c{HMAC_KEY} >= 32;

    $c{VALIDITY_DAYS}      = 30   unless defined $c{VALIDITY_DAYS} && $c{VALIDITY_DAYS} =~ /^\d+$/;
    $c{CPF_ATTRIBUTE_CODE} = 'CPF' unless defined $c{CPF_ATTRIBUTE_CODE} && length $c{CPF_ATTRIBUTE_CODE};
    return \%c;
}

# ---------------------------------------------------------------------------
# Código verificador (sem tabelas: tudo é recalculável pela chave)
# ---------------------------------------------------------------------------

sub _base32 {
    my ($bytes) = @_;
    my $bits = unpack 'B*', $bytes;
    my $out  = '';
    for ( my $i = 0 ; $i < length $bits ; $i += 5 ) {
        my $chunk = substr $bits, $i, 5;
        $chunk .= '0' x ( 5 - length $chunk );
        $out .= $B32[ oct "0b$chunk" ];
    }
    return $out;
}

# Mensagem assinada: "NC1|borrowernumber|emitido_epoch|expira_epoch".
# Código = primeiros 80 bits do HMAC-SHA256, em base32 e com hífens: ABCD-EFGH-IJKL-MNOP
sub make_code {
    my (%a) = @_;
    die "chave HMAC inválida\n" unless defined $a{key} && length $a{key} >= 32;
    die "borrowernumber inválido\n" unless defined $a{borrowernumber} && $a{borrowernumber} =~ /^\d+$/;
    die "datas inválidas\n" unless $a{issued} =~ /^\d+$/ && $a{expires} =~ /^\d+$/;

    my $msg = join '|', 'NC1', $a{borrowernumber}, $a{issued}, $a{expires};
    my $raw = hmac_sha256( $msg, $a{key} );
    my $s   = _base32( substr $raw, 0, 10 );
    return join '-', unpack '(A4)*', $s;
}

# Verifica se o código bate com os dados. Não checa validade (ver certificate_expiry).
sub verify_code {
    my (%a) = @_;
    return 0 unless defined $a{code};
    my $expected = eval { make_code(%a) } or return 0;

    my $given = uc $a{code};
    $given =~ s/[^A-Z2-7]//g;
    ( my $exp_plain = $expected ) =~ s/-//g;
    return 0 unless length $given == length $exp_plain;

    # Comparação sem atalho (tempo constante para o mesmo tamanho).
    my $diff = 0;
    $diff |= ord( substr $given, $_, 1 ) ^ ord( substr $exp_plain, $_, 1 )
        for 0 .. length( $exp_plain ) - 1;
    return $diff == 0 ? 1 : 0;
}

sub certificate_expiry {
    my ( $issued, $days ) = @_;
    return $issued + $days * 86400;
}

# ---------------------------------------------------------------------------
# Consultas ao banco (Koha)
# ---------------------------------------------------------------------------

# Pendências do leitor. Bloqueia se houver qualquer empréstimo corrente,
# qualquer item em atraso ou qualquer accountlines.amountoutstanding > 0.
sub pendencies {
    my ($bn) = @_;
    require C4::Context;
    my $dbh = C4::Context->dbh;

    my ( $issues, $overdue ) = $dbh->selectrow_array(
        'SELECT COUNT(*), COALESCE(SUM(CASE WHEN date_due < NOW() THEN 1 ELSE 0 END), 0)
           FROM issues WHERE borrowernumber = ?',
        undef, $bn
    );
    my ( $fines, $owed ) = $dbh->selectrow_array(
        'SELECT COUNT(*), COALESCE(SUM(amountoutstanding), 0)
           FROM accountlines WHERE borrowernumber = ? AND amountoutstanding > 0',
        undef, $bn
    );

    $issues //= 0;
    $overdue //= 0;
    $fines   //= 0;
    $owed    //= 0;

    return {
        issues  => $issues,
        overdue => $overdue,
        fines   => $fines,
        owed    => $owed,
        blocked => ( $issues > 0 || $overdue > 0 || $fines > 0 ) ? 1 : 0,
    };
}

# Dados básicos do leitor (tabela borrowers).
sub patron_row {
    my ($bn) = @_;
    require C4::Context;
    return C4::Context->dbh->selectrow_hashref(
        'SELECT borrowernumber, firstname, surname, cardnumber FROM borrowers WHERE borrowernumber = ?',
        undef, $bn
    );
}

# CPF guardado como atributo do leitor (código configurável, padrão CPF).
sub cpf_of {
    my ( $bn, $cfg ) = @_;
    require C4::Context;
    my ($v) = C4::Context->dbh->selectrow_array(
        'SELECT attribute FROM borrower_attributes WHERE borrowernumber = ? AND code = ? LIMIT 1',
        undef, $bn, $cfg->{CPF_ATTRIBUTE_CODE}
    );
    return $v // '';
}

# Matrícula: atributo ENROLMENT_ATTRIBUTE_CODE se configurado, senão o número do cartão.
sub enrolment_of {
    my ( $bn, $cfg, $row ) = @_;
    if ( my $code = $cfg->{ENROLMENT_ATTRIBUTE_CODE} ) {
        require C4::Context;
        my ($v) = C4::Context->dbh->selectrow_array(
            'SELECT attribute FROM borrower_attributes WHERE borrowernumber = ? AND code = ? LIMIT 1',
            undef, $bn, $code
        );
        return $v if defined $v && length $v;
    }
    return $row->{cardnumber} // '';
}

# ---------------------------------------------------------------------------
# QR Code (opcional: precisa de Imager::QRCode; sem ele, a página mostra o link)
# ---------------------------------------------------------------------------

sub qr_data_uri {
    my ($text) = @_;
    my $png;
    my $ok = eval {
        require Imager::QRCode;
        my $qr  = Imager::QRCode->new( size => 4, margin => 2, level => 'M' );
        my $img = $qr->plot($text) or die "plot\n";
        $img->write( type => 'png', data => \$png ) or die "write\n";
        1;
    };
    return undef unless $ok && defined $png;
    require MIME::Base64;
    return 'data:image/png;base64,' . MIME::Base64::encode_base64( $png, '' );
}

1;

__END__

=head1 NAME

Koha::Nexus::NadaConsta - código verificador e pendências do módulo Nada Consta

=head1 SYNOPSIS

  use Koha::Nexus::NadaConsta qw(read_config make_code verify_code);
  my $cfg  = read_config('/etc/koha/nadaconsta.conf');
  my $code = make_code(key => $cfg->{HMAC_KEY}, borrowernumber => 42,
                       issued => 1767225600, expires => 1769817600);

=cut
