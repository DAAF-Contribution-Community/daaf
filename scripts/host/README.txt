DAAF - Data Analyst Augmentation Framework
===========================================

This folder contains DAAF's host-side tools.

START HERE:

    bash daaf.sh

That opens the DAAF Control Panel - a menu with everything: starting
Claude Code, notebooks, VS Code, session logs, backups, updates, and
rebuilds. It is the only command you need to remember.

The other scripts in this folder are helpers that the Control Panel
calls for you. Each one also works standalone if you prefer, e.g.:

    bash backup_daaf.sh        make a backup
    bash update_daaf.sh        update DAAF
    bash view_notebooks.sh     open the notebook browser

NOTES:

- environment_settings.txt is where your data source API keys go
  (copy environment_settings_example.txt to get started).
- Folders ending in _daaf_backup are your backups. Safe to move or
  delete; the Control Panel can restore from them.
- If the updater says it updated itself, run it once more to finish
  syncing the tools in this folder.
- You should not need to edit any script in this folder. Framework
  customization happens inside the container, with Claude's help.

Documentation: https://github.com/DAAF-Contribution-Community/daaf
