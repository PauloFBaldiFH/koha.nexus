# Nada Consta (certidão negativa de débito) para o OPAC

Módulo independente do Koha.Nexus. Não altera arquivos do núcleo do Koha.

- O leitor logado emite no OPAC uma certidão em HTML imprimível (salvar como PDF pelo navegador), com QR Code e código verificador.
- A emissão é bloqueada se houver empréstimos correntes, itens em atraso ou `accountlines.amountoutstanding > 0`. A tela mostra o resumo.
- O código verificador é HMAC-SHA256 truncado (80 bits, base32, ex.: `ABCD-EFGH-IJKL-MNOP`). Não há tabelas novas: a verificação recalcula o código a partir da chave.
- A validação é pública em `opac-validar-certidao.pl`. Mostra o nome abreviado e nunca o CPF.

## Arquivos

| Repositório | Instalar em (Linux, pacote Debian/Ubuntu do Koha) | Permissões |
|---|---|---|
| `lib/Koha/Nexus/NadaConsta.pm` | `/usr/share/koha/lib/Koha/Nexus/NadaConsta.pm` | `chown root:root`, `chmod 644` |
| `cgi/opac-nadaconsta.pl` | `/usr/share/koha/opac/cgi-bin/opac/opac-nadaconsta.pl` | `chown root:root`, `chmod 755` |
| `cgi/opac-validar-certidao.pl` | `/usr/share/koha/opac/cgi-bin/opac/opac-validar-certidao.pl` | `chown root:root`, `chmod 755` |
| `conf/nadaconsta.conf.example` | `/etc/koha/nadaconsta.conf` (copiar e editar) | `chown root:www-data`, `chmod 640` |
| `js/opacuserjs-nada-consta.js` | colar em Administração > Preferências > `OpacUserJS` | - |

Se o Koha foi instalado a partir do código-fonte (sem pacote), troque `/usr/share/koha` pelo diretório da instalação. O `use lib` dos CGIs aponta para `/usr/share/koha/lib`; ajuste também.

## Passo a passo

```bash
# 1. Módulo e CGIs (a partir da raiz do repositório)
sudo install -d -m 755 /usr/share/koha/lib/Koha/Nexus
sudo install -m 644 -o root -g root koha-modules/nada-consta/lib/Koha/Nexus/NadaConsta.pm /usr/share/koha/lib/Koha/Nexus/NadaConsta.pm
sudo install -m 755 -o root -g root koha-modules/nada-consta/cgi/opac-nadaconsta.pl /usr/share/koha/opac/cgi-bin/opac/opac-nadaconsta.pl
sudo install -m 755 -o root -g root koha-modules/nada-consta/cgi/opac-validar-certidao.pl /usr/share/koha/opac/cgi-bin/opac/opac-validar-certidao.pl

# 2. Chave secreta (fora do repositório)
sudo sh -c 'sed "s|^HMAC_KEY=.*|HMAC_KEY=$(openssl rand -base64 48 | tr -d "\n")|" koha-modules/nada-consta/conf/nadaconsta.conf.example > /etc/koha/nadaconsta.conf'
sudo chown root:www-data /etc/koha/nadaconsta.conf
sudo chmod 640 /etc/koha/nadaconsta.conf
# Edite VERIFY_URL com o endereço público da biblioteca.

# 3. Dependência opcional para o QR Code (sem ela a página mostra o link)
sudo apt-get install -y libimager-qrcode-perl

# 4. Testes puros (sem Koha)
prove -I koha-modules/nada-consta/lib koha-modules/nada-consta/t/

# 5. Recarregar o Apache
sudo systemctl reload apache2
```

Depois, em **Administração > Preferências do sistema > OpacUserJS**, cole o conteúdo de `js/opacuserjs-nada-consta.js`.

### Trocar a chave

Trocar `HMAC_KEY` invalida todas as certidões já emitidas (a validação passa a acusar "não confere"). Faça isso só se a chave vazar.

### Atributo de CPF

O CPF é lido do atributo de leitor com código `CPF_ATTRIBUTE_CODE` (padrão `CPF`). Crie esse tipo de atributo em **Administração > Atributos de leitor** se ainda não existir.

## O que foi testado aqui e o que depende de um Koha vivo

Testado neste ambiente (sem Koha instalado):

- Lógica do código verificador: formato, determinismo, aceite do código correto, recusa de código adulterado, de outro leitor, de data ou validade alteradas e de outra chave (`t/nadaconsta.t`, 19 testes, passando).
- Leitura da configuração: comentários, valores padrão, chave curta, arquivo ausente.
- Sintaxe dos dois CGIs e do módulo (`perl -c`), com módulos do Koha substituídos por stubs.
- Sintaxe do JavaScript do `OpacUserJS` (`node --check`).

**Não testado, precisa de um Koha instalado:**

- Consultas SQL de `issues`, `accountlines`, `borrowers` e `borrower_attributes` (nomes de colunas conferidos pelo esquema do Koha, mas não executados).
- Login por `checkauth` e a sessão do OPAC.
- Bloqueio real com leitor com pendências e emissão com leitor regular.
- Renderização do QR Code com `Imager::QRCode` e a leitura do QR por um celular.
- O seletor do botão em `opac-user.pl`: o script procura `#usersummary`, `#opac-user-account`, `.userSummary` ou `#main`. Pode ser preciso ajustar conforme o tema do OPAC.
- Impressão para PDF pelo navegador.

## Limites conhecidos

- A validação pública não tem limite de tentativas. O código de 80 bits torna a adivinhação impraticável, mas o endpoint pode ser protegido no proxy se necessário.
- O QR Code aponta para o número interno do leitor (`n=`). Ele aparece no link de validação, não o nome nem o CPF.
- A certidão atesta a situação no momento da emissão. Não é recalculada depois.
- Nenhum registro de emissão é gravado (por exigência de não criar tabelas). Se a biblioteca quiser auditoria, isso exige uma decisão posterior.
