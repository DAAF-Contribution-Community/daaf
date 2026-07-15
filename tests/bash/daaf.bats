#!/usr/bin/env bats
# ============================================================================
# Tests for daaf.sh -- DAAF Control Panel
# ============================================================================
# Tests cover syntax, preflight checks, status gathering, menu display,
# input handling, dispatch routing, service management, help, and exit.
#
# Strategy: Source daaf.sh with DAAF_TEST_MODE=1 to load functions without
# entering the main loop, then test individual functions directly. For
# end-to-end tests, pipe input to the script with DAAF_DRY_RUN=1.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    create_fake_compose_file

    # Source daaf.sh in test mode to get access to functions
    export DAAF_TEST_MODE=1
    source "$REPO_ROOT/scripts/host/daaf.sh"
    unset DAAF_TEST_MODE

    # Re-source shared library (test mode guard may skip it)
    unset _DAAF_LIB_LOADED
    source "$REPO_ROOT/scripts/host/daaf_lib.sh"
    mock_open_url
    mock_port_check
}

teardown() {
    common_teardown
}

# =========================================================================
# Tier 1 -- Syntax
# =========================================================================

@test "daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
}

# =========================================================================
# Tier 2 -- Preflight checks
# =========================================================================

@test "daaf.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    run env DAAF_DRY_RUN=1 bash -c 'echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

@test "daaf.sh fails when docker command is not found" {
    mock_no_docker
    run bash -c 'echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

@test "daaf.sh fails when Docker daemon is not running" {
    # Do NOT use DAAF_DRY_RUN here: the dry-run docker() stub returns 0 for
    # `info` and would mask the failure. Use a real docker() override that fails
    # `docker info` so the preflight check is actually exercised.
    run bash -c '
        docker() {
            case "$1" in
                info) return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"
    '
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# =========================================================================
# Tier 3 -- Script structure
# =========================================================================

@test "daaf.sh includes strict-mode preamble" {
    # The wrapper uses set -Eeuo pipefail (the -E propagates the ERR trap into
    # functions so unexpected failures are reported rather than silently aborting).
    run grep -Ec "set -E?euo pipefail" "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "daaf.sh sources daaf_lib.sh" {
    run grep -c 'source.*daaf_lib.sh' "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "daaf.sh supports DAAF_TEST_MODE guard" {
    run grep -c "DAAF_TEST_MODE" "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "daaf.sh supports DAAF_DRY_RUN" {
    run grep -c "DAAF_DRY_RUN" "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "daaf.sh does not have DAAF_NESTED pause-on-exit trap" {
    # The menu wrapper is the top-level entry point and should NOT carry the
    # child-script "pause on exit unless nested" trap (the DAAF_NESTED guard
    # around a 'Press Enter to continue' EXIT trap that child scripts use).
    # It does legitimately have an error-only pause ("Press Enter to close")
    # and a help prompt, so we assert specifically the DAAF_NESTED-guarded
    # pause pattern is absent.
    run grep -E "DAAF_NESTED.*Press Enter to continue" "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_failure
}

# =========================================================================
# Tier 4 -- Test mode sourcing
# =========================================================================

@test "daaf.sh exits cleanly when sourced with DAAF_TEST_MODE=1" {
    export DAAF_TEST_MODE=1
    run bash -c "source '${REPO_ROOT}/scripts/host/daaf.sh'"
    assert_success
}

# =========================================================================
# Tier 5 -- Status Gathering
# =========================================================================

@test "gather_status sets container to Running when container is up" {
    # Mock docker compose ps -q to return a container ID (non-empty = running)
    docker() {
        case "$*" in
            *"compose ps -q daaf-docker"*)
                echo "abc123"
                return 0
                ;;
            *"compose exec"*)
                echo ""
                return 0
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    gather_status
    [ "$STATUS_CONTAINER" = "Running" ]
}

@test "gather_status sets container to Stopped when container is down" {
    docker() {
        case "$*" in
            *"compose ps --status running"*"--format"*)
                echo ""
                return 0
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    gather_status
    [ "$STATUS_CONTAINER" = "Stopped" ]
}

@test "gather_status reads version from git describe" {
    docker() {
        case "$*" in
            *"compose ps -q daaf-docker"*)
                echo "abc123"
                return 0
                ;;
            *"compose exec"*"git"*"describe"*)
                echo "v3.1.0"
                return 0
                ;;
            *"compose exec"*)
                echo ""
                return 0
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    gather_status
    [ "$STATUS_VERSION" = "v3.1.0" ]
}

@test "gather_status shows last backup date from backup folder" {
    mkdir -p "${TEST_DIR}/2026-06-18_daaf_backup"
    gather_status
    [ "$STATUS_LAST_BACKUP" = "2026-06-18" ]
}

@test "gather_status handles no backup folders" {
    # TEST_DIR has no *_daaf_backup folders
    gather_status
    [ -z "$STATUS_LAST_BACKUP" ]
}

@test "gather_status uses latest backup when multiple exist" {
    mkdir -p "${TEST_DIR}/2026-06-15_daaf_backup"
    mkdir -p "${TEST_DIR}/2026-06-18_daaf_backup"
    mkdir -p "${TEST_DIR}/2026-06-10_daaf_backup"
    gather_status
    [ "$STATUS_LAST_BACKUP" = "2026-06-18" ]
}

# =========================================================================
# Tier 6 -- Menu Display
# =========================================================================

@test "display_menu shows exact ordered launch and manage blocks" {
    STATUS_CONTAINER="Running"
    STATUS_VERSION="v2.0.0"
    STATUS_DATE="2026-06-21"
    STATUS_BRANCH="main"
    STATUS_UPDATES="0"
    STATUS_LAST_BACKUP="2026-06-18"
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false
    BOLD=""
    RESET=""

    run display_menu
    assert_success

    local launch_block
    launch_block=$(printf '%s\n' "$output" | awk '
        /^  LAUNCH$/ { in_launch=1 }
        in_launch && /^$/ { exit }
        in_launch { print }
    ')
    local expected_launch_block
    expected_launch_block=$(printf '%s\n' \
        '  LAUNCH' \
        '    1) Start Claude Code' \
        '    2) Browse Files (VS Code)' \
        '    3) View Session Logs' \
        '    4) View Marimo Notebooks (Python)' \
        '    5) View Quarto Notebooks (R)' \
        '    6) Open Terminal in Container')
    [ "$launch_block" = "$expected_launch_block" ]

    local manage_block
    manage_block=$(printf '%s\n' "$output" | awk '
        /^  MANAGE$/ { in_manage=1 }
        in_manage && /^$/ { exit }
        in_manage { print }
    ')
    local expected_manage_block
    expected_manage_block=$(printf '%s\n' \
        '  MANAGE' \
        '    7) Create Backup' \
        '    8) Restore from Backup' \
        '    9) Check for Updates' \
        '   10) Rebuild Container' \
        '   11) Stop Web Services')
    [ "$manage_block" = "$expected_manage_block" ]

    assert_output --partial "h) Help"
    assert_output --partial "q) Quit"
}

@test "display_menu shows status dashboard" {
    STATUS_CONTAINER="Running"
    STATUS_VERSION="v2.0.0"
    STATUS_DATE="2026-06-21"
    STATUS_BRANCH="main"
    STATUS_UPDATES="0"
    STATUS_LAST_BACKUP="2026-06-18"
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false

    run display_menu
    assert_success
    assert_output --partial "DAAF Control Panel"
    assert_output --partial "Container:"
    assert_output --partial "Version:"
    assert_output --partial "Branch:"
    assert_output --partial "Services:"
}

@test "display_menu shows Running indicator when container is up" {
    STATUS_CONTAINER="Running"
    STATUS_VERSION="v2.0.0"
    STATUS_DATE=""
    STATUS_BRANCH="main"
    STATUS_UPDATES=""
    STATUS_LAST_BACKUP=""
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false

    run display_menu
    assert_output --partial "Running"
}

@test "display_menu shows Stopped indicator when container is down" {
    STATUS_CONTAINER="Stopped"
    STATUS_VERSION="--"
    STATUS_DATE=""
    STATUS_BRANCH="--"
    STATUS_UPDATES=""
    STATUS_LAST_BACKUP=""
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false

    run display_menu
    assert_output --partial "Stopped"
}

@test "display_menu shows updates available count" {
    STATUS_CONTAINER="Running"
    STATUS_VERSION="v2.0.0"
    STATUS_DATE=""
    STATUS_BRANCH="main"
    STATUS_UPDATES="5"
    STATUS_LAST_BACKUP=""
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false

    run display_menu
    assert_output --partial "5 updates available"
}

@test "display_menu shows up to date when no updates" {
    STATUS_CONTAINER="Running"
    STATUS_VERSION="v2.0.0"
    STATUS_DATE=""
    STATUS_BRANCH="main"
    STATUS_UPDATES="0"
    STATUS_LAST_BACKUP=""
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false

    run display_menu
    assert_output --partial "up to date"
}

@test "display_menu shows never when no backups" {
    STATUS_CONTAINER="Running"
    STATUS_VERSION="v2.0.0"
    STATUS_DATE=""
    STATUS_BRANCH="main"
    STATUS_UPDATES=""
    STATUS_LAST_BACKUP=""
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false

    run display_menu
    assert_output --partial "Last backup: never"
}

@test "display_menu shows section headers" {
    STATUS_CONTAINER="Running"
    STATUS_VERSION="v2.0.0"
    STATUS_DATE=""
    STATUS_BRANCH="main"
    STATUS_UPDATES=""
    STATUS_LAST_BACKUP=""
    STATUS_PORT_2718=false
    STATUS_PORT_2719=false
    STATUS_PORT_2720=false

    run display_menu
    assert_output --partial "LAUNCH"
    assert_output --partial "MANAGE"
    assert_output --partial "OTHER"
}

# =========================================================================
# Tier 7 -- Input Handling
# =========================================================================

@test "dispatch_choice routes option 1 to handle_claude_code" {
    # Override handle_claude_code to just echo a marker
    handle_claude_code() { echo "CALLED_CLAUDE_CODE"; }
    export -f handle_claude_code

    run dispatch_choice "1"
    assert_success
    assert_output --partial "CALLED_CLAUDE_CODE"
}

@test "dispatch_choice routes option 2 to handle_vscode" {
    handle_vscode() { echo "CALLED_VSCODE"; }
    export -f handle_vscode

    run dispatch_choice "2"
    assert_success
    assert_output --partial "CALLED_VSCODE"
}

@test "dispatch_choice routes option 3 to handle_logs" {
    handle_logs() { echo "CALLED_LOGS"; }
    export -f handle_logs

    run dispatch_choice "3"
    assert_success
    assert_output --partial "CALLED_LOGS"
}

@test "dispatch_choice routes option 4 to handle_notebooks" {
    handle_notebooks() { echo "CALLED_NOTEBOOKS"; }
    export -f handle_notebooks

    run dispatch_choice "4"
    assert_success
    assert_output --partial "CALLED_NOTEBOOKS"
}

@test "dispatch_choice routes option 5 to handle_quarto" {
    handle_quarto() { echo "CALLED_QUARTO"; }
    export -f handle_quarto

    run dispatch_choice "5"
    assert_success
    assert_output --partial "CALLED_QUARTO"
}

@test "dispatch_choice routes option 6 to handle_shell" {
    handle_shell() { echo "CALLED_SHELL"; }
    export -f handle_shell

    run dispatch_choice "6"
    assert_success
    assert_output --partial "CALLED_SHELL"
}

@test "dispatch_choice routes option 11 to handle_stop_services" {
    handle_stop_services() { echo "CALLED_STOP_SERVICES"; }
    export -f handle_stop_services

    run dispatch_choice "11"
    assert_success
    assert_output --partial "CALLED_STOP_SERVICES"
}

@test "dispatch_choice routes h to handle_help" {
    handle_help() { echo "CALLED_HELP"; }
    export -f handle_help

    run dispatch_choice "h"
    assert_success
    assert_output --partial "CALLED_HELP"
}

@test "dispatch_choice routes H (uppercase) to handle_help" {
    handle_help() { echo "CALLED_HELP"; }
    export -f handle_help

    run dispatch_choice "H"
    assert_success
    assert_output --partial "CALLED_HELP"
}

@test "dispatch_choice routes q to handle_quit" {
    # handle_quit calls `exit 0`; under `run` this is captured as status 0.
    run dispatch_choice "q"
    assert_success
    assert_output --partial "Goodbye"
}

@test "dispatch_choice handles empty input silently" {
    run dispatch_choice ""
    assert_success
    [ -z "$output" ]
}

@test "dispatch_choice rejects invalid input gracefully" {
    run dispatch_choice "xyz"
    assert_success
    assert_output --partial "Invalid choice"
}

@test "dispatch_choice rejects out of range number" {
    run dispatch_choice "99"
    assert_success
    assert_output --partial "Invalid choice"
}

# =========================================================================
# Tier 8 -- Dispatch Routing (delegation)
# =========================================================================

@test "handle_claude_code calls run_daaf.sh with DAAF_NESTED" {
    # Override bash to capture the call
    bash() {
        echo "BASH_CALLED: $*"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_claude_code
    assert_output --partial "run_daaf.sh"
    assert_output --partial "NESTED=1"
}

@test "handle_shell calls run_daaf.sh bash with DAAF_NESTED" {
    bash() {
        echo "BASH_CALLED: $*"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_shell
    assert_output --partial "run_daaf.sh"
    assert_output --partial "bash"
    assert_output --partial "NESTED=1"
}

@test "handle_quarto calls view_quarto.sh with DAAF_NESTED" {
    bash() {
        echo "BASH_CALLED: $*"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_quarto
    assert_output --partial "view_quarto.sh"
    assert_output --partial "NESTED=1"
}

@test "handle_backup calls backup_daaf.sh with DAAF_NESTED" {
    bash() {
        echo "BASH_CALLED: $*"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_backup
    assert_output --partial "backup_daaf.sh"
    assert_output --partial "NESTED=1"
}

@test "handle_update calls update_daaf.sh with DAAF_NESTED" {
    bash() {
        echo "BASH_CALLED: $*"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_update
    assert_output --partial "update_daaf.sh"
    assert_output --partial "NESTED=1"
}

@test "handle_restore calls restore_from_backup.sh with DAAF_NESTED" {
    bash() {
        echo "BASH_CALLED: $*"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_restore
    assert_output --partial "restore_from_backup.sh"
    assert_output --partial "NESTED=1"
}

@test "handle_rebuild calls rebuild_daaf.sh with DAAF_NESTED" {
    bash() {
        echo "BASH_CALLED: $*"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_rebuild
    assert_output --partial "rebuild_daaf.sh"
    assert_output --partial "NESTED=1"
}

# =========================================================================
# Tier 9 -- Service Management
# =========================================================================

@test "handle_notebooks skips start when service already running" {
    mock_port_check "2718:yes"

    run handle_notebooks
    assert_success
    assert_output --partial "already running"
}

@test "handle_notebooks starts service when port is free" {
    mock_port_check ""

    # Mock docker to succeed and then make port check succeed after "start"
    docker() {
        # After the exec -d call, make port respond
        mock_port_check "2718:yes"
        return 0
    }
    export -f docker

    run handle_notebooks
    assert_success
    assert_output --partial "Starting notebook browser"
}

@test "handle_notebooks calls open_url" {
    # Pin the host-published port to the default so the assertion is independent
    # of the container's environment. daaf.sh:44 reads DAAF_PORT_MARIMO from the
    # env (default 2718); a custom-port host (e.g. 3718) would otherwise leak in.
    export DAAF_PORT_MARIMO=2718
    mock_port_check "2718:yes"

    run handle_notebooks
    assert_success
    assert_output --partial "http://localhost:2718"
}

@test "handle_vscode skips start when service already running" {
    mock_port_check "2720:yes"

    run handle_vscode
    assert_success
    assert_output --partial "already running"
}

@test "handle_vscode calls open_url with port 2720" {
    # Pin the host-published port to the default so the assertion is independent
    # of the container's environment. daaf.sh:46 reads DAAF_PORT_VSCODE from the
    # env (default 2720); a custom-port host (e.g. 3720) would otherwise leak in.
    export DAAF_PORT_VSCODE=2720
    mock_port_check "2720:yes"

    run handle_vscode
    assert_success
    assert_output --partial "http://localhost:2720"
}

@test "handle_stop_services reports no services when none running" {
    mock_port_check ""

    run handle_stop_services
    assert_success
    assert_output --partial "No web services are currently running"
}

@test "handle_stop_services lists running services" {
    # Provide "0" (Back) as input to avoid blocking on read. Source daaf.sh in
    # test mode so only function definitions load (no main loop), and define an
    # inline check_port stub reporting 2718/2720 as listening (the test_helper
    # mock functions are not exported into this subshell).
    run bash -c 'echo "0" | (
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        setup_colors
        export DAAF_TEST_MODE=1
        source "'"${REPO_ROOT}"'/scripts/host/daaf.sh"
        unset DAAF_TEST_MODE
        check_port() {
            case "$1" in
                2718|2720) return 0 ;;
                *) return 1 ;;
            esac
        }
        handle_stop_services
    )' 2>/dev/null
    # Structural check: the function should show running services
    assert_output --partial "Running services"
}

# =========================================================================
# Tier 10 -- Help and Exit
# =========================================================================

@test "handle_help shows exact ordered launch headings and all management descriptions" {
    # Provide Enter as input for the "Press Enter to continue" prompt
    run bash -c 'echo "" | (
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        setup_colors
        export DAAF_TEST_MODE=1
        source "'"${REPO_ROOT}"'/scripts/host/daaf.sh"
        unset DAAF_TEST_MODE
        CYAN=""
        RESET=""
        handle_help
    )'
    assert_success

    local help_launch_headings
    help_launch_headings=$(printf '%s\n' "$output" | awk '/^  [1-6][)] / { print }')
    local expected_help_launch_headings
    expected_help_launch_headings=$(printf '%s\n' \
        '  1) Start Claude Code' \
        '  2) Browse Files (VS Code)' \
        '  3) View Session Logs' \
        '  4) View Marimo Notebooks (Python)' \
        '  5) View Quarto Notebooks (R)' \
        '  6) Open Terminal in Container')
    [ "$help_launch_headings" = "$expected_help_launch_headings" ]

    assert_output --partial "Create Backup"
    assert_output --partial "Restore from Backup"
    assert_output --partial "Check for Updates"
    assert_output --partial "Rebuild Container"
    assert_output --partial "Stop Web Services"
}

@test "handle_quit exits with code 0" {
    run handle_quit
    # exit 0 in subshell — bats records exit code
    [ "$status" -eq 0 ]
    assert_output --partial "Goodbye"
}

@test "Ctrl+D (EOF) exits cleanly" {
    # Pipe empty input (immediate EOF) to the script
    run env DAAF_DRY_RUN=1 bash -c 'true | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_output --partial "Goodbye"
}

# =========================================================================
# Tier 11 -- Dry-run end-to-end
# =========================================================================

@test "daaf.sh: dry-run quit completes successfully" {
    run env DAAF_DRY_RUN=1 bash -c 'echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_success
    assert_output --partial "DAAF Control Panel"
    assert_output --partial "Goodbye"
}

@test "daaf.sh: dry-run shows status dashboard" {
    run env DAAF_DRY_RUN=1 bash -c 'echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_success
    assert_output --partial "Container:"
    assert_output --partial "Running"
    assert_output --partial "Version:"
    assert_output --partial "v2.0.0"
}

@test "daaf.sh: dry-run shows all menu sections" {
    run env DAAF_DRY_RUN=1 bash -c 'echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_success
    assert_output --partial "LAUNCH"
    assert_output --partial "MANAGE"
    assert_output --partial "OTHER"
}

@test "daaf.sh: dry-run invalid then quit" {
    run env DAAF_DRY_RUN=1 bash -c 'printf "xyz\nq\n" | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_success
    assert_output --partial "Invalid choice"
    assert_output --partial "Goodbye"
}

@test "daaf.sh: dry-run empty input redraws menu" {
    # Send empty line then quit -- should see the menu twice
    run env DAAF_DRY_RUN=1 bash -c 'printf "\nq\n" | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_success
    # The menu banner should appear twice (initial draw + redraw)
    local count
    count=$(echo "$output" | grep -c "DAAF Control Panel" || true)
    [ "$count" -ge 2 ]
}

# =========================================================================
# Tier 12 -- Regression coverage for the Control Panel fixes
# =========================================================================

@test "daaf.sh uses Bash 3.2-safe last-element array indexing (no negative subscript)" {
    # Bash 3.2 (macOS /bin/bash) has no ${arr[-1]}; a negative subscript there
    # is a fatal "bad array subscript" error. Guard against reintroduction.
    run grep -F 'backup_dirs[-1]' "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_failure
}

@test "gather_status does not crash when a backup dir exists (3.2-safe indexing)" {
    # Regression for the L134 crash: with a seeded backup dir the last-element
    # branch executes. This must run cleanly under the arithmetic subscript.
    mkdir -p "${TEST_DIR}/2026-07-01_daaf_backup"
    run gather_status
    assert_success
}

@test "daaf.sh probes ports via /proc/net/tcp, not ss" {
    # The image has no `ss`; the probe must read /proc/net/tcp instead.
    run grep -F '/proc/net/tcp' "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
    run grep -E '\bss -tlnp\b' "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_failure
}

@test "daaf_lib.sh check_port probes via /proc/net/tcp, not ss" {
    run grep -F '/proc/net/tcp' "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_success
    run grep -E '\bss -tlnp\b' "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_failure
}

@test "handle_restore returns to menu when child exits non-zero (no set -e abort)" {
    # Simulate restore_from_backup.sh exiting 1 (e.g., no backups found). The
    # guard must catch it and return to the menu instead of killing the panel.
    bash() {
        return 1
    }
    export -f bash
    run handle_restore
    assert_success
    assert_output --partial "Returned to DAAF Control Panel"
}

@test "handle_backup returns to menu when child exits non-zero" {
    bash() { return 1; }
    export -f bash
    run handle_backup
    assert_success
    assert_output --partial "Returned to DAAF Control Panel"
}

@test "handle_vscode displays the code-server password" {
    mock_port_check "2720:yes"
    run handle_vscode
    assert_success
    assert_output --partial "Password:"
    assert_output --partial "daaf"
}

@test "handle_vscode honors a PASSWORD override in the displayed password" {
    mock_port_check "2720:yes"
    PASSWORD="hunter2" run handle_vscode
    assert_success
    assert_output --partial "hunter2"
}

@test "handle_logs starts the server against the selected source, not always --archive" {
    # The server-start command must be able to use the selected project source
    # so a project selection works even when the DAAF-wide archive is empty.
    run grep -F 'serve_args=("$selected" --background)' "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
}

@test "handle_logs surfaces manifest generation failures (no dead URL)" {
    # A manifest generation failure must produce a visible message and return,
    # rather than printing a URL that leads nowhere.
    run grep -F 'Could not generate the session manifest' "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
}

@test "service handlers call ensure_container before docker exec" {
    # Notebooks, VS Code, and Log Viewer handlers must ensure the container is
    # up before attempting docker compose exec.
    local count
    count=$(grep -c 'ensure_container' "${REPO_ROOT}/scripts/host/daaf.sh" || true)
    [ "$count" -ge 3 ]
}

@test "daaf.sh registers an ERR trap for diagnostics" {
    run grep -E "trap .* ERR" "${REPO_ROOT}/scripts/host/daaf.sh"
    assert_success
}
