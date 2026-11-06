# T. Central de backups, agendamentos, endereço, acesso administrativo e pós-instalação

Especificação da etapa pedida por Paulo em 06/11/2026 (08:58). Base: `main` em `5c0053d` (1.5.174), documentos A a S desta pasta e o código atual. O Tainacan de Paulo está funcionando (ele entrou na administração), então nada aqui trata a instalação dele como inoperante.

## 1. Inventário do que já existe

### Backups do Koha (legado, continua valendo)

| Peça | Onde | O que faz |
|---|---|---|
| Backup noturno SQL | `/root/backup_sql.sh` (gerado por `write_backup_scripts`), linha em `/etc/cron.d/koha_tasks` | `mysqldump` consistente, compressão gz, zst ou xz (`BACKUP_COMPRESSION`), retenção local `KEEP_DAYS=7` em `/var/backups/koha_sql`, envio à nuvem quando não há planos |
| Exportação MARC21 | `/root/backup_marc.sh`, semanal, recuperada pelo noturno (`--if-due`) | `.mrc` em `DIR_MARC` |
| Backup manual | `--task backup-manual DIR` → `function_manual_backup` → `create_safety_backup` | mesmo dump consistente, testado (gzip e linha final do mysqldump), trava `backup_lock` |
| Teste de integridade | `--task backup-test` | descompacta e confere o último |
| Restauração | `--task restore-check FILE`, `--task restore FILE` | pré-checagem (SQL no início, linha final, espaço), cópia de segurança `pre_restore_safety_backup_*`, teste em banco temporário, troca, reindexação |
| Nuvem (planos) | `cloud_plans.conf` (`ID|CONEXÃO|PASTA|DIAS`), `/root/cloud_plan.sh ID sql|marc|sql+marc`, linhas `cloud:ID` no `koha_tasks` | cada plano tem conexão, pasta, retenção na nuvem e horário próprios |
| Conexões rclone | `--task cloud-*`, telas `screens/cloud_backup.py` e `screens/cloud_remote.py`, `/root/.config/rclone/rclone.conf` | cadastro de qualquer serviço do rclone; Google Drive por autorização no navegador (`cloud-authorize`) ou token colado (`cloud-token`) |
| Painel | seção `backup` (grupo Koha, tecla `b`, `views/backup.py`) | cartões: baixar último, manual, MARC21, restaurar, nuvem, testar; compressão |

### Backups das plataformas em contêiner (motor do PR #333)

| Peça | Onde | O que faz |
|---|---|---|
| Motor | `kei_backup_*`, `--task platform-backup-*` | pacote formato 2 (`journal.jsonl`, `db.sql.gz`, `files.tar.gz` ou `files.ref.json` do restic, `secrets.tar.gpg` ou `secrets/`, `manifest.json`, `SHA256SUMS`), retomada, janela sem escrita registrada (`window_seconds`) |
| Adaptador Tainacan | `_kei_bk_tainacan_*` | para o contêiner `wordpress`, `mysqldump` do MariaDB, tar do volume, segredos `.env`, `compose.yml`, estado |
| Chave e kit | `kei_backup_setup`, `kei_backup_kit` | GnuPG; a frase nunca é guardada; o kit tem a chave privada protegida e as senhas do restic |
| Repositório e cópia | `repo_<p>` (restic), `copy_<p>` (rclone) | cópia recusada sem chave (segredos em claro não saem do servidor) |
| Agenda | `/etc/cron.d/koha-nexus-platform-backups` | backup diário, manutenção aos domingos, teste de restauração no dia 1 |
| Tainacan | `--task tainacan-backup|backups|restore-test|restore` | backup manual, lista, teste isolado (`kn-tainacan-rt`), restauração com cópia de segurança |
| Painel | seção `tainacan-backups` (grupo Tainacan) e `infra` | sete cartões próprios do Tainacan; chave e kit em Infraestrutura |

### Agendamentos

* `/etc/cron.d/koha_tasks`: editor visual `views/crons.py` + `cron.py` (predefinições do Koha, linhas da nuvem, linhas manuais preservadas, `#off#`), tarefa `cron-apply` exige Koha.
* `/etc/cron.d/koha-nexus-platform-backups`: escrito por `kei_backup_schedule`, sem tela própria além do cartão "Agendar backups".
* WordPress: WP-Cron interno, disparado por visitas (`DISABLE_WP_CRON` só no teste isolado). Não é cron do servidor.

### Endereço, túnel e domínio gratuito

* Tainacan: `tainacan-plan URL`/`tainacan-install confirm URL` com um campo livre ("vazio = endereço local"); `tainacan-address URL` troca depois (search-replace, proxy, ingresso do túnel próprio via `kei_tunnel_ingress_add`).
* Koha: Cloudflare Tunnel Manager, com modo domínio próprio (config local) e modo endereço gratuito (`tunnel_mode broker`, ingresso gerenciado remotamente).
* Broker (`broker/`, Cloudflare Worker): um túnel por biblioteca, nomes planos `<slug>` e `<slug>-admin`, ingresso fixo `:80` e `:8080`, CNAMEs comentados `kei:lib:<id>`, reconciliação, nomes retidos 180 dias. Não conhece o Tainacan.

### Acesso administrativo

* Koha: o instalador da web (onboarding) cria a primeira conta; o painel mostra as credenciais do banco para ele (`credentials`) e cria superbibliotecário (`superlibrarian`), recusando usuário existente.
* Tainacan: `wp core install` com usuário e senha aleatórios guardados em `.env` (600); o painel mostra (`tainacan-credentials`). Não há troca de senha nem criação de outro administrador pelo painel.

### Pós-instalação

Não existe assistente. Cada instalação termina com uma mensagem e os links.

## 2. Lacunas

1. Duas centrais de backup concorrentes (Koha no grupo Koha, Tainacan no grupo Tainacan), mais chave e kit em Infraestrutura.
2. Não existe backup conjunto nem pacote transportável com as duas plataformas.
3. A restauração é separada por plataforma e decide pelo caminho escolhido, não por um exame do conteúdo.
4. Cadastro de conexão de nuvem exige banco Koha (`require_database` em `cloud-prepare`, `cloud-token`, `cloud-authorize`, `cloud-remote`), e `validate_and_register_rclone` cria um plano SQL/MARC do Koha e dispara o primeiro backup Koha.
5. Os planos de nuvem do Koha e a cópia do motor são mundos separados; não há plano para conjunto.
6. A tela de agendamentos só lê o `koha_tasks` e some sem Koha; a agenda das plataformas não aparece nela.
7. O campo de endereço do Tainacan é ambíguo; o endereço gratuito não existe para o Tainacan.
8. Não há troca de senha, redefinição ou novo administrador no Tainacan; no Koha, não há redefinição nem estado "conta inicial ainda não configurada".
9. Não há assistente pós-instalação nem registro de pendências.

## 3. Fluxos e esboços

### 3.1 Menu

```
📊 Painel de Controle            (abas Geral, Koha, Tainacan: sem mudança)
▸ 📚 Koha (biblioteca)           grupo; "💾 Backups do Koha" abre a central filtrada em Koha
▸ 🏺 Tainacan (acervos e museus) grupo; "💾 Backups do Tainacan" abre a central filtrada em Tainacan
💾 Central de backups      [b]   NOVA, no menu principal
⏰ Agendamentos             [s]   NOVA no menu principal (substitui "Agendamentos e tarefas cron" do grupo Koha)
🔒 Segurança e acesso
🧱 Infraestrutura compartilhada   (Docker; a chave e o kit vão para a Central de backups)
...
```

As seções antigas `backup` (Koha) e `tainacan-backups` saem. As teclas continuam: `b` abre a central, `s` os agendamentos.

### 3.2 Central de backups

```
💾 Central de backups
 Plataforma: (•) Koha  ( ) Tainacan  ( ) Koha e Tainacan     ← só as instaladas; "ambos" só com as duas
 ┌ Resumo da seleção ───────────────────────────────────────┐
 │ Último backup · tamanho · resultado · última restauração  │
 │ de teste · pendências (backup incompleto)                │
 └──────────────────────────────────────────────────────────┘
 Agora
   [💾 Fazer backup agora]  [📥 Restaurar…]  [🧪 Testar]  [📥 Baixar o último]
 Automático e nuvem
   [☁ Conexões de nuvem]  [🗓 Planos de backup]
 Recursos desta plataforma (aparecem só no contexto certo)
   Koha: [📚 Exportar MARC21] [Compressão] 
   Tainacan: [⏯ Backup incompleto] [🧾 Verificar backups] [🔐 Chave e kit de recuperação]
```

"Restaurar…" é uma entrada única para qualquer seleção: ela pede o arquivo e reconhece o tipo pelo conteúdo.

### 3.3 Backup manual conjunto

```
Koha e Tainacan · Fazer backup agora
 Plano: pasta de destino, espaço livre, o que entra (Koha: SQL; Tainacan: banco,
 arquivos, configuração cifrada ou não), aviso de que as plataformas são
 capturadas uma depois da outra, sem simultaneidade transacional.
 [Sim]
 Progresso por plataforma:  Koha ✔ 00:12  ·  Tainacan ✔ 01:40  ·  Pacote ✔
 Resultado: pacote knx-set-20261106-091500.tar (2,1 GB), manifesto, SHA256SUMS.
 Parcial: "Koha concluído, Tainacan falhou: <motivo>. O pacote não foi montado;
 o backup do Koha está em <caminho>. Para repetir: Fazer backup agora; para
 retomar o do Tainacan: Backup incompleto."
```

### 3.4 Restauração assistida

```
Restaurar · escolher arquivo (mesmo seletor de hoje: navegador por SSH, arquivo
no servidor, arquivo do Windows copiado)
 → exame (sem extrair nada fora de uma pasta de quarentena)
 Origem: knx-set-20261106-091500.tar · criado em 06/11/2026 09:15 no servidor X
 Plataformas: Koha (SQL 380 MB, íntegro) · Tainacan (banco + arquivos, íntegro,
 configuração cifrada)
 Conflitos: endereço do Tainacan no pacote = http://10.8.0.3:8090, atual =
 http://192.168.0.20:8090 (o atual é mantido); portas livres; volumes existentes
 serão substituídos depois da cópia de segurança.
 Restaurar: [x] Koha  [x] Tainacan
 Segredos: o pacote tem a configuração cifrada; sem a frase de recuperação o
 Tainacan é restaurado com a configuração atual (efeitos listados).
 → para cada plataforma marcada, o fluxo de hoje: confirmações, cópia de
   segurança, teste isolado (Tainacan) ou banco temporário (Koha).
```

### 3.5 Planos automáticos e nuvem

```
Planos de backup
 Plano          Plataforma     Destino                 Frequência       Retenção     Última execução
 noturno-koha   Koha           local + gdrive:/Koha    diário 23:00     7 d / 30 d   06/11 23:00 OK
 tainacan       Tainacan       local + restic          diário 02:00     7/7/4/6      Sem registro
 conjunto       Koha+Tainacan  gdrive:/Conjuntos       semanal dom 03:00 4 pacotes   Sem registro
 [Novo plano] [Editar] [Executar agora] [Desligar]

Conexões de nuvem (cadastro separado): lista, adicionar (Google Drive pelo fluxo
de autorização atual e os demais serviços do rclone), testar, apagar.
```

Cada plano tem conexão, pasta, frequência, horário e retenção próprios. Um plano nunca reaproveita a pasta de outro. A tela diz o que é cifrado: "configuração cifrada com a chave do servidor", "pacote de dados cifrado pela camada crypt da conexão" ou "repositório restic cifrado"; nunca "backup criptografado" sem dizer de quê.

### 3.6 Agendamentos

```
⏰ Agendamentos   Plataforma: [Todas ▾]  Tipo: [Todos ▾]
 Plataforma   Tarefa                       Frequência   Horário  Fuso                Estado   Última execução    Próxima
 Koha         Backup SQL noturno           diário       23:00    America/Sao_Paulo   ligado   06/11 23:00 OK     07/11 23:00
 Koha         Reindexação completa         semanal      dom 02   …                   ligado   Sem registro       09/11 02:00
 Tainacan     Backup                       diário       02:00    …                   ligado   06/11 02:00 OK     07/11 02:00
 Conjunto     Pacote Koha+Tainacan         semanal      …
 Tainacan     WP-Cron (interno do WordPress, dispara com visitas, não é cron do servidor)   —
 Manual       linha escrita à mão (preservada)
 [Editar] abre o editor de cada origem (o editor de hoje para o koha_tasks).
```

### 3.7 Endereço do Tainacan

```
Como as pessoas vão acessar o Tainacan?
 (•) Só nesta máquina ou na rede local
     Quem acessa: quem está nesta rede (http://192.168.0.20:8090). Nada vai para a internet.
 ( ) Domínio ou subdomínio da instituição (ex.: acervo.prefeitura.gov.br)
     Quem acessa: qualquer pessoa na internet, pelo túnel Cloudflare da instituição.
     Requer: o domínio na conta Cloudflare da instituição e o túnel configurado.
 ( ) Endereço gratuito do koha.nexus (ex.: palotina-acervo.koha.nexus)
     Quem acessa: qualquer pessoa na internet. O nome é do projeto, não da instituição.
     Disponível quando o serviço de endereços aceitar o Tainacan (ver seção 7).
 ( ) Configurar depois
     O Tainacan fica só na rede local até você escolher.
```

### 3.8 Acesso administrativo e assistente

```
Koha instalado. Próximos passos (1 de 4)
 1 Acesso administrativo   [Configurar agora] [Fazer depois]
 2 Acesso público          [Configurar agora] [Fazer depois]
 3 Backup e nuvem          [Configurar agora] [Fazer depois]
 4 Próximos passos e links
Pendências guardadas em /var/lib/koha-nexus/setup/<plataforma>.state; o grupo da
plataforma mostra "Continuar a configuração" enquanto houver pendência.
```

O assistente não tem configuração própria (Paulo, 06/11 09:01). Cada etapa abre a mesma rotina da central correspondente (acesso administrativo do grupo da plataforma, Endereço/Cloudflare em Segurança e acesso, Planos de backup da Central de backups), que lê o que já existe antes de propor algo: se já há um plano de nuvem ou um endereço, a etapa mostra o que está configurado e conta como feita, sem criar outro. "Fazer depois" só marca a pendência; o menu continua oferecendo tudo. Depois do assistente, consultar, alterar ou desligar é sempre pelas telas normais, com as confirmações de lá. O arquivo de pendências guarda apenas "feito, adiado ou pendente" por etapa, nunca parâmetros, e a etapa é recalculada pelo estado real (uma configuração feita pelo menu marca a etapa como feita).

Acesso administrativo do Tainacan: mostra o estado ("conta inicial ainda não configurada" = a conta aleatória da instalação continua com a senha gerada; "conta já existente"), e oferece "Definir minha senha" (para a conta inicial), "Redefinir a senha de um administrador", "Criar outro administrador". Campos protegidos, confirmação, senha por stdin para `wp user update` dentro do contêiner, nunca na linha de comando nem em log. Koha: estado do instalador da web (terminado ou não, pela existência de superbibliotecário), "Criar superbibliotecário" (função de hoje), "Redefinir a senha de um superbibliotecário" (hash pelo `Koha::AuthUtils` como hoje).

## 4. Formato do pacote conjunto

Arquivo `knx-set-<AAAAMMDD-HHMMSS>.tar` (tar sem compressão: as partes já vêm compactadas), também aceito como pasta com o mesmo conteúdo:

```
knx-set-20261106-091500/
  manifest.json
  SHA256SUMS                      sha256 de todos os arquivos, inclusive manifest.json
  koha/
    <db>_set_20261106-091500.sql.gz     o dump do Koha (mesma captura do backup manual)
  tainacan/
    knx-tainacan-20261106-091512/       o pacote formato 2 do motor, autossuficiente
      manifest.json  SHA256SUMS  db.sql.gz  files.tar.gz  secrets.tar.gpg | secrets/
```

`manifest.json`:

```json
{
  "kind": "koha-nexus-set",
  "format": 1,
  "id": "knx-set-20261106-091500",
  "created": "2026-11-06T09:15:00-03:00",
  "host": "biblioteca",
  "panel_version": "1.5.176",
  "complete": true,
  "consistency": "per-platform",
  "note": "Platforms captured one after the other; no transaction spans them.",
  "platforms": [
    {"id": "koha", "result": "ok", "path": "koha/biblioteca_set_20261106-091500.sql.gz",
     "instance": "biblioteca", "koha_version": "26.05", "started": "...", "ended": "...",
     "bytes": 398000000, "sha256": "...", "capture": "mysqldump --single-transaction"},
    {"id": "tainacan", "result": "ok", "path": "tainacan/knx-tainacan-20261106-091512",
     "package_format": 2, "started": "...", "ended": "...", "window_seconds": 88,
     "secrets": "gpg", "key": "<impressão digital>", "url": "http://...:8090",
     "manifest_sha256": "..."}
  ]
}
```

Regras:

* Montado só depois de todas as capturas terem dado certo; `complete: true` só então. Falha de uma plataforma: nada de pacote, as capturas válidas ficam onde estão, o resultado diz qual falhou e como repetir.
* Tainacan em modo referenciado (restic): para o pacote conjunto, a captura é feita autossuficiente (tar), porque um pacote transportável não pode depender de um repositório do servidor.
* Exame de entrada (restauração): tamanho total limitado ao espaço livre, só arquivos regulares e pastas, nenhum caminho absoluto, `..`, link simbólico, link físico, dispositivo ou FIFO; nomes só do conjunto esperado; `SHA256SUMS` confere antes de qualquer uso; o manifesto é lido como dado (nada dele é executado nem vira argumento de shell sem validação por expressão regular).
* Reconhecimento pelo conteúdo: `kind` do manifesto (conjunto), `format: 2` e `platform` (pacote do motor), e para SQL do Koha a pré-checagem atual (linhas SQL no início e linha final do mysqldump), em qualquer compressão aceita hoje.

## 5. Compatibilidade e migração

* Backups antigos do Koha (`.sql`, `.sql.gz`, `.sql.zst`, `.sql.xz`, `.bz2`) e pacotes do Tainacan (formato 1 e 2) continuam restauráveis pela mesma entrada.
* Os arquivos e scripts atuais (`backup_sql.sh`, `backup_marc.sh`, `cloud_plan.sh`, `cloud_plans.conf`, `koha_tasks`, `koha-nexus-platform-backups`) não mudam de formato. A central lê e escreve neles pelas tarefas de hoje.
* Planos de conjunto ficam num arquivo novo (`/var/lib/koha-nexus/backup/sets.conf`) e numa agenda nova (`/etc/cron.d/koha-nexus-backup-sets`, registrada em `owned.tsv`). Nada é criado ao atualizar o painel: só quando a pessoa cria um plano.
* Nenhuma migração cria agendamento novo. A central mostra os que existem. Para não duplicar: um plano de conjunto não liga sozinho os planos individuais; a agenda de conjunto é única por id; `cron-apply` continua conferindo o arquivo inteiro.
* Endereço: instalações existentes mantêm o endereço; o modo novo só se aplica quando a pessoa escolhe.
* Contas: nada muda ao atualizar. O assistente só aparece depois de uma instalação nova, ou quando a pessoa abre "Continuar a configuração".

## 6. Divisão em PRs e critérios de aceite

Cada PR aponta para a `main`. Quando um depende do anterior, a descrição diz isso e pede a ordem de mescla; o PR seguinte só é aberto depois de o anterior estar no ramo certo (o caso do #338 não se repete).

| PR | Conteúdo | Aceite principal |
|---|---|---|
| U1 (1.5.175) Central de backups e nuvem sem Koha | seção principal `backups` com seletor, atalhos filtrados nos grupos, remoção de `backup` e `tainacan-backups`, chave e kit na central; conexões de nuvem sem `require_database`; registro de conexão sem criar plano Koha quando não há Koha; planos por plataforma com destino, frequência, retenção e última execução; rótulos de cifra corretos | quatro cenários; nuvem configurável só com Tainacan; nenhum recurso existente perdido; testes de falha de conexão |
| U2 (1.5.176) Pacote conjunto e restauração assistida | `kei_set_*`, `--task backup-set-plan|run|list|inspect`, planos de conjunto com agenda própria, `--task backup-inspect FILE`, restauração seletiva reaproveitando os fluxos de hoje | pacote real (CI com Koha falso e Tainacan real), falha parcial, falta de espaço, arquivo malicioso, backups antigos |
| U3 (1.5.177) Central de agendamentos | seção principal `schedules` com filtros, linhas de todas as origens, última execução por log confiável, próxima execução calculada, WP-Cron identificado | sem duplicação, linhas manuais preservadas, "Sem registro" quando não há histórico |
| U4 (1.5.178) Acesso administrativo e assistente pós-instalação | tarefas `koha-admin-*` e `tainacan-admin-*`, estado de pendências, assistente | adiar não deixa conta sem senha; contas existentes intactas; senha fora de logs e status |
| U5 (1.5.179) Endereço do Tainacan e endereço gratuito | escolha de modo no instalar e depois; broker com hostname do Tainacan e biblioteca só Tainacan; procedimento de implantação | broker testado localmente (vitest + workerd); Koha intacto; nada publicado em produção |

## 7. Dependências externas e decisões

Dependências externas (não faço sozinho):

* **Broker em produção** (U5): aplicar a migração D1 e publicar o Worker é com Paulo, seguindo o procedimento do PR. Até lá, a opção "endereço gratuito" do Tainacan aparece como indisponível, com o motivo.
* **Google Drive**: o fluxo de autorização é o de hoje; não muda o projeto do Google nem o client id.

Decisões que precisam de Paulo (sigo com a recomendação enquanto isso):

1. **Nome do endereço gratuito do Tainacan.** Recomendo `<slug>-acervo.koha.nexus` (curto, em português, um nível só, coberto pelo certificado gratuito). O sufixo fica configurável no broker (`TAINACAN_SUFFIX`).
2. **Segredos do Koha no pacote conjunto.** Recomendo incluir `koha-conf.xml` cifrado com a chave do servidor quando ela existir (ele guarda a `encryption_key` do Koha, sem substituto), sem aplicá-lo sozinho na restauração. Sem a chave, o pacote não leva esse arquivo e a restauração explica o efeito.

Fora desta etapa, como pedido: busca unificada, SSO e o restante do roadmap.

## 8. Testes

* Painel (pytest, modo demonstração): os quatro cenários em cada tela nova, filtros, atalhos, teclado, terminal pequeno e grande.
* Instalador (bats): exame de pacote com entradas maliciosas, falha parcial, falta de espaço, planos sem duplicação, conexão de nuvem sem Koha, contas (senha fora de log), migração de agendas.
* CI com serviços reais: Tainacan real (WordPress + plugin + Docker) para backup conjunto e restauração seletiva; Apache real para túnel e endereço; broker em workerd local.
* Servidor de Paulo: só o roteiro não destrutivo do fim, com o que ainda depende dele marcado como pendente.

## 9. Situação (06/11/2026)

* U1 é o PR #341, aberto e com a CI verde.
* U2 a U6 estão prontos e testados aqui, com capturas em `capturas-U2` a `capturas-U6`.
  * Como todos usam o mesmo ramo, cada um é aberto quando o anterior estiver na `main`.
  * Os commits estão nas branches remotas `claude/etapa-T-u2` a `claude/etapa-T-u6`; estado exato em `X-continuidade-etapa-T.md`.
* Ajustes de 06/11 15:26:
  * U2 ganhou os arquivos e segredos do Koha no pacote: nunca em claro, e sem chave a pessoa escolhe antes;
  * U2 também ganhou a recuperação dos segredos sem sobrescrever o destino;
  * o job de CI `koha-set` usa Koha e Tainacan reais. Está configurado e ainda não rodou;
  * U6 (1.5.180) é o backup conjunto agendado.
  
  Detalhes: `V-auditoria-backup-koha.md` e `W-matriz-requisitos-etapa-T.md`.
* Correção (Paulo, 06/11 15:26): o backup conjunto agendado é requisito do pedido e das seções 3.5, 5 e 6 deste documento. Afirmei por engano que o pedido era só o backup manual. Ele entra num PR separado (U6), que reaproveita a operação manual (destino, retenção, bloqueio contra concorrência, histórico e falhas por plataforma), com `/etc/cron.d/koha-nexus-backup-sets` como previsto na seção 5. A configuração ficou junto da chave dos backups (`set_*`) em vez de num `sets.conf` à parte.
* U5: o serviço de endereços não foi publicado. O procedimento está no PR e no README do `broker/` ("Deploying the collection addresses"): testes locais, `npm run db:migrate` (a 0003 só acrescenta colunas), `npm run deploy` e conferir `GET /v1/capabilities`. Até lá, o painel mostra a opção como indisponível, com o motivo.
* Nome do endereço do acervo: `<biblioteca>-acervo.koha.nexus`, como recomendado (configurável em `TAINACAN_SUFFIX`).
* Servidor do Paulo: `roteiro-teste-etapa-T.sh`, nesta pasta. Só lê. Roda com `antes` antes de atualizar o painel e com `depois` depois; compara agendamentos, sites do Apache, túnel, firewall, contêineres e resumos de arquivos sensíveis (nunca o conteúdo). Também lê o estado da central de backups, das contas administrativas (sem senhas) e do endereço gratuito.
