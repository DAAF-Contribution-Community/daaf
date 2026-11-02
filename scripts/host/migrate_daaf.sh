#!/usr/bin/env bash
# ============================================================================
# DAAF Migration Script (macOS / Linux)
# ============================================================================
# Sets up an older DAAF installation (one without update_daaf.sh) so the updater
# works.
#
# This script is for users who installed DAAF before update_daaf.sh existed.
# It downloads the host utility scripts, backs up the volume, detects your
# installation era (git clone vs ZIP download), and grafts your local git
# history onto the upstream repository so that update_daaf.sh works going
# forward.
#
# Usage (one-liner):
#   curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/migrate_daaf.sh | bash
#
# Or download and run:
#   curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/migrate_daaf.sh -o migrate_daaf.sh
#   bash migrate_daaf.sh
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection
#   - An existing DAAF installation (Docker volume daaf_daaf-data exists)
#
# This script is idempotent -- safe to run multiple times. If the migration
# has already been completed, it will detect that and skip ahead.
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Interactivity detection: use /dev/tty instead of stdin (fd 0).
# When users run `curl ... | bash`, stdin is the pipe -- but the user's
# terminal is still available at /dev/tty. CI runners either lack /dev/tty
# or it is not a real terminal, so this naturally gives the right answer.
#
# DAAF_NESTED is separate: it suppresses the exit prompt (so nested
# scripts don't double-pause) but does NOT suppress interactive prompts.
IS_INTERACTIVE=false
if [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    IS_INTERACTIVE=true
fi

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script).
if [ "${IS_INTERACTIVE}" = "true" ] && [ -z "${DAAF_NESTED:-}" ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Configuration ---
REPO="DAAF-Contribution-Community/daaf"
BRANCH="${DAAF_BRANCH:-main}"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
# The documented one-liner, printed wherever the user is told to run the migration
# again: a `curl ... | bash` run leaves no migrate_daaf.sh on disk to re-run, and
# the updater does not sync it to the host.
MIGRATE_RERUN="curl -fsSL ${RAW_BASE}/scripts/host/migrate_daaf.sh | bash"
# Migration deliberately targets the DEFAULT data volume "daaf_daaf-data" and does
# NOT honor DAAF_PROJECT_NAME or the DAAF_DATA_VOLUME_NAME override. This tool is a
# one-time bootstrap for LEGACY installs that predate custom project names and the
# data-volume override -- those installs always used the single hardcoded default
# name, so deriving or overriding it here would only risk missing the volume the
# migration is meant to find.
VOLUME_NAME="daaf_daaf-data"
# The helper image of the volume ownership repair (section 4c), PINNED by digest:
# busybox 1.37.0, multi-arch OCI index (amd64, arm64/v8 and others), the tested digest
# below. Pinned by digest: the untagged `busybox` image moved to busybox 1.38.0,
# which DAAF has not tested (upstream image move observed 2026-09-23). The same
# string is in backup_daaf.{sh,ps1},
# restore_from_backup.{sh,ps1}, migrate_daaf.{sh,ps1} and docker-compose.yml (daaf-init):
# keep every copy identical (a parity test enforces it).
BUSYBOX_IMAGE='busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'
CONTAINER_NAME=""
BACKUP_COMPLETED=false
IS_FORK=false

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"volume inspect"*) return 0 ;;
            *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-dry-run-1" ;;
            *"inspect --format"*"State.Status"*) echo "running" ;;
            *"exec"*"true"*) return 0 ;;
            *"exec"*"test -f"*) return 0 ;;
            *"exec"*"config"*"safe.directory"*) return 0 ;;
            *"exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
            *"exec"*"fetch"*) return 0 ;;
            *"exec"*"branch --set-upstream"*) return 0 ;;
            *)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
    curl() {
        # Dry run writes nothing: print the [DRY-RUN] line and succeed WITHOUT
        # creating any files or directories. HOST_DIR resolves to the current
        # folder when it holds a docker-compose.yml, so a mock that created
        # files would leave empty stubs there. The dry-run write sites below
        # (chmod, compose update, nested backup) are gated so the whole flow
        # still runs.
        echo "[DRY-RUN] curl $*" >&2
        return 0
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
    echo "Your research files and data are safe -- the migration only changes" >&2
    echo "framework git history, not your research/ folder." >&2
    echo "" >&2
    if [ "${BACKUP_COMPLETED}" = true ]; then
        echo "A backup was created before any changes were made." >&2
    else
        echo "No changes were made to your installation." >&2
    fi
    echo "" >&2
    echo "Most likely causes:" >&2
    echo "  - Docker Desktop stopped (laptop sleep, lid closed)" >&2
    echo "  - Internet connection dropped during download" >&2
    echo "  - A temporary Docker glitch" >&2
    echo "" >&2
    echo "To try again:" >&2
    echo "  1. Make sure Docker Desktop is running" >&2
    echo "  2. From the same folder, run the migration command again:" >&2
    echo "       ${MIGRATE_RERUN}" >&2
    echo "     (It is safe to re-run -- it will pick up where it left off.)" >&2
    echo "" >&2
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

# Run a git command inside the container (strips carriage returns)
container_git() {
    docker exec "${CONTAINER_NAME}" git -C /daaf "$@" </dev/null 2>/dev/null | tr -d '\r'
}

# Run a git command inside the container, allowing stderr through
container_git_verbose() {
    docker exec "${CONTAINER_NAME}" git -C /daaf "$@" </dev/null | tr -d '\r'
}

# Run a shell command inside the container
container_exec() {
    docker exec "${CONTAINER_NAME}" "$@" </dev/null
}

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/migrate_daaf.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# =====================================================================
# Portable concurrent-run lock (mkdir)
# =====================================================================
# Prevent two instances from operating on the same container simultaneously.
# mkdir is atomic on all POSIX systems (Linux, macOS, Git Bash on Windows).
# The lock directory is cleaned up via the EXIT trap when the script exits.
LOCK_DIR="/tmp/daaf-migrate.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "ERROR: Another instance of migrate_daaf is already running." >&2
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
echo "  DAAF Migration"
echo "=========================================="
echo ""
echo "This script sets up an older DAAF installation (one without"
echo "update_daaf.sh) so that the updater works."
echo ""

# =====================================================================
# 1. PREFLIGHT
# =====================================================================
echo "-------------------------------------------"
echo "  Preflight checks"
echo "-------------------------------------------"
echo ""

# --- Docker installed ---
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal."
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# --- Docker running ---
if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start it and try again."
    exit 1
fi

echo "Docker is running."

# --- Volume exists ---
if ! docker volume inspect "${VOLUME_NAME}" &> /dev/null; then
    echo ""
    echo "ERROR: Docker volume '${VOLUME_NAME}' not found."
    echo ""
    echo "This script is for migrating an existing DAAF installation."
    echo "If you haven't installed DAAF yet, use the installer instead:"
    echo "  curl -fsSL https://raw.githubusercontent.com/${REPO}/${BRANCH}/scripts/host/install.sh | bash"
    exit 1
fi

echo "Found DAAF volume: ${VOLUME_NAME}"

# --- Determine host directory ---
# If docker-compose.yml exists in the current directory, use it.
# Otherwise, create daaf-docker/ as install.sh would.
if [ -f "docker-compose.yml" ]; then
    HOST_DIR="$(pwd)"
    echo "Using current directory: ${HOST_DIR}"
else
    HOST_DIR="$(pwd)/daaf-docker"
    echo "Will create host directory: ${HOST_DIR}"
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] Would create host directory: ${HOST_DIR}"
    else
        mkdir -p "${HOST_DIR}"
    fi
fi

echo ""

# =====================================================================
# 2. DOWNLOAD HOST SCRIPTS
# =====================================================================
echo "-------------------------------------------"
echo "  Downloading host scripts"
echo "-------------------------------------------"
echo ""

echo "Downloading utility scripts from GitHub..."

DOWNLOAD_FAILED=false

for FILE in daaf.sh daaf_lib.sh backup_daaf.sh restore_from_backup.sh rebuild_daaf.sh update_daaf.sh run_daaf.sh view_logs.sh view_notebooks.sh view_quarto.sh run_vscode.sh environment_settings_example.txt README.txt; do
    if curl -fsSL "${RAW_BASE}/scripts/host/${FILE}" -o "${HOST_DIR}/${FILE}"; then
        echo "  Downloaded: ${FILE}"
    else
        echo "  FAILED: ${FILE}"
        DOWNLOAD_FAILED=true
    fi
done

if [ "${DOWNLOAD_FAILED}" = true ]; then
    echo ""
    echo "ERROR: Failed to download one or more utility scripts."
    echo "Please check your internet connection and try again."
    exit 1
fi

# Download Dockerfile and docker-compose.yml if not already present
if [ ! -f "${HOST_DIR}/Dockerfile" ]; then
    if curl -fsSL "${RAW_BASE}/Dockerfile" -o "${HOST_DIR}/Dockerfile"; then
        echo "  Downloaded: Dockerfile"
    else
        echo ""
        echo "ERROR: Failed to download Dockerfile."
        echo "Please check your internet connection and try again."
        exit 1
    fi
fi

if [ ! -f "${HOST_DIR}/docker-compose.yml" ]; then
    if curl -fsSL "${RAW_BASE}/docker-compose.yml" -o "${HOST_DIR}/docker-compose.yml"; then
        echo "  Downloaded: docker-compose.yml"
    else
        echo ""
        echo "ERROR: Failed to download docker-compose.yml."
        echo "Please check your internet connection and try again."
        exit 1
    fi
else
    # Even if docker-compose.yml exists, update it if it lacks a project-name
    # declaration (v1.0.0 installations shipped without one). The predicate is
    # "does the compose file already set a top-level `name:` key" -- matching
    # any `^name: ` line. Both the legacy literal `name: daaf` and the current
    # parameterized `name: ${DAAF_PROJECT_NAME:-daaf}` therefore count as
    # up-to-date. Matching any `name:` line keeps the check from re-downloading a
    # current compose file and writing a .pre-migrate backup on every run.
    if ! grep -q '^name: ' "${HOST_DIR}/docker-compose.yml"; then
        echo ""
        echo "  Updating docker-compose.yml to current version..."
        if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
            echo "  [DRY-RUN] Would update docker-compose.yml (backing up to docker-compose.yml.pre-migrate)"
        else
            cp "${HOST_DIR}/docker-compose.yml" "${HOST_DIR}/docker-compose.yml.pre-migrate"
            if curl -fsSL "${RAW_BASE}/docker-compose.yml" -o "${HOST_DIR}/docker-compose.yml"; then
                echo "  Updated: docker-compose.yml (old version saved as docker-compose.yml.pre-migrate)"
            else
                echo "  WARNING: Could not download updated docker-compose.yml. Restoring original."
                mv "${HOST_DIR}/docker-compose.yml.pre-migrate" "${HOST_DIR}/docker-compose.yml"
            fi
        fi
    fi
fi

# Make all .sh files executable
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    echo "[DRY-RUN] Would make host scripts executable (chmod +x ${HOST_DIR}/*.sh)"
else
    chmod +x "${HOST_DIR}"/*.sh 2>/dev/null || true
fi

echo ""
echo "All scripts downloaded to: ${HOST_DIR}/"
echo ""

# =====================================================================
# 3. BACKUP
# =====================================================================
echo "-------------------------------------------"
echo "  Backup"
echo "-------------------------------------------"
echo ""
echo "Before making any changes, a full backup of your DAAF volume will"
echo "be created. This protects your research data and local history."
echo ""

if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    # Dry-run creates nothing, so there is no downloaded backup_daaf.sh to run
    # (the curl mock writes nothing). Print the step and skip the nested
    # call; keep BACKUP_COMPLETED=true so the rest of the dry-run flow matches
    # the real path's post-backup state.
    echo "[DRY-RUN] Would run backup_daaf.sh in ${HOST_DIR} to back up the Docker volume"
    BACKUP_COMPLETED=true
else
    ORIGINAL_DIR="$(pwd)"
    cd "${HOST_DIR}"
    # Capture the backup exit explicitly. Under this script's `set -euo pipefail` an
    # unguarded failed backup would abort the migration abruptly with no explanation;
    # `|| BACKUP_EXIT=$?` defuses set -e so we can abort gracefully with a clear
    # message instead. This backup is mandatory (not prompted), so any failure stops
    # the migration -- mirroring migrate_daaf.ps1's existing gated abort.
    BACKUP_EXIT=0
    DAAF_NESTED=1 bash backup_daaf.sh || BACKUP_EXIT=$?
    cd "${ORIGINAL_DIR}"
    if [ "${BACKUP_EXIT}" -ne 0 ]; then
        echo ""
        echo "ERROR: Backup failed (exit code ${BACKUP_EXIT})."
        echo "The migration will not proceed without a successful backup."
        echo "Please resolve the backup issue, then run the migration command again:"
        echo "  ${MIGRATE_RERUN}"
        exit 1
    fi
    BACKUP_COMPLETED=true
fi

echo ""

# =====================================================================
# 4. START CONTAINER (if not running)
# =====================================================================
echo "-------------------------------------------"
echo "  Starting container"
echo "-------------------------------------------"
echo ""

# Discover container dynamically from the volume
ALL_CONTAINERS=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}')
CONTAINER_COUNT=$(echo "${ALL_CONTAINERS}" | grep -c . || true)
CONTAINER_COUNT="${CONTAINER_COUNT:-0}"
CONTAINER_NAME=$(echo "${ALL_CONTAINERS}" | head -1)

if [ "${CONTAINER_COUNT}" -gt 1 ]; then
    echo "WARNING: Multiple containers found using the DAAF volume:"
    echo "${ALL_CONTAINERS}" | sed 's/^/  /'
    echo ""
    echo "Using the first one: ${CONTAINER_NAME}"
    echo "If this is wrong, stop the other containers and run the migration"
    echo "command again:"
    echo "  ${MIGRATE_RERUN}"
    echo ""
fi

if [ -n "${CONTAINER_NAME}" ]; then
    echo "Found existing container: ${CONTAINER_NAME}"

    # Check if it's running
    CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
    if [ "${CONTAINER_STATE}" != "running" ]; then
        echo "Container is ${CONTAINER_STATE}. Starting it..."
        docker start "${CONTAINER_NAME}" >/dev/null 2>&1 || true

        # Wait for readiness
        RETRIES=0
        MAX_RETRIES=30
        until docker exec "${CONTAINER_NAME}" true </dev/null 2>/dev/null; do
            RETRIES=$((RETRIES + 1))
            if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
                echo ""
                echo "ERROR: Container did not become ready within 60 seconds."
                echo "Try restarting Docker Desktop, then run the migration command again:"
                echo "  ${MIGRATE_RERUN}"
                exit 1
            fi
            sleep 2
        done
        echo "Container started."
    else
        echo "Container is already running."
    fi
else
    echo "No existing container found. Starting one with docker compose..."

    ORIGINAL_DIR_COMPOSE="$(pwd)"
    cd "${HOST_DIR}"

    if ! docker compose up -d; then
        echo ""
        echo "ERROR: Failed to start the DAAF container."
        echo ""
        echo "Common causes:"
        echo "  - Another program is using the same ports"
        echo "  - Docker Desktop needs more memory (Settings > Resources)"
        echo ""
        echo "Try restarting Docker Desktop, then run the migration command again:"
        echo "  ${MIGRATE_RERUN}"
        cd "${ORIGINAL_DIR_COMPOSE}"
        exit 1
    fi

    # After docker compose up, discover the container name
    CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
    if [ -z "${CONTAINER_NAME}" ]; then
        echo "ERROR: Container started but could not be found."
        echo "Try restarting Docker Desktop, then run the migration command again:"
        echo "  ${MIGRATE_RERUN}"
        cd "${ORIGINAL_DIR_COMPOSE}"
        exit 1
    fi

    cd "${ORIGINAL_DIR_COMPOSE}"

    # Wait for readiness
    RETRIES=0
    MAX_RETRIES=30
    until docker exec "${CONTAINER_NAME}" true </dev/null 2>/dev/null; do
        RETRIES=$((RETRIES + 1))
        if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
            echo ""
            echo "ERROR: Container started but is not responding after 60 seconds."
            echo "Try restarting Docker Desktop, then run the migration command again:"
            echo "  ${MIGRATE_RERUN}"
            exit 1
        fi
        sleep 2
    done
    echo "Container started: ${CONTAINER_NAME}"
fi

echo ""

# --- Verify DAAF is in the container ---
if ! container_exec test -f /daaf/CLAUDE.md; then
    echo "ERROR: DAAF does not appear to be installed in the container."
    echo "The volume exists but /daaf/CLAUDE.md was not found."
    echo ""
    echo "If this is a fresh installation, use the installer instead:"
    echo "  curl -fsSL https://raw.githubusercontent.com/${REPO}/${BRANCH}/scripts/host/install.sh | bash"
    exit 1
fi

echo "DAAF installation verified in container."
echo ""

# =====================================================================
# 4b. GIT safe.directory EXEMPTION (before any in-container git op)
# =====================================================================
# DAAF v1.0.0 volumes are owned by root while the v1.0.0 image runs git as its
# non-root 'appuser', so git 2.35.2 and later refuses the repository:
#     fatal: detected dubious ownership in repository at '/daaf'
# container_git hides stderr, so every git step below (era detection, fetch,
# graft, tracking) would silently return nothing. One global safe.directory
# entry, added before the first in-container git call, covers every install
# type: the exec user, the ${CONTAINER_NAME} container and the /daaf path are the
# same in all of them, and the entry is a no-op where ownership already matches.
# The --get-all check keeps a re-run from adding a duplicate entry.
echo "-------------------------------------------"
echo "  Git safe.directory exemption"
echo "-------------------------------------------"
echo ""
echo "Allowing git to operate on /daaf inside the container..."

# Capture-then-test (conventions lint 9: never pipe a LIVE command into grep -q;
# echo of an already-captured value is the sanctioned form). git config exits 1
# when the key is unset, so tolerate that with || true.
SAFE_DIR_EXISTING=$(container_exec git config --global --get-all safe.directory 2>/dev/null | tr -d '\r' || true)
if echo "${SAFE_DIR_EXISTING}" | grep -qx '/daaf'; then
    echo "  Already configured (safe.directory already lists /daaf)."
else
    # container_exec (unlike container_git) lets stderr through, so a genuine
    # config-add failure is visible rather than swallowed.
    if container_exec git config --global --add safe.directory /daaf; then
        echo "  Configured: safe.directory -> /daaf"
    else
        echo ""
        echo "ERROR: Could not configure the git safe.directory exemption for /daaf"
        echo "inside the container."
        echo ""
        echo "Modern git refuses to operate on a repository owned by a different user"
        echo "than the one running git, unless /daaf is listed as a safe.directory."
        echo "Every git step below would otherwise fail silently, so the migration"
        echo "cannot proceed until this is resolved."
        echo ""
        echo "This usually means the container's git user has no writable home"
        echo "directory. Try restarting Docker Desktop, then run the migration"
        echo "command again:"
        echo "  ${MIGRATE_RERUN}"
        exit 1
    fi
fi

echo ""

# =====================================================================
# 4c. VOLUME OWNERSHIP REPAIR (same chown as daaf-init, before any git write)
# =====================================================================
# DAAF v1.0.0 copied the repository into the volume with `busybox cp -a`, which
# keeps root ownership on Docker Desktop, and its compose file has no ownership
# repair (DAAF v2.0.0 added the daaf-init service for this). The container runs
# as uid 1000 with all capabilities dropped, so every git write below (fetch,
# set-upstream, the offered update's merge) fails with EPERM; safe.directory
# (4b) fixes the read refusal but not write access. Run the chown -R 1000:1000
# that daaf-init runs at every start; it is a no-op where ownership is already
# correct. On failure, warn and continue: the git steps then fail with this
# diagnosis already printed.
echo "-------------------------------------------"
echo "  Volume ownership repair"
echo "-------------------------------------------"
echo ""
echo "Repairing /daaf ownership for the container user (uid 1000)..."
if docker run --rm -v "${VOLUME_NAME}:/daaf" "${BUSYBOX_IMAGE}" chown -R 1000:1000 /daaf; then
    echo "  Ownership repaired: ${VOLUME_NAME} -> 1000:1000 (the same repair newer"
    echo "  installations run at every start)"
else
    echo ""
    echo "WARNING: Could not repair ownership of the DAAF volume (${VOLUME_NAME})."
    echo "On a v1.0.0-era installation the volume payload is typically owned by"
    echo "root, which blocks the container's non-root user from writing -- the"
    echo "git steps below may fail. Newer installations already have correct"
    echo "ownership (their compose repairs it on every startup), so this warning"
    echo "is harmless there. Continuing..."
fi

echo ""

# =====================================================================
# 4d. GIT IDENTITY (before any commit-creating git op)
# =====================================================================
# Images from DAAF v1.0.0 set no git identity (no entrypoint; git is installed
# bare); later images set user.email "daaf@local" and user.name "DAAF Container".
# Without an identity git refuses to create commits ("Please tell me who you
# are"), so the stash and merge of the update offered below would fail on a
# v1.0.0 container that has not been rebuilt. Set the same identity repo-local,
# and only when user.email is empty, so a user's own identity is never
# replaced; repo-local config lives in the volume and survives a rebuild. On
# failure, warn and continue, as in 4c.
echo "-------------------------------------------"
echo "  Git identity"
echo "-------------------------------------------"
echo ""
echo "Checking for a git identity in /daaf..."
# Capture-then-test (lint 9); git config exits 1 when unset -- tolerate.
GIT_EMAIL_EXISTING=$(container_exec git -C /daaf config user.email 2>/dev/null | tr -d '\r' || true)
if [ -n "${GIT_EMAIL_EXISTING}" ]; then
    echo "  Already configured (user.email: ${GIT_EMAIL_EXISTING})."
else
    if container_exec git -C /daaf config user.email "daaf@local" \
       && container_exec git -C /daaf config user.name "DAAF Container"; then
        echo "  Configured: repo-local git identity (daaf@local / DAAF Container)"
    else
        echo ""
        echo "WARNING: Could not configure a git identity in /daaf. Installations from"
        echo "DAAF v1.0.0 have none, and git refuses to create commits (including"
        echo "the update's stash and merge) without it. If a later step fails with"
        echo "'Please tell me who you are', run these two commands, then run the"
        echo "migration command again:"
        echo "  docker exec ${CONTAINER_NAME} git -C /daaf config user.email daaf@local"
        echo "  docker exec ${CONTAINER_NAME} git -C /daaf config user.name \"DAAF Container\""
        echo "  ${MIGRATE_RERUN}"
        echo "Continuing..."
    fi
fi

echo ""

# =====================================================================
# 5. DETECT ERA
# =====================================================================
echo "-------------------------------------------"
echo "  Detecting installation type"
echo "-------------------------------------------"
echo ""

ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || true)

if [ -n "${ORIGIN_URL}" ] && echo "${ORIGIN_URL}" | grep -qi "${REPO}"; then
    DETECTED_ERA="1"
    echo "Detected: clone-based installation (remote already configured)"
    echo "Remote URL: ${ORIGIN_URL}"
elif [ -n "${ORIGIN_URL}" ]; then
    # Remote exists but points somewhere unexpected (likely a fork)
    DETECTED_ERA="1"
    IS_FORK=true
    echo "Detected: clone-based installation (remote already configured)"
    echo "Remote URL: ${ORIGIN_URL}"
    echo ""
    echo "NOTE: Your remote points to a location other than the official DAAF"
    echo "repository. The migration will proceed, but you may want to verify"
    echo "this is correct."
else
    DETECTED_ERA="2"
    echo "Detected: ZIP-based installation (no remote configured)"
    echo "Your local history will be connected to the official DAAF timeline"
    echo "so that future updates can merge cleanly with your work."
fi

echo ""

# =====================================================================
# 6a. ERA 1 PATH (v1.0.0 -- remote exists)
# =====================================================================
if [ "${DETECTED_ERA}" = "1" ]; then
    echo "-------------------------------------------"
    echo "  Fetching upstream history"
    echo "-------------------------------------------"
    echo ""

    echo "Running git fetch origin..."
    if container_git_verbose fetch origin; then
        echo "Fetch complete."
    else
        echo ""
        echo "ERROR: Failed to fetch from origin."
        echo ""
        echo "Common causes:"
        echo "  - No internet connection"
        echo "  - GitHub may be experiencing an outage"
        echo ""
        echo "Once the issue is resolved, run the migration command again:"
        echo "  ${MIGRATE_RERUN}"
        exit 1
    fi

    # Ensure tracking is set up. Best-effort: a missing local 'main' branch is
    # non-fatal. container_git_verbose lets git's error through, and the success
    # line prints only when set-upstream succeeded.
    if container_git_verbose branch --set-upstream-to=origin/main main; then
        echo "Tracking set: main -> origin/main"
    else
        # Report which precondition failed: a single-branch or tag-pinned clone
        # has no origin/main remote-tracking ref, which needs a different fix
        # from a missing local main.
        if container_exec git -C /daaf rev-parse --verify --quiet refs/remotes/origin/main >/dev/null 2>&1; then
            echo "NOTE: Could not set upstream tracking (no local 'main' branch on this install)."
        else
            echo "NOTE: Could not set upstream tracking (no 'origin/main' remote-tracking ref on this install -- e.g. a single-branch or tag-pinned clone)."
        fi
    fi

    # --- For fork users: add upstream remote for official updates ---
    if [ "${IS_FORK}" = true ]; then
        EXISTING_UPSTREAM=$(container_git remote get-url upstream 2>/dev/null || true)
        if [ -z "${EXISTING_UPSTREAM}" ]; then
            echo ""
            echo "Your 'origin' remote points to a fork. Adding 'upstream' remote"
            echo "for official DAAF updates..."
            if container_git_verbose remote add upstream "https://github.com/${REPO}.git"; then
                echo "Fetching upstream history..."
                if container_git_verbose fetch upstream; then
                    echo "Fetch complete."
                else
                    echo ""
                    echo "WARNING: Could not fetch from upstream. The 'upstream' remote was"
                    echo "added but the fetch failed. You can retry later:"
                    echo "  cd \"${HOST_DIR}\""
                    echo "  bash run_daaf.sh bash"
                    echo "  git fetch upstream"
                    echo "  exit"
                fi
            else
                echo ""
                echo "WARNING: Could not add 'upstream' remote. You can add it"
                echo "manually later:"
                echo "  cd \"${HOST_DIR}\""
                echo "  bash run_daaf.sh bash"
                echo "  git remote add upstream https://github.com/${REPO}.git"
                echo "  git fetch upstream"
                echo "  exit"
            fi
        else
            echo ""
            echo "'upstream' remote already configured: ${EXISTING_UPSTREAM}"
        fi
    fi

    echo ""
    if [ "${IS_FORK}" = true ]; then
        echo "Migration complete. Your installation is connected to your fork"
        echo "(origin) and the official DAAF repository (upstream)."
        echo ""
        echo "update_daaf.sh will pull official updates from 'upstream' and merge"
        echo "them with your fork's changes."
    else
        echo "Migration complete. Your installation is connected to upstream"
        echo "and update_daaf.sh will work immediately."
    fi
    echo ""

# =====================================================================
# 6b. ERA 2 PATH (v2.0.0+ -- no remote, need graft)
# =====================================================================
else
    echo "-------------------------------------------"
    echo "  Connecting to upstream repository"
    echo "-------------------------------------------"
    echo ""

    # --- Check if remote was already added (idempotent) ---
    EXISTING_ORIGIN=$(container_git remote get-url origin 2>/dev/null || true)
    if [ -n "${EXISTING_ORIGIN}" ]; then
        echo "Remote 'origin' already exists: ${EXISTING_ORIGIN}"
        echo "Skipping remote add (previous migration attempt detected)."
    else
        echo "Adding remote origin..."
        container_git_verbose remote add origin "https://github.com/${REPO}.git"
        echo "Remote added."
    fi

    echo ""

    # --- Fetch full history ---
    echo "Fetching upstream history (this may take a moment)..."
    if container_git_verbose fetch origin; then
        echo "Fetch complete."
    else
        echo ""
        echo "ERROR: Failed to fetch from origin."
        echo ""
        echo "Common causes:"
        echo "  - No internet connection"
        echo "  - GitHub may be experiencing an outage"
        echo ""
        echo "Once the issue is resolved, run the migration command again:"
        echo "  ${MIGRATE_RERUN}"
        exit 1
    fi

    echo ""

    # --- Find the initial (root) commit ---
    INITIAL_COMMITS=$(container_git_verbose rev-list --max-parents=0 HEAD || true)

    if [ -z "${INITIAL_COMMITS}" ]; then
        echo ""
        echo "ERROR: Could not find git history in the container."
        echo "The volume exists but no git repository was found at /daaf/."
        echo ""
        echo "If this is a fresh installation, use the installer instead:"
        echo "  curl -fsSL https://raw.githubusercontent.com/${REPO}/${BRANCH}/scripts/host/install.sh | bash"
        exit 1
    fi

    # If multiple root commits exist, use the first (oldest) one
    INITIAL_COMMIT=$(echo "${INITIAL_COMMITS}" | tail -1)
    ROOT_COUNT=$(echo "${INITIAL_COMMITS}" | grep -c . || true)
    ROOT_COUNT="${ROOT_COUNT:-0}"
    if [ "${ROOT_COUNT}" -gt 1 ]; then
        echo "NOTE: Found ${ROOT_COUNT} root commits. Using the oldest one"
        echo "      (${INITIAL_COMMIT:0:12}) for graft matching."
        echo ""
    fi

    # --- Check if graft is already in place (idempotent) ---
    # Three-leg probe (replace-first, shallow-guarded). The naive
    # `rev-list --max-parents=0 | cat-file | grep -c '^parent '` detector is
    # unreliable: after a prior graft, rev-list walks THROUGH the replace ref to
    # upstream's genuine parentless root (parent count 0 -> false "no graft yet" ->
    # redundant re-graft); on a shallow clone, rev-list returns the shallow
    # boundary commit whose object still lists parents (false "graft in place" ->
    # graft skipped). The migrate twins are the only creators of git replace refs
    # in a DAAF volume, so a replace ref's existence is a sound "already grafted"
    # marker that sidesteps both failure modes.
    #
    # Leg 1 (replace): capture `git replace -l` and test the captured value. Do
    # NOT pipe a live `git ... | grep -q` -- grep -q exits on first match, the
    # upstream git dies of SIGPIPE, and `set -o pipefail` inverts the result.
    EXISTING_REPLACE_REFS=$(container_git_verbose replace -l || true)
    # Leg 2 (shallow): a shallow clone's boundary-commit parents are untrustworthy.
    IS_SHALLOW=$(container_git_verbose rev-parse --is-shallow-repository || true)

    GRAFT_IN_PLACE=false
    GRAFT_SKIP_REASON=""
    if [ -n "${EXISTING_REPLACE_REFS}" ]; then
        # Leg 1: a replace ref exists -> a prior migrate already grafted.
        GRAFT_IN_PLACE=true
        GRAFT_SKIP_REASON="git still records that link"
    elif [ "${IS_SHALLOW}" = "true" ]; then
        # Leg 2: do not trust boundary-commit parents on a shallow clone; fall
        # through to the match/graft path (attempting a graft is idempotent-safe).
        echo "NOTE: Repository is a shallow clone -- boundary-commit parent counts"
        echo "      are unreliable, so proceeding to the match/graft path."
        echo ""
    else
        # Leg 3 (fallback): full, un-replaced repo -- the parent-count check on the
        # true root commit is correct here.
        INITIAL_PARENT_COUNT=$(container_git_verbose cat-file -p "${INITIAL_COMMIT}" | grep -c '^parent ' || true)
        INITIAL_PARENT_COUNT="${INITIAL_PARENT_COUNT:-0}"
        if [ "${INITIAL_PARENT_COUNT}" -gt 0 ]; then
            GRAFT_IN_PLACE=true
            GRAFT_SKIP_REASON="your first commit already has earlier history behind it"
        fi
    fi

    if [ "${GRAFT_IN_PLACE}" = true ]; then
        echo "History graft already in place: a previous migration already linked"
        echo "your history to DAAF's (${GRAFT_SKIP_REASON}). Skipping this step."
        echo ""
    else
        # --- Find matching upstream commit ---
        echo "Analyzing local initial commit..."
        echo ""

        # Get the blob fingerprint of the initial local commit
        # We compare only (blob_hash, filepath) pairs, ignoring file modes
        LOCAL_TREE=$(container_exec sh -c "cd /daaf && git ls-tree -r '${INITIAL_COMMIT}' | awk '{print \$3, \$4}' | sort" </dev/null | tr -d '\r')

        MATCHING_COMMIT=""
        MATCH_TYPE=""

        # Try known tags first, then origin/main HEAD
        echo "Searching for matching upstream commit..."
        echo ""

        CANDIDATES="v2.0.1 v2.0.0 v1.0.0"

        # Check which tags actually exist
        VALID_CANDIDATES=""
        for TAG in ${CANDIDATES}; do
            if container_git rev-parse --verify "${TAG}" >/dev/null 2>&1; then
                VALID_CANDIDATES="${VALID_CANDIDATES} ${TAG}"
            elif container_git rev-parse --verify "origin/${TAG}" >/dev/null 2>&1; then
                VALID_CANDIDATES="${VALID_CANDIDATES} origin/${TAG}"
            fi
        done

        # Also try origin/main HEAD
        VALID_CANDIDATES="${VALID_CANDIDATES} origin/main"

        STEP=0
        TOTAL_CANDIDATES=$(echo "${VALID_CANDIDATES}" | wc -w | tr -d '[:space:]')

        for CANDIDATE in ${VALID_CANDIDATES}; do
            STEP=$((STEP + 1))
            CANDIDATE_SHA=$(container_git rev-parse "${CANDIDATE}" 2>/dev/null || true)
            if [ -z "${CANDIDATE_SHA}" ]; then
                continue
            fi

            printf "  Checking %s (%d/%d)..." "${CANDIDATE}" "${STEP}" "${TOTAL_CANDIDATES}"

            CANDIDATE_TREE=$(container_exec sh -c "cd /daaf && git ls-tree -r '${CANDIDATE_SHA}' | awk '{print \$3, \$4}' | sort" </dev/null | tr -d '\r')

            if [ "${LOCAL_TREE}" = "${CANDIDATE_TREE}" ]; then
                MATCHING_COMMIT="${CANDIDATE_SHA}"
                MATCH_TYPE="exact"
                echo " EXACT MATCH"
                echo ""
                echo "  Matched: ${CANDIDATE} (${CANDIDATE_SHA:0:12})"
                break
            else
                echo " no match"
            fi
        done

        # If no exact match from known candidates, search all commits on origin/main
        # This runs the entire search inside a SINGLE docker exec call to avoid
        # the overhead of hundreds of individual docker exec invocations.
        if [ -z "${MATCHING_COMMIT}" ]; then
            echo ""
            echo "  No exact match from known tags. Searching all upstream commits..."
            echo "  (This runs inside the container and may take 30-60 seconds.)"
            echo ""

            # Build a skip list of SHAs we already checked
            SKIP_LIST=""
            for CANDIDATE in ${VALID_CANDIDATES}; do
                CANDIDATE_SHA=$(container_git rev-parse "${CANDIDATE}" 2>/dev/null || true)
                if [ -n "${CANDIDATE_SHA}" ]; then
                    SKIP_LIST="${SKIP_LIST} ${CANDIDATE_SHA}"
                fi
            done

            # Run the full search inside the container in one exec call.
            # Output format: "EXACT:<sha>" or "BEST:<sha>:<overlap>:<local_count>"
            # Progress lines go to stderr (prefixed with PROGRESS:)
            SEARCH_RESULT=$(docker exec "${CONTAINER_NAME}" sh -c '
                cd /daaf
                INITIAL="'"${INITIAL_COMMIT}"'"
                SKIP_SHAS="'"${SKIP_LIST}"'"

                # Save local blob fingerprint to temp file
                git ls-tree -r "$INITIAL" | awk "{print \$3, \$4}" | sort > /tmp/migrate_local_blobs.txt
                LOCAL_COUNT=$(wc -l < /tmp/migrate_local_blobs.txt)

                BEST_SHA=""
                BEST_OVERLAP=0
                TOTAL=$(git rev-list origin/main | wc -l)
                NUM=0

                for COMMIT in $(git rev-list origin/main); do
                    NUM=$((NUM + 1))

                    # Skip already-checked commits
                    case " $SKIP_SHAS " in
                        *" $COMMIT "*) continue ;;
                    esac

                    # Progress every 20 commits (to stderr so it does not mix with result)
                    if [ $((NUM % 20)) -eq 0 ]; then
                        printf "  Searching commit %d/%d...\r" "$NUM" "$TOTAL" >&2
                    fi

                    # Generate candidate blob fingerprint
                    git ls-tree -r "$COMMIT" | awk "{print \$3, \$4}" | sort > /tmp/migrate_cand_blobs.txt

                    # Exact match check (fast)
                    if diff -q /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt >/dev/null 2>&1; then
                        echo "EXACT:$COMMIT"
                        rm -f /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt
                        exit 0
                    fi

                    # Track best fuzzy match
                    OVERLAP=$(comm -12 /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt | wc -l)
                    if [ "$OVERLAP" -gt "$BEST_OVERLAP" ]; then
                        BEST_OVERLAP=$OVERLAP
                        BEST_SHA=$COMMIT
                    fi
                done

                rm -f /tmp/migrate_local_blobs.txt /tmp/migrate_cand_blobs.txt
                echo "BEST:$BEST_SHA:$BEST_OVERLAP:$LOCAL_COUNT"
            ' </dev/null 2>&1 | tr -d '\r')

            # Parse the result (last non-empty line is the result; earlier lines are progress)
            RESULT_LINE=$(echo "${SEARCH_RESULT}" | grep -E '^(EXACT|BEST):' | tail -1)

            if echo "${RESULT_LINE}" | grep -q '^EXACT:'; then
                MATCHING_COMMIT=$(echo "${RESULT_LINE}" | cut -d: -f2)
                MATCH_TYPE="exact"
                echo ""
                echo "  EXACT MATCH found: ${MATCHING_COMMIT:0:12}"
            elif echo "${RESULT_LINE}" | grep -q '^BEST:'; then
                BEST_MATCH_SHA=$(echo "${RESULT_LINE}" | cut -d: -f2)
                BEST_MATCH_OVERLAP=$(echo "${RESULT_LINE}" | cut -d: -f3)
                LOCAL_LINE_COUNT=$(echo "${RESULT_LINE}" | cut -d: -f4)

                if [ -n "${BEST_MATCH_SHA}" ] && [ "${LOCAL_LINE_COUNT:-0}" -gt 0 ]; then
                    OVERLAP_PCT=$((BEST_MATCH_OVERLAP * 100 / LOCAL_LINE_COUNT))
                else
                    OVERLAP_PCT=0
                fi

                if [ "${OVERLAP_PCT}" -ge 95 ]; then
                    MATCHING_COMMIT="${BEST_MATCH_SHA}"
                    MATCH_TYPE="fuzzy (${OVERLAP_PCT}% blob overlap)"
                    echo ""
                    echo "  Best match: ${BEST_MATCH_SHA:0:12} (${OVERLAP_PCT}% overlap)"
                else
                    echo ""
                    echo "  WARNING: No upstream commit matches your initial commit well enough."
                    if [ -n "${BEST_MATCH_SHA}" ]; then
                        echo "  Best candidate: ${BEST_MATCH_SHA:0:12} (${OVERLAP_PCT}% overlap)"
                    fi
                    echo ""
                fi
            fi
        fi

        # Fallback: graft onto latest known tag
        if [ -z "${MATCHING_COMMIT}" ]; then
            echo "  Falling back to grafting onto the latest known tag..."

            FALLBACK_TAG=""
            for TAG in v2.0.1 v2.0.0 v1.0.0; do
                if container_git rev-parse --verify "${TAG}" >/dev/null 2>&1; then
                    FALLBACK_TAG="${TAG}"
                    break
                elif container_git rev-parse --verify "origin/${TAG}" >/dev/null 2>&1; then
                    FALLBACK_TAG="origin/${TAG}"
                    break
                fi
            done

            if [ -n "${FALLBACK_TAG}" ]; then
                MATCHING_COMMIT=$(container_git rev-parse "${FALLBACK_TAG}" 2>/dev/null || true)
                MATCH_TYPE="fallback (${FALLBACK_TAG})"
                echo ""
                echo "  WARNING: Using fallback graft point: ${FALLBACK_TAG} (${MATCHING_COMMIT:0:12})"
                echo "  Your local initial commit did not match any upstream commit exactly."
                echo "  This is safe but means your git history may show a small discontinuity"
                echo "  at the graft point. update_daaf.sh will still work correctly."
            else
                # Last resort: use origin/main
                MATCHING_COMMIT=$(container_git rev-parse origin/main 2>/dev/null || true)
                MATCH_TYPE="fallback (origin/main HEAD)"
                echo ""
                echo "  WARNING: No tags found. Using origin/main HEAD as graft point."
                echo "  This is safe but means your git history may show a discontinuity."
            fi
        fi

        echo ""

        if [ -z "${MATCHING_COMMIT}" ]; then
            echo "ERROR: Could not determine a graft point."
            echo "This is unexpected. Please report this issue at:"
            echo "  https://github.com/${REPO}/issues"
            exit 1
        fi

        # --- Graft local history onto upstream ---
        echo "Connecting local history to upstream (${MATCH_TYPE})..."
        container_git_verbose replace --graft "${INITIAL_COMMIT}" "${MATCHING_COMMIT}"
        echo "Graft complete."
        echo ""

        # --- Verify the graft works ---
        echo "Verifying graft..."
        MERGE_BASE=$(container_git_verbose merge-base HEAD origin/main || true)
        if [ -n "${MERGE_BASE}" ]; then
            echo "  Verified: common ancestor found (${MERGE_BASE:0:12})"
            echo "  git merge and git pull will work correctly."
        else
            echo ""
            echo "  WARNING: Could not verify graft -- no common ancestor found."
            echo "  The graft was applied, but git merge may not work as expected."
            echo "  This is unusual. You can run the migration command again:"
            echo "    ${MIGRATE_RERUN}"
            echo "  If the problem persists, report it at:"
            echo "    https://github.com/${REPO}/issues"
        fi
        echo ""

        # --- Fix file permissions in the index ---
        echo "Fixing file permissions (ZIP downloads don't preserve executable bits)..."

        # Get files that are 100755 upstream but 100644 locally
        UPSTREAM_EXEC=$(container_exec sh -c "cd /daaf && git ls-tree -r '${MATCHING_COMMIT}' | grep '^100755' | awk '{print \$4}' | sort" </dev/null | tr -d '\r')

        PERM_FIXED=0
        PERM_FILES=""
        if [ -n "${UPSTREAM_EXEC}" ]; then
            while IFS= read -r FILEPATH; do
                [ -z "${FILEPATH}" ] && continue
                # Check if the file exists locally and has wrong mode
                LOCAL_MODE=$(container_git ls-files -s -- "${FILEPATH}" 2>/dev/null | awk '{print $1}' | tr -d '\r' || true)
                if [ "${LOCAL_MODE}" = "100644" ]; then
                    container_git update-index --chmod=+x "${FILEPATH}" 2>/dev/null || true
                    PERM_FILES="${PERM_FILES} ${FILEPATH}"
                    PERM_FIXED=$((PERM_FIXED + 1))
                fi
            done <<< "${UPSTREAM_EXEC}"
        fi

        if [ "${PERM_FIXED}" -gt 0 ]; then
            echo "  Fixed permissions on ${PERM_FIXED} file(s)."
            echo ""
            echo "Committing permission fixes..."
            # Commit only the permission changes already staged by update-index
            # (do NOT use 'git add -A' which could sweep in unrelated changes)
            container_git_verbose commit --allow-empty -m "Migration: normalize file permissions"
            echo "Permission fixes committed."
        else
            echo "  No permission fixes needed."
        fi

        echo ""
    fi

    # --- Set upstream tracking ---
    # Best-effort: a missing local 'main' branch is non-fatal. Print the success
    # line only when set-upstream succeeded.
    echo "Setting upstream tracking branch..."
    if container_git_verbose branch --set-upstream-to=origin/main main; then
        echo "Tracking set: main -> origin/main"
    else
        # Report which precondition failed: a single-branch or tag-pinned clone
        # has no origin/main remote-tracking ref, which needs a different fix
        # from a missing local main.
        if container_exec git -C /daaf rev-parse --verify --quiet refs/remotes/origin/main >/dev/null 2>&1; then
            echo "NOTE: Could not set upstream tracking (no local 'main' branch on this install)."
        else
            echo "NOTE: Could not set upstream tracking (no 'origin/main' remote-tracking ref on this install -- e.g. a single-branch or tag-pinned clone)."
        fi
    fi
    echo ""

    echo "Migration complete. Your local history is now connected to the"
    echo "official DAAF timeline. Future updates will merge cleanly."
    echo ""
fi

# =====================================================================
# 7. OFFER UPDATE
# =====================================================================
echo "-------------------------------------------"
echo "  Run update?"
echo "-------------------------------------------"
echo ""
echo "Your installation is now connected to the upstream repository."
echo "Would you like to pull the latest updates now?"
echo ""

if [ "${IS_INTERACTIVE}" = "true" ]; then
    CHOICE=$(prompt_choice "  Run update_daaf.sh now? [y/n]: " "y n")
else
    # Non-interactive -- skip the update
    echo "  (Non-interactive mode detected -- skipping update. Run it manually.)"
    CHOICE="n"
fi

UPDATE_RAN=false
if [ "${CHOICE}" = "y" ]; then
    echo ""
    ORIGINAL_DIR_UPDATE="$(pwd)"
    cd "${HOST_DIR}"
    if DAAF_NESTED=1 bash update_daaf.sh; then
        UPDATE_RAN=true
    else
        UPDATE_RAN=false
    fi
    cd "${ORIGINAL_DIR_UPDATE}"
fi

# =====================================================================
# 8. SUCCESS MESSAGE
# =====================================================================
echo ""
echo "=========================================="
echo "  Migration complete!"
echo "=========================================="
echo ""
echo "Your installation can now use the updater. The migration checked each"
echo "item below and set it up where it was missing (an item already in place"
echo "from an earlier run was left as it was):"
echo ""
if [ "${DETECTED_ERA}" = "1" ]; then
    echo "  - Host utility scripts, downloaded to: ${HOST_DIR}/"
    echo "  - A full backup of your Docker volume"
    echo "  - The latest DAAF history, fetched into your existing repository"
else
    echo "  - Host utility scripts, downloaded to: ${HOST_DIR}/"
    echo "  - A full backup of your Docker volume"
    echo "  - A link (remote 'origin') to the official DAAF repository"
    echo "  - Your local git history, connected to DAAF's history"
    echo "  - File permissions matching DAAF's"
    echo "  - Upstream tracking (main -> origin/main)"
fi
echo "Any NOTE or WARNING printed above marks an item that needs attention."
echo ""
if [ "${CHOICE}" = "y" ] && [ "${UPDATE_RAN}" = true ]; then
    echo "Going forward, you can update DAAF with:"
elif [ "${CHOICE}" = "y" ] && [ "${UPDATE_RAN}" = false ]; then
    echo "The update step encountered an issue (see above). Once resolved,"
    echo "you can update DAAF with:"
elif [ "${CHOICE}" = "n" ] && [ "${IS_INTERACTIVE}" = "true" ]; then
    # User chose not to update
    echo "To pull the latest updates when you're ready:"
elif [ "${IS_INTERACTIVE}" != "true" ]; then
    # Non-interactive mode -- update was skipped automatically
    echo "IMPORTANT: The update step was skipped because the script was run"
    echo "non-interactively. To pull the latest updates, run:"
else
    echo "Going forward, you can update DAAF with:"
fi
echo "  cd \"${HOST_DIR}\""
echo "  bash update_daaf.sh"
echo ""
echo "Other available scripts:"
echo "  bash daaf.sh                    DAAF Control Panel (recommended)"
echo "  bash run_daaf.sh               Launch Claude Code directly"
echo "  bash backup_daaf.sh            Back up the Docker volume"
echo "  bash restore_from_backup.sh    Restore from a backup"
echo "  bash rebuild_daaf.sh           Rebuild the Docker image"
echo "  bash view_logs.sh              Browse session logs"
echo "  bash view_notebooks.sh         Browse and edit marimo notebooks"
echo "  bash view_quarto.sh            Render and view Quarto notebooks in your browser"
echo "  bash run_vscode.sh             Open VS Code in your browser (code-server)"
echo ""
