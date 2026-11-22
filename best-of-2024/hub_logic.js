const TAGS = __TAGS__;
const SEP = " › ";
const $ = id => document.getElementById(id);
function syncThemeToggle() {
  const dark = document.documentElement.dataset.theme === "dark";
  $("theme-toggle").textContent = dark ? "Light mode" : "Dark mode";
  $("theme-toggle").setAttribute("aria-label", "Dark mode");
  $("theme-toggle").setAttribute("aria-pressed", String(dark));
}
$("theme-toggle").addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("best-2024-theme", theme); } catch (e) {}
  syncThemeToggle();
});
syncThemeToggle();
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pathOf = i => [i.line, ...i.topic];
const keyOf = parts => parts.join(SEP);
const linkLabel = i => i.href.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
const normalizeSearch = s => String(s).normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
const SEARCH_ALIASES = {
  nyt: ["new york times"], rs: ["rolling stone"], tv: ["television"], pw: ["publishers weekly"],
  bbc: ["bbc culture"], goty: ["game of the year", "game awards"], lp: ["lonely planet"],
};
const searchDocuments = new WeakMap();
function searchDocument(i) {
  if (!searchDocuments.has(i)) {
    const text = normalizeSearch([i.title, i.desc, ...pathOf(i), i.href, ...i.tags].join(" "));
    searchDocuments.set(i, { text, words: [...new Set(text.split(" "))] });
  }
  return searchDocuments.get(i);
}
// One insertion, deletion, substitution or adjacent transposition; short words stay exact.
function nearWord(a, b) {
  if (Math.abs(a.length - b.length) > 1) return false;
  let n = 0;
  while (n < Math.min(a.length, b.length) && a[n] === b[n]) n++;
  if (n === Math.min(a.length, b.length)) return true;
  if (a.length === b.length) return a.slice(n + 1) === b.slice(n + 1)
    || (a[n] === b[n + 1] && a[n + 1] === b[n] && a.slice(n + 2) === b.slice(n + 2));
  return a.length > b.length ? a.slice(n + 1) === b.slice(n) : a.slice(n) === b.slice(n + 1);
}
function searchMatches(i, query) {
  const terms = normalizeSearch(query).split(" ").filter(Boolean);
  const doc = searchDocument(i);
  return terms.every(term => [term, ...(SEARCH_ALIASES[term] || [])].some(word =>
    doc.text.includes(word) || (word.length >= 4 && !word.includes(" ") && doc.words.some(candidate => nearWord(word, candidate)))));
}
const removeIcon = '<svg aria-hidden="true" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m4 4 8 8m0-8-8 8"/></svg>';

const state = { sel: [], q: "", kind: "", sort: "topic", open: new Set(), tags: new Set() };
const hasFilters = () => Boolean(state.sel.length || state.q || state.kind || state.tags.size);

function buildTree(items) {
  const root = { name: "", kids: new Map(), n: 0 };
  for (const i of items) {
    let node = root; root.n++;
    for (const part of pathOf(i)) {
      if (!node.kids.has(part)) node.kids.set(part, { name: part, kids: new Map(), n: 0 });
      node = node.kids.get(part); node.n++;
    }
  }
  return root;
}
function matches(i, skipTags) {
  if (state.kind && i.kind !== state.kind) return false;
  if (!skipTags && state.tags.size && !i.tags.some(t => state.tags.has(t))) return false;
  if (!state.q) return true;
  return searchMatches(i, state.q);
}
const inSel = i => state.sel.every((p, n) => pathOf(i)[n] === p);

function renderTree() {
  const tree = buildTree(ITEMS.filter(i => matches(i)));
  const selKey = keyOf(state.sel);
  const node = (n, parts, depth) => {
    const key = keyOf(parts), hasSubs = n.kids.size > 0, isOpen = state.open.has(key);
    const cls = [depth ? "ix-sub" : "ix-item", hasSubs ? "has-subs" : "", isOpen ? "open" : "", key === selKey ? "on" : ""].join(" ");
    let html = `<button class="${cls}" data-key="${esc(key)}"><span>${esc(n.name)}</span><span class="ix-n">${n.n}</span></button>`;
    if (hasSubs) html += `<div class="ix-subs${isOpen ? " open" : ""}">${[...n.kids.values()].map(k => node(k, [...parts, k.name], depth + 1)).join("")}</div>`;
    return html;
  };
  $("tree").innerHTML =
    `<button class="ix-all${state.sel.length ? "" : " on"}" data-key="" title="Show every list and clear all filters"><span>All lists</span><span class="ix-n">${tree.n}</span></button>` +
    [...tree.kids.values()].sort((a, b) => a.name.localeCompare(b.name)).map(n => node(n, [n.name], 0)).join("");
}
function renderChips() {
  const base = ITEMS.filter(i => inSel(i) && matches(i, true));
  const n = Object.fromEntries(TAGS.map(t => [t, base.filter(i => i.tags.includes(t)).length]));
  $("chips").innerHTML = `<span class="lbl">Source type</span>` + TAGS.filter(t => n[t] || state.tags.has(t)).map(t =>
    `<button class="chip${state.tags.has(t) ? " on" : ""}" data-tag="${esc(t)}" aria-pressed="${state.tags.has(t)}" title="${state.tags.has(t) ? "Remove" : "Add"} ${esc(t)} filter"><span>${esc(t)}</span><b>${n[t]}</b>${state.tags.has(t) ? removeIcon : ""}</button>`).join("");
}
function activePills() {
  const pills = [];
  if (state.sel.length) pills.push(["sel", keyOf(state.sel)]);
  if (state.q) pills.push(["q", `“${state.q}”`]);
  state.tags.forEach(t => pills.push(["tag:" + t, t]));
  if (state.kind) pills.push(["kind", state.kind]);
  return pills.map(([k, label]) => `<button type="button" class="pill" data-clear="${esc(k)}" aria-label="Remove ${esc(label)} filter" title="Remove this filter"><span>${esc(label)}</span>${removeIcon}</button>`).join("");
}
function renderFilterbar() {
  const filtered = hasFilters();
  $("active-filters").innerHTML = `<span class="filter-label">${filtered ? "Filters:" : "No filters applied"}</span>` + activePills();
  $("clear-all").disabled = !filtered;
  $("filter-hint").hidden = !filtered;
  $("search-clear").hidden = !$("q").value;
}
function hl(s) {
  if (!state.q) return esc(s);
  const words = state.q.split(/\s+/).filter(Boolean).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return String(s).split(new RegExp(`(${words.join("|")})`, "gi"))
    .map((part, n) => n % 2 ? `<mark>${esc(part)}</mark>` : esc(part)).join("");
}
function card(i) {
  const crumb = `<div class="c" aria-label="Link" title="${esc(i.href)}">${hl(linkLabel(i))}</div>`;
  return `<a class="card" href="${esc(i.href)}" target="_blank" rel="noopener">
    <div class="t">${hl(i.title)}<span class="arrow">↗</span></div>
    ${i.desc ? `<div class="d">${hl(i.desc)}</div>` : ""}${crumb}
    <div class="m"><span class="badge">${esc(i.kind)}</span></div></a>`;
}
function renderMain() {
  const list = ITEMS.filter(i => inSel(i) && matches(i));
  const where = state.sel.length ? ` in <span class="crumb">${esc(keyOf(state.sel))}</span>` : "";
  const filtered = hasFilters();
  $("results").innerHTML = `<span><b>${list.length}</b> list${list.length === 1 ? "" : "s"}${where}</span>` +
    (filtered ? `<button class="clear" data-clear="all">Show all ${ITEMS.length} lists</button>` : "");
  if (!list.length) {
    $("app").innerHTML = `<div class="empty"><b>No matching lists</b><p>Try a different search or clear the filters to see every list.</p><button class="clear-all" data-clear="all">Clear all filters</button></div>`;
    return;
  }
  if (state.sort !== "topic") {
    const sorted = [...list].sort(state.sort === "outlet" ? (a, b) => a.desc.localeCompare(b.desc) || a.title.localeCompare(b.title)
      : (a, b) => a.title.localeCompare(b.title));
    $("app").innerHTML = `<section class="cat">${sorted.map(i => card(i)).join("")}</section>`;
    return;
  }
  let html = "", line = null, topic = null;
  for (const i of list) {
    if (i.line !== line) {
      if (line !== null) html += `</section>`;
      const n = list.filter(x => x.line === i.line).length;
      html += `<section class="cat" id="${esc(i.line)}"><div class="cathead"><h2>${esc(i.line)}</h2><span class="n">${n} list${n === 1 ? "" : "s"}</span></div>`;
      line = i.line; topic = null;
    }
    const t = keyOf(i.topic);
    if (t !== topic) {
      if (t || topic !== null) html += `<h3 class="topic">${i.topic.length ? i.topic.map(esc).join("<span>›</span>") : "General"}</h3>`;
      topic = t;
    }
    html += card(i);
  }
  const notes = state.sel.length ? PENDING.filter(p => p[0] === state.sel[0]) : (!filtered ? PENDING : []);
  if (notes.length) html += `</section><section class="cat"><div class="cathead"><h2>Not out yet</h2><span class="n">Expected late Nov – Dec</span></div>` +
    notes.map(p => `<div class="card pending"><div class="t">${esc(p[0])}</div><div class="d">${esc(p[1])}</div></div>`).join("");
  $("app").innerHTML = html + `</section>`;
}
function render() {
  renderTree(); renderChips(); renderFilterbar(); renderMain(); setCtl();
  const h = state.sel.length ? "#" + encodeURIComponent(keyOf(state.sel)) : location.pathname + location.search;
  try { history.replaceState(null, "", h); } catch (e) {}
}
$("tree").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  const key = b.dataset.key, parts = key ? key.split(SEP) : [];
  const wasSelected = key === keyOf(state.sel);
  if (!key) clearFilter("all");
  else if (wasSelected && state.open.has(key)) state.open.delete(key);
  else {
    if (parts.length === 1) [...state.open].forEach(k => { if (k.split(SEP)[0] !== key) state.open.delete(k); });
    for (let n = 1; n <= parts.length; n++) state.open.add(keyOf(parts.slice(0, n)));
    state.sel = parts;
  }
  render();
  const top = $("results").getBoundingClientRect().top + window.scrollY - $("controls").offsetHeight - 8;
  if (window.scrollY > top) window.scrollTo({ top, behavior: "smooth" });
});
function clearFilter(key) {
  if (key === "q" || key === "all") { state.q = ""; $("q").value = ""; }
  if (key === "kind" || key === "all") { state.kind = ""; $("kind").value = ""; }
  if (key === "all") { state.sel = []; state.tags.clear(); state.open.clear(); }
  if (key === "sel") { state.sel = []; state.open.clear(); }
  if (key.startsWith("tag:")) state.tags.delete(key.slice(4));
}
document.addEventListener("click", e => {
  const button = e.target.closest("button[data-clear]");
  if (!button || button.disabled) return;
  clearFilter(button.dataset.clear); render();
  $("q").focus({ preventScroll: true });
});
$("chips").addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  const t = b.dataset.tag;
  state.tags.has(t) ? state.tags.delete(t) : state.tags.add(t);
  render();
});
$("q").addEventListener("input", e => {
  state.q = e.target.value.trim();
  if (state.q) state.sel = [];
  render();
});
$("kind").addEventListener("change", e => { state.kind = e.target.value; render(); });
$("sort").addEventListener("change", e => { state.sort = e.target.value; render(); });
document.addEventListener("keydown", e => {
  if (document.documentElement.dataset.view === "master") return;
  if (e.isComposing || e.defaultPrevented) return;
  const editing = e.target.closest("input, textarea, select, [contenteditable]");
  if (e.key === "/" && !editing && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); $("q").focus(); }
  if (e.key === "Escape" && hasFilters()) {
    e.preventDefault(); clearFilter("all"); render();
    $("q").focus({ preventScroll: true });
  }
});
window.addEventListener("scroll", () => $("top").classList.toggle("show", window.scrollY > 800), { passive: true });
$("top").addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
const setCtl = () => document.documentElement.style.setProperty("--ctl", $("controls").offsetHeight + "px");
window.addEventListener("resize", setCtl);
if (typeof ResizeObserver !== "undefined") new ResizeObserver(setCtl).observe($("controls"));
function applyHash() {
  const hash = decodeURIComponent(location.hash.slice(1));
  state.open.clear(); state.sel = [];
  if (hash) {
    state.sel = hash.split(SEP);
    for (let n = 1; n <= state.sel.length; n++) state.open.add(keyOf(state.sel.slice(0, n)));
  }
}
window.addEventListener("hashchange", () => { applyHash(); render(); });
(function init() {
  const kinds = [...new Set(ITEMS.map(i => i.kind))].sort();
  $("kind").innerHTML = `<option value="">All list types</option>` +
    kinds.map(k => `<option value="${esc(k)}">${esc(k)} (${ITEMS.filter(i => i.kind === k).length})</option>`).join("");
  const topics = new Set(ITEMS.map(i => i.line));
  $("stats").innerHTML = [[ITEMS.length, "Lists"], [topics.size, "Topics"], [new Set(ITEMS.map(i => i.desc)).size, "Outlets"]]
    .map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join("");
  $("foot-n").textContent = ITEMS.length;
  const wide = matchMedia("(min-width: 901px)");
  const syncIndex = () => { $("index").open = wide.matches; };
  wide.addEventListener("change", syncIndex);
  syncIndex();
  applyHash();
  setCtl();
  render();
})();
