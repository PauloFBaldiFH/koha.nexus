# Nexus Eventos para Tainacan

Plugin WordPress gratuito para agenda, vínculo com coleções do Tainacan, presença e comprovantes de participação. O Events Manager gratuito cuida de eventos e reservas; a extensão Nexus adiciona a integração e seus recursos próprios.

## Instalação a partir deste repositório

Copie esta pasta `nexus-events-plugin/` para o diretório de plugins do seu WordPress e ative **Nexus Eventos para Tainacan**. Se a base estiver ausente, o aviso administrativo permite preparar o Events Manager incluído, com confirmação. Uma instalação existente não é sobrescrita.

Todos os arquivos estão descompactados. `bundled/events-manager/` contém a base original, sem alterações; `bundled/events-manager.sha256.json` registra os hashes por arquivo. A preparação copia essa base para um plugin independente, preservando seu caminho de atualização.

Esta pasta não é instalada automaticamente pelo instalador Koha.Nexus. Use primeiro em um site de teste.

- [Manual e limitações](LEIA-ME.md)
- [Validação executada](VALIDACAO.md)
- [Escolha das bases](ANALISE-DAS-BASES.md)
- [Licenças e atribuições](THIRD-PARTY-NOTICES.md)
- [Testes de desenvolvimento](development/tests/README.md)

Versão 0.1.0 para piloto. O servidor de produção, SMTP real e os temas específicos do Tainacan ainda precisam de homologação.
