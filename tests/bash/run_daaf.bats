#!/usr/bin/env bats
# ============================================================================
# Tests for run_daaf.sh -- DAAF Launcher
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    create_fake_compose_file
    # A DAAF dev container exports DAAF_BRANCH and DAAF_DEV, which the printed
    # reinstall carries; tests that need them set them explicitly.
    unset DAAF_BRANCH DAAF_DEV
}

teardown() {
    common_teardown
}

# --- Syntax ---

@test "run_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_success
}

# --- Preflight: missing docker-compose.yml ---

@test "run_daaf.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "run_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "run_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "run_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    # The mock will make compose ps return no match, then compose up succeeds,
    # then exec for CLAUDE.md check succeeds, then exec for claude runs
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_EXEC_OUTPUT=""
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Default command ---

@test "run_daaf.sh defaults to claude command" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_output --partial "Launching Claude Code"
}

# --- Custom command ---

@test "run_daaf.sh accepts bash as argument" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh" bash
    assert_output --partial "Entering container shell"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "run_daaf.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_success
}

@test "run_daaf.sh: dry-run produces DRY-RUN markers" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_daaf.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
}

# =========================================================================
# --- Error paths ---
# =========================================================================

@test "run_daaf: auto-starts container when not running" {
    export DAAF_NESTED=1
    create_fake_compose_file

    docker() {
        case "$1" in
            info) return 0 ;;
            compose)
                shift
                case "$1" in
                    ps) echo "" ; return 0 ;;
                    up) return 0 ;;
                    exec) echo "" ; return 0 ;;
                    *) return 0 ;;
                esac ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_output --partial "Starting"
}

@test "run_daaf: auto-start fails exits with error" {
    export DAAF_NESTED=1
    create_fake_compose_file

    docker() {
        case "$1" in
            info) return 0 ;;
            compose)
                shift
                case "$1" in
                    ps) echo "" ; return 0 ;;
                    up) return 1 ;;
                    *) return 0 ;;
                esac ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start"
}

@test "run_daaf: compose file missing exits with error" {
    export DAAF_NESTED=1
    rm -f "${TEST_DIR}/docker-compose.yml"

    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

@test "run_daaf: DAAF not installed in container exits with error" {
    export DAAF_NESTED=1
    create_fake_compose_file

    docker() {
        case "$1" in
            info) return 0 ;;
            compose)
                shift
                case "$1" in
                    ps) echo "daaf-docker" ; return 0 ;;
                    exec)
                        # Check if this is the CLAUDE.md test
                        local args_str="$*"
                        if [[ "${args_str}" == *"test -f"* ]]; then
                            return 1
                        fi
                        return 0
                        ;;
                    *) return 0 ;;
                esac ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    assert_output --partial "DAAF does not appear to be installed"
    # The updater refuses this state, so the remedy is a forced reinstall run
    # from the folder above this one; the default project prints no project.
    refute_output --partial "update_daaf.sh"
    grep -Fxq "  cd \"$(dirname "${TEST_DIR}")\"" <<< "${output}"
    # Without a project (a DAAF dev container exports its own), no prefix.
    unset DAAF_PROJECT_NAME
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    grep -Fxq "  DAAF_FORCE_REINSTALL=1 bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh)\"" <<< "${output}"
}

# A docker mock for a running container whose files are missing (exec test -f
# fails) or present, created long before environment_settings.txt was written.
run_daaf_running_mock() {
    docker() {
        case "$*" in
            info) return 0 ;;
            "compose ps -q daaf-docker") echo "abc123" ;;
            "inspect --format {{.Created}} abc123") echo "2000-01-01T00:00:00.000000000Z" ;;
            *"test -f /daaf/CLAUDE.md"*) return "${MOCK_RUN_DAAF_TESTF_EXIT:-0}" ;;
            *) return 0 ;;
        esac
    }
    export -f docker
}

@test "run_daaf: with a named project, the by-hand restart and the reinstall hint carry the project" {
    export DAAF_NESTED=1
    unset DAAF_PROJECT_NAME
    create_fake_compose_file
    printf '%s\n' "DAAF_PROJECT_NAME=Work" > "${TEST_DIR}/environment_settings.txt"
    run_daaf_running_mock
    export MOCK_RUN_DAAF_TESTF_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    assert_output --partial "modified since this container was started"
    assert_output --partial "11) Restart Container in the DAAF Control Panel"
    # Normalized as Docker Compose does: "Work" is project "work".
    grep -Fxq "        docker compose -p work down" <<< "${output}"
    grep -Fxq "  DAAF_PROJECT_NAME=work DAAF_FORCE_REINSTALL=1 bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh)\"" <<< "${output}"
    refute_output --regexp 'docker compose down'
}

@test "run_daaf: the reinstall hint carries DAAF_BRANCH (not main) and DAAF_DEV=1 from the settings file" {
    export DAAF_NESTED=1
    unset DAAF_PROJECT_NAME
    create_fake_compose_file
    printf '%s\n' "DAAF_BRANCH=feature-x" "DAAF_DEV=1" > "${TEST_DIR}/environment_settings.txt"
    run_daaf_running_mock
    export MOCK_RUN_DAAF_TESTF_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    grep -Fxq "  cd \"$(dirname "${TEST_DIR}")\"" <<< "${output}"
    # The URL stays on main: main's installer clones the branch DAAF_BRANCH names.
    grep -Fxq "  DAAF_BRANCH=feature-x DAAF_DEV=1 DAAF_FORCE_REINSTALL=1 bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh)\"" <<< "${output}"
    # DAAF_BRANCH=main prints no branch prefix.
    printf '%s\n' "DAAF_BRANCH=main" > "${TEST_DIR}/environment_settings.txt"
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_failure
    grep -Fxq "  DAAF_FORCE_REINSTALL=1 bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh)\"" <<< "${output}"
    refute_output --partial "DAAF_BRANCH="
}

@test "run_daaf: the default project prints the by-hand restart without -p, and the launch hint says /exit" {
    export DAAF_NESTED=1
    unset DAAF_PROJECT_NAME
    create_fake_compose_file
    printf '%s\n' "# keys" > "${TEST_DIR}/environment_settings.txt"
    run_daaf_running_mock
    export MOCK_RUN_DAAF_TESTF_EXIT=0
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_success
    grep -Fxq "        docker compose down" <<< "${output}"
    assert_output --partial "(Type /exit to leave Claude Code when you are done.)"
    refute_output --partial "Ctrl+C"
}

@test "run_daaf: custom command passthrough runs correctly" {
    export DAAF_NESTED=1
    create_fake_compose_file
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0

    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh" htop
    assert_output --partial "Running: htop"
}

@test "run_daaf: default command when no args launches claude" {
    export DAAF_NESTED=1
    create_fake_compose_file
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0

    run bash "${REPO_ROOT}/scripts/host/run_daaf.sh"
    assert_output --partial "Launching Claude Code"
}
