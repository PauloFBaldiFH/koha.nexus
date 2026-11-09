# Idiomas do DSpace e compatibilidade de imagens — 1.5.192

O menu compartilhado **Idiomas** agora reúne painel, Koha e DSpace. No DSpace,
a pessoa escolhe os idiomas disponíveis aos visitantes e o idioma de fallback.
O painel sugere seu próprio idioma, quando o upstream o oferece. Não traduz
metadados nem altera a preferência salva de contas existentes.

## Comportamento

- A imagem de receita 5 inclui 37 catálogos de tradução do DSpace 10.1,
  conferidos por SHA-256 contra o commit upstream fixado. Inclui português
  brasileiro, português europeu, espanhol, francês, alemão, japonês e suaíli.
  A ativação utiliza os arquivos já incluídos; não precisa baixar um pacote
  a cada seleção. As traduções podem ter cobertura diferente entre idiomas.
- Em instalação nova, o idioma do painel sugere o fallback inicial. Idioma
  indisponível no DSpace usa inglês. Preferência do navegador/visitante tem
  prioridade quando está entre os idiomas habilitados.
- A seleção apresenta plano e confirmação, valida que ao menos um idioma está
  ativo e que o fallback pertence à seleção. Detecta configuração alterada
  desde o plano. Se o repositório está rodando, recria somente a UI e confere
  sua saúde e acesso público; não reinicia banco, Solr ou backend.
- Se o repositório está parado, salva para a próxima inicialização, mantendo
  os serviços parados. Falha ao aplicar recupera a configuração anterior.
- O administrador criado pelo assistente pode usar qualquer um dos 37 idiomas
  na receita 5. Senhas continuam somente na entrada padrão, sem log ou argv.
  Não muda o idioma das contas já cadastradas.

## Instalações e backups existentes

Atualizar o painel não substitui imagens instaladas. As receitas 3 e 4
continuam disponíveis com os hashes históricos exatos, inclusive para testar
ou restaurar seus backups. Nessas imagens, a UI oferece seus 35 idiomas
originais; o assistente antigo de contas suporta inglês, português brasileiro
ou espanhol. A interface respeita essa capacidade, em vez de anunciar suporte
que o contêiner não tem.

Para os 37 idiomas e a ampliação do assistente de contas, usar **DSpace →
Atualização revisada do DSpace**. É possível preparar as imagens no próprio
servidor, com consentimento para a compilação demorada, ou selecionar um
catálogo existente. Preparar não troca as imagens ativas. O plano de atualização
separado exige backup de segurança criptografado e verificado antes de trocar
as imagens. Não há migração de versão do banco nesta atualização.

A atualização das receitas 3 ou 4 para 5 remapeia os idiomas pelo código, não
pelo índice no array, preservando os idiomas ativos e o fallback. Configuração
manual com códigos/rótulos personalizados ou arquivo de configuração externo
é preservada e exige revisão do mapeamento. O procedimento não a reinterpreta
silenciosamente.

O manifesto inclui o hash do catálogo de idiomas e dos adaptadores de imagem.
O bundle de preparação inclui catálogo, travas históricas e arquivos de imagem.
O cache offline do instalador inclui o módulo de idiomas e verifica seus hashes.

## Validação e limites

- Suíte completa do workflow Platforms panel: 276 testes aprovados. Após os
  ajustes finais de revisão/instalação parada, 77 testes de
  idiomas e de administração do DSpace, menus e documentação aprovados.
- 202 testes DSpace aprovados em Debian descartável como root: configuração, plano sem
  escrita, cancelamento, revisão obsoleta, preservação de serviços parados,
  rollback, compatibilidade de receitas e restauração.
- Imagem real da UI de receita 5 compilada neste ambiente; contrato e startup
  como usuário sem privilégios aprovados. Os 37 arquivos públicos de tradução
  foram lidos e interpretados como JSON, não apenas aceitos por HTTP 200.
- CI ampliada para instalar com navegador real, criar e autenticar uma conta
  francesa, conferir seu idioma salvo, testar fallback português e preferência
  francesa; atualizações reais 3→5 e 4→5 preservando idiomas por código.
- O backend novo não foi compilado localmente: a política deste ambiente
  bloqueia o repositório Maven de handle.net. Compilação, conta real e ciclos
  completos devem passar na CI antes da mesclagem. Os testes de seleção local
  usam serviços controlados; não representam validação no servidor de Paulo.

Esta etapa depende da correção de retomada da rota web em
`docs/dspace/PR-retomar-acesso.pt-BR.md`. Mesclar essa correção primeiro permite
revisar apenas o conteúdo de idiomas no PR seguinte.
