
Quarto PR da etapa T (especificação em `estudo-ecossistema/v2/T-backups-agendamentos-pos-instalacao.md`, seção 6, U4). Aponta para a `main`, já com o U3 dentro.

## O que muda

**Acesso administrativo** (um cartão no grupo Koha e um no grupo Tainacan):
- Koha: diz se o instalador da web foi concluído (pela existência de superbibliotecário). Oferece **Criar um superbibliotecário** (a rotina de hoje), **Trocar a senha de um superbibliotecário** e **Ver as credenciais de primeiro acesso**. A troca é feita pelo próprio Koha (`Koha::Patron->set_password`, com as regras de senha da categoria) e só para superbibliotecários.
- Tainacan: diz se a conta criada na instalação ainda tem a senha gerada. Oferece **Definir minha senha**: a gerada sai do `.env` e deixa de funcionar. Também **Trocar a senha de um administrador** e **Criar outro administrador**, que recusa nome ou e-mail que já pertencem a uma conta.
- A senha é digitada duas vezes em campo protegido e confirmada. Vai ao instalador só no ambiente daquela tarefa (`KEI_ADMIN_PASSWORD`), que a tira do ambiente antes de chamar qualquer programa e a entrega ao Koha ou ao WordPress pela entrada padrão. Nunca aparece em linha de comando, log, status, resultado ou tela depois.
- Nenhuma conta é criada, apagada ou alterada sem ser escolhida pelo nome. A chave de criptografia do Koha e as chaves e salts do WordPress não são tocadas.

**Assistente pós-instalação** (Próximos passos):
- 3 etapas: acesso administrativo, acesso público e backup. Cada uma tem **Configurar agora** ou **Fazer depois**. A etapa 4 diz onde fica cada coisa.
- Não tem configuração própria: cada etapa abre a tela de sempre (Acesso administrativo, Gerenciador do Túnel Cloudflare ou Endereço do Tainacan, Configurar backup na nuvem ou chave + Agendar backups do Tainacan). Assim nada é criado duas vezes.
- Uma etapa feita pelos menus conta como feita, porque o estado é recalculado pelo estado real.
- O arquivo de pendências (`/var/lib/koha-nexus/setup/<plataforma>.state`, pasta 700, arquivo 600) guarda só `feito`, `para depois` ou `pendente` por etapa, nunca parâmetros.
- Só uma instalação nova o cria:
  - Koha: quando a instalação termina sem superbibliotecário.
  - Tainacan: quando o WordPress foi criado agora.
- Atualizar o painel ou reinstalar sobre dados existentes nunca o inicia.
- Abre sozinho depois da instalação feita pelo painel. O cartão **Continuar a configuração** fica na tela da plataforma enquanto faltar etapa. No fim, quem tem etapa para depois escolhe entre manter o lembrete ou não lembrar de novo.

**Endereço do Tainacan** (cartão novo): manter, este servidor na rede local ou um domínio próprio, sempre com confirmação. Usa a tarefa `tainacan-address` de hoje, que agora aceita `local`. O U5 acrescenta o endereço gratuito do koha.nexus a esta mesma tela.

Também:
- `tainacan-credentials` diz que a senha é a sua e não fica guardada, depois que ela foi trocada;
- a mensagem do fim da instalação do Tainacan aponta para Acesso administrativo;
- traduções pt-BR, manual (en e pt-BR, 5 itens novos), README, preview regenerado;
- versão 1.5.178 e `installer.sha256`.

## Decisões rotineiras

- No Koha, a troca usa `set_password` do próprio Koha em vez de gravar o hash à mão: ele aplica as regras de senha da categoria e zera as tentativas de login. Uma senha recusada pelo Koha não muda nada.
- O cartão **Ver credenciais de primeiro acesso** do Koha continua onde estava; o Acesso administrativo também leva a ele.
- "Manter este endereço" no Endereço do Tainacan conta como etapa feita: é uma escolha. Um endereço que não é de rede local também conta.
- A etapa de backup do Koha é a nuvem, porque o backup local noturno já existe desde a instalação. A do Tainacan é a chave mais o agendamento diário.
- O assistente aparece só depois de instalar pelo painel ou pelo cartão Continuar a configuração. Instalações atuais não ganham nada ao atualizar.

## Como foi validado

Simulado (painel em modo demonstração):
- `panel/tests/test_admin_setup.py` (novo, 13 testes) cobre:
  - as opções por estado;
  - a senha só no ambiente da tarefa e nunca nos argumentos ou em tela;
  - nada roda com senhas diferentes, com Não, ao cancelar ou ao fechar;
  - campo curto recusado e só superbibliotecários listados;
  - outro administrador;
  - o assistente abrindo a rotina de cada tela;
  - Fazer depois só registra, e fechar não registra nada;
  - etapa feita não é perguntada de novo;
  - tudo feito encerra, e sem configuração em andamento não há assistente;
  - o cartão Continuar só com pendência.
- `test_tainacan_view` ajustado: os cartões novos, e `setup-status` como leitura da tela.
- Suíte completa do painel: 976 aprovados, 2 ignorados e 1 falha de tempo (`test_search_toggle_no_changes_nothing`: a tela de espera ainda estava aberta 0,5 s depois, com a máquina carregada). Esse teste é da troca de motor de busca, não toca o U4 e passa quando roda sozinho.
- `platforms-panel.yml` passa a rodar `test_admin_setup.py` também, em Python 3.9 e 3.13.

bats (instalador de verdade, Koha e WordPress simulados):
- `tests/admin_access.bats` (novo, 10 testes) cobre:
  - estado do instalador da web;
  - senha só pela entrada padrão, nunca em argumentos, log ou saída, e retirada do ambiente;
  - curta, com quebra de linha ou nome inválido recusados antes de qualquer coisa;
  - só superbibliotecários e administradores existentes;
  - regra de senha do Koha recusando;
  - conta inicial e `.env` (as chaves continuam);
  - outro administrador sem sobrescrever nome ou e-mail;
  - arquivo de pendências: só estados, 700/600, `begin` não reinicia, estado real marca feito, fechar apaga;
  - só as duas instalações novas criam pendências.
- Conferido que o teste pega vazamento: com a senha passada como argumento, A07 falha.
- `tainacan.bats`, `platforms.bats`, `backup_set.bats` continuam passando.

CI:
- `proxy.yml` roda `admin_access.bats`.
- `tests/tainacan_system.bats` ganhou um teste com o WordPress de verdade: senha própria sem aparecer em nenhuma linha de comando durante a troca (vigiando `/proc/*/cmdline`), `wp_check_password` confirmando, chaves do WordPress iguais, outro administrador, nome existente recusado, pendências criadas na instalação nova e não na reinstalação com os mesmos dados.

Não testado em servidor real: a troca de senha no Koha (`koha-shell` + `set_password`) só foi exercitada com o Koha simulado. Nenhum teste destrutivo foi feito no seu servidor.

## Capturas

Na pasta do projeto `estudo-ecossistema/v2/capturas-U4/`, em terminal pequeno (80x24) e grande (160x48):
- os grupos Koha e Tainacan com os cartões novos;
- o assistente do Koha e do Tainacan passo a passo;
- a senha protegida e a confirmação;
- o Endereço do Tainacan;
- os próximos passos e o lembrete;
- o acesso do Koha.

