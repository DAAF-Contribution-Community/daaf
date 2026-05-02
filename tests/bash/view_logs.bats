#!/usr/bin/env bats
# ============================================================================
# Tests for view_logs.sh — DAAF Log Explorer
# ============================================================================
# Thin wrapper script — tests focus on preflight checks, argument parsing,
# menu structure, and dry-run behavior.
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

# --- Argument parsing ---

@test "view_logs.sh --archive skips menu and opens log explorer" {
    export DAAF_NESTED=1
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh" --archive
    assert_success
    assert_output --partial "Opening DAAF Log Explorer"
}

@test "view_logs.sh --help shows usage" {
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh" --help
    assert_success
    assert_output --partial "Usage"
    assert_output --partial "--archive"
}

@test "view_logs.sh rejects unknown arguments" {
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh" --bogus
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Unknown argument"
}

# --- Script structure ---

@test "view_logs.sh includes recovery step" {
    run grep -c "recover-session-logs" "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_logs.sh includes menu selection prompt" {
    run grep -c "Select a log source" "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_logs.sh skips menu when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_success
    refute_output --partial "Select a log source"
    assert_output --partial "Opening DAAF Log Explorer"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "view_logs.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_logs.sh"
    assert_success
}

@test "view_logs.sh: dry-run opens log explorer" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_logs.sh" 2>&1
    assert_success
    assert_output --partial "Log Explorer"
}

@test "view_logs.sh: dry-run skips menu" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_logs.sh" 2>&1
    assert_success
    refute_output --partial "Select a log source"
}

@test "view_logs.sh: dry-run skips sleep" {
    # Dry-run should not sleep 2 seconds
    start_time=$SECONDS
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_logs.sh" 2>&1
    elapsed=$((SECONDS - start_time))
    assert_success
    [ "$elapsed" -lt 2 ]
}

@test "view_logs.sh: dry-run includes recovery step" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_logs.sh" 2>&1
    assert_success
    assert_output --partial "orphaned session logs"
}
