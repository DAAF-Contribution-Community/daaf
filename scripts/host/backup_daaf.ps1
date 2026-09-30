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
        # First matching arm wins (each returns), so the specific patterns come first:
        # the backup-folder count's argument string holds the user's backup path, which
        # can contain "info" (e.g. C:\Users\info\...) and always contains "run --rm".
        switch -Wildcard ($argStr) {
            "logs *" {
                # Staging-container log after a clean `docker wait`: the snapshot
                # count markers. (The dry run exits before staging; modeled so the
                # parse stays compatible if the early exit ever moves.)
                Write-Output "STAGED_FILES=42"
                Write-Output "STAGED_KB=1000"
                return
            }
            "run --rm -v *:/b:ro*" {
                # Container-side count of the host backup folder (same caveat).
                Write-Output "BACKUP_FILES=42"
                Write-Output "BACKUP_KB=1000"
                Write-Output "BACKUP_SENTINEL=1"
                return
            }
            "*info*" { return }
            "*volume inspect*" { return }
            "run -d*" {
                # Staging container launch (symlink strip) -- emit a fake CID.
                Write-Output "stagecid0000"
                return
            }
            "wait*" { Write-Output "0"; return }
            "*run --rm*" {
                # Scan command -- return 6 lines matching the parsing expectations:
                # Line 0: file count, Line 1: "KB\t/source", Line 2: "size\t/source", Line 3: logical KB,
                # Line 4: special-file count, Line 5: long-path file count (both nonzero
                # so the dry-run exercises the skip note and the long-path notice)
                Write-Output "42"
                Write-Output "1024`t/source"
                Write-Output "1.0M`t/source"
                Write-Output "1000"
                Write-Output "2"
                Write-Output "3"
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
# dot-source daaf_lib.ps1 inline it. Parse only these whitelisted keys (never
# dot-source -- the file holds API keys); process env wins; absent file = no-op;
# CR stripped; PS 5.1 safe.
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

# --- Native Argument Quoting (inlined from daaf_lib.ps1) ---
# INLINE COPY of daaf_lib.ps1 ConvertTo-DaafNativeArg: this standalone script does
# not dot-source daaf_lib.ps1, so the helper is carried inline. The function
# definition must stay BYTE-IDENTICAL to the library version (pinned by
# tests/powershell/native_arg_quoting.Tests.ps1) -- see daaf_lib.ps1 for the full
# annotation of the Windows argv quoting rules it implements. Used to build the
# single pre-joined `docker cp` argument string below.
function ConvertTo-DaafNativeArg {
    [CmdletBinding()]
    param([string]$Value = '')
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    return '"' + (($Value -replace '(\\*)"', '$1$1\"') -replace '(\\+)\z', '$1$1') + '"'
}

# --- Count helpers (a byte-identical copy lives in restore_from_backup.ps1) ---
# Get-DaafCountMarker reads one NAME=<digits> marker from container output (the
# staging log's STAGED_FILES/STAGED_KB, the backup-folder count's BACKUP_FILES/
# BACKUP_KB). The pattern is anchored on the trimmed line, so a merged stderr record
# or stray text never parses; [long]::TryParse is gated on its boolean (it writes 0
# into the [ref] on failure) and the last valid occurrence wins. Returns $null when
# the marker is missing or unparseable -- callers treat $null as "count unavailable",
# never as 0.
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

# Measure-DaafBackupTree is the PowerShell FALLBACK count of a backup folder, used
# when the container-side count is unavailable, and for the Claude-state count when
# that staging log cannot be read. It is never silent: Windows PowerShell 5.1
# Get-ChildItem cannot descend into a folder whose Windows path is 248+ characters
# (nor list a file at 260+) unless LongPathsEnabled=1, and `-ErrorAction
# SilentlyContinue` alone would turn that into a quiet undercount (field 2026-09-29:
# 72,834 counted vs 73,021 present -- 187 files hidden). The errors are captured with
# -ErrorVariable and returned, so the caller can call the count a LOWER BOUND.
# Exclusions are root-relative, mirroring the container-side count: named files at
# the root, and every file under named root subfolders. They are compared
# case-SENSITIVELY (-ccontains, Ordinal), like the container's `find -path`, so a root
# ".DAAF-SYMLINKS" counts as data on both sides.
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
# DAAF_DATA_VOLUME_NAME, when set, overrides the whole derivation with a verbatim
# full volume name (the shared-workspace escape hatch); unset => the derived
# default. Matches Resolve-DaafDataVolumeName in daaf_lib.ps1 (inlined here because
# this standalone script does not dot-source the library).
$projectName = "daaf"
if ($env:DAAF_PROJECT_NAME) { $projectName = $env:DAAF_PROJECT_NAME }
$VolumeName = "${projectName}_daaf-data"
if ($env:DAAF_DATA_VOLUME_NAME) { $VolumeName = $env:DAAF_DATA_VOLUME_NAME }
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
# recreate the links. The staging step ALWAYS writes it (0 bytes when the volume has
# no symlinks), which is also what lets the backup-folder count below use it as a
# visibility sentinel. Absent manifest (a backup that predates this feature) = no-op
# on restore, matching the ".daaf-permissions" "no manifest, no action" rule.
# The same staging step also DELETES special files -- named pipes (FIFOs), sockets,
# and block/char device nodes -- with no manifest: Windows `docker cp` creates
# nothing for them and then aborts on the follow-up timestamp call, the same
# truncation class as the symlink abort. They are runtime rendezvous objects with no
# content (e.g. stale provider-shim `output.fifo` stream files), so restore does not
# recreate them; the scan below counts them so the skip is visible to the user.
#
# SYNC NOTE: the container-side $StageProgram and $BackupCountProgram here-strings
# below are single-quoted (`@'...'@`), so they CANNOT interpolate these variables --
# they hardcode the literals ".daaf-symlinks" (the `paste ... > /staging/.daaf-symlinks`
# line, $BackupCountProgram's `test -e` sentinel, and both programs' count
# predicates), ".daaf-permissions" and ".daaf-claude-config" (both programs' count
# exclusions, which must stay identical -- pinned by tests/bash/backup_twin_parity.bats).
# The volume scan ($ScanOutput) hardcodes the same three names in its [0]/[3] count
# predicate (kept literal, like the .sh twin's scan, so the pinned predicate text is
# identical in every program). restore_from_backup.ps1 carries a byte-identical
# $BackupCountProgram and the same literals in its post-restore count.
# If a name ever changes, update the literals by hand to match. (The .sh
# twin splices ${SYMLINKS_MANIFEST} into its single-quoted program via a quote break
# but hardcodes the other two names, so it carries its own sync note.)
$SymlinksManifest = ".daaf-symlinks"
# Executable-permission manifest, written into the backup root after verification
# (see "Capture the executable-permission manifest" below). Declared here because
# the backup-folder count excludes it too.
$PermissionsManifest = ".daaf-permissions"
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
# Name the volume being copied (the resolved name, so DAAF_PROJECT_NAME and the
# DAAF_DATA_VOLUME_NAME override both show). With more than one install on a machine,
# nothing else in the output said which volume a backup came from, and a user once
# diffed a backup against the wrong install's volume.
Write-Host "Source volume: $VolumeName"
Write-Host ""

# --- Count source files ---
# Long-path threshold for the scan's index [5]. Every backed-up file lands at
# <this folder>\<BackupName>\<volume-relative path>, so its Windows path length is
# this prefix plus the relative path's length. Windows' classic MAX_PATH is 260
# including the terminating NUL, so a path of 260+ characters is past it. Computed
# from the current location BEFORE New-Item creates the folder; ProviderPath is the
# real filesystem path (a PS drive name would understate it).
$BackupPathPrefixLen = (Get-Location).ProviderPath.TrimEnd('\', '/').Length + 1 + $BackupName.Length + 1
$LongPathMinRel = 260 - $BackupPathPrefixLen
Write-Host "Scanning Docker volume..."
# Scan output, one value per line (index order is a parsing contract shared with the
# .sh twin -- append new lines at the END only): [0] regular-file count, [1] `du -sk`,
# [2] `du -sh`, [3] logical KB, [4] special-file count (named pipes, sockets,
# block/char device nodes -- the set the staging program deletes), [5] count of
# regular files whose volume-relative path is at least $LongPathMinRel characters,
# i.e. whose Windows path in this backup folder will be 260+ ("/source/" is 8
# characters, subtracted by awk). Index [5] is Windows-only: the .sh twin does not
# emit it and reserves the slot. Because [5] is informational, its segment is grouped
# as `{ ... || echo 0; }`: if it fails, it prints 0 and the scan still succeeds,
# instead of the `&&` chain turning a notice into "Could not scan Docker volume". The
# braces matter -- a bare `... && X || echo 0` would also swallow a failure of any
# EARLIER segment. Index [5] covers the data volume only: Claude-state files land
# under ".daaf-claude-config\" in the backup folder, 20 characters deeper, and are not
# counted (the notice is a heads-up, not a verification input). The `\(`/`\)`/`\*`
# reach docker.exe intact (a backslash is literal in a PS double-quoted string and in
# Windows argv parsing unless it precedes a double quote), exactly like the staging
# program's existing `\;`; the container `sh` then unescapes them for `find`.
#
# [0] and [3] use the SNAPSHOT COUNT's `find` predicate and one-line-per-file
# counting (see $StageProgram below): run from /source, the root ".daaf-symlinks",
# ".daaf-permissions" and ".daaf-claude-config" subtree are excluded, and ONE `find
# -exec stat -c %s {} + | awk` pass yields "<files> <KB>" into `c`, split with
# `${c% *}` / `${c#* }` (a `find | wc -l` would count a name holding a newline twice).
# So when the "Snapshot: N files (M fewer than the scan ...)" line below reports a
# difference, it is genuine live-volume change, not a predicate gap (a stray root
# ".daaf-permissions" left by a failed restore replay used to show up there as
# "drift"), and on the fallback path the scan is a like-for-like expected count. The
# three names are hardcoded literals (see the SYNC NOTE in the Configuration section),
# matching the .sh twin's scan; tests/bash/backup_twin_parity.bats pins the predicate.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$ScanOutput = docker run --rm -v "${VolumeName}:/source:ro" busybox sh -c "cd /source && c=`$(find . -type f ! -path ./.daaf-symlinks ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + | awk '{n++; s+=`$1} END {print n+0, int(s/1024)}') && echo `${c% *} && du -sk /source && du -sh /source && echo `${c#* } && find /source \( -type p -o -type s -o -type b -o -type c \) | wc -l && { find /source -type f | awk -v m=$LongPathMinRel '{if (length(`$0) - 8 >= m) n++} END {print n+0}' || echo 0; }"
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not scan Docker volume." -ForegroundColor Red
    Wait-AndExit 1
}
$TotalFiles = [int]($ScanOutput[0].Trim())
$VolumeSizeKB = [long](($ScanOutput[1].Trim() -split '\s+')[0])
$TotalSize = ($ScanOutput[2].Trim() -split '\s+')[0]
$VolumeLogicalKB = [long]($ScanOutput[3].Trim())
# Index [4] is informational only: a missing or non-numeric value (e.g. a mock that
# emits the older 4-line scan) reads as 0 rather than failing the backup. The bounds
# check matters -- Set-StrictMode 3.0 makes an out-of-range index a terminating
# error. Special files are never regular files, so they are already outside
# $TotalFiles and the file-count verification below is unaffected by skipping them.
$SpecialFiles = 0
$ScanLines = @($ScanOutput)
if ($ScanLines.Count -ge 5) {
    $SpecialFilesParsed = 0
    if ([int]::TryParse("$($ScanLines[4])".Trim(), [ref]$SpecialFilesParsed)) {
        $SpecialFiles = $SpecialFilesParsed
    }
}
# Index [5] is informational in the same way (bounds-checked, TryParse, default 0).
# It drives a heads-up only and never latches the WITH WARNINGS banner: the files are
# backed up and verified correctly (Docker handles long paths); it is other Windows
# tools that may fail on them. awk's length() counts bytes, so a non-ASCII name can
# overstate its UTF-16 path length slightly -- acceptable for a notice.
$LongPathFiles = 0
if ($ScanLines.Count -ge 6) {
    $LongPathFilesParsed = 0
    if ([int]::TryParse("$($ScanLines[5])".Trim(), [ref]$LongPathFilesParsed)) {
        $LongPathFiles = $LongPathFilesParsed
    }
}
Write-Host "Found $TotalFiles files to copy ($TotalSize)."
if ($SpecialFiles -gt 0) {
    Write-Host "Note: skipping $SpecialFiles named pipe/socket/device file(s) -- runtime-only, not backed up."
}
if ($LongPathFiles -gt 0) {
    Write-Host "Note: $LongPathFiles file(s) will have paths longer than Windows' 260-character limit in"
    Write-Host "      this location. They are backed up correctly, but Windows Explorer, zip tools and"
    Write-Host "      cloud-sync apps may fail on them. To avoid it, keep the daaf-docker folder at a"
    Write-Host "      shorter path (e.g. C:\daaf) or enable Windows long-path support."
}
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
$AvailableKB = [long][math]::Floor($DriveInfo.AvailableFreeSpace / 1024)
# Add 10% buffer to account for filesystem overhead
$RequiredKB = [long][math]::Floor($VolumeSizeKB * 110 / 100)
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
# The final `find` then deletes special files (`-type p` named pipes, `-type s`
# sockets, `-type b`/`-type c` device nodes). For FIFOs and device nodes, Windows
# `docker cp` has the same abort-and-truncate failure as for symlinks: moby's Windows
# archive extractor creates nothing for a FIFO/device entry, then its timestamp step
# (`chtimes`) fails on the missing path and aborts the whole extraction -- after the
# CLI has already printed "Successfully copied" (field failure 2026-09-29, sibling
# project on a variant of this script: a stale provider-shim `output.fifo` stopped a
# Windows backup; last progress reading 94%). Sockets are stripped defensively (how
# Docker archives them was not verified). None of these carry data, so they are
# dropped with NO manifest and restore does not recreate them. The
# grouped `\( ... \)` predicates keep `-exec` bound to all four types; with no
# matches `find` runs no `rm` and exits 0, so `set -e` is safe on a clean volume.
# The staged tree `docker cp` streams therefore holds only directories, regular
# files, and the ".daaf-symlinks" manifest.
#
# The staging program contains NO embedded double quotes -- embedded double quotes
# corrupt Windows arg parsing on PS 5.1. Its /tmp writes are inside the throwaway
# container's own layer (NOT the DAAF container's /tmp), so no provenance concern.
# It is passed by DIRECT invocation (`docker run ... sh -c $StageProgram`, below):
# the call operator hands it to docker as one argument, no Start-Process involved.
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
# first NAMES the offenders to STDOUT before `exit 3`: the tab branch prints the
# matching lines (`grep -f` without `-q`); the newline branch prints the whole
# (typically short) symlink path list, since mismatched line counts cannot isolate
# the culprit. The driver relays that STDOUT via `docker logs` on the failure path
# below (the staging container is detached, so its output would otherwise be lost).
# WHY STDOUT, not stderr: on a real Windows host, PS 5.1's native-command `2>&1` merge
# dropped the staging container's stderr, so the offender list never reached the
# user's terminal (field failure 2026-07-14). The staging program's stdout is
# otherwise unused (`docker run -d` detaches; the CID comes from the daemon, not the
# program), and stdout survives `docker logs` retrieval on every PowerShell version --
# stderr was the fragile leg.
# This here-string is a SINGLE-quoted (`@'...'@`) literal, so its bytes reach the
# container `sh` verbatim; the `\\011` DOUBLE backslash therefore survives to hand
# printf ONE backslash (the same octal-escape trap the .sh twin and the restore-replay
# `\\357` idiom hit). The echo/cat/grep offender lines add no printf escapes and stay
# quote-free for twin parity.
#
# SNAPSHOT COUNT: on success only (every earlier step is under `set -e`), the program
# ends by printing STAGED_FILES=<n> and STAGED_KB=<n> to STDOUT -- the regular files of
# the FROZEN staged tree the copy streams, with the source scan's logical-KB formula
# (sum of `stat -c %s`, int(s/1024)). The source scan runs on the LIVE volume before
# `cp -a`, so it can drift from what is actually backed up; this count cannot, which
# is what lets the verification below run at ZERO tolerance.
#
# A count that hit a read error is NOT a count. A pipeline's exit status is its LAST
# command's (awk here), and busybox `sh` has no verified `pipefail` default, so a
# `find` or `stat` error would otherwise be silent: awk would print a SHORT count and
# the program would exit 0 (reproduced under dash in review round 2). So the count's
# stderr goes to /tmp/count_err (the throwaway container's own /tmp, like the link
# files above), and the markers are printed only when that file is empty; otherwise
# the program prints STAGED_COUNT_ERRORS=<lines> INSTEAD of STAGED_FILES/STAGED_KB.
# Missing markers route to the existing "Could not read the snapshot's file count"
# fallback below, and the staging step itself still exits 0 (the `if` is not a
# failure under `set -e`), so an unreadable count never fails the backup. `grep -c ^`
# counts lines (quote-free, and it counts a last line with no newline).
#
# Its `find` predicate is IDENTICAL to $BackupCountProgram's (pinned by
# tests/bash/backup_twin_parity.bats): it excludes the root ".daaf-symlinks" manifest
# and, like the host-side count, a root ".daaf-permissions" and everything under a
# root ".daaf-claude-config". Those two are never volume content in a healthy volume,
# but restore's permission replay can leave a stray root ".daaf-permissions" behind
# when it fails; counting it on one side only produced a false zero-tolerance
# mismatch (review reproduction: STAGED_FILES=2 vs BACKUP_FILES=1).
#
# ONE traversal yields both numbers: `stat -c %s` prints one size line per file
# (even for a name that holds a newline, which `find | wc -l` would count twice), and
# awk prints "<files> <KB>" at END (`n+0` so an empty tree prints 0, not an empty
# field); `${counts% *}` / `${counts#* }` split the pair. The awk program is
# backslash-escaped rather than quoted: the program must stay quote-free (PS 5.1 argv,
# and the .sh twin's single-quoted string, whose parity extractor ends at a line
# ending in a single quote). A pipeline's status is its last command's, so the count
# line cannot trip `set -e` (which is also why errors are detected through
# /tmp/count_err, above), and with no files `find` runs no `stat` and awk prints 0 0.
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
echo STAGE_ERR_NEWLINE
echo One of these symlink names embeds a newline -- rename or remove the offending link:
cat /tmp/link_paths
exit 3
fi
if grep -qf /tmp/tab_pat /tmp/link_paths || grep -qf /tmp/tab_pat /tmp/link_targets; then
echo STAGE_ERR_TAB
echo These symlink paths or targets embed a tab -- rename or remove the offending link:
grep -f /tmp/tab_pat /tmp/link_paths || true
grep -f /tmp/tab_pat /tmp/link_targets || true
exit 3
fi
paste /tmp/link_paths /tmp/link_targets > /staging/.daaf-symlinks
find /staging -type l -exec rm -f {} +
find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +
counts=$(find . -type f ! -path ./.daaf-symlinks ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | awk \{n++\;s+=\$1\}\ END\ \{print\ n+0,int\(s/1024\)\})
if test -s /tmp/count_err; then
echo STAGED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err)
else
echo STAGED_FILES=${counts% *}
echo STAGED_KB=${counts#* }
fi
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

# From here until the copy finishes, ONE try/finally owns the staging container: its
# finally runs `docker rm -f $StageCid` however the block ends -- success, a throw, or
# Ctrl-C (PowerShell runs finally blocks when the user stops the script) during the
# possibly long `docker wait`, the `docker logs` reads, or the copy. Before this, the
# try began only at the copy loop, so an interruption while waiting for staging left
# a full-size staging container (a complete copy of the volume) behind in the Docker
# VM. As everywhere in this script, nothing inside the try calls `exit`/Wait-AndExit
# (version-fragile on PS 5.1 when a finally must still run): a staging failure only
# sets $StageFailed, and the fatal exit happens after the finally.
$StageFailed = $false
$StageStatus = 1
$StageLog = ""
$CopyProcess = $null
$HaveStagedCounts = $false
$ExpectedFiles = $TotalFiles
$ExpectedKB = $VolumeLogicalKB
try {
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $StageStatusRaw = (docker wait $StageCid 2>&1 | Select-Object -Last 1)
    $ErrorActionPreference = $savedEAP
    # Gate on TryParse's BOOLEAN return. [int]::TryParse writes 0 into the [ref] on a
    # parse FAILURE (not just a parse of "0"), so the old `$null = TryParse(...)` form
    # silently overwrote the fail-closed default with 0 whenever `docker wait` emitted a
    # non-numeric last line (e.g. a daemon error merged via 2>&1) -- flipping this fatal
    # gate from "abort" to "proceed to copy a partial staged tree." Parse into a temp var
    # and adopt it ONLY on success; otherwise stay fail-closed at 1 (mirrors the correct
    # idiom in restore_from_backup.ps1's backup-number check,
    # `[int]::TryParse($Choice, [ref]$ChoiceNum)`).
    $StageStatusParsed = 0
    if ($null -ne $StageStatusRaw -and [int]::TryParse("$StageStatusRaw".Trim(), [ref]$StageStatusParsed)) {
        $StageStatus = $StageStatusParsed
    }
    if ($StageStatus -ne 0) {
        # The staging container is DETACHED (`docker run -d`), so the gate's STDOUT --
        # including the offender list it prints on an exit-3 -- went to the container
        # log, NOT this terminal. Fetch that log now, BEFORE the finally below runs
        # `docker rm -f` (order matters); it is shown after the finally. Best-effort: a
        # `docker logs` failure must not mask the original staging error. (The gate
        # prints offenders to STDOUT, not stderr: PS 5.1's native `2>&1` merge dropped
        # the container's stderr in the field 2026-07-14, so the offender list never
        # reached the user; stdout is version-agnostic. The `2>&1` here still merges
        # both streams into the log.)
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $StageLog = (docker logs $StageCid 2>&1 | Out-String)
        $ErrorActionPreference = $savedEAP
        $StageFailed = $true
    } else {
        # --- Snapshot count (the verification target) ---
        # Staging exited 0, so its last step printed STAGED_FILES/STAGED_KB to STDOUT
        # (see SNAPSHOT COUNT above). The container is detached, so its log is the only
        # channel: read it now, BEFORE the finally below runs `docker rm -f`. When both
        # markers parse, the snapshot is the expected count and verification is exact
        # (zero tolerance). When they do not (a log driver that cannot be read back, a
        # daemon error, an older program, or a count that hit read errors and printed
        # STAGED_COUNT_ERRORS instead), fall back to the live-volume scan and its 1%
        # tolerance, and say so -- a Note, not a warning: the copy itself is unaffected.
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $StageDoneLog = @(docker logs $StageCid 2>&1)
        $stageLogsOk = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $savedEAP
        $StagedFiles = $null
        $StagedKB = $null
        if ($stageLogsOk) {
            $StagedFiles = Get-DaafCountMarker -Lines $StageDoneLog -Name 'STAGED_FILES'
            $StagedKB = Get-DaafCountMarker -Lines $StageDoneLog -Name 'STAGED_KB'
        }
        $HaveStagedCounts = ($null -ne $StagedFiles -and $null -ne $StagedKB)
        if ($HaveStagedCounts) {
            $ExpectedFiles = $StagedFiles
            $ExpectedKB = $StagedKB
            if ($StagedFiles -eq $TotalFiles) {
                Write-Host "Snapshot: $StagedFiles files."
            } else {
                # Net change only: the scan saw the live volume moments before `cp -a` froze
                # it. The scan's [0] uses the snapshot's own predicate, so the difference is
                # real change on the volume, not a counting difference.
                if ($StagedFiles -gt $TotalFiles) { $SnapshotDelta = "$($StagedFiles - $TotalFiles) more" } else { $SnapshotDelta = "$($TotalFiles - $StagedFiles) fewer" }
                Write-Host "Snapshot: $StagedFiles files ($SnapshotDelta than the scan -- the live volume changed in"
                Write-Host "          between; the snapshot is what gets backed up)."
            }
        } else {
            $ExpectedFiles = $TotalFiles
            $ExpectedKB = $VolumeLogicalKB
            Write-Host "Note: Could not read the snapshot's file count; verifying against the volume scan"
            Write-Host "      instead (1% tolerance)."
        }

        Write-Host "Copying files from Docker volume..."
        Write-Host "  Progress: 0 / $ExpectedFiles files (0%)" -NoNewline

        # ONE pre-joined, quoted argument string -- NOT an array. Start-Process does not
        # quote array elements: it joins them with bare spaces (Microsoft's Start-Process
        # docs: "joins the array into a single string with each element of the array
        # separated by a single space"; PowerShell#5576), so a $HostPath under a spaced
        # folder such as "C:\Users\John Smith" or "OneDrive - Org" reached docker as
        # several arguments and the copy failed. ConvertTo-DaafNativeArg (inlined above)
        # quotes each element for the Windows argv parser. Source is the staged (symlink-
        # and special-file-free) tree, not the volume.
        $CopyArgs = (@('cp', "${StageCid}:/staging/.", $HostPath) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '
        $CopyProcess = Start-Process -FilePath "docker" `
            -ArgumentList $CopyArgs `
            -NoNewWindow -PassThru
        # Cache the process handle NOW, while docker cp is still running. Known PowerShell
        # quirk on Windows (reported upstream, not reproduced here: it needs a Windows host):
        # with -NoNewWindow and/or -RedirectStandard*, the Process object Start-Process
        # -PassThru returns does not hold an open OS handle, so if nothing opens one before
        # the process exits, ExitCode later reads as $null (the exit status is gone).
        # PowerShell#5421 reports it for Windows PowerShell 5.1 and PowerShell 6; #20400
        # for 7.4 previews; the 7.4.1 release notes list the fix -- so it affects Windows
        # PowerShell 5.1 and PowerShell 6.0-7.4.0 on Windows. Touching .Handle opens and
        # retains one for the object's lifetime, which keeps the exit status readable after
        # exit. The old code then coerced that $null to 0 -- a plausible reason the earlier
        # symlink truncation "surfaced with a ZERO exit" (see the file-count verification
        # below). In-repo field precedent: the same `ExitCode` = $null symptom and
        # Handle-cache fix in test_migration.ps1 Invoke-HardenedScript ("exited with code
        # ."). Best-effort: if the handle cannot be opened (the process already exited),
        # the exit code is treated as UNKNOWN below, never 0.
        try {
            $null = $CopyProcess.Handle
        } catch {
            Write-Verbose "Could not cache the docker cp process handle: $_"
        }

        while (-not $CopyProcess.HasExited) {
            Start-Sleep -Seconds 3
            if ($CopyProcess.HasExited) { break }
            # Progress display only: Get-ChildItem undercounts folders past the Windows
            # path-length limit, so this can read low. The final line below reports the
            # verified (container-side) count.
            $Copied = @(Get-ChildItem -Path $BackupName -Recurse -File -Force -ErrorAction SilentlyContinue).Count
            if ($ExpectedFiles -gt 0) {
                $Percent = [math]::Min(100, [math]::Floor($Copied * 100 / $ExpectedFiles))
            } else {
                $Percent = 0
            }
            Write-Host "`r  Progress: $Copied / $ExpectedFiles files ($Percent%)   " -NoNewline
        }
    }
} finally {
    if ($null -ne $CopyProcess -and -not $CopyProcess.HasExited) {
        Stop-Process -Id $CopyProcess.Id -Force -ErrorAction SilentlyContinue
    }
    # Remove the staging container. Best-effort: the copy is done, staging failed, or
    # the run was interrupted -- a failure here must never fail the backup. Wrapped in
    # its own SilentlyContinue bracket: on an interrupt the ambient EAP is not
    # guaranteed, and under EAP=Stop a stderr line from `docker rm` would throw here.
    # Guarded on an empty CID like the Claude block's finally: the launch check above
    # makes it non-empty here today, but `docker rm -f ""` would only add a spurious
    # daemon error if that ever changed.
    if (-not [string]::IsNullOrEmpty($StageCid)) {
        $innerEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $null = docker rm -f $StageCid 2>&1
        $ErrorActionPreference = $innerEAP
    }
}

if ($StageFailed) {
    Write-Host "ERROR: Failed to stage the Docker volume for a symlink-safe backup (exit $StageStatus)." -ForegroundColor Red
    Write-Host "       No backup files were written."
    Write-Host ""
    Write-Host "Details from the staging scan:"
    if (-not [string]::IsNullOrWhiteSpace($StageLog)) {
        foreach ($logLine in ($StageLog -split "`r?`n")) {
            if ($logLine -ne "") { Write-Host "       $logLine" }
        }
    } else {
        # Empty/whitespace log: label the silence rather than omit the block, so a
        # future stream regression is visible rather than ambiguous.
        Write-Host "       (no details could be retrieved from the staging container)"
    }
    Write-Host ""
    Write-Host "       Exit 3 means a symlink's path or target contains an unsupported"
    Write-Host "       character (a TAB or a NEWLINE), which would corrupt the symlink"
    Write-Host "       manifest -- rename or remove the offending symbolic link named above"
    Write-Host "       and re-run."
    Write-Host "       Otherwise, staging can also fail if the Docker Desktop disk image is"
    Write-Host "       full (staging transiently duplicates the volume inside it); check"
    Write-Host "       Docker Desktop for errors, free space, and re-run."
    Wait-AndExit 1
}

# Block until the copy process is fully gone and read its exit code exactly once.
# (Stop-Process in the finally above, if it fired, leaves the process exiting;
# WaitForExit here settles it before we trust ExitCode.)
$CopyProcess.WaitForExit()
# An unreadable exit code ($null, or a getter that throws) is UNKNOWN -- it is never
# coerced to 0. Coercing it read an unknown (possibly failed) copy as a clean
# success, which disarmed the corroborated short-copy check below. With
# $CopyExitKnown false, the branches below never treat the copy as clean on the exit
# code's say-so: they warn, latch $HadWarnings, and lean on the file counts.
$CopyExitCode = $null
try {
    $CopyExitCode = $CopyProcess.ExitCode
} catch {
    $CopyExitCode = $null
}
$CopyExitKnown = ($null -ne $CopyExitCode)

# Latch for the completion banner: any of the non-fatal WARNING paths below
# (nonzero or unreadable copy exit code, a backup folder missing its symlink manifest,
# a lower-bound fallback count, file-count mismatch, size mismatch, Claude-state copy
# failure, permission-manifest failure) sets this so the final banner can say the
# backup completed WITH WARNINGS rather than claiming an unqualified success. The
# exit status stays 0 on those paths -- the banner wording is the signal, not the
# exit code (the corroborated short-copy case below is the one that is fatal, and it
# exits before the banner).
$HadWarnings = $false

# --- Verify ---
# Count what actually landed in the host folder CONTAINER-SIDE, through a read-only
# bind mount. This is the authoritative completeness signal. Windows PowerShell 5.1
# Get-ChildItem cannot descend into folders whose Windows path is 248+ characters
# when LongPathsEnabled=0, and `-ErrorAction SilentlyContinue` hid that as a quiet
# undercount: field run 2026-09-29 counted 72,834 files where a container-side count
# of the same folder found 73,021 -- 187 files hidden (docker cp, written in Go,
# handles long paths fine). Linux `find` in the Docker VM has no such limit.
#
# $BackupCountProgram uses EXACTLY the staged count's `find` predicate and KB formula
# (pinned by tests/bash/backup_twin_parity.bats), so the two sides are comparable
# file-for-file: the root ".daaf-symlinks", a root ".daaf-permissions", and the
# ".daaf-claude-config" subtree are excluded on both. (Here the last two are written
# AFTER this check, but restore_from_backup.ps1 carries a byte-identical copy of this
# program, pinned by the same file, and runs it on finished backups.) Files and KB
# come from ONE traversal (see SNAPSHOT COUNT above): the bind mount crosses Docker
# Desktop's host file sharing, so every walk of it is slow. Quote-free like
# $StageProgram (the `\*` keeps `sh` from globbing the pattern).
#
# VISIBILITY SENTINEL: Docker Desktop has been reported to present an EMPTY folder
# for a bind mount of some locations -- a non-C: drive, a USB or network drive
# (docker/for-win#14271; not reproduced here). The program would then count 0 and
# exit 0, and the backup would report "0 files copied" on a complete copy. So the
# program also prints BACKUP_SENTINEL=1 only when it can see the root
# ".daaf-symlinks", which the staging step writes into EVERY backup (0 bytes when the
# volume has no symlinks). No sentinel = the container count is unavailable, and the
# PowerShell fallback runs with a note saying why. The sentinel is a marker line
# rather than an early `exit`, so the SAME program serves restore, which must accept
# older backups that predate the manifest (restore instead treats a count of 0 as
# unavailable).
#
# READ ERRORS: like the snapshot count (see SNAPSHOT COUNT above), the count's stderr
# goes to /tmp/count_err inside the throwaway container, and BACKUP_FILES/BACKUP_KB are
# printed only when that file is empty; otherwise BACKUP_COUNT_ERRORS=<lines> is
# printed instead, and the count is UNAVAILABLE (PowerShell fallback, with a note
# naming the errors). Without this, a `find` read error through the bind mount
# produced a short count, BACKUP_SENTINEL=1 and exit 0 -- trusted as EXACT, it could
# report "missing files" or even trip the fatal short-copy branch on a complete
# backup. `: > /tmp/count_err` first, under `set -e`: if the file cannot be created
# the program exits nonzero (count unavailable) rather than printing an unchecked count.
#
# The host path is passed by DIRECT invocation as one argument ("<path>:/b:ro"), so a
# spaced folder ("C:\Users\John Smith", "OneDrive - Org") stays one argument --
# PowerShell quotes an argument that contains whitespace -- and it never ends in a
# backslash (the ":/b:ro" suffix), so no quoting edge case applies. If this count is
# unavailable, fall back to Measure-DaafBackupTree (PowerShell, never silent:
# enumeration errors make the count a stated LOWER BOUND and latch the warnings banner).
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
Write-Host "Verifying the backup (counting files inside Docker)..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$HostCountOutput = @(docker run --rm -v "${HostPath}:/b:ro" busybox sh -c $BackupCountProgram 2>&1)
$HostCountExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
$FileCount = $null
$BackupSizeKB = $null
$HostCountBlind = $false
$HostCountErrors = $null
if ($HostCountExit -eq 0) {
    if ((Get-DaafCountMarker -Lines $HostCountOutput -Name 'BACKUP_SENTINEL') -eq 1) {
        # The program withholds BACKUP_FILES/BACKUP_KB when its count hit read errors
        # (see READ ERRORS above), so a count that parses here is error-free.
        $FileCount = Get-DaafCountMarker -Lines $HostCountOutput -Name 'BACKUP_FILES'
        $BackupSizeKB = Get-DaafCountMarker -Lines $HostCountOutput -Name 'BACKUP_KB'
        $HostCountErrors = Get-DaafCountMarker -Lines $HostCountOutput -Name 'BACKUP_COUNT_ERRORS'
    } else {
        $HostCountBlind = $true
    }
}
$CountIsLowerBound = $false
if ($null -eq $FileCount -or $null -eq $BackupSizeKB) {
    if ($null -ne $HostCountErrors -and $HostCountErrors -gt 0) {
        # Docker saw the folder but could not read all of it: its count would be short,
        # so it is not used. The PowerShell count below says whether it did better.
        Write-Host "Note: Docker hit $HostCountErrors read error(s) while counting the backup folder, so it is" -ForegroundColor Yellow
        Write-Host "      counted with PowerShell instead."
    } elseif (-not $HostCountBlind) {
        Write-Host "Note: Could not count the backup folder inside Docker (exit $HostCountExit); counting it" -ForegroundColor Yellow
        Write-Host "      with PowerShell instead."
        # No sentinel was read on this path, so the manifest's presence is unproven:
        # check it here too. (Where the count ran -- including the read-error branch
        # above -- BACKUP_SENTINEL=1 already proved the root manifest is in the copy.)
        if (-not (Test-Path -LiteralPath (Join-Path $HostPath $SymlinksManifest))) {
            Write-Host "WARNING: The backup folder is missing its $SymlinksManifest file (every backup writes one)," -ForegroundColor Yellow
            Write-Host "         so the copy did not finish cleanly."
            Write-Host "         Re-run the backup; restoring this one would not recreate symbolic links."
            $HadWarnings = $true
        }
    } elseif (Test-Path -LiteralPath (Join-Path $HostPath $SymlinksManifest)) {
        # PowerShell sees the manifest that Docker could not: the bind mount showed an
        # empty (or wrong) folder. The copy itself does not use a bind mount (docker cp
        # streams through the Docker API), so only the count is affected.
        Write-Host "Note: Docker could not see the files in the backup folder, so they are counted with" -ForegroundColor Yellow
        Write-Host "      PowerShell instead. (Docker Desktop can show an empty folder for some locations,"
        Write-Host "      such as a USB, network, or non-C: drive. The copy itself is not affected.)"
    } else {
        # Neither side sees the manifest the staging step always writes: the copy did
        # not deliver it, so restore could not recreate this backup's symbolic links.
        Write-Host "WARNING: The backup folder is missing its $SymlinksManifest file (every backup writes one)," -ForegroundColor Yellow
        Write-Host "         so the copy did not finish cleanly. Counting the files with PowerShell instead."
        Write-Host "         Re-run the backup; restoring this one would not recreate symbolic links."
        $HadWarnings = $true
    }
    $Fallback = Measure-DaafBackupTree -Root $HostPath -ExcludeRootFiles @($SymlinksManifest, $PermissionsManifest) -ExcludeRootDirs @($ClaudeSubDir)
    $FileCount = $Fallback.Files
    $BackupSizeKB = $Fallback.KB
    if ($Fallback.Errors -gt 0) {
        $CountIsLowerBound = $true
        Write-Host "WARNING: PowerShell could not read $($Fallback.Errors) folder(s) or file(s) in the backup," -ForegroundColor Yellow
        Write-Host "         most likely because of the Windows path-length limit. The count below is a"
        Write-Host "         LOWER BOUND ($FileCount+ files): the backup may be complete, but this run"
        Write-Host "         could not prove it."
        $HadWarnings = $true
    }
}
$FileCountLabel = "$FileCount"
if ($CountIsLowerBound) { $FileCountLabel = "$FileCount+" }

# Print the ACTUAL final count, not a fabricated "100%". On a truncated copy (the
# Windows symlink/special-file abort this staging step now prevents, or any other
# partial copy) an unconditional "100%" would lie about completeness.
if ($ExpectedFiles -gt 0) {
    $FinalPercent = [math]::Min(100, [math]::Floor($FileCount * 100 / $ExpectedFiles))
} else {
    $FinalPercent = 0
}
Write-Host "  Progress: $FileCountLabel / $ExpectedFiles files ($FinalPercent%)   "

# Zero files counted. When that 0 is a LOWER BOUND (the PowerShell fallback hit read
# errors), it is not evidence of an empty or failed copy -- nothing could be counted.
# It still exits 1 like the other zero-file cases: an unverifiable backup must not
# pass as good, and exit 1 makes a calling updater or migration stop instead of
# building on it. The wording says it could not be checked, and never suggests the
# volume is empty.
if ($FileCount -eq 0) {
    Write-Host ""
    if ($CountIsLowerBound) {
        Write-Host "ERROR: The backup could not be verified: neither Docker nor PowerShell could read the" -ForegroundColor Red
        Write-Host "       backup folder, so no files could be counted. This does not show the backup is"
        Write-Host "       empty, but do not rely on it. Re-run the backup, ideally from a shorter folder"
        Write-Host "       path (e.g. C:\daaf) or with Windows long-path support enabled."
        if ($CopyExitKnown -and $CopyExitCode -ne 0) {
            Write-Host "       The file copy also reported an error (exit code $CopyExitCode)."
        }
    } elseif ($CopyExitKnown -and $CopyExitCode -ne 0) {
        Write-Host "ERROR: Backup failed (exit code $CopyExitCode). Check Docker Desktop for errors." -ForegroundColor Red
    } elseif (-not $CopyExitKnown -and $ExpectedFiles -gt 0) {
        # The snapshot (or scan) held files but none arrived, and the copy's exit code
        # is unknown: this is a failed copy, not an empty volume.
        Write-Host "ERROR: Backup failed -- 0 of $ExpectedFiles expected files were copied (the copy's exit code could not be read). Check Docker Desktop for errors." -ForegroundColor Red
    } else {
        Write-Host "WARNING: Backup completed but 0 files were copied." -ForegroundColor Yellow
        Write-Host "The Docker volume may be empty. Is DAAF properly installed?"
    }
    Write-Host "Location: $HostPath\"
    Wait-AndExit 1
}

# --- Corroborated short-copy check (fatal) ---
# A nonzero docker cp exit AND a copied count short of the expected count (the
# snapshot, or the scan on the fallback path) are two independent signals that
# agree the backup is truncated -- the nonzero exit corroborates the shortfall, so no
# tolerance is applied here. A truncated backup that passed as usable could cost a
# user their data on restore, so fail hard: name the partial folder, tell them to
# delete it, and exit before the completion banner. (A nonzero exit with a FULL count
# falls through to the Note below, which latches the WITH WARNINGS banner -- warnings
# without an actual shortfall.)
#
# UNKNOWN exit code ($CopyExitKnown false): never read as clean. It always latches
# $HadWarnings, so the banner says WITH WARNINGS. A shortfall on top of it gets a loud
# WARNING, also at zero tolerance. It is deliberately NOT fatal: "unknown" is missing
# evidence, not a second signal of failure (and on the fallback path the expected
# count is the live-volume scan, which can drift slightly from the snapshot). Fatal
# stays reserved for two agreeing signals, and the WARNING tells the user not to rely
# on the backup.
#
# LOWER-BOUND count ($CountIsLowerBound, the PowerShell fallback hit read errors): the
# count is not a second signal either -- the "missing" files may only be unreadable
# to PowerShell -- so a nonzero exit with a short lower-bound count is downgraded to
# a WARNING (latched, exit 0) that says so, rather than the fatal delete-and-re-run.
if ($CopyExitKnown -and $CopyExitCode -ne 0 -and $FileCount -lt $ExpectedFiles -and -not $CountIsLowerBound) {
    Write-Host ""
    Write-Host "ERROR: Backup failed (exit code $CopyExitCode); only $FileCountLabel of $ExpectedFiles expected files were copied." -ForegroundColor Red
    Write-Host "       This backup is incomplete and must not be relied on. Delete this"
    Write-Host "       partial backup folder and re-run once the copy issue is resolved."
    Write-Host "Location: $HostPath\"
    Wait-AndExit 1
} elseif ($CopyExitKnown -and $CopyExitCode -ne 0 -and $FileCount -lt $ExpectedFiles) {
    Write-Host ""
    Write-Host "WARNING: The file copy reported an error (exit code $CopyExitCode), and PowerShell counted" -ForegroundColor Yellow
    Write-Host "         $FileCountLabel of $ExpectedFiles expected files. That count is a lower bound (some folders"
    Write-Host "         could not be read), so this run cannot tell whether files are missing. Do not"
    Write-Host "         rely on this backup until a run finishes without this warning."
    $HadWarnings = $true
} elseif ($CopyExitKnown -and $CopyExitCode -ne 0) {
    # A nonzero exit is a copy-reported problem even when the count came up full,
    # so latch the warnings banner: "Backup complete!" would overstate a run the
    # copy itself flagged. Exit status stays 0 (no shortfall, so not fatal).
    Write-Host "Note: File copy reported warnings (exit code $CopyExitCode); $FileCountLabel of $ExpectedFiles expected files were transferred." -ForegroundColor Yellow
    $HadWarnings = $true
} elseif (-not $CopyExitKnown) {
    if ($FileCount -lt $ExpectedFiles) {
        Write-Host ""
        Write-Host "WARNING: The file copy's exit code could not be read, and only $FileCountLabel of $ExpectedFiles" -ForegroundColor Yellow
        Write-Host "         expected files were copied. This backup may be incomplete -- do not rely"
        Write-Host "         on it. Re-run the backup and keep a run that finishes without this warning."
    } else {
        Write-Host "Note: The file copy's exit code could not be read; $FileCountLabel of $ExpectedFiles expected files were transferred." -ForegroundColor Yellow
        Write-Host "      The file-count and size checks are the completeness signal for this run."
    }
    $HadWarnings = $true
}

# --- File-count verification ---
# Do NOT trust docker cp's exit code as the sole failure signal: the Windows
# symlink-abort truncation surfaced with a ZERO exit on the user's run (INFERENCE:
# most likely the since-removed $null-to-0 ExitCode coercion -- see the handle cache
# after Start-Process above -- since docker cp returns the extraction error). A nonzero
# exit that ALSO comes up short on the count is already fatal (the corroborated
# short-copy branch above). This block catches the harder case -- a clean ZERO exit
# that still copied the wrong number of files -- and warns loudly (latching the WITH
# WARNINGS banner) on a mismatch in either direction beyond the tolerance below.
#
# ZERO tolerance when the snapshot markers were read: the snapshot is exactly the
# tree `docker cp` streamed, and both counts use the same predicates, so any
# difference is a real one. That closes the hole the old 1% tolerance left open --
# it hid the 2026-09-29 gap of 197 files out of 73,031 (187 hidden by the Windows
# PowerShell 5.1 long-path skip, plus 10 most likely live-volume drift between scan
# and snapshot -- a volume-vs-backup diff found every surviving pre-backup file
# present) and a probe of a FIFO-abort truncation (714 of 71,820 files, under its
# 718-file tolerance). The 1% tolerance survives ONLY on the fallback path, where
# the expected count is the live-volume scan and benign drift between scan and
# snapshot is possible, so a mismatch there is only "may be incomplete".
#
# Against the snapshot the wording follows the direction. FEWER files is a proven
# loss (unless the count is a lower bound, which cannot prove anything). MORE files
# is not a loss: something the snapshot never held landed in the folder (e.g. an
# OS-added desktop.ini/Thumbs.db/.DS_Store), so it still latches WITH WARNINGS but
# says the DAAF data appears complete.
if ($HaveStagedCounts) {
    $CountTolerance = 0
    $ExpectedLabel = "Snapshot"
} else {
    $CountTolerance = [math]::Max(1, [long][math]::Floor($TotalFiles / 100))
    $ExpectedLabel = "Source"
}
if ($HaveStagedCounts -or $TotalFiles -gt 0) {
    $CountDiff = [math]::Abs($ExpectedFiles - $FileCount)
    if ($CountDiff -gt $CountTolerance) {
        # A lower-bound count bounds the difference only one way: a shortfall is "up
        # to" it, an excess is "at least" it.
        $CountDiffLabel = "$CountDiff"
        if ($CountIsLowerBound) {
            if ($FileCount -lt $ExpectedFiles) { $CountDiffLabel = "up to $CountDiff" } else { $CountDiffLabel = "at least $CountDiff" }
            $CountDiffLabel = "$CountDiffLabel; the backup count is a lower bound"
        }
        Write-Host ""
        Write-Host "WARNING: Backup file-count mismatch." -ForegroundColor Yellow
        Write-Host "         ${ExpectedLabel}: $ExpectedFiles files, Backup: $FileCountLabel files (difference: $CountDiffLabel)"
        if (-not $HaveStagedCounts) {
            Write-Host "         The backup may be incomplete. Consider re-running."
        } elseif ($FileCount -gt $ExpectedFiles) {
            Write-Host "         The backup folder holds files that are not in the snapshot, for example"
            Write-Host "         desktop.ini, Thumbs.db or .DS_Store files added by the operating system or a"
            Write-Host "         sync app. The DAAF data itself appears complete."
        } elseif ($CountIsLowerBound) {
            Write-Host "         PowerShell could not read every folder, so this run cannot tell whether these"
            Write-Host "         files are missing or only uncounted. Do not rely on this backup until a run"
            Write-Host "         finishes without this warning."
        } else {
            Write-Host "         $CountDiff file(s) from the snapshot are missing from this backup. Do not rely on it."
            Write-Host "         One possible cause that re-running will not fix: file names Windows cannot"
            Write-Host "         store, such as names that differ only in upper/lower case, or names that"
            Write-Host "         contain characters like : * ? < > |"
        }
        $HadWarnings = $true
    }
}

# --- Size verification ---
# Compare expected vs backup logical byte sums (KB) to detect truncated files, with
# the same exclusions on both sides as the file count; the backup side comes from the
# container-side count above (or its PowerShell fallback). Same tolerance rule as the
# file count: zero against the snapshot, 1% against the live-volume scan on the
# fallback path. Against the snapshot, a size difference with EQUAL file counts means
# file contents differ, so the wording says not to rely on the backup; with unequal
# counts it points back at the file-count warning.
$SourceSizeKB = $ExpectedKB
if ($HaveStagedCounts) {
    $ToleranceKB = 0
} else {
    $ToleranceKB = [math]::Max(1, [long][math]::Floor($SourceSizeKB / 100))
}
if ($HaveStagedCounts -or ($SourceSizeKB -gt 0 -and $BackupSizeKB -gt 0)) {
    $DiffKB = [math]::Abs($SourceSizeKB - $BackupSizeKB)
    if ($DiffKB -gt $ToleranceKB) {
        $BackupSizeLabel = "${BackupSizeKB} KB"
        $DiffKBLabel = "${DiffKB} KB"
        if ($CountIsLowerBound) {
            $BackupSizeLabel = "${BackupSizeKB}+ KB"
            $DiffKBLabel = "${DiffKB} KB; the backup size is a lower bound"
        }
        Write-Host ""
        Write-Host "WARNING: Backup size mismatch." -ForegroundColor Yellow
        Write-Host "         ${ExpectedLabel}: ${SourceSizeKB} KB, Backup: $BackupSizeLabel (difference: $DiffKBLabel)"
        if (-not $HaveStagedCounts) {
            Write-Host "         The backup may be incomplete. Consider re-running."
        } elseif ($CountIsLowerBound) {
            Write-Host "         PowerShell could not read every folder, so this run cannot prove the contents"
            Write-Host "         match. Do not rely on this backup until a run finishes without this warning."
        } elseif ($FileCount -eq $ExpectedFiles) {
            Write-Host "         The file counts match, but the file contents differ in size from the"
            Write-Host "         snapshot. Do not rely on this backup."
        } else {
            Write-Host "         See the file-count mismatch above."
        }
        $HadWarnings = $true
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
    Write-Host "Backing up Claude Code state from volume $ClaudeVolumeName (credentials, session history, plugins)..."
    $ClaudeDestPath = Join-Path $HostPath $ClaudeSubDir
    New-Item -ItemType Directory -Path $ClaudeDestPath -Force | Out-Null
    # Same STAGING mechanism as the data volume above (this volume ALSO carries
    # symlinks -- e.g. codex-daaf/tmp/arg0/... -- which is why the "Failed to back
    # up the Claude Code state volume" warning appeared on Windows: `docker cp`
    # aborted on the first link). Stage into a throwaway container to strip the
    # symlinks into this subfolder's own ".daaf-symlinks" manifest (and delete any
    # special files, unreported here -- the scan above covers the data volume only),
    # then cp the stripped staged tree out. Run synchronously (this copy is small). Only
    # docker's text status lines reach stdout (the file data goes straight to disk),
    # so synchronous inline calls are pipeline-safe on PS 5.1.
    $ClaudeStageCid = $null
    $claudeCopyOk = $false
    $ClaudeStageLog = ""
    $ClaudeStagedFiles = $null
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
            # Gate on TryParse's BOOLEAN return (see the data-volume staging block
            # above): a parse failure writes 0 into the [ref], which would flip this
            # gate from "skip the copy" to "copy a partial staged tree." Parse into a
            # temp var; stay fail-closed at 1 on failure.
            $ClaudeStageStatus = 1
            $ClaudeStageStatusParsed = 0
            if ($null -ne $ClaudeStageStatusRaw -and [int]::TryParse("$ClaudeStageStatusRaw".Trim(), [ref]$ClaudeStageStatusParsed)) {
                $ClaudeStageStatus = $ClaudeStageStatusParsed
            }
            if ($ClaudeStageStatus -eq 0) {
                # Same $StageProgram, so its log carries STAGED_FILES too (unless that
                # count hit read errors, in which case the fallback below runs): read it
                # before the finally below removes the container. Used for the
                # displayed count (Get-ChildItem undercounts long paths).
                $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
                $ClaudeStageDoneLog = @(docker logs $ClaudeStageCid 2>&1)
                if ($LASTEXITCODE -eq 0) {
                    $ClaudeStagedFiles = Get-DaafCountMarker -Lines $ClaudeStageDoneLog -Name 'STAGED_FILES'
                }
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
        # Data files only. Prefer the snapshot count (the same $StageProgram, so its
        # STAGED_FILES predicate excludes the subfolder's ROOT ".daaf-symlinks" and
        # ".daaf-permissions" and a root ".daaf-claude-config" subtree); the PowerShell
        # fallback applies exactly those root exclusions so both paths count the same
        # set, and is marked "+" when it hit read errors (a lower bound, e.g. long
        # session-history paths). Display only: the Claude copy's success is judged by
        # the docker cp exit code above.
        if ($null -ne $ClaudeStagedFiles) {
            $ClaudeFileCount = "$ClaudeStagedFiles"
        } else {
            $ClaudeFallback = Measure-DaafBackupTree -Root $ClaudeDestPath -ExcludeRootFiles @($SymlinksManifest, $PermissionsManifest) -ExcludeRootDirs @($ClaudeSubDir)
            $ClaudeFileCount = "$($ClaudeFallback.Files)"
            if ($ClaudeFallback.Errors -gt 0) { $ClaudeFileCount = "$($ClaudeFallback.Files)+" }
        }
        Write-Host "Claude Code state backed up ($ClaudeFileCount files)."
        $ClaudeBackedUp = $true
    } else {
        Write-Host "WARNING: Failed to back up the Claude Code state volume." -ForegroundColor Yellow
        Write-Host "         Details from the staging scan:"
        if (-not [string]::IsNullOrWhiteSpace($ClaudeStageLog)) {
            foreach ($logLine in ($ClaudeStageLog -split "`r?`n")) {
                if ($logLine -ne "") { Write-Host "         $logLine" }
            }
        } else {
            # Empty/whitespace log: label the silence rather than omit the detail,
            # so a future stream regression is visible rather than ambiguous.
            Write-Host "         (no details could be retrieved from the staging container)"
        }
        Write-Host "         The data volume backup above is still valid."
        $HadWarnings = $true
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
# ($PermissionsManifest is declared in the Configuration section.)
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
        $HadWarnings = $true
    }
} else {
    Write-Host "WARNING: Could not record the executable-permission manifest." -ForegroundColor Yellow
    Write-Host "         The backup is still valid; on restore, file permissions may need"
    Write-Host "         manual repair if this backup is restored on a Windows host."
    $HadWarnings = $true
}

Write-Host ""
Write-Host "=========================================="
if ($HadWarnings) {
    Write-Host "  Backup completed WITH WARNINGS -- verify before relying on it"
} else {
    Write-Host "  Backup complete!"
}
Write-Host "=========================================="
Write-Host ""
Write-Host "Location: $HostPath\"
Write-Host "Files:    $FileCountLabel files copied"
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
