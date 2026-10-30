/* Standalone training only. Never calls Koha APIs or executes report SQL. */
(function () {
  "use strict";
  const KEY = "koha-nexus-staff-learning-v1";
  class Exercise {
    constructor(lesson) { this.lesson = lesson; this.stage = 0; this.values = {}; }
    next(values = {}) {
      if (this.stage === 1) {
        for (const field of this.lesson.fields) {
          if (String(values[field.label] || "").trim() !== field.example) {
            return {ok: false, message: "Use the fictional example for “" + field.label + "”: " + field.example};
          }
        }
        this.values = {...values};
      }
      this.stage = Math.min(3, this.stage + 1);
      return {ok: true, message: this.stage === 3 ? this.lesson.result : ""};
    }
    back() { this.stage = Math.max(0, this.stage - 1); }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {Exercise};
  if (typeof document === "undefined") return;
  const $ = id => document.getElementById(id);
  const make = (tag, text) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; return el; };
  let lessons = [], exercise, completed = new Set();
  let modules = [];
  try { const saved = JSON.parse(localStorage.getItem(KEY)); if (Array.isArray(saved)) completed = new Set(saved.filter(x => typeof x === "string")); } catch (e) {}
  function progress() { $("progress").textContent = lessons.filter(l => completed.has(l.id)).length + " / " + lessons.length + " guides completed"; }
  function nav() {
    const query = $("guide-search").value.toLowerCase().trim();
    const matches = lessons.filter(l => [l.title,l.section,l.overview,l.id].join(" ").toLowerCase().includes(query));
    $("guide-nav").replaceChildren();
    for (const lesson of matches) {
      const a = make("a", (completed.has(lesson.id) ? "✓ " : "") + lesson.title);
      a.href = "#" + lesson.id;
      if (exercise && lesson.id === exercise.lesson.id) a.setAttribute("aria-current", "page");
      a.addEventListener("click", () => { if (exercise && exercise.lesson.id === lesson.id) select(lesson.id); });
      $("guide-nav").append(a);
    }
    if (!matches.length) $("guide-nav").append(make("p", "No matching guides. Try another task."));
    progress();
  }
  function renderPractice() {
    const stage = exercise.stage;
    $("practice-instruction").textContent = ["Open this training task to begin. No staff login is required.", "Enter the fictional examples below. These simplified fields are practice controls, not a complete Koha form.", "Review the example before finishing. This does not save anything in Koha.", "Exercise complete. You can repeat it or choose another guide."][stage];
    document.querySelectorAll("#practice-stages li").forEach((el,i) => { el.removeAttribute("aria-current"); if (i === stage) el.setAttribute("aria-current","step"); });
    $("practice-fields").hidden = stage !== 1;
    $("review").hidden = stage < 2;
    $("review").replaceChildren();
    if (stage >= 2) {
      const dl = make("dl");
      for (const field of exercise.lesson.fields) { dl.append(make("dt",field.label),make("dd",exercise.values[field.label])); }
      $("review").append(dl);
    }
    $("practice-back").disabled = stage === 0 || stage === 3;
    $("fill-example").hidden = stage !== 1;
    $("practice-next").hidden = stage === 3;
    $("practice-next").textContent = ["Open training task","Review example","Finish exercise"][stage] || "Complete";
    $("practice-message").textContent = stage === 3 ? exercise.lesson.result : "";
  }
  function view(guides) {
    $("task-view").hidden = !guides;
    $("staff-overview").hidden = guides;
    $("show-staff").setAttribute("aria-pressed",String(!guides));
    $("show-guides").setAttribute("aria-pressed",String(guides));
  }
  function explain(module) {
    $("module-title").textContent = module.title;
    $("module-description").textContent = module.description;
    $("module-tips-title").hidden = false;
    $("module-tips").replaceChildren(...module.tips.map(t => make("li",t)));
    $("module-guides").replaceChildren();
    for (const id of module.guides) {
      const lesson = lessons.find(l => l.id === id);
      if (!lesson) continue;
      const a = make("a", "Read guide: " + lesson.title);
      a.href = "#" + id;
      a.addEventListener("click", () => { if (location.hash === a.hash) { view(true); select(id); } });
      $("module-guides").append(a);
    }
    $("module-coverage").textContent = module.guides.length ? "The guides explain selected workflows. This screen does not connect to your library." : "Module overview only. Detailed interactive screens for this module are not included yet.";
    document.querySelectorAll("#staff-options button").forEach(b => b.setAttribute("aria-pressed",String(b.dataset.module === module.id)));
    $("module-explanation").focus();
    if (window.matchMedia("(max-width: 800px)").matches) $("module-explanation").scrollIntoView({block:"start"});
  }
  function staffHome() {
    $("staff-options").replaceChildren();
    const columns = [make("div"),make("div")];
    columns.forEach(c => { c.className = "koha-option-column"; $("staff-options").append(c); });
    for (const [index,module] of modules.entries()) {
      const button = make("button"); button.type = "button"; button.dataset.module = module.id;
      button.setAttribute("aria-pressed","false");
      const icon = make("span",module.icon); icon.setAttribute("aria-hidden","true");
      button.append(icon,make("span",module.title));
      button.addEventListener("click", () => explain(module));
      columns[index < 9 ? 0 : 1].append(button);
    }
    $("staff-load-status").hidden = true;
  }
  $("show-staff").addEventListener("click", () => { history.replaceState(null,"",location.pathname + location.search); view(false); });
  $("show-guides").addEventListener("click", () => view(true));
  function select(id) {
    const lesson = lessons.find(l => l.id === id) || lessons[0];
    exercise = new Exercise(lesson);
    $("lesson-section").textContent = lesson.section;
    $("lesson-title").textContent = lesson.title;
    $("overview").textContent = lesson.overview;
    $("warning").textContent = lesson.warning;
    $("screen-path").textContent = lesson.where;
    $("source-reference").textContent = "Based on the supplied Koha staff template: " + lesson.source.path;
    $("instructions").replaceChildren(...lesson.steps.map(s => make("li",s)));
    $("practice-fields").replaceChildren();
    lesson.fields.forEach((field,i) => {
      const label = make("label",field.label); label.htmlFor = "field-" + i;
      const input = make("input"); input.id = label.htmlFor; input.name = field.label; input.autocomplete = "off"; input.maxLength = 200; input.placeholder = field.example;
      input.setAttribute("aria-describedby","hint-" + i);
      const hint = make("small",field.hint + " Example: " + field.example); hint.id = "hint-" + i;
      $("practice-fields").append(label,input,hint);
    });
    const index = lessons.indexOf(lesson);
    $("previous-lesson").disabled = index === 0;
    $("next-lesson").disabled = index === lessons.length - 1;
    $("lesson").hidden = false;
    nav(); renderPractice();
  }
  $("practice-form").addEventListener("submit", event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    const outcome = exercise.next(values);
    if (!outcome.ok) { $("practice-message").textContent = outcome.message; return; }
    if (exercise.stage === 3) {
      completed.add(exercise.lesson.id);
      try { localStorage.setItem(KEY,JSON.stringify([...completed])); } catch (e) {}
      nav();
    }
    renderPractice();
    if (exercise.stage === 1) $("practice-fields").querySelector("input").focus();
    else if (exercise.stage === 2) $("practice-next").focus();
  });
  $("fill-example").addEventListener("click", () => exercise.lesson.fields.forEach((f,i) => { $("field-" + i).value = f.example; }));
  $("practice-back").addEventListener("click", () => { exercise.back(); renderPractice(); });
  $("practice-reset").addEventListener("click", () => select(exercise.lesson.id));
  $("guide-search").addEventListener("input",nav);
  $("clear-progress").addEventListener("click", () => { completed.clear(); try { localStorage.removeItem(KEY); } catch (e) {} nav(); });
  for (const [id,delta] of [["previous-lesson",-1],["next-lesson",1]]) $(id).addEventListener("click", () => { const l = lessons[lessons.indexOf(exercise.lesson) + delta]; if (l) location.hash = l.id; });
  window.addEventListener("hashchange", () => { if (lessons.length) { view(Boolean(location.hash)); select(location.hash.slice(1)); } });
  const load = path => fetch(path).then(r => { if (!r.ok) throw Error("HTTP " + r.status); return r.json(); });
  Promise.all([load("lessons.json"),load("staff-home.json")]).then(([data, home]) => {
    if (!Array.isArray(data.lessons) || !data.lessons.length) throw Error("No lessons");
    lessons = data.lessons;
    modules = home.modules;
    staffHome();
    $("load-status").hidden = true;
    select(location.hash.slice(1));
    view(Boolean(location.hash));
  }).catch(() => { $("staff-load-status").hidden = false; $("staff-load-status").textContent = "The staff screen could not be loaded. Please reload this page."; $("load-status").textContent = "The guides could not be loaded. Reload this page over HTTP/HTTPS, or use the official Koha manual linked below."; });
})();
