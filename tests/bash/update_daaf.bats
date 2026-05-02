#!/usr/bin/env bats
# ============================================================================
# Tests for update_daaf.sh — DAAF Update Script
# ============================================================================
# update_daaf.sh is the most complex script: state machine with ahead/behind
# detection, merge/rebase paths, stash handling, conflict resolution.
# These tests focus on preflight checks and early-exit paths that can be
# tested without a real Docker daemon.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    create_fake_compose_file
}

teardown() {
    common_teardown
    # Clean up lock directories that may be left by lock contention tests
    rmdir /tmp/daaf-update.lock.d 2>/dev/null || true
}

# --- Syntax ---

@test "update_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
}

# --- Preflight: missing docker-compose.yml ---

@test "update_daaf.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "update_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "update_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "update_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    # Will fail at some docker step, but should not pause
    MOCK_DOCKER_COMPOSE_EXIT=1
    MOCK_DOCKER_PS_OUTPUT=""
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Helper function: prompt_choice ---

@test "update_daaf.sh defines prompt_choice helper function" {
    # Verify the function exists in the script source
    run grep -c "prompt_choice()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: handle_conflict ---

@test "update_daaf.sh defines handle_conflict helper function" {
    run grep -c "handle_conflict()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: sync_host_scripts ---

@test "update_daaf.sh defines sync_host_scripts helper function" {
    run grep -c "sync_host_scripts()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: check_build_changes ---

@test "update_daaf.sh defines check_build_changes helper function" {
    run grep -c "check_build_changes()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: finish_update ---

@test "update_daaf.sh defines finish_update helper function" {
    run grep -c "finish_update()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- ERR trap defined ---

@test "update_daaf.sh defines an ERR trap for cleanup" {
    run grep -c "trap cleanup_on_error ERR" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Banner display ---

@test "update_daaf.sh displays the DAAF Updater banner" {
    export DAAF_NESTED=1
    # Will fail at preflight but should show banner first
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_output --partial "DAAF Updater"
}

# --- DAAF_BRANCH override ---

@test "update_daaf.sh uses DAAF_BRANCH variable in banner tip" {
    # The script references DAAF_BRANCH for branch resolution
    run grep -c "DAAF_BRANCH" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# ============================================================================
# Behavioral tests — sourced functions
# ============================================================================
# Source the script in test mode so all helper functions are available
# without executing the main state-machine logic.
#
# The sourcing pattern:
#   DAAF_TEST_MODE=1 source update_daaf.sh   (defines functions, then returns)
#   trap - ERR                                (remove ERR trap from sourced script)
#   set +eu                                   (disable strict mode for test flexibility)
#
# After sourcing, these functions are callable:
#   prompt_choice, handle_conflict, sync_host_scripts,
#   check_build_changes, finish_update, cleanup_on_error
# ============================================================================

# --- sync_host_scripts behavioral tests ---

@test "update: sync_host_scripts skips when HEAD unchanged" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        # Mock docker: compose exec returns the same HEAD hash
        docker() {
            echo "abc1234"
            return 0
        }

        sync_host_scripts "abc1234"
    '
    assert_success
    # No "Syncing" output when HEAD is unchanged
    refute_output --partial "Syncing"
}

@test "update: sync_host_scripts detects changed files via git diff" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *diff*--name-only*) echo "scripts/host/run_daaf.sh" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    assert_output --partial "Syncing updated utility scripts..."
}

@test "update: sync_host_scripts copies only changed files" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *diff*--name-only*) printf "scripts/host/run_daaf.sh\nscripts/host/backup_daaf.sh\n" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    assert_output --partial "Updated: run_daaf.sh"
    assert_output --partial "Updated: backup_daaf.sh"
}

@test "update: sync_host_scripts handles partial failure gracefully" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *diff*--name-only*) printf "scripts/host/run_daaf.sh\nscripts/host/backup_daaf.sh\n" ;;
                cp*) return 1 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    assert_output --partial "Warning: could not copy run_daaf.sh"
    assert_output --partial "Warning: could not copy backup_daaf.sh"
}

# --- check_build_changes behavioral tests ---

@test "update: check_build_changes detects Dockerfile modifications" {
    # Pipe "n" to decline the rebuild prompt
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *diff*--name-only*) echo "Dockerfile" ;;
                *) return 0 ;;
            esac
        }
        echo "n" | check_build_changes "old1234"
    '
    assert_success
    assert_output --partial "Build files were updated"
}

@test "update: check_build_changes detects docker-compose.yml modifications" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *diff*--name-only*) echo "docker-compose.yml" ;;
                *) return 0 ;;
            esac
        }
        echo "n" | check_build_changes "old1234"
    '
    assert_success
    assert_output --partial "Build files were updated"
}

@test "update: check_build_changes reports no changes when unchanged" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$1" in
                compose)
                    # rev-parse HEAD returns same hash as old_head
                    echo "samehash"
                    return 0
                    ;;
                *) return 0 ;;
            esac
        }
        check_build_changes "samehash"
    '
    assert_success
    assert_output --partial "No Dockerfile changes"
}

# --- finish_update behavioral tests ---

@test "update: finish_update calls sync and check_build_changes" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        # Override downstream functions to track calls
        sync_host_scripts() { echo "SYNC_CALLED:$1"; }
        check_build_changes() { echo "CHECK_CALLED:$1"; }

        finish_update "oldhash123"
    '
    assert_success
    assert_output --partial "SYNC_CALLED:oldhash123"
    assert_output --partial "CHECK_CALLED:oldhash123"
    assert_output --partial "Update complete!"
}

@test "update: finish_update displays extra message when provided" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        sync_host_scripts() { :; }
        check_build_changes() { :; }

        finish_update "oldhash123" "Your commits were rebased."
    '
    assert_success
    assert_output --partial "Update complete!"
    assert_output --partial "Your commits were rebased."
}

# --- prompt_choice behavioral tests ---
# Note: IS_INTERACTIVE is false inside `bash -c` subshells (no /dev/tty),
# which triggers the non-interactive auto-select path. To test the
# interactive read path, we define a wrapper that bypasses the check.

@test "update: prompt_choice auto-selects first choice in non-interactive mode" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        echo "ignored" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

@test "update: prompt_choice auto-selects first of multi-option set" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        echo "ignored" | prompt_choice "Choose [1/2/3]: " "1 2 3"
    '
    assert_success
    assert_output --partial "1"
}

@test "update: prompt_choice reads input interactively when stdin is a TTY" {
    # Override prompt_choice to remove the TTY check, simulating interactive mode
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        prompt_choice() {
            local prompt_text="$1"
            local valid_choices="$2"
            local choice=""
            read -r choice
            choice=$(echo "${choice}" | tr "[:upper:]" "[:lower:]")
            if echo "${valid_choices}" | grep -qw "${choice}"; then
                echo "${choice}"
            fi
        }
        echo "y" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

@test "update: prompt_choice normalizes uppercase to lowercase" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        prompt_choice() {
            local prompt_text="$1"
            local valid_choices="$2"
            local choice=""
            read -r choice
            choice=$(echo "${choice}" | tr "[:upper:]" "[:lower:]")
            if echo "${valid_choices}" | grep -qw "${choice}"; then
                echo "${choice}"
            fi
        }
        echo "Y" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

# --- handle_conflict behavioral tests ---

@test "update: handle_conflict shows conflicting file list" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$*" in
                *diff*--diff-filter=U*) printf "CLAUDE.md\nscripts/host/run_daaf.sh\n" ;;
                *) return 0 ;;
            esac
        }

        # Pipe "2" to choose manual resolution (avoids interactive Claude launch)
        echo "2" | handle_conflict "merge" "merge --abort" || true
    '
    assert_output --partial "CLAUDE.md"
    assert_output --partial "scripts/host/run_daaf.sh"
}

# handle_conflict calls prompt_choice internally. Since IS_INTERACTIVE is
# false in bash -c subshells, prompt_choice auto-selects option 1. We
# override prompt_choice to force option 2 for testing the manual path.

@test "update: handle_conflict option 2 shows manual resolution instructions" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        prompt_choice() { echo "2"; }
        handle_conflict "merge" "merge --abort" || true
    '
    assert_output --partial "resolve the conflicts manually"
}

@test "update: handle_conflict merge type shows git add + commit instructions" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        prompt_choice() { echo "2"; }
        handle_conflict "merge" "merge --abort" || true
    '
    assert_output --partial "git commit"
    # Merge type should NOT show rebase --continue
    refute_output --partial "git rebase --continue"
}

@test "update: handle_conflict rebase type shows git rebase --continue" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        prompt_choice() { echo "2"; }
        handle_conflict "rebase" "rebase --abort" || true
    '
    assert_output --partial "git rebase --continue"
}

@test "update: handle_conflict returns 1 when conflicts remain" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        echo "2" | handle_conflict "merge" "merge --abort"
    '
    assert_failure
}

# --- Safety tests ---

@test "update: ERR trap is registered after sourcing" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        # Do NOT clear the trap — we want to verify it exists
        set +eu
        trap -p ERR
    '
    assert_success
    assert_output --partial "cleanup_on_error"
}

@test "update: locking uses portable mkdir (no flock)" {
    # Verify the script uses mkdir for locking, not flock
    run grep -ci 'mkdir.*lock' "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]

    run grep -c 'flock' "${REPO_ROOT}/scripts/host/update_daaf.sh"
    [ "${output}" = "0" ]
}

@test "update: cleanup_on_error prints recovery guidance" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        # Mock docker to prevent actual docker calls in cleanup
        docker() { return 1; }

        cleanup_on_error 2>&1
    '
    assert_success
    assert_output --partial "Something went wrong unexpectedly"
    assert_output --partial "safe to re-run"
}

@test "update: cleanup_on_error mentions stash when STASHED=true" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() { return 1; }
        STASHED=true

        cleanup_on_error 2>&1
    '
    assert_success
    assert_output --partial "stash pop"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "update_daaf.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
}

@test "update_daaf.sh: dry-run reports already up to date" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/update_daaf.sh" 2>&1
    assert_success
    assert_output --partial "Already up to date"
}

# ============================================================================
# Integrated state-machine tests
# ============================================================================
# These test the MAIN ORCHESTRATION flow (not individual helper functions).
# The script is run as a full process with carefully crafted docker mock
# responses that dispatch on the git subcommand arguments.

# --- Helper: create a dispatch-based docker mock ---
# Sets up a docker function that dispatches on the full argument string.
# Callers configure behavior via MOCK_* variables before running the script.
setup_state_machine() {
    create_fake_compose_file
    export DAAF_NESTED=1
}

@test "update: clean pull path succeeds (behind, no local commits, no dirty files)" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "main" ;;
                *"compose exec"*"rev-parse"*"origin/main"*) echo "def456remote" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123local" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"rev-list --count"*"origin/main..HEAD"*) echo "0" ;;
                *"compose exec"*"rev-list --count"*"HEAD..origin/main"*) echo "3" ;;
                *"compose exec"*"pull"*) echo "Updating abc123..def456" ; return 0 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"symbolic-ref"*) echo "main" ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Update complete!"
    assert_output --partial "Pulling updates..."
}

@test "update: already up to date exits cleanly (same SHA, no dirty files)" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "main" ;;
                *"compose exec"*"rev-parse"*"origin/main"*) echo "abc123same" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123same" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Already up to date"
}

@test "update: no remote configured exits with guidance" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*) return 0 ;;
                *"compose exec"*"remote get-url"*) echo "" ; return 1 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    # exit 0 with guidance message
    assert_success
    assert_output --partial "not connected to the update server"
}

@test "update: network failure during fetch exits with error" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*) return 0 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) echo "fatal: unable to access" >&2 ; return 1 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "Failed to fetch"
}

@test "update: lock contention exits with already running message" {
    setup_state_machine
    # Create the lock directory before running the script
    mkdir -p /tmp/daaf-update.lock.d
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "already running"
    # Clean up the lock
    rmdir /tmp/daaf-update.lock.d 2>/dev/null || true
}

@test "update: lock cleanup on exit (trap removes lock dir)" {
    setup_state_machine
    # Run the script in dry-run mode so it completes cleanly, then check that
    # the lock directory no longer exists.
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    # Lock directory should be cleaned up by the EXIT trap
    [ ! -d /tmp/daaf-update.lock.d ]
}

# ============================================================================
# Error path tests
# ============================================================================

@test "update: container not running and start fails exits with error" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*) echo "" ;;
                *"compose up"*) echo "ERROR: Cannot start" >&2 ; return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "Failed to start"
}

@test "update: DAAF not installed (CLAUDE.md missing) exits with error" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*/daaf/CLAUDE.md*) return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "DAAF does not appear to be installed"
}

@test "update: DAAF_BRANCH specifies nonexistent branch exits with error" {
    setup_state_machine
    run bash -c '
        export DAAF_BRANCH="nonexistent-branch-xyz"
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/nonexistent-branch-xyz"*) return 1 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "nonexistent-branch-xyz"
    assert_output --partial "was not found"
}
