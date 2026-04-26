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

@test "update: prompt_choice accepts valid input on first try" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
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
        echo "Y" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

@test "update: prompt_choice rejects invalid input and reprompts" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        printf "x\ny\n" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    # The reprompt message goes to stderr; stdout should contain the final valid choice
    assert_output --partial "y"
}

@test "update: prompt_choice accepts multi-option choice sets" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        echo "2" | prompt_choice "Choose [1/2/3]: " "1 2 3"
    '
    assert_success
    assert_output --partial "2"
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

        echo "2" | handle_conflict "merge" "merge --abort" || true
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

        echo "2" | handle_conflict "merge" "merge --abort" || true
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

        echo "2" | handle_conflict "rebase" "rebase --abort" || true
    '
    assert_output --partial "git rebase --continue"
}

@test "update: handle_conflict returns 1 when manual resolution chosen" {
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
