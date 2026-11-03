# Job Radar 1.8.0: architecture (generated for the archive, from the source code)

```
Browser (static/index.html, single-page app)
   │  JSON over http://127.0.0.1:8765 (web.py; only localhost is accepted; POST requests need the X-JobRadar header)
   ▼
web.py ── intake.py ──── chat and form intake: questions, confirm, set_field, resume, parse_brief
       ├─ attachments.py ─ PDF/DOCX/TXT/RTF reading; images → services.ocr_image; voice → transcript
       ├─ services.py ──── AI (Anthropic) and OCR engines (Windows WinRT OCR / Tesseract / Claude vision), status, tests
       ├─ cards.py ─────── card list/status, create/update/duplicate/delete, export/import (jobradar.card v1), email settings
       ├─ schedules.py ─── schedules + schedule_cards, next run, conflicts, sync of OS tasks
       │     └─ scheduler.py  Windows Task Scheduler XML (JobRadar\Schedule-<id>) / cron, run_scan.bat
       ├─ mailer.py ────── accounts (DPAPI secrets), recipients, sender planning + fallback, templates, send, resend, history
       └─ pipeline.py ──── run(): lock → sources → store → close missing → dedupe → per card: score, verify, report, email
             ├─ sources/ats.py, sources/boards.py   public job APIs
             ├─ normalize.py, dedupe.py, freshness.py, verify.py, matching.py
             └─ report.py   HTML report, job cards (jobs_html), footer
db.py ── SQLite (data/jobradar.db). Migrations run once per process, under a lock.
config.py ── settings.json defaults; config/secrets.json holds the encrypted app passwords.
doctor.py ── "Check setup" diagnostics.
__main__.py ── CLI: ui | run [--schedule ID] | ask | schedule | unschedule | status | doctor | email-now
```

## Main tables (see `../Schemas/schema.sql`)
| Table | Contents |
|---|---|
| `profiles` | Cards. `input_mode`, `answer_source`, `email` (the To list) and `email_json` (card email settings) |
| `jobs`, `job_history`, `matches`, `notifications`, `user_state` | Jobs pipeline |
| `runs` | Scans |
| `executions`, `activity` | Card history |
| `email_log`, `email_attempts`, `email_messages` | Mail history |
| `schedules`, `schedule_cards` | Schedules |
| `mail_accounts`, `email_templates`, `email_template_versions` | Mail settings |
| `attachments` | Uploaded files |

## Mail precedence
Card setting → global setting (`settings["mail"]`) → built-in default.

Recipients are one of `global`, `custom` or `none`. The sender mode is one of `default`, `specific`, `multi` or `all`, and the multi-account strategy is either `copy` or `rotate`. The fallback is one of `stop`, `default` or `other`.
