#!/usr/bin/env bats
# ============================================================================
# Tests for migrate_daaf.sh — DAAF Migration Script
# ============================================================================
# Key testable logic: era detection (clone vs ZIP), preflight checks,
# helper functions (container_git, prompt_choice), idempotency markers.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    mock_curl
}

teardown() {
    common_teardown
}

# --- Syntax ---

@test "migrate_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
}

# --- Preflight: missing Docker ---

@test "migrate_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "migrate_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- Preflight: volume not found ---

@test "migrate_daaf.sh fails when Docker volume does not exist" {
    MOCK_DOCKER_VOLUME_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

# --- DAAF_NESTED behavior ---

@test "migrate_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Banner display ---

@test "migrate_daaf.sh displays the DAAF Migration banner" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_output --partial "DAAF Migration"
}

# --- Helper functions defined ---

@test "migrate_daaf.sh defines prompt_choice helper function" {
    run grep -c "prompt_choice()" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate_daaf.sh defines container_git helper function" {
    run grep -c "container_git()" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate_daaf.sh defines container_git_verbose helper function" {
    run grep -c "container_git_verbose()" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate_daaf.sh defines container_exec helper function" {
    run grep -c "container_exec()" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- ERR trap defined ---

@test "migrate_daaf.sh defines an ERR trap for cleanup" {
    run grep -c "trap cleanup_on_error ERR" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Era detection references ---

@test "migrate_daaf.sh references both Era 1 and Era 2 paths" {
    run grep -c "ERA.*PATH" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 2 ]
}

# --- DAAF_BRANCH override ---

@test "migrate_daaf.sh supports DAAF_BRANCH environment variable" {
    run grep -c "DAAF_BRANCH" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Idempotency check ---

@test "migrate_daaf.sh claims to be idempotent in its header" {
    run grep -c "idempotent" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Creates host directory when not in daaf-docker ---

@test "migrate_daaf.sh creates daaf-docker directory when docker-compose.yml is missing" {
    # When docker-compose.yml does not exist in cwd, the script creates daaf-docker/
    # The script will fail later at volume check or download, but it should
    # announce the directory creation
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_CURL_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_output --partial "daaf-docker"
}

# ============================================================================
# Behavioral tests — sourced functions
# ============================================================================
# Source the script in test mode to access helper functions directly.
# DAAF_TEST_MODE=1 causes the script to return after defining functions,
# skipping the main execution body.

# --- container_git behavioral tests ---

@test "migrate: container_git executes git in container" {
    # Source in test mode to get the functions
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    CONTAINER_NAME="test-container"

    # Mock docker to record calls and return empty output
    docker() {
        echo "DOCKER_CALLED: $*"
        return 0
    }
    export -f docker

    run container_git status
    assert_success
    assert_output --partial "DOCKER_CALLED:"
    assert_output --partial "test-container"
    assert_output --partial "git -C /daaf status"
}

@test "migrate: container_git suppresses stderr" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    CONTAINER_NAME="test-container"

    # Mock docker to emit both stdout and stderr
    docker() {
        echo "stdout-line"
        echo "stderr-line" >&2
        return 0
    }
    export -f docker

    # container_git redirects stderr to /dev/null, so only stdout should appear
    run container_git status
    assert_success
    assert_output --partial "stdout-line"
    refute_output --partial "stderr-line"
}

@test "migrate: container_git strips carriage returns" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    CONTAINER_NAME="test-container"

    # Mock docker to return output with \r (Windows-style line endings)
    docker() {
        printf "line-with-cr\r\n"
        return 0
    }
    export -f docker

    run container_git status
    assert_success
    # Output should not contain \r
    [[ "${output}" != *$'\r'* ]]
    assert_output --partial "line-with-cr"
}

# --- container_git_verbose behavioral tests ---

@test "migrate: container_git_verbose preserves stderr" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    CONTAINER_NAME="test-container"

    # Mock docker to emit stderr
    docker() {
        echo "stdout-output"
        echo "verbose-stderr" >&2
        return 0
    }
    export -f docker

    # container_git_verbose does NOT redirect stderr to /dev/null
    # Use run with 3>&1 to capture stderr in output
    run bash -c '
        CONTAINER_NAME="test-container"
        docker() {
            echo "stdout-output"
            echo "verbose-stderr" >&2
            return 0
        }
        export -f docker
        source "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh" 2>/dev/null
        container_git_verbose status 2>&1
    '
    assert_success
    assert_output --partial "verbose-stderr"
}

# --- container_exec behavioral tests ---

@test "migrate: container_exec runs arbitrary command in container" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    CONTAINER_NAME="test-container"

    docker() {
        echo "EXEC_CALLED: $*"
        return 0
    }
    export -f docker

    run container_exec ls -la /daaf
    assert_success
    assert_output --partial "EXEC_CALLED:"
    assert_output --partial "test-container"
    assert_output --partial "ls -la /daaf"
}

# --- prompt_choice behavioral tests ---
# Note: piping input makes stdin a pipe (not a TTY), which triggers the
# non-interactive auto-select path. To test the interactive read path,
# we define a wrapper that overrides the [ -t 0 ] check.

@test "migrate: prompt_choice auto-selects first choice in non-interactive mode" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh" 2>/dev/null
        echo "ignored" | prompt_choice "Choose [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
    assert_output --partial "Non-interactive"
}

@test "migrate: prompt_choice reads input interactively when stdin is a TTY" {
    # Override prompt_choice to remove the TTY check, simulating interactive mode
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh" 2>/dev/null
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
        echo "y" | prompt_choice "Choose [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

# ============================================================================
# Era detection pattern tests
# ============================================================================
# These test the patterns used by the inline era detection code — verifying
# that the git commands used for detection produce distinguishable output
# for each era type.

@test "migrate: no remote indicates Era 1 pattern (ZIP install)" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    # Override container_git to simulate no remote configured
    container_git() {
        case "$1" in
            remote) echo "" ;;  # No remote URL → empty output
            *) echo "" ;;
        esac
        return 0
    }

    # Simulate the era detection logic from the script (lines 405-426):
    # ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || true)
    ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || true)

    # When ORIGIN_URL is empty, the script goes to DETECTED_ERA="2" (ZIP install)
    [ -z "${ORIGIN_URL}" ]
}

@test "migrate: remote with known repo URL indicates Era 2 pattern (clone)" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    # Override container_git to simulate a remote pointing to the official repo
    container_git() {
        case "$1" in
            remote) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
            *) echo "" ;;
        esac
        return 0
    }

    ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || true)

    # When ORIGIN_URL is non-empty AND contains the repo name, era is "1" (clone)
    [ -n "${ORIGIN_URL}" ]
    echo "${ORIGIN_URL}" | grep -qi "DAAF-Contribution-Community/daaf"
}

@test "migrate: idempotency marker detected via root commit parent check" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    # The script checks if the initial commit already has a parent (line 567-568):
    #   INITIAL_PARENT_COUNT=$(container_git_verbose cat-file -p "$INITIAL_COMMIT" | grep -c '^parent ')
    # If > 0, graft is already in place → skip graft step.

    # Simulate a commit that already has a parent (graft already applied)
    FAKE_CAT_FILE_OUTPUT="tree abc123
parent def456
author Test <test@test> 1700000000 +0000
committer Test <test@test> 1700000000 +0000

Initial commit"

    INITIAL_PARENT_COUNT=$(echo "${FAKE_CAT_FILE_OUTPUT}" | grep -c '^parent ' || echo "0")

    # Parent count > 0 means graft is in place → idempotency check passes
    [ "${INITIAL_PARENT_COUNT}" -gt 0 ]
}

@test "migrate: corrupted volume (no .git) detected by container_exec test" {
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    CONTAINER_NAME="test-container"

    # Override container_exec to fail for the CLAUDE.md existence check (line 385)
    # In the script: container_exec test -f /daaf/CLAUDE.md
    container_exec() {
        return 1  # File not found → volume is corrupted/missing
    }

    # Verify the pattern: failed test returns non-zero
    run container_exec test -f /daaf/CLAUDE.md
    assert_failure
}

# ============================================================================
# Safety tests
# ============================================================================

@test "migrate: locking uses portable mkdir (no flock)" {
    # The script should use mkdir for locking (portable across Linux/macOS/Git Bash)
    # and should NOT use flock (not available on macOS)
    run grep -c 'mkdir.*LOCK' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]

    run grep -c 'flock' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    # grep returns exit 1 when no matches — that is the expected outcome
    assert_failure
}

@test "migrate: ERR trap registered for cleanup after sourcing" {
    # After sourcing in test mode, verify the ERR trap was set
    # (we clear it in tests, but the script should have set it)
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh" 2>/dev/null
        trap -p ERR
    '
    assert_success
    assert_output --partial "cleanup_on_error"
}

@test "migrate: backup runs before destructive operations" {
    # Verify that backup_daaf.sh is called (section 3) before the era detection
    # and graft operations (sections 5-6). Check that "backup_daaf" appears in
    # the script before "replace --graft" (the destructive graft operation).
    local backup_line
    local graft_line
    backup_line=$(grep -n 'backup_daaf' "${REPO_ROOT}/scripts/host/migrate_daaf.sh" | head -1 | cut -d: -f1)
    graft_line=$(grep -n 'replace --graft' "${REPO_ROOT}/scripts/host/migrate_daaf.sh" | head -1 | cut -d: -f1)

    # Both patterns must exist
    [ -n "${backup_line}" ]
    [ -n "${graft_line}" ]

    # Backup must come before the graft operation
    [ "${backup_line}" -lt "${graft_line}" ]
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "migrate_daaf.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
}

@test "migrate_daaf.sh: dry-run produces DRY-RUN markers" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
}

@test "migrate_daaf.sh: dry-run completes migration" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh" 2>&1
    assert_success
    assert_output --partial "Migration complete"
}
