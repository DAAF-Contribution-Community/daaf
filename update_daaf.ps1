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

$UpstreamRepo = "DAAF-Contribution-Community/daaf"
$ContainerName = "daaf-daaf-docker-1"
$Timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
$BackupBranch = "backup/pre-update-$Timestamp"

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
    $branchExists = docker compose exec -T daaf-docker git -C /daaf rev-parse --verify $BackupBranch 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "A restore point was saved before the update started. To undo"
        Write-Host "any partial changes:"
        Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
        Write-Host ""
    }
    Pause-And-Exit 1
}

# =====================================================================
# Helper functions
# =====================================================================

function Prompt-Choice {
    param(
        [string]$PromptText,
        [string[]]$ValidChoices
    )
    while ($true) {
        $choice = (Read-Host $PromptText).Trim().ToLower()
        if ($ValidChoices -contains $choice) { return $choice }
        Write-Host "  Please enter one of: $($ValidChoices -join ', ')" -ForegroundColor Yellow
    }
}

function Handle-Conflict {
    param(
        [string]$ConflictType,
        [string]$AbortCmd
    )

    $conflictFiles = (docker compose exec -T daaf-docker `
        git -C /daaf diff --name-only --diff-filter=U 2>$null | Out-String).Trim()

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
    Write-Host "Options:"
    Write-Host "  1) Launch Claude Code to help resolve the conflicts"
    Write-Host "     Claude Code can read the files, explain both sides, and walk"
    Write-Host "     you through the resolution interactively."
    Write-Host ""
    Write-Host "  2) Exit and resolve manually"
    Write-Host ""
    $choice = Prompt-Choice "  Choose [1/2]" @("1", "2")

    if ($choice -eq "1") {
        Write-Host ""
        Write-Host "Launching Claude Code inside the container..."
        Write-Host ""
        Write-Host "Copy and paste this prompt to get started:"
        Write-Host ""
        if ($conflictFiles) {
            Write-Host "  User support mode. I just ran the DAAF updater and got"
            Write-Host "  $ConflictType conflicts in:"
            $conflictFiles -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "    $_" } }
            Write-Host "  Please help me resolve them."
        } else {
            Write-Host "  User support mode. I just ran the DAAF updater and got"
            Write-Host "  $ConflictType conflicts. Please help me resolve them."
        }
        Write-Host ""
        Write-Host "IMPORTANT: When Claude Code is done, type /exit to return here."
        Write-Host "The updater still needs to finish a few steps after this."
        Write-Host ""
        docker compose exec -it daaf-docker claude
        Write-Host ""

        $remaining = (docker compose exec -T daaf-docker `
            git -C /daaf diff --name-only --diff-filter=U 2>$null | Out-String).Trim()

        if ([string]::IsNullOrWhiteSpace($remaining)) {
            Write-Host "Conflicts resolved!"
            Write-Host ""
            return $true
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
            return $false
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
        return $false
    }
}

function Sync-HostScripts {
    param([string]$OldHead)

    $newHead = (docker compose exec -T daaf-docker `
        git -C /daaf rev-parse HEAD 2>$null | Out-String).Trim()

    if ($OldHead -eq $newHead) { return }

    $changedScripts = (docker compose exec -T daaf-docker `
        git -C /daaf diff --name-only "$OldHead..$newHead" -- `
        run_daaf.sh run_daaf.ps1 `
        backup_daaf.sh backup_daaf.ps1 `
        rebuild_daaf.sh rebuild_daaf.ps1 `
        update_daaf.sh update_daaf.ps1 `
        view_logs.sh view_logs.ps1 `
        install.sh install.ps1 `
        2>$null | Out-String).Trim()

    if ([string]::IsNullOrWhiteSpace($changedScripts)) { return }

    Write-Host "Syncing updated utility scripts..."
    $changedScripts -split "`n" | ForEach-Object {
        $script = $_.Trim()
        if (-not $script) { return }
        docker cp "${ContainerName}:/daaf/$script" "./$script" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Updated: $script"
        } else {
            Write-Host "  Warning: could not copy $script. You can copy it manually:" -ForegroundColor Yellow
            Write-Host "    docker cp ${ContainerName}:/daaf/$script ./$script" -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

function Check-BuildChanges {
    param([string]$OldHead)

    $newHead = (docker compose exec -T daaf-docker `
        git -C /daaf rev-parse HEAD 2>$null | Out-String).Trim()

    if ($OldHead -eq $newHead) {
        Write-Host "No Dockerfile changes - no container rebuild needed."
        Write-Host ""
        return
    }

    $buildChanges = (docker compose exec -T daaf-docker `
        git -C /daaf diff --name-only "$OldHead..$newHead" -- `
        Dockerfile docker-compose.yml `
        2>$null | Out-String).Trim()

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
    $choice = Prompt-Choice "  Run rebuild now? [y/n]" @("y", "n")

    if ($choice -eq "y") {
        Write-Host ""
        if (Test-Path "rebuild_daaf.ps1") {
            $env:DAAF_NESTED = "1"
            & .\rebuild_daaf.ps1
            Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue
        } else {
            Write-Host "rebuild_daaf.ps1 is not in your daaf-docker folder."
            Write-Host "You can retrieve it from the container and run it:"
            Write-Host "  docker cp ${ContainerName}:/daaf/rebuild_daaf.ps1 .\rebuild_daaf.ps1"
            Write-Host "  .\rebuild_daaf.ps1"
        }
    } else {
        Write-Host ""
        Write-Host "When you're ready to rebuild:"
        Write-Host "  .\rebuild_daaf.ps1"
    }
}

function Finish-Update {
    param(
        [string]$OldHead,
        [string]$ExtraMsg = ""
    )

    Sync-HostScripts $OldHead
    Check-BuildChanges $OldHead

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
    Pause-And-Exit 1
}

# --- Preflight: Docker installed ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from PowerShell." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Pause-And-Exit 1
}

# --- Preflight: Docker running ---
$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
    Pause-And-Exit 1
}

# --- Preflight: Start container if needed ---
$runningCheck = docker compose ps --status running --format '{{.Name}}' 2>$null
$running = ($runningCheck | Out-String) -match "daaf-docker"

if (-not $running) {
    Write-Host "Starting DAAF container..."
    docker compose up -d
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
        Pause-And-Exit 1
    }

    $retries = 0
    $maxRetries = 30
    while ($retries -lt $maxRetries) {
        docker compose exec -T daaf-docker true 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        $retries++
        Start-Sleep -Seconds 2
    }
    if ($retries -ge $maxRetries) {
        Write-Host ""
        Write-Host "ERROR: The DAAF container started but is not responding after 60 seconds." -ForegroundColor Red
        Write-Host ""
        Write-Host "No changes were made to your DAAF installation."
        Write-Host ""
        Write-Host "This can happen if Docker Desktop is under heavy load."
        Write-Host "Try:"
        Write-Host "  1. Restart Docker Desktop"
        Write-Host "  2. Re-run:  .\update_daaf.ps1"
        Pause-And-Exit 1
    }
    Write-Host "Container started."
    Write-Host ""
}

# --- Preflight: DAAF installed ---
docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: DAAF does not appear to be installed in the container." -ForegroundColor Red
    Write-Host "Run the installer first. See:"
    Write-Host "  https://github.com/$UpstreamRepo#quick-start"
    Pause-And-Exit 1
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
    $choice = Prompt-Choice "  Run backup now? [y/n]" @("y", "n")
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
docker compose exec -T daaf-docker git -C /daaf branch $BackupBranch 2>&1 | Out-Null

$OldHead = (docker compose exec -T daaf-docker `
    git -C /daaf rev-parse HEAD 2>$null | Out-String).Trim()

# =====================================================================
# Check git remote
# =====================================================================
$OriginUrl = (docker compose exec -T daaf-docker `
    git -C /daaf remote get-url origin 2>$null | Out-String).Trim()

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
    Pause-And-Exit 0
}

# --- Determine upstream remote ---
$UpstreamRemote = "origin"

if ($OriginUrl -notlike "*$UpstreamRepo*") {
    Write-Host "NOTE: Your 'origin' remote points to a fork:"
    Write-Host "  $OriginUrl"
    Write-Host ""

    $upstreamUrl = (docker compose exec -T daaf-docker `
        git -C /daaf remote get-url upstream 2>$null | Out-String).Trim()

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
        Pause-And-Exit 0
    }
    Write-Host ""
}

# =====================================================================
# Fetch latest
# =====================================================================
Write-Host "Fetching latest changes from $UpstreamRemote..."
docker compose exec -T daaf-docker git -C /daaf fetch $UpstreamRemote 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Failed to fetch from $UpstreamRemote." -ForegroundColor Red
    Write-Host "No changes were made to your installation."
    Write-Host ""
    Write-Host "Common causes:"
    Write-Host "  - No internet connection"
    Write-Host "  - GitHub may be experiencing an outage (check https://www.githubstatus.com)"
    Write-Host "  - Corporate firewall or proxy blocking the connection"
    Write-Host ""
    Write-Host "Once the issue is resolved, re-run:  .\update_daaf.ps1"
    Pause-And-Exit 1
}

# =====================================================================
# Resolve remote branch
# =====================================================================
$RemoteBranch = if ($env:DAAF_BRANCH) { $env:DAAF_BRANCH } else { "" }

if ($RemoteBranch) {
    # User specified a branch - verify it exists on the remote
    $null = docker compose exec -T daaf-docker `
        git -C /daaf rev-parse --verify "$UpstreamRemote/$RemoteBranch" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "The branch '$RemoteBranch' (from DAAF_BRANCH) was not found on" -ForegroundColor Red
        Write-Host "$UpstreamRemote."
        Write-Host ""
        Write-Host "Your installation is unchanged. Double-check the branch name and try"
        Write-Host "again, or omit DAAF_BRANCH to use the default branch."
        Pause-And-Exit 1
    }
    Write-Host "Using branch: $RemoteBranch (from DAAF_BRANCH)"
} else {
    # Auto-detect: try main, then master
    $null = docker compose exec -T daaf-docker `
        git -C /daaf rev-parse --verify "$UpstreamRemote/main" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $RemoteBranch = "main"
    } else {
        $null = docker compose exec -T daaf-docker `
            git -C /daaf rev-parse --verify "$UpstreamRemote/master" 2>&1
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
    Write-Host "This is unusual. Your installation is unchanged."
    Write-Host ""
    Write-Host "You can specify a branch explicitly:"
    Write-Host "  `$env:DAAF_BRANCH = 'your-branch'; .\update_daaf.ps1"
    Write-Host ""
    Write-Host "If this persists, check:"
    Write-Host "  https://github.com/$UpstreamRepo/issues"
    Pause-And-Exit 1
}

# =====================================================================
# Check current branch
# =====================================================================
$CurrentBranch = (docker compose exec -T daaf-docker `
    git -C /daaf branch --show-current 2>$null | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($CurrentBranch)) {
    Write-Host ""
    Write-Host "Your DAAF installation is not on a named branch right now."
    Write-Host ""
    Write-Host "This can happen after a previous update was interrupted or after"
    Write-Host "running a manual git command inside the container. It's not a"
    Write-Host "problem, but the updater needs you on a branch to proceed."
    Write-Host ""
    Write-Host "To fix this:"
    Write-Host "  .\run_daaf.ps1 bash"
    Write-Host "  git checkout $RemoteBranch"
    Write-Host "  exit"
    Write-Host ""
    Write-Host "Then re-run:  .\update_daaf.ps1"
    Write-Host ""
    Write-Host "No changes were made. Your research files are not affected."
    Pause-And-Exit 0
}

# =====================================================================
# Check if already up to date
# =====================================================================
$Local = (docker compose exec -T daaf-docker `
    git -C /daaf rev-parse HEAD 2>$null | Out-String).Trim()
$Remote = (docker compose exec -T daaf-docker `
    git -C /daaf rev-parse "$UpstreamRemote/$RemoteBranch" 2>$null | Out-String).Trim()

$DirtyFiles = (docker compose exec -T daaf-docker `
    git -C /daaf diff --name-only HEAD 2>$null | Out-String).Trim()

if (($CurrentBranch -eq $RemoteBranch) -and ($Local -eq $Remote) -and `
    [string]::IsNullOrWhiteSpace($DirtyFiles)) {
    Write-Host ""
    Write-Host "Already up to date! Nothing to do."
    Write-Host ""
    Pause-And-Exit 0
}

# =====================================================================
# Compute ahead/behind
# =====================================================================
$Ahead = (docker compose exec -T daaf-docker `
    git -C /daaf rev-list --count "$UpstreamRemote/$RemoteBranch..HEAD" `
    2>$null | Out-String).Trim()
if (-not $Ahead) { $Ahead = "0" }

$Behind = (docker compose exec -T daaf-docker `
    git -C /daaf rev-list --count "HEAD..$UpstreamRemote/$RemoteBranch" `
    2>$null | Out-String).Trim()
if (-not $Behind) { $Behind = "0" }

if ($Behind -ne "0") {
    Write-Host ""
    Write-Host "Updates available: $Behind new commit(s) on $UpstreamRemote/$RemoteBranch."
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
    $choice = Prompt-Choice "  Choose [1/2]" @("1", "2")

    if ($choice -eq "2") {
        Write-Host ""
        Write-Host "Aborted. No changes made."
        Pause-And-Exit 0
    }

    $Stashed = $false
    if ($DirtyFiles) {
        Write-Host ""
        Write-Host "Setting aside your uncommitted changes for safekeeping..."
        docker compose exec -T daaf-docker `
            git -C /daaf stash push -m "DAAF update backup $Timestamp"
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
            Pause-And-Exit 1
        }
        $Stashed = $true
    }

    Write-Host "Switching to $RemoteBranch..."
    docker compose exec -T daaf-docker git -C /daaf checkout $RemoteBranch
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
        Pause-And-Exit 1
    }

    Write-Host "Pulling updates..."
    docker compose exec -T daaf-docker `
        git -C /daaf pull $UpstreamRemote $RemoteBranch
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
        Pause-And-Exit 1
    }

    Write-Host "Switching back to '$CurrentBranch'..."
    docker compose exec -T daaf-docker git -C /daaf checkout $CurrentBranch
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
        Pause-And-Exit 1
    }

    Write-Host "Merging $RemoteBranch into '$CurrentBranch'..."
    docker compose exec -T daaf-docker git -C /daaf merge $RemoteBranch 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        if (-not (Handle-Conflict "merge" "merge --abort")) {
            if ($Stashed) {
                Write-Host ""
                Write-Host "Your uncommitted changes are safely saved and will be"
                Write-Host "restored after conflicts are resolved."
                Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
            }
            Pause-And-Exit 1
        }
    }

    if ($Stashed) {
        Write-Host "Restoring your changes..."
        docker compose exec -T daaf-docker git -C /daaf stash pop 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "The framework update was applied successfully!"
            Write-Host ""
            Write-Host "However, some of your uncommitted edits overlap with files that"
            Write-Host "changed in the update. Your edits are NOT lost - they are saved"
            Write-Host "in a temporary holding area."
            Write-Host ""
            Write-Host "The easiest way to resolve this:"
            Write-Host "  1. Launch Claude Code:  .\run_daaf.ps1"
            Write-Host "     Paste: 'User support mode. I have stash conflicts after"
            Write-Host "     a DAAF update. Please help me resolve them.'"
            Write-Host ""
            Write-Host "  2. Or, to discard your uncommitted edits and keep the update"
            Write-Host "     (WARNING - this cannot be undone):"
            Write-Host "       .\run_daaf.ps1 bash"
            Write-Host "       git checkout -- ."
            Write-Host "       git stash drop"
            Write-Host "       exit"
            Write-Host ""
            Finish-Update $OldHead "Note: Uncommitted changes still need to be restored from the stash."
            Pause-And-Exit 0
        }
    }

    Finish-Update $OldHead
    Pause-And-Exit 0
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
    docker compose exec -T daaf-docker `
        git -C /daaf log --oneline "$UpstreamRemote/$RemoteBranch..HEAD" 2>$null `
        | ForEach-Object { Write-Host "  $_" }
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
    $choice = Prompt-Choice "  Choose [1/2/3]" @("1", "2", "3")

    if ($choice -eq "3") {
        Write-Host ""
        Write-Host "Aborted. No changes made."
        Pause-And-Exit 0
    }

    $Stashed = $false
    if ($DirtyFiles) {
        Write-Host ""
        Write-Host "Setting aside your uncommitted changes for safekeeping..."
        docker compose exec -T daaf-docker `
            git -C /daaf stash push -m "DAAF update backup $Timestamp"
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
            Pause-And-Exit 1
        }
        $Stashed = $true
    }

    if ($choice -eq "1") {
        # --- Merge path ---
        Write-Host "Merging upstream updates..."
        docker compose exec -T daaf-docker `
            git -C /daaf merge "$UpstreamRemote/$RemoteBranch" `
            -m "Merge DAAF upstream updates" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            if (-not (Handle-Conflict "merge" "merge --abort")) {
                if ($Stashed) {
                    Write-Host ""
                    Write-Host "Your uncommitted changes are safely saved and will be"
                    Write-Host "restored after conflicts are resolved."
                    Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
                }
                Pause-And-Exit 1
            }
        }
    } else {
        # --- Squash-then-rebase path ---
        Write-Host ""
        Write-Host "Bundling your $Ahead local commit(s) into a single commit..."
        $MergeBase = (docker compose exec -T daaf-docker `
            git -C /daaf merge-base HEAD "$UpstreamRemote/$RemoteBranch" `
            2>$null | Out-String).Trim()

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
            Pause-And-Exit 1
        }

        docker compose exec -T daaf-docker git -C /daaf reset --soft $MergeBase
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
            Pause-And-Exit 1
        }
        docker compose exec -T daaf-docker git -C /daaf commit `
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
            Pause-And-Exit 1
        }

        Write-Host "Rebasing on top of the latest update..."
        docker compose exec -T daaf-docker `
            git -C /daaf rebase "$UpstreamRemote/$RemoteBranch" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            if (-not (Handle-Conflict "rebase" "rebase --abort")) {
                if ($Stashed) {
                    Write-Host ""
                    Write-Host "Your uncommitted changes are safely saved and will be"
                    Write-Host "restored after conflicts are resolved."
                    Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
                }
                Pause-And-Exit 1
            }
        }
    }

    # Restore stashed changes
    if ($Stashed) {
        Write-Host "Restoring your changes..."
        docker compose exec -T daaf-docker git -C /daaf stash pop 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "The framework update was applied successfully!"
            Write-Host ""
            Write-Host "However, some of your uncommitted edits overlap with files that"
            Write-Host "changed in the update. Your edits are NOT lost - they are saved"
            Write-Host "in a temporary holding area."
            Write-Host ""
            Write-Host "The easiest way to resolve this:"
            Write-Host "  1. Launch Claude Code:  .\run_daaf.ps1"
            Write-Host "     Paste: 'User support mode. I have stash conflicts after"
            Write-Host "     a DAAF update. Please help me resolve them.'"
            Write-Host ""
            Write-Host "  2. Or, to discard your uncommitted edits and keep the update"
            Write-Host "     (WARNING - this cannot be undone):"
            Write-Host "       .\run_daaf.ps1 bash"
            Write-Host "       git checkout -- ."
            Write-Host "       git stash drop"
            Write-Host "       exit"
            Write-Host ""
            if ($choice -eq "1") {
                Finish-Update $OldHead "Note: Uncommitted changes still need attention (see above)."
            } else {
                Finish-Update $OldHead "Your commits were rebased. Uncommitted changes still need attention (see above)."
            }
            Pause-And-Exit 0
        }
    }

    if ($choice -eq "1") {
        Finish-Update $OldHead
    } else {
        Finish-Update $OldHead "Your local changes have been rebased on top of the update."
    }
    Pause-And-Exit 0
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
    $choice = Prompt-Choice "  Choose [1/2/3]" @("1", "2", "3")

    if ($choice -eq "3") {
        Write-Host ""
        Write-Host "Aborted. No changes made."
        Pause-And-Exit 0
    }

    if ($choice -eq "2") {
        Write-Host ""
        docker compose exec -T daaf-docker git -C /daaf diff 2>$null
        Write-Host ""
        Write-Host "Lines starting with + are additions, - are removals."
        Write-Host ""
        Write-Host "Options:"
        Write-Host "  1) Stash changes, update, then re-apply"
        Write-Host "  3) Abort"
        Write-Host ""
        $choice = Prompt-Choice "  Choose [1/3]" @("1", "3")
        if ($choice -eq "3") {
            Write-Host ""
            Write-Host "Aborted. No changes made."
            Pause-And-Exit 0
        }
    }

    Write-Host "Setting aside your changes for safekeeping..."
    docker compose exec -T daaf-docker `
        git -C /daaf stash push -m "DAAF update backup $Timestamp"
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
        Pause-And-Exit 1
    }

    Write-Host "Pulling updates..."
    docker compose exec -T daaf-docker `
        git -C /daaf pull $UpstreamRemote $RemoteBranch
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
        Pause-And-Exit 1
    }

    Write-Host "Re-applying your changes..."
    docker compose exec -T daaf-docker git -C /daaf stash pop 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "The framework update was applied successfully!"
        Write-Host ""
        Write-Host "However, some of your uncommitted edits overlap with files that"
        Write-Host "changed in the update. Your edits are NOT lost - they are saved"
        Write-Host "in a temporary holding area."
        Write-Host ""
        Write-Host "Options:"
        Write-Host "  1) Launch Claude Code to help resolve the conflicts"
        Write-Host "  2) Exit and resolve manually"
        Write-Host ""
        $choice = Prompt-Choice "  Choose [1/2]" @("1", "2")

        if ($choice -eq "1") {
            Write-Host ""
            Write-Host "Launching Claude Code inside the container..."
            Write-Host ""
            Write-Host "Copy and paste this prompt to get started:"
            Write-Host ""
            Write-Host "  User support mode. I have stash conflicts after a DAAF"
            Write-Host "  update. Please help me resolve them."
            Write-Host ""
            Write-Host "IMPORTANT: When Claude Code is done, type /exit to return here."
            Write-Host "The updater still needs to finish a few steps after this."
            Write-Host ""
            docker compose exec -it daaf-docker claude
            Write-Host ""

            $remaining = (docker compose exec -T daaf-docker `
                git -C /daaf diff --name-only --diff-filter=U 2>$null | Out-String).Trim()

            if ([string]::IsNullOrWhiteSpace($remaining)) {
                Write-Host "Conflicts resolved!"
                Finish-Update $OldHead "Your local changes have been re-applied on top of the update."
                Pause-And-Exit 0
            } else {
                Write-Host "Some conflicts still remain in these files:"
                $remaining -split "`n" | ForEach-Object { if ($_.Trim()) { Write-Host "  $_" } }
                Write-Host ""
                Write-Host "You can keep working on them - launch Claude Code and pick up"
                Write-Host "where you left off:"
                Write-Host "  .\run_daaf.ps1"
                Write-Host ""
                Write-Host "Or to undo the update entirely (your research files are not affected):"
                Write-Host "  docker compose exec daaf-docker git -C /daaf reset --hard $BackupBranch"
                Write-Host "  docker compose exec daaf-docker git -C /daaf stash pop"
                Pause-And-Exit 1
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
            Pause-And-Exit 1
        }
    }

    Finish-Update $OldHead "Your local changes have been re-applied on top of the update."
    Pause-And-Exit 0
}

# =====================================================================
# Cleanest path: on default branch, no local commits, no changes
# =====================================================================
Write-Host ""
Write-Host "Pulling updates..."
docker compose exec -T daaf-docker `
    git -C /daaf pull $UpstreamRemote $RemoteBranch
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
    Pause-And-Exit 1
}

Finish-Update $OldHead
Pause-And-Exit 0
