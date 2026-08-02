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
# CONTAINER_ID is derived from the compose project after the container is started
# (see the preflight block below), not hardcoded -- so it tracks DAAF_PROJECT_NAME
# and is correct for a second instance. It is consumed by `docker cp` in
# _sync_copy_one and by user-facing manual-recovery hints.
CONTAINER_ID=""
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
BACKUP_BRANCH="backup/pre-update-${TIMESTAMP}"

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so `docker compose` interpolation resolves the project name and
# published host ports. Canonical shared pattern (kept in sync with
# load_daaf_settings in daaf_lib.sh). Parse only these whitelisted keys (never `source`
# -- the file holds API keys); shell env wins; absent file = no-op; CR stripped;
# Bash 3.2 safe.
_daaf_load_settings() {
    local settings_file="./environment_settings.txt"
    [ -f "${settings_file}" ] || return 0
    local key val line
    while IFS= read -r line || [ -n "${line}" ]; do
        line="$(printf '%s' "${line}" | tr -d '\r')"
        case "${line}" in ''|'#'*) continue ;; esac
        case "${line}" in
            DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*|DAAF_DEV=*|DAAF_BRANCH=*|DAAF_DATA_VOLUME_NAME=*)
                key="${line%%=*}"; val="${line#*=}"
                case "${val}" in
                    \"*\") val="${val#\"}"; val="${val%\"}" ;;
                    \'*\') val="${val#\'}"; val="${val%\'}" ;;
                esac
                if [ -z "${!key:-}" ]; then
                    export "${key}=${val}"
                fi
                ;;
            *) continue ;;
        esac
    done < "${settings_file}"
}
# Capture whether DAAF_BRANCH came from the process environment BEFORE the
# settings bridge runs. _daaf_load_settings only adopts the file's value when the
# env var is unset (the `if [ -z "${!key:-}" ]` guard above), so after the call:
# DAAF_BRANCH set + FROM_ENV=0 => file-origin; FROM_ENV=1 => env-origin. This
# distinction drives tag handling and branch persistence in the resolver below.
DAAF_BRANCH_FROM_ENV=0
if [ -n "${DAAF_BRANCH:-}" ]; then DAAF_BRANCH_FROM_ENV=1; fi
_daaf_load_settings

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps -q daaf-docker"*) echo "abc123" ;;
            *"compose ps"*"--format"*) echo "daaf-docker" ;;
            "cp"*) return 0 ;;
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
        echo "Then re-run the updater from your host terminal:"
        echo "  bash update_daaf.sh"
        echo "It picks up where it left off -- restoring any set-aside changes and"
        echo "finishing the remaining steps (host-script sync and rebuild check)"
        echo "automatically."
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
    echo "However, re-applying your uncommitted changes hit conflicts: some of"
    echo "your local edits (commonly to Dockerfile or docker-compose.yml)"
    echo "overlap with changes in this update, so Git could not merge them"
    echo "automatically."
    echo ""
    echo "Nothing is lost. Your changes are preserved safely in a git stash --"
    echo "the update did not discard them."
    echo ""
    echo "The easiest fix: start a DAAF session (launch Claude Code in the"
    echo "container) and ask for help with \"update conflicts\". DAAF's User"
    echo "Support mode has a guided walkthrough that resolves these step by step."
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
        echo "Recommended: start a DAAF session and ask for help with \"update"
        echo "conflicts\" -- User Support mode has a guided conflict walkthrough:"
        echo "  bash run_daaf.sh"
        echo ""
        echo "Or resolve manually -- enter the container:"
        echo "  bash run_daaf.sh bash"
        echo "  (edit the conflicting files to remove the <<<<<<< markers)"
        echo "  git add ."
        echo "  git stash drop"
        echo "  exit"
        echo ""
        echo "Either way, your changes are safe in the git stash until you"
        echo "resolve them -- nothing has been lost."
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

# Copy one host script out of the container. Sets SYNC_COPY_FAILED=true and
# prints a manual-recovery hint on failure (no silent skips). Marks the file's
# basename as copied in the "already copied" tracker so tier B does not repeat
# a tier A copy. Returns 0 on success, 1 on failure.
#
# INTENT: single shared copy routine so the existence-heal (tier A) and
#   changed-file (tier B) passes format success/failure output identically.
# ASSUMES: CONTAINER_ID points at the running container; docker cp is
#   ID/name-sensitive (docker compose exec is not, but cp is). The manual-recovery
#   hint prints the project-resolved `docker cp <project>-daaf-docker-1:...` form
#   so it works from a fresh shell where DAAF_PROJECT_NAME may not be exported.
_sync_copy_one() {
    local repo_path="$1"
    local script
    script=$(basename "${repo_path}")
    # Tier B can overwrite a host copy that DIFFERS from what it delivers
    # (e.g. a locally drifted file that also changed in the update range --
    # and on old-era migrations EVERY host script is "changed in range", so
    # this path, not tier C, performs the drift heal). Preserve the tier C
    # recoverability contract here too: stage the incoming copy as a sibling
    # file (same directory keeps `docker cp`'s file-mode semantics and makes
    # the final rename same-filesystem), and when an existing host copy
    # differs, save it to the rolling "<name>.pre-update" BEFORE overwriting.
    # If the backup cannot be created, do NOT overwrite -- never destroy the
    # only copy -- same rule as the tier C drift heal. (Field finding
    # 2026-07-17: the v2.0.1 vector's class E drift fixture was healed via
    # tier B and clobbered with no backup.)
    if [ -f "./${script}" ]; then
        # The staged-existence leg mirrors the ps1 twin's Test-Path guard: an
        # abnormal "docker cp exits 0 but produced no file" would otherwise
        # fall through to cmp (missing staged reads as drift), create a
        # spurious .pre-update, and fail at the rename.
        if ! docker cp "${CONTAINER_ID}:/daaf/${repo_path}" "./${script}.sync-staged" 2>/dev/null \
            || [ ! -f "./${script}.sync-staged" ]; then
            rm -f "./${script}.sync-staged" 2>/dev/null || true
            echo "  Warning: could not copy ${script}. You can copy it manually:"
            echo "    docker cp ${DAAF_PROJECT_NAME:-daaf}-daaf-docker-1:/daaf/${repo_path} ./${script}"
            SYNC_COPY_FAILED=true
            return 1
        fi
        local backed_up=false
        if ! cmp -s "./${script}" "./${script}.sync-staged"; then
            if cp -f "./${script}" "./${script}.pre-update" 2>/dev/null; then
                backed_up=true
            else
                rm -f "./${script}.sync-staged" 2>/dev/null || true
                echo "  Warning: could not back up ${script} before overwriting -- left unchanged."
                echo "    To adopt the repository version manually, run:"
                echo "    docker cp ${DAAF_PROJECT_NAME:-daaf}-daaf-docker-1:/daaf/${repo_path} ./${script}"
                SYNC_COPY_FAILED=true
                return 1
            fi
        fi
        if ! mv -f "./${script}.sync-staged" "./${script}" 2>/dev/null; then
            rm -f "./${script}.sync-staged" 2>/dev/null || true
            echo "  Warning: could not copy ${script}. You can copy it manually:"
            echo "    docker cp ${DAAF_PROJECT_NAME:-daaf}-daaf-docker-1:/daaf/${repo_path} ./${script}"
            SYNC_COPY_FAILED=true
            return 1
        fi
        # Text and icon (.txt/.ico) files do not need the executable bit; scripts do.
        case "${script}" in
            *.sh|*.command) chmod +x "./${script}" 2>/dev/null || true ;;
        esac
        if [ "${backed_up}" = true ]; then
            echo "  Updated: ${script} (your previous copy was saved as ${script}.pre-update)"
        else
            echo "  Updated: ${script}"
        fi
        SYNC_COPIED="${SYNC_COPIED} ${script}"
        return 0
    fi
    if docker cp "${CONTAINER_ID}:/daaf/${repo_path}" "./${script}" 2>/dev/null; then
        # Text and icon (.txt/.ico) files do not need the executable bit; scripts do.
        case "${script}" in
            *.sh|*.command) chmod +x "./${script}" 2>/dev/null || true ;;
        esac
        echo "  Updated: ${script}"
        SYNC_COPIED="${SYNC_COPIED} ${script}"
        return 0
    else
        echo "  Warning: could not copy ${script}. You can copy it manually:"
        echo "    docker cp ${DAAF_PROJECT_NAME:-daaf}-daaf-docker-1:/daaf/${repo_path} ./${script}"
        SYNC_COPY_FAILED=true
        return 1
    fi
}

# Sync host-side utility scripts out of the container to the daaf-docker folder.
#
# The old design diffed a HARDCODED pathspec inside the running (old) script.
# Files added upstream that the old script did not know about were silently
# skipped forever -- a chicken-and-egg defect (a v2.1.0 updater could never
# deliver daaf.sh/daaf_lib.sh even though they were in the update). This
# rewrite derives the file list from the POST-UPDATE repo state and adds an
# existence-heal pass so past misses self-correct on the next run.
#
# INTENT: guarantee every host-appropriate script that exists in the new HEAD
#   reaches the host, regardless of what the running (old) script knew.
# REASONING: the authoritative list lives in the freshly-pulled repo
#   (git ls-files at new HEAD), not in this script's source.
#
# old_head may be empty (called from the "already up to date" path). When
# empty or equal to new_head, only the existence-heal pass runs (cheap).
sync_host_scripts() {
    local old_head="${1:-}"

    local new_head
    new_head=$(docker compose exec -T daaf-docker \
        git -C /daaf rev-parse HEAD </dev/null 2>/dev/null | tr -d '\r')

    # Derive the authoritative host-script list from the post-update repo state.
    # git ls-files runs in-container at new HEAD -- Linux userland, so GNU git
    # features are fine here (this is NOT host-executed code).
    local all_host_files
    all_host_files=$(docker compose exec -T daaf-docker \
        git -C /daaf ls-files 'scripts/host/*' </dev/null 2>/dev/null | tr -d '\r' || true)

    if [ -z "${all_host_files}" ]; then
        return
    fi

    # Platform filter (macOS/Linux hosts): keep *.sh files, the macOS double-click
    # launcher DAAF.command (Darwin-gated below), the daaf.ico icon (future,
    # user-supplied -- absent from the repo until then, so it simply never appears
    # in the git ls-files list), and shared plain-text files
    # (environment_settings_example.txt, README.txt); drop all *.ps1 and daaf.bat
    # (Windows-only -- delivered by update_daaf.ps1 instead).
    # Bootstrap-only scripts (install.sh, migrate_daaf.sh) are intentionally
    # excluded -- they are fetched via curl on demand and are not needed in the
    # daaf-docker folder post-install. This preserves the pre-existing exclusion
    # intent from the old hardcoded list. The dev-only test harness
    # (test_migration.sh) is likewise excluded -- it is a contributor tool
    # tracked in git for CI, never needed in the user's daaf-docker folder.
    # Without this exclusion it would match the *.sh case and be synced to hosts.
    #
    # ASSUMES: no negative subscripts, no mapfile, no declare -A -- Bash 3.2
    #   compatible for macOS hosts.
    # sync_list is a newline-delimited set of full repo paths, with a leading
    # and trailing newline so membership tests can anchor on "\n<path>\n"
    # (prevents a short path from matching as a substring of a longer one).
    local sync_list="
"
    # DAAF.command (the macOS double-click launcher) is Finder-specific and is
    # delivered on macOS only, mirroring install.sh's `uname -s = Darwin` gate;
    # on Linux hosts it is filtered out (Linux users launch via `bash daaf.sh`).
    local is_darwin=false
    if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
        is_darwin=true
    fi
    while IFS= read -r repo_path; do
        [ -z "${repo_path}" ] && continue
        case "${repo_path}" in
            scripts/host/install.sh|scripts/host/migrate_daaf.sh|scripts/host/test_migration.sh) continue ;;
            scripts/host/DAAF.command)
                [ "${is_darwin}" = true ] || continue
                sync_list="${sync_list}${repo_path}
" ;;
            *.sh|scripts/host/daaf.ico|scripts/host/environment_settings_example.txt|scripts/host/README.txt) sync_list="${sync_list}${repo_path}
" ;;
            *) continue ;;
        esac
    done <<< "${all_host_files}"

    # Only the seed newline means no files passed the filter.
    if [ "${sync_list}" = "
" ]; then
        return
    fi

    # Compute the set of files that changed in old_head..new_head (tier B).
    # Only when we have a real commit range; skip the diff on the up-to-date
    # path (old_head empty or unchanged) -- the existence-heal pass still runs.
    local changed_scripts=""
    if [ -n "${old_head}" ] && [ "${old_head}" != "${new_head}" ]; then
        changed_scripts=$(docker compose exec -T daaf-docker \
            git -C /daaf diff --name-only "${old_head}..${new_head}" -- scripts/host \
            </dev/null 2>/dev/null | tr -d '\r' || true)
    fi

    # Trackers (space-delimited strings -- Bash 3.2 compatible, no arrays needed).
    SYNC_COPIED=""
    SYNC_COPY_FAILED=false
    local self_updated=false
    local printed_header=false

    # --- Tier A: existence-heal ---------------------------------------------
    # Any host-appropriate file MISSING on the host is copied unconditionally.
    # This is what heals past misses (e.g., daaf.sh arriving for a v2.1.0 user
    # even though it will never change again).
    while IFS= read -r repo_path; do
        [ -z "${repo_path}" ] && continue
        local script
        script=$(basename "${repo_path}")
        if [ ! -f "./${script}" ]; then
            if [ "${printed_header}" = false ]; then
                echo "Syncing utility scripts..."
                printed_header=true
            fi
            _sync_copy_one "${repo_path}" || true
        fi
    done <<< "${sync_list}"

    # --- Tier B: changed files ----------------------------------------------
    # Any listed file that changed in this update range is copied (unless tier A
    # already copied it). Preserves the only-touch-changed-files courtesy for
    # existing host copies the user may have customized.
    if [ -n "${changed_scripts}" ]; then
        while IFS= read -r repo_path; do
            [ -z "${repo_path}" ] && continue
            # Only sync files that pass the platform filter (i.e., are in
            # sync_list). Anchor on surrounding newlines for an exact line match.
            case "${sync_list}" in
                *"
${repo_path}
"*) ;;
                *) continue ;;
            esac
            local script
            script=$(basename "${repo_path}")
            # Skip if tier A already copied this file (space-delimited membership).
            case " ${SYNC_COPIED} " in
                *" ${script} "*) continue ;;
            esac
            if [ "${printed_header}" = false ]; then
                echo "Syncing updated utility scripts..."
                printed_header=true
            fi
            if _sync_copy_one "${repo_path}"; then
                if [ "${script}" = "update_daaf.sh" ]; then
                    self_updated=true
                fi
            fi
        done <<< "${changed_scripts}"
    fi

    if [ "${printed_header}" = true ]; then
        echo ""
    fi

    # --- Tier C: drift heal (overwrite with rolling backup) -----------------
    # A file that EXISTS on host but differs from the repo copy and was NOT
    # copied this run (not missing, not changed in-range) would otherwise be
    # left silently stale -- the last silent failure mode after interrupted
    # syncs, upstream changes the diff missed, or manual copies. We OVERWRITE
    # with the repo version, first saving the existing host copy to
    # "<name>.pre-update" (rolling: any previous .pre-update is overwritten, so
    # backups never accumulate).
    #
    # DESIGN DECISION (2026-07-09): the files this updater syncs -- host utility
    # scripts (*.sh) and the example template (environment_settings_example.txt,
    # README.txt) -- have NO supported local-edit use-case. All user-serviceable
    # configuration lives exclusively in environment_settings.txt, which this
    # updater never syncs or touches. Therefore drift here means STALENESS, not
    # a deliberate customization worth preserving, and silently keeping a stale
    # copy is the worst outcome. Overwrite + rolling backup is the deliberate
    # design: the host always ends up with the current repo version, and the
    # user's prior bytes are recoverable from the .pre-update file if ever needed.
    # This supersedes the earlier warn-never-overwrite behavior.
    #
    # INTENT: bring stale-but-present host files up to date, preserving one
    #   recoverable backup per file.
    # REASONING: one bulk `docker compose cp` of scripts/host into a temp dir,
    #   then local `cmp -s` per file, avoids N per-file docker execs. `cmp -s`
    #   is POSIX/BSD-safe (available on macOS's BSD userland).
    # ASSUMES: files already copied this run (SYNC_COPIED) are fresh by
    #   construction and are excluded. Failure to stage or compare degrades to
    #   a single notice -- drift healing is best-effort and never aborts.
    #   The .pre-update backup files are never themselves sync candidates: the
    #   sync_list is derived purely from repo paths (git ls-files scripts/host/*),
    #   and .pre-update files exist only on the host, so they can never appear in
    #   that list or match a repo basename.
    local drift_dir=""
    local drift_found=false
    local drift_degraded=false
    drift_dir=$(mktemp -d 2>/dev/null || true)
    if [ -z "${drift_dir}" ] || [ ! -d "${drift_dir}" ]; then
        # Could not create a scratch dir -- skip drift checking silently-ish.
        drift_degraded=true
    else
        # Bulk-copy the repo's scripts/host tree out of the container once.
        # `docker compose cp` is project-aware HERE because this script parsed
        # and exported DAAF_PROJECT_NAME. Printed user-facing hints instead use
        # the explicit `docker cp <project>-daaf-docker-1:` form, because a
        # fresh user shell lacks that env and compose would resolve the default
        # project. On failure, degrade.
        if ! docker compose cp daaf-docker:/daaf/scripts/host "${drift_dir}/repo_host" \
            >/dev/null 2>&1; then
            drift_degraded=true
        fi
    fi

    if [ "${drift_degraded}" = true ]; then
        echo "Note: could not check host scripts for drift this run (skipped safely)."
        echo ""
    else
        while IFS= read -r repo_path; do
            [ -z "${repo_path}" ] && continue
            local script
            script=$(basename "${repo_path}")
            # Only files that exist on host are drift candidates (missing files
            # were handled by tier A).
            [ -f "./${script}" ] || continue
            # Exclude files copied this run (tier A or tier B) -- fresh by
            # construction (space-delimited membership, Bash 3.2 safe).
            case " ${SYNC_COPIED} " in
                *" ${script} "*) continue ;;
            esac
            # Never overwrite the RUNNING updater from the drift loop: bash reads
            # scripts lazily, so replacing this file mid-execution can execute
            # corrupted content. Tier B's self-update path (with its explicit
            # re-run notice) is the sanctioned way the updater refreshes itself.
            [ "${script}" = "update_daaf.sh" ] && continue
            local repo_copy="${drift_dir}/repo_host/${script}"
            # If the repo copy is missing from the staged tree, we cannot compare
            # -- skip this file rather than guessing.
            [ -f "${repo_copy}" ] || continue
            if ! cmp -s "./${script}" "${repo_copy}"; then
                # Drift detected. Back up the existing host copy to a rolling
                # "<name>.pre-update" (overwrite any prior backup), THEN overwrite
                # the host copy with the repo version. If the backup step fails we
                # do NOT overwrite -- never destroy the only copy -- and fall back
                # to the old warning for that file.
                if cp -f "./${script}" "./${script}.pre-update" 2>/dev/null; then
                    if cp -f "${repo_copy}" "./${script}" 2>/dev/null; then
                        # Text and icon (.txt/.ico) files do not need the executable bit; scripts do.
                        case "${script}" in
                            *.sh|*.command) chmod +x "./${script}" 2>/dev/null || true ;;
                        esac
                        echo "  Updated: ${script} (your previous copy was saved as ${script}.pre-update)"
                        drift_found=true
                    else
                        # Backup succeeded but overwrite failed -- the host copy is
                        # untouched and the backup is a redundant duplicate. Warn.
                        echo "  WARNING: ${script} is stale but could not be updated"
                        echo "    (write failed). Your file is unchanged. To adopt the"
                        echo "    repository version manually, run:"
                        echo "      docker cp ${DAAF_PROJECT_NAME:-daaf}-daaf-docker-1:/daaf/${repo_path} ./${script}"
                    fi
                else
                    # Could not create the backup -- do NOT overwrite (never
                    # destroy the only copy). Fall back to the old warning.
                    echo "  WARNING: ${script} is stale but could not be updated"
                    echo "    (backup step failed). Your file was left unchanged to"
                    echo "    avoid losing it. To adopt the repository version, run:"
                    echo "      docker cp ${DAAF_PROJECT_NAME:-daaf}-daaf-docker-1:/daaf/${repo_path} ./${script}"
                fi
            fi
        done <<< "${sync_list}"
    fi

    # Clean up the staging dir (best-effort; never fatal).
    if [ -n "${drift_dir}" ] && [ -d "${drift_dir}" ]; then
        rm -rf "${drift_dir}" 2>/dev/null || true
    fi

    # Closing summary if any stale files were updated -- mirrors the
    # SYNC_COPY_FAILED summary so the message is not missed if it scrolled past.
    if [ "${drift_found}" = true ]; then
        echo ""
        echo "One or more host files were stale and have been updated to the"
        echo "repository version -- see the messages above. Your previous copies"
        echo "were saved as <name>.pre-update files in this folder; you can delete"
        echo "them once you have confirmed everything works, or restore one by"
        echo "renaming it back if something regresses."
        echo ""
    fi

    # --- Sync failure summary ------------------------------------------------
    # SYNC_COPY_FAILED is set true by _sync_copy_one on any copy error. Print a
    # closing summary so the user knows to act even if the warning scrolled by.
    if [ "${SYNC_COPY_FAILED}" = true ]; then
        echo "Warning: some host scripts could not be synced -- see the messages above for manual copy commands."
        echo ""
    fi

    # --- Self-update notice --------------------------------------------------
    # If the updater itself was refreshed as a CHANGED file, its new logic is on
    # disk but was not executed this run. Prompt a re-run so the new updater's
    # existence-heal pass can deliver anything the old logic could not. This is
    # the explicit mechanism for the v2.1.0 -> daaf_dev two-run recovery (no
    # auto re-exec -- that would collide with the mkdir lock and EXIT traps).
    if [ "${self_updated}" = true ]; then
        echo "-------------------------------------------"
        echo "  The updater itself was updated"
        echo "-------------------------------------------"
        echo ""
        echo "update_daaf.sh was refreshed in this update. The new version is"
        echo "now on disk but this run used the previous version. Re-run it once"
        echo "more so the latest updater can finish syncing your host tools:"
        echo "  bash update_daaf.sh"
        echo ""
        echo "(It is safe to re-run -- if everything is already current it will"
        echo " simply report 'Already up to date!')"
        echo ""
    fi
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
            echo "  docker cp ${DAAF_PROJECT_NAME:-daaf}-daaf-docker-1:/daaf/scripts/host/rebuild_daaf.sh ./rebuild_daaf.sh"
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
    # Persist an env-origin update branch so future runs track it without
    # re-exporting DAAF_BRANCH. Extracted into persist_branch_choice so the no-op
    # success paths ("Already up to date"), which exit before finish_update runs,
    # can persist the same way -- otherwise a re-run of `DAAF_BRANCH=x update`
    # while already current would never save the choice.
    persist_branch_choice

    # Single marker-cleanup chokepoint: every successful completion clears the
    # interrupted-update resume marker so a subsequent run does not mistake this
    # (now-finished) update for one still needing resume finalization.
    clear_resume_marker
}

# --- Settings-File Key Upsert (inlined from daaf_lib.sh) ---
# Insert/update a single KEY=value line in environment_settings.txt when
# persisting an env-origin DAAF_BRANCH after a successful update. This is an
# INLINE COPY of daaf_lib.sh upsert_settings_key (byte-equivalent to the copy in
# install.sh): update_daaf is a standalone recovery tool that must run even if
# daaf_lib is broken and, like install.sh, does not source it (mirroring the
# inline settings *reader* above). Semantics, placement rules, atomicity,
# encoding, DRY-RUN gating and Bash 3.2 safety are identical to the library
# version -- see daaf_lib.sh for the full annotation. Defined before the
# DAAF_TEST_MODE guard so it is available to finish_update under test dot-source.
upsert_settings_key() {
    local file key value mode backup_suffix
    file="${1:?upsert_settings_key requires a file path}"
    key="${2:?upsert_settings_key requires a key}"
    value="${3-}"
    mode="${4:-if-absent}"
    backup_suffix="${5:-}"

    if [ ! -f "${file}" ]; then
        echo "upsert_settings_key: ERROR: file not found: ${file}" >&2
        return 1
    fi

    local -a lines=()
    local _l
    while IFS= read -r _l || [ -n "${_l}" ]; do
        _l="${_l%$'\r'}"
        lines+=("${_l}")
    done < "${file}"

    local active_idx=-1 comment_idx=-1 i line stripped
    for (( i=0; i<${#lines[@]}; i++ )); do
        line="${lines[$i]}"
        if [ "${active_idx}" -lt 0 ]; then
            case "${line}" in
                "${key}="*) active_idx=$i ;;
            esac
        fi
        if [ "${comment_idx}" -lt 0 ]; then
            case "${line}" in
                '#'*)
                    stripped="${line#\#}"
                    stripped="${stripped#"${stripped%%[![:space:]]*}"}"
                    case "${stripped}" in
                        "${key}="*) comment_idx=$i ;;
                    esac
                    ;;
            esac
        fi
    done

    local new_line="${key}=${value}"
    local action=""
    local -a out=()

    if [ "${active_idx}" -ge 0 ]; then
        if [ "${mode}" != "replace" ]; then
            echo "upsert_settings_key: ${key} skipped (exists)"
            return 0
        fi
        if [ "${lines[$active_idx]}" = "${new_line}" ]; then
            echo "upsert_settings_key: ${key} unchanged (value already present)"
            return 0
        fi
        for (( i=0; i<${#lines[@]}; i++ )); do
            if [ "${i}" -eq "${active_idx}" ]; then
                out+=("${new_line}")
            else
                out+=("${lines[$i]}")
            fi
        done
        action="replaced"
    elif [ "${comment_idx}" -ge 0 ]; then
        for (( i=0; i<${#lines[@]}; i++ )); do
            out+=("${lines[$i]}")
            if [ "${i}" -eq "${comment_idx}" ]; then
                out+=("${new_line}")
            fi
        done
        action="inserted below commented example"
    else
        for (( i=0; i<${#lines[@]}; i++ )); do
            out+=("${lines[$i]}")
        done
        if [ "${#out[@]}" -gt 0 ] && [ -n "${out[$(( ${#out[@]} - 1 ))]}" ]; then
            out+=("")
        fi
        out+=("# Added by DAAF on $(date +%Y-%m-%d)")
        out+=("${new_line}")
        action="appended (new)"
    fi

    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] upsert_settings_key would write ${file}: ${action}"
        echo "[DRY-RUN]   line: ${new_line}"
        return 0
    fi

    if [ -n "${backup_suffix}" ] && [ ! -f "${file}${backup_suffix}" ]; then
        if ! cp -p "${file}" "${file}${backup_suffix}"; then
            echo "upsert_settings_key: ERROR: backup failed: ${file}${backup_suffix}" >&2
            return 1
        fi
    fi

    local payload="" ln
    for ln in "${out[@]}"; do
        payload="${payload}${ln}"$'\n'
    done

    local dir tmp
    dir="$(dirname "${file}")"
    tmp="${dir}/.daaf_upsert.$$.${RANDOM}"
    if ! cp -p "${file}" "${tmp}"; then
        echo "upsert_settings_key: ERROR: could not create temp file in ${dir}" >&2
        rm -f "${tmp}"
        return 1
    fi
    if ! printf '%s' "${payload}" > "${tmp}"; then
        echo "upsert_settings_key: ERROR: write failed: ${tmp}" >&2
        rm -f "${tmp}"
        return 1
    fi
    if ! mv -f "${tmp}" "${file}"; then
        echo "upsert_settings_key: ERROR: rename failed: ${tmp} -> ${file}" >&2
        rm -f "${tmp}"
        return 1
    fi

    echo "upsert_settings_key: ${key} ${action}"
    return 0
}

# --- Persist an env-origin update branch (shared by every success path) ---
# Writes PERSIST_BRANCH back to environment_settings.txt so future runs track it
# without re-exporting DAAF_BRANCH. Called from finish_update AND from the no-op
# "already up to date" success exits, which return before finish_update runs (the
# most common re-run case: `DAAF_BRANCH=x update` while already current). Every
# property of the original inline block is preserved: fires only when
# PERSIST_BRANCH is non-empty (env-origin *branch* only, never a tag or a file-
# origin value, so "never persist a tag" holds by construction), replace mode,
# .pre-update backup, skip-with-note when the settings file is absent.
# upsert_settings_key is itself DAAF_DRY_RUN gated (writes nothing in dry run);
# `|| true` keeps a persistence hiccup from failing a completed update. Guarded
# with ${PERSIST_BRANCH:-} because this runs under set -u and is dot-sourced under
# DAAF_TEST_MODE. Defined before the DAAF_TEST_MODE guard so it is available to
# finish_update (and the no-op exits) under test dot-source.
persist_branch_choice() {
    if [ -n "${PERSIST_BRANCH:-}" ]; then
        if [ -f "./environment_settings.txt" ]; then
            upsert_settings_key "./environment_settings.txt" "DAAF_BRANCH" "${PERSIST_BRANCH}" "replace" ".pre-update" || true
            if [ "${DAAF_DRY_RUN:-}" != "1" ]; then
                echo "Saved DAAF_BRANCH=${PERSIST_BRANCH} to environment_settings.txt for future updates."
            fi
        else
            echo "NOTE: DAAF_BRANCH=${PERSIST_BRANCH} was used for this update but not saved"
            echo "      (no environment_settings.txt). Copy environment_settings_example.txt to"
            echo "      persist it for future runs."
        fi
    fi
}

# --- Interrupted-update resume marker helpers ---
# A genuine merge/rebase conflict cannot be auto-resolved non-interactively, so
# the updater exits 1 mid-merge and asks the user to resolve, commit, and re-run.
# The re-run lands on an "already up to date" early exit (HEAD now == remote),
# which historically did tier-A-only sync and skipped rebuild detection, tier-B
# host-script sync, and the stash pop -- stranding the user on a stale image with
# the "DAAF update backup" stash still set aside. These helpers persist the
# pre-update HEAD across the interruption so the re-run can finish the journey.
#
# Marker path is inside the repo's own .git dir: invisible to `git status`,
# survives the merge, and is wiped by a reclone. Written via docker exec (the
# repo lives in the container). Defined before the DAAF_TEST_MODE guard so they
# are unit-testable and callable from finish_update under test dot-source.

# Persist OLD_HEAD + TIMESTAMP so a post-conflict re-run can resume. No-op under
# dry run (nothing real to write, and the dry-run docker mock would misread the
# exec). `|| true` so a write hiccup never trips the ERR trap.
write_resume_marker() {
    [ "${DAAF_DRY_RUN:-}" = "1" ] && return 0
    # Host builds the marker bytes, an in-container `cat` writes them. The sh arg
    # carries no embedded double quotes (the PS twin cannot -- PS 5.1 mangles them
    # in native argv -- so both twins share this stdin mechanism for parity).
    printf 'OLD_HEAD=%s\nTIMESTAMP=%s\n' "${OLD_HEAD}" "${TIMESTAMP}" \
        | docker compose exec -T daaf-docker \
        sh -c 'cat > /daaf/.git/daaf-update-resume' >/dev/null 2>&1 || true
}

# Delete the resume marker. Called from finish_update (the single success
# chokepoint) and when a corrupt marker is discovered at startup. No-op under dry
# run; `|| true` keeps it off the ERR trap.
clear_resume_marker() {
    [ "${DAAF_DRY_RUN:-}" = "1" ] && return 0
    docker compose exec -T daaf-docker \
        rm -f /daaf/.git/daaf-update-resume </dev/null >/dev/null 2>&1 || true
}

# Find the stash entry a prior interrupted run set aside. Echoes the stash@{N}
# ref of the FIRST stash whose message contains "DAAF update backup", or nothing
# if none exists (user already popped it, or there were no dirty files).
# Capture-then-parse -- never `| grep -q` a live producer (conventions lint rule 9).
# Bash 3.2 safe: no mapfile, no arrays.
_find_update_backup_stash() {
    local stash_list line ref
    stash_list=$(docker compose exec -T daaf-docker \
        git -C /daaf stash list </dev/null 2>/dev/null | tr -d '\r' || true)
    while IFS= read -r line; do
        case "${line}" in
            *"DAAF update backup"*)
                # A stash list line looks like: stash@{0}: On main: DAAF update...
                # so everything before the first ':' is the ref.
                ref="${line%%:*}"
                if [ -n "${ref}" ]; then
                    echo "${ref}"
                    return 0
                fi
                ;;
        esac
    done <<< "${stash_list}"
    return 0
}

# Finish an interrupted update that has now landed on an "already up to date"
# early exit (the resolved-and-committed merge left HEAD == remote). Restore the
# set-aside stash (if still present) exactly like the normal pop sites, then run
# finish_update against the recorded pre-update OLD_HEAD so tier A+B host-script
# sync AND rebuild detection execute against the true pre-update baseline.
resume_finalize() {
    local stash_ref
    stash_ref=$(_find_update_backup_stash)
    if [ -n "${stash_ref}" ]; then
        echo "Restoring your set-aside changes..."
        if ! docker compose exec -T daaf-docker \
            git -C /daaf stash pop "${stash_ref}" </dev/null; then
            if handle_stash_conflict; then
                finish_update "${OLD_HEAD}"
            else
                finish_update "${OLD_HEAD}" \
                    "Note: Uncommitted changes still need attention (see above)."
            fi
            return 0
        fi
    fi
    finish_update "${OLD_HEAD}"
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
# `docker compose ps -q daaf-docker` prints the running container's ID (empty
# when stopped), derived from the compose project rather than a hardcoded name.
RUNNING_CID=$(docker compose ps -q daaf-docker 2>/dev/null || true)

if [ -z "${RUNNING_CID}" ]; then
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

# Derive the container ID now that the container is guaranteed running. Used by
# `docker cp` in _sync_copy_one and by manual-recovery hints. `-q` (running only)
# is correct here because the preflight above ensures the container is up.
CONTAINER_ID=$(docker compose ps -q daaf-docker 2>/dev/null || true)

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
        # Capture the backup exit explicitly. Under this script's `set -euo pipefail`
        # an unguarded failed backup would abort the update abruptly with no
        # explanation; `|| BACKUP_EXIT=$?` defuses set -e so we can abort gracefully
        # with a clear message instead (mirrors migrate_daaf.ps1's gated abort). A
        # user who opted into a backup and had it fail must not have the update
        # proceed on a missing restore point; a DECLINED backup (the else path below)
        # still lets the update continue.
        BACKUP_EXIT=0
        DAAF_NESTED=1 bash backup_daaf.sh || BACKUP_EXIT=$?
        if [ "${BACKUP_EXIT}" -ne 0 ]; then
            echo ""
            echo "ERROR: Backup failed (exit code ${BACKUP_EXIT})."
            echo "The update will not proceed without a successful backup."
            echo "Please resolve the backup issue and re-run: bash update_daaf.sh"
            exit 1
        fi
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
# Resume detection (interrupted-update recovery)
# =====================================================================
# Runs after the pre-update HEAD is captured but before any branch-state
# decision. Two cases to handle when a prior run stopped on a genuine conflict:
#   1. A merge/rebase is STILL in progress -> the user has not finished
#      resolving. Guide them and exit 1, keeping the marker.
#   2. A resume marker exists and records a valid pre-update HEAD -> resume:
#      adopt the recorded OLD_HEAD so rebuild detection and tier-B host-script
#      sync run against the TRUE pre-update baseline (this run's HEAD is already
#      the post-merge HEAD, so check_build_changes keyed on it would see nothing).
# Skipped entirely under dry run: there is no real repo to probe, and the
# built-in dry-run docker mock would misread the MERGE_HEAD probe as HEAD.
RESUMING=false
if [ "${DAAF_DRY_RUN:-}" != "1" ]; then
    # Capture the in-progress probes, then test -- never `| grep -q` a live
    # producer (conventions lint rule 9). Use the canonical git filesystem markers:
    # .git/MERGE_HEAD exists only during an unresolved merge; rebase state lives
    # in .git/rebase-merge or .git/rebase-apply. (Filesystem probes, not
    # `rev-parse MERGE_HEAD`, so the probe strings carry no "rev-parse HEAD"
    # token that generic test mocks would false-match.)
    MERGE_IN_PROGRESS=$(docker compose exec -T daaf-docker \
        sh -c 'if [ -f /daaf/.git/MERGE_HEAD ]; then echo yes; fi' \
        </dev/null 2>/dev/null | tr -d '\r' || true)
    REBASE_IN_PROGRESS=$(docker compose exec -T daaf-docker \
        sh -c 'if [ -d /daaf/.git/rebase-merge ] || [ -d /daaf/.git/rebase-apply ]; then echo yes; fi' \
        </dev/null 2>/dev/null | tr -d '\r' || true)
    RESUME_MARKER=$(docker compose exec -T daaf-docker \
        sh -c 'cat /daaf/.git/daaf-update-resume 2>/dev/null' \
        </dev/null 2>/dev/null | tr -d '\r' || true)

    if [ -n "${MERGE_IN_PROGRESS}" ] || [ -n "${REBASE_IN_PROGRESS}" ]; then
        echo ""
        echo "-------------------------------------------"
        echo "  An update is still in progress"
        echo "-------------------------------------------"
        echo ""
        echo "A previous update stopped partway through resolving a conflict. Please"
        echo "finish that before running the updater again."
        echo ""
        echo "To finish resolving (inside the container):"
        echo "  bash run_daaf.sh bash"
        echo "  (edit the conflicting files to remove the <<<<<<< markers)"
        echo "  git add ."
        if [ -n "${MERGE_IN_PROGRESS}" ]; then
            echo "  git commit"
        else
            echo "  git rebase --continue"
        fi
        echo "  exit"
        echo ""
        echo "Then re-run:  bash update_daaf.sh"
        echo ""
        echo "Or to abort the update entirely (your research files are not affected):"
        if [ -n "${MERGE_IN_PROGRESS}" ]; then
            echo "  docker compose exec daaf-docker git -C /daaf merge --abort"
        else
            echo "  docker compose exec daaf-docker git -C /daaf rebase --abort"
        fi
        echo "  docker compose exec daaf-docker git -C /daaf reset --hard ${BACKUP_BRANCH}"
        echo ""
        exit 1
    fi

    if [ -n "${RESUME_MARKER}" ]; then
        # Parse OLD_HEAD from the marker (Bash 3.2 safe: no mapfile/arrays).
        MARKER_OLD_HEAD=""
        while IFS= read -r _rline; do
            case "${_rline}" in
                OLD_HEAD=*) MARKER_OLD_HEAD="${_rline#OLD_HEAD=}" ;;
            esac
        done <<< "${RESUME_MARKER}"

        if [ -n "${MARKER_OLD_HEAD}" ] && docker compose exec -T daaf-docker \
            git -C /daaf rev-parse --verify --quiet "${MARKER_OLD_HEAD}^{commit}" \
            </dev/null >/dev/null 2>&1; then
            RESUMING=true
            OLD_HEAD="${MARKER_OLD_HEAD}"
            echo ""
            echo "Resuming interrupted update..."
            echo ""
        else
            # Corrupt/invalid marker -> warn, delete, continue normally (fail-open).
            echo ""
            echo "NOTE: Found a leftover update marker with no valid restart point."
            echo "      Ignoring it and continuing normally."
            echo ""
            clear_resume_marker
        fi
    fi
fi

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
# PERSIST_BRANCH is set only when DAAF_BRANCH names a real branch AND came from
# the process environment (not the settings file). On a successful update it is
# written back to environment_settings.txt (in finish_update) so future runs
# track it without re-exporting. It is never set for a tag or for a file-origin
# value, so tags are never persisted.
PERSIST_BRANCH=""

if [ -n "${REMOTE_BRANCH}" ]; then
    # Classify the DAAF_BRANCH value against the remote: branch, tag, or unknown.
    if docker compose exec -T daaf-docker \
        git -C /daaf rev-parse --verify "${UPSTREAM_REMOTE}/${REMOTE_BRANCH}" \
        </dev/null >/dev/null 2>&1; then
        echo "Using branch: ${REMOTE_BRANCH} (from DAAF_BRANCH)"
        # Persist only an env-origin branch: a file-origin value is already in the
        # file, and a tag is handled below and never persisted.
        if [ "${DAAF_BRANCH_FROM_ENV}" = "1" ]; then
            PERSIST_BRANCH="${REMOTE_BRANCH}"
        fi
    elif docker compose exec -T daaf-docker \
        git -C /daaf rev-parse --verify "refs/tags/${REMOTE_BRANCH}" \
        </dev/null >/dev/null 2>&1; then
        # The value is a version tag, not a branch. Tags live in refs/tags/, not
        # refs/remotes/origin/, so the branch check above correctly failed.
        if [ "${DAAF_BRANCH_FROM_ENV}" = "1" ]; then
            # Env-origin tag: refuse informatively. The updater tracks a *branch*
            # to pull ongoing changes; a tag is a fixed snapshot the branch-
            # comparison machinery cannot advance (it silently no-ops as "already
            # up to date"). A tag is never persisted, so ongoing updates would
            # track the auto-detected default branch. Point the user at the one
            # supported way to move onto a release: re-install pinned to the tag.
            echo ""
            echo "'${REMOTE_BRANCH}' is a version tag, not a branch."
            echo "(You set it via DAAF_BRANCH in your environment.)"
            echo ""
            echo "The updater can only track a branch for ongoing updates. A tag is a"
            echo "fixed snapshot, so it cannot be followed for updates -- and a tag is"
            echo "never saved as your update branch."
            echo ""
            echo "To move this installation onto the '${REMOTE_BRANCH}' release, re-run the"
            echo "installer pinned to that tag (the supported path for this container-based"
            echo "layout):"
            echo "  DAAF_BRANCH=${REMOTE_BRANCH} bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/${UPSTREAM_REPO}/main/scripts/host/install.sh)\""
            echo ""
            echo "To keep receiving ongoing updates instead, unset DAAF_BRANCH (or set it"
            echo "to a branch). Updates then track the default branch (auto-detected"
            echo "main/master)."
            echo ""
            echo "No changes were made. Your research files are not affected."
            exit 1
        else
            # File-origin tag: a persisted tag would otherwise lock every future
            # update out. Warn, name the file and key, and fall back to the
            # auto-detected default branch for THIS run (do not hard-exit).
            echo ""
            echo "NOTE: DAAF_BRANCH in environment_settings.txt is set to '${REMOTE_BRANCH}',"
            echo "      which is a version tag, not a branch. Tags can't be tracked for"
            echo "      updates. Edit environment_settings.txt and set DAAF_BRANCH to a"
            echo "      branch (or remove it) to silence this. Continuing this run with the"
            echo "      auto-detected default branch."
            REMOTE_BRANCH=""
        fi
    else
        echo ""
        echo "The branch '${REMOTE_BRANCH}' (from DAAF_BRANCH) was not found on"
        echo "${UPSTREAM_REMOTE}."
        echo ""
        echo "Your installation is unchanged. Double-check the branch name and try"
        echo "again, or omit DAAF_BRANCH to use the default branch."
        exit 1
    fi
fi

if [ -z "${REMOTE_BRANCH}" ]; then
    # Auto-detect: try main, then master. Reached when DAAF_BRANCH was unset, or
    # when a file-origin tag was cleared just above.
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
    # A resume run lands here once the user resolved and committed a conflict
    # from the interrupted run (HEAD now == remote). Do NOT take the tier-A-only
    # exit -- restore the set-aside stash and run tier A+B sync + rebuild
    # detection against the recorded pre-update OLD_HEAD, which the interrupted
    # run never got to. finish_update clears the resume marker.
    if [ "${RESUMING}" = true ]; then
        resume_finalize
        exit 0
    fi
    # Even when there is nothing to pull, run the existence-heal sync so host
    # scripts a prior update missed (e.g., a file added in a release the user
    # updated across) are delivered now. Called with no old_head so only the
    # cheap tier-A (missing-file) pass runs -- no diff, no changed-file copies.
    sync_host_scripts
    # Persist an env-origin branch even on this no-op success: this exits before
    # finish_update, and re-running with DAAF_BRANCH set while already current is
    # the most common case where the choice would otherwise never be saved.
    persist_branch_choice
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
    # Resume run: the resolved-and-committed merge on '${CURRENT_BRANCH}' now
    # contains all of ${UPSTREAM_REMOTE}/${REMOTE_BRANCH} (BEHIND=0), so we land
    # here. Finish the interrupted journey instead of the tier-A-only exit --
    # restore the stash and run tier A+B sync + rebuild detection against the
    # recorded pre-update OLD_HEAD. finish_update clears the resume marker.
    if [ "${RESUMING}" = true ]; then
        resume_finalize
        exit 0
    fi
    # Existence-heal sync (tier A only) so host scripts a prior update missed
    # are delivered even when there is nothing new to pull. See the note on the
    # default-branch up-to-date path above.
    sync_host_scripts
    # Persist an env-origin branch on this no-op success too (exits before
    # finish_update) -- see the default-branch up-to-date path above.
    persist_branch_choice
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
            # Persist a resume marker so a post-resolution re-run finishes the
            # remaining steps (stash restore + host-script sync + rebuild check).
            write_resume_marker
            if [ "${STASHED}" = true ]; then
                echo ""
                echo "Your uncommitted changes are safely set aside. After you resolve"
                echo "the conflicts and commit, re-run the updater and it will restore"
                echo "them and finish the remaining steps automatically:"
                echo "  bash update_daaf.sh"
                echo "(Or restore manually: docker compose exec daaf-docker git -C /daaf stash pop)"
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
    # A resume run can land here on the DEFAULT branch: the user resolved and
    # committed a conflict from the interrupted run, so HEAD is now a merge
    # commit and the up-to-date hash check above no longer matches -- BEHIND=0
    # but AHEAD>0 (the local merge/customization commits). Finish the interrupted
    # journey instead of re-showing the merge/rebase/abort menu, which would be
    # spurious here and would strand the set-aside "DAAF update backup" stash
    # (the tree is now clean, so STASHED would be false and the stash never
    # popped). resume_finalize pops the stash if present and runs tier A+B sync +
    # rebuild detection against the recorded pre-update OLD_HEAD; finish_update
    # clears the resume marker. See the two "already up to date" resume routes.
    if [ "${RESUMING}" = true ]; then
        echo ""
        echo "Detected an interrupted update -- finishing it now."
        resume_finalize
        # Rare corner: new upstream commits arrived between the conflict and this
        # re-run. Always finish the interrupted update first, never mix it with a
        # fresh pull -- so tell the user to re-run for the new commits.
        if [ "${BEHIND}" -gt 0 ]; then
            echo ""
            echo "The interrupted update was completed first. New updates are now"
            echo "available -- run the updater again to get them:"
            echo "  bash update_daaf.sh"
        fi
        exit 0
    fi
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
                # Persist a resume marker so a post-resolution re-run finishes
                # the remaining steps (stash restore + sync + rebuild check).
                write_resume_marker
                if [ "${STASHED}" = true ]; then
                    echo ""
                    echo "Your uncommitted changes are safely set aside. After you resolve"
                    echo "the conflicts and commit, re-run the updater and it will restore"
                    echo "them and finish the remaining steps automatically:"
                    echo "  bash update_daaf.sh"
                    echo "(Or restore manually: docker compose exec daaf-docker git -C /daaf stash pop)"
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
                # Persist a resume marker so a post-resolution re-run finishes
                # the remaining steps (stash restore + sync + rebuild check).
                write_resume_marker
                if [ "${STASHED}" = true ]; then
                    echo ""
                    echo "Your uncommitted changes are safely set aside. After you resolve"
                    echo "the conflicts and commit, re-run the updater and it will restore"
                    echo "them and finish the remaining steps automatically:"
                    echo "  bash update_daaf.sh"
                    echo "(Or restore manually: docker compose exec daaf-docker git -C /daaf stash pop)"
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
