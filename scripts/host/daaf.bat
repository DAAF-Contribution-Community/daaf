@echo off
REM ============================================================================
REM DAAF Launcher (Windows) -- double-clickable shim for the Control Panel
REM ============================================================================
REM WHAT THIS IS:
REM   A thin double-click launcher for Windows. When you double-click this file
REM   in File Explorer, Windows runs it. All it does is change into its own
REM   folder (your daaf-docker folder) and hand off to daaf.ps1 -- the real
REM   DAAF Control Panel. It adds no logic of its own beyond that handoff.
REM
REM WHY IT IS SAFE TO DOUBLE-CLICK:
REM   It runs no privileged commands, installs nothing, and touches no files. It
REM   only launches the Control Panel you would otherwise start by typing
REM   ".\daaf.ps1" in PowerShell. You can open it in Notepad to verify.
REM
REM WHY THE CD IS REQUIRED:
REM   Every DAAF host script expects docker-compose.yml in the CURRENT
REM   directory. "cd /d %~dp0" changes into this file's own folder (the drive
REM   and path it was launched from) so the Control Panel's preflight finds
REM   docker-compose.yml regardless of where Explorer started it.
REM
REM WHY PowerShell IS INVOKED DIRECTLY:
REM   The panel is run in THIS console window (no "start", no hidden window) so
REM   the interactive "docker compose exec -t" path keeps a real TTY. Launching
REM   it in a separate/hidden window would break Claude Code's TTY detection and
REM   force it into non-interactive --print mode (see daaf.ps1 console-
REM   inheritance notes). -ExecutionPolicy Bypass is PER-PROCESS only: it lets
REM   this one PowerShell run daaf.ps1 without changing any system policy.
REM
REM WHY THIS SHIM NEEDS NO DAAF_NESTED / DAAF_DRY_RUN HANDLING:
REM   Those environment variables are consumed by daaf.ps1 (and the scripts it
REM   delegates to), not here. As a pure passthrough shim, this launcher just
REM   invokes powershell; any DAAF_* variables set in the environment are
REM   inherited by the child process automatically, so the delegate sees them
REM   unchanged. There is nothing for this shim to interpret or forward.
REM
REM The universal fallback works everywhere: open PowerShell in this folder and
REM run ".\daaf.ps1" directly.
REM ============================================================================

REM --- Move into this launcher's own directory (the daaf-docker folder) ---
cd /d "%~dp0"

REM --- Guard: cmd.exe cannot use a UNC (network-share) path as its working ---
REM --- directory, so the cd above fails when this launcher lives on one.    ---
if errorlevel 1 (
    echo ERROR: Could not change into the DAAF folder.
    echo This launcher appears to live on a network ^(UNC^) path, which Windows
    echo cmd.exe cannot use as a working directory. Copy the daaf-docker folder
    echo to a local drive, or follow the terminal instructions in README.txt
    echo to launch DAAF with ".\daaf.ps1" from PowerShell instead.
    echo.
    pause
    exit /b 1
)

REM --- Verify the Control Panel is present before handing off ---
if not exist "%~dp0daaf.ps1" (
    echo ERROR: daaf.ps1 was not found next to this launcher.
    echo This launcher must live in your daaf-docker folder alongside daaf.ps1.
    echo If it is missing, re-run the installer or your update to restore it.
    echo.
    pause
    exit /b 1
)

REM --- Hand off to the real Control Panel, in this same console window ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0daaf.ps1"

REM --- Hold the window open only if PowerShell/the panel exited with an error ---
REM Clean quit from the menu returns 0 and closes without an extra pause;
REM daaf.ps1 handles its own in-script error prompts. Compare against "0"
REM explicitly (not `if errorlevel 1`, which is "1 or higher" and would miss a
REM NEGATIVE exit code from a PowerShell host crash) so any non-zero code pauses.
if not "%errorlevel%"=="0" (
    echo.
    echo DAAF exited with an error. Review the messages above.
    pause
)
