# REQ_05_archive_and_handover_instruction

- Received: 2026-10-11T09:13:43.584Z
- Status: Original text of the user's message (verbatim).
- Credentials, if any, are redacted.

---

MASTER INSTRUCTION FOR CLAUDE
Complete Project Collection, Organization, Archiving, and Account Handover
1. Your Mission
Act as my Project Archivist, Documentation Manager, Version Controller, and Handover Specialist.
Your task is to collect, inspect, organize, document, and package every available file associated with my existing project.
I want one complete, well-structured project folder containing all available:

* Project files and source files
* Documents, reports, drafts, and final deliverables
* Every available version and revision
* Research, references, notes, and source links
* Diagrams, flowcharts, architecture designs, and visual assets
* Images, datasets, templates, and other resources
* Code, scripts, configuration files, and supporting materials
* Generated outputs, exports, and presentations
* Existing ZIP files and other archives
* Project history, decisions, requirements, and change logs
* Checklists, instructions, and continuation documentation
* Everything else relevant to the project that can be recovered

The final result must be organized, traceable, downloadable, and ready to transfer to another Claude or ChatGPT account.
Do not merely describe what should be done. Inspect the available files, perform the work using your available tools, create the required documents, and package the actual files whenever your environment permits.
Do not claim that a file was collected, created, inspected, or verified unless that action was actually completed.
2. Inspect All Available Project Sources
First, inspect all project materials you can actually access, including:

1. Files uploaded in the current conversation.
2. Files and attachments available through the current project workspace.
3. Documents, source files, and outputs available in the working environment.
4. Existing ZIP files and previously exported project archives.
5. Available project instructions, conversation context, research notes, and documented decisions.
6. Any connected storage locations that you are authorized to access.
7. Relevant previous project conversations or artifacts, but only when they are actually accessible.

Do not assume you can access every previous conversation, another account, my computer's Downloads folder, or external storage.
If something is inaccessible, document that limitation and explain what I need to upload or export.
Do not stop after inspecting only one file if additional project materials are available.
3. Create the Master Folder
Create the following folder structure. Adapt individual subfolders if necessary, but preserve the numbered organization and the overall purpose of each folder.
PROJECTMASTERARCHIVE/
00STARTHERE/ README.md PROJECTOVERVIEW.md PROJECTSTATUS.md MASTERFILEINDEX.csv ARCHIVE_MANIFEST.txt
01PROJECTBRIEF/ OriginalRequirements/ Scopeand_Objectives/ Specifications/ Decisions/
02VERSIONSANDHISTORY/ OriginalVersions/ WorkingVersions/ ReviewedVersions/ FinalVersions/ VERSIONHISTORY.md CHANGELOG.md VERSION_COMPARISON.md
03DOCUMENTS/ OriginalDocuments/ Drafts/ Reports/ Proposals/ Presentations/ Final_Documents/
04RESEARCHANDREFERENCES/ ResearchNotes/ ReferenceDocuments/ SourcePapers/ WebReferences/ Evidence/ SOURCEREGISTER.csv
05DIAGRAMSANDDESIGN/ Architecture/ Flowcharts/ UMLandDataModels/ Wireframes/ VisualDesigns/ EditableDiagrams/ Diagram_Exports/
06RESOURCESANDASSETS/ Images/ Icons/ Templates/ Datasets/ Media/ SupportingResources/ LicensesandAttribution/
07SOURCEFILES/ SourceCode/ Scripts/ Configuration/ Schemas/ Dependencies/ TechnicalDocumentation/
08OUTPUTSANDDELIVERABLES/ GeneratedOutputs/ Reports/ Exports/ Presentations/ Approved_Deliverables/
09ZIPANDPACKAGES/ OriginalArchives/ ExistingPackages/ ReleasePackages/ Package_Notes/
10TESTSANDVALIDATION/ TestResults/ QualityChecks/ ValidationReports/ Screenshots/ Known_Issues/
11HANDOVERTONEWACCOUNT/ HANDOVERGUIDE.md CONTINUEPROJECTPROMPT.md PROJECTCONTEXT.md NEXTSTEPS.md OPENISSUES.md TRANSFER_CHECKLIST.md
12BACKUPANDRECOVERY/ OriginalFileCopies/ RecoveredFiles/ DuplicateReview/ RecoveryNotes/ MISSING_FILES.md
99ARCHIVEOLD/ SupersededDrafts/ DeprecatedMaterials/ Historical_Artifacts/
Only create folders and files that are appropriate for the project. If a category has no available materials, retain the folder if useful and document its status. Never create fake project artifacts merely to fill the structure.
4. Preserve Every Available Version
Version preservation is mandatory.

* Preserve original files without modifying their contents.
* Collect all available versions, including early drafts and intermediate revisions.
* Preserve original filenames and timestamps where possible.
* Record each file's original location.
* Never silently replace an earlier version with a newer version.
* Identify the latest version using evidence, not filename assumptions alone.
* Distinguish working drafts, reviewed versions, approved deliverables, and deprecated versions.
* If two files conflict, preserve both and document the conflict.
* Do not label a document FINAL unless its approval status is established.
* Do not reconstruct missing historical versions and present them as originals.

If a version comparison is possible, record what changed, what was added or removed, and which version should be treated as authoritative for each purpose.
5. Create a Master File Index
Create `MASTER_FILE_INDEX.csv` with these columns:
FileID, FileName, FileExtension, Category, Version, CreatedDate, ModifiedDate, Status, OriginalLocation, ArchivePath, Source, FileSize, Checksum, Verified, Notes
Requirements:

* Give every collected file a unique identifier.
* Include all file types, including images, diagrams, datasets, archives, code, and hidden project support files where accessible.
* Record the exact destination path inside the master folder.
* Record the original path or source when known.
* Use `Unknown` or `Not available` when information cannot be established.
* Mark files as verified only after checking them.
* Identify duplicate files without automatically deleting them.
* Clearly distinguish actual files from missing-file placeholders.

Also create `MISSING_FILES.md`, documenting expected files that could not be found, files referenced but not supplied, and items requiring my input.
6. Organize Research and Resources
For all available research:

* Preserve the original research documents and notes.
* Collect source URLs and citations when available.
* Record titles, authors, publication dates, access dates, and relevant notes when known.
* Distinguish primary sources from secondary sources where possible.
* Preserve research findings and their supporting evidence.
* Record broken links and inaccessible references.
* Do not invent citations or claim to have reviewed sources you could not access.

For diagrams and design assets:

* Preserve editable source files when available.
* Preserve exported images and PDFs.
* Record the diagram's purpose and related project component.
* Link each diagram to its relevant document or version when possible.

For source code and technical files:

* Preserve source files, configuration, dependency manifests, and documentation.
* Do not include passwords, API keys, access tokens, or unnecessary private credentials in the transfer package.
* Do not bundle large generated caches or reproducible build artifacts unless they are necessary for project continuity.
* Document any omitted items.

7. Create the Required Documentation
Create or update the following documents based on the actual materials available.
README.md
Explain the project folder structure, where to begin, how files are organized, and which documents are the most important.
PROJECT_OVERVIEW.md
Summarize the project's purpose, goals, scope, main components, and intended outcomes.
PROJECT_STATUS.md
Record what has been completed, what is currently in progress, what remains unfinished, and what is blocked.
VERSION_HISTORY.md
List available versions, their dates, key changes, status, and relationships.
CHANGELOG.md
Record meaningful changes made during the archive preparation and any subsequent project updates.
VERSION_COMPARISON.md
Compare important versions where sufficient evidence exists.
SOURCE_REGISTER.csv
Record available research sources, URLs, citation details, relevance, and verification status.
MISSING_FILES.md
List missing files, inaccessible locations, unresolved version conflicts, and required recovery actions.
HANDOVER_GUIDE.md
Explain how another AI assistant or human collaborator can understand and continue the project.
PROJECT_CONTEXT.md
Provide a concise but sufficiently detailed summary of the established project context, requirements, decisions, constraints, current status, and relevant file locations.
NEXT_STEPS.md
List the remaining tasks in priority order, including dependencies, blockers, and expected outputs.
CONTINUEPROJECTPROMPT.md
Write a ready-to-copy instruction that I can give to Claude or ChatGPT in another account.
TRANSFER_CHECKLIST.md
Provide a checklist for verifying the archive, transferring it, and resuming work.
Do not fabricate unknown project information. Clearly mark information that requires confirmation.
8. Create the Continuation Prompt
The continuation prompt must instruct the next AI assistant to:

1. Read the README and project context first.
2. Inspect the master file index and available documents.
3. Identify the authoritative version of each major deliverable.
4. Review the requirements, decisions, research, and change history.
5. Summarize the current project status.
6. Identify missing files and unresolved issues.
7. Ask for clarification only when a necessary detail cannot be resolved from the available evidence.
8. Propose the next logical task before making major changes.
9. Preserve existing files and create new versions when appropriate.
10. Update the file index, change log, and status records after modifications.
11. Never assume that files mentioned in the documentation are actually present.
12. Never claim that inaccessible files or previous conversations have been reviewed.

The goal is seamless project continuation, not starting the project from scratch.
9. Build the Downloadable ZIP Archive
After organizing the available files, create a ZIP archive named:
`PROJECT_MASTER_ARCHIVE_YYYY-MM-DD.zip`
Use the actual packaging date.
The ZIP should contain the complete `PROJECT_MASTER_ARCHIVE/` directory, including all collected files and handover documentation.
If file-generation and archive tools are available, use them to create the real archive. Do not simply print a suggested ZIP filename.
Before declaring success:

* Verify that the ZIP file exists.
* Verify that it can be opened.
* Test the archive for corruption when supported.
* Check that the folder structure is present.
* Compare the archive contents against the master file index.
* Confirm that all expected collected files are included.
* Record any excluded files and the reason for exclusion.
* Generate checksums when supported.
* Save the archive manifest.
* Provide the actual downloadable file or attachment if the environment supports it.

If the archive is too large, create numbered split packages or separate logical ZIP files. Include a manifest explaining how the packages fit together.
Retain all original ZIP files separately within the master archive. Do not replace original archives with the new consolidated ZIP.
10. Final Quality Assurance
Perform a final review covering:

* Completeness of the file inventory
* Folder organization
* Preservation of all accessible versions
* Research and reference documentation
* Presence of diagrams and resources
* Consistency of filenames and paths
* Missing and inaccessible files
* ZIP integrity
* Handover instructions
* Sensitive information and credential handling
* Backup and recovery readiness

Do not claim absolute completeness if some project sources or historical conversations were inaccessible.
Distinguish clearly between:

* Collected and verified
* Collected but not fully verified
* Referenced but missing
* Inaccessible
* Not applicable

11. Final Report to Me
When the work is complete, give me a concise but detailed completion report containing:

1. The actual master folder created.
2. The actual ZIP archive and download link, if successfully created.
3. The total number of files collected.
4. The number of documents, source files, diagrams, research items, resources, versions, and archives.
5. The number of files verified.
6. Any missing or inaccessible materials.
7. Any excluded files and the reasons.
8. The location of the continuation prompt.
9. The location of the handover checklist.
10. Any remaining actions I must complete manually.

Use real counts from the file inventory. Do not invent counts.
If you cannot create a file or ZIP in the current environment, explain the exact limitation and complete every other useful step possible.
12. Execution Order
Follow this order:
PHASE 1 — Inspect available sources.
PHASE 2 — Inventory and preserve originals.
PHASE 3 — Organize files into the master structure.
PHASE 4 — Identify versions, duplicates, conflicts, and missing materials.
PHASE 5 — Create the master index and documentation.
PHASE 6 — Prepare the continuation prompt and handover checklist.
PHASE 7 — Build the consolidated ZIP archive.
PHASE 8 — Verify the archive and compare it against the inventory.
PHASE 9 — Deliver the archive and completion report.
Start with Phase 1. Do not stop after producing a plan. Execute the work using the tools and files you can actually access, and report any genuine blockers that require my assistance.
FINAL SUCCESS CRITERION: I must have a well-organized, verifiable project archive and enough documented context to transfer the work to another Claude or ChatGPT account and continue without unnecessarily repeating completed work.
