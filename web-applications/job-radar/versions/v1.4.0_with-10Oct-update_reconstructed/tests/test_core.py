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
            r = intake.answer(r["state"], {"email": "skip", "name": "DA"}.get(k, "yes"))
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
        self.assertIn("Anthropic API key", r["note"])

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
            r = intake.answer(r["state"], {"email": "skip", "name": "x"}.get(k, "yes"))
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
        with mock.patch.object(pl.report, "send_email", side_effect=lambda s, to, subj, h, t: (sent.append((to, subj)) or (True, "sent"))):
            rid = pl.run("t", progress=lambda m: None)
        self.assertEqual(len(sent), 1)
        self.assertIn("1 new match", sent[0][1])
        # email-now sends all open matches even though they were reported
        with mock.patch.object(pl.report, "send_email", return_value=(True, "sent")) as m:
            ok, msg = pl.email_current(1)
        self.assertTrue(ok)
        self.assertIn("Sent 1 job", msg)


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
