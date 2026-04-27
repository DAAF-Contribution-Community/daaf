#!/usr/bin/env bash
# ============================================================================
# DAAF Migration Script (macOS / Linux)
# ============================================================================
# Migrates existing DAAF installations to the new update infrastructure.
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
# This script is idempotent — safe to run multiple times. If the migration
# has already been completed, it will detect that and skip ahead.
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output
# Skip when called from another script or piped (curl ... | bash)
if [ -z "${DAAF_NESTED:-}" ] && [ -t 0 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: "' EXIT
fi

# --- Configuration ---
REPO="DAAF-Contribution-Community/daaf"
BRANCH="${DAAF_BRANCH:-main}"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
VOLUME_NAME="daaf_daaf-data"
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
        # Parse -o flag to create empty target files so chmod +x succeeds
        local outfile=""
        local args=("$@")
        local i
        for (( i=0; i<${#args[@]}; i++ )); do
            if [ "${args[$i]}" = "-o" ] && [ $((i+1)) -lt ${#args[@]} ]; then
                outfile="${args[$((i+1))]}"
                break
            fi
        done
        if [ -n "${outfile}" ]; then
            mkdir -p "$(dirname "${outfile}")"
            touch "${outfile}"
        fi
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
    echo "Your research files and data are safe — the migration only changes" >&2
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
    echo "  2. Re-run:  bash migrate_daaf.sh" >&2
    echo "     (It is safe to re-run — it will pick up where it left off.)" >&2
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
    if ! [ -t 0 ]; then
        choice=$(echo "${valid_choices}" | awk '{print $1}')
        echo "  (Non-interactive mode — auto-selecting: ${choice})" >&2
        echo "${choice}"
        return
    fi
    while true; do
        read -r -p "${prompt_text}" choice
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
echo "This script migrates your existing DAAF installation to support"
echo "the new update infrastructure (update_daaf.sh)."
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
    mkdir -p "${HOST_DIR}"
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

for FILE in backup_daaf.sh rebuild_daaf.sh update_daaf.sh run_daaf.sh view_logs.sh env.example; do
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
    # Even if docker-compose.yml exists, update it so it has name: daaf
    # (v1.0.0 installations may lack this)
    if ! grep -q '^name: daaf' "${HOST_DIR}/docker-compose.yml"; then
        echo ""
        echo "  Updating docker-compose.yml to current version..."
        cp "${HOST_DIR}/docker-compose.yml" "${HOST_DIR}/docker-compose.yml.pre-migrate"
        if curl -fsSL "${RAW_BASE}/docker-compose.yml" -o "${HOST_DIR}/docker-compose.yml"; then
            echo "  Updated: docker-compose.yml (old version saved as docker-compose.yml.pre-migrate)"
        else
            echo "  WARNING: Could not download updated docker-compose.yml. Restoring original."
            mv "${HOST_DIR}/docker-compose.yml.pre-migrate" "${HOST_DIR}/docker-compose.yml"
        fi
    fi
fi

# Make all .sh files executable
chmod +x "${HOST_DIR}"/*.sh 2>/dev/null || true

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

ORIGINAL_DIR="$(pwd)"
cd "${HOST_DIR}"
DAAF_NESTED=1 bash backup_daaf.sh
cd "${ORIGINAL_DIR}"
BACKUP_COMPLETED=true

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
CONTAINER_COUNT=$(echo "${ALL_CONTAINERS}" | grep -c . || echo "0")
CONTAINER_NAME=$(echo "${ALL_CONTAINERS}" | head -1)

if [ "${CONTAINER_COUNT}" -gt 1 ]; then
    echo "WARNING: Multiple containers found using the DAAF volume:"
    echo "${ALL_CONTAINERS}" | sed 's/^/  /'
    echo ""
    echo "Using the first one: ${CONTAINER_NAME}"
    echo "If this is wrong, stop the other containers and re-run."
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
                echo "Try restarting Docker Desktop, then re-run:  bash migrate_daaf.sh"
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
        echo "Try restarting Docker Desktop, then re-run:  bash migrate_daaf.sh"
        cd "${ORIGINAL_DIR_COMPOSE}"
        exit 1
    fi

    # After docker compose up, discover the container name
    CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
    if [ -z "${CONTAINER_NAME}" ]; then
        echo "ERROR: Container started but could not be found."
        echo "Try restarting Docker Desktop, then re-run:  bash migrate_daaf.sh"
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
            echo "Try restarting Docker Desktop, then re-run:  bash migrate_daaf.sh"
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
# 6a. ERA 1 PATH (v1.0.0 — remote exists)
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
        echo "Once the issue is resolved, re-run:  bash migrate_daaf.sh"
        exit 1
    fi

    # Ensure tracking is set up
    container_git branch --set-upstream-to=origin/main main 2>/dev/null || true

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
                    echo "  bash run_daaf.sh bash"
                    echo "  git fetch upstream"
                    echo "  exit"
                fi
            else
                echo ""
                echo "WARNING: Could not add 'upstream' remote. You can add it"
                echo "manually later:"
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
# 6b. ERA 2 PATH (v2.0.0+ — no remote, need graft)
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
        echo "Once the issue is resolved, re-run:  bash migrate_daaf.sh"
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
    ROOT_COUNT=$(echo "${INITIAL_COMMITS}" | grep -c . || echo "0")
    if [ "${ROOT_COUNT}" -gt 1 ]; then
        echo "NOTE: Found ${ROOT_COUNT} root commits. Using the oldest one"
        echo "      (${INITIAL_COMMIT:0:12}) for graft matching."
        echo ""
    fi

    # --- Check if graft is already in place (idempotent) ---
    INITIAL_PARENT_COUNT=$(container_git_verbose cat-file -p "${INITIAL_COMMIT}" | grep -c '^parent ' || true)
    INITIAL_PARENT_COUNT="${INITIAL_PARENT_COUNT:-0}"

    if [ "${INITIAL_PARENT_COUNT}" -gt 0 ]; then
        echo "History graft already in place (root commit has a parent)."
        echo "Skipping graft step (previous migration completed successfully)."
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
            echo "  WARNING: Could not verify graft — no common ancestor found."
            echo "  The graft was applied, but git merge may not work as expected."
            echo "  This is unusual. You can re-run:  bash migrate_daaf.sh"
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
    echo "Setting upstream tracking branch..."
    container_git branch --set-upstream-to=origin/main main 2>/dev/null || true
    echo "Tracking set: main -> origin/main"
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

if [ -t 0 ]; then
    CHOICE=$(prompt_choice "  Run update_daaf.sh now? [y/n]: " "y n")
else
    # Non-interactive (piped) — skip the update
    echo "  (Non-interactive mode detected — skipping update. Run it manually.)"
    CHOICE="n"
fi

if [ "${CHOICE}" = "y" ]; then
    echo ""
    ORIGINAL_DIR_UPDATE="$(pwd)"
    cd "${HOST_DIR}"
    DAAF_NESTED=1 bash update_daaf.sh
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
echo "Your DAAF installation has been migrated to support the new update"
echo "infrastructure. Here is what was done:"
echo ""
if [ "${DETECTED_ERA}" = "1" ]; then
    echo "  - Downloaded host utility scripts to: ${HOST_DIR}/"
    echo "  - Created a full backup of your Docker volume"
    echo "  - Fetched latest upstream history into your existing repo"
else
    echo "  - Downloaded host utility scripts to: ${HOST_DIR}/"
    echo "  - Created a full backup of your Docker volume"
    echo "  - Added remote origin pointing to the official DAAF repository"
    echo "  - Connected your local git history to the official DAAF timeline"
    echo "  - Fixed file permissions to match upstream"
    echo "  - Set upstream tracking (main -> origin/main)"
fi
echo ""
if [ "${CHOICE}" = "n" ] && [ -t 0 ]; then
    # User chose not to update
    echo "To pull the latest updates when you're ready:"
elif ! [ -t 0 ]; then
    # Non-interactive mode (curl pipe) — update was skipped automatically
    echo "IMPORTANT: The update step was skipped because the script was run"
    echo "non-interactively. To pull the latest updates, run:"
else
    echo "Going forward, you can update DAAF with:"
fi
echo "  cd ${HOST_DIR}"
echo "  bash update_daaf.sh"
echo ""
echo "Other available scripts:"
echo "  bash run_daaf.sh        Launch Claude Code"
echo "  bash backup_daaf.sh     Back up the Docker volume"
echo "  bash rebuild_daaf.sh    Rebuild the Docker image"
echo "  bash view_logs.sh       Browse session logs"
echo ""
