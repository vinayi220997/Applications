"""Guided intake: turn a free-text job description into a precise search profile by asking
only the questions whose answers are missing (location, experience, arrangement, skills, pay ...).

Used by both the command line (`python -m jobradar ask`) and the local web app.
"""
import json
import re
import urllib.request

from .normalize import INDIA_CITIES, canonical_city, parse_candidate_experience, parse_lpa

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
    if not cfg.get("api_key"):
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
    else:
        p[key] = a


def answer(state, text):
    state.pop("error", None)
    if state.get("pending"):
        _apply(state, state["pending"], text)
        state["pending"] = None
    return advance(state)


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
