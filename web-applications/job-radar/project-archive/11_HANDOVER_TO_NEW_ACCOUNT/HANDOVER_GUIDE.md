# Handover guide

## For a new AI assistant (Claude or ChatGPT)
1. Upload `PROJECT_MASTER_ARCHIVE_2026-10-11.zip`, or the unzipped folder.
   - **Claude:** create a Project and add `00_START_HERE/*`, `11_HANDOVER_TO_NEW_ACCOUNT/*` and `01_PROJECT_BRIEF/**` as project knowledge. Upload the zip in the chat when code work is needed.
   - **ChatGPT:** upload the zip to a chat that has the code interpreter on.
2. Paste the prompt from `CONTINUE_PROJECT_PROMPT.md`.
3. Check that the assistant's status summary matches `00_START_HERE/PROJECT_STATUS.md`.

## For a human developer
- **Requirements:** Python 3.9 or later. No pip packages are needed; pypdf is bundled in `vendor/`. Tesseract and an Anthropic key are optional.
- **Run the app:** `cd 07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0 && python -m jobradar ui`, then open http://127.0.0.1:8765.
- **Run the tests:** `python -m unittest tests.test_core`. Expect 79 tests to pass. `/tmp/fx` fixtures are optional; copies are in `10_TESTS_AND_VALIDATION/QualityChecks/fixtures/`.
- **End-to-end scripts:**
  - `10_TESTS_AND_VALIDATION/QualityChecks/scripts/fullflow2.py` uses Playwright, a fake Gmail and fake job sites.
  - It expects the project at `/home/claude/jobradar-agent`. Edit `ROOT` and the copy path before running it.
- **Build the installer:** `cd installer && makensis jobradar.nsi`.

## What is NOT in this archive
- Passwords, app passwords, API keys, `config/settings.json` and `config/secrets.json`.
- The full raw chat transcript. A redacted text log is included instead.
- Conversations before the session reset (only their summary).
- The sandbox's runtime test data.
- Other projects' artifacts in the same Claude account.

See `12_BACKUP_AND_RECOVERY/MISSING_FILES.md`.
