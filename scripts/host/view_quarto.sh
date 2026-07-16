#!/usr/bin/env bash
# ============================================================================
# DAAF Quarto Document Viewer (macOS / Linux)
# ============================================================================
# Recursively discovers Quarto notebooks (.qmd) under research/, lets you select
# one, renders it to a single self-contained HTML file inside the DAAF container,
# copies the result out to your host machine, and opens it in your default
# browser. This is the R-notebook counterpart to view_notebooks.sh (which serves
# marimo for Python projects).
#
# Unlike marimo, Quarto notebooks are not served live -- they render to a static
# HTML file. This script closes that gap so you never have to run
# `quarto render` + `docker cp` by hand.
#
# Usage:
#   cd daaf-docker
#   bash view_quarto.sh                                  # recursively select a .qmd notebook
#   bash view_quarto.sh 2026-01-24_My_Project           # render the notebook in that project
#   bash view_quarto.sh research/2026-01-24_My_Project/notebook.qmd   # render a specific .qmd
#
# Output:
#   Rendered HTML is copied to ./quarto_html/ under your current directory
#   (created on first use). Output uses the notebook's flat basename, so notebooks
#   with the same basename overwrite one another. Set QUARTO_HTML_DIR to a
#   different directory when both outputs must be retained.
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
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ "${DAAF_DRY_RUN:-}" != "1" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate Docker for CI cross-platform smoke testing. The
# recursive find returns a deep fixture. Later branches skip every host write,
# copy, output-directory resolution, and browser launch rather than merely
# replacing those operations with no-ops.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps -q daaf-docker"*) echo "abc123" ;;
            *"compose up"*) return 0 ;;
            *"find research"*|*"find \"research"*) echo "research/2026-07-15_Project/output/analysis/deep.qmd" ;;
            *"quarto render"*) return 0 ;;
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
# Usage: DAAF_TEST_MODE=1 source scripts/host/view_quarto.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# --- Parse arguments ---
# Optional single positional argument: a project folder name (under research/)
# or a direct path to a .qmd file. No argument => recursive discovery picker.
TARGET_ARG=""
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            echo "Usage: bash $0                         # recursively discover and select a .qmd"
            echo "       bash $0 <project-folder>        # render the single .qmd in that project"
            echo "       bash $0 <path/to/notebook.qmd>  # render a specific .qmd file"
            echo ""
            echo "The picker accepts a number; 0, blank, q/Q, or EOF cancels cleanly."
            echo "Rendered HTML is written to ${QUARTO_HTML_DIR}/ and opened in your browser."
            echo "Flat basenames overwrite on collision; set QUARTO_HTML_DIR to retain both."
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
#   1. No argument              -> recursively discover and select under research/.
#   2. A project folder name    -> recursively find its single .qmd.
#   3. A direct .qmd path       -> use it verbatim (normalized to container-relative).
# Discovery is newline-delimited, so literal-newline filenames are unsupported.
# Spaces and ordinary shell metacharacters are preserved as literal path data.
# The final path handed to `quarto render` is relative to /daaf, the container's
# working_dir.
QMD_REL=""

if [ -z "${TARGET_ARG}" ]; then
    echo ""
    echo "Discovering Quarto notebooks under research/ ..."
    echo "Searching recursively at every depth."
    if ! QMDS_RAW=$(docker compose exec -T daaf-docker bash -o pipefail -c 'cd /daaf && find research -type f -name "*.qmd" -print | LC_ALL=C sort' 2>/dev/null); then
        echo "ERROR: Could not discover Quarto notebooks in the DAAF container." >&2
        echo "  Check Docker/container status, then try again." >&2
        exit 1
    fi
    QMDS_RAW="$(printf '%s' "${QMDS_RAW}" | tr -d '\r')"

    qmd_paths=()
    while IFS= read -r qmd_path; do
        [ -z "${qmd_path}" ] && continue
        qmd_paths+=("${qmd_path}")
    done <<< "${QMDS_RAW}"

    qmd_count="${#qmd_paths[@]}"
    if [ "${qmd_count}" -eq 0 ]; then
        echo ""
        echo "No Quarto notebooks (.qmd) found under research/." >&2
        echo "  Quarto notebooks are produced by R projects. If you expected one here," >&2
        echo "  confirm the project finished assembling its notebook." >&2
        exit 1
    fi

    echo ""
    echo "Available Quarto notebooks:"
    echo ""
    qmd_index=0
    while [ "${qmd_index}" -lt "${qmd_count}" ]; do
        printf "  %d) %s\n" "$((qmd_index + 1))" "${qmd_paths[${qmd_index}]}"
        qmd_index=$((qmd_index + 1))
    done
    echo "  0) Cancel"
    echo ""

    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        QMD_REL="${qmd_paths[0]}"
        echo "[DRY-RUN] Auto-selected 1) ${QMD_REL}"
    else
        while true; do
            if ! IFS= read -r -p "Select a notebook (1-${qmd_count}, 0 to cancel): " selection; then
                selection=""
            fi

            case "${selection}" in
                ""|0|q|Q)
                    echo "Quarto notebook selection cancelled."
                    exit 0
                    ;;
                *[!0-9]*|0*)
                    echo "Invalid selection. Enter a number from 1 to ${qmd_count}, or 0 to cancel." >&2
                    continue
                    ;;
            esac

            # Bound digit length before arithmetic conversion/indexing. Nine digits
            # safely covers any practical candidate count on Bash 3.2 hosts.
            if [ "${#selection}" -gt 9 ]; then
                echo "Invalid selection. Enter a number from 1 to ${qmd_count}, or 0 to cancel." >&2
                continue
            fi
            selection_number=$((10#${selection}))
            if [ "${selection_number}" -lt 1 ] || [ "${selection_number}" -gt "${qmd_count}" ]; then
                echo "Invalid selection. Enter a number from 1 to ${qmd_count}, or 0 to cancel." >&2
                continue
            fi

            QMD_REL="${qmd_paths[$((selection_number - 1))]}"
            break
        done
    fi
else
    case "${TARGET_ARG}" in
        *.qmd)
            # Direct .qmd path. Strip a leading ./ and /daaf/ so the value is
            # relative to the container working_dir (/daaf).
            QMD_REL="${TARGET_ARG#./}"
            QMD_REL="${QMD_REL#/daaf/}"
            if ! docker compose exec -T daaf-docker test -f "/daaf/${QMD_REL}" 2>/dev/null; then
                echo "ERROR: Quarto notebook not found in the container: ${QMD_REL}" >&2
                echo "  Run 'bash $0' with no arguments to select an available notebook." >&2
                exit 1
            fi
            ;;
        *)
            # Keep the project value as a positional argument to container bash;
            # never interpolate host-provided text into the command source.
            proj="${TARGET_ARG#research/}"
            proj="${proj%/}"
            if ! FOUND_RAW=$(docker compose exec -T daaf-docker bash -o pipefail -c 'cd /daaf && find "research/$1" -type f -name "*.qmd" -print | LC_ALL=C sort' _ "${proj}" 2>/dev/null); then
                echo "ERROR: Could not search project '${proj}' for Quarto notebooks." >&2
                echo "  Check Docker/container status and the project name, then try again." >&2
                exit 1
            fi
            FOUND_RAW="$(printf '%s' "${FOUND_RAW}" | tr -d '\r')"

            found_paths=()
            while IFS= read -r found_path; do
                [ -z "${found_path}" ] && continue
                found_paths+=("${found_path}")
            done <<< "${FOUND_RAW}"
            found_count="${#found_paths[@]}"

            if [ "${found_count}" -eq 0 ]; then
                echo "ERROR: No Quarto notebook (.qmd) found in project: ${proj}" >&2
                echo "  Run 'bash $0' with no arguments to select an available notebook." >&2
                exit 1
            fi

            if [ "${found_count}" -gt 1 ]; then
                echo "ERROR: Multiple Quarto notebooks found in project '${proj}':" >&2
                found_index=0
                while [ "${found_index}" -lt "${found_count}" ]; do
                    printf '    %s\n' "${found_paths[${found_index}]}" >&2
                    found_index=$((found_index + 1))
                done
                echo "  Re-run with the full .qmd path to pick one." >&2
                exit 1
            fi

            QMD_REL="${found_paths[0]}"
            ;;
    esac
fi

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
# tracks DAAF_PROJECT_NAME just like the ps/exec calls above). Preserve the flat
# basename destination: a later render overwrites an earlier notebook with the
# same basename. Set QUARTO_HTML_DIR differently when both must be retained.
HOST_HTML="${QUARTO_HTML_DIR%/}/${HTML_BASENAME}"

if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    echo ""
    echo "[DRY-RUN] Render simulated for: ${QMD_REL}"
    echo "[DRY-RUN] Rendered document would be copied to: ${HOST_HTML}"
    echo "[DRY-RUN] Skipping output-directory creation, copy, path resolution, and browser launch."
    exit 0
fi

mkdir -p "${QUARTO_HTML_DIR}"

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
# Prefer the shared open_url helper (handles macOS/WSL/Linux). Pass the raw local
# path rather than constructing a file:// URI: literal #, ?, and % characters in
# a valid filename otherwise acquire URI fragment/query/escape semantics. Fall
# back silently if daaf_lib.sh was not sourced -- the path is printed regardless.
ABS_HTML="$(cd "$(dirname "${HOST_HTML}")" && pwd)/$(basename "${HOST_HTML}")"
if command -v open_url >/dev/null 2>&1; then
    open_url "${ABS_HTML}"
    echo "Opening in your default browser..."
else
    echo "Open it in your browser to view:"
    echo "  ${ABS_HTML}"
fi
