# REQ_03_v1.7_mail_configuration

- Received: 2026-10-11T07:02:36.833Z
- Status: Original text of the user's message (verbatim).
- Credentials, if any, are redacted.

---

# Consolidated Requirement: Mail Configuration, Multiple Gmail Accounts, Email Recipients, Templates, and Job Search Email History

Writing

## 1\. Objective

Enhance the Mail Configuration module to support multiple recipient email addresses, multiple Gmail sending accounts, flexible sender selection, reusable email templates, job-search-specific email settings, and comprehensive email execution history.

Users should be able to manage email settings centrally, override configurations for individual job search cards or schedules, choose one or multiple sending Gmail accounts, personalize email content using dynamic placeholders, and track the status of every email operation.

The system must provide secure authentication, reliable delivery processing, clear error handling, and protection against accidental duplicate emails.

## 2\. Mail Configuration Module

Create a centralized **Mail Configuration** section containing the following settings:

- Recipient email addresses: To, CC, and BCC.
- Gmail account management.
- Default sending Gmail account.
- Sender selection and multi-account sending rules.
- Default email template.
- Email subject and content configuration.
- Email notification preferences.
- Fallback policy for unavailable sending accounts.
- Email execution history and delivery tracking.

Users should be able to configure global defaults and override them for individual job search cards or schedules without recreating existing cards.

## 3\. Multiple Recipient Email Addresses

Add recipient management fields to the Mail Configuration module.

### Required functionality

- Support multiple email addresses separated by commas.
- Provide an **Add Email** option to add addresses individually.
- Support separate **To**, **CC**, and **BCC** fields.
- Validate every email address before saving.
- Identify invalid and duplicate addresses.
- Allow users to edit or remove individual addresses.
- Display clear validation messages for invalid entries.
- Preserve recipient settings when editing a job search card or schedule.
- Support global recipient settings and card-specific overrides.
- Validate the final recipient list before sending an email.

Example:

- To: user1@gmail.com, user2@outlook.com
- CC: manager@company.com
- BCC: archive@company.com

All valid recipients should receive the configured email according to the selected recipient fields. Duplicate addresses should be identified and handled according to the application's validation policy.

## 4\. Multiple Sending Gmail Accounts

Add a dedicated **Sending Gmail Accounts** section to manage multiple Gmail accounts.

### Required functionality

- Provide an **Add Gmail Account** option.
- Allow users to connect multiple Gmail accounts.
- Authenticate accounts using Google's supported OAuth 2.0 authentication flow.
- Request only the permissions necessary to send email.
- Display each account's email address and connection status.
- Allow users to set one connected account as the default sender.
- Allow users to change the default account at any time.
- Provide options to reconnect or disconnect an account.
- Display clear errors for disconnected, unauthenticated, expired, or unavailable accounts.
- Prevent unavailable accounts from being used without notifying the user.
- Require confirmation before disconnecting an account assigned to active job search cards or schedules.
- Preserve account assignments when editing existing cards.

Example account management table:

| Gmail Account | Status | Usage |
| --- | --- | --- |
| jobs.account1@gmail.com | Connected | Software Developer searches |
| jobs.account2@gmail.com | Connected | Data Analyst searches |
| jobs.account3@gmail.com | Disconnected | Currently unavailable |

The email addresses above are illustrative examples.

## 5\. Sending Account Selection

Provide a **Sending Account** setting in the global Mail Configuration module and in every job search card or schedule.

Users must be able to select one of the following modes:

### A. Default Gmail Account

Send emails using the globally configured default Gmail account unless a card-specific override is configured.

### B. Specific Gmail Account

Send emails using a particular connected Gmail account selected for the job search card or schedule.

### C. All Selected Gmail Accounts

Allow users to select multiple connected Gmail accounts for email sending.

When this mode is selected, provide two explicit delivery strategies:

**Option 1: Send a Copy from Each Account**

Each selected Gmail account sends a separate copy of the same email to the configured recipients.

The interface must display a confirmation explaining that recipients may receive duplicate messages.

**Option 2: Distribute Emails Across Accounts**

Distribute separate email messages or job-result batches across the selected Gmail accounts. Each message should be assigned to one account according to the configured distribution policy.

The system must explain the distribution method and must not silently duplicate or omit job results.

### Account availability and fallback policy

Allow users to configure what happens when a selected account is unavailable:

- **Stop and notify:** Do not send from another account; notify the user.
- **Use default account:** Retry through the configured default account, subject to duplicate-send protection.
- **Use another selected account:** Use an eligible alternative account according to the configured policy.

The selected policy must be visible to the user. Any fallback must be recorded in the email history, including the originally selected account and the account actually used.

## 6\. Email Template Management

Add a dedicated **Email Templates** section under Mail Configuration.

Users should be able to create and maintain reusable email templates for different job search cards and schedules.

### Template management features

- Create a new email template.
- Enter a template name and description.
- Configure the email subject.
- Design the email body.
- Insert supported dynamic placeholders.
- Preview the generated email with sample job data.
- Save and edit templates.
- Duplicate existing templates.
- Enable or disable templates.
- Delete templates when they are no longer in use, subject to assignment and history-retention rules.
- Set a default email template.
- Assign different templates to individual job search cards or schedules.
- Preserve existing assignments when a template is edited or replaced.

Each template should have a unique identifier and appropriate versioning so that email history can identify the template version used for a particular execution.

### Supported dynamic placeholders

Support the following placeholders:

- `{{job_search_name}}`
- `{{job_title}}`
- `{{company_name}}`
- `{{job_location}}`
- `{{work_mode}}`
- `{{job_url}}`
- `{{job_description}}`
- `{{search_date}}`
- `{{total_jobs_found}}`

For compatibility with existing template examples, the system may also support aliases such as `{{jobsearchname}}` and `{{totaljobsfound}}`.

The template engine must replace placeholders with actual values when generating the email. If a value is unavailable, it must handle the missing field gracefully rather than displaying unresolved placeholders. For repeated job results, job-specific placeholders should be rendered separately for each job.

The system should safely encode dynamic values for the relevant email format and validate URLs before including them in generated HTML emails.

## 7\. Default Email Templates

Provide the following templates as examples that users can customize.

### Template A: Daily Job Search Results

**Template name:** Daily Job Search Results

**Subject:**

`Daily Job Opportunities — {{job_search_name}} — {{search_date}}`

**Email body:**

Hello,

Here are the latest job opportunities identified by your job search configuration.

Job Search: {{job_search_name}}

Search Date: {{search\_date}}

Total Jobs Found: {{total_jobs_found}}

The matching job details are included below.

Please review the opportunities and apply to the positions that match your profile.

Regards,\
Job Search Notification System

### Template B: New Job Opportunities

**Template name:** New Job Opportunities

**Subject:**

`{{total_jobs_found}} New Job Opportunities Found`

**Email body:**

Hello,

Your latest job search has identified new opportunities.

Job Search: {{job_search_name}}

Search Date: {{search\_date}}

New matching opportunities are listed below, including the job title, company, location, work mode, and application link wherever available.

Regards,\
Job Search Notification System

The system should append or render the corresponding job-result details using the configured template format.

## 8\. Email Configuration for Each Job Search Card

Add an **Email Configuration** option to every job search card.

Users should be able to configure:

- Enable or disable email notifications.
- Select an existing email template.
- Preview the selected template.
- Use the default global template or override it.
- Configure card-specific To, CC, and BCC recipients.
- Use global recipients or override them for the card.
- Select the default sending account, a specific account, or multiple selected accounts.
- Choose the multi-account sending strategy when applicable.
- Configure the fallback policy for unavailable accounts.
- Set or edit email schedules.
- Save changes without recreating the job search card.

### Configuration precedence

Use the following precedence rules:

1. An explicit card-specific setting takes precedence over the corresponding global setting.
2. If no card-specific template is selected, use the default global template.
3. If no card-specific recipient list is configured, use the global recipient list.
4. If no card-specific sending account is selected, use the configured default sending account.
5. If email notifications are disabled for a card, do not send its scheduled emails.

An explicitly configured empty recipient list must be distinguishable from an unset recipient list so that users can intentionally suppress email delivery for a particular card.

## 9\. Email Execution Workflow

For each scheduled or manually triggered job search email, the system should:

1. Identify the job search card and its applicable schedule.
2. Resolve the effective recipients, sender selection, template, and fallback policy.
3. Validate recipient addresses and confirm that the selected sending account or accounts are eligible.
4. Retrieve the matching job results.
5. Render the email subject and body using the selected template and dynamic placeholders.
6. Determine the sending accounts and delivery strategy.
7. Create an execution record before attempting to send.
8. Send the email through the selected Gmail account or accounts.
9. Record the result of each account's send attempt.
10. Display the execution outcome in the job search card's email history.

If one account fails while other selected accounts succeed, record each outcome separately and notify the user of partial success.

The system must respect Gmail sending limits, API quotas, authentication restrictions, and provider error responses. Implement appropriate retry handling and backoff for transient errors.

## 10\. Email Execution History and Tracking

Maintain a complete email history for every job search card and schedule.

### Required execution fields

For every email operation, record:

- Unique execution ID.
- Date and time of execution.
- Job search card ID and name.
- Schedule ID, where applicable.
- Email template ID, name, and version.
- Sending account selected by the user.
- Sending Gmail account actually used.
- Recipient count.
- Recipient list, subject to privacy and retention policies.
- Number of jobs included in the email.
- Email subject.
- Email status.
- Error details, if applicable.
- Retry count and retry information.
- Fallback account and reason, if applicable.
- Provider message identifier, when available.

### Email status

Support the following statuses:

- **Pending:** The email is queued for processing.
- **Sending:** The system is attempting to submit the email.
- **Sent:** Gmail has confirmed that the message was accepted for sending.
- **Failed:** The email could not be submitted successfully.

Where supported, maintain delivery information separately from the submission status. For example, delivery, bounce, or other provider-reported events must not be inferred solely from Gmail's confirmation that a message was sent.

### History interface

Display the following information in the job search card's history:

| Field | Description |
| --- | --- |
| Execution time | Date and time of the send attempt |
| Job search | Name of the associated card |
| Template | Template used for the email |
| Sender | Gmail account that sent the message |
| Recipients | Recipient count or permitted recipient details |
| Jobs included | Number of matching jobs in the email |
| Status | Pending, Sending, Sent, or Failed |
| Error details | Failure reason and suggested corrective action |

When multiple accounts are selected, show a separate result for each account or message delivery operation so users can identify successful sends and failed sends individually.

## 11\. Security and Validation Requirements

Implement the following security controls:

- Use Google's supported OAuth 2.0 authentication flow for Gmail account connections.
- Never request or store Gmail passwords in plain text.
- Store refresh tokens and other authentication credentials using secure, access-controlled encryption.
- Request only the Gmail permissions required for the intended sending functionality.
- Protect tokens from exposure in logs, browser responses, error messages, and email history.
- Support token expiration, revocation, account disconnection, and reauthentication.
- Validate email addresses before saving and again before sending.
- Prevent accidental duplicate sends when retries are initiated.
- Use idempotency keys or equivalent execution-level safeguards where appropriate.
- Handle uncertain send outcomes carefully: do not automatically send a second copy when the first attempt may already have been accepted by Gmail.
- Apply rate limiting, backoff, and retry policies that respect Gmail restrictions.
- Record security-relevant actions, including account connections, disconnections, sender changes, and sending configuration changes.
- Require confirmation before disconnecting accounts assigned to active schedules.
- Protect recipient information and apply appropriate data-retention policies.
- Escape dynamic template content and safely handle links in generated emails.

## 12\. Error Handling and User Notifications

Provide clear, actionable error messages for situations such as:

- Invalid or duplicate recipient addresses.
- No recipients configured.
- No connected Gmail account available.
- Gmail authentication expired or revoked.
- Selected sending account disconnected.
- Gmail quota or sending limit exceeded.
- Temporary Gmail API failure.
- Email template missing or disabled.
- Invalid template placeholders.
- Email submission failure.
- Partial success when sending through multiple accounts.
- Uncertain send outcome after a timeout.

Notifications should identify the affected job search card, execution time, sending account, and recommended corrective action where appropriate.

Do not silently switch sending accounts, suppress errors, or report an email as delivered when only submission has been confirmed.

## 13\. Suggested Data Model

The implementation should support the following logical entities, adapted to the application's existing database architecture:

- **Gmail Accounts:** Account ID, authenticated email address, encrypted token references, connection status, default-account flag, and timestamps.
- **Email Recipients:** Recipient ID, email address, recipient type (To, CC, or BCC), scope, and validation status.
- **Email Templates:** Template ID, name, description, subject, body, enabled status, version, and timestamps.
- **Mail Configuration:** Global recipient settings, default sending account, default template, multi-account delivery strategy, and fallback policy.
- **Job Search Email Settings:** Job search card ID, notification status, recipient overrides, sender selection, account assignments, template assignment, and schedule settings.
- **Email Executions:** Execution ID, card ID, schedule ID, resolved configuration, template version, job count, status, timestamps, and error information.
- **Email Send Attempts:** Execution ID, sending account ID, provider message ID, recipient count, attempt status, retry information, and error details.
- **Email Delivery Events:** Provider-reported delivery, bounce, or other supported delivery events.

Use appropriate foreign keys, unique constraints, access controls, and indexes. Store credentials separately from ordinary configuration data.

## 14\. Acceptance Criteria

The implementation will be considered complete when:

1. Users can add, edit, validate, and remove multiple To, CC, and BCC addresses.
2. Users can connect and manage multiple Gmail accounts securely.
3. Users can choose a default sending account and assign different accounts to different job search cards or schedules.
4. Users can send through a single selected account or all selected connected accounts.
5. Users can choose between sending a separate copy from each account and distributing emails across accounts.
6. The interface clearly explains the risk of duplicate emails before enabling copy-from-each-account mode.
7. Unavailable accounts trigger the configured fallback policy and produce a visible execution record.
8. Users can create, preview, edit, duplicate, enable, disable, and manage reusable email templates.
9. Dynamic placeholders are populated correctly, and unavailable values do not appear as unresolved placeholders.
10. Job search cards support card-specific recipients, sending accounts, templates, and notification settings.
11. Global defaults are applied when card-specific overrides are not configured.
12. Every email execution records its status, sending account, template, recipient count, job count, and failure details when applicable.
13. Multi-account sending records success or failure independently for each send attempt.
14. Retry processing prevents accidental duplicate sends and handles uncertain outcomes safely.
15. The system distinguishes Gmail submission confirmation from confirmed delivery.
16. Authentication tokens and recipient information are handled securely.
17. Existing job search cards and schedules continue working with sensible default email settings after the enhancement.
18. The interface provides clear validation messages, account status indicators, execution history, and actionable error notifications.

## 15\. Expected Outcome

The enhanced Mail Configuration module will provide a centralized, secure, and flexible email management system for job search notifications.

Users will be able to manage multiple recipients, connect multiple Gmail sending accounts, select individual or multiple senders, configure reusable email templates, personalize messages with job-specific information, override global settings for individual cards, and track the outcome of every email execution.

The implementation must maintain reliable execution, prevent unintended duplicate messages, respect Gmail sending restrictions, and provide transparent reporting of account selection, sending status, errors, and delivery information where supported.


Adobe according to our flow , this idea. if any thing usefull   take and implement or change it if possibel to or no need
