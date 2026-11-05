# Nexus Eventos para Tainacan

Plugin WordPress gratuito para agenda, vínculo com coleções do Tainacan, presença e comprovantes de participação. O Events Manager gratuito cuida de eventos e reservas; a extensão Nexus adiciona a integração e seus recursos próprios.

## Instalação a partir deste repositório

Não copie esta pasta inteira para um servidor. Ela guarda material de desenvolvimento (`development/`) e a cópia do Events Manager usada na análise (`bundled/`), que não devem ir para produção.

O pacote de produção sai de `tools/nexus-eventos-package.py` (na raiz do repositório): uma pasta `nexus-eventos/` só com o plugin, sem `bundled/` e `development/`. A lista dos arquivos e seus sha256 fica no instalador do Koha.Nexus, que confere cada arquivo antes de instalar.

No Koha.Nexus com Tainacan, os eventos são opcionais e ficam desligados até alguém pedir:

    sudo config.sh --task tainacan-events plan
    sudo config.sh --task tainacan-events enable confirm

A ativação baixa o Events Manager do wordpress.org na versão fixada, confere cada arquivo contra as somas publicadas e só então instala. Um Events Manager que já estava no site é preservado (não é substituído nem rebaixado) e nunca é desativado sem pedido explícito (`disable dependency`). Fora do Koha.Nexus, instale o Events Manager em Plugins, Adicionar novo, e depois o pacote de produção.

- [Manual e limitações](LEIA-ME.md)
- [Validação executada](VALIDACAO.md)
- [Escolha das bases](ANALISE-DAS-BASES.md)
- [Licenças e atribuições](THIRD-PARTY-NOTICES.md)
- [Testes de desenvolvimento](development/tests/README.md)

Versão 0.1.1 para piloto. O servidor de produção, SMTP real e os temas específicos do Tainacan ainda precisam de homologação.
