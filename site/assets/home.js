/* Shared behaviour; all page text is rendered at build time. */
const SITE_ROOT = new URL("../../", document.currentScript.src);
const SITE_MESSAGES = JSON.parse(document.getElementById("site-messages").textContent);
function siteText(key) { return SITE_MESSAGES[key] || ""; }
const SITE_LANGUAGE_KEY = "koha_lang";
function rememberSiteLanguage(code) {
  try { localStorage.setItem(SITE_LANGUAGE_KEY, code); } catch (e) {}
}
(function () {
  const current = new URL(location.href);
  const links = Array.from(document.querySelectorAll("[data-language]"));
  const aliases = {br: "pt", "pt-br": "pt", fil: "tl"};
  function match(value) {
    const tag = String(value || "").toLowerCase().replace(/_/g, "-");
    const base = tag.split("-")[0];
    const code = aliases[tag] || aliases[base] || base;
    return links.find(a => a.dataset.language === code);
  }
  const hashLanguage = match(current.hash.slice(1));
  const requested = current.searchParams.get("lang") || (hashLanguage ? current.hash.slice(1) : "");
  let link;
  if (requested) {
    link = match(requested);
    if (link) rememberSiteLanguage(link.dataset.language);
  } else if (current.pathname === SITE_ROOT.pathname || current.pathname === SITE_ROOT.pathname + "index.html") {
    // Explicit translated URLs stay in their language. Only the root detects.
    let saved;
    try { saved = localStorage.getItem(SITE_LANGUAGE_KEY); } catch (e) {}
    link = match(saved);
    const preferred = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language];
    if (!link) link = preferred.map(match).find(Boolean);
  }
  if (link && link.dataset.language !== document.body.dataset.language) {
    const url = new URL(link.href);
    current.searchParams.delete("lang");
    url.search = current.search;
    if (!hashLanguage) url.hash = current.hash;
    location.replace(url.href);
  }
})();
document.querySelectorAll("[data-language]").forEach(a => a.addEventListener("click", () => {
  rememberSiteLanguage(a.dataset.language);
  if (location.hash && !Array.from(document.querySelectorAll("[data-language]")).some(link => link.dataset.language === location.hash.slice(1))) a.hash = location.hash;
}));
    function copyFallback(value) {
      const area = document.createElement("textarea");
      area.value = value;
      area.setAttribute("readonly", "");
      area.style.cssText = "position:fixed; top:-1000px; opacity:0;";
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (e) {}
      area.remove();
      return ok;
    }

    document.querySelectorAll(".copy").forEach(button => {
      button.addEventListener("click", async () => {
        const value = button.dataset.copy || "";
        const original = button.innerHTML;
        let ok = false;
        try {
          await navigator.clipboard.writeText(value);
          ok = true;
        } catch (e) {
          ok = copyFallback(value);
        }
        button.textContent = ok ? "✓" : "✗";
        setTimeout(() => button.innerHTML = original, ok ? 1600 : 2200);
      });
    });

    // ----------------------------------------------------------------------
    // Rede pública: lista de bibliotecas vinda do broker (Cloudflare Worker)
    // ----------------------------------------------------------------------
    async function loadLibraries() {
      const grid = document.getElementById("libraries-grid");
      if (!grid) return;

      const message = (text, color) => {
        grid.innerHTML = "";
        const div = document.createElement("div");
        div.style.cssText = `grid-column: 1 / -1; text-align: center; color: var(${color}); padding: 40px 0;`;
        div.textContent = text;
        grid.appendChild(div);
      };

      try {
        const response = await fetch("https://broker.koha.nexus/api/public-libraries");
        if (!response.ok) throw new Error("HTTP " + response.status);
        const libraries = await response.json();

        if (!Array.isArray(libraries) || libraries.length === 0) {
          message(siteText("network_empty"), "--muted");
          return;
        }

        grid.innerHTML = "";
        libraries.forEach(lib => {
          // Os nomes vêm do cadastro das bibliotecas: nunca inserir como HTML
          if (!lib || !/^https:\/\//.test(lib.url || "")) return;
          const card = document.createElement("a");
          card.href = lib.url;
          card.target = "_blank";
          card.rel = "noopener";
          card.className = "card";
          card.style.cssText = "display:flex; flex-direction:column; justify-content:center; text-align:center; padding:32px;";

          const title = document.createElement("h3");
          title.style.marginBottom = "4px";
          title.textContent = lib.name || lib.domain;
          const domain = document.createElement("span");
          domain.style.cssText = "color:var(--green); font-size:0.85rem;";
          domain.textContent = lib.domain || "";

          card.append(title, domain);
          grid.appendChild(card);
        });
      } catch (error) {
        console.error("Failed to fetch libraries:", error);
        message(siteText("network_error"), "--danger");
      }
    }

    loadLibraries();



    // ----------------------------------------------------------------------
    // Formulário de contato (Formspree): envio com fetch, confirmação na
    // própria página. Sem JavaScript o formulário faz um POST comum.
    // Os placeholders seguem o idioma escolhido (data-i18n-ph).
    // ----------------------------------------------------------------------
    (function () {
      function tr(key) { return siteText(key); }
      const form = document.getElementById("contact-form");
      if (!form || !window.fetch) return;
      const status = document.getElementById("contact-status");
      const send = document.getElementById("contact-send");
      const fields = Array.from(form.querySelectorAll("input[required], textarea[required]"));

      function show(kind, key) {
        status.hidden = false;
        status.className = "contact-status " + kind;
        status.textContent = tr(key);
      }
      fields.forEach(el => el.addEventListener("input", () => el.classList.remove("invalid")));

      form.addEventListener("submit", async event => {
        event.preventDefault();
        const bad = fields.filter(el => !el.value.trim() || !el.checkValidity());
        fields.forEach(el => el.classList.toggle("invalid", bad.includes(el)));
        if (bad.length) { bad[0].focus(); return; }

        const label = send.innerHTML;
        send.disabled = true;
        send.textContent = tr("ct_sending");
        status.hidden = true;
        try {
          const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "Accept": "application/json" }
          });
          if (!response.ok) throw new Error("HTTP " + response.status);
          form.reset();
          show("ok", "ct_ok");
        } catch (error) {
          console.error("Contact form:", error);
          show("err", "ct_err");
        } finally {
          send.disabled = false;
          send.innerHTML = label;
        }
      });
    })();

    // ----------------------------------------------------------------------
    // Movimento e navegação: barra de progresso, menu ativo, menu no celular,
    // revelar ao rolar, contadores, vitrine do painel e voltar ao topo.
    // Nada aqui mexe na rede pública (loadLibraries) nem nas traduções.
    // ----------------------------------------------------------------------
    (function () {
      const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const $ = (sel, root) => (root || document).querySelector(sel);
      const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

      // Barra de progresso e botão "voltar ao topo"
      const bar = $("#scroll-progress");
      const toTop = $("#to-top");
      let ticking = false;
      function onScroll() {
        ticking = false;
        const doc = document.documentElement;
        const max = doc.scrollHeight - window.innerHeight;
        const ratio = max > 0 ? Math.min(1, window.scrollY / max) : 0;
        if (bar) bar.style.transform = "scaleX(" + ratio + ")";
        if (toTop) toTop.classList.toggle("show", window.scrollY > 700);
      }
      window.addEventListener("scroll", () => {
        if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
      }, { passive: true });
      onScroll();
      if (toTop) toTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" }));

      // Menu no celular
      const nav = $("#main-nav");
      const toggle = $("#menu-toggle");
      if (nav && toggle) {
        toggle.addEventListener("click", () => {
          const open = nav.classList.toggle("open");
          toggle.setAttribute("aria-expanded", open ? "true" : "false");
          toggle.textContent = open ? "✕" : "☰";
        });
        nav.addEventListener("click", e => {
          if (e.target.closest("a") && nav.classList.contains("open")) toggle.click();
        });
      }

      // Link do menu da seção visível
      const links = nav ? $$("a[href^='#']", nav) : [];
      const sections = links.map(a => document.getElementById(a.getAttribute("href").slice(1))).filter(Boolean);
      if ("IntersectionObserver" in window && sections.length) {
        const seen = new Map();
        const spy = new IntersectionObserver(entries => {
          entries.forEach(en => seen.set(en.target.id, en.isIntersecting ? en.intersectionRatio : 0));
          let best = null, bestRatio = 0;
          seen.forEach((r, id) => { if (r > bestRatio) { bestRatio = r; best = id; } });
          links.forEach(a => a.classList.toggle("active", best !== null && a.getAttribute("href") === "#" + best));
        }, { rootMargin: "-35% 0px -55% 0px", threshold: [0, 0.01, 0.25, 0.5, 1] });
        sections.forEach(sec => spy.observe(sec));
      }

      // Revelar ao rolar (os cartões da rede pública chegam depois e não entram aqui)
      if (!reduce && "IntersectionObserver" in window) {
        const items = $$(".section-heading, .card, .step, .download-banner, .table-wrap, .showcase, .stat")
          .filter(el => !el.closest("#libraries-grid") && !el.closest(".hero"));
        const groups = new Map();
        items.forEach(el => {
          const parent = el.parentElement;
          const i = groups.get(parent) || 0;
          groups.set(parent, i + 1);
          el.dataset.rd = String(Math.min(i, 6) * 70);
          el.classList.add("reveal");
        });
        const io = new IntersectionObserver(entries => {
          entries.forEach(en => {
            if (en.isIntersecting) {
              const el = en.target;
              io.unobserve(el);
              setTimeout(() => el.classList.add("in"), parseInt(el.dataset.rd || "0", 10));
            }
          });
        }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
        items.forEach(el => io.observe(el));
      }

      // Contadores dos números do topo ("22 idiomas" conta de 0 a 22)
      function countUp(el) {
        const m = (el.textContent || "").match(/\d+/);
        if (!m) return;
        const target = parseInt(m[0], 10);
        const start = performance.now();
        const dur = 1100;
        function frame(now) {
          const t = Math.min(1, (now - start) / dur);
          const value = Math.round(target * (1 - Math.pow(1 - t, 3)));
          // Relê o texto a cada quadro: se o idioma mudar no meio, vale o novo.
          el.innerHTML = el.innerHTML.replace(/\d+/, String(value));
          if (t < 1) requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      }
      if (!reduce) {
        window.addEventListener("load", () => $$(".stat strong").forEach(countUp));
      }

      // Luz que segue o ponteiro nos cartões
      document.addEventListener("pointermove", e => {
        const card = e.target.closest && e.target.closest(".card");
        if (!card) return;
        const r = card.getBoundingClientRect();
        card.style.setProperty("--mx", (e.clientX - r.left) + "px");
        card.style.setProperty("--my", (e.clientY - r.top) + "px");
      }, { passive: true });

      // Vitrine do painel: abas, setas do teclado, troca automática e link para o manual
      const tabs = $$(".tab[data-shot]");
      const img = $("#shot-img");
      const shot = $("#shot");
      const dots = $$(".stage-dots i");
      const stage = $("#panel-stage");
      let current = 0, timer = null, userPicked = false;
      const preload = {};
      function select(i, focus) {
        if (!tabs.length || !img) return;
        current = (i + tabs.length) % tabs.length;
        const name = tabs[current].dataset.shot;
        tabs.forEach((t, n) => {
          t.setAttribute("aria-selected", n === current ? "true" : "false");
          t.tabIndex = n === current ? 0 : -1;
        });
        $$(".pane[data-pane]").forEach(p => { p.hidden = p.dataset.pane !== name; });
        dots.forEach((d, n) => d.classList.toggle("on", n === current));
        if (stage) stage.setAttribute("aria-labelledby", tabs[current].id);
        // The screenshot opens this screen in the interactive manual.
        if (shot) shot.setAttribute("href", "preview/#" + name);
        const src = new URL("docs/images/panel/" + name + ".webp", SITE_ROOT).href;
        if (!img.src.endsWith(src)) {
          shot.classList.add("loading");
          const next = new Image();
          next.onload = next.onerror = () => {
            img.src = src;
            img.alt = tabs[current].textContent.trim();
            shot.classList.remove("loading");
          };
          next.src = src;
        }
        if (focus) tabs[current].focus();
      }
      tabs.forEach((t, n) => {
        t.addEventListener("click", () => { userPicked = true; stop(); select(n); });
        t.addEventListener("keydown", e => {
          const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
          if (step) { e.preventDefault(); userPicked = true; stop(); select(current + step, true); }
          else if (e.key === "Home") { e.preventDefault(); select(0, true); }
          else if (e.key === "End") { e.preventDefault(); select(tabs.length - 1, true); }
        });
      });
      function stop() { if (timer) { clearInterval(timer); timer = null; } }
      function play() {
        if (reduce || userPicked || timer) return;
        timer = setInterval(() => select(current + 1), 6500);
      }
      if (stage && "IntersectionObserver" in window) {
        new IntersectionObserver(entries => {
          entries.forEach(en => {
            if (en.isIntersecting) {
              // As outras telas só são baixadas quando a vitrine aparece.
              tabs.forEach(t => {
                const n = t.dataset.shot;
                if (!preload[n]) { preload[n] = new Image(); preload[n].src = new URL("docs/images/panel/" + n + ".webp", SITE_ROOT).href; }
              });
              play();
            } else stop();
          });
        }, { threshold: 0.3 }).observe(stage);
        stage.addEventListener("mouseenter", stop);
        stage.addEventListener("mouseleave", play);
      }

    })();
