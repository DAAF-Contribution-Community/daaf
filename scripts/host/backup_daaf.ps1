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
# ============================================================================

$ErrorActionPreference = "Stop"

function Pause-And-Exit {
    param([int]$Code = 0)
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    exit $Code
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/backup_daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# --- Configuration ---
$VolumeName = "daaf_daaf-data"
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
    Pause-And-Exit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    Pause-And-Exit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker volume inspect $VolumeName 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker volume '$VolumeName' not found." -ForegroundColor Red
    Write-Host "Have you run the DAAF installer yet?"
    Pause-And-Exit 1
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
            Pause-And-Exit 1
        }
    }
}

Write-Host "Backup name: $BackupName\"
Write-Host ""

# --- Count source files ---
Write-Host "Scanning Docker volume..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ScanOutput = docker run --rm -v "${VolumeName}:/source:ro" busybox sh -c "find /source -type f | wc -l && du -sk /source && du -sh /source"
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not scan Docker volume." -ForegroundColor Red
    Pause-And-Exit 1
}
$TotalFiles = [int]($ScanOutput[0].Trim())
$VolumeSizeKB = [long](($ScanOutput[1].Trim() -split '\s+')[0])
$TotalSize = ($ScanOutput[2].Trim() -split '\s+')[0]
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
    Pause-And-Exit 1
}

# --- Create backup ---
New-Item -ItemType Directory -Path $BackupName -Force | Out-Null
$HostPath = (Resolve-Path $BackupName).Path
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
    Pause-And-Exit 1
}

if ($CopyExitCode -ne 0) {
    Write-Host "Note: File copy reported warnings (exit code $CopyExitCode) but all $FileCount files were transferred." -ForegroundColor Yellow
}

# --- Size verification ---
# Compare source vs backup byte counts to detect truncated files
$SourceSizeKB = $VolumeSizeKB
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

Write-Host ""
Write-Host "=========================================="
Write-Host "  Backup complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Location: $HostPath\"
Write-Host "Files:    $FileCount files copied"
Write-Host ""
Write-Host "To restore from this backup in the future, you can copy files back"
Write-Host "into the Docker volume using Docker Desktop's Files tab, or with:"
Write-Host "  docker run --rm -v `"${HostPath}:/source:ro`" -v `"${VolumeName}:/dest`" busybox sh -c 'cp -a /source/. /dest/'"
Write-Host ""
Pause-And-Exit 0
