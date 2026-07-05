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
            "*run --rm*find /dest*" {
                Write-Output "42"
                return
            }
            default {
                # The dry-run path exits before any create/cp/rm/chown, so no match
                # arm is needed for the copy mechanism or the ownership repair -- the
                # default is only reached for unmodeled calls, which are echoed and
                # treated as no-ops.
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

# Copy the backup into the data volume via `docker create` + `docker cp` instead
# of a bind-mounted `busybox cp -a`. On Docker Desktop for Windows, a bind-mounted
# copy reads every host file across the 9p/gRPC-FUSE host<->VM boundary
# individually, so a large restore takes minutes; `docker cp` streams the whole
# tree to the daemon in one pass and extracts it inside the VM, avoiding that
# per-file overhead. The helper container is created but never started -- `docker
# cp` still writes into the volume because the daemon mounts the container root AND
# its volume MountPoints into the archive view regardless of container state. The
# trailing "/." on the source copies the backup's CONTENTS into /dest.
#
# Two asymmetries vs the backup script's copy-OUT:
#   1. Ownership: `docker cp` INTO a container writes files as ROOT (not the
#      volume's appuser, UID 1000), so a container-side chown repair is REQUIRED
#      below (Step 2c). Copy-OUT needs no repair because `docker cp` extracts
#      container->host as the invoking user.
#   2. Exclusion: `docker cp` has no exclude flag, so it copies the whole backup
#      folder INCLUDING the hidden ".daaf-claude-config\" subfolder. That subfolder
#      belongs in the separate Claude volume (restored below), not the data volume,
#      so it is stripped container-side in Step 2b -- matching the old
#      `cp -a ... && rm -rf "/dest/$ClaudeSubDir"` outcome exactly.
# Only docker cp's text status line reaches stdout here (the file data goes over
# the daemon API pipe, not the PS pipeline), so synchronous inline calls are
# pipeline-safe on PS 5.1.
#
# Structure (mirrors backup_daaf.ps1): do the create + copy inside try, set
# $createOk/$copyOk flags, and put ONLY the best-effort container cleanup in
# finally. All error checks and Wait-AndExit calls happen AFTER the try/finally
# completes -- calling `exit` from inside a `try` whose `finally` must still run is
# version-fragile on PS 5.1, so it is avoided entirely.
$Cid = $null
$createOk = $false
$copyOk = $false
try {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $Cid = (docker create -v "${VolumeName}:/dest" busybox 2>&1).Trim()
    $createOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $savedEAP

    if ($createOk) {
        # Step 2a: copy the backup CONTENTS into the volume.
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $null = docker cp "${SelectedPath}/." "${Cid}:/dest/" 2>&1
        $copyOk = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $savedEAP
    }
} finally {
    # Remove the helper container even if the copy is interrupted (PS finally runs
    # on Ctrl-C). Best-effort; guarded so an unset/empty CID is a no-op. Subsequent
    # container-side steps use `docker run --rm`.
    if (-not [string]::IsNullOrEmpty($Cid)) {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $null = docker rm -f $Cid 2>&1
        $ErrorActionPreference = $savedEAP
    }
}

if (-not $createOk) {
    Write-Host "" -ForegroundColor Red
    Write-Host "ERROR: Could not create the helper container for the volume copy." -ForegroundColor Red
    Write-Host "The Docker volume has already been cleared and is now EMPTY."
    Write-Host "Re-run this restore, or reinstall DAAF, to repopulate it."
    Wait-AndExit 1
}

if (-not $copyOk) {
    Write-Host "" -ForegroundColor Red
    Write-Host "ERROR: File copy failed." -ForegroundColor Red
    Write-Host "The Docker volume may be in an inconsistent state."
    Write-Host "You may want to re-run this restore or reinstall DAAF."
    Wait-AndExit 1
}

# Step 2b: strip the Claude subfolder from the DATA volume. `docker cp` copied the
# whole backup, including "$ClaudeSubDir\"; remove it container-side (fast: inside
# the VM, no bind mount) so the data volume matches the old copy's outcome. It is
# restored to its own volume below when present.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker run --rm -v "${VolumeName}:/dest" busybox rm -rf "/dest/${ClaudeSubDir}" 2>&1
$stripOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if (-not $stripOk) {
    Write-Host "" -ForegroundColor Red
    Write-Host "ERROR: Failed to remove the $ClaudeSubDir subfolder from the data volume." -ForegroundColor Red
    Write-Host "WARNING: The restore copied the whole backup into the data volume, so Claude" -ForegroundColor Yellow
    Write-Host "         Code credentials and session data may REMAIN inside the data volume"
    Write-Host "         until this is resolved. Re-run this restore to clear them."
    Wait-AndExit 1
}

# Step 2c: repair ownership. `docker cp` wrote files as root; the volume must be
# owned by appuser (UID 1000). Chown container-side (inside the VM, no bind mount,
# so it is fast). The literal 1000:1000 mirrors the daaf-init service in
# docker-compose.yml, which chowns both volumes to 1000:1000 on every startup;
# that init container is a second net, but restore must not depend on it.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker run --rm -v "${VolumeName}:/dest" busybox chown -R 1000:1000 /dest 2>&1
$chownOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if (-not $chownOk) {
    Write-Host "" -ForegroundColor Red
    Write-Host "ERROR: Failed to repair ownership on the data volume." -ForegroundColor Red
    Write-Host "The files were restored intact, but the DAAF container may not be able to"
    Write-Host "read them. Re-run this restore, or restart DAAF -- the compose init service"
    Write-Host "also repairs volume ownership on startup."
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
    # Clear then copy, mirroring the data-volume restore semantics. The copy uses
    # the same `docker create` + `docker cp` mechanism (with the same root->1000
    # ownership repair) as the data volume above; the claude-config volume is also
    # chowned to 1000:1000 by daaf-init in docker-compose.yml, but restore repairs
    # it here rather than depending on that init container.
    $null = docker run --rm -v "${ClaudeVolumeName}:/dest" busybox sh -c 'rm -rf /dest/* /dest/.[!.]* /dest/..?*' 2>&1
    $clearOk = ($LASTEXITCODE -eq 0)
    $claudeCopyOk = $false
    if ($clearOk) {
        $ClaudeCid = $null
        try {
            $ClaudeCid = (docker create -v "${ClaudeVolumeName}:/dest" busybox 2>&1).Trim()
            $claudeCreateOk = ($LASTEXITCODE -eq 0)
            if ($claudeCreateOk) {
                $null = docker cp "${ClaudeBackupPath}/." "${ClaudeCid}:/dest/" 2>&1
                $claudeCpOk = ($LASTEXITCODE -eq 0)
                if ($claudeCpOk) {
                    $null = docker run --rm -v "${ClaudeVolumeName}:/dest" busybox chown -R 1000:1000 /dest 2>&1
                    $claudeCopyOk = ($LASTEXITCODE -eq 0)
                }
            }
        } finally {
            # Remove the helper container even if the copy is interrupted (PS
            # finally runs on Ctrl-C). Best-effort; guarded on an unset/empty CID.
            # Wrap in its own SilentlyContinue bracket -- on an interrupt path the
            # ambient EAP is not guaranteed, and under EAP=Stop a stderr line from
            # `docker rm` would throw inside finally.
            if (-not [string]::IsNullOrEmpty($ClaudeCid)) {
                $innerEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
                $null = docker rm -f $ClaudeCid 2>&1
                $ErrorActionPreference = $innerEAP
            }
        }
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
