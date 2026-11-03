"""Offline tests (no network). Run: python -m unittest discover tests"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobradar import intake, freshness, dedupe, matching, normalize, verify  # noqa: E402
from jobradar.sources import ats  # noqa: E402
from jobradar.config import DEFAULT_SETTINGS  # noqa: E402

NOW = datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)
W = DEFAULT_SETTINGS["weights"]


def profile(**kw):
    p = intake.finalize({"roles": ["backend engineer", "software engineer"], "skills": ["python", "django", "aws"],
                         "experience": "3–5 years", "locations": ["Bengaluru"], "remote_international": True,
                         "work_arrangement": "any", "description": "x"})
    p.update(kw)
    return p


def job(**kw):
    j = {"source": "greenhouse", "source_job_id": "1", "company": "Acme", "title": "Backend Engineer",
         "location": "Bengaluru, India", "description": "We use Python, Django and AWS. 3+ years of experience required.",
         "is_ats": True, "apply_url": "https://boards.greenhouse.io/acme/jobs/1", "published_at": None}
    j.update(kw)
    return j


class Freshness(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(freshness.classify((NOW - timedelta(hours=23)).isoformat(), NOW), "24h")
        self.assertEqual(freshness.classify((NOW - timedelta(hours=50)).isoformat(), NOW), "3d")
        self.assertEqual(freshness.classify((NOW - timedelta(days=6)).isoformat(), NOW), "7d")
        self.assertEqual(freshness.classify((NOW - timedelta(days=20)).isoformat(), NOW), "older_active")

    def test_unknown_is_never_invented(self):
        self.assertEqual(freshness.classify(None, NOW), "unknown")
        self.assertEqual(freshness.classify("garbage", NOW), "unknown")
        self.assertEqual(freshness.classify((NOW + timedelta(days=5)).isoformat(), NOW), "unknown")

    def test_epoch_ms(self):
        ms = int((NOW - timedelta(hours=2)).timestamp() * 1000)
        self.assertEqual(freshness.classify(normalize.iso(normalize.parse_date(ms)), NOW), "24h")


class Parsing(unittest.TestCase):
    def test_description(self):
        p = intake.parse_description("Python backend developer, 4 years, Django and AWS, fintech, Bengaluru or remote, min 18 LPA")
        self.assertIn("python", p["skills"])
        self.assertIn("Bengaluru", p["locations"])
        self.assertEqual(p["work_arrangement"], "remote")
        self.assertIn("fintech", p["industries"])
        self.assertTrue(p["min_salary"].startswith("18"))

    def test_experience(self):
        self.assertEqual(normalize.experience_range("Requires 5-8 years of experience in Java"), (5, 8))
        self.assertEqual(normalize.experience_range("3+ years of professional experience"), (3, None))
        self.assertEqual(normalize.experience_range("Founded 20 years ago"), (None, None))
        self.assertEqual(normalize.parse_candidate_experience("3–5 years"), (3, 5))
        self.assertEqual(normalize.parse_candidate_experience("8+ years"), (8, 40))

    def test_salary(self):
        self.assertEqual(normalize.parse_lpa("18 LPA"), 18)
        self.assertEqual(normalize.parse_lpa("₹1800000"), 18)
        self.assertEqual(normalize.salary_from_source(1000000, 2000000, "INR"), (10.0, 20.0))

    def test_location(self):
        f = normalize.location_facts("Remote - US only")
        self.assertEqual(f["remote_scope"], "restricted")
        f = normalize.location_facts("Remote (Worldwide)")
        self.assertEqual(f["remote_scope"], "global")
        f = normalize.location_facts("Bangalore, Karnataka, India")
        self.assertTrue(f["in_india"])
        self.assertEqual(f["cities"], ["bengaluru"])

    def test_board_detection(self):
        self.assertEqual(ats.detect_board("https://jobs.lever.co/acme/123"), ("lever", "acme"))
        self.assertEqual(ats.detect_board("https://job-boards.greenhouse.io/postman"), ("greenhouse", "postman"))
        self.assertEqual(ats.detect_board("https://jobs.ashbyhq.com/notion"), ("ashby", "notion"))
        self.assertIsNone(ats.detect_board("https://www.linkedin.com/jobs/view/1"))


class Intake(unittest.TestCase):
    def test_asks_for_missing_items_then_finishes(self):
        r = intake.start("I want a backend engineer job using python")
        asked = []
        answers = {"roles": "yes", "experience": "3–5 years", "locations": "Bengaluru, Hyderabad",
                   "remote_international": "Yes", "work_arrangement": "Hybrid", "skills": "python, django",
                   "min_salary": "skip", "exclude": "skip", "email": "me@example.com", "name": "Backend search"}
        while not r["done"]:
            k = r["state"]["pending"]
            asked.append(k)
            r = intake.answer(r["state"], answers[k])
        for k in ("experience", "locations", "work_arrangement", "remote_international"):
            self.assertIn(k, asked)
        p = r["profile"]
        self.assertEqual((p["exp_min"], p["exp_max"]), (3, 5))
        self.assertEqual(p["locations"], ["Bengaluru", "Hyderabad"])
        self.assertEqual(p["email"], "me@example.com")
        self.assertEqual(p["skills"], ["python", "django"])

    def test_skips_known_answers(self):
        r = intake.start("Data analyst, 2 years, SQL and Power BI, Pune, hybrid")
        asked = []
        while not r["done"]:
            k = r["state"]["pending"]; asked.append(k)
            r = intake.answer(r["state"], {"min_salary": "skip", "exclude": "skip", "email": "skip", "name": "DA", "work_arrangement": "Any"}.get(k, "yes"))
        self.assertNotIn("experience", asked)
        self.assertNotIn("locations", asked)
        self.assertNotIn("work_arrangement", asked)

    def test_bad_email_is_asked_again(self):
        keys = [q["key"] for q in intake.QUESTIONS]
        st = {"profile": {"roles": ["x"]}, "asked": keys[:keys.index("email") + 1], "pending": "email"}
        r = intake.answer(st, "not an email")
        self.assertEqual(r["state"]["pending"], "email")
        self.assertIn("doesn't look like an email", r["question"])


class Matching(unittest.TestCase):
    def test_good_match(self):
        m = matching.score_job(job(), profile(), W)
        self.assertTrue(m["eligible"])
        self.assertGreaterEqual(m["score"], 80)
        self.assertTrue(any("python" in r for r in m["reasons"]))

    def test_irrelevant_title(self):
        self.assertFalse(matching.score_job(job(title="Account Executive"), profile(), W)["eligible"])

    def test_location_outside_cities(self):
        m = matching.score_job(job(location="Mumbai, India"), profile(), W)
        self.assertFalse(m["eligible"])

    def test_remote_restricted(self):
        m = matching.score_job(job(location="Remote - USA only"), profile(), W)
        self.assertFalse(m["eligible"])

    def test_remote_global_ok_only_if_international(self):
        self.assertTrue(matching.score_job(job(location="Remote (Worldwide)"), profile(), W)["eligible"])
        self.assertFalse(matching.score_job(job(location="Remote (Worldwide)"), profile(remote_international=False), W)["eligible"])

    def test_experience_too_high(self):
        m = matching.score_job(job(description="Python Django AWS. 10+ years of experience required."), profile(), W)
        self.assertFalse(m["eligible"])

    def test_seniority(self):
        self.assertFalse(matching.score_job(job(title="Principal Backend Engineer"), profile(), W)["eligible"])

    def test_salary_floor(self):
        p = profile(min_salary_lpa=30)
        self.assertFalse(matching.score_job(job(salary_max_lpa=20), p, W)["eligible"])
        m = matching.score_job(job(), p, W)            # unknown salary is not a fail
        self.assertTrue(m["eligible"])
        self.assertTrue(any("Salary not stated" in g for g in m["gaps"]))

    def test_unmentioned_skill_is_uncertain_not_missing_from_candidate(self):
        m = matching.score_job(job(description="Python and Kubernetes. 3+ years of experience."), profile(), W)
        self.assertTrue(any("not established" in g for g in m["gaps"]))


class Dedupe(unittest.TestCase):
    def test_merges_aggregator_into_ats(self):
        a = job()
        b = job(source="remotive", source_job_id="9", is_ats=False, apply_url="https://remotive.com/x", source_name="Remotive")
        out = dedupe.cluster([b, a])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "greenhouse")
        self.assertEqual(len(out[0]["also_seen_on"]), 1)

    def test_keeps_distinct_requisitions(self):
        a = job(source_job_id="1", apply_url="https://x/1")
        b = job(source_job_id="2", apply_url="https://x/2")
        self.assertEqual(len(dedupe.cluster([a, b])), 2)


class Verify(unittest.TestCase):
    def test_closed_phrase(self):
        with mock.patch("jobradar.verify.fetch", return_value=(200, "https://x.com/jobs/1", "<h1>This position is no longer available</h1>")):
            self.assertEqual(verify.check("https://x.com/jobs/1", "Backend Engineer")[0], "closed")

    def test_redirect_to_home(self):
        with mock.patch("jobradar.verify.fetch", return_value=(200, "https://x.com/careers", "<h1>Careers</h1>")):
            self.assertEqual(verify.check("https://x.com/jobs/123", "Backend Engineer")[0], "unable_to_verify")

    def test_ok(self):
        with mock.patch("jobradar.verify.fetch", return_value=(200, "https://x.com/jobs/1", "<h1>Backend Engineer</h1><button>Apply</button>")):
            self.assertEqual(verify.check("https://x.com/jobs/1", "Backend Engineer")[0], "appears_active")


class Pipeline(unittest.TestCase):
    """End-to-end with fake connectors and a temporary database."""

    def test_run_twice_no_duplicate_alerts_and_closure(self):
        tmp = Path(tempfile.mkdtemp())
        import jobradar.config as cfg
        import jobradar.db as dbm
        import jobradar.pipeline as pl
        patches = [mock.patch.object(cfg, "DATA_DIR", tmp), mock.patch.object(dbm, "DB_PATH", tmp / "t.db"),
                   mock.patch.object(pl, "DATA_DIR", tmp), mock.patch.object(pl, "LOCK", tmp / "lock"),
                   mock.patch.object(pl, "REPORTS_DIR", tmp), mock.patch.object(cfg, "LOG_PATH", tmp / "log"),
                   mock.patch.object(pl, "LOG_PATH", tmp / "log"),
                   mock.patch.object(pl, "online", return_value=True),
                   mock.patch.object(pl, "load_company_candidates", return_value=[{"ats": "greenhouse", "token": "acme"}])]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        recent = normalize.iso(normalize.now_utc() - timedelta(hours=3))
        feed = {"jobs": [job(source_job_id="1", published_at=recent, board="greenhouse:acme"),
                         job(source_job_id="2", title="Senior Backend Engineer", apply_url="https://x/2", board="greenhouse:acme")]}
        with mock.patch.dict(pl.ats.CONNECTORS, {"greenhouse": lambda t, timeout: ("Acme", [dict(j) for j in feed["jobs"]])}), \
             mock.patch.dict(pl.boards.BOARDS, {}, clear=True), \
             mock.patch.object(pl, "load_settings", return_value=json.loads(json.dumps(DEFAULT_SETTINGS))):
            with dbm.session() as conn:
                p = profile()
                conn.execute("INSERT INTO profiles(name,email,email_on,active,profile_json) VALUES ('t','',1,1,?)", (json.dumps(p),))
            rid = pl.run("test", progress=lambda m: None)
            with dbm.session() as conn:
                s1 = json.loads(conn.execute("SELECT summary_json FROM runs WHERE id=?", (rid,)).fetchone()[0])
            self.assertEqual(list(s1.values())[0]["reported"], 2)
            # second run: unchanged -> nothing new
            rid2 = pl.run("test", progress=lambda m: None)
            with dbm.session() as conn:
                s2 = json.loads(conn.execute("SELECT summary_json FROM runs WHERE id=?", (rid2,)).fetchone()[0])
            self.assertEqual(list(s2.values())[0]["reported"], 0)
            # third run: job 2 removed from the employer feed -> closed
            feed["jobs"] = feed["jobs"][:1]
            pl.run("test", progress=lambda m: None)
            with dbm.session() as conn:
                st = conn.execute("SELECT status, closed_at FROM jobs WHERE id='greenhouse:2'").fetchone()
            self.assertEqual(st["status"], "closed")
            self.assertIsNotNone(st["closed_at"])


if __name__ == "__main__":
    unittest.main()


class Attachments(unittest.TestCase):
    def setUp(self):
        import sqlite3
        import jobradar.attachments as att
        self.att = att
        self.tmp = Path(tempfile.mkdtemp())
        self.p = mock.patch.object(att, "ATT_DIR", self.tmp)
        self.p.start()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.p.stop()
        self.conn.close()

    def _b64(self, raw):
        import base64
        return base64.b64encode(raw).decode()

    def test_text_resume(self):
        raw = ("Rahul K\nSenior Python Developer\nPROFILE SUMMARY\n5 years of experience in Django, AWS and React.\n"
               "SKILLS\nPython, Django, AWS, React\nEDUCATION\nB.E.").encode()
        r = self.att.save(self.conn, "resume.txt", "text/plain", self._b64(raw), {})
        self.assertEqual(r["doc_type"], "resume")
        self.assertIn("django", r["extracted"]["skills"])
        self.assertEqual(r["extracted"]["experience"], "5–7 years")

    def test_docx_job_post(self):
        raw = Path("/tmp/fx/jd.docx").read_bytes() if Path("/tmp/fx/jd.docx").exists() else None
        if raw is None:
            self.skipTest("fixture missing")
        r = self.att.save(self.conn, "jd.docx", "", self._b64(raw), {})
        self.assertEqual(r["doc_type"], "job_post")
        self.assertIn("spark", r["extracted"]["skills"])
        self.assertIn("Pune", r["extracted"]["locations"])

    def test_pdf_resume(self):
        f = Path("/tmp/fx/resume.pdf")
        if not f.exists():
            self.skipTest("fixture missing")
        r = self.att.save(self.conn, "resume.pdf", "application/pdf", self._b64(f.read_bytes()), {})
        self.assertTrue(r["has_text"])
        self.assertEqual(r["doc_type"], "resume")
        self.assertIn("kafka", r["extracted"]["skills"])

    def test_image_without_key_is_saved_with_note(self):
        png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
        r = self.att.save(self.conn, "shot.png", "image/png", self._b64(png), {"anthropic": {}})
        self.assertFalse(r["has_text"])
        self.assertTrue(r["problem"])               # never claims the image was read
        self.assertRegex(r["note"], r"Couldn't read text|no OCR engine")

    def test_voice_uses_transcript(self):
        r = self.att.save(self.conn, "voice.webm", "audio/webm", self._b64(b"\x1aE\xdf\xa3fake"), {},
                          transcript="I want a data analyst job in Hyderabad with SQL and Tableau, 2 years")
        self.assertIn("sql", r["extracted"]["skills"])
        self.assertIn("Hyderabad", r["extracted"]["locations"])

    def test_rejects_unknown_type(self):
        with self.assertRaises(self.att.AttachmentError):
            self.att.save(self.conn, "virus.exe", "application/octet-stream", self._b64(b"MZ"), {})

    def test_intake_with_resume_skips_known_questions(self):
        item = {"id": "a1", "doc_type": "resume", "note": "From your resume…",
                "extracted": {"roles": ["backend developer"], "skills": ["python", "django"], "experience": "4–6 years", "locations": ["Bengaluru"]}}
        r = intake.start("", {}, [item])
        asked = []
        while not r["done"]:
            k = r["state"]["pending"]; asked.append(k)
            r = intake.answer(r["state"], {"min_salary": "skip", "exclude": "skip", "email": "skip", "name": "x", "work_arrangement": "Any"}.get(k, "yes"))
        self.assertNotIn("experience", asked)
        self.assertNotIn("locations", asked)
        self.assertEqual(r["profile"]["attachment_ids"], ["a1"])

    def test_attach_mid_conversation_answers_pending_question(self):
        r = intake.start("backend developer python")
        while r["state"]["pending"] != "experience":
            r = intake.answer(r["state"], "yes")
        r = intake.attach(r["state"], [{"id": "a2", "doc_type": "resume", "note": "n", "extracted": {"experience": "4–6 years"}}])
        self.assertNotEqual(r["state"]["pending"], "experience")
        self.assertEqual(r["state"]["profile"]["experience"], "4–6 years")


class EmailDelivery(unittest.TestCase):
    """Jobs must not be marked as sent when the email never went out."""

    def test_unsent_jobs_go_out_once_email_works(self):
        tmp = Path(tempfile.mkdtemp())
        import jobradar.config as cfg
        import jobradar.db as dbm
        import jobradar.pipeline as pl
        settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        patches = [mock.patch.object(cfg, "DATA_DIR", tmp), mock.patch.object(dbm, "DB_PATH", tmp / "t.db"),
                   mock.patch.object(pl, "DATA_DIR", tmp), mock.patch.object(pl, "LOCK", tmp / "lock"),
                   mock.patch.object(pl, "REPORTS_DIR", tmp), mock.patch.object(pl, "LOG_PATH", tmp / "log"),
                   mock.patch.object(pl, "online", return_value=True),
                   mock.patch.object(pl, "load_company_candidates", return_value=[{"ats": "greenhouse", "token": "acme"}]),
                   mock.patch.dict(pl.ats.CONNECTORS, {"greenhouse": lambda t, timeout: ("Acme", [job(source_job_id="1", board="greenhouse:acme")])}),
                   mock.patch.dict(pl.boards.BOARDS, {}, clear=True),
                   mock.patch.object(pl, "load_settings", side_effect=lambda: settings)]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        with dbm.session() as conn:
            conn.execute("INSERT INTO profiles(name,email,email_on,active,profile_json) VALUES ('t','me@x.com',1,1,?)", (json.dumps(profile()),))
        # 1st run: email not configured -> not sent, not marked
        rid = pl.run("t", progress=lambda m: None)
        with dbm.session() as conn:
            s1 = list(json.loads(conn.execute("SELECT summary_json FROM runs WHERE id=?", (rid,)).fetchone()[0]).values())[0]
            self.assertFalse(s1["email_sent"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)
        # 2nd run: email works -> the same job is sent now
        sent = []
        import jobradar.mailer as mailer
        p2 = mock.patch.object(mailer, "SECRETS", tmp / "secrets.json"); p2.start(); self.addCleanup(p2.stop)
        with dbm.session() as conn:
            settings["mail"]["default_account"] = mailer.add_account(conn, "a@gmail.com", "abcdabcdabcdabcd", test=False)
        with mock.patch.object(mailer, "_send_one", side_effect=lambda a, pw, rec, subj, h, t, fn: (sent.append((rec["to"], subj)) or ("sent", "<id@x>", 0, None))):
            rid = pl.run("t", progress=lambda m: None)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], ["me@x.com"])
        self.assertIn("Daily Job Opportunities", sent[0][1])
        # email-now sends all open matches even though they were reported
        with mock.patch.object(mailer, "_send_one", return_value=("sent", "<id@x>", 0, None)):
            ok, msg = pl.email_current(1)
        self.assertTrue(ok)
        self.assertIn("Email sent from a@gmail.com", msg)
        with mock.patch.object(mailer, "_send_one", return_value=("sent", "<id@x>", 0, None)) as m2:
            ok2, msg2 = pl.email_current(1)                  # pressed twice within a minute: not sent twice
        self.assertFalse(ok2)
        self.assertEqual(m2.call_count, 0)


class SmtpBehaviour(unittest.TestCase):
    def cfg(self):
        return {"email": {"enabled": True, "username": "me@gmail.com", "app_password": "abcd efgh ijkl mnop"}}

    def test_strips_spaces_and_sends(self):
        from jobradar import report
        inst = mock.MagicMock()
        with mock.patch("smtplib.SMTP") as S:
            S.return_value.__enter__.return_value = inst
            ok, _ = report.send_email(self.cfg(), "vinay@example.com", "s", "<p>h</p>", "t")
        self.assertTrue(ok)
        inst.login.assert_called_with("me@gmail.com", "abcdefghijklmnop")
        self.assertEqual(inst.sendmail.call_args[0][1], ["vinay@example.com"])

    def test_falls_back_to_465(self):
        from jobradar import report
        inst = mock.MagicMock()
        with mock.patch("smtplib.SMTP", side_effect=OSError("blocked")), mock.patch("smtplib.SMTP_SSL") as SS:
            SS.return_value.__enter__.return_value = inst
            ok, _ = report.send_email(self.cfg(), "v@example.com", "s", "h", "t")
        self.assertTrue(ok)
        self.assertEqual(SS.call_args[0][1], 465)

    def test_bad_password_message(self):
        import smtplib
        from jobradar import report
        inst = mock.MagicMock()
        inst.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad")
        with mock.patch("smtplib.SMTP") as S:
            S.return_value.__enter__.return_value = inst
            ok, msg = report.send_email(self.cfg(), "v@example.com", "s", "h", "t")
        self.assertFalse(ok)
        self.assertIn("app password", msg)


class WindowsTimezone(unittest.TestCase):
    def test_report_works_without_tz_database(self):
        import zoneinfo
        from jobradar import report
        def boom(*a, **k):
            raise zoneinfo.ZoneInfoNotFoundError("no tzdata")
        with mock.patch.object(report, "ZoneInfo", boom):
            tz = report._tz({"timezone": "Asia/Kolkata"})
            self.assertEqual(tz.utcoffset(None), timedelta(hours=5, minutes=30))
            html = report.build({"name": "x", "summary": ""}, {"top24": [job(score=80, freshness="24h", published_at="2026-10-10T00:00:00Z")]},
                                {"sources_configured": 1, "sources_scanned": 1, "retrieved": 1, "unique": 1, "new": 1, "recent": 1, "verified": 1, "high": 1},
                                [], [], {"timezone": "Asia/Kolkata"})
        self.assertIn("Backend Engineer", html)



class ChatUnderstanding(unittest.TestCase):
    """Replays the conversation from Dilip's screenshot plus edits after the summary."""
    ITEM = {"id": "a", "doc_type": "resume", "note": "n", "extracted": {"roles": ["ui designer", "ui/ux designer"],
            "skills": ["css", "figma", "seo"], "locations": ["Visakhapatnam"]}}

    def test_add_location_while_titles_asked(self):
        r = intake.start("", {}, [self.ITEM])
        self.assertEqual(r["state"]["pending"], "roles")
        r = intake.answer(r["state"], "also add location")
        self.assertIn("Which cities", r["question"])
        r = intake.answer(r["state"], "Bengaluru and Hyderabad")
        self.assertEqual(r["state"]["profile"]["locations"], ["Visakhapatnam", "Bengaluru", "Hyderabad"])
        self.assertEqual(r["state"]["profile"]["roles"], ["ui designer", "ui/ux designer"])
        self.assertEqual(r["state"]["pending"], "roles")           # comes back to the open question

    def test_side_answers_do_not_overwrite_open_question(self):
        r = intake.start("", {}, [self.ITEM])
        r = intake.answer(r["state"], "yes")
        self.assertEqual(r["state"]["pending"], "experience")
        r = intake.answer(r["state"], "min salary 6 LPA")
        self.assertEqual(r["state"]["profile"]["min_salary"], "6 LPA")
        self.assertEqual(r["state"]["pending"], "experience")
        r = intake.answer(r["state"], "3-5 years")
        self.assertEqual(r["state"]["profile"]["experience"], "3-5 years")

    def test_edits_after_summary(self):
        r = intake.start("UI designer, figma, 3 years, Pune, hybrid", {})
        while not r["done"]:
            r = intake.answer(r["state"], {"min_salary": "skip", "exclude": "skip", "email": "skip", "name": "x"}.get(r["state"]["pending"], "yes"))
        r = intake.answer(r["state"], "add Chennai")
        self.assertIn("Chennai", r["profile"]["locations"])
        r = intake.answer(r["state"], "remove figma skill")
        self.assertNotIn("figma", r["profile"]["skills"])
        r = intake.answer(r["state"], "make it remote")
        self.assertEqual(r["profile"]["work_arrangement"], "remote")
        self.assertTrue(r["done"])

    def test_bad_arrangement_is_asked_again(self):
        st = {"profile": {"roles": ["x"]}, "asked": [q["key"] for q in intake.QUESTIONS][:5], "pending": "work_arrangement"}
        r = intake.answer(st, "yes")
        self.assertEqual(r["state"]["pending"], "work_arrangement")
        self.assertIn("Hybrid, Remote, Onsite, or Any", r["question"])


class StopScan(unittest.TestCase):
    def test_stop_marks_run_stopped_and_sends_nothing(self):
        tmp = Path(tempfile.mkdtemp())
        import jobradar.config as cfg
        import jobradar.db as dbm
        import jobradar.pipeline as pl
        def slow_board(t, timeout):
            pl.request_stop()                 # the person presses Stop while boards are being read
            return ("Acme", [job(source_job_id="1", board="greenhouse:acme")])
        patches = [mock.patch.object(cfg, "DATA_DIR", tmp), mock.patch.object(dbm, "DB_PATH", tmp / "t.db"),
                   mock.patch.object(pl, "DATA_DIR", tmp), mock.patch.object(pl, "LOCK", tmp / "lock"), mock.patch.object(pl, "CANCEL", tmp / "cancel"),
                   mock.patch.object(pl, "REPORTS_DIR", tmp), mock.patch.object(pl, "LOG_PATH", tmp / "log"),
                   mock.patch.object(pl, "online", return_value=True),
                   mock.patch.object(pl, "load_company_candidates", return_value=[{"ats": "greenhouse", "token": "acme"}, {"ats": "greenhouse", "token": "b"}]),
                   mock.patch.dict(pl.ats.CONNECTORS, {"greenhouse": slow_board}), mock.patch.dict(pl.boards.BOARDS, {}, clear=True)]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        with dbm.session() as conn:
            conn.execute("INSERT INTO profiles(name,email,email_on,active,profile_json) VALUES ('t','me@x.com',1,1,?)", (json.dumps(profile()),))
        with mock.patch.object(pl.report, "send_email") as send:
            rid = pl.run("t", progress=lambda m: None)
        send.assert_not_called()
        with dbm.session() as conn:
            self.assertEqual(conn.execute("SELECT status FROM runs WHERE id=?", (rid,)).fetchone()[0], "stopped")
        self.assertFalse((tmp / "cancel").exists())
        self.assertFalse((tmp / "lock").exists())


class ChatSpellingAndValues(unittest.TestCase):
    ITEM = {"id": "a", "doc_type": "resume", "note": "n", "extracted": {"roles": ["ui designer", "ui/ux designer"],
            "skills": ["css", "figma"], "locations": ["Visakhapatnam"]}}

    def test_misspelt_city_while_titles_asked(self):
        r = intake.start("", {}, [self.ITEM])
        r = intake.answer(r["state"], "add bengular")
        p = r["state"]["profile"]
        self.assertEqual(p["roles"], ["ui designer", "ui/ux designer"])
        self.assertEqual(p["locations"], ["Visakhapatnam", "Bengaluru"])
        self.assertIn("read 'bengular' as Bengaluru", r["question"])

    def test_short_forms(self):
        r = intake.start("", {}, [self.ITEM])
        r = intake.answer(r["state"], "add hyd and vizag and banglore")
        self.assertEqual(r["state"]["profile"]["locations"], ["Visakhapatnam", "Hyderabad", "Bengaluru"])

    def test_non_title_is_not_added_as_title(self):
        r = intake.start("", {}, [self.ITEM])
        r = intake.answer(r["state"], "xyzabc")
        self.assertEqual(r["state"]["profile"]["roles"], ["ui designer", "ui/ux designer"])
        self.assertIn("doesn't look like a job title", r["question"])

    def test_salary_number_means_lpa(self):
        st = {"profile": {"roles": ["x"]}, "asked": [q["key"] for q in intake.QUESTIONS][:7], "pending": "min_salary"}
        r = intake.answer(st, "7")
        self.assertEqual(r["state"]["profile"]["min_salary"], "7 LPA")

    def test_unknown_city_added_when_called_a_city(self):
        r = intake.start("", {}, [self.ITEM])
        r = intake.answer(r["state"], "add city Kakinada")
        self.assertIn("Kakinada", r["state"]["profile"]["locations"])


class ReviewAndEdit(unittest.TestCase):
    """Updats 1: answer confirmation data, progress, section edits with overwrite/add/edit, samples, AI/OCR status."""
    def _state(self):
        from jobradar import intake
        r = intake.start("Product designer, Figma, 4 years, Bengaluru", {})
        return intake, r

    def test_progress_counts_and_current(self):
        intake, r = self._state()
        pr = intake.progress(r["state"])
        self.assertEqual(pr["total"], 10)
        self.assertEqual(pr["steps"][pr["current"] - 1]["key"], r["state"]["pending"])
        self.assertTrue(all(s["status"] in ("done", "current", "pending") for s in pr["steps"]))

    def test_changes_diff(self):
        from jobradar.intake import changes
        c = changes({"locations": ["Pune"]}, {"locations": ["Pune", "Chennai"], "email": "a@b.co"})
        self.assertEqual([x["key"] for x in c], ["locations", "email"])
        self.assertEqual(c[0]["old"], "Pune")

    def test_set_field_modes(self):
        intake, r = self._state()
        st = r["state"]
        add = intake.set_field(st, "locations", "hyd, bengular", "add")
        self.assertEqual(add["state"]["profile"]["locations"], ["Bengaluru", "Hyderabad"])
        over = intake.set_field(st, "locations", "Chennai", "overwrite")
        self.assertEqual(over["state"]["profile"]["locations"], ["Chennai"])
        edit = intake.set_field(add["state"], "locations", "Pune", "edit", items=["Hyderabad"])
        self.assertEqual(edit["state"]["profile"]["locations"], ["Hyderabad", "Pune"])
        self.assertEqual(st["profile"]["locations"], ["Bengaluru"])          # original untouched until confirmed
        self.assertEqual(add["state"]["pending"], st["pending"])             # the open question stays open

    def test_set_field_validation(self):
        intake, r = self._state()
        self.assertTrue(intake.set_field(r["state"], "email", "not-an-email")["error"])
        self.assertTrue(intake.set_field(r["state"], "work_arrangement", "sometimes")["error"])
        self.assertEqual(intake.set_field(r["state"], "min_salary", "12")["state"]["profile"]["min_salary"], "12 LPA")
        self.assertIs(intake.set_field(r["state"], "remote_international", "No")["state"]["profile"]["remote_international"], False)

    def test_edit_after_done_returns_profile(self):
        from jobradar import intake
        st = {"profile": {"roles": ["data analyst"], "locations": ["Pune"], "experience": "3 years", "skills": ["sql"],
                          "work_arrangement": "any", "remote_international": False, "name": "x"},
              "asked": [q["key"] for q in intake.QUESTIONS], "pending": None}
        r = intake.set_field(st, "skills", "tableau", "add")
        self.assertTrue(r["done"])
        self.assertEqual(r["profile"]["skills"], ["sql", "tableau"])

    def test_brief_sample_is_understood(self):
        from jobradar.intake import parse_brief
        txt = (Path(__file__).parent.parent / "jobradar" / "static" / "samples" / "job-search-brief.txt").read_text(encoding="utf-8")
        b = parse_brief(txt)
        self.assertIn("product designer", b["roles"])
        self.assertIn("ux designer", b["roles"])
        self.assertEqual(b["work_arrangement"], "hybrid")
        self.assertEqual(b["min_salary"], "14 LPA")
        self.assertIsNone(parse_brief("I like python. Location: Pune"))

    def test_all_samples_exist(self):
        d = Path(__file__).parent.parent / "jobradar" / "static" / "samples"
        for f in ("job-search-brief.txt", "sample-resume.docx", "sample-job-post.txt", "sample-job-post.png", "sample-voice.mp3"):
            self.assertTrue((d / f).exists(), f)

    def test_services_offline_status_is_honest(self):
        from jobradar import services
        with mock.patch.object(services, "engines_available", return_value=[]):
            s = services.status({"anthropic": {"api_key": ""}, "ai": {"enabled": True}, "ocr": {"enabled": True}})
        self.assertEqual(s["mode"], "offline")
        self.assertEqual(s["ai"]["state"], "not_configured")
        self.assertEqual(s["ocr"]["state"], "not_configured")
        with mock.patch.object(services, "engines_available", return_value=[]):
            txt, eng, note = services.ocr_image(b"x", ".png", "image/png", {"ocr": {"enabled": True}})
        self.assertIsNone(txt); self.assertIsNone(eng); self.assertIn("no OCR engine", note)

    def test_ocr_disabled_never_reads(self):
        from jobradar import services
        txt, eng, note = services.ocr_image(b"x", ".png", "image/png", {"ocr": {"enabled": False}})
        self.assertIsNone(txt)
        self.assertIn("turned off", note)

    def test_key_hint_never_full_key(self):
        from jobradar import services
        s = services.status({"anthropic": {"api_key": "sk-ant-abcdefghijklmnop1234"}, "ai": {"enabled": True}, "ocr": {"enabled": False}})
        self.assertEqual(s["ai"]["key_hint"], "…1234")
        self.assertNotIn("abcdefgh", json.dumps(s))

    def test_ai_test_without_key(self):
        from jobradar import services
        self.assertFalse(services.test_ai({"anthropic": {"api_key": ""}})["ok"])


class CardsSchedulesHistory(unittest.TestCase):
    """v1.6: multi work modes, cards, export/import, schedules and execution/email history."""
    def setUp(self):
        import sqlite3
        import jobradar.db as dbm
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(dbm.SCHEMA)
        dbm._migrate(self.conn)
        from jobradar import mailer
        mailer.migrate(self.conn)
        from jobradar import cards, schedules
        self.cards, self.S = cards, schedules
        self.p = [mock.patch.object(schedules.scheduler, "install_task", return_value=(True, "ok")),
                  mock.patch.object(schedules.scheduler, "remove_task"),
                  mock.patch.object(schedules.scheduler, "installed_ids", return_value=set())]
        for x in self.p:
            x.start()
        self.addCleanup(lambda: [x.stop() for x in self.p])

    def _card(self, name="DA", **kw):
        prof = {"roles": ["data analyst"], "name": name, "locations": ["Pune", "Hyderabad"], "work_modes": ["hybrid", "remote"],
                "experience": "3-5 years", "skills": ["sql"]}
        prof.update(kw)
        pid, _ = self.cards.create(self.conn, prof, "questionnaire", ["manual", "file"], "me@x.com")
        return pid

    def test_multi_modes_saved_and_matched(self):
        from jobradar.matching import score_job
        pid = self._card()
        p = json.loads(self.conn.execute("SELECT profile_json FROM profiles WHERE id=?", (pid,)).fetchone()[0])
        self.assertEqual(p["work_modes"], ["hybrid", "remote"])
        self.assertEqual(p["work_arrangement"], "hybrid, remote")
        onsite = profile(work_modes=["remote"])
        m = score_job(job(location="Bengaluru, India"), onsite, settings_weights())
        self.assertTrue(any("Not a fully remote" in g for g in m["gaps"]))
        both = profile(work_modes=["hybrid", "onsite"])
        m2 = score_job(job(location="Remote - India", description="Fully remote role open to candidates in India. Python, Django, AWS."), both, settings_weights())
        self.assertTrue(any("Role is remote" in g for g in m2["gaps"]))

    def test_card_list_status_and_toggle(self):
        pid = self._card()
        c = next(x for x in self.cards.card_list(self.conn) if x["id"] == pid)
        self.assertEqual(c["status"], "Not Started")
        self.assertEqual(c["input_mode"], "questionnaire")
        self.assertEqual(c["schedule_status"], "Not Scheduled")
        self.cards.set_flag(self.conn, pid, "active", False)
        c = next(x for x in self.cards.card_list(self.conn) if x["id"] == pid)
        self.assertEqual(c["status"], "Disabled")
        kinds = [a["kind"] for a in self.cards.history(self.conn, pid)["activity"]]
        self.assertIn("disabled", kinds)
        self.assertIn("created", kinds)

    def test_update_keeps_history_and_no_duplicate(self):
        pid = self._card()
        n = self.conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        changed = self.cards.update(self.conn, pid, {"roles": ["data analyst"], "name": "DA", "locations": ["Chennai"], "experience": "3-5 years"}, "chart")
        self.assertIn("Locations", changed)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0], n)
        self.assertEqual(self.conn.execute("SELECT input_mode FROM profiles WHERE id=?", (pid,)).fetchone()[0], "chart")
        self.assertEqual(len(self.cards.history(self.conn, pid)["activity"]), 2)

    def test_export_has_no_secrets_and_imports(self):
        pid = self._card()
        data = self.cards.export(self.conn, pid)
        blob = json.dumps(data)
        self.assertNotIn("me@x.com", blob)                     # email only when asked
        for bad in ('"password"', '"api_key"', '"app_password"', '"anthropic"', '"smtp'):
            self.assertNotIn(bad, blob)
        self.assertEqual(data["format"], "jobradar.card")
        self.assertIn("me@x.com", json.dumps(self.cards.export(self.conn, pid, include_email=True)))
        new, warns, _ = self.cards.do_import(self.conn, data, "new")
        self.assertNotEqual(new, pid)
        self.assertEqual(self.conn.execute("SELECT input_mode FROM profiles WHERE id=?", (new,)).fetchone()[0], "questionnaire")
        upd, _, _ = self.cards.do_import(self.conn, data, "update", pid)
        self.assertEqual(upd, pid)
        self.assertTrue(any(a["kind"] == "imported" for a in self.cards.history(self.conn, pid)["activity"]))

    def test_import_validation(self):
        with self.assertRaises(self.cards.CardError):
            self.cards.check_import({"format": "other"})
        with self.assertRaisesRegex(self.cards.CardError, "newer"):
            self.cards.check_import({"format": "jobradar.card", "version": 7, "card": {"answers": {"roles": ["x"]}}})
        with self.assertRaisesRegex(self.cards.CardError, "job titles"):
            self.cards.check_import({"format": "jobradar.card", "version": 1, "card": {"answers": {"skills": ["x"]}}})
        card, w = self.cards.check_import({"format": "jobradar.card", "version": 1, "card": {"answers": {"roles": ["x"], "app_password": "y"}}})
        self.assertNotIn("app_password", card["answers"])
        self.assertTrue(w)

    def test_duplicate_starts_off(self):
        pid = self._card()
        new = self.cards.duplicate(self.conn, pid)
        r = self.conn.execute("SELECT name, active FROM profiles WHERE id=?", (new,)).fetchone()
        self.assertEqual((r[0], r[1]), ("DA (copy)", 0))

    def test_schedule_timing_and_text(self):
        from datetime import datetime, timezone
        s = {"enabled": True, "frequency": "weekly", "time": "18:00", "days": ["MON", "WED", "FRI"], "timezone": "Asia/Kolkata"}
        nxt = self.S.next_run(s, datetime(2026, 10, 11, 6, 0, tzinfo=timezone.utc))      # Sunday 11:30 IST
        self.assertEqual(nxt.astimezone(self.S.tz("Asia/Kolkata")).strftime("%a %H:%M"), "Mon 18:00")
        self.assertEqual(self.S.describe(s), "Mon, Wed, Fri at 6:00 PM (India (IST))")
        h = {"enabled": True, "frequency": "hourly", "time": "08:00", "days": self.S.DAYS, "every_hours": 6, "timezone": "Asia/Kolkata"}
        occ = self.S.occurrences(h, datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc), datetime(2026, 10, 11, 18, 29, tzinfo=timezone.utc))
        self.assertEqual([o.strftime("%H:%M") for o in occ], ["08:00", "14:00", "20:00"])
        self.assertIsNone(self.S.next_run(dict(s, enabled=False)))

    def test_schedule_conflicts_and_runs(self):
        a, b = self._card("A"), self._card("B")
        sid, _ = self.S.save(self.conn, {"name": "Morning", "time": "09:00", "card_ids": [a, b]})
        with self.assertRaises(self.S.Conflict):
            self.S.save(self.conn, {"name": "Evening", "time": "18:00", "card_ids": [a]})
        sid2, confl = self.S.save(self.conn, {"name": "Evening", "time": "18:00", "card_ids": [a], "confirm_duplicates": True})
        self.assertEqual(confl[0]["card_id"], a)
        self.cards.set_flag(self.conn, b, "active", False)
        s, run, skipped = self.S.cards_to_run(self.conn, sid)
        self.assertEqual(run, [a])
        self.assertEqual(skipped[0][0], b)
        # a card that ran 5 minutes ago is not run again by another schedule unless allowed
        self.conn.execute("INSERT INTO executions(profile_id, started_at, status) VALUES (?,?, 'completed')", (a, normalize.iso(normalize.now_utc())))
        self.assertEqual(self.S.cards_to_run(self.conn, sid)[1], [])           # Morning link: not allowed
        self.assertEqual(self.S.cards_to_run(self.conn, sid2)[1], [a])         # Evening link: duplicates confirmed
        self.S.set_enabled(self.conn, sid, False)
        self.assertEqual(self.S.cards_to_run(self.conn, sid)[1], [])
        c = next(x for x in self.cards.card_list(self.conn) if x["id"] == a)
        self.assertEqual(c["schedule_status"], "Scheduled")
        self.assertIn("Evening", [x["name"] for x in c["schedules"]])

    def test_default_schedule_links_new_cards(self):
        a = self._card("A")
        sid, _ = self.S.save(self.conn, {"name": "Default", "time": "08:00", "card_ids": [a], "is_default": True})
        b, linked = self.cards.create(self.conn, {"roles": ["x"], "name": "B"})
        self.assertEqual(linked, "Default")
        self.assertIn(b, [c["id"] for c in self.S.get(self.conn, sid)["cards"]])

    def test_schedule_validation(self):
        with self.assertRaises(self.S.ScheduleError):
            self.S.clean({"name": "", "time": "09:00"})
        with self.assertRaises(self.S.ScheduleError):
            self.S.clean({"name": "x", "time": "25:00"})
        with self.assertRaises(self.S.ScheduleError):
            self.S.clean({"name": "x", "frequency": "hourly", "every_hours": 5})


def settings_weights():
    return json.loads(json.dumps(DEFAULT_SETTINGS))["weights"]


class ExecutionHistory(unittest.TestCase):
    def test_run_records_execution_and_email_separately(self):
        tmp = Path(tempfile.mkdtemp())
        import jobradar.config as cfg
        import jobradar.db as dbm
        import jobradar.pipeline as pl
        settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        patches = [mock.patch.object(cfg, "DATA_DIR", tmp), mock.patch.object(dbm, "DB_PATH", tmp / "t.db"),
                   mock.patch.object(pl, "DATA_DIR", tmp), mock.patch.object(pl, "LOCK", tmp / "lock"),
                   mock.patch.object(pl, "REPORTS_DIR", tmp), mock.patch.object(pl, "LOG_PATH", tmp / "log"),
                   mock.patch.object(pl, "online", return_value=True),
                   mock.patch.object(pl, "load_company_candidates", return_value=[{"ats": "greenhouse", "token": "acme"}]),
                   mock.patch.dict(pl.ats.CONNECTORS, {"greenhouse": lambda t, timeout: ("Acme", [job(source_job_id="1", board="greenhouse:acme")])}),
                   mock.patch.dict(pl.boards.BOARDS, {}, clear=True),
                   mock.patch.object(pl, "load_settings", side_effect=lambda: settings)]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        with dbm.session() as conn:
            conn.execute("INSERT INTO profiles(name,email,email_on,active,profile_json) VALUES ('t','me@x.com',1,1,?)", (json.dumps(profile()),))
        pl.run("manual", progress=lambda m: None)
        with dbm.session() as conn:
            e = conn.execute("SELECT * FROM executions").fetchone()
            self.assertEqual(e["status"], "completed")
            self.assertEqual(e["jobs_found"], 1)
            self.assertEqual(e["new_jobs"], 1)
            em = conn.execute("SELECT * FROM email_log").fetchone()
            self.assertEqual(em["status"], "skipped")              # search completed, but no email was sent
            kinds = [r[0] for r in conn.execute("SELECT kind FROM activity")]
            self.assertIn("search_started", kinds)
            self.assertIn("search_completed", kinds)
        import jobradar.mailer as mailer
        p2 = mock.patch.object(mailer, "SECRETS", tmp / "secrets.json"); p2.start(); self.addCleanup(p2.stop)
        with dbm.session() as conn:
            settings["mail"]["default_account"] = mailer.add_account(conn, "a@gmail.com", "abcdabcdabcdabcd", test=False)
        with mock.patch.object(mailer, "_send_one", return_value=("failed", "<id@x>", 0, "Gmail rejected the message (550)")):
            pl.run("manual", progress=lambda m: None)
        with dbm.session() as conn:
            em = conn.execute("SELECT * FROM email_log ORDER BY id DESC").fetchone()
            self.assertEqual(em["status"], "failed")
            self.assertIn("rejected", em["error"])
            att = conn.execute("SELECT * FROM email_attempts ORDER BY id DESC").fetchone()
            self.assertEqual((att["status"], att["account_email"]), ("failed", "a@gmail.com"))
            self.assertEqual(conn.execute("SELECT status FROM executions ORDER BY id DESC").fetchone()[0], "completed")
        with mock.patch.object(pl, "online", return_value=False):
            pl.run("manual", progress=lambda m: None)
        with dbm.session() as conn:
            e = conn.execute("SELECT * FROM executions ORDER BY id DESC").fetchone()
            self.assertEqual(e["status"], "failed")
            self.assertIn("internet", e["error"])


class MailModule(unittest.TestCase):
    """v1.7 mail: recipients, accounts, sender rules, fallback, templates, history, duplicate protection."""
    def setUp(self):
        import sqlite3
        import jobradar.db as dbm
        from jobradar import mailer
        self.m = mailer
        self.tmp = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(mailer, "SECRETS", self.tmp / "secrets.json")]
        for x in self.p:
            x.start()
        self.addCleanup(lambda: [x.stop() for x in self.p])
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(dbm.SCHEMA)
        dbm._migrate(self.conn)
        mailer.migrate(self.conn)
        self.a1 = mailer.add_account(self.conn, "one@gmail.com", "abcd efgh ijkl mnop", test=False)
        self.a2 = mailer.add_account(self.conn, "two@gmail.com", "abcdefghijklmnop", test=False)
        self.conn.execute("UPDATE mail_accounts SET status='connected'")
        self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        self.settings["mail"].update(default_account=self.a1, to=["team@x.com"])
        self.conn.execute("INSERT INTO profiles(id,name,email,email_on,active,profile_json) VALUES (1,'DA',NULL,1,1,'{}')")

    def row(self):
        return self.conn.execute("SELECT * FROM profiles WHERE id=1").fetchone()

    def test_addresses(self):
        clean, probs = self.m.check_addresses({"to": "a@x.com, bad@, A@x.com", "cc": ["c@y.org", "a@x.com"], "bcc": "z@z.io"})
        self.assertEqual(clean, {"to": ["a@x.com"], "cc": ["c@y.org"], "bcc": ["z@z.io"]})
        self.assertEqual(len(probs), 3)

    def test_password_is_encrypted_and_never_listed(self):
        raw = (self.tmp / "secrets.json").read_text()
        self.assertNotIn("abcdefghijklmnop", raw.replace("\\n", "")) if os.name == "nt" else None
        self.assertEqual(self.m.get_secret(self.a1), "abcdefghijklmnop")
        self.assertNotIn("abcdefghijklmnop", json.dumps(self.m.accounts(self.conn, True)))
        with self.assertRaises(self.m.MailError):
            self.m.add_account(self.conn, "x@gmail.com", "short", test=False)
        with self.assertRaises(self.m.MailError):
            self.m.add_account(self.conn, "one@gmail.com", "abcdefghijklmnop", test=False)

    def test_precedence(self):
        r = self.m.resolve(self.conn, self.row(), self.settings)
        self.assertEqual((r["recipients_source"], r["recipients"]["to"]), ("global", ["team@x.com"]))
        self.assertEqual(r["template"]["name"], "Daily Job Search Results")
        self.conn.execute("UPDATE profiles SET email='me@x.com', email_json=? WHERE id=1", (json.dumps({"recipients_mode": "custom", "cc": ["boss@x.com"]}),))
        r = self.m.resolve(self.conn, self.row(), self.settings)
        self.assertEqual((r["recipients"]["to"], r["recipients"]["cc"], r["recipient_count"]), (["me@x.com"], ["boss@x.com"], 2))
        self.conn.execute("UPDATE profiles SET email_json=? WHERE id=1", (json.dumps({"recipients_mode": "none"}),))
        self.assertEqual(self.m.resolve(self.conn, self.row(), self.settings)["recipient_count"], 0)   # explicit empty != unset

    def _plan(self, sender, fallback="stop"):
        self.conn.execute("UPDATE profiles SET email_json=? WHERE id=1", (json.dumps({"recipients_mode": "global", "sender": sender, "fallback": fallback}),))
        res = self.m.resolve(self.conn, self.row(), self.settings)
        return self.m.plan_senders(self.conn, res, self.settings, 1)[0]

    def test_sender_modes_and_fallback(self):
        self.assertEqual([p["account"]["email"] for p in self._plan({"mode": "default"})], ["one@gmail.com"])
        self.assertEqual([p["account"]["email"] for p in self._plan({"mode": "specific", "accounts": [self.a2]})], ["two@gmail.com"])
        both = self._plan({"mode": "multi", "accounts": [self.a1, self.a2], "strategy": "copy"})
        self.assertEqual([p["account"]["email"] for p in both], ["one@gmail.com", "two@gmail.com"])
        self.assertEqual(len(self._plan({"mode": "multi", "accounts": [self.a1, self.a2], "strategy": "rotate"})), 1)
        self.conn.execute("UPDATE mail_accounts SET status='failed' WHERE id=?", (self.a2,))
        stop = self._plan({"mode": "specific", "accounts": [self.a2]}, "stop")
        self.assertIsNone(stop[0]["account"])
        self.assertIn("Stop and notify", stop[0]["error"])
        fb = self._plan({"mode": "specific", "accounts": [self.a2]}, "default")
        self.assertEqual(fb[0]["account"]["email"], "one@gmail.com")
        self.assertIn("two@gmail.com couldn't be used", fb[0]["fallback_reason"])
        # copy mode: the failed account's copy is NOT moved to an account already sending a copy
        cp = self._plan({"mode": "multi", "accounts": [self.a1, self.a2], "strategy": "copy"}, "default")
        self.assertEqual([bool(p["account"]) for p in cp], [True, False])

    def test_templates(self):
        self.assertTrue(self.m.validate_template("Hi {{job_title}}", "x"))
        self.assertTrue(self.m.validate_template("ok", "{{company_name}}"))
        self.assertTrue(self.m.validate_template("ok", "{{nope}}"))
        self.assertTrue(self.m.validate_template("ok", "{{#jobs}} {{job_title}}"))
        self.assertEqual(self.m.validate_template("{{totaljobsfound}} found", "{{#jobs}}{{job_title}} {{job_url}}{{/jobs}}"), [])
        t = {"subject": "{{totaljobsfound}} jobs for {{job_search_name}}", "body": "Hi\\n{{#jobs}}* {{job_title}} at {{company_name}} {{job_url}} {{job_location}}\\n{{/jobs}}End"}
        t["body"] = t["body"].replace("\\\\n", "\\n")
        jobs = [{"title": "<b>Dev</b>", "company": None, "apply_url": "javascript:alert(1)", "location": None}]
        subj, body = self.m.render(t, {"job_search_name": "A & B", "total_jobs_found": 1}, jobs, None, True)
        self.assertEqual(subj, "1 jobs for A & B")
        self.assertIn("&lt;b&gt;Dev&lt;/b&gt;", body)
        self.assertNotIn("javascript:", body)
        self.assertIn("Company not stated", body)
        self.assertNotIn("{{", body)
        _, text = self.m.render(self.m.DEFAULT_TEMPLATES[0], {"job_search_name": "x"}, jobs, None, False)
        self.assertNotIn("{{", text)
        pv = self.m.preview(self.m.DEFAULT_TEMPLATES[1])
        self.assertNotIn("{{", pv["html"])
        tid = self.m.save_template(self.conn, {"name": "Mine", "subject": "s", "body": "b"})
        self.m.save_template(self.conn, {"name": "Mine", "subject": "s2", "body": "b"}, tid)
        self.assertEqual(self.m.get_template(self.conn, tid)["version"], 2)
        with self.assertRaises(self.m.MailError):
            self.m.delete_template(self.conn, self.m.default_template(self.conn)["id"])

    def _send(self, results, key="exec:1"):
        it = iter(results)
        with mock.patch.object(self.m, "_send_one", side_effect=lambda *a: next(it)):
            return self.m.send(self.conn, self.settings, card_row=self.row(), execution_id=1, jobs=[{"title": "x"}], ctx={"job_search_name": "DA"},
                               standard_html="<p>jobs</p>", idem_key=key)

    def test_partial_uncertain_and_duplicates(self):
        self.conn.execute("UPDATE profiles SET email_json=? WHERE id=1", (json.dumps({"recipients_mode": "global", "sender": {"mode": "multi", "accounts": [self.a1, self.a2], "strategy": "copy"}}),))
        r = self._send([("sent", "<1@x>", 0, None), ("failed", "<2@x>", 2, "Gmail rejected the message (550)")])
        self.assertEqual(r["status"], "partial")
        att = self.conn.execute("SELECT status, account_email, retries FROM email_attempts ORDER BY id").fetchall()
        self.assertEqual([tuple(a) for a in att], [("sent", "one@gmail.com", 0), ("failed", "two@gmail.com", 2)])
        again = self._send([("sent", "<3@x>", 0, None)])                    # same run again: refused
        self.assertEqual(again["status"], "duplicate")
        with mock.patch.object(self.m, "_send_one", return_value=("sent", "<4@x>", 0, None)) as s1:
            rr, _ = self.m.resend(self.conn, self.settings, r["log_id"])
        self.assertEqual(s1.call_count, 1)                                   # only the account that failed
        self.assertEqual(rr["status"], "sent")
        u = self._send([("uncertain", "<5@x>", 0, "connection broke"), ("sent", "<6@x>", 0, None)], key="exec:2")
        self.assertEqual(u["status"], "partial")
        u2 = self._send([("uncertain", "<7@x>", 0, "connection broke"), ("uncertain", "<8@x>", 0, "broke")], key="exec:3")
        self.assertEqual(u2["status"], "uncertain")
        with self.assertRaisesRegex(self.m.MailError, "uncertain"):
            self.m.resend(self.conn, self.settings, u2["log_id"])            # needs explicit confirmation

    def test_skips_are_explained(self):
        self.settings["mail"]["to"] = []
        r = self._send([])
        self.assertEqual(r["status"], "skipped")
        self.assertIn("no recipients", r["note"])
        self.settings["mail"]["to"] = ["t@x.com"]
        self.settings["mail"]["default_account"] = None
        self.assertIn("No sending Gmail account", self._send([], key="k2")["note"])

    def test_legacy_settings_migrate(self):
        import jobradar.config as cfg
        st = json.loads(json.dumps(DEFAULT_SETTINGS))
        st["email"].update(username="old@gmail.com", app_password="abcd efgh ijkl mnop")
        self.conn.execute("DELETE FROM mail_accounts")
        with mock.patch.object(cfg, "SETTINGS_PATH", self.tmp / "settings.json"), mock.patch.object(cfg, "CONFIG_DIR", self.tmp):
            self.assertTrue(self.m.migrate_legacy_settings(self.conn, st))
        self.assertEqual(st["email"]["app_password"], "")
        aid = st["mail"]["default_account"]
        self.assertEqual(self.m.get_secret(aid), "abcdefghijklmnop")
