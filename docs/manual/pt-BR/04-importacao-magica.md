# 4. Importação mágica

[Índice do manual](README.md) · [Anterior: backup](03-backup-restauracao.md)

A Ferramenta de Importação Mágica reúne a leitura de registros bibliográficos, exemplares, leitores e autoridades. Reconhecer o formato não garante que todos os campos tenham sido interpretados corretamente. A decisão final depende da revisão do bibliotecário, principalmente em exportações sem cabeçalho e em campos locais.

## Antes de importar

Mantenha o arquivo original e um backup conferido do Koha. Comece com uma amostra representativa, incluindo registros com vários exemplares, caracteres acentuados, campos vazios e situações excepcionais. Compare os totais do sistema de origem com os totais da prévia. Não envie exportações de leitores para espaços públicos.

Abra **Ferramenta de Importação Mágica**, pela barra lateral ou pela tecla **i**, e abra o cartão da ferramenta. Escolha o arquivo ou a pasta pelo seletor apresentado. O caminho deve ser acessível ao Linux que executa o painel; um arquivo existente apenas no computador do navegador ou do terminal remoto não está automaticamente no servidor.

## Formatos e limites

| Entrada | Como preparar e conferir |
| --- | --- |
| MARC21 ISO 2709, MARCXML e texto MARC | Confira títulos, acentos, autoridades e exemplares. O leitor atual reconhece texto MarcEdit `.mrk`; não é obrigatório convertê-lo apenas por ser `.mrk`. |
| CSV/TSV, Excel `.xlsx` e `.xls`, LibreOffice `.ods`, dBase `.dbf` | Confira separador, cabeçalhos, tipos de campo e os valores realmente detectados. O reconhecimento usa conteúdo e, quando disponíveis, cabeçalhos. |
| JSON e XML tabulares | Confira a estrutura reconhecida e se os campos selecionados representam os dados pretendidos. Um XML qualquer não é necessariamente MARCXML. |
| SQL tabular, inclusive trechos sem cabeçalho | O leitor extrai dados e relações reconhecíveis; não executa o arquivo SQL como um programa de migração. Revise campos ambíguos e vínculos entre tabelas. |
| ISIS | O leitor específico aceita a exportação PostgreSQL reconhecida com a tabela `acervo`. Para um arquivo mestre CDS/ISIS `.mst`, exporte a base do WinISIS em ISO 2709; o arquivo mestre não é lido diretamente como catálogo. |
| Biblioteca Fácil | Use o backup reconhecido ou a pasta de dados, mantendo as tabelas relacionadas juntas. O leitor específico pode preparar registros, leitores, empréstimos e reservas reconhecidos. Confira cada parte separadamente. |
| Backup completo do Koha | A ferramenta encaminha para restauração. Esse procedimento substitui a base e não equivale a acrescentar registros. Leia o capítulo de backup antes de confirmar. |

Um dump PostgreSQL de outro sistema, especialmente no formato binário de `pg_dump`, não é uma base MariaDB pronta para o Koha. Se a ferramenta disser que não o lê, exporte MARC ou planilhas no sistema de origem. Para arquivos compactados, leia o resultado da detecção de cada membro. PDF, imagem, documento de texto e programa executável não são exportações bibliográficas utilizáveis por esse leitor.

## Revisar o mapeamento manual

A tela de mapeamento aparece durante a preparação. Ela não é uma ferramenta separada da importação automática: permite revisar o resultado antes da gravação.

1. Confira o modo no alto: **Bibliographic**, **Patrons** ou **Authorities**. Use o seletor para corrigir uma classificação inadequada. Os rótulos podem aparecer traduzidos na instalação.
2. Observe a grade de exemplos, organizada por registros e campos. Escolha um campo e confira o destino proposto. Para ampliar ou reduzir a grade, use a barra de ajuste ou **Ctrl+Seta para cima** e **Ctrl+Seta para baixo**.
3. Escolha a função do campo: preservar, redirecionar para um destino, definir texto fixo ou ignorar. Não ignore um identificador antes de entender os vínculos que dependem dele.
4. Abra **Values of this Koha** para conferir os códigos disponíveis e os valores padrão de biblioteca, tipo de item e categoria de leitor. Confira também as substituições de valores de origem por valores de destino.
5. Use **Record preview** para ver o registro resultante. **Check the whole file** executa a preparação e a validação do arquivo completo, sem importar os dados no Koha nessa etapa.
6. Para repetir um mapeamento, dê um nome ao perfil e use **Save**. Selecione um perfil salvo e use **Use** para carregá-lo. Revise novamente quando a estrutura da exportação mudar.
7. Use **Apply** ou **Ctrl+S** para aceitar o mapeamento e continuar a preparação. Esse botão não é a confirmação final de importação. **Skip: import as it is**, inclusive **Esc** nessa tela, dispensa o mapeamento manual; não significa cancelar todo o procedimento.

As opções adicionais incluem agrupamento de duplicados e ajustes de texto. Examine a prévia antes de aceitar uma transformação em lote. Não aplique correções de grafia ou de caixa indiscriminadamente a siglas, nomes próprios e códigos de exemplar.

## Registros bibliográficos e exemplares

Os exemplares nativos do Koha estão em `952`. A normalização preserva seus dados e pode remapear biblioteca e tipo de item quando isso for solicitado. Não substitua um código válido só por ser diferente do código padrão: confirme a biblioteca e o tipo de item existentes no Koha de destino.

Campos locais como `949`, `852`, `950` e `990` precisam de interpretação. Exportações de Pergamum e Biblivre podem guardar códigos e datas em subcampos diferentes; o número da etiqueta sozinho não demonstra o significado. Confira código de barras, biblioteca de origem e atual, número de chamada, tipo de item, localização e data de aquisição.

Uma anotação de depósito legal, como um número acompanhado de `DL` e data, não deve criar automaticamente um exemplar local. O normalizador distingue essas anotações de campos com evidência independente de um exemplar real. Revise os campos excluídos e os casos ambíguos.

A política padrão para código de barras ausente é pedir revisão. A geração de identificadores exige a escolha correspondente e uma identidade estável da migração/origem; não resolve colisões com códigos já existentes por renumeração silenciosa. Confira códigos ausentes, duplicados e colisões antes da importação.

Em SQL relacionado, metadados bibliográficos e exemplares precisam de um vínculo reconhecido. Não presuma que a mesma posição de coluna ou a mesma ordem de linhas vincule as tabelas. Se a associação não estiver clara na prévia, interrompa a importação e corrija o mapeamento.

## Leitores e autoridades

Em **Patrons**, confira cada destino do cadastro, incluindo nome, sobrenome, carteirinha, contatos, endereço, datas, biblioteca e categoria. E-mail, CPF ou data reconhecidos são indícios, não prova de que uma coluna foi corretamente classificada. Datas de nascimento, inscrição e vencimento podem ter formatos iguais e sentidos diferentes. A categoria padrão deve existir no Koha.

O fluxo pergunta se leitores existentes devem ser atualizados, usando a carteirinha para a correspondência. Leia essa escolha antes de confirmar; atualizar não é o mesmo que apenas cadastrar leitores novos. Não atribua permissões administrativas ou informações de autenticação por suposição sobre uma coluna.

Em **Authorities**, confira o identificador, o cabeçalho autorizado, as variantes, as relações e o tipo de autoridade. O modo permite mapear campos MARC de autoridade; mudar o modo de uma tabela não cria, por si só, informação que não existe na origem.

## Confirmar e conferir o resultado

Depois do mapeamento, a ferramenta prepara os arquivos de saída e apresenta a prévia e as contagens. Responda às perguntas pendentes sobre biblioteca, tipo de item, categoria e atualização de leitores. Leia rejeições e avisos antes de aceitar a gravação.

Para registros já existentes, o fluxo oferece manter o registro do catálogo e acrescentar somente exemplares novos, substituir o registro pelo recebido ou não comparar e criar um título novo para cada registro. Escolha conforme a migração, evitando repetir um lote por engano.

A execução pode ter etapas de registros, autoridades, leitores e circulação. **Uma falha posterior não garante que as etapas anteriores tenham sido desfeitas.** Guarde o resumo e os logs, confira as contagens e não repita o lote completo automaticamente.

Depois, pesquise amostras no Koha, confira exemplares em suas bibliotecas, cadastros de leitores e vínculos de autoridade. Em **Ferramentas da biblioteca**, **Desfazer uma importação MARC** trata lotes MARC; não é uma reversão universal de leitores, empréstimos e reservas. Para recuperação da base completa, use a Central de Backup com os cuidados do capítulo anterior.

## Ponto a confirmar

**A confirmar:** a compatibilidade com uma exportação de versão específica de outro sistema depende de uma amostra e da revisão do resultado. O reconhecimento dos formatos acima não constitui garantia para qualquer layout proprietário.

## Fontes conferidas

- [Menus do painel](../../../panel/kei_panel/menus.py), seção `import`.
- [Mapeamento manual](../../../panel/kei_panel/screens/fieldmap.py), composição da tela, modos, prévia e aplicação.
- [Instalador e leitores](../../../installer), `lt_magic_import`, `_lt_magic_run` e módulos gerados `detect`, `bridge`, `engine`, `readers`, `relational` e `holdings`.
