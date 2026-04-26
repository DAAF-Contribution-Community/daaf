#!/usr/bin/env bats
# ============================================================================
# Tests for run_daaf.sh — DAAF Launcher
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
