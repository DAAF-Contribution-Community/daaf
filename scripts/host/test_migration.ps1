# ============================================================================
# DAAF Migration End-to-End Test (Windows PowerShell)
# ============================================================================
# Automated 1-click test that:
#   1. Nukes any existing DAAF Docker resources (clean slate)
#   2. Installs an old version of DAAF from a specific tag/branch
#   3. Simulates the correct "era" (clone-based vs ZIP-based) for that version
#   4. Creates committed framework changes + research files
#   5. Creates uncommitted framework changes + research files
#   6. Runs the migration script (from the local repo, not GitHub)
#   7. Runs verification checks to ensure everything worked
#
# Usage:
#   .\test_migration.ps1                                          # defaults to v2.0.1
#   $env:DAAF_TEST_VERSION = "v1.0.0"; .\test_migration.ps1      # test Era 1
#   $env:DAAF_TEST_VERSION = "v2.0.0"; .\test_migration.ps1      # test Era 2
#
# Environment variables:
#   DAAF_TEST_VERSION      Tag/branch to install (default: v2.0.1)
#   DAAF_TEST_ERA          Override era detection: "1" or "2" (default: auto)
#   DAAF_MIGRATION_BRANCH  Branch for migration script downloads (default: minor_revisions_v202)
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection (to pull old versions from GitHub)
#   - This script must be run from a local clone of the DAAF repo
#     (it copies migrate_daaf.ps1 from the local repo)
#
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

# Ensure TLS 1.2 for GitHub downloads (required on PowerShell 5.1)
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

# --- Configuration ---
$TestVersion = if ($env:DAAF_TEST_VERSION) { $env:DAAF_TEST_VERSION } else { "v2.0.1" }
$MigrationBranch = if ($env:DAAF_MIGRATION_BRANCH) { $env:DAAF_MIGRATION_BRANCH } else { "minor_revisions_v202" }
$Repo = "DAAF-Contribution-Community/daaf"
$VolumeName = "daaf_daaf-data"
$ContainerMain = "daaf-daaf-docker-1"

# Auto-detect era from version if not overridden
# v1.0.0 = Era 1 (clone-based, remote exists)
# v2.0.0+ = Era 2 (ZIP-based, no remote)
if ($env:DAAF_TEST_ERA) {
    $TestEra = $env:DAAF_TEST_ERA
} elseif ($TestVersion -eq "v1.0.0") {
    $TestEra = "1"
} else {
    $TestEra = "2"
}

# Locate the local repo root (where this script lives)
$ScriptDir = $PSScriptRoot
# The repo root is two levels up from scripts/host/
$LocalRepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

# Verify local migrate_daaf.ps1 exists
$LocalMigratePath = Join-Path $LocalRepoRoot "scripts\host\migrate_daaf.ps1"
if (-not (Test-Path $LocalMigratePath)) {
    Write-Error "Cannot find migrate_daaf.ps1 in the local repo. Expected at: $LocalMigratePath"
    exit 1
}

# Working directory for the test install
$TestDir = Join-Path ([System.IO.Path]::GetTempPath()) "daaf-migration-test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$null = New-Item -ItemType Directory -Path $TestDir -Force

# Track test results
$script:TestsPassed = 0
$script:TestsFailed = 0
$script:Failures = @()

function Test-Check {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Description,
        [Parameter(Mandatory)]
        [bool]$Passed
    )
    if ($Passed) {
        $script:TestsPassed++
        Write-Host "  PASS: $Description" -ForegroundColor Green
    } else {
        $script:TestsFailed++
        $script:Failures += "  FAIL: $Description"
        Write-Host "  FAIL: $Description" -ForegroundColor Red
    }
}

# Container helper functions
function Invoke-ContainerExec {
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments=$true)]$ExecArgs)
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker exec $script:ContainerName @ExecArgs 2>$null
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

function Invoke-ContainerGit {
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments=$true)]$GitArgs)
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $result = docker exec $script:ContainerName git -C /daaf @GitArgs 2>$null | Out-String
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

$EraLabel = if ($TestEra -eq "1") { "clone-based" } else { "ZIP-based" }

Write-Host ""
Write-Host "==========================================" -ForegroundColor White
Write-Host "  DAAF Migration Test" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor White
Write-Host ""
Write-Host "  Version:   $TestVersion"
Write-Host "  Era:       $TestEra ($EraLabel)"
Write-Host "  Migration: from local repo (branch: $MigrationBranch)"
Write-Host "  Work dir:  $TestDir"
Write-Host ""

# =====================================================================
# PHASE 1: Clean Slate
# =====================================================================
Write-Host "[1/7] Clean slate" -ForegroundColor White
Write-Host ""

# Preflight
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found. Install Docker Desktop first."
    exit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker daemon is not running. Start Docker Desktop first."
    exit 1
}

Write-Host "INFO: Removing any existing DAAF Docker resources..." -ForegroundColor Cyan

# Stop and remove containers
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker rm -f $ContainerMain 2>&1 | Out-Null
docker rm -f "daaf-daaf-init-1" 2>&1 | Out-Null
# Remove volume
docker volume rm $VolumeName 2>&1 | Out-Null
# Remove image
docker rmi "daaf-daaf-docker" 2>&1 | Out-Null
$ErrorActionPreference = $savedEAP

Write-Host "SUCCESS: Clean slate achieved." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 2: Install Old Version
# =====================================================================
Write-Host "[2/7] Install $TestVersion" -ForegroundColor White
Write-Host ""

Write-Host "INFO: Installing DAAF from branch/tag: $TestVersion" -ForegroundColor Cyan
Write-Host "INFO: This will build the Docker image and clone the repo - may take several minutes..." -ForegroundColor Cyan
Write-Host ""

Set-Location $TestDir

# Download and run the install script from the target version
$InstallUrl = "https://raw.githubusercontent.com/$Repo/$TestVersion/scripts/host/install.ps1"
$InstallScript = Join-Path $TestDir "install_old.ps1"

Invoke-WebRequest -UseBasicParsing -Uri $InstallUrl -OutFile $InstallScript

$env:DAAF_BRANCH = $TestVersion
$env:DAAF_NESTED = "1"
& $InstallScript
Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue

# Verify install succeeded
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker volume inspect $VolumeName 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Error "Installation failed - volume $VolumeName not found."
    exit 1
}

Write-Host "SUCCESS: DAAF $TestVersion installed successfully." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 3: Simulate Era
# =====================================================================
Write-Host "[3/7] Simulate Era $TestEra" -ForegroundColor White
Write-Host ""

# Discover container
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$script:ContainerName = (docker ps -a --filter "volume=$VolumeName" --format '{{.Names}}' | Select-Object -First 1 | Out-String).Trim() -replace "`r",""
$ErrorActionPreference = $savedEAP

if ([string]::IsNullOrWhiteSpace($script:ContainerName)) {
    Write-Error "No container found using volume $VolumeName."
    exit 1
}

# Ensure running
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ContainerState = (docker inspect --format '{{.State.Status}}' $script:ContainerName 2>$null | Out-String).Trim() -replace "`r",""
$ErrorActionPreference = $savedEAP

if ($ContainerState -ne "running") {
    Write-Host "INFO: Starting container $($script:ContainerName)..." -ForegroundColor Cyan
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker start $script:ContainerName 2>&1 | Out-Null
    $ErrorActionPreference = $savedEAP
    Start-Sleep -Seconds 3
}

if ($TestEra -eq "2") {
    # Era 2: ZIP-based install - remove the remote to simulate no remote
    Write-Host "INFO: Simulating ZIP-based install (removing git remote)..." -ForegroundColor Cyan
    $null = Invoke-ContainerGit remote remove origin

    $OriginCheck = Invoke-ContainerGit remote get-url origin
    if ([string]::IsNullOrWhiteSpace($OriginCheck)) {
        Write-Host "SUCCESS: Remote removed - simulating Era 2 (ZIP-based) install." -ForegroundColor Green
    } else {
        Write-Host "WARNING: Failed to remove remote. Era simulation may be inaccurate." -ForegroundColor Yellow
    }
} elseif ($TestEra -eq "1") {
    # Era 1: clone-based - remote should already exist from install
    $OriginCheck = Invoke-ContainerGit remote get-url origin
    if (-not [string]::IsNullOrWhiteSpace($OriginCheck)) {
        Write-Host "SUCCESS: Remote exists ($OriginCheck) - Era 1 (clone-based) already simulated." -ForegroundColor Green
    } else {
        Write-Host "WARNING: Expected remote for Era 1 but none found. Adding one..." -ForegroundColor Yellow
        $null = Invoke-ContainerGit remote add origin "https://github.com/$Repo.git"
        Write-Host "SUCCESS: Remote added." -ForegroundColor Green
    }
}

Write-Host ""

# =====================================================================
# PHASE 4: Simulate User Work (Committed)
# =====================================================================
Write-Host "[4/7] Simulate committed user work" -ForegroundColor White
Write-Host ""

Write-Host "INFO: Creating committed framework changes and research files..." -ForegroundColor Cyan

# Create a research project
Invoke-ContainerExec bash -c 'mkdir -p /daaf/research/2026-01-15_Test_Analysis/data'
Invoke-ContainerExec bash -c 'mkdir -p /daaf/research/2026-01-15_Test_Analysis/scripts'
Invoke-ContainerExec bash -c 'mkdir -p /daaf/research/2026-01-15_Test_Analysis/output'
Invoke-ContainerExec bash -c @'
cat > /daaf/research/2026-01-15_Test_Analysis/scripts/01_fetch.py << "PYEOF"
# --- Config ---
import polars as pl

BASE_DIR = "/daaf"
PROJECT_DIR = f"{BASE_DIR}/research/2026-01-15_Test_Analysis"

# --- Load ---
# INTENT: Fetch test data for migration verification
print("Test script executed successfully")
PYEOF
'@

Invoke-ContainerExec bash -c 'echo "Test analysis data" > /daaf/research/2026-01-15_Test_Analysis/data/test_data.txt'
Invoke-ContainerExec bash -c 'echo "# Test Analysis" > /daaf/research/2026-01-15_Test_Analysis/README.md'

# Make a framework modification
Invoke-ContainerExec bash -c 'echo "" >> /daaf/CLAUDE.md'
Invoke-ContainerExec bash -c 'echo "<!-- test-migration-marker: committed -->" >> /daaf/CLAUDE.md'

# Commit everything
$null = Invoke-ContainerGit add -A
$null = Invoke-ContainerGit commit -m "Test: Add research project and framework tweaks"

$CommittedSha = Invoke-ContainerGit rev-parse HEAD
Write-Host "INFO: Committed changes at: $($CommittedSha.Substring(0, [Math]::Min(12, $CommittedSha.Length)))" -ForegroundColor Cyan
Write-Host "SUCCESS: Committed user work created." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 5: Simulate User Work (Uncommitted)
# =====================================================================
Write-Host "[5/7] Simulate uncommitted user work" -ForegroundColor White
Write-Host ""

Write-Host "INFO: Creating uncommitted framework changes and research files..." -ForegroundColor Cyan

# Add more uncommitted research files
Invoke-ContainerExec bash -c 'mkdir -p /daaf/research/2026-02-10_WIP_Analysis/scripts'
Invoke-ContainerExec bash -c 'echo "Work in progress data" > /daaf/research/2026-02-10_WIP_Analysis/notes.md'
Invoke-ContainerExec bash -c @'
cat > /daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py << "PYEOF"
# --- Config ---
# INTENT: WIP exploration script - uncommitted
print("WIP script")
PYEOF
'@

# Make an uncommitted framework change
Invoke-ContainerExec bash -c 'echo "<!-- test-migration-marker: uncommitted -->" >> /daaf/CLAUDE.md'

Write-Host "SUCCESS: Uncommitted user work created." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 6: Run Migration
# =====================================================================
Write-Host "[6/7] Run migration script" -ForegroundColor White
Write-Host ""

Write-Host "INFO: Copying migration script from local repo..." -ForegroundColor Cyan

# Determine the daaf-docker host directory
$HostDir = Join-Path $TestDir "daaf-docker"
if (-not (Test-Path $HostDir)) {
    $HostDir = $TestDir
}

# Copy the local migration script to the host dir
Copy-Item $LocalMigratePath (Join-Path $HostDir "migrate_daaf.ps1") -Force

Write-Host "INFO: Running migration with DAAF_BRANCH=$MigrationBranch..." -ForegroundColor Cyan
Write-Host ""

Set-Location $HostDir

# Run migration non-interactively
$env:DAAF_BRANCH = $MigrationBranch
$env:DAAF_NESTED = "1"

# Wrap in try/catch since migration might exit non-zero
try {
    & (Join-Path $HostDir "migrate_daaf.ps1")
} catch {
    Write-Host "WARNING: Migration script threw an error: $_" -ForegroundColor Yellow
    Write-Host "WARNING: This may or may not indicate a problem - check the output above." -ForegroundColor Yellow
}

Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "SUCCESS: Migration script completed." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 7: Verification
# =====================================================================
Write-Host "[7/7] Verification" -ForegroundColor White
Write-Host ""

# Re-discover container (may have changed during migration)
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$script:ContainerName = (docker ps -a --filter "volume=$VolumeName" --format '{{.Names}}' | Select-Object -First 1 | Out-String).Trim() -replace "`r",""
$ErrorActionPreference = $savedEAP

if ([string]::IsNullOrWhiteSpace($script:ContainerName)) {
    Write-Error "No container found after migration!"
    exit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ContainerState = (docker inspect --format '{{.State.Status}}' $script:ContainerName 2>$null | Out-String).Trim() -replace "`r",""
$ErrorActionPreference = $savedEAP
if ($ContainerState -ne "running") {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker start $script:ContainerName 2>&1 | Out-Null
    $ErrorActionPreference = $savedEAP
    Start-Sleep -Seconds 3
}

Write-Host "  Git State Checks:" -ForegroundColor White

# Check 1: Remote exists and points to correct repo
$OriginUrl = Invoke-ContainerGit remote get-url origin
if (-not [string]::IsNullOrWhiteSpace($OriginUrl) -and $OriginUrl -match $Repo) {
    Test-Check "Remote 'origin' points to official DAAF repo" $true
} else {
    Test-Check "Remote 'origin' points to official DAAF repo (got: '$OriginUrl')" $false
}

# Check 2: Upstream tracking is set
$Tracking = Invoke-ContainerGit rev-parse --abbrev-ref --symbolic-full-name '@{u}'
if ($Tracking -eq "origin/main") {
    Test-Check "Upstream tracking set to origin/main" $true
} else {
    Test-Check "Upstream tracking set to origin/main (got: '$Tracking')" $false
}

# Check 3: Era-specific - graft exists (Era 2 only)
if ($TestEra -eq "2") {
    $InitialCommit = (Invoke-ContainerGit rev-list --max-parents=0 HEAD) -split "`n" | Select-Object -Last 1
    if (-not [string]::IsNullOrWhiteSpace($InitialCommit)) {
        $InitialCommit = $InitialCommit.Trim()
        $CatFileOutput = Invoke-ContainerGit cat-file -p $InitialCommit
        $ParentCount = 0
        if (-not [string]::IsNullOrWhiteSpace($CatFileOutput)) {
            $ParentCount = ($CatFileOutput -split "`n" | Where-Object { $_ -match '^parent ' }).Count
        }
        Test-Check "Era 2 graft in place (root commit has parent)" ($ParentCount -gt 0)
    } else {
        Test-Check "Era 2 graft in place (could not find root commit)" $false
    }

    # Check merge-base exists
    $MergeBase = Invoke-ContainerGit merge-base HEAD origin/main
    Test-Check "Common ancestor exists with origin/main" (-not [string]::IsNullOrWhiteSpace($MergeBase))
}

Write-Host ""
Write-Host "  Research File Checks:" -ForegroundColor White

# Check 4: Committed research project survived
Invoke-ContainerExec test -f /daaf/research/2026-01-15_Test_Analysis/scripts/01_fetch.py
Test-Check "Committed research project preserved" ($LASTEXITCODE -eq 0)

Invoke-ContainerExec test -f /daaf/research/2026-01-15_Test_Analysis/data/test_data.txt
Test-Check "Committed research data preserved" ($LASTEXITCODE -eq 0)

# Check 5: Uncommitted research files survived
Invoke-ContainerExec test -f /daaf/research/2026-02-10_WIP_Analysis/notes.md
Test-Check "Uncommitted research files preserved" ($LASTEXITCODE -eq 0)

Invoke-ContainerExec test -f /daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py
Test-Check "Uncommitted WIP script preserved" ($LASTEXITCODE -eq 0)

Write-Host ""
Write-Host "  Framework State Checks:" -ForegroundColor White

# Check 6: Committed framework marker survived
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$CommittedMarker = (docker exec $script:ContainerName bash -c 'grep -c "test-migration-marker: committed" /daaf/CLAUDE.md' 2>$null | Out-String).Trim() -replace "`r",""
$ErrorActionPreference = $savedEAP
Test-Check "Committed framework changes preserved" ([int]$CommittedMarker -gt 0)

# Check 7: Uncommitted framework marker survived
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$UncommittedMarker = (docker exec $script:ContainerName bash -c 'grep -c "test-migration-marker: uncommitted" /daaf/CLAUDE.md' 2>$null | Out-String).Trim() -replace "`r",""
$ErrorActionPreference = $savedEAP
Test-Check "Uncommitted framework changes preserved" ([int]$UncommittedMarker -gt 0)

# Check 8: Committed SHA still in history
$GitLog = Invoke-ContainerGit log --oneline
$ShortSha = $CommittedSha.Substring(0, [Math]::Min(7, $CommittedSha.Length))
Test-Check "Committed changes still in git history" ($GitLog -match $ShortSha)

Write-Host ""
Write-Host "  Host Script Checks:" -ForegroundColor White

# Check 9: Host scripts were downloaded
foreach ($Script in @("update_daaf.ps1", "backup_daaf.ps1", "rebuild_daaf.ps1", "run_daaf.ps1", "view_logs.ps1", "view_notebooks.ps1")) {
    Test-Check "Host script downloaded: $Script" (Test-Path (Join-Path $HostDir $Script))
}

# Check 10: Backup was created
$BackupDir = Get-ChildItem -Path $HostDir -Directory -Filter '*_daaf_backup' -ErrorAction SilentlyContinue | Select-Object -First 1
Test-Check "Backup directory created during migration" ($null -ne $BackupDir)

# =====================================================================
# RESULTS
# =====================================================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor White
Write-Host "  Test Results" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor White
Write-Host ""
Write-Host "  Version:  $TestVersion"
Write-Host "  Era:      $TestEra"
Write-Host "  Passed:   $($script:TestsPassed)" -ForegroundColor Green
if ($script:TestsFailed -gt 0) {
    Write-Host "  Failed:   $($script:TestsFailed)" -ForegroundColor Red
} else {
    Write-Host "  Failed:   $($script:TestsFailed)"
}
Write-Host ""

if ($script:TestsFailed -gt 0) {
    Write-Host "  Failures:" -ForegroundColor Red
    foreach ($f in $script:Failures) {
        Write-Host $f -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "ERROR: Some checks failed. Inspect the container and test directory for details." -ForegroundColor Red
    Write-Host "  Container:  $($script:ContainerName)"
    Write-Host "  Host dir:   $HostDir"
    Write-Host "  Test dir:   $TestDir"
    exit 1
} else {
    Write-Host "SUCCESS: All checks passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  The DAAF Docker resources are still running for manual inspection."
    Write-Host "  To clean up:  `$env:DAAF_NUKE_CONFIRM = '1'; & '$LocalRepoRoot\scripts\host\nuke_daaf.ps1'"
    Write-Host ""
}

Write-Host "Test working directory preserved at: $TestDir"
Write-Host "(Delete manually when done inspecting)"
Write-Host ""

# Pause before exit so the user can review output
if (-not $env:DAAF_NESTED) {
    Write-Host ""
    Read-Host "Press Enter to close this window"
}
