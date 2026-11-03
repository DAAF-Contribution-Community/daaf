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
#
# --port is for use inside the container only. Compose publishes only container
# ports 2718-2720, one per DAAF web service (docker-compose.yml), so a browser
# on the host reaches code-server only on its own port, 2720.
#
# Default behavior:
#   - Opens /daaf (the DAAF project root)
#   - Serves on port 2720 (mapped in docker-compose.yml)
#   - Binds to 0.0.0.0 for Docker container access
#   - Password authentication enabled (password displayed on launch)
#   - code-server's bundled Node verifies TLS against the OS CA store
#     (NODE_OPTIONS gains --use-openssl-ca; see "TLS trust store" below)
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
            echo "  --port PORT       Port for the server (default: 2720; another port is"
            echo "                    reachable only from inside the container)"
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
    echo "  code-server ships in the DAAF image, so a missing code-server means the image needs rebuilding:" >&2
    printf '%s\n' "  exit the container, then choose 10) Rebuild Container in the DAAF Control Panel, or run 'bash rebuild_daaf.sh' ('.\\rebuild_daaf.ps1' on Windows) from the daaf-docker folder." >&2
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
        echo "  Fix: stop that process (kill $LISTEN_PID in the container, or DAAF Control Panel option 12 \"Stop Web Services\", which stops whatever holds ports 2718-2720), then launch again." >&2
        echo "  Keep the default port: your browser reaches VS Code only through container port 2720, so --port is for use inside the container only." >&2
        exit 1
    else
        echo "ERROR: Port $PORT is in use but the owning process could not be identified." >&2
        echo "  Fix: choose 11) Restart Container in the DAAF Control Panel, which frees every port (it also ends any open Claude Code session), then launch again." >&2
        echo "  Keep the default port: your browser reaches VS Code only through container port 2720, so --port is for use inside the container only." >&2
        exit 1
    fi
fi

# --- TLS trust store for code-server's bundled Node ---

# code-server runs on its own bundled Node (v22.22.1 in the pinned 4.117.0),
# which by default trusts Node's compiled-in root list. That list still contains
# "emSign ECC Root CA - G3", the root of the 2026-10-20 eMudhra compromise (see
# the Dockerfile section "Distrust compromised CA roots"). --use-openssl-ca
# makes it use the OS store instead (OPENSSLDIR /etc/ssl, so the hashed
# /etc/ssl/certs directory), from which the image removes G3. With
# --use-openssl-ca and a G3-free store, this Node rejects a chain to G3 and
# accepts a control host (observed 2026-10-24, code-server 4.117.0). Any
# NODE_OPTIONS already set is kept and the flag is appended once. Node refuses
# --use-openssl-ca together with --use-bundled-ca (exit 9; observed 2026-11-02,
# Node v22.22.1), so an explicit --use-bundled-ca is left alone, with a
# warning; a value that already holds both flags gets its own warning, because
# code-server would not start at all. Child processes inherit NODE_OPTIONS:
# code-server's terminals and extension host keep it, so `node
# --use-bundled-ca` typed in a code-server terminal exits 9; the Copilot agent
# host deletes it, and that extension is not in DAAF's set (verified against
# code-server 4.117.0 source on 2026-10-28; read, not run).
HAS_OPENSSL_CA=false
HAS_BUNDLED_CA=false
case " ${NODE_OPTIONS:-} " in *" --use-openssl-ca "*) HAS_OPENSSL_CA=true ;; esac
case " ${NODE_OPTIONS:-} " in *" --use-bundled-ca "*) HAS_BUNDLED_CA=true ;; esac
if [ "$HAS_OPENSSL_CA" = true ] && [ "$HAS_BUNDLED_CA" = true ]; then
    echo "WARNING: NODE_OPTIONS contains both --use-openssl-ca and --use-bundled-ca. Node refuses" >&2
    echo "  that combination (exit 9), so code-server will not start. Remove --use-bundled-ca." >&2
elif [ "$HAS_BUNDLED_CA" = true ]; then
    echo "WARNING: NODE_OPTIONS contains --use-bundled-ca, so code-server keeps Node's built-in root" >&2
    echo "  list, which still trusts the compromised emSign ECC Root CA - G3. Remove it to use the OS store." >&2
elif [ "$HAS_OPENSSL_CA" = false ]; then
    NODE_OPTIONS="${NODE_OPTIONS:+${NODE_OPTIONS} }--use-openssl-ca"
fi
export NODE_OPTIONS

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
