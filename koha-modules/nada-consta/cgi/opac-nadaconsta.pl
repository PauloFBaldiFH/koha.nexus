#!/usr/bin/perl
# Koha.Nexus - Nada Consta: emissão autenticada no OPAC.
#
# Instalar em: /usr/share/koha/opac/cgi-bin/opac/opac-nadaconsta.pl
# Permissões:  chown root:root, chmod 755
#
# Só emite a certidão se o leitor não tiver empréstimos correntes, itens
# em atraso nem saldo em aberto. Nada é gravado no banco.

use strict;
use warnings;
use utf8;
use lib '/usr/share/koha/lib';

use CGI qw(-utf8);
use C4::Auth qw(checkauth);
use C4::Context;
use Koha::Nexus::NadaConsta
    qw(read_config make_code certificate_expiry pendencies patron_row cpf_of enrolment_of qr_data_uri);
use HTML::Entities qw(encode_entities);
use POSIX qw(strftime);

binmode STDOUT, ':encoding(UTF-8)';

my $query = CGI->new;

# Exige login no OPAC (redireciona para o login se não houver sessão).
my ( undef, $cookie ) = checkauth( $query, 0, {}, 'opac' );
my $bn = C4::Context->userenv->{number};

my $h = sub { encode_entities( $_[0] // '' ) };

sub page {
    my ( $title, $body ) = @_;
    return <<"HTML";
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@{[ $h->($title) ]}</title>
<style>
  body { font-family: Georgia, "Times New Roman", serif; color: #111; background: #f4f4f1; margin: 0; padding: 16px; }
  .sheet { max-width: 720px; margin: 0 auto; background: #fff; border: 2px solid #222; padding: 28px; }
  h1 { font-size: 1.5rem; text-align: center; margin: 0 0 4px; }
  h2 { font-size: 1.1rem; text-align: center; font-weight: normal; margin: 0 0 20px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  td { padding: 6px 4px; border-bottom: 1px solid #ccc; vertical-align: top; }
  td.k { width: 36%; color: #444; }
  .code { font-family: monospace; font-size: 1.15rem; letter-spacing: 1px; }
  .qr { text-align: center; margin: 16px 0; }
  .qr img { width: 180px; height: 180px; }
  .note { font-size: 0.85rem; color: #333; margin-top: 16px; }
  .alert { border: 2px solid #8a1c1c; background: #fdf3f3; padding: 14px; }
  .actions { margin-top: 18px; text-align: center; }
  .actions a, .actions button { display: inline-block; margin: 4px; padding: 10px 16px; border: 1px solid #222;
    background: #222; color: #fff; text-decoration: none; font: inherit; cursor: pointer; }
  .actions a.alt, .actions button.alt { background: #fff; color: #222; }
  \@media print { body { background: #fff; padding: 0; } .sheet { border: 1px solid #000; }
    .actions, .no-print { display: none; } }
</style>
</head>
<body>
<div class="sheet">
$body
</div>
</body>
</html>
HTML
}

sub error_page {
    my ($msg) = @_;
    return page( 'Nada Consta', <<"B");
<h1>Nada Consta</h1>
<div class="alert"><p>$msg</p></div>
<div class="actions no-print"><a class="alt" href="/cgi-bin/koha/opac-user.pl">Voltar à minha conta</a></div>
B
}

my $html;
my $cfg = eval { read_config( $ENV{NADA_CONSTA_CONF} // '/etc/koha/nadaconsta.conf' ) };

if ( !$cfg ) {
    # Não revela detalhes internos ao leitor; o erro fica no log do Apache.
    warn "nadaconsta: configuração inválida: $@";
    $html = error_page('O serviço de certidão não está configurado. Procure a biblioteca.');
}
elsif ( !$bn ) {
    $html = error_page('Sessão inválida. Entre novamente na sua conta.');
}
else {
    my $p = pendencies($bn);

    if ( $p->{blocked} ) {
        my $owed = sprintf( '%.2f', $p->{owed} );
        $owed =~ tr/./,/;
        $html = page( 'Nada Consta - pendências', <<"B");
<h1>Nada Consta indisponível</h1>
<h2>Há pendências na sua conta</h2>
<div class="alert">
  <p>A certidão só é emitida quando não há pendências. Resumo:</p>
  <table>
    <tr><td class="k">Empréstimos correntes</td><td>$p->{issues}</td></tr>
    <tr><td class="k">Itens em atraso</td><td>$p->{overdue}</td></tr>
    <tr><td class="k">Multas / saldos em aberto</td><td>$p->{fines} lançamento(s), total R\$ $owed</td></tr>
  </table>
  <p>Devolva os itens, quite as multas e tente novamente.</p>
</div>
<div class="actions no-print">
  <a href="/cgi-bin/koha/opac-user.pl">Ver minha conta</a>
  <a class="alt" href="/cgi-bin/koha/opac-user.pl?tab=fines">Ver multas</a>
</div>
B
    }
    else {
        my $row    = patron_row($bn) or die "leitor não encontrado\n";
        my $issued = time;
        my $days   = $cfg->{VALIDITY_DAYS};
        my $expire = certificate_expiry( $issued, $days );

        my $code = make_code(
            key            => $cfg->{HMAC_KEY},
            borrowernumber => $bn,
            issued         => $issued,
            expires        => $expire,
        );

        my $base = $cfg->{VERIFY_URL}
            // ( C4::Context->preference('OPACBaseURL') // '' ) . '/cgi-bin/koha/opac-validar-certidao.pl';
        my $verify_url = sprintf '%s?c=%s&n=%d&t=%d&e=%d', $base, $code, $bn, $issued, $expire;

        my $name       = join ' ', grep { defined && length } $row->{firstname}, $row->{surname};
        my $cpf        = cpf_of( $bn, $cfg );
        my $enrolment  = enrolment_of( $bn, $cfg, $row );
        my $library    = C4::Context->preference('LibraryName') // '';
        my $qr         = qr_data_uri($verify_url);
        my $qr_html    = $qr
            ? qq{<img src="$qr" alt="QR Code para validar a certidão">}
            : '<p class="note">QR Code indisponível neste servidor. Use o link abaixo.</p>';

        my $body = <<"B";
<h1>@{[ $h->($library) ]}</h1>
<h2>CERTIDÃO NEGATIVA DE DÉBITO (NADA CONSTA)</h2>
<table>
  <tr><td class="k">Nome completo</td><td>@{[ $h->($name) ]}</td></tr>
  <tr><td class="k">Número do cartão / matrícula</td><td>@{[ $h->($enrolment) ]}</td></tr>
  <tr><td class="k">CPF</td><td>@{[ $h->($cpf || 'não cadastrado') ]}</td></tr>
  <tr><td class="k">Emitida em</td><td>@{[ strftime( '%d/%m/%Y às %H:%M', localtime $issued ) ]}</td></tr>
  <tr><td class="k">Válida até</td><td>@{[ strftime( '%d/%m/%Y às %H:%M', localtime $expire ) ]} ($days dias)</td></tr>
  <tr><td class="k">Código verificador</td><td class="code">$code</td></tr>
</table>
<p>Certificamos que, nesta data, o(a) leitor(a) acima não possui empréstimos correntes, itens em atraso
nem débitos ou multas em aberto junto a esta biblioteca.</p>
<div class="qr">$qr_html</div>
<p class="note">Para validar a autenticidade: $verify_url</p>
<div class="actions no-print">
  <button type="button" onclick="window.print()">Imprimir / salvar em PDF</button>
  <a class="alt" href="/cgi-bin/koha/opac-user.pl">Voltar à minha conta</a>
</div>
B
        $html = page( 'Nada Consta', $body );
    }
}

print $query->header( -type => 'text/html', -charset => 'UTF-8', ( $cookie ? ( -cookie => $cookie ) : () ) );
print $html;
