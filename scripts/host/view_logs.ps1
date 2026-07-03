# ============================================================================
# DAAF Log Explorer (Windows PowerShell)
# ============================================================================
# Opens the interactive session log viewer in your browser.
# Starts the DAAF container if needed, recovers any orphaned session logs,
# presents available log sources, and starts an HTTP server.
#
# Usage:
#   cd daaf-docker
#   .\view_logs.ps1              # Interactive menu
#   .\view_logs.ps1 --archive    # Skip menu, open full archive
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Port 2719 mapped in docker-compose.yml
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

$ErrorActionPreference = "Stop"

function Wait-AndExit {
    param([int]$Code = 0)
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    exit $Code
}

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# process environment so `docker compose` interpolation resolves the project name
# and published host ports. Canonical shared pattern (kept in sync with
# Import-DaafSettingsFile in daaf_lib.ps1); standalone scripts that do NOT dot-source
# daaf_lib.ps1 inline it. Parse only these four keys (never dot-source -- the file
# holds API keys); process env wins; absent file = no-op; CR stripped; PS 5.1 safe.
function Import-DaafSettingsInline {
    param([string]$SettingsFile = "./environment_settings.txt")
    if (-not (Test-Path -LiteralPath $SettingsFile)) { return }
    $known = @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE')
    foreach ($rawLine in (Get-Content -LiteralPath $SettingsFile)) {
        $line = $rawLine -replace "`r", ""
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        if ($known -notcontains $key) { continue }
        $val = $line.Substring($eq + 1)
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            if ($val.Length -ge 2) { $val = $val.Substring(1, $val.Length - 2) }
        }
        $current = [Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrEmpty($current)) {
            Set-Item -Path ("Env:" + $key) -Value $val
        }
    }
}
Import-DaafSettingsInline

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI
# cross-platform smoke testing without a Docker daemon.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*compose ps -q daaf-docker*" { Write-Output "abc123" }
            "*compose up*" { return }
            "*compose exec*" { return }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/view_logs.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# --- Parse arguments ---
$SkipMenu = $false
$SelectedSource = ""

foreach ($arg in $args) {
    switch ($arg) {
        "--archive" {
            $SkipMenu = $true
            $SelectedSource = "--archive"
        }
        { $_ -in "-h", "--help" } {
            Write-Host "Usage: .\view_logs.ps1              # Interactive log source menu"
            Write-Host "       .\view_logs.ps1 --archive    # Open full session archive directly"
            exit 0
        }
        default {
            Write-Host "ERROR: Unknown argument: $arg" -ForegroundColor Red
            Write-Host "Usage: .\view_logs.ps1 [--archive]"
            Wait-AndExit 1
        }
    }
}

# In non-interactive contexts, default to archive view
if ($env:DAAF_DRY_RUN -eq "1" -or $env:CI -or $env:DAAF_NESTED) {
    $SkipMenu = $true
    if (-not $SelectedSource) { $SelectedSource = "--archive" }
}

# --- Preflight ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host "Please run this script from your daaf-docker folder."
    Wait-AndExit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Wait-AndExit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running. Please start it and try again." -ForegroundColor Red
    Wait-AndExit 1
}

# --- Start container if not running ---
# `docker compose ps -q daaf-docker` prints the running container's ID (empty
# when stopped), derived from the compose project rather than a hardcoded name.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$CidOutput = docker compose ps -q daaf-docker 2>&1
$ErrorActionPreference = $savedEAP
$Running = if ([string]::IsNullOrWhiteSpace(($CidOutput | Out-String))) { 0 } else { 1 }

if ($Running -eq 0) {
    Write-Host "Starting DAAF container..."
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose up -d
    $ErrorActionPreference = $savedEAP
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start the container." -ForegroundColor Red
        Wait-AndExit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is running."
}

# --- Recover orphaned session logs ---
# The recovery hook archives transcripts from sessions that ended without
# a clean SessionEnd (e.g., crashes). The hook's foreground portion returns
# immediately, but actual recovery runs in a detached background subshell
# inside the container (& disown). The sleep gives that subprocess time to
# finish before we discover log sources.
Write-Host "Checking for orphaned session logs..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
'{"session_id":"recovery","transcript_path":"/home/appuser/.claude/projects/-daaf/_.jsonl"}' | docker compose exec -T -e CLAUDE_PROJECT_DIR=/daaf daaf-docker bash /daaf/.claude/hooks/recover-session-logs.sh 2>$null
$global:LASTEXITCODE = 0
$ErrorActionPreference = $savedEAP
if ($env:DAAF_DRY_RUN -ne "1") {
    Start-Sleep -Seconds 2
}

# --- Select log source ---
if (-not $SkipMenu) {
    # Discover all log sources via helper script (avoids bash -c quoting issues)
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $SourcesRaw = docker compose exec -T daaf-docker bash /daaf/scripts/discover_log_sources.sh 2>$null
    $ErrorActionPreference = $savedEAP

    # Build menu from pipe-delimited output
    $MenuPaths = @()
    $MenuLabels = @()

    if ($SourcesRaw) {
        foreach ($line in @($SourcesRaw)) {
            $cleanLine = "$line".Trim()
            if (-not $cleanLine) { continue }
            $parts = $cleanLine -split '\|', 2
            if ($parts.Count -lt 2) { continue }
            $sourceId = $parts[0].Trim()
            $sessionCount = 0
            $null = [int]::TryParse(($parts[1] -replace '\D', '').Trim(), [ref]$sessionCount)
            if ($sessionCount -eq 0) { continue }

            $countWord = "sessions"
            if ($sessionCount -eq 1) { $countWord = "session" }

            if ($sourceId -eq "ARCHIVE") {
                $MenuPaths += "--archive"
                $MenuLabels += "Full session archive ($sessionCount $countWord)"
            } else {
                $folderName = Split-Path $sourceId -Leaf
                $underscoreIdx = $folderName.IndexOf('_')
                if ($underscoreIdx -gt 0) {
                    $displayDate = $folderName.Substring(0, $underscoreIdx)
                    $displayTitle = $folderName.Substring($underscoreIdx + 1) -replace '_', ' '
                } else {
                    $displayDate = ""
                    $displayTitle = $folderName
                }
                $MenuPaths += $sourceId
                $MenuLabels += "$displayDate $displayTitle ($sessionCount $countWord)"
            }
        }
    }

    if ($MenuPaths.Count -eq 0) {
        Write-Host ""
        Write-Host "No log sources found. Run a DAAF session first to generate logs."
        Wait-AndExit 0
    }

    Write-Host ""
    Write-Host "DAAF Log Explorer -- Select a log source:"
    Write-Host ""
    for ($i = 0; $i -lt $MenuLabels.Count; $i++) {
        Write-Host ("  {0}) {1}" -f ($i + 1), $MenuLabels[$i])
    }
    Write-Host ""
    $selection = Read-Host "Enter selection"

    $selNum = 0
    if (-not [int]::TryParse($selection, [ref]$selNum) -or $selNum -lt 1 -or $selNum -gt $MenuPaths.Count) {
        Write-Host "ERROR: Invalid selection: $selection" -ForegroundColor Red
        Wait-AndExit 1
    }

    $SelectedSource = $MenuPaths[$selNum - 1]
}

# --- Launch log viewer ---
Write-Host ""
Write-Host "Opening DAAF Log Explorer..."
Write-Host ""
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
if ($SelectedSource -eq "--archive") {
    docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive
} else {
    docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh "$SelectedSource"
}
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to generate log viewer." -ForegroundColor Red
    Write-Host "  The container may not be running, or there may be no session logs to display." -ForegroundColor Red
    Write-Host "  Try: docker compose logs daaf-docker" -ForegroundColor Yellow
}

# If the server was already running, the command above returns immediately
# after printing the URL. Wait-AndExit keeps the window open so the user
# can read/copy it.
Wait-AndExit 0
