"""SQLite persistence: profiles, companies, jobs, history, notifications, runs."""
import json
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT,
  email_on INTEGER DEFAULT 1,
  active INTEGER DEFAULT 1,
  description TEXT,
  profile_json TEXT NOT NULL,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS companies (
  ats TEXT NOT NULL, token TEXT NOT NULL, name TEXT,
  status TEXT DEFAULT 'unchecked',          -- ok | dead | error | unchecked
  last_checked TEXT, last_error TEXT, job_count INTEGER,
  source TEXT DEFAULT 'registry',           -- registry | user
  PRIMARY KEY (ats, token)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,                       -- source:source_job_id
  source TEXT, source_job_id TEXT, requisition_id TEXT,
  company TEXT, title TEXT, location TEXT, work_arrangement TEXT, employment_type TEXT,
  description TEXT, salary_text TEXT, salary_min_lpa REAL, salary_max_lpa REAL,
  experience_text TEXT,
  published_at TEXT, updated_at TEXT, first_seen_at TEXT, last_seen_at TEXT,
  verified_at TEXT, closed_at TEXT,
  status TEXT,                               -- verified_active | appears_active | closed | unable_to_verify
  apply_url TEXT, apply_url_verified INTEGER, careers_url TEXT, source_url TEXT, source_name TEXT,
  is_ats INTEGER, board TEXT, content_hash TEXT, reopened INTEGER DEFAULT 0,
  raw_json TEXT
);
CREATE INDEX IF NOT EXISTS jobs_board ON jobs(board);
CREATE TABLE IF NOT EXISTS job_history (
  job_id TEXT, changed_at TEXT, field TEXT, old_value TEXT, new_value TEXT
);
CREATE TABLE IF NOT EXISTS matches (
  profile_id INTEGER, job_id TEXT, score REAL, eligible INTEGER,
  reasons_json TEXT, gaps_json TEXT, components_json TEXT, computed_at TEXT,
  PRIMARY KEY (profile_id, job_id)
);
CREATE TABLE IF NOT EXISTS notifications (
  profile_id INTEGER, job_id TEXT, content_hash TEXT, sent_at TEXT, run_id INTEGER,
  PRIMARY KEY (profile_id, job_id, content_hash)
);
CREATE TABLE IF NOT EXISTS user_state (
  profile_id INTEGER, job_id TEXT, state TEXT, updated_at TEXT,   -- saved | applied | dismissed
  PRIMARY KEY (profile_id, job_id)
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT, finished_at TEXT, status TEXT, trigger TEXT,
  sources_configured INTEGER, sources_scanned INTEGER, retrieved INTEGER, unique_jobs INTEGER,
  failures_json TEXT, summary_json TEXT
);
CREATE TABLE IF NOT EXISTS executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER, run_id INTEGER, trigger TEXT, schedule_id INTEGER,
  started_at TEXT, finished_at TEXT,
  status TEXT,                               -- running | completed | failed | stopped | skipped
  jobs_found INTEGER, new_jobs INTEGER, saved INTEGER, error TEXT
);
CREATE INDEX IF NOT EXISTS executions_profile ON executions(profile_id, id);
CREATE TABLE IF NOT EXISTS email_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER, execution_id INTEGER, at TEXT,
  status TEXT,                               -- sending | sent | failed | skipped
  jobs_included INTEGER, recipients TEXT, emails_sent INTEGER, subject TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS email_log_profile ON email_log(profile_id, id);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER, at TEXT, kind TEXT, detail TEXT
);
CREATE INDEX IF NOT EXISTS activity_profile ON activity(profile_id, id);
CREATE TABLE IF NOT EXISTS schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, kind TEXT DEFAULT 'shared',
  frequency TEXT DEFAULT 'daily',
  time TEXT DEFAULT '09:00', days_json TEXT, every_hours INTEGER,
  timezone TEXT DEFAULT 'Asia/Kolkata', enabled INTEGER DEFAULT 1, is_default INTEGER DEFAULT 0,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS schedule_cards (
  schedule_id INTEGER, profile_id INTEGER, allow_duplicate INTEGER DEFAULT 0,
  PRIMARY KEY (schedule_id, profile_id)
);
"""

PROFILE_COLUMNS = {"input_mode": "TEXT DEFAULT 'chart'", "answer_source": "TEXT"}


def _migrate(conn):
    have = {r[1] for r in conn.execute("PRAGMA table_info(profiles)")}
    for col, decl in PROFILE_COLUMNS.items():
        if col not in have:
            _add_column(conn, "profiles", col, decl)


import threading
_MIGRATE_LOCK = threading.Lock()
_MIGRATED = set()


def _add_column(conn, table, col, decl):
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    except sqlite3.OperationalError as e:          # another thread/process added it first
        if "duplicate column" not in str(e).lower():
            raise


def connect():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    key = str(DB_PATH)
    if key not in _MIGRATED:
        with _MIGRATE_LOCK:
            if key not in _MIGRATED:
                conn.executescript(SCHEMA)
                _migrate(conn)
                from . import mailer
                mailer.migrate(conn)
                conn.commit()
                _MIGRATED.add(key)
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row is not None else None


def jdump(v):
    return json.dumps(v, ensure_ascii=False)


def jload(v, default=None):
    if not v:
        return default
    try:
        return json.loads(v)
    except (TypeError, json.JSONDecodeError):
        return default
