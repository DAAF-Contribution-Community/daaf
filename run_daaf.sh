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
# ============================================================================

set -euo pipefail

COMMAND="${1:-claude}"

# --- Preflight ---
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found in the current directory."
    echo "Please run this script from your daaf-docker folder."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in your PATH."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start it and try again."
    exit 1
fi

# --- Start container if not running ---
RUNNING=$(docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -c "daaf-docker" || true)

if [ "${RUNNING}" -eq 0 ]; then
    echo "Starting DAAF container..."
    if ! docker compose up -d; then
        echo "ERROR: Failed to start the container. Check Docker Desktop for errors."
        exit 1
    fi
    echo "Container started."
else
    echo "DAAF container is already running."
fi

echo ""

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
