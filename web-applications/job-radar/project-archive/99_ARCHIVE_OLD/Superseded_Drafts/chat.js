/* ---------------- toasts & status ---------------- */
const CHECK = () => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "check"); s.setAttribute("aria-hidden", "true");
  s.innerHTML = '<circle cx="12" cy="12" r="10"/><path d="M7 12.5l3.2 3.2L17 9"/>'; return s; };
function toast(text, type = "ok", actions = []) {
  const ico = type === "ok" ? CHECK() : h("span", { class: "ico", "aria-hidden": "true" }, type === "err" ? "!" : "i");
  const el = h("div", { class: "t " + type, role: type === "err" ? "alert" : "status" }, ico, h("div", {}, text),
    h("button", { type: "button", class: "x", "aria-label": "Dismiss", onclick: () => el.remove() }, "×"),
    actions.length ? h("div", { class: "acts" }, actions.map(([label, fn]) => h("button", { type: "button", onclick: () => { el.remove(); fn(); } }, label))) : null);
  $("toasts").append(el);
  setTimeout(() => el.remove(), type === "err" ? 12000 : 4500);
}
S.busy = 0; S.flashSt = null; S.svc = null;
function busy(on, label) { S.busy = Math.max(0, S.busy + (on ? 1 : -1)); if (label) S.busyLabel = label; renderStatus(); }
function flashStatus(kind) { S.flashSt = kind; renderStatus(); clearTimeout(flashStatus.t); flashStatus.t = setTimeout(() => { S.flashSt = null; renderStatus(); }, 3000); }
function renderStatus() {
  const b = $("statusBtn"), v = S.svc;
  let cls = "st-offline", txt = "Offline mode";
  if (S.busy) { cls = "st-busy"; txt = (S.busyLabel || "Processing") + "…"; }
  else if (S.flashSt === "success") { cls = "st-success"; txt = "Success"; }
  else if (S.flashSt === "error") { cls = "st-error"; txt = "Error"; }
  else if (v && v.mode === "online") { cls = "st-online"; txt = "Online"; }
  else if (!v) txt = "Checking…";
  b.className = "status-btn " + cls; $("statusText").textContent = txt;
  if (!v) return;
  const chip = (s, label, title) => h("button", { type: "button", class: "chip " + ({ ready: "ok", error: "bad" }[s] || "warn"), title, onclick: toggleSvc }, h("span", { class: "dot" }), label);
  const voiceOk = !!SR;
  $("featChips").replaceChildren(chip(v.ai.state, v.ai.label, v.ai.detail), chip(v.ocr.state, v.ocr.label, v.ocr.detail),
    chip(voiceOk ? "ready" : "not_configured", voiceOk ? "Voice to text" : "Voice to text unavailable", voiceOk ? "Browser speech-to-text" : "This browser has no speech-to-text"));
  renderSvcBody();
}
function renderSvcBody() {
  const v = S.svc; if (!v) return;
  const off = v.ai.state !== "ready" && v.ocr.state !== "ready";
  const row = (f, s) => h("tr", {}, h("td", {}, f), h("td", {}, s));
  $("svcBody").replaceChildren(
    off ? h("p", { class: "svc-note", style: "margin:0 0 8px" }, "AI and OCR services are not configured. The chat is running in offline mode: you can keep entering and editing information by hand. Configure them in Settings to read screenshots and understand text with AI.") :
      v.ai.state !== "ready" ? h("p", { class: "svc-note", style: "margin:0 0 8px" }, "AI isn't set up, so text is understood with built-in rules. " + (v.ocr.state === "ready" ? "Screenshots are still read with " + v.ocr.detail.split(" ·")[0] + "." : "")) : null,
    h("table", { class: "svc-table" }, h("thead", {}, h("tr", {}, h("th", {}, "Feature"), h("th", {}, "Status"))),
      h("tbody", {},
        row("Chat workflow", v.mode === "online" ? "Available — Online (AI-assisted)" : "Available — Offline mode"),
        row("AI processing", (v.ai.state === "ready" ? "Ready — " : v.ai.state === "error" ? "Error — " : "Disabled — ") + v.ai.detail),
        row("OCR processing", (v.ocr.state === "ready" ? "Ready — " : v.ocr.state === "error" ? "Error — " : "Disabled — ") + v.ocr.detail),
        row("Voice transcription", SR ? "Available — browser speech-to-text (needs internet)" : "Unavailable — use Microsoft Edge or Google Chrome; recordings are still saved"),
        row("Manual data entry", "Available"), row("Answer editing", "Available"),
        row("Save search", "Available — saved on this computer"))),
    h("div", { class: "btns", style: "margin-top:8px" }, h("button", { type: "button", onclick: () => loadServices(true) }, "Refresh"),
      h("button", { type: "button", class: "primary", onclick: openAISettings }, "Configure in Settings")));
}
function toggleSvc() { const p = $("svcPanel"); p.hidden = !p.hidden; $("statusBtn").setAttribute("aria-expanded", String(!p.hidden)); }
$("statusBtn").addEventListener("click", toggleSvc);
$("svcClose").addEventListener("click", toggleSvc);
async function loadServices(announce) {
  try { S.svc = await api("GET", "/api/services"); renderStatus(); renderAIState(); if (announce) toast("Status refreshed.", "info"); }
  catch (e) { if (announce) toast("Couldn't check services: " + e.message, "err"); }
}
function openAISettings() {
  const d = document.querySelector("details.settings"); d.open = true; $("svcPanel").hidden = true;
  $("aiForm").scrollIntoView({ behavior: "smooth", block: "start" }); setTimeout(() => $("aiOn").focus(), 400);
}

/* ---------------- chat intake ---------------- */
const GREETING = "Hi! Tell me about the job you're looking for: the role, the kind of work and anything you care about. You can also attach a resume, a job post, a screenshot or a voice note.";
let SECTIONS = [];
const SEC = (k) => SECTIONS.find((s) => s.key === k) || { key: k, label: k, kind: "text", options: [] };
const clone = (o) => JSON.parse(JSON.stringify(o));
const showVal = (p, k) => { const v = (p || {})[k]; if (k === "remote_international") return v ? "Yes" : v === false ? "No" : "";
  if (Array.isArray(v)) return v.filter(Boolean).join(", "); return v == null ? "" : String(v); };
S.confirm = null; S.editor = null; S.prog = null; S.armRestart = false;

function renderProgress() {
  const box = $("prog"), pr = S.prog;
  if (!pr) { box.replaceChildren(h("div", { class: "prog-top" }, h("b", {}, "Describe the job to begin"), h("span", { class: "muted" }, "10 short questions")), h("div", { class: "bar" }, h("i", { style: "width:0%" }))); return; }
  const all = pr.done === pr.total && !pr.current;
  const cur = pr.current ? pr.steps[pr.current - 1] : null;
  const locked = !!S.confirm || !!S.editor;
  box.replaceChildren(
    h("div", { class: "prog-top" }, h("b", {}, all ? "All 10 sections answered" : cur ? `Question ${pr.current} of ${pr.total}: ${cur.label}` : `${pr.done} of ${pr.total} answered`),
      h("span", { class: "muted" }, `${pr.done} done · ${pr.percent}%`)),
    h("div", { class: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(pr.percent), "aria-label": "Questions answered" }, h("i", { style: `width:${pr.percent}%` })),
    h("div", { class: "segs", role: "list" }, pr.steps.map((s, i) => h("button", { type: "button", role: "listitem", class: "seg " + s.status,
      disabled: s.status !== "done" || locked, title: `${i + 1}. ${s.label}: ` + (s.status === "done" ? (s.value || "not set") + " — click to edit" : s.status === "current" ? "answering now" : "not answered yet"),
      "aria-label": `${s.label}, ${s.status === "done" ? "answered, edit" : s.status}`, onclick: () => openEditor([s.key]) }, s.status === "done" ? "✓" : String(i + 1)))),
    pr.done ? h("details", { class: "small" }, h("summary", { style: "cursor:pointer" }, "Review my answers"),
      h("ul", { class: "answers", style: "margin-top:6px" }, pr.steps.filter((s) => s.status === "done").map((s) => h("li", {},
        h("span", { class: "k" }, s.label), h("span", { class: "v" }, s.value || "not set"),
        h("button", { type: "button", disabled: locked, onclick: () => openEditor([s.key]) }, "Edit"))))) : null);
}

function renderChat() {
  const t = $("thread");
  let lastBot = -1; S.chat.forEach((m, i) => { if (m.role === "bot") lastBot = i; });
  const live = !S.confirm && !S.editor && !S.done;
  const items = S.chat.map((m, i) => h("div", { class: "msg " + m.role },
    h("div", { class: "b" }, m.role === "ok" ? CHECK() : null, m.text || (m.files && m.files.length ? "" : "…"),
      m.files && m.files.length ? h("div", { class: "att" }, m.files.map((f) =>
        f.kind === "image" ? h("img", { src: f.url, alt: f.filename }) :
        f.kind === "voice" ? h("audio", { controls: true, src: f.url }) :
        h("a", { href: f.url, target: "_blank" }, "Document: " + f.filename))) : null),
    m.role === "bot" && i === lastBot && live && m.options && m.options.length
      ? h("div", { class: "opts" }, m.options.map((o) => h("button", { type: "button", onclick: () => send(o) }, o))) : null));
  if (S.confirm) items.push(confirmCard());
  else if (S.editor) items.push(editorCard());
  else if (S.done) items.push(summaryCard(S.done));
  t.replaceChildren(...items); t.scrollTop = t.scrollHeight;
  renderProgress();
  const lock = !!S.editor;
  $("chatText").disabled = lock; $("send").disabled = lock;
  $("chatLabel").textContent = S.confirm ? "Confirm above, or type a different answer" : lock ? "Finish or cancel the edit above" : "Your message";
}

/* ---- answer confirmation ---- */
function confirmRows(r, ctx) {
  const rows = (r.changes || []).map((c) => ({ ...c }));
  const k = r.asked_key, st = r.state || {};
  if (ctx.kind === "answer" && k && !rows.some((c) => c.key === k) && (st.asked || []).includes(k) && st.pending !== k)
    rows.unshift({ key: k, label: SEC(k).label, old: null, new: showVal(st.profile, k) || "Not set (skipped)", kept: true });
  return rows;
}
function handleResult(r, ctx) {
  const st = r.state || {};
  const reasked = r.asked_key && !(st.asked || []).includes(r.asked_key);
  const rows = confirmRows(r, ctx);
  if (r.error || !rows.length || (reasked && !(r.changes || []).length)) return commit(r, ctx, false);
  S.confirm = { r, ctx, rows };
}
function cleanQuestion(r) {
  let q = r.question || "";
  if (q.includes("\n\n")) q = q.split("\n\n").pop();
  return q;
}
function commit(r, ctx, confirmed) {
  const wasDone = !!S.done;
  S.intake = r.state; S.prog = r.progress || S.prog; S.confirm = null;
  if (confirmed) S.chat.push({ role: "ok", text: ctx.kind === "answer" ? "Answer confirmed" : ctx.kind === "start" ? "Details confirmed" : "Attachment details confirmed" });
  if (r.done) {
    S.done = r.profile;
    const notes = (r.notes || []).join(" ");
    if (!confirmed) S.chat.push({ role: "bot", text: wasDone ? (notes ? "Updated. " + notes : "I didn't find a change in that. Use Edit on the card below, or type e.g. 'add Pune', 'remove seo skill', 'make it hybrid'.")
      : (notes ? "Got it. " + notes + "\n" : "") + "Thanks, I have what I need. Check the search below." });
    else if (!wasDone) S.chat.push({ role: "bot", text: "Thanks, I have everything I need. Check the search below, then save it." });
  } else {
    S.done = null;
    S.chat.push({ role: "bot", text: confirmed ? cleanQuestion(r) : r.question, options: r.options });
  }
  renderChat();
  if (!S.editor) $("chatText").focus();
}
function confirmCard() {
  const { r, ctx, rows } = S.confirm;
  const title = ctx.kind === "start" ? "Here's what I understood. Is this right?" : ctx.kind === "attach" ? "From your attachment. Use these details?" : "Please confirm your answer";
  return h("div", { class: "card", role: "group", "aria-label": "Confirm answer" },
    h("div", { class: "title" }, title),
    h("dl", { class: "diff" }, rows.map((c) => [h("dt", {}, c.label),
      h("dd", {}, c.kept ? [c.new, h("span", { class: "kept" }, "✓ kept")] : c.old ? [h("del", {}, c.old), h("span", { class: "arrow" }, "→"), h("ins", {}, c.new || "removed")] : h("ins", {}, c.new || "removed"))])),
    (r.notes || []).filter((n) => /didn't add|read '/i.test(n)).map((n) => h("div", { class: "warn-text" }, n)),
    ctx.kind === "start" ? h("div", { class: "how" }, r.ai_used ? "Understood with Claude AI." : "Understood with built-in rules (offline mode).") : null,
    h("div", { class: "btns" },
      h("button", { type: "button", class: "grow", title: "Clear it and answer this question again", onclick: () => undoConfirm(false) }, "Change"),
      h("button", { type: "button", title: "Put your words back in the message box to correct them", onclick: () => undoConfirm(true) }, "Edit"),
      h("button", { type: "button", class: "primary", id: "confirmBtn", onclick: () => commit(r, ctx, true) }, "✓ Confirm")));
}
function undoConfirm(keepText) {
  const { ctx } = S.confirm; S.confirm = null;
  S.chat.pop();                                                   // the message that produced this answer
  if (keepText) { $("chatText").value = ctx.text || ""; S.files = ctx.files.slice(); renderFiles(); }
  else { $("chatText").value = ""; if (ctx.kind === "start") { S.files = []; renderFiles(); } }
  renderChat(); $("chatText").focus();
}

/* ---- final card ---- */
function summaryCard(p) {
  const rows = [["Search name", p.name], ["Job titles", (p.roles || []).join(", ")], ["Experience", p.experience],
    ["Locations", (p.locations || []).join(", ") + (p.remote_international ? " + remote jobs abroad" : "")], ["Work arrangement", p.work_arrangement],
    ["Must-have skills", (p.skills || []).join(", ")], ["Minimum salary", p.min_salary || "not set"], ["Industries", (p.industries || []).join(", ")],
    ["Avoid", (p.exclude || []).join(", ")], ["Report email", p.email || "no email (results in this app)"]].filter(([, v]) => v);
  return h("div", { class: "summary card" }, h("b", {}, "Here's the search I'll run"),
    h("dl", {}, rows.map(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])),
    h("div", { class: "edit-hint" }, "Use Edit to change one or more sections, or type a change like 'add Chennai' or 'make it hybrid'."),
    h("div", { class: "btns" },
      h("button", { type: "button", class: "grow", onclick: restartAsk }, S.armRestart ? "Press again to clear" : "Start over"),
      h("button", { type: "button", onclick: () => openEditor(null) }, "Edit"),
      h("button", { type: "button", onclick: (e) => saveSearch(false, e.target) }, "Save"),
      h("button", { type: "button", class: "primary", onclick: (e) => saveSearch(true, e.target) }, "Save and scan")));
}
function restartAsk() {
  const hasAnswers = S.intake && (S.prog ? S.prog.done : 0) > 0;
  if (hasAnswers && !S.armRestart) { S.armRestart = true; renderChat(); toast("Press Start over again to clear all answers.", "warn"); setTimeout(() => { S.armRestart = false; if (S.done) renderChat(); }, 5000); return; }
  restart();
}
function restart() { S.chat = [{ role: "bot", text: GREETING }]; S.intake = null; S.done = null; S.confirm = null; S.editor = null; S.prog = null; S.armRestart = false; renderChat(); }

/* ---- section editor ---- */
const MODE_HELP = { overwrite: "Replace what's saved with what you type.", add: "Keep what's saved and add what you type.", edit: "Remove or correct individual items, and add new ones." };
function openEditor(keys) {
  if (!S.intake) return;
  S.editor = { step: keys ? "edit" : "pick", keys: keys || [], i: 0, sel: new Set(keys || []), updated: [], error: null, preview: null };
  if (keys) prepSection();
  renderChat();
}
function prepSection() {
  const e = S.editor, k = e.keys[e.i], sec = SEC(k), p = S.intake.profile || {};
  const cur = p[k];
  e.error = null; e.preview = null; e.warning = null;
  e.items = Array.isArray(cur) ? cur.slice() : [];
  e.mode = sec.kind === "list" ? (e.items.length ? "edit" : "overwrite") : (sec.kind === "bool" || sec.kind === "choice") ? "overwrite" : (cur ? "edit" : "overwrite");
  e.text = sec.kind === "list" || sec.kind === "bool" || sec.kind === "choice" ? "" : (e.mode === "edit" ? showVal(p, k) : "");
  e.choice = sec.kind === "bool" ? (cur === true ? "Yes" : cur === false ? "No" : "") : sec.kind === "choice" ? (cur || "") : "";
}
function editorCard() {
  const e = S.editor, p = S.intake.profile || {};
  if (e.step === "pick") {
    return h("div", { class: "card" }, h("div", { class: "title", id: "edH" }, "Which section would you like to edit?"),
      h("div", { class: "small muted" }, "Pick one or more. Only those questions are shown; everything else stays as it is."),
      h("div", { class: "picks", role: "group", "aria-labelledby": "edH" }, SECTIONS.map((s) => h("label", {},
        h("input", { type: "checkbox", checked: e.sel.has(s.key), onchange: (ev) => { ev.target.checked ? e.sel.add(s.key) : e.sel.delete(s.key); renderChat(); } }),
        h("span", {}, s.label), h("span", { class: "v" }, showVal(p, s.key) || "not set")))),
      h("div", { class: "btns" },
        h("button", { type: "button", class: "grow linkish", onclick: () => { SECTIONS.forEach((s) => e.sel.add(s.key)); renderChat(); } }, "Select all"),
        h("button", { type: "button", onclick: closeEditor }, "Cancel"),
        h("button", { type: "button", class: "primary", disabled: !e.sel.size, onclick: () => { e.keys = SECTIONS.map((s) => s.key).filter((k) => e.sel.has(k)); e.i = 0; e.step = "edit"; prepSection(); renderChat(); } },
          `Edit selected (${e.sel.size})`)));
  }
  const k = e.keys[e.i], sec = SEC(k), n = e.keys.length;
  const head = h("div", { class: "row" }, h("div", { class: "title" }, `Editing ${sec.label}`), n > 1 ? h("span", { class: "small muted" }, `${e.i + 1} of ${n}`) : null);
  if (e.step === "review") {
    const r = e.preview, c = r.changes || [];
    return h("div", { class: "card" }, head,
      c.length ? h("dl", { class: "diff" }, c.map((x) => [h("dt", {}, x.label), h("dd", {}, x.old ? [h("del", {}, x.old), h("span", { class: "arrow" }, "→")] : null, h("ins", {}, x.new || "removed"))]))
        : h("div", { class: "muted small" }, "That's the same as what's saved, so nothing will change."),
      r.warning ? h("div", { class: "warn-text" }, r.warning) : null,
      h("div", { class: "btns" }, h("button", { type: "button", class: "grow", onclick: () => { e.step = "edit"; renderChat(); } }, "Back"),
        h("button", { type: "button", class: "primary", id: "edConfirm", onclick: confirmEdit }, c.length ? "✓ Confirm change" : "Keep as is")));
  }
  const cur = showVal(p, k);
  const quick = (sec.options || []).filter((o) => o !== "Skip");
  let body;
  if (sec.kind === "bool" || sec.kind === "choice") {
    const opts = sec.kind === "bool" ? ["Yes", "No"] : ["Remote", "Hybrid", "Onsite", "Any"];
    body = [h("div", { class: "small" }, sec.ask),
      h("div", { class: "modes", role: "radiogroup", "aria-label": sec.label }, opts.map((o) => h("button", { type: "button", role: "radio", "aria-checked": String(e.choice.toLowerCase() === o.toLowerCase()), "aria-pressed": String(e.choice.toLowerCase() === o.toLowerCase()),
        onclick: () => { e.choice = o; renderChat(); } }, o)))];
  } else {
    const modes = sec.kind === "list" ? ["overwrite", "add", "edit"] : ["overwrite", "edit"];
    const label = { overwrite: "Overwrite existing", add: "Add to existing", edit: "Edit existing" };
    const inp = h("input", { id: "edText", value: e.text, placeholder: sec.kind === "list" ? (e.mode === "edit" ? "Add or correct items, comma separated" : "Type values, comma separated") : sec.ask,
      oninput: (ev) => { e.text = ev.target.value; }, onkeydown: (ev) => { if (ev.key === "Enter") { ev.preventDefault(); previewEdit(); } } });
    body = [
      h("div", { class: "small" }, h("span", { class: "muted" }, "Saved now: "), cur || "not set"),
      cur ? [h("div", { class: "small", style: "font-weight:600" }, "How would you like to update this information?"),
        h("div", { class: "modes", role: "radiogroup" }, modes.map((m) => h("button", { type: "button", role: "radio", "aria-checked": String(e.mode === m), "aria-pressed": String(e.mode === m),
          onclick: () => { e.mode = m; e.error = null; if (sec.kind !== "list") e.text = m === "edit" ? cur : ""; renderChat(); setTimeout(() => $("edText") && $("edText").focus(), 0); } }, label[m]))),
        h("div", { class: "mode-help" }, MODE_HELP[e.mode])] : null,
      sec.kind === "list" && e.mode === "edit" ? h("div", { class: "tags" }, e.items.length ? e.items.map((it, i) => h("span", { class: "tag" }, it,
        h("button", { type: "button", "aria-label": "Remove " + it, onclick: () => { e.items.splice(i, 1); renderChat(); } }, "×"))) : h("span", { class: "small muted" }, "All items removed.")) : null,
      inp,
      quick.length ? h("div", { class: "opts" }, quick.map((o) => h("button", { type: "button", onclick: () => {
        if (sec.kind === "list") { e.text = e.text.trim() ? e.text.replace(/[,\s]*$/, "") + ", " + o : o; } else e.text = o; renderChat(); } }, o))) : null];
  }
  return h("div", { class: "card" }, head, body,
    e.error ? h("div", { class: "err-text", role: "alert" }, e.error) : null,
    h("div", { class: "btns" },
      h("button", { type: "button", class: "grow", onclick: closeEditor }, "Cancel editing"),
      n > 1 ? h("button", { type: "button", onclick: nextSection }, "Skip") : null,
      h("button", { type: "button", class: "primary", onclick: previewEdit }, "Review change")));
}
async function previewEdit() {
  const e = S.editor, k = e.keys[e.i], sec = SEC(k);
  const text = sec.kind === "bool" || sec.kind === "choice" ? e.choice : e.text;
  if ((sec.kind === "bool" || sec.kind === "choice") && !text) { e.error = "Choose one option."; return renderChat(); }
  try {
    const r = await api("POST", "/api/intake/set", { state: S.intake, key: k, text, mode: e.mode, items: e.mode === "edit" ? e.items : null });
    if (r.error) { e.error = r.error; return renderChat(); }
    e.preview = r; e.step = "review"; renderChat(); setTimeout(() => $("edConfirm") && $("edConfirm").focus(), 0);
  } catch (err) { e.error = "Couldn't check that: " + err.message; renderChat(); }
}
function confirmEdit() {
  const e = S.editor, r = e.preview;
  if ((r.changes || []).length) {
    S.intake = r.state; S.prog = r.progress || S.prog;
    if (r.profile && (S.done || r.done)) S.done = r.profile;
    e.updated.push(SEC(e.keys[e.i]).label);
  }
  nextSection();
}
function nextSection() {
  const e = S.editor;
  if (e.i + 1 < e.keys.length) { e.i++; e.step = "edit"; prepSection(); renderChat(); setTimeout(() => $("edText") && $("edText").focus(), 0); return; }
  const upd = e.updated; S.editor = null;
  if (upd.length) { S.chat.push({ role: "ok", text: "Updated: " + upd.join(", ") }); toast("Your changes have been saved successfully!"); flashStatus("success"); }
  else toast("No changes made.", "info");
  renderChat();
}
function closeEditor() { const upd = S.editor.updated; S.editor = null; if (upd.length) { S.chat.push({ role: "ok", text: "Updated: " + upd.join(", ") }); toast("Your changes have been saved successfully!"); } renderChat(); }

/* ---- sending ---- */
async function send(text) {
  text = (text || "").trim();
  if (S.editor) return toast("Finish or cancel the edit first.", "warn");
  if (S.files.some((f) => f.status === "uploading")) { flash($("chatMsg"), "Wait a moment, still reading your attachment.", true); return; }
  if (S.review) return toast("Review the attachment first: press Use these details or Remove.", "warn");
  if (S.confirm) {
    if (!text) return commit(S.confirm.r, S.confirm.ctx, true);    // Enter on an empty box confirms
    S.confirm = null; S.chat.pop();                                   // typed a different answer instead
  }
  const files = S.files.filter((f) => f.id);
  if (!text && !files.length) return;
  S.chat.push({ role: "me", text, files }); S.files = []; renderFiles();
  $("chatText").value = ""; renderChat();
  $("send").disabled = true;
  const ids = files.filter((f) => !f.noIntake).map((f) => f.id);
  const kind = !S.intake ? "start" : (ids.length && !text ? "attach" : "answer");
  busy(true, "Understanding");
  try {
    let r;
    if (!S.intake) r = await api("POST", "/api/intake/start", { description: text, attachment_ids: ids });
    else {
      const before = clone(S.intake);
      if (ids.length) r = await api("POST", "/api/intake/attach", { state: S.intake, attachment_ids: ids });
      if (text) { const r2 = await api("POST", "/api/intake/answer", { state: r ? r.state : S.intake, answer: text });
        if (r) { r2.changes = mergeChanges(r.changes, r2.changes); } r = r2; }
      if (!r) { busy(false); renderChat(); return; }
      if (!r.asked_key) r.asked_key = before.pending;
    }
    handleResult(r, { kind, text, files });
  } catch (e) {
    S.chat.pop(); S.files = files; renderFiles(); $("chatText").value = text;
    toast(e.message, "err", [["Retry", () => send($("chatText").value)]]); flashStatus("error");
  } finally { busy(false); $("send").disabled = !!S.editor; renderChat(); if (S.confirm) setTimeout(() => $("confirmBtn") && $("confirmBtn").focus(), 0); }
}
function mergeChanges(a, b) {
  const out = (a || []).map((x) => ({ ...x }));
  for (const c of b || []) { const o = out.find((x) => x.key === c.key); if (o) o.new = c.new; else out.push(c); }
  return out.filter((x) => x.old !== x.new);
}

/* ---------------- attachments, screenshots, review ---------------- */
S.files = []; S.recording = null; S.review = null;
const OK_EXT = /\.(pdf|docx|txt|md|rtf|png|jpe?g|webp|gif|webm|ogg|mp3|wav|m4a)$/i;
function renderFiles() {
  $("files").replaceChildren(...S.files.map((f, i) => h("div", { class: "file" + (f.status === "error" ? " err" : ""), title: f.note || "" },
    f.kind === "image" && f.preview ? h("img", { src: f.preview, alt: "" }) : null,
    f.status === "uploading" ? h("span", { class: "spin", style: "color:var(--accent)" }) : null,
    h("span", { class: "nm" }, f.filename),
    h("span", { class: "st" }, f.status === "uploading" ? (f.kind === "image" ? "Reading text (OCR)…" : "Reading…") : f.status === "error" ? "Failed" : f.reviewed ? "Ready" : f.has_text ? "Read" : "Saved"),
    f.status === "error" && f.blob ? h("button", { type: "button", title: "Try again", onclick: () => { S.files.splice(i, 1); upload(f.blob, f.filename, f.extra); } }, "↻") : null,
    f.status === "done" && !f.noIntake ? h("button", { type: "button", title: "Review what was read", onclick: () => openReview(f) }, "✎") : null,
    h("button", { type: "button", "aria-label": "Remove " + f.filename, onclick: () => { S.files.splice(i, 1); if (S.review === f) S.review = null; renderFiles(); renderReview(); } }, "×"))));
}
const toB64 = (blob) => new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.onerror = rej; fr.readAsDataURL(blob); });
async function upload(blob, filename, extra) {
  if (!OK_EXT.test(filename) && !/^(image|audio)\//.test(blob.type || "")) {
    toast(`“${filename}” isn't a supported file. Use PDF, Word (.docx), TXT, MD, RTF, an image or an audio file.`, "err"); return null; }
  if (blob.size > 15 * 1024 * 1024) { toast(`“${filename}” is ${(blob.size / 1048576).toFixed(1)} MB. The limit is 15 MB per file.`, "err"); return null; }
  if (!blob.size) { toast(`“${filename}” is empty.`, "err"); return null; }
  if (S.files.length >= 10) { toast("Up to 10 files per message.", "err"); return null; }
  const isImg = (blob.type || "").startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(filename);
  const f = { filename, blob, extra, status: "uploading", kind: isImg ? "image" : (blob.type || "").startsWith("audio/") ? "voice" : "document", preview: isImg ? URL.createObjectURL(blob) : null, noIntake: extra && extra.interpret === false };
  S.files.push(f); renderFiles(); busy(true, isImg ? "Reading image" : "Processing");
  try {
    const rec = await api("POST", "/api/attachments", { filename, mime: blob.type, data: await toB64(blob), ...(extra || {}) });
    Object.assign(f, rec, { status: "done" });
    if (f.noIntake) { toast("Voice recording uploaded successfully!"); flashStatus("success"); }
    else if (!rec.has_text) { toast(rec.problem || rec.note, "warn", rec.kind === "image" ? [["Open Settings", openAISettings]] : []); flashStatus("error"); openReview(f); }
    else { toast(f.kind === "image" ? `Screenshot processed: text read with ${rec.text_engine}.` : `${rec.filename} processed successfully!`); flashStatus("success"); openReview(f); }
  } catch (e) {
    f.status = "error"; f.note = e.message; flashStatus("error");
    toast(`Upload failed for “${filename}”: ${e.message}`, "err", [["Retry", () => { S.files.splice(S.files.indexOf(f), 1); upload(blob, filename, extra); }]]);
  } finally { busy(false); renderFiles(); }
  return f;
}
const FIELD_LABELS = { roles: "Job titles", skills: "Skills", experience: "Experience", locations: "Locations", work_arrangement: "Work arrangement",
  remote_international: "Remote jobs abroad", min_salary: "Minimum salary", industries: "Industries", exclude: "Avoid", email: "Report email", name: "Search name" };
const DOC_LABEL = { resume: "Resume", job_post: "Job post", brief: "Job search brief", notes: "Notes" };
function openReview(f) { S.review = f; f.draft = clone(f.extracted || {}); f.textDraft = f.text || ""; renderReview(); $("attachPanel").hidden = true; }
function renderReview() {
  const box = $("review"), f = S.review;
  if (!f) { box.replaceChildren(); return; }
  const d = f.draft || {};
  const keys = Object.keys(FIELD_LABELS).filter((k) => d[k] != null && d[k] !== "" && !(Array.isArray(d[k]) && !d[k].length));
  const ta = h("textarea", { "aria-label": "Text read from the file", oninput: (e) => { f.textDraft = e.target.value; } }); ta.value = f.textDraft || "";
  box.replaceChildren(h("div", { class: "popover review", role: "group", "aria-label": "Review attachment" },
    h("div", { class: "row" }, h("h3", {}, "Review: " + f.filename), h("span", { class: "chip info" }, f.has_text ? (DOC_LABEL[f.doc_type] || "File") : "Not read")),
    f.has_text ? h("div", { class: "how" }, "Text read by: " + (f.text_engine || "—") + " · Details found by: " + (f.fields_engine || "built-in rules")) :
      h("div", { class: "svc-line bad" }, f.problem || f.note),
    keys.length ? h("div", { style: "display:grid;gap:8px" }, h("div", { class: "small", style: "font-weight:600" }, "Details I'll add to the search (remove anything wrong):"),
      keys.map((k) => h("div", { class: "fieldrow" }, h("span", {}, FIELD_LABELS[k]),
        h("div", { class: "tags" }, (Array.isArray(d[k]) ? d[k] : [k === "remote_international" ? (d[k] ? "Yes" : "No") : d[k]]).map((v, i) => h("span", { class: "tag" }, String(v),
          h("button", { type: "button", "aria-label": `Remove ${v}`, onclick: () => { if (Array.isArray(d[k])) d[k].splice(i, 1); else delete d[k]; renderReview(); } }, "×"))))))) :
      f.has_text ? h("div", { class: "warn-text" }, "I couldn't find job details (titles, skills, experience or locations) in this file. Correct the text below and press Re-read, or type the details in the chat.") : null,
    (f.missing || []).length && keys.length ? h("div", { class: "small muted" }, "Not found: " + f.missing.join(", ") + ". I'll ask about these next.") : null,
    f.has_text || f.kind === "image" ? h("details", { open: !keys.length && f.has_text }, h("summary", { class: "small", style: "cursor:pointer" }, f.has_text ? "Show and edit the text that was read" : "Type the text from the image"),
      h("div", { style: "display:grid;gap:6px;margin-top:6px" }, ta, h("button", { type: "button", style: "justify-self:start", onclick: () => rereadText(f) }, "Re-read details from this text"))) : null,
    h("div", { class: "btns" },
      h("button", { type: "button", class: "grow", onclick: () => { S.files.splice(S.files.indexOf(f), 1); S.review = null; renderFiles(); renderReview(); } }, "Remove file"),
      f.kind === "image" && !f.has_text ? h("button", { type: "button", onclick: openAISettings }, "Set up OCR") : null,
      h("button", { type: "button", class: "primary", onclick: () => useReviewed(f) }, keys.length ? "Use these details" : "Attach anyway"))));
}
async function rereadText(f) {
  busy(true, "Re-reading");
  try { const r = await api("POST", "/api/attachments/update", { id: f.id, text: f.textDraft });
    Object.assign(f, r); f.draft = clone(r.extracted || {}); renderReview(); toast("Text re-read: details updated."); }
  catch (e) { toast("Couldn't re-read: " + e.message, "err", [["Retry", () => rereadText(f)]]); }
  finally { busy(false); }
}
async function useReviewed(f) {
  try {
    if (JSON.stringify(f.draft) !== JSON.stringify(f.extracted)) { const r = await api("POST", "/api/attachments/update", { id: f.id, extracted: f.draft }); Object.assign(f, r); }
    f.reviewed = true; S.review = null; renderFiles(); renderReview();
    send($("chatText").value);
  } catch (e) { toast("Couldn't save your corrections: " + e.message, "err", [["Retry", () => useReviewed(f)]]); }
}
function togglePanel(id, btn) { const p = $(id); const open = p.hidden; ["attachPanel", "voicePanel"].forEach((x) => { $(x).hidden = true; }); p.hidden = !open; if (btn) btn.setAttribute("aria-expanded", String(open)); return open; }
document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => { $(b.dataset.close).hidden = true; }));
$("attachBtn").addEventListener("click", (e) => togglePanel("attachPanel", e.currentTarget));
$("chooseFiles").addEventListener("click", () => $("fileInput").click());
$("fileInput").addEventListener("change", (e) => { $("attachPanel").hidden = true; [...e.target.files].forEach((f) => upload(f, f.name)); e.target.value = ""; });
$("chatText").addEventListener("paste", (e) => {
  const imgs = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith("image/"));
  if (imgs.length) { e.preventDefault(); imgs.forEach((f, i) => upload(f, `pasted-image-${Date.now()}${i ? "-" + i : ""}.png`)); }
});
const comp = $("composer");
comp.addEventListener("dragover", (e) => { e.preventDefault(); comp.classList.add("drag"); });
comp.addEventListener("dragleave", () => comp.classList.remove("drag"));
comp.addEventListener("drop", (e) => { e.preventDefault(); comp.classList.remove("drag"); [...e.dataTransfer.files].forEach((f) => upload(f, f.name)); });

$("shotBtn").addEventListener("click", async () => {
  if (S.svc && S.svc.ocr.state !== "ready") toast("OCR isn't available, so text in the screenshot won't be read automatically. You can type it in the review box, or set up OCR.", "warn", [["Open Settings", openAISettings]]);
  if (!navigator.mediaDevices?.getDisplayMedia) { toast("Screenshots need a recent Edge or Chrome. You can also paste one: Win+Shift+S, then Ctrl+V in the message box.", "err"); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false }); }
  catch { toast("Screenshot cancelled. Tip: Win+Shift+S, then Ctrl+V in the message box also works.", "info"); return; }
  try {
    const video = document.createElement("video"); video.srcObject = stream; video.muted = true; await video.play();
    await new Promise((r) => setTimeout(r, 400));
    const c = document.createElement("canvas"); c.width = video.videoWidth; c.height = video.videoHeight;
    c.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((r) => c.toBlob(r, "image/png"));
    await upload(blob, `screenshot-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.png`);
  } finally { stream.getTracks().forEach((t) => t.stop()); }
});

/* ---------------- voice: sample, record, review, transcript ---------------- */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const V = { phase: "idle", blob: null, url: null, transcript: "", secs: 0 };
const sampleAudio = new Audio("/samples/sample-voice.mp3"); sampleAudio.preload = "none";
sampleAudio.addEventListener("ended", () => renderVoice());
function fmtSecs(s) { return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }
function renderVoice() {
  const p = $("voicePanel");
  const playing = !sampleAudio.paused;
  const parts = [h("div", { class: "row" }, h("h3", {}, "Voice note"), h("button", { type: "button", class: "linkish", onclick: () => { if (V.phase !== "recording") { $("voicePanel").hidden = true; $("micBtn").setAttribute("aria-expanded", "false"); } } }, "Close")),
    h("div", { class: "small" }, "Say clearly: the job title, years of experience, cities, remote or hybrid, your main skills and minimum salary."),
    h("div", { class: "row", style: "justify-content:flex-start" },
      h("button", { type: "button", onclick: () => { playing ? sampleAudio.pause() : (sampleAudio.currentTime = 0, sampleAudio.play().catch(() => toast("Couldn't play the sample.", "err"))); setTimeout(renderVoice, 50); } }, playing ? "■ Stop sample" : "▶ Play sample voice"),
      h("a", { class: "btn", href: "/samples/sample-voice.mp3?download=1", download: "job-radar-sample-voice.mp3" }, "Download sample audio")),
    h("div", { class: "svc-line " + (SR ? "ok" : "bad") }, SR ? "✓ Speech-to-text available (browser speech service; needs internet)." : "✕ Speech-to-text is unavailable in this browser, so your words won't be typed automatically. The recording is still saved; type the details in the box. Use Edge or Chrome for transcription.")];
  if (V.phase === "idle") parts.push(h("button", { type: "button", class: "primary", style: "justify-self:start", onclick: startVoice }, "● Start recording"));
  if (V.phase === "recording") parts.push(
    h("div", { class: "recbar" }, h("span", { class: "recdot" }), h("b", { id: "recTime" }, fmtSecs(V.secs)), h("div", { class: "level" }, h("i", { id: "recLevel" })),
      h("button", { type: "button", class: "danger", onclick: stopVoice }, "■ Stop recording")),
    h("div", { class: "live-tx", id: "liveTx" }, V.transcript || (SR ? "Listening…" : "Recording…")));
  if (V.phase === "review") {
    const ta = h("textarea", { id: "vTx", rows: 3, "aria-label": "Transcript", oninput: (e) => { V.transcript = e.target.value; } }); ta.value = V.transcript;
    parts.push(h("audio", { controls: true, src: V.url, style: "width:100%" }),
      h("label", { for: "vTx" }, SR ? "Transcript – check it and correct anything misheard" : "Type what you said (no automatic transcript in this browser)", ta),
      h("div", { class: "btns" }, h("button", { type: "button", class: "grow", onclick: discardVoice }, "Discard"),
        h("button", { type: "button", onclick: () => { discardVoice(); startVoice(); } }, "Re-record"),
        h("button", { type: "button", class: "primary", onclick: useVoice }, "Use this recording")));
  }
  p.replaceChildren(...parts);
}
$("micBtn").addEventListener("click", (e) => { if (togglePanel("voicePanel", e.currentTarget)) renderVoice(); });
async function startVoice() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return toast("This browser can't record audio. Use Microsoft Edge or Google Chrome.", "err");
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { toast("Microphone access was blocked. Allow it from the icon in the address bar, then try again.", "err", [["Retry", startVoice]]); return; }
  sampleAudio.pause();
  const chunks = [], rec = new MediaRecorder(stream);
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const st = { stream, rec, chunks, started: Date.now(), rec2: null, fin: "" };
  V.phase = "recording"; V.transcript = ""; V.secs = 0; renderVoice();
  if (SR) {
    const r2 = new SR(); r2.lang = "en-IN"; r2.continuous = true; r2.interimResults = true;
    r2.onresult = (e) => { let fin = "", interim = ""; for (const res of e.results) (res.isFinal ? (fin += res[0].transcript + " ") : (interim += res[0].transcript));
      st.fin = fin.trim(); V.transcript = (fin + interim).trim(); const lt = $("liveTx"); if (lt) lt.textContent = V.transcript || "Listening…"; };
    r2.onerror = (ev) => { if (ev.error === "network") toast("Speech-to-text needs internet; the recording continues without a transcript.", "warn"); };
    r2.onend = () => { if (S.recording === st) try { r2.start(); } catch {} };
    try { r2.start(); st.rec2 = r2; } catch {}
  }
  try {                                                         // live microphone level
    const ac = new (window.AudioContext || window.webkitAudioContext)(); const an = ac.createAnalyser(); an.fftSize = 256;
    ac.createMediaStreamSource(stream).connect(an); const buf = new Uint8Array(an.frequencyBinCount); st.ac = ac;
    const loop = () => { if (S.recording !== st) return; an.getByteTimeDomainData(buf); let m = 0; for (const x of buf) m = Math.max(m, Math.abs(x - 128));
      const el = $("recLevel"); if (el) el.style.width = Math.min(100, m * 1.6) + "%"; requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  } catch {}
  rec.start(); S.recording = st;
  $("micBtn").setAttribute("aria-pressed", "true"); $("micLabel").textContent = "Recording";
  st.timer = setInterval(() => { V.secs = Math.round((Date.now() - st.started) / 1000); const t = $("recTime"); if (t) t.textContent = fmtSecs(V.secs); if (V.secs >= 300) stopVoice(); }, 500);
}
async function stopVoice() {
  const st = S.recording; if (!st) return;
  S.recording = null; clearInterval(st.timer);
  $("micBtn").setAttribute("aria-pressed", "false"); $("micLabel").textContent = "Voice";
  if (st.rec2) try { st.rec2.stop(); } catch {}
  if (st.ac) try { st.ac.close(); } catch {}
  await new Promise((r) => { st.rec.onstop = r; st.rec.stop(); });
  st.stream.getTracks().forEach((t) => t.stop());
  V.blob = new Blob(st.chunks, { type: st.rec.mimeType || "audio/webm" });
  if (!V.blob.size) { V.phase = "idle"; renderVoice(); return toast("Nothing was recorded. Check the microphone and try again.", "err", [["Retry", startVoice]]); }
  V.url = URL.createObjectURL(V.blob); V.phase = "review"; V.transcript = (V.transcript || st.fin || "").trim();
  renderVoice(); setTimeout(() => $("vTx") && $("vTx").focus(), 0);
}
function discardVoice() { if (V.url) URL.revokeObjectURL(V.url); Object.assign(V, { phase: "idle", blob: null, url: null, transcript: "" }); renderVoice(); }
async function useVoice() {
  const tx = (V.transcript || "").trim();
  if (!tx) return toast("Add the transcript first (type what you said), so I can use it.", "warn");
  const ext = (V.blob.type.includes("ogg") ? "ogg" : V.blob.type.includes("mp4") ? "m4a" : "webm");
  const f = await upload(V.blob, `voice-note-${fmtSecs(V.secs).replace(":", "m")}s.${ext}`, { transcript: tx, interpret: false });
  if (!f || f.status !== "done") return;
  discardVoice(); $("voicePanel").hidden = true; $("micBtn").setAttribute("aria-expanded", "false");
  $("chatText").value = ($("chatText").value.trim() ? $("chatText").value.trim() + " " : "") + tx;
  send($("chatText").value);
}

async function saveSearch(scan, btn) {
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
  busy(true, "Saving");
  try {
    const r = await api("POST", "/api/profiles", { profile: S.done });
    S.selected = r.id; try { localStorage.setItem("jr-sel", r.id); } catch {}
    const name = S.done.name;
    S.chat = [{ role: "ok", text: `Search “${name}” saved` }, { role: "bot", text: "Want to add another search? Describe it here." }];
    S.intake = null; S.done = null; S.prog = null; renderChat();
    toast(`Search “${name}” saved successfully!`); flashStatus("success");
    await load();
    if (scan) runScan([r.id]);
  } catch (e) {
    toast("Couldn't save: " + e.message, "err", [["Retry", () => saveSearch(scan)]]); flashStatus("error");
    if (btn) { btn.disabled = false; btn.textContent = scan ? "Save and scan" : "Save"; }
  } finally { busy(false); }
}

