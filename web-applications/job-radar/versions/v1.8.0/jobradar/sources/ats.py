"""Applicant-tracking-system connectors. Each board = one employer's official, public job feed.

A job present in the employer's live ATS feed is treated as verified active.
"""
import re
import urllib.parse

from ..http import get_json, FetchError
from ..normalize import html_to_text, parse_date, iso, salary_from_source

DESC_LIMIT = 6000


def pretty(token):
    return re.sub(r"[-_]+", " ", token).title()


def _job(**kw):
    base = {"requisition_id": None, "workplace_type": None, "remote_flag": None, "employment_type": None,
            "salary_text": None, "salary_min_lpa": None, "salary_max_lpa": None, "published_at": None,
            "updated_at": None, "careers_url": None, "is_ats": True}
    base.update(kw)
    return base


# ---------------- Greenhouse ----------------
def greenhouse(token, timeout=20):
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(token)}/jobs?content=true", timeout=timeout, retries=1)
    company = token
    try:
        meta = get_json(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(token)}", timeout=timeout, retries=0)
        company = meta.get("name") or token
    except FetchError:
        pass
    out = []
    for j in data.get("jobs", []):
        url = j.get("absolute_url")
        # first_published is the publication date when Greenhouse supplies it; updated_at is NOT a publish date.
        pub = parse_date(j.get("first_published"))
        out.append(_job(
            source="greenhouse", source_job_id=str(j.get("id")), requisition_id=j.get("requisition_id"),
            company=company, title=j.get("title", "").strip(),
            location=(j.get("location") or {}).get("name", ""),
            description=html_to_text(j.get("content"), DESC_LIMIT),
            published_at=iso(pub), updated_at=iso(parse_date(j.get("updated_at"))),
            apply_url=url, careers_url=f"https://job-boards.greenhouse.io/{token}", source_url=url,
            source_name="Greenhouse", board=f"greenhouse:{token}"))
    return company, out


# ---------------- Lever ----------------
def lever(token, timeout=20):
    data = get_json(f"https://api.lever.co/v0/postings/{urllib.parse.quote(token)}?mode=json", timeout=timeout, retries=1)
    out = []
    for j in data if isinstance(data, list) else []:
        cats = j.get("categories") or {}
        desc = (j.get("descriptionPlain") or "") + "\n\n"
        for l in j.get("lists") or []:
            desc += f"{l.get('text', '')}\n{html_to_text(l.get('content'))}\n\n"
        desc += j.get("additionalPlain") or ""
        sal = j.get("salaryRange") or {}
        lo, hi = salary_from_source(sal.get("min"), sal.get("max"), sal.get("currency"), sal.get("interval", "").replace("per-", ""))
        loc = cats.get("location") or ", ".join(cats.get("allLocations") or [])
        out.append(_job(
            source="lever", source_job_id=j.get("id"), company=pretty(token), title=(j.get("text") or "").strip(),
            location=loc, workplace_type=j.get("workplaceType"), employment_type=cats.get("commitment"),
            description=desc.strip()[:DESC_LIMIT],
            salary_text=(f"₹{lo:g}–{hi:g} LPA" if lo and hi and sal.get("currency") == "INR" else
                         (f"{sal.get('currency')} {sal.get('min'):,}–{sal.get('max'):,} {sal.get('interval', '').replace('per-', '').replace('-salary', '')}"
                          if sal.get("min") and sal.get("max") else None)),
            salary_min_lpa=lo, salary_max_lpa=hi,
            published_at=iso(parse_date(j.get("createdAt"))),
            apply_url=j.get("applyUrl") or j.get("hostedUrl"), careers_url=f"https://jobs.lever.co/{token}",
            source_url=j.get("hostedUrl"), source_name="Lever", board=f"lever:{token}"))
    return pretty(token), out


# ---------------- Ashby ----------------
def ashby(token, timeout=20):
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(token)}?includeCompensation=true", timeout=timeout, retries=1)
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location", "") for s in (j.get("secondaryLocations") or []) if isinstance(s, dict)]
        comp = j.get("compensation") or {}
        out.append(_job(
            source="ashby", source_job_id=j.get("id"), company=pretty(token), title=(j.get("title") or "").strip(),
            location=" / ".join([l for l in locs if l]), workplace_type=j.get("workplaceType"),
            remote_flag=j.get("isRemote"), employment_type=j.get("employmentType"),
            description=(j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")))[:DESC_LIMIT],
            salary_text=comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary"),
            published_at=iso(parse_date(j.get("publishedAt"))),
            apply_url=j.get("applyUrl") or j.get("jobUrl"), careers_url=f"https://jobs.ashbyhq.com/{token}",
            source_url=j.get("jobUrl"), source_name="Ashby", board=f"ashby:{token}"))
    return pretty(token), out


# ---------------- SmartRecruiters ----------------
def smartrecruiters(token, timeout=20):
    out, offset, company = [], 0, token
    while offset < 1000:
        data = get_json(f"https://api.smartrecruiters.com/v1/companies/{urllib.parse.quote(token)}/postings?limit=100&offset={offset}", timeout=timeout, retries=1)
        items = data.get("content", [])
        for j in items:
            loc = j.get("location") or {}
            company = (j.get("company") or {}).get("name") or company
            url = f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}"
            out.append(_job(
                source="smartrecruiters", source_job_id=str(j.get("id")), requisition_id=j.get("refNumber"),
                company=company, title=(j.get("name") or "").strip(),
                location=", ".join([x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x]),
                remote_flag=loc.get("remote"), workplace_type="hybrid" if loc.get("hybrid") else None,
                employment_type=(j.get("typeOfEmployment") or {}).get("label"),
                description=(j.get("experienceLevel") or {}).get("label", ""),   # full text fetched later for shortlisted jobs
                published_at=iso(parse_date(j.get("releasedDate"))),
                apply_url=url, careers_url=f"https://careers.smartrecruiters.com/{token}", source_url=url,
                source_name="SmartRecruiters", board=f"smartrecruiters:{token}",
                detail_url=f"https://api.smartrecruiters.com/v1/companies/{token}/postings/{j.get('id')}"))
        if len(items) < 100:
            break
        offset += 100
    return company, out


def smartrecruiters_detail(job, timeout=20):
    d = get_json(job["detail_url"], timeout=timeout)
    secs = ((d.get("jobAd") or {}).get("sections") or {})
    text = "\n\n".join(html_to_text((secs.get(k) or {}).get("text")) for k in ("jobDescription", "qualifications", "additionalInformation"))
    return text[:DESC_LIMIT], d.get("applyUrl")


# ---------------- Workable ----------------
def workable(token, timeout=20):
    data = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{urllib.parse.quote(token)}?details=true", timeout=timeout, retries=1)
    company = data.get("name") or token
    out = []
    for j in data.get("jobs", []):
        loc = ", ".join([x for x in (j.get("city"), j.get("state"), j.get("country")) if x])
        url = j.get("url") or j.get("shortlink")
        out.append(_job(
            source="workable", source_job_id=j.get("shortcode") or j.get("code"), company=company,
            title=(j.get("title") or "").strip(), location=loc, remote_flag=j.get("telecommuting"),
            employment_type=j.get("employment_type"),
            description=html_to_text(j.get("description"), DESC_LIMIT),
            published_at=iso(parse_date(j.get("published_on"))),
            apply_url=j.get("application_url") or url, careers_url=f"https://apply.workable.com/{token}/",
            source_url=url, source_name="Workable", board=f"workable:{token}"))
    return company, out


# ---------------- Recruitee ----------------
def recruitee(token, timeout=20):
    data = get_json(f"https://{urllib.parse.quote(token)}.recruitee.com/api/offers/", timeout=timeout, retries=1)
    out = []
    for j in data.get("offers", []):
        if j.get("status") and j.get("status") != "published":
            continue
        out.append(_job(
            source="recruitee", source_job_id=str(j.get("id")), company=j.get("company_name") or token,
            title=(j.get("title") or "").strip(), location=j.get("location") or "",
            remote_flag=j.get("remote"), employment_type=j.get("employment_type_code"),
            description=html_to_text((j.get("description") or "") + (j.get("requirements") or ""), DESC_LIMIT),
            published_at=iso(parse_date(j.get("published_at"))),
            apply_url=j.get("careers_apply_url") or j.get("careers_url"),
            careers_url=f"https://{token}.recruitee.com/", source_url=j.get("careers_url"),
            source_name="Recruitee", board=f"recruitee:{token}"))
    return out[0]["company"] if out else token, out


CONNECTORS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby,
              "smartrecruiters": smartrecruiters, "workable": workable, "recruitee": recruitee}

URL_PATTERNS = [
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)"),
    ("lever", r"jobs\.lever\.co/([A-Za-z0-9_.-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)"),
    ("workable", r"apply\.workable\.com/([A-Za-z0-9_-]+)"),
    ("recruitee", r"([A-Za-z0-9_-]+)\.recruitee\.com"),
]


def detect_board(url):
    """Turn a careers-page URL into (ats, token), or None if it is not a supported ATS URL."""
    for ats, pat in URL_PATTERNS:
        m = re.search(pat, url or "", re.I)
        if m:
            return ats, urllib.parse.unquote(m.group(1))
    return None
