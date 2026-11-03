"""Job boards with public APIs or feeds (remote boards, optional Adzuna for India).

Jobs from these sources are third-party listings: they are 'appears active' until the
application link is checked, and the employer's own page is preferred when known.
"""
import re
import urllib.parse
import xml.etree.ElementTree as ET

from ..http import get_json, fetch
from ..normalize import html_to_text, parse_date, iso, salary_from_source

DESC_LIMIT = 6000


def _job(**kw):
    base = {"requisition_id": None, "workplace_type": None, "remote_flag": None, "employment_type": None,
            "salary_text": None, "salary_min_lpa": None, "salary_max_lpa": None, "published_at": None,
            "updated_at": None, "careers_url": None, "is_ats": False, "board": None}
    base.update(kw)
    return base


def remotive(queries, timeout=20):
    """Remotive asks API users to link back and keep requests low; we make one call per query (max 3)."""
    out = []
    for q in queries[:3]:
        data = get_json(f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(q)}&limit=100", timeout=timeout)
        for j in data.get("jobs", []):
            out.append(_job(
                source="remotive", source_job_id=str(j.get("id")), company=j.get("company_name", ""),
                title=j.get("title", "").strip(), location=f"Remote ({j.get('candidate_required_location') or 'unspecified'})",
                remote_flag=True, employment_type=j.get("job_type"), salary_text=j.get("salary") or None,
                description=html_to_text(j.get("description"), DESC_LIMIT),
                published_at=iso(parse_date(j.get("publication_date"))),
                apply_url=j.get("url"), source_url=j.get("url"), source_name="Remotive"))
    return out


def remoteok(queries, timeout=20):
    """Remote OK's API terms require a visible link back to Remote OK, which every report includes."""
    data = get_json("https://remoteok.com/api", timeout=timeout)
    out = []
    for j in data[1:] if isinstance(data, list) else []:
        lo, hi = salary_from_source(j.get("salary_min") or None, j.get("salary_max") or None, "USD")
        out.append(_job(
            source="remoteok", source_job_id=str(j.get("id")), company=j.get("company", ""),
            title=(j.get("position") or "").strip(), location=f"Remote ({j.get('location') or 'unspecified'})",
            remote_flag=True, description=html_to_text(j.get("description"), DESC_LIMIT),
            salary_text=(f"USD {j.get('salary_min')}–{j.get('salary_max')}" if j.get("salary_min") else None),
            salary_min_lpa=lo, salary_max_lpa=hi,
            published_at=iso(parse_date(j.get("date") or j.get("epoch"))),
            apply_url=j.get("apply_url") or j.get("url"), source_url=j.get("url"), source_name="Remote OK"))
    return out


def jobicy(queries, timeout=20):
    out = []
    for q in queries[:3]:
        tag = urllib.parse.quote(q.split()[0].lower())
        data = get_json(f"https://jobicy.com/api/v2/remote-jobs?count=50&tag={tag}", timeout=timeout)
        for j in data.get("jobs", []):
            lo, hi = salary_from_source(j.get("annualSalaryMin"), j.get("annualSalaryMax"), j.get("salaryCurrency"))
            out.append(_job(
                source="jobicy", source_job_id=str(j.get("id")), company=j.get("companyName", ""),
                title=html_to_text(j.get("jobTitle")), location=f"Remote ({j.get('jobGeo') or 'unspecified'})",
                remote_flag=True, employment_type=", ".join(j.get("jobType") or []) if isinstance(j.get("jobType"), list) else j.get("jobType"),
                description=html_to_text(j.get("jobDescription") or j.get("jobExcerpt"), DESC_LIMIT),
                salary_min_lpa=lo, salary_max_lpa=hi,
                published_at=iso(parse_date(j.get("pubDate"))),
                apply_url=j.get("url"), source_url=j.get("url"), source_name="Jobicy"))
    return out


WWR_FEEDS = ["https://weworkremotely.com/categories/remote-programming-jobs.rss",
             "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
             "https://weworkremotely.com/categories/remote-design-jobs.rss",
             "https://weworkremotely.com/categories/remote-product-jobs.rss",
             "https://weworkremotely.com/categories/remote-data-science-jobs.rss"]


def weworkremotely(queries, timeout=20):
    out = []
    for feed in WWR_FEEDS:
        _, _, body = fetch(feed, timeout=timeout)
        root = ET.fromstring(body.encode("utf-8"))
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            company, _, role = title.partition(":")
            link = it.findtext("link") or ""
            region = it.findtext("region") or "unspecified"
            out.append(_job(
                source="weworkremotely", source_job_id=link.rsplit("/", 1)[-1], company=company.strip(),
                title=(role or title).strip(), location=f"Remote ({region})", remote_flag=True,
                employment_type=it.findtext("type"),
                description=html_to_text(it.findtext("description"), DESC_LIMIT),
                published_at=iso(parse_date(it.findtext("pubDate"))),
                apply_url=link, source_url=link, source_name="We Work Remotely"))
    return out


def arbeitnow(queries, timeout=20):
    data = get_json("https://www.arbeitnow.com/api/job-board-api", timeout=timeout)
    out = []
    for j in data.get("data", []):
        out.append(_job(
            source="arbeitnow", source_job_id=j.get("slug"), company=j.get("company_name", ""),
            title=(j.get("title") or "").strip(), location=("Remote" if j.get("remote") else "") + f" ({j.get('location') or ''})",
            remote_flag=j.get("remote"), employment_type=", ".join(j.get("job_types") or []),
            description=html_to_text(j.get("description"), DESC_LIMIT),
            published_at=iso(parse_date(j.get("created_at"))),
            apply_url=j.get("url"), source_url=j.get("url"), source_name="Arbeitnow"))
    return out


def adzuna(queries, locations, cfg, timeout=20):
    """Authorised aggregator API (free key at developer.adzuna.com). Covers Indian job boards."""
    out = []
    country = cfg.get("country") or "in"
    where_list = (locations or [""])[:3]
    for q in queries[:3]:
        for where in where_list:
            params = {"app_id": cfg["app_id"], "app_key": cfg["app_key"], "what": q, "results_per_page": 50,
                      "max_days_old": 7, "sort_by": "date", "content-type": "application/json"}
            if where and where.lower() not in ("india", "anywhere in india"):
                params["where"] = where
            data = get_json(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?" + urllib.parse.urlencode(params), timeout=timeout)
            for j in data.get("results", []):
                lo, hi = salary_from_source(j.get("salary_min"), j.get("salary_max"), "INR" if country == "in" else None)
                out.append(_job(
                    source="adzuna", source_job_id=str(j.get("id")), company=(j.get("company") or {}).get("display_name", ""),
                    title=html_to_text(j.get("title")), location=(j.get("location") or {}).get("display_name", ""),
                    employment_type=j.get("contract_time"), description=html_to_text(j.get("description"), DESC_LIMIT),
                    salary_min_lpa=lo if j.get("salary_is_predicted") in ("0", 0) else None,
                    salary_max_lpa=hi if j.get("salary_is_predicted") in ("0", 0) else None,
                    published_at=iso(parse_date(j.get("created"))),
                    apply_url=j.get("redirect_url"), source_url=j.get("redirect_url"), source_name="Adzuna"))
    return out


BOARDS = {"remotive": remotive, "remoteok": remoteok, "jobicy": jobicy, "weworkremotely": weworkremotely,
          "arbeitnow": arbeitnow}


def manual_search_links(profile):
    """Portals without an open API. We never scrape them; we give the user pre-filled searches instead."""
    role = (profile.get("roles") or ["software engineer"])[0]
    q = urllib.parse.quote_plus(role)
    loc = next((l for l in profile.get("locations") or [] if l.lower() not in ("india", "anywhere in india")), "India")
    lq = urllib.parse.quote_plus(loc)
    slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    lslug = re.sub(r"[^a-z0-9]+", "-", loc.lower()).strip("-")
    return [
        ("LinkedIn Jobs (past 24 h)", f"https://www.linkedin.com/jobs/search/?keywords={q}&location={lq}&f_TPR=r86400"),
        ("Naukri (past day)", f"https://www.naukri.com/{slug}-jobs-in-{lslug}?jobAge=1"),
        ("Indeed India (past day)", f"https://in.indeed.com/jobs?q={q}&l={lq}&fromage=1"),
        ("Foundit", f"https://www.foundit.in/srp/results?query={q}&locations={lq}"),
        ("Glassdoor", f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={q}&fromAge=1"),
        ("Wellfound (startups)", f"https://wellfound.com/role/{slug}"),
        ("Dice (tech)", f"https://www.dice.com/jobs?q={q}&filters.postedDate=ONE"),
    ]
