#!/usr/bin/perl
# Koha.Nexus - Nada Consta: verificação pública da certidão (sem login).
#
# Instalar em: /usr/share/koha/opac/cgi-bin/opac/opac-validar-certidao.pl
# Permissões:  chown root:root, chmod 755
#
# Parâmetros (vindos do QR Code): c = código, n = borrowernumber,
# t = emissão (epoch), e = validade (epoch). Mostra só dados mínimos:
# o nome aparece abreviado e o CPF nunca é mostrado.

use strict;
use warnings;
use utf8;
use lib '/usr/share/koha/lib';

use CGI qw(-utf8);
use C4::Context;
use Koha::Nexus::NadaConsta qw(read_config verify_code patron_row);
use HTML::Entities qw(encode_entities);
use POSIX qw(strftime);

binmode STDOUT, ':encoding(UTF-8)';

my $query = CGI->new;
my $h     = sub { encode_entities( $_[0] // '' ) };

my ( $code, $n, $t, $e ) = map { $query->param($_) // '' } qw(c n t e);

my ( $state, $detail ) = ( 'invalid', '' );
my $cfg = eval { read_config( $ENV{NADA_CONSTA_CONF} // '/etc/koha/nadaconsta.conf' ) };

if ( !$cfg ) {
    warn "nadaconsta-validar: configuração inválida: $@";
}
elsif ( $n =~ /^\d+$/ && $t =~ /^\d+$/ && $e =~ /^\d+$/ && $code =~ /^[A-Za-z2-7-]{16,40}$/ ) {
    my $ok = verify_code(
        key            => $cfg->{HMAC_KEY},
        borrowernumber => $n,
        issued         => $t,
        expires        => $e,
        code           => $code,
    );
    if ($ok) {
        if ( time <= $e ) {
            $state = 'valid';
        }
        else {
            $state = 'expired';
        }
        my $row = patron_row($n);
        if ($row) {
            my $surname = $row->{surname} // '';
            my $initial = length $surname ? ' ' . substr( $surname, 0, 1 ) . '.' : '';
            $detail = ( $row->{firstname} // '' ) . $initial . ' ***';
        }
        else {
            $detail = 'titular não localizado no sistema atual';
        }
    }
}

my $library = eval { C4::Context->preference('LibraryName') } // '';

my ( $title, $cls, $msg ) =
    $state eq 'valid'   ? ( 'Certidão válida',   'ok',  'Esta certidão é autêntica e está dentro do prazo de validade.' )
  : $state eq 'expired' ? ( 'Certidão vencida',  'old', 'Esta certidão é autêntica, mas o prazo de validade já terminou.' )
  :                       ( 'Certidão não confere', 'bad', 'O código não corresponde a nenhuma certidão emitida por esta biblioteca.' );

my $dates = '';
if ( $state ne 'invalid' ) {
    $dates = sprintf(
        '<tr><td class="k">Emitida em</td><td>%s</td></tr><tr><td class="k">Válida até</td><td>%s</td></tr>',
        $h->( strftime( '%d/%m/%Y às %H:%M', localtime $t ) ),
        $h->( strftime( '%d/%m/%Y às %H:%M', localtime $e ) ),
    );
}
my $who = $detail ne '' ? sprintf( '<tr><td class="k">Titular</td><td>%s</td></tr>', $h->($detail) ) : '';

print $query->header( -type => 'text/html', -charset => 'UTF-8' );
print <<"HTML";
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Validação de certidão - Nada Consta</title>
<style>
  body { font-family: system-ui, Arial, sans-serif; color: #111; background: #f4f4f1; margin: 0; padding: 16px; }
  .card { max-width: 620px; margin: 24px auto; background: #fff; border: 1px solid #bbb; padding: 24px; }
  h1 { font-size: 1.3rem; margin: 0 0 4px; }
  .status { padding: 12px; margin: 14px 0; font-weight: bold; border-left: 6px solid; }
  .ok  { border-color: #2e7d32; background: #eef8ef; }
  .old { border-color: #b26a00; background: #fff7e6; }
  .bad { border-color: #8a1c1c; background: #fdf3f3; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 6px 4px; border-bottom: 1px solid #ddd; vertical-align: top; }
  td.k { width: 36%; color: #444; }
  p.small { font-size: 0.85rem; color: #444; }
</style>
</head>
<body>
<div class="card">
  <h1>@{[ $h->($library) ]}</h1>
  <p class="small">Validação pública de Nada Consta</p>
  <div class="status $cls">$title</div>
  <p>$msg</p>
  <table>$who$dates</table>
  <p class="small">Esta página não mostra dados de contato, endereço ou CPF do leitor.</p>
</div>
</body>
</html>
HTML
