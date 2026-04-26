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

# Pause before exit so the user can review output (skip when called from another script)
if [ -z "${DAAF_NESTED:-}" ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: "' EXIT
fi

COMMAND="${1:-claude}"

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
