# Central de agendamentos com controles de edição

Versão 1.5.189, base `9bac7c0` (PR #359 mesclado).

A central agora permite ativar/desativar e editar os horários gerenciados,
com revisão e confirmação por tarefa. Continua usando os mesmos arquivos e
os mesmos gravadores dos editores existentes.

## Controles

- **Koha:** frequência diária, semanal, mensal ou personalizada, conforme a
  tarefa; dia e horário; tarefas de nuvem já existentes. Modifica apenas a
  linha escolhida, preservando as demais linhas, comentários e blocos manuais.
- **Tainacan:** um controle diário para o grupo de backup, manutenção semanal
  uma hora depois e teste mensal duas horas depois. Desativar desliga as três,
  mantendo repositório, destino e retenção.
- **Conjunto Koha + Tainacan:** ativação e horário diário sem refazer destino,
  retenção, escolha de segredos ou cópia na nuvem.
- **Planos DSpace e conjuntos explícitos:** ativação e horário diário. Membros,
  destino, retenção e nuvem ficam iguais. Desativar funciona mesmo sem acesso
  à chave, à nuvem ou ao destino.
- Os drivers de backup atuais suportam horário diário; a central não oferece
  frequências que seus gravadores não aceitam.
- Agendas configuradas e desativadas continuam visíveis. Se a configuração
  existir mas faltar sua entrada cron, o estado observado aparece desligado e
  pode ser reconciliado por Save, sem criar outra configuração paralela.

## Interface

O switch muda um rascunho; nada é gravado até Salvar e confirmar. Filtros
preservam as alterações ainda não salvas. A central mantém última/próxima
execução, fuso do servidor e editor original; os atalhos antigos ficam no fim.

Tarefas manuais, de pacotes, WP-Cron e manutenção vinculada não recebem
controles que reescrevam seus arquivos. Grupos com conteúdo cron ou ambiente
personalizado são somente leitura e encaminham ao editor original.

Capturas do painel em demonstração, sem operações no servidor real:

- [80×24](capturas/agendamentos-80x24.svg)
- [160×48](capturas/agendamentos-160x48.svg)

Durante a regressão completa também foi corrigido o seletor de plataformas
da Central de backups: os botões se distribuem em grade, mantendo “todos”
visível no terminal pequeno sem depender de rolagem horizontal.

## Integridade

Os gravadores Bash compartilham trava por arquivo. O salvamento da central
leva o SHA-256 da versão exibida: uma edição concorrente exige atualizar e
revisar. Os planos DSpace também conferem a configuração anterior sob sua
trava antes de substituir dados. Callbacks antigos da tela não podem escolher
outro controle após uma atualização.

Abrir, filtrar e mudar campos não executam backup, manutenção, restauração ou
edição de cron. A única ação de escrita é Salvar após confirmação.

## Verificação

- Testes de modelo, rascunho, cancelamento, salvamento via gravador, layout e
  filtros em 80×24 e 160×48, incluindo protocolo Tainacan com campos prefixados.
- Bats com os gravadores reais em Debian descartável como root: mudança de
  horário, preservação de tarefas manuais, configuração, revisão concorrente,
  remoção dos jobs vinculados e recusa de links simbólicos.
- 45 testes dos motores/conjuntos e 35 testes das operações DSpace aprovados
  no contêiner, incluindo os casos novos. Nenhum serviço real foi alterado.
- Suíte completa do painel em execução antes da publicação; registrar o
  resultado final junto ao commit. Testes da CI incluem o novo módulo de
  controles e os testes Bash em Ubuntu/Debian.
- Sem validação no servidor de Paulo nesta etapa.
