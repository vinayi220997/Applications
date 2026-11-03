# Open issues and known limitations

| # | Issue | Impact | Notes |
|---|---|---|---|
| 1 | Version 1.8.0 was copied to the PC but the app has not been restarted yet | The old code runs until a restart | Press Restart now |
| 2 | Not verified on real Windows: Task Scheduler XML (time-zone offset in `StartBoundary`), DPAPI, Windows OCR | Possible Windows-only bugs | **Check setup** reports schedules missing from Task Scheduler; mail shows clear errors |
| 3 | Schedule time zones use the UTC offset at the moment of saving | Zones with daylight saving shift by an hour until re-saved | India is not affected |
| 4 | Speech-to-text works only in Edge or Chrome and needs internet | Other browsers: the user types the transcript | Stated in the UI |
| 5 | No tracking of delivery or bounces (SMTP limitation) | "Sent" means accepted by Gmail, not delivered | Stated in the UI |
| 6 | Job coverage leans towards US tech companies | Fewer India matches | Adding an Adzuna key helps |
| 7 | Card history starts at v1.6 | Earlier scans are not in card history | — |
| 8 | Gmail OAuth was not implemented, by design | — | See `01_PROJECT_BRIEF/Decisions` and `04_RESEARCH_AND_REFERENCES` |
| 9 | One app password was typed in chat | Should be considered exposed | Revoke it (see `NEXT_STEPS.md` step 5) |
| 10 | The original 1.4–1.7 installer binaries were overwritten | Rebuilt installers exist, but they are new builds | See `09_ZIP_AND_PACKAGES/Package_Notes/INSTALLERS_ALL_VERSIONS.md` |
