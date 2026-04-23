#!/usr/bin/env bash
# ============================================================================
# DAAF Log Explorer (macOS / Linux)
# ============================================================================
# Opens the interactive session log viewer in your browser.
# Starts the DAAF container if needed, generates the session manifest,
# and starts an HTTP server.
#
# Usage:
#   cd daaf-docker
#   bash view_logs.sh
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Port 2719 mapped in docker-compose.yml
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output (skip when called from another script)
if [ -z "${DAAF_NESTED:-}" ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: "' EXIT
fi

# --- Preflight ---
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found in the current directory."
    echo "Please run this script from your daaf-docker folder."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in your PATH."
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop is not running. Please start it and try again."
    exit 1
fi

# --- Start container if not running ---
RUNNING=$(docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -c "daaf-docker" || true)

if [ "${RUNNING}" -eq 0 ]; then
    echo "Starting DAAF container..."
    if ! docker compose up -d; then
        echo "ERROR: Failed to start the container."
        exit 1
    fi
    echo "Container started."
else
    echo "DAAF container is running."
fi

echo ""
echo "Opening DAAF Log Explorer..."
echo ""
docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive

# If the server was already running, the command above returns immediately
# after printing the URL. The EXIT trap keeps the terminal open so the user
# can read/copy it.
