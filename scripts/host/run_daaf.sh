#!/usr/bin/env bash
# ============================================================================
# DAAF Launcher (macOS / Linux)
# ============================================================================
# Starts the DAAF container (if needed) and launches Claude Code.
#
# Usage:
#   cd daaf-docker
#   bash run_daaf.sh          # Start container + launch Claude Code
#   bash run_daaf.sh bash     # Start container + drop into bash shell
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script).
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

COMMAND="${1:-claude}"

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's seven whitelisted DAAF_* keys (the case
# pattern below) into the environment so `docker compose` interpolation resolves
# the project name and published host ports. This inline block is the canonical shared pattern (kept
# in sync with load_daaf_settings in daaf_lib.sh); standalone scripts that do NOT
# source daaf_lib.sh inline it so a second install's settings take effect.
# Parse only these whitelisted keys (never `source` -- the file holds API keys with
# arbitrary characters). Shell env wins over the file value; absent file = no-op;
# CR is stripped for CRLF tolerance. Bash 3.2 safe.
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
_daaf_load_settings

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps --status running"*"--format"*) echo "daaf-docker" ;;
            *"compose ps -q"*) echo "abc123" ;;
            *"inspect --format"*) echo "2026-01-01T00:00:00Z" ;;
            *"compose exec"*"test -f"*) return 0 ;;
            *"compose exec"*)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
            *)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
fi

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/run_daaf.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# --- Preflight ---
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found in the current directory."
    echo "Please run this script from your daaf-docker folder."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal."
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start it and try again."
    exit 1
fi

# --- Project name for printed commands ---
# A command printed for the user runs in the user's shell, where the project
# from environment_settings.txt is not set, so a bare `docker compose` there
# reaches the default install. For any other project the printed commands carry
# `-p <project>` and DAAF_PROJECT_NAME=<project>, normalized as Docker Compose
# does (resolve_project_name in daaf_lib.sh; this script runs without it).
# SYNC NOTE: the two HINT_PROJECT lines are a copy of the library's normalization;
# tests/bash/daaf_lib.bats runs them over the library's fixed input set.
HINT_PROJECT="$(printf '%s' "${DAAF_PROJECT_NAME:-daaf}" | LC_ALL=C tr 'A-Z' 'a-z' | LC_ALL=C tr -cd 'a-z0-9_-')"
HINT_PROJECT="${HINT_PROJECT#"${HINT_PROJECT%%[!_-]*}"}"
COMPOSE_P_FLAG=""
RERUN_PROJECT_PREFIX=""
if [ -n "${HINT_PROJECT}" ] && [ "${HINT_PROJECT}" != "daaf" ]; then
    COMPOSE_P_FLAG="-p ${HINT_PROJECT} "
    RERUN_PROJECT_PREFIX="DAAF_PROJECT_NAME=${HINT_PROJECT} "
fi
# The printed reinstall also carries the branch this install follows (DAAF_BRANCH,
# when set and not main) and DAAF_DEV=1 (when set): the installer does not read
# DAAF_BRANCH from environment_settings.txt, so without it a reinstall would
# switch this install to main.
RERUN_BUILD_PREFIX=""
if [ -n "${DAAF_BRANCH:-}" ] && [ "${DAAF_BRANCH}" != "main" ]; then
    RERUN_BUILD_PREFIX="DAAF_BRANCH=${DAAF_BRANCH} "
fi
if [ "${DAAF_DEV:-}" = "1" ]; then
    RERUN_BUILD_PREFIX="${RERUN_BUILD_PREFIX}DAAF_DEV=1 "
fi

# --- Start container if not running ---
# `docker compose ps -q daaf-docker` prints the running container's ID (empty
# when stopped), derived from the compose project rather than a hardcoded name.
RUNNING_CID=$(docker compose ps -q daaf-docker 2>/dev/null || true)

if [ -z "${RUNNING_CID}" ]; then
    echo "Starting DAAF container..."
    if ! docker compose up -d; then
        echo "ERROR: Failed to start the container. Check Docker Desktop for errors."
        exit 1
    fi
    echo "Container started."
else
    echo "DAAF container is already running."
    # Check if environment_settings.txt has been modified since the container was created
    if [ -f "environment_settings.txt" ]; then
        _cid=$(docker compose ps -q daaf-docker 2>/dev/null || true)
        if [ -n "${_cid}" ]; then
            _created=$(docker inspect --format '{{.Created}}' "${_cid}" 2>/dev/null || true)
            # Get environment_settings.txt mtime as epoch (Linux: -c %Y, macOS: -f %m)
            _env_epoch=$(stat -c %Y environment_settings.txt 2>/dev/null || stat -f %m environment_settings.txt 2>/dev/null || echo "")
            # Convert container creation ISO timestamp to epoch (Linux: date -d, macOS: date -j -f)
            # Strip fractional seconds and trailing Z for macOS BSD date compatibility
            _ts_clean=$(echo "${_created}" | sed 's/\.[0-9]*Z$//' | sed 's/Z$//')
            _ctr_epoch=$(date -d "${_created}" +%s 2>/dev/null || \
                date -j -f "%Y-%m-%dT%H:%M:%S" "${_ts_clean}" +%s 2>/dev/null || \
                echo "")
            if [ -n "${_ctr_epoch}" ] && [ -n "${_env_epoch}" ] && [ "${_env_epoch}" -gt "${_ctr_epoch}" ]; then
                echo ""
                echo "NOTE: Your environment_settings.txt file has been modified since this container was started."
                echo "      To apply environment_settings.txt changes, close all DAAF sessions, then choose"
                echo "      11) Restart Container in the DAAF Control Panel (bash daaf.sh), which does this for you."
                echo "      Or run these commands yourself:"
                echo "        docker compose ${COMPOSE_P_FLAG}down"
                echo "        bash run_daaf.sh"
            fi
        fi
    fi
fi

echo ""

# --- Verify DAAF is installed in the container ---
if ! docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md </dev/null 2>/dev/null; then
    echo "WARNING: DAAF does not appear to be installed in the container (/daaf/CLAUDE.md is missing),"
    echo "so Claude Code cannot start with DAAF. The updater cannot repair this; reinstalling can."
    echo "A reinstall replaces DAAF's framework files and local git history, and keeps your"
    echo "research files and environment_settings.txt (a backup first is still a good idea:"
    echo "Control Panel option 7) Create Backup). To reinstall, run:"
    echo "  cd \"$(dirname "${PWD}")\""
    echo "  ${RERUN_PROJECT_PREFIX}${RERUN_BUILD_PREFIX}DAAF_FORCE_REINSTALL=1 bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh)\""
    exit 1
fi

# --- Launch ---
if [ "${COMMAND}" = "claude" ]; then
    echo "Launching Claude Code..."
    echo "(Type /exit to leave Claude Code when you are done.)"
    echo ""
    docker compose exec daaf-docker claude
elif [ "${COMMAND}" = "bash" ]; then
    echo "Entering container shell..."
    echo "(Type 'exit' to leave the container)"
    echo ""
    docker compose exec daaf-docker bash
else
    echo "Running: ${COMMAND}"
    docker compose exec daaf-docker "${COMMAND}"
fi
