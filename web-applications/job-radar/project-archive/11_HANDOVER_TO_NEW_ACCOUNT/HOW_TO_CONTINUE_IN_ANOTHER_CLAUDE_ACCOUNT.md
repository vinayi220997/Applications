# How to continue this project in another Claude account

## The short answer
Claude has **no "clone this project" link between accounts**. Chats, Project memory and session workspaces stay with the account that made them. Everything needed to continue is in this archive, so moving the work means: **put the ZIP somewhere the new account can reach, create a Project there, and paste the continuation prompt.**

Job Radar itself does **not** depend on any Claude account. It runs on the PC with Python, Gmail and Task Scheduler. Switching Claude accounts doesn't stop or change the installed app.

## Option 1: a "master link" (recommended)
Make one link that always gives the whole project:
1. Upload `PROJECT_MASTER_ARCHIVE_2026-10-11.zip` (and its `.sha256`) to **Google Drive, OneDrive or a private GitHub repo**.
2. Share it with the other account's email address, or as "anyone with the link" if you accept that risk.
3. When the project changes later, replace the file, or add a new dated ZIP in the same folder. The folder link stays the same.

Before sharing outside your own accounts, remove `12_BACKUP_AND_RECOVERY/Recovered_Files/`. It holds the PC's job database, which contains email addresses.

A private GitHub repo is the best "clone" link for code. The new account (or any developer) can `git clone` it, and every version is kept as history.

## Option 2: set up the new account (10 minutes)
1. In the new account, create a **Project** called "Job Radar" and add these files as project knowledge:
   - `11_HANDOVER_TO_NEW_ACCOUNT/CONTINUE_PROJECT_PROMPT.md`, `PROJECT_CONTEXT.md`, `NEXT_STEPS.md`, `OPEN_ISSUES.md`
   - `01_PROJECT_BRIEF/Specifications/job-discovery-agent-spec.md` and `01_PROJECT_BRIEF/Decisions/job-discovery-agent-decisions.md`
   - `00_START_HERE/PROJECT_FILE_STRUCTURE.md`
2. Start a new task in that Project (Cowork, so it has a workspace and can build installers).
3. Attach the ZIP, or give its Drive/GitHub link if that app is connected in the new account.
4. Paste the text of `CONTINUE_PROJECT_PROMPT.md` as the first message.
5. To let the new account update the PC directly, open the desktop app signed in to the new account, link the computer and connect the folder `C:\Users\Admin\AppData\Local\Programs\JobRadar`.
6. Check that the assistant's summary matches `00_START_HERE/PROJECT_STATUS.md` before asking for new features.

## Option 3: same organization (Team or Enterprise plan)
If both accounts belong to the same Claude organization, the Project can be **shared** with the other member from the Project's sharing settings. No copying is needed. This doesn't work between separate personal accounts.

## What moves and what doesn't
| Item | Moves? | How |
|---|---|---|
| Source code, installers, all versions | Yes | The ZIP |
| Requirements, decisions, status, next steps | Yes | Docs in the ZIP plus project knowledge |
| Conversation history | Partly | Redacted log: `02_VERSIONS_AND_HISTORY/PROJECT_CONVERSATION_LOG_redacted.md` |
| Published artifacts (Job Radar page, Demo, Flows) | View only | Share their links from this account. To own them in the new account, republish the HTML copies in the archive |
| Claude Project memory and settings | No | Re-create from the docs above |
| Gmail app password and API keys | No, on purpose | They stay on the PC. Enter them again only if you reinstall |
| The app installed on the PC | Not needed | It keeps running regardless of the Claude account |
