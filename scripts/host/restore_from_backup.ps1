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
# Parse only these whitelisted keys (never dot-source -- the file holds API keys); process
# env wins; absent file = no-op; CR stripped; PS 5.1 safe.
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

# --- Configuration ---
# The Docker named volume is project-prefixed: "<project>_daaf-data". Default
# unset => "daaf_daaf-data" (byte-for-byte identical to the previous hardcoded value).
# DAAF_DATA_VOLUME_NAME, when set, overrides the whole derivation with a verbatim
# full volume name (the shared-workspace escape hatch); unset => the derived
# default. Matches Resolve-DaafDataVolumeName in daaf_lib.ps1 (inlined here because
# this standalone script does not dot-source the library).
$projectName = "daaf"
if ($env:DAAF_PROJECT_NAME) { $projectName = $env:DAAF_PROJECT_NAME }
$VolumeName = "${projectName}_daaf-data"
if ($env:DAAF_DATA_VOLUME_NAME) { $VolumeName = $env:DAAF_DATA_VOLUME_NAME }
# Second volume: Claude Code state. Restored only when the selected backup
# contains the dedicated subfolder (newer backups); older backups predating the
# volume are restored data-only with a warning.
$ClaudeVolumeName = "${projectName}_daaf-claude-config"
$ClaudeSubDir = ".daaf-claude-config"
# Executable-permission manifest written into the backup root by backup_daaf.ps1
# (see the "Capture the executable-permission manifest" block there). Lists every
# regular file that had the owner-exec bit set at backup time. Restore uses it to
# put POSIX modes back after a Windows round-trip (NTFS) erased them. Absent on
# older backups -- restore handles that gracefully (no normalization; see Step 2d).
$PermissionsManifest = ".daaf-permissions"
# Symlink manifest written into the backup root (and the Claude subfolder root) by
# backup_daaf.ps1's staging step. Lists each symlink's path and target (TAB-
# separated). Restore replays it container-side to recreate the links that the
# staging step stripped so `docker cp` could stream a symlink-free tree on Windows.
# Current backups always contain it (0 bytes when the volume had no symlinks); absent
# only on backups that predate the feature -- restore no-ops then (see Step 2e),
# matching the ".daaf-permissions" "no manifest, no action" rule.
$SymlinksManifest = ".daaf-symlinks"
#
# SYNC NOTE: two container-side programs below cannot use these variables and
# hardcode the literals ".daaf-symlinks", ".daaf-permissions" and ".daaf-claude-config":
# $BackupCountProgram (a single-quoted `@'...'@` here-string, byte-identical to
# backup_daaf.ps1's -- pinned by tests/bash/backup_twin_parity.bats) and the
# post-restore volume count in "--- Verify ---" (a single-quoted string, identical to
# restore_from_backup.sh's -- pinned by the same file). They are kept literal so their
# `find` predicates stay textually identical to the backup's. If a name ever changes,
# update those literals by hand (and backup_daaf.ps1's / the .sh twins' copies).

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI
# cross-platform smoke testing without a Docker daemon.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "run --rm -v *:/b:ro*" {
                # Container-side count of the selected backup folder. Listed first:
                # the argument string holds the user's path, which can contain "info".
                # (The dry run exits before selection; modeled so the parse stays
                # compatible if the early exit ever moves.)
                Write-Output "BACKUP_FILES=42"
                Write-Output "BACKUP_KB=1000"
                Write-Output "BACKUP_SENTINEL=1"
                return
            }
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

# --- Count helpers (byte-identical copies of backup_daaf.ps1's) ---
# Each `function ... { ... }` definition is pinned byte-identical to backup_daaf.ps1's
# by tests/powershell/restore_from_backup.Tests.ps1 (case-sensitive -BeExactly); this
# comment block itself is not pinned. See backup_daaf.ps1 for the full rationale.
# Get-DaafCountMarker reads one NAME=<digits> marker (anchored, TryParse-gated, $null
# when missing). Measure-DaafBackupTree is
# the PowerShell count of a backup folder that is never silent: Windows PowerShell 5.1
# Get-ChildItem cannot descend into a folder whose Windows path is 248+ characters
# unless LongPathsEnabled=1, so its enumeration errors are captured with
# -ErrorVariable and returned, and the caller marks the count as a lower bound. Its
# root exclusions are case-sensitive, like the container's `find -path`.
function Get-DaafCountMarker {
    [CmdletBinding()]
    param(
        [AllowNull()][object[]]$Lines,
        [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$Name
    )
    $value = $null
    $pattern = '^' + [regex]::Escape($Name) + '=(\d+)$'
    foreach ($raw in @($Lines)) {
        foreach ($line in ("$raw" -split "`r?`n")) {
            if ($line.Trim() -match $pattern) {
                $parsed = [long]0
                if ([long]::TryParse($Matches[1], [ref]$parsed)) { $value = $parsed }
            }
        }
    }
    return $value
}

function Measure-DaafBackupTree {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$Root,
        [string[]]$ExcludeRootFiles = @(),
        [string[]]$ExcludeRootDirs = @()
    )
    $rootItem = Get-Item -LiteralPath $Root -Force -ErrorAction SilentlyContinue
    if ($null -eq $rootItem) {
        return [pscustomobject]@{ Files = 0; Bytes = [long]0; KB = [long]0; Errors = 1 }
    }
    $rootFull = $rootItem.FullName.TrimEnd('\', '/')
    $sep = [string][System.IO.Path]::DirectorySeparatorChar
    $enumErrors = $null
    $files = 0
    $bytes = [long]0
    foreach ($item in @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue -ErrorVariable enumErrors)) {
        $rel = $item.FullName.Substring($rootFull.Length + 1)
        if ($ExcludeRootFiles -ccontains $rel) { continue }
        $underExcludedDir = $false
        foreach ($dir in $ExcludeRootDirs) {
            if ($rel.StartsWith($dir + $sep, [System.StringComparison]::Ordinal)) { $underExcludedDir = $true; break }
        }
        if ($underExcludedDir) { continue }
        $files++
        $bytes += $item.Length
    }
    $errorCount = 0
    if ($null -ne $enumErrors) { $errorCount = @($enumErrors).Count }
    return [pscustomobject]@{ Files = $files; Bytes = $bytes; KB = [long][math]::Floor($bytes / 1024); Errors = $errorCount }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/restore_from_backup.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Enable strict mode for real executions only. Set-StrictMode is dynamically
# scoped, so placing it AFTER the DAAF_TEST_MODE guard keeps Pester's dot-sourcing
# (which returns above) from leaking strict mode into the whole test session, while
# every code path a real run reaches is fully protected against uninitialized-variable
# and missing-property reads.
Set-StrictMode -Version 3.0

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
    # Count and size the DATA-volume contents only -- exclude the hidden Claude
    # subfolder (it restores to its own volume, not the data volume) and BOTH root
    # metadata manifests (".daaf-permissions", ".daaf-symlinks" -- neither is restored
    # content). These are the same root-relative exclusions as the "Scanning backup"
    # count below and the backup script's completion report, so they agree with each
    # other and with the post-restore volume count -- EXCEPT that this listing stays on
    # PowerShell for speed (one container scan per listed backup would be slow), and
    # Windows PowerShell 5.1 cannot read folders past the Windows path-length limit.
    # When it hit read errors the count is shown as a lower bound ("72834+ files");
    # the scan of the selected backup below counts inside Docker and is exact. When
    # Claude state is present it is noted inline rather than folded into the number.
    $claudeSub = Join-Path $dir.FullName $ClaudeSubDir
    $listing = Measure-DaafBackupTree -Root $dir.FullName -ExcludeRootFiles @($PermissionsManifest, $SymlinksManifest) -ExcludeRootDirs @($ClaudeSubDir)
    $fileCount = "$($listing.Files)"
    if ($listing.Errors -gt 0) { $fileCount = "$($listing.Files)+" }
    $sizeBytes = $listing.Bytes
    if ($sizeBytes -ge 1073741824) {
        $sizeStr = "{0:N1}G" -f ($sizeBytes / 1073741824)
    } elseif ($sizeBytes -ge 1048576) {
        $sizeStr = "{0:N0}M" -f ($sizeBytes / 1048576)
    } else {
        $sizeStr = "{0:N0}K" -f ($sizeBytes / 1024)
    }
    $hasClaude = (Test-Path -LiteralPath $claudeSub -PathType Container) -and
        (@(Get-ChildItem -LiteralPath $claudeSub -Force -ErrorAction SilentlyContinue).Count -gt 0)
    if ($hasClaude) {
        Write-Host ("  {0}) {1}  ({2} files + Claude state, {3})" -f ($i + 1), $dir.Name, $fileCount, $sizeStr)
    } else {
        Write-Host ("  {0}) {1}  ({2} files, {3})" -f ($i + 1), $dir.Name, $fileCount, $sizeStr)
    }
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

# --- Completion-banner latch ---
# Mirrors backup_daaf.ps1's $HadWarnings: every non-fatal WARNING on the success path
# below (a permission or symlink replay failure, a restored file count that could not
# be verified, a post-restore file-count mismatch, a Claude-state clear, copy or
# symlink-replay failure) sets this so the final banner can say the restore completed
# WITH WARNINGS rather than claiming an unqualified success. The exit status stays 0
# on those paths -- the banner wording is the signal, not the exit code (callers such
# as daaf.ps1 branch on the exit code only). The NOTEs do not latch: a backup that
# predates the permission manifest or the Claude volume restores exactly what it
# holds. Refusals and errors exit nonzero before the banner, so they need no latch.
# This twin also latches a LOWER-BOUND backup count (the PowerShell fallback in the
# scan below hit read errors), as backup_daaf.ps1 does: the post-restore check can
# then show the restore is consistent with the backup but not that it is complete.
# That latch is set before the destructive prompt; a cancelled restore exits before
# the banner. The .sh twin refuses such a backup instead, so it has no such latch.
$HadWarnings = $false

# --- Count source files ---
# Exclude the Claude subfolder from the DATA-volume count -- it is restored to a
# separate volume below, not into the data volume. Also exclude BOTH metadata
# manifests: ".daaf-permissions" (consumed by Step 2d, then removed) and
# ".daaf-symlinks" (consumed by Step 2e, then removed). Neither is restored content,
# so counting them would make this scan disagree with the post-restore verification
# count (which runs after both manifests are stripped from the volume) and with the
# listing count above.
#
# Counted CONTAINER-SIDE through a read-only bind mount -- the authoritative count
# the post-restore verification is compared against. Windows PowerShell 5.1
# Get-ChildItem cannot descend into folders whose Windows path is 248+ characters
# when LongPathsEnabled=0, and with `-ErrorAction SilentlyContinue` that was a quiet
# undercount (field 2026-09-29: 72,834 counted vs 73,021 present), which would then
# show up as a spurious post-restore mismatch against the container `find` below.
# $BackupCountProgram is byte-identical to backup_daaf.ps1's (pinned by
# tests/bash/backup_twin_parity.bats), which documents it: root-relative exclusions
# (the three above), one traversal for files and KB, a BACKUP_SENTINEL line, and
# BACKUP_COUNT_ERRORS in place of the count when its `find` hit read errors (a
# pipeline's status is awk's, so an error would otherwise print a short count and
# exit 0). A count with errors is unavailable here too: the PowerShell count runs.
# Restore does NOT require that sentinel -- backups that predate the ".daaf-symlinks"
# manifest have none. Instead it treats a container count of 0 as UNAVAILABLE: Docker
# Desktop has been reported to present an EMPTY folder for a bind mount of some
# locations (a non-C:, USB or network drive; docker/for-win#14271, not reproduced
# here), which would otherwise show "Found 0 files" in the destructive prompt below.
# On 0 the PowerShell count runs; a genuinely empty backup then reads 0 there too,
# silently, while a folder Docker could not see gets a note. The restore copy itself
# is unaffected (`docker cp` streams through the Docker API, not a bind mount). The
# path is one direct-invocation argument ("<path>:/b:ro"), so a spaced folder stays
# one argument and never ends in a backslash. Fallback: the PowerShell count, with
# read errors shown as a lower bound rather than hidden.
$BackupCountProgram = @'
set -e
cd /b
: > /tmp/count_err
seen=0
if test -e ./.daaf-symlinks; then seen=1; fi
counts=$(find . -type f ! -path ./.daaf-symlinks ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | awk \{n++\;s+=\$1\}\ END\ \{print\ n+0,int\(s/1024\)\})
if test -s /tmp/count_err; then
echo BACKUP_COUNT_ERRORS=$(grep -c ^ /tmp/count_err)
else
echo BACKUP_FILES=${counts% *}
echo BACKUP_KB=${counts#* }
fi
echo BACKUP_SENTINEL=$seen
'@
Write-Host ""
Write-Host "Scanning backup..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ScanCountOutput = @(docker run --rm -v "${SelectedPath}:/b:ro" busybox sh -c $BackupCountProgram 2>&1)
$scanCountExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
$TotalFiles = $null
$TotalSizeKB = $null
$ScanCountErrors = $null
if ($scanCountExit -eq 0) {
    $TotalFiles = Get-DaafCountMarker -Lines $ScanCountOutput -Name 'BACKUP_FILES'
    $TotalSizeKB = Get-DaafCountMarker -Lines $ScanCountOutput -Name 'BACKUP_KB'
    $ScanCountErrors = Get-DaafCountMarker -Lines $ScanCountOutput -Name 'BACKUP_COUNT_ERRORS'
}
$TotalFilesLabel = ""
$TotalFilesIsLowerBound = $false
if ($null -ne $TotalFiles -and $null -ne $TotalSizeKB -and $TotalFiles -gt 0) {
    $TotalSizeBytes = $TotalSizeKB * 1024
    $TotalFilesLabel = "$TotalFiles"
} else {
    # 0 from a successful container count is "Docker saw nothing" -- possibly an
    # empty bind-mount view -- so it is treated as unavailable, like a failed count.
    $ContainerSawNothing = ($null -ne $TotalFiles -and $null -ne $TotalSizeKB)
    $ScanFallback = Measure-DaafBackupTree -Root $SelectedPath -ExcludeRootFiles @($PermissionsManifest, $SymlinksManifest) -ExcludeRootDirs @($ClaudeSubDir)
    if ($null -ne $ScanCountErrors -and $ScanCountErrors -gt 0) {
        Write-Host "Note: Docker hit $ScanCountErrors read error(s) while counting this backup, so it is counted" -ForegroundColor Yellow
        Write-Host "      with PowerShell instead."
    } elseif (-not $ContainerSawNothing) {
        Write-Host "Note: Could not count the backup inside Docker (exit $scanCountExit); counting it with" -ForegroundColor Yellow
        Write-Host "      PowerShell instead."
    } elseif ($ScanFallback.Files -gt 0 -or $ScanFallback.Errors -gt 0) {
        Write-Host "Note: Docker could not see the files in this backup folder, so they are counted with" -ForegroundColor Yellow
        Write-Host "      PowerShell instead. (Docker Desktop can show an empty folder for some locations,"
        Write-Host "      such as a USB, network, or non-C: drive. The restore copy itself is not affected.)"
    }
    $TotalFiles = $ScanFallback.Files
    $TotalSizeBytes = $ScanFallback.Bytes
    $TotalFilesLabel = "$TotalFiles"
    if ($ScanFallback.Errors -gt 0) {
        $TotalFilesIsLowerBound = $true
        $TotalFilesLabel = "$TotalFiles+"
        Write-Host "Note: PowerShell could not read $($ScanFallback.Errors) folder(s) or file(s) in this backup," -ForegroundColor Yellow
        Write-Host "      most likely because of the Windows path-length limit, so the count below is a"
        Write-Host "      LOWER BOUND. The restore itself copies everything (Docker handles long paths);"
        Write-Host "      the post-restore check may then report more files than this count."
        $HadWarnings = $true
    }
}
if ($TotalSizeBytes -ge 1073741824) {
    $TotalSizeStr = "{0:N1}G" -f ($TotalSizeBytes / 1073741824)
} elseif ($TotalSizeBytes -ge 1048576) {
    $TotalSizeStr = "{0:N0}M" -f ($TotalSizeBytes / 1048576)
} else {
    $TotalSizeStr = "{0:N0}K" -f ($TotalSizeBytes / 1024)
}
Write-Host "Found $TotalFilesLabel files ($TotalSizeStr) to restore."

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
Write-Host "Source:      $SelectedName\ ($TotalFilesLabel files, $TotalSizeStr)"
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

# Step 2d: replay executable permissions from the manifest. The manifest
# ("$PermissionsManifest") was copied into the volume by the whole-folder
# `docker cp` above. When it is PRESENT, normalize every regular file to 0644 and
# re-apply 0755 to exactly the paths it lists -- undoing the mode loss the NTFS
# round-trip inflicts (where `docker cp` fabricates 0755 for every file and git
# then flags every tracked 0644 file as a spurious 100644->100755 change).
#
# SAFETY RULE -- no manifest, no normalization: when the manifest is ABSENT (older
# backups, OR a manifest whose write failed at backup time), do NOTHING. A blanket
# 0644 without the manifest would strip exec from every script and hook and make
# matters worse than the fabricated 0755. The manifest's presence is the signal for
# "these files should be executable, everything else 0644"; without it there is no
# safe baseline. Replay failure is a WARNING (data is intact), never fatal.
#
# Trailing CR (WriteAllLines emits CRLF on Windows) and a leading UTF-8 BOM are both
# stripped as parameter-expansion suffix/prefix (`${p%`$cr} / `${p#`$bom}), NOT with
# sed: busybox sed has no \xNN hex escapes, so a `sed 1s/^\xef\xbb\xbf//` would match
# those bytes literally and silently do nothing. The BOM bytes are derived once via
# octal `printf '\357\273\277'` (portable) and removed only as a leading prefix --
# never with `tr -d`, which would also delete them where they legitimately appear
# inside multi-byte UTF-8 filenames. The `[ -e ... ] && chmod` on a missing path does
# NOT trip `set -e`: a non-final command in an AND-OR list is exempt from errexit per
# POSIX, so a manifest path absent from this backup is skipped, not fatal.
#
# Windows quoting: the `sh -c` program reaches docker.exe as a single command-line
# string, so it must contain NO embedded double-quotes (they get re-parsed by the
# Windows C runtime and silently mangle the argument -- see shell-scripting
# gotchas.md). This is a PS double-quoted outer string using sh single-quotes
# throughout; sh variables are backtick-escaped (`$p, `$manifest, `$cr, `$bom) so
# PowerShell does not interpolate them, and $PermissionsManifest (a fixed constant,
# no user input) IS interpolated by PowerShell to build the container path.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker run --rm -v "${VolumeName}:/dest:ro" busybox test -f "/dest/${PermissionsManifest}" 2>&1
$manifestPresent = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if ($manifestPresent) {
    Write-Host "Restoring executable permissions from $PermissionsManifest..."
    $replayScript = "set -e; manifest=/dest/$PermissionsManifest; find /dest -type f -exec chmod 644 {} +; cr=`$(printf '\r'); bom=`$(printf '\357\273\277'); while IFS= read -r p; do p=`${p%`$cr}; p=`${p#`$bom}; [ -z `$p ] && continue; [ -e /dest/`$p ] && chmod 755 /dest/`$p; done < `$manifest; rm -f `$manifest"
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $null = docker run --rm -v "${VolumeName}:/dest" busybox sh -c $replayScript 2>&1
    $replayOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $savedEAP
    if (-not $replayOk) {
        Write-Host "WARNING: Could not fully replay executable permissions." -ForegroundColor Yellow
        Write-Host "         Your data was restored intact; only file permissions may be off."
        Write-Host "         If git reports many files as changed by mode only, or a script"
        Write-Host "         will not run, repair with: chmod +x <file> inside the container."
        $HadWarnings = $true
    }
} else {
    Write-Host "NOTE: No $PermissionsManifest manifest found in this backup (it may predate"
    Write-Host "      permission preservation, or the manifest write may have failed during"
    Write-Host "      backup). File permissions were left as-is -- no normalization was applied."
}

# Step 2e: replay symlinks from the manifest. The symlink manifest
# ("$SymlinksManifest") was copied into the volume by the whole-folder `docker cp`
# above. backup_daaf.ps1's staging step stripped every symlink from the tree (so
# `docker cp` could stream a symlink-free archive that does not abort on Windows)
# and recorded each link's path + target here, TAB-separated. When the manifest is
# PRESENT, recreate each link, chown it to appuser (-h: the link, not its target),
# then remove the manifest from the volume.
#
# SAFETY / no manifest, no action: when the manifest is ABSENT (older backups, a
# volume with no symlinks, or a manifest whose write failed at backup time), do
# NOTHING -- matching the $PermissionsManifest rule. Replay failure is a WARNING
# (regular files are intact; such links are typically regenerable), never fatal.
#
# Windows quoting: the `sh -c` program reaches docker.exe as a single command-line
# string, so it must contain NO embedded double-quotes (they get re-parsed by the
# Windows C runtime and silently mangle the argument -- see shell-scripting
# gotchas.md). Unquoted sh expansions are exact because of `set -f` (no globbing) +
# an empty global IFS (no word splitting); the `IFS=$tab` prefix scopes field
# splitting to the `read` alone. Trailing CR / leading BOM are stripped as parameter-
# expansion suffix/prefix (never `tr -d`); the BOM is derived via octal printf
# (busybox sed has no \xNN escapes). This is a PS double-quoted outer string using
# sh single-quotes throughout; sh variables are backtick-escaped (`$p, `$t, `$cr,
# `$bom, `$tab) so PowerShell does not interpolate them, and $SymlinksManifest (a
# fixed constant, no user input) IS interpolated by PowerShell to build the path.
#
# Double backslashes (\\r, \\357...) so the sh that runs this program receives a
# SINGLE backslash after its own unquoted-backslash processing, which printf then
# interprets as the escape. A single backslash here would be eaten by sh before
# printf sees it (yielding literal digits, not the byte) -- verified against the
# busybox/ash + dash behavior; this mirrors the .sh twin's `printf \\357...`.
#
# Defined UNCONDITIONALLY (before the manifest probe) so the Claude-volume replay
# below can reuse it even when the DATA volume had no symlink manifest -- otherwise
# a strict-mode read of an unset variable would throw. Building the string is a
# harmless no-op when no manifest is present. Both replay call sites (data volume
# here, Claude volume in the "Restore the Claude Code state volume" block) run the
# SAME program against their own `/dest`.
$symlinkReplayScript = "set -ef; IFS=; cr=`$(printf \\r); bom=`$(printf \\357\\273\\277); tab=`$(printf \\t); while IFS=`$tab read -r p t; do p=`${p#`$bom}; t=`${t%`$cr}; [ -z `$p ] && continue; [ -z `$t ] && continue; ln -sf -- `$t /dest/`$p; chown -h 1000:1000 /dest/`$p; done < /dest/$SymlinksManifest; rm -f /dest/$SymlinksManifest"
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker run --rm -v "${VolumeName}:/dest:ro" busybox test -f "/dest/${SymlinksManifest}" 2>&1
$symlinkManifestPresent = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if ($symlinkManifestPresent) {
    Write-Host "Restoring symlinks from $SymlinksManifest..."
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $null = docker run --rm -v "${VolumeName}:/dest" busybox sh -c $symlinkReplayScript 2>&1
    $symlinkReplayOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $savedEAP
    if (-not $symlinkReplayOk) {
        Write-Host "WARNING: Could not fully replay symlinks from the manifest." -ForegroundColor Yellow
        Write-Host "         Your data was restored intact; only symbolic links may be missing."
        Write-Host "         Such links are usually regenerable (e.g. by re-running the step that"
        Write-Host "         created them). Inspect $SymlinksManifest in the backup for the list."
        $HadWarnings = $true
    }
}
Write-Host "Copy complete."
Write-Host ""

# --- Verify ---
# Count the restored volume like with like: the same root exclusions as the backup
# count above (a root ".daaf-symlinks"/".daaf-permissions" left behind when a manifest
# replay failed, and the ".daaf-claude-config" subtree), and one `stat` line per file
# so a name holding a newline counts once. Quote-free (Windows argv), and textually
# identical to restore_from_backup.sh's program (tests/bash/backup_twin_parity.bats).
Write-Host "Verifying restore..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$VerifyOutput = @(docker run --rm -v "${VolumeName}:/dest:ro" busybox sh -c 'set -e; : > /tmp/count_err; n=$(find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | wc -l); if test -s /tmp/count_err; then echo RESTORED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err); else echo RESTORED_FILES=$((n)); fi' 2>&1)
$verifyExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
# Markers, not a bare number: the old `2>&1` + TryParse of the whole output turned any
# stderr line into a failed parse, i.e. a false "0 files found" ERROR. The program
# prints RESTORED_FILES only when its count's stderr was empty (the same F1 pattern as
# $BackupCountProgram), else RESTORED_COUNT_ERRORS. Unavailable ($null) is its own
# outcome: a WARNING with exit 0, because the copy, ownership repair and replays all
# succeeded and only this check could not run (exit 1 would tell a caller the restore
# failed with the data in place). A count that WAS read as 0 still fails with exit 1.
# Parsed on ANY exit, exactly like the .sh twin: an error marker is evidence of read
# errors even when docker also exited nonzero, and it takes precedence in choosing the
# WARNING variant below. A count marker is trusted only on exit 0 (a nonzero exit means
# the count did not run cleanly), so both twins print the same variant for one input.
$RestoredCount = Get-DaafCountMarker -Lines $VerifyOutput -Name 'RESTORED_FILES'
$RestoredErrors = Get-DaafCountMarker -Lines $VerifyOutput -Name 'RESTORED_COUNT_ERRORS'
if ($verifyExit -ne 0) { $RestoredCount = $null }
# The completion report's "Files:" value (identical wording in the .sh twin).
$RestoredLabel = "$RestoredCount files in volume"

if ($null -eq $RestoredCount) {
    $RestoredLabel = "not verified (the restored file count could not be read)"
    Write-Host ""
    if ($null -ne $RestoredErrors) {
        Write-Host "WARNING: Could not verify the restored file count: Docker hit $RestoredErrors read error(s)" -ForegroundColor Yellow
        Write-Host "         while counting the restored volume."
    } else {
        Write-Host "WARNING: Could not verify the restored file count (the count inside Docker did not" -ForegroundColor Yellow
        Write-Host "         run cleanly, exit $verifyExit)."
    }
    Write-Host "         The copy itself reported success, so your data is most likely in place. Start"
    Write-Host "         DAAF and check your files; if anything is missing, re-run this restore."
    $HadWarnings = $true
} elseif ($RestoredCount -eq 0) {
    Write-Host ""
    Write-Host "ERROR: Verification failed -- 0 files found in restored volume." -ForegroundColor Red
    Write-Host "The restore may have failed. Consider re-running or reinstalling DAAF."
    Wait-AndExit 1
} else {
    Write-Host "Verified: $RestoredCount files in restored volume."
}

# --- File count comparison ---
# When the backup count is a LOWER BOUND (the PowerShell fallback could not read some
# folders), a restored volume holding at least that many files is exactly what is
# expected -- the restore copies everything, and `find` inside Docker sees it all --
# so it gets an informational line, not a "may be incomplete" warning. Only a
# restored count BELOW the lower bound is a real mismatch. (The banner still ends
# WITH WARNINGS: the scan latched it, because a lower bound cannot prove the restore
# complete.)
if ($null -ne $RestoredCount -and $TotalFiles -gt 0 -and $RestoredCount -gt 0) {
    if ($TotalFilesIsLowerBound -and $RestoredCount -ge $TotalFiles) {
        Write-Host "Note: The backup count ($TotalFilesLabel files) was a lower bound; the restored volume holds"
        Write-Host "      $RestoredCount files, which is consistent with it."
    } else {
        $Diff = [math]::Abs($TotalFiles - $RestoredCount)
        $Tolerance = [math]::Max(1, [math]::Floor($TotalFiles / 100))
        if ($Diff -gt $Tolerance) {
            Write-Host ""
            Write-Host "WARNING: File count mismatch." -ForegroundColor Yellow
            Write-Host "         Backup: $TotalFilesLabel files, Restored: $RestoredCount files (difference: $Diff)"
            Write-Host "         The restore may be incomplete."
            $HadWarnings = $true
        }
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
    # Pre-init the full guard set (not just $claudeCopyOk) so a strict-mode read
    # is safe even if a docker step throws before its own assignment.
    $claudeCopyOk = $false
    $claudeCreateOk = $false
    $claudeCpOk = $false
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
                    if ($claudeCopyOk) {
                        # Replay the Claude volume's own symlink manifest (staged out
                        # by backup), then strip it. Same $symlinkReplayScript program
                        # + no-manifest-no-op + WARNING-not-fatal semantics as the
                        # data-volume Step 2e. The manifest copied into this volume's
                        # root as /dest/.daaf-symlinks. Replay failure must NOT flip
                        # $claudeCopyOk to false (the state itself restored fine).
                        $null = docker run --rm -v "${ClaudeVolumeName}:/dest:ro" busybox test -f "/dest/${SymlinksManifest}" 2>&1
                        if ($LASTEXITCODE -eq 0) {
                            $null = docker run --rm -v "${ClaudeVolumeName}:/dest" busybox sh -c $symlinkReplayScript 2>&1
                            if ($LASTEXITCODE -ne 0) {
                                Write-Host "WARNING: Could not fully replay Claude state symlinks." -ForegroundColor Yellow
                                Write-Host "         Claude state was restored; only symbolic links may be missing."
                                $HadWarnings = $true
                            }
                        }
                    }
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
        $HadWarnings = $true
    } elseif (-not $claudeCopyOk) {
        Write-Host "WARNING: Failed to restore the Claude Code state volume." -ForegroundColor Yellow
        Write-Host "         Data volume restore above succeeded; you may need to re-run /login."
        $HadWarnings = $true
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
if ($HadWarnings) {
    Write-Host "  Restore completed WITH WARNINGS -- verify before relying on it"
} else {
    Write-Host "  Restore complete!"
}
Write-Host "=========================================="
Write-Host ""
Write-Host "Restored: $SelectedName"
Write-Host "Files:    $RestoredLabel"
Write-Host ""
Write-Host "You can now start DAAF with:"
Write-Host "  .\run_daaf.ps1"
Write-Host ""
Wait-AndExit 0
