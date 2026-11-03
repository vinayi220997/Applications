/* ---------------- dialogs ---------------- */
function modal({ title, body, actions }) {
  const d = $("dlg");
  $("dlgTitle").textContent = title;
  $("dlgBody").replaceChildren(...[].concat(body).filter(Boolean));
  return new Promise((resolve) => {
    const done = (v) => { d.close(); resolve(v); };
    $("dlgActs").replaceChildren(...actions.map((a) => h("button", { type: "button", class: (a.primary ? "primary " : "") + (a.danger ? "danger " : "") + (a.grow ? "grow" : ""),
      onclick: async (e) => { if (a.onClick) { const btn = e.currentTarget; btn.disabled = true; try { const keep = await a.onClick(); if (keep === false) return; } finally { btn.disabled = false; } } done(a.value); } }, a.label)));
    $("dlgX").onclick = () => done(null);
    d.onclose = () => resolve(null);
    d.oncancel = () => resolve(null);
    if (!d.open) d.showModal();
    setTimeout(() => { const f = d.querySelector("#dlgBody input:not([type=hidden]):not([type=checkbox]):not([type=radio]), #dlgBody select"); (f || d.querySelector("#dlgActs .primary") || d.querySelector("#dlgActs button"))?.focus(); }, 30);
  });
}
const confirmBox = (title, text, ok = "OK", danger = false) =>
  modal({ title, body: h("p", { style: "margin:0" }, text), actions: [{ label: "Cancel", value: false }, { label: ok, value: true, primary: !danger, danger }] }).then(Boolean);

/* ---------------- formatting ---------------- */
const fmtDT = (v) => { if (!v) return "—"; const d = new Date(v); return isNaN(d) ? "—" : d.toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }); };
const fmtDur = (s) => s == null ? "—" : s < 60 ? `${s} s` : s < 3600 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`;
const MODE_LABEL = { chart: "Chart mode", questionnaire: "Questionnaire mode" };
const SRC_LABEL = { manual: "Manual entry", file: "Uploaded file", screenshot: "Screenshot (OCR)", voice: "Voice", ai: "AI-assisted", import: "Imported file" };
const modesText = (m) => (m && m.length ? m.map((x) => x === "onsite" ? "On-site" : x[0].toUpperCase() + x.slice(1)).join(", ") : "Any");
const stChip = (label) => h("span", { class: "chip st-" + String(label).replace(/\s+/g, "") }, label);
function switchEl(checked, label, onchange, title) {
  const inp = h("input", { type: "checkbox", role: "switch", "aria-label": title || label, onchange: (e) => onchange(e.target.checked, e.target) });
  inp.checked = !!checked;
  return h("label", { class: "switch", title }, inp, h("span", { class: "track" }), h("span", {}, label));
}

/* ---------------- main tabs ---------------- */
S.cards = []; S.schedules = []; S.tz = []; S.editing = null; S.importing = null; S.sources = new Set(); S.mainTab = "cards";
try { S.mainTab = localStorage.getItem("jr-main") || "cards"; } catch {}
function showTab(t) {
  S.mainTab = t; try { localStorage.setItem("jr-main", t); } catch {}
  for (const [k, pane, tab] of [["cards", "paneCards", "tabCards"], ["schedules", "paneSchedules", "tabSched"], ["results", "paneResults", "tabResults"]]) {
    $(pane).hidden = k !== t; $(tab).setAttribute("aria-selected", String(k === t));
  }
}
document.querySelectorAll(".maintabs [data-tab]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

/* ---------------- job search cards ---------------- */
function renderCards() {
  const box = $("cards");
  $("nCards").textContent = S.cards.length || "";
  if (!S.cards.length) { box.replaceChildren(h("div", { class: "empty" }, "No job search cards yet. Describe a job on the left (Chart or Questionnaire mode), or import a card file.")); return; }
  box.replaceChildren(...S.cards.map(cardEl));
}
function cardEl(c) {
  const e = c.last_exec, m = c.last_email;
  const more = h("details", { class: "more" }, h("summary", { "aria-label": "More actions for " + c.name }, "More ▾"),
    h("div", { class: "menu", role: "menu" },
      h("button", { type: "button", role: "menuitem", onclick: () => exportCard(c) }, "Export card"),
      h("button", { type: "button", role: "menuitem", onclick: () => duplicateCard(c) }, "Duplicate card"),
      c.email ? h("button", { type: "button", role: "menuitem", onclick: (ev) => emailNow(c, ev.currentTarget) }, "Email results now") : null,
      h("button", { type: "button", role: "menuitem", onclick: () => changeEmail(c) }, c.email ? "Change email" : "Add email"),
      c.email ? h("button", { type: "button", role: "menuitem", onclick: () => api("POST", "/api/profiles/" + c.id, { email_on: !c.email_on }).then(() => { toast(c.email_on ? "Daily email turned off." : "Daily email turned on."); load(); }) }, c.email_on ? "Turn daily email off" : "Turn daily email on") : null,
      h("button", { type: "button", role: "menuitem", class: "danger-text", onclick: () => deleteCard(c) }, "Delete card")));
  more.addEventListener("toggle", () => { if (more.open) document.querySelectorAll(".more[open]").forEach((o) => { if (o !== more) o.open = false; }); });
  return h("article", { class: "jc" + (c.active ? "" : " off"), "aria-current": String(S.selected === c.id), "aria-label": c.name, "data-id": c.id },
    h("div", { class: "jc-head" }, h("div", { style: "display:grid;gap:4px;min-width:0" }, h("h3", {}, c.name), h("div", {}, stChip(c.status))),
      switchEl(c.active, c.active ? "On" : "Off", (on, inp) => toggleCard(c, on, inp), c.active ? "Turn this card off" : "Turn this card on")),
    h("div", { class: "jc-body" },
      h("dl", { class: "kv" },
        h("dt", {}, "Cities"), h("dd", {}, h("div", { class: "mini" }, c.cities.map((x) => h("span", {}, x)))),
        h("dt", {}, "Work modes"), h("dd", {}, h("div", { class: "mini" }, (c.work_modes.length ? c.work_modes : ["any"]).map((x) => h("span", {}, modesText(x === "any" ? [] : [x]))))),
        h("dt", {}, "Input mode"), h("dd", {}, MODE_LABEL[c.input_mode] || "Chart mode"),
        h("dt", {}, "Answers from"), h("dd", {}, c.answer_source.map((s) => SRC_LABEL[s] || s).join(", "))),
      h("div", { class: "blk" }, h("h4", {}, "Schedule", stChip(c.schedule_status)),
        c.schedules.length ? h("div", {}, c.schedules.map((s) => s.name + (s.enabled ? "" : " (paused)")).join(", ")) : h("div", { class: "muted" }, "Runs only when you start it."),
        c.next_run_text ? h("div", {}, "Next run: ", h("b", {}, c.next_run_text)) : null,
        c.duplicate_schedules ? h("div", { class: "warn-text" }, "In more than one active schedule, so it may run more than once a day.") : null),
      h("div", { class: "blk" }, h("h4", {}, "Latest search", e ? stChip(e.status === "completed" ? "Completed" : e.status === "running" ? "Running" : e.status === "failed" ? "Failed" : e.status === "stopped" ? "Stopped" : e.status) : null),
        e ? [h("div", {}, fmtDT(e.started_at), h("span", { class: "muted" }, " · " + e.trigger_label)),
             e.status === "running" ? h("div", { class: "scanning", style: "font-size:13px" }, h("span", { class: "radar", style: "width:16px;height:16px" }), "Searching", h("span", { class: "dots" })) :
             h("div", {}, `Jobs found: ${e.jobs_found ?? "—"} · New: ${e.new_jobs ?? "—"} · Duration: ${fmtDur(e.duration_s)}`),
             e.error ? h("div", { class: e.status === "completed" ? "small muted" : "err-line" }, e.error) : null]
          : h("div", { class: "muted" }, "Not run yet."),
        h("div", { class: "muted small" }, `Open matches stored: ${c.total_jobs}`)),
      h("div", { class: "blk" }, h("h4", {}, "Latest email", stChip(c.email_status)),
        m ? [h("div", {}, fmtDT(m.at), m.recipients ? h("span", { class: "muted" }, " · " + m.recipients) : null),
             m.status === "sent" ? h("div", {}, `${m.jobs_included} job${m.jobs_included === 1 ? "" : "s"} included · ${m.emails_sent} email sent`) : null,
             m.error ? h("div", { class: m.status === "failed" ? "err-line" : "small muted" }, m.error) : null]
          : h("div", { class: "muted" }, c.email ? "No email sent yet." : "No email address. Results stay in the app."),
        h("div", { class: "muted small" }, "Next email: " + c.email_next))),
    h("div", { class: "jc-acts" },
      h("button", { type: "button", class: "primary", disabled: !c.active || S.running, title: c.active ? "Run this search now" : "Turn the card on to run it", onclick: () => runScan([c.id]) }, "Run search"),
      h("button", { type: "button", onclick: () => viewResults(c.id) }, "View results"),
      h("button", { type: "button", onclick: () => editCard(c) }, "Edit card"),
      h("button", { type: "button", onclick: () => manageCardSchedules(c) }, "Schedule"),
      h("button", { type: "button", onclick: () => openHistory(c) }, "History"),
      more));
}
document.addEventListener("click", (e) => { if (!e.target.closest(".more")) document.querySelectorAll(".more[open]").forEach((o) => { o.open = false; }); });
async function toggleCard(c, on, inp) {
  try {
    await api("POST", "/api/profiles/" + c.id, { active: on });
    toast(on ? `“${c.name}” is on and will run with its schedules.` : `“${c.name}” is off. It won't run or email automatically; its results and history are kept.`, on ? "ok" : "info");
    load();
  } catch (e) { inp.checked = !on; toast("Couldn't change it: " + e.message, "err"); }
}
async function viewResults(id) { S.selected = id; try { localStorage.setItem("jr-sel", id); } catch {} showTab("results"); await load(); }
async function emailNow(c, btn) {
  btn.disabled = true; busy(true, "Sending email");
  try { const r = await api("POST", `/api/profiles/${c.id}/email-now`, {}); toast(r.message); flashStatus("success"); }
  catch (e) { toast("Not sent: " + e.message, "err", [["Retry", () => emailNow(c, btn)]]); flashStatus("error"); }
  finally { btn.disabled = false; busy(false); load(); }
}
async function changeEmail(c) {
  let inp, on;
  const r = await modal({ title: (c.email ? "Change email for “" : "Add email for “") + c.name + "”",
    body: [h("label", {}, "Report email", inp = h("input", { type: "email", value: c.email || "", placeholder: "you@example.com" })),
           h("label", { class: "inline-check" }, on = h("input", { type: "checkbox", checked: c.email ? c.email_on : true }), "Send the daily email for this card"),
           h("p", { class: "small muted", style: "margin:0" }, "Leave empty to remove the email; results stay in the app.")],
    actions: [{ label: "Cancel", value: null }, { label: "Save", value: "save", primary: true, onClick: async () => {
      const v = inp.value.trim();
      if (v && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { toast("That doesn't look like an email address.", "err"); return false; }
      try { await api("POST", "/api/profiles/" + c.id, { email: v, email_on: !!v && on.checked }); } catch (e) { toast(e.message, "err"); return false; }
    } }] });
  if (r) { toast("Email saved."); load(); }
}
async function deleteCard(c) {
  const shared = c.schedules.filter((s) => s.kind !== "card").map((s) => s.name);
  const ok = await confirmBox(`Delete “${c.name}”?`, "This permanently removes the card, its stored results, history and attachments. " +
    (shared.length ? `It's removed from ${shared.join(", ")}; those schedules stay for their other cards. ` : "") + "To keep it but stop it running, turn it off instead.", "Delete card", true);
  if (!ok) return;
  try { await api("DELETE", "/api/profiles/" + c.id); if (S.selected === c.id) S.selected = null; toast(`“${c.name}” deleted.`); load(); }
  catch (e) { toast("Couldn't delete: " + e.message, "err"); }
}
async function duplicateCard(c) {
  try { const r = await api("POST", `/api/profiles/${c.id}/duplicate`, {}); toast(`Copy created (turned off). Edit it, then turn it on.`); await load(); highlightCard(r.id); }
  catch (e) { toast("Couldn't duplicate: " + e.message, "err"); }
}
function highlightCard(id) { showTab("cards"); setTimeout(() => { const el = document.querySelector(`.jc[data-id="${id}"]`); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.animate([{ boxShadow: "0 0 0 4px var(--accent)" }, { boxShadow: "0 0 0 0 transparent" }], { duration: 1600 }); } }, 50); }
async function exportCard(c) {
  let withEmail;
  const ok = await modal({ title: `Export “${c.name}”`, body: [
    h("p", { style: "margin:0" }, "Saves the card as a .json file you can keep as a backup or share. Another Job Radar can import it."),
    h("div", { class: "note" }, "Included: name, job titles, experience, cities, work modes, skills, salary, exclusions, notes, input mode and the card's own schedule. ",
      h("b", {}, "Never included:"), " passwords, API keys, email settings, results or history."),
    c.email ? h("label", { class: "inline-check" }, withEmail = h("input", { type: "checkbox" }), `Include the report email address (${c.email})`) : null],
    actions: [{ label: "Cancel", value: false }, { label: "Download .json", value: true, primary: true }] });
  if (!ok) return;
  const a = h("a", { href: `/api/profiles/${c.id}/export${withEmail && withEmail.checked ? "?email=1" : ""}`, download: "" });
  document.body.append(a); a.click(); a.remove();
  toast("Card exported. Check your Downloads folder."); setTimeout(load, 800);
}

/* ---------------- history ---------------- */
const ACT_ICON = { created: ["+", "ok"], updated: ["✎", "info"], enabled: ["●", "ok"], disabled: ["○", "warn"], search_started: ["▶", "info"], search_completed: ["✓", "ok"],
  search_failed: ["!", "bad"], search_stopped: ["■", "warn"], search_skipped: ["↷", "warn"], email_sent: ["✉", "ok"], email_failed: ["!", "bad"], email_skipped: ["↷", "warn"],
  exported: ["⇩", "info"], imported: ["⇧", "info"], duplicated: ["⧉", "info"], schedule: ["⏱", "info"], email: ["✉", "info"] };
async function openHistory(c) {
  let data;
  try { data = await api("GET", `/api/profiles/${c.id}/history`); } catch (e) { return toast("Couldn't load history: " + e.message, "err"); }
  let tab = "activity";
  const box = h("div", { style: "display:grid;gap:10px" });
  const draw = () => {
    const seg = h("div", { class: "seg2", role: "tablist" }, [["activity", `Activity (${data.activity.length})`], ["searches", `Searches (${data.executions.length})`], ["emails", `Emails (${data.emails.length})`]]
      .map(([k, l]) => h("button", { type: "button", role: "tab", "aria-pressed": String(tab === k), onclick: () => { tab = k; draw(); } }, l)));
    let body;
    if (tab === "activity") body = data.activity.length ? h("ol", { class: "timeline" }, data.activity.map((a) => { const [ic, cl] = ACT_ICON[a.kind] || ["•", ""];
      return h("li", {}, h("span", { class: "ic " + cl, "aria-hidden": "true" }, ic), h("div", {}, h("time", {}, fmtDT(a.at)), a.detail)); })) : h("div", { class: "empty" }, "No activity yet.");
    else if (tab === "searches") body = data.executions.length ? h("div", { class: "tblwrap" }, h("table", { class: "tbl" },
      h("thead", {}, h("tr", {}, ["Started", "Finished", "Status", "Found", "New", "Saved", "Duration", "Triggered by", ""].map((x) => h("th", {}, x)))),
      h("tbody", {}, data.executions.map((x) => h("tr", {}, h("td", {}, fmtDT(x.started_at)), h("td", {}, fmtDT(x.finished_at)), h("td", {}, stChip(x.status[0].toUpperCase() + x.status.slice(1)), x.error ? h("div", { class: x.status === "completed" ? "small muted" : "err-line" }, x.error) : null),
        h("td", {}, x.jobs_found ?? "—"), h("td", {}, x.new_jobs ?? "—"), h("td", {}, x.saved ?? "—"), h("td", {}, fmtDur(x.duration_s)), h("td", {}, x.trigger_label),
        h("td", {}, x.status === "failed" && c.active ? h("button", { type: "button", onclick: () => { $("dlg").close(); runScan([c.id], "retry"); } }, "Retry") : null)))))) : h("div", { class: "empty" }, "This card hasn't run yet.");
    else body = data.emails.length ? h("div", { class: "tblwrap" }, h("table", { class: "tbl" },
      h("thead", {}, h("tr", {}, ["Date", "Status", "Jobs", "To", "Search run", "Details"].map((x) => h("th", {}, x)))),
      h("tbody", {}, data.emails.map((x) => { const ex = data.executions.find((y) => y.id === x.execution_id);
        return h("tr", {}, h("td", {}, fmtDT(x.at)), h("td", {}, stChip(x.status[0].toUpperCase() + x.status.slice(1))), h("td", {}, x.jobs_included ?? 0), h("td", {}, x.recipients || "—"),
          h("td", {}, ex ? fmtDT(ex.started_at) : (x.execution_id ? "#" + x.execution_id : "Email results now")), h("td", {}, x.error || x.subject || "")); })))) : h("div", { class: "empty" }, "No email activity yet.");
    box.replaceChildren(seg, body,
      h("p", { class: "small muted", style: "margin:0" }, "'Sent' means Gmail accepted the email for delivery. Job Radar can't see whether it reached the inbox or spam."));
  };
  draw();
  modal({ title: `History: ${c.name}`, body: box, actions: [{ label: "Close", value: null, primary: true }] });
}

/* ---------------- schedules ---------------- */
const SDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
function renderSchedules() {
  $("nSched").textContent = S.schedules.length || "";
  const live = S.schedules.filter((s) => s.enabled && s.cards.some((c) => c.active));
  const nxt = live.map((s) => s.next_run).filter(Boolean).sort()[0];
  const ns = live.find((s) => s.next_run === nxt);
  $("schedText").textContent = live.length ? `${live.length} active schedule${live.length > 1 ? "s" : ""}` + (ns ? ` · next: ${ns.next_run_text}` : "") : "Not scheduled";
  const box = $("schedList");
  if (!S.schedules.length) { box.replaceChildren(h("div", { class: "empty" }, "No schedules yet. Create one here to run several cards at the same time, or use Schedule on a card to give it its own time.")); return; }
  box.replaceChildren(...S.schedules.map((s) => h("article", { class: "sc" + (s.enabled ? "" : " off") },
    h("div", { class: "sc-head" }, h("div", { style: "display:grid;gap:3px;min-width:0" },
        h("h3", { style: "font-size:16px" }, s.name, " ", h("span", { class: "chip" }, s.kind === "card" ? "Card schedule" : "Shared"), s.is_default ? h("span", { class: "chip info", title: "New cards are added to this schedule" }, " Default for new cards") : null),
        h("div", { class: "small" }, s.text)),
      switchEl(s.enabled, s.enabled ? "On" : "Paused", (on, inp) => toggleSchedule(s, on, inp), s.enabled ? "Pause this schedule" : "Turn this schedule on")),
    h("dl", { class: "kv" },
      h("dt", {}, "Cards"), h("dd", {}, s.cards.length ? h("div", { class: "mini" }, s.cards.map((c) => h("span", { title: c.active ? "" : "Card is off, so it won't run" }, c.name + (c.active ? "" : " (off)")))) : h("span", { class: "warn-text" }, "No cards linked, so it never runs.")),
      h("dt", {}, "Next run"), h("dd", {}, s.next_run_text || (s.enabled ? "—" : "Paused")),
      h("dt", {}, "Last run"), h("dd", {}, s.last ? [fmtDT(s.last.started_at), " · ", stChip(s.last.status[0].toUpperCase() + s.last.status.slice(1)), s.last.card ? h("span", { class: "muted" }, " · " + s.last.card) : null, s.last.error ? h("div", { class: "err-line" }, s.last.error) : null] : "Hasn't run yet")),
    s.os_ok === false ? h("div", { class: "note warn" }, "This schedule isn't registered with the system scheduler, so it won't run. Press Edit, then Save, to fix it.") : null,
    h("div", { class: "jc-acts" },
      h("button", { type: "button", onclick: () => scheduleDialog(s) }, "Edit"),
      h("button", { type: "button", disabled: S.running || !s.cards.some((c) => c.active), onclick: () => runSchedule(s) }, "Run now"),
      h("button", { type: "button", onclick: () => scheduleHistory(s) }, "History"),
      h("button", { type: "button", onclick: () => deleteSchedule(s) }, "Delete")))));
}
async function toggleSchedule(s, on, inp, confirm) {
  try {
    const r = await api("POST", `/api/schedules/${s.id}/enable`, { enabled: on });
    toast(on ? `“${s.name}” is on.` : `“${s.name}” paused. Its cards won't run from this schedule.`, on ? "ok" : "info");
    if (r.problems && r.problems.length) toast("The system scheduler reported: " + r.problems.join("; "), "warn");
    load();
  } catch (e) {
    inp.checked = !on;
    if (/another active schedule/.test(e.message)) toast("Some of its cards are in another active schedule. Open Edit to confirm duplicate runs.", "warn", [["Edit", () => scheduleDialog(s)]]);
    else toast(e.message, "err");
  }
}
async function runSchedule(s) {
  try { await api("POST", `/api/schedules/${s.id}/run`, {}); startPolling(); toast(`Running the cards in “${s.name}” now.`, "info"); }
  catch (e) { toast(e.message, "err"); }
}
async function deleteSchedule(s) {
  const ok = await confirmBox(`Delete schedule “${s.name}”?`, `Its ${s.cards.length} linked card${s.cards.length === 1 ? "" : "s"} stay, with their results and history. They just won't run on this schedule any more.`, "Delete schedule", true);
  if (!ok) return;
  try { await api("DELETE", "/api/schedules/" + s.id); toast(`Schedule “${s.name}” deleted.`); load(); } catch (e) { toast(e.message, "err"); }
}
function scheduleHistory(s) {
  modal({ title: `Runs from “${s.name}”`, body: s.history.length ? h("div", { class: "tblwrap" }, h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["Started", "Card", "Status", "Found", "New", "Details"].map((x) => h("th", {}, x)))),
    h("tbody", {}, s.history.map((x) => h("tr", {}, h("td", {}, fmtDT(x.started_at)), h("td", {}, x.card || "(deleted card)"), h("td", {}, stChip(x.status[0].toUpperCase() + x.status.slice(1))),
      h("td", {}, x.jobs_found ?? "—"), h("td", {}, x.new_jobs ?? "—"), h("td", { class: "small" }, x.error || "")))))) : h("div", { class: "empty" }, "This schedule hasn't run yet."),
    actions: [{ label: "Close", value: null, primary: true }] });
}
function scheduleBody(s, opts = {}) {
  const st = { name: s.name || "", frequency: s.frequency || "daily", time: s.time || "09:00", days: (s.days || SDAYS).slice(), every_hours: s.every_hours || 4,
    timezone: s.timezone || "Asia/Kolkata", enabled: s.enabled !== false, cards: new Set((s.cards || []).map((c) => c.id).concat(opts.cardId ? [opts.cardId] : [])),
    is_default: !!s.is_default, kind: s.kind || opts.kind || "shared" };
  const wrap = h("div", { style: "display:grid;gap:12px" });
  const draw = () => {
    const freq = h("div", { class: "seg2", role: "radiogroup", "aria-label": "Frequency" }, [["daily", "Daily"], ["weekly", "Weekly (pick days)"], ["hourly", "Every few hours"]].map(([k, l]) =>
      h("button", { type: "button", role: "radio", "aria-checked": String(st.frequency === k), "aria-pressed": String(st.frequency === k), onclick: () => { st.frequency = k; draw(); } }, l)));
    const nameI = h("input", { value: st.name, placeholder: "e.g. Morning search", oninput: (e) => { st.name = e.target.value; } });
    const timeI = h("input", { type: "time", value: st.time, required: true, oninput: (e) => { st.time = e.target.value; } });
    const tzS = h("select", { onchange: (e) => { st.timezone = e.target.value; } }, S.tz.map(([v, l]) => h("option", { value: v, selected: v === st.timezone }, l)));
    const cards = h("div", { class: "checklist" }, S.cards.length ? S.cards.map((c) => { const cb = h("input", { type: "checkbox", onchange: (e) => { e.target.checked ? st.cards.add(c.id) : st.cards.delete(c.id); } }); cb.checked = st.cards.has(c.id);
      return h("label", {}, cb, h("span", {}, c.name), c.active ? null : h("span", { class: "chip st-Disabled" }, "off")); }) : h("div", { class: "muted small" }, "No cards yet."));
    wrap.replaceChildren(
      h("label", {}, "Schedule name", nameI),
      h("div", { style: "display:grid;gap:6px" }, h("span", { class: "lbl small", style: "font-weight:600" }, "Frequency"), freq),
      h("div", { class: "grid2" }, h("label", {}, st.frequency === "hourly" ? "Start time" : "Time", timeI), h("label", {}, "Time zone", tzS)),
      st.frequency === "hourly" ? h("label", {}, "Repeat every", h("select", { onchange: (e) => { st.every_hours = Number(e.target.value); } }, [1, 2, 3, 4, 6, 8, 12].map((n) => h("option", { value: n, selected: n === st.every_hours }, `${n} hour${n > 1 ? "s" : ""} (until midnight)`)))) : null,
      st.frequency !== "daily" ? h("fieldset", { style: "border:0;padding:0;margin:0" }, h("legend", { class: "small", style: "font-weight:600;margin-bottom:4px" }, "Days"),
        h("div", { class: "picker" }, SDAYS.map((d) => h("button", { type: "button", "aria-pressed": String(st.days.includes(d)), onclick: () => { st.days = st.days.includes(d) ? st.days.filter((x) => x !== d) : SDAYS.filter((x) => x === d || st.days.includes(x)); draw(); } }, d[0] + d.slice(1).toLowerCase())))) : null,
      st.kind === "card" ? h("div", { class: "note" }, "This schedule belongs to “" + (S.cards.find((c) => st.cards.has(c.id)) || {}).name + "”.") :
        h("div", { style: "display:grid;gap:6px" }, h("span", { class: "small", style: "font-weight:600" }, "Cards to run"), cards),
      st.kind !== "card" ? h("label", { class: "inline-check" }, (() => { const x = h("input", { type: "checkbox", onchange: (e) => { st.is_default = e.target.checked; } }); x.checked = st.is_default; return x; })(), "Add new cards to this schedule automatically") : null,
      h("label", { class: "inline-check" }, (() => { const x = h("input", { type: "checkbox", onchange: (e) => { st.enabled = e.target.checked; } }); x.checked = st.enabled; return x; })(), "Schedule is on"),
      h("p", { class: "small muted", style: "margin:0" }, "Runs even when the app is closed, as long as the computer is on. If the computer was off, it runs as soon as it's back on. Turned-off cards are skipped."));
  };
  draw();
  return { wrap, st };
}
async function saveSchedule(id, st, confirm) {
  if (!st.name.trim()) { toast("Give the schedule a name.", "err"); return false; }
  if (!/^\d{2}:\d{2}$/.test(st.time)) { toast("Pick a time.", "err"); return false; }
  if (st.frequency !== "daily" && !st.days.length) { toast("Pick at least one day.", "err"); return false; }
  const body = { name: st.name.trim(), kind: st.kind, frequency: st.frequency, time: st.time, days: st.frequency === "daily" ? SDAYS : st.days, every_hours: st.frequency === "hourly" ? st.every_hours : null,
    timezone: st.timezone, enabled: st.enabled, card_ids: [...st.cards], is_default: st.is_default, confirm_duplicates: !!confirm };
  try {
    const r = await fetch(id ? `/api/schedules/${id}` : "/api/schedules", { method: "POST", headers: { "Content-Type": "application/json", "X-JobRadar": "1" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (r.status === 409) {
      const lines = data.conflicts.map((c) => `${c.card} is also in ${c.schedules.join(", ")}`);
      const again = await modal({ title: "Run these cards more than once?", body: [h("p", { style: "margin:0" }, "These cards are already in another active schedule, so they could search and email twice:"),
          h("ul", {}, lines.map((l) => h("li", {}, l))), h("p", { class: "small muted", style: "margin:0" }, "Choose Allow if that's intended (for example a morning and an evening run). Otherwise go back and remove them from one schedule.")],
        actions: [{ label: "Go back", value: false }, { label: "Allow duplicate runs", value: true, primary: true }] });
      return again ? saveSchedule(id, st, true) : false;
    }
    if (!r.ok) { toast(data.error || "Couldn't save the schedule.", "err"); return false; }
    toast(`Schedule “${body.name}” saved.` + (body.enabled && body.card_ids.length ? "" : body.card_ids.length ? " It's paused." : " Link a card so it runs."));
    if (data.problems && data.problems.length) toast("Saved, but the system scheduler reported: " + data.problems.join("; "), "warn");
    flashStatus("success"); load(); return true;
  } catch (e) { toast("Couldn't save: " + e.message, "err", [["Retry", () => saveSchedule(id, st, confirm)]]); return false; }
}
async function scheduleDialog(s, opts = {}) {
  const { wrap, st } = scheduleBody(s || {}, opts);
  let saved = false;
  await modal({ title: s && s.id ? `Edit schedule “${s.name}”` : opts.kind === "card" ? "New schedule for this card" : "Create schedule", body: wrap,
    actions: [{ label: "Cancel", value: null }, { label: "Save schedule", value: "ok", primary: true, onClick: async () => { saved = await saveSchedule(s && s.id, st); if (!saved) return false; } }] });
  return saved;
}
$("newSchedBtn").addEventListener("click", () => scheduleDialog(null));
async function manageCardSchedules(c) {
  const linked = new Set(c.schedules.map((s) => s.id));
  const before = new Set(linked);
  const list = h("div", { class: "checklist", style: "max-height:300px" }, S.schedules.length ? S.schedules.map((s) => {
    const cb = h("input", { type: "checkbox", onchange: (e) => { e.target.checked ? linked.add(s.id) : linked.delete(s.id); } }); cb.checked = linked.has(s.id);
    return h("label", { style: "align-items:flex-start" }, cb, h("span", { style: "display:grid" }, h("b", {}, s.name + (s.enabled ? "" : " (paused)")), h("span", { class: "small muted" }, s.text + (s.next_run_text ? " · next " + s.next_run_text : ""))));
  }) : h("div", { class: "muted small", style: "padding:6px" }, "No schedules yet."));
  const r = await modal({ title: `Schedule for “${c.name}”`, body: [
      h("p", { style: "margin:0" }, "Tick the schedules this card should run on, or give it its own schedule."),
      !c.active ? h("div", { class: "note warn" }, "This card is off, so no schedule will run it until you turn it on.") : null,
      list],
    actions: [{ label: "Give it its own schedule…", value: "new", grow: true }, { label: "Cancel", value: null }, { label: "Save", value: "save", primary: true, onClick: async () => {
      for (const s of S.schedules) {
        const want = linked.has(s.id); if (want === before.has(s.id)) continue;
        const ids = s.cards.map((x) => x.id).filter((x) => x !== c.id).concat(want ? [c.id] : []);
        if (s.kind === "card" && !want) { if (!(await confirmBox(`Delete “${s.name}”?`, "It's this card's own schedule, so unlinking deletes it.", "Delete schedule", true))) return false;
          await api("DELETE", "/api/schedules/" + s.id); continue; }
        const st = { name: s.name, kind: s.kind, frequency: s.frequency, time: s.time, days: s.days, every_hours: s.every_hours, timezone: s.timezone, enabled: s.enabled, cards: new Set(ids), is_default: s.is_default };
        if (!(await saveSchedule(s.id, st))) return false;
      }
    } }] });
  if (r === "new") scheduleDialog({ name: c.name + " schedule", kind: "card", cards: [{ id: c.id }] }, { kind: "card", cardId: c.id });
}

/* ---------------- edit / import / mode switching ---------------- */
function renderEditBar() {
  const b = $("editBar"), e = S.editing || S.importing;
  if (!e) { b.hidden = true; return; }
  const mode = S.inputMode;
  b.replaceChildren(h("span", {}, h("b", {}, S.importing ? `Importing “${e.name}”` : `Editing “${e.name}”`), " · " + MODE_LABEL[mode],
      e.origMode && e.origMode !== mode ? h("span", { class: "muted" }, ` (was ${MODE_LABEL[e.origMode]}; changes when you save)`) : null),
    h("span", { class: "btns" }, h("button", { type: "button", class: "linkish", onclick: () => setMode(mode === "chart" ? "questionnaire" : "chart") }, "Change input mode"),
      h("button", { type: "button", class: "linkish", onclick: cancelEditing }, S.importing ? "Cancel import" : "Cancel editing")));
  b.hidden = false;
}
async function cancelEditing() {
  const ok = await confirmBox(S.importing ? "Cancel the import?" : "Cancel editing?", S.importing ? "Nothing is imported." : "Your unsaved changes are discarded. The card stays as it was.", "Yes, cancel");
  if (!ok) return;
  S.editing = null; S.importing = null; restart(); resetQ(); renderQ(); renderEditBar();
}
async function editCard(c) {
  if ((S.editing || S.importing) && !(await confirmBox("Stop the current edit?", "You're already editing a card. Discard those unsaved changes?", "Discard and continue"))) return;
  S.importing = null;
  S.editing = { id: c.id, name: c.name, origMode: c.input_mode, email_on: c.email_on, sources: c.answer_source.slice() };
  S.sources = new Set(c.answer_source.filter((x) => x !== "import"));
  const prof = Object.assign({}, c.profile, { email: c.email || "" });
  await openInMode(c.input_mode, prof, `Editing “${c.name}”. Your saved answers are loaded: change any section with Edit, then press Save changes.`);
  document.querySelector('[aria-labelledby="chatH"]').scrollIntoView({ behavior: "smooth" });
}
async function openInMode(mode, prof, msg) {
  if (mode === "questionnaire") { fillQ(prof); setMode("questionnaire", { convert: false }); }
  else {
    const r = await api("POST", "/api/intake/resume", { profile: prof, all_answered: true });
    S.intake = r.state; S.prog = r.progress; S.done = r.profile; S.confirm = null; S.editor = null;
    S.chat = [{ role: "bot", text: msg }];
    setMode("chart", { convert: false });
  }
  renderEditBar();
}
S.inputMode = "chart";
async function setMode(mode, { convert = true } = {}) {
  if (convert && mode !== S.inputMode) {
    if (S.confirm || S.editor) return toast("Confirm or cancel the open answer first.", "warn");
    if (mode === "questionnaire") {
      const prof = S.done || (S.intake && S.intake.profile) || null;
      if (prof) { fillQ(prof); toast("Your chat answers were carried over to the form.", "info"); }
    } else {
      const prof = readQ(false);
      const has = Object.keys(FIELD_LABELS).some((k) => prof[k] && (!Array.isArray(prof[k]) || prof[k].length));
      if (has) {
        try {
          const r = await api("POST", "/api/intake/resume", { profile: prof, all_answered: !!(S.editing || S.importing) });
          S.intake = r.state; S.prog = r.progress; S.confirm = null; S.editor = null;
          S.done = r.done ? r.profile : null;
          S.chat = [{ role: "bot", text: "I've loaded your form answers." + (r.done ? " Check the card below." : "") }];
          if (!r.done) S.chat.push({ role: "bot", text: r.question, options: r.options });
          const extra = ["industries", "employment_type", "description"].filter((k) => prof[k] && prof[k].length);
          toast("Form answers carried over to Chart mode." + (extra.length ? " Industries, employment type and notes aren't asked in the chat, but they're kept and saved." : ""), "info");
        } catch (e) { return toast("Couldn't switch: " + e.message + " Your form is unchanged.", "err"); }
      }
    }
  }
  S.inputMode = mode;
  $("modeChart").setAttribute("aria-selected", String(mode === "chart")); $("modeQ").setAttribute("aria-selected", String(mode === "questionnaire"));
  $("chatMode").hidden = mode !== "chart"; $("qForm").hidden = mode !== "questionnaire";
  $("featChips").hidden = false;
  if (mode === "questionnaire") renderQ(); else renderChat();
  renderEditBar();
}
$("modeChart").addEventListener("click", () => setMode("chart"));
$("modeQ").addEventListener("click", () => setMode("questionnaire"));
$("newCardBtn").addEventListener("click", async () => {
  if ((S.editing || S.importing) && !(await confirmBox("Start a new search?", "Discard the unsaved edit?", "Discard"))) return;
  S.editing = null; S.importing = null; restart(); resetQ(); renderQ(); renderEditBar();
  document.querySelector('[aria-labelledby="chatH"]').scrollIntoView({ behavior: "smooth" });
  setTimeout(() => (S.inputMode === "chart" ? $("chatText") : $("qName"))?.focus(), 300);
});

$("importBtn").addEventListener("click", () => $("importFile").click());
$("importFile").addEventListener("change", async (e) => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  if (f.size > 1024 * 1024) return toast("That file is too large for a card export (over 1 MB).", "err");
  let data;
  try { data = JSON.parse(await f.text()); } catch { return toast(`“${f.name}” isn't valid JSON. Choose a file made with Export card.`, "err"); }
  let pv;
  try { pv = await api("POST", "/api/import/preview", { data }); } catch (err) { return toast("Can't import: " + err.message, "err"); }
  const card = pv.card;
  let mode = "new", target = pv.same_name ? pv.same_name.id : (pv.existing[0] || {}).id, withSch;
  const tsel = h("select", { disabled: true, onchange: (ev) => { target = Number(ev.target.value); } }, pv.existing.map((x) => h("option", { value: x.id, selected: x.id === target }, x.name)));
  const radio = (v, label) => { const r = h("input", { type: "radio", name: "impmode", value: v, onchange: () => { mode = v; tsel.disabled = v !== "update"; } }); r.checked = v === "new"; return h("label", { class: "inline-check" }, r, label); };
  const res = await modal({ title: "Import card", body: [
      h("div", { class: "note ok" }, `File OK: “${card.name}”, ${MODE_LABEL[card.input_mode]}` + (card.exported_at ? `, exported ${fmtDT(card.exported_at)}` : "") + (card.app ? ` from ${card.app}` : "") + "."),
      pv.warnings.map((w) => h("div", { class: "note warn" }, w)),
      h("div", { class: "tblwrap", style: "max-height:240px" }, h("table", { class: "tbl" }, h("tbody", {}, card.preview.filter((x) => x.answer).map((x) => h("tr", {}, h("th", { style: "position:static" }, x.label), h("td", {}, x.answer)))))),
      h("fieldset", { style: "border:0;padding:0;margin:0;display:grid;gap:6px" }, h("legend", { class: "small", style: "font-weight:600" }, "What should happen?"),
        radio("new", "Create a new card"),
        pv.existing.length ? h("div", { style: "display:grid;gap:4px" }, radio("update", "Update an existing card (its history is kept)"), tsel) : null),
      pv.same_name ? h("div", { class: "small muted" }, `A card named “${pv.same_name.name}” already exists. Creating a new one makes a second card.`) : null,
      card.schedules.some((s) => s.kind === "card") ? h("label", { class: "inline-check" }, withSch = h("input", { type: "checkbox" }), "Also create the card's own schedule from the file") : null],
    actions: [{ label: "Cancel", value: null, grow: true }, { label: "Review and edit first", value: "review" }, { label: "Import", value: "import", primary: true }] });
  if (!res) return;
  const opts = { data, mode, target_id: mode === "update" ? target : null, with_schedules: !!(withSch && withSch.checked), name: card.name, origMode: card.input_mode };
  if (res === "import") return finishImport(opts, null);
  S.editing = null; S.importing = opts;
  S.sources = new Set(card.answer_source.concat(["import"]));
  await openInMode(card.input_mode, Object.assign({}, card.answers, { email: card.email || "" }), `Importing “${card.name}”. Review the answers, change anything with Edit, then press Save to import.`);
  document.querySelector('[aria-labelledby="chatH"]').scrollIntoView({ behavior: "smooth" });
});
async function finishImport(opts, answers, inputMode) {
  try {
    const r = await api("POST", "/api/import", { data: opts.data, mode: opts.mode, target_id: opts.target_id, answers, with_schedules: opts.with_schedules });
    S.importing = null; renderEditBar();
    toast(opts.mode === "update" ? "Card updated from the file." : "Card imported successfully!"); flashStatus("success");
    (r.warnings || []).forEach((w) => toast(w, "warn"));
    if (inputMode && inputMode !== opts.origMode) await api("POST", "/api/profiles/" + r.id, { profile: answers, input_mode: inputMode });
    await load(); highlightCard(r.id); return r.id;
  } catch (e) { toast("Import failed: " + e.message, "err", [["Retry", () => finishImport(opts, answers, inputMode)]]); return null; }
}

/* ---------------- questionnaire mode ---------------- */
const Q0 = () => ({ name: "", roles: [], experience: "", locations: [], anywhere: false, remote_international: false, work_modes: [], skills: [], industries: [],
  min_salary: "", exclude: [], employment_type: "full-time", email: "", email_on: true, description: "", attachment_ids: [], from: new Set(), errors: {} });
let Q = Q0();
const EXP_OPTS = ["0–1 years", "1–3 years", "3–5 years", "5–8 years", "8+ years"];
const CITY_OPTS = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi NCR", "Mumbai", "Kolkata", "Ahmedabad", "Kochi", "Visakhapatnam"];
function resetQ() { Q = Q0(); }
function fillQ(p) {
  Q = Q0();
  const L = (v) => (Array.isArray(v) ? v.slice() : v ? [v] : []);
  Q.name = p.name || ""; Q.roles = L(p.roles); Q.experience = p.experience || ""; Q.skills = L(p.skills); Q.industries = L(p.industries); Q.exclude = L(p.exclude);
  const locs = L(p.locations); Q.anywhere = locs.some((x) => /^(india|anywhere in india)$/i.test(x)); Q.locations = locs.filter((x) => !/^(india|anywhere in india)$/i.test(x));
  Q.remote_international = !!p.remote_international;
  Q.work_modes = Array.isArray(p.work_modes) ? p.work_modes.slice() : String(p.work_arrangement || "").toLowerCase().split(/[,\s]+/).filter((x) => ["hybrid", "remote", "onsite"].includes(x));
  Q.min_salary = p.min_salary || ""; Q.employment_type = p.employment_type || "full-time"; Q.email = p.email || ""; Q.description = p.description || "";
  Q.email_on = S.editing ? S.editing.email_on !== false : true;
  Q.attachment_ids = L(p.attachment_ids);
}
function readQ(strict) {
  const errors = {};
  if (strict) {
    if (!Q.name.trim()) errors.name = "Give the search a name.";
    if (!Q.roles.length) errors.roles = "Add at least one job title.";
    if (!Q.experience.trim()) errors.experience = "Choose your experience.";
    if (!Q.locations.length && !Q.anywhere) errors.locations = "Add at least one city, or tick Anywhere in India.";
    if (Q.email.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(Q.email.trim())) errors.email = "That doesn't look like an email address.";
    if (Q.min_salary && !/^\s*(₹|rs\.?|inr)?\s*\d+(\.\d+)?\s*(lpa|lakhs?|l)?\s*$/i.test(Q.min_salary)) errors.min_salary = "Type a number of lakhs per year, e.g. 12.";
  }
  Q.errors = errors;
  const sal = Q.min_salary.trim();
  return { name: Q.name.trim(), roles: Q.roles, experience: Q.experience.trim(), locations: Q.anywhere ? ["India"].concat(Q.locations) : Q.locations,
    remote_international: Q.remote_international, work_modes: Q.work_modes, skills: Q.skills, industries: Q.industries, exclude: Q.exclude,
    min_salary: sal ? (/^\d+(\.\d+)?$/.test(sal) ? sal + " LPA" : sal) : "", employment_type: Q.employment_type, email: Q.email.trim(), description: Q.description.trim(),
    attachment_ids: Q.attachment_ids };
}
async function normItems(key, text) {
  if (!["locations", "roles", "skills"].includes(key)) return text.split(/[,;\n]/).map((x) => x.trim()).filter(Boolean);
  try { const r = await api("POST", "/api/intake/set", { state: {}, key, text, mode: "overwrite" }); return (r.state && r.state.profile && r.state.profile[key]) || []; }
  catch { return text.split(/[,;\n]/).map((x) => x.trim()).filter(Boolean); }
}
function chipInput(key, label, placeholder, opts = {}) {
  const inp = h("input", { id: "q_" + key, placeholder, "aria-label": label, list: opts.list || null,
    onkeydown: async (e) => { if ((e.key === "Enter" || e.key === ",") && e.target.value.trim()) { e.preventDefault(); await addChips(key, e.target.value); }
      else if (e.key === "Backspace" && !e.target.value && Q[key].length) { Q[key].pop(); renderQ(); setTimeout(() => $("q_" + key)?.focus(), 0); } },
    onblur: (e) => { if (e.target.value.trim()) addChips(key, e.target.value); } });
  return h("div", { class: "chipin", onclick: (e) => { if (e.target === e.currentTarget) inp.focus(); } },
    Q[key].map((v, i) => h("span", { class: "tag" }, v, h("button", { type: "button", "aria-label": `Remove ${v}`, onclick: () => { Q[key].splice(i, 1); renderQ(); } }, "×"))), inp);
}
async function addChips(key, text) {
  const items = await normItems(key, text);
  for (const it of items) if (!Q[key].some((x) => x.toLowerCase() === String(it).toLowerCase())) Q[key].push(it);
  delete Q.errors[key]; renderQ(); setTimeout(() => $("q_" + key)?.focus(), 0);
}
const qLabel = (text, key, req, help) => h("span", { class: "lbl" + (req ? " req" : "") }, text, Q.from.has(key) ? h("span", { class: "fromfile", title: "Filled from your file. Check it." }, "from file") : null, help ? h("span", { class: "help" }, " " + help) : null);
const qErr = (key) => Q.errors[key] ? h("div", { class: "field-err", role: "alert" }, Q.errors[key]) : null;
function renderQ() {
  const f = $("qForm");
  if (f.hidden) return;
  const editingLabel = S.importing ? "Import card" : S.editing ? "Save changes" : "Save card";
  const custom = Q.experience && !EXP_OPTS.includes(Q.experience);
  const expSel = h("select", { id: "q_experience", onchange: (e) => { Q.experience = e.target.value === "__other" ? " " : e.target.value; delete Q.errors.experience; renderQ(); if (e.target.value === "__other") setTimeout(() => $("q_exp_custom")?.focus(), 0); } },
    h("option", { value: "" }, "Choose…"), EXP_OPTS.map((o) => h("option", { value: o, selected: Q.experience === o }, o)), h("option", { value: "__other", selected: custom }, "Other…"));
  const field = (key, ...kids) => h("div", { class: "fieldrow" + (Q.errors[key] ? " invalid" : "") }, ...kids, qErr(key));
  f.replaceChildren(
    h("div", { class: "upbox" },
      h("div", { style: "font-weight:600" }, "Fill the form from a file (optional)"),
      h("div", { class: "muted" }, "PDF, Word (.docx), TXT, MD, RTF or an image, up to 15 MB. Answers found are put into the fields below for you to check."),
      h("div", { class: "btns", style: "justify-content:flex-start" },
        h("button", { type: "button", id: "qUpBtn", onclick: () => $("qFile").click() }, "Upload file…"),
        h("a", { class: "btn", href: "/samples/job-search-brief.txt?download=1", download: "" }, "Download sample file"),
        h("input", { type: "file", id: "qFile", hidden: true, accept: ".pdf,.docx,.txt,.md,.rtf,.png,.jpg,.jpeg,.webp,.gif", onchange: (e) => { const x = e.target.files[0]; e.target.value = ""; if (x) qUpload(x); } })),
      Q.fileNote ? h("div", { class: "note " + (Q.fileNoteKind || "") }, Q.fileNote) : null),
    field("name", h("label", { for: "q_name" }, qLabel("Search name", "name", true)), h("input", { id: "q_name", value: Q.name, placeholder: "e.g. Dilip – product design", oninput: (e) => { Q.name = e.target.value; } })),
    field("roles", qLabel("Job titles", "roles", true, "Press Enter after each"), chipInput("roles", "Job titles", "e.g. Product Designer", { list: "roleList" })),
    h("datalist", { id: "roleList" }, ["Software Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer", "Data Analyst", "Data Scientist", "Data Engineer", "DevOps Engineer", "QA Engineer", "Product Manager", "Product Designer", "UX Designer", "UI Designer", "Business Analyst", "Project Manager"].map((r) => h("option", { value: r }))),
    field("experience", h("label", { for: "q_experience" }, qLabel("Experience", "experience", true)), expSel,
      custom ? h("input", { id: "q_exp_custom", value: Q.experience.trim(), placeholder: "e.g. 4 years", oninput: (e) => { Q.experience = e.target.value || " "; } }) : null),
    field("locations", qLabel("Cities", "locations", true, "Pick or type several"),
      h("div", { class: "picker" }, CITY_OPTS.map((c) => h("button", { type: "button", "aria-pressed": String(Q.locations.includes(c)), onclick: () => { Q.locations = Q.locations.includes(c) ? Q.locations.filter((x) => x !== c) : Q.locations.concat([c]); delete Q.errors.locations; renderQ(); } }, c))),
      chipInput("locations", "Cities", "Type another city and press Enter"),
      h("label", { class: "inline-check" }, (() => { const x = h("input", { type: "checkbox", onchange: (e) => { Q.anywhere = e.target.checked; delete Q.errors.locations; } }); x.checked = Q.anywhere; return x; })(), "Anywhere in India")),
    h("fieldset", {}, h("legend", {}, qLabel("Work modes", "work_modes", false, "Choose one or more. None selected = any.")),
      h("div", { class: "picker" }, [["hybrid", "Hybrid"], ["remote", "Remote"], ["onsite", "On-site"]].map(([k, l]) => h("button", { type: "button", "aria-pressed": String(Q.work_modes.includes(k)),
        onclick: () => { Q.work_modes = Q.work_modes.includes(k) ? Q.work_modes.filter((x) => x !== k) : ["hybrid", "remote", "onsite"].filter((x) => x === k || Q.work_modes.includes(x)); renderQ(); } }, l))),
      h("div", { class: "small muted" }, "Selected: " + modesText(Q.work_modes))),
    h("label", { class: "inline-check" }, (() => { const x = h("input", { type: "checkbox", onchange: (e) => { Q.remote_international = e.target.checked; } }); x.checked = Q.remote_international; return x; })(),
      "Include remote jobs at international companies that hire from India", Q.from.has("remote_international") ? h("span", { class: "fromfile" }, "from file") : null),
    field("skills", qLabel("Must-have skills", "skills", false, "Press Enter after each"), chipInput("skills", "Skills", "e.g. Figma")),
    field("industries", qLabel("Preferred industries", "industries"), chipInput("industries", "Industries", "e.g. fintech")),
    h("div", { class: "grid2" },
      field("min_salary", h("label", { for: "q_sal" }, qLabel("Minimum salary (LPA)", "min_salary")), h("input", { id: "q_sal", value: Q.min_salary, inputmode: "decimal", placeholder: "e.g. 12", oninput: (e) => { Q.min_salary = e.target.value; } })),
      field("employment_type", h("label", { for: "q_emp" }, qLabel("Employment type", "employment_type")), h("select", { id: "q_emp", onchange: (e) => { Q.employment_type = e.target.value; } },
        [["full-time", "Full-time"], ["contract", "Contract"], ["internship", "Internship"]].map(([v, l]) => h("option", { value: v, selected: Q.employment_type === v }, l))))),
    field("exclude", qLabel("Avoid", "exclude", false, "Roles, companies or industries"), chipInput("exclude", "Avoid", "e.g. internship")),
    field("email", h("label", { for: "q_email" }, qLabel("Report email", "email", false, "Optional")), h("input", { id: "q_email", type: "email", value: Q.email, placeholder: "you@example.com", oninput: (e) => { Q.email = e.target.value; } }),
      h("label", { class: "inline-check" }, (() => { const x = h("input", { type: "checkbox", onchange: (e) => { Q.email_on = e.target.checked; } }); x.checked = Q.email_on; return x; })(), "Send the daily email")),
    field("description", h("label", { for: "q_desc" }, qLabel("Notes about the job you want", "description", false, "Optional")), h("textarea", { id: "q_desc", rows: 3, oninput: (e) => { Q.description = e.target.value; } }, Q.description)),
    Object.keys(Q.errors).length ? h("div", { class: "note bad", role: "alert" }, "Please fix the highlighted fields.") : null,
    h("div", { class: "btns" },
      h("button", { type: "button", class: "grow", onclick: async () => { if (await confirmBox("Clear the form?", "All answers in the form are removed.", "Clear form", true)) { resetQ(); renderQ(); } } }, "Clear form"),
      S.editing ? h("button", { type: "button", onclick: () => saveQ(false, true) }, "Save as new card") : null,
      !S.editing && !S.importing ? h("button", { type: "button", onclick: () => saveQ(true) }, "Save and run") : null,
      h("button", { type: "button", class: "primary", onclick: () => saveQ(false) }, editingLabel)));
  const qn = $("q_name"); if (qn) qn.id = "q_name"; window.$qName = qn;
}
const _qn = () => $("q_name");
async function qUpload(file) {
  if (!/\.(pdf|docx|txt|md|rtf|png|jpe?g|webp|gif)$/i.test(file.name)) return toast(`“${file.name}” isn't supported. Use PDF, Word, TXT, MD, RTF or an image.`, "err");
  if (file.size > 15 * 1024 * 1024) return toast(`“${file.name}” is over 15 MB.`, "err");
  Q.fileNote = "Reading " + file.name + "…"; Q.fileNoteKind = ""; renderQ(); busy(true, "Reading file");
  try {
    const r = await api("POST", "/api/attachments", { filename: file.name, mime: file.type, data: await toB64(file) });
    if (!r.has_text) { Q.fileNote = r.problem || r.note; Q.fileNoteKind = "warn"; toast("The file was saved, but no text could be read from it.", "warn"); return; }
    const x = r.extracted || {}, filled = [];
    const mergeL = (k, v) => { if (!v || !v.length) return; const before = Q[k].length; for (const it of v) if (!Q[k].some((y) => y.toLowerCase() === String(it).toLowerCase())) Q[k].push(it); if (Q[k].length > before) { Q.from.add(k); filled.push(FIELD_LABELS[k] || k); } };
    mergeL("roles", x.roles); mergeL("skills", x.skills); mergeL("industries", x.industries); mergeL("exclude", x.exclude);
    const locs = (x.locations || []).filter((l) => !/^india$/i.test(l)); if ((x.locations || []).some((l) => /^india$/i.test(l)) && !Q.anywhere) { Q.anywhere = true; Q.from.add("locations"); }
    mergeL("locations", locs);
    const setS = (k, v, label) => { if (v && !String(Q[k]).trim()) { Q[k] = v; Q.from.add(k); filled.push(label); } };
    setS("experience", x.experience, "Experience"); setS("min_salary", x.min_salary, "Minimum salary"); setS("email", x.email, "Report email"); setS("name", x.name, "Search name");
    const modes = Array.isArray(x.work_modes) ? x.work_modes : String(x.work_arrangement || "").toLowerCase().split(/[,\s]+/).filter((m) => ["hybrid", "remote", "onsite"].includes(m));
    if (modes.length && !Q.work_modes.length) { Q.work_modes = modes; Q.from.add("work_modes"); filled.push("Work modes"); }
    if (x.remote_international && !Q.remote_international) { Q.remote_international = true; Q.from.add("remote_international"); filled.push("Remote jobs abroad"); }
    if (r.id) Q.attachment_ids.push(r.id);
    S.qsrc = (S.qsrc || new Set()).add(r.kind === "image" ? "screenshot" : "file"); if (/Claude/.test(r.fields_engine || "")) S.qsrc.add("ai");
    const miss = ["roles", "experience", "locations"].filter((k) => k === "locations" ? !(Q.locations.length || Q.anywhere) : !(Array.isArray(Q[k]) ? Q[k].length : String(Q[k]).trim())).map((k) => FIELD_LABELS[k]);
    Q.fileNote = (filled.length ? `Filled from ${r.filename}: ${filled.join(", ")}. Fields marked “from file” need a quick check.` : `I read ${r.filename} but found nothing new to add.`) +
      (miss.length ? ` Still needed: ${miss.join(", ")}.` : "") + ` (Text read by ${r.text_engine}; details found by ${r.fields_engine}.)`;
    Q.fileNoteKind = filled.length ? "ok" : "warn";
    toast(filled.length ? `File processed: ${filled.length} field${filled.length > 1 ? "s" : ""} filled.` : "File read, but nothing new was found.", filled.length ? "ok" : "warn"); flashStatus("success");
  } catch (e) { Q.fileNote = "Upload failed: " + e.message; Q.fileNoteKind = "bad"; toast("Upload failed: " + e.message, "err", [["Retry", () => qUpload(file)]]); flashStatus("error"); }
  finally { busy(false); renderQ(); }
}
async function saveQ(run, asNew) {
  const prof = readQ(true);
  if (Object.keys(Q.errors).length) { renderQ(); toast("Please fix the highlighted fields.", "err"); const k = Object.keys(Q.errors)[0]; setTimeout(() => ($("q_" + k) || $("q_name"))?.focus(), 0); return; }
  const src = ["manual"].concat([...(S.qsrc || [])]);
  busy(true, "Saving");
  try {
    if (S.importing) { await finishImport(S.importing, prof, "questionnaire"); resetQ(); renderQ(); return; }
    if (S.editing && !asNew) {
      const id = S.editing.id;
      await api("POST", "/api/profiles/" + id, { profile: prof, input_mode: "questionnaire", answer_source: src });
      if (!!S.editing.email_on !== Q.email_on && prof.email) await api("POST", "/api/profiles/" + id, { email_on: Q.email_on });
      toast(`Card “${prof.name}” updated successfully!`); S.editing = null; renderEditBar();
      resetQ(); renderQ(); flashStatus("success"); await load(); highlightCard(id); return;
    }
    const r = await api("POST", "/api/profiles", { profile: prof, input_mode: "questionnaire", answer_source: src });
    if (!Q.email_on && prof.email) await api("POST", "/api/profiles/" + r.id, { email_on: false });
    toast(`Card “${prof.name}” saved successfully!` + (r.default_schedule ? ` Added to “${r.default_schedule}”.` : "")); flashStatus("success");
    S.editing = null; renderEditBar(); resetQ(); S.qsrc = new Set(); renderQ();
    S.selected = r.id; await load(); highlightCard(r.id);
    if (run) runScan([r.id]);
  } catch (e) { toast("Couldn't save: " + e.message, "err", [["Retry", () => saveQ(run, asNew)]]); flashStatus("error"); }
  finally { busy(false); }
}
