# Continuidade do PR combinado DSpace 5 + 6

Atualizado em 08/11/2026. Branch remota: `feat/dspace-operations`, sobre
`main` no commit `1504c03` (PR #354 mesclado). Versão: **1.5.184**.
Não mesclar nem publicar automaticamente. Paulo prefere abrir o PR pelo link:

https://github.com/PauloFBaldiFH/koha.nexus/compare/main...feat/dspace-operations?expand=1

Escopo, recuperação, limitações e capturas estão em
[PR5-6-operations.md](PR5-6-operations.md). Texto sugerido para o PR:
[PR5-6-description.md](PR5-6-description.md).

## Implementado e enviado

- Backups individuais e conjuntos explícitos com DSpace, planos com participantes
  fixos, agenda, histórico, retenção e cópia integralmente cifrada usando as
  conexões rclone existentes. Planos Koha/Tainacan anteriores não são ampliados.
- Restauração seletiva pelo adaptador de cada plataforma; formato anterior
  preservado. Pacotes são verificados antes da extração, em staging privado.
- Endereço/HTTPS assistido, certificado existente ou proxy externo; preparação
  opcional do endereço gratuito pelo broker, sem implantação de produção.
- Atualização homologável somente da receita 3 para 4 do mesmo DSpace 10.1.
  Recria também Solr, verifica a matriz efetivamente em execução e guarda
  configuração/catálogo anteriores para rollback sem retroceder os dados.
- Remoção mantém dados por padrão; exclusão exige salvaguardas e propriedade.
  Diários privados permitem tratar interrupções. Agendas podem ser desligadas
  mesmo sem a conexão de nuvem ou o destino originais.

## Evidência local e limites

- 137 testes Python 3.13 aprovados; testes de propriedade de diretório executados
  com UIDs reais, fora do remapeamento da sandbox. Docker/cripto simulados nesses
  testes de falha são identificados como tais.
- 130 testes de painel/documentação aprovados, mais o novo teste de adiamento de
  publicação sem chave (131). Dez avisos de encerramento Textual/workers ficaram
  registrados na rodada; nenhum teste falhou nessa seleção.
- Broker: TypeScript, 72 unitários, 24 checks e2e existentes e seis novos checks
  DSpace aprovados com Worker/D1/DO e assinaturas reais, Cloudflare simulado.
- 37 testes Bash aprovados (20 conjuntos/cron, nove Tainacan e oito DSpace).
  Usam contêiner Debian 12 descartável como root. Adaptadores de
  captura Koha/Tainacan e respostas do cliente DSpace são simulados e declarados
  nos arquivos. Não equivalem a executar as três aplicações reais juntas.
- Capturas de interface são do modo de demonstração em 80×24 e 160×48.

## CI: acompanhar antes da mesclagem

Não interpretar testes escritos, imagens construídas ou jobs em fila como aceite.
O workflow `dspace-images.yml` inclui aplicações reais, GPG, rclone, navegador,
URL/TLS e atualização com imagens históricas reais da receita 3. As imagens
históricas vêm do export imutável `858153cc730c17d410943836d222944149c24250`.

Na rodada `42455902927`, a instalação integrada falhou na conexão rclone;
o teste foi corrigido para criar sua conexão com o mesmo arquivo de configuração
usado pelo runtime, sem depender do HOME preservado por sudo. A atualização
histórica também falhou naquela rodada. A nova rodada precisa comprovar o
resultado: foram corrigidos a recriação do Solr e a verificação da matriz, e foi
adicionada uma anotação pública com os frames da falha, sem exportar segredos.
Não afirmar que a causa histórica está resolvida sem a nova execução passar.

Consultar os checks do último commit da branch/PR, incluindo os workflows de
proxy, painel, broker e Tainacan. Corrigir a falha concreta preservando os
critérios de aceite. Não remover gates, rotular imagens novas como antigas ou
contar um teste simulado como validação real.

Na execução do PR #355 sobre `5ac2f88`, os logs fornecidos por Paulo confirmam
HTTP 504 do GitHub em dois downloads: Syft 1.42.3 no inventário da imagem Solr
(`42473993293`) e cloudflared no job de sistema do proxy (`42473993440`). Não
foram falhas de execução do DSpace nesses passos. A CI agora separa o download
do Syft, fixado em 1.42.3, e permite uma segunda tentativa após 30 segundos;
o inventário continua obrigatório. O curl do cloudflared passa a ter intervalo
de 30 segundos e limites explícitos de tempo/tentativas, sem aceitar erro nem
instalar download parcial. Esses ajustes toleram indisponibilidade transitória;
não comprovam os testes integrados que foram pulados. Conferir a nova execução.

## Continua pendente fora da CI

Servidor de Paulo, convivência/carga real das três plataformas, reboot de VM/WSL,
domínio/túnel na conta real e matriz de aplicação completa Debian 12/13 e ARM.
DSpace permanece experimental. OAI não é publicado pelo proxy gerenciado até
homologar visibilidade e reconciliação do índice. Não há emissão ACME automática.
Broker/migração 0004/imagens não foram publicados; a opção de endereço gratuito
só funciona após promoção explícita do serviço, com o feature flag habilitado.

## Revisão independente e correção da CI (08/11/2026, tarde)

Estado conferido: `main` em `1504c03`; branch e PR #355 em `734d310` antes desta
revisão. Nenhum trabalho pendente local foi encontrado. Código validado na CI:
**`ca99aa6`** (código; o commit seguinte só altera documentação) (ver "Resultado da CI" abaixo).

### Causa das falhas da CI (logs completos do commit 734d310)

As quatro falhas (installation e upgrade, por push e pull_request) têm **duas
causas distintas**, ambas determinísticas: repetem-se em 68a5c3d, d1f1194 e
5ac2f88. O HTTP 504 do Syft/cloudflared não participa delas (os jobs de imagem
baixaram o Syft na primeira tentativa).

1. **installation** — `KeyError: 'complete'` em `dspace_operations_test.py:29`.
   O instalador entrega os resultados de `--task` como linhas `@@result` em
   **stderr** (`kei_emit`), e `Operations.driver` devolvia só o stdout. O teste
   não recebia nenhum resultado. O mesmo defeito existia no produto:
   `run_plan` de um plano com Koha/Tainacan + DSpace sempre terminaria com "No
   platform could be captured", ou seja, **todo backup agendado conjunto com
   DSpace falharia**. Corrigido com `Operations.results()`, que lê o fluxo do
   protocolo e devolve também os resultados de uma captura parcial. Teste novo
   com o instalador real, sem dublê.
2. **upgrade** — `DSpace REST API did not become ready` na segunda atualização
   (a primeira, com falha injetada, já fazia rollback corretamente). O guarda de
   esquema do backend (`NexusSchemaGuard`) calcula o recibo com o *release lock*
   da imagem mais o histórico Flyway. A imagem da receita 4 tem outro lock, então
   o recibo gravado pela receita 3 não confere e o backend se recusa a iniciar
   (saída 78) em toda atualização real. Corrigido sem afrouxar o guarda: a
   atualização confere o histórico com o guarda da imagem instalada, guarda o
   recibo exato no diário, regrava o recibo com a imagem nova com o backend
   parado, e o rollback devolve o recibo anterior antes de subir a imagem antiga.
   Diários antigos sem recibo mantêm o comportamento anterior. O teste de
   atualização agora imprime logs dos serviços (senha do laboratório
   redigida) quando falha, o que faltava para diagnosticar.

Os jobs `publish` ficam pulados por desenho: só rodam com `workflow_dispatch`
na `main` e `publish=true`.

### Problemas encontrados na revisão e correções

| Gravidade | Problema | Situação |
|---|---|---|
| Perda de backup | Planos agendados conjuntos com DSpace nunca capturavam (resultado lido de stdout) | Corrigido, teste com o instalador real |
| Funcionamento | Atualização 3 → 4 nunca subia o backend (recibo de esquema) | Corrigido, testes de ordem/rollback/recibo inválido; aceite real na CI |
| Recuperação | Após atualizar, a restauração exige a matriz exata de imagens: pacotes da receita 3, inclusive o backup de segurança da própria atualização, são recusados | **Não resolvido**: o plano (`earlier_backups_restorable_after_update=False`) e a confirmação do painel agora avisam. Restaurar receita 3 em receita 4 exige procedimento revisado e teste real |
| Padrão combinado | Agendas DSpace apareciam em Agendamentos sem última execução nem status | Corrigido: lê o histórico privado; captura parcial, cópia falha ou retenção não executada aparecem como FALHOU |
| Agenda silenciosa | A linha do cron chamava `/usr/local/bin/config.sh` sem conferir se existe; sem ele, o plano falharia toda noite (127) sem aviso. Achado na CI de 2fa0c94, que roda a linha exata do cron | Corrigido: `plan-cron` recusa (rc 3) antes de gravar; o teste instala o comando como num servidor real; bats DS03b |
| Higiene | Bytecode Python enviado por engano no primeiro commit desta revisão | Removido; `__pycache__/` no `.gitignore` |

Conferido sem defeito concreto: extração (lista de membros, duplicatas,
conteúdo DSpace não declarado, cópia privada antes de inspecionar, limite de
descompressão), nuvem cifrada sem poda após falha, retenção restrita aos
arquivos do plano, desativar agenda sem nuvem/chave, `plan-cron` só remove
arquivo registrado como próprio, remoção mantém dados por padrão e recusa
túnel ativo, `publish` pulado conforme o workflow.

Observações sem correção neste PR (registrar para decisão):

- O backup conjunto manual pelo painel não cifra o pacote externo: o membro
  DSpace e os segredos do Koha vão cifrados, o SQL do Koha não (igual ao formato
  1). Só o plano agendado cifra o conjunto inteiro. O texto "pacote integral
  cifrado" de `PR5-6-operations.md` vale para planos, não para o conjunto manual.
- Dois planos com DSpace no mesmo horário: o segundo encontra a trava da
  plataforma e registra falha de captura (sem perda de dados).

### Padrão combinado (Tainacan) aplicado ao DSpace

- Zonas: instalar, uso, recuperação e remoção existem no grupo DSpace; remoção
  na zona própria; restaurar só na Central de backup. Aplicado.
- Uma só Central de backup, restauração que reconhece o conteúdo: conjuntos
  formato 2 reconhecidos pelo manifesto; um arquivo cifrado desconhecido pede ao
  operador o tipo (conjunto ou pacote DSpace) e o conteúdo ainda é verificado.
  Aplicado em parte: o tipo de um arquivo cifrado não é detectado sozinho.
- Agendas listadas com sistema, texto curto, última execução e status: aplicado
  nesta revisão.
- Domínio e endereço num único lugar em Segurança e acesso: **não aplicado**. Na
  `main` o endereço do Tainacan também fica no grupo dele ("Tainacan address"),
  e o DSpace segue o mesmo lugar. Mover os dois para Segurança e acesso muda o
  Tainacan, fora do escopo pedido; fica para decisão de Paulo.

### Testes desta revisão

- Locais (real): 142 testes Python `test_dspace_*` (inclui o novo teste com o
  instalador real); 221 testes do painel na seleção do job "Platforms panel"
  (Textual real, serviços simulados); `bash -n installer`.
- Simulados: ordem de reinício, recibo e rollback usam dublês de Docker; não
  provam o DSpace real. Quem prova é o job `upgrade` da CI.
- Não executados aqui: jobs com DSpace real (rodam na CI), bats Debian.

### Resultado da CI

Rodadas desta revisão (workflow "DSpace image foundation"):

| Commit | installation | upgrade | Observação |
|---|---|---|---|
| 734d310 (antes) | falha `KeyError: 'complete'` | falha REST API | causas 1 e 2 acima |
| 2fa0c94 | falha 127 na linha do cron | **passou** | recibo de esquema confirmado com imagens reais r3 → r4 |
| ca99aa6, pull_request (run 42484700539) | **passou** | **passou** | aceite completo com DSpace real, navegador, GPG, rclone local, URL/TLS, remoção mantendo dados |
| ca99aa6, push (run 42484696631) | 1ª tentativa: `systemctl restart docker` passou de 120 s (passo de PR4, inalterado); 2ª tentativa **passou** | **passou** | reexecutado sem mudança |

Proxy em ca99aa6: pull_request passou; no push, `events (debian:13)` falhou na
preparação porque o wordpress.org não entregou o checksum do Events Manager
7.4.13 (o teste exige o plugin real, corretamente). O PR não altera eventos;
o job passou nos commits anteriores do dia. Reexecutado sem mudança.

Nenhum timeout foi aumentado: o reinício do Docker excedeu 120 s uma vez em
nove execuções e não há evidência de que o tempo seja insuficiente.

Reexecuções (attempt 2, mesmo commit, sem mudança): DSpace image foundation
push **passou** inteiro (installation e upgrade), proxy push **passou**
(inclusive `events (debian:13)`). Resultado: todos os checks de `ca99aa6`
verdes nos dois eventos; `publish` pulado como previsto.

### Continua pendente (exige servidor real)

Servidor de Paulo, convivência real Koha + Tainacan + DSpace com carga, reboot
de VM/WSL, túnel/domínio na conta real, broker e migração 0004 publicados,
restauração de pacote da receita 3 após atualizar, ARM, Debian 12/13 com DSpace
completo.
