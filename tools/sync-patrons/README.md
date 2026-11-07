# Sincronização de alunos a partir de ERP acadêmico (`sync_patrons.py`)

Ferramenta de linha de comando que lê o CSV exportado pelo ERP da instituição
(Totvs, SIGAA, Lyceum ou outro) e atualiza os leitores do Koha pela **API REST
oficial** (`/api/v1/patrons`). Não altera arquivos nem tabelas do Koha, não
precisa de módulos extras (só Python 3.8+ padrão) e pode rodar pelo cron.

## O que ela faz, linha por linha

| Situação do aluno no CSV | Leitor no Koha | Resultado |
| --- | --- | --- |
| Ativo | não existe | **cria** o leitor (matrícula, nome, e-mail, categoria, biblioteca) |
| Ativo | existe | **atualiza** nome, e-mail e categoria se mudaram |
| Trancado, Transferido ou Evadido | existe | **bloqueia** empréstimos (`restricted`) se ainda não estiver bloqueado |
| Trancado, Transferido ou Evadido | não existe | **ignora** (não cria leitor inativo) |
| Linha inválida (matrícula vazia, situação desconhecida, e-mail inválido, matrícula repetida) | — | **ignora a linha** e registra o motivo |

Regras de segurança:

- **Dry-run por padrão.** Sem `--apply`, nada é gravado: o programa mostra e
  registra o plano completo.
- **Nunca desbloqueia.** Um leitor bloqueado (por aluno inativo ou por ato da
  biblioteca) continua bloqueado; desfazer é decisão manual do bibliotecário.
- **Nunca apaga** leitor, empréstimo, multa ou item.
- **Só olha os alunos do CSV.** Quem sumiu do arquivo não é tocado. Isso evita
  que um CSV incompleto bloqueie a escola inteira.
- **Trava contra massa de bloqueios.** Se o plano bloquear mais leitores do
  que `max_restrictions` (padrão 50), a execução aborta **antes de gravar
  qualquer coisa**. Se o número estiver certo, use `--max-restrictions N`.
- **Trava de execução.** Duas execuções ao mesmo tempo não rodam juntas.
- **Log de cada alteração**, com a linha do CSV, a ação e os campos gravados.
- **Credenciais fora do repositório**: vêm de variáveis de ambiente.

## Arquivos

| Arquivo no repositório | Função |
| --- | --- |
| `sync_patrons.py` | o programa |
| `config.example.json` | modelo da configuração (URL, biblioteca, categorias, limites, logs) |
| `sync-patrons.env.example` | modelo do arquivo com as credenciais da API |
| `alunos-exemplo.csv` | CSV de exemplo com as cinco colunas e os quatro estados |
| `cron.example` | exemplo de rotina diária no cron do Linux |
| `tests/test_sync_patrons.py` | testes com mocks (sem Koha) |

## Formato do CSV

Cinco colunas, **com estes nomes** no cabeçalho (sem acento, sem espaço):

| Coluna | Exemplo | Observação |
| --- | --- | --- |
| `matricula` | `2024001` | vira o número de cartão (`cardnumber`) do leitor |
| `nome` | `Ana Clara Souza` | grava o nome completo no sobrenome (campo `surname`) |
| `email` | `ana@aluno.exemplo.edu.br` | pode ficar vazio |
| `curso` | `Engenharia Civil` | procurado na tabela `category_map` da configuração |
| `situacao` | `Ativo` | um de: `Ativo`, `Trancado`, `Transferido`, `Evadido` (sem diferença entre maiúsculas e minúsculas) |

Aceitos: separador `;`, `,` ou TAB; codificação UTF-8 (com ou sem BOM) ou
Windows-1252. Veja `alunos-exemplo.csv`.

Se o ERP usa outros nomes de coluna, renomeie no cabeçalho da exportação
(ou ajuste o gerador do arquivo). O programa recusa o arquivo se faltar
alguma das cinco colunas e diz qual.

## Passo a passo de instalação (Linux, como root)

Os caminhos abaixo são os recomendados. Ajuste se a sua instalação for diferente.

**1. Copiar a ferramenta**

```sh
sudo install -d -m 755 /usr/local/share/koha-nexus/sync-patrons
sudo cp tools/sync-patrons/sync_patrons.py /usr/local/share/koha-nexus/sync-patrons/
sudo chown root:root /usr/local/share/koha-nexus/sync-patrons/sync_patrons.py
sudo chmod 755 /usr/local/share/koha-nexus/sync-patrons/sync_patrons.py
```

**2. Credenciais da API** (usuário criado só para isso no Koha)

```sh
sudo install -d -m 750 -o root -g koha-nexus /etc/koha-nexus
sudo cp tools/sync-patrons/sync-patrons.env.example /etc/koha-nexus/sync-patrons.env
sudo nano /etc/koha-nexus/sync-patrons.env      # preencha URL, usuário e senha
sudo chown root:koha-nexus /etc/koha-nexus/sync-patrons.env
sudo chmod 640 /etc/koha-nexus/sync-patrons.env
```

O usuário `koha-nexus` é o do sistema que roda o cron (ajuste o nome se for outro).
Sem permissão de leitura para ele, o cron falha ao ler o arquivo.

**3. Configuração da instituição**

```sh
sudo cp tools/sync-patrons/config.example.json /etc/koha-nexus/sync-patrons.json
sudo nano /etc/koha-nexus/sync-patrons.json     # library_id, categorias e cursos
sudo chown root:koha-nexus /etc/koha-nexus/sync-patrons.json
sudo chmod 640 /etc/koha-nexus/sync-patrons.json
```

Campos:

- `koha_url`: endereço do Koha (pode vir de `KOHA_URL` no arquivo de ambiente).
- `library_id`: código da biblioteca onde os alunos são cadastrados (o código
  que aparece em Administração > Bibliotecas).
- `default_category_id`: categoria para cursos sem mapeamento (só usada na
  criação; na atualização um curso sem mapeamento não muda a categoria).
- `category_map`: curso do ERP -> código da categoria do Koha. Compara sem
  diferença de maiúsculas e acento.
- `max_restrictions`: limite de bloqueios por execução.
- `log_file` e `lock_file`: onde gravar o log e a trava.

**4. Pastas de trabalho**

```sh
sudo install -d -m 755 -o koha-nexus -g koha-nexus /var/log/koha-nexus
sudo install -d -m 755 -o koha-nexus -g koha-nexus /var/lib/koha-nexus/erp
```

O ERP (ou um script de cópia) deve gravar o CSV em
`/var/lib/koha-nexus/erp/alunos.csv`, com dono `koha-nexus`.

**5. Pré-requisitos no Koha**

- Autenticação Basic da API ativa: preferência de sistema `RESTBasicAuth` = `Allow`.
- O usuário da API precisa de permissão para gerenciar leitores
  (`borrowers`, em Administração > Permissões).
- A categoria e a biblioteca citadas na configuração precisam existir.

## Como usar

Use sempre o dry-run primeiro. Ele só lê o Koha e mostra o que faria.

```sh
# 1) Dry-run: não grava nada (padrão)
sudo -u koha-nexus sh -c 'set -a; . /etc/koha-nexus/sync-patrons.env; set +a; \
  python3 /usr/local/share/koha-nexus/sync-patrons/sync_patrons.py \
  /var/lib/koha-nexus/erp/alunos.csv -c /etc/koha-nexus/sync-patrons.json'

# 2) Aplicar de verdade
sudo -u koha-nexus sh -c 'set -a; . /etc/koha-nexus/sync-patrons.env; set +a; \
  python3 /usr/local/share/koha-nexus/sync-patrons/sync_patrons.py \
  /var/lib/koha-nexus/erp/alunos.csv -c /etc/koha-nexus/sync-patrons.json --apply'

# 3) Se o plano bloquear mais que o limite e você confirmou que está certo
#    ... --apply --max-restrictions 120
```

Opções:

| Opção | Efeito |
| --- | --- |
| `--apply` | grava no Koha (sem ela, só dry-run) |
| `--max-restrictions N` | limite de bloqueios desta execução (sobrepõe a configuração) |
| `-v`, `--verbose` | mostra mensagens de depuração |

Códigos de saída: `0` tudo certo; `1` houve linhas inválidas, erro em alguma
gravação ou o limite de bloqueios foi atingido; `2` configuração, CSV ou
credencial inválidos (nada foi executado); `3` a API do Koha não respondeu
ou recusou a autenticação.

Log: cada execução grava em `log_file` (padrão
`/var/log/koha-nexus/sync-patrons.log`) e também na saída de erro. Exemplo:

```
2026-11-07 05:30:02 INFO início: alunos.csv, 6 linhas válidas, modo APLICAR
2026-11-07 05:30:03 INFO OK CRIAR leitor 2025009 (Fábio Nunes) {...}
2026-11-07 05:30:03 INFO OK ATUALIZAR leitor 2024002 {'restricted': True}
2026-11-07 05:30:03 ERROR linha 5 (2021530) ignorada: situação desconhecida 'Formado' ...
2026-11-07 05:30:04 INFO fim (APLICAR): criar=2 atualizar=1 sem mudança=3 ignorados=0 bloqueios=1 erros_csv=1 erros_api=0
```

## Agendamento diário (cron)

Veja `tools/sync-patrons/cron.example`. Copie para `/etc/cron.d/koha-nexus-sync-patrons`
(sem a extensão `.example`) e ajuste os caminhos. Só ative o cron depois de
rodar o dry-run e conferir o plano.

```sh
sudo cp tools/sync-patrons/cron.example /etc/cron.d/koha-nexus-sync-patrons
sudo chmod 644 /etc/cron.d/koha-nexus-sync-patrons
```

## Testes

Os testes usam mocks e um servidor HTTP local que imita a API. Não precisam de Koha:

```sh
python3 tools/sync-patrons/tests/test_sync_patrons.py
```

O que os testes cobrem: leitura e validação do CSV (separadores, BOM, linhas
inválidas, matrícula repetida, coluna faltando); todas as regras de decisão
(criar, atualizar, bloquear, não desbloquear, não criar inativo, categoria
não mapeada); dry-run sem gravação; a trava de bloqueios em massa; a
continuidade após erro em uma linha; credenciais ausentes; e o formato real
das requisições (Basic auth, parâmetro `q` com `cardnumber`, corpo JSON).

## O que ainda precisa de Koha real

Os testes **não** falam com um Koha de verdade. Antes de usar em produção,
faça estes testes numa cópia de teste do Koha:

1. Autenticação Basic com o usuário da API e permissão de `borrowers`.
2. A busca `GET /api/v1/patrons?q={"cardnumber":...}` devolve o leitor exato.
3. A criação (`POST`) aceita o corpo enviado, em especial `category_id` e
   `library_id` com os códigos reais da sua instituição.
4. O bloqueio: confirmar que `PUT` com `restricted: true` impede empréstimo
   no seu Koha (na versão em uso o campo pode aparecer com outro nome; o
   programa avisa no log quando o campo não vem na resposta).
5. Nomes com acento e caracteres especiais chegam corretamente ao Koha.

## Limitações conhecidas

- Não reativa leitores: quando o aluno volta a ficar Ativo, o bloqueio
  precisa ser retirado pelo bibliotecário no Koha. Se a escola quiser o
  desbloqueio automático, é uma mudança a acrescentar com regra própria.
- O sobrenome recebe o nome completo; o primeiro nome fica vazio. Se a
  instituição preferir separar, ajuste `plan_row` em `sync_patrons.py`.
- Uma consulta à API por linha do CSV: para dezenas de milhares de alunos,
  o tempo de execução cresce; nesse caso, rode por turnos.
