#!/usr/bin/env bats
# ============================================================================
# Tests for view_notebooks.sh — DAAF Notebook Browser
# ============================================================================
# Thin wrapper script — tests focus on preflight checks, container lifecycle,
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
# Tier 1 — Syntax
# =========================================================================

@test "view_notebooks.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
}

# =========================================================================
# Tier 2 — Preflight checks
# =========================================================================

# --- Preflight: missing docker-compose.yml ---

@test "view_notebooks.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "view_notebooks.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "view_notebooks.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "view_notebooks.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    refute_output --partial "Press Enter"
}

# =========================================================================
# Tier 3 — Script structure
# =========================================================================

@test "view_notebooks.sh includes set -euo pipefail" {
    run grep -c "set -euo pipefail" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh checks for docker-compose.yml" {
    run grep -c "docker-compose.yml" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh checks command -v docker" {
    run grep -c "command -v docker" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh checks docker info" {
    run grep -c "docker info" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh references launch_marimo.sh" {
    run grep -c "launch_marimo.sh" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh mentions Notebook Browser in output" {
    run grep -c "Notebook Browser" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh supports DAAF_TEST_MODE guard" {
    run grep -c "DAAF_TEST_MODE" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh supports DAAF_DRY_RUN" {
    run grep -c "DAAF_DRY_RUN" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# =========================================================================
# Tier 4 — Behavioral (DAAF_TEST_MODE)
# =========================================================================

@test "view_notebooks.sh exits cleanly when sourced with DAAF_TEST_MODE=1" {
    export DAAF_TEST_MODE=1
    run bash -c "source '${REPO_ROOT}/scripts/host/view_notebooks.sh'"
    assert_success
}

# =========================================================================
# Tier 5 — Dry-run
# =========================================================================

@test "view_notebooks.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
}

@test "view_notebooks.sh: dry-run produces DRY-RUN markers" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
}

@test "view_notebooks.sh: dry-run shows Notebook Browser message" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh" 2>&1
    assert_success
    assert_output --partial "Notebook Browser"
}

@test "view_notebooks.sh: dry-run reports container running" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
}

# =========================================================================
# Tier 6 — Error paths
# =========================================================================

# --- Container not running → start attempt ---

@test "view_notebooks.sh attempts to start container when not running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=0
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_output --partial "Starting DAAF container"
}

# --- Container start fails ---

@test "view_notebooks.sh fails when container start fails" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start the container"
}

# --- Notebook browser launch fails ---

@test "view_notebooks.sh reports error when notebook browser fails to start" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start the notebook browser"
}

# --- Container already running ---

@test "view_notebooks.sh reports container already running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_output --partial "DAAF container is running"
}
