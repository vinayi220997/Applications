# Job Radar: a local job discovery agent

Job Radar runs on your own computer. You describe the job you want, it asks a few questions to fill in what's missing (location, experience, work arrangement, skills, pay, things to avoid), and then it scans job sources, removes duplicates and closed jobs, ranks what's left against the search, and gives you direct application links. It runs when you start it, or on a schedule you choose.

Several people can use one installation. Each person adds their own search and, if they like, their own email address for the daily report.

## 1. Install (Windows, about 5 minutes)

1. Install **Python 3.9 or newer** from https://www.python.org/downloads/. On the first installer screen, tick **"Add python.exe to PATH"**.
2. Unzip this folder somewhere permanent, for example `Documents\JobRadar`.
3. Double-click **`Start Job Radar.bat`**. Your browser opens at `http://127.0.0.1:8765`.

There's nothing else to install. Job Radar uses Python's standard library plus a bundled PDF reader in `vendor/`. On macOS or Linux, run `./start.sh`.

## 2. Use it

Under **Find jobs**, pick how to describe the job:

- **Chart mode**: a chat that asks one question at a time (described below).
- **Questionnaire mode**: one form with every question: job titles, experience, several **cities** (removable chips, quick-add buttons, misspellings like "bengular" are fixed), **work modes** (Hybrid, Remote, On-site; pick any combination, none = any), skills, industries, salary, things to avoid, email and notes. **Upload file** fills the form from a resume, job post or the sample **Job search brief**; fields marked *from file* should be checked before saving.

You can switch modes at any time; your answers are carried across. (Industries, employment type and notes aren't asked in the chat, but they're kept.)

Chart mode:

1. Describe the job in your own words, for example *"Python backend developer, Django and AWS, fintech, Bengaluru or remote"*.
2. Answer the follow-up questions. It asks only about what you didn't already mention. The bar above the chat shows **Question X of 10** and which sections are done (✓), current and still to come.
   - After each answer you see what was understood. Press **Confirm** to go on, **Edit** to correct your words, or **Change** to answer again. You can also just type a different answer. Pressing Enter in an empty box confirms.
   - To change an earlier answer, click its ✓ in the bar or open **Review my answers**. Nothing else is lost.
   - On the final card, **Edit** asks which sections to change (pick one or several). For each one choose **Overwrite existing**, **Add to existing** or **Edit existing** (remove or correct single items), check the before → after preview, and confirm.
3. Press **Save and scan**. The search becomes a **job search card**. A first scan takes about 1 to 3 minutes. Results (tab **Results**) show:
   - the match score, why it matches, and what's missing or uncertain
   - the job description
   - the posting date (or "unknown" when the source doesn't give one), when Job Radar first saw it, and when it was last verified
   - whether the job is Verified active, Appears active, or Unable to verify
   - **Apply**, the company careers page, and the original source
4. Mark jobs as **Save**, **Applied** or **Dismiss**. Applied and dismissed jobs aren't reported again.

### Job search cards

Every saved search is a card in the **Job search cards** tab. A card shows its cities, work modes, input mode (Chart or Questionnaire), where the answers came from (manual entry, uploaded file, screenshot, voice, AI-assisted, imported file), its status (Not Started, Ready, Running, Completed, Failed, Stopped, Disabled), its schedules and next run, the latest search (time, jobs found, new jobs, duration, errors) and the latest email (time, Sent / Failed / Skipped / Scheduled / Not Scheduled, jobs included, errors). A search that completed is shown separately from whether its email was really sent.

- **On/Off switch**: an off card never runs or emails automatically, even if a schedule includes it. Its results, history and settings stay; switch it back on any time.
- **Run search**, **View results**, **Edit card** (reopens it in the mode it was made with, with all answers loaded; **Change input mode** converts it, and nothing changes until you save. **Save changes** updates the same card; **Save as new card** makes a copy), **Schedule**, **History**.
- **More**: **Export card**, **Duplicate card** (the copy starts turned off), **Email results now**, change the email, turn the daily email on/off, **Delete card** (asks first).
- **History** has three tabs: every event (created, edited, turned on/off, searches started/completed/failed, emails sent/skipped/failed, exported/imported, schedule changes), every search run with its counts, and every email.

### Export and import

**Export card** downloads a `.json` file with the card's settings and answers, its input mode and its own schedule. Passwords, API keys, email settings, results and history are never included; the report email address only if you tick it. **Import card** checks the file and its version, shows a preview, and asks whether to create a new card or update an existing one (history is kept). **Review and edit first** opens it in its mode so you can change it before saving.

### Attachments, screenshots and voice

Under the message box in **Find jobs** there are three buttons:

- **Attach** opens a panel that lists the supported files (PDF, Word .docx, TXT, MD, RTF, PNG, JPG, WEBP, GIF and audio, up to 15 MB each, 10 per message) and offers sample files: a **Job search brief** to fill in and attach (the fastest way to set up a search), a sample resume, a sample job post and a sample screenshot. After a file is read you get a **review** box: remove any detail that's wrong, correct the extracted text and press **Re-read**, then **Use these details**.
- **Screenshot**: choose a window or browser tab, for example a job post open on LinkedIn or Naukri. Its text is read with OCR and shown for review. You can also press **Win+Shift+S** and then **Ctrl+V** in the message box.
- **Voice** opens a panel with a **sample voice note** (play or download it), then **Start recording**, **Stop**, play it back, **Re-record**, and an editable transcript to check before **Use this recording**. Transcription uses the browser's speech service in Microsoft Edge or Google Chrome (needs internet). In other browsers the recording is saved and you type the details.

### AI, OCR and offline mode

The status button next to **Find jobs** shows **Online** (AI connected), **Offline mode**, **Processing…**, **Success** or **Error**, with chips for AI, OCR and voice. Click it for the **Chat status** table.

Under **Settings → AI & OCR configuration** (both optional):

- **AI processing**: Anthropic Claude understands descriptions, documents and screenshot text better than the built-in rules. Add an API key, pick a model, and press **Test AI connection**. A saved key is never shown again; only its last 4 characters.
- **OCR**: reads text from images. **Automatic** uses Windows' built-in OCR (Windows 10/11, offline, free), then Tesseract if installed, then Claude vision if AI is set up. Press **Test OCR** to check it on a sample image.

Without AI or OCR the chat still works: you can type, review, confirm, edit and save everything by hand, and Job Radar never says it read an image when it didn't. PDF and Word files are always read on your computer. Attachments are stored in `data/attachments` and are deleted when you delete the search.

## 3. Schedule it

There are two ways, and you can use both:

- **A card's own schedule**: press **Schedule** on a card, then **Give it its own schedule**.
- **Shared schedules**: in the **Schedules** tab, press **Create schedule**, give it a name (for example "Morning search"), and tick the cards it should run.

Each schedule has a frequency (daily, weekly on chosen days, or every few hours until midnight), a time and a time zone, and an On/Off switch. The Schedules tab lists every schedule with its cards, next run and last result, plus **Edit**, **Run now**, **History** and **Delete**. A schedule can be marked **Add new cards to this schedule automatically**.

- Each schedule becomes its own Windows Task Scheduler task (`JobRadar\Schedule-<number>`), so it runs even when the Job Radar window is closed. If the computer was off or asleep, it runs as soon as it's back on.
- Turned-off cards and paused schedules never run.
- If a card is in two active schedules, Job Radar warns you and asks you to confirm. Unless you confirmed it, a card that already ran in the last 15 minutes is skipped (and the skip is recorded in its history). Two schedules due at the same time run one after the other, never on top of each other.
- If a schedule fails, the card shows the error and **History → Retry** runs it again.
- A schedule saved with an older version becomes **Default schedule**, linked to every card.

From a terminal: `py -m jobradar schedule 08:00 [--days MON,TUE] [--every-hours 4]` sets the default schedule, `py -m jobradar unschedule` pauses all schedules, and `py -m jobradar status` lists cards and schedules.

To scan right now without opening the app, double-click **`Scan Now.bat`** or run `py -m jobradar run`.

## 4. Email reports (optional)

Open **Settings** and fill in:

- **Send reports by email**: tick this box.
- **Sending Gmail address**: the account the reports are sent from.
- **Gmail app password**: create one at myaccount.google.com → Security → App passwords. This needs 2-Step Verification turned on.

Press **Save settings**, then **Send test email**. Each search's report goes to the email address saved with that search. The password is stored only in `config/settings.json` on this computer. Instead of saving it there, you can set the `JOBRADAR_SMTP_PASSWORD` environment variable.

## 4a. Not getting emails? Press Check setup

The **Check setup** button (or `py -m jobradar doctor`) tests each step and tells you what to fix:

1. **Email sending is off.** This is the default, so reports are only saved in the app. Open **Settings**, tick *Send reports by email*, enter the Gmail address that sends the reports and a Gmail **app password** (not your normal password), then **Save** and **Send test email**.
2. **Gmail rejected the sign-in.** Create an app password at myaccount.google.com/apppasswords. 2-Step Verification must be on.
3. **The search has no email address.** Press **Add email** on the search card.
4. **No new matches.** Widen the search: add more job titles or cities, allow remote, or remove the minimum salary. You can also add your target companies' careers pages.
5. **Job sites are blocked.** An office network or firewall can block them.
6. **Check your spam folder** for the first email from Job Radar.

When email is working, press **Email results now** on a search to receive every open match straight away. Jobs that were found while email wasn't working are included in the next email that goes out.

## 5. Where jobs come from

| Source | How it's read | Status shown |
|---|---|---|
| Employer job boards on Greenhouse, Lever, Ashby, SmartRecruiters, Workable and Recruitee | The employer's own public job-board API | **Verified active** while the job is in the live feed. It's marked closed when it disappears. |
| Remotive, Remote OK, Jobicy, We Work Remotely | Their public APIs or RSS feeds (used for remote searches) | Appears active, or the result of an application-page check |
| Adzuna (optional, free key from developer.adzuna.com) | An authorised aggregator API that covers Indian job boards | Same as above |
| LinkedIn, Naukri, Indeed, Glassdoor, Foundit, Wellfound, Dice | **Not scraped**, because they don't offer an open API | Every report includes pre-filled search links for these sites, already filtered to the last 24 hours |

`config/companies.json` is a starter list of about 130 employer boards. These are guesses, so every scan checks them, keeps the ones that respond, and sets aside the ones that don't exist (they're checked again every 14 days). To add your own target companies, go to **Settings → Add a company's careers page** and paste a link such as `https://jobs.lever.co/company`. The more target companies you add, the better your coverage.

## 6. Rules the agent follows

- It never invents jobs, posting dates or links. If a source gives no date, the date is shown as *unknown*. The date Job Radar first saw a job is never presented as the posting date.
- A page loading successfully isn't treated as proof that a job is open. Third-party jobs on your shortlist are checked for "no longer accepting" messages, dead links, and redirects to a general page.
- Duplicates are merged across sources, and the employer's own link is preferred. Two different openings with the same title are never merged.
- An unchanged job is never reported twice. A job that changes or is reposted is flagged.
- If some sources fail, the scan continues with the rest, and the failures are listed in the report. A partial scan is never reported as complete.
- It never applies for jobs and never sends your data anywhere except the email address you set.

## 7. How matching works

First, hard filters remove jobs that don't fit: the wrong location, a remote job limited to another country, too much required experience, a seniority level that's too high, a verified salary below your minimum, internships (unless you want one), and anything on your exclude list.

Then each remaining job gets a weighted score out of 100:

`0.30 skills + 0.25 experience + 0.20 responsibilities + 0.10 location + 0.10 preferences + 0.05 compensation`

You can change these weights in `config/settings.json`.

A skill that the job doesn't mention is listed as *not mentioned*. A skill the job asks for that isn't in your search is listed as *not established in your profile*. Neither is treated as a confirmed gap.

Optional: add an Anthropic API key in Settings so Job Radar can understand free-text descriptions better.

## 8. Files

```
Start Job Radar.bat   open the app
Scan Now.bat          run one scan
config/               settings.json (created when you save settings), companies.json
data/                 jobradar.db (all jobs, history, searches), logs
reports/              one HTML report per search per scan
jobradar/             the agent's code
tests/                offline tests: py -m unittest discover tests
```
