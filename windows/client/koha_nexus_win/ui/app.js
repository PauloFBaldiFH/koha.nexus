// The status window: draws what Api.status() (viewmodel.build) returns.
// Texts come translated from Python and are set with textContent only.
"use strict";

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function buttons(box, items, primaryFirst) {
  box.replaceChildren();
  items.forEach((it, i) => {
    const b = el("button", primaryFirst && i === 0 ? "primary" : "", it.text);
    b.disabled = !it.enabled;
    b.addEventListener("click", () => window.pywebview.api.act(it.key).then(refreshSoon));
    box.appendChild(b);
  });
}

function draw(vm) {
  const banner = document.getElementById("banner");
  if (vm.error) {
    banner.className = "card banner fault";
    document.getElementById("banner-title").textContent = vm.error;
    return;
  }
  banner.className = "card banner " + vm.banner.level;
  document.getElementById("banner-title").textContent = vm.banner.text;
  document.getElementById("banner-sub").textContent = [vm.checked, vm.backup].filter(Boolean).join("  ·  ");
  document.getElementById("cap-quick").textContent = vm.labels.quick;
  document.getElementById("cap-components").textContent = vm.labels.components;
  document.getElementById("cap-actions").textContent = vm.labels.actions;
  buttons(document.getElementById("links"), vm.links, true);
  buttons(document.getElementById("actions"), vm.actions, false);
  const list = document.getElementById("components");
  list.replaceChildren();
  vm.components.forEach((c) => {
    const li = el("li", c.broken ? "broken" : "");
    li.appendChild(el("span", "name", c.name));
    li.appendChild(el("span", "state " + c.state, c.text));
    list.appendChild(li);
  });
}

let timer = null;
function refresh() {
  window.pywebview.api.status().then(draw);
}
function refreshSoon() {
  setTimeout(refresh, 5000);
}

window.addEventListener("pywebviewready", () => {
  refresh();
  window.pywebview.api.refresh_every().then((s) => {
    clearInterval(timer);
    timer = setInterval(refresh, s * 1000);
  });
});
