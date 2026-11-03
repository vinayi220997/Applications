# Job Discovery Agent — Project Notes

Updated 2026-10-11.

## Current direction: local agent ("Job Radar"), v1.8.0

### v1.8.0
- Card create/edit (Chart summary card and Questionnaire) has an **Email** block:
  - email on/off
  - To with several addresses, plus optional CC/BCC (empty = default recipients)
  - Send from: Default / All accounts / Choose accounts, with Take turns or A copy from each
  - Saved via `email_cfg` on POST /api/profiles(/id) → cards.set_email_cfg.
  - The chat's email question accepts several addresses.
- New sender mode "all": all accounts that aren't paused, including ones added later.
- Gmail accounts have a **pause** toggle (mail_accounts.paused): the password is kept, paused accounts are skipped via the fallback rule, and pausing an in-use account asks for confirmation. The Disconnect button was removed; "disconnected" now shows as "Needs reconnect".
- The Mail tab's default recipients and default sending rule moved into a collapsible **Advanced settings** section (closed by default; open state remembered).
- **Theme**: Light / Dark / System, in the header and in Settings. Stored in localStorage; applied before the page draws.
- Fixed a race where two simultaneous first requests both ran ALTER TABLE ("duplicate column"). Migrations now run once under a lock and tolerate an existing column.
- v1.8 was NOT committed to the PC (the device was offline). The installer was sent in chat; the user runs it over the existing install.

Dilip asked for an agent that runs locally on demand, with a user-chosen schedule, usable by anyone, that asks clarifying questions (location, experience, etc.).
Installed on Dilip's PC at C:\Users\Admin\AppData\Local\Programs\JobRadar (updates are committed into that folder; the app shows "Restart now"). Installer: JobRadar-Setup.exe (NSIS) in Downloads.
- Python 3.9+ app (stdlib + bundled pypdf). Local web UI at http://127.0.0.1:8765.

### v1.7.0 (Mail module, jobradar/mailer.py, Mail tab)
- **Decision: no Gmail OAuth.** Sign-in stays on Gmail app passwords over SMTP.
  - Reason: a self-made Google OAuth app in testing mode has refresh tokens that expire every 7 days, and production use needs Google verification of the gmail.send scope.
  - App passwords are encrypted with Windows DPAPI in config/secrets.json, separate from settings.json and excluded from the installer.
  - The legacy settings.email.app_password migrates to account #1 and is then blanked.
- Several sending accounts (table mail_accounts).
  - Statuses: connected / untested / failed / disconnected / limited.
  - Actions: test, send test, make default, reconnect, disconnect / remove (asks first if the account is in use).
  - A per-account 24h recipient count is checked against the daily limit (default 450).
- Global To/CC/BCC in settings["mail"], plus a global sender rule:
  - default / specific / multi, where multi is either copy (a copy from each account, needs confirmation) or rotate (accounts take turns).
  - Fallback policy: stop / default / other. A fallback never sends a second copy and is recorded per attempt.
  - Master switch: settings.email.enabled (now defaults to True).
- Templates (email_templates + email_template_versions).
  - Two defaults: "Daily Job Search Results" (default, uses {{job_list}} = full job cards) and "New Job Opportunities" (a {{#jobs}} loop).
  - Placeholders and aliases are validated; values are HTML-escaped; only http(s) URLs are used; missing values show "Not stated".
  - Preview uses sample jobs. Each save creates a new version. Templates can be duplicated, enabled/disabled, made default, and deleted only when unused.
- Per-card Email settings live in profiles.email_json; profiles.email holds the card's To list.
  - Recipients: global / custom (To+CC+BCC) / none (explicitly empty).
  - Template override, sender override, fallback override.
  - Precedence: card > global > built-in. The chat/questionnaire "Report email" field = the card's To list.
- Sending (mailer.send) creates an email_log execution (template id/name/version, sender mode, recipients, jobs, idem_key) and one email_attempts row per account (selected vs actual account, fallback reason, status, Message-ID, retries, error). It also stores the rendered message in email_messages (last 300 kept) for View/Resend.
  - Statuses: pending / sending / sent / partial / uncertain / failed / skipped.
  - idem_key exec:<execution id> means one email per run; now:<card>:<minute> stops double-clicks.
  - Connect/login failures are retried with backoff, and so are 4xx DATA rejections. A connection broken during DATA is marked "uncertain" and is never auto-resent; Resend needs confirmation and only resends the failed accounts.
  - 535 marks the account failed; 5.4.5 marks it limited for 24h.
- Not done, by design: per-schedule email overrides (card settings apply whichever schedule runs it), and delivery/bounce tracking (SMTP doesn't report it; "Sent" = accepted by Gmail).
- Tests: 80 unit tests, plus a full-flow test with a fake Gmail (2 accounts, copy mode, template B, CC) and browser screenshots. Also checked against a copy of the real DB.

### v1.6.0 (cards, modes, schedules, history)
- Multi-select cities and work modes. Chart and Questionnaire input modes that convert into each other.
- Job search cards with on/off, status, last search and email, edit (same card), duplicate, export/import (JSON jobradar.card v1, no secrets) and history (executions, email_log, activity).
- Schedules: card-own and shared, each with its own Windows task `JobRadar\Schedule-<id>`. Duplicate runs need confirmation, plus a 15-minute guard.

### v1.5.0
- Confirm / Edit / Change after each answer, progress bar, section editor, toasts, sample files, voice panel, OCR separate from AI, Chat status.

## Core rules (unchanged)
- published_at is never inferred from first_seen.
- No bypassing logins or CAPTCHAs.
- No auto-apply.
- No duplicate alerts.
- Never handle the user's passwords or API keys (the user types them into the app).

## Open items
- On the PC: after Restart, check the Mail tab. The old Gmail account should appear (migrated, "Not tested"). Press Test.
- Confirm DPAPI encryption and Task Scheduler on real Windows (both untestable in the sandbox).
- Coverage is US-tech heavy. Recommend an Adzuna key for India.
- Default report email for Dilip's search: vinayi220997@gmail.com.
