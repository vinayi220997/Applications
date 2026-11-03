# Version comparison
Generated from the actual files in this archive. Line counts compare each delta file with the matching file in the current 1.8.0 source.

## v1.0 package (JobRadar.zip) vs current 1.8.0 source
- Files only in 1.8.0 (9): jobradar/cards.py, jobradar/mailer.py, jobradar/schedules.py, jobradar/services.py, jobradar/static/samples/job-search-brief.txt, jobradar/static/samples/sample-job-post.png, jobradar/static/samples/sample-job-post.txt, jobradar/static/samples/sample-resume.docx, jobradar/static/samples/sample-voice.mp3
- Files only in v1.0 (0): none

| File | Lines v1.0 | Lines 1.8.0 | Added | Removed |
|---|---|---|---|---|
| README.md | 123 | 169 | +74 | -28 |
| installer/jobradar.nsi | 144 | 144 | +2 | -2 |
| jobradar/__main__.py | 88 | 113 | +36 | -11 |
| jobradar/attachments.py | 263 | 300 | +83 | -46 |
| jobradar/config.py | 89 | 94 | +6 | -1 |
| jobradar/db.py | 98 | 161 | +64 | -1 |
| jobradar/doctor.py | 88 | 117 | +61 | -32 |
| jobradar/http.py | 66 | 70 | +4 | -0 |
| jobradar/intake.py | 332 | 792 | +487 | -27 |
| jobradar/matching.py | 206 | 221 | +22 | -7 |
| jobradar/normalize.py | 222 | 288 | +67 | -1 |
| jobradar/pipeline.py | 511 | 685 | +196 | -22 |
| jobradar/report.py | 187 | 234 | +54 | -7 |
| jobradar/scheduler.py | 159 | 282 | +126 | -3 |
| jobradar/sources/boards.py | 161 | 171 | +17 | -7 |
| jobradar/static/index.html | 592 | 2370 | +1981 | -203 |
| jobradar/web.py | 298 | 645 | +393 | -46 |
| tests/test_core.py | 416 | 969 | +560 | -7 |

## update_2026-10-10_1722 vs current 1.8.0

| File in delta | Identical to 1.8.0? | Lines (delta → 1.8.0) |
|---|---|---|
| jobradar/__init__.py | yes | 0 → 0 |
| jobradar/__main__.py | no | 90 → 113 |
| jobradar/attachments.py | no | 265 → 300 |
| jobradar/config.py | no | 89 → 94 |
| jobradar/db.py | no | 98 → 161 |
| jobradar/dedupe.py | yes | 61 → 61 |
| jobradar/doctor.py | no | 104 → 117 |
| jobradar/freshness.py | yes | 33 → 33 |
| jobradar/http.py | yes | 70 → 70 |
| jobradar/intake.py | no | 548 → 792 |
| jobradar/matching.py | no | 218 → 221 |
| jobradar/normalize.py | no | 259 → 288 |
| jobradar/pipeline.py | no | 577 → 685 |
| jobradar/report.py | no | 193 → 234 |
| jobradar/scheduler.py | no | 159 → 282 |
| jobradar/sources/__init__.py | yes | 0 → 0 |
| jobradar/sources/ats.py | yes | 190 → 190 |
| jobradar/sources/boards.py | yes | 171 → 171 |
| jobradar/static/index.html | no | 663 → 2370 |
| jobradar/verify.py | yes | 42 → 42 |
| jobradar/web.py | no | 345 → 645 |

## v1.5.0_delta vs current 1.8.0

| File in delta | Identical to 1.8.0? | Lines (delta → 1.8.0) |
|---|---|---|
| README.md | no | 135 → 169 |
| jobradar/attachments.py | yes | 300 → 300 |
| jobradar/config.py | no | 91 → 94 |
| jobradar/intake.py | no | 754 → 792 |
| jobradar/services.py | yes | 277 → 277 |
| jobradar/static/index.html | no | 1264 → 2370 |
| jobradar/static/samples/job-search-brief.txt | yes | 20 → 20 |
| jobradar/static/samples/sample-job-post.png | no | — |
| jobradar/static/samples/sample-job-post.txt | yes | 25 → 25 |
| jobradar/static/samples/sample-resume.docx | yes | — |
| jobradar/static/samples/sample-voice.mp3 | no | — |
| jobradar/web.py | no | 391 → 645 |

## v1.6.0_delta vs current 1.8.0

| File in delta | Identical to 1.8.0? | Lines (delta → 1.8.0) |
|---|---|---|
| README.md | no | 157 → 169 |
| jobradar/__main__.py | yes | 113 → 113 |
| jobradar/attachments.py | yes | 300 → 300 |
| jobradar/cards.py | no | 328 → 465 |
| jobradar/config.py | no | 91 → 94 |
| jobradar/db.py | no | 140 → 161 |
| jobradar/doctor.py | no | 119 → 117 |
| jobradar/intake.py | no | 792 → 792 |
| jobradar/matching.py | yes | 221 → 221 |
| jobradar/normalize.py | yes | 288 → 288 |
| jobradar/pipeline.py | no | 694 → 685 |
| jobradar/scheduler.py | yes | 282 → 282 |
| jobradar/schedules.py | yes | 352 → 352 |
| jobradar/services.py | yes | 277 → 277 |
| jobradar/static/index.html | no | 1939 → 2370 |
| jobradar/web.py | no | 488 → 645 |

## v1.7.0_delta vs current 1.8.0

| File in delta | Identical to 1.8.0? | Lines (delta → 1.8.0) |
|---|---|---|
| README.md | no | 162 → 169 |
| jobradar/cards.py | no | 463 → 465 |
| jobradar/config.py | yes | 94 → 94 |
| jobradar/db.py | no | 142 → 161 |
| jobradar/doctor.py | yes | 117 → 117 |
| jobradar/mailer.py | no | 942 → 960 |
| jobradar/pipeline.py | yes | 685 → 685 |
| jobradar/report.py | yes | 234 → 234 |
| jobradar/static/index.html | no | 2253 → 2370 |
| jobradar/web.py | no | 625 → 645 |

## v1.8.0_delta vs current 1.8.0

| File in delta | Identical to 1.8.0? | Lines (delta → 1.8.0) |
|---|---|---|
| README.md | yes | 169 → 169 |
| jobradar/cards.py | yes | 465 → 465 |
| jobradar/db.py | yes | 161 → 161 |
| jobradar/intake.py | yes | 792 → 792 |
| jobradar/mailer.py | yes | 960 → 960 |
| jobradar/static/index.html | yes | 2370 → 2370 |
| jobradar/web.py | yes | 645 → 645 |

## Which version to use
- **Building, running or changing the app:** `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/`.
- **Installing on Windows:** `09_ZIP_AND_PACKAGES/Release_Packages/JobRadar-Setup_v1.8.0.exe`.
- **Matching what is on the PC right now (1.7.0):** the 1.8.0 source with the files from `v1.7.0_delta` and earlier deltas applied. No full 1.7.0 tree was kept.
