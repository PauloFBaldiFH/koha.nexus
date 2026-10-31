# 7. IA local e ferramentas de assistência

[Índice do manual](README.md) · [Anterior: aparência](06-aparencia.md)

A tela **IA**, acessível pela tecla **a**, reúne a configuração do provedor, o Ollama neste servidor e duas ferramentas: catalogação a partir de imagens no MARC Replace e assistente na página inicial da equipe. Configurar o provedor não instala automaticamente todas as ferramentas.

## Configurar o Ollama

1. Abra a tela de IA e leia o aviso de desempenho. O processamento local pode consumir grande parte da CPU e da RAM e deixar o Koha lento.
2. Na caixa **Ollama neste servidor**, use **Verificar o Ollama**. Se não estiver instalado, use **Instalar o Ollama** e aguarde o resultado.
3. Escolha o modelo na lista apresentada pelo próprio painel e use **Baixar**. O download requer acesso à rede e espaço livre. Este manual não fixa nomes de modelos, pois a lista e a disponibilidade podem mudar.
4. Selecione **Ollama local** como provedor e confira a URL do servidor. O endereço local padrão é `http://127.0.0.1:11434`.
5. Use **Usar no chat** ou **Usar na catalogação**, conforme a finalidade. A catalogação de fotos exige capacidade de visão; um modelo apenas de texto não serve para ler imagens.
6. Use **Testar conexão** e **Salvar**. Colocar uma seleção no campo não equivale a salvá-la. Os atalhos da tela são **F5** para testar e **Ctrl+S** para salvar.

O campo de chat vazio usa a escolha de visão, segundo a configuração. **Carregar modelos** consulta a lista do provedor; a tela informa quando está usando uma lista embutida por não conseguir consultar o servidor.

**Instalado** e **em memória** são estados diferentes. Um modelo baixado ocupa disco; quando carregado para responder, também ocupa RAM. **Liberar memória** descarrega os modelos em memória, sem apagar os downloads. O Ollama pode carregá-los novamente na próxima solicitação.

A caixa de Ollama continua disponível mesmo quando outro provedor está selecionado. Para que uma ferramenta realmente use processamento local, confira o provedor e a URL salvos para ela. Não conclua que uma consulta foi local apenas porque o Ollama está instalado.

## Usar MARC Replace e a catalogação por fotos

Na área das ferramentas, instale ou atualize a página de substituição MARC e abra **MARC Replace**. O instalador verifica se a página compila com o Koha e pergunta sobre os atalhos da interface profissional.

A página trabalha com um registro por vez. Na substituição por arquivo ou texto:

1. Escolha o `.mrc` ou `.xml`, ou cole o texto do registro.
2. Informe o `biblionumber` do registro existente que pretende substituir. Deixá-lo vazio é o caminho de criação de um registro novo; confira a prévia para não criar uma duplicação acidental.
3. Use **Prévia** e compare a versão atual com a proposta.
4. Confirme somente depois de conferir a identidade do título e os campos bibliográficos.

Os exemplares de um registro substituído são preservados; os campos de item recebidos no arquivo são deixados de fora. A versão anterior é salva e pode ser baixada em MARCXML. Para voltar a ela, a própria página orienta enviar essa versão para o mesmo `biblionumber`. Isso não substitui o backup completo do banco.

Na aba de catalogação com IA:

1. Envie fotos legíveis da capa, folha de rosto e verso da folha de rosto, conforme disponíveis. A página aceita JPEG, PNG e WebP e exige pelo menos uma imagem.
2. Escolha o framework do registro novo ou informe o registro que será substituído, conforme a intenção.
3. Use a ação de leitura das fotos e aguarde o rascunho.
4. Compare o rascunho com as imagens. Confira título, responsabilidade, publicação, ISBN, classificação e dados que não puderam ser lidos.
5. Corrija o texto MARC antes de confirmar a gravação.

A classificação sugerida pela IA exige revisão nas tabelas adotadas pela biblioteca. Um ISBN com dígito verificador correto não prova a correspondência com a edição. A página apresenta avisos para informações ausentes e não grava os campos de exemplares nesse rascunho.

## Assistente na página inicial da equipe

Use **Instalar, atualizar ou remover o assistente** para gerenciar a ferramenta. A instalação coloca o chat acima do bloco de notícias da página inicial da equipe; as notícias continuam visíveis logo abaixo.

O assistente busca com o mecanismo do Koha e consultas de leitura definidas pela aplicação. Ele não executa SQL livre escrito pela IA. Respostas podem trazer links para registros e propostas de ação.

**Uma proposta ainda não é uma alteração executada.** Confira o registro, os valores atuais e propostos e o efeito da operação. A execução exige **Approve & Execute**, mostrado traduzido conforme a instalação, e respeita as permissões do bibliotecário. Se o registro mudou depois da proposta, o fluxo pode recusá-la e pedir uma nova.

Há uma opção para consultar as mudanças confirmadas no assistente. Não confunda limpar uma conversa ou remover o assistente com desfazer todas as ações aprovadas. A remoção apaga as conversas salvas e mantém o registro das mudanças confirmadas, conforme o aviso do painel.

## Desempenho e confidencialidade

Use a IA local em um horário que permita observar CPU, memória e resposta do Koha. Se o servidor ficar lento, evite iniciar novas leituras de fotos e use a liberação de memória quando apropriado. Não existe, no código consultado, um tempo garantido de resposta para todos os computadores.

Um provedor remoto recebe os dados enviados para a solicitação. Antes de utilizá-lo, avalie a política da biblioteca para dados pessoais e imagens. Não envie dados de leitores só para testar o chat. As etiquetas de custo da lista são orientação da interface, não garantia de gratuidade pelo provedor.

## Ponto a confirmar

**A confirmar:** dimensionamento de RAM, disco e tempo de resposta para cada escolha de processamento local. As necessidades dependem do modelo selecionado e do hardware; o mínimo de instalação do Koha não garante desempenho de IA.

## Fontes conferidas

- [Tela de IA](../../../panel/kei_panel/views/ai.py), campos, botões, atalhos, verificação, download e liberação de memória.
- [Integração MARC Replace](../../../panel/kei_panel/marcreplace.py), abertura e gerenciamento da página.
- [Instalador](../../../installer), `function_marc_replace`, textos e implementação da página gerada, `function_ai_assistant`, instalação, propostas e remoção do assistente.
