# ============================================================================
# DAAF Backup Utility (Windows PowerShell)
# ============================================================================
# Creates a timestamped backup of your DAAF Docker volume on the host.
#
# Usage:
#   cd daaf-docker
#   .\backup_daaf.ps1
#
# Backups are created in the current directory with date-versioned names:
#   2026-04-21_daaf_backup\     (first backup of the day)
#   2026-04-21a_daaf_backup\    (second backup)
#   2026-04-21b_daaf_backup\    (third backup)
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
            "run -d*" {
                # Staging container launch (symlink strip) -- emit a fake CID.
                Write-Output "stagecid0000"
                return
            }
            "wait*" { Write-Output "0"; return }
            "*run --rm*" {
                # Scan command -- return 4 lines matching the parsing expectations:
                # Line 0: file count, Line 1: "KB\t/source", Line 2: "size\t/source", Line 3: logical KB
                Write-Output "42"
                Write-Output "1024`t/source"
                Write-Output "1.0M`t/source"
                Write-Output "1000"
                return
            }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }
}

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# process environment so the volume name below reflects DAAF_PROJECT_NAME. This
# script operates on the Docker volume via raw `docker run`/`docker volume` (not
# `docker compose`), so compose interpolation does not apply -- we must derive the
# project-prefixed volume name ourselves. Canonical shared pattern (kept in sync
# with Import-DaafSettingsFile in daaf_lib.ps1); standalone scripts that do NOT
# dot-source daaf_lib.ps1 inline it. Parse only these four keys (never
# dot-source -- the file holds API keys); process env wins; absent file = no-op;
# CR stripped; PS 5.1 safe.
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

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/backup_daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Enable strict mode for real executions only. Set-StrictMode is dynamically
# scoped, so placing it AFTER the DAAF_TEST_MODE guard keeps Pester's dot-sourcing
# (which returns above) from leaking strict mode into the whole test session, while
# every code path a real run reaches is fully protected against uninitialized-variable
# and missing-property reads.
Set-StrictMode -Version 3.0

# --- Configuration ---
# The Docker named volume is project-prefixed: "<project>_daaf-data". Compose
# derives the prefix from the project name (default "daaf"), so a second instance
# with DAAF_PROJECT_NAME=daaf2 owns the volume "daaf2_daaf-data". Default unset =>
# "daaf_daaf-data" (byte-for-byte identical to the previous hardcoded value).
$projectName = "daaf"
if ($env:DAAF_PROJECT_NAME) { $projectName = $env:DAAF_PROJECT_NAME }
$VolumeName = "${projectName}_daaf-data"
# Second volume: Claude Code state (auth/credentials, session history and
# transcripts, plugins, ~/.claude.json). Backed up into a dedicated hidden
# subfolder of the backup so it does not contaminate the data-volume file counts
# (which scan the backup root). May not exist on very old installs that predate
# the volume -- handled gracefully below.
$ClaudeVolumeName = "${projectName}_daaf-claude-config"
$ClaudeSubDir = ".daaf-claude-config"
# Symlink manifest: backup-root sibling of .daaf-permissions. On Windows hosts,
# `docker cp` extraction ABORTS the moment it hits a symlink it cannot create
# (symlink creation needs admin/Developer Mode), silently dropping every file that
# sorts after it in the archive stream. To make backups symlink-safe, the volume is
# first STAGED into a throwaway container: the staging step records each symlink's
# path+target into this manifest and then removes the symlinks, so the tree
# `docker cp` streams contains NO symlinks. Restore replays the manifest to
# recreate the links. Absent manifest (older backup, or a volume with no symlinks)
# = no-op on restore, matching the ".daaf-permissions" "no manifest, no action" rule.
#
# SYNC NOTE: the container-side $StageProgram here-string below is single-quoted
# (`@'...'@`), so it CANNOT interpolate this variable -- it hardcodes the literal
# ".daaf-symlinks" (in the `paste ... > /staging/.daaf-symlinks` line). If this
# manifest name ever changes, update the here-string literal by hand to match.
# (The .sh twin interpolates ${SYMLINKS_MANIFEST} into its single-quoted program via
# a quote break, so it needs no such manual sync.)
$SymlinksManifest = ".daaf-symlinks"
$Today = Get-Date -Format "yyyy-MM-dd"

Write-Host ""
Write-Host "=========================================="
Write-Host "  DAAF Backup"
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

# --- Generate date-versioned backup name ---
$BackupName = "${Today}_daaf_backup"

if (Test-Path $BackupName) {
    # First backup of the day already exists -- find next available suffix
    $SuffixNum = 0
    while ($true) {
        $Suffix = [char](97 + $SuffixNum)  # 0=a, 1=b, 2=c, ...
        $BackupName = "${Today}${Suffix}_daaf_backup"
        if (-not (Test-Path $BackupName)) { break }
        $SuffixNum++
        if ($SuffixNum -ge 26) {
            Write-Host "ERROR: Too many backups for today (26 max). Please remove some old backups." -ForegroundColor Red
            Wait-AndExit 1
        }
    }
}

Write-Host "Backup name: $BackupName\"
Write-Host ""

# --- Count source files ---
Write-Host "Scanning Docker volume..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ScanOutput = docker run --rm -v "${VolumeName}:/source:ro" busybox sh -c "find /source -type f | wc -l && du -sk /source && du -sh /source && find /source -type f -exec stat -c %s {} + | awk '{s+=`$1} END {print int(s/1024)}'"
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not scan Docker volume." -ForegroundColor Red
    Wait-AndExit 1
}
$TotalFiles = [int]($ScanOutput[0].Trim())
$VolumeSizeKB = [long](($ScanOutput[1].Trim() -split '\s+')[0])
$TotalSize = ($ScanOutput[2].Trim() -split '\s+')[0]
$VolumeLogicalKB = [long]($ScanOutput[3].Trim())
Write-Host "Found $TotalFiles files to copy ($TotalSize)."
Write-Host ""

# --- Disk space pre-check ---
# This checks free space on the HOST drive where the backup folder lands. Note it
# does NOT cover the staging step's transient cost: staging `cp -a /source /staging`
# inside the throwaway container roughly DOUBLES the volume's footprint on the Docker
# VM's own internal disk (the Docker Desktop disk image), which is invisible to this
# host-drive check. If that internal disk is full, staging fails and the fatal
# staging-failure error below points the user at the Docker Desktop disk image.
$BackupDrive = (Get-Item -Path ".").PSDrive.Name
$DriveInfo = New-Object System.IO.DriveInfo($BackupDrive)
$AvailableKB = [long]($DriveInfo.AvailableFreeSpace / 1024)
# Add 10% buffer to account for filesystem overhead
$RequiredKB = [long]($VolumeSizeKB * 110 / 100)
if ($AvailableKB -lt $RequiredKB) {
    $RequiredMB = [math]::Floor($RequiredKB / 1024)
    $AvailableMB = [math]::Floor($AvailableKB / 1024)
    Write-Host "ERROR: Insufficient disk space for backup." -ForegroundColor Red
    Write-Host "       Required: ~${RequiredMB} MB (includes 10% buffer), Available: ${AvailableMB} MB"
    Wait-AndExit 1
}

# --- Dry-run early exit ---
# The mock copy creates no files, so verification would fail. Exit cleanly
# after confirming scan parsing works.
if ($env:DAAF_DRY_RUN -eq "1") {
    Write-Host "[DRY-RUN] Would copy $TotalFiles files ($TotalSize) to $BackupName\"
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Backup dry-run complete!"
    Write-Host "=========================================="
    Write-Host ""
    Wait-AndExit 0
}

# --- Create backup ---
New-Item -ItemType Directory -Path $BackupName -Force | Out-Null
$HostPath = (Resolve-Path $BackupName).Path

# Copy the data volume out via a STAGING container + `docker cp`, instead of
# `docker cp`ing the volume directly. On Windows hosts, `docker cp`'s host-side
# extraction ABORTS the instant it meets a symlink it cannot create (symlink
# creation needs admin/Developer Mode), silently truncating the archive stream and
# dropping every file that sorts after the failing link. To make the tree
# `docker cp` streams symlink-free, first stage the volume into a throwaway busybox
# container: `cp -a /source /staging` freezes the tree, two `find` passes record
# each symlink's path and target line-for-line (identical traversal order, so
# `paste` pairs them exactly -- the `cp -a` freeze is a correctness requirement,
# not an optimization) into the ".daaf-symlinks" manifest at the staging root, and
# `find -type l -exec rm` strips the links. Restore replays the manifest.
#
# The staging program contains NO embedded double quotes -- embedded double quotes
# corrupt Windows arg parsing on PS 5.1. Its /tmp writes are inside the throwaway
# container's own layer (NOT the DAAF container's /tmp), so no provenance concern.
# It is passed as a single array-form ArgumentList element (robust quoting), the
# same way the docker cp path below passes $HostPath.
#
# FATAL unsupported-character gate (twin of backup_daaf.sh): the ".daaf-symlinks"
# manifest is a line-based, TAB-separated "path<TAB>target" file, and restore replays
# it by splitting each line on the first tab. A TAB in a symlink's own path or target
# shifts that field boundary (restore parses the wrong path/target); a NEWLINE in a
# name splits one logical entry across lines, which also desyncs `paste` (it pairs
# path line N with target line N) for every entry after it. Neither is detectable at
# restore time, so gate HERE, loudly: a newline-immune true link count is
# `find . -type l -exec printf x ;` (one x per link, `wc -c`); if either `wc -l` of
# link_paths/link_targets disagrees, a name holds a newline. A literal tab is caught
# by `grep -qf` against a one-tab pattern file. Any hit exits 3, which trips the fatal
# staging-failure path below -- NO corrupt manifest is written. On a hit the gate
# first NAMES the offenders to stderr before `exit 3`: the tab branch prints the
# matching lines (`grep -f` without `-q`); the newline branch prints the whole
# (typically short) symlink path list, since mismatched line counts cannot isolate
# the culprit. The driver relays that stderr via `docker logs` on the failure path
# below (the staging container is detached, so its output would otherwise be lost).
# This here-string is a SINGLE-quoted (`@'...'@`) literal, so its bytes reach the
# container `sh` verbatim; the `\\011` DOUBLE backslash therefore survives to hand
# printf ONE backslash (the same octal-escape trap the .sh twin and the restore-replay
# `\\357` idiom hit). The new echo/cat/grep lines add no printf escapes and stay
# quote-free for twin parity.
$StageProgram = @'
set -e
cp -a /source /staging
cd /staging
find . -type l > /tmp/link_paths
find . -type l -exec readlink {} \; > /tmp/link_targets
printf \\011 > /tmp/tab_pat
true_links=$(find . -type l -exec printf x \; | wc -c)
path_lines=$(wc -l < /tmp/link_paths)
target_lines=$(wc -l < /tmp/link_targets)
if [ $true_links -ne $path_lines ] || [ $true_links -ne $target_lines ]; then
echo STAGE_ERR_NEWLINE >&2
echo One of these symlink names embeds a newline -- rename or remove the offending link: >&2
cat /tmp/link_paths >&2
exit 3
fi
if grep -qf /tmp/tab_pat /tmp/link_paths || grep -qf /tmp/tab_pat /tmp/link_targets; then
echo STAGE_ERR_TAB >&2
echo These symlink paths or targets embed a tab -- rename or remove the offending link: >&2
grep -f /tmp/tab_pat /tmp/link_paths >&2 || true
grep -f /tmp/tab_pat /tmp/link_targets >&2 || true
exit 3
fi
paste /tmp/link_paths /tmp/link_targets > /staging/.daaf-symlinks
find /staging -type l -exec rm -f {} +
'@

Write-Host "Preparing volume snapshot (staging + symlink strip)... (this may take a while for large volumes)"
# Launch the staging container detached and wait for it. `docker run -d` returns a
# CID; `docker wait` blocks until the staging program finishes and prints its exit
# status, which MUST be checked -- a nonzero status means staging failed before any
# host bytes were written, so the backup aborts fatally (nothing useful produced).
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$StageCid = (docker run -d -v "${VolumeName}:/source:ro" busybox sh -c $StageProgram 2>&1 | Select-Object -Last 1)
if ($null -ne $StageCid) { $StageCid = "$StageCid".Trim() }
$stageStartOk = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrEmpty($StageCid))
$ErrorActionPreference = $savedEAP
if (-not $stageStartOk) {
    if (-not [string]::IsNullOrEmpty($StageCid)) {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $null = docker rm -f $StageCid 2>&1
        $ErrorActionPreference = $savedEAP
    }
    Write-Host "ERROR: Could not start the staging container for a symlink-safe backup." -ForegroundColor Red
    Wait-AndExit 1
}
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$StageStatusRaw = (docker wait $StageCid 2>&1 | Select-Object -Last 1)
$ErrorActionPreference = $savedEAP
$StageStatus = 1
if ($null -ne $StageStatusRaw) { $null = [int]::TryParse("$StageStatusRaw".Trim(), [ref]$StageStatus) }
if ($StageStatus -ne 0) {
    # The staging container is DETACHED (`docker run -d`), so the gate's stderr --
    # including the offender list it now prints on an exit-3 -- went to the container
    # log, NOT this terminal. Fetch and show that log BEFORE `docker rm -f` removes
    # the container (order matters). Best-effort: a `docker logs` failure must not
    # mask the original staging error.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $StageLog = (docker logs $StageCid 2>&1 | Out-String)
    $null = docker rm -f $StageCid 2>&1
    $ErrorActionPreference = $savedEAP
    Write-Host "ERROR: Failed to stage the Docker volume for a symlink-safe backup (exit $StageStatus)." -ForegroundColor Red
    Write-Host "       No backup files were written."
    if (-not [string]::IsNullOrWhiteSpace($StageLog)) {
        Write-Host ""
        Write-Host "Details from the staging scan:"
        foreach ($logLine in ($StageLog -split "`r?`n")) {
            if ($logLine -ne "") { Write-Host "       $logLine" }
        }
        Write-Host ""
    }
    Write-Host "       Exit 3 means a symlink's path or target contains an unsupported"
    Write-Host "       character (a TAB or a NEWLINE), which would corrupt the symlink"
    Write-Host "       manifest -- rename or remove the offending symbolic link named above"
    Write-Host "       and re-run."
    Write-Host "       Otherwise, staging can also fail if the Docker Desktop disk image is"
    Write-Host "       full (staging transiently duplicates the volume inside it); check"
    Write-Host "       Docker Desktop for errors, free space, and re-run."
    Wait-AndExit 1
}

Write-Host "Copying files from Docker volume..."
Write-Host "  Progress: 0 / $TotalFiles files (0%)" -NoNewline

# Array-form ArgumentList: each element is quoted robustly by PowerShell, so a
# $HostPath containing parentheses or ampersands (e.g. OneDrive-style folders)
# cannot silently corrupt the single-string parse that an embedded-quote form
# risks on PS 5.1. Source is the staged (symlink-free) tree, not the volume.
$CopyProcess = Start-Process -FilePath "docker" `
    -ArgumentList @("cp", "${StageCid}:/staging/.", $HostPath) `
    -NoNewWindow -PassThru

try {
    while (-not $CopyProcess.HasExited) {
        Start-Sleep -Seconds 3
        if ($CopyProcess.HasExited) { break }
        $Copied = @(Get-ChildItem -Path $BackupName -Recurse -File -Force -ErrorAction SilentlyContinue).Count
        if ($TotalFiles -gt 0) {
            $Percent = [math]::Min(100, [math]::Floor($Copied * 100 / $TotalFiles))
        } else {
            $Percent = 0
        }
        Write-Host "`r  Progress: $Copied / $TotalFiles files ($Percent%)   " -NoNewline
    }
} finally {
    if (-not $CopyProcess.HasExited) {
        Stop-Process -Id $CopyProcess.Id -Force -ErrorAction SilentlyContinue
    }
    # Remove the staging container. Best-effort: the copy is already done (or was
    # interrupted), so a failure here must never fail the backup.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $null = docker rm -f $StageCid 2>&1
    $ErrorActionPreference = $savedEAP
}

# Block until the copy process is fully gone and read its exit code exactly once.
# (Stop-Process in the finally above, if it fired, leaves the process exiting;
# WaitForExit here settles it before we trust ExitCode.)
$CopyProcess.WaitForExit()
$CopyExitCode = if ($null -ne $CopyProcess.ExitCode) { $CopyProcess.ExitCode } else { 0 }

# --- Verify ---
# The staged tree the copy streamed = volume regular files + 1 symlink manifest
# - symlinks. Symlinks were never counted by the source scan (TotalFiles), and the
# manifest is metadata, not volume content -- so exclude the manifest here to keep
# the copied count aligned with TotalFiles.
$FileCount = @(Get-ChildItem -Path $BackupName -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne $SymlinksManifest }).Count

# Print the ACTUAL final host-side count, not a fabricated "100%". On a truncated
# copy (the Windows symlink-abort this staging step now prevents, or any other
# partial copy) an unconditional "100%" would lie about completeness.
if ($TotalFiles -gt 0) {
    $FinalPercent = [math]::Min(100, [math]::Floor($FileCount * 100 / $TotalFiles))
} else {
    $FinalPercent = 0
}
Write-Host "`r  Progress: $FileCount / $TotalFiles files ($FinalPercent%)   "

if ($FileCount -eq 0) {
    Write-Host ""
    if ($CopyExitCode -ne 0) {
        Write-Host "ERROR: Backup failed (exit code $CopyExitCode). Check Docker Desktop for errors." -ForegroundColor Red
    } else {
        Write-Host "WARNING: Backup completed but 0 files were copied." -ForegroundColor Yellow
        Write-Host "The Docker volume may be empty. Is DAAF properly installed?"
    }
    Write-Host "Location: $HostPath\"
    Wait-AndExit 1
}

if ($CopyExitCode -ne 0) {
    Write-Host "Note: File copy reported warnings (exit code $CopyExitCode); $FileCount of $TotalFiles expected files were transferred." -ForegroundColor Yellow
}

# --- File-count verification ---
# Do NOT trust docker cp's exit code as the sole failure signal: the Windows
# symlink-abort truncation surfaced with a ZERO exit on the user's run. Compare the
# copied data-file count (manifest excluded) against the source scan count and warn
# loudly on a shortfall beyond a 1% tolerance -- the count and size checks are the
# authoritative completeness signals, not $CopyExitCode.
if ($TotalFiles -gt 0 -and $FileCount -gt 0) {
    $CountTolerance = [math]::Max(1, [long]($TotalFiles / 100))
    $CountDiff = [math]::Abs($TotalFiles - $FileCount)
    if ($CountDiff -gt $CountTolerance) {
        Write-Host ""
        Write-Host "WARNING: Backup file-count mismatch." -ForegroundColor Yellow
        Write-Host "         Source: $TotalFiles files, Backup: $FileCount files (difference: $CountDiff)"
        Write-Host "         The backup may be incomplete. Consider re-running."
    }
}

# --- Size verification ---
# Compare source vs backup logical byte sums to detect truncated files
$SourceSizeKB = $VolumeLogicalKB
# Exclude the ".daaf-symlinks" manifest from the backup byte sum: it exists in the
# backup but not the volume, and the source side (VolumeLogicalKB) never counted it
# -- so counting it here would skew the comparison.
$BackupSizeKB = [long]((Get-ChildItem -Path $BackupName -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne $SymlinksManifest } | Measure-Object -Property Length -Sum).Sum / 1024)
if ($SourceSizeKB -gt 0 -and $BackupSizeKB -gt 0) {
    # Allow 1% tolerance for filesystem metadata differences
    $ToleranceKB = [math]::Max(1, [long]($SourceSizeKB / 100))
    $DiffKB = [math]::Abs($SourceSizeKB - $BackupSizeKB)
    if ($DiffKB -gt $ToleranceKB) {
        Write-Host ""
        Write-Host "WARNING: Backup size mismatch." -ForegroundColor Yellow
        Write-Host "         Source: ${SourceSizeKB} KB, Backup: ${BackupSizeKB} KB (difference: ${DiffKB} KB)"
        Write-Host "         The backup may be incomplete. Consider re-running."
    }
}

# --- Back up the Claude Code state volume ---
# Copy the second volume into a dedicated hidden subfolder. This runs AFTER the
# data-volume verification above so the earlier file counts are unaffected by
# these files. If the volume does not exist (older install predating it), skip
# with a note rather than failing -- the data backup is still valid on its own.
$ClaudeBackedUp = $false
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker volume inspect $ClaudeVolumeName 2>&1
$claudeVolumeExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if ($claudeVolumeExists) {
    Write-Host ""
    Write-Host "Backing up Claude Code state (credentials, session history, plugins)..."
    $ClaudeDestPath = Join-Path $HostPath $ClaudeSubDir
    New-Item -ItemType Directory -Path $ClaudeDestPath -Force | Out-Null
    # Same STAGING mechanism as the data volume above (this volume ALSO carries
    # symlinks -- e.g. codex-daaf/tmp/arg0/... -- which is why the "Failed to back
    # up the Claude Code state volume" warning appeared on Windows: `docker cp`
    # aborted on the first link). Stage into a throwaway container to strip the
    # symlinks into this subfolder's own ".daaf-symlinks" manifest, then cp the
    # symlink-free staged tree out. Run synchronously (this copy is small). Only
    # docker's text status lines reach stdout (the file data goes straight to disk),
    # so synchronous inline calls are pipeline-safe on PS 5.1.
    $ClaudeStageCid = $null
    $claudeCopyOk = $false
    $ClaudeStageLog = ""
    try {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $ClaudeStageCid = (docker run -d -v "${ClaudeVolumeName}:/source:ro" busybox sh -c $StageProgram 2>&1 | Select-Object -Last 1)
        if ($null -ne $ClaudeStageCid) { $ClaudeStageCid = "$ClaudeStageCid".Trim() }
        $claudeStageStartOk = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrEmpty($ClaudeStageCid))
        $ErrorActionPreference = $savedEAP
        if ($claudeStageStartOk) {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $ClaudeStageStatusRaw = (docker wait $ClaudeStageCid 2>&1 | Select-Object -Last 1)
            $ErrorActionPreference = $savedEAP
            $ClaudeStageStatus = 1
            if ($null -ne $ClaudeStageStatusRaw) { $null = [int]::TryParse("$ClaudeStageStatusRaw".Trim(), [ref]$ClaudeStageStatus) }
            if ($ClaudeStageStatus -eq 0) {
                $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
                $null = docker cp "${ClaudeStageCid}:/staging/." "${ClaudeDestPath}" 2>&1
                $claudeCopyOk = ($LASTEXITCODE -eq 0)
                $ErrorActionPreference = $savedEAP
            } else {
                # Staging gate tripped: the offender list went to the DETACHED
                # container's log. Capture it now, before the finally below removes
                # the container. Best-effort; kept a WARNING (never fatal), asymmetric
                # with the data volume.
                $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
                $ClaudeStageLog = (docker logs $ClaudeStageCid 2>&1 | Out-String)
                $ErrorActionPreference = $savedEAP
            }
        }
    } finally {
        # Remove the staging container even if the copy is interrupted (PS finally
        # runs on pipeline stop / Ctrl-C), mirroring the data-copy cleanup idiom.
        # Best-effort; guarded so an unset/empty CID is a no-op.
        if (-not [string]::IsNullOrEmpty($ClaudeStageCid)) {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $null = docker rm -f $ClaudeStageCid 2>&1
            $ErrorActionPreference = $savedEAP
        }
    }
    if ($claudeCopyOk) {
        # Count data files only -- exclude the symlink manifest (metadata, not
        # volume content), mirroring the data-volume FileCount exclusion.
        $ClaudeFileCount = @(Get-ChildItem -Path $ClaudeDestPath -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne $SymlinksManifest }).Count
        Write-Host "Claude Code state backed up ($ClaudeFileCount files)."
        $ClaudeBackedUp = $true
    } else {
        Write-Host "WARNING: Failed to back up the Claude Code state volume." -ForegroundColor Yellow
        if (-not [string]::IsNullOrWhiteSpace($ClaudeStageLog)) {
            Write-Host "         Details from the staging scan:"
            foreach ($logLine in ($ClaudeStageLog -split "`r?`n")) {
                if ($logLine -ne "") { Write-Host "         $logLine" }
            }
        }
        Write-Host "         The data volume backup above is still valid."
    }
} else {
    Write-Host ""
    Write-Host "NOTE: No Claude Code state volume ('$ClaudeVolumeName') found."
    Write-Host "      Skipping -- this install may predate the dedicated Claude volume."
}

# --- Capture the executable-permission manifest ---
# Why: NTFS (and the FAT/exFAT of external drives) stores no POSIX permission
# bits, so when this backup lands on the Windows host every file's mode is lost.
# On restore, `docker cp` INTO the volume fabricates 0755 for every file, and git
# inside the container then reports every tracked 0644 file as modified (a pure
# 100644->100755 mode diff, no content change). To let restore put the modes back,
# record -- here, from the volume, where the modes are still intact -- the relative
# path of every regular file that has the owner-exec bit set. Restore normalizes
# everything to 0644 and re-applies 0755 to exactly these paths.
#
# This runs AFTER the data-volume file-count/size verification above (same reason
# the Claude subfolder copy does): the backup compares backup-folder counts/sizes
# against the volume scan, and the manifest file must not skew that comparison. It
# is written into the backup ROOT (not a subfolder) so restore finds it via the
# whole-folder `docker cp`.
#
# Generate the list container-side from the volume: `find -type f -perm -0100`
# matches regular files with the owner-exec bit set. Manifest write failure is a
# WARNING, not fatal -- the data backup is still valid, and restore degrades
# gracefully (an absent manifest simply means no permission normalization happens).
$PermissionsManifest = ".daaf-permissions"
Write-Host ""
Write-Host "Recording executable-permission manifest..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ExecPathsRaw = docker run --rm -v "${VolumeName}:/source:ro" busybox sh -c 'find /source -type f -perm -0100' 2>$null
$manifestScanOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if ($manifestScanOk) {
    # Normalize to an array of volume-relative paths (strip the leading "/source/"),
    # dropping blank lines. `docker run` may return $null (no matches), a single
    # string (one match -- PS unwraps the array), or a string[]; @() forces array
    # context so the foreach is always safe.
    $ExecPaths = @($ExecPathsRaw | ForEach-Object { ($_ -replace '\r', '').Trim() } |
        Where-Object { $_ -ne "" } | ForEach-Object { $_ -replace '^/source/', '' })
    # PS 5.1 encoding trap: `>` and Out-File default to UTF-16, and `-Encoding UTF8`
    # writes a BOM -- either corrupts the container-side read on restore. Write raw
    # LF-terminated, BOM-free bytes via WriteAllLines with a no-BOM UTF8 encoding.
    # WriteAllLines joins with Environment.NewLine (CRLF on Windows), so restore
    # strips trailing CR defensively; a zero-length array still writes an empty
    # (0-byte) file, which correctly signals "backup DOES preserve permissions"
    # (restore normalizes to 644, re-applies exec to nothing) vs. an absent manifest
    # (older backup: restore leaves modes untouched).
    $ManifestPath = Join-Path $HostPath $PermissionsManifest
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    # A WriteAllLines failure (e.g. disk full) would throw under EAP=Stop and abort the
    # whole backup fatally. Catch it and downgrade to the same WARNING the scan-failure
    # branch below emits -- the data backup is already complete and valid, and restore
    # degrades gracefully on an absent manifest. Remove any partial file so restore
    # sees an ABSENT manifest (no normalization) rather than a truncated one.
    try {
        [System.IO.File]::WriteAllLines($ManifestPath, $ExecPaths, $utf8NoBom)
        Write-Host "Recorded $($ExecPaths.Count) executable file(s) in $PermissionsManifest."
    } catch {
        Remove-Item -LiteralPath $ManifestPath -Force -ErrorAction SilentlyContinue
        Write-Host "WARNING: Could not record the executable-permission manifest." -ForegroundColor Yellow
        Write-Host "         The backup is still valid; on restore, file permissions may need"
        Write-Host "         manual repair if this backup is restored on a Windows host."
    }
} else {
    Write-Host "WARNING: Could not record the executable-permission manifest." -ForegroundColor Yellow
    Write-Host "         The backup is still valid; on restore, file permissions may need"
    Write-Host "         manual repair if this backup is restored on a Windows host."
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  Backup complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Location: $HostPath\"
Write-Host "Files:    $FileCount files copied"
if ($ClaudeBackedUp) {
    Write-Host ""
    Write-Host "IMPORTANT: This backup INCLUDES your Claude Code credentials and session" -ForegroundColor Yellow
    Write-Host "history (in $ClaudeSubDir\). Treat the backup folder as sensitive --"
    Write-Host "store it somewhere private and do not share it."
}
Write-Host ""
Write-Host "To restore from this backup, run the restore script from this folder:"
Write-Host ""
Write-Host "  .\restore_from_backup.ps1"
Write-Host ""
Write-Host "The restore script lets you pick which backup to restore from and"
Write-Host "handles clearing the volume before copying to ensure a clean state."
Write-Host ""
Wait-AndExit 0
