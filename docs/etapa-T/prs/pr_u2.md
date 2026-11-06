
Segundo PR da etapa T (especificação em `estudo-ecossistema/v2/T-backups-agendamentos-pos-instalacao.md`, seção 6, U2). Aponta para a `main`, já com o U1 (#341) dentro.

## O que muda

**Backup conjunto (Koha + Tainacan)**, na Central de backups, com a opção **Koha e Tainacan** no seletor (só quando as duas estão instaladas):
- um único arquivo `knx-set-AAAAMMDD-HHMMSS.tar` com os **dados** de cada plataforma (nunca referências): o SQL do Koha feito pelo mesmo backup de segurança da restauração, e o pacote do Tainacan feito pelo motor de backups com a janela sem escritas, já com os arquivos dentro (ignora o repositório restic e não envia cópia para a nuvem nessa execução);
- `manifest.json` (tipo `koha-nexus-set`, formato 1, id, data, servidor, versão do painel) com, por plataforma: resultado, início e fim da captura, caminho, tamanho, sha256 e o que está criptografado; `SHA256SUMS` de todos os arquivos;
- cada plataforma é capturada na sua vez, com a sua cópia consistente; a tela e o manifesto dizem os dois intervalos e que **não** é o mesmo instante;
- falha parcial nunca vira "feito": o arquivo recebe `-partial` no nome, o manifesto diz `complete: false`, a tela mostra qual plataforma falhou e por quê, e explica como repetir; sem nenhuma parte válida, nenhum arquivo é gravado; sem espaço, nada fica para trás;
- o Koha vai além do banco (auditoria no documento `V-auditoria-backup-koha.md`):
  - `koha/files.tar.gz`: arquivos enviados (Upload e 856 $u), plugins, imagens próprias do OPAC e da equipe, regras MARC e perfis de importação do painel;
  - `koha/secrets.tar.gpg`: `koha-conf.xml` (por causa da `<encryption_key>`), `SIPconfig.xml`, logins de mensagens, IA e Z39.50 do painel. Só entra cifrado com a chave dos backups, nunca em claro;
- sem a chave dos backups, nada é gerado antes de a pessoa escolher:
  - configurar a chave agora;
  - ou gerar sem os segredos do Koha. A tela diz o efeito: o segredo do segundo fator da equipe e outras senhas cifradas pelo Koha não poderão ser lidos em outra instalação;
- um pacote sem os segredos fica marcado `data-only` no Koha e `partial` no conjunto. Nunca é chamado de completo. O manifesto lista o que nunca vai em pacote nenhum: `koha-common`, contas de nuvem, túnel ou endereço gratuito, índice de busca.

**Restauração assistida**, uma entrada só:
- reconhece pelo conteúdo, não pelo nome: backups do Koha de qualquer versão (`.sql`, `.gz`, `.xz`, `.zst`), pacote do Tainacan (pasta ou arquivo) e pacote conjunto;
- o arquivo é tratado como não confiável: antes de extrair, cada item do tar é conferido (caminhos absolutos ou com `..`, links, arquivos especiais, itens fora da lista permitida, tamanho total contra o espaço livre), o manifesto é validado contra o esquema e as somas são conferidas lendo o tar, sem extrair; nada do manifesto é executado (há teste com comandos no manifesto);
- antes de aplicar, mostra origem, data, plataformas, integridade, o que cada parte tem criptografado e os conflitos com este servidor; permite restaurar só o Koha, só o Tainacan ou os dois, e explica o efeito de restaurar sem a frase de recuperação;
- a extração vai para uma pasta privada (700) no diretório dos backups, sem donos nem permissões do arquivo, e é conferida de novo; daí chama as restaurações que já existiam (Koha: conferência, backup de segurança e as suas perguntas; Tainacan: teste numa cópia isolada, backup de segurança, frase de recuperação); a pasta temporária é apagada no fim;
- um backup danificado ou alterado nunca é aplicado;
- depois do banco do Koha, a restauração oferece **Arquivos e segredos do Koha**, sempre com um plano antes:
  - do `koha-conf.xml` só volta a `<encryption_key>`. Senha do banco, caminhos, Zebra e memcached do destino ficam. O arquivo anterior é guardado (600);
  - outro arquivo de segredo só entra quando o destino não tem o seu; se tiver, o do pacote fica ao lado como `.from-backup` (600);
  - antes de trocar, os arquivos substituídos vão para uma cópia de segurança;
  - nenhum valor aparece no plano, na tela ou no log;
  - a frase de recuperação vai só no ambiente;
  - num servidor novo, o painel oferece importar o kit de recuperação do servidor de origem.

Instalador: `kei_set_backup`, `kei_set_inspect`, `kei_set_unpack`, `kei_set_koha_extras`, `kei_set_cleanup` e as tarefas `set-backup`, `set-inspect`, `set-unpack`, `set-koha-extras`, `set-cleanup` (nenhuma delas exige o Koha). Painel: `routines/backup_set.py`. Também: o texto longo de uma escolha (o resumo do backup) rola num terminal pequeno, para as opções e o Voltar não sumirem; os botões de plataforma cabem em 80 colunas; traduções pt-BR; manual (en e pt-BR); preview regenerado; versão 1.5.176 e `installer.sha256`.

## Decisões rotineiras

- O pacote conjunto é um `.tar` sem compressão por fora: as partes já vêm comprimidas (SQL `.gz`, arquivos do Tainacan `.tar.gz`), e assim o `tar` pode ser lido item a item para validar antes de extrair.
- Para o Tainacan, o backup conjunto usa o mesmo motor do backup diário, mas grava os arquivos dentro do pacote mesmo com um repositório restic configurado: o pacote precisa ser transportável. O pacote fica também na lista de backups do Tainacan, com o rótulo `set`.
- O motivo de uma recusa vem do instalador já traduzido.
- O backup conjunto agendado é requisito (seções 3.5, 5 e 6 do documento T) e vem num PR separado (U6), reaproveitando esta mesma operação.

## Como foi validado

Simulado (modo demonstração, respostas simuladas do instalador):
- `panel/tests/test_backup_center.py` (18 testes): a opção Koha e Tainacan só com as duas plataformas; o resumo da inspeção; o backup conjunto (pasta, aviso de que não é simultâneo, resultado por plataforma); a restauração assistida para conjunto (só Tainacan, os dois), SQL do Koha e arquivo recusado, sempre pelas restaurações que já existiam e com a limpeza no fim.
- Suíte completa do painel: 933 testes passando localmente; 2 testes de tempo (`test_tools`, `test_transfer`), que não tocam o que mudou, falharam sob carga e passaram 3 vezes seguidas quando rodados sozinhos. O subconjunto da CI também passa em Python 3.9.

bats (instalador de verdade, Koha e Tainacan simulados):
- `tests/backup_set.bats` S01 a S11 (novo). Cobre:
  - conteúdo e horários;
  - conjunto parcial;
  - nada a gravar e falta de espaço;
  - reconhecimento pelo conteúdo;
  - extração e limpeza;
  - conjunto alterado recusado sem extrair;
  - tar malicioso: caminho para fora, link, item desconhecido, manifesto forjado com comandos que nunca rodam;
  - S08, segredos do Koha:
    - sem chave, rc 7 e nada capturado;
    - "sem segredos" vira `data-only`/`partial`;
    - com chave, `files.tar.gz` e `secrets.tar.gpg`;
    - nenhum valor legível no pacote nem dentro de `files.tar.gz`;
  - conflitos;
  - tarefas fora da lista do Koha;
  - S11, recuperação no destino:
    - o plano não mostra valores e não muda nada;
    - sem frase, com frase errada ou sem a chave neste servidor, os segredos não abrem;
    - aplicar exige confirmação;
    - só a `<encryption_key>` muda: a senha do banco e os caminhos do destino ficam, e as permissões também;
    - o SIP do destino fica, e o do pacote vai ao lado;
    - um segredo ausente no destino é acrescentado (600);
    - cópia de segurança dos arquivos.
- Conferido que o S11 pega erro: copiar o `koha-conf.xml` inteiro do pacote, ou mostrar o conteúdo de um segredo no plano, faz o teste falhar.
- Segundo commit: as verificações negativas do `backup_set.bats` passam a falhar o teste de verdade (um `! comando` solto no meio de um teste do bats não falha).
- `backup_engine.bats`, `cloud_test.bats` e `platforms.bats` continuam passando.

Painel, também: a escolha sem chave antes de gerar (as três respostas), o resultado "não recuperável por completo", e o plano dos arquivos e segredos (frase só no ambiente, nada aplicado sem o Sim).

CI (configurado, ainda não aprovado até rodar aqui):
- `proxy.yml`, job novo `koha-set` (Debian 12, terceiro commit). Usa um Koha de verdade (`koha-common` do repositório oficial) e um Tainacan de verdade. O teste:
  - cria um leitor com segredo de segundo fator cifrado pelo Koha, um arquivo enviado, um plugin e logins de SIP2;
  - gera o pacote conjunto (completo, segredos só cifrados);
  - apaga a instância e cria de novo, com outra chave e outra senha de banco;
  - restaura só o Koha a partir do conjunto e confere que o segredo ainda não abre;
  - confere que o plano não mostra valores;
  - aplica o plano e confere que só a `<encryption_key>` mudou no `koha-conf.xml`, que o segredo abre de novo e que o arquivo e o plugin voltaram;
  - restaura o Tainacan à parte.
  
  O log lista onde o Koha instalado usa `Koha::Encryption`. Não rodou aqui: este ambiente não alcança o repositório do Koha nem tem Docker.
- `proxy.yml` job `apache`: passa a rodar `backup_set.bats` em Ubuntu 24.04, Debian 12 e 13.
- `proxy.yml` job `engine`: novo teste em `backup_engine_system.bats` com o Tainacan de verdade: o pacote conjunto feito com repositório restic e cópia na nuvem configurados (os arquivos vão dentro, nada é enviado), a janela sem escritas no diário, a inspeção sem extrair, a extração, a restauração numa cópia isolada sem tocar o Tainacan em uso, a limpeza, e o Apache do Koha como antes.

Não testado em servidor real: nenhum teste destrutivo foi feito no seu servidor; a restauração conjunta só foi exercitada com as restaurações simuladas no painel e, no Tainacan, com a restauração isolada da CI.

## Capturas

Na pasta do projeto `estudo-ecossistema/v2/capturas-U2/`: a central com Koha e Tainacan, o backup conjunto (confirmação, resultado, parcial), a restauração assistida (escolha, resumo) e um arquivo recusado, em terminal pequeno (80x24) e grande (160x48).

