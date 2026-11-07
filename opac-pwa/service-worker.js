/*
 * Koha.Nexus - service worker do OPAC (PWA).
 * Instalar em: /usr/share/koha/opac/htdocs/service-worker.js (raiz do OPAC, escopo "/").
 *
 * Regras de privacidade:
 *  - Páginas do Koha (/cgi-bin/...), HTML e dados de leitor NUNCA entram no cache.
 *  - Só ficam em cache arquivos estáticos (CSS, JS, imagens, fontes) e a biblioteca JsBarcode.
 *  - Ao navegar sem conexão, mostra uma página offline genérica.
 */
'use strict';

const VERSION = 'koha-nexus-pwa-v1';
const STATIC_CACHE = VERSION + '-static';

// Arquivos locais essenciais (caminhos absolutos a partir da raiz do OPAC).
const PRECACHE = [
  '/koha-nexus-pwa/offline.html',
  '/koha-nexus-pwa/carteirinha.css',
  '/koha-nexus-pwa/carteirinha.js',
  '/koha-nexus-pwa/icons/icon-192.png',
  '/koha-nexus-pwa/icons/icon-512.png',
  '/koha-nexus-pwa/icons/icon-maskable-512.png',
  '/manifest.json'
];

// Biblioteca externa usada pela carteirinha (CORS habilitado pelo cdnjs).
const JSBARCODE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/jsbarcode/3.11.6/JsBarcode.all.min.js';
const CROSS_ORIGIN_CACHE = [JSBARCODE_URL];

const STATIC_EXT = /\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|otf)$/i;

function isStaticSameOrigin(url) {
  if (url.pathname.startsWith('/cgi-bin/')) return false;
  if (url.pathname.startsWith('/koha-nexus-pwa/') || url.pathname.startsWith('/opac-tmpl/')) return true;
  return STATIC_EXT.test(url.pathname);
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(STATIC_CACHE);
    // Um arquivo ausente não deve impedir a instalação do restante.
    await Promise.allSettled(PRECACHE.map((u) => cache.add(new Request(u, { cache: 'reload' }))));
    await Promise.allSettled(CROSS_ORIGIN_CACHE.map((u) => cache.add(new Request(u, { mode: 'cors' }))));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((k) => k.startsWith('koha-nexus-pwa-') && k !== STATIC_CACHE)
        .map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

async function staleWhileRevalidate(event, request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok && (response.type === 'basic' || response.type === 'cors')) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);
  event.waitUntil(network);
  if (cached) return cached;
  const fresh = await network;
  return fresh || Response.error();
}

async function navigateOrOffline(request) {
  try {
    // Navegação sempre pela rede; a resposta não é guardada.
    return await fetch(request);
  } catch (err) {
    const cache = await caches.open(STATIC_CACHE);
    const offline = await cache.match('/koha-nexus-pwa/offline.html');
    return offline || Response.error();
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  if (request.mode === 'navigate' && url.origin === self.location.origin) {
    event.respondWith(navigateOrOffline(request));
    return;
  }

  if (url.origin === self.location.origin && isStaticSameOrigin(url)) {
    event.respondWith(staleWhileRevalidate(event, request));
    return;
  }

  if (CROSS_ORIGIN_CACHE.includes(request.url)) {
    event.respondWith(staleWhileRevalidate(event, request));
    return;
  }

  // Todo o resto (consultas, contas de leitor, APIs) segue direto para a rede, sem cache.
});
