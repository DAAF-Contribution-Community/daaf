# ============================================================================
# DAAF Rebuild Utility (Windows PowerShell)
# ============================================================================
# Copies the current Dockerfile and docker-compose.yml from the container
# back to the host build directory, then rebuilds the Docker image.
#
# Use this after:
#   - Adding Python packages via DAAF's Framework Development mode
#   - Running update_daaf.ps1 when it reports Dockerfile or docker-compose.yml changes
#   - Any other change to build files inside the container
#
# Why this is needed:
#   The Dockerfile and docker-compose.yml live in two places - inside the Docker
#   volume (where DAAF and update_daaf.ps1 modify them) and on the host (where docker
#   compose reads them for builds). This script bridges the gap so you don't
#   have to remember the manual docker cp commands.
#
# Usage:
#   cd daaf-docker
#   .\rebuild_daaf.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

function Pause-And-Exit {
    param([int]$Code = 0)
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to close this window"
    }
    exit $Code
}

$ContainerName = "daaf-daaf-docker-1"

Write-Host ""
Write-Host "=========================================="
Write-Host "  DAAF Rebuild"
Write-Host "=========================================="
Write-Host ""

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

$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    Pause-And-Exit 1
}

# --- Check container exists (running or stopped) ---
$null = docker inspect $ContainerName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Container '$ContainerName' not found." -ForegroundColor Red
    Write-Host "Have you run the DAAF installer? The container must exist (running or stopped)"
    Write-Host "for this script to copy the updated files from it."
    Pause-And-Exit 1
}

# --- Copy build files from container to host ---
Write-Host "[1/3] Copying build files from container to host..."

# Back up current host files so we can show what changed
$DockerfileChanged = $false
$ComposefileChanged = $false

if (Test-Path "Dockerfile") {
    Copy-Item "Dockerfile" "Dockerfile.pre-rebuild" -Force
}
if (Test-Path "docker-compose.yml") {
    Copy-Item "docker-compose.yml" "docker-compose.yml.pre-rebuild" -Force
}

docker cp "${ContainerName}:/daaf/Dockerfile" ./Dockerfile
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to copy Dockerfile from container." -ForegroundColor Red
    Write-Host "Make sure DAAF is installed in the container (run the installer if needed)."
    Pause-And-Exit 1
}
Write-Host "      Copied Dockerfile"

docker cp "${ContainerName}:/daaf/docker-compose.yml" ./docker-compose.yml
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to copy docker-compose.yml from container." -ForegroundColor Red
    Pause-And-Exit 1
}
Write-Host "      Copied docker-compose.yml"

# --- Show what changed ---
Write-Host ""
if (Test-Path "Dockerfile.pre-rebuild") {
    $OldHash = (Get-FileHash "Dockerfile.pre-rebuild").Hash
    $NewHash = (Get-FileHash "Dockerfile").Hash
    if ($OldHash -eq $NewHash) {
        Write-Host "      Dockerfile: no changes detected"
    } else {
        $DockerfileChanged = $true
        Write-Host "      Dockerfile: UPDATED"
    }
} else {
    $DockerfileChanged = $true
    Write-Host "      Dockerfile: new (no previous version on host)"
}

if (Test-Path "docker-compose.yml.pre-rebuild") {
    $OldHash = (Get-FileHash "docker-compose.yml.pre-rebuild").Hash
    $NewHash = (Get-FileHash "docker-compose.yml").Hash
    if ($OldHash -eq $NewHash) {
        Write-Host "      docker-compose.yml: no changes detected"
    } else {
        $ComposefileChanged = $true
        Write-Host "      docker-compose.yml: UPDATED"
    }
} else {
    $ComposefileChanged = $true
    Write-Host "      docker-compose.yml: new (no previous version on host)"
}

if ((-not $DockerfileChanged) -and (-not $ComposefileChanged)) {
    Write-Host ""
    Write-Host "      No changes detected - the host files already match the container."
    Write-Host "      Rebuilding anyway to make sure the image is up to date."
}

# --- Rebuild ---
Write-Host ""
Write-Host "[2/3] Rebuilding Docker image (this may take a few minutes if packages changed)..."
Write-Host ""
# Build and start are split into two commands so that --progress plain can be
# applied to the build step (where it is universally supported) without relying
# on `docker compose up --progress`, which is rejected as "unknown flag" on
# Docker Compose versions prior to ~v2.27.
docker compose build --progress plain
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Rebuild failed. Check the output above for details." -ForegroundColor Red
    if (Test-Path "Dockerfile.pre-rebuild") {
        Write-Host "Your previous Dockerfile was saved as Dockerfile.pre-rebuild"
    }
    Pause-And-Exit 1
}
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to start the container after rebuild. Check the output above for details." -ForegroundColor Red
    Pause-And-Exit 1
}

# --- Wait for container to be ready ---
Write-Host ""
Write-Host "      Waiting for container to be ready..."
$retries = 0
$maxRetries = 30
while ($retries -lt $maxRetries) {
    docker compose exec -T daaf-docker true 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    $retries++
    Start-Sleep -Seconds 2
}
if ($retries -ge $maxRetries) {
    Write-Host "ERROR: Container did not become ready within 60 seconds." -ForegroundColor Red
    Write-Host "Check Docker Desktop for errors."
    Pause-And-Exit 1
}

# --- Verify ---
Write-Host ""
Write-Host "[3/3] Verifying DAAF installation..."
docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "WARNING: Rebuild completed but DAAF files may not be intact." -ForegroundColor Yellow
    Write-Host "Try entering the container with: .\run_daaf.ps1 bash"
    Pause-And-Exit 1
}

Write-Host "      DAAF verified."

# Clean up pre-rebuild backups on success
if (Test-Path "Dockerfile.pre-rebuild") { Remove-Item "Dockerfile.pre-rebuild" -Force }
if (Test-Path "docker-compose.yml.pre-rebuild") { Remove-Item "docker-compose.yml.pre-rebuild" -Force }

Write-Host ""
Write-Host "=========================================="
Write-Host "  Rebuild complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "The Docker image has been rebuilt with the latest Dockerfile."
Write-Host "To launch DAAF:  .\run_daaf.ps1"
Write-Host ""
Pause-And-Exit 0
