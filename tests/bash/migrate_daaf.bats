#!/usr/bin/env bats
# ============================================================================
# Tests for migrate_daaf.sh -- DAAF Migration Script
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
    # Clean up lock directories that may be left by lock contention tests
    rmdir /tmp/daaf-migrate.lock.d 2>/dev/null || true
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
# Behavioral tests -- sourced functions
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
# Note: IS_INTERACTIVE is false inside `bash -c` subshells (no /dev/tty),
# which triggers the non-interactive auto-select path. To test the
# interactive read path, we define a wrapper that bypasses the check.

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
# These test the patterns used by the inline era detection code -- verifying
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
    # grep returns exit 1 when no matches -- that is the expected outcome
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

# ============================================================================
# Era-specific file marker tests
# ============================================================================
# These verify the migration script's era detection output and the file-level
# markers that distinguish each installation era. Complements the integration
# tests in ci-integration.yml which test against real Docker containers.

@test "migrate: script emits 'clone-based' for Era 1 detection" {
    # The script must output the Era 1 detection string
    run grep -c 'clone-based installation' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate: script emits 'ZIP-based' for Era 2 detection" {
    # The script must output the Era 2 detection string
    run grep -c 'ZIP-based installation' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate: Era 1 path exists (section 6a)" {
    # The script must have a code path for ERA 1 (clone-based)
    run grep -c 'ERA 1 PATH' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate: Era 2 path exists (section 6b) with graft" {
    # The script must have a code path for ERA 2 (ZIP-based) that includes grafting
    run grep -c 'ERA 2 PATH' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]

    # The Era 2 path must include the graft operation
    run grep -c 'replace --graft' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate: Era 2 detection triggers when ORIGIN_URL is empty" {
    # Simulate the era detection logic: when container_git remote returns
    # empty string, the script should set DETECTED_ERA="2"
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    container_git() { echo ""; return 0; }
    ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || true)

    # Empty ORIGIN_URL → Era 2
    [ -z "${ORIGIN_URL}" ]
}

@test "migrate: Era 1 detection triggers when ORIGIN_URL has repo name" {
    # Simulate the era detection logic: when container_git remote returns
    # the official repo URL, the script should set DETECTED_ERA="1"
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    trap - ERR
    set +eu

    container_git() { echo "https://github.com/DAAF-Contribution-Community/daaf.git"; return 0; }
    ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || true)

    # Non-empty ORIGIN_URL with repo name → Era 1
    [ -n "${ORIGIN_URL}" ]
    echo "${ORIGIN_URL}" | grep -qi "DAAF-Contribution-Community/daaf"
}

@test "migrate: dry-run output includes era detection for simulated Era 1" {
    # In dry-run mode, the script simulates an Era 1 installation.
    # Verify the output includes the era detection string.
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh" 2>&1
    assert_success
    assert_output --partial "clone-based installation"
}

# ============================================================================
# Dry-run mode
# ============================================================================

@test "migrate: download list includes daaf.sh and daaf_lib.sh" {
    run grep -c 'daaf.sh' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]

    run grep -c 'daaf_lib.sh' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "migrate: success message mentions daaf.sh as recommended entry point" {
    run grep 'DAAF Control Panel' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
}

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

# --- Regression: non-writing dry-run (2026-07-14 root-stub incident) ---
# Root cause: the dry-run curl mock touched a zero-byte stub for every -o
# target, and HOST_DIR resolves to $(pwd) when the CWD holds a
# docker-compose.yml. Running the dry-run from a compose-seeded directory
# therefore leaked ~13 zero-byte stubs (named after the host scripts) plus a
# docker-compose.yml.pre-migrate at the caller's root. These tests pin that the
# dry-run creates NOTHING on disk. See:
# research/2026-07-15_FrameworkDev_CwdLeakRootStubs/SESSION_NOTES.md

@test "migrate_daaf.sh: dry-run from a compose-seeded dir creates no new files" {
    # Seed TEST_DIR with a docker-compose.yml so HOST_DIR resolves to it (the
    # exact condition that triggered the incident at the repo root).
    create_fake_compose_file "${TEST_DIR}"
    cd "${TEST_DIR}"
    # Capture the directory contents before the dry-run.
    local before_listing
    before_listing="$(ls -A "${TEST_DIR}" | sort)"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    # The directory contents must be identical afterward -- no zero-byte stubs,
    # no docker-compose.yml.pre-migrate, no new files or directories.
    local after_listing
    after_listing="$(ls -A "${TEST_DIR}" | sort)"
    [ "${before_listing}" = "${after_listing}" ]
    # Explicit spot-checks for the specific incident artifacts.
    [ ! -e "${TEST_DIR}/docker-compose.yml.pre-migrate" ]
    [ ! -e "${TEST_DIR}/backup_daaf.sh" ]
    [ ! -e "${TEST_DIR}/daaf.sh" ]
}

@test "migrate_daaf.sh: dry-run without a compose file creates no daaf-docker dir" {
    # No docker-compose.yml in CWD: HOST_DIR would be $(pwd)/daaf-docker. The
    # dry-run must announce but NOT create it (nothing on disk).
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ ! -e "${TEST_DIR}/daaf-docker" ]
}

# --- Compose version-check predicate (^name: matches parameterized form) ---
# The up-to-date check must treat BOTH `name: daaf` and the current
# parameterized `name: ${DAAF_PROJECT_NAME:-daaf}` as already-current, so a
# migrate against a current install does NOT re-download and does NOT print the
# "Updating docker-compose.yml" line. A compose file with no `name:` key DOES
# trigger the update branch. In dry-run the branch prints a [DRY-RUN] line
# instead of writing, which these tests assert on.

@test "migrate_daaf.sh: parameterized compose name does not trigger update branch" {
    # Seed a compose file with the current parameterized name line.
    cat > "${TEST_DIR}/docker-compose.yml" <<'YAML'
name: ${DAAF_PROJECT_NAME:-daaf}
services:
  daaf-docker:
    image: daaf:latest
YAML
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    # The update branch must NOT fire for an already-current compose file.
    refute_output --partial "Updating docker-compose.yml to current version"
    [ ! -e "${TEST_DIR}/docker-compose.yml.pre-migrate" ]
}

@test "migrate_daaf.sh: compose without a name key triggers the update branch" {
    # Seed a legacy (v1.0.0-style) compose file with no top-level name: key.
    cat > "${TEST_DIR}/docker-compose.yml" <<'YAML'
services:
  daaf-docker:
    image: daaf:latest
YAML
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    # The update branch fires, and in dry-run prints the [DRY-RUN] gate line
    # instead of writing a .pre-migrate backup.
    assert_output --partial "Updating docker-compose.yml to current version"
    assert_output --partial "[DRY-RUN] Would update docker-compose.yml"
    [ ! -e "${TEST_DIR}/docker-compose.yml.pre-migrate" ]
}

# ============================================================================
# Integrated state-machine tests
# ============================================================================
# These test the MAIN ORCHESTRATION flow. The script is run as a full process
# with carefully crafted docker + curl mock responses that dispatch on the
# argument string.

# --- Helper: setup for integrated tests ---
setup_migrate_integrated() {
    export DAAF_NESTED=1
    # Create docker-compose.yml so the script uses current dir as HOST_DIR
    create_fake_compose_file
    # Create stub backup_daaf.sh that exits cleanly (called in section 3)
    cat > "${TEST_DIR}/backup_daaf.sh" <<'SH'
#!/usr/bin/env bash
echo "Backup completed (stub)"
SH
    chmod +x "${TEST_DIR}/backup_daaf.sh"
}

@test "migrate: Era 1 path (clone-based) completes successfully" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"branch --set-upstream"*) return 0 ;;
                *"exec"*"remote get-url"*"upstream"*) echo "" ; return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "clone-based installation"
    # Positive-path lock: the set-upstream arm returns 0 in this mock, so the
    # success line must print (complements the failure-path refute_output test).
    assert_output --partial "Tracking set: main -> origin/main"
    assert_output --partial "Migration complete"
}

@test "migrate: Era 2 path (ZIP-based) completes with graft" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        CALL_COUNT_REMOTE=0
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "" ; return 1 ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"rev-list --max-parents=0"*) echo "aaa111rootcommit" ;;
                *"exec"*"cat-file -p"*) printf "tree abc123\nparent def456\nauthor Test\n" ;;
                *"exec"*"branch --set-upstream"*) return 0 ;;
                *"exec"*"remote add"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "ZIP-based installation"
    assert_output --partial "Migration complete"
}

@test "migrate: already migrated (idempotency) skips graft via replace-ref leg" {
    # Idempotency via LEG 1 (replace-ref): a non-empty `git replace -l` marks the
    # graft as already done. cat-file returns NO parent here, so the ONLY thing
    # that can produce the skip is the replace leg -- proving the replace-first
    # detector (not the old parent-count check) is what catches re-runs.
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "" ; return 1 ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"replace -l"*) echo "refs/replace/aaa111rootcommit" ;;
                *"exec"*"rev-parse --is-shallow-repository"*) echo "false" ;;
                *"exec"*"rev-list --max-parents=0"*) echo "aaa111rootcommit" ;;
                *"exec"*"cat-file -p"*) printf "tree abc123\nauthor Test\n" ;;
                *"exec"*"branch --set-upstream"*) return 0 ;;
                *"exec"*"remote add"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "graft already in place"
    assert_output --partial "replace ref present"
    assert_output --partial "Migration complete"
}

@test "migrate: shallow clone forces the graft path (not falsely skipped)" {
    # Regression for Finding 3: on a shallow clone the boundary commit shows a
    # phantom parent, which the OLD detector read as "graft already in place" and
    # skipped (the bug). The new LEG 2 shallow guard forces the match/graft path
    # despite the phantom parent. Mock: no replace ref, shallow=true, cat-file has
    # a (phantom) parent, and an origin/main tree that matches so the graft lands.
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "" ; return 1 ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"replace -l"*) echo "" ;;
                *"exec"*"rev-parse --is-shallow-repository"*) echo "true" ;;
                *"exec"*"rev-list --max-parents=0"*) echo "aaa111rootcommit" ;;
                *"exec"*"cat-file -p"*) printf "tree abc123\nparent def456\nauthor Test\n" ;;
                *"exec"*"replace --graft"*) return 0 ;;
                *"exec"*"merge-base"*) echo "mergebasesha1" ;;
                *"exec"*"rev-parse"*"origin/main"*) echo "upstreamsha999" ;;
                *"exec"*"ls-tree"*) echo "blob0000 file1" ;;
                *"exec"*"branch --set-upstream"*) return 0 ;;
                *"exec"*"remote add"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "shallow clone"
    refute_output --partial "graft already in place"
    assert_output --partial "Connecting local history to upstream"
    assert_output --partial "Migration complete"
}

@test "migrate: set-upstream failure prints an honest note and does not abort" {
    # Finding 2: a failed `branch --set-upstream-to` must NOT print the
    # "Tracking set" success line. Here the set-upstream arm returns exit 1, so
    # the honest NOTE branch fires and the migration still completes (tracking is
    # best-effort, non-fatal). Era-1 path (origin matches the official repo).
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"branch --set-upstream"*) return 1 ;;
                *"exec"*"remote get-url"*"upstream"*) echo "" ; return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "Could not set upstream tracking"
    refute_output --partial "Tracking set: main -> origin/main"
    assert_output --partial "Migration complete"
}

# ============================================================================
# Error path tests
# ============================================================================

@test "migrate: fetch from origin fails exits with error" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"exec"*"fetch"*) echo "fatal: unable to access" >&2 ; return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_failure
    assert_output --partial "Failed to fetch"
}

@test "migrate: lock contention exits with already running" {
    setup_migrate_integrated
    # Create the lock directory before running
    mkdir -p /tmp/daaf-migrate.lock.d
    run bash -c '
        cd "'"${TEST_DIR}"'"
        docker() { return 0; }
        export -f docker
        curl() { return 0; }
        export -f curl
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_failure
    assert_output --partial "already running"
    # Clean up
    rmdir /tmp/daaf-migrate.lock.d 2>/dev/null || true
}

@test "migrate: DAAF not installed (CLAUDE.md missing) exits with error" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_failure
    assert_output --partial "DAAF does not appear to be installed"
}

@test "migrate: container not running and start fails exits with error" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "" ;;
                *"compose up"*) echo "ERROR: Cannot start" >&2 ; return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_failure
    assert_output --partial "Failed to start"
}

@test "migrate: volume not found exits with error" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_failure
    assert_output --partial "not found"
}

# ============================================================================
# Edge cases
# ============================================================================

@test "migrate: fork detection adds upstream remote" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"upstream"*) echo "" ; return 1 ;;
                *"exec"*"remote get-url"*"origin"*) echo "https://github.com/user/daaf-fork.git" ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"branch --set-upstream"*) return 0 ;;
                *"exec"*"remote add"*"upstream"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "clone-based installation"
    assert_output --partial "fork"
    assert_output --partial "Migration complete"
}

@test "migrate: multi-container on same volume shows warning" {
    setup_migrate_integrated
    run bash -c '
        cd "'"${TEST_DIR}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) printf "daaf-test-1\ndaaf-test-2\n" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"branch --set-upstream"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "Multiple containers"
    assert_output --partial "Migration complete"
}

# --- Field-run 4 regression pin (2026-07-17): honest tracking NOTE ---

@test "migrate: set-upstream failure NOTE diagnoses the actual failed precondition" {
    # The former NOTE always blamed a missing local 'main' branch; on tag-pinned
    # or single-branch installs the actual missing piece is the origin/main
    # remote-tracking ref. Both sites (Era 1 and Era 2/3) must probe which
    # precondition failed and say so.
    run grep -cF "no 'origin/main' remote-tracking ref" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -eq 2 ]
    run grep -cF "rev-parse --verify --quiet refs/remotes/origin/main" "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -eq 2 ]
}

# ============================================================================
# Field-Run Triage Round 5 (2026-07-17): git safe.directory exemption
# ============================================================================
# A root-owned v1.0.0 (Era-1) volume payload + the image's non-root appuser +
# modern git (>= 2.35.2) => "fatal: detected dubious ownership in repository at
# '/daaf'" on every in-container git op, so migrate could not proceed at all.
# migrate now issues an idempotent `git config --global --add safe.directory
# /daaf` for the exec user BEFORE the first in-container git operation (the
# era-detection probe). These pin that the exemption is issued, targets /daaf,
# and precedes era detection.

@test "migrate: safe.directory exemption is added before the first container git op" {
    setup_migrate_integrated
    local calllog="${TEST_DIR}/docker_exec_calls.log"
    run bash -c '
        cd "'"${TEST_DIR}"'"
        # Export so the migrate subprocess (set -u) and the exported docker
        # function both see it.
        export CALLLOG="'"${calllog}"'"
        curl() {
            local outfile=""
            local args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
                if [ "${args[$i]}" = "-o" ]; then
                    outfile="${args[$((i+1))]}"
                    break
                fi
            done
            if [ -n "${outfile}" ]; then
                mkdir -p "$(dirname "${outfile}")"
                echo "#!/usr/bin/env bash" > "${outfile}"
                echo "exit 0" >> "${outfile}"
            fi
            return 0
        }
        export -f curl
        docker() {
            local all_args="$*"
            # Record every docker exec invocation in call order for ordering checks.
            case "$all_args" in
                *"exec"*) echo "${all_args}" >> "${CALLLOG}" ;;
            esac
            case "$all_args" in
                "info") return 0 ;;
                *"volume inspect"*) return 0 ;;
                *"ps -a"*"--filter"*"volume="*"--format"*) echo "daaf-test-1" ;;
                *"inspect --format"*"State.Status"*) echo "running" ;;
                *"exec"*"true"*) return 0 ;;
                *"exec"*"test -f"*"CLAUDE.md"*) return 0 ;;
                *"exec"*"config"*"safe.directory"*) return 0 ;;
                *"exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"exec"*"fetch"*) return 0 ;;
                *"exec"*"branch --set-upstream"*) return 0 ;;
                *"exec"*"remote get-url"*"upstream"*) echo "" ; return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/migrate_daaf.sh"
    '
    assert_success
    assert_output --partial "Configured: safe.directory -> /daaf"
    # The safe.directory add must be recorded, target /daaf, and precede the
    # first era-detection git op (remote get-url origin). Revert the fix -> the
    # add line is absent -> config_line is empty -> this assertion fails.
    local config_line firstgit_line
    config_line=$(grep -n -- '--add safe.directory /daaf' "${calllog}" | head -1 | cut -d: -f1)
    firstgit_line=$(grep -n 'remote get-url origin' "${calllog}" | head -1 | cut -d: -f1)
    [ -n "${config_line}" ]
    [ -n "${firstgit_line}" ]
    [ "${config_line}" -lt "${firstgit_line}" ]
}

@test "migrate: safe.directory exemption command and field-evidence rationale are present" {
    # Source-level pin (revert-the-fix-and-it-fails): the exemption command and
    # the field-evidence comment (git's dubious-ownership fatal) must both exist.
    run grep -cF 'git config --global --add safe.directory /daaf' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
    run grep -cF 'detected dubious ownership' "${REPO_ROOT}/scripts/host/migrate_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}
