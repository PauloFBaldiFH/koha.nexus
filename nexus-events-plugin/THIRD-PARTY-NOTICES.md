# Código e materiais de terceiros

## Events Manager 7.4.13

Autor identificado no código: Marcus Sykes / Pixelite.
Projeto: https://wp-events-plugin.com/
Código original: https://wordpress.org/plugins/events-manager/
Licença declarada: GPLv2; o cabeçalho permite versão 2 ou posterior.

O pacote de produção (tools/nexus-eventos-package.py) não contém o Events Manager. Ele é um plugin independente, instalado a partir do diretório oficial do WordPress; no Koha.Nexus, cada arquivo do pacote baixado é conferido contra as somas publicadas pelo wordpress.org antes de instalar. Não é apresentado como código desenvolvido pelo Koha.Nexus.

No repositório, o diretório bundled/events-manager guarda os arquivos extraídos do ZIP fornecido para análise, sem alterações de conteúdo, com o manifesto bundled/events-manager.sha256.json e o texto GPLv2 em bundled/LICENSE.events-manager. Ele serve só ao desenvolvimento e não vai para produção.

SHA-256 do ZIP original analisado (não incluído no repositório): 1e55d8f8492b6439b1e956850faab2d975ab444d8b218802db4037dc1c21c6d1

## Biblioteca de QR

qrcode-generator 1.4.4, Kazuhiko Arase.
Origem: https://www.npmjs.com/package/qrcode-generator/v/1.4.4
Licença MIT, reproduzida em assets/vendor/LICENSE.qrcode. O cabeçalho original permanece em qrcode.js.
O uso desta biblioteca não envia códigos a um serviço remoto.

## Referências analisadas, não incorporadas

The Events Calendar 6.18.3 e Event Tickets 5.31.0 foram fornecidos para análise de recursos, organização e pontos de integração. Não copiamos seu código, suas imagens ou seus templates para esta extensão. Não são dependências.

Hashes dos arquivos analisados:
- The Events Calendar 6.18.3: a7a2b1b688fc1e5c975b26b6b924c7d8db2f0005f585c1ed965eeb3ee7b37101
- Event Tickets 5.31.0: 22450af21881acc4a44502ad0e83b553d64a497075ecf259c5aa4d5b2eaebe59

Tainacan não é redistribuído neste pacote. Sua API de dados e seus tipos de conteúdo são usados no site em que estiver instalado. Não há afiliação ou endosso declarado por esses projetos.
