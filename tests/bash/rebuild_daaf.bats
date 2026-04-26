#!/usr/bin/env bats
# ============================================================================
# Tests for rebuild_daaf.sh — DAAF Rebuild Utility
# ============================================================================
# Key testable logic: preflight checks, docker-compose.yml requirement,
# container existence check, file hash comparison.
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

@test "rebuild_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_success
}

# --- Preflight: missing docker-compose.yml ---

@test "rebuild_daaf.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "rebuild_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "rebuild_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- Preflight: container not found ---

@test "rebuild_daaf.sh fails when container does not exist" {
    MOCK_DOCKER_INSPECT_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

# --- DAAF_NESTED behavior ---

@test "rebuild_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INSPECT_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Banner display ---

@test "rebuild_daaf.sh displays the DAAF Rebuild banner" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INSPECT_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_output --partial "DAAF Rebuild"
}

# --- Numbered progress steps ---

@test "rebuild_daaf.sh uses numbered progress steps [1/3] [2/3] [3/3]" {
    run grep -c '\[1/3\]\|\[2/3\]\|\[3/3\]' "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_success
    [ "${output}" -ge 3 ]
}
