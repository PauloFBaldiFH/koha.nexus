#!/usr/bin/perl
# Testes puros do Nada Consta (não precisam de Koha nem de banco).
# Executar: prove -I koha-modules/nada-consta/lib koha-modules/nada-consta/t/

use strict;
use warnings;
use Test::More;
use File::Temp qw(tempfile);
use Koha::Nexus::NadaConsta qw(read_config make_code verify_code certificate_expiry);

my $key = 'x' x 48;
my $issued = 1767225600;
my $expire = certificate_expiry( $issued, 30 );

is( $expire - $issued, 30 * 86400, 'validade de 30 dias em segundos' );

my %base = ( key => $key, borrowernumber => 42, issued => $issued, expires => $expire );
my $code = make_code(%base);

like( $code, qr/^[A-Z2-7]{4}(?:-[A-Z2-7]{4}){3}$/, 'código no formato ABCD-EFGH-IJKL-MNOP' );
is( make_code(%base), $code, 'código é determinístico' );

ok( verify_code( %base, code => $code ), 'código correto é aceito' );
ok( verify_code( %base, code => lc $code ), 'aceita minúsculas e hífens' );
ok( !verify_code( %base, code => substr( $code, 0, -1 ) . ( substr( $code, -1 ) eq 'A' ? 'B' : 'A' ) ),
    'código adulterado é recusado' );
ok( !verify_code( %base, borrowernumber => 43, code => $code ), 'outro leitor é recusado' );
ok( !verify_code( %base, issued => $issued + 1, code => $code ), 'data de emissão alterada é recusada' );
ok( !verify_code( %base, expires => $expire + 86400, code => $code ), 'validade alterada é recusada' );
ok( !verify_code( %base, key => 'y' x 48, code => $code ), 'outra chave é recusada' );
ok( !verify_code( %base, code => undef ), 'sem código é recusado' );
ok( !verify_code( %base, code => '' ), 'código vazio é recusado' );

eval { make_code( %base, key => 'curta' ) };
like( $@, qr/chave HMAC inválida/, 'chave curta é recusada' );
eval { make_code( %base, borrowernumber => '4x2' ) };
like( $@, qr/borrowernumber inválido/, 'borrowernumber não numérico é recusado' );

# Leitura da configuração
my ( $fh, $file ) = tempfile( UNLINK => 1 );
print {$fh} "# comentário\n\nHMAC_KEY=$key\nVALIDITY_DAYS=45\n";
close $fh;
my $cfg = read_config($file);
is( $cfg->{VALIDITY_DAYS}, 45, 'lê VALIDITY_DAYS' );
is( $cfg->{CPF_ATTRIBUTE_CODE}, 'CPF', 'padrão do atributo de CPF' );
is( $cfg->{HMAC_KEY}, $key, 'lê HMAC_KEY' );

( $fh, my $short ) = tempfile( UNLINK => 1 );
print {$fh} "HMAC_KEY=curta\n";
close $fh;
eval { read_config($short) };
like( $@, qr/HMAC_KEY ausente ou com menos de 32/, 'recusa chave curta na configuração' );

eval { read_config('/nao/existe/nadaconsta.conf') };
like( $@, qr/Não consigo ler a configuração/, 'erro claro quando o arquivo falta' );

done_testing();
