"""Paths and settings. Everything lives inside the project folder so the agent is portable."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
CONFIG_DIR = ROOT / "config"
DB_PATH = DATA_DIR / "jobradar.db"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
COMPANIES_PATH = CONFIG_DIR / "companies.json"
LOG_PATH = DATA_DIR / "jobradar.log"

TIMEZONE = "Asia/Kolkata"
USER_AGENT = "JobRadar/1.0 (personal job-search agent; respects rate limits)"

DEFAULT_SETTINGS = {
    "timezone": "Asia/Kolkata",
    "freshness_window_days": 7,
    "high_match_threshold": 75,
    "min_score_to_report": 55,
    "max_jobs_per_report": 40,
    "verify_top_n": 30,
    "request_timeout_seconds": 20,
    "max_parallel_requests": 8,
    "weights": {"skills": 0.30, "experience": 0.25, "responsibilities": 0.20,
                "location": 0.10, "preferences": 0.10, "compensation": 0.05},
    "email": {
        "enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "",
        "app_password": "",
        "from_name": "Job Radar",
    },
    "sources": {
        "greenhouse": True, "lever": True, "ashby": True, "smartrecruiters": True,
        "workable": True, "recruitee": True,
        "remotive": True, "remoteok": True, "jobicy": True, "weworkremotely": True, "arbeitnow": False,
        "adzuna": {"enabled": False, "app_id": "", "app_key": "", "country": "in"},
    },
    "anthropic": {"api_key": "", "model": "claude-haiku-4-5"},
    "ai": {"enabled": True, "provider": "anthropic"},
    "ocr": {"enabled": True, "provider": "auto"},
    "ui_port": 8765,
}


def _merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def ensure_dirs():
    for d in (DATA_DIR, REPORTS_DIR, CONFIG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_settings():
    ensure_dirs()
    user = {}
    if SETTINGS_PATH.exists():
        try:
            user = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            user = {}
    s = _merge(DEFAULT_SETTINGS, user)
    # Environment variables override secrets so they never need to live in a file.
    if os.environ.get("JOBRADAR_SMTP_PASSWORD"):
        s["email"]["app_password"] = os.environ["JOBRADAR_SMTP_PASSWORD"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        s["anthropic"]["api_key"] = os.environ["ANTHROPIC_API_KEY"]
    return s


def save_settings(s):
    ensure_dirs()
    SETTINGS_PATH.write_text(json.dumps(s, indent=2), encoding="utf-8")


def load_company_candidates():
    if not COMPANIES_PATH.exists():
        return []
    data = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))
    return data.get("companies", [])
