# X. Continuidade da etapa T

Estado em 06/11/2026. Este documento basta para continuar a etapa T sem a pasta da conversa: todo o código, os testes, os documentos e o roteiro estão no GitHub.

Documentos desta pasta (`docs/etapa-T/`):

* `T-backups-agendamentos-pos-instalacao.md`: especificação da etapa (seção 6 = divisão em U1 a U6, seção 9 = situação).
* `V-auditoria-backup-koha.md`: o que o backup do Koha cobre e o que fica fora.
* `W-matriz-requisitos-etapa-T.md`: requisito por requisito, com teste realizado e pendência.
* `roteiro-teste-etapa-T.sh`: roteiro só de leitura para o servidor do Paulo (`antes` e `depois` da atualização).
* `prs/pr_u2.md` a `prs/pr_u6.md`: textos prontos dos PRs.

As capturas de tela (`capturas-U1` a `capturas-U6`) não estão no repositório, porque somam cerca de 16 MB. Ficam na pasta do projeto e podem ser refeitas pelos testes do painel.

## 1. Branches e commits

Cada etapa é uma branch remota, montada sobre a anterior. Nenhuma foi mesclada.

| Etapa | Versão | Branch remota | Commits (do mais antigo ao mais novo) | PR |
|---|---|---|---|---|
| U1 | 1.5.175 | `claude/project-thread-evltj0` | `5691fc1` central de backups e nuvem sem Koha; `de2c191` telas de nuvem em Python 3.9 | #341, **mesclado** em 06/11 |
| U2 | 1.5.176 | `claude/etapa-T-u2` (ponta `c7a71f4`) | `09217e6` pacote conjunto e restauração assistida; `52ec636` negativos do bats falham de verdade; `69a863e` arquivos e segredos do Koha; `c857252` job `koha-set`; correções achadas pelo Koha real: `14b979a`, `fea6d88`, `7c42b40` (instalador: seção `<config>` certa do `koha-conf.xml`), `60b1ae6`; `fc31d5e`, `c969b55` (testes do painel), `9a38ad9` (painel sem root), `991cc13`, `c7a71f4` (koha-create mostrado e repetido) | #342, **mesclado** em 06/11 |
| U3 | 1.5.177 | `claude/etapa-T-u3` (ponta `521edc7`) | `c9591d0` central de agendamentos; `8ea9dcd` merge das correções do U2 | #343, **mesclado** em 06/11 |
| U4 | 1.5.178 | `claude/etapa-T-u4` (ponta `dc4860c`) | `c490351` acesso administrativo e assistente pós-instalação; `70c6000` acesso administrativo do Tainacan por `wp eval-file`; merges das correções do U2 | **PR #344**, aberto |
| U5 | 1.5.179 | `claude/etapa-T-u5` (ponta `73656be`) | `9b4751a` endereço gratuito do acervo (Tainacan); `e67ec19` merge | depois do U4 |
| U6 | 1.5.180 | `claude/etapa-T-u6` (ponta `2862835`) | `4c05abf` backup conjunto agendado; `b2235ad` merge; `bbc939a` passo agendado do `koha-set` | depois do U5 |
| Documentos | (sem versão) | `claude/etapa-T-docs` | `2a963e6` e seguintes | sem PR; pode ir junto do U2 ou à parte |

Para conferir: `git fetch origin && git log --oneline origin/main..origin/claude/etapa-T-u6`.

Correções numa etapa já enviada entram como commit novo nessa branch e seguem para as de cima por merge (`git checkout uN && git merge u(N-1)`), nunca reescrevendo uma branch enviada. O único conflito esperado é `installer.sha256`: recalcular com `sha256sum installer > installer.sha256`.

## 2. Como abrir os PRs

Ordem obrigatória: U2, U3, U4, U5, U6. Cada um abre quando o anterior estiver na `main`. Nunca abrir um PR contra a branch de outro PR: quando o PR de baixo é mesclado na branch de cima, o trabalho não chega à `main` (aconteceu com o #338).

1. Com o anterior mesclado por merge commit (o padrão do repositório), basta abrir o PR da branch `claude/etapa-T-uN` contra a `main`. O GitHub mostra só os commits novos.
2. Se o anterior for mesclado por squash ou rebase, os commits dele reaparecem. Nesse caso, recriar a branch a partir da `main`:

   ```
   git fetch origin
   git checkout -b uN-novo origin/main
   git cherry-pick <commits da etapa N, da tabela acima>
   git push origin uN-novo:claude/etapa-T-uN-v2
   ```
   Se houver conflito, ele costuma estar só em `installer.sha256`, na versão do painel e no `preview/`. Para resolver:
   * manter a versão mais alta;
   * regenerar o preview com `python3 tools/export_docs_preview.py`;
   * recalcular `installer.sha256` com `sha256sum installer > installer.sha256`.
3. Texto do PR: `docs/etapa-T/prs/pr_uN.md`.
4. Ninguém mescla automaticamente. Quem mescla é o Paulo.

## 3. Testes

### Aprovados

Rodaram e passaram:

* **U1:** CI do #341 verde.
* **U2 a U6, nesta máquina:**
  * `tests/backup_set.bats`: 15 de 15 (S01 a S15, instalador de verdade, Koha e Tainacan simulados);
  * `tainacan_free.bats`, `admin_access.bats`, `platforms.bats`, `backup_engine.bats`, `cloud_test.bats`.
* **Painel no U6:** 993 aprovados e 2 ignorados.
  * Teve 1 falha de tempo de tela em `test_tools`, que não toca o que mudou e passou 3 vezes seguidas sozinha.
  * As falhas de tempo só aparecem quando duas suítes rodam ao mesmo tempo.
* **Mutações conferidas no S11.** O teste falha quando:
  * o `koha-conf.xml` inteiro é copiado do pacote;
  * o plano mostra o conteúdo de um segredo.

### Koha e Tainacan reais (job `koha-set`)

* `.github/workflows/proxy.yml`, job `koha-set`, com `tests/koha_set_system.bats`: Debian 12, Koha 26.05.05 do repositório oficial e Tainacan 1.4.1 de verdade.
* **Aprovado no U2** (run 42270862044, 8 de 8):
  * pacote conjunto completo, com os arquivos do Koha e os segredos só cifrados;
  * instância apagada e criada de novo, com outra chave e outra senha de banco;
  * Koha restaurado sozinho a partir do conjunto: o segredo de 2FA ainda não abre;
  * plano sem valores; depois de aplicado, só a `<encryption_key>` muda no `koha-conf.xml`, o segredo abre de novo, o arquivo enviado e o plugin voltam;
  * Tainacan restaurado à parte, sem tocar o Koha.
* No U6 o mesmo job tem um 9º passo (agendar, rodar o que o cron rodaria, conferir o histórico, desligar). Situação na seção 4.
* Não roda nesta máquina de desenvolvimento: aqui o repositório do Koha responde 403 e não há Docker. Roda na CI a cada envio.

### O que o Koha real ensinou

1. **Erro real do instalador, corrigido em `7c42b40`:** `_kei_koha_conf_value` lia o primeiro `<config>…</config>` do `koha-conf.xml`. Num arquivo real, esse é o caminho dentro da seção `<server>` do Zebra. Resultado: a chave, a senha do banco e os caminhos de uploads e plugins não eram achados, e o plano de recuperação dizia que o pacote não tinha chave. Agora o arquivo é lido como XML (o `<config>` filho da raiz). O `backup_set.bats` passou a usar um `koha-conf.xml` com a seção do Zebra primeiro, e o S08 e o S11 falham com o leitor antigo.
2. O `kohastructure.sql` sozinho não grava a preferência `Version`, que a restauração do painel exige. O teste grava a versão como o instalador web faria.
3. `koha-remove` mantém os arquivos da instância em `/var/lib/koha`. O teste apaga as pastas de uploads e plugins para fazer o papel de um servidor novo.
4. Um processo iniciado pelas tarefas (Zebra) prendia a saída do bats e o job não terminava. As tarefas rodam sem esse descritor (`3>&-`), e o job tem limite de 45 minutos.
5. **Erro real do U4, corrigido em `70c6000`:** o acesso administrativo do Tainacan usava `wp eval CÓDIGO LOGIN`, mas `wp eval` não entrega argumentos ao código (só `wp eval-file` preenche `$args`). A conta inicial nunca aparecia como tal e não dava para trocar a senha nem criar outro administrador. Agora o código vai num arquivo da pasta de trabalho, sem segredo; a senha continua só na entrada padrão. O dublê do WordPress em `admin_access.bats` imitava o erro e passou a se comportar como o wp-cli (A05 a A07 falham com o código antigo). Desinstalar o Tainacan também apaga os passos pós-instalação dele.
6. **Painel sem root, corrigido em `9a38ad9`:** a CI roda o painel como usuário comum; `Path("/root/backups").is_dir()` dava `PermissionError` e a rotina do backup conjunto terminava em silêncio. Agora uma pasta ilegível cai na pasta pessoal. Os testes da central guardam o erro de uma rotina e o mostram quando uma tela não chega. Conferido aqui como usuário comum (162 testes).
7. Um `koha-create` logo depois do `koha-remove` falhou uma vez (branch do U5), com a saída escondida. O teste agora mostra a saída e tenta de novo uma vez, depois de limpar o que sobrou.

### Comandos

```
# instalador (bats), na raiz do repositório
bats tests/backup_set.bats
# painel (sempre da raiz; rodar de panel/ quebra test_site_languages)
python -m pytest -q -p no:cacheprovider panel/tests
# só as telas da etapa T
python -m pytest -q -p no:cacheprovider panel/tests/test_backup_center.py panel/tests/test_schedules.py panel/tests/test_admin_setup.py
# Koha e Tainacan reais (precisa de Docker e de acesso a debian.koha-community.org)
tests/system/container.sh start debian:12 kn-system
KEI_REQUIRE_REAL_KOHA=1 KEI_REQUIRE_REAL_TAINACAN=1 KEI_TAINACAN_REGISTRY=docker.io \
  tests/system/container.sh run kn-system bats tests/koha_set_system.bats
tests/system/container.sh stop kn-system
```

Não rodar duas suítes do painel ao mesmo tempo.

## 4. CI das branches

Atualizado a cada execução acompanhada.

| Branch e commit | Resultado | Observação |
|---|---|---|
| U2 `c857252` a `7c42b40` | falhou (4 rodadas) | ajustes do teste e o erro real do `<config>` (ver acima) |
| U2 `60b1ae6` | `proxy` verde, 16 de 16; `koha-set` 8 de 8 | Platforms panel vermelho: painel sem root (corrigido em `9a38ad9`) |
| U3 a U6, merges das correções | `koha-set` verde nos quatro, com o 9º passo (backup agendado) no U6 | Tainacan real vermelho do U4 em diante: `wp eval` (corrigido em `70c6000`, verde no U4 e no U6) |
| U5 `c81fe35` | `koha-set` falhou uma vez no `koha-create` | mesma etapa passou no U4 e no U6; saída e nova tentativa em `991cc13`/`c7a71f4` |
| PR #342 (U2), `9a38ad9` | `koha-set` verde; Platforms panel: 1 teste clicava antes da janela montar | corrigido em `c969b55` |
| PR #342 (U2), `c7a71f4` | 47 de 47 verdes | mesclado em 06/11 |
| PR #343 (U3), `521edc7` | verde | mesclado em 06/11 |
| U4 `dc4860c` | 19 de 19 verdes, inclusive `koha-set` e `tainacan` nos três sistemas | aberto como PR #344 |
| Pontas atuais | em execução | a conferir |

Todos os outros jobs do `proxy` (apache, system, tainacan, engine, events, nos três sistemas) passaram em todas as execuções do U2.

## 5. Pendências

Do Paulo:
1. Mesclar cada PR na ordem (o #341, o #342 e o #343 já entraram; agora o #344).
2. Publicar o serviço de endereços (`broker/`) e aplicar a migração 0003. O procedimento está no README do `broker/`, em "Deploying the collection addresses". Nada é publicado automaticamente.
3. Rodar `roteiro-teste-etapa-T.sh antes` no servidor, atualizar o painel e rodar `roteiro-teste-etapa-T.sh depois`. O roteiro só lê, e os arquivos que ele gera ficam com permissão 600.

De quem continuar:
1. Acompanhar a CI do #344 e das pontas U5 e U6; corrigir na branch mais baixa e levar adiante por merge (seção 1).
2. Quando o #344 entrar, abrir o U5 (`claude/etapa-T-u5`, texto em `prs/pr_u5.md`), e assim por diante, um de cada vez.
3. Nada de servidor real foi testado. Nenhum teste destrutivo deve rodar no servidor do Paulo.

Fora do escopo: Portal Nexus, DSpace e AtoM.

## 6. Regras da etapa, para quem continuar

Pacote e backup:
* Uma única central de backups.
* O pacote guarda os dados, nunca referências.
* Cada plataforma é capturada na sua vez. Nunca dizer que a captura foi simultânea.
* Falha parcial nunca vira "concluído".
* A restauração reconhece o arquivo pelo conteúdo e o trata como não confiável. O manifesto nunca é executado.
* Dizer exatamente o que está cifrado.
* Os segredos do Koha nunca vão em claro. Sem a chave dos backups, a pessoa escolhe antes de gerar. Um pacote só com os dados nunca é chamado de completo.
* A recuperação só troca a `<encryption_key>`. Nenhum valor de segredo é mostrado.

Agendamentos:
* Nunca duplicar um agendamento.
* WP-Cron não é cron do servidor.
* Sem histórico, mostrar "Sem registro".

Senhas e contas:
* Senhas nunca aparecem em logs, status, capturas ou relatórios.
* Atualizar o painel não cria exposição pública, conta nova nem agendamento.

PRs e testes:
* O assistente pós-instalação só reaproveita as telas permanentes.
* PRs abertos para revisão, nunca mesclados automaticamente.
* Teste configurado na CI ainda não é teste aprovado.
