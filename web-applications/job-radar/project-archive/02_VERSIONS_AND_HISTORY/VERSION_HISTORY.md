# Version history

Dates are file modification times (UTC) in the sandbox, plus delivery events recorded in this session. Version numbers 1.1–1.3 were never recorded as separate releases. The installer was at 1.4.0 by the evening of 2026-10-10.

| Version | Date (UTC) | What exists in this archive | Status | Relationship |
|---|---|---|---|---|
| 0 – web artifact | 2026-10-10 ~09:35 | `99_ARCHIVE_OLD/Historical_Artifacts/claude-web-artifact-v0/` (local source) and the published copy | Superseded | Replaced by the local agent |
| Early builds A and B | 2026-10-10 16:13 and 16:21 | `09_ZIP_AND_PACKAGES/Original_Archives/JobRadar_build-A_…zip`, `…build-B_…zip` (from the PC's Downloads) | Superseded | Before the installer existed; no version number |
| 1.4.0 package | 2026-10-10 16:50 | `09_ZIP_AND_PACKAGES/Original_Archives/JobRadar.zip` (101 entries; its installer script says 1.4.0) | Superseded | First package with an installer script. Earlier versions of this table called it 1.0 |
| Demo UI | 2026-10-10 16:20 | `05_DIAGRAMS_AND_DESIGN/VisualDesigns/` (local source, mock data, published copy) | Reference | Mock-up of the app's UI |
| Update 2026-10-10 17:22 | 2026-10-10 17:22 | `02_VERSIONS_AND_HISTORY/WorkingVersions/update_2026-10-10_1722/` (full `jobradar/` package) | Superseded | Copied to the PC as a bug-fix update |
| Flows diagrams | 2026-10-10 19:04 | `05_DIAGRAMS_AND_DESIGN/Flowcharts/` | Reference (about v1.4) | Documents every app flow at that time |
| 1.4.0 installer | 2026-10-10 | Original missing (overwritten). **Rebuilt:** `09_ZIP_AND_PACKAGES/Release_Packages/Rebuilt_Installers/` (two builds: as zipped, and with the 10 Oct update) | Rebuilt | From `JobRadar.zip` |
| UI before 1.5 | 2026-10-11 04:09 | `99_ARCHIVE_OLD/SupersededDrafts/index.before_v1.5.html` | Superseded | `static/index.html` as of 1.4 |
| 1.5.0 delta | 2026-10-11 04:21 | `02_VERSIONS_AND_HISTORY/WorkingVersions/v1.5.0_delta/` | Superseded; deployed to PC | Only the changed files |
| 1.6.0 delta | 2026-10-11 05:51 | `…/v1.6.0_delta/` | Superseded; deployed to PC | Only the changed files |
| 1.7.0 delta | 2026-10-11 07:17 | `…/v1.7.0_delta/` | Superseded | Only the changed files |
| 1.8.0 delta | 2026-10-11 08:11 | `…/v1.8.0_delta/` | Current; **on the PC** (copied 2026-10-11) | Only the changed files |
| 1.8.0 full source | 2026-10-11 | `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/` | **Authoritative source** | Full tree (secrets and runtime data excluded) |
| 1.8.0 installer | 2026-10-11 08:11 | `09_ZIP_AND_PACKAGES/Release_Packages/JobRadar-Setup_v1.8.0.exe` | Current release; not approved by the user yet | Built from the 1.8.0 source with makensis |

"Delta" folders hold only the files that were copied to the PC for that update. Each one is a partial snapshot, not a complete version. The original 1.4–1.7 installers were overwritten by later builds. On 2026-10-11 they were **rebuilt** from the zip, the update folder and the deltas. Full source trees for those versions are in `07_SOURCE_FILES/SourceCode/JobRadar_v1.x.0_reconstructed/`. See `09_ZIP_AND_PACKAGES/Package_Notes/INSTALLERS_ALL_VERSIONS.md`.
