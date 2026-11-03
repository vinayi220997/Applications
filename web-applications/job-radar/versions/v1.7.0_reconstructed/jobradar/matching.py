"""Hard eligibility filters, weighted 0–100 score, and evidence-based reasons/gaps."""
import re

from .normalize import experience_range, location_facts, norm_title, work_modes

SYNONYMS = {
    "software engineer": ["software developer", "sde", "developer", "programmer", "software development engineer", "member of technical staff", "mts"],
    "backend engineer": ["backend developer", "back end", "back-end", "server side", "api engineer"],
    "frontend engineer": ["frontend developer", "front end", "front-end", "ui engineer", "web developer"],
    "full stack developer": ["full stack", "fullstack", "full-stack"],
    "machine learning engineer": ["ml engineer", "ai engineer", "applied scientist", "ai/ml", "deep learning engineer"],
    "ml engineer": ["machine learning engineer", "ai engineer", "ai/ml"],
    "ai engineer": ["machine learning engineer", "ml engineer", "llm engineer", "genai engineer", "generative ai"],
    "data scientist": ["applied scientist", "machine learning scientist", "research scientist"],
    "data engineer": ["analytics engineer", "big data engineer", "etl developer", "data platform engineer"],
    "data analyst": ["business analyst", "analytics", "bi analyst", "insights analyst", "reporting analyst"],
    "devops engineer": ["site reliability", "sre", "platform engineer", "cloud engineer", "infrastructure engineer"],
    "qa engineer": ["sdet", "test engineer", "quality engineer", "automation engineer", "qa automation"],
    "product manager": ["product owner", "pm", "product lead"],
    "mobile developer": ["android developer", "ios developer", "flutter developer", "react native"],
    "ui/ux designer": ["product designer", "ux designer", "ui designer", "interaction designer"],
}
SKILL_ALIASES = {
    "javascript": ["js", "ecmascript"], "typescript": ["ts"], "node.js": ["node", "nodejs"], "golang": ["go"],
    "go": ["golang"], "kubernetes": ["k8s"], "postgresql": ["postgres"], "gcp": ["google cloud"],
    "aws": ["amazon web services"], "azure": ["microsoft azure"], "machine learning": ["ml"],
    "react": ["react.js", "reactjs"], "next.js": ["nextjs"], "ci/cd": ["cicd", "continuous integration"],
    "llm": ["large language model", "llms", "gpt"], "rag": ["retrieval-augmented", "retrieval augmented"],
    "scikit-learn": ["sklearn"], "c#": ["csharp", ".net"], "power bi": ["powerbi"],
}
STOP = {"senior", "junior", "lead", "staff", "principal", "ii", "iii", "i", "iv", "engineer", "developer", "the", "of",
        "and", "for", "with", "sr", "jr", "associate", "intern", "remote", "india", "hybrid", "manager", "specialist"}
_ENG = {"engineer", "developer", "sde", "programmer", "swe"}
HEAD_FAMILIES = {"engineer": _ENG, "developer": _ENG, "designer": {"designer", "design"}, "analyst": {"analyst", "analytics"},
                 "scientist": {"scientist", "science"}, "manager": {"manager", "lead", "head"}, "architect": {"architect"},
                 "writer": {"writer"}, "recruiter": {"recruiter", "talent"}, "accountant": {"accountant", "accounts"},
                 "consultant": {"consultant"}, "tester": {"tester", "qa", "test"}, "administrator": {"administrator", "admin"}}
SENIOR_TITLES = re.compile(r"\b(principal|staff|director|head of|vp|vice president|chief|distinguished|architect)\b", re.I)
JUNIOR_TITLES = re.compile(r"\b(intern|internship|trainee|fresher|graduate|apprentice)\b", re.I)


def _has(text, term):
    terms = [term] + SKILL_ALIASES.get(term, [])
    for t in terms:
        if re.search(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])", text):
            return True
    return False


def title_relevance(title, roles):
    """0–100: how well the job title matches the wanted roles (with synonyms)."""
    t = " " + norm_title(title) + " "
    best = 0
    for role in roles or []:
        r = norm_title(role)
        variants = [r] + [norm_title(s) for s in SYNONYMS.get(r, [])]
        for key, syns in SYNONYMS.items():          # reverse lookup: 'backend developer' -> 'backend engineer' family
            if r in [norm_title(x) for x in syns]:
                variants += [norm_title(key)] + [norm_title(x) for x in syns]
        for v in variants:
            if v and f" {v} " in t:
                best = max(best, 100 if v == r else 85)
        # A partial match must keep the kind of job: a 'UI designer' search shouldn't match 'UI engineer'.
        head = next((w for w in reversed(r.split()) if w in HEAD_FAMILIES), None)
        if head and not any(f" {x} " in t for x in HEAD_FAMILIES[head]):
            continue
        core = [w for w in r.split() if w not in STOP]
        if core:
            hits = sum(1 for w in core if f" {w} " in t)
            if hits:
                best = max(best, int(70 * hits / len(core)))
        # generic "engineer/developer" family match
        if re.search(r"\b(engineer|developer)\b", r) and re.search(r"\b(engineer|developer|sde)\b", t):
            best = max(best, 35)
    return best


def score_job(job, p, weights):
    """Return dict(eligible, score, reasons, gaps, components, hard_fail)."""
    title = job.get("title") or ""
    desc = (job.get("description") or "")
    blob = (title + "\n" + desc).lower()
    reasons, gaps = [], []
    hard = None

    # ---- relevance gate
    R_title = title_relevance(title, p.get("roles"))
    if R_title < 35:
        return {"eligible": False, "score": 0, "reasons": [], "gaps": [], "components": {}, "hard_fail": "title not relevant"}

    # ---- exclusions
    for ex in p.get("exclude") or []:
        if ex and re.search(r"\b" + re.escape(ex.lower()) + r"\b", (title + " " + (job.get("company") or "")).lower()):
            return {"eligible": False, "score": 0, "reasons": [], "gaps": [], "components": {}, "hard_fail": f"excluded: {ex}"}

    # ---- employment type
    want_type = (p.get("employment_type") or "full-time").lower()
    if want_type != "internship" and JUNIOR_TITLES.search(title):
        hard = "internship/trainee role"
    if want_type == "internship" and not JUNIOR_TITLES.search(title):
        hard = "not an internship"

    # ---- seniority
    exp_min, exp_max = p.get("exp_min"), p.get("exp_max")
    if exp_max is not None and exp_max < 8 and SENIOR_TITLES.search(title) and not re.search(r"solutions? architect", " ".join(p.get("roles") or []), re.I):
        hard = hard or "seniority above your experience"

    # ---- location eligibility
    lf = location_facts(job.get("location"), desc, job.get("remote_flag"), job.get("workplace_type"))
    want_cities = {c.lower() for c in (p.get("locations") or [])}
    any_india = not want_cities or any(c in ("india", "anywhere in india") for c in want_cities)
    if "delhi ncr" in want_cities:
        want_cities |= {"delhi", "gurugram", "noida"}
    modes = set(work_modes(p.get("work_modes") if p.get("work_modes") is not None else p.get("work_arrangement")))
    L = 0
    if lf["remote"] and not lf["hybrid"]:
        if lf["remote_scope"] in ("india", "apac", "global"):
            L = 100
            reasons.append(f"Remote role open to candidates in {'India' if lf['remote_scope'] == 'india' else lf['remote_scope'].upper() if lf['remote_scope'] == 'apac' else 'any country'}")
        elif lf["remote_scope"] == "restricted":
            hard = hard or "remote, but restricted to another country/region"
        else:
            L = 60
            gaps.append("Remote, but the listing doesn't say which countries can apply")
        if not p.get("remote_international") and not lf["in_india"] and lf["remote_scope"] != "india":
            hard = hard or "international remote role (you chose India-only)"
        if modes and "remote" not in modes and not hard:
            L = min(L, 40)
            gaps.append("Role is remote; you chose " + " or ".join(sorted(modes)))
    elif lf["in_india"]:
        cities = set(lf["cities"])
        if any_india or (cities & want_cities) or (not cities and "india" in (job.get("location") or "").lower()):
            L = 100 if (cities & want_cities) or any_india else 75
            reasons.append(f"Located in {', '.join(c.title() for c in cities) or 'India'}" + (" (hybrid)" if lf["hybrid"] else ""))
        else:
            hard = hard or f"located in {', '.join(c.title() for c in cities)}, outside your cities"
        if modes == {"remote"} and not hard:
            L = min(L, 50)
            gaps.append("Not a fully remote role")
        elif modes and lf["arrangement"] in ("hybrid", "onsite") and lf["arrangement"] not in modes and not hard:
            L = min(L, 70)
            gaps.append(f"Role is {lf['arrangement']}; you chose " + " or ".join(sorted(modes)))
    else:
        hard = hard or "location outside India and not remote"

    # ---- skills
    skills = p.get("skills") or []
    found = [s for s in skills if _has(blob, s.lower())]
    missing = [s for s in skills if s not in found]
    # Matching 3–4 of the listed skills is a strong match; long skill lists shouldn't sink every job.
    K = round(100 * min(1.0, len(found) / max(1, min(len(skills), 4)))) if skills else 60
    if skills and not found and R_title >= 85:
        K = 35
    if found:
        reasons.append("Skills mentioned in the job: " + ", ".join(found))
    if missing:
        gaps.append("Not mentioned in the job: " + ", ".join(missing))
    # job's own key skills that the candidate didn't list
    from .intake import SKILLS as VOCAB
    job_sk = [s for s in VOCAB if _has(blob, s) and s not in [x.lower() for x in skills]][:6]
    if job_sk and skills:
        gaps.append("Job also asks for (not established in your profile): " + ", ".join(job_sk))

    # ---- experience
    rmin, rmax = experience_range(desc)
    E = 65
    exp_text = None
    if rmin is not None:
        exp_text = f"{rmin}{'–' + str(rmax) if rmax else '+'} years"
        if exp_min is None:
            E = 65
        elif exp_max is not None and rmin > exp_max + 2:
            hard = hard or f"requires {exp_text}"
        elif exp_max is not None and rmin > exp_max:
            E = 50
            gaps.append(f"Asks for {exp_text}; slightly above your {p.get('experience')}")
        elif rmax is not None and exp_min is not None and exp_min > rmax + 3:
            E = 55
            gaps.append(f"Asks for {exp_text}; you may be over-qualified")
        else:
            E = 100
            reasons.append(f"Experience fits: asks for {exp_text}, you have {p.get('experience')}")
    else:
        gaps.append("Required experience not stated")

    # ---- responsibilities (title + role words in description)
    role_words = {w for r in p.get("roles") or [] for w in norm_title(r).split() if w not in STOP}
    desc_hits = sum(1 for w in role_words if re.search(r"\b" + re.escape(w) + r"\b", desc.lower()))
    Rr = min(100, int(0.75 * R_title + (25 * desc_hits / max(1, len(role_words)))))
    if R_title >= 85:
        reasons.insert(0, f"Title matches your target role ({title})")

    # ---- preferences (industry, arrangement)
    P = 60
    inds = [i for i in (p.get("industries") or []) if _has(blob, i.lower())]
    if inds:
        P = 100
        reasons.append("Industry: " + ", ".join(inds))
    if modes and lf["arrangement"] in modes:
        P = min(100, P + 20)

    # ---- compensation
    C = 50
    floor = p.get("min_salary_lpa")
    smax = job.get("salary_max_lpa") or job.get("salary_min_lpa")
    if floor and smax:
        if smax < floor:
            hard = hard or f"salary up to {smax} LPA, below your {floor} LPA minimum"
        else:
            C = 100
            reasons.append(f"Pay meets your minimum ({job.get('salary_text') or str(smax) + ' LPA'})")
    elif floor:
        gaps.append("Salary not stated; can't confirm your minimum")

    w = weights
    score = (w["skills"] * K + w["experience"] * E + w["responsibilities"] * Rr +
             w["location"] * L + w["preferences"] * P + w["compensation"] * C)
    return {"eligible": hard is None, "score": round(score, 1), "reasons": reasons[:6], "gaps": gaps[:5],
            "components": {"skills": K, "experience": E, "responsibilities": Rr, "location": L,
                           "preferences": P, "compensation": C},
            "hard_fail": hard, "experience_text": exp_text, "arrangement": lf["arrangement"]}
