
Quinto e último PR da etapa T (especificação em `estudo-ecossistema/v2/T-backups-agendamentos-pos-instalacao.md`, seção 6, U5). Aponta para a `main`, já com o U4 dentro.

**Nada disto entra em produção sozinho.** O serviço de endereços (`broker/`) não foi publicado e a migração do banco não foi aplicada. Enquanto você não fizer o passo a passo abaixo, o painel mostra a opção nova como indisponível e diz o motivo.

## O que muda

**Serviço de endereços (`broker/`)**
- Cada biblioteca passa a ter serviços: `koha`, `tainacan` ou os dois.
- Com `tainacan`, ela publica mais um nome, `<biblioteca>-acervo`, no mesmo túnel, apontando para o Apache do servidor na porta 80.
- Uma biblioteca com Koha liga ou desliga esse nome com `PUT /v1/services`.
- Um servidor sem Koha pede um endereço só do acervo (`"services":["tainacan"]` no `device/start`). Não ganha nome de OPAC, de equipe nem de lista pública.
- `GET /v1/capabilities` diz o que aquela publicação oferece. Assim um instalador diante do serviço antigo explica o motivo em vez de falhar.
- Desligar o acervo apaga só o registro nosso daquele nome. Registro de outra pessoa nunca é tocado.
- A migração `0003_services.sql` só acrescenta colunas. Toda biblioteca existente fica como `koha`, sem nenhuma mudança.
- Lista pública e acesso remoto da equipe recusam (409) biblioteca sem Koha.

**Instalador**
- Novas funções `kei_tainacan_free_*` e tarefas `tainacan-free-status` e `tainacan-free on|off`.
- Quando o endereço não pode ser dado agora, diz por quê e não muda nada:
  - o serviço não está no ar;
  - o serviço ainda não oferece endereços para acervos;
  - o Koha usa domínio próprio;
  - o Koha ainda não tem endereço gratuito.
- Com o Koha num endereço gratuito: mostra o nome que o acervo vai ganhar, pede um Sim e então pede o nome ao serviço.
- Num servidor sem Koha: é o mesmo pedido do catálogo, só para o acervo. O token fica no arquivo 600, nunca em linha de comando ou tela.
- Deixar de usar o endereço gratuito leva o Tainacan de volta à rede local, sempre depois de um Sim:
  - com Koha, o catálogo continua com o endereço dele;
  - sem Koha, o endereço é devolvido.
- Abrir mão do endereço gratuito do catálogo também traz o acervo de volta à rede local.
- O arquivo de recuperação leva o nome do acervo.

**Painel**
- O cartão **Endereço do Tainacan** ganha **Endereço gratuito do koha.nexus**, ou **Deixar de usar** quando já está em uso. Quando indisponível, a opção diz "(indisponível agora)" e mostra o motivo.
- A instalação do Tainacan pergunta onde o acervo vai responder: rede local, domínio próprio, endereço gratuito ou decidir depois. O endereço gratuito é feito logo depois da instalação.
- A etapa de acesso público do assistente abre essa mesma tela.

Também:
- traduções pt-BR;
- manual (item `tainacan-address`, en e pt-BR);
- README e README do `broker/`;
- preview regenerado;
- versão 1.5.179 e `installer.sha256`.

## Como publicar o serviço (passo seu)

Na pasta `broker/`, com o seu `wrangler login` (também está no README do `broker/`):
1. `npm ci && npx tsc --noEmit && npx vitest run && npm run test:e2e`
2. `npm run db:migrate`. Só acrescenta colunas, então o Worker que está no ar continua funcionando antes e depois.
3. Confira `TAINACAN_SUFFIX = "-acervo"` no `wrangler.toml` e rode `npm run deploy`.
4. `curl -s https://broker.koha.nexus/v1/capabilities` deve responder `{"services":["koha","tainacan"],"collection_suffix":"-acervo"}`.
5. Para desfazer, publique a versão anterior. As colunas ficam e são ignoradas.

## Decisões rotineiras

- **Nome do acervo:** o sufixo é `-acervo` (configurável). O tamanho máximo do nome da biblioteca agora considera o sufixo mais longo, e um nome terminado em `-acervo` é recusado para não colidir.
- **Koha sem endereço gratuito:** o painel pede para obter primeiro o endereço do catálogo. Não cria um segundo túnel nem troca o domínio próprio do Koha, porque o servidor tem um só serviço do cloudflared.
- **Lista pública e acesso remoto da equipe** continuam sendo só do catálogo.
- **"Decidir depois" na instalação** deixa a etapa de acesso público pendente no assistente. "Rede local" e "domínio" contam como feita.
- **Workflow novo `broker.yml`:** roda tipos, testes de unidade e ponta a ponta do serviço. Não publica nada.

## Como foi validado

Simulado:
- `broker/` com vitest (68 testes, 8 novos em `test/services.test.ts`). Cobre:
  - nomes com o sufixo;
  - os registros por serviço;
  - ligar e desligar sem tocar registro alheio;
  - 409 sem serviço e com nome longo demais;
  - capacidades.
- `npm run test:e2e` com o Worker de verdade em workerd local (24 verificações). Cobre:
  - biblioteca só de acervo;
  - biblioteca do Koha acrescentando e tirando o acervo;
  - suspensão.
- `tests/tainacan_free.bats` (novo, 9 testes), com o instalador de verdade diante de um serviço simulado (`tests/lib/fake_broker.py`). Cobre:
  - serviço antigo, fora do ar e Koha sem endereço não mudam nada nem perguntam nada ao serviço;
  - Não não muda nada;
  - com Koha, o nome é acrescentado e retirado sem tocar o catálogo nem o túnel;
  - abrir mão do endereço do catálogo traz o acervo de volta;
  - servidor sem Koha: pedido só do acervo, token fora de tela, log e linha de comando, nada do Koha e nada de lista pública;
  - arquivo de recuperação;
  - devolução.
- Conferido que o teste pega erro: tirar `services` do pedido, ou perguntar sobre a lista pública sem Koha, faz o F06 falhar.
- `panel/tests/test_tainacan_free.py` (novo, 9 testes). Cobre:
  - as opções por estado;
  - o motivo quando indisponível, sem rodar nada;
  - deixar de usar;
  - instalador antigo sem a opção;
  - domínio só com confirmação;
  - a pergunta da instalação nas quatro escolhas.
- `test_platforms` ajustado para a pergunta nova da instalação.
- Suíte completa do painel: 986 aprovados e 2 ignorados, nenhuma falha. O conjunto da CI também passa em Python 3.9 (160 testes).
- bats `admin_access`, `tainacan`, `platforms` e `backup_set` continuam passando.

CI:
- `proxy.yml` roda `tainacan_free.bats`;
- `platforms-panel.yml` roda `test_tainacan_free.py` em Python 3.9 e 3.13;
- `broker.yml` é novo.

Não testado em servidor real: nada do U5. O serviço de endereços de produção não foi tocado.

## Capturas

Na pasta do projeto `estudo-ecossistema/v2/capturas-U5/`, em terminal pequeno (80x24) e grande (160x48):
- as opções do Endereço do Tainacan;
- a confirmação e o acervo no ar;
- a opção indisponível com o motivo;
- deixar de usar;
- a pergunta na instalação.

