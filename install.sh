#!/usr/bin/env bash
# ============================================================================
# DAAF One-Line Installer (macOS / Linux)
# ============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/install.sh | bash
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
# ============================================================================

set -euo pipefail

# --- Configuration ---
REPO="DAAF-Contribution-Community/daaf"
BRANCH="${DAAF_BRANCH:-main}"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
INSTALL_DIR="$(pwd)/daaf-docker"

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

# --- Create minimal build directory ---
echo "[1/4] Creating initial directory for installation files at ${INSTALL_DIR} ..."
mkdir -p "${INSTALL_DIR}"

# --- Download build-context and utility files ---
echo "[2/4] Downloading installation files ..."
if ! curl -fsSL "${RAW_BASE}/Dockerfile"              -o "${INSTALL_DIR}/Dockerfile" ||
   ! curl -fsSL "${RAW_BASE}/docker-compose.yml"       -o "${INSTALL_DIR}/docker-compose.yml" ||
   ! curl -fsSL "${RAW_BASE}/run_daaf.sh"              -o "${INSTALL_DIR}/run_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/backup_daaf.sh"           -o "${INSTALL_DIR}/backup_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/rebuild_daaf.sh"          -o "${INSTALL_DIR}/rebuild_daaf.sh"; then
    echo ""
    echo "ERROR: Failed to download installation files from branch '${BRANCH}'."
    echo "Please verify that the branch name is correct and that you have an internet connection."
    echo "You can check available branches at: https://github.com/${REPO}/branches"
    exit 1
fi
chmod +x "${INSTALL_DIR}/run_daaf.sh" "${INSTALL_DIR}/backup_daaf.sh" "${INSTALL_DIR}/rebuild_daaf.sh"

# --- Build the Docker image ---
echo "[3/4] Building Docker image (this may take a few minutes on first run since there are a lot of Python libraries to install)..."
export COMPOSE_PROJECT_NAME=daaf
if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" up -d --build; then
    echo ""
    echo "ERROR: Docker image build failed. Check the output above for details."
    echo "You can safely re-run this installer to retry."
    exit 1
fi

# --- Wait for container to be ready ---
echo "      Waiting for container to be ready ..."
RETRIES=0
MAX_RETRIES=30
until docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker true </dev/null 2>/dev/null; do
    RETRIES=$((RETRIES + 1))
    if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
        echo "ERROR: Container did not become ready within 60 seconds."
        echo "Check Docker Desktop for errors, then retry with:"
        echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml up -d"
        exit 1
    fi
    sleep 2
done

# --- Clone the full repository into the Docker volume ---
echo "[4/4] Cloning DAAF repository files into the Docker container ..."
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
    echo "You can also safely re-run this installer to retry from scratch."
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
    echo "You can also safely re-run this installer to retry from scratch."
    exit 1
fi

# --- Verify DAAF files are present ---
if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    test -f /daaf/CLAUDE.md </dev/null 2>/dev/null; then
    echo ""
    echo "WARNING: Installation may be incomplete — /daaf/CLAUDE.md was not found in the container."
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
echo "  1. Navigate to the install directory and launch Claude Code:"
echo "     cd ${INSTALL_DIR}"
echo "     bash run_daaf.sh"
echo ""
echo "     This starts the container (if needed) and launches Claude Code directly."
echo ""
echo "  2. On first launch, you'll be asked to authenticate with your Anthropic account."
echo ""
echo "  3. Configure Claude Code (required):"
echo "     - Type /config and set:"
echo "         Auto-compact  -> False"
echo "         Verbose output -> True"
echo "     - Press ESC to return to the chat"
echo ""
echo "Convenience scripts (in ${INSTALL_DIR}):"
echo "  bash run_daaf.sh             Launch Claude Code (starts container if needed)"
echo "  bash run_daaf.sh bash        Enter the container shell (e.g., for API keys)"
echo "  bash backup_daaf.sh          Back up the Docker volume to a dated folder"
echo "  bash rebuild_daaf.sh         Copy build files from container and rebuild image"
echo ""
echo "Manual alternative (if you prefer individual commands):"
echo "  docker compose exec daaf-docker bash   # enter the container"
echo "  claude                                  # launch Claude Code"
echo ""
echo "For day-to-day usage and more, see:"
echo "  https://github.com/${REPO}/blob/${BRANCH}/user_reference/01_installation_and_quickstart.md"
echo ""
echo "Keep this directory — it contains the Dockerfile needed for rebuilds."
echo ""
