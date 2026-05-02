#!/usr/bin/env bash
# ============================================================================
# DAAF Log Explorer (macOS / Linux)
# ============================================================================
# Opens the interactive session log viewer in your browser.
# Starts the DAAF container if needed, recovers any orphaned session logs,
# presents available log sources, and starts an HTTP server.
#
# Usage:
#   cd daaf-docker
#   bash view_logs.sh              # Interactive menu
#   bash view_logs.sh --archive    # Skip menu, open full archive
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Port 2719 mapped in docker-compose.yml
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

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
# Usage: DAAF_TEST_MODE=1 source scripts/host/view_logs.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# --- Parse arguments ---
SKIP_MENU=false
SELECTED_SOURCE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --archive)
            SKIP_MENU=true
            SELECTED_SOURCE="--archive"
            shift
            ;;
        -h|--help)
            echo "Usage: bash $0              # Interactive log source menu"
            echo "       bash $0 --archive    # Open full session archive directly"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            echo "Usage: bash $0 [--archive]" >&2
            exit 1
            ;;
    esac
done

# In non-interactive contexts, default to archive view
if [ "${DAAF_DRY_RUN:-}" = "1" ] || [ -n "${CI:-}" ] || [ -n "${DAAF_NESTED:-}" ] || ! [ -c /dev/tty ]; then
    SKIP_MENU=true
    SELECTED_SOURCE="${SELECTED_SOURCE:---archive}"
fi

# --- Preflight ---
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found in the current directory." >&2
    echo "Please run this script from your daaf-docker folder." >&2
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal." >&2
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/" >&2
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
        echo "  Try: docker compose logs daaf-docker" >&2
        exit 1
    fi
    echo "Container started."
else
    echo "DAAF container is running."
fi

# --- Recover orphaned session logs ---
# The recovery hook archives transcripts from sessions that ended without
# a clean SessionEnd (e.g., crashes). The hook's foreground portion returns
# immediately, but actual recovery runs in a detached background subshell
# inside the container (& disown). The sleep gives that subprocess time to
# finish before we discover log sources.
echo "Checking for orphaned session logs..."
echo '{"session_id":"recovery","transcript_path":"/home/appuser/.claude/projects/-daaf/_.jsonl"}' | docker compose exec -T -e CLAUDE_PROJECT_DIR=/daaf daaf-docker bash /daaf/.claude/hooks/recover-session-logs.sh 2>/dev/null || true
if [ "${DAAF_DRY_RUN:-}" != "1" ]; then
    sleep 2
fi

# --- Select log source ---
if [ "$SKIP_MENU" = false ]; then
    # Discover all log sources via helper script (avoids bash -c quoting issues)
    SOURCES_RAW=$(docker compose exec -T daaf-docker bash /daaf/scripts/discover_log_sources.sh 2>/dev/null | tr -d '\r') || SOURCES_RAW=""

    # Build menu arrays from pipe-delimited output
    declare -a MENU_PATHS=()
    declare -a MENU_LABELS=()

    if [ -n "$SOURCES_RAW" ]; then
        while IFS='|' read -r source_id session_count; do
            [ -z "$source_id" ] && continue
            session_count=$(echo "$session_count" | tr -d '[:space:]')
            if ! [[ "$session_count" =~ ^[0-9]+$ ]]; then continue; fi

            if [ "$session_count" -eq 1 ]; then
                count_label="$session_count session"
            else
                count_label="$session_count sessions"
            fi

            if [ "$source_id" = "ARCHIVE" ]; then
                MENU_PATHS+=("--archive")
                MENU_LABELS+=("Full session archive ($count_label)")
            else
                folder_name=$(basename "$source_id")
                display_date="${folder_name%%_*}"
                display_title=$(echo "${folder_name#*_}" | tr '_' ' ')
                MENU_PATHS+=("$source_id")
                MENU_LABELS+=("$display_date $display_title ($count_label)")
            fi
        done <<< "$SOURCES_RAW"
    fi

    if [ ${#MENU_PATHS[@]} -eq 0 ]; then
        echo ""
        echo "No log sources found. Run a DAAF session first to generate logs."
        exit 0
    fi

    echo ""
    echo "DAAF Log Explorer -- Select a log source:"
    echo ""
    for i in "${!MENU_LABELS[@]}"; do
        printf "  %d) %s\n" "$((i + 1))" "${MENU_LABELS[$i]}"
    done
    echo ""
    read -r -p "Enter selection: " SELECTION < /dev/tty

    if [ -z "$SELECTION" ] || ! [[ "$SELECTION" =~ ^[0-9]+$ ]] || [ "$SELECTION" -lt 1 ] || [ "$SELECTION" -gt ${#MENU_PATHS[@]} ]; then
        echo "ERROR: Invalid selection: $SELECTION" >&2
        exit 1
    fi

    SELECTED_SOURCE="${MENU_PATHS[$((SELECTION - 1))]}"
fi

# --- Launch log viewer ---
echo ""
echo "Opening DAAF Log Explorer..."
echo ""

declare -a VIEWER_ARGS=()
if [ "$SELECTED_SOURCE" = "--archive" ]; then
    VIEWER_ARGS=("--archive")
else
    VIEWER_ARGS=("$SELECTED_SOURCE")
fi

if ! docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh "${VIEWER_ARGS[@]}"; then
    echo "" >&2
    echo "ERROR: Failed to generate log viewer." >&2
    echo "  The container may not be running, or there may be no session logs to display." >&2
    echo "  Try: docker compose logs daaf-docker" >&2
fi

# If the server was already running, the command above returns immediately
# after printing the URL. The EXIT trap keeps the terminal open so the user
# can read/copy it.
