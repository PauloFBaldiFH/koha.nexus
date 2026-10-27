# Z39 Atlas 2.0 — descoberta bibliográfica com fontes públicas

Ferramenta independente para **descobrir metadados de endpoints Z39.50 publicados**, cruzar evidências, importar resultados do antigo Z39.50 Explorer, retomar o trabalho em SQLite e **confirmar recuperação real de registros MARC ISO 2709** em servidores expressamente autorizados para teste.

> **Escopo:** não executa varredura indiscriminada de IPs, sondagens de portas em terceiros, quebra de autenticação, tentativa de senhas ou bypass de firewall. Parâmetros técnicos incompletos (porta/base) podem ser complementados por opções convencionais **somente em hosts explicitamente autorizados**. Não pode descobrir servidores deliberadamente privados nem garantir cobertura de toda a internet.

## Dependências

- Ubuntu ou Debian, Python 3.10+, SQLite (embutido), `yaz-client` para validar MARC.
- Para *descoberta passiva* e importação CSV, só a biblioteca padrão do Python.
- Opcional: uma chave própria da [Brave Search API](https://api.search.brave.com/) para obter URLs de documentos públicos automaticamente. A ferramenta não disponibiliza nem obtém essa chave.

```bash
sudo apt update
sudo apt install -y python3 yaz
unzip z39-atlas-2.0.zip
cd z39-atlas
python3 -m unittest discover -s tests -v
# opcional: sudo ./install.sh  # não inicia nada automaticamente
```

**Não é necessário remover ou modificar o antigo `z39-explorer.service`.** O Atlas cria seu próprio banco. Por padrão não liga nem altera serviços nem redes.

## 1 — Aproveitar as descobertas que você já tem

O Explorer anterior salvou seus relatórios em `/var/lib/z39-explorer/reports/`. Importe-os sem alterar os originais. O pacote também traz `data/legacy-confirmed-2026-10-27.csv`, com as suas 116 linhas anteriores (111 configurações após deduplicação):

```bash
python3 z39atlas.py --db ./atlas.sqlite3 import-csv /var/lib/z39-explorer/reports/todos_candidatos.csv
python3 z39atlas.py --db ./atlas.sqlite3 stats
# Alternativa para começar já com as 116 linhas que você enviou:
# python3 z39atlas.py --db ./atlas.sqlite3 import-csv data/legacy-confirmed-2026-10-27.csv
```

Se esse CSV estiver restrito ao usuário do antigo serviço, faça uma **cópia autorizada e somente leitura** para sua conta, preservando o arquivo original:

```bash
sudo cp /var/lib/z39-explorer/reports/todos_candidatos.csv ./candidatos-anteriores.csv
sudo chown "$USER":"$(id -gn)" ./candidatos-anteriores.csv
python3 z39atlas.py --db ./atlas.sqlite3 import-csv ./candidatos-anteriores.csv
```

As classificações anteriores são importadas **como evidência histórica da fonte**, não como nova validação. O Atlas só marca `marc_*` depois de recuperar dados ISO 2709 em sua própria execução.

## 2 — Descobrir endpoints na documentação pública (modo passivo)

```bash
python3 z39atlas.py --db ./atlas.sqlite3 harvest --max-pages 60 --delay 3
python3 z39atlas.py --db ./atlas.sqlite3 stats
```

Fontes iniciais: páginas públicas da comunidade Koha, Z-BRARY (índice A–Z), IRSpy e páginas institucionais selecionadas. Respeita robots.txt e limita o tamanho das páginas. Pode também analisar **URLs HTTPS de documentação** selecionadas pelo operador:

```bash
printf '%s\n' \
  'https://www.loc.gov/standards/z3950/lcserver.html' \
  'https://decti.bu.ufsc.br/catalogacao/dados-abertos/' \
  > public-docs.txt
python3 z39atlas.py --db ./atlas.sqlite3 harvest --no-defaults \
  --urls-file public-docs.txt --max-pages 10
```

`--follow-links` expande somente links HTTPS **dentro dos domínios das fontes fornecidas**, com limite de páginas e acesso respeitoso; use apenas com domínios que permitam coleta automatizada.

### Opcional — pesquisar documentação por mecanismos de busca

Se você possui acesso à API oficial do Brave Search, a ferramenta pode descobrir páginas de documentação pelo índice do buscador, inclusive domínios `.br`:

```bash
export BRAVE_SEARCH_API_KEY='SUA_CHAVE_DA_API'
python3 z39atlas.py search-docs --output public-docs.txt
# revise public-docs.txt; a lista pode conter páginas irrelevantes
python3 z39atlas.py --db ./atlas.sqlite3 harvest --no-defaults \
  --urls-file public-docs.txt --max-pages 30 --delay 3
unset BRAVE_SEARCH_API_KEY
```

**Importante:** não cole sua chave aqui, não a coloque em um repositório e use um gerenciador de segredos/variável de ambiente no servidor.

## 3 — Validar MARC em servidores permitidos

Coloque em `allowed-hosts.txt` **somente hosts para os quais você tem autorização de realizar consultas**. Um host por linha, sem porta ou URL. A inclusão manual é deliberada: documentos encontrados não são automaticamente autorizados para sondagem ativa.

Exemplo de formato (substitua por hosts efetivamente autorizados):

```text
# allowed-hosts.txt — modelos; valide as permissões da instituição
z3950.ufsc.br
lx2.loc.gov
```

```bash
python3 z39atlas.py --db ./atlas.sqlite3 probe \
  --allowlist allowed-hosts.txt --ack-authorized \
  --workers 2 --timeout 25 --host-interval 10 \
  --max-hours 24 --recheck-hours 168
```

O Atlas chama o **YAZ** com até duas buscas pequenas por título e solicita um único registro de cada busca. Sua conclusão positiva exige um registro ISO2709 com líder, diretório e terminadores coerentes, e não apenas `InitializeResponse` ou respostas de busca.

Quando um *host que você está autorizado a consultar* aparece incompleto na documentação, você pode testar uma **lista limitada de convenções** (`porta 210`; `Default`, `innopac`, `voyager`) assim:

```bash
python3 z39atlas.py --db ./atlas.sqlite3 probe \
  --allowlist allowed-hosts.txt --ack-authorized --infer-missing \
  --workers 2 --host-interval 10
```

Isso **não testa nomes de usuário nem senhas**, não descobre IPs vizinhos e não tenta contornar restrições de acesso.

### Controle de carga, longa duração e retomada

- Máximo de 4 tarefas simultâneas e 1 tarefa de cada vez por host.
- Intervalo mínimo de 5 segundos entre acessos ao mesmo host; padrão 10 segundos.
- Máximo de 2 consultas pequenas por configuração, com no máximo um `show 1` por consulta.
- Tempo máximo por processo YAZ configurável de 5 a 120 segundos; padrão 25 segundos.
- Banco SQLite atualizado **a cada alvo**; uma interrupção permite retomar sem repetir verificações recentes.
- `--max-hours 24` é teto de programação de novos alvos; processos já iniciados podem levar até seu próprio timeout.
- `--recheck-hours 168` evita retestar alvos verificados nos últimos sete dias.
- Nenhuma opção habilita varredura ampla de IPs, força bruta ou coleta em massa de catálogos.

Se pretende ficar dias **monitorando apenas seus alvos autorizados**, programe uma execução diária por `systemd timer` ou cron; o `--recheck-hours` mantém os testes espaçados.

## 4 — Relatórios exportáveis para revisão e Koha

```bash
python3 z39atlas.py --db ./atlas.sqlite3 export --output ./todos.csv
python3 z39atlas.py --db ./atlas.sqlite3 export \
  --confirmed-only --output ./marc-confirmados.csv
python3 z39atlas.py --db ./atlas.sqlite3 stats
```

O CSV traz: `name,host,port,database,status,hits,marc_type,marc_bytes,latency_ms,checked_at,error,sources`.

**Atenção:** `hits` é a contagem da consulta de teste, não o número total de obras no catálogo. `marc_bibliographic` e `marc_authority` indicam somente que houve recuperação MARC estruturalmente válida. Revise manualmente MARC21 vs. UNIMARC, codificação (MARC-8/UTF-8), limites de uso e qualidade bibliográfica antes de cadastrar no Koha.Nexus. Não há importação direta no Koha.

## 5 — Serviço systemd (opcional)

O pacote inclui `systemd/z39-atlas.service.example`. É somente um **modelo**: configure paths e a lista de hosts autorizados antes de instalá-lo. Ele não é habilitado por padrão. Prefira rodar com usuário dedicado sem privilégios e criar o banco em uma pasta gravável por esse usuário.

## Verificação incluída

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile z39atlas.py
```

Os testes offline cobrem: parsing, hosts privados bloqueados, deduplicação/proveniência, estrutura MARC, autorização por allowlist, sugestões de parâmetros e recuperação YAZ simulada. **Este ambiente não possui `yaz-client` ou acesso à sua VPS**, portanto a integração ao vivo deve ser verificada no servidor antes de uso permanente.

## Fontes técnicas e convenções

- [Koha — lista de servidores abertos](https://wiki.koha-community.org/wiki/Koha_Open_Z39.50_Sources)
- [Koha — servidores Z39.50 e SRU](https://wiki.koha-community.org/wiki/Configure_Z39.50/SRU_targets)
- [YAZ client — documentação](https://software.indexdata.com/yaz/doc/yaz-client.html)
- [Z-BRARY](https://www.z-brary.com/)
- [IRSpy](https://irspy.indexdata.com/)

Este programa não é um serviço oficial do Koha. Desenvolvido como protótipo de pesquisa bibliográfica respeitosa; respeite as regras e permissões de cada instituição.
