# Project status — as of 2026-10-11

## Summary
Job Radar **1.8.0** is built and its tests pass in the sandbox: 79 unit tests, plus scripted end-to-end and browser tests (results are in `10_TESTS_AND_VALIDATION`).

**Version on Dilip's PC: 1.8.0.** I copied the 1.8.0 files into the PC's install folder on 2026-10-11, while preparing this archive. The app picks them up after **Restart now**. The installer is also in the PC's Downloads folder.

## Completed
| Version | Delivered | Highlights |
|---|---|---|
| 0 (web artifact) | 2026-10-10 | Claude-hosted browser app (superseded) |
| 1.0 | 2026-10-10 | Local Python agent: chat intake, ATS and board sources, freshness, verification, dedupe, scoring, HTML report, Gmail SMTP, Task Scheduler (`JobRadar.zip`) |
| 1.1–1.4 (exact numbering not recorded) | 2026-10-10 | Bug fixes: email not sent, crash on Windows without time zone data, scoring too strict, "close matches", Restart banner. Plus: attachments, screenshots, voice, the .exe installer, scan animation with Stop, better chat understanding, the Flows and Demo artifacts |
| 1.5.0 | 2026-10-11 | From `Updats_1.md`: confirm/edit for each answer, progress bar, section editor, toasts, sample files, voice panel, OCR separate from AI, AI/OCR settings, chat status |
| 1.6.0 | 2026-10-11 | Multiple cities and work modes, Chart and Questionnaire modes, job search cards, export/import, execution and email history, per-card and shared schedules |
| 1.7.0 | 2026-10-11 | Mail module: several Gmail accounts (DPAPI-encrypted), To/CC/BCC, sender rules and fallback, templates, per-card email settings, history of each send attempt, duplicate-send protection |
| 1.8.0 | 2026-10-11 | Email block when creating or editing a card (several addresses, choice of senders including "All accounts"), pause switch for accounts, Advanced settings section, Light/Dark/System theme, fix for a race in database migrations |

## In progress
- Nothing is being coded. Job Radar still has to be restarted on the PC so that 1.8.0 is used.

## Not verified on real Windows (sandbox is Linux)
- Windows Task Scheduler tasks created per schedule (`schtasks /Create /XML`).
- DPAPI encryption of app passwords (ctypes `CryptProtectData`).
- Windows built-in OCR (PowerShell WinRT).
- Real Gmail delivery from the new mail module. All mail tests used a fake SMTP server.

## Blocked / waiting on the user
- Restart Job Radar (Restart now), open the Mail tab, and press **Test** on the migrated Gmail account.
- Optional: an Adzuna API key, for better coverage of Indian job boards.
