const fold = s => String(s).normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
const slug = s => "m-" + String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const noun = n => n === 1 ? "list" : "lists";
let mTimer = 0;
const mState = { q: "", topic: "" };

for (const cat of MASTER) {
  cat.max = cat.items.reduce((m, it) => Math.max(m, it.count), 1);
  cat.items.forEach((it, i) => { it.rank = i + 1; });
}
const titleCount = MASTER.reduce((n, cat) => n + cat.items.length, 0);
const multiCount = MASTER.reduce((n, cat) => n + cat.items.filter(it => it.count > 1).length, 0);

function mStats(pairs) {
  return pairs.map(([n, l]) => `<div class="stat"><b>${n.toLocaleString("en-US")}</b><span>${l}</span></div>`).join("");
}
const listStats = $("stats").innerHTML;
const listEyebrow = $("eyebrow-label").textContent;
const listSub = $("hero-sub").textContent;
const masterStats = mStats([[titleCount, "Titles"], [MASTER.length, "Categories"], [multiCount, "On 2+ lists"]]);
const masterSub = "Every work those lists name, merged by category. More mentions rank higher. Open a × count for the lists that name it.";

function chipText(src, ids) {
  const group = ids.map(id => LISTS[id]);
  const outlet = (src.outlet || "").trim();
  const twins = group.filter(s => (s.outlet || "").trim() === outlet).length;
  if (!outlet) return src.name;
  if (twins === 1) return outlet;
  const first = outlet.split(/\s+/)[0];
  const heads = first && first !== outlet ? [outlet, first] : [outlet];
  let rest = src.name;
  let used = outlet;
  for (const head of heads) {
    const re = new RegExp("^" + head.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*[:\\u2013\\u2014-]\\s*", "i");
    if (re.test(rest)) { rest = rest.replace(re, ""); used = head; break; }
  }
  return rest ? `${used} · ${rest}` : outlet;
}
function mMatch(it, query) {
  const terms = fold(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  const sources = it.sources.map(id => `${LISTS[id].name} ${LISTS[id].outlet}`).join(" ");
  const hay = fold(`${it.title} ${it.creator} ${sources}`);
  return terms.every(term => hay.includes(term));
}
function mHl(s, query) {
  if (!query) return esc(s);
  const words = query.split(/\s+/).filter(Boolean).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return esc(s);
  return String(s).split(new RegExp("(" + words.join("|") + ")", "gi"))
    .map((part, n) => n % 2 ? `<mark>${esc(part)}</mark>` : esc(part)).join("");
}
function mRow(cat, it, query) {
  const cid = `${slug(cat.topic)}-${it.rank}`;
  const chips = it.sources.map(id => {
    const src = LISTS[id];
    const label = chipText(src, it.sources);
    return `<a class="schip" href="${esc(src.url)}" target="_blank" rel="noopener" title="${esc(src.name)}">${esc(label)}</a>`;
  }).join("");
  const who = it.creator ? mHl(it.creator, query) : "";
  const mention = `Mentioned on ${it.count} ${noun(it.count)}. Show those lists`;
  return `<article class="mitem">
    <span class="rank">${it.rank}</span>
    <span class="mti">${mHl(it.title, query)}</span>
    <span class="who">${who}</span>
    <button type="button" class="xbadge" aria-expanded="false" aria-controls="${cid}" aria-label="${esc(mention)}">×${it.count}</button>
    <div class="schips" id="${cid}" hidden>${chips}</div>
  </article>`;
}
function renderMaster(scroll) {
  const query = mState.q;
  const topic = mState.topic;
  let shown = 0;
  let html = "";
  for (const cat of MASTER) {
    if (topic && cat.topic !== topic) continue;
    const rows = cat.items.filter(it => mMatch(it, query));
    if (!rows.length) continue;
    shown += rows.length;
    const id = slug(cat.topic);
    const note = query ? `${rows.length} shown` : `${cat.items.length.toLocaleString("en-US")} titles · ${cat.lists} ${noun(cat.lists)}`;
    html += `<section class="cat" id="${id}"><div class="cathead"><h2 id="${id}-h">${esc(cat.topic)}</h2><span class="n">${note}</span></div>
      <div class="mlist" aria-labelledby="${id}-h">
        <div class="mhead" aria-hidden="true"><span>#</span><span>Title</span><span>Creator</span><span>Mentions</span></div>
        ${rows.map(it => mRow(cat, it, query)).join("")}
      </div></section>`;
  }
  const where = topic ? ` in <span class="crumb">${esc(topic)}</span>` : "";
  const filtered = Boolean(query || topic);
  $("m-results").innerHTML = `<span><b>${shown.toLocaleString("en-US")}</b> title${shown === 1 ? "" : "s"}${where}</span>` +
    (filtered ? `<button type="button" class="clear" id="m-reset">Show all ${titleCount.toLocaleString("en-US")} titles</button>` : "");
  $("m-app").innerHTML = shown
    ? html
    : `<div class="empty"><b>No matching titles</b><p>Try a different search, or clear the category filter.</p><button type="button" class="clear-all" id="m-reset">Show all titles</button></div>`;
  $("m-topic").value = topic;
  $("m-clear").hidden = !$("mq").value;
  for (const chip of $("m-chips").querySelectorAll(".chip")) {
    const on = chip.dataset.topic === topic;
    chip.classList.toggle("on", on);
    chip.setAttribute("aria-pressed", String(on));
  }
  const current = $("m-chips").querySelector(".chip.on");
  if (current) current.scrollIntoView({ inline: "nearest", block: "nearest" });
  const bar = $("m-controls");
  document.documentElement.style.setProperty("--mctl", bar.offsetHeight + "px");
  if (scroll) {
    const top = $("m-results").getBoundingClientRect().top + window.scrollY - bar.offsetHeight - 8;
    if (window.scrollY > top) window.scrollTo({ top, behavior: "smooth" });
  }
}
function resetMaster() {
  mState.q = "";
  mState.topic = "";
  $("mq").value = "";
  renderMaster(true);
  $("mq").focus({ preventScroll: true });
}
function setTopic(topic) {
  mState.topic = topic;
  renderMaster(true);
}

const chips = [["", "All", titleCount], ...MASTER.map(cat => [cat.topic, cat.topic, cat.items.length])];
$("m-chips").innerHTML = `<span class="lbl">Category</span>` + chips.map(([id, label, n]) =>
  `<button type="button" class="chip" data-topic="${esc(id)}" aria-pressed="false"><span>${esc(label)}</span><b>${n.toLocaleString("en-US")}</b></button>`).join("");
$("m-topic").innerHTML = `<option value="">All categories</option>` + MASTER.map(cat =>
  `<option value="${esc(cat.topic)}">${esc(cat.topic)} (${cat.items.length.toLocaleString("en-US")})</option>`).join("");
$("m-chips").addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  setTopic(chip.dataset.topic);
});
$("m-topic").addEventListener("change", e => setTopic(e.target.value));
$("mq").addEventListener("input", e => {
  mState.q = e.target.value.trim();
  $("m-clear").hidden = !e.target.value;
  clearTimeout(mTimer);
  mTimer = setTimeout(() => renderMaster(false), 40);
});
$("m-clear").addEventListener("click", () => {
  mState.q = "";
  $("mq").value = "";
  renderMaster(false);
  $("mq").focus({ preventScroll: true });
});
$("panel-master").addEventListener("click", e => {
  if (e.target.closest("#m-reset")) { resetMaster(); return; }
  const badge = e.target.closest(".xbadge");
  if (!badge) return;
  const box = document.getElementById(badge.getAttribute("aria-controls"));
  const open = badge.getAttribute("aria-expanded") !== "true";
  badge.setAttribute("aria-expanded", String(open));
  if (box) box.hidden = !open;
});

const tabs = [...document.querySelectorAll(".viewtabs [role='tab']")];
function showView(view, focusTab) {
  document.documentElement.dataset.view = view;
  const master = view === "master";
  for (const tab of tabs) {
    const on = tab.dataset.view === view;
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
    if (on && focusTab) tab.focus();
  }
  $("panel-lists").hidden = master;
  $("panel-master").hidden = !master;
  $("eyebrow-label").textContent = master ? "Best of __YEAR__ · Master list" : listEyebrow;
  $("hero-sub").textContent = master ? masterSub : listSub;
  $("stats").innerHTML = master ? masterStats : listStats;
  const url = new URL(location.href);
  if (master) url.searchParams.set("view", "master");
  else url.searchParams.delete("view");
  history.replaceState(null, "", url.pathname + url.search + url.hash);
  if (master) renderMaster(false);
  else window.dispatchEvent(new Event("resize"));
}
document.querySelector(".viewtabs").addEventListener("keydown", e => {
  if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
  const i = tabs.indexOf(document.activeElement);
  if (i < 0) return;
  e.preventDefault();
  const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
  showView(next.dataset.view, true);
});
for (const tab of tabs) tab.addEventListener("click", () => showView(tab.dataset.view, false));

document.addEventListener("keydown", e => {
  if (document.documentElement.dataset.view !== "master") return;
  if (e.isComposing || e.defaultPrevented) return;
  const editing = e.target.closest("input, textarea, select, [contenteditable]");
  if (e.key === "/" && !editing && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    $("mq").focus();
  }
  if (e.key === "Escape" && (mState.q || mState.topic)) {
    e.preventDefault();
    resetMaster();
  }
});

showView(new URLSearchParams(location.search).get("view") === "master" ? "master" : "lists", false);
