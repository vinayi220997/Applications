"""The scan: discover -> normalise -> store -> close/reopen -> dedupe -> match -> verify -> report -> deliver."""
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from . import db as dbm
from . import report, verify
from .config import DATA_DIR, REPORTS_DIR, load_company_candidates, load_settings, LOG_PATH, ensure_dirs
from .dedupe import cluster
from .freshness import classify
from .http import FetchError
from .intake import summary as profile_summary
from .matching import score_job
from .normalize import content_hash, iso, now_utc, parse_date
from .sources import ats, boards

log = logging.getLogger("jobradar")
LOCK = DATA_DIR / "run.lock"
ATS_RECHECK_DEAD_DAYS = 14


def setup_logging():
    ensure_dirs()
    if not log.handlers:
        h = logging.FileHandler(LOG_PATH, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)


class Progress:
    def __init__(self, cb=None):
        self.cb = cb
        self.lines = []

    def __call__(self, msg):
        self.lines.append(msg)
        log.info(msg)
        if self.cb:
            self.cb(msg)
        else:
            try:
                print(msg, flush=True)
            except Exception:       # no console (pythonw) or an encoding it can't show
                pass


# ------------------------------------------------------------------ registry
def sync_registry(conn):
    for c in load_company_candidates():
        conn.execute("INSERT OR IGNORE INTO companies(ats, token, name, source) VALUES (?,?,?, 'registry')",
                     (c["ats"], c["token"], c.get("name")))


def boards_to_scan(conn, settings):
    rows = conn.execute("SELECT * FROM companies").fetchall()
    enabled = settings["sources"]
    out = []
    cutoff = iso(now_utc() - timedelta(days=ATS_RECHECK_DEAD_DAYS))
    for r in rows:
        if not enabled.get(r["ats"], False):
            continue
        if r["status"] == "dead" and (r["last_checked"] or "") > cutoff:
            continue
        out.append(dbm.row_to_dict(r))
    return out


# ------------------------------------------------------------------ storage
def upsert_jobs(conn, jobs, run_start):
    now = iso(now_utc())
    for j in jobs:
        jid = f"{j['source']}:{j['source_job_id']}"
        j["id"] = jid
        h = content_hash(j)
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        status = "verified_active" if j.get("is_ats") else "appears_active"
        if row is None:
            conn.execute("""INSERT INTO jobs(id, source, source_job_id, requisition_id, company, title, location,
                work_arrangement, employment_type, description, salary_text, salary_min_lpa, salary_max_lpa,
                published_at, updated_at, first_seen_at, last_seen_at, verified_at, status, apply_url,
                apply_url_verified, careers_url, source_url, source_name, is_ats, board, content_hash, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (jid, j["source"], j["source_job_id"], j.get("requisition_id"), j.get("company"), j.get("title"),
                 j.get("location"), j.get("workplace_type"), j.get("employment_type"), j.get("description"),
                 j.get("salary_text"), j.get("salary_min_lpa"), j.get("salary_max_lpa"), j.get("published_at"),
                 j.get("updated_at"), now, now, now if j.get("is_ats") else None, status, j.get("apply_url"),
                 1 if j.get("is_ats") else None, j.get("careers_url"), j.get("source_url"), j.get("source_name"),
                 1 if j.get("is_ats") else 0, j.get("board"), h,
                 dbm.jdump({k: j.get(k) for k in ("remote_flag", "workplace_type", "detail_url")})))
            j["change"] = None
            j["first_seen_at"] = now
        else:
            change = None
            if row["closed_at"]:
                change = "reopened"
                conn.execute("INSERT INTO job_history VALUES (?,?,?,?,?)", (jid, now, "status", "closed", "reopened"))
            elif row["content_hash"] != h:
                change = "updated"
                conn.execute("INSERT INTO job_history VALUES (?,?,?,?,?)", (jid, now, "content", row["content_hash"], h))
            # A changed source publish date on the same requisition means it was re-posted.
            if row["published_at"] and j.get("published_at") and row["published_at"] != j.get("published_at"):
                change = change or "reopened"
                conn.execute("INSERT INTO job_history VALUES (?,?,?,?,?)", (jid, now, "published_at", row["published_at"], j.get("published_at")))
            conn.execute("""UPDATE jobs SET company=?, title=?, location=?, work_arrangement=?, employment_type=?,
                description=COALESCE(NULLIF(?, ''), description), salary_text=?, salary_min_lpa=?, salary_max_lpa=?,
                published_at=COALESCE(?, published_at), updated_at=?, last_seen_at=?,
                verified_at=CASE WHEN ?=1 THEN ? ELSE verified_at END,
                status=CASE WHEN ?=1 THEN 'verified_active' WHEN status='closed' THEN 'appears_active' ELSE status END,
                apply_url=?, careers_url=?, source_url=?, content_hash=?, closed_at=NULL,
                reopened=CASE WHEN ? THEN 1 ELSE reopened END WHERE id=?""",
                (j.get("company"), j.get("title"), j.get("location"), j.get("workplace_type"), j.get("employment_type"),
                 j.get("description"), j.get("salary_text"), j.get("salary_min_lpa"), j.get("salary_max_lpa"),
                 j.get("published_at"), j.get("updated_at"), now, 1 if j.get("is_ats") else 0, now,
                 1 if j.get("is_ats") else 0, j.get("apply_url"), j.get("careers_url"), j.get("source_url"), h,
                 change == "reopened", jid))
            j["change"] = change
            j["first_seen_at"] = row["first_seen_at"]
        j["content_hash"] = h
        j["status"] = status
        j["verified_at"] = now if j.get("is_ats") else None


def close_missing(conn, scanned_boards, seen_ids):
    """A job that disappeared from an employer feed we just read successfully is closed."""
    now = iso(now_utc())
    n = 0
    for b in scanned_boards:
        for r in conn.execute("SELECT id FROM jobs WHERE board=? AND closed_at IS NULL", (b,)).fetchall():
            if r["id"] not in seen_ids:
                conn.execute("UPDATE jobs SET status='closed', closed_at=? WHERE id=?", (now, r["id"]))
                conn.execute("INSERT INTO job_history VALUES (?,?,?,?,?)", (r["id"], now, "status", "open", "closed"))
                n += 1
    return n


# ------------------------------------------------------------------ run
def online(timeout=10):
    """Quick check that job sites are reachable before spending minutes on retries."""
    from .http import fetch
    for url in ("https://api.lever.co/v0/postings/lever?mode=json&limit=1",
                "https://boards-api.greenhouse.io/v1/boards/greenhouse/jobs"):
        try:
            fetch(url, timeout=min(timeout, 10), retries=0)
            return True
        except FetchError as e:
            if e.status:          # the site answered (even 404) -> we are online
                return True
    return False


def acquire_lock():
    ensure_dirs()
    if LOCK.exists():
        try:
            age = time.time() - LOCK.stat().st_mtime
        except OSError:
            age = 0
        if age < 3 * 3600:
            return False
    LOCK.write_text(str(os.getpid()))
    return True


def release_lock():
    try:
        LOCK.unlink()
    except OSError:
        pass


def repair_unsent(conn):
    """Earlier versions marked jobs as reported even when the email wasn't sent. Undo that so they go out next time."""
    for r in conn.execute("SELECT id, summary_json FROM runs WHERE summary_json IS NOT NULL").fetchall():
        for pid, v in (dbm.jload(r["summary_json"], {}) or {}).items():
            if isinstance(v, dict) and not v.get("email_sent") and str(v.get("email_note", "")).startswith(("email sending is not configured", "email failed")):
                conn.execute("DELETE FROM notifications WHERE run_id=? AND profile_id=?", (r["id"], int(pid)))


def load_profiles(conn, profile_ids=None):
    rows = conn.execute("SELECT * FROM profiles WHERE active=1").fetchall()
    out = []
    for r in rows:
        if profile_ids and r["id"] not in profile_ids:
            continue
        p = dbm.jload(r["profile_json"], {})
        p.update({"id": r["id"], "name": r["name"], "email": r["email"], "email_on": r["email_on"]})
        p["summary"] = profile_summary(p)
        out.append(p)
    return out


def run(trigger="manual", profile_ids=None, progress=None, send=True):
    setup_logging()
    say = Progress(progress)
    if not acquire_lock():
        say("Another scan is already running. Try again when it finishes.")
        return None
    settings = load_settings()
    timeout = settings["request_timeout_seconds"]
    run_start = iso(now_utc())
    conn = dbm.connect()
    run_id = conn.execute("INSERT INTO runs(started_at, status, trigger) VALUES (?, 'running', ?)", (run_start, trigger)).lastrowid
    conn.commit()
    failures, scanned_boards = [], []
    configured = scanned = retrieved = 0
    try:
        profiles = load_profiles(conn, profile_ids)
        if not profiles:
            say("No active searches. Add one in the app (or `python -m jobradar ask`) first.")
            conn.execute("UPDATE runs SET status='completed', finished_at=?, summary_json=? WHERE id=?",
                         (iso(now_utc()), dbm.jdump({"note": "no active searches"}), run_id))
            conn.commit()
            return run_id
        say(f"Scan started for {len(profiles)} search(es).")
        repair_unsent(conn)
        if not online(timeout):
            msg = "No internet connection, or a firewall/proxy is blocking job sites. Nothing was scanned."
            say(msg)
            conn.execute("UPDATE runs SET finished_at=?, status='failed', sources_configured=0, sources_scanned=0, failures_json=? WHERE id=?",
                         (iso(now_utc()), dbm.jdump([msg]), run_id))
            conn.commit()
            return run_id
        sync_registry(conn)
        conn.commit()

        # ---------------- 1. employer ATS boards
        targets = boards_to_scan(conn, settings)
        configured += len(targets)
        all_jobs = []
        say(f"Checking {len(targets)} employer job boards…")
        with ThreadPoolExecutor(max_workers=settings["max_parallel_requests"]) as ex:
            futs = {ex.submit(ats.CONNECTORS[t["ats"]], t["token"], timeout): t for t in targets}
            for f in as_completed(futs):
                t = futs[f]
                now = iso(now_utc())
                try:
                    company, jobs = f.result()
                    for j in jobs:
                        j["company"] = t.get("name") or company or j["company"]
                    all_jobs.extend(jobs)
                    scanned += 1
                    scanned_boards.append(f"{t['ats']}:{t['token']}")
                    conn.execute("UPDATE companies SET status='ok', last_checked=?, job_count=?, last_error=NULL, name=COALESCE(name, ?) WHERE ats=? AND token=?",
                                 (now, len(jobs), company, t["ats"], t["token"]))
                except FetchError as e:
                    dead = e.status in (404, 410)
                    conn.execute("UPDATE companies SET status=?, last_checked=?, last_error=? WHERE ats=? AND token=?",
                                 ("dead" if dead else "error", now, str(e), t["ats"], t["token"]))
                    if dead:
                        configured -= 1   # not a real board; removed from the registry until re-checked
                    else:
                        failures.append(f"{t['ats'].title()} board '{t['token']}': {e}")
                except Exception as e:
                    failures.append(f"{t['ats'].title()} board '{t['token']}': unexpected error {e.__class__.__name__}")
        conn.commit()
        say(f"Employer boards: {scanned} answered, {len(all_jobs)} open jobs.")

        # ---------------- 2. job-board APIs and feeds
        queries = []
        for p in profiles:
            for r in p.get("roles") or []:
                if r.lower() not in [q.lower() for q in queries]:
                    queries.append(r)
        queries = queries[:3] or ["software engineer"]
        want_remote = any(p.get("remote_international") or p.get("work_arrangement") == "remote" for p in profiles)
        for name, fn in boards.BOARDS.items():
            if not settings["sources"].get(name):
                continue
            if not want_remote and name in ("remotive", "remoteok", "jobicy", "weworkremotely", "arbeitnow"):
                continue
            configured += 1
            try:
                jobs = fn(queries, timeout)
                all_jobs.extend(jobs)
                scanned += 1
                say(f"{name}: {len(jobs)} jobs")
            except Exception as e:
                failures.append(f"{name}: {e}")
        adz = settings["sources"].get("adzuna") or {}
        if adz.get("enabled") and adz.get("app_id") and adz.get("app_key"):
            configured += 1
            try:
                locs = list(dict.fromkeys(l for p in profiles for l in (p.get("locations") or [])))
                jobs = boards.adzuna(queries, locs, adz, timeout)
                all_jobs.extend(jobs)
                scanned += 1
                say(f"adzuna: {len(jobs)} jobs")
            except Exception as e:
                failures.append(f"Adzuna: {e}")
        retrieved = len(all_jobs)

        # ---------------- 3. store, detect changes, close vanished jobs
        upsert_jobs(conn, all_jobs, run_start)
        closed = close_missing(conn, scanned_boards, {j['id'] for j in all_jobs})
        conn.commit()
        say(f"Stored {retrieved} listings; {closed} jobs closed since the last scan.")

        # ---------------- 4. dedupe
        unique = cluster(all_jobs)
        say(f"{len(unique)} unique jobs after removing duplicates.")

        # ---------------- 5. match, verify, report per profile
        summaries = {}
        for p in profiles:
            summaries[p["id"]] = process_profile(conn, p, unique, settings, run_id, say,
                                                 {"sources_configured": configured, "sources_scanned": scanned,
                                                  "retrieved": retrieved, "unique": len(unique)}, failures, send)
        status = "completed" if not failures else ("partial" if scanned else "failed")
        conn.execute("""UPDATE runs SET finished_at=?, status=?, sources_configured=?, sources_scanned=?, retrieved=?,
                        unique_jobs=?, failures_json=?, summary_json=? WHERE id=?""",
                     (iso(now_utc()), status, configured, scanned, retrieved, len(unique),
                      dbm.jdump(failures), dbm.jdump(summaries), run_id))
        conn.commit()
        say(f"Scan {status}. {scanned}/{configured} sources scanned.")
        return run_id
    except Exception as e:
        log.exception("run failed")
        conn.execute("UPDATE runs SET finished_at=?, status='failed', failures_json=? WHERE id=?",
                     (iso(now_utc()), dbm.jdump(failures + [f"run crashed: {e}"]), run_id))
        conn.commit()
        say(f"Scan failed: {e}")
        return run_id
    finally:
        conn.close()
        release_lock()


def process_profile(conn, p, unique, settings, run_id, say, stats, failures, send):
    now = now_utc()
    weights = settings["weights"]
    scored = []
    for j in unique:
        if j.get("status") == "closed":
            continue
        m = score_job(j, p, weights)
        if not m["eligible"] or m["score"] < settings["min_score_to_report"] - 10:
            continue
        jj = dict(j)
        jj.update(score=m["score"], reasons=m["reasons"], gaps=m["gaps"],
                  experience_text=m.get("experience_text"), arrangement=m.get("arrangement"))
        scored.append(jj)
    scored.sort(key=lambda x: -x["score"])

    # Enrich + verify the shortlist (third-party links and SmartRecruiters descriptions).
    top = scored[: settings["verify_top_n"]]
    for j in top:
        if j.get("source") == "smartrecruiters":
            try:
                raw = dbm.jload(conn.execute("SELECT raw_json FROM jobs WHERE id=?", (j["id"],)).fetchone()["raw_json"], {})
                desc, apply = ats.smartrecruiters_detail({"detail_url": raw.get("detail_url")})
                if desc:
                    j["description"] = desc
                    m = score_job(j, p, weights)
                    j.update(score=m["score"], reasons=m["reasons"], gaps=m["gaps"], experience_text=m.get("experience_text"))
                    conn.execute("UPDATE jobs SET description=? WHERE id=?", (desc, j["id"]))
                if apply:
                    j["apply_url"] = apply
            except Exception:
                pass
        if not j.get("is_ats"):
            st, ok, note = verify.check(j.get("apply_url"), j.get("title"))
            j.update(status=st, apply_url_verified=ok, verify_note=note, verified_at=iso(now_utc()))
            conn.execute("UPDATE jobs SET status=?, apply_url_verified=?, verified_at=?, closed_at=CASE WHEN ?='closed' THEN ? ELSE closed_at END WHERE id=?",
                         (st, 1 if ok else 0, j["verified_at"], st, j["verified_at"], j["id"]))
        else:
            j["apply_url_verified"] = True
            j["verify_note"] = "listed in the employer's live job feed"
    shortlisted_ids = {j["id"] for j in top}
    for j in scored:
        if j["id"] not in shortlisted_ids and not j.get("is_ats"):
            j["status"] = "unable_to_verify"
            j["verify_note"] = "not checked (outside the top matches)"
            j["apply_url_verified"] = False
    scored = [j for j in scored if j["status"] != "closed" and j["score"] >= settings["min_score_to_report"]]

    # Persist matches
    for j in scored:
        conn.execute("""INSERT OR REPLACE INTO matches VALUES (?,?,?,?,?,?,?,?)""",
                     (p["id"], j["id"], j["score"], 1, dbm.jdump(j["reasons"]), dbm.jdump(j["gaps"]), "{}", iso(now)))

    # Classify freshness + novelty
    sections = {"top24": [], "week": [], "changed": [], "unknown": [], "older": [], "still_open": []}
    dismissed = {r["job_id"] for r in conn.execute("SELECT job_id FROM user_state WHERE profile_id=? AND state IN ('dismissed','applied')", (p["id"],))}
    for j in scored:
        if j["id"] in dismissed:
            continue
        j["freshness"] = classify(j.get("published_at"), now, settings["freshness_window_days"])
        sent = conn.execute("SELECT content_hash FROM notifications WHERE profile_id=? AND job_id=?", (p["id"], j["id"])).fetchall()
        hashes = {r["content_hash"] for r in sent}
        if not sent:
            novelty = "new"
        elif j.get("content_hash") not in hashes or j.get("change") == "reopened":
            novelty = "changed"
        else:
            novelty = "seen"
        if novelty == "seen":
            sections["still_open"].append(j)
        elif novelty == "changed":
            j["change"] = j.get("change") or "updated"
            sections["changed"].append(j)
        elif j["freshness"] == "24h":
            sections["top24"].append(j)
        elif j["freshness"] in ("3d", "7d"):
            sections["week"].append(j)
        elif j["freshness"] == "unknown":
            sections["unknown"].append(j)
        else:
            sections["older"].append(j)

    def rank(j):
        act = {"verified_active": 2, "appears_active": 1}.get(j.get("status"), 0)
        fr = {"24h": 4, "3d": 3, "7d": 2, "older_active": 1, "unknown": 0}.get(j.get("freshness"), 0)
        return (-j["score"], -fr, -act, 0 if j.get("apply_url_verified") else 1)

    cap = settings["max_jobs_per_report"]
    for k in sections:
        sections[k].sort(key=rank)
    budget = cap
    for k in ("top24", "week", "changed", "unknown", "older"):
        sections[k] = sections[k][:budget]
        budget = max(0, budget - len(sections[k]))

    reported = [j for k in ("top24", "week", "changed", "unknown", "older") for j in sections[k]]
    st = dict(stats)
    st.update(new=len(reported),
              recent=sum(1 for j in reported if j["freshness"] in ("24h", "3d", "7d")),
              verified=sum(1 for j in reported if j["status"] == "verified_active"),
              high=sum(1 for j in reported if j["score"] >= settings["high_match_threshold"]))
    links = boards.manual_search_links(p)
    html = report.build(p, sections, st, failures, links, settings)
    stamp = now.strftime("%Y-%m-%d_%H%M")
    safe = "".join(c if c.isalnum() else "_" for c in p["name"])[:40]
    path = REPORTS_DIR / f"{stamp}_{safe}.html"
    path.write_text(html, encoding="utf-8")

    email_note = "no email address on this search"
    sent_ok = False
    if send and p.get("email") and p.get("email_on"):
        subject = (f"Job Radar: {len(reported)} new match{'es' if len(reported) != 1 else ''} – {p['name']}"
                   if reported else f"Job Radar: no new matches today – {p['name']}")
        sent_ok, email_note = report.send_email(settings, p["email"], subject, html, report.plain_text(p, sections))
    # Record what was reported so unchanged jobs are never re-sent.
    wants_email = bool(p.get("email") and p.get("email_on"))
    # Mark jobs as reported only when the person really received them (or has no email, so the app is the inbox).
    # If email isn't set up or failed, the same jobs go out in the first email that works.
    if reported and (sent_ok or not wants_email or not send):
        for j in reported:
            conn.execute("INSERT OR IGNORE INTO notifications VALUES (?,?,?,?,?)",
                         (p["id"], j["id"], j.get("content_hash"), iso(now), run_id))
    conn.commit()
    say(f"[{p['name']}] {len(reported)} new/updated matches, report saved{'; email sent' if sent_ok else '; ' + email_note}.")
    return {"report": str(path), "reported": len(reported), "email_sent": sent_ok, "email_note": email_note,
            "high": st["high"], "verified": st["verified"]}


def email_current(profile_id, limit=40):
    """Email every open, eligible match currently stored for a search (ignores 'already sent')."""
    settings = load_settings()
    conn = dbm.connect()
    try:
        profs = load_profiles(conn, [profile_id]) or []
        if not profs:
            row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
            if not row:
                return False, "Search not found."
            p = dbm.jload(row["profile_json"], {})
            p.update({"id": row["id"], "name": row["name"], "email": row["email"], "email_on": row["email_on"]})
            p["summary"] = profile_summary(p)
        else:
            p = profs[0]
        if not p.get("email"):
            return False, "This search has no email address. Add one first."
        now = now_utc()
        rows = conn.execute("""SELECT j.*, m.score, m.reasons_json, m.gaps_json FROM matches m JOIN jobs j ON j.id=m.job_id
            LEFT JOIN user_state u ON u.profile_id=m.profile_id AND u.job_id=m.job_id
            WHERE m.profile_id=? AND j.status!='closed' AND (u.state IS NULL OR u.state='saved')
            ORDER BY m.score DESC LIMIT ?""", (profile_id, limit)).fetchall()
        sections = {"top24": [], "week": [], "changed": [], "unknown": [], "older": [], "still_open": []}
        jobs = []
        for r in rows:
            j = dbm.row_to_dict(r)
            j["reasons"] = dbm.jload(j.pop("reasons_json"), [])
            j["gaps"] = dbm.jload(j.pop("gaps_json"), [])
            j["freshness"] = classify(j.get("published_at"), now)
            j["arrangement"] = j.get("work_arrangement")
            j["apply_url_verified"] = bool(j.get("apply_url_verified")) if j.get("apply_url_verified") is not None else j.get("is_ats") == 1
            key = {"24h": "top24", "3d": "week", "7d": "week", "unknown": "unknown"}.get(j["freshness"], "older")
            sections[key].append(j)
            jobs.append(j)
        last = conn.execute("SELECT * FROM runs WHERE status!='running' ORDER BY id DESC LIMIT 1").fetchone()
        st = {"sources_configured": last["sources_configured"] if last else 0, "sources_scanned": last["sources_scanned"] if last else 0,
              "retrieved": last["retrieved"] if last else 0, "unique": last["unique_jobs"] if last else 0,
              "new": len(jobs), "recent": sum(1 for j in jobs if j["freshness"] in ("24h", "3d", "7d")),
              "verified": sum(1 for j in jobs if j["status"] == "verified_active"),
              "high": sum(1 for j in jobs if (j["score"] or 0) >= settings["high_match_threshold"])}
        failures = dbm.jload(last["failures_json"], []) if last else ["No scan has run yet."]
        html = report.build(p, sections, st, failures, boards.manual_search_links(p), settings)
        subject = f"Job Radar: {len(jobs)} open match{'es' if len(jobs) != 1 else ''} – {p['name']}"
        ok, note = report.send_email(settings, p["email"], subject, html, report.plain_text(p, sections))
        if ok:
            for j in jobs:
                conn.execute("INSERT OR IGNORE INTO notifications VALUES (?,?,?,?,?)", (p["id"], j["id"], j.get("content_hash"), iso(now), None))
            conn.commit()
            return True, f"Sent {len(jobs)} job{'s' if len(jobs) != 1 else ''} to {p['email']}." if jobs else f"Sent to {p['email']}, but there are no open matches stored yet. Run a scan first."
        return False, note
    finally:
        conn.close()
