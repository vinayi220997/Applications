"""Local web app (http://127.0.0.1:8765). Listens on this computer only."""
import json
import re
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

from . import db as dbm
from . import attachments, cards, intake, pipeline, scheduler, schedules, services
from .config import REPORTS_DIR, load_settings, save_settings
from .freshness import classify
from .normalize import iso, now_utc
from .sources.ats import detect_board

STATIC = Path(__file__).parent / "static"
SAMPLE_TYPES = {".txt": "text/plain; charset=utf-8", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".png": "image/png", ".wav": "audio/wav", ".mp3": "audio/mpeg"}
PKG = Path(__file__).parent


def _code_mtime():
    return max((f.stat().st_mtime for f in PKG.rglob("*.py")), default=0)


CODE_MTIME = _code_mtime()       # what this running copy loaded
SERVER = {"httpd": None}
RUN = {"thread": None, "lines": [], "run_id": None}
SECRET_KEYS = [("email", "app_password"), ("anthropic", "api_key"), ("sources", "adzuna", "app_key")]


def _redact(settings):
    s = json.loads(json.dumps(settings))
    for path in SECRET_KEYS:
        node = s
        for k in path[:-1]:
            node = node.get(k, {})
        if node.get(path[-1]):
            node[path[-1]] = "••••••••"
    return s


def _merge_settings(incoming):
    s = load_settings()
    def merge(dst, src, path=()):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v, path + (k,))
            elif v == "••••••••":
                continue          # unchanged secret
            else:
                dst[k] = v
    merge(s, incoming)
    save_settings(s)
    return s


def profile_rows(conn):
    out = []
    for r in conn.execute("SELECT * FROM profiles ORDER BY id DESC"):
        p = dbm.jload(r["profile_json"], {})
        out.append({"id": r["id"], "name": r["name"], "email": r["email"], "email_on": bool(r["email_on"]),
                    "active": bool(r["active"]), "summary": intake.summary(p), "profile": p,
                    "created_at": r["created_at"]})
    return out


def jobs_for(conn, pid):
    now = now_utc()
    rows = conn.execute("""SELECT j.*, m.score, m.reasons_json, m.gaps_json, m.computed_at, u.state AS user_state
        FROM matches m JOIN jobs j ON j.id = m.job_id
        LEFT JOIN user_state u ON u.profile_id = m.profile_id AND u.job_id = m.job_id
        WHERE m.profile_id = ? ORDER BY m.score DESC LIMIT 400""", (pid,)).fetchall()
    out = []
    for r in rows:
        d = dbm.row_to_dict(r)
        d.pop("raw_json", None)
        d["reasons"] = dbm.jload(d.pop("reasons_json"), [])
        d["gaps"] = dbm.jload(d.pop("gaps_json"), [])
        d["freshness"] = classify(d.get("published_at"), now)
        d["description"] = (d.get("description") or "")[:6000]
        out.append(d)
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "JobRadar/1.0"

    def log_message(self, fmt, *args):
        pass

    # ---------- helpers
    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json", headers=None):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        texty = ctype.startswith("text/") or ctype == "application/json"
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if texty and "charset" not in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (ConnectionError, OSError):
            pass                     # the browser closed or reloaded the page before the answer arrived

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 22_000_000:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    # ---------- GET
    def do_GET(self):
        try:
            return self._get()
        except Exception as e:
            pipeline.log.exception("GET failed")
            return self._send(500, {"error": f"Something went wrong: {e.__class__.__name__}: {e}. Details are in data/jobradar.log."})

    def do_POST(self):
        try:
            return self._post()
        except Exception as e:
            pipeline.log.exception("POST failed")
            return self._send(500, {"error": f"Something went wrong: {e.__class__.__name__}: {e}. Details are in data/jobradar.log."})

    def _get(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html")
        m = re.fullmatch(r"/attachments/([0-9a-f]{16})", path)
        if m:
            with dbm.session() as conn:
                a = attachments.get(conn, m.group(1))
            if a and Path(a["path"]).exists():
                ctype = (a["mime"] or "application/octet-stream").split(";")[0]
                return self._send(200, Path(a["path"]).read_bytes(), ctype)
            return self._send(404, {"error": "attachment not found"})
        m = re.fullmatch(r"/samples/([\w.\-]+)", path)
        if m:
            f = STATIC / "samples" / m.group(1)
            if f.exists() and f.suffix in SAMPLE_TYPES:
                return self._send(200, f.read_bytes(), SAMPLE_TYPES[f.suffix],
                                  {"Content-Disposition": f'attachment; filename="{f.name}"'} if "download" in (urlparse(self.path).query or "") else None)
            return self._send(404, {"error": "sample not found"})
        if path == "/api/services":
            return self._send(200, services.status(load_settings()))
        if path == "/api/intake/sections":
            return self._send(200, {"sections": intake.section_info()})
        if path.startswith("/reports/"):
            name = unquote(path[len("/reports/"):])
            f = (REPORTS_DIR / name).resolve()
            if f.parent == REPORTS_DIR.resolve() and f.exists() and f.suffix == ".html":
                return self._send(200, f.read_bytes(), "text/html")
            return self._send(404, {"error": "report not found"})
        with dbm.session() as conn:
            if path == "/api/state":
                runs = [dbm.row_to_dict(r) for r in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5")]
                for r in runs:
                    r["failures"] = dbm.jload(r.pop("failures_json"), [])
                    r["summary"] = dbm.jload(r.pop("summary_json"), {})
                comp = conn.execute("SELECT status, COUNT(*) n FROM companies GROUP BY status").fetchall()
                clist = cards.card_list(conn)
                return self._send(200, {
                    "profiles": clist, "runs": runs, "schedules": schedules.list_all(conn),
                    "timezones": schedules.TIMEZONES,
                    "running": bool(RUN["thread"] and RUN["thread"].is_alive()),
                    "settings": _redact(load_settings()),
                    "companies": {r["status"]: r["n"] for r in comp},
                    "update_ready": _code_mtime() > CODE_MTIME + 1})
            m = re.fullmatch(r"/api/profiles/(\d+)/history", path)
            if m:
                return self._send(200, cards.history(conn, int(m.group(1))))
            m = re.fullmatch(r"/api/profiles/(\d+)/export", path)
            if m:
                try:
                    data = cards.export(conn, int(m.group(1)), "email=1" in (urlparse(self.path).query or ""))
                except cards.CardError as e:
                    return self._send(404, {"error": str(e)})
                fname = re.sub(r"[^\w\-]+", "-", data["card"]["name"]).strip("-")[:50] or "card"
                return self._send(200, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"), "application/json",
                                  {"Content-Disposition": f'attachment; filename="jobradar-card-{fname}.json"'})
            m = re.fullmatch(r"/api/profiles/(\d+)/jobs", path)
            if m:
                return self._send(200, {"jobs": jobs_for(conn, int(m.group(1)))})
            if path == "/api/run/status":
                bg = pipeline.LOCK.exists() and not (RUN["thread"] and RUN["thread"].is_alive())
                return self._send(200, {"running": bool(RUN["thread"] and RUN["thread"].is_alive()) or bg, "background": bg,
                                        "stopping": pipeline.CANCEL.exists(),
                                        "lines": RUN["lines"][-80:], "run_id": RUN["run_id"]})
            if path == "/api/companies":
                rows = [dbm.row_to_dict(r) for r in conn.execute("SELECT * FROM companies ORDER BY status, ats, token")]
                return self._send(200, {"companies": rows})
        return self._send(404, {"error": "not found"})

    # ---------- POST / DELETE
    def _post(self):
        if not self._host_ok() or self.headers.get("X-JobRadar") != "1":
            return self._send(403, {"error": "forbidden"})
        path = urlparse(self.path).path
        try:
            body = self._body()
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "Invalid request body."})
        settings = load_settings()

        if path == "/api/attachments":
            try:
                with dbm.session() as conn:
                    rec = attachments.save(conn, body.get("filename"), body.get("mime"), body.get("data") or "",
                                           settings, body.get("transcript"), body.get("interpret", True) is not False)
                return self._send(200, rec)
            except attachments.AttachmentError as e:
                return self._send(400, {"error": str(e)})
        if path == "/api/attachments/update":
            try:
                with dbm.session() as conn:
                    rec = attachments.update(conn, body.get("id") or "", settings, body.get("text"), body.get("extracted"))
                return self._send(200, rec)
            except attachments.AttachmentError as e:
                return self._send(400, {"error": str(e)})
        if path == "/api/ai/test":
            if body.get("settings"):
                settings = _merge_settings(body["settings"])
            return self._send(200, services.test_ai(settings))
        if path == "/api/ocr/test":
            if body.get("settings"):
                settings = _merge_settings(body["settings"])
            return self._send(200, services.test_ocr(settings))
        def decorate(r, before_state):
            before = (before_state or {}).get("profile") or {}
            st = r.get("state") or {}
            r["progress"] = intake.progress(st)
            r["changes"] = intake.changes(before, st.get("profile") or {})
            r["error"] = st.get("error")
            r["asked_key"] = (before_state or {}).get("pending")
            return r
        def items_for(ids):
            with dbm.session() as conn:
                return [a for a in (attachments.get(conn, i) for i in (ids or [])[:10]) if a]
        if path == "/api/intake/start":
            desc = (body.get("description") or "").strip()
            items = items_for(body.get("attachment_ids"))
            if len(desc) < 5 and not any(i.get("extracted") for i in items):
                return self._send(400, {"error": "Describe the job in a few more words, or attach a resume or job post with readable text."})
            return self._send(200, decorate(intake.start(desc, settings, items), {}))
        if path == "/api/intake/attach":
            before = json.loads(json.dumps(body.get("state") or {}))
            return self._send(200, decorate(intake.attach(body.get("state") or {}, items_for(body.get("attachment_ids"))), before))
        if path == "/api/intake/answer":
            before = json.loads(json.dumps(body.get("state") or {}))
            return self._send(200, decorate(intake.answer(body.get("state") or {}, body.get("answer") or ""), before))
        if path == "/api/intake/set":
            return self._send(200, intake.set_field(body.get("state") or {}, body.get("key") or "", body.get("text") or "",
                                                    body.get("mode") or "overwrite", body.get("items")))
        if path == "/api/intake/progress":
            return self._send(200, intake.progress(body.get("state") or {}))

        with dbm.session() as conn:
            if path == "/api/profiles":
                try:
                    pid, linked = cards.create(conn, body.get("profile") or {}, body.get("input_mode") or "chart", body.get("answer_source"),
                                               (body.get("profile") or {}).get("email"), True, True, link_default=body.get("link_default", True))
                except cards.CardError as e:
                    return self._send(400, {"error": str(e)})
                attachments.link(conn, (body.get("profile") or {}).get("attachment_ids"), pid)
                conn.commit()
                if linked:
                    schedules.sync_os(conn)
                return self._send(200, {"id": pid, "default_schedule": linked})
            m = re.fullmatch(r"/api/profiles/(\d+)/duplicate", path)
            if m:
                try:
                    return self._send(200, {"id": cards.duplicate(conn, int(m.group(1)))})
                except cards.CardError as e:
                    return self._send(404, {"error": str(e)})
            m = re.fullmatch(r"/api/profiles/(\d+)", path)
            if m:
                pid = int(m.group(1))
                if not conn.execute("SELECT 1 FROM profiles WHERE id=?", (pid,)).fetchone():
                    return self._send(404, {"error": "That card no longer exists."})
                if body.get("profile") is not None:
                    try:
                        changed = cards.update(conn, pid, body["profile"], body.get("input_mode"), body.get("answer_source"))
                    except cards.CardError as e:
                        return self._send(400, {"error": str(e)})
                    attachments.link(conn, body["profile"].get("attachment_ids"), pid)
                    return self._send(200, {"ok": True, "changed": changed})
                if "email" in body:
                    v = (body.get("email") or "").strip()
                    if v and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
                        return self._send(400, {"error": "That doesn't look like an email address."})
                    conn.execute("UPDATE profiles SET email=?, updated_at=? WHERE id=?", (v or None, iso(now_utc()), pid))
                    cards.log(conn, pid, "email", f"Report email changed to {v}" if v else "Report email removed")
                if "name" in body:
                    conn.execute("UPDATE profiles SET name=?, updated_at=? WHERE id=?", (body["name"], iso(now_utc()), pid))
                for k in ("active", "email_on"):
                    if k in body:
                        cards.set_flag(conn, pid, k, bool(body[k]))
                return self._send(200, {"ok": True})
            if path == "/api/jobs/state":
                st = body.get("state")
                if st in (None, "", "new"):
                    conn.execute("DELETE FROM user_state WHERE profile_id=? AND job_id=?", (body["profile_id"], body["job_id"]))
                elif st in ("saved", "applied", "dismissed"):
                    conn.execute("INSERT OR REPLACE INTO user_state VALUES (?,?,?,?)", (body["profile_id"], body["job_id"], st, iso(now_utc())))
                return self._send(200, {"ok": True})
            if path == "/api/companies":
                det = detect_board(body.get("url") or "")
                if not det:
                    return self._send(400, {"error": "That isn't a supported careers link. Use a Greenhouse, Lever, Ashby, SmartRecruiters, Workable or Recruitee job-board URL."})
                conn.execute("INSERT OR REPLACE INTO companies(ats, token, name, status, source) VALUES (?,?,?, 'unchecked', 'user')",
                             (det[0], det[1], body.get("name") or None))
                return self._send(200, {"ats": det[0], "token": det[1]})

        if path == "/api/import/preview":
            try:
                card, warnings = cards.check_import(body.get("data"))
            except cards.CardError as e:
                return self._send(400, {"error": str(e)})
            with dbm.session() as conn:
                existing = [{"id": r["id"], "name": r["name"]} for r in conn.execute("SELECT id, name FROM profiles ORDER BY name")]
            same = next((c for c in existing if c["name"].lower() == card["name"].lower()), None)
            return self._send(200, {"card": card, "warnings": warnings, "existing": existing, "same_name": same})
        if path == "/api/import":
            try:
                with dbm.session() as conn:
                    pid, warnings, made = cards.do_import(conn, body.get("data"), body.get("mode") or "new", body.get("target_id"),
                                                          body.get("answers"), bool(body.get("with_schedules")))
                    conn.commit()
                    schedules.sync_os(conn)
            except cards.CardError as e:
                return self._send(400, {"error": str(e)})
            return self._send(200, {"id": pid, "warnings": warnings, "schedules": made})
        if path == "/api/intake/resume":
            return self._send(200, intake.resume(body.get("profile") or {}, bool(body.get("all_answered"))))
        if path == "/api/schedules" or re.fullmatch(r"/api/schedules/(\d+)(/enable|/run)?", path):
            m = re.fullmatch(r"/api/schedules/(\d+)(/enable|/run)?", path)
            sid = int(m.group(1)) if m else None
            try:
                with dbm.session() as conn:
                    if m and m.group(2) == "/run":
                        sch, ids, skipped = schedules.cards_to_run(conn, sid)
                        if not sch:
                            return self._send(404, {"error": "That schedule no longer exists."})
                        ids = [c["id"] for c in sch["cards"] if c["active"]]
                        if not ids:
                            return self._send(400, {"error": "No turned-on cards are linked to this schedule."})
                        body = {"profile_ids": ids}
                    elif m and m.group(2) == "/enable":
                        schedules.set_enabled(conn, sid, bool(body.get("enabled")))
                        conn.commit()
                        problems = schedules.sync_os(conn)
                        return self._send(200, {"ok": True, "problems": problems})
                    else:
                        sid, confl = schedules.save(conn, body, sid)
                        conn.commit()
                        problems = schedules.sync_os(conn)
                        return self._send(200, {"id": sid, "problems": problems, "duplicates": confl})
            except schedules.Conflict as c:
                return self._send(409, {"error": "Some cards are already in another active schedule.", "conflicts": c.conflicts})
            except schedules.ScheduleError as e:
                return self._send(400, {"error": str(e)})
            path = "/api/run"
        if path == "/api/restart":
            if RUN["thread"] and RUN["thread"].is_alive():
                return self._send(409, {"error": "Wait for the scan to finish (or stop it) before restarting."})
            restart_soon()
            return self._send(200, {"restarting": True})
        if path == "/api/run/stop":
            pipeline.request_stop()
            RUN["lines"].append(f"{datetime.now():%H:%M:%S} Stopping… (finishing the current step)")
            return self._send(200, {"stopping": True})
        if path == "/api/run":
            if RUN["thread"] and RUN["thread"].is_alive():
                return self._send(409, {"error": "A scan is already running."})
            ids = body.get("profile_ids") or None
            if ids:
                with dbm.session() as conn:
                    off = [r["name"] for r in conn.execute(f"SELECT name FROM profiles WHERE active=0 AND id IN ({','.join('?' * len(ids))})", ids)]
                if off and len(off) == len(ids):
                    return self._send(400, {"error": f"“{off[0]}” is turned off. Turn the card on to run it."})
            RUN["lines"] = [f"{datetime.now():%H:%M:%S} Starting scan…"]
            def go():
                RUN["run_id"] = pipeline.run(body.get("trigger") if body.get("trigger") in ("retry",) else "manual", ids, progress=lambda m: RUN["lines"].append(f"{datetime.now():%H:%M:%S} {m}"),
                                             send=bool(body.get("send_email", True)))
            RUN["thread"] = threading.Thread(target=go, daemon=True)
            RUN["thread"].start()
            return self._send(200, {"started": True})

        if path == "/api/settings":
            s = _merge_settings(body)
            return self._send(200, {"settings": _redact(s)})
        m2 = re.fullmatch(r"/api/profiles/(\d+)/email-now", path)
        if m2:
            ok, msg = pipeline.email_current(int(m2.group(1)))
            return self._send(200 if ok else 400, {"ok": ok, "message": msg})
        if path == "/api/doctor":
            from .doctor import check
            return self._send(200, {"checks": check()})
        if path == "/api/test-email":
            from .report import send_email
            if body.get("email"):                      # use what's on screen, saving it first
                settings = _merge_settings({"email": body["email"]})
            to = body.get("to") or settings["email"].get("username")
            ok, msg = send_email(settings, to, "Job Radar test email",
                                 "<p>This is a test from Job Radar. If you can read this, daily job reports will reach this address.</p>",
                                 "This is a test from Job Radar. If you can read this, daily job reports will reach this address.")
            return self._send(200 if ok else 400, {"ok": ok, "message": (f"Test email sent to {to}." if ok else msg)})
        return self._send(404, {"error": "not found"})

    def do_DELETE(self):
        if not self._host_ok() or self.headers.get("X-JobRadar") != "1":
            return self._send(403, {"error": "forbidden"})
        m2 = re.fullmatch(r"/api/schedules/(\d+)", urlparse(self.path).path)
        if m2:
            with dbm.session() as conn:
                schedules.delete(conn, int(m2.group(1)))
            return self._send(200, {"ok": True})
        m = re.fullmatch(r"/api/profiles/(\d+)", urlparse(self.path).path)
        if m:
            with dbm.session() as conn:
                pid = int(m.group(1))
                cards.delete(conn, pid)
                conn.commit()
                schedules.sync_os(conn)
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})


def restart_soon():
    """Start a fresh copy of the app (which loads the updated code), then close this one."""
    import os, subprocess, sys
    from .config import ROOT
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen([sys.executable, "-m", "jobradar", "ui", "--no-browser", "--wait-port"], cwd=str(ROOT), creationflags=flags)
    def stop():
        if SERVER["httpd"]:
            SERVER["httpd"].shutdown()
            SERVER["httpd"].server_close()
        os._exit(0)
    threading.Timer(0.6, stop).start()


def serve(open_browser=True, wait_port=False):
    import time
    pipeline.setup_logging()
    port = load_settings().get("ui_port", 8765)
    url = f"http://127.0.0.1:{port}/"
    httpd = None
    for _ in range(40 if wait_port else 1):        # after a restart, wait for the old copy to let go of the port
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            time.sleep(0.5)
    if httpd is None:
        print(f"Job Radar is already running. Opening {url}")
        if open_browser:
            webbrowser.open(url)
        return
    SERVER["httpd"] = httpd
    try:
        with dbm.session() as conn:
            schedules.migrate_legacy(conn)
            cards._fix_stale(conn)
    except Exception:
        pipeline.log.exception("startup migration failed")
    print(f"Job Radar is running at {url}  (press Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
