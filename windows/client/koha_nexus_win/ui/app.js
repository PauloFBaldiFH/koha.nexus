// The Control Center page: a sidebar built from the panel's menu
// (Api.sections), the status dashboard (Api.status) and a job drawer that
// draws the events of a task run (nexus.onEvents, fed by engine.EventPump).
// Every text comes from Python or from Debian and is set with textContent only.
"use strict";

const api = () => window.pywebview.api;
const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}

const state = {
  ready: false,
  sections: [],
  inline: new Set(),
  labels: {},
  current: "dashboard",
  job: null, // {run, ended, rc, events, logOpen}
  ended: false,
  rc: null,
  events: 0,
};
const L = (key) => state.labels[key] || key;

// --- dashboard ----------------------------------------------------------
function buttons(box, items, primaryFirst) {
  box.replaceChildren();
  items.forEach((it, i) => {
    const b = el("button", primaryFirst && i === 0 ? "primary" : "", it.text);
    b.type = "button";
    b.disabled = !it.enabled;
    b.addEventListener("click", () => api().act(it.key).then(refreshSoon));
    box.appendChild(b);
  });
}

function draw(vm) {
  const banner = $("banner");
  const head = $("head-state");
  if (vm.error) {
    banner.className = "card banner fault";
    head.className = "head-state fault";
    $("banner-title").textContent = vm.error;
    $("head-state-text").textContent = vm.error;
    return;
  }
  banner.className = "card banner " + vm.banner.level;
  head.className = "head-state " + vm.banner.level;
  $("banner-title").textContent = vm.banner.text;
  $("head-state-text").textContent = vm.banner.text;
  $("banner-sub").textContent = [vm.checked, vm.backup].filter(Boolean).join("  ·  ");
  $("cap-quick").textContent = vm.labels.quick;
  $("cap-components").textContent = vm.labels.components;
  $("cap-actions").textContent = vm.labels.actions;
  buttons($("links"), vm.links, true);
  buttons($("head-links"), vm.links, false);
  buttons($("actions"), vm.actions, false);
  const list = $("components");
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
  api().status().then(draw);
}
function refreshSoon() {
  setTimeout(refresh, 5000);
}

// --- sidebar and sections ---------------------------------------------
function navButton(id, icon, label) {
  const li = el("li");
  const b = el("button");
  b.type = "button";
  b.dataset.section = id;
  b.appendChild(el("span", "icon", icon || "•"));
  b.appendChild(el("span", "label", label));
  b.title = label;
  b.addEventListener("click", () => show(id));
  li.appendChild(b);
  return li;
}

function buildSidebar(dashboardLabel) {
  const nav = $("nav");
  nav.replaceChildren(navButton("dashboard", "🏠", dashboardLabel));
  state.sections.filter((s) => s.sidebar).forEach((s) => nav.appendChild(navButton(s.id, s.icon, s.label)));
  const foot = $("terminal-panel");
  foot.textContent = "⌨ " + L("terminal_panel");
  foot.title = L("terminal_hint");
  foot.onclick = () => api().terminal_panel();
}

function show(id) {
  state.current = id;
  document.querySelectorAll("#nav button").forEach((b) => {
    b.classList.toggle("current", b.dataset.section === id);
  });
  const dash = id === "dashboard";
  $("view-dashboard").hidden = !dash;
  $("view-section").hidden = dash;
  if (!dash) drawSection(id);
}

function sectionById(id) {
  return state.sections.find((s) => s.id === id);
}

function drawSection(id) {
  const s = sectionById(id);
  const cards = $("cards");
  cards.replaceChildren();
  if (!s) return;
  $("section-title").textContent = [s.icon, s.title || s.label].filter(Boolean).join(" ");
  const entries = s.entries || [];
  if (!entries.length) {
    const box = el("div", "card");
    box.appendChild(el("p", "muted", L("not_ported")));
    const b = el("button", "primary", L("open_terminal"));
    b.type = "button";
    b.addEventListener("click", () => api().terminal_panel());
    box.appendChild(b);
    cards.appendChild(box);
    return;
  }
  entries.forEach((e) => {
    const card = el("button", "entry");
    card.type = "button";
    const top = el("div", "name");
    if (e.icon) top.appendChild(el("span", "icon", e.icon + " "));
    top.appendChild(document.createTextNode(e.label));
    card.appendChild(top);
    if (e.description) card.appendChild(el("div", "muted small", e.description));
    const view = e.kind === "view" ? sectionById(e.action) : null;
    if (!view) {
      const here = state.inline.has(e.action);
      card.appendChild(el("div", here ? "how here" : "how", L(here ? "runs_here" : "opens_terminal")));
    }
    card.addEventListener("click", () => openEntry(e, view));
    cards.appendChild(card);
  });
}

function openEntry(entry, view) {
  if (view) {
    show(view.id);
    return;
  }
  api().open_entry(entry.action).then((r) => {
    if (!r || !r.ok) {
      if (r && r.busy) message("error", "", L("busy"));
      return;
    }
    if (r.how !== "inline") return;
    // A task that ended at once may already have drawn its events.
    if (state.job && state.job.run === r.id) $("job-title").textContent = entry.label;
    else openJob(r.id, entry.label);
  });
}

// --- job drawer ---------------------------------------------------------
function openJob(run, title) {
  state.job = { run: run, ended: false, logOpen: false };
  state.ended = false;
  state.rc = null;
  $("job").hidden = false;
  $("job-title").textContent = title || "";
  $("job-stage").textContent = L("running");
  $("job-bar").className = "bar indeterminate";
  $("job-bar").firstElementChild.style.width = "";
  $("job-steps").replaceChildren();
  $("job-messages").replaceChildren();
  $("job-results").replaceChildren();
  $("job-log").textContent = "";
  $("job-log").hidden = true;
  $("job-log-toggle").textContent = L("show_log");
  $("job-cancel").textContent = L("cancel");
  $("job-cancel").hidden = false;
  $("job-close").textContent = L("close");
  $("job-close").hidden = true;
}

function logLine(text) {
  const pre = $("job-log");
  pre.textContent += text + "\n";
  pre.scrollTop = pre.scrollHeight;
}

function message(level, title, text) {
  const box = el("div", "message " + (level === "error" ? "error" : level === "ok" || level === "info" ? "ok" : ""));
  if (title) box.appendChild(el("strong", "", title + "\n"));
  box.appendChild(document.createTextNode(text || ""));
  ($("job").hidden ? $("cards") : $("job-messages")).appendChild(box);
}

function setProgress(fraction) {
  const bar = $("job-bar");
  if (fraction === null || fraction === undefined) {
    bar.className = "bar indeterminate";
    bar.firstElementChild.style.width = "";
  } else {
    bar.className = "bar";
    bar.firstElementChild.style.width = Math.round(fraction * 100) + "%";
  }
}

function stepItem(label) {
  const items = $("job-steps").children;
  for (let i = items.length - 1; i >= 0; i--) {
    if (items[i].dataset.label === label && !items[i].className) return items[i];
  }
  return null;
}

function resultRow(key, value) {
  let table = $("job-results").querySelector("table");
  if (!table) {
    $("job-results").appendChild(el("div", "caption", L("results")));
    table = el("table", "results");
    $("job-results").appendChild(table);
  }
  const tr = el("tr");
  let cells = [key, value];
  if (key === "row") {
    cells = value.split("\t");
    while (cells.length < 3) cells.unshift("");
  }
  cells.forEach((c, i) => tr.appendChild(el("td", i === 0 ? "group" : "", c)));
  table.appendChild(tr);
}

function handle(ev) {
  if (!state.job || state.job.run !== ev.run) openJob(ev.run, "");
  state.events += 1;
  switch (ev.kind) {
    case "title":
      $("job-title").textContent = ev.text;
      break;
    case "stage":
      $("job-stage").textContent = ev.note || ev.stage;
      setProgress(ev.progress);
      break;
    case "step": {
      const li = el("li", "", ev.label);
      li.dataset.label = ev.label;
      $("job-steps").appendChild(li);
      $("job-stage").textContent = ev.label;
      setProgress(ev.progress);
      break;
    }
    case "done": {
      const li = stepItem(ev.label) || $("job-steps").appendChild(el("li", "", ev.label));
      li.className = ev.rc === 0 ? "ok" : "bad";
      setProgress(ev.progress);
      break;
    }
    case "note":
    case "log":
      logLine(ev.text);
      break;
    case "msg":
      message(ev.level, ev.title, ev.text);
      break;
    case "preview":
      $("job-messages").appendChild(el("pre", "preview", [ev.title, ev.text].filter(Boolean).join("\n")));
      break;
    case "result":
      resultRow(ev.key, ev.value);
      break;
    case "cancel":
      $("job-cancel").hidden = !ev.on;
      break;
    case "end":
      endJob(ev);
      break;
    default:
      if (ev.waits) ask(ev);
      else logLine(JSON.stringify(ev));
  }
}

function endJob(ev) {
  state.job.ended = true;
  state.ended = true;
  state.rc = ev.rc;
  const word = ev.cancelled ? "cancelled" : ev.rc === 0 ? "finished" : "failed";
  $("job-stage").textContent = L(word);
  $("job-bar").className = "bar " + (ev.rc === 0 ? "done" : "fail");
  $("job-bar").firstElementChild.style.width = "";
  $("job-cancel").hidden = true;
  $("job-close").hidden = false;
  closeDialog();
}

// --- dialogs: one question of the routine at a time ------------------
const questions = [];
let asking = null;

function ask(ev) {
  questions.push(ev);
  if (!asking) nextQuestion();
}

function closeDialog() {
  questions.length = 0;
  asking = null;
  $("dialog-veil").hidden = true;
}

function reply(value) {
  const ev = asking;
  asking = null;
  $("dialog-veil").hidden = true;
  if (ev) api().answer(ev.run, value);
  if (questions.length) nextQuestion();
}

function dialogButton(text, primary, onClick) {
  const b = el("button", primary ? "primary" : "", text);
  b.type = primary ? "submit" : "button";
  if (!primary) b.addEventListener("click", onClick);
  return b;
}

function nextQuestion() {
  const ev = questions.shift();
  if (!ev) return;
  asking = ev;
  const body = $("dialog-body");
  const btns = $("dialog-buttons");
  body.replaceChildren();
  btns.replaceChildren();
  $("dialog-title").textContent = ev.title || $("job-title").textContent;
  $("dialog-text").textContent = ev.text || ev.note || "";
  let submit = () => reply(true);
  let cancel = () => reply(null);
  switch (ev.kind) {
    case "say":
    case "view":
      if (ev.kind === "view") {
        $("dialog-text").textContent = "";
        body.appendChild(el("pre", "preview", ev.text));
      }
      btns.appendChild(dialogButton(L("ok"), true));
      cancel = null;
      break;
    case "ask":
      btns.appendChild(dialogButton(L("no"), false, () => reply(false)));
      btns.appendChild(dialogButton(L("yes"), true));
      cancel = () => reply(false);
      break;
    case "choose":
      ev.options.forEach((o) => {
        const label = el("label");
        const r = el("input");
        r.type = "radio";
        r.name = "choice";
        r.value = o.key;
        r.checked = o.key === ev.default;
        label.appendChild(r);
        label.appendChild(document.createTextNode(o.label));
        body.appendChild(label);
      });
      submit = () => {
        const c = body.querySelector("input:checked");
        reply(c ? c.value : null);
      };
      break;
    case "check":
      ev.options.forEach((o) => {
        const label = el("label");
        const c = el("input");
        c.type = "checkbox";
        c.value = o.key;
        c.checked = o.on;
        label.appendChild(c);
        label.appendChild(document.createTextNode(o.label));
        body.appendChild(label);
      });
      submit = () => reply(Array.from(body.querySelectorAll("input:checked")).map((c) => c.value));
      break;
    case "input":
    case "file": {
      const field = el("input");
      field.type = ev.password ? "password" : "text";
      field.value = ev.kind === "file" ? ev.start || "" : ev.default || "";
      if (ev.kind === "file") body.appendChild(el("div", "muted small", L("path")));
      body.appendChild(field);
      setTimeout(() => field.focus(), 0);
      submit = () => reply(field.value.trim() || (ev.kind === "file" ? null : ""));
      break;
    }
    case "edit":
      body.appendChild(el("p", "muted", ev.path));
      body.appendChild(el("p", "", L("edit_later")));
      btns.appendChild(dialogButton(L("ok"), true));
      submit = () => reply(false);
      cancel = null;
      break;
    default:
      submit = () => reply(true);
  }
  if (["choose", "check", "input", "file"].includes(ev.kind)) {
    btns.appendChild(dialogButton(L("cancel"), false, cancel));
    btns.appendChild(dialogButton(L("ok"), true));
  }
  $("dialog").onsubmit = (e) => {
    e.preventDefault();
    submit();
  };
  $("dialog").onkeydown = (e) => {
    if (e.key === "Escape" && cancel) {
      e.preventDefault();
      cancel();
    }
  };
  $("dialog-veil").hidden = false;
}

// --- wiring -------------------------------------------------------------
$("job-log-toggle").addEventListener("click", () => {
  const pre = $("job-log");
  pre.hidden = !pre.hidden;
  $("job-log-toggle").textContent = L(pre.hidden ? "show_log" : "hide_log");
});
$("job-cancel").addEventListener("click", () => {
  if (state.job && !state.job.ended) api().cancel(state.job.run);
});
$("job-close").addEventListener("click", () => {
  $("job").hidden = true;
  state.job = null;
});

window.nexus = {
  onEvents(batch) {
    (batch || []).forEach((ev) => {
      try {
        handle(ev);
      } catch (e) {
        console.error(e);
      }
    });
  },
  selfTest() {
    return {
      ready: state.ready,
      sidebar: document.querySelectorAll("#nav button").length,
      sections: state.sections.length,
      ended: state.ended,
      rc: state.rc,
      events: state.events,
    };
  },
};

window.addEventListener("pywebviewready", () => {
  refresh();
  api().refresh_every().then((s) => {
    clearInterval(timer);
    timer = setInterval(refresh, s * 1000);
  });
  api().sections().then((data) => {
    state.sections = data.sections || [];
    state.inline = new Set(data.inline || []);
    state.labels = data.labels || {};
    buildSidebar(L("dashboard"));
    show("dashboard");
    state.ready = true;
  });
});
