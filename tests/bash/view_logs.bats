#!/usr/bin/env bats
# ============================================================================
# Tests for view_logs.sh — DAAF Log Explorer
# ============================================================================
# Thin wrapper script — tests focus on preflight checks and structure.
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

@test "view_logs.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_success
}

# --- Preflight: missing docker-compose.yml ---

@test "view_logs.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "view_logs.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "view_logs.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "view_logs.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh"
    refute_output --partial "Press Enter"
}

# --- Container start when not running ---

@test "view_logs.sh attempts to start container when not running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=0
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_output --partial "Starting DAAF container"
}

# --- Log Explorer invocation ---

@test "view_logs.sh references generate_log_viewer.sh" {
    run grep -c "generate_log_viewer.sh" "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_success
    [ "${output}" -ge 1 ]
}
