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

# --- Preflight ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host "Please run this script from your daaf-docker folder."
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
}

$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running. Please start it and try again." -ForegroundColor Red
    exit 1
}

# --- Start container if not running ---
$RunningOutput = docker compose ps --status running --format '{{.Name}}' 2>&1
$Running = ($RunningOutput | Select-String "daaf-docker").Count

if ($Running -eq 0) {
    Write-Host "Starting DAAF container..."
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start the container." -ForegroundColor Red
        exit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is running."
}

Write-Host ""
Write-Host "Opening DAAF Log Explorer..."
Write-Host ""
docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive

# If the server was already running, the command above returns immediately
# after printing the URL. Keep the window open so the user can read/copy it.
Write-Host ""
Read-Host "Press Enter to close this window"
