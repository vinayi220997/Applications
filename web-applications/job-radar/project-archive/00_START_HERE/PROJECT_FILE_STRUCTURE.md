# Project file structure

## 1. The Job Radar app (v1.8.0, as installed on the PC)
`07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/`. The installer copies this into `C:\Users\Admin\AppData\Local\Programs\JobRadar\`. On the PC it also gets `config\settings.json`, `config\secrets.json`, `data\` and `reports\`, which are never archived. `vendor/` (bundled pypdf) is collapsed here.

```
JobRadar/
├── config/  (1 files)
│   └── companies.json
├── installer/  (1 files)
│   └── jobradar.nsi
├── jobradar/  (30 files)
│   ├── sources/  (3 files)
│   │   ├── __init__.py
│   │   ├── ats.py
│   │   └── boards.py
│   ├── static/  (6 files)
│   │   ├── samples/  (5 files)
│   │   │   ├── job-search-brief.txt
│   │   │   ├── sample-job-post.png
│   │   │   ├── sample-job-post.txt
│   │   │   ├── sample-resume.docx
│   │   │   └── sample-voice.mp3
│   │   └── index.html   # the whole user interface
│   ├── __init__.py
│   ├── __main__.py   # command line: ui, run, doctor
│   ├── attachments.py   # resume, screenshots, voice
│   ├── cards.py   # job search cards, history, export/import
│   ├── config.py   # settings defaults
│   ├── db.py   # SQLite schema + migrations
│   ├── dedupe.py   # duplicate detection
│   ├── doctor.py   # Check setup
│   ├── freshness.py   # posting-age categories
│   ├── http.py   # web requests
│   ├── intake.py   # chat questionnaire
│   ├── mailer.py   # Gmail accounts, templates, sending, email history
│   ├── matching.py   # scoring
│   ├── normalize.py   # cleans titles, places, work modes
│   ├── pipeline.py   # scan: fetch, verify, dedupe, rank, email
│   ├── report.py   # HTML report
│   ├── scheduler.py   # Windows Task Scheduler tasks
│   ├── schedules.py   # schedules + conflicts
│   ├── services.py   # AI / OCR status
│   ├── verify.py   # is the job still open
│   └── web.py   # local web server + JSON API
├── tests/  (1 files)
│   └── test_core.py
├── .gitignore
├── jobradar.ico
├── README.md
├── Scan Now.bat
├── Start Job Radar.bat
└── start.sh
```

## 2. This archive
```
PROJECT_MASTER_ARCHIVE/
├── 00_START_HERE/  (5 files)
│   ├── ARCHIVE_MANIFEST.txt
│   ├── MASTER_FILE_INDEX.csv
│   ├── PROJECT_OVERVIEW.md
│   ├── PROJECT_STATUS.md
│   └── README.md
├── 01_PROJECT_BRIEF/  (9 files)
│   ├── Decisions/  (1 files)
│   ├── OriginalRequirements/  (6 files)
│   ├── Scope_and_Objectives/  (1 files)
│   └── Specifications/  (1 files)
├── 02_VERSIONS_AND_HISTORY/  (73 files)
│   ├── Final_Versions/  (1 files)
│   ├── Original_Versions/  (1 files)
│   ├── Reviewed_Versions/  (1 files)
│   ├── WorkingVersions/  (66 files)
│   ├── CHANGELOG.md
│   ├── PROJECT_CONVERSATION_LOG_redacted.md
│   ├── VERSION_COMPARISON.md
│   └── VERSION_HISTORY.md
├── 03_DOCUMENTS/  (6 files)
│   ├── Drafts/  (1 files)
│   ├── Final_Documents/  (1 files)
│   ├── Original_Documents/  (1 files)
│   ├── Presentations/  (1 files)
│   ├── Proposals/  (1 files)
│   └── Reports/  (1 files)
├── 04_RESEARCH_AND_REFERENCES/  (6 files)
│   ├── Evidence/  (1 files)
│   ├── Reference_Documents/  (1 files)
│   ├── Research_Notes/  (1 files)
│   ├── Source_Papers/  (1 files)
│   ├── Web_References/  (1 files)
│   └── SOURCE_REGISTER.csv
├── 05_DIAGRAMS_AND_DESIGN/  (9 files)
│   ├── Architecture/  (1 files)
│   ├── Diagram_Exports/  (1 files)
│   ├── Editable_Diagrams/  (1 files)
│   ├── Flowcharts/  (1 files)
│   ├── UML_and_Data_Models/  (1 files)
│   ├── Visual_Designs/  (3 files)
│   └── Wireframes/  (1 files)
├── 06_RESOURCES_AND_ASSETS/  (13 files)
│   ├── Datasets/  (1 files)
│   ├── Icons/  (1 files)
│   ├── Images/  (4 files)
│   ├── Licenses_and_Attribution/  (1 files)
│   ├── Media/  (2 files)
│   ├── Supporting_Resources/  (1 files)
│   └── Templates/  (3 files)
├── 07_SOURCE_FILES/  (544 files)
│   ├── Configuration/  (1 files)
│   ├── Dependencies/  (1 files)
│   ├── Schemas/  (1 files)
│   ├── Scripts/  (1 files)
│   ├── SourceCode/  (539 files)
│   └── Technical_Documentation/  (1 files)
├── 08_OUTPUTS_AND_DELIVERABLES/  (5 files)
│   ├── Approved_Deliverables/  (1 files)
│   ├── Exports/  (1 files)
│   ├── Generated_Outputs/  (1 files)
│   ├── Presentations/  (1 files)
│   └── Reports/  (1 files)
├── 09_ZIP_AND_PACKAGES/  (11 files)
│   ├── Existing_Packages/  (1 files)
│   ├── Original_Archives/  (3 files)
│   ├── Package_Notes/  (1 files)
│   └── Release_Packages/  (6 files)
├── 10_TESTS_AND_VALIDATION/  (46 files)
│   ├── Known_Issues/  (1 files)
│   ├── Quality_Checks/  (14 files)
│   ├── Screenshots/  (29 files)
│   ├── Test_Results/  (1 files)
│   └── Validation_Reports/  (1 files)
├── 11_HANDOVER_TO_NEW_ACCOUNT/  (7 files)
│   ├── CONTINUE_PROJECT_PROMPT.md
│   ├── HANDOVER_GUIDE.md
│   ├── HOW_TO_CONTINUE_IN_ANOTHER_CLAUDE_ACCOUNT.md
│   ├── NEXT_STEPS.md
│   ├── OPEN_ISSUES.md
│   ├── PROJECT_CONTEXT.md
│   └── TRANSFER_CHECKLIST.md
├── 12_BACKUP_AND_RECOVERY/  (6 files)
│   ├── Duplicate_Review/  (1 files)
│   ├── Original_File_Copies/  (1 files)
│   ├── Recovered_Files/  (2 files)
│   ├── Recovery_Notes/  (1 files)
│   └── MISSING_FILES.md
└── 99_ARCHIVE_OLD/  (13 files)
    ├── Deprecated_Materials/  (1 files)
    ├── Historical_Artifacts/  (4 files)
    └── Superseded_Drafts/  (8 files)
```
`00_START_HERE` also gets `README.md`, `ARCHIVE_MANIFEST.txt` and `MASTER_FILE_INDEX.csv` when the archive is finalised. The index lists every file with its SHA-256.

## 3. Versions at a glance
| Version | Full source | Installer |
|---|---|---|
| Early builds A/B | `09_ZIP_AND_PACKAGES/Original_Archives/JobRadar_build-*.zip` | none (zip + .bat) |
| 1.4.0 | `07_SOURCE_FILES/SourceCode/JobRadar_v1.4.0_as-zipped/` | `Release_Packages/Rebuilt_Installers/…v1.4.0_as-zipped…exe` |
| 1.4.0 + 10 Oct update | `…/JobRadar_v1.4.0_with-10Oct-update_reconstructed/` | `…v1.4.0_with-10Oct-update_rebuilt.exe` |
| 1.5.0 | `…/JobRadar_v1.5.0_reconstructed/` | `…v1.5.0_rebuilt.exe` |
| 1.6.0 | `…/JobRadar_v1.6.0_reconstructed/` | `…v1.6.0_rebuilt.exe` |
| 1.7.0 | `…/JobRadar_v1.7.0_reconstructed/` | `…v1.7.0_rebuilt.exe` |
| **1.8.0 (current)** | `…/JobRadar_v1.8.0/` (authoritative) | `Release_Packages/JobRadar-Setup_v1.8.0.exe` (original) |
