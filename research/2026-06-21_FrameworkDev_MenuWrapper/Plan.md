# DAAF Control Panel — Implementation Plan

**Date:** 2026-06-21
**Work Type:** Framework Development — New Host Script + Modifications
**Status:** Draft

---

## 1. Objective

Create a unified `daaf.sh` menu wrapper ("DAAF Control Panel") that replaces the
need to remember and invoke 8+ individual host scripts. The wrapper provides:

- A status dashboard (container status, version, branch, services, last backup)
- A curated, user-friendly menu grouping all operations
- Background service management for web viewers (notebooks, vscode, logs)
- Automatic browser opening for web services
- A help system with plain-language descriptions
- A service stop option for cleaning up background viewers

Secondary goals:
- Add browser auto-open (`open_url`) to standalone viewer scripts
- Add `--background` support to container-side launcher scripts
- Create a shared function library (`daaf_lib.sh`) to avoid duplication
- Comprehensive BATS test coverage for all new and modified code

---

## 2. Architecture

### 2.1 File Map

```
scripts/host/
├── daaf.sh                    # NEW — main menu wrapper
├── daaf_lib.sh                # NEW — shared functions (open_url, colors, port_check)
├── run_daaf.sh                # MODIFY — source daaf_lib.sh for open_url
├── view_notebooks.sh          # MODIFY — add open_url call
├── run_vscode.sh              # MODIFY — add open_url call
├── view_logs.sh               # MODIFY — add open_url call
├── backup_daaf.sh             # no change
├── restore_from_backup.sh     # no change
├── update_daaf.sh             # no change
├── rebuild_daaf.sh            # no change
├── install.sh                 # MODIFY — reference daaf.sh in success message
├── migrate_daaf.sh            # MODIFY — reference daaf.sh in success message

scripts/
├── launch_marimo.sh           # MODIFY — add --background flag
├── launch_code_server.sh      # MODIFY — add --background flag
├── generate_log_viewer.sh     # MODIFY — add --background flag

tests/bash/
├── daaf.bats                  # NEW — menu wrapper tests
├── daaf_lib.bats              # NEW — shared library tests
├── run_daaf.bats              # no change expected
├── view_notebooks.bats        # MODIFY — add open_url tests
├── run_vscode.bats            # MODIFY — add open_url tests
├── view_logs.bats             # MODIFY — add open_url tests
├── install.bats               # MODIFY — test for daaf.sh reference
├── test_helper.bash           # MODIFY — add mock_open_url, mock_port_check helpers

user_reference/
├── 01_installation_and_quickstart.md  # MODIFY — document daaf.sh
```

### 2.2 Component Relationships

```
daaf.sh (menu wrapper)
    │
    ├── sources daaf_lib.sh (shared functions)
    │     ├── open_url()           — cross-platform browser open
    │     ├── setup_colors()       — tput-based with NO_COLOR respect
    │     ├── check_port()         — is a service running on port N?
    │     └── ensure_container()   — start container if not running
    │
    ├── calls existing scripts via DAAF_NESTED=1:
    │     ├── backup_daaf.sh       — runs to completion, returns to menu
    │     ├── restore_from_backup.sh — interactive, returns to menu
    │     ├── update_daaf.sh       — interactive, returns to menu
    │     ├── rebuild_daaf.sh      — runs to completion, returns to menu
    │     └── run_daaf.sh          — interactive (Claude/shell), returns to menu
    │
    └── manages services directly (does NOT call viewer .sh scripts):
          ├── Notebooks: docker compose exec [-d] ... launch_marimo.sh [--background]
          ├── VS Code:   docker compose exec [-d] ... launch_code_server.sh [--background]
          └── Logs:      discover_log_sources.sh → generate_log_viewer.sh --no-serve
                         → start log_viewer_server.py in background → open URL
```

### 2.3 Service Management Model

Services (notebooks, vscode, log viewer) are **long-running processes inside the
container**. The menu wrapper starts them in the background and opens the browser.
They persist until explicitly stopped (via the "Stop services" menu option) or
until the container itself stops.

**Start flow:**
1. Check if service is already running (port check inside container)
2. If not running: start via `docker compose exec -d` with `--background` flag
3. Wait briefly for startup (2-3 seconds with readiness polling)
4. Print URL
5. Open browser via `open_url`
6. Return to menu

**Stop flow:**
1. Check which services are running (port check)
2. Show status
3. Kill process(es) inside container via `docker compose exec`
4. Return to menu

---

## 3. Detailed Design

### 3.1 daaf_lib.sh — Shared Function Library

```bash
#!/usr/bin/env bash
# Shared functions for DAAF host scripts. Source via:
#   DAAF_LIB_DIR="$(cd "$(dirname "$0")" && pwd)"
#   source "${DAAF_LIB_DIR}/daaf_lib.sh"

# --- Color Setup ---
# Respects NO_COLOR (https://no-color.org/) and non-TTY contexts.
# Sets: RED, GREEN, YELLOW, CYAN, BOLD, DIM, RESET (empty strings when disabled)
setup_colors() { ... }

# --- Browser Open ---
# Attempts to open a URL in the default browser. Falls back to printing the URL.
# Works on macOS (open), Linux (xdg-open), and WSL (wslview).
# Returns 0 regardless of whether the browser opened (non-critical).
open_url() { ... }

# --- Port Check ---
# Checks if a service is listening on a given port inside the DAAF container.
# Usage: check_port 2718 && echo "running" || echo "not running"
check_port() { ... }

# --- Container Check ---
# Ensures the DAAF container is running. Starts it if not.
# Returns 0 on success, 1 on failure.
# Sets CONTAINER_RUNNING=true/false as a side effect.
ensure_container() { ... }
```

### 3.2 daaf.sh — Menu Wrapper

#### Top-Level Structure

```bash
#!/usr/bin/env bash
set -euo pipefail

# Source shared library
DAAF_LIB_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${DAAF_LIB_DIR}/daaf_lib.sh"

# --- Dry-Run / Test Mode Guards ---
# (standard DAAF patterns)

# --- Preflight ---
# Validate docker-compose.yml, Docker installed, Docker running

# --- Main Loop ---
while true; do
    gather_status        # container, version, branch, services, backup
    display_menu         # formatted menu with status dashboard
    read_choice          # validated input
    dispatch_choice      # route to handler function
done
```

#### Status Dashboard

```
==========================================
  DAAF Control Panel
==========================================

  Container:  ● Running
  Version:    v2.0.1 (2026-06-15)
  Branch:     main (up to date)
  Last backup: 2026-06-18

  Services:
    ● Notebooks    localhost:2718
    ● Log Viewer   localhost:2719
    ○ VS Code      (not running)
```

**Data gathering (6 docker exec calls, parallelized via background subshells):**

| Data Point | Command | Fallback |
|------------|---------|----------|
| Container status | `docker compose ps --status running` | "Stopped" |
| Version | `docker compose exec -T ... git describe --tags --always` | Short hash |
| Version date | `docker compose exec -T ... git log -1 --format='%cd' --date=short` | "(unknown)" |
| Branch | `docker compose exec -T ... git branch --show-current` | "(detached)" |
| Updates available | `docker compose exec -T ... git rev-list --count HEAD..origin/main` | Skip (show nothing) |
| Service ports | `docker compose exec -T ... ss -tlnp` (parsed for 2718/2719/2720) | All "not running" |

Last backup date: `ls -d *_daaf_backup 2>/dev/null | sort | tail -1` (local, no docker).

**Parallelization strategy:** Run the 5 container-side commands as background
subshells writing to temp files, then `wait` for all. This reduces the 5 sequential
docker exec calls (~5s) to roughly 1 parallel batch (~1.5s). The local backup check
runs simultaneously.

```bash
gather_status() {
    local tmpdir
    tmpdir=$(mktemp -d)

    # Parallel docker exec calls
    docker compose exec -T daaf-docker git -C /daaf describe --tags --always \
        </dev/null 2>/dev/null > "$tmpdir/version" &
    docker compose exec -T daaf-docker git -C /daaf log -1 --format='%cd' --date=short \
        </dev/null 2>/dev/null > "$tmpdir/date" &
    docker compose exec -T daaf-docker git -C /daaf branch --show-current \
        </dev/null 2>/dev/null > "$tmpdir/branch" &
    docker compose exec -T daaf-docker git -C /daaf rev-list --count HEAD..origin/main \
        </dev/null 2>/dev/null > "$tmpdir/updates" &
    docker compose exec -T daaf-docker bash -c "ss -tlnp 2>/dev/null | grep -oP ':(2718|2719|2720)'" \
        </dev/null 2>/dev/null > "$tmpdir/ports" &

    wait

    # Read results (with fallbacks)
    STATUS_VERSION=$(tr -d '\r' < "$tmpdir/version" 2>/dev/null || echo "unknown")
    STATUS_DATE=$(tr -d '\r' < "$tmpdir/date" 2>/dev/null || echo "")
    STATUS_BRANCH=$(tr -d '\r' < "$tmpdir/branch" 2>/dev/null || echo "detached")
    STATUS_UPDATES=$(tr -d '\r' < "$tmpdir/updates" 2>/dev/null || echo "")
    STATUS_PORTS=$(tr -d '\r' < "$tmpdir/ports" 2>/dev/null || echo "")

    # Local backup check
    STATUS_LAST_BACKUP=$(ls -d ./*_daaf_backup 2>/dev/null | sort | tail -1 | sed 's|.*/||; s|_daaf_backup||' || echo "")

    rm -rf "$tmpdir"
}
```

#### Menu Options

```
  LAUNCH
    1) Start Claude Code
       Start an interactive DAAF session with Claude

    2) Browse Notebooks
       Open the marimo notebook browser in your web browser

    3) Browse Files (VS Code)
       Open a browser-based code editor to view and edit files

    4) View Session Logs
       Browse past DAAF session transcripts in your web browser

    5) Open Container Shell
       Get direct command-line access inside the DAAF container

  MANAGE
    6) Create Backup
       Save a complete copy of all your DAAF files to a dated folder

    7) Restore from Backup
       Replace current files with a previous backup (destructive)

    8) Check for Updates
       Download and apply the latest DAAF updates

    9) Rebuild Container
       Rebuild the Docker image (needed after Dockerfile changes)

   10) Stop Web Services
       Stop any running notebook, VS Code, or log viewer servers

  OTHER
    h) Help
       Learn more about DAAF and what each option does

    q) Quit

  Enter choice:
```

**Design decisions for menu text:**
- Descriptions are complete sentences, non-technical, action-oriented
- "(destructive)" warning on Restore is intentional — surface risk early
- Number 10 (two digits) is fine — `read` handles it
- `h` and `q` are letters to distinguish from numeric actions
- No abbreviations or jargon

#### Dispatch Logic

```bash
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
        *)  echo "  Invalid choice. Please enter a number (1-10), h, or q." ;;
    esac
}
```

#### Handler: Interactive Commands (Claude Code, Shell)

```bash
handle_claude_code() {
    echo ""
    echo "Launching Claude Code..."
    echo "(When you're done, type /exit to return to this menu)"
    echo ""
    DAAF_NESTED=1 bash "${SCRIPT_DIR}/run_daaf.sh"
    echo ""
    echo "Returned to DAAF Control Panel."
    # Status will be re-gathered on next menu redraw
}
```

#### Handler: Web Services (Notebooks, VS Code)

```bash
handle_notebooks() {
    echo ""
    echo "Starting notebook browser..."

    if check_port 2718; then
        echo "  Marimo is already running."
    else
        docker compose exec -d daaf-docker \
            bash /daaf/scripts/launch_marimo.sh --background </dev/null 2>/dev/null

        # Poll for readiness (max 10 seconds)
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
```

#### Handler: Session Logs (Sub-Menu)

```bash
handle_logs() {
    echo ""
    echo "Discovering available log sources..."

    local sources
    sources=$(docker compose exec -T daaf-docker \
        bash /daaf/scripts/discover_log_sources.sh </dev/null 2>/dev/null | tr -d '\r')

    if [ -z "$sources" ]; then
        echo "  No session logs found. Run a DAAF session first to generate logs."
        return
    fi

    # Build arrays from pipe-delimited output
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

    # Present sub-menu
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

    # Generate manifest (non-blocking)
    echo ""
    echo "  Generating session manifest..."
    if [ "$selected" = "ARCHIVE" ]; then
        docker compose exec -T daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh --archive --no-serve \
            </dev/null 2>/dev/null
        url="http://localhost:2719/scripts/log_viewer.html?manifest=.claude/logs/sessions/session_manifest.json"
    else
        docker compose exec -T daaf-docker \
            bash /daaf/scripts/generate_log_viewer.sh "$selected" --no-serve \
            </dev/null 2>/dev/null
        local rel_path="${selected#/daaf/}"
        url="http://localhost:2719/scripts/log_viewer.html?manifest=${rel_path}/logs/session_manifest.json"
    fi

    # Ensure server is running
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
```

#### Handler: Stop Services

```bash
handle_stop_services() {
    echo ""

    local svc_running=false
    local marimo_running=false vscode_running=false logs_running=false

    if check_port 2718; then marimo_running=true; svc_running=true; fi
    if check_port 2719; then logs_running=true; svc_running=true; fi
    if check_port 2720; then vscode_running=true; svc_running=true; fi

    if [ "$svc_running" = false ]; then
        echo "  No web services are currently running."
        return
    fi

    echo "  Running services:"
    $marimo_running && echo "    ${GREEN}●${RESET} Notebooks    (port 2718)"
    $logs_running   && echo "    ${GREEN}●${RESET} Log Viewer   (port 2719)"
    $vscode_running && echo "    ${GREEN}●${RESET} VS Code      (port 2720)"
    echo ""
    echo "    1) Stop all"
    echo "    0) Back"
    echo ""

    local choice
    read -r -p "  Enter choice: " choice

    if [ "$choice" = "1" ]; then
        echo "  Stopping services..."
        # Kill by port — find PIDs listening on the known ports and kill them
        docker compose exec -T daaf-docker bash -c '
            for port in 2718 2719 2720; do
                PORT_HEX=$(printf "%04X" "$port")
                INODE=$(awk -v ph="$PORT_HEX" '\''$2 ~ ":"ph"$" && $4 == "0A" {print $10}'\'' /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -1)
                [ -z "$INODE" ] && continue
                PID=$(find /proc -maxdepth 3 -path "*/fd/*" -exec ls -la {} + 2>/dev/null \
                    | grep "socket:\[$INODE\]" | head -1 \
                    | sed "s|.*/proc/\([0-9]*\)/.*|\1|")
                [ -n "$PID" ] && kill "$PID" 2>/dev/null && echo "  Stopped service on port $port (PID $PID)"
            done
        ' </dev/null 2>/dev/null || true
        echo "  Done."
    fi
}
```

#### Handler: Help

```bash
handle_help() {
    echo ""
    echo "${BOLD}About DAAF${RESET}"
    echo ""
    echo "  DAAF (Data Analyst Augmentation Framework) is a structured research"
    echo "  environment that helps you produce rigorous, reproducible data analyses"
    echo "  with Claude as your AI research partner."
    echo ""
    echo "  Everything runs inside a Docker container, so your system stays clean"
    echo "  and your work is portable and backed up."
    echo ""
    echo "${BOLD}What each option does:${RESET}"
    echo ""
    echo "  ${CYAN}1) Start Claude Code${RESET}"
    echo "     Opens an interactive session where you describe your research"
    echo "     question and DAAF guides you through the analysis step by step."
    echo "     Type /exit inside Claude Code to return to this menu."
    echo ""
    echo "  ${CYAN}2) Browse Notebooks${RESET}"
    echo "     Opens marimo (a Python notebook tool) in your web browser."
    echo "     Browse, view, and edit the notebooks produced by your analyses."
    echo "     Runs in the background — you can use it alongside Claude Code."
    echo ""
    echo "  ${CYAN}3) Browse Files (VS Code)${RESET}"
    echo "     Opens a browser-based VS Code editor so you can view and edit"
    echo "     any file in the DAAF container. Useful for reviewing scripts,"
    echo "     reading reports, or making manual edits. Password: daaf"
    echo ""
    echo "  ${CYAN}4) View Session Logs${RESET}"
    echo "     Opens an interactive timeline of past DAAF sessions. See what"
    echo "     happened, what files were created, and review the full conversation"
    echo "     history. Runs in the background alongside Claude Code."
    echo ""
    echo "  ${CYAN}5) Open Container Shell${RESET}"
    echo "     Drops you into a Linux command line inside the DAAF container."
    echo "     For advanced users who want to run commands directly."
    echo "     Type 'exit' to return to this menu."
    echo ""
    echo "  ${CYAN}6) Create Backup${RESET}"
    echo "     Makes a complete copy of all your DAAF files (research data,"
    echo "     scripts, notebooks, everything) into a dated folder on your"
    echo "     computer. Quick and safe — do this before major changes."
    echo ""
    echo "  ${CYAN}7) Restore from Backup${RESET}"
    echo "     Replaces everything in DAAF with a previous backup. This is"
    echo "     destructive — current files are erased first. You'll be asked"
    echo "     to confirm before anything happens."
    echo ""
    echo "  ${CYAN}8) Check for Updates${RESET}"
    echo "     Downloads the latest DAAF improvements and applies them."
    echo "     Your research files are never affected by updates. If there"
    echo "     are conflicts with your changes, you'll be walked through them."
    echo ""
    echo "  ${CYAN}9) Rebuild Container${RESET}"
    echo "     Rebuilds the Docker image from the latest Dockerfile. Only"
    echo "     needed when the Dockerfile changes (the updater will tell you)."
    echo "     Takes a few minutes."
    echo ""
    echo "  ${CYAN}10) Stop Web Services${RESET}"
    echo "     Stops any notebook, VS Code, or log viewer servers running in"
    echo "     the background. They'll also stop automatically when you shut"
    echo "     down the Docker container."
    echo ""
    echo "  For more information, see the full documentation inside the container:"
    echo "  /daaf/user_reference/01_installation_and_quickstart.md"
    echo ""
    echo "  Press Enter to return to the menu."
    read -r
}
```

### 3.3 Launcher Script Modifications

#### --background Flag Pattern (launch_marimo.sh, launch_code_server.sh)

Add argument parsing for `--background`:

```bash
BACKGROUND=false

# In argument parsing loop:
--background)
    BACKGROUND=true
    shift
    ;;
```

At the server launch point, replace direct `exec`:

```bash
if [ "$BACKGROUND" = true ]; then
    # Start in background, exit immediately
    nohup <server_command> > /dev/null 2>&1 &
    disown
    echo "Server started in background (PID $!)."
    echo "  URL: http://localhost:$PORT"
    exit 0
else
    # Original foreground behavior
    echo "Press Ctrl+C to stop the server."
    exec <server_command>
fi
```

#### generate_log_viewer.sh --background

Same pattern, but applied to the `python3 log_viewer_server.py` invocation:

```bash
if [ "$BACKGROUND" = true ]; then
    if [ "$ARCHIVE" = true ]; then
        nohup python3 "$SCRIPT_DIR/log_viewer_server.py" \
            --port "$PORT" --root "$REPO_ROOT" --archive --logs-dir "$LOGS_DIR" \
            > /dev/null 2>&1 &
    else
        nohup python3 "$SCRIPT_DIR/log_viewer_server.py" \
            --port "$PORT" --root "$REPO_ROOT" --project-path "$PROJECT_PATH" \
            > /dev/null 2>&1 &
    fi
    disown
    echo "Server started in background (PID $!)."
    echo "  URL: http://localhost:$PORT/$VIEWER_URL"
    exit 0
fi
```

### 3.4 Standalone Viewer Script Modifications

#### view_notebooks.sh, run_vscode.sh, view_logs.sh

Add `open_url` call after the docker compose exec returns (which happens
when the server is already running or after user Ctrl+C's a fresh server):

```bash
# At the top, source the shared library:
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/daaf_lib.sh" ]; then
    source "${SCRIPT_DIR}/daaf_lib.sh"
    setup_colors
fi

# After the docker compose exec call that prints the URL:
if [ -f "${SCRIPT_DIR}/daaf_lib.sh" ]; then
    open_url "http://localhost:${PORT:-2718}"
fi
```

For `view_logs.sh`, the URL is dynamic. We'll capture it by parsing stdout:

```bash
# Capture output while still displaying it
OUTPUT=$(docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh ... | tee /dev/stderr)

# Extract URL
VIEWER_URL=$(echo "$OUTPUT" | grep -oP 'http://localhost:[0-9]+/\S+' | head -1)
if [ -n "$VIEWER_URL" ] && [ -f "${SCRIPT_DIR}/daaf_lib.sh" ]; then
    open_url "$VIEWER_URL"
fi
```

### 3.5 install.sh and migrate_daaf.sh Updates

Add `daaf.sh` to the success message script listing and to the download list:

```bash
# In the download section:
curl -fsSL "${RAW_BASE}/scripts/host/daaf.sh"      -o "${INSTALL_DIR}/daaf.sh"
curl -fsSL "${RAW_BASE}/scripts/host/daaf_lib.sh"   -o "${INSTALL_DIR}/daaf_lib.sh"

# In the success message:
echo "  bash daaf.sh                    DAAF Control Panel (recommended)"
echo "  bash run_daaf.sh               Launch Claude Code directly"
# ... (existing scripts) ...
```

### 3.6 Signal Handling

The main menu loop needs clean signal handling:

```bash
# Ctrl+C during menu should exit cleanly
trap 'echo ""; echo "Goodbye!"; exit 0' INT TERM

# Ctrl+C during a nested script is handled by the nested script itself
# (DAAF_NESTED=1 suppresses the exit trap, and the nested script's own
# signal handling takes over)
```

When a nested interactive script (Claude Code, shell) is running, Ctrl+C is
handled by that script. When it exits, the menu loop resumes naturally.

---

## 4. Testing Plan

### 4.1 Test Infrastructure Updates

**test_helper.bash additions:**

```bash
# Mock for open_url (prevents actual browser launches in tests)
mock_open_url() {
    export OPENED_URLS=()
    open_url() {
        OPENED_URLS+=("$1")
    }
    export -f open_url
}

# Mock for check_port
mock_port_check() {
    export MOCK_PORT_RESPONSES=""  # Format: "2718:yes 2719:no 2720:yes"
    check_port() {
        local port="$1"
        if echo "${MOCK_PORT_RESPONSES}" | grep -q "${port}:yes"; then
            return 0
        fi
        return 1
    }
    export -f check_port
}

# Mock for ss command output (used by status gathering)
mock_ss() {
    ss() {
        echo "${MOCK_SS_OUTPUT:-}"
    }
    export -f ss
}
```

### 4.2 tests/bash/daaf_lib.bats (~12 tests)

```
Syntax
  ✓ daaf_lib.sh parses without errors

Colors
  ✓ setup_colors sets color variables when stdout is a TTY
  ✓ setup_colors sets empty variables when NO_COLOR is set
  ✓ setup_colors sets empty variables when stdout is not a TTY

Browser Open
  ✓ open_url calls 'open' on macOS (mock test)
  ✓ open_url calls 'xdg-open' on Linux (mock test)
  ✓ open_url calls 'wslview' on WSL (mock test)
  ✓ open_url succeeds silently when no opener is available
  ✓ open_url does not fail on invalid URL (non-critical function)

Port Check
  ✓ check_port returns 0 when service is listening
  ✓ check_port returns 1 when port is free
  ✓ check_port handles docker exec failure gracefully
```

### 4.3 tests/bash/daaf.bats (~39 tests)

```
Syntax
  ✓ daaf.sh parses without errors

Preflight
  ✓ fails when docker-compose.yml is missing
  ✓ fails when docker command is not found
  ✓ fails when Docker daemon is not running

Status Gathering
  ✓ extracts container running status from docker compose ps
  ✓ extracts version from git describe output
  ✓ extracts version date from git log output
  ✓ extracts branch name from git branch output
  ✓ detects available updates from rev-list count
  ✓ shows "up to date" when 0 updates available
  ✓ detects running services from port scan
  ✓ shows last backup date from backup folders
  ✓ handles missing backup folders gracefully
  ✓ handles container-not-running (skip git commands, show "Stopped")

Menu Display
  ✓ displays all 10 numbered options plus h and q
  ✓ displays user-friendly descriptions for each option

Input Handling
  ✓ accepts single-digit input (1-9)
  ✓ accepts double-digit input (10)
  ✓ accepts letter input (h, q, H, Q)
  ✓ rejects non-numeric non-letter input
  ✓ rejects out-of-range numbers
  ✓ rejects empty input gracefully

Dispatch Routing
  ✓ option 1 calls run_daaf.sh with DAAF_NESTED=1
  ✓ option 2 starts notebooks service
  ✓ option 3 starts vscode service
  ✓ option 4 enters log source sub-menu
  ✓ option 5 calls run_daaf.sh bash with DAAF_NESTED=1
  ✓ option 6 calls backup_daaf.sh with DAAF_NESTED=1
  ✓ option 7 calls restore_from_backup.sh with DAAF_NESTED=1
  ✓ option 8 calls update_daaf.sh with DAAF_NESTED=1
  ✓ option 9 calls rebuild_daaf.sh with DAAF_NESTED=1
  ✓ option 10 enters stop services flow

Service Management
  ✓ skips start when service already running on port
  ✓ starts service when port is free
  ✓ calls open_url after service is running

Log Viewer Sub-Menu
  ✓ shows "no logs found" when discover returns empty
  ✓ presents discovered sources as numbered options
  ✓ option 0 returns to main menu

Help
  ✓ displays descriptions for all options
  ✓ waits for Enter before returning to menu

Exit
  ✓ option q exits with code 0
  ✓ Ctrl+C exits cleanly
```

### 4.4 Modifications to Existing Test Files

**view_notebooks.bats, run_vscode.bats, view_logs.bats:**
- Add 2-3 tests each for the `open_url` integration
- Test that `open_url` is called with correct URL
- Test graceful behavior when `daaf_lib.sh` is not present (backwards compat)

**install.bats:**
- Add 1 test: success message references `daaf.sh`
- Add 1 test: `daaf.sh` and `daaf_lib.sh` are in the download list

**Launcher script tests (if they exist, or add .bats files):**
- Add 2-3 tests per launcher for `--background` flag behavior
- Test that `--background` starts server and exits immediately
- Test that without `--background`, behavior is unchanged

### 4.5 Test Execution

All tests run via the existing BATS infrastructure:

```bash
# Run all tests
./tests/libs/bats/bin/bats tests/bash/

# Run only the new tests
./tests/libs/bats/bin/bats tests/bash/daaf.bats tests/bash/daaf_lib.bats

# Dry-run smoke test (no Docker required)
DAAF_DRY_RUN=1 bash scripts/host/daaf.sh
```

---

## 5. Implementation Order

Work is organized into waves. Each wave's items are independent and can be worked
in parallel. Later waves depend on earlier ones.

### Wave 1: Foundation (no dependencies)

| # | Task | Output |
|---|------|--------|
| 1.1 | Create `daaf_lib.sh` with `open_url`, `setup_colors`, `check_port`, `ensure_container` | `scripts/host/daaf_lib.sh` |
| 1.2 | Create `tests/bash/daaf_lib.bats` with ~12 tests | `tests/bash/daaf_lib.bats` |
| 1.3 | Add mock helpers to `test_helper.bash` (`mock_open_url`, `mock_port_check`) | Modified `tests/bash/test_helper.bash` |

### Wave 2: Launcher Modifications (depends on Wave 1)

| # | Task | Output |
|---|------|--------|
| 2.1 | Add `--background` to `launch_marimo.sh` | Modified `scripts/launch_marimo.sh` |
| 2.2 | Add `--background` to `launch_code_server.sh` | Modified `scripts/launch_code_server.sh` |
| 2.3 | Add `--background` to `generate_log_viewer.sh` | Modified `scripts/generate_log_viewer.sh` |
| 2.4 | Add tests for `--background` flag (in existing or new .bats files) | Modified/new test files |

### Wave 3: Standalone Script Modifications (depends on Wave 1)

| # | Task | Output |
|---|------|--------|
| 3.1 | Add `open_url` to `view_notebooks.sh` + tests | Modified script + tests |
| 3.2 | Add `open_url` to `run_vscode.sh` + tests | Modified script + tests |
| 3.3 | Add `open_url` to `view_logs.sh` + tests | Modified script + tests |

### Wave 4: Main Menu Script (depends on Waves 1-3)

| # | Task | Output |
|---|------|--------|
| 4.1 | Create `daaf.sh` — preflight, status gathering, menu display | `scripts/host/daaf.sh` |
| 4.2 | Add dispatch handlers — interactive commands (1, 5) | Continued in `daaf.sh` |
| 4.3 | Add dispatch handlers — web services (2, 3, 4) | Continued in `daaf.sh` |
| 4.4 | Add dispatch handlers — maintenance (6, 7, 8, 9) | Continued in `daaf.sh` |
| 4.5 | Add dispatch handlers — stop services (10), help (h), quit (q) | Continued in `daaf.sh` |
| 4.6 | Create `tests/bash/daaf.bats` with ~39 tests | `tests/bash/daaf.bats` |

### Wave 5: Integration and Documentation (depends on Wave 4)

| # | Task | Output |
|---|------|--------|
| 5.1 | Update `install.sh` — add daaf.sh/daaf_lib.sh to downloads + success message | Modified `scripts/host/install.sh` |
| 5.2 | Update `install.ps1` — add daaf.sh/daaf_lib.sh mention (PS1 menu is future work) | Modified `scripts/host/install.ps1` |
| 5.3 | Update `migrate_daaf.sh` — add daaf.sh to success message + sync list | Modified `scripts/host/migrate_daaf.sh` |
| 5.4 | Update `migrate_daaf.ps1` — add daaf.sh mention | Modified `scripts/host/migrate_daaf.ps1` |
| 5.5 | Update `update_daaf.sh` — add daaf.sh/daaf_lib.sh to sync list | Modified `scripts/host/update_daaf.sh` |
| 5.6 | Update `update_daaf.ps1` — add daaf.sh/daaf_lib.sh to sync list | Modified `scripts/host/update_daaf.ps1` |
| 5.7 | Update `user_reference/01_installation_and_quickstart.md` | Modified doc |
| 5.8 | Update test files for install/migrate changes | Modified test files |

### Wave 6: Review and Polish (depends on Wave 5)

| # | Task | Output |
|---|------|--------|
| 6.1 | ShellCheck lint pass on all new/modified .sh files | Clean lint |
| 6.2 | Full BATS test suite run | All passing |
| 6.3 | DAAF_DRY_RUN=1 smoke test of daaf.sh | Clean dry run |
| 6.4 | Manual review of menu text for clarity and tone | Approved |
| 6.5 | Set executable permissions on new .sh files | `chmod +x` + `git update-index --chmod=+x` |

---

## 6. Known Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `docker compose exec -d` behavior varies across Docker Compose versions | Service might not start in background on older versions | Test with `--background` flag in launcher scripts as primary approach; `-d` as host-side fallback |
| `nohup ... & disown` in container might be killed when exec session ends | Background service stops immediately | Test this specific behavior; alternative: use container-side systemd-style process management or a PID file |
| Parallel `docker compose exec` calls may overwhelm Docker daemon | Status gathering hangs or errors | Use `wait` with timeout; fall back to sequential if parallel fails |
| `tput` not available in all terminals | Color setup fails | Already handled: check `command -v tput` before using, fall back to empty strings |
| User runs `daaf.sh` from wrong directory | Missing docker-compose.yml | Same preflight as all other scripts — clear error message |
| Ctrl+C during nested script propagates to menu | Menu exits unexpectedly | Nested scripts handle their own signals; menu traps are re-established after dispatch returns |

---

## 7. Future Work (Out of Scope)

- **`daaf.ps1`** — PowerShell equivalent of the menu wrapper. Requires careful
  design around PowerShell's process model issues (nested script freezing,
  console buffer corruption after docker exec). May benefit from WinForms GUI
  approach to avoid console issues entirely.
- **Keyboard navigation** — arrow keys + Enter instead of number input
- **Auto-update check** — background check for updates on menu startup
- **Custom port support** — let users configure ports in environment_settings.txt
- **Session resumption** — "Resume last session" shortcut in the menu
