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
# backup, and rebuild -- in interactive mode you drive those choices, exactly as
# an end user would, and the Phase 7 checks are designed to pass whichever way you
# answer. In auto mode (-Auto / -All) the child scripts run non-interactive (their
# stdin is redirected from an empty file, the .ps1 non-interactive seam) and every
# prompt auto-selects its first valid choice, so no tester input is needed.
# HISTORICAL WART (now FIXED): earlier revisions of migrate_daaf.ps1 /
# update_daaf.ps1 / daaf.ps1 clobbered the harness's DAAF_NESTED suppression (they
# set-then-Remove-Item instead of save/restore), which surfaced up to 2-3 stray
# "Press Enter to continue/close" pauses from the child scripts. That is FIXED as
# of commit 4cd280d (2026-07-17): all 6 clobber sites now save and restore
# DAAF_NESTED, so stray pauses are no longer expected on current main /
# daaf_dev_R2. Auto mode is additionally immune by construction -- the child's
# stdin is an empty redirect, so even a stray Read-Host reads EOF and returns
# immediately (no hang possible even if the wart ever regressed). See
# research/2026-07-06_FrameworkDev_MigrationTestHarness/SESSION_NOTES.md for the
# original finding.
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
#   .\test_migration.ps1                                       # v2.0.1, Era 2 (interactive)
#   $env:DAAF_TEST_VERSION = "v1.0.0"; .\test_migration.ps1    # Era 1
#   $env:DAAF_TEST_VERSION = "v2.1.0"; .\test_migration.ps1    # Era 3 (tag)
#   $env:DAAF_TEST_VERSION = "daaf_dev"; .\test_migration.ps1  # Era 3 (branch)
#   $env:DAAF_TEST_VERSION = "fresh"; .\test_migration.ps1     # FRESH-INSTALL track (no migration)
#   .\test_migration.ps1 -Auto                                 # non-interactive single vector
#   .\test_migration.ps1 -All                                  # matrix: fresh + v1.0.0 + v2.0.1 + v2.1.0
#   .\test_migration.ps1 -SkipMultiInstance                    # skip phase 8 (or SKIP_MULTI_INSTANCE=1)
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
# ----------------------------------------------------------------------------
# TWO TRACKS
# ----------------------------------------------------------------------------
#   MIGRATION TRACK (default): install an OLD version the era-authentic way,
#     plant fixtures, run migrate_daaf.ps1, then (in -Auto) drive update_daaf.ps1,
#     and verify the end state. This is everything below Phase 2.
#   FRESH-INSTALL TRACK (DAAF_TEST_VERSION=fresh): no old version, no migration.
#     Runs the LOCAL install.ps1 from a clean slate, verifies the install landed
#     (container up, branch, host scripts present, environment_settings seeded,
#     functional smoke), and asserts a second install is refused by the
#     existing-install guard. Exits after its own compact results block.
#
# ----------------------------------------------------------------------------
# INTERACTIVE vs AUTO
# ----------------------------------------------------------------------------
#   INTERACTIVE (default): migrate/update prompts are answered by the tester at
#     the console, exactly as an end user would. Phase 7 checks pass whichever way
#     the update offer is answered; newest-endpoint checks (Phase 7b) run ONLY in
#     auto mode -- an interactive .ps1 cannot capture console-inherited child
#     output to detect that an update ran (see DIVERGENCES).
#   AUTO (-Auto, or DAAF_TEST_AUTO=1, implied by -All): forces the child scripts
#     non-interactive by REDIRECTING their stdin from an empty file -- the .ps1
#     non-interactive seam ([Console]::IsInputRedirected => auto-select the first
#     valid choice: backup=y, strategy=1, rebuild=y). Because migrate_daaf.ps1
#     SKIPS its update offer when non-interactive, -Auto drives update_daaf.ps1
#     itself from the host dir after migration, enabling the Phase 7b
#     newest-endpoint checks + class E, and captures child output to a file so the
#     update-detection / rebuild-evidence greps can read it.
#
# ----------------------------------------------------------------------------
# EXPECTED RUNTIME
# ----------------------------------------------------------------------------
#   A single migration vector with a cold Docker cache is ~15-30 min (old-era
#   builds are authentic and slow). The full -All matrix (fresh + 3 migration
#   vectors), each building at least once, is ~45-90+ min. Budget accordingly;
#   nothing here is fast, by design (the point is a real end-to-end pathway).
#
# ----------------------------------------------------------------------------
# FIXTURE MANIFEST (classes A-E)
# ----------------------------------------------------------------------------
#   Every fixture below is planted BEFORE migration and verified AFTER. Classes
#   B/C/D/E are capability-probed or mode-gated: when the probe/precondition is
#   not met (an old era lacks the target section, or update did not run) the
#   corresponding check is a SKIP, never a FAIL.
#
#   Class A  Always-on. New-file markers + a research project, committed and
#            uncommitted. Upstream owns none of these paths, so update merges
#            can never conflict on them. (Phases 4/5, original coverage.)
#   Class B  Appends to EXISTING framework files (merge/stash coverage):
#            B(i)  COMMITTED   Dockerfile "USER ADDITIONS" block append.
#                              Probe: grep 'USER ADDITIONS' /daaf/Dockerfile.
#                              Marker: # test-migration-marker-B: dockerfile-user-block
#            B(ii) UNCOMMITTED CLAUDE.md append (dirty tracked -> stash/pop path).
#                              Probe: grep 'Primary execution language' CLAUDE.md.
#                              Marker: <!-- test-migration-marker-Bii -->
#   Class C  COMMITTED CLAUDE.md prose append (merge coverage on a tracked file).
#            Probe: grep '## Identity' /daaf/CLAUDE.md.
#            Marker: test-migration-marker-C
#            NOTE: on daaf_dev CLAUDE.md is heavily rewritten relative to the old
#            eras, so a committed append near it legitimately MAY hit a merge
#            conflict on update. The .ps1 records Class C's Phase-7 outcome as an
#            OBSERVE note (never pass/fail) to avoid a spurious FAIL on an expected
#            conflict -- a documented divergence from the .sh (see DIVERGENCES).
#   Class D  HOST-side environment_settings.txt byte-identity across migration
#            (and update). Content hash captured pre-migration, re-checked in
#            Phase 7. Applicable only when the era's install seeded the file.
#            Compared MODULO the active DAAF_BRANCH line: the driven update's
#            env-origin branch persist is a sanctioned single-line mutation.
#   Class E  Host-script DRIFT-HEAL (auto-mode only). A marker line is appended
#            to <host>\view_logs.ps1 before update; a healthy update re-syncs the
#            script (marker gone) and backs up the drifted copy as
#            view_logs.ps1.pre-update. Verified in Phase 7b.
#
#   NOTE on B/C appends to tracked framework files: these deliberately exercise
#   the updater's merge/stash paths that class-A new-file markers cannot. Appends
#   land at END-OF-FILE, which 3-way-merges cleanly UNLESS upstream also rewrote
#   the file's final lines. The COMMITTED CLAUDE.md append (Class C) is EXPECTED
#   to collide on the v2.x -> v3.0.0 vectors (v3.0.0 rewrites CLAUDE.md wholesale):
#   the first driven update aborts mid-merge on that conflict. That abort is no
#   longer a dead end -- the harness EXERCISES the full conflict -> resolve ->
#   resume journey. When the unmerged set is EXACTLY CLAUDE.md it simulates the
#   guided resolution a real user performs with Claude Code (take upstream's file,
#   re-preserve the user's prose), commits, and re-drives the now-resumable
#   updater, which must finish cleanly (stash pop, tier-B host-script sync,
#   rebuild). Only a CLAUDE.md-exactly conflict is auto-resolved this way; any
#   OTHER unmerged set -- notably a Dockerfile B(i) append conflict, or a
#   multi-file conflict -- is NOT eligible and the update FAILs loudly, which
#   remains the correct signal for an unexpected conflict. (Separately, the
#   post-migration Class B(i)/B(ii) Phase-7 checks still report CONFLICTED via
#   Add-Skip if git conflict markers remain in those files, and Class C's Phase-7
#   probe stays observe-only.)
#
# ----------------------------------------------------------------------------
# FLAGS / ENV REFERENCE
# ----------------------------------------------------------------------------
#   CLI parameters (param() block below; tm_parse_args mirrors them for Pester):
#     -All                  Run the whole matrix (implies -Auto). Aggregates child
#                           TEST_MIGRATION_SUMMARY lines into a scoreboard.
#     -Auto                 Non-interactive single vector (redirects child stdin;
#                           drives update itself).
#     -SkipMultiInstance    Skip Phase 8 (CLI equivalent of SKIP_MULTI_INSTANCE=1).
#   Environment variables:
#     DAAF_TEST_VERSION          Tag/branch to install, or "fresh" (default v2.0.1).
#     DAAF_TEST_ERA              Force era pathway 1|2|3 (default: auto by version).
#     DAAF_MIGRATION_BRANCH      Branch whose migrate/install/host scripts are tested.
#     DAAF_TEST_AUTO=1           Env equivalent of -Auto.
#     DAAF_TEST_MATRIX=1         Env equivalent of -All.
#     DAAF_TEST_MATRIX_VERSIONS  Override the matrix vector list (space-separated).
#     DAAF_TEST_MATRIX_FULL_MULTI=1  Let matrix children run Phase 8 (default: they
#                                skip it for speed; the fresh vector never runs it).
#     SKIP_MULTI_INSTANCE=1      Skip Phase 8.
#     DAAF_TEST_MODE=1           Source-only: define functions (incl. tm_*) and
#                                return before any execution (used by the Pester suite).
#
# ----------------------------------------------------------------------------
# MACHINE-READABLE SUMMARY
# ----------------------------------------------------------------------------
#   Every single-vector run emits exactly ONE line, as its final stdout line
#   (from Write-SummaryOnce, via Complete-Run or the script-scope trap), in this
#   grammar:
#     TEST_MIGRATION_SUMMARY vector=<v> status=<PASS|FAIL|INFRA> pass=<n> fail=<n> skip=<n>
#   status semantics (tm_classify_status): INFRA = migration/work never reached
#   (setup broke); FAIL = the work ran but >=1 check failed; PASS = the work ran
#   and every non-skipped check passed. The -All matrix parses this line per child
#   to build its scoreboard and its own nonzero exit on any non-PASS.
#
# ----------------------------------------------------------------------------
# .ps1 / .sh DIVERGENCES (kept in sync with test_migration.sh)
# ----------------------------------------------------------------------------
#   Four platform divergences, each forced by a real Windows/PowerShell constraint:
#   1. Non-interactive seam: the .sh rides CI=1 (IS_INTERACTIVE=false); the .ps1
#      child scripts read no CI var and instead detect [Console]::IsInputRedirected,
#      so auto mode REDIRECTS the child's stdin from an empty file (same net effect:
#      prompts auto-select the first valid choice).
#   2. Existing-install refusal: install.sh's refusal path exits nonzero;
#      install.ps1's ends in `Wait-ForUser; return`, so a refused re-install exits
#      0. The fresh track therefore asserts the refusal STRING in captured output
#      ONLY, never a nonzero exit code.
#   3. Interactive child-output capture: the .sh tees child output even
#      interactively (so it can detect an update from migrate's own offer); an
#      interactive .ps1 cannot capture console-inherited child output, so Phase 7b
#      (newest-endpoint) coverage requires -Auto. Interactive runs set
#      UpdateRan=false and observe-note this.
#   4. Host-script executable bit: the .sh asserts `-x` on downloaded host scripts;
#      Windows has no executable bit, so the .ps1 uses a Test-Path presence check
#      only. (The host-script SET also differs: daaf.sh/daaf_lib.sh vs
#      daaf.ps1/daaf_lib.ps1, commit 4fa8c43 -- reflected in the fresh track and
#      Check 9.)
#   The B(i)/B(ii) three-way outcome (PASS / CONFLICTED-skip / FAIL) and the
#   Class C observe-only treatment are now SHARED by both twins (the .sh backported
#   them), so fixture semantics are no longer a divergence.
#
# ============================================================================

[CmdletBinding()]
param(
    [switch]$All,
    [switch]$Auto,
    [switch]$SkipMultiInstance
)

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# Ensure TLS 1.2 for GitHub downloads (required on PowerShell 5.1)
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

# ============================================================================
# Pure helper functions (tm_*)  --  no docker, no network, unit-testable
# ============================================================================
# These carry no side effects beyond output and their return value, so the Pester
# suite (tests/powershell/test_migration.Tests.ps1) can dot-source this file under
# the DAAF_TEST_MODE guard below and exercise them directly. Kept underscore-named
# (tm_*) for 1:1 traceability with the .sh twin; the underscore also sidesteps the
# unapproved-verb warning a Verb-Noun name would trigger.

function tm_detect_era([string]$Version) {
    # Map a version string to its authentic install-era pathway.
    #   v1.0.0           -> 1 (clone)
    #   v2.0.0 / v2.0.1  -> 2 (ZIP)
    #   everything else  -> 3 (install.ps1 / branch)
    # A DAAF_TEST_ERA override belongs to the CALLER, not here.
    if ($Version -eq "v1.0.0") { return "1" }
    if ($Version -eq "v2.0.0" -or $Version -eq "v2.0.1") { return "2" }
    return "3"
}

function tm_version_ge_floor([string]$Version) {
    # Compare a vX.Y.Z tag against the Era-3 floor (v2.1.0), returning an int VALUE
    # (not $LASTEXITCODE): 0 if tag >= v2.1.0; 1 if tag < floor; 2 if not a vX.Y.Z
    # tag (a branch name -- the caller decides). [version] numeric parse keeps
    # "v2.10.0" >= floor where a lexical compare would wrongly reject it.
    if ($Version -match '^v(\d+)\.(\d+)\.(\d+)$') {
        $parsed = [version]::new([int]$Matches[1], [int]$Matches[2], [int]$Matches[3])
        if ($parsed -ge [version]::new(2, 1, 0)) { return 0 }
        return 1
    }
    return 2
}

function tm_matrix_vectors() {
    # The default matrix: the fresh-install track plus one vector per era.
    # DAAF_TEST_MATRIX_VERSIONS overrides (space-separated).
    if ($env:DAAF_TEST_MATRIX_VERSIONS) {
        return @($env:DAAF_TEST_MATRIX_VERSIONS -split '\s+' | Where-Object { $_ -ne '' })
    }
    return @('fresh', 'v1.0.0', 'v2.0.1', 'v2.1.0')
}

function tm_emit_summary($Vector, $Status, $Pass, $Fail, $Skip) {
    # Return the single machine-readable line the matrix driver (and any CI
    # wrapper) parses. Byte-identical grammar to the .sh twin; the caller writes it.
    return "TEST_MIGRATION_SUMMARY vector=$Vector status=$Status pass=$Pass fail=$Fail skip=$Skip"
}

function tm_parse_summary_field($Line, $Field) {
    # Split a summary line on whitespace and return the value after '<Field>='.
    if ($null -eq $Line) { return "" }
    foreach ($tok in ($Line -split '\s+')) {
        if ($tok -like "$Field=*") { return $tok.Substring($Field.Length + 1) }
    }
    return ""
}

function tm_classify_status([string]$Reached, [int]$FailCount) {
    #   INFRA  the meaningful work never ran (setup broke before migration/install)
    #   FAIL   the work ran but >=1 check failed
    #   PASS   the work ran and every non-skipped check passed
    if ($Reached -ne "true") { return "INFRA" }
    if ($FailCount -gt 0) { return "FAIL" }
    return "PASS"
}

function tm_matrix_verdict([string]$Status, [int]$Rc) {
    # tm_matrix_verdict <status> <rc> -> return 0 (vector passed) / 1 (vector failed).
    # Reconcile the parsed summary status against the child's ACTUAL exit code: a
    # vector passes only when the child reported PASS *and* exited zero. A nonzero
    # child rc fails the vector even when status=PASS (a summary line can report
    # PASS while a later teardown/exit path returns nonzero); any non-PASS status
    # (FAIL, INFRA, or an UNKNOWN(rc=N) placeholder) also fails. Mirrors the .sh
    # twin's tm_matrix_verdict; returns an int VALUE, not $LASTEXITCODE.
    if ($Status -eq "PASS" -and $Rc -eq 0) { return 0 }
    return 1
}

function tm_parse_args([string[]]$ArgList) {
    # Mirror the .sh tm_parse_args: fold argv into a decision object. --all/-All
    # implies --auto (a matrix cannot pause for prompts); unknown tokens ignored.
    # An explicit [string[]] signature (no $args) keeps it Pester-testable; the
    # main body binds the same flags via param() and does not call this.
    $runAll = $false; $autoMode = $false; $skipMulti = $false
    foreach ($a in $ArgList) {
        switch -Regex ($a) {
            '^(--all|-All)$'                               { $runAll = $true; $autoMode = $true }
            '^(--auto|-Auto)$'                             { $autoMode = $true }
            '^(--skip-multi-instance|-SkipMultiInstance)$' { $skipMulti = $true }
            default { }
        }
    }
    if ($runAll) { $autoMode = $true }
    return [pscustomobject]@{ RunAll = $runAll; AutoMode = $autoMode; SkipMultiCli = $skipMulti }
}

function Test-ConflictAutoResolvable([string]$MergeHead, [string]$Unmerged) {
    # Decide whether a nonzero-exit driven update is the EXPECTED, auto-resolvable
    # conflict the harness knows how to simulate a user resolving: a merge is in
    # progress (MergeHead non-empty) AND the unmerged set is EXACTLY the single
    # path CLAUDE.md -- the Class-C committed-append vs upstream-CLAUDE.md-rewrite
    # collision. Anything else (no merge in progress, an empty unmerged set, a
    # different single file such as Dockerfile, or a multi-file conflict) is NOT
    # auto-resolvable and must fail loudly. Inputs may carry trailing whitespace or
    # CR from the Invoke-ContainerGit capture; normalize before deciding. Pure (no
    # docker, no side effects); despite the Test- verb it lives here with the pure
    # tm_* helpers, above the DAAF_TEST_MODE guard, so the Pester suite can
    # dot-source it. Mirrors the .sh twin's tm_conflict_autoresolvable.
    $head = ($MergeHead -replace '\s', '')
    if ([string]::IsNullOrEmpty($head)) { return $false }
    $lines = @()
    foreach ($ln in (($Unmerged -replace "`r", '') -split "`n")) {
        $t = $ln.Trim()
        if ($t -ne '') { $lines += $t }
    }
    if ($lines.Count -eq 1 -and $lines[0] -eq 'CLAUDE.md') { return $true }
    return $false
}

# --- Source-only guard (D8) ---
# When dot-sourced with DAAF_TEST_MODE=1, return here: the Pester suite gets the
# tm_* functions above without running any of the harness body below. Placed AFTER
# all pure-function definitions and BEFORE Set-StrictMode / execution, mirroring the
# guard in migrate_daaf.ps1. StrictMode is dynamically scoped, so keeping it below
# the guard prevents it leaking into Pester's dot-sourced session.
if ($env:DAAF_TEST_MODE -eq "1") { return }

Set-StrictMode -Version 3.0
# MARGIN GUARD: do not insert fallible statements between here and the
# summary-contract block below. The scope-wide trap calls Write-SummaryOnce,
# so a terminating error thrown before that function (and its $script: state)
# is defined resurrects the field-run-4 CommandNotFoundException crash. The
# statements in between must remain null-safe casts and $env: reads only.

# --- Argument / mode resolution ---
# param() above binds -All/-Auto/-SkipMultiInstance; fold in the env entry points
# (the matrix driver re-invokes children with DAAF_TEST_AUTO=1, and CI wrappers may
# prefer env toggles). -All (and DAAF_TEST_MATRIX=1) force auto mode -- a matrix
# cannot pause for prompts. SKIP_MULTI_INSTANCE=1 folds onto the -SkipMultiInstance
# switch so the existing Phase-8 gate honors one flag.
$script:RunAll = [bool]$All
$script:AutoMode = [bool]$Auto
if ($env:DAAF_TEST_MATRIX -eq "1") { $script:RunAll = $true }
if ($env:DAAF_TEST_AUTO -eq "1") { $script:AutoMode = $true }
if ($env:SKIP_MULTI_INSTANCE -eq "1") { $SkipMultiInstance = $true }
if ($script:RunAll) { $script:AutoMode = $true }

# --- Summary contract (state + emitter + trap) ---
# Defined HERE -- above the matrix driver -- and not lower down, because
# PowerShell `trap` statements are SCOPE-WIDE: the trap below is armed for the
# WHOLE script scope (including the matrix-driver branch, which exits before
# ever reaching later lines), while `function` definitions only exist once
# execution passes them. Field run 4 (2026-07-17): with this block below the
# driver, a child's stderr line ("Cloning into...") wrapped by 2>&1 under
# EAP=Stop fired the trap inside the driver loop, and the trap died with
# CommandNotFoundException on the not-yet-defined Write-SummaryOnce, killing
# the whole matrix. Repro: scripts/scratch/probe_trap_scope.ps1.

# Default install-from version: v2.0.1 -- the richest migration path (ZIP era:
# no remote, synthetic root commit, graft + permission-fix machinery all get
# exercised). Override with DAAF_TEST_VERSION for the other pathways.
$TestVersion = if ($env:DAAF_TEST_VERSION) { $env:DAAF_TEST_VERSION } else { "v2.0.1" }

# Track test results + machine-readable summary state. Initialized up front so the
# summary emitter (Write-SummaryOnce) and the script-scope trap never dereference an
# unset $script: var under Set-StrictMode 3.0, even on an early-exit path.
$script:TestsPassed = 0
$script:TestsFailed = 0
$script:TestsSkipped = 0
$script:Failures = @()
$script:Skips = @()
$script:VectorName = $TestVersion       # the vector this process reports as
$script:MigrationReached = $false       # flipped true once the meaningful work begins
$script:SummaryEmitted = $false         # guards single emission of the summary line
# Fixture / update state read across phases. Initialized up front so StrictMode 3.0
# never dereferences an unset $script: var on an early-exit or skipped-plant path.
$script:PlantedB1 = $false              # Class B(i) committed Dockerfile append planted?
$script:PlantedC = $false               # Class C committed CLAUDE.md append planted?
$script:PlantedB2 = $false              # Class B(ii) uncommitted CLAUDE.md append planted?
$script:UpdateRan = $false              # did a driven update_daaf.ps1 run (auto mode)?
$script:ClassEPlanted = $false          # Class E host-script drift marker planted?
$script:UpdateOut = ""                  # capture file for the driven update (auto mode)
$script:HarnessAddedSafeDir = $false    # did the harness add the /daaf safe.directory exemption (Phase 3)?

function Write-SummaryOnce {
    # Emit the machine-readable summary exactly ONCE, as the final stdout line, so
    # the matrix driver (and any CI wrapper) can parse this vector's outcome no
    # matter where execution stopped. In interactive mode (not auto/matrix, not
    # nested, real console) pause first so the tester can review output -- the
    # matrix parse is pattern-anchored, so any trailing error text is inert.
    #
    # The matrix DRIVER never emits a vector summary line (the grammar is one
    # line per CHILD vector; the driver reports via scoreboard + exit code).
    # This guard is also what makes the scope-wide trap safe in the driver
    # branch: on a driver-side terminating error the trap calls this function,
    # which returns immediately, and `break` surfaces the real error.
    if ($script:RunAll) { return }
    if ($script:SummaryEmitted) { return }
    $script:SummaryEmitted = $true
    $interactive = $false
    try { $interactive = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) } catch { $interactive = $false }
    if (-not $script:AutoMode -and -not $env:DAAF_NESTED -and $interactive) {
        Write-Host ""
        $null = Read-Host "Press Enter to continue"
    }
    $reached = if ($script:MigrationReached) { "true" } else { "false" }
    $status = tm_classify_status $reached $script:TestsFailed
    Write-Host (tm_emit_summary $script:VectorName $status $script:TestsPassed $script:TestsFailed $script:TestsSkipped)
}

function Complete-Run([int]$Code) {
    # Single-vector exit path: emit the summary, then exit with the given code.
    # (The matrix-driver branch below exits with plain `exit` and emits no summary.)
    Write-SummaryOnce
    exit $Code
}

# Script-scope safety net: any terminating error (a Write-Error under EAP=Stop, or
# a StrictMode violation) still emits the summary before the script dies, so an
# aborted vector stays INFRA/FAIL-classifiable rather than a silent, unparseable
# gap. Verified: the trap body runs to completion before `break` propagates.
# NOTE: this trap is armed for the ENTIRE script scope regardless of its line
# position (PowerShell trap semantics) -- which is exactly why it and everything
# it calls are defined above the matrix-driver branch.
trap { Write-SummaryOnce; break }

function Invoke-NativeLogged([scriptblock]$Command) {
    # Run a native command with its stderr merged and stringified under a
    # scoped EAP=Continue. Under PS 5.1 with a redirected error stream, a
    # native command's routine stderr output (git clone progress, docker build
    # chatter) becomes ErrorRecords; under EAP=Stop the first record is a
    # TERMINATING error (field run 4). Continue + ForEach-Object "$_" renders
    # them as plain text lines (parity with the .sh harness's `tee` output).
    # Returns the native exit code. Simple positional parameter on purpose
    # (PS 5.1-safe helper rules per the header constraints).
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Command 2>&1 | ForEach-Object { Write-Host "$_" }
    $rc = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    return $rc
}

# --- Matrix driver (-All / DAAF_TEST_MATRIX=1) ---
# Runs the whole vector list as CHILD processes of this same script (one clean
# process per vector -- no cross-vector state), tees each child's combined output
# to a per-vector log, parses the child's final TEST_MIGRATION_SUMMARY line, and
# builds a scoreboard. Exits nonzero if any child was not PASS. This branch EXITs
# before the single-vector setup below, so no single-vector summary is emitted for
# the driver itself (it uses plain `exit`, never Complete-Run).
if ($script:RunAll) {
    $hostExe = (Get-Process -Id $PID).Path
    $selfPath = $PSCommandPath
    $matrixStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $matrixDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-matrix-$matrixStamp") -Force

    Write-Host ""
    Write-Host "==========================================" -ForegroundColor White
    Write-Host "  DAAF Migration Test -- MATRIX (-All)" -ForegroundColor White
    Write-Host "==========================================" -ForegroundColor White
    Write-Host ""
    Write-Host "  Vectors:  $((tm_matrix_vectors) -join ' ')"
    Write-Host "  Logs:     $($matrixDir.FullName)"
    Write-Host ""

    # Children skip Phase 8 by default (each build+teardown is expensive); opt in
    # with DAAF_TEST_MATRIX_FULL_MULTI=1. The fresh vector never runs Phase 8.
    $childSkip = if ($env:DAAF_TEST_MATRIX_FULL_MULTI -eq "1") { "0" } else { "1" }

    # Save + clear DAAF_TEST_MATRIX for the child environment: on the env entry path
    # (DAAF_TEST_MATRIX=1) the exported value would otherwise be inherited and turn
    # every child into another matrix driver (infinite recursion). The .sh twin
    # carries the identical guard on its env-entry path (`env DAAF_TEST_MATRIX= ...`).
    $savedMatrix = $env:DAAF_TEST_MATRIX
    $savedTestVersion = $env:DAAF_TEST_VERSION
    $savedTestAuto = $env:DAAF_TEST_AUTO
    $savedSkipMulti = $env:SKIP_MULTI_INSTANCE

    $matrixFail = 0
    $scoreboard = @()
    try {
        foreach ($vec in (tm_matrix_vectors)) {
            $thisSkip = if ($vec -eq 'fresh') { "1" } else { $childSkip }
            $logf = Join-Path $matrixDir.FullName "$vec.log"
            Write-Host "--- vector: $vec ---" -ForegroundColor White
            Remove-Item Env:\DAAF_TEST_MATRIX -ErrorAction SilentlyContinue
            $env:DAAF_TEST_VERSION = $vec
            $env:DAAF_TEST_AUTO = "1"
            $env:SKIP_MULTI_INSTANCE = $thisSkip
            # Scoped EAP=Continue + stringification: under PS 5.1, `2>&1` wraps
            # the child's stderr lines as ErrorRecords, and with EAP=Stop the
            # FIRST such line (e.g. git clone's "Cloning into...") becomes a
            # TERMINATING error in this loop (field run 4 killed the matrix
            # here). Continue lets them flow; ForEach-Object "$_" stringifies
            # records so the log gets clean text (parity with the .sh `tee`).
            $savedEAP = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            & $hostExe -NoProfile -ExecutionPolicy Bypass -File $selfPath 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $logf
            $childRc = $LASTEXITCODE
            $ErrorActionPreference = $savedEAP
            $summaryLine = (Select-String -Path $logf -Pattern '^TEST_MIGRATION_SUMMARY ' | Select-Object -Last 1).Line
            $vstatus = tm_parse_summary_field $summaryLine 'status'
            $vpass = tm_parse_summary_field $summaryLine 'pass'
            $vfail = tm_parse_summary_field $summaryLine 'fail'
            $vskip = tm_parse_summary_field $summaryLine 'skip'
            # Reconcile the parsed status with the child's actual exit code (see
            # tm_matrix_verdict): a missing summary line falls back to
            # UNKNOWN(rc=N); a PASS status riding a nonzero child rc is annotated
            # PASS(rc=N)! on the scoreboard and counted as a failure by the verdict.
            if ([string]::IsNullOrEmpty($vstatus)) {
                $vstatus = "UNKNOWN(rc=$childRc)"
                $vlabel = $vstatus
            } elseif ($vstatus -eq "PASS" -and $childRc -ne 0) {
                $vlabel = "PASS(rc=$childRc)!"
            } else {
                $vlabel = $vstatus
            }
            $pShow = if ($vpass) { $vpass } else { '?' }
            $fShow = if ($vfail) { $vfail } else { '?' }
            $sShow = if ($vskip) { $vskip } else { '?' }
            $scoreboard += "  ${vec}: $vlabel (pass=$pShow fail=$fShow skip=$sShow)"
            if ((tm_matrix_verdict $vstatus $childRc) -ne 0) { $matrixFail = 1 }
            Write-Host ""
        }
    } finally {
        # Restore the caller's env (clear only when it was genuinely unset).
        if ($null -ne $savedMatrix) { $env:DAAF_TEST_MATRIX = $savedMatrix } else { Remove-Item Env:\DAAF_TEST_MATRIX -ErrorAction SilentlyContinue }
        if ($null -ne $savedTestVersion) { $env:DAAF_TEST_VERSION = $savedTestVersion } else { Remove-Item Env:\DAAF_TEST_VERSION -ErrorAction SilentlyContinue }
        if ($null -ne $savedTestAuto) { $env:DAAF_TEST_AUTO = $savedTestAuto } else { Remove-Item Env:\DAAF_TEST_AUTO -ErrorAction SilentlyContinue }
        if ($null -ne $savedSkipMulti) { $env:SKIP_MULTI_INSTANCE = $savedSkipMulti } else { Remove-Item Env:\SKIP_MULTI_INSTANCE -ErrorAction SilentlyContinue }
    }

    Write-Host "==========================================" -ForegroundColor White
    Write-Host "  Matrix Scoreboard" -ForegroundColor White
    Write-Host "==========================================" -ForegroundColor White
    foreach ($row in $scoreboard) { Write-Host $row }
    Write-Host ""
    Write-Host "  Per-vector logs: $($matrixDir.FullName)"
    Write-Host ""
    if ($matrixFail -ne 0) {
        Write-Host "ERROR: One or more matrix vectors did not PASS." -ForegroundColor Red
        exit 1
    }
    Write-Host "SUCCESS: All matrix vectors passed." -ForegroundColor Green
    exit 0
}

# --- Configuration ---
# ($TestVersion is derived in the summary-contract block ABOVE the matrix
# driver, because $script:VectorName needs it there. Remaining config follows.)
# Default migration branch: the branch whose migrate_daaf.ps1 + host scripts are
# under test. Keep this pointing at the CURRENT update-testing branch (today:
# daaf_dev). Overridable per-run via DAAF_MIGRATION_BRANCH without editing here.
$MigrationBranch = if ($env:DAAF_MIGRATION_BRANCH) { $env:DAAF_MIGRATION_BRANCH } else { "daaf_dev" }
$Repo = "DAAF-Contribution-Community/daaf"
# (The -SkipMultiInstance switch and the SKIP_MULTI_INSTANCE=1 env toggle are
# folded together in the mode-resolution block above, so downstream logic checks
# one flag.)

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

# (Summary state, Write-SummaryOnce, Complete-Run, and the script-scope trap
# are defined ABOVE the matrix driver: PowerShell traps are scope-wide, so the
# trap's machinery must already exist when a terminating error fires anywhere
# in this scope -- including inside the driver branch, which exits before
# reaching this point. See the summary-contract block after mode resolution.)

function Add-Skip {
    # Record an intentional skip: a check that does not apply to this vector/mode,
    # or whose fixture could not be planted. A skip is NOT a failure and does not
    # affect PASS/FAIL classification.
    param([Parameter(Mandatory)][string]$Description)
    $script:TestsSkipped++
    $script:Skips += "  SKIP: $Description"
    Write-Host "  SKIP: $Description" -ForegroundColor Yellow
}

function Write-ObserveNote {
    # Informational line (neither pass/fail/skip) -- context for the reader.
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "  NOTE: $Message" -ForegroundColor Cyan
}

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

# Auto-mode sibling of Invoke-HardenedScript: spawn a HARNESS-OWNED .ps1 with its
# STDIN redirected from an EMPTY file, which is THE non-interactive seam for the
# .ps1 child scripts. migrate_daaf.ps1/install.ps1/update_daaf.ps1 detect
# non-interactive mode via [Console]::IsInputRedirected (NOT a CI env var like the
# .sh twin), so a redirected empty stdin makes Read-UserChoice auto-select the
# first valid choice AND makes any stray Read-Host read EOF and return at once
# (immune to the DAAF_NESTED-clobber stray-pause wart). Combined stdout+stderr are
# captured to $CaptureFile (echoed to the host and returned to the caller) so the
# update-detection / rebuild-evidence greps can read the child's output -- the one
# capability interactive mode cannot provide (console-inherited child output is not
# captured). Start-Process cannot redirect stdout and stderr to the SAME file
# (throws), so they use separate files and are merged after.
function Invoke-HardenedScriptAuto {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Path,
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$CaptureFile,
        [string[]]$ScriptArgs = @()
    )
    try { Unblock-File -LiteralPath $Path -ErrorAction Stop } catch { Write-Verbose "Unblock-File no-op: $_" }

    # Working files live next to $CaptureFile (inside the harness test dir), never
    # in the ambient CWD. An empty stdin file = immediate EOF for the child.
    $stdinFile = "$CaptureFile.stdin"
    $errFile = "$CaptureFile.err"
    $null = New-Item -ItemType File -Path $stdinFile -Force

    $hostExe = (Get-Process -Id $PID).Path
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Path)
    foreach ($a in $ScriptArgs) {
        if ($a -match '\s') { $argList += ('"' + ($a -replace '"', '\"') + '"') }
        else { $argList += $a }
    }
    $proc = Start-Process -FilePath $hostExe -ArgumentList $argList -NoNewWindow -PassThru `
        -RedirectStandardInput $stdinFile -RedirectStandardOutput $CaptureFile -RedirectStandardError $errFile
    # Touch $proc.Handle BEFORE waiting (same PS 5.1 gotcha as Invoke-HardenedScript:
    # without a cached handle $proc.ExitCode is $null after WaitForExit()).
    $null = $proc.Handle
    $proc.WaitForExit()

    # Merge stderr into the capture file, then echo the whole capture to the host so
    # the run stays followable and the caller can grep a single $CaptureFile.
    if (Test-Path $errFile) {
        Get-Content -LiteralPath $errFile | Add-Content -LiteralPath $CaptureFile
        Remove-Item -LiteralPath $errFile -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $stdinFile -ErrorAction SilentlyContinue
    if (Test-Path $CaptureFile) { Get-Content -LiteralPath $CaptureFile | ForEach-Object { Write-Host $_ } }

    if ($null -eq $proc.ExitCode) {
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
Write-Host "  Mode:      $(if ($script:AutoMode) { 'auto (non-interactive)' } else { 'interactive' })"
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
# FRESH-INSTALL TRACK (DAAF_TEST_VERSION=fresh) -- no migration
# =====================================================================
# Exercises the LOCAL install.ps1 end to end from the clean slate above, then
# asserts the install landed and that a second install is refused. Exits after its
# own compact results block (the migration phases below do not apply). Divergences
# from the .sh twin are documented inline: the non-interactive seam (redirect-stdin,
# not CI=1), the refusal exit code (refused re-install exits 0, so assert the string
# only), the host-script set (.ps1 variants), and no executable-bit check on Windows.
if ($TestVersion -eq "fresh") {
    Write-Host "[2/2] Fresh-install track (local install.ps1)" -ForegroundColor White
    Write-Host ""

    # D7 guard: install.ps1 must exist in the local repo (mirror of the .sh -f test).
    if (-not (Test-Path $LocalInstallPath)) {
        Write-Error "Cannot find install.ps1 in the local repo -- fresh-install track needs it. Expected at: $LocalInstallPath"
        Complete-Run 1
    }

    $FreshDir = Join-Path $TestDir "fresh"
    $null = New-Item -ItemType Directory -Path $FreshDir -Force
    Set-Location $FreshDir

    # 'Reached the meaningful work' -- classify PASS/FAIL, not INFRA. (There is no
    # migration in this track; MigrationReached doubles as a work-started flag.)
    $script:MigrationReached = $true

    # Copy install.ps1 into the harness-owned fresh dir and run the COPY, so
    # Unblock-File only ever strips MOTW from a harness-written file, never the
    # user's repo original. install.ps1 derives its install dir from the CWD
    # (.\daaf-docker), so running the copy from $FreshDir is location-correct.
    $FreshInstallCopy = Join-Path $FreshDir "install.ps1"
    Copy-Item $LocalInstallPath $FreshInstallCopy -Force

    Write-Host "INFO: Running local install.ps1 (branch $MigrationBranch)..." -ForegroundColor Cyan
    Write-Host ""
    $env:DAAF_BRANCH = $MigrationBranch
    $env:DAAF_NESTED = "1"
    $FreshInstallExit = 1
    try {
        if ($script:AutoMode) {
            $FreshInstallExit = Invoke-HardenedScriptAuto -Path $FreshInstallCopy -CaptureFile (Join-Path $FreshDir "install.out")
        } else {
            $FreshInstallExit = Invoke-HardenedScript -Path $FreshInstallCopy
        }
    } catch {
        Write-Host "ERROR: Could not run install.ps1: $_" -ForegroundColor Red
        $FreshInstallExit = 1
    }
    Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
    Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
    Write-Host ""

    if ($FreshInstallExit -eq 0) {
        Test-Check "Fresh install completed (exit 0)" $true
    } else {
        Write-Host "FAIL: Fresh install.ps1 did NOT complete successfully (exit $FreshInstallExit)." -ForegroundColor Red
        Test-Check "Fresh install completed (exit $FreshInstallExit)" $false
    }

    # Discover the freshly-created container and wait for exec readiness.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $script:ContainerName = (docker ps -a --filter "volume=$VolumeName" --format '{{.Names}}' | Select-Object -First 1 | Out-String).Trim() -replace "`r",""
    $ErrorActionPreference = $savedEAP
    if (-not [string]::IsNullOrWhiteSpace($script:ContainerName)) {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $FreshState = (docker inspect --format '{{.State.Status}}' $script:ContainerName 2>$null | Out-String).Trim() -replace "`r",""
        $ErrorActionPreference = $savedEAP
        if ($FreshState -ne "running") {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            docker start $script:ContainerName 2>&1 | Out-Null
            $ErrorActionPreference = $savedEAP
        }
        $retries = 0
        while ($retries -lt 30) {
            Invoke-ContainerExec true 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { break }
            $retries++
            Start-Sleep -Seconds 2
        }
    }

    $freshExecReady = $false
    if (-not [string]::IsNullOrWhiteSpace($script:ContainerName)) {
        Invoke-ContainerExec true 2>&1 | Out-Null
        $freshExecReady = ($LASTEXITCODE -eq 0)
    }
    Test-Check "Fresh container is exec-ready ($($script:ContainerName))" $freshExecReady

    # Branch check: install.ps1 clones the branch and leaves it checked out.
    $FreshBranch = Invoke-ContainerGit branch --show-current
    if ($FreshBranch -eq $MigrationBranch) {
        Test-Check "Fresh install checked out branch $MigrationBranch" $true
    } else {
        Test-Check "Fresh install checked out branch $MigrationBranch (got: '$FreshBranch')" $false
    }

    # Host scripts present in the fresh daaf-docker dir. DIVERGENCE from the .sh
    # twin: Windows has no executable bit, so this is a Test-Path presence check
    # ONLY (the .sh additionally asserts -x). The list is the .ps1 host-script set
    # (daaf.sh/daaf_lib.sh are never shipped to Windows -- commit 4fa8c43).
    $FreshHostDir = Join-Path $FreshDir "daaf-docker"
    foreach ($Script in @("daaf.ps1", "daaf_lib.ps1", "backup_daaf.ps1", "restore_from_backup.ps1", "rebuild_daaf.ps1", "update_daaf.ps1", "run_daaf.ps1", "view_logs.ps1", "view_notebooks.ps1", "view_quarto.ps1", "run_vscode.ps1")) {
        Test-Check "Fresh host script present: $Script" (Test-Path (Join-Path $FreshHostDir $Script))
    }

    # environment_settings.txt seeded by install.ps1.
    Test-Check "Fresh install seeded environment_settings.txt" (Test-Path (Join-Path $FreshHostDir "environment_settings.txt"))

    # Functional smoke: git describe sane + hooks present.
    $FreshGitDesc = Invoke-ContainerGit describe --tags --always
    Test-Check "Fresh install git describe returns a sane ref ($FreshGitDesc)" (-not [string]::IsNullOrWhiteSpace($FreshGitDesc))
    Invoke-ContainerExec test -d /daaf/.claude/hooks
    Test-Check "Fresh install framework hooks present (.claude/hooks)" ($LASTEXITCODE -eq 0)

    # Second install must be REFUSED by the existing-install guard. DIVERGENCE from
    # the .sh twin: install.ps1's refusal path ends in `Wait-ForUser; return`, so a
    # refused re-install exits 0 (NOT nonzero). Assert the refusal STRING in the
    # captured output ONLY -- do NOT gate on a nonzero exit code. Always capture via
    # the auto path so the string is greppable even in an interactive fresh run.
    Write-Host "INFO: Verifying a second install is refused by the existing-install guard..." -ForegroundColor Cyan
    $SecondInstallOut = Join-Path $FreshDir "second_install.out"
    $env:DAAF_BRANCH = $MigrationBranch
    $env:DAAF_NESTED = "1"
    try {
        $null = Invoke-HardenedScriptAuto -Path $FreshInstallCopy -CaptureFile $SecondInstallOut
    } catch {
        Write-Host "WARNING: Second install run threw: $_" -ForegroundColor Yellow
    }
    Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
    Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
    $secondRefused = $false
    if (Test-Path $SecondInstallOut) {
        $secondRefused = [bool](Select-String -Path $SecondInstallOut -Pattern 'existing DAAF installation was detected' -Quiet)
    }
    Test-Check "Second fresh install refused (existing-install guard string present)" $secondRefused

    # --- Fresh-track results ---
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor White
    Write-Host "  Fresh-Install Track Results" -ForegroundColor White
    Write-Host "==========================================" -ForegroundColor White
    Write-Host ""
    Write-Host "  Passed:   $($script:TestsPassed)" -ForegroundColor Green
    Write-Host "  Failed:   $($script:TestsFailed)"
    Write-Host "  Skipped:  $($script:TestsSkipped)"
    Write-Host ""
    if ($script:TestsFailed -gt 0) {
        Write-Host "  Failures:" -ForegroundColor Red
        foreach ($f in $script:Failures) { Write-Host $f -ForegroundColor Red }
        Write-Host ""
        Write-Host "ERROR: Fresh-install track: some checks failed." -ForegroundColor Red
        Complete-Run 1
    }
    Write-Host "SUCCESS: Fresh-install track: all checks passed!" -ForegroundColor Green
    Complete-Run 0
}

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
    # Invoke-NativeLogged on every bare native call in the era-install blocks:
    # git clone/checkout and docker builds ALWAYS write progress to stderr,
    # which is lethal under EAP=Stop with a redirected error stream (matrix
    # children) -- see the helper's comment.
    $rc = Invoke-NativeLogged { git clone "https://github.com/$Repo.git" $CloneDir }
    if ($rc -ne 0) {
        Write-Error "git clone failed - cannot replay the Era 1 install."
        exit 1
    }

    # Time-machine deviation (see header): rewind main to the tag, because a
    # 2026-era user's clone HAD main at v1.0.0. checkout -B moves the branch
    # pointer and working tree while keeping origin + tracking config intact.
    $rc = Invoke-NativeLogged { git -C $CloneDir checkout -B main $TestVersion }
    if ($rc -ne 0) {
        Write-Error "git checkout -B main $TestVersion failed - cannot pin the Era 1 tree."
        exit 1
    }

    Set-Location $CloneDir
    Write-Host "INFO: Copying the clone into the Docker volume (documented busybox step)..." -ForegroundColor Cyan
    $rc = Invoke-NativeLogged { docker run --rm -v "${PWD}:/source:ro" -v "${VolumeName}:/dest" busybox cp -a /source/. /dest/ }
    if ($rc -ne 0) {
        Write-Error "busybox copy into volume $VolumeName failed."
        exit 1
    }

    # v1.0.0's compose file has no `name:` key, so the compose project name
    # comes from THIS directory's name ("daaf") -- reproducing the era's
    # container/volume names (daaf-daaf-docker-1 / daaf_daaf-data).
    Write-Host "INFO: Building and starting the v1.0.0 container (docker compose up -d --build)..." -ForegroundColor Cyan
    Write-Host "INFO: This builds the OLD Dockerfile - authentic and slow on a cold cache..." -ForegroundColor Cyan
    $rc = Invoke-NativeLogged { docker compose up -d --build }
    if ($rc -ne 0) {
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
    $rc = Invoke-NativeLogged { docker run --rm -v "${PWD}:/source:ro" -v "${VolumeName}:/dest" busybox sh -c 'cp -a /source/. /dest/' }
    if ($rc -ne 0) {
        Write-Error "busybox copy into volume $VolumeName failed."
        exit 1
    }

    # v2.0.x compose hardcodes `name: daaf`, so project naming is stable
    # regardless of this directory's name (daaf-2.0.1 etc.).
    Write-Host "INFO: Building and starting the $TestVersion container (docker compose up -d --build)..." -ForegroundColor Cyan
    Write-Host "INFO: This builds the OLD Dockerfile - authentic and slow on a cold cache..." -ForegroundColor Cyan
    $rc = Invoke-NativeLogged { docker compose up -d --build }
    if ($rc -ne 0) {
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

# --- Harness git safe.directory exemption window (OPEN) ---
# The harness performs its OWN git operations in the OLD-era container before
# migrate runs: the Phase 3 era-state verify probes below, the Phase 4 committed-
# fixture plant, and the Phase 5 dirty/uncommitted plant. On a root-owned Era-1
# (v1.0.0) payload every one of those hits modern git's dubious-ownership fatal
# ("detected dubious ownership in repository at '/daaf'"), so the vector INFRAs
# at Phase 3 before migrate ever runs. Add a global safe.directory exemption for
# the exec user NOW, spanning all pre-migrate old-container git usage. It is
# CLOSED (removed) immediately before migrate is invoked (Phase 6), but ONLY if
# the harness added it here -- so the field run still exercises migrate's own
# section-4b safe.directory fix end-to-end on the v1.0.0 vector rather than the
# harness masking it. Harmless on the v2.x vectors: their payload is already
# exec-user-owned, so the add is a redundant no-op exemption that cannot change
# any currently-passing check. Guarded (capture-then-test on --get-all) so a
# re-run never duplicates the entry; mirrors migrate_daaf.ps1 section 4b.
$SafeDirPre = @(Invoke-ContainerExec git config --global --get-all safe.directory) -join "`n"
if (($SafeDirPre -split "`n") -contains '/daaf') {
    Write-ObserveNote "Git safe.directory exemption window: /daaf was already a safe.directory before the harness ran, so the harness neither adds nor later removes it."
} else {
    Invoke-ContainerExec git config --global --add safe.directory /daaf
    if ($LASTEXITCODE -eq 0) {
        $script:HarnessAddedSafeDir = $true
        Write-ObserveNote "Git safe.directory exemption window OPENED (harness added /daaf) for the pre-migration old-container git ops in phases 3-5; it is removed before migrate runs so migrate's own section-4b safe.directory fix is still exercised end-to-end on the v1.0.0 vector."
    } else {
        Write-Error "Could not configure the git safe.directory exemption for /daaf in the old container. Every pre-migration git probe would fail silently (dubious-ownership refusal), so the vector cannot proceed."
        exit 1
    }
}
Write-Host ""

if ($TestEra -eq "1") {
    # Era 1 expectation: /daaf carries the clone's full .git -- origin remote
    # pointing at the official repo, branch main checked out.
    $OriginCheck = Invoke-ContainerGit remote get-url origin
    $BranchCheck = Invoke-ContainerGit branch --show-current
    if ($OriginCheck -match $Repo -and $BranchCheck -eq "main") {
        Write-Host "SUCCESS: Era 1 state verified (origin remote + branch main from the clone)." -ForegroundColor Green
    } else {
        # Surface the RAW git error + /daaf ownership BEFORE the terminating
        # Write-Error (Invoke-ContainerGit discards stderr, which hid the
        # diagnosis in field run 4 -- modern-git "dubious ownership" refusal:
        # root-owned volume payload vs the v1.0.0 image's non-root user, with
        # no safe.directory config in that era).
        # PS 5.1 native-stderr capture (round-5 field-confirmed, Windows): under a
        # redirected error stream `docker exec ... 2>&1` renders git's stderr lines
        # as ErrorRecords, and with EAP=SilentlyContinue + Out-String those records
        # were DROPPED -- so $gitDiag came back EMPTY on Windows where the .sh twin
        # printed git's dubious-ownership fatal. Capture them the way
        # Invoke-NativeLogged surfaces native stderr: scoped EAP=Continue + 2>&1 +
        # per-object stringify (ForEach-Object "$_"), joined into one string. The
        # .sh side already surfaces this text (raw docker exec 2>&1) and is left
        # unchanged; parity here means both twins surface git's stderr, not
        # identical mechanics.
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
        $gitDiag = ((docker exec $script:ContainerName git -C /daaf remote get-url origin 2>&1 | ForEach-Object { "$_" }) -join "`n").Trim()
        $ownerDiag = ((docker exec $script:ContainerName ls -ldn /daaf /daaf/.git 2>&1 | ForEach-Object { "$_" }) -join "`n").Trim()
        $ErrorActionPreference = $savedEAP
        Write-Host "INFO: Raw git probe output: $gitDiag" -ForegroundColor Yellow
        Write-Host "INFO: Ownership probe (ls -ldn): $ownerDiag" -ForegroundColor Yellow
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
        # Complete the time-machine state. A real era user's install ran
        # `git clone --depth 1 -b main`, which ALSO left: a main-only fetch
        # refspec, an origin/main remote-tracking ref, and main tracking
        # origin/main. The tag-pinned replay clone has none of those (its
        # refspec is pinned to the tag), so migrate's best-effort
        # `--set-upstream-to=origin/main` failed on a git state no real user
        # had (field run 4: tracking '' on the v2.1.0 vector). set-branches
        # rewrites the refspec to main-only; the shallow fetch materializes
        # origin/main at the CURRENT tip; set-upstream then matches the
        # tracking a real `clone -b main` had from day one. Invoke-NativeLogged
        # (not Invoke-ContainerGit) so a failure's stderr reaches the log.
        $rc = Invoke-NativeLogged { docker exec $script:ContainerName git -C /daaf remote set-branches origin main }
        if ($rc -ne 0) {
            Write-Error "Era 3 normalization failed - could not set the origin fetch refspec to main."
            exit 1
        }
        $rc = Invoke-NativeLogged { docker exec $script:ContainerName git -C /daaf fetch --depth 1 origin main }
        if ($rc -ne 0) {
            Write-Error "Era 3 normalization failed - could not fetch origin/main (network?)."
            exit 1
        }
        $rc = Invoke-NativeLogged { docker exec $script:ContainerName git -C /daaf branch --set-upstream-to=origin/main main }
        if ($rc -ne 0) {
            Write-Error "Era 3 normalization failed - could not set main's upstream to origin/main."
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

# --- Class B(i) + Class C: COMMITTED appends to EXISTING framework files ---
# These exercise the updater's 3-way MERGE path on tracked files (class-A markers
# only ever test new-file preservation). Each is capability-probed: an old era that
# lacks the target section is recorded as a skip-at-plant (observe note), not
# planted, so a legitimately-absent target never becomes a spurious FAIL. The
# appends land at EOF, which merges cleanly unless upstream also rewrote the file's
# final lines. FIXTURE RULE (PS 5.1): the bash -c payload is a PowerShell
# single-quoted string with NO embedded double quotes; inner single quotes are
# doubled ('') so bash receives a single-quoted printf whose \n are its own.
Invoke-ContainerExec grep -q 'USER ADDITIONS' /daaf/Dockerfile
if ($LASTEXITCODE -eq 0) {
    Invoke-ContainerExec bash -c 'printf ''\n# test-migration-marker-B: dockerfile-user-block\n'' >> /daaf/Dockerfile'
    $script:PlantedB1 = $true
    Write-ObserveNote "Class B(i) planted: committed Dockerfile user-block append."
} else {
    Write-ObserveNote "Class B(i) not planted: Dockerfile has no USER ADDITIONS block at $TestVersion."
}
Invoke-ContainerExec grep -q '## Identity' /daaf/CLAUDE.md
if ($LASTEXITCODE -eq 0) {
    Invoke-ContainerExec bash -c 'printf ''\n<!-- test-migration-marker-C: committed CLAUDE.md prose line -->\n'' >> /daaf/CLAUDE.md'
    $script:PlantedC = $true
    Write-ObserveNote "Class C planted: committed CLAUDE.md prose append."
} else {
    Write-ObserveNote "Class C not planted: CLAUDE.md has no '## Identity' section at $TestVersion."
}
if ($script:PlantedB1 -or $script:PlantedC) {
    $null = Invoke-ContainerGit add -A
    $null = Invoke-ContainerGit commit -m "Test: class B(i)/C framework-file appends"
    $B1CFiles = Invoke-ContainerGit show --name-only --format= HEAD
    if ($script:PlantedB1 -and ($B1CFiles -notmatch 'Dockerfile')) {
        Write-Error "Class B(i) fixture missing from its commit - aborting before migration."
        exit 1
    }
    if ($script:PlantedC -and ($B1CFiles -notmatch 'CLAUDE\.md')) {
        Write-Error "Class C fixture missing from its commit - aborting before migration."
        exit 1
    }
}

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

# --- Class B(ii): UNCOMMITTED append to a tracked framework file (CLAUDE.md) ---
# A dirty tracked change on a framework file -- exercises the updater's stash/pop
# path on a file upstream also owns (stronger than the research/ dirty-file above,
# which upstream never touches). Capability-probed; skipped-at-plant if the target
# line is absent in this era. Same single-quoted-printf argv rule as Phase 4.
Invoke-ContainerExec grep -q 'Primary execution language' /daaf/CLAUDE.md
if ($LASTEXITCODE -eq 0) {
    Invoke-ContainerExec bash -c 'printf ''\n<!-- test-migration-marker-Bii -->\n'' >> /daaf/CLAUDE.md'
    $script:PlantedB2 = $true
    Write-ObserveNote "Class B(ii) planted: uncommitted CLAUDE.md append (stash/pop path)."
} else {
    Write-ObserveNote "Class B(ii) not planted: CLAUDE.md lacks 'Primary execution language' at $TestVersion."
}

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
if ($script:PlantedB2) {
    Invoke-ContainerExec grep -q 'test-migration-marker-Bii' /daaf/CLAUDE.md
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Class B(ii) uncommitted fixture (CLAUDE.md append) was not created - aborting before migration."
        exit 1
    }
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

# We have reached the meaningful work -- outcome now classifies PASS/FAIL, not
# INFRA. (Setup failures before this point classify INFRA via tm_classify_status.)
$script:MigrationReached = $true

# Snapshot whether the Claude state volume exists RIGHT NOW, immediately before
# migration runs. The backup-content assertion (Check 11) needs to know whether
# the source volume existed AT BACKUP TIME, and backup happens inside migration.
# Capturing the flag here -- rather than re-inspecting live after migration --
# makes the gate robust: anything migration does afterward (a fallback
# `docker compose up` against the current compose file, or phase 8's install.ps1)
# can legitimately create the volume, and a post-migration inspect would then
# wrongly flip an absent-at-backup-time skip into a FAIL.
$ClaudeVolumeExistedPreMigration = Test-DockerVolume $ClaudeVolumeName

# --- Class D baseline: the host environment_settings.txt must survive migration
#     (and any driven update) byte-for-byte -- EXCEPT the active DAAF_BRANCH
#     line. The harness drives update_daaf with env-origin DAAF_BRANCH (branch
#     fidelity), and the updater INTENTIONALLY persists that choice into
#     environment_settings.txt -- a designed, single-line mutation, not fixture
#     loss. Hashing modulo '^DAAF_BRANCH=' keeps the check byte-strict for
#     everything else while tolerating the one sanctioned write (quality
#     review, field-run-4 fix pass; mirrors the .sh `grep -v | cksum`).
function Get-ClassDHash([string]$Path) {
    # PS 5.1-safe string hash: Get-FileHash cannot hash filtered content, so
    # SHA256 over the UTF8 bytes of the non-DAAF_BRANCH lines joined by LF.
    $lines = @(Get-Content -LiteralPath $Path | Where-Object { $_ -notmatch '^DAAF_BRANCH=' })
    $text = ($lines -join "`n")
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($text))) -replace '-','')
    } finally {
        $sha.Dispose()
    }
}
$script:ClassDApplicable = $false
$script:ClassDPre = ""
$ClassDPath = Join-Path $HostDir "environment_settings.txt"
if (Test-Path $ClassDPath) {
    $script:ClassDApplicable = $true
    $script:ClassDPre = Get-ClassDHash $ClassDPath
    Write-ObserveNote "Class D baseline captured (environment_settings.txt SHA256 sans DAAF_BRANCH line: $($script:ClassDPre.Substring(0, 12))...)."
} else {
    Write-ObserveNote "Class D not applicable: no environment_settings.txt in $HostDir (era predates it)."
}

# --- Harness git safe.directory exemption window (CLOSE) ---
# Remove the exemption the harness added in Phase 3, immediately BEFORE migrate is
# invoked -- but ONLY if the harness added it (if it pre-existed, leave it). This
# is the point of the window: closing it here means the field run exercises
# migrate's OWN section-4b safe.directory fix on the v1.0.0 vector end-to-end,
# instead of the harness's instrumentation masking whether migrate handles the
# root-owned Era-1 payload. Targeted value-regex removal (^/daaf$) so any other
# pre-existing safe.directory entries are untouched.
if ($script:HarnessAddedSafeDir) {
    Invoke-ContainerExec git config --global --unset-all safe.directory '^/daaf$'
    Write-ObserveNote "Git safe.directory exemption window CLOSED (harness removed its /daaf entry) immediately before invoking migrate, so migrate's own section-4b safe.directory fix runs on the v1.0.0 vector instead of being masked by harness instrumentation."
}

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
# itself a migration failure that must be recorded truthfully. In auto mode the
# migrate child runs via the redirect-stdin capture path (its output is teed to
# migrate.out, which the interactive-vs-auto update detection below greps); in
# interactive mode the tester drives migrate's prompts at the console.
$script:MigrateOut = Join-Path $TestDir "migrate.out"
$migrationExit = 1
try {
    if ($script:AutoMode) {
        $migrationExit = Invoke-HardenedScriptAuto -Path (Join-Path $HostDir "migrate_daaf.ps1") -CaptureFile $script:MigrateOut
    } else {
        $migrationExit = Invoke-HardenedScript -Path (Join-Path $HostDir "migrate_daaf.ps1")
    }
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
# UPDATE DRIVING (class E + Phase 7b prerequisite)
# =====================================================================
# migrate_daaf.ps1 SKIPS its update offer when non-interactive (it detects the
# redirected stdin and prints "Non-interactive mode detected - skipping update"),
# so in auto mode the harness drives update_daaf.ps1 itself from the host dir. In
# interactive mode the tester already answered migrate's own update offer at the
# console -- but an interactive .ps1 CANNOT capture the console-inherited child
# output to detect whether update ran (unlike the .sh, which tees even
# interactively; DIVERGENCE 3), so UpdateRan stays false and Phase 7b coverage
# requires -Auto.
$script:UpdateOut = Join-Path $TestDir "update.out"
if ($script:AutoMode) {
    if (Test-Path (Join-Path $HostDir "update_daaf.ps1")) {
        # Class E: plant a drift marker on a host script; a healthy update re-syncs
        # it from the branch (marker gone) and backs up the drifted copy as
        # view_logs.ps1.pre-update. Verified in Phase 7b. This is a HOST-side file
        # edit (not a container op), so the docker-exec quoting rules do not apply.
        $ClassEView = Join-Path $HostDir "view_logs.ps1"
        if (Test-Path $ClassEView) {
            Add-Content -LiteralPath $ClassEView -Value "`n# test-migration-marker-E: drifted host script"
            $script:ClassEPlanted = $true
            Write-ObserveNote "Class E planted: drift marker on $ClassEView."
        }
        Write-Host "INFO: Driving update_daaf.ps1 (non-interactive) from $HostDir..." -ForegroundColor Cyan
        Write-Host ""
        # DAAF_BRANCH keeps the driven update BRANCH-FAITHFUL (parity with the
        # migrate drive above): without it the updater auto-detects 'main' and
        # merges GitHub origin/main instead of the branch under test -- field
        # run 4 merged main's tip, so the noble Dockerfile never arrived and no
        # rebuild was exercised.
        $env:DAAF_BRANCH = $MigrationBranch
        $env:DAAF_NESTED = "1"
        $UpdateExit = 1
        try {
            $UpdateExit = Invoke-HardenedScriptAuto -Path (Join-Path $HostDir "update_daaf.ps1") -CaptureFile $script:UpdateOut
        } catch {
            Write-Host "ERROR: Could not run update_daaf.ps1: $_" -ForegroundColor Red
            $UpdateExit = 1
        }
        Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
        Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
        $script:UpdateRan = $true
        Write-Host ""
        if ($UpdateExit -eq 0) {
            Test-Check "Update script completed (exit 0)" $true
        } else {
            # The first driven update exited nonzero. The EXPECTED cause on the
            # remaining era vectors is the Class-C committed CLAUDE.md append vs
            # v3.0.0's wholesale CLAUDE.md rewrite: the merge conflicts on CLAUDE.md
            # and the non-interactive conflict handler exits mid-merge. That abort is
            # the FIRST HALF of the conflict -> resolve -> resume journey a real user
            # walks, NOT a harness failure. Probe the container for the mid-merge
            # state (capture-then-test; Invoke-ContainerGit strips \r, suppresses
            # stderr, and returns "" when MERGE_HEAD is absent).
            $MergeHead = Invoke-ContainerGit rev-parse -q --verify MERGE_HEAD
            $Unmerged = Invoke-ContainerGit diff --name-only --diff-filter=U
            if (Test-ConflictAutoResolvable $MergeHead $Unmerged) {
                Write-ObserveNote "First driven update exited $UpdateExit on the EXPECTED Class-C-vs-rewrite CLAUDE.md merge conflict (MERGE_HEAD present, unmerged set exactly CLAUDE.md). Simulating the guided resolution a real user would perform with Claude Code, then re-driving the resumable updater."
                # Resolve the way update_daaf's own guidance tells a user to: take
                # upstream's rewritten CLAUDE.md (--theirs); then, if the Class C prose
                # marker was planted, re-append it (same printf as at planting, above)
                # so the user's customization survives the resolution and the
                # observe-only Class C content probe (Phase 7) stays meaningful.
                $null = Invoke-ContainerGit checkout --theirs -- CLAUDE.md
                if ($script:PlantedC) {
                    Invoke-ContainerExec bash -c 'printf ''\n<!-- test-migration-marker-C: committed CLAUDE.md prose line -->\n'' >> /daaf/CLAUDE.md'
                }
                $null = Invoke-ContainerGit add CLAUDE.md
                $null = Invoke-ContainerGit commit -m "Resolved merge conflicts from DAAF update (harness-simulated guided resolution)"
                Write-Host "INFO: Re-driving update_daaf.ps1 (resume path) after the simulated conflict resolution..." -ForegroundColor Cyan
                Write-Host ""
                # Identical env/invocation as the first drive. Start-Process truncates
                # its capture file, so re-drive to a SIBLING file and APPEND it to
                # $script:UpdateOut (parity with the .sh `tee -a`) so the self-update
                # grep below sees the union of both runs.
                $env:DAAF_BRANCH = $MigrationBranch
                $env:DAAF_NESTED = "1"
                $ResumeUpdateOut = "$($script:UpdateOut).resume"
                $UpdateExit = 1
                try {
                    $UpdateExit = Invoke-HardenedScriptAuto -Path (Join-Path $HostDir "update_daaf.ps1") -CaptureFile $ResumeUpdateOut
                } catch {
                    Write-Host "ERROR: Could not run update_daaf.ps1 (resume): $_" -ForegroundColor Red
                    $UpdateExit = 1
                }
                Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
                Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
                if (Test-Path $ResumeUpdateOut) {
                    Get-Content -LiteralPath $ResumeUpdateOut | Add-Content -LiteralPath $script:UpdateOut
                }
                Write-Host ""
                # Only the RESUMED run is scored here; the first run's nonzero exit is
                # the expected half of the journey (recorded in the note above).
                if ($UpdateExit -eq 0) {
                    Test-Check "Update conflict journey completed (conflict -> resolved -> resumed update exit 0)" $true
                } else {
                    Test-Check "Update conflict journey completed (conflict -> resolved -> resumed update exit $UpdateExit)" $false
                }
            } else {
                # Not the expected auto-resolvable conflict: either no merge is in
                # progress, or the unmerged set is not exactly CLAUDE.md (e.g. a
                # Dockerfile B(i) conflict, or a multi-file conflict). Fail loudly,
                # verbatim as before, and surface the unmerged set for triage.
                Test-Check "Update script completed (exit $UpdateExit)" $false
                $UnmergedFlat = ($Unmerged -replace "`r", " " -replace "`n", " ")
                Write-ObserveNote "First driven update exited $UpdateExit but the conflict is NOT auto-resolvable (unexpected): MERGE_HEAD='$MergeHead', unmerged set='$UnmergedFlat'. Failing loudly per design."
            }
        }

        # Self-update two-run: if the updater reports it updated ITSELF, a real user
        # re-runs it once more. For the v2.1.0 vector migrate may have pre-seeded the
        # newest update_daaf.ps1, so the banner may legitimately NOT appear -- record
        # a skip in that case rather than a FAIL (a known consequence of routing
        # v2.1.0 through migrate, which downloads the newest host scripts first).
        $selfUpdated = $false
        if (Test-Path $script:UpdateOut) {
            $selfUpdated = [bool](Select-String -Path $script:UpdateOut -Pattern 'updater itself was updated' -Quiet)
        }
        if ($selfUpdated) {
            Write-Host "INFO: Self-update detected - running update once more (as a real user would)..." -ForegroundColor Cyan
            Write-Host ""
            $env:DAAF_BRANCH = $MigrationBranch
            $env:DAAF_NESTED = "1"
            $SecondUpdateOut = "$($script:UpdateOut).2"
            $UpdateExit2 = 1
            try {
                $UpdateExit2 = Invoke-HardenedScriptAuto -Path (Join-Path $HostDir "update_daaf.ps1") -CaptureFile $SecondUpdateOut
            } catch {
                Write-Host "ERROR: Could not run update_daaf.ps1 (second run): $_" -ForegroundColor Red
                $UpdateExit2 = 1
            }
            Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
            Remove-Item Env:\DAAF_BRANCH -ErrorAction SilentlyContinue
            # Append the second run's capture to the primary update.out (the .sh uses
            # `tee -a`) so the Phase 7b greps see the union of both runs.
            if (Test-Path $SecondUpdateOut) {
                Get-Content -LiteralPath $SecondUpdateOut | Add-Content -LiteralPath $script:UpdateOut
            }
            Write-Host ""
            if ($UpdateExit2 -eq 0) {
                Test-Check "Self-update two-run reproduced (second update exit 0)" $true
            } else {
                Test-Check "Self-update two-run reproduced (second update exit $UpdateExit2)" $false
            }
        } else {
            Add-Skip "Self-update two-run: no 'updater itself was updated' banner (migrate pre-seeded the newest update_daaf.ps1 for $TestVersion)."
        }
    } else {
        Add-Skip "Auto-mode update driving: no update_daaf.ps1 in $HostDir (migration did not download it)."
    }
} else {
    # Interactive mode: an interactive .ps1 cannot capture console-inherited child
    # output, so we cannot detect whether the tester accepted migrate's update
    # offer. UpdateRan stays false and Phase 7b documents its skip. Run with -Auto
    # for Phase 7b (newest-endpoint) coverage.
    $script:UpdateRan = $false
    Write-ObserveNote "Interactive mode: cannot capture console-inherited child output to detect an update; Phase 7b will skip. Run with -Auto for newest-endpoint coverage."
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
#     Phase 3 normalization), tracking main -> origin/main comes from the era
#     pathway itself (Era 1 clone), migrate's set-upstream (Era 2, post-fetch),
#     or the Phase 3 tag normalization (Era 3 tags -- replicating what a real
#     `clone -b main` set at install time), and the
#     updater always returns HEAD to the branch it started on. Expect
#     origin/main.
#   - Era 3 BRANCH installs (e.g. daaf_dev): no local main ever exists; the
#     clone's branch keeps its own tracking (origin/<branch>). migrate's
#     set-upstream to main is a silent no-op there. (Historical wart: migrate
#     once printed "Tracking set: main -> origin/main" unconditionally, even on
#     that no-op; fixed as of commit 4cd280d (2026-07-17), which prints the
#     message only on set-upstream success and an honest NOTE otherwise. This
#     harness has always asserted the REAL git tracking state below, never the
#     printed string, so its behavior is unchanged either way.)
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
Write-Host "  Extended Fixture Checks (classes B/C/D):" -ForegroundColor White

# Outcome semantics for the B(i)/B(ii) appends to tracked framework files (a
# three-way outcome, slightly richer than the .sh present/absent binary --
# DIVERGENCE): marker present with NO git conflict markers = PASS; conflict markers
# in the file = CONFLICTED (an Add-Skip with a prominent note, since a conflict on a
# heavily-rewritten upstream file is an expected, non-defect outcome); marker absent
# with no conflict markers = FAIL. The conflict probe greps for 7-char git markers
# (<<<<<<< / >>>>>>>); '=======' is excluded because it occurs in ordinary Markdown.
# All grep argv are PowerShell single-quoted literals with no embedded double quotes.

# Class B(i): committed Dockerfile user-block append survived migration (merge path).
if ($script:PlantedB1) {
    Invoke-ContainerExec grep -q 'test-migration-marker-B: dockerfile-user-block' /daaf/Dockerfile
    $b1Present = ($LASTEXITCODE -eq 0)
    Invoke-ContainerExec grep -qE '<<<<<<<|>>>>>>>' /daaf/Dockerfile
    $b1Conflict = ($LASTEXITCODE -eq 0)
    if ($b1Conflict) {
        Add-Skip "Class B(i): CONFLICTED -- git conflict markers in /daaf/Dockerfile around the committed append (expected when upstream rewrote the file's tail; not a migration defect)."
    } elseif ($b1Present) {
        Test-Check "Class B(i): committed Dockerfile append preserved" $true
    } else {
        Test-Check "Class B(i): committed Dockerfile append preserved" $false
    }
} else {
    Add-Skip "Class B(i): not planted (no USER ADDITIONS block at $TestVersion)."
}

# Class C: committed CLAUDE.md prose append -- OBSERVE-ONLY (never pass/fail).
# DIVERGENCE from the .sh (which pass/fails this): on daaf_dev CLAUDE.md is heavily
# rewritten relative to the old eras, so a committed append near '## Identity'
# legitimately MAY hit a merge conflict on update. Recording the outcome as an
# observe note avoids a spurious FAIL on an expected conflict.
if ($script:PlantedC) {
    Invoke-ContainerExec grep -q 'test-migration-marker-C' /daaf/CLAUDE.md
    if ($LASTEXITCODE -eq 0) {
        Write-ObserveNote "Class C: committed CLAUDE.md append is present after migration (merge preserved it)."
    } else {
        Write-ObserveNote "Class C: committed CLAUDE.md append is NOT present after migration (likely a merge conflict/rewrite on this heavily-edited file -- observe-only, not a FAIL)."
    }
} else {
    Add-Skip "Class C: not planted (no '## Identity' section at $TestVersion)."
}

# Class B(ii): uncommitted CLAUDE.md append survived (updater stash/pop path).
# Same three-way outcome as B(i).
if ($script:PlantedB2) {
    Invoke-ContainerExec grep -q 'test-migration-marker-Bii' /daaf/CLAUDE.md
    $b2Present = ($LASTEXITCODE -eq 0)
    Invoke-ContainerExec grep -qE '<<<<<<<|>>>>>>>' /daaf/CLAUDE.md
    $b2Conflict = ($LASTEXITCODE -eq 0)
    if ($b2Conflict) {
        Add-Skip "Class B(ii): CONFLICTED -- git conflict markers in /daaf/CLAUDE.md around the uncommitted append (expected when upstream rewrote the file's tail; not a migration defect)."
    } elseif ($b2Present) {
        Test-Check "Class B(ii): uncommitted CLAUDE.md append preserved (stash/pop)" $true
    } else {
        Test-Check "Class B(ii): uncommitted CLAUDE.md append preserved (stash/pop)" $false
    }
} else {
    Add-Skip "Class B(ii): not planted (no 'Primary execution language' line at $TestVersion)."
}

# Class D: host environment_settings.txt byte-identical across migration (+update),
# modulo the active DAAF_BRANCH line (see the baseline capture comment: the
# driven update's env-origin DAAF_BRANCH persist is a sanctioned mutation).
# Gated on the pre-migration baseline ($script:ClassDApplicable / $script:ClassDPre).
if ($script:ClassDApplicable) {
    if (Test-Path $ClassDPath) {
        $ClassDPost = Get-ClassDHash $ClassDPath
        if ($ClassDPost -eq $script:ClassDPre) {
            Test-Check "Class D: environment_settings.txt byte-identical across migration (sans DAAF_BRANCH line)" $true
        } else {
            Test-Check "Class D: environment_settings.txt byte-identical sans DAAF_BRANCH line (pre='$($script:ClassDPre.Substring(0,12))...' post='$($ClassDPost.Substring(0,12))...')" $false
        }
    } else {
        Test-Check "Class D: environment_settings.txt still present after migration" $false
    }
} else {
    Add-Skip "Class D: no environment_settings.txt baseline (era predates it)."
}

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
# PHASE 7b: Newest-Endpoint Verification (post-update)
# =====================================================================
# Gated on an actual update run (auto-mode drove it). When no update ran there is
# no "newest endpoint" to assert, so the whole phase is a single documented SKIP
# rather than a set of FAILs. (An interactive .ps1 run cannot capture child output
# to confirm an update, so UpdateRan is false there -- run -Auto for this coverage;
# the single-skip mirrors the .sh's one skip_note for the whole phase.)
Write-Host ""
Write-Host "[7b] Newest-endpoint checks (post-update)" -ForegroundColor White
Write-Host ""
if ($script:UpdateRan) {
    # Re-discover the container (an update rebuild may have replaced it).
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $script:ContainerName = (docker ps -a --filter "volume=$VolumeName" --format '{{.Names}}' | Select-Object -First 1 | Out-String).Trim() -replace "`r",""
    $ErrorActionPreference = $savedEAP
    if (-not [string]::IsNullOrWhiteSpace($script:ContainerName)) {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        $ContainerState = (docker inspect --format '{{.State.Status}}' $script:ContainerName 2>$null | Out-String).Trim() -replace "`r",""
        $ErrorActionPreference = $savedEAP
        if ($ContainerState -ne "running") {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
            docker start $script:ContainerName 2>&1 | Out-Null
            $ErrorActionPreference = $savedEAP
            Start-Sleep -Seconds 3
        }
    }

    # Rebuild evidence: update's build-change check invokes rebuild_daaf.ps1 when the
    # Dockerfile/compose changed across the update; rebuild prints these strings.
    # Absent => the build was unchanged, a legitimate skip (not a FAIL).
    $rebuildSeen = $false
    if (Test-Path $script:UpdateOut) {
        $rebuildSeen = [bool](Select-String -Path $script:UpdateOut -Pattern 'Rebuilding Docker image|Rebuild complete' -Quiet)
    }
    if ($rebuildSeen) {
        Test-Check "Update triggered a Docker rebuild (build strings in update output)" $true
    } else {
        Add-Skip "No rebuild strings in update output (Dockerfile/compose unchanged across this update -- rebuild legitimately not triggered)."
    }

    # Noble base image: the HEAD Dockerfile is FROM ubuntu:24.04 (noble). Capture as
    # one string (Out-String) so -match returns a scalar bool for Test-Check.
    $OsRelease = (Invoke-ContainerExec cat /etc/os-release | Out-String)
    Test-Check "Container base image is Ubuntu noble (24.04) after update" ($OsRelease -match 'VERSION_CODENAME=noble')

    # Functional smoke: container exec-ready + git sanity + hooks present.
    Invoke-ContainerExec true 2>&1 | Out-Null
    Test-Check "Container exec-ready after update" ($LASTEXITCODE -eq 0)
    $GitDescPost = Invoke-ContainerGit describe --tags --always
    Test-Check "git describe returns a sane ref after update ($GitDescPost)" (-not [string]::IsNullOrWhiteSpace($GitDescPost))

    # Upstream tracking survives update (reuse the era-conditional expectation set by
    # Check 2 above).
    $TrackingPost = Invoke-ContainerGit rev-parse --abbrev-ref --symbolic-full-name '@{u}'
    if ($TrackingPost -eq $ExpectedTracking) {
        Test-Check "Upstream tracking still $ExpectedTracking after update" $true
    } else {
        Test-Check "Upstream tracking still $ExpectedTracking after update (got: '$TrackingPost')" $false
    }
    Invoke-ContainerExec test -d /daaf/.claude/hooks
    Test-Check "Framework hooks directory present after update (.claude/hooks)" ($LASTEXITCODE -eq 0)

    # Class E drift-heal: the drifted host script was re-synced (marker gone) and the
    # drifted copy backed up as view_logs.ps1.pre-update.
    if ($script:ClassEPlanted) {
        $ClassEViewPost = Join-Path $HostDir "view_logs.ps1"
        $markerGone = $true
        if (Test-Path $ClassEViewPost) {
            $markerGone = -not [bool](Select-String -Path $ClassEViewPost -Pattern 'test-migration-marker-E' -Quiet)
        }
        Test-Check "Class E: drifted host script re-synced by update (marker cleared)" $markerGone
        Test-Check "Class E: drifted host script backed up (view_logs.ps1.pre-update)" (Test-Path (Join-Path $HostDir "view_logs.ps1.pre-update"))
    } else {
        Add-Skip "Class E: drift marker not planted (auto-mode only; no view_logs.ps1 at update time)."
    }
} else {
    Add-Skip "Newest-endpoint checks skipped: no update ran (interactive mode, or update_daaf.ps1 absent)."
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
Write-Host "  Skipped:  $($script:TestsSkipped)" -ForegroundColor Yellow
Write-Host ""

if ($script:TestsSkipped -gt 0) {
    Write-Host "  Skips (not failures):" -ForegroundColor Yellow
    foreach ($s in $script:Skips) { Write-Host $s -ForegroundColor Yellow }
    Write-Host ""
}

# The machine-readable TEST_MIGRATION_SUMMARY line is emitted by Complete-Run /
# Write-SummaryOnce, so it is always the final stdout line regardless of exit path.
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
    Write-Host ""
    Write-Host "Test working directory preserved at: $TestDir"
    Write-Host "(Delete manually when done inspecting)"
    Complete-Run 1
} else {
    Write-Host "SUCCESS: All checks passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  The DAAF Docker resources are still running for manual inspection."
    Write-Host "  To clean up:  `$env:DAAF_NUKE_CONFIRM = '1'; & '$LocalRepoRoot\scripts\host\nuke_daaf.ps1'"
    Write-Host ""
    Write-Host "Test working directory preserved at: $TestDir"
    Write-Host "(Delete manually when done inspecting)"
    Complete-Run 0
}

# NOTE: the standalone end-of-run "Press Enter to close" pause is intentionally
# gone -- Write-SummaryOnce performs the interactive pause (auto/nested-aware) just
# before emitting the summary, so the summary line is always the final stdout line.
