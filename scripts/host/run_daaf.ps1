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
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

#Requires -Version 5.1
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
            "*compose ps*--format*" { Write-Output "daaf-docker" }
            "*compose up*" { return }
            "*compose exec*" { return }
            "*inspect*--format*" { Write-Output "2026-01-01T00:00:00.0000000Z" }
            "*compose ps -q*" { Write-Output "abc123" }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/run_daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Enable strict mode for real executions only. Set-StrictMode is dynamically
# scoped, so placing it AFTER the DAAF_TEST_MODE guard keeps Pester's dot-sourcing
# (which returns above) from leaking strict mode into the whole test session, while
# every code path a real run reaches -- including library functions called below --
# runs fully protected against uninitialized-variable and missing-property reads.
Set-StrictMode -Version 3.0

$Command = if ($args.Count -gt 0) { $args[0] } else { "claude" }

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
        Write-Host "ERROR: Failed to start the container. Check Docker Desktop for errors." -ForegroundColor Red
        Wait-AndExit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is already running."
    # Check if environment_settings.txt has been modified since the container was created
    if (Test-Path "environment_settings.txt") {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $_cid = docker compose ps -q daaf-docker 2>&1
        $ErrorActionPreference = $savedEAP
        if ($_cid) {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $_created = docker inspect --format '{{.Created}}' $_cid 2>&1
            $ErrorActionPreference = $savedEAP
            try {
                # Truncate to 7 fractional digits -- .NET DateTimeOffset.Parse() rejects Docker's 9-digit nanoseconds
                $_created = $_created -replace '(\.\d{7})\d+', '$1'
                $ContainerStart = [DateTimeOffset]::Parse($_created).UtcDateTime
                $EnvModified = (Get-Item "environment_settings.txt").LastWriteTimeUtc
                if ($EnvModified -gt $ContainerStart) {
                    Write-Host ""
                    Write-Host "NOTE: Your environment_settings.txt file has been modified since this container was started." -ForegroundColor Yellow
                    Write-Host "      To apply environment_settings.txt changes, close all DAAF sessions, then run:"
                    Write-Host "        docker compose down"
                    Write-Host "        .\run_daaf.ps1"
                }
            } catch {
                # Date-parsing edge cases (e.g., Docker nanosecond format) are
                # non-critical -- the environment_settings.txt freshness hint is best-effort only.
                Write-Verbose "Silenced: $_"
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
    Wait-AndExit 1
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

Wait-AndExit 0
