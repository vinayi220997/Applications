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
from . import attachments, intake, pipeline, scheduler
from .config import REPORTS_DIR, load_settings, save_settings
from .freshness import classify
from .normalize import iso, now_utc
from .sources.ats import detect_board

STATIC = Path(__file__).parent / "static"
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

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "charset" not in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
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
                return self._send(200, {
                    "profiles": profile_rows(conn), "runs": runs, "schedule": scheduler.status(),
                    "running": bool(RUN["thread"] and RUN["thread"].is_alive()),
                    "settings": _redact(load_settings()),
                    "companies": {r["status"]: r["n"] for r in comp},
                    "update_ready": _code_mtime() > CODE_MTIME + 1})
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
                                           settings, body.get("transcript"))
                return self._send(200, rec)
            except attachments.AttachmentError as e:
                return self._send(400, {"error": str(e)})
        def items_for(ids):
            with dbm.session() as conn:
                return [a for a in (attachments.get(conn, i) for i in (ids or [])[:10]) if a]
        if path == "/api/intake/start":
            desc = (body.get("description") or "").strip()
            items = items_for(body.get("attachment_ids"))
            if len(desc) < 5 and not any(i.get("extracted") for i in items):
                return self._send(400, {"error": "Describe the job in a few more words, or attach a resume or job post with readable text."})
            return self._send(200, intake.start(desc, settings, items))
        if path == "/api/intake/attach":
            return self._send(200, intake.attach(body.get("state") or {}, items_for(body.get("attachment_ids"))))
        if path == "/api/intake/answer":
            return self._send(200, intake.answer(body.get("state") or {}, body.get("answer") or ""))

        with dbm.session() as conn:
            if path == "/api/profiles":
                p = intake.finalize(body.get("profile") or {})
                now = iso(now_utc())
                cur = conn.execute("""INSERT INTO profiles(name, email, email_on, active, description, profile_json, created_at, updated_at)
                                      VALUES (?,?,?,?,?,?,?,?)""",
                                   (p["name"], p.get("email"), 1, 1, p.get("description"), dbm.jdump(p), now, now))
                attachments.link(conn, p.get("attachment_ids"), cur.lastrowid)
                return self._send(200, {"id": cur.lastrowid})
            m = re.fullmatch(r"/api/profiles/(\d+)", path)
            if m:
                pid = int(m.group(1))
                for k in ("name", "email"):
                    if k in body:
                        conn.execute(f"UPDATE profiles SET {k}=?, updated_at=? WHERE id=?", (body[k], iso(now_utc()), pid))
                for k in ("active", "email_on"):
                    if k in body:
                        conn.execute(f"UPDATE profiles SET {k}=?, updated_at=? WHERE id=?", (1 if body[k] else 0, iso(now_utc()), pid))
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
            RUN["lines"] = [f"{datetime.now():%H:%M:%S} Starting scan…"]
            ids = body.get("profile_ids") or None
            def go():
                RUN["run_id"] = pipeline.run("manual", ids, progress=lambda m: RUN["lines"].append(f"{datetime.now():%H:%M:%S} {m}"),
                                             send=bool(body.get("send_email", True)))
            RUN["thread"] = threading.Thread(target=go, daemon=True)
            RUN["thread"].start()
            return self._send(200, {"started": True})
        if path == "/api/schedule":
            if body.get("enabled") is False:
                ok, msg = scheduler.remove()
            else:
                ok, msg = scheduler.install(body.get("time") or "08:00", body.get("days"), body.get("every_hours") or None)
            return self._send(200 if ok else 400, {"ok": ok, "message": msg, "schedule": scheduler.status()})
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
        m = re.fullmatch(r"/api/profiles/(\d+)", urlparse(self.path).path)
        if m:
            with dbm.session() as conn:
                pid = int(m.group(1))
                attachments.delete_for_profile(conn, pid)
                for t in ("profiles WHERE id=?", "matches WHERE profile_id=?", "notifications WHERE profile_id=?", "user_state WHERE profile_id=?"):
                    conn.execute("DELETE FROM " + t, (pid,))
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
    print(f"Job Radar is running at {url}  (press Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
