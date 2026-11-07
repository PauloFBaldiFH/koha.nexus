# OPAC como aplicativo (PWA) e carteirinha digital

Módulo autocontido do Koha.Nexus. Não altera o núcleo do Koha: só copia arquivos para a pasta pública do OPAC e cola dois blocos nas preferências `OpacUserCSS` e `OpacUserJS`.

O que ele entrega:

- **Instalar no celular**: `manifest.json` (nome, ícones, `display: standalone`, `orientation: portrait`) e `service-worker.js`.
- **Cache offline leve**: o service worker guarda só arquivos estáticos (CSS, JS, imagens, fontes), a página `offline.html` e a biblioteca JsBarcode. Páginas do Koha (`/cgi-bin/...`), HTML e dados de leitor nunca vão para o cache.
- **Carteirinha digital**: botão "Carteirinha digital" para leitores logados. Abre um cartão com o número da carteirinha como código de barras Code 128 (JsBarcode, em SVG), legível por leitores óticos comuns.

## Arquivos

| Arquivo | Função | Vai para |
|---|---|---|
| `manifest.json` | identidade do app | raiz do OPAC |
| `service-worker.js` | cache offline dos estáticos | raiz do OPAC |
| `carteirinha.js` | bloco de **OpacUserJS** | colar na preferência (não é copiado) |
| `carteirinha.css` | bloco de **OpacUserCSS** | colar na preferência (não é copiado) |
| `offline.html` | página sem conexão | `koha-nexus-pwa/` |
| `icons/*.png` | ícones 192, 512 e maskable 512 | `koha-nexus-pwa/icons/` |
| `instalar-opac-pwa.sh` | copia os arquivos, com permissões | executar com sudo |
| `check.sh` | verificação estática (JSON, sintaxe, ícones) | não instalar |

## Pré-requisitos

- Koha com OPAC servido por **HTTPS**. O service worker e a instalação do app só funcionam em HTTPS (ou em `localhost`). Em HTTP na rede local, a carteirinha funciona, mas o app não instala e o cache offline fica desligado.
- Leitores com login no OPAC (a carteirinha é mostrada só para quem está logado).
- Acesso à internet no celular para carregar a biblioteca JsBarcode (vinda do cdnjs.cloudflare.com, versão fixada 3.11.6).

## Instalação passo a passo (Linux, Debian/Ubuntu com pacote Koha)

### 1. Confirmar a pasta pública do OPAC

Caminho padrão do pacote Koha:

```
/usr/share/koha/opac/htdocs
```

Confira no Apache, pelo DocumentRoot do site do OPAC:

```bash
grep -R "DocumentRoot" /etc/apache2/sites-enabled/
```

Se for outro caminho, use `KOHA_OPAC_HTDOCS` no passo 2.

### 2. Copiar os arquivos

Na raiz do repositório, dentro da pasta `opac-pwa/`:

```bash
cd /caminho/do/koha.nexus/opac-pwa
sudo ./instalar-opac-pwa.sh
```

Para outro DocumentRoot:

```bash
sudo KOHA_OPAC_HTDOCS=/caminho/htdocs ./instalar-opac-pwa.sh
```

O script usa `install -m 0644 -o root -g root` para arquivos e `install -d -m 0755 -o root -g root` para pastas. Assim o Apache (usuário `www-data`) consegue ler, e ninguém de fora altera os arquivos. Se já existir um `manifest.json` ou `service-worker.js` diferente na raiz, o script para e pede para renomear o arquivo antigo.

Os caminhos finais ficam:

```
/usr/share/koha/opac/htdocs/manifest.json
/usr/share/koha/opac/htdocs/service-worker.js
/usr/share/koha/opac/htdocs/koha-nexus-pwa/carteirinha.js
/usr/share/koha/opac/htdocs/koha-nexus-pwa/carteirinha.css
/usr/share/koha/opac/htdocs/koha-nexus-pwa/offline.html
/usr/share/koha/opac/htdocs/koha-nexus-pwa/icons/icon-192.png
/usr/share/koha/opac/htdocs/koha-nexus-pwa/icons/icon-512.png
/usr/share/koha/opac/htdocs/koha-nexus-pwa/icons/icon-maskable-512.png
```

Se copiar à mão, ajuste as permissões:

```bash
sudo install -d -m 0755 -o root -g root /usr/share/koha/opac/htdocs/koha-nexus-pwa/icons
sudo chown root:root /usr/share/koha/opac/htdocs/manifest.json /usr/share/koha/opac/htdocs/service-worker.js
sudo chmod 0644 /usr/share/koha/opac/htdocs/manifest.json /usr/share/koha/opac/htdocs/service-worker.js
sudo find /usr/share/koha/opac/htdocs/koha-nexus-pwa -type d -exec chmod 0755 {} +
sudo find /usr/share/koha/opac/htdocs/koha-nexus-pwa -type f -exec chmod 0644 {} +
sudo chown -R root:root /usr/share/koha/opac/htdocs/koha-nexus-pwa
```

Confira que o Apache lê os arquivos:

```bash
sudo -u www-data test -r /usr/share/koha/opac/htdocs/service-worker.js && echo "legível"
curl -sI https://SEU-OPAC/service-worker.js | head -1      # HTTP/2 200 ou HTTP/1.1 200
curl -s https://SEU-OPAC/manifest.json | python3 -m json.tool >/dev/null && echo "manifest ok"
```

Se o Apache tiver um cabeçalho de cache agressivo para `.js`, desative-o só para `/service-worker.js`. Por padrão, o Koha não define isso.

### 3. Colar o CSS e o JS nas preferências do Koha

No Koha, como bibliotecário com permissão de preferências:

1. Administração > Preferências do sistema > **OpacUserCSS**: cole o conteúdo completo de `carteirinha.css` e salve.
2. Administração > Preferências do sistema > **OpacUserJS**: cole o conteúdo completo de `carteirinha.js` (sem a tag `<script>`) e salve.

Ajuste, dentro de `carteirinha.js`, o bloco `CONFIG` se quiser:

- `libraryName`: nome da biblioteca no cartão (vazio = "Biblioteca").
- `accountUrl`: página da conta do leitor. Padrão `/cgi-bin/koha/opac-user.pl`.

Se o OPAC usar outro prefixo de URL, altere também `manifestUrl`, `serviceWorkerUrl` e o nome em `manifest.json` (`start_url`).

### 4. Limpar o cache do navegador

Depois de instalar ou atualizar, o celular pode guardar a versão antiga. Feche o app instalado, ou limpe os dados do site, e abra o OPAC de novo.

## Como o leitor usa

1. Abrir o OPAC pelo celular, entrar na conta.
2. Tocar em **Carteirinha digital** (botão no canto inferior direito).
3. Apresentar a tela no balcão. Se o leitor não reconhecer, aumentar o brilho do celular.

Instalar o app: no Android (Chrome), menu > "Instalar app" ou "Adicionar à tela inicial". No iPhone (Safari), Compartilhar > "Adicionar à Tela de Início".

## Privacidade e segurança

- O número da carteirinha é lido da página "Minha conta" do próprio leitor, com a mesma sessão do navegador. Nada é enviado a terceiros, e nada é gravado no navegador (sem `localStorage`), para não sobrar dado de leitor em celular compartilhado.
- O service worker não guarda páginas nem respostas com dados do leitor. Só guarda CSS, JS, imagens e fontes.
- A biblioteca JsBarcode vem do cdnjs na versão fixada `3.11.6`. Se a biblioteca precisar ser hospedada no próprio servidor, baixe `JsBarcode.all.min.js` e troque `jsBarcodeUrl` por um caminho local (`/koha-nexus-pwa/jsbarcode.js`), e inclua o arquivo em `instalar-opac-pwa.sh`.
- O código não usa `eval`, não monta HTML a partir de dados externos (usa `textContent`), e só aceita números de carteirinha com caracteres comuns (letras, dígitos, ponto, barra, hífen e espaço).
- O número da carteirinha só aparece para o próprio leitor logado, porque vem da página "Minha conta" dele. A biblioteca deve avaliar a política de dados pessoais (LGPD) dela; este módulo não cria nenhuma cópia nova dos dados.

## Verificado e o que precisa de OPAC real

Verificado neste repositório (sem Koha):

- `manifest.json` é JSON válido, com `display: standalone`, `orientation: portrait`, `scope: "/"`, ícones 192, 512 e maskable 512 (`check.sh`).
- `service-worker.js` e `carteirinha.js` passam em `node --check`.
- Teste em Chromium (Playwright) com um OPAC simulado: o botão aparece para leitor logado, abre o diálogo, lê o número `0045821` e o nome da página da conta, desenha o Code 128 com JsBarcode 3.11.6, fecha com Esc e devolve o foco ao botão. Sem erros de console.
- Service worker registrado; o cache guardou só os arquivos estáticos e nenhum caminho `/cgi-bin/`.

Precisa ser testado num OPAC real Koha antes de liberar:

1. **Leitura do número da carteirinha.** O script procura um rótulo como "Card number", "Número do cartão" ou "Cartão" na página "Minha conta" e pega o valor ao lado. O texto exato depende da versão do Koha e do tema. Abra a conta do leitor, confirme o rótulo na tela e, se não aparecer, mande a captura de tela para ajustar `CARD_LABEL` (ou troque por uma leitura direta de um elemento com `id` fixo).
2. **Leitura por scanner.** O código de barras foi gerado, mas não foi lido por um leitor ótico de verdade. Testar com um leitor USB e com o celular no balcão, em brilho alto e em brilho médio.
3. **Instalação do app** em Android (Chrome) e iPhone (Safari), com HTTPS. Confirmar que o manifest é lido quando o link é inserido pelo OpacUserJS. Se o navegador não reconhecer, colar a tag `<link rel="manifest" href="/manifest.json">` no `OpacHeader` (preferência do Koha).
4. **Tema do OPAC.** O botão e o diálogo foram testados com o layout simulado. Com o tema Koha Bootstrap ou com um tema da biblioteca, conferir sobreposição com o rodapé e o menu.
5. **Atualização.** Ao mudar a versão de `service-worker.js` (campo `VERSION`), conferir que o celular passa a usar a nova versão e apaga o cache antigo.

## Desinstalar

```bash
sudo rm -f /usr/share/koha/opac/htdocs/manifest.json /usr/share/koha/opac/htdocs/service-worker.js
sudo rm -rf /usr/share/koha/opac/htdocs/koha-nexus-pwa
```

Depois, apague o conteúdo de OpacUserCSS e OpacUserJS (ou só os blocos deste módulo).
