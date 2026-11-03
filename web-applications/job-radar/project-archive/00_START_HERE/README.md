# PROJECT_MASTER_ARCHIVE — Job Radar (AI Job Discovery Agent)

Packaged 2026-10-11 from the Cowork session for the Claude project "Web crawler". Owner: Dilip (Blive Co).

## Start here
1. `PROJECT_OVERVIEW.md`: what the project is.
2. `PROJECT_STATUS.md`: what's done, what isn't, and what hasn't been verified.
3. `../11_HANDOVER_TO_NEW_ACCOUNT/CONTINUE_PROJECT_PROMPT.md`: paste it into a new Claude or ChatGPT account.
4. `MASTER_FILE_INDEX.csv`: every file, with where it came from, its checksum and whether it was verified.
5. `../12_BACKUP_AND_RECOVERY/MISSING_FILES.md`: what isn't here, and why.
6. `PROJECT_FILE_STRUCTURE.md`: the app's files and this archive's layout.
7. `../11_HANDOVER_TO_NEW_ACCOUNT/HOW_TO_CONTINUE_IN_ANOTHER_CLAUDE_ACCOUNT.md`: moving the work to another Claude account.

## Most important files
| What | Where |
|---|---|
| Current source code, authoritative (v1.8.0) | `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/` |
| Windows installer (v1.8.0) | `09_ZIP_AND_PACKAGES/Release_Packages/JobRadar-Setup_v1.8.0.exe` |
| Installers for 1.4–1.7 (rebuilt) | `09_ZIP_AND_PACKAGES/Release_Packages/Rebuilt_Installers/` (see `Package_Notes/INSTALLERS_ALL_VERSIONS.md`) |
| User manual | `03_DOCUMENTS/Final_Documents/JobRadar_User_Manual_README_v1.8.0.md` |
| Requirements (the user's own words) | `01_PROJECT_BRIEF/OriginalRequirements/` |
| Decisions log | `01_PROJECT_BRIEF/Decisions/job-discovery-agent-decisions.md` |
| Version history and comparison | `02_VERSIONS_AND_HISTORY/` |
| Database schema and architecture | `07_SOURCE_FILES/Schemas/schema.sql`, `07_SOURCE_FILES/Technical_Documentation/ARCHITECTURE.md` |

## Folders
`00` start here · `01` brief · `02` versions and history · `03` documents · `04` research · `05` diagrams and design · `06` resources · `07` source · `08` outputs · `09` zip files and installer · `10` tests · `11` handover · `12` backup and recovery · `99` old material.

Folders without material contain a `_FOLDER_STATUS.md` that explains why. Nothing was invented to fill the structure. Files marked "Generated" in the index were written while preparing this archive.

## Privacy
- **No passwords or API keys are included.**
- `12_BACKUP_AND_RECOVERY/Recovered_Files/` holds the job database from the user's PC, which contains email addresses. Remove it before sharing the archive with anyone else.
