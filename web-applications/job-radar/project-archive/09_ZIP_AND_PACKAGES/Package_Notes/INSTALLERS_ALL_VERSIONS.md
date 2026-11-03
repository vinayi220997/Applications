# Installers for every version

| Version | File | How it was made | SHA-256 (first 16) |
|---|---|---|---|
| 1.4.0 | `Release_Packages/Rebuilt_Installers/JobRadar-Setup_v1.4.0_as-zipped-2026-10-10_rebuilt.exe` | Rebuilt from JobRadar.zip exactly as packaged (16:50 UTC, 10 Oct); installer script inside the zip says 1.4.0 | `a1ae459a7bcb34ee` |
| 1.4.0 + update | `Release_Packages/Rebuilt_Installers/JobRadar-Setup_v1.4.0_with-10Oct-update_rebuilt.exe` | JobRadar.zip + the 10 Oct bug-fix update folder (the state the PC had before 1.5) | `a6fd0d0fff76974b` |
| 1.5.0 | `Release_Packages/Rebuilt_Installers/JobRadar-Setup_v1.5.0_rebuilt.exe` | 1.4 + update + the 1.5.0 delta shipped to the PC | `44dcd1bf75e68909` |
| 1.6.0 | `Release_Packages/Rebuilt_Installers/JobRadar-Setup_v1.6.0_rebuilt.exe` | 1.5 tree + the 1.6.0 delta shipped to the PC | `795f17e5f942665f` |
| 1.7.0 | `Release_Packages/Rebuilt_Installers/JobRadar-Setup_v1.7.0_rebuilt.exe` | 1.6 tree + the 1.7.0 delta | `dd9dadab7cae99f9` |
| 1.8.0 | `Release_Packages/JobRadar-Setup_v1.8.0.exe` | Original build of 11 Oct 08:11 UTC (current release) | `4861d12955644f98` |

## How the old versions were rebuilt
The original 1.4–1.7 installers were overwritten (every build wrote `JobRadar-Setup.exe`). They were rebuilt on 2026-10-11:
1. **1.4.0 as zipped**: `JobRadar.zip` (found in the archive and, identical, in the PC's Downloads) built with its own installer script.
2. **1.4.0 + update**: that tree plus the 10 Oct bug-fix `update/` folder.
3. **1.5.0, 1.6.0, 1.7.0**: each previous tree plus that version's delta folder (the exact files copied to the PC), with the installer script's version number set.

**Check of the method:** applying the 1.8.0 delta to the rebuilt 1.7.0 tree gives exactly the current 1.8.0 source. Every program file matches. The only differences are 2 sample files (a PNG and an MP3 regenerated later) and the tests, which installers don't include.

**Limits:**
- These are new builds of the same files, not the original binaries. Their checksums differ from the lost originals.
- A change made in a version but shipped only in a later delta would appear one version late. The 1.8.0 check shows no change was lost overall.
- No old tests exist for 1.5–1.7, so those trees were checked only by compiling and importing, not by unit tests.
- Installing an old version over a newer one keeps `data/` and `config/`. The newer database tables stay and are ignored by older code. Back up `data\jobradar.db` first.

## Early zip builds (no installer)
`Original_Archives/JobRadar_build-A_2026-10-10_1613.zip` and `JobRadar_build-B_2026-10-10_1621.zip` came from the PC's Downloads (`JobRadar_1.zip` and `JobRadar_2.zip`; `JobRadar_3.zip` is identical to `_2`). They predate the installer and carry no version number. To run one: unzip, then `Start Job Radar.bat`.
