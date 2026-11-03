/* ---------------- Mail (accounts, recipients, rules, templates, history) ---------------- */
const EMAIL_OK = (a) => /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$/.test(a);
const ACC_ST = { connected: ["Connected", "ok"], failed: ["Sign-in failed", "bad"], untested: ["Not tested", "warn"], disconnected: ["Disconnected", "bad"], limited: ["Daily limit reached", "warn"] };
const MAIL_ST = { pending: "Pending", sending: "Sending", sent: "Sent", partial: "Partly sent", uncertain: "Unconfirmed", failed: "Failed", skipped: "Skipped" };
const SENDER_TXT = (s, accs) => { const nm = (id) => (accs.find((a) => a.id === id) || {}).email || "a removed account";
  return s.mode === "default" ? "Default account" : s.mode === "specific" ? nm(s.accounts[0]) : (s.accounts.map(nm).join(" + ") + (s.strategy === "copy" ? " (a copy from each)" : " (take turns)")); };
const FALLBACK_TXT = { stop: "Stop and notify", default: "Use the default account", other: "Use another account" };
S.mail = null;
async function loadMail() { try { S.mail = await api("GET", "/api/mail"); renderMail(); } catch (e) { toast("Couldn't load mail settings: " + e.message, "err"); } }

/* address chips: to/cc/bcc lists that show invalid and duplicate entries */
function addrField(lists, key, label, all) {
  const box = h("div", { style: "display:grid;gap:4px" });
  const draw = () => {
    const seen = new Map(); for (const k of ["to", "cc", "bcc"]) for (const a of lists[k]) { const l = a.toLowerCase(); seen.set(l, (seen.get(l) || 0) + 1); }
    const inp = h("input", { type: "email", placeholder: "name@example.com", "aria-label": `Add ${label} address`, style: "flex:1;min-width:150px;border:0;padding:3px 4px;outline:none;background:transparent",
      onkeydown: (e) => { if (["Enter", ",", ";", " "].includes(e.key) && e.target.value.trim()) { e.preventDefault(); add(e.target.value); } else if (e.key === "Backspace" && !e.target.value && lists[key].length) { lists[key].pop(); draw(); } },
      onpaste: (e) => { const t = e.clipboardData.getData("text"); if (/[,;\s]/.test(t.trim())) { e.preventDefault(); add(t); } },
      onblur: (e) => { if (e.target.value.trim()) add(e.target.value); } });
    const add = (t) => { for (const a of t.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean)) lists[key].push(a); draw(); setTimeout(() => box.querySelector("input")?.focus(), 0); };
    const bad = lists[key].filter((a) => !EMAIL_OK(a)), dup = lists[key].filter((a) => seen.get(a.toLowerCase()) > 1);
    box.replaceChildren(h("span", { class: "small", style: "font-weight:600" }, label),
      h("div", { class: "chipin" }, lists[key].map((a, i) => h("span", { class: "tag", style: !EMAIL_OK(a) ? "background:var(--bad-bg);color:var(--bad)" : seen.get(a.toLowerCase()) > 1 ? "background:var(--warn-bg)" : "", title: !EMAIL_OK(a) ? "Not a valid address" : seen.get(a.toLowerCase()) > 1 ? "Listed more than once" : "" },
        h("span", { contenteditable: "true", spellcheck: "false", onblur: (e) => { const v = e.target.textContent.trim(); if (v !== a) { if (v) lists[key][i] = v; else lists[key].splice(i, 1); draw(); } },
          onkeydown: (e) => { if (e.key === "Enter") { e.preventDefault(); e.target.blur(); } } }, a),
        h("button", { type: "button", "aria-label": "Remove " + a, onclick: () => { lists[key].splice(i, 1); draw(); } }, "×"))), inp,
        h("button", { type: "button", class: "linkish", onclick: () => { if (inp.value.trim()) add(inp.value); else inp.focus(); } }, "Add email")),
      bad.length ? h("div", { class: "field-err" }, `Not valid: ${bad.join(", ")}. Click an address to correct it.`) : null,
      dup.length ? h("div", { class: "warn-text" }, `Listed more than once: ${[...new Set(dup)].join(", ")}. Each person gets one copy.`) : null);
  };
  draw(); return box;
}
const addrProblems = (lists) => { const all = ["to", "cc", "bcc"].flatMap((k) => lists[k]); return all.filter((a) => !EMAIL_OK(a)); };

/* sender rule editor, shared by Mail and the card's Email settings */
function senderEditor(st, accs, opts = {}) {
  const box = h("div", { style: "display:grid;gap:8px" });
  const usable = accs.filter((a) => a.status !== "disconnected");
  const draw = () => {
    const modes = [["default", "Default Gmail account", "Send from the account marked Default."], ["specific", "A specific account", "Always send from the account you pick."],
      ["multi", "Several accounts", "Pick two or more accounts, then choose how they share the work."]];
    if (opts.inherit) modes.unshift(["inherit", "Use the Mail settings", "Follow the sending rule set in the Mail tab: " + SENDER_TXT(S.mail.mail.sender, accs) + "."]);
    const sel = st.mode;
    box.replaceChildren(
      h("div", { role: "radiogroup", style: "display:grid;gap:4px" }, modes.map(([k, l, d]) => { const r = h("input", { type: "radio", name: "sm" + (opts.id || ""), onchange: () => { st.mode = k; if (k === "specific" && st.accounts.length !== 1) st.accounts = usable.slice(0, 1).map((a) => a.id); draw(); } }); r.checked = sel === k;
        return h("label", { class: "inline-check", style: "align-items:flex-start;font-weight:500" }, r, h("span", {}, h("b", {}, l), h("span", { class: "small muted", style: "display:block" }, d))); })),
      sel === "specific" ? h("label", {}, "Send from", h("select", { onchange: (e) => { st.accounts = [Number(e.target.value)]; } },
        accs.map((a) => h("option", { value: a.id, selected: st.accounts[0] === a.id, disabled: a.status === "disconnected" }, a.email + (a.status !== "connected" ? ` (${(ACC_ST[a.status] || [a.status])[0]})` : ""))))) : null,
      sel === "multi" ? h("div", { style: "display:grid;gap:6px" },
        h("div", { class: "checklist" }, accs.map((a) => { const c = h("input", { type: "checkbox", disabled: a.status === "disconnected", onchange: (e) => { st.accounts = e.target.checked ? st.accounts.concat([a.id]) : st.accounts.filter((x) => x !== a.id); } }); c.checked = st.accounts.includes(a.id);
          return h("label", {}, c, a.email, h("span", { class: "chip " + (ACC_ST[a.status] || ["", "warn"])[1] }, (ACC_ST[a.status] || [a.status])[0])); })),
        h("div", { role: "radiogroup", style: "display:grid;gap:4px" }, [["copy", "Send a copy from each account", "Every selected account sends the same email. Recipients get one copy per account (duplicates)."],
          ["rotate", "Take turns (spread emails across accounts)", "Each email goes from one account, the next email from the next account. No duplicates, no jobs left out; it spreads Gmail's daily sending limit."]]
          .map(([k, l, d]) => { const r = h("input", { type: "radio", name: "ss" + (opts.id || ""), onchange: () => { st.strategy = k; draw(); } }); r.checked = st.strategy === k;
            return h("label", { class: "inline-check", style: "align-items:flex-start;font-weight:500" }, r, h("span", {}, h("b", {}, l), h("span", { class: "small muted", style: "display:block" }, d))); })),
        st.strategy === "copy" ? h("div", { class: "note warn" }, "Recipients will receive duplicate emails, one from each selected account. You'll be asked to confirm.") : null) : null,
      !usable.length ? h("div", { class: "note warn" }, "No Gmail account is connected yet. Add one under Sending Gmail accounts.") : null);
  };
  draw(); return box;
}
function fallbackEditor(st, opts = {}) {
  const items = [["stop", "Stop and notify", "Don't send from another account; show the problem on the card."],
    ["default", "Use the default account", "Send from the default account instead (never as a second copy)."],
    ["other", "Use another selected account", "Send from another working account instead (never as a second copy)."]];
  if (opts.inherit) items.unshift(["inherit", "Use the Mail settings", "Currently: " + FALLBACK_TXT[S.mail.mail.fallback] + "."]);
  return h("div", { role: "radiogroup", style: "display:grid;gap:4px" }, items.map(([k, l, d]) => { const r = h("input", { type: "radio", name: "fb" + (opts.id || ""), onchange: () => { st.fallback = k; } }); r.checked = st.fallback === k;
    return h("label", { class: "inline-check", style: "align-items:flex-start;font-weight:500" }, r, h("span", {}, h("b", {}, l), h("span", { class: "small muted", style: "display:block" }, d))); }));
}

function renderMail() {
  const M = S.mail; if (!M) return;
  const box = $("mailBox");
  const accs = M.accounts;
  const R = { to: M.mail.to.slice(), cc: M.mail.cc.slice(), bcc: M.mail.bcc.slice() };
  const snd = { mode: M.mail.sender.mode, accounts: M.mail.sender.accounts.slice(), strategy: M.mail.sender.strategy, fallback: M.mail.fallback };
  let enabledI, limitI, fromI;
  const accRows = accs.length ? h("div", { class: "tblwrap", style: "max-height:none" }, h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["Gmail account", "Status", "Used for", "Sent (24 h)", ""].map((x) => h("th", {}, x)))),
    h("tbody", {}, accs.map((a) => { const [lbl, cls] = ACC_ST[a.status] || [a.status, "warn"];
      return h("tr", {}, h("td", {}, h("b", {}, a.email), M.mail.default_account === a.id ? h("span", { class: "chip info", style: "margin-left:6px" }, "Default") : null),
        h("td", {}, h("span", { class: "chip " + cls }, lbl), a.last_error ? h("div", { class: "err-line" }, a.last_error) : null, a.last_checked ? h("div", { class: "small muted" }, "Checked " + fmtDT(a.last_checked)) : null),
        h("td", { class: "small" }, a.used_by.length ? a.used_by.join(", ") : h("span", { class: "muted" }, "Not used")),
        h("td", { class: "small" }, `${a.sent_24h} / ${M.mail.daily_limit}`),
        h("td", {}, h("div", { class: "btns", style: "justify-content:flex-start" },
          h("button", { type: "button", onclick: (e) => accountAction(a, "test", e.currentTarget) }, "Test"),
          h("button", { type: "button", onclick: () => sendTestDialog(a) }, "Send test"),
          M.mail.default_account !== a.id && a.status !== "disconnected" ? h("button", { type: "button", onclick: (e) => accountAction(a, "default", e.currentTarget) }, "Make default") : null,
          h("button", { type: "button", onclick: () => reconnectDialog(a) }, a.status === "connected" ? "Change password" : "Reconnect"),
          a.status !== "disconnected" ? h("button", { type: "button", onclick: () => removeAccount(a, "disconnect") }, "Disconnect") : null,
          h("button", { type: "button", onclick: () => removeAccount(a, "remove") }, "Remove")))); })))) :
    h("div", { class: "empty" }, "No sending account yet. Add the Gmail account that will send the job emails.");
  const senderBox = senderEditor(snd, accs, { id: "g" });
  const tmpl = M.templates;
  box.replaceChildren(
    h("section", { class: "panel" },
      h("div", { class: "row" }, h("h2", {}, "Sending"), switchEl(M.enabled, M.enabled ? "Send emails: On" : "Send emails: Off", async (on, inp) => {
        try { await api("POST", "/api/mail/settings", Object.assign(mailBody(R, snd), { enabled: on })); toast(on ? "Email sending is on." : "Email sending is off. Results are only saved in the app.", on ? "ok" : "info"); loadMail(); load(); }
        catch (e) { inp.checked = !on; toast(e.message, "err"); } }, "Turn all job emails on or off")),
      h("p", { class: "small muted", style: "margin:0" }, "Accounts sign in with a Gmail app password (Google's supported way for apps to send mail). It's encrypted with Windows' own data protection, so only your Windows account on this PC can read it, and it's never shown again.")),
    h("section", { class: "panel" },
      h("div", { class: "row" }, h("h2", {}, "Sending Gmail accounts"), h("button", { type: "button", class: "primary", onclick: addAccountDialog }, "Add Gmail account")), accRows),
    h("section", { class: "panel" },
      h("h2", {}, "Default recipients"),
      h("p", { class: "small muted", style: "margin:0" }, "Used by every card that doesn't have its own recipients. Type or paste addresses separated by commas."),
      addrField(R, "to", "To"), addrField(R, "cc", "CC"), addrField(R, "bcc", "BCC (hidden from others)")),
    h("section", { class: "panel" },
      h("h2", {}, "Default sending rule"), senderBox,
      h("div", { style: "display:grid;gap:6px" }, h("span", { class: "small", style: "font-weight:600" }, "If an account can't be used (signed out, limit reached)"), fallbackEditor(snd, { id: "g" })),
      h("div", { class: "grid2" },
        h("label", {}, "Sender name shown in inboxes", fromI = h("input", { value: M.mail.from_name || "Job Radar", maxlength: 60 })),
        h("label", {}, "Daily limit per account (recipients)", limitI = h("input", { type: "number", min: 1, max: 2000, value: M.mail.daily_limit }))),
      h("p", { class: "small muted", style: "margin:0" }, "Free Gmail accounts can send to about 500 recipients a day. Job Radar stops an account before the limit and applies the rule above."),
      h("div", { class: "btns" }, h("button", { type: "button", class: "primary", onclick: () => saveMail(R, snd, limitI.value, fromI.value) }, "Save recipients and rules"))),
    h("section", { class: "panel" },
      h("div", { class: "row" }, h("h2", {}, "Email templates"), h("button", { type: "button", class: "primary", onclick: () => templateDialog(null) }, "New template")),
      h("div", { style: "display:grid;gap:8px" }, tmpl.map((t) => h("div", { class: "sc" + (t.enabled ? "" : " off") },
        h("div", { class: "sc-head" }, h("div", { style: "min-width:0" }, h("b", {}, t.name), " ", t.is_default ? h("span", { class: "chip info" }, "Default") : null, " ", h("span", { class: "chip" }, "v" + t.version),
            h("div", { class: "small muted" }, t.description || ""), h("div", { class: "small" }, "Subject: ", h("code", {}, t.subject)),
            h("div", { class: "small muted" }, t.used_by.length ? "Used by: " + t.used_by.join(", ") : (t.is_default ? "Used by every card without its own template" : "Not assigned to a card"))),
          switchEl(t.enabled, t.enabled ? "On" : "Off", async (on, inp) => { try { await api("POST", `/api/mail/templates/${t.id}/flags`, { enabled: on }); loadMail(); } catch (e) { inp.checked = !on; toast(e.message, "err"); } }, "Turn template on or off")),
        h("div", { class: "jc-acts" },
          h("button", { type: "button", onclick: () => templateDialog(t) }, "Edit"),
          h("button", { type: "button", onclick: () => previewTemplate(t) }, "Preview"),
          h("button", { type: "button", onclick: async () => { try { await api("POST", `/api/mail/templates/${t.id}/duplicate`, {}); toast("Template duplicated."); loadMail(); } catch (e) { toast(e.message, "err"); } } }, "Duplicate"),
          !t.is_default ? h("button", { type: "button", disabled: !t.enabled, onclick: async () => { try { await api("POST", `/api/mail/templates/${t.id}/flags`, { default: true }); toast(`“${t.name}” is now the default template.`); loadMail(); load(); } catch (e) { toast(e.message, "err"); } } }, "Make default") : null,
          !t.is_default ? h("button", { type: "button", disabled: !!t.used_by.length, title: t.used_by.length ? "Used by a card" : "", onclick: () => deleteTemplate(t) }, "Delete") : null))))),
    h("section", { class: "panel" }, h("div", { class: "row" }, h("h2", {}, "Email history"), h("button", { type: "button", onclick: loadMail }, "Refresh")), mailHistoryTable(M.history, true)),
    h("section", { class: "panel" }, h("h2", {}, "Mail activity"),
      M.activity.length ? h("ol", { class: "timeline", style: "max-height:260px" }, M.activity.map((a) => h("li", {}, h("span", { class: "ic info" }, "✉"), h("div", {}, h("time", {}, fmtDT(a.at)), a.detail)))) : h("div", { class: "muted small" }, "Nothing yet.")));
}
function mailBody(R, snd) { return { to: R.to, cc: R.cc, bcc: R.bcc, sender: { mode: snd.mode, accounts: snd.accounts, strategy: snd.strategy }, fallback: snd.fallback, enabled: S.mail.enabled }; }
async function saveMail(R, snd, limit, from, confirm) {
  const bad = addrProblems(R); if (bad.length) return toast(`Fix the invalid address${bad.length > 1 ? "es" : ""}: ${bad.join(", ")}`, "err");
  if (snd.mode === "multi" && snd.accounts.length < 2) return toast("Pick at least two accounts, or choose a single account.", "err");
  try {
    const r = await fetch("/api/mail/settings", { method: "POST", headers: { "Content-Type": "application/json", "X-JobRadar": "1" },
      body: JSON.stringify(Object.assign(mailBody(R, snd), { daily_limit: Number(limit), from_name: from, confirm_copies: !!confirm })) });
    const d = await r.json().catch(() => ({}));
    if (r.status === 409 && d.error === "confirm_copies") {
      if (await confirmBox("Send duplicate emails?", "With ‘Send a copy from each account’, every recipient gets one copy of each job email from every selected account. Use this only if that's what you want.", "Yes, send copies")) return saveMail(R, snd, limit, from, true);
      return;
    }
    if (!r.ok) return toast(d.error || "Couldn't save.", "err");
    toast("Mail settings saved."); flashStatus("success"); loadMail(); load();
  } catch (e) { toast(e.message, "err", [["Retry", () => saveMail(R, snd, limit, from, confirm)]]); }
}
async function accountAction(a, act, btn) {
  if (btn) { btn.disabled = true; }
  busy(true, act === "test" ? "Testing Gmail" : "Saving");
  try { const r = await api("POST", `/api/mail/accounts/${a.id}/${act}`, {}); toast(act === "test" ? r.message : `${a.email} is now the default sending account.`, r.ok === false ? "err" : "ok"); }
  catch (e) { toast(e.message, "err"); }
  finally { busy(false); if (btn) btn.disabled = false; loadMail(); load(); }
}
async function addAccountDialog() {
  let em, pw, nm, test;
  await modal({ title: "Add Gmail account", body: [
      h("ol", { class: "small", style: "margin:0;padding-left:18px" }, h("li", {}, "Turn on 2-Step Verification for the Gmail account."),
        h("li", {}, "Open ", h("a", { href: "https://myaccount.google.com/apppasswords", target: "_blank", rel: "noopener" }, "myaccount.google.com/apppasswords"), ", create an app password named ‘Job Radar’."),
        h("li", {}, "Paste the 16 letters below. Your normal Gmail password is never used.")),
      h("label", {}, "Gmail address", em = h("input", { type: "email", placeholder: "jobs.account@gmail.com", autocomplete: "off" })),
      h("label", {}, "App password", pw = h("input", { type: "password", placeholder: "16 letters", autocomplete: "new-password" })),
      h("label", { class: "inline-check" }, test = h("input", { type: "checkbox", checked: true }), "Sign in now to check it (recommended)")],
    actions: [{ label: "Cancel", value: null }, { label: "Add account", value: "ok", primary: true, onClick: async () => {
      const e = em.value.trim(), p = pw.value.replace(/\s+/g, "");
      if (!EMAIL_OK(e)) { toast("Enter a valid Gmail address.", "err"); return false; }
      if (!/^[A-Za-z]{16}$/.test(p)) { toast(`An app password is exactly 16 letters; this has ${p.length} characters.`, "err"); return false; }
      busy(true, "Signing in to Gmail");
      try { await api("POST", "/api/mail/accounts", { email: e, password: p, test: test.checked }); toast(`${e} added` + (test.checked ? " and signed in." : ". Press Test to check it.")); }
      catch (err) { toast(err.message, "err"); return false; } finally { busy(false); }
    } }] });
  loadMail(); load();
}
async function reconnectDialog(a) {
  let pw;
  await modal({ title: `Reconnect ${a.email}`, body: [h("p", { style: "margin:0", class: "small" }, "Create a new app password for this account at myaccount.google.com/apppasswords and paste it here. The old one is replaced."),
      h("label", {}, "App password", pw = h("input", { type: "password", placeholder: "16 letters", autocomplete: "new-password" }))],
    actions: [{ label: "Cancel", value: null }, { label: "Sign in and save", value: "ok", primary: true, onClick: async () => {
      busy(true, "Signing in to Gmail");
      try { await api("POST", `/api/mail/accounts/${a.id}/reconnect`, { password: pw.value }); toast(`${a.email} is connected.`); }
      catch (e) { toast(e.message, "err"); return false; } finally { busy(false); }
    } }] });
  loadMail(); load();
}
async function removeAccount(a, act, confirmUse) {
  try {
    const r = await fetch(`/api/mail/accounts/${a.id}/${act}`, { method: "POST", headers: { "Content-Type": "application/json", "X-JobRadar": "1" }, body: JSON.stringify({ confirm: !!confirmUse }) });
    const d = await r.json().catch(() => ({}));
    if (r.status === 409) {
      const ok = await confirmBox(`${act === "remove" ? "Remove" : "Disconnect"} ${a.email}?`, `It's used by: ${d.used_by.join(", ")}. Emails that should go from it will follow the fallback rule (or stop and show an error) until you pick another account.`, act === "remove" ? "Remove anyway" : "Disconnect anyway", true);
      return ok ? removeAccount(a, act, true) : undefined;
    }
    if (!r.ok) return toast(d.error || "Couldn't do that.", "err");
    if (!confirmUse && !(await confirmBox(`${act === "remove" ? "Remove" : "Disconnect"} ${a.email}?`, act === "remove" ? "The account and its saved app password are removed. Past email history keeps the address." : "Its app password is deleted from this computer. You can reconnect later.", act === "remove" ? "Remove" : "Disconnect", true))) return;
  } catch (e) { return toast(e.message, "err"); }
  toast(`${a.email} ${act === "remove" ? "removed" : "disconnected"}.`); loadMail(); load();
}
async function sendTestDialog(a) {
  let to;
  await modal({ title: `Send a test from ${a.email}`, body: h("label", {}, "Send the test to", to = h("input", { type: "email", value: (S.mail.mail.to[0] || ""), placeholder: "name@example.com" })),
    actions: [{ label: "Cancel", value: null }, { label: "Send test", value: "ok", primary: true, onClick: async () => {
      busy(true, "Sending test");
      try { const r = await api("POST", `/api/mail/accounts/${a.id}/send-test`, { to: to.value.trim() }); toast(r.message); }
      catch (e) { toast(e.message, "err"); return false; } finally { busy(false); loadMail(); }
    } }] });
}

/* templates */
const PH_CARD = ["job_search_name", "search_date", "total_jobs_found", "new_jobs_found", "cities", "work_modes", "job_list"];
const PH_JOB = ["job_title", "company_name", "job_location", "work_mode", "job_url", "job_description", "match_score", "salary"];
async function previewTemplate(t, card) {
  try {
    const r = await api("POST", "/api/mail/preview", { subject: t.subject, body: t.body, card_name: card || "Example search" });
    if (r.problems.length) return toast(r.problems.join(" "), "err");
    const fr = h("iframe", { title: "Email preview", sandbox: "", style: "width:100%;height:55vh;border:1px solid var(--line);border-radius:8px;background:#fff" }); fr.srcdoc = r.preview.html;
    modal({ title: "Preview: " + (t.name || "template"), body: [h("div", { class: "small" }, h("b", {}, "Subject: "), r.preview.subject), fr,
      h("p", { class: "small muted", style: "margin:0" }, "Example data. The third job has no company, location or valid link, to show how missing values look.")], actions: [{ label: "Close", value: null, primary: true }] });
  } catch (e) { toast(e.message, "err"); }
}
async function templateDialog(t) {
  const st = { name: t ? t.name : "", description: t ? t.description || "" : "", subject: t ? t.subject : "{{total_jobs_found}} jobs for {{job_search_name}} — {{search_date}}",
    body: t ? t.body : "Hello,\n\nHere are today's jobs for {{job_search_name}}.\n\n{{#jobs}}• {{job_title}} — {{company_name}} ({{job_location}}, {{work_mode}})\n  {{job_url}}\n\n{{/jobs}}Regards,\nJob Radar" };
  let bodyTa, subjI, probBox;
  const insert = (ph) => { const el = document.activeElement === subjI ? subjI : bodyTa; const s = el.selectionStart ?? el.value.length; el.value = el.value.slice(0, s) + `{{${ph}}}` + el.value.slice(el.selectionEnd ?? s); el.focus(); el.selectionStart = el.selectionEnd = s + ph.length + 4; st[el === subjI ? "subject" : "body"] = el.value; check(); };
  const check = async () => { try { const r = await api("POST", "/api/mail/preview", { subject: st.subject, body: st.body }); probBox.replaceChildren(r.problems.length ? h("div", { class: "note bad" }, r.problems.join(" ")) : h("div", { class: "note ok" }, "All placeholders are valid.")); return r.problems; } catch { return []; } };
  let tm; const later = () => { clearTimeout(tm); tm = setTimeout(check, 400); };
  await modal({ title: t ? `Edit “${t.name}”` : "New email template", body: [
      h("div", { class: "grid2" }, h("label", {}, "Name", h("input", { value: st.name, oninput: (e) => { st.name = e.target.value; } })), h("label", {}, "Description", h("input", { value: st.description, oninput: (e) => { st.description = e.target.value; } }))),
      h("label", {}, "Subject", subjI = h("input", { value: st.subject, oninput: (e) => { st.subject = e.target.value; later(); } })),
      h("label", {}, "Body", bodyTa = h("textarea", { rows: 10, style: "font:13px/1.5 var(--mono)", oninput: (e) => { st.body = e.target.value; later(); } })),
      h("div", { class: "small" }, h("b", {}, "Insert: "), PH_CARD.map((p) => h("button", { type: "button", class: "linkish", style: "margin-right:8px", onclick: () => insert(p) }, `{{${p}}}`))),
      h("div", { class: "small" }, h("b", {}, "Inside the job list: "), h("button", { type: "button", class: "linkish", style: "margin-right:8px", onclick: () => insert("#jobs") }, "{{#jobs}}"), PH_JOB.map((p) => h("button", { type: "button", class: "linkish", style: "margin-right:8px", onclick: () => insert(p) }, `{{${p}}}`)), h("button", { type: "button", class: "linkish", onclick: () => insert("/jobs") }, "{{/jobs}}")),
      h("p", { class: "small muted", style: "margin:0" }, "Text between {{#jobs}} and {{/jobs}} repeats for every job. {{job_list}} inserts the full job cards (description, why it matches, apply links). If you use neither, the full job cards are added after your text. Missing values show as ‘Not stated’, never as {{…}}."),
      probBox = h("div", {})],
    actions: [{ label: "Cancel", value: null }, { label: "Preview", value: null, onClick: async () => { await previewTemplate(Object.assign({ name: st.name }, st)); return false; } },
      { label: t ? "Save (new version)" : "Create template", value: "ok", primary: true, onClick: async () => {
        if (!st.name.trim()) { toast("Give the template a name.", "err"); return false; }
        const probs = await check(); if (probs.length) { toast("Fix the template first.", "err"); return false; }
        try { await api("POST", t ? `/api/mail/templates/${t.id}` : "/api/mail/templates", st); toast(t ? "Template saved. Cards using it get the new version." : "Template created."); }
        catch (e) { toast(e.message, "err"); return false; }
      } }] });
  loadMail();
}
setTimeout(() => {}, 0);
async function deleteTemplate(t) {
  if (!(await confirmBox(`Delete “${t.name}”?`, "It's removed from the list. Email history still shows which template and version each email used.", "Delete template", true))) return;
  try { await api("DELETE", "/api/mail/templates/" + t.id); toast("Template deleted."); loadMail(); } catch (e) { toast(e.message, "err"); }
}

/* history table: one row per email, with one line per sending account */
function mailHistoryTable(rows, showCard) {
  if (!rows.length) return h("div", { class: "empty" }, "No emails yet.");
  return h("div", { class: "tblwrap" }, h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["When", showCard ? "Card" : null, "Template", "Sender → result", "Recipients", "Jobs", "Status", ""].filter(Boolean).map((x) => h("th", {}, x)))),
    h("tbody", {}, rows.map((r) => h("tr", {},
      h("td", { class: "small" }, fmtDT(r.at), h("div", { class: "muted" }, { "email-now": "Email results now", resend: "Resend", run: "Search run", schedule: "Schedule" }[r.trigger] || r.trigger || "")),
      showCard ? h("td", {}, r.card_name || "—") : null,
      h("td", { class: "small" }, r.template_name ? `${r.template_name} (v${r.template_version || 1})` : "—"),
      h("td", { class: "small" }, r.attempts.length ? r.attempts.map((a) => h("div", {}, (a.account_email || a.selected_email || "—") + " → ", h("b", {}, MAIL_ST[a.status] || a.status),
          a.fallback_reason ? h("div", { class: "warn-text" }, a.fallback_reason) : null, a.error ? h("div", { class: "err-line" }, a.error) : null,
          a.message_id && a.status === "sent" ? h("div", { class: "muted", title: "Message-ID: search for it in the Gmail Sent folder" }, "ID " + a.message_id.slice(0, 28) + "…") : null)) : h("span", { class: "muted" }, "Not sent")),
      h("td", { class: "small" }, r.recipients_count != null ? `${r.recipients_count}` : "—", r.recipients ? h("div", { class: "muted" }, r.recipients) : null),
      h("td", {}, r.jobs_included ?? 0),
      h("td", {}, stChip(MAIL_ST[r.status] || r.status), r.status === "skipped" && r.error ? h("div", { class: "small muted" }, r.error) : null,
        r.status === "sent" ? h("div", { class: "small muted" }, "Accepted by Gmail") : null),
      h("td", {}, h("div", { class: "btns", style: "justify-content:flex-start" },
        r.has_message ? h("a", { class: "btn", href: `/api/mail/message/${r.id}`, target: "_blank", rel: "noopener" }, "View") : null,
        ["failed", "partial", "uncertain"].includes(r.status) && r.has_message ? h("button", { type: "button", onclick: () => resendMail(r) }, r.status === "partial" ? "Resend failed" : "Resend") : null)))))));
}
async function resendMail(r, confirm) {
  if (r.status === "uncertain" && !confirm) {
    const ok = await confirmBox("Resend this email?", "The connection broke while this email was being handed to Gmail, so it may already have been sent. Check the Sent folder of " +
      (r.attempts.map((a) => a.account_email).filter(Boolean).join(", ") || "the sending account") + " first. Resending may give recipients a second copy.", "Resend anyway", true);
    if (!ok) return; confirm = true;
  }
  busy(true, "Sending");
  try { const d = await api("POST", `/api/mail/resend/${r.id}`, { confirm: !!confirm }); toast(d.message, d.ok ? "ok" : "err"); }
  catch (e) { toast(e.message, "err"); } finally { busy(false); loadMail(); load(); }
}

/* card Email settings */
async function emailDialog(c) {
  if (!S.mail) await loadMail();
  const M = S.mail, cfg = c.email_cfg, raw = cfg.raw || {};
  const st = { enabled: cfg.enabled, mode: raw.recipients_mode || "global", R: { to: (c.email ? c.email.split(/,\s*/) : []), cc: (raw.cc || []).slice(), bcc: (raw.bcc || []).slice() },
    template: raw.template_id || "", snd: raw.sender ? { mode: raw.sender.mode, accounts: raw.sender.accounts.slice(), strategy: raw.sender.strategy } : { mode: "inherit", accounts: [], strategy: "copy" },
    fb: { fallback: raw.fallback || "inherit" } };
  const wrap = h("div", { style: "display:grid;gap:14px" });
  const g = M.mail;
  const draw = () => {
    const recRadio = (k, l, d) => { const r = h("input", { type: "radio", name: "rm", onchange: () => { st.mode = k; draw(); } }); r.checked = st.mode === k;
      return h("label", { class: "inline-check", style: "align-items:flex-start;font-weight:500" }, r, h("span", {}, h("b", {}, l), h("span", { class: "small muted", style: "display:block" }, d))); };
    const tsel = h("select", { onchange: (e) => { st.template = e.target.value ? Number(e.target.value) : ""; } },
      h("option", { value: "" }, "Use the default template (" + ((M.templates.find((t) => t.is_default) || {}).name || "built-in") + ")"),
      M.templates.map((t) => h("option", { value: t.id, selected: st.template === t.id, disabled: !t.enabled }, t.name + (t.enabled ? "" : " (off)"))));
    wrap.replaceChildren(
      h("label", { class: "inline-check" }, (() => { const x = h("input", { type: "checkbox", onchange: (e) => { st.enabled = e.target.checked; draw(); } }); x.checked = st.enabled; return x; })(), "Email this card's results"),
      !st.enabled ? h("div", { class: "note" }, "Off: no emails for this card, from schedules or runs. Results stay in the app. ‘Email results now’ still works.") : null,
      h("fieldset", { style: "border:0;padding:0;margin:0;display:grid;gap:6px" }, h("legend", { style: "font-weight:600;margin-bottom:4px" }, "Who gets it"),
        recRadio("global", "Default recipients", (g.to.concat(g.cc, g.bcc).length ? g.to.concat(g.cc).join(", ") + (g.bcc.length ? ` (+${g.bcc.length} BCC)` : "") : "None set yet. Add them in the Mail tab.")),
        recRadio("custom", "Only for this card", "Its own To, CC and BCC lists."),
        recRadio("none", "Don't email anyone", "Keeps the card emailing nobody, even if default recipients are added later."),
        st.mode === "custom" ? h("div", { style: "display:grid;gap:8px;padding-left:24px" }, addrField(st.R, "to", "To"), addrField(st.R, "cc", "CC"), addrField(st.R, "bcc", "BCC")) : null),
      h("fieldset", { style: "border:0;padding:0;margin:0;display:grid;gap:6px" }, h("legend", { style: "font-weight:600;margin-bottom:4px" }, "Template"),
        h("div", { class: "row", style: "flex-wrap:nowrap" }, tsel, h("button", { type: "button", onclick: () => { const t = M.templates.find((x) => x.id === st.template) || M.templates.find((x) => x.is_default); if (t) previewTemplate(t, c.name); } }, "Preview"))),
      h("fieldset", { style: "border:0;padding:0;margin:0;display:grid;gap:6px" }, h("legend", { style: "font-weight:600;margin-bottom:4px" }, "Send from"), senderEditor(st.snd, M.accounts, { inherit: true, id: "c" })),
      h("fieldset", { style: "border:0;padding:0;margin:0;display:grid;gap:6px" }, h("legend", { style: "font-weight:600;margin-bottom:4px" }, "If an account can't be used"), fallbackEditor(st.fb, { inherit: true, id: "c" })),
      h("p", { class: "small muted", style: "margin:0" }, "When it's sent: with every run of this card (Run search or its schedules). Change the times with Schedule on the card."));
  };
  draw();
  const save = async (confirm) => {
    if (st.mode === "custom") { const bad = addrProblems(st.R); if (bad.length) { toast("Fix: " + bad.join(", "), "err"); return false; }
      if (!st.R.to.length && !st.R.cc.length && !st.R.bcc.length) { toast("Add at least one recipient, or choose ‘Don't email anyone’.", "err"); return false; } }
    if (st.snd.mode === "multi" && st.snd.accounts.length < 2) { toast("Pick at least two accounts.", "err"); return false; }
    const body = { enabled: st.enabled, recipients_mode: st.mode, to: st.R.to, cc: st.R.cc, bcc: st.R.bcc, template_id: st.template || null,
      sender: st.snd.mode === "inherit" ? null : st.snd, fallback: st.fb.fallback === "inherit" ? null : st.fb.fallback, confirm_copies: !!confirm };
    const r = await fetch(`/api/profiles/${c.id}/email`, { method: "POST", headers: { "Content-Type": "application/json", "X-JobRadar": "1" }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    if (r.status === 409 && d.error === "confirm_copies") {
      if (await confirmBox("Send duplicate emails?", "Each selected account will send its own copy, so every recipient gets several copies of this card's emails.", "Yes, send copies")) return save(true);
      return false;
    }
    if (!r.ok) { toast(d.error || "Couldn't save.", "err"); return false; }
    toast(`Email settings for “${c.name}” saved.`); load();
  };
  await modal({ title: `Email settings: ${c.name}`, body: wrap, actions: [{ label: "Cancel", value: null }, { label: "Save", value: "ok", primary: true, onClick: () => save(false) }] });
}
