# ============================================================================
# DAAF Notebook Browser (Windows PowerShell)
# ============================================================================
# Opens marimo's notebook browser in your browser -- browse, open, create, and
# edit marimo notebooks across all your research projects.
# Starts the DAAF container if needed. The notebook server requires an access
# token that changes with every launch; the printed link carries it. A fresh
# launch keeps the server in this window until Ctrl+C and only prints the link;
# the browser opens automatically only when a notebook server was already
# running.
#
# Usage:
#   cd daaf-docker
#   .\view_notebooks.ps1
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Port 2718 mapped in docker-compose.yml
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"
# pwsh 7.4+ only (an ordinary, unused variable on Windows PowerShell 5.1): never turn a
# native command's nonzero exit into an error record or a throw. The native calls here
# read $LASTEXITCODE themselves (same line as backup_daaf.ps1 and restore_from_backup.ps1).
# With it set to $true under 'Stop', a nonzero native exit throws
# NativeCommandExitException (observed 2026-11-01, PowerShell 7.6.3).
$PSNativeCommandUseErrorActionPreference = $false

function Wait-AndExit {
    param([int]$Code = 0)
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    exit $Code
}

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's seven whitelisted DAAF_* keys into the
# process environment so `docker compose` interpolation resolves the project name
# and published host ports. Canonical shared pattern (kept in sync with
# Import-DaafSettingsFile in daaf_lib.ps1); standalone scripts that do NOT dot-source
# daaf_lib.ps1 inline it. Parse only these whitelisted keys (never dot-source -- the file
# holds API keys); process env wins; absent file = no-op; CR stripped; PS 5.1 safe.
function Import-DaafSettingsInline {
    param([string]$SettingsFile = "./environment_settings.txt")
    if (-not (Test-Path -LiteralPath $SettingsFile)) { return }
    $known = @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV', 'DAAF_BRANCH', 'DAAF_DATA_VOLUME_NAME')
    # -Encoding UTF8: PS 5.1's bare Get-Content misreads BOM-less UTF-8 as ANSI
    # (cp1252); the settings writer is BOM-less UTF-8, so reads are pinned to match.
    foreach ($rawLine in (Get-Content -LiteralPath $SettingsFile -Encoding UTF8)) {
        $line = $rawLine -replace "`r", ""
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        # Extract the key WITHOUT trimming: a leading or trailing space means the
        # line is not flush at column 0, so it must fall through as unrecognized --
        # matching the bash loaders' column-0 `case` glob so a padded key like
        # "  DAAF_PROJECT_NAME=..." is rejected identically on both platforms.
        $key = $line.Substring(0, $eq)
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

# --- Project flag for printed commands ---
# A `docker compose` command printed for the user runs in the user's own shell,
# where DAAF_PROJECT_NAME from environment_settings.txt is not set, so it would
# reach the default install 'daaf'. For any other project the printed command
# carries `-p <project>`, as install.ps1 prints it. The name is normalized the
# way Resolve-DaafProjectName in daaf_lib.ps1 does it.
$HintProject = 'daaf'
if ($env:DAAF_PROJECT_NAME) { $HintProject = ($env:DAAF_PROJECT_NAME -creplace '[^A-Za-z0-9_-]', '').ToLowerInvariant().TrimStart('_', '-') }
$ComposePFlag = if ($HintProject -and $HintProject -ne 'daaf') { "-p $HintProject " } else { "" }

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
            "*--print-token*" { Write-Output "dryruntoken"; return }
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
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/view_notebooks.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Enable strict mode AFTER the test-mode guard. Set-StrictMode is dynamically
# scoped, so placing it here keeps Pester's dot-sourcing (which returns above)
# from leaking strict mode into the whole test session, while real executions
# run fully protected from this point on.
Set-StrictMode -Version 3.0

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
# Stdout only (2>$null): a stderr line, such as a Compose warning, is not a container
# ID and must not make a stopped container look running.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$CidOutput = docker compose ps -q daaf-docker 2>$null
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

Write-Host ""
Write-Host "Opening DAAF Notebook Browser..."
Write-Host ""
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose exec daaf-docker bash /daaf/scripts/launch_marimo.sh
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to start the notebook browser." -ForegroundColor Red
    Write-Host "  The container may not be running, or marimo may not be installed." -ForegroundColor Red
    Write-Host "  Try: docker compose ${ComposePFlag}logs daaf-docker" -ForegroundColor Yellow
}

# Open the browser (parity with view_notebooks.sh). The URL uses the HOST-published
# port (DAAF_PORT_MARIMO); the container port stays fixed at 2718.
# marimo requires the access token launch_marimo.sh generates for each launch, so
# ask the running server for it (--print-token). Its stdout carries only the token,
# which stays in a variable and is never written to a file or log. -T: no TTY, so
# the captured value has no CR. Stdout only (2>$null): the exit code, not a stderr
# line, decides. If nothing is running any more (a foreground launch ended with
# Ctrl+C) or the server has no known token (an older launcher's --no-token server;
# launch_marimo.sh printed what to do), --print-token fails and nothing is opened.
$MarimoHostPort = if ($env:DAAF_PORT_MARIMO) { $env:DAAF_PORT_MARIMO } else { "2718" }
$savedEAP = $ErrorActionPreference
try {
    $ErrorActionPreference = "SilentlyContinue"
    $MarimoTokenOutput = docker compose exec -T daaf-docker bash /daaf/scripts/launch_marimo.sh --print-token 2>$null
    $TokenExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedEAP
}
$MarimoToken = ($MarimoTokenOutput | Out-String) -replace '\s', ''
if ($TokenExit -eq 0 -and $MarimoToken -match '^[A-Za-z0-9_-]+$') {
    Write-Host "Opening the notebook browser in your default browser..."
    $NotebookUrl = "http://localhost:$MarimoHostPort/?access_token=$MarimoToken"
    if ($env:DAAF_DRY_RUN -ne "1") {
        try {
            # FilePath-only open of a URL (no argv; pinned in native_arg_quoting.Tests.ps1).
            $null = Start-Process $NotebookUrl
        } catch {
            # No handler available (headless, restricted shell) -- the link printed
            # above by launch_marimo.sh still works when opened by hand.
            Write-Verbose "Silenced: $_"
        }
    }
}

# If marimo was already running, the container-side script returns immediately
# after printing the URL. Wait-AndExit keeps the window open so the user
# can read/copy it.
Wait-AndExit 0
