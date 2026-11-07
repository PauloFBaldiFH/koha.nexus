# Pagamento de multas via Pix (Koha.Nexus)

Módulo opcional e **desligado por padrão**. Não altera arquivos do núcleo do Koha
e não escreve em tabelas SQL do Koha.

> **Nota de posicionamento.** O projeto Koha.Nexus é software livre instalado por
> cada pessoa, sem planos de hospedagem ou cobrança. Este módulo foi pedido
> explicitamente para uma biblioteca que quer quitar multas online. Ele só entra
> em uso se o responsável ligar `enabled` e instalar o serviço. Fica em
> `pix-multas/` para quem quiser usar; não é ativado pela instalação padrão.

## O que tem aqui

| Caminho | Função |
|---|---|
| `opac/pix-multas.js` | OpacUserJS: bloco na aba de multas (`tab=fines`). Fluxo 1 (chave estática, copia e cola) e botão do Fluxo 2. |
| `servico/pix_webhook.py` | Serviço Python (só biblioteca padrão): cria cobrança Pix dinâmica, valida a assinatura do banco e lança o crédito pela API REST. |
| `servico/pix.env.example` | Modelo de configuração. Segredos ficam só no ambiente. |
| `servico/nexus-pix.service` | Unidade systemd. |
| `servico/apache-nexus-pix.conf` | Trecho de proxy para o VirtualHost do OPAC. |
| `tests/test_pix_webhook.py` | Testes com fakes (sem banco, sem Koha). |

## Fluxo 1: Pix estático (sem servidor)

1. Abra **Administração > Preferências do sistema > OpacUserJS** e cole o conteúdo de `opac/pix-multas.js`.
2. Edite o bloco `CONFIG` no topo: `enabled: true`, `pixKey`, `recipientName`, `instructions`.
   Para o Fluxo 1 sozinho, troque `dynamicEndpoint` por `""`.
3. Salve. Na aba **Multas** do leitor logado aparece o bloco com a chave e o botão Copiar.

O Fluxo 1 não confirma o pagamento. A baixa continua manual no balcão.

## Fluxo 2: Pix dinâmico com baixa automática

### Como funciona

1. O leitor logado clica em "Gerar Pix com valor atual". O navegador faz `POST /nexus-pix/charges` no mesmo site, com o cookie `CGISESSID` do OPAC.
2. O serviço **não confia no navegador**. Lê o cookie, pede a página `opac-account.pl` ao Koha com esse cookie, extrai o número do cartão (regex `KOHA_CARDNUMBER_RE`) e resolve o paciente por `GET /api/v1/patrons?q={"cardnumber":...}`. Sem correspondência, recusa (fail closed).
3. Soma as multas com `GET /api/v1/patrons/{id}/account` e cria a cobrança no PSP (`PIX_PROVIDER_URL`). Devolve o copia e cola e o QR.
4. Quando o banco paga, envia `POST /nexus-pix/webhook` com `X-Signature: sha256=<HMAC-SHA256 do corpo com PIX_WEBHOOK_SECRET>`.
5. O serviço confere assinatura, txid conhecido, valor igual ao cobrado e estado ainda não creditado. Depois chama **somente** `POST /api/v1/patrons/{id}/account/credits`. Se o crédito falhar, responde 500 e o banco reenvia.

Segurança: assinatura comparada em tempo constante; txid e cookie validados por regex; o cookie é filtrado para só `CGISESSID`; corpo limitado a 64 KB; logs sem cookie nem corpo; idempotência por estado (`pending` → `crediting` → `credited`); sem CORS.

### Instalação (Debian/Ubuntu com Koha)

Use caminhos absolutos. Execute como root (`sudo -i`).

```sh
# 1. Usuário de serviço sem login
useradd --system --home /var/lib/nexus-pix --shell /usr/sbin/nologin nexus-pix

# 2. Código (lido pelo serviço, não editável por ele)
install -d -o root -g root -m 0755 /opt/nexus-pix
install -o root -g root -m 0644 /caminho/koha.nexus/pix-multas/servico/pix_webhook.py /opt/nexus-pix/pix_webhook.py

# 3. Configuração com segredos (somente leitura para o grupo do serviço)
install -d -o root -g nexus-pix -m 0750 /etc/nexus-pix
install -o root -g nexus-pix -m 0640 /caminho/koha.nexus/pix-multas/servico/pix.env.example /etc/nexus-pix/pix.env
nano /etc/nexus-pix/pix.env        # preencha os valores reais

# 4. Estado: banco SQLite de cobranças pendentes (fora do Koha)
install -d -o nexus-pix -g nexus-pix -m 0750 /var/lib/nexus-pix

# 5. Conferir configuração (sai com "config ok" ou com o erro)
sudo -u nexus-pix sh -c 'set -a; . /etc/nexus-pix/pix.env; set +a; python3 -I /opt/nexus-pix/pix_webhook.py --check'

# 6. Serviço
install -o root -g root -m 0644 /caminho/koha.nexus/pix-multas/servico/nexus-pix.service /etc/systemd/system/nexus-pix.service
systemctl daemon-reload
systemctl enable --now nexus-pix
systemctl status nexus-pix --no-pager
```

Proxy do OPAC (`/etc/apache2/sites-enabled/` no VirtualHost HTTPS do OPAC, ou no arquivo do site):

```sh
a2enmod proxy proxy_http headers
# cole o trecho de servico/apache-nexus-pix.conf dentro do <VirtualHost *:443> do OPAC
apache2ctl configtest && systemctl reload apache2
```

Para o banco entregar o webhook, a URL pública `https://<seu-opac>/nexus-pix/webhook` precisa estar acessível da internet. Um túnel ou o próprio Apache já servem.

Usuário da API no Koha: crie um patron de serviço com permissão mínima para ler pacientes e lançar créditos, e informe a senha em `KOHA_API_PASSWORD`. Não use credenciais de bibliotecário.

Bloco JavaScript: cole `opac/pix-multas.js` em OpacUserJS, como no Fluxo 1, com `dynamicEndpoint: "/nexus-pix/charges"`.

### Permissões resumidas

| Caminho | Dono | Modo |
|---|---|---|
| `/opt/nexus-pix/pix_webhook.py` | root:root | 0644 |
| `/etc/nexus-pix/` | root:nexus-pix | 0750 |
| `/etc/nexus-pix/pix.env` | root:nexus-pix | 0640 |
| `/var/lib/nexus-pix/` | nexus-pix:nexus-pix | 0750 |
| `/etc/systemd/system/nexus-pix.service` | root:root | 0644 |

## Adaptar ao seu PSP

`PixProvider.create_charge()` assume um contrato genérico: `POST` com `txid`, `valor`, `descricao`, `expiracao` e resposta com `pix_copia_cola` e, opcionalmente, `qr_base64`. Ajuste os nomes de campos e a autenticação ao seu PSP. O webhook espera JSON com `txid`, `status` (valor `paid`) e `valor`, assinado por HMAC. Se o banco usar outro esquema de assinatura (por exemplo, certificado mTLS), mude `verify_signature`.

## O que não dá para testar sem sandbox

- Os testes de `tests/` usam fakes. Não há prova de contrato com um PSP real, nem de assinatura, nem de formato de payload do banco.
- O endpoint REST de créditos e a forma de `outstanding_debits.total_outstanding` na resposta de `/account` foram escritos a partir da documentação do Koha. Confirme na sua versão com `curl` em um Koha de teste.
- A regex `KOHA_CARDNUMBER_RE` depende do HTML do seu OPAC. Se não casar, o serviço recusa tudo (fail closed).
- Não testado ao vivo: a leitura do cookie do OPAC e o proxy do Apache.
- Estado `crediting` pode ficar preso se o serviço cair entre o crédito e a marcação. Nesse caso, confira no Koha se o lançamento com "Pix txid ..." existe antes de tocar no banco.

## Testes

```sh
cd /caminho/koha.nexus/pix-multas
python3 -m pip install pytest
python3 -m pytest -q tests
node -e "require('vm').createScript(require('fs').readFileSync('opac/pix-multas.js','utf8'))" && echo JS ok
```
