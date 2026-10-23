# 6. Aparência do OPAC e da interface da equipe

[Índice do manual](README.md) · [Anterior: enriquecimento](05-enriquecimento.md)

Abra **Aparência do OPAC e STAFF**, pela barra lateral ou pela tecla **o**. A tela configura o catálogo público e a interface profissional, chamada staff ou intranet. Os dois lados têm configurações próprias.

## Um procedimento seguro

1. Use **Sincronizar configurações atuais do OPAC** para carregar o que está no Koha antes de editar. A sincronização lê as configurações; não aplica um novo tema.
2. Ajuste um grupo de opções por vez. Confira cores, legibilidade e imagens antes de acrescentar outras mudanças.
3. Use **Prévia**. Ela mostra o CSS, o JavaScript e o conteúdo que serão gravados no Koha; não é uma renderização completa da página em um navegador.
4. Use **Aplicar**, leia o resumo e confirme. O fluxo faz backup do banco antes da aplicação.
5. Abra o OPAC e a interface da equipe no navegador. Confira as páginas de busca, registro e login, além das páginas iniciais. Verifique também a leitura em uma tela pequena.

O painel escreve seus blocos nas preferências `OpacUserCSS` e `OpacUserJS`; a aparência da equipe usa `IntranetUserCSS` e, quando necessário, `IntranetUserJS`. Os blocos próprios da biblioteca são preservados pelo mecanismo do tema. Isso não garante ausência de conflitos visuais com personalizações externas: confira o resultado no navegador.

## Cores, material e legibilidade

Os controles incluem textura, desfoque, opacidade, cantos, cores de destaque e fundo. O modo claro/escuro e o tema padrão têm controles próprios. Evite combinações com pouco contraste entre texto e fundo, especialmente quando há imagem ou transparência.

Na área da equipe, há controles para cores, barra superior, busca rápida, cartões de módulos, densidade das tabelas, tamanho do texto e contraste. Ative a aplicação do tema à equipe se quiser usar essas escolhas. **Copiar predefinição do OPAC** preenche os campos da equipe; **Aplicar** é que grava as alterações.

## Imagens

Escolha entre arquivo no servidor, serviços de hospedagem disponíveis na tela ou URL HTTPS direta. O seletor aceita PNG, JPEG, GIF, WebP e ICO; SVG é recusado. Um arquivo no computador do bibliotecário precisa estar acessível ao servidor antes de ser escolhido como arquivo local.

Use imagens próprias ou com autorização de uso. Para as páginas de login, preencha a descrição da imagem para leitores de tela. Um endereço de página de hospedagem não é necessariamente o endereço direto de uma imagem.

Se usar um serviço externo de imagens, confira a configuração pela própria tela. Não publique dados privados em imagens do login ou do OPAC.

## Carrossel e botões

O carrossel pode mostrar novidades ou uma lista do Koha. Para uma lista, informe seu número, conforme aparece em `shelfnumber=` no endereço da lista. Ajuste título, quantidade, estilo, velocidade e reprodução automática. A atualização do carrossel tem botão próprio.

As novidades dependem dos registros e das capas disponíveis; não aparecer uma capa não significa que o registro tenha desaparecido do catálogo. O uso de capas externas exige conexão aos respectivos serviços.

Os botões de acesso rápido do OPAC e os da página inicial da equipe são configurados separadamente. Confira texto, endereço, destino e ordem. Use **Adicionar um botão** para incluir uma entrada e o botão de remoção da linha para excluí-la antes de aplicar.

## Login, notícias e rodapé

As caixas de login do OPAC e da equipe permitem imagem, descrição e texto HTML. O fluxo filtra elementos inseguros, como scripts, estilos e manipuladores de eventos. Não use essas áreas para publicar instruções internas que não devam ser vistas por visitantes.

As notícias do OPAC e da equipe têm título, texto e botões próprios. Elas são publicadas como entradas do painel no Koha; as notícias já criadas pela biblioteca não são substituídas por esse mecanismo.

Os créditos do rodapé são preenchidos como linhas `Campo: valor`, conforme os campos indicados na própria tela. Links adicionais usam texto, uma barra `|` e o endereço, com limite de seis links. Escreva somente informações públicas da biblioteca.

## Remover a aparência

**Remover** pede confirmação e faz backup antes de retirar os blocos do tema do painel. O objetivo é voltar à aparência do Koha, preservando as personalizações próprias da biblioteca. Essa ação não é um restore geral da base e não desfaz outras operações administrativas.

Se uma imagem, cor ou botão ficar incorreto, corrija o grupo correspondente e aplique novamente. Guarde a mensagem de erro quando a aplicação falhar, para consulta na seção de diagnóstico.

## Fontes conferidas

- [Tela de aparência](../../../panel/kei_panel/views/opac.py), composição, coleta e validação, sincronização, prévia, aplicação e remoção.
- [Menus do painel](../../../panel/kei_panel/menus.py), seção `opac` e tecla de acesso.
