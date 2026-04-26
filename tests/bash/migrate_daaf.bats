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
