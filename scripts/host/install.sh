#!/usr/bin/env bash
# ============================================================================
# DAAF One-Line Installer (macOS / Linux)
# ============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh | bash
#
# What this script does:
#   1. Creates a minimal build directory (~5 KB)
#   2. Downloads the Dockerfile, docker-compose.yml, and convenience scripts
#   3. Builds the Docker image (Python, data science stack, Claude Code)
#   4. Clones the full DAAF repository into the Docker volume
#   5. Prints instructions for first launch
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Interactivity detection: use /dev/tty instead of stdin (fd 0).
# When users run `curl ... | bash`, stdin is the pipe -- but the user's
# terminal is still available at /dev/tty. CI environments lack a real
# terminal entirely.
#
# DAAF_NESTED is separate: it suppresses the exit prompt (so nested
# scripts don't double-pause) but does NOT suppress interactive prompts.
IS_INTERACTIVE=false
if [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    IS_INTERACTIVE=true
fi

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script like test_migration.sh).
if [ "${IS_INTERACTIVE}" = "true" ] && [ -z "${DAAF_NESTED:-}" ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Configuration ---
REPO="DAAF-Contribution-Community/daaf"
BRANCH="${DAAF_BRANCH:-main}"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
INSTALL_DIR="$(pwd)/daaf-docker"

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    # Match patterns are space/flag-anchored so they cannot collide with the
    # random mktemp INSTALL_DIR path embedded in "$*". The former
    # *"compose"*"up"* / *"compose"*"build"* substring forms were functionally
    # immune here (every real arm returns 0), but are hardened to the same
    # path-proof style used in tests/bash/install.bats and daaf.bats for
    # consistency and future-proofing (a "$*" containing "up" or "build" in its
    # temp path can no longer route to the wrong arm).
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"volume inspect"*) return 1 ;;
            *"buildx inspect"*) return 1 ;;
            *"buildx create"*) return 0 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"exec -T daaf-docker true"*) return 0 ;;
            *"git clone"*) return 0 ;;
            *"bash -c"*) return 0 ;;
            *"test -f /daaf/CLAUDE.md"*) return 0 ;;
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

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/install.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

echo ""
echo "=========================================="
echo "  DAAF Installer"
echo "=========================================="
echo ""
echo "Branch: ${BRANCH}"
echo ""

# --- Preflight checks ---
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal."
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start Docker Desktop on your computer and try again."
    exit 1
fi

# --- Check for existing installation ---
# Derive the project-prefixed data volume name so multi-instance installs
# (DAAF_PROJECT_NAME set) are detected correctly. The value comes from the shell
# environment first, else DAAF_PROJECT_NAME in the existing install's
# environment_settings.txt, else the "daaf" default (byte-for-byte identical to
# the former hardcoded "daaf_daaf-data"). Parse only that one key (never `source`
# -- the file holds API keys); shell env wins; CR stripped; Bash 3.2 safe.
INSTALL_PROJECT_NAME="${DAAF_PROJECT_NAME:-}"
if [ -z "${INSTALL_PROJECT_NAME}" ] && [ -f "${INSTALL_DIR}/environment_settings.txt" ]; then
    while IFS= read -r _line || [ -n "${_line}" ]; do
        _line="$(printf '%s' "${_line}" | tr -d '\r')"
        case "${_line}" in
            DAAF_PROJECT_NAME=*)
                INSTALL_PROJECT_NAME="${_line#*=}"
                case "${INSTALL_PROJECT_NAME}" in
                    \"*\") INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME#\"}"; INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME%\"}" ;;
                    \'*\') INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME#\'}"; INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME%\'}" ;;
                esac
                break
                ;;
        esac
    done < "${INSTALL_DIR}/environment_settings.txt"
fi
DATA_VOLUME_NAME="${INSTALL_PROJECT_NAME:-daaf}_daaf-data"

# --- Bridge the DAAF_DEV build flag into the environment ---
# Unlike DAAF_PROJECT_NAME above (only needed locally to derive the volume name;
# the compose project name comes from the file's `name:` key), the build flag
# must be EXPORTED so `docker compose build` below sees it and forwards it as
# `--build-arg DAAF_DEV=${DAAF_DEV:-0}`. Parse only that one key from the
# just-downloaded environment_settings.txt (never `source` -- the file holds API
# keys); shell env wins; CR stripped; Bash 3.2 safe. Absent file / absent key =
# the flag stays unset, so its build arg defaults to 0 (standard build).
if [ -z "${DAAF_DEV:-}" ] && [ -f "${INSTALL_DIR}/environment_settings.txt" ]; then
    while IFS= read -r _line || [ -n "${_line}" ]; do
        _line="$(printf '%s' "${_line}" | tr -d '\r')"
        case "${_line}" in
            DAAF_DEV=*)
                _dev_val="${_line#*=}"
                case "${_dev_val}" in
                    \"*\") _dev_val="${_dev_val#\"}"; _dev_val="${_dev_val%\"}" ;;
                    \'*\') _dev_val="${_dev_val#\'}"; _dev_val="${_dev_val%\'}" ;;
                esac
                export DAAF_DEV="${_dev_val}"
                break
                ;;
        esac
    done < "${INSTALL_DIR}/environment_settings.txt"
fi

if [ -f "${INSTALL_DIR}/docker-compose.yml" ]; then
    if docker volume inspect "${DATA_VOLUME_NAME}" &>/dev/null; then
        # Volume exists -- this is a completed or substantially completed installation
        if [ "${DAAF_FORCE_REINSTALL:-}" = "1" ]; then
            echo "NOTE: Existing installation detected. Proceeding with re-install (DAAF_FORCE_REINSTALL=1)."
            echo ""
        else
            echo "WARNING: An existing DAAF installation was detected."
            echo ""
            echo "Re-running the installer will overwrite framework files (CLAUDE.md, skills,"
            echo "agents, templates) and local git history. Your research data will NOT be"
            echo "deleted, but a backup is strongly recommended."
            echo ""
            echo "To update DAAF instead (recommended -- preserves local changes):"
            echo "  cd ${INSTALL_DIR}"
            echo "  bash update_daaf.sh"
            echo ""
            echo "To force a fresh re-install, set DAAF_FORCE_REINSTALL=1:"
            echo "  DAAF_FORCE_REINSTALL=1 bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
            echo ""
            exit 1
        fi
    else
        echo "NOTE: A previous install attempt was detected but appears incomplete."
        echo "      Proceeding with a fresh install."
        echo ""
    fi
fi

# --- Create minimal build directory ---
echo "[1/4] Creating initial directory for installation files at ${INSTALL_DIR} ..."
mkdir -p "${INSTALL_DIR}"

# --- Download build-context and utility files ---
echo "[2/4] Downloading installation files ..."
if ! curl -fsSL "${RAW_BASE}/Dockerfile"                          -o "${INSTALL_DIR}/Dockerfile" ||
   ! curl -fsSL "${RAW_BASE}/docker-compose.yml"                   -o "${INSTALL_DIR}/docker-compose.yml" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/daaf.sh"                 -o "${INSTALL_DIR}/daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/daaf_lib.sh"             -o "${INSTALL_DIR}/daaf_lib.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/run_daaf.sh"             -o "${INSTALL_DIR}/run_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/backup_daaf.sh"          -o "${INSTALL_DIR}/backup_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/restore_from_backup.sh"  -o "${INSTALL_DIR}/restore_from_backup.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/rebuild_daaf.sh"         -o "${INSTALL_DIR}/rebuild_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/update_daaf.sh"          -o "${INSTALL_DIR}/update_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/view_logs.sh"            -o "${INSTALL_DIR}/view_logs.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/view_notebooks.sh"      -o "${INSTALL_DIR}/view_notebooks.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/view_quarto.sh"          -o "${INSTALL_DIR}/view_quarto.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/run_vscode.sh"           -o "${INSTALL_DIR}/run_vscode.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/environment_settings_example.txt" -o "${INSTALL_DIR}/environment_settings_example.txt" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/README.txt"                      -o "${INSTALL_DIR}/README.txt"; then
    echo ""
    echo "ERROR: Failed to download installation files from branch '${BRANCH}'."
    echo "Please verify that the branch name is correct and that you have an internet connection."
    echo "You can check available branches at: https://github.com/${REPO}/branches"
    exit 1
fi
chmod +x "${INSTALL_DIR}/daaf.sh" "${INSTALL_DIR}/daaf_lib.sh" "${INSTALL_DIR}/run_daaf.sh" "${INSTALL_DIR}/backup_daaf.sh" "${INSTALL_DIR}/restore_from_backup.sh" "${INSTALL_DIR}/rebuild_daaf.sh" "${INSTALL_DIR}/update_daaf.sh" "${INSTALL_DIR}/view_logs.sh" "${INSTALL_DIR}/view_notebooks.sh" "${INSTALL_DIR}/view_quarto.sh" "${INSTALL_DIR}/run_vscode.sh"

# --- Apple Silicon (arm64) build-time notice ---
# On the Ubuntu noble base, arm64 gets P3M pre-built R binaries (same as x86_64),
# so Apple Silicon no longer compiles R packages from source. The first build is
# still a sizable one-time download, but there is no arm64-specific source-compile
# penalty. A brief heads-up keeps the quiet download/install phase from looking
# like a hang.
DAAF_ARCH="$(uname -m 2>/dev/null || echo unknown)"
if [ "${DAAF_ARCH}" = "arm64" ] || [ "${DAAF_ARCH}" = "aarch64" ]; then
    echo ""
    echo "NOTE: arm64 detected (Apple Silicon or other ARM64 host). The first build"
    echo "      downloads a large stack of Python and R packages, so it takes a while"
    echo "      with some quiet stretches -- this is normal, not a hang. arm64 now"
    echo "      installs pre-built R binaries (no source compilation)."
    echo ""
fi

# --- Optional diagnostic builder (DAAF_DIAG_BUILD=1) ---
# BuildKit clips each step's log output (by size AND by rate), and Docker
# Desktop's DEFAULT builder does not let those limits be raised. The only
# mechanism is a custom docker-container builder with larger
# BUILDKIT_STEP_LOG_MAX_SIZE / _MAX_SPEED, selected via BUILDX_BUILDER. That
# builder has real costs (separate build cache; the built image must be loaded
# back into the Docker image store), so it is opt-in only. Fail-open: any failure
# creating/inspecting it falls back to the default builder.
DIAG_BUILDER_SELECTED=0
if [ "${DAAF_DIAG_BUILD:-}" = "1" ]; then
    if docker buildx inspect daaf-diag-builder >/dev/null 2>&1; then
        DIAG_BUILDER_SELECTED=1
        echo "NOTE: Reusing existing diagnostic buildx builder 'daaf-diag-builder' (raised step-log limits)."
    elif docker buildx create --name daaf-diag-builder --driver docker-container \
            --driver-opt env.BUILDKIT_STEP_LOG_MAX_SIZE=16777216 \
            --driver-opt env.BUILDKIT_STEP_LOG_MAX_SPEED=10485760 >/dev/null 2>&1; then
        DIAG_BUILDER_SELECTED=1
        echo "NOTE: Created diagnostic buildx builder 'daaf-diag-builder' (raised step-log limits)."
    else
        echo "NOTE: DAAF_DIAG_BUILD=1 set, but the diagnostic buildx builder could not be"
        echo "      created. Falling back to the default builder (build logs may be clipped)."
    fi
    if [ "${DIAG_BUILDER_SELECTED}" = "1" ]; then
        echo "      This build uses a separate build cache (slower first run); the image is"
        echo "      loaded back into Docker when the build completes."
        echo ""
    fi
fi

# --- Build the Docker image ---
echo "[3/4] Building Docker image (this may take a few minutes on first run since there are a lot of Python libraries to install)..."
# Project name is set declaratively via the top-level "name: daaf" key in
# docker-compose.yml -- no need to set COMPOSE_PROJECT_NAME here.
# Build and start are split into two commands so that --progress plain can be
# applied to the build step (where it is universally supported) without relying
# on `docker compose up --progress`, which is rejected as "unknown flag" on
# Docker Compose versions prior to ~v2.27.
#
# The BUILDX_BUILDER prefix is applied ONLY on the diagnostic path. On the normal
# path the command must NOT reference BUILDX_BUILDER at all: setting it to the
# empty string still EXPORTS it (set-but-empty, not unset), which relies on
# undocumented docker empty==default semantics and would clobber a user's own
# pre-exported BUILDX_BUILDER. Two explicit branches avoid that.
# `set -e` is active: capture the exit code with `|| BUILD_EXIT=$?` so a non-zero
# build does not abort the script before the error message below can print.
BUILD_EXIT=0
if [ "${DIAG_BUILDER_SELECTED}" = "1" ]; then
    BUILDX_BUILDER="daaf-diag-builder" docker compose -f "${INSTALL_DIR}/docker-compose.yml" build --progress plain || BUILD_EXIT=$?
else
    docker compose -f "${INSTALL_DIR}/docker-compose.yml" build --progress plain || BUILD_EXIT=$?
fi
if [ "${BUILD_EXIT}" -ne 0 ]; then
    echo ""
    echo "ERROR: Docker image build failed. Check the output above for details."
    echo "You can safely re-run this installer to retry (set DAAF_FORCE_REINSTALL=1 if prompted)."
    echo "If the output above contains a line like '[output clipped, log limit 2MiB reached]'"
    echo "(the exact limit varies by Docker version), re-run with DAAF_DIAG_BUILD=1 for"
    echo "unclipped build logs:"
    echo "  DAAF_DIAG_BUILD=1 bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
    exit 1
fi
echo "Starting container..."
if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" up -d; then
    echo ""
    echo "ERROR: Failed to start the Docker container after build. Check the output above for details."
    echo "You can safely re-run this installer to retry (set DAAF_FORCE_REINSTALL=1 if prompted)."
    exit 1
fi

# --- Wait for container to be ready ---
echo "      Waiting for container to be ready ..."
RETRIES=0
MAX_RETRIES=30
READY_LOG=$(mktemp)
until docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker true </dev/null 2>>"$READY_LOG"; do
    RETRIES=$((RETRIES + 1))
    if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
        echo "ERROR: Container did not become ready within 60 seconds." >&2
        if [ -s "$READY_LOG" ]; then
            echo "  Docker reported:" >&2
            tail -5 "$READY_LOG" | sed 's/^/    /' >&2
            echo "" >&2
        fi
        echo "Check Docker Desktop for errors, then retry with:" >&2
        echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml up -d" >&2
        rm -f "$READY_LOG"
        exit 1
    fi
    sleep 2
done
rm -f "$READY_LOG"

# --- Clone the full repository into the Docker volume ---
echo "[4/4] Cloning DAAF repository files into the Docker container ..."

# On reinstall, remove the existing .git directory first.  Git pack files are
# mode 444 (read-only by design) which prevents cp -a from overwriting them.
# The research/ folder is preserved -- only framework files are replaced.
docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    bash -c 'rm -rf /daaf/.git /daaf/.pre-commit-config.yaml /daaf/.gitignore /daaf/.claudeignore 2>/dev/null; true' </dev/null \
    || true

if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    git clone --depth 1 -b "${BRANCH}" "https://github.com/${REPO}.git" /tmp/daaf-clone </dev/null; then
    echo ""
    echo "ERROR: Failed to clone the DAAF repository."
    echo "The Docker image was built successfully, but the repository could not be downloaded."
    echo "Check your internet connection and retry with:"
    echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    git clone --depth 1 -b ${BRANCH} https://github.com/${REPO}.git /tmp/daaf-clone"
    echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    echo "You can also safely re-run this installer to retry from scratch (set DAAF_FORCE_REINSTALL=1 if prompted)."
    exit 1
fi

if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone' </dev/null; then
    echo ""
    echo "ERROR: Failed to copy repository files into the container."
    echo "The clone succeeded, but copying to /daaf/ failed (possibly a permissions issue)."
    echo "You can retry manually with:"
    echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    echo "You can also safely re-run this installer to retry from scratch (set DAAF_FORCE_REINSTALL=1 if prompted)."
    exit 1
fi

# --- Verify DAAF files are present ---
if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    test -f /daaf/CLAUDE.md </dev/null 2>/dev/null; then
    echo ""
    echo "WARNING: Installation may be incomplete -- /daaf/CLAUDE.md was not found in the container."
    echo "The Docker image was built, but the repository files may not have copied correctly."
    echo "You can try cloning manually inside the container:"
    echo "  cd ${INSTALL_DIR}"
    echo "  docker compose exec daaf-docker bash"
    echo "  git clone --depth 1 -b ${BRANCH} https://github.com/${REPO}.git /tmp/daaf-clone"
    echo "  cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone"
    exit 1
fi

echo ""
echo "=========================================="
echo "  Installation complete!"
echo "=========================================="
echo ""
echo "To start using DAAF:"
echo ""
echo "  1. Navigate to the install directory and launch the DAAF Control Panel:"
echo "     cd ${INSTALL_DIR}"
echo "     bash daaf.sh"
echo ""
echo "     The Control Panel provides a status dashboard, service management,"
echo "     and all DAAF operations in one place."
echo ""
echo "  2. On first launch, you'll be asked to authenticate with your Anthropic account."
echo ""
echo "  3. Configure Claude Code (required):"
echo "     - Type /config and set:"
echo "         Auto-compact  -> False"
echo "         Verbose output -> True"
echo "     - Press ESC to return to the chat"
echo ""
echo "Available scripts (in ${INSTALL_DIR}):"
echo "  bash daaf.sh                    DAAF Control Panel (recommended)"
echo "  bash run_daaf.sh               Launch Claude Code directly"
echo "  bash run_daaf.sh bash          Enter the container shell"
echo "  bash backup_daaf.sh            Back up the Docker volume to a dated folder"
echo "  bash restore_from_backup.sh    Restore from a backup"
echo "  bash update_daaf.sh            Check for and apply DAAF updates"
echo "  bash rebuild_daaf.sh           Copy build files from container and rebuild image"
echo "  bash view_logs.sh              Browse session logs in your browser"
echo "  bash view_notebooks.sh         Browse and edit marimo notebooks in your browser"
echo "  bash view_quarto.sh            Render and view Quarto notebooks in your browser"
echo "  bash run_vscode.sh             Open VS Code in your browser (code-server)"
echo ""
echo "To set up data source API keys (optional):"
echo "  cp environment_settings_example.txt environment_settings.txt   Copy the template"
echo "  Edit environment_settings.txt with your keys, then restart with: bash run_daaf.sh"
echo ""
echo "Manual alternative (if you prefer individual commands):"
echo "  docker compose exec daaf-docker bash   # enter the container"
echo "  claude                                  # launch Claude Code"
echo ""
echo "For day-to-day usage and more, see:"
echo "  https://github.com/${REPO}/blob/${BRANCH}/user_reference/01_installation_and_quickstart.md"
echo ""
echo "Keep this directory -- it contains the Dockerfile needed for rebuilds."
echo ""
echo "To get started using any of those scripts, enter the install directory first:"
echo "  cd daaf-docker"
echo ""
