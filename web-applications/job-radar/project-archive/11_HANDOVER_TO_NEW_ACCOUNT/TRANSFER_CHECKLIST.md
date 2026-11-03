# Transfer checklist

## Check the archive
- [ ] Download `PROJECT_MASTER_ARCHIVE_2026-10-11.zip` and `PROJECT_MASTER_ARCHIVE_2026-10-11.zip.sha256`.
- [ ] Check the SHA-256: on Windows run `certutil -hashfile PROJECT_MASTER_ARCHIVE_2026-10-11.zip SHA256` and compare.
- [ ] Unzip it. Check that the folders `00_START_HERE` … `99_ARCHIVE_OLD` exist.
- [ ] Open `00_START_HERE/MASTER_FILE_INDEX.csv`. The number of rows should match the file count in `ARCHIVE_MANIFEST.txt`.
- [ ] Spot-check: the installer `09_ZIP_AND_PACKAGES/Release_Packages/JobRadar-Setup_v1.8.0.exe` and the source `07_SOURCE_FILES/SourceCode/JobRadar_v1.8.0/jobradar/mailer.py` are present.

## Privacy before sharing
- [ ] The archive holds personal data: email addresses, and the PC's job database in `12_BACKUP_AND_RECOVERY/Recovered_Files/`. Remove that folder before sharing with anyone else.
- [ ] Confirm there are no passwords. The archive was scanned for app-password and API-key patterns (see `ARCHIVE_MANIFEST.txt`).

## Transfer
- [ ] Copy the zip to the new account's storage, or upload it to the new assistant.
- [ ] Paste `11_HANDOVER_TO_NEW_ACCOUNT/CONTINUE_PROJECT_PROMPT.md`.
- [ ] Check the assistant's status summary against `PROJECT_STATUS.md`.

## Resume work
- [ ] Do `NEXT_STEPS.md` items 1–5 (install 1.8.0, test mail, schedules and OCR, revoke the exposed password).
- [ ] After any change: run the tests, then update the index, changelog and status.
