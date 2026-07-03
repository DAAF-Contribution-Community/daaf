#!/usr/bin/env bash
# ============================================================================
# DAAF Rebuild Utility (macOS / Linux)
# ============================================================================
# Copies the current Dockerfile and docker-compose.yml from the container
# back to the host build directory, then rebuilds the Docker image.
#
# Use this after:
#   - Adding Python packages via DAAF's Framework Development mode
#   - Running update_daaf.sh when it reports Dockerfile or docker-compose.yml changes
#   - Any other change to build files inside the container
#
# Why this is needed:
#   The Dockerfile and docker-compose.yml live in two places -- inside the Docker
#   volume (where DAAF and update_daaf.sh modify them) and on the host (where docker
#   compose reads them for builds). This script bridges the gap so you don't
#   have to remember the manual docker cp commands.
#
# Usage:
#   cd daaf-docker
#   bash rebuild_daaf.sh
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script like update_daaf.sh).
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so `docker compose` interpolation resolves the project name and
# published host ports. Canonical shared pattern (kept in sync with
# load_daaf_settings in daaf_lib.sh). Parse only these four keys (never `source`
# -- the file holds API keys); shell env wins; absent file = no-op; CR stripped;
# Bash 3.2 safe.
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
            *"compose ps -aq daaf-docker"*) echo "abc123" ;;
            "inspect"*) return 0 ;;
            "cp"*) return 0 ;;
            *"compose build"*) return 0 ;;
            *"compose up"*) return 0 ;;
            *"compose exec"*"true"*) return 0 ;;
            *"compose exec"*"test -f"*) return 0 ;;
            *)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
fi

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/rebuild_daaf.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

echo ""
echo "=========================================="
echo "  DAAF Rebuild"
echo "=========================================="
echo ""

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

# --- Check container exists (running or stopped) ---
# Derive the container ID from the compose project rather than a hardcoded name.
# `-aq` includes STOPPED containers: rebuild must be able to copy build files out
# of a container that is not currently running (this is the documented use case),
# so the running-only `-q` form would be wrong here.
CONTAINER_ID=$(docker compose ps -aq daaf-docker 2>/dev/null || true)
if [ -z "${CONTAINER_ID}" ]; then
    echo "ERROR: No daaf-docker container found (running or stopped)."
    echo "Have you run the DAAF installer? The container must exist (running or stopped)"
    echo "for this script to copy the updated files from it."
    exit 1
fi

# --- Copy build files from container to host ---
echo "[1/3] Copying build files from container to host..."

# Back up current host files so we can show what changed
DOCKERFILE_CHANGED="no"
COMPOSEFILE_CHANGED="no"

if [ -f "Dockerfile" ]; then
    cp Dockerfile Dockerfile.pre-rebuild
fi
if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml docker-compose.yml.pre-rebuild
fi

if ! docker cp "${CONTAINER_ID}:/daaf/Dockerfile" ./Dockerfile; then
    echo "ERROR: Failed to copy Dockerfile from container."
    echo "Make sure DAAF is installed in the container (run the installer if needed)."
    exit 1
fi
echo "      Copied Dockerfile"

if ! docker cp "${CONTAINER_ID}:/daaf/docker-compose.yml" ./docker-compose.yml; then
    echo "ERROR: Failed to copy docker-compose.yml from container."
    exit 1
fi
echo "      Copied docker-compose.yml"

# --- Show what changed ---
echo ""
if [ -f "Dockerfile.pre-rebuild" ]; then
    if diff -q Dockerfile.pre-rebuild Dockerfile &> /dev/null; then
        echo "      Dockerfile: no changes detected"
    else
        DOCKERFILE_CHANGED="yes"
        echo "      Dockerfile: UPDATED"
    fi
else
    DOCKERFILE_CHANGED="yes"
    echo "      Dockerfile: new (no previous version on host)"
fi

if [ -f "docker-compose.yml.pre-rebuild" ]; then
    if diff -q docker-compose.yml.pre-rebuild docker-compose.yml &> /dev/null; then
        echo "      docker-compose.yml: no changes detected"
    else
        COMPOSEFILE_CHANGED="yes"
        echo "      docker-compose.yml: UPDATED"
    fi
else
    COMPOSEFILE_CHANGED="yes"
    echo "      docker-compose.yml: new (no previous version on host)"
fi

if [ "${DOCKERFILE_CHANGED}" = "no" ] && [ "${COMPOSEFILE_CHANGED}" = "no" ]; then
    echo ""
    echo "      No changes detected -- the host files already match the container."
    echo "      Rebuilding anyway to make sure the image is up to date."
fi

# --- Rebuild ---
echo ""
echo "[2/3] Rebuilding Docker image (this may take a few minutes if packages changed)..."
echo ""
# Build and start are split into two commands so that --progress plain can be
# applied to the build step (where it is universally supported) without relying
# on `docker compose up --progress`, which is rejected as "unknown flag" on
# Docker Compose versions prior to ~v2.27.
if ! docker compose build --progress plain; then
    echo ""
    echo "ERROR: Rebuild failed. Check the output above for details."
    if [ -f "Dockerfile.pre-rebuild" ]; then
        echo "Your previous Dockerfile was saved as Dockerfile.pre-rebuild"
    fi
    exit 1
fi
echo ""
echo "Starting container..."
if ! docker compose up -d; then
    echo ""
    echo "ERROR: Failed to start the container after rebuild. Check the output above for details."
    exit 1
fi

# --- Wait for container to be ready ---
echo ""
echo "      Waiting for container to be ready..."
RETRIES=0
MAX_RETRIES=30
READY_LOG=$(mktemp)
until docker compose exec -T daaf-docker true </dev/null 2>>"$READY_LOG"; do
    RETRIES=$((RETRIES + 1))
    if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
        echo "ERROR: Container did not become ready within 60 seconds." >&2
        if [ -s "$READY_LOG" ]; then
            echo "  Docker reported:" >&2
            tail -5 "$READY_LOG" | sed 's/^/    /' >&2
            echo "" >&2
        fi
        echo "Check Docker Desktop for errors." >&2
        rm -f "$READY_LOG"
        exit 1
    fi
    sleep 2
done
rm -f "$READY_LOG"

# --- Verify ---
echo ""
echo "[3/3] Verifying DAAF installation..."
if ! docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md </dev/null 2>/dev/null; then
    echo ""
    echo "WARNING: Rebuild completed but DAAF files may not be intact."
    echo "Try entering the container with: bash run_daaf.sh bash"
    exit 1
fi

echo "      DAAF verified."

# Clean up pre-rebuild backups on success
rm -f Dockerfile.pre-rebuild docker-compose.yml.pre-rebuild

echo ""
echo "=========================================="
echo "  Rebuild complete!"
echo "=========================================="
echo ""
echo "The Docker image has been rebuilt with the latest Dockerfile."
echo "To launch DAAF:  bash run_daaf.sh"
echo ""
