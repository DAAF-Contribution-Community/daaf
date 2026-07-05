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
# Pre-create the Claude state subfolder NOW, before the data-volume copy below,
# for parity with backup_daaf.sh. On Linux (pwsh-on-Linux / CI), busybox
# `cp -a /source/. /dest/` resets the backup dir's owner to the volume root's UID,
# which can make a later mkdir under it fail -- creating the subfolder while it is
# still user-owned avoids that. On Windows Docker Desktop, bind-mount ownership is
# a no-op, so this is harmless there and exists purely for cross-platform parity.
# Gate on the same volume-exists condition as the Claude backup block below so a
# data-only backup never leaves an empty "$ClaudeSubDir\" dir that restore might
# misread.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker volume inspect $ClaudeVolumeName 2>&1
$claudeVolumeExistsEarly = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if ($claudeVolumeExistsEarly) {
    New-Item -ItemType Directory -Path (Join-Path $HostPath $ClaudeSubDir) -Force | Out-Null
}
Write-Host "Copying files from Docker volume..."
Write-Host "  Progress: 0 / $TotalFiles files (0%)" -NoNewline

$CopyProcess = Start-Process -FilePath "docker" `
    -ArgumentList "run --rm -v `"${VolumeName}:/source:ro`" -v `"${HostPath}:/dest`" busybox sh -c `"cp -a /source/. /dest/`"" `
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
        $CopyProcess.WaitForExit()
    }
}

$CopyProcess.WaitForExit()
$CopyExitCode = if ($null -ne $CopyProcess.ExitCode) { $CopyProcess.ExitCode } else { 0 }
Write-Host "`r  Progress: $TotalFiles / $TotalFiles files (100%)   "

# --- Verify ---
$FileCount = @(Get-ChildItem -Path $BackupName -Recurse -File -Force -ErrorAction SilentlyContinue).Count

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
    Write-Host "Note: File copy reported warnings (exit code $CopyExitCode) but all $FileCount files were transferred." -ForegroundColor Yellow
}

# --- Size verification ---
# Compare source vs backup logical byte sums to detect truncated files
$SourceSizeKB = $VolumeLogicalKB
$BackupSizeKB = [long]((Get-ChildItem -Path $BackupName -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1024)
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
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $null = docker run --rm -v "${ClaudeVolumeName}:/source:ro" -v "${ClaudeDestPath}:/dest" busybox sh -c "cp -a /source/. /dest/" 2>&1
    $claudeCopyOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $savedEAP
    if ($claudeCopyOk) {
        $ClaudeFileCount = @(Get-ChildItem -Path $ClaudeDestPath -Recurse -File -Force -ErrorAction SilentlyContinue).Count
        Write-Host "Claude Code state backed up ($ClaudeFileCount files)."
        $ClaudeBackedUp = $true
    } else {
        Write-Host "WARNING: Failed to back up the Claude Code state volume." -ForegroundColor Yellow
        Write-Host "         The data volume backup above is still valid."
    }
} else {
    Write-Host ""
    Write-Host "NOTE: No Claude Code state volume ('$ClaudeVolumeName') found."
    Write-Host "      Skipping -- this install may predate the dedicated Claude volume."
}

# --- Repair backup tree ownership ---
# Parity with backup_daaf.sh: the busybox `cp -a` copies chown the backup tree to
# the volumes' internal UIDs (1000, with Claude state dirs at mode 700). On Linux
# (pwsh-on-Linux / CI) a differing invoking UID would then be unable to traverse
# those dirs; root inside a container can rewrite the bind mount's ownership to
# fix it. On pwsh-on-Linux the external `id` command resolves the real invoking
# UID/GID (matching the .sh behavior); on Windows `id` is absent and we fall back
# to the literal volume UID/GID 1000:1000 -- harmless there, since Windows Docker
# Desktop bind mounts ignore Unix ownership. Non-fatal: the backup is already
# complete, so failure only WARNs.
$chownOwner = "1000:1000"
if (Get-Command id -ErrorAction SilentlyContinue) {
    $chownOwner = "$(& id -u):$(& id -g)"
}
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker run --rm -v "${HostPath}:/dest" busybox chown -R $chownOwner /dest 2>&1
$chownOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $savedEAP
if (-not $chownOk) {
    Write-Host "WARNING: Could not restore backup folder ownership to the current user." -ForegroundColor Yellow
    Write-Host "         The backup is complete, but you may need elevated permissions"
    Write-Host "         to inspect or remove it."
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
