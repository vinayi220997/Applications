"""Duplicate detection across sources. Never merges two employer requisitions just because titles match."""
import re

from .normalize import norm_company, norm_title, india_cities_in


def _loc_key(loc):
    cities = india_cities_in(loc)
    if cities:
        return ",".join(sorted(cities))
    return "remote" if re.search(r"remote", loc or "", re.I) else re.sub(r"[^a-z]+", "", (loc or "").lower())[:20]


def _canon_url(u):
    if not u:
        return None
    u = re.sub(r"[?#].*$", "", u.strip().lower())
    return re.sub(r"/(apply|application)/?$", "", u).rstrip("/")


def cluster(jobs):
    """jobs: list of dicts. Returns list of representative jobs, each with 'also_seen_on' [(source_name, url)]."""
    by_url, groups = {}, {}
    order = []
    for j in jobs:
        cu = _canon_url(j.get("apply_url"))
        if cu and cu in by_url:
            groups[by_url[cu]].append(j)
            continue
        key = (norm_company(j.get("company")), norm_title(j.get("title")), _loc_key(j.get("location")))
        gid = None
        for g in groups.get(("k",) + key, []):
            gid = g
            break
        if gid is not None:
            rep = groups[gid][0]
            # distinct requisitions at the same employer stay separate
            if j.get("is_ats") and rep.get("is_ats") and j.get("source_job_id") != rep.get("source_job_id") and j.get("source") == rep.get("source"):
                gid = None
        if gid is None:
            gid = len(order)
            order.append(gid)
            groups[gid] = [j]
            groups.setdefault(("k",) + key, []).append(gid)
        else:
            groups[gid].append(j)
        if cu:
            by_url[cu] = gid
    out = []
    for gid in order:
        members = groups[gid]
        members.sort(key=lambda m: (not m.get("is_ats"), m.get("published_at") is None))
        rep = dict(members[0])
        rep["also_seen_on"] = [(m.get("source_name"), m.get("source_url") or m.get("apply_url")) for m in members[1:]]
        if not rep.get("published_at"):
            dates = [m.get("published_at") for m in members if m.get("published_at")]
            if dates:
                rep["published_at"] = min(dates)
                rep["published_from"] = "other listing of the same job"
        out.append(rep)
    return out
