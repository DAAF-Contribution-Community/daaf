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
# WARNING: Restoring is a DESTRUCTIVE operation: the entire contents of the
# Docker volume are replaced with the backup contents. The backup is first copied
# into a TEMPORARY Docker volume and checked there; only after you type RESTORE is
# the live volume replaced, in one step inside Docker ("copy-then-swap"). Any
# failure before that step leaves your current data untouched.
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"
# pwsh 7.4+ only (an ordinary, unused variable on Windows PowerShell 5.1): never turn a
# native command's nonzero exit into an error record or a throw. Every docker call here
# reads $LASTEXITCODE itself (audit 04: under 'Stop' with this set to $true, pwsh 7.6
# threw NativeCommandExitException; under 'Continue' it added a "Program ... ended with
# non-zero exit code" line that could become the "Docker said:" text).
$PSNativeCommandUseErrorActionPreference = $false

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
# volume are restored data-only with a NOTE.
$ClaudeVolumeName = "${projectName}_daaf-claude-config"
$ClaudeSubDir = ".daaf-claude-config"
# Executable-permission manifest written into the backup root by backup_daaf.ps1
# (see the "Capture the executable-permission manifest" block there). Lists every
# regular file that had the owner-exec bit set at backup time. Restore uses it to
# put POSIX modes back after a Windows round-trip (NTFS) erased them. Absent on
# older backups -- restore handles that gracefully (no normalization; see Step 3d).
$PermissionsManifest = ".daaf-permissions"
# Symlink manifest written into the backup root (and the Claude subfolder root) by
# backup_daaf.ps1's staging step. Lists each symlink's path and target (TAB-
# separated). Restore replays it container-side to recreate the links that the
# staging step stripped so `docker cp` could stream a symlink-free tree on Windows.
# Current backups always contain it (0 bytes when the volume had no symlinks); absent
# only on backups that predate the feature -- restore no-ops then (see Step 3e),
# matching the ".daaf-permissions" "no manifest, no action" rule.
$SymlinksManifest = ".daaf-symlinks"
# --- Copy-then-swap names and container programs ---
# Same names, label, marker and programs as restore_from_backup.sh (see its
# "Copy-then-swap names and container programs" block for the full rationale). The
# three programs are single-quoted, quote-free (no `"`: the Windows PowerShell 5.1
# native-argument rule) and BYTE-IDENTICAL to the .sh twin's (pinned by
# tests/bash/backup_twin_parity.bats). Every name is checked by EXACT name (`docker
# volume inspect` / `docker container inspect`); `docker volume create` silently
# reuses an existing volume, so a temp volume is only created after that check found
# none. Temp volumes and prepare-phase helpers carry the label; the swap containers do
# not, so no reap can ever kill a running swap. The state marker is written into a temp
# volume right before its swap and deleted from the live volume as the swap's last
# step, so it only survives in a leftover temp volume (evidence that a swap started).
$TempVolumeName = "${VolumeName}-restore-tmp"
$ClaudeTempVolumeName = "${ClaudeVolumeName}-restore-tmp"
$SwapContainerName = "${VolumeName}-restore-swap"
$ClaudeSwapContainerName = "${ClaudeVolumeName}-restore-swap"
$RestoreLabel = "org.daaf.restore-tmp-for"
# Identity of THIS run's temp volumes (see the .sh twin's RESTORE_RUN_LABEL): a second
# label whose value is unique to this run, re-checked with `docker volume inspect
# --format {{.Labels}}` (one argument with no space or quote, so Windows PowerShell 5.1
# passes it unchanged) right after creation, before the state marker, and right before
# each swap.
$RestoreRunLabel = "org.daaf.restore-run"
$RestoreRunId = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + $PID + '-' + [guid]::NewGuid().ToString('N')
$SwapMarker = ".daaf-restore-swap-started"
$SpaceProgram = 'a=$(stat -f -c %a /dest) && s=$(stat -f -c %S /dest) && echo AVAIL_KB=$((a*s/1024)) && set -- $(du -sk /dest) && echo LIVE_KB=$1 && if test -d /src; then set -- $(du -sk /src) && echo SRC_KB=$1; fi'
$SwapProgram = 'trap : INT TERM HUP; test -f /src/.daaf-restore-swap-started || exit 3; rm -rf /dest/* /dest/.[!.]* /dest/..?* && cp -a /src/. /dest/ && rm -f /dest/.daaf-restore-swap-started'
$SwapVerifyProgram = 'export LC_ALL=C; : > /tmp/err || exit 4; for t in src dest; do cd /$t 2>>/tmp/err && { find . ! -path ./.daaf-restore-swap-started ! -type d -exec stat -c %f:%u:%g:%s:%n {} + ; find . ! -path . -type d -exec stat -c %f:%u:%g:%n {} + ; find . -type l -exec readlink {} \; ; } 2>>/tmp/err | sort 2>>/tmp/err > /tmp/$t.lst || echo LIST_FAILED_$t >> /tmp/err; done; if test -s /tmp/err; then echo SWAP_VERIFY_ERRORS=$(grep -c ^ /tmp/err); elif cmp -s /tmp/src.lst /tmp/dest.lst; then echo SWAP_VERIFY=MATCH; else echo SWAP_VERIFY=MISMATCH; fi; echo SWAP_VERIFY_ENTRIES=$(grep -c ^ /tmp/src.lst):$(grep -c ^ /tmp/dest.lst)'
# The helper image every container step runs, PINNED by digest: busybox 1.37.0,
# multi-arch OCI index (amd64, arm64/v8 and others), the tested digest below. Pinned
# because the untagged `busybox` (latest) moved to the untested busybox 1.38.0 on
# 2026-09-23 (research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/
# 04_F1_compat_audit.md). The same string is in backup_daaf.{sh,ps1},
# restore_from_backup.{sh,ps1}, migrate_daaf.{sh,ps1} and docker-compose.yml (daaf-init):
# keep every copy identical (a parity test enforces it). No `"`, space or trailing `\`,
# so it passes to docker.exe unchanged on Windows PowerShell 5.1.
$BusyboxImage = 'busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'
#
# SYNC NOTE: the container-side count programs below cannot use these variables and
# hardcode the literals ".daaf-symlinks", ".daaf-permissions" and ".daaf-claude-config":
# $BackupCountProgram (a single-quoted `@'...'@` here-string, byte-identical to
# backup_daaf.ps1's -- pinned by tests/bash/backup_twin_parity.bats) and the volume
# count program used twice, for the temporary copy (Step 3f) and for the post-restore
# count in "--- Verify ---" (single-quoted strings, identical to each other and to
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
            "version --format*" { Write-Output "29.1.3 29.1.3"; return }
            "image inspect *" { return }
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

# --- Platform guard (F1 compatibility; audit 04) ---
# This is the Windows twin, written and tested for Windows PowerShell 5.1 (and pwsh on
# Windows). Under PowerShell 7 on macOS or Linux, refuse before anything else happens
# and point to the .sh twin. Short-circuit order matters: on Windows PowerShell 5.1
# PSEdition is 'Desktop', so `-and` stops before reading $IsWindows, an automatic
# variable that does not exist there (a strict-mode error if it were read). Skipped for
# DAAF_DRY_RUN=1 (the CI smoke run under pwsh on Linux/macOS: Docker is mocked and
# nothing is changed) and for DAAF_TEST_ALLOW_CORE_NONWINDOWS=1, a TEST-ONLY hook for the
# Pester suites, which run the real script with a fake docker under pwsh on Linux.
if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows -and $env:DAAF_DRY_RUN -ne '1' -and $env:DAAF_TEST_ALLOW_CORE_NONWINDOWS -ne '1') {
    Write-Host "ERROR: This PowerShell script is for Windows. On macOS or Linux, run the restore with:" -ForegroundColor Red
    Write-Host "         bash restore_from_backup.sh"
    Write-Host "       Nothing was changed."
    Wait-AndExit 1
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
    # Old-Engine hint (F1; review round 9): same rule and text as the .sh twin (see there)
    # and backup_daaf.{sh,ps1}. A client of 25 or newer that cannot talk to an Engine older
    # than 25.0 also fails `docker info`, so the version check below is never reached. Stdout
    # only (2>$null), the last non-empty line; the hint is added only when the client's
    # major reads as 25 or newer and the Engine's version is empty or cannot be read.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $infoFailVersionOut = @(docker version --format '{{.Client.Version}} {{.Server.Version}}' 2>$null)
    $ErrorActionPreference = $savedEAP
    $infoFailVersionLine = ''
    foreach ($versionLine in $infoFailVersionOut) { if ("$versionLine".Trim() -ne '') { $infoFailVersionLine = "$versionLine".Trim() } }
    $infoFailParts = @(-split $infoFailVersionLine)
    $infoFailClient = ''
    $infoFailServer = ''
    if ($infoFailParts.Count -ge 1) { $infoFailClient = $infoFailParts[0] }
    if ($infoFailParts.Count -ge 2) { $infoFailServer = $infoFailParts[1] }
    if ($infoFailClient -match '^(\d{1,5})(\.|$)' -and [int]$Matches[1] -ge 25 -and $infoFailServer -notmatch '^\d{1,5}(\.|$)') {
        Write-Host "       If Docker is running, its Docker Engine may be older than 25.0 (Docker client $infoFailClient)."
        Write-Host "       The restore needs Docker 25.0 or newer (Docker Desktop 4.27.1 or newer)."
    }
    Wait-AndExit 1
}

# --- Docker version check (F1 compatibility; audit 04, section 3) ---
# Same rule and wording as the .sh twin (see there) and backup_daaf.{sh,ps1}: refuse when
# either side's major version is below 25 or cannot be read; a major other than the
# tested 29 only prints a NOTE. Stdout only (2>$null), so a stderr line can never be read
# as a version; the last non-empty line. The --format value has no `"` (Windows
# PowerShell 5.1 native-argument rule).
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$dockerVersionOut = @(docker version --format '{{.Client.Version}} {{.Server.Version}}' 2>$null)
$ErrorActionPreference = $savedEAP
$dockerVersionLine = ''
foreach ($versionLine in $dockerVersionOut) { if ("$versionLine".Trim() -ne '') { $dockerVersionLine = "$versionLine".Trim() } }
$dockerVersionParts = @(-split $dockerVersionLine)
$DockerClientVersion = ''
$DockerServerVersion = ''
if ($dockerVersionParts.Count -ge 1) { $DockerClientVersion = $dockerVersionParts[0] }
if ($dockerVersionParts.Count -ge 2) { $DockerServerVersion = $dockerVersionParts[1] }
$DockerVersionState = 'ok'
foreach ($dockerV in @($DockerClientVersion, $DockerServerVersion)) {
    $dockerMajor = -1
    if ($dockerV -match '^(\d{1,5})(\.|$)') { $dockerMajor = [int]$Matches[1] }
    if ($dockerMajor -lt 0) {
        $DockerVersionState = 'unreadable'
    } elseif ($dockerMajor -lt 25) {
        if ($DockerVersionState -ne 'unreadable') { $DockerVersionState = 'old' }
    } elseif ($dockerMajor -ne 29 -and $DockerVersionState -eq 'ok') {
        $DockerVersionState = 'untested'
    }
}
if ($DockerVersionState -eq 'old' -or $DockerVersionState -eq 'unreadable') {
    $dockerClientShown = 'unknown'
    if ($DockerClientVersion -ne '') { $dockerClientShown = $DockerClientVersion }
    $dockerServerShown = 'unknown'
    if ($DockerServerVersion -ne '') { $dockerServerShown = $DockerServerVersion }
    if ($DockerVersionState -eq 'old') {
        Write-Host "ERROR: This Docker version is too old for the restore (Docker client $dockerClientShown, Docker Engine $dockerServerShown)." -ForegroundColor Red
    } else {
        Write-Host "ERROR: Could not read the Docker version (Docker client $dockerClientShown, Docker Engine $dockerServerShown)." -ForegroundColor Red
    }
    Write-Host "       The restore needs Docker 25.0 or newer, for both the Docker client and Docker Engine"
    Write-Host "       (Docker Desktop 4.27.1 or newer). Update Docker, then run the restore again."
    Write-Host "       (Docker Desktop or Docker Engine is required; Podman is not supported.)"
    Write-Host "       Nothing was changed."
    Wait-AndExit 1
}
if ($DockerVersionState -eq 'untested') {
    Write-Host "NOTE: The restore has not been tested with this Docker version (Docker client $DockerClientVersion, Docker Engine $DockerServerVersion; tested: 29). Continuing."
    Write-Host ""
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker volume inspect $VolumeName 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker volume '$VolumeName' not found." -ForegroundColor Red
    Write-Host "Have you run the DAAF installer yet?"
    Wait-AndExit 1
}

# --- Helper image check (F1 compatibility; audit 04, section 3) ---
# Same as the .sh twin (see there): make sure the pinned $BusyboxImage is on this
# computer before any prompt and before the temporary copy is prepared; download it
# here (progress shown) when missing, and refuse with nothing changed when that fails.
# The pull's stdout lines are shown as they arrive and its stderr lines are kept for the
# "Docker said:" line, so the bracket is 'Continue' (field test 2026-10-05, D2: Windows
# PowerShell 5.1 drops native stderr under SilentlyContinue, even with 2>&1).
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker image inspect $BusyboxImage 2>&1
$imageInspectExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
if ($imageInspectExit -ne 0) {
    Write-Host "Downloading the small helper image busybox that the restore needs..."
    # Each stdout line is shown as it arrives (Write-Host inside the pipeline); every line
    # is also kept, and the ErrorRecords (stderr) give the "Docker said:" line.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $pullAll = @(docker pull $BusyboxImage 2>&1 | ForEach-Object {
        if ($_ -isnot [System.Management.Automation.ErrorRecord]) { Write-Host "$_" }
        $_
    })
    $pullExit = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    if ($pullExit -ne 0) {
        $pullSaid = ''
        foreach ($pullLine in @($pullAll | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] })) { if ("$pullLine".Trim() -ne '') { $pullSaid = "$pullLine".Trim() } }
        Write-Host ""
        Write-Host "ERROR: The restore needs the small helper image busybox and could not download it." -ForegroundColor Red
        Write-Host "       Check the internet connection and that Docker Desktop is running, then run the restore again."
        if ($pullSaid -ne '') { Write-Host "       Docker said: $pullSaid" }
        Write-Host "       Nothing was changed."
        Wait-AndExit 1
    }
    Write-Host ""
}

# --- Check for running containers using the volume ---
# Names from STDOUT only (review round 2): through 2>&1 a stderr line (a Docker config
# WARNING, or the error text of a failing `docker ps`) was listed as a running
# "container". A FAILED `docker ps` is not "nothing is running" -- until 2026-10-02 its
# exit code was not read here -- so refuse: nothing has been created yet. Same wording,
# outcome and exit code as the .sh twin, and the same first line as the swap-time
# re-check below.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$RunningContainers = @(docker ps --filter "volume=$VolumeName" --format '{{.Names}}' 2>$null)
$runningContainersExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
if ($runningContainersExit -ne 0) {
    Write-Host "ERROR: Could not check whether DAAF is running (docker ps failed, exit $runningContainersExit)," -ForegroundColor Red
    Write-Host "       so the restore cannot start safely. This restore has not changed anything."
    Write-Host "       Make sure Docker Desktop is running, then run the restore again."
    Wait-AndExit 1
}
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
# data-only with a NOTE.
$ClaudeBackupPath = Join-Path $SelectedPath $ClaudeSubDir
# Require the subfolder to exist AND be non-empty. An empty "$ClaudeSubDir\" dir
# (e.g., a stray pre-created folder from an interrupted backup) must NOT trigger
# the Claude restore path below -- that path REPLACES the live claude-config volume's
# contents, so restoring from an empty source would wipe the user's Claude
# Code login and session history and copy nothing back.
$HasClaudeBackup = $false
if (Test-Path -LiteralPath $ClaudeBackupPath -PathType Container) {
    $claudeItemCount = @(Get-ChildItem -LiteralPath $ClaudeBackupPath -Force -ErrorAction SilentlyContinue).Count
    if ($claudeItemCount -gt 0) { $HasClaudeBackup = $true }
}

# --- Completion-banner latch ---
# Mirrors backup_daaf.ps1's $HadWarnings: every non-fatal WARNING on the success path
# below (a free space that could not be checked, a permission or symlink replay
# failure in the temporary copy, a Claude-state symlink-replay failure, a restored
# file count that could not be verified, a temporary copy that could not be removed)
# sets this so the final banner can say the restore completed
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
# manifests: ".daaf-permissions" (consumed by Step 3d, then removed) and
# ".daaf-symlinks" (consumed by Step 3e, then removed). Neither is restored content,
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
# 'Continue', not 'SilentlyContinue': the merged output is read (field test 2026-10-05,
# D2 -- see Invoke-DaafRestoreDocker).
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$ScanCountOutput = @(docker run --rm -v "${SelectedPath}:/b:ro" $BusyboxImage sh -c $BackupCountProgram 2>&1)
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
# $true when the count below came from the PowerShell fallback (Docker could not count
# the folder). That count is never authoritative -- Windows PowerShell can miss files
# (long paths) and cannot see what `docker cp` will stream -- so the temp-copy check in
# step 3f treats it as a LOWER BOUND (the temp copy must hold at least that many).
$TotalFilesFromFallback = $false
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
    $TotalFilesFromFallback = $true
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

# ============================================================================
# Copy-then-swap
# ============================================================================
# Nothing above changed anything. From here: (1) leftovers from an earlier restore,
# (2) a free-space check, (3) copy the backup into TEMPORARY volumes and check them,
# (4) the RESTORE confirmation, (5) replace the live volumes inside Docker, (6) check
# the result and remove the temporary volumes. Until step 5 starts, every failure,
# cancel or Ctrl+C removes what this run created (the try/finally below) and leaves
# the live volumes untouched. Once step 5 has started, a temporary volume may hold the
# only complete copy, so NOTHING deletes it any more ($SwapStarted). As elsewhere in
# this script, no `exit` runs inside the try: outcomes are flags, acted on after the
# finally (calling `exit` from inside a try whose finally must run is version-fragile
# on PS 5.1). Mirrors restore_from_backup.sh step for step.
$TempCreated = $false
$ClaudeTempCreated = $false
# $true from right BEFORE a temp volume's `docker volume create` until that attempt is
# resolved (recorded in $TempCreated / $ClaudeTempCreated, or deliberately left alone by
# the Test-DaafRestoreNewTemp refusal). See Resolve-DaafRestoreAttemptedTemp (task #36;
# the .sh twin's TEMP_CREATE_ATTEMPTED / CLAUDE_TEMP_CREATE_ATTEMPTED).
$TempCreateAttempted = $false
$ClaudeTempCreateAttempted = $false
$SwapStarted = $false
$TempRemoveFailed = $false
# Why a temp volume was kept (message lines; field test 2026-10-05, D1/D2).
$TempRemoveNote = @()
# $true once the Claude Code state swap phase began: the data volume was already
# replaced and checked (the interrupt text says so; field test 2026-10-05, D3).
$ClaudeSwapPhase = $false
# $true once the state marker may have been written into a temp volume (see
# Invoke-DaafRestoreTempCleanup); the .sh twin's MARKERS_WRITTEN.
$MarkersWritten = $false
# $true when a temp volume under one of this run's names may belong to someone else:
# cleanup then skips the label reap and removes only temps that are still this run's
# (the .sh twin's TEMP_CLEANUP_CAREFUL).
$TempCleanupCareful = $false
$RerunCommand = ".\restore_from_backup.ps1"

# Run docker with the given arguments, stdout and stderr merged; returns them as
# strings. $LASTEXITCODE is docker's exit code on return.
# Field test 2026-10-05, D2: the bracket is 'Continue', NOT 'SilentlyContinue'. Windows
# PowerShell 5.1 DROPS a native command's stderr lines under SilentlyContinue even with
# 2>&1 (field probe: one line fewer than under Continue), so every Docker error text
# this script read was lost there -- no "Docker said:" line, and no "no such ..." match.
# Under Continue the stderr lines stay in the merged stream (Windows PowerShell 5.1 field
# probe: CONTINUE_LINES=2); as ErrorRecords on pwsh 7.6 (observed), inferred for 5.1.
# With 2>&1 into a variable nothing reaches the console and nothing is terminating
# (pwsh 7.6 repro under the script's top-level 'Stop'; untested on 5.1 beyond the field
# probe -- inference). The old value is restored after.
# (Captures that read stdout only, `2>$null`, and calls whose output is discarded keep
# SilentlyContinue: they read no stderr text.)
function Invoke-DaafRestoreDocker {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string[]]$DockerArgs)
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $out = @(docker @DockerArgs 2>&1 | ForEach-Object { "$_" })
    $ErrorActionPreference = $savedEAP
    return $out
}

# Like Invoke-DaafRestoreDocker, but keeps stdout and stderr APART (review round 2,
# I-A): with 2>&1 a native command's stderr lines arrive as ErrorRecord objects and its
# stdout lines as strings (observed on pwsh 7.6; Windows PowerShell 5.1 wraps native
# stderr the same way, inferred from its NativeCommandError behaviour). Use it wherever
# a VALUE in the output is matched, so a stray stderr line (a Docker config WARNING)
# can never be read as that value. Returns Out, Err (string arrays) and Exit. 'Continue'
# for the same reason as above (field test 2026-10-05, D2): under SilentlyContinue,
# Windows PowerShell 5.1 left Err empty.
function Invoke-DaafRestoreDockerSplit {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string[]]$DockerArgs)
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $all = @(docker @DockerArgs 2>&1)
    $code = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    $out = @($all | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" })
    $err = @($all | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" })
    return [pscustomobject]@{ Out = $out; Err = $err; Exit = $code }
}

# The exact-name fallback (review round 2, S3; the .sh twin's _restore_name_listed) for
# a check whose inspect failed with text that is not a recognised "no such ..." message:
# list the names, STDOUT only, and compare whole lines exactly. -Kind volume | container
# (all containers) | running (running containers only). Returns 'listed', 'absent', or
# 'failed' (the list itself failed: the check could not be made).
function Find-DaafRestoreExactName {
    [CmdletBinding()]
    param([Parameter(Mandatory)][ValidateSet('volume', 'container', 'running')][string]$Kind, [Parameter(Mandatory)][string]$Name)
    $listArgs = @('ps', '--format', '{{.Names}}')
    if ($Kind -eq 'volume') { $listArgs = @('volume', 'ls', '-q') }
    if ($Kind -eq 'container') { $listArgs = @('ps', '-a', '--format', '{{.Names}}') }
    $list = Invoke-DaafRestoreDockerSplit -DockerArgs $listArgs
    if ($list.Exit -ne 0) { return 'failed' }
    if (@($list.Out | Where-Object { "$_".Trim() -ceq $Name }).Count -gt 0) { return 'listed' }
    return 'absent'
}

# Best-effort removal of every prepare-phase helper container of this volume pair
# (exact label match): a leftover helper keeps a temp volume "in use". IDs from stdout
# only (a stderr line is not an ID).
function Invoke-DaafRestoreHelperReap {
    [CmdletBinding()]
    param()
    foreach ($lbl in @($VolumeName, $ClaudeVolumeName)) {
        $ids = Invoke-DaafRestoreDockerSplit -DockerArgs @('ps', '-aq', '--filter', "label=$RestoreLabel=$lbl")
        if ($ids.Exit -ne 0) { continue }
        foreach ($id in $ids.Out) {
            if ("$id".Trim() -ne '') { $null = Invoke-DaafRestoreDocker -DockerArgs @('rm', '-f', "$id".Trim()) }
        }
    }
}

# Remove the temp volumes this run created; a no-op once a swap has started, unless
# -Final (after every check passed). Sets $TempRemoveFailed when one is kept. With
# -Final -- and on any call once a marker may have been written ($MarkersWritten) --
# each temp volume's state marker is deleted first (best-effort), so a temp copy that
# then cannot be removed is not later reported as a restore that had "started
# replacing" the data. With $TempCleanupCareful the label reap is skipped and a temp
# that no longer carries this run's identity label is left alone (and no longer
# counted as this run's) -- consistency review round 2 (SF2); the .sh twin's
# TEMP_CLEANUP_CAREFUL. A temp whose create was attempted but not yet recorded is
# removed only when it is provably this run's (task #36,
# Resolve-DaafRestoreAttemptedTemp).
function Invoke-DaafRestoreTempCleanup {
    [CmdletBinding()]
    param([switch]$Final)
    if ($script:SwapStarted -and -not $Final) { return }
    $script:TempRemoveFailed = $false
    $script:TempRemoveNote = @()
    Resolve-DaafRestoreAttemptedTemp
    $unmark = ($Final -or $script:MarkersWritten)
    if ($script:TempCleanupCareful) {
        if ($script:TempCreated -and -not (Test-DaafRestoreTempIdentity -Name $TempVolumeName)) { $script:TempCreated = $false }
        if ($script:ClaudeTempCreated -and -not (Test-DaafRestoreTempIdentity -Name $ClaudeTempVolumeName)) { $script:ClaudeTempCreated = $false }
    } else {
        Invoke-DaafRestoreHelperReap
    }
    # Field test 2026-10-05, D1: each removal goes through Invoke-DaafRestoreVolumeRemoval
    # (stopped holders first, then the volume); careful cleanup removes no holder. A temp
    # that is kept stays this run's ($TempCreated) and its reason is kept for the message.
    if ($script:TempCreated) {
        if ($unmark) { $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$VolumeName", '-v', "${TempVolumeName}:/dest", $BusyboxImage, 'rm', '-f', "/dest/$SwapMarker") }
        $removal = Invoke-DaafRestoreVolumeRemoval -Name $TempVolumeName -KeepHolders:$script:TempCleanupCareful
        if ($removal.Result -eq 'removed') { $script:TempCreated = $false } else {
            $script:TempRemoveFailed = $true
            if ($script:TempRemoveNote.Count -eq 0) { $script:TempRemoveNote = @(Get-DaafRestoreRemovalNote -Removal $removal) }
        }
    }
    if ($script:ClaudeTempCreated) {
        if ($unmark) { $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$ClaudeVolumeName", '-v', "${ClaudeTempVolumeName}:/dest", $BusyboxImage, 'rm', '-f', "/dest/$SwapMarker") }
        $removal = Invoke-DaafRestoreVolumeRemoval -Name $ClaudeTempVolumeName -KeepHolders:$script:TempCleanupCareful
        if ($removal.Result -eq 'removed') { $script:ClaudeTempCreated = $false } else {
            $script:TempRemoveFailed = $true
            if ($script:TempRemoveNote.Count -eq 0) { $script:TempRemoveNote = @(Get-DaafRestoreRemovalNote -Removal $removal) }
        }
    }
}

# The last non-empty line of Docker's stderr text, trimmed ('' when there is none): the
# "Docker said:" text of a failure message (field test 2026-10-05, D2).
# -PreferCopyCause (docker cp only; review round 6, R6): the line that names the CAUSE
# wins over the last line, which is only the consequence (field test Run 3b: "Can't
# add file ...rt_n.txt to tar: open ...\rt_n.txt: Access is denied.", then "Error
# response from daemon: unexpected EOF"). In order: (1) the FIRST non-empty line that
# contains "denied" (case-insensitive); else (2) the FIRST non-empty line that contains
# "Can't add file" (delta review of round 7, SUGGESTION 2: Windows localises "Access is
# denied.", so (1) can miss on a non-English system, but Docker's own "Can't add file"
# text is not localised and names the file); else (3) the last non-empty line. The line
# is NOT shortened, although it can be long (about 230 characters in Run 3b): it names
# the file to fix, a deep path can fill most of it, and the console wraps it; any fixed
# cut could lose that path.
function Get-DaafRestoreDockerSaid {
    [CmdletBinding()]
    param([AllowNull()][object[]]$Lines, [switch]$PreferCopyCause)
    $said = @(@($Lines) | ForEach-Object { "$_".Trim() } | Where-Object { $_ -ne '' })
    if ($said.Count -eq 0) { return '' }
    if ($PreferCopyCause) {
        $denied = @($said | Where-Object { $_ -match 'denied' })
        if ($denied.Count -gt 0) { return $denied[0] }
        $cantAdd = @($said | Where-Object { $_.Contains("Can't add file") })
        if ($cantAdd.Count -gt 0) { return $cantAdd[0] }
    }
    return $said[$said.Count - 1]
}

# Field test 2026-10-05, D1: remove temp volume -Name together with the STOPPED
# containers that still reference it. A Ctrl+C between `docker run`'s create and start
# leaves a never-started ("created") container -- `--rm` acts only on exit, and an
# unlabelled one (the swap check, the space check, the marker probe) escapes the label
# reap -- which keeps the volume "in use"; it does not go away on its own while Docker
# keeps running (a Docker restart is expected to remove it: moby restore(), inference).
# Holders come from STDOUT only (a stderr line is not an ID): `docker ps -a --filter
# volume=<temp>`. Moby's `volume` filter matches a mount's volume NAME (a bind's source)
# or its DESTINATION exactly, several values OR'd (daemon/list.go, read 2026-10-05);
# a temp name never starts with "/", so it cannot match a destination. A holder in
# `created`, `exited` or `dead` is removed with a PLAIN `docker rm` (never -f): the daemon
# refuses a running one (daemon/delete.go: "stop the container before removing or
# force remove"), so a container that started since the list survives, and `docker rm`
# never removes a NAMED volume (the live one stays). Any other state -- running,
# restarting, paused, removing, or one not known here -- means another restore may
# still be using it: nothing is removed. A failed list is "could not check", never "no
# holders". -KeepHolders (careful cleanup, SF2: the temp may be another restore's)
# skips the holders; -CheckOnly only lists them. Only this run's two temp names are ever
# removed. Returns Result (removed | removable (-CheckOnly) | busy | listfailed |
# failed), Said (Docker's last stderr line, '' when none) and PsExit (docker ps's exit).
function Invoke-DaafRestoreVolumeRemoval {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name, [switch]$KeepHolders, [switch]$CheckOnly)
    if (@($TempVolumeName, $ClaudeTempVolumeName) -cnotcontains $Name) {
        return [pscustomobject]@{ Result = 'failed'; Said = ''; PsExit = 0 }
    }
    $holderIds = @()
    if (-not $KeepHolders) {
        $holders = Invoke-DaafRestoreDockerSplit -DockerArgs @('ps', '-a', '--filter', "volume=$Name", '--format', '{{.ID}} {{.State}}')
        if ($holders.Exit -ne 0) {
            return [pscustomobject]@{ Result = 'listfailed'; Said = (Get-DaafRestoreDockerSaid -Lines $holders.Err); PsExit = $holders.Exit }
        }
        foreach ($line in $holders.Out) {
            $fields = @("$line".Trim() -split '\s+')
            if ($fields[0] -eq '') { continue }
            $state = ''
            if ($fields.Count -ge 2) { $state = $fields[1].ToLowerInvariant() }
            if (@('created', 'exited', 'dead') -notcontains $state) {
                return [pscustomobject]@{ Result = 'busy'; Said = ''; PsExit = 0 }
            }
            $holderIds += $fields[0]
        }
    }
    if ($CheckOnly) { return [pscustomobject]@{ Result = 'removable'; Said = ''; PsExit = 0 } }
    foreach ($id in $holderIds) {
        $rmHolder = Invoke-DaafRestoreDockerSplit -DockerArgs @('rm', $id)
        if ($rmHolder.Exit -ne 0) {
            return [pscustomobject]@{ Result = 'failed'; Said = (Get-DaafRestoreDockerSaid -Lines $rmHolder.Err); PsExit = 0 }
        }
    }
    $rmVolume = Invoke-DaafRestoreDockerSplit -DockerArgs @('volume', 'rm', $Name)
    if ($rmVolume.Exit -ne 0) {
        return [pscustomobject]@{ Result = 'failed'; Said = (Get-DaafRestoreDockerSaid -Lines $rmVolume.Err); PsExit = 0 }
    }
    return [pscustomobject]@{ Result = 'removed'; Said = ''; PsExit = 0 }
}

# Why a temp volume was kept, as message lines (none when Docker gave no reason).
function Get-DaafRestoreRemovalNote {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Removal)
    $note = @()
    if ($Removal.Result -eq 'busy') { $note += "Something is still using it; another restore may still be running." }
    if ($Removal.Result -eq 'listfailed') { $note += "Could not check what is using it (docker ps failed, exit $($Removal.PsExit))." }
    if ($Removal.Said -ne '') { $note += "Docker said: $($Removal.Said)" }
    return $note
}

# How to remove temp volume(s) -Volumes by hand (field test 2026-10-05, D1): the
# removal command, then -- for a volume Docker says is in use -- how to find and remove
# the container that holds it. -Lead is the message's indent; commands get two more.
function Write-DaafRestoreRemoveHint {
    [CmdletBinding()]
    param([string]$Lead = '', [string]$Volumes = '')
    $filters = @(@($Volumes -split ' ' | Where-Object { $_ -ne '' }) | ForEach-Object { "--filter volume=$_" }) -join ' '
    Write-Host "$Lead  docker volume rm $Volumes"
    Write-Host "${Lead}If Docker says it is in use, first run"
    Write-Host "$Lead  docker ps -a $filters"
    Write-Host "${Lead}and remove each container it lists with docker rm <ID>, then try again."
}

# The "kept temporary copy" lines after a cleanup that could not remove one: why (when
# known), and how to remove it by hand. -Lead is the message's indent.
function Write-DaafRestoreKeptTempHint {
    [CmdletBinding()]
    param([string]$Lead = '')
    Write-Host "${Lead}The temporary copy could not be removed."
    foreach ($noteLine in $script:TempRemoveNote) { Write-Host "$Lead$noteLine" }
    Write-Host "${Lead}To free the space it uses, run:"
    Write-DaafRestoreRemoveHint -Lead $Lead -Volumes (Get-DaafRestoreKeptTempList)
}

# The temp volumes this run still holds, space-separated (for removal commands).
function Get-DaafRestoreKeptTempList {
    [CmdletBinding()]
    param()
    $names = @()
    if ($script:TempCreated) { $names += $TempVolumeName }
    if ($script:ClaudeTempCreated) { $names += $ClaudeTempVolumeName }
    return ($names -join ' ')
}

# A KB figure as GB with one decimal (invariant culture: same text as the .sh twin).
function Format-DaafRestoreGB {
    [CmdletBinding()]
    param([long]$KB)
    return ([double]$KB / 1048576).ToString('F1', [Globalization.CultureInfo]::InvariantCulture)
}

# $true when the leftover check found that an earlier restore had started replacing the
# live data, or could not tell: "nothing changed" messages then say that THIS restore
# changed nothing but the data may still be incomplete from the earlier one.
$EarlierSwapStarted = $false

# The "nothing was changed" sentence for refusals, cancels and interrupts before any
# swap (the .sh twin's _restore_unchanged). -First = text before it on its first line,
# -Indent = indent for a continuation line.
function Write-DaafRestoreUnchanged {
    [CmdletBinding()]
    param([string]$First = '', [string]$Indent = '')
    if ($script:EarlierSwapStarted) {
        Write-Host "${First}This restore did not change anything, but your DAAF data may still be"
        Write-Host "${Indent}incomplete from the earlier restore. Run the restore again to finish it."
    } else {
        Write-Host "${First}Your DAAF data has not been changed."
    }
}

# $true when the volume still carries THIS run's identity label ($RestoreRunLabel).
# Any other answer -- another token, no such label, no such volume, or an inspect that
# failed -- is "not ours". stdout only: an error line must not be read as a label.
function Test-DaafRestoreTempIdentity {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $labelLines = @(docker volume inspect --format '{{.Labels}}' $Name 2>$null)
    $inspectExit = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    if ($inspectExit -ne 0) { return $false }
    $text = ((@($labelLines) | ForEach-Object { "$_" }) -join ' ').Trim()
    $text = ($text -replace '^map\[', '') -replace '\]$', ''
    return (@($text -split ' ') -ccontains "${RestoreRunLabel}:$RestoreRunId")
}

# Task #36 (review 32q, I-3): a Ctrl+C during a temp volume's `docker volume create`, or
# during Test-DaafRestoreNewTemp's `docker run`, stops the try BEFORE $TempCreated
# ($ClaudeTempCreated) is set, so the finally's cleanup skipped the new, empty, labelled
# temp volume. For a create attempt that was never resolved, count the temp as this
# run's (so the usual removal path -- holders, the kept-copy note -- applies) ONLY when
# it exists AND still carries THIS run's identity label: `docker volume create` silently
# reuses an existing volume and keeps its labels, so a reused leftover or another
# window's temp fails the test and is left alone, and an inspect that fails is "not
# ours" (never read as "absent" or as "ours"). No docker call is made when no attempt is
# open. Clears the attempt flags. The .sh twin's _restore_adopt_attempted_temps.
# SYNC NOTE: the .sh twin also calls it from its EXIT handler (any other exit); here the
# finally's Invoke-DaafRestoreTempCleanup covers every exit from the try.
function Resolve-DaafRestoreAttemptedTemp {
    [CmdletBinding()]
    param()
    if ($script:TempCreateAttempted -and -not $script:TempCreated -and (Test-DaafRestoreTempIdentity -Name $TempVolumeName)) { $script:TempCreated = $true }
    $script:TempCreateAttempted = $false
    if ($script:ClaudeTempCreateAttempted -and -not $script:ClaudeTempCreated -and (Test-DaafRestoreTempIdentity -Name $ClaudeTempVolumeName)) { $script:ClaudeTempCreated = $true }
    $script:ClaudeTempCreateAttempted = $false
}

# $true when inspect (or leftover rm) output says the object does not exist
# (case-insensitive). Any other failure is "could not check", never "absent".
function Test-DaafRestoreNotFound {
    [CmdletBinding()]
    param([AllowNull()][object[]]$Lines)
    $text = (@($Lines) | ForEach-Object { "$_" }) -join ' '
    return ($text -match 'no such (volume|container|object)')
}

# $true when $SwapVerifyProgram output proves a match: SWAP_VERIFY=MATCH AND
# SWAP_VERIFY_ENTRIES=n:n with equal counts -- and, with -NonEmpty, n > 0 (two EMPTY
# trees, e.g. a vanished temp volume that Docker re-created empty, otherwise "match").
# The Claude volume may legitimately be empty, so it is checked without -NonEmpty.
function Test-DaafRestoreSwapChecked {
    [CmdletBinding()]
    param([AllowNull()][object[]]$Lines, [switch]$NonEmpty)
    if (@(@($Lines) | Where-Object { "$_".Trim() -ceq 'SWAP_VERIFY=MATCH' }).Count -eq 0) { return $false }
    $srcEntries = $null
    $destEntries = $null
    foreach ($line in @($Lines)) {
        if ("$line".Trim() -match '^SWAP_VERIFY_ENTRIES=(\d+):(\d+)$') {
            $srcEntries = [long]$Matches[1]
            $destEntries = [long]$Matches[2]
        }
    }
    if ($null -eq $srcEntries -or $srcEntries -ne $destEntries) { return $false }
    if ($NonEmpty -and $srcEntries -eq 0) { return $false }
    return $true
}

# The after-swap failure text: the ERROR lines given, then how to finish (the temp
# volumes are KEPT; they may hold the only complete copy). The caller exits 1.
# -ClaudeOnly (review round 2, S5): a Claude Code state failure AFTER the data swap
# succeeded and was checked -- say plainly that the project files are in place and only
# the login and history are not (the .sh twin's _restore_fail_claude_after_data).
# -ClaudeSwapRan (review round 3, S-a): the Claude swap container ran, so the old login
# may be erased too -- say so, and that the restore puts the backup's back.
function Write-DaafRestoreSwapFailure {
    [CmdletBinding()]
    param([string[]]$Lines, [switch]$ClaudeOnly, [switch]$ClaudeSwapRan)
    Write-Host ""
    foreach ($line in $Lines) { Write-Host $line -ForegroundColor Red }
    if ($ClaudeOnly -and $ClaudeSwapRan) {
        Write-Host "       Your project files (DAAF data) were restored and checked. Only the Claude Code"
        Write-Host "       login and session history were not restored."
        Write-Host "       Your previous Claude Code login may also be gone now; running the restore again"
        Write-Host "       puts the backup's login and history back."
        Write-Host "       The checked copy of the backup is"
    } elseif ($ClaudeOnly) {
        Write-Host "       Your project files (DAAF data) were restored and checked. Only the Claude Code"
        Write-Host "       login and session history were not restored. The checked copy of the backup is"
    } else {
        Write-Host "       Your DAAF data may now be incomplete. The checked copy of the backup is"
    }
    Write-Host "       kept in Docker (volume(s): $(Get-DaafRestoreKeptTempList)), and your backup"
    Write-Host "       folder $SelectedName\ is unchanged. To finish, run this restore again"
    Write-Host "       and choose the same backup:"
    Write-Host "         $RerunCommand"
    Write-Host "       It will offer to remove the leftover copy (answer y) and then redo the restore."
}

# Delete the state marker from temp volume -Name if it still carries this run's identity
# label (best-effort; review round 2, S2). Used when a refusal keeps this run's temps.
function Clear-DaafRestoreOwnMarker {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)
    if (Test-DaafRestoreTempIdentity -Name $Name) {
        $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '-v', "${Name}:/dest", $BusyboxImage, 'rm', '-f', "/dest/$SwapMarker")
    }
}

# An exact-name check that FAILED for a reason other than "no such ...", whose
# exact-name list (Find-DaafRestoreExactName) failed too: refuse.
function Write-DaafRestoreInspectFailure {
    [CmdletBinding()]
    param([string]$Kind, [AllowNull()][object[]]$Lines)
    $first = @(@($Lines) | ForEach-Object { "$_".Trim() } | Where-Object { $_ -ne '' }) | Select-Object -First 1
    Write-Host ""
    Write-Host "ERROR: Could not check for a temporary copy left by an earlier restore (docker" -ForegroundColor Red
    Write-Host "       $Kind inspect failed: $first)."
    Write-Host "       This restore has not changed anything. Make sure Docker Desktop is running,"
    Write-Host "       then run the restore again. If this keeps happening, restart Docker Desktop"
    Write-Host "       and try again."
}

# A leftover temp volume that something still uses (-Removal.Result busy) or whose users
# could not be listed (listfailed): refuse (field test 2026-10-05, D1). The caller exits 1.
function Write-DaafRestoreLeftoverRefusal {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Volume, [Parameter(Mandatory)][object]$Removal)
    Write-Host ""
    if ($Removal.Result -eq 'busy') {
        Write-Host "ERROR: Something is still using the temporary copy left by the earlier restore" -ForegroundColor Red
        Write-Host "       (Docker volume '$Volume'), so it was not removed. Another restore may"
        Write-Host "       still be running."
        Write-DaafRestoreUnchanged -First '       ' -Indent '       '
        Write-Host "       Wait a few minutes and close any other restore window, then run this"
        Write-Host "       restore again."
    } else {
        Write-Host "ERROR: Could not check what is using the temporary copy left by the earlier" -ForegroundColor Red
        Write-Host "       restore (Docker volume '$Volume'; docker ps failed, exit $($Removal.PsExit)), so it was not removed."
        if ($Removal.Said -ne '') { Write-Host "       Docker said: $($Removal.Said)" }
        Write-DaafRestoreUnchanged -First '       ' -Indent '       '
        Write-Host "       Make sure Docker Desktop is running, then run this restore again."
    }
}

# --- (1) Leftovers from an earlier restore ---
# A RUNNING swap container: refuse. A leftover temp volume or a stopped swap
# container: offer to remove it (y/n). The prompt appears ONLY when a leftover exists.
$LeftoverVolumes = @()
$LeftoverContainers = @()
# Review round 2 (I-A): the running state is read from STDOUT only, and the swap counts
# as running when ANY line is exactly "true". (Read through 2>&1 and joined, a stderr
# line made a RUNNING swap look stopped, and the user was then offered `docker rm -f`
# of a live swap.) (S3) Error text that is not a recognised "no such ..." message falls
# back to the exact-name lists before the check is given up as "could not check".
foreach ($sc in @($SwapContainerName, $ClaudeSwapContainerName)) {
    $scCheck = Invoke-DaafRestoreDockerSplit -DockerArgs @('container', 'inspect', '--format', '{{.State.Running}}', $sc)
    $scRunning = (@($scCheck.Out | Where-Object { "$_".Trim() -ceq 'true' }).Count -gt 0)
    if ($scCheck.Exit -ne 0) {
        if (Test-DaafRestoreNotFound -Lines $scCheck.Err) { continue }
        $scListed = Find-DaafRestoreExactName -Kind 'container' -Name $sc
        if ($scListed -eq 'absent') { continue }
        if ($scListed -eq 'listed') {
            # It exists: the running-only list says whether it runs.
            $scListed = Find-DaafRestoreExactName -Kind 'running' -Name $sc
            $scRunning = ($scListed -eq 'listed')
        }
        if ($scListed -eq 'failed') {
            Write-DaafRestoreInspectFailure -Kind 'container' -Lines $scCheck.Err
            Wait-AndExit 1
        }
    }
    if ($scRunning) {
        Write-Host ""
        Write-Host "ERROR: An earlier restore is still replacing your DAAF data inside Docker" -ForegroundColor Red
        Write-Host "       (Docker container '$sc' is running). Wait a few minutes for it to"
        Write-Host "       finish, then run this restore again. This restore has not changed anything."
        Write-Host "       If this keeps happening, restart Docker Desktop and try again."
        Wait-AndExit 1
    }
    $LeftoverContainers += $sc
}
foreach ($tv in @($TempVolumeName, $ClaudeTempVolumeName)) {
    $tvCheck = Invoke-DaafRestoreDockerSplit -DockerArgs @('volume', 'inspect', $tv)
    if ($tvCheck.Exit -ne 0) {
        if (Test-DaafRestoreNotFound -Lines $tvCheck.Err) { continue }
        $tvListed = Find-DaafRestoreExactName -Kind 'volume' -Name $tv
        if ($tvListed -eq 'absent') { continue }
        if ($tvListed -eq 'failed') {
            Write-DaafRestoreInspectFailure -Kind 'volume' -Lines $tvCheck.Err
            Wait-AndExit 1
        }
    }
    $LeftoverVolumes += $tv
}
if (($LeftoverVolumes.Count + $LeftoverContainers.Count) -gt 0) {
    # Did that earlier restore start replacing live data? 0 = no, 1 = yes, 2 = unknown.
    $SwapEvidence = 0
    if ($LeftoverContainers.Count -gt 0) { $SwapEvidence = 1 }
    foreach ($tv in $LeftoverVolumes) {
        $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '-v', "${tv}:/src:ro", $BusyboxImage, 'sh', '-c', "test ! -e /src/$SwapMarker || exit 3")
        if ($LASTEXITCODE -eq 3) { $SwapEvidence = 1 }
        elseif ($LASTEXITCODE -ne 0 -and $SwapEvidence -eq 0) { $SwapEvidence = 2 }
    }
    Write-Host ""
    Write-Host "A temporary copy left behind by an earlier restore that did not finish was found:"
    foreach ($tv in $LeftoverVolumes) { Write-Host "  - Docker volume '$tv'" }
    foreach ($sc in $LeftoverContainers) { Write-Host "  - Docker container '$sc' (stopped)" }
    if ($SwapEvidence -eq 1) {
        Write-Host "That earlier restore had started replacing your DAAF data, so your current"
        Write-Host "DAAF data may be incomplete. Continuing redoes the restore from the backup"
        Write-Host "folder you chose."
    } elseif ($SwapEvidence -eq 2) {
        Write-Host "It could not be checked whether that earlier restore had started replacing"
        Write-Host "your DAAF data, so your current DAAF data may be incomplete. Continuing redoes"
        Write-Host "the restore from the backup folder you chose."
    } else {
        Write-Host "That earlier restore stopped before it replaced anything, so your current"
        Write-Host "DAAF data was not changed by it."
    }
    if ($SwapEvidence -ne 0) { $EarlierSwapStarted = $true }
    Write-Host "Your backup folders are not affected, so this temporary copy is not needed."
    Write-Host "If another restore window is still open, answer n."
    Write-Host ""
    # End of input: Read-Host returns $null (observed on pwsh 7), which is a "no" here.
    $LeftoverChoice = Read-Host "Remove it and continue? (y/n)"
    if ($LeftoverChoice -ne "y" -and $LeftoverChoice -ne "Y") {
        Write-Host ""
        Write-DaafRestoreUnchanged -First 'Restore cancelled. '
        Write-Host "To remove the temporary copy later, run:"
        if ($LeftoverContainers.Count -gt 0) { Write-Host "  docker rm $($LeftoverContainers -join ' ')" }
        if ($LeftoverVolumes.Count -gt 0) { Write-DaafRestoreRemoveHint -Lead '' -Volumes ($LeftoverVolumes -join ' ') }
        Wait-AndExit 0
    }
    # Field test 2026-10-05, D1: a never-started container left by the earlier restore's
    # Ctrl+C still references its temp volume (and the live one), so `docker volume rm`
    # failed every time. Every leftover volume's holders are listed FIRST, before anything
    # is removed: one in use (or a list that fails) refuses here, with nothing removed;
    # stopped ones are removed with the volume below (Invoke-DaafRestoreVolumeRemoval).
    foreach ($tv in $LeftoverVolumes) {
        $leftoverCheck = Invoke-DaafRestoreVolumeRemoval -Name $tv -CheckOnly
        if ($leftoverCheck.Result -ne 'removable') {
            Write-DaafRestoreLeftoverRefusal -Volume $tv -Removal $leftoverCheck
            Wait-AndExit 1
        }
    }
    Invoke-DaafRestoreHelperReap
    $LeftoverFailed = $false
    $LeftoverSaid = ''
    # Review round 6 (R5): each leftover swap container -- found NOT running before the
    # prompt -- is removed with a PLAIN `docker rm` (never -f). The y/n prompt can wait
    # for any length of time, and a restore started meanwhile in another window runs its
    # swap under the SAME name; the daemon refuses to remove a running container without
    # -f (daemon/delete.go: "stop the container before removing or force remove"), so
    # that swap is never killed. A failed removal stops here: no leftover volume is
    # touched (a running swap may be using the temp) and the failure message below shows
    # Docker's reason. Delta review of round 7 (ISSUE 1): a swap container that is GONE by
    # now (its --rm finished, Docker restarted, another window removed it) counts as
    # removed. A plain rm of a missing container exits 1 with "No such container" (docker
    # CLI cli/command/container/rm.go at v29.1.3 ignores not-found only for -f), so that
    # text is read as success here. Any other failure -- still running, or a removal
    # already in progress -- still stops here with nothing removed.
    foreach ($sc in $LeftoverContainers) {
        $scRemoval = Invoke-DaafRestoreDockerSplit -DockerArgs @('rm', $sc)
        if ($scRemoval.Exit -ne 0) {
            if (Test-DaafRestoreNotFound -Lines $scRemoval.Err) { continue }
            $LeftoverFailed = $true
            if ($LeftoverSaid -eq '') { $LeftoverSaid = Get-DaafRestoreDockerSaid -Lines $scRemoval.Err }
        }
    }
    if (-not $LeftoverFailed) {
        foreach ($tv in $LeftoverVolumes) {
            $leftoverRemoval = Invoke-DaafRestoreVolumeRemoval -Name $tv
            if ($leftoverRemoval.Result -eq 'busy' -or $leftoverRemoval.Result -eq 'listfailed') {
                Write-DaafRestoreLeftoverRefusal -Volume $tv -Removal $leftoverRemoval
                Wait-AndExit 1
            }
            if ($leftoverRemoval.Result -ne 'removed') {
                $LeftoverFailed = $true
                if ($LeftoverSaid -eq '') { $LeftoverSaid = $leftoverRemoval.Said }
            }
        }
    }
    if ($LeftoverFailed) {
        Write-Host ""
        Write-Host "ERROR: Could not remove the temporary copy left by the earlier restore." -ForegroundColor Red
        if ($LeftoverSaid -ne '') { Write-Host "       Docker said: $LeftoverSaid" }
        Write-DaafRestoreUnchanged -First '       ' -Indent '       '
        Write-Host "       Make sure no other restore is running (and Docker Desktop is running), then"
        Write-Host "       run this restore again, or remove it yourself with:"
        if ($LeftoverContainers.Count -gt 0) { Write-Host "         docker rm $($LeftoverContainers -join ' ')" }
        if ($LeftoverVolumes.Count -gt 0) { Write-DaafRestoreRemoveHint -Lead '       ' -Volumes ($LeftoverVolumes -join ' ') }
        Wait-AndExit 1
    }
    Write-Host "Removed the leftover temporary copy."
}

# --- (2) Free space inside Docker ---
# Same rule as the .sh twin: refuse below max(B, 2B - L) + max(10% of B, 1 GiB),
# measured inside Docker only; unmeasurable -> a latched WARNING and continue. B is
# the scan's data KB plus the Claude subfolder's KB (a PowerShell count of a small,
# shallow folder -- only an estimate for this check, never a verification).
$NeedBKB = [long][math]::Floor($TotalSizeBytes / 1024)
if ($HasClaudeBackup) {
    $claudeMeasure = Measure-DaafBackupTree -Root $ClaudeBackupPath
    $NeedBKB += $claudeMeasure.KB
}
$SpaceMarginKB = [long][math]::Max([math]::Floor($NeedBKB / 10), 1048576)
$SpaceOutput = @(Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '-v', "${VolumeName}:/dest:ro", $BusyboxImage, 'sh', '-c', $SpaceProgram))
$spaceExit = $LASTEXITCODE
$AvailKB = Get-DaafCountMarker -Lines $SpaceOutput -Name 'AVAIL_KB'
$LiveKB = Get-DaafCountMarker -Lines $SpaceOutput -Name 'LIVE_KB'
$SpaceKnown = ($spaceExit -eq 0 -and $null -ne $AvailKB -and $null -ne $LiveKB)
if ($SpaceKnown) {
    $SpaceNeededKB = [long][math]::Max($NeedBKB, 2 * $NeedBKB - $LiveKB) + $SpaceMarginKB
    if ($AvailKB -lt $SpaceNeededKB) {
        Write-Host ""
        Write-Host "ERROR: There is not enough free space inside Docker for this restore." -ForegroundColor Red
        Write-Host "       The restore needs about $(Format-DaafRestoreGB $SpaceNeededKB) GB free inside Docker (it makes a temporary"
        Write-Host "       copy of the backup first, then replaces your current data); Docker has"
        Write-Host "       $(Format-DaafRestoreGB $AvailKB) GB free. Free up space for Docker (for example, delete unused"
        Write-Host "       images in Docker Desktop, or free space on the drive that holds Docker's"
        Write-Host "       data), then run the restore again."
        Write-DaafRestoreUnchanged -First '       ' -Indent '       '
        Wait-AndExit 1
    }
} else {
    # L unknown: quote the worst case (L = 0).
    $SpaceNeededKB = 2 * $NeedBKB + $SpaceMarginKB
    Write-Host ""
    Write-Host "WARNING: Could not check the free space inside Docker before the restore." -ForegroundColor Yellow
    Write-Host "         The restore needs up to about $(Format-DaafRestoreGB $SpaceNeededKB) GB free inside Docker. If it"
    Write-Host "         runs out while preparing, it stops without changing your DAAF data."
    $HadWarnings = $true
}

# --- (3) .. (5): prepare, confirm, swap (cleanup-safe) ---
$PrepFail = $null       # ERROR lines: stopped before any swap (nothing changed)
$SwapFail = $null       # ERROR lines: a swap failed or did not check out (temps kept)
$Cancelled = $false
$ChangedTemp = $null    # a temp volume that is no longer this run's: refuse, remove nothing
$SwapFailClaudeOnly = $false  # $SwapFail came after the data swap was replaced and checked (S5)
$ClaudeSwapRan = $false       # the Claude swap container ran (any exit but its own refusal, 3; S-a)
$ReachedEnd = $false
$Faulted = $false             # an unexpected error ended the try (set by its catch; never a Ctrl+C)
# Right after `docker volume create`: $true when the volume carries THIS run's identity
# label (a reused existing volume keeps its own labels) AND is empty (`find /dest
# -mindepth 1` prints nothing on STDOUT; review round 2: a merged stderr line, e.g. a
# Docker config WARNING, once made every new temp look non-empty -- a `find` that hits
# an error still exits nonzero, which fails the check). Otherwise it may hold another
# restore's copy, and it is left alone (the caller closes its create attempt before
# the cleanup runs). A Ctrl+C DURING the check never reaches this verdict: the finally
# then removes the temp only if it carries this run's identity label (task #36,
# Resolve-DaafRestoreAttemptedTemp).
function Test-DaafRestoreNewTemp {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$Live)
    $listing = Invoke-DaafRestoreDockerSplit -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$Live", '-v', "${Name}:/dest:ro", $BusyboxImage, 'find', '/dest', '-mindepth', '1')
    if ($listing.Exit -ne 0) { return $false }
    if (@($listing.Out | Where-Object { "$_".Trim() -ne '' }).Count -gt 0) { return $false }
    return (Test-DaafRestoreTempIdentity -Name $Name)
}
function Get-DaafRestoreNewTempFailure {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)
    return @("ERROR: Could not confirm that the new temporary Docker volume '$Name' is empty",
        "       and was created by this restore, so it was left as it is (it may belong to",
        "       another restore, for example one still open in another window).",
        "       Close any other restore window, then run this restore again: it will show",
        "       the leftover copy and ask whether to remove it.")
}
$TempCount = $null
$SwapSpaceKnown = $false
# Defined UNCONDITIONALLY before both replay sites (data and Claude temp copies), so a
# strict-mode read can never hit an unset variable. Same program, byte for byte after
# the manifest splice, as the .sh twin's two inlined replays (parity-pinned). Double
# backslashes (\\r, \\357...) so the sh that runs it receives a SINGLE backslash after
# its own unquoted-backslash processing (see shell-scripting gotchas.md, octal printf).
# No `"` anywhere (Windows argv); sh variables are backtick-escaped.
$symlinkReplayScript = "set -ef; IFS=; cr=`$(printf \\r); bom=`$(printf \\357\\273\\277); tab=`$(printf \\t); while IFS=`$tab read -r p t; do p=`${p#`$bom}; t=`${t%`$cr}; [ -z `$p ] && continue; [ -z `$t ] && continue; ln -sf -- `$t /dest/`$p; chown -h 1000:1000 /dest/`$p; done < /dest/$SymlinksManifest; rm -f /dest/$SymlinksManifest"
try {
    do {
        # --- (3) Prepare the temporary copy of the data volume ---
        # `docker create` + `docker cp` into the TEMP volume (one streamed pass instead
        # of a slow per-file bind-mount copy on Docker Desktop); the helper is never
        # started. `docker cp` writes as root (3c repairs ownership) and has no exclude
        # flag (3b strips the Claude subfolder). See the .sh twin for the full notes.
        Write-Host ""
        Write-Host "Preparing a temporary copy of the backup inside Docker..."
        Write-Host "  Your current DAAF data is not touched until you confirm below."
        Write-Host "  This may take a few minutes for large backups."
        Write-Host ""
        # Task #36: the attempt is recorded BEFORE the create (a Ctrl+C there is handled
        # by Resolve-DaafRestoreAttemptedTemp) and closed only AFTER $TempCreated.
        $TempCreateAttempted = $true
        $null = Invoke-DaafRestoreDocker -DockerArgs @('volume', 'create', '--label', "$RestoreLabel=$VolumeName", '--label', "$RestoreRunLabel=$RestoreRunId", $TempVolumeName)
        if ($LASTEXITCODE -ne 0) { $PrepFail = @("ERROR: Could not create a temporary Docker volume ('$TempVolumeName') for the restore."); break }
        # SF2 (review round 2): a refused new temp may be another restore's, so the
        # cleanup is careful (no label reap; only temps still this run's are removed).
        # Task #36: its create attempt is closed first, so the refused volume is never
        # removed as an "attempted" one. (SYNC NOTE: the .sh twin closes it inside
        # _restore_check_new_temp, whose refusal also runs the cleanup and exits.)
        if (-not (Test-DaafRestoreNewTemp -Name $TempVolumeName -Live $VolumeName)) { $TempCreateAttempted = $false; $PrepFail = @(Get-DaafRestoreNewTempFailure -Name $TempVolumeName); $TempCleanupCareful = $true; break }
        $TempCreated = $true
        $TempCreateAttempted = $false
        # stdout ONLY for the CID (the old `(docker create ... 2>&1).Trim()` would have
        # folded a stderr warning line into it). A CID from a create that then failed is
        # reaped by label with the temp volume.
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $cidLines = @(docker create --label "$RestoreLabel=$VolumeName" -v "${TempVolumeName}:/dest" $BusyboxImage 2>$null)
        $createOk = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $savedEAP
        $Cid = ''
        if ($cidLines.Count -gt 0) { $Cid = "$($cidLines[$cidLines.Count - 1])".Trim() }
        if (-not $createOk -or $Cid -eq '') { $PrepFail = @("ERROR: Could not create the helper container for the copy."); break }
        # Only docker cp's text status line reaches stdout (the data goes over the daemon
        # API pipe), so a synchronous inline call is pipeline-safe on PS 5.1. 'Continue'
        # keeps docker cp's error text for the "Docker said:" line: under SilentlyContinue
        # Windows PowerShell 5.1 dropped it (field test 2026-10-05, Run 3c, D2).
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $cpOut = @(docker cp "${SelectedPath}/." "${Cid}:/dest/" 2>&1 | ForEach-Object { "$_" })
        $copyOk = ($LASTEXITCODE -eq 0)
        $null = docker rm -f $Cid 2>&1
        $ErrorActionPreference = $savedEAP
        if (-not $copyOk) {
            $PrepFail = @("ERROR: Copying the backup into Docker failed.")
            $cpSaid = Get-DaafRestoreDockerSaid -Lines $cpOut -PreferCopyCause
            if ($cpSaid -ne '') { $PrepFail += "       Docker said: $cpSaid" }
            break
        }

        # Step 3b: strip the Claude subfolder from the temporary DATA copy.
        $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$VolumeName", '-v', "${TempVolumeName}:/dest", $BusyboxImage, 'rm', '-rf', "/dest/$ClaudeSubDir")
        if ($LASTEXITCODE -ne 0) { $PrepFail = @("ERROR: Failed to remove the $ClaudeSubDir subfolder from the temporary copy."); break }

        # Step 3c: repair ownership (appuser, UID 1000, mirroring daaf-init).
        $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$VolumeName", '-v', "${TempVolumeName}:/dest", $BusyboxImage, 'chown', '-R', '1000:1000', '/dest')
        if ($LASTEXITCODE -ne 0) { $PrepFail = @("ERROR: Failed to set file ownership in the temporary copy."); break }

        # Step 3d: replay executable permissions from the manifest. When it is PRESENT,
        # normalize every regular file to 0644 and re-apply 0755 to exactly the listed
        # paths (undoing the NTFS mode loss); when ABSENT, do NOTHING (a blanket 0644
        # would strip exec from every script). CR and a leading UTF-8 BOM are stripped
        # as parameter-expansion suffix/prefix (busybox sed has no \xNN; never `tr -d`).
        # No `"` in the program (Windows argv); sh variables are backtick-escaped and
        # $PermissionsManifest (a fixed constant) is interpolated by PowerShell. Replay
        # failure stays a latched WARNING (the copy is intact).
        $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$VolumeName", '-v', "${TempVolumeName}:/dest:ro", $BusyboxImage, 'test', '-f', "/dest/$PermissionsManifest")
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Restoring executable permissions from $PermissionsManifest..."
            $replayScript = "set -e; manifest=/dest/$PermissionsManifest; find /dest -type f -exec chmod 644 {} +; cr=`$(printf '\r'); bom=`$(printf '\357\273\277'); while IFS= read -r p; do p=`${p%`$cr}; p=`${p#`$bom}; [ -z `$p ] && continue; [ -e /dest/`$p ] && chmod 755 /dest/`$p; done < `$manifest; rm -f `$manifest"
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $null = docker run --rm --label "$RestoreLabel=$VolumeName" -v "${TempVolumeName}:/dest" $BusyboxImage sh -c $replayScript 2>&1
            $replayOk = ($LASTEXITCODE -eq 0)
            $ErrorActionPreference = $savedEAP
            if (-not $replayOk) {
                Write-Host "WARNING: Could not fully replay executable permissions." -ForegroundColor Yellow
                Write-Host "         Your data was copied intact; only file permissions may be off."
                Write-Host "         If git reports many files as changed by mode only, or a script"
                Write-Host "         will not run, repair with: chmod +x <file> inside the container."
                $HadWarnings = $true
            }
        } else {
            Write-Host "NOTE: No $PermissionsManifest manifest found in this backup (it may predate"
            Write-Host "      permission preservation, or the manifest write may have failed during"
            Write-Host "      backup). File permissions were left as-is -- no normalization was applied."
        }

        # Step 3e: replay symlinks from the manifest (no manifest, no action; failure is
        # a latched WARNING).
        $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$VolumeName", '-v', "${TempVolumeName}:/dest:ro", $BusyboxImage, 'test', '-f', "/dest/$SymlinksManifest")
        $symlinkManifestPresent = ($LASTEXITCODE -eq 0)
        if ($symlinkManifestPresent) {
            Write-Host "Restoring symlinks from $SymlinksManifest..."
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $null = docker run --rm --label "$RestoreLabel=$VolumeName" -v "${TempVolumeName}:/dest" $BusyboxImage sh -c $symlinkReplayScript 2>&1
            $symlinkReplayOk = ($LASTEXITCODE -eq 0)
            $ErrorActionPreference = $savedEAP
            if (-not $symlinkReplayOk) {
                Write-Host "WARNING: Could not fully replay symlinks from the manifest." -ForegroundColor Yellow
                Write-Host "         Your data was copied intact; only symbolic links may be missing."
                Write-Host "         Such links are usually regenerable (e.g. by re-running the step that"
                Write-Host "         created them). Inspect $SymlinksManifest in the backup for the list."
                $HadWarnings = $true
            }
        }

        # Step 3f: check the temporary copy against the backup, with the same count
        # program as the post-restore check (textually identical, parity-pinned). A
        # backup count made inside Docker must match EXACTLY; a count from the
        # PowerShell fallback (Docker could not count the folder; "N+" when it also hit
        # read errors) is a lower bound that must be reached. Unreadable or short: stop
        # before anything is replaced.
        Write-Host "Checking the temporary copy..."
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $TempVerifyOutput = @(docker run --rm --label "$RestoreLabel=$VolumeName" -v "${TempVolumeName}:/dest:ro" $BusyboxImage sh -c 'set -e; : > /tmp/count_err; n=$(find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | wc -l); if test -s /tmp/count_err; then echo RESTORED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err); else echo RESTORED_FILES=$((n)); fi' 2>&1)
        $tempVerifyExit = $LASTEXITCODE
        $ErrorActionPreference = $savedEAP
        $TempCount = Get-DaafCountMarker -Lines $TempVerifyOutput -Name 'RESTORED_FILES'
        if ($tempVerifyExit -ne 0) { $TempCount = $null }
        if ($null -eq $TempCount) {
            $PrepFail = @("ERROR: Could not count the files in the temporary copy (exit $tempVerifyExit), so it", "       cannot be checked against the backup.")
            break
        }
        $tempShort = ($TempCount -eq 0) -or ($TempCount -lt $TotalFiles) -or ((-not $TotalFilesIsLowerBound) -and (-not $TotalFilesFromFallback) -and $TempCount -ne $TotalFiles)
        if ($tempShort) {
            $PrepFail = @("ERROR: The temporary copy holds $TempCount files, but the backup has $TotalFilesLabel,", "       so the copy into Docker is not complete.")
            break
        }
        Write-Host "Verified: $TempCount files in the temporary copy."

        # --- Restore the Claude Code state volume ---
        # Step 3g: prepare its temporary copy (the swap is step 5b below). Any failure
        # here stops the restore before ANY volume is replaced (user decision D2).
        if ($HasClaudeBackup) {
            Write-Host "Preparing the Claude Code state (credentials, session history, plugins)..."
            $claudeFail = @("ERROR: Could not prepare the Claude Code state (login and session history)", "       from this backup: copying it into Docker failed.")
            $ClaudeTempCreateAttempted = $true
            $null = Invoke-DaafRestoreDocker -DockerArgs @('volume', 'create', '--label', "$RestoreLabel=$ClaudeVolumeName", '--label', "$RestoreRunLabel=$RestoreRunId", $ClaudeTempVolumeName)
            if ($LASTEXITCODE -ne 0) {
                $PrepFail = @("ERROR: Could not prepare the Claude Code state (login and session history)", "       from this backup: a temporary Docker volume could not be created.")
                break
            }
            if (-not (Test-DaafRestoreNewTemp -Name $ClaudeTempVolumeName -Live $ClaudeVolumeName)) { $ClaudeTempCreateAttempted = $false; $PrepFail = @(Get-DaafRestoreNewTempFailure -Name $ClaudeTempVolumeName); $TempCleanupCareful = $true; break }
            $ClaudeTempCreated = $true
            $ClaudeTempCreateAttempted = $false
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            $claudeCidLines = @(docker create --label "$RestoreLabel=$ClaudeVolumeName" -v "${ClaudeTempVolumeName}:/dest" $BusyboxImage 2>$null)
            $claudeCreateOk = ($LASTEXITCODE -eq 0)
            $ClaudeCid = ''
            if ($claudeCidLines.Count -gt 0) { $ClaudeCid = "$($claudeCidLines[$claudeCidLines.Count - 1])".Trim() }
            $claudeCpOk = $false
            if ($claudeCreateOk -and $ClaudeCid -ne '') {
                $null = docker cp "${ClaudeBackupPath}/." "${ClaudeCid}:/dest/" 2>&1
                $claudeCpOk = ($LASTEXITCODE -eq 0)
            }
            if (-not [string]::IsNullOrEmpty($ClaudeCid)) { $null = docker rm -f $ClaudeCid 2>&1 }
            $ErrorActionPreference = $savedEAP
            if (-not $claudeCpOk) { $PrepFail = $claudeFail; break }
            $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$ClaudeVolumeName", '-v', "${ClaudeTempVolumeName}:/dest", $BusyboxImage, 'chown', '-R', '1000:1000', '/dest')
            if ($LASTEXITCODE -ne 0) { $PrepFail = $claudeFail; break }
            # The Claude volume's own symlink manifest (at the Claude subfolder root).
            $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$ClaudeVolumeName", '-v', "${ClaudeTempVolumeName}:/dest:ro", $BusyboxImage, 'test', '-f', "/dest/$SymlinksManifest")
            if ($LASTEXITCODE -eq 0) {
                $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
                $null = docker run --rm --label "$RestoreLabel=$ClaudeVolumeName" -v "${ClaudeTempVolumeName}:/dest" $BusyboxImage sh -c $symlinkReplayScript 2>&1
                $claudeReplayOk = ($LASTEXITCODE -eq 0)
                $ErrorActionPreference = $savedEAP
                if (-not $claudeReplayOk) {
                    Write-Host "WARNING: Could not fully replay Claude state symlinks." -ForegroundColor Yellow
                    Write-Host "         Claude state was copied; only symbolic links may be missing."
                    $HadWarnings = $true
                }
            }
            Write-Host "Claude Code state prepared."
        }

        # Re-check the free space with the temporary copy in place: the swap needs
        # F + L >= S + margin. Unmeasurable -> said at the prompt.
        $SpaceOutput = @(Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '-v', "${VolumeName}:/dest:ro", '-v', "${TempVolumeName}:/src:ro", $BusyboxImage, 'sh', '-c', $SpaceProgram))
        $spaceExit = $LASTEXITCODE
        $AvailKB = Get-DaafCountMarker -Lines $SpaceOutput -Name 'AVAIL_KB'
        $LiveKB = Get-DaafCountMarker -Lines $SpaceOutput -Name 'LIVE_KB'
        $SrcKB = Get-DaafCountMarker -Lines $SpaceOutput -Name 'SRC_KB'
        if ($spaceExit -eq 0 -and $null -ne $AvailKB -and $null -ne $LiveKB -and $null -ne $SrcKB) {
            $SwapSpaceKnown = $true
            if (($AvailKB + $LiveKB) -lt ($SrcKB + $SpaceMarginKB)) {
                $PrepFail = @("ERROR: There is not enough free space inside Docker to replace your data with the",
                    "       checked copy: it needs about $(Format-DaafRestoreGB ($SrcKB + $SpaceMarginKB - $LiveKB)) GB free, Docker has $(Format-DaafRestoreGB $AvailKB) GB.",
                    "       Free up space for Docker (for example, delete unused images in Docker Desktop),",
                    "       then run the restore again.")
                break
            }
        }

        # --- (4) Confirmation (after the copy was checked; user decision D1) ---
        Write-Host ""
        Write-Host "==========================================" -ForegroundColor Red
        Write-Host "  *** WARNING: DESTRUCTIVE OPERATION ***" -ForegroundColor Red
        Write-Host "==========================================" -ForegroundColor Red
        Write-Host ""
        Write-Host "The backup was copied into Docker and checked: $TempCount files."
        Write-Host "Typing RESTORE will now COMPLETELY ERASE the current contents of your"
        Write-Host "DAAF Docker volume and replace them with this checked copy."
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
        if (-not $SwapSpaceKnown) {
            Write-Host ""
            Write-Host "Note: The free space inside Docker could not be checked. Replacing your data"
            Write-Host "      needs up to about $(Format-DaafRestoreGB $SpaceNeededKB) GB free. If Docker runs out of space during"
            Write-Host "      this step, your DAAF data may be left incomplete; the checked copy is then"
            Write-Host "      kept so you can run the restore again."
        }
        Write-Host ""
        $Confirm = Read-Host "Type RESTORE to confirm, or anything else to cancel"
        if ($Confirm -ne "RESTORE") { $Cancelled = $true; break }

        # Nothing may use the live volumes while they are replaced. Names come from
        # stdout ONLY (2>$null): with 2>&1 a failing `docker ps` would list its error
        # text as a "container". A FAILED `docker ps` is not "nothing is running": the
        # check could not be made, so refuse (same wording and outcome as the .sh twin).
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $runningNowLines = @(docker ps --filter "volume=$VolumeName" --filter "volume=$ClaudeVolumeName" --format '{{.Names}}' 2>$null)
        $runningNowExit = $LASTEXITCODE
        $ErrorActionPreference = $savedEAP
        if ($runningNowExit -ne 0) {
            $PrepFail = @("ERROR: Could not check whether DAAF is running (docker ps failed, exit $runningNowExit),",
                "       so your data cannot be replaced safely. Make sure Docker Desktop is running,",
                "       then run the restore again.")
            break
        }
        $RunningNow = @($runningNowLines | ForEach-Object { "$_".Trim() } | Where-Object { $_ -ne "" })
        if ($RunningNow.Count -gt 0) {
            $PrepFail = @("ERROR: A container started using your DAAF data while the restore was being",
                "       prepared: $($RunningNow -join ' ')",
                "       Stop it (docker compose down) and run the restore again.")
            break
        }

        # The temp volumes must still be the ones this run created and checked (a restore
        # in another window, or a user, could have removed or replaced one while the
        # prompt waited). Checked BEFORE the marker write, which would make Docker
        # create a new, EMPTY volume under a vanished name. Not ours: refuse and remove
        # NOTHING (the volume under that name may belong to another restore).
        foreach ($tv in @((Get-DaafRestoreKeptTempList) -split ' ' | Where-Object { $_ -ne '' })) {
            if (-not (Test-DaafRestoreTempIdentity -Name $tv)) { $ChangedTemp = $tv; break }
        }
        if ($null -ne $ChangedTemp) { $TempCreated = $false; $ClaudeTempCreated = $false; break }

        # State marker into each temp volume, right before the swaps (see $SwapMarker).
        $markOk = $true
        $MarkersWritten = $true
        foreach ($tv in @((Get-DaafRestoreKeptTempList) -split ' ' | Where-Object { $_ -ne '' })) {
            $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--label', "$RestoreLabel=$VolumeName", '-v', "${tv}:/dest", $BusyboxImage, 'touch', "/dest/$SwapMarker")
            if ($LASTEXITCODE -ne 0) { $markOk = $false }
        }
        if (-not $markOk) { $PrepFail = @("ERROR: Could not prepare the temporary copy for the final step."); break }

        # Right before the data swap (after the marker write): still our volume? S2
        # (review round 2): the refusal removes nothing, but the Claude temp of this run
        # (if still ours) loses its marker, so the next run does not report a swap.
        if (-not (Test-DaafRestoreTempIdentity -Name $TempVolumeName)) {
            $ChangedTemp = $TempVolumeName
            if ($ClaudeTempCreated) { Clear-DaafRestoreOwnMarker -Name $ClaudeTempVolumeName }
            $TempCreated = $false; $ClaudeTempCreated = $false; break
        }

        # --- (5) Replace the live volumes inside Docker ---
        # ONE named, unlabelled container per volume, --sig-proxy=false, so a Ctrl+C is
        # never forwarded into the swap: it ends only the docker client (PowerShell 7
        # source; OBSERVED on Windows PowerShell 5.1.26100 with Docker 29.1.3 in the
        # 2026-10-05 field test, Runs 5a and 7: a console Ctrl+C ended the client, the
        # swap ran to its end, and the finally's text printed in full), and the swap
        # itself runs to the end inside Docker. From here on nothing deletes a temp
        # volume except the final cleanup. A Ctrl+C anywhere inside this try (preparing,
        # at the prompt, or during the swap) prints the right text from the finally
        # below; for its exit code (130 under the Control Panel, 0 when run on its own)
        # see the end of that finally.
        Write-Host ""
        Write-Host "Replacing your DAAF data with the checked copy..."
        Write-Host "  Do not close this window or quit Docker Desktop until this step finishes."
        $SwapStarted = $true
        $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--sig-proxy=false', '--name', $SwapContainerName, '-v', "${TempVolumeName}:/src:ro", '-v', "${VolumeName}:/dest", $BusyboxImage, 'sh', '-c', $SwapProgram)
        $swapExit = $LASTEXITCODE
        # S1 (review round 2): a swap that provably replaced NOTHING -- ONLY exit 3, the
        # program's own refusal before its rm -- is not the after-swap path: careful
        # cleanup (marker first, identity-checked, no reap) and a plain message. Review
        # round 3 (I-1): Docker's 125 is NOT such proof. Docker documents 125 as "the
        # error is with Docker daemon itself" (Running containers guide, "Exit status"),
        # and `docker run` can return 125 after the container started -- e.g. when it
        # loses track of it in a daemon restart mid-swap (moby PR #34999 / #46857),
        # possibly after the rm ran. So 125, whether or not the swap container still
        # exists, takes the after-swap path below (temps and marker kept). The careful
        # flag is set BEFORE the swap-started flag is cleared (S-c): a Ctrl+C between the
        # two then still finds the swap "started" (temps kept), never an ordinary
        # cleanup with a label reap. (The .sh twin's _restore_fail_swap_not_run.)
        if ($swapExit -eq 3) {
            $TempCleanupCareful = $true
            $SwapStarted = $false
            $PrepFail = @("ERROR: The temporary copy of the backup in Docker was gone or could not be used",
                "       (exit $swapExit), so NOTHING was replaced. Run the restore again.")
            break
        }
        if ($swapExit -ne 0) { $SwapFail = @("ERROR: Replacing your DAAF data did not complete (exit $swapExit)."); break }
        $swapCheck = @(Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '-v', "${TempVolumeName}:/src:ro", '-v', "${VolumeName}:/dest:ro", $BusyboxImage, 'sh', '-c', $SwapVerifyProgram))
        if (-not (Test-DaafRestoreSwapChecked -Lines $swapCheck -NonEmpty)) {
            $SwapFail = @("ERROR: After replacing your DAAF data, it could not be confirmed to match the",
                "       checked copy (file names, sizes, permissions and owners).")
            break
        }

        # --- (5b) Replace the Claude Code state volume (same program and check) ---
        if ($HasClaudeBackup) {
            # Field test 2026-10-05, D3: from here an interrupt says the Claude Code state
            # was being replaced (the data volume already is, and was checked).
            $ClaudeSwapPhase = $true
            Write-Host ""
            Write-Host "Replacing the Claude Code state..."
            # Right before the Claude swap: still our volume? The data volume is already
            # replaced and checked, so every Claude failure below is an after-swap failure
            # that says so plainly ($SwapFailClaudeOnly, S5); the changed volume is not
            # ours, so it is not listed as the kept copy.
            $SwapFailClaudeOnly = $true
            if (-not (Test-DaafRestoreTempIdentity -Name $ClaudeTempVolumeName)) {
                $ClaudeTempCreated = $false
                $SwapFail = @("ERROR: The temporary copy of the Claude Code state (volume '$ClaudeTempVolumeName')",
                    "       was changed by something else -- for example, a restore started in another",
                    "       window -- so it was not used.")
                break
            }
            $null = Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '--sig-proxy=false', '--name', $ClaudeSwapContainerName, '-v', "${ClaudeTempVolumeName}:/src:ro", '-v', "${ClaudeVolumeName}:/dest", $BusyboxImage, 'sh', '-c', $SwapProgram)
            $swapExit = $LASTEXITCODE
            # Exit 3 is the program's own refusal before its rm (the live Claude state is
            # untouched); any other outcome means the swap ran and may have erased it (S-a).
            if ($swapExit -ne 3) { $ClaudeSwapRan = $true }
            if ($swapExit -ne 0) {
                $SwapFail = @("ERROR: Replacing the Claude Code state (login and session history) did not",
                    "       complete (exit $swapExit).")
                break
            }
            $swapCheck = @(Invoke-DaafRestoreDocker -DockerArgs @('run', '--rm', '-v', "${ClaudeTempVolumeName}:/src:ro", '-v', "${ClaudeVolumeName}:/dest:ro", $BusyboxImage, 'sh', '-c', $SwapVerifyProgram))
            if (-not (Test-DaafRestoreSwapChecked -Lines $swapCheck)) {
                $SwapFail = @("ERROR: After replacing the Claude Code state, it could not be confirmed to match",
                    "       the checked copy.")
                break
            }
            Write-Host "Claude Code state restored."
        }
    } while ($false)
    $ReachedEnd = $true
} catch {
    # An unexpected error (a bug, not an outcome: every outcome above is a flag plus
    # `break`). Recorded so the interrupt exit code at the end of the finally is never
    # given to it, then rethrown unchanged: after the finally it still ends the script
    # with PowerShell's own error text and exit code (1). A Ctrl+C never runs a catch
    # (a stopped pipeline runs only the finally; observed on pwsh 7.6, see below).
    $Faulted = $true
    throw
} finally {
    # Ctrl+C, a failure or a cancel BEFORE any swap: remove what this run created.
    # After a swap started: never (the temp copy may be the only complete one). Nor
    # when a temp volume is no longer this run's ($ChangedTemp): that refusal removes
    # NOTHING -- not even the label reap of prepare helpers, which could belong to the
    # other restore that changed it (the .sh twin's _restore_refuse_changed_temp).
    if (-not $SwapStarted -and $null -eq $ChangedTemp) { Invoke-DaafRestoreTempCleanup }
    if (-not $ReachedEnd) {
        Write-Host ""
        if ($SwapStarted) {
            if ($ClaudeSwapPhase) {
                Write-Host "Restore interrupted while the Claude Code state (login and session history) was being replaced." -ForegroundColor Red
                Write-Host "Your project files (DAAF data) were already replaced and checked."
            } else {
                Write-Host "Restore interrupted while your DAAF data was being replaced." -ForegroundColor Red
            }
            Write-Host "The replacement keeps running inside Docker until it finishes. Your backup"
            Write-Host "folder $SelectedName\ is unchanged. Wait a few minutes, then run this restore"
            Write-Host "again and choose the same backup:"
            Write-Host "  $RerunCommand"
        } else {
            Write-DaafRestoreUnchanged -First 'Restore interrupted. '
            if ($TempRemoveFailed) { Write-DaafRestoreKeptTempHint -Lead '' }
        }
    }
    # Interrupt exit code. A Ctrl+C stops the script right after this finally: nothing
    # below it runs, so without this line the process exits 0 (observed under pwsh 7.6
    # on Linux) and a caller that reads only the exit code -- the Control Panel,
    # daaf.ps1's Invoke-DaafDelegate, which starts this script as a child process with
    # DAAF_NESTED=1 -- would report an interrupted restore as a clean return. So, ONLY
    # when DAAF_NESTED is set, an interrupt ends the process with 130 (the .sh twin's
    # code), as the LAST statement of the finally, after every message above. A run
    # started on its own in the user's PowerShell window is NOT ended this way:
    # [Environment]::Exit would end that whole PowerShell session, closing the window
    # the recovery text was just printed in, so it keeps exit 0 (documented known limit).
    # "Interrupted" = the try did not reach its end, the catch did not record an error,
    # and no outcome flag explains it (each is set before a `break` that reaches
    # $ReachedEnd; an interrupt between a flag and its `break` errs toward exit 0, never
    # toward a false 130). Only this try is covered: a Ctrl+C at an earlier prompt or in
    # the post-swap count/cleanup below still exits 0 (pwsh -File exits 0 on SIGINT). [Environment]::Exit, not `exit`, because no `exit` statement runs
    # inside this try/finally (see the section comment above). Verified under pwsh 7.6 on
    # Linux (a SIGINT during a native command or a cmdlet: 10 of 10 runs exited 130 with
    # the finally's text printed in full; `exit 130` behaved the same there). Windows
    # PowerShell 5.1.26100 with Docker 29.1.3 (field test 2026-10-05, Runs 5a and 7,
    # OBSERVED): a real console Ctrl+C during a swap ended only the docker client; the
    # swap ran to its end and this finally's text printed in full. The exit code was not
    # captured there (130 on 5.1 is inference), and from the Control Panel the panel
    # itself ended too.
    $Interrupted = (-not $ReachedEnd) -and (-not $Faulted) -and ($null -eq $PrepFail) -and ($null -eq $SwapFail) -and (-not $Cancelled) -and ($null -eq $ChangedTemp)
    if ($Interrupted -and $env:DAAF_NESTED) { [Environment]::Exit(130) }
}

if ($null -ne $ChangedTemp) {
    Write-Host ""
    Write-Host "ERROR: The temporary copy of the backup in Docker (volume '$ChangedTemp') was changed by" -ForegroundColor Red
    Write-Host "       something else while this restore was running -- for example, a restore"
    Write-Host "       started in another window. It was not used, and nothing was removed."
    Write-DaafRestoreUnchanged -First '       ' -Indent '       '
    Write-Host "       Close any other restore window, then run this restore again."
    Wait-AndExit 1
}
if ($null -ne $PrepFail) {
    Write-Host ""
    foreach ($line in $PrepFail) { Write-Host $line -ForegroundColor Red }
    Write-DaafRestoreUnchanged -First '       ' -Indent '       '
    if ($TempRemoveFailed) { Write-DaafRestoreKeptTempHint -Lead '       ' }
    Wait-AndExit 1
}
if ($Cancelled) {
    Write-Host ""
    Write-DaafRestoreUnchanged -First 'Restore cancelled. '
    if ($TempRemoveFailed) { Write-DaafRestoreKeptTempHint -Lead '' }
    Wait-AndExit 0
}
if ($null -ne $SwapFail) {
    Write-DaafRestoreSwapFailure -Lines $SwapFail -ClaudeOnly:$SwapFailClaudeOnly -ClaudeSwapRan:$ClaudeSwapRan
    Wait-AndExit 1
}

# --- Verify ---
# Count the restored volume like with like: the same root exclusions as the backup
# count above (a root ".daaf-symlinks"/".daaf-permissions" left behind when a manifest
# replay failed, and the ".daaf-claude-config" subtree), and one `stat` line per file
# so a name holding a newline counts once. Quote-free (Windows argv), and textually
# identical to restore_from_backup.sh's program (tests/bash/backup_twin_parity.bats).
Write-Host "Verifying restore..."
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$VerifyOutput = @(docker run --rm -v "${VolumeName}:/dest:ro" $BusyboxImage sh -c 'set -e; : > /tmp/count_err; n=$(find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | wc -l); if test -s /tmp/count_err; then echo RESTORED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err); else echo RESTORED_FILES=$((n)); fi' 2>&1)
$verifyExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
# Markers, not a bare number: the old `2>&1` + TryParse of the whole output turned any
# stderr line into a failed parse, i.e. a false "0 files found" ERROR. The program
# prints RESTORED_FILES only when its count's stderr was empty (the same F1 pattern as
# $BackupCountProgram), else RESTORED_COUNT_ERRORS. Unavailable ($null) is its own
# outcome: a WARNING with exit 0, because the copy, ownership repair and replays all
# succeeded and only this check could not run (exit 1 would tell a caller the restore
# failed with the data in place). A count that WAS read must EQUAL the temp copy's
# count from step 3f (the same program; the swap copied that copy): any difference --
# including 0 -- goes through the after-swap failure path (temp copy kept, exit 1).
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
} elseif ($RestoredCount -ne $TempCount) {
    Write-DaafRestoreSwapFailure -Lines @("ERROR: After replacing your DAAF data, it holds $RestoredCount files, but the checked",
        "       copy held $TempCount.")
    Wait-AndExit 1
} else {
    Write-Host "Verified: $RestoredCount files in restored volume."
    # A LOWER-BOUND backup count ("N+", the PowerShell fallback could not read some
    # folders): the temp copy reached it in step 3f, so this restored count -- equal to
    # the temp copy's -- is consistent with it. Informational; the scan already latched
    # WITH WARNINGS, because a lower bound cannot prove the restore complete.
    if ($TotalFilesIsLowerBound) {
        Write-Host "Note: The backup count ($TotalFilesLabel files) was a lower bound; the restored volume holds"
        Write-Host "      $RestoredCount files, which is consistent with it."
    }
}

if (-not $HasClaudeBackup) {
    Write-Host ""
    Write-Host "NOTE: This backup does not contain Claude Code state (it predates the"
    Write-Host "      dedicated Claude volume). Your data was restored, but Claude Code"
    Write-Host "      login and session history were NOT part of this backup -- you may"
    Write-Host "      need to run /login again after starting DAAF."
}

# --- (6) Remove the temporary copies ---
# Every check passed. A removal failure does not undo the restore: a latched WARNING
# with the exact command, exit 0.
Invoke-DaafRestoreTempCleanup -Final
if ($TempRemoveFailed) {
    $KeptTemps = Get-DaafRestoreKeptTempList
    Write-Host ""
    Write-Host "WARNING: Could not remove the temporary copy of your data (Docker volume(s): $KeptTemps)." -ForegroundColor Yellow
    foreach ($noteLine in $TempRemoveNote) { Write-Host "         $noteLine" }
    Write-Host "         Your DAAF data was restored. To free the space it uses, run:"
    Write-DaafRestoreRemoveHint -Lead '         ' -Volumes $KeptTemps
    $HadWarnings = $true
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
