# W. Matriz de requisitos da etapa T

Situação em 06/11/2026, noite (atualizada às 19h com a CI do Koha real). Pedidos de origem: documento T, os ajustes do Paulo das 15:26 e das 15:31, e as regras permanentes da etapa.

## Como ler

* **PR/commit.** Só o U1 é PR aberto (#341). Os outros estão nas branches remotas `claude/etapa-T-u2` a `claude/etapa-T-u6`, uma sobre a outra (ver `X-continuidade-etapa-T.md`). Todos usam o mesmo ramo designado, então cada PR só abre quando o anterior estiver na `main`.
* **Teste realizado.** Só conta o que rodou e passou:
  * bats e pytest, aqui;
  * a CI, no caso do U1.
* **Configurado na CI.** Teste escrito que ainda não rodou. Pela sua regra, isso não é teste aprovado: fica na coluna de pendência.

## Matriz

| # | Requisito | Implementado | PR/commit | Teste realizado | Pendência |
|---|---|---|---|---|---|
| 1 | Uma central de backups no menu principal (Koha, Tainacan ou os dois); atalhos filtrados; sem telas concorrentes | sim | U1, PR #341 (5691fc1, de2c191) | CI verde no #341; pytest `test_backup_center` nos quatro cenários | mesclar o #341 |
| 2 | Conexões de nuvem sem banco do Koha | sim | U1, PR #341 | CI verde no #341; bats de nuvem | mesclar o #341 |
| 3 | Pacote conjunto com os dados (não referências), captura consistente por plataforma, sem dizer que é simultâneo | sim | U2 (09217e6, 52ec636) | bats S01 a S07 e S09; pytest de backup e restauração | job `engine` (Tainacan real) só roda quando o PR abrir |
| 4 | Falha parcial nunca "concluído"; falta de espaço; arquivo malicioso; manifesto nunca executado | sim | U2 | bats S02, S03, S06, S07 (os negativos falham de verdade desde 52ec636) | nenhuma |
| 5 | Restauração assistida: reconhece pelo conteúdo, restauração seletiva reaproveitando as rotinas de cada plataforma | sim | U2 | bats S04 e S05; pytest `restore-assisted` nos quatro tipos de arquivo | prova com Koha real: item 11 |
| 6 | Auditoria do backup do Koha: banco × reconstruir a instalação; dependências externas declaradas | sim | documento `V-auditoria-backup-koha.md`; manifesto com `external` (69a863e) | bats S08 (manifesto e pacote) | conferir na CI os usos de `Koha::Encryption` (o job lista no log) |
| 7 | Arquivos do Koha fora do banco no pacote (uploads, plugins, imagens, regras e perfis do painel) | sim | U2 (69a863e) | bats S08 (o que entra; `vision.conf` fica fora dos dados) | prova com Koha real: item 11 |
| 8 | Segredos do Koha nunca omitidos em silêncio. Sem chave: configurar ou gerar sem segredos, explicado antes. Pacote sem segredos ≠ completo | sim | U2 (69a863e) | bats S08 (rc 7 `needs=key`, `data-only`, `partial`); pytest da escolha antes de gerar (as três respostas) | nenhuma |
| 9 | Segredos nunca em claro, nem no pacote nem na nuvem | sim | U2 (69a863e); nuvem no U6 (4c05abf) | bats S08 (nenhum valor legível no pacote nem nos arquivos dele); S15 (nuvem só `.tar.gpg`, recusada sem chave) | nenhuma |
| 10 | Recuperar os segredos sem sobrescrever o destino: só a `encryption_key`; senha do banco, caminhos e configurações do destino ficam; demais segredos ao lado; valores nunca mostrados | sim | U2 (69a863e) | bats S11, com dois erros de propósito que o teste pega; pytest do plano, da frase só no ambiente e do Sim | prova com Koha real: item 11 |
| 11 | Validação real com Koha e Tainacan reais: pacote conjunto, restauração seletiva, recuperação de dado que depende da chave (2FA), arquivo e plugin | sim | U2: c857252 (job `koha-set`, Debian 12), correções 14b979a, fea6d88, 7c42b40, 60b1ae6 | **CI aprovada** na branch `claude/etapa-T-u2` (run 42270862044, Koha 26.05.05 e Tainacan reais, 8 de 8): o segredo de 2FA não abre depois da restauração do banco e abre de novo depois da volta da `encryption_key`; só essa linha muda no `koha-conf.xml`; arquivo enviado e plugin de volta; Tainacan restaurado à parte | nenhuma (no U2). A CI achou e corrigiu um erro real: a leitura do `koha-conf.xml` pegava o `<config>` do Zebra |
| 12 | Central de agendamentos: todas as origens, sem duplicar, "Sem registro" sem histórico, WP-Cron identificado | sim | U3 (c9591d0) | pytest `test_schedules` nos quatro cenários | nenhuma |
| 13 | Acesso administrativo: senha fora de logs, status e capturas; contas existentes intactas; chaves de criptografia nunca trocadas | sim | U4 (c490351) | bats `admin_access` (o dublê agora se comporta como o wp-cli); pytest `test_admin_setup`; `tainacan_system.bats` com WordPress real verde no U4 e no U6 depois da correção `70c6000` | nenhuma |
| 14 | Assistente pós-instalação só reaproveita as telas permanentes; "Fazer depois" deixa tudo no menu | sim | U4 | pytest do assistente e das etapas adiadas | nenhuma |
| 15 | Funções permanentes (domínio, contas, nuvem, agendamento) acessíveis depois de concluir ou adiar o assistente | sim | teste no U6 (4c05abf) | pytest `test_the_permanent_screens_stay_in_the_menu...`, em três estados: concluído, adiado e sem assistente | nenhuma |
| 16 | Endereço do Tainacan: modos e endereço gratuito; serviço externo nunca publicado automaticamente | sim | U5 (9b4751a) | vitest 68; ponta a ponta em workerd 24; bats `tainacan_free` 9; pytest 9 | **seu passo:** publicar o serviço de endereços e aplicar a migração 0003 (procedimento no README do `broker/`) |
| 17 | Backup conjunto agendado: reaproveita a operação manual, com destino, retenção, bloqueio contra concorrência, histórico e falhas por plataforma | sim | U6 (4c05abf, 1.5.180) | bats S12 a S15:<br>• escrito só quando pedido;<br>• sem chave, a pessoa escolhe;<br>• uma linha só;<br>• retenção só dos pacotes do agendamento;<br>• falha parcial;<br>• execução concorrente pulada e registrada;<br>• nuvem cifrada.<br>pytest da rotina, da linha na central de backups e na de agendamentos | nenhuma: o 9º passo do `koha-set` (agendar, rodar o que o cron rodaria, histórico `ok`/`full` nas duas plataformas, desligar) passou com Koha e Tainacan reais na branch `claude/etapa-T-u6` |
| 18 | Atualizar o painel não cria exposição pública, conta nova nem agendamento | sim | U1 a U6 | bats S12 (carregar o instalador e ler o status não escrevem nada); `admin_access` e `tainacan_free` (nada sem um Sim) | conferir no seu servidor com o roteiro (item 19) |
| 19 | Roteiro do servidor não destrutivo, revisto conforme os pontos das 15:31 | sim | `roteiro-teste-etapa-T.sh` | rodado aqui com um painel simulado:<br>• agendamento repetido aparece como arquivo:linha e resumo, sem o comando;<br>• arquivos 600 e pasta 700 | rodar no seu servidor (antes e depois da atualização) |
| 20 | Portal Nexus, DSpace e AtoM fora desta etapa | respeitado | (nenhum) | (nenhum) | (nenhuma) |

## Testes desta rodada

* bats `backup_set.bats`: 15 de 15 (U6). Rodados também `tainacan_free`, `admin_access` e `platforms` sobre o U5 refeito.
* Mutações conferidas no S11. O teste falha quando:
  * o `koha-conf.xml` inteiro é copiado do pacote;
  * o plano mostra o conteúdo de um segredo.
* pytest: os arquivos tocados passam em Python 3.13 e no subconjunto da CI em Python 3.9.
* Suíte completa do painel no U5 refeito: 987 aprovados.
  * 4 falhas de tempo de tela, que passam sozinhas.
  * Rodou ao mesmo tempo que outra suíte.
* Suíte completa do painel no U6: 993 aprovados, 2 ignorados e 1 falha de tempo de tela (`test_tools`), que passou 3 vezes seguidas sozinha.
* Capturas das telas novas em `capturas-U6/`, em terminal pequeno e grande. Nenhuma senha ou frase aparece: a frase digitada fica oculta.

## Pendências que dependem de você

1. Mesclar o #341. Depois disso eu abro o U2, e assim por diante até o U6.
2. Publicar o serviço de endereços e aplicar a migração 0003 (U5).
3. Rodar o roteiro no servidor, com `antes` e `depois`.
4. Se quiser, uma recuperação real numa máquina de teste sua. O job `koha-set` faz isso na CI.
