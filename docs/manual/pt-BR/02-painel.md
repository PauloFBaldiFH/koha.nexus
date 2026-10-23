# 2. Primeiros passos e painel

[Índice do manual](README.md) · [Instalação](01-instalacao.md) · [Backup e restauração](03-backup-restauracao.md)

## 2.1 Abrir o painel

No Debian ou Ubuntu já preparado pelo instalador, execute:

```bash
sudo config.sh
```

No Windows, use o ícone **Koha** criado pelo instalador ou abra o Koha.Nexus instalado pelo MSIX. Para o procedimento do pacote MSIX, consulte a seção 1.3.

Na primeira abertura, o painel pode pedir a escolha do idioma antes de mostrar a tela principal. Quando a preparação da interface Textual falha, o instalador pode oferecer o painel clássico. A organização e as telas deste manual descrevem principalmente o painel Textual; não espere que a numeração de um menu clássico seja reproduzida nele.

Fonte: `install_panel_copy` e inicialização da interface no [instalador](../../../installer), `on_mount` em [app.py](../../../panel/kei_panel/app.py), e [fluxo de abertura Windows](../../../windows/KohaEasy.Install.psm1).

## 2.2 Encontrar uma ação

A barra lateral lista as seções. Use as setas para destacar uma seção e **Enter** para abri-la, ou clique. Mover o destaque sozinho não executa a ação. Na área de conteúdo, abra o cartão correspondente à tarefa e leia as perguntas antes de confirmar.

**Tab** permite mover o foco entre os controles. Os atalhos abaixo pertencem à tela principal; ao preencher uma caixa de texto, termine ou saia dela antes de tentar navegar por letras.

| Tecla | Ação conferida |
| --- | --- |
| `d` | Abrir o Painel de Controle |
| `b` | Abrir a Central de backups e restauração |
| `c` | Abrir o terminal do Debian |
| `Ctrl+B` | Mostrar ou ocultar a barra lateral |
| `q` | Sair do painel |

Sair do painel em repouso não é o procedimento de desligamento do servidor. Para uma operação em andamento, respeite a indicação de cancelamento da própria tela. A instalação e a restauração têm etapas explicitamente não canceláveis; fechar a janela à força não é um modo seguro de interrompê-las.

Fontes: `MainScreen.BINDINGS`, `on_option_list_option_selected` e `action_show` em [screens/main.py](../../../panel/kei_panel/screens/main.py); `BINDINGS` em [app.py](../../../panel/kei_panel/app.py); chamadas com `cancellable=False` nas rotinas de [instalação](../../../panel/kei_panel/routines/install.py) e [restauração](../../../panel/kei_panel/routines/backup.py).

## 2.3 Ler o Painel de Controle

A tela inicial mostra:

- **Koha:** estado geral e memória disponível.
- **Último backup:** data, idade e arquivo mais recente encontrado.
- **Disco livre:** espaço disponível em relação ao total.
- **Endereços:** acesso ao catálogo e à interface da equipe neste computador, na rede local e, quando houver, na internet.
- **Componentes:** MariaDB, Apache, RabbitMQ, Memcached e Koha, além da resposta HTTP.

O indicador do backup considera a idade do arquivo e o resultado informado da última execução noturna. Um cartão favorável não substitui o teste de restauração descrito na seção 3. Um arquivo recente e uma execução noturna com falha podem aparecer juntos: leia ambos os indicadores.

A resposta HTTP informa se houve resposta segundo a verificação do painel. Ela não prova, isoladamente, que o assistente web do Koha foi concluído ou que todas as funções bibliotecárias foram verificadas.

Use **Atualizar** para consultar novamente. **Reiniciar Koha** solicita a rotina de reparo/reinício de serviços; planeje essa ação considerando quem está usando o catálogo. **Exportar diagnóstico** prepara as informações de diagnóstico pelo fluxo oferecido. Esses botões podem ficar indisponíveis se o instalador instalado não tiver a tarefa correspondente.

Fonte: `DashboardView`, `backup_card`, `OVERALL`, `COMPONENTS` e `access_links` em [views/dashboard.py](../../../panel/kei_panel/views/dashboard.py).

## 2.4 Abrir o catálogo e a interface da equipe

Use os cartões de endereço da própria instalação. Cada um permite abrir ou copiar a URL. Quando o ambiente não consegue abrir um navegador, o painel pode copiar o endereço para você colar no navegador do seu computador.

Por padrão, o catálogo usa a porta 80 e a interface da equipe usa a 8080. No próprio computador, os endereços locais são:

- Catálogo público: `http://localhost/`.
- Interface da equipe: `http://localhost:8080/`.

Esses endereços são locais: em outro computador, use o endereço de rede indicado pelo painel. Se ele informar que a rede local não está acessível por causa do WSL em NAT, não suponha que o endereço local funcionará em todos os computadores. Confira o resultado da preparação de rede Windows e procure o responsável pelo ambiente.

Se a interface da equipe apresentar o instalador web do Koha, conclua esse assistente antes de começar a operar o acervo. Este manual não presume que todas as etapas do instalador web sejam iguais em qualquer versão do Koha.

Fonte: `access_links` e `http_url` em [views/dashboard.py](../../../panel/kei_panel/views/dashboard.py), `open_url` em [app.py](../../../panel/kei_panel/app.py), configurações padrão em [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1), e orientação de próximo passo emitida pelo [instalador](../../../installer).

## 2.5 Preparar a operação da biblioteca

Depois de concluir o assistente web, a ação **Criar superbibliotecário** fica em **Configurações e parâmetros do Koha**. Ela abre um fluxo próprio de cadastro; preencha os dados somente na tela da instalação. Este manual não reproduz valores de acesso.

Antes de iniciar o trabalho com o acervo:

1. Atualize o Painel de Controle e confira os componentes e endereços.
2. Abra a interface da equipe e o catálogo pelo endereço apropriado ao computador usado.
3. Gere e teste um backup conforme a seção 3.
4. Confirme onde a cópia fora do servidor foi guardada e quem consegue recuperá-la.

A etapa 4 é uma recomendação operacional: o painel consegue criar e copiar arquivos, mas a existência de uma cópia utilizável fora do computador depende de concluir essa cópia e conferir seu resultado.

Fontes: seção `settings` de [menus.py](../../../panel/kei_panel/menus.py), rotina `superlibrarian` em [routines/settings.py](../../../panel/kei_panel/routines/settings.py), e rotinas de [backup e transferência](../../../panel/kei_panel/routines/backup.py).
