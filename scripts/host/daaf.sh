#!/usr/bin/env bash
# ============================================================================
# DAAF Control Panel (macOS / Linux)
# ============================================================================
# Interactive menu wrapper for all DAAF operations. Presents a status
# dashboard and numbered options for launching services, managing backups,
# and performing maintenance.
#
# Usage:
#   cd daaf-docker
#   bash daaf.sh
#
# This is the top-level entry point -- it runs a persistent menu loop and
# delegates to individual scripts via DAAF_NESTED=1 to suppress their
# pause-on-exit traps.
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# --- Source shared library ---
DAAF_LIB_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${DAAF_LIB_DIR}/daaf_lib.sh"
setup_colors
SCRIPT_DIR="$DAAF_LIB_DIR"

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps --status running"*"--format"*) echo "daaf-docker" ;;
            *"compose exec"*"ss -tlnp"*) echo "" ;;
            *"compose exec"*"git"*"describe"*) echo "v2.0.0" ;;
            *"compose exec"*"git"*"log"*) echo "2026-06-21" ;;
            *"compose exec"*"git"*"branch"*) echo "main" ;;
            *"compose exec"*"git"*"rev-list"*) echo "0" ;;
            *"compose exec -d"*) return 0 ;;
            *"compose exec"*) echo "[DRY-RUN] docker $*" >&2; return 0 ;;
            *) echo "[DRY-RUN] docker $*" >&2; return 0 ;;
        esac
    }
fi

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/daaf.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
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
    echo "ERROR: Docker Desktop does not seem to be running. Please start it and try again." >&2
    exit 1
fi

# --- Signal handling ---
trap 'echo ""; echo "Goodbye!"; exit 0' INT TERM

# ============================================================================
# Status Gathering
# ============================================================================

gather_status() {
    local tmpdir
    tmpdir=$(mktemp -d)

    # Check if container is running first
    local running
    running=$(docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -c "daaf-docker" || true)

    if [ "$running" -eq 0 ]; then
        STATUS_CONTAINER="Stopped"
        STATUS_VERSION="--"
        STATUS_DATE=""
        STATUS_BRANCH="--"
        STATUS_UPDATES=""
        STATUS_PORT_2718=false
        STATUS_PORT_2719=false
        STATUS_PORT_2720=false
    else
        STATUS_CONTAINER="Running"

        # Parallel docker exec calls for container-side info
        docker compose exec -T daaf-docker git -C /daaf describe --tags --always \
            </dev/null 2>/dev/null > "$tmpdir/version" &
        docker compose exec -T daaf-docker git -C /daaf log -1 --format='%cd' --date=short \
            </dev/null 2>/dev/null > "$tmpdir/date" &
        docker compose exec -T daaf-docker git -C /daaf branch --show-current \
            </dev/null 2>/dev/null > "$tmpdir/branch" &
        docker compose exec -T daaf-docker git -C /daaf rev-list --count HEAD..origin/main \
            </dev/null 2>/dev/null > "$tmpdir/updates" &
        docker compose exec -T daaf-docker bash -c "ss -tlnp 2>/dev/null" \
            </dev/null 2>/dev/null > "$tmpdir/ports" &
        wait || true

        STATUS_VERSION=$(tr -d '\r' < "$tmpdir/version" 2>/dev/null || echo "unknown")
        STATUS_DATE=$(tr -d '\r' < "$tmpdir/date" 2>/dev/null || echo "")
        STATUS_BRANCH=$(tr -d '\r' < "$tmpdir/branch" 2>/dev/null || echo "detached")
        STATUS_UPDATES=$(tr -d '\r' < "$tmpdir/updates" 2>/dev/null || echo "")

        # Parse ports from ss output
        local ports_output
        ports_output=$(tr -d '\r' < "$tmpdir/ports" 2>/dev/null || echo "")
        STATUS_PORT_2718=false
        STATUS_PORT_2719=false
        STATUS_PORT_2720=false
        if echo "$ports_output" | grep -q ":2718 "; then STATUS_PORT_2718=true; fi
        if echo "$ports_output" | grep -q ":2719 "; then STATUS_PORT_2719=true; fi
        if echo "$ports_output" | grep -q ":2720 "; then STATUS_PORT_2720=true; fi
    fi

    # Local backup check (no docker needed)
    # Use glob array instead of parsing ls output
    local -a backup_dirs=(./*_daaf_backup)
    if [ -e "${backup_dirs[0]}" ]; then
        local last_backup_dir="${backup_dirs[-1]}"
        STATUS_LAST_BACKUP=$(basename "$last_backup_dir" | sed 's/_daaf_backup//')
    else
        STATUS_LAST_BACKUP=""
    fi

    rm -rf "$tmpdir"
}

# ============================================================================
# Menu Display
# ============================================================================

display_menu() {
    echo ""
    echo "=========================================="
    echo "  DAAF Control Panel"
    echo "=========================================="
    echo ""

    # --- Status dashboard ---
    if [ "$STATUS_CONTAINER" = "Running" ]; then
        echo "  Container:  ${GREEN}●${RESET} Running"
    else
        echo "  Container:  ${DIM}○${RESET} Stopped"
    fi

    # Version line
    local version_line
    version_line="  Version:    ${STATUS_VERSION}"
    if [ -n "$STATUS_DATE" ]; then
        version_line="${version_line} (${STATUS_DATE})"
    fi
    echo "$version_line"

    # Branch line
    local branch_line
    branch_line="  Branch:     ${STATUS_BRANCH}"
    if [ -n "$STATUS_UPDATES" ] && [ "$STATUS_UPDATES" != "0" ]; then
        branch_line="${branch_line} (${STATUS_UPDATES} updates available)"
    elif [ -n "$STATUS_UPDATES" ]; then
        branch_line="${branch_line} (up to date)"
    fi
    echo "$branch_line"

    # Last backup
    if [ -n "$STATUS_LAST_BACKUP" ]; then
        echo "  Last backup: ${STATUS_LAST_BACKUP}"
    else
        echo "  Last backup: never"
    fi

    echo ""

    # --- Services ---
    echo "  Services:"
    if [ "$STATUS_PORT_2718" = true ]; then
        echo "    ${GREEN}●${RESET} Notebooks    localhost:2718"
    else
        echo "    ${DIM}○${RESET} Notebooks    (not running)"
    fi
    if [ "$STATUS_PORT_2719" = true ]; then
        echo "    ${GREEN}●${RESET} Log Viewer   localhost:2719"
    else
        echo "    ${DIM}○${RESET} Log Viewer   (not running)"
    fi
    if [ "$STATUS_PORT_2720" = true ]; then
        echo "    ${GREEN}●${RESET} VS Code      localhost:2720"
    else
        echo "    ${DIM}○${RESET} VS Code      (not running)"
    fi

    echo ""

    # --- Menu options ---
    echo "  ${BOLD}LAUNCH${RESET}"
    echo "    1) Start Claude Code"
    echo "    2) Browse Notebooks"
    echo "    3) Browse Files (VS Code)"
    echo "    4) View Session Logs"
    echo "    5) Open Container Shell"

    echo ""

    echo "  ${BOLD}MANAGE${RESET}"
    echo "    6) Create Backup"
    echo "    7) Restore from Backup"
    echo "    8) Check for Updates"
    echo "    9) Rebuild Container"
    echo "   10) Stop Web Services"

    echo ""

    echo "  ${BOLD}OTHER${RESET}"
    echo "    h) Help"
    echo "    q) Quit"

    echo ""
}

# ============================================================================
# Input
# ============================================================================

read_choice() {
    if ! read -r -p "  Enter choice: " CHOICE; then
        echo ""
        echo "Goodbye!"
        exit 0
    fi
}

# ============================================================================
# Dispatch
# ============================================================================

dispatch_choice() {
    case "$1" in
        1)  handle_claude_code ;;
        2)  handle_notebooks ;;
        3)  handle_vscode ;;
        4)  handle_logs ;;
        5)  handle_shell ;;
        6)  handle_backup ;;
        7)  handle_restore ;;
        8)  handle_update ;;
        9)  handle_rebuild ;;
        10) handle_stop_services ;;
        h|H) handle_help ;;
        q|Q) handle_quit ;;
        "") ;;  # Empty input -- just redraw
        *)  echo "  Invalid choice. Please enter a number (1-10), h, or q." ;;
    esac
}

# ============================================================================
# Handlers: Interactive (options 1, 5)
# ============================================================================

handle_claude_code() {
    echo ""
    echo "Launching Claude Code..."
    echo "(When you're done, type /exit to return to this menu)"
    echo ""
    DAAF_NESTED=1 bash "${SCRIPT_DIR}/run_daaf.sh"
    echo ""
    echo "Returned to DAAF Control Panel."
}

handle_shell() {
    echo ""
    echo "Opening container shell..."
    echo "(Type 'exit' to return to this menu)"
    echo ""
    DAAF_NESTED=1 bash "${SCRIPT_DIR}/run_daaf.sh" bash
    echo ""
    echo "Returned to DAAF Control Panel."
}

# ============================================================================
# Handlers: Web services (options 2, 3, 4)
# ============================================================================

handle_notebooks() {
    echo ""
    echo "Starting notebook browser..."

    if check_port 2718; then
        echo "  Marimo is already running."
    else
        docker compose exec -d daaf-docker \
            bash /daaf/scripts/launch_marimo.sh --background </dev/null 2>/dev/null

        local elapsed=0
        while [ "$elapsed" -lt 10 ]; do
            if check_port 2718; then break; fi
            sleep 1
            elapsed=$((elapsed + 1))
        done

        if ! check_port 2718; then
            echo "  ${YELLOW}Server may still be starting. Try the URL in a moment.${RESET}"
        else
            echo "  Server started."
        fi
    fi

    local url="http://localhost:2718"
    echo ""
    echo "  ${CYAN}${url}${RESET}"
    echo ""
    open_url "$url"
}

handle_vscode() {
    echo ""
    echo "Starting VS Code browser..."

    if check_port 2720; then
        echo "  VS Code is already running."
    else
        docker compose exec -d daaf-docker \
            bash /daaf/scripts/launch_code_server.sh --background </dev/null 2>/dev/null

        local elapsed=0
        while [ "$elapsed" -lt 10 ]; do
            if check_port 2720; then break; fi
            sleep 1
            elapsed=$((elapsed + 1))
        done

        if ! check_port 2720; then
            echo "  ${YELLOW}Server may still be starting. Try the URL in a moment.${RESET}"
        else
            echo "  Server started."
        fi
    fi

    local url="http://localhost:2720"
    echo ""
    echo "  ${CYAN}${url}${RESET}"
    echo ""
    open_url "$url"
}

handle_logs() {
    echo ""
    echo "Discovering available log sources..."

    local sources
    sources=$(docker compose exec -T daaf-docker \
        bash /daaf/scripts/discover_log_sources.sh </dev/null 2>/dev/null | tr -d '\r') || sources=""

    if [ -z "$sources" ]; then
        echo "  No session logs found. Run a DAAF session first to generate logs."
        return
    fi

    local -a paths=()
    local -a labels=()

    while IFS='|' read -r source_id session_count; do
        [ -z "$source_id" ] && continue
        session_count=$(echo "$session_count" | tr -d '[:space:]')
        if [ "$source_id" = "ARCHIVE" ]; then
            paths+=("ARCHIVE")
            labels+=("Full session archive ($session_count sessions)")
        else
            local folder_name
            folder_name=$(basename "$source_id")
            local display_date="${folder_name%%_*}"
            local display_title
            display_title=$(echo "${folder_name#*_}" | tr '_' ' ')
            paths+=("$source_id")
            labels+=("$display_date $display_title ($session_count sessions)")
        fi
    done <<< "$sources"

    if [ "${#labels[@]}" -eq 0 ]; then
        echo "  No session logs found. Run a DAAF session first to generate logs."
        return
    fi

    echo ""
    echo "  Select a log source:"
    echo ""
    for i in "${!labels[@]}"; do
        printf "    %d) %s\n" "$((i + 1))" "${labels[$i]}"
    done
    echo ""
    echo "    0) Back to main menu"
    echo ""

    local choice
    read -r -p "  Enter choice: " choice

    if [ "$choice" = "0" ] || [ -z "$choice" ]; then
        return
    fi

    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#paths[@]}" ]; then
        echo "  Invalid selection."
        return
    fi

    local selected="${paths[$((choice - 1))]}"
    local url

    echo ""
    echo "  Generating session manifest..."
    if [ "$selected" = "ARCHIVE" ]; then
        docker compose exec -T daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh --archive --no-serve \
            </dev/null 2>/dev/null || true
        url="http://localhost:2719/scripts/log_viewer.html?manifest=.claude/logs/sessions/session_manifest.json"
    else
        docker compose exec -T daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh "$selected" --no-serve \
            </dev/null 2>/dev/null || true
        local rel_path="${selected#/daaf/}"
        url="http://localhost:2719/scripts/log_viewer.html?manifest=${rel_path}/logs/session_manifest.json"
    fi

    # Ensure log viewer server is running
    if ! check_port 2719; then
        echo "  Starting log viewer server..."
        docker compose exec -d daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh --archive --background \
            </dev/null 2>/dev/null

        local elapsed=0
        while [ "$elapsed" -lt 10 ]; do
            if check_port 2719; then break; fi
            sleep 1
            elapsed=$((elapsed + 1))
        done
    fi

    echo ""
    echo "  ${CYAN}${url}${RESET}"
    echo ""
    open_url "$url"
}

# ============================================================================
# Handlers: Maintenance (options 6-9)
# ============================================================================

handle_backup() {
    echo ""
    DAAF_NESTED=1 bash "${SCRIPT_DIR}/backup_daaf.sh"
    echo ""
    echo "Returned to DAAF Control Panel."
}

handle_restore() {
    echo ""
    DAAF_NESTED=1 bash "${SCRIPT_DIR}/restore_from_backup.sh"
    echo ""
    echo "Returned to DAAF Control Panel."
}

handle_update() {
    echo ""
    DAAF_NESTED=1 bash "${SCRIPT_DIR}/update_daaf.sh"
    echo ""
    echo "Returned to DAAF Control Panel."
}

handle_rebuild() {
    echo ""
    DAAF_NESTED=1 bash "${SCRIPT_DIR}/rebuild_daaf.sh"
    echo ""
    echo "Returned to DAAF Control Panel."
}

# ============================================================================
# Handler: Stop Services (option 10)
# ============================================================================

handle_stop_services() {
    echo ""

    local svc_running=false
    local marimo_running=false
    local vscode_running=false
    local logs_running=false

    if check_port 2718; then marimo_running=true; svc_running=true; fi
    if check_port 2719; then logs_running=true; svc_running=true; fi
    if check_port 2720; then vscode_running=true; svc_running=true; fi

    if [ "$svc_running" = false ]; then
        echo "  No web services are currently running."
        return
    fi

    echo "  Running services:"
    if [ "$marimo_running" = true ]; then
        echo "    ${GREEN}●${RESET} Notebooks    (port 2718)"
    fi
    if [ "$logs_running" = true ]; then
        echo "    ${GREEN}●${RESET} Log Viewer   (port 2719)"
    fi
    if [ "$vscode_running" = true ]; then
        echo "    ${GREEN}●${RESET} VS Code      (port 2720)"
    fi
    echo ""
    echo "    1) Stop all"
    echo "    0) Back"
    echo ""

    local choice
    read -r -p "  Enter choice: " choice

    if [ "$choice" = "1" ]; then
        echo "  Stopping services..."
        docker compose exec -T daaf-docker bash -c '
            for port in 2718 2719 2720; do
                pid=$(ss -tlnp 2>/dev/null | grep ":${port} " | sed -n "s/.*pid=\([0-9]*\).*/\1/p" | head -1)
                if [ -n "$pid" ]; then
                    kill "$pid" 2>/dev/null && echo "    Stopped service on port $port (PID $pid)"
                fi
            done
        ' </dev/null 2>/dev/null || true
        echo "  Done."
    fi
}

# ============================================================================
# Handler: Help (option h)
# ============================================================================

handle_help() {
    echo ""
    echo "=========================================="
    echo "  ${BOLD}DAAF Control Panel -- Help${RESET}"
    echo "=========================================="
    echo ""
    echo "  ${BOLD}LAUNCH${RESET}"
    echo ""
    echo "  ${CYAN}1) Start Claude Code${RESET}"
    echo "     Launch an interactive Claude Code session inside the DAAF"
    echo "     container. Type /exit within Claude to return to this menu."
    echo ""
    echo "  ${CYAN}2) Browse Notebooks${RESET}"
    echo "     Open the marimo notebook browser (port 2718). Browse, open,"
    echo "     create, and edit research notebooks across all projects."
    echo ""
    echo "  ${CYAN}3) Browse Files (VS Code)${RESET}"
    echo "     Open code-server (port 2720) for browser-based file browsing"
    echo "     and editing. Useful for reviewing scripts and data files."
    echo ""
    echo "  ${CYAN}4) View Session Logs${RESET}"
    echo "     Browse session transcripts from previous DAAF sessions."
    echo "     Select a project or the full archive to view logs."
    echo ""
    echo "  ${CYAN}5) Open Container Shell${RESET}"
    echo "     Drop into a bash shell inside the DAAF container."
    echo "     Type 'exit' to return to this menu."
    echo ""
    echo "  ${BOLD}MANAGE${RESET}"
    echo ""
    echo "  ${CYAN}6) Create Backup${RESET}"
    echo "     Create a timestamped backup of your DAAF Docker volume."
    echo "     Backups are saved in the current directory."
    echo ""
    echo "  ${CYAN}7) Restore from Backup${RESET}"
    echo "     Restore a previous backup to the DAAF Docker volume."
    echo "     You will be prompted to select which backup to restore."
    echo ""
    echo "  ${CYAN}8) Check for Updates${RESET}"
    echo "     Check for and apply updates to the DAAF framework."
    echo ""
    echo "  ${CYAN}9) Rebuild Container${RESET}"
    echo "     Rebuild the DAAF Docker container from the latest image."
    echo "     Your data volume is preserved during rebuilds."
    echo ""
    echo "  ${CYAN}10) Stop Web Services${RESET}"
    echo "      Stop any running web services (notebooks, log viewer,"
    echo "      VS Code) without stopping the container itself."
    echo ""
    echo "  ${BOLD}OTHER${RESET}"
    echo ""
    echo "  ${CYAN}h) Help${RESET}  -- Show this help screen"
    echo "  ${CYAN}q) Quit${RESET}  -- Exit the control panel"
    echo ""
    read -r -p "  Press Enter to continue... "
}

# ============================================================================
# Handler: Quit (option q)
# ============================================================================

handle_quit() {
    echo ""
    echo "Goodbye!"
    exit 0
}

# ============================================================================
# Main Loop
# ============================================================================

while true; do
    gather_status
    display_menu
    read_choice
    dispatch_choice "$CHOICE"
done
