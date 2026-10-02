<p align="right">
  <a href="README.md">🇺🇸 English</a> &nbsp;|&nbsp; 🇧🇷 Português
</p>

<p align="center">
  <img src="docs/images/koha-logo-green.png" alt="Logotipo do Koha" width="320">
</p>

# Koha Easy Installer & Manager

Um único script Bash que instala, ajusta e mantém o **[Koha](https://koha-community.org/), sistema integrado de gestão de bibliotecas**, no Debian/Ubuntu, por meio de um painel de controle com menus (whiptail, tema escuro) disponível em **22 idiomas**.

Nasceu da experiência real com as barreiras técnicas da gestão de acervos e foi pensado para bibliotecas sem orçamento para sistemas comerciais caros ou suporte técnico dedicado.

---

## Recursos

- **Instalação em um passo** do Koha, MariaDB, Apache, Memcached e Plack, com pré-validação do servidor (sistema, disco, rede, portas ocupadas), SWAP de 4 GB, NTP e escolha do fuso horário.
- **Central de backup**: backup SQL compactado diário, exportação MARC21 semanal, backup manual com instruções de download, teste de restauração em banco temporário e cópia na nuvem para o Google Drive (rclone).
- **Restauração segura** de backups `.sql` / `.sql.gz`: o arquivo é verificado (teste do gzip, mysqldump completo, tabelas do Koha) e importado antes em um banco temporário; o catálogo atual só é substituído depois de existir uma cópia de segurança verificada, volta automaticamente se algo falhar, e a restauração não fica pela metade por causa de um CTRL+C ou de uma queda da conexão SSH.
- **Motor de busca**: troca entre Zebra e Elasticsearch 7, vigia (watchdog) do indexador e ferramentas de reparo/reconstrução.
- **Publicação na internet**: Túnel Cloudflare (sem abrir portas), certificado SSL gratuito (Certbot) e assistente do Google Search Console.
- **Endereço gratuito (em teste)**: um endereço público para o catálogo sem comprar domínio nem abrir conta no Cloudflare. A biblioteca digita o nome e o endereço desejado no painel, e o endereço é criado na hora. O link pode ser compartilhado como QR code na tela, imagem de QR code para imprimir ou link. O acesso remoto da equipe acrescenta uma senha verificada no Cloudflare antes do login do próprio Koha. O serviço de endereços ainda está em teste e não está aberto às bibliotecas.
- **Autorização por QR code**: quando o Cloudflare ou o Google Drive pedem para autorizar o servidor, o painel deixa você escolher como abrir a página. O Cloudflare oferece um QR code para ler com o celular, o navegador deste computador (o navegador do Windows no WSL) ou um link para copiar. O Google Drive oferece o navegador ou o link: o Google só volta ao computador que executa o rclone, então o celular não conclui esse login, e em um servidor sem tela o painel explica o túnel SSH. O token do Google nunca aparece na tela.
- **Diagnóstico**: verificação completa com relatório detalhado, status do servidor, logs do Apache em tempo real e manutenção profunda do banco.
- **Segurança**: Fail2ban, firewall UFW (com opção de restringir a porta 8080 do Staff) e troca da senha do banco de dados.
- **Configurações do Koha**: perfis de dimensionamento, avisos por e-mail (agenda do próprio Koha, ativada com `koha-email-enable`), criação de superbibliotecário, SIP2 e Z39.50, relógio e fuso horário.
- **Ferramentas da biblioteca**: a 🪄 Ferramenta de Importação Mágica Maluca, uma entrada só para toda importação (planilhas, MARC, o backup do sistema antigo, arquivos compactados com eles: livros e leitores encontrados e separados sozinhos), desfazer uma importação MARC, pacote de relatórios SQL essenciais, virada do ano letivo (troca de categorias), verificação da qualidade do catálogo e rotinas de privacidade (LGPD). Toda alteração mostra antes uma prévia com a simulação do próprio Koha e é protegida por um backup verificado (veja [Ferramentas da biblioteca](#ferramentas-da-biblioteca)).
- **Brasil: localização** (opcional, nunca aplicado pela instalação nem por agendamento): auditoria de CPF (módulo 11), modelos de etiquetas Pimaco, ficha catalográfica com a referência ABNT do registro, feriados brasileiros no calendário do Koha, relatórios para os censos oficiais (MEC/INEP/IBGE/SNBP) e bibliografias e listagens do acervo pela ABNT NBR 6023 (veja [Brasil: localização](#brasil-localização)). As migrações do Biblivre, SophiA, Pergamum, Biblioteca Fácil e ISIS ficam na [Ferramenta de Importação Mágica Maluca](#-ferramenta-de-importação-mágica-maluca).
- **Mensagens: WhatsApp e Telegram** (opcional): os próprios avisos do Koha (empréstimo, devolução, atraso, vencimento, reserva) entregues por um gateway de WhatsApp próprio (Evolution API ou similar) ou por um bot do Telegram, com os números dos leitores completados e corrigidos no caminho (veja [Mensagens](#mensagens-whatsapp-e-telegram)).
- **Auxílio à catalogação**: notação de autor com a tabela PHA ou Cutter-Sanborn carregada pela biblioteca, consulta à CDD, uma Calculadora Cutter (Cutter-Sanborn ou PHA, com a tabela PHA lida até de um PDF digitalizado) com um botão Cutter na catalogação do Koha e uma página da interface da equipe que substitui um registro pelo biblionumber sem mexer nos exemplares (veja [Auxílio à catalogação](#auxílio-à-catalogação-pha-cutter-sanborn-cdd), [Calculadora Cutter](#calculadora-cutter) e [Substituir um registro MARC](#substituir-um-registro-marc-interface-da-equipe)).
- **Windows 10/11 (WSL 2)**: o Koha em um único computador com Windows, com atalhos Iniciar/Parar que usam o ícone oficial do Koha, ícone de status, notificações do Windows, diagnóstico com um clique e vigia do disco (veja [Windows (WSL 2)](#windows-wsl-2)).
- **Idiomas**: instala os pacotes de idioma do Koha e traduz o próprio painel (22 idiomas).
- **Autoatualização** pelo GitHub com verificação SHA-256.

## Requisitos

| Item | Mínimo |
|------|--------|
| Sistema operacional | Debian 11/12/13 ou Ubuntu 22.04/24.04, 64 bits (amd64 ou arm64, ex.: Oracle Ampere, AWS Graviton, Raspberry Pi 4/5), ou Windows 10/11 pelo WSL 2 (veja [Windows](#windows-wsl-2)) |
| RAM | 2 GB (recomendado 4 GB ou mais; o Elasticsearch precisa de ~1,5 GB a mais) |
| Disco livre | 5 GB (recomendado 10 GB ou mais) |
| Acesso | `root` ou usuário com `sudo` |
| Rede | Acesso à internet para `debian.koha-community.org` |
| Portas | 80 (OPAC) e 8080 (interface do Staff) livres |

## Instalação

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Ou clone o repositório (assim os arquivos de tradução ficam ao lado do script e funcionam sem internet):

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Na primeira execução você escolhe o idioma do painel. Depois selecione **1 – Instalar servidor Koha** e siga o assistente (10 a 30 minutos).

Após a instalação, o painel fica disponível em qualquer lugar com:

```bash
sudo config.sh
```

### Depois de instalar

1. Abra a interface do Staff em `http://IP-DO-SERVIDOR:8080`.
2. Entre com o usuário e a senha do banco de dados mostrados no fim da instalação (também salvos em `/root/koha_credentials.txt`) e conclua o **Web Installer** do Koha.
3. De volta ao painel, crie seu próprio superbibliotecário (**9 – Configurações do Koha > Criar superbibliotecário**).
4. O catálogo público (OPAC) fica em `http://IP-DO-SERVIDOR:80`.

## Windows (WSL 2)

O Koha também pode rodar em um único computador com Windows 10 ou 11. É o caso de bibliotecas pequenas com um só balcão, de treinamentos da equipe e de avaliações. Bibliotecas com vários balcões devem continuar com um servidor Linux dedicado.

O Koha roda dentro de um sistema Debian no **WSL 2** (Subsistema do Windows para Linux), administrado pelo mesmo painel. Pequenas ferramentas em **PowerShell** permitem controlá-lo pelo Windows, sem abrir um terminal.

### O que já funciona no Windows

- **Modo WSL no painel**: o WSL 2 é detectado automaticamente. O WSL 1 é recusado, com explicação.
  - As tarefas do computador ficam com o Windows: sem swapfile, NTP, UFW, Fail2ban ou avahi.
  - O fuso horário é escolhido dentro do Debian durante a instalação, com o fuso do Windows oferecido primeiro. Um fuso diferente continua valendo depois que o WSL reinicia (`useWindowsTimezone=false` em `/etc/wsl.conf`).
  - "Reiniciar servidor" vira **Reiniciar os serviços do Koha**.
  - O systemd precisa estar ativado no WSL (o instalador do Windows faz isso).
  - As telas são sempre em UTF-8, e o instalador e o painel mostram emojis. Quando o Terminal do Windows está instalado (ele já vem no Windows 11), o instalador e o painel de controle abrem nele. O console clássico do Windows não tem fonte de emoji, então num PC sem o Terminal do Windows eles mostram símbolos simples como `[OK]` no lugar de quadradinhos.
  - O lado Windows conversa com o painel pelo arquivo `/etc/koha-easy-install/windows.conf`. Ele é lido com uma lista fechada de chaves e nunca é executado.
- **Rede**: o Apache escuta em todos os endereços, nas portas 80 (catálogo) e 8080 (interface da equipe). O instalador abre as duas portas só para a rede local, no firewall do Windows e, no Windows 11, no firewall do Hyper-V que protege o WSL, e os outros computadores da biblioteca acessam o Koha pelo endereço deste computador. O Windows 11 usa a rede espelhada (mirrored), com `hostAddressLoopback` para que este computador também acesse o Koha pelo próprio endereço. O modo de rede é lido do próprio WSL, não do `.wslconfig`: quando o WSL volta para o NAT (Windows 10, ou um Windows 11 em que a rede espelhada não consegue iniciar), a tarefa *Koha network* aponta o `netsh interface portproxy` para o endereço do Debian toda vez que o Koha inicia, e de volta ao modo espelhado ela remove esse redirecionamento. Os outros computadores podem usar o nome deste computador (`http://<nome-do-pc>:8080/`), que não muda quando o roteador distribui um endereço novo. Para publicar o Koha na internet, use o **Túnel Cloudflare** do painel.
- **Teste da rede da biblioteca**: no fim da instalação, pelo botão **Testar a rede da biblioteca** da janela do Koha e no diagnóstico, o Koha é acessado pelo endereço de rede deste computador, do mesmo jeito que os outros computadores o acessam. O resultado diz se ele respondeu e o que pode estar bloqueando os outros computadores: uma regra de firewall que falta, o redirecionamento de portas que falta no modo NAT, ou outro programa de firewall em que as portas 80 e 8080 também precisam ser liberadas.
- **Janela do Koha**: uma janela nativa do Windows, com visual escuro, aberta pelo ícone **Koha** da área de trabalho, por *Koha - Status* e pelo ícone da bandeja. Ela funciona mesmo quando o Koha não responde, porque pergunta direto ao Debian pelo WSL e nunca depende do servidor web do Koha. No topo fica o logotipo verde do Koha (o nome e o logotipo pertencem à comunidade Koha). A janela, as caixas de diálogo e a dica do ícone Koha trazem o título *Koha descomplicado : instalação e gestão*. O ícone Koha e os outros atalhos de programa mostram o ícone que vem dentro do `KohaEasy.exe`, o programa que eles abrem, e por isso o mantêm depois que o Windows reinicia. Logo abaixo, uma faixa só chama a atenção quando há problema: enquanto todos os componentes funcionam, ela fica verde, com a hora da última verificação e o último backup. Quando um falha, ela fica vermelha e diz qual é (por exemplo "Atenção: MariaDB está fora do ar"), com um botão **Iniciar o Koha** enquanto o Koha está desligado. **Detalhes**, na faixa, abre a lista dos componentes (Debian (WSL), MariaDB, Apache, RabbitMQ, Memcached, koha-common e a resposta HTTP da página da equipe), com um selo vermelho no que falhou. Abaixo vêm o **Acesso rápido** (primeiro a interface da equipe, depois o catálogo público) e o **Painel de Gestão**: o próprio menu do painel, dentro da janela, com um ícone colorido para cada opção (Fluent Emoji Flat, licença MIT, em `windows/icons`). Os grupos ficam à esquerda e as opções do grupo escolhido à direita. Um clique executa uma opção; as setas percorrem a lista, Enter ou a seta para a direita entra em um grupo e Enter executa; a seta para a esquerda ou Esc volta. As opções que alteram dados ou reiniciam parte do Koha (restaurar o banco, trocar o mecanismo de busca, manutenção profunda do banco, trocar a senha do banco, atualizar o sistema) perguntam antes. Cada opção abre uma janela de terminal direto naquela rotina (`installer --run <ação>`), com as perguntas de sempre, e a janela fecha quando ela termina. Depois vêm quatro ações: **Painel de Gestão** (os menus completos no terminal), **Reiniciar Koha** (os serviços do Koha, sem reiniciar o WSL), **Desligar o PC com segurança** (veja abaixo) e **Abrir terminal do Debian**, que abre um shell completo do Debian com o seu usuário do Debian em uma janela própria (Terminal do Windows ou o console clássico) enquanto o Koha está funcionando; lá funcionam o sudo, as senhas e os programas de tela cheia, e fechar a janela ou digitar `exit` encerra tudo o que rodou nela. **Mais ações** reúne Parar o Koha, Reiniciar o Debian e o Koha, Reconstruir índice de busca, Testar a rede da biblioteca e a exportação do diagnóstico. Enquanto o Koha para, a janela mostra em que passo ele está. A janela verifica de novo a cada 30 segundos, ou quando você aperta F5. Nos 45 segundos depois que o Windows inicia, um Koha que ainda está subindo aparece como iniciando, não como falha, e não gera notificação de falha. Ela também mostra os endereços que os outros computadores usam.
- **Sem janelas de console**: os atalhos, o ícone da bandeja e as tarefas que rodam ao entrar no Windows e mantêm o Debian ligado iniciam pelo `KohaEasy.exe`, um pequeno inicializador que o instalador compila no próprio computador a partir do código-fonte em C# (`windows/KohaEasy.Launcher.cs`) com o compilador que já vem no Windows, então nada é baixado. É um programa do Windows que inicia o PowerShell sem janela nenhuma, e assim o Terminal do Windows nunca abre uma janela vazia ao entrar no Windows. Ele também dá à janela do Koha, à entrada do menu Iniciar e às notificações o nome e o ícone do próprio Koha na barra de tarefas. Se o Windows não deixar que ele rode (Controle Inteligente de Aplicativos ou um antivírus), tudo inicia pelo Windows Script Host (`KohaEasy.Hidden.js`, que inicia o PowerShell já oculto) e, depois dele, por um console oculto. Cada execução do instalador tenta de novo, do melhor para o pior. O que for iniciado do jeito antigo, com um console visível (um atalho, uma entrada de início ou uma tarefa de uma versão anterior), reinicia sozinho do jeito oculto na hora, e esse console fecha. O instalador confere que o ícone **Koha** está mesmo na sua área de trabalho (a que o Explorer mostra, inclusive a do OneDrive) e no menu Iniciar antes de dizer que está. Quando o Windows recusa um deles, ele diz onde o Koha está e mostra o motivo dado pelo Windows, que também fica no log da instalação.
- **Janela do painel de controle**: o painel de controle e o terminal do Debian abrem em uma janela própria (o Terminal do Windows, quando está instalado), que fecha assim que você sai com **Sair**: o que ainda estiver preso àquela janela é parado antes, e ela nunca fica aberta e preta. Se o painel terminar com um erro, a janela espera o Enter para que a mensagem possa ser lida.
- **Ícone e atalhos do Koha**: um ícone **Koha** na área de trabalho e no menu Iniciar. Ao clicar nele, inicia o que não estiver rodando, sem janela de console: o ícone de status e o próprio Koha (a janela do Koha então mostra que ele está iniciando). Também recoloca a entrada de início com o Windows e as tarefas agendadas, se alguém as apagou. Depois abre a janela do Koha, ou traz para a frente a que já está aberta, então clicar de novo nunca inicia nada duas vezes. Todos os atalhos, inclusive os da pasta *Koha* do menu Iniciar, têm o ícone oficial `koha.ico`, e nenhum abre janela de console. A pasta traz:
  - Interface da equipe, Catálogo público, Painel de controle e Pasta de backups
  - **Iniciar**, **Parar** e **Reiniciar**
  - Status, Exportar diagnóstico e Ícone de status
- **Iniciar e parar**: o Koha pode iniciar sozinho quando você entra no Windows ou só quando você clica em *Koha - Iniciar*. Isso pode ser trocado a qualquer momento pelo menu do ícone. Depois de **Parar**, o Koha fica desligado até você iniciá-lo de novo, e nada o liga sem você saber.
- **Paradas limpas e reparo depois de uma queda de energia**: Parar, Reiniciar e todos os outros passos que param o Debian primeiro param os serviços do Koha dentro dele, em ordem (o servidor web, depois a fila e o cache, depois o MariaDB), e só então deixam o WSL parar o Debian. Assim o banco de dados e o índice de busca nunca são cortados no meio de uma gravação. Uma parada limpa deixa uma marca. Quando o Debian inicia sem ela (queda de energia, desligamento forçado do Windows, travamento), o Koha verifica o banco de dados, faz um backup novo e atualiza o índice de busca do Zebra, reconstruindo-o do zero quando preciso, e uma notificação do Windows conta como foi. Servidores Linux ganham a mesma verificação depois de um reinício inesperado.
- **Proteções de dados**: as proteções do MariaDB contra falhas (doublewrite, gravação do log a cada commit, um arquivo por tabela, sem log binário) ficam fixadas em `98-koha-durability.cnf`; o journal do sistema fica limitado a 100 MB e um mês, os logs do painel são rotacionados, e os timers semanais de rotação de logs e de TRIM ficam ligados. No Windows, quando o Windows desliga, reinicia ou sai da conta com o Koha em funcionamento, o ícone da bandeja para o Koha de forma limpa primeiro: o Windows avisa a ele antes dos outros programas, e ele faz a parada por um `wsl.exe` sem console, porque o Windows fecha os programas de console quando a sessão termina; uma queda de energia ou um desligamento forçado continuam dependendo do reparo acima. O diagnóstico avisa quando o esvaziamento do cache de gravação do Windows está desligado no disco que guarda o Koha. A janela do Koha tem o botão **Reconstruir índice de busca** em **Mais ações**.
- **Desligar o PC com segurança**: um clique no fim do dia, pela janela do Koha, pelo menu do ícone da bandeja ou por *Koha - Desligar o PC com segurança* no menu Iniciar. Uma janelinha marca cada passo assim que ele acontece (a interface web e o mecanismo de busca Zebra, a fila de mensagens e o cache, o banco de dados, a gravação de tudo no disco, o fechamento do Debian e do disco virtual dele), e depois o Windows desliga ou reinicia, como você escolheu. Nada corre contra o Windows: o Koha para por completo antes de o Windows ser chamado. Se o Koha não parar em 60 segundos, o Windows desliga mesmo assim e o Koha se repara na próxima vez que iniciar. O Koha volta a iniciar na próxima entrada no Windows, como sempre. Quando o Windows é desligado do jeito comum, a parada feita pelo ícone da bandeja, descrita acima, continua valendo, e agora ela para o WSL inteiro, para que o disco virtual do Debian seja fechado antes de o Windows desligá-lo.
- **Ícone de status (área de notificação)**: o ícone do Koha com um ponto colorido ao lado, com borda branca (verde funcionando, amarelo iniciando, vermelho sem resposta, cinza parado), desenhado no tamanho que a escala da tela pede. Se o `koha.ico` não puder ser lido ao entrar no Windows, entra o ícone de dentro do `KohaEasy.exe`, e o log diz o motivo. Um clique duplo, ou **Status dos serviços**, abre a janela do Koha. O menu também abre a interface da equipe, o catálogo e o painel de controle, inicia e para o Koha, reinicia os serviços do Koha, reconstrói o índice de busca e exporta o diagnóstico. **Fechar este ícone** pergunta se o Koha continua funcionando em segundo plano ou se para também. Se o ícone travar ou for encerrado de outro jeito com o Koha funcionando, ele volta em até um minuto. Na primeira vez que inicia, ele pede ao Windows 11 para ficar ao lado do relógio, e não entre os ícones ocultos (^), e uma notificação diz onde ele está.
- **Notificações do Windows**:
  - o Koha para de responder, para sem aviso ou volta a funcionar
  - o Koha não foi desligado corretamente, e o que o reparo feito depois encontrou
  - o backup noturno é concluído (dá para desligar esse aviso), falha ou não roda há 36 horas
  - o espaço em disco fica baixo
- **Diagnóstico com um clique**, os dois prontos para enviar a quem dá suporte à biblioteca, sem senhas, tokens nem chaves:
  - `diagnostico_koha.txt` na área de trabalho: versões do WSL e do Windows, cada serviço, os últimos erros dos serviços dentro do Debian e os logs do Windows dos últimos dias. Não liga nada, então funciona também com o Koha fora do ar.
  - um `.zip` na área de trabalho com os logs completos do WSL, do Windows, do Apache, do MariaDB, do Koha e do painel, além do status do sistema. Nenhum arquivo de configuração entra.
- **Vigia do disco**: avisa quando a unidade que guarda o disco virtual do Koha (`ext4.vhdx`) tem menos de 10 GB livres, e em nível crítico abaixo de 5 GB. Quando o disco virtual tem muito espaço sem uso, **Compactar** devolve esse espaço ao Windows (pede permissão de administrador).
- **Idiomas**: as ferramentas do Windows usam os 22 idiomas do painel.

### Como instalar no Windows

Abra o **PowerShell** (menu Iniciar, digite *PowerShell*; não precisa ser como administrador), cole esta linha e tecle Enter:

```powershell
[Net.ServicePointManager]::SecurityProtocol='Tls12'; irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Se preferir dois cliques, baixe o [**Install-Koha.cmd**](https://github.com/PauloFBaldiFH/koha.nexus/blob/main/windows/Install-Koha.cmd) (**Download raw file**, a seta no canto superior direito da página) e dê dois cliques nele. Ele roda exatamente a mesma linha, então a instalação é idêntica. O arquivo não é assinado: se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações > Executar assim mesmo**. É texto puro, então você pode abri-lo no Bloco de Notas e lê-lo antes.

O instalador faz todo o resto e mostra cada etapa em linguagem simples:

1. Verifica o computador: Windows 10 versão 2004 ou mais recente, ou Windows 11; 64 bits; pelo menos 4 GB de memória (8 GB recomendados); pelo menos 10 GB livres no C:; virtualização ativada na BIOS.
2. Pede um nome de usuário e uma senha para o Debian, antes de instalar qualquer coisa. Você os usa para abrir o Debian e com `sudo`; não são o login da equipe no Koha. A senha nunca é gravada nem registrada no log, e é pedida de novo se o Windows reiniciar antes de o Debian ficar pronto.
3. Instala o WSL 2. O Windows pede permissão uma vez. Se o Windows precisar reiniciar, o instalador continua sozinho quando você entrar de novo.
4. Pede ao WSL que instale o Debian da lista oficial do WSL da Microsoft como `koha` em `C:\KohaEasy\wsl`. Em um WSL mais antigo, baixa a mesma imagem, confere o SHA-256 e a importa.
5. Cria o seu usuário do Debian com permissão de `sudo` e ativa o systemd. No Windows 11 22H2 ou mais recente, também acrescenta a rede espelhada (mirrored) e o `hostAddressLoopback` ao seu `.wslconfig`, mantendo as suas configurações e uma cópia de segurança. Depois reinicia o Debian e espera o systemd estar funcionando por completo antes de seguir.
6. Antes de instalar o Koha, compila o `KohaEasy.exe` e cria as tarefas agendadas, o ícone **Koha** (área de trabalho e menu Iniciar) e o ícone de status, para que haja um jeito de abrir o Koha mesmo se o passo seguinte parar no meio. Ele diz onde o ícone do Koha ficou, com o motivo dado pelo Windows quando um atalho não pôde ser criado. Depois abre o painel de controle do Koha. As ferramentas do próprio painel são baixadas com uma única linha de status ("Baixando dependências do painel..."); a saída do gerenciador de pacotes vai só para `/var/log/koha-easy-install/apt.log`, ou para a tela com `--verbose`. Escolha o idioma, depois **1 – Instalar servidor Koha** (ele pergunta o fuso horário), e saia do painel com **Sair** quando terminar. Se o Koha não ficar totalmente instalado, o instalador diz qual verificação falhou.
7. Pergunta se o Koha deve iniciar quando você entrar no Windows. Depois compila o `KohaEasy.exe`, cria as tarefas agendadas, os atalhos e o ícone de status, coloca o ícone do Koha na entrada do Debian no menu Iniciar e no perfil do Terminal do Windows, abre o Koha para a rede da biblioteca (o Windows pede permissão uma vez), inicia o Koha, testa a rede da biblioteca e abre a interface da equipe. Mostra também os endereços que os outros computadores usam, pelo nome deste computador e pelo endereço dele. A partir daí, o ícone **Koha** na área de trabalho inicia o Koha quando ele está desligado e abre a janela do Koha. Rodar o comando de uma linha de novo é seguro: ele atualiza o `KohaEasy.exe`, as tarefas agendadas, os atalhos e o ícone de status, atualiza as configurações de rede da biblioteca feitas por uma versão anterior (o Windows pede permissão uma vez), termina uma instalação do Koha que parou no meio (dizendo qual verificação falhou) e, se o Koha não iniciar, mostra o que o Debian informa e salva o diagnóstico na área de trabalho. Quando o `.wslconfig` recebe configurações novas, ou o Koha ainda roda com a janela de uma versão anterior, o Koha é parado de forma limpa e iniciado de novo. Se o ícone do Koha ou o ícone de status ainda estiver faltando, este comando verifica cada parte passo a passo, mostra cada erro por completo e salva o resultado em `C:\KohaEasy\logs\diagnose-<data>.txt`:
   `irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex`

Pode rodar de novo sem medo: ele continua da última etapa concluída. Uma instalação feita por uma versão anterior, em que o Debian se chamava `KohaEasy`, passa a se chamar `koha`, com os dados mantidos. O usuário e a senha de primeiro acesso ficam no painel de controle, opção 2. Tudo fica em `C:\KohaEasy`, e o log do instalador em `C:\KohaEasy\logs`.

O comportamento em um Windows real (o instalador, notificações, ícone de status, Agendador de Tarefas, `KohaEasy.exe`, o teste da rede da biblioteca e compactação do disco) ainda está sendo conferido em computadores físicos, então avise se algo parecer estranho.

## Menu principal

| # | Opção | O que faz |
|---|-------|-----------|
| 1 | Instalar servidor Koha | Instalação e ajuste completos |
| 2 | Ver credenciais de primeiro acesso | Endereços, usuário e senha |
| 3 | Restaurar banco de dados | Importa um backup `.sql` / `.sql.gz` |
| 4 | Central de backup | Backup manual, backup na nuvem, teste de integridade |
| 5 | Motor de busca e indexação | Zebra ⇄ Elasticsearch, reparo de índices |
| 6 | Publicar o sistema na internet | Túnel Cloudflare, SSL, Google Search Console |
| 7 | Diagnóstico e manutenção | Status, verificação, logs, otimização |
| 8 | Central de segurança | Fail2ban, firewall, troca de senha |
| 9 | Configurações e parâmetros do Koha | Dimensionamento, e-mail, superbibliotecário, SIP2/Z39.50, relógio |
| 10 | Ferramentas da biblioteca | Ferramenta de Importação Mágica Maluca, desfazer uma importação MARC, relatórios SQL, virada do ano letivo, qualidade do catálogo, privacidade (LGPD), Brasil: localização, mensagens por WhatsApp / Telegram, auxílio à catalogação, substituir um registro MARC, consulta à CDD, ligar ou desligar os plugins do Koha, Calculadora Cutter |
| 11 | Ferramentas gerais | htop/nethogs, navegador de terminal, gerenciador de arquivos |
| 12 | Agendamentos e tarefas (cron) | Ver, entender, regenerar ou editar as tarefas automáticas |
| 13 | Idiomas do Koha e do painel | Pacotes de idioma do Koha e idioma do painel |
| 14 | Central de atualizações | Atualizações do sistema/Koha e do painel |
| 15 | Sobre | Informações do projeto e apoio |
| 16 | Reiniciar servidor | |
| 17 | Sair | |

As janelas usam um tema escuro, largura fixa e se adaptam a terminais pequenos. Para as cores padrão do newt em um terminal monocromático, abra o painel com `NO_COLOR=1`.

## Ferramentas da biblioteca

Tarefas do dia a dia da equipe da biblioteca, feitas com as próprias ferramentas de linha de comando do Koha, como o usuário da instância (`koha-shell library -c ...`). Tudo o que altera dados segue os mesmos passos: a trava de backup/restauração (nenhum backup noturno ou restauração roda no meio), uma **prévia** (a simulação do próprio Koha), uma confirmação explícita, um **backup `PRE-*` verificado** em `/var/backups/koha_sql` e só então a execução real. As ferramentas nunca param os serviços do Koha, e o backup `PRE-*` desfaz qualquer alteração (**Restaurar banco de dados**).

| Ferramenta | Scripts do Koha | Prévia | Backup |
|------------|-----------------|--------|--------|
| 🪄 Ferramenta de Importação Mágica Maluca: qualquer arquivo, pasta ou arquivo compactado com registros, exemplares, leitores, empréstimos ou reservas ([abaixo](#-ferramenta-de-importação-mágica-maluca)) | `stage_file.pl`, `commit_file.pl`, `import_patrons.pl` | A prévia da própria ferramenta, depois o relatório de preparação e a simulação de leitores do Koha | `PRE-IMPORT`, `PRE-PATRONS`, `PRE-CIRCULATION` |
| Desfazer uma importação MARC | `commit_file.pl --revert` | Registros e exemplares do lote | `PRE-UNDO-IMPORT` |
| Pacote de relatórios SQL essenciais: 8 relatórios somente leitura (mais emprestados, atrasos com contato, nunca emprestados, aquisições recentes, cadastros a vencer, empréstimos por mês, exemplares sem código de barras/número de chamada, perdidos), marcados para que atualizar ou remover o pacote nunca mexa em outros relatórios | — (`saved_sql`) | Cada consulta é testada nesta versão do Koha | `PRE-REPORTS` |
| Virada do ano letivo: mover leitores entre categorias (todos, acima da idade da categoria ou cadastrados antes de uma data) | `update_patrons_category.pl` | Simulação nativa com a lista de leitores | `PRE-PATRONS` |
| Verificação da qualidade do catálogo (somente leitura) | `search_for_data_inconsistencies.pl` | — | — |
| Privacidade (LGPD): anonimizar o histórico antigo de empréstimos e reservas | `batch_anonymise.pl` | Contagens calculadas como o Koha faz | `PRE-PRIVACY` |
| Privacidade (LGPD): excluir leitores expirados que não pegaram nada desde então (confirmação digitada) | `delete_patrons.pl` | Simulação nativa | `PRE-PRIVACY` |

Cada execução fica registrada em `/var/log/koha-easy-install/tools/` (só o root lê: os logs podem ter nomes de leitores), que também podem ser vistos pelo menu.

### 🪄 Ferramenta de Importação Mágica Maluca

**Ferramentas da biblioteca > Ferramenta de Importação Mágica Maluca**: não questione, só jogue aqui o que você quer importar. É a entrada única para toda importação: o acervo, os exemplares, os leitores e os empréstimos e reservas do sistema antigo, vindos de um arquivo, de uma pasta ou de um arquivo compactado com tudo isso junto. Coloque-o na pasta `importar` da pasta pessoal do usuário do painel (no Windows também em `C:\KohaEasy\Importar`, criada na primeira vez que a ferramenta abre): o que estiver lá aparece primeiro, e **Outro arquivo** abre o explorador de arquivos.

O que ela lê, reconhecido pelos bytes de cada arquivo, nunca só pelo nome:

| Entrada | Como é lida |
|---------|-------------|
| Planilhas: CSV / TSV (qualquer separador; UTF-8, Windows-1252 ou Latin-1), Excel `.xlsx` e `.xls`, LibreOffice `.ods`, dBase `.dbf` com o memo `.dbt` / `.fpt` | Cada aba é uma tabela. Cada coluna recebe uma nota para cada campo MARC 21 e de leitor a partir do cabeçalho (nomes em português ou inglês, 40 %) e dos valores (60 %: dígitos verificadores de ISBN e CPF, datas, e-mails, números de chamada...). Uma tabela é de livros, de leitores, de empréstimos ou mista; um nome de pessoa é o autor ao lado de títulos e o leitor ao lado de CPFs, então autores nunca viram leitores. Uma linha com um livro e o leitor dele (uma aba de empréstimos) manda o livro para o catálogo e o leitor para os leitores. Datas de planilha e datas seriais do Excel são convertidas; o `.xls` precisa do `python3-xlrd`, oferecido quando aparece um arquivo assim |
| MARC 21: ISO 2709 (`.mrc`, `.iso`) e MARCXML | Os caracteres são convertidos para UTF-8 com o `yaz-marcdump` (de Latin-1 ou MARC-8; o pacote `yaz` é oferecido se faltar). Registros já no leiaute do Koha mantêm o 952. Exemplares guardados num campo de item de outro sistema (949, 950, 990, ou o 852 de localização do MARC 21) viram um 952 cada, movidos com o MARC::Record do próprio Koha: no 852 cada subcampo é lido pelo seu significado no MARC 21, e num 9XX pelos seus valores (código de barras, tombo, número de chamada, biblioteca, tipo de item, localização na estante, exemplar, volume, data de aquisição, preço, situação extraviado/baixado/danificado/só consulta, notas), então o leiaute de qualquer sistema é entendido. Biblioteca, tipo de item e localização só são usados quando o Koha os tem (códigos ou nomes); senão, e quando o campo não os traz, valem a biblioteca e o tipo de item escolhidos para a importação. A prévia mostra para onde vai cada subcampo e quantos valores o Koha não tinha. Outro 9XX repetido na maioria dos registros, ou um dos usuais sem numeração, é perguntado, mostrando como cada subcampo foi lido |
| Banco de dados do Biblioteca Fácil | Acervo, leitores, empréstimos e reservas (detalhes abaixo) |
| Acervo do ISIS | Acervo (detalhes abaixo) |
| Arquivos compactados: `.zip`, `.tar` (também `.tar.gz`, `.tar.bz2`, `.tar.xz`) e arquivos `.gz`, `.bz2`, `.xz` | Descompactados dentro da pasta de trabalho com limites: nenhum caminho fora dela, sem links nem dispositivos, limites de tamanho e de quantidade, bombas zip recusadas, compactados dentro de compactados até três níveis |
| Um backup do Koha (dump MariaDB de um banco do Koha) | Nunca é importado: ele substitui o catálogo inteiro, então vai para **Restaurar banco de dados**, que o testa antes em um banco temporário. Num arquivo compactado com outros arquivos, o painel pergunta se é para restaurá-lo ou importar os outros |

O que ela não consegue ler aparece com o que fazer: texto `.mrk` do MarcEdit (salve como `.mrc`), um arquivo mestre do CDS/ISIS (exporte a base no WinISIS como ISO 2709), uma exportação PostgreSQL em formato custom (exporte de novo como SQL simples) ou um dump SQL de outro sistema.

Como corre uma importação:

1. **Perguntas, só quando precisa.** Uma coluna sobre a qual a ferramenta não tem certeza (confiança abaixo de 0,85) é perguntada com valores de exemplo, no idioma do painel. Também são perguntados o conjunto de caracteres quando o texto fica legível em mais de um, ISBNs compartilhados por títulos diferentes e um campo de exemplar desconhecido. As respostas sobre as colunas ficam guardadas (`/etc/koha-easy-install/import-profiles/`), então o próximo arquivo com as mesmas colunas não precisa de pergunta.
2. **Registros e exemplares.** As linhas do mesmo livro viram um registro MARC 21 com um exemplar no 952 por item: a chave da obra é o ISBN-13 quando o dígito verificador está certo, senão título, sobrenome do primeiro autor, editora e edição; o volume sempre entra, então volumes nunca se juntam. A coluna de código de barras, ou então o tombo, vira o código de barras (um repetido vira `-2`, `-3`... com uma nota no exemplar), o tombo também fica como número de inventário, uma coluna de quantidade de exemplares gera essa quantidade de itens, CDD + Cutter formam o número de chamada, e o tipo de material é o do exemplar quando o arquivo traz um tipo do Koha, senão o que você escolher.
3. **Leitores.** Uma linha só vira leitor com um identificador pessoal: um CPF válido, um e-mail, um número de cartão de uma tabela de leitores, ou data de nascimento com endereço. Os CPFs são verificados (módulo 11) e um CPF ou número de cartão usado duas vezes é recusado com a linha; o CPF vira o número do cartão quando não há um e fica num atributo de leitor com código `CPF` quando esse tipo existe.
4. **Prévia.** Nada é gravado no Koha até aqui: a ferramenta mostra o que achou em cada arquivo, as colunas e para onde vão, as contagens, uma amostra dos registros e as linhas recusadas com o motivo.
5. **Gravação com as ferramentas do próprio Koha,** como todas as outras: os registros pela importação MARC em etapas (`stage_file.pl` / `commit_file.pl`; registros iguais mantidos, substituídos ou sempre novos), os leitores pelo `import_patrons.pl` com a simulação dele, os empréstimos e reservas do Biblioteca Fácil numa única transação. Cada parte tem a sua confirmação e o seu backup `PRE-*` verificado, e os registros podem ser desfeitos em **Desfazer uma importação MARC**.
6. **Resumo**: "Importados com sucesso X registros bibliográficos, Y exemplares e Z leitores, sem nenhum mapeamento manual", ou quantas perguntas foram respondidas.

A ferramenta é o pacote Python `kei_import` (só a biblioteca padrão e pacotes do Debian), que o painel grava na sua pasta de trabalho e roda como o usuário da instância pelo `koha-shell`, como as ferramentas do próprio Koha. Os arquivos do Biblioteca Fácil e do ISIS e os campos de exemplar do MARC de outros sistemas são decodificados pelos leitores Perl do painel, com o MARC::Record do Koha:

| Leitor | Como funciona | Prévia | Backup |
|--------|---------------|--------|--------|
| Banco de dados do Biblioteca Fácil (backup `.bkp`, ou a pasta de dados dele com o `T09_ACER.dat`) | O leitor do painel (Perl) lê as tabelas do próprio programa (DBISAM 4, `T01_USUA` a `T15_RESE`, formato em [docs/biblioteca-facil-format.md](docs/biblioteca-facil-format.md)) conferindo o checksum de cada registro; o que o programa excluiu fica de fora. Três etapas: **acervo** (exemplares com o mesmo título, subtítulo, edição, ano, editora, ISBN e autores viram um registro MARC 21: autores na ordem do `T10_AUAC`, editora e cidade, CDD, CDU, Cutter, palavras-chave, classificação literária, índice do `T12_INDC`, idioma; um exemplar no 952 por item do acervo, com o tombo como código de barras, `BF<número>` quando o tombo falta ou se repete, exemplar, volume, localização, data de aquisição, baixa e "não emprestar"), depois a importação MARC; **leitores** (número do cartão = código do leitor, CPF verificado e guardado no atributo `CPF` quando esse tipo existe, turma e turno em sort1/sort2, RG, pais e observações nas notas do leitor, leitores desativados com bloqueio), depois o `import_patrons.pl`; **empréstimos e reservas** (em aberto no `issues`, devolvidos no `old_issues`, reservas ainda válidas no `reserves`, ligados pelo número do cartão e pelo código de barras, numa única transação; o que já está no Koha é pulado). Operadores e senhas não são migrados | Tabelas, contagens, erros de checksum, as regras de empréstimo do programa antigo e uma amostra dos registros; depois o relatório de preparação do Koha, a simulação dos leitores e os empréstimos e reservas que podem ser ligados | `PRE-IMPORT`, `PRE-PATRONS`, `PRE-CIRCULATION` |
| Acervo do ISIS (backup PostgreSQL: `.backup` / `.sql`, também gzip, bzip2, zip ou dumps com `INSERT`) | O leitor do painel (Perl) lê o `pg_dump` do banco do ISIS (formato e regras em [docs/isis-format.md](docs/isis-format.md)): o lixo antes e depois do dump fica de fora, a codificação é detectada e as colunas são reconhecidas pelo nome. Um registro MARC 21 por MFN (autores, marcas `<artigo>` de caracteres a ignorar, local / editora / ano separados da imprenta, CDD e Cutter, assuntos das listas `<A><B>` ou com `;`) com um exemplar no 952 por tombo do campo `registro`: exemplares separados por hífens, vírgulas e circunflexos do ISIS (`^f`), volumes (`v1`, `I`, `1ª série`) no $h, intervalos (`669 a 672`) expandidos, letras soltas, `$` e números de chamada digitados no campo descartados, `(Baixa)` como baixa, `ISIS<mfn>` quando não há tombo e `ISIS<mfn>-<n>` quando ele se repete, o campo como foi digitado guardado na nota interna; a tabela de ocorrências acrescenta notas e marca exemplares extraviados. Texto limpo de `Informação não encontrada`, caracteres de controle e `Ẃ` no lugar de `ª`. A exportação não tem leitores nem empréstimos | Tabelas, colunas e para onde vão, cada contagem da limpeza e os MFN a conferir, uma amostra dos registros; depois o relatório de preparação do Koha | `PRE-IMPORT` |

- Os campos de exemplar do Biblivre, SophiA e Pergamum seguem o leiaute de exportação mais comum desses sistemas; a prévia mostra o resultado antes de qualquer gravação.
- A nota das colunas foi construída a partir dos nomes de coluna usuais dos programas de biblioteca e das planilhas brasileiras, e testada só com arquivos sintéticos. A prévia lista cada coluna, para onde vai e as que ficaram de fora, então confira antes de confirmar.
- A leitura do banco de dados do Biblioteca Fácil foi construída a partir de um backup do banco modelo vazio do programa. As tabelas de empréstimos, reservas e leitores foram conferidas só com um backup sintético, então compare as contagens da prévia com o programa antigo antes de confirmar.
- A leitura do ISIS foi construída a partir da exportação de uma biblioteca. Títulos com um circunflexo no meio podem ficar com uma letra de subcampo do ISIS grudada na palavra seguinte, por isso a prévia lista os MFN deles para conferir no Koha.

### Brasil: localização

**Ferramentas da biblioteca > Brasil: localização**. Nada aqui é aplicado durante a instalação nem por agendamento: cada opção só age quando você a escolhe, segue os mesmos passos das outras ferramentas (trava, prévia, confirmação, backup `PRE-*` verificado) e pode ser desfeita. As migrações de outros sistemas ficam na [Ferramenta de Importação Mágica Maluca](#-ferramenta-de-importação-mágica-maluca).

| Ferramenta | Como funciona | Prévia | Backup |
|------------|---------------|--------|--------|
| Verificar CPFs dos leitores (somente leitura) | Número do cartão, usuário, sort1/sort2 ou o atributo `CPF`: válidos, inválidos, compartilhados por dois leitores | — | — |
| Modelos de etiquetas Pimaco | Folhas 6180, 6181, 6287 (Carta) e A4256, A4251 (A4) mais 3 leiautes (lombada, código de barras, título e código de barras) no criador de etiquetas do Koha; atualiza ou remove só os próprios modelos | Resumo antes da alteração | `PRE-LABELS` |
| Ficha catalográfica | Folhas de estilo que envolvem a visualização de detalhes padrão do Koha (OPAC e interface da equipe, uma por idioma instalado) e acrescentam a ficha abaixo do registro, com botão de impressão; configuradas em `OPACXSLTDetailsDisplay` / `XSLTDetailsDisplay`. Os valores anteriores são guardados e **Ocultar a ficha** os devolve; os arquivos são regravados sempre que o painel abre, acompanhando as atualizações do Koha | Valores antigos e novos | `PRE-FICHA` |
| Feriados brasileiros no calendário | Feriados nacionais de um ano, Carnaval (segunda e terça), Sexta-feira Santa e Corpus Christi (Páscoa pelo algoritmo de Meeus/Jones/Butcher) e um feriado municipal opcional, para uma biblioteca ou todas; os dias que já estão no calendário são ignorados e **Remover** tira só os dias adicionados pelo painel | Datas com o dia da semana | `PRE-CALENDAR` |
| Relatórios para os censos oficiais (MEC/INEP/IBGE) | 10 relatórios SQL somente leitura nos relatórios salvos do Koha com os números pedidos pelo Censo Escolar e pelo Censo da Educação Superior (INEP), pelas pesquisas do IBGE, pelo cadastro do SNBP e pelas avaliações de curso do MEC: resumo do ano, acervo ativo por tipo de material e biblioteca e por classe da CDD, exemplares incorporados, circulação por mês, empréstimos por tipo de material e categoria de leitor, leitores por categoria, sexo e faixa etária, perdas e baixas (com o valor de reposição), idade do acervo por classe da CDD e candidatos a descarte. O Koha pede o ano ao executar o relatório. Instalados e removidos separadamente do pacote essencial (marca `[koha-easy-installer-censo:...]`) | Os relatórios, novos ou atualizados; um relatório que o esquema do Koha não consegue executar é ignorado | `PRE-CENSO` |
| Referências e bibliografias ABNT (somente leitura) | Referências pela ABNT NBR 6023:2018 montadas a partir dos registros MARC 21 (livros, capítulos e artigos pelo 773, teses pelo 502, documentos on-line pelo 856; SOBRENOME, Prenomes; até três autores, depois *et al.*; organizadores; entrada pelo título com a primeira palavra em maiúsculas; `[S. l.]`, `[s. n.]`; título do livro ou do periódico em negrito), em ordem alfabética, a partir de uma lista do Koha, dos exemplares incorporados num período, de uma classe do número de chamada, de todo o acervo de uma biblioteca ou de números de registro. Gravadas em HTML com a apresentação da NBR 14724 (A4, Times 12, espaço simples, uma linha em branco entre as referências; abre no Word ou no LibreOffice) e em texto simples, opcionalmente com os números de chamada e exemplares sob cada referência (listagem do acervo) | As primeiras referências | — |

- As medidas das etiquetas são as equivalentes Avery de cada folha Pimaco: faça um teste de impressão em papel comum e ajuste o modelo no Koha se a impressora deslocar a página.
- Na página do registro a ficha começa fechada, atrás de **Mostrar a ficha catalográfica (AACR2)**, e abre com um clique.
- A ficha segue o leiaute AACR2 usado nas bibliotecas brasileiras (coluna do número de chamada, recuo francês, assuntos numerados, entradas secundárias em algarismos romanos). Abaixo dela vem a referência do registro pela ABNT NBR 6023 (elementos essenciais), para os leitores copiarem.
- Os relatórios dos censos contam o que o Koha registra: a consulta local depende das devoluções de *uso local* do Koha, sexo e faixa etária dependem desses campos do leitor e a classe da CDD vem dos três primeiros dígitos do número de chamada. Confira cada número com o formulário do censo antes de enviá-lo.
- Carnaval e Corpus Christi são ponto facultativo, não feriados nacionais: remova-os em Ferramentas > Calendário se a biblioteca abrir. O Dia da Consciência Negra (20/11) entra a partir de 2024.

### Mensagens: WhatsApp e Telegram

**Ferramentas da biblioteca > Mensagens: WhatsApp e Telegram**. O Koha já escreve os avisos (empréstimo, devolução, atraso, vencimento, reserva) e entrega os do tipo SMS ao driver SMS::Send indicado na preferência `SMSSendDriver`. O painel instala um driver assim (`SMS::Send::KohaEasy::Gateway`): cada aviso vai pelo Telegram quando o leitor vinculou o bot da biblioteca, senão pelo WhatsApp. Nada muda no Koha até **Enviar os avisos do Koha** ser ligado, e desligar devolve o `SMSSendDriver` anterior (backup `PRE-MESSAGING` verificado nos dois sentidos).

| Opção | O que faz |
|-------|-----------|
| Gateway de WhatsApp | Um gateway próprio da biblioteca: Evolution API v2 (`POST /message/sendText/<instância>`, cabeçalho `apikey`) ou outro que aceite `{"number", "to", "text"}` com token Bearer |
| Bot do Telegram | O token do @BotFather é verificado com o Telegram (`getMe`). Os leitores abrem o bot, tocam em Iniciar e compartilham o próprio contato; uma tarefa a cada dois minutos vincula a conversa ao número (`/stop` desfaz) |
| Código do país e DDD | Os números são completados e corrigidos antes do envio: código do país (Brasil por padrão, ou qualquer outro), DDD para números sem ele, prefixos de operadora e o 0 retirados, e o 9º dígito dos celulares brasileiros acrescentado |
| Enviar uma mensagem de teste | Pelo mesmo caminho SMS::Send que o Koha usa, como o usuário da instância |
| O que o Koha precisa | Verifica o `SMSSendDriver`, as versões SMS dos avisos, as regras de atraso com SMS e os leitores com número e preferências de SMS; oferece criar versões SMS curtas dos avisos que não têm (`PRE-NOTICES`) |
| Verificar os telefones dos leitores | Relatório somente de leitura com as mesmas regras; os números corrigidos só são gravados após confirmação (`PRE-PHONES`) |

As configurações (com os tokens) ficam em `/etc/koha/sites/library/kei-messaging.conf`, legível só pelo root e pelo Koha. Com os avisos ligados, a fila de SMS também é enviada a cada dois minutos (`/etc/cron.d/koha_messaging`).

### Auxílio à catalogação: PHA, Cutter-Sanborn, CDD

**Ferramentas da biblioteca > Auxílio à catalogação**, somente leitura para o catálogo.

- **Notação de autor**: a entrada imediatamente anterior ao nome na tabela, a inicial do sobrenome, o número e a inicial do título (o artigo inicial nunca conta, e título começando com "l" leva L maiúsculo); prefixos lidos como uma só palavra (La Fonte, O'Donnel) e M' / Mc como Mac; instituições pela primeira palavra e obras anônimas pela primeira palavra do título, como na explicação da tabela PHA. A partir de um registro do catálogo, lê o 100 / 110 / 111, o 245 (com o indicador de caracteres a desprezar) e o 082, e lista os números de chamada que já usam o mesmo número naquela classe, com os números livres imediatamente antes e depois.
- **As tabelas não são distribuídas com o painel**: a Tabela PHA (Heloísa de Almeida Prado, T. A. Queiroz) e as tabelas Cutter-Sanborn têm direitos autorais. Cada biblioteca carrega o próprio exemplar como arquivo de texto (uma entrada e o número por linha; as linhas da PHA podem ser digitadas como estão impressas, entrada - número - entrada; o PDF do livro da PHA também é lido, veja [Calculadora Cutter](#calculadora-cutter)). O arquivo é conferido antes de ser guardado: entradas por letra, números fora de ordem (erros de digitação) e entradas repetidas.
- **CDD**: as dez classes principais vêm embutidas; a biblioteca pode carregar a própria tabela (número e descrição por linha) para pesquisar por número ou por palavra, e toda consulta mostra também como o catálogo já usa o número.

### Substituir um registro MARC (interface da equipe)

**Ferramentas da biblioteca > Substituir um registro MARC** instala o `marc_replace.pl` na interface da equipe do Koha (`/cgi-bin/koha/tools/marc_replace.pl`). Se quiser, acrescenta também atalhos na interface da equipe: **Injeção MARC & IA** ao lado de **Novo registro** (e no menu Novo das páginas de registro), que abre a catalogação com IA descrita abaixo para rascunhar um registro novo; **Substituir via MARC / IA** ao lado de **Editar** em cada registro, que abre a página com aquele registro (arquivo ou texto MARC, ou fotos do livro), sempre passando pela prévia antes de qualquer substituição; **Substituir o registro (arquivo MARC)** no menu Editar de cada registro; e **Substituir um registro MARC** e **Catalogação com IA** nas ferramentas da página inicial da catalogação (`/cgi-bin/koha/cataloguing/cataloging-home.pl`). Ele substitui um registro, encontrado pelo biblionumber, por um arquivo `.mrc` ou `.xml` ou por texto colado (linhas da Biblioteca Nacional `245 10 |a`, do MarcEdit ou do yaz-marcdump):

- login com a permissão `edit_catalogue` e token CSRF (operações `cud-` do Koha 24.05+);
- primeiro uma prévia; depois, numa única transação, o registro atual é travado e comparado com a prévia (nada é substituído se ele mudou), guardado em MARCXML em `/var/lib/koha/library/kei-marc-replace/` (pode ser baixado pela página e reenviado para desfazer) e substituído com o `ModBiblio` do Koha;
- os campos de exemplar do arquivo são sempre deixados de fora: os exemplares nunca são tocados;
- arquivos em MARC-8 / Latin-1 são convertidos pelo `MarcToUTF8Record` do próprio Koha.

A página é verificada com os módulos Perl do Koha antes de ser instalada; removê-la mantém as versões guardadas.

#### Catalogação com IA (fotos do livro)

Mais duas abas da mesma página catalogam um livro a partir de fotos da capa, da folha de rosto e do verso da folha de rosto (com a ficha catalográfica):

- **Configuração da IA** (só para quem pode alterar as preferências do sistema): o modelo de visão, seja uma API na nuvem com token (OpenAI, Anthropic ou qualquer serviço compatível com a OpenAI), seja um modelo na própria rede da biblioteca (Ollama `http://localhost:11434` ou LM Studio `http://localhost:1234/v1` com um modelo de visão como `qwen2.5vl`, `llama3.2-vision` ou `gemma3`). A configuração fica em `kei-marc-replace/vision.conf`, legível só pelo usuário da instância do Koha; o token nunca volta a ser exibido e é recusado em `http` simples para um servidor fora da rede local. **Testar a conexão** lista os modelos do servidor. Nenhum token vem com o painel.
- **Instruções de catalogação para o modelo** (na mesma aba): as instruções enviadas com cada livro, antes do formato fixo da resposta. As instruções padrão pedem a catalogação pelo MARC 21, AACR2 e ISBD no idioma da catalogação, a partir das fontes principais e do contexto do livro, com um registro de exemplo. A biblioteca pode reescrevê-las (`{language}` vira o idioma da catalogação); elas ficam em `kei-marc-replace/vision-prompt.txt`, e **Voltar às instruções padrão** traz de volta as padrão.
- **Catalogação com IA**: as fotos vão para o modelo, com um campo opcional de **instruções só para este livro** (por exemplo, "o autor também é o ilustrador"), que têm precedência sobre as instruções gerais, vão só com aquelas fotos e nunca são guardadas: o próximo livro começa com o campo vazio. O modelo responde com os dados bibliográficos em JSON (conferidos contra um esquema fixo: nada inventado, marcadores vazios descartados). Em seguida as regras nacionais são aplicadas por `KohaEasy::Cataloguing::Rules`: pontuação AACR2 e ISBD (245 `:` `/`, 260 com `[S.l.]` / `[s.n.]`, 300), nomes invertidos como na catalogação brasileira (`Assis, Machado de`, `Andrade Filho, José de`), caracteres a desconsiderar do 245, dígito verificador do ISBN (os errados vão para o 020 `$z`), a CDD impressa na ficha catalográfica (senão a sugestão do modelo, marcada para conferência) no 082 e 090, e a **notação de autor da tabela PHA ou Cutter-Sanborn da própria biblioteca**, calculada por uma versão em Perl do algoritmo do painel, de modo que a página e o **Auxílio à catalogação** dão a mesma notação.
- O bibliotecário corrige o rascunho ao lado das fotos e segue uma **prévia obrigatória**. Só então o registro é incluído com o `AddBiblio` do Koha, numa única transação sob uma trava do banco, depois de conferir de novo o ISBN no catálogo (um registro com o mesmo ISBN exige marcar uma caixa), com uma cópia do registro e da resposta do modelo guardada em `kei-marc-replace/vision/`. Um formulário enviado duas vezes não inclui nada. Com um biblionumber, o rascunho vai para a substituição acima (com a trava e a versão guardada dela).

Os dois módulos são instalados com a página em `/usr/local/lib/site_perl/KohaEasy/Cataloguing/` e removidos com ela (a configuração fica junto das versões guardadas).

### Consulta à CDD na catalogação (interface da equipe)

**Ferramentas da biblioteca > Consulta à CDD** coloca a CDD inteira na catalogação do Koha, em `/cgi-bin/koha/cataloguing/cdd_lookup.pl`.

- **A CDD não é distribuída com o painel**: a CDD tem direitos autorais da OCLC. **Gerar o índice** pede o exemplar da própria biblioteca (o PDF, ou um `.txt` com o texto dele; o PDF é lido com o `pdftotext`) e gera um índice SQLite no servidor (`/var/lib/koha/<instância>/kei-cdd/cdd.sqlite`, legível só pelo root e pela instância). São lidas as tabelas principais, as Tabelas 1 a 6 e o índice alfabético de assuntos, com os números entre colchetes (não usados) e opcionais marcados. Um arquivo com menos de 100 entradas nas tabelas principais é recusado e o índice anterior é mantido. PDF digitalizado não tem texto: use o texto de um OCR.
- **A página** pesquisa por número (`869.3`, `869,3`, `T1—09`) ou por palavras do assunto (acentos e plurais não importam). Cada número mostra o lugar na hierarquia, as notas (com os números citados como links), as subdivisões, os assuntos do índice e, para um número que não está impresso nas tabelas, **como provavelmente foi construído** (número base mais Tabela 1, Tabela 2 via —09, Tabela 3 em 810–899, Tabela 4 em 420–499), marcado como sugestão. **Construir um número** acrescenta a notação de uma tabela ao número enquanto você digita.
- **Na sua biblioteca**: ao lado de cada resultado, quantos títulos e exemplares do catálogo usam aquela classe (com e sem as subdivisões, pelo número de chamada dos exemplares), os próprios títulos e como a biblioteca classificou títulos com as palavras pesquisadas.
- **Instalar a página** pode adicionar um botão **CDD** ao lado dos campos 082, 083, 090, 092 `$a` e do número de chamada do exemplar (952 `$o`) nos formulários de catalogação, e **Consulta à CDD** nas ferramentas da página inicial da catalogação (um bloco marcado no `IntranetUserJS`, com backup verificado `PRE-CDD` antes). O botão abre a consulta com o número que já está no campo ou com os assuntos e o título do registro como sugestões; **Usar no registro** coloca o número no campo (082 e 083 recebem o número e o `$2` com a edição quando vazio; 090, 092 e 952 mantêm a notação de autor depois dele). **Copiar** copia o número.
- **Remover a página** remove a página, os botões e o módulo `KohaEasy/CDD.pm`; o índice é mantido.

### Calculadora Cutter

**Ferramentas da biblioteca > Calculadora Cutter** monta o número de chamada de um registro: a classe e a notação de autor pela tabela Cutter-Sanborn ou PHA da própria biblioteca, no painel e na catalogação do Koha, em `/cgi-bin/koha/cataloguing/cutter_calculator.pl`.

- **As tabelas não são distribuídas com o painel**: as edições da tabela Cutter-Sanborn e a Tabela PHA (Heloísa de Almeida Prado, T. A. Queiroz) têm direitos autorais. **Carregar a tabela Cutter-Sanborn** pede o exemplar da biblioteca como arquivo de texto, um número e a entrada por linha, como a tabela de três algarismos os imprime (`848     Assis`, `  127     Abbot, J.`; os espaços no começo podem variar). **Carregar a tabela PHA** aceita um arquivo de texto ou o PDF do livro, mesmo digitalizado: o painel lê o texto com o `pdftotext` ou, quando as páginas são imagens, com o OCR Tesseract (português) no próprio servidor, página por página. As linhas do livro são postas na ordem dele e um número que o OCR leu errado é corrigido quando um algarismo parecido o devolve à ordem decimal da tabela; o relatório lista cada correção para conferir no livro. Cada tabela é conferida antes de ser guardada (entradas por letra, números fora de ordem, entradas repetidas) e salva em `/etc/koha-easy-install/tables/`, as mesmas tabelas usadas pela catalogação com IA e pelo Auxílio à catalogação.
- **A notação** segue as mesmas regras em todo lugar (`KohaEasy::Cataloguing::Rules`): a entrada imediatamente anterior ao nome em ordem alfabética, a inicial do sobrenome, o número e a inicial do título sem o artigo (`Assis, Machado de` + *Dom Casmurro* = `A848d` na Cutter-Sanborn). A entrada principal é automática: o autor, ou a primeira palavra do título (sem o artigo) quando a obra não tem autor; ela também pode ser fixada como pessoa, instituição (primeira palavra) ou título. Na página, um nome digitado na ordem direta (`Machado de Assis`) é lido como `Assis, Machado de`.
- **Opções na página**: a tabela (PHA ou Cutter-Sanborn, quando as duas estão carregadas), a classificação, **Sem a letra do título** (`A848` em vez de `A848d`), **Edição** (a partir da 2ª: `A848d 2. ed.`; lida do 250) e **Exemplar** (`ex. 2`; o número do exemplar, 952 `$t`, quando o botão é usado ali).
- **A engrenagem** (Configurações) guarda no navegador o padrão de cada bibliotecário: a tabela, a classificação, se a letra do título entra e se a edição e o número do exemplar entram quando o registro os tem. Valem sempre que a página abre; um campo mudado à mão na página prevalece.
- **A classificação** do número de chamada é CDD, CDU ou os códigos próprios da biblioteca (`LIT`, `INF J`). É a escolhida nas configurações; senão, é lida da classe já digitada, depois do registro (082 CDD, 080 CDU, 084 outra) e depois de como é a maioria dos números de chamada do catálogo. Sem classe no campo, entra a classe do registro (082, 080 ou 084, conforme a classificação).
- **Classes sugeridas**: quando o registro não tem classe, ou só tem uma classe CDD sem decimais (`869`), a página lista classes tiradas do catálogo: as classes de outros títulos do mesmo autor, de títulos com os mesmos assuntos (650) e de títulos com as mesmas palavras no título, e, para a CDD, os números que o índice da **Consulta à CDD** dá para os assuntos e o título quando esse índice foi gerado. São pistas contadas no catálogo, não uma classificação: a melhor preenche um **Número de chamada sugerido**, e **Usar esta classe** coloca qualquer uma delas no formulário. O painel não tem tabela da CDU, então para a CDU a classe vem só do 080 ou dos números de chamada CDU do próprio catálogo. A catalogação com IA (Substituir um registro MARC) é onde um modelo sugere a CDD a partir das fotos do livro; esta página não envia nada para fora.
- **A página** mostra o número enquanto o autor é digitado, a entrada da tabela usada e, com um número de classificação, o número de chamada e os números de chamada do catálogo que já usam o mesmo número nessa classe, com os números imediatamente anterior e posterior e se estão livres. **Copiar** copia o número ou o número de chamada. `?format=json` dá o mesmo resultado em JSON (`code` é o número completo com edição e exemplar, `notation` só o número).
- **Instalar a página** pode adicionar um botão **Número de chamada** ao lado do 090 e 092 `$a` e do número de chamada do exemplar (952 `$o`), e um botão **Cutter** ao lado do 090 e 092 `$b`, nos formulários de catalogação, depois do botão CDD quando ele existe, e **Calculadora Cutter** nas ferramentas da página inicial da catalogação (um bloco marcado no `IntranetUserJS`, com backup verificado `PRE-CUTTER` antes). Os botões abrem a página com o autor (100, ou 110/111), o título (245 e o indicador de caracteres a desconsiderar), a classe (do campo, ou do 090), 080 / 082 / 084, os assuntos (650) e a edição (250) do formulário; no editor de exemplares eles são lidos do registro. **Usar no registro** coloca a classe no `$a` e a notação de autor no `$b` do 090 / 092, ou o número de chamada inteiro no número de chamada do exemplar (mantendo um prefixo de localização como `R`).
- **Calcular um número Cutter** faz o mesmo no painel com a tabela escolhida, com os números usados na classe. **Remover a página** remove a página e os botões; as tabelas são mantidas.

### Plugins do Koha (ligar ou desligar)

**Ferramentas da biblioteca > Plugins do Koha** liga ou desliga o sistema de plugins do próprio Koha (**Administração > Gerenciar plugins**), que vem desligado numa instância Debian nova (`<enable_plugins>0</enable_plugins>` no `koha-conf.xml`).

- **Ligar os plugins do Koha** coloca `enable_plugins` em 1, acrescenta `<pluginsdir>` quando falta (`/var/lib/koha/<instância>/plugins`, criada para o usuário da instância), liga a preferência `UseKohaPlugins` nas versões do Koha que ainda a têm e reinicia o Plack e os processos em segundo plano.
- **Desligar os plugins do Koha** volta `enable_plugins` para 0 e não muda mais nada: os arquivos dos plugins e seus dados ficam, e ao ligar de novo eles voltam como estavam.
- **De onde os plugins podem ser instalados**: envio de `.kpz` mais os repositórios de plugins, ou somente os repositórios de plugins (`plugins_restricted`). Sem nenhum repositório configurado, o painel oferece adicionar os que o `koha-conf.xml` traz como exemplo (ByWater Solutions, Theke Solutions, PTFS Europe).
- **Registrar plugins copiados para a pasta** executa o `koha-plugins --install` do Koha (ou o `install_plugins.pl` em Koha mais antigo) depois de um backup verificado `PRE-PLUGINS`, para plugins descompactados à mão na pasta de plugins.
- Cada alteração só grava um `koha-conf.xml` novo quando ele é XML válido e é relido com os valores novos; se não, o arquivo fica como estava. O arquivo anterior fica ao lado como `koha-conf.xml.bak-<data>`.

## Tarefas automáticas

Instaladas em `/etc/cron.d/koha_tasks`:

| Quando | Tarefa |
|--------|--------|
| Diariamente 23:00 | Backup SQL compactado (verificado, envio opcional para a nuvem) |
| Domingos 03:00 | Exportação MARC21 dos registros bibliográficos e de autoridade |
| Diariamente 01:30 | Limpeza de sessões e da fila do Zebra (`cleanup_database.pl --confirm`) |
| Diariamente 05:00 | Reinício do Plack (mantém a memória baixa) |
| A cada 2 min | Vigia da indexação do Zebra: mantém o daemon indexador do Koha (`koha-indexer`) no ar e o reinicia se registros esperarem mais de 10 min |
| A cada 5 min (só Elasticsearch) | Vigia do indexador do Elasticsearch |

Os avisos por e-mail ficam com a agenda do próprio Koha (`koha-common`): avisos de atraso e de vencimento uma vez por dia e a fila de mensagens a cada 15 minutos, para a instância ativada com `koha-email-enable` (feito na instalação e em **Configurações do Koha > Configurar e-mail**). Agendamentos gravados por versões antigas do painel são atualizados sozinhos: a limpeza das 01:30 ganha o `--confirm` (sem ele, só informava o que apagaria) e as antigas tarefas de e-mail das 08:00/08:05, que duplicavam as do Koha, são removidas assim que o e-mail é ativado.

## Arquivos importantes

| Caminho | Conteúdo |
|---------|----------|
| `/root/koha_credentials.txt` | Credenciais de primeiro acesso |
| `/etc/koha/sites/library/koha-conf.xml` | Configuração da instância do Koha |
| `/var/backups/koha_sql`, `/var/backups/koha_marc` | Backups locais |
| `/etc/koha-easy-install/` | Configurações do painel (idioma, backup) |
| `/var/log/koha-easy-install/` | Logs do painel, do APT e das validações (`tools/`: ferramentas da biblioteca, só root) |
| `~/importar` (`C:\KohaEasy\Importar` no Windows) | Pasta de entrada da Ferramenta de Importação Mágica Maluca |
| `/etc/koha-easy-install/import-profiles/` | Respostas sobre colunas que a Ferramenta de Importação Mágica Maluca guarda |
| `/var/lib/koha/library/kei-xslt/` | Folhas de estilo da ficha catalográfica (só enquanto a ficha estiver ativada) |
| `/etc/koha/sites/library/kei-messaging.conf` | Configurações e tokens de WhatsApp / Telegram (só root e Koha) |
| `/usr/local/lib/site_perl/SMS/Send/KohaEasy/Gateway.pm` | O driver de mensagens do Koha (com `KohaEasy/Messaging.pm`) |
| `/etc/koha-easy-install/tables/` | Tabelas de autor e tabela da CDD carregadas pela biblioteca |
| `/var/lib/koha/library/kei-marc-replace/` | Registros como estavam antes de cada substituição |
| `/etc/koha-easy-install/windows.conf` | Só no Windows: o que as ferramentas do Windows informam ao painel (modo de rede, início automático...) |
| `C:\KohaEasy\` | Só no Windows: `bin\` (scripts, `KohaEasy.exe` e `koha.ico`), `logs\`, `Backups\`, `state.json` |

A instalação mostra sete etapas numeradas, uma linha por tarefa com uma pequena barra de progresso do Pac-Man, e uma tela final com os endereços do catálogo e da interface da equipe. A saída dos comandos nunca aparece na tela: ela fica em `/var/log/koha-easy-install/apt.log`. Se uma tarefa falhar, o painel mostra a etapa que falhou, o que verificar e as últimas linhas desse log, que é o arquivo a enviar ao suporte de TI.

As outras tarefas longas do painel têm o mesmo visual: troca do motor de busca, reparo do índice de busca, configuração do Cloudflare Tunnel, atualização do sistema, validação, reparo dos serviços, manutenção profunda e atualização de idiomas. A saída delas fica em `/var/log/koha-easy-install/` (por exemplo `search-engine.log`, `zebra-rebuild.log`, `cloudflare.log`, `restore.log` e `apt.log`). A restauração de backups e as ferramentas que o painel instala quando pedidas (Midnight Commander, links, htop e nethogs) têm o mesmo visual.

As janelas do painel são desenhadas com o `dialog`, que o painel instala, então botões, itens de menu e caixas de seleção também aceitam cliques do mouse nos terminais que informam o mouse: Windows Terminal, os terminais do desktop Linux (GNOME Terminal, Konsole, xterm), PuTTY e a maioria dos clientes SSH. O console de texto do Linux só aceita com o `gpm` instalado. `KEI_UI=whiptail` mantém o visual antigo, só com teclado.

Num PC Linux com desktop gráfico, o painel adiciona um atalho **Koha** (`koha-descomplicado.desktop`) ao menu de aplicativos do usuário que o executou com `sudo` e, na primeira vez, à área de trabalho desse usuário. Ele abre o painel num terminal e pede a senha do `sudo`. Em português, o painel se chama **Koha descomplicado : instalação e gestão**.

## Desinstalação

O `uninstall.sh` **apaga definitivamente** o Koha, seus bancos de dados, os backups locais e as configurações, e pede confirmação antes:

```bash
sudo bash uninstall.sh          # pede para digitar APAGAR
sudo bash uninstall.sh --yes    # sem perguntas (automação)
```

Copie seus backups para outro lugar antes de executá-lo.

## Testes

A pasta `tests/` tem uma bateria [bats-core](https://github.com/bats-core/bats-core) que executa o painel contra um MariaDB real: backups corrompidos, truncados e vazios, MariaDB parado ou recusando o login, disco cheio ou sem permissão de escrita, CTRL+C / queda do SSH no meio da restauração, travas compartilhadas com os backups noturnos, indexação depois de trocar o motor de busca e de restaurar, versões do Debian/Ubuntu em amd64/arm64, as ferramentas da biblioteca (simulação antes de qualquer alteração, trava, backup verificado, aspas do `koha-shell`), as ferramentas do Brasil (migração MARC em Latin-1 para o 952, dígitos verificadores do CPF, feriados móveis, modelos de etiquetas, ficha catalográfica, planilhas do acervo, relatórios dos censos, referências ABNT), o driver de mensagens (contra um dublê de WhatsApp / Telegram), a notação de autor, a Calculadora Cutter e a consulta à CDD, o interruptor dos plugins do Koha no `koha-conf.xml`, o `marc_replace.pl` (executado como CGI), a atualização dos agendamentos, o modo WSL, a autorização por QR code / navegador / link e as ferramentas do Windows (os testes em PowerShell rodam com o [Pester 5](https://pester.dev) quando o `pwsh` está instalado).

```bash
sudo apt-get install bats mariadb-server memcached whiptail yaz xsltproc python3 \
     libmarc-record-perl libmarc-xml-perl libsms-send-perl libcgi-pm-perl libmodern-perl-perl
sudo KEI_TEST_SANDBOX=1 tests/run.sh
```

**Somente em um contêiner ou VM descartável:** os testes substituem o banco `koha_library` e instalam dublês de teste para as ferramentas `koha-*` e o `systemctl`. O `tests/run.sh` se recusa a rodar ao lado de um Koha real.

## Traduções

Os textos do painel ficam em inglês dentro do `installer`; cada idioma tem um dicionário em `lang/<código>.cache` (`base64(inglês)|base64(tradução)`). O painel em si é Bash puro; os scripts Python abaixo são ferramentas opcionais para quem contribui.

- Envolva todo texto visível em `$(t "...")`. As variáveis devem ser escapadas para que o texto em inglês chegue intacto ao `t()`: `$(t "Backup saved in \${file}")`.
- Verificar a cobertura e reparar os dicionários: `python3 i18n_common.py` / `python3 i18n_common.py --fix`
- Traduzir só o que falta: `python3 gen_all_langs.py` (offline, Argos Translate) ou `python3 gen_lang.py` (online).
- Traduções que perdem uma variável ou `%s` são rejeitadas automaticamente e o texto em inglês é exibido.

Depois de mudar o `PANEL_VERSION`, rode `python3 i18n_common.py --fix` (cada dicionário leva a versão do painel, e dicionários desatualizados só são usados em último caso).

Depois de alterar o `installer`, gere de novo o checksum usado pela autoatualização:

```bash
sha256sum installer > installer.sha256
```

## Licença

O Koha Easy Installer & Manager é software livre sob a [Licença Pública Geral GNU v3.0 ou posterior](LICENSE) (GPL-3.0-or-later), a mesma licença do Koha. Você pode usar, estudar, compartilhar e modificar; se distribuir versões modificadas, elas devem continuar sob a GPL e com o código-fonte disponível. É fornecido **sem garantia**.

## Apoie o projeto

- Pix: `076.650.449.21`
- Bitcoin (BTC): `bc1qw0kvacdkzul0panuppxcv90y08ah443m2z89tx`
- ⭐ Dê uma estrela ao repositório e compartilhe com outras bibliotecas.

---

Criado com dedicação por **Paulo F. Baldi FH** — Auxiliar de Biblioteca, Biblioteca Pública Castro Alves, Palotina, Paraná, Brasil.

<sub>O nome e o logotipo do Koha pertencem à comunidade Koha (koha-community.org); este instalador é um projeto independente.</sub>
