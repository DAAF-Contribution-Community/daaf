#!/usr/bin/env bash
# ============================================================================
# DAAF Notebook Browser (macOS / Linux)
# ============================================================================
# Opens marimo's notebook browser in your browser -- browse, open, create, and
# edit marimo notebooks across all your research projects.
# Starts the DAAF container if needed. Automatically opens the browser when
# daaf_lib.sh is available.
#
# Usage:
#   cd daaf-docker
#   bash view_notebooks.sh
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Port 2718 mapped in docker-compose.yml
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
            *"compose ps --status running"*"--format"*) echo "daaf-docker" ;;
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
# Usage: DAAF_TEST_MODE=1 source scripts/host/view_notebooks.sh
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
RUNNING=$(docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -c "daaf-docker" || true)

if [ "${RUNNING}" -eq 0 ]; then
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
echo "Opening DAAF Notebook Browser..."
echo ""
if ! docker compose exec daaf-docker bash /daaf/scripts/launch_marimo.sh; then
    echo "" >&2
    echo "ERROR: Failed to start the notebook browser." >&2
    echo "  The container may not be running, or marimo may not be installed." >&2
    echo "  Try: docker compose logs daaf-docker" >&2
fi

# Open browser automatically if library is available
if command -v open_url >/dev/null 2>&1; then
    open_url "http://localhost:2718"
fi

# If marimo was already running, the container-side script returns immediately
# after printing the URL. The EXIT trap keeps the terminal open so the user
# can read/copy it.
