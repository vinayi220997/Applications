# REQ_02_v1.6_cards_modes_schedules

- Received: 2026-10-11T05:29:51.499Z
- Status: Original text of the user's message (verbatim).
- Credentials, if any, are redacted.

---

Additional Requirements: Job Search, Job Description Modes, Job Cards, Export/Import, and Activity History
1. Job Location and Work Mode Selection
1.1 Multiple City Selection
The job search form should allow users to select multiple cities instead of restricting them to a single city.
Required improvements:

* Allow users to select multiple cities for a single job search.
* Display the selected cities as removable tags or chips.
* Allow users to add or remove cities at any time.
* Support searching across all selected cities in a single search.
* Preserve the selected cities when editing or rerunning a saved job search.

1.2 Multiple Work Mode Selection
Allow users to select one or more work modes.
Available options:

* Hybrid
* Remote
* On-site

Required improvements:

* Support multiple selections, such as Hybrid + Remote or Remote + On-site.
* Allow users to remove an individual work mode without clearing the other selections.
* Display the selected work modes clearly.
* Do not force users to choose only one work mode.
* Save the selected work modes with the job search card.

Example: A user should be able to select Bengaluru, Hyderabad, and Pune, with Hybrid and Remote work modes enabled for the same search.
2. Job Description Input Modes
When entering or configuring a job description, provide two modes for defining the information and questions.
Mode 1: Chart Mode
Chart Mode uses the existing interactive question-and-answer workflow.
Required functionality:

* Display questions one at a time.
* Capture and confirm each answer before moving to the next question.
* Display a progress bar and question counter.
* Allow users to go back and edit previous answers.
* Support manual entry, file attachments, voice input, and screenshots where configured.
* Allow users to review, edit, and confirm the completed chart.
* Save the completed chart with the associated job search configuration.

Mode 2: Questionnaire Mode
Questionnaire Mode uses a predefined form containing all relevant questions.
Required functionality:

* Display predefined questions in a structured form.
* Allow users to answer multiple questions on one screen.
* Support text fields, dropdowns, checkboxes, multiple selections, and other suitable input types.
* Allow users to upload a file containing relevant information.
* Extract answers from the uploaded file where supported.
* Show the extracted answers in the corresponding form fields for review and correction.
* Provide a sample file download that demonstrates the expected file structure and content.
* Allow users to save, edit, and reuse the completed questionnaire.

2.1 Switching Between Modes

* Clearly display the selected mode: Chart Mode or Questionnaire Mode.
* Allow users to choose the appropriate mode when configuring a job description.
* Preserve previously entered information when switching modes wherever the data structure permits.
* If a direct conversion is not supported, explain the limitation and offer the available editing option.

3. Job Search Cards
Each configured job search should be displayed as a separate card on the Job Search page.
Every card should show the key information needed to understand, control, and track that search.
3.1 Information Displayed on Each Card

* Job search name or job title.
* Selected cities.
* Selected work modes.
* Job description input mode: Chart Mode or Questionnaire Mode.
* Method used to obtain answers, such as manual entry, uploaded file, or configured AI-assisted extraction.
* Current search status.
* Card activation toggle.
* Last search date and time.
* Last email execution date and time.
* Number of jobs found in the most recent search.
* Total jobs found, if tracked.
* Last execution result or error message, where applicable.

3.2 Enable and Disable Individual Cards
Add an On/Off toggle to each job search card.
When enabled:

* The card is active and eligible to run according to its configured schedule or execution rules.
* The system can perform the associated search when the required conditions are met.

When disabled:

* The card should not initiate new automated searches or email actions.
* The existing configuration, search history, and saved results should remain available.
* The user should be able to re-enable the card without recreating the search.

The toggle should control each card independently so users can enable only the job searches they want to run.
4. Edit Job Search Cards
Provide an Edit Card option on every job search card.
When selected, the system should reopen the configuration using the mode originally used to create the card.
4.1 Editing a Chart Mode Card

* Reopen the chart workflow.
* Load all previously saved answers.
* Allow users to navigate to specific sections and questions.
* Allow users to update existing answers without restarting the entire workflow.
* Save the changes back to the same job search card.

4.2 Editing a Questionnaire Mode Card

* Reopen the predefined questionnaire form.
* Populate the form with the previously saved answers.
* Allow users to update individual fields or upload a replacement file.
* Save the changes back to the same card.

4.3 Editing Across Modes
If a user wants to edit a Chart Mode card using Questionnaire Mode, or vice versa:

* Provide a Change Input Mode option when conversion is supported.
* Convert the existing answers into the new mode wherever possible.
* Preserve the original data until the user confirms the conversion.
* If conversion is not supported, retain the original mode and explain the limitation.

Important: Editing a card should update the existing card rather than create a duplicate card, unless the user explicitly chooses to duplicate it.
5. Export and Import Job Search Cards
Allow users to export a configured job search card to a portable file that can be shared and imported later.
5.1 Export Job Search Card
Provide an Export Card option.
The exported file should include, where applicable:

* Job search name and configuration.
* Selected cities.
* Selected work modes.
* Job description input mode.
* Saved questions and answers.
* Relevant search filters and preferences.
* Card settings that can safely be transferred.
* A version identifier for compatibility checks.

Use a structured, documented format such as JSON for configuration data. If users need a more human-readable version, optionally provide a PDF or spreadsheet export.
Sensitive credentials, API keys, passwords, and private connection tokens must never be included in the exported file.
5.2 Import an Exported Card
Provide an Import Card option on the Job Search page.
The user should be able to upload a previously exported card file and restore the saved configuration.
Required workflow:

1. Select Import Card.
2. Upload the exported file.
3. Validate the file format and version.
4. Read the saved configuration and answers.
5. Show a preview of the imported card.
6. Ask whether to create a new card or update an existing card.
7. Confirm the import.
8. Create or update the card and display a success message.

5.3 Import Behavior by Input Mode

* Questionnaire Mode: Restore the predefined questions, saved answers, and supported configuration fields into the questionnaire form. Allow the user to review and edit them before saving.
* Chart Mode: Restore the chart configuration and answers. If the application supports editing those answers through the chart interface, open the chart for editing. Otherwise, keep the card in its original mode and clearly indicate that direct form editing is unavailable.

The import process should preserve existing data unless the user explicitly confirms an overwrite or update.
6. Search Execution Date, Time, and Status
Every job search card should maintain a history of when searches were executed.
6.1 Search Status
Display clear status labels, such as:

* Not Started
* Ready
* Running
* Completed
* Failed
* Paused
* Disabled

Update the status as the search progresses.
6.2 Search Execution Details
For each search execution, record:

* Search start date and time.
* Search completion date and time.
* Current status.
* Number of jobs found.
* Number of new jobs found, where deduplication is supported.
* Number of jobs successfully processed or saved, where applicable.
* Error details if the search fails.

Display the most recent execution details directly on the card.
Example:

* Last Search: 11 Oct 2026, 10:30 AM
* Status: Completed
* Jobs Found: 24
* New Jobs: 8
* Duration: 2 minutes

These values are illustrative examples; the application must display actual execution data.
7. Email Execution Status and History
Track email activity separately from job search activity.
7.1 Email Status on the Card
Display:

* Last email execution date and time.
* Email status.
* Number of jobs included in the email.
* Number of emails sent, where applicable.
* Error or failure details, if any.

7.2 Email Status Labels
Use clear labels such as:

* Not Scheduled
* Scheduled
* Sending
* Sent
* Failed
* Skipped

Distinguish between a search that completed successfully and an email that was actually sent successfully.
7.3 Email History
Maintain a history of email executions for each card, including:

* Date and time.
* Related search execution.
* Number of jobs included.
* Delivery or sending status, according to the email provider's available information.
* Error details, if applicable.

Do not mark an email as sent merely because the search completed. Update the email status only after the email operation reports the corresponding result.
8. Card Activity History
Add a View History option to every job search card.
The history should show a chronological record of important events, including:

* Card created.
* Configuration updated.
* Card enabled or disabled.
* Search started.
* Search completed or failed.
* Number of jobs found in each execution.
* Email scheduled, sent, skipped, or failed.
* Card imported or exported.
* Date and time of each event.

Allow users to review previous executions and identify when a search ran, how many jobs it found, and whether the associated email operation succeeded.
Keep the activity history associated with the card even when its configuration is edited or the card is temporarily disabled.
9. Recommended Job Search Card Layout
Each card should provide a concise overview, with detailed information available through expandable sections.
Card header

* Job search name
* Current status
* On/Off toggle

Configuration summary

* Cities
* Work modes
* Input mode
* Answer source

Latest search

* Last run date and time
* Jobs found
* New jobs found
* Search status

Latest email

* Last email date and time
* Email status
* Number of jobs included

Actions

* Edit Card
* Run Search
* View Results
* View History
* Export Card
* Duplicate Card
* Delete Card

Use confirmation dialogs for destructive actions, such as deleting a card.
10. Expected End-to-End Workflow

1. Create a job search configuration.
2. Select multiple cities and one or more work modes.
3. Choose Chart Mode or Questionnaire Mode.
4. Enter the required information or upload a supported file.
5. Review, edit, and save the configuration.
6. Create the job search card.
7. Enable or disable the card independently.
8. Run the search manually or according to the configured schedule.
9. Display the execution status, date, time, and job counts.
10. Execute the configured email action and record its status separately.
11. Review the complete search and email history.
12. Edit the card at any time without losing existing answers or history.
13. Export the card for backup or sharing.
14. Import the exported card later and restore its supported configuration and answers.

Final Expected Outcome
The Job Search module should support multiple locations and work modes, two flexible job-description input methods, independently controlled job search cards, editable configurations, portable export/import, and complete execution history.
Users should be able to manage multiple job searches efficiently, choose which cards are active, edit previously saved information, share configurations with other users, and clearly understand when each search ran, how many jobs it returned, and whether the corresponding email operation succeeded.


Additional Requirement: Flexible Scheduling for Job Search Cards
1. Objective

Currently, the Schedule setting applies to all job search cards. This limits the user's ability to run different job searches at different times.

Enhance the scheduling functionality to support individual card schedules and multiple schedules linked to selected cards.

The system should provide two scheduling approaches so users can choose the one that best suits their requirements.

2. Option 1: Individual Schedule for Each Card

Each job search card should have its own scheduling configuration.

Required functionality
Add a Schedule option to each job search card.
Allow users to configure the schedule independently for each card.
Support daily, weekly, and custom scheduling intervals, where applicable.
Allow users to select the execution time, time zone, and active days.
Allow users to enable, disable, edit, or delete a card's schedule.
Display the next scheduled execution date and time on the card.
Maintain a history of scheduled executions.

Example:

Job Search Card	Schedule
Software Developer	Daily at 9:00 AM
Data Analyst	Daily at 1:00 PM
Product Manager	Monday, Wednesday, and Friday at 6:00 PM

Each card should execute according to its own schedule without affecting the other cards.

3. Option 2: Multiple Schedules in the Schedule Section

Retain the existing central Schedule section, but enhance it to support creating multiple schedules and linking each schedule to one or more job search cards.

Required functionality
Allow users to create multiple named schedules.
Allow users to select one or multiple job search cards for each schedule.
Configure the execution frequency, days, time, and time zone for each schedule.
Allow users to edit, enable, disable, or delete individual schedules.
Display the cards linked to each schedule.
Allow users to add or remove cards from an existing schedule.
Display the next execution date and time for each schedule.
Maintain execution history for each schedule and its associated cards.

Example:

Schedule Name	Linked Job Cards	Frequency
Morning Search	Software Developer, Data Analyst	Daily at 9:00 AM
Evening Search	Product Manager, Business Analyst	Daily at 6:00 PM
Weekend Search	Remote Jobs, Senior Developer	Saturday and Sunday at 10:00 AM

A single schedule can trigger multiple linked cards. Each card's search results and email status must still be tracked separately.

4. Recommended Approach: Support Both Options

Implement both scheduling methods to provide maximum flexibility.

Individual card scheduling

Best for users who want to configure a unique schedule for each job search.

Centralized multi-card scheduling

Best for users who want to group several job search cards under one schedule.

The Schedule section should provide a clear overview of all schedules, regardless of where they were created.

5. Scheduling Rules and Conflict Handling
A disabled card must not run automatically, even if it is linked to an active schedule.
A disabled schedule must not trigger any linked cards.
If a card is linked to multiple active schedules, warn the user about potential duplicate executions.
Allow users to confirm whether duplicate executions are intentional.
Prevent overlapping executions of the same card unless explicitly supported.
If an execution fails, record the failure and provide an appropriate retry option.
Use the configured time zone consistently for scheduling and execution history.
Do not silently delete schedules or card configurations when a card is edited or disabled.
6. Job Card Display

Each job search card should show:

Card status: Enabled or Disabled.
Schedule status: Scheduled, Paused, or Not Scheduled.
Schedule name or names.
Next scheduled execution.
Last execution date and time.
Last execution result.
Number of jobs found in the latest execution.
Latest email execution status.

Provide a Manage Schedule action on each card to view or modify its linked schedules.

7. Central Schedule Dashboard

The Schedule section should display all configured schedules in one place.

For each schedule, show:

Schedule name.
Linked job search cards.
Frequency and execution time.
Next scheduled run.
Last execution status.
Enable/disable toggle.
Edit and delete actions.

Include a Create Schedule option that allows users to configure a schedule and select multiple job cards to link to it.

8. Expected Outcome

Users should be able to schedule job searches independently or group multiple cards under shared schedules. The system must maintain clear execution status, prevent unintended duplicate runs, and provide complete visibility [REDACTED-CREDENTIAL] is scheduled to run.

The existing global Schedule setting should be retained only if it is useful as a default schedule for new cards. It should not unexpectedly override explicitly configured card-level or multi-card schedules.
