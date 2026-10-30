#!/usr/bin/env bash
# launch_marimo.sh — Launch marimo's notebook browser for DAAF projects
#
# Opens marimo's built-in home page, which provides a web-based file explorer
# for browsing, opening, creating, and editing marimo notebooks.
#
# Usage:
#   bash /daaf/scripts/launch_marimo.sh [directory] [--port PORT] [--background]
#   bash /daaf/scripts/launch_marimo.sh --print-token [--port PORT]
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
#   - Requires a fresh random access token for every server launch
#
# Why a token: marimo's terminal WebSocket (/terminal/ws) opens a shell in the
# container, and marimo checks it only when a token is set. It checks no Origin
# or Host header, so with --no-token any web page open in the user's browser
# (or any process that can reach the port) could open that shell while the
# server runs; binding the published port to the host's 127.0.0.1 does not stop
# a browser page. With a token, the browser logs in once through the printed
# link, http://localhost:PORT/?access_token=TOKEN, and marimo keeps the session
# in a SameSite=Lax cookie, which a cross-site page's WebSocket does not carry.
#
# Where the token lives: 256 bits from /dev/urandom (hex), written to
# $HOME/.local/state/daaf/marimo-token-PORT (directory 0700, file 0600; the
# container layer, NOT /daaf, because the log viewer serves /daaf and /daaf is
# backed up). marimo reads it via --token-password-file, so the token never
# appears on a command line. A new launch writes a new token; a running server
# keeps the one it started with.
#
# --print-token prints only the token of the marimo server listening on PORT,
# provided this launcher started it. The host launchers (view_notebooks.*,
# daaf.* option 4) call it through `docker compose exec` to open the tokenized
# URL in the browser.
#
# Exit codes:
#   0 — success (or server stopped by Ctrl+C)
#   1 — usage error, invalid directory, or port conflict
#   4 — --print-token: no marimo server is listening on PORT
#   5 — --print-token: the marimo server on PORT was started without a token
#       (an older launcher); stop it and launch again
#   6 — --print-token: the marimo server on PORT was not started by this
#       launcher, so its token is unknown
#   30 — marimo is not installed (the image needs rebuilding)

set -euo pipefail

# --- Resolve paths ---

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Defaults ---

readonly DEFAULT_DIR="$REPO_ROOT/research"
PORT=2718
PORT_OVERRIDDEN=false
BROWSE_DIR=""
BACKGROUND=false
PRINT_TOKEN=false

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
        --background)
            BACKGROUND=true
            shift
            ;;
        --print-token)
            PRINT_TOKEN=true
            shift
            ;;
        -h|--help)
            echo "Usage: bash $0 [directory] [--port PORT] [--background]"
            echo "       bash $0 --print-token [--port PORT]"
            echo ""
            echo "Launch marimo's notebook browser for DAAF projects."
            echo ""
            echo "Arguments:"
            echo "  directory       Directory to browse (default: /daaf/research)"
            echo "  --port PORT     Port for the marimo server (default: 2718)"
            echo "  --background    Start the server in the background and exit"
            echo "  --print-token   Print the access token of the server running on PORT"
            echo ""
            echo "Examples:"
            echo "  bash $0                                # Browse all projects"
            echo "  bash $0 /daaf/research/2026-04-15_Analysis  # Specific project"
            echo ""
            echo "Open the printed http://localhost:PORT/?access_token=... link in your"
            echo "browser after launching. Each launch uses a new token."
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

# --print-token serves nothing, so it does not need the browse directory.
if [ "$PRINT_TOKEN" = false ] && [ ! -d "$BROWSE_DIR" ]; then
    echo "ERROR: Directory does not exist: $BROWSE_DIR" >&2
    echo "  Create a research project first, or specify a different directory." >&2
    exit 1
fi

# --- Validate port ---

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "ERROR: --port must be a number between 1 and 65535 (got: $PORT)" >&2
    exit 1
fi

# --- Resolve display port ---

# The server always BINDS the container-side port ($PORT stays 2718 unless
# --port is passed). But the URL the user opens goes through the compose port
# mapping (host ${DAAF_PORT_MARIMO:-2718} -> container 2718), so when the host
# port is remapped via environment_settings.txt (available in-container through
# the compose env_file), the printed URL must show the HOST port. An explicit
# --port bypasses this: custom in-container flows keep the literal port.
DISPLAY_PORT="$PORT"
if [ "$PORT_OVERRIDDEN" = false ] && [ -n "${DAAF_PORT_MARIMO:-}" ]; then
    DISPLAY_PORT="$DAAF_PORT_MARIMO"
fi

# --- Token file location ---

# Keyed by the container port, so two servers on different ports keep separate
# tokens. Outside /daaf on purpose (see the header): the log viewer serves /daaf.
TOKEN_DIR="${HOME:?HOME is not set}/.local/state/daaf"
TOKEN_FILE="$TOKEN_DIR/marimo-token-$PORT"

# --- Preflight ---

# --print-token only reads state, so it does not need marimo itself.
if [ "$PRINT_TOKEN" = false ] && ! command -v marimo >/dev/null 2>&1; then
    echo "ERROR: marimo is not installed." >&2
    echo "  marimo ships in the DAAF image, so a missing marimo means the image needs rebuilding:" >&2
    printf '%s\n' "  exit the container, then run 'bash rebuild_daaf.sh' ('.\\rebuild_daaf.ps1' on Windows) from the daaf-docker folder." >&2
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
        # Which token does the running server use? This launcher starts marimo
        # with --token-password-file "$TOKEN_FILE"; launchers before the token
        # change used --no-token; anything else was started by hand, with a
        # token this script cannot know. ${TOKEN_FILE} stays inside the double
        # quotes of the pattern, so any glob characters in it match literally.
        TOKEN_STATE="unknown"
        case " $LISTEN_CMD " in
            *" --no-token "*)
                TOKEN_STATE="none"
                ;;
            *" --token-password-file ${TOKEN_FILE} "*)
                if [ -s "$TOKEN_FILE" ]; then
                    TOKEN_STATE="recorded"
                fi
                ;;
        esac

        if [ "$PRINT_TOKEN" = true ]; then
            case "$TOKEN_STATE" in
                recorded)
                    printf '%s\n' "$(cat "$TOKEN_FILE")"
                    exit 0
                    ;;
                none)
                    echo "ERROR: The marimo server on port $PORT was started without an access token." >&2
                    echo "  Fix: stop it with DAAF Control Panel option 12 \"Stop Web Services\" or with pkill -f \"marimo edit\" in the container, then launch it again with this script." >&2
                    exit 5
                    ;;
                *)
                    echo "ERROR: The marimo server on port $PORT was not started by launch_marimo.sh; its access token is unknown." >&2
                    echo "  Fix: use the link printed when it started, or stop it with DAAF Control Panel option 12 \"Stop Web Services\" and launch it again with this script." >&2
                    exit 6
                    ;;
            esac
        fi

        echo "Marimo is already running on port $PORT (PID $LISTEN_PID)."
        echo ""
        case "$TOKEN_STATE" in
            recorded)
                echo "  Open in your browser (the link includes this server's access token):"
                echo "  http://localhost:$DISPLAY_PORT/?access_token=$(cat "$TOKEN_FILE")"
                ;;
            none)
                echo "  WARNING: this server was started by an older DAAF launcher WITHOUT an"
                echo "  access token, so any web page open in your browser could reach it."
                echo "  Stop it, then open the notebooks again to start it with a token:"
                echo "    - DAAF Control Panel: 12) Stop Web Services, or"
                echo "    - from your daaf-docker folder: docker compose exec daaf-docker pkill -f \"marimo edit\""
                ;;
            *)
                echo "  It was not started by this launcher, so its access token is unknown."
                echo "  Use the link that was printed when it started, or stop it and launch again:"
                echo "    - DAAF Control Panel: 12) Stop Web Services, or"
                echo "    - from your daaf-docker folder: docker compose exec daaf-docker pkill -f \"marimo edit\""
                ;;
        esac
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

if [ "$PRINT_TOKEN" = true ]; then
    echo "ERROR: No marimo server is listening on port $PORT." >&2
    echo "  Fix: start one first with bash $0 or DAAF Control Panel option 4 \"View Marimo Notebooks\", then ask for its token again." >&2
    exit 4
fi

# --- Generate this launch's access token ---

# INTENT: a fresh token per launch, readable only by the container user.
# REASONING: 32 bytes from the kernel CSPRNG = 256 bits; hex is URL-safe, so
# the token drops straight into ?access_token= with no escaping. The file is
# written to a mktemp file (created 0600) and renamed over the old one, so a
# reader never sees a half-written token and the mode never widens. umask is
# NOT changed for the whole script: marimo inherits it, and a 077 umask would
# make every notebook it creates private.
mkdir -p "$TOKEN_DIR"
chmod 700 "$TOKEN_DIR"
TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
if ! [[ "$TOKEN" =~ ^[0-9a-f]{64}$ ]]; then
    echo "ERROR: Could not generate an access token from /dev/urandom." >&2
    exit 1
fi
TOKEN_TMP="$(mktemp "$TOKEN_DIR/.marimo-token-$PORT.XXXXXX")"
trap 'rm -f "$TOKEN_TMP"' EXIT
printf '%s\n' "$TOKEN" > "$TOKEN_TMP"
mv -f "$TOKEN_TMP" "$TOKEN_FILE"

# --- Launch marimo ---

echo "Starting marimo notebook browser..."
echo "  Browsing: $BROWSE_DIR"
echo "  Port:     $PORT"
echo ""
echo "  Open in your browser (the link includes this launch's access token):"
echo "  http://localhost:$DISPLAY_PORT/?access_token=$TOKEN"
echo ""
echo "  (Marimo will print its own URL below using 0.0.0.0 — ignore that,"
echo "   use the localhost link above from your host browser.)"
echo ""

if [ "$BACKGROUND" = true ]; then
    nohup marimo edit "$BROWSE_DIR" --host 0.0.0.0 --port "$PORT" --token-password-file "$TOKEN_FILE" --headless --skip-update-check > /dev/null 2>&1 &
    disown
    echo "Server started in background (PID $!)."
    echo "  URL: http://localhost:$DISPLAY_PORT/?access_token=$TOKEN"
    exit 0
else
    echo "  Press Ctrl+C to stop the server."
    echo ""
    exec marimo edit "$BROWSE_DIR" --host 0.0.0.0 --port "$PORT" --token-password-file "$TOKEN_FILE" --headless --skip-update-check
fi
