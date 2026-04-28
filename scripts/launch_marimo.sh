#!/usr/bin/env bash
# launch_marimo.sh — Launch marimo's notebook browser for DAAF projects
#
# Opens marimo's built-in home page, which provides a web-based file explorer
# for browsing, opening, creating, and editing marimo notebooks.
#
# Usage:
#   bash /daaf/scripts/launch_marimo.sh [directory] [--port PORT]
#
# Examples:
#   bash /daaf/scripts/launch_marimo.sh
#   bash /daaf/scripts/launch_marimo.sh /daaf/research/2026-04-15_My_Analysis
#   bash /daaf/scripts/launch_marimo.sh --port 2720
#
# Default behavior:
#   - Browses /daaf/research/ (where all project notebooks live)
#   - Serves on port 2718 (mapped in docker-compose.yml)
#   - Binds to 0.0.0.0 for Docker container access
#   - Runs without authentication token (local development only)
#
# Exit codes:
#   0 — success (or server stopped by Ctrl+C)
#   1 — usage error, invalid directory, or port conflict

set -euo pipefail

# --- Resolve paths ---

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Defaults ---

readonly DEFAULT_DIR="$REPO_ROOT/research"
PORT=2718
BROWSE_DIR=""

# --- Parse arguments ---

while [ $# -gt 0 ]; do
    case "$1" in
        --port)
            if [ $# -lt 2 ]; then
                echo "ERROR: --port requires a value." >&2
                echo "  Usage: bash $0 [directory] [--port PORT]" >&2
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: bash $0 [directory] [--port PORT]"
            echo ""
            echo "Launch marimo's notebook browser for DAAF projects."
            echo ""
            echo "Arguments:"
            echo "  directory     Directory to browse (default: /daaf/research)"
            echo "  --port PORT   Port for the marimo server (default: 2718)"
            echo ""
            echo "Examples:"
            echo "  bash $0                                # Browse all projects"
            echo "  bash $0 /daaf/research/2026-04-15_Analysis  # Specific project"
            echo ""
            echo "Open http://localhost:PORT in your browser after launching."
            exit 0
            ;;
        *)
            if [ -z "$BROWSE_DIR" ]; then
                BROWSE_DIR="$1"
            else
                echo "ERROR: Unexpected argument: $1" >&2
                echo "  Usage: bash $0 [directory] [--port PORT]" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

# --- Resolve browse directory ---

if [ -z "$BROWSE_DIR" ]; then
    BROWSE_DIR="$DEFAULT_DIR"
fi

if [ ! -d "$BROWSE_DIR" ]; then
    echo "ERROR: Directory does not exist: $BROWSE_DIR" >&2
    echo "  Create a research project first, or specify a different directory." >&2
    exit 1
fi

# --- Validate port ---

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "ERROR: --port must be a number between 1 and 65535 (got: $PORT)" >&2
    exit 1
fi

# --- Preflight ---

if ! command -v marimo >/dev/null 2>&1; then
    echo "ERROR: marimo is not installed." >&2
    echo "  Install with: pip install marimo" >&2
    exit 30
fi

# --- Check for port conflict ---

PORT_HEX=$(printf '%04X' "$PORT")
LISTEN_INODE=$(awk -v ph="$PORT_HEX" '$2 ~ ":"ph"$" && $4 == "0A" {print $10}' /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -1)

if [ -n "$LISTEN_INODE" ]; then
    LISTEN_PID=$(find /proc -maxdepth 3 -path '*/fd/*' -exec ls -la {} + 2>/dev/null \
        | grep "socket:\[$LISTEN_INODE\]" | head -1 \
        | sed 's|.*/proc/\([0-9]*\)/.*|\1|' || true)

    if ! [[ "$LISTEN_PID" =~ ^[0-9]+$ ]]; then
        LISTEN_PID=""
    fi

    LISTEN_CMD=""
    [ -n "$LISTEN_PID" ] && LISTEN_CMD=$(ps -p "$LISTEN_PID" -o args= 2>/dev/null || true)

    if echo "$LISTEN_CMD" | grep -q "marimo"; then
        echo "Marimo is already running on port $PORT (PID $LISTEN_PID)."
        echo ""
        echo "  Open in your browser:"
        echo "  http://localhost:$PORT"
        echo ""
        exit 0
    elif [ -n "$LISTEN_PID" ]; then
        echo "ERROR: Port $PORT is in use by another process: $LISTEN_CMD (PID $LISTEN_PID)" >&2
        echo "  Free the port or use --port to specify a different one." >&2
        exit 1
    else
        echo "ERROR: Port $PORT is in use but the owning process could not be identified." >&2
        echo "  Free the port or use --port to specify a different one." >&2
        exit 1
    fi
fi

# --- Launch marimo ---

echo "Starting marimo notebook browser..."
echo "  Browsing: $BROWSE_DIR"
echo "  Port:     $PORT"
echo ""
echo "  Open in your browser:"
echo "  http://localhost:$PORT"
echo ""
echo "  (Marimo will print its own URL below using 0.0.0.0 — ignore that,"
echo "   use the localhost link above from your host browser.)"
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

exec marimo edit "$BROWSE_DIR" --host 0.0.0.0 --port "$PORT" --no-token --headless --skip-update-check
