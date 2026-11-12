/* Brandproof web app: plain JavaScript, no build step. */
"use strict";

const S = { token: null, me: null, brandId: null, samples: null, activeFinding: null };
const $ = (sel, el = document) => el.querySelector(sel);
const app = $("#app");

const CAT = { claims: "Claims", tone: "Tone & messaging", terminology: "Terminology", style: "Writing style",
  accessibility: "Accessibility", visual: "Visual", legal: "Legal & disclosure" };
const STATUS = { draft: "Draft", in_review: "In review", changes_requested: "Changes requested", approved: "Approved" };
const CHANNEL = { social: "Instagram / social", whatsapp: "WhatsApp", email: "Email", blog: "Blog", press: "Press note", packaging: "Packaging" };
const CLAIM = { outdated: "Outdated", contradicted: "Contradicted", unsupported: "Unsupported" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function toast(msg, err = false) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.className = "toast"), 3600);
}
function ago(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now"; if (s < 3600) return Math.floor(s / 60) + " min ago";
  if (s < 86400) return Math.floor(s / 3600) + " h ago"; return new Date(iso).toLocaleDateString();
}
function loading(msg = "Loading…") {
  app.innerHTML = `<div class="skeleton" aria-label="${esc(msg)}"><div class="sk h1"></div><div class="sk line" style="width:60%"></div>
    <div class="sk-grid"><div class="sk block"></div><div class="sk block"></div></div><div class="sk line" style="width:80%"></div></div>`;
}

/* ---------- motion helpers ---------- */
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function enter(root = app) {
  if (REDUCED) return;
  root.classList.remove("page-enter"); void root.offsetWidth; root.classList.add("page-enter");
  stagger(root);
  countUp(root);
}
function stagger(root = app) {
  if (REDUCED) return;
  const groups = [".sample", ".step", ".kpi", ".clause", ".finding", ".feature-row .panel", "tbody tr", ".bar", ".timeline li"];
  groups.forEach(sel => root.querySelectorAll(sel).forEach((el, i) => { if (i < 24) { el.style.setProperty("--i", i); el.classList.add("stagger"); } }));
  root.querySelectorAll(".bar").forEach((el, i) => el.querySelector(".fill")?.style.setProperty("--i", i));
  root.querySelectorAll("mark.hl").forEach((el, i) => el.style.setProperty("--i", i));
}
function countUp(root = app) {
  if (REDUCED) return;
  root.querySelectorAll(".kpi b").forEach(el => {
    const m = el.textContent.trim().match(/^(\d+)(%?)(\/\d+)?$/); if (!m) return;
    const end = +m[1], suffix = m[2] + (m[3] || ""); if (end < 2) return;
    const t0 = performance.now(), dur = 700;
    const tick = t => { const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = Math.round(end * e) + suffix; if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
}
const CHECK_STEPS = ["Exact rules: terms, claims, style", "Retrieving guideline clauses and facts", "AI review of tone, claims and legal", "Citation gate: dropping uncited flags", "Preparing minimal fixes"];
function checkingOverlay() {
  const el = document.createElement("div"); el.className = "checking";
  el.innerHTML = `<div class="card" role="status"><b>Checking against the rulebook…</b>
    <div class="scanbox"><span style="top:12px;width:70%"></span><span style="top:30px;width:45%"></span></div>
    <ol>${CHECK_STEPS.map(t => `<li><span class="dot"></span>${t}</li>`).join("")}</ol></div>`;
  document.body.appendChild(el);
  const lis = [...el.querySelectorAll("li")]; let k = 0;
  const adv = () => { if (k > 0) { lis[k - 1].className = "done"; lis[k - 1].querySelector(".dot").textContent = "✓"; } if (k < lis.length) lis[k].className = "on"; k++; };
  adv(); const timer = setInterval(() => { if (k < lis.length) adv(); }, 1800);
  return () => { clearInterval(timer); while (k <= lis.length) adv(); setTimeout(() => { el.style.transition = "opacity .25s"; el.style.opacity = "0"; setTimeout(() => el.remove(), 260); }, 250); };
}
async function withChecking(fn) { const done = checkingOverlay(); try { return await fn(); } finally { done(); } }

const store = {  // browser storage can be blocked (private windows): never let that break the app
  get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* ignore */ } },
  del(k) { try { localStorage.removeItem(k); } catch (_) { /* ignore */ } },
};
async function api(method, path, body) {
  const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 130000);
  let res;
  try {
    res = await fetch(path, {
      method, signal: ctl.signal,
      headers: { "Content-Type": "application/json", ...(S.token ? { Authorization: "Bearer " + S.token } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new Error(e.name === "AbortError" ? "This is taking too long. Please try again." : "Can't reach Brandproof. Check your internet connection and try again.");
  } finally { clearTimeout(timer); }
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty */ }
  if (res.status === 401) { store.del("bp_token"); S.token = null; }
  if (res.status === 429) throw new Error((data && data.detail) || "Too many requests. Please wait a minute and try again.");
  if (res.status >= 500 && !(data && data.detail)) throw new Error("Something went wrong on our side. Please try again.");
  if (!res.ok) throw new Error((data && data.detail && (typeof data.detail === "string" ? data.detail : data.detail[0]?.msg)) || `Request failed (${res.status})`);
  guideTrack(method, path, body);
  return data;
}

/* ---------------- judge guide: 6 steps, ticked automatically ---------------- */
const GUIDE = [
  ["check", "Check a sample draft", "#/new"],
  ["decide", "Accept, edit or dispute an issue", null],
  ["submit", "Submit the draft for review", null],
  ["approve", "Switch Role to Manager and approve it", "#/queue"],
  ["lang", "Check a Tamil or Hindi sample", "#/new"],
  ["explore", "Open Learning, Rulebook versions or Evaluation", "#/learning"],
];
let guideDone = new Set((store.get("bp_guide") || "").split(",").filter(Boolean));
function guideMark(k) {
  if (guideDone.has(k)) return;
  guideDone.add(k); store.set("bp_guide", [...guideDone].join(",")); renderGuide(true);
}
function guideTrack(method, path, body) {
  if (method !== "POST") return;
  if (/\/api\/drafts\/[^/]+\/check$/.test(path)) guideMark("check");
  else if (/\/api\/findings\/[^/]+\/decision$/.test(path)) guideMark("decide");
  else if (/\/submit$/.test(path)) guideMark("submit");
  else if (/\/review$/.test(path) && body && body.action === "approve") guideMark("approve");
  else if (path === "/api/drafts" && body && /^r\d/.test(body.sample_id || "")) guideMark("lang");
}
function renderGuide(pulse) {
  let g = $("#guide");
  if (!S.token) { if (g) g.remove(); return; }
  if (!g) { g = document.createElement("div"); g.id = "guide"; document.body.appendChild(g); }
  const n = GUIDE.filter(([k]) => guideDone.has(k)).length, open = g.classList.contains("open");
  g.innerHTML = `<button class="guide-btn" id="guideBtn">${n === GUIDE.length ? "✓ Tour done" : `Try this · ${n}/${GUIDE.length}`}</button>
    <div class="guide-panel"><b>Try Brandproof in 3 minutes</b>
      <ol>${GUIDE.map(([k, t, href]) => `<li class="${guideDone.has(k) ? "done" : ""}">${href && !guideDone.has(k) ? `<a href="${href}">${t}</a>` : t}</li>`).join("")}</ol>
      <p class="small muted">No sign-in needed. Use <b>Role</b> (top right) to act as creator, manager, reviewer or admin.</p></div>`;
  if (open) g.classList.add("open");
  if (pulse) { g.classList.remove("pulse"); void g.offsetWidth; g.classList.add("pulse"); }
  $("#guideBtn").onclick = () => g.classList.toggle("open");
}
async function busy(btn, fn, label) {
  const old = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spinner${btn.classList.contains("btn-primary") || btn.classList.contains("btn-good") ? "" : " dark"}"></span> ${label || "Working…"}`;
  try { return await fn(); } catch (e) { toast(e.message, true); } finally { btn.disabled = false; btn.innerHTML = old; }
}

/* ---------------- session ---------------- */
async function startDemo(role = "creator") {
  const d = await api("POST", "/api/session/demo", { name: "Guest", role });
  S.token = d.token; store.set("bp_token", d.token);
  await loadMe();
}
async function loadMe() {
  S.me = await api("GET", "/api/me");
  const saved = store.get("bp_brand");
  S.brandId = S.me.brands.find(b => b.id === saved) ? saved : S.me.brands[0]?.id;
  $("#topbar").hidden = false; $("#demoBanner").hidden = S.me.org.kind !== "guest";
  $("#roleSelect").value = S.me.role;
  $("#brandSelect").innerHTML = S.me.brands.map(b => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
  $("#brandSelect").value = S.brandId;
  const ai = S.me.ai;
  $("#aiChip").textContent = ai.text_model ? `AI: ${ai.text_model.split(":")[1]}${ai.vision_model ? " + vision" : ""}` : "AI checks off: rules only";
  refreshQueueCount();
}
async function refreshQueueCount() {
  try { const q = await api("GET", "/api/drafts?status=in_review"); $("#queueCount").textContent = q.length || ""; } catch (_) { /* ignore */ }
}
$("#roleSelect").addEventListener("change", async e => {
  try { await api("POST", "/api/session/role", { role: e.target.value }); S.me.role = e.target.value; toast(`You are now acting as ${e.target.value}`); route(); }
  catch (err) { toast(err.message, true); e.target.value = S.me.role; }
});
$("#brandSelect").addEventListener("change", e => { S.brandId = e.target.value; store.set("bp_brand", S.brandId); route(); });
$("#menuBtn").addEventListener("click", () => $("#nav").classList.toggle("open"));

/* ---------------- router ---------------- */
const routes = [
  [/^#?\/?$/, landing], [/^#\/new$/, newCheck], [/^#\/drafts$/, drafts], [/^#\/queue$/, queue],
  [/^#\/d\/([\w]+)$/, draftView], [/^#\/rulebook$/, rulebook], [/^#\/insights$/, insights],
  [/^#\/eval$/, evaluation], [/^#\/learning$/, learningPage], [/^#\/how$/, how],
];
async function route() {
  const h = location.hash || "#/";
  $("#nav").classList.remove("open");
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("active", h.startsWith("#/" + a.dataset.nav) || (a.dataset.nav === "drafts" && h.startsWith("#/d/"))));
  if (!S.token && h !== "#/" && h !== "" && h !== "#/how") { location.hash = "#/"; return; }
  if (S.token && !S.me) { try { await loadMe(); } catch (_) { S.token = null; store.del("bp_token"); location.hash = "#/"; return; } }
  if (/^#\/(learning|eval|rulebook)/.test(h)) guideMark("explore");
  renderGuide();
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) { window.scrollTo(0, 0); try { await fn(...m.slice(1)); enter(); } catch (e) { app.innerHTML = `<div class="panel empty">${esc(e.message)}<br><br><a href="#/new">Back to New check</a></div>`; } return; }
  }
  location.hash = "#/";
}
window.addEventListener("hashchange", route);

/* ---------------- landing ---------------- */
function landing() {
  $("#topbar").hidden = !S.token; $("#demoBanner").hidden = !S.token;
  app.innerHTML = `
  <section class="hero">
    <div>
      <div class="pill cat" style="margin-bottom:.8rem">Brand governance before publication</div>
      <h1>Catch <span class="grad">off-brand content</span> before anyone publishes it.</h1>
      <p class="lead">Brandproof checks posts, emails, blogs and images against your own brand guidelines, approved facts and assets. Every issue is explained with the exact clause or fact it breaks, comes with a minimal fix, and a person makes the final call.</p>
      <div class="hero-actions">
        <button class="btn-primary" id="startBtn">Start the demo, no sign-up →</button>
        <a class="btn" href="#/how">How it works</a>
      </div>
      <p class="muted small">You get a private demo workspace with a fictional skincare brand and 12 sample drafts. Takes under 2 minutes.</p>
    </div>
    <div class="preview-card">
      <div class="row" style="margin-bottom:.5rem"><span class="pill high">High</span><span class="pill cat">Claims</span><span class="pill rule">Rule</span></div>
      <p>Glow serum, <span class="q">clinically proven</span> to remove acne in 7 days.</p>
      <div class="cite"><b>Guideline 4.3 · No absolute claims.</b> Never use absolute or superlative claims such as 'clinically proven' unless that exact claim is on the fact sheet.</div>
      <p class="fix">Fix: <span class="diff-del">clinically proven</span> <span class="diff-ins">dermatologist tested</span></p>
      <div class="row" style="margin-top:.6rem"><button class="btn-sm btn-good">Accept</button><button class="btn-sm">Edit</button><button class="btn-sm">Dispute</button></div>
    </div>
  </section>
  <div class="steps">
    <div class="step"><div class="n">1</div><b>Pick a draft</b><span class="muted small">Use a sample, paste your own text, or upload an image or PDF.</span></div>
    <div class="step"><div class="n">2</div><b>Run the check</b><span class="muted small">Rules and AI check tone, terms, claims, visuals and accessibility.</span></div>
    <div class="step"><div class="n">3</div><b>Fix or dispute</b><span class="muted small">Each issue cites its guideline or fact. Accept, edit or dispute it.</span></div>
    <div class="step"><div class="n">4</div><b>Approve as manager</b><span class="muted small">Switch role (top right), review the changes and approve or send back.</span></div>
  </div>
  <div class="feature-row">
    <div class="panel"><h3>No citation, no flag</h3><p class="muted small">AI findings that don't point to a real clause or fact, or that quote text not in the draft, are discarded automatically.</p></div>
    <div class="panel"><h3>Claims checked against facts</h3><p class="muted small">Prices, ingredients and offers are matched to the approved fact sheet: Supported, Outdated, Contradicted or Unsupported.</p></div>
    <div class="panel"><h3>Humans decide</h3><p class="muted small">Nothing is auto-published or silently rewritten. Every decision is logged with who, when and which version.</p></div>
  </div>`;
  $("#startBtn").onclick = e => busy(e.currentTarget, async () => { await startDemo(); location.hash = "#/new"; }, "Creating your workspace…");
}

/* ---------------- new check ---------------- */
async function newCheck() {
  if (!S.samples) S.samples = await api("GET", "/api/samples");
  const demoBrand = (S.me.brands.find(b => b.id === S.brandId) || {}).name === "Neem & Nila Skincare";
  app.innerHTML = `
  <div class="page-head"><div><h1>New check</h1><p class="muted">Pick a sample, or paste your own content.</p></div></div>
  <div class="grid-2">
    <div class="panel">
      <div class="iss-head"><h2>Samples</h2>${demoBrand ? `<div class="seg" id="sampleTabs"><button class="on" data-tab="en">English</button><button data-tab="indic">Tamil &amp; Hindi</button></div>` : ""}</div>
      ${demoBrand ? `<div class="samples compact">${S.samples.map(s => `<button class="sample" data-sample="${s.id}" data-set="${s.lang ? "indic" : "en"}" ${s.lang ? "hidden" : ""}><b>${esc(s.title.split(" — ")[0])}</b><i class="chan">${s.lang ? `<span class="lang-tag">${esc(s.lang)}</span> ` : ""}${CHANNEL[s.channel] || s.channel}${s.has_image ? " · image" : ""}</i></button>`).join("")}</div>`
      : `<p class="muted">Samples are written for the Neem &amp; Nila demo brand. Switch brand in the top bar to use them, or check your own content here.</p>`}
    </div>
    <div class="panel">
      <h2>Check your own content</h2>
      <label class="field"><span>Title</span><input id="fTitle" placeholder="e.g. Diwali serum post"></label>
      <label class="field"><span>Channel</span><select id="fChannel">${Object.entries(CHANNEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label>
      <label class="field"><span>Text</span><textarea id="fText" maxlength="20000" placeholder="Paste a caption, email, blog paragraph or press note (any language)…"></textarea></label>
      <label class="field"><span>Image (optional)</span><span class="drop"><input id="fImage" type="file" accept="image/png,image/jpeg,image/webp"><span class="drop-text" data-for="fImage">Click to add a PNG or JPG</span></span></label>
      <div id="imgPrev"></div>
      <label class="field"><span>Alt text for the image</span><input id="fAlt" placeholder="Describe what the image shows"></label>
      <label class="field"><span>Or upload a PDF (brochure, press note)</span><span class="drop"><input id="fPdf" type="file" accept="application/pdf"><span class="drop-text" data-for="fPdf">Click to add a PDF</span></span></label>
      <button class="btn-primary" id="checkBtn">Check content</button>
    </div>
  </div>`;
  let image = null, pdf = null;
  app.querySelectorAll("#sampleTabs [data-tab]").forEach(t => t.onclick = () => {
    app.querySelectorAll("#sampleTabs [data-tab]").forEach(x => x.classList.toggle("on", x === t));
    app.querySelectorAll(".sample[data-set]").forEach(b => { b.hidden = b.dataset.set !== t.dataset.tab; });
  });
  app.querySelectorAll("[data-sample]").forEach(b => b.onclick = () => busy(b, () => withChecking(async () => {
    const d = await api("POST", "/api/drafts", { sample_id: b.dataset.sample, brand_id: S.brandId });
    await api("POST", `/api/drafts/${d.id}/check`); location.hash = "#/d/" + d.id;
  }), "Checking…"));
  $("#fImage").onchange = async e => { image = e.target.files[0] ? await shrinkImage(e.target.files[0]) : null; $("#imgPrev").innerHTML = image ? `<img src="${image}" style="max-width:160px;border-radius:8px">` : ""; };
  $("#fPdf").onchange = async e => { pdf = e.target.files[0] ? await fileB64(e.target.files[0]) : null; if (e.target.files[0]?.size > 3.5e6) { toast("PDF must be under 3.5 MB", true); pdf = null; e.target.value = ""; } };
  $("#checkBtn").onclick = e => busy(e.currentTarget, async () => {
    const body = { title: $("#fTitle").value, channel: $("#fChannel").value, text: $("#fText").value, image_b64: image, alt_text: $("#fAlt").value, pdf_b64: pdf, brand_id: S.brandId };
    if (!body.text.trim() && !image && !pdf) throw new Error("Add some text, an image or a PDF first.");
    await withChecking(async () => {
      const d = await api("POST", "/api/drafts", body);
      await api("POST", `/api/drafts/${d.id}/check`); location.hash = "#/d/" + d.id;
    });
  }, "Checking…");
}
function fileB64(file) { return new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(file); }); }
async function shrinkImage(file) {
  const url = await fileB64(file);
  const img = await new Promise(ok => { const i = new Image(); i.onload = () => ok(i); i.src = url; });
  const scale = Math.min(1, 1024 / Math.max(img.width, img.height));
  const c = document.createElement("canvas"); c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.85);
}

/* ---------------- lists ---------------- */
async function drafts(filter) {
  loading();
  const rows = await api("GET", "/api/drafts" + (filter ? "?status=" + filter : ""));
  app.innerHTML = `
  <div class="page-head"><div><h1>Drafts</h1><p class="muted">Everything checked in this workspace.</p></div><a class="btn btn-primary" href="#/new">+ New check</a></div>
  <div class="tabs">${[["", "All"], ["draft", "Draft"], ["in_review", "In review"], ["changes_requested", "Changes requested"], ["approved", "Approved"]].map(([k, v]) => `<button class="${(filter || "") === k ? "on" : ""}" data-f="${k}">${v}</button>`).join("")}</div>
  <div class="panel">${draftTable(rows)}</div>`;
  app.querySelectorAll("[data-f]").forEach(b => b.onclick = () => drafts(b.dataset.f));
  bindRows();
}
function draftTable(rows) {
  if (!rows.length) return `<div class="empty">Nothing here yet. <a href="#/new">Run a check</a>.</div>`;
  return `<table><thead><tr><th>Title</th><th class="hide-sm">Channel</th><th>Status</th><th>Issues</th><th class="hide-sm">Updated</th></tr></thead><tbody>${rows.map(r => `
    <tr class="click" data-href="#/d/${r.id}"><td><b>${esc(r.title)}</b><div class="muted small">${esc(r.brand)} · v${r.current_version} · by ${esc(r.created_by)}</div></td>
    <td class="hide-sm">${CHANNEL[r.channel] || r.channel}</td><td><span class="pill ${r.status}">${STATUS[r.status]}</span></td>
    <td>${r.issues == null ? '<span class="muted">Not checked</span>' : `${r.issues}${r.open_issues ? ` <span class="muted small">(${r.open_issues} open)</span>` : ""}`}</td>
    <td class="muted small hide-sm">${ago(r.updated_at)}</td></tr>`).join("")}</tbody></table>`;
}
function bindRows() { app.querySelectorAll("tr[data-href]").forEach(tr => tr.onclick = () => (location.hash = tr.dataset.href)); }
async function queue() {
  loading();
  const rows = await api("GET", "/api/drafts?status=in_review");
  const canReview = ["manager", "reviewer", "admin"].includes(S.me.role);
  app.innerHTML = `
  <div class="page-head"><div><h1>Review queue</h1><p class="muted">Drafts waiting for a manager or reviewer decision.</p></div></div>
  ${canReview ? "" : `<div class="warn">You are acting as <b>${S.me.role}</b>. Switch <b>Role</b> to Manager (top right) to approve or send drafts back.</div>`}
  <div class="panel">${rows.length ? draftTable(rows) : `<div class="empty">The queue is empty. Submit a checked draft for review and it appears here.</div>`}</div>`;
  bindRows(); refreshQueueCount();
}

/* ---------------- draft view (the core screen) ---------------- */
async function draftView(id) {
  loading("Loading draft…");
  const d = await api("GET", `/api/drafts/${id}`);
  renderDraft(d);
}
function renderDraft(d) {
  const { draft, versions, check, findings, events } = d;
  const cur = versions[versions.length - 1];
  const editable = ["draft", "changes_requested"].includes(draft.status);
  const reviewer = ["manager", "reviewer", "admin"].includes(S.me.role);
  const open = findings.filter(f => !f.decision).length;
  const lastChange = [...events].reverse().find(e => e.action === "changes_requested");
  const firstV = versions[0];
  const fixedFrom = check?.summary?.carried_from_version ? versions.find(v => v.n === check.summary.carried_from_version) : null;

  app.innerHTML = `
  <div class="page-head">
    <div>
      <div class="row"><a href="#/drafts" class="small">← Drafts</a></div>
      <h1>${esc(draft.title)}</h1>
      <div class="row small"><span class="pill ${draft.status}">${STATUS[draft.status]}</span>
        <span class="muted">${CHANNEL[draft.channel] || draft.channel} · ${esc(d.brand.name)} · version ${cur.n} · by ${esc(draft.created_by)}</span></div>
    </div>
    <div class="row" id="headActions"></div>
  </div>
  ${draft.status === "changes_requested" && lastChange ? `<div class="warn"><b>Changes requested by ${esc(lastChange.actor)} (${lastChange.role}):</b> ${esc(lastChange.comment)}<br>Edit the text below and it will be re-checked.</div>` : ""}
  ${draft.status === "in_review" && !reviewer ? `<div class="warn">Submitted for review. Switch <b>Role</b> to Manager (top right) to approve or send it back.</div>` : ""}
  ${draft.status === "approved" ? `<div class="okbox" style="margin-bottom:1rem">✓ Approved and ready to publish. This version is locked and the decision trail is below.</div>` : ""}
  <div class="grid-2">
    <div>
      <div class="panel">
        <div class="row"><h2 style="margin:0">${fixedFrom ? "Final text (fixes applied)" : "Content"}</h2><span class="spacer"></span>
          ${editable ? `<button class="btn-sm" id="editBtn">Edit text</button>` : ""}</div>
        <div id="docArea" style="margin-top:.6rem">${docHtml(cur.text, findings, !!fixedFrom)}</div>
        ${cur.image_b64 ? `<div class="img-wrap"><img src="${cur.image_b64}" alt="${esc(cur.alt_text || "")}"><div class="small"><b>Alt text:</b> ${cur.alt_text ? esc(cur.alt_text) : '<span class="expired">missing</span>'}</div></div>` : ""}
        ${fixedFrom ? `<details style="margin-top:.8rem"><summary class="small"><b>What changed from version ${fixedFrom.n}</b></summary><div class="doc small" style="margin-top:.5rem">${wordDiff(fixedFrom.text, cur.text)}</div></details>` : ""}
        ${versions.length > 1 && !fixedFrom ? `<details style="margin-top:.8rem"><summary class="small"><b>Changes since version 1</b></summary><div class="doc small" style="margin-top:.5rem">${wordDiff(firstV.text, cur.text)}</div></details>` : ""}
      </div>
      <div class="panel">
        <h2>Activity</h2>
        <ul class="timeline">${events.map(e => `<li><b>${esc(e.actor)}</b> <span class="muted">(${e.role})</span> ${actionText(e.action)}${e.comment ? `: “${esc(e.comment)}”` : ""} <span class="muted small">· ${ago(e.at)}</span></li>`).join("") || '<li class="muted">No activity yet.</li>'}</ul>
        <div class="inline-form"><input id="commentIn" placeholder="Add a comment for the team…"><button class="btn-sm" id="commentBtn">Comment</button></div>
      </div>
    </div>
    <div class="sticky">
      <div class="panel" id="findingsPanel">${findingsHtml(draft, check, findings, editable)}</div>
    </div>
  </div>`;

  // header actions
  const ha = $("#headActions");
  if (editable) {
    ha.innerHTML = `<button id="recheckBtn">Re-run check</button><button class="btn-primary" id="submitBtn" ${!check || open ? "disabled" : ""} title="${!check ? "Run a check first" : open ? `Decide on ${open} open issue(s) first` : ""}">Submit for review</button>`;
    $("#recheckBtn").onclick = e => busy(e.currentTarget, () => withChecking(async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/check`)); enter(); }), "Checking…");
    $("#submitBtn").onclick = e => busy(e.currentTarget, async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/submit`)); enter(); refreshQueueCount(); toast("Submitted for review. Switch role to Manager to review it."); }, "Submitting…");
  } else if (draft.status === "in_review" && reviewer) {
    ha.innerHTML = `<input id="reviewComment" placeholder="Comment (required to send back)" style="width:260px"><button id="sendBackBtn">Send back</button><button class="btn-good" id="approveBtn">Approve</button>`;
    $("#approveBtn").onclick = e => busy(e.currentTarget, async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/review`, { action: "approve", comment: $("#reviewComment").value })); enter(); refreshQueueCount(); toast("Approved"); }, "Approving…");
    $("#sendBackBtn").onclick = e => busy(e.currentTarget, async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/review`, { action: "request_changes", comment: $("#reviewComment").value })); enter(); refreshQueueCount(); toast("Sent back to the creator"); }, "Sending…");
  }
  if (editable && $("#editBtn")) $("#editBtn").onclick = () => editMode(draft, cur);
  $("#commentBtn").onclick = e => { const c = $("#commentIn").value.trim(); if (!c) return; busy(e.currentTarget, async () => renderDraft(await api("POST", `/api/drafts/${draft.id}/comment`, { comment: c }))); };
  bindFindings(d, editable);
}
function actionText(a) {
  return { created: "created the draft", checked: "ran a check", submitted: "submitted for review", approved: "approved", changes_requested: "requested changes", edited: "edited the text", commented: "commented" }[a] || a;
}
function docHtml(text, findings, readOnly) {
  // Show the most specific highlights: shorter spans win where findings overlap; the rest stay in the list.
  const all = findings.map((f, i) => ({ ...f, i: i + 1 })).filter(f => f.start_idx != null && f.end_idx != null)
    .sort((a, b) => (a.end_idx - a.start_idx) - (b.end_idx - b.start_idx));
  const chosen = [];
  for (const f of all) if (!chosen.some(c => f.start_idx < c.end_idx && c.start_idx < f.end_idx)) chosen.push(f);
  const spans = chosen.sort((a, b) => a.start_idx - b.start_idx);
  // Server offsets count Unicode code points (Python); JS strings count UTF-16 units, so slice by code point.
  const cp = Array.from(text);
  const sl = (a, b) => cp.slice(a, b).join("");
  let out = "", pos = 0;
  for (const f of spans) {
    if (f.start_idx < pos) continue; // overlapping: already inside another highlight
    out += esc(sl(pos, f.start_idx));
    const cls = readOnly ? "" : f.decision ? "done" : f.severity;
    out += readOnly ? esc(sl(f.start_idx, f.end_idx)) : `<mark class="hl ${cls}" data-f="${f.id}">${esc(sl(f.start_idx, f.end_idx))}<sup>${f.i}</sup></mark>`;
    pos = f.end_idx;
  }
  out += esc(sl(pos));
  return `<div class="doc">${out || '<span class="muted">(image only)</span>'}</div>`;
}
function findingsHtml(draft, check, findings, editable) {
  if (!check) return `<h2>Issues</h2><div class="empty">Not checked yet.<br><br><button class="btn-primary" id="firstCheck">Run check</button></div>`;
  const s = check.summary || {};
  const decided = findings.filter(f => f.decision).length;
  const high = findings.filter(f => f.severity === "high").length;
  const aiCount = findings.filter(f => f.source === "ai").length;
  const ai = check.ai_status;
  const pct = findings.length ? Math.round((decided / findings.length) * 100) : 100;
  const order = [["high", "High severity"], ["medium", "Medium"], ["low", "Low"]];
  const numbered = findings.map((f, i) => [f, i + 1]);
  const disputedFirst = !editable && findings.some(f => f.decision === "disputed");
  const groups = disputedFirst
    ? [["Disputed by the creator", numbered.filter(([f]) => f.decision === "disputed")], ["Other issues", numbered.filter(([f]) => f.decision !== "disputed")]]
    : order.map(([k, label]) => [label, numbered.filter(([f]) => f.severity === k)]);
  return `
    <div class="iss-head">
      <h2>Issues</h2>
      <span class="muted small">${s.rulebook_version ? `<span title="The rulebook version this check used">rulebook v${s.rulebook_version}</span> · ` : ""}${s.cached ? "saved result · " : ""}${(check.duration_ms / 1000).toFixed(1)} s</span>
    </div>
    <div class="statline">
      <span><b>${findings.length}</b> issues</span>
      <span class="${high ? "bad" : ""}"><b>${high}</b> high</span>
      <span><b>${aiCount}</b> by AI</span>
      <span title="AI suggestions that did not cite a real guideline clause or fact, or quoted text not in the draft, are thrown away"><b>${check.dropped_uncited}</b> uncited AI flags blocked</span>
    </div>
    ${findings.length ? `<div class="decide-bar"><div class="track"><div style="width:${pct}%"></div></div><span class="small"><b>${decided}/${findings.length}</b> decided</span>
      ${editable ? `<button class="btn-sm" id="acceptAll" ${decided === findings.length ? "disabled" : ""}>Accept all fixes</button>` : ""}</div>` : ""}
    ${ai === "failed" ? `<div class="warn small">AI review didn't respond this time, so only rule-based checks are shown. <b>Re-run check</b> to try again.</div>` : ""}
    ${ai === "not_configured" ? `<div class="warn small">AI checks aren't configured; showing rule-based checks only.</div>` : ""}
    ${s.language && s.language.indic ? `<div class="lang-note small"><span class="lang-tag">${esc(s.language.label)}</span> Checked against the English rulebook in the draft's own language; fixes keep the same language and script.</div>` : ""}
    ${check.model ? `<div class="ai-note small"><span class="ai-dot"></span>AI-assisted by <b>${esc(check.model.replace("sarvam_flash:", "Sarvam ").replace("sarvam:", "Sarvam ").replace("gemini_backup:", "Gemini ").replace("gemini:", "Gemini "))}</b> · every AI finding cites a clause or fact</div>` : ""}
    ${(s.verified_claims || []).length ? `<p class="verified small">✓ Verified against the fact sheet: ${s.verified_claims.map(v => `“${esc(v.quote)}” (${esc(v.cite_code)})`).join(", ")}</p>` : ""}
    ${!findings.length ? `<div class="okbox">No issues found. This content follows the rulebook.</div>` : ""}
    ${disputedFirst && findings.some(f => f.decision === "disputed" && f.severity === "high" && ["claims", "legal"].includes(f.category)) ? `<div class="warn small">A high-severity claim was disputed: a manager must add a comment to approve, or a Reviewer can approve directly.</div>` : ""}
    <div id="flist" class="flist">${groups.filter(([, g]) => g.length).map(([label, g]) => `<div class="group-label">${label} <span>${g.length}</span></div>${g.map(([f, n]) => findingCard(f, n, editable, (s.learning_notes || {})[String(f.ord)])).join("")}`).join("")}</div>
    ${hiddenHtml(s)}`;
}
function hiddenHtml(s) {
  const h = s.hidden || [];
  const L = s.learning;
  if (!L || !L.enabled) return "";
  if (!h.length) return L.decisions ? `<p class="learn-note small"><span class="learn-dot"></span>Learning from <b>${L.decisions}</b> past reviewer decisions · <a href="#/learning">see what it learned</a></p>` : "";
  return `<details class="hidden-box"><summary><span class="learn-dot"></span><b>${h.length}</b> flag${h.length > 1 ? "s" : ""} hidden by learning from ${L.decisions} reviewer decisions <span class="muted">· show</span></summary>
    ${h.map(x => `<div class="hidden-item"><div><b>${esc(CAT[x.category] || x.category)}</b> · ${x.quote && x.quote !== "[image]" ? `“${esc(x.quote)}”` : "image"} <span class="muted small">(${esc(x.cite_code || "")})</span></div>
      <div class="small muted">${esc(x.explanation || "")}</div><div class="small learn-why">Hidden: ${esc(x.hidden_reason)}</div></div>`).join("")}
    <p class="small muted">Hidden flags are never deleted. An admin can switch learning off for any guideline on the <a href="#/learning">Learning</a> page.</p></details>`;
}
function findingCard(f, n, editable, learnNote) {
  const quoteable = f.quote && f.quote !== "*" && f.quote !== "[image]";
  const fixShown = f.decision === "edited" ? f.edited_fix : f.fix_text;
  const src = f.cite_type === "fact" ? "Fact " + esc(f.cite_code) : "Guideline " + esc(f.cite_code);
  return `<div class="finding sev-${f.severity} ${f.decision ? "decided" : ""}" id="f-${f.id}">
    <div class="f-top"><span class="num">${n}</span>
      <span class="f-quote">${quoteable ? `“${esc(f.quote)}”` : f.quote === "[image]" ? "In the image" : "Whole draft"}</span>
      <span class="f-tags"><span class="tag">${CAT[f.category] || f.category}</span>${f.claim_status ? `<span class="tag claim">${CLAIM[f.claim_status] || f.claim_status}</span>` : ""}${f.source === "ai" ? `<span class="tag ai" title="Found by AI; confidence ${Math.round(f.confidence * 100)}%">AI ${Math.round(f.confidence * 100)}%</span>` : `<span class="tag rule" title="Found by an exact rule">Rule</span>`}</span></div>
    <div class="f-why">${esc(f.explanation)}</div>
    ${learnNote ? `<div class="learn-note small"><span class="learn-dot"></span>${esc(learnNote)}</div>` : ""}
    <div class="f-cite ${f.cite_type === "fact" ? "fact" : ""}" data-toggle><b>${src}</b> ${esc(f.cite_text)}</div>
    ${fixShown != null && quoteable ? `<div class="f-fix"><span class="diff-del">${esc(f.quote)}</span><span class="arrow">→</span>${fixShown === "" ? '<span class="muted">remove</span>' : `<span class="diff-ins">${esc(fixShown)}</span>`}</div>` : ""}
    ${f.decision ? `<div class="f-actions"><span class="decision ${f.decision}">${{ accepted: "✓ Accepted", edited: "✓ Edited", disputed: "⚑ Disputed" }[f.decision]}</span>${f.decision_note ? `<span class="small muted">“${esc(f.decision_note)}”</span>` : ""}<span class="spacer"></span>${editable ? `<button class="btn-ghost btn-sm" data-undo="${f.id}">Undo</button>` : `<span class="small muted">by ${esc(f.decided_by)}</span>`}</div>`
    : editable ? `<div class="f-actions"><span class="spacer"></span>
        <button class="btn-sm" data-dispute="${f.id}">Dispute</button>
        ${quoteable ? `<button class="btn-sm" data-edit="${f.id}">Edit</button>` : ""}
        ${fixShown != null && quoteable ? `<button class="btn-sm btn-good" data-accept="${f.id}">Accept fix</button>` : `<button class="btn-sm btn-good" data-ack="${f.id}">Mark resolved</button>`}
      </div><div class="slot"></div>` : `<div class="f-actions"><span class="small muted">Open</span></div>`}
  </div>`;
}
function bindFindings(d, editable) {
  const byId = Object.fromEntries(d.findings.map(f => [f.id, f]));
  app.querySelectorAll("mark.hl").forEach(m => m.onclick = () => focusFinding(m.dataset.f));
  app.querySelectorAll("[data-toggle]").forEach(c => c.onclick = () => c.classList.toggle("open"));
  if ($("#firstCheck")) $("#firstCheck").onclick = e => busy(e.currentTarget, () => withChecking(async () => { renderDraft(await api("POST", `/api/drafts/${d.draft.id}/check`)); enter(); }), "Checking…");
  if (!editable) return;
  const decide = async (id, body) => {
    await api("POST", `/api/findings/${id}/decision`, body);
    const y = window.scrollY; renderDraft(await api("GET", `/api/drafts/${d.draft.id}`)); window.scrollTo(0, y);
    const card = $("#f-" + id); if (card && body.decision && !REDUCED) card.classList.add("just-decided");
    setTimeout(() => focusNext(), 450);
  };
  app.querySelectorAll("[data-accept]").forEach(b => b.onclick = () => busy(b, () => decide(b.dataset.accept, { decision: "accepted" }), "Saving…"));
  app.querySelectorAll("[data-ack]").forEach(b => b.onclick = () => busy(b, () => decide(b.dataset.ack, { decision: "accepted" }), "Saving…"));
  app.querySelectorAll("[data-undo]").forEach(b => b.onclick = () => busy(b, () => decide(b.dataset.undo, { decision: null }), "…"));
  app.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
    const f = byId[b.dataset.edit]; const slot = b.closest(".finding").querySelector(".slot");
    slot.innerHTML = `<div class="inline-form"><input value="${esc(f.fix_text ?? f.quote)}"><button class="btn-sm btn-primary">Save</button></div>`;
    const inp = slot.querySelector("input"); inp.focus();
    slot.querySelector("button").onclick = e => busy(e.currentTarget, () => decide(f.id, { decision: "edited", edited_fix: inp.value }), "Saving…");
  });
  app.querySelectorAll("[data-dispute]").forEach(b => b.onclick = () => {
    const slot = b.closest(".finding").querySelector(".slot");
    slot.innerHTML = `<div class="inline-form"><input placeholder="Why is this OK? (seen by the reviewer)"><button class="btn-sm btn-primary">Dispute</button></div>`;
    const inp = slot.querySelector("input"); inp.focus();
    slot.querySelector("button").onclick = e => busy(e.currentTarget, () => decide(b.dataset.dispute, { decision: "disputed", note: inp.value }), "Saving…");
  });
  if ($("#acceptAll")) $("#acceptAll").onclick = e => busy(e.currentTarget, async () => {
    for (const f of d.findings.filter(x => !x.decision)) await api("POST", `/api/findings/${f.id}/decision`, { decision: "accepted" });
    renderDraft(await api("GET", `/api/drafts/${d.draft.id}`)); toast("All remaining fixes accepted");
  }, "Accepting…");
}
function focusFinding(id) {
  app.querySelectorAll(".finding.active, mark.active").forEach(x => x.classList.remove("active"));
  const card = $("#f-" + id); if (card) { card.classList.add("active"); card.scrollIntoView({ behavior: "smooth", block: "center" }); }
  const m = app.querySelector(`mark[data-f="${id}"]`); if (m) m.classList.add("active");
}
function focusNext() { const nxt = app.querySelector(".finding:not(.decided)"); if (nxt) nxt.scrollIntoView({ behavior: "smooth", block: "center" }); }
function editMode(draft, cur) {
  $("#docArea").innerHTML = `<textarea id="editText" style="min-height:220px">${esc(cur.text)}</textarea>
    ${cur.image_b64 ? `<label class="field"><span>Alt text</span><input id="editAlt" value="${esc(cur.alt_text || "")}"></label>` : ""}
    <div class="row"><button class="btn-primary" id="saveEdit">Save and re-check</button><button id="cancelEdit">Cancel</button></div>`;
  $("#editText").focus();
  $("#cancelEdit").onclick = () => draftView(draft.id);
  $("#saveEdit").onclick = e => busy(e.currentTarget, () => withChecking(async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/versions`, { text: $("#editText").value, alt_text: $("#editAlt") ? $("#editAlt").value : null })); enter(); }), "Saving and checking…");
}
function wordDiff(a, b) {
  const A = a.split(/(\s+)/), B = b.split(/(\s+)/);
  if (A.length * B.length > 400000) return esc(b);
  const dp = Array.from({ length: A.length + 1 }, () => new Uint16Array(B.length + 1));
  for (let i = A.length - 1; i >= 0; i--) for (let j = B.length - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  let i = 0, j = 0, out = "";
  while (i < A.length && j < B.length) {
    if (A[i] === B[j]) { out += esc(A[i]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out += A[i].trim() ? `<span class="diff-del">${esc(A[i])}</span>` : esc(A[i]); i++; }
    else { out += B[j].trim() ? `<span class="diff-ins">${esc(B[j])}</span>` : esc(B[j]); j++; }
  }
  while (i < A.length) { out += A[i].trim() ? `<span class="diff-del">${esc(A[i])}</span>` : ""; i++; }
  while (j < B.length) { out += B[j].trim() ? `<span class="diff-ins">${esc(B[j])}</span>` : esc(B[j]); j++; }
  return out;
}

/* ---------------- rulebook ---------------- */
async function rulebook() {
  loading("Loading rulebook…");
  const [rb, gp, vh] = await Promise.all([api("GET", "/api/rulebook?brand_id=" + S.brandId),
    api("GET", "/api/rulebook/gaps?brand_id=" + S.brandId), api("GET", "/api/rulebook/versions?brand_id=" + S.brandId)]);
  const canEdit = ["admin", "manager"].includes(S.me.role);
  const sections = {};
  rb.clauses.forEach(c => (sections[c.section] = sections[c.section] || []).push(c));
  const drafts = rb.clauses.filter(c => c.status !== "confirmed").length;
  const today = new Date().toISOString().slice(0, 10);
  app.innerHTML = `
  <div class="page-head"><div><h1>Rulebook · ${esc(rb.brand.name)} <span class="ver-badge" title="Every change saves a new version">v${vh.current}</span></h1><p class="muted">${rb.clauses.length} clauses, ${rb.facts.length} approved facts, ${rb.terms.length} terms. Every finding cites one of these.</p></div>
    <div class="row"><button class="btn-sm" id="histToggle">Version history</button>${canEdit ? `<button class="btn-primary" id="importToggle">Import a guideline PDF</button>` : ""}</div></div>
  <div class="panel" id="histPanel" hidden><h2>Version history</h2>
    <div class="ver-list">${vh.versions.map(v => `<button class="ver-item" data-ver="${v.version}"><b>v${v.version}</b><span>${esc(v.note || "")}</span><span class="muted small">${esc(v.actor || "")} · ${ago(v.created_at)}</span></button>`).join("")}</div>
    <div id="verDiff" class="small muted">Pick a version to see what changed.</div></div>
  ${gapsHtml(gp, canEdit)}
  ${!canEdit ? `<div class="warn">Switch <b>Role</b> to Admin or Manager to edit clauses or import a new guideline.</div>` : ""}
  <div class="panel" id="importPanel" hidden>
    <h2>Import a brand guideline</h2>
    <p class="muted small">Upload any guideline PDF (or paste the text). Brandproof splits it into numbered clauses, classifies each as an exact rule or an AI-judged rule, and extracts banned or required terms. It is added as a new brand for you to review and confirm.</p>
    <label class="field"><span>Brand name</span><input id="impName" placeholder="e.g. Acme Foods"></label>
    <label class="field"><span>Guideline PDF</span><span class="drop"><input id="impPdf" type="file" accept="application/pdf"><span class="drop-text" data-for="impPdf">Click to add a guideline PDF</span></span></label>
    <label class="field"><span>…or paste guideline text</span><textarea id="impText" placeholder="1 Voice&#10;1.1 Be friendly and clear.&#10;1.2 Never use more than 2 emoji."></textarea></label>
    <button class="btn-primary" id="impBtn">Import and create rule cards</button>
  </div>
  ${drafts ? `<div class="warn">${drafts} clauses were imported and need review. Edit any that look wrong, then confirm. Only confirmed clauses are used in checks. ${canEdit ? `<button class="btn-sm btn-primary" id="confirmAll">Confirm all</button>` : ""}</div>` : ""}
  <div class="grid-2">
    <div class="panel"><h2>Guideline clauses</h2>
      ${Object.entries(sections).map(([sec, cs]) => `<div class="section-title">${esc(sec)}</div>${cs.map(c => clauseHtml(c, canEdit)).join("")}`).join("")}
    </div>
    <div>
      <div class="panel"><h2>Approved facts</h2><p class="muted small">Claims in drafts are matched against these.</p>
        <table><thead><tr><th>Code</th><th>Fact</th><th>Valid until</th></tr></thead><tbody>${rb.facts.map(f => `<tr><td><b>${esc(f.code)}</b></td><td><b>${esc(f.fkey)}</b><div class="small">${esc(f.value)}</div><div class="muted small">${esc(f.source || "")}</div></td><td class="small ${f.valid_until && f.valid_until < today ? "expired" : ""}">${f.valid_until ? esc(f.valid_until) + (f.valid_until < today ? " (expired)" : "") : "—"}</td></tr>`).join("") || `<tr><td colspan="3" class="muted">No facts yet.</td></tr>`}</tbody></table>
        ${canEdit ? `<details style="margin-top:.6rem"><summary class="small"><b>Add a fact</b></summary>
          <label class="field"><span>Fact</span><input id="factKey" placeholder="e.g. Glow serum price"></label>
          <label class="field"><span>Approved value</span><input id="factVal" placeholder="e.g. ₹649 for 30 ml"></label>
          <label class="field"><span>Valid until (optional)</span><input id="factUntil" type="date"></label>
          <button class="btn-sm btn-primary" id="factBtn">Add fact</button></details>` : ""}
      </div>
      <div class="panel"><h2>Terms</h2>
        <table><thead><tr><th>Term</th><th>Type</th><th>Use instead</th></tr></thead><tbody>${rb.terms.map(t => `<tr><td>${esc(t.term)}</td><td class="small">${esc(t.kind.replace("_", " "))}</td><td>${esc(t.replacement)} <span class="muted small">(${esc(t.clause_code)})</span></td></tr>`).join("") || `<tr><td colspan="3" class="muted">No terms.</td></tr>`}</tbody></table>
      </div>
      <div class="panel"><h2>Palette</h2><div class="swatches">${(rb.brand.palette || []).map(p => `<span class="swatch"><i style="background:${esc(p.hex)}"></i>${esc(p.name)} <span class="muted">${esc(p.hex)}</span></span>`).join("") || '<span class="muted">No palette.</span>'}</div></div>
    </div>
  </div>`;
  if ($("#importToggle")) $("#importToggle").onclick = () => { $("#importPanel").hidden = !$("#importPanel").hidden; };
  $("#histToggle").onclick = () => { $("#histPanel").hidden = !$("#histPanel").hidden; };
  app.querySelectorAll("[data-ver]").forEach(b => b.onclick = async () => {
    app.querySelectorAll("[data-ver]").forEach(x => x.classList.toggle("on", x === b));
    try { $("#verDiff").innerHTML = diffHtml(await api("GET", `/api/rulebook/versions/${b.dataset.ver}?brand_id=${S.brandId}`)); }
    catch (e) { $("#verDiff").textContent = e.message; }
  });
  bindGaps(gp);
  if ($("#impBtn")) $("#impBtn").onclick = e => busy(e.currentTarget, async () => {
    const f = $("#impPdf").files[0];
    const body = { name: $("#impName").value || "Imported brand", text: $("#impText").value, pdf_b64: f ? await fileB64(f) : null };
    const r = await api("POST", "/api/rulebook/import", body);
    await loadMe(); S.brandId = r.brand_id; store.set("bp_brand", r.brand_id); $("#brandSelect").value = r.brand_id;
    toast(`Imported ${r.clauses} clauses and ${r.terms} terms${r.used_ai ? "" : " (AI classification unavailable, used rules)"}`); rulebook();
  }, "Importing…");
  if ($("#confirmAll")) $("#confirmAll").onclick = e => busy(e.currentTarget, async () => { await api("POST", "/api/rulebook/confirm-all?brand_id=" + S.brandId); rulebook(); }, "Confirming…");
  if ($("#factBtn")) $("#factBtn").onclick = e => busy(e.currentTarget, async () => { await api("POST", "/api/facts?brand_id=" + S.brandId, { fkey: $("#factKey").value, value: $("#factVal").value, valid_until: $("#factUntil").value || null }); rulebook(); }, "Adding…");
  app.querySelectorAll("[data-editc]").forEach(b => b.onclick = () => {
    const box = b.closest(".clause"); const c = rb.clauses.find(x => x.id === b.dataset.editc);
    box.innerHTML = `<textarea style="min-height:90px">${esc(c.text)}</textarea><div class="row" style="margin-top:.4rem"><select style="width:auto"><option value="exact" ${c.kind === "exact" ? "selected" : ""}>Exact rule</option><option value="judgement" ${c.kind === "judgement" ? "selected" : ""}>AI-judged</option></select><button class="btn-sm btn-primary">Save</button></div>`;
    box.querySelector("button").onclick = e => busy(e.currentTarget, async () => { await api("PATCH", "/api/clauses/" + c.id, { text: box.querySelector("textarea").value, kind: box.querySelector("select").value, status: "confirmed" }); toast("Clause saved"); rulebook(); });
  });
}
function clauseHtml(c, canEdit) {
  return `<div class="clause"><div class="row"><span class="code">${esc(c.code)}</span><b>${esc(c.title)}</b><span class="spacer"></span>
    ${c.kind === "exact" ? `<span class="pill rule" title="Checked by code${c.check_type ? ": " + c.check_type : ""}">Exact rule</span>` : `<span class="pill ai" title="Checked by AI, which must cite this clause">AI-judged${c.visual ? " · image" : ""}</span>`}
    ${c.status !== "confirmed" ? `<span class="pill in_review">Needs review</span>` : ""}
    ${canEdit ? `<button class="btn-ghost btn-sm" data-editc="${c.id}">Edit</button>${c.kind === "judgement" ? `<button class="btn-ghost btn-sm" data-clarify="${esc(c.code)}" title="Ask the AI for clearer wording with do/don't examples">Clarify</button>` : ""}` : ""}</div>
    <p class="small" style="margin:.3rem 0 0">${esc(c.text)}</p></div>`;
}

/* guideline-gap assistant (improvement 3) */
function gapsHtml(gp, canEdit) {
  const list = gp.candidates;
  return `<div class="panel gaps" id="gapsPanel"><div class="iss-head"><h2>Guideline gaps</h2><span class="muted small">${list.length ? `${list.length} guideline${list.length > 1 ? "s" : ""} look unclear` : ""}</span></div>
    <p class="muted small">Often-disputed guidelines get a clearer rewrite with do/don't examples. Nothing changes until an admin approves.</p>
    ${list.length ? list.map(g => `<div class="gap" data-gap="${esc(g.code)}">
        <div class="row"><span class="code">${esc(g.code)}</span><b>${esc(g.title)}</b><span class="spacer"></span>${canEdit && !g.suggestion ? `<button class="btn-sm btn-primary" data-suggest="${esc(g.code)}" data-reason="${esc(g.reason)}">Suggest clearer wording</button>` : ""}</div>
        <p class="small gap-why">${esc(g.reason)}</p>
        <div class="slot">${g.suggestion ? suggestionHtml(g.suggestion, canEdit) : ""}</div></div>`).join("")
      : `<div class="empty small">None yet.${canEdit ? " Click <b>Clarify</b> on any AI-judged guideline below to try it." : ""}</div>`}
    <div id="gapAdhoc"></div>
    ${gp.recent.length ? `<details class="small" style="margin-top:.6rem"><summary>Recent decisions (${gp.recent.length})</summary>${gp.recent.map(r => `<div class="hidden-item"><b>${esc(r.code)}</b> ${r.status === "approved" ? `<span class="good">approved → v${r.version}</span>` : `<span class="muted">rejected</span>`} by ${esc(r.decided_by || "")}<div class="muted">${esc(r.new_text)}</div></div>`).join("")}</details>` : ""}
    </div>`;
}
function suggestionHtml(sg, canEdit) {
  return `<div class="suggestion" data-sid="${sg.id}">
    <div class="sg-cols"><div><div class="sg-label">Current</div><p class="small diff-del-block">${esc(sg.old_text)}</p></div>
      <div><div class="sg-label">Suggested</div>${canEdit ? `<textarea class="sg-text">${esc(sg.new_text)}</textarea>` : `<p class="small">${esc(sg.new_text)}</p>`}</div></div>
    <div class="sg-cols"><div><div class="sg-label good">Do</div>${canEdit ? `<textarea class="sg-do" rows="3">${esc(sg.do_examples.join("\n"))}</textarea>` : sg.do_examples.map(x => `<div class="small">✓ ${esc(x)}</div>`).join("")}</div>
      <div><div class="sg-label bad">Don't</div>${canEdit ? `<textarea class="sg-dont" rows="3">${esc(sg.dont_examples.join("\n"))}</textarea>` : sg.dont_examples.map(x => `<div class="small">✗ ${esc(x)}</div>`).join("")}</div></div>
    ${sg.why ? `<p class="small muted">${esc(sg.why)} <span class="tag ai">${esc((sg.model || "").split(":").pop())}</span></p>` : ""}
    ${canEdit ? `<div class="row"><label class="small chk"><input type="checkbox" class="sg-reset" checked> Reset learning history for this guideline</label><span class="spacer"></span>
      <button class="btn-sm" data-sgno="${sg.id}">Reject</button><button class="btn-sm btn-good" data-sgyes="${sg.id}">Approve → new version</button></div>` : ""}</div>`;
}
function bindGaps(gp) {
  const lines = el => el.value.split("\n").map(x => x.trim()).filter(Boolean);
  const bindSuggestion = box => {
    const yes = box.querySelector("[data-sgyes]"), no = box.querySelector("[data-sgno]");
    if (yes) yes.onclick = e => busy(e.currentTarget, async () => {
      const r = await api("POST", `/api/rulebook/suggestions/${yes.dataset.sgyes}/decision`, { approve: true, brand_id: S.brandId,
        text: box.querySelector(".sg-text").value, do_examples: lines(box.querySelector(".sg-do")), dont_examples: lines(box.querySelector(".sg-dont")),
        reset_history: box.querySelector(".sg-reset").checked });
      toast(`Guideline updated · rulebook v${r.version}`); rulebook();
    }, "Saving…");
    if (no) no.onclick = e => busy(e.currentTarget, async () => {
      await api("POST", `/api/rulebook/suggestions/${no.dataset.sgno}/decision`, { approve: false, brand_id: S.brandId });
      toast("Suggestion rejected"); rulebook();
    }, "Saving…");
  };
  app.querySelectorAll(".suggestion").forEach(bindSuggestion);
  const ask = async (btn, code, reason, slot) => busy(btn, async () => {
    const sg = await api("POST", "/api/rulebook/gaps/suggest", { code, reason, brand_id: S.brandId });
    slot.innerHTML = suggestionHtml(sg, true); bindSuggestion(slot.querySelector(".suggestion")); enter(slot);
    if (btn.dataset.suggest) btn.remove();
  }, "Thinking…");
  app.querySelectorAll("[data-suggest]").forEach(b => b.onclick = () => ask(b, b.dataset.suggest, b.dataset.reason, b.closest(".gap").querySelector(".slot")));
  app.querySelectorAll("[data-clarify]").forEach(b => b.onclick = () => {
    const code = b.dataset.clarify, slot = $("#gapAdhoc");
    slot.innerHTML = `<div class="gap"><div class="row"><span class="code">${esc(code)}</span><b>Requested rewrite</b></div><div class="slot"></div></div>`;
    $("#gapsPanel").scrollIntoView({ behavior: "smooth", block: "start" });
    ask(b, code, "An admin asked for clearer wording.", slot.querySelector(".slot"));
  });
}
function diffHtml(d) {
  if (!d.changes.length) return `<p><b>v${d.version}</b> · ${esc(d.note || "")} · no rule changes recorded.</p>`;
  return `<p><b>v${d.version}</b>${d.previous ? ` vs v${d.previous}` : ""} · ${esc(d.note || "")} · ${esc(d.actor || "")}, ${ago(d.created_at)}</p>
    ${d.changes.slice(0, 40).map(c => `<div class="vchange"><span class="pill ${c.type === "removed" ? "in_review" : "rule"}">${c.type}</span> <b>${esc(c.what)} ${esc(c.code)}</b>
      ${c.old ? `<div class="diff-del-block">${esc(c.old)}</div>` : ""}${c.new ? `<div class="diff-ins-block">${esc(c.new)}</div>` : ""}</div>`).join("")}
    ${d.changes.length > 40 ? `<p class="muted">…and ${d.changes.length - 40} more.</p>` : ""}`;
}

/* ---------------- insights ---------------- */
async function insights() {
  loading("Loading insights…");
  const i = await api("GET", "/api/insights");
  const max = Math.max(1, ...i.by_category.map(c => c.count));
  const ds = i.drafts_by_status;
  app.innerHTML = `
  <div class="page-head"><div><h1>Insights</h1><p class="muted">Recurring mistakes and guidelines that people find unclear, from every check in this workspace.</p></div></div>
  <div class="kpis">
    <div class="kpi"><b>${i.checks.count}</b><span>checks run</span></div>
    <div class="kpi"><b>${i.total_findings}</b><span>issues found</span></div>
    <div class="kpi"><b>${(ds.approved || 0)}</b><span>drafts approved</span></div>
    <div class="kpi"><b>${i.checks.dropped_uncited}</b><span>uncited AI flags blocked</span></div>
  </div>
  ${!i.total_findings ? `<div class="panel empty">No checks yet. <a href="#/new">Run a few samples</a> and come back.</div>` : `
  <div class="grid-2">
    <div class="panel"><h2>Issues by type</h2>${i.by_category.map(c => `<div class="bar"><span>${CAT[c.category] || c.category}</span><div class="track"><div class="fill" style="width:${(c.count / max) * 100}%"></div></div><b>${c.count}</b></div>`).join("")}
      <p class="muted small" style="margin-top:.8rem">${i.by_source.rule || 0} found by exact rules · ${i.by_source.ai || 0} by AI with citations · average check ${(i.checks.avg_ms / 1000).toFixed(1)} s</p></div>
    <div class="panel"><h2>Possibly unclear guidelines</h2><p class="muted small">Clauses that creators dispute often. Consider rewriting them with clearer examples.</p>
      ${i.unclear_clauses.length ? i.unclear_clauses.map(c => `<div class="clause"><span class="code">${esc(c.code)}</span><b>${c.disputed} of ${c.count} flags disputed</b><p class="small" style="margin:.3rem 0 0">${esc(c.text)}</p></div>`).join("") : `<p class="muted">No clause has been disputed often yet. Dispute a finding on a draft to see it here.</p>`}
    </div>
  </div>
  <div class="panel"><h2>Most-broken guidelines</h2>
    <table><thead><tr><th>Clause / fact</th><th>Flags</th><th>Accepted</th><th>Disputed</th></tr></thead><tbody>${i.top_clauses.map(c => `<tr><td><b>${esc(c.code)}</b> <span class="small">${esc((c.text || "").slice(0, 110))}${(c.text || "").length > 110 ? "…" : ""}</span></td><td>${c.count}</td><td>${c.accepted}</td><td>${c.disputed}</td></tr>`).join("")}</tbody></table></div>`}`;
}

/* ---------------- evaluation ---------------- */
async function evaluation() {
  loading();
  const [allCases, last, exp, indic] = await Promise.all([api("GET", "/api/eval/cases"), api("GET", "/api/eval/latest"), api("GET", "/api/eval/latest?kind=experiment"), api("GET", "/api/eval/latest?kind=indic")]);
  const cases = allCases.filter(c => c.set === "main"), icases = allCases.filter(c => c.set === "indic");
  app.innerHTML = `
  <div class="page-head"><div><h1>Evaluation</h1><p class="muted">Accuracy on ${cases.length} hand-labelled drafts (${cases.reduce((a, c) => a + c.expected, 0)} known issues). <span class="tip" title="A flag is correct if it matches a labelled issue of the same type at the same place. Precision = share of flags that were right. Recall = share of real issues caught.">How it's scored</span></p></div>
    <button class="btn-primary" id="runEval">Run evaluation</button></div>
  <div id="evalProgress"></div>
  <div id="evalOut">${last ? publishedNote(last.results) + evalReport(last.results, last.ran_at) : `<div class="panel empty">Not run yet. Click <b>Run evaluation</b> (2–4 min).</div>`}</div>
  <div class="panel exp"><div class="iss-head"><h2>Learning: before vs after</h2>
      <button class="btn-sm" id="runExp">Run experiment</button></div>
    <p class="small muted">Learns from 12 labelled drafts, then tested on 18 drafts it never saw. 4–6 min.</p>
    <div id="expProgress"></div><div id="expOut">${publishedNote(exp && exp.results)}${experimentReport(exp && exp.results, exp && exp.ran_at)}</div></div>
  <div class="panel exp indic"><div class="iss-head"><h2>Tamil, Hindi, Tanglish, Hinglish</h2>
      <button class="btn-sm" id="runIndic">Run language evaluation</button></div>
    <p class="small muted">${icases.length} labelled drafts (${icases.reduce((a, c) => a + c.expected, 0)} known issues) against the same English rulebook. 2–3 min.</p>
    <div id="indicProgress"></div></div>
  <div id="indicOut">${indic ? publishedNote(indic.results) + evalReport(indic.results, indic.ran_at, true) : ""}</div>
  <details class="small muted owner"><summary>Team only: publish these results for every visitor</summary>
    <div class="row"><input id="pubCode" type="password" placeholder="Publish code" autocomplete="off"><button class="btn-sm" id="pubBtn">Publish</button></div></details>`;
  $("#pubBtn").onclick = e => busy(e.currentTarget, async () => {
    const r = await api("POST", "/api/eval/publish", { code: $("#pubCode").value });
    toast(r.published.length ? `Published: ${r.published.join(", ")}` : "Nothing to publish yet: run the evaluations first");
  }, "Publishing…");
  $("#runIndic").onclick = e => busy(e.currentTarget, async () => {
    const prog = $("#indicProgress"); let done = 0;
    const results = await pool(icases, 1, async c => {
      let r; try { r = await evalCase(c.id); } catch (err) { r = { id: c.id, title: c.title, lang: c.lang, error: err.message, tp: 0, fp: 0, fn: c.expected, by_cat: {}, missed: [], predicted: [] }; }
      done++; prog.innerHTML = `<div class="progress"><div style="width:${(done / icases.length) * 100}%"></div></div><span class="small muted">Checked ${done} of ${icases.length}</span>`;
      return r;
    });
    prog.innerHTML = "";
    const summary = { kind: "indic", cases: results };
    await api("POST", "/api/eval/runs", { results: summary });
    $("#indicOut").innerHTML = evalReport(summary, new Date().toISOString(), true); enter($("#indicOut"));
  }, "Running…");
  $("#runExp").onclick = e => busy(e.currentTarget, async () => {
    const r = await runExperiment(cases, $("#expProgress"));
    $("#expOut").innerHTML = experimentReport(r, new Date().toISOString()); enter($("#expOut"));
  }, "Running…");
  $("#runEval").onclick = e => busy(e.currentTarget, async () => {
    const results = []; const prog = $("#evalProgress");
    for (let k = 0; k < cases.length; k++) {
      prog.innerHTML = `<div class="progress"><div style="width:${(k / cases.length) * 100}%"></div></div><span class="small muted">Checking ${k + 1} of ${cases.length}: ${esc(cases[k].title)}</span>`;
      try { results.push(await evalCase(cases[k].id)); } catch (err) { results.push({ id: cases[k].id, title: cases[k].title, error: err.message, tp: 0, fp: 0, fn: cases[k].expected, by_cat: {}, missed: [], predicted: [] }); }
    }
    prog.innerHTML = "";
    const summary = { cases: results };
    await api("POST", "/api/eval/runs", { results: summary });
    $("#evalOut").innerHTML = evalReport(summary, new Date().toISOString()); enter($("#evalOut"));
  }, "Running…");
}
function publishedNote(res) {
  return res && res.published_from ? `<p class="small pub-note">Saved results from the team's last full run (${new Date(res.published_from).toLocaleString()}). Click Run to measure it yourself, live.</p>` : "";
}
function evalReport(res, at, byLang) {
  const cases = res.cases; const cats = {};
  let tp = 0, fp = 0, fn = 0, dropped = 0, aiFail = 0;
  for (const c of cases) {
    tp += c.tp; fp += c.fp; fn += c.fn; dropped += c.dropped_uncited || 0; if (c.ai_status && c.ai_status !== "ok") aiFail++;
    for (const [k, v] of Object.entries(c.by_cat || {})) { const x = (cats[k] = cats[k] || { tp: 0, fp: 0, fn: 0 }); x.tp += v.tp; x.fp += v.fp; x.fn += v.fn; }
  }
  const P = (a, b) => (a + b ? (100 * a) / (a + b) : 100);
  const fmt = v => `${v.toFixed(0)}%`;
  const pr = P(tp, fp), rc = P(tp, fn), f1 = pr + rc ? (2 * pr * rc) / (pr + rc) : 0;
  return `
  <div class="kpis">
    <div class="kpi"><b class="score">${fmt(pr)}</b><span>precision (flags that were right)</span></div>
    <div class="kpi"><b class="score">${fmt(rc)}</b><span>recall (real issues caught)</span></div>
    <div class="kpi"><b class="score">${fmt(f1)}</b><span>F1 score</span></div>
    <div class="kpi"><b>${dropped}</b><span>uncited AI flags blocked by the gate</span></div>
  </div>
  ${aiFail ? `<div class="warn">${aiFail} case(s) ran without AI (provider unavailable), so tone, legal and fact checks are under-counted.</div>` : ""}
  <div class="grid-2">
    ${byLang ? `<div class="panel"><h2>By language</h2><table><thead><tr><th>Language</th><th>Drafts</th><th>Precision</th><th>Recall</th><th>Caught</th><th>Missed</th><th>False alarms</th></tr></thead><tbody>
      ${Object.entries(cases.reduce((m, c) => { const x = (m[c.lang || "Other"] = m[c.lang || "Other"] || { n: 0, tp: 0, fp: 0, fn: 0 }); x.n++; x.tp += c.tp; x.fp += c.fp; x.fn += c.fn; return m; }, {})).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.n}</td><td>${fmt(P(v.tp, v.fp))}</td><td>${fmt(P(v.tp, v.fn))}</td><td>${v.tp}</td><td>${v.fn}</td><td>${v.fp}</td></tr>`).join("")}</tbody></table></div>` : ""}
    <div class="panel"><h2>By issue type</h2><table><thead><tr><th>Type</th><th>Precision</th><th>Recall</th><th>Caught</th><th>Missed</th><th>False alarms</th></tr></thead><tbody>
      ${Object.entries(cats).sort().map(([k, v]) => `<tr><td>${CAT[k] || k}</td><td>${fmt(P(v.tp, v.fp))}</td><td>${fmt(P(v.tp, v.fn))}</td><td>${v.tp}</td><td>${v.fn}</td><td>${v.fp}</td></tr>`).join("")}</tbody></table>
      <p class="muted small">Run ${ago(at)} on ${cases.length} drafts.</p></div>
    <div class="panel"><h2>Per draft</h2><table><thead><tr><th>Draft</th><th>Caught</th><th>Missed</th><th>False</th></tr></thead><tbody>
      ${cases.map(c => `<tr><td>${esc(c.title)}${c.missed?.length ? `<div class="muted small">Missed: ${c.missed.map(m => `${CAT[m.category] || m.category} ${m.quote === "*" ? "(whole draft)" : `“${esc(m.quote)}”`}`).join("; ")}</div>` : ""}${(c.predicted || []).some(p => !p.correct) ? `<div class="small fa">False alarms: ${c.predicted.filter(p => !p.correct).map(p => `${CAT[p.category] || p.category} ${p.quote === "[image]" ? "(image)" : `“${esc(p.quote)}”`} <span class="muted">(${esc(p.cite_code || "")}, ${p.source === "ai" ? "AI " + Math.round((p.confidence || 0) * 100) + "%" : "rule"})</span>`).join("; ")}</div>` : ""}${c.error ? `<div class="bad small">${esc(c.error)}</div>` : ""}</td><td>${c.tp}</td><td class="${c.fn ? "bad" : ""}">${c.fn}</td><td class="${c.fp ? "bad" : ""}">${c.fp}</td></tr>`).join("")}</tbody></table></div>
  </div>`;
}

/* ---------------- learning from reviewer decisions ---------------- */
const MODE = {
  trusted: ["Trusted", "Reviewers almost always accept these flags."],
  normal: ["Normal", "Not enough history to change anything yet."],
  softened: ["Softened", "Often disputed: findings are shown as low severity."],
  muted: ["Muted", "AI flags for this guideline are hidden until an admin reviews it."],
  off: ["Ignoring history", "An admin switched learning off for this guideline."],
};
async function learningPage() {
  loading("Loading what Brandproof has learned…");
  const L = await api("GET", "/api/learning?brand_id=" + (S.brandId || ""));
  const canAdmin = ["admin", "manager"].includes(S.me.role);
  const counts = {}; L.clauses.forEach(c => (counts[c.mode] = (counts[c.mode] || 0) + 1));
  app.innerHTML = `
  <div class="page-head"><div><h1>Learning</h1><p class="muted">Every Accept, Edit and Dispute teaches Brandproof what your reviewers count as a real problem.</p></div>
    ${canAdmin ? `<label class="switch"><input type="checkbox" id="learnAll" ${L.enabled ? "checked" : ""}><span>Learning ${L.enabled ? "on" : "off"}</span></label>` : ""}</div>
  <div class="kpis">
    <div class="kpi"><b>${L.decisions}</b><span>decisions learned from${L.calibration_decisions ? ` (${L.calibration_decisions} from training drafts)` : ""}</span></div>
    <div class="kpi"><b>${L.ai_threshold ? Math.round(L.ai_threshold * 100) + "%" : "–"}</b><span>learned AI confidence cut-off</span></div>
    <div class="kpi"><b>${counts.softened || 0} / ${counts.muted || 0}</b><span>guidelines softened / muted</span></div>
    <div class="kpi"><b>${counts.trusted || 0}</b><span>guidelines trusted</span></div>
  </div>
  <details class="panel how-learn"><summary><b>How it learns</b></summary><ol class="small">
    <li><b>Per guideline:</b> disputed in half or more of 2+ decisions → <b>softened</b> to low severity. AI flags disputed in 80%+ of 4+ decisions → <b>muted</b>. Exact rule checks are never hidden, only softened.</li>
    <li><b>Confidence cut-off:</b> from past AI decisions it picks the minimum confidence that keeps the most accepted flags and drops the most disputed ones.</li>
    <li><b>Examples for the AI:</b> up to 3 recent accepted and disputed cases per guideline are added to the AI prompt, so the model follows your reviewers' judgement.</li>
    <li><b>No repeats:</b> text that reviewers already disputed for a guideline (and never accepted) isn't flagged again.</li>
    <li><b>Always visible:</b> hidden flags are listed under each check, and admins or managers can switch learning off for any guideline.</li></ol></details>
  ${!L.clauses.length ? `<div class="panel empty">Nothing learned yet. Accept or dispute a few issues, or run the <a href="#/eval">learning experiment</a>.</div>` : `
  <div class="panel"><h2>What it learned, per guideline</h2>
    <table class="learn-table"><thead><tr><th>Guideline / fact</th><th>Accepted</th><th>Disputed</th><th>Disputed share</th><th>Effect</th>${canAdmin ? "<th></th>" : ""}</tr></thead><tbody>
    ${L.clauses.map(c => `<tr>
      <td><b>${esc(c.code)}</b> <span class="small">${esc((c.text || "").slice(0, 90))}${(c.text || "").length > 90 ? "…" : ""}</span>
        ${c.examples.length ? `<details class="small ex"><summary>${c.examples.length} example${c.examples.length > 1 ? "s" : ""}</summary>${c.examples.map(e => `<div class="${e.decision}">${e.decision === "disputed" ? "⚑ Disputed" : "✓ Accepted"}: “${esc(e.quote)}”${e.note ? ` <span class="muted">(${esc(e.note)})</span>` : ""}</div>`).join("")}</details>` : ""}</td>
      <td>${c.accepted}</td><td>${c.disputed}</td>
      <td><div class="mini-track"><div style="width:${Math.round(c.dispute_rate * 100)}%"></div></div><span class="small">${Math.round(c.dispute_rate * 100)}%</span></td>
      <td><span class="mode mode-${c.mode}" title="${esc(MODE[c.mode][1])}">${MODE[c.mode][0]}</span></td>
      ${canAdmin ? `<td class="nowrap"><button class="btn-ghost btn-sm" data-lt="${esc(c.code)}" data-on="${c.enabled ? 0 : 1}">${c.enabled ? "Ignore history" : "Use history"}</button><button class="btn-ghost btn-sm" data-lr="${esc(c.code)}">Reset</button></td>` : ""}
    </tr>`).join("")}</tbody></table>
    ${canAdmin ? "" : `<p class="small muted">Switch Role to Manager or Admin to change learning settings.</p>`}</div>`}`;
  const after = async (fn, msg) => { try { await fn(); toast(msg); learningPage(); } catch (e) { toast(e.message, true); } };
  const all = $("#learnAll");
  if (all) all.onchange = () => after(() => api("POST", "/api/learning/settings", { code: "*", enabled: all.checked, brand_id: S.brandId }), all.checked ? "Learning switched on" : "Learning switched off: checks ignore past decisions");
  app.querySelectorAll("[data-lt]").forEach(b => b.onclick = () => after(() => api("POST", "/api/learning/settings", { code: b.dataset.lt, enabled: b.dataset.on === "1", brand_id: S.brandId }), "Saved"));
  app.querySelectorAll("[data-lr]").forEach(b => b.onclick = () => {
    if (b.dataset.confirm !== "1") { b.dataset.confirm = "1"; b.textContent = "Confirm reset"; b.classList.add("bad"); return; }
    after(() => api("POST", "/api/learning/reset", { code: b.dataset.lr, brand_id: S.brandId }), `History for ${b.dataset.lr} cleared`);
  });
}

/* one labelled case; if the AI provider was busy, wait and try once more so results aren't skewed */
async function evalCase(id, q = "") {
  const call = () => api("POST", `/api/eval/cases/${id}${q ? "?" + q : ""}`);
  let r = await call();
  if (r.ai_status && r.ai_status !== "ok") { await new Promise(res => setTimeout(res, 4000)); try { const r2 = await call(); if (r2.ai_status === "ok" || !r.predicted) r = r2; } catch (_) { /* keep first */ } }
  return r;
}

/* learning experiment: learn on 12 drafts, measure on 18 unseen drafts, before vs after */
function metrics(cases) {
  let tp = 0, fp = 0, fn = 0, flags = 0, hidden = 0, aiFail = 0;
  for (const c of cases) { tp += c.tp; fp += c.fp; fn += c.fn; flags += (c.predicted || []).length; hidden += c.hidden_by_learning || 0; if (c.ai_status && c.ai_status !== "ok") aiFail++; }
  const P = tp + fp ? tp / (tp + fp) : 1, R = tp + fn ? tp / (tp + fn) : 1;
  return { tp, fp, fn, flags, hidden, aiFail, precision: P, recall: R, f1: P + R ? (2 * P * R) / (P + R) : 0, false_share: flags ? fp / flags : 0 };
}
async function pool(items, n, fn) {
  const out = new Array(items.length); let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k], k); } }));
  return out;
}
async function runExperiment(cases, prog) {
  const split = await api("GET", "/api/eval/split");
  const title = id => (cases.find(c => c.id === id) || {}).title || id;
  const one = async (id, q) => { try { return await evalCase(id, q); } catch (e) { return { id, title: title(id), error: e.message, tp: 0, fp: 0, fn: (cases.find(c => c.id === id) || {}).expected || 0, predicted: [] }; } };
  const total = split.train.length + split.test.length * 2; let done = 0;
  const tick = label => { done++; prog.innerHTML = `<div class="progress"><div style="width:${(done / total) * 100}%"></div></div><span class="small muted">${label} (${done} of ${total})</span>`; };
  tick("Step 1 of 3: clearing earlier training decisions"); done--;
  await api("POST", "/api/eval/experiment/start");
  const before = await pool(split.test, 2, async id => { const r = await one(id, "learn=0"); tick("Step 1 of 3: unseen drafts without learning"); return r; });
  const train = await pool(split.train, 2, async id => { const r = await one(id, "learn=0&train=1"); tick("Step 2 of 3: learning from labelled training drafts"); return r; });
  const after = await pool(split.test, 2, async id => { const r = await one(id, "learn=1"); tick("Step 3 of 3: the same unseen drafts with learning"); return r; });
  prog.innerHTML = "";
  const res = { kind: "experiment", train_ids: split.train, test_ids: split.test, before: metrics(before), after: metrics(after),
    train: metrics(train), before_cases: before, after_cases: after };
  await api("POST", "/api/eval/runs", { results: res });
  return res;
}
function experimentReport(r, at) {
  if (!r) return `<p class="muted small">Not run yet in this workspace.</p>`;
  const b = r.before, a = r.after, pct = v => `${Math.round(v * 100)}%`;
  const row = (label, x, y, better, isPct = true) => {
    const d = y - x, eps = isPct ? 0.0049 : 0.5;
    const good = better === "up" ? d > eps : d < -eps, bad = better === "up" ? d < -eps : d > eps;
    const f = v => (isPct ? pct(v) : v);
    return `<tr><td>${label}</td><td>${f(x)}</td><td><b>${f(y)}</b></td><td class="${good ? "good" : bad ? "bad" : "muted"}">${good ? "better" : bad ? "worse" : "same"}</td></tr>`;
  };
  const changed = r.before_cases.map((c, i) => [c, r.after_cases[i]]).filter(([x, y]) => y && (x.fp !== y.fp || x.tp !== y.tp));
  return `
  <table class="cmp"><thead><tr><th>On ${r.test_ids.length} unseen drafts</th><th>Before learning</th><th>After learning</th><th></th></tr></thead><tbody>
    ${row("Precision (flags that were right)", b.precision, a.precision, "up")}
    ${row("False alarms (share of flags)", b.false_share, a.false_share, "down")}
    ${row("Recall (real issues caught)", b.recall, a.recall, "up")}
    ${row("F1 score", b.f1, a.f1, "up")}
    ${row("False alarms", b.fp, a.fp, "down", false)}
    ${row("Real issues caught", b.tp, a.tp, "up", false)}
  </tbody></table>
  <p class="small muted">Learned from ${r.train_ids.length} labelled training drafts (${r.train.flags} flags replayed as ${r.train.flags - r.train.fp} accepts and ${r.train.fp} disputes). ${a.hidden} flags hidden by learning on the unseen drafts. Run ${ago(at)}.
    ${b.aiFail || a.aiFail ? `<span class="bad">${b.aiFail + a.aiFail} run(s) had the AI unavailable, so results are partial.</span>` : ""}</p>
  ${changed.length ? `<details class="small"><summary>${changed.length} draft(s) changed</summary><table><thead><tr><th>Draft</th><th>Caught before → after</th><th>False alarms before → after</th></tr></thead><tbody>${changed.map(([x, y]) => `<tr><td>${esc(x.title)}</td><td>${x.tp} → ${y.tp}</td><td>${x.fp} → ${y.fp}</td></tr>`).join("")}</tbody></table></details>` : ""}`;
}

/* ---------------- how it works ---------------- */
function how() {
  if (!S.token) { $("#topbar").hidden = true; }
  app.innerHTML = `
  <div class="page-head"><div><h1>How Brandproof works</h1><p class="muted">Rules first, AI second, citations always, and a person makes the final decision.</p></div>${S.token ? "" : `<a class="btn btn-primary" href="#/">Start the demo</a>`}</div>
  <div class="panel"><h2>Architecture</h2>${ARCH_SVG}</div>
  <div class="grid-2">
    <div class="panel"><h2>What happens when you click “Check”</h2><ol class="pipeline">
      <li><b>Exact rules (code).</b> Brand and product names, banned and inclusive-language terms, spelling, risky claim words, medical claims, emoji per channel, readability, ALL CAPS, exclamation marks, hashtags, alt text and image colours against the palette.</li>
      <li><b>Retrieve.</b> The most relevant guideline clauses and approved facts are selected (keyword ranking, plus embeddings when configured).</li>
      <li><b>AI judgement.</b> The language model sees only those numbered clauses and facts, and must quote the draft and cite one id per issue. It also lists every claim and labels it Supported, Outdated, Contradicted or Unsupported.</li>
      <li><b>Citation gate.</b> An AI finding is kept only if its id was really provided and its quote really appears in the draft. Everything else is discarded and counted.</li>
      <li><b>Image check.</b> A vision model reviews the image against visual clauses (logo, retouching, text contrast), with the same citation rule.</li>
      <li><b>Minimal fix.</b> Each issue gets the smallest rewrite that resolves it. A fix that changes too much of the sentence is dropped so the writer's meaning is kept.</li>
      <li><b>Human decision.</b> The creator accepts, edits or disputes each issue; a manager or reviewer approves or sends back. Every step is in the audit log.</li>
    </ol></div>
    <div>
      <div class="panel"><h2>Privacy and responsible AI</h2><ul class="small">
        <li>Each organisation's guidelines, facts and drafts are isolated: every query is scoped to the signed-in organisation.</li>
        <li>Emails and phone numbers are redacted before any text is sent to an AI provider.</li>
        <li>Content is not used to train models. Results are cached by content hash so the same draft gets the same answer.</li>
        <li>Every AI finding is labelled with the model that produced it, and shows a confidence level.</li>
        <li>Nothing is published or rewritten automatically: people decide.</li></ul></div>
      <div class="panel"><h2>For developers</h2><p class="small">Check content from any tool with the public API:</p>
        <div class="doc small">POST /api/v1/check
Authorization: Bearer &lt;token&gt;
{ "text": "...", "channel": "social" }</div>
        <p class="small">Interactive API docs: <a href="/api/docs" target="_blank">/api/docs</a></p></div>
    </div>
  </div>`;
}
const ARCH_SVG = `<svg class="arch" viewBox="0 0 760 470" role="img" aria-label="Brandproof architecture" font-family="Inter, Arial, sans-serif" font-size="13">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#9AA3B5"/></marker></defs>
<g fill="none" stroke="#9AA3B5" stroke-width="1.3"><path d="M132 72V94" marker-end="url(#ah)"/><path d="M380 72V94" marker-end="url(#ah)"/><path d="M628 72V94" marker-end="url(#ah)" stroke-dasharray="5 4"/><path d="M380 148V170" marker-end="url(#ah)"/><path d="M196 386V408" marker-end="url(#ah)"/><path d="M564 386V408" marker-end="url(#ah)"/></g>
<g><rect x="24" y="20" width="216" height="52" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="132" y="42" text-anchor="middle" font-weight="700" fill="#121826">Web app</text><text x="132" y="60" text-anchor="middle" font-size="11.5" fill="#4A5468">Creator, manager, admin views</text></g>
<g><rect x="272" y="20" width="216" height="52" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="380" y="42" text-anchor="middle" font-weight="700" fill="#121826">Public API</text><text x="380" y="60" text-anchor="middle" font-size="11.5" fill="#4A5468">POST /api/v1/check from any tool</text></g>
<g><rect x="520" y="20" width="216" height="52" rx="8" fill="#fff" stroke="#9AA3B5" stroke-dasharray="5 4"/><text x="628" y="42" text-anchor="middle" font-weight="700" fill="#121826">Integrations (next)</text><text x="628" y="60" text-anchor="middle" font-size="11.5" fill="#4A5468">Chrome, Google Docs, Canva</text></g>
<g><rect x="24" y="96" width="712" height="52" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="380" y="118" text-anchor="middle" font-weight="700" fill="#121826">FastAPI on Vercel</text><text x="380" y="136" text-anchor="middle" font-size="11.5" fill="#4A5468">Signed sessions, organisation check on every request, roles</text></g>
<rect x="24" y="172" width="712" height="214" rx="8" fill="#F1F3F8" stroke="#9AA3B5"/><text x="40" y="196" font-weight="700" fill="#121826">Core services</text>
<g><rect x="40" y="208" width="680" height="88" rx="8" fill="#EEF2FF" stroke="#3451C6" stroke-width="2"/><text x="380" y="232" text-anchor="middle" font-weight="700" fill="#121826">Check engine</text><text x="380" y="252" text-anchor="middle" font-size="11.5" fill="#121826">Exact rules: terms, claim words, medical claims, readability, palette, alt text</text><text x="380" y="268" text-anchor="middle" font-size="11.5" fill="#121826">Retrieve clauses + facts → AI judgement + claim check (structured JSON)</text><text x="380" y="284" text-anchor="middle" font-size="11.5" fill="#121826">Citation gate drops uncited findings → minimal fix → saved with source and confidence</text></g>
<g><rect x="40" y="306" width="216" height="64" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="148" y="328" text-anchor="middle" font-weight="700" fill="#121826">Rulebook</text><text x="148" y="346" text-anchor="middle" font-size="11.5" fill="#4A5468">PDF import to rule cards;</text><text x="148" y="361" text-anchor="middle" font-size="11.5" fill="#4A5468">clauses, facts, terms, palette</text></g>
<g><rect x="272" y="306" width="216" height="64" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="380" y="328" text-anchor="middle" font-weight="700" fill="#121826">Workflow</text><text x="380" y="346" text-anchor="middle" font-size="11.5" fill="#4A5468">Versions, accept / edit / dispute,</text><text x="380" y="361" text-anchor="middle" font-size="11.5" fill="#4A5468">approvals, comments, audit log</text></g>
<g><rect x="504" y="306" width="216" height="64" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="612" y="328" text-anchor="middle" font-weight="700" fill="#121826">Insights + evaluation</text><text x="612" y="346" text-anchor="middle" font-size="11.5" fill="#4A5468">Recurring issues, unclear clauses,</text><text x="612" y="361" text-anchor="middle" font-size="11.5" fill="#4A5468">precision / recall per check type</text></g>
<g><rect x="24" y="410" width="344" height="52" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="196" y="432" text-anchor="middle" font-weight="700" fill="#121826">Supabase Postgres</text><text x="196" y="450" text-anchor="middle" font-size="11.5" fill="#4A5468">Per-organisation data, audit log, check cache</text></g>
<g><rect x="392" y="410" width="344" height="52" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="564" y="432" text-anchor="middle" font-weight="700" fill="#121826">AI gateway</text><text x="564" y="450" text-anchor="middle" font-size="11.5" fill="#4A5468">Redaction · retries · fallback · Gemini / Sarvam</text></g>
</svg>`;

document.addEventListener("change", e => {
  if (e.target.type === "file") { const t = document.querySelector(`.drop-text[data-for="${e.target.id}"]`); if (t && e.target.files[0]) { t.textContent = "✓ " + e.target.files[0].name; t.parentElement.classList.add("has"); } }
});

/* ---------------- boot ---------------- */
S.token = store.get("bp_token");
route();
