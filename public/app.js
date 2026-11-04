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
function loading(msg = "Loading…") { app.innerHTML = `<div class="loading"><span class="spinner dark"></span>${esc(msg)}</div>`; }

async function api(method, path, body) {
  const res = await fetch(path, {
    method, headers: { "Content-Type": "application/json", ...(S.token ? { Authorization: "Bearer " + S.token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty */ }
  if (res.status === 401) { localStorage.removeItem("bp_token"); S.token = null; }
  if (!res.ok) throw new Error((data && data.detail && (typeof data.detail === "string" ? data.detail : data.detail[0]?.msg)) || `Request failed (${res.status})`);
  return data;
}
async function busy(btn, fn, label) {
  const old = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spinner${btn.classList.contains("btn-primary") || btn.classList.contains("btn-good") ? "" : " dark"}"></span> ${label || "Working…"}`;
  try { return await fn(); } catch (e) { toast(e.message, true); } finally { btn.disabled = false; btn.innerHTML = old; }
}

/* ---------------- session ---------------- */
async function startDemo(role = "creator") {
  const d = await api("POST", "/api/session/demo", { name: "Guest", role });
  S.token = d.token; localStorage.setItem("bp_token", d.token);
  await loadMe();
}
async function loadMe() {
  S.me = await api("GET", "/api/me");
  const saved = localStorage.getItem("bp_brand");
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
$("#brandSelect").addEventListener("change", e => { S.brandId = e.target.value; localStorage.setItem("bp_brand", S.brandId); route(); });
$("#menuBtn").addEventListener("click", () => $("#nav").classList.toggle("open"));

/* ---------------- router ---------------- */
const routes = [
  [/^#?\/?$/, landing], [/^#\/new$/, newCheck], [/^#\/drafts$/, drafts], [/^#\/queue$/, queue],
  [/^#\/d\/([\w]+)$/, draftView], [/^#\/rulebook$/, rulebook], [/^#\/insights$/, insights],
  [/^#\/eval$/, evaluation], [/^#\/how$/, how],
];
async function route() {
  const h = location.hash || "#/";
  $("#nav").classList.remove("open");
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("active", h.startsWith("#/" + a.dataset.nav) || (a.dataset.nav === "drafts" && h.startsWith("#/d/"))));
  if (!S.token && h !== "#/" && h !== "" && h !== "#/how") { location.hash = "#/"; return; }
  if (S.token && !S.me) { try { await loadMe(); } catch (_) { S.token = null; localStorage.removeItem("bp_token"); location.hash = "#/"; return; } }
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) { window.scrollTo(0, 0); try { await fn(...m.slice(1)); } catch (e) { app.innerHTML = `<div class="panel empty">${esc(e.message)}<br><br><a href="#/new">Back to New check</a></div>`; } return; }
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
      <h1>Catch off-brand content before anyone publishes it.</h1>
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
  <div class="page-head"><div><h1>New check</h1><p class="muted">Pick a sample or bring your own content. It's checked against the <b>${esc((S.me.brands.find(b => b.id === S.brandId) || {}).name)}</b> rulebook.</p></div></div>
  <div class="grid-2">
    <div class="panel">
      <h2>Try a sample</h2>
      ${demoBrand ? `<p class="muted small">Real-world drafts written with typical mistakes. Two are compliant, to show what a clean result looks like.</p>
      <div class="samples">${S.samples.map(s => `<button class="sample" data-sample="${s.id}"><b>${esc(s.title)}${s.has_image ? " 🖼" : ""}</b><span>${esc(s.text)}</span></button>`).join("")}</div>`
      : `<p class="muted">Samples are written for the Neem &amp; Nila demo brand. Switch brand in the top bar to use them, or check your own content here.</p>`}
    </div>
    <div class="panel">
      <h2>Check your own content</h2>
      <label class="field"><span>Title</span><input id="fTitle" placeholder="e.g. Diwali serum post"></label>
      <label class="field"><span>Channel</span><select id="fChannel">${Object.entries(CHANNEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label>
      <label class="field"><span>Text</span><textarea id="fText" placeholder="Paste a caption, email, blog paragraph or press note…"></textarea></label>
      <label class="field"><span>Image (optional)</span><input id="fImage" type="file" accept="image/png,image/jpeg,image/webp"></label>
      <div id="imgPrev"></div>
      <label class="field"><span>Alt text for the image</span><input id="fAlt" placeholder="Describe what the image shows"></label>
      <div class="or">or</div>
      <label class="field"><span>Upload a PDF (brochure, press note)</span><input id="fPdf" type="file" accept="application/pdf"></label>
      <button class="btn-primary" id="checkBtn">Check content</button>
    </div>
  </div>`;
  let image = null, pdf = null;
  app.querySelectorAll("[data-sample]").forEach(b => b.onclick = () => busy(b, async () => {
    const d = await api("POST", "/api/drafts", { sample_id: b.dataset.sample, brand_id: S.brandId });
    await api("POST", `/api/drafts/${d.id}/check`); location.hash = "#/d/" + d.id;
  }, "Checking…"));
  $("#fImage").onchange = async e => { image = e.target.files[0] ? await shrinkImage(e.target.files[0]) : null; $("#imgPrev").innerHTML = image ? `<img src="${image}" style="max-width:160px;border-radius:8px">` : ""; };
  $("#fPdf").onchange = async e => { pdf = e.target.files[0] ? await fileB64(e.target.files[0]) : null; if (e.target.files[0]?.size > 3.5e6) { toast("PDF must be under 3.5 MB", true); pdf = null; e.target.value = ""; } };
  $("#checkBtn").onclick = e => busy(e.currentTarget, async () => {
    const body = { title: $("#fTitle").value, channel: $("#fChannel").value, text: $("#fText").value, image_b64: image, alt_text: $("#fAlt").value, pdf_b64: pdf, brand_id: S.brandId };
    if (!body.text.trim() && !image && !pdf) throw new Error("Add some text, an image or a PDF first.");
    const d = await api("POST", "/api/drafts", body);
    await api("POST", `/api/drafts/${d.id}/check`); location.hash = "#/d/" + d.id;
  }, "Checking… (AI review takes ~10–20 s)");
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
    $("#recheckBtn").onclick = e => busy(e.currentTarget, async () => renderDraft(await api("POST", `/api/drafts/${draft.id}/check`)), "Checking…");
    $("#submitBtn").onclick = e => busy(e.currentTarget, async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/submit`)); refreshQueueCount(); toast("Submitted for review. Switch role to Manager to review it."); }, "Submitting…");
  } else if (draft.status === "in_review" && reviewer) {
    ha.innerHTML = `<input id="reviewComment" placeholder="Comment (required to send back)" style="width:260px"><button id="sendBackBtn">Send back</button><button class="btn-good" id="approveBtn">Approve</button>`;
    $("#approveBtn").onclick = e => busy(e.currentTarget, async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/review`, { action: "approve", comment: $("#reviewComment").value })); refreshQueueCount(); toast("Approved"); }, "Approving…");
    $("#sendBackBtn").onclick = e => busy(e.currentTarget, async () => { renderDraft(await api("POST", `/api/drafts/${draft.id}/review`, { action: "request_changes", comment: $("#reviewComment").value })); refreshQueueCount(); toast("Sent back to the creator"); }, "Sending…");
  }
  if (editable && $("#editBtn")) $("#editBtn").onclick = () => editMode(draft, cur);
  $("#commentBtn").onclick = e => { const c = $("#commentIn").value.trim(); if (!c) return; busy(e.currentTarget, async () => renderDraft(await api("POST", `/api/drafts/${draft.id}/comment`, { comment: c }))); };
  bindFindings(d, editable);
}
function actionText(a) {
  return { created: "created the draft", checked: "ran a check", submitted: "submitted for review", approved: "approved", changes_requested: "requested changes", edited: "edited the text", commented: "commented" }[a] || a;
}
function docHtml(text, findings, readOnly) {
  const spans = findings.map((f, i) => ({ ...f, i: i + 1 })).filter(f => f.start_idx != null && f.end_idx != null).sort((a, b) => a.start_idx - b.start_idx || b.end_idx - a.end_idx);
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
  const ai = check.ai_status;
  return `
    <div class="row"><h2 style="margin:0">Issues</h2><span class="spacer"></span><span class="muted small">${s.cached ? "cached result · " : ""}${(check.duration_ms / 1000).toFixed(1)} s</span></div>
    <div class="summary" style="margin-top:.6rem">
      <div class="kpi"><b>${findings.length}</b><span>issues</span></div>
      <div class="kpi"><b class="${high ? "bad" : ""}">${high}</b><span>high severity</span></div>
      <div class="kpi"><b>${decided}/${findings.length}</b><span>decided</span></div>
      <div class="kpi"><b>${check.dropped_uncited}</b><span>uncited AI flags discarded</span></div>
    </div>
    ${ai === "failed" ? `<div class="warn">AI review was unavailable for this run, so only rule-based checks are shown. Use <b>Re-run check</b> to try again.</div>` : ""}
    ${ai === "not_configured" ? `<div class="warn">AI checks are not configured on this server; showing rule-based checks only.</div>` : ""}
    ${check.model ? `<div class="ai-note">AI-assisted review by <b>${esc(check.model)}</b>. AI findings are labelled “AI” and every one cites a clause or fact; uncited suggestions are discarded automatically.</div>` : ""}
    ${(s.verified_claims || []).length ? `<p class="verified">✓ Verified against the fact sheet: ${s.verified_claims.map(v => `“${esc(v.quote)}” (${esc(v.cite_code)})`).join(", ")}</p>` : ""}
    ${!findings.length ? `<div class="okbox">No issues found. This content follows the rulebook.</div>` : ""}
    ${editable && findings.length ? `<div class="row small" style="margin:.2rem 0 .6rem"><span class="muted">Decide on every issue, then submit.</span><span class="spacer"></span><button class="btn-sm" id="acceptAll" ${decided === findings.length ? "disabled" : ""}>Accept all remaining fixes</button></div>` : ""}
    ${!editable && findings.some(f => f.decision === "disputed") ? `<div class="warn"><b>${findings.filter(f => f.decision === "disputed").length} disputed by the creator</b>, shown first. Read the notes before approving.${findings.some(f => f.decision === "disputed" && f.severity === "high" && ["claims", "legal"].includes(f.category)) ? " A high-severity claim was disputed: a manager must add a comment to approve, or a Reviewer can approve directly." : ""}</div>` : ""}
    <div id="flist">${findings.map((f, i) => [f, i + 1]).sort((a, b) => editable ? 0 : (b[0].decision === "disputed") - (a[0].decision === "disputed")).map(([f, n]) => findingCard(f, n, editable)).join("")}</div>`;
}
function findingCard(f, n, editable) {
  const quoteable = f.quote && f.quote !== "*" && f.quote !== "[image]";
  const fixShown = f.decision === "edited" ? f.edited_fix : f.fix_text;
  return `<div class="finding ${f.decision ? "decided" : ""}" id="f-${f.id}">
    <div class="head"><span class="num">#${n}</span><span class="pill ${f.severity}">${f.severity[0].toUpperCase() + f.severity.slice(1)}</span>
      <span class="pill cat">${CAT[f.category] || f.category}</span>
      ${f.claim_status ? `<span class="pill claim">Claim: ${CLAIM[f.claim_status] || f.claim_status}</span>` : ""}
      ${f.source === "ai" ? `<span class="pill ai" title="Found by AI; confidence ${Math.round(f.confidence * 100)}%">AI · ${Math.round(f.confidence * 100)}%</span>` : `<span class="pill rule" title="Found by an exact rule">Rule</span>`}
    </div>
    ${quoteable ? `<div class="quote">“${esc(f.quote)}”</div>` : f.quote === "[image]" ? `<div class="quote">In the image</div>` : ""}
    <p class="small">${esc(f.explanation)}</p>
    <div class="cite ${f.cite_type === "fact" ? "fact" : ""}"><b>${f.cite_type === "fact" ? "Approved fact " + esc(f.cite_code) : "Guideline " + esc(f.cite_code)}</b> · ${esc(f.cite_text)}</div>
    ${fixShown != null && quoteable ? `<div class="fix">Suggested fix: <span class="diff-del">${esc(f.quote)}</span> → ${fixShown === "" ? '<span class="muted">(remove)</span>' : `<span class="diff-ins">${esc(fixShown)}</span>`}</div>` : ""}
    ${f.decision ? `<div class="actions"><span class="decision ${f.decision}">${{ accepted: "✓ Fix accepted", edited: "✓ Edited", disputed: "⚑ Disputed" }[f.decision]}</span>${f.decision_note ? `<span class="small muted">“${esc(f.decision_note)}”</span>` : ""}<span class="small muted">by ${esc(f.decided_by)}</span>${editable ? `<button class="btn-ghost btn-sm" data-undo="${f.id}">Undo</button>` : ""}</div>`
    : editable ? `<div class="actions">
        ${fixShown != null && quoteable ? `<button class="btn-sm btn-good" data-accept="${f.id}">Accept fix</button>` : `<button class="btn-sm btn-good" data-ack="${f.id}">Mark resolved</button>`}
        ${quoteable ? `<button class="btn-sm" data-edit="${f.id}">Edit</button>` : ""}
        <button class="btn-sm" data-dispute="${f.id}">Dispute</button></div><div class="slot"></div>` : `<div class="small muted">Open</div>`}
  </div>`;
}
function bindFindings(d, editable) {
  const byId = Object.fromEntries(d.findings.map(f => [f.id, f]));
  app.querySelectorAll("mark.hl").forEach(m => m.onclick = () => focusFinding(m.dataset.f));
  if ($("#firstCheck")) $("#firstCheck").onclick = e => busy(e.currentTarget, async () => renderDraft(await api("POST", `/api/drafts/${d.draft.id}/check`)), "Checking…");
  if (!editable) return;
  const decide = async (id, body) => { await api("POST", `/api/findings/${id}/decision`, body); renderDraft(await api("GET", `/api/drafts/${d.draft.id}`)); setTimeout(() => focusNext(), 50); };
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
  $("#saveEdit").onclick = e => busy(e.currentTarget, async () => renderDraft(await api("POST", `/api/drafts/${draft.id}/versions`, { text: $("#editText").value, alt_text: $("#editAlt") ? $("#editAlt").value : null })), "Saving and checking…");
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
  const rb = await api("GET", "/api/rulebook?brand_id=" + S.brandId);
  const canEdit = ["admin", "manager"].includes(S.me.role);
  const sections = {};
  rb.clauses.forEach(c => (sections[c.section] = sections[c.section] || []).push(c));
  const drafts = rb.clauses.filter(c => c.status !== "confirmed").length;
  const today = new Date().toISOString().slice(0, 10);
  app.innerHTML = `
  <div class="page-head"><div><h1>Rulebook · ${esc(rb.brand.name)}</h1><p class="muted">${rb.clauses.length} clauses, ${rb.facts.length} approved facts, ${rb.terms.length} terms. Every finding cites one of these.</p></div>
    ${canEdit ? `<button class="btn-primary" id="importToggle">Import a guideline PDF</button>` : ""}</div>
  ${!canEdit ? `<div class="warn">Switch <b>Role</b> to Admin or Manager to edit clauses or import a new guideline.</div>` : ""}
  <div class="panel" id="importPanel" hidden>
    <h2>Import a brand guideline</h2>
    <p class="muted small">Upload any guideline PDF (or paste the text). Brandproof splits it into numbered clauses, classifies each as an exact rule or an AI-judged rule, and extracts banned or required terms. It is added as a new brand for you to review and confirm.</p>
    <label class="field"><span>Brand name</span><input id="impName" placeholder="e.g. Acme Foods"></label>
    <label class="field"><span>Guideline PDF</span><input id="impPdf" type="file" accept="application/pdf"></label>
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
  if ($("#impBtn")) $("#impBtn").onclick = e => busy(e.currentTarget, async () => {
    const f = $("#impPdf").files[0];
    const body = { name: $("#impName").value || "Imported brand", text: $("#impText").value, pdf_b64: f ? await fileB64(f) : null };
    const r = await api("POST", "/api/rulebook/import", body);
    await loadMe(); S.brandId = r.brand_id; localStorage.setItem("bp_brand", r.brand_id); $("#brandSelect").value = r.brand_id;
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
    ${canEdit ? `<button class="btn-ghost btn-sm" data-editc="${c.id}">Edit</button>` : ""}</div>
    <p class="small" style="margin:.3rem 0 0">${esc(c.text)}</p></div>`;
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
  const [cases, last] = await Promise.all([api("GET", "/api/eval/cases"), api("GET", "/api/eval/latest")]);
  app.innerHTML = `
  <div class="page-head"><div><h1>Evaluation</h1><p class="muted">How accurate is Brandproof? We run it on ${cases.length} labelled drafts (${cases.reduce((a, c) => a + c.expected, 0)} known issues) and measure what it catches and what it gets wrong.</p></div>
    <button class="btn-primary" id="runEval">Run evaluation now</button></div>
  <div class="panel"><p class="small muted"><b>How it's scored.</b> Each test draft was labelled by hand with the issues a careful brand reviewer would flag. A finding counts as correct if it matches a labelled issue of the same type at the same place. <b>Precision</b> = share of flags that were right (low precision means false alarms). <b>Recall</b> = share of real issues caught.</p>
    <div id="evalProgress"></div></div>
  <div id="evalOut">${last ? evalReport(last.results, last.ran_at) : `<div class="panel empty">No evaluation run yet in this workspace. Click <b>Run evaluation now</b> (about 2–4 minutes with AI).</div>`}</div>`;
  $("#runEval").onclick = e => busy(e.currentTarget, async () => {
    const results = []; const prog = $("#evalProgress");
    for (let k = 0; k < cases.length; k++) {
      prog.innerHTML = `<div class="progress"><div style="width:${(k / cases.length) * 100}%"></div></div><span class="small muted">Checking ${k + 1} of ${cases.length}: ${esc(cases[k].title)}</span>`;
      try { results.push(await api("POST", "/api/eval/cases/" + cases[k].id)); } catch (err) { results.push({ id: cases[k].id, title: cases[k].title, error: err.message, tp: 0, fp: 0, fn: cases[k].expected, by_cat: {}, missed: [], predicted: [] }); }
    }
    prog.innerHTML = "";
    const summary = { cases: results };
    await api("POST", "/api/eval/runs", { results: summary });
    $("#evalOut").innerHTML = evalReport(summary, new Date().toISOString());
  }, "Running…");
}
function evalReport(res, at) {
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
    <div class="panel"><h2>By issue type</h2><table><thead><tr><th>Type</th><th>Precision</th><th>Recall</th><th>Caught</th><th>Missed</th><th>False alarms</th></tr></thead><tbody>
      ${Object.entries(cats).sort().map(([k, v]) => `<tr><td>${CAT[k] || k}</td><td>${fmt(P(v.tp, v.fp))}</td><td>${fmt(P(v.tp, v.fn))}</td><td>${v.tp}</td><td>${v.fn}</td><td>${v.fp}</td></tr>`).join("")}</tbody></table>
      <p class="muted small">Run ${ago(at)} on ${cases.length} drafts.</p></div>
    <div class="panel"><h2>Per draft</h2><table><thead><tr><th>Draft</th><th>Caught</th><th>Missed</th><th>False</th></tr></thead><tbody>
      ${cases.map(c => `<tr><td>${esc(c.title)}${c.missed?.length ? `<div class="muted small">Missed: ${c.missed.map(m => `${CAT[m.category] || m.category} ${m.quote === "*" ? "(whole draft)" : `“${esc(m.quote)}”`}`).join("; ")}</div>` : ""}${c.error ? `<div class="bad small">${esc(c.error)}</div>` : ""}</td><td>${c.tp}</td><td class="${c.fn ? "bad" : ""}">${c.fn}</td><td class="${c.fp ? "bad" : ""}">${c.fp}</td></tr>`).join("")}</tbody></table></div>
  </div>`;
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
<g><rect x="392" y="410" width="344" height="52" rx="8" fill="#fff" stroke="#9AA3B5"/><text x="564" y="432" text-anchor="middle" font-weight="700" fill="#121826">AI gateway</text><text x="564" y="450" text-anchor="middle" font-size="11.5" fill="#4A5468">Redaction, retries · Sarvam (text) · vision · embeddings</text></g>
</svg>`;

/* ---------------- boot ---------------- */
S.token = localStorage.getItem("bp_token");
route();
