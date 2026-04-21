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
# ============================================================================

$ErrorActionPreference = "Stop"

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
    Write-Host "ERROR: Docker is not installed or not in your PATH." -ForegroundColor Red
    exit 1
}

$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    exit 1
}

$null = docker volume inspect $VolumeName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker volume '$VolumeName' not found." -ForegroundColor Red
    Write-Host "Have you run the DAAF installer yet?"
    exit 1
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
            exit 1
        }
    }
}

Write-Host "Backup name: $BackupName\"
Write-Host ""

# --- Create backup ---
Write-Host "Copying files from Docker volume (this may take a moment)..."
New-Item -ItemType Directory -Path $BackupName -Force | Out-Null

$HostPath = (Resolve-Path $BackupName).Path
docker run --rm `
    -v "${VolumeName}:/source:ro" `
    -v "${HostPath}:/dest" `
    busybox sh -c "cp -a /source/. /dest/"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backup failed. Check Docker Desktop for errors." -ForegroundColor Red
    exit 1
}

# --- Verify ---
$FileCount = @(Get-ChildItem -Path $BackupName -Recurse -File).Count

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
