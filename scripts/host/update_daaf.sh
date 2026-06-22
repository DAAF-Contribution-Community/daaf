#!/usr/bin/env bash
# ============================================================================
# DAAF Update Script (macOS / Linux)
# ============================================================================
# Usage:
#   cd daaf-docker
#   bash update_daaf.sh
#
#   To update from a specific branch (default: auto-detects main/master):
#   DAAF_BRANCH=dev bash update_daaf.sh
#
# What this script does:
#   1. Optionally backs up your DAAF installation (via backup_daaf.sh)
#   2. Checks for updates and detects your git state
#   3. Walks you through updating safely with options at each step
#   4. Offers Claude Code to help resolve any merge conflicts
#   5. Syncs utility scripts and auto-rebuilds if Docker files changed
#
# This script runs on the host and reaches into the container for git
# operations. It composes the existing backup and rebuild scripts rather
# than reimplementing their logic.
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection
#   - Run from the daaf-docker directory
# ============================================================================

set -euo pipefail

# Interactivity detection: use /dev/tty instead of stdin (fd 0).
# When users run `curl ... | bash`, stdin is the pipe -- but the user's
# terminal is still available at /dev/tty. CI environments lack a real
# terminal entirely.
#
# DAAF_NESTED is separate: it suppresses the exit prompt (so nested
# scripts don't double-pause) but does NOT suppress interactive prompts.
# A nested script can still prompt the user for conflict resolution,
# merge strategy, etc. -- as long as a real terminal is available.
IS_INTERACTIVE=false
if [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    IS_INTERACTIVE=true
fi

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script like migrate_daaf.sh).
if [ "${IS_INTERACTIVE}" = "true" ] && [ -z "${DAAF_NESTED:-}" ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

UPSTREAM_REPO="DAAF-Contribution-Community/daaf"
CONTAINER_NAME="daaf-daaf-docker-1"
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
BACKUP_BRANCH="backup/pre-update-${TIMESTAMP}"

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps"*"--format"*) echo "daaf-docker" ;;
            *"compose exec"*"true"*) return 0 ;;
            *"compose exec"*"test -f"*) return 0 ;;
            *"fetch"*) return 0 ;;
            *"rev-list HEAD..origin"*"--count"*) echo "0" ;;
            *"rev-list"*"--count"*) echo "0" ;;
            *"status --porcelain"*) echo "" ;;
            *"symbolic-ref"*) echo "main" ;;
            *"branch --show-current"*) echo "main" ;;
            *"rev-parse --verify"*"backup/"*) return 1 ;;
            *"rev-parse --verify"*"origin/"*) return 0 ;;
            *"rev-parse"*"origin/main"*) echo "abc123def456" ;;
            *"rev-parse"*"HEAD"*) echo "abc123def456" ;;
            *"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
            *"diff --name-only"*"HEAD"*) echo "" ;;
            *)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
fi

# --- Trap handler for unexpected failures ---
cleanup_on_error() {
    [ -n "${LOCK_DIR:-}" ] && rmdir "$LOCK_DIR" 2>/dev/null || true
    echo "" >&2
    echo "-------------------------------------------" >&2
    echo "  Something went wrong unexpectedly" >&2
    echo "-------------------------------------------" >&2
    echo "" >&2
    echo "Your research files and data are safe -- updates only change" >&2
    echo "framework files, not your research/ folder." >&2
    echo "" >&2
    echo "Most likely causes:" >&2
    echo "  - Docker Desktop stopped (laptop sleep, lid closed)" >&2
    echo "  - Internet connection dropped during download" >&2
    echo "  - A temporary Docker glitch" >&2
    echo "" >&2
    echo "To try again:" >&2
    echo "  1. Make sure Docker Desktop is running" >&2
    echo "  2. Re-run:  bash update_daaf.sh" >&2
    echo "     (It is safe to re-run -- it will pick up where it left off.)" >&2
    echo "" >&2
    if [ "${STASHED:-false}" = true ]; then
        echo "Your uncommitted changes are safely saved in a stash." >&2
        echo "To restore them after fixing the issue:" >&2
        echo "  docker compose exec daaf-docker git -C /daaf stash pop" >&2
        echo "" >&2
    fi
    if docker compose exec -T daaf-docker \
        git -C /daaf rev-parse --verify "${BACKUP_BRANCH}" \
        </dev/null >/dev/null 2>&1; then
        echo "A restore point was saved before the update started. To undo" >&2
        echo "any partial changes:" >&2
        echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}" >&2
        echo "" >&2
    fi
}
trap cleanup_on_error ERR

# =====================================================================
# Helper functions
# =====================================================================

prompt_choice() {
    local prompt_text="$1"
    local valid_choices="$2"
    local choice=""
    # Non-interactive mode: auto-select first valid choice
    if [ "${IS_INTERACTIVE}" != "true" ]; then
        choice=$(echo "${valid_choices}" | awk '{print $1}')
        echo "  (Non-interactive mode -- auto-selecting: ${choice})" >&2
        echo "${choice}"
        return
    fi
    while true; do
        read -r -p "${prompt_text}" choice < /dev/tty
        choice=$(echo "${choice}" | tr '[:upper:]' '[:lower:]')
        if echo "${valid_choices}" | grep -qw "${choice}"; then
            echo "${choice}"
            return
        fi
        echo "  Please enter one of: ${valid_choices}" >&2
    done
}

# Override prompt_choice in dry-run mode (must come after the real definition
# since bash function definitions are global, not block-scoped)
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    prompt_choice() {
        local valid_choices="$2"
        local first_choice
        first_choice=$(echo "${valid_choices}" | awk '{print $1}')
        echo "[DRY-RUN] Auto-selecting: ${first_choice}" >&2
        echo "${first_choice}"
    }
fi

handle_conflict() {
    local conflict_type="$1"
    local abort_cmd="$2"

    local conflict_files
    conflict_files=$(docker compose exec -T daaf-docker \
        git -C /daaf diff --name-only --diff-filter=U </dev/null 2>/dev/null \
        | tr -d '\r' || true)

    echo ""
    echo "-------------------------------------------"
    echo "  Conflict detected"
    echo "-------------------------------------------"
    echo ""
    echo "The same file(s) were changed both in the update and in your local"
    echo "version. Git has marked the conflicting sections with <<<<<<< and"
    echo ">>>>>>> markers."
    echo ""
    if [ -n "${conflict_files}" ]; then
        echo "Conflicting files:"
        echo "${conflict_files}" | sed 's/^/  /'
        echo ""
    fi
    # Claude Code requires an interactive terminal (-it flag). When running
    # non-interactively (e.g., nested from migrate_daaf.sh), skip straight
    # to manual resolution instructions since launching Claude Code would
    # fail with "the input device is not a TTY".
    local choice="2"
    if [ "${IS_INTERACTIVE}" = "true" ]; then
        echo "Options:"
        echo "  1) Launch Claude Code to help resolve the conflicts"
        echo "     Claude Code can read the files, explain both sides, and walk"
        echo "     you through the resolution interactively."
        echo ""
        echo "  2) Exit and resolve manually"
        echo ""
        choice=$(prompt_choice "  Choose [1/2]: " "1 2")
    fi

    if [ "${choice}" = "1" ]; then
        echo ""
        echo "Launching Claude Code inside the container..."
        echo ""
        echo "Copy and paste this prompt to get started:"
        echo ""
        if [ -n "${conflict_files}" ]; then
            echo "  User support mode. I just ran the DAAF updater and got"
            echo "  ${conflict_type} conflicts in these files:"
            echo "${conflict_files}" | sed 's/^/    /'
        else
            echo "  User support mode. I just ran the DAAF updater and got"
            echo "  ${conflict_type} conflicts."
        fi
        echo ""
        echo "  Please help me resolve them. For each conflicting file:"
        echo "  1. Read it and explain what changed on both sides of the"
        echo "     conflict markers (<<<<<<< vs >>>>>>>)"
        echo "  2. Help me decide which version to keep or how to combine them"
        echo "  3. Edit the file to remove all conflict markers"
        echo "  After all files are resolved, commit the result:"
        echo "    git add ."
        if [ "${conflict_type}" = "merge" ]; then
            echo "    git commit -m \"Resolved merge conflicts from DAAF update\""
        else
            echo "    git rebase --continue"
        fi
        echo "  When finished, remind me to type /exit so the updater can"
        echo "  finish its remaining steps."
        echo ""
        echo "IMPORTANT: When Claude Code is done, type /exit to return here."
        echo "The updater still needs to finish a few steps after this."
        echo ""
        # When stdin is a pipe (curl|bash), Docker rejects the -t flag with
        # "the input device is not a TTY". Redirect from /dev/tty on the
        # host side so Docker sees a real TTY and allocates a PTY inside
        # the container.
        if [ -t 0 ]; then
            docker compose exec -it daaf-docker claude || true
        else
            docker compose exec -it daaf-docker claude < /dev/tty || true
        fi
        echo ""

        local remaining
        remaining=$(docker compose exec -T daaf-docker \
            git -C /daaf diff --name-only --diff-filter=U </dev/null 2>/dev/null \
            | tr -d '\r' || true)

        if [ -z "${remaining}" ]; then
            echo "Conflicts resolved!"
            echo ""
            return 0
        else
            echo "Some conflicts still remain in these files:"
            echo "${remaining}" | sed 's/^/  /'
            echo ""
            echo "You can keep working on them -- launch Claude Code and pick up"
            echo "where you left off:"
            echo "  bash run_daaf.sh"
            echo ""
            echo "Or to undo the update entirely (your research files are not affected):"
            echo "  docker compose exec daaf-docker git -C /daaf ${abort_cmd}"
            echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}"
            return 1
        fi
    else
        echo ""
        echo "To resolve the conflicts manually, enter the container:"
        echo "  bash run_daaf.sh bash"
        echo ""
        echo "Conflicting files contain markers that look like:"
        echo "  <<<<<<< HEAD"
        echo "  (your version)"
        echo "  ======="
        echo "  (the update's version)"
        echo "  >>>>>>>"
        echo "Edit each file to keep the version you want, removing all markers."
        echo ""
        if [ "${conflict_type}" = "merge" ]; then
            echo "After resolving all files (inside the container):"
            echo "  git add ."
            echo "  git commit -m \"Resolved merge conflicts\""
            echo "  exit"
        else
            echo "After resolving all files (inside the container):"
            echo "  git add ."
            echo "  git rebase --continue"
            echo "  exit"
        fi
        echo ""
        echo "To undo the update instead (run from your host terminal):"
        echo "  docker compose exec daaf-docker git -C /daaf ${abort_cmd}"
        echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}"
        return 1
    fi
}

handle_stash_conflict() {
    echo ""
    echo "The framework update was applied successfully!"
    echo ""
    echo "However, some of your uncommitted edits overlap with files that"
    echo "changed in the update. Your edits are NOT lost -- they are saved"
    echo "in a temporary holding area."
    echo ""
    # Claude Code requires an interactive terminal. When non-interactive,
    # skip straight to manual resolution instructions.
    local choice="2"
    if [ "${IS_INTERACTIVE}" = "true" ]; then
        echo "Options:"
        echo "  1) Launch Claude Code to help resolve the conflicts"
        echo "  2) Exit and resolve manually"
        echo ""
        choice=$(prompt_choice "  Choose [1/2]: " "1 2")
    fi

    if [ "${choice}" = "1" ]; then
        echo ""
        echo "Launching Claude Code inside the container..."
        echo ""
        echo "Copy and paste this prompt to get started:"
        echo ""
        echo "  User support mode. The DAAF updater applied the framework"
        echo "  update successfully, but re-applying my uncommitted changes"
        echo "  caused stash conflicts. Please help me resolve them:"
        echo "  1. Run git status to find the conflicting files"
        echo "  2. Read each one and explain both sides of the conflict"
        echo "  3. Help me choose what to keep and edit the file to resolve it"
        echo "  4. After all conflicts are resolved, run: git add ."
        echo "     Then: git stash drop"
        echo "     Then: git commit -m 'Resolved stash conflicts from DAAF update'"
        echo "  When done, remind me to type /exit so the updater can"
        echo "  finish its remaining steps."
        echo ""
        echo "IMPORTANT: When Claude Code is done, type /exit to return here."
        echo "The updater still needs to finish a few steps after this."
        echo ""
        if [ -t 0 ]; then
            docker compose exec -it daaf-docker claude || true
        else
            docker compose exec -it daaf-docker claude < /dev/tty || true
        fi
        echo ""

        local remaining
        remaining=$(docker compose exec -T daaf-docker \
            git -C /daaf diff --name-only --diff-filter=U </dev/null 2>/dev/null \
            | tr -d '\r' || true)

        if [ -z "${remaining}" ]; then
            echo "Conflicts resolved!"
            return 0
        else
            echo "Some conflicts still remain in these files:"
            echo "${remaining}" | sed 's/^/  /'
            echo ""
            echo "You can keep working on them -- launch Claude Code:"
            echo "  bash run_daaf.sh"
            echo ""
            echo "Or to undo the update:"
            echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}"
            echo "  docker compose exec daaf-docker git -C /daaf stash pop"
            return 1
        fi
    else
        echo ""
        echo "To resolve, enter the container:"
        echo "  bash run_daaf.sh bash"
        echo "  (edit the conflicting files to remove the <<<<<<< markers)"
        echo "  git add ."
        echo "  git stash drop"
        echo "  exit"
        echo ""
        echo "Or to discard your uncommitted edits and keep the update"
        echo "(WARNING -- this cannot be undone):"
        echo "  bash run_daaf.sh bash"
        echo "  git checkout -- ."
        echo "  git stash drop"
        echo "  exit"
        echo ""
        echo "To undo the entire update:"
        echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}"
        echo "  docker compose exec daaf-docker git -C /daaf stash pop"
        return 1
    fi
}

sync_host_scripts() {
    local old_head="$1"

    local new_head
    new_head=$(docker compose exec -T daaf-docker \
        git -C /daaf rev-parse HEAD </dev/null 2>/dev/null | tr -d '\r')

    if [ "${old_head}" = "${new_head}" ]; then
        return
    fi

    local changed_scripts
    # Only sync platform-appropriate scripts (.sh on Unix) and shared files.
    # Excludes install.sh (not needed post-install) and all .ps1 files.
    changed_scripts=$(docker compose exec -T daaf-docker \
        git -C /daaf diff --name-only "${old_head}..${new_head}" -- \
        scripts/host/daaf.sh \
        scripts/host/daaf_lib.sh \
        scripts/host/run_daaf.sh \
        scripts/host/backup_daaf.sh \
        scripts/host/restore_from_backup.sh \
        scripts/host/rebuild_daaf.sh \
        scripts/host/update_daaf.sh \
        scripts/host/view_logs.sh \
        scripts/host/view_notebooks.sh \
        scripts/host/run_vscode.sh \
        scripts/host/environment_settings_example.txt \
        </dev/null 2>/dev/null | tr -d '\r' || true)

    if [ -z "${changed_scripts}" ]; then
        return
    fi

    echo "Syncing updated utility scripts..."
    while IFS= read -r repo_path; do
        [ -z "${repo_path}" ] && continue
        local script
        script=$(basename "${repo_path}")
        if docker cp "${CONTAINER_NAME}:/daaf/${repo_path}" "./${script}" 2>/dev/null; then
            chmod +x "./${script}" 2>/dev/null || true
            echo "  Updated: ${script}"
        else
            echo "  Warning: could not copy ${script}. You can copy it manually:"
            echo "    docker cp ${CONTAINER_NAME}:/daaf/${repo_path} ./${script}"
        fi
    done <<< "${changed_scripts}"
    echo ""
}

check_build_changes() {
    local old_head="$1"

    local new_head
    new_head=$(docker compose exec -T daaf-docker \
        git -C /daaf rev-parse HEAD </dev/null 2>/dev/null | tr -d '\r')

    if [ "${old_head}" = "${new_head}" ]; then
        echo "No Dockerfile changes -- no container rebuild needed."
        echo ""
        return
    fi

    local build_changes
    build_changes=$(docker compose exec -T daaf-docker \
        git -C /daaf diff --name-only "${old_head}..${new_head}" -- \
        Dockerfile docker-compose.yml \
        </dev/null 2>/dev/null | tr -d '\r' || true)

    if [ -z "${build_changes}" ]; then
        echo "No Dockerfile changes -- no container rebuild needed."
        echo ""
        return
    fi

    echo ""
    echo "Build files were updated in this release:"
    echo "${build_changes}" | sed 's/^/  /'
    echo ""
    echo "A rebuild is needed for these changes to take full effect."
    echo ""
    local choice
    choice=$(prompt_choice "  Run rebuild now? [y/n]: " "y n")

    if [ "${choice}" = "y" ]; then
        echo ""
        if [ -f "rebuild_daaf.sh" ]; then
            DAAF_NESTED=1 bash rebuild_daaf.sh
        else
            echo "rebuild_daaf.sh is not in your daaf-docker folder."
            echo "You can retrieve it from the container and run it:"
            echo "  docker cp ${CONTAINER_NAME}:/daaf/scripts/host/rebuild_daaf.sh ./rebuild_daaf.sh"
            echo "  chmod +x ./rebuild_daaf.sh"
            echo "  bash rebuild_daaf.sh"
        fi
    else
        echo ""
        echo "When you're ready to rebuild:"
        echo "  bash rebuild_daaf.sh"
    fi
}

finish_update() {
    local old_head="$1"
    local extra_msg="${2:-}"

    sync_host_scripts "${old_head}"
    check_build_changes "${old_head}"

    echo ""
    echo "=========================================="
    echo "  Update complete!"
    echo "=========================================="
    echo ""
    if [ -n "${extra_msg}" ]; then
        echo "${extra_msg}"
        echo ""
    fi
    echo "If you need to undo this update later:"
    echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}"
    echo ""
    echo "  (This reverts DAAF's framework files to how they were before the"
    echo "   update. Your research projects and data are not affected.)"
    echo ""
    echo "  To launch DAAF:"
    echo "    bash run_daaf.sh"
    echo ""
}

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/update_daaf.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# =====================================================================
# Portable concurrent-run lock (mkdir)
# =====================================================================
# Prevent two simultaneous update_daaf runs from corrupting git state
# (double-stash, conflicting merges, backup branch pointing to wrong commit).
# mkdir is atomic on all POSIX systems (Linux, macOS, Git Bash on Windows).
# The lock directory is cleaned up via the EXIT trap when the script exits,
# including exits via the ERR trap.
LOCK_DIR="/tmp/daaf-update.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "ERROR: Another instance of update_daaf is already running." >&2
    echo "       If you believe this is stale, remove: $LOCK_DIR" >&2
    exit 1
fi
_daaf_prior_exit_trap=$(trap -p EXIT | sed -n "s/^trap -- '\\(.*\\)' EXIT$/\\1/p")
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true; '"$_daaf_prior_exit_trap" EXIT

# =====================================================================
# Main script
# =====================================================================

echo ""
echo "=========================================="
echo "  DAAF Updater"
echo "=========================================="
echo ""
echo "Tip: If Claude Code is running inside the container, exit it first"
echo "(/exit) to avoid file conflicts during the update."
echo ""

# --- Preflight: docker-compose.yml ---
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found in the current directory."
    echo ""
    echo "This script must be run from your daaf-docker folder. Try:"
    echo "  cd ~/daaf-docker"
    echo "  bash update_daaf.sh"
    echo ""
    echo "If you installed DAAF somewhere else, cd to that folder first."
    exit 1
fi

# --- Preflight: Docker installed ---
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal."
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# --- Preflight: Docker running ---
if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start it and try again."
    exit 1
fi

# --- Preflight: Start container if needed ---
RUNNING=$(docker compose ps --status running --format '{{.Name}}' 2>/dev/null \
    | grep -c "daaf-docker" || true)

if [ "${RUNNING}" -eq 0 ]; then
    echo "Starting DAAF container..."
    if ! docker compose up -d; then
        echo "ERROR: Failed to start the DAAF container."
        echo ""
        echo "No changes were made to your installation."
        echo ""
        echo "Common causes:"
        echo "  - Another program is using the same ports"
        echo "  - Docker Desktop needs more memory (Settings > Resources)"
        echo ""
        echo "Try restarting Docker Desktop, then:  bash update_daaf.sh"
        exit 1
    fi

    RETRIES=0
    MAX_RETRIES=30
    READY_LOG=$(mktemp)
    until docker compose exec -T daaf-docker true </dev/null 2>>"$READY_LOG"; do
        RETRIES=$((RETRIES + 1))
        if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
            echo "ERROR: The DAAF container started but is not responding after 60 seconds." >&2
            if [ -s "$READY_LOG" ]; then
                echo "  Docker reported:" >&2
                tail -5 "$READY_LOG" | sed 's/^/    /' >&2
                echo "" >&2
            fi
            echo "No changes were made to your DAAF installation." >&2
            echo "" >&2
            echo "This can happen if Docker Desktop is under heavy load." >&2
            echo "Try:" >&2
            echo "  1. Restart Docker Desktop" >&2
            echo "  2. Re-run:  bash update_daaf.sh" >&2
            rm -f "$READY_LOG"
            exit 1
        fi
        sleep 2
    done
    rm -f "$READY_LOG"
    echo "Container started."
    echo ""
fi

# --- Preflight: DAAF installed ---
if ! docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md </dev/null 2>/dev/null; then
    echo "ERROR: DAAF does not appear to be installed in the container."
    echo "Run the installer first. See:"
    echo "  https://github.com/${UPSTREAM_REPO}#quick-start"
    exit 1
fi

# =====================================================================
# Offer backup
# =====================================================================
echo "-------------------------------------------"
echo "  Backup recommendation"
echo "-------------------------------------------"
echo ""
echo "It's a good idea to back up before updating, especially if you have"
echo "research projects or local customizations you want to protect."
echo ""
if [ -f "backup_daaf.sh" ]; then
    CHOICE=$(prompt_choice "  Run backup now? [y/n]: " "y n")
    if [ "${CHOICE}" = "y" ]; then
        echo ""
        DAAF_NESTED=1 bash backup_daaf.sh
        echo ""
    fi
else
    echo "  (backup_daaf.sh not found in this directory -- skipping)"
    echo ""
fi

# =====================================================================
# Create git backup branch (lightweight restore point)
# =====================================================================
docker compose exec -T daaf-docker \
    git -C /daaf branch "${BACKUP_BRANCH}" </dev/null 2>/dev/null || true

OLD_HEAD=$(docker compose exec -T daaf-docker \
    git -C /daaf rev-parse HEAD </dev/null 2>/dev/null | tr -d '\r')

# =====================================================================
# Check git remote
# =====================================================================
ORIGIN_URL=$(docker compose exec -T daaf-docker \
    git -C /daaf remote get-url origin </dev/null 2>/dev/null | tr -d '\r' || true)

if [ -z "${ORIGIN_URL}" ]; then
    echo ""
    echo "Your DAAF installation is not connected to the update server."
    echo ""
    echo "This usually means DAAF was installed from a downloaded zip file"
    echo "instead of using the installer script. To connect it for updates,"
    echo "run these commands one at a time:"
    echo ""
    echo "  bash run_daaf.sh bash"
    echo "  git remote add origin https://github.com/${UPSTREAM_REPO}.git"
    echo "  git fetch origin"
    echo "  exit"
    echo ""
    echo "Then re-run:  bash update_daaf.sh"
    exit 0
fi

# --- Determine upstream remote ---
UPSTREAM_REMOTE="origin"

if ! echo "${ORIGIN_URL}" | grep -qi "${UPSTREAM_REPO}"; then
    echo "NOTE: Your 'origin' remote points to a fork:"
    echo "  ${ORIGIN_URL}"
    echo ""

    UPSTREAM_URL=$(docker compose exec -T daaf-docker \
        git -C /daaf remote get-url upstream </dev/null 2>/dev/null | tr -d '\r' || true)

    if [ -n "${UPSTREAM_URL}" ]; then
        UPSTREAM_REMOTE="upstream"
        echo "Found 'upstream' remote -- will check for updates there."
    else
        echo "Your installation is connected to a personal copy (fork) of DAAF,"
        echo "not the official release. To also receive official updates, run"
        echo "these commands one at a time:"
        echo ""
        echo "  bash run_daaf.sh bash"
        echo "  git remote add upstream https://github.com/${UPSTREAM_REPO}.git"
        echo "  git fetch upstream"
        echo "  exit"
        echo ""
        echo "Then re-run:  bash update_daaf.sh"
        exit 0
    fi
    echo ""
fi

# =====================================================================
# Ensure fetch refspec covers all branches
# =====================================================================
# git clone --depth 1 -b <ref> implies --single-branch, which locks the
# fetch refspec to only the cloned ref. This means git fetch will never
# retrieve other branches (like main), breaking auto-detect. Widen to
# the standard wildcard if it's currently narrow.
CURRENT_REFSPEC=$(docker compose exec -T daaf-docker \
    git -C /daaf config --get remote."${UPSTREAM_REMOTE}".fetch \
    </dev/null 2>/dev/null | tr -d '\r' || true)

if [ -n "${CURRENT_REFSPEC}" ] \
    && [ "${CURRENT_REFSPEC}" != "+refs/heads/*:refs/remotes/${UPSTREAM_REMOTE}/*" ]; then
    docker compose exec -T daaf-docker \
        git -C /daaf config --replace-all remote."${UPSTREAM_REMOTE}".fetch \
        "+refs/heads/*:refs/remotes/${UPSTREAM_REMOTE}/*" </dev/null 2>/dev/null \
        || true
fi

# =====================================================================
# Fetch latest
# =====================================================================
echo "Fetching latest changes from ${UPSTREAM_REMOTE}..."
if ! docker compose exec -T daaf-docker \
    git -C /daaf fetch "${UPSTREAM_REMOTE}" </dev/null; then
    echo ""
    echo "Failed to fetch from ${UPSTREAM_REMOTE}."
    echo "No changes were made to your installation."
    echo ""
    echo "Common causes:"
    echo "  - No internet connection"
    echo "  - GitHub may be experiencing an outage (check https://www.githubstatus.com)"
    echo "  - Corporate firewall or proxy blocking the connection"
    echo ""
    echo "Once the issue is resolved, re-run:  bash update_daaf.sh"
    exit 1
fi

# --- Unshallow if needed (shallow clones can't compute merge-base) ---
if docker compose exec -T daaf-docker \
    test -f /daaf/.git/shallow </dev/null 2>/dev/null; then
    echo "Deepening repository history (installed from a shallow clone)..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf fetch --unshallow "${UPSTREAM_REMOTE}" </dev/null 2>/dev/null; then
        echo "  (Already unshallowed or not needed.)"
    fi
    echo ""
fi

# =====================================================================
# Resolve remote branch
# =====================================================================
REMOTE_BRANCH="${DAAF_BRANCH:-}"

if [ -n "${REMOTE_BRANCH}" ]; then
    # User specified a branch -- verify it exists on the remote
    if ! docker compose exec -T daaf-docker \
        git -C /daaf rev-parse --verify "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" \
        </dev/null >/dev/null 2>&1; then

        # Check if the value is a version tag rather than a branch.
        # Tags live in refs/tags/, not refs/remotes/origin/, so the branch
        # check above correctly fails for them.
        if docker compose exec -T daaf-docker \
            git -C /daaf rev-parse --verify "refs/tags/${REMOTE_BRANCH}" \
            </dev/null >/dev/null 2>&1; then
            echo ""
            echo "'${REMOTE_BRANCH}' is a version tag, not a branch."
            echo ""
            echo "The updater needs a branch to pull changes from. Tags are fixed"
            echo "snapshots and cannot receive updates."
            echo ""
            echo "To update to the latest release on the main branch:"
            echo "  bash update_daaf.sh"
            echo "  (without setting DAAF_BRANCH)"
            echo ""
            echo "To update from a specific branch:"
            echo "  DAAF_BRANCH=dev bash update_daaf.sh"
            exit 1
        fi

        echo ""
        echo "The branch '${REMOTE_BRANCH}' (from DAAF_BRANCH) was not found on"
        echo "${UPSTREAM_REMOTE}."
        echo ""
        echo "Your installation is unchanged. Double-check the branch name and try"
        echo "again, or omit DAAF_BRANCH to use the default branch."
        exit 1
    fi
    echo "Using branch: ${REMOTE_BRANCH} (from DAAF_BRANCH)"
else
    # Auto-detect: try main, then master
    if docker compose exec -T daaf-docker \
        git -C /daaf rev-parse --verify "${UPSTREAM_REMOTE}/main" \
        </dev/null >/dev/null 2>&1; then
        REMOTE_BRANCH="main"
    elif docker compose exec -T daaf-docker \
        git -C /daaf rev-parse --verify "${UPSTREAM_REMOTE}/master" \
        </dev/null >/dev/null 2>&1; then
        REMOTE_BRANCH="master"
    fi
fi

if [ -z "${REMOTE_BRANCH}" ]; then
    echo ""
    echo "Could not find the update branch on the server."
    echo "(Looked for 'main' and 'master' on ${UPSTREAM_REMOTE}, but neither exists.)"
    echo ""
    echo "Your installation is unchanged. No changes were made."
    echo ""
    echo "This usually means one of:"
    echo "  - The repository was recently restructured and uses a different"
    echo "    default branch name"
    echo "  - The remote URL points to an empty or misconfigured repository"
    echo "  - A network issue caused an incomplete fetch (try re-running)"
    echo ""
    echo "To troubleshoot:"
    echo "  1. Check what branches exist on the remote:"
    echo "       docker compose exec daaf-docker git -C /daaf ls-remote --heads ${UPSTREAM_REMOTE}"
    echo "  2. If you see a branch listed, specify it explicitly:"
    echo "       DAAF_BRANCH=branch-name bash update_daaf.sh"
    echo "  3. Verify your remote URL is correct:"
    echo "       docker compose exec daaf-docker git -C /daaf remote -v"
    echo ""
    echo "If this persists, check:"
    echo "  https://github.com/${UPSTREAM_REPO}/issues"
    exit 1
fi

# =====================================================================
# Check current branch
# =====================================================================
CURRENT_BRANCH=$(docker compose exec -T daaf-docker \
    git -C /daaf branch --show-current </dev/null 2>/dev/null | tr -d '\r')

if [ -z "${CURRENT_BRANCH}" ]; then
    echo ""
    echo "Your DAAF installation is not on a named branch right now."
    echo ""
    echo "This can happen after installing from a specific version tag, after"
    echo "a previous update was interrupted, or after running a manual git"
    echo "command inside the container. Not a problem -- I'll handle it."
    echo ""

    # Create a branch at the current HEAD to preserve any local commits.
    # Without this, checking out another branch would orphan those commits.
    PRESERVED_BRANCH="local-work-$(date +%Y%m%d-%H%M%S)"
    echo "Creating branch '${PRESERVED_BRANCH}' to preserve your current work..."
    if docker compose exec -T daaf-docker \
        git -C /daaf checkout -b "${PRESERVED_BRANCH}" </dev/null 2>/dev/null; then
        CURRENT_BRANCH="${PRESERVED_BRANCH}"
        echo "Done. Your commits are safe on branch '${PRESERVED_BRANCH}'."
        echo ""
    else
        echo ""
        echo "Could not create a branch from the current state."
        echo ""
        echo "To fix this manually:"
        echo "  bash run_daaf.sh bash"
        echo "  git checkout -b my-work"
        echo "  exit"
        echo ""
        echo "Then re-run:  bash update_daaf.sh"
        echo ""
        echo "No changes were made. Your research files are not affected."
        exit 1
    fi
fi

# =====================================================================
# Check if already up to date
# =====================================================================
LOCAL=$(docker compose exec -T daaf-docker \
    git -C /daaf rev-parse HEAD </dev/null 2>/dev/null | tr -d '\r')
REMOTE=$(docker compose exec -T daaf-docker \
    git -C /daaf rev-parse "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" \
    </dev/null 2>/dev/null | tr -d '\r')

DIRTY_FILES=$(docker compose exec -T daaf-docker \
    git -C /daaf diff --name-only HEAD </dev/null 2>/dev/null | tr -d '\r' || true)

if [ "${CURRENT_BRANCH}" = "${REMOTE_BRANCH}" ] \
    && [ "${LOCAL}" = "${REMOTE}" ] \
    && [ -z "${DIRTY_FILES}" ]; then
    echo ""
    echo "Already up to date! Nothing to do."
    echo ""
    exit 0
fi

# =====================================================================
# Compute ahead/behind
# =====================================================================
AHEAD=$(docker compose exec -T daaf-docker \
    git -C /daaf rev-list --count "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}..HEAD" \
    </dev/null 2>/dev/null | tr -d '\r' || echo "0")
BEHIND=$(docker compose exec -T daaf-docker \
    git -C /daaf rev-list --count "HEAD..${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" \
    </dev/null 2>/dev/null | tr -d '\r' || echo "0")

if [ "${BEHIND}" != "0" ]; then
    echo ""
    echo "Updates available: ${BEHIND} new commit(s) on ${UPSTREAM_REMOTE}/${REMOTE_BRANCH}."
fi

# =====================================================================
# Early exit: no upstream updates for non-default branches
# =====================================================================
if [ "${CURRENT_BRANCH}" != "${REMOTE_BRANCH}" ] && [ "${BEHIND}" = "0" ]; then
    echo ""
    echo "Already up to date! Your branch '${CURRENT_BRANCH}' has all the latest"
    echo "changes from ${UPSTREAM_REMOTE}/${REMOTE_BRANCH}. Nothing to do."
    echo ""
    exit 0
fi

# =====================================================================
# Handle non-default branch
# =====================================================================
if [ "${CURRENT_BRANCH}" != "${REMOTE_BRANCH}" ]; then
    echo ""
    echo "You are on branch '${CURRENT_BRANCH}', not '${REMOTE_BRANCH}'."
    echo ""
    echo "DAAF updates are published to '${REMOTE_BRANCH}'. This will pull the"
    echo "latest updates into '${REMOTE_BRANCH}', then merge them into your branch."
    echo ""
    echo "Options:"
    echo "  1) Update: pull into ${REMOTE_BRANCH}, then merge into '${CURRENT_BRANCH}'"
    echo "  2) Abort (no changes made)"
    echo ""
    CHOICE=$(prompt_choice "  Choose [1/2]: " "1 2")

    if [ "${CHOICE}" = "2" ]; then
        echo ""
        echo "Aborted. No changes made."
        exit 0
    fi

    STASHED=false
    if [ -n "${DIRTY_FILES}" ]; then
        echo ""
        echo "Setting aside your uncommitted changes for safekeeping..."
        if ! docker compose exec -T daaf-docker \
            git -C /daaf stash push -m "DAAF update backup ${TIMESTAMP}" </dev/null; then
            echo ""
            echo "ERROR: Could not safely set aside your uncommitted changes."
            echo ""
            echo "No changes were made -- your files are exactly as they were."
            echo ""
            echo "This can happen if there are new files that need to be committed first."
            echo "You can commit your changes, then re-run the updater:"
            echo "  bash run_daaf.sh bash"
            echo "  git add -A"
            echo "  git commit -m \"Save my changes before update\""
            echo "  exit"
            echo "  bash update_daaf.sh"
            exit 1
        fi
        STASHED=true
    fi

    echo "Switching to ${REMOTE_BRANCH}..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf checkout "${REMOTE_BRANCH}" </dev/null; then
        echo ""
        echo "ERROR: Could not switch to the '${REMOTE_BRANCH}' branch."
        echo ""
        echo "This is unusual. Your files are unchanged."
        if [ "${STASHED}" = true ]; then
            echo "Your uncommitted changes are safely saved."
            echo "To restore them: docker compose exec daaf-docker git -C /daaf stash pop"
        fi
        echo ""
        echo "Your research files are not affected."
        exit 1
    fi

    echo "Pulling updates..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf pull "${UPSTREAM_REMOTE}" "${REMOTE_BRANCH}" </dev/null; then
        echo ""
        echo "ERROR: Could not download the latest updates."
        echo ""
        echo "Common causes:"
        echo "  - No internet connection"
        echo "  - GitHub may be down (check https://www.githubstatus.com)"
        echo ""
        echo "To get back to where you were:"
        echo "  docker compose exec daaf-docker git -C /daaf checkout ${CURRENT_BRANCH}"
        if [ "${STASHED}" = true ]; then
            echo "  docker compose exec daaf-docker git -C /daaf stash pop"
        fi
        echo ""
        echo "Your research files are not affected."
        exit 1
    fi

    echo "Switching back to '${CURRENT_BRANCH}'..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf checkout "${CURRENT_BRANCH}" </dev/null; then
        echo ""
        echo "ERROR: Could not switch back to your '${CURRENT_BRANCH}' branch."
        echo ""
        echo "The updates were downloaded successfully, but the script could"
        echo "not return to your branch. Your research files are safe."
        echo ""
        echo "To fix this, enter the container and switch manually:"
        echo "  bash run_daaf.sh bash"
        echo "  git checkout ${CURRENT_BRANCH}"
        echo "  exit"
        echo ""
        echo "If that also fails, you can restore to before the update:"
        echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}"
        if [ "${STASHED}" = true ]; then
            echo ""
            echo "Your uncommitted changes are still saved. After switching back:"
            echo "  docker compose exec daaf-docker git -C /daaf stash pop"
        fi
        exit 1
    fi

    echo "Merging ${REMOTE_BRANCH} into '${CURRENT_BRANCH}'..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf merge "${REMOTE_BRANCH}" </dev/null; then
        if ! handle_conflict "merge" "merge --abort"; then
            if [ "${STASHED}" = true ]; then
                echo ""
                echo "Your uncommitted changes are safely saved and will be"
                echo "restored after conflicts are resolved."
                echo "  docker compose exec daaf-docker git -C /daaf stash pop"
            fi
            exit 1
        fi
    fi

    if [ "${STASHED}" = true ]; then
        echo "Restoring your changes..."
        if ! docker compose exec -T daaf-docker \
            git -C /daaf stash pop </dev/null; then
            if handle_stash_conflict; then
                finish_update "${OLD_HEAD}"
            else
                finish_update "${OLD_HEAD}" \
                    "Note: Uncommitted changes still need attention (see above)."
            fi
            exit 0
        fi
    fi

    finish_update "${OLD_HEAD}"
    exit 0
fi

# =====================================================================
# On default branch -- local commits
# =====================================================================
if [ "${AHEAD}" -gt 0 ]; then
    echo ""
    echo "You have ${AHEAD} local commit(s) on ${REMOTE_BRANCH} that aren't in"
    echo "the official DAAF release."
    echo ""
    echo "Your local commits:"
    docker compose exec -T daaf-docker \
        git -C /daaf log --oneline "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}..HEAD" \
        </dev/null | tr -d '\r' | sed 's/^/  /'
    echo ""
    echo "Options:"
    echo ""
    echo "  1) MERGE (recommended)"
    echo "     Combines your changes with the update. Your commits stay as-is."
    echo "     Git creates a merge commit tying both histories together."
    echo ""
    echo "  2) REBASE (cleaner history)"
    echo "     Bundles your local changes into one commit and places it on top"
    echo "     of the latest update. Individual commit messages are combined."
    echo ""
    echo "  3) ABORT (no changes made)"
    echo ""
    CHOICE=$(prompt_choice "  Choose [1/2/3]: " "1 2 3")

    if [ "${CHOICE}" = "3" ]; then
        echo ""
        echo "Aborted. No changes made."
        exit 0
    fi

    STASHED=false
    if [ -n "${DIRTY_FILES}" ]; then
        echo ""
        echo "Setting aside your uncommitted changes for safekeeping..."
        if ! docker compose exec -T daaf-docker \
            git -C /daaf stash push -m "DAAF update backup ${TIMESTAMP}" </dev/null; then
            echo ""
            echo "ERROR: Could not safely set aside your uncommitted changes."
            echo ""
            echo "No changes were made -- your files are exactly as they were."
            echo ""
            echo "This can happen if there are new files that need to be committed first."
            echo "You can commit your changes, then re-run the updater:"
            echo "  bash run_daaf.sh bash"
            echo "  git add -A"
            echo "  git commit -m \"Save my changes before update\""
            echo "  exit"
            echo "  bash update_daaf.sh"
            exit 1
        fi
        STASHED=true
    fi

    if [ "${CHOICE}" = "1" ]; then
        # --- Merge path ---
        echo "Merging upstream updates..."
        if ! docker compose exec -T daaf-docker \
            git -C /daaf merge "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" \
            -m "Merge DAAF upstream updates" </dev/null; then
            if ! handle_conflict "merge" "merge --abort"; then
                if [ "${STASHED}" = true ]; then
                    echo ""
                    echo "Your uncommitted changes are safely saved and will be"
                    echo "restored after conflicts are resolved."
                    echo "  docker compose exec daaf-docker git -C /daaf stash pop"
                fi
                exit 1
            fi
        fi
    else
        # --- Squash-then-rebase path ---
        echo ""
        echo "Bundling your ${AHEAD} local commit(s) into a single commit..."
        MERGE_BASE=$(docker compose exec -T daaf-docker \
            git -C /daaf merge-base HEAD "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" \
            </dev/null 2>/dev/null | tr -d '\r' || true)

        if [ -z "${MERGE_BASE}" ]; then
            echo ""
            echo "The rebase option is not available for your setup."
            echo ""
            echo "This happens when your local changes and the update don't share"
            echo "a common starting point. This is unusual but not a problem."
            echo ""
            echo "Re-run the updater and choose option 1 (Merge) instead:"
            echo "  bash update_daaf.sh"
            if [ "${STASHED}" = true ]; then
                echo ""
                echo "Your uncommitted changes are safely saved and will be"
                echo "restored automatically when you re-run the updater."
            fi
            exit 1
        fi

        docker compose exec -T daaf-docker \
            git -C /daaf reset --soft "${MERGE_BASE}" </dev/null
        docker compose exec -T daaf-docker \
            git -C /daaf commit \
            -m "Local DAAF customizations (${AHEAD} commits, squashed before update on ${TIMESTAMP})" \
            </dev/null

        echo "Rebasing on top of the latest update..."
        if ! docker compose exec -T daaf-docker \
            git -C /daaf rebase "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" </dev/null; then
            if ! handle_conflict "rebase" "rebase --abort"; then
                if [ "${STASHED}" = true ]; then
                    echo ""
                    echo "Your uncommitted changes are safely saved and will be"
                    echo "restored after conflicts are resolved."
                    echo "  docker compose exec daaf-docker git -C /daaf stash pop"
                fi
                exit 1
            fi
        fi
    fi

    # Restore stashed changes
    if [ "${STASHED}" = true ]; then
        echo "Restoring your changes..."
        if ! docker compose exec -T daaf-docker \
            git -C /daaf stash pop </dev/null; then
            if handle_stash_conflict; then
                if [ "${CHOICE}" = "1" ]; then
                    finish_update "${OLD_HEAD}"
                else
                    finish_update "${OLD_HEAD}" \
                        "Your local changes have been rebased on top of the update."
                fi
            else
                if [ "${CHOICE}" = "1" ]; then
                    finish_update "${OLD_HEAD}" \
                        "Note: Uncommitted changes still need attention (see above)."
                else
                    finish_update "${OLD_HEAD}" \
                        "Your commits were rebased. Uncommitted changes still need attention (see above)."
                fi
            fi
            exit 0
        fi
    fi

    if [ "${CHOICE}" = "1" ]; then
        finish_update "${OLD_HEAD}"
    else
        finish_update "${OLD_HEAD}" \
            "Your local changes have been rebased on top of the update."
    fi
    exit 0
fi

# =====================================================================
# On default branch, no local commits -- uncommitted changes only
# =====================================================================
if [ -n "${DIRTY_FILES}" ]; then
    echo ""
    echo "You have uncommitted changes to the following files:"
    echo "${DIRTY_FILES}" | sed 's/^/  /'
    echo ""
    echo "These will be safely set aside during the update, then re-applied."
    echo ""
    echo "Options:"
    echo "  1) Stash changes, update, then re-apply"
    echo "  2) Show what changed first"
    echo "  3) Abort (no changes made)"
    echo ""
    CHOICE=$(prompt_choice "  Choose [1/2/3]: " "1 2 3")

    if [ "${CHOICE}" = "3" ]; then
        echo ""
        echo "Aborted. No changes made."
        exit 0
    fi

    if [ "${CHOICE}" = "2" ]; then
        echo ""
        docker compose exec -T daaf-docker \
            git -C /daaf diff </dev/null | tr -d '\r'
        echo ""
        echo "Lines starting with + are additions, - are removals."
        echo ""
        echo "Options:"
        echo "  1) Stash changes, update, then re-apply"
        echo "  3) Abort"
        echo ""
        CHOICE=$(prompt_choice "  Choose [1/3]: " "1 3")
        if [ "${CHOICE}" = "3" ]; then
            echo ""
            echo "Aborted. No changes made."
            exit 0
        fi
    fi

    echo "Setting aside your changes for safekeeping..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf stash push -m "DAAF update backup ${TIMESTAMP}" </dev/null; then
        echo ""
        echo "ERROR: Could not safely set aside your uncommitted changes."
        echo ""
        echo "No changes were made -- your files are exactly as they were."
        echo ""
        echo "This can happen if there are new files that need to be committed first."
        echo "You can commit your changes, then re-run the updater:"
        echo "  bash run_daaf.sh bash"
        echo "  git add -A"
        echo "  git commit -m \"Save my changes before update\""
        echo "  exit"
        echo "  bash update_daaf.sh"
        exit 1
    fi

    echo "Pulling updates..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf pull "${UPSTREAM_REMOTE}" "${REMOTE_BRANCH}" </dev/null; then
        echo ""
        echo "ERROR: Could not download the latest updates."
        echo ""
        echo "Your uncommitted changes are safely saved."
        echo ""
        echo "Common causes:"
        echo "  - No internet connection"
        echo "  - GitHub may be down (check https://www.githubstatus.com)"
        echo ""
        echo "To restore your changes:"
        echo "  docker compose exec daaf-docker git -C /daaf stash pop"
        echo ""
        echo "Your research files are not affected."
        exit 1
    fi

    echo "Re-applying your changes..."
    if ! docker compose exec -T daaf-docker \
        git -C /daaf stash pop </dev/null; then
        if handle_stash_conflict; then
            finish_update "${OLD_HEAD}" \
                "Your local changes have been re-applied on top of the update."
            exit 0
        else
            finish_update "${OLD_HEAD}" \
                "Note: Uncommitted changes still need attention (see above)."
            exit 0
        fi
    fi

    finish_update "${OLD_HEAD}" \
        "Your local changes have been re-applied on top of the update."
    exit 0
fi

# =====================================================================
# Cleanest path: on default branch, no local commits, no changes
# =====================================================================
echo ""
echo "Pulling updates..."
if ! docker compose exec -T daaf-docker \
    git -C /daaf pull "${UPSTREAM_REMOTE}" "${REMOTE_BRANCH}" </dev/null; then
    echo ""
    echo "ERROR: Could not download the latest updates."
    echo ""
    echo "No changes were made to your installation."
    echo "Your research files are not affected."
    echo ""
    echo "Common causes:"
    echo "  - No internet connection"
    echo "  - GitHub may be down (check https://www.githubstatus.com)"
    echo ""
    echo "Once the issue is resolved, re-run:  bash update_daaf.sh"
    exit 1
fi

finish_update "${OLD_HEAD}"
