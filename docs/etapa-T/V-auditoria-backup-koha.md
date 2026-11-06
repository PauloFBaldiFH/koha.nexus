# V. Auditoria da cobertura do backup do Koha

Pedido do Paulo em 06/11/2026 15:26. O ponto de partida é o que a versão 1.5.179 (U1 a U5) faz. Fontes: o próprio `installer` (funções `write_backup_scripts`, `create_safety_backup` e `_kei_set_make`) e os caminhos que o painel usa. A coluna "Na versão real" é conferida pelo teste de CI com o Koha de verdade (seção 5). O que ainda não foi conferido ali está marcado como **a conferir**.

## 1. Dois níveis que não podem ser confundidos

* **Backup do banco**: o dump do MariaDB da instância. É o que o backup noturno (`backup_sql.sh`), o "Salvar backup" e o pacote conjunto da 1.5.176 faziam. Ele traz o catálogo, os leitores, a circulação, as preferências do sistema, os textos e as imagens que o Koha guarda no banco. Não traz arquivos do disco nem a chave de criptografia.
* **Backup suficiente para reconstruir a instalação**: o banco, mais os arquivos de dados fora do banco, mais os segredos sem os quais parte dos dados não se lê (a chave de criptografia do Koha). Mesmo assim, ainda dependem de fora: o pacote do Koha (`koha-common`), as contas externas (nuvem, Cloudflare, SMTP) e os índices de busca, que se refazem a partir do banco.

O pacote conjunto só pode se dizer "recuperável por completo" no segundo caso, e mesmo então lista as dependências externas.

## 2. Inventário

Legenda da coluna "Hoje (1.5.179)": **sim**, **não**, **só com chave** (entrava cifrado só quando havia chave, e era omitido em silêncio sem ela).

| Item | Onde fica | Usado quando | Hoje (1.5.179) | Depois do ajuste | Observação |
|---|---|---|---|---|---|
| Banco da instância | MariaDB `koha_<instância>` | sempre | sim | sim | `mysqldump --single-transaction`, conferido |
| Fotos de leitores, capas locais, notícias, HTML do OPAC, preferências | banco | quando usados | sim (no banco) | sim | |
| Senhas de SMTP, chaves de API do Koha, logins do Z39.50 cadastrados no Koha | banco | quando usados | sim (no banco, em claro dentro do dump) | sim | o dump é dado sensível: só sai do servidor cifrado (seção 4) |
| **Chave de criptografia do Koha** (`<encryption_key>` em `koha-conf.xml`) | `/etc/koha/sites/<inst>/koha-conf.xml` | Koha 22.11 em diante: segredo do segundo fator (2FA) da equipe; em versões novas também outras senhas guardadas (**a conferir** na versão real, o teste lista os usos) | só com chave | segredo cifrado; sem chave, a pessoa escolhe antes, e o pacote fica marcado "sem segredos" | sem ela, o que foi cifrado no banco não se lê em outra instalação |
| Resto de `koha-conf.xml` (senha do banco, caminhos, Zebra, memcached) | idem | sempre | só com chave | segredo cifrado | na recuperação, **nunca** substitui o do destino: só a chave volta (seção 3) |
| Arquivos enviados pela ferramenta Upload e pelo plugin de catalogação (856 $u) | `<upload_path>` (Debian: `/var/lib/koha/<inst>/uploads`) | quando usados | **não** | sim (`koha/files.tar.gz`) | o banco (`uploaded_files`) só guarda o nome e o hash; sem o arquivo, o link quebra |
| Plugins do Koha (código) | `<pluginsdir>` (Debian: `/var/lib/koha/<inst>/plugins`) | com `enable_plugins` | **não** | sim | o banco guarda dados e métodos dos plugins, não o código |
| Imagens próprias do OPAC (logo, favicon, fundo enviados como arquivo) | `/usr/share/koha/opac/htdocs/images/custom` | quando o painel usa arquivo local | **não** | sim | |
| Imagens próprias da interface da equipe | `/usr/share/koha/intranet/htdocs/intranet-tmpl/kei-custom` | idem | **não** | sim | |
| Configuração do SIP2 (`SIPconfig.xml`, com logins das máquinas) | `/etc/koha/sites/<inst>/SIPconfig.xml` | com SIP2 | **não** | segredo cifrado | na recuperação, só entra se o destino não tem o seu |
| Mensagens do painel (WhatsApp, Telegram, SMS: tokens) | `/etc/koha/sites/<inst>/kei-messaging.conf` | quando configurado | **não** | segredo cifrado | idem |
| IA de catalogação (chave da API ativa) | `/var/lib/koha/<inst>/kei-marc-replace/vision.conf` | quando configurado | **não** | segredo cifrado | idem |
| Regras de substituição MARC do painel | `/var/lib/koha/<inst>/kei-marc-replace` (sem `vision.conf`) | quando usadas | **não** | sim | |
| Logins de Z39.50 do painel | `/etc/koha-easy-install/.env` | quando usados | **não** | segredo cifrado | idem |
| Aparência salva pelo painel | `/etc/koha-easy-install/theme-settings.json` | quando usada | não | sim | o painel também a reconstrói a partir do banco restaurado |
| Perfis de importação do painel | `/etc/koha-easy-install/import-profiles` | quando usados | **não** | sim | |
| Índice Zebra | `/var/lib/koha/<inst>/biblios`, `authorities` | sempre (Zebra) | não | não | refeito do banco (`koha-rebuild-zebra -f -v`): a restauração já faz isso |
| Índice Elasticsearch | serviço Elasticsearch | com Elasticsearch | não | não | refeito do banco (`rebuild_elasticsearch.pl`) |
| Site do Apache, `koha-sites.conf`, `/etc/koha/passwd`, `log4perl` | `/etc/apache2`, `/etc/koha` | sempre | não | não | refeitos por `koha-create` e pela instalação do painel no destino |
| Agendamentos e scripts de backup do painel | `/etc/cron.d/koha_tasks`, `/root/backup_sql.sh` | sempre | não | não | refeitos pelo painel; o pacote não cria agendamento |
| Pacotes de idioma do Koha | `/usr/share/koha/.../<idioma>` | quando instalados | não | não | reinstalar pelo painel (Idiomas) |
| Conexões de nuvem (tokens do rclone) | `/root/.config/rclone/rclone.conf` | com nuvem | não | não, **dependência externa** | reconectar a conta na central de backups; nunca vai no pacote |
| Endereço gratuito (chave do servidor) | `/etc/koha-easy-install/broker.key` | com endereço gratuito | não | não, **tem caminho próprio** | o arquivo de recuperação do endereço (Gerenciador do Túnel) |
| Túnel com domínio próprio | `/etc/cloudflared` e a conta Cloudflare | com domínio próprio | não | não, **dependência externa** | refazer pelo Gerenciador do Túnel |

## 3. Recuperação dos segredos sem sobrescrever o destino

A restauração do banco já existe e não muda. Depois dela, o painel oferece "Arquivos e segredos do Koha" com um plano antes de qualquer mudança:

1. **Arquivos** (`files.tar.gz`): cada pasta volta ao lugar dela. O que já existe no destino é guardado antes num `.tar.gz` de segurança; nenhuma pasta fora da lista do pacote é tocada.
2. **Segredos** (`secrets.tar.gpg`): abertos com a frase de recuperação, numa pasta temporária 700 que é apagada no fim.
   * `koha-conf.xml`: do pacote só sai o valor de `<encryption_key>`. Ele substitui o do destino apenas quando são diferentes e depois de um Sim. Senha do banco, usuário, caminhos, Zebra e memcached do destino ficam como estão. O arquivo anterior é guardado como `koha-conf.xml.kei-before-secrets-<data>` (600).
   * `SIPconfig.xml`, `kei-messaging.conf`, `vision.conf` e `.env`: entram só quando o destino não tem o seu. Quando tem, o do pacote fica ao lado como `<arquivo>.from-backup` (600), para a pessoa comparar, e o plano diz isso.
   * Depois de trocar a chave: o Plack e o memcached do Koha são reiniciados.
3. Os valores nunca aparecem no plano, no log, no status ou na tela. O plano só diz "igual", "diferente", "ausente no destino" ou "ausente no pacote".

## 4. Proteção

* Sem a chave dos backups, o painel pergunta antes de gerar: configurar a proteção agora, ou gerar sem os segredos. Na segunda opção, a tela diz o que não vai e o efeito: os segredos de 2FA e outras senhas cifradas pelo Koha não poderão ser lidas em outra instalação. O manifesto marca `recoverability: data-only` para o Koha, e o resultado mostra "dados sem segredos", nunca "completo".
* Com a chave: `recoverability: full` e `secrets: gpg`.
* Nada de segredos do Koha em claro no pacote, nunca: sem chave eles ficam fora.
* Nuvem: um pacote conjunto só vai para a nuvem inteiro cifrado com a chave do servidor (`.tar.gpg`), porque o dump do banco também tem dados pessoais e senhas de SMTP. Sem a chave, o destino na nuvem é recusado.

## 5. Validação

* bats (instalador de verdade, Koha simulado): o que entra em cada caso, a escolha sem chave, o plano de segredos sem valores, a chave aplicada sem tocar senha do banco e caminhos, arquivos de segredo ao lado quando o destino tem os seus.
* CI com Koha de verdade (`koha-common` do repositório oficial, Debian 12) e Tainacan de verdade: um leitor com segredo de 2FA cifrado pelo Koha, um arquivo enviado, um plugin; o pacote conjunto; a instância apagada e criada de novo (outra chave e outra senha de banco); a restauração seletiva do Koha; antes de aplicar a chave o segredo não se lê, depois sim; a senha do banco do destino continua a nova; o arquivo enviado volta; o Tainacan restaurado à parte.
* Servidor do Paulo: nada destrutivo. Fica pendente a recuperação real numa máquina de teste dele, se ele quiser.

## 6. Situação (06/11/2026, noite)

* A coluna "Depois do ajuste" está implementada no U2:
  * commit 69a863e;
  * o teste real é o commit c857252.
* Um ajuste à seção 3: num servidor novo, os segredos só abrem com a chave dos backups do servidor de origem.
  * O painel oferece importar o kit de recuperação dele antes do plano.
  * Se o servidor novo já tem outra chave, a importação é recusada (o kit nunca substitui uma chave existente). Nesse caso só os arquivos voltam.
* bats S08 e S11 passam aqui.
* O job `koha-set`, com Koha e Tainacan reais, está configurado mas **ainda não rodou**:
  * este ambiente não alcança debian.koha-community.org;
  * este ambiente não tem Docker.
  
  Ele roda quando o PR do U2 abrir. Até lá, a lista de usos de `Koha::Encryption` na versão real continua **a conferir**.
* Matriz de requisitos: `W-matriz-requisitos-etapa-T.md`.
