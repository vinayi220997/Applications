"""Guided intake: turn a free-text job description into a precise search profile by asking
only the questions whose answers are missing (location, experience, arrangement, skills, pay ...).

Used by both the command line (`python -m jobradar ask`) and the local web app.
"""
import json
import re
import urllib.request

from .normalize import INDIA_CITIES, canonical_city, match_city, parse_candidate_experience, parse_lpa

ROLE_PHRASES = [
    "software engineer", "software developer", "backend engineer", "backend developer", "frontend engineer",
    "frontend developer", "full stack developer", "full stack engineer", "fullstack developer", "mobile developer",
    "android developer", "ios developer", "react developer", "react native developer", "flutter developer",
    "java developer", "python developer", "node.js developer", "golang developer", ".net developer", "php developer",
    "devops engineer", "site reliability engineer", "sre", "cloud engineer", "platform engineer", "data engineer",
    "data scientist", "data analyst", "business analyst", "machine learning engineer", "ml engineer", "ai engineer",
    "applied scientist", "research engineer", "nlp engineer", "computer vision engineer", "mlops engineer",
    "qa engineer", "test engineer", "sdet", "automation engineer", "security engineer", "network engineer",
    "embedded engineer", "firmware engineer", "product manager", "product owner", "program manager",
    "project manager", "engineering manager", "technical lead", "tech lead", "solutions architect",
    "solution architect", "ui designer", "ux designer", "product designer", "ui/ux designer", "graphic designer",
    "technical writer", "scrum master", "salesforce developer", "sap consultant", "support engineer",
    "customer success manager", "account manager", "sales executive", "business development", "marketing manager",
    "digital marketing", "content writer", "hr executive", "recruiter", "financial analyst", "accountant",
]

SKILLS = [
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#", "kotlin", "swift", "scala",
    "ruby", "php", "r", "sql", "nosql", "react", "react native", "angular", "vue", "next.js", "node.js", "express",
    "django", "flask", "fastapi", "spring", "spring boot", "hibernate", ".net", "asp.net", "rails", "laravel",
    "flutter", "android", "ios", "html", "css", "tailwind", "redux", "graphql", "rest", "grpc", "microservices",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "jenkins", "ci/cd", "github actions",
    "linux", "bash", "kafka", "rabbitmq", "redis", "postgresql", "mysql", "mongodb", "elasticsearch", "cassandra",
    "dynamodb", "snowflake", "bigquery", "redshift", "databricks", "spark", "pyspark", "hadoop", "airflow", "dbt",
    "etl", "tableau", "power bi", "looker", "excel", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "keras", "machine learning", "deep learning", "nlp", "computer vision", "llm", "rag", "langchain",
    "generative ai", "mlops", "statistics", "a/b testing", "selenium", "cypress", "playwright", "jest", "appium",
    "figma", "sketch", "jira", "agile", "scrum", "salesforce", "sap", "servicenow", "power apps",
    "seo", "sem", "google analytics", "hubspot", "content marketing", "networking", "cybersecurity", "siem",
    "system design", "data structures", "oop", "embedded c", "rtos", "iot", "blockchain", "solidity",
]
INDUSTRIES = ["fintech", "saas", "healthtech", "edtech", "e-commerce", "ecommerce", "gaming", "logistics",
              "banking", "insurance", "telecom", "automotive", "retail", "media", "travel", "crypto", "web3",
              "cybersecurity", "ai", "consulting", "manufacturing", "pharma", "real estate", "adtech"]

YES = re.compile(r"^\s*(y|yes|yeah|yep|sure|ok|okay|correct|confirm|looks good|right|fine|that'?s right)\b", re.I)
NO = re.compile(r"^\s*(n|no|nope|not really|don'?t)\b", re.I)
SKIP = re.compile(r"^\s*(skip|none|no|nothing|n/a|na|-|no preference|any)\s*$", re.I)


def _find_terms(text, vocab):
    t = " " + (text or "").lower() + " "
    found = []
    for term in vocab:
        pat = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        if re.search(pat, t) and term not in found:
            found.append(term)
    # drop terms contained in longer found terms (e.g. 'react' when 'react native')
    return [f for f in found if not any(f != g and f in g for g in found)]


def _split_list(s):
    return [x.strip() for x in re.split(r"[,;/\n]| and ", s or "") if x.strip()]


def parse_description(text):
    """Deterministic extraction from a free-text description."""
    p = {}
    roles = _find_terms(text, ROLE_PHRASES)
    if roles:
        p["roles"] = roles
    skills = _find_terms(text, SKILLS)
    if skills:
        p["skills"] = skills
    inds = _find_terms(text, INDUSTRIES)
    if inds:
        p["industries"] = inds
    m = re.search(r"(\d{1,2}\s*(?:\+|[-–to ]+\s*\d{1,2})?)\s*(?:\+\s*)?(?:years?|yrs?)", text or "", re.I)
    if m:
        p["experience"] = m.group(0)
    cities = []
    for c in INDIA_CITIES:
        if re.search(r"\b" + re.escape(c) + r"\b", (text or "").lower()):
            cc = canonical_city(c).title()
            if cc not in cities:
                cities.append(cc)
    if cities:
        p["locations"] = cities
    elif re.search(r"\b(anywhere in india|across india|pan india|india)\b", text or "", re.I):
        p["locations"] = ["India"]
    t = (text or "").lower()
    if "hybrid" in t:
        p["work_arrangement"] = "hybrid"
    elif re.search(r"\bremote|work from home|wfh\b", t):
        p["work_arrangement"] = "remote"
    elif re.search(r"\bonsite|on-site|in office|work from office\b", t):
        p["work_arrangement"] = "onsite"
    if re.search(r"international|global|worldwide|anywhere in the world|foreign compan", t):
        p["remote_international"] = True
    sal = re.search(r"(₹|rs\.?|inr)?\s*\d+(\.\d+)?\s*(lpa|lakhs?|lacs?|l\b|cr)", t)
    if sal:
        p["min_salary"] = sal.group(0).strip()
    if re.search(r"\bintern(ship)?\b", t):
        p["employment_type"] = "internship"
    elif re.search(r"\bcontract\b|freelance", t):
        p["employment_type"] = "contract"
    ex = re.search(r"(?:no|avoid|not interested in|exclude)\s+([a-z ,/&-]{3,80})", t)
    if ex:
        p["exclude"] = _split_list(ex.group(1))[:6]
    return p


def parse_with_claude(text, settings):
    """Optional: use the Anthropic API (if a key is configured) for a richer first parse."""
    cfg = settings.get("anthropic") or {}
    if not cfg.get("api_key") or not (settings.get("ai") or {}).get("enabled", True):
        return None
    prompt = ("Extract a job-search profile from this description. Return ONLY JSON with keys: roles (list of job "
              "titles incl. close equivalents, max 6), skills (must-have, max 12), nice_to_have, industries, "
              "experience (e.g. '3-5 years' or empty), locations (list), work_arrangement (remote|hybrid|onsite|any|''), "
              "remote_international (true/false/null), min_salary (string or ''), exclude (list), employment_type. "
              "Leave unknown fields empty; never invent facts.\n\nDescription:\n" + text[:4000])
    body = json.dumps({"model": cfg.get("model", "claude-haiku-4-5"), "max_tokens": 800,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": cfg["api_key"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            out = json.loads(r.read().decode())
        txt = "".join(b.get("text", "") for b in out.get("content", []))
        m = re.search(r"\{.*\}", txt, re.S)
        data = json.loads(m.group(0)) if m else None
        return {k: v for k, v in (data or {}).items() if v not in (None, "", [], {})}
    except Exception:
        return None


# ------------------------------------------------------------------ question flow
QUESTIONS = [
    {"key": "roles", "ask": "Which job titles should I search for?", "kind": "list",
     "confirm": "I'll search for: {value}. Is that right? Reply yes, or type the titles you want (comma separated).",
     "options": []},
    {"key": "experience", "ask": "How many years of relevant experience do you have?", "kind": "text",
     "options": ["0–1 years", "1–3 years", "3–5 years", "5–8 years", "8+ years"]},
    {"key": "locations", "ask": "Where do you want to work? Pick one or type your cities.", "kind": "list",
     "options": ["Anywhere in India", "Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi NCR", "Mumbai"]},
    {"key": "remote_international", "ask": "Should I include remote jobs at international companies that hire from India?",
     "kind": "bool", "options": ["Yes", "No"]},
    {"key": "work_arrangement", "ask": "Which work arrangement suits you?", "kind": "choice",
     "options": ["Remote", "Hybrid", "Onsite", "Any"]},
    {"key": "skills", "ask": "Which skills or tools must the job use? List the main ones.", "kind": "list",
     "confirm": "Must-have skills I found: {value}. Reply yes, or type the list you want.", "options": []},
    {"key": "min_salary", "ask": "Is there a minimum salary? Type it (e.g. 15 LPA) or reply skip.", "kind": "text",
     "options": ["Skip"]},
    {"key": "exclude", "ask": "Anything to avoid? Roles, companies or industries (or reply skip).", "kind": "list",
     "options": ["Skip"]},
    {"key": "email", "ask": "Which email should the daily report go to? (reply skip to only see results in the app)",
     "kind": "email", "options": ["Skip"]},
    {"key": "name", "ask": "Finally, what should I call this search? (e.g. your name or 'Backend jobs')", "kind": "text",
     "options": []},
]
ALWAYS_CONFIRM = {"roles", "skills"}
OPTIONAL_ALWAYS_ASK = {"min_salary", "exclude", "email", "name"}


def merge_extracted(profile, ex, doc_type="notes"):
    """Fold fields found in an attachment into the profile without overwriting what the person said."""
    for k in ("roles", "skills", "industries", "exclude"):
        if ex.get(k):
            cap = {"roles": 6, "skills": 15}.get(k, 10)
            profile[k] = list(dict.fromkeys((profile.get(k) or []) + list(ex[k])))[:cap]
    for k in ("experience", "locations", "work_arrangement", "min_salary", "employment_type", "remote_international"):
        if ex.get(k) not in (None, "", []) and profile.get(k) in (None, "", []):
            profile[k] = ex[k]
    if doc_type == "resume" and ex.get("resume_titles"):
        profile["resume_titles"] = ex["resume_titles"]
    return profile


def attach(state, items):
    """Add attachment findings mid-conversation, then ask the next useful question (or re-ask the current one)."""
    p = state["profile"]
    notes = []
    for it in items:
        merge_extracted(p, it.get("extracted") or {}, it.get("doc_type"))
        p.setdefault("attachment_ids", [])
        if it.get("id") and it["id"] not in p["attachment_ids"]:
            p["attachment_ids"].append(it["id"])
        if it.get("note"):
            notes.append(it["note"])
    pending = state.get("pending")
    if pending:
        if pending in state["asked"]:
            state["asked"].remove(pending)
        state["pending"] = None
    r = advance(state)
    if notes and r.get("question"):
        r["question"] = "\n".join(notes) + "\n\n" + r["question"]
    r["notes"] = notes
    return r


def start(description, settings=None, items=None):
    profile = parse_description(description)
    for it in items or []:
        merge_extracted(profile, it.get("extracted") or {}, it.get("doc_type"))
        profile.setdefault("attachment_ids", []).append(it.get("id"))
    llm = parse_with_claude(description, settings or {})
    if llm:
        for k, v in llm.items():
            profile.setdefault(k, v)
            if k in ("roles", "skills") and isinstance(v, list):
                profile[k] = list(dict.fromkeys((profile.get(k) or []) + v))[:12]
    profile["description"] = (description or "").strip() or "; ".join(it.get("note", "") for it in items or [])[:500]
    state = {"profile": profile, "asked": [], "pending": None}
    r = advance(state)
    r["ai_used"] = bool(llm)
    notes = [it["note"] for it in items or [] if it.get("note")]
    if notes and r.get("question"):
        r["question"] = "\n".join(notes) + "\n\n" + r["question"]
    return r


def _apply(state, key, answer):
    p = state["profile"]
    q = next(q for q in QUESTIONS if q["key"] == key)
    a = (answer or "").strip()
    if key in ALWAYS_CONFIRM and p.get(key) and YES.match(a):
        return
    if q["kind"] == "bool":
        p[key] = bool(YES.match(a)) and not NO.match(a)
        return
    if SKIP.match(a) and key in OPTIONAL_ALWAYS_ASK | {"work_arrangement"}:
        if key == "work_arrangement":
            p[key] = "any"
        return
    if q["kind"] == "list":
        items = _split_list(a)
        if key == "locations":
            items = ["India" if re.search(r"anywhere|india", i, re.I) else
                     ("Delhi NCR" if re.search(r"ncr|delhi", i, re.I) else i.title()) for i in items]
        p[key] = items
    elif q["kind"] == "choice":
        p[key] = a.lower()
    elif q["kind"] == "email":
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", a)
        if m:
            p[key] = m.group(0)
        else:
            state["error"] = "That doesn't look like an email address. Type it again, or reply skip."
            state["asked"].remove(key)
    elif key == "min_salary":
        n = re.fullmatch(r"\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*", a, re.I)
        if n:
            v = float(n.group(1))
            p[key] = f"{v:g} LPA" if v <= 200 else f"₹{int(v):,} per year"
        else:
            p[key] = a
    else:
        p[key] = a


ADD_WORDS = re.compile(r"\b(add|also|plus|include|including|along with|as well|more|another|extra)\b", re.I)
REMOVE_WORDS = re.compile(r"\b(remove|drop|delete|exclude|without|no longer|don'?t want|not interested in)\b", re.I)
LOC_WORDS = re.compile(r"\b(locations?|city|cities|place|places|relocate|based in|work in)\b", re.I)
SKILL_WORDS = re.compile(r"\b(skills?|tools?|tech|technologies)\b", re.I)
ROLE_WORDS = re.compile(r"\b(roles?|titles?|positions?|job titles?)\b", re.I)
INSTRUCTION = re.compile(r"\b(add|also|plus|include|please|location|locations|city|cities|skill|skills|role|roles|title|titles|"
                         r"remove|drop|change|update|and|to|the|in|my|me|want|need)\b", re.I)


def _locations_in(text):
    t = text or ""
    found = []
    if re.search(r"\b(anywhere in india|across india|pan india|all over india|any city)\b", t, re.I):
        found.append("India")
    if re.search(r"\b(ncr|delhi)\b", t, re.I):
        found.append("Delhi NCR")
    for c in INDIA_CITIES:
        if c in ("delhi", "new delhi", "ncr"):
            continue
        if re.search(r"\b" + re.escape(c) + r"\b", t, re.I):
            name = canonical_city(c).title()
            if name not in found:
                found.append(name)
    # misspellings and short forms: 'bengular', 'hyd', 'vizag'
    skip = set(ROLE_WORDS_SET) | set(SKILLS)
    for w in re.findall(r"[A-Za-z]+", t):
        if w.lower() in skip:
            continue
        c = match_city(w)
        if c:
            name = "Delhi NCR" if c in ("delhi", "ncr") else c.title()
            if name not in found:
                found.append(name)
    return found


ROLE_WORDS_SET = {"designer", "design", "engineer", "developer", "analyst", "manager", "scientist", "architect", "consultant",
                  "lead", "specialist", "executive", "writer", "tester", "administrator", "admin", "intern", "associate",
                  "officer", "recruiter", "accountant", "director", "head", "programmer", "sde", "sre", "devops", "owner",
                  "coordinator", "artist", "illustrator", "researcher", "strategist", "marketer", "editor", "trainer",
                  "teacher", "support", "representative", "agent", "operator", "technician", "advisor", "planner",
                  "product", "ux", "ui", "qa", "data", "frontend", "backend", "fullstack", "mobile", "cloud", "security"}


def _looks_like_role(item):
    t = item.lower()
    if _find_terms(t, ROLE_PHRASES):
        return True
    return any(w in ROLE_WORDS_SET for w in re.findall(r"[a-z]+", t))


def _merge_list(old, new, mode):
    old = list(old or [])
    if mode == "remove":
        low = {x.lower() for x in new}
        return [x for x in old if x.lower() not in low]
    if mode == "add":
        return list(dict.fromkeys(old + list(new)))
    return list(dict.fromkeys(new))


def _clean_items(text):
    """Split a free answer into items, dropping instruction words ('also add location ...')."""
    items = []
    for part in _split_list(text):
        core = INSTRUCTION.sub(" ", part)
        core = re.sub(r"\s+", " ", core).strip(" .,-")
        if len(core) >= 2:
            items.append(core)
    return items


def answer(state, text):
    """Understand a chat message: fill the question being asked, and also pick up anything else the person
    mentions (extra cities, experience, salary, remote/hybrid, email, 'add/remove' skills or roles)."""
    state.pop("error", None)
    p = state["profile"]
    pending = state.get("pending")
    a = (text or "").strip()
    mode = "remove" if REMOVE_WORDS.search(a) else ("add" if ADD_WORDS.search(a) else "replace")
    notes, touched = [], set()

    # --- things that can be said at any point
    locs = _locations_in(a)
    if locs and not (pending in ("roles", "skills") and not LOC_WORDS.search(a) and not mode == "add" and len(locs) < len(_split_list(a))):
        lmode = mode if (pending == "locations" or LOC_WORDS.search(a)) else "add"
        if (pending != "locations" and lmode == "replace") or state.pop("loc_mode", None) == "add":
            lmode = "add" if lmode != "remove" else lmode
        p["locations"] = _merge_list(p.get("locations"), locs, lmode)
        fixed = [w for w in re.findall(r"[A-Za-z]+", a) if w.lower() not in INDIA_CITIES and w.lower() not in ROLE_WORDS_SET
                 and match_city(w) and match_city(w) != w.lower()]
        if fixed:
            notes.append("I read '" + "', '".join(fixed) + "' as " + ", ".join(dict.fromkeys(match_city(w).title() for w in fixed)) + ".")
        notes.append(("Removed from" if lmode == "remove" else "Locations now:") + " " +
                     (", ".join(locs) if lmode == "remove" else ", ".join(p["locations"])) + ".")
        touched.add("locations")
    if pending != "experience":
        m = re.search(r"(\d{1,2})\s*(\+|(?:-|–|to)\s*\d{1,2})?\s*(?:years?|yrs?)", a, re.I)
        if m:
            p["experience"] = m.group(0)
            notes.append(f"Experience: {m.group(0)}.")
            touched.add("experience")
    if pending != "work_arrangement":
        m = re.search(r"\b(remote|hybrid|on-?site|work from office|any arrangement)\b", a, re.I)
        if m and not (pending == "remote_international"):
            val = {"work from office": "onsite", "on-site": "onsite", "any arrangement": "any"}.get(m.group(1).lower(), m.group(1).lower())
            p["work_arrangement"] = val
            notes.append(f"Work arrangement: {val}.")
            touched.add("work_arrangement")
    if pending != "min_salary":
        m = re.search(r"(₹|rs\.?|inr)?\s*\d+(\.\d+)?\s*(lpa|lakhs?|lacs?|cr)\b", a, re.I)
        if m:
            p["min_salary"] = m.group(0).strip()
            notes.append(f"Minimum salary: {p['min_salary']}.")
            touched.add("min_salary")
    if pending != "email":
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", a)
        if m:
            p["email"] = m.group(0)
            notes.append(f"Report email: {p['email']}.")
            touched.add("email")
    if pending != "skills" and SKILL_WORDS.search(a) and mode in ("add", "remove"):
        sk = _find_terms(a, SKILLS) or [x.lower() for x in _clean_items(SKILL_WORDS.sub(" ", a))]
        if sk:
            p["skills"] = _merge_list(p.get("skills"), sk, mode)
            notes.append(("Removed skills: " + ", ".join(sk)) if mode == "remove" else ("Skills now: " + ", ".join(p["skills"])) + ".")
            touched.add("skills")
    if pending != "roles" and ROLE_WORDS.search(a) and mode in ("add", "remove"):
        rl = _find_terms(a, ROLE_PHRASES) or [x.lower() for x in _clean_items(ROLE_WORDS.sub(" ", a)) if _looks_like_role(x)]
        if not rl:
            bad = _clean_items(ROLE_WORDS.sub(" ", a))
            if bad:
                notes.append("I didn't add '" + "', '".join(bad) + "' because it doesn't look like a job title (for example 'product designer').")
        if rl:
            p["roles"] = _merge_list(p.get("roles"), rl, mode)
            notes.append("Job titles now: " + ", ".join(p["roles"]) + ".")
            touched.add("roles")

    # "also add location" without naming a city: ask which ones, then come back to the open question
    if LOC_WORDS.search(a) and not locs and mode != "remove":
        named = [x.title() for x in _clean_items(LOC_WORDS.sub(" ", a)) if not _looks_like_role(x) and not _find_terms(x, SKILLS)]
        if named:
            p["locations"] = _merge_list(p.get("locations"), named, "add")
            notes.append("Added " + ", ".join(named) + " to locations. Locations now: " + ", ".join(p["locations"]) + ".")
            touched.add("locations")
            locs = named
    if LOC_WORDS.search(a) and not locs and mode != "remove" and pending != "locations":
        if pending and pending in state["asked"]:
            state["asked"].remove(pending)
        state["pending"] = "locations"
        state["loc_mode"] = "add"
        if "locations" in state["asked"]:
            state["asked"].remove("locations")
        state["asked"].append("locations")
        return {"state": state, "question": "Sure. Which cities should I add? (current: " + (", ".join(p.get("locations") or []) or "none") + ")",
                "options": ["Anywhere in India", "Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi NCR", "Mumbai"], "done": False, "notes": notes}

    # --- the question that was asked
    answered = True
    if pending:
        if pending in touched:
            pass
        elif pending in ("roles", "skills"):
            if p.get(pending) and YES.match(a):
                pass
            else:
                vocab = ROLE_PHRASES if pending == "roles" else SKILLS
                found = _find_terms(a, vocab)
                rest = _clean_items(a) if not (found or touched) else []
                rest = [x for x in rest if not _locations_in(x)]
                items = found or [x.lower() for x in rest]
                if pending == "roles":
                    odd = [x for x in items if not _looks_like_role(x)]
                    items = [x for x in items if _looks_like_role(x)]
                    if odd:
                        notes.append("I didn't add '" + "', '".join(odd) + "' because it doesn't look like a job title. "
                                     "If it's a city, type 'add city " + odd[0] + "'.")
                if items:
                    p[pending] = _merge_list(p.get(pending), items, mode)
                    if mode != "replace" or pending == "skills":
                        notes.append(("Job titles now: " if pending == "roles" else "Skills now: ") + ", ".join(p[pending]) + ".")
                else:
                    answered = False
        elif pending == "locations" and locs:
            pass
        elif pending == "locations" and not locs:
            items = _clean_items(a)
            if items and not SKIP.match(a):
                p["locations"] = _merge_list(p.get("locations"), [i.title() for i in items], mode)
            elif not touched:
                answered = False
        elif touched and pending not in ("remote_international",) and not re.search(r"\w", INSTRUCTION.sub("", a).strip()):
            answered = False
        else:
            if touched and pending in ("experience", "work_arrangement", "min_salary", "exclude", "name") and not SKIP.match(a):
                # the message was about something else; ask the pending question again
                answered = False
            elif pending == "work_arrangement":
                m = re.search(r"\b(remote|hybrid|on-?site|office|any|anything|no preference|skip)\b", a, re.I)
                if m:
                    p["work_arrangement"] = {"on-site": "onsite", "office": "onsite", "anything": "any", "no preference": "any", "skip": "any"}.get(m.group(1).lower(), m.group(1).lower())
                else:
                    answered = False
                    state["error"] = "Please pick Remote, Hybrid, Onsite or Any."
            else:
                _apply(state, pending, a)
        if not answered and pending in state["asked"]:
            state["asked"].remove(pending)
        state["pending"] = None

    r = advance(state)
    r["notes"] = notes
    if notes and r.get("question"):
        r["question"] = "Got it. " + " ".join(notes) + "\n\n" + r["question"]
    return r


def advance(state):
    p = state["profile"]
    for q in QUESTIONS:
        k = q["key"]
        if k in state["asked"]:
            continue
        known = p.get(k) not in (None, "", [])
        if known and k not in ALWAYS_CONFIRM and k not in OPTIONAL_ALWAYS_ASK:
            continue
        if k == "remote_international" and p.get("remote_international") is not None:
            continue
        if k == "name" and p.get("name"):
            continue
        if k == "email" and p.get("email"):
            continue
        state["asked"].append(k)
        state["pending"] = k
        if known and q.get("confirm"):
            text = q["confirm"].format(value=", ".join(p[k]) if isinstance(p[k], list) else p[k])
            opts = ["Yes"]
        else:
            text, opts = q["ask"], q["options"]
            if k == "roles" and not known:
                text = "What job title(s) are you looking for? (e.g. Backend Engineer, Data Analyst)"
        if state.get("error"):
            text = state["error"] + "\n" + text
        return {"state": state, "question": text, "options": opts, "done": False}
    return {"state": state, "question": None, "options": [], "done": True, "profile": finalize(p)}


def finalize(p):
    out = dict(p)
    out["roles"] = [r for r in (p.get("roles") or []) if r] or [p.get("description", "")[:60]]
    out["skills"] = p.get("skills") or []
    lo, hi = parse_candidate_experience(p.get("experience"))
    out["exp_min"], out["exp_max"] = lo, hi
    out["min_salary_lpa"] = parse_lpa(p.get("min_salary")) if p.get("min_salary") else None
    out["locations"] = p.get("locations") or ["India"]
    out["work_arrangement"] = (p.get("work_arrangement") or "any").lower()
    if out["work_arrangement"] == "remote" and p.get("remote_international") is None:
        out["remote_international"] = True
    out["remote_international"] = bool(p.get("remote_international"))
    out["employment_type"] = p.get("employment_type") or "full-time"
    out["name"] = p.get("name") or (out["roles"][0].title() + " search")
    return out


def summary(p):
    bits = [", ".join(p.get("roles") or []), p.get("experience") or "",
            ", ".join(p.get("locations") or []) + (" + remote international" if p.get("remote_international") else ""),
            p.get("work_arrangement") or ""]
    return " · ".join(b for b in bits if b)


# ------------------------------------------------------------------ review & edit support (progress, diffs, section edits)
LABELS = {"roles": "Job titles", "experience": "Experience", "locations": "Locations",
          "remote_international": "Remote jobs abroad", "work_arrangement": "Work arrangement",
          "skills": "Must-have skills", "min_salary": "Minimum salary", "exclude": "Avoid",
          "email": "Report email", "name": "Search name"}
KIND = {q["key"]: q["kind"] for q in QUESTIONS}
LIST_KEYS = {k for k, v in KIND.items() if v == "list"}


def show(p, key):
    """A field's value as people read it."""
    v = (p or {}).get(key)
    if key == "remote_international":
        return "Yes" if v else ("No" if v is False else "")
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x)
    return "" if v is None else str(v)


def changes(before, after):
    """Field-by-field difference between two profiles (only the questions people answer)."""
    out = []
    for q in QUESTIONS:
        k = q["key"]
        o, n = show(before, k), show(after, k)
        if o != n:
            out.append({"key": k, "label": LABELS[k], "old": o, "new": n})
    return out


def _will_skip(state, k):
    p = state["profile"]
    known = p.get(k) not in (None, "", [])
    if known and k not in ALWAYS_CONFIRM and k not in OPTIONAL_ALWAYS_ASK:
        return True
    if k == "remote_international" and p.get("remote_international") is not None:
        return True
    return k in ("name", "email") and bool(p.get(k))


def progress(state):
    """Where the person is: Question X of 10, and each section done / current / pending."""
    state = state or {}
    p, asked, pending = state.get("profile") or {}, state.get("asked") or [], state.get("pending")
    steps = []
    for q in QUESTIONS:
        k = q["key"]
        if k == pending:
            st = "current"
        elif k in asked or (state.get("profile") is not None and _will_skip(state, k)):
            st = "done"
        else:
            st = "pending"
        steps.append({"key": k, "label": LABELS[k], "status": st, "value": show(p, k)})
    done = sum(s["status"] == "done" for s in steps)
    cur = next((i + 1 for i, s in enumerate(steps) if s["status"] == "current"), None)
    return {"steps": steps, "total": len(steps), "done": done, "current": cur,
            "percent": round(100 * done / len(steps))}


def _parse_items(key, text):
    """Turn typed text into list items for one section."""
    a = (text or "").strip()
    if not a or SKIP.match(a):
        return []
    if key == "locations":
        found = _locations_in(a)
        rest = [x.title() for x in _clean_items(a) if not _locations_in(x)]
        return list(dict.fromkeys(found + rest))
    if key == "roles":
        parts = [re.sub(r"\s+", " ", x).strip(" .-").lower() for x in re.split(r"[,;\n]| and ", a) if x.strip(" .-")]
        return list(dict.fromkeys(parts))
    if key == "skills":
        found = _find_terms(a, SKILLS)
        rest = [x.lower() for x in _split_list(a) if not _find_terms(x, SKILLS)]
        return list(dict.fromkeys(found + rest))
    return [x for x in _split_list(a)]


def set_field(state, key, text="", mode="overwrite", items=None):
    """Change one section directly (section editor). mode: overwrite | add | edit.
    'edit' takes the kept/edited list in `items` (plus anything typed in `text`).
    Nothing else in the profile is touched; the open question (if any) stays open."""
    if key not in KIND:
        return {"state": state, "error": "Unknown section.", "changes": []}
    state = json.loads(json.dumps(state or {}))
    state.setdefault("profile", {}); state.setdefault("asked", []); state.setdefault("pending", None)
    p = state["profile"]
    before = json.loads(json.dumps(p))
    kind, a = KIND[key], (text or "").strip()
    err = warn = None
    if kind == "list":
        new = _parse_items(key, a)
        if mode == "edit":
            kept = [str(x).strip() for x in (items or []) if str(x).strip()]
            p[key] = list(dict.fromkeys(kept + new))
        elif mode == "add":
            if not new:
                err = "Type what to add."
            p[key] = _merge_list(p.get(key), new, "add")
        else:
            if not new and not SKIP.match(a or "x") and key not in ("exclude",):
                err = "Type at least one value, or choose Cancel."
            p[key] = new
        if key == "roles":
            odd = [x for x in p[key] if not _looks_like_role(x) and x not in (before.get("roles") or [])]
            if odd:
                warn = "'" + "', '".join(odd) + "' doesn't look like a job title. Confirm only if that's what you want."
    elif kind == "bool":
        if YES.match(a) or a.lower() in ("include", "true"):
            p[key] = True
        elif NO.match(a) or a.lower() in ("exclude", "false"):
            p[key] = False
        else:
            err = "Choose Yes or No."
    elif kind == "choice":
        m = re.search(r"\b(remote|hybrid|on-?site|office|any)\b", a, re.I)
        if m:
            p[key] = {"on-site": "onsite", "office": "onsite"}.get(m.group(1).lower(), m.group(1).lower())
        else:
            err = "Please pick Remote, Hybrid, Onsite or Any."
    elif kind == "email":
        if not a or SKIP.match(a):
            p.pop(key, None)
        else:
            m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", a)
            if m:
                p[key] = m.group(0)
            else:
                err = "That doesn't look like an email address."
    elif key == "experience":
        lo, hi = parse_candidate_experience(a)
        if lo is None and not re.search(r"\d", a):
            err = "Type your experience in years, for example '4 years' or '3-5 years'."
        else:
            p[key] = a if re.search(r"year|yr", a, re.I) else a + " years"
    elif key == "min_salary":
        if not a or SKIP.match(a):
            p.pop(key, None)
        else:
            n = re.fullmatch(r"\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*", a, re.I)
            p[key] = (f"{float(n.group(1)):g} LPA" if float(n.group(1)) <= 200 else f"₹{int(float(n.group(1))):,} per year") if n else a
    else:
        if not a:
            err = "Type a value, or choose Cancel."
        else:
            p[key] = a
    if err:
        state["profile"] = before
        return {"state": state, "error": err, "changes": [], "key": key}
    if key not in state["asked"]:
        state["asked"].append(key)
    r = {"state": state, "changes": changes(before, p), "key": key, "error": None, "warning": warn}
    if not state.get("pending"):
        nxt = advance(state)
        r.update({"done": nxt["done"], "question": nxt.get("question"), "options": nxt.get("options", []),
                  "profile": nxt.get("profile")})
    else:
        r["done"] = False
    r["progress"] = progress(state)
    return r


def section_info():
    """Questions, labels, kinds and quick options, for the section editor."""
    return [{"key": q["key"], "label": LABELS[q["key"]], "kind": q["kind"], "ask": q["ask"],
             "options": [o for o in q["options"] if o != "Skip"]} for q in QUESTIONS]


BRIEF_FIELDS = {
    "job titles": "roles", "job title": "roles", "roles": "roles", "role": "roles",
    "experience": "experience", "years of experience": "experience",
    "locations": "locations", "location": "locations", "preferred locations": "locations", "cities": "locations",
    "remote jobs abroad": "remote_international", "remote international": "remote_international",
    "international remote": "remote_international",
    "work arrangement": "work_arrangement", "work mode": "work_arrangement",
    "must-have skills": "skills", "must have skills": "skills", "skills": "skills", "key skills": "skills",
    "minimum salary": "min_salary", "expected salary": "min_salary", "min salary": "min_salary",
    "avoid": "exclude", "exclude": "exclude", "industries": "industries", "preferred industries": "industries",
    "report email": "email", "email": "email", "search name": "name", "name": "name",
}


def parse_brief(text):
    """Read the filled-in 'job search brief' sample (lines like 'Locations: Bengaluru, Pune').
    Returns a profile dict, or None if the text isn't in that format."""
    out, hits = {}, 0
    for line in (text or "").splitlines():
        m = re.match(r"^\s*[-*•]?\s*([A-Za-z][A-Za-z \-]{1,30}?)\s*[:=]\s*(.+?)\s*$", line)
        if not m:
            continue
        key = BRIEF_FIELDS.get(m.group(1).strip().lower())
        val = m.group(2).strip()
        if not key or not val or val.startswith("<") or SKIP.match(val):
            continue
        hits += 1
        if key == "industries":
            out[key] = [x.lower() for x in _split_list(val)]
            continue
        r = set_field({"profile": {}, "asked": [], "pending": "x"}, key, val, "overwrite")
        if not r.get("error") and key in r["state"]["profile"]:
            out[key] = r["state"]["profile"][key]
    return out if hits >= 3 else None


def cli():
    """Interactive intake in the terminal."""
    print("\nDescribe the job you want (role, skills, industry, anything you care about):")
    desc = input("> ").strip()
    while len(desc) < 5:
        desc = input("Please describe the job in a few words:\n> ").strip()
    from .config import load_settings
    r = start(desc, load_settings())
    while not r["done"]:
        print("\n" + r["question"])
        if r["options"]:
            print("  options: " + " | ".join(r["options"]))
        r = answer(r["state"], input("> "))
    return r["profile"]
