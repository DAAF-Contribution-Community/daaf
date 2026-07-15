#!/usr/bin/env bash
# ============================================================================
# DAAF Quarto Document Viewer (macOS / Linux)
# ============================================================================
# Renders a Quarto notebook (.qmd) to a single self-contained HTML file inside
# the DAAF container, copies the result out to your host machine, and opens it
# in your default browser. This is the R-notebook counterpart to
# view_notebooks.sh (which serves marimo for Python projects).
#
# Unlike marimo, Quarto notebooks are not served live -- they render to a static
# HTML file. This script closes that gap so you never have to run
# `quarto render` + `docker cp` by hand.
#
# Usage:
#   cd daaf-docker
#   bash view_quarto.sh                                  # list available .qmd notebooks
#   bash view_quarto.sh 2026-01-24_My_Project           # render the notebook in that project
#   bash view_quarto.sh research/2026-01-24_My_Project/notebook.qmd   # render a specific .qmd
#
# Output:
#   Rendered HTML is copied to ./quarto_html/ under your current directory
#   (created on first use). Each render overwrites the file of the same name.
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - An R project with a Quarto notebook (.qmd) under research/
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# --- Source shared library (optional -- backwards compatible without it) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/daaf_lib.sh" ]; then
    # shellcheck source=/dev/null
    source "${SCRIPT_DIR}/daaf_lib.sh"
fi

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so `docker compose` interpolation resolves the project name and
# published host ports. Canonical shared pattern (kept in sync with
# load_daaf_settings in daaf_lib.sh). Parse only these whitelisted keys (never `source`
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
                DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*|DAAF_DEV=*|DAAF_BRANCH=*)
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

# Host directory the rendered HTML is copied into (created on first use).
# Kept relative to the invoking directory so the user finds output right where
# they launched the script (their daaf-docker folder, next to docker-compose.yml).
QUARTO_HTML_DIR="${QUARTO_HTML_DIR:-./quarto_html}"

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from another
# script) and in non-interactive contexts (CI, no controlling terminal).
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI cross-platform
# smoke testing without a Docker daemon. The `compose exec` arm echoes a fake
# .qmd path so the discovery listing has something to show; `cp` is a no-op.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps -q daaf-docker"*) echo "abc123" ;;
            *"compose up"*) return 0 ;;
            *"find research"*|*"find \"research"*) echo "research/2026-01-24_Sample_R_Project/2026-01-24_Sample_R_Project.qmd" ;;
            *"quarto render"*) return 0 ;;
            *"compose exec"*) return 0 ;;
            *"compose cp"*) return 0 ;;
            *)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
fi

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/view_quarto.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# --- Parse arguments ---
# Optional single positional argument: a project folder name (under research/)
# or a direct path to a .qmd file. No argument => discovery-listing mode.
TARGET_ARG=""
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            echo "Usage: bash $0                         # list available .qmd notebooks"
            echo "       bash $0 <project-folder>        # render the .qmd in that research project"
            echo "       bash $0 <path/to/notebook.qmd>  # render a specific .qmd file"
            echo ""
            echo "Rendered HTML is written to ${QUARTO_HTML_DIR}/ and opened in your browser."
            exit 0
            ;;
        -*)
            echo "ERROR: Unknown option: $1" >&2
            echo "  Try: bash $0 --help" >&2
            exit 1
            ;;
        *)
            if [ -n "${TARGET_ARG}" ]; then
                echo "ERROR: Too many arguments. Provide at most one project folder or .qmd path." >&2
                echo "  Try: bash $0 --help" >&2
                exit 1
            fi
            TARGET_ARG="$1"
            shift
            ;;
    esac
done

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
        echo "  Try: docker compose logs daaf-docker" >&2
        exit 1
    fi
    echo "Container started."
else
    echo "DAAF container is running."
fi

# --- Resolve the .qmd to render ---
# Three input shapes are accepted:
#   1. No argument              -> list all .qmd files under research/ and exit.
#   2. A project folder name    -> find the .qmd inside research/<name>/.
#   3. A direct .qmd path       -> use it verbatim (normalized to container-relative).
# The .qmd path we ultimately hand to `quarto render` is expressed relative to
# /daaf inside the container, because the container's working_dir is /daaf.
QMD_REL=""

if [ -z "${TARGET_ARG}" ]; then
    # --- Discovery mode: list available notebooks ---
    echo ""
    echo "Discovering Quarto notebooks under research/ ..."
    # `find` runs inside the container (its GNU userland is guaranteed); results
    # are paths relative to /daaf. -maxdepth keeps this to project-level notebooks.
    QMDS_RAW=$(docker compose exec -T daaf-docker bash -c 'cd /daaf && find research -maxdepth 3 -name "*.qmd" -type f 2>/dev/null | sort' 2>/dev/null | tr -d '\r') || QMDS_RAW=""

    if [ -z "${QMDS_RAW}" ]; then
        echo ""
        echo "No Quarto notebooks (.qmd) found under research/." >&2
        echo "  Quarto notebooks are produced by R projects. If you expected one here," >&2
        echo "  confirm the project finished assembling its notebook." >&2
        exit 1
    fi

    echo ""
    echo "Available Quarto notebooks:"
    echo ""
    # Bash 3.2 safe: iterate the newline-delimited list with a while-read loop
    # (no mapfile). This mode lists and exits.
    while IFS= read -r qmd_path; do
        [ -z "${qmd_path}" ] && continue
        printf "  %s\n" "${qmd_path}"
    done <<< "${QMDS_RAW}"
    echo ""
    echo "To render one, re-run with its project folder or path, e.g.:"
    echo "  bash $0 <project-folder>"
    echo "  bash $0 <path/to/notebook.qmd>"
    exit 0
fi

case "${TARGET_ARG}" in
    *.qmd)
        # Direct .qmd path. Strip a leading ./ and a leading /daaf/ so the value
        # is expressed relative to the container working_dir (/daaf).
        QMD_REL="${TARGET_ARG#./}"
        QMD_REL="${QMD_REL#/daaf/}"
        # Confirm it exists inside the container before attempting a render.
        if ! docker compose exec -T daaf-docker test -f "/daaf/${QMD_REL}" 2>/dev/null; then
            echo "ERROR: Quarto notebook not found in the container: ${QMD_REL}" >&2
            echo "  Run 'bash $0' with no arguments to list available notebooks." >&2
            exit 1
        fi
        ;;
    *)
        # Treat the argument as a project folder name (with or without a leading
        # research/). Find the single .qmd inside it.
        proj="${TARGET_ARG#research/}"
        proj="${proj%/}"
        FOUND=$(docker compose exec -T daaf-docker bash -c 'cd /daaf && find "research/$1" -maxdepth 2 -name "*.qmd" -type f 2>/dev/null | sort' _ "${proj}" 2>/dev/null | tr -d '\r') || FOUND=""

        if [ -z "${FOUND}" ]; then
            echo "ERROR: No Quarto notebook (.qmd) found in project: ${proj}" >&2
            echo "  Run 'bash $0' with no arguments to list available notebooks." >&2
            exit 1
        fi

        # If multiple .qmd files exist in the project, ask the user to be specific
        # rather than guessing which one they meant.
        qmd_count=$(printf '%s\n' "${FOUND}" | grep -c . || true)
        if [ "${qmd_count}" -gt 1 ]; then
            echo "ERROR: Multiple Quarto notebooks found in project '${proj}':" >&2
            printf '%s\n' "${FOUND}" | sed 's/^/    /' >&2
            echo "  Re-run with the full .qmd path to pick one." >&2
            exit 1
        fi

        QMD_REL="${FOUND}"
        ;;
esac

# --- Render inside the container ---
# `-M embed-resources:true` forces a SINGLE self-contained HTML regardless of
# whether the source .qmd's YAML sets it, so the copied-out file is fully
# portable (all CSS/JS/images inlined -- no sidecar _files/ directory to copy).
# Verified against Quarto 1.7.29: `-M embed-resources:true` produces one .html
# with no _files/ dir even when the .qmd YAML omits the setting.
HTML_REL="${QMD_REL%.qmd}.html"
HTML_BASENAME="$(basename "${HTML_REL}")"

echo ""
echo "Rendering ${QMD_REL} to a self-contained HTML file..."
echo ""
if ! docker compose exec -T daaf-docker quarto render "/daaf/${QMD_REL}" --to html -M embed-resources:true; then
    echo "" >&2
    echo "ERROR: quarto render failed for ${QMD_REL}." >&2
    echo "  The Quarto error output above shows what went wrong (a code chunk error," >&2
    echo "  a missing package, or malformed YAML frontmatter are the usual causes)." >&2
    exit 1
fi

# --- Copy the rendered HTML out to the host ---
# `docker compose cp` copies from the container to the host without needing a
# raw container name (it resolves the service from the compose project, so it
# tracks DAAF_PROJECT_NAME just like the ps/exec calls above).
mkdir -p "${QUARTO_HTML_DIR}"
HOST_HTML="${QUARTO_HTML_DIR%/}/${HTML_BASENAME}"

if ! docker compose cp "daaf-docker:/daaf/${HTML_REL}" "${HOST_HTML}"; then
    echo "" >&2
    echo "ERROR: Failed to copy the rendered HTML out of the container." >&2
    echo "  The render succeeded, so the file exists at /daaf/${HTML_REL} inside" >&2
    echo "  the container. You can copy it manually with:" >&2
    echo "    docker compose cp daaf-docker:/daaf/${HTML_REL} ${HOST_HTML}" >&2
    exit 1
fi

echo ""
echo "Rendered document copied to: ${HOST_HTML}"

# --- Open in the default browser ---
# Prefer the shared open_url helper (handles macOS/WSL/Linux). It expects a URL;
# a file:// URL with an absolute path opens a local file in every supported
# opener. Fall back silently if daaf_lib.sh was not sourced -- the file path is
# printed above regardless, so the user can always open it by hand.
ABS_HTML="$(cd "$(dirname "${HOST_HTML}")" && pwd)/$(basename "${HOST_HTML}")"
if command -v open_url >/dev/null 2>&1; then
    open_url "file://${ABS_HTML}"
    echo "Opening in your default browser..."
else
    echo "Open it in your browser to view:"
    echo "  file://${ABS_HTML}"
fi
