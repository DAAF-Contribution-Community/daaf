# ============================================================================
# DAAF Log Explorer (Windows PowerShell)
# ============================================================================
# Opens the interactive session log viewer in your browser.
# Starts the DAAF container if needed, generates the session manifest,
# and starts an HTTP server.
#
# Usage:
#   cd daaf-docker
#   .\view_logs.ps1
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Port 2719 mapped in docker-compose.yml
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

# --- Preflight ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host "Please run this script from your daaf-docker folder."
    Pause-And-Exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Pause-And-Exit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running. Please start it and try again." -ForegroundColor Red
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
        Write-Host "ERROR: Failed to start the container." -ForegroundColor Red
        Pause-And-Exit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is running."
}

Write-Host ""
Write-Host "Opening DAAF Log Explorer..."
Write-Host ""
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to generate log viewer." -ForegroundColor Red
    Write-Host "  The container may not be running, or there may be no session logs to display." -ForegroundColor Red
    Write-Host "  Try: docker compose logs daaf-docker" -ForegroundColor Yellow
}

# If the server was already running, the command above returns immediately
# after printing the URL. Pause-And-Exit keeps the window open so the user
# can read/copy it.
Pause-And-Exit 0
