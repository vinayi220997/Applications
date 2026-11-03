# Continuation prompt (copy everything below the line into Claude or ChatGPT)

---

You are continuing an existing software project called **Job Radar**: a local AI job discovery agent for Windows, written in Python. I'm giving you its archive, `PROJECT_MASTER_ARCHIVE_2026-10-11.zip`, unzipped or uploaded. Don't start from scratch: the project is at version 1.8.0 and most features are finished.

Work in this order:

1. Read `00_START_HERE/README.md`, then `11_HANDOVER_TO_NEW_ACCOUNT/PROJECT_CONTEXT.md`.
2. Open `00_START_HERE/MASTER_FILE_INDEX.csv` and check which listed files are actually present in what I gave you. Never assume a file mentioned in the docs exists until you have opened it.
3. Treat `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/` as the authoritative source. Folders named `*_delta` and anything in `99_ARCHIVE_OLD` are history only.
4. Review the requirements in `01_PROJECT_BRIEF/OriginalRequirements/`, the decisions in `01_PROJECT_BRIEF/Decisions/`, the research in `04_RESEARCH_AND_REFERENCES/`, and `02_VERSIONS_AND_HISTORY/CHANGELOG.md`.
5. Give me a short summary of the current status, using `00_START_HERE/PROJECT_STATUS.md`.
6. List the missing files and open issues from `12_BACKUP_AND_RECOVERY/MISSING_FILES.md` and `11_HANDOVER_TO_NEW_ACCOUNT/OPEN_ISSUES.md`.
7. Ask me a question only when something you need can't be worked out from these files.
8. Propose the next task (start from `NEXT_STEPS.md`) and wait for my OK before making major changes.
9. Keep the existing files. Make changes as new versions: bump the version in `installer/jobradar.nsi` and in `APP_VERSION` in `cards.py`, and add a changelog entry.
10. After any change, run the tests (`python -m unittest tests.test_core`), then update `MASTER_FILE_INDEX.csv`, `CHANGELOG.md` and `PROJECT_STATUS.md`.
11. Never claim you have reviewed files, earlier conversations or my computer if you can't actually access them.
12. Follow these project rules:
    - No scraping of sites without an API, and no bypassing logins or CAPTCHAs.
    - Never invent jobs, dates or links.
    - Never auto-apply to jobs.
    - Never ask me to paste passwords or API keys into the chat; I type them into the app.
    - Write in plain English. My UI-related messages may contain typos ("chart" means the chat).

To build the Windows installer on Linux: `cd installer && makensis jobradar.nsi`. To run the app locally: `python -m jobradar ui`.
