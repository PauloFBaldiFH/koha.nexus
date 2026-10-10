/* koha.nexus interactive preview and manual.
 *
 * Reads data/preview.json (export_docs_preview.py) and draws:
 *   - the sidebar: the panel's sections, their screen parts and their cards;
 *   - the simulator: the panel window for the chosen section, drawn from the
 *     same menus and t() keys as the real panel, in the chosen language;
 *   - the screenshot of the real panel, when there is one;
 *   - the manual of the chosen item.
 *
 * Language: ?lang= first, then the website's choice (localStorage koha_lang,
 * the same key index.html writes, "br" meaning pt-BR), then the browser.
 * Changing it here writes it back, so the site and the preview stay in step;
 * a page that embeds this one can also post {type: "koha-nexus:lang", lang}.
 * No framework and no build step.
 */
(function () {
  "use strict";

  var root = document.getElementById("kp-app");
  // Paths are taken from the preview folder (the parent of assets/), not from
  // the page's URL, so /preview, /preview/ and /preview/index.html all work.
  var HERE = new URL("../", (document.currentScript && document.currentScript.src) || location.href);
  var SRC = new URL(root.getAttribute("data-src") || "data/preview.json", HERE).href;
  var ASSET_BASE = new URL(root.getAttribute("data-asset-base") || "../", HERE).href;
  var STORE_KEY = "koha_lang";

  // English defaults of the page's own texts; preview/manual/<lang>.json "ui" overrides them.
  var UI = {
    title: "Interactive preview & manual",
    subtitle: "Every screen of the control panel, explained.",
    search: "Search",
    language: "Language",
    menu: "Menu",
    mockup: "Simulator",
    screenshot: "Screenshot",
    loading: "Loading the manual…",
    load_error: "The manual could not be loaded.",
    footer: "Generated from the panel's code by export_docs_preview.py.",
    version: "Panel version",
    overview: "What it does",
    steps: "Step by step",
    options: "Options explained",
    tips: "Best practices",
    warnings: "Watch out",
    related: "Related",
    where: "Where",
    shortcut: "Key",
    kind_section: "Screen",
    kind_entry: "Card",
    kind_feature: "Screen part",
    pending: "Pending",
    pending_note: "This part is described as planned: it is not in the published panel yet.",
    untranslated: "This guide is not translated into this language yet: it is shown in English.",
    outdated: "The English text of this guide changed after it was translated: the translation may be behind.",
    no_manual: "No guide has been written for this item yet.",
    no_results: "Nothing matches.",
    full_manual: "Full manual",
    panel_only: "Panel texts (guide in English)",
    exit: "Exit",
    back_to_site: "Back to koha.nexus",
    screenshot_of: "The real panel"
  };
  var SAMPLE = { age: "7 h", code: "200", port: "210", n: "12", name: "koha.nexus", model: "gemini-flash-latest" };

  var data = null;
  var lang = "en";
  var current = { section: "dashboard", item: "sec-dashboard" };
  var els = {
    nav: document.getElementById("kp-nav"),
    mock: document.getElementById("kp-mock"),
    shot: document.getElementById("kp-shot"),
    doc: document.getElementById("kp-doc"),
    search: document.getElementById("kp-search"),
    lang: document.getElementById("kp-lang"),
    menu: document.getElementById("kp-menu"),
    tabMock: document.getElementById("kp-tab-mock"),
    tabShot: document.getElementById("kp-tab-shot"),
    version: document.getElementById("kp-version")
  };

  // ------------------------------------------------------------------
  // Small helpers
  // ------------------------------------------------------------------
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") el.className = v;
        else if (k === "text") el.textContent = v;
        else if (k === "html") el.innerHTML = v;
        else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? "" : v);
      });
    }
    (children || []).forEach(function (c) {
      if (c === null || c === undefined) return;
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Manual text: plain text with **bold**, `code` and [label](#item) links.
  function rich(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\(#([a-z0-9-]+)\)/g, '<a href="#$2" data-goto="$2">$1</a>');
  }

  function fill(s) {
    return String(s).replace(/\$\{([A-Za-z_]+)(?::-[^}]*)?\}/g, function (_, k) { return SAMPLE[k] || ""; });
  }

  // A panel text (t() key) in the chosen language, English when it has none.
  function t(key) {
    if (!key) return "";
    var row = data.strings[key];
    return fill((row && row[lang]) || key);
  }

  function ui(key) {
    var row = data && data.ui[key];
    return (row && (row[lang] || row.en)) || UI[key] || key;
  }

  // "📦  Install Koha server" -> ["📦", "Install Koha server"]
  function splitIcon(label) {
    var m = /^(\S+)\s{1,2}(.*)$/.exec(label || "");
    if (m && !/[A-Za-z0-9]/.test(m[1])) return [m[1], m[2]];
    return ["", label || ""];
  }

  function cleanTitle(s) { return String(s).replace(/[:：]\s*$/, ""); }

  function item(id) { return data.items[id]; }
  function section(id) {
    for (var i = 0; i < data.sections.length; i++) if (data.sections[i].id === id) return data.sections[i];
    return null;
  }

  function manualOf(id) {
    var m = data.manual[id] || {};
    return { local: m[lang] || null, en: m.en || null };
  }

  function itemLabel(id) {
    var it = item(id);
    if (!it) return id;
    var m = manualOf(id);
    if (m.local && m.local.title) return m.local.title;
    if (lang === "en" && m.en && m.en.title) return m.en.title;
    return cleanTitle(splitIcon(t(it.label))[1] || t(it.label));
  }

  function sectionItem(sec) { return sec.single || sec.item; }

  // ------------------------------------------------------------------
  // Language
  // ------------------------------------------------------------------
  function langFromCode(code) {
    if (!code) return null;
    code = String(code).trim();
    var low = code.toLowerCase();
    if (low === "br" || low === "pt" || low.indexOf("pt-") === 0 || low.indexOf("pt_") === 0) low = "pt-br";
    for (var i = 0; i < data.languages.length; i++) {
      var L = data.languages[i];
      if (L.code.toLowerCase() === low || L.site === low || L.panel.toLowerCase() === low) return L.code;
    }
    var base = low.split(/[-_]/)[0];
    for (var j = 0; j < data.languages.length; j++) if (data.languages[j].dict === base) return data.languages[j].code;
    return null;
  }

  function langInfo(code) {
    for (var i = 0; i < data.languages.length; i++) if (data.languages[i].code === code) return data.languages[i];
    return data.languages[0];
  }

  function initialLang() {
    var q = new URLSearchParams(location.search).get("lang");
    var stored = null;
    try { stored = localStorage.getItem(STORE_KEY); } catch (e) { /* private mode */ }
    return langFromCode(q) || langFromCode(stored) || langFromCode(navigator.language) || "en";
  }

  function setLanguage(code, opts) {
    var next = langFromCode(code) || "en";
    var info = langInfo(next);
    lang = next;
    document.documentElement.lang = lang;
    document.documentElement.dir = info.dir || "ltr";
    els.lang.value = lang;
    if (!opts || opts.store !== false) {
      try { localStorage.setItem(STORE_KEY, info.site); } catch (e) { /* private mode */ }
      var url = new URL(location.href);
      url.searchParams.set("lang", info.site);
      history.replaceState(null, "", url);
    }
    translateChrome();
    renderNav();
    show(current.section, current.item, { keepScroll: true });
    applySearch();
  }

  function buildLangSelect() {
    var full = h("optgroup", { label: ui("full_manual") });
    var partial = h("optgroup", { label: ui("panel_only") });
    data.languages.forEach(function (L) {
      (L.manual ? full : partial).appendChild(h("option", { value: L.code, text: L.name }));
    });
    els.lang.innerHTML = "";
    els.lang.appendChild(full);
    if (partial.children.length) els.lang.appendChild(partial);
  }

  function translateChrome() {
    document.querySelectorAll("[data-ui]").forEach(function (el) { el.textContent = ui(el.getAttribute("data-ui")); });
    document.querySelectorAll("[data-ui-title]").forEach(function (el) { el.title = ui(el.getAttribute("data-ui-title")); });
    els.search.placeholder = ui("search");
    var groups = els.lang.querySelectorAll("optgroup");
    if (groups[0]) groups[0].label = ui("full_manual");
    if (groups[1]) groups[1].label = ui("panel_only");
    els.version.textContent = ui("version") + " " + data.panel_version;
    document.title = "koha.nexus · " + ui("title");
  }

  // ------------------------------------------------------------------
  // Sidebar
  // ------------------------------------------------------------------
  function childIds(sec) {
    if (sec.single) return [];
    var ids = sec.features.slice();
    sec.entries.forEach(function (id) {
      var it = item(id);
      if (it && it.status !== "hidden" && ids.indexOf(id) < 0) ids.push(id);
    });
    return ids;
  }

  function renderNav() {
    els.nav.innerHTML = "";
    data.sections.forEach(function (sec) {
      if (!sec.sidebar) return;
      var main = sectionItem(sec);
      var parts = splitIcon(t(sec.label));
      var group = h("div", { class: "kp-group", "data-section": sec.id });
      var kids = childIds(sec);
      var head = h("button", {
        type: "button", "data-item": main, "data-in": sec.id,
        "aria-current": current.item === main && current.section === sec.id ? "true" : null,
        onclick: function () { go(sec.id, main); group.classList.add("kp-open"); }
      }, [
        kids.length ? h("span", { class: "kp-caret", "aria-hidden": "true", text: "▶" }) : null,
        h("span", { "aria-hidden": "true", text: parts[0] || sec.icon || "•" }),
        h("span", { class: "kp-label", text: parts[1] }),
        sec.key ? h("kbd", { class: "kp-key", title: ui("shortcut"), text: sec.key }) : null
      ]);
      group.appendChild(head);
      if (kids.length) {
        var list = h("div", { class: "kp-children" });
        kids.forEach(function (id) {
          var it = item(id);
          if (!it) return;
          // A view entry (WireGuard VPN in the Security hub) opens its own screen.
          var target = it.type === "section" ? it.section : sec.id;
          list.appendChild(h("button", {
            type: "button", class: "kp-child kp-" + it.type, "data-item": id, "data-in": target,
            "aria-current": current.item === id && current.section === target ? "true" : null,
            onclick: function () { go(target, id); }
          }, [h("span", { class: "kp-label", text: itemLabel(id) }),
              it.status === "pending" ? h("span", { class: "kp-badge", text: ui("pending") }) : null]));
        });
        group.appendChild(list);
      }
      if (sec.id === current.section || (section(current.section) || {}).parent === sec.id) group.classList.add("kp-open");
      els.nav.appendChild(group);
    });
  }

  function markNav() {
    var sec = section(current.section) || {};
    els.nav.querySelectorAll(".kp-group").forEach(function (g) {
      var id = g.getAttribute("data-section");
      g.classList.toggle("kp-open", id === current.section || id === sec.parent);
    });
    els.nav.querySelectorAll("[data-item]").forEach(function (b) {
      var on = b.getAttribute("data-item") === current.item && b.getAttribute("data-in") === current.section;
      if (on) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
    });
  }

  // ------------------------------------------------------------------
  // Search: labels and guide texts, in the chosen language and in English
  // ------------------------------------------------------------------
  function haystack(id) {
    var m = manualOf(id);
    var parts = [itemLabel(id), t((item(id) || {}).description)];
    [m.local, m.en].forEach(function (x) { if (x) parts.push(x.title || "", x.summary || ""); });
    return parts.join(" ").toLowerCase();
  }

  function applySearch() {
    var q = els.search.value.trim().toLowerCase();
    var any = false;
    els.nav.querySelectorAll(".kp-group").forEach(function (g) {
      var head = g.firstChild;
      var headHit = !q || haystack(head.getAttribute("data-item")).indexOf(q) >= 0;
      var kidHit = false;
      g.querySelectorAll(".kp-child").forEach(function (c) {
        var hit = !q || headHit || haystack(c.getAttribute("data-item")).indexOf(q) >= 0;
        c.classList.toggle("kp-hidden-by-search", !hit);
        if (hit && q) kidHit = true;
      });
      var show = headHit || kidHit;
      g.classList.toggle("kp-hidden-by-search", !show);
      if (q && kidHit) g.classList.add("kp-open");
      if (show) any = true;
    });
    var empty = els.nav.querySelector(".kp-nav-empty");
    if (!any && !empty) els.nav.appendChild(h("p", { class: "kp-nav-empty", text: ui("no_results") }));
    if (any && empty) empty.remove();
  }

  // ------------------------------------------------------------------
  // Simulator: the panel window
  // ------------------------------------------------------------------
  function control(c) {
    var label = c.label ? t(c.label) : "";
    switch (c.type) {
      case "button":
        return h("span", { class: "kp-btn" + (c.primary ? " kp-primary" : ""), text: label });
      case "select": {
        var opt = (c.options || [])[c.value || 0];
        var text = opt ? (opt.prefix ? opt.prefix + "  " : "") + (opt.literal ? opt.text : t(opt.text)) : "";
        return row(label, h("span", { class: "kp-ctl-select", title: (c.options || []).map(function (o) {
          return (o.prefix ? o.prefix + " " : "") + (o.literal ? o.text : t(o.text));
        }).join("\n"), text: text }));
      }
      case "switch":
        return row(label, h("span", { class: "kp-switch" + (c.on ? " kp-on" : ""), role: "img", "aria-label": c.on ? "on" : "off" }));
      case "input":
        return row(label, h("span", {
          class: "kp-ctl-input" + (c.value ? "" : " kp-placeholder"),
          text: c.value ? t(c.value) : t(c.placeholder) || " "
        }));
      case "slider": {
        var range = c.unit === " ms" ? 10000 : c.unit === "" ? 24 : 100;
        var pct = Math.max(4, Math.min(100, Math.round((c.value / range) * 100)));
        return row(label, h("span", { class: "kp-slider-row" }, [
          h("span", { class: "kp-slider" }, [h("b", { style: "width:" + pct + "%" }), h("em", { style: "inset-inline-start:" + pct + "%" })]),
          h("span", { text: c.value + (c.unit || "") })
        ]));
      }
      case "color":
        return row(label, h("span", {}, [h("span", { class: "kp-swatch", style: "background:" + c.value }), c.value]));
      case "status":
        return h("div", { class: "kp-card-status kp-" + (c.state || "ok") }, [h("small", { text: label }), h("strong", { text: t(c.value) })]);
      case "note":
        return h("p", { class: "kp-note", text: t(c.text) });
      case "table":
        return h("table", { class: "kp-table" }, [
          h("thead", {}, [h("tr", {}, c.columns.map(function (col) { return h("th", { text: t(col) }); }))]),
          h("tbody", {}, (c.rows || []).map(function (r) {
            return h("tr", {}, r.map(function (cell, i) { return h("td", { text: i === 1 ? t(cell) : cell, title: cell }); }));
          }))
        ]);
    }
    return null;
  }

  function row(label, ctl) { return h("div", { class: "kp-row" }, [h("span", { text: label }), ctl]); }

  // Buttons side by side, status cards in a grid, the rest one per line.
  function controls(list) {
    var out = [], buttons = null, cards = null;
    list.forEach(function (c) {
      var el = control(c);
      if (!el) return;
      if (c.type === "button") {
        if (!buttons) { buttons = h("div", { class: "kp-buttons" }); out.push(buttons); }
        buttons.appendChild(el); cards = null; return;
      }
      if (c.type === "status") {
        if (!cards) { cards = h("div", { class: "kp-status" }); out.push(cards); }
        cards.appendChild(el); buttons = null; return;
      }
      buttons = cards = null;
      out.push(el);
    });
    return out;
  }

  function card(id, secId) {
    var it = item(id);
    if (!it || it.status === "hidden") return null;
    return h("button", {
      type: "button", class: "kp-card kp-target", "data-item": id,
      onclick: function () { go(it.type === "section" ? it.section : secId, id); }
    }, [h("span", { text: t(it.label) }), it.description ? h("small", { text: t(it.description) }) : null]);
  }

  function renderMock(sec) {
    var win = els.mock;
    win.innerHTML = "";
    var side = h("div", { class: "kp-term-side" });
    data.sections.forEach(function (s) {
      if (!s.sidebar) return;
      var p = splitIcon(t(s.label));
      side.appendChild(h("button", {
        type: "button", text: (p[0] || s.icon || " ") + " " + p[1],
        "aria-current": s.id === sec.id || s.id === sec.parent ? "true" : null,
        onclick: function () { go(s.id, sectionItem(s)); }
      }));
    });

    var main = h("div", { class: "kp-term-main" });
    var title = sec.title || sec.label;
    var tp = splitIcon(t(title));
    main.appendChild(h("p", { class: "kp-term-title", text: (tp[0] || sec.icon || "") + " " + tp[1] }));
    if (sec.prompt) main.appendChild(h("p", { class: "kp-term-prompt", text: t(sec.prompt) }));
    else if (item(sec.item) && item(sec.item).description) main.appendChild(h("p", { class: "kp-term-prompt", text: t(item(sec.item).description) }));

    sec.features.forEach(function (fid) {
      var f = item(fid);
      var box = h("div", { class: "kp-box kp-target", "data-item": fid, onclick: function () { go(sec.id, fid); } },
        [h("span", { class: "kp-box-title", text: cleanTitle(t(f.label)) })].concat(controls(f.controls || [])));
      main.appendChild(box);
    });
    var cards = h("div", { class: "kp-cards" });
    sec.entries.forEach(function (id) { var c = card(id, sec.id); if (c) cards.appendChild(c); });
    if (cards.children.length) main.appendChild(cards);

    var keys = data.sections.filter(function (s) { return s.key; }).slice(0, 8).map(function (s) {
      return h("span", {}, [h("b", { text: s.key }), " " + splitIcon(t(s.label))[1]]);
    });
    keys.push(h("span", {}, [h("b", { text: "q" }), " " + t("Exit")]));

    win.appendChild(h("div", { class: "kp-titlebar", "aria-hidden": "true" }, [h("i"), h("i"), h("i"), h("span", { text: "sudo config.sh · koha.nexus" + data.panel_version.replace(/^/, " ") })]));
    win.appendChild(h("div", { class: "kp-term" }, [side, main]));
    win.appendChild(h("div", { class: "kp-term-foot" }, keys));
  }

  function focusMock(id) {
    var main = els.mock.querySelector(".kp-term-main");
    if (!main) return;
    els.mock.querySelectorAll(".kp-focus").forEach(function (e) { e.classList.remove("kp-focus"); });
    var target = main.querySelector('[data-item="' + id + '"]');
    if (!target) { main.scrollTop = 0; return; }
    void target.offsetWidth;          // restart the pulse
    target.classList.add("kp-focus");
    main.scrollTop = Math.max(0, target.offsetTop - 24);
  }

  // ------------------------------------------------------------------
  // Screenshots
  // ------------------------------------------------------------------
  function mediaFor(id, sec) {
    var it = item(id) || {};
    var list = (it.media || []).slice();
    (sec.media || []).forEach(function (m) { if (list.indexOf(m) < 0) list.push(m); });
    return list;
  }

  function renderShot(list, label) {
    els.shot.innerHTML = "";
    els.tabShot.disabled = !list.length;
    if (!list.length) { selectTab("mock"); return; }
    var img = h("img", { src: ASSET_BASE + list[0], alt: ui("screenshot_of") + ": " + label, loading: "lazy" });
    els.shot.appendChild(img);
    els.shot.appendChild(h("figcaption", { text: ui("screenshot_of") + " · " + label }));
    if (list.length > 1) {
      var bar = h("div", { class: "kp-shot-list" });
      list.forEach(function (src, i) {
        bar.appendChild(h("button", {
          type: "button", "aria-pressed": i === 0 ? "true" : "false", text: String(i + 1),
          onclick: function (ev) {
            img.src = ASSET_BASE + src;
            bar.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
            ev.currentTarget.setAttribute("aria-pressed", "true");
          }
        }));
      });
      els.shot.appendChild(bar);
    }
  }

  function selectTab(which) {
    var mock = which !== "shot";
    els.tabMock.setAttribute("aria-selected", mock ? "true" : "false");
    els.tabShot.setAttribute("aria-selected", mock ? "false" : "true");
    els.mock.hidden = !mock;
    els.shot.hidden = mock;
  }

  // ------------------------------------------------------------------
  // The manual
  // ------------------------------------------------------------------
  function renderDoc(id, sec) {
    var it = item(id);
    var m = manualOf(id);
    var text = m.local || m.en;
    var doc = els.doc;
    doc.innerHTML = "";
    if (!it) return;

    var label = itemLabel(id);
    var icon = splitIcon(t(it.label))[0];
    doc.appendChild(h("h2", {}, [icon ? icon + " " : "", label]));

    var where = sec.id !== it.section || it.type !== "section" ? splitIcon(t(sec.label))[1] : "";
    var meta = h("div", { class: "kp-meta" }, [
      h("span", { class: "kp-chip", text: ui("kind_" + it.type) }),
      where ? h("span", { text: ui("where") + ": " + where }) : null,
      sec.key && (it.type === "section" || sec.single) ? h("span", {}, [ui("shortcut") + " ", h("kbd", { class: "kp-key", text: sec.key })]) : null,
      it.status === "pending" ? h("span", { class: "kp-badge", text: ui("pending") }) : null
    ]);
    doc.appendChild(meta);

    if (it.status === "pending") doc.appendChild(h("p", { class: "kp-notice kp-pending", text: ui("pending_note") }));
    if (!text) {
      doc.appendChild(h("p", { class: "kp-notice", text: ui("no_manual") }));
      if (it.description) doc.appendChild(h("p", { class: "kp-summary", text: t(it.description) }));
      return;
    }
    if (!m.local && lang !== "en") doc.appendChild(h("p", { class: "kp-notice", text: ui("untranslated") }));
    else if (m.local && m.local.outdated) doc.appendChild(h("p", { class: "kp-notice", text: ui("outdated") }));

    if (text.summary) doc.appendChild(h("p", { class: "kp-summary", html: rich(text.summary) }));
    if (text.overview && text.overview.length) {
      doc.appendChild(h("h3", { text: ui("overview") }));
      text.overview.forEach(function (p) { doc.appendChild(h("p", { html: rich(p) })); });
    }
    if (text.steps && text.steps.length) {
      doc.appendChild(h("h3", { text: ui("steps") }));
      doc.appendChild(h("ol", { class: "kp-steps" }, text.steps.map(function (s) { return h("li", { html: rich(s) }); })));
    }
    if (text.options && text.options.length) {
      doc.appendChild(h("h3", { text: ui("options") }));
      var dl = h("dl", { class: "kp-options" });
      text.options.forEach(function (o) {
        dl.appendChild(h("dt", { html: rich(o.name) }));
        dl.appendChild(h("dd", { html: rich(o.text) }));
      });
      doc.appendChild(dl);
    }
    if (text.tips && text.tips.length) {
      doc.appendChild(h("h3", { text: ui("tips") }));
      doc.appendChild(h("ul", { class: "kp-tips" }, text.tips.map(function (s) { return h("li", { html: rich(s) }); })));
    }
    if (text.warnings && text.warnings.length) {
      doc.appendChild(h("h3", { text: ui("warnings") }));
      doc.appendChild(h("ul", { class: "kp-warnings" }, text.warnings.map(function (s) { return h("li", { html: rich(s) }); })));
    }
    var related = ((m.en && m.en.related) || []).filter(function (r) { return item(r) && item(r).status !== "hidden"; });
    if (related.length) {
      doc.appendChild(h("h3", { text: ui("related") }));
      doc.appendChild(h("div", { class: "kp-related" }, related.map(function (r) {
        return h("a", { href: "#" + r, "data-goto": r, text: itemLabel(r) });
      })));
    }
  }

  // ------------------------------------------------------------------
  // Navigation
  // ------------------------------------------------------------------
  // The section an item is drawn in: a screen part's or a card's own
  // section, the one named in the link, or the item's section.
  function sectionFor(id, preferred) {
    var it = item(id);
    if (!it) return null;
    if (it.type === "section") return it.section;
    var pref = preferred && section(preferred);
    if (pref && (pref.entries.indexOf(id) >= 0 || pref.features.indexOf(id) >= 0 || pref.single === id)) return pref.id;
    return it.section;
  }

  function show(secId, id, opts) {
    var sec = section(secId);
    if (!sec || !item(id)) { sec = section("dashboard"); id = sectionItem(sec); }
    current = { section: sec.id, item: id };
    renderMock(sec);
    renderShot(mediaFor(id, sec), itemLabel(id));
    renderDoc(id, sec);
    markNav();
    requestAnimationFrame(function () { focusMock(id); });
    if (!opts || !opts.keepScroll) {
      if (window.innerWidth <= 980) els.mock.parentNode.scrollIntoView({ block: "start" });
    }
  }

  function go(secId, id) {
    var hash = "#" + (secId && sectionFor(id, secId) !== item(id).section ? secId + "/" : "") + id;
    if (location.hash !== hash) history.pushState(null, "", hash);
    closeMenu();
    show(sectionFor(id, secId), id);
  }

  function fromHash(initial) {
    var opts = initial === true ? { keepScroll: true } : null;
    var raw = decodeURIComponent(location.hash.replace(/^#/, ""));
    var parts = raw.split("/");
    var id = parts.pop(), pref = parts.pop();
    if (id && section(id) && !item(id)) id = sectionItem(section(id));     // #backup
    if (!id || !item(id)) return show("dashboard", "sec-dashboard", opts);
    show(sectionFor(id, pref), id, opts);
  }

  function closeMenu() {
    els.nav.classList.remove("kp-nav-open");
    els.menu.setAttribute("aria-expanded", "false");
  }

  // ------------------------------------------------------------------
  // Start
  // ------------------------------------------------------------------
  function start(json) {
    data = json;
    buildLangSelect();
    lang = initialLang();
    setLanguage(lang, { store: false });
    fromHash(true);

    els.lang.addEventListener("change", function () { setLanguage(els.lang.value); });
    els.search.addEventListener("input", applySearch);
    els.tabMock.addEventListener("click", function () { selectTab("mock"); });
    els.tabShot.addEventListener("click", function () { if (!els.tabShot.disabled) selectTab("shot"); });
    els.menu.addEventListener("click", function () {
      var open = els.nav.classList.toggle("kp-nav-open");
      els.menu.setAttribute("aria-expanded", open ? "true" : "false");
    });
    window.addEventListener("popstate", fromHash);
    window.addEventListener("hashchange", fromHash);
    els.doc.addEventListener("click", function (ev) {
      var a = ev.target.closest("[data-goto]");
      if (!a) return;
      ev.preventDefault();
      go(null, a.getAttribute("data-goto"));
    });
    // The website changed its language in another tab, or an embedding page asks.
    window.addEventListener("storage", function (ev) {
      if (ev.key === STORE_KEY && ev.newValue && langFromCode(ev.newValue) !== lang) setLanguage(ev.newValue, { store: false });
    });
    window.addEventListener("message", function (ev) {
      var d = ev.data;
      if (d && d.type === "koha-nexus:lang" && d.lang) setLanguage(d.lang);
    });
    // Panel shortcut keys jump to their section, as in the real panel.
    document.addEventListener("keydown", function (ev) {
      if (ev.ctrlKey || ev.metaKey || ev.altKey || /INPUT|SELECT|TEXTAREA/.test(ev.target.tagName)) return;
      if (ev.key === "/") { ev.preventDefault(); els.search.focus(); return; }
      for (var i = 0; i < data.sections.length; i++) {
        var s = data.sections[i];
        if (s.key && s.key === ev.key) { go(s.id, sectionItem(s)); return; }
      }
    });
  }

  window.KohaPreview = {
    setLanguage: function (code) { if (data) setLanguage(code); },
    open: function (id) { if (data && item(id)) go(null, id); }
  };

  fetch(SRC, { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(start)
    .catch(function (err) {
      els.doc.innerHTML = "";
      els.doc.appendChild(h("p", { class: "kp-error", text: UI.load_error + " (" + SRC + ": " + err.message + ")" }));
    });
})();
