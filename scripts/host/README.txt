DAAF - Data Analyst Augmentation Framework
===========================================

This folder contains DAAF's host-side tools.

START HERE:

    macOS / Linux:   bash daaf.sh
    Windows:         .\daaf.ps1

Run either of the following commands in your terminal when this folder
is open. That opens the DAAF Control Panel - a menu with everything: starting
Claude Code, notebooks, VS Code, session logs, backups, updates, and
rebuilds. It is the only command you need to remember. Run it and
use the Help option to learn more about what each command does.

The other scripts in this folder are helpers that the Control Panel
calls for you. Each one also works standalone if you prefer, e.g.:

    bash backup_daaf.sh        make a backup      (macOS / Linux)
    .\backup_daaf.ps1          make a backup      (Windows)
    bash update_daaf.sh        update DAAF        (macOS / Linux)
    .\update_daaf.ps1          update DAAF        (Windows)

NOTES:

- environment_settings.txt is where your data source API keys go
  (copy environment_settings_example.txt to get started).
- Folders ending in _daaf_backup are your backups. Safe to move or
  delete; the Control Panel can restore from them if they're in the
  same folder as the script itself.
- If the updater says it updated itself, run it once more to finish
  syncing the tools in this folder.
- You should not need to edit any script in this folder. Framework
  customization happens inside the container, with Claude's help.

Documentation: https://github.com/DAAF-Contribution-Community/daaf
Website: https://daaf.openaugments.org
