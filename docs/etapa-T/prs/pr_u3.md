
Terceiro PR da etapa T (especificação em `estudo-ecossistema/v2/T-backups-agendamentos-pos-instalacao.md`, seção 6, U3). Aponta para a `main`, já com o U2 dentro.

## O que muda

**Central de agendamentos no menu principal** (área Servidor, tecla **s**), só leitura:
- uma linha por linha de cron, de todos os arquivos que guardam um agendamento do Koha.Nexus: `koha_tasks` (tarefas do Koha, backups na nuvem, linhas escritas à mão e blocos `# BEGIN ... # END`), `koha-nexus-platform-backups` (backup, manutenção e teste de restauração do Tainacan), os arquivos próprios do instalador (vigias do Elasticsearch e do Zebra, mensagens, mapa do site do OPAC, sinal de vida do endereço gratuito, IA local ao iniciar) e o `koha-common` do próprio pacote do Koha;
- cada linha diz plataforma, quando roda, se está ligada, a última execução, a próxima execução (calculada pela linha, no fuso horário do servidor) e onde é alterada;
- a última execução vem só de registro confiável (log do backup noturno, linhas da nuvem com `[ID]`, pacote mais novo do Tainacan, teste de restauração); sem registro, **Sem registro**;
- **WP-Cron** aparece como agendador interno do WordPress, que roda com visitas, nunca como agendamento do servidor;
- sem duplicação: nada aparece duas vezes, os presets do editor que não estão no arquivo não viram linha, e um mesmo comando ligado em duas linhas mostra o aviso "roda duas vezes";
- uma senha escrita à mão numa linha (`-p...`, `--password=`, `token=`) aparece como `***`;
- filtros **Plataforma** (só as instaladas, mais Servidor) e **Tipo** (backups, manutenção e indexação, outras); o cartão **Agendamentos do Koha** do grupo Koha abre a central já filtrada.

**Os editores continuam os mesmos**: o cartão **Tarefas agendadas do Koha** abre a tela de hoje (Tarefas agendadas e automações, que agora sai da barra lateral e fica dentro da central) e **Agendar backups** abre a rotina do Tainacan. Nenhum arquivo é escrito por esta tela.

Também: traduções pt-BR, manual (en e pt-BR: nova seção `sec-schedules`, passo do editor atualizado), README, preview regenerado, versão 1.5.177 e `installer.sha256`; num terminal pequeno, os filtros ficam um por linha.

## Decisões rotineiras

- A central lê os arquivos de `/etc/cron.d` diretamente, como o editor de hoje já faz; não foi preciso tarefa nova no instalador.
- Só os arquivos que o Koha.Nexus conhece entram (mais o `koha-common` do Koha); arquivos de terceiros em `/etc/cron.d` não são listados.
- A tecla **s** passa a abrir a central; o editor continua a um clique. A escolha de plataforma da Central de backups não é mais alterada quando se abre outra tela filtrada.
- Uma linha `@reboot` mostra "Na próxima inicialização" como próxima execução.

## Como foi validado

Simulado (modo demonstração do painel):
- `panel/tests/test_schedules.py` (novo, 29 testes): próxima execução seguindo o cron (diário, semanal, 7 = domingo, nomes, intervalos, passos, dia do mês OU dia da semana, `@daily`, `@reboot`, linhas inválidas e datas impossíveis); descrição em palavras; uma linha por linha do arquivo; presets não escritos ficam de fora; linha desligada; linha à mão preservada com a senha escondida; blocos; backups do Tainacan; arquivos do instalador; WP-Cron só com Tainacan; aviso de duplicação (e não para linha desligada); última execução só de registro; leitura da pasta ignorando arquivos de terceiros; filtros; a central nos 4 cenários (nenhuma, só Koha, só Tainacan, ambas) só lendo; o grupo Koha abrindo filtrado e o cartão abrindo o editor.
- `test_menus`, `test_platforms`, `test_tainacan_view`, `test_cron_view` ajustados ao novo lugar.
- Suíte completa do painel (Python 3.13): 960 passaram, 2 pulados; 4 falharam só sob carga (tempo de espera) e passaram ao rodar de novo sozinhos: `test_backup_view` (download do MARC), `test_loader` (animação), `test_routines` (busca) e `test_schedules` (atalho do grupo Koha, que agora espera o editor terminar de desenhar e passou 3 vezes seguidas).
- Subconjunto da CI em Python 3.9 (5 arquivos, com `test_schedules.py`): 138 passaram.
- Traduções: nenhum texto sem pt-BR; preview e manual conferidos (`export_docs_preview.py --check`).

CI: `platforms-panel.yml` passa a rodar `test_schedules.py` (Python 3.9 e 3.13).

Não testado em servidor real: a leitura dos arquivos de `/etc/cron.d` de um servidor de verdade e o fuso horário só foram exercitados com arquivos de teste; nenhum teste destrutivo foi feito no seu servidor.

## Capturas

Na pasta do projeto `estudo-ecossistema/v2/capturas-U3/`: os 4 cenários, a lista com as duas plataformas, o filtro de backups e o atalho do grupo Koha, em terminal pequeno (80x24) e grande (160x48).

