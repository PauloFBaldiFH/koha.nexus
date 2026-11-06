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
| U1 | 1.5.175 | `claude/project-thread-evltj0` | `5691fc1` central de backups e nuvem sem Koha; `de2c191` telas de nuvem em Python 3.9 | #341, aberto, CI verde |
| U2 | 1.5.176 | `claude/etapa-T-u2` (ponta `60b1ae6`) | `09217e6` pacote conjunto e restauração assistida; `52ec636` negativos do bats falham de verdade; `69a863e` arquivos e segredos do Koha; `c857252` job `koha-set`; correções achadas pelo Koha real: `14b979a`, `fea6d88`, `7c42b40` (instalador: seção `<config>` certa do `koha-conf.xml`), `60b1ae6` | abrir depois do #341 |
| U3 | 1.5.177 | `claude/etapa-T-u3` (ponta `8ea9dcd`) | `c9591d0` central de agendamentos; `8ea9dcd` merge das correções do U2 | depois do U2 |
| U4 | 1.5.178 | `claude/etapa-T-u4` (ponta `4288144`) | `c490351` acesso administrativo e assistente pós-instalação; `4288144` merge | depois do U3 |
| U5 | 1.5.179 | `claude/etapa-T-u5` (ponta `e67ec19`) | `9b4751a` endereço gratuito do acervo (Tainacan); `e67ec19` merge | depois do U4 |
| U6 | 1.5.180 | `claude/etapa-T-u6` (ponta `bbc939a`) | `4c05abf` backup conjunto agendado; `b2235ad` merge; `bbc939a` passo agendado do `koha-set` | depois do U5 |
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

| Branch e commit | Workflow `proxy` (inclui `koha-set`) | Observação |
|---|---|---|
| `claude/etapa-T-u2` `c857252` | falhou (run 42255933667) | 1ª execução: chave da instância nova e `Version` |
| `claude/etapa-T-u2` `14b979a` | falhou (run 42260265675) | caminho do Koha para ler a versão |
| `claude/etapa-T-u2` `fea6d88` | cancelada (run 42262359611) | todos os testes rodaram, mas o bats não terminava (descritor preso) |
| `claude/etapa-T-u2` `7c42b40` | falhou (run 42268564245) | erro real do `<config>` corrigido; faltavam dois ajustes do teste |
| `claude/etapa-T-u2` `60b1ae6` | **verde, 16 de 16 jobs** (run 42270862044) | `koha-set` 8 de 8 |
| `claude/etapa-T-u3` a `u6` | em execução (runs 42271314751, 42271319434, 42271324914, 42271328590) | o U6 inclui o 9º passo, do backup agendado |

Todos os outros jobs do `proxy` (apache, system, tainacan, engine, events, nos três sistemas) passaram em todas as execuções do U2.

## 5. Pendências

Do Paulo:
1. Mesclar o #341, e depois cada PR na ordem.
2. Publicar o serviço de endereços (`broker/`) e aplicar a migração 0003. O procedimento está no README do `broker/`, em "Deploying the collection addresses". Nada é publicado automaticamente.
3. Rodar `roteiro-teste-etapa-T.sh antes` no servidor, atualizar o painel e rodar `roteiro-teste-etapa-T.sh depois`. O roteiro só lê, e os arquivos que ele gera ficam com permissão 600.

De quem continuar:
1. Conferir o resultado do `koha-set` no U6 (9º passo, backup agendado) e corrigir se falhar. Correções seguem a regra do merge da seção 1.
2. Abrir os PRs U2 a U6 na ordem da seção 2.
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
