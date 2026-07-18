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

#Requires -Version 5.1
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
        # Match patterns are space/flag-anchored so they cannot collide with the
        # random InstallDir path embedded in $argStr. switch -Wildcard uses the
        # same `*` globbing as Bash `case`, so the same reasoning applies as in
        # install.sh: a temp-directory path fragment (no spaces, no hyphenated
        # flags, no long literals) can no longer route to the wrong arm. The
        # former *compose*build* / *compose*up* substring forms were functionally
        # immune here (every real arm returns via $LASTEXITCODE = 0), but are
        # hardened to the path-proof style used in install.sh and the .bats mocks
        # for cross-file parity and future-proofing.
        switch -Wildcard ($argStr) {
            "info" { return }
            "*volume inspect*" {
                # Simulate volume-not-found for fresh install path
                $global:LASTEXITCODE = 1
                return
            }
            "*buildx inspect*" {
                # Simulate builder-not-found so the create arm is exercised
                $global:LASTEXITCODE = 1
                return
            }
            "*buildx create*" {
                # Test hook: DAAF_DIAG_BUILD_TEST_CREATE_FAIL=1 simulates a
                # create failure so the fail-open path can be exercised in tests.
                if ($env:DAAF_DIAG_BUILD_TEST_CREATE_FAIL -eq "1") { $global:LASTEXITCODE = 1 }
                return
            }
            "* build --progress*" { return }
            "* up -d*" { return }
            "*exec -T daaf-docker true*" { return }
            "*git clone*" { return }
            "*bash -c*" { return }
            "*test -f /daaf/CLAUDE.md*" { return }
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
        # Dry-run is fully non-writing: acknowledge the parameters and succeed
        # WITHOUT creating any files or directories. The former mock wrote an
        # empty file for each -OutFile target, which (with $InstallDir under the
        # caller's CWD) leaked zero-byte stubs on disk. The New-Item site below
        # is gated so the full flow still walks end-to-end.
        $null = $UseBasicParsing, $Uri, $OutFile
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/install.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Enable strict mode AFTER the test-mode guard. Set-StrictMode is dynamically
# scoped, so placing it here keeps Pester's dot-sourcing (which returns above)
# from leaking strict mode into the whole test session, while real executions
# run fully protected from this point on.
Set-StrictMode -Version 3.0

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
# Derive the project-prefixed data volume name so multi-instance installs
# (DAAF_PROJECT_NAME set) are detected correctly. The value comes from the process
# environment first, else DAAF_PROJECT_NAME in the existing install's
# environment_settings.txt, else the "daaf" default (byte-for-byte identical to the
# former hardcoded "daaf_daaf-data"). Parse only that one key (never dot-source --
# the file holds API keys); process env wins; CR stripped; PS 5.1 safe.
$InstallProjectName = $env:DAAF_PROJECT_NAME
if ([string]::IsNullOrEmpty($InstallProjectName)) {
    $SettingsPath = Join-Path $InstallDir "environment_settings.txt"
    if (Test-Path -LiteralPath $SettingsPath) {
        # -Encoding UTF8: PS 5.1's bare Get-Content misreads BOM-less UTF-8 as ANSI
        # (cp1252), corrupting any non-ASCII value. The settings writer is BOM-less
        # UTF-8, so reads are pinned to match; no-op on PS 7 (UTF-8 by default).
        foreach ($rawLine in (Get-Content -LiteralPath $SettingsPath -Encoding UTF8)) {
            $line = $rawLine -replace "`r", ""
            if ($line -match '^\s*DAAF_PROJECT_NAME\s*=(.*)$') {
                $val = $Matches[1].Trim()
                if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
                    if ($val.Length -ge 2) { $val = $val.Substring(1, $val.Length - 2) }
                }
                $InstallProjectName = $val
                break
            }
        }
    }
}
if ([string]::IsNullOrEmpty($InstallProjectName)) { $InstallProjectName = "daaf" }
$DataVolumeName = "${InstallProjectName}_daaf-data"

# --- Bridge the DAAF_DEV build flag into the environment ---
# Unlike DAAF_PROJECT_NAME above (only needed locally to derive the volume name;
# the compose project name comes from the file's `name:` key), the build flag
# must be EXPORTED so `docker compose build` below sees it and forwards it as
# `--build-arg DAAF_DEV=${DAAF_DEV:-0}`. Parse only that one key from the
# just-downloaded environment_settings.txt (never dot-source -- the file holds
# API keys); process env wins; CR stripped; PS 5.1 safe. Absent file / absent
# key = the flag stays unset, so its build arg defaults to 0 (standard build).
if ([string]::IsNullOrEmpty($env:DAAF_DEV)) {
    $DevSettingsPath = Join-Path $InstallDir "environment_settings.txt"
    if (Test-Path -LiteralPath $DevSettingsPath) {
        # -Encoding UTF8: PS 5.1's bare Get-Content misreads BOM-less UTF-8 as ANSI
        # (cp1252), corrupting any non-ASCII value. The settings writer is BOM-less
        # UTF-8, so reads are pinned to match; no-op on PS 7 (UTF-8 by default).
        foreach ($rawLine in (Get-Content -LiteralPath $DevSettingsPath -Encoding UTF8)) {
            $line = $rawLine -replace "`r", ""
            if ($line -match '^\s*DAAF_DEV\s*=(.*)$') {
                $val = $Matches[1].Trim()
                if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
                    if ($val.Length -ge 2) { $val = $val.Substring(1, $val.Length - 2) }
                }
                $env:DAAF_DEV = $val
                break
            }
        }
    }
}

if (Test-Path "$InstallDir\docker-compose.yml") {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker volume inspect $DataVolumeName 2>&1 | Out-Null
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
if ($env:DAAF_DRY_RUN -eq "1") {
    Write-Host "[DRY-RUN] Would create install directory: $InstallDir"
} else {
    New-Item -ItemType Directory -Path "$InstallDir" -Force | Out-Null
}

# --- Download build-context and utility files ---
Write-Host "[2/4] Downloading installation files ..."
try {
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/Dockerfile"                          -OutFile "$InstallDir\Dockerfile"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/docker-compose.yml"                   -OutFile "$InstallDir\docker-compose.yml"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/daaf.ps1"                 -OutFile "$InstallDir\daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/daaf_lib.ps1"             -OutFile "$InstallDir\daaf_lib.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/run_daaf.ps1"             -OutFile "$InstallDir\run_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/backup_daaf.ps1"          -OutFile "$InstallDir\backup_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/restore_from_backup.ps1"  -OutFile "$InstallDir\restore_from_backup.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/rebuild_daaf.ps1"         -OutFile "$InstallDir\rebuild_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/update_daaf.ps1"          -OutFile "$InstallDir\update_daaf.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/view_logs.ps1"            -OutFile "$InstallDir\view_logs.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/view_notebooks.ps1"      -OutFile "$InstallDir\view_notebooks.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/view_quarto.ps1"          -OutFile "$InstallDir\view_quarto.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/run_vscode.ps1"           -OutFile "$InstallDir\run_vscode.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/environment_settings_example.txt" -OutFile "$InstallDir\environment_settings_example.txt"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/scripts/host/README.txt"                      -OutFile "$InstallDir\README.txt"
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to download installation files from branch '$Branch'." -ForegroundColor Red
    Write-Host "Please verify that the branch name is correct and that you have an internet connection."
    Write-Host "You can check available branches at: https://github.com/$Repo/branches"
    Write-Host "Details: $_"
    Wait-ForUser; return
}

# --- Apple Silicon / arm64 build-time notice ---
# On the Ubuntu noble base, arm64 gets P3M pre-built R binaries (same as x86_64),
# so Apple Silicon no longer compiles R packages from source. The first build is
# still a sizable one-time download, but there is no arm64-specific source-compile
# penalty. A brief heads-up keeps the quiet install phase from looking like a hang.
$DaafArch = $env:PROCESSOR_ARCHITECTURE
if ($DaafArch -eq "ARM64") {
    Write-Host ""
    Write-Host "NOTE: arm64 detected. The first build downloads a large stack of Python"
    Write-Host "      and R packages, so it takes a while with some quiet stretches -- this"
    Write-Host "      is normal, not a hang. arm64 now installs pre-built R binaries (no"
    Write-Host "      source compilation)."
    Write-Host ""
}

# --- Optional diagnostic builder (DAAF_DIAG_BUILD=1) ---
# BuildKit clips each step's log output (by size AND by rate), and Docker
# Desktop's DEFAULT builder does not let those limits be raised. The only
# mechanism is a custom docker-container builder with larger
# BUILDKIT_STEP_LOG_MAX_SIZE / _MAX_SPEED, selected via the BUILDX_BUILDER env
# var. That builder has real costs (separate build cache; the built image must be
# loaded back into the Docker image store), so it is opt-in only. Fail-open: any
# failure creating/inspecting it falls back to the default builder.
$UseDiagBuilder = $false
if ($env:DAAF_DIAG_BUILD -eq "1") {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker buildx inspect daaf-diag-builder 2>&1 | Out-Null
    $ErrorActionPreference = $savedEAP
    if ($LASTEXITCODE -eq 0) {
        $UseDiagBuilder = $true
        Write-Host "NOTE: Reusing existing diagnostic buildx builder 'daaf-diag-builder' (raised step-log limits)."
    } else {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        docker buildx create --name daaf-diag-builder --driver docker-container --driver-opt env.BUILDKIT_STEP_LOG_MAX_SIZE=16777216 --driver-opt env.BUILDKIT_STEP_LOG_MAX_SPEED=10485760 2>&1 | Out-Null
        $ErrorActionPreference = $savedEAP
        if ($LASTEXITCODE -eq 0) {
            $UseDiagBuilder = $true
            Write-Host "NOTE: Created diagnostic buildx builder 'daaf-diag-builder' (raised step-log limits)."
        } else {
            Write-Host "NOTE: DAAF_DIAG_BUILD=1 set, but the diagnostic buildx builder could not be"
            Write-Host "      created. Falling back to the default builder (build logs may be clipped)."
        }
    }
    if ($UseDiagBuilder) {
        Write-Host "      This build uses a separate build cache (slower first run); the image is"
        Write-Host "      loaded back into Docker when the build completes."
        Write-Host ""
    }
}

# --- Build the Docker image ---
Write-Host "[3/4] Building Docker image (this may take a few minutes on first run since there are a lot of Python libraries to install)..."
# Project name is set declaratively via the top-level "name: daaf" key in
# docker-compose.yml -- no need to set COMPOSE_PROJECT_NAME here.
# Build and start are split into two commands so that --progress plain can be
# applied to the build step (where it is universally supported) without relying
# on `docker compose up --progress`, which is rejected as "unknown flag" on
# Docker Compose versions prior to ~v2.27.
# BUILDX_BUILDER is set only when the diagnostic builder was selected above, then
# cleared right after the build so it does not leak into later docker calls.
if ($UseDiagBuilder) { $env:BUILDX_BUILDER = "daaf-diag-builder" }
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose -f "$InstallDir\docker-compose.yml" build --progress plain
$ErrorActionPreference = $savedEAP
if ($UseDiagBuilder) { $env:BUILDX_BUILDER = $null }
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker image build failed. Check the output above for details." -ForegroundColor Red
    Write-Host "You can safely re-run this installer to retry (set DAAF_FORCE_REINSTALL=1 if prompted)."
    Write-Host "If the output above contains a line like '[output clipped, log limit 2MiB reached]'"
    Write-Host "(the exact limit varies by Docker version), re-run with DAAF_DIAG_BUILD=1 for"
    Write-Host "unclipped build logs:"
    Write-Host '  $env:DAAF_DIAG_BUILD = "1"'
    Write-Host "  irm $RawBase/scripts/host/install.ps1 | iex"
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

# On reinstall, remove the existing .git directory first.  Git pack files are
# mode 444 (read-only by design) which prevents cp -a from overwriting them.
# The research/ folder is preserved -- only framework files are replaced.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose -f "$InstallDir\docker-compose.yml" exec -T daaf-docker `
    bash -c 'rm -rf /daaf/.git /daaf/.pre-commit-config.yaml /daaf/.gitignore /daaf/.claudeignore 2>/dev/null; true'
$ErrorActionPreference = $savedEAP

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

# --- Settings-File Key Upsert (inlined from daaf_lib.ps1) ---
# INLINE COPY of daaf_lib.ps1 Set-DaafSettingsKey: the installer is a deliberately
# standalone `irm | iex` script that does not dot-source daaf_lib.ps1 (mirroring
# its existing inline settings parsers above), so the write helper is carried
# inline. Semantics, placement rules, atomicity, paired encoding (BOM-less UTF-8
# write + `-Encoding UTF8` read), DRY-RUN gating and strict-mode cleanliness are
# identical to the library version -- see daaf_lib.ps1 for the full annotation,
# including why the read and write encodings must stay pinned together.
function Set-DaafSettingsKey {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Low')]
    param(
        [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$File,
        [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$Key,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Value,
        [ValidateSet('if-absent', 'replace')][string]$Mode = 'if-absent',
        [string]$BackupSuffix = ''
    )

    if (-not (Test-Path -LiteralPath $File)) {
        Write-Error "Set-DaafSettingsKey: file not found: $File"
        return
    }
    $File = (Resolve-Path -LiteralPath $File).Path

    # -Encoding UTF8 is REQUIRED and paired with the BOM-less UTF-8 write below: a
    # bare read on PS 5.1 would decode this function's own BOM-less UTF-8 output as
    # ANSI and mojibake it once per seeded key (see daaf_lib.ps1 for the full note).
    $lines = @(Get-Content -LiteralPath $File -Encoding UTF8 | ForEach-Object { $_ -replace "`r", "" })

    $activeIdx = -1
    $commentIdx = -1
    $keyPattern = '^' + [regex]::Escape($Key) + '='
    $commentPattern = '^\s*#\s*' + [regex]::Escape($Key) + '='
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($activeIdx -lt 0 -and $lines[$i] -match $keyPattern) { $activeIdx = $i }
        if ($commentIdx -lt 0 -and $lines[$i] -match $commentPattern) { $commentIdx = $i }
    }

    $newLine = "$Key=$Value"
    $action = ''
    $out = New-Object System.Collections.Generic.List[string]

    if ($activeIdx -ge 0) {
        if ($Mode -ne 'replace') {
            Write-Host "Set-DaafSettingsKey: $Key skipped (exists)"
            return
        }
        if ($lines[$activeIdx] -eq $newLine) {
            Write-Host "Set-DaafSettingsKey: $Key unchanged (value already present)"
            return
        }
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($i -eq $activeIdx) { $out.Add($newLine) } else { $out.Add($lines[$i]) }
        }
        $action = 'replaced'
    }
    elseif ($commentIdx -ge 0) {
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $out.Add($lines[$i])
            if ($i -eq $commentIdx) { $out.Add($newLine) }
        }
        $action = 'inserted below commented example'
    }
    else {
        for ($i = 0; $i -lt $lines.Count; $i++) { $out.Add($lines[$i]) }
        if ($out.Count -gt 0 -and -not [string]::IsNullOrEmpty($out[$out.Count - 1])) {
            $out.Add('')
        }
        $out.Add('# Added by DAAF on ' + (Get-Date -Format 'yyyy-MM-dd'))
        $out.Add($newLine)
        $action = 'appended (new)'
    }

    if ($env:DAAF_DRY_RUN -eq '1') {
        Write-Host "[DRY-RUN] Set-DaafSettingsKey would write ${File}: $action"
        Write-Host "[DRY-RUN]   line: $newLine"
        return
    }

    if (-not $PSCmdlet.ShouldProcess($File, "Update settings key $Key ($action)")) {
        return
    }

    if (-not [string]::IsNullOrEmpty($BackupSuffix)) {
        $backupPath = $File + $BackupSuffix
        if (-not (Test-Path -LiteralPath $backupPath)) {
            Copy-Item -LiteralPath $File -Destination $backupPath -Confirm:$false
        }
    }

    $payload = ($out -join "`n") + "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    $dir = Split-Path -Parent $File
    if ([string]::IsNullOrEmpty($dir)) { $dir = '.' }
    $tmp = Join-Path $dir ('.daaf_upsert.' + [System.IO.Path]::GetRandomFileName())
    try {
        [System.IO.File]::WriteAllText($tmp, $payload, $utf8NoBom)
        Move-Item -LiteralPath $tmp -Destination $File -Force -Confirm:$false
    }
    catch {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -Confirm:$false }
        Write-Error "Set-DaafSettingsKey: write failed for ${File}: $_"
        return
    }

    Write-Host "Set-DaafSettingsKey: $Key $action"
}

# --- Seed environment_settings.txt from process-env DAAF_* variables ---
# Parity twin of the seeder in install.sh. A fresh install carries the user's
# DAAF_* choices straight into a new environment_settings.txt so future launches
# and updates pick them up without re-exporting. Binding rules (identical to the
# Bash installer):
#   - Never overwrite an existing environment_settings.txt (a reinstall preserves
#     the user's real API keys; env vars are used for THIS install only).
#   - Never fail the install: seeding runs in a try/catch so any failure degrades
#     to a printed manual-fallback note.
#   - Never persist a DAAF_BRANCH that is a version tag (a persisted tag would
#     break future updates). Tag-vs-branch is detected from the container clone:
#     `git clone -b <ref>` leaves HEAD symbolic for a branch and detached for a
#     tag, so `symbolic-ref -q HEAD` is a cheap local (no-network) discriminator.
#   - Always print an outcome note; fully DAAF_DRY_RUN gated (HSM5).
$SeedSrc = Join-Path $InstallDir "environment_settings_example.txt"
$SeedDst = Join-Path $InstallDir "environment_settings.txt"

if ($env:DAAF_DRY_RUN -eq "1") {
    Write-Host ""
    Write-Host "[DRY-RUN] Would seed $SeedDst from process-env DAAF_* variables (if absent, never overwriting an existing file)."
}
elseif (Test-Path -LiteralPath $SeedDst) {
    Write-Host ""
    Write-Host "NOTE: An existing environment_settings.txt was found and left untouched."
    Write-Host "      Any DAAF_* environment variables you set were used for THIS install"
    Write-Host "      only; your existing settings file was preserved."
}
elseif (-not (Test-Path -LiteralPath $SeedSrc)) {
    Write-Host ""
    Write-Host "NOTE: Could not seed environment_settings.txt (the example template was"
    Write-Host "      not found). To configure settings manually:"
    Write-Host "        cd $InstallDir"
    Write-Host "        Copy-Item environment_settings_example.txt environment_settings.txt"
    Write-Host "        # then edit environment_settings.txt with your keys and settings"
}
else {
    # Determine whether DAAF_BRANCH (if set) is a branch or a version tag.
    # Three outcomes are distinguished so a docker-exec failure is never
    # misreported as "is a tag" (a false tag claim + a silently dropped seed):
    #   1. exec healthy + attached HEAD (symbolic-ref succeeds) -> branch, seed
    #   2. exec healthy + detached HEAD (symbolic-ref fails)    -> tag, skip w/ note
    #   3. exec/probe failure (health probe fails)             -> cannot verify, skip
    # A cheap health probe (git rev-parse HEAD) runs first over the SAME exec
    # path; only if it succeeds is a subsequent symbolic-ref failure trusted as
    # "detached HEAD = tag". Both probes are local (no network) and this whole
    # else-branch is skipped under DAAF_DRY_RUN, so it stays dry-run inert.
    $SeedBranchOk = $false
    $SeedBranchSkipTag = $false
    $SeedBranchUnverified = $false
    if (-not [string]::IsNullOrEmpty($env:DAAF_BRANCH)) {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        docker compose -f "$InstallDir\docker-compose.yml" exec -T daaf-docker git -C /daaf rev-parse HEAD 2>&1 | Out-Null
        $probeOk = ($LASTEXITCODE -eq 0)
        if ($probeOk) {
            docker compose -f "$InstallDir\docker-compose.yml" exec -T daaf-docker git -C /daaf symbolic-ref -q HEAD 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $SeedBranchOk = $true } else { $SeedBranchSkipTag = $true }
        } else {
            $SeedBranchUnverified = $true
        }
        $ErrorActionPreference = $savedEAP
    }

    $SeedOk = $true
    $SeedKeys = @()
    try {
        Copy-Item -LiteralPath $SeedSrc -Destination $SeedDst
        foreach ($k in @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV', 'DAAF_BRANCH')) {
            $v = [Environment]::GetEnvironmentVariable($k, "Process")
            if ([string]::IsNullOrEmpty($v)) { continue }
            if ($k -eq 'DAAF_BRANCH' -and -not $SeedBranchOk) { continue }
            Set-DaafSettingsKey -File $SeedDst -Key $k -Value $v -Mode if-absent | Out-Null
            $SeedKeys += $k
        }
    }
    catch {
        $SeedOk = $false
    }

    Write-Host ""
    if ($SeedOk) {
        if ($SeedKeys.Count -gt 0) {
            Write-Host "NOTE: Created environment_settings.txt and seeded these values from your"
            Write-Host ("      environment: " + ($SeedKeys -join ' '))
        } else {
            Write-Host "NOTE: Created environment_settings.txt from the template (no DAAF_* values"
            Write-Host "      were set in your environment to seed)."
        }
        if ($SeedBranchSkipTag) {
            Write-Host "      DAAF_BRANCH was NOT seeded because '$($env:DAAF_BRANCH)' is a version tag;"
            Write-Host "      persisting a tag would break future updates. Ongoing updates track the"
            Write-Host "      default branch. Edit environment_settings.txt to pin a branch if desired."
        }
        if ($SeedBranchUnverified) {
            Write-Host "      DAAF_BRANCH was NOT seeded: could not verify whether '$($env:DAAF_BRANCH)' is"
            Write-Host "      a branch (the container clone was not reachable). Add DAAF_BRANCH to"
            Write-Host "      environment_settings.txt manually if desired."
        }
        Write-Host "      Review it and add any data source API keys before your next launch."

        # Recreate the container so the newly created environment_settings.txt takes
        # effect. docker-compose.yml injects it via `env_file`, which is applied at
        # container CREATION -- and this container was created (up -d above) BEFORE
        # the seeder wrote the file, so without a recreate the seeded settings are
        # not injected AND the run_daaf "modified since container started" freshness
        # NOTE would fire on the very next launch of a fresh install. --force-recreate
        # is deliberate: an all-commented seeded file resolves to an empty compose
        # env and would NOT trigger config-hash recreate on its own, leaving the
        # warning armed. Reached only in the SeedOk path (the file was actually
        # created) and never under DAAF_DRY_RUN (that hits the dry-run branch above).
        # The just-cloned repo lives in the daaf-data NAMED VOLUME, so recreating the
        # container cannot lose it. Non-fatal: on failure, print the same
        # down/relaunch guidance run_daaf gives and continue (never fail the install).
        Write-Host ""
        Write-Host "NOTE: Restarting the container to apply your seeded settings..."
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        docker compose -f "$InstallDir\docker-compose.yml" up -d --force-recreate
        $RecreateExit = $LASTEXITCODE
        $ErrorActionPreference = $savedEAP
        if ($RecreateExit -ne 0) {
            Write-Host "NOTE: Could not restart the container to apply the seeded settings. They"
            Write-Host "      were written to environment_settings.txt but will not take effect"
            Write-Host "      until you recreate the container. Close all DAAF sessions, then run:"
            Write-Host "        cd $InstallDir"
            Write-Host "        docker compose down"
            Write-Host "        .\run_daaf.ps1"
        }
    } else {
        Write-Host "NOTE: Automatic settings seeding did not fully complete, so your other"
        Write-Host "      installation steps finished but environment_settings.txt may be absent"
        Write-Host "      or partial. To configure it manually:"
        Write-Host "        cd $InstallDir"
        Write-Host "        Copy-Item environment_settings_example.txt environment_settings.txt"
        Write-Host "        # then edit environment_settings.txt with your keys and settings"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  Installation complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "To start using DAAF:"
Write-Host ""
Write-Host "  1. Navigate to the install directory and launch the DAAF Control Panel:"
Write-Host "     cd $InstallDir"
Write-Host "     .\daaf.ps1"
Write-Host ""
Write-Host "     The Control Panel provides a status dashboard, service management,"
Write-Host "     and all DAAF operations in one place."
Write-Host ""
Write-Host "  2. On first launch, you'll be asked to authenticate with your Anthropic account."
Write-Host ""
Write-Host "Available scripts (in $InstallDir):"
Write-Host "  .\daaf.ps1                     DAAF Control Panel (recommended)"
Write-Host "  .\run_daaf.ps1                 Launch Claude Code directly"
Write-Host "  .\run_daaf.ps1 bash            Enter the container shell"
Write-Host "  .\backup_daaf.ps1              Back up the Docker volume to a dated folder"
Write-Host "  .\restore_from_backup.ps1      Restore from a backup"
Write-Host "  .\update_daaf.ps1              Check for and apply DAAF updates"
Write-Host "  .\rebuild_daaf.ps1             Copy build files from container and rebuild image"
Write-Host "  .\view_logs.ps1                Browse session logs in your browser"
Write-Host "  .\view_notebooks.ps1           Browse and edit marimo notebooks in your browser"
Write-Host "  .\view_quarto.ps1              Render and view Quarto notebooks in your browser"
Write-Host "  .\run_vscode.ps1               Open VS Code in your browser (code-server)"
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
