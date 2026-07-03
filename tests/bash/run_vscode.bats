#!/usr/bin/env bats
# ============================================================================
# Tests for run_vscode.sh -- DAAF Code Browser (VS Code in the browser)
# ============================================================================
# Thin wrapper script -- tests focus on preflight checks, container lifecycle,
# dry-run behavior, and structural markers.
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

# =========================================================================
# Tier 1 -- Syntax
# =========================================================================

@test "run_vscode.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
}

# =========================================================================
# Tier 2 -- Preflight checks
# =========================================================================

# --- Preflight: missing docker-compose.yml ---

@test "run_vscode.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "run_vscode.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "run_vscode.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "run_vscode.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    refute_output --partial "Press Enter"
}

# =========================================================================
# Tier 3 -- Script structure
# =========================================================================

@test "run_vscode.sh includes set -euo pipefail" {
    run grep -c "set -euo pipefail" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh checks for docker-compose.yml" {
    run grep -c "docker-compose.yml" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh checks command -v docker" {
    run grep -c "command -v docker" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh checks docker info" {
    run grep -c "docker info" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh references launch_code_server.sh" {
    run grep -c "launch_code_server.sh" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh mentions Code Browser in output" {
    run grep -c "Code Browser" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh supports DAAF_TEST_MODE guard" {
    run grep -c "DAAF_TEST_MODE" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh supports DAAF_DRY_RUN" {
    run grep -c "DAAF_DRY_RUN" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# =========================================================================
# Tier 4 -- Behavioral (DAAF_TEST_MODE)
# =========================================================================

@test "run_vscode.sh exits cleanly when sourced with DAAF_TEST_MODE=1" {
    export DAAF_TEST_MODE=1
    run bash -c "source '${REPO_ROOT}/scripts/host/run_vscode.sh'"
    assert_success
}

# =========================================================================
# Tier 5 -- Dry-run
# =========================================================================

@test "run_vscode.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
}

@test "run_vscode.sh: dry-run completes without real Docker" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
    assert_output --partial "Code Browser"
}

@test "run_vscode.sh: dry-run shows Code Browser message" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh" 2>&1
    assert_success
    assert_output --partial "Code Browser"
}

@test "run_vscode.sh: dry-run reports container running" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
}

# =========================================================================
# Tier 6 -- Error paths
# =========================================================================

# --- Container not running → start attempt ---

@test "run_vscode.sh attempts to start container when not running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=0
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_output --partial "Starting DAAF container"
}

# --- Container start fails ---

@test "run_vscode.sh fails when container start fails" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start the container"
}

# --- Code-server launch fails ---

@test "run_vscode.sh reports error when code-server fails to start" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start code-server"
}

# --- Container already running ---

@test "run_vscode.sh reports container already running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_output --partial "DAAF container is running"
}

# =========================================================================
# Browser auto-open (open_url integration)
# =========================================================================

@test "run_vscode.sh sources daaf_lib.sh when present" {
    run grep -c "source.*daaf_lib.sh" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh calls open_url with the host VS Code port (default 2720)" {
    # The URL uses the overridable host port var (defaults to 2720). Assert the
    # parameterized form plus the default resolution.
    run grep 'open_url.*DAAF_PORT_VSCODE' "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    assert_output --partial 'http://localhost:${DAAF_PORT_VSCODE}'
    run grep 'DAAF_PORT_VSCODE:-2720' "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
}

@test "run_vscode.sh guards open_url behind command -v check" {
    # Verify the script uses a guard pattern so open_url is only called
    # when the function is actually available (backwards compatible when
    # daaf_lib.sh is absent).
    run grep "command -v open_url" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    assert_output --partial "open_url"
}

@test "run_vscode.sh dry-run completes with library sourcing" {
    # With daaf_lib.sh present, open_url is a no-op in dry-run mode.
    # Confirms the full script (including library sourcing) works end-to-end.
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    assert_output --partial "Code Browser"
}
