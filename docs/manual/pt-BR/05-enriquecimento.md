# 5. Enriquecimento de registros e servidores Z39.50/SRU

[Índice do manual](README.md) · [Anterior: importação](04-importacao-magica.md)

Importar e enriquecer têm objetivos diferentes. A importação traz registros de uma exportação. O enriquecimento procura dados complementares para registros existentes, ou encontra um livro para inclusão como registro novo. Uma correspondência de título não dispensa revisão bibliográfica.

## Enriquecer registros existentes

Abra **Ferramentas da biblioteca** e **Enriquecer com catálogos do mundo**. A tecla **n** abre essa tela. A tela antiga de enriquecimento bibliográfico em lote não é mais o caminho apresentado no menu atual.

1. Informe `all` para todos os registros ou os `biblionumbers` desejados, como `101, 102, 500-510`, e use **Pesquisar**.
2. Acompanhe o trabalho e o quadro de servidores. Uma tarefa grande continua em segundo plano e pode prosseguir depois de um reinício. A máquina precisa permanecer disponível para que haja progresso.
3. Use **Pausar** e **Retomar** quando necessário. Pausar a busca não equivale a reverter alterações já aplicadas.
4. Selecione o trabalho e abra seu relatório. Compare os campos propostos com o registro atual, especialmente assuntos, classificação, notas e descrição física.
5. Use **Pesquisar mais servidores** para consultar fontes ainda não utilizadas, ou **Escolher doador** para selecionar a fonte de um grupo de campos entre os resultados disponíveis.
6. Use **Aplicar** apenas depois da revisão e leia a confirmação. A busca e a preparação do relatório não gravam essas propostas no catálogo.

A tela atual anuncia consultas Z39.50 diretas. Os servidores têm seus próprios limites e podem ficar temporariamente indisponíveis. Uma demora ou uma busca sem resultado não demonstra que o livro não exista em outros catálogos.

Não há um limite geral de 50 registros para pesquisar. A diferença entre trabalhos pequenos e grandes afeta a proteção da aplicação: o código usa cópias dos registros para trabalhos pequenos e backup completo verificado para trabalhos maiores. Isso não torna a revisão dispensável.

**Reverter** recupera as versões anteriores dos registros do trabalho conforme as regras de proteção do fluxo. Registros alterados no Koha depois da aplicação são preservados. Não trate essa ação como um restore completo da base ou como reversão de qualquer edição feita por outros usuários.

## Encontrar um livro e importá-lo

Na mesma tela, use os campos ISBN ou título; autor e ano ajudam a identificação. Use **Encontrar**, examine as fontes e selecione o resultado desejado. **Importar como registro novo** acrescenta um registro, mediante confirmação; não substitui um registro existente com o mesmo ISBN.

Os campos locais `9XX` do catálogo doador são retirados nesse fluxo e a origem é registrada. Isso evita copiar os exemplares de outra biblioteca como se fossem seus. Confira o registro incluído no Koha e cadastre os exemplares locais pelo procedimento da biblioteca. Para desfazer o lote MARC correspondente, há **Desfazer uma importação MARC** em Ferramentas da biblioteca.

## Enriquecer e padronizar autoridades

Abra **Enriquecer e padronizar autoridades**, em Ferramentas da biblioteca, ou use a tecla **h**. Defina o escopo e escolha entre formas exatas e formas próximas. A opção de formas próximas pode propor uma correção de grafia e criar autoridades marcadas como preliminares; requer atenção especial.

O fluxo procura primeiro nas autoridades do próprio Koha, depois na base de enriquecimento e em servidores diretos. O código prioriza fontes brasileiras e restringe a busca de assuntos a fontes brasileiras. Essas regras não garantem que cada cabeçalho encontrado seja o adequado para sua política de catalogação.

Leia o relatório antes de **Aplicar**. A aplicação cria autoridades necessárias e vincula os registros, com backup de segurança. Registros editados depois da preparação do relatório ficam preservados. Ao reverter, autoridades criadas pelo trabalho que ainda tenham vínculos são mantidas; não se deve esperar sua exclusão indiscriminada.

## Configurar Z39.50 e SRU

Abra **Servidores Z39.50 / SRU**, pela barra lateral ou pela tecla **z**. Diferencie as funções da tela:

- O servidor deste Koha permite que outras bibliotecas consultem seu catálogo. Ligar ou desligar altera também a abertura da porta correspondente no firewall, segundo o fluxo do painel.
- A rede comunitária configura uma fonte de catálogo compartilhado no Koha. Isso é distinto da lista de servidores diretos consultados pelo enriquecimento por catálogos do mundo.
- O quadro de saúde mostra falhas dos servidores usados nas buscas diretas. **Reset** ou **Reset all** libera uma nova tentativa; não conserta o serviço remoto.
- Os catálogos de saída servem à catalogação por cópia. **Mostrar servidores** testa cada servidor com uma busca real (não apenas uma conexão à porta) e lista os que devolvem registro; um servidor de backup só aparece quando o principal não devolve nenhum. Marque os servidores da pesquisa da catalogação com **Selecionar** ou a barra de espaço, desmarque com **Desselecionar** (recomendamos no máximo 20) e use **Salvar no Koha**. **Atualizar** testa de novo.

O suporte a SRU nessa configuração não significa que toda pesquisa de enriquecimento use SRU. Não exponha o servidor de entrada apenas para consultar um catálogo externo: são direções de comunicação diferentes.

## Ponto a confirmar

**A confirmar:** a disponibilidade, a cobertura e as condições de acesso de cada fonte externa no momento de uso. O código e a lista de servidores não comprovam que todos estejam acessíveis na rede da biblioteca.

## Fontes conferidas

- [Menus](../../../panel/kei_panel/menus.py), ações de ferramentas da biblioteca e servidores.
- [Enriquecer com catálogos do mundo](../../../panel/kei_panel/views/ondemand.py), composição, busca, importação e proteção de aplicação.
- [Trabalhos e autoridades](../../../panel/kei_panel/views/enrich.py), relatórios, aplicação, reversão e `AuthEnrichView`.
- [Servidores](../../../panel/kei_panel/views/z3950.py), entrada, saúde, seleção, teste e inclusão.
