#!/usr/bin/env bash
# ============================================================================
# DAAF Update Script (run inside the container)
# ============================================================================
# Usage:
#   bash /daaf/scripts/update.sh
#
# What this script does:
#   1. Checks git remote, branch, and local state
#   2. Creates a full backup (tar.gz + git backup branch) before any changes
#   3. Walks you through handling uncommitted changes, local commits, etc.
#   4. Pulls the latest DAAF updates safely
#   5. Detects Dockerfile changes and prints rebuild instructions
#
# This script creates a backup before any changes, offers interactive
# prompts for safe operations, and never runs destructive operations
# without explicit manual commands from the user.
# ============================================================================

set -euo pipefail

DAAF_DIR="/daaf"
UPSTREAM_REPO="DAAF-Contribution-Community/daaf"
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
BACKUP_BRANCH="backup/pre-update-${TIMESTAMP}"
BACKUP_FILE="/daaf/daaf-backup-${TIMESTAMP}.tar.gz"
BACKUP_CREATED=false
cd "${DAAF_DIR}"

# --- Require interactive terminal ---
if [ ! -t 0 ]; then
    echo "This script requires interactive input. Run it directly in a terminal:" >&2
    echo "  bash /daaf/scripts/update.sh" >&2
    exit 1
fi

# =====================================================================
# Helper functions
# =====================================================================

prompt_choice() {
    local prompt_text="$1"
    local valid_choices="$2"
    local choice=""
    while true; do
        read -r -p "${prompt_text}" choice
        if echo "${valid_choices}" | grep -qw "${choice}"; then
            echo "${choice}"
            return
        fi
        echo "  Please enter one of: ${valid_choices}" >&2
    done
}

create_backup() {
    # Skip if we already created a backup this run
    if [ "${BACKUP_CREATED}" = true ]; then
        return
    fi

    echo ""
    echo "-------------------------------------------"
    echo "  Creating a safety backup"
    echo "-------------------------------------------"
    echo ""
    echo "Before making any changes, this script will save a complete copy of"
    echo "your DAAF folder so you can always restore it if anything goes wrong."
    echo ""
    echo "Creating backup archive (this may take a moment) ..."

    tar -czf "${BACKUP_FILE}" \
        -C / daaf \
        --exclude='daaf/.git' \
        --exclude='daaf/.claude/logs' \
        --exclude='daaf/daaf-backup-*.tar.gz' \
        2>/dev/null || true

    # Verify the archive was created successfully
    if [ ! -s "${BACKUP_FILE}" ]; then
        echo ""
        echo "WARNING: Archive backup failed or is empty (possibly disk full)."
        echo "The git backup branch will still be available as a restore point."
        echo ""
    fi

    # Also create a git backup branch for easy restore within git
    git branch "${BACKUP_BRANCH}" 2>/dev/null || true

    BACKUP_CREATED=true

    echo ""
    echo "Backup saved to: ${BACKUP_FILE}"
    echo "Git restore point: ${BACKUP_BRANCH}"
    echo ""
    echo "RECOMMENDED: Download this backup to your computer before continuing."
    echo "Open a NEW terminal on your host computer and run:"
    echo ""
    echo "  docker cp daaf-daaf-docker-1:${BACKUP_FILE} ~/Downloads/"
    echo ""
    echo "  (On Windows PowerShell:)"
    echo "  docker cp daaf-daaf-docker-1:${BACKUP_FILE} \$env:USERPROFILE\\Downloads\\"
    echo ""
    echo "This gives you a complete snapshot you can restore from no matter what."
    echo ""

    CHOICE=$(prompt_choice "  Ready to proceed with the update? [y/n]: " "y n")
    if [ "${CHOICE}" = "n" ]; then
        echo ""
        echo "No problem! Download your backup first, then re-run:"
        echo "  bash /daaf/scripts/update.sh"
        echo ""
        exit 0
    fi
    echo ""
}

print_rebuild_instructions() {
    local changed_files="$1"
    echo "NOTE: The following build files changed in this update:"
    echo "${changed_files}" | sed 's/^/  /'
    echo ""
    echo "You'll need to rebuild the Docker image for these changes to fully take effect."
    echo "From your HOST computer terminal (not inside the container):"
    echo ""
    echo "  1. Navigate to your daaf-docker folder (wherever you ran the installer):"
    echo "     cd daaf-docker"
    echo ""
    echo "  2. Copy updated files to your host build directory:"
    echo "     docker cp daaf-daaf-docker-1:/daaf/Dockerfile ./Dockerfile"
    echo "     docker cp daaf-daaf-docker-1:/daaf/docker-compose.yml ./docker-compose.yml"
    echo ""
    echo "  3. Rebuild:"
    echo "     docker compose up -d --build"
    echo ""
}

print_completion() {
    local old_head="$1"
    local extra_msg="${2:-}"

    local new_head
    new_head=$(git rev-parse HEAD)
    local dockerfile_changed
    dockerfile_changed=$(git diff --name-only "${old_head}..${new_head}" -- Dockerfile docker-compose.yml 2>/dev/null || true)

    echo ""
    echo "=========================================="
    echo "  Update complete!"
    echo "=========================================="
    echo ""
    if [ -n "${extra_msg}" ]; then
        echo "${extra_msg}"
        echo ""
    fi
    echo "Backup archive: ${BACKUP_FILE}"
    echo "Git restore point: ${BACKUP_BRANCH}"
    echo ""
    echo "  To undo this update using git:"
    echo "    git reset --hard ${BACKUP_BRANCH}"
    echo ""
    echo "  Once you're satisfied the update is working, you can delete the backup:"
    echo "    rm ${BACKUP_FILE}"
    echo ""

    if [ -n "${dockerfile_changed}" ]; then
        print_rebuild_instructions "${dockerfile_changed}"
    else
        echo "No Dockerfile changes — no container rebuild is needed."
        echo ""
    fi
}

# =====================================================================
# Main script
# =====================================================================

echo ""
echo "=========================================="
echo "  DAAF Updater"
echo "=========================================="
echo ""
echo "Tip: Exit Claude Code (/exit) before updating to avoid file conflicts."
echo ""

# --- Check for git remote ---
if ! git remote get-url origin &>/dev/null; then
    echo "No git remote configured."
    echo ""
    echo "This usually means you installed DAAF using the manual (zip) method."
    echo "You can either:"
    echo ""
    echo "  1. Add the remote and use this updater going forward:"
    echo "     git remote add origin https://github.com/${UPSTREAM_REPO}.git"
    echo "     git fetch origin"
    echo "     Then re-run: bash /daaf/scripts/update.sh"
    echo ""
    echo "  2. Update manually using the zip method (see the Installation Guide):"
    echo "     https://github.com/${UPSTREAM_REPO}/blob/main/user_reference/01_installation_and_quickstart.md#keeping-daaf-updated"
    echo ""
    exit 0
fi

# --- Determine upstream remote ---
ORIGIN_URL=$(git remote get-url origin)
UPSTREAM_REMOTE="origin"

if ! echo "${ORIGIN_URL}" | grep -qi "${UPSTREAM_REPO}"; then
    echo "NOTE: Your 'origin' remote points to:"
    echo "  ${ORIGIN_URL}"
    echo ""
    echo "This looks like a fork, not the main DAAF repository."
    echo ""
    if git remote get-url upstream &>/dev/null; then
        UPSTREAM_REMOTE="upstream"
        echo "Found 'upstream' remote — will check for updates from there."
    else
        echo "To pull updates from the official DAAF repository, add it as 'upstream':"
        echo "  git remote add upstream https://github.com/${UPSTREAM_REPO}.git"
        echo "  git fetch upstream"
        echo "  Then re-run: bash /daaf/scripts/update.sh"
        echo ""
        echo "You can then merge upstream changes into your fork with:"
        echo "  git merge upstream/main"
        echo ""
        exit 0
    fi
    echo ""
fi

# --- Fetch latest from remote ---
echo "Fetching latest changes from ${UPSTREAM_REMOTE} ..."
if ! git fetch "${UPSTREAM_REMOTE}"; then
    echo ""
    echo "Failed to fetch from ${UPSTREAM_REMOTE}. Check your internet connection and try again."
    exit 1
fi

# --- Resolve the remote's default branch ---
REMOTE_BRANCH=""
if git rev-parse --verify "${UPSTREAM_REMOTE}/main" &>/dev/null; then
    REMOTE_BRANCH="main"
elif git rev-parse --verify "${UPSTREAM_REMOTE}/master" &>/dev/null; then
    REMOTE_BRANCH="master"
else
    REMOTE_BRANCH=$(git symbolic-ref "refs/remotes/${UPSTREAM_REMOTE}/HEAD" 2>/dev/null | sed "s|refs/remotes/${UPSTREAM_REMOTE}/||" || true)
    if [ -z "${REMOTE_BRANCH}" ]; then
        echo ""
        echo "Could not determine the default branch for ${UPSTREAM_REMOTE}."
        echo "Expected 'main' or 'master' but neither exists."
        echo "Available remote branches:"
        git branch -r --list "${UPSTREAM_REMOTE}/*" | sed 's/^/  /'
        echo ""
        exit 1
    fi
fi

# --- Check which branch we're on ---
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")

if [ -z "${CURRENT_BRANCH}" ]; then
    echo ""
    echo "WARNING: You are in a 'detached HEAD' state (not on any branch)."
    echo "This can happen if you checked out a specific commit or tag."
    echo "Switch to ${REMOTE_BRANCH} first, then re-run this script:"
    echo "  git checkout ${REMOTE_BRANCH}"
    echo "  bash /daaf/scripts/update.sh"
    echo ""
    exit 0
fi

# --- Check if already up to date ---
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}")

if [ "${CURRENT_BRANCH}" = "${REMOTE_BRANCH}" ] && [ "${LOCAL}" = "${REMOTE}" ]; then
    DIRTY_CHECK=$(git diff --name-only HEAD 2>/dev/null || true)
    if [ -z "${DIRTY_CHECK}" ]; then
        echo ""
        echo "Already up to date! Nothing to do."
        echo ""
        exit 0
    fi
fi

# --- Compute ahead/behind ---
AHEAD=$(git rev-list --count "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}..HEAD" 2>/dev/null || echo "0")
BEHIND=$(git rev-list --count "HEAD..${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" 2>/dev/null || echo "0")

if [ "${BEHIND}" != "0" ]; then
    echo ""
    echo "Updates available: ${BEHIND} new commit(s) on ${UPSTREAM_REMOTE}/${REMOTE_BRANCH}."
fi

# =====================================================================
# Handle non-default branch
# =====================================================================
if [ "${CURRENT_BRANCH}" != "${REMOTE_BRANCH}" ]; then
    echo ""
    echo "You are on branch '${CURRENT_BRANCH}', not '${REMOTE_BRANCH}'."
    echo ""
    echo "A 'branch' in git is like a separate workspace where you can make changes"
    echo "without affecting the main copy. DAAF updates are published to the"
    echo "'${REMOTE_BRANCH}' branch, so we need to bring those updates into your"
    echo "current branch."
    echo ""
    echo "Options:"
    echo "  1) Update: switch to ${REMOTE_BRANCH}, pull updates, switch back, and"
    echo "     merge the updates into '${CURRENT_BRANCH}'"
    echo "  2) Abort (no changes made)"
    echo ""
    CHOICE=$(prompt_choice "  Choose [1/2]: " "1 2")

    if [ "${CHOICE}" = "2" ]; then
        echo ""
        echo "Aborted. No changes made."
        echo ""
        exit 0
    fi

    create_backup

    # Stash uncommitted changes if any
    DIRTY_FILES=$(git diff --name-only HEAD 2>/dev/null || true)
    STASHED=false
    if [ -n "${DIRTY_FILES}" ]; then
        echo "Stashing uncommitted changes (saving them temporarily) ..."
        git stash push -m "DAAF update backup ${TIMESTAMP}"
        STASHED=true
    fi

    echo "Switching to ${REMOTE_BRANCH} ..."
    git checkout "${REMOTE_BRANCH}"

    echo "Pulling updates ..."
    git pull "${UPSTREAM_REMOTE}" "${REMOTE_BRANCH}"

    echo "Switching back to '${CURRENT_BRANCH}' ..."
    git checkout "${CURRENT_BRANCH}"

    echo "Merging ${REMOTE_BRANCH} into '${CURRENT_BRANCH}' ..."
    if ! git merge "${REMOTE_BRANCH}"; then
        echo ""
        echo "Merge conflict detected!"
        echo ""
        echo "A 'conflict' means the same file was changed both in the update and in"
        echo "your branch, and git doesn't know which version to keep. The conflicting"
        echo "files have been marked — open them in a text editor and look for lines"
        echo "starting with <<<<<<< and >>>>>>> to see both versions."
        echo ""
        echo "After resolving:"
        echo "  git add <resolved-files>"
        echo "  git commit"
        echo ""
        echo "To undo everything and go back to exactly how things were before:"
        echo "  git merge --abort"
        echo "  git reset --hard ${BACKUP_BRANCH}"
        if [ "${STASHED}" = true ]; then
            echo "  git stash pop"
        fi
        echo ""
        exit 1
    fi

    if [ "${STASHED}" = true ]; then
        echo "Restoring your stashed changes ..."
        if ! git stash pop; then
            echo ""
            echo "Your stashed changes conflict with the update. The stash is still saved."
            echo "Resolve the conflicts, then run: git stash drop"
            echo "Or to undo everything: git reset --hard ${BACKUP_BRANCH}"
            echo ""
            exit 1
        fi
    fi

    print_completion "${LOCAL}"
    exit 0
fi

# =====================================================================
# On default branch — check for local commits
# =====================================================================
if [ "${AHEAD}" -gt 0 ]; then
    echo ""
    echo "You have ${AHEAD} local commit(s) on ${REMOTE_BRANCH} that aren't part of"
    echo "the official DAAF release. This means you've saved custom changes to"
    echo "framework files."
    echo ""
    echo "Your local commits:"
    git log --oneline "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}..HEAD" | sed 's/^/  /'
    echo ""
    echo "To update, your changes need to be combined with the upstream changes."
    echo "Here are your options:"
    echo ""
    echo "  1) MERGE (recommended for most users)"
    echo "     Combines your changes with the update side-by-side. Git creates a"
    echo "     'merge commit' that ties both histories together. Your original"
    echo "     commits stay exactly as they are. If there's a conflict (the same"
    echo "     file was changed in both your version and the update), you'll"
    echo "     resolve it once."
    echo ""
    echo "  2) REBASE (cleaner history, slightly more advanced)"
    echo "     Takes all your local changes, bundles them into a single commit,"
    echo "     and places that commit on TOP of the latest update — as if you"
    echo "     made your changes after downloading the newest version. This"
    echo "     creates a cleaner, linear history with no merge commits. Your"
    echo "     individual commit messages are combined into one. Best if your"
    echo "     local changes are small customizations you'd like to keep tidy."
    echo ""
    echo "  3) ABORT (no changes made)"
    echo ""
    CHOICE=$(prompt_choice "  Choose [1/2/3]: " "1 2 3")

    if [ "${CHOICE}" = "3" ]; then
        echo ""
        echo "Aborted. No changes made."
        echo ""
        exit 0
    fi

    create_backup

    # Stash uncommitted changes if any
    DIRTY_FILES=$(git diff --name-only HEAD 2>/dev/null || true)
    STASHED=false
    if [ -n "${DIRTY_FILES}" ]; then
        echo "Stashing uncommitted changes (saving them temporarily) ..."
        git stash push -m "DAAF update backup ${TIMESTAMP}"
        STASHED=true
    fi

    if [ "${CHOICE}" = "1" ]; then
        # --- Merge path ---
        echo "Merging upstream updates into your local changes ..."
        if ! git merge "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" -m "Merge DAAF upstream updates"; then
            echo ""
            echo "Merge conflict detected!"
            echo ""
            echo "A 'conflict' means the same file was changed both in the update and"
            echo "in your local commits. Git has marked the conflicting sections in the"
            echo "affected files — look for lines starting with <<<<<<< and >>>>>>>."
            echo ""
            echo "After resolving:"
            echo "  git add <resolved-files>"
            echo "  git commit"
            echo ""
            echo "To undo everything and go back to exactly how things were before:"
            echo "  git merge --abort"
            echo "  git reset --hard ${BACKUP_BRANCH}"
            echo ""
            exit 1
        fi
    else
        # --- Squash-then-rebase path ---
        echo ""
        echo "Bundling your ${AHEAD} local commit(s) into a single commit ..."
        MERGE_BASE=$(git merge-base HEAD "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" 2>/dev/null || true)
        if [ -z "${MERGE_BASE}" ]; then
            echo ""
            echo "Cannot find a common ancestor between your branch and"
            echo "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}. This is unusual — it typically"
            echo "means the histories are unrelated. Try using merge (option 1) instead."
            echo ""
            echo "To undo: git reset --hard ${BACKUP_BRANCH}"
            echo ""
            exit 1
        fi
        git reset --soft "${MERGE_BASE}"
        git commit -m "Local DAAF customizations (${AHEAD} commits, squashed before update on ${TIMESTAMP})"

        echo "Rebasing your changes on top of the latest update ..."
        echo ""
        echo "(A 'rebase' replays your changes on top of the new version. If there's"
        echo "a conflict, git will pause and show you which files need attention.)"
        echo ""
        if ! git rebase "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}"; then
            echo ""
            echo "Rebase conflict detected!"
            echo ""
            echo "Git paused because one of your changes conflicts with the update."
            echo "The conflicting files have been marked — look for lines starting"
            echo "with <<<<<<< and >>>>>>> to see both versions."
            echo ""
            echo "After resolving the conflicts in each file:"
            echo "  git add <resolved-files>"
            echo "  git rebase --continue"
            echo ""
            echo "To undo everything and go back to exactly how things were before:"
            echo "  git rebase --abort"
            echo "  git reset --hard ${BACKUP_BRANCH}"
            echo ""
            exit 1
        fi
    fi

    # Restore stashed changes
    if [ "${STASHED}" = true ]; then
        echo "Restoring your stashed changes ..."
        if ! git stash pop; then
            echo ""
            echo "Your stashed changes conflict with the update. The stash is still saved."
            echo "Resolve the conflicts, then run: git stash drop"
            echo "Or to undo everything: git reset --hard ${BACKUP_BRANCH}"
            echo ""
            exit 1
        fi
    fi

    if [ "${CHOICE}" = "1" ]; then
        print_completion "${LOCAL}"
    else
        print_completion "${LOCAL}" "Your local changes have been rebased on top of the update."
    fi
    exit 0
fi

# =====================================================================
# On default branch, no local commits — check for uncommitted changes
# =====================================================================
DIRTY_FILES=$(git diff --name-only HEAD 2>/dev/null || true)

if [ -n "${DIRTY_FILES}" ]; then
    echo ""
    echo "You have uncommitted changes to the following files:"
    echo ""
    echo "${DIRTY_FILES}" | sed 's/^/  /'
    echo ""
    echo "'Uncommitted changes' means you (or DAAF) edited these files but haven't"
    echo "saved them as a git commit yet. These changes will be safely set aside"
    echo "during the update, then re-applied on top."
    echo ""
    echo "Options:"
    echo "  1) Stash changes, update, then re-apply (safe — nothing is lost)"
    echo "  2) Show what changed first (so you can review before deciding)"
    echo "  3) Abort (no changes made)"
    echo ""
    CHOICE=$(prompt_choice "  Choose [1/2/3]: " "1 2 3")

    if [ "${CHOICE}" = "3" ]; then
        echo ""
        echo "Aborted. No changes made."
        echo ""
        exit 0
    fi

    if [ "${CHOICE}" = "2" ]; then
        echo ""
        git diff
        echo ""
        echo "Above is a 'diff' — lines starting with + are additions, lines starting"
        echo "with - are removals. These are the changes that will be saved and"
        echo "re-applied after the update."
        echo ""
        echo "Options:"
        echo "  1) Stash changes, update, then re-apply"
        echo "  3) Abort"
        echo ""
        CHOICE=$(prompt_choice "  Choose [1/3]: " "1 3")
        if [ "${CHOICE}" = "3" ]; then
            echo ""
            echo "Aborted. No changes made."
            echo ""
            exit 0
        fi
    fi

    # Choice is 1: stash + update + pop
    create_backup

    echo "Stashing your changes (saving them temporarily) ..."
    echo ""
    echo "('Stashing' means git puts your changes in a safe holding area while we"
    echo "update the framework files, then puts them back afterward.)"
    echo ""
    git stash push -m "DAAF update backup ${TIMESTAMP}"

    echo "Pulling updates ..."
    git pull "${UPSTREAM_REMOTE}" "${REMOTE_BRANCH}"

    echo "Re-applying your changes on top of the update ..."
    if ! git stash pop; then
        echo ""
        echo "Some of your changes conflict with the update."
        echo ""
        echo "A 'conflict' means the update changed the same file(s) you edited."
        echo "Git has marked the conflicts in the affected files — open them and"
        echo "look for lines starting with <<<<<<< and >>>>>>> to see both versions."
        echo ""
        echo "After resolving the conflicts:"
        echo "  git stash drop"
        echo ""
        echo "To undo the entire update and restore your previous state:"
        echo "  git reset --hard ${BACKUP_BRANCH}"
        echo "  git stash pop"
        echo ""
        exit 1
    fi

    print_completion "${LOCAL}" "Your local changes have been re-applied on top of the update."
    exit 0
fi

# =====================================================================
# Cleanest path: on default branch, no local commits, no changes
# =====================================================================
create_backup

echo "Pulling updates ..."
git pull "${UPSTREAM_REMOTE}" "${REMOTE_BRANCH}"

print_completion "${LOCAL}"
