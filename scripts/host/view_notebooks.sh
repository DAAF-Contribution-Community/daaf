#!/usr/bin/env bash
# ============================================================================
# DAAF Notebook Browser (macOS / Linux)
# ============================================================================
# Opens marimo's notebook browser in your browser -- browse, open, create, and
# edit marimo notebooks across all your research projects.
# Starts the DAAF container if needed. The notebook server requires an access
# token that changes with every launch; the printed link carries it. A fresh
# launch keeps the server in this window until Ctrl+C and only prints the link;
# the browser opens automatically (when daaf_lib.sh is available) only when a
# notebook server was already running.
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

# --- Source shared library (optional -- backwards compatible without it) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/daaf_lib.sh" ]; then
    source "${SCRIPT_DIR}/daaf_lib.sh"
fi

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's seven whitelisted DAAF_* keys into the
# environment so `docker compose` interpolation resolves the project name and
# published host ports. Canonical shared pattern (kept in sync with
# load_daaf_settings in daaf_lib.sh). Parse only these whitelisted keys (never `source`
# -- the file holds API keys); shell env wins; absent file = no-op; CR stripped;
# Bash 3.2 safe. Prefer the library function when daaf_lib.sh was sourced.
if command -v load_daaf_settings >/dev/null 2>&1; then
    # An existing but unreadable file makes the loader return non-zero without
    # printing anything (its open check silences only bash's raw "Permission
    # denied" line), so say what to fix instead of exiting silently -- the same
    # message daaf.sh gives at startup. The call keeps its stderr: any other
    # loader error (a bug) must stay visible.
    if ! load_daaf_settings; then
        echo "ERROR: Cannot read environment_settings.txt -- make sure it is not open in another program and that you have permission to read it." >&2
        echo "Fix that (or move the file aside), then run view_notebooks.sh again." >&2
        exit 1
    fi
else
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
fi

# --- Project flag for printed commands ---
# A `docker compose` command printed for the user runs in the user's own shell,
# where DAAF_PROJECT_NAME from environment_settings.txt is not set, so it would
# reach the default install 'daaf'. For any other project the printed command
# carries `-p <project>`, as install.sh prints it. Without daaf_lib.sh the name
# is printed as set.
COMPOSE_P_FLAG=""
if command -v resolve_project_name >/dev/null 2>&1; then
    HINT_PROJECT="$(resolve_project_name)"
else
    HINT_PROJECT="${DAAF_PROJECT_NAME:-daaf}"
fi
if [ -n "${HINT_PROJECT}" ] && [ "${HINT_PROJECT}" != "daaf" ]; then
    COMPOSE_P_FLAG="-p ${HINT_PROJECT} "
fi

# Host-facing port for the browser URL (defaults to the fixed container port).
DAAF_PORT_MARIMO="${DAAF_PORT_MARIMO:-2718}"

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
            *"--print-token"*) echo "dryruntoken" ;;
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
echo "Opening DAAF Notebook Browser..."
echo ""
if ! docker compose exec daaf-docker bash /daaf/scripts/launch_marimo.sh; then
    echo "" >&2
    echo "ERROR: Failed to start the notebook browser." >&2
    echo "  The container may not be running, or marimo may not be installed." >&2
    echo "  Try: docker compose ${COMPOSE_P_FLAG}logs daaf-docker" >&2
fi

# Open browser automatically if library is available. URL uses the HOST-published
# port (DAAF_PORT_MARIMO); the container port stays fixed at 2718.
# marimo requires the access token launch_marimo.sh generates for each launch,
# so ask the running server for it (--print-token). Its stdout carries only the
# token, which stays in a shell variable and is never written to a file or log.
# -T: no TTY, so the captured value has no CR. If nothing is running any more
# (a foreground launch ended with Ctrl+C) or the server has no known token (an
# older launcher's --no-token server; launch_marimo.sh printed what to do),
# --print-token fails and no browser is opened.
if command -v open_url >/dev/null 2>&1; then
    MARIMO_TOKEN=""
    TOKEN_RC=0
    MARIMO_TOKEN=$(docker compose exec -T daaf-docker bash /daaf/scripts/launch_marimo.sh --print-token </dev/null 2>/dev/null) || TOKEN_RC=$?
    MARIMO_TOKEN="$(printf '%s' "${MARIMO_TOKEN}" | tr -d '\r\n')"
    if [ "${TOKEN_RC}" -eq 0 ] && [[ "${MARIMO_TOKEN}" =~ ^[A-Za-z0-9_-]+$ ]]; then
        echo "Opening the notebook browser in your default browser..."
        open_url "http://localhost:${DAAF_PORT_MARIMO}/?access_token=${MARIMO_TOKEN}"
    fi
fi

# If marimo was already running, the container-side script returns immediately
# after printing the URL. The EXIT trap keeps the terminal open so the user
# can read/copy it.
