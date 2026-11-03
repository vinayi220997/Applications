# Project context (read this first if you're continuing the work)

## People and accounts
- **Owner:** Dilip (dilip@blive.co.in, Blive Co).
- **First report recipient:** vinayi220997@gmail.com.
- **Sending Gmail account:** dilipkumarramathota@gmail.com. Its app password is stored only on the PC and is **not** in this archive. A password once typed in chat was redacted here. It should be treated as exposed and revoked.
- **Target user:** anyone who wants job alerts. The UI is in plain English, and every feature works without AI keys.

## The user's requirements, in their own words
These are in `01_PROJECT_BRIEF/OriginalRequirements/`:
- `REQ_00` is the summary of all early requests (v1.0–1.4).
- `Updats_1.md` drove v1.5.
- `REQ_02` drove v1.6, `REQ_03` drove v1.7 and `REQ_04` drove v1.8.
- `REQ_05` is this archiving instruction.

The original operating spec is in `01_PROJECT_BRIEF/Specifications/job-discovery-agent-spec.md`:
- a daily scan at 8 AM IST
- freshness categories, active-status verification and dedupe
- scoring and a 17-field report
- no fabricated jobs or links, no duplicate alerts, no auto-apply.

## Hard constraints
- Use only sources that have an API. LinkedIn, Naukri, Indeed and Glassdoor are not scraped; the report includes pre-filled search links for them.
- Never infer a job's publication date from when it was discovered. HTTP 200 does not prove a job is active.
- Never handle the user's passwords or API keys. The user types them into the app. Secrets stay in `config/settings.json` and `config/secrets.json` on the PC (DPAPI-encrypted).
- Never auto-apply to jobs. Never report success on a partial or failed scan.
- Mail: "Sent" means only that Gmail accepted the message. Never resend automatically when the outcome is uncertain. Every fallback is recorded.

## Architecture
See `07_SOURCE_FILES/Technical_Documentation/ARCHITECTURE.md` and `07_SOURCE_FILES/Schemas/schema.sql`. In short:
- `python -m jobradar ui` serves the single-page app and JSON API (`web.py`).
- `python -m jobradar run [--schedule ID]` runs a scan (`pipeline.py`). Each card becomes an `executions` row, and its email goes through `mailer.send`, which writes `email_log` and `email_attempts` rows.
- Windows Task Scheduler tasks call `run_scan.bat <schedule id>`.

## How the PC is updated
The cloud session can write directly into the install folder with the remote-devices bridge (`device_commit_files`), when Dilip's computer is connected. The app notices the changed `.py` files and shows a **Restart now** banner. Otherwise, rebuild the installer and send it:
- on Linux: `cd installer && makensis jobradar.nsi` writes `../../JobRadar-Setup.exe`
- the build skips `data/`, `reports/`, `settings.json` and `secrets.json`.

## Current state
- Source tree: 1.8.0, with 79 unit tests passing.
- PC: the 1.8.0 files were copied to the install folder on 2026-10-11. Running 1.8.0 needs a Restart (not confirmed yet).
- Real data snapshot from the PC: `12_BACKUP_AND_RECOVERY/Recovered_Files/pc_data_snapshot_2026-10-11/jobradar.db` (taken 05:52 UTC, before v1.6). It holds one card, "test1". It contains personal data (email addresses, job matches).

## File locations
- Authoritative source: `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/`
- Installer: `09_ZIP_AND_PACKAGES/Release_Packages/JobRadar-Setup_v1.8.0.exe`
- User manual: `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/README.md`, also copied to `03_DOCUMENTS/Final_Documents/` (not approved by the user)
- Decisions log: `01_PROJECT_BRIEF/Decisions/job-discovery-agent-decisions.md`
