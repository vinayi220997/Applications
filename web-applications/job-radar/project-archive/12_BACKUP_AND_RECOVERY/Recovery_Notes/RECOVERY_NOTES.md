# Recovery notes

- **PC data snapshot** (`../Recovered_Files/pc_data_snapshot_2026-10-11/`):
  - `jobradar.db` was copied from the PC with the remote-devices bridge on 2026-10-11 at 05:52 UTC. `jobradar.log` was copied on 2026-10-10.
  - To restore it, close Job Radar and copy `jobradar.db` into `C:\Users\Admin\AppData\Local\Programs\JobRadar\data\`. Newer versions upgrade the database automatically when they start.
  - It contains personal data: email addresses and job matches.
- **Settings and secrets are NOT backed up here.** If the PC is lost, re-enter the Gmail app passwords in the Mail tab and the API keys in Settings.
- **Rebuilding from source:**
  - Run `makensis installer/jobradar.nsi` in the source folder to get the installer.
  - Or run directly with `python -m jobradar ui`.
