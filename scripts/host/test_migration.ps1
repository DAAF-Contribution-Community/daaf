# ============================================================================
# DAAF Migration End-to-End Test (Windows PowerShell)
# ============================================================================
# Automated harness that walks the ACTUAL end-user install pathway for a chosen
# historical DAAF version, plants user work, runs the migration script from the
# local repo, and verifies the end state:
#   1. Nukes any existing DAAF Docker resources (clean slate)
#   2. Installs the old version THE WAY USERS ACTUALLY DID at that version:
#        Era 1 (v1.0.0)         git clone + busybox copy + docker compose up
#                               (/daaf gets a full .git: origin remote, main)
#        Era 2 (v2.0.0/v2.0.1)  ZIP download + busybox copy + docker compose up
#                               (no .git in a ZIP; that era's container
#                               entrypoint git-inits a LOCAL-ONLY repo with a
#                               synthetic root commit and NO remote -- the
#                               state migrate_daaf's graft machinery exists for)
#        Era 3 (v2.1.0+/branch) the version's own scripts\host\install.ps1
#   3. Verifies the install produced the era's expected git state (the harness
#      never fakes era state by mutating the repo -- the pathway must produce it)
#   4. Creates committed framework changes + research files
#   5. Creates uncommitted user work (untracked files + a dirty tracked file,
#      which exercises the updater's stash/pop path)
#   6. Runs the migration script (from the local repo, not GitHub)
#   7. Runs era-conditional verification checks
#   8. (Optional) Exercises DAAF_PROJECT_NAME multi-instance support end-to-end
#      by standing up a SECOND coexisting instance and tearing it down again
#
# FIDELITY PRINCIPLE: Phases 2-3 replay the documented install commands from
# user_reference/01_installation_and_quickstart.md AT THE CHOSEN TAG as closely
# as possible. The point is to mirror what a real user's machine actually ran,
# so migration bugs surface authentically. Deliberate, documented deviations --
# each exists only to pin a moving target to a reproducible historical state:
#   - Era 1: users cloned when main WAS v1.0.0; a clone today lands on current
#     main. After the documented clone, the harness runs
#     `git checkout -B main v1.0.0` to rewind main to the tag. (The object
#     store still contains newer history than a 2026-era user had; migration
#     only fetches and sets upstream, so this is inert.)
#   - Era 2: users downloaded main.zip; the harness downloads the TAG's ZIP
#     (archive/refs/tags/<tag>.zip) for the same reason. Same busybox copy,
#     same compose build, same entrypoint git-init as the era produced.
#   - Era 3 with a vX.Y.Z tag: install.ps1 clones `--depth 1 -b <tag>`, which
#     leaves a detached HEAD that no real user had (users installed from
#     branch main). The harness normalizes with `git checkout -B main` at that
#     commit so the git state matches a real install of that vintage. Branch
#     values (e.g. daaf_dev) need no normalization and get none.
#
# EXPECT INTERACTIVE PROMPTS: migrate/update ask about running the update,
# backup, and rebuild -- you drive those choices, exactly as an end user would,
# and the Phase 7 checks are designed to pass whichever way you answer.
# KNOWN WART: you will also see up to 2-3 stray "Press Enter to continue/close"
# pauses from the child scripts. migrate_daaf.ps1/update_daaf.ps1 clobber the
# harness's DAAF_NESTED suppression (they set-then-Remove-Item instead of
# save/restore -- documented production finding, deliberately NOT patched from
# this dev harness; see research/2026-07-06_FrameworkDev_MigrationTestHarness/
# SESSION_NOTES.md). Just press Enter when they appear.
#
# BUILD COST: Era 1/2 runs build the OLD Dockerfiles -- authentic and slow
# (10+ min cold). v1.0.0 pins no base-image digest (floating tag) and does not
# pin Claude Code, so that build may drift or break as upstreams move; the
# harness fails loudly if so rather than papering over it. Era 1 may also
# surface authentic-era permission pain (v2.0.1 added a chown repair command
# precisely because real users hit it) -- such failures are findings, not
# harness bugs.
#
# Usage:
#   .\test_migration.ps1                                       # v2.0.1, Era 2
#   $env:DAAF_TEST_VERSION = "v1.0.0"; .\test_migration.ps1    # Era 1
#   $env:DAAF_TEST_VERSION = "v2.1.0"; .\test_migration.ps1    # Era 3 (tag)
#   $env:DAAF_TEST_VERSION = "daaf_dev"; .\test_migration.ps1  # Era 3 (branch)
#   .\test_migration.ps1 -SkipMultiInstance                    # skip phase 8
#
# Environment variables:
#   DAAF_TEST_VERSION      Tag/branch to install (default: v2.0.1 -- the
#                          richest migration path: ZIP era, graft required)
#   DAAF_TEST_ERA          Override era pathway: "1", "2", or "3" (default:
#                          auto -- v1.0.0=1, v2.0.0/v2.0.1=2, everything
#                          else=3). Tags below v2.1.0 cannot run era 3: no
#                          scripts\host\install.ps1 exists at those tags.
#   DAAF_MIGRATION_BRANCH  Branch for migration script downloads
#                          (default: daaf_dev -- keep this tracking the branch
#                           currently under update-testing)
#
# Parameters:
#   -SkipMultiInstance     Skip the multi-instance phase (8), which lengthens
#                          the run (fresh build + teardown). Equivalent env
#                          toggle: $env:SKIP_MULTI_INSTANCE = "1"
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - git on the host PATH (Era 1 replays the documented git clone)
#   - Internet connection (to pull old versions from GitHub)
#   - This script must be run from a local clone of the DAAF repo
#     (it copies migrate_daaf.ps1 from the local repo)
#
# Which versions of the local scripts?
#   - migrate_daaf.ps1 and install.ps1 are taken from the LOCAL repo this
#     harness runs from (scripts\host\ two levels up). They must be checked
#     out to the branch under test -- typically the same branch as
#     DAAF_MIGRATION_BRANCH (default: daaf_dev). The harness tests THAT
#     checkout's migration/install logic.
#   - The OLD version being migrated FROM is controlled by DAAF_TEST_VERSION
#     and is fetched from GitHub at that tag (clone, ZIP, or install.ps1
#     download depending on era), independent of the local repo.
#
# ============================================================================

[CmdletBinding()]
param(
    [switch]$SkipMultiInstance
)

#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

# Ensure TLS 1.2 for GitHub downloads (required on PowerShell 5.1)
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

# --- Configuration ---
# Default install-from version: v2.0.1 -- the richest migration path (ZIP era:
# no remote, synthetic root commit, graft + permission-fix machinery all get
# exercised). Override with DAAF_TEST_VERSION for the other pathways.
$TestVersion = if ($env:DAAF_TEST_VERSION) { $env:DAAF_TEST_VERSION } else { "v2.0.1" }
# Default migration branch: the branch whose migrate_daaf.ps1 + host scripts are
# under test. Keep this pointing at the CURRENT update-testing branch (today:
# daaf_dev). Overridable per-run via DAAF_MIGRATION_BRANCH without editing here.
$MigrationBranch = if ($env:DAAF_MIGRATION_BRANCH) { $env:DAAF_MIGRATION_BRANCH } else { "daaf_dev" }
$Repo = "DAAF-Contribution-Community/daaf"

# The -SkipMultiInstance switch OR the SKIP_MULTI_INSTANCE=1 env toggle skips
# phase 8. Fold the env toggle into the switch so downstream logic checks one flag.
if ($env:SKIP_MULTI_INSTANCE -eq "1") { $SkipMultiInstance = $true }

# --- Era detection ---
# Era 1 = v1.0.0            clone-based: full .git, origin remote, branch main
# Era 2 = v2.0.0 / v2.0.1   ZIP-based: entrypoint git-inits a local-only repo
#                           (synthetic root commit, no remote)
# Era 3 = v2.1.0+ / branch  modern install.ps1 pathway (shipped at the ref)
# DAAF_TEST_ERA overrides the pathway (e.g. to run a branch through the ZIP
# flow); the auto-detect maps each version to the pathway its real users had.
if ($env:DAAF_TEST_ERA) {
    $TestEra = $env:DAAF_TEST_ERA
} elseif ($TestVersion -eq "v1.0.0") {
    $TestEra = "1"
} elseif ($TestVersion -in @("v2.0.0", "v2.0.1")) {
    $TestEra = "2"
} else {
    $TestEra = "3"
}

if ($TestEra -notin @("1", "2", "3")) {
    Write-Error "DAAF_TEST_ERA '$TestEra' is invalid. Use 1 (clone), 2 (ZIP), or 3 (install.ps1)."
    exit 1
}

# --- Era/version compatibility guard ---
# Era 3 downloads scripts\host\install.ps1 from the chosen ref; tags below
# v2.1.0 predate that layout entirely (the host helper set landed at v2.1.0,
# commit a399639), so the download 404s. Fail fast with a clear message.
# Only vX.Y.Z tags are checked -- branch names always carry the current layout.
# Comparison parses numeric components ([version]) because a lexical compare is
# wrong ("v2.10.0" sorts before "v2.2.0" lexically).
if ($TestEra -eq "3" -and $TestVersion -match '^v(\d+)\.(\d+)\.(\d+)$') {
    $requested = [version]::new([int]$Matches[1], [int]$Matches[2], [int]$Matches[3])
    if ($requested -lt [version]::new(2, 1, 0)) {
        Write-Error ("Era 3 requires v2.1.0 or newer ($TestVersion ships no scripts\host\install.ps1). " +
            "Remove DAAF_TEST_ERA and let auto-detection replay the authentic pathway for $TestVersion.")
        exit 1
    }
}

# --- Docker identifier derivation (default "daaf" instance) ---
# All identifiers are derived from DAAF_PROJECT_NAME rather than hardcoded, so a
# non-default install is testable and so this mirrors how nuke_daaf.ps1 /
# backup_daaf.ps1 derive their names. Docker joins the compose project name to the
# service with a DASH (containers/image) and to declared volumes with an
# UNDERSCORE (verified against docker-compose.yml). Default project name "daaf"
# reproduces the original hardcoded values byte-for-byte.
$ProjectName = if ($env:DAAF_PROJECT_NAME) { $env:DAAF_PROJECT_NAME } else { "daaf" }
$VolumeName = "${ProjectName}_daaf-data"
$ClaudeVolumeName = "${ProjectName}_daaf-claude-config"
$ContainerMain = "${ProjectName}-daaf-docker-1"
$ContainerInit = "${ProjectName}-daaf-init-1"
$ImageName = "${ProjectName}-daaf-docker"

# --- Second-instance identifiers (Phase 8 multi-instance pass) ---
# A distinct project name proves DAAF_PROJECT_NAME actually reprojects every
# Docker object. Same derivation rules as above.
$SecondProjectName = "daaftest2"
$SecondVolumeName = "${SecondProjectName}_daaf-data"
$SecondClaudeVolumeName = "${SecondProjectName}_daaf-claude-config"
$SecondContainerMain = "${SecondProjectName}-daaf-docker-1"
$SecondContainerInit = "${SecondProjectName}-daaf-init-1"
$SecondImageName = "${SecondProjectName}-daaf-docker"
# Distinct host ports so the second instance does not collide with the first on
# the same host. Container ports stay fixed (2718/2719/2720); only the published
# host port varies. These key names match environment_settings_example.txt and
# the compose interpolation (DAAF_PORT_MARIMO / _LOGVIEWER / _VSCODE).
$SecondPortMarimo = "12718"
$SecondPortLogviewer = "12719"
$SecondPortVscode = "12720"

# --- Era 1/2 project-name guard ---
# The historical pathways predate DAAF_PROJECT_NAME entirely: v1.0.0's compose
# file has no `name:` key (project name = directory name, which the documented
# flow fixes as "daaf"), and v2.0.x hardcodes `name: daaf`. A non-default
# project name is only meaningful for Era 3.
if ($TestEra -ne "3" -and $ProjectName -ne "daaf") {
    Write-Error ("Era $TestEra replays a pathway that predates DAAF_PROJECT_NAME; " +
        "only the default 'daaf' project is supported (got: '$ProjectName').")
    exit 1
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
# install.ps1 is reused for the second instance in phase 8 (see there for why).
$LocalInstallPath = Join-Path $LocalRepoRoot "scripts\host\install.ps1"

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

# Invoke a HARNESS-OWNED .ps1 as a hardened child process and return its exit
# code. Two defenses against the field failure where a script copied from a
# Downloads-path repo (carrying NTFS Mark-of-the-Web) is refused by RemoteSigned
# with "...is not digitally signed. You cannot run this script on the current
# system":
#   1. Unblock-File on the TARGET. The caller MUST pass a harness-written copy
#      (never a path inside the user's repo) so we only ever strip MOTW from
#      files the harness itself produced -- never from the user's originals.
#   2. Spawn a child powershell.exe with -ExecutionPolicy Bypass -File, instead
#      of in-process dot/`&`-invocation, so the child's policy is Bypass
#      regardless of the machine's RemoteSigned setting. This mirrors the
#      canonical child-launch idiom in daaf.ps1 (Invoke-DaafDelegate: resolve
#      the running host exe, Start-Process -NoNewWindow -PassThru, WaitForExit,
#      read $proc.ExitCode) -- with -NoNewWindow the child inherits THIS
#      process's console AND its environment block, so any $env:DAAF_* vars the
#      caller set before calling are visible to the child (the Phase 6 / Phase 8
#      env mutations keep working unchanged).
# Windows PowerShell 5.1 is the host; resolve the running host exe rather than
# hardcoding "powershell.exe" so a pwsh-driven run stays consistent.
function Invoke-HardenedScript {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Path,
        [string[]]$ScriptArgs = @()
    )
    # Strip MOTW from the harness-owned copy so RemoteSigned cannot refuse it.
    # Best-effort: a file with no Zone.Identifier stream is a no-op, and a rare
    # provider error must not abort the run (Bypass below is the real guarantee).
    try { Unblock-File -LiteralPath $Path -ErrorAction Stop } catch { Write-Verbose "Unblock-File no-op: $_" }

    $hostExe = (Get-Process -Id $PID).Path
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Path)
    foreach ($a in $ScriptArgs) {
        if ($a -match '\s') { $argList += ('"' + ($a -replace '"', '\"') + '"') }
        else { $argList += $a }
    }
    $proc = Start-Process -FilePath $hostExe -ArgumentList $argList -NoNewWindow -PassThru
    # PS 5.1 gotcha: touch $proc.Handle BEFORE waiting. Start-Process -PassThru
    # returns a Process object that has not opened a handle; without one, the
    # .NET runtime cannot retrieve the exit code and $proc.ExitCode is $null
    # after WaitForExit(). That $null was the field failure "exited with code ."
    # -- a SUCCESSFUL child scored as failed because $null -ne 0 is $true.
    $null = $proc.Handle
    $proc.WaitForExit()
    if ($null -eq $proc.ExitCode) {
        # Should be unreachable with the handle cached; if it ever happens,
        # fail loudly and truthfully rather than $null-comparing quietly.
        Write-Host "WARNING: Child exit code unavailable for '$Path' - treating as failure." -ForegroundColor Yellow
        return 1
    }
    return $proc.ExitCode
}

# Write file content into the container via STDIN. This exists because of a
# PS 5.1 field failure: passing `bash -c '... "quoted" ...'` through docker.exe
# mangles embedded double quotes (pre-7.3 native argument passing does not
# escape them), silently re-tokenizing the payload -- the old fixture writes
# printed "Test"/"Work" and created NOTHING. Rules that keep container commands
# safe on PS 5.1:
#   1. Multi-line / quote-bearing file content goes through this function
#      (content rides stdin, immune to argv quoting; CRLF is stripped).
#   2. Any direct docker-exec argv (Invoke-ContainerExec/-Git) must contain NO
#      embedded double-quote characters. Spaces are fine; quotes are not.
function Write-ContainerFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Content
    )
    # The bash -c payload deliberately contains no double quotes (rule 2).
    $cmd = 'tr -d ''\r'' > ' + $Path
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $Content | docker exec -i $script:ContainerName bash -c $cmd
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Container helper functions.
# SIMPLE functions using $args -- deliberately NOT [CmdletBinding()] +
# ValueFromRemainingArguments. An advanced function gains PowerShell's common
# parameters, and lone flags prefix-bind onto them: `-p` uniquely prefixes
# -PipelineVariable and CONSUMES THE NEXT ARGUMENT as its value. Field failure
# 2026-07-06: `Invoke-ContainerExec mkdir -p d1 d2 d3` reached docker as
# `mkdir d2 d3` (no -p, d1 eaten), failed silently under 2>$null, and every
# fixture write under those dirs then died on a bash redirect error. The same
# binding would eat the SHA in `cat-file -p <sha>`. This mirrors the
# documented idiom in migrate_daaf.ps1's own container helpers.
function Invoke-ContainerExec {
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker exec $script:ContainerName @args 2>$null
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

function Invoke-ContainerGit {
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $result = docker exec $script:ContainerName git -C /daaf @args 2>$null | Out-String
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Test whether a Docker volume exists (returns $true/$false; no exception noise)
function Test-DockerVolume {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $null = docker volume inspect $Name 2>&1
    $exists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $savedEAP
    return $exists
}

# Test whether a Docker container exists (any state; returns $true/$false)
function Test-DockerContainer {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $null = docker inspect $Name 2>&1
    $exists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $savedEAP
    return $exists
}

$EraLabel = switch ($TestEra) {
    "1" { "clone-based" }
    "2" { "ZIP-based" }
    default { "modern install.ps1" }
}
$MultiLabel = if ($SkipMultiInstance) { "skipped (-SkipMultiInstance)" } else { "enabled (phase 8)" }

Write-Host ""
Write-Host "==========================================" -ForegroundColor White
Write-Host "  DAAF Migration Test" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor White
Write-Host ""
Write-Host "  Version:   $TestVersion"
Write-Host "  Era:       $TestEra ($EraLabel)"
Write-Host "  Migration: from local repo (branch: $MigrationBranch)"
Write-Host "  Work dir:  $TestDir"
Write-Host "  Multi:     $MultiLabel"
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

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
# Default instance
docker rm -f $ContainerMain 2>&1 | Out-Null
docker rm -f $ContainerInit 2>&1 | Out-Null
docker volume rm $VolumeName 2>&1 | Out-Null
# Remove the Claude Code state volume too. A prior run (or a migrated install)
# creates this once the current compose file is in play; leaving it behind would
# leak Claude auth/session state across test runs. Absence is tolerated.
docker volume rm $ClaudeVolumeName 2>&1 | Out-Null
docker rmi $ImageName 2>&1 | Out-Null
# Clean up any leftovers from a previous, possibly aborted, multi-instance pass
# (phase 8) so its state cannot poison this run's coexistence checks.
docker rm -f $SecondContainerMain 2>&1 | Out-Null
docker rm -f $SecondContainerInit 2>&1 | Out-Null
docker volume rm $SecondVolumeName 2>&1 | Out-Null
docker volume rm $SecondClaudeVolumeName 2>&1 | Out-Null
docker rmi $SecondImageName 2>&1 | Out-Null
$ErrorActionPreference = $savedEAP

Write-Host "SUCCESS: Clean slate achieved." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 2: Install Old Version (era-authentic pathway)
# =====================================================================
Write-Host "[2/7] Install $TestVersion (Era $TestEra pathway: $EraLabel)" -ForegroundColor White
Write-Host ""

Set-Location $TestDir

# $script:HostDir is where migrate_daaf.ps1 will be run from in Phase 6 -- for
# each era this is the directory a real user would have run it from (the one
# holding docker-compose.yml).
$script:HostDir = ""
# Era 2 only: the synthetic root commit's SHA, captured in Phase 3 before
# migration can graft it (initialized here so StrictMode never reads an
# undefined variable on other eras).
$script:Era2RootSha = ""

if ($TestEra -eq "1") {
    # ----- Era 1: the documented v1.0.0 pathway -----
    # Verbatim flow from v1.0.0 user_reference/01_installation_and_quickstart.md:
    #   git clone https://github.com/DAAF-Contribution-Community/daaf.git
    #   cd daaf
    #   docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox cp -a /source/. /dest/
    #   docker compose up -d --build
    # (v1.0.0's busybox copy has NO sh -c wrapper -- that arrived in v2.0.0.)
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Error "git not found on the host PATH - Era 1 replays the documented git clone."
        exit 1
    }

    Write-Host "INFO: Cloning DAAF repo (documented v1.0.0 flow)..." -ForegroundColor Cyan
    $CloneDir = Join-Path $TestDir "daaf"
    git clone "https://github.com/$Repo.git" $CloneDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git clone failed - cannot replay the Era 1 install."
        exit 1
    }

    # Time-machine deviation (see header): rewind main to the tag, because a
    # 2026-era user's clone HAD main at v1.0.0. checkout -B moves the branch
    # pointer and working tree while keeping origin + tracking config intact.
    git -C $CloneDir checkout -B main $TestVersion
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git checkout -B main $TestVersion failed - cannot pin the Era 1 tree."
        exit 1
    }

    Set-Location $CloneDir
    Write-Host "INFO: Copying the clone into the Docker volume (documented busybox step)..." -ForegroundColor Cyan
    docker run --rm -v "${PWD}:/source:ro" -v "${VolumeName}:/dest" busybox cp -a /source/. /dest/
    if ($LASTEXITCODE -ne 0) {
        Write-Error "busybox copy into volume $VolumeName failed."
        exit 1
    }

    # v1.0.0's compose file has no `name:` key, so the compose project name
    # comes from THIS directory's name ("daaf") -- reproducing the era's
    # container/volume names (daaf-daaf-docker-1 / daaf_daaf-data).
    Write-Host "INFO: Building and starting the v1.0.0 container (docker compose up -d --build)..." -ForegroundColor Cyan
    Write-Host "INFO: This builds the OLD Dockerfile - authentic and slow on a cold cache..." -ForegroundColor Cyan
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker compose up failed for the v1.0.0 build. If the base image or Claude installer has drifted upstream, that is a real finding about resurrecting this era - see the header BUILD COST note."
        exit 1
    }
    $script:HostDir = $CloneDir

} elseif ($TestEra -eq "2") {
    # ----- Era 2: the documented v2.0.x ZIP pathway -----
    # Verbatim flow from v2.0.x user_reference/01_installation_and_quickstart.md
    # (Windows variant):
    #   Invoke-WebRequest -Uri ".../archive/refs/heads/main.zip" -OutFile daaf.zip
    #   Expand-Archive -Path daaf.zip -DestinationPath .
    #   cd daaf-main
    #   docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox sh -c 'cp -a /source/. /dest/'
    #   docker compose up -d --build
    # Time-machine deviation (see header): the TAG's ZIP stands in for that
    # era's main.zip. No .git comes out of a ZIP; the era's container
    # entrypoint git-inits /daaf on first start (verified verbatim at both
    # tags: git init, branch -m main, add -A, commit "Initial commit: DAAF
    # framework", NO remote) -- Phase 3 waits for and verifies that.
    Write-Host "INFO: Downloading release ZIP (documented v2.0.x flow, pinned to the tag)..." -ForegroundColor Cyan
    $ZipPath = Join-Path $TestDir "daaf.zip"
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/tags/$TestVersion.zip" -OutFile $ZipPath

    Expand-Archive -Path $ZipPath -DestinationPath $TestDir -Force
    # GitHub names the ZIP's root folder <repo>-<ref> (with a version-like
    # tag's leading "v" stripped) -- detect it instead of hardcoding.
    $ExtractDir = Get-ChildItem -Path $TestDir -Directory -Filter 'daaf-*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $ExtractDir) {
        Write-Error "Could not find the extracted daaf-* folder under $TestDir."
        exit 1
    }

    Set-Location $ExtractDir.FullName
    Write-Host "INFO: Copying the extracted tree into the Docker volume (documented busybox step)..." -ForegroundColor Cyan
    docker run --rm -v "${PWD}:/source:ro" -v "${VolumeName}:/dest" busybox sh -c 'cp -a /source/. /dest/'
    if ($LASTEXITCODE -ne 0) {
        Write-Error "busybox copy into volume $VolumeName failed."
        exit 1
    }

    # v2.0.x compose hardcodes `name: daaf`, so project naming is stable
    # regardless of this directory's name (daaf-2.0.1 etc.).
    Write-Host "INFO: Building and starting the $TestVersion container (docker compose up -d --build)..." -ForegroundColor Cyan
    Write-Host "INFO: This builds the OLD Dockerfile - authentic and slow on a cold cache..." -ForegroundColor Cyan
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker compose up failed for the $TestVersion build - see the header BUILD COST note."
        exit 1
    }
    $script:HostDir = $ExtractDir.FullName

} else {
    # ----- Era 3: the version's own install script (v2.1.0+ / branches) -----
    Write-Host "INFO: Installing DAAF via the ref's own install.ps1 from branch/tag: $TestVersion" -ForegroundColor Cyan
    Write-Host "INFO: This will build the Docker image and clone the repo - may take several minutes..." -ForegroundColor Cyan
    Write-Host ""

    # Download and run the install script from the target version
    $InstallUrl = "https://raw.githubusercontent.com/$Repo/$TestVersion/scripts/host/install.ps1"
    $InstallScript = Join-Path $TestDir "install_old.ps1"

    Invoke-WebRequest -UseBasicParsing -Uri $InstallUrl -OutFile $InstallScript

    # Run the downloaded old-installer via the hardened child-process path
    # (Bypass + Unblock-File on this harness-written copy). NOTE: files written
    # by Invoke-WebRequest -OutFile do NOT normally carry Mark-of-the-Web (MOTW
    # is applied by the browser's Attachment Manager, not by IWR), so this
    # invocation is the least exposed -- hardened anyway for consistency.
    # $env:DAAF_* set below are inherited by the child via Start-Process
    # -NoNewWindow.
    $env:DAAF_BRANCH = $TestVersion
    $env:DAAF_NESTED = "1"
    $installExit = Invoke-HardenedScript -Path $InstallScript
    Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
    Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
    if ($installExit -ne 0) {
        Write-Host "WARNING: Old-version install.ps1 exited with code $installExit." -ForegroundColor Yellow
        Write-Host "WARNING: The volume check below will confirm whether the install actually succeeded." -ForegroundColor Yellow
    }
    # install.ps1 creates .\daaf-docker under the invocation directory.
    $script:HostDir = Join-Path $TestDir "daaf-docker"
}

# Verify install succeeded
if (-not (Test-DockerVolume $VolumeName)) {
    Write-Error "Installation failed - volume $VolumeName not found."
    exit 1
}
if (-not (Test-Path (Join-Path $script:HostDir "docker-compose.yml"))) {
    Write-Host "WARNING: docker-compose.yml not found in $($script:HostDir) - migration will treat this as a compose-less host dir." -ForegroundColor Yellow
}

Write-Host "SUCCESS: DAAF $TestVersion installed via the Era $TestEra pathway." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 3: Verify Era State
# =====================================================================
# The old harness "simulated" Era 2 here by stripping the remote from a modern
# shallow clone. That never produced a real Era 2 repo (genuine upstream
# history remained, and the shallow boundary commit's visible parent lines
# fooled migrate_daaf's graft-already-in-place check into skipping the graft
# entirely). Phase 2 now replays the real pathways, so this phase only WAITS
# for and VERIFIES the era state the install should have produced -- if the
# state is wrong, that is a broken replay and the run stops here rather than
# feeding Phase 7 misleading results.
Write-Host "[3/7] Verify Era $TestEra state" -ForegroundColor White
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
}

# Wait for exec readiness (fresh first boot can lag briefly)
$retries = 0
while ($retries -lt 30) {
    Invoke-ContainerExec true 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    $retries++
    Start-Sleep -Seconds 2
}
if ($retries -ge 30) {
    Write-Error "Container $($script:ContainerName) did not become exec-ready within 60 seconds."
    exit 1
}

if ($TestEra -eq "1") {
    # Era 1 expectation: /daaf carries the clone's full .git -- origin remote
    # pointing at the official repo, branch main checked out.
    $OriginCheck = Invoke-ContainerGit remote get-url origin
    $BranchCheck = Invoke-ContainerGit branch --show-current
    if ($OriginCheck -match $Repo -and $BranchCheck -eq "main") {
        Write-Host "SUCCESS: Era 1 state verified (origin remote + branch main from the clone)." -ForegroundColor Green
    } else {
        Write-Error "Era 1 replay did not produce the expected state (origin: '$OriginCheck', branch: '$BranchCheck'). Expected the documented clone flow to leave origin=$Repo and branch=main."
        exit 1
    }

} elseif ($TestEra -eq "2") {
    # Era 2 expectation: the era's entrypoint git-inits /daaf on FIRST start
    # (git init; branch -m main; add -A; commit "Initial commit: DAAF
    # framework"; no remote). The commit of the full tree can take a few
    # seconds after the container reports running -- wait for HEAD to exist.
    Write-Host "INFO: Waiting for the era's entrypoint to git-init /daaf (first boot)..." -ForegroundColor Cyan
    $retries = 0
    $HeadSha = ""
    while ($retries -lt 30) {
        $HeadSha = Invoke-ContainerGit rev-parse HEAD
        if (-not [string]::IsNullOrWhiteSpace($HeadSha) -and $HeadSha -notmatch 'HEAD') { break }
        $retries++
        Start-Sleep -Seconds 2
    }
    if ([string]::IsNullOrWhiteSpace($HeadSha) -or $HeadSha -match 'HEAD') {
        Write-Error "Era 2 entrypoint never produced an initial commit in /daaf (waited 60s). The ZIP-era replay is broken - inspect container logs: docker logs $($script:ContainerName)"
        exit 1
    }

    $OriginCheck = Invoke-ContainerGit remote get-url origin
    $BranchCheck = Invoke-ContainerGit branch --show-current
    $CommitCount = Invoke-ContainerGit rev-list --count HEAD
    if ([string]::IsNullOrWhiteSpace($OriginCheck) -and $BranchCheck -eq "main" -and $CommitCount -eq "1") {
        # Capture the synthetic root's SHA NOW, pre-migration. Check 3 must
        # interrogate THIS commit later: `git replace --graft` adds a
        # replacement ref rather than rewriting the root, so post-graft
        # `rev-list --max-parents=0 HEAD` walks THROUGH the grafted root into
        # upstream history and returns upstream's genuine root -- parentless
        # by definition, forever. Inspecting that commit produced run 3's
        # false FAIL (repro: scripts/scratch/graft_repro.sh in the session
        # workspace -- cat-file on the synthetic root shows 1 parent
        # post-graft; on rev-list's answer, 0).
        $script:Era2RootSha = $HeadSha
        Write-Host "SUCCESS: Era 2 state verified (local-only repo, single synthetic root commit $($HeadSha.Substring(0, [Math]::Min(12, $HeadSha.Length))), no remote)." -ForegroundColor Green
    } else {
        Write-Error "Era 2 replay did not produce the expected state (origin: '$OriginCheck', branch: '$BranchCheck', commits: '$CommitCount'). Expected: no remote, branch main, exactly 1 entrypoint commit."
        exit 1
    }

} else {
    # Era 3 expectation: install.ps1 cloned with origin retained. For a TAG,
    # the shallow `-b <tag>` clone leaves a detached HEAD no real user had
    # (real users installed from branch main) -- normalize per the header note.
    $OriginCheck = Invoke-ContainerGit remote get-url origin
    if ([string]::IsNullOrWhiteSpace($OriginCheck)) {
        Write-Error "Era 3 install left no origin remote - unexpected for the modern install pathway."
        exit 1
    }

    if ($TestVersion -match '^v\d+\.\d+\.\d+$') {
        Write-Host "INFO: Normalizing tag install to a real user's git state (checkout -B main at the tag commit)..." -ForegroundColor Cyan
        $null = Invoke-ContainerGit checkout -B main
        $BranchCheck = Invoke-ContainerGit branch --show-current
        if ($BranchCheck -ne "main") {
            Write-Error "Era 3 normalization failed - expected branch main, got '$BranchCheck'."
            exit 1
        }
    }
    Write-Host "SUCCESS: Era 3 state verified (origin remote present: $OriginCheck)." -ForegroundColor Green
}

Write-Host ""

# =====================================================================
# PHASE 4: Simulate User Work (Committed)
# =====================================================================
Write-Host "[4/7] Simulate committed user work" -ForegroundColor White
Write-Host ""

Write-Host "INFO: Creating committed framework changes and research files..." -ForegroundColor Cyan

# FIXTURE RULES (both learned from field failures):
#   - No embedded double quotes in any docker-exec argv (PS 5.1 mangles them;
#     the old fixtures here silently created NOTHING and printed "Test"/"Work").
#     Multi-line or quote-bearing content goes through Write-ContainerFile.
#   - Framework-change markers live in NEW files (upstream has no such path,
#     so update merges can never conflict on them). The old CLAUDE.md-append
#     markers were conflict bait: daaf_dev heavily rewrites CLAUDE.md relative
#     to the old eras, and a merge conflict would abort the update for reasons
#     unrelated to migration correctness.

# Create a research project
Invoke-ContainerExec mkdir -p /daaf/research/2026-01-15_Test_Analysis/data /daaf/research/2026-01-15_Test_Analysis/scripts /daaf/research/2026-01-15_Test_Analysis/output

Write-ContainerFile -Path "/daaf/research/2026-01-15_Test_Analysis/scripts/01_fetch.py" -Content @'
# --- Config ---
import polars as pl

BASE_DIR = "/daaf"
PROJECT_DIR = f"{BASE_DIR}/research/2026-01-15_Test_Analysis"

# --- Load ---
# INTENT: Fetch test data for migration verification
print("Test script executed successfully")
'@

Write-ContainerFile -Path "/daaf/research/2026-01-15_Test_Analysis/data/test_data.txt" -Content 'Test analysis data'
Write-ContainerFile -Path "/daaf/research/2026-01-15_Test_Analysis/README.md" -Content '# Test Analysis'

# Make a framework modification: a NEW file under agent_reference/ (see
# FIXTURE RULES above for why this is not a CLAUDE.md append).
Write-ContainerFile -Path "/daaf/agent_reference/test_migration_marker.md" -Content 'test-migration-marker: committed'

# Commit everything
$null = Invoke-ContainerGit add -A
$null = Invoke-ContainerGit commit -m "Test: Add research project and framework tweaks"

$CommittedSha = Invoke-ContainerGit rev-parse HEAD
if ([string]::IsNullOrWhiteSpace($CommittedSha)) {
    Write-Error "Fixture commit failed - no HEAD SHA readable. Cannot proceed to migration with unplanted fixtures."
    exit 1
}
# Verify the fixtures actually landed IN the commit (the old harness only
# discovered missing fixtures at Phase 7, after migration had already run).
$CommittedFiles = Invoke-ContainerGit show --name-only --format= HEAD
foreach ($MustHave in @(
    "research/2026-01-15_Test_Analysis/scripts/01_fetch.py",
    "research/2026-01-15_Test_Analysis/data/test_data.txt",
    "agent_reference/test_migration_marker.md"
)) {
    if ($CommittedFiles -notmatch [regex]::Escape($MustHave)) {
        Write-Error "Fixture file '$MustHave' is missing from the fixture commit - aborting before migration."
        exit 1
    }
}
Write-Host "INFO: Committed changes at: $($CommittedSha.Substring(0, [Math]::Min(12, $CommittedSha.Length)))" -ForegroundColor Cyan
Write-Host "SUCCESS: Committed user work created." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 5: Simulate User Work (Uncommitted)
# =====================================================================
Write-Host "[5/7] Simulate uncommitted user work" -ForegroundColor White
Write-Host ""

Write-Host "INFO: Creating uncommitted framework changes and research files..." -ForegroundColor Cyan

# Add more uncommitted research files (untracked -- the updater never touches
# untracked files, so these must survive verbatim)
Invoke-ContainerExec mkdir -p /daaf/research/2026-02-10_WIP_Analysis/scripts
Write-ContainerFile -Path "/daaf/research/2026-02-10_WIP_Analysis/notes.md" -Content 'Work in progress data'
Write-ContainerFile -Path "/daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py" -Content @'
# --- Config ---
# INTENT: WIP exploration script - uncommitted
print("WIP script")
'@

# Make an uncommitted framework change: a NEW untracked file (see Phase 4
# FIXTURE RULES for why this is not a CLAUDE.md append).
Write-ContainerFile -Path "/daaf/agent_reference/test_migration_marker_uncommitted.md" -Content 'test-migration-marker: uncommitted'

# Dirty a TRACKED file: append a line to the README committed in Phase 4.
# This is what exercises the updater's stash/pop path (dirty tracked changes
# get stashed before the merge and popped after). It lives in research/ where
# upstream never writes, so the pop can never conflict. The payload contains
# no double quotes (PS 5.1 argv rule) -- a bare word needs no quoting at all.
Invoke-ContainerExec bash -c 'echo uncommitted-stash-check >> /daaf/research/2026-01-15_Test_Analysis/README.md'

# Verify the uncommitted fixtures actually exist before migration runs
foreach ($MustExist in @(
    "/daaf/research/2026-02-10_WIP_Analysis/notes.md",
    "/daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py",
    "/daaf/agent_reference/test_migration_marker_uncommitted.md"
)) {
    Invoke-ContainerExec test -f $MustExist
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Uncommitted fixture '$MustExist' was not created - aborting before migration."
        exit 1
    }
}
Invoke-ContainerExec grep -q uncommitted-stash-check /daaf/research/2026-01-15_Test_Analysis/README.md
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dirty-file fixture (README.md append) was not created - aborting before migration."
    exit 1
}

Write-Host "SUCCESS: Uncommitted user work created." -ForegroundColor Green
Write-Host ""

# =====================================================================
# PHASE 6: Run Migration
# =====================================================================
Write-Host "[6/7] Run migration script" -ForegroundColor White
Write-Host ""

Write-Host "INFO: Copying migration script from local repo..." -ForegroundColor Cyan

# The host directory is era-specific (set in Phase 2): the clone dir (Era 1),
# the extracted ZIP dir (Era 2), or install.ps1's daaf-docker dir (Era 3) --
# i.e., wherever a real user of that era would run migrate_daaf.ps1 from (the
# directory holding docker-compose.yml).
$HostDir = $script:HostDir
if (-not (Test-Path $HostDir)) {
    Write-Error "Era host directory vanished: $HostDir"
    exit 1
}

# Copy the local migration script to the host dir
Copy-Item $LocalMigratePath (Join-Path $HostDir "migrate_daaf.ps1") -Force

Write-Host "INFO: Running migration with DAAF_BRANCH=$MigrationBranch..." -ForegroundColor Cyan
Write-Host ""

Set-Location $HostDir

# Snapshot whether the Claude state volume exists RIGHT NOW, immediately before
# migration runs. The backup-content assertion (Check 11) needs to know whether
# the source volume existed AT BACKUP TIME, and backup happens inside migration.
# Capturing the flag here -- rather than re-inspecting live after migration --
# makes the gate robust: anything migration does afterward (a fallback
# `docker compose up` against the current compose file, or phase 8's install.ps1)
# can legitimately create the volume, and a post-migration inspect would then
# wrongly flip an absent-at-backup-time skip into a FAIL.
$ClaudeVolumeExistedPreMigration = Test-DockerVolume $ClaudeVolumeName

# Run migration non-interactively via the hardened child-process path. The copy
# at $HostDir\migrate_daaf.ps1 is harness-owned (copied above), so Unblock-File +
# -ExecutionPolicy Bypass inside Invoke-HardenedScript defeat the RemoteSigned
# "...is not digitally signed" refusal seen in the field when the local repo
# lived under a Downloads path carrying Mark-of-the-Web. $env:DAAF_* set below
# are inherited by the child via Start-Process -NoNewWindow.
$env:DAAF_BRANCH = $MigrationBranch
$env:DAAF_NESTED = "1"

# Capture the child exit code. Wrap in try/catch too: a spawn failure (e.g. the
# host exe cannot be resolved) throws rather than returning a code, and that is
# itself a migration failure that must be recorded truthfully.
$migrationExit = 1
try {
    $migrationExit = Invoke-HardenedScript -Path (Join-Path $HostDir "migrate_daaf.ps1")
} catch {
    Write-Host "ERROR: Could not run the migration script: $_" -ForegroundColor Red
    $migrationExit = 1
}

Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue

Write-Host ""
# Fix B: report the migration outcome TRUTHFULLY. A nonzero exit (or a spawn
# failure caught above) is a real FAIL fed into the results counter -- never
# printed as SUCCESS. Verification (Phase 7) still runs regardless, because it
# shows the blast radius of a failed migration; but it runs under a banner that
# makes clear migration itself failed.
if ($migrationExit -eq 0) {
    Write-Host "SUCCESS: Migration script completed (exit code 0)." -ForegroundColor Green
    Test-Check "Migration script completed successfully (exit 0)" $true
} else {
    Write-Host "FAIL: Migration script did NOT complete successfully (exit code $migrationExit)." -ForegroundColor Red
    Write-Host "      Verification below still runs to show the blast radius, but migration itself FAILED." -ForegroundColor Red
    Test-Check "Migration script completed successfully (exit $migrationExit)" $false
}
Write-Host ""

# =====================================================================
# PHASE 7: Verification
# =====================================================================
Write-Host "[7/7] Verification" -ForegroundColor White
if ($migrationExit -ne 0) {
    Write-Host "  (Migration FAILED with exit code $migrationExit -- the checks below report the blast radius, not a healthy migration.)" -ForegroundColor Red
}
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

# Check 2: Upstream tracking is set.
# Expected tracking is era- and ref-aware:
#   - Era 1/2 and Era 3 TAGS: local main exists (from the era pathway or the
#     Phase 3 normalization), migrate sets main -> origin/main, and the
#     updater always returns HEAD to the branch it started on. Expect
#     origin/main.
#   - Era 3 BRANCH installs (e.g. daaf_dev): no local main ever exists; the
#     clone's branch keeps its own tracking (origin/<branch>). migrate's
#     set-upstream to main is a silent no-op there -- and it prints "Tracking
#     set: main -> origin/main" regardless (documented production wart, see
#     SESSION_NOTES.md in the harness workspace).
$ExpectedTracking = "origin/main"
if ($TestEra -eq "3" -and $TestVersion -notmatch '^v\d+\.\d+\.\d+$') {
    $ExpectedTracking = "origin/$TestVersion"
}
$Tracking = Invoke-ContainerGit rev-parse --abbrev-ref --symbolic-full-name '@{u}'
if ($Tracking -eq $ExpectedTracking) {
    Test-Check "Upstream tracking set to $ExpectedTracking" $true
} else {
    Test-Check "Upstream tracking set to $ExpectedTracking (got: '$Tracking')" $false
}

# Check 3: Era 2 only - the graft must now exist ON THE SYNTHETIC ROOT whose
# SHA Phase 3 captured pre-migration. Do NOT re-discover the root with
# `rev-list --max-parents=0` here: after a SUCCESSFUL graft that command walks
# through the replaced root and returns upstream's genuine root, which is
# parentless forever -- inspecting it produced a false FAIL on a healthy
# migration (field run 3; repro in the session workspace's
# scripts/scratch/graft_repro.sh). cat-file honors replace refs, so the
# grafted parent is visible on the captured SHA.
if ($TestEra -eq "2") {
    if (-not [string]::IsNullOrWhiteSpace($script:Era2RootSha)) {
        $CatFileOutput = Invoke-ContainerGit cat-file -p $script:Era2RootSha
        $ParentCount = 0
        if (-not [string]::IsNullOrWhiteSpace($CatFileOutput)) {
            # Wrap in @(): with exactly ONE matching line (a grafted root has
            # exactly one parent -- the expected success case!) Where-Object
            # returns a scalar string, and .Count on a scalar (or on the
            # zero-match null) throws PropertyNotFoundStrict under
            # Set-StrictMode 3.0. Field failure 2026-07-06; migrate_daaf.ps1
            # guards this same expression with @().
            $ParentCount = @($CatFileOutput -split "`n" | Where-Object { $_ -match '^parent ' }).Count
        }
        Test-Check "Era 2 graft in place (synthetic root now has a parent)" ($ParentCount -gt 0)
    } else {
        Test-Check "Era 2 graft in place (pre-migration root SHA was not captured)" $false
    }
}

# Check 3b (all eras): a common ancestor with origin/main must exist -- via
# genuine history (Era 1/3) or via the graft (Era 2). This is the property
# update_daaf's merges depend on.
$MergeBase = Invoke-ContainerGit merge-base HEAD origin/main
Test-Check "Common ancestor exists with origin/main" (-not [string]::IsNullOrWhiteSpace($MergeBase))

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

# Check 6: Committed framework marker file survived (content-verified).
# Direct argv (no bash -c): the pattern contains a space but no double quotes,
# so PS 5.1 passes it as one clean argument -- no shell re-tokenization risk.
Invoke-ContainerExec grep -q 'test-migration-marker: committed' /daaf/agent_reference/test_migration_marker.md
Test-Check "Committed framework changes preserved" ($LASTEXITCODE -eq 0)

# Check 7: Uncommitted (untracked) framework marker file survived
Invoke-ContainerExec grep -q 'test-migration-marker: uncommitted' /daaf/agent_reference/test_migration_marker_uncommitted.md
Test-Check "Uncommitted framework changes preserved" ($LASTEXITCODE -eq 0)

# Check 7b: Dirty tracked change survived. If the user took the update,
# update_daaf stashed this before merging and popped it after -- this line
# surviving is the stash/pop path working end to end. If the update was
# declined, migration alone must not have touched it either way.
Invoke-ContainerExec grep -q uncommitted-stash-check /daaf/research/2026-01-15_Test_Analysis/README.md
Test-Check "Dirty tracked change preserved (updater stash/pop path)" ($LASTEXITCODE -eq 0)

# Check 8: Committed SHA still in history
$GitLog = Invoke-ContainerGit log --oneline
$ShortSha = $CommittedSha.Substring(0, [Math]::Min(7, $CommittedSha.Length))
Test-Check "Committed changes still in git history" ($GitLog -match $ShortSha)

Write-Host ""
Write-Host "  Host Script Checks:" -ForegroundColor White

# Check 9: Host scripts were downloaded.
# This list mirrors what migrate_daaf.ps1 actually fetches today (see its
# "foreach ($File in @(...))" download loop): the .ps1 utility set plus the two
# shipped text files. Note this DIFFERS from the .sh twin: daaf.sh/daaf_lib.sh
# are never shipped to Windows (commit 4fa8c43), so they are absent here by
# design; Windows gets daaf.ps1/daaf_lib.ps1 instead.
foreach ($Script in @("daaf.ps1", "daaf_lib.ps1", "backup_daaf.ps1", "restore_from_backup.ps1", "rebuild_daaf.ps1", "update_daaf.ps1", "run_daaf.ps1", "view_logs.ps1", "view_notebooks.ps1", "view_quarto.ps1", "run_vscode.ps1", "environment_settings_example.txt", "README.txt")) {
    Test-Check "Host script downloaded: $Script" (Test-Path (Join-Path $HostDir $Script))
}

Write-Host ""
Write-Host "  Backup Checks:" -ForegroundColor White

# Check 10: Backup directory was created during migration
$BackupDir = Get-ChildItem -Path $HostDir -Directory -Filter '*_daaf_backup' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $BackupDir) {
    Test-Check "Backup directory created during migration" $true

    # Check 11: Backup content is complete. The on-disk backup layout produced by
    # backup_daaf.ps1 (verified against that script) is:
    #   <backup>\                      data-volume CONTENTS at the root (CLAUDE.md,
    #                                  research\, etc. -- copied via "docker cp .../.")
    #   <backup>\.daaf-claude-config\  Claude Code state volume payload (hidden
    #                                  subfolder; ONLY present if the claude-config
    #                                  volume existed at backup time)
    #   <backup>\.daaf-permissions     executable-permission manifest at the root
    #   <backup>\.daaf-symlinks        symlink manifest at the root (always present
    #                                  in current backups -- 0-byte when the volume
    #                                  has no symlinks; absent only in pre-feature backups)
    #
    # Data payload: assert a known volume file (CLAUDE.md) is at the backup root.
    Test-Check "Backup contains data-volume payload (CLAUDE.md at root)" (Test-Path (Join-Path $BackupDir.FullName "CLAUDE.md"))

    # Permissions manifest: always written by a current backup_daaf.ps1.
    Test-Check "Backup contains .daaf-permissions manifest" (Test-Path (Join-Path $BackupDir.FullName ".daaf-permissions"))

    # Symlink manifest: CONDITIONAL on the backup ERA, not on symlink presence.
    # backup_daaf.ps1's staging step always runs `paste`, which ALWAYS creates
    # .daaf-symlinks (a 0-byte file when the volume has no symlinks) -- so a CURRENT
    # backup always has the file, and absence means only that the backup predates
    # this feature. This harness replays pre-feature eras, where the manifest is
    # legitimately absent, so a missing file here is NOT a defect: present => PASS;
    # absent => informational skip (pre-feature backup).
    if (Test-Path (Join-Path $BackupDir.FullName ".daaf-symlinks")) {
        Test-Check "Backup contains .daaf-symlinks manifest" $true
    } else {
        Write-Host "  INFO: Skipped .daaf-symlinks check: no symlink manifest in this backup (it predates the symlink-safe backup feature; current backups always include the file, 0-byte when the volume has no symlinks)." -ForegroundColor Cyan
    }

    # Claude state payload: CONDITIONAL. backup_daaf.ps1 only writes the
    # .daaf-claude-config\ subfolder when the claude-config volume exists at
    # backup time. Every era this harness replays (v1.0.0 through v2.1.0)
    # predates that volume -- their compose files define no claude-config
    # volume, and the migration backs up BEFORE any current-compose
    # `docker compose up` could create it, so the subfolder is legitimately
    # absent there. Gate the assertion on $ClaudeVolumeExistedPreMigration -- the flag
    # captured just before migration (phase 6) -- NOT on a live inspect here: by
    # this point migration (and, on non-skipped runs, phase 8's install.ps1) may
    # have created the volume, which a live inspect would mistake for "should have
    # been in the backup." Three-way outcome: subfolder present -> PASS; absent
    # but volume existed pre-migration -> FAIL (a real backup gap); absent and
    # volume did not exist pre-migration -> informational skip.
    $ClaudeSub = Join-Path $BackupDir.FullName ".daaf-claude-config"
    if (Test-Path $ClaudeSub) {
        Test-Check "Backup contains Claude state payload (.daaf-claude-config\)" $true
    } elseif ($ClaudeVolumeExistedPreMigration) {
        # The volume existed at backup time yet the subfolder is missing -- real gap.
        Test-Check "Backup contains Claude state payload (.daaf-claude-config\)" $false
    } else {
        Write-Host "  INFO: Skipped Claude state payload check: source volume '$ClaudeVolumeName' did not exist at backup time (install predates it)." -ForegroundColor Cyan
    }
} else {
    Test-Check "Backup directory created during migration" $false
    Write-Host "  WARNING: Skipping backup-content checks: no backup directory to inspect." -ForegroundColor Yellow
}

# =====================================================================
# PHASE 8: Multi-Instance Coexistence (DAAF_PROJECT_NAME end-to-end)
# =====================================================================
# WHY a POST-migration phase rather than a migrated multi-instance install:
# a historical multi-instance migration is impossible. Old DAAF versions predate
# DAAF_PROJECT_NAME, so every real old install carries the DEFAULT names -- there
# is no such thing as an "old daaftest2 install" to migrate. So the honest way to
# exercise the DAAF_PROJECT_NAME machinery is to stand up a fresh CURRENT-branch
# second instance ALONGSIDE the migrated default one and prove they coexist, then
# tear the second one down cleanly.
if (-not $SkipMultiInstance) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor White
    Write-Host "  Phase 8: Multi-Instance Coexistence" -ForegroundColor White
    Write-Host "==========================================" -ForegroundColor White
    Write-Host ""
    Write-Host "  Second project: $SecondProjectName"
    Write-Host "  Ports:          marimo=$SecondPortMarimo log=$SecondPortLogviewer vscode=$SecondPortVscode"
    Write-Host ""

    # --- 8a. Create the second install directory + environment_settings.txt ---
    Write-Host "INFO: Creating second install directory and environment_settings.txt..." -ForegroundColor Cyan
    $SecondDir = Join-Path $TestDir "instance2"
    $null = New-Item -ItemType Directory -Path $SecondDir -Force

    # Write the four multi-instance keys the compose file interpolates. The key
    # names (DAAF_PROJECT_NAME / DAAF_PORT_MARIMO / DAAF_PORT_LOGVIEWER /
    # DAAF_PORT_VSCODE) match environment_settings_example.txt and how
    # install.ps1/rebuild_daaf.ps1 read them. install.ps1 derives the volume name
    # from DAAF_PROJECT_NAME (process env first), and compose interpolates all
    # four from the process env at build/up time -- so setting them below is what
    # makes the second instance actually reproject. ASCII, LF-friendly content.
    $EnvLines = @(
        "DAAF_PROJECT_NAME=$SecondProjectName",
        "DAAF_PORT_MARIMO=$SecondPortMarimo",
        "DAAF_PORT_LOGVIEWER=$SecondPortLogviewer",
        "DAAF_PORT_VSCODE=$SecondPortVscode"
    )
    Set-Content -LiteralPath (Join-Path $SecondDir "environment_settings.txt") -Value $EnvLines -Encoding Ascii
    Write-Host "SUCCESS: Second environment_settings.txt written." -ForegroundColor Green
    Write-Host ""

    # --- 8b. Bring up a fresh CURRENT-branch instance there ---
    # MECHANISM CHOICE: reuse the local install.ps1 (from the migration branch's
    # repo checkout) rather than hand-rolling `docker compose up`. Rationale:
    # install.ps1 is the ONLY mechanism that both (1) stands up the container with
    # the correct project-prefixed names AND (2) populates /daaf via git clone.
    # A bare `docker compose up` against the fetched compose file would start an
    # EMPTY-/daaf container (no repo clone), which is not a realistic instance and
    # would make the coexistence checks meaningless. install.ps1 already reads
    # DAAF_PROJECT_NAME (process env wins) to derive its volume name, and compose
    # reads all four DAAF_* keys from the process env for interpolation -- so we
    # set them, point install.ps1 at the current branch, and run it in the second
    # directory. DAAF_NESTED suppresses its exit pause.
    if (-not (Test-Path $LocalInstallPath)) {
        Write-Host "WARNING: Cannot find install.ps1 at $LocalInstallPath - skipping multi-instance bring-up." -ForegroundColor Yellow
    } else {
        Write-Host "INFO: Bringing up second instance from branch '$MigrationBranch' via install.ps1..." -ForegroundColor Cyan
        Write-Host ""

        # This was the second field-failure site: invoking install.ps1 directly
        # from the user's Downloads-path repo hit the same RemoteSigned "...is
        # not digitally signed" refusal. We must NOT Unblock-File the user's repo
        # original ($LocalInstallPath), so COPY it into the harness-owned second
        # install dir first and run the COPY via Invoke-HardenedScript (which
        # unblocks only that copy + spawns with -ExecutionPolicy Bypass).
        # install.ps1 is location-independent -- it derives its install dir from
        # the CURRENT working directory (Get-Location -> .\daaf-docker) and pulls
        # compose/scripts from GitHub, so running the copy from $SecondDir is
        # equivalent to running the original there.
        $SecondInstallCopy = Join-Path $SecondDir "install.ps1"
        Copy-Item $LocalInstallPath $SecondInstallCopy -Force

        # Save prior values of EVERY env var + the location we mutate below, and
        # initialize each saved-value variable BEFORE the try so no finally path
        # reads an unassigned variable under Set-StrictMode 3.0. All mutations
        # (the four DAAF_* keys, DAAF_BRANCH, DAAF_NESTED, DAAF_FORCE_REINSTALL)
        # and the Set-Location move happen INSIDE the try so the finally always
        # restores the caller's exact prior state -- clearing a var only when it
        # was genuinely unset, never clobbering a caller-set value.
        $savedProject = $env:DAAF_PROJECT_NAME
        $savedMarimo = $env:DAAF_PORT_MARIMO
        $savedLog = $env:DAAF_PORT_LOGVIEWER
        $savedVscode = $env:DAAF_PORT_VSCODE
        $savedBranch = $env:DAAF_BRANCH
        $savedNested = $env:DAAF_NESTED
        $savedForceReinstall = $env:DAAF_FORCE_REINSTALL
        $savedLocation = (Get-Location).Path
        try {
            Set-Location $SecondDir
            $env:DAAF_PROJECT_NAME = $SecondProjectName
            $env:DAAF_PORT_MARIMO = $SecondPortMarimo
            $env:DAAF_PORT_LOGVIEWER = $SecondPortLogviewer
            $env:DAAF_PORT_VSCODE = $SecondPortVscode
            $env:DAAF_BRANCH = $MigrationBranch
            $env:DAAF_NESTED = "1"
            # Force a clean re-install so a leftover daaftest2 install (e.g. from an
            # aborted prior run whose phase-1 cleanup never ran) cannot make install.ps1
            # halt at its "existing installation detected" prompt and hang/abort the harness.
            $env:DAAF_FORCE_REINSTALL = "1"
            $secondInstallExit = Invoke-HardenedScript -Path $SecondInstallCopy
            if ($secondInstallExit -ne 0) {
                Write-Host "WARNING: Second-instance install.ps1 exited with code $secondInstallExit." -ForegroundColor Yellow
                Write-Host "WARNING: Coexistence checks below will show what actually came up." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "WARNING: Second-instance install.ps1 could not be run: $_" -ForegroundColor Yellow
            Write-Host "WARNING: Coexistence checks below will show what actually came up." -ForegroundColor Yellow
        } finally {
            # Restore the caller's environment (null-safe: clear if it was unset).
            if ($null -ne $savedProject) { $env:DAAF_PROJECT_NAME = $savedProject } else { Remove-Item Env:\DAAF_PROJECT_NAME -ErrorAction SilentlyContinue }
            if ($null -ne $savedMarimo) { $env:DAAF_PORT_MARIMO = $savedMarimo } else { Remove-Item Env:\DAAF_PORT_MARIMO -ErrorAction SilentlyContinue }
            if ($null -ne $savedLog) { $env:DAAF_PORT_LOGVIEWER = $savedLog } else { Remove-Item Env:\DAAF_PORT_LOGVIEWER -ErrorAction SilentlyContinue }
            if ($null -ne $savedVscode) { $env:DAAF_PORT_VSCODE = $savedVscode } else { Remove-Item Env:\DAAF_PORT_VSCODE -ErrorAction SilentlyContinue }
            if ($null -ne $savedBranch) { $env:DAAF_BRANCH = $savedBranch } else { Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue }
            if ($null -ne $savedNested) { $env:DAAF_NESTED = $savedNested } else { Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue }
            if ($null -ne $savedForceReinstall) { $env:DAAF_FORCE_REINSTALL = $savedForceReinstall } else { Remove-Item Env:\DAAF_FORCE_REINSTALL -ErrorAction SilentlyContinue }
            Set-Location $savedLocation
        }
    }

    Write-Host ""

    # --- 8c. Verify coexistence ---
    Write-Host "  Multi-Instance Checks:" -ForegroundColor White

    # Second instance container is running
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $SecondState = (docker inspect --format '{{.State.Status}}' $SecondContainerMain 2>$null | Out-String).Trim() -replace "`r",""
    $ErrorActionPreference = $savedEAP
    if ($SecondState -eq "running") {
        Test-Check "Second instance container running ($SecondContainerMain)" $true
    } else {
        Test-Check "Second instance container running ($SecondContainerMain) (state: '$SecondState')" $false
    }

    # Second instance volumes exist
    Test-Check "Second instance data volume exists ($SecondVolumeName)" (Test-DockerVolume $SecondVolumeName)
    Test-Check "Second instance Claude volume exists ($SecondClaudeVolumeName)" (Test-DockerVolume $SecondClaudeVolumeName)

    # The migrated DEFAULT instance must still be intact (coexistence, untouched)
    Test-Check "Default instance container still present ($ContainerMain)" (Test-DockerContainer $ContainerMain)
    Test-Check "Default instance data volume still present ($VolumeName)" (Test-DockerVolume $VolumeName)

    Write-Host ""

    # --- 8d. Tear the second instance down completely ---
    # Remove container, init container, and both volumes. IMAGE DECISION: remove
    # the second image too. `docker compose build` tags the image from the compose
    # PROJECT name, so with name=daaftest2 the second image is a DISTINCT tag
    # (daaftest2-daaf-docker), NOT shared with the default instance's
    # daaf-daaf-docker -- removing it cannot affect the default instance. The
    # busybox init IMAGE, by contrast, IS shared across instances, so leave it
    # alone (nuke_daaf.ps1 only removes busybox when no container references it).
    Write-Host "INFO: Tearing down the second instance (container, init, volumes, distinct image)..." -ForegroundColor Cyan
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker rm -f $SecondContainerMain 2>&1 | Out-Null
    docker rm -f $SecondContainerInit 2>&1 | Out-Null
    docker volume rm $SecondVolumeName 2>&1 | Out-Null
    docker volume rm $SecondClaudeVolumeName 2>&1 | Out-Null
    docker rmi $SecondImageName 2>&1 | Out-Null
    $ErrorActionPreference = $savedEAP

    # Verify teardown succeeded
    Test-Check "Second instance container removed" (-not (Test-DockerContainer $SecondContainerMain))
    Test-Check "Second instance data volume removed" (-not (Test-DockerVolume $SecondVolumeName))

    # Coexistence sanity: the default instance survived the teardown untouched.
    Test-Check "Default instance data volume survived second-instance teardown" (Test-DockerVolume $VolumeName)

    Write-Host "SUCCESS: Second instance torn down." -ForegroundColor Green
    Set-Location $HostDir
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "INFO: Phase 8 (multi-instance) skipped via -SkipMultiInstance / SKIP_MULTI_INSTANCE=1." -ForegroundColor Cyan
    Write-Host ""
}

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
