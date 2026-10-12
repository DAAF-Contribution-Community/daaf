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
    # Tier 13's unreadable-settings tests chmod the fixture to 000; give it its
    # permissions back so the fixture tree is left in a normal state for removal.
    if [ -e "${TEST_DIR}/environment_settings.txt" ]; then
        chmod 644 "${TEST_DIR}/environment_settings.txt" 2>/dev/null || true
    fi
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

@test "daaf.sh exits with a permissions message when environment_settings.txt is unreadable" {
    # The startup load runs before the ERR/pause traps are registered, so the
    # panel names the file and the fix rather than ending on bash's bare line.
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    skip_unless_chmod_blocks_reads "${TEST_DIR}/environment_settings.txt"
    chmod 000 "${TEST_DIR}/environment_settings.txt"
    run env DAAF_DRY_RUN=1 bash -c 'echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_failure
    assert_output --partial "ERROR: Cannot read environment_settings.txt -- make sure it is not open in another program and that you have permission to read it."
    assert_output --partial "Fix that (or move the file aside), then start the DAAF Control Panel again."
    refute_output --partial "DAAF Control Panel hit an unexpected failure"
    refute_output --partial "Permission denied"
}

@test "daaf.sh startup does not hide a loader error that is not a failed open" {
    # The loader's open check silences only the failed open, and the startup
    # call keeps its stderr. So a bug inside the loader (here an unbound
    # variable injected just after the open check, in a copy of the library)
    # must reach the user -- it runs before the ERR/pause traps exist, so
    # nothing else would report it -- and must not be mislabeled "Cannot read".
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    mkdir -p "${TEST_DIR}/hostcopy"
    cp "${REPO_ROOT}/scripts/host/daaf.sh" "${TEST_DIR}/hostcopy/daaf.sh"
    sed 's/^    local key val line$/    local key val line; : "${_DAAF_TEST_INJECTED_UNBOUND}"/' \
        "${REPO_ROOT}/scripts/host/daaf_lib.sh" > "${TEST_DIR}/hostcopy/daaf_lib.sh"
    # The seam must have landed exactly once, or the test proves nothing.
    [ "$(grep -c '_DAAF_TEST_INJECTED_UNBOUND' "${TEST_DIR}/hostcopy/daaf_lib.sh")" -eq 1 ]
    run env -u _DAAF_TEST_INJECTED_UNBOUND DAAF_DRY_RUN=1 bash -c 'echo q | bash "'"${TEST_DIR}"'/hostcopy/daaf.sh"'
    assert_failure
    assert_output --partial "_DAAF_TEST_INJECTED_UNBOUND: unbound variable"
    refute_output --partial "Cannot read environment_settings.txt"
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
        '   11) Restart Container' \
        '   12) Stop Web Services')
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

@test "dispatch_choice routes option 11 to handle_restart" {
    handle_restart() { echo "CALLED_RESTART"; }
    export -f handle_restart

    run dispatch_choice "11"
    assert_success
    assert_output --partial "CALLED_RESTART"
}

@test "dispatch_choice routes option 12 to handle_stop_services" {
    handle_stop_services() { echo "CALLED_STOP_SERVICES"; }
    export -f handle_stop_services

    run dispatch_choice "12"
    assert_success
    assert_output --partial "CALLED_STOP_SERVICES"
}

@test "dispatch_choice names the full 1-12 range in the invalid-choice message" {
    run dispatch_choice "13"
    assert_success
    assert_output --partial "Please enter a number (1-12), h, or q."
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

@test "handle_quarto calls view_quarto.sh with no target and DAAF_NESTED" {
    bash() {
        echo "BASH_CALLED: $*"
        echo "ARGC=$#"
        echo "NESTED=${DAAF_NESTED:-unset}"
    }
    export -f bash

    run handle_quarto
    assert_success
    assert_output --partial "view_quarto.sh"
    assert_output --partial "ARGC=1"
    assert_output --partial "NESTED=1"
    assert_output --partial "Returned to DAAF Control Panel"
}

@test "handle_help explains that option 5 recursively discovers and selects Quarto notebooks" {
    run bash -c 'printf "\n" | (
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        setup_colors
        export DAAF_TEST_MODE=1
        source "'"${REPO_ROOT}"'/scripts/host/daaf.sh"
        CYAN="" RESET=""
        handle_help
    )'
    assert_success
    assert_output --partial "recursively"
    assert_output --partial "select"
    assert_output --partial "cancel"
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

@test "handle_notebooks opens the URL on the HOST-published port (PANEL_PORT_MARIMO)" {
    # Pin a NON-default host-published port (set_panel_ports in daaf.sh derives
    # PANEL_PORT_MARIMO from DAAF_PORT_MARIMO, default 2718), so a URL hardcoded
    # to the container port 2718 fails here. The container-side probe stays 2718.
    PANEL_PORT_MARIMO=3718
    mock_port_check "2718:yes"

    run handle_notebooks
    assert_success
    assert_output --partial "http://localhost:3718"
    refute_output --partial "localhost:2718"
}

@test "handle_vscode skips start when service already running" {
    mock_port_check "2720:yes"

    run handle_vscode
    assert_success
    assert_output --partial "already running"
}

@test "handle_vscode opens the URL on the HOST-published port (PANEL_PORT_VSCODE)" {
    # Pin a NON-default host-published port (set_panel_ports in daaf.sh derives
    # PANEL_PORT_VSCODE from DAAF_PORT_VSCODE, default 2720), so a URL hardcoded
    # to the container port 2720 fails here. The container-side probe stays 2720.
    PANEL_PORT_VSCODE=3720
    mock_port_check "2720:yes"

    run handle_vscode
    assert_success
    assert_output --partial "http://localhost:3720"
    refute_output --partial "localhost:2720"
}

@test "handle_logs opens the viewer URL on the HOST-published port (PANEL_PORT_LOGVIEWER)" {
    # Non-default host port (default 2719), so a hardcoded container port fails.
    # The discovery exec lists only the archive; the user picks it (1).
    PANEL_PORT_LOGVIEWER=3719
    mock_port_check "2719:yes"
    ensure_container() { return 0; }
    export MOCK_DOCKER_EXEC_OUTPUT="ARCHIVE|3"

    run handle_logs <<< "1"
    assert_success
    assert_output --partial "http://localhost:3719/scripts/log_viewer.html?manifest=.claude/logs/sessions/session_manifest.json"
    refute_output --partial "localhost:2719"
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
    assert_output --partial "  11) Restart Container"
    assert_output --partial "environment_settings.txt"
    assert_output --partial "no image build"
    assert_output --partial "  12) Stop Web Services"
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

# =========================================================================
# Tier 13 -- Restart Container (option 11)
# =========================================================================
# run_restart <answer> [settings-after-startup]
# Sources daaf.sh (test mode) in a clean subshell with every whitelisted DAAF_*
# key unset, so the panel starts exactly as on a fresh install with whatever
# ./environment_settings.txt the test wrote beforehand. It then (optionally)
# rewrites the settings file -- the user's edit AFTER the panel started -- and
# answers the confirmation prompt with <answer>. The docker mock echoes each call
# ("DOCKER: <args>") so tests can assert which compose commands ran and in what
# order. After the handler returns, the panel's port and project values are
# printed for assertions.
#
# The subshell keeps daaf.sh's `set -Eeuo pipefail`, and a marker ERR trap
# ("PANEL_ERR_TRAP: <command>") stands in for the panel's real one (registered
# only outside test mode). An unguarded failure in the handler would therefore
# print the marker AND end the subshell before the AFTER_* lines -- which is how
# the real panel dies -- so "AFTER_* present, no PANEL_ERR_TRAP" proves the
# handler returned to the menu.
#
# Knobs (exported by the test, unset afterwards):
#   <answer> = __EOF__        handle_restart reads from </dev/null (a real EOF;
#                             a herestring always delivers a line, read rc 0)
#   RESTART_EXPORT_PROJECT    DAAF_PROJECT_NAME the user exported before launch
#   RESTART_CHMOD             chmod mode applied to ./environment_settings.txt
#                             after startup (e.g. 000 = made unreadable later)
#   MOCK_DOWN_EXIT / MOCK_UP_EXIT       make `down` / `up` fail
#   MOCK_DOWN_CHMOD           chmod mode applied to the settings file during
#                             `down` (file becomes unreadable mid-restart)
#   MOCK_DOWN_SETTINGS        printf %b content written to the settings file
#                             during `down` (the user edits it mid-restart);
#                             __DELETE__ removes the file instead
#   RESTART_SECOND            after the first handler returns, write this
#                             content (printf %b) to the settings file and choose
#                             Restart Container again in the SAME panel, with
#                             MOCK_DOWN_* switched off ("SECOND_RESTART" marks
#                             the boundary; AFTER2_* lines follow)
#   MOCK_RELOAD_CHMOD         chmod mode applied to the settings file at the
#                             START of a reload_daaf_settings call (a wrapper
#                             around the real one), so the file turns unreadable
#                             at the moment that call reads it.
#                             MOCK_RELOAD_CHMOD_AT picks which call: "guard" (the
#                             project-guard probe, before `down`) or "after_down"
#                             (the post-down reload; the default)
#   MOCK_LOADER_STDERR        the real load_daaf_settings also writes
#                             "INJECTED_LOADER_STDERR" to stderr just after its
#                             open check (a stand-in for a loader bug)
#   MOCK_READY_EXIT          `exec -T daaf-docker true` fails (and writes a
#                             Docker-style line to stderr)
#   MOCK_READY_STDERR         printf %b content the failing readiness probe
#                             writes to stderr instead of that line
#   MOCK_VERIFY_EXIT          `exec -T daaf-docker test -f ...` fails
# `sleep` is stubbed to print "SLEEP: <args>" so the 30 x 2s readiness poll
# runs instantly and can be counted.
run_restart() {
    run bash -c '
        unset DAAF_PROJECT_NAME DAAF_PORT_MARIMO DAAF_PORT_LOGVIEWER DAAF_PORT_VSCODE \
              DAAF_DEV DAAF_BRANCH DAAF_DATA_VOLUME_NAME DAAF_DRY_RUN _DAAF_LIB_LOADED
        if [ -n "${RESTART_EXPORT_PROJECT:-}" ]; then
            export DAAF_PROJECT_NAME="${RESTART_EXPORT_PROJECT}"
        fi
        export DAAF_TEST_MODE=1
        source "$1/scripts/host/daaf.sh"
        unset DAAF_TEST_MODE
        trap "echo \"PANEL_ERR_TRAP: \${BASH_COMMAND}\"" ERR
        if [ -n "${MOCK_RELOAD_CHMOD:-}" ]; then
            # Keep the real reload under another name (declare -f copy; bash 3.2
            # cannot `source <(...)`), then wrap it. The guard probe runs in a
            # $( ) subshell, so "has down run" is a variable the main shell sets.
            eval "$(declare -f reload_daaf_settings | sed "1s/^reload_daaf_settings/_real_reload_daaf_settings/")"
            reload_daaf_settings() {
                case "${MOCK_RELOAD_CHMOD_AT:-after_down}:${_MOCK_DOWN_RAN:-0}" in
                    guard:0|after_down:1) chmod "${MOCK_RELOAD_CHMOD}" ./environment_settings.txt ;;
                esac
                _real_reload_daaf_settings "$@"
            }
        fi
        if [ -n "${MOCK_LOADER_STDERR:-}" ]; then
            # Re-define the real loader (declare -f copy, as above) with one
            # extra stderr line just after its open check, standing in for any
            # loader error that is not a failed open.
            eval "$(declare -f load_daaf_settings | sed "s/local key val line;/local key val line; echo \"INJECTED_LOADER_STDERR\" >\&2;/")"
            declare -f load_daaf_settings | grep -q INJECTED_LOADER_STDERR || echo "LOADER_SEAM_FAILED"
        fi
        docker() {
            echo "DOCKER: $*"
            case "$*" in
                "compose down"*)
                    _MOCK_DOWN_RAN=1
                    if [ -n "${MOCK_DOWN_CHMOD:-}" ]; then
                        chmod "${MOCK_DOWN_CHMOD}" ./environment_settings.txt
                    fi
                    if [ "${MOCK_DOWN_SETTINGS:-}" = "__DELETE__" ]; then
                        rm -f ./environment_settings.txt
                    elif [ -n "${MOCK_DOWN_SETTINGS:-}" ]; then
                        printf "%b" "${MOCK_DOWN_SETTINGS}" > ./environment_settings.txt
                    fi
                    return "${MOCK_DOWN_EXIT:-0}"
                    ;;
                "compose up"*) return "${MOCK_UP_EXIT:-0}" ;;
                "compose exec -T daaf-docker true"*)
                    if [ "${MOCK_READY_EXIT:-0}" != "0" ]; then
                        if [ -n "${MOCK_READY_STDERR:-}" ]; then
                            printf "%b" "${MOCK_READY_STDERR}" >&2
                        else
                            echo "Error response from daemon: container mock123 is restarting" >&2
                        fi
                    fi
                    return "${MOCK_READY_EXIT:-0}"
                    ;;
                "compose exec -T daaf-docker test -f"*) return "${MOCK_VERIFY_EXIT:-0}" ;;
            esac
            return 0
        }
        sleep() { echo "SLEEP: $*"; }
        if [ -n "$3" ]; then
            printf "%b" "$3" > ./environment_settings.txt
        fi
        if [ -n "${RESTART_CHMOD:-}" ]; then
            chmod "${RESTART_CHMOD}" ./environment_settings.txt
        fi
        if [ "$2" = "__EOF__" ]; then
            handle_restart </dev/null
        else
            handle_restart <<< "$2"
        fi
        echo "AFTER_PORT_MARIMO=${PANEL_PORT_MARIMO}"
        echo "AFTER_PROJECT=${DAAF_PROJECT_NAME:-daaf}"
        echo "AFTER_ENV_PORT_MARIMO=${DAAF_PORT_MARIMO:-}"
        echo "AFTER_ENV_PORT_VSCODE=${DAAF_PORT_VSCODE:-}"
        echo "AFTER_TRACKER=${_DAAF_KEYS_FROM_FILE:-}"
        if [ -n "${RESTART_SECOND:-}" ]; then
            echo "SECOND_RESTART"
            unset MOCK_DOWN_CHMOD MOCK_DOWN_SETTINGS
            chmod 644 ./environment_settings.txt 2>/dev/null || true
            printf "%b" "${RESTART_SECOND}" > ./environment_settings.txt
            handle_restart <<< "y"
            echo "AFTER2_PORT_MARIMO=${PANEL_PORT_MARIMO}"
            echo "AFTER2_PROJECT=${DAAF_PROJECT_NAME:-daaf}"
        fi
    ' _ "${REPO_ROOT}" "$1" "${2:-}"
}

# first_restart_output -- the part of $output before the SECOND_RESTART marker
# (the whole output when there is no second restart).
first_restart_output() {
    printf '%s\n' "$output" | sed '/^SECOND_RESTART$/q'
}

# skip_unless_chmod_blocks_reads <file>
# The unreadable-settings tests need `chmod 000` to actually stop reads. Running
# as root (or with CAP_DAC_OVERRIDE) the file stays readable, so the scenario
# cannot be staged: skip with the reason. Leaves the file readable either way.
skip_unless_chmod_blocks_reads() {
    chmod 000 "$1"
    if [ -r "$1" ]; then
        chmod 644 "$1"
        skip "chmod 000 does not block reads here (running as root?) -- cannot stage an unreadable settings file"
    fi
    chmod 644 "$1"
}

@test "handle_restart: answering n cancels without any docker down/up" {
    run_restart "n"
    assert_success
    assert_output --partial "Restart cancelled"
    refute_output --partial "DOCKER: compose down"
    refute_output --partial "DOCKER: compose up"
}

@test "handle_restart: an empty answer (default No) cancels without any docker down/up" {
    run_restart ""
    assert_success
    assert_output --partial "Restart cancelled"
    refute_output --partial "DOCKER: compose down"
    refute_output --partial "DOCKER: compose up"
}

@test "handle_restart: confirming runs compose down BEFORE compose up -d, never -v" {
    run_restart "y"
    assert_success
    assert_output --partial "Container restarted"
    local down_line up_line volume_flags
    down_line=$(printf '%s\n' "$output" | grep -n '^DOCKER: compose down' | head -1 | cut -d: -f1)
    up_line=$(printf '%s\n' "$output" | grep -n '^DOCKER: compose up -d' | head -1 | cut -d: -f1)
    [ -n "${down_line}" ]
    [ -n "${up_line}" ]
    [ "${down_line}" -lt "${up_line}" ]
    # No compose down may ever carry the volume-deleting flag.
    volume_flags=$(printf '%s\n' "$output" | grep '^DOCKER: compose down' | grep -cE -- '(^| )(-v|--volumes)( |$)' || true)
    [ "${volume_flags}" -eq 0 ]
}

@test "handle_restart: waits for readiness and verifies DAAF files after up -d" {
    run_restart "y"
    assert_success
    assert_output --partial "DOCKER: compose exec -T daaf-docker true"
    assert_output --partial "DOCKER: compose exec -T daaf-docker test -f /daaf/CLAUDE.md"
}

@test "handle_restart: a changed DAAF_PROJECT_NAME aborts before any docker command" {
    run_restart "y" 'DAAF_PROJECT_NAME=otherinstall\n'
    assert_success
    assert_output --partial "Restart stopped"
    assert_output --partial "otherinstall"
    assert_output --partial "Running"
    refute_output --partial "DOCKER: compose down"
    refute_output --partial "DOCKER: compose up"
    # The probe ran in a subshell: the panel still targets the original project.
    assert_output --partial "AFTER_PROJECT=daaf"
}

@test "handle_restart: a port added to the file after startup is reflected in the panel" {
    # No settings file at startup, so the panel defaulted DAAF_PORT_MARIMO to 2718.
    # That display default must not block the newly added file value on reload.
    run_restart "y" 'DAAF_PORT_MARIMO=3001\n'
    assert_success
    assert_output --partial "Container restarted"
    assert_output --partial "AFTER_PORT_MARIMO=3001"
}

@test "handle_restart: a port changed in the file after startup is reflected in the panel" {
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    run_restart "y" 'DAAF_PORT_MARIMO=3002\n'
    assert_success
    assert_output --partial "AFTER_PORT_MARIMO=3002"
}

@test "handle_restart: a failed compose down returns to the menu without compose up" {
    export MOCK_DOWN_EXIT=1
    run_restart "y"
    unset MOCK_DOWN_EXIT
    assert_success
    assert_output --partial "Could not stop the container"
    refute_output --partial "DOCKER: compose up"
    refute_output --partial "Container restarted"
}

@test "handle_restart: a failed compose up returns to the menu with guidance" {
    export MOCK_UP_EXIT=1
    run_restart "y"
    unset MOCK_UP_EXIT
    assert_success
    assert_output --partial "could not be started again"
    refute_output --partial "Container restarted"
}

@test "handle_restart: EOF at the confirmation prompt (</dev/null) cancels and returns to the menu" {
    run_restart "__EOF__"
    assert_success
    assert_output --partial "Restart cancelled"
    refute_output --partial "DOCKER:"
    refute_output --partial "PANEL_ERR_TRAP"
    # The handler returned normally: the lines after it still ran.
    assert_output --partial "AFTER_PORT_MARIMO=2718"
}

@test "handle_restart: YES, ' Yes ', and a CRLF-typed yes all confirm (any case, ends trimmed)" {
    # A herestring line is word-trimmed by `read` (spaces/tabs are IFS), so
    # ' Yes ' passes either way; the trailing CR of "yes<CR>" is NOT IFS and is
    # removed only by the handler's own end-trim.
    local answer
    for answer in "YES" " Yes " "$(printf 'yes\r')"; do
        run_restart "${answer}"
        assert_success
        assert_output --partial "DOCKER: compose down"
        assert_output --partial "DOCKER: compose up -d"
        assert_output --partial "Container restarted"
        refute_output --partial "PANEL_ERR_TRAP"
    done
}

@test "handle_restart: no, nope, and 'y es' cancel (only the ends are trimmed)" {
    local answer
    for answer in "no" "nope" "y es"; do
        run_restart "${answer}"
        assert_success
        assert_output --partial "Restart cancelled"
        refute_output --partial "DOCKER:"
        refute_output --partial "PANEL_ERR_TRAP"
    done
}

@test "handle_restart: a readiness timeout reports 60 seconds and Docker's stderr, then returns" {
    export MOCK_READY_EXIT=1
    run_restart "y"
    unset MOCK_READY_EXIT
    assert_success
    assert_output --partial "did not become ready within 60 seconds"
    assert_output --partial "Docker reported:"
    assert_output --partial "    Error response from daemon: container mock123 is restarting"
    refute_output --partial "PANEL_ERR_TRAP"
    refute_output --partial "Container restarted"
    # No verify step after a timeout.
    refute_output --partial "DOCKER: compose exec -T daaf-docker test -f"
    # 30 visible polls (the 31st, stderr-capturing call sends stdout to /dev/null)
    # with a 2s sleep between consecutive polls.
    local polls sleeps
    polls=$(printf '%s\n' "$output" | grep -c '^DOCKER: compose exec -T daaf-docker true$' || true)
    sleeps=$(printf '%s\n' "$output" | grep -c '^SLEEP: 2$' || true)
    [ "${polls}" -eq 30 ]
    [ "${sleeps}" -eq 29 ]
    assert_output --partial "AFTER_PORT_MARIMO="
}

@test "handle_restart: 'Docker reported:' skips blank lines in Docker's stderr, and is omitted when it is all blank" {
    # Parity with daaf.ps1, which drops whitespace-only lines before the last five.
    export MOCK_READY_EXIT=1
    export MOCK_READY_STDERR='\n   \nError response from daemon: container mock123 is restarting\n\t\n\n'
    run_restart "y"
    assert_success
    assert_output --partial "Docker reported:"
    local block
    block=$(printf '%s\n' "$output" | awk '/^  Docker reported:$/ {grab=1; next} /^  Check Docker Desktop for errors\.$/ {grab=0} grab {print}')
    [ "${block}" = "    Error response from daemon: container mock123 is restarting" ]

    # Whitespace-only stderr: no header, straight to the advice line.
    export MOCK_READY_STDERR=' \n\n\t\n'
    run_restart "y"
    unset MOCK_READY_EXIT MOCK_READY_STDERR
    assert_success
    assert_output --partial "did not become ready within 60 seconds"
    refute_output --partial "Docker reported:"
    assert_output --partial "Check Docker Desktop for errors."
    refute_output --partial "PANEL_ERR_TRAP"
}

@test "handle_restart: a failed DAAF-files check warns 'may not be intact' and returns" {
    export MOCK_VERIFY_EXIT=1
    run_restart "y"
    unset MOCK_VERIFY_EXIT
    assert_success
    assert_output --partial "DOCKER: compose exec -T daaf-docker test -f /daaf/CLAUDE.md"
    assert_output --partial "DAAF's files may not be intact"
    refute_output --partial "Container restarted"
    refute_output --partial "PANEL_ERR_TRAP"
    assert_output --partial "AFTER_PORT_MARIMO="
}

@test "handle_restart: guard proceeds when an exported DAAF_PROJECT_NAME outranks the file's value" {
    # The user exported DAAF_PROJECT_NAME=foo before launching; the file says bar.
    # Exported values win over the file (load + reload), so the project does not
    # change and the restart must go ahead.
    printf 'DAAF_PROJECT_NAME=bar\n' > "${TEST_DIR}/environment_settings.txt"
    export RESTART_EXPORT_PROJECT=foo
    run_restart "y"
    unset RESTART_EXPORT_PROJECT
    assert_success
    refute_output --partial "Restart stopped"
    assert_output --partial "DOCKER: compose down"
    assert_output --partial "DOCKER: compose up -d"
    assert_output --partial "Container restarted"
    assert_output --partial "AFTER_PROJECT=foo"
}

@test "handle_restart: guard proceeds when the file adds DAAF_PROJECT_NAME=daaf (the default)" {
    run_restart "y" 'DAAF_PROJECT_NAME=daaf\n'
    assert_success
    refute_output --partial "Restart stopped"
    assert_output --partial "DOCKER: compose down"
    assert_output --partial "DOCKER: compose up -d"
    assert_output --partial "Container restarted"
    assert_output --partial "AFTER_PROJECT=daaf"
}

# Review 51q SUGGESTION-1: the guard compares the names Docker Compose USES
# (resolve_project_name), so an edit that normalizes to the same project is
# not a different install.
@test "handle_restart: guard proceeds when the edit normalizes to the same project (Work -> work, My.Proj -> myproj)" {
    local pair from to
    for pair in "Work:work" "My.Proj:myproj"; do
        from="${pair%%:*}"
        to="${pair#*:}"
        printf 'DAAF_PROJECT_NAME=%s\n' "${from}" > "${TEST_DIR}/environment_settings.txt"
        run_restart "y" "DAAF_PROJECT_NAME=${to}\n"
        assert_success
        refute_output --partial "Restart stopped"
        refute_output --partial "DIFFERENT"
        assert_output --partial "DOCKER: compose down"
        assert_output --partial "DOCKER: compose up -d"
        assert_output --partial "Container restarted"
        assert_output --partial "AFTER_PROJECT=${to}"
    done
}

@test "handle_restart: guard still refuses work -> play before any docker command" {
    printf 'DAAF_PROJECT_NAME=work\n' > "${TEST_DIR}/environment_settings.txt"
    run_restart "y" 'DAAF_PROJECT_NAME=play\n'
    assert_success
    assert_output --partial "Restart stopped -- nothing was changed."
    assert_output --partial 'the project name "play" (the default is "daaf" when the'
    assert_output --partial 'file does not set one) instead of "work".'
    assert_output --partial "start a DIFFERENT one in its place"
    refute_output --partial "DOCKER:"
    assert_output --partial "AFTER_PROJECT=work"
}

@test "handle_restart: default path unchanged -- no file, and the file adding daaf, pass with no refusal text" {
    run_restart "y"
    assert_success
    refute_output --partial "Restart stopped"
    refute_output --partial "cannot use"
    assert_output --partial "Container restarted"
    assert_output --partial "AFTER_PROJECT=daaf"
    run_restart "y" 'DAAF_PROJECT_NAME=daaf\n'
    assert_success
    refute_output --partial "Restart stopped"
    refute_output --partial "cannot use"
    assert_output --partial "Container restarted"
}

@test "handle_restart: a file name that normalizes to nothing is refused before any docker command" {
    run_restart "y" 'DAAF_PROJECT_NAME=___\n'
    assert_success
    assert_output --partial "Restart stopped -- nothing was changed."
    local flat
    flat=$(printf '%s\n' "$output" | tr '\n' ' ' | tr -s ' ')
    [[ "${flat}" == *"With your current environment_settings.txt, the project name would be \"___\", which Docker Compose cannot use. A project name may use lowercase letters, digits, '-' and '_', and must start with a letter or digit."* ]]
    [[ "${flat}" == *'make environment_settings.txt use the project name "daaf" again'* ]]
    refute_output --partial "DIFFERENT"
    refute_output --partial "DOCKER:"
    assert_output --partial "AFTER_PROJECT=daaf"
}

@test "handle_restart: the post-down re-check also compares normalized names (Work -> WORK proceeds, -> ___ stops before up)" {
    printf 'DAAF_PROJECT_NAME=Work\n' > "${TEST_DIR}/environment_settings.txt"
    export MOCK_DOWN_SETTINGS='DAAF_PROJECT_NAME=WORK\n'
    run_restart "y"
    assert_success
    refute_output --partial "now names a different project"
    assert_output --partial "DOCKER: compose up -d"
    assert_output --partial "Container restarted"
    assert_output --partial "AFTER_PROJECT=WORK"

    printf 'DAAF_PROJECT_NAME=Work\n' > "${TEST_DIR}/environment_settings.txt"
    export MOCK_DOWN_SETTINGS='DAAF_PROJECT_NAME=___\n'
    run_restart "y"
    unset MOCK_DOWN_SETTINGS
    assert_success
    assert_output --partial "DOCKER: compose down"
    refute_output --partial "DOCKER: compose up"
    # An unusable name gets its own header; "a different project" would be wrong.
    refute_output --partial "now names a different project"
    local flat
    flat=$(printf '%s\n' "$output" | tr '\n' ' ' | tr -s ' ')
    [[ "${flat}" == *"The container is stopped, but it was not started again -- environment_settings.txt now has a project name that cannot be used."* ]]
    [[ "${flat}" == *'now gives the project name "___", which Docker Compose cannot use.'* ]]
    refute_output --partial "Container restarted"
    refute_output --partial "PANEL_ERR_TRAP"
    assert_output --partial "AFTER_PROJECT=Work"
}

@test "handle_restart: an unreadable settings file stops before any docker command" {
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    skip_unless_chmod_blocks_reads "${TEST_DIR}/environment_settings.txt"
    export RESTART_CHMOD=000
    run_restart "y"
    unset RESTART_CHMOD
    assert_success
    assert_output --partial "Cannot read environment_settings.txt -- make sure it is not open in another"
    assert_output --partial "program and that you have permission to read it."
    assert_output --partial "Nothing was changed."
    # Only the handler's own message: bash's raw redirection error is suppressed.
    refute_output --partial "Permission denied"
    refute_output --partial "DOCKER:"
    refute_output --partial "PANEL_ERR_TRAP"
    # The panel kept the settings it started with.
    assert_output --partial "AFTER_PORT_MARIMO=3001"
}

@test "handle_restart: a settings file that becomes unreadable during down stops before up" {
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    skip_unless_chmod_blocks_reads "${TEST_DIR}/environment_settings.txt"
    export MOCK_DOWN_CHMOD=000
    run_restart "y" 'DAAF_PORT_MARIMO=3002\n'
    unset MOCK_DOWN_CHMOD
    assert_success
    assert_output --partial "DOCKER: compose down"
    local flat
    flat=$(printf '%s\n' "$output" | tr '\n' ' ' | tr -s ' ')
    [[ "${flat}" == *"The container is stopped, but environment_settings.txt can no longer be read. Make sure it is not open in another program and that you have permission to read it, then choose Restart Container again (or Start Claude Code, which starts the container)."* ]]
    refute_output --partial "Permission denied"
    refute_output --partial "DOCKER: compose up"
    refute_output --partial "Container restarted"
    refute_output --partial "PANEL_ERR_TRAP"
    # The failed reload's changes were undone, so the panel still shows the
    # startup port and keeps its startup settings.
    assert_output --partial "AFTER_PORT_MARIMO=3001"
    assert_output --partial "AFTER_ENV_PORT_MARIMO=3001"
    assert_output --partial "AFTER_TRACKER=DAAF_PORT_MARIMO"
}

@test "handle_restart: a read failure at the moment of the post-down reload stops before up and restores settings" {
    # The file turns unreadable exactly when the post-down reload reads it, so
    # only the reload's own non-zero return can catch it. Without the `if !`
    # guard the panel's ERR trap would end the panel with the container stopped.
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    skip_unless_chmod_blocks_reads "${TEST_DIR}/environment_settings.txt"
    export MOCK_RELOAD_CHMOD=000 MOCK_RELOAD_CHMOD_AT=after_down
    run_restart "y" 'DAAF_PORT_MARIMO=3002\n'
    unset MOCK_RELOAD_CHMOD MOCK_RELOAD_CHMOD_AT
    assert_success
    refute_output --partial "PANEL_ERR_TRAP"
    assert_output --partial "DOCKER: compose down"
    assert_output --partial "The container is stopped, but environment_settings.txt can no longer"
    refute_output --partial "Permission denied"
    refute_output --partial "DOCKER: compose up"
    refute_output --partial "Container restarted"
    # The reload had already unset the tracked key; the snapshot put it back.
    assert_output --partial "AFTER_ENV_PORT_MARIMO=3001"
    assert_output --partial "AFTER_TRACKER=DAAF_PORT_MARIMO"
    assert_output --partial "AFTER_PORT_MARIMO=3001"
}

@test "handle_restart: a read failure at the moment of the guard probe stops before any docker command" {
    printf 'DAAF_PROJECT_NAME=myproj\nDAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    skip_unless_chmod_blocks_reads "${TEST_DIR}/environment_settings.txt"
    export MOCK_RELOAD_CHMOD=000 MOCK_RELOAD_CHMOD_AT=guard
    run_restart "y"
    unset MOCK_RELOAD_CHMOD MOCK_RELOAD_CHMOD_AT
    assert_success
    refute_output --partial "PANEL_ERR_TRAP"
    assert_output --partial "Cannot read environment_settings.txt -- make sure it is not open in another"
    assert_output --partial "Nothing was changed."
    refute_output --partial "Permission denied"
    # Not the project-change message: an unreadable file names no project.
    refute_output --partial "Restart stopped"
    refute_output --partial "DOCKER:"
    # The probe ran in a subshell, so the panel's settings are untouched.
    assert_output --partial "AFTER_PROJECT=myproj"
    assert_output --partial "AFTER_ENV_PORT_MARIMO=3001"
    assert_output --partial "AFTER_TRACKER=DAAF_PROJECT_NAME DAAF_PORT_MARIMO"
}

@test "handle_restart: both reload calls keep the loader's stderr visible" {
    # Only the loader's failed open is silent. Any other loader stderr must reach
    # the user from BOTH reloads -- the guard probe and the post-down reload --
    # so a loader bug is never hidden or mislabeled "Cannot read". The injected
    # line is harmless, so the restart itself completes.
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    export MOCK_LOADER_STDERR=1
    run_restart "y" 'DAAF_PORT_MARIMO=3002\n'
    unset MOCK_LOADER_STDERR
    assert_success
    refute_output --partial "LOADER_SEAM_FAILED"
    refute_output --partial "PANEL_ERR_TRAP"
    [ "$(printf '%s\n' "$output" | grep -c '^INJECTED_LOADER_STDERR$')" -eq 2 ]
    refute_output --partial "Cannot read"
    assert_output --partial "Container restarted"
    assert_output --partial "AFTER_PORT_MARIMO=3002"
}

@test "handle_restart: a project name edited during down stops before up, keeps the original settings, and a retry proceeds" {
    printf 'DAAF_PROJECT_NAME=myproj\nDAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    # The mid-down edit also ADDS a key the panel never had (DAAF_PORT_VSCODE), so
    # the restore must unset what the reload adopted, not only re-export old values.
    export MOCK_DOWN_SETTINGS='DAAF_PROJECT_NAME=other\nDAAF_PORT_MARIMO=3002\nDAAF_PORT_VSCODE=3999\n'
    export RESTART_SECOND='DAAF_PROJECT_NAME=myproj\nDAAF_PORT_MARIMO=3003\n'
    run_restart "y"
    unset MOCK_DOWN_SETTINGS RESTART_SECOND
    assert_success
    refute_output --partial "PANEL_ERR_TRAP"

    # First restart: down ran, up did not, and the user was told why.
    local first ups
    first=$(first_restart_output)
    [[ "${first}" == *"DOCKER: compose down"* ]]
    ups=$(printf '%s\n' "${first}" | grep -c '^DOCKER: compose up' || true)
    [ "${ups}" -eq 0 ]
    [[ "${first}" == *"The container is stopped, but it was not started again --"* ]]
    [[ "${first}" == *"environment_settings.txt now names a different project."* ]]
    # A different but usable name keeps that header, not the unusable-name one.
    [[ "${first}" != *"now has a project name that cannot be used"* ]]
    [[ "${first}" == *'name "other" (the default is "daaf"'* ]]
    [[ "${first}" == *'name "myproj" again, then choose Restart Container again.'* ]]
    [[ "${first}" != *"Container restarted"* ]]
    # The panel's settings are exactly the pre-restart ones (env, tracker, display).
    # Whole-line matches (grep -x): a substring match would also accept a tracker
    # with the added key appended, or a non-empty AFTER_ENV_PORT_VSCODE.
    grep -qx 'AFTER_PROJECT=myproj' <<< "${first}"
    grep -qx 'AFTER_ENV_PORT_MARIMO=3001' <<< "${first}"
    grep -qx 'AFTER_PORT_MARIMO=3001' <<< "${first}"
    grep -qx 'AFTER_ENV_PORT_VSCODE=' <<< "${first}"
    grep -qx 'AFTER_TRACKER=DAAF_PROJECT_NAME DAAF_PORT_MARIMO' <<< "${first}"

    # Second restart (file names myproj again): the guard passes and up runs.
    assert_output --partial "SECOND_RESTART"
    assert_output --partial "Container restarted"
    assert_output --partial "AFTER2_PROJECT=myproj"
    assert_output --partial "AFTER2_PORT_MARIMO=3003"
}

@test "handle_restart: a settings file deleted during down stops before up (the default project would differ)" {
    printf 'DAAF_PROJECT_NAME=myproj\n' > "${TEST_DIR}/environment_settings.txt"
    export MOCK_DOWN_SETTINGS=__DELETE__
    run_restart "y"
    unset MOCK_DOWN_SETTINGS
    assert_success
    assert_output --partial "DOCKER: compose down"
    refute_output --partial "DOCKER: compose up"
    assert_output --partial "environment_settings.txt now names a different project."
    assert_output --partial 'name "daaf" (the default is "daaf"'
    refute_output --partial "Container restarted"
    refute_output --partial "PANEL_ERR_TRAP"
    assert_output --partial "AFTER_PROJECT=myproj"
    assert_output --partial "AFTER_TRACKER=DAAF_PROJECT_NAME"
}

@test "handle_restart: the intro names DAAF_DEV, the first-time shim, and the Dockerfile/packages/docker-compose.yml list" {
    run_restart "n"
    assert_success
    # The sentence wraps across lines, so compare with line breaks and runs of
    # spaces collapsed.
    local flat
    flat=$(printf '%s\n' "$output" | tr '\n' ' ' | tr -s ' ')
    [[ "${flat}" == *'Settings marked "rebuild required" in environment_settings.txt (such as DAAF_DEV, or turning on the provider shim for the first time), and changes to the Dockerfile, packages, or docker-compose.yml, need Rebuild Container instead.'* ]]
    [[ "${flat}" != *"Alternative Providers"* ]]
}

@test "handle_help: Restart entry says 'rebuild required'; items 11 and 12 use a 5-space description indent" {
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

    # Description block = the lines after an item heading, up to the blank line.
    local desc11 desc12 flat11 bad
    desc11=$(printf '%s\n' "$output" | awk '/^  11[)] Restart Container$/ {grab=1; next} grab && /^$/ {grab=0} grab {print}')
    desc12=$(printf '%s\n' "$output" | awk '/^  12[)] Stop Web Services$/ {grab=1; next} grab && /^$/ {grab=0} grab {print}')
    [ -n "${desc11}" ]
    [ -n "${desc12}" ]

    # The phrase is wrapped across two lines in the help text, so compare with
    # line breaks and runs of spaces collapsed.
    flat11=$(printf '%s\n' "${desc11}" | tr '\n' ' ' | tr -s ' ')
    [[ "${flat11}" == *'Settings marked "rebuild required" there'* ]]
    # Same examples and Rebuild list as the handler's intro text.
    [[ "${flat11}" == *'there (such as DAAF_DEV, or turning on the provider shim for the first time), and changes to the Dockerfile, packages, or docker-compose.yml, need Rebuild Container instead.'* ]]
    [[ "${flat11}" == *'no image build. It ends any open Claude Code session or web service. Settings marked'* ]]
    [[ "${flat11}" != *'web service first.'* ]]

    # Every description line: exactly five spaces, then text.
    bad=$(printf '%s\n%s\n' "${desc11}" "${desc12}" | grep -cvE '^     [^ ]' || true)
    [ "${bad}" -eq 0 ]
}

@test "daaf.sh: dry-run restart completes, issues down then up -d, and writes nothing" {
    run env DAAF_DRY_RUN=1 bash -c 'printf "11\ny\nq\n" | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_success
    assert_output --partial "[DRY-RUN] docker compose down"
    assert_output --partial "[DRY-RUN] docker compose up -d"
    assert_output --partial "Container restarted"
    assert_output --partial "Goodbye"
    # HSM5: the dry-run restart path creates nothing in the working directory.
    run ls -A "${TEST_DIR}"
    assert_output "docker-compose.yml"
}
