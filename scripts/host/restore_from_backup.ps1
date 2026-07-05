# ============================================================================
# DAAF Restore from Backup (Windows PowerShell)
# ============================================================================
# Restores a DAAF Docker volume from a previously created backup.
#
# Usage:
#   cd daaf-docker
#   .\restore_from_backup.ps1
#
# The script searches the current directory for backup folders matching the
# naming pattern produced by backup_daaf.ps1 (e.g., 2026-04-21_daaf_backup\)
# and presents them for interactive selection.
#
# WARNING: Restoring is a DESTRUCTIVE operation. The entire contents of the
# Docker volume are erased and replaced with the backup contents.
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

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
# process environment so the volume name below reflects DAAF_PROJECT_NAME and
# `docker compose down` (used when stopping a running container) targets the right
# project. Canonical shared pattern (kept in sync with Import-DaafSettingsFile in
# daaf_lib.ps1); standalone scripts that do NOT dot-source daaf_lib.ps1 inline it.
# Parse only these four keys (never dot-source -- the file holds API keys); process
# env wins; absent file = no-op; CR stripped; PS 5.1 safe.
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

# --- Configuration ---
# The Docker named volume is project-prefixed: "<project>_daaf-data". Default
# unset => "daaf_daaf-data" (byte-for-byte identical to the previous hardcoded value).
$projectName = "daaf"
if ($env:DAAF_PROJECT_NAME) { $projectName = $env:DAAF_PROJECT_NAME }
$VolumeName = "${projectName}_daaf-data"
# Second volume: Claude Code state. Restored only when the selected backup
# contains the dedicated subfolder (newer backups); older backups predating the
# volume are restored data-only with a warning.
$ClaudeVolumeName = "${projectName}_daaf-claude-config"
$ClaudeSubDir = ".daaf-claude-config"

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI
# cross-platform smoke testing without a Docker daemon.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*volume inspect*" { return }
            "*ps --filter*" { return }
            "*run --rm*rm -rf*" { return }
            "*run --rm*cp -a*" { return }
            "*run --rm*find /dest*" {
                Write-Output "42"
                return
            }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/restore_from_backup.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  DAAF Restore from Backup"
Write-Host "=========================================="
Write-Host ""

# --- Preflight ---
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

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker volume inspect $VolumeName 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker volume '$VolumeName' not found." -ForegroundColor Red
    Write-Host "Have you run the DAAF installer yet?"
    Wait-AndExit 1
}

# --- Check for running containers using the volume ---
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$RunningContainers = @(docker ps --filter "volume=$VolumeName" --format '{{.Names}}' 2>&1)
$ErrorActionPreference = $savedEAP
$RunningContainers = @($RunningContainers | Where-Object { $_ -and $_.Trim() -ne "" })

if ($RunningContainers.Count -gt 0) {
    Write-Host "The DAAF container is currently running:"
    Write-Host ""
    foreach ($name in $RunningContainers) {
        Write-Host "  - $name"
    }
    Write-Host ""
    Write-Host "The container must be stopped before restoring. This will terminate"
    Write-Host "any Claude Code sessions currently in progress."
    Write-Host ""
    $StopChoice = Read-Host "Stop the container now? (y/n)"
    if ($StopChoice -eq "y" -or $StopChoice -eq "Y") {
        Write-Host ""
        Write-Host "Stopping containers..."
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $null = docker compose down 2>&1
        $ErrorActionPreference = $savedEAP
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to stop containers." -ForegroundColor Red
            Wait-AndExit 1
        }
        Write-Host "Containers stopped."
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "Restore cancelled. Stop the container manually and try again:"
        Write-Host "  docker compose down"
        Wait-AndExit 0
    }
}

# --- Find backup folders ---
$Backups = @(Get-ChildItem -Directory | Where-Object {
    $_.Name -match '^\d{4}-\d{2}-\d{2}[a-z]?_daaf_backup$'
} | Sort-Object Name -Descending)

if ($Backups.Count -eq 0) {
    if ($env:DAAF_DRY_RUN -eq "1") {
        Write-Host "[DRY-RUN] No backup folders found (expected in CI)."
        Write-Host ""
        Write-Host "=========================================="
        Write-Host "  Restore dry-run complete!"
        Write-Host "=========================================="
        Wait-AndExit 0
    }
    Write-Host "No backup folders found in the current directory." -ForegroundColor Red
    Write-Host ""
    Write-Host "Backup folders are created by backup_daaf.ps1 and follow the pattern:"
    Write-Host "  2026-04-21_daaf_backup\"
    Write-Host "  2026-04-21a_daaf_backup\"
    Write-Host ""
    Write-Host "Make sure you are running this script from your daaf-docker folder."
    Wait-AndExit 1
}

# --- Display backups (newest first, already sorted descending) ---
Write-Host "Available backups (newest first):"
Write-Host ""
for ($i = 0; $i -lt $Backups.Count; $i++) {
    $dir = $Backups[$i]
    $fileCount = @(Get-ChildItem -Path $dir.FullName -Recurse -File -Force -ErrorAction SilentlyContinue).Count
    $sizeBytes = (Get-ChildItem -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sizeBytes) { $sizeBytes = 0 }
    if ($sizeBytes -ge 1073741824) {
        $sizeStr = "{0:N1}G" -f ($sizeBytes / 1073741824)
    } elseif ($sizeBytes -ge 1048576) {
        $sizeStr = "{0:N0}M" -f ($sizeBytes / 1048576)
    } else {
        $sizeStr = "{0:N0}K" -f ($sizeBytes / 1024)
    }
    Write-Host ("  {0}) {1}  ({2} files, {3})" -f ($i + 1), $dir.Name, $fileCount, $sizeStr)
}
Write-Host ""

# --- Dry-run early exit ---
if ($env:DAAF_DRY_RUN -eq "1") {
    Write-Host "[DRY-RUN] Would present interactive selection for $($Backups.Count) backup(s)."
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Restore dry-run complete!"
    Write-Host "=========================================="
    Wait-AndExit 0
}

# --- User selects backup ---
$Choice = Read-Host "Enter backup number to restore (1-$($Backups.Count))"

$ChoiceNum = 0
if (-not [int]::TryParse($Choice, [ref]$ChoiceNum) -or $ChoiceNum -lt 1 -or $ChoiceNum -gt $Backups.Count) {
    Write-Host "" -ForegroundColor Red
    Write-Host "ERROR: Invalid selection '$Choice'. Please enter a number between 1 and $($Backups.Count)." -ForegroundColor Red
    Wait-AndExit 1
}

$Selected = $Backups[$ChoiceNum - 1]
$SelectedName = $Selected.Name
$SelectedPath = $Selected.FullName

Write-Host ""
Write-Host "Selected: $SelectedName"

# --- Detect Claude Code state in the backup ---
# Newer backups nest the Claude Code state volume in a hidden subfolder. Older
# backups (created before the dedicated volume existed) lack it -- those restore
# data-only with a warning.
$ClaudeBackupPath = Join-Path $SelectedPath $ClaudeSubDir
# Require the subfolder to exist AND be non-empty. An empty "$ClaudeSubDir\" dir
# (e.g., a stray pre-created folder from an interrupted backup) must NOT trigger
# the Claude restore path below -- that path CLEARS the live claude-config volume
# before copying, so restoring from an empty source would wipe the user's Claude
# Code login and session history and copy nothing back.
$HasClaudeBackup = $false
if (Test-Path -LiteralPath $ClaudeBackupPath -PathType Container) {
    $claudeItemCount = @(Get-ChildItem -LiteralPath $ClaudeBackupPath -Force -ErrorAction SilentlyContinue).Count
    if ($claudeItemCount -gt 0) { $HasClaudeBackup = $true }
}

# --- Count source files ---
# Exclude the Claude subfolder from the DATA-volume count -- it is restored to a
# separate volume below, not into the data volume.
Write-Host ""
Write-Host "Scanning backup..."
$TotalFiles = @(Get-ChildItem -Path $SelectedPath -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike "$ClaudeBackupPath*" }).Count
$TotalSizeBytes = (Get-ChildItem -Path $SelectedPath -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike "$ClaudeBackupPath*" } | Measure-Object -Property Length -Sum).Sum
if ($null -eq $TotalSizeBytes) { $TotalSizeBytes = 0 }
if ($TotalSizeBytes -ge 1073741824) {
    $TotalSizeStr = "{0:N1}G" -f ($TotalSizeBytes / 1073741824)
} elseif ($TotalSizeBytes -ge 1048576) {
    $TotalSizeStr = "{0:N0}M" -f ($TotalSizeBytes / 1048576)
} else {
    $TotalSizeStr = "{0:N0}K" -f ($TotalSizeBytes / 1024)
}
Write-Host "Found $TotalFiles files ($TotalSizeStr) to restore."

# --- Destructive warning ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Red
Write-Host "  *** WARNING: DESTRUCTIVE OPERATION ***" -ForegroundColor Red
Write-Host "==========================================" -ForegroundColor Red
Write-Host ""
Write-Host "This will COMPLETELY ERASE the current contents of your"
Write-Host "DAAF Docker volume and replace them with the backup."
Write-Host ""
Write-Host "All existing files, git history, research data, and"
Write-Host "configuration in the Docker volume will be permanently"
Write-Host "deleted and overwritten by the backup contents."
Write-Host ""
Write-Host "Source:      $SelectedName\ ($TotalFiles files, $TotalSizeStr)"
Write-Host "Destination: Docker volume '$VolumeName'"
if ($HasClaudeBackup) {
    Write-Host ""
    Write-Host "This backup also contains Claude Code state (credentials and session"
    Write-Host "history), which will be restored to volume '$ClaudeVolumeName',"
    Write-Host "overwriting any existing Claude Code login/history in this install."
}
Write-Host ""
$Confirm = Read-Host "Type RESTORE to confirm, or anything else to cancel"

if ($Confirm -ne "RESTORE") {
    Write-Host ""
    Write-Host "Restore cancelled."
    Wait-AndExit 0
}

Write-Host ""

# --- Step 1: Clear the Docker volume ---
Write-Host "Clearing Docker volume..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker run --rm -v "${VolumeName}:/dest" busybox sh -c 'rm -rf /dest/* /dest/.[!.]* /dest/..?*' 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to clear Docker volume." -ForegroundColor Red
    Write-Host "The volume may be in an inconsistent state."
    Wait-AndExit 1
}
Write-Host "Volume cleared."
Write-Host ""

# --- Step 2: Copy backup into volume ---
Write-Host "Copying backup into Docker volume..."
Write-Host "  This may take a few minutes for large backups."
Write-Host ""

# Copy everything, then strip the Claude subfolder from the DATA volume -- it
# belongs in the separate Claude volume (restored below), not the data volume.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker run --rm -v "${SelectedPath}:/source:ro" -v "${VolumeName}:/dest" busybox sh -c "cp -a /source/. /dest/ && rm -rf `"/dest/${ClaudeSubDir}`"" 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "" -ForegroundColor Red
    Write-Host "ERROR: File copy failed." -ForegroundColor Red
    Write-Host "The Docker volume may be in an inconsistent state."
    Write-Host "You may want to re-run this restore or reinstall DAAF."
    Wait-AndExit 1
}
Write-Host "Copy complete."
Write-Host ""

# --- Verify ---
Write-Host "Verifying restore..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$VerifyOutput = docker run --rm -v "${VolumeName}:/dest:ro" busybox sh -c 'find /dest -type f | wc -l' 2>&1
$ErrorActionPreference = $savedEAP
$RestoredCount = 0
if ($null -ne $VerifyOutput) {
    $null = [int]::TryParse(($VerifyOutput | Out-String).Trim(), [ref]$RestoredCount)
}

if ($RestoredCount -eq 0) {
    Write-Host ""
    Write-Host "ERROR: Verification failed -- 0 files found in restored volume." -ForegroundColor Red
    Write-Host "The restore may have failed. Consider re-running or reinstalling DAAF."
    Wait-AndExit 1
}

Write-Host "Verified: $RestoredCount files in restored volume."

# --- File count comparison ---
if ($TotalFiles -gt 0 -and $RestoredCount -gt 0) {
    $Diff = [math]::Abs($TotalFiles - $RestoredCount)
    $Tolerance = [math]::Max(1, [math]::Floor($TotalFiles / 100))
    if ($Diff -gt $Tolerance) {
        Write-Host ""
        Write-Host "WARNING: File count mismatch." -ForegroundColor Yellow
        Write-Host "         Backup: $TotalFiles files, Restored: $RestoredCount files (difference: $Diff)"
        Write-Host "         The restore may be incomplete."
    }
}

# --- Restore the Claude Code state volume ---
# Only when the backup contains it. Older backups predating the volume are
# restored data-only, with a clear warning (not an error) so the user knows
# Claude Code login/history was not part of that backup.
if ($HasClaudeBackup) {
    Write-Host ""
    Write-Host "Restoring Claude Code state (credentials, session history, plugins)..."
    # Ensure the volume exists (idempotent) in case restore runs before first start.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $null = docker volume create $ClaudeVolumeName 2>&1
    # Clear then copy, mirroring the data-volume restore semantics.
    $null = docker run --rm -v "${ClaudeVolumeName}:/dest" busybox sh -c 'rm -rf /dest/* /dest/.[!.]* /dest/..?*' 2>&1
    $clearOk = ($LASTEXITCODE -eq 0)
    if ($clearOk) {
        $null = docker run --rm -v "${ClaudeBackupPath}:/source:ro" -v "${ClaudeVolumeName}:/dest" busybox sh -c "cp -a /source/. /dest/" 2>&1
        $claudeCopyOk = ($LASTEXITCODE -eq 0)
    } else {
        $claudeCopyOk = $false
    }
    $ErrorActionPreference = $savedEAP
    if (-not $clearOk) {
        Write-Host "WARNING: Failed to clear the Claude Code state volume before restore." -ForegroundColor Yellow
        Write-Host "         Data volume restore above succeeded; Claude state may be inconsistent."
    } elseif (-not $claudeCopyOk) {
        Write-Host "WARNING: Failed to restore the Claude Code state volume." -ForegroundColor Yellow
        Write-Host "         Data volume restore above succeeded; you may need to re-run /login."
    } else {
        Write-Host "Claude Code state restored."
    }
} else {
    Write-Host ""
    Write-Host "NOTE: This backup does not contain Claude Code state (it predates the"
    Write-Host "      dedicated Claude volume). Your data was restored, but Claude Code"
    Write-Host "      login and session history were NOT part of this backup -- you may"
    Write-Host "      need to run /login again after starting DAAF."
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  Restore complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Restored: $SelectedName"
Write-Host "Files:    $RestoredCount files in volume"
Write-Host ""
Write-Host "You can now start DAAF with:"
Write-Host "  .\run_daaf.ps1"
Write-Host ""
Wait-AndExit 0
