#!/usr/bin/env bash
# generate_log_viewer.sh — Generate an interactive HTML session viewer for a DAAF project
#
# Processes JSONL session transcripts into a structured manifest, then starts
# an HTTP server so the interactive Log Explorer is accessible in a browser.
#
# Usage:
#   bash /daaf/scripts/generate_log_viewer.sh <project_path> [--port PORT]
#   bash /daaf/scripts/generate_log_viewer.sh --archive [--port PORT]
#
# Examples:
#   bash /daaf/scripts/generate_log_viewer.sh /daaf/research/2026-03-29_College_Analysis
#   bash /daaf/scripts/generate_log_viewer.sh /daaf/research/2026-03-29_College_Analysis --port 2720
#   bash /daaf/scripts/generate_log_viewer.sh --archive
#
# Prerequisites:
#   - Project must have a logs/ directory containing *_orchestrator.jsonl files
#     (run collect_session_logs.sh first if needed), or use --archive for all sessions
#   - Port 2719 (default) must be mapped in docker-compose.yml
#
# Exit codes:
#   0 — success
#   1 — usage error, invalid project path, or missing logs

set -euo pipefail

# --- Resolve paths ---

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GENERATOR_SCRIPT="$SCRIPT_DIR/generate_log_viewer.py"

# --- Parse arguments ---

PROJECT_PATH=""
SERVE=true
PORT=2719
ARCHIVE=false

while [ $# -gt 0 ]; do
    case "$1" in
        --archive)
            ARCHIVE=true
            shift
            ;;
        --serve)
            # Default behavior; accepted for backwards compatibility
            shift
            ;;
        --no-serve)
            SERVE=false
            shift
            ;;
        --port)
            if [ $# -lt 2 ]; then
                echo "ERROR: --port requires a value"
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: bash $0 <project_path> [--port PORT] [--no-serve]"
            echo "       bash $0 --archive [--port PORT] [--no-serve]"
            echo ""
            echo "Generates an interactive HTML viewer for DAAF session logs"
            echo "and starts an HTTP server (default port: 2719)."
            echo ""
            echo "Arguments:"
            echo "  project_path    Absolute path to a DAAF research project"
            echo "  --archive       View all sessions from the DAAF-wide log archive"
            echo "  --port PORT     Use a custom port for the HTTP server (default: 2719)"
            echo "  --no-serve      Generate the manifest without starting a server"
            echo ""
            echo "Examples:"
            echo "  bash $0 /daaf/research/2026-03-29_Analysis"
            echo "  bash $0 --archive"
            exit 0
            ;;
        *)
            if [ -z "$PROJECT_PATH" ]; then
                PROJECT_PATH="$1"
            else
                echo "ERROR: Unexpected argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# --- Validate inputs ---

if [ "$ARCHIVE" = true ] && [ -n "$PROJECT_PATH" ]; then
    echo "ERROR: --archive and project_path are mutually exclusive"
    exit 1
fi

if [ "$ARCHIVE" = false ] && [ -z "$PROJECT_PATH" ]; then
    echo "ERROR: Project path is required (or use --archive for DAAF-wide view)"
    echo "Usage: bash $0 <project_path> [--port PORT] [--no-serve]"
    echo "       bash $0 --archive [--port PORT] [--no-serve]"
    exit 1
fi

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "ERROR: --port must be a number between 1 and 65535 (got: $PORT)"
    exit 1
fi

if [ "$ARCHIVE" = true ]; then
    LOGS_DIR="$REPO_ROOT/.claude/logs/sessions"
else
    if [ ! -d "$PROJECT_PATH" ]; then
        echo "ERROR: Project directory does not exist: $PROJECT_PATH"
        exit 1
    fi
    LOGS_DIR="$PROJECT_PATH/logs"
fi

if [ ! -d "$LOGS_DIR" ]; then
    if [ "$ARCHIVE" = true ]; then
        echo "ERROR: No session archive found at: $LOGS_DIR"
    else
        echo "ERROR: No logs/ directory found in: $PROJECT_PATH"
        echo "Hint: Run collect_session_logs.sh first to gather session transcripts."
    fi
    exit 1
fi

# Check for orchestrator JSONL files
ORCH_COUNT=$(find "$LOGS_DIR" -maxdepth 1 -name '*_orchestrator.jsonl' 2>/dev/null | wc -l)
if [ "$ORCH_COUNT" -eq 0 ]; then
    echo "ERROR: No orchestrator JSONL files found in: $LOGS_DIR"
    if [ "$ARCHIVE" = false ]; then
        echo "Hint: Run collect_session_logs.sh first to gather session transcripts."
    fi
    exit 1
fi

if [ ! -f "$GENERATOR_SCRIPT" ]; then
    echo "ERROR: Python generator not found: $GENERATOR_SCRIPT"
    exit 1
fi

# --- Step 1: Generate manifest ---

echo "Generating session manifest..."
if [ "$ARCHIVE" = true ]; then
    if ! python3 "$GENERATOR_SCRIPT" --logs-dir "$LOGS_DIR"; then
        echo "ERROR: Manifest generation failed (see Python output above)"
        exit 1
    fi
else
    if ! python3 "$GENERATOR_SCRIPT" "$PROJECT_PATH"; then
        echo "ERROR: Manifest generation failed (see Python output above)"
        exit 1
    fi
fi

MANIFEST="$LOGS_DIR/session_manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "ERROR: Manifest generation failed — no output file created"
    exit 1
fi

# --- Step 2: Compute viewer URL ---

# The viewer lives at its canonical location in scripts/ and accepts
# the manifest path as a query parameter — no copy needed.
RELATIVE_MANIFEST="${MANIFEST#$REPO_ROOT/}"
VIEWER_URL="scripts/log_viewer.html?manifest=$RELATIVE_MANIFEST"

# --- Summary ---

echo ""
echo "=== Log Viewer Generated ==="
echo "  Manifest: $MANIFEST"
echo ""

# --- Step 3: Optionally start HTTP server ---

if [ "$SERVE" = true ]; then
    # Check if a server is already listening on the target port
    # Use /proc/net/tcp and /proc/net/tcp6 (reliable in Docker) since lsof may not see all processes
    PORT_HEX=$(printf '%04X' "$PORT")
    LISTEN_INODE=$(awk -v ph="$PORT_HEX" '$2 ~ ":"ph"$" && $4 == "0A" {print $10}' /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -1)

    if [ -n "$LISTEN_INODE" ]; then
        # Find the PID holding this socket
        # Note: find may return non-zero as /proc entries vanish mid-scan; || true prevents set -e abort
        LISTEN_PID=$(find /proc -maxdepth 3 -path '*/fd/*' -exec ls -la {} + 2>/dev/null \
            | grep "socket:\[$LISTEN_INODE\]" | head -1 \
            | sed 's|.*/proc/\([0-9]*\)/.*|\1|' || true)

        # Validate PID is numeric
        if ! [[ "$LISTEN_PID" =~ ^[0-9]+$ ]]; then
            LISTEN_PID=""
        fi

        LISTEN_CMD=""
        [ -n "$LISTEN_PID" ] && LISTEN_CMD=$(ps -p "$LISTEN_PID" -o args= 2>/dev/null || true)

        if echo "$LISTEN_CMD" | grep -q "http.server"; then
            echo "Server already running on port $PORT (PID $LISTEN_PID)."
            echo ""
            echo "  Open in your browser:"
            echo "  http://localhost:$PORT/$VIEWER_URL"
            echo ""
        elif [ -n "$LISTEN_PID" ]; then
            echo "Port $PORT is in use by: $LISTEN_CMD (PID $LISTEN_PID). Stopping it..."
            kill "$LISTEN_PID" 2>/dev/null
            sleep 1
            echo "Starting HTTP server on port $PORT (serving from $REPO_ROOT)..."
            echo ""
            echo "  Open in your browser:"
            echo "  http://localhost:$PORT/$VIEWER_URL"
            echo ""
            echo "  Press Ctrl+C to stop the server."
            echo ""
            cd "$REPO_ROOT"
            python3 -c "
import http.server, socketserver
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', $PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    httpd.serve_forever()
"
        else
            echo "ERROR: Port $PORT is in use but the owning process could not be identified."
            echo "Free the port manually or use --port to specify a different one."
            exit 1
        fi
    else
        echo "Starting HTTP server on port $PORT (serving from $REPO_ROOT)..."
        echo ""
        echo "  Open in your browser:"
        echo "  http://localhost:$PORT/$VIEWER_URL"
        echo ""
        echo "  Press Ctrl+C to stop the server."
        echo ""
        cd "$REPO_ROOT"
        python3 -c "
import http.server, socketserver
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', $PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    httpd.serve_forever()
"
    fi
else
    echo "Manifest generated. To view, re-run without --no-serve:"
    echo ""
    if [ "$ARCHIVE" = true ]; then
        echo "  bash $0 --archive"
    else
        echo "  bash $0 $PROJECT_PATH"
    fi
    echo ""
fi
