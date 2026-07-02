# ============================================================================
# DAAF Update Script (Windows PowerShell)
# ============================================================================
# Usage:
#   cd daaf-docker
#   .\update_daaf.ps1
#
#   To update from a specific branch (default: auto-detects main/master):
#   $env:DAAF_BRANCH = "dev"; .\update_daaf.ps1
#
# What this script does:
#   1. Optionally backs up your DAAF installation (via backup_daaf.ps1)
#   2. Checks for updates and detects your git state
#   3. Walks you through updating safely with options at each step
#   4. Offers Claude Code to help resolve any merge conflicts
#   5. Syncs utility scripts and auto-rebuilds if Docker files changed
#
# This script runs on the host and reaches into the container for git
# operations. It composes the existing backup and rebuild scripts rather
# than reimplementing their logic.
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection
#   - Run from the daaf-docker directory
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

$ErrorActionPreference = "Stop"

function Wait-AndExit {
    param([int]$Code = 0)
    # Release the concurrent-run mutex if we hold it
    if ($script:Mutex) {
        try { $script:Mutex.ReleaseMutex() } catch {
            # Mutex may not be held (e.g., exit before acquisition) -- safe to ignore
            Write-Verbose "Silenced: $_"
        }
    }
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    # For non-zero exits, use [Environment]::Exit() which terminates the CLR
    # process unconditionally.  Plain `exit` fails to propagate when this
    # script is dot-sourced for testing -- it only unwinds the dot-sourced
    # scope instead of terminating the host process.
    if ($Code -ne 0) { [Environment]::Exit($Code) }
    exit $Code
}

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI
# cross-platform smoke testing without a Docker daemon.
# Mock git returns simulate an "already up to date" state for clean exit.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*compose ps*--format*" { Write-Output "daaf-docker" }
            "*compose up*" { return }
            "*compose exec*test -f*/daaf/.git/shallow*" {
                # Not a shallow clone
                $global:LASTEXITCODE = 1
                return
            }
            "*compose exec*test -f*" { return }
            "*compose exec*git -C /daaf remote get-url origin*" {
                Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
            }
            "*compose exec*git -C /daaf fetch*" { return }
            "*compose exec*git -C /daaf rev-parse --verify*origin/main*" {
                Write-Output "abc123def456"
            }
            "*compose exec*git -C /daaf rev-parse HEAD*" {
                Write-Output "abc123def456"
            }
            "*compose exec*git -C /daaf rev-parse*origin/main*" {
                Write-Output "abc123def456"
            }
            "*compose exec*git -C /daaf branch*--show-current*" {
                Write-Output "main"
            }
            "*compose exec*git -C /daaf branch*" { return }
            "*compose exec*git -C /daaf diff --name-only*" {
                # No dirty files
                return
            }
            "*compose exec*git -C /daaf rev-list*" {
                Write-Output "0"
            }
            "*compose exec*git*" { return }
            "*compose exec*" { return }
            "*cp *" { return }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }
}

$UpstreamRepo = "DAAF-Contribution-Community/daaf"
$ContainerName = "daaf-daaf-docker-1"
$Timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
$BackupBranch = "backup/pre-update-$Timestamp"
$Mutex = $null  # Initialized before trap; set to actual mutex after helper functions

# --- Trap handler for unexpected failures ---
trap {
    Write-Host "" -ForegroundColor Red
    Write-Host "-------------------------------------------" -ForegroundColor Red
    Write-Host "  Something went wrong unexpectedly" -ForegroundColor Red
    Write-Host "-------------------------------------------" -ForegroundColor Red
    Write-Host ""
    Write-Host "Your research files and data are safe - updates only change"
    Write-Host "framework files, not your research/ folder."
    Write-Host ""
    Write-Host "Most likely causes:"
    Write-Host "  - Docker Desktop stopped (laptop sleep, lid closed)"
    Write-Host "  - Internet connection dropped during download"
    Write-Host "  - A temporary Docker glitch"
    Write-Host ""
    Write-Host "To try again:"
    Write-Host "  1. Make sure Docker Desktop is running"
    Write-Host "  2. Re-run:  .\update_daaf.ps1"
    Write-Host "     (It is safe to re-run - it will pick up where it left off.)"
    Write-Host ""
    if ($Stashed) {
        Write-Host "Your uncommitted changes are safely saved in a stash."
        Write-Host "To restore them after fixing the issue:"
        Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
        Write-Host ""
    }
    $branchExists = Invoke-ComposeGit rev-parse --verify $BackupBranch
    if ($LASTEXITCODE -eq 0) {
        Write-Host "A restore point was saved before the update started. To undo"
        Write-Host "any partial changes:"
        Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
        Write-Host ""
    }
    # Release the concurrent-run mutex if we hold it
    if ($Mutex) {
        try { $Mutex.ReleaseMutex() } catch {
            # Mutex may not be held if trap fires before lock acquisition -- safe to ignore
            Write-Verbose "Silenced: $_"
        }
    }
    # Inline Wait-AndExit logic -- do not call the function here because trap
    # blocks are scope-wide (active before function definitions execute), and
    # Invoke-Expression evaluation may lose function definitions during scope
    # unwinding, causing CommandNotFoundException.
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    [Environment]::Exit(1)
}

# =====================================================================
# Helper functions
# =====================================================================

# Run docker compose exec with git, suppressing stderr (for commands where
# stderr is expected/unwanted). Strips carriage returns and returns trimmed
# string. Uses SilentlyContinue to prevent PS 5.1 from promoting stderr to
# a terminating error when $ErrorActionPreference is "Stop" in the caller's
# scope.
function Invoke-ComposeGit {
    # Uses $args (simple function) instead of [Parameter(ValueFromRemainingArguments)]
    # so PowerShell does not add common parameters (-Debug, -Verbose,
    # -PipelineVariable, ...) that silently consume single-letter git flags.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $raw = @(docker compose exec -T daaf-docker git -C /daaf @args 2>$null)
        $exitCode = $LASTEXITCODE
        $result = ($raw | Out-String)
        $global:LASTEXITCODE = $exitCode
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run docker compose exec with git, allowing stderr through (for commands
# that produce useful progress output). Strips carriage returns and returns
# trimmed string. Uses SilentlyContinue to prevent PS 5.1 from promoting
# stderr to a terminating error when $ErrorActionPreference is "Stop" in
# the caller's scope.
function Invoke-ComposeGitVerbose {
    # Simple function -- see Invoke-ComposeGit comment for rationale.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $raw = @(docker compose exec -T daaf-docker git -C /daaf @args)
        $exitCode = $LASTEXITCODE
        $result = ($raw | Out-String)
        $global:LASTEXITCODE = $exitCode
        return ($result -replace "`r","").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run docker compose exec with git, piping output to Out-Null (for commands
# where we only care about $LASTEXITCODE). Uses SilentlyContinue to prevent
# PS 5.1 from promoting stderr to a terminating error.
function Invoke-ComposeGitNull {
    # Simple function -- see Invoke-ComposeGit comment for rationale.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $null = docker compose exec -T daaf-docker git -C /daaf @args 2>&1
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run docker compose with arbitrary args. Uses SilentlyContinue to prevent
# PS 5.1 from promoting stderr to a terminating error.
function Invoke-Compose {
    # Simple function -- see Invoke-ComposeGit comment for rationale.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose @args
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# Run docker compose exec with arbitrary (non-git) args. Uses
# SilentlyContinue to prevent PS 5.1 from promoting stderr to a
# terminating error.
function Invoke-ComposeExec {
    # Simple function -- see Invoke-ComposeGit comment for rationale.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose exec -T daaf-docker @args
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

function Read-UserChoice {
    param(
        [string]$PromptText,
        [string[]]$ValidChoices
    )
    # Non-interactive mode (CI, piped input): auto-select first valid choice
    try { $interactive = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) }
    catch { $interactive = $false }
    if (-not $interactive) {
        Write-Host "  (Non-interactive mode - auto-selecting: $($ValidChoices[0]))"
        return $ValidChoices[0]
    }
    while ($true) {
        $choice = (Read-Host $PromptText).Trim().ToLower()
        if ($ValidChoices -contains $choice) { return $choice }
        Write-Host "  Please enter one of: $($ValidChoices -join ', ')" -ForegroundColor Yellow
    }
}

# Override Read-UserChoice in dry-run mode (must come after the real definition
# since the later definition overwrites the earlier one at the same scope)
if ($env:DAAF_DRY_RUN -eq "1") {
    function Read-UserChoice {
        param([string]$PromptText, [string[]]$ValidChoices)
        $null = $PromptText  # Accept param for interface compatibility
        Write-Host "[DRY-RUN] Auto-selecting: $($ValidChoices[0])"
        return $ValidChoices[0]
    }
}

function Resolve-Conflict {
    param(
        [string]$ConflictType,
        [string]$AbortCmd
    )

    $conflictFiles = Invoke-ComposeGit diff --name-only --diff-filter=U

    Write-Host ""
    Write-Host "-------------------------------------------"
    Write-Host "  Conflict detected"
    Write-Host "-------------------------------------------"
    Write-Host ""
    Write-Host "The same file(s) were changed both in the update and in your local"
    Write-Host "version. Git has marked the conflicting sections with <<<<<<< and"
    Write-Host ">>>>>>> markers."
    Write-Host ""
    if ($conflictFiles) {
        Write-Host "Conflicting files:"
        $conflictFiles -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "  $_" } }
        Write-Host ""
    }
    # Claude Code requires an interactive terminal (docker exec -it). When
    # running non-interactively (e.g., nested from migrate_daaf.ps1), skip
    # straight to manual resolution instructions.
    $canInteract = $false
    try { $canInteract = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) } catch { Write-Verbose "Silenced: $_" }
    $choice = "2"
    if ($canInteract) {
        Write-Host "Options:"
        Write-Host "  1) Launch Claude Code to help resolve the conflicts"
        Write-Host "     Claude Code can read the files, explain both sides, and walk"
        Write-Host "     you through the resolution interactively."
        Write-Host ""
        Write-Host "  2) Exit and resolve manually"
        Write-Host ""
        $choice = Read-UserChoice "  Choose [1/2]" @("1", "2")
    }

    if ($choice -eq "1") {
        Write-Host ""
        Write-Host "Launching Claude Code inside the container..."
        Write-Host ""
        Write-Host "Copy and paste this prompt to get started:"
        Write-Host ""
        if ($conflictFiles) {
            Write-Host "  User support mode. I just ran the DAAF updater and got"
            Write-Host "  $ConflictType conflicts in these files:"
            $conflictFiles -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "    $_" } }
        } else {
            Write-Host "  User support mode. I just ran the DAAF updater and got"
            Write-Host "  $ConflictType conflicts."
        }
        Write-Host ""
        Write-Host "  Please help me resolve them. For each conflicting file:"
        Write-Host "  1. Read it and explain what changed on both sides of the"
        Write-Host "     conflict markers (<<<<<<< vs >>>>>>>)"
        Write-Host "  2. Help me decide which version to keep or how to combine them"
        Write-Host "  3. Edit the file to remove all conflict markers"
        Write-Host "  After all files are resolved, commit the result:"
        Write-Host "    git add ."
        if ($ConflictType -eq "merge") {
            Write-Host "    git commit -m `"Resolved merge conflicts from DAAF update`""
        } else {
            Write-Host "    git rebase --continue"
        }
        Write-Host "  When finished, remind me to type /exit so the updater can"
        Write-Host "  finish its remaining steps."
        Write-Host ""
        Write-Host "IMPORTANT: When Claude Code is done, type /exit to return here."
        Write-Host "The updater still needs to finish a few steps after this."
        Write-Host ""
        # EAP = SilentlyContinue prevents PS 5.1 from promoting Docker's
        # stderr to a terminating error under the script's global EAP = Stop.
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        docker compose exec daaf-docker claude
        $ErrorActionPreference = $savedEAP
        Write-Host ""

        $remaining = Invoke-ComposeGit diff --name-only --diff-filter=U

        if ([string]::IsNullOrWhiteSpace($remaining)) {
            Write-Host "Conflicts resolved!"
            Write-Host ""
            $script:ConflictResolved = $true
            return
        } else {
            Write-Host "Some conflicts still remain in these files:"
            $remaining -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "  $_" } }
            Write-Host ""
            Write-Host "You can keep working on them - launch Claude Code and pick up"
            Write-Host "where you left off:"
            Write-Host "  .\run_daaf.ps1"
            Write-Host ""
            Write-Host "Or to undo the update entirely (your research files are not affected):"
            Write-Host "  docker compose exec daaf-docker git -C /daaf $AbortCmd"
            Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
            $script:ConflictResolved = $false
            return
        }
    } else {
        Write-Host ""
        Write-Host "To resolve the conflicts manually, enter the container:"
        Write-Host "  .\run_daaf.ps1 bash"
        Write-Host ""
        Write-Host "Conflicting files contain markers that look like:"
        Write-Host "  <<<<<<< HEAD"
        Write-Host "  (your version)"
        Write-Host "  ======="
        Write-Host "  (the update's version)"
        Write-Host "  >>>>>>>"
        Write-Host "Edit each file to keep the version you want, removing all markers."
        Write-Host ""
        if ($ConflictType -eq "merge") {
            Write-Host "After resolving all files (inside the container):"
            Write-Host "  git add ."
            Write-Host "  git commit -m `"Resolved merge conflicts`""
            Write-Host "  exit"
        } else {
            Write-Host "After resolving all files (inside the container):"
            Write-Host "  git add ."
            Write-Host "  git rebase --continue"
            Write-Host "  exit"
        }
        Write-Host ""
        Write-Host "To undo the update instead (run from PowerShell, not the container):"
        Write-Host "  docker compose exec daaf-docker git -C /daaf $AbortCmd"
        Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
        $script:ConflictResolved = $false
        return
    }
}

function Resolve-StashConflict {
    Write-Host ""
    Write-Host "The framework update was applied successfully!"
    Write-Host ""
    Write-Host "However, some of your uncommitted edits overlap with files that"
    Write-Host "changed in the update. Your edits are NOT lost - they are saved"
    Write-Host "in a temporary holding area."
    Write-Host ""
    # Claude Code requires an interactive terminal. When non-interactive,
    # skip straight to manual resolution instructions.
    $canInteract = $false
    try { $canInteract = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) } catch { Write-Verbose "Silenced: $_" }
    $choice = "2"
    if ($canInteract) {
        Write-Host "Options:"
        Write-Host "  1) Launch Claude Code to help resolve the conflicts"
        Write-Host "  2) Exit and resolve manually"
        Write-Host ""
        $choice = Read-UserChoice "  Choose [1/2]" @("1", "2")
    }

    if ($choice -eq "1") {
        Write-Host ""
        Write-Host "Launching Claude Code inside the container..."
        Write-Host ""
        Write-Host "Copy and paste this prompt to get started:"
        Write-Host ""
        Write-Host "  User support mode. The DAAF updater applied the framework"
        Write-Host "  update successfully, but re-applying my uncommitted changes"
        Write-Host "  caused stash conflicts. Please help me resolve them:"
        Write-Host "  1. Run git status to find the conflicting files"
        Write-Host "  2. Read each one and explain both sides of the conflict"
        Write-Host "  3. Help me choose what to keep and edit the file to resolve it"
        Write-Host "  4. After all conflicts are resolved, run: git add ."
        Write-Host "     Then: git stash drop"
        Write-Host "     Then: git commit -m 'Resolved stash conflicts from DAAF update'"
        Write-Host "  When done, remind me to type /exit so the updater can"
        Write-Host "  finish its remaining steps."
        Write-Host ""
        Write-Host "IMPORTANT: When Claude Code is done, type /exit to return here."
        Write-Host "The updater still needs to finish a few steps after this."
        Write-Host ""
        # EAP = SilentlyContinue prevents PS 5.1 from promoting Docker's
        # stderr to a terminating error under the script's global EAP = Stop.
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        docker compose exec daaf-docker claude
        $ErrorActionPreference = $savedEAP
        Write-Host ""

        $remaining = Invoke-ComposeGit diff --name-only --diff-filter=U

        if ([string]::IsNullOrWhiteSpace($remaining)) {
            Write-Host "Conflicts resolved!"
            $script:StashConflictResolved = $true
            return
        } else {
            Write-Host "Some conflicts still remain in these files:"
            $remaining -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "  $_" } }
            Write-Host ""
            Write-Host "You can keep working on them - launch Claude Code:"
            Write-Host "  .\run_daaf.ps1"
            Write-Host ""
            Write-Host "Or to undo the update:"
            Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
            Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
            $script:StashConflictResolved = $false
            return
        }
    } else {
        Write-Host ""
        Write-Host "To resolve, enter the container:"
        Write-Host "  .\run_daaf.ps1 bash"
        Write-Host "  (edit the conflicting files to remove the <<<<<<< markers)"
        Write-Host "  git add ."
        Write-Host "  git stash drop"
        Write-Host "  exit"
        Write-Host ""
        Write-Host "Or to discard your uncommitted edits and keep the update"
        Write-Host "(WARNING - this cannot be undone):"
        Write-Host "  .\run_daaf.ps1 bash"
        Write-Host "  git checkout -- ."
        Write-Host "  git stash drop"
        Write-Host "  exit"
        Write-Host ""
        Write-Host "To undo the entire update:"
        Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
        Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
        $script:StashConflictResolved = $false
        return
    }
}

# Copy one host script out of the container. Returns $true on success, $false
# on failure (printing a manual-recovery hint -- no silent skips).
function Copy-HostScript {
    param([string]$RepoPath)
    $scriptName = Split-Path $RepoPath -Leaf
    $savedEAP = $ErrorActionPreference
    try { $ErrorActionPreference = "SilentlyContinue"; docker cp "${ContainerName}:/daaf/$RepoPath" "./$scriptName" 2>$null } finally { $ErrorActionPreference = $savedEAP }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Updated: $scriptName"
        return $true
    } else {
        Write-Host "  Warning: could not copy $scriptName. You can copy it manually:" -ForegroundColor Yellow
        Write-Host "    docker cp ${ContainerName}:/daaf/$RepoPath ./$scriptName" -ForegroundColor Yellow
        return $false
    }
}

# Sync host-side utility scripts out of the container to the daaf-docker folder.
#
# The old design diffed a HARDCODED pathspec inside the running (old) script, so
# files added upstream that the old script did not know about were silently
# skipped forever (chicken-and-egg). This rewrite derives the file list from the
# POST-UPDATE repo state (git ls-files at new HEAD) and adds an existence-heal
# pass so past misses self-correct on the next run. Mirrors the Bash design in
# update_daaf.sh sync_host_scripts.
#
# $OldHead may be empty (called from the "already up to date" path). When empty
# or equal to $newHead, only the existence-heal pass runs.
function Sync-HostScript {
    param([string]$OldHead = "")

    $newHead = Invoke-ComposeGit rev-parse HEAD

    # Authoritative host-script list from the post-update repo state. ls-files
    # runs in-container (Linux git) so its features are fine here.
    $allHostFiles = Invoke-ComposeGit ls-files 'scripts/host/*'
    if ([string]::IsNullOrWhiteSpace($allHostFiles)) { return }

    # Platform filter (Windows hosts): keep *.ps1 files, the shared plain-text
    # files (environment_settings_example.txt, README.txt), and daaf.sh /
    # daaf_lib.sh (the Control Panel is run via Git Bash on Windows -- there is
    # no daaf.ps1). Drop other
    # *.sh files. Bootstrap-only scripts (install.ps1, migrate_daaf.ps1) are
    # intentionally excluded -- fetched via irm on demand, not needed post-install.
    $syncList = @()
    foreach ($line in ($allHostFiles -split "`n")) {
        $repoPath = $line.Trim()
        if (-not $repoPath) { continue }
        if ($repoPath -eq "scripts/host/install.ps1" -or $repoPath -eq "scripts/host/migrate_daaf.ps1") { continue }
        if ($repoPath -like "*.ps1" -or
            $repoPath -eq "scripts/host/environment_settings_example.txt" -or
            $repoPath -eq "scripts/host/README.txt" -or
            $repoPath -eq "scripts/host/daaf.sh" -or
            $repoPath -eq "scripts/host/daaf_lib.sh") {
            $syncList += $repoPath
        }
    }
    if ($syncList.Count -eq 0) { return }

    # Files changed in the update range (tier B). Only when we have a real range.
    $changedList = @()
    if ($OldHead -and ($OldHead -ne $newHead)) {
        $changedRaw = Invoke-ComposeGit diff --name-only "$OldHead..$newHead" -- scripts/host
        foreach ($line in ($changedRaw -split "`n")) {
            $p = $line.Trim()
            if ($p) { $changedList += $p }
        }
    }

    $copied = @()
    $selfUpdated = $false
    $printedHeader = $false
    $syncCopyFailed = $false

    # --- Tier A: existence-heal ---
    # Any host-appropriate file MISSING on the host is copied unconditionally.
    foreach ($repoPath in $syncList) {
        $scriptName = Split-Path $repoPath -Leaf
        if (-not (Test-Path "./$scriptName")) {
            if (-not $printedHeader) { Write-Host "Syncing utility scripts..."; $printedHeader = $true }
            if (Copy-HostScript $repoPath) {
                $copied += $scriptName
            } else {
                $syncCopyFailed = $true
            }
        }
    }

    # --- Tier B: changed files ---
    # Any listed file changed in this range is copied (unless tier A already did).
    foreach ($repoPath in $changedList) {
        if ($syncList -notcontains $repoPath) { continue }
        $scriptName = Split-Path $repoPath -Leaf
        if ($copied -contains $scriptName) { continue }
        if (-not $printedHeader) { Write-Host "Syncing updated utility scripts..."; $printedHeader = $true }
        if (Copy-HostScript $repoPath) {
            if ($scriptName -eq "update_daaf.ps1") { $selfUpdated = $true }
            $copied += $scriptName
        } else {
            $syncCopyFailed = $true
        }
    }

    if ($printedHeader) { Write-Host "" }

    # --- Sync failure summary ---
    # $syncCopyFailed is set on any copy error. Print a closing summary so the
    # user knows to act even if the per-file warning scrolled by.
    if ($syncCopyFailed) {
        Write-Host "Warning: some host scripts could not be synced -- see the messages above for manual copy commands."
        Write-Host ""
    }

    # --- Self-update notice ---
    # If the updater itself was refreshed as a CHANGED file, its new logic is on
    # disk but was not executed this run. Prompt a re-run so the new updater's
    # existence-heal pass can deliver anything the old logic could not (no auto
    # re-exec -- that would collide with the mutex and trap handling).
    if ($selfUpdated) {
        Write-Host "-------------------------------------------"
        Write-Host "  The updater itself was updated"
        Write-Host "-------------------------------------------"
        Write-Host ""
        Write-Host "update_daaf.ps1 was refreshed in this update. The new version is"
        Write-Host "now on disk but this run used the previous version. Re-run it once"
        Write-Host "more so the latest updater can finish syncing your host tools:"
        Write-Host "  .\update_daaf.ps1"
        Write-Host ""
        Write-Host "(It is safe to re-run - if everything is already current it will"
        Write-Host " simply report 'Already up to date!')"
        Write-Host ""
    }
}

function Test-BuildChange {
    param([string]$OldHead)

    $newHead = Invoke-ComposeGit rev-parse HEAD

    if ($OldHead -eq $newHead) {
        Write-Host "No Dockerfile changes - no container rebuild needed."
        Write-Host ""
        return
    }

    $buildChanges = Invoke-ComposeGit diff --name-only "$OldHead..$newHead" -- `
        Dockerfile docker-compose.yml

    if ([string]::IsNullOrWhiteSpace($buildChanges)) {
        Write-Host "No Dockerfile changes - no container rebuild needed."
        Write-Host ""
        return
    }

    Write-Host ""
    Write-Host "Build files were updated in this release:"
    $buildChanges -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "  $_" } }
    Write-Host ""
    Write-Host "A rebuild is needed for these changes to take full effect."
    Write-Host ""
    $choice = Read-UserChoice "  Run rebuild now? [y/n]" @("y", "n")

    if ($choice -eq "y") {
        Write-Host ""
        if (Test-Path "rebuild_daaf.ps1") {
            $env:DAAF_NESTED = "1"
            & .\rebuild_daaf.ps1
            Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
        } else {
            Write-Host "rebuild_daaf.ps1 is not in your daaf-docker folder."
            Write-Host "You can retrieve it from the container and run it:"
            Write-Host "  docker cp ${ContainerName}:/daaf/scripts/host/rebuild_daaf.ps1 .\rebuild_daaf.ps1"
            Write-Host "  .\rebuild_daaf.ps1"
        }
    } else {
        Write-Host ""
        Write-Host "When you're ready to rebuild:"
        Write-Host "  .\rebuild_daaf.ps1"
    }
}

function Complete-Update {
    param(
        [string]$OldHead,
        [string]$ExtraMsg = ""
    )

    Sync-HostScript $OldHead
    Test-BuildChange $OldHead

    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Update complete!"
    Write-Host "=========================================="
    Write-Host ""
    if ($ExtraMsg) {
        Write-Host $ExtraMsg
        Write-Host ""
    }
    Write-Host "If you need to undo this update later:"
    Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
    Write-Host ""
    Write-Host "  (This reverts DAAF's framework files to how they were before the"
    Write-Host "   update. Your research projects and data are not affected.)"
    Write-Host ""
    Write-Host "  To launch DAAF:"
    Write-Host "    .\run_daaf.ps1"
    Write-Host ""
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/update_daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# =====================================================================
# Concurrent-run lock (named mutex)
# =====================================================================
# Prevent two simultaneous update_daaf runs from corrupting git state
# (double-stash, conflicting merges, backup branch pointing to wrong commit).
$MutexName = "Global\DAAFUpdate"
$Mutex = [System.Threading.Mutex]::new($false, $MutexName)
try {
    if (-not $Mutex.WaitOne(0)) {
        Write-Host "ERROR: Another instance of update_daaf is already running." -ForegroundColor Red
        Write-Host "       Wait for it to finish or restart Docker Desktop to clear the lock." -ForegroundColor Yellow
        Wait-AndExit 1
    }
} catch [System.Threading.AbandonedMutexException] {
    # Previous instance crashed without releasing -- we now own the mutex, continue
    Write-Verbose "Silenced: $_"
}

# =====================================================================
# Main script
# =====================================================================

Write-Host ""
Write-Host "=========================================="
Write-Host "  DAAF Updater"
Write-Host "=========================================="
Write-Host ""
Write-Host "Tip: If Claude Code is running inside the container, exit it first"
Write-Host "(/exit) to avoid file conflicts during the update."
Write-Host ""

# --- Preflight: docker-compose.yml ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host ""
    Write-Host "This script must be run from your daaf-docker folder. Try:"
    Write-Host "  cd ~\daaf-docker"
    Write-Host "  .\update_daaf.ps1"
    Write-Host ""
    Write-Host "If you installed DAAF somewhere else, cd to that folder first."
    Wait-AndExit 1
}

# --- Preflight: Docker installed ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from PowerShell." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Wait-AndExit 1
}

# --- Preflight: Docker running ---
$savedEAP = $ErrorActionPreference
try { $ErrorActionPreference = "SilentlyContinue"; $null = docker info 2>&1 } finally { $ErrorActionPreference = $savedEAP }
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    Wait-AndExit 1
}

# --- Preflight: Start container if needed ---
$savedEAP = $ErrorActionPreference
try { $ErrorActionPreference = "SilentlyContinue"; $runningCheck = docker compose ps --status running --format '{{.Name}}' 2>$null } finally { $ErrorActionPreference = $savedEAP }
$running = ($runningCheck | Out-String) -match "daaf-docker"

if (-not $running) {
    Write-Host "Starting DAAF container..."
    Invoke-Compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Failed to start the DAAF container." -ForegroundColor Red
        Write-Host ""
        Write-Host "No changes were made to your installation."
        Write-Host ""
        Write-Host "Common causes:"
        Write-Host "  - Another program is using the same ports"
        Write-Host "  - Docker Desktop needs more memory (Settings > Resources)"
        Write-Host ""
        Write-Host "Try restarting Docker Desktop, then:  .\update_daaf.ps1"
        Wait-AndExit 1
    }

    $retries = 0
    $maxRetries = 30
    $readyLog = [System.IO.Path]::GetTempFileName()
    while ($retries -lt $maxRetries) {
        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        docker compose exec -T daaf-docker true 2>> $readyLog
        $ErrorActionPreference = $savedEAP
        if ($LASTEXITCODE -eq 0) { break }
        $retries++
        Start-Sleep -Seconds 2
    }
    if ($retries -ge $maxRetries) {
        Write-Host ""
        Write-Host "ERROR: The DAAF container started but is not responding after 60 seconds." -ForegroundColor Red
        if ((Test-Path $readyLog) -and (Get-Item $readyLog).Length -gt 0) {
            Write-Host "  Docker reported:" -ForegroundColor Red
            Get-Content $readyLog -Tail 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            Write-Host ""
        }
        Write-Host "No changes were made to your DAAF installation."
        Write-Host ""
        Write-Host "This can happen if Docker Desktop is under heavy load."
        Write-Host "Try:"
        Write-Host "  1. Restart Docker Desktop"
        Write-Host "  2. Re-run:  .\update_daaf.ps1"
        Remove-Item $readyLog -ErrorAction SilentlyContinue
        Wait-AndExit 1
    }
    Remove-Item $readyLog -ErrorAction SilentlyContinue
    Write-Host "Container started."
    Write-Host ""
}

# --- Preflight: DAAF installed ---
$null = Invoke-ComposeExec test -f /daaf/CLAUDE.md 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: DAAF does not appear to be installed in the container." -ForegroundColor Red
    Write-Host "Run the installer first. See:"
    Write-Host "  https://github.com/$UpstreamRepo#quick-start"
    Wait-AndExit 1
}

# =====================================================================
# Offer backup
# =====================================================================
Write-Host "-------------------------------------------"
Write-Host "  Backup recommendation"
Write-Host "-------------------------------------------"
Write-Host ""
Write-Host "It's a good idea to back up before updating, especially if you have"
Write-Host "research projects or local customizations you want to protect."
Write-Host ""
if (Test-Path "backup_daaf.ps1") {
    $choice = Read-UserChoice "  Run backup now? [y/n]" @("y", "n")
    if ($choice -eq "y") {
        Write-Host ""
        $env:DAAF_NESTED = "1"
        & .\backup_daaf.ps1
        Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
        Write-Host ""
    }
} else {
    Write-Host "  (backup_daaf.ps1 not found in this directory - skipping)"
    Write-Host ""
}

# =====================================================================
# Create git backup branch (lightweight restore point)
# =====================================================================
Invoke-ComposeGitNull branch $BackupBranch

$OldHead = Invoke-ComposeGit rev-parse HEAD

# =====================================================================
# Check git remote
# =====================================================================
$OriginUrl = Invoke-ComposeGit remote get-url origin

if ([string]::IsNullOrWhiteSpace($OriginUrl)) {
    Write-Host ""
    Write-Host "Your DAAF installation is not connected to the update server."
    Write-Host ""
    Write-Host "This usually means DAAF was installed from a downloaded zip file"
    Write-Host "instead of using the installer script. To connect it for updates,"
    Write-Host "run these commands one at a time:"
    Write-Host ""
    Write-Host "  .\run_daaf.ps1 bash"
    Write-Host "  git remote add origin https://github.com/$UpstreamRepo.git"
    Write-Host "  git fetch origin"
    Write-Host "  exit"
    Write-Host ""
    Write-Host "Then re-run:  .\update_daaf.ps1"
    Wait-AndExit 0
}

# --- Determine upstream remote ---
$UpstreamRemote = "origin"

if ($OriginUrl -notlike "*$UpstreamRepo*") {
    Write-Host "NOTE: Your 'origin' remote points to a fork:"
    Write-Host "  $OriginUrl"
    Write-Host ""

    $upstreamUrl = Invoke-ComposeGit remote get-url upstream

    if ($upstreamUrl) {
        $UpstreamRemote = "upstream"
        Write-Host "Found 'upstream' remote - will check for updates there."
    } else {
        Write-Host "Your installation is connected to a personal copy (fork) of DAAF,"
        Write-Host "not the official release. To also receive official updates, run"
        Write-Host "these commands one at a time:"
        Write-Host ""
        Write-Host "  .\run_daaf.ps1 bash"
        Write-Host "  git remote add upstream https://github.com/$UpstreamRepo.git"
        Write-Host "  git fetch upstream"
        Write-Host "  exit"
        Write-Host ""
        Write-Host "Then re-run:  .\update_daaf.ps1"
        Wait-AndExit 0
    }
    Write-Host ""
}

# =====================================================================
# Ensure fetch refspec covers all branches
# =====================================================================
# git clone --depth 1 -b <ref> implies --single-branch, which locks the
# fetch refspec to only the cloned ref. This means git fetch will never
# retrieve other branches (like main), breaking auto-detect. Widen to
# the standard wildcard if it's currently narrow.
$CurrentRefspec = Invoke-ComposeGit config --get "remote.$UpstreamRemote.fetch"
if ($LASTEXITCODE -eq 0 -and $CurrentRefspec -and
    $CurrentRefspec.Trim() -ne "+refs/heads/*:refs/remotes/$UpstreamRemote/*") {
    Invoke-ComposeGitNull config --replace-all "remote.$UpstreamRemote.fetch" `
        "+refs/heads/*:refs/remotes/$UpstreamRemote/*"
}

# =====================================================================
# Fetch latest
# =====================================================================
Write-Host "Fetching latest changes from $UpstreamRemote..."
# Use direct docker exec instead of Invoke-ComposeGitNull so we can capture stderr
# for diagnostic output on failure (Invoke-ComposeGitNull discards all output).
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$fetchOutput = docker compose exec -T daaf-docker git -C /daaf fetch $UpstreamRemote 2>&1
$fetchExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
if ($fetchExit -ne 0) {
    Write-Host ""
    Write-Host "Failed to fetch from $UpstreamRemote." -ForegroundColor Red
    if ($fetchOutput) {
        Write-Host "  Git reported:" -ForegroundColor Red
        $fetchOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    }
    Write-Host ""
    Write-Host "No changes were made to your installation."
    Write-Host ""
    Write-Host "Common causes:"
    Write-Host "  - No internet connection"
    Write-Host "  - GitHub may be experiencing an outage (check https://www.githubstatus.com)"
    Write-Host "  - Corporate firewall or proxy blocking the connection"
    Write-Host ""
    Write-Host "Once the issue is resolved, re-run:  .\update_daaf.ps1"
    Wait-AndExit 1
}

# --- Unshallow if needed (shallow clones can't compute merge-base) ---
$null = Invoke-ComposeExec test -f /daaf/.git/shallow 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Deepening repository history (installed from a shallow clone)..."
    Invoke-ComposeGitNull fetch --unshallow $UpstreamRemote
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (Already unshallowed or not needed.)"
    }
    Write-Host ""
}

# =====================================================================
# Resolve remote branch
# =====================================================================
$RemoteBranch = if ($env:DAAF_BRANCH) { $env:DAAF_BRANCH } else { "" }

if ($RemoteBranch) {
    # User specified a branch - verify it exists on the remote
    $null = Invoke-ComposeGit rev-parse --verify "$UpstreamRemote/$RemoteBranch"
    if ($LASTEXITCODE -ne 0) {

        # Check if the value is a version tag rather than a branch.
        # Tags live in refs/tags/, not refs/remotes/origin/, so the branch
        # check above correctly fails for them.
        $null = Invoke-ComposeGit rev-parse --verify "refs/tags/$RemoteBranch"
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "'$RemoteBranch' is a version tag, not a branch." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "The updater needs a branch to pull changes from. Tags are fixed"
            Write-Host "snapshots and cannot receive updates."
            Write-Host ""
            Write-Host "To update to the latest release on the main branch:"
            Write-Host "  .\update_daaf.ps1"
            Write-Host "  (without setting `$env:DAAF_BRANCH)"
            Write-Host ""
            Write-Host "To update from a specific branch:"
            Write-Host "  `$env:DAAF_BRANCH = 'dev'; .\update_daaf.ps1"
            Wait-AndExit 1
        }

        Write-Host ""
        Write-Host "The branch '$RemoteBranch' (from DAAF_BRANCH) was not found on" -ForegroundColor Red
        Write-Host "$UpstreamRemote."
        Write-Host ""
        Write-Host "Your installation is unchanged. Double-check the branch name and try"
        Write-Host "again, or omit DAAF_BRANCH to use the default branch."
        Wait-AndExit 1
    }
    Write-Host "Using branch: $RemoteBranch (from DAAF_BRANCH)"
} else {
    # Auto-detect: try main, then master
    $null = Invoke-ComposeGit rev-parse --verify "$UpstreamRemote/main"
    if ($LASTEXITCODE -eq 0) {
        $RemoteBranch = "main"
    } else {
        $null = Invoke-ComposeGit rev-parse --verify "$UpstreamRemote/master"
        if ($LASTEXITCODE -eq 0) {
            $RemoteBranch = "master"
        }
    }
}

if (-not $RemoteBranch) {
    Write-Host ""
    Write-Host "Could not find the update branch on the server." -ForegroundColor Red
    Write-Host "(Looked for 'main' and 'master' on $UpstreamRemote, but neither exists.)"
    Write-Host ""
    Write-Host "Your installation is unchanged. No changes were made."
    Write-Host ""
    Write-Host "This usually means one of:"
    Write-Host "  - The repository was recently restructured and uses a different"
    Write-Host "    default branch name"
    Write-Host "  - The remote URL points to an empty or misconfigured repository"
    Write-Host "  - A network issue caused an incomplete fetch (try re-running)"
    Write-Host ""
    Write-Host "To troubleshoot:"
    Write-Host "  1. Check what branches exist on the remote:"
    Write-Host "       docker compose exec daaf-docker git -C /daaf ls-remote --heads $UpstreamRemote"
    Write-Host "  2. If you see a branch listed, specify it explicitly:"
    Write-Host "       `$env:DAAF_BRANCH = 'branch-name'; .\update_daaf.ps1"
    Write-Host "  3. Verify your remote URL is correct:"
    Write-Host "       docker compose exec daaf-docker git -C /daaf remote -v"
    Write-Host ""
    Write-Host "If this persists, check:"
    Write-Host "  https://github.com/$UpstreamRepo/issues"
    Wait-AndExit 1
}

# =====================================================================
# Check current branch
# =====================================================================
$CurrentBranch = Invoke-ComposeGit branch --show-current

if ([string]::IsNullOrWhiteSpace($CurrentBranch)) {
    Write-Host ""
    Write-Host "Your DAAF installation is not on a named branch right now."
    Write-Host ""
    Write-Host "This can happen after installing from a specific version tag, after"
    Write-Host "a previous update was interrupted, or after running a manual git"
    Write-Host "command inside the container. Not a problem - I'll handle it."
    Write-Host ""

    # Create a branch at the current HEAD to preserve any local commits.
    # Without this, checking out another branch would orphan those commits.
    $PreservedBranch = "local-work-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Write-Host "Creating branch '$PreservedBranch' to preserve your current work..."
    Invoke-ComposeGitNull checkout -b $PreservedBranch
    if ($LASTEXITCODE -eq 0) {
        $CurrentBranch = $PreservedBranch
        Write-Host "Done. Your commits are safe on branch '$PreservedBranch'."
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "Could not create a branch from the current state."
        Write-Host ""
        Write-Host "To fix this manually:"
        Write-Host "  .\run_daaf.ps1 bash"
        Write-Host "  git checkout -b my-work"
        Write-Host "  exit"
        Write-Host ""
        Write-Host "Then re-run:  .\update_daaf.ps1"
        Write-Host ""
        Write-Host "No changes were made. Your research files are not affected."
        Wait-AndExit 1
    }
}

# =====================================================================
# Check if already up to date
# =====================================================================
$Local = Invoke-ComposeGit rev-parse HEAD
$Remote = Invoke-ComposeGit rev-parse "$UpstreamRemote/$RemoteBranch"

$DirtyFiles = Invoke-ComposeGit diff --name-only HEAD

if (($CurrentBranch -eq $RemoteBranch) -and ($Local -eq $Remote) -and `
    [string]::IsNullOrWhiteSpace($DirtyFiles)) {
    Write-Host ""
    Write-Host "Already up to date! Nothing to do."
    Write-Host ""
    # Even with nothing to pull, run the existence-heal sync so host scripts a
    # prior update missed are delivered now. No OldHead -> only tier A runs.
    Sync-HostScript
    Wait-AndExit 0
}

# =====================================================================
# Compute ahead/behind
# =====================================================================
$Ahead = Invoke-ComposeGit rev-list --count "$UpstreamRemote/$RemoteBranch..HEAD"
if (-not $Ahead) { $Ahead = "0" }

$Behind = Invoke-ComposeGit rev-list --count "HEAD..$UpstreamRemote/$RemoteBranch"
if (-not $Behind) { $Behind = "0" }

if ($Behind -ne "0") {
    Write-Host ""
    Write-Host "Updates available: $Behind new commit(s) on $UpstreamRemote/$RemoteBranch."
}

# =====================================================================
# Early exit: no upstream updates for non-default branches
# =====================================================================
if (($CurrentBranch -ne $RemoteBranch) -and ($Behind -eq "0")) {
    Write-Host ""
    Write-Host "Already up to date! Your branch '$CurrentBranch' has all the latest"
    Write-Host "changes from $UpstreamRemote/$RemoteBranch. Nothing to do."
    Write-Host ""
    # Existence-heal sync (tier A only) even when there is nothing new to pull.
    Sync-HostScript
    Wait-AndExit 0
}

# =====================================================================
# Handle non-default branch
# =====================================================================
if ($CurrentBranch -ne $RemoteBranch) {
    Write-Host ""
    Write-Host "You are on branch '$CurrentBranch', not '$RemoteBranch'."
    Write-Host ""
    Write-Host "DAAF updates are published to '$RemoteBranch'. This will pull the"
    Write-Host "latest updates into '$RemoteBranch', then merge them into your branch."
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  1) Update: pull into $RemoteBranch, then merge into '$CurrentBranch'"
    Write-Host "  2) Abort (no changes made)"
    Write-Host ""
    $choice = Read-UserChoice "  Choose [1/2]" @("1", "2")

    if ($choice -eq "2") {
        Write-Host ""
        Write-Host "Aborted. No changes made."
        Wait-AndExit 0
    }

    $Stashed = $false
    if ($DirtyFiles) {
        Write-Host ""
        Write-Host "Setting aside your uncommitted changes for safekeeping..."
        Invoke-ComposeGitVerbose stash push -m "DAAF update backup $Timestamp"
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "ERROR: Could not safely set aside your uncommitted changes." -ForegroundColor Red
            Write-Host ""
            Write-Host "No changes were made - your files are exactly as they were."
            Write-Host ""
            Write-Host "This can happen if there are new files that need to be committed first."
            Write-Host "You can commit your changes, then re-run the updater:"
            Write-Host "  .\run_daaf.ps1 bash"
            Write-Host "  git add -A"
            Write-Host "  git commit -m `"Save my changes before update`""
            Write-Host "  exit"
            Write-Host "  .\update_daaf.ps1"
            Wait-AndExit 1
        }
        $Stashed = $true
    }

    Write-Host "Switching to $RemoteBranch..."
    Invoke-ComposeGitVerbose checkout $RemoteBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Could not switch to the '$RemoteBranch' branch." -ForegroundColor Red
        Write-Host ""
        Write-Host "This is unusual. Your files are unchanged."
        if ($Stashed) {
            Write-Host "Your uncommitted changes are safely saved."
            Write-Host "To restore them: docker compose exec daaf-docker git -C /daaf stash pop"
        }
        Write-Host ""
        Write-Host "Your research files are not affected."
        Wait-AndExit 1
    }

    Write-Host "Pulling updates..."
    Invoke-ComposeGitVerbose pull $UpstreamRemote $RemoteBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Could not download the latest updates." -ForegroundColor Red
        Write-Host ""
        Write-Host "Common causes:"
        Write-Host "  - No internet connection"
        Write-Host "  - GitHub may be down (check https://www.githubstatus.com)"
        Write-Host ""
        Write-Host "To get back to where you were:"
        Write-Host "  docker compose exec daaf-docker git -C /daaf checkout $CurrentBranch"
        if ($Stashed) {
            Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
        }
        Write-Host ""
        Write-Host "Your research files are not affected."
        Wait-AndExit 1
    }

    Write-Host "Switching back to '$CurrentBranch'..."
    Invoke-ComposeGitVerbose checkout $CurrentBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Could not switch back to your '$CurrentBranch' branch." -ForegroundColor Red
        Write-Host ""
        Write-Host "The updates were downloaded successfully, but the script could"
        Write-Host "not return to your branch. Your research files are safe."
        Write-Host ""
        Write-Host "To fix this, enter the container and switch manually:"
        Write-Host "  .\run_daaf.ps1 bash"
        Write-Host "  git checkout $CurrentBranch"
        Write-Host "  exit"
        Write-Host ""
        Write-Host "If that also fails, you can restore to before the update:"
        Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
        if ($Stashed) {
            Write-Host ""
            Write-Host "Your uncommitted changes are still saved. After switching back:"
            Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
        }
        Wait-AndExit 1
    }

    Write-Host "Merging $RemoteBranch into '$CurrentBranch'..."
    Invoke-ComposeGitNull merge $RemoteBranch
    if ($LASTEXITCODE -ne 0) {
        # Call as statement, not expression -- if (-not (Fn)) captures
        # stdout through a pipe, breaking Docker's TTY detection.
        Resolve-Conflict "merge" "merge --abort"
        if (-not $script:ConflictResolved) {
            if ($Stashed) {
                Write-Host ""
                Write-Host "Your uncommitted changes are safely saved and will be"
                Write-Host "restored after conflicts are resolved."
                Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
            }
            Wait-AndExit 1
        }
    }

    if ($Stashed) {
        Write-Host "Restoring your changes..."
        Invoke-ComposeGitNull stash pop
        if ($LASTEXITCODE -ne 0) {
            Resolve-StashConflict
            if ($script:StashConflictResolved) {
                Complete-Update $OldHead
            } else {
                Complete-Update $OldHead "Note: Uncommitted changes still need attention (see above)."
            }
            Wait-AndExit 0
        }
    }

    Complete-Update $OldHead
    Wait-AndExit 0
}

# =====================================================================
# On default branch - local commits
# =====================================================================
if ([int]$Ahead -gt 0) {
    Write-Host ""
    Write-Host "You have $Ahead local commit(s) on $RemoteBranch that aren't in"
    Write-Host "the official DAAF release."
    Write-Host ""
    Write-Host "Your local commits:"
    $logOutput = Invoke-ComposeGit log --oneline "$UpstreamRemote/$RemoteBranch..HEAD"
    $logOutput -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "  $_" } }
    Write-Host ""
    Write-Host "Options:"
    Write-Host ""
    Write-Host "  1) MERGE (recommended)"
    Write-Host "     Combines your changes with the update. Your commits stay as-is."
    Write-Host "     Git creates a merge commit tying both histories together."
    Write-Host ""
    Write-Host "  2) REBASE (cleaner history)"
    Write-Host "     Bundles your local changes into one commit and places it on top"
    Write-Host "     of the latest update. Individual commit messages are combined."
    Write-Host ""
    Write-Host "  3) ABORT (no changes made)"
    Write-Host ""
    $choice = Read-UserChoice "  Choose [1/2/3]" @("1", "2", "3")

    if ($choice -eq "3") {
        Write-Host ""
        Write-Host "Aborted. No changes made."
        Wait-AndExit 0
    }

    $Stashed = $false
    if ($DirtyFiles) {
        Write-Host ""
        Write-Host "Setting aside your uncommitted changes for safekeeping..."
        Invoke-ComposeGitVerbose stash push -m "DAAF update backup $Timestamp"
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "ERROR: Could not safely set aside your uncommitted changes." -ForegroundColor Red
            Write-Host ""
            Write-Host "No changes were made - your files are exactly as they were."
            Write-Host ""
            Write-Host "This can happen if there are new files that need to be committed first."
            Write-Host "You can commit your changes, then re-run the updater:"
            Write-Host "  .\run_daaf.ps1 bash"
            Write-Host "  git add -A"
            Write-Host "  git commit -m `"Save my changes before update`""
            Write-Host "  exit"
            Write-Host "  .\update_daaf.ps1"
            Wait-AndExit 1
        }
        $Stashed = $true
    }

    if ($choice -eq "1") {
        # --- Merge path ---
        Write-Host "Merging upstream updates..."
        Invoke-ComposeGitNull merge "$UpstreamRemote/$RemoteBranch" `
            -m "Merge DAAF upstream updates"
        if ($LASTEXITCODE -ne 0) {
            # Call as statement, not expression -- if (-not (Fn)) captures
            # stdout through a pipe, breaking Docker's TTY detection.
            Resolve-Conflict "merge" "merge --abort"
            if (-not $script:ConflictResolved) {
                if ($Stashed) {
                    Write-Host ""
                    Write-Host "Your uncommitted changes are safely saved and will be"
                    Write-Host "restored after conflicts are resolved."
                    Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
                }
                Wait-AndExit 1
            }
        }
    } else {
        # --- Squash-then-rebase path ---
        Write-Host ""
        Write-Host "Bundling your $Ahead local commit(s) into a single commit..."
        $MergeBase = Invoke-ComposeGit merge-base HEAD "$UpstreamRemote/$RemoteBranch"

        if ([string]::IsNullOrWhiteSpace($MergeBase)) {
            Write-Host ""
            Write-Host "The rebase option is not available for your setup." -ForegroundColor Red
            Write-Host ""
            Write-Host "This happens when your local changes and the update don't share"
            Write-Host "a common starting point. This is unusual but not a problem."
            Write-Host ""
            Write-Host "Re-run the updater and choose option 1 (Merge) instead:"
            Write-Host "  .\update_daaf.ps1"
            if ($Stashed) {
                Write-Host ""
                Write-Host "Your uncommitted changes are safely saved and will be"
                Write-Host "restored automatically when you re-run the updater."
            }
            Wait-AndExit 1
        }

        Invoke-ComposeGitVerbose reset --soft $MergeBase
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "ERROR: The rebase could not proceed - an internal step failed." -ForegroundColor Red
            Write-Host ""
            Write-Host "To restore to your previous state:"
            Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
            if ($Stashed) {
                Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
            }
            Write-Host ""
            Write-Host "Then re-run and try option 1 (Merge) instead:"
            Write-Host "  .\update_daaf.ps1"
            Write-Host ""
            Write-Host "Your research files are not affected."
            Wait-AndExit 1
        }
        Invoke-ComposeGitVerbose commit `
            -m "Local DAAF customizations ($Ahead commits, squashed before update on $Timestamp)"
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "ERROR: Could not bundle your local changes for the rebase." -ForegroundColor Red
            Write-Host ""
            Write-Host "To restore to your previous state:"
            Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
            if ($Stashed) {
                Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
            }
            Write-Host ""
            Write-Host "Then re-run and try option 1 (Merge) instead:"
            Write-Host "  .\update_daaf.ps1"
            Write-Host ""
            Write-Host "Your research files are not affected."
            Wait-AndExit 1
        }

        Write-Host "Rebasing on top of the latest update..."
        Invoke-ComposeGitNull rebase "$UpstreamRemote/$RemoteBranch"
        if ($LASTEXITCODE -ne 0) {
            # Call as statement -- see merge path comment above
            Resolve-Conflict "rebase" "rebase --abort"
            if (-not $script:ConflictResolved) {
                if ($Stashed) {
                    Write-Host ""
                    Write-Host "Your uncommitted changes are safely saved and will be"
                    Write-Host "restored after conflicts are resolved."
                    Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
                }
                Wait-AndExit 1
            }
        }
    }

    # Restore stashed changes
    if ($Stashed) {
        Write-Host "Restoring your changes..."
        Invoke-ComposeGitNull stash pop
        if ($LASTEXITCODE -ne 0) {
            Resolve-StashConflict
            if ($script:StashConflictResolved) {
                if ($choice -eq "1") {
                    Complete-Update $OldHead
                } else {
                    Complete-Update $OldHead "Your local changes have been rebased on top of the update."
                }
            } else {
                if ($choice -eq "1") {
                    Complete-Update $OldHead "Note: Uncommitted changes still need attention (see above)."
                } else {
                    Complete-Update $OldHead "Your commits were rebased. Uncommitted changes still need attention (see above)."
                }
            }
            Wait-AndExit 0
        }
    }

    if ($choice -eq "1") {
        Complete-Update $OldHead
    } else {
        Complete-Update $OldHead "Your local changes have been rebased on top of the update."
    }
    Wait-AndExit 0
}

# =====================================================================
# On default branch, no local commits - uncommitted changes only
# =====================================================================
if ($DirtyFiles) {
    Write-Host ""
    Write-Host "You have uncommitted changes to the following files:"
    $DirtyFiles -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "  $_" } }
    Write-Host ""
    Write-Host "These will be safely set aside during the update, then re-applied."
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  1) Stash changes, update, then re-apply"
    Write-Host "  2) Show what changed first"
    Write-Host "  3) Abort (no changes made)"
    Write-Host ""
    $choice = Read-UserChoice "  Choose [1/2/3]" @("1", "2", "3")

    if ($choice -eq "3") {
        Write-Host ""
        Write-Host "Aborted. No changes made."
        Wait-AndExit 0
    }

    if ($choice -eq "2") {
        Write-Host ""
        Invoke-ComposeExec git -C /daaf diff 2>$null
        Write-Host ""
        Write-Host "Lines starting with + are additions, - are removals."
        Write-Host ""
        Write-Host "Options:"
        Write-Host "  1) Stash changes, update, then re-apply"
        Write-Host "  3) Abort"
        Write-Host ""
        $choice = Read-UserChoice "  Choose [1/3]" @("1", "3")
        if ($choice -eq "3") {
            Write-Host ""
            Write-Host "Aborted. No changes made."
            Wait-AndExit 0
        }
    }

    Write-Host "Setting aside your changes for safekeeping..."
    Invoke-ComposeGitVerbose stash push -m "DAAF update backup $Timestamp"
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Could not safely set aside your uncommitted changes." -ForegroundColor Red
        Write-Host ""
        Write-Host "No changes were made - your files are exactly as they were."
        Write-Host ""
        Write-Host "This can happen if there are new files that need to be committed first."
        Write-Host "You can commit your changes, then re-run the updater:"
        Write-Host "  .\run_daaf.ps1 bash"
        Write-Host "  git add -A"
        Write-Host "  git commit -m `"Save my changes before update`""
        Write-Host "  exit"
        Write-Host "  .\update_daaf.ps1"
        Wait-AndExit 1
    }

    Write-Host "Pulling updates..."
    Invoke-ComposeGitVerbose pull $UpstreamRemote $RemoteBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Could not download the latest updates." -ForegroundColor Red
        Write-Host ""
        Write-Host "Your uncommitted changes are safely saved."
        Write-Host ""
        Write-Host "Common causes:"
        Write-Host "  - No internet connection"
        Write-Host "  - GitHub may be down (check https://www.githubstatus.com)"
        Write-Host ""
        Write-Host "To restore your changes:"
        Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
        Write-Host ""
        Write-Host "Your research files are not affected."
        Wait-AndExit 1
    }

    Write-Host "Re-applying your changes..."
    Invoke-ComposeGitNull stash pop
    if ($LASTEXITCODE -ne 0) {
        Resolve-StashConflict
        if ($script:StashConflictResolved) {
            Complete-Update $OldHead "Your local changes have been re-applied on top of the update."
        } else {
            Complete-Update $OldHead "Note: Uncommitted changes still need attention (see above)."
        }
        Wait-AndExit 0
    }

    Complete-Update $OldHead "Your local changes have been re-applied on top of the update."
    Wait-AndExit 0
}

# =====================================================================
# Cleanest path: on default branch, no local commits, no changes
# =====================================================================
Write-Host ""
Write-Host "Pulling updates..."
Invoke-ComposeGitVerbose pull $UpstreamRemote $RemoteBranch
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Could not download the latest updates." -ForegroundColor Red
    Write-Host ""
    Write-Host "No changes were made to your installation."
    Write-Host "Your research files are not affected."
    Write-Host ""
    Write-Host "Common causes:"
    Write-Host "  - No internet connection"
    Write-Host "  - GitHub may be down (check https://www.githubstatus.com)"
    Write-Host ""
    Write-Host "Once the issue is resolved, re-run:  .\update_daaf.ps1"
    Wait-AndExit 1
}

Complete-Update $OldHead
Wait-AndExit 0
