#!/usr/bin/env bash
# ============================================================================
# DAAF Code Browser (macOS / Linux)
# ============================================================================
# Opens code-server (VS Code in the browser) for browsing, editing, and
# reviewing files in the DAAF container.
# Starts the DAAF container if needed. Automatically opens the browser when
# daaf_lib.sh is available.
#
# Usage:
#   cd daaf-docker
#   bash run_vscode.sh
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Port 2720 mapped in docker-compose.yml
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# --- Source shared library (optional — backwards compatible without it) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/daaf_lib.sh" ]; then
    source "${SCRIPT_DIR}/daaf_lib.sh"
fi

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so `docker compose` interpolation resolves the project name and
# published host ports. Canonical shared pattern (kept in sync with
# load_daaf_settings in daaf_lib.sh). Parse only these four keys (never `source`
# -- the file holds API keys); shell env wins; absent file = no-op; CR stripped;
# Bash 3.2 safe. Prefer the library function when daaf_lib.sh was sourced.
if command -v load_daaf_settings >/dev/null 2>&1; then
    load_daaf_settings
else
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
fi

# Host-facing port for the browser URL (defaults to the fixed container port).
DAAF_PORT_VSCODE="${DAAF_PORT_VSCODE:-2720}"

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script).
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps -q daaf-docker"*) echo "abc123" ;;
            *"compose exec"*) return 0 ;;
            *)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
fi

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/run_vscode.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# --- Preflight ---
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found in the current directory." >&2
    echo "  Please run this script from your daaf-docker folder." >&2
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal." >&2
    echo "  Please install Docker Desktop: https://www.docker.com/products/docker-desktop/" >&2
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop is not running. Please start it and try again." >&2
    exit 1
fi

# --- Start container if not running ---
# `docker compose ps -q daaf-docker` prints the running container's ID (empty
# when stopped), derived from the compose project rather than a hardcoded name.
RUNNING_CID=$(docker compose ps -q daaf-docker 2>/dev/null || true)

if [ -z "${RUNNING_CID}" ]; then
    echo "Starting DAAF container..."
    if ! docker compose up -d; then
        echo "ERROR: Failed to start the container." >&2
        exit 1
    fi
    echo "Container started."
else
    echo "DAAF container is running."
fi

echo ""
echo "Opening DAAF Code Browser (VS Code in the browser)..."
echo ""
if ! docker compose exec daaf-docker bash /daaf/scripts/launch_code_server.sh; then
    echo "" >&2
    echo "ERROR: Failed to start code-server." >&2
    echo "  The container may not be running, or code-server may not be installed." >&2
    echo "  Try: docker compose logs daaf-docker" >&2
fi

# Open browser automatically if library is available. URL uses the HOST-published
# port (DAAF_PORT_VSCODE); the container port stays fixed at 2720.
if command -v open_url >/dev/null 2>&1; then
    open_url "http://localhost:${DAAF_PORT_VSCODE}"
fi

# If code-server was already running, the container-side script returns
# immediately after printing the URL. The EXIT trap keeps the terminal open
# so the user can read/copy it.
