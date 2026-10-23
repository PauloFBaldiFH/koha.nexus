# 1. Instalação

[Índice do manual](README.md) · [Próximos passos: painel](02-painel.md)

## 1.1 Escolha o ambiente

No Windows, o Koha funciona dentro do Debian no WSL 2. As ferramentas Windows preparam esse ambiente, abrem o painel e integram o aplicativo ao computador. No Debian ou Ubuntu, o painel e os serviços são instalados diretamente no servidor.

Não use a instalação como forma de abrir um catálogo já existente: quando o painel detecta uma instância instalada, a reinstalação tem uma confirmação destrutiva própria. Para usar uma instalação pronta, abra o painel conforme a seção 2.

### Requisitos conferidos

| Ambiente | Sistema e arquitetura | Memória | Espaço livre |
| --- | --- | --- | --- |
| Windows | Windows 10 versão 2004, compilação 19041 ou posterior, ou Windows 11; sistema de 64 bits; virtualização habilitada | 8 GB; 12 GB recomendados | 10 GB na unidade de instalação; 20 GB recomendados |
| Debian/Ubuntu | Debian 11, 12 ou 13; Ubuntu 22.04 ou 24.04; arquiteturas testadas amd64 e arm64 | Consulte a ressalva abaixo | Menos de 5 GB impede a instalação; de 5 GB até menos de 10 GB gera aviso; a partir de 10 GB a verificação passa |

Esses valores são verificações de entrada. O acervo, os anexos, os índices e as cópias de segurança também precisam de espaço durante o uso.

**RAM no Linux, a confirmar:** o guia de instalação existente recomenda 4 GB para servidor dedicado, com 8 GB recomendados, e 8 GB para desktop ou ambiente virtualizado, com 12 GB recomendados. Entretanto, a pré-validação Linux consultada não aplica um mínimo numérico de RAM. Não interprete a ausência de erro nessa etapa como garantia de capacidade. O dimensionamento precisa considerar o computador e o uso da biblioteca.

No Windows, a checagem admite uma pequena parcela de memória reservada pelo hardware: os cortes internos são 7,5 GB e 11,5 GB de memória detectada. Isso explica por que um computador vendido com 8 GB pode mostrar um valor um pouco menor sem ser recusado.

No Linux, o instalador exige privilégios administrativos e verifica o acesso ao repositório do Koha. As portas TCP 80 e 8080 são usadas pelo catálogo público e pela interface da equipe. Se já estiverem ocupadas, o painel oferece parar os serviços que as utilizam. **Só aceite se souber que esses serviços podem ser interrompidos.**

Fontes: [`Get-KohaPreflight`](../../../windows/KohaEasy.Install.psm1); `install_precheck`, `platform_check`, `validate_network_and_system` e `install_free_ports` no [instalador](../../../installer); quadro de requisitos do [guia de instalação](../../../README.pt-BR.md).

## 1.2 Windows: instalação por PowerShell

1. Entre na conta do Windows que vai usar o Koha e que tenha permissão de administrador.
2. Abra o PowerShell como administrador nessa mesma conta.
3. Execute:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Se a elevação pedir os dados de outra pessoa, cancele e abra a sessão com uma conta administradora apropriada. Os componentes do WSL são vinculados à conta usada na instalação.

4. Leia as verificações do computador. Se a virtualização estiver desativada, siga a orientação apresentada para o equipamento e só retome depois de resolver o impedimento.
5. Preencha as perguntas para criação da conta do Debian diretamente na janela do instalador. Essa conta é distinta da conta bibliotecária do Koha.
6. Aguarde a preparação do WSL 2 e do Debian. Se houver solicitação de reinício, o instalador registra a retomada para a próxima entrada no Windows.
7. Quando o painel abrir, escolha o idioma e a ação **Instalar servidor Koha**. Siga o procedimento da seção 1.5.
8. Ao terminar a instalação no painel, saia normalmente dele para que o fluxo Windows continue. Aguarde a conclusão da integração e leia o resultado final.

A pasta padrão das ferramentas é `C:\Koha`. Uma instalação antiga em `C:\KohaEasy` pode ser mantida nesse local pelo instalador. Não mova a pasta manualmente para tentar corrigir uma instalação interrompida.

Se a preparação parar, registre a mensagem exibida. O fluxo registra as etapas concluídas e pode retomar ao executar novamente o instalador. Se ele detectar que o Koha não foi instalado por completo, pode reabrir o painel para concluir. Isso não torna a opção destrutiva de reinstalação um procedimento seguro para repetir sem ler as confirmações.

Fontes: [bootstrap Windows](../../../windows/install.ps1), funções `Install-Koha` e `Register-KohaResume` em [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1), e configuração de caminhos em [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).

## 1.3 Windows: pacote MSIX

O MSIX é uma alternativa de entrada para a preparação do mesmo ambiente com WSL. Instalar o pacote não significa que o servidor Koha e o banco já estejam configurados.

Para instalar o pacote disponibilizado pelo projeto usando o auxiliar existente, abra uma janela **normal**, sem elevar previamente o PowerShell, e execute:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Esse auxiliar busca o pacote configurado no próprio script, verifica sua origem, solicita a autorização administrativa necessária e o instala para o usuário atual. Não ignore mensagens de rejeição. Ao final, ele abre o Koha.Nexus para continuar a preparação.

Na primeira abertura, aguarde a preparação e siga a instalação guiada dentro do painel. Depois de concluir essa instalação, feche o painel pela ação de saída e aguarde a finalização dos atalhos, tarefas de segundo plano e rede no Windows. Se fechar o painel antes de concluir o servidor Koha, abra novamente o aplicativo para continuar; o fluxo não deve considerar essa instalação concluída apenas porque a janela fechou.

**Microsoft Store, a confirmar:** existe um modo de geração de pacote para a Store no repositório. A disponibilidade e o endereço público de uma listagem precisam de confirmação. Este manual não fornece um link de Store presumido.

**ARM64, a confirmar:** o manifesto gerado do MSIX é x64. Não se deve deduzir a compatibilidade desse pacote em ARM64 a partir do suporte arm64 do instalador Linux.

O manifesto do pacote permite uma versão de Windows anterior à exigida pela verificação do fluxo completo com WSL. Para planejar uma instalação do Koha, use o requisito completo da seção 1.1, não apenas o mínimo do manifesto.

Fontes: [auxiliar de instalação MSIX](../../../windows/msix/instalar_msix.ps1), `NeedsVisibleSetup` no [inicializador MSIX](../../../windows/msix/KohaMsixEntry.cs), [continuação após o painel](../../../windows/KohaMsixPanel.ps1) e manifesto produzido pelo [compilador MSIX](../../../windows/msix/compilar_msix.ps1). Estes arquivos foram lidos, não executados nesta revisão.

## 1.4 Debian ou Ubuntu

Em um terminal do servidor, baixe e abra o instalador conforme o guia existente:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Para manter uma cópia do repositório e das traduções junto do instalador, a alternativa documentada é:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Selecione o idioma e abra **Instalar servidor Koha**. A instalação verifica o sistema, os programas necessários, o acesso de rede, o espaço e as portas. Um erro crítico exige corrigir o impedimento antes de prosseguir; um aviso deve ser lido, não tratado como aprovação de capacidade para qualquer carga de trabalho.

Se estiver usando uma distribuição no WSL, ela precisa ser WSL 2 e executar systemd. O código recusa WSL 1 nesse fluxo. O caminho recomendado para um usuário de Windows é a preparação guiada das seções 1.2 ou 1.3.

Fontes: [comandos do guia existente](../../../README.pt-BR.md); `install_precheck`, `platform_check` e `require_systemd` no [instalador](../../../installer).

## 1.5 Instalar o servidor dentro do painel

1. Abra **Instalar servidor Koha** e aguarde a verificação inicial.
2. Leia o relatório. Se houver erro crítico, a instalação não avança. Se as portas estiverem ocupadas, avalie o impacto antes de autorizar a liberação.
3. Confirme o início somente depois de conferir o computador de destino.
4. Confirme o fuso horário detectado ou escolha região e cidade na seleção apresentada.
5. **Se aparecer uma instância existente, pare para conferir:** a reinstalação apaga o banco e a configuração. Ela exige uma confirmação adicional e a palavra exata `REINSTALL`. Não a use para simplesmente abrir ou atualizar o painel.
6. Aguarde as etapas. A tela estima de 10 a 30 minutos, mas o tempo real depende do computador e da rede. A execução da instalação é marcada como não cancelável no painel; não feche a janela durante o trabalho.
7. Leia o resultado final. Uma mensagem de instalação concluída com problemas não equivale a todos os serviços saudáveis. Abra o relatório oferecido e anote os itens que falharam.
8. Avalie a opção de reiniciar quando ela for oferecida. No fluxo MSIX, depois de sair do painel, espere também a continuação Windows descrita anteriormente.

Não transcreva dados privados da tela de resultado para documentos públicos ou chamados de suporte. A seção seguinte explica os endereços e as primeiras verificações sem reproduzir esses dados.

Fonte: `install_koha` e `_choose_timezone` em [routines/install.py](../../../panel/kei_panel/routines/install.py).
