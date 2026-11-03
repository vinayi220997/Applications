/* ---- Demo backend: runs entirely in this page with sample data. The real app talks to the Job Radar service on your computer. ---- */
const DEMO = (() => {
  const H = 3600e3, now = Date.now(), ago = (h) => new Date(now - h * H).toISOString();
  const M = {
    settings: { email: { enabled: false, username: "", app_password: "" }, sources: { adzuna: { enabled: false, app_id: "", app_key: "" } }, anthropic: { api_key: "" } },
    schedule: { enabled: false, text: "Not scheduled. Scans run only when you start them." },
    profiles: [{ id: 1, name: "Sample – backend developer", email: "", email_on: true, active: true, created_at: ago(30),
      summary: "backend developer, software engineer · 3–5 years · Bengaluru + remote international · any",
      profile: { roles: ["backend developer", "software engineer"], skills: ["python", "django", "aws"] } }],
    runs: [{ id: 1, started_at: ago(0.5), status: "completed", trigger: "sample", sources_configured: 74, sources_scanned: 71, retrieved: 3912, unique_jobs: 3655,
      failures: ["Greenhouse board 'examplecorp': network error: timed out", "Lever board 'samplelabs': HTTP 500", "jobicy: network error: timed out"],
      summary: { 1: { reported: 5, email_sent: false, email_note: "email sending is not configured (Settings → Email)" } } }],
    states: {}, nextId: 2, run: null,
  };
  const desc = (t) => t + "\n\nThis is sample text for the demo. In the real app this panel shows the full job description from the employer's listing.";
  const J = [
    { id: "g1", title: "Backend Engineer II", company: "Acme Pay (sample)", location: "Bengaluru, Karnataka, India", work_arrangement: "hybrid", employment_type: "Full-time",
      salary_text: null, published_at: ago(5), first_seen_at: ago(0.5), verified_at: ago(0.5), status: "verified_active", score: 88, freshness: "24h", source_name: "Greenhouse",
      reasons: ["Title matches your target role (Backend Engineer II)", "Located in Bengaluru (hybrid)", "Skills mentioned in the job: python, django, aws", "Experience fits: asks for 3–5 years, you have 3–5 years"],
      gaps: ["Job also asks for (not established in your profile): kafka, postgresql", "Salary not stated; can't confirm your minimum"],
      description: desc("Build and scale payment APIs used by millions of merchants. Python, Django, PostgreSQL, Kafka on AWS. 3-5 years of experience.") },
    { id: "l1", title: "Software Engineer – Backend", company: "Beta Labs (sample)", location: "Bangalore", work_arrangement: "hybrid", employment_type: "Full-time",
      salary_text: "₹25–35 LPA", published_at: ago(110), first_seen_at: ago(0.5), verified_at: ago(0.5), status: "verified_active", score: 86, freshness: "7d", source_name: "Lever",
      reasons: ["Located in Bengaluru (hybrid)", "Skills mentioned in the job: python, django, aws", "Experience fits: asks for 3+ years, you have 3–5 years", "Pay meets your minimum (₹25–35 LPA)"], gaps: [],
      description: desc("Own services end to end: design, build, deploy and operate. Python/Django, AWS. Minimum 3 years of experience.") },
    { id: "r1", title: "Backend Python Engineer", company: "Gamma Remote (sample)", location: "Remote (Worldwide)", work_arrangement: "remote", employment_type: "Full-time",
      salary_text: null, published_at: ago(30), first_seen_at: ago(0.5), verified_at: ago(0.5), status: "appears_active", apply_url_verified: 1, score: 84, freshness: "3d", source_name: "Remotive",
      reasons: ["Remote role open to candidates in any country", "Skills mentioned in the job: python, django, aws", "Experience fits: asks for 3+ years, you have 3–5 years"],
      gaps: ["Salary not stated; can't confirm your minimum"], description: desc("Fully remote team across 12 time zones. Python, Django, AWS. 3+ years of experience.") },
    { id: "g2", title: "Senior Software Engineer, Payments", company: "Acme Pay (sample)", location: "Remote - India", work_arrangement: "remote", employment_type: "Full-time",
      salary_text: null, published_at: ago(60), first_seen_at: ago(0.5), verified_at: ago(0.5), status: "verified_active", score: 69, freshness: "3d", source_name: "Greenhouse",
      reasons: ["Remote role open to candidates in India", "Skills mentioned in the job: python, aws", "Experience fits: asks for 4+ years, you have 3–5 years"],
      gaps: ["Not mentioned in the job: django", "Job also asks for (not established in your profile): kubernetes", "Salary not stated; can't confirm your minimum"],
      description: desc("Python, AWS, Kubernetes. 4+ years of experience.") },
    { id: "w1", title: "Python Developer", company: "Delta Systems (sample)", location: "Remote (APAC)", work_arrangement: "remote", employment_type: "Contract",
      salary_text: null, published_at: null, first_seen_at: ago(0.5), verified_at: ago(0.5), status: "unable_to_verify", apply_url_verified: 0, score: 62, freshness: "unknown", source_name: "We Work Remotely",
      reasons: ["Remote role open to candidates in APAC", "Skills mentioned in the job: python"], gaps: ["Not mentioned in the job: django, aws", "Required experience not stated"],
      description: desc("Contract Python role, APAC hours.") },
  ].map((j, i) => ({ ...j, apply_url: "https://example.com/apply/" + j.id, careers_url: "https://example.com/careers", source_url: "https://example.com/listing/" + j.id }));

  /* small client-side version of the intake questions */
  const Q = [
    ["roles", "I'll search for: {v}. Is that right? Reply yes, or type the titles you want.", ["Yes"]],
    ["experience", "How many years of relevant experience do you have?", ["0–1 years", "1–3 years", "3–5 years", "5–8 years", "8+ years"]],
    ["locations", "Where do you want to work? Pick one or type your cities.", ["Anywhere in India", "Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi NCR", "Mumbai"]],
    ["remote_international", "Should I include remote jobs at international companies that hire from India?", ["Yes", "No"]],
    ["work_arrangement", "Which work arrangement suits you?", ["Remote", "Hybrid", "Onsite", "Any"]],
    ["skills", "Which skills or tools must the job use? List the main ones.", []],
    ["min_salary", "Is there a minimum salary? Type it (e.g. 15 LPA) or reply skip.", ["Skip"]],
    ["email", "Which email should the daily report go to? (reply skip to only see results in the app)", ["Skip"]],
    ["name", "Finally, what should I call this search?", []],
  ];
  const ROLES = ["software engineer", "backend developer", "backend engineer", "frontend developer", "full stack developer", "data analyst", "data scientist", "data engineer", "devops engineer", "product manager", "qa engineer", "machine learning engineer", "ui/ux designer", "business analyst", "android developer"];
  const SK = ["python", "java", "javascript", "typescript", "react", "node.js", "django", "flask", "spring", "aws", "azure", "gcp", "docker", "kubernetes", "sql", "power bi", "tableau", "excel", "spark", "airflow", "figma", "selenium", "go", "kafka", "postgresql"];
  const CITIES = ["Bengaluru", "Bangalore", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi", "Gurugram", "Noida", "Kolkata", "Ahmedabad", "Kochi"];
  const find = (t, list) => list.filter((x) => new RegExp("(^|[^a-z])" + x.replace(/[.+/]/g, "\\$&") + "($|[^a-z])", "i").test(t));
  function parse(t) {
    const p = {};
    const r = find(t, ROLES); if (r.length) p.roles = r;
    const s = find(t, SK); if (s.length) p.skills = s;
    const e = t.match(/(\d{1,2})\s*(\+|[-–to ]+\s*\d{1,2})?\s*(years?|yrs?)/i); if (e) p.experience = e[0];
    const c = find(t, CITIES).map((x) => (x === "Bangalore" ? "Bengaluru" : x)); if (c.length) p.locations = [...new Set(c)];
    if (/hybrid/i.test(t)) p.work_arrangement = "hybrid"; else if (/remote|work from home/i.test(t)) p.work_arrangement = "remote";
    const m = t.match(/\d+(\.\d+)?\s*(lpa|lakhs?)/i); if (m) p.min_salary = m[0];
    return p;
  }
  function advance(st) {
    const p = st.profile;
    for (const [k, q, o] of Q) {
      if (st.asked.includes(k)) continue;
      const known = p[k] != null && p[k] !== "" && !(Array.isArray(p[k]) && !p[k].length);
      if (known && !["roles", "skills", "min_salary", "email", "name"].includes(k)) continue;
      st.asked.push(k); st.pending = k;
      if (k === "roles" && !known) return { state: st, question: "What job title(s) are you looking for? (e.g. Backend Engineer, Data Analyst)", options: [], done: false };
      if (k === "skills" && known) return { state: st, question: `Must-have skills I found: ${p.skills.join(", ")}. Reply yes, or type the list you want.`, options: ["Yes"], done: false };
      return { state: st, question: q.replace("{v}", (p.roles || []).join(", ")), options: o, done: false };
    }
    p.name = p.name || ((p.roles || ["job"])[0] + " search");
    if ((p.work_arrangement || "").toLowerCase() === "remote" && p.remote_international == null) p.remote_international = true;
    return { state: st, done: true, profile: p };
  }
  function answer(st, a) {
    const k = st.pending, p = st.profile; a = (a || "").trim();
    if (k) {
      if (["roles", "skills"].includes(k) && p[k] && /^(y|yes|ok|correct)\b/i.test(a)) {}
      else if (k === "remote_international") p[k] = /^y/i.test(a);
      else if (/^(skip|none|no)$/i.test(a) && ["min_salary", "email"].includes(k)) {}
      else if (["roles", "skills", "locations"].includes(k)) p[k] = a.split(/[,;/]| and /).map((x) => x.trim()).filter(Boolean);
      else if (k === "email") { if (/\S+@\S+\.\S+/.test(a)) p.email = a; else { st.asked.pop(); const r = advance(st); r.question = "That doesn't look like an email address. Type it again, or reply skip.\n" + r.question; return r; } }
      else p[k] = k === "work_arrangement" ? a.toLowerCase() : a;
      st.pending = null;
    }
    return advance(st);
  }
  const summary = (p) => [(p.roles || []).join(", "), p.experience, (p.locations || ["India"]).join(", ") + (p.remote_international ? " + remote international" : ""), p.work_arrangement].filter(Boolean).join(" · ");
  const ok = (d) => Promise.resolve(JSON.parse(JSON.stringify(d)));
  const fail = (m) => Promise.reject(new Error(m));
  const emailReady = () => M.settings.email.enabled && M.settings.email.username && M.settings.email.app_password;

  return async function api(method, url, body) {
    await new Promise((r) => setTimeout(r, 150));
    body = body || {};
    let m;
    if (url === "/api/state") return ok({ profiles: M.profiles, runs: M.runs, schedule: M.schedule, running: !!M.run, settings: M.settings, companies: { ok: 61, unchecked: 0, dead: 67 } });
    if ((m = url.match(/^\/api\/profiles\/(\d+)\/jobs$/))) return ok({ jobs: Number(m[1]) === 1 ? J.map((j) => ({ ...j, user_state: M.states[j.id] || null })) : [] });
    if ((m = url.match(/^\/api\/profiles\/(\d+)\/email-now$/))) {
      const p = M.profiles.find((x) => x.id == m[1]);
      if (!p || !p.email) return fail("This search has no email address. Add one first.");
      if (!emailReady()) return fail("email sending is not configured (Settings → Email)");
      return ok({ ok: true, message: `Demo: the real app would now email ${p.id === 1 ? J.length : 0} open jobs to ${p.email}.` });
    }
    if ((m = url.match(/^\/api\/profiles\/(\d+)$/))) {
      const p = M.profiles.find((x) => x.id == m[1]);
      if (method === "DELETE") { M.profiles = M.profiles.filter((x) => x !== p); return ok({ ok: true }); }
      for (const k of ["name", "email", "active", "email_on"]) if (k in body) p[k] = body[k];
      return ok({ ok: true });
    }
    switch (url) {
      case "/api/intake/start": {
        const items = (body.attachment_ids || []).map((id) => DEMO_FILES[id]).filter(Boolean);
        if ((body.description || "").length < 5 && !items.length) return fail("Describe the job in a few more words, or attach a resume or job post.");
        const p = parse(body.description || "");
        for (const it of items) for (const [k, v] of Object.entries(it.extracted)) p[k] = Array.isArray(v) ? [...new Set([...(p[k] || []), ...v])] : (p[k] || v);
        const r = advance({ profile: p, asked: [], pending: null });
        if (items.length && r.question) r.question = items.map((i) => i.note).join("\n") + "\n\n" + r.question;
        return ok(r);
      }
      case "/api/intake/attach": {
        const st = body.state; const items = (body.attachment_ids || []).map((id) => DEMO_FILES[id]).filter(Boolean);
        for (const it of items) for (const [k, v] of Object.entries(it.extracted)) st.profile[k] = Array.isArray(v) ? [...new Set([...(st.profile[k] || []), ...v])] : (st.profile[k] || v);
        if (st.pending) { st.asked = st.asked.filter((x) => x !== st.pending); st.pending = null; }
        const r = advance(st); r.notes = items.map((i) => i.note);
        if (r.question) r.question = r.notes.join("\n") + "\n\n" + r.question;
        return ok(r);
      }
      case "/api/intake/answer": return ok(answer(body.state, body.answer));
      case "/api/profiles": {
        const p = body.profile; const id = M.nextId++;
        M.profiles.unshift({ id, name: p.name, email: p.email || "", email_on: true, active: true, summary: summary(p), profile: p, created_at: new Date().toISOString() });
        return ok({ id });
      }
      case "/api/jobs/state": if (!body.state || body.state === "new") delete M.states[body.job_id]; else M.states[body.job_id] = body.state; return ok({ ok: true });
      case "/api/run": {
        if (M.run) return fail("A scan is already running.");
        const steps = ["Scan started for " + M.profiles.filter((p) => p.active).length + " search(es).", "Checking 128 employer job boards…", "Employer boards: 61 answered, 3604 open jobs.",
          "remotive: 96 jobs", "remoteok: 101 jobs", "weworkremotely: 111 jobs", "Stored 3912 listings; 14 jobs closed since the last scan.", "3655 unique jobs after removing duplicates.",
          "[Sample – backend developer] 5 new/updated matches, report saved; " + (emailReady() ? "email sent." : "email sending is not configured (Settings → Email)."), "Scan completed. 71/74 sources scanned."];
        M.run = { lines: [new Date().toLocaleTimeString() + " Starting scan… (demo: no real sites are contacted)"], i: 0 };
        const tick = setInterval(() => {
          M.run.lines.push(new Date().toLocaleTimeString() + " " + steps[M.run.i++]);
          if (M.run.i >= steps.length) { clearInterval(tick); M.runs[0].started_at = new Date().toISOString(); M.runs[0].trigger = "manual";
            M.runs[0].summary[1].email_sent = !!emailReady(); M.runs[0].summary[1].email_note = emailReady() ? "sent" : "email sending is not configured (Settings → Email)";
            setTimeout(() => { M.lastLines = M.run.lines; M.run = null; }, 300); }
        }, 700);
        return ok({ started: true });
      }
      case "/api/run/status": return ok({ running: !!M.run, lines: (M.run || { lines: M.lastLines || [] }).lines });
      case "/api/schedule": {
        if (body.enabled === false) { M.schedule = { enabled: false, text: "Not scheduled. Scans run only when you start them." }; return ok({ ok: true, message: "Schedule removed. Scans now run only when you start them.", schedule: M.schedule }); }
        const days = body.days || [], dtxt = days.length === 7 ? "every day" : days.join(", ");
        M.schedule = { enabled: true, time: body.time, days, every_hours: body.every_hours, text: `Runs ${dtxt} at ${body.time}${body.every_hours ? `, then every ${body.every_hours} hours until midnight` : ""} (your computer's local time). If the computer was off or asleep at that time, the scan runs as soon as it's back on.` };
        return ok({ ok: true, message: "Demo: on your computer this creates the Windows scheduled task. " + M.schedule.text, schedule: M.schedule });
      }
      case "/api/settings": {
        const e = body.email || {}; Object.assign(M.settings.email, { enabled: e.enabled, username: e.username, app_password: e.app_password ? "••••••••" : "" });
        Object.assign(M.settings.sources.adzuna, body.sources?.adzuna || {}); M.settings.anthropic.api_key = body.anthropic?.api_key ? "••••••••" : "";
        return ok({ settings: M.settings });
      }
      case "/api/test-email": return emailReady() ? ok({ ok: true, message: "sent" }) : fail("email sending is not configured (Settings → Email)");
      case "/api/companies": return /greenhouse|lever|ashby|smartrecruiters|workable|recruitee/i.test(body.url || "") ? ok({ ats: "board", token: (body.url.match(/\/([A-Za-z0-9_-]+)\/?$/) || [, "company"])[1] }) : fail("That isn't a supported careers link. Use a Greenhouse, Lever, Ashby, SmartRecruiters, Workable or Recruitee job-board URL.");
      case "/api/doctor": {
        const mail = M.profiles.filter((p) => p.active && p.email && p.email_on);
        return ok({ checks: [
          { name: "Job sites reachable", ok: true, detail: "Demo: on your computer this tests the job-board APIs." },
          emailReady() ? { name: "Email sending", ok: true, detail: "Demo: settings filled in. On your computer this signs in to Gmail to check the app password." }
            : { name: "Email sending", ok: false, detail: "Email sending is turned off, so reports are only saved in the app.", fix: "Open Settings, tick 'Send reports by email', enter your Gmail address and app password, then Save." },
          mail.length ? { name: "Saved searches", ok: true, detail: `${mail.length} active search(es) will be emailed: ` + mail.map((p) => `${p.name} → ${p.email}`).join(", ") }
            : { name: "Saved searches", ok: false, detail: "No active search has an email address with email turned on.", fix: "On a search card press Add email." },
          { name: "Last scan", ok: true, detail: "completed, 71/74 sources. 5 new for one search." },
          { name: "Schedule", ok: M.schedule.enabled, detail: M.schedule.text, fix: M.schedule.enabled ? "" : "Set a time in the Schedule card and press Save schedule." }] });
      }
      case "/api/attachments": {
        const id = Math.random().toString(16).slice(2, 18);
        const n = (body.filename || "").toLowerCase();
        const voice = /\.(webm|ogg|mp3|wav|m4a)$/.test(n), img = /\.(png|jpe?g|webp|gif)$/.test(n);
        const ex = voice ? parse(body.transcript || "") : img ? {} : { roles: ["backend developer"], skills: ["python", "django", "aws", "postgresql"], experience: "4–6 years", locations: ["Bengaluru"] };
        const note = voice ? (body.transcript ? "From your voice note I picked up " + (Object.keys(ex).join(", ") || "nothing new") + "." : "Voice note saved. Live transcription works in Microsoft Edge or Google Chrome.")
          : img ? "Saved the image. In the real app, text is read from images when an Anthropic API key is set in Settings."
          : "Demo: from your resume I picked up role: backend developer; 4 skills (python, django, aws, postgresql); experience: 4–6 years; location: Bengaluru. The real app reads your actual file.";
        DEMO_FILES[id] = { extracted: ex, note };
        return ok({ id, filename: body.filename, kind: voice ? "voice" : img ? "image" : "document", has_text: !img, note, url: body.data });
      }
    }
    return fail("Not available in the demo.");
  };
})();
const DEMO_FILES = {};
