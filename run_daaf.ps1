# ============================================================================
# DAAF Launcher (Windows PowerShell)
# ============================================================================
# Starts the DAAF container (if needed) and launches Claude Code.
#
# Usage:
#   cd daaf-docker
#   .\run_daaf.ps1            # Start container + launch Claude Code
#   .\run_daaf.ps1 bash       # Start container + drop into bash shell
# ============================================================================

$ErrorActionPreference = "Stop"

$Command = if ($args.Count -gt 0) { $args[0] } else { "claude" }

# --- Preflight ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host "Please run this script from your daaf-docker folder."
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is not installed or not in your PATH." -ForegroundColor Red
    exit 1
}

$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    exit 1
}

# --- Start container if not running ---
$RunningOutput = docker compose ps --status running --format '{{.Name}}' 2>&1
$Running = ($RunningOutput | Select-String "daaf-docker").Count

if ($Running -eq 0) {
    Write-Host "Starting DAAF container..."
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start the container. Check Docker Desktop for errors." -ForegroundColor Red
        exit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is already running."
}

Write-Host ""

# --- Launch ---
if ($Command -eq "claude") {
    Write-Host "Launching Claude Code..."
    Write-Host "(Press Ctrl+C twice to exit Claude Code when done)"
    Write-Host ""
    docker compose exec daaf-docker claude
} elseif ($Command -eq "bash") {
    Write-Host "Entering container shell..."
    Write-Host "(Type 'exit' to leave the container)"
    Write-Host ""
    docker compose exec daaf-docker bash
} else {
    Write-Host "Running: $Command"
    docker compose exec daaf-docker $Command
}
