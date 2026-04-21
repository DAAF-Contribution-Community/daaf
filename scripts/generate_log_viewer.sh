#!/usr/bin/env bash
# generate_log_viewer.sh — Generate an interactive HTML session viewer for a DAAF project
#
# Processes JSONL session transcripts in a project's logs/ directory into a
# structured manifest, then copies the HTML viewer template alongside it.
# Optionally starts a local HTTP server so the viewer is accessible in a browser.
#
# Usage:
#   bash /daaf/scripts/generate_log_viewer.sh <project_path> [--serve] [--port PORT]
#
# Examples:
#   bash /daaf/scripts/generate_log_viewer.sh /daaf/research/2026-03-29_College_Analysis
#   bash /daaf/scripts/generate_log_viewer.sh /daaf/research/2026-03-29_College_Analysis --serve
#   bash /daaf/scripts/generate_log_viewer.sh /daaf/research/2026-03-29_College_Analysis --serve --port 2720
#
# Prerequisites:
#   - Project must have a logs/ directory containing *_orchestrator.jsonl files
#     (run collect_session_logs.sh first if needed)
#   - For --serve: port 2719 (default) must be mapped in docker-compose.yml
#
# Exit codes:
#   0 — success
#   1 — usage error, invalid project path, or missing logs

set -euo pipefail

# --- Resolve paths ---

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIEWER_TEMPLATE="$SCRIPT_DIR/log_viewer.html"
GENERATOR_SCRIPT="$SCRIPT_DIR/generate_log_viewer.py"

# --- Parse arguments ---

PROJECT_PATH=""
SERVE=false
PORT=2719

while [ $# -gt 0 ]; do
    case "$1" in
        --serve)
            SERVE=true
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
            echo "Usage: bash $0 <project_path> [--serve] [--port PORT]"
            echo ""
            echo "Generates an interactive HTML viewer for DAAF session logs."
            echo ""
            echo "Arguments:"
            echo "  project_path    Absolute path to a DAAF research project"
            echo "  --serve         Start an HTTP server after generating (default port: 2719)"
            echo "  --port PORT     Use a custom port for the HTTP server (default: 2719)"
            echo ""
            echo "Examples:"
            echo "  bash $0 /daaf/research/2026-03-29_Analysis"
            echo "  bash $0 /daaf/research/2026-03-29_Analysis --serve"
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

if [ -z "$PROJECT_PATH" ]; then
    echo "ERROR: Project path is required"
    echo "Usage: bash $0 <project_path> [--serve] [--port PORT]"
    exit 1
fi

if [ ! -d "$PROJECT_PATH" ]; then
    echo "ERROR: Project directory does not exist: $PROJECT_PATH"
    exit 1
fi

LOGS_DIR="$PROJECT_PATH/logs"

if [ ! -d "$LOGS_DIR" ]; then
    echo "ERROR: No logs/ directory found in: $PROJECT_PATH"
    echo "Hint: Run collect_session_logs.sh first to gather session transcripts."
    exit 1
fi

# Check for orchestrator JSONL files
ORCH_COUNT=$(find "$LOGS_DIR" -maxdepth 1 -name '*_orchestrator.jsonl' 2>/dev/null | wc -l)
if [ "$ORCH_COUNT" -eq 0 ]; then
    echo "ERROR: No orchestrator JSONL files found in: $LOGS_DIR"
    echo "Hint: Run collect_session_logs.sh first to gather session transcripts."
    exit 1
fi

if [ ! -f "$GENERATOR_SCRIPT" ]; then
    echo "ERROR: Python generator not found: $GENERATOR_SCRIPT"
    exit 1
fi

if [ ! -f "$VIEWER_TEMPLATE" ]; then
    echo "ERROR: HTML viewer template not found: $VIEWER_TEMPLATE"
    exit 1
fi

# --- Step 1: Generate manifest ---

echo "Generating session manifest..."
python3 "$GENERATOR_SCRIPT" "$PROJECT_PATH"

MANIFEST="$LOGS_DIR/session_manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "ERROR: Manifest generation failed — no output file created"
    exit 1
fi

# --- Step 2: Copy viewer template ---

VIEWER_DEST="$LOGS_DIR/log_viewer.html"
cp "$VIEWER_TEMPLATE" "$VIEWER_DEST"
echo "Copied viewer to: $VIEWER_DEST"

# --- Summary ---

echo ""
echo "=== Log Viewer Generated ==="
echo "  Manifest: $MANIFEST"
echo "  Viewer:   $VIEWER_DEST"
echo ""

# --- Step 3: Optionally start HTTP server ---

if [ "$SERVE" = true ]; then
    # Compute the viewer URL relative to repo root
    RELATIVE_VIEWER="${VIEWER_DEST#$REPO_ROOT/}"
    echo "Starting HTTP server on port $PORT (serving from $REPO_ROOT)..."
    echo ""
    echo "  Open in your browser:"
    echo "  http://localhost:$PORT/$RELATIVE_VIEWER"
    echo ""
    echo "  Press Ctrl+C to stop the server."
    echo ""
    cd "$REPO_ROOT"
    python3 -m http.server "$PORT"
else
    RELATIVE_VIEWER="${VIEWER_DEST#$REPO_ROOT/}"
    echo "To view in your browser, either:"
    echo ""
    echo "  1. Start the built-in server:"
    echo "     bash $0 $PROJECT_PATH --serve"
    echo ""
    echo "  2. Or copy the files out of the container:"
    echo "     docker cp daaf-daaf-docker-1:/daaf/$RELATIVE_VIEWER ./"
    echo "     docker cp daaf-daaf-docker-1:$MANIFEST ./"
    echo ""
fi
