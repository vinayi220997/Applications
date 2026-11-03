# Research notes (collected from this session's records)

## 1. Gmail sign-in method (decision for v1.7)
- **Question:** Should the app connect Gmail with Google OAuth 2.0, as `REQ_03` asked, or with app passwords?
- **Finding:** A Google OAuth app in "testing" publishing status issues refresh tokens that expire after 7 days. Getting longer-lived tokens means publishing the app and going through Google's verification for the Gmail send scope.
  - This was found with a web search on 2026-10-11. The search results were read; the pages themselves were **not** opened.
  - Sources: https://newscrewdriver.com/2023/02/04/google-oauth-test-tokens-expire-weekly/ and https://www.unipile.com/google-oauth-refresh-token/ (both are secondary sources).
- **Decision:** Keep Gmail app passwords over SMTP, encrypt them with Windows DPAPI, and support several accounts.

## 2. Job sources
- The sources used are public, unauthenticated job APIs. Their endpoints are listed in `SOURCE_REGISTER.csv`, extracted from `sources/ats.py` and `sources/boards.py`.
- LinkedIn, Naukri, Indeed, Glassdoor, Foundit, Wellfound and Dice have no open API, so they are not scraped. The report gives pre-filled search links for them instead.
- Earlier findings, from the session summary:
  - jobicy returned HTTP 400 and We Work Remotely returned HTTP 301. Both were fixed in v1.x.
  - Coverage leans towards US tech companies. Adzuna, which needs a free key, adds Indian boards.

## 3. Text-to-speech for the sample voice note
- The neural voice models on huggingface.co could not be downloaded, because the sandbox proxy blocked them (HTTP 403).
- The sample was made with espeak-ng and the MBROLA us2 voice instead: `jobradar/static/samples/sample-voice.mp3`, 23.8 s long.

## 4. Real data check (2026-10-11)
- I copied the PC's `jobradar.db`, staged at 05:52 UTC.
- I loaded it read-only with v1.6, v1.7 and v1.8 code to make sure the database migrations and card listing work on it. They did: 1 card, "test1", no old-style schedule.
