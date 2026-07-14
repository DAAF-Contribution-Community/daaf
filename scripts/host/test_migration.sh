#!/usr/bin/env bash
# ============================================================================
# DAAF Migration End-to-End Test (macOS / Linux)
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
#        Era 3 (v2.1.0+/branch) the version's own scripts/host/install.sh
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
#   - Era 3 with a vX.Y.Z tag: install.sh clones `--depth 1 -b <tag>`, which
#     leaves a detached HEAD that no real user had (users installed from
#     branch main). The harness normalizes with `git checkout -B main` at that
#     commit so the git state matches a real install of that vintage. Branch
#     values (e.g. daaf_dev) need no normalization and get none.
#
# EXPECT INTERACTIVE PROMPTS: migrate/update ask about running the update,
# backup, and rebuild -- you drive those choices, exactly as an end user would,
# and the Phase 7 checks are designed to pass whichever way you answer.
# (Unlike the .ps1 twin, the .sh child scripts pass DAAF_NESTED per-invocation
# and do not clobber it, so no stray exit pauses are expected here.)
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
#   bash test_migration.sh                            # v2.0.1, Era 2
#   DAAF_TEST_VERSION=v1.0.0 bash test_migration.sh   # Era 1
#   DAAF_TEST_VERSION=v2.1.0 bash test_migration.sh   # Era 3 (tag)
#   DAAF_TEST_VERSION=daaf_dev bash test_migration.sh # Era 3 (branch)
#   SKIP_MULTI_INSTANCE=1 bash test_migration.sh      # skip the slower phase 8
#
# Environment variables:
#   DAAF_TEST_VERSION      Tag/branch to install (default: v2.0.1 -- the
#                          richest migration path: ZIP era, graft required)
#   DAAF_TEST_ERA          Override era pathway: "1", "2", or "3" (default:
#                          auto -- v1.0.0=1, v2.0.0/v2.0.1=2, everything
#                          else=3). Tags below v2.1.0 cannot run era 3: no
#                          scripts/host/install.sh exists at those tags.
#   DAAF_MIGRATION_BRANCH  Branch for migration script downloads
#                          (default: daaf_dev -- keep this tracking the branch
#                           currently under update-testing)
#   SKIP_MULTI_INSTANCE    Set to "1" to skip the multi-instance phase (8),
#                          which lengthens the run (fresh build + teardown)
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - git on the host PATH (Era 1 replays the documented git clone)
#   - Internet connection (to pull old versions from GitHub)
#   - This script must be run from a local clone of the DAAF repo
#     (it copies migrate_daaf.sh from the local repo)
#
# Which versions of the local scripts?
#   - migrate_daaf.sh and install.sh are taken from the LOCAL repo this harness
#     runs from (scripts/host/ two levels up). They must be checked out to the
#     branch under test -- typically the same branch as DAAF_MIGRATION_BRANCH
#     (default: daaf_dev). The harness tests THAT checkout's migration/install
#     logic.
#   - The OLD version being migrated FROM is controlled by DAAF_TEST_VERSION
#     and is fetched from GitHub at that tag (clone, ZIP, or install.sh
#     download depending on era), independent of the local repo.
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
# Default install-from version: v2.0.1 -- the richest migration path (ZIP era:
# no remote, synthetic root commit, graft + permission-fix machinery all get
# exercised). Override with DAAF_TEST_VERSION for the other pathways.
readonly TEST_VERSION="${DAAF_TEST_VERSION:-v2.0.1}"
# Default migration branch: the branch whose migrate_daaf.sh + host scripts are
# under test. Keep this pointing at the CURRENT update-testing branch (today:
# daaf_dev). Overridable per-run via DAAF_MIGRATION_BRANCH without editing here.
readonly MIGRATION_BRANCH="${DAAF_MIGRATION_BRANCH:-daaf_dev}"
readonly REPO="DAAF-Contribution-Community/daaf"

# --- Era detection ---
# Era 1 = v1.0.0            clone-based: full .git, origin remote, branch main
# Era 2 = v2.0.0 / v2.0.1   ZIP-based: entrypoint git-inits a local-only repo
#                           (synthetic root commit, no remote)
# Era 3 = v2.1.0+ / branch  modern install.sh pathway (shipped at the ref)
# DAAF_TEST_ERA overrides the pathway (e.g. to run a branch through the ZIP
# flow); the auto-detect maps each version to the pathway its real users had.
if [ -n "${DAAF_TEST_ERA:-}" ]; then
    TEST_ERA="${DAAF_TEST_ERA}"
elif [ "${TEST_VERSION}" = "v1.0.0" ]; then
    TEST_ERA="1"
elif [ "${TEST_VERSION}" = "v2.0.0" ] || [ "${TEST_VERSION}" = "v2.0.1" ]; then
    TEST_ERA="2"
else
    TEST_ERA="3"
fi
readonly TEST_ERA

case "${TEST_ERA}" in
    1|2|3) ;;
    *)
        error "DAAF_TEST_ERA '${TEST_ERA}' is invalid. Use 1 (clone), 2 (ZIP), or 3 (install.sh)."
        exit 1
        ;;
esac

# --- Era/version compatibility guard ---
# Era 3 downloads scripts/host/install.sh from the chosen ref; tags below
# v2.1.0 predate that layout entirely (the host helper set landed at v2.1.0,
# commit a399639), so the download fails. Fail fast with a clear message.
# Only vX.Y.Z tags are checked -- branch names always carry the current layout.
# Comparison parses numeric components (a lexical compare is wrong: "v2.10.0"
# sorts before "v2.2.0" lexically). Written bash-3.2-safe: [[ =~ ]] +
# BASH_REMATCH, and 10# arithmetic prefixes so a zero-padded component is
# never mis-read as octal.
if [ "${TEST_ERA}" = "3" ] && [[ "${TEST_VERSION}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    req_major=$((10#${BASH_REMATCH[1]}))
    req_minor=$((10#${BASH_REMATCH[2]}))
    req_patch=$((10#${BASH_REMATCH[3]}))
    # Encode as a single comparable integer (each component < 1000). Era 3
    # floor is v2.1.0 = 2*1000000 + 1*1000 + 0.
    req_num=$(( req_major * 1000000 + req_minor * 1000 + req_patch ))
    if [ "${req_num}" -lt 2001000 ]; then
        error "Era 3 requires v2.1.0 or newer (${TEST_VERSION} ships no scripts/host/install.sh)."
        error "Remove DAAF_TEST_ERA and let auto-detection replay the authentic pathway for ${TEST_VERSION}."
        exit 1
    fi
fi

# --- Docker identifier derivation (default "daaf" instance) ---
# All identifiers are derived from DAAF_PROJECT_NAME rather than hardcoded, so a
# non-default install is testable and so this mirrors how nuke_daaf.sh /
# backup_daaf.sh derive their names. Docker joins the compose project name to the
# service with a DASH (containers/image) and to declared volumes with an
# UNDERSCORE (verified against docker-compose.yml). Default project name "daaf"
# reproduces the original hardcoded values byte-for-byte.
readonly PROJECT_NAME="${DAAF_PROJECT_NAME:-daaf}"
readonly VOLUME_NAME="${PROJECT_NAME}_daaf-data"
readonly CLAUDE_VOLUME_NAME="${PROJECT_NAME}_daaf-claude-config"
readonly CONTAINER_MAIN="${PROJECT_NAME}-daaf-docker-1"
readonly CONTAINER_INIT="${PROJECT_NAME}-daaf-init-1"
readonly IMAGE_NAME="${PROJECT_NAME}-daaf-docker"

# --- Second-instance identifiers (Phase 8 multi-instance pass) ---
# A distinct project name proves DAAF_PROJECT_NAME actually reprojects every
# Docker object. Same derivation rules as above.
readonly SECOND_PROJECT_NAME="daaftest2"
readonly SECOND_VOLUME_NAME="${SECOND_PROJECT_NAME}_daaf-data"
readonly SECOND_CLAUDE_VOLUME_NAME="${SECOND_PROJECT_NAME}_daaf-claude-config"
readonly SECOND_CONTAINER_MAIN="${SECOND_PROJECT_NAME}-daaf-docker-1"
readonly SECOND_CONTAINER_INIT="${SECOND_PROJECT_NAME}-daaf-init-1"
readonly SECOND_IMAGE_NAME="${SECOND_PROJECT_NAME}-daaf-docker"
# Distinct host ports so the second instance does not collide with the first on
# the same host. Container ports stay fixed (2718/2719/2720); only the published
# host port varies. These key names match environment_settings_example.txt and
# the compose interpolation (DAAF_PORT_MARIMO / _LOGVIEWER / _VSCODE).
readonly SECOND_PORT_MARIMO="12718"
readonly SECOND_PORT_LOGVIEWER="12719"
readonly SECOND_PORT_VSCODE="12720"

# --- Era 1/2 project-name guard ---
# The historical pathways predate DAAF_PROJECT_NAME entirely: v1.0.0's compose
# file has no `name:` key (project name = directory name, which the documented
# flow fixes as "daaf"), and v2.0.x hardcodes `name: daaf`. A non-default
# project name is only meaningful for Era 3.
if [ "${TEST_ERA}" != "3" ] && [ "${PROJECT_NAME}" != "daaf" ]; then
    error "Era ${TEST_ERA} replays a pathway that predates DAAF_PROJECT_NAME;"
    error "only the default 'daaf' project is supported (got: '${PROJECT_NAME}')."
    exit 1
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
case "${TEST_ERA}" in
    1) ERA_LABEL="clone-based" ;;
    2) ERA_LABEL="ZIP-based" ;;
    *) ERA_LABEL="modern install.sh" ;;
esac
readonly ERA_LABEL

echo "  Version:   ${TEST_VERSION}"
echo "  Era:       ${TEST_ERA} (${ERA_LABEL})"
echo "  Migration: from local repo (branch: ${MIGRATION_BRANCH})"
echo "  Work dir:  ${TEST_DIR}"
echo "  Multi:     $([ "${SKIP_MULTI_INSTANCE:-}" = "1" ] && echo "skipped (SKIP_MULTI_INSTANCE=1)" || echo "enabled (phase 8)")"
echo ""

# --- Container helpers ---
# Defined ONCE, up front, rather than re-defined inside each phase. Both read the
# current value of the CONTAINER_NAME global at call time, so re-discovering the
# container (Phase 3 / Phase 7) just reassigns CONTAINER_NAME -- no redefinition
# needed. This mirrors how migrate_daaf.sh defines its container helpers once at
# the top, and it avoids the "function defined later" (SC2218) heuristic that a
# per-phase definition triggers.
CONTAINER_NAME=""
container_exec() {
    docker exec "${CONTAINER_NAME}" "$@" </dev/null
}
container_git() {
    docker exec "${CONTAINER_NAME}" git -C /daaf "$@" </dev/null 2>/dev/null | tr -d '\r'
}

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

# Stop and remove containers (default instance)
docker rm -f "${CONTAINER_MAIN}" 2>/dev/null || true
docker rm -f "${CONTAINER_INIT}" 2>/dev/null || true

# Remove the data volume
docker volume rm "${VOLUME_NAME}" 2>/dev/null || true

# Remove the Claude Code state volume too. A prior run (or a migrated install)
# creates this once the current compose file is in play; leaving it behind would
# leak Claude auth/session state across test runs. Absence is tolerated (older
# installs predate it) -- the `|| true` swallows "no such volume".
docker volume rm "${CLAUDE_VOLUME_NAME}" 2>/dev/null || true

# Remove the image
docker rmi "${IMAGE_NAME}" 2>/dev/null || true

# Clean up any leftovers from a previous, possibly aborted, multi-instance pass
# (phase 8) so its state cannot poison this run's coexistence checks.
docker rm -f "${SECOND_CONTAINER_MAIN}" 2>/dev/null || true
docker rm -f "${SECOND_CONTAINER_INIT}" 2>/dev/null || true
docker volume rm "${SECOND_VOLUME_NAME}" 2>/dev/null || true
docker volume rm "${SECOND_CLAUDE_VOLUME_NAME}" 2>/dev/null || true
docker rmi "${SECOND_IMAGE_NAME}" 2>/dev/null || true

success "Clean slate achieved."
echo ""

# =====================================================================
# PHASE 2: Install Old Version (era-authentic pathway)
# =====================================================================
echo "[2/7] ${BOLD}Install ${TEST_VERSION} (Era ${TEST_ERA} pathway: ${ERA_LABEL})${RESET}"
echo ""

cd "${TEST_DIR}" || { error "Cannot enter test directory: ${TEST_DIR}"; exit 1; }

# HOST_DIR is where migrate_daaf.sh will be run from in Phase 6 -- for each era
# this is the directory a real user would have run it from (the one holding
# docker-compose.yml).
HOST_DIR=""
# Era 2 only: the synthetic root commit's SHA, captured in Phase 3 before
# migration can graft it (initialized here for set -u safety on other eras).
ERA2_ROOT_SHA=""

if [ "${TEST_ERA}" = "1" ]; then
    # ----- Era 1: the documented v1.0.0 pathway -----
    # Verbatim flow from v1.0.0 user_reference/01_installation_and_quickstart.md:
    #   git clone https://github.com/DAAF-Contribution-Community/daaf.git
    #   cd daaf
    #   docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox cp -a /source/. /dest/
    #   docker compose up -d --build
    # (v1.0.0's busybox copy has NO sh -c wrapper -- that arrived in v2.0.0.)
    if ! command -v git >/dev/null 2>&1; then
        error "git not found on the host PATH -- Era 1 replays the documented git clone."
        exit 1
    fi

    info "Cloning DAAF repo (documented v1.0.0 flow)..."
    CLONE_DIR="${TEST_DIR}/daaf"
    if ! git clone "https://github.com/${REPO}.git" "${CLONE_DIR}"; then
        error "git clone failed -- cannot replay the Era 1 install."
        exit 1
    fi

    # Time-machine deviation (see header): rewind main to the tag, because a
    # v1.0.0-era user's clone HAD main at v1.0.0. checkout -B moves the branch
    # pointer and working tree while keeping origin + tracking config intact.
    if ! git -C "${CLONE_DIR}" checkout -B main "${TEST_VERSION}"; then
        error "git checkout -B main ${TEST_VERSION} failed -- cannot pin the Era 1 tree."
        exit 1
    fi

    cd "${CLONE_DIR}" || { error "Cannot enter clone dir: ${CLONE_DIR}"; exit 1; }
    info "Copying the clone into the Docker volume (documented busybox step)..."
    if ! docker run --rm -v "${PWD}:/source:ro" -v "${VOLUME_NAME}:/dest" busybox cp -a /source/. /dest/; then
        error "busybox copy into volume ${VOLUME_NAME} failed."
        exit 1
    fi

    # v1.0.0's compose file has no `name:` key, so the compose project name
    # comes from THIS directory's name ("daaf") -- reproducing the era's
    # container/volume names (daaf-daaf-docker-1 / daaf_daaf-data).
    info "Building and starting the v1.0.0 container (docker compose up -d --build)..."
    info "This builds the OLD Dockerfile -- authentic and slow on a cold cache..."
    if ! docker compose up -d --build; then
        error "docker compose up failed for the v1.0.0 build. If the base image or"
        error "Claude installer has drifted upstream, that is a real finding about"
        error "resurrecting this era -- see the header BUILD COST note."
        exit 1
    fi
    HOST_DIR="${CLONE_DIR}"

elif [ "${TEST_ERA}" = "2" ]; then
    # ----- Era 2: the documented v2.0.x ZIP pathway -----
    # Verbatim flow from v2.0.x user_reference/01_installation_and_quickstart.md
    # (macOS/Linux variant):
    #   curl -L -o daaf.zip https://github.com/.../archive/refs/heads/main.zip
    #   unzip daaf.zip
    #   cd daaf-main
    #   docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox sh -c 'cp -a /source/. /dest/'
    #   docker compose up -d --build
    # Time-machine deviation (see header): the TAG's ZIP stands in for that
    # era's main.zip. No .git comes out of a ZIP; the era's container
    # entrypoint git-inits /daaf on first start (verified verbatim at both
    # tags: git init, branch -m main, add -A, commit "Initial commit: DAAF
    # framework", NO remote) -- Phase 3 waits for and verifies that.
    if ! command -v unzip >/dev/null 2>&1; then
        error "unzip not found on the host PATH -- Era 2 replays the documented ZIP flow."
        exit 1
    fi

    info "Downloading release ZIP (documented v2.0.x flow, pinned to the tag)..."
    if ! curl -fsSL -o "${TEST_DIR}/daaf.zip" "https://github.com/${REPO}/archive/refs/tags/${TEST_VERSION}.zip"; then
        error "Failed to download the ${TEST_VERSION} ZIP from GitHub."
        exit 1
    fi
    if ! unzip -q "${TEST_DIR}/daaf.zip" -d "${TEST_DIR}"; then
        error "Failed to extract ${TEST_DIR}/daaf.zip."
        exit 1
    fi

    # GitHub names the ZIP's root folder <repo>-<ref> (with a version-like
    # tag's leading "v" stripped) -- detect it instead of hardcoding.
    # `|| true` guards the low-probability find-vs-head SIGPIPE race under
    # `set -e` (head -1 closing the pipe before find finishes writing).
    EXTRACT_DIR=$(find "${TEST_DIR}" -maxdepth 1 -type d -name 'daaf-*' | head -1 || true)
    if [ -z "${EXTRACT_DIR}" ]; then
        error "Could not find the extracted daaf-* folder under ${TEST_DIR}."
        exit 1
    fi

    cd "${EXTRACT_DIR}" || { error "Cannot enter extract dir: ${EXTRACT_DIR}"; exit 1; }
    info "Copying the extracted tree into the Docker volume (documented busybox step)..."
    if ! docker run --rm -v "${PWD}:/source:ro" -v "${VOLUME_NAME}:/dest" busybox sh -c 'cp -a /source/. /dest/'; then
        error "busybox copy into volume ${VOLUME_NAME} failed."
        exit 1
    fi

    # v2.0.x compose hardcodes `name: daaf`, so project naming is stable
    # regardless of this directory's name (daaf-2.0.1 etc.).
    info "Building and starting the ${TEST_VERSION} container (docker compose up -d --build)..."
    info "This builds the OLD Dockerfile -- authentic and slow on a cold cache..."
    if ! docker compose up -d --build; then
        error "docker compose up failed for the ${TEST_VERSION} build -- see the header BUILD COST note."
        exit 1
    fi
    HOST_DIR="${EXTRACT_DIR}"

else
    # ----- Era 3: the version's own install script (v2.1.0+ / branches) -----
    info "Installing DAAF via the ref's own install.sh from branch/tag: ${TEST_VERSION}"
    info "This will build the Docker image and clone the repo -- may take several minutes..."
    echo ""

    # Use the install script from the target version's own branch/tag. Download
    # to a temp file FIRST rather than `bash -c "$(curl ...)"`: on a curl
    # failure the command-substitution collapses to `bash -c ""`, which exits 0
    # and silently no-ops -- the install never runs, and the failure only
    # surfaces later as a confusing "volume not found" error. Fetching to a
    # file lets us fail loudly and precisely here if the download fails or
    # comes back empty.
    INSTALL_SCRIPT="${TEST_DIR}/install_old.sh"
    if ! curl -fsSL "https://raw.githubusercontent.com/${REPO}/${TEST_VERSION}/scripts/host/install.sh" -o "${INSTALL_SCRIPT}"; then
        error "Failed to download install.sh for ${TEST_VERSION} from GitHub."
        error "Check your internet connection and that the tag/branch '${TEST_VERSION}' exists."
        exit 1
    fi
    if [ ! -s "${INSTALL_SCRIPT}" ]; then
        error "Downloaded install.sh for ${TEST_VERSION} is empty -- aborting."
        exit 1
    fi
    DAAF_BRANCH="${TEST_VERSION}" DAAF_NESTED=1 bash "${INSTALL_SCRIPT}"

    # install.sh creates ./daaf-docker under the invocation directory.
    HOST_DIR="${TEST_DIR}/daaf-docker"
fi

# Verify install succeeded
if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
    error "Installation failed -- volume ${VOLUME_NAME} not found."
    exit 1
fi
if [ ! -f "${HOST_DIR}/docker-compose.yml" ]; then
    warn "docker-compose.yml not found in ${HOST_DIR} -- migration will treat this as a compose-less host dir."
fi

success "DAAF ${TEST_VERSION} installed via the Era ${TEST_ERA} pathway."
echo ""

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
echo "[3/7] ${BOLD}Verify Era ${TEST_ERA} state${RESET}"
echo ""

# Discover container (CONTAINER_NAME is a global the helpers read)
CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
if [ -z "${CONTAINER_NAME}" ]; then
    error "No container found using volume ${VOLUME_NAME}."
    exit 1
fi

CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
if [ "${CONTAINER_STATE}" != "running" ]; then
    info "Starting container ${CONTAINER_NAME}..."
    docker start "${CONTAINER_NAME}" >/dev/null 2>&1
fi

# Wait for exec readiness (fresh first boot can lag briefly)
RETRIES=0
while [ "${RETRIES}" -lt 30 ]; do
    if container_exec true >/dev/null 2>&1; then
        break
    fi
    RETRIES=$((RETRIES + 1))
    sleep 2
done
if [ "${RETRIES}" -ge 30 ]; then
    error "Container ${CONTAINER_NAME} did not become exec-ready within 60 seconds."
    exit 1
fi

if [ "${TEST_ERA}" = "1" ]; then
    # Era 1 expectation: /daaf carries the clone's full .git -- origin remote
    # pointing at the official repo, branch main checked out.
    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    BRANCH_CHECK=$(container_git branch --show-current 2>/dev/null || echo "")
    if echo "${ORIGIN_CHECK}" | grep -qi "${REPO}" && [ "${BRANCH_CHECK}" = "main" ]; then
        success "Era 1 state verified (origin remote + branch main from the clone)."
    else
        error "Era 1 replay did not produce the expected state (origin: '${ORIGIN_CHECK}', branch: '${BRANCH_CHECK}')."
        error "Expected the documented clone flow to leave origin=${REPO} and branch=main."
        exit 1
    fi

elif [ "${TEST_ERA}" = "2" ]; then
    # Era 2 expectation: the era's entrypoint git-inits /daaf on FIRST start
    # (git init; branch -m main; add -A; commit "Initial commit: DAAF
    # framework"; no remote). The commit of the full tree can take a few
    # seconds after the container reports running -- wait for HEAD to exist.
    info "Waiting for the era's entrypoint to git-init /daaf (first boot)..."
    RETRIES=0
    HEAD_SHA=""
    while [ "${RETRIES}" -lt 30 ]; do
        HEAD_SHA=$(container_git rev-parse HEAD 2>/dev/null || echo "")
        case "${HEAD_SHA}" in
            ""|*HEAD*) ;;  # not ready yet (empty, or literal "HEAD" from an unborn branch)
            *) break ;;
        esac
        RETRIES=$((RETRIES + 1))
        sleep 2
    done
    case "${HEAD_SHA}" in
        ""|*HEAD*)
            error "Era 2 entrypoint never produced an initial commit in /daaf (waited 60s)."
            error "The ZIP-era replay is broken -- inspect container logs: docker logs ${CONTAINER_NAME}"
            exit 1
            ;;
    esac

    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    BRANCH_CHECK=$(container_git branch --show-current 2>/dev/null || echo "")
    COMMIT_COUNT=$(container_git rev-list --count HEAD 2>/dev/null || echo "0")
    if [ -z "${ORIGIN_CHECK}" ] && [ "${BRANCH_CHECK}" = "main" ] && [ "${COMMIT_COUNT}" = "1" ]; then
        # Capture the synthetic root's SHA NOW, pre-migration. Check 3 must
        # interrogate THIS commit later: `git replace --graft` adds a
        # replacement ref rather than rewriting the root, so post-graft
        # `rev-list --max-parents=0 HEAD` walks THROUGH the grafted root into
        # upstream history and returns upstream's genuine root -- parentless
        # by definition, forever. Inspecting that commit produced a false
        # FAIL on a healthy migration (repro: scripts/scratch/graft_repro.sh
        # in the session workspace).
        ERA2_ROOT_SHA="${HEAD_SHA}"
        success "Era 2 state verified (local-only repo, single synthetic root commit ${HEAD_SHA:0:12}, no remote)."
    else
        error "Era 2 replay did not produce the expected state (origin: '${ORIGIN_CHECK}', branch: '${BRANCH_CHECK}', commits: '${COMMIT_COUNT}')."
        error "Expected: no remote, branch main, exactly 1 entrypoint commit."
        exit 1
    fi

else
    # Era 3 expectation: install.sh cloned with origin retained. For a TAG,
    # the shallow `-b <tag>` clone leaves a detached HEAD no real user had
    # (real users installed from branch main) -- normalize per the header note.
    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    if [ -z "${ORIGIN_CHECK}" ]; then
        error "Era 3 install left no origin remote -- unexpected for the modern install pathway."
        exit 1
    fi

    if [[ "${TEST_VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        info "Normalizing tag install to a real user's git state (checkout -B main at the tag commit)..."
        container_git checkout -B main 2>/dev/null || true
        BRANCH_CHECK=$(container_git branch --show-current 2>/dev/null || echo "")
        if [ "${BRANCH_CHECK}" != "main" ]; then
            error "Era 3 normalization failed -- expected branch main, got '${BRANCH_CHECK}'."
            exit 1
        fi
    fi
    success "Era 3 state verified (origin remote present: ${ORIGIN_CHECK})."
fi

echo ""

# =====================================================================
# PHASE 4: Simulate User Work (Committed)
# =====================================================================
echo "[4/7] ${BOLD}Simulate committed user work${RESET}"
echo ""

info "Creating committed framework changes and research files..."

# FIXTURE RULES (mirrored with the .ps1 twin):
#   - Framework-change markers live in NEW files (upstream has no such path,
#     so update merges can never conflict on them). The old CLAUDE.md-append
#     markers were conflict bait: daaf_dev heavily rewrites CLAUDE.md relative
#     to the old eras, and a merge conflict would abort the update for reasons
#     unrelated to migration correctness.
#   - Fixture existence is verified BEFORE migration runs, so a broken fixture
#     aborts here instead of surfacing as a bogus "not preserved" FAIL later.

# Create a research project
container_exec mkdir -p /daaf/research/2026-01-15_Test_Analysis/data /daaf/research/2026-01-15_Test_Analysis/scripts /daaf/research/2026-01-15_Test_Analysis/output
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
container_exec bash -c 'echo "# Test Analysis" > /daaf/research/2026-01-15_Test_Analysis/README.md'

# Make a framework modification: a NEW file under agent_reference/ (see
# FIXTURE RULES above for why this is not a CLAUDE.md append).
container_exec bash -c 'echo "test-migration-marker: committed" > /daaf/agent_reference/test_migration_marker.md'

# Commit everything
container_git add -A
container_git commit -m "Test: Add research project and framework tweaks"

COMMITTED_SHA=$(container_git rev-parse HEAD)
if [ -z "${COMMITTED_SHA}" ]; then
    error "Fixture commit failed -- no HEAD SHA readable. Cannot proceed to migration with unplanted fixtures."
    exit 1
fi
# Verify the fixtures actually landed IN the commit (the old harness only
# discovered missing fixtures at Phase 7, after migration had already run).
COMMITTED_FILES=$(container_git show --name-only --format= HEAD)
for MUST_HAVE in \
    "research/2026-01-15_Test_Analysis/scripts/01_fetch.py" \
    "research/2026-01-15_Test_Analysis/data/test_data.txt" \
    "agent_reference/test_migration_marker.md"; do
    if ! echo "${COMMITTED_FILES}" | grep -qF "${MUST_HAVE}"; then
        error "Fixture file '${MUST_HAVE}' is missing from the fixture commit -- aborting before migration."
        exit 1
    fi
done
info "Committed changes at: ${COMMITTED_SHA:0:12}"
success "Committed user work created."
echo ""

# =====================================================================
# PHASE 5: Simulate User Work (Uncommitted)
# =====================================================================
echo "[5/7] ${BOLD}Simulate uncommitted user work${RESET}"
echo ""

info "Creating uncommitted framework changes and research files..."

# Add more uncommitted research files (untracked -- the updater never touches
# untracked files, so these must survive verbatim)
container_exec mkdir -p /daaf/research/2026-02-10_WIP_Analysis/scripts
container_exec bash -c 'echo "Work in progress data" > /daaf/research/2026-02-10_WIP_Analysis/notes.md'
container_exec bash -c 'cat > /daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py << "PYEOF"
# --- Config ---
# INTENT: WIP exploration script -- uncommitted
print("WIP script")
PYEOF'

# Make an uncommitted framework change: a NEW untracked file (see Phase 4
# FIXTURE RULES for why this is not a CLAUDE.md append).
container_exec bash -c 'echo "test-migration-marker: uncommitted" > /daaf/agent_reference/test_migration_marker_uncommitted.md'

# Dirty a TRACKED file: append a line to the README committed in Phase 4.
# This is what exercises the updater's stash/pop path (dirty tracked changes
# get stashed before the merge and popped after). It lives in research/ where
# upstream never writes, so the pop can never conflict.
container_exec bash -c 'echo uncommitted-stash-check >> /daaf/research/2026-01-15_Test_Analysis/README.md'

# Verify the uncommitted fixtures actually exist before migration runs
for MUST_EXIST in \
    "/daaf/research/2026-02-10_WIP_Analysis/notes.md" \
    "/daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py" \
    "/daaf/agent_reference/test_migration_marker_uncommitted.md"; do
    if ! container_exec test -f "${MUST_EXIST}"; then
        error "Uncommitted fixture '${MUST_EXIST}' was not created -- aborting before migration."
        exit 1
    fi
done
if ! container_exec grep -q uncommitted-stash-check /daaf/research/2026-01-15_Test_Analysis/README.md; then
    error "Dirty-file fixture (README.md append) was not created -- aborting before migration."
    exit 1
fi

success "Uncommitted user work created."
echo ""

# =====================================================================
# PHASE 6: Run Migration
# =====================================================================
echo "[6/7] ${BOLD}Run migration script${RESET}"
echo ""

info "Copying migration script from local repo..."

# The host directory is era-specific (set in Phase 2): the clone dir (Era 1),
# the extracted ZIP dir (Era 2), or install.sh's daaf-docker dir (Era 3) --
# i.e., wherever a real user of that era would run migrate_daaf.sh from (the
# directory holding docker-compose.yml).
if [ ! -d "${HOST_DIR}" ]; then
    error "Era host directory vanished: ${HOST_DIR}"
    exit 1
fi

# Copy the local migration script to the host dir
cp "${LOCAL_REPO_ROOT}/scripts/host/migrate_daaf.sh" "${HOST_DIR}/migrate_daaf.sh"
chmod +x "${HOST_DIR}/migrate_daaf.sh"

info "Running migration with DAAF_BRANCH=${MIGRATION_BRANCH}..."
echo ""

cd "${HOST_DIR}" || { error "Cannot enter host directory: ${HOST_DIR}"; exit 1; }

# Snapshot whether the Claude state volume exists RIGHT NOW, immediately before
# migration runs. The backup-content assertion (Check 11) needs to know whether
# the source volume existed AT BACKUP TIME, and backup happens inside migration.
# Capturing the flag here -- rather than re-inspecting live after migration --
# makes the gate robust: anything migration does afterward (a fallback
# `docker compose up` against the current compose file, or phase 8's install.sh)
# can legitimately create the volume, and a post-migration inspect would then
# wrongly flip an absent-at-backup-time skip into a FAIL.
if docker volume inspect "${CLAUDE_VOLUME_NAME}" >/dev/null 2>&1; then
    CLAUDE_VOLUME_EXISTED_PRE_MIGRATION=true
else
    CLAUDE_VOLUME_EXISTED_PRE_MIGRATION=false
fi

# Run migration with the branch env var. Do NOT pipe input in: migrate_daaf.sh
# reads interactive prompts from /dev/tty (not stdin), so a piped "n" was a
# no-op that only obscured intent. Non-interactive detection inside the migration
# script auto-skips the optional update prompt on its own.
#
# Capture the exit status. `set -e` is active, so guard the invocation with an
# `if` (a bare call would abort the whole harness on a nonzero exit before we
# could report it). MIGRATION_EXIT feeds the truthful outcome + Phase 7 banner.
MIGRATION_EXIT=0
if DAAF_BRANCH="${MIGRATION_BRANCH}" DAAF_NESTED=1 bash migrate_daaf.sh; then
    MIGRATION_EXIT=0
else
    MIGRATION_EXIT=$?
fi

echo ""
# Fix B: report the migration outcome TRUTHFULLY. A nonzero exit is a real FAIL
# fed into the results counter -- never printed as SUCCESS. Verification (Phase
# 7) still runs regardless, because it shows the blast radius of a failed
# migration; but it runs under a banner that makes clear migration itself failed.
if [ "${MIGRATION_EXIT}" -eq 0 ]; then
    success "Migration script completed (exit code 0)."
    check "Migration script completed successfully (exit 0)" "0"
else
    error "Migration script did NOT complete successfully (exit code ${MIGRATION_EXIT})."
    error "Verification below still runs to show the blast radius, but migration itself FAILED."
    check "Migration script completed successfully (exit ${MIGRATION_EXIT})" "1"
fi
echo ""

# =====================================================================
# PHASE 7: Verification
# =====================================================================
echo "[7/7] ${BOLD}Verification${RESET}"
if [ "${MIGRATION_EXIT}" -ne 0 ]; then
    echo "  ${RED}(Migration FAILED with exit code ${MIGRATION_EXIT} -- the checks below report the blast radius, not a healthy migration.)${RESET}"
fi
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
# CONTAINER_NAME was just re-discovered above; the top-level helpers pick it up.

echo "${BOLD}  Git State Checks:${RESET}"

# Check 1: Remote exists and points to correct repo
ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || echo "")
if echo "${ORIGIN_URL}" | grep -qi "${REPO}"; then
    check "Remote 'origin' points to official DAAF repo" "0"
else
    check "Remote 'origin' points to official DAAF repo (got: '${ORIGIN_URL}')" "1"
fi

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
EXPECTED_TRACKING="origin/main"
if [ "${TEST_ERA}" = "3" ] && ! [[ "${TEST_VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    EXPECTED_TRACKING="origin/${TEST_VERSION}"
fi
TRACKING=$(container_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "")
if [ "${TRACKING}" = "${EXPECTED_TRACKING}" ]; then
    check "Upstream tracking set to ${EXPECTED_TRACKING}" "0"
else
    check "Upstream tracking set to ${EXPECTED_TRACKING} (got: '${TRACKING}')" "1"
fi

# Check 3: Era 2 only -- the graft must now exist ON THE SYNTHETIC ROOT whose
# SHA Phase 3 captured pre-migration. Do NOT re-discover the root with
# `rev-list --max-parents=0` here: after a SUCCESSFUL graft that command walks
# through the replaced root and returns upstream's genuine root, which is
# parentless forever -- inspecting it produced a false FAIL on a healthy
# migration (field run 3; repro in the session workspace's
# scripts/scratch/graft_repro.sh). cat-file honors replace refs, so the
# grafted parent is visible on the captured SHA.
if [ "${TEST_ERA}" = "2" ]; then
    if [ -n "${ERA2_ROOT_SHA}" ]; then
        # grep -c already prints "0" on no-match (while exiting 1) -- a
        # `|| echo "0"` fallback here would DOUBLE the output to "0\n0" under
        # pipefail and break the integer test below exactly when the graft is
        # absent. `|| true` absorbs the exit code; the :-0 guard covers the
        # only truly empty case (substitution failure).
        PARENT_COUNT=$(container_git cat-file -p "${ERA2_ROOT_SHA}" 2>/dev/null | grep -c '^parent ' || true)
        if [ "${PARENT_COUNT:-0}" -gt 0 ]; then
            check "Era 2 graft in place (synthetic root now has a parent)" "0"
        else
            check "Era 2 graft in place (synthetic root now has a parent)" "1"
        fi
    else
        check "Era 2 graft in place (pre-migration root SHA was not captured)" "1"
    fi
fi

# Check 3b (all eras): a common ancestor with origin/main must exist -- via
# genuine history (Era 1/3) or via the graft (Era 2). This is the property
# update_daaf's merges depend on.
MERGE_BASE=$(container_git merge-base HEAD origin/main 2>/dev/null || echo "")
if [ -n "${MERGE_BASE}" ]; then
    check "Common ancestor exists with origin/main" "0"
else
    check "Common ancestor exists with origin/main" "1"
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

# Check 6: Committed framework marker file survived (content-verified)
if container_exec grep -q 'test-migration-marker: committed' /daaf/agent_reference/test_migration_marker.md; then
    check "Committed framework changes preserved" "0"
else
    check "Committed framework changes preserved" "1"
fi

# Check 7: Uncommitted (untracked) framework marker file survived
if container_exec grep -q 'test-migration-marker: uncommitted' /daaf/agent_reference/test_migration_marker_uncommitted.md; then
    check "Uncommitted framework changes preserved" "0"
else
    check "Uncommitted framework changes preserved" "1"
fi

# Check 7b: Dirty tracked change survived. If the user took the update,
# update_daaf stashed this before merging and popped it after -- this line
# surviving is the stash/pop path working end to end. If the update was
# declined, migration alone must not have touched it either way.
if container_exec grep -q uncommitted-stash-check /daaf/research/2026-01-15_Test_Analysis/README.md; then
    check "Dirty tracked change preserved (updater stash/pop path)" "0"
else
    check "Dirty tracked change preserved (updater stash/pop path)" "1"
fi

# Check 8: Committed SHA still in history.
# Capture-then-grep, NOT `container_git log | grep -q`: grep -q exits on the
# first match and closes the pipe, git log upstream dies of SIGPIPE (141), and
# `set -o pipefail` turns a FOUND commit into a false "lost" FAIL. (Review
# repro: PIPESTATUS='141 0' with the piped form.)
GITLOG=$(container_git log --oneline)
if printf '%s\n' "${GITLOG}" | grep -q "${COMMITTED_SHA:0:7}"; then
    check "Committed changes still in git history" "0"
else
    check "Committed changes still in git history" "1"
fi

echo ""
echo "${BOLD}  Host Script Checks:${RESET}"

# Check 9: Host scripts were downloaded.
# This list mirrors what migrate_daaf.sh actually fetches today (see its
# "for FILE in ..." download loop): the full .sh utility set -- including
# daaf.sh + daaf_lib.sh (the macOS/Linux Control Panel) -- plus the two shipped
# text files. The .ps1 twin uses a DIFFERENT list (see test_migration.ps1):
# daaf.sh/daaf_lib.sh are never shipped to Windows (commit 4fa8c43), and Windows
# gets the .ps1 variants instead.
for SCRIPT in daaf.sh daaf_lib.sh backup_daaf.sh restore_from_backup.sh rebuild_daaf.sh update_daaf.sh run_daaf.sh view_logs.sh view_notebooks.sh view_quarto.sh run_vscode.sh environment_settings_example.txt README.txt; do
    if [ -f "${HOST_DIR}/${SCRIPT}" ]; then
        check "Host script downloaded: ${SCRIPT}" "0"
    else
        check "Host script downloaded: ${SCRIPT}" "1"
    fi
done

echo ""
echo "${BOLD}  Backup Checks:${RESET}"

# Check 10: Backup directory was created during migration
BACKUP_DIR=$(find "${HOST_DIR}" -maxdepth 1 -type d -name '*_daaf_backup' 2>/dev/null | head -1 || echo "")
if [ -n "${BACKUP_DIR}" ]; then
    check "Backup directory created during migration" "0"

    # Check 11: Backup content is complete. The on-disk backup layout produced by
    # backup_daaf.sh (verified against that script) is:
    #   <backup>/                      data-volume CONTENTS at the root (CLAUDE.md,
    #                                  research/, etc. -- copied via "docker cp .../.")
    #   <backup>/.daaf-claude-config/  Claude Code state volume payload (hidden
    #                                  subfolder; ONLY present if the claude-config
    #                                  volume existed at backup time)
    #   <backup>/.daaf-permissions     executable-permission manifest at the root
    #   <backup>/.daaf-symlinks        symlink manifest at the root (always present
    #                                  in current backups, 0-byte when the volume has
    #                                  no symlinks; absent only in pre-feature backups)
    #
    # Data payload: assert a known volume file (CLAUDE.md) is at the backup root.
    if [ -f "${BACKUP_DIR}/CLAUDE.md" ]; then
        check "Backup contains data-volume payload (CLAUDE.md at root)" "0"
    else
        check "Backup contains data-volume payload (CLAUDE.md at root)" "1"
    fi

    # Permissions manifest: always written by a current backup_daaf.sh.
    if [ -f "${BACKUP_DIR}/.daaf-permissions" ]; then
        check "Backup contains .daaf-permissions manifest" "0"
    else
        check "Backup contains .daaf-permissions manifest" "1"
    fi

    # Symlink manifest: CONDITIONAL on the backup ERA, not on symlink presence.
    # backup_daaf.sh's staging step always runs `paste`, which ALWAYS creates
    # .daaf-symlinks (a 0-byte file when the volume has no symlinks) -- so a CURRENT
    # backup always has the file, and absence means only that the backup predates
    # this feature. This harness replays pre-feature eras, where the manifest is
    # legitimately absent, so a missing file here is NOT a defect: present => PASS;
    # absent => informational skip (pre-feature backup).
    if [ -f "${BACKUP_DIR}/.daaf-symlinks" ]; then
        check "Backup contains .daaf-symlinks manifest" "0"
    else
        info "Skipped .daaf-symlinks check: no symlink manifest in this backup (it predates the symlink-safe backup feature; current backups always include the file, 0-byte when the volume has no symlinks)."
    fi

    # Claude state payload: CONDITIONAL. backup_daaf.sh only writes the
    # .daaf-claude-config/ subfolder when the claude-config volume exists at
    # backup time. Every era this harness replays (v1.0.0 through v2.1.0)
    # predates that volume -- their compose files define no claude-config
    # volume, and the migration backs up BEFORE any current-compose
    # `docker compose up` could create it, so the subfolder is legitimately
    # absent there. Gate the assertion on CLAUDE_VOLUME_EXISTED_PRE_MIGRATION --
    # the flag captured just before migration (phase 6) -- NOT on a live inspect
    # here: by this point migration (and, on non-skipped runs, phase 8's
    # install.sh) may have created the volume, which a live inspect would
    # mistake for "should have been in the backup." Three-way outcome:
    # subfolder present -> PASS; absent but volume existed pre-migration ->
    # FAIL (a real backup gap); absent and volume did not exist pre-migration ->
    # informational skip.
    if [ -d "${BACKUP_DIR}/.daaf-claude-config" ]; then
        check "Backup contains Claude state payload (.daaf-claude-config/)" "0"
    elif [ "${CLAUDE_VOLUME_EXISTED_PRE_MIGRATION}" = "true" ]; then
        # The volume existed at backup time yet the subfolder is missing -- real gap.
        check "Backup contains Claude state payload (.daaf-claude-config/)" "1"
    else
        info "Skipped Claude state payload check: source volume '${CLAUDE_VOLUME_NAME}' did not exist at backup time (install predates it)."
    fi
else
    check "Backup directory created during migration" "1"
    warn "Skipping backup-content checks: no backup directory to inspect."
fi

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
if [ "${SKIP_MULTI_INSTANCE:-}" != "1" ]; then
    echo ""
    echo "${BOLD}==========================================${RESET}"
    echo "${BOLD}  Phase 8: Multi-Instance Coexistence${RESET}"
    echo "${BOLD}==========================================${RESET}"
    echo ""
    echo "  Second project: ${SECOND_PROJECT_NAME}"
    echo "  Ports:          marimo=${SECOND_PORT_MARIMO} log=${SECOND_PORT_LOGVIEWER} vscode=${SECOND_PORT_VSCODE}"
    echo ""

    # --- 8a. Create the second install directory + environment_settings.txt ---
    info "Creating second install directory and environment_settings.txt..."
    SECOND_DIR="${TEST_DIR}/instance2"
    mkdir -p "${SECOND_DIR}"

    # Write the four multi-instance keys the compose file interpolates. The key
    # names (DAAF_PROJECT_NAME / DAAF_PORT_MARIMO / DAAF_PORT_LOGVIEWER /
    # DAAF_PORT_VSCODE) match environment_settings_example.txt and how
    # install.sh/rebuild_daaf.sh read them. install.sh derives the volume name
    # from DAAF_PROJECT_NAME (shell env first), and compose interpolates all four
    # from the shell env at build/up time -- so exporting them below is what makes
    # the second instance actually reproject.
    {
        echo "DAAF_PROJECT_NAME=${SECOND_PROJECT_NAME}"
        echo "DAAF_PORT_MARIMO=${SECOND_PORT_MARIMO}"
        echo "DAAF_PORT_LOGVIEWER=${SECOND_PORT_LOGVIEWER}"
        echo "DAAF_PORT_VSCODE=${SECOND_PORT_VSCODE}"
    } > "${SECOND_DIR}/environment_settings.txt"
    success "Second environment_settings.txt written."
    echo ""

    # --- 8b. Bring up a fresh CURRENT-branch instance there ---
    # MECHANISM CHOICE: reuse the local install.sh (from the migration branch's
    # repo checkout) rather than hand-rolling `docker compose up`. Rationale:
    # install.sh is the ONLY mechanism that both (1) stands up the container with
    # the correct project-prefixed names AND (2) populates /daaf via git clone.
    # A bare `docker compose up` against the fetched compose file would start an
    # EMPTY-/daaf container (no repo clone), which is not a realistic instance and
    # would make the coexistence checks meaningless. install.sh already reads
    # DAAF_PROJECT_NAME (shell env wins) to derive its volume name, and compose
    # reads all four DAAF_* keys from the shell env for interpolation -- so we
    # export them, point install.sh at the current branch, and run it in the
    # second directory. DAAF_NESTED suppresses its exit pause.
    info "Bringing up second instance from branch '${MIGRATION_BRANCH}' via install.sh..."
    echo ""
    cd "${SECOND_DIR}" || { error "Cannot enter second install dir: ${SECOND_DIR}"; exit 1; }

    (
        export DAAF_PROJECT_NAME="${SECOND_PROJECT_NAME}"
        export DAAF_PORT_MARIMO="${SECOND_PORT_MARIMO}"
        export DAAF_PORT_LOGVIEWER="${SECOND_PORT_LOGVIEWER}"
        export DAAF_PORT_VSCODE="${SECOND_PORT_VSCODE}"
        export DAAF_BRANCH="${MIGRATION_BRANCH}"
        export DAAF_NESTED=1
        # Force a clean re-install so a leftover daaftest2 install (e.g. from an
        # aborted prior run whose phase-1 cleanup never ran) cannot make install.sh
        # halt at its "existing installation detected" prompt and hang/abort the harness.
        export DAAF_FORCE_REINSTALL=1
        bash "${LOCAL_REPO_ROOT}/scripts/host/install.sh"
    ) || warn "Second-instance install.sh exited non-zero -- coexistence checks below will show what actually came up."

    echo ""

    # --- 8c. Verify coexistence ---
    echo "${BOLD}  Multi-Instance Checks:${RESET}"

    # Second instance container is running
    SECOND_STATE=$(docker inspect --format '{{.State.Status}}' "${SECOND_CONTAINER_MAIN}" 2>/dev/null || echo "absent")
    if [ "${SECOND_STATE}" = "running" ]; then
        check "Second instance container running (${SECOND_CONTAINER_MAIN})" "0"
    else
        check "Second instance container running (${SECOND_CONTAINER_MAIN}) (state: ${SECOND_STATE})" "1"
    fi

    # Second instance volumes exist
    if docker volume inspect "${SECOND_VOLUME_NAME}" >/dev/null 2>&1; then
        check "Second instance data volume exists (${SECOND_VOLUME_NAME})" "0"
    else
        check "Second instance data volume exists (${SECOND_VOLUME_NAME})" "1"
    fi
    if docker volume inspect "${SECOND_CLAUDE_VOLUME_NAME}" >/dev/null 2>&1; then
        check "Second instance Claude volume exists (${SECOND_CLAUDE_VOLUME_NAME})" "0"
    else
        check "Second instance Claude volume exists (${SECOND_CLAUDE_VOLUME_NAME})" "1"
    fi

    # The migrated DEFAULT instance must still be intact (coexistence, untouched)
    if docker inspect "${CONTAINER_MAIN}" >/dev/null 2>&1; then
        check "Default instance container still present (${CONTAINER_MAIN})" "0"
    else
        check "Default instance container still present (${CONTAINER_MAIN})" "1"
    fi
    if docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
        check "Default instance data volume still present (${VOLUME_NAME})" "0"
    else
        check "Default instance data volume still present (${VOLUME_NAME})" "1"
    fi

    echo ""

    # --- 8d. Tear the second instance down completely ---
    # Remove container, init container, and both volumes. IMAGE DECISION: remove
    # the second image too. `docker compose build` tags the image from the compose
    # PROJECT name, so with name=daaftest2 the second image is a DISTINCT tag
    # (daaftest2-daaf-docker), NOT shared with the default instance's
    # daaf-daaf-docker -- removing it cannot affect the default instance. The
    # busybox init IMAGE, by contrast, IS shared across instances, so leave it
    # alone (nuke_daaf.sh only removes busybox when no container references it).
    info "Tearing down the second instance (container, init, volumes, distinct image)..."
    docker rm -f "${SECOND_CONTAINER_MAIN}" >/dev/null 2>&1 || true
    docker rm -f "${SECOND_CONTAINER_INIT}" >/dev/null 2>&1 || true
    docker volume rm "${SECOND_VOLUME_NAME}" >/dev/null 2>&1 || true
    docker volume rm "${SECOND_CLAUDE_VOLUME_NAME}" >/dev/null 2>&1 || true
    docker rmi "${SECOND_IMAGE_NAME}" >/dev/null 2>&1 || true

    # Verify teardown succeeded
    if docker inspect "${SECOND_CONTAINER_MAIN}" >/dev/null 2>&1; then
        check "Second instance container removed" "1"
    else
        check "Second instance container removed" "0"
    fi
    if docker volume inspect "${SECOND_VOLUME_NAME}" >/dev/null 2>&1; then
        check "Second instance data volume removed" "1"
    else
        check "Second instance data volume removed" "0"
    fi

    # Coexistence sanity: the default instance survived the teardown untouched.
    if docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
        check "Default instance data volume survived second-instance teardown" "0"
    else
        check "Default instance data volume survived second-instance teardown" "1"
    fi

    success "Second instance torn down."
    cd "${HOST_DIR}" || true
    echo ""
else
    echo ""
    info "Phase 8 (multi-instance) skipped via SKIP_MULTI_INSTANCE=1."
    echo ""
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
