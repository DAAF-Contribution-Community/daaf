#!/usr/bin/env bash
# launch_code_server.sh — Launch code-server (VS Code in the browser) for DAAF
#
# Opens a browser-accessible VS Code instance for browsing, editing, and
# reviewing files in the DAAF container.
#
# Usage:
#   bash /daaf/scripts/launch_code_server.sh [directory] [--port PORT] [--background]
#
# Examples:
#   bash /daaf/scripts/launch_code_server.sh
#   bash /daaf/scripts/launch_code_server.sh /daaf/research/2026-04-15_My_Analysis
#   bash /daaf/scripts/launch_code_server.sh --port 2721
#
# Default behavior:
#   - Opens /daaf (the DAAF project root)
#   - Serves on port 2720 (mapped in docker-compose.yml)
#   - Binds to 0.0.0.0 for Docker container access
#   - Password authentication enabled (password displayed on launch)
#
# Exit codes:
#   0 — success (or server stopped by Ctrl+C)
#   1 — usage error, invalid directory, or port conflict

set -euo pipefail

# --- Defaults ---

PORT=2720
PORT_OVERRIDDEN=false
OPEN_DIR="/daaf"
PASSWORD="${PASSWORD:-daaf}"
BACKGROUND=false

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
            PORT_OVERRIDDEN=true
            shift 2
            ;;
        --password)
            if [ $# -lt 2 ]; then
                echo "ERROR: --password requires a value." >&2
                exit 1
            fi
            PASSWORD="$2"
            shift 2
            ;;
        --background)
            BACKGROUND=true
            shift
            ;;
        -h|--help)
            echo "Usage: bash $0 [directory] [--port PORT] [--password PASSWORD] [--background]"
            echo ""
            echo "Launch code-server (VS Code in the browser) for DAAF."
            echo ""
            echo "Arguments:"
            echo "  directory         Directory to open (default: /daaf)"
            echo "  --port PORT       Port for the server (default: 2720)"
            echo "  --password PASS   Set login password (default: \$PASSWORD or 'daaf')"
            echo "  --background      Start the server in the background and exit"
            echo ""
            echo "Examples:"
            echo "  bash $0                                          # Open DAAF root"
            echo "  bash $0 /daaf/research/2026-04-15_Analysis       # Specific project"
            echo ""
            echo "Open http://localhost:PORT in your browser after launching."
            exit 0
            ;;
        *)
            if [ "$OPEN_DIR" = "/daaf" ]; then
                OPEN_DIR="$1"
            else
                echo "ERROR: Unexpected argument: $1" >&2
                echo "  Usage: bash $0 [directory] [--port PORT]" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

# --- Validate directory ---

if [ ! -d "$OPEN_DIR" ]; then
    echo "ERROR: Directory does not exist: $OPEN_DIR" >&2
    exit 1
fi

# --- Validate port ---

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "ERROR: --port must be a number between 1 and 65535 (got: $PORT)" >&2
    exit 1
fi

# --- Resolve display port ---

# The server always BINDS the container-side port ($PORT stays 2720 unless
# --port is passed). But the URL the user opens goes through the compose port
# mapping (host ${DAAF_PORT_VSCODE:-2720} -> container 2720), so when the host
# port is remapped via environment_settings.txt (available in-container through
# the compose env_file), the printed URL must show the HOST port. An explicit
# --port bypasses this: custom in-container flows keep the literal port.
DISPLAY_PORT="$PORT"
if [ "$PORT_OVERRIDDEN" = false ] && [ -n "${DAAF_PORT_VSCODE:-}" ]; then
    DISPLAY_PORT="$DAAF_PORT_VSCODE"
fi

# --- Preflight ---

if ! command -v code-server >/dev/null 2>&1; then
    echo "ERROR: code-server is not installed." >&2
    echo "  This should be pre-installed in the DAAF Docker image." >&2
    echo "  If you rebuilt the image without code-server, re-run:" >&2
    echo "    bash rebuild_daaf.sh" >&2
    exit 1
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

    if echo "$LISTEN_CMD" | grep -q "code-server"; then
        echo "code-server is already running on port $PORT (PID $LISTEN_PID)."
        echo ""
        echo "  Open in your browser:"
        echo "  http://localhost:$DISPLAY_PORT"
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

# --- Launch code-server ---

echo "Starting code-server (VS Code in the browser)..."
echo "  Opening:  $OPEN_DIR"
echo "  Port:     $PORT"
echo ""
echo "  ┌────────────────────────────────────────────────┐"
printf "  │  %-46s │\n" "Open in your browser:"
printf "  │  %-46s │\n" "http://localhost:$DISPLAY_PORT"
printf "  │  %-46s │\n" ""
printf "  │  %-46s │\n" "Password: $PASSWORD"
echo "  └────────────────────────────────────────────────┘"
echo ""

export PASSWORD
if [ "$BACKGROUND" = true ]; then
    nohup code-server \
        --bind-addr "0.0.0.0:$PORT" \
        --user-data-dir /home/appuser/.local/share/code-server \
        --extensions-dir /home/appuser/.local/share/code-server/extensions \
        --disable-telemetry \
        --disable-update-check \
        --disable-getting-started-override \
        --auth password \
        "$OPEN_DIR" > /dev/null 2>&1 &
    disown
    echo "Server started in background (PID $!)."
    echo "  URL: http://localhost:$DISPLAY_PORT"
    exit 0
else
    echo "  Press Ctrl+C to stop the server."
    echo ""
    exec code-server \
        --bind-addr "0.0.0.0:$PORT" \
        --user-data-dir /home/appuser/.local/share/code-server \
        --extensions-dir /home/appuser/.local/share/code-server/extensions \
        --disable-telemetry \
        --disable-update-check \
        --disable-getting-started-override \
        --auth password \
        "$OPEN_DIR"
fi
