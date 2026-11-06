
Sexto PR da etapa T: o backup conjunto agendado. Ele é requisito do pedido original (seções 3.5, 5 e 6 do documento T) e vem à parte, como você pediu em 06/11 às 15:26. Aponta para a `main`, já com o U5 dentro.

## O que muda

**Instalador**
- `kei_set_schedule time=HH:MM|off [dest=PASTA] [keep=N] [copy=REMOTO:CAMINHO|none] [secrets=yes|no]` escreve uma linha em `/etc/cron.d/koha-nexus-backup-sets`.
  - Só escreve quando a pessoa agenda. Atualizar o painel nunca cria esse arquivo.
  - O arquivo fica registrado no `owned.tsv` para o Koha e para o Tainacan.
  - Agendar de novo troca a linha. Nunca há duas.
  - Desligar apaga o arquivo e mantém os pacotes.
  - O cron é instalado se faltar, como no backup das plataformas.
- `kei_set_run` faz o mesmo `kei_set_backup` do backup manual:
  - bloqueio próprio: uma execução que encontra outra em andamento é pulada e registrada como `busy`;
  - uma linha por execução em `sets-history.jsonl` (600), com início, fim, resultado (`ok`, `partial`, `failed`, `busy`), arquivo, recuperabilidade, resultado e erro de cada plataforma, cópia e quantos pacotes saíram;
  - retenção: guarda os N pacotes completos mais novos **deste agendamento**. Só apaga depois de um pacote completo, nunca depois de uma falha, e nunca toca um pacote feito à mão;
  - nuvem: o pacote inteiro, cifrado com a chave dos backups (`.tar.gpg`), porque o dump do Koha tem dados pessoais e senhas. Sem a chave, a nuvem é recusada ao agendar (rc 6). Se a chave sumir depois, a execução falha e nada sobe;
  - sem a chave dos backups, a escolha é a mesma do backup manual: configurar a chave, ou agendar um pacote só com os dados do Koha (`secrets=no`, registrado).
- Novas tarefas: `set-schedule`, `set-schedule-status` (só leitura) e `set-run`.

**Painel**
- **Agendar o backup conjunto** aparece:
  - na Central de backups, em Koha e Tainacan;
  - em Agendamentos, só com as duas plataformas instaladas.
- A rotina pergunta, nesta ordem:
  1. a escolha sem chave, quando for o caso;
  2. a pasta;
  3. o horário;
  4. quantos pacotes guardar;
  5. a cópia na nuvem, só com chave.
  
  Depois mostra o resumo e pede um Sim.
- A linha **Backup conjunto (Koha + Tainacan)** aparece:
  - na Central de backups: destino, horário, retenção, o que está cifrado e a última execução tirada do histórico;
  - na Central de agendamentos: aparece no filtro Koha e no filtro Tainacan, com a última execução, ou "Sem registro" quando não há histórico.

Também:
- traduções pt-BR;
- manual (item `set-schedule`, en e pt-BR);
- preview regenerado;
- versão 1.5.180 e `installer.sha256`.

## Decisões rotineiras

- A configuração fica no arquivo de configuração da chave dos backups (`set_*`), e não num `sets.conf` à parte. Assim o kit de recuperação e o status leem do mesmo lugar.
- A retenção conta pacotes, não dias, porque um pacote conjunto é grande. O padrão é 7.
- O teste com Koha e Tainacan reais (job `koha-set`) ganha mais um passo: agendar, rodar o que o cron rodaria, conferir o histórico (as duas plataformas `ok`, `full`) e desligar.

## Como foi validado

Simulado:
- `tests/backup_set.bats`, com o instalador de verdade e as plataformas simuladas, S12 a S15:
  - nada é escrito antes de agendar;
  - sem chave, a pessoa escolhe;
  - entradas inválidas são recusadas;
  - nuvem sem chave é recusada;
  - nunca duas linhas;
  - registro no `owned.tsv`;
  - desligar mantém os pacotes;
  - três execuções com retenção 2 apagam só o pacote agendado mais antigo, nunca o feito à mão;
  - histórico por plataforma;
  - falha parcial sem apagar nada;
  - falha total;
  - execução concorrente pulada;
  - nuvem só `.tar.gpg`, sem nenhum valor legível;
  - chave perdida: falha e nada sobe.
- `panel/tests/test_backup_center.py` e `test_schedules.py`:
  - a rotina inteira, com os argumentos exatos;
  - a linha nas duas centrais;
  - "só dados" e "Sem registro";
  - a última execução: OK, incompleta, cópia na nuvem com falha, pulada.
- `test_admin_setup.py`: domínio, contas, nuvem e agendamentos continuam no menu depois de concluir ou adiar o assistente, e também sem assistente.
- `backup_set.bats` 15 de 15. Suíte completa do painel: 993 aprovados, 2 ignorados e 1 falha de tempo de tela (`test_tools`), que não toca o que mudou e passou 3 vezes seguidas sozinha.

## Capturas

Na pasta do projeto `estudo-ecossistema/v2/capturas-U6/`, em terminal pequeno e grande:
- a escolha sem chave e o resultado "só dados";
- o resultado completo;
- a central com Koha e Tainacan;
- a frase oculta e o plano dos segredos;
- o agendamento passo a passo;
- a central de agendamentos.

CI (configurado, ainda não aprovado até rodar aqui):
- `koha-set` com o passo do agendamento;
- `apache` com `backup_set.bats`;
- `platforms-panel` com os testes do painel.

Não testado em servidor real: nada do U6.

