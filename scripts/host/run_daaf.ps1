# ============================================================================
# DAAF Launcher (Windows PowerShell)
# ============================================================================
# Starts the DAAF container (if needed) and launches Claude Code.
#
# Usage:
#   cd daaf-docker
#   .\run_daaf.ps1            # Start container + launch Claude Code
#   .\run_daaf.ps1 bash       # Start container + drop into bash shell
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# ============================================================================

$ErrorActionPreference = "Stop"

function Pause-And-Exit {
    param([int]$Code = 0)
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    exit $Code
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/run_daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

$Command = if ($args.Count -gt 0) { $args[0] } else { "claude" }

# --- Preflight ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host "Please run this script from your daaf-docker folder."
    Pause-And-Exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from PowerShell." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Pause-And-Exit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    Pause-And-Exit 1
}

# --- Start container if not running ---
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$RunningOutput = docker compose ps --status running --format '{{.Name}}' 2>&1
$ErrorActionPreference = $savedEAP
$Running = ($RunningOutput | Select-String "daaf-docker").Count

if ($Running -eq 0) {
    Write-Host "Starting DAAF container..."
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose up -d
    $ErrorActionPreference = $savedEAP
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start the container. Check Docker Desktop for errors." -ForegroundColor Red
        Pause-And-Exit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is already running."
    # Check if .env has been modified since the container was created
    if (Test-Path ".env") {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $_cid = docker compose ps -q daaf-docker 2>&1
        $ErrorActionPreference = $savedEAP
        if ($_cid) {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $_created = docker inspect --format '{{.Created}}' $_cid 2>&1
            $ErrorActionPreference = $savedEAP
            try {
                # Truncate to 7 fractional digits — .NET DateTimeOffset.Parse() rejects Docker's 9-digit nanoseconds
                $_created = $_created -replace '(\.\d{7})\d+', '$1'
                $ContainerStart = [DateTimeOffset]::Parse($_created).UtcDateTime
                $EnvModified = (Get-Item ".env").LastWriteTimeUtc
                if ($EnvModified -gt $ContainerStart) {
                    Write-Host ""
                    Write-Host "NOTE: Your .env file has been modified since this container was started." -ForegroundColor Yellow
                    Write-Host "      To apply .env changes, close all DAAF sessions, then run:"
                    Write-Host "        docker compose down"
                    Write-Host "        .\run_daaf.ps1"
                }
            } catch {
                # Silently skip if date comparison fails
            }
        }
    }
}

Write-Host ""

# --- Verify DAAF is installed in the container ---
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md 2>&1 | Out-Null
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: DAAF does not appear to be installed in the container (/daaf is empty or missing key files)." -ForegroundColor Yellow
    Write-Host "The container is running, but DAAF's repository files may not have been cloned."
    Write-Host "You can fix this by running '.\update_daaf.ps1' from your daaf-docker folder, or manually cloning inside the container:"
    Write-Host "  docker compose exec daaf-docker bash"
    Write-Host "  git clone --depth 1 https://github.com/DAAF-Contribution-Community/daaf.git /tmp/daaf-clone"
    Write-Host "  cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone"
    Pause-And-Exit 1
}

# --- Launch ---
if ($Command -eq "claude") {
    Write-Host "Launching Claude Code..."
    Write-Host "(Press Ctrl+C twice to exit Claude Code when done)"
    Write-Host ""
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose exec daaf-docker claude
    $ErrorActionPreference = $savedEAP
} elseif ($Command -eq "bash") {
    Write-Host "Entering container shell..."
    Write-Host "(Type 'exit' to leave the container)"
    Write-Host ""
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose exec daaf-docker bash
    $ErrorActionPreference = $savedEAP
} else {
    Write-Host "Running: $Command"
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose exec daaf-docker $Command
    $ErrorActionPreference = $savedEAP
}

Pause-And-Exit 0
