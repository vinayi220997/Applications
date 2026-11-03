# Next steps (in priority order)

1. **Restart Job Radar on the PC.** *(User. Blocks everything below.)*
   - The 1.8.0 files are already in the install folder.
   - Press **Restart now**, or reopen the app.
   - Expected result: the app shows version 1.8 features (the theme buttons at the top).
2. **Check mail on real Windows.** *(User, with the assistant)*
   - Mail tab: the migrated Gmail account should be listed.
   - Press **Test**, then **Send test** to vinayi220997@gmail.com.
   - This confirms DPAPI encryption and Gmail sign-in.
   - Expected result: the test email arrives, and the account shows "Connected".
3. **Check schedules on real Windows.**
   - Give a card a schedule, then press **Check setup**.
   - The task `JobRadar\Schedule-<id>` should exist in Task Scheduler.
   - Expected result: Check setup shows "Schedule: OK".
4. **Check OCR.** Settings → AI & OCR → **Test OCR** (Windows built-in OCR).
5. **Revoke the exposed app password.** It was once typed into the chat. Create a new one and press **Reconnect** in the Mail tab.
6. **Improve India coverage.** *(Optional)* Add an Adzuna app ID and key in Settings, and add target companies' careers pages.
7. **Possible next features** *(not requested yet; ask first)*:
   - a PDF or spreadsheet export of a card (the export spec mentioned it as optional)
   - email overrides per schedule
   - an update to the Flows artifact for versions 1.5–1.8.
