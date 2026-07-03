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
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so `docker compose` interpolation resolves the project name and
# published host ports. This inline block is the canonical shared pattern (kept
# in sync with load_daaf_settings in daaf_lib.sh); standalone scripts that do NOT
# source daaf_lib.sh inline it so a second install's settings take effect.
# Parse only these four keys (never `source` -- the file holds API keys with
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
            DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*)
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
                echo "      To apply environment_settings.txt changes, close all DAAF sessions, then run:"
                echo "        docker compose down"
                echo "        bash run_daaf.sh"
            fi
        fi
    fi
fi

echo ""

# --- Verify DAAF is installed in the container ---
if ! docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md </dev/null 2>/dev/null; then
    echo "WARNING: DAAF does not appear to be installed in the container (/daaf is empty or missing key files)."
    echo "The container is running, but DAAF's repository files may not have been cloned."
    echo "You can fix this by running 'bash update_daaf.sh' from your daaf-docker folder, or manually cloning inside the container:"
    echo "  docker compose exec daaf-docker bash"
    echo "  git clone --depth 1 https://github.com/DAAF-Contribution-Community/daaf.git /tmp/daaf-clone"
    echo "  cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone"
    exit 1
fi

# --- Launch ---
if [ "${COMMAND}" = "claude" ]; then
    echo "Launching Claude Code..."
    echo "(Press Ctrl+C twice to exit Claude Code when done)"
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
