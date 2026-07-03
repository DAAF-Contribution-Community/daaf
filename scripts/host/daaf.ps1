# ============================================================================
# DAAF Control Panel (Windows PowerShell)
# ============================================================================
# Interactive menu wrapper for all DAAF operations. Presents a status
# dashboard and numbered options for launching services, managing backups,
# and performing maintenance.
#
# Usage:
#   cd daaf-docker
#   .\daaf.ps1
#
# This is the top-level entry point on Windows -- it runs a persistent menu
# loop and delegates to individual .ps1 scripts via DAAF_NESTED=1 to suppress
# their pause-on-exit prompts. It is the PowerShell counterpart to daaf.sh
# (macOS/Linux) and mirrors its menu, dashboard, and behavior.
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

$ErrorActionPreference = "Stop"

# --- Source shared library ---
# Resolve this script's directory from MyInvocation so the library resolves
# whether the panel is executed directly or dot-sourced by Pester (where
# $PSCommandPath may point at the test runner).
$DaafScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $DaafScriptDir "daaf_lib.ps1")

# --- Multi-instance settings ---
# Bridge environment_settings.txt's DAAF_* keys into the process environment so
# `docker compose` interpolation resolves the project name and published host
# ports. See Import-DaafSettingsFile in daaf_lib.ps1 for the full rationale.
Import-DaafSettingsFile

# Host-facing ports for browser URLs and status display (default to the fixed
# container ports so existing single-instance installs behave identically).
$DaafPortMarimo = if ($env:DAAF_PORT_MARIMO) { $env:DAAF_PORT_MARIMO } else { "2718" }
$DaafPortLogViewer = if ($env:DAAF_PORT_LOGVIEWER) { $env:DAAF_PORT_LOGVIEWER } else { "2719" }
$DaafPortVscode = if ($env:DAAF_PORT_VSCODE) { $env:DAAF_PORT_VSCODE } else { "2720" }

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate Docker for CI cross-platform smoke testing
# without a Docker daemon. Mirrors daaf.sh's docker() dry-run shim: the status
# probes return empty (no services listening), git metadata returns canned
# values, and every other invocation is a no-op that echoes a [DRY-RUN] marker.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*compose ps -q daaf-docker*" { Write-Output "abc123" }
            "*compose ps --status running*--format*" { Write-Output "daaf-docker" }
            "*compose exec*PORT:*" { return }
            "*compose exec*/proc/net/tcp*" { return }
            "*compose exec*git*describe*" { Write-Output "v2.0.0" }
            "*compose exec*git*log*" { Write-Output "2026-06-21" }
            "*compose exec*git*branch*" { Write-Output "main" }
            "*compose exec*git*rev-list*" { Write-Output "0" }
            "*compose exec -d*" { return }
            "*compose exec*" { return }
            default { Write-Host "[DRY-RUN] docker $argStr"; return }
        }
    }
}

# --- Preflight ---
# Skipped under DAAF_TEST_MODE so the Pester harness can dot-source this file
# (to load the function definitions further below) without a real Docker daemon.
if ($env:DAAF_TEST_MODE -ne "1") {
    if (-not (Test-Path "docker-compose.yml")) {
        Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
        Write-Host "Please run this script from your daaf-docker folder."
        if (-not $env:DAAF_NESTED) { $null = Read-DaafLine "Press Enter to close" }
        exit 1
    }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from PowerShell." -ForegroundColor Red
        Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
        if (-not $env:DAAF_NESTED) { $null = Read-DaafLine "Press Enter to close" }
        exit 1
    }

    $savedEAP = $ErrorActionPreference
    try { $ErrorActionPreference = "SilentlyContinue"; $null = docker info 2>&1 } finally { $ErrorActionPreference = $savedEAP }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
        if (-not $env:DAAF_NESTED) { $null = Read-DaafLine "Press Enter to close" }
        exit 1
    }
}

# ============================================================================
# Status Gathering
# ============================================================================

# Populates the script-scoped STATUS_* variables the menu reads. Mirrors
# daaf.sh gather_status: checks container state first, then (if running)
# gathers version/date/branch/updates and probes ports 2718/2719/2720; finally
# finds the most recent local *_daaf_backup folder.
function Get-DaafStatus {
    # Container running? `docker compose ps -q daaf-docker` prints the running
    # container's ID (empty when stopped), derived from the compose project
    # rather than matching a hardcoded container name.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $cidRaw = docker compose ps -q daaf-docker 2>$null
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    $running = -not [string]::IsNullOrWhiteSpace(($cidRaw | Out-String))

    if (-not $running) {
        $script:STATUS_CONTAINER = "Stopped"
        $script:STATUS_VERSION = "--"
        $script:STATUS_DATE = ""
        $script:STATUS_BRANCH = "--"
        $script:STATUS_UPDATES = ""
        $script:STATUS_PORT_2718 = $false
        $script:STATUS_PORT_2719 = $false
        $script:STATUS_PORT_2720 = $false
    } else {
        $script:STATUS_CONTAINER = "Running"

        # Container-side git metadata. PowerShell has no cheap parallel-exec
        # idiom that is PS-5.1-safe, so these run sequentially (a handful of
        # fast exec calls). Each strips carriage returns and falls back to a
        # sensible default, matching daaf.sh's `|| echo` fallbacks.
        $script:STATUS_VERSION = (Invoke-DaafGit "describe" "--tags" "--always")
        if (-not $script:STATUS_VERSION) { $script:STATUS_VERSION = "unknown" }
        $script:STATUS_DATE    = (Invoke-DaafGit "log" "-1" "--format=%cd" "--date=short")
        $script:STATUS_BRANCH  = (Invoke-DaafGit "branch" "--show-current")
        if (-not $script:STATUS_BRANCH) { $script:STATUS_BRANCH = "detached" }
        $script:STATUS_UPDATES = (Invoke-DaafGit "rev-list" "--count" "HEAD..origin/main")

        # Port probes reuse the shared Test-DaafPort helper (container-side
        # /proc/net/tcp probe copied verbatim from daaf_lib.sh).
        $script:STATUS_PORT_2718 = (Test-DaafPort 2718)
        $script:STATUS_PORT_2719 = (Test-DaafPort 2719)
        $script:STATUS_PORT_2720 = (Test-DaafPort 2720)
    }

    # Local backup check (no Docker needed). Timestamp-prefixed names sort
    # lexicographically, so the last match is the newest backup. Mirrors
    # daaf.sh's glob-array last-element lookup (the very line that was fatal
    # under Bash 3.2 -- PowerShell has no such subscript hazard).
    $backupDirs = @(Get-ChildItem -Path "." -Directory -Filter "*_daaf_backup" -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($backupDirs.Count -gt 0) {
        $lastBackup = $backupDirs[$backupDirs.Count - 1].Name
        $script:STATUS_LAST_BACKUP = ($lastBackup -replace "_daaf_backup", "")
    } else {
        $script:STATUS_LAST_BACKUP = ""
    }
}

# Run `docker compose exec ... git -C /daaf <args>` and return trimmed,
# CR-stripped stdout (empty string on failure). Uses SilentlyContinue so PS 5.1
# does not promote Docker/git stderr to a terminating error under EAP = Stop.
function Invoke-DaafGit {
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $raw = @(docker compose exec -T daaf-docker git -C /daaf @args 2>$null)
        $result = ($raw | Out-String)
        return ($result -replace "`r", "").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# ============================================================================
# Menu Display
# ============================================================================

function Show-DaafMenu {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  DAAF Control Panel"
    Write-Host "=========================================="
    Write-Host ""

    # --- Status dashboard ---
    if ($script:STATUS_CONTAINER -eq "Running") {
        Write-Host "  Container:  " -NoNewline; Write-Host "* Running" -ForegroundColor Green
    } else {
        Write-Host "  Container:  " -NoNewline; Write-Host "o Stopped" -ForegroundColor DarkGray
    }

    # Version line
    $versionLine = "  Version:    $($script:STATUS_VERSION)"
    if ($script:STATUS_DATE) {
        $versionLine = "$versionLine ($($script:STATUS_DATE))"
    }
    Write-Host $versionLine

    # Branch line
    $branchLine = "  Branch:     $($script:STATUS_BRANCH)"
    if ($script:STATUS_UPDATES -and $script:STATUS_UPDATES -ne "0") {
        $branchLine = "$branchLine ($($script:STATUS_UPDATES) updates available)"
    } elseif ($script:STATUS_UPDATES) {
        $branchLine = "$branchLine (up to date)"
    }
    Write-Host $branchLine

    # Last backup
    if ($script:STATUS_LAST_BACKUP) {
        Write-Host "  Last backup: $($script:STATUS_LAST_BACKUP)"
    } else {
        Write-Host "  Last backup: never"
    }

    Write-Host ""

    # --- Services ---
    Write-Host "  Services:"
    if ($script:STATUS_PORT_2718) {
        Write-Host "    " -NoNewline; Write-Host "* Notebooks    localhost:$DaafPortMarimo" -ForegroundColor Green
    } else {
        Write-Host "    o Notebooks    (not running)" -ForegroundColor DarkGray
    }
    if ($script:STATUS_PORT_2719) {
        Write-Host "    " -NoNewline; Write-Host "* Log Viewer   localhost:$DaafPortLogViewer" -ForegroundColor Green
    } else {
        Write-Host "    o Log Viewer   (not running)" -ForegroundColor DarkGray
    }
    if ($script:STATUS_PORT_2720) {
        Write-Host "    " -NoNewline; Write-Host "* VS Code      localhost:$DaafPortVscode" -ForegroundColor Green
    } else {
        Write-Host "    o VS Code      (not running)" -ForegroundColor DarkGray
    }

    Write-Host ""

    # --- Menu options ---
    Write-Host "  LAUNCH"
    Write-Host "    1) Start Claude Code"
    Write-Host "    2) Browse Notebooks"
    Write-Host "    3) Browse Files (VS Code)"
    Write-Host "    4) View Session Logs"
    Write-Host "    5) Open Container Shell"

    Write-Host ""

    Write-Host "  MANAGE"
    Write-Host "    6) Create Backup"
    Write-Host "    7) Restore from Backup"
    Write-Host "    8) Check for Updates"
    Write-Host "    9) Rebuild Container"
    Write-Host "   10) Stop Web Services"

    Write-Host ""

    Write-Host "  OTHER"
    Write-Host "    h) Help"
    Write-Host "    q) Quit"

    Write-Host ""
}

# ============================================================================
# Input
# ============================================================================

# Read a menu choice into the script-scoped $script:CHOICE. Returns $false when
# input is exhausted (EOF -- e.g., CI piping a single `q`) so the main loop can
# quit cleanly, mirroring daaf.sh read_choice's EOF-to-quit behavior.
function Read-DaafChoice {
    $line = Read-DaafLine "  Enter choice"
    if ($null -eq $line) {
        # EOF on stdin (CI piped a finite input, or terminal closed). Treat as
        # explicit quit so the main loop exits cleanly and CI assertions hold.
        Write-Host ""
        Write-Host "Goodbye!"
        return $false
    }
    $script:CHOICE = $line
    return $true
}

# ============================================================================
# Dispatch
# ============================================================================

# Returns $false only for the quit choice (signals the main loop to stop);
# every other choice returns $true so the loop redraws the menu.
function Invoke-DaafChoice {
    param([string]$Choice)

    switch ($Choice) {
        "1"  { Invoke-DaafClaudeCode; return $true }
        "2"  { Invoke-DaafNotebookBrowser; return $true }
        "3"  { Invoke-DaafVSCode; return $true }
        "4"  { Invoke-DaafLogViewer; return $true }
        "5"  { Invoke-DaafShell; return $true }
        "6"  { Invoke-DaafBackup; return $true }
        "7"  { Invoke-DaafRestore; return $true }
        "8"  { Invoke-DaafUpdate; return $true }
        "9"  { Invoke-DaafRebuild; return $true }
        "10" { Invoke-DaafServiceStop; return $true }
        { $_ -in @("h", "H") } { Show-DaafHelp; return $true }
        { $_ -in @("q", "Q") } { Invoke-DaafQuit; return $false }
        "" { return $true }  # Empty input -- just redraw
        default {
            Write-Host "  Invalid choice. Please enter a number (1-10), h, or q."
            return $true
        }
    }
}

# ============================================================================
# Handlers: Interactive (options 1, 5)
# ============================================================================

# run_delegate equivalent for a delegated .ps1 that takes over the terminal
# (Claude Code, container shell). Guards the child exit so a non-zero return
# does not abort the panel -- control always returns to the menu with the
# failure surfaced. DAAF_NESTED=1 suppresses the child's pause-on-exit prompt.
function Invoke-DaafDelegateInteractive {
    param(
        [string]$ScriptName,
        [string[]]$ScriptArgs = @(),
        [string]$FailureMessage
    )
    $env:DAAF_NESTED = "1"
    try {
        $global:LASTEXITCODE = 0
        & (Join-Path $script:DaafScriptDir $ScriptName) @ScriptArgs
        $ec = $LASTEXITCODE
    } finally {
        Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
    }
    if ($ec -and $ec -ne 0) {
        Write-Host ""
        Write-Host "  $FailureMessage" -ForegroundColor Yellow
    }
}

function Invoke-DaafClaudeCode {
    Write-Host ""
    Write-Host "Launching Claude Code..."
    Write-Host "(When you're done, type /exit to return to this menu)"
    Write-Host ""
    Invoke-DaafDelegateInteractive "run_daaf.ps1" @() "Claude Code session ended with an error."
    Write-Host ""
    Write-Host "Returned to DAAF Control Panel."
}

function Invoke-DaafShell {
    Write-Host ""
    Write-Host "Opening container shell..."
    Write-Host "(Type 'exit' to return to this menu)"
    Write-Host ""
    Invoke-DaafDelegateInteractive "run_daaf.ps1" @("bash") "Container shell ended with an error."
    Write-Host ""
    Write-Host "Returned to DAAF Control Panel."
}

# ============================================================================
# Handlers: Web services (options 2, 3, 4)
# ============================================================================

function Invoke-DaafNotebookBrowser {
    Write-Host ""
    Write-Host "Starting notebook browser..."

    # Ensure the container is up before attempting docker compose exec, so we
    # give a clear message instead of letting a failed exec surface obscurely.
    if (-not (Confirm-DaafContainer)) {
        Write-Host "  Could not start the DAAF container. Is Docker running?" -ForegroundColor Yellow
        return
    }

    if (Test-DaafPort 2718) {
        Write-Host "  Marimo is already running."
    } else {
        # Capture stderr (do NOT discard) so a container-side launch failure is
        # distinguishable from a slow start. A non-zero exit returns to the menu.
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $launchErr = docker compose exec -d daaf-docker bash /daaf/scripts/launch_marimo.sh --background 2>&1
            $launchExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($launchExit -and $launchExit -ne 0) {
            Write-Host "  Failed to start the notebook server:" -ForegroundColor Yellow
            Write-Host "  $launchErr"
            return
        }

        $elapsed = 0
        while ($elapsed -lt 10) {
            if (Test-DaafPort 2718) { break }
            Start-Sleep -Seconds 1
            $elapsed++
        }

        if (-not (Test-DaafPort 2718)) {
            Write-Host "  Server may still be starting. Try the URL in a moment." -ForegroundColor Yellow
        } else {
            Write-Host "  Server started."
        }
    }

    # Browser URL uses the HOST-published port ($DaafPortMarimo); the container
    # port probed above stays fixed at 2718.
    $url = "http://localhost:$DaafPortMarimo"
    Write-Host ""
    Write-Host "  $url" -ForegroundColor Cyan
    Write-Host ""
    Open-DaafUrl $url
}

function Invoke-DaafVSCode {
    Write-Host ""
    Write-Host "Starting VS Code browser..."

    # Ensure the container is up before attempting docker compose exec.
    if (-not (Confirm-DaafContainer)) {
        Write-Host "  Could not start the DAAF container. Is Docker running?" -ForegroundColor Yellow
        return
    }

    # code-server runs with --auth password; the launcher prints the password to
    # its own stdout, which is lost under `exec -d`. Mirror launch_code_server.sh's
    # default here so the menu can display it. Honor a PASSWORD override if the
    # user exported one before launching the panel.
    # Default mirrors launch_code_server.sh (PASSWORD env var overrides both).
    $vscodePassword = if ($env:PASSWORD) { $env:PASSWORD } else { "daaf" }

    if (Test-DaafPort 2720) {
        Write-Host "  VS Code is already running."
    } else {
        # Capture stderr (do NOT discard) so a container-side launch failure --
        # e.g., a stale image without code-server -- is visible rather than
        # masquerading as "still starting". Non-zero exit returns to the menu.
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $launchErr = docker compose exec -d daaf-docker bash /daaf/scripts/launch_code_server.sh --background 2>&1
            $launchExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($launchExit -and $launchExit -ne 0) {
            Write-Host "  Failed to start VS Code (code-server):" -ForegroundColor Yellow
            Write-Host "  $launchErr"
            return
        }

        $elapsed = 0
        while ($elapsed -lt 10) {
            if (Test-DaafPort 2720) { break }
            Start-Sleep -Seconds 1
            $elapsed++
        }

        if (-not (Test-DaafPort 2720)) {
            Write-Host "  Server may still be starting. Try the URL in a moment." -ForegroundColor Yellow
        } else {
            Write-Host "  Server started."
        }
    }

    # Browser URL uses the HOST-published port ($DaafPortVscode); the container
    # port probed above stays fixed at 2720.
    $url = "http://localhost:$DaafPortVscode"
    Write-Host ""
    Write-Host "  $url" -ForegroundColor Cyan
    Write-Host "  Password: $vscodePassword"
    Write-Host ""
    Open-DaafUrl $url
}

function Invoke-DaafLogViewer {
    Write-Host ""
    Write-Host "Discovering available log sources..."

    # Ensure the container is up before attempting docker compose exec.
    if (-not (Confirm-DaafContainer)) {
        Write-Host "  Could not start the DAAF container. Is Docker running?" -ForegroundColor Yellow
        return
    }

    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $sourcesRaw = docker compose exec -T daaf-docker bash /daaf/scripts/discover_log_sources.sh 2>$null
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    $sources = (($sourcesRaw | Out-String) -replace "`r", "").Trim()

    if ([string]::IsNullOrWhiteSpace($sources)) {
        Write-Host "  No session logs found. Run a DAAF session first to generate logs."
        return
    }

    $paths = @()
    $labels = @()

    foreach ($line in ($sources -split "`n")) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split '\|'
        $sourceId = $parts[0].Trim()
        $sessionCount = if ($parts.Count -gt 1) { $parts[1].Trim() } else { "" }
        if ([string]::IsNullOrWhiteSpace($sourceId)) { continue }
        if ($sourceId -eq "ARCHIVE") {
            $paths += "ARCHIVE"
            $labels += "Full session archive ($sessionCount sessions)"
        } else {
            $folderName = Split-Path $sourceId -Leaf
            $displayDate = ($folderName -split '_')[0]
            $displayTitle = ($folderName -replace '^[^_]*_', '') -replace '_', ' '
            $paths += $sourceId
            $labels += "$displayDate $displayTitle ($sessionCount sessions)"
        }
    }

    if ($labels.Count -eq 0) {
        Write-Host "  No session logs found. Run a DAAF session first to generate logs."
        return
    }

    Write-Host ""
    Write-Host "  Select a log source:"
    Write-Host ""
    for ($i = 0; $i -lt $labels.Count; $i++) {
        Write-Host ("    {0}) {1}" -f ($i + 1), $labels[$i])
    }
    Write-Host ""
    Write-Host "    0) Back to main menu"
    Write-Host ""

    $choice = Read-DaafLine "  Enter choice"

    if ($choice -eq "0" -or [string]::IsNullOrWhiteSpace($choice)) {
        return
    }

    if (($choice -notmatch '^[0-9]+$') -or ([int]$choice -lt 1) -or ([int]$choice -gt $paths.Count)) {
        Write-Host "  Invalid selection."
        return
    }

    $selected = $paths[[int]$choice - 1]

    # --- Step 1: Generate the manifest for the SELECTED source ---
    # Capture stderr so a generation failure (e.g., empty archive) produces an
    # accurate message instead of a dead URL. A failure here returns to the menu.
    Write-Host ""
    Write-Host "  Generating session manifest..."
    if ($selected -eq "ARCHIVE") {
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $manifestErr = docker compose exec -T daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive --no-serve 2>&1
            $manifestExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($manifestExit -and $manifestExit -ne 0) {
            Write-Host "  Could not generate the session manifest:" -ForegroundColor Yellow
            Write-Host "  $manifestErr"
            Write-Host "  The full archive may be empty. Run a DAAF session, or" -ForegroundColor Yellow
            Write-Host "  choose a specific project source instead." -ForegroundColor Yellow
            return
        }
        $url = "http://localhost:$DaafPortLogViewer/scripts/log_viewer.html?manifest=.claude/logs/sessions/session_manifest.json"
    } else {
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $manifestErr = docker compose exec -T daaf-docker bash /daaf/scripts/generate_log_viewer.sh $selected --no-serve 2>&1
            $manifestExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($manifestExit -and $manifestExit -ne 0) {
            Write-Host "  Could not generate the session manifest:" -ForegroundColor Yellow
            Write-Host "  $manifestErr"
            return
        }
        $relPath = $selected -replace '^/daaf/', ''
        $url = "http://localhost:$DaafPortLogViewer/scripts/log_viewer.html?manifest=$relPath/logs/session_manifest.json"
    }

    # --- Step 2: Ensure the log viewer server is running ---
    # Start the server against the SELECTED source, not always --archive, so a
    # valid project selection is not left with a dead URL when the DAAF-wide
    # archive is empty. Serving from the chosen source decouples the two.
    if (-not (Test-DaafPort 2719)) {
        Write-Host "  Starting log viewer server..."
        if ($selected -eq "ARCHIVE") {
            $serveArgs = @("--archive", "--background")
        } else {
            $serveArgs = @($selected, "--background")
        }
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $serveErr = docker compose exec -d daaf-docker bash /daaf/scripts/generate_log_viewer.sh @serveArgs 2>&1
            $serveExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($serveExit -and $serveExit -ne 0) {
            Write-Host "  Could not start the log viewer server:" -ForegroundColor Yellow
            Write-Host "  $serveErr"
            return
        }

        $elapsed = 0
        while ($elapsed -lt 10) {
            if (Test-DaafPort 2719) { break }
            Start-Sleep -Seconds 1
            $elapsed++
        }

        if (-not (Test-DaafPort 2719)) {
            Write-Host "  Server may still be starting. Try the URL in a moment." -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "  $url" -ForegroundColor Cyan
    Write-Host ""
    Open-DaafUrl $url
}

# ============================================================================
# Handlers: Maintenance (options 6-9)
# ============================================================================

# Invoke-DaafDelegate <script-name> -- run a delegated child .ps1 with
# DAAF_NESTED=1. Guards the child's exit code: a non-zero exit (child failure,
# user abort, or the graceful "no backups found" case in
# restore_from_backup.ps1) prints a clear message and returns to the menu
# rather than aborting the panel. Mirrors daaf.sh run_delegate.
function Invoke-DaafDelegate {
    param([string]$ScriptName)
    Write-Host ""
    $env:DAAF_NESTED = "1"
    try {
        $global:LASTEXITCODE = 0
        & (Join-Path $script:DaafScriptDir $ScriptName)
        $ec = $LASTEXITCODE
    } finally {
        Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
    }
    if (-not $ec -or $ec -eq 0) {
        Write-Host ""
        Write-Host "Returned to DAAF Control Panel."
    } else {
        Write-Host ""
        Write-Host "  $ScriptName exited without completing (code $ec)." -ForegroundColor Yellow
        Write-Host "Returned to DAAF Control Panel."
    }
}

function Invoke-DaafBackup  { Invoke-DaafDelegate "backup_daaf.ps1" }
function Invoke-DaafRestore { Invoke-DaafDelegate "restore_from_backup.ps1" }
function Invoke-DaafUpdate  { Invoke-DaafDelegate "update_daaf.ps1" }
function Invoke-DaafRebuild { Invoke-DaafDelegate "rebuild_daaf.ps1" }

# ============================================================================
# Handler: Stop Services (option 10)
# ============================================================================

# Named with Invoke- (like the other menu handlers) rather than the natural
# Stop- verb: PSSA's PSUseShouldProcessForStateChangingFunctions requires
# SupportsShouldProcess on Stop-* functions, which is wrong ceremony for an
# interactive menu handler that has its own confirmation prompt.
function Invoke-DaafServiceStop {
    Write-Host ""

    $marimoRunning = Test-DaafPort 2718
    $logsRunning   = Test-DaafPort 2719
    $vscodeRunning = Test-DaafPort 2720
    $svcRunning = $marimoRunning -or $logsRunning -or $vscodeRunning

    if (-not $svcRunning) {
        Write-Host "  No web services are currently running."
        return
    }

    Write-Host "  Running services:"
    if ($marimoRunning) {
        Write-Host "    " -NoNewline; Write-Host "* Notebooks    (port 2718)" -ForegroundColor Green
    }
    if ($logsRunning) {
        Write-Host "    " -NoNewline; Write-Host "* Log Viewer   (port 2719)" -ForegroundColor Green
    }
    if ($vscodeRunning) {
        Write-Host "    " -NoNewline; Write-Host "* VS Code      (port 2720)" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "    1) Stop all"
    Write-Host "    0) Back"
    Write-Host ""

    $choice = Read-DaafLine "  Enter choice"

    if ($choice -eq "1") {
        Write-Host "  Stopping services..."
        # Container-side stop payload -- VERBATIM from daaf.sh handle_stop_services.
        # Maps each listening port to its owning PID via /proc/net/tcp (inode) ->
        # /proc/*/fd (socket symlink) -> PID, then kills it. `ss` is not present
        # in the image, so this reuses the /proc pattern from
        # generate_log_viewer.sh. Surface stderr so failures are visible.
        $stopScript = @'
            for port in 2718 2719 2720; do
                ph=$(printf "%04X" "$port")
                inode=$(awk -v ph="$ph" '$2 ~ ":"ph"$" && $4 == "0A" {print $10}' \
                    /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -1)
                [ -z "$inode" ] && continue
                pid=$(find /proc -maxdepth 3 -path "*/fd/*" -exec ls -la {} + 2>/dev/null \
                    | grep "socket:\[$inode\]" | head -1 \
                    | sed "s|.*/proc/\([0-9]*\)/.*|\1|")
                case "$pid" in
                    ""|*[!0-9]*) continue ;;
                esac
                if kill "$pid" 2>/dev/null; then
                    echo "    Stopped service on port $port (PID $pid)"
                else
                    echo "    Could not stop service on port $port (PID $pid)"
                fi
            done
'@
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            docker compose exec -T daaf-docker bash -c $stopScript
            $stopExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($stopExit -and $stopExit -ne 0) {
            Write-Host "  Warning: could not reach the container to stop services." -ForegroundColor Yellow
        }
        Write-Host "  Done."
    }
}

# ============================================================================
# Handler: Help (option h)
# ============================================================================

function Show-DaafHelp {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  DAAF Control Panel -- Help"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "  LAUNCH"
    Write-Host ""
    Write-Host "  1) Start Claude Code" -ForegroundColor Cyan
    Write-Host "     Launch an interactive Claude Code session inside the DAAF"
    Write-Host "     container. Type /exit within Claude to return to this menu."
    Write-Host ""
    Write-Host "  2) Browse Notebooks" -ForegroundColor Cyan
    Write-Host "     Open the marimo notebook browser (port 2718). Browse, open,"
    Write-Host "     create, and edit research notebooks across all projects."
    Write-Host ""
    Write-Host "  3) Browse Files (VS Code)" -ForegroundColor Cyan
    Write-Host "     Open code-server (port 2720) for browser-based file browsing"
    Write-Host "     and editing. Useful for reviewing scripts and data files."
    Write-Host ""
    Write-Host "  4) View Session Logs" -ForegroundColor Cyan
    Write-Host "     Browse session transcripts from previous DAAF sessions."
    Write-Host "     Select a project or the full archive to view logs."
    Write-Host ""
    Write-Host "  5) Open Container Shell" -ForegroundColor Cyan
    Write-Host "     Drop into a bash shell inside the DAAF container."
    Write-Host "     Type 'exit' to return to this menu."
    Write-Host ""
    Write-Host "  MANAGE"
    Write-Host ""
    Write-Host "  6) Create Backup" -ForegroundColor Cyan
    Write-Host "     Create a timestamped backup of your DAAF Docker volume."
    Write-Host "     Backups are saved in the current directory."
    Write-Host ""
    Write-Host "  7) Restore from Backup" -ForegroundColor Cyan
    Write-Host "     Restore a previous backup to the DAAF Docker volume."
    Write-Host "     You will be prompted to select which backup to restore."
    Write-Host ""
    Write-Host "  8) Check for Updates" -ForegroundColor Cyan
    Write-Host "     Check for and apply updates to the DAAF framework."
    Write-Host ""
    Write-Host "  9) Rebuild Container" -ForegroundColor Cyan
    Write-Host "     Rebuild the DAAF Docker container from the latest image."
    Write-Host "     Your data volume is preserved during rebuilds."
    Write-Host ""
    Write-Host "  10) Stop Web Services" -ForegroundColor Cyan
    Write-Host "      Stop any running web services (notebooks, log viewer,"
    Write-Host "      VS Code) without stopping the container itself."
    Write-Host ""
    Write-Host "  OTHER"
    Write-Host ""
    Write-Host "  h) Help" -ForegroundColor Cyan -NoNewline; Write-Host "  -- Show this help screen"
    Write-Host "  q) Quit" -ForegroundColor Cyan -NoNewline; Write-Host "  -- Exit the control panel"
    Write-Host ""
    $null = Read-DaafLine "  Press Enter to continue"
}

# ============================================================================
# Handler: Quit (option q)
# ============================================================================

function Invoke-DaafQuit {
    Write-Host ""
    Write-Host "Goodbye!"
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip the menu loop.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# ============================================================================
# Main Loop
# ============================================================================
# Wrapped in try/catch/finally so an unexpected failure prints a diagnostic and
# pauses -- a double-clicked window must not vanish before the error can be read
# (parity with daaf.sh's ERR + EXIT traps). Ctrl+C surfaces as a
# PipelineStoppedException, which we treat as a clean "Goodbye!".
try {
    while ($true) {
        Get-DaafStatus
        Show-DaafMenu
        if (-not (Read-DaafChoice)) { break }
        if (-not (Invoke-DaafChoice $script:CHOICE)) { break }
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: DAAF Control Panel hit an unexpected failure." -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  This is a bug -- please report it. The panel will now exit." -ForegroundColor Red
    # Pause so a double-clicked window does not vanish before the diagnostic can
    # be read. Skips the pause in nested/dry-run/non-interactive/redirected-stdin
    # contexts so CI smoke tests never block here.
    try { $pauseOk = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) }
    catch { $pauseOk = $false }
    if ((-not $env:DAAF_NESTED) -and ($env:DAAF_DRY_RUN -ne "1") -and $pauseOk) {
        $null = Read-DaafLine "Press Enter to close"
    }
    exit 1
}
