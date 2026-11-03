Writing

Writing

# Issues Identified and Required Improvements in the Chart Workflow

## 1\. Answer Confirmation Before Moving to the Next Question

- Currently, the chart workflow moves to the next question immediately after an answer is provided.
- It does not ask for confirmation or verify whether the answer is correct.
- **Required improvement:** After each answer, the system should display the entered response and ask the user to confirm it before proceeding to the next question.
- The user should have options to **Confirm, Edit, or Change** the answer.

## 2\. Ability to Edit Previous Answers

- Currently, once an answer is submitted, the user cannot return to the previous question to edit or change the response.
- For example, if the user wants to correct the answer to the first question, the system does not provide an option to do so.
- **Required improvement:** The user should be able to navigate to any previously answered question, edit the response, and confirm the updated answer without restarting the entire workflow.

## 3\. Edit Option on the Final Card

- Currently, the final card provides the following options:
  - Save
  - Save and Scan
  - Start Over
- However, there is no option to edit previously entered information.
- **Required improvement:** Add an **Edit** option to the final card so users can review and modify their answers before saving or proceeding with the scan.

## 4\. Section-Based Editing

When the user selects the **Edit** option, the system should ask:

**"Which section would you like to edit?"**

- Display all available sections.
- Allow the user to select multiple sections for editing.
- After the sections are selected, display the relevant questions from those sections.
- Allow the user to update the answers to the selected questions without affecting other sections.

## 5\. Update Existing Information or Add New Information

When the user updates an answer, the system should ask how the updated information should be handled.

**Prompt:** "How would you like to update this information?"

Provide the following options:

1. **Overwrite Existing Information:** Replace the previously saved answer with the updated answer.
2. **Add to Existing Information:** Retain the existing answer and append the new information.
3. **Edit Existing Information:** Modify the existing answer while retaining the relevant information the user wants to keep.

The system should apply the selected action only after the user confirms the update.

## 6\. Expected Workflow

1. Display the question.
2. Capture the user's answer.
3. Show the entered answer for confirmation.
4. Provide **Confirm, Edit, or Change** options.
5. Move to the next question only after confirmation.
6. Allow users to revisit and edit any previously answered question.
7. On the final card, provide **Save, Save and Scan, Start Over, and Edit** options.
8. When editing, allow users to select one or multiple sections.
9. Display the questions associated with the selected sections.
10. Ask whether to overwrite, add to, or edit the existing information.
11. Apply the changes and show the updated answers for confirmation.
12. Allow the user to save the final, confirmed information.

## Expected Outcome

The chart workflow should provide users with complete control over their answers. Users must be able to review, confirm, correct, and update information at any stage without losing previously entered data or restarting the entire process. All changes should be applied according to the user's explicit selection and confirmation.

# Additional Requirements: Chart Workflow, User Experience, Attachments, Voice, Screenshot OCR, and AI Configuration

## 7\. Progress Status Bar and Question Counter

To improve the user experience, the chart workflow should display a progress status bar and question counter throughout the process.

**Required improvements:**

- Display the current question number and total number of questions, such as **Question 3 of 10**.
- Show a visual progress bar indicating the percentage of completion.
- Update the progress bar and question counter dynamically as the user moves through the questions.
- If the user goes back to edit a previous answer, update the status appropriately without losing completed answers.
- Clearly distinguish between completed, pending, and currently active questions.

**Expected outcome:** Users should always know their current position, how much of the workflow is complete, and how many questions remain.

## 8\. Success Messages and Animations

Provide clear visual feedback whenever an important action is completed successfully.

**Required improvements:**

- Display a success message after an answer is confirmed or updated.
- Show a success animation when the chart is saved successfully.
- Display an appropriate success message after a successful scan.
- Confirm when an attachment, voice recording, or screenshot has been uploaded and processed successfully.
- Display clear error messages if an action fails, along with an option to retry.

**Example success messages:**

- "Answer confirmed successfully!"
- "Your changes have been saved successfully!"
- "Chart saved successfully!"
- "Screenshot processed successfully!"
- "Voice recording uploaded successfully!"

Use lightweight animations, such as a checkmark animation or a success indicator, without unnecessarily delaying the workflow.

## 9\. Attachment Upload with Sample File Download

The attachment feature should help users understand which file types and information they need to provide.

**Required improvements:**

- Provide an option to upload an attachment.
- Display the supported file formats and size limits.
- Include a **Download Sample File** option near the attachment upload field.
- The sample file should demonstrate the required structure, format, and type of information expected.
- The sample file must contain realistic example data relevant to the chart workflow.
- Allow users to download the sample, fill it in, and upload the completed file.
- Validate the uploaded file and display clear messages for unsupported formats, missing information, or invalid data.

**Expected outcome:** Users should understand what information to include in the attachment before uploading it.

## 10\. Voice Recording with Sample Audio

The voice input feature should provide guidance on what users need to say in their recordings.

**Required improvements:**

- Provide a **Play Sample Voice** option so users can listen to an example recording.
- Provide a **Download Sample Audio** option so users can listen to the sample offline.
- The sample recording should demonstrate the type of information, level of detail, and speaking format expected by the system.
- Provide a clear **Start Recording**, **Stop Recording**, **Play Recording**, and **Re-record** option.
- Allow users to review their recording before submitting it.
- Where AI or speech-to-text services are configured, convert the recording into text and display the transcription for confirmation before using it in the chart.
- If voice processing is unavailable, clearly indicate that the feature is disabled and explain why.

**Example guidance:** "Please describe the relevant information clearly, including the details requested in the current chart section."

## 11\. Screenshot Upload and OCR Support

Currently, the screenshot feature does not appear to provide OCR (Optical Character Recognition) functionality to extract text from uploaded images.

**Required improvements:**

- Allow users to upload screenshots or image files.
- Integrate an OCR service to extract readable text from the uploaded screenshot.
- Where appropriate, use a configured AI service to interpret the extracted text and identify information relevant to the chart.
- Display the extracted text and proposed chart information for user review.
- Allow users to edit, correct, or remove extracted information before adding it to the chart.
- Ask the relevant chart questions when required information is missing or unclear.
- Show processing, success, and error statuses during screenshot processing.

**Expected outcome:** Users should be able to upload a screenshot and extract relevant information without manually typing all the content.

**Important:** OCR extracts text from images, while AI interprets and structures the extracted information. These are separate capabilities and should have separate configuration and status indicators.

## 12\. AI and OCR Configuration in Settings

Add an **AI Configuration** section under Settings to manage the external services required for AI processing, OCR, and related chart features.

### 12.1 Configuration Options

The settings page should provide the following:

- AI provider or service configuration.
- Required API credentials or connection settings, where applicable.
- OCR provider or service configuration.
- Connection status and configuration validation.
- Test connection option.
- Enable or disable AI functionality.
- Enable or disable OCR functionality.
- Clear error messages when configuration is missing, invalid, or unavailable.

Credentials must be stored securely and should never be displayed in full after they have been saved.

### 12.2 Chart Status in Offline Mode

When no AI or OCR service is configured, the chart should continue to operate in offline mode wherever possible.

The **Chart Status** section should clearly display the availability of these services.

Example status display:

| Feature | Status |
| --- | --- |
| Chart Workflow | Available — Offline Mode |
| AI Processing | Disabled — Not Configured |
| OCR Processing | Disabled — Not Configured |
| Manual Data Entry | Available |
| Answer Editing | Available |
| Save Chart | Available, subject to local storage support |

### 12.3 Behavior When AI or OCR Is Not Configured

- The chart should continue to support manual question-and-answer entry.
- Users should be able to review, confirm, edit, and save their answers.
- AI-dependent features should be disabled or clearly marked as unavailable.
- Screenshot text extraction should display an appropriate message if OCR is unavailable.
- Voice transcription should be marked unavailable if it requires an unconfigured speech-to-text service.
- The system should not show a successful AI or OCR processing message when processing has not occurred.
- Provide a link or action to open Settings and configure the required service.

**Example message:**

"AI and OCR services are not configured. The chart is currently running in offline mode. You can continue entering and editing information manually. Configure the required services in Settings to enable AI and OCR features."

## 13\. Chart Status Indicators

Introduce a consistent status indicator on the chart screen so users can quickly understand which features are available.

Recommended statuses:

- **Online:** Required services are connected and available.
- **Offline Mode:** The chart can operate without the external services.
- **AI Disabled:** AI processing is unavailable or not configured.
- **OCR Disabled:** Screenshot text extraction is unavailable or not configured.
- **Processing:** An upload, recording, or extraction is being processed.
- **Success:** The requested operation has completed successfully.
- **Error:** The operation failed and may require a retry or configuration change.

The status should update automatically when the configuration or connection state changes.

## 14\. Consolidated Expected Workflow

1. Start the chart and display the progress bar and question counter.
2. Ask a question and capture the user's response.
3. Show the answer for confirmation before proceeding.
4. Allow the user to confirm, change, or edit any previous answer.
5. Support manual entry, attachments, voice recordings, and screenshots.
6. Provide sample downloads for attachments and voice recordings.
7. Process screenshots through OCR when configured.
8. Use AI to interpret and structure information only when the required service is available.
9. Display clear status indicators for online, offline, AI, OCR, and processing states.
10. Allow users to select one or multiple sections for editing.
11. Ask whether to overwrite, add to, or edit existing information.
12. Display the final chart for review.
13. Provide Save, Save and Scan, Start Over, and Edit options.
14. Display a success message and animation after successful completion.
15. Preserve existing data during editing and prevent accidental loss of confirmed answers.

## Final Expected Outcome

The chart application should provide a reliable, transparent, and user-friendly experience, with clear progress tracking, answer confirmation, flexible editing, sample files and recordings, screenshot OCR, configurable AI integration, and appropriate success and error feedback.

The chart must remain usable for manual data entry and editing when AI or OCR is not configured. All unavailable capabilities should be clearly identified in the Chart Status section, and users should be guided to Settings when configuration is required.