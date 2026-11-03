# Job Radar

A local job discovery agent for Windows, written in Python. You describe the job you want (in a chat or a questionnaire), and Job Radar scans job boards and company career pages, removes duplicates and closed jobs, ranks the rest against your search, and emails you a daily report with direct apply links. It runs on your own PC, on demand or on a schedule you pick, with a web UI at `http://127.0.0.1:8765`.

**Current version: 1.9.0** (Admin and Public editions).

## Download

| Version | Date | Installer |
|---|---|---|
| **1.9.0 Admin** | 2026-10-12 | [`installers/JobRadar-Admin-Setup_v1.9.0.exe`](installers/JobRadar-Admin-Setup_v1.9.0.exe) |
| **1.9.0 Public** | 2026-10-12 | [`installers/JobRadar-Setup_v1.9.0_Public.exe`](installers/JobRadar-Setup_v1.9.0_Public.exe) |
| 1.8.1 | 2026-10-12 | [`installers/JobRadar-Setup_v1.8.1.exe`](installers/JobRadar-Setup_v1.8.1.exe) |
| 1.8.0 | 2026-10-11 | [`installers/JobRadar-Setup_v1.8.0.exe`](installers/JobRadar-Setup_v1.8.0.exe) |
| 1.7.0 | 2026-10-11 | [`installers/JobRadar-Setup_v1.7.0_rebuilt.exe`](installers/JobRadar-Setup_v1.7.0_rebuilt.exe) |
| 1.6.0 | 2026-10-11 | [`installers/JobRadar-Setup_v1.6.0_rebuilt.exe`](installers/JobRadar-Setup_v1.6.0_rebuilt.exe) |
| 1.5.0 | 2026-10-10 | [`installers/JobRadar-Setup_v1.5.0_rebuilt.exe`](installers/JobRadar-Setup_v1.5.0_rebuilt.exe) |
| 1.4.0 + 10 Oct update | 2026-10-10 | [`installers/JobRadar-Setup_v1.4.0_with-10Oct-update_rebuilt.exe`](installers/JobRadar-Setup_v1.4.0_with-10Oct-update_rebuilt.exe) |
| 1.4.0 | 2026-10-10 | [`installers/JobRadar-Setup_v1.4.0_as-zipped-2026-10-10_rebuilt.exe`](installers/JobRadar-Setup_v1.4.0_as-zipped-2026-10-10_rebuilt.exe) |

Installers marked *rebuilt* were rebuilt from the saved source after the originals were overwritten. See [`installers/INSTALLERS_ALL_VERSIONS.md`](installers/INSTALLERS_ALL_VERSIONS.md). Windows SmartScreen may warn because the installers aren't code-signed.

## Folder layout

```
job-radar/
├── app/                 current source (v1.9.0): run, test and build from here
│   ├── jobradar/        Python package: pipeline, sources, matching, mailer, web UI (static/index.html)
│   ├── vendor/pypdf/    bundled PDF reader
│   ├── tests/           unit tests
│   ├── installer/       NSIS installer script
│   └── config/          companies.json (career pages to scan)
├── versions/            full source of every earlier version (1.4.0 → 1.8.0)
├── installers/          Windows installers for every version
├── project-archive/     requirements, decisions, specs, research, diagrams, test evidence,
│                        handover docs and the redacted project history
└── CHANGELOG.md
```

## Run from source

Needs Python 3.9 or newer; nothing else to install.

```
cd app
python -m jobradar ui                    # opens http://127.0.0.1:8765
python -m unittest tests.test_core       # run the tests
```

## Build the installer

On Linux with NSIS installed:

```
cd app/installer
makensis jobradar.nsi
```

The script here is the 1.8.0 one. The 1.9.0 script added `-DEDITION=public` for the Public build; until it's restored, set the edition by editing `app/jobradar/edition.json` (`"admin"` or `"public"`) before building.

## Project rules

- No scraping of sites without an API, no bypassing logins or CAPTCHAs.
- Never invent jobs, dates or links; publication date is never guessed from discovery date.
- Never auto-apply to jobs.
- Gmail app passwords and API keys are typed into the app only. They are stored encrypted (Windows DPAPI) in `config/secrets.json`, which is never committed.

## What is not in this repo

- `config/secrets.json`, `config/settings.json`, `data/` (the job database, logs, uploaded files) and `reports/`: these are personal and stay on the PC.
- The PC database snapshot that was in the archive's `12_BACKUP_AND_RECOVERY/Recovered_Files/`.

## Known gaps

- `app/tests/` and `app/installer/jobradar.nsi` are the 1.8.0 copies; the 1.9.0 versions (84 tests, `-DEDITION` support) weren't on the PC. The 1.8.0 tests pass against the 1.9.0 code (79 run, 2 skipped).
- Source trees for 1.5.0–1.7.0 are reconstructions (see `installers/INSTALLERS_ALL_VERSIONS.md`).
