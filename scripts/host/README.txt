DAAF - Data Analyst Augmentation Framework
===========================================

This folder contains DAAF's host-side tools.

START HERE (double-click, no typing):

    Windows:         double-click daaf.bat  (or the DAAF shortcut the installer
                     drops in this folder, which you can drag to your Desktop)
    macOS:           double-click DAAF.command
    Linux:           no double-click launcher ships. Open a terminal in this
                     folder (your file manager's "Open Terminal Here") and run
                     the command below. Linux desktops run double-clicked
                     scripts too inconsistently to ship one.

START HERE (terminal - works everywhere):

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
- The double-click launchers (daaf.bat, DAAF.command) are thin wrappers
  that just open the Control Panel above - nothing you need to edit. The
  installer places and enables them for you. If you ever obtain DAAF.command
  by downloading it in a browser (rather than via the installer), macOS may
  block it once as "unidentified developer"; allow it via System Settings >
  Privacy & Security > "Open Anyway". Installer-placed copies are not blocked.

Documentation: https://github.com/DAAF-Contribution-Community/daaf
Website: https://daaf.openaugments.org
