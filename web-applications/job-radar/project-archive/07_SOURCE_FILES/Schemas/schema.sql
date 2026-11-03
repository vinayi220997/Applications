-- Job Radar 1.8.0 SQLite schema, dumped from a fresh database created by the 1.8.0 code
CREATE TABLE activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER, at TEXT, kind TEXT, detail TEXT
);
CREATE TABLE attachments (
  id TEXT PRIMARY KEY, profile_id INTEGER, filename TEXT, mime TEXT, kind TEXT, size INTEGER,
  path TEXT, text TEXT, doc_type TEXT, extracted_json TEXT, note TEXT, created_at TEXT);
CREATE TABLE companies (
  ats TEXT NOT NULL, token TEXT NOT NULL, name TEXT,
  status TEXT DEFAULT 'unchecked',          -- ok | dead | error | unchecked
  last_checked TEXT, last_error TEXT, job_count INTEGER,
  source TEXT DEFAULT 'registry',           -- registry | user
  PRIMARY KEY (ats, token)
);
CREATE TABLE email_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_log_id INTEGER, account_id INTEGER, account_email TEXT,
  selected_email TEXT, fallback_reason TEXT,
  status TEXT,                                -- pending | sending | sent | failed | uncertain
  message_id TEXT, recipients_count INTEGER, retries INTEGER DEFAULT 0, error TEXT, at TEXT
);
CREATE TABLE email_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER, execution_id INTEGER, at TEXT,
  status TEXT,                               -- sending | sent | failed | skipped
  jobs_included INTEGER, recipients TEXT, emails_sent INTEGER, subject TEXT, error TEXT
, schedule_id INTEGER, card_name TEXT, trigger TEXT, template_id INTEGER, template_name TEXT, template_version INTEGER, sender_mode TEXT, strategy TEXT, selected_accounts TEXT, recipients_count INTEGER, idem_key TEXT, note TEXT);
CREATE TABLE email_messages (email_log_id INTEGER PRIMARY KEY, subject TEXT, html TEXT, text TEXT, to_json TEXT);
CREATE TABLE email_template_versions (
  template_id INTEGER, version INTEGER, subject TEXT, body TEXT, saved_at TEXT, PRIMARY KEY (template_id, version)
);
CREATE TABLE email_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, subject TEXT NOT NULL, body TEXT NOT NULL,
  enabled INTEGER DEFAULT 1, is_default INTEGER DEFAULT 0, version INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT
);
CREATE TABLE executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER, run_id INTEGER, trigger TEXT, schedule_id INTEGER,
  started_at TEXT, finished_at TEXT,
  status TEXT,                               -- running | completed | failed | stopped | skipped
  jobs_found INTEGER, new_jobs INTEGER, saved INTEGER, error TEXT
);
CREATE TABLE job_history (
  job_id TEXT, changed_at TEXT, field TEXT, old_value TEXT, new_value TEXT
);
CREATE TABLE jobs (
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
CREATE TABLE mail_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, from_name TEXT,
  status TEXT DEFAULT 'untested',            -- connected | failed | untested | disconnected | limited
  paused INTEGER DEFAULT 0,
  last_error TEXT, last_checked TEXT, limited_until TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE matches (
  profile_id INTEGER, job_id TEXT, score REAL, eligible INTEGER,
  reasons_json TEXT, gaps_json TEXT, components_json TEXT, computed_at TEXT,
  PRIMARY KEY (profile_id, job_id)
);
CREATE TABLE notifications (
  profile_id INTEGER, job_id TEXT, content_hash TEXT, sent_at TEXT, run_id INTEGER,
  PRIMARY KEY (profile_id, job_id, content_hash)
);
CREATE TABLE profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT,
  email_on INTEGER DEFAULT 1,
  active INTEGER DEFAULT 1,
  description TEXT,
  profile_json TEXT NOT NULL,
  created_at TEXT, updated_at TEXT
, input_mode TEXT DEFAULT 'chart', answer_source TEXT, email_json TEXT);
CREATE TABLE runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT, finished_at TEXT, status TEXT, trigger TEXT,
  sources_configured INTEGER, sources_scanned INTEGER, retrieved INTEGER, unique_jobs INTEGER,
  failures_json TEXT, summary_json TEXT
);
CREATE TABLE schedule_cards (
  schedule_id INTEGER, profile_id INTEGER, allow_duplicate INTEGER DEFAULT 0,
  PRIMARY KEY (schedule_id, profile_id)
);
CREATE TABLE schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, kind TEXT DEFAULT 'shared',
  frequency TEXT DEFAULT 'daily',
  time TEXT DEFAULT '09:00', days_json TEXT, every_hours INTEGER,
  timezone TEXT DEFAULT 'Asia/Kolkata', enabled INTEGER DEFAULT 1, is_default INTEGER DEFAULT 0,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE user_state (
  profile_id INTEGER, job_id TEXT, state TEXT, updated_at TEXT,   -- saved | applied | dismissed
  PRIMARY KEY (profile_id, job_id)
);
CREATE INDEX activity_profile ON activity(profile_id, id);
CREATE INDEX email_attempts_log ON email_attempts(email_log_id);
CREATE INDEX email_log_idem ON email_log(idem_key);
CREATE INDEX email_log_profile ON email_log(profile_id, id);
CREATE INDEX executions_profile ON executions(profile_id, id);
CREATE INDEX jobs_board ON jobs(board);
