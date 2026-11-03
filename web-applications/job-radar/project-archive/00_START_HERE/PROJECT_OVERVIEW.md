# Project overview: Job Radar (AI Job Discovery Agent)

**Owner:** Dilip (Blive Co) · **Claude project:** "Web crawler" · **Archive date:** 2026-10-11 · **Current version:** 1.8.0

## Purpose
A job discovery agent that searches job sources, checks that openings are still active, removes duplicates, ranks jobs against a person's profile, and emails a report with direct apply links. It never invents jobs, dates or links, and it never applies on the user's behalf.

The first report recipient was **vinayi220997@gmail.com**. The app is built so that anyone can create their own searches.

## What it is now
**Job Radar** is a local Windows application, written in Python 3.9+ using only the standard library plus a bundled copy of pypdf.
- It runs a web interface at `http://127.0.0.1:8765` and is installed with `JobRadar-Setup.exe` (an NSIS installer).
- It is installed on Dilip's PC at `C:\Users\Admin\AppData\Local\Programs\JobRadar`.

### Main components (source in `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/`)
| Area | Files | What it does |
|---|---|---|
| Intake (describing the job) | `intake.py`, `attachments.py`, `services.py` | **Chart mode** chat with confirm, edit and progress, plus a **Questionnaire mode** form. Reads resumes and job posts (PDF/DOCX/TXT), screenshots (Windows OCR, Tesseract or Claude vision) and voice notes (browser speech-to-text). Claude AI is optional. |
| Sources | `sources/ats.py`, `sources/boards.py` | Public APIs of Greenhouse, Lever, Ashby, SmartRecruiters, Workable and Recruitee. Remotive, Remote OK, Jobicy, We Work Remotely and Arbeitnow. Adzuna is optional. LinkedIn and Naukri are not scraped; the report gives pre-filled search links instead. |
| Pipeline | `pipeline.py`, `normalize.py`, `dedupe.py`, `freshness.py`, `verify.py`, `matching.py` | Scan, normalise, store, close missing jobs, remove duplicates, classify freshness, verify, score (0–100) and report. |
| Cards | `cards.py` | Each saved search is a **job search card**. Cards have an on/off switch, status, an edit option, duplicate, export/import (JSON) and an activity history. |
| Schedules | `schedules.py`, `scheduler.py` | Per-card and shared schedules. Each schedule becomes one Windows Task Scheduler task (`JobRadar\Schedule-<id>`). |
| Mail | `mailer.py`, `report.py` | Several Gmail sending accounts using app passwords encrypted with Windows DPAPI. To/CC/BCC, sender rules (default, specific, several or all accounts, sending copies or taking turns), fallback policy, templates with placeholders, history of every send attempt, and duplicate-send protection. |
| UI | `static/index.html` | A single-page app with tabs for cards, schedules, results and mail. Light, Dark or System theme. |
| Persistence | `db.py` | SQLite database at `data/jobradar.db`. Settings in `config/settings.json`, secrets in `config/secrets.json`. |

## Scope and key decisions (details in `01_PROJECT_BRIEF/Decisions/`)
- **Local agent, not a cloud service.** The user asked for it to run on their PC and on a schedule they choose.
- **No scraping of sites without an API**, no bypassing logins or CAPTCHAs, and no auto-apply.
- **Gmail app passwords instead of OAuth.** Self-made OAuth apps in testing mode lose their tokens every 7 days; see `04_RESEARCH_AND_REFERENCES`.
- **Secrets never leave the PC.** They are never exported, logged or bundled into the installer.

## Earlier deliverables (superseded, kept for history)
- **Job Radar web artifact** (Claude-hosted browser app): https://claude.ai/artifact/U9ZzRWZeAp6dVGYEiYNX9S
- **Job Radar Demo** (interactive UI demo with mock data): https://claude.ai/artifact/2Wc9CJNDezoDNCnJUQmZaB
- **Job Radar Flows** (diagrams of every application flow, as of about version 1.4): https://claude.ai/artifact/BA6mD6LrUFHKUH5Ws5WNtG
