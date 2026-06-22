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
    MOCK_DOCKER_INFO_EXIT=1
    run env DAAF_DRY_RUN=1 bash -c 'echo q | bash "'"${REPO_ROOT}"'/scripts/host/daaf.sh"'
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# =========================================================================
# Tier 3 -- Script structure
# =========================================================================

@test "daaf.sh includes set -euo pipefail" {
    run grep -c "set -euo pipefail" "${REPO_ROOT}/scripts/host/daaf.sh"
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

@test "daaf.sh does not have DAAF_NESTED exit trap" {
    # The menu wrapper is the top-level entry point and should NOT
    # have the "Press Enter to continue" trap.
    run grep "Press Enter" "${REPO_ROOT}/scripts/host/daaf.sh"
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
    # Mock docker compose ps to show the container
    docker() {
        case "$*" in
            *"compose ps --status running"*"--format"*)
                echo "daaf-docker"
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
            *"compose ps --status running"*"--format"*)
                echo "daaf-docker"
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

@test "display_menu shows all numbered options 1-10" {
    # Set status variables for display
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
    assert_output --partial "1)"
    assert_output --partial "2)"
    assert_output --partial "3)"
    assert_output --partial "4)"
    assert_output --partial "5)"
    assert_output --partial "6)"
    assert_output --partial "7)"
    assert_output --partial "8)"
    assert_output --partial "9)"
    assert_output --partial "10)"
    assert_output --partial "h)"
    assert_output --partial "q)"
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

@test "dispatch_choice routes option 10 to handle_stop_services" {
    handle_stop_services() { echo "CALLED_STOP_SERVICES"; }
    export -f handle_stop_services

    run dispatch_choice "10"
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
    run dispatch_choice "q"
    assert_failure  # exit 0 from subshell shows as failure in run
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
    mock_port_check "2718:yes 2720:yes"

    # Provide "0" (Back) as input to avoid blocking on read
    run bash -c 'echo "0" | (
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        setup_colors
        source "'"${REPO_ROOT}"'/scripts/host/daaf.sh" 2>/dev/null
        mock_port_check "2718:yes 2720:yes"
        handle_stop_services
    )' 2>/dev/null
    # Structural check: the function should show running services
    assert_output --partial "Running services"
}

# =========================================================================
# Tier 10 -- Help and Exit
# =========================================================================

@test "handle_help shows descriptions for all options" {
    # Provide Enter as input for the "Press Enter to continue" prompt
    run bash -c 'echo "" | (
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        setup_colors
        export DAAF_TEST_MODE=1
        source "'"${REPO_ROOT}"'/scripts/host/daaf.sh"
        unset DAAF_TEST_MODE
        handle_help
    )'
    assert_success
    assert_output --partial "Start Claude Code"
    assert_output --partial "Browse Notebooks"
    assert_output --partial "Browse Files"
    assert_output --partial "View Session Logs"
    assert_output --partial "Open Container Shell"
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
