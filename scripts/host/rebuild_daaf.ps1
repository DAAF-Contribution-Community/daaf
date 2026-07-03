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
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

$ErrorActionPreference = "Stop"

function Wait-AndExit {
    param([int]$Code = 0)
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to close this window"
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
            "*compose ps -aq daaf-docker*" { Write-Output "abc123" }
            "*inspect*" { return }
            "*cp *" { return }
            "*compose build*" { return }
            "*compose up*" { return }
            "*compose exec*true*" { return }
            "*compose exec*test -f*" { return }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/rebuild_daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  DAAF Rebuild"
Write-Host "=========================================="
Write-Host ""

# --- Preflight ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host "Please run this script from your daaf-docker folder."
    Wait-AndExit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from PowerShell." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Wait-AndExit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    Wait-AndExit 1
}

# --- Check container exists (running or stopped) ---
# Derive the container ID from the compose project rather than a hardcoded name.
# `-aq` includes STOPPED containers: rebuild must be able to copy build files out
# of a container that is not currently running (the documented use case), so the
# running-only `-q` form would be wrong here.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ContainerId = (docker compose ps -aq daaf-docker 2>$null | Out-String).Trim()
$ErrorActionPreference = $savedEAP
if ([string]::IsNullOrWhiteSpace($ContainerId)) {
    Write-Host "ERROR: No daaf-docker container found (running or stopped)." -ForegroundColor Red
    Write-Host "Have you run the DAAF installer? The container must exist (running or stopped)"
    Write-Host "for this script to copy the updated files from it."
    Wait-AndExit 1
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

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker cp "${ContainerId}:/daaf/Dockerfile" ./Dockerfile
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to copy Dockerfile from container." -ForegroundColor Red
    Write-Host "Make sure DAAF is installed in the container (run the installer if needed)."
    Wait-AndExit 1
}
Write-Host "      Copied Dockerfile"

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker cp "${ContainerId}:/daaf/docker-compose.yml" ./docker-compose.yml
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to copy docker-compose.yml from container." -ForegroundColor Red
    Wait-AndExit 1
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
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose build --progress plain
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Rebuild failed. Check the output above for details." -ForegroundColor Red
    if (Test-Path "Dockerfile.pre-rebuild") {
        Write-Host "Your previous Dockerfile was saved as Dockerfile.pre-rebuild"
    }
    Wait-AndExit 1
}
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose up -d
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to start the container after rebuild. Check the output above for details." -ForegroundColor Red
    Wait-AndExit 1
}

# --- Wait for container to be ready ---
Write-Host ""
Write-Host "      Waiting for container to be ready..."
$retries = 0
$maxRetries = 30
$readyLog = [System.IO.Path]::GetTempFileName()
while ($retries -lt $maxRetries) {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose exec -T daaf-docker true 2>> $readyLog
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
    Write-Host "Check Docker Desktop for errors."
    Remove-Item $readyLog -ErrorAction SilentlyContinue
    Wait-AndExit 1
}
Remove-Item $readyLog -ErrorAction SilentlyContinue

# --- Verify ---
Write-Host ""
Write-Host "[3/3] Verifying DAAF installation..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md 2>&1 | Out-Null
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "WARNING: Rebuild completed but DAAF files may not be intact." -ForegroundColor Yellow
    Write-Host "Try entering the container with: .\run_daaf.ps1 bash"
    Wait-AndExit 1
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
Wait-AndExit 0
