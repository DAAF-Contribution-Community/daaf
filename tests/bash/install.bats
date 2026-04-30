#!/usr/bin/env bats
# ============================================================================
# Tests for install.sh — DAAF One-Line Installer
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    mock_curl
    # install.sh does NOT require docker-compose.yml to exist beforehand
    # (it creates the install directory itself)
}

teardown() {
    common_teardown
}

# --- Syntax ---

@test "install.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
}

# --- Preflight: missing Docker ---

@test "install.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "install.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "install.sh suppresses pause trap when DAAF_NESTED=1" {
    # With DAAF_NESTED=1, the script should not set the EXIT trap
    # for read -r -p. We test this indirectly: the script will fail
    # (mocked docker info succeeds but curl creates empty files which
    # won't build), but the important thing is it does not hang on
    # "Press Enter".
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should not contain the pause prompt
    refute_output --partial "Press Enter"
}

# --- Existing installation detection ---

@test "install.sh detects existing installation and warns" {
    # Create the install directory with a compose file
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    # Mock docker volume inspect to succeed (volume exists)
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    # Run from a directory where daaf-docker/ exists
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "WARNING"
    assert_output --partial "existing DAAF installation"
}

# --- Download file list ---

@test "install.sh attempts to download required files" {
    export DAAF_NESTED=1
    # curl mock creates empty files; compose build will fail but we can
    # check that it gets past the download step
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # The script should have tried to download and then failed at build
    assert_failure
    assert_output --partial "Downloading"
}

# --- Branch override ---

@test "install.sh respects DAAF_BRANCH environment variable" {
    export DAAF_BRANCH="dev"
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "Branch: dev"
}

# --- Fresh install proceeds when no compose file exists ---

@test "install.sh proceeds with downloads when no prior installation exists" {
    # No compose file in daaf-docker/ — fresh install path
    export DAAF_NESTED=1
    # Build will fail, but downloads should be attempted
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should reach the download step (no "existing installation" block)
    assert_output --partial "Downloading"
    refute_output --partial "existing DAAF installation"
}

# --- Incomplete installation detection ---

@test "install.sh proceeds when compose file exists but volume does not" {
    # Compose file present but volume inspect fails — incomplete install
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_DOCKER_VOLUME_EXIT=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should note incomplete install and continue
    assert_output --partial "previous install attempt"
    assert_output --partial "incomplete"
    assert_output --partial "Downloading"
}

# --- DAAF_FORCE_REINSTALL bypasses existing check ---

@test "install.sh proceeds when DAAF_FORCE_REINSTALL=1 despite existing installation" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_COMPOSE_EXIT=1
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should note force reinstall and proceed (not block)
    assert_output --partial "DAAF_FORCE_REINSTALL"
    assert_output --partial "Downloading"
    refute_output --partial "To update DAAF instead"
}

# --- Default branch is 'main' ---

@test "install.sh defaults to branch 'main' when DAAF_BRANCH is unset" {
    unset DAAF_BRANCH
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "Branch: main"
}

# --- Download failure exits non-zero ---

@test "install.sh exits with error when downloads fail" {
    export DAAF_NESTED=1
    MOCK_CURL_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to download"
}

# --- Download file list coverage ---

@test "install.sh downloads all required lifecycle scripts" {
    # Override curl to log the URLs it receives
    curl() {
        local outfile=""
        local url=""
        local args=("$@")
        for ((i=0; i<${#args[@]}; i++)); do
            case "${args[$i]}" in
                -o) outfile="${args[$((i+1))]}" ;;
                http*) url="${args[$i]}" ;;
            esac
        done
        echo "CURL_URL: ${url}" >> "${TEST_DIR}/curl_log.txt"
        if [ -n "${outfile}" ]; then
            touch "${outfile}"
        fi
        return 0
    }
    export -f curl

    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"

    # Verify all expected files were requested
    [ -f "${TEST_DIR}/curl_log.txt" ]
    run grep -c "CURL_URL:" "${TEST_DIR}/curl_log.txt"
    # Should download: Dockerfile, docker-compose.yml, run_daaf.sh,
    # backup_daaf.sh, rebuild_daaf.sh, update_daaf.sh, view_logs.sh, environment_settings_example.txt
    [ "$output" -ge 8 ]

    run cat "${TEST_DIR}/curl_log.txt"
    assert_output --partial "Dockerfile"
    assert_output --partial "docker-compose.yml"
    assert_output --partial "run_daaf.sh"
    assert_output --partial "backup_daaf.sh"
    assert_output --partial "update_daaf.sh"
    assert_output --partial "environment_settings_example.txt"
}

# --- Download URLs use correct path prefix ---

@test "install.sh download URLs contain scripts/host/ prefix for lifecycle scripts" {
    curl() {
        local url=""
        local outfile=""
        local args=("$@")
        for ((i=0; i<${#args[@]}; i++)); do
            case "${args[$i]}" in
                -o) outfile="${args[$((i+1))]}" ;;
                http*) url="${args[$i]}" ;;
            esac
        done
        echo "${url}" >> "${TEST_DIR}/curl_urls.txt"
        if [ -n "${outfile}" ]; then
            touch "${outfile}"
        fi
        return 0
    }
    export -f curl

    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"

    [ -f "${TEST_DIR}/curl_urls.txt" ]
    # All .sh and environment_settings_example.txt downloads should use scripts/host/ prefix
    run grep "scripts/host/" "${TEST_DIR}/curl_urls.txt"
    assert_success
}

# --- Creates daaf-docker directory ---

@test "install.sh creates daaf-docker directory" {
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # The directory should have been created
    [ -d "${TEST_DIR}/daaf-docker" ]
}

# --- Build step invoked ---

@test "install.sh invokes docker compose build" {
    export DAAF_NESTED=1
    # Let build succeed, but up fail so we don't reach later steps
    MOCK_DOCKER_COMPOSE_EXIT=0
    # Actually: compose mock returns same exit for build and up.
    # We need compose to eventually stop. Let exec fail for the readiness check.
    MOCK_DOCKER_EXEC_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "Building Docker image"
}

# --- Readiness check looks for CLAUDE.md ---

@test "install.sh verifies CLAUDE.md exists in container" {
    export DAAF_NESTED=1
    # exec mock returns success — test -f /daaf/CLAUDE.md passes
    MOCK_DOCKER_EXEC_EXIT=0
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # If readiness + clone + verify all succeed, should reach completion
    assert_output --partial "Installation complete"
}

# --- Existing installation suggests update_daaf.sh ---

@test "install.sh suggests update_daaf.sh when blocking on existing installation" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "update_daaf.sh"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "install.sh: dry-run completes successfully" {
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    # Clean up the daaf-docker directory created by install.sh
    rm -r "${TEST_DIR}/daaf-docker" 2>/dev/null || true
}

@test "install.sh: dry-run produces DRY-RUN markers" {
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
    # Clean up the daaf-docker directory created by install.sh
    rm -r "${TEST_DIR}/daaf-docker" 2>/dev/null || true
}
