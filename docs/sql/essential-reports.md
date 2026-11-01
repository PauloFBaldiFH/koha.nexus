# Pacote de 100 relatórios SQL essenciais

O pacote contém 100 definições: os 22 relatórios anteriores, preservados com
suas chaves, e 78 novas consultas de finalidade distinta. A instalação pelo
painel atualiza os relatórios identificados pela marca própria, preserva IDs
e não remove relatórios criados pela biblioteca. Reinstalar não duplica o pacote.
A remoção continua limitada às marcas do pacote.

## Uso e limites

No painel, abra o pacote de relatórios SQL essenciais e escolha instalar ou
atualizar. Examine a prévia e confirme. Depois use Relatórios > Relatórios salvos
no Koha. Nada é instalado automaticamente por esta mudança no repositório.

Cada consulta é um SELECT. A instalação testa sua compatibilidade com EXPLAIN;
relatórios incompatíveis com o esquema local são ignorados e registrados no log.
Assim, 100 é a quantidade de definições, não uma garantia de 100 instaladas em
qualquer versão do Koha. A cópia de segurança e a confirmação existentes são
preservadas. Os relatórios são privados por padrão, com public=0.

Há dados pessoais em consultas operacionais de leitores e circulação. Restrinja
permissões e a distribuição de exportações. Nenhuma consulta lê senhas, tokens
ou documentos pessoais. Indicadores históricos dependem da retenção e da
anonimização de statistics/old_issues; junções com exemplares atuais não
reconstituem automaticamente exemplares já excluídos.

Agregações e verificações de integridade podem percorrer tabelas inteiras:
execute-as fora de horários de pico em bases grandes. Muitos diagnósticos
retornam zero linhas quando os dados estão consistentes. Não use essas listas
como ordem automática para apagar, fundir ou corrigir registros.

Títulos repetidos não provam duplicidade bibliográfica; emails compartilhados
podem ser legítimos; endereços ausentes podem refletir política de privacidade.
“Reservas aguardando há mais de sete dias” é um alerta fixo para revisão,
não a aplicação da política local de expiração. Pressão de reservas compara
reservas ativas com cópias não baixadas, não com disponibilidade emprestável:
exemplares perdidos, restritos e já emprestados exigem avaliação adicional.
Os relatórios financeiros mostram saldos de accountlines, não um demonstrativo
fiscal ou fluxo de caixa. Datas e resultados dependem do relógio do banco.

Os novos títulos têm tradução pt-BR. Nos demais caches a chave está presente
com fallback inglês; não há alegação de tradução humana para esses títulos.
Os nomes técnicos de colunas das novas consultas também podem aparecer em inglês.

## Referências e validação

- Manual oficial indicado pelo usuário: https://koha-community.org/manual/latest/en/html/reports.html
- Biblioteca comunitária: https://wiki.koha-community.org/wiki/SQL_Reports_Library

A rede deste ambiente bloqueou o acesso aos dois endereços. Eles são referências
para revisão, não fontes que tenham sido consultadas ou copiadas nesta execução.
As novas consultas foram escritas para este pacote e verificadas no ambiente de
testes do projeto. Não foi realizada validação numa instalação Koha de produção.

A revisão considerou a finalidade de cada relatório e compara também chaves,
títulos e SQL normalizado para impedir duplicações exatas. Indicadores agregados,
listas de atendimento e diagnósticos relacionados podem compartilhar tabelas,
mas respondem perguntas diferentes.

## Inventário

CAT: catálogo e autoridades. CIRC: circulação e reservas. PAT: leitores e saldos.
ACQ: aquisições. Os 22 primeiros são os relatórios preservados.

| Nº | Chave estável | Grupo | Relatório |
| --- | --- | --- | --- |
| 1 | `top-loans` | CIRC | Títulos mais emprestados (últimos 12 meses) |
| 2 | `overdue` | CIRC | Empréstimos em atraso com contato dos leitores |
| 3 | `never-borrowed` | CAT | Exemplares nunca emprestados (adquiridos há mais de 2 anos) |
| 4 | `new-items` | CAT | Aquisições recentes (últimos 30 dias) |
| 5 | `expiring` | PAT | Cadastros de leitores que expiram nos próximos 30 dias |
| 6 | `loans-month` | CIRC | Empréstimos por mês e biblioteca (últimos 12 meses) |
| 7 | `missing-data` | CAT | Exemplares sem código de barras ou número de chamada |
| 8 | `lost-items` | CAT | Exemplares perdidos |
| 9 | `acquisitions` | ACQ | Aquisições e doações por período |
| 10 | `zero-loans` | CAT | Exemplares nunca emprestados |
| 11 | `ddc-classes` | CAT | Acervo por classe da CDD (000-900) |
| 12 | `patrons-district` | PAT | Leitores por bairro e cidade |
| 13 | `patrons-new` | PAT | Novos leitores cadastrados por mês (últimos 24 meses) |
| 14 | `inventory-out` | CAT | Exemplares baixados, danificados ou extraviados (inventário) |
| 15 | `loans-type` | CIRC | Empréstimos por tipo de material (últimos 12 meses) |
| 16 | `children-new` | CAT | Livros infantis catalogados recentemente (últimos 90 dias) |
| 17 | `fines-debarred` | PAT | Leitores com multas pendentes ou suspensões |
| 18 | `orphan-authorities` | CAT | Registros de autoridade sem nenhum registro bibliográfico vinculado |
| 19 | `active-patrons` | PAT | Leitores ativos por categoria (últimos 12 meses) |
| 20 | `holds-waiting` | CIRC | Reservas aguardando retirada |
| 21 | `collection-type` | CAT | Acervo por biblioteca e tipo de material |
| 22 | `circ-daily` | CIRC | Circulação diária (últimos 30 dias) |
| 23 | `titles-no-items` | CAT | Registros bibliográficos sem exemplares |
| 24 | `titles-no-author` | CAT | Registros bibliográficos sem autor |
| 25 | `titles-no-title` | CAT | Registros bibliográficos sem título |
| 26 | `items-no-type` | CAT | Exemplares sem tipo de material |
| 27 | `items-invalid-type` | CAT | Exemplares com tipo de material desconhecido |
| 28 | `items-invalid-home` | CAT | Exemplares com biblioteca de origem desconhecida |
| 29 | `items-invalid-holding` | CAT | Exemplares com biblioteca atual desconhecida |
| 30 | `items-away-home` | CAT | Exemplares em biblioteca diferente da origem |
| 31 | `items-by-location` | CAT | Acervo por localização na estante |
| 32 | `items-by-collection` | CAT | Acervo por código de coleção |
| 33 | `items-by-year` | CAT | Acervo por ano de incorporação |
| 34 | `items-notforloan` | CAT | Exemplares marcados como não emprestáveis |
| 35 | `items-restricted` | CAT | Exemplares com restrições de uso |
| 36 | `items-not-seen` | CAT | Exemplares não vistos nos últimos dois anos |
| 37 | `items-future-accession` | CAT | Exemplares com data de incorporação futura |
| 38 | `items-negative-cost` | CAT | Exemplares com preço de compra ou reposição negativo |
| 39 | `items-no-replacement` | CAT | Exemplares emprestáveis sem valor de reposição |
| 40 | `items-duplicate-barcodes` | CAT | Códigos de barras de exemplares duplicados |
| 41 | `items-orphan-biblio` | CAT | Exemplares vinculados a registro bibliográfico inexistente |
| 42 | `metadata-missing` | CAT | Registros bibliográficos sem metadados MARC |
| 43 | `titles-same-name` | CAT | Títulos e autores repetidos para revisão de duplicatas |
| 44 | `titles-copy-count` | CAT | Títulos com mais exemplares físicos |
| 45 | `collection-value` | CAT | Valor de compra e reposição do acervo por biblioteca |
| 46 | `cataloging-month` | CAT | Registros bibliográficos catalogados por mês |
| 47 | `authors-most-titles` | CAT | Autores com mais títulos catalogados |
| 48 | `loans-current-library` | CIRC | Empréstimos atuais por biblioteca de atendimento |
| 49 | `loans-current-category` | CIRC | Empréstimos atuais por categoria de leitor |
| 50 | `loans-current-type` | CIRC | Empréstimos atuais por tipo de exemplar |
| 51 | `loans-due-today` | CIRC | Empréstimos com vencimento hoje |
| 52 | `loans-due-week` | CIRC | Empréstimos com vencimento nos próximos sete dias, exceto hoje |
| 53 | `overdue-bands` | CIRC | Empréstimos atrasados por faixa de atraso |
| 54 | `overdue-patron-count` | CIRC | Leitores por quantidade de empréstimos atrasados |
| 55 | `loans-expired-accounts` | CIRC | Empréstimos atuais de leitores com cadastro vencido |
| 56 | `loans-lost-copies` | CIRC | Empréstimos atuais de exemplares marcados como perdidos |
| 57 | `loans-withdrawn-copies` | CIRC | Empréstimos atuais de exemplares baixados |
| 58 | `loans-missing-borrower` | CIRC | Empréstimos atuais vinculados a leitor inexistente |
| 59 | `loans-missing-item` | CIRC | Empréstimos atuais vinculados a exemplar inexistente |
| 60 | `loans-renewed-current` | CIRC | Empréstimos atuais com renovações |
| 61 | `loans-invalid-dates` | CIRC | Empréstimos com vencimento anterior à retirada |
| 62 | `returns-month` | CIRC | Empréstimos concluídos por mês de devolução |
| 63 | `returns-lateness` | CIRC | Empréstimos concluídos devolvidos após o vencimento |
| 64 | `loan-duration` | CIRC | Duração média de empréstimos concluídos por biblioteca |
| 65 | `circulation-weekday` | CIRC | Movimentações de circulação por dia da semana |
| 66 | `circulation-hour` | CIRC | Movimentações de circulação por hora |
| 67 | `renewals-month` | CIRC | Renovações por mês e biblioteca |
| 68 | `localuse-month` | CIRC | Uso local por mês e biblioteca |
| 69 | `patrons-library-category` | PAT | Leitores cadastrados por biblioteca e categoria |
| 70 | `patrons-age-bands` | PAT | Leitores por faixa etária |
| 71 | `patrons-expired` | PAT | Cadastros de leitores vencidos |
| 72 | `patrons-no-expiry` | PAT | Leitores sem data de vencimento do cadastro |
| 73 | `patrons-no-contacts` | PAT | Leitores sem contato de email ou telefone |
| 74 | `patrons-no-address` | PAT | Leitores sem endereço residencial |
| 75 | `patrons-invalid-birth` | PAT | Leitores com data de nascimento futura |
| 76 | `patrons-invalid-membership` | PAT | Cadastros com vencimento anterior à inscrição |
| 77 | `patrons-duplicate-email` | PAT | Endereços de email compartilhados por vários leitores |
| 78 | `patrons-duplicate-card` | PAT | Números de carteirinha duplicados |
| 79 | `patrons-invalid-category` | PAT | Leitores com categoria desconhecida |
| 80 | `patrons-invalid-library` | PAT | Leitores com biblioteca desconhecida |
| 81 | `patrons-current-load` | PAT | Leitores por quantidade atual de empréstimos |
| 82 | `patrons-no-current-loans` | PAT | Cadastros válidos sem empréstimos atuais |
| 83 | `holds-by-library` | CIRC | Reservas ativas por biblioteca de retirada e situação |
| 84 | `holds-queued` | CIRC | Reservas não atendidas por ordem de prioridade |
| 85 | `holds-suspended` | CIRC | Reservas suspensas |
| 86 | `holds-expired` | CIRC | Reservas com data explícita de expiração ultrapassada |
| 87 | `holds-old-waiting` | CIRC | Reservas aguardando retirada há mais de sete dias |
| 88 | `holds-no-copies` | CIRC | Reservas de títulos sem exemplares físicos |
| 89 | `holds-missing-patron` | CIRC | Reservas vinculadas a leitor inexistente |
| 90 | `holds-missing-record` | CIRC | Reservas vinculadas a registro bibliográfico inexistente |
| 91 | `holds-demand` | CIRC | Títulos por demanda de reservas ativas |
| 92 | `holds-pressure` | CIRC | Demanda de reservas comparada a exemplares não baixados |
| 93 | `debits-by-code` | PAT | Saldos de débitos pendentes por tipo de cobrança |
| 94 | `credits-by-code` | PAT | Saldos de créditos não alocados por tipo |
| 95 | `debits-age` | PAT | Débitos pendentes por faixa de antiguidade |
| 96 | `patrons-net-balances` | PAT | Saldos líquidos das contas dos leitores |
| 97 | `account-orphan-patron` | PAT | Lançamentos financeiros vinculados a leitor inexistente |
| 98 | `authority-type-count` | CAT | Registros de autoridade por tipo |
| 99 | `authority-missing-marc` | CAT | Registros de autoridade sem MARCXML |
| 100 | `authority-created-month` | CAT | Registros de autoridade criados por mês |
