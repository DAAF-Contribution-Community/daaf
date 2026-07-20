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

# --- Multi-instance / build-flag settings (shared pattern) ---
# Bridge environment_settings.txt's whitelisted DAAF_* keys into the
# environment so `docker compose` interpolation resolves the project name and
# published host ports, and so the DAAF_DEV build flag reaches
# `docker compose build` as `--build-arg DAAF_DEV=${DAAF_DEV:-0}`. The build
# flag matters specifically for THIS script because it runs the build (below); a
# developer who set DAAF_DEV=1 expects the rebuild to pick up the dev toolchain.
# Canonical shared pattern (kept in sync with load_daaf_settings in
# daaf_lib.sh). Parse only these whitelisted keys (never `source` -- the file holds API
# keys); shell env wins; absent file = no-op; CR stripped; Bash 3.2 safe.
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
            *"compose ps -aq daaf-docker"*) echo "abc123" ;;
            *"buildx inspect"*) return 1 ;;
            *"buildx create"*) return 0 ;;
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

# --- Apple Silicon (arm64) build-time notice ---
# On the Ubuntu noble base, arm64 gets P3M pre-built R binaries (same as x86_64),
# so Apple Silicon no longer compiles R packages from source. A rebuild that
# touches an early layer still re-runs the sizable package installs, but there is
# no arm64-specific source-compile penalty. A brief heads-up keeps the quiet
# install phase from looking like a hang.
DAAF_ARCH="$(uname -m 2>/dev/null || echo unknown)"
if [ "${DAAF_ARCH}" = "arm64" ] || [ "${DAAF_ARCH}" = "aarch64" ]; then
    echo ""
    echo "NOTE: arm64 detected (Apple Silicon or other ARM64 host). If this rebuild"
    echo "      re-runs the package layers it takes a while with some quiet stretches"
    echo "      -- this is normal, not a hang. arm64 now installs pre-built R binaries"
    echo "      (no source compilation)."
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

# --- Rebuild ---
echo ""
echo "[2/3] Rebuilding Docker image (this may take a few minutes if packages changed)..."
echo ""
# Build and start are split into two commands so that --progress plain can be
# applied to the build step (where it is universally supported) without relying
# on `docker compose up --progress`, which is rejected as "unknown flag" on
# Docker Compose versions prior to ~v2.27.
#
# The BUILDX_BUILDER prefix is applied ONLY on the diagnostic path. On the normal
# path the command must NOT reference BUILDX_BUILDER at all: setting it to the
# empty string still EXPORTS it (set-but-empty, not unset), which relies on
# undocumented docker empty==default semantics and would clobber a user's own
# pre-exported BUILDX_BUILDER. Two explicit branches avoid that. `set -e` is
# active, so capture the exit code with `|| BUILD_EXIT=$?` to reach the error
# message below on failure.
BUILD_EXIT=0
if [ "${DIAG_BUILDER_SELECTED}" = "1" ]; then
    BUILDX_BUILDER="daaf-diag-builder" docker compose build --progress plain || BUILD_EXIT=$?
else
    docker compose build --progress plain || BUILD_EXIT=$?
fi
if [ "${BUILD_EXIT}" -ne 0 ]; then
    echo ""
    echo "ERROR: Rebuild failed. Check the output above for details."
    if [ -f "Dockerfile.pre-rebuild" ]; then
        echo "Your previous Dockerfile was saved as Dockerfile.pre-rebuild"
    fi
    echo "If the output above contains a line like '[output clipped, log limit 2MiB reached]'"
    echo "(the exact limit varies by Docker version), re-run with DAAF_DIAG_BUILD=1 for"
    echo "unclipped build logs:"
    echo "  DAAF_DIAG_BUILD=1 bash rebuild_daaf.sh"
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
