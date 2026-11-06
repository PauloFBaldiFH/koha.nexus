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
| U2 | 1.5.176 | `claude/etapa-T-u2` | `09217e6` pacote conjunto e restauração assistida; `52ec636` negativos do bats falham de verdade; `69a863e` arquivos e segredos do Koha; `c857252` job `koha-set` | abrir depois do #341 |
| U3 | 1.5.177 | `claude/etapa-T-u3` | `c9591d0` central de agendamentos | depois do U2 |
| U4 | 1.5.178 | `claude/etapa-T-u4` | `c490351` acesso administrativo e assistente pós-instalação | depois do U3 |
| U5 | 1.5.179 | `claude/etapa-T-u5` | `9b4751a` endereço gratuito do acervo (Tainacan) | depois do U4 |
| U6 | 1.5.180 | `claude/etapa-T-u6` | `4c05abf` backup conjunto agendado | depois do U5 |
| Documentos | (sem versão) | `claude/etapa-T-docs` | este commit | rascunho |

Para conferir: `git fetch origin && git log --oneline origin/main..origin/claude/etapa-T-u6`.

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

### Configurados na CI, ainda não aprovados

* Job `koha-set` em `.github/workflows/proxy.yml`, com `tests/koha_set_system.bats`: Debian 12, Koha de verdade (`koha-common` do repositório oficial) e Tainacan de verdade.
* Ele nunca rodou nesta máquina: aqui o repositório do Koha responde 403 e não há Docker.
* O envio das branches dispara a CI por `push`. A situação de cada execução está na seção 4.

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

| Branch | Workflow `proxy` (inclui `koha-set`) | Observação |
|---|---|---|
| `claude/etapa-T-u2` | em execução (run 42255933667) | primeira execução real do `koha-set` |

## 5. Pendências

Do Paulo:
1. Mesclar o #341, e depois cada PR na ordem.
2. Publicar o serviço de endereços (`broker/`) e aplicar a migração 0003. O procedimento está no README do `broker/`, em "Deploying the collection addresses". Nada é publicado automaticamente.
3. Rodar `roteiro-teste-etapa-T.sh antes` no servidor, atualizar o painel e rodar `roteiro-teste-etapa-T.sh depois`. O roteiro só lê, e os arquivos que ele gera ficam com permissão 600.

De quem continuar:
1. Acompanhar o `koha-set` e corrigir as falhas dele antes de qualquer outra coisa. A correção vai na branch `claude/etapa-T-u2`, e as branches seguintes são refeitas por cima, com cherry-pick, numa branch nova (`-v2`), porque não se reescreve uma branch já enviada.
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
