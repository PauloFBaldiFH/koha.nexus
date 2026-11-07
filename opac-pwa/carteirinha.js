/*
 * Koha.Nexus - Carteirinha digital e instalação (PWA) para o OPAC.
 *
 * COLAR em: Administração > Preferências do sistema > OpacUserJS
 * (cole só o conteúdo abaixo, sem a tag <script>).
 *
 * O que faz:
 *  - Registra o service worker e aponta o manifest (instalar no celular).
 *  - Para leitores logados, mostra o botão "Carteirinha digital".
 *  - A carteirinha lê o número do cartão da página "Minha conta" do próprio leitor
 *    (mesma sessão, nenhum dado sai do servidor da biblioteca) e desenha um
 *    código de barras Code 128 com JsBarcode.
 *
 * Não altera arquivos do núcleo do Koha. Só usa o DOM das páginas do OPAC.
 */
(function () {
  'use strict';

  if (window.KohaNexusCarteirinha) return;
  window.KohaNexusCarteirinha = true;

  var CONFIG = {
    libraryName: '',                       // nome exibido no cartão; vazio = "Biblioteca"
    jsBarcodeUrl: 'https://cdnjs.cloudflare.com/ajax/libs/jsbarcode/3.11.6/JsBarcode.all.min.js',
    manifestUrl: '/manifest.json',
    serviceWorkerUrl: '/service-worker.js',
    accountUrl: '/cgi-bin/koha/opac-user.pl',
    themeColor: '#1f4e79'
  };

  // Rótulos aceitos para o número do cartão (já sem acento e em minúsculas).
  var CARD_LABEL = /^(numero do cartao|n\.? ?do cartao|cartao|carteirinha|card number|cardnumber)\s*:?\s*$/;

  function norm(s) {
    return (s || '')
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  function isLoggedIn() {
    return !!document.querySelector('#logout, a[href*="logout.pl"], a[href*="logout.x"], .loggedinusername');
  }

  // ---------- PWA: manifest, ícones, service worker ----------
  function setupPwa() {
    var head = document.head || document.getElementsByTagName('head')[0];
    if (!document.querySelector('link[rel="manifest"]')) {
      var m = document.createElement('link');
      m.rel = 'manifest';
      m.href = CONFIG.manifestUrl;
      head.appendChild(m);
    }
    if (!document.querySelector('meta[name="theme-color"]')) {
      var t = document.createElement('meta');
      t.name = 'theme-color';
      t.content = CONFIG.themeColor;
      head.appendChild(t);
    }
    if (!document.querySelector('link[rel="apple-touch-icon"]')) {
      var a = document.createElement('link');
      a.rel = 'apple-touch-icon';
      a.href = '/koha-nexus-pwa/icons/icon-192.png';
      head.appendChild(a);
    }
    // Service worker só funciona em HTTPS (ou localhost).
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
      navigator.serviceWorker.register(CONFIG.serviceWorkerUrl).catch(function () { /* sem SW, o site segue normal */ });
    }
  }

  // ---------- Leitura do número do cartão ----------
  function valueAfterLabel(el) {
    // 1) texto logo depois do rótulo (nó de texto irmão)
    var n = el.nextSibling;
    while (n && n.nodeType === 3 && !n.textContent.trim()) n = n.nextSibling;
    if (n && n.nodeType === 3) return n.textContent.trim();
    // 2) elemento irmão (ex.: <dt>/<dd>, <th>/<td>)
    if (el.nextElementSibling) return el.nextElementSibling.textContent.trim();
    // 3) texto do pai menos o próprio rótulo
    if (el.parentElement) {
      return el.parentElement.textContent.replace(el.textContent, '').trim();
    }
    return '';
  }

  function cleanCardNumber(v) {
    v = (v || '').split(/[\r\n]/)[0].trim();
    if (!v || v.length > 40) return '';
    // Código 128 aceita ASCII; aqui só aceitamos caracteres comuns de carteirinha.
    return /^[A-Za-z0-9._\/\- ]+$/.test(v) ? v : '';
  }

  function readCardFromDocument(doc) {
    var leaves = doc.querySelectorAll('dt, th, td, label, span, strong, b, li, p, div');
    for (var i = 0; i < leaves.length; i++) {
      var el = leaves[i];
      if (el.children.length) continue;
      if (!CARD_LABEL.test(norm(el.textContent))) continue;
      var v = cleanCardNumber(valueAfterLabel(el));
      if (v) return v;
    }
    return '';
  }

  function readHolderName(doc) {
    var el = doc.querySelector('.loggedinusername');
    return el ? el.textContent.trim() : '';
  }

  function fetchAccount() {
    return fetch(CONFIG.accountUrl, { credentials: 'same-origin', headers: { Accept: 'text/html' } })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        return { cardnumber: readCardFromDocument(doc), name: readHolderName(doc) };
      });
  }

  // ---------- JsBarcode (carregado sob demanda) ----------
  var barcodeReady = null;
  function loadJsBarcode() {
    if (window.JsBarcode) return Promise.resolve();
    if (barcodeReady) return barcodeReady;
    barcodeReady = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = CONFIG.jsBarcodeUrl;
      s.async = true;
      s.onload = function () { window.JsBarcode ? resolve() : reject(new Error('JsBarcode')); };
      s.onerror = function () { barcodeReady = null; reject(new Error('JsBarcode')); };
      document.head.appendChild(s);
    });
    return barcodeReady;
  }

  // ---------- Interface ----------
  var ui = null;
  var lastFocus = null;
  var wakeLock = null;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function buildUi() {
    var open = el('button', 'kn-pwa-open', 'Carteirinha digital');
    open.type = 'button';
    open.setAttribute('aria-haspopup', 'dialog');

    var overlay = el('div', 'kn-pwa-overlay');
    overlay.hidden = true;

    var dialog = el('div', 'kn-pwa-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'kn-pwa-title');

    var close = el('button', 'kn-pwa-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Fechar carteirinha');

    var lib = el('p', 'kn-pwa-lib', CONFIG.libraryName || 'Biblioteca');
    var title = el('h2', 'kn-pwa-title', 'Carteirinha digital');
    title.id = 'kn-pwa-title';
    var name = el('p', 'kn-pwa-name', '');
    var status = el('p', 'kn-pwa-status', 'Carregando sua carteirinha…');
    status.setAttribute('role', 'status');

    var svgNS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class', 'kn-pwa-barcode');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Código de barras da carteirinha');
    svg.style.display = 'none';

    var hint = el('p', 'kn-pwa-hint', 'Apresente esta tela no balcão. Se o leitor não reconhecer, aumente o brilho do celular.');

    dialog.appendChild(close);
    dialog.appendChild(lib);
    dialog.appendChild(title);
    dialog.appendChild(name);
    dialog.appendChild(status);
    dialog.appendChild(svg);
    dialog.appendChild(hint);
    overlay.appendChild(dialog);
    document.body.appendChild(open);
    document.body.appendChild(overlay);

    ui = { open: open, overlay: overlay, dialog: dialog, close: close, name: name, status: status, svg: svg };

    open.addEventListener('click', showCard);
    close.addEventListener('click', hideCard);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) hideCard(); });
    document.addEventListener('keydown', function (e) {
      if (overlay.hidden) return;
      if (e.key === 'Escape') hideCard();
      if (e.key === 'Tab') { e.preventDefault(); close.focus(); } // mantém o foco no diálogo
    });
  }

  function requestWakeLock() {
    try {
      if ('wakeLock' in navigator) {
        navigator.wakeLock.request('screen').then(function (l) { wakeLock = l; }).catch(function () {});
      }
    } catch (e) { /* opcional */ }
  }

  function releaseWakeLock() {
    if (wakeLock) { wakeLock.release().catch(function () {}); wakeLock = null; }
  }

  function showCard() {
    lastFocus = document.activeElement;
    ui.overlay.hidden = false;
    document.body.classList.add('kn-pwa-lock');
    ui.close.focus();
    requestWakeLock();
    ui.status.hidden = false;
    ui.status.textContent = 'Carregando sua carteirinha…';
    ui.svg.style.display = 'none';
    ui.name.textContent = '';

    Promise.all([fetchAccount(), loadJsBarcode()])
      .then(function (res) {
        var data = res[0];
        ui.name.textContent = data.name || readHolderName(document);
        if (!data.cardnumber) {
          ui.status.textContent = 'Não foi possível ler o número da sua carteirinha. Entre na sua conta e tente de novo, ou fale com a biblioteca.';
          return;
        }
        window.JsBarcode(ui.svg, data.cardnumber, {
          format: 'CODE128',
          width: 2,            // módulo largo o bastante para scanners óticos comuns
          height: 90,
          margin: 12,
          displayValue: true,
          fontSize: 18,
          font: 'monospace',
          background: '#ffffff',
          lineColor: '#000000'
        });
        ui.svg.style.display = '';
        ui.status.hidden = true;
        ui.svg.setAttribute('aria-label', 'Código de barras da carteirinha ' + data.cardnumber);
      })
      .catch(function () {
        ui.status.textContent = 'Não foi possível carregar a carteirinha. Verifique sua conexão e se você está logado.';
      });
  }

  function hideCard() {
    ui.overlay.hidden = true;
    document.body.classList.remove('kn-pwa-lock');
    releaseWakeLock();
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  // ---------- Início ----------
  function init() {
    setupPwa();
    if (!isLoggedIn()) return;
    buildUi();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
