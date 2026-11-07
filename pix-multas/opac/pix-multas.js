/* Koha.Nexus - Pagamento de multas via Pix (OpacUserJS).
 * Cole este bloco em: Administração > Preferências do sistema > OpacUserJS.
 * Desligado por padrão: mude enabled para true depois de preencher os dados.
 * Sem servidor: o Fluxo 1 (Pix estático) mostra a chave e copia; o Fluxo 2
 * (dinâmico) só funciona se o serviço nexus-pix estiver instalado e o Apache
 * encaminhar /nexus-pix/ para ele. */
(function () {
  "use strict";
  var CONFIG = {
    enabled: false,
    pixKey: "troque-pela-chave@suabiblioteca.gov.br",   // chave Pix institucional (CNPJ, e-mail, telefone ou aleatória)
    recipientName: "Nome da Biblioteca",                 // beneficiário que aparece no app do banco
    instructions: [
      "Abra o app do seu banco e escolha Pix > Pix Copia e Cola (ou Pagar com chave).",
      "Cole a chave acima ou o código copiado e confirme o valor da multa.",
      "Envie o comprovante ao balcão da biblioteca se a multa não sumir em 1 dia útil."
    ],
    dynamicEndpoint: "/nexus-pix/charges"               // "" desliga o Fluxo 2
  };
  var STYLE_ID = "nexus-pix-style";

  function el(tag, props, children) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === "className") { node.className = props[k]; } else { node.setAttribute(k, props[k]); }
    });
    (children || []).forEach(function (c) {
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) { return; }
    var css = ".nexus-pix{border:1px solid #c9d3dd;border-radius:8px;padding:16px;margin:12px 0;background:#fff;color:#1d2733}" +
      ".nexus-pix h3{margin:0 0 8px;font-size:1.1em}" +
      ".nexus-pix input[type=text]{width:100%;max-width:420px;padding:6px;font:inherit}" +
      ".nexus-pix button{margin:6px 6px 0 0;padding:8px 14px;border:0;border-radius:6px;background:#1f6f5c;color:#fff;cursor:pointer;font:inherit}" +
      ".nexus-pix button[disabled]{opacity:.6;cursor:wait}" +
      ".nexus-pix .np-msg{margin-top:8px;font-size:.95em}" +
      ".nexus-pix img{max-width:220px;display:block;margin-top:8px}" +
      "@media (prefers-color-scheme: dark){.nexus-pix{background:#1d2733;color:#e6edf3;border-color:#3c4a5a}}";
    document.head.appendChild(el("style", { id: STYLE_ID }, [css]));
  }

  function copyText(text, msgNode) {
    function fallback() {
      var tmp = el("textarea", {}, [text]);
      tmp.style.position = "fixed"; tmp.style.opacity = "0";
      document.body.appendChild(tmp); tmp.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      document.body.removeChild(tmp);
      msgNode.textContent = ok ? "Copiado." : "Não foi possível copiar. Selecione o texto e copie.";
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        msgNode.textContent = "Copiado.";
      }, fallback);
    } else {
      fallback();
    }
  }

  var DYNAMIC_ERRORS = {
    login_required: "Entre na sua conta do OPAC para gerar o Pix.",
    nothing_owed: "Você não tem multas em aberto.",
    amount_over_limit: "Valor acima do limite para Pix online. Procure o balcão da biblioteca.",
    koha_unavailable: "O sistema da biblioteca está indisponível. Tente mais tarde.",
    pix_unavailable: "O serviço de Pix está indisponível. Tente mais tarde."
  };

  function dynamicBlock(msg) {
    var button = el("button", { type: "button" }, ["Gerar Pix com valor atual"]);
    var out = el("div", { className: "np-result" });
    button.addEventListener("click", function () {
      button.disabled = true; msg.textContent = "Gerando cobrança...";
      out.textContent = "";
      fetch(CONFIG.dynamicEndpoint, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: "{}"
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) { return { ok: r.ok, data: data }; });
      }).then(function (res) {
        button.disabled = false;
        if (!res.ok) { msg.textContent = DYNAMIC_ERRORS[res.data.error] || "Não foi possível gerar o Pix."; return; }
        msg.textContent = "Valor: R$ " + res.data.amount + ". Pague em até " + Math.round(res.data.expires_in / 60) + " minutos.";
        var field = el("input", { type: "text", readonly: "readonly", value: res.data.copia_cola });
        out.appendChild(field);
        out.appendChild(el("button", { type: "button" }, ["Copiar código"])).addEventListener("click", function () {
          copyText(field.value, msg);
        });
        if (res.data.qr_base64) {
          out.appendChild(el("img", { alt: "QR Code Pix", src: "data:image/png;base64," + res.data.qr_base64 }));
        }
        msg.appendChild(el("div", {}, ["Depois de pagar, recarregue esta página para ver a multa quitada."]));
      }).catch(function () {
        button.disabled = false; msg.textContent = "Falha de conexão. Tente novamente.";
      });
    });
    return el("div", {}, [el("p", {}, ["Ou gere um código Pix com o valor exato das suas multas agora:"]), button, out]);
  }

  function staticBlock() {
    var msg = el("div", { className: "np-msg", "aria-live": "polite" });
    var field = el("input", { type: "text", readonly: "readonly", value: CONFIG.pixKey, "aria-label": "Chave Pix da biblioteca" });
    var copy = el("button", { type: "button" }, ["Copiar chave Pix"]);
    copy.addEventListener("click", function () { copyText(CONFIG.pixKey, msg); });
    var steps = el("ol", {}, CONFIG.instructions.map(function (t) { return el("li", {}, [t]); }));
    var children = [
      el("h3", {}, ["Pagar multas com Pix"]),
      el("p", {}, ["Favorecido: " + CONFIG.recipientName]),
      field, copy, steps
    ];
    if (CONFIG.dynamicEndpoint) { children.push(dynamicBlock(msg)); }
    children.push(msg);
    return el("section", { className: "nexus-pix", id: "nexus-pix-multas" }, children);
  }

  function onFinesTab() {
    return new URLSearchParams(window.location.search).get("tab") === "fines";
  }

  function run() {
    if (!CONFIG.enabled || !onFinesTab() || document.getElementById("nexus-pix-multas")) { return; }
    injectStyle();
    var target = document.querySelector("#main") || document.querySelector(".maincontent") || document.body;
    target.insertBefore(staticBlock(), target.firstChild);
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", run); } else { run(); }
})();
