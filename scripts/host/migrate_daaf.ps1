# ============================================================================
# DAAF Migration Script (Windows PowerShell)
# ============================================================================
# Migrates existing DAAF installations to the new update infrastructure.
#
# This script is for users who installed DAAF before update_daaf.ps1 existed.
# It downloads the host utility scripts, backs up the volume, detects your
# installation type (git clone vs ZIP download), and connects your local git
# history to the upstream repository so that update_daaf.ps1 works going
# forward.
#
# Usage (one-liner):
#   irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/migrate_daaf.ps1 | iex
#
# Or download and run:
#   Invoke-WebRequest -Uri https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/migrate_daaf.ps1 -OutFile migrate_daaf.ps1
#   .\migrate_daaf.ps1
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection
#   - An existing DAAF installation (Docker volume daaf_daaf-data exists)
#
# This script is idempotent - safe to run multiple times. If the migration
# has already been completed, it will detect that and skip ahead.
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

$ErrorActionPreference = "Stop"

# Ensure TLS 1.2 for GitHub downloads (required on PowerShell 5.1)
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

# --- Pause before exit so the user can review output ---
# Skip the prompt when called from another script (DAAF_NESTED).
# Always calls exit so the window closes cleanly after the user presses
# Enter — including when invoked via irm ... | iex (which terminates the
# PowerShell session, but the user has already read the output).
function Wait-ForUser {
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to close this window"
    }
    exit
}

# --- Configuration ---
$Repo = "DAAF-Contribution-Community/daaf"
$Branch = if ($env:DAAF_BRANCH) { $env:DAAF_BRANCH } else { "main" }
$RawBase = "https://raw.githubusercontent.com/$Repo/$Branch"
$VolumeName = "daaf_daaf-data"
$ContainerName = ""
$BackupCompleted = $false
$IsFork = $false
$DetectedEra = ""
$UpdateChoice = "n"

# --- Detect non-interactive mode (curl-pipe equivalent) ---
$NonInteractive = $false
try {
    if (-not [Environment]::UserInteractive) {
        $NonInteractive = $true
    } elseif ([Console]::IsInputRedirected) {
        $NonInteractive = $true
    }
} catch {
    # Console properties unavailable (e.g., ISE, remoting) — default to interactive
    Write-Verbose "Silenced: $_"
}

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, Invoke-WebRequest)
# for CI cross-platform smoke testing without a Docker daemon.
# Mock simulates an era-1 clone-based installation (already migrated path).
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*volume inspect*" { return }
            "*ps -a*--filter*volume=*--format*" {
                Write-Output "daaf-daaf-docker-1"
            }
            "*inspect*--format*Status*" {
                Write-Output "running"
            }
            "*exec*true*" { return }
            "*exec*test -f*" { return }
            "*exec*git -C /daaf remote get-url origin*" {
                Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
            }
            "*exec*git -C /daaf fetch*" { return }
            "*exec*git -C /daaf branch --set-upstream*" { return }
            "*exec*git -C /daaf remote get-url upstream*" {
                $global:LASTEXITCODE = 1
                return
            }
            "*exec*git*" { return }
            "*exec*" { return }
            "*start*" { return }
            "*compose up*" { return }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }

    function Invoke-WebRequest {
        param(
            [switch]$UseBasicParsing,
            [string]$Uri,
            [string]$OutFile
        )
        # Acknowledge parameters accepted for interface compatibility
        $null = $UseBasicParsing, $Uri
        if ($OutFile) {
            $parentDir = Split-Path $OutFile -Parent
            if ($parentDir -and -not (Test-Path $parentDir)) {
                New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
            }
            # Write a minimal stub that exits cleanly (for nested script calls)
            Set-Content -Path $OutFile -Value "exit 0"
        }
    }

    # Force non-interactive to skip the update prompt at the end
    $NonInteractive = $true
}

# --- Trap handler for unexpected failures ---
trap {
    Write-Host "" -ForegroundColor Red
    Write-Host "-------------------------------------------" -ForegroundColor Red
    Write-Host "  Something went wrong unexpectedly" -ForegroundColor Red
    Write-Host "-------------------------------------------" -ForegroundColor Red
    Write-Host ""
    Write-Host "Your research files and data are safe - the migration only changes"
    Write-Host "framework git history, not your research/ folder."
    Write-Host ""
    if ($BackupCompleted) {
        Write-Host "A backup was created before any changes were made."
    } else {
        Write-Host "No changes were made to your installation."
    }
    Write-Host ""
    Write-Host "Most likely causes:"
    Write-Host "  - Docker Desktop stopped (laptop sleep, lid closed)"
    Write-Host "  - Internet connection dropped during download"
    Write-Host "  - A temporary Docker glitch"
    Write-Host ""
    Write-Host "To try again:"
    Write-Host "  1. Make sure Docker Desktop is running"
    Write-Host "  2. Re-run:  .\migrate_daaf.ps1"
    Write-Host "     (It is safe to re-run - it will pick up where it left off.)"
    Write-Host ""
    if ($Mutex) { try { $Mutex.ReleaseMutex() } catch { <# Mutex already released or not owned — safe to ignore #> Write-Verbose "Silenced: $_" } }
    Wait-ForUser; return
}

# =====================================================================
# Helper functions
# =====================================================================

function Read-UserChoice {
    param(
        [string]$PromptText,
        [string[]]$ValidChoices
    )
    while ($true) {
        $choice = (Read-Host $PromptText).Trim().ToLower()
        if ($ValidChoices -contains $choice) { return $choice }
        Write-Host "  Please enter one of: $($ValidChoices -join ', ')" -ForegroundColor Yellow
    }
}

# Override Read-UserChoice in dry-run mode (must come after the real definition
# since the later definition overwrites the earlier one at the same scope)
if ($env:DAAF_DRY_RUN -eq "1") {
    function Read-UserChoice {
        param([string]$PromptText, [string[]]$ValidChoices)
        $null = $PromptText  # Accept param for interface compatibility
        Write-Host "[DRY-RUN] Auto-selecting: $($ValidChoices[0])"
        return $ValidChoices[0]
    }
}

# Run a git command inside the container (strips carriage returns, suppresses stderr)
# Uses SilentlyContinue to prevent PS 5.1 from promoting stderr to a terminating
# error when $ErrorActionPreference is "Stop" in the caller's scope.
function Invoke-ContainerGit {
    param([Parameter(ValueFromRemainingArguments=$true)]$GitArgs)
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $result = docker exec $script:ContainerName git -C /daaf @GitArgs 2>$null | Out-String
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run a git command inside the container, allowing stderr through
# Uses SilentlyContinue to prevent PS 5.1 from promoting stderr to a terminating
# error when $ErrorActionPreference is "Stop" in the caller's scope.
function Invoke-ContainerGitVerbose {
    param([Parameter(ValueFromRemainingArguments=$true)]$GitArgs)
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $result = docker exec $script:ContainerName git -C /daaf @GitArgs | Out-String
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run an arbitrary command inside the container
# Uses SilentlyContinue to prevent PS 5.1 from promoting stderr to a terminating
# error when $ErrorActionPreference is "Stop" in the caller's scope.
function Invoke-ContainerExec {
    param([Parameter(ValueFromRemainingArguments=$true)]$ExecArgs)
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker exec $script:ContainerName @ExecArgs
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run a shell command inside the container, capturing stdout as a string.
# Suppresses stderr and strips carriage returns. Returns trimmed string.
# Uses SilentlyContinue to prevent PS 5.1 from promoting stderr to a terminating
# error when $ErrorActionPreference is "Stop" in the caller's scope.
function Invoke-ContainerShell {
    param([string]$ShellCommand)
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $result = docker exec $script:ContainerName sh -c $ShellCommand 2>$null | Out-String
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run a shell command inside the container, capturing stdout+stderr as a string.
# Strips carriage returns. Returns trimmed string.
# Uses SilentlyContinue to prevent PS 5.1 from promoting stderr to a terminating
# error when $ErrorActionPreference is "Stop" in the caller's scope.
function Invoke-ContainerShellVerbose {
    param([string]$ShellCommand)
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $result = docker exec $script:ContainerName sh -c $ShellCommand 2>&1 | Out-String
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/migrate_daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# =====================================================================
# Concurrent-run lock
# =====================================================================
# Prevent two instances from operating on the same container simultaneously.
# The mutex is released on normal exit or when the process terminates.

$MutexName = "Global\DAAFMigrate"
$Mutex = [System.Threading.Mutex]::new($false, $MutexName)
try {
    if (-not $Mutex.WaitOne(0)) {
        Write-Host "ERROR: Another instance of migrate_daaf is already running." -ForegroundColor Red
        Write-Host "       Wait for it to finish or restart Docker Desktop to clear the lock." -ForegroundColor Yellow
        Wait-ForUser
        return
    }
} catch [System.Threading.AbandonedMutexException] {
    # Previous instance crashed — we inherited ownership of the mutex, safe to continue
    Write-Verbose "Silenced: $_"
}

# =====================================================================
# Main script
# =====================================================================

Write-Host ""
Write-Host "=========================================="
Write-Host "  DAAF Migration"
Write-Host "=========================================="
Write-Host ""
Write-Host "This script migrates your existing DAAF installation to support"
Write-Host "the new update infrastructure (update_daaf.ps1)."
Write-Host ""

# =====================================================================
# 1. PREFLIGHT
# =====================================================================
Write-Host "-------------------------------------------"
Write-Host "  Preflight checks"
Write-Host "-------------------------------------------"
Write-Host ""

# --- Docker installed ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from PowerShell." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Wait-ForUser; return
}

# --- Docker running ---
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    Wait-ForUser; return
}

Write-Host "Docker is running."

# --- Volume exists ---
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker volume inspect $VolumeName 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Docker volume '$VolumeName' not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "This script is for migrating an existing DAAF installation."
    Write-Host "If you haven't installed DAAF yet, use the installer instead:"
    Write-Host "  irm $RawBase/scripts/host/install.ps1 | iex"
    Wait-ForUser; return
}

Write-Host "Found DAAF volume: $VolumeName"

# --- Determine host directory ---
# If docker-compose.yml exists in the current directory, use it.
# Otherwise, create daaf-docker\ as install.ps1 would.
if (Test-Path "docker-compose.yml") {
    $HostDir = (Get-Location).Path
    Write-Host "Using current directory: $HostDir"
} else {
    $HostDir = Join-Path (Get-Location).Path "daaf-docker"
    Write-Host "Will create host directory: $HostDir"
    New-Item -ItemType Directory -Path $HostDir -Force | Out-Null
}

Write-Host ""

# =====================================================================
# 2. DOWNLOAD HOST SCRIPTS
# =====================================================================
Write-Host "-------------------------------------------"
Write-Host "  Downloading host scripts"
Write-Host "-------------------------------------------"
Write-Host ""

Write-Host "Downloading utility scripts from GitHub..."

$DownloadFailed = $false

foreach ($File in @("backup_daaf.ps1", "rebuild_daaf.ps1", "update_daaf.ps1", "run_daaf.ps1", "view_logs.ps1", "env.example")) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/$File" -OutFile "$HostDir\$File"
        Write-Host "  Downloaded: $File"
    } catch {
        Write-Host "  FAILED: $File"
        $DownloadFailed = $true
    }
}

if ($DownloadFailed) {
    Write-Host ""
    Write-Host "ERROR: Failed to download one or more utility scripts." -ForegroundColor Red
    Write-Host "Please check your internet connection and try again."
    Wait-ForUser; return
}

# Download Dockerfile and docker-compose.yml if not already present
if (-not (Test-Path "$HostDir\Dockerfile")) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/Dockerfile" -OutFile "$HostDir\Dockerfile"
        Write-Host "  Downloaded: Dockerfile"
    } catch {
        Write-Host ""
        Write-Host "ERROR: Failed to download Dockerfile." -ForegroundColor Red
        Write-Host "Please check your internet connection and try again."
        Wait-ForUser; return
    }
}

if (-not (Test-Path "$HostDir\docker-compose.yml")) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/docker-compose.yml" -OutFile "$HostDir\docker-compose.yml"
        Write-Host "  Downloaded: docker-compose.yml"
    } catch {
        Write-Host ""
        Write-Host "ERROR: Failed to download docker-compose.yml." -ForegroundColor Red
        Write-Host "Please check your internet connection and try again."
        Wait-ForUser; return
    }
} else {
    # Even if docker-compose.yml exists, update it so it has name: daaf
    # (v1.0.0 installations may lack this)
    $composeContent = Get-Content "$HostDir\docker-compose.yml" -Raw
    if ($composeContent -notmatch '(?m)^name: daaf') {
        Write-Host ""
        Write-Host "  Updating docker-compose.yml to current version..."
        Copy-Item "$HostDir\docker-compose.yml" "$HostDir\docker-compose.yml.pre-migrate" -Force
        try {
            Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/docker-compose.yml" -OutFile "$HostDir\docker-compose.yml"
            Write-Host "  Updated: docker-compose.yml (old version saved as docker-compose.yml.pre-migrate)"
        } catch {
            Write-Host "  WARNING: Could not download updated docker-compose.yml. Restoring original." -ForegroundColor Yellow
            Move-Item "$HostDir\docker-compose.yml.pre-migrate" "$HostDir\docker-compose.yml" -Force
        }
    }
}

Write-Host ""
Write-Host "All scripts downloaded to: $HostDir\"
Write-Host ""

# =====================================================================
# 3. BACKUP
# =====================================================================
Write-Host "-------------------------------------------"
Write-Host "  Backup"
Write-Host "-------------------------------------------"
Write-Host ""
Write-Host "Before making any changes, a full backup of your DAAF volume will"
Write-Host "be created. This protects your research data and local history."
Write-Host ""

$OriginalDir = (Get-Location).Path
Set-Location $HostDir
$env:DAAF_NESTED = "1"
& .\backup_daaf.ps1
$backupExit = $LASTEXITCODE
Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
Set-Location $OriginalDir
if ($backupExit -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Backup failed (exit code $backupExit)."
    Write-Host "The migration will not proceed without a successful backup."
    Write-Host "Please resolve the backup issue and re-run: .\migrate_daaf.ps1"
    Wait-ForUser; return
}
$BackupCompleted = $true

Write-Host ""

# =====================================================================
# 4. START CONTAINER (if not running)
# =====================================================================
Write-Host "-------------------------------------------"
Write-Host "  Starting container"
Write-Host "-------------------------------------------"
Write-Host ""

# Discover container dynamically from the volume
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$AllContainers = (docker ps -a --filter "volume=$VolumeName" --format '{{.Names}}' | Out-String) -replace "`r",""
$ErrorActionPreference = $savedEAP
$AllContainersList = @($AllContainers.Trim() -split "`n" | Where-Object { $_.Trim() -ne "" })
$ContainerCount = $AllContainersList.Count
$ContainerName = if ($ContainerCount -gt 0) { $AllContainersList[0].Trim() } else { "" }

if ($ContainerCount -gt 1) {
    Write-Host "WARNING: Multiple containers found using the DAAF volume:" -ForegroundColor Yellow
    foreach ($c in $AllContainersList) {
        Write-Host "  $($c.Trim())"
    }
    Write-Host ""
    Write-Host "Using the first one: $ContainerName"
    Write-Host "If this is wrong, stop the other containers and re-run."
    Write-Host ""
}

if (-not [string]::IsNullOrWhiteSpace($ContainerName)) {
    Write-Host "Found existing container: $ContainerName"

    # Check if it's running
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $ContainerState = (docker inspect --format '{{.State.Status}}' $ContainerName 2>$null | Out-String).Trim() -replace "`r",""
    $ErrorActionPreference = $savedEAP
    if ([string]::IsNullOrWhiteSpace($ContainerState)) { $ContainerState = "unknown" }

    if ($ContainerState -ne "running") {
        Write-Host "Container is $ContainerState. Starting it..."
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        docker start $ContainerName 2>&1 | Out-Null
        $ErrorActionPreference = $savedEAP

        # Wait for readiness
        $retries = 0
        $maxRetries = 30
        while ($retries -lt $maxRetries) {
            Invoke-ContainerExec true 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { break }
            $retries++
            Start-Sleep -Seconds 2
        }
        if ($retries -ge $maxRetries) {
            Write-Host ""
            Write-Host "ERROR: Container did not become ready within 60 seconds." -ForegroundColor Red
            Write-Host "Try restarting Docker Desktop, then re-run:  .\migrate_daaf.ps1"
            Wait-ForUser; return
        }
        Write-Host "Container started."
    } else {
        Write-Host "Container is already running."
    }
} else {
    Write-Host "No existing container found. Starting one with docker compose..."

    $OriginalDirCompose = (Get-Location).Path
    Set-Location $HostDir

    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose up -d
    $ErrorActionPreference = $savedEAP
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Failed to start the DAAF container." -ForegroundColor Red
        Write-Host ""
        Write-Host "Common causes:"
        Write-Host "  - Another program is using the same ports"
        Write-Host "  - Docker Desktop needs more memory (Settings > Resources)"
        Write-Host ""
        Write-Host "Try restarting Docker Desktop, then re-run:  .\migrate_daaf.ps1"
        Set-Location $OriginalDirCompose
        Wait-ForUser; return
    }

    # After docker compose up, discover the container name
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $ContainerName = (docker ps -a --filter "volume=$VolumeName" --format '{{.Names}}' | Select-Object -First 1 | Out-String).Trim() -replace "`r",""
    $ErrorActionPreference = $savedEAP
    if ([string]::IsNullOrWhiteSpace($ContainerName)) {
        Write-Host "ERROR: Container started but could not be found." -ForegroundColor Red
        Write-Host "Try restarting Docker Desktop, then re-run:  .\migrate_daaf.ps1"
        Set-Location $OriginalDirCompose
        Wait-ForUser; return
    }

    Set-Location $OriginalDirCompose

    # Wait for readiness
    $retries = 0
    $maxRetries = 30
    while ($retries -lt $maxRetries) {
        Invoke-ContainerExec true 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        $retries++
        Start-Sleep -Seconds 2
    }
    if ($retries -ge $maxRetries) {
        Write-Host ""
        Write-Host "ERROR: Container started but is not responding after 60 seconds." -ForegroundColor Red
        Write-Host "Try restarting Docker Desktop, then re-run:  .\migrate_daaf.ps1"
        Wait-ForUser; return
    }
    Write-Host "Container started: $ContainerName"
}

Write-Host ""

# --- Verify DAAF is in the container ---
Invoke-ContainerExec test -f /daaf/CLAUDE.md
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: DAAF does not appear to be installed in the container." -ForegroundColor Red
    Write-Host "The volume exists but /daaf/CLAUDE.md was not found."
    Write-Host ""
    Write-Host "If this is a fresh installation, use the installer instead:"
    Write-Host "  irm $RawBase/scripts/host/install.ps1 | iex"
    Wait-ForUser; return
}

Write-Host "DAAF installation verified in container."
Write-Host ""

# =====================================================================
# 5. DETECT ERA
# =====================================================================
Write-Host "-------------------------------------------"
Write-Host "  Detecting installation type"
Write-Host "-------------------------------------------"
Write-Host ""

$OriginUrl = Invoke-ContainerGit remote get-url origin
# Invoke-ContainerGit returns "" on failure (stderr suppressed, empty stdout)

if (-not [string]::IsNullOrWhiteSpace($OriginUrl) -and $OriginUrl -match $Repo) {
    $DetectedEra = "1"
    Write-Host "Detected: clone-based installation (remote already configured)"
    Write-Host "Remote URL: $OriginUrl"
} elseif (-not [string]::IsNullOrWhiteSpace($OriginUrl)) {
    # Remote exists but points somewhere unexpected (likely a fork)
    $DetectedEra = "1"
    $IsFork = $true
    Write-Host "Detected: clone-based installation (remote already configured)"
    Write-Host "Remote URL: $OriginUrl"
    Write-Host ""
    Write-Host "NOTE: Your remote points to a location other than the official DAAF"
    Write-Host "repository. The migration will proceed, but you may want to verify"
    Write-Host "this is correct."
} else {
    $DetectedEra = "2"
    Write-Host "Detected: ZIP-based installation (no remote configured)"
    Write-Host "Your local history will be connected to the official DAAF timeline"
    Write-Host "so that future updates can merge cleanly with your work."
}

Write-Host ""

# =====================================================================
# 6a. ERA 1 PATH (v1.0.0 - remote exists)
# =====================================================================
if ($DetectedEra -eq "1") {
    Write-Host "-------------------------------------------"
    Write-Host "  Fetching upstream history"
    Write-Host "-------------------------------------------"
    Write-Host ""

    Write-Host "Running git fetch origin..."
    $null = Invoke-ContainerGitVerbose fetch origin
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Failed to fetch from origin." -ForegroundColor Red
        Write-Host ""
        Write-Host "Common causes:"
        Write-Host "  - No internet connection"
        Write-Host "  - GitHub may be experiencing an outage"
        Write-Host ""
        Write-Host "Once the issue is resolved, re-run:  .\migrate_daaf.ps1"
        Wait-ForUser; return
    }
    Write-Host "Fetch complete."

    # Ensure tracking is set up
    $null = Invoke-ContainerGit branch --set-upstream-to=origin/main main

    # --- For fork users: add upstream remote for official updates ---
    if ($IsFork) {
        $ExistingUpstream = Invoke-ContainerGit remote get-url upstream
        if ([string]::IsNullOrWhiteSpace($ExistingUpstream)) {
            Write-Host ""
            Write-Host "Your 'origin' remote points to a fork. Adding 'upstream' remote"
            Write-Host "for official DAAF updates..."
            $null = Invoke-ContainerGitVerbose remote add upstream "https://github.com/$Repo.git"
            if ($LASTEXITCODE -ne 0) {
                Write-Host ""
                Write-Host "WARNING: Could not add 'upstream' remote. You can add it" -ForegroundColor Yellow
                Write-Host "manually later:"
                Write-Host "  .\run_daaf.ps1 bash"
                Write-Host "  git remote add upstream https://github.com/$Repo.git"
                Write-Host "  git fetch upstream"
                Write-Host "  exit"
            } else {
                Write-Host "Fetching upstream history..."
                $null = Invoke-ContainerGitVerbose fetch upstream
                if ($LASTEXITCODE -ne 0) {
                    Write-Host ""
                    Write-Host "WARNING: Could not fetch from upstream. The 'upstream' remote was" -ForegroundColor Yellow
                    Write-Host "added but the fetch failed. You can retry later:"
                    Write-Host "  .\run_daaf.ps1 bash"
                    Write-Host "  git fetch upstream"
                    Write-Host "  exit"
                } else {
                    Write-Host "Fetch complete."
                }
            }
        } else {
            Write-Host ""
            Write-Host "'upstream' remote already configured: $ExistingUpstream"
        }
    }

    Write-Host ""
    if ($IsFork) {
        Write-Host "Migration complete. Your installation is connected to your fork"
        Write-Host "(origin) and the official DAAF repository (upstream)."
        Write-Host ""
        Write-Host "update_daaf.ps1 will pull official updates from 'upstream' and merge"
        Write-Host "them with your fork's changes."
    } else {
        Write-Host "Migration complete. Your installation is connected to upstream"
        Write-Host "and update_daaf.ps1 will work immediately."
    }
    Write-Host ""

# =====================================================================
# 6b. ERA 2 PATH (v2.0.0+ - no remote, need graft)
# =====================================================================
} else {
    Write-Host "-------------------------------------------"
    Write-Host "  Connecting to upstream repository"
    Write-Host "-------------------------------------------"
    Write-Host ""

    # --- Check if remote was already added (idempotent) ---
    $ExistingOrigin = Invoke-ContainerGit remote get-url origin
    if (-not [string]::IsNullOrWhiteSpace($ExistingOrigin)) {
        Write-Host "Remote 'origin' already exists: $ExistingOrigin"
        Write-Host "Skipping remote add (previous migration attempt detected)."
    } else {
        Write-Host "Adding remote origin..."
        $null = Invoke-ContainerGitVerbose remote add origin "https://github.com/$Repo.git"
        Write-Host "Remote added."
    }

    Write-Host ""

    # --- Fetch full history ---
    Write-Host "Fetching upstream history (this may take a moment)..."
    $null = Invoke-ContainerGitVerbose fetch origin
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Failed to fetch from origin." -ForegroundColor Red
        Write-Host ""
        Write-Host "Common causes:"
        Write-Host "  - No internet connection"
        Write-Host "  - GitHub may be experiencing an outage"
        Write-Host ""
        Write-Host "Once the issue is resolved, re-run:  .\migrate_daaf.ps1"
        Wait-ForUser; return
    }
    Write-Host "Fetch complete."

    Write-Host ""

    # --- Find the initial (root) commit ---
    $InitialCommits = Invoke-ContainerGitVerbose rev-list --max-parents=0 HEAD

    if ([string]::IsNullOrWhiteSpace($InitialCommits)) {
        Write-Host ""
        Write-Host "ERROR: Could not find git history in the container." -ForegroundColor Red
        Write-Host "The volume exists but no git repository was found at /daaf/."
        Write-Host ""
        Write-Host "If this is a fresh installation, use the installer instead:"
        Write-Host "  irm $RawBase/scripts/host/install.ps1 | iex"
        Wait-ForUser; return
    }

    # Parse commits into array
    $InitialCommitsList = $InitialCommits -split "`n" | Where-Object { $_.Trim() -ne "" } | ForEach-Object { $_.Trim() }
    $RootCount = $InitialCommitsList.Count

    # If multiple root commits exist, use the last (oldest) one
    $InitialCommit = $InitialCommitsList[-1]

    if ($RootCount -gt 1) {
        Write-Host "NOTE: Found $RootCount root commits. Using the oldest one"
        Write-Host "      ($($InitialCommit.Substring(0, [Math]::Min(12, $InitialCommit.Length)))) for graft matching."
        Write-Host ""
    }

    # --- Check if graft is already in place (idempotent) ---
    $CatFileOutput = Invoke-ContainerGitVerbose cat-file -p $InitialCommit
    $InitialParentCount = 0
    if (-not [string]::IsNullOrWhiteSpace($CatFileOutput)) {
        $InitialParentCount = ($CatFileOutput -split "`n" | Where-Object { $_ -match '^parent ' }).Count
    }

    if ($InitialParentCount -gt 0) {
        Write-Host "History graft already in place (root commit has a parent)."
        Write-Host "Skipping graft step (previous migration completed successfully)."
        Write-Host ""
    } else {
        # --- Find matching upstream commit ---
        Write-Host "Analyzing local initial commit..."
        Write-Host ""

        # Get the blob fingerprint of the initial local commit
        # We compare only (blob_hash, filepath) pairs, ignoring file modes
        $LocalTree = Invoke-ContainerShell "cd /daaf && git ls-tree -r '$InitialCommit' | awk '{print `$3, `$4}' | sort"

        if ([string]::IsNullOrWhiteSpace($LocalTree)) {
            Write-Host ""
            Write-Host "ERROR: Could not compute file fingerprint for the initial commit."
            Write-Host "The git repository may be corrupted."
            Write-Host ""
            Write-Host "You can try a fresh install instead:"
            Write-Host "  irm $RawBase/scripts/host/install.ps1 | iex"
            Wait-ForUser; return
        }

        $MatchingCommit = ""
        $MatchType = ""

        # Try known tags first, then origin/main HEAD
        Write-Host "Searching for matching upstream commit..."
        Write-Host ""

        $Candidates = @("v2.0.1", "v2.0.0", "v1.0.0")

        # Check which tags actually exist
        $ValidCandidates = @()
        foreach ($Tag in $Candidates) {
            $null = Invoke-ContainerGit rev-parse --verify $Tag
            if ($LASTEXITCODE -eq 0) {
                $ValidCandidates += $Tag
            } else {
                $null = Invoke-ContainerGit rev-parse --verify "origin/$Tag"
                if ($LASTEXITCODE -eq 0) {
                    $ValidCandidates += "origin/$Tag"
                }
            }
        }

        # Also try origin/main HEAD
        $ValidCandidates += "origin/main"

        $Step = 0
        $TotalCandidates = $ValidCandidates.Count

        foreach ($Candidate in $ValidCandidates) {
            $Step++
            $CandidateSha = Invoke-ContainerGit rev-parse $Candidate
            if ([string]::IsNullOrWhiteSpace($CandidateSha)) {
                continue
            }

            Write-Host "  Checking $Candidate ($Step/$TotalCandidates)..." -NoNewline

            $CandidateTree = Invoke-ContainerShell "cd /daaf && git ls-tree -r '$CandidateSha' | awk '{print `$3, `$4}' | sort"

            if ($LocalTree -eq $CandidateTree) {
                $MatchingCommit = $CandidateSha
                $MatchType = "exact"
                Write-Host " EXACT MATCH"
                Write-Host ""
                Write-Host "  Matched: $Candidate ($($CandidateSha.Substring(0, [Math]::Min(12, $CandidateSha.Length))))"
                break
            } else {
                Write-Host " no match"
            }
        }

        # If no exact match from known candidates, search all commits on origin/main
        # This runs the entire search inside a SINGLE docker exec call to avoid
        # the overhead of hundreds of individual docker exec invocations.
        if ([string]::IsNullOrWhiteSpace($MatchingCommit)) {
            Write-Host ""
            Write-Host "  No exact match from known tags. Searching all upstream commits..."
            Write-Host "  (This runs inside the container and may take 30-60 seconds.)"
            Write-Host ""

            # Build a skip list of SHAs we already checked
            $SkipList = ""
            foreach ($Candidate in $ValidCandidates) {
                $CandidateSha = Invoke-ContainerGit rev-parse $Candidate
                if (-not [string]::IsNullOrWhiteSpace($CandidateSha)) {
                    $SkipList = "$SkipList $CandidateSha"
                }
            }

            # Run the full search inside the container in one exec call.
            # Output format: "EXACT:<sha>" or "BEST:<sha>:<overlap>:<local_count>"
            # Progress lines go to stderr (prefixed with PROGRESS:)
            # Temporarily lower ErrorActionPreference so PS 5.1 does not promote
            # stderr progress output to a terminating error.
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $SearchResultRaw = @'
cd /daaf

# Save local blob fingerprint to temp file
git ls-tree -r "$INITIAL" | awk '{print $3, $4}' | sort > /tmp/migrate_local_blobs.txt
LOCAL_COUNT=$(wc -l < /tmp/migrate_local_blobs.txt)

BEST_SHA=""
BEST_OVERLAP=0
TOTAL=$(git rev-list origin/main | wc -l)
NUM=0

for COMMIT in $(git rev-list origin/main); do
    NUM=$((NUM + 1))

    # Skip already-checked commits
    case " $SKIP_SHAS " in
        *" $COMMIT "*) continue ;;
    esac

    # Progress every 20 commits (to stderr so it does not mix with result)
    if [ $((NUM % 20)) -eq 0 ]; then
        printf "  Searching commit %d/%d...\r" "$NUM" "$TOTAL" >&2
    fi

    # Generate candidate blob fingerprint
    git ls-tree -r "$COMMIT" | awk '{print $3, $4}' | sort > /tmp/migrate_cand_blobs.txt

    # Exact match check (fast)
    if diff -q /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt >/dev/null 2>&1; then
        echo "EXACT:$COMMIT"
        rm -f /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt
        exit 0
    fi

    # Track best fuzzy match
    OVERLAP=$(comm -12 /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt | wc -l)
    if [ "$OVERLAP" -gt "$BEST_OVERLAP" ]; then
        BEST_OVERLAP=$OVERLAP
        BEST_SHA=$COMMIT
    fi
done

rm -f /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt
echo "BEST:$BEST_SHA:$BEST_OVERLAP:$LOCAL_COUNT"
'@ | docker exec -i -e "INITIAL=$InitialCommit" -e "SKIP_SHAS=$SkipList" $ContainerName sh 2>&1 | Out-String
            $ErrorActionPreference = $savedEAP
            $SearchResult = ($SearchResultRaw -replace "`r","").Trim()

            # Parse the result (last non-empty line matching EXACT/BEST is the result;
            # earlier lines are progress)
            $ResultLine = ""
            foreach ($line in ($SearchResult -split "`n")) {
                if ($line -match '^(EXACT|BEST):') {
                    $ResultLine = $line.Trim()
                }
            }

            if ($ResultLine -match '^EXACT:') {
                $MatchingCommit = ($ResultLine -split ':')[1]
                $MatchType = "exact"
                Write-Host ""
                Write-Host "  EXACT MATCH found: $($MatchingCommit.Substring(0, [Math]::Min(12, $MatchingCommit.Length)))"
            } elseif ($ResultLine -match '^BEST:') {
                $parts = $ResultLine -split ':'
                $BestMatchSha = $parts[1]
                $BestMatchOverlap = [int]$parts[2]
                $LocalLineCount = [int]$parts[3]

                $OverlapPct = 0
                if (-not [string]::IsNullOrWhiteSpace($BestMatchSha) -and $LocalLineCount -gt 0) {
                    $OverlapPct = [math]::Floor($BestMatchOverlap * 100 / $LocalLineCount)
                }

                if ($OverlapPct -ge 95) {
                    $MatchingCommit = $BestMatchSha
                    $MatchType = "fuzzy ($OverlapPct% blob overlap)"
                    Write-Host ""
                    Write-Host "  Best match: $($BestMatchSha.Substring(0, [Math]::Min(12, $BestMatchSha.Length))) ($OverlapPct% overlap)"
                } else {
                    Write-Host ""
                    Write-Host "  WARNING: No upstream commit matches your initial commit well enough." -ForegroundColor Yellow
                    if (-not [string]::IsNullOrWhiteSpace($BestMatchSha)) {
                        Write-Host "  Best candidate: $($BestMatchSha.Substring(0, [Math]::Min(12, $BestMatchSha.Length))) ($OverlapPct% overlap)"
                    }
                    Write-Host ""
                }
            }
        }

        # Fallback: graft onto latest known tag
        if ([string]::IsNullOrWhiteSpace($MatchingCommit)) {
            Write-Host "  Falling back to grafting onto the latest known tag..."

            $FallbackTag = ""
            foreach ($Tag in @("v2.0.1", "v2.0.0", "v1.0.0")) {
                $null = Invoke-ContainerGit rev-parse --verify $Tag
                if ($LASTEXITCODE -eq 0) {
                    $FallbackTag = $Tag
                    break
                }
                $null = Invoke-ContainerGit rev-parse --verify "origin/$Tag"
                if ($LASTEXITCODE -eq 0) {
                    $FallbackTag = "origin/$Tag"
                    break
                }
            }

            if (-not [string]::IsNullOrWhiteSpace($FallbackTag)) {
                $MatchingCommit = Invoke-ContainerGit rev-parse $FallbackTag
                $MatchType = "fallback ($FallbackTag)"
                Write-Host ""
                Write-Host "  WARNING: Using fallback graft point: $FallbackTag ($($MatchingCommit.Substring(0, [Math]::Min(12, $MatchingCommit.Length))))" -ForegroundColor Yellow
                Write-Host "  Your local initial commit did not match any upstream commit exactly."
                Write-Host "  This is safe but means your git history may show a small discontinuity"
                Write-Host "  at the graft point. update_daaf.ps1 will still work correctly."
            } else {
                # Last resort: use origin/main
                $MatchingCommit = Invoke-ContainerGit rev-parse origin/main
                $MatchType = "fallback (origin/main HEAD)"
                Write-Host ""
                Write-Host "  WARNING: No tags found. Using origin/main HEAD as graft point." -ForegroundColor Yellow
                Write-Host "  This is safe but means your git history may show a discontinuity."
            }
        }

        Write-Host ""

        if ([string]::IsNullOrWhiteSpace($MatchingCommit)) {
            Write-Host "ERROR: Could not determine a graft point." -ForegroundColor Red
            Write-Host "This is unexpected. Please report this issue at:"
            Write-Host "  https://github.com/$Repo/issues"
            Wait-ForUser; return
        }

        # --- Graft local history onto upstream ---
        Write-Host "Connecting local history to upstream ($MatchType)..."
        $null = Invoke-ContainerGitVerbose replace --graft $InitialCommit $MatchingCommit
        Write-Host "Graft complete."
        Write-Host ""

        # --- Verify the graft works ---
        Write-Host "Verifying graft..."
        $MergeBase = Invoke-ContainerGitVerbose merge-base HEAD origin/main
        if (-not [string]::IsNullOrWhiteSpace($MergeBase)) {
            Write-Host "  Verified: common ancestor found ($($MergeBase.Substring(0, [Math]::Min(12, $MergeBase.Length))))"
            Write-Host "  git merge and git pull will work correctly."
        } else {
            Write-Host ""
            Write-Host "  WARNING: Could not verify graft - no common ancestor found." -ForegroundColor Yellow
            Write-Host "  The graft was applied, but git merge may not work as expected."
            Write-Host "  This is unusual. You can re-run:  .\migrate_daaf.ps1"
            Write-Host "  If the problem persists, report it at:"
            Write-Host "    https://github.com/$Repo/issues"
        }
        Write-Host ""

        # --- Fix file permissions in the index ---
        Write-Host "Fixing file permissions (ZIP downloads don't preserve executable bits)..."

        # Get files that are 100755 upstream but 100644 locally
        $UpstreamExec = Invoke-ContainerShell "cd /daaf && git ls-tree -r '$MatchingCommit' | grep '^100755' | awk '{print `$4}' | sort"

        $PermFixed = 0
        if (-not [string]::IsNullOrWhiteSpace($UpstreamExec)) {
            $UpstreamExecFiles = $UpstreamExec -split "`n" | Where-Object { $_.Trim() -ne "" } | ForEach-Object { $_.Trim() }

            foreach ($FilePath in $UpstreamExecFiles) {
                if ([string]::IsNullOrWhiteSpace($FilePath)) { continue }

                # Check if the file exists locally and has wrong mode
                # Use git ls-files -s -- <filepath> (no sh -c wrapper)
                $LocalMode = Invoke-ContainerGit ls-files -s -- $FilePath
                if (-not [string]::IsNullOrWhiteSpace($LocalMode)) {
                    $ModeField = ($LocalMode -split '\s+')[0]
                    if ($ModeField -eq "100644") {
                        $null = Invoke-ContainerGit update-index --chmod=+x $FilePath
                        $PermFixed++
                    }
                }
            }
        }

        if ($PermFixed -gt 0) {
            Write-Host "  Fixed permissions on $PermFixed file(s)."
            Write-Host ""
            Write-Host "Committing permission fixes..."
            # Commit only the permission changes already staged by update-index
            # (do NOT use 'git add -A' which could sweep in unrelated changes)
            $null = Invoke-ContainerGitVerbose commit --allow-empty -m "Migration: normalize file permissions"
            Write-Host "Permission fixes committed."
        } else {
            Write-Host "  No permission fixes needed."
        }

        Write-Host ""
    }

    # --- Set upstream tracking ---
    Write-Host "Setting upstream tracking branch..."
    $null = Invoke-ContainerGit branch --set-upstream-to=origin/main main
    Write-Host "Tracking set: main -> origin/main"
    Write-Host ""

    Write-Host "Migration complete. Your local history is now connected to the"
    Write-Host "official DAAF timeline. Future updates will merge cleanly."
    Write-Host ""
}

# =====================================================================
# 7. OFFER UPDATE
# =====================================================================
Write-Host "-------------------------------------------"
Write-Host "  Run update?"
Write-Host "-------------------------------------------"
Write-Host ""
Write-Host "Your installation is now connected to the upstream repository."
Write-Host "Would you like to pull the latest updates now?"
Write-Host ""

if (-not $NonInteractive) {
    $UpdateChoice = Read-UserChoice "  Run update_daaf.ps1 now? [y/n]" @("y", "n")
} else {
    # Non-interactive (piped) - skip the update
    Write-Host "  (Non-interactive mode detected - skipping update. Run it manually.)"
    $UpdateChoice = "n"
}

if ($UpdateChoice -eq "y") {
    Write-Host ""
    $OriginalDirUpdate = (Get-Location).Path
    Set-Location $HostDir
    $env:DAAF_NESTED = "1"
    & .\update_daaf.ps1
    Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
    Set-Location $OriginalDirUpdate
}

# =====================================================================
# 8. SUCCESS MESSAGE
# =====================================================================
Write-Host ""
Write-Host "=========================================="
Write-Host "  Migration complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Your DAAF installation has been migrated to support the new update"
Write-Host "infrastructure. Here is what was done:"
Write-Host ""
if ($DetectedEra -eq "1") {
    Write-Host "  - Downloaded host utility scripts to: $HostDir\"
    Write-Host "  - Created a full backup of your Docker volume"
    Write-Host "  - Fetched latest upstream history into your existing repo"
} else {
    Write-Host "  - Downloaded host utility scripts to: $HostDir\"
    Write-Host "  - Created a full backup of your Docker volume"
    Write-Host "  - Added remote origin pointing to the official DAAF repository"
    Write-Host "  - Connected your local git history to the official DAAF timeline"
    Write-Host "  - Fixed file permissions to match upstream"
    Write-Host "  - Set upstream tracking (main -> origin/main)"
}
Write-Host ""
if ($UpdateChoice -eq "n" -and (-not $NonInteractive)) {
    # User chose not to update
    Write-Host "To pull the latest updates when you're ready:"
} elseif ($NonInteractive) {
    # Non-interactive mode (irm pipe) - update was skipped automatically
    Write-Host "IMPORTANT: The update step was skipped because the script was run"
    Write-Host "non-interactively. To pull the latest updates, run:"
} else {
    Write-Host "Going forward, you can update DAAF with:"
}
Write-Host "  cd $HostDir"
Write-Host "  .\update_daaf.ps1"
Write-Host ""
Write-Host "Other available scripts:"
Write-Host "  .\run_daaf.ps1        Launch Claude Code"
Write-Host "  .\backup_daaf.ps1     Back up the Docker volume"
Write-Host "  .\rebuild_daaf.ps1    Rebuild the Docker image"
Write-Host "  .\view_logs.ps1       Browse session logs"
Write-Host ""

if ($Mutex) { try { $Mutex.ReleaseMutex() } catch { <# Mutex already released or not owned — safe to ignore #> Write-Verbose "Silenced: $_" } }
Wait-ForUser
