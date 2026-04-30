# ============================================================================
# DAAF One-Line Installer (Windows PowerShell)
# ============================================================================
# Usage:
#   irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.ps1 | iex
#
# What this script does:
#   1. Creates a minimal build directory (~5 KB)
#   2. Downloads the Dockerfile, docker-compose.yml, and convenience scripts
#   3. Builds the Docker image (Python, data science stack, Claude Code)
#   4. Clones the full DAAF repository into the Docker volume
#   5. Prints instructions for first launch
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

$ErrorActionPreference = "Stop"

function Wait-ForUser {
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to close this window"
    }
    exit
}

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, Invoke-WebRequest)
# for CI cross-platform smoke testing without a Docker daemon.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*volume inspect*" {
                # Simulate volume-not-found for fresh install path
                $global:LASTEXITCODE = 1
                return
            }
            "*compose*build*" { return }
            "*compose*up*" { return }
            "*compose*exec*true*" { return }
            "*compose*exec*git clone*" { return }
            "*compose*exec*bash -c*" { return }
            "*compose*exec*test -f*" { return }
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
            # Create parent directory if needed, then an empty file
            $parentDir = Split-Path $OutFile -Parent
            if ($parentDir -and -not (Test-Path $parentDir)) {
                New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
            }
            Set-Content -Path $OutFile -Value ""
        }
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/install.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Ensure TLS 1.2 for GitHub downloads (required on PowerShell 5.1)
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

# --- Configuration ---
$Repo = "DAAF-Contribution-Community/daaf"
$Branch = if ($env:DAAF_BRANCH) { $env:DAAF_BRANCH } else { "main" }
$RawBase = "https://raw.githubusercontent.com/$Repo/$Branch"
$InstallDir = Join-Path (Get-Location).Path "daaf-docker"

Write-Host ""
Write-Host "=========================================="
Write-Host "  DAAF Installer"
Write-Host "=========================================="
Write-Host ""
Write-Host "Branch: $Branch"
Write-Host ""

# --- Preflight checks ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Powershell." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Wait-ForUser; return
}

# Check Docker daemon is running (compatible with PowerShell 5.1 and 7+)
# Save/restore ErrorActionPreference around native commands to prevent PS 5.1
# from promoting stderr output to a terminating error when $ErrorActionPreference
# is "Stop".
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start Docker Desktop on your computer and try again." -ForegroundColor Red
    Wait-ForUser; return
}

# --- Check for existing installation ---
if (Test-Path "$InstallDir\docker-compose.yml") {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker volume inspect daaf_daaf-data 2>&1 | Out-Null
    $ErrorActionPreference = $savedEAP
    $volumeExists = ($LASTEXITCODE -eq 0)
    if ($volumeExists) {
        # Volume exists -- this is a completed or substantially completed installation
        if ($env:DAAF_FORCE_REINSTALL -eq "1") {
            Write-Host "NOTE: Existing installation detected. Proceeding with re-install (DAAF_FORCE_REINSTALL=1)."
            Write-Host ""
        } else {
            Write-Host "WARNING: An existing DAAF installation was detected." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Re-running the installer will overwrite framework files (CLAUDE.md, skills,"
            Write-Host "agents, templates) and local git history. Your research data will NOT be"
            Write-Host "deleted, but a backup is strongly recommended."
            Write-Host ""
            Write-Host "To update DAAF instead (recommended - preserves local changes):"
            Write-Host "  cd $InstallDir"
            Write-Host "  .\update_daaf.ps1"
            Write-Host ""
            Write-Host "To force a fresh re-install:"
            Write-Host '  $env:DAAF_FORCE_REINSTALL = "1"'
            Write-Host "  irm $RawBase/scripts/host/install.ps1 | iex"
            Write-Host ""
            Wait-ForUser; return
        }
    } else {
        Write-Host "NOTE: A previous install attempt was detected but appears incomplete."
        Write-Host "      Proceeding with a fresh install."
        Write-Host ""
    }
}

# --- Create minimal build directory ---
Write-Host "[1/4] Creating an initial directory for installation files at $InstallDir ..."
New-Item -ItemType Directory -Path "$InstallDir" -Force | Out-Null

# --- Download build-context and utility files ---
Write-Host "[2/4] Downloading installation files ..."
try {
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/Dockerfile"                          -OutFile "$InstallDir\Dockerfile"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/docker-compose.yml"                   -OutFile "$InstallDir\docker-compose.yml"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/run_daaf.ps1"             -OutFile "$InstallDir\run_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/backup_daaf.ps1"          -OutFile "$InstallDir\backup_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/restore_from_backup.ps1"  -OutFile "$InstallDir\restore_from_backup.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/rebuild_daaf.ps1"         -OutFile "$InstallDir\rebuild_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/update_daaf.ps1"          -OutFile "$InstallDir\update_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/view_logs.ps1"            -OutFile "$InstallDir\view_logs.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/view_notebooks.ps1"      -OutFile "$InstallDir\view_notebooks.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/environment_settings_example.txt" -OutFile "$InstallDir\environment_settings_example.txt"
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to download installation files from branch '$Branch'." -ForegroundColor Red
    Write-Host "Please verify that the branch name is correct and that you have an internet connection."
    Write-Host "You can check available branches at: https://github.com/$Repo/branches"
    Write-Host "Details: $_"
    Wait-ForUser; return
}

# --- Build the Docker image ---
Write-Host "[3/4] Building Docker image (this may take a few minutes on first run since there are a lot of Python libraries to install)..."
# Project name is set declaratively via the top-level "name: daaf" key in
# docker-compose.yml -- no need to set COMPOSE_PROJECT_NAME here.
# Build and start are split into two commands so that --progress plain can be
# applied to the build step (where it is universally supported) without relying
# on `docker compose up --progress`, which is rejected as "unknown flag" on
# Docker Compose versions prior to ~v2.27.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose -f "$InstallDir\docker-compose.yml" build --progress plain
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker image build failed. Check the output above for details." -ForegroundColor Red
    Write-Host "You can safely re-run this installer to retry (set DAAF_FORCE_REINSTALL=1 if prompted)."
    Wait-ForUser; return
}
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose -f "$InstallDir\docker-compose.yml" up -d
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start the Docker container after build. Check the output above for details." -ForegroundColor Red
    Write-Host "You can safely re-run this installer to retry (set DAAF_FORCE_REINSTALL=1 if prompted)."
    Wait-ForUser; return
}

# --- Wait for container to be ready ---
Write-Host "      Waiting for container to be ready ..."
$retries = 0
$maxRetries = 30
$readyLog = [System.IO.Path]::GetTempFileName()
while ($retries -lt $maxRetries) {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose -f "$InstallDir\docker-compose.yml" exec -T daaf-docker true 2>> $readyLog
    $ErrorActionPreference = $savedEAP
    if ($LASTEXITCODE -eq 0) { break }
    $retries++
    Start-Sleep -Seconds 2
}
if ($retries -ge $maxRetries) {
    Write-Host "ERROR: Container did not become ready within 60 seconds." -ForegroundColor Red
    if ((Test-Path $readyLog) -and (Get-Item $readyLog).Length -gt 0) {
        Write-Host "  Docker reported:" -ForegroundColor Red
        Get-Content $readyLog -Tail 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Write-Host ""
    }
    Write-Host "Check Docker Desktop for errors, then retry with:"
    Write-Host "  docker compose -f $InstallDir\docker-compose.yml up -d"
    Remove-Item $readyLog -ErrorAction SilentlyContinue
    Wait-ForUser; return
}
Remove-Item $readyLog -ErrorAction SilentlyContinue

# --- Clone the full repository into the Docker volume ---
Write-Host "[4/4] Cloning DAAF repository files into the Docker container ..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose -f "$InstallDir\docker-compose.yml" exec -T daaf-docker `
    git clone --depth 1 -b "$Branch" "https://github.com/$Repo.git" /tmp/daaf-clone
$ErrorActionPreference = $savedEAP

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to clone the DAAF repository." -ForegroundColor Red
    Write-Host "The Docker image was built successfully, but the repository could not be downloaded."
    Write-Host "Check your internet connection and retry with:"
    Write-Host "  docker compose -f $InstallDir\docker-compose.yml exec -T daaf-docker ``"
    Write-Host "    git clone --depth 1 -b $Branch https://github.com/$Repo.git /tmp/daaf-clone"
    Write-Host "  docker compose -f $InstallDir\docker-compose.yml exec -T daaf-docker ``"
    Write-Host "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    Write-Host "You can also safely re-run this installer to retry from scratch (set DAAF_FORCE_REINSTALL=1 if prompted)."
    Wait-ForUser; return
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose -f "$InstallDir\docker-compose.yml" exec -T daaf-docker `
    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to copy repository files into the container." -ForegroundColor Red
    Write-Host "The clone succeeded, but copying to /daaf/ failed (possibly a permissions issue)."
    Write-Host "You can retry manually with:"
    Write-Host "  docker compose -f $InstallDir\docker-compose.yml exec -T daaf-docker ``"
    Write-Host "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    Write-Host "You can also safely re-run this installer to retry from scratch (set DAAF_FORCE_REINSTALL=1 if prompted)."
    Wait-ForUser; return
}

# --- Verify DAAF files are present ---
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose -f "$InstallDir\docker-compose.yml" exec -T daaf-docker test -f /daaf/CLAUDE.md 2>&1 | Out-Null
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "WARNING: Installation may be incomplete -- /daaf/CLAUDE.md was not found in the container." -ForegroundColor Yellow
    Write-Host "The Docker image was built, but the repository files may not have copied correctly."
    Write-Host "You can try cloning manually inside the container:"
    Write-Host "  cd $InstallDir"
    Write-Host "  docker compose exec daaf-docker bash"
    Write-Host "  git clone --depth 1 -b $Branch https://github.com/$Repo.git /tmp/daaf-clone"
    Write-Host "  cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone"
    Wait-ForUser; return
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  Installation complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "To start using DAAF:"
Write-Host ""
Write-Host "  1. Navigate to the install directory and launch Claude Code:"
Write-Host "     cd $InstallDir"
Write-Host "     .\run_daaf.ps1"
Write-Host ""
Write-Host "     This starts the container (if needed) and launches Claude Code directly."
Write-Host ""
Write-Host "  2. On first launch, you'll be asked to authenticate with your Anthropic account."
Write-Host ""
Write-Host "  3. Configure Claude Code (required):"
Write-Host "     - Type /config and set:"
Write-Host "         Auto-compact  -> False"
Write-Host "         Verbose output -> True"
Write-Host "     - Press ESC to return to the chat"
Write-Host ""
Write-Host "Convenience scripts (in $InstallDir):"
Write-Host "  .\run_daaf.ps1                 Launch Claude Code (starts container if needed)"
Write-Host "  .\run_daaf.ps1 bash            Enter the container shell"
Write-Host "  .\backup_daaf.ps1              Back up the Docker volume to a dated folder"
Write-Host "  .\restore_from_backup.ps1      Restore from a backup"
Write-Host "  .\update_daaf.ps1              Check for and apply DAAF updates"
Write-Host "  .\rebuild_daaf.ps1             Copy build files from container and rebuild image"
Write-Host "  .\view_logs.ps1                Browse session logs in your browser"
Write-Host "  .\view_notebooks.ps1           Browse and edit marimo notebooks in your browser"
Write-Host ""
Write-Host "To set up data source API keys (optional):"
Write-Host "  Copy-Item environment_settings_example.txt environment_settings.txt   Copy the template"
Write-Host "  Edit environment_settings.txt with your keys, then restart with: .\run_daaf.ps1"
Write-Host ""
Write-Host "Manual alternative (if you prefer individual commands):"
Write-Host "  docker compose exec daaf-docker bash   # enter the container"
Write-Host "  claude                                  # launch Claude Code"
Write-Host ""
Write-Host "For day-to-day usage and more, see:"
Write-Host "  https://github.com/$Repo/blob/$Branch/user_reference/01_installation_and_quickstart.md"
Write-Host ""
Write-Host "Keep this directory - it contains the Dockerfile needed for rebuilds."
Write-Host ""
Write-Host "To get started using any of those scripts, enter the install directory first:"
Write-Host "  cd daaf-docker"
Write-Host ""

Wait-ForUser
