#!/usr/bin/env bash
# ============================================================================
# DAAF Migration End-to-End Test (macOS / Linux)
# ============================================================================
# Automated 1-click test that:
#   1. Nukes any existing DAAF Docker resources (clean slate)
#   2. Installs an old version of DAAF from a specific tag/branch
#   3. Simulates the correct "era" (clone-based vs ZIP-based) for that version
#   4. Creates committed framework changes + research files
#   5. Creates uncommitted framework changes + research files
#   6. Runs the migration script (from the local repo, not GitHub)
#   7. Runs verification checks to ensure everything worked
#
# Usage:
#   bash test_migration.sh                          # defaults to v2.0.1
#   DAAF_TEST_VERSION=v1.0.0 bash test_migration.sh # test Era 1
#   DAAF_TEST_VERSION=v2.0.0 bash test_migration.sh # test Era 2
#
# Environment variables:
#   DAAF_TEST_VERSION   Tag/branch to install (default: v2.0.1)
#   DAAF_TEST_ERA       Override era detection: "1" or "2" (default: auto)
#   DAAF_MIGRATION_BRANCH  Branch for migration script downloads (default: minor_revisions_v202)
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection (to pull old versions from GitHub)
#   - This script must be run from a local clone of the DAAF repo
#     (it copies migrate_daaf.sh from the local repo)
#
# ============================================================================

set -euo pipefail

# --- Color setup ---
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    CYAN=$(tput setaf 6)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" CYAN="" BOLD="" RESET=""
fi

info()    { echo "${CYAN}INFO:${RESET} $*" >&2; }
success() { echo "${GREEN}SUCCESS:${RESET} $*" >&2; }
warn()    { echo "${YELLOW}WARNING:${RESET} $*" >&2; }
error()   { echo "${RED}ERROR:${RESET} $*" >&2; }

# --- Configuration ---
readonly TEST_VERSION="${DAAF_TEST_VERSION:-v2.0.1}"
readonly MIGRATION_BRANCH="${DAAF_MIGRATION_BRANCH:-minor_revisions_v202}"
readonly REPO="DAAF-Contribution-Community/daaf"
readonly VOLUME_NAME="daaf_daaf-data"
readonly CONTAINER_MAIN="daaf-daaf-docker-1"

# Auto-detect era from version if not overridden
# v1.0.0 = Era 1 (clone-based, remote exists)
# v2.0.0+ = Era 2 (ZIP-based, no remote)
if [ -n "${DAAF_TEST_ERA:-}" ]; then
    TEST_ERA="${DAAF_TEST_ERA}"
elif [ "${TEST_VERSION}" = "v1.0.0" ]; then
    TEST_ERA="1"
else
    TEST_ERA="2"
fi

# Locate the local repo root (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# The repo root is two levels up from scripts/host/
LOCAL_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Verify local migrate_daaf.sh exists
if [ ! -f "${LOCAL_REPO_ROOT}/scripts/host/migrate_daaf.sh" ]; then
    error "Cannot find migrate_daaf.sh in the local repo."
    error "Expected at: ${LOCAL_REPO_ROOT}/scripts/host/migrate_daaf.sh"
    error "Run this script from within a DAAF repo clone."
    exit 1
fi

# Working directory for the test install
TEST_DIR="$(mktemp -d)"
cleanup() {
    info "Test working directory preserved at: ${TEST_DIR}"
    info "(Delete manually when done inspecting: rm -rf ${TEST_DIR})"
    # Pause before exit so the user can review output
    if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
        echo ""
        read -r -p "Press Enter to continue: " < /dev/tty
    fi
}
trap cleanup EXIT

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0
FAILURES=""

check() {
    local description="$1"
    local result="$2"
    if [ "${result}" = "0" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo "  ${GREEN}PASS${RESET}: ${description}"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILURES="${FAILURES}\n  FAIL: ${description}"
        echo "  ${RED}FAIL${RESET}: ${description}"
    fi
}

echo ""
echo "${BOLD}==========================================${RESET}"
echo "${BOLD}  DAAF Migration Test${RESET}"
echo "${BOLD}==========================================${RESET}"
echo ""
echo "  Version:   ${TEST_VERSION}"
echo "  Era:       ${TEST_ERA} ($([ "${TEST_ERA}" = "1" ] && echo "clone-based" || echo "ZIP-based"))"
echo "  Migration: from local repo (branch: ${MIGRATION_BRANCH})"
echo "  Work dir:  ${TEST_DIR}"
echo ""

# =====================================================================
# PHASE 1: Clean Slate
# =====================================================================
echo "[1/7] ${BOLD}Clean slate${RESET}"
echo "${BOLD}-------------------------------------------${RESET}"
echo ""

# Preflight
if ! command -v docker >/dev/null 2>&1; then
    error "Docker not found. Install Docker Desktop first."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    error "Docker daemon is not running. Start Docker Desktop first."
    exit 1
fi

info "Removing any existing DAAF Docker resources..."

# Stop and remove containers
docker rm -f "${CONTAINER_MAIN}" 2>/dev/null || true
docker rm -f "daaf-daaf-init-1" 2>/dev/null || true

# Remove volume
docker volume rm "${VOLUME_NAME}" 2>/dev/null || true

# Remove image
docker rmi "daaf-daaf-docker" 2>/dev/null || true

success "Clean slate achieved."
echo ""

# =====================================================================
# PHASE 2: Install Old Version
# =====================================================================
echo "[2/7] ${BOLD}Install ${TEST_VERSION}${RESET}"
echo ""

info "Installing DAAF from branch/tag: ${TEST_VERSION}"
info "This will build the Docker image and clone the repo — may take several minutes..."
echo ""

cd "${TEST_DIR}" || { error "Cannot enter test directory: ${TEST_DIR}"; exit 1; }

# Use the install script from the target version's own branch/tag
DAAF_BRANCH="${TEST_VERSION}" DAAF_NESTED=1 bash -c "$(curl -fsSL "https://raw.githubusercontent.com/${REPO}/${TEST_VERSION}/scripts/host/install.sh")"

# Verify install succeeded
if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
    error "Installation failed — volume ${VOLUME_NAME} not found."
    exit 1
fi

success "DAAF ${TEST_VERSION} installed successfully."
echo ""

# =====================================================================
# PHASE 3: Simulate Era
# =====================================================================
echo "[3/7] ${BOLD}Simulate Era ${TEST_ERA}${RESET}"
echo ""

# Ensure container is running
CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
if [ -z "${CONTAINER_NAME}" ]; then
    error "No container found using volume ${VOLUME_NAME}."
    exit 1
fi

CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
if [ "${CONTAINER_STATE}" != "running" ]; then
    info "Starting container ${CONTAINER_NAME}..."
    docker start "${CONTAINER_NAME}" >/dev/null 2>&1
    sleep 3
fi

container_exec() {
    docker exec "${CONTAINER_NAME}" "$@" </dev/null
}

container_git() {
    docker exec "${CONTAINER_NAME}" git -C /daaf "$@" </dev/null 2>/dev/null | tr -d '\r'
}

if [ "${TEST_ERA}" = "2" ]; then
    # Era 2: ZIP-based install — remove the remote to simulate no remote
    info "Simulating ZIP-based install (removing git remote)..."
    container_git remote remove origin 2>/dev/null || true

    # Verify remote is gone
    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    if [ -z "${ORIGIN_CHECK}" ]; then
        success "Remote removed — simulating Era 2 (ZIP-based) install."
    else
        error "Failed to remove remote. Era simulation may be inaccurate."
    fi
elif [ "${TEST_ERA}" = "1" ]; then
    # Era 1: clone-based — remote should already exist from install
    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    if [ -n "${ORIGIN_CHECK}" ]; then
        success "Remote exists (${ORIGIN_CHECK}) — Era 1 (clone-based) already simulated."
    else
        warn "Expected remote for Era 1 but none found. Adding one..."
        container_git remote add origin "https://github.com/${REPO}.git" 2>/dev/null || true
        success "Remote added."
    fi
fi

echo ""

# =====================================================================
# PHASE 4: Simulate User Work (Committed)
# =====================================================================
echo "[4/7] ${BOLD}Simulate committed user work${RESET}"
echo ""

info "Creating committed framework changes and research files..."

# Create a research project
container_exec bash -c 'mkdir -p /daaf/research/2026-01-15_Test_Analysis/data'
container_exec bash -c 'mkdir -p /daaf/research/2026-01-15_Test_Analysis/scripts'
container_exec bash -c 'mkdir -p /daaf/research/2026-01-15_Test_Analysis/output'
container_exec bash -c 'cat > /daaf/research/2026-01-15_Test_Analysis/scripts/01_fetch.py << "PYEOF"
# --- Config ---
import polars as pl

BASE_DIR = "/daaf"
PROJECT_DIR = f"{BASE_DIR}/research/2026-01-15_Test_Analysis"

# --- Load ---
# INTENT: Fetch test data for migration verification
print("Test script executed successfully")
PYEOF'

container_exec bash -c 'echo "Test analysis data" > /daaf/research/2026-01-15_Test_Analysis/data/test_data.txt'
container_exec bash -c 'echo "# Test Analysis\nThis is a test research project." > /daaf/research/2026-01-15_Test_Analysis/README.md'

# Make a framework modification (edit CLAUDE.md slightly)
container_exec bash -c 'echo "" >> /daaf/CLAUDE.md'
container_exec bash -c 'echo "<!-- test-migration-marker: committed -->" >> /daaf/CLAUDE.md'

# Commit everything
container_git add -A
container_git commit -m "Test: Add research project and framework tweaks"

COMMITTED_SHA=$(container_git rev-parse HEAD)
info "Committed changes at: ${COMMITTED_SHA:0:12}"
success "Committed user work created."
echo ""

# =====================================================================
# PHASE 5: Simulate User Work (Uncommitted)
# =====================================================================
echo "[5/7] ${BOLD}Simulate uncommitted user work${RESET}"
echo ""

info "Creating uncommitted framework changes and research files..."

# Add more uncommitted research files
container_exec bash -c 'mkdir -p /daaf/research/2026-02-10_WIP_Analysis/scripts'
container_exec bash -c 'echo "Work in progress data" > /daaf/research/2026-02-10_WIP_Analysis/notes.md'
container_exec bash -c 'cat > /daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py << "PYEOF"
# --- Config ---
# INTENT: WIP exploration script — uncommitted
print("WIP script")
PYEOF'

# Make an uncommitted framework change
container_exec bash -c 'echo "<!-- test-migration-marker: uncommitted -->" >> /daaf/CLAUDE.md'

success "Uncommitted user work created."
echo ""

# =====================================================================
# PHASE 6: Run Migration
# =====================================================================
echo "[6/7] ${BOLD}Run migration script${RESET}"
echo ""

info "Copying migration script from local repo..."

# Determine the daaf-docker host directory
HOST_DIR="${TEST_DIR}/daaf-docker"
if [ ! -d "${HOST_DIR}" ]; then
    HOST_DIR="${TEST_DIR}"
fi

# Copy the local migration script to the host dir
cp "${LOCAL_REPO_ROOT}/scripts/host/migrate_daaf.sh" "${HOST_DIR}/migrate_daaf.sh"
chmod +x "${HOST_DIR}/migrate_daaf.sh"

info "Running migration with DAAF_BRANCH=${MIGRATION_BRANCH}..."
echo ""

cd "${HOST_DIR}" || { error "Cannot enter host directory: ${HOST_DIR}"; exit 1; }

# Run migration non-interactively (piped input means it skips the update prompt)
# Use DAAF_BRANCH to point downloads at the current dev branch
DAAF_BRANCH="${MIGRATION_BRANCH}" DAAF_NESTED=1 echo "n" | bash migrate_daaf.sh || {
    warn "Migration script exited with non-zero status: $?"
    warn "This may or may not indicate a problem — check the output above."
}

echo ""
success "Migration script completed."
echo ""

# =====================================================================
# PHASE 7: Verification
# =====================================================================
echo "[7/7] ${BOLD}Verification${RESET}"
echo ""

# Re-discover container (may have changed during migration)
CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
if [ -z "${CONTAINER_NAME}" ]; then
    error "No container found after migration!"
    exit 1
fi

CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
if [ "${CONTAINER_STATE}" != "running" ]; then
    docker start "${CONTAINER_NAME}" >/dev/null 2>&1
    sleep 3
fi

# Redefine helpers with current container
container_exec() {
    docker exec "${CONTAINER_NAME}" "$@" </dev/null
}
container_git() {
    docker exec "${CONTAINER_NAME}" git -C /daaf "$@" </dev/null 2>/dev/null | tr -d '\r'
}

echo "${BOLD}  Git State Checks:${RESET}"

# Check 1: Remote exists and points to correct repo
ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || echo "")
if echo "${ORIGIN_URL}" | grep -qi "${REPO}"; then
    check "Remote 'origin' points to official DAAF repo" "0"
else
    check "Remote 'origin' points to official DAAF repo (got: '${ORIGIN_URL}')" "1"
fi

# Check 2: Upstream tracking is set
TRACKING=$(container_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "")
if [ "${TRACKING}" = "origin/main" ]; then
    check "Upstream tracking set to origin/main" "0"
else
    check "Upstream tracking set to origin/main (got: '${TRACKING}')" "1"
fi

# Check 3: Era-specific — graft exists (Era 2 only)
if [ "${TEST_ERA}" = "2" ]; then
    # The graft should make the initial commit have a parent
    INITIAL_COMMIT=$(container_git rev-list --max-parents=0 HEAD 2>/dev/null | tail -1 || echo "")
    if [ -n "${INITIAL_COMMIT}" ]; then
        PARENT_COUNT=$(container_git cat-file -p "${INITIAL_COMMIT}" 2>/dev/null | grep -c '^parent ' || echo "0")
        if [ "${PARENT_COUNT}" -gt 0 ]; then
            check "Era 2 graft in place (root commit has parent)" "0"
        else
            check "Era 2 graft in place (root commit has parent)" "1"
        fi
    else
        check "Era 2 graft in place (could not find root commit)" "1"
    fi

    # Check merge-base exists
    MERGE_BASE=$(container_git merge-base HEAD origin/main 2>/dev/null || echo "")
    if [ -n "${MERGE_BASE}" ]; then
        check "Common ancestor exists with origin/main" "0"
    else
        check "Common ancestor exists with origin/main" "1"
    fi
fi

echo ""
echo "${BOLD}  Research File Checks:${RESET}"

# Check 4: Committed research project survived
if container_exec test -f /daaf/research/2026-01-15_Test_Analysis/scripts/01_fetch.py; then
    check "Committed research project preserved" "0"
else
    check "Committed research project preserved" "1"
fi

if container_exec test -f /daaf/research/2026-01-15_Test_Analysis/data/test_data.txt; then
    check "Committed research data preserved" "0"
else
    check "Committed research data preserved" "1"
fi

# Check 5: Uncommitted research files survived
if container_exec test -f /daaf/research/2026-02-10_WIP_Analysis/notes.md; then
    check "Uncommitted research files preserved" "0"
else
    check "Uncommitted research files preserved" "1"
fi

if container_exec test -f /daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py; then
    check "Uncommitted WIP script preserved" "0"
else
    check "Uncommitted WIP script preserved" "1"
fi

echo ""
echo "${BOLD}  Framework State Checks:${RESET}"

# Check 6: Committed framework marker survived
COMMITTED_MARKER=$(container_exec bash -c 'grep -c "test-migration-marker: committed" /daaf/CLAUDE.md' 2>/dev/null || echo "0")
if [ "${COMMITTED_MARKER}" -gt 0 ]; then
    check "Committed framework changes preserved" "0"
else
    check "Committed framework changes preserved" "1"
fi

# Check 7: Uncommitted framework marker survived
UNCOMMITTED_MARKER=$(container_exec bash -c 'grep -c "test-migration-marker: uncommitted" /daaf/CLAUDE.md' 2>/dev/null || echo "0")
if [ "${UNCOMMITTED_MARKER}" -gt 0 ]; then
    check "Uncommitted framework changes preserved" "0"
else
    check "Uncommitted framework changes preserved" "1"
fi

# Check 8: Committed SHA still in history
if container_git log --oneline | grep -q "${COMMITTED_SHA:0:7}"; then
    check "Committed changes still in git history" "0"
else
    check "Committed changes still in git history" "1"
fi

echo ""
echo "${BOLD}  Host Script Checks:${RESET}"

# Check 9: Host scripts were downloaded
for SCRIPT in update_daaf.sh backup_daaf.sh rebuild_daaf.sh run_daaf.sh view_logs.sh view_notebooks.sh; do
    if [ -f "${HOST_DIR}/${SCRIPT}" ]; then
        check "Host script downloaded: ${SCRIPT}" "0"
    else
        check "Host script downloaded: ${SCRIPT}" "1"
    fi
done

# Check 10: Backup was created
BACKUP_DIR=$(find "${HOST_DIR}" -maxdepth 1 -type d -name '*_daaf_backup' 2>/dev/null | head -1 || echo "")
if [ -n "${BACKUP_DIR}" ]; then
    check "Backup directory created during migration" "0"
else
    check "Backup directory created during migration" "1"
fi

# =====================================================================
# RESULTS
# =====================================================================
echo ""
echo "${BOLD}==========================================${RESET}"
echo "${BOLD}  Test Results${RESET}"
echo "${BOLD}==========================================${RESET}"
echo ""
echo "  Version:  ${TEST_VERSION}"
echo "  Era:      ${TEST_ERA}"
echo "  Passed:   ${GREEN}${TESTS_PASSED}${RESET}"
echo "  Failed:   $([ "${TESTS_FAILED}" -gt 0 ] && echo "${RED}" || echo "")${TESTS_FAILED}${RESET}"
echo ""

if [ "${TESTS_FAILED}" -gt 0 ]; then
    echo "${RED}  Failures:${RESET}"
    printf '%b\n' "${FAILURES}"
    echo ""
    error "Some checks failed. Inspect the container and test directory for details."
    echo "  Container:  ${CONTAINER_NAME}"
    echo "  Host dir:   ${HOST_DIR}"
    echo "  Test dir:   ${TEST_DIR}"
    exit 1
else
    success "All checks passed!"
    echo ""
    echo "  The DAAF Docker resources are still running for manual inspection."
    echo "  To clean up:  DAAF_NUKE_CONFIRM=1 bash ${LOCAL_REPO_ROOT}/scripts/host/nuke_daaf.sh"
    echo ""
fi
