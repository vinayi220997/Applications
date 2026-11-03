# Changelog

## 2026-10-11 — Archive update: all versions
- Rebuilt installers for 1.4.0 (two builds), 1.5.0, 1.6.0 and 1.7.0, and reconstructed their full source trees.
- Added two early zip builds found in the PC's Downloads.
- Corrected the `JobRadar.zip` label from 1.0 to 1.4.0.
- Added `PROJECT_FILE_STRUCTURE.md` and `HOW_TO_CONTINUE_IN_ANOTHER_CLAUDE_ACCOUNT.md`.

## 2026-10-11 — Archive preparation
- Copied the 1.8.0 files to the PC's install folder (the PC came back online), and the archive ZIP to the PC's Downloads folder.
- Built `PROJECT_MASTER_ARCHIVE/` from the sandbox source tree, the delivered update folders, the uploads, the project docs, the published artifacts, the test scripts and screenshots, and the session transcript (redacted).
- Excluded: secrets, the sandbox's runtime test data, caches and the raw transcript. See `ARCHIVE_MANIFEST.txt`.
- Generated new files, each labelled as generated: the handover documents, `schema.sql`, `settings.example.json`, `ARCHITECTURE.md`, the source register, the file index and the unit test results.

## 1.8.0 — 2026-10-11
- Creating or editing a card (Chart or Questionnaire mode) now has an **Email** block.
  - Several To addresses, plus optional CC and BCC.
  - Send from: Default, All accounts, or Choose accounts.
  - When several accounts send: take turns, or a copy from each.
- The chat's email question accepts several addresses.
- New sender mode `all`.
- Gmail accounts have a **pause** switch (`mail_accounts.paused`), which replaces Disconnect in the interface.
- The Mail tab's default recipients and default sending rule moved under **Advanced settings**, which is collapsed by default.
- **Theme**: Light, Dark or System.
- Fixed: concurrent first requests could crash the database migration ("duplicate column"). Migrations now run once under a lock and tolerate an existing column.

## 1.7.0 — 2026-10-11
- New mail module (`mailer.py`) and a Mail tab.
  - Several Gmail accounts, with app passwords encrypted using DPAPI in `config/secrets.json`. The old plain-text password is migrated and blanked.
  - Default To/CC/BCC, sender rules and fallback policy, and a daily limit.
  - Versioned templates with placeholders and preview.
- Per-card email settings, with precedence card > global > built-in.
- Email history now records each send attempt (statuses: pending, sending, sent, partial, uncertain, failed, skipped), with Message-ID, View and Resend.
- Idempotency keys stop duplicate sends. Uncertain outcomes are never resent automatically.

## 1.6.0 — 2026-10-11
- A search can have several cities and several work modes.
- Chart and Questionnaire input modes, which convert into each other.
- Job search cards: on/off, status, edit, duplicate, delete, export/import (JSON v1), and history (executions, emails, activity).
- Schedules: per-card and shared, one Task Scheduler task each, duplicate-run guard. The old global schedule migrates to a "Default schedule".

## 1.5.0 — 2026-10-11
- Confirm, Edit or Change after each answer, plus a progress bar and section segments.
- Section editor with Overwrite, Add or Edit existing.
- Toasts and checkmark animations.
- Attach panel with sample files and a review box.
- Voice panel with a sample recording and a transcript review.
- OCR handled separately from AI (Windows OCR, Tesseract or Claude), with AI/OCR settings and connection tests.
- Chat status panel with an honest offline mode.

## 1.0–1.4 — 2026-10-10
See `01_PROJECT_BRIEF/OriginalRequirements/REQ_00_…` and `PROJECT_STATUS.md`.
