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

# -E propagates the ERR trap into functions and command substitutions so an
# unexpected failure anywhere is reported rather than silently aborting.
set -Eeuo pipefail

# --- Source shared library ---
# Use BASH_SOURCE (not $0) so the library resolves correctly whether this file
# is executed directly or sourced (e.g., by the bats test harness, where $0 is
# the test runner's path rather than this script's).
DAAF_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${DAAF_LIB_DIR}/daaf_lib.sh"
setup_colors
SCRIPT_DIR="$DAAF_LIB_DIR"

# --- Multi-instance settings ---
# Bridge environment_settings.txt's DAAF_* keys into the environment so
# `docker compose` interpolation resolves the project name and published host
# ports. See load_daaf_settings in daaf_lib.sh for the full rationale.
load_daaf_settings

# Host-facing ports for browser URLs and status display. These are the ports
# published on the HOST (docker-compose.yml maps them to the fixed container
# ports 2718/2719/2720). Default to the container ports when unset so existing
# single-instance installs behave identically.
DAAF_PORT_MARIMO="${DAAF_PORT_MARIMO:-2718}"
DAAF_PORT_LOGVIEWER="${DAAF_PORT_LOGVIEWER:-2719}"
DAAF_PORT_VSCODE="${DAAF_PORT_VSCODE:-2720}"

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"compose ps -q daaf-docker"*) echo "abc123" ;;
            *"compose ps --status running"*"--format"*) echo "daaf-docker" ;;
            *"compose exec"*"PORT:"*) echo "" ;;
            *"compose exec"*"/proc/net/tcp"*) echo "" ;;
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

# --- Preflight ---
# Skipped under DAAF_TEST_MODE so the test harness can source this file (to load
# function definitions further below) without a real Docker daemon present.
if [ "${DAAF_TEST_MODE:-}" != "1" ]; then
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
fi

# --- Signal / error handling ---
# Registered only outside test mode so sourcing this file for tests does not
# install an EXIT trap into the harness shell.
if [ "${DAAF_TEST_MODE:-}" != "1" ]; then
    trap 'echo ""; echo "Goodbye!"; exit 0' INT TERM

    # Any unexpected non-zero command (one not already guarded by `if`/`||`)
    # trips the ERR trap. We print a diagnostic line — script, line number, and
    # the failing command — so a failure is never silent. Important for users
    # who launch the panel by double-clicking in Terminal, where the window
    # would otherwise close instantly on an uncaught error.
    trap 'ec=$?; echo "" >&2; echo "ERROR: DAAF Control Panel hit an unexpected failure." >&2; echo "  Location: $(basename "$0"), line ${LINENO} (exit ${ec})" >&2; echo "  Command:  ${BASH_COMMAND}" >&2; echo "  This is a bug — please report it. The panel will now exit." >&2' ERR

    # On any error exit, pause so a double-clicked Terminal window does not
    # vanish before the diagnostic above can be read. Skips the clean-quit path
    # (exit 0), non-interactive contexts, and dry-run runs.
    trap 'ec=$?; if [ "$ec" -ne 0 ] && [ -t 0 ] && [ "${DAAF_DRY_RUN:-}" != "1" ]; then read -r -p "Press Enter to close... " _ || true; fi' EXIT
fi

# ============================================================================
# Status Gathering
# ============================================================================

gather_status() {
    local tmpdir
    tmpdir=$(mktemp -d)

    # Check if container is running first. `docker compose ps -q daaf-docker`
    # prints the running container's ID (empty when stopped), derived from the
    # compose project rather than a hardcoded container name.
    local running_cid
    running_cid=$(docker compose ps -q daaf-docker 2>/dev/null || true)

    if [ -z "$running_cid" ]; then
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

        # Parallel docker exec calls for container-side info.
        # The ports probe reads /proc/net/tcp{,6} (not `ss`, which is not
        # installed in the image) and emits one "PORT:<n>" line per listening
        # port among 2718/2719/2720. Column 2 is HEXIP:HEXPORT and column 4 is
        # the socket state (0A = LISTEN); we match each target port by its
        # uppercase 4-hex-digit form.
        docker compose exec -T daaf-docker git -C /daaf describe --tags --always \
            </dev/null 2>/dev/null > "$tmpdir/version" &
        docker compose exec -T daaf-docker git -C /daaf log -1 --format='%cd' --date=short \
            </dev/null 2>/dev/null > "$tmpdir/date" &
        docker compose exec -T daaf-docker git -C /daaf branch --show-current \
            </dev/null 2>/dev/null > "$tmpdir/branch" &
        docker compose exec -T daaf-docker git -C /daaf rev-list --count HEAD..origin/main \
            </dev/null 2>/dev/null > "$tmpdir/updates" &
        local ports_probe='
            for p in 2718 2719 2720; do
                ph=$(printf "%04X" "$p")
                if awk -v ph="$ph" '\''$2 ~ ":"ph"$" && $4 == "0A" {found=1} END {exit !found}'\'' \
                    /proc/net/tcp /proc/net/tcp6 2>/dev/null; then
                    echo "PORT:$p"
                fi
            done
        '
        docker compose exec -T daaf-docker bash -c "$ports_probe" \
            </dev/null 2>/dev/null > "$tmpdir/ports" &
        wait || true

        STATUS_VERSION=$(tr -d '\r' < "$tmpdir/version" 2>/dev/null || echo "unknown")
        STATUS_DATE=$(tr -d '\r' < "$tmpdir/date" 2>/dev/null || echo "")
        STATUS_BRANCH=$(tr -d '\r' < "$tmpdir/branch" 2>/dev/null || echo "detached")
        STATUS_UPDATES=$(tr -d '\r' < "$tmpdir/updates" 2>/dev/null || echo "")

        # Parse ports from the probe output (one "PORT:<n>" line per listener)
        local ports_output
        ports_output=$(tr -d '\r' < "$tmpdir/ports" 2>/dev/null || echo "")
        STATUS_PORT_2718=false
        STATUS_PORT_2719=false
        STATUS_PORT_2720=false
        if echo "$ports_output" | grep -q "PORT:2718"; then STATUS_PORT_2718=true; fi
        if echo "$ports_output" | grep -q "PORT:2719"; then STATUS_PORT_2719=true; fi
        if echo "$ports_output" | grep -q "PORT:2720"; then STATUS_PORT_2720=true; fi
    fi

    # Local backup check (no docker needed)
    # Use glob array instead of parsing ls output
    local -a backup_dirs=(./*_daaf_backup)
    if [ -e "${backup_dirs[0]}" ]; then
        # Bash 3.2 (macOS /bin/bash) does not support negative array subscripts
        # (${arr[-1]} was added in 4.3), so index the last element via arithmetic.
        # Timestamp-prefixed names sort lexicographically, so the last glob match
        # is the newest backup.
        local last_backup_dir="${backup_dirs[$((${#backup_dirs[@]} - 1))]}"
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
        echo "    ${GREEN}●${RESET} Notebooks    localhost:${DAAF_PORT_MARIMO}"
    else
        echo "    ${DIM}○${RESET} Notebooks    (not running)"
    fi
    if [ "$STATUS_PORT_2719" = true ]; then
        echo "    ${GREEN}●${RESET} Log Viewer   localhost:${DAAF_PORT_LOGVIEWER}"
    else
        echo "    ${DIM}○${RESET} Log Viewer   (not running)"
    fi
    if [ "$STATUS_PORT_2720" = true ]; then
        echo "    ${GREEN}●${RESET} VS Code      localhost:${DAAF_PORT_VSCODE}"
    else
        echo "    ${DIM}○${RESET} VS Code      (not running)"
    fi

    echo ""

    # --- Menu options ---
    echo "  ${BOLD}LAUNCH${RESET}"
    echo "    1) Start Claude Code"
    echo "    2) View Marimo Notebooks (Python)"
    echo "    3) Browse Files (VS Code)"
    echo "    4) View Session Logs"
    echo "    5) View Quarto Notebooks (R)"
    echo "    6) Open Container Shell"

    echo ""

    echo "  ${BOLD}MANAGE${RESET}"
    echo "    7) Create Backup"
    echo "    8) Restore from Backup"
    echo "    9) Check for Updates"
    echo "   10) Rebuild Container"
    echo "   11) Stop Web Services"

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
        5)  handle_quarto ;;
        6)  handle_shell ;;
        7)  handle_backup ;;
        8)  handle_restore ;;
        9)  handle_update ;;
        10) handle_rebuild ;;
        11) handle_stop_services ;;
        h|H) handle_help ;;
        q|Q) handle_quit ;;
        "") ;;  # Empty input -- just redraw
        *)  echo "  Invalid choice. Please enter a number (1-11), h, or q." ;;
    esac
}

# ============================================================================
# Handlers: Interactive (options 1, 6)
# ============================================================================

handle_claude_code() {
    echo ""
    echo "Launching Claude Code..."
    echo "(When you're done, type /exit to return to this menu)"
    echo ""
    # Guard the child exit so a non-zero return (e.g., run_daaf.sh preflight
    # failure) does not abort the panel under set -e.
    if ! DAAF_NESTED=1 bash "${SCRIPT_DIR}/run_daaf.sh"; then
        echo ""
        echo "  ${YELLOW}Claude Code session ended with an error.${RESET}"
    fi
    echo ""
    echo "Returned to DAAF Control Panel."
}

handle_shell() {
    echo ""
    echo "Opening container shell..."
    echo "(Type 'exit' to return to this menu)"
    echo ""
    if ! DAAF_NESTED=1 bash "${SCRIPT_DIR}/run_daaf.sh" bash; then
        echo ""
        echo "  ${YELLOW}Container shell ended with an error.${RESET}"
    fi
    echo ""
    echo "Returned to DAAF Control Panel."
}

# ============================================================================
# Handlers: Web services (options 2, 3, 4, 5)
# ============================================================================

handle_notebooks() {
    echo ""
    echo "Starting notebook browser..."

    # Ensure the container is up before attempting docker compose exec, so we
    # give a clear message instead of letting a failed exec surface obscurely.
    if ! ensure_container; then
        echo "  ${YELLOW}Could not start the DAAF container. Is Docker running?${RESET}"
        return
    fi

    if check_port 2718; then
        echo "  Marimo is already running."
    else
        # Capture stderr (do NOT discard) so a container-side launch failure is
        # distinguishable from a slow start. A non-zero exit returns to the menu
        # rather than aborting the panel under set -e.
        local launch_err
        launch_err=$(docker compose exec -d daaf-docker \
            bash /daaf/scripts/launch_marimo.sh --background </dev/null 2>&1) || {
            echo "  ${YELLOW}Failed to start the notebook server:${RESET}"
            echo "  ${launch_err}"
            return
        }

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

    # Browser URL uses the HOST-published port (DAAF_PORT_MARIMO); the container
    # port probed above stays fixed at 2718.
    local url="http://localhost:${DAAF_PORT_MARIMO}"
    echo ""
    echo "  ${CYAN}${url}${RESET}"
    echo ""
    open_url "$url"
}

handle_vscode() {
    echo ""
    echo "Starting VS Code browser..."

    # Ensure the container is up before attempting docker compose exec.
    if ! ensure_container; then
        echo "  ${YELLOW}Could not start the DAAF container. Is Docker running?${RESET}"
        return
    fi

    # code-server runs with --auth password; the launcher prints the password to
    # its own stdout, which is lost under `exec -d`. Mirror launch_code_server.sh's
    # default here so the menu can display it. Honor a PASSWORD override if the
    # user exported one before launching the panel.
    # Default mirrors launch_code_server.sh (PASSWORD env var overrides both).
    local vscode_password="${PASSWORD:-daaf}"

    if check_port 2720; then
        echo "  VS Code is already running."
    else
        # Capture stderr (do NOT discard) so a container-side launch failure —
        # e.g., a stale image without code-server — is visible rather than
        # masquerading as "still starting". Non-zero exit returns to the menu.
        local launch_err
        launch_err=$(docker compose exec -d daaf-docker \
            bash /daaf/scripts/launch_code_server.sh --background </dev/null 2>&1) || {
            echo "  ${YELLOW}Failed to start VS Code (code-server):${RESET}"
            echo "  ${launch_err}"
            return
        }

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

    # Browser URL uses the HOST-published port (DAAF_PORT_VSCODE); the container
    # port probed above stays fixed at 2720.
    local url="http://localhost:${DAAF_PORT_VSCODE}"
    echo ""
    echo "  ${CYAN}${url}${RESET}"
    echo "  ${BOLD}Password:${RESET} ${vscode_password}"
    echo ""
    open_url "$url"
}

handle_logs() {
    echo ""
    echo "Discovering available log sources..."

    # Ensure the container is up before attempting docker compose exec.
    if ! ensure_container; then
        echo "  ${YELLOW}Could not start the DAAF container. Is Docker running?${RESET}"
        return
    fi

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
    local manifest_err

    # --- Step 1: Generate the manifest for the SELECTED source ---
    # Capture stderr so a generation failure (e.g., empty archive) produces an
    # accurate message instead of a dead URL. A failure here returns to the menu.
    echo ""
    echo "  Generating session manifest..."
    if [ "$selected" = "ARCHIVE" ]; then
        manifest_err=$(docker compose exec -T daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh --archive --no-serve \
            </dev/null 2>&1) || {
            echo "  ${YELLOW}Manifest generation failed for the full archive.${RESET}"
            echo "  ${YELLOW}The specific error is in the output above.${RESET}"
            echo "  ${manifest_err}"
            echo "  ${YELLOW}A specific project source may still work -- try selecting"
            echo "  one project instead of the full archive.${RESET}"
            return
        }
        url="http://localhost:${DAAF_PORT_LOGVIEWER}/scripts/log_viewer.html?manifest=.claude/logs/sessions/session_manifest.json"
    else
        manifest_err=$(docker compose exec -T daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh "$selected" --no-serve \
            </dev/null 2>&1) || {
            echo "  ${YELLOW}Could not generate the session manifest:${RESET}"
            echo "  ${manifest_err}"
            return
        }
        local rel_path="${selected#/daaf/}"
        url="http://localhost:${DAAF_PORT_LOGVIEWER}/scripts/log_viewer.html?manifest=${rel_path}/logs/session_manifest.json"
    fi

    # --- Step 2: Ensure the log viewer server is running ---
    # Start the server against the SELECTED source, not always --archive. The
    # old code always launched with --archive, which exits before serving when
    # the DAAF-wide archive is empty — leaving a valid project selection with a
    # dead URL. Serving from the chosen source decouples the two.
    if ! check_port 2719; then
        echo "  Starting log viewer server..."
        local -a serve_args=()
        if [ "$selected" = "ARCHIVE" ]; then
            serve_args=(--archive --background)
        else
            serve_args=("$selected" --background)
        fi
        local serve_err
        serve_err=$(docker compose exec -d daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh "${serve_args[@]}" \
            </dev/null 2>&1) || {
            echo "  ${YELLOW}Could not start the log viewer server:${RESET}"
            echo "  ${serve_err}"
            return
        }

        local elapsed=0
        while [ "$elapsed" -lt 10 ]; do
            if check_port 2719; then break; fi
            sleep 1
            elapsed=$((elapsed + 1))
        done

        if ! check_port 2719; then
            echo "  ${YELLOW}Server may still be starting. Try the URL in a moment.${RESET}"
        fi
    fi

    echo ""
    echo "  ${CYAN}${url}${RESET}"
    echo ""
    open_url "$url"
}

# ============================================================================
# Handler: View Quarto Notebooks (option 5)
# ============================================================================

# view_quarto.sh is a HOST sibling script (like backup/restore/update), not a
# container-side launcher: it renders a Quarto .qmd to self-contained HTML inside
# the container, copies it out, and opens it in the browser. With no argument it
# lists the available notebooks and exits, which is what this menu entry drives.
# Delegate to it with DAAF_NESTED=1 (suppresses its own pause-on-exit trap) so
# control returns cleanly to the menu, mirroring run_delegate's guarded child call.
handle_quarto() {
    echo ""
    echo "Discovering Quarto notebooks..."
    if DAAF_NESTED=1 bash "${SCRIPT_DIR}/view_quarto.sh"; then
        echo ""
        echo "Returned to DAAF Control Panel."
    else
        local ec=$?
        echo ""
        echo "  ${YELLOW}view_quarto.sh exited without completing (code ${ec}).${RESET}"
        echo "Returned to DAAF Control Panel."
    fi
}

# ============================================================================
# Handlers: Maintenance (options 7-10)
# ============================================================================

# run_delegate <script-name> — run a delegated child script with DAAF_NESTED=1.
# Guards the child's exit code: a non-zero exit (child failure, user abort, or
# the graceful "no backups found" case in restore_from_backup.sh) prints a clear
# message and returns to the menu rather than letting `set -e` kill the panel.
run_delegate() {
    local script_name="$1"
    echo ""
    if DAAF_NESTED=1 bash "${SCRIPT_DIR}/${script_name}"; then
        echo ""
        echo "Returned to DAAF Control Panel."
    else
        local ec=$?
        echo ""
        echo "  ${YELLOW}${script_name} exited without completing (code ${ec}).${RESET}"
        echo "Returned to DAAF Control Panel."
    fi
}

handle_backup() {
    run_delegate backup_daaf.sh
}

handle_restore() {
    run_delegate restore_from_backup.sh
}

handle_update() {
    run_delegate update_daaf.sh
}

handle_rebuild() {
    run_delegate rebuild_daaf.sh
}

# ============================================================================
# Handler: Stop Services (option 11)
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
        # Map each listening port to its owning PID via /proc/net/tcp (inode) ->
        # /proc/*/fd (socket symlink) -> PID, then kill it. `ss` is not present
        # in the image, so we reuse the /proc pattern from generate_log_viewer.sh.
        # Surface stderr (do NOT discard) so container-side failures are visible.
        local stop_script='
            for port in 2718 2719 2720; do
                ph=$(printf "%04X" "$port")
                inode=$(awk -v ph="$ph" '\''$2 ~ ":"ph"$" && $4 == "0A" {print $10}'\'' \
                    /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -1)
                [ -z "$inode" ] && continue
                pid=$(find /proc -maxdepth 3 -path "*/fd/*" -exec ls -la {} + 2>/dev/null \
                    | grep "socket:\[$inode\]" | head -1 \
                    | sed "s|.*/proc/\([0-9]*\)/.*|\1|")
                case "$pid" in
                    ""|*[!0-9]*) continue ;;
                esac
                if kill "$pid" 2>/dev/null; then
                    echo "    Stopped service on port $port (PID $pid)"
                else
                    echo "    Could not stop service on port $port (PID $pid)"
                fi
            done
        '
        if ! docker compose exec -T daaf-docker bash -c "$stop_script" </dev/null; then
            echo "  ${YELLOW}Warning: could not reach the container to stop services.${RESET}"
        fi
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
    echo "  ${CYAN}2) View Marimo Notebooks (Python)${RESET}"
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
    echo "  ${CYAN}5) View Quarto Notebooks (R)${RESET}"
    echo "     Render a Quarto notebook (.qmd) from an R project to a"
    echo "     self-contained HTML file and open it in your browser."
    echo ""
    echo "  ${CYAN}6) Open Container Shell${RESET}"
    echo "     Drop into a bash shell inside the DAAF container."
    echo "     Type 'exit' to return to this menu."
    echo ""
    echo "  ${BOLD}MANAGE${RESET}"
    echo ""
    echo "  ${CYAN}7) Create Backup${RESET}"
    echo "     Create a timestamped backup of your DAAF Docker volume."
    echo "     Backups are saved in the current directory."
    echo ""
    echo "  ${CYAN}8) Restore from Backup${RESET}"
    echo "     Restore a previous backup to the DAAF Docker volume."
    echo "     You will be prompted to select which backup to restore."
    echo ""
    echo "  ${CYAN}9) Check for Updates${RESET}"
    echo "     Check for and apply updates to the DAAF framework."
    echo ""
    echo "  ${CYAN}10) Rebuild Container${RESET}"
    echo "     Rebuild the DAAF Docker container from the latest image."
    echo "     Your data volume is preserved during rebuilds."
    echo ""
    echo "  ${CYAN}11) Stop Web Services${RESET}"
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
# Skipped under DAAF_TEST_MODE: the test harness sources this file to load the
# function definitions above and drives them directly, without the menu loop.
if [ "${DAAF_TEST_MODE:-}" != "1" ]; then
    while true; do
        gather_status
        display_menu
        read_choice
        dispatch_choice "$CHOICE"
    done
fi
