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
# pwsh 7.4+ only (an ordinary, unused variable on Windows PowerShell 5.1): never turn a
# native command's nonzero exit into an error record or a throw. The native calls here
# read $LASTEXITCODE themselves (same line as backup_daaf.ps1 and restore_from_backup.ps1).
# With this set to $true under 'Stop', pwsh throws NativeCommandExitException (observed
# 2026-11-01, PowerShell 7.6.3).
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
# Bridge environment_settings.txt's seven whitelisted DAAF_* keys ($known below)
# into the process environment so `docker compose` interpolation resolves the project name
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

# --- Project name for printed commands ---
# Parity twin of the block in run_daaf.sh (see there for why): printed commands
# carry `-p <project>` and DAAF_PROJECT_NAME for any project other than 'daaf',
# normalized as Docker Compose does (Resolve-DaafProjectName in daaf_lib.ps1).
# SYNC NOTE: the $HintProject line is a copy of the library's expression;
# tests/powershell/daaf_lib.Tests.ps1 runs it over the library's fixed input set.
# The printed reinstall also carries DAAF_BRANCH (when set and not main) and
# DAAF_DEV=1 (when set), as in run_daaf.sh (see there for why).
$HintProject = if ([string]::IsNullOrEmpty($env:DAAF_PROJECT_NAME)) { "daaf" } else { ($env:DAAF_PROJECT_NAME -creplace '[^A-Za-z0-9_-]', '').ToLowerInvariant().TrimStart('_', '-') }
$ComposePFlag = ""
$RerunEnvPart = ""
if (-not [string]::IsNullOrEmpty($HintProject) -and $HintProject -cne "daaf") {
    $ComposePFlag = "-p $HintProject "
    $RerunEnvPart = "`$env:DAAF_PROJECT_NAME = `"$HintProject`"; "
}
if (-not [string]::IsNullOrEmpty($env:DAAF_BRANCH) -and $env:DAAF_BRANCH -cne "main") {
    $RerunEnvPart += "`$env:DAAF_BRANCH = `"$($env:DAAF_BRANCH)`"; "
}
if ($env:DAAF_DEV -eq "1") {
    $RerunEnvPart += "`$env:DAAF_DEV = `"1`"; "
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
        Write-Host "ERROR: Failed to start the container. Check Docker Desktop for errors." -ForegroundColor Red
        Wait-AndExit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is already running."
    # Check if environment_settings.txt has been modified since the container was created
    if (Test-Path "environment_settings.txt") {
        # Stdout only (2>$null), as above: the ID is passed to `docker inspect`, and
        # the inspect output is parsed as a date, so a stderr line in either would
        # only break them.
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $_cid = docker compose ps -q daaf-docker 2>$null
        $ErrorActionPreference = $savedEAP
        if ($_cid) {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $_created = docker inspect --format '{{.Created}}' $_cid 2>$null
            $ErrorActionPreference = $savedEAP
            try {
                # Truncate to 7 fractional digits -- .NET DateTimeOffset.Parse() rejects Docker's 9-digit nanoseconds
                $_created = $_created -replace '(\.\d{7})\d+', '$1'
                $ContainerStart = [DateTimeOffset]::Parse($_created).UtcDateTime
                $EnvModified = (Get-Item "environment_settings.txt").LastWriteTimeUtc
                if ($EnvModified -gt $ContainerStart) {
                    Write-Host ""
                    Write-Host "NOTE: Your environment_settings.txt file has been modified since this container was started." -ForegroundColor Yellow
                    Write-Host "      To apply environment_settings.txt changes, close all DAAF sessions, then choose"
                    Write-Host "      11) Restart Container in the DAAF Control Panel (.\daaf.ps1), which does this for you."
                    Write-Host "      Or run these commands yourself:"
                    Write-Host "        docker compose $($ComposePFlag)down"
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
    Write-Host "WARNING: DAAF does not appear to be installed in the container (/daaf/CLAUDE.md is missing)," -ForegroundColor Yellow
    Write-Host "so Claude Code cannot start with DAAF. The updater cannot repair this; reinstalling can."
    Write-Host "A reinstall replaces DAAF's framework files and local git history, and keeps your"
    Write-Host "research files and environment_settings.txt (a backup first is still a good idea:"
    Write-Host "Control Panel option 7) Create Backup). To reinstall, run:"
    Write-Host "  cd `"$(Split-Path -Parent (Get-Location).Path)`""
    Write-Host "  $($RerunEnvPart)`$env:DAAF_FORCE_REINSTALL = `"1`""
    Write-Host "  irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.ps1 | iex"
    Wait-AndExit 1
}

# --- Launch ---
if ($Command -eq "claude") {
    Write-Host "Launching Claude Code..."
    Write-Host "(Type /exit to leave Claude Code when you are done.)"
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
